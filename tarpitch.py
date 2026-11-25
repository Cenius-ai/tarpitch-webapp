#!/usr/bin/env python3
"""Tarpitch -- catalogue pine resin tapping spots, log yields, chart the season.

Tarpitch is a single-file, standard-library-only field tool for pine resin
tappers. It keeps one local JSON catalogue (``.tarpitch.json`` in the working
directory), records one yield entry per tree visit, and prints a plain-ASCII
seasonal flow chart.

Design notes (committed direction: calm-precise, monospace, compact)
-------------------------------------------------------------------
* Every screen is monospace terminal text with aligned columns; nothing relies
  on colour, so a captured log reads exactly like a live terminal.
* One accent carries primary status: the ``|`` bar spine of the seasonal chart
  and the peak line printed underneath it. There is no colour-only signal.
* All output is plain ASCII (rules are ``-``, spines are ``|``, bars are ``#``)
  so a chart renders identically in any terminal, pipe or recorded demo.
* One two-space gutter and one rule width are reused on every screen.

Exit codes
----------
0   success
1   the store file cannot be read or written
2   rejected input (blank or duplicate spot id, bad grams, bad date, unknown spot)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Sequence

__version__ = "1.0.0"

PROGRAM = "tarpitch"
STORE_FILENAME = ".tarpitch.json"

EXIT_OK = 0
EXIT_STORE_ERROR = 1
EXIT_INVALID_INPUT = 2
EXIT_INTERRUPTED = 130

# --- committed layout tokens (calm-precise / mono / compact) ---------------
GUTTER = "  "
RULE_CHAR = "-"
BAR_CHAR = "#"
BAR_SPINE = "|"
BAR_WIDTH = 30
NOTE_COLUMN_LIMIT = 40

SEASONS: Sequence[str] = ("spring", "summer", "autumn", "winter")
SEASON_LABEL_WIDTH = max(len(name) for name in SEASONS)

# Fixed month-only mapping: the year never changes the season (D3).
_MONTH_TO_SEASON: Dict[int, str] = {
    1: "winter",
    2: "winter",
    3: "spring",
    4: "spring",
    5: "spring",
    6: "summer",
    7: "summer",
    8: "summer",
    9: "autumn",
    10: "autumn",
    11: "autumn",
    12: "winter",
}

ISO_DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
WHOLE_GRAMS_RE = re.compile(r"^[+-]?[0-9]+$")


class InputError(Exception):
    """Rejected user input; the message is shown verbatim on stderr."""


class StoreError(Exception):
    """The store file cannot be read or written; shown verbatim on stderr."""


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------
def season_for_month(month: int) -> str:
    """Map a calendar month to its season; the year is deliberately ignored."""
    try:
        return _MONTH_TO_SEASON[month]
    except KeyError:
        raise InputError(f"month out of range: {month}") from None


def season_for_date(iso_date: str) -> str:
    """Season of an ISO date string, derived from the month only."""
    return season_for_month(int(iso_date[5:7]))


def plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def describe_path(path: Path) -> str:
    """Show the store path relative to the working directory when possible."""
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def clip(text: str, limit: int) -> str:
    """Shorten an over-long note for display only; the store keeps it whole."""
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


# --------------------------------------------------------------------------
# data model
# --------------------------------------------------------------------------
@dataclass
class Spot:
    """One pine resin tapping spot."""

    id: str
    note: str = ""
    created: str = ""

    def as_dict(self) -> Dict[str, str]:
        return {"id": self.id, "note": self.note, "created": self.created}

    @classmethod
    def from_dict(cls, raw: object) -> "Spot":
        if not isinstance(raw, dict):
            raise ValueError("a spot entry is not an object")
        spot_id = raw.get("id")
        if not isinstance(spot_id, str) or not spot_id.strip():
            raise ValueError("a spot entry has no usable id")
        note = raw.get("note") or ""
        created = raw.get("created") or ""
        return cls(id=spot_id, note=str(note), created=str(created))


@dataclass
class Visit:
    """One yield entry for a single tree visit."""

    id: int
    spot_id: str
    date: str
    grams: int

    def as_dict(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "spot_id": self.spot_id,
            "date": self.date,
            "grams": self.grams,
        }

    @classmethod
    def from_dict(cls, raw: object) -> "Visit":
        if not isinstance(raw, dict):
            raise ValueError("a visit entry is not an object")
        spot_id = raw.get("spot_id")
        if not isinstance(spot_id, str) or not spot_id.strip():
            raise ValueError("a visit entry has no usable spot_id")
        visit_date = raw.get("date")
        if not isinstance(visit_date, str) or not ISO_DATE_RE.match(visit_date):
            raise ValueError(f"a visit for {spot_id} has a date that is not YYYY-MM-DD")
        grams = raw.get("grams")
        if not isinstance(grams, int) or isinstance(grams, bool) or grams < 0:
            raise ValueError(f"a visit for {spot_id} on {visit_date} has invalid grams")
        visit_id = raw.get("id")
        if not isinstance(visit_id, int) or isinstance(visit_id, bool) or visit_id < 1:
            visit_id = 0  # re-derived when the file was hand-edited
        return cls(id=visit_id, spot_id=spot_id, date=visit_date, grams=grams)


@dataclass
class Store:
    """The whole catalogue: one JSON document holding spots and visits."""

    path: Path
    spots: List[Spot] = field(default_factory=list)
    visits: List[Visit] = field(default_factory=list)

    # -- loading -----------------------------------------------------------
    @classmethod
    def load(cls, path: Path) -> "Store":
        if not path.exists():
            return cls(path=path)
        try:
            raw_text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise StoreError(
                f"cannot read store file {describe_path(path)}: {exc.strerror or exc}"
            ) from exc
        try:
            document = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise StoreError(
                f"cannot read store file {describe_path(path)}: invalid JSON "
                f"(line {exc.lineno}, column {exc.colno}); "
                "repair or remove the file to start over"
            ) from exc
        if not isinstance(document, dict):
            raise StoreError(
                f"cannot read store file {describe_path(path)}: "
                "the top level is not a JSON object; "
                "repair or remove the file to start over"
            )
        try:
            spots = [Spot.from_dict(item) for item in _json_array(document, "spots")]
            visits = [Visit.from_dict(item) for item in _json_array(document, "visits")]
        except ValueError as exc:
            raise StoreError(
                f"cannot read store file {describe_path(path)}: {exc}; "
                "repair or remove the file to start over"
            ) from exc
        return cls(path=path, spots=spots, visits=visits).with_visit_ids()

    # -- writing -----------------------------------------------------------
    def save(self) -> None:
        """Write the store atomically: temp file first, then rename over."""
        document = {
            "spots": [spot.as_dict() for spot in self.spots],
            "visits": [visit.as_dict() for visit in self.visits],
        }
        payload = json.dumps(document, indent=2) + "\n"
        temp_path: Optional[Path] = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=str(self.path.parent),
                prefix=self.path.name + ".",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temp_path = Path(handle.name)
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(str(temp_path), str(self.path))
        except OSError as exc:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
            raise StoreError(
                f"cannot write store file {describe_path(self.path)}: "
                f"{exc.strerror or exc}"
            ) from exc

    def with_visit_ids(self) -> "Store":
        """Give every visit a unique positive id (a hand-edited file may lose them)."""
        seen = set()
        next_free = 1
        for visit in self.visits:
            if visit.id > 0 and visit.id not in seen:
                seen.add(visit.id)
                next_free = max(next_free, visit.id + 1)
                continue
            while next_free in seen:
                next_free += 1
            visit.id = next_free
            seen.add(next_free)
            next_free += 1
        return self

    # -- queries -----------------------------------------------------------
    def find_spot(self, spot_id: str) -> Spot:
        for spot in self.spots:
            if spot.id == spot_id:
                return spot
        raise InputError(
            f"unknown spot {spot_id!r}; add it first with "
            f"`{PROGRAM} spots add {spot_id or 'pine-01'}`"
        )

    def visits_for(self, spot_id: str) -> List[Visit]:
        return [visit for visit in self.visits if visit.spot_id == spot_id]

    def next_visit_id(self) -> int:
        return max((visit.id for visit in self.visits), default=0) + 1


def _json_array(document: Dict[str, object], key: str) -> List[object]:
    value = document.get(key, [])
    if not isinstance(value, list):
        raise ValueError(f'the "{key}" field is not an array')
    return value


def store_path() -> Path:
    """The catalogue always lives beside the working directory (D2)."""
    return Path.cwd() / STORE_FILENAME


# --------------------------------------------------------------------------
# input validation (every check runs before anything is written, D4)
# --------------------------------------------------------------------------
def parse_spot_id(raw: str) -> str:
    spot_id = raw.strip()
    if not spot_id:
        raise InputError("spot id cannot be blank; use an id such as pine-01")
    if any(character in spot_id for character in "\t\r\n"):
        raise InputError(f"spot id must be a single token, got {raw!r}")
    return spot_id


def parse_grams(raw: str) -> int:
    text = raw.strip()
    if not WHOLE_GRAMS_RE.match(text):
        raise InputError(f"grams must be a number, got {raw!r}")
    grams = int(text, 10)
    if grams < 0:
        raise InputError(f"grams cannot be negative, got {raw!r}")
    return grams


def parse_visit_date(raw: str) -> str:
    text = raw.strip()
    if ISO_DATE_RE.match(text):
        try:
            return date.fromisoformat(text).isoformat()
        except ValueError:
            pass
    raise InputError(f"date must be a real YYYY-MM-DD date, got {raw!r}")


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------
def render_table(
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    right_align: Sequence[bool],
) -> List[str]:
    """Aligned monospace columns: one gutter, one rule width, ASCII only."""
    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    def format_row(cells: Sequence[str]) -> str:
        padded = [
            cell.rjust(width) if right_align[index] else cell.ljust(width)
            for index, (cell, width) in enumerate(zip(cells, widths))
        ]
        return GUTTER.join(padded).rstrip()

    lines = [format_row(headers), GUTTER.join(RULE_CHAR * width for width in widths)]
    lines.extend(format_row(row) for row in rows)
    return lines


def render_spot_table(spots: Sequence[Spot]) -> List[str]:
    """One row per spot, sorted by id, with its note and creation date."""
    rows = [
        [spot.id, clip(spot.note, NOTE_COLUMN_LIMIT), spot.created or "-"]
        for spot in sorted(spots, key=lambda spot: spot.id)
    ]
    return render_table(("id", "note", "created"), rows, (False, False, False))


def render_visit_table(spot_id: str, visits: Sequence[Visit]) -> List[str]:
    """One row per visit, newest first, with its date and grams."""
    ordered = sorted(visits, key=lambda visit: (visit.date, visit.id), reverse=True)
    rows = [[visit.date, f"{visit.grams} g"] for visit in ordered]
    total = sum(visit.grams for visit in ordered)
    header = f"Visits for {spot_id} -- {plural(len(ordered), 'visit')}, {total} g"
    return [header] + render_table(("date", "grams"), rows, (False, True))


def bar_length(total: int, peak: int) -> int:
    """Scale a season total to BAR_WIDTH cells; a zero maximum yields 0 (D5)."""
    if total <= 0 or peak <= 0:
        return 0
    return max(1, round(total * BAR_WIDTH / peak))


def render_season_chart(
    totals: Dict[str, int], scope: str, visit_count: int
) -> List[str]:
    """Four fixed season rows with gram totals and bars scaled to the peak."""
    peak = max(totals.values())
    grand_total = sum(totals.values())
    gram_width = max(len("grams"), len(str(grand_total))) + len(" g")

    lines = [
        f"Seasonal flow -- {scope} ({plural(visit_count, 'visit')}, {grand_total} g)",
        f"{'season':<{SEASON_LABEL_WIDTH}}{GUTTER}"
        f"{'grams':>{gram_width}}{GUTTER}bar",
        GUTTER.join(
            (
                RULE_CHAR * SEASON_LABEL_WIDTH,
                RULE_CHAR * gram_width,
                RULE_CHAR * (len(BAR_SPINE) + BAR_WIDTH),
            )
        ),
    ]
    for season in SEASONS:
        filled = bar_length(totals[season], peak)
        bar = BAR_SPINE + (BAR_CHAR * filled)
        row = (
            f"{season:<{SEASON_LABEL_WIDTH}}{GUTTER}"
            f"{format(totals[season]) + ' g':>{gram_width}}{GUTTER}{bar}"
        )
        lines.append(row.rstrip())

    if peak == 0:
        lines.append("peak: none (every season is 0 g)")
    else:
        peak_season = next(season for season in SEASONS if totals[season] == peak)
        lines.append(f"peak: {peak_season} ({peak} g)")
    return lines


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------
def cmd_spots_add(args: argparse.Namespace) -> int:
    """Create a tapping spot; nothing is stored when the id is rejected."""
    spot_id = parse_spot_id(args.spot_id)
    note = args.note.strip()

    store = Store.load(store_path())
    if any(spot.id == spot_id for spot in store.spots):
        raise InputError(f"spot id already exists: {spot_id}")

    created = date.today().isoformat()
    store.spots.append(Spot(id=spot_id, note=note, created=created))
    store.save()

    suffix = f", note: {note}" if note else ""
    print(f"Added spot {spot_id} (created {created}{suffix})")
    return EXIT_OK


def cmd_spots_list(_args: argparse.Namespace) -> int:
    """List every spot, or print a copyable hint when the catalogue is empty."""
    store = Store.load(store_path())
    if not store.spots:
        print("No spots in the catalogue yet.")
        print("Add your first tapping spot:")
        print(f'  {PROGRAM} spots add pine-01 --note "north ridge"')
        return EXIT_OK

    print(f"Catalogue -- {plural(len(store.spots), 'spot')}")
    for line in render_spot_table(store.spots):
        print(line)
    return EXIT_OK


def cmd_visits_log(args: argparse.Namespace) -> int:
    """Append one yield visit after validating date, grams and spot id."""
    spot_id = parse_spot_id(args.spot_id)
    visit_date = parse_visit_date(args.date)
    grams = parse_grams(args.grams)

    store = Store.load(store_path())
    store.find_spot(spot_id)

    store.visits.append(
        Visit(id=store.next_visit_id(), spot_id=spot_id, date=visit_date, grams=grams)
    )
    store.save()

    logged = len(store.visits_for(spot_id))
    print(
        f"Logged {grams} g for {spot_id} on {visit_date} "
        f"({plural(logged, 'visit')} total)"
    )
    return EXIT_OK


def cmd_visits_list(args: argparse.Namespace) -> int:
    """List one spot's visits, newest first, or hint at the first one."""
    spot_id = parse_spot_id(args.spot_id)
    store = Store.load(store_path())
    store.find_spot(spot_id)

    visits = store.visits_for(spot_id)
    if not visits:
        print(f"Spot {spot_id} has no visits logged yet.")
        print("Log the first visit (date is ISO YYYY-MM-DD, grams are whole grams):")
        print(f"  {PROGRAM} visits log {spot_id} 2024-05-02 250")
        return EXIT_OK

    for line in render_visit_table(spot_id, visits):
        print(line)
    return EXIT_OK


