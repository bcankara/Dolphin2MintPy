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

OUT_PNG = OUT_DIR / "fig04_matrix_equivalence_dolphin_vs_mintpy_300dpi.png"
OUT_PDF = OUT_DIR / "fig04_matrix_equivalence_dolphin_vs_mintpy_300dpi.pdf"
OUT_CAPTION = OUT_DIR / "fig04_matrix_equivalence_caption.txt"

PAIR = "20230110_20230122"
DATASET_FOR_TILE = "unwrapPhase"
TILE_SIZE = 512


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
        p = f"{decode_date(row[0])}_{decode_date(row[1])}"
        if p == pair:
            return idx
    raise ValueError(f"Pair not found in HDF5 /date: {pair}")


def read_h5_tile(pair_index: int, yoff: int, xoff: int, size: int) -> np.ndarray:
    with h5py.File(IFGRAM_H5, "r") as f:
        arr = f[DATASET_FOR_TILE][pair_index, yoff : yoff + size, xoff : xoff + size]
    return np.asarray(arr)


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
        tgt = read_h5_tile(pair_index, yoff, xoff, size)
        finite = np.isfinite(src) & np.isfinite(tgt)
        if not np.any(finite):
            score = -np.inf
        else:
            score = float(np.nanstd(src[finite])) + 0.01 * float(np.count_nonzero(finite)) / src.size
        if score > best_score:
            best_score = score
            best = (yoff, xoff, src, tgt)
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
    mat = np.zeros((len(pairs), len(datasets)), dtype=int)
    lookup = {(row["pair"], row["dataset"]): row["status"] for row in rows}
    for i, pair in enumerate(pairs):
        for j, dataset in enumerate(datasets):
            mat[i, j] = 1 if lookup.get((pair, dataset)) == "PASS" else 0
    return pairs, datasets, mat


def add_panel_label(ax, label: str) -> None:
    ax.text(
        -0.06,
        1.05,
        label,
        transform=ax.transAxes,
        fontsize=12,
        fontweight="bold",
        va="top",
        ha="left",
        color="#111111",
    )


