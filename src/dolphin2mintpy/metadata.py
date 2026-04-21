"""
Metadata extraction from various InSAR data sources.

Supports:
  - ISCE2 topsStack reference XML files (IW*.xml)
  - ISCE2 baseline directory structure
  - GDAL GeoTIFF metadata (raster dimensions + geotransform)
  - Date extraction from Dolphin-style filenames (YYYYMMDD_YYYYMMDD)
"""

import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path

logger = logging.getLogger(__name__)

# Regex for extracting date pairs from filenames
DATE_PAIR_PATTERN = re.compile(r"(\d{8})_(\d{8})")


def parse_isce_xml(xml_path):
    """Extract radar parameters from an ISCE2 reference XML file.

    Reads properties such as radar wavelength, range pixel size,
    starting range, azimuth time interval, and pass direction
    from the ISCE2 XML schema (without requiring iscesys).

    Parameters
    ----------
    xml_path : str or Path
        Path to the ISCE2 reference XML file (e.g., IW2.xml).

    Returns
    -------
    dict
        Dictionary with keys: radarwavelength, rangepixelsize,
        startingrange, azimuthtimeinterval, passdirection, prf.

    Raises
    ------
    FileNotFoundError
        If the XML file does not exist.
    xml.etree.ElementTree.ParseError
        If the XML is malformed.
    """
    xml_path = Path(xml_path)
    if not xml_path.exists():
        raise FileNotFoundError(f"ISCE2 reference XML not found: {xml_path}")

    tree = ET.parse(xml_path)
    root = tree.getroot()

    wanted = {
        "radarwavelength",
        "rangepixelsize",
        "startingrange",
        "azimuthtimeinterval",
        "passdirection",
        "prf",
    }

    vals = {}
    for prop in root.iter("property"):
        key = prop.attrib.get("name", "").lower()
        if key in wanted and key not in vals:
            v = prop.find("value")
            if v is not None and v.text:
                vals[key] = v.text.strip()

    # Derive PRF from azimuth time interval if not explicitly present
    if "prf" not in vals and "azimuthtimeinterval" in vals:
        try:
            az_time = float(vals["azimuthtimeinterval"])
            if az_time > 0:
                vals["prf"] = str(1.0 / az_time)
        except (ValueError, ZeroDivisionError):
            pass

    logger.info(
        "Parsed ISCE2 XML: wavelength=%s, range_ps=%s, starting_range=%s, prf=%s, pass=%s",
        vals.get("radarwavelength", "N/A"),
        vals.get("rangepixelsize", "N/A"),
        vals.get("startingrange", "N/A"),
        vals.get("prf", "N/A"),
        vals.get("passdirection", "N/A"),
    )

    return vals


# Geotransform returned by GDAL for a raster that has *no* georeference.
# We use this to distinguish a real geocoded product from a Dolphin radar
# geometry GeoTIFF whose geotransform GDAL fills with identity values.
_DEFAULT_GT = (0.0, 1.0, 0.0, 0.0, 0.0, 1.0)


def _is_default_geotransform(gt, tol=1e-9):
    """Return True when the geotransform matches GDAL's identity default."""
    if gt is None or len(gt) < 6:
        return True
    return all(abs(float(gt[i]) - _DEFAULT_GT[i]) < tol for i in range(6))


def _detect_geocoded(projection_wkt, geotransform):
    """Decide whether a raster is truly geocoded.

    A product is considered geocoded only when:
      * it has a non-empty projection string (``GetProjection``), **and**
      * its geotransform is not the GDAL identity default (0, 1, 0, 0, 0, 1).

    Either condition alone can be misleading (Dolphin radar-geometry
    GeoTIFFs carry the default geotransform but no projection; some tools
    strip the CRS while keeping a valid geotransform), so we require both.

    Parameters
    ----------
    projection_wkt : str
        WKT projection string from ``GDALDataset.GetProjection``.
    geotransform : sequence of float
        Six-element geotransform from ``GDALDataset.GetGeoTransform``.

    Returns
    -------
    (bool, str)
        Tuple of ``(is_geocoded, reason)``. The reason string is suitable
        for logging and debugging.
    """
    has_proj = bool(projection_wkt and projection_wkt.strip())
    has_gt = not _is_default_geotransform(geotransform)

    if has_proj and has_gt:
        return True, "projection present and non-identity geotransform"
    if has_proj and not has_gt:
        return False, "projection present but identity geotransform (treated as radar)"
    if not has_proj and has_gt:
        return False, "non-identity geotransform but no projection (treated as radar)"
    return False, "no projection and identity geotransform"


