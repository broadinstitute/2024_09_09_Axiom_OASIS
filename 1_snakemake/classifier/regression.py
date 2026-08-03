import numpy as np
import pandas as pd
import polars as pl
import xgboost as xgb
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
from sklearn.model_selection import GroupShuffleSplit
from tqdm import tqdm


def xgboost_regression(dat: pd.DataFrame, target: str, feat_cols: list, split_group: str, *, mean_pred: bool = False) -> pl.DataFrame:
    """Predict continuous metadata from profiling data with XGBoost."""

    groups = dat[split_group]
    gss = GroupShuffleSplit(n_splits=10, test_size=0.2, random_state=42)
    i = 1
    results = []
    pred_obs = []

    for split_idx, (train_idx, test_idx) in tqdm(enumerate(gss.split(dat, groups=groups))):
        # Splitting the dataset
        train_data = dat.iloc[train_idx]
        test_data = dat.iloc[test_idx]

        train_data = train_data.dropna(subset=[target]).reset_index(drop=True)
        test_data = test_data.dropna(subset=[target]).reset_index(drop=True)
        
        X_train = train_data[feat_cols]
        y_train = train_data[target]
        X_test = test_data[feat_cols]
        y_test = test_data[target]

        # Train model
        if mean_pred:
            mean_value = np.mean(y_train)
            predictions = np.full(len(y_test), mean_value)
        else: 
            model = xgb.XGBRegressor(objective="reg:squarederror")
            model.fit(X_train, y_train)
            predictions = model.predict(X_test)

        # Calculate performance
        mse = mean_squared_error(y_test, predictions)
        r2 = r2_score(y_test, predictions)
        rmse = np.sqrt(mse)
        mae = mean_absolute_error(y_test, predictions)

        results.append((target, split_idx, r2, rmse, mae))
        pred_obs.append(pl.DataFrame({
            "Predicted": predictions,
            "Observed": y_test.values,
            # .tolist(), not .values: pandas stores these as object dtype, and
            # polars 0.20 types a numpy object array as Object, not Utf8.
            # Writing an Object column to parquet serialises the raw Python
            # object pointers, so the file ends up holding bytes like
            # b'\xf0(\xf0\x05\xfa\x7f\x00\x00' -- identical on every row --
            # instead of the plate/well/compound identifiers. That silently
            # destroys these columns and makes any downstream join on them fail.
            # A Python list is inferred as Utf8 correctly.
            "Metadata_Plate": test_data["Metadata_Plate"].tolist(),
            "Metadata_Well": test_data["Metadata_Well"].tolist(),
            "Metadata_Compound": test_data["Metadata_Compound"].tolist(),
            "Metadata_OASIS_ID": test_data["Metadata_OASIS_ID"].tolist(),
            "Metadata_Log10Conc": test_data["Metadata_Log10Conc"].values,
            "Variable": target,
            "Split": i,
        }))

    # Convert results to DataFrame for analysis
    results_df = pd.DataFrame(results, columns=["Variable", "Split", "R²", "RMSE", "MAE"])
    pred_obs_df = pl.concat(pred_obs, how="vertical_relaxed").to_pandas()

    return results_df, pred_obs_df


