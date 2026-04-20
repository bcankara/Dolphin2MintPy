# Architecture

## Overview

dolphin2mintpy is a metadata bridge that converts Dolphin InSAR GeoTIFF outputs
into a format MintPy can ingest. It does **not** modify any raster data — it only
generates `.rsc` (ROI_PAC-style) sidecar metadata files.

## Module Dependency Graph

```
cli.py                  ← Entry point, argument parsing
  ├── gui.py            ← Tkinter desktop interface (default command)
  │     ├── settings.py ← Load/save dolphin2mintpy_settings.json
  │     ├── prepare.py  ← Core .rsc generation engine
  │     │     ├── metadata.py   ← ISCE2 XML, GDAL, baseline parsing
  │     │     └── constants.py  ← Sentinel-1 defaults, RSC templates
  │     └── config.py   ← MintPy .cfg template generation
  └── (prepare / generate-config / info subcommands call prepare.py and config.py directly)
```

## Data Flow

```
                     ┌──────────────────┐
                     │  User Input      │
                     │  (GUI / CLI)     │
                     └────────┬─────────┘
                              │
                    ┌─────────▼──────────┐
                    │  metadata.py       │
                    │  ┌───────────────┐ │
                    │  │ ISCE2 XML     │ │  radar wavelength, pixel size,
                    │  │ parser        │ │  starting range, PRF, orbit dir
                    │  └───────────────┘ │
                    │  ┌───────────────┐ │
                    │  │ Baseline      │ │  perpendicular baselines
                    │  │ parser        │ │  (Bperp per date pair)
                    │  └───────────────┘ │
                    │  ┌───────────────┐ │
                    │  │ GDAL raster   │ │  WIDTH, LENGTH, geotransform
                    │  │ reader        │ │
                    │  └───────────────┘ │
                    └─────────┬──────────┘
                              │
                    ┌─────────▼──────────┐
                    │  prepare.py        │
                    │                    │  For each GeoTIFF:
                    │  .unw.tif → .rsc   │  1. Read GDAL dimensions
                    │  .cor.tif → .rsc   │  2. Extract dates from filename
                    │  .conncomp → .rsc  │  3. Look up Bperp
                    │  geometry → .rsc   │  4. Write .rsc sidecar
                    └─────────┬──────────┘
                              │
                    ┌─────────▼──────────┐
                    │  config.py         │
                    │                    │  Generate mintpy_config.txt
                    │  processor = hyp3  │  with correct glob patterns
                    │  load paths        │  pointing to .rsc-enriched data
                    └─────────┬──────────┘
                              │
                    ┌─────────▼──────────┐
                    │  Ready for MintPy  │
                    │  smallbaselineApp  │
                    └────────────────────┘
```

## Key Design Decisions

### Why `PROCESSOR=hyp3`?

MintPy routes data reading through processor-specific code paths. The `hyp3`
processor uses `readfile.read_gdal_vrt()`, which correctly handles multi-band
compressed GeoTIFFs. This is the most compatible path for Dolphin's output format.

### Why not modify MintPy directly?

1. **Separation of concerns**: dolphin2mintpy can evolve independently
2. **No fork maintenance burden**: users don't need a patched MintPy
3. **Standards-based**: uses the existing `.rsc` + `PROCESSOR` mechanism
4. **Future-proof**: when MintPy adds native Dolphin support, this package
   becomes optional (but remains useful for custom workflows)

### Why `.rsc` sidecars instead of HDF5?

MintPy's `load_data` step converts everything to HDF5 internally.
The `.rsc` files are only needed for the initial data ingestion phase.
They are lightweight text files (~500 bytes each) that don't duplicate
any raster data.
