# Method contract evidence

This note records method-level agreements and deviations between the camera-ready paper and the implementation at the `6ca56dc` reproduction baseline.
No workflow was rerun for this check.

## METHOD-CLASSIFIER

The classifier implementation sets `n_splits = 5` and passes it to `StratifiedKFold` in `1_snakemake/classifier/classify.py`.
This agrees with the five-fold, compound-level, stratified classifier procedure described in STAR Methods.

Decision: `reproduced`.

## METHOD-REGRESSION

Table 1 reports performance across ten train-test splits.
The regression implementation uses `GroupShuffleSplit(n_splits=10, test_size=0.2, random_state=42)` with compound groups in `1_snakemake/classifier/regression.py`.
The implementation therefore matches Table 1: ten repeated 80/20 splits with compound-level group isolation.

STAR Methods says that all scenarios used five-fold cross-validation.
That universal statement does not describe the regression implementation or Table 1.

Decision: `reproduced-with-deviation` because the code and table agree while STAR Methods is internally inconsistent.

## METHOD-POD

The paper generally describes selecting the model with the lowest residual standard deviation for morphology, cell count, MT, and LDH concentration-response fits.
The implementation uses that rule for Cell Painting distances by setting `filt.var = "SDres"`.
Cell count, MT, and LDH instead use the default rounded-AIC model selection in `fastbmdR::scoresPOD`.
The remaining documented contracts still apply: eight model families, the DMSO 95th-percentile benchmark response, confidence-interval ratio filtering, and tested-concentration filtering.

Decision: `reproduced-with-deviation` because the model-selection difference is real and can change discrete model and POD pass calls.
The numerical consequences are reported in `paper/REPRODUCING.md`.
