"""Guard the build-time data validation gate.

The Docker build bakes ``image_metadata.json`` by running the extractor. If a
download silently truncates, or a ZFIN TSV format drifts, ``load_tsv()`` swallows
the error and returns an empty DataFrame -- so without a guard the extractor
would write an empty/partial index and still exit 0, shipping an image that
starts healthy but returns no gene data.

``--min-records`` gates that path: the extractor must exit non-zero (failing the
build) when it produces fewer than the required number of records.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "zfin_image_metadata_extractor.py"

sys.path.insert(0, str(REPO_ROOT))
import pandas as pd  # noqa: E402

from zfin_image_metadata_extractor import (  # noqa: E402
    REQUIRED_FILES,
    build_alias_map,
)


def _make_zfin_dir(tmp_path: Path, n_images: int) -> Path:
    """Build a minimal ``zfin_data`` dir: every required file exists, and
    ImageFigures has ``n_images`` data rows behind ZFIN's date + header lines.

    With ``--all-images`` the extractor derives the image set from
    ImageFigures.txt, so the other (empty) files are enough to satisfy the
    presence check while yielding exactly ``n_images`` output records.
    """
    data_dir = tmp_path / "zfin_data"
    data_dir.mkdir()
    for name in REQUIRED_FILES:
        (data_dir / name).touch()

    lines = ["! date stamp", "Image ID\tFigure ID\tImage Preparation"]
    for i in range(n_images):
        lines.append(f"ZDB-IMAGE-{i}\tZDB-FIG-{i}\twhole mount")
    (data_dir / "ImageFigures.txt").write_text("\n".join(lines) + "\n")
    return data_dir


def _run(data_dir: Path, out_prefix: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--input-dir",
            str(data_dir),
            "--output-prefix",
            str(out_prefix),
            "--no-download",
            "--all-images",
            *extra,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )


def test_min_records_fails_build_when_below_threshold(tmp_path):
    data_dir = _make_zfin_dir(tmp_path, n_images=5)
    result = _run(data_dir, tmp_path / "out", "--min-records", "10")
    output = result.stdout + result.stderr
    assert result.returncode == 1, output
    assert "record" in output.lower(), output
    # A failed gate must not leave a bad artifact behind.
    assert not (tmp_path / "out.json").exists(), "must not write output when gate fails"


def test_min_records_passes_when_at_threshold(tmp_path):
    data_dir = _make_zfin_dir(tmp_path, n_images=5)
    result = _run(data_dir, tmp_path / "out", "--min-records", "5")
    assert result.returncode == 0, result.stdout + result.stderr
    records = json.loads((tmp_path / "out.json").read_text())
    assert len(records) == 5


def test_no_min_records_preserves_exit_zero_on_empty(tmp_path):
    """Without the flag the existing behavior is unchanged: an empty result set
    still exits 0 (so ad-hoc runs and single-image extractions are not gated)."""
    data_dir = _make_zfin_dir(tmp_path, n_images=0)
    result = _run(data_dir, tmp_path / "out")
    assert result.returncode == 0, result.stdout + result.stderr


def test_build_alias_map_scopes_to_dataset_genes_and_dedups():
    aliases_df = pd.DataFrame(
        {
            "Current ZFIN ID": [
                "ZDB-GENE-1", "ZDB-GENE-1", "ZDB-GENE-1",  # in dataset
                "ZDB-GENE-1",                               # duplicate previous name
                "ZDB-GENE-2",                               # not in dataset
                "ZDB-ALT-9",                                # not a gene we have
            ],
            "Current Name": [None] * 6,
            "Current Symbol": ["pou5f3"] * 4 + ["other", "alt"],
            "Previous Name": ["oct4", "pou2", "pou5f1", "oct4", "xyz", "moe"],
            "SO ID": [None] * 6,
        }
    )

    alias_map = build_alias_map(aliases_df, {"ZDB-GENE-1"})

    # Only the dataset gene is kept, previous names de-duplicated and sorted.
    assert alias_map == {"ZDB-GENE-1": ["oct4", "pou2", "pou5f1"]}


def test_build_alias_map_skips_missing_previous_names():
    aliases_df = pd.DataFrame(
        {
            "Current ZFIN ID": ["ZDB-GENE-1", "ZDB-GENE-1"],
            "Current Name": [None, None],
            "Current Symbol": ["g", "g"],
            "Previous Name": ["alpha", float("nan")],
            "SO ID": [None, None],
        }
    )

    assert build_alias_map(aliases_df, {"ZDB-GENE-1"}) == {"ZDB-GENE-1": ["alpha"]}