def parse_gdal_metadata(tif_path):
    """Read raster dimensions, geotransform and geocoded flag from GDAL.

    Parameters
    ----------
    tif_path : str or Path
        Path to the GeoTIFF file.

    Returns
    -------
    dict
        Dictionary with keys: WIDTH, LENGTH, NUMBER_BANDS,
        X_FIRST, Y_FIRST, X_STEP, Y_STEP, DATA_TYPE,
        IS_GEOCODED, GEOCODED_REASON, PROJECTION_WKT.

        ``IS_GEOCODED`` is a Python bool and ``GEOCODED_REASON`` is a
        short human-readable explanation of the decision, useful for
        log output and debugging.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    RuntimeError
        If GDAL cannot open the file.
    """
    try:
        from osgeo import gdal
    except ImportError:
        raise ImportError(
            "GDAL is required but not installed. "
            "Install it with: conda install -c conda-forge gdal"
        )

    tif_path = Path(tif_path)
    if not tif_path.exists():
        raise FileNotFoundError(f"GeoTIFF not found: {tif_path}")

    gdal.UseExceptions()
    ds = gdal.Open(str(tif_path))
    if ds is None:
        raise RuntimeError(f"GDAL failed to open: {tif_path}")

    width = ds.RasterXSize
    length = ds.RasterYSize
    num_bands = ds.RasterCount

    gt = ds.GetGeoTransform()  # (x_origin, x_step, 0, y_origin, 0, y_step)
    projection = ds.GetProjection() or ""

    is_geocoded, reason = _detect_geocoded(projection, gt)

    x_first = gt[0] if gt else 0.0
    y_first = gt[3] if gt else 0.0
    x_step = gt[1] if gt else 1.0
    y_step = gt[5] if gt else 1.0

    band = ds.GetRasterBand(1)
    gdal_dtype = gdal.GetDataTypeName(band.DataType).lower()
    dtype_map = {
        "float32": "float32",
        "float64": "float64",
        "int16": "int16",
        "int32": "int32",
        "uint8": "uint8",
        "byte": "uint8",
    }
    data_type = dtype_map.get(gdal_dtype, "float32")

    ds = None  # close dataset

    meta = {
        "WIDTH": str(width),
        "LENGTH": str(length),
        "NUMBER_BANDS": str(num_bands),
        "X_FIRST": str(x_first),
        "Y_FIRST": str(y_first),
        "X_STEP": str(x_step),
        "Y_STEP": str(y_step),
        "DATA_TYPE": data_type,
        "IS_GEOCODED": is_geocoded,
        "GEOCODED_REASON": reason,
        "PROJECTION_WKT": projection,
    }

    logger.debug(
        "GDAL metadata for %s: %dx%d, %s bands, geocoded=%s (%s)",
        tif_path.name, width, length, num_bands, is_geocoded, reason,
    )
    return meta


