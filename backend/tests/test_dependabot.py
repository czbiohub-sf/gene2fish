"""Guard that Dependabot monitors the app's real dependency ecosystems (GEN-3).

``.github/dependabot.yml`` is ``argus bootstrap``-generated. A future regen could
silently drop the application ecosystems and leave pip/npm CVEs unmonitored -- the
exact gap GEN-3 closed. This test fails if the ``uv`` (Python) or ``npm`` (frontend)
ecosystem is missing, so the regression is caught in CI instead of in production.

Parses the file as text (mirroring ``test_dockerfile.py``) to avoid coupling the
test suite to a YAML library.
"""

from pathlib import Path

DEPENDABOT = Path(__file__).resolve().parents[2] / ".github" / "dependabot.yml"


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
