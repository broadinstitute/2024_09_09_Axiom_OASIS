import hashlib

import numpy as np
import pandas as pd
import polars as pl
from copairs import map
from copairs.matching import assign_reference_index
from joblib import Parallel, delayed
from tqdm import tqdm

n_cpus = 10


def _rng_for(context: str, compound: str) -> np.random.Generator:
    payload = f"axiom-oasis-ap-v1\0{context}\0{compound}".encode()
    seed = int.from_bytes(hashlib.sha256(payload).digest()[:8], byteorder="big")
    return np.random.default_rng(seed)


def phenotypic_consistency_dmso(cmpd: str, prof_path: str):

    rng = _rng_for("dmso", cmpd)

    profiles = pl.read_parquet(prof_path)
    feat_cols = [i for i in profiles.columns if "Metadata" not in i]
    dmso_profiles = profiles.filter(pl.col("Metadata_Compound") == "DMSO")

    cmpd_profs = profiles.filter(pl.col("Metadata_Compound") == cmpd)
    cmpd_plates = cmpd_profs.select(pl.col("Metadata_Plate")).to_series().unique().to_list()
    cmpd_dmso = dmso_profiles.filter(pl.col("Metadata_Plate").is_in(cmpd_plates)).with_row_index().with_columns(
        pl.lit(cmpd).alias("Metadata_Compound_DMSO")
    )

    # Choose 720 samples to have even multiple of 16
    indices = rng.choice(np.arange(cmpd_dmso.shape[0]), size=720, replace=False)
    cmpd_dmso = cmpd_dmso.filter(pl.col("index").is_in(indices))

    # create random DMSO groups
    categories = rng.permutation(np.repeat(np.arange(1, 46), 16))
    cmpd_dmso = cmpd_dmso.with_columns(
        pl.Series("Metadata_DMSO_Category", categories)
    ).to_pandas()

    # Calculate phenotypic consistency
    pos_sameby = ["Metadata_DMSO_Category"]
    pos_diffby = []
    neg_sameby = []
    neg_diffby = ["Metadata_DMSO_Category"]

    metadata = cmpd_dmso.filter(regex="^Metadata")
    cmpd_feats = cmpd_dmso.filter(regex="^(?!Metadata)").values

    activity_ap = map.average_precision(
        metadata, cmpd_feats, pos_sameby, pos_diffby, neg_sameby, neg_diffby
    )

    return activity_ap


def phenotypic_activity_compound(cmpd: str, prof_path: str):
    """ Function to process each compound in parallel """

    rng = _rng_for("compound", cmpd)

    # get data
    profiles = pl.scan_parquet(prof_path)
    feat_cols = [i for i in profiles.collect_schema().names() if "Metadata" not in i]
    dmso_profiles = profiles.filter(pl.col("Metadata_Compound") == "DMSO")

    # select only data for cmpd
    cmpd_profs = profiles.filter(pl.col("Metadata_Compound") == cmpd).collect()
    cmpd_plates = cmpd_profs.select(pl.col("Metadata_Plate")).to_series().unique().to_list()
    cmpd_dmso = dmso_profiles.filter(pl.col("Metadata_Plate").is_in(cmpd_plates)).collect().with_row_index()

    # Choose 720 samples to have even multiple of 16
    indices = rng.choice(np.arange(cmpd_dmso.shape[0]), size=720, replace=False)
    cmpd_dmso = cmpd_dmso.filter(pl.col("index").is_in(indices)).drop("index")

    cmpd_df = pl.concat([cmpd_profs, cmpd_dmso]).to_pandas()

    # calculate phenotypic activity
    reference_col = "Metadata_reference_index"

    df_activity = assign_reference_index(
        cmpd_df,
        "Metadata_Compound == 'DMSO'",
        reference_col=reference_col,
        default_value=-1,
    )

    pos_sameby = ["Metadata_Compound", reference_col]
    pos_diffby = []
    neg_sameby = []
    neg_diffby = ["Metadata_Compound", reference_col]

    metadata = df_activity.filter(regex="^Metadata")
    cmpd_feats = df_activity.filter(regex="^(?!Metadata)").values

    activity_ap = map.average_precision(
        metadata, cmpd_feats, pos_sameby, pos_diffby, neg_sameby, neg_diffby
    )

    return activity_ap


def calculate_ap(prof_path: str):

    lf = pl.scan_parquet(prof_path)
    compounds = lf.select("Metadata_Compound").collect().to_series().unique().to_list()
    compounds = sorted(i for i in compounds if "DMSO" not in i)

    # Calculate dmso AP in parallel
    dmso_results = Parallel(n_jobs=n_cpus)(delayed(phenotypic_consistency_dmso)(cmpd, prof_path) for cmpd in tqdm(compounds))
    dmso_ap = pd.concat(dmso_results)

    # Calculate cmpd AP in parallel
    cmpd_results = Parallel(n_jobs=n_cpus)(delayed(phenotypic_activity_compound)(cmpd, prof_path) for cmpd in tqdm(compounds))
    cmpd_ap = pd.concat(cmpd_results)

    # Combine everything together
    cmpd_ap = pl.DataFrame(cmpd_ap).filter(~pl.col("average_precision").is_null()).drop("Metadata_reference_index")
    meta_cols = [i for i in cmpd_ap.columns if "Metadata" in i]
    cmpd_ap = cmpd_ap.select(meta_cols + ["average_precision"])

    dmso_ap = pl.DataFrame(dmso_ap).drop(["Metadata_Compound"]).with_columns(
        pl.concat_str([pl.lit("DMSO"), pl.col("Metadata_Compound_DMSO")], separator="_").alias("Metadata_Compound")
    ).select(meta_cols + ["average_precision"])

    ap = pl.concat([dmso_ap, cmpd_ap]).rename({"average_precision": "Distance"}).with_columns(
        pl.lit("ap").alias("Metadata_Distance")
    )

    return ap


def calculate_distances(prof_path: str, dist_path: str, method: str):

    if method == "ap":
        dist = calculate_ap(prof_path)
        dist.write_parquet(dist_path)
    else:
        print("METHOD NOT FOUND")
