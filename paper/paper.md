---
title: Cell Painting for cytotoxicity and mode-of-action analysis in primary human hepatocytes
doi: 10.1016/j.cels.2026.101566
canonical_source: sources/main.pdf
structural_source: sources/manuscript-source.docx
---

# Searchable paper transcription

This Markdown file is a searchable structural transcription of the paper.
It was generated from the final author manuscript because that source preserves headings, tables, and references more reliably than the two-column PDF text layer.
The camera-ready PDF at `sources/main.pdf` is authoritative whenever wording, values, captions, pagination, or formatting differ.
Publication-stage differences are expected and should be recorded as deviations rather than silently corrected here.
Inline reference numbers below come from the author manuscript and can differ from the final publisher numbering.

<!-- source-page: cover -->

## In brief

Ewald et al. use machine learning to predict chemical cytotoxicity and mode of action from images of cells exposed to 1,085 compounds.
With sufficient training data, imaging reveals subtle cellular events, highlighting its potential to improve chemical safety assessment by detecting cellular changes linked to adverse health outcomes.

## Highlights

- Cell Painting reveals rich compound-induced bioactivity, including cytotoxicity.
- Image-based profiles are more sensitive and capture more signals than cell counts alone.
- Profiles predict activity in diverse cell-based assays, revealing the mode of action.
- Deep learning and traditional computer vision feature extraction performed similarly.

<!-- source-page: 1 -->

## Article title

Cell Painting for cytotoxicity and mode-of-action analysis in primary human hepatocytes

Jessica D. Ewald<sup>a,b</sup>\*, Katherine L. Titterton<sup>c</sup>, Alex Bauerle<sup>c</sup>, Alex Beatson<sup>c</sup>, Daniil A. Boiko<sup>c</sup>, Angel A. Cabrera<sup>c</sup>, Jaime Cheah<sup>d</sup>, Beth A. Cimini<sup>a</sup>, Bram L. Gorissen<sup>e</sup>, Joshua Harrill<sup>f</sup>, Thouis R. Jones<sup>e</sup>, Konrad J. Karczewski<sup>e</sup>, Christine E. Crute<sup>g</sup>, David Rouquie<sup>h</sup>, Srijit Seal<sup>a</sup>, Erin Weisbart<sup>a</sup>, Brandon White<sup>c</sup>, Anne E. Carpenter<sup>a</sup>, Shantanu Singh<sup>a</sup>

a - Imaging Platform, Broad Institute of MIT and Harvard, Cambridge, MA, USA

b - European Bioinformatics Institute, European Molecular Biology Laboratory, Hinxton, UK

c - Axiom Bio, San Francisco, CA, USA

d - The Center for the Development of Therapeutics, Broad Institute of MIT and Harvard, Cambridge, MA, USA

e - The Novo Nordisk Foundation Center for Genomic Mechanisms of Disease, Broad Institute of MIT and Harvard, Cambridge, MA, USA

f - Center for Computational Toxicology and Exposure, Office of Research and Development, United States Environmental Protection Agency, Research Triangle Park, NC, USA

g - Health and Environmental Sciences Institute, Washington DC, USA

h - Toxicology Data Science, Bayer SAS Crop Science Division, Valbonne Sophia-Antipolis, France

\*Corresponding author

*Lead Contact*: Further information and requests for resources and reagents should be directed to and will be fulfilled by the Lead Contact, Jessica Ewald ([<u>jewald@ebi.ac.uk</u>](mailto:jewald@ebi.ac.uk)).

Summary

Scalable, human-relevant approaches for detecting compound mode of action are needed to improve chemical safety evaluation.
Here, we apply image-based profiling (Cell Painting) alongside two cytotoxicity assays in primary human hepatocytes exposed to eight concentrations of 1,085 compounds spanning pharmaceuticals, pesticides, and industrial chemicals.
We compared three computational approaches (CellProfiler, a Cell Painting-specific convolutional neural network, and a pretrained vision transformer) to extract morphological features from single cells or whole images.
These features were used to predict activity in the measured cytotoxicity assays and in ToxCast assays covering cytotoxicity, cell-based, and cell-free endpoints.
Morphological profiles detected bioactivity at lower concentrations than standard cytotoxicity assays and provided mode-of-action insights.
In supervised analyses, they predicted cytotoxicity and targeted cell-based assays, but not cell-free assays.
Feature extraction methods performed similarly, and filtering concentrations did not improve performance.
We envision that image-based profiling could be a key component of modern safety assessment.

Keywords

Image-based profiling \| cytotoxicity \| mode-of-action \| high-throughput screening \| primary human hepatocytes \| computational toxicology \| feature extraction \| supervised machine learning

# Introduction