def predict_axiom_assays(prof_path: str, prediction_path: str, results_path: str) -> None:
    """Train XGBoost regression model to predict Axiom assays."""
    profiles = pd.read_parquet(prof_path)
    profiles = profiles.dropna(subset=["Metadata_OASIS_ID"]).reset_index(drop=True)
    profiles = profiles[profiles["Metadata_Perturbation"] != "DMSO_0.0"].reset_index(drop=True)
    profiles["Metadata_Log10Conc"] = np.round(profiles["Metadata_Log10Conc"], 2)

    # Encoding categorical columns
    profiles["Metadata_Plate_cat"] = profiles["Metadata_Plate"].astype("category").cat.codes
    profiles["Metadata_source_cat"] = profiles["Metadata_source"].astype("category").cat.codes
    profiles["Metadata_Well_cat"] = profiles["Metadata_Well"].astype("category").cat.codes
    profiles["Metadata_Compound_cat"] = profiles["Metadata_Compound"].astype("category").cat.codes

    feat_cols = [i for i in profiles.columns if "Metadata" not in i]
    baseline_cols = ["Metadata_Plate_cat", "Metadata_Well_cat", "Metadata_source_cat", "Metadata_Count_Cells"]

    # LDH
    ldh_bl_res, ldh_bl_pred = xgboost_regression(
        profiles,
        "Metadata_ldh_ridge_norm",
        baseline_cols,
        "Metadata_Compound"
    )
    ldh_bl_pred["Variable_Name"] = "Metadata_ldh_ridge_norm"
    ldh_bl_pred["Model_type"] = "Baseline"
    ldh_bl_res["Variable_Name"] = "Metadata_ldh_ridge_norm"
    ldh_bl_res["Model_type"] = "Baseline"

    ldh_res, ldh_pred = xgboost_regression(
        profiles,
        "Metadata_ldh_ridge_norm",
        feat_cols,
        "Metadata_Compound"
    )
    ldh_pred["Variable_Name"] = "Metadata_ldh_ridge_norm"
    ldh_pred["Model_type"] = "Morphology"
    ldh_res["Variable_Name"] = "Metadata_ldh_ridge_norm"
    ldh_res["Model_type"] = "Morphology"

    ldh_mean_res, ldh_mean_pred = xgboost_regression(
        profiles,
        "Metadata_ldh_ridge_norm",
        [],
        "Metadata_Compound",
        mean_pred=True
    )
    ldh_mean_pred["Variable_Name"] = "Metadata_ldh_ridge_norm"
    ldh_mean_pred["Model_type"] = "Mean_predictor"
    ldh_mean_res["Variable_Name"] = "Metadata_ldh_ridge_norm"
    ldh_mean_res["Model_type"] = "Mean_predictor"

    # MTT
    mtt_res, mtt_pred = xgboost_regression(
        profiles,
        "Metadata_mtt_ridge_norm",
        feat_cols,
        "Metadata_Compound"
    )
    mtt_pred["Variable_Name"] = "Metadata_mtt_ridge_norm"
    mtt_pred["Model_type"] = "Morphology"
    mtt_res["Variable_Name"] = "Metadata_mtt_ridge_norm"
    mtt_res["Model_type"] = "Morphology"

    mtt_bl_res, mtt_bl_pred = xgboost_regression(
        profiles,
        "Metadata_mtt_ridge_norm",
        baseline_cols,
        "Metadata_Compound"
    )
    mtt_bl_pred["Variable_Name"] = "Metadata_mtt_ridge_norm"
    mtt_bl_pred["Model_type"] = "Baseline"
    mtt_bl_res["Variable_Name"] = "Metadata_mtt_ridge_norm"
    mtt_bl_res["Model_type"] = "Baseline"

    mtt_mean_res, mtt_mean_pred = xgboost_regression(
        profiles,
        "Metadata_mtt_ridge_norm",
        [],
        "Metadata_Compound",
        mean_pred=True
    )
    mtt_mean_pred["Variable_Name"] = "Metadata_mtt_ridge_norm"
    mtt_mean_pred["Model_type"] = "Mean_predictor"
    mtt_mean_res["Variable_Name"] = "Metadata_mtt_ridge_norm"
    mtt_mean_res["Model_type"] = "Mean_predictor"

    # Write out predictions
    prediction_df = pd.concat(
        [ldh_pred, ldh_bl_pred, ldh_mean_pred, mtt_pred, mtt_bl_pred, mtt_mean_pred], 
        ignore_index=True
    )
    prediction_df.to_parquet(prediction_path)

    # Write out results
    res_df = pd.concat(
        [ldh_res, ldh_bl_res, ldh_mean_res, mtt_res, mtt_bl_res, mtt_mean_res], 
        ignore_index=True
    )
    res_df.to_parquet(results_path)