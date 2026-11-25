"""Shared helpers for the Tarpitch test suite.

Every test drives the real script the way a user would: a subprocess in a
throwaway working directory. That exercises stdout/stderr routing, exit codes,
input validation and the on-disk JSON store for real instead of mocking them.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tarpitch.py"
STORE_FILENAME = ".tarpitch.json"

SEASON_ORDER = ["spring", "summer", "autumn", "winter"]
SEASON_ROW_RE = re.compile(r"^(spring|summer|autumn|winter)\s+([0-9]+) g\s+\|(#*)$")


def run(workdir, *args):
    """Run the CLI in *workdir* and capture both streams as text."""
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(workdir),
        capture_output=True,
        text=True,
    )


def ok(workdir, *args):
    """Run a command that must succeed."""
    result = run(workdir, *args)
    assert result.returncode == 0, f"unexpected failure: {result.stderr}"
    return result


def rejected(workdir, *args):
    """A rejected command: non-zero exit, message on stderr, nothing on stdout."""
    result = run(workdir, *args)
    assert result.returncode != 0, "command should have been rejected"
    assert result.stdout == "", f"rejections must not print to stdout: {result.stdout!r}"
    assert result.stderr.strip(), "rejections must explain themselves on stderr"
    assert "Traceback" not in result.stderr, result.stderr
    return result


def read_store(workdir):
    return json.loads((workdir / STORE_FILENAME).read_text(encoding="utf-8"))


def chart_rows(stdout):
    """Parse the seasonal chart into (season, grams, bar cells) rows, in order."""
    rows = []
    for line in stdout.splitlines():
        match = SEASON_ROW_RE.match(line)
        if match:
            rows.append((match.group(1), int(match.group(2)), len(match.group(3))))
    return rows


def seed_spots(workdir, *spot_ids):
    for spot_id in spot_ids:
        ok(workdir, "spots", "add", spot_id)


def log_yield(workdir, spot_id, visit_date, grams):
    return ok(workdir, "visits", "log", spot_id, visit_date, str(grams))