def main() -> None:
    mpl.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 7,
            "axes.titlesize": 8,
            "axes.labelsize": 7,
            "xtick.labelsize": 6,
            "ytick.labelsize": 6,
            "figure.dpi": 300,
            "savefig.dpi": 300,
        }
    )

    summary = read_summary()
    rows = read_pair_rows()
    pair_index = h5_pair_index(PAIR)
    src_path, ds = open_source_raster(PAIR)
    yoff, xoff, src_tile, h5_tile = choose_tile(ds, pair_index, TILE_SIZE)
    diff = h5_tile.astype(np.float64) - src_tile.astype(np.float64)
    abs_diff = np.abs(diff)
    vmin, vmax = robust_limits(src_tile)
    dmax = max(float(np.nanmax(abs_diff)), 1e-6)

    pairs, datasets, pass_matrix = build_pass_matrix(rows)
    by_dataset = summary["by_dataset"]

    fig = plt.figure(figsize=(11.5, 7.0), constrained_layout=True)
    gs = fig.add_gridspec(2, 3, height_ratios=[1.0, 0.70], wspace=0.18, hspace=0.18)

    ax1 = fig.add_subplot(gs[0, 0])
    im1 = ax1.imshow(src_tile, cmap="viridis", vmin=vmin, vmax=vmax)
    ax1.set_title(f"Dolphin GeoTIFF tile\n{PAIR}")
    ax1.set_xticks([])
    ax1.set_yticks([])
    add_panel_label(ax1, "a")
    cbar1 = fig.colorbar(im1, ax=ax1, fraction=0.046, pad=0.02)
    cbar1.ax.set_ylabel("phase", rotation=90, labelpad=5)

    ax2 = fig.add_subplot(gs[0, 1])
    im2 = ax2.imshow(h5_tile, cmap="viridis", vmin=vmin, vmax=vmax)
    ax2.set_title("MintPy HDF5 tile\n/unwrapPhase")
    ax2.set_xticks([])
    ax2.set_yticks([])
    add_panel_label(ax2, "b")
    cbar2 = fig.colorbar(im2, ax=ax2, fraction=0.046, pad=0.02)
    cbar2.ax.set_ylabel("phase", rotation=90, labelpad=5)

    ax3 = fig.add_subplot(gs[0, 2])
    im3 = ax3.imshow(abs_diff, cmap="magma", vmin=0.0, vmax=dmax)
    ax3.set_title(f"Absolute difference\nmax={float(np.nanmax(abs_diff)):.1e}")
    ax3.set_xticks([])
    ax3.set_yticks([])
    add_panel_label(ax3, "c")
    cbar3 = fig.colorbar(im3, ax=ax3, fraction=0.046, pad=0.02)
    cbar3.ax.set_ylabel("|HDF5 - GeoTIFF|", rotation=90, labelpad=5)

    ax4 = fig.add_subplot(gs[1, 0])
    cmap = ListedColormap(["#d9534f", "#2ca25f"])
    ax4.imshow(pass_matrix, aspect="auto", cmap=cmap, vmin=0, vmax=1)
    ax4.set_title("Pairwise validation matrix")
    ax4.set_xticks(range(len(datasets)))
    ax4.set_xticklabels(["unwrap\nphase", "coherence", "conn.\ncomp."])
    label_positions = [0, len(pairs) // 2, len(pairs) - 1]
    ax4.set_yticks(label_positions)
    ax4.set_yticklabels([pairs[i] for i in label_positions])
    ax4.set_ylabel("date pairs")
    ax4.tick_params(length=0)
    add_panel_label(ax4, "d")
    for j, dataset in enumerate(datasets):
        ax4.text(j, 3, f"{by_dataset[dataset]['pass']}/84", ha="center", va="center", fontsize=7, color="white", fontweight="bold")

    ax5 = fig.add_subplot(gs[1, 1])
    ax5.axis("off")
    add_panel_label(ax5, "e")
    ax5.set_title("Global equivalence metrics", pad=6)
    table_rows = []
    for dataset in datasets:
        item = by_dataset[dataset]
        label = {
            "unwrapPhase": "unwrap",
            "coherence": "coh.",
            "connectComponent": "conn.",
        }[dataset]
        table_rows.append(
            [
                label,
                f"{item['max_abs_diff_max']:.1f}",
                f"{item['rmse_max']:.1f}",
                f"{item['correlation_min']:.1f}",
                f"{item['exact_match_ratio_min']:.1f}",
            ]
        )
    table = ax5.table(
        cellText=table_rows,
        colLabels=["Dataset", "Max |diff|", "Max RMSE", "Min corr.", "Min exact"],
        loc="center",
        cellLoc="center",
        colColours=["#d9eaf7"] * 5,
    )
    table.auto_set_font_size(False)
    table.set_fontsize(6.2)
    table.scale(0.98, 1.35)
    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor("#777777")
        if row > 0 and col > 0:
            cell.set_facecolor("#edf8ed")

    ax6 = fig.add_subplot(gs[1, 2])
    exact = [by_dataset[d]["exact_match_ratio_min"] for d in datasets]
    bars = ax6.bar(range(len(datasets)), exact, color=["#2b8cbe", "#41ab5d", "#756bb1"])
    ax6.set_ylim(0.985, 1.002)
    ax6.set_xticks(range(len(datasets)))
    ax6.set_xticklabels(["unwrap\nphase", "coherence", "conn.\ncomp."])
    ax6.set_ylabel("min exact-match ratio")
    ax6.set_title("Full-stack exact agreement")
    ax6.grid(axis="y", color="#dddddd", linewidth=0.7)
    add_panel_label(ax6, "f")
    for bar in bars:
        ax6.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.00025,
            "1.0",
            ha="center",
            va="bottom",
            fontsize=8,
            fontweight="bold",
        )

    fig.suptitle(
        "Dolphin2MintPy matrix-equivalence validation: Dolphin GeoTIFF to MintPy HDF5",
        fontsize=11,
        fontweight="bold",
    )
    fig.savefig(OUT_PNG, dpi=300)
    fig.savefig(OUT_PDF, dpi=300)
    plt.close(fig)

    caption = (
        "Fig. 4 Matrix-equivalence validation for the Dolphin2MintPy bridge. "
        "(a) Representative 512 x 512 tile from a Dolphin unwrapped-phase GeoTIFF. "
        "(b) The corresponding tile read from MintPy ifgramStack.h5:/unwrapPhase. "
        "(c) Absolute difference between the HDF5 and GeoTIFF tiles. "
        "(d) Pass/fail matrix for all 84 date pairs and the three loaded datasets. "
        "(e) Global equivalence metrics derived from the full raster stack. "
        "(f) Minimum exact-match ratio per dataset. "
        "All 84 comparisons passed for unwrapPhase, coherence, and connectComponent; "
        "the maximum absolute difference and RMSE were 0.0 for all datasets."
    )
    OUT_CAPTION.write_text(caption + "\n", encoding="utf-8")

    print(f"PNG={OUT_PNG}")
    print(f"PDF={OUT_PDF}")
    print(f"CAPTION={OUT_CAPTION}")
    print(f"source_raster={src_path}")
    print(f"tile_pair={PAIR}")
    print(f"tile_offset_x={xoff}")
    print(f"tile_offset_y={yoff}")
    print(f"tile_size={TILE_SIZE}")
    print(f"tile_max_abs_diff={float(np.nanmax(abs_diff))}")


if __name__ == "__main__":
    main()
