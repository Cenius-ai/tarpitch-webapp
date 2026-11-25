#!/usr/bin/env bash
# Tarpitch installer.
#
# Tarpitch needs nothing outside the Python standard library, so this script
# only validates the interpreter, checks that the tool imports, offers the
# optional `tarpitch` console script, and installs the test runner.
# It never installs system packages, never uses sudo, and exits when done:
# starting the tool is a separate command (see README.md / INSTALL.md).
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "error: $PYTHON not found. Install Python 3.9 or newer, then retry." >&2
    exit 1
fi

if ! "$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)'; then
    echo "error: Python 3.9 or newer is required, found $("$PYTHON" -V 2>&1)." >&2
    exit 1
fi
echo "python: $("$PYTHON" -V 2>&1)"

# Runtime dependencies: none. The file is complete on purpose (see requirements.txt).
"$PYTHON" -c 'import tarpitch' || {
    echo "error: tarpitch.py does not import; the delivery is broken." >&2
    exit 1
}
echo "tarpitch.py imports cleanly (standard library only)"

# Optional: install the `tarpitch` console script so the tool is on PATH.
if "$PYTHON" -c 'import setuptools' >/dev/null 2>&1; then
    if "$PYTHON" -m pip install --no-build-isolation --no-input --quiet -e .; then
        echo "installed the 'tarpitch' console script"
    else
        echo "note: could not install the console script; use 'python3 tarpitch.py <command>'"
    fi
else
    echo "note: setuptools is missing; use 'python3 tarpitch.py <command>'"
fi

# Test runner (development only, never needed to use the tool).
if "$PYTHON" -c 'import pytest' >/dev/null 2>&1; then
    echo "pytest: already available"
else
    echo "installing the test runner from requirements-dev.txt"
    "$PYTHON" -m pip install --no-input -r requirements-dev.txt
fi

cat <<'NEXT'
Setup complete. Next steps:
  python3 tarpitch.py --help
  bash demo.sh
  python3 -m pytest
NEXT
