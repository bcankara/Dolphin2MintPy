"""
User settings persistence for Dolphin2MintPy.

Saves and loads project settings from a JSON file so that users
configure their paths once and reuse them across runs.

Settings file: dolphin2mintpy_settings.json (in the current working directory)
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SETTINGS_FILENAME = "dolphin2mintpy_settings.json"

# All recognized setting keys with descriptions
SETTINGS_KEYS = {
    "unw_dir": "Unwrapped interferograms directory (*.unw.tif)",
    "cor_dir": "Coherence files directory (*.cor.tif)",
    "conncomp_dir": "Connected component files directory",
    "baseline_dir": "ISCE2 baseline directory",
    "ref_xml": "ISCE2 reference XML file path",
    "ref_date": "Reference (super-master) date (YYYYMMDD)",
    "geometry_dir": "Geometry files directory (DEM, incidence, azimuth)",
    "dem_file": "DEM file (e.g. hgt.rdr.full)",
    "inc_angle_file": "Incidence angle file (e.g. los.rdr.full)",
    "az_angle_file": "Azimuth angle file (e.g. los.rdr.full)",
    "lookup_y_file": "Lookup Y / latitude file (e.g. lat.rdr.full)",
    "lookup_x_file": "Lookup X / longitude file (e.g. lon.rdr.full)",
    "water_mask_file": "Water mask file (optional)",
    "mintpy_processor": "mintpy.load.processor value (isce / hyp3)",
    "work_dir": "MintPy working/output directory",
    "geometry_mode": "Geometry mode for .rsc sidecars (auto/radar/geo)",
}


def find_settings_file(search_dir=None):
    """Find the settings file in the given or current directory.

    Parameters
    ----------
    search_dir : str or Path, optional
        Directory to search for settings. Defaults to cwd.

    Returns
    -------
    Path or None
        Path to settings file if found, None otherwise.
    """
    search_dir = Path(search_dir) if search_dir else Path.cwd()
    settings_path = search_dir / SETTINGS_FILENAME
    if settings_path.exists():
        return settings_path
    return None


def load_settings(settings_path=None):
    """Load settings from a JSON file.

    Parameters
    ----------
    settings_path : str or Path, optional
        Path to settings file. If None, searches current directory.

    Returns
    -------
    dict
        Settings dictionary. Empty dict if file not found.
    """
    if settings_path is None:
        settings_path = find_settings_file()

    if settings_path is None:
        return {}

    settings_path = Path(settings_path)
    if not settings_path.exists():
        return {}

    try:
        with open(settings_path, encoding="utf-8") as f:
            data = json.load(f)
        logger.info("Loaded settings from: %s", settings_path)
        return data
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Could not load settings from %s: %s", settings_path, e)
        return {}


def save_settings(settings, settings_path=None):
    """Save settings to a JSON file.

    Parameters
    ----------
    settings : dict
        Settings to save.
    settings_path : str or Path, optional
        Path to write. Defaults to cwd/dolphin2mintpy_settings.json.

    Returns
    -------
    Path
        Path to the saved settings file.
    """
    if settings_path is None:
        settings_path = Path.cwd() / SETTINGS_FILENAME

    settings_path = Path(settings_path)

    # Convert Path objects to strings for JSON serialization
    serializable = {}
    for key, value in settings.items():
        if isinstance(value, Path):
            serializable[key] = str(value)
        elif value is not None:
            serializable[key] = value

    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2, ensure_ascii=False)

    logger.info("Settings saved to: %s", settings_path)
    return settings_path


def format_settings_display(settings):
    """Format settings for terminal display.

    Parameters
    ----------
    settings : dict
        Settings dictionary.

    Returns
    -------
    str
        Formatted multi-line string.
    """
    lines = []
    for key, description in SETTINGS_KEYS.items():
        value = settings.get(key)
        if value:
            lines.append(f"    {description}:")
            lines.append(f"      {value}")
        else:
            lines.append(f"    {description}:")
            lines.append("      (not set)")
    return "\n".join(lines)
