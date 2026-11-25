"""T5: the unreadable store is reported, never a traceback."""

import json

import pytest

from cli_helpers import STORE_FILENAME, ok, read_store, rejected, run, seed_spots

BROKEN = '{"spots": [ {"id": "pine-01"'

COMMANDS = [
    ("spots", "list"),
    ("spots", "add", "pine-01"),
    ("visits", "list", "pine-01"),
    ("visits", "log", "pine-01", "2024-05-02", "100"),
    ("report", "seasons"),
]


@pytest.fixture
def field(tmp_path):
    return tmp_path


@pytest.fixture
def corrupt(field):
    (field / STORE_FILENAME).write_text(BROKEN, encoding="utf-8")
    return field


@pytest.mark.parametrize("command", COMMANDS)
def test_corrupt_store_is_reported_for_every_command(corrupt, command):
    result = rejected(corrupt, *command)
    assert "cannot read store file" in result.stderr
    assert (corrupt / STORE_FILENAME).read_text(encoding="utf-8") == BROKEN


def test_corrupt_store_is_never_overwritten(corrupt):
    rejected(corrupt, "spots", "add", "pine-01")
    assert (corrupt / STORE_FILENAME).read_text(encoding="utf-8") == BROKEN


def test_an_empty_store_file_is_reported(field):
    (field / STORE_FILENAME).write_text("", encoding="utf-8")
    result = rejected(field, "spots", "list")
    assert "cannot read store file" in result.stderr


@pytest.mark.parametrize(
    "payload",
    [
        "[]",
        '"just a string"',
        json.dumps({"spots": {}, "visits": []}),
        json.dumps({"spots": [], "visits": {}}),
        json.dumps({"spots": [{"note": "no id here"}], "visits": []}),
        json.dumps({"spots": [{"id": "pine-01"}], "visits": [{"spot_id": "pine-01"}]}),
        json.dumps(
            {
                "spots": [{"id": "pine-01"}],
                "visits": [{"spot_id": "pine-01", "date": "2024-05-02", "grams": -3}],
            }
        ),
    ],
)
def test_a_store_with_the_wrong_shape_is_reported(field, payload):
    (field / STORE_FILENAME).write_text(payload, encoding="utf-8")
    result = rejected(field, "spots", "list")
    assert "cannot read store file" in result.stderr


def test_a_store_path_that_is_a_directory_is_reported(field):
    (field / STORE_FILENAME).mkdir()
    result = rejected(field, "spots", "list")
    assert "cannot read store file" in result.stderr


def test_help_works_even_with_a_corrupt_store(corrupt):
    assert "usage: tarpitch" in ok(corrupt, "--help").stdout


def test_reading_the_catalogue_never_mutates_the_store(field):
    seed_spots(field, "pine-01")
    before = (field / STORE_FILENAME).read_text(encoding="utf-8")

    ok(field, "spots", "list")
    ok(field, "visits", "list", "pine-01")
    ok(field, "report", "seasons")

    assert (field / STORE_FILENAME).read_text(encoding="utf-8") == before


def test_the_store_is_human_readable_json(field):
    seed_spots(field, "pine-01")
    ok(field, "visits", "log", "pine-01", "2024-05-02", "250")

    text = (field / STORE_FILENAME).read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert "\n  " in text, "the store should be indented for a person to read"
    assert read_store(field)["visits"][0]["grams"] == 250


def test_a_successful_command_keeps_stderr_empty(field):
    result = ok(field, "spots", "add", "pine-01", "--note", "north ridge")
    assert result.stderr == ""


def test_a_hand_edited_store_without_visit_ids_still_lists(field):
    (field / STORE_FILENAME).write_text(
        json.dumps(
            {
                "spots": [{"id": "pine-01", "note": "", "created": "2024-03-04"}],
                "visits": [
                    {"spot_id": "pine-01", "date": "2024-05-02", "grams": 100},
                    {"spot_id": "pine-01", "date": "2024-06-02", "grams": 200},
                ],
            }
        ),
        encoding="utf-8",
    )

    listing = ok(field, "visits", "list", "pine-01").stdout
    assert "300 g" in listing
    assert "2024-06-02" in listing

    ok(field, "visits", "log", "pine-01", "2024-07-02", "300")
    ids = [visit["id"] for visit in read_store(field)["visits"]]
    assert len(set(ids)) == len(ids), "visit ids must stay unique"


def test_running_two_commands_never_duplicates_data(field):
    seed_spots(field, "pine-01")
    ok(field, "visits", "log", "pine-01", "2024-05-02", "250")

    store = read_store(field)
    assert len(store["spots"]) == 1
    assert len(store["visits"]) == 1

    run(field, "visits", "log", "pine-01", "2024-05-02", "abc")
    assert len(read_store(field)["visits"]) == 1
