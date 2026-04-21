"""Tests for dolphin2mintpy.metadata module."""


import pytest

from dolphin2mintpy.metadata import (
    _detect_geocoded,
    _is_default_geotransform,
    auto_detect_ref_date,
    compute_bperp_pair,
    extract_dates_from_filename,
    parse_baselines,
    parse_isce_xml,
)


class TestParseIsceXml:
    """Tests for ISCE2 XML parsing."""

    def test_parse_valid_xml(self, sample_xml):
        result = parse_isce_xml(sample_xml)
        assert "radarwavelength" in result
        assert float(result["radarwavelength"]) == pytest.approx(0.05546576)
        assert float(result["rangepixelsize"]) == pytest.approx(2.329562)
        assert float(result["startingrange"]) == pytest.approx(845984.71)
        assert "passdirection" in result
        assert result["passdirection"] == "ASCENDING"

    def test_derives_prf_from_azimuth_time(self, sample_xml):
        result = parse_isce_xml(sample_xml)
        assert "prf" in result
        expected_prf = 1.0 / 0.002055556
        assert float(result["prf"]) == pytest.approx(expected_prf, rel=1e-3)

    def test_missing_xml_raises(self):
        with pytest.raises(FileNotFoundError):
            parse_isce_xml("/nonexistent/path/IW2.xml")


class TestParseBaselines:
    """Tests for baseline directory parsing."""

    def test_parse_baselines(self, tmp_workspace, sample_baselines):
        ref_date, dates = sample_baselines
        result = parse_baselines(tmp_workspace["baseline_dir"], ref_date)

        assert ref_date in result
        assert result[ref_date] == 0.0
        assert "20240907" in result
        assert result["20240907"] == pytest.approx(-45.2)
        assert "20241001" in result
        assert result["20241001"] == pytest.approx(32.7)

    def test_missing_dir_raises(self):
        with pytest.raises(FileNotFoundError):
            parse_baselines("/nonexistent/baselines", "20240101")


class TestComputeBperpPair:
    """Tests for Bperp pair computation."""

    def test_compute_valid_pair(self):
        baselines = {"20240101": 0.0, "20240201": 50.0, "20240301": -30.0}
        # Bperp(d1, d2) = Bperp(ref, d2) - Bperp(ref, d1)
        assert compute_bperp_pair(baselines, "20240201", "20240301") == pytest.approx(-80.0)

    def test_missing_date_returns_none(self):
        baselines = {"20240101": 0.0}
        assert compute_bperp_pair(baselines, "20240101", "20240201") is None


class TestExtractDates:
    """Tests for date extraction from filenames."""

    def test_standard_dolphin_filename(self):
        result = extract_dates_from_filename("20240907_20241001.unw.tif")
        assert result == ("20240907", "20241001")

    def test_with_prefix(self):
        result = extract_dates_from_filename("phase_20240907_20241001.unw.tif")
        assert result == ("20240907", "20241001")

    def test_no_dates(self):
        result = extract_dates_from_filename("dem.tif")
        assert result is None

    def test_single_date(self):
        result = extract_dates_from_filename("20240907.tif")
        assert result is None


class TestAutoDetectRefDate:
    """Tests for automatic reference date detection."""

    def test_detects_most_frequent(self, tmp_workspace, sample_baselines):
        ref_date, _ = sample_baselines
        detected = auto_detect_ref_date(tmp_workspace["baseline_dir"])
        assert detected == ref_date

    def test_empty_dir_returns_none(self, tmp_path):
        empty_dir = tmp_path / "empty_baselines"
        empty_dir.mkdir()
        assert auto_detect_ref_date(empty_dir) is None

    def test_nonexistent_dir_returns_none(self):
        assert auto_detect_ref_date("/nonexistent/path") is None


class TestDetectGeocoded:
    """Tests for the projection + geotransform geocoded detector."""

    def test_identity_geotransform_is_default(self):
        assert _is_default_geotransform((0.0, 1.0, 0.0, 0.0, 0.0, 1.0)) is True

    def test_non_identity_geotransform(self):
        assert _is_default_geotransform((36.0, 0.001, 0, 41.0, 0, -0.001)) is False

    def test_none_geotransform_treated_as_default(self):
        assert _is_default_geotransform(None) is True

    def test_real_geocoded(self):
        wkt = 'GEOGCS["WGS 84",...]'
        gt = (36.0, 0.001, 0.0, 41.0, 0.0, -0.001)
        is_geo, reason = _detect_geocoded(wkt, gt)
        assert is_geo is True
        assert "projection" in reason

    def test_dolphin_radar_geometry(self):
        is_geo, reason = _detect_geocoded("", (0.0, 1.0, 0.0, 0.0, 0.0, 1.0))
        assert is_geo is False
        assert "identity" in reason

    def test_projection_without_real_geotransform(self):
        is_geo, _ = _detect_geocoded(
            'GEOGCS["WGS 84",...]', (0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
        )
        assert is_geo is False

    def test_geotransform_without_projection(self):
        is_geo, _ = _detect_geocoded("", (36.0, 0.001, 0.0, 41.0, 0.0, -0.001))
        assert is_geo is False
