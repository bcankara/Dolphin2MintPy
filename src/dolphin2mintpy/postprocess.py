"""
Post-load HDF5 post-processing for MintPy.

After ``smallbaselineApp.py --dostep load_data`` completes, MintPy's
``check_loaded_dataset()`` decides how to locate the lookup table based
on the ``PROCESSOR`` HDF5 attribute written on the input stack files.

Dolphin GeoTIFFs are compressed, so dolphin2mintpy sets ``PROCESSOR=hyp3``
in the ``.rsc`` sidecars to force MintPy's GDAL reader during ``load_data``
(the ISCE path would try a raw-binary read and fail with a reshape error).
However, the ``hyp3`` label is also interpreted as "this stack is in
geographic coordinates", and MintPy then refuses to look up
``/latitude`` + ``/longitude`` datasets that we actually have in
``geometryRadar.h5``. The failure surfaces as::

    AttributeError: Unknown InSAR processor: hyp3 to locate look up table!

Patching the HDF5 ``PROCESSOR`` attribute from ``hyp3`` to ``isce`` after
``load_data`` succeeds keeps the GDAL ingest path we needed and unlocks
the ISCE lookup-table logic that is compatible with radar-geometry
stacks. This module exposes a small helper that automates exactly that
patch with up-front safety checks.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# MintPy's default inputs/ layout
DEFAULT_TARGET_FILES = ("ifgramStack.h5", "geometryRadar.h5")

# Attributes to rewrite on every targeted file
PROCESSOR_ATTRS = ("PROCESSOR", "INSAR_PROCESSOR")

# Datasets expected in geometryRadar.h5 for radar-mode lookup
REQUIRED_LOOKUP_DATASETS = ("latitude", "longitude")


class PostProcessError(RuntimeError):
    """Raised when the HDF5 patch cannot be applied safely."""


def _require_h5py():
    """Import h5py lazily with a user-friendly error message."""
    try:
        import h5py  # noqa: F401
    except ImportError as exc:
        raise PostProcessError(
            "h5py is required for the post-load fix step. "
            "Install it with: pip install h5py"
        ) from exc
    return __import__("h5py")


def verify_inputs_dir(
    inputs_dir,
    target_files=DEFAULT_TARGET_FILES,
    expected_old="hyp3",
):
    """Inspect an ``inputs/`` directory and report what will happen.

    Parameters
    ----------
    inputs_dir : str or Path
        MintPy ``inputs/`` directory produced by ``load_data``.
    target_files : iterable of str
        HDF5 files to inspect (defaults to ``ifgramStack.h5``,
        ``geometryRadar.h5``).
    expected_old : str
        The processor label we expect to replace (default ``hyp3``).

    Returns
    -------
    list of dict
        One record per file with keys:

        ``path``           absolute Path to the HDF5 file
        ``exists``         bool
        ``processor``      current PROCESSOR attribute value (or None)
        ``insar_processor`` current INSAR_PROCESSOR attribute value (or None)
        ``has_lat_lon``    True if /latitude and /longitude datasets exist
                           (only computed for geometryRadar.h5)
        ``needs_patch``    True if PROCESSOR currently equals ``expected_old``
        ``issues``         list of human-readable warnings for this file
    """
    h5py = _require_h5py()
    inputs_dir = Path(inputs_dir)
    report = []

    for fname in target_files:
        path = inputs_dir / fname
        entry = {
            "path": path,
            "exists": path.is_file(),
            "processor": None,
            "insar_processor": None,
            "has_lat_lon": None,
            "needs_patch": False,
            "issues": [],
        }

        if not entry["exists"]:
            entry["issues"].append(
                f"{fname} not found - run 'smallbaselineApp.py --dostep "
                "load_data' first to produce it."
            )
            report.append(entry)
            continue

        try:
            with h5py.File(path, "r") as f:
                attrs = dict(f.attrs)
                entry["processor"] = _decode_attr(attrs.get("PROCESSOR"))
                entry["insar_processor"] = _decode_attr(
                    attrs.get("INSAR_PROCESSOR")
                )
                entry["needs_patch"] = entry["processor"] == expected_old

                if fname.startswith("geometryRadar"):
                    missing = [
                        ds for ds in REQUIRED_LOOKUP_DATASETS if ds not in f
                    ]
                    entry["has_lat_lon"] = not missing
                    if missing:
                        entry["issues"].append(
                            f"{fname} is missing required datasets: "
                            f"{', '.join(missing)}. Delete this file and "
                            "re-run load_data before applying the fix."
                        )
        except OSError as exc:
            entry["issues"].append(f"Could not read {fname}: {exc}")

        report.append(entry)

    return report


def fix_processor_attribute(
    inputs_dir,
    old="hyp3",
    new="isce",
    target_files=DEFAULT_TARGET_FILES,
    dry_run=False,
    require_lookup_datasets=True,
):
    """Rewrite the PROCESSOR / INSAR_PROCESSOR attributes on MintPy HDF5 files.

    Parameters
    ----------
    inputs_dir : str or Path
        MintPy ``inputs/`` directory produced by ``load_data``.
    old : str
        Expected current processor label. Files whose PROCESSOR attribute
        does not equal this value are skipped with an informational log
        entry (so re-running the fix is idempotent).
    new : str
        Replacement processor label (default ``isce``).
    target_files : iterable of str
        HDF5 files to patch. Default: ``ifgramStack.h5``,
        ``geometryRadar.h5``.
    dry_run : bool
        If True, only reports what would change without writing anything.
    require_lookup_datasets : bool
        If True, aborts when ``geometryRadar.h5`` lacks ``/latitude`` or
        ``/longitude`` datasets (without them the rename only defers the
        failure to the next step).

    Returns
    -------
    dict
        Summary with keys ``patched``, ``skipped``, ``errors`` and
        ``details`` (per-file outcome records).
    """
    h5py = _require_h5py()
    inputs_dir = Path(inputs_dir)

    if not inputs_dir.is_dir():
        raise PostProcessError(
            f"inputs directory does not exist: {inputs_dir}"
        )

    if require_lookup_datasets:
        _abort_if_lookup_missing(inputs_dir, target_files)

    summary = {
        "patched": 0,
        "skipped": 0,
        "errors": [],
        "details": [],
        "dry_run": dry_run,
    }

    for fname in target_files:
        path = inputs_dir / fname
        record = {"file": fname, "path": str(path), "action": None}

        if not path.is_file():
            record["action"] = "missing"
            record["message"] = f"{fname} not found; skipping."
            logger.warning(record["message"])
            summary["skipped"] += 1
            summary["details"].append(record)
            continue

        try:
            mode = "r" if dry_run else "r+"
            with h5py.File(path, mode) as f:
                before = _decode_attr(f.attrs.get("PROCESSOR"))
                before_insar = _decode_attr(f.attrs.get("INSAR_PROCESSOR"))

                if before == new:
                    record["action"] = "already"
                    record["message"] = (
                        f"{fname}: PROCESSOR is already {new!r}; skipping."
                    )
                    logger.info(record["message"])
                    summary["skipped"] += 1
                elif before != old:
                    record["action"] = "mismatch"
                    record["message"] = (
                        f"{fname}: PROCESSOR is {before!r}, expected {old!r}. "
                        "Skipping - pass --from to override."
                    )
                    logger.warning(record["message"])
                    summary["skipped"] += 1
                else:
                    if not dry_run:
                        for attr in PROCESSOR_ATTRS:
                            f.attrs[attr] = new
                    record["action"] = "patched" if not dry_run else "would_patch"
                    record["before"] = before
                    record["before_insar_processor"] = before_insar
                    record["after"] = new
                    record["message"] = (
                        f"{fname}: PROCESSOR {before!r} -> {new!r}"
                        + ("  [dry-run]" if dry_run else "")
                    )
                    logger.info(record["message"])
                    summary["patched"] += 1

        except OSError as exc:
            record["action"] = "error"
            record["message"] = f"{fname}: {exc}"
            logger.error(record["message"])
            summary["errors"].append(record)

        summary["details"].append(record)

    return summary


def _abort_if_lookup_missing(inputs_dir, target_files):
    """Refuse to patch if geometryRadar.h5 lacks /latitude or /longitude."""
    geom_name = "geometryRadar.h5"
    if geom_name not in target_files:
        return

    report = verify_inputs_dir(inputs_dir, target_files=(geom_name,))
    record = report[0]
    if not record["exists"]:
        return
    if record["has_lat_lon"] is False:
        raise PostProcessError(
            f"{geom_name} is missing /latitude and/or /longitude datasets. "
            "Renaming the processor attribute would only defer the failure. "
            f"Delete {record['path']} and re-run "
            "'smallbaselineApp.py --dostep load_data' so MintPy can rebuild "
            "the geometry file with the lookup tables, then apply the fix."
        )


def _decode_attr(value):
    """Decode an HDF5 attribute value to a plain Python string."""
    if value is None:
        return None
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return value.decode("latin-1", errors="replace")
    return str(value)
