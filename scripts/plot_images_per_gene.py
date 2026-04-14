#!/usr/bin/env python3
"""Histogram of image counts per gene in the Thisse dataset."""

import argparse
import collections
import json
import os
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def load_counts(json_path: Path) -> dict[str, int]:
    raw = json_path.read_text(encoding="utf-8")
    raw = re.sub(r"\bNaN\b", "null", raw)
    records = json.loads(raw)
    counts: dict[str, int] = collections.Counter(
        r["gene"]["gene_symbol"]
        for r in records
        if r.get("gene", {}).get("gene_symbol")
        and not r["gene"]["gene_symbol"].startswith("WITHDRAWN")
    )
    return counts


def plot(counts: dict[str, int], out_path: Path | None) -> None:
    values = list(counts.values())
    n_genes = len(values)
    n_images = sum(values)

    # Bin edges: 1, 2, 3–5, 6–10, 11–20, 21–50, 51–100, 101+
    bins = [1, 2, 3, 6, 11, 21, 51, 101, max(values) + 1]
    labels = ["1", "2", "3–5", "6–10", "11–20", "21–50", "51–100", "101+"]
    counts_per_bin = [
        sum(1 for v in values if bins[i] <= v < bins[i + 1])
        for i in range(len(bins) - 1)
    ]

    fig, ax = plt.subplots(figsize=(9, 5))

    bars = ax.bar(
        range(len(labels)),
        counts_per_bin,
        color="#2563eb",
        edgecolor="white",
        linewidth=0.6,
        width=0.7,
    )

    # Annotate bar tops
    for bar, count in zip(bars, counts_per_bin):
        if count > 0:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + n_genes * 0.005,
                f"{count:,}",
                ha="center", va="bottom", fontsize=8, color="#374151",
            )

    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_xlabel("Images per gene", fontsize=11, labelpad=8)
    ax.set_ylabel("Number of genes", fontsize=11, labelpad=8)
    ax.set_title(
        f"Distribution of image counts per gene — Thisse dataset\n"
        f"{n_genes:,} genes · {n_images:,} images total",
        fontsize=12, pad=12,
    )

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5, zorder=0)
    ax.set_axisbelow(True)

    # Summary stats annotation
    vals_sorted = sorted(values)
    median = vals_sorted[len(vals_sorted) // 2]
    mean = np.mean(values)
    ax.text(
        0.97, 0.95,
        f"Median: {median}  ·  Mean: {mean:.1f}  ·  Max: {max(values)}",
        transform=ax.transAxes, ha="right", va="top",
        fontsize=9, color="#6b7280",
    )

    plt.tight_layout()

    if out_path:
        fig.savefig(out_path, dpi=150, bbox_inches="tight")
        print(f"Saved to {out_path}")
    else:
        plt.show()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        default=os.environ.get("GENE2IMAGE_DATA_DIR", "/Users/vera.janssen/projects/gene2image_data"),
        help="Directory containing image_metadata.json",
    )
    parser.add_argument(
        "--out", "-o", type=Path, default=None,
        help="Save plot to this path (e.g. plot.png). Omit to display interactively.",
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
    counts = load_counts(json_path)
    print(f"  {len(counts):,} genes, {sum(counts.values()):,} images")
    plot(counts, args.out)


if __name__ == "__main__":
    main()
