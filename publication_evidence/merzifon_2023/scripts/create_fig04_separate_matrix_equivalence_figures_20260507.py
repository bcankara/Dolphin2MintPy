from __future__ import annotations

import csv
import json
from pathlib import Path

import h5py
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap
from osgeo import gdal


ROOT = Path(r"W:\tubitak3501_merzifon")
OUT_DIR = ROOT / "07_article_figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SUMMARY_JSON = ROOT / "06_validation" / "stage5d_matrix_equivalence_summary_20260507.json"
PAIR_CSV = ROOT / "06_validation" / "stage5d_matrix_equivalence_pairs_20260507.csv"
IFGRAM_H5 = ROOT / "05_mintpy" / "aoi_crop_cpu_prod" / "inputs" / "ifgramStack.h5"
UNW_DIR = ROOT / "03_dolphin" / "aoi_crop_cpu_prod" / "work" / "unwrapped"

PAIR = "20230110_20230122"
DATASET_FOR_TILE = "unwrapPhase"
TILE_SIZE = 512

OUT_TILE_PNG = OUT_DIR / "fig04a_representative_tile_dolphin_vs_mintpy_300dpi.png"
OUT_TILE_PDF = OUT_DIR / "fig04a_representative_tile_dolphin_vs_mintpy_300dpi.pdf"
OUT_DIFF_PNG = OUT_DIR / "fig04b_absolute_difference_tile_300dpi.png"
OUT_DIFF_PDF = OUT_DIR / "fig04b_absolute_difference_tile_300dpi.pdf"
OUT_MATRIX_PNG = OUT_DIR / "fig04c_full_stack_validation_matrix_300dpi.png"
OUT_MATRIX_PDF = OUT_DIR / "fig04c_full_stack_validation_matrix_300dpi.pdf"
OUT_CAPTION = OUT_DIR / "fig04_separate_matrix_equivalence_captions.txt"


def read_summary() -> dict:
    return json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))


def read_pair_rows() -> list[dict]:
    with PAIR_CSV.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def decode_date(value) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


def h5_pair_index(pair: str) -> int:
    with h5py.File(IFGRAM_H5, "r") as f:
        dates = f["date"][()]
    for idx, row in enumerate(dates):
        row_pair = f"{decode_date(row[0])}_{decode_date(row[1])}"
        if row_pair == pair:
            return idx
    raise ValueError(f"Pair not found in HDF5 /date: {pair}")


def open_source_raster(pair: str):
    path = UNW_DIR / f"{pair}.unw.tif"
    ds = gdal.Open(str(path), gdal.GA_ReadOnly)
    if ds is None:
        raise RuntimeError(f"Could not open source raster: {path}")
    return path, ds


def read_source_tile(ds, yoff: int, xoff: int, size: int) -> np.ndarray:
    arr = ds.GetRasterBand(1).ReadAsArray(xoff, yoff, size, size)
    if arr is None:
        raise RuntimeError("GDAL ReadAsArray returned None")
    return np.asarray(arr)


def read_h5_tile(pair_index: int, yoff: int, xoff: int, size: int) -> np.ndarray:
    with h5py.File(IFGRAM_H5, "r") as f:
        arr = f[DATASET_FOR_TILE][pair_index, yoff : yoff + size, xoff : xoff + size]
    return np.asarray(arr)