def parse_baselines(baseline_dir, ref_date):
    """Load perpendicular baseline values from ISCE2 baseline directory.

    The baseline directory should contain subdirectories named as
    YYYYMMDD_YYYYMMDD, each containing a .txt file with baseline info.

    Parameters
    ----------
    baseline_dir : str or Path
        Path to the ISCE2 baselines directory.
    ref_date : str
        Reference (super-master) date in YYYYMMDD format.

    Returns
    -------
    dict
        Mapping of {date_str: bperp_value} relative to reference.
        The reference date itself maps to 0.0.
    """
    baseline_dir = Path(baseline_dir)
    if not baseline_dir.exists():
        raise FileNotFoundError(f"Baseline directory not found: {baseline_dir}")

    ref_baselines = {}
    ref_baselines[ref_date] = 0.0

    for folder in sorted(baseline_dir.iterdir()):
        if not folder.is_dir():
            continue
        parts = folder.name.split("_")
        if len(parts) != 2:
            continue

        # We need baselines relative to reference date
        if parts[0] != ref_date:
            continue

        secondary_date = parts[1]
        txt_file = folder / f"{folder.name}.txt"
        if not txt_file.exists():
            # Try finding any .txt file in the folder
            txt_files = list(folder.glob("*.txt"))
            if txt_files:
                txt_file = txt_files[0]
            else:
                logger.warning("No baseline file found in: %s", folder)
                continue

        bperp = _parse_bperp_file(txt_file)
        ref_baselines[secondary_date] = bperp

    logger.info(
        "Loaded baselines for %d dates from %s (ref: %s)",
        len(ref_baselines),
        baseline_dir,
        ref_date,
    )
    return ref_baselines


def _parse_bperp_file(txt_path):
    """Extract average Bperp value from a baseline text file.

    Parameters
    ----------
    txt_path : Path
        Path to the baseline .txt file.

    Returns
    -------
    float
        The average perpendicular baseline value, or 0.0 if not found.
    """
    try:
        with open(txt_path) as f:
            for line in f:
                if "Bperp" in line and "average" in line.lower():
                    try:
                        return float(line.split(":")[-1].strip())
                    except ValueError:
                        return 0.0
    except OSError as e:
        logger.warning("Could not read baseline file %s: %s", txt_path, e)

    return 0.0


def compute_bperp_pair(baselines, date1, date2):
    """Compute perpendicular baseline between two dates.

    Bperp(d1, d2) = Bperp(ref, d2) - Bperp(ref, d1)

    Parameters
    ----------
    baselines : dict
        Mapping from date string to Bperp relative to reference.
    date1 : str
        First date (YYYYMMDD).
    date2 : str
        Second date (YYYYMMDD).

    Returns
    -------
    float or None
        Perpendicular baseline in meters, or None if dates not found.
    """
    b1 = baselines.get(date1)
    b2 = baselines.get(date2)
    if b1 is None or b2 is None:
        return None
    return b2 - b1


def extract_dates_from_filename(filename):
    """Extract YYYYMMDD date pair from a filename.

    Looks for the pattern YYYYMMDD_YYYYMMDD anywhere in the filename.

    Parameters
    ----------
    filename : str
        Filename (basename, not full path).

    Returns
    -------
    tuple of (str, str) or None
        (date1, date2) if found, None otherwise.
    """
    m = DATE_PAIR_PATTERN.search(filename)
    if m:
        return m.group(1), m.group(2)
    return None


def auto_detect_ref_date(baseline_dir):
    """Auto-detect the reference (super-master) date from baseline directory.

    The reference date is the one that appears most frequently as the
    first element of YYYYMMDD_YYYYMMDD folder names.

    Parameters
    ----------
    baseline_dir : str or Path
        Path to the ISCE2 baselines directory.

    Returns
    -------
    str or None
        The detected reference date, or None if detection fails.
    """
    baseline_dir = Path(baseline_dir)
    if not baseline_dir.exists():
        return None

    date_counts = {}
    for folder in baseline_dir.iterdir():
        if not folder.is_dir():
            continue
        parts = folder.name.split("_")
        if len(parts) == 2 and len(parts[0]) == 8 and parts[0].isdigit():
            date_counts[parts[0]] = date_counts.get(parts[0], 0) + 1

    if not date_counts:
        return None

    # The reference date appears in most pairs
    ref_date = max(date_counts, key=date_counts.get)
    logger.info("Auto-detected reference date: %s (%d pairs)", ref_date, date_counts[ref_date])
    return ref_date


def count_files(directory, pattern):
    """Count files matching a glob pattern in a directory.

    Parameters
    ----------
    directory : str or Path
        Directory to search.
    pattern : str
        Glob pattern (e.g., '*.unw.tif').

    Returns
    -------
    int
        Number of matching files.
    """
    directory = Path(directory)
    if not directory.exists():
        return 0
    return len(list(directory.glob(pattern)))
