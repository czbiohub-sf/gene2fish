"""Canonical zebrafish developmental stage list and utilities."""

from __future__ import annotations

# Each entry: (stage_name, begin_hours, display_label)
CANONICAL_STAGES: list[tuple[str, float, str]] = [
    ("Zygote:1-cell",               0.00,    "unspecified"),
    ("Cleavage:2-cell",             0.75,    "2-cell"),
    ("Cleavage:4-cell",             1.00,    "4-cell"),
    ("Cleavage:8-cell",             1.25,    "8-cell"),
    ("Cleavage:16-cell",            1.50,    "16-cell"),
    ("Cleavage:32-cell",            1.75,    "32-cell"),
    ("Cleavage:64-cell",            2.00,    "64-cell"),
    ("Cleavage:128-cell",           2.25,    "128-cell"),
    ("Blastula:256-cell",           2.50,    "256-cell"),
    ("Blastula:512-cell",           2.75,    "512-cell"),
    ("Blastula:1k-cell",            3.00,    "1k-cell"),
    ("Blastula:High",               3.33,    "High"),
    ("Blastula:Oblong",             3.67,    "Oblong"),
    ("Blastula:Sphere",             4.00,    "Sphere"),
    ("Blastula:Dome",               4.33,    "Dome"),
    ("Gastrula:30%-epiboly",        4.67,    "30%-epiboly"),
    ("Gastrula:50%-epiboly",        5.25,    "50%-epiboly"),
    ("Gastrula:Germ-ring",          5.67,    "Germ-ring"),
    ("Gastrula:Shield",             6.00,    "Shield"),
    ("Gastrula:75%-epiboly",        8.00,    "75%-epiboly"),
    ("Gastrula:90%-epiboly",        9.00,    "90%-epiboly"),
    ("Gastrula:Bud",                10.00,   "Bud"),
    ("Segmentation:1-4 somites",    10.33,   "1-4 somites"),
    ("Segmentation:5-9 somites",    11.67,   "5-9 somites"),
    ("Segmentation:10-13 somites",  14.00,   "10-13 somites"),
    ("Segmentation:14-19 somites",  16.00,   "14-19 somites"),
    ("Segmentation:20-25 somites",  19.00,   "20-25 somites"),
    ("Pharyngula:Prim-5",           24.00,   "Prim-5 (24 hpf)"),
    ("Pharyngula:Prim-15",          30.00,   "Prim-15 (30 hpf)"),
    ("Pharyngula:Prim-25",          36.00,   "Prim-25 (36 hpf)"),
    ("Pharyngula:High-pec",         42.00,   "High-pec (42 hpf)"),
    ("Hatching:Long-pec",           48.00,   "Long-pec (48 hpf)"),
    ("Hatching:Pec-fin",            60.00,   "Pec-fin (60 hpf)"),
    ("Larval:Protruding-mouth",     72.00,   "Protruding-mouth (72 hpf)"),
    ("Larval:Day 4",                96.00,   "Day 4 (96 hpf)"),
    ("Larval:Day 5",                120.00,  "Day 5 (120 hpf)"),
    ("Adult",                       2160.00, "Adult"),
]

# Map begin_hours → (stage_name, display_label) for fast lookup
_HOURS_TO_STAGE: dict[float, tuple[str, str]] = {
    h: (name, label) for name, h, label in CANONICAL_STAGES
}

_CANONICAL_HOURS: list[float] = [h for _, h, _ in CANONICAL_STAGES]


def assign_canonical_stage(image: dict) -> float | None:
    """Return the begin_hours of the nearest canonical stage for an image.

    After the extractor fix, each image's developmental_stages list contains
    only the stages specific to that image (via its expression_result_ids).
    We take the minimum begin_hours to get the primary/start stage.
    Returns None if the image has no stage data.
    """
    stages = image.get("developmental_stages") or []
    hours_values = []
    for s in stages:
        bh = s.get("begin_hours")
        if bh is not None:
            try:
                hours_values.append(float(bh))
            except (ValueError, TypeError):
                pass

    if not hours_values:
        return None

    min_hours = min(hours_values)
    return min(_CANONICAL_HOURS, key=lambda h: abs(h - min_hours))


def get_stage_info(canonical_hours: float) -> tuple[str, str]:
    """Return (stage_name, display_label) for a canonical begin_hours value."""
    return _HOURS_TO_STAGE[canonical_hours]


def _score_image(img: dict) -> tuple[int, int]:
    """Score an image for ranking: (is_whole_mount, anatomy_term_count)."""
    is_whole_mount = int(
        (img.get("image_info") or {}).get("image_preparation", "") == "whole-mount"
    )
    anatomy_count = len(img.get("anatomical_locations") or [])
    return (is_whole_mount, anatomy_count)


def select_representative(images: list[dict]) -> dict:
    """Pick the best representative image from a list at the same canonical stage.

    Priority:
    1. image_preparation == "whole-mount"
    2. Most anatomy terms
    3. First encountered
    """
    if not images:
        raise ValueError("Empty image list")

    return max(images, key=_score_image)


def select_top_n(images: list[dict], n: int) -> list[dict]:
    """Return up to n best-ranked images from a list at the same canonical stage.

    Priority: whole-mount first, then most anatomy terms, then highest image ID
    (descending) so that later-acquired images — which tend to show more varied
    orientations — appear before earlier ones.
    """
    if not images:
        return []
    ranked = sorted(
        images,
        key=lambda img: (_score_image(img), img.get("image_id", "")),
        reverse=True,
    )
    return ranked[:n]
