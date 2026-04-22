"""Shared test fixtures for dolphin2mintpy tests."""

from pathlib import Path

import pytest


@pytest.fixture
def tmp_workspace(tmp_path):
    """Create a temporary workspace with realistic directory structure."""
    # Create directories
    unw_dir = tmp_path / "unwrapped"
    cor_dir = tmp_path / "interferograms"
    baseline_dir = tmp_path / "baselines"
    ref_dir = tmp_path / "reference"
    work_dir = tmp_path / "mintpy"

    for d in [unw_dir, cor_dir, baseline_dir, ref_dir, work_dir]:
        d.mkdir()

    return {
        "root": tmp_path,
        "unw_dir": unw_dir,
        "cor_dir": cor_dir,
        "baseline_dir": baseline_dir,
        "ref_dir": ref_dir,
        "work_dir": work_dir,
    }


@pytest.fixture
def sample_xml(tmp_workspace):
    """Create a minimal ISCE2-style reference XML file.

    Includes ``sensingStart`` / ``sensingStop`` so tests can exercise
    the ``CENTER_LINE_UTC`` derivation path used by MintPy's
    ``correct_troposphere`` step.
    """
    xml_content = """\
<?xml version="1.0" encoding="UTF-8"?>
<component name="IW2">
    <property name="radarwavelength">
        <value>0.05546576</value>
    </property>
    <property name="rangepixelsize">
        <value>2.329562</value>
    </property>
    <property name="startingrange">
        <value>845984.71</value>
    </property>
    <property name="azimuthtimeinterval">
        <value>0.002055556</value>
    </property>
    <property name="passdirection">
        <value>ASCENDING</value>
    </property>
    <property name="sensingstart">
        <value>2024-09-19 03:30:00.000000</value>
    </property>
    <property name="sensingstop">
        <value>2024-09-19 03:30:30.000000</value>
    </property>
</component>
"""
    xml_path = tmp_workspace["ref_dir"] / "IW2.xml"
    xml_path.write_text(xml_content)
    return xml_path


@pytest.fixture
def sample_baselines(tmp_workspace):
    """Create sample baseline directory structure."""
    ref_date = "20240919"
    dates = ["20240907", "20241001", "20241013"]

    for d in dates:
        pair_dir = tmp_workspace["baseline_dir"] / f"{ref_date}_{d}"
        pair_dir.mkdir()
        txt = pair_dir / f"{ref_date}_{d}.txt"
        bperp_val = {"20240907": -45.2, "20241001": 32.7, "20241013": -12.8}[d]
        txt.write_text(
            f"Bperp (average): {bperp_val}\n"
            f"Bperp at top of first burst: {bperp_val + 1.0}\n"
        )

    return ref_date, dates


def create_mock_geotiff(filepath, width=100, height=50, bands=1):
    """Create a minimal valid GeoTIFF file for testing.

    This creates a bare-minimum TIFF file that GDAL can open.
    For tests that don't need GDAL, use create_dummy_tif instead.
    """
    try:
        from osgeo import gdal, osr

        driver = gdal.GetDriverByName("GTiff")
        ds = driver.Create(str(filepath), width, height, bands, gdal.GDT_Float32)

        # Set geotransform
        ds.SetGeoTransform([36.0, 0.001, 0, 41.0, 0, -0.001])

        # Set projection (WGS84)
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(4326)
        ds.SetProjection(srs.ExportToWkt())

        ds.FlushCache()
        ds = None
        return True
    except ImportError:
        # GDAL not available, create a dummy file
        create_dummy_tif(filepath)
        return False


def create_dummy_tif(filepath):
    """Create a minimal placeholder .tif file (not GDAL-readable)."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_bytes(b"dummy_tif_content")
