# Remaining paper-reproduction targets

This note resolves `TABLE-S1`, `TABLE-S5`, `METHOD-STATS`, `RESOURCE-001`, and `INTERPRETATION-001` from the repository state at `4c000a2bbfeee449e2f76125e0a892d3c7df38c4`.
The audit was read-only apart from this note and the target ledger.
No notebook, scientific pipeline, external service, or remote data source was executed or changed.

## Inputs and audit method

The camera-ready paper was read from `paper/sources/main.pdf` after conversion with `pdftotext -layout` and checked against `paper/paper.md`.
The two workbooks were queried directly as Office Open XML archives with Python standard-library `zipfile.ZipFile` and `xml.etree.ElementTree`, resolving `sharedStrings.xml` and retaining worksheet rows with a nonblank first cell.
The Parquet and CSV calculations used the pinned `pipeline` environment through `pixi run -e pipeline python` and Polars group-by, unique-set, and exact-key comparisons.
Repository tracking and access checks used `git ls-files`, `git check-ignore -v`, `git remote -v`, `stat`, `find`, `sha256sum`, and `md5sum`.

The principal input SHA-256 values were:

- camera-ready PDF: `b24665d58da4c7e12fc37165c15003e36a3e5fbd4ad431457dadfe656f7df80c`;
- Table S1 workbook: `345dff689db7d3e0ed2c6d39403879b755c3526e33360d66f874c9dc7828560d`;
- Table S5 workbook: `112432976c3f944d5ca953481bfbec808fb25c065c218bf1e258508ccfc0e7e5`;
- processed metadata: `92c2a3c4d305d5a8c17efe467ceb1cde6a6c5505e51d395f1d0300882277f8ff`;
- OASIS annotation catalog: `6357f30cb4bc12bbe703a028854f465590d487f9f31126083281855dd71ee845`;
- ToxCast cell-based info: `0ab624a053c7344bf53e3d597d99aac3ec2ec6fe1c97b0c2a35012313bfc9d72`;
- ToxCast cytotoxicity info: `b2133166d6562e8310606677888b88a53db9f280b27bbaa565c4dacd476d5988`;
- ToxCast cytotoxicity binary: `0b5ebf947a7bce28b65ab54bc3622b65b41ea5930ccf381109ad3db63dfda1d0`.

## TABLE-S1

The published workbook has 1,085 nonblank data rows.
It contains 966 unique nonblank OASIS IDs and 119 rows whose OASIS ID, source code, and compound URL are blank.
The processed metadata has 1,085 unique non-DMSO compound names, 967 nonblank OASIS IDs, and the same 119 null-ID compound labels after DMSO is excluded.

Set comparison on OASIS ID found no workbook ID absent from metadata.
Metadata has one tested ID absent from the workbook: `OASIS1752`, Ribociclib, represented by 16 wells and present in the annotation catalog.
The 119 workbook labels without stable IDs match the 119 non-DMSO null-ID metadata labels exactly.

For the 966 shared stable IDs, 965 workbook names equal `Metadata_Compound` exactly.
The sole mismatch is `OASIS330`, where the workbook contains a character-encoding corruption of beta-Naphthoflavone and metadata contains the readable beta-Naphthoflavone label.
The workbook also has two Vasopressin rows, `OASIS1751` and `OASIS679`, with the same source code and URL.
The processed metadata preserves both IDs under the same compound name.
Consequently, the workbook has 1,085 rows but 1,084 unique displayed compound names, while metadata has 1,085 unique non-control names because it additionally includes Ribociclib.

The annotation catalog has 1,494 rows and 1,477 unique OASIS IDs.
All 966 published stable IDs are present and marked `Purchased_Axiom_Medchemxpress == Yes`.
Preferred names agree exactly for 790 of 966 IDs and differ for 176, principally because of synonyms, salts, systematic names, capitalization, or vendor labels.
For example, `OASIS483` is 2-Ethylanthracene-9,10-dione in the workbook and processed metadata but 2-Ethylanthraquinone in the preferred-name catalog.
The stable identifier, rather than a display label, is therefore the semantic join key.

The workbook has 891 MedChemExpress URLs and 194 blank URLs.
This URL incompleteness does not change tested-library membership, but it prevents byte-for-byte or label-for-label agreement from being an appropriate conclusion.

Decision: `reproduced-with-deviation`.
The 966 published stable IDs and 119 blinded labels have complete semantic coverage in committed metadata, while Ribociclib is an extra tested metadata member, Vasopressin is duplicated under two stable IDs, one name is encoding-corrupted, and preferred-name labels differ for 176 stable IDs.

