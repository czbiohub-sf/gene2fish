"""Guard that Dependabot monitors the app's real dependency ecosystems (GEN-3).

``.github/dependabot.yml`` is ``argus bootstrap``-generated. A future regen could
silently drop the application ecosystems and leave pip/npm CVEs unmonitored -- the
exact gap GEN-3 closed. This test fails if the ``uv`` (Python) or ``npm`` (frontend)
ecosystem is missing, so the regression is caught in CI instead of in production.

Parses the file as text (mirroring ``test_dockerfile.py``) to avoid coupling the
test suite to a YAML library.
"""

from pathlib import Path

GITHUB = Path(__file__).resolve().parents[2] / ".github"
DEPENDABOT = GITHUB / "dependabot.yml"
AUTOAPPROVE = GITHUB / "workflows" / "autoapprove-dependabot.yml"


def test_dependabot_monitors_python_deps():
    text = DEPENDABOT.read_text()
    assert 'package-ecosystem: "uv"' in text, (
        "Dependabot must monitor Python deps via the native uv ecosystem"
    )


def test_dependabot_monitors_frontend_deps():
    text = DEPENDABOT.read_text()
    assert 'package-ecosystem: "npm"' in text, (
        "Dependabot must monitor frontend deps via the npm ecosystem"
    )


def test_autoapprove_gates_on_patch_and_minor_only():
    """Auto-approve/merge must be conditioned on the update-type so only patch
    and minor bumps are automated; major bumps require human review (GEN-8)."""
    text = AUTOAPPROVE.read_text()
    assert "steps.metadata.outputs.update-type" in text, (
        "auto-merge must be conditioned on the dependabot update-type"
    )
    assert "version-update:semver-patch" in text
    assert "version-update:semver-minor" in text


def test_autoapprove_never_allows_major_bumps():
    """A major bump must not appear as an allowed update-type — that would let a
    breaking upgrade merge without review (GEN-8)."""
    text = AUTOAPPROVE.read_text()
    assert "version-update:semver-major" not in text
