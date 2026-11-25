"""F2: logging and listing yield visits."""

import pytest

from cli_helpers import log_yield, ok, read_store, rejected, seed_spots


@pytest.fixture
def field(tmp_path):
    return tmp_path


@pytest.fixture
def spot(field):
    seed_spots(field, "pine-01")
    return "pine-01"


# --------------------------------------------------------------------------
# logging
# --------------------------------------------------------------------------
def test_visits_log_records_date_and_grams(field, spot):
    result = log_yield(field, spot, "2024-05-02", 250)
    assert "250" in result.stdout and "2024-05-02" in result.stdout

    stored = read_store(field)["visits"]
    assert len(stored) == 1
    assert stored[0]["spot_id"] == spot
    assert stored[0]["date"] == "2024-05-02"
    assert stored[0]["grams"] == 250

    listing = ok(field, "visits", "list", spot).stdout
    assert "2024-05-02" in listing
    assert "250 g" in listing


def test_visit_ids_are_assigned_and_increment(field, spot):
    log_yield(field, spot, "2024-05-02", 250)
    log_yield(field, spot, "2024-05-03", 260)
    assert [visit["id"] for visit in read_store(field)["visits"]] == [1, 2]


def test_zero_grams_is_a_legal_visit(field, spot):
    log_yield(field, spot, "2024-05-02", 0)
    assert read_store(field)["visits"][0]["grams"] == 0


@pytest.mark.parametrize("grams", ["abc", "", "12,5", "2.5"])
def test_visits_log_rejects_non_numeric_grams(field, spot, grams):
    result = rejected(field, "visits", "log", spot, "2024-05-02", grams)
    assert "grams must be a number" in result.stderr
    assert read_store(field)["visits"] == []


def test_visits_log_rejects_negative_grams(field, spot):
    result = rejected(field, "visits", "log", spot, "2024-05-02", "-5")
    assert "cannot be negative" in result.stderr
    assert read_store(field)["visits"] == []


@pytest.mark.parametrize(
    "bad_date", ["2024-13-40", "2024-02-30", "2024-5-2", "02-05-2024", "yesterday"]
)
def test_visits_log_rejects_impossible_dates(field, spot, bad_date):
    result = rejected(field, "visits", "log", spot, bad_date, "100")
    assert "YYYY-MM-DD" in result.stderr
    assert read_store(field)["visits"] == []


def test_visits_log_rejects_unknown_spots(field):
    result = rejected(field, "visits", "log", "ghost-01", "2024-05-02", "100")
    assert "unknown spot" in result.stderr
    store_exists = (field / ".tarpitch.json").exists()
    assert not store_exists or read_store(field)["visits"] == []


def test_a_rejected_visit_leaves_earlier_visits_intact(field, spot):
    log_yield(field, spot, "2024-05-02", 250)
    rejected(field, "visits", "log", spot, "2024-05-03", "abc")
    visits = read_store(field)["visits"]
    assert len(visits) == 1
    assert visits[0]["grams"] == 250


# --------------------------------------------------------------------------
# listing
# --------------------------------------------------------------------------
def test_visits_list_prints_newest_first(field, spot):
    log_yield(field, spot, "2024-05-02", 250)
    log_yield(field, spot, "2024-07-20", 300)
    log_yield(field, spot, "2024-04-10", 200)

    lines = ok(field, "visits", "list", spot).stdout.splitlines()
    assert lines[0] == "Visits for pine-01 -- 3 visits, 750 g"
    assert lines[1].startswith("date")
    assert [line.split()[0] for line in lines[3:]] == [
        "2024-07-20",
        "2024-05-02",
        "2024-04-10",
    ]


def test_visits_list_shows_only_the_requested_spot(field):
    seed_spots(field, "pine-01", "pine-02")
    log_yield(field, "pine-01", "2024-05-02", 250)
    log_yield(field, "pine-02", "2024-05-03", 150)

    listing = ok(field, "visits", "list", "pine-01").stdout
    assert "250 g" in listing
    assert "150 g" not in listing


def test_visits_list_hints_when_a_spot_has_no_visits(field, spot):
    result = ok(field, "visits", "list", spot)
    assert "no visits" in result.stdout.lower()
    assert "tarpitch visits log pine-01 2024-05-02 250" in result.stdout


def test_visits_list_rejects_an_unknown_spot(field):
    result = rejected(field, "visits", "list", "ghost-01")
    assert "unknown spot" in result.stderr
