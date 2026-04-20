# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
