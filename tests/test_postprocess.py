"""Tests for the post-load HDF5 processor patch."""

import pytest

h5py = pytest.importorskip("h5py")

from dolphin2mintpy.postprocess import (  # noqa: E402
    PostProcessError,
    fix_processor_attribute,
    verify_inputs_dir,
)


def _make_ifgram_stack(path, processor="hyp3"):
    with h5py.File(path, "w") as f:
        f.attrs["PROCESSOR"] = processor
        f.attrs["INSAR_PROCESSOR"] = processor
        f.create_dataset("date", data=[b"20240101_20240113"])


def _make_geometry_radar(path, processor="hyp3", with_lookup=True):
    with h5py.File(path, "w") as f:
        f.attrs["PROCESSOR"] = processor
        f.attrs["INSAR_PROCESSOR"] = processor
        f.create_dataset("height", data=[[0.0]])
        if with_lookup:
            f.create_dataset("latitude", data=[[0.0]])
            f.create_dataset("longitude", data=[[0.0]])


def test_verify_reports_existing_attributes(tmp_path):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    _make_ifgram_stack(inputs / "ifgramStack.h5")
    _make_geometry_radar(inputs / "geometryRadar.h5")

    report = verify_inputs_dir(inputs)

    by_name = {r["path"].name: r for r in report}
    assert by_name["ifgramStack.h5"]["exists"] is True
    assert by_name["ifgramStack.h5"]["processor"] == "hyp3"
    assert by_name["ifgramStack.h5"]["needs_patch"] is True

    assert by_name["geometryRadar.h5"]["exists"] is True
    assert by_name["geometryRadar.h5"]["has_lat_lon"] is True


def test_verify_flags_missing_lookup_datasets(tmp_path):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    _make_ifgram_stack(inputs / "ifgramStack.h5")
    _make_geometry_radar(inputs / "geometryRadar.h5", with_lookup=False)

    report = verify_inputs_dir(inputs)
    geom = next(r for r in report if r["path"].name == "geometryRadar.h5")
    assert geom["has_lat_lon"] is False
    assert any("missing required datasets" in issue for issue in geom["issues"])


def test_fix_processor_rewrites_attributes(tmp_path):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    stack = inputs / "ifgramStack.h5"
    geom = inputs / "geometryRadar.h5"
    _make_ifgram_stack(stack)
    _make_geometry_radar(geom)

    summary = fix_processor_attribute(inputs)

    assert summary["patched"] == 2
    assert summary["errors"] == []
    with h5py.File(stack) as f:
        assert f.attrs["PROCESSOR"] == "isce"
        assert f.attrs["INSAR_PROCESSOR"] == "isce"
    with h5py.File(geom) as f:
        assert f.attrs["PROCESSOR"] == "isce"


def test_fix_processor_dry_run_leaves_files_unchanged(tmp_path):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    stack = inputs / "ifgramStack.h5"
    _make_ifgram_stack(stack)
    _make_geometry_radar(inputs / "geometryRadar.h5")

    summary = fix_processor_attribute(inputs, dry_run=True)

    assert summary["patched"] == 2
    assert summary["dry_run"] is True
    with h5py.File(stack) as f:
        assert f.attrs["PROCESSOR"] == "hyp3"


def test_fix_processor_is_idempotent(tmp_path):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    _make_ifgram_stack(inputs / "ifgramStack.h5", processor="isce")
    _make_geometry_radar(inputs / "geometryRadar.h5", processor="isce")

    summary = fix_processor_attribute(inputs)

    assert summary["patched"] == 0
    assert summary["skipped"] == 2


def test_fix_processor_aborts_when_lookup_missing(tmp_path):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    _make_ifgram_stack(inputs / "ifgramStack.h5")
    _make_geometry_radar(inputs / "geometryRadar.h5", with_lookup=False)

    with pytest.raises(PostProcessError):
        fix_processor_attribute(inputs)


def test_fix_processor_skip_lookup_check(tmp_path):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    _make_ifgram_stack(inputs / "ifgramStack.h5")
    _make_geometry_radar(inputs / "geometryRadar.h5", with_lookup=False)

    summary = fix_processor_attribute(inputs, require_lookup_datasets=False)
    assert summary["patched"] == 2


def test_fix_processor_missing_inputs_dir(tmp_path):
    with pytest.raises(PostProcessError):
        fix_processor_attribute(tmp_path / "does-not-exist")
