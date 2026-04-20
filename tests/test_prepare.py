"""Tests for dolphin2mintpy.prepare module."""

from unittest.mock import patch

import pytest

from dolphin2mintpy.prepare import prepare_rsc, prepare_stack

# Mock GDAL metadata for tests without GDAL
MOCK_GDAL_META = {
    "WIDTH": "100",
    "LENGTH": "50",
    "NUMBER_BANDS": "1",
    "X_FIRST": "36.0",
    "Y_FIRST": "41.0",
    "X_STEP": "0.001",
    "Y_STEP": "-0.001",
    "DATA_TYPE": "float32",
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
