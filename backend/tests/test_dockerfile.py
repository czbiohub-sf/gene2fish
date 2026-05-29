"""Guard the container hardening and data-integrity contracts.

The runtime image must drop root: an RCE/escape should not run as UID 0,
and cluster admission policies frequently reject root containers outright.
This test parses the repo-root Dockerfile and asserts the runtime stage
sets a non-root ``USER``.

It also guards the baked-index gate: the build must pass ``--min-records`` to
the extractor so a truncated download or drifted ZFIN format fails the build
instead of silently shipping an empty/partial index.
"""

import re
from pathlib import Path

DOCKERFILE = Path(__file__).resolve().parents[2] / "Dockerfile"


def _user_directives() -> list[str]:
    """Return the value of every ``USER`` instruction in the Dockerfile."""
    values = []
    for raw in DOCKERFILE.read_text().splitlines():
        line = raw.strip()
        if line.upper().startswith("USER "):
            values.append(line.split(None, 1)[1].strip())
    return values


def test_dockerfile_sets_a_user():
    assert _user_directives(), "Dockerfile must set a non-root USER directive"


def test_dockerfile_user_is_not_root():
    for value in _user_directives():
        uid = value.split(":", 1)[0]  # strip optional :group
        assert uid not in ("root", "0"), f"USER must not be root, got {value!r}"


def test_dockerfile_gates_baked_index_with_min_records():
    """The extractor invocation that bakes the index must pass --min-records,
    so an empty/partial download fails the build rather than shipping silently."""
    text = DOCKERFILE.read_text()
    assert "zfin_image_metadata_extractor.py" in text
    match = re.search(r"--min-records\s+(\d+)", text)
    assert match, "Dockerfile must run the extractor with --min-records to gate the build"
    assert int(match.group(1)) > 0, "the --min-records floor must be positive"
