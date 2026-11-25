"""F3: the seasonal flow report, plus the pure rules behind it."""

import pytest

import tarpitch
from cli_helpers import chart_rows, log_yield, ok, rejected, seed_spots

WINTER = "2024-01-15"
SPRING = "2024-04-10"
SUMMER = "2024-07-20"
AUTUMN = "2024-10-05"


@pytest.fixture
def field(tmp_path):
    return tmp_path


@pytest.fixture
def season(field):
    """One spot with a visit in every season, spread over two years."""
    seed_spots(field, "pine-01")
    log_yield(field, "pine-01", WINTER, 100)
    log_yield(field, "pine-01", SPRING, 200)
    log_yield(field, "pine-01", SUMMER, 300)
    log_yield(field, "pine-01", AUTUMN, 400)
    log_yield(field, "pine-01", "2025-01-20", 50)
    return "pine-01"


# --------------------------------------------------------------------------
# the chart
# --------------------------------------------------------------------------
def test_report_seasons_uses_the_fixed_month_mapping(field, season):
    rows = chart_rows(ok(field, "report", "seasons").stdout)
    assert [(name, grams) for name, grams, _bar in rows] == [
        ("spring", 200),
        ("summer", 300),
        ("autumn", 400),
        ("winter", 150),
    ]


def test_report_seasons_ignores_the_year(field, season):
    # winter = 2024-01-15 (100 g) + 2025-01-20 (50 g): two different years, one row.
    rows = dict((name, grams) for name, grams, _bar in chart_rows(ok(field, "report", "seasons").stdout))
    assert rows["winter"] == 150


def test_report_seasons_scales_bars_to_the_largest_season(field, season):
    rows = chart_rows(ok(field, "report", "seasons").stdout)
    bars = {name: bar for name, _grams, bar in rows}
    assert bars["autumn"] == tarpitch.BAR_WIDTH
    assert bars["winter"] < bars["spring"] < bars["summer"] < bars["autumn"]
    assert all(bar > 0 for bar in bars.values())


def test_report_seasons_names_the_peak(field, season):
    assert "peak: autumn (400 g)" in ok(field, "report", "seasons").stdout


def test_report_seasons_sums_across_every_spot(field):
    seed_spots(field, "pine-01", "pine-02")
    log_yield(field, "pine-01", "2024-05-02", 250)
    log_yield(field, "pine-02", "2024-05-03", 150)

    rows = dict((name, grams) for name, grams, _bar in chart_rows(ok(field, "report", "seasons").stdout))
    assert rows["spring"] == 400


def test_report_seasons_spot_filter_narrows_to_one_spot(field):
    seed_spots(field, "pine-01", "pine-02")
    log_yield(field, "pine-01", "2024-05-02", 250)
    log_yield(field, "pine-02", "2024-05-03", 150)

    result = ok(field, "report", "seasons", "--spot", "pine-01")
    rows = dict((name, grams) for name, grams, _bar in chart_rows(result.stdout))
    assert rows["spring"] == 250
    assert "spot pine-01" in result.stdout


def test_report_seasons_rejects_an_unknown_spot_and_prints_no_chart(field, season):
    result = rejected(field, "report", "seasons", "--spot", "missing-01")
    assert "unknown spot" in result.stderr
    assert chart_rows(result.stdout) == []


def test_report_seasons_renders_zero_grams_with_zero_length_bars(field):
    seed_spots(field, "pine-01")
    log_yield(field, "pine-01", "2024-05-02", 0)
    log_yield(field, "pine-01", "2024-08-11", 0)

    result = ok(field, "report", "seasons")
    rows = chart_rows(result.stdout)
    assert [(name, grams, bar) for name, grams, bar in rows] == [
        ("spring", 0, 0),
        ("summer", 0, 0),
        ("autumn", 0, 0),
        ("winter", 0, 0),
    ]
    assert "peak: none" in result.stdout
    assert "division by zero" not in result.stderr.lower()
    assert "Traceback" not in result.stderr


def test_report_seasons_invites_the_first_visit_when_nothing_is_logged(field):
    seed_spots(field, "pine-01")
    result = ok(field, "report", "seasons")
    assert "No visits logged yet" in result.stdout
    assert "tarpitch visits log" in result.stdout
    assert chart_rows(result.stdout) == []


def test_report_seasons_on_an_empty_catalogue_invites_the_first_visit(field):
    result = ok(field, "report", "seasons")
    assert "No visits logged yet" in result.stdout


def test_report_seasons_hints_when_only_another_spot_has_visits(field):
    seed_spots(field, "pine-01", "pine-02")
    log_yield(field, "pine-01", SPRING, 200)
    result = ok(field, "report", "seasons", "--spot", "pine-02")
    assert "spot pine-02" in result.stdout
    assert chart_rows(result.stdout) == []


# --------------------------------------------------------------------------
# pure rules
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "month, expected",
    [
        (1, "winter"),
        (2, "winter"),
        (3, "spring"),
        (4, "spring"),
        (5, "spring"),
        (6, "summer"),
        (7, "summer"),
        (8, "summer"),
        (9, "autumn"),
        (10, "autumn"),
        (11, "autumn"),
        (12, "winter"),
    ],
)
def test_season_for_month(month, expected):
    assert tarpitch.season_for_month(month) == expected


def test_season_for_month_rejects_out_of_range_values():
    with pytest.raises(tarpitch.InputError):
        tarpitch.season_for_month(13)


def test_season_for_date_reads_the_month_only():
    assert tarpitch.season_for_date("2024-01-15") == "winter"
    assert tarpitch.season_for_date("1999-12-31") == "winter"
    assert tarpitch.season_for_date("2031-04-01") == "spring"


@pytest.mark.parametrize(
    "total, peak, expected",
    [(400, 400, 30), (300, 400, 22), (200, 400, 15), (0, 400, 0)],
)
def test_bar_length_scales_to_the_peak(total, peak, expected):
    assert tarpitch.bar_length(total, peak) == expected


def test_bar_length_never_divides_by_zero():
    assert tarpitch.bar_length(0, 0) == 0
    assert tarpitch.bar_length(10, 0) == 0


def test_bar_length_keeps_a_tiny_season_visible():
    assert tarpitch.bar_length(1, 1_000_000) == 1


@pytest.mark.parametrize("raw, expected", [("0", 0), ("250", 250), (" 250 ", 250), ("+7", 7)])
def test_parse_grams_accepts_whole_numbers(raw, expected):
    assert tarpitch.parse_grams(raw) == expected


@pytest.mark.parametrize("raw", ["abc", "", "1.5", "2,5", "0x10", "-5"])
def test_parse_grams_rejects_bad_values(raw):
    with pytest.raises(tarpitch.InputError):
        tarpitch.parse_grams(raw)


@pytest.mark.parametrize("raw", ["2024-13-40", "2024-02-30", "2024-5-2", "20240502", ""])
def test_parse_visit_date_rejects_non_iso_dates(raw):
    with pytest.raises(tarpitch.InputError):
        tarpitch.parse_visit_date(raw)


def test_parse_visit_date_returns_the_iso_date():
    assert tarpitch.parse_visit_date("2024-05-02") == "2024-05-02"