def choose_tile(ds, pair_index: int, size: int) -> tuple[int, int, np.ndarray, np.ndarray]:
    width = ds.RasterXSize
    height = ds.RasterYSize
    candidates = [
        ((height - size) // 2, (width - size) // 2),
        (height // 3, width // 3),
        (height // 3, (2 * width) // 3 - size),
        ((2 * height) // 3 - size, width // 3),
        ((2 * height) // 3 - size, (2 * width) // 3 - size),
        (height // 2 - size // 2, width // 4),
        (height // 2 - size // 2, (3 * width) // 4 - size),
    ]
    best = None
    best_score = -np.inf
    for yoff, xoff in candidates:
        yoff = int(np.clip(yoff, 0, height - size))
        xoff = int(np.clip(xoff, 0, width - size))
        src = read_source_tile(ds, yoff, xoff, size)
        h5_tile = read_h5_tile(pair_index, yoff, xoff, size)
        finite = np.isfinite(src) & np.isfinite(h5_tile)
        if not np.any(finite):
            score = -np.inf
        else:
            score = float(np.nanstd(src[finite])) + 0.01 * float(np.count_nonzero(finite)) / src.size
        if score > best_score:
            best_score = score
            best = (yoff, xoff, src, h5_tile)
    if best is None:
        raise RuntimeError("No readable tile candidate found")
    return best


def robust_limits(arr: np.ndarray) -> tuple[float, float]:
    valid = arr[np.isfinite(arr)]
    if valid.size == 0:
        return 0.0, 1.0
    lo, hi = np.percentile(valid, [2, 98])
    if not np.isfinite(lo) or not np.isfinite(hi) or lo == hi:
        lo = float(np.nanmin(valid))
        hi = float(np.nanmax(valid))
    if lo == hi:
        hi = lo + 1.0
    return float(lo), float(hi)


def build_pass_matrix(rows: list[dict]) -> tuple[list[str], list[str], np.ndarray]:
    datasets = ["unwrapPhase", "coherence", "connectComponent"]
    pairs = []
    seen = set()
    for row in rows:
        pair = row["pair"]
        if pair not in seen:
            seen.add(pair)
            pairs.append(pair)
    matrix = np.zeros((len(pairs), len(datasets)), dtype=int)
    lookup = {(row["pair"], row["dataset"]): row["status"] for row in rows}
    for i, pair in enumerate(pairs):
        for j, dataset in enumerate(datasets):
            matrix[i, j] = 1 if lookup.get((pair, dataset)) == "PASS" else 0
    return pairs, datasets, matrix


def save_tile_comparison(src_tile: np.ndarray, h5_tile: np.ndarray, vmin: float, vmax: float) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.6), constrained_layout=True)
    for ax, arr, title in [
        (axes[0], src_tile, f"Dolphin GeoTIFF\n{PAIR}"),
        (axes[1], h5_tile, "MintPy HDF5\nifgramStack:/unwrapPhase"),
    ]:
        im = ax.imshow(arr, cmap="viridis", vmin=vmin, vmax=vmax)
        ax.set_title(title)
        ax.set_xticks([])
        ax.set_yticks([])
    cbar = fig.colorbar(im, ax=axes, fraction=0.035, pad=0.025)
    cbar.ax.set_ylabel("unwrapped phase", rotation=90, labelpad=7)
    fig.suptitle("Representative matrix tile comparison", fontweight="bold")
    fig.savefig(OUT_TILE_PNG, dpi=300)
    fig.savefig(OUT_TILE_PDF, dpi=300)
    plt.close(fig)


def save_difference_figure(abs_diff: np.ndarray) -> None:
    max_abs = float(np.nanmax(abs_diff))
    dmax = max(max_abs, 1e-12)
    fig, ax = plt.subplots(1, 1, figsize=(4.6, 4.0), constrained_layout=True)
    im = ax.imshow(abs_diff, cmap="magma", vmin=0.0, vmax=dmax)
    subtitle = "all pixels exact match" if max_abs == 0.0 else f"max={max_abs:.1e}"
    ax.set_title(f"Absolute difference tile\n{subtitle}")
    ax.set_xticks([])
    ax.set_yticks([])
    if max_abs == 0.0:
        ax.text(
            0.5,
            0.5,
            "all 512 x 512 pixels\nexactly equal",
            color="white",
            ha="center",
            va="center",
            transform=ax.transAxes,
            fontsize=10,
            fontweight="bold",
        )
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.025)
    cbar.ax.set_ylabel("|MintPy HDF5 - Dolphin GeoTIFF|", rotation=90, labelpad=7)
    if max_abs == 0.0:
        cbar.set_ticks([0.0])
        cbar.set_ticklabels(["0"])
    fig.savefig(OUT_DIFF_PNG, dpi=300)
    fig.savefig(OUT_DIFF_PDF, dpi=300)
    plt.close(fig)


def save_validation_matrix(summary: dict, rows: list[dict]) -> None:
    pairs, datasets, matrix = build_pass_matrix(rows)
    by_dataset = summary["by_dataset"]

    fig, ax = plt.subplots(1, 1, figsize=(5.8, 7.2), constrained_layout=True)
    cmap = ListedColormap(["#d9534f", "#2ca25f"])
    ax.imshow(matrix, aspect="auto", cmap=cmap, vmin=0, vmax=1)
    ax.set_title("Full-stack matrix-equivalence validation", fontweight="bold")
    ax.set_xticks(range(len(datasets)))
    ax.set_xticklabels(["unwrapPhase", "coherence", "connectComponent"], rotation=25, ha="right")
    label_positions = [0, len(pairs) // 4, len(pairs) // 2, 3 * len(pairs) // 4, len(pairs) - 1]
    ax.set_yticks(label_positions)
    ax.set_yticklabels([pairs[i] for i in label_positions])
    ax.set_ylabel("date pairs")
    ax.tick_params(length=0)
    ax.set_xlabel("loaded datasets")
    for j, dataset in enumerate(datasets):
        ax.text(
            j,
            3,
            f"{by_dataset[dataset]['pass']}/84 PASS",
            ha="center",
            va="center",
            fontsize=8,
            color="white",
            fontweight="bold",
        )
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.savefig(OUT_MATRIX_PNG, dpi=300)
    fig.savefig(OUT_MATRIX_PDF, dpi=300)
    plt.close(fig)


def write_captions(yoff: int, xoff: int, abs_diff: np.ndarray) -> None:
    caption = (
        "Fig. 4a Representative 512 x 512 matrix tile comparison for date pair "
        f"{PAIR}. The left panel is read from the Dolphin unwrapped-phase GeoTIFF, "
        "and the right panel is read from MintPy ifgramStack.h5:/unwrapPhase after "
        "Dolphin2MintPy preparation.\n"
        "Fig. 4b Absolute pixel-wise difference for the same representative tile. "
        f"The selected tile offset is x={xoff}, y={yoff}; the maximum absolute "
        f"difference is {float(np.nanmax(abs_diff)):.1e}.\n"
        "Fig. 4c Full-stack matrix-equivalence validation without tabular panels. "
        "All 84 date pairs passed for unwrapPhase, coherence, and connectComponent."
    )
    OUT_CAPTION.write_text(caption + "\n", encoding="utf-8")


def main() -> None:
    mpl.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8,
            "axes.titlesize": 9,
            "axes.labelsize": 8,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "figure.dpi": 300,
            "savefig.dpi": 300,
        }
    )

    summary = read_summary()
    rows = read_pair_rows()
    pair_index = h5_pair_index(PAIR)
    src_path, ds = open_source_raster(PAIR)
    yoff, xoff, src_tile, h5_tile = choose_tile(ds, pair_index, TILE_SIZE)
    abs_diff = np.abs(h5_tile.astype(np.float64) - src_tile.astype(np.float64))
    vmin, vmax = robust_limits(src_tile)

    save_tile_comparison(src_tile, h5_tile, vmin, vmax)
    save_difference_figure(abs_diff)
    save_validation_matrix(summary, rows)
    write_captions(yoff, xoff, abs_diff)

    print(f"TILE_PNG={OUT_TILE_PNG}")
    print(f"TILE_PDF={OUT_TILE_PDF}")
    print(f"DIFF_PNG={OUT_DIFF_PNG}")
    print(f"DIFF_PDF={OUT_DIFF_PDF}")
    print(f"MATRIX_PNG={OUT_MATRIX_PNG}")
    print(f"MATRIX_PDF={OUT_MATRIX_PDF}")
    print(f"CAPTION={OUT_CAPTION}")
    print(f"source_raster={src_path}")
    print(f"tile_pair={PAIR}")
    print(f"tile_offset_x={xoff}")
    print(f"tile_offset_y={yoff}")
    print(f"tile_size={TILE_SIZE}")
    print(f"tile_max_abs_diff={float(np.nanmax(abs_diff))}")


if __name__ == "__main__":
    main()
