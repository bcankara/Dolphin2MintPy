"""Tests for dolphin2mintpy.prepare module."""

from unittest.mock import patch

import pytest

from dolphin2mintpy.prepare import prepare_rsc, prepare_stack

# Mock GDAL metadata for a truly geocoded raster (lat/lon grid).
MOCK_GDAL_META = {
    "WIDTH": "100",
    "LENGTH": "50",
    "NUMBER_BANDS": "1",
    "X_FIRST": "36.0",
    "Y_FIRST": "41.0",
    "X_STEP": "0.001",
    "Y_STEP": "-0.001",
    "DATA_TYPE": "float32",
    "IS_GEOCODED": True,
    "GEOCODED_REASON": "projection present and non-identity geotransform",
    "PROJECTION_WKT": 'GEOGCS["WGS 84", ...]',
}

# Mock metadata for a Dolphin radar-geometry GeoTIFF (no CRS, identity GT).
MOCK_RADAR_META = {
    "WIDTH": "100",
    "LENGTH": "50",
    "NUMBER_BANDS": "1",
    "X_FIRST": "0.0",
    "Y_FIRST": "0.0",
    "X_STEP": "1.0",
    "Y_STEP": "1.0",
    "DATA_TYPE": "float32",
    "IS_GEOCODED": False,
    "GEOCODED_REASON": "no projection and identity geotransform",
    "PROJECTION_WKT": "",
}


class TestPrepareRsc:
    """Tests for single-file .rsc generation."""

    @patch("dolphin2mintpy.prepare.parse_gdal_metadata", return_value=MOCK_GDAL_META)
    def test_generate_rsc_for_unw(self, mock_gdal, tmp_path):
        tif = tmp_path / "20240907_20241001.unw.tif"
        tif.write_bytes(b"dummy")

        rsc_path = prepare_rsc(
            tif_path=tif,
            date1="20240907",
            date2="20241001",
            bperp=45.3,
        )

        assert rsc_path.exists()
        content = rsc_path.read_text()
        assert "WIDTH" in content
        assert "100" in content
        assert "DATE12" in content
        assert "240907-241001" in content
        assert "45.3000" in content
        assert "PROCESSOR" in content
        assert "hyp3" in content

    @patch("dolphin2mintpy.prepare.parse_gdal_metadata", return_value=MOCK_GDAL_META)
    def test_generate_rsc_for_geometry(self, mock_gdal, tmp_path):
        tif = tmp_path / "dem.tif"
        tif.write_bytes(b"dummy")

        rsc_path = prepare_rsc(
            tif_path=tif,
            is_interferogram=False,
            file_type=".dem",
        )

        assert rsc_path.exists()
        content = rsc_path.read_text()
        assert "WIDTH" in content
        assert "DATE12" not in content

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            prepare_rsc(tmp_path / "nonexistent.tif")

    @patch("dolphin2mintpy.prepare.parse_gdal_metadata", return_value=MOCK_GDAL_META)
    def test_rsc_uses_default_params(self, mock_gdal, tmp_path):
        tif = tmp_path / "20240907_20241001.unw.tif"
        tif.write_bytes(b"dummy")

        rsc_path = prepare_rsc(tif, "20240907", "20241001", 0.0)
        content = rsc_path.read_text()

        # Should use Sentinel-1 defaults
        assert "0.0554" in content  # wavelength
        assert "ASCENDING" in content or "DESCENDING" in content

    @patch("dolphin2mintpy.prepare.parse_gdal_metadata", return_value=MOCK_GDAL_META)
    def test_rsc_uses_custom_params(self, mock_gdal, tmp_path):
        tif = tmp_path / "20240907_20241001.unw.tif"
        tif.write_bytes(b"dummy")

        custom_params = {
            "radarwavelength": "0.05546",
            "rangepixelsize": "2.33",
            "startingrange": "850000.0",
            "prf": "486.0",
            "passdirection": "DESCENDING",
        }

        rsc_path = prepare_rsc(tif, "20240907", "20241001", 10.0, radar_params=custom_params)
        content = rsc_path.read_text()
        assert "DESCENDING" in content
        assert "850000" in content

    @patch("dolphin2mintpy.prepare.parse_gdal_metadata", return_value=MOCK_GDAL_META)
    def test_rsc_always_writes_numeric_heading(self, mock_gdal, tmp_path):
        tif = tmp_path / "20240907_20241001.unw.tif"
        tif.write_bytes(b"dummy")

        rsc_path = prepare_rsc(tif, "20240907", "20241001", 0.0)
        content = rsc_path.read_text()
        # HEADING is required by MintPy's geocode step (pyresample).
        # Even without explicit radar_params it must be a numeric line.
        heading_line = [line for line in content.splitlines() if line.startswith("HEADING")]
        assert len(heading_line) == 1
        value = heading_line[0].split()[1]
        float(value)

    @patch("dolphin2mintpy.prepare.parse_gdal_metadata", return_value=MOCK_GDAL_META)
    def test_rsc_heading_follows_pass_direction(self, mock_gdal, tmp_path):
        tif = tmp_path / "20240907_20241001.unw.tif"
        tif.write_bytes(b"dummy")

        asc = prepare_rsc(
            tif, "20240907", "20241001", 0.0,
            radar_params={"passdirection": "ASCENDING"},
        ).read_text()
        desc = prepare_rsc(
            tif, "20240907", "20241001", 0.0,
            radar_params={"passdirection": "DESCENDING"},
        ).read_text()

        def _heading(text):
            for line in text.splitlines():
                if line.startswith("HEADING"):
                    return float(line.split()[1])
            raise AssertionError("HEADING line missing")

        assert _heading(asc) == pytest.approx(-12.6)
        assert _heading(desc) == pytest.approx(-167.4)

    @patch("dolphin2mintpy.prepare.parse_gdal_metadata", return_value=MOCK_GDAL_META)
    def test_rsc_timing_block_written_when_available(self, mock_gdal, tmp_path):
        tif = tmp_path / "20240907_20241001.unw.tif"
        tif.write_bytes(b"dummy")

        rsc_path = prepare_rsc(
            tif, "20240907", "20241001", 0.0,
            radar_params={
                "passdirection": "ASCENDING",
                "center_line_utc": "12615.000",
                "startutc": "2024-09-19 03:30:00",
                "stoputc": "2024-09-19 03:30:30",
            },
        )
        content = rsc_path.read_text()
        assert "CENTER_LINE_UTC" in content
        assert "12615.000" in content
        assert "startUTC" in content
        assert "stopUTC" in content

    @patch("dolphin2mintpy.prepare.parse_gdal_metadata", return_value=MOCK_GDAL_META)
    def test_rsc_timing_block_absent_without_center_line_utc(self, mock_gdal, tmp_path):
        tif = tmp_path / "20240907_20241001.unw.tif"
        tif.write_bytes(b"dummy")

        rsc_path = prepare_rsc(tif, "20240907", "20241001", 0.0)
        content = rsc_path.read_text()
        # Writing a fake CENTER_LINE_UTC would silently break pyaps3's
        # ERA5 lookup, so the line must be omitted when unknown.
        assert "CENTER_LINE_UTC" not in content


