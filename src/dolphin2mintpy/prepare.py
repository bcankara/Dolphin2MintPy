"""
Core RSC sidecar generation for Dolphin GeoTIFF outputs.

Transforms Dolphin-produced GeoTIFF files into MintPy-compatible datasets
by generating ROI_PAC-style .rsc metadata sidecar files.
"""

import logging
from pathlib import Path

from dolphin2mintpy.constants import (
    DEFAULT_ALOOKS,
    DEFAULT_ANTENNA_SIDE,
    DEFAULT_EARTH_RADIUS,
    DEFAULT_GEOMETRY_MODE,
    DEFAULT_RLOOKS,
    DEFAULT_SAT_HEIGHT,
    GEOMETRY_MODES,
    MINTPY_PROCESSOR,
    RSC_GEO_BLOCK,
    RSC_IFG_EXTRA,
    RSC_TEMPLATE_BASE,
    S1_AZIMUTH_PIXEL_SIZE,
    S1_RANGE_PIXEL_SIZE,
    S1_WAVELENGTH,
)
from dolphin2mintpy.metadata import (
    compute_bperp_pair,
    extract_dates_from_filename,
    parse_baselines,
    parse_gdal_metadata,
    parse_isce_xml,
)

logger = logging.getLogger(__name__)


def _resolve_geocoded(gdal_meta, geometry_mode):
    """Decide whether to emit geocoded metadata given the requested mode.

    Parameters
    ----------
    gdal_meta : dict
        Metadata dict returned by ``parse_gdal_metadata``.
    geometry_mode : str
        One of ``"auto"``, ``"radar"`` or ``"geo"``.

    Returns
    -------
    (bool, str)
        ``(is_geocoded, reason)`` — the effective decision plus the
        reason string to be logged.
    """
    if geometry_mode not in GEOMETRY_MODES:
        raise ValueError(
            f"geometry_mode must be one of {GEOMETRY_MODES}, got {geometry_mode!r}"
        )

    detected = bool(gdal_meta.get("IS_GEOCODED", False))
    detected_reason = gdal_meta.get("GEOCODED_REASON", "no detection info")

    if geometry_mode == "auto":
        return detected, f"auto ({detected_reason})"
    if geometry_mode == "radar":
        return False, "radar (user override)"
    # "geo"
    return True, "geo (user override)"