## TABLE-S5

The published workbook has 22 nonblank data rows, and all 22 are marked `Active` and `REPR == TRUE`.
Exactly 12 of 22 rows have `INTENDED_TARGET_FAMILY == nuclear receptor`.
Their AC50 values range from 1.64808942 to 45 uM and cover RARA, ESRRA, NR1I3, ESR1, PGR, NR1I2, PPARG, and VDR across 12 assays.
This reproduces the paper's approximate 1-45 uM statement and its eight example genes.

All 22 workbook rows have `CYTOTOX_BURST == 1000`, but repository code does not define that exported field or its sentinel semantics.
Independent pinned evidence is stronger: `OASIS483` has 19 curated cell or tissue cytotoxicity categories assembled from 102 source tests, with zero source hits and zero non-null consensus cytotoxicity AC50 values.
All 19 observed values in the retained cytotoxicity binary row are zero.

The pinned cell-based info has 87 endpoint rows for `OASIS483`.
Fifteen of the 22 workbook endpoints are present, and every shared endpoint has `hitcall > 0.9`.
Their AC50 values agree with the workbook to a maximum absolute difference of `4.81225e-08` uM, reflecting workbook rounding.
The shared set contains eight of the 12 published nuclear-receptor assays.
The seven workbook endpoints absent from the pinned curated info include four nuclear-receptor assays: `TOX21_RAR_LUC_Agonist`, `ATG_ERa_TRANS`, `ATG_PXR_TRANS`, and `ATG_PPARg_TRANS`.

The workbook and pinned info both contain `TOX21_MMP_ratio` at AC50 14.8795941 uM, with pinned hit call 0.999797722.
The pinned row describes a HepG2 mitochondrial membrane-potential reporter, a mitochondria target subtype, a mitochondrial-depolarization biological-process label, and a gain signal direction.
This directly supports an active mitochondrial-depolarization-related endpoint.
It does not by itself encode the paper's directional phrase "decreased mitochondrial depolarization" or prove oxidative-phosphorylation uncoupling.

Decision: `reproduced-with-deviation`.
The workbook exactly supports 12 nuclear-receptor assays, the stated concentration range, no-cytotoxicity annotation, and an MMP signal, while pinned curated inputs retain only 8 of those 12 receptor endpoints and provide assay activity rather than a causal uncoupling mechanism.

## METHOD-STATS

The camera-ready Quantification and Statistical Analysis section and `paper/paper.md` both declare `p < 0.05` for single-hypothesis tests, `FDR < 0.05` for multiple-hypothesis correction, 5,500 initially seeded cells per well, and sixteen wells per compound from eight concentrations with two replicates each.
The Cell Culture and Supervised Analysis sections independently repeat the seeding density and the `8 x 2 = 16` design.

The notebooks compute paired t-test p-values, mixed-model Tukey HSD p-values, and one-sided hypergeometric enrichment p-values.
The enrichment notebooks apply Benjamini-Hochberg correction with `multipletests(p_values, method='fdr_bh', is_sorted=False)`.
The existing enrichment evidence independently recalculates the stored p-values and FDR values and uses FDR below 0.05 for significant target sets.
No shared executable constant enforces either 0.05 threshold across all analyses, and several notebooks print p-values without applying an explicit repository-side decision gate.
The thresholds are therefore declared methods plus analysis-specific interpretation, rather than one centrally executable contract.

Initial seeding density is absent from committed processed metadata.
`Metadata_Count_Cells` instead records post-treatment counts, as the paper states.
Across 16,607 non-DMSO metadata rows, every final count is present, with minimum 1, median 785, and maximum 1,349 cells.
Those values cannot be used to recompute the initial 5,500-cell seeding claim.

The processed metadata contains 1,085 unique non-DMSO compound names and 16,607 retained wells.
Wells per displayed compound are 16 for 446 compounds, 15 for 318, 14 for 311, 13 for one, and greater than 16 for nine compounds because repeated exposures are retained.
At compound-concentration grain, 1,084 compounds retain all eight concentrations and one retains seven.
Of 8,679 retained compound-concentration groups, 7,672 have exactly two wells, 941 have one, and 66 have more than two.
The profile aggregation code takes the median of all available rows by OASIS ID and does not assert a 16-row cardinality.