Scalable approaches for detecting potential *in vivo* toxicity of compounds in humans are urgently needed for better decision-making in human health.
The majority of the \>350,000 compounds registered for commercial use worldwide have never been assessed for adverse impacts on human health [<sup>1</sup>](https://paperpile.com/c/2xFVvw/3P7iR).
Even for pharmaceuticals, which undergo extensive preclinical testing, many fail clinical trials due to toxicities not predicted by animal models, draining resources and increasing drug development costs [<sup>2</sup>](https://paperpile.com/c/2xFVvw/il16T).
Animal-based testing is resource-intensive, raises ethical concerns, and often fails to accurately predict specific adverse health outcomes in humans, making them insufficient for addressing these data gaps.
Thus, scientists in government, industry, and academia are working to bring about a new paradigm in which a suite of human-relevant *in silico* and *in vitro* models are used to understand and predict the *in vivo* impacts of chemical exposures at scale [<sup>3,4</sup>](https://paperpile.com/c/2xFVvw/6K9bT+KgGPB).
Developing such scalable methods would transform chemical safety evaluation by enabling more efficient prioritization of environmental and commercial compounds, while also improving early decision-making in drug development.

*In vitro* cellular models can point towards *in vivo* toxicity when compound-induced changes in cells are known to drive adverse outcomes at real-world exposure concentrations.
In cases where the link is direct, such as between certain cellular phenotypes and classical toxicity endpoints, *in vitro* assays have already been developed, for example, tests for skin sensitization [<sup>5</sup>](https://paperpile.com/c/2xFVvw/Hjzf8) or genotoxicity [<sup>6</sup>](https://paperpile.com/c/2xFVvw/QjS9X).
To extend this approach to more complex scenarios and to uncover novel links, researchers are defining causal relationships between compound-induced perturbations and key impacts across biological scales, from macromolecules to cells to tissues to organisms, also called "adverse outcome pathways" [<sup>7,8</sup>](https://paperpile.com/c/2xFVvw/vA7Qb+7KVVh).
If there is high confidence in how a compound-induced phenotype at the cellular level causes toxicity at the organism level, then observing this phenotype *in vitro* at concentrations relevant to human exposures should be a solid basis for screening for chemical toxicity at scale.
Linking cellular phenotypes to specific *in vivo* effects is particularly important for industries that create compounds that are supposed to interact with human biology, for example new therapeutics or food ingredients.
Achieving this vision requires high-throughput methods that can identify specific compound modes-of-action across a range of concentrations.

Targeted *in vitro* assays can identify specific modes-of-action by measuring individual molecular targets and cellular pathways.
However it is logistically difficult to run enough assays in parallel to comprehensively cover the large variety of molecular targets that are present in human tissues.
The ToxCast program is a nearly 20-year effort that screened ~1,500 targeted assay endpoints and approximately 10,000 diverse compounds [<sup>9-11</sup>](https://paperpile.com/c/2xFVvw/yQROZ+M8sMB+XtCtu); it is an extremely valuable source of interpretable cellular mode-of-action information resulting in applications across human and environmental health. [<sup>10,12</sup>](https://paperpile.com/c/2xFVvw/M8sMB+yvOvE)
Recent approaches in toxicology try to capture this information and more with fewer assays by collecting high-throughput, high-dimensional data that covers broad swathes of biological space in a single assay [<sup>4,13-15</sup>](https://paperpile.com/c/2xFVvw/KgGPB+kUchq+rlEuk+KRdtK).
The Cell Painting assay is a promising approach for acquiring this type of data from cells that might be predictive of specific toxicity-related outcomes [<sup>16</sup>](https://paperpile.com/c/2xFVvw/nG35j).
It is an image-based profiling assay using six fluorescent dyes to label eight different cell components, and it measures thousands of features, including intensity, shape, and texture of the various stains in various regions of the cell [<sup>17</sup>](https://paperpile.com/c/2xFVvw/N3alo).
The underlying principle is that different biological perturbations create distinct morphological signatures detectable through imaging.
Cell Painting captures these signatures and can potentially reveal mode-of-action information at the single-cell level while being at least 1000 times cheaper than other single-cell omics such as transcriptomics and proteomics, and at least 15 times cheaper than bulk -omics methods.

Prior work on inferring mode-of-action from Cell Painting and transcriptomics data in high-throughput, concentration-response toxicity screens has primarily relied on unsupervised approaches, where profiles from compounds with unknown modes-of-action are compared to groups of compounds with high-confidence mechanistic annotations [<sup>13,18-20</sup>](https://paperpile.com/c/2xFVvw/skeIa+sb19j+kUchq+yFw7E).
While these approaches have proven successful in many cases, they face limitations when compounds either perturb cells in multiple ways or trigger common compensatory responses, as subtler specific impacts can be masked by stronger generalized phenotypes.
Supervised machine learning is an intuitive approach to disentangle specific mode-of-action and cell state signals from high-content data, and has successfully predicted toxicity-related outcomes from Cell Painting and transcriptomics data in single-concentration *in vitro* screens [<sup>21-24</sup>](https://paperpile.com/c/2xFVvw/oGg2H+BpV5M+acrNa+UKAzb).

In this paper, we used supervised machine learning to predict diverse *in vitro* assay readouts relevant to mode-of-action and cell state using Cell Painting in primary human hepatocytes exposed to eight concentrations of 1,085 compounds.
We selected hepatocytes because the liver is a primary site of xenobiotic metabolism and liver toxicity is one of the most common causes of compound attrition across pharmaceuticals, agrochemicals, and industrial chemicals [<sup>25,26</sup>](https://paperpile.com/c/2xFVvw/ShH7M+Ygh3A).
These readouts include curated ToxCast assay activities that represent diverse modes-of-action, as well as biochemical cytotoxicity assays measured alongside the Cell Painting data.
We also evaluated strategies for making mode-of-action predictions from image-based profiles, including different ways to incorporate concentration and comparing traditional versus deep learning methods for extracting morphological features from images.
This work contributes to the long-term goal of linking specific *in vitro* cellular responses with specific *in vivo* toxicological outcomes.
By advancing these connections, we move closer to realizing a new paradigm in toxicology where high-content *in vitro* assays can provide mechanistic explanations of human toxicity at scale to support safer and more efficient decision-making across many different chemical industries.

<!-- source-page: 2 -->

# Results

## 1. Experimental design and data overview

To generate a comprehensive dataset for evaluating cytotoxicity and cellular mode-of-action prediction, we profiled a diverse set of compounds in primary human hepatocytes using a combination of biochemical assays, high-content Cell Painting imaging, and curated ToxCast assay data.
Future work by the OASIS (Omics for Assessing Signatures for Integrated Safety) Consortium will link these data to *in vivo* liver toxicity observed in rats and in humans, hence the choice of a liver-relevant cell model.
We tested 1,085 compounds at eight concentrations ranging from 0.01 to 100 uM, with two biological replicates each, in primary human hepatocytes (Figure 1, Supplementary Figure 1).
The compounds were a subset of compounds from a list of 1,495 compiled by the OASIS Consortium based on the public availability of *in vivo* hepatotoxicity data (Supplementary Table 1).
The tested compounds include pharmaceuticals, agrochemicals, food additives, and known environmental contaminants.

Hepatocytes were arrayed into 384-well plates and exposed to compounds for 44 hours before carrying out three assays.
First, we took the supernatants from each well and measured lactate dehydrogenase (LDH), an enzyme that is released during cell membrane damage [<sup>27</sup>](https://paperpile.com/c/2xFVvw/YamBn), and metabolic activity using the Realtime-Glo assay (Promega).
Similar to the widely-used 3-(4,5-dimethylthiazol-2-yl)-2,5-diphenyltetrazolium bromide (MTT) assay which measures mitochondrial activity [<sup>28</sup>](https://paperpile.com/c/2xFVvw/xulhF), Realtime-Glo measures substrate reduction by metabolically active cells, though it uses a luminescent rather than colorimetric readout.
From here on, we refer to the Realtime-Glo assay as MT.

Next, we applied Cell Painting dyes to stain the cellular DNA, RNA, mitochondria, actin, Golgi, and endoplasmic reticulum, and imaged each well at 40x magnification in five fluorescent channels.
We created morphological profiles using three different computational methods, including CellProfiler software (yields 5,640 single-cell level, named features for each combination of channel and cell compartment) [<sup>29</sup>](https://paperpile.com/c/2xFVvw/Xq4Xw), Cell Painting convolutional neural network (CP-CNN, pretrained on several large Cell Painting datasets, yields 672 single-cell level, numbered features that are not directly interpretable nor mapped to channels) [<sup>30</sup>](https://paperpile.com/c/2xFVvw/e3bSu), and Meta's "distillation with no labels" v2 vision transformer (DINO, pretrained on 142 million curated natural images, yields 4,608 image-level, numbered features with channel labels) [<sup>31</sup>](https://paperpile.com/c/2xFVvw/L2SVY).
In addition to morphological features, we also counted the number of nuclei within each well using the Cell Painting images.
We analyzed this cell count as a third cytotoxicity-related metric, alongside LDH and MT.
While all three measurements - LDH, MT, and cell counts - reflect different biological aspects of cell state and toxicity, we collectively refer to them as "cytotoxicity-related" metrics for convenience.

Finally, we extracted relevant ToxCast assay results from *invitrodb [<sup>12</sup>](https://paperpile.com/c/2xFVvw/yvOvE)*.
The ToxCast program screened ~1,500 targeted assay endpoints and approximately 10,000 diverse compounds [<sup>10,11</sup>](https://paperpile.com/c/2xFVvw/M8sMB+XtCtu), an extremely valuable source of compound mode-of-action information that overlaps with nearly 90% of our tested compounds.
ToxCast assay activities were used to train models to predict compound cytotoxicity and mode-of-action based on Cell Painting profiles.

## 2. Morphological profiles detect cytotoxicity and more sensitive bioactivity signals

Our goal is to detect detailed compound modes-of-action from morphological profiles, a challenging task.
As a starting point, we focused on predicting cytotoxicity-related endpoints measured in parallel biochemical assays, avoiding complications from external datasets with differing designs.
We then compared these signals with concentration-dependent bioactivity in Cell Painting profiles to assess whether the assay captures mode-of-action information beyond overt cytotoxicity.

### 2.1 Concentration-dependent activity of compounds across different assay readouts

<!-- source-page: 3 -->

#### 2.1.1 40% of compounds induce activity as measured by LDH, MT, and cell counts

We analyzed the cytotoxicity-related endpoints to determine which compounds induced significant activity relative to DMSO negative controls.
We also used concentration-response analysis to estimate the lowest concentration with detected activity for each active compound, herein referred to as the point-of-departure (POD), and whether the detected activity was more, or less, cytotoxic compared to DMSO.
We detected activity for 430 of the 1,085 compounds (40%) in the MT assay, 221 (20%) in the cell count assay, and 144 (13%) in the LDH assay for a total of 438 unique compounds (Supplementary Table 2).
Overall, 429 compounds (40%) induced cytotoxicity as measured by one or more assays at one or more concentrations - the discrepancy between the 438 compounds with assay activity is because sometimes the directionality compared to DMSO does not indicate cytotoxicity, for example an increase in cell count would count towards the 438 active compounds but not the 429 cytotoxic compounds.
Most compounds active in the MT assay caused decreases in activity that were indicative of cytotoxicity, however ten compounds (1%) caused an increase in MT assay readouts relative to the DMSO controls.
Four of these compounds had particularly strong responses (Figure 2A).

<!-- source-page: 3-5 -->

#### 2.1.2 Morphological profiling detects bioactivity for up to 60% of compounds

To analyze the Cell Painting data, we wanted to detect whether *any* impacts to morphology were observed for each compound, hereafter referred to as general bioactivity.
To accomplish this, we summarized the image profiles using a Mahalanobis distance (MD)-based approach, as described previously [<sup>32</sup>](https://paperpile.com/c/2xFVvw/Ux9D4).
We computed the MD of each profile relative to the DMSO vehicle controls using all features (global MD) and using subsets of features (categorical MDs) corresponding to specific channels and/or cell compartments.
Each of these distances is a measure of bioactivity, with larger values indicating that a profile has greater compound-induced perturbation of cell morphology.
Next, we used concentration-response analysis as described for the cytotoxicity-related assays to determine PODs for each MD.
We defined the general bioactivity PODs as the lowest POD among all of the statistically significant MD PODs for each compound.

Overall, morphological profiling and concentration-response analysis detected bioactivity for 34-59% of compounds, depending on the cell representation (CellProfiler, CP-CNN, and DINO) and distance metric used (global vs categorical) (Figure 2B, Supplementary Table 3).
The two deep learning-based methods (CP-CNN and DINO) detected ~50-60% compounds as active, as did CellProfiler in the categorical MD case.
The one outlier, at 34% active compounds, was CellProfiler using the global metric.
Comparing the alternate approaches for extracting image features, CP-CNN general bioactivity PODs were, on average, 2.0-fold higher (less sensitive) than CellProfiler and 1.5-fold higher than DINO general bioactivity PODs (Figure 2B and 2C).
There was no significant difference between CellProfiler and DINO general bioactivity PODs (paired t-test).

<!-- source-page: 5 -->

#### 2.1.3 Morphological profiles are more sensitive than cytotoxicity readouts

The morphological profiles from Cell Painting detected activity at lower concentrations than the three cytotoxicity-related readouts.
There was a clear ranking of assay sensitivity, by both the number of active compounds and the relative POD, with morphology \> MT \> cell counts \> LDH.
The 121 compounds (12%) with PODs for all four assays qualitatively appear to be mainly conventionally toxic compounds (Supplementary Table 4) .
Among these 121 compounds, morphology PODs were 1.8-fold lower than MT, 3.9-fold lower than cell counts, and 7.0-fold lower than LDH (Figure 2D, all p-values \< 1.0 e-14).

The assays' differences in sensitivity are consistent with assay biology.
LDH, an enzyme released during membrane damage, is more representative of the subset of cell death pathways that cause catastrophic membrane rupture, for example necrosis, and represents a relatively late stage of cell death.
Cell count represents the balance between all forms of cell proliferation and cell death, so we expect it to be active for more compounds and at lower concentrations than LDH.
The MT assay measures metabolic competence, which we expect to be perturbed at lower concentrations than those that cause outright cell death.
Finally, Cell Painting captures subtle morphological changes across a wide biological space far beyond cell death alone, having been shown to detect a wide range of chemical and genetic perturbation modes-of-action [<sup>24,33</sup>](https://paperpile.com/c/2xFVvw/KVNuY+UKAzb).

### 2.2 Morphological profiles predict cytotoxicity assay readouts

The MT and LDH assays measure different aspects of cytotoxicity; since Cell Painting is more sensitive than these assays (Figure 2D) and has been previously shown to contain detailed mode-of-action signals [<sup>16,34</sup>](https://paperpile.com/c/2xFVvw/nG35j+kqvqd), we hypothesized that it captured these nuances more effectively than simple cell counts.

<!-- source-page: 5 -->

#### 2.2.1 Regression models predict paired cytotoxicity readouts

To test this, we first trained XGBRegressor models to predict MT and LDH assay readouts from individual wells based on their paired Cell Painting profiles (CellProfiler, CP-CNN, and DINO representations).
Because the measurements are paired (readouts are recorded from the same well), we expect assay readouts to be partially confounded by plate and well position, which are known to influence cell proliferation.
To account for this, we compared the performance of the Cell Painting-based models to a technical baseline model trained using cell count, well position, and plate features.

First, there were no significant differences in performance across representations (Table 1), thus we refer to morphology-based predictions from all representations hereafter as the "Cell Painting" predictions.
We found that Cell Painting outperformed the technical baseline, which includes cell count, plate, and well position features, for the MT assay but not for the LDH assay (Table 1).
To some degree, the cell count captures the same types of cytotoxicity captured by the LDH assay.
As well, there is also a strong influence of technical plate and well position factors on the LDH readouts (Supplementary Figure 2A-C), which resulted in high variability between technical replicates.
In fact, the R<sup>2</sup> between observed LDH readouts and predictions based on either Cell Painting or the technical baseline models were significantly higher than the R<sup>2</sup> between technical replicates of the same compound and concentration (mean difference = 0.20, p-value \< 1.0 e-14).
The MT readouts were less influenced by well position, showed much better concordance across replicates, and were better predicted by Cell Painting than by the technical baseline.

<!-- source-page: 6 -->

#### 2.2.2 Classification models predict overall compound cytotoxicity

We converted the cytotoxicity endpoints into binary hit calls ("active" or "inactive", see methods for more details) for each compound-endpoint pair.
Cell Painting features were median-aggregated across all concentrations to generate consensus profiles for each compound.
Using these profiles, we trained XGBoost classifiers to predict compound cytotoxicity.
Model performance was evaluated with AUROC (Area Under the Receiver Operating Characteristic curve), which reflects overall discriminative ability, and PRAUC (Area Under the Precision-Recall curve), which emphasizes performance on the typically smaller active class [<sup>35</sup>](https://paperpile.com/c/2xFVvw/Id6zF).
Classification performance was benchmarked against models using cell count features and against a random baseline.

Cell Painting predictions were highly accurate, particularly for LDH, with mean AUROC of 0.93 and PRAUC of 0.75 (Table 2).
Performance was consistent across feature representations.
Unlike in the regression setting, Cell Painting predictions here outperformed all baselines.
Note that baseline definitions differed slightly due to preprocessing, which collapsed replicate wells into compound-level consensus profiles and removed plate and well annotations.
Because cytotoxicity was defined from the full dose-response relationship, MT and LDH readouts in this analysis are less likely to be confounded by well-position or plate effects.

<!-- source-page: 6-7 -->

### 2.3 Target enrichment analysis reveals biologically meaningful differences between morphology and cytotoxicity-related assays

Throughout this project, various statistical analyses revealed sample sets of interest, for example clusters of similar image-based profiles or groups of compounds with particularly poor assay prediction performance.
We wanted to generate hypotheses of perturbed cellular processes that could explain these statistical patterns in our data.
To do this, we leveraged publicly available information on the proteins that our compounds are known to target.
We compiled these annotations into a "target set library", and used overrepresentation analysis to assess protein target enrichment within sample sets of interest.

For example, we wanted to know which additional biological signals were captured by Cell Painting compared to the technical and cell count baseline for the MT predictions.
Target set enrichment revealed that individual wells whose MT values were better predicted by Cell Painting (*n* = 138, 1.0%) than by the technical baseline were exposed to compounds that were significantly enriched in 480 molecular targets, many of which are in the cell cycle (29/97 targets, FDR = 1.46e-12), PI3K-Akt signaling (53/256 targets, FDR \< 1.0 e-14), MAPK signaling (47/249, FDR = 1.90e-12), and p53 signaling (21/64 targets, FDR = 3.43e-10) KEGG pathways.
Individual wells that were better predicted by Cell Painting tended to have lower normalized MT values compared to all samples (Supplementary Figure 2D).
The cell counts were also lower, although most were in a normal range between 500 and 1000 (Supplementary Figure 2E).
We wanted to know whether the samples better predicted by Cell Painting had one or multiple distinct phenotypes, however clustering of morphological profiles based on pairwise cosine similarity between samples was mainly dominated by differences in cell count (Supplementary Figure 2F), highlighting the difficulties of using unsupervised approaches to analyze toxic exposures.
Because Cell Painting encodes cell counts and technical effects in addition to biological signals [<sup>36</sup>](https://paperpile.com/c/2xFVvw/gLTfl), we expected that the samples with MT readouts better predicted by the technical baseline compared to Cell Painting would be random and have no meaningful biological signals.
There were in fact no significantly enriched targets in this list of samples (*n* = 304, 2.3%), increasing confidence in our analysis.

Like any regression problem, our analysis revealed cases where predicted values deviated from observed measurements.
We leveraged these prediction discrepancies to investigate the biological mechanisms underlying the relationship between cellular morphology and metabolic activity.
Specifically, we found that a small number of wells had MT readouts that were poorly predicted by both their morphological profiles and technical features like cell count, suggesting fundamental disconnects between cellular appearance and metabolic activity.
We analyzed the samples with significantly higher morphology-predicted MT readouts than observed (*n* = 261, 2.0%) to investigate whether there were any particular modes-of-action underlying this phenomenon, and found that they were enriched in compounds targeting 147 proteins (FDR \< 0.05).
These targets included many cytochrome P450 enzymes, for example CYP3A5, CYP3A43, CYP2B6, CYP3A7, CYP2C8, and CYP3A4.
They also included many compounds that targeted G-protein coupled dopaminergic, serotonergic, and adrenergic receptors (amoxapine, apomorphine, aripiprazole, cisapride, clomipramine, domperidone, paliperidone, risperidone, and tamsulosin), and compounds that targeted xenobiotic transporters including efflux (ABCB1 and ABCG2) and uptake (SLCO1B1 and SLCO1B3) transporters.
Similarly, analyzing the underpredicted cases (n = 131, 1.0%) revealed enrichment for compounds targeting distinct biological processes, including proteasome inhibition (specifically through bortezomib, carfilzomib, and ixazomib exposures), xenobiotic metabolism, bile acid synthesis, general cell stress, and apoptosis.
Some of the prediction errors might be explained by assay interference by the administered compounds.
For example, redox-active compounds can directly reduce the MT substrate and some compounds have a similar absorbance spectrum to the reduced substrate [<sup>37,38</sup>](https://paperpile.com/c/2xFVvw/chDf7+FpRy1), leading to higher MT assay readouts than supported by the actual level of mitochondrial activity.

<!-- source-page: 7 -->

## 3. Morphological profiles contain detailed compound mode-of-action signals

Our next goal was to evaluate whether Cell Painting profiles can capture a wider range of toxicity-related activities that provide insight into compound mode-of-action.
To this end, we leveraged the ToxCast program, which provides a large collection of targeted biochemical and cell-based assays for many of our compounds (963, or 89% of those tested).
These assays span cytotoxicity, cell-based molecular and pathway activities, and cell-free biochemical functions, offering a rich benchmark to test how well morphological profiles generalize across diverse macromolecular and cellular endpoints.
By comparing predictive performance across these categories, and across different feature extraction strategies and concentration filtering schemes, we aimed to clarify the strengths and limitations of Cell Painting as a platform for mechanistic toxicity prediction.

### 3.1 Preparing ToxCast assay endpoints

We selected 48 cytotoxicity endpoints, 292 non-cytotoxicity cell-based endpoints, and 72 cell-free endpoints.
Cytotoxicity endpoints were measured alongside many of the more specific ToxCast endpoints, resulting in many repeated cytotoxicity readouts for the same compound and often the same cell type.
We therefore curated cytotoxicity endpoints to be consensus hit calls of cytotoxicity readouts aggregated across 28 cell types and 20 tissue sources resulting in 48 (consensus-level) readouts (Supplementary Figure 3A).
While the cytotoxicity hit calls broadly agree across different cell and tissue types, there are distinct clusters of compounds with cytotoxicity in some cell (Supplementary Figure 3B) and tissue (Supplementary Figure 3C) types but not others.

Most of the cell-based endpoints were measured in cell types derived from liver (52%), vascular tissues (22%), and kidney (12%).
They fall into six different categories, with 84% assessing the activity of individual molecules, such as mRNA transcript levels or activation/inhibition of specific receptors, and the remainder assessing perturbations at the pathway, subcellular, or cellular levels.
The individual mRNA and protein targets come from 36 distinct protein families, with the three most common being nuclear receptors (19%), DNA binding proteins (18%), and cytokines (11%).
The cell-free endpoints assess two main functional categories: protein binding (51%) and enzymatic activity (49%).
The cell-free targets come from 11 protein families, with the three most common being GPCRs (29%), CYP450s (15%), and nuclear receptors (14%).
Overall, the median number of ToxCast compounds that overlapped with our tested compounds was 346 for cytotoxicity endpoints, 306 for cell-based endpoints, and 33 for cell-free endpoints, and the median percentage of active compounds was 21% for cytotoxicity, 7% for cell-based, and 41% for cell-free.
Many of the positive hits in the cell-free assays were for the enzymatic activity of various cytochrome P450s, which are expected to interact with many xenobiotic compounds.

<!-- source-page: 7-9 -->

### 3.2 Cell Painting profiles predict activity in ToxCast assays

Cell Painting profiles predict compound activity in ToxCast cytotoxicity and cell-based assays, but not cell-free assays, compared to a random baseline where we shuffled labels prior to training classifiers (Figure 3).
We determined this by converting ToxCast data into binary hit calls of "active" or "inactive" for each compound-endpoint pair, using the same methodology as for the MT and LDH assays.
Cell Painting profiles performed best at predicting cytotoxicity assays, including the MT and LDH assays; this is not surprising given that the image profiles include cell count in addition to morphological changes associated with cell stress and death.
Cytotoxicity prediction performance was lower for the external ToxCast assays compared to the MT and LDH assays that were run in parallel with Cell Painting, likely due to differences in the ToxCast experimental design such as cell type and exposure time.
Cell-based assays were next-most predictable, with cell-free assays being least, in line with Cell Painting being itself a cell-based assay.
Assay activity prediction based on cell count alone outperforms the random baseline for cytotoxicity but not cell-based or cell-free assays (Figure 3).

<!-- source-page: 9 -->

#### 3.2.1 Filtering out non-bioactive and cytotoxic compound concentrations did not improve mode-of-action prediction

We hypothesized that filtering out Cell Painting profiles from non-bioactive concentrations would be more predictive of assay activity than including them.
To test this, we created a second set of consensus profiles for each compound using only profiles from concentrations greater than the general bioactivity POD, and used these to predict assay activity (Figure 4A).
There was only a small improvement in the AUROC scores for the bioactive-concentration versus all-concentration consensus profiles for the ToxCast cytotoxicity (mean difference = 0.04, FDR \< 1.0 e-14) and ToxCast cell-based (mean difference = 0.02, FDR = 0.002) assays.
There were no significant differences in AUROC for the other assays, nor for the PRAUC scores for any assays (Supplementary Figure 4A).
We next hypothesized that additionally filtering out exposures that induced cytotoxicity would improve predictive performance for the targeted cell-based and cell-free assays because this would remove non-specific signals associated with general cell stress and death pathways, though this might be offset by the reduction in useful data points.
To test this, we created a third set of consensus profiles using only concentrations greater than the morphological POD and lower than the cell count POD.
As expected, filtering out the cytotoxic profiles resulted in significantly worse performance for both of the cytotoxicity assay categories (FDR \< 1.0 e-14 for both AUROC and PRAUC).
Contrary to our prediction, there were no significant differences in performance for the bioactive-but-not-cytotoxic consensus profiles compared to the bioactive profiles for the cell-based and cell-free assays.

#### 3.2.2 Alternative cell representations perform similarly

Although there is great enthusiasm for using deep learning strategies to extract features from raw pixels in images, the predictive performance was very similar across the different cell representations we tested.
DINO had slightly higher median AUROC scores for the cell-based ToxCast assays (mean diff = 0.02 for both comparisons, p-value = 2.7e-5 and 7.4e-6 for CellProfiler and CP-CNN respectively); otherwise there were no significant differences in performance according to AUROC or PRAUC scores (Figure 4B, Supplementary Figure 4B).

<!-- source-page: 9-10 -->

# Discussion

Overall, we found that morphological profiles from Cell Painting in human hepatocytes detected activity at lower concentrations, and for more compounds, than the multiple cytotoxicity assays that we measured for the same compounds.
The morphological profiles also have some ability to predict many mode-of-action and toxicity-related assay endpoints in cell-based assays, but not cell-free assays of protein binding and enzymatic activity.
These findings demonstrate the potential of morphological profiling as a sensitive, information-rich tool for assessing compound mode-of-action at scale as part of toxicity evaluations.

We used public compound-target annotations and target set enrichment analysis to search for biological explanations for patterns in our imaging data.
This approach is promising in that it did yield statistically significant protein target enrichment results in several cases.
For example, we explored samples that were predicted (based on their morphological profiles) to have higher mitochondrial activity than actually observed in the MT assay.
These "overpredicted" samples were enriched in compounds targeting xenobiotic metabolism enzymes (cytochrome P450 enzymes - CYPs) and neurotransmitter receptors, which regulate hepatic CYP expression and metabolism [<sup>39-41</sup>](https://paperpile.com/c/2xFVvw/0tIPR+rcLWn+2dqLc).
We hypothesize that general metabolic reprogramming and CYP induction might decrease MT values - perhaps by shifting metabolism from oxidative phosphorylation to other pathways such as glycolysis that do not require mitochondrial activity [<sup>42</sup>](https://paperpile.com/c/2xFVvw/AIWIY) - without a dramatic change in cell morphology.
Mitochondrial activity could be further reduced if the metabolic perturbations increase the reactive oxygen species (ROS) burden within the cells (a known impact of CYP inhibition [<sup>43</sup>](https://paperpile.com/c/2xFVvw/XWkMS)), which can directly impair the dehydrogenase enzyme activity required for MT substrate reduction [<sup>44,45</sup>](https://paperpile.com/c/2xFVvw/QFkT4+WBeH0).
Nevertheless, because the available compound-target annotations are general and not directional, these results suggest testable hypotheses rather than definitive mechanisms.

Predicting targeted assay endpoints from Cell Painting profiles can in some cases offer greater interpretability than interpreting specific morphological features themselves.
Predictions from Cell Painting are also more practical than running hundreds of individual assays.
Our results show that Cell Painting profiles capture rich mode-of-action signals and can discriminate subtle differences in cytotoxicity when sufficient high-quality training data are available.
However, predictive performance depended on how closely the targeted assays matched the Cell Painting experimental design.
For example, performance was markedly higher for the paired cytotoxicity assays conducted in parallel than for similar ToxCast cytotoxicity assays, which differed in concentration ranges, exposure durations, and cell types.
This performance gap suggests that future efforts to incorporate assay metadata in the analysis could further enhance predictive power.

Unexpectedly, consensus profiles aggregated across all concentrations generally performed as well as, or better than, those filtered by bioactivity or cytotoxicity thresholds.
One likely explanation is that averaging over more profiles reduces plate- and well-level variability, and this benefit outweighs any signal loss from including inactive concentrations.
Alternatively, morphology-based bioactivity PODs defined by Mahalanobis distances may overestimate bioactivity PODs, causing the loss of informative profiles when used as filters.
This hypothesis is consistent with previous work showing that Cell Painting Mahalanobis-based activity was detected at higher concentrations than activity observed in targeted ToxCast assays [<sup>46</sup>](https://paperpile.com/c/2xFVvw/05XcE).
These findings suggest that our assay prediction benchmark (Figure 4A) could guide the development and evaluation of improved approaches for computing bioactivity PODs from high-dimensional omics data, an open challenge in toxicogenomics [<sup>47-49</sup>](https://paperpile.com/c/2xFVvw/Qmdr4+1BzuC+31q8t).
Until more sensitive methods are available, aggregating all concentrations into a consensus profile appears to be a simple and robust strategy for supervised prediction.

Beyond biological findings, our results also speak to practical considerations in feature extraction.
In this analysis, state-of-the-art deep learning features had very similar predictive performance to traditional engineered image features from CellProfiler.
While not unprecedented, this is a highly active area of machine learning research and new methods could show improved performance [<sup>50,51</sup>](https://paperpile.com/c/2xFVvw/4cg5D+FTTuD).
We envision that our analysis could be used to benchmark novel methods for learning representation of cellular images.
[<sup>50,51</sup>](https://paperpile.com/c/2xFVvw/4cg5D+FTTuD).
Beyond predictive performance, the different cell representations we tested had relative strengths and limitations in their practical implementation.
DINO was the easiest end-to-end solution because it was used off-the-shelf and did not require any cell or nucleus segmentation; however this also means that it did not produce profiles at the single-cell level, which might be desirable for some applications [<sup>52,53</sup>](https://paperpile.com/c/2xFVvw/9l7S7+sEdqd).
CP-CNN was also relatively hands-free, with only a single tunable parameter (Cellpose 2.0 nuclei size).
CellProfiler, by comparison, requires tuning in two hands-on steps (nuclear and cell segmentation) each with dozens of potentially tunable parameters, though pipelines, once expertly tuned, can often be reused on similar data with little to no further tuning.
However, the standard CellProfiler processing pipeline yields readily interpretable features and includes standardized QA/QC metrics such as blur, intensity, and saturation metrics, which have proved invaluable in our past experience.
We highly recommend that similar quality checks be developed for deep learning cell representation pipelines.

Although unrelated to morphology profiles, our analysis of the MT assay revealed that a small number of compounds increased rather than decreased mitochondrial activity.
Three of the four strongest MT-increasing compounds (tolcapone, benzarone, tiratricol) are pharmaceuticals with off-target impacts on the liver that have been mechanistically linked to the uncoupling of oxidative phosphorylation [<sup>54-57</sup>](https://paperpile.com/c/2xFVvw/J0h9i+2QusE+ZtvBG+MfN8W), likely leading to compensatory increases in the rate of oxidative phosphorylation and higher MT readouts.
The fourth, 2-ethylanthraquinone, is an industrial chemical produced or imported to the United States at 50-500 tons per year (CompTox Chemicals Dashboard, v2.5.3, accessed April 25, 2025) [<sup>58</sup>](https://paperpile.com/c/2xFVvw/DumQ2).
Despite more than 100 publications in material sciences, little is known about its biological mode of action beyond limited ToxCast data [<sup>10,59,60</sup>](https://paperpile.com/c/2xFVvw/AVXwl+M8sMB+2qVy9).
In our study it showed the highest potency and maximal response of all MT-increasing compounds.
ToxCast results further indicate metabolic disruption, with activity detected in twelve nuclear receptor assays (e.g., RARA, NR1I2, ESR1, VDR, ESRRA, NR1I3, PGR, PPARG) at 1-45 uM in the absence of cytotoxicity (Supplementary Table 5), and decreased mitochondrial depolarization consistent with oxidative phosphorylation uncoupling [<sup>61</sup>](https://paperpile.com/c/2xFVvw/6d3PR).
Taken together, these findings suggest that 2-ethylanthraquinone may perturb hepatocyte metabolism through uncoupling of oxidative phosphorylation.
Given both the potency we observed and its widespread industrial use, follow-up studies to confirm its mode-of-action are recommended.

Future work could advance the utility of imaging and omics data in compound toxicity screening.
Publicly available training data (both from targeted assays and *in vivo* exposures) is precious and every effort should be made to document experimental design parameters, harmonize units and other nomenclature, and improve the translation between data sources via pharmacokinetic and chemical partitioning models [<sup>62,63</sup>](https://paperpile.com/c/2xFVvw/ZSohl+rg6pr).
Given the relative scarcity of well-annotated, targeted training data, comparisons are often made across datasets collected for different cell types, which may impact results and prevent accurate predictions.
Future work by the OASIS Consortium will collect Cell Painting data for additional cell types for a consistent set of compounds, enabling direct comparisons of how well cell types with diverse lineages predict the same targeted assays.
For a subset of compounds and cell types, it will also capture transcriptomics and proteomic data, enabling a comparison and combination of these data types with imaging, which may prove powerfully predictive.

<!-- source-page: 10 -->

# Resource Availability

*Lead Contact*: Further information and requests for resources and reagents should be directed to and will be fulfilled by the Lead Contact, Jessica Ewald ([<u>jewald@ebi.ac.uk</u>](mailto:jewald@ebi.ac.uk)).

*Materials Availability:* This study did not generate new materials.

*Data and Code Availability*

- Raw images have been deposited at [<u>https://broadinstitute.github.io/cellpainting-gallery</u>](https://broadinstitute.github.io/cellpainting-gallery) and are publicly available as of the date of publication.
  Accession numbers are listed in the key resources table.
- All original code has been deposited at [<u>https://github.com/jessica-ewald/2024_09_09_Axiom_OASIS</u>](https://github.com/jessica-ewald/2024_09_09_Axiom_OASIS) and is publicly available as of the date of publication.
  The DOI is listed in the key resources table.
- Any additional information required to reanalyze the data reported in this paper is available from the lead contact upon request.

# Acknowledgements

This work was supported by Banting and SOT Syngenta postdoctoral fellowships to JE, a National Institutes of Health grant (NIGMS R35 GM122547 to AEC), the Novo Nordisk Foundation (NNF21SA0072102), and the Omics for Assessing Signatures for Integrated Safety (OASIS) Consortium, which is supported by a grant from the Massachusetts Life Sciences Center (MLSC) Bits to Bytes Capital Call grant to SS, as well as partnered resources and expertise from industry partners and in-kind contributions from academic, government, non-governmental organizations, and biotech partners (listed here <u>[https://oasisconsortium.org/members](https://oasisconsortium.org/members/))</u>.
The authors thank Nisha Sipes and Katie Paul Friedman for their insightful reviews.

# Author contributions

Conceptualization: J.D.E., K.L.T., B.W., C.C., J.H., D.R., Sh.S., A.E.C., Data curation: J.D.E., K.L.T., A.A.C., Sr.S., Analysis: J.D.E., K.L.T., D.A.B., Sr.S., Funding acquisition: C.C., J.H., D.R., Sh.S., A.E.C., Experiments/Investigation: J.D.E., K.L.T., D.A.B., E.W., J.C., Methodology: J.D.E., K.L.T., D.A.B., A.A.C., A.B., A.B., Sr.S., T.J., B.L.G., K.J.K., J.H., Project administration: K.L.T., B.W., T.J., C.C., Software: J.D.E., D.A.B., A.A.C., A.B., A.B., E.W., Supervision: B.W., B.A.C., Sh.S., A.E.C., Visualization: J.D.E., Writing - original draft: J.D.E., K.L.T., Writing - review & editing: All authors.

# Declaration of generative AI and AI-assisted technologies in the manuscript preparation process

During the preparation of this work, the authors used ChatGPT-5 in a limited manner to improve the readability and language of the manuscript.
After using this tool, the authors reviewed and edited the content as needed and take full responsibility for the content of the published article.

# Figure titles and legends

<!-- source-page: 3 -->

***Figure 1.
Overview of the experimental design.***

![Figure 1.
Overview of the experimental design.](figures/figure-1.jpg)

*Primary human hepatocytes were exposed to eight concentrations of 1,085 compounds (2 replicates).
Three complementary assays (Cell Painting morphology, membrane rupture, and mitochondrial activity) were used to measure cellular responses to chemical exposure.
The ultimate goal is to predict several outcomes (right) from the processed readouts.
See also Figure S1.*

<!-- source-page: 4 -->

***Figure 2.
Assay activity trends.***

![Figure 2.
Assay activity trends.](figures/figure-2.jpg)

*Compounds with a strong increase in MT readouts (A), with the POD indicated by blue, dashed lines.
Number and percentage of active compounds and their morphological PODs according to different cell representations and distance metrics (B).
Comparison of PODs across cell representations (C; n = 342, 32%) and assays (D; n = 121, 12%).
In (C) and (D), only compounds with PODs for all four assays are displayed, to avoid bias for particular types of compounds.
The morphological PODs in (D) are computed from DINO features.
Lower values on the y axis indicate that activity was detected at a lower concentration (lower POD).
See also Figure S2.*

<!-- source-page: 8 -->

***Figure 3.
Classifier performance across assay types.***

![Figure 3.
Classifier performance across assay types.](figures/figure-3.jpg)

*Distributions of AUROC scores (A) and PRAUC scores (B) for the MT and LDH cytotoxicity (n = 2), ToxCast cytotoxicity (n = 48), ToxCast cell-based (n = 292), and ToxCast cell-free (n = 72) assays.
The sample size refers to the number of individual assays with AUROC and PRAUC scores.
The morphology and cell count classifiers are trained on CellProfiler features and cell counts that were median-aggregated across all concentrations.
The random baseline is trained on CellProfiler morphology features after randomly shuffling the labels.
(C) Mean difference in classifier performance according to AUROC and PRAUC, stratified by endpoint type, compared to random and cell count baselines, with the same sample sizes as for (A) and (B).
Associated paired t-test p-values are in parentheses.
Each point is an AUROC or PRAUC score for one assay.
See also Figure S3.*

<!-- source-page: 9 -->

***Figure 4.
Classifier performance across concentration and image representations.***

![Figure 4.
Classifier performance across concentration and image representations.](figures/figure-4.jpg)

*Classifier AUROCs, stratified by endpoint type, across consensus profile strategies (CellProfiler features) (A) and cell representations ("all" concentration consensus profiles) (B), for the MT and LDH cytotoxicity (n = 2), ToxCast cytotoxicity (n = 48), ToxCast cell-based (n = 292), and ToxCast cell-free (n = 72) assays.
Each point is an AUROC or PRAUC score for one assay.
The sample size refers to the number of individual assays with AUROC and PRAUC scores.
See also Figure S4.*

# Main tables

<!-- source-page: 5 -->

***Table 1.
Prediction of paired cytotoxicity readouts from cell morphology.***

*Mean R<sup>2</sup>, root mean square error (RMSE), and mean average error (MAE) between predicted and observed biochemical assay readouts for models trained on different input features across 10 different train-test splits (by compound).
Standard deviation values are in parentheses.
The technical baseline includes features for cell count, batch, plate, and well position.
The replicate baseline computes metrics between the first and second replicate of each compound-concentration exposure and captures the consistency between replicates for that assay.
The mean predictor baseline predicts the mean assay value for all compounds, providing a minimum performance reference that any useful model should exceed.*

<table>
<colgroup>
<col style="width: 25%" />
<col style="width: 25%" />
<col style="width: 25%" />
<col style="width: 25%" />
</colgroup>
<thead>
<tr>
<th style="text-align: left;">Input features</th>
<th style="text-align: left;">R<sup>2</sup></th>
<th style="text-align: left;">RMSE</th>
<th style="text-align: left;">MAE</th>
</tr>
<tr>
<th colspan="4" style="text-align: left;">LDH (ridge-normalized)</th>
</tr>
<tr>
<th style="text-align: left;">Mean predictor baseline</th>
<th style="text-align: left;">-0.002 (0.0020)</th>
<th style="text-align: left;">0.1 (0.011)</th>
<th style="text-align: left;">0.061 (0.0030)</th>
</tr>
<tr>
<th style="text-align: left;">Technical baseline</th>
<th style="text-align: left;">0.65 (0.044)</th>
<th style="text-align: left;">0.06 (0.0049)</th>
<th style="text-align: left;">0.035 (0.00078)</th>
</tr>
<tr>
<th style="text-align: left;">Replicate baseline</th>
<th style="text-align: left;">0.45 (0.062)</th>
<th style="text-align: left;">0.08 (0.0025)</th>
<th style="text-align: left;">0.053 (0.0017)</th>
</tr>
<tr>
<th style="text-align: left;">CellProfiler</th>
<th style="text-align: left;">0.65 (0.051)</th>
<th style="text-align: left;">0.059 (0.0026)</th>
<th style="text-align: left;">0.039 (0.00085)</th>
</tr>
<tr>
<th style="text-align: left;">CP-CNN</th>
<th style="text-align: left;">0.66 (0.053)</th>
<th style="text-align: left;">0.058 (0.0025)</th>
<th style="text-align: left;">0.039 (0.0010)</th>
</tr>
<tr>
<th style="text-align: left;">DINO</th>
<th style="text-align: left;">0.66 (0.052)</th>
<th style="text-align: left;">0.059 (0.0030)</th>
<th style="text-align: left;">0.04 (0.0011)</th>
</tr>
<tr>
<th colspan="4" style="text-align: left;">MT (ridge-normalized)</th>
</tr>
<tr>
<th style="text-align: left;">Mean predictor baseline</th>
<th style="text-align: left;">-0.0019 (0.0017)</th>
<th style="text-align: left;">0.17 (0.014)</th>
<th style="text-align: left;">0.092 (0.0044)</th>
</tr>
<tr>
<th style="text-align: left;">Technical baseline</th>
<th style="text-align: left;">0.70 (0.055)</th>
<th style="text-align: left;">0.093 (0.0050)</th>
<th style="text-align: left;">0.048 (0.0014)</th>
</tr>
<tr>
<th style="text-align: left;">Replicate baseline</th>
<th style="text-align: left;">0.88 (0.020)</th>
<th style="text-align: left;">0.06 (0.0052)</th>
<th style="text-align: left;">0.032 (0.0013)</th>
</tr>
<tr>
<th style="text-align: left;">CellProfiler</th>
<th style="text-align: left;">0.79 (0.039)</th>
<th style="text-align: left;">0.077 (0.0034)</th>
<th style="text-align: left;">0.042 (0.0013)</th>
</tr>
<tr>
<th style="text-align: left;">CP-CNN</th>
<th style="text-align: left;">0.79 (0.040)</th>
<th style="text-align: left;">0.077 (0.0032)</th>
<th style="text-align: left;">0.042 (0.0011)</th>
</tr>
<tr>
<th style="text-align: left;">DINO</th>
<th style="text-align: left;">0.79 (0.039)</th>
<th style="text-align: left;">0.078 (0.0031)</th>
<th style="text-align: left;">0.042 (0.0013)</th>
</tr>
</thead>
<tbody>
</tbody>
</table>

<!-- source-page: 6 -->

***Table 2.
Prediction of binarized cytotoxicity readouts with different cell morphology representations.***

*AUROC and PRAUC of MT and LDH cytotoxicity classifiers trained on different input features.
Performance was calculated from pooled predictions across 10 train-test splits.
The cell count baseline uses only cell count features.
The random baseline shuffled cytotoxicity labels before training the classifier.*

<table>
<colgroup>
<col style="width: 33%" />
<col style="width: 33%" />
<col style="width: 33%" />
</colgroup>
<thead>
<tr>
<th style="text-align: left;">Input features</th>
<th style="text-align: left;">AUROC</th>
<th style="text-align: left;">PRAUC</th>
</tr>
<tr>
<th colspan="3" style="text-align: left;">LDH (binary activity call)</th>
</tr>
<tr>
<th style="text-align: left;">Cell count baseline</th>
<th style="text-align: left;">0.73</th>
<th style="text-align: left;">0.42</th>
</tr>
<tr>
<th style="text-align: left;">Random baseline</th>
<th style="text-align: left;">0.50</th>
<th style="text-align: left;">0.14</th>
</tr>
<tr>
<th style="text-align: left;">CellProfiler</th>
<th style="text-align: left;">0.93</th>
<th style="text-align: left;">0.77</th>
</tr>
<tr>
<th style="text-align: left;">CP-CNN</th>
<th style="text-align: left;">0.93</th>
<th style="text-align: left;">0.72</th>
</tr>
<tr>
<th style="text-align: left;">DINO</th>
<th style="text-align: left;">0.94</th>
<th style="text-align: left;">0.77</th>
</tr>
<tr>
<th colspan="3" style="text-align: left;">MT (binary activity call)</th>
</tr>
<tr>
<th style="text-align: left;">Cell count baseline</th>
<th style="text-align: left;">0.69</th>
<th style="text-align: left;">0.64</th>
</tr>
<tr>
<th style="text-align: left;">Random baseline</th>
<th style="text-align: left;">0.51</th>
<th style="text-align: left;">0.40</th>
</tr>
<tr>
<th style="text-align: left;">CellProfiler</th>
<th style="text-align: left;">0.87</th>
<th style="text-align: left;">0.84</th>
</tr>
<tr>
<th style="text-align: left;">CP-CNN</th>
<th style="text-align: left;">0.86</th>
<th style="text-align: left;">0.83</th>
</tr>
<tr>
<th style="text-align: left;">DINO</th>
<th style="text-align: left;">0.87</th>
<th style="text-align: left;">0.84</th>
</tr>
</thead>
<tbody>
</tbody>
</table>

# STAR Methods

<!-- source-page: e1-e2 -->

## Key Resources Table

| Reagent or resource | Source | Identifier |
| --- | --- | --- |
| **Biological samples** | | |
| LIVERPOOL Mixed Gender Human Hepatocytes - 5-Donor Pool, Cryoplateable | BioIVT | X008052-P \| Lot: BSS, AW ID: s0617818 |
| **Chemicals, peptides, and recombinant proteins** | | |
| Collagen I, Rat Tail | Thermo Fisher | A10483-01 |
| INVITROGRO CP Medium | BioIVT | X008052-P \| Lot: BSS, AW ID: s0617818 |
| TORPEDO Antibiotic Mix | BioIVT | Z99000, Lot: C06103A |
| DMSO | Carl Roth | 4720 |
| OASIS Compounds | MedChemXpress | Table S1 |
| HBSS (10X), with calcium and magnesium, no phenol red | Fisher Scientific | 14065056 |
| 32% Paraformaldehyde solution | Science Services | E15740 |
| PhenoVue reagent dye diluent A (5x) | Revvity | PVDDA1 |
| PhenoVue 641 Mitochondrial stain | Revvity | CP3D1 # 08A |
| PhenoVue Flour 555-WGA | Revvity | CP1551 #02A |
| PhenoVue Flour 488 Concanavalin A | Revvity | CP94881 #03B |
| PhenoVue Flour 568 Phalloidin | Revvity | CP25681 #04A |
| PhenoVue 512 nucleic acid stain | Revvity | CP61 #03A |
| PhenoVue Hoechst 33342 nuclear stain | Revvity | CP71 #01B |
| **Critical commercial assays** | | |
| RealTime-Glo MT Cell Viability Assay | Promega | G9713 |
| CyQUANT LDH Cytotoxicity Assay Kit | Invitrogen | C20300/1 |
| **Deposited data** | | |
| Raw images | Database: Cell Painting Gallery | cpg0037-oasis/axiom/images/ |
| Metadata for images | Database: Cell Painting Gallery | cpg0037-oasis/axiom/workspace/metadata/ |
| Image-based profiles processed with CellProfiler | Database: Cell Painting Gallery | cpg0037-oasis/axiom/workspace/profiles/ |
| Image-based profiles processed with CP-CNN | Database: Cell Painting Gallery | cpg0037-oasis/axiom/workspace_dl/profiles/cpcnn_zenodo_7114558/ |
| Image-based profiles processed with DINO | Database: Cell Painting Gallery | cpg0037-oasis/axiom/workspace_dl/profiles/dinov2_b_vitl14_fieldnorm_825c11/ |
| ToxCast/Tox21 Assays (invitrodb v4.1) | Database: invitrodb v4.1 | ToxCast/Tox21 Assays (invitrodb v4.1) |
| **Software and algorithms** | | |
| Code repository for data analysis | 10.5281/zenodo.18242918 | https://github.com/jessica-ewald/2024_09_09_Axiom_OASIS |
| CellProfiler v4.2.4 | Stirling et al. | https://cellprofiler.org/releases |
| Cellpose v2.3.2 | Pachitariu and Stringer | https://www.cellpose.org/ |
| DINO v2 | Oquab et al. | https://huggingface.co/docs/transformers/model_doc/dinov2 |
| Cell Painting CNN | Moshkov et al. | https://zenodo.org/records/7114558 |
| FastBMD v0.0.0.9000 | Ewald et al. | https://github.com/jessica-ewald/fastbmdR |
| XGBoost v2.1.1 | Chen and Guestrin | https://xgboost.readthedocs.io/en/stable/install.html |
| **Other** | | |
| Multidrop Combi | Thermo Fisher | https://www.fishersci.co.uk/shop/products/p/17801692 |
| CyBio-Felix with 384-well head | Analytik Jena | https://www.analytik-jena.com/products/liquid-handling-automation/laboratory-equipment/automated-liquid-handlers-alh/cybio-felix-series/ |
| EnVision Multimode Detector | PerkinElmer, now Revvity | https://www.revvity.com/gb-en/product/envision-xcite-plate-reader-2105-0020 |
| Operetta CLS | PerkinElmer, now Revvity | https://www.revvity.com/gb-en/product/operetta-cls-system-hh16000020 |

<!-- source-page: e2 -->

## Experimental model and study participant details

### Cell culture

384-well microplates (Corning \#4518) were coated with 50 ug/mL of Collagen I, Rat Tail (Thermo Fisher) diluted in 20 mM acetic acid.
Plates were incubated with the collagen solution for 1 hour, washed twice with sterile H2O, and then air-dried in a sterile cabinet for a minimum of 2 hours before cell seeding.
Pooled primary human hepatocytes (PHH) from a commercial supplier (BioIVT; LIVERPOOL(R) Mixed Gender Human Hepatocytes, 5-donor pool) were thawed in a 37 degrees C water bath following the vendor's protocol, resuspended in INVITROGRO CP medium supplemented with TORPEDO antibiotic mix (Complete CP medium), and plated at 5,500 cells/well.
Plates were incubated at 37 degrees C in a humidified 5% CO2 incubator for 3-5 hours to allow time for cells to become adherent to the collagen coating.
The study used primary human hepatocytes rather than immortalized cell lines; therefore, standard cell line authentication procedures (e.g., STR profiling) are not applicable.
Because the hepatocytes were obtained as a pooled, mixed-sex donor population, sex could not be attributed to individual cells or samples.

<!-- source-page: e2-e5 -->

## Method details

### Compound selection

The OASIS Consortium curated a total of 1,495 compounds known to be of interest to the hepatotoxicology research community by integrating data from established toxicological resources, including DrugMatrix, TG-GATES, ToxRefDB, DILIlist and DILIrank [<sup>64-69</sup>](https://paperpile.com/c/2xFVvw/LltnY+JDli7+TgolH+YW2Dr+XRSFV+NPozc).
The curated dataset has been released via https://oasisconsortium.org/oasis-compounds.
Compounds were cross-referenced using InChIKey identifiers to remove duplicates.
The finalized list was a subset of 1,085 compounds that could be sourced from MedChemExpress.

### Compound treatment

Once cells were attached, the medium was replaced with Complete CP medium containing test compounds at a 2x final concentration using the CyBio Felix liquid handler.
Plates were then returned to the incubator for 44 hours at 37 degrees C, 5% CO2, until the assay endpoints were measured.
This timepoint was selected to balance convenience and prior studies indicating 48 hours maximizes sensitivity relative to 24 hours for chemical perturbations [<sup>70</sup>](https://paperpile.com/c/2xFVvw/3SrUM).
Each compound was tested at eight concentrations on a semi-log scale, with two biological replicates (n = 2 wells) per compound-concentration group.
DMSO solvent controls (n = 69 wells) were included on each plate, with fixed positions across plates chosen to represent all rows and columns.
Compound-concentration biological replicates were always on different plates.
The well position of compounds within plates were randomized.

### LDH and MT biochemical assays for cytotoxicity assessment

LDH (CyQUANT(TM) LDH Cytotoxicity Assay, Invitrogen) and MT (RealTime-Glo MT Cell Viability Assay, Promega) assays were performed to assess cytotoxicity.
For the LDH assay, a clear microplate was pre-filled with 7.5 uL HBSS, and 2.5 uL of cell media was transferred from the cell plate to the clear LDH assay plate using the CyBio Felix liquid handler.
The assay was performed according to the manufacturer's instructions by adding 10 uL of reaction mixture, incubating for 30 minutes in ambient conditions, then adding 10 uL of stop solution before measuring absorbance at 530 nm and 720 nm on an EnVision plate reader.
For the MT assay, the cell viability substrate and NanoLuc(R) enzyme were added to pre-warmed Complete CP medium to prepare the reagent solution, which was added at 15 uL/well to the cell plate and incubated for 1 hour at 37 degrees C and 5% CO2 before reading luminescence on the EnVision plate reader.
Cell plates were washed 2x with HBSS to remove any residual luminescent substrate prior to staining with Cell Painting dyes, which could interfere with image-based readouts.

### Cell Painting and image acquisition

We used the Cell Painting v3 protocol [<sup>70</sup>](https://paperpile.com/c/2xFVvw/3SrUM) using PhenoVue Cell Painting JUMP Kit (Revvity, PING21) to generate fluorescent images.
Initially, PhenoVue 641 Mitochondrial Stain in CP complete medium was added at a final concentration of 500 nM to HBSS-washed cells as described above, and cells were incubated for 30 minutes at 37 degrees C, 5% CO2.
Cells were then fixed with 4% paraformaldehyde (PFA) for 20 minutes at room temperature and washed four times with HBSS.
The remaining dyes, including PhenoVue Fluor 488 Concanavalin A (5 ug/mL), PhenoVue 512 Nucleic Acid Stain (1 ug/mL), PhenoVue Fluor 555 WGA (1.5 ug/mL), and PhenoVue Fluor 568 Phalloidin (8 nM), were added.
We reduced the concentration of PhenoVue 512 Nucleic Acid Stain (RNA) from 3 ug/mL to 1 ug/mL to reduce channel similarity to the neighboring WGP channel; otherwise, the protocol was followed as published [<sup>70</sup>](https://paperpile.com/c/2xFVvw/3SrUM).
Images were acquired on an Operetta imaging system (Revvity) using a 40x water objective in non-confocal mode.
We chose to image at 40x, a higher resolution than the 20x that is typical for the Cell Painting assay [<sup>70</sup>](https://paperpile.com/c/2xFVvw/3SrUM), to maximize the chances of capturing phenotypes.
We captured more fields of view (15 vs 9) to compensate for the smaller number of cells per field.
Full-resolution images (2160x2160) were captured with binning set to 1.
A single z-plane was acquired for each of the five fluorescent channels and one brightfield channel, with the optimal z-plane selected for each channel based on focal quality assessed by maximal variance in Laplacian texture measurement.

### Image processing

*CellProfiler.* We used CellProfiler bioimage analysis software (version 4.2.4) [<sup>29</sup>](https://paperpile.com/c/2xFVvw/Xq4Xw) to process the images using classical algorithms following a prior protocol [<sup>70</sup>](https://paperpile.com/c/2xFVvw/3SrUM).
Flat field correction was applied to the images [<sup>71</sup>](https://paperpile.com/c/2xFVvw/T7Dx2).
We segmented nuclei using Cellpose (version 2.3.2) [<sup>72</sup>](https://paperpile.com/c/2xFVvw/OXvQx) as a CellProfiler plugin [<sup>73</sup>](https://paperpile.com/c/2xFVvw/nNLWc) with the pre-trained "nuclei" model and minimum object size of 1500 px) and cells and measured feature categories including fluorescence intensity, texture, granularity, density, and location (see http://cellprofiler-manual.s3.amazonaws.com/CellProfiler-4.2.4/index.html for more details) across all segmented compartments and all imaged channels.
We obtained 5,640 feature measurements from each of about 800 cells per well.
We parallelized our image processing workflow using Distributed-CellProfiler [<sup>74</sup>](https://paperpile.com/c/2xFVvw/xj8oL).
The image analysis pipelines we used are available in the Cell Painting Gallery [<sup>75</sup>](https://paperpile.com/c/2xFVvw/hsX8C).

*CellPainting-CNN (CP-CNN)*.
Images were converted to JPEG-XL format with the -q 99 option.
Cell centers were taken from CellProfiler output.
DeepProfiler (version bed9d6a with pull request 358) with the CellPainting-CNN model [<sup>30</sup>](https://paperpile.com/c/2xFVvw/e3bSu) \[https://github.com/cytomining/DeepProfiler/pull/358/files, https://zenodo.org/records/7114558\] was used to generate embeddings.
CP-CNN profiles contain 672 features.

*DINO.* Each channel image was preprocessed with instance normalization at the field level to control for intensity variation.
Then, a pre-trained DINOv2 model ViT-L/14 (*https://github.com/facebookresearch/dinov2)* was used on each of the 6 normalized channel images per FOV to generate vectors of features of length 768 per channel.
DINO profiles contain 4,608 features.

<!-- source-page: e3-e4 -->

### ToxCast data curation

ToxCast includes data from different assays, each of which can have one or multiple endpoints, measured across different tissue, cell, and cell-free models from different species [<sup>12</sup>](https://paperpile.com/c/2xFVvw/yvOvE).
Each endpoint was measured at multiple compound concentrations, often along with cell viability or cytotoxicity endpoints run in parallel to the assay.
For each compound-endpoint concentration-response series, the ToxCast authors calculate a hit call from 0 to 1 (with 1 being high confidence that there is a change of activity relative to the control), and an AC50 value (concentration at which 50% of the maximum endpoint value is observed) [<sup>12</sup>](https://paperpile.com/c/2xFVvw/yvOvE).
We considered any hit call \>0.9 to be a positive hit.
We matched ToxCast compounds to our tested compound library using the EPA's DTXSID.

We accessed all assay endpoint data from *invitrodb* version 4.1 using the SQLalchemy version 1.4.54 Python package.
We filtered endpoints to only include those from human cell and cell-free assays.
We excluded QA/QC endpoints like background fluorescence, the individual ch1 and ch2 endpoints used to compute the more interpretable "ratio" endpoints, any assay marked as "follow-up", and any human cells that were transfected with non-human genes.
When the same endpoint was measured after multiple exposure time points, we kept the single timepoint that most closely matched our experimental design (44 hour compound exposure).
Any positive hit call with an associated AC50 higher than 100uM (the highest concentration we tested) was set to 0 because the activity was not observed in our tested range.

A significant proportion of the specific cell-based assay endpoint AC50s are at the same or higher concentrations than where cytotoxicity is observed; these are more indicative of general cell stress than of the specific modes-of-action that the endpoints were intended to measure [<sup>76,77</sup>](https://paperpile.com/c/2xFVvw/uvFXc+SRniu).
We performed extra assay filtering and curation steps to account for confounding between specific endpoints and cytotoxicity endpoints.
We computed "consensus cytotoxicity hit calls" of assays marked with a 1 in the "cell_viability_assay" ToxCast metadata across different biological categories defined by "cell_short_name"and "tissue" ToxCast metadata annotations.
For each cell and tissue category, we considered a compound to have a positive cytotoxicity hit call if 20% or more of the individual hit calls were positive and defined the AC50 as the median AC50 of all of the positive hit calls.
Next, we compared each specific cell-based assay endpoint AC50 to the closest matched consensus cytotoxicity AC50 (cell-level if available, tissue-level otherwise).
If the specific AC50 was higher than the cytotoxicity AC50 / 2, then the specific endpoint hit call was set to 0.
Across all cell-based assays and OASIS compounds, there were 281,196 hit calls for non-cytotoxicity endpoints, where each hit call specifies whether a particular assay was active for a particular compound.
Of these, there were initially 17,110 positive hits (6.1% of all hit calls) and filtering for cytotoxicity-confounded hits reduced the positive calls by 51% from 17,110 to 8400 (3.0% of all hit calls).
Finally, we removed endpoints from the curated dataset if there were fewer than five positive and negative hit calls in our tested compound library.

### Profile processing

Image-based profiles from CellProfiler, DINO, and CP-CNN were analyzed using the same Python pipeline.
First, features with missing or infinite values were filtered out.
Next, features that had an absolute coefficient of variation \< 0.001 in the DMSO negative control samples on any plate were also filtered out to prevent the creation of exploding values in the next step.
Profiles were next MAD-normalized, by subtracting the median and dividing by the MAD of the DMSO samples from the same plate, to minimize systematic plate effects.
Finally, profiles were filtered to remove low variability and highly correlated features using the "variance_threshold" and "correlation_threshold" from Pycytominer (v1.2.0) [<sup>78</sup>](https://paperpile.com/c/2xFVvw/6WsvV) using default parameters.

### Mahalanobis distance calculations

Various Mahalanobis distances were computed between each morphological profile and the centroid of the DMSO samples on the same plate, as described previously [<sup>32</sup>](https://paperpile.com/c/2xFVvw/Ux9D4).
The global Mahalanobis distance is calculated using entire profiles that include all measured features.
The categorical Mahalanobis distances are computed for "mini" profiles, each containing a subset of related features.
The set of categories depends on the type of cell representation.

CellProfiler produces named, interpretable features and so it is possible to group them into categories according to both the subcellular compartments imaged by each channel (DNA, ER, RNA, actin+golgi, and mitochondria) and the various segmented parts of each cell (entire cell, cytoplasm only, and nucleus only) [<sup>29</sup>](https://paperpile.com/c/2xFVvw/Xq4Xw).
In addition to the five channels, we also considered the "AreaShape" features as a sixth category since these do not depend on any individual channel.
This resulted in 6\*3 = 18 categories, for example Cells_RNA or Cytoplasm_AreaShape.

Cell representations from deep learning methods do not have features with meaningful names.
Since the CellPainting-CNN produces one set of embeddings that represent images from all channels simultaneously [<sup>30</sup>](https://paperpile.com/c/2xFVvw/e3bSu), it is not possible to break these into smaller categories and so only global Mahalanobis distances were computed for this representation.
The DINO architecture produces one set of embeddings for each individual image, and so we computed six categorical Mahalanobis distances for each perturbation, one for each channel (DNA, ER, RNA, actin+golgi, mitochondria, and brightfield).

<!-- source-page: e4-e5 -->

### Concentration-response analysis

Curve fitting was performed on all Mahalanobis distances (both global and categorical, where applicable), cell count, and normalized MT and LDH biochemical assays according to conventional approaches used by the regulatory toxicology community [<sup>48,79</sup>](https://paperpile.com/c/2xFVvw/Hj8YM+1BzuC), here using the fastbmdR package (v0.0.0.9, [<u>https://github.com/jessica-ewald/fastbmdR</u>](https://github.com/jessica-ewald/fastbmdR))[<sup>80</sup>](https://paperpile.com/c/2xFVvw/Zd6QD).
Prior to fitting, concentrations were converted to a logarithmic scale (base 10).
Eight parametric models (Exp2, Exp3, Exp4, Exp5, Poly2, Lin, Power, Hill, as defined here [<sup>79</sup>](https://paperpile.com/c/2xFVvw/Hj8YM)) were fit to the Mahalanobis distances, cell count, and biochemical assay readouts for each compound.
Curve fits were filtered out if the standard deviation of the residuals was more than three times the standard deviation of the DMSO controls.
The best-fit model for each readout for each compound was defined as the one with the lowest standard deviation of the residuals.
The benchmark dose for each best-fit model was defined as the concentration at which the fitted curve exceeded the benchmark response, which was defined as the 95th percentile of Mahalanobis distances (MDs) from DMSO controls.
We used the 95th percentile rather than the mean +- SD because the distribution of DMSO MDs is highly right-skewed.
Since each DMSO MD represents the distance from the DMSO centroid, only unusually large values are biologically meaningful, making a one-sided threshold appropriate.
Benchmark doses were filtered out if the ratio between the upper and lower 95th confidence intervals was greater than 40 or if the benchmark dose was higher than the highest tested concentration.
For morphology readouts, compound-level PODs were defined as the lowest POD among all of the global and categorical Mahalanobis distance PODs that passed the QA/QC filters for each compound.

<!-- source-page: e5 -->

### Supervised analysis

XGBoost was used to predict various continuous and categorical labels from different sources [<sup>81</sup>](https://paperpile.com/c/2xFVvw/iyfRv).
For all scenarios, we used five-fold cross-validation with compound-level splits, stratified to preserve the proportion of active and inactive compounds in each fold.
Default parameters were used, and the exact splits can be reproduced from the linked GitHub repository.
For continuous outcomes, we trained XGBRegressor models and compared performance to a mean predictor baseline and to a "technical metadata" baseline with cell count, batch, plate, and well position features.
We assessed performance with R<sup>2</sup> and RMSE and MAE.
For the categorical outcomes describing assay activity, we trained binary XGBoost classifiers and compared performance to a random baseline (labels shuffled prior to training) and to a cell count baseline.
Classification performance was assessed using AUROC (Area Under the Receiver Operating Characteristic curve) and PRAUC (Area Under the Precision-Recall curve).

The continuous outcomes had one readout per Cell Painting profile, therefore we trained models based on individual profiles.
The categorical outcomes describing assay activity had one label for each compound, corresponding to sixteen morphological profiles (two replicates for each of the eight tested concentrations).
We created three different compound consensus profiles computed as the median of each feature across different sets of profiles: 1) all profiles ("all"), 2) all profiles after the morphology POD, defaulting to all profiles if there was no detected morphological change ("all_morph"), and 3) all profiles between the morphology POD and cytotoxicity POD, defaulting to all profiles after the morphology POD if there was no cytotoxicity and to all profiles if there was no cytotoxicity or morphology changes ("all_morph_cytotox").
We trained a different classifier for each consensus profile, and compared performance across consensus profile strategies.

<!-- source-page: e5 -->

## Quantification and statistical analysis

Statistical analyses were conducted in Python using the scipy.stats library.
Information on the statistical tests performed and sample sizes is provided in the figure legends.
A significance threshold of p \< 0.05 was applied for single-hypothesis tests, while an FDR cutoff of \< 0.05 was used when correcting for multiple hypotheses; further details are specified in the corresponding figure legends.
For the Cell Painting, MT, and LDH assays, 5,500 cells were seeded per well across sixteen wells per compound (eight concentrations with two replicates each).
These values reflect the initial seeding density, as some cell loss occurred during compound treatment.
The final cell counts at the time of assay readout were measured and are reported in the Metadata_Count_Cells column of the processed dataset deposited in the Cell Painting Gallery (see Key Resources Table).

# Supplementary table titles

Supplementary Table 1.
OASIS Compound List, related to Figure 1

Supplementary Table 2.
Cytotoxicity points-of-departure, related to Figure 2

Supplementary Table 3.
Cell Painting points-of-departure, related to Figure 2

Supplementary Table 4.
Summary of activity across all assays, related to Figure 2

Supplementary Table 5.
Toxcast assay bioactivity data for 2-Ethylanthraquinone, related to Figure 2

# Supplemental figure legends

These legends were transcribed from the published `sources/supplemental-figures.pdf`.

## Figure S1. Representative Cell Painting image, related to Figure 1

![Figure S1.
Representative Cell Painting image.](figures/figure-s1.jpg)

Representative Cell Painting image of a randomly selected DMSO solvent control.
Plate = 41002889, well = L12, site = 6.
This image is representative of 191,754 total images in the dataset, 43,641 of which are DMSO solvent controls.

## Figure S2. Technical factors influencing paired assay prediction, related to Figure 2

![Figure S2.
Technical factors influencing paired assay prediction.](figures/figure-s2.jpg)

Mean cell count (A), normalized LDH (B), and normalized MT (C) for each well position across a representative batch (prod_27).
Ridge-normalized MT values (D) and cell counts (E) across different sets of samples.
Panel F is a clustergram of pairwise cosine similarity between DINO profiles of the exposures that were significantly better predicted by Cell Painting than by the technical baseline, with rows and columns colored by cell count.
All color scales are linear between the minimum and maximum observed values in the respective dataset.

## Figure S3. ToxCast assay binarization, related to Figure 3

![Figure S3.
ToxCast assay binarization.](figures/figure-s3.jpg)

Detailed methods for binarizing ToxCast assays are shown in panel A.
Cytotoxicity AC50 values are shown across the 12 cell lines (C) and tissues (D) that had more than 800 OASIS compounds.
Compounds that either had an AC50 above 100 or did not have a detected AC50 were set to 100, the upper range of OASIS concentrations.
Lower values indicate greater cytotoxicity because it occurred at a lower concentration, with color on a linear scale from 0 to 100.

## Figure S4. Classifier PRAUC across concentration and image representations, related to Figure 4

![Figure S4.
Classifier PRAUC across concentration and image representations.](figures/figure-s4.jpg)

Classifier PRAUC is stratified by endpoint type across consensus profile strategy (A) and cell representation (B).

Declaration of interests

The Authors declare the following competing interests: B.A.C., S.S., and A.E.C. serve as scientific advisors for companies that use image-based profiling and Cell Painting (B.A.C.: Marble Therapeutics, A.E.C: Recursion, SyzOnc, Quiver Bioscience, S.S.: Waypoint Bio, Dewpoint Therapeutics, Deepcell) and receive honoraria for occasional scientific visits to pharmaceutical and biotechnology companies.
K.J.K. is a consultant for Tome Biosciences, AlloDx, and Vor Biosciences, and a member of the scientific advisory board of Nurture Genomics.
All other authors declare no competing interests.

Disclaimer

This manuscript has been reviewed by the Center for Computational Toxicology and Exposure, Office of Research and Development, U.S. Environmental Protection Agency, and approved for publication.
Approval does not signify that the contents reflect the official views or policies of the Agency, nor does mention of trade names or commercial products constitute endorsement or recommendation for use.

# References

1\.
[Wang, Z., Walker, G.W., Muir, D.C.G., and Nagatani-Yoshida, K. (2020).
Toward a global understanding of chemical pollution: A first comprehensive analysis of national and regional chemical inventories.
Environ.
Sci.
Technol.
*54*, 2575-2584.](http://paperpile.com/b/2xFVvw/3P7iR)

2\.
[Ewart, L., Apostolou, A., Briggs, S.A., Carman, C.V., Chaff, J.T., Heng, A.R., Jadalannagari, S., Janardhanan, J., Jang, K.-J., Joshipura, S.R., et al.
(2022).
Performance assessment and economic analysis of a human Liver-Chip for predictive toxicology.
Commun.
Med.
*2*, 154.](http://paperpile.com/b/2xFVvw/il16T)

3\.
[Krewski, D., Acosta, D., Jr, Andersen, M., Anderson, H., Bailar, J.C., 3rd, Boekelheide, K., Brent, R., Charnley, G., Cheung, V.G., Green, S., Jr, et al.
(2010).
Toxicity testing in the 21st century: a vision and a strategy.
J. Toxicol.
Environ.
Health B Crit.
Rev.
*13*, 51-138.](http://paperpile.com/b/2xFVvw/6K9bT)

4\.
[Thomas, R.S., Bahadori, T., Buckley, T.J., Cowden, J., Deisenroth, C., Dionisio, K.L., Frithsen, J.B., Grulke, C.M., Gwinn, M.R., Harrill, J.A., et al.
(2019).
The Next Generation Blueprint of Computational Toxicology at the U.S. Environmental Protection Agency.
Toxicol.
Sci.
*169*, 317-332.](http://paperpile.com/b/2xFVvw/KgGPB)

5\.
[Gilmour, N., Kern, P.S., Alepee, N., Boisleve, F., Bury, D., Clouet, E., Hirota, M., Hoffmann, S., Kuhnl, J., Lalko, J.F., et al.
(2020).
Development of a next generation risk assessment framework for the evaluation of skin sensitisation of cosmetic ingredients.
Regul.
Toxicol.
Pharmacol.
*116*, 104721.](http://paperpile.com/b/2xFVvw/Hjzf8)

6\.
[Fortin, A.-M.V., Long, A.S., Williams, A., Meier, M.J., Cox, J., Pinsonnault, C., Yauk, C.L., and White, P.A.
(2023).
Application of a new approach methodology (NAM)-based strategy for genotoxicity assessment of data-poor compounds.
Front.
Toxicol.
*5*, 1098432.](http://paperpile.com/b/2xFVvw/QjS9X)

7\.
[Ankley, G.T., Bennett, R.S., Erickson, R.J., Hoff, D.J., Hornung, M.W., Johnson, R.D., Mount, D.R., Nichols, J.W., Russom, C.L., Schmieder, P.K., et al.
(2010).
Adverse outcome pathways: a conceptual framework to support ecotoxicology research and risk assessment.
Environ.
Toxicol.
Chem.
*29*, 730-741.](http://paperpile.com/b/2xFVvw/vA7Qb)

8\.
[Villeneuve, D.L., Crump, D., Garcia-Reyero, N., Hecker, M., Hutchinson, T.H., LaLone, C.A., Landesmann, B., Lettieri, T., Munn, S., Nepelska, M., et al.
(2014).
Adverse outcome pathway (AOP) development I: strategies and principles.
Toxicol.
Sci.
*142*, 312-320.](http://paperpile.com/b/2xFVvw/7KVVh)

9\.
[Thomas, R.S., Paules, R.S., Simeonov, A., Fitzpatrick, S.C., Crofton, K.M., Casey, W.M., and Mendrick, D.L.
(2018).
The US Federal Tox21 Program: A strategic and operational plan for continued leadership.
ALTEX *35*, 163-168.](http://paperpile.com/b/2xFVvw/yQROZ)

10\.
[Richard, A.M., Judson, R.S., Houck, K.A., Grulke, C.M., Volarath, P., Thillainadarajah, I., Yang, C., Rathman, J., Martin, M.T., Wambaugh, J.F., et al.
(2016).
ToxCast chemical landscape: Paving the road to 21st century toxicology.
Chem.
Res.
Toxicol.
*29*, 1225-1251.](http://paperpile.com/b/2xFVvw/M8sMB)

11\.
[Kavlock, R., Chandler, K., Houck, K., Hunter, S., Judson, R., Kleinstreuer, N., Knudsen, T., Martin, M., Padilla, S., Reif, D., et al.
(2012).
Update on EPA's ToxCast program: providing high throughput decision support tools for chemical risk management.
Chem.
Res.
Toxicol.
*25*, 1287-1302.](http://paperpile.com/b/2xFVvw/XtCtu)

12\.
[Feshuk, M., Kolaczkowski, L., Dunham, K., Davidson-Fritz, S.E., Carstens, K.E., Brown, J., Judson, R.S., and Paul Friedman, K. (2023).
The ToxCast pipeline: updates to curve-fitting approaches and database structure.
Front.
Toxicol.
*5*, 1275980.](http://paperpile.com/b/2xFVvw/yvOvE)

13\.
[Bundy, J.L., Everett, L.J., Rogers, J.D., Nyffeler, J., Byrd, G., Culbreth, M., Haggard, D.E., Word, L.J., Chambers, B.A., Davidson-Fritz, S., et al.
(2024).
High-Throughput Transcriptomics screen of ToxCast chemicals in U-2 OS cells.
Toxicol.
Appl.
Pharmacol.
*491*, 117073.](http://paperpile.com/b/2xFVvw/kUchq)

14\.
[Meier, M.J., Harrill, J., Johnson, K., Thomas, R.S., Tong, W., Rager, J.E., and Yauk, C.L.
(2024).
Progress in toxicogenomics to protect human health.
Nat.
Rev.
Genet., 1-18.](http://paperpile.com/b/2xFVvw/rlEuk)

15\.
[Liu, A., Seal, S., Yang, H., and Bender, A. (2023).
Using chemical and biological data to predict drug toxicity.
SLAS Discov.
*28*, 53-64.](http://paperpile.com/b/2xFVvw/KRdtK)

16\.
[Seal, S., Trapotsi, M.-A., Spjuth, O., Singh, S., Carreras-Puigvert, J., Greene, N., Bender, A., and Carpenter, A.E.
(2024).
Cell Painting: a decade of discovery and innovation in cellular imaging.
Nat.
Methods, 1-15.](http://paperpile.com/b/2xFVvw/nG35j)

17\.
[Bray, M.-A., Singh, S., Han, H., Davis, C.T., Borgeson, B., Hartland, C., Kost-Alimova, M., Gustafsdottir, S.M., Gibson, C.C., and Carpenter, A.E.
(2016).
Cell Painting, a high-content image-based assay for morphological profiling using multiplexed fluorescent dyes.
Nat.
Protoc.
*11*, 1757-1774.](http://paperpile.com/b/2xFVvw/N3alo)

18\.
[Dahlin, J.L., Hua, B.K., Zucconi, B.E., Nelson, S.D., Jr, Singh, S., Carpenter, A.E., Shrimp, J.H., Lima-Fernandes, E., Wawer, M.J., Chung, L.P.W., et al.
(2023).
Reference compounds for characterizing cellular injury in high-content cellular morphology assays.
Nat.
Commun.
*14*, 1364.](http://paperpile.com/b/2xFVvw/skeIa)

19\.
[Nyffeler, J., Willis, C., Harris, F.R., Taylor, L.W., Judson, R., Everett, L.J., and Harrill, J.A.
(2022).
Combining phenotypic profiling and targeted RNA-Seq reveals linkages between transcriptional perturbations and chemical effects on cell morphology: Retinoic acid as an example.
Toxicol.
Appl.
Pharmacol.
*444*, 116032.](http://paperpile.com/b/2xFVvw/sb19j)

20\.
[Harrill, J.A., Everett, L.J., Haggard, D.E., Word, L.J., Bundy, J.L., Chambers, B., Harris, F., Willis, C., Thomas, R.S., Shah, I., et al.
(2024).
Signature analysis of high-throughput transcriptomics screening data for mechanistic inference and chemical grouping.
Toxicol.
Sci.
*202*, 103-122.](http://paperpile.com/b/2xFVvw/yFw7E)

21\.
[Seal, S., Yang, H., Vollmers, L., and Bender, A. (2021).
Comparison of cellular morphological descriptors and molecular fingerprints for the prediction of cytotoxicity- and proliferation-related assays.
Chem.
Res.
Toxicol.
*34*, 422-437.](http://paperpile.com/b/2xFVvw/oGg2H)

22\.
[Bundy, J.L., Judson, R., Williams, A.J., Grulke, C., Shah, I., and Everett, L.J.
(2022).
Predicting molecular initiating events using chemical target annotations and gene expression.
BioData Min.
*15*, 7.](http://paperpile.com/b/2xFVvw/BpV5M)

23\.
[Moshkov, N., Becker, T., Yang, K., Horvath, P., Dancik, V., Wagner, B.K., Clemons, P.A., Singh, S., Carpenter, A.E., and Caicedo, J.C.
(2023).
Predicting compound activity from phenotypic profiles and chemical structures.
Nat.
Commun.
*14*, 1967.](http://paperpile.com/b/2xFVvw/acrNa)

24\.
[Way, G.P., Kost-Alimova, M., Shibue, T., Harrington, W.F., Gill, S., Piccioni, F., Becker, T., Shafqat-Abbasi, H., Hahn, W.C., Carpenter, A.E., et al.
(2021).
Predicting cell health phenotypes using image-based morphology profiling.
Mol.
Biol.
Cell *32*, 995-1005.](http://paperpile.com/b/2xFVvw/UKAzb)

25\.
[Bahtiri, S., Hagens, T.M.S., van de Water, B., and Niemeijer, M. (2025).
Mechanism-based drug safety testing using innovative in vitro liver models: from DILI prediction to idiosyncratic DILI liability assessment.
Expert Opin.
Drug Metab.
Toxicol.
*21*, 769-787.](http://paperpile.com/b/2xFVvw/ShH7M)

26\.
[Lee, W.M.
(2003).
Drug-induced hepatotoxicity.
N. Engl.
J. Med.
*349*, 474-485.](http://paperpile.com/b/2xFVvw/Ygh3A)

27\.
[Kumar, P., Nagarajan, A., and Uchil, P.D.
(2018).
Analysis of cell viability by the lactate dehydrogenase assay.
Cold Spring Harb.
Protoc.
*2018*, db.prot095497.](http://paperpile.com/b/2xFVvw/YamBn)

28\.
[Burton, J.D.
(2005).
The MTT assay to evaluate chemosensitivity.
Methods Mol.
Med.
*110*, 69-78.](http://paperpile.com/b/2xFVvw/xulhF)

29\.
[Stirling, D.R., Swain-Bowden, M.J., Lucas, A.M., Carpenter, A.E., Cimini, B.A., and Goodman, A. (2021).
CellProfiler 4: improvements in speed, utility and usability.
BMC Bioinformatics *22*, 433.](http://paperpile.com/b/2xFVvw/Xq4Xw)

30\.
[Moshkov, N., Bornholdt, M., Benoit, S., Smith, M., McQuin, C., Goodman, A., Senft, R.A., Han, Y., Babadi, M., Horvath, P., et al.
(2024).
Learning representations for image-based profiling of perturbations.
Nat.
Commun.
*15*, 1594.](http://paperpile.com/b/2xFVvw/e3bSu)

31\.
[Oquab, M., Darcet, T., Moutakanni, T., Vo, H., Szafraniec, M., Khalidov, V., Fernandez, P., Haziza, D., Massa, F., El-Nouby, A., et al.
(2023).
DINOv2: Learning robust visual features without supervision. arXiv \[cs.CV\].](http://paperpile.com/b/2xFVvw/L2SVY)

32\.
[Nyffeler, J., Haggard, D.E., Willis, C., Setzer, R.W., Judson, R., Paul-Friedman, K., Everett, L.J., and Harrill, J.A.
(2021).
Comparison of Approaches for Determining Bioactivity Hits from High-Dimensional Profiling Data.
SLAS Discov *26*, 292-308.](http://paperpile.com/b/2xFVvw/Ux9D4)

33\.
[Chandrasekaran, S.N., Alix, E., Arevalo, J., Borowa, A., Byrne, P.J., Charles, W.G., Chen, Z.S., Cimini, B.A., Deng, B., Doench, J.G., et al.
(2024).
Morphological map of under- and over-expression of genes in human cells. bioRxiv, 2024.12.02.624527. https://doi.org/](http://paperpile.com/b/2xFVvw/KVNuY)[10.1101/2024.12.02.624527](http://dx.doi.org/10.1101/2024.12.02.624527)[.](http://paperpile.com/b/2xFVvw/KVNuY)

34\.
[Wong, D.R., Logan, D.J., Hariharan, S., Stanton, R., Clevert, D.-A., and Kiruluta, A. (2023).
Deep representation learning determines drug mechanism of action from cell painting images.
Digit.
Discov.
*2*, 1354-1367.](http://paperpile.com/b/2xFVvw/kqvqd)

35\.
[Seal, S., Mahale, M., Garcia-Ortegon, M., Joshi, C.K., Hosseini-Gerami, L., Beatson, A., Greenig, M., Shekhar, M., Patra, A., Weis, C., et al.
(2025).
Machine learning for toxicity prediction using chemical structures: Pillars for success in the real world.
Chem.
Res.
Toxicol.
*38*, 759-807.](http://paperpile.com/b/2xFVvw/Id6zF)

36\.
[Arevalo, J., Su, E., Ewald, J.D., van Dijk, R., Carpenter, A.E., and Singh, S. (2024).
Evaluating batch correction methods for image-based cell profiling.
Nat.
Commun.
*15*, 6516.](http://paperpile.com/b/2xFVvw/gLTfl)

37\.
[Laaksonen, T., Santos, H., Vihola, H., Salonen, J., Riikonen, J., Heikkila, T., Peltonen, L., Kumar, N., Murzin, D.Y., Lehto, V.-P., et al.
(2007).
Failure of MTT as a toxicity testing agent for mesoporous silicon microparticles.
Chem.
Res.
Toxicol.
*20*, 1913-1918.](http://paperpile.com/b/2xFVvw/chDf7)

38\.
[Ghasemi, M., Turnbull, T., Sebastian, S., and Kempson, I. (2021).
The MTT assay: Utility, limitations, pitfalls, and interpretation in bulk and single-cell analysis.
Int.
J. Mol.
Sci.
*22*, 12827.](http://paperpile.com/b/2xFVvw/FpRy1)

39\.
[Kot, M., and Daniel, W.A.
(2011).
Cytochrome P450 is regulated by noradrenergic and serotonergic systems.
Pharmacol.
Res.
*64*, 371-380.](http://paperpile.com/b/2xFVvw/0tIPR)

40\.
[Konstandi, M. (2013).
Psychophysiological stress: a significant parameter in drug pharmacokinetics.
Expert Opin.
Drug Metab.
Toxicol.
*9*, 1317-1334.](http://paperpile.com/b/2xFVvw/rcLWn)

41\.
[Harkitis, P., Daskalopoulos, E.P., Malliou, F., Lang, M.A., Marselos, M., Fotopoulos, A., Albucharali, G., and Konstandi, M. (2015).
Dopamine D2-receptor antagonists down-regulate CYP1A1/2 and CYP1B1 in the rat liver.
PLoS One *10*, e0128708.](http://paperpile.com/b/2xFVvw/2dqLc)

42\.
[Nishikawa, T., Bellance, N., Damm, A., Bing, H., Zhu, Z., Handa, K., Yovchev, M.I., Sehgal, V., Moss, T.J., Oertel, M., et al.
(2014).
A switch in the source of ATP production and a loss in capacity to perform glycolysis are hallmarks of hepatocyte failure in advance liver disease.
J. Hepatol.
*60*, 1203-1211.](http://paperpile.com/b/2xFVvw/AIWIY)

43\.
[Veith, A., and Moorthy, B. (2018).
Role of cytochrome p450s in the generation and metabolism of reactive oxygen species.
Curr.
Opin.
Toxicol.
*7*, 44-51.](http://paperpile.com/b/2xFVvw/XWkMS)

44\.
[Zou, Y., Li, H., Graham, E.T., Deik, A.A., Eaton, J.K., Wang, W., Sandoval-Gomez, G., Clish, C.B., Doench, J.G., and Schreiber, S.L.
(2020).
Cytochrome P450 oxidoreductase contributes to phospholipid peroxidation in ferroptosis.
Nat.
Chem.
Biol.
*16*, 302-309.](http://paperpile.com/b/2xFVvw/QFkT4)

45\.
[Fujii, J., and Imai, H. (2024).
Oxidative metabolism as a cause of lipid peroxidation in the execution of ferroptosis.
Int.
J. Mol.
Sci.
*25*, 7544.](http://paperpile.com/b/2xFVvw/WBeH0)

46\.
[Nyffeler, J., Willis, C., Harris, F.R., Foster, M.J., Chambers, B., Culbreth, M., Brockway, R.E., Davidson-Fritz, S., Dawson, D., Shah, I., et al.
(2023).
Application of Cell Painting for chemical hazard evaluation in support of screening-level chemical assessments.
Toxicol.
Appl.
Pharmacol.
*468*, 116513.](http://paperpile.com/b/2xFVvw/05XcE)

47\.
[Wheeler, M.W., Lim, S., House, J., Shockley, K., Bailer, A.J., Fostel, J., Yang, L., Talley, D., Raghuraman, A., Gift, J.S., et al.
(2023).
ToxicR: A computational platform in R for computational toxicology and dose-response analyses.
Comput.
Toxicol.
*25*, 100259.](http://paperpile.com/b/2xFVvw/Qmdr4)

48\.
[O'Brien, J., Mitchell, C., Auerbach, S., Doonan, L., Ewald, J., Everett, L., Faranda, A., Johnson, K., Reardon, A., Rooney, J., et al.
(2024).
Bioinformatic workflows for deriving transcriptomic points of departure: Current status, data gaps, and research priorities.
Toxicol.
Sci., kfae145.](http://paperpile.com/b/2xFVvw/1BzuC)

49\.
[Ji, C., Weissmann, A., and Shao, K. (2022).
A computational system for Bayesian benchmark dose estimation of genomic data in BBMD.
Environ.
Int.
*161*, 107135.](http://paperpile.com/b/2xFVvw/31q8t)

50\.
[Kraus, O., Kenyon-Dean, K., Saberian, S., Fallah, M., McLean, P., Leung, J., Sharma, V., Khan, A., Balakrishnan, J., Celik, S., et al.
(2024).
Masked autoencoders for microscopy are scalable learners of cellular biology. arXiv \[cs.CV\].](http://paperpile.com/b/2xFVvw/4cg5D)

51\.
[Celik, S., Hutter, J.-C., Carlos, S.M., Lazar, N.H., Mohan, R., Tillinghast, C., Biancalani, T., Fay, M.M., Earnshaw, B.A., and Haque, I.S.
(2024).
Building, benchmarking, and exploring perturbative maps of transcriptional and morphological data.
PLoS Comput.
Biol.
*20*, e1012463.](http://paperpile.com/b/2xFVvw/FTTuD)

52\.
[Caicedo, J.C., Arevalo, J., Piccioni, F., Bray, M.-A., Hartland, C.L., Wu, X., Brooks, A.N., Berger, A.H., Boehm, J.S., Carpenter, A.E., et al.
(2022).
Cell Painting predicts impact of lung cancer variants.
Mol.
Biol.
Cell *33*, ar49.](http://paperpile.com/b/2xFVvw/9l7S7)

53\.
[van Dijk, R., Arevalo, J., Babadi, M., Carpenter, A.E., and Singh, S. (2024).
Capturing cell heterogeneity in representations of cell populations for image-based profiling using contrastive learning.
PLoS Comput.
Biol.
*20*, e1012547.](http://paperpile.com/b/2xFVvw/sEdqd)

54\.
[Borges, N. (2005).
Tolcapone in Parkinson's disease: liver toxicity and clinical efficacy.
Expert Opin.
Drug Saf.
*4*, 69-73.](http://paperpile.com/b/2xFVvw/J0h9i)

55\.
[Kaufmann, P., Torok, M., Hanni, A., Roberts, P., Gasser, R., and Krahenbuhl, S. (2005).
Mechanisms of benzarone and benzbromarone-induced hepatic toxicity.
Hepatology *41*, 925-935.](http://paperpile.com/b/2xFVvw/2QusE)

56\.
[Sherman, S.I., Ringel, M.D., Smith, M.J., Kopelen, H.A., Zoghbi, W.A., and Ladenson, P.W.
(1997).
Augmented hepatic and skeletal thyromimetic effects of tiratricol in comparison with levothyroxine.
J. Clin.
Endocrinol.
Metab.
*82*, 2153-2158.](http://paperpile.com/b/2xFVvw/ZtvBG)

57\.
[Verhoeven, A.J., Kamer, P., Groen, A.K., and Tager, J.M.
(1985).
Effects of thyroid hormone on mitochondrial oxidative phosphorylation.
Biochem.
J. *226*, 183-192.](http://paperpile.com/b/2xFVvw/MfN8W)

58\.
[Williams, A.J., Grulke, C.M., Edwards, J., McEachran, A.D., Mansouri, K., Baker, N.C., Patlewicz, G., Shah, I., Wambaugh, J.F., Judson, R.S., et al.
(2017).
The CompTox Chemistry Dashboard: a community data resource for environmental chemistry.
J. Cheminform.
*9*, 61.](http://paperpile.com/b/2xFVvw/DumQ2)

59\.
[Geier, M.C., Chlebowski, A.C., Truong, L., Massey Simonich, S.L., Anderson, K.A., and Tanguay, R.L.
(2018).
Comparative developmental toxicity of a comprehensive suite of polycyclic aromatic hydrocarbons.
Arch.
Toxicol.
*92*, 571-586.](http://paperpile.com/b/2xFVvw/AVXwl)

60\.
[Harrill, J.A., Everett, L.J., Haggard, D.E., Sheffield, T., Bundy, J.L., Willis, C.M., Thomas, R.S., Shah, I., and Judson, R.S.
(2021).
High-throughput transcriptomics platform for screening environmental chemicals.
Toxicol.
Sci.
*181*, 68-89.](http://paperpile.com/b/2xFVvw/2qVy9)

61\.
[Liberman, E.A., Topaly, V.P., Tsofina, L.M., Jasaitis, A.A., and Skulachev, V.P.
(1969).
Mechanism of coupling of oxidative phosphorylation and the membrane potential of mitochondria.
Nature *222*, 1076-1078.](http://paperpile.com/b/2xFVvw/6d3PR)

62\.
[Armitage, J.M., Wania, F., and Arnot, J.A.
(2014).
Application of mass balance models and the chemical activity concept to facilitate the use of in vitro toxicity data for risk assessment.
Environ.
Sci.
Technol.
*48*, 9770-9779.](http://paperpile.com/b/2xFVvw/ZSohl)

63\.
[Armitage, J.M., Sangion, A., Parmar, R., Looky, A.B., and Arnot, J.A.
(2021).
Update and Evaluation of a High-Throughput In Vitro Mass Balance Distribution Model: IV-MBM EQP v2.0.
Toxics *9*. https://doi.org/](http://paperpile.com/b/2xFVvw/rg6pr)[10.3390/toxics9110315](http://dx.doi.org/10.3390/toxics9110315)[.](http://paperpile.com/b/2xFVvw/rg6pr)

64\.
[Chen, M., Suzuki, A., Thakkar, S., Yu, K., Hu, C., and Tong, W. (2016).
DILIrank: the largest reference drug list ranked by the risk for developing drug-induced liver injury in humans.
Drug Discov.
Today *21*, 648-653.](http://paperpile.com/b/2xFVvw/LltnY)

65\.
[Igarashi, Y., Nakatsu, N., Yamashita, T., Ono, A., Ohno, Y., Urushidani, T., and Yamada, H. (2015).
Open TG-GATEs: a large-scale toxicogenomics database.
Nucleic Acids Res.
*43*, D921-D927.](http://paperpile.com/b/2xFVvw/JDli7)

66\.
[Thakkar, S., Li, T., Liu, Z., Wu, L., Roberts, R., and Tong, W. (2020).
Drug-induced liver injury severity and toxicity (DILIst): binary classification of 1279 drugs by human hepatotoxicity.
Drug Discov.
Today *25*, 201-208.](http://paperpile.com/b/2xFVvw/TgolH)

67\.
[Feshuk, M., Kolaczkowski, L., Watford, S., and Paul Friedman, K. (2023).
ToxRefDB v2.1: update to curated in vivo study data in the Toxicity Reference Database.
Front.
Toxicol.
*5*, 1260305.](http://paperpile.com/b/2xFVvw/YW2Dr)

68\.
[Svoboda, D.L., Saddler, T., and Auerbach, S.S.
(2019).
An overview of national toxicology program's toxicogenomic applications: DrugMatrix and ToxFX.
In Challenges and Advances in Computational Chemistry and Physics (Springer International Publishing), pp. 141-157.](http://paperpile.com/b/2xFVvw/XRSFV)

69\.
[Seal, S., Williams, D.P., Hosseini-Gerami, L., Spjuth, O., and Bender, A. (2024).
Improved Early Detection of Drug-Induced Liver Injury by Integrating Predicted in vivo and in vitro Data. bioArxiv.](http://paperpile.com/b/2xFVvw/NPozc)

70\.
[Cimini, B.A., Chandrasekaran, S.N., Kost-Alimova, M., Miller, L., Goodale, A., Fritchman, B., Byrne, P., Garg, S., Jamali, N., Logan, D.J., et al.
(2023).
Optimizing the Cell Painting assay for image-based profiling.
Nat.
Protoc.
*18*, 1981-2013.](http://paperpile.com/b/2xFVvw/3SrUM)

71\.
[Singh, S., Bray, M.-A., Jones, T.R., and Carpenter, A.E.
(2014).
Pipeline for illumination correction of images for high-throughput microscopy: ILLUMINATION CORRECTION FOR HIGH-THROUGHPUT IMAGES.
J. Microsc.
*256*, 231-236.](http://paperpile.com/b/2xFVvw/T7Dx2)

72\.
[Pachitariu, M., and Stringer, C. (2022).
Cellpose 2.0: how to train your own model.
Nat.
Methods *19*, 1634-1641.](http://paperpile.com/b/2xFVvw/OXvQx)

73\.
[Weisbart, E., Tromans-Coia, C., Diaz-Rohrer, B., Stirling, D.R., Garcia-Fossa, F., Senft, R.A., Hiner, M.C., de Jesus, M.B., Eliceiri, K.W., and Cimini, B.A.
(2023).
CellProfiler plugins - An easy image analysis platform integration for containers and Python tools.
J. Microsc. https://doi.org/](http://paperpile.com/b/2xFVvw/nNLWc)[10.1111/jmi.13223](http://dx.doi.org/10.1111/jmi.13223)[.](http://paperpile.com/b/2xFVvw/nNLWc)

74\.
[McQuin, C., Goodman, A., Chernyshev, V., Kamentsky, L., Cimini, B.A., Karhohs, K.W., Doan, M., Ding, L., Rafelski, S.M., Thirstrup, D., et al.
(2018).
CellProfiler 3.0: Next-generation image processing for biology.
PLoS Biol.
*16*, e2005970.](http://paperpile.com/b/2xFVvw/xj8oL)

75\.
[Weisbart, E., Kumar, A., Arevalo, J., Carpenter, A.E., Cimini, B.A., and Singh, S. (2024).
Cell Painting Gallery: an open resource for image-based profiling.
Nat.
Methods *21*, 1775-1777.](http://paperpile.com/b/2xFVvw/hsX8C)

76\.
[Escher, B.I., Henneberger, L., Konig, M., Schlichting, R., and Fischer, F.C.
(2020).
Cytotoxicity burst?
Differentiating specific from nonspecific effects in Tox21 in vitro reporter gene assays.
Environ.
Health Perspect.
*128*, 77007.](http://paperpile.com/b/2xFVvw/uvFXc)

77\.
[Judson, R., Houck, K., Martin, M., Richard, A.M., Knudsen, T.B., Shah, I., Little, S., Wambaugh, J., Woodrow Setzer, R., Kothiya, P., et al.
(2016).
Editor's highlight: Analysis of the effects of cell stress and cytotoxicity on in vitro assay activity across a diverse chemical and assay space.
Toxicol.
Sci.
*152*, 323-339.](http://paperpile.com/b/2xFVvw/SRniu)

78\.
[Serrano, E., Chandrasekaran, S.N., Bunten, D., Brewer, K.I., Tomkinson, J., Kern, R., Bornholdt, M., Fleming, S., Pei, R., Arevalo, J., et al.
(2023).
Reproducible image-based profiling with Pycytominer. arXiv \[q-bio.QM\].](http://paperpile.com/b/2xFVvw/6WsvV)

79\.
[National Toxicology Program (2018).
NTP Research Report on National Toxicology Program Approach to Genomic Dose-Response Modeling. https://doi.org/](http://paperpile.com/b/2xFVvw/Hj8YM)[10.22427/NTP-RR-5](http://dx.doi.org/10.22427/NTP-RR-5)[.](http://paperpile.com/b/2xFVvw/Hj8YM)

80\.
[Ewald, J., Soufan, O., Xia, J., and Basu, N. (2021).
FastBMD: an online tool for rapid benchmark dose-response analysis of transcriptomics data.
Bioinformatics *37*, 1035-1036.](http://paperpile.com/b/2xFVvw/Zd6QD)

81\.
[Chen, T., and Guestrin, C. (2016).
XGBoost: A Scalable Tree Boosting System.
In Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining (ACM). https://doi.org/](http://paperpile.com/b/2xFVvw/iyfRv)[10.1145/2939672.2939785](http://dx.doi.org/10.1145/2939672.2939785)[.](http://paperpile.com/b/2xFVvw/iyfRv)
