# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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
