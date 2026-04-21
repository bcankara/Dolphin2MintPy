"""Tests for dolphin2mintpy.cli module."""

from unittest.mock import patch

import pytest

from dolphin2mintpy.cli import main


class TestCli:
    """Tests for CLI argument parsing and dispatch."""

    def test_version_flag(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["--version"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "0.1.0" in captured.out

    def test_no_args_launches_gui(self):
        with patch("dolphin2mintpy.cli._cmd_gui") as mock_gui:
            main([])
            mock_gui.assert_called_once()

    def test_gui_subcommand(self):
        with patch("dolphin2mintpy.cli._cmd_gui") as mock_gui:
            main(["gui"])
            mock_gui.assert_called_once()

    def test_prepare_requires_unw_dir(self):
        with pytest.raises(SystemExit) as exc_info:
            main(["prepare"])
        assert exc_info.value.code != 0

    def test_generate_config_requires_args(self):
        with pytest.raises(SystemExit) as exc_info:
            main(["generate-config"])
        assert exc_info.value.code != 0

    def test_info_requires_unw_dir(self):
        with pytest.raises(SystemExit) as exc_info:
            main(["info"])
        assert exc_info.value.code != 0

    def test_prepare_rejects_invalid_geometry_mode(self):
        with pytest.raises(SystemExit) as exc_info:
            main(["prepare", "--unw-dir", "/tmp", "--geometry-mode", "bogus"])
        assert exc_info.value.code != 0

    def test_prepare_accepts_geometry_mode(self, tmp_path):
        with patch("dolphin2mintpy.prepare.prepare_stack") as mock_prep:
            mock_prep.return_value = {
                "rsc_written": 0, "errors": [], "skipped": 0,
                "details": [], "geometry_mode": "radar",
            }
            unw = tmp_path / "unw"
            unw.mkdir()
            main(["prepare", "--unw-dir", str(unw), "--geometry-mode", "radar"])
            kwargs = mock_prep.call_args.kwargs
            assert kwargs["geometry_mode"] == "radar"