class TestPrepareStack:
    """Tests for batch .rsc generation."""

    @patch("dolphin2mintpy.prepare.parse_gdal_metadata", return_value=MOCK_GDAL_META)
    def test_empty_directory(self, mock_gdal, tmp_path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        result = prepare_stack(unw_dir=empty_dir)
        assert result["rsc_written"] == 0
        assert len(result["errors"]) == 0

    @patch("dolphin2mintpy.prepare.parse_gdal_metadata", return_value=MOCK_GDAL_META)
    def test_processes_all_file_types(self, mock_gdal, tmp_path):
        unw_dir = tmp_path / "unw"
        cor_dir = tmp_path / "cor"
        unw_dir.mkdir()
        cor_dir.mkdir()

        # Create test files
        (unw_dir / "20240907_20241001.unw.tif").write_bytes(b"dummy")
        (unw_dir / "20240907_20241001.unw.conncomp.tif").write_bytes(b"dummy")
        (cor_dir / "20240907_20241001.int.cor.tif").write_bytes(b"dummy")

        result = prepare_stack(unw_dir=unw_dir, cor_dir=cor_dir)
        assert result["rsc_written"] == 3

    @patch("dolphin2mintpy.prepare.parse_gdal_metadata", return_value=MOCK_GDAL_META)
    def test_progress_callback(self, mock_gdal, tmp_path):
        unw_dir = tmp_path / "data"
        unw_dir.mkdir()
        (unw_dir / "20240907_20241001.unw.tif").write_bytes(b"dummy")

        progress_calls = []
        prepare_stack(
            unw_dir=unw_dir,
            progress_callback=lambda c, t: progress_calls.append((c, t)),
        )

        assert len(progress_calls) > 0
        assert progress_calls[-1][0] == progress_calls[-1][1]


class TestGeometryMode:
    """Tests covering auto / radar / geo geometry mode behaviour."""

    @patch("dolphin2mintpy.prepare.parse_gdal_metadata", return_value=MOCK_RADAR_META)
    def test_auto_detects_radar_omits_geotransform(self, mock_gdal, tmp_path):
        tif = tmp_path / "20240907_20241001.unw.tif"
        tif.write_bytes(b"dummy")

        rsc_path = prepare_rsc(tif, "20240907", "20241001", 0.0)
        content = rsc_path.read_text()

        # Radar geometry → X_FIRST / Y_FIRST must NOT be written, otherwise
        # MintPy readfile flags the product as geocoded and looks for
        # geometryGeo.h5 instead of geometryRadar.h5.
        assert "X_FIRST" not in content
        assert "Y_FIRST" not in content
        assert "X_STEP" not in content
        assert "Y_STEP" not in content

    @patch("dolphin2mintpy.prepare.parse_gdal_metadata", return_value=MOCK_GDAL_META)
    def test_auto_detects_geo_emits_geotransform(self, mock_gdal, tmp_path):
        tif = tmp_path / "20240907_20241001.unw.tif"
        tif.write_bytes(b"dummy")

        rsc_path = prepare_rsc(tif, "20240907", "20241001", 0.0)
        content = rsc_path.read_text()

        assert "X_FIRST" in content
        assert "Y_FIRST" in content
        assert "X_STEP" in content
        assert "Y_STEP" in content

    @patch("dolphin2mintpy.prepare.parse_gdal_metadata", return_value=MOCK_GDAL_META)
    def test_force_radar_overrides_detection(self, mock_gdal, tmp_path):
        tif = tmp_path / "20240907_20241001.unw.tif"
        tif.write_bytes(b"dummy")

        rsc_path = prepare_rsc(
            tif, "20240907", "20241001", 0.0, geometry_mode="radar",
        )
        content = rsc_path.read_text()

        assert "X_FIRST" not in content
        assert "Y_FIRST" not in content

    @patch("dolphin2mintpy.prepare.parse_gdal_metadata", return_value=MOCK_RADAR_META)
    def test_force_geo_overrides_detection(self, mock_gdal, tmp_path):
        tif = tmp_path / "20240907_20241001.unw.tif"
        tif.write_bytes(b"dummy")

        rsc_path = prepare_rsc(
            tif, "20240907", "20241001", 0.0, geometry_mode="geo",
        )
        content = rsc_path.read_text()

        assert "X_FIRST" in content
        assert "Y_FIRST" in content

    @patch("dolphin2mintpy.prepare.parse_gdal_metadata", return_value=MOCK_RADAR_META)
    def test_invalid_mode_raises(self, mock_gdal, tmp_path):
        tif = tmp_path / "20240907_20241001.unw.tif"
        tif.write_bytes(b"dummy")

        with pytest.raises(ValueError):
            prepare_rsc(tif, "20240907", "20241001", 0.0, geometry_mode="bogus")

    @patch("dolphin2mintpy.prepare.parse_gdal_metadata", return_value=MOCK_RADAR_META)
    def test_stack_records_effective_mode(self, mock_gdal, tmp_path):
        unw_dir = tmp_path / "unw"
        unw_dir.mkdir()
        (unw_dir / "20240907_20241001.unw.tif").write_bytes(b"dummy")

        result = prepare_stack(unw_dir=unw_dir, geometry_mode="radar")
        assert result["geometry_mode"] == "radar"
        assert result["rsc_written"] == 1

    @patch("dolphin2mintpy.prepare.parse_gdal_metadata", return_value=MOCK_RADAR_META)
    def test_stack_rejects_invalid_mode(self, mock_gdal, tmp_path):
        unw_dir = tmp_path / "unw"
        unw_dir.mkdir()
        (unw_dir / "20240907_20241001.unw.tif").write_bytes(b"dummy")

        with pytest.raises(ValueError):
            prepare_stack(unw_dir=unw_dir, geometry_mode="nope")
