# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Sensing-time and heading metadata** in every `.rsc` sidecar:
  - `HEADING` is always written as a numeric value (degrees clockwise
    from north). Uses the ISCE2 XML value when present, otherwise
    falls back to the Sentinel-1 nominal heading implied by
    `passDirection` (ASCENDING ≈ -12.6°, DESCENDING ≈ -167.4°). This
    unblocks MintPy's `geocode` step (pyresample
    `radius_of_influence`).
  - `CENTER_LINE_UTC`, `startUTC`, `stopUTC` are derived from
    `sensingStart` / `sensingStop` in the reference XML when
    available. `CENTER_LINE_UTC` is required by
    `correct_troposphere` (pyaps3) to pick the right ERA5 hour.
  - `metadata.parse_isce_xml` now reads `sensingStart`, `sensingStop`
    and an optional `heading` property, computing the derived values
    above. New public helpers `S1_HEADING_ASCENDING`,
    `S1_HEADING_DESCENDING` and `_parse_isce_datetime`.
  - Removes the need for the previous standalone
    `fix_mintpy_metadata.py` script (deleted): MintPy's `load_data`
    now propagates these fields straight into `ifgramStack.h5`,
    `geometryRadar.h5` and `timeseries.h5`.
- **Two-stage workflow** for Dolphin -> MintPy integration:
  - Stage 1 (`Prepare`) writes `.rsc` sidecars + `mintpy_config.txt`.
  - Stage 2 (`Post-Load Fix`) patches the `PROCESSOR` HDF5 attribute
    from `hyp3` to `isce` on `ifgramStack.h5` and `geometryRadar.h5`
    after MintPy's `load_data` step. This fixes
    `AttributeError: Unknown InSAR processor: hyp3 to locate look up table!`.
- New `dolphin2mintpy.postprocess` module with `fix_processor_attribute`
  and `verify_inputs_dir` helpers (exposed on the public API).
- CLI subcommand `dolphin2mintpy fix-processor` with `--verify-only`,
  `--dry-run`, `--from`, `--to`, `--targets`, `--skip-lookup-check`.
- GUI is now a two-tab notebook: `1. Prepare (pre load_data)` and
  `2. Post-Load Fix`. The second tab has a prominent warning banner
  explaining that it must run *after* MintPy's `load_data` step, plus
  `Verify` and `Apply fix` buttons with their own log pane.
- `h5py` added to runtime dependencies.
- Dedicated GUI / CLI fields for every MintPy geometry and lookup path:
  `demFile`, `incAngleFile`, `azAngleFile`, `lookupYFile`, `lookupXFile`,
  `waterMaskFile`. The lookup table fields specifically prevent MintPy's
  `No lookup table (longitude or rangeCoord) found` failure in radar
  geometry pipelines.
- `mintpy.load.processor` is now a first-class option (GUI dropdown and
  `--processor` flag). Default is `isce` to match hybrid ISCE2/Dolphin
  stacks; `hyp3` is also supported.
- Geometry directory picker auto-populates DEM and lookup file fields
  from the expected ISCE2 topsStack filenames (`hgt.rdr.full`,
  `los.rdr.full`, `lat.rdr.full`, `lon.rdr.full`).
- `generate_mintpy_config` now emits `mintpy.project.name`,
  `mintpy.load.metaFile`, `mintpy.load.baselineDir`, `reference.yx`,
  and the full `networkInversion.*` block (weightFunc, maskDataset,
  minTempCoh).

### Changed
- CLI `generate-config` gained `--inc-angle-file`, `--az-angle-file`,
  `--lookup-y-file`, `--lookup-x-file`, `--water-mask-file` and
  `--processor` arguments.
- Persisted settings now include the new per-file paths so they are
  restored across runs.

## [0.1.0] - 2026-04-20

### Added
- Initial public release.
- **Linux desktop GUI** (`dolphin2mintpy` / `dolphin2mintpy gui`):
  - Tkinter-based form with native directory and file pickers for every input path.
  - Per-field `?` help tooltips that appear on hover.
  - Reference-date auto-detection from the baseline directory.
  - `Load settings` / `Save settings` buttons backed by `dolphin2mintpy_settings.json`.
  - Progress bar and scrollable log driven by a background worker thread so the UI stays responsive.
- **Scriptable CLI** with `prepare`, `generate-config`, and `info` subcommands.
- Core `.rsc` sidecar generation for unwrapped phase, coherence, and connected component rasters.
- Geometry (`DEM`, incidence angle, azimuth angle) `.rsc` support.
- ISCE2 reference XML metadata parser (wavelength, heading, incidence, pixel size, PRF).
- ISCE2 baseline directory parser (perpendicular baselines per date pair).
- GDAL GeoTIFF metadata reader for raster dimensions and geotransform.
- MintPy `smallbaselineApp.cfg` template generator using `PROCESSOR=hyp3`.
- JSON-based settings persistence (`dolphin2mintpy_settings.json`).
- Pytest suite covering CLI dispatch, metadata parsing, and stack preparation.
- GitHub Actions CI pipeline (lint + test matrix on Python 3.9–3.12 + package build).
