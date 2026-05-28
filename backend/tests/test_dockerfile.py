"""Guard the container hardening contract.

The runtime image must drop root: an RCE/escape should not run as UID 0,
and cluster admission policies frequently reject root containers outright.
This test parses the repo-root Dockerfile and asserts the runtime stage
sets a non-root ``USER``.
"""

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
