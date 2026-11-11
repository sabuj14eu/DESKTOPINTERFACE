"""The version on screen is the build's own: one VERSION file, tied to the release history,
with commit and build number read from git — never typed into the code."""
import re
from pathlib import Path

from signalmesh_terminal import __version__, build

ROOT = Path(__file__).resolve().parents[2]


def test_version_file_is_the_newest_release():
    v = (ROOT / "VERSION").read_text().strip()
    assert re.fullmatch(r"\d+\.\d+\.\d+", v)
    rel = build.releases()
    assert rel and rel[0]["version"] == v, "VERSION and the first heading of docs/RELEASES.md must be the same release"
    assert rel[0]["changes"] and all(set(r) == {"version", "date", "changes", "fixed", "outstanding"} for r in rel)
    assert __version__ == v


def test_no_version_number_is_typed_in_the_code():
    v = (ROOT / "VERSION").read_text().strip()
    for p in list((ROOT / "adapter" / "signalmesh_terminal").rglob("*.py")) + list((ROOT / "web" / "src").rglob("*.ts*")):
        assert v not in p.read_text(), f"{p} contains the version number — it must come from VERSION"


def test_health_and_version_carry_the_build_identity(client):
    b = client.get("/api/terminal/health").json()["build"]
    assert b["version"] == __version__ and b["label"] == f"V{__version__}"
    assert b["environment"] == "LOCAL" and b["data"] == "TEST FIXTURES"       # the test adapter runs fixtures
    assert re.fullmatch(r"[0-9a-f]{7}|UNKNOWN", b["commit"]) and b["started_at"]
    v = client.get("/api/terminal/version").json()
    assert v["build"]["commit"] == b["commit"] and v["releases"][0]["version"] == __version__


def test_environment_and_data_words():
    assert build.identity("production", False)["environment"] == "PRODUCTION" and build.identity("production", False)["data"] == "PRODUCTION DATA"
    assert build.identity("staging", False)["data"] == "STAGING DATA"
    assert build.identity("development", True)["data"] == "TEST FIXTURES"