Decision: `reproduced-with-deviation`.
All four published constants trace exactly as declared methods, Benjamini-Hochberg FDR is executable, and the design arithmetic is explicit, while initial seeding cannot be recomputed and the processed dataset does not retain exactly sixteen rows for every compound.

## RESOURCE-001

The camera-ready resource table and repository contract name the Cell Painting Gallery accession `cpg0037-oasis/axiom` for raw images, metadata, CellProfiler profiles, CP-CNN profiles, and DINO profiles.
Tracked download scripts encode the same metadata and profile paths, while `Plot_images.ipynb` encodes `s3://cellpainting-gallery/cpg0037-oasis/axiom/images` for raw TIFF access.
The saved checkout contains no local TIFF or rendered PNG image directory; `1_snakemake/inputs/images/index.parquet` is an image-location index rather than raw image data.
Raw-image reproduction therefore depends on the external Cell Painting Gallery.

The saved checkout contains the five compiled Zenodo inputs described by `README.md` and `REPRODUCING.md`.
Their byte sizes and MD5 values match the documented record 17067683 values: CellProfiler `413433180 / 0cf2b9d11268c363d756e69851a1a568`, DINO `399927644 / 421529eb80880721eaa42bdcd26920d5`, CP-CNN `48201019 / d79b1cebc8aa3999fa993ea2500fab8d`, metadata `734477 / 6731b56f8f4fe2db31fcdf1308c305fb`, and image index `2524798 / b56e249504f76bc2f6025f90abc8608c`.
All five are ignored by `1_snakemake/.gitignore`, so a fresh repository clone must retrieve them externally.

The saved checkout also contains 99 ignored pipeline-output files.
The repository tracks 10 annotation inputs and 17 final compiled-result files, so important processed evidence is repository-local even though the complete scientific output tree is not clone-contained.
The ToxCast curation note separately documents that raw invitrodb regeneration is an external and currently non-executable dependency, while the derived annotation inputs are pinned locally.

The paper names GitHub repository `jessica-ewald/2024_09_09_Axiom_OASIS` and code DOI `10.5281/zenodo.18242918`.
The current checkout's `origin` is `broadinstitute/2024_09_09_Axiom_OASIS`, and repository content alone cannot prove that it is identical to the published owner URL or resolve the DOI.
The code DOI appears in the paper sources but not in the top-level README, while README and `4A_download_compiled_inputs.py` separately identify data record 17067683.
The code itself, download recipes, workflow, notebooks, and reproduction guide are tracked locally.

Decision: `reproduced-with-deviation`.
All published access classes and path references are traceable, but raw images, compiled profile inputs, the complete output tree, raw invitrodb, DOI resolution, and published-repository identity require external state or data.

## INTERPRETATION-001

This target is a trace audit of the already recorded `ENRICH-003` and `ENRICH-004` evidence.
It does not introduce a new enrichment calculation or biological experiment.

For the 261 historical higher-predicted MT wells, the committed enrichment artifact has 147 target sets at FDR below 0.05.
All six paper-named CYP sets and all four named xenobiotic transporter sets are significant.
Six serotonergic receptor sets are significant, but no dopaminergic or adrenergic receptor set is significant and two of nine named compounds are absent from significant overlaps.
This directly supports CYP, transporter, and serotonergic-receptor association, with narrower support than the paper's general neurotransmitter-receptor wording.

For the 131 historical lower-predicted MT wells, 107 target sets are significant.
Eighteen proteasome-related sets and three CYP sets directly support proteasome and xenobiotic-metabolism association.
The repository has no pathway or process mapping that turns target keys into direct evidence for bile-acid synthesis, general cell stress, or apoptosis, and carfilzomib is absent from the historical overlap artifact.

Both enrichment layers are one-sided overrepresentation tests over exposure-well target annotations.
The target annotations are general and non-directional, and the recorded implementation also has an unenforced universe-intersection deviation.
Neither association establishes that CYP induction, altered glycolysis, reactive oxygen species, proteasome inhibition, stress, apoptosis, or another process caused an MT prediction discrepancy.
The camera-ready discussion itself marks metabolic reprogramming, CYP effects, glycolysis, reactive oxygen species, and uncoupling as hypotheses and says that follow-up work is needed.

Decision: `reproduced-with-deviation`.
The trace supports the principal CYP, serotonergic, transporter, proteasome, and xenobiotic-metabolism associations, while several process and receptor-class labels remain paper interpretation and all mechanistic or causal language remains explicitly hypothetical.
