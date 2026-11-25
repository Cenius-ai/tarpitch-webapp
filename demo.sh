#!/usr/bin/env bash
# Tarpitch demo: a scripted, non-interactive walk through every screen.
#
# Commands are labelled `tarpitch ...` for readability; this script actually
# runs `python3 <repo>/tarpitch.py ...` so nothing has to be installed.
# Everything happens in a throwaway working directory, which is removed on exit.
set -uo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
SCRIPT="$PWD/tarpitch.py"
DEMO_DIR="$(mktemp -d)"
trap 'cd /; rm -rf "$DEMO_DIR"' EXIT

quote_args() {
    # Rebuild the command line for display, quoting values that contain spaces.
    local out="" arg
    for arg in "$@"; do
        case "$arg" in
            *" "*) out="$out \"$arg\"" ;;
            *) out="$out $arg" ;;
        esac
    done
    printf '%s' "${out# }"
}

run() {
    printf '\n$ tarpitch %s\n' "$(quote_args "$@")"
    "$PYTHON" "$SCRIPT" "$@"
    printf '[exit %s]\n' "$?"
}

note() {
    printf '\n== %s ==\n' "$*"
}

if [ ! -f "$SCRIPT" ]; then
    printf 'error: tarpitch.py not found next to demo.sh\n' >&2
    exit 1
fi

cd "$DEMO_DIR"
printf 'Tarpitch demo -- %s\n' "$("$PYTHON" "$SCRIPT" --version)"
printf 'Catalogue for this demo: %s\n' "$DEMO_DIR/.tarpitch.json"
printf 'Seasons come from the visit month: Mar-May spring, Jun-Aug summer,\n'
printf 'Sep-Nov autumn, Dec-Feb winter.\n'

note "an empty catalogue prints a copyable hint"
run spots list

note "create tapping spots"
run spots add pine-01 --note "north ridge"
run spots add pine-02 --note "south slope"
run spots add pine-03 --note "creek bend"
run spots add pine-01 --note "duplicate attempt"
run spots add "   "
run spots list

note "log one yield per tree visit"
run visits log pine-01 2025-03-18 180
run visits log pine-01 2025-04-22 260
run visits log pine-01 2025-06-05 240
run visits log pine-01 2025-07-19 310
run visits log pine-01 2025-09-12 220
run visits log pine-01 2025-10-03 140
run visits log pine-01 2025-12-11 60
run visits log pine-01 2026-01-08 45
run visits log pine-02 2025-05-02 150
run visits log pine-02 2025-06-20 190
run visits log pine-02 2025-08-14 210
run visits log pine-02 2025-11-06 90
run visits log pine-03 2025-04-30 120
run visits log pine-03 2025-07-02 95
run visits log pine-03 2025-09-25 0

note "rejected entries never reach the store"
run visits log pine-01 2025-05-02 abc
run visits log pine-01 2025-05-02 -5
run visits log pine-01 2025-13-40 100
run visits log ghost-01 2025-05-02 100

note "one spot's visit log, newest first"
run visits list pine-01
run visits list pine-03

note "seasonal flow across every spot"
run report seasons

note "seasonal flow narrowed to one spot"
run report seasons --spot pine-01

note "an unknown spot is rejected and no chart is printed"
run report seasons --spot missing-01

note "a spot with no visits yet prints a hint"
run spots add pine-08 --note "unvisited stand"
run visits list pine-08
run report seasons --spot pine-08

note "the stored catalogue is plain, human-readable JSON"
printf '\n$ head -8 .tarpitch.json\n'
head -8 .tarpitch.json

mkdir -p "$DEMO_DIR/zeros"
cd "$DEMO_DIR/zeros"
note "zero grams are legal and still chart (zero-length bars)"
run spots add pine-04 --note "new stand, first season"
run visits log pine-04 2025-05-04 0
run visits log pine-04 2025-08-19 0
run report seasons

mkdir -p "$DEMO_DIR/broken"
cd "$DEMO_DIR/broken"
note "a corrupt store is reported on stderr, never a traceback"
printf '{"spots": [ {"id": "pine-01"\n' > .tarpitch.json
run spots list
run report seasons

printf '\nDemo complete. Exit codes above show the accepted and rejected commands.\n'
exit 0
