"""F0/F1: the command surface and the spot catalogue."""

import json
from datetime import date

import pytest

from cli_helpers import STORE_FILENAME, ok, read_store, rejected, run


@pytest.fixture
def field(tmp_path):
    """A throwaway working directory; the store always lives in the cwd."""
    return tmp_path


# --------------------------------------------------------------------------
# command surface
# --------------------------------------------------------------------------
def test_help_lists_every_command_and_exits_zero(field):
    result = ok(field, "--help")
    for word in ("spots", "visits", "report", "add", "log", "seasons"):
        assert word in result.stdout
    assert result.stderr == ""


def test_help_documents_the_season_mapping(field):
    result = ok(field, "--help")
    assert "Mar-May spring" in result.stdout
    assert "Dec-Feb winter" in result.stdout


def test_bare_invocation_prints_help_without_failing(field):
    result = ok(field)
    assert "usage: tarpitch" in result.stdout


def test_group_without_action_prints_its_help(field):
    result = ok(field, "spots")
    assert "usage: tarpitch spots" in result.stdout


def test_version_flag(field):
    result = ok(field, "--version")
    assert result.stdout.strip() == "tarpitch 1.0.0"


def test_unknown_command_is_rejected(field):
    result = run(field, "harvest")
    assert result.returncode != 0
    assert "Traceback" not in result.stderr


# --------------------------------------------------------------------------
# F1: spot catalogue
# --------------------------------------------------------------------------
def test_spots_list_treats_missing_store_as_empty(field):
    result = ok(field, "spots", "list")
    assert "No spots in the catalogue yet." in result.stdout
    assert "tarpitch spots add" in result.stdout
    assert not (field / STORE_FILENAME).exists(), "listing must not create a store"


def test_spots_add_confirms_and_creates_a_valid_store(field):
    result = ok(field, "spots", "add", "pine-01", "--note", "north ridge")
    assert "pine-01" in result.stdout

    document = read_store(field)
    assert set(document) == {"spots", "visits"}
    assert document["visits"] == []
    assert len(document["spots"]) == 1
    spot = document["spots"][0]
    assert spot["id"] == "pine-01"
    assert spot["note"] == "north ridge"
    assert spot["created"] == date.today().isoformat()


def test_spots_add_without_note_stores_an_empty_note(field):
    ok(field, "spots", "add", "pine-02")
    assert read_store(field)["spots"][0]["note"] == ""


def test_spots_add_trims_the_id(field):
    ok(field, "spots", "add", "  pine-07  ")
    assert read_store(field)["spots"][0]["id"] == "pine-07"


@pytest.mark.parametrize("blank", ["", "   ", "\t"])
def test_spots_add_rejects_blank_ids(field, blank):
    result = rejected(field, "spots", "add", blank)
    assert "blank" in result.stderr
    assert not (field / STORE_FILENAME).exists()


def test_spots_add_rejects_duplicates_and_keeps_one_spot(field):
    ok(field, "spots", "add", "pine-01")
    result = rejected(field, "spots", "add", "pine-01")
    assert "already exists" in result.stderr

    listing = ok(field, "spots", "list")
    assert listing.stdout.count("pine-01") == 1
    assert len(read_store(field)["spots"]) == 1


def test_spots_list_shows_id_note_and_created_sorted_by_id(field):
    ok(field, "spots", "add", "pine-02", "--note", "south slope")
    ok(field, "spots", "add", "pine-01", "--note", "north ridge")

    lines = ok(field, "spots", "list").stdout.splitlines()
    assert lines[0] == "Catalogue -- 2 spots"
    rows = [line for line in lines if line.startswith("pine-")]
    assert rows == [
        f"pine-01  north ridge  {date.today().isoformat()}",
        f"pine-02  south slope  {date.today().isoformat()}",
    ]


def test_spots_list_uses_the_stored_created_date(field):
    store = {"spots": [{"id": "pine-09", "note": "", "created": "2024-03-04"}], "visits": []}
    (field / STORE_FILENAME).write_text(json.dumps(store), encoding="utf-8")
    assert "2024-03-04" in ok(field, "spots", "list").stdout


def test_spots_list_leaves_no_temporary_file_behind(field):
    ok(field, "spots", "add", "pine-01")
    ok(field, "visits", "log", "pine-01", "2024-05-02", "250")
    assert sorted(path.name for path in field.iterdir()) == [STORE_FILENAME]
