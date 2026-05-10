# Merzifon 2023 Publication Evidence

This folder contains compact evidence from the Merzifon 2023 Sentinel-1
validation experiment used for the Dolphin2MintPy software article.

It is not a raw data archive. Large Sentinel-1 SLC, ISCE2, Dolphin, GeoTIFF,
and MintPy HDF5 products are intentionally excluded. The purpose of this
folder is to provide small, inspectable artifacts showing that:

1. Dolphin unwrapped/coherence/connect-component outputs were produced.
2. Dolphin2MintPy prepared the Dolphin outputs for MintPy.
3. MintPy loaded the converted stack and completed the SBAS workflow.
4. The scientific raster matrices were preserved during conversion.

## Experiment Scope

- Study area: Merzifon, Turkiye
- Input stack: 30 Sentinel-1 SLC acquisitions from 2023
- Interferograms validated: 84
- Raster size after AOI crop: 3134 x 10568 pixels
- Dolphin2MintPy validation target: Dolphin GeoTIFF outputs vs MintPy HDF5 datasets

## Key Results

Matrix equivalence between Dolphin GeoTIFF outputs and MintPy HDF5 datasets:

```text
unwrapPhase      rows=84  pass=84  max_abs_diff_max=0.0  exact_match_ratio_min=1.0
coherence        rows=84  pass=84  max_abs_diff_max=0.0  exact_match_ratio_min=1.0
connectComponent rows=84  pass=84  max_abs_diff_max=0.0  exact_match_ratio_min=1.0
```

MintPy SBAS workflow completion:

```text
Normal end of smallbaselineApp processing
MintPy run exit status: 0
has_timeseries: True
has_velocity: True
has_temporal_coherence: True
```

## Folder Contents

### `validation/`

Machine-readable summaries and pair-level validation outputs.

- `stage4n_dolphin_unwrap_qc_20260507.*`: Dolphin unwrap output QC.
- `stage5c_hdf5_attrs_before_fix_20260507.json`: MintPy HDF5 processor attributes before the post-load fix.
- `stage5c_hdf5_attrs_after_fix_20260507.json`: HDF5 processor attributes after Dolphin2MintPy patched them to `isce`.
- `stage5c_check_loaded_dataset_after_fix_20260507.txt`: MintPy `check_loaded_dataset` result after the processor fix.
- `stage5d_matrix_equivalence_summary_20260507.json`: Full-stack matrix-equivalence summary.
- `stage5d_matrix_equivalence_pairs_20260507.csv`: Pair-level matrix-equivalence results for 84 interferograms and three datasets.
- `stage6_mintpy_sbas_outputs_20260507.*`: MintPy SBAS output summary.

### `logs/`

Selected small logs for reproducibility and auditability.

- `ubuntu_stage4n_qc_dolphin_unwrap_outputs_20260507.log`
- `ubuntu_stage5c_fix_processor_after_load_data_20260507.log`
- `ubuntu_stage5d_matrix_equivalence_nodatafix_20260507.log`
- `stage6_mintpy_success_excerpt_20260507.txt`

The full MintPy SBAS terminal log is not included because it is large and
mostly routine progress output. The summary and excerpt record the completion
status and generated output products.

### `figures/`

Publication-oriented evidence figures in PNG and PDF formats.

- `fig04a_representative_tile_dolphin_vs_mintpy_300dpi.*`
- `fig04b_absolute_difference_tile_300dpi.*`
- `fig04c_full_stack_validation_matrix_300dpi.*`
- `fig04d_per_pair_equivalence_statistics_300dpi.*`
- `fig04e_conncomp_nodata_diagnostic_300dpi.*`

The main manuscript figure set uses `fig04a`, `fig04b`, and `fig04d`.
`fig04e` is retained here as a QC/diagnostic figure explaining why
`connectComponent` comparisons were performed after masking nodata values.

### `scripts/`

Figure-generation scripts used to create the included validation figures.
The scripts retain local experiment paths from the original Windows/WSL
workspace and are included for transparency, not as general-purpose package
entry points.

## How This Evidence Should Be Used

For the article, this folder supports a short reproducibility statement: the
public repository includes compact logs, validation summaries, and figures
showing successful MintPy product generation from Dolphin outputs prepared by
Dolphin2MintPy.

The primary scientific evidence remains the matrix-equivalence validation:
Dolphin GeoTIFF raster values and MintPy HDF5 datasets are pixel-wise identical
for `unwrapPhase`, `coherence`, and `connectComponent` over all 84 validated
interferograms.

For the manuscript, the `connectComponent` nodata handling can be summarized
with one sentence: `connectComponent comparisons were performed after masking
nodata values to avoid representation-dependent integer differences.`
