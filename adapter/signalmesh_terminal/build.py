"""BUILD IDENTITY — which terminal is running, read from the build, never typed.

  version      the VERSION file (one line), tied by a test to the newest heading in docs/RELEASES.md
  commit       git short hash of the checkout the image was built from
  build        number of commits up to that one (a number that only goes up)
  dirty        True when the checkout had uncommitted changes at build time
  built_at     when the image was built
  started_at   when this process started — on the box, the time of the last deployment
  environment  PRODUCTION / STAGING / LOCAL from SMT_ENV
  data         what the numbers on screen are: PRODUCTION DATA, STAGING DATA, LOCAL DATA or TEST FIXTURES

In the container these come from /srv/terminal/build.json, which the Dockerfile computes from the
git checkout (see the `meta` stage). Outside a container (development) they are read from git
directly. What cannot be determined is the word UNKNOWN — never a guess.
"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # repo root, or /srv/terminal in the image
STARTED_AT = datetime.now(timezone.utc).isoformat(timespec="seconds")
UNKNOWN = "UNKNOWN"


def version() -> str:
    try:
        return (ROOT / "VERSION").read_text().strip() or UNKNOWN
    except OSError:
        return UNKNOWN


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, timeout=5, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _from_git() -> dict:
    commit = _git("rev-parse", "--short=7", "HEAD")
    if not commit:
        return {}
    shallow = _git("rev-parse", "--is-shallow-repository") == "true"
    count = _git("rev-list", "--count", "HEAD")
    return {"commit": commit, "build": None if shallow or not count.isdigit() else int(count), "shallow": shallow,
            "dirty": bool(_git("status", "--porcelain", "--untracked-files=no")),
            "commit_time": _git("log", "-1", "--format=%cI") or None, "built_at": None, "source": "git checkout (not an image build)"}


_cached: dict | None = None


def identity(env: str = "development", is_fixture: bool = False) -> dict:
    global _cached
    if _cached is None:
        meta: dict = {}
        try:
            meta = json.loads((ROOT / "build.json").read_text())
            meta["source"] = "image build (build.json, computed from the git checkout by the Dockerfile)"
        except (OSError, ValueError):
            meta = _from_git()
        _cached = {"commit": meta.get("commit") or UNKNOWN, "build": meta.get("build"), "shallow": bool(meta.get("shallow")),
                   "dirty": bool(meta.get("dirty")), "commit_time": meta.get("commit_time"), "built_at": meta.get("built_at"),
                   "source": meta.get("source") or "no build metadata found"}
    e = (env or "").strip().lower()
    environment = "PRODUCTION" if e in ("production", "prod") else "STAGING" if e in ("staging", "stage") else "LOCAL"
    return {"name": "SignalMesh Terminal", "version": version(), **_cached, "started_at": STARTED_AT,
            "environment": environment, "data": "TEST FIXTURES" if is_fixture else f"{environment} DATA",
            "label": f"V{version()}"}


def releases() -> list[dict]:
    """docs/RELEASES.md as data: [{version, date, changes[], fixed[], outstanding[]}], newest first."""
    try:
        text = (ROOT / "docs" / "RELEASES.md").read_text()
    except OSError:
        return []
    out: list[dict] = []
    cur, key = None, None
    names = {"changes": "changes", "fixed bugs": "fixed", "outstanding issues": "outstanding"}
    for line in text.splitlines():
        m = re.match(r"^## (\d+\.\d+\.\d+)\s+[—-]\s+(\S+)", line)
        if m:
            cur = {"version": m.group(1), "date": m.group(2), "changes": [], "fixed": [], "outstanding": []}
            out.append(cur)
            key = None
        elif line.startswith("### ") and cur is not None:
            key = names.get(line[4:].strip().lower())
        elif line.startswith("- ") and cur is not None and key:
            cur[key].append(line[2:].strip())
    return out
