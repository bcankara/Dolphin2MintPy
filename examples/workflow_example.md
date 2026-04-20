# Example Workflow

This guide demonstrates how to use **dolphin2mintpy** to bridge Dolphin InSAR outputs into MintPy for time-series analysis.

## Prerequisites

- ISCE2 topsStack processing completed (coregistered SLCs + baselines + geometry)
- Dolphin phase linking completed (wrapped interferograms)
- SNAPHU phase unwrapping completed (`*.unw.tif`, `*.cor.tif`, `*.conncomp.tif`)

## Directory Structure (Before)

```
project/
├── unwrapped/
│   ├── 20240907_20241001.unw.tif
│   ├── 20240907_20241001.unw.conncomp.tif
│   ├── 20241001_20241013.unw.tif
│   └── ...
├── interferograms/
│   ├── 20240907_20241001.int.cor.tif
│   ├── 20241001_20241013.int.cor.tif
│   └── ...
├── baselines/
│   ├── 20240919_20240907/
│   │   └── 20240919_20240907.txt
│   ├── 20240919_20241001/
│   │   └── 20240919_20241001.txt
│   └── ...
└── reference/
    └── IW2.xml
```

## Step 1: Run Dolphin2MintPy

### Option A: Interactive Wizard

```bash
dolphin2mintpy
```

Follow the prompts — the wizard will auto-detect parameters where possible.

### Option B: Non-Interactive

```bash
dolphin2mintpy prepare \
    --unw-dir ./unwrapped \
    --cor-dir ./interferograms \
    --baseline-dir ./baselines \
    --ref-xml ./reference/IW2.xml \
    --ref-date 20240919

dolphin2mintpy generate-config \
    --work-dir ./mintpy \
    --unw-dir ./unwrapped \
    --cor-dir ./interferograms
```

## Step 2: Verify

```bash
dolphin2mintpy info --unw-dir ./unwrapped --baseline-dir ./baselines
```

Check that `.rsc` files were created alongside each GeoTIFF:

```
unwrapped/
├── 20240907_20241001.unw.tif
├── 20240907_20241001.unw.tif.rsc     ← generated
├── 20240907_20241001.unw.conncomp.tif
├── 20240907_20241001.unw.conncomp.tif.rsc  ← generated
└── ...
```

## Step 3: Run MintPy

```bash
cd mintpy
smallbaselineApp.py mintpy_config.txt
```

MintPy will now correctly load the Dolphin GeoTIFFs through its GDAL reading path.

## Directory Structure (After)

```
project/
├── unwrapped/
│   ├── 20240907_20241001.unw.tif
│   ├── 20240907_20241001.unw.tif.rsc          ← NEW
│   └── ...
├── interferograms/
│   ├── 20240907_20241001.int.cor.tif
│   ├── 20240907_20241001.int.cor.tif.rsc      ← NEW
│   └── ...
├── mintpy/
│   ├── mintpy_config.txt                       ← NEW
│   ├── inputs/
│   │   └── ifgramStack.h5                     ← MintPy output
│   └── ...
└── ...
```