def prepare_rsc(
    tif_path,
    date1=None,
    date2=None,
    bperp=0.0,
    radar_params=None,
    file_type=".unw",
    is_interferogram=True,
    geometry_mode=DEFAULT_GEOMETRY_MODE,
):
    """Generate a .rsc sidecar file for a single GeoTIFF.

    Parameters
    ----------
    tif_path : str or Path
        Path to the GeoTIFF file.
    date1 : str, optional
        First acquisition date (YYYYMMDD). Required for interferograms.
    date2 : str, optional
        Second acquisition date (YYYYMMDD). Required for interferograms.
    bperp : float
        Perpendicular baseline in meters.
    radar_params : dict, optional
        Radar parameters from ISCE2 XML. If None, defaults are used.
    file_type : str
        File type label for the .rsc (e.g., '.unw', '.cor', '.conncomp').
    is_interferogram : bool
        If True, includes DATE12 and baseline fields.
    geometry_mode : {"auto", "radar", "geo"}
        Controls how the geotransform block is written:
          * ``auto``  — infer from the GeoTIFF (projection + geotransform)
          * ``radar`` — force radar geometry (no X_FIRST / Y_FIRST lines)
          * ``geo``   — force geocoded output even if detection says radar

    Returns
    -------
    Path
        Path to the generated .rsc file.

    Raises
    ------
    FileNotFoundError
        If the GeoTIFF does not exist.
    ValueError
        If ``geometry_mode`` is not one of the supported values.
    """
    tif_path = Path(tif_path)
    if not tif_path.exists():
        raise FileNotFoundError(f"GeoTIFF not found: {tif_path}")

    gdal_meta = parse_gdal_metadata(tif_path)
    width = int(gdal_meta["WIDTH"])
    length = int(gdal_meta["LENGTH"])

    is_geocoded, reason = _resolve_geocoded(gdal_meta, geometry_mode)
    logger.debug(
        "Geometry decision for %s: geocoded=%s (%s)",
        tif_path.name, is_geocoded, reason,
    )

    rp = radar_params or {}
    wavelength = float(rp.get("radarwavelength", S1_WAVELENGTH))
    range_psize = float(rp.get("rangepixelsize", S1_RANGE_PIXEL_SIZE))
    starting_range = float(rp.get("startingrange", 800000.0))
    prf = float(rp.get("prf", 486.486))
    orbit_dir = rp.get("passdirection", "ASCENDING")

    rsc_content = RSC_TEMPLATE_BASE.format(
        width=width,
        length=length,
        xmax=width - 1,
        ymax=length - 1,
        wavelength=wavelength,
        range_pixel_size=range_psize,
        azimuth_pixel_size=float(rp.get("azimuthpixelsize", S1_AZIMUTH_PIXEL_SIZE)),
        starting_range=starting_range,
        prf=prf,
        earth_radius=float(rp.get("earthradius", DEFAULT_EARTH_RADIUS)),
        height=float(rp.get("height", DEFAULT_SAT_HEIGHT)),
        orbit_direction=orbit_dir,
        processor=MINTPY_PROCESSOR,
        antenna_side=DEFAULT_ANTENNA_SIDE,
        alooks=int(rp.get("alooks", DEFAULT_ALOOKS)),
        rlooks=int(rp.get("rlooks", DEFAULT_RLOOKS)),
        number_bands=gdal_meta.get("NUMBER_BANDS", "1"),
        file_type=file_type,
        data_type=gdal_meta.get("DATA_TYPE", "float32"),
    )

    if is_geocoded:
        x_step = float(gdal_meta.get("X_STEP", 1.0))
        y_step = float(gdal_meta.get("Y_STEP", -1.0))
        # Heuristic: |step| < 1 degree → lon/lat grid; otherwise metres (UTM)
        x_unit = "degree" if abs(x_step) < 1.0 else "meter"
        y_unit = "degree" if abs(y_step) < 1.0 else "meter"
        rsc_content += RSC_GEO_BLOCK.format(
            x_first=gdal_meta.get("X_FIRST", "0.0"),
            y_first=gdal_meta.get("Y_FIRST", "0.0"),
            x_step=gdal_meta.get("X_STEP", "1.0"),
            y_step=gdal_meta.get("Y_STEP", "-1.0"),
            x_unit=x_unit,
            y_unit=y_unit,
        )

    if is_interferogram and date1 and date2:
        date12 = f"{date1[2:]}-{date2[2:]}"
        rsc_content += RSC_IFG_EXTRA.format(
            date12=date12,
            bperp=f"{bperp:.4f}",
        )

    rsc_path = Path(str(tif_path) + ".rsc")
    with open(rsc_path, "w") as f:
        f.write(rsc_content)

    logger.debug("Generated .rsc: %s (mode=%s)", rsc_path.name, geometry_mode)
    return rsc_path


