#!/usr/bin/env python3
"""Barplots of distinct-gene counts per anatomy term in the Thisse dataset."""

import argparse
import collections
import csv
import json
import os
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


BAR_COLOR = "#2563eb"
ANNOT_COLOR = "#374151"
MUTED_COLOR = "#6b7280"


def load_anatomy_gene_counts(json_path: Path) -> dict[str, int]:
    """Return {anatomy_name: distinct_gene_count}."""
    raw = json_path.read_text(encoding="utf-8")
    raw = re.sub(r"\bNaN\b", "null", raw)
    records = json.loads(raw)

    anatomy_to_genes: dict[str, set[str]] = collections.defaultdict(set)
    all_genes: set[str] = set()
    for r in records:
        sym = (r.get("gene") or {}).get("gene_symbol", "")
        if not sym or sym.startswith("WITHDRAWN"):
            continue
        all_genes.add(sym)
        for loc in r.get("anatomical_locations") or []:
            name = loc.get("anatomy_name")
            if name:
                anatomy_to_genes[name].add(sym)

    counts = {name: len(genes) for name, genes in anatomy_to_genes.items()}
    return counts, len(all_genes), len(records)


def _style_axes(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.xaxis.grid(True, linestyle="--", alpha=0.5, zorder=0)
    ax.set_axisbelow(True)


def write_table(counts: dict[str, int], out_path: Path) -> None:
    sorted_items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["rank", "anatomy_name", "n_genes"])
        for rank, (name, count) in enumerate(sorted_items, start=1):
            writer.writerow([rank, name, count])
    print(f"Saved to {out_path}")


def plot_top50(counts: dict[str, int], n_genes: int, n_images: int, out_path: Path) -> None:
    sorted_items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    top = sorted_items[:50]
    names = [n for n, _ in top]
    values = [v for _, v in top]

    fig, ax = plt.subplots(figsize=(14, 10))
    y_pos = range(len(names))
    ax.barh(
        y_pos, values,
        color=BAR_COLOR, edgecolor="white", linewidth=0.6, height=0.75,
    )
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(names, fontsize=9)
    ax.invert_yaxis()

    ax.set_xlabel("Number of distinct genes", fontsize=11, labelpad=8)
    ax.set_title(
        f"Top 50 anatomy terms by gene coverage — Thisse dataset\n"
        f"{len(counts):,} total anatomy terms · {n_genes:,} genes · {n_images:,} images",
        fontsize=12, pad=12,
    )

    xmax = max(values)
    for i, v in enumerate(values):
        ax.text(
            v + xmax * 0.005, i,
            f"{v:,}",
            ha="left", va="center", fontsize=8, color=ANNOT_COLOR,
        )
    ax.set_xlim(0, xmax * 1.06)

    all_values = list(counts.values())
    vals_sorted = sorted(all_values)
    median = vals_sorted[len(vals_sorted) // 2]
    mean = np.mean(all_values)
    ax.text(
        0.97, 0.04,
        f"Across all {len(counts)} terms — "
        f"median: {median}  ·  mean: {mean:.1f}  ·  max: {max(all_values):,}",
        transform=ax.transAxes, ha="right", va="bottom",
        fontsize=9, color=MUTED_COLOR,
    )

    _style_axes(ax)
    plt.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved to {out_path}")


def plot_full(counts: dict[str, int], n_genes: int, n_images: int, out_path: Path) -> None:
    sorted_items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    names = [n for n, _ in sorted_items]
    values = [v for _, v in sorted_items]

    fig, ax = plt.subplots(figsize=(10, 36))
    y_pos = range(len(names))
    ax.barh(
        y_pos, values,
        color=BAR_COLOR, edgecolor="white", linewidth=0.5, height=0.7,
    )
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(names, fontsize=6.5)
    ax.invert_yaxis()

    ax.set_xlabel("Number of distinct genes", fontsize=11, labelpad=8)
    ax.set_title(
        f"Anatomy terms by gene coverage — Thisse dataset\n"
        f"{len(counts):,} anatomy terms · {n_genes:,} genes · {n_images:,} images",
        fontsize=12, pad=12,
    )

    _style_axes(ax)
    plt.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved to {out_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        default=os.environ.get(
            "GENE2IMAGE_DATA_DIR",
            "/Users/vera.janssen/projects/gene2image_data",
        ),
        help="Directory containing image_metadata.json",
    )
    parser.add_argument(
        "--out-dir", type=Path,
        default=Path("/Users/vera.janssen/projects/gene2image_data/results"),
        help="Directory to write PNG plots into",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    json_path = (
        data_dir / "image_metadata_v2.json"
        if (data_dir / "image_metadata_v2.json").exists()
        else data_dir / "image_metadata.json"
    )
    if not json_path.exists():
        raise FileNotFoundError(f"Data file not found: {json_path}")

    print(f"Loading {json_path} ...")
    counts, n_genes, n_images = load_anatomy_gene_counts(json_path)
    print(f"  {len(counts):,} anatomy terms · {n_genes:,} genes · {n_images:,} images")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_table(counts, args.out_dir / "genes_per_anatomy.csv")
    plot_top50(counts, n_genes, n_images, args.out_dir / "genes_per_anatomy_top50.png")
    plot_full(counts, n_genes, n_images, args.out_dir / "genes_per_anatomy_full.png")


if __name__ == "__main__":
    main()
