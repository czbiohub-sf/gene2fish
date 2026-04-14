#!/usr/bin/env python3
"""Faceted histogram of images-per-gene, one panel per developmental stage."""

import argparse
import collections
import json
import os
import re
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np


# Canonical stage order (begin_hours) — only stages present in the dataset will be shown
STAGE_ORDER = [
    "Zygote:1-cell",
    "Cleavage:2-cell", "Cleavage:4-cell", "Cleavage:8-cell",
    "Cleavage:16-cell", "Cleavage:32-cell", "Cleavage:64-cell", "Cleavage:128-cell",
    "Blastula:256-cell", "Blastula:512-cell", "Blastula:1k-cell",
    "Blastula:High", "Blastula:Oblong", "Blastula:Sphere", "Blastula:Dome",
    "Gastrula:30%-epiboly", "Gastrula:50%-epiboly", "Gastrula:Germ-ring",
    "Gastrula:Shield", "Gastrula:75%-epiboly", "Gastrula:90%-epiboly", "Gastrula:Bud",
    "Segmentation:1-4 somites", "Segmentation:5-9 somites",
    "Segmentation:10-13 somites", "Segmentation:14-19 somites",
    "Segmentation:20-25 somites",
    "Pharyngula:Prim-5", "Pharyngula:Prim-15", "Pharyngula:Prim-25", "Pharyngula:High-pec",
    "Hatching:Long-pec", "Hatching:Pec-fin",
    "Larval:Protruding-mouth", "Larval:Day 4", "Larval:Day 5",
    "Adult",
]

DISPLAY_LABELS = {
    "Zygote:1-cell": "1-cell",
    "Blastula:Sphere": "Sphere",
    "Gastrula:50%-epiboly": "50%-epiboly",
    "Gastrula:Bud": "Bud",
    "Segmentation:1-4 somites": "1–4 somites",
    "Segmentation:5-9 somites": "5–9 somites",
    "Segmentation:10-13 somites": "10–13 somites",
    "Segmentation:14-19 somites": "14–19 somites",
    "Segmentation:20-25 somites": "20–25 somites",
    "Pharyngula:Prim-5": "Prim-5 (24 hpf)",
    "Pharyngula:Prim-15": "Prim-15 (30 hpf)",
    "Pharyngula:Prim-25": "Prim-25 (36 hpf)",
    "Pharyngula:High-pec": "High-pec (42 hpf)",
    "Hatching:Long-pec": "Long-pec (48 hpf)",
    "Larval:Protruding-mouth": "Prot.-mouth (72 hpf)",
    "Larval:Day 4": "Day 4 (96 hpf)",
    "Larval:Day 5": "Day 5 (120 hpf)",
    "Adult": "Adult",
}

BINS = [1, 2, 3, 6, 11, 21, 51, 200]
BIN_LABELS = ["1", "2", "3–5", "6–10", "11–20", "21–50", "51+"]


def load_stage_gene_counts(json_path: Path) -> dict[str, dict[str, int]]:
    """Return {stage_name: {gene_symbol: image_count}}."""
    raw = json_path.read_text(encoding="utf-8")
    raw = re.sub(r"\bNaN\b", "null", raw)
    records = json.loads(raw)

    # stage → gene → count
    data: dict[str, dict[str, int]] = collections.defaultdict(
        lambda: collections.defaultdict(int)
    )
    for r in records:
        sym = (r.get("gene") or {}).get("gene_symbol", "")
        if not sym or sym.startswith("WITHDRAWN"):
            continue
        for s in r.get("developmental_stages", []):
            name = s.get("stage_name")
            if name:
                data[name][sym] += 1

    return data


def bin_counts(gene_counts: dict[str, int]) -> list[int]:
    vals = list(gene_counts.values())
    return [
        sum(1 for v in vals if BINS[i] <= v < BINS[i + 1])
        for i in range(len(BINS) - 1)
    ]


def plot(data: dict[str, dict[str, int]], out_path: Path | None) -> None:
    # Only stages present in data, in canonical order
    present = [s for s in STAGE_ORDER if s in data]
    n = len(present)

    # Layout: up to 4 columns
    ncols = 4
    nrows = int(np.ceil(n / ncols))

    fig = plt.figure(figsize=(ncols * 3.2, nrows * 2.8))
    fig.suptitle(
        "Images per gene by developmental stage — Thisse dataset",
        fontsize=13, fontweight="bold", y=1.01,
    )

    for idx, stage in enumerate(present):
        ax = fig.add_subplot(nrows, ncols, idx + 1)
        gene_counts = data[stage]
        binned = bin_counts(gene_counts)
        n_genes = sum(binned)
        n_images = sum(gene_counts.values())

        bars = ax.bar(
            range(len(BIN_LABELS)), binned,
            color="#2563eb", edgecolor="white", linewidth=0.5, width=0.7,
        )

        label = DISPLAY_LABELS.get(stage, stage.split(":")[-1])
        ax.set_title(label, fontsize=9, fontweight="bold", pad=4)
        ax.set_xticks(range(len(BIN_LABELS)))
        ax.set_xticklabels(BIN_LABELS, fontsize=6.5, rotation=30, ha="right")
        ax.tick_params(axis="y", labelsize=7)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.yaxis.grid(True, linestyle="--", alpha=0.4, zorder=0)
        ax.set_axisbelow(True)

        ax.text(
            0.97, 0.97,
            f"{n_genes:,} genes\n{n_images:,} images",
            transform=ax.transAxes, ha="right", va="top",
            fontsize=6.5, color="#6b7280", linespacing=1.4,
        )

    # Hide any unused subplots
    total_slots = nrows * ncols
    for idx in range(n, total_slots):
        fig.add_subplot(nrows, ncols, idx + 1).set_visible(False)

    fig.text(0.5, -0.01, "Images per gene", ha="center", fontsize=10)
    fig.text(-0.01, 0.5, "Number of genes", va="center", rotation="vertical", fontsize=10)

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
        default=os.environ.get(
            "GENE2IMAGE_DATA_DIR",
            "/Users/vera.janssen/projects/gene2image_data",
        ),
    )
    parser.add_argument("--out", "-o", type=Path, default=None)
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    json_path = (
        data_dir / "image_metadata_v2.json"
        if (data_dir / "image_metadata_v2.json").exists()
        else data_dir / "image_metadata.json"
    )
    print(f"Loading {json_path} ...")
    data = load_stage_gene_counts(json_path)
    present = [s for s in STAGE_ORDER if s in data]
    print(f"  Stages with data: {len(present)}")
    plot(data, args.out)


if __name__ == "__main__":
    main()
