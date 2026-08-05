# Supplemental Figure S1 source-image reproduction

Target: `SFIG-1`.

The camera-ready supplement identifies plate 41002889, well L12, site 6 as a randomly selected DMSO control.
`paper/render_sfig1.py` resolves that identity against the downloaded Zenodo image index and requires exactly one source URI for each of the DNA, ER, AGP, RNA, and Mito channels.
All five rows resolve to batch `prod_26` and to distinct public TIFFs under the Cell Painting Gallery.

The script downloads those TIFFs with atomic replacement, records their byte counts and SHA-256 hashes, and renders the five grayscale channels plus the same composite mapping used by `Plot_images.ipynb`.
The target metadata resolve only to DMSO.
This reproduces the published field identity and the substantive image content without requiring the original notebook's missing directory setup.

The inventory statement does not reproduce literally from the current source index.
After joining the image index to metadata and counting distinct plate, well, and site fields, the current inputs contain 318,828 fields, including 72,519 DMSO fields.
The paper reports 191,754 and 43,641.
The published values equal nine fields for each of 21,306 processed DINO wells and nine fields for each of 4,849 DMSO wells, whereas the image index contains as many as 15 sites per well.
No tracked method or index field identifies the nine-site inclusion rule, so the reproduction reports both count layers and does not invent a filter.

Run this target directly after downloading the Zenodo inputs:

```bash
uv run paper/render_sfig1.py --output-dir paper/runs/figure-s1
```

The end-to-end runner invokes the same producer inside its isolated snapshot and stores the PNG and JSON evidence under `artifacts/sfig1/`.

Outcome: `reproduced-with-deviation`.
The exact field and channel identity reproduce, while the published inventory counts require an undocumented nine-site selection rule.