def cmd_report_seasons(args: argparse.Namespace) -> int:
    """Aggregate grams per season, across every spot or narrowed to one."""
    spot_filter = parse_spot_id(args.spot) if args.spot is not None else None
    store = Store.load(store_path())

    scope = "all spots"
    if spot_filter is None:
        visits = store.visits
    else:
        store.find_spot(spot_filter)
        scope = f"spot {spot_filter}"
        visits = store.visits_for(spot_filter)

    if not visits:
        print(f"No visits logged yet for {scope}.")
        print("Log the first yield with:")
        print(f"  {PROGRAM} visits log {spot_filter or 'pine-01'} 2024-05-02 250")
        return EXIT_OK

    totals = {season: 0 for season in SEASONS}
    for visit in visits:
        totals[season_for_date(visit.date)] += visit.grams

    for line in render_season_chart(totals, scope, len(visits)):
        print(line)
    return EXIT_OK


# --------------------------------------------------------------------------
# argument parser
# --------------------------------------------------------------------------
EXAMPLES = """
examples:
  tarpitch spots add pine-01 --note "north ridge"
  tarpitch spots list
  tarpitch visits log pine-01 2024-05-02 250
  tarpitch visits list pine-01
  tarpitch report seasons
  tarpitch report seasons --spot pine-01

The catalogue is one JSON file, .tarpitch.json, in the working directory.
Seasons come from the visit month alone: Mar-May spring, Jun-Aug summer,
Sep-Nov autumn, Dec-Feb winter.
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROGRAM,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Catalogue pine resin tapping spots, log the yield of each tree\n"
            "visit, and chart the seasonal flow."
        ),
        epilog=EXAMPLES,
    )
    parser.add_argument(
        "--version", action="version", version=f"{PROGRAM} {__version__}"
    )
    commands = parser.add_subparsers(
        dest="command", metavar="<command>", title="commands"
    )

    spots = commands.add_parser(
        "spots",
        help="create and list tapping spots",
        description="Create and list pine resin tapping spots.",
    )
    spots.set_defaults(group_parser=spots)
    spot_actions = spots.add_subparsers(
        dest="spots_action", metavar="<action>", title="actions"
    )

    spots_add = spot_actions.add_parser(
        "add", help="add a tapping spot", description="Add a tapping spot."
    )
    spots_add.add_argument(
        "spot_id",
        metavar="<spot_id>",
        help="short id for the tapping spot, for example pine-01",
    )
    spots_add.add_argument(
        "--note",
        "-n",
        metavar="TEXT",
        default="",
        help='free-text note, for example "north ridge"',
    )
    spots_add.set_defaults(handler=cmd_spots_add)

    spots_list = spot_actions.add_parser(
        "list",
        help="list tapping spots",
        description="List every tapping spot with its note and creation date.",
    )
    spots_list.set_defaults(handler=cmd_spots_list)

    visits = commands.add_parser(
        "visits",
        help="log and list resin yields",
        description="Log one resin yield per tree visit and list a spot's visits.",
    )
    visits.set_defaults(group_parser=visits)
    visit_actions = visits.add_subparsers(
        dest="visits_action", metavar="<action>", title="actions"
    )

    visits_log = visit_actions.add_parser(
        "log",
        help="log a visit's yield in grams",
        description="Append one yield visit for an existing spot.",
    )
    visits_log.add_argument(
        "spot_id", metavar="<spot_id>", help="id of an existing tapping spot"
    )
    visits_log.add_argument(
        "date", metavar="<YYYY-MM-DD>", help="date of the visit, an ISO calendar date"
    )
    visits_log.add_argument(
        "grams", metavar="<grams>", help="whole grams of resin collected, 0 or more"
    )
    visits_log.set_defaults(handler=cmd_visits_log)

    visits_list = visit_actions.add_parser(
        "list",
        help="list a spot's visits",
        description="List every logged visit for one spot, newest first.",
    )
    visits_list.add_argument(
        "spot_id", metavar="<spot_id>", help="id of an existing tapping spot"
    )
    visits_list.set_defaults(handler=cmd_visits_list)

    report = commands.add_parser(
        "report",
        help="seasonal flow report",
        description="Print the seasonal flow chart of resin grams per season.",
    )
    report.set_defaults(group_parser=report)
    report_actions = report.add_subparsers(
        dest="report_action", metavar="<action>", title="actions"
    )

    report_seasons = report_actions.add_parser(
        "seasons",
        help="chart grams per season",
        description="Chart resin grams per season, across all spots or one spot.",
    )
    report_seasons.add_argument(
        "--spot",
        "-s",
        metavar="<spot_id>",
        default=None,
        help="narrow the chart to one existing spot",
    )
    report_seasons.set_defaults(handler=cmd_report_seasons)

    return parser


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------
def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        # A bare invocation, or a group with no action, prints help and exits 0.
        group = getattr(args, "group_parser", None)
        (group or parser).print_help()
        return EXIT_OK
    try:
        return handler(args)
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_INVALID_INPUT
    except StoreError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_STORE_ERROR


def _run() -> int:
    try:
        return main()
    except KeyboardInterrupt:
        print("error: interrupted", file=sys.stderr)
        return EXIT_INTERRUPTED
    except BrokenPipeError:
        # Reader went away (for example `| head`); exit quietly without a traceback.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return EXIT_OK


if __name__ == "__main__":
    sys.exit(_run())