def prepare_stack(
    unw_dir,
    cor_dir=None,
    conncomp_dir=None,
    geometry_dir=None,
    baseline_dir=None,
    ref_xml=None,
    ref_date=None,
    progress_callback=None,
    geometry_mode=DEFAULT_GEOMETRY_MODE,
):
    """Generate .rsc sidecar files for an entire interferogram stack.

    Parameters
    ----------
    unw_dir : str or Path
        Directory containing unwrapped phase GeoTIFFs (*.unw.tif).
    cor_dir : str or Path, optional
        Directory containing coherence GeoTIFFs (*.cor.tif or *.int.cor.tif).
        Defaults to unw_dir.
    conncomp_dir : str or Path, optional
        Directory containing connected component GeoTIFFs (*.conncomp.tif).
        Defaults to unw_dir.
    geometry_dir : str or Path, optional
        Directory containing geometry GeoTIFFs (DEM, incidence, azimuth).
    baseline_dir : str or Path, optional
        ISCE2 baselines directory for Bperp computation.
    ref_xml : str or Path, optional
        ISCE2 reference XML file for radar parameters.
    ref_date : str, optional
        Reference (super-master) date in YYYYMMDD format.
    progress_callback : callable, optional
        Function called with (current, total) for progress reporting.
    geometry_mode : {"auto", "radar", "geo"}
        Controls whether .rsc files are written as radar or geocoded.
        ``auto`` inspects the GeoTIFF CRS and geotransform; ``radar`` and
        ``geo`` force the corresponding layout regardless of detection.

    Returns
    -------
    dict
        Summary with keys: ``rsc_written``, ``skipped``, ``errors``,
        ``details`` and ``geometry_mode`` (the effective mode for the run).
    """
    if geometry_mode not in GEOMETRY_MODES:
        raise ValueError(
            f"geometry_mode must be one of {GEOMETRY_MODES}, got {geometry_mode!r}"
        )

    unw_dir = Path(unw_dir)
    cor_dir = Path(cor_dir) if cor_dir else unw_dir
    conncomp_dir = Path(conncomp_dir) if conncomp_dir else unw_dir

    radar_params = {}
    if ref_xml:
        try:
            radar_params = parse_isce_xml(ref_xml)
        except Exception as e:
            logger.warning("Could not parse reference XML: %s. Using defaults.", e)

    baselines = {}
    if baseline_dir and ref_date:
        try:
            baselines = parse_baselines(baseline_dir, ref_date)
        except Exception as e:
            logger.warning("Could not parse baselines: %s. Using Bperp=0.", e)

    # Collect all files to process
    file_groups = []

    # Unwrapped phase files
    unw_files = _find_tif_files(unw_dir, ["*.unw.tif"])
    for f in unw_files:
        file_groups.append((f, ".unw", True))

    # Coherence files
    cor_patterns = ["*.int.cor.tif", "*.cor.tif"]
    cor_files = _find_tif_files(cor_dir, cor_patterns)
    for f in cor_files:
        file_groups.append((f, ".cor", True))

    # Connected component files
    conn_files = _find_tif_files(conncomp_dir, ["*.unw.conncomp.tif", "*.conncomp.tif"])
    for f in conn_files:
        file_groups.append((f, ".conncomp", True))

    # Geometry files
    if geometry_dir:
        geom_dir = Path(geometry_dir)
        if geom_dir.exists():
            geom_patterns = {
                "*.dem.tif": ".dem",
                "*dem*.tif": ".dem",
                "*height*.tif": ".dem",
                "*inc*.tif": ".inc",
                "*incidence*.tif": ".inc",
                "*lv_theta*.tif": ".inc",
                "*az*.tif": ".az",
                "*azimuth*.tif": ".az",
                "*lv_phi*.tif": ".az",
                "*shadow*.tif": ".shadowMask",
                "*water*.tif": ".waterMask",
            }
            for pattern, ftype in geom_patterns.items():
                for f in sorted(geom_dir.glob(pattern)):
                    file_groups.append((f, ftype, False))

    total = len(file_groups)
    result = {
        "rsc_written": 0,
        "skipped": 0,
        "errors": [],
        "details": [],
        "geometry_mode": geometry_mode,
    }

    if total == 0:
        logger.warning("No GeoTIFF files found to process.")
        return result

    _log_geometry_decision(file_groups[0][0], geometry_mode)
    _validate_geometry_consistency(file_groups[0][0], geometry_dir, geometry_mode)

    logger.info("Processing %d files (geometry_mode=%s)...", total, geometry_mode)

    for i, (fpath, file_type, is_ifg) in enumerate(file_groups):
        try:
            dates = extract_dates_from_filename(fpath.name)
            d1, d2, bperp = None, None, 0.0

            if dates:
                d1, d2 = dates
                bp = compute_bperp_pair(baselines, d1, d2)
                if bp is not None:
                    bperp = bp
                elif is_ifg:
                    logger.debug("No baseline for %s, using Bperp=0.", fpath.name)

            rsc_path = prepare_rsc(
                tif_path=fpath,
                date1=d1,
                date2=d2,
                bperp=bperp,
                radar_params=radar_params,
                file_type=file_type,
                is_interferogram=is_ifg,
                geometry_mode=geometry_mode,
            )

            result["rsc_written"] += 1
            result["details"].append({"file": str(fpath.name), "rsc": str(rsc_path.name)})

        except Exception as e:
            result["errors"].append({"file": str(fpath.name), "error": str(e)})
            logger.error("Error processing %s: %s", fpath.name, e)

        if progress_callback:
            progress_callback(i + 1, total)

    logger.info(
        "Complete: %d .rsc written, %d errors.",
        result["rsc_written"],
        len(result["errors"]),
    )
    return result


