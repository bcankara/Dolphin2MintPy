"""
Command-line interface for dolphin2mintpy.

Provides subcommands for graphical and non-interactive workflows:
  - gui        : Launch the Tkinter GUI (default when no subcommand given)
  - prepare    : Non-interactive .rsc generation
  - generate-config : Generate MintPy configuration only
  - info       : Display stack information
"""

import argparse
import logging
import sys


def main(args=None):
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="dolphin2mintpy",
        description=(
            "Bridge between Dolphin InSAR processor and MintPy time-series analysis. "
            "Generates .rsc sidecar files and MintPy-compatible configuration."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  dolphin2mintpy                          # Launch the GUI
  dolphin2mintpy gui                      # Same as above

  dolphin2mintpy prepare \\
      --unw-dir ./unwrapped \\
      --cor-dir ./interferograms \\
      --baseline-dir ./baselines \\
      --ref-xml ./reference/IW2.xml \\
      --ref-date 20240919

  dolphin2mintpy generate-config \\
      --work-dir ./mintpy \\
      --unw-dir ./unwrapped

  dolphin2mintpy info --unw-dir ./unwrapped
""",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_get_version()}",
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG) logging.",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- gui (default) ---
    subparsers.add_parser(
        "gui",
        help="Launch the Tkinter graphical interface (default).",
        description=(
            "Open the point-and-click interface for selecting paths "
            "and running the pipeline."
        ),
    )

    # --- prepare ---
    prep_parser = subparsers.add_parser(
        "prepare",
        help="Generate .rsc sidecar files (non-interactive).",
        description="Generate .rsc metadata sidecar files for all GeoTIFFs.",
    )
    prep_parser.add_argument(
        "--unw-dir", required=True,
        help="Directory containing unwrapped phase GeoTIFFs (*.unw.tif).",
    )
    prep_parser.add_argument(
        "--cor-dir", default=None,
        help="Directory containing coherence GeoTIFFs. Default: same as --unw-dir.",
    )
    prep_parser.add_argument(
        "--conncomp-dir", default=None,
        help="Directory containing connected component GeoTIFFs. Default: same as --unw-dir.",
    )
    prep_parser.add_argument(
        "--geometry-dir", default=None,
        help="Directory containing geometry GeoTIFFs (DEM, incidence, azimuth).",
    )
    prep_parser.add_argument(
        "--baseline-dir", default=None,
        help="ISCE2 baselines directory for Bperp computation.",
    )
    prep_parser.add_argument(
        "--ref-xml", default=None,
        help="ISCE2 reference XML file (e.g., reference/IW2.xml).",
    )
    prep_parser.add_argument(
        "--ref-date", default=None,
        help="Reference (super-master) date in YYYYMMDD format.",
    )
    prep_parser.add_argument(
        "--geometry-mode",
        choices=("auto", "radar", "geo"),
        default="auto",
        help=(
            "How to populate geotransform metadata in the .rsc sidecars: "
            "'auto' detects from the GeoTIFF (default), 'radar' forces "
            "radar geometry (omits X_FIRST/Y_FIRST so MintPy produces "
            "geometryRadar.h5), 'geo' forces geocoded output (emits the "
            "geotransform so MintPy produces geometryGeo.h5)."
        ),
    )

    # --- generate-config ---
    cfg_parser = subparsers.add_parser(
        "generate-config",
        help="Generate MintPy configuration file only.",
        description="Generate a smallbaselineApp.cfg-compatible configuration file.",
    )
    cfg_parser.add_argument(
        "--work-dir", required=True,
        help="MintPy working directory (where config will be written).",
    )
    cfg_parser.add_argument(
        "--unw-dir", required=True,
        help="Directory containing unwrapped phase GeoTIFFs.",
    )
    cfg_parser.add_argument(
        "--cor-dir", default=None,
        help="Directory containing coherence GeoTIFFs.",
    )
    cfg_parser.add_argument(
        "--conncomp-dir", default=None,
        help="Directory containing connected component GeoTIFFs.",
    )
    cfg_parser.add_argument(
        "--dem-file", default=None,
        help="DEM GeoTIFF file path or glob pattern.",
    )
    cfg_parser.add_argument(
        "--config-name", default="mintpy_config.txt",
        help="Output config filename. Default: mintpy_config.txt.",
    )

    # --- info ---
    info_parser = subparsers.add_parser(
        "info",
        help="Display stack information.",
        description="Show summary information about a Dolphin output stack.",
    )
    info_parser.add_argument(
        "--unw-dir", required=True,
        help="Directory containing unwrapped phase GeoTIFFs.",
    )
    info_parser.add_argument(
        "--cor-dir", default=None,
        help="Directory containing coherence GeoTIFFs.",
    )
    info_parser.add_argument(
        "--baseline-dir", default=None,
        help="ISCE2 baselines directory.",
    )

    parsed = parser.parse_args(args)

    log_level = logging.DEBUG if parsed.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if parsed.command is None or parsed.command == "gui":
        _cmd_gui()
    elif parsed.command == "prepare":
        _cmd_prepare(parsed)
    elif parsed.command == "generate-config":
        _cmd_generate_config(parsed)
    elif parsed.command == "info":
        _cmd_info(parsed)
    else:
        parser.print_help()
        sys.exit(1)


def _cmd_gui():
    """Launch the Tkinter GUI."""
    from dolphin2mintpy.gui import run_gui

    run_gui()


def _cmd_prepare(args):
    """Run non-interactive .rsc generation."""
    from dolphin2mintpy.prepare import prepare_stack

    result = prepare_stack(
        unw_dir=args.unw_dir,
        cor_dir=args.cor_dir,
        conncomp_dir=args.conncomp_dir,
        geometry_dir=args.geometry_dir,
        baseline_dir=args.baseline_dir,
        ref_xml=args.ref_xml,
        ref_date=args.ref_date,
        geometry_mode=args.geometry_mode,
    )

    print(f"\nDone: {result['rsc_written']} .rsc files written.")
    if result["errors"]:
        print(f"Errors: {len(result['errors'])}")
        for e in result["errors"]:
            print(f"  ! {e['file']}: {e['error']}")
        sys.exit(2)


def _cmd_generate_config(args):
    """Generate MintPy configuration file."""
    from dolphin2mintpy.config import generate_mintpy_config

    config_path = generate_mintpy_config(
        work_dir=args.work_dir,
        unw_dir=args.unw_dir,
        cor_dir=args.cor_dir,
        conncomp_dir=args.conncomp_dir,
        dem_file=args.dem_file,
        config_name=args.config_name,
    )

    print(f"Config written: {config_path}")
    print(f"\nNext step: smallbaselineApp.py {config_path.name}")


def _cmd_info(args):
    """Display stack information."""
    from pathlib import Path

    from dolphin2mintpy.metadata import (
        auto_detect_ref_date,
        count_files,
        extract_dates_from_filename,
    )

    unw_dir = Path(args.unw_dir)
    cor_dir = Path(args.cor_dir) if args.cor_dir else unw_dir

    print(f"\n{'-' * 50}")
    print("  Dolphin Stack Information")
    print(f"{'-' * 50}")

    unw_count = count_files(unw_dir, "*.unw.tif")
    cor_count = count_files(cor_dir, "*.cor.tif") + count_files(cor_dir, "*.int.cor.tif")
    conn_count = count_files(unw_dir, "*.conncomp.tif")

    print(f"\n  Unwrapped files:     {unw_count}")
    print(f"  Coherence files:     {cor_count}")
    print(f"  ConnComp files:      {conn_count}")

    dates = set()
    for f in unw_dir.glob("*.unw.tif"):
        result = extract_dates_from_filename(f.name)
        if result:
            dates.add(result[0])
            dates.add(result[1])

    if dates:
        sorted_dates = sorted(dates)
        print(f"\n  Date range:          {sorted_dates[0]} -> {sorted_dates[-1]}")
        print(f"  Unique dates:        {len(sorted_dates)}")
        print(f"  Interferogram pairs: {unw_count}")

    if args.baseline_dir:
        ref = auto_detect_ref_date(args.baseline_dir)
        if ref:
            print(f"  Reference date:      {ref}")

    rsc_count = count_files(unw_dir, "*.rsc")
    if rsc_count > 0:
        print(f"\n  Existing .rsc files: {rsc_count}")
    else:
        print("\n  WARNING: No .rsc files found -- run 'dolphin2mintpy' to generate them.")

    print(f"\n{'-' * 50}\n")


def _get_version():
    """Get package version string."""
    try:
        from dolphin2mintpy import __version__
        return __version__
    except ImportError:
        return "unknown"


if __name__ == "__main__":
    main()