def _log_geometry_decision(sample_tif, geometry_mode):
    """Log the effective geometry decision using the first file as reference.

    Helps the user understand why the pipeline produced radar- or
    geocoded-flavoured .rsc sidecars — the root cause of a common
    MintPy ``geometryGeo.h5 not found`` failure.
    """
    try:
        meta = parse_gdal_metadata(sample_tif)
    except Exception as e:
        logger.warning("Could not probe %s for geometry detection: %s", sample_tif, e)
        return

    effective, reason = _resolve_geocoded(meta, geometry_mode)
    override_hint = ""
    if geometry_mode == "auto":
        override_hint = " (override with geometry_mode='radar' or 'geo' if incorrect)"

    logger.info(
        "Detected geometry: %s — %s%s",
        "GEOCODED" if effective else "RADAR",
        reason,
        override_hint,
    )


def _validate_geometry_consistency(sample_tif, geometry_dir, geometry_mode):
    """Warn when stack geometry and geometry_dir contents look mismatched.

    The goal is to surface the "ifgramStack is radar but geometry files
    are geocoded" (or vice-versa) mismatch before MintPy's
    ``check_loaded_dataset`` aborts the run with an obscure
    ``FileNotFoundError``.
    """
    if not geometry_dir:
        return

    geom_dir = Path(geometry_dir)
    if not geom_dir.exists():
        return

    try:
        stack_meta = parse_gdal_metadata(sample_tif)
    except Exception:
        return

    stack_effective, _ = _resolve_geocoded(stack_meta, geometry_mode)

    geom_candidates = [
        *geom_dir.glob("*.tif"),
        *geom_dir.glob("*dem*.tif"),
        *geom_dir.glob("*inc*.tif"),
    ]
    if not geom_candidates:
        return

    try:
        geom_meta = parse_gdal_metadata(geom_candidates[0])
    except Exception:
        return

    geom_is_geocoded = bool(geom_meta.get("IS_GEOCODED", False))

    if stack_effective != geom_is_geocoded:
        logger.warning(
            "Geometry mismatch: stack is %s but %s is %s. "
            "MintPy check_loaded_dataset will likely fail — re-run with a "
            "matching geometry_mode or resample the geometry files first.",
            "GEOCODED" if stack_effective else "RADAR",
            geom_candidates[0].name,
            "GEOCODED" if geom_is_geocoded else "RADAR",
        )


def _find_tif_files(directory, patterns):
    """Find GeoTIFF files matching any of the given glob patterns.

    Uses a set to avoid duplicates when patterns overlap.

    Parameters
    ----------
    directory : Path
        Directory to search.
    patterns : list of str
        Glob patterns to match.

    Returns
    -------
    list of Path
        Sorted list of unique matching file paths.
    """
    if not directory.exists():
        return []

    found = set()
    for pattern in patterns:
        for f in directory.glob(pattern):
            found.add(f)

    return sorted(found)
