import pandas as pd
import pytest

from lollie.streams.ingest import (
    combine_stream_frames,
    normalize_stream_frame,
    suggest_mapping,
)
from lollie.streams.schema import SCOPE_SOURCE, SCOPE_TOTAL
from lollie.streams.tracks import daily_scope_totals, match_streams, tracks_from_stream_frame


def raw(rows, columns=("Date", "Track", "ISRC", "Country", "Service", "Streams")):
    return pd.DataFrame(rows, columns=list(columns))


def load(frame, **kwargs):
    return normalize_stream_frame(frame, suggest_mapping(list(frame.columns)), **kwargs)


def test_columns_are_matched_from_common_opus_style_headers():
    mapping = suggest_mapping(["Reporting Date", "Artist Name", "Track Title", "ISRC", "Territory", "Service", "Daily Streams"])
    assert mapping["date"] == "Reporting Date"
    assert mapping["artist"] == "Artist Name"
    assert mapping["track_title"] == "Track Title"
    assert mapping["isrc"] == "ISRC"
    assert mapping["market"] == "Territory"
    assert mapping["dsp"] == "Service"
    assert mapping["streams"] == "Daily Streams"


def test_missing_required_columns_are_explained():
    result = load(pd.DataFrame({"Track": ["A"], "Country": ["US"]}))
    messages = [i.message for i in result.issues if i.level == "error"]
    assert any("date" in m for m in messages) and any("streams" in m for m in messages)
    assert result.frame.empty


def test_numbers_with_thousands_separators_and_bad_values():
    result = load(raw([["2026-01-01", "A", "", "US", "Spotify", "1,200"], ["2026-01-02", "A", "", "US", "Spotify", "n/a"]]))
    assert result.frame["streams"].tolist() == [1200]
    assert any("no stream count" in i.message or "not numbers" in i.message for i in result.issues)


def test_rows_with_no_date_are_dropped_and_reported():
    result = load(raw([["not a date", "A", "", "US", "Spotify", 10], ["2026-01-02", "A", "", "US", "Spotify", 20]]))
    assert len(result.frame) == 1
    assert any("no valid date" in i.message for i in result.issues)


def test_country_names_and_codes_match_the_same_market():
    result = load(raw([["2026-01-01", "A", "", "United States", "Spotify", 10], ["2026-01-02", "A", "", "US", "Spotify", 20],
                       ["2026-01-02", "A", "", "Deutschland", "Spotify", 5]]))
    assert set(result.frame["market_code"]) == {"US", "DE"}


def test_unrecognized_country_is_flagged_not_guessed():
    result = load(raw([["2026-01-01", "A", "", "Narnia", "Spotify", 10]]))
    assert result.frame["market_code"].isna().all()
    assert any("Narnia" in i.message for i in result.issues)


def test_identical_repeated_rows_are_not_double_counted():
    row = ["2026-01-01", "A", "", "US", "Spotify", 10]
    result = load(raw([row, row]))
    assert result.frame["streams"].sum() == 10
    assert any("identical" in i.message for i in result.issues)


def test_total_and_playlist_attributed_streams_stay_separate():
    frame = pd.DataFrame(
        {
            "Date": ["2026-01-01"] * 2,
            "Track": ["A", "A"],
            "Country": ["US", "US"],
            "Source": ["Total", "Editorial Playlist"],
            "Streams": [1000, 120],
        }
    )
    result = load(frame)
    assert set(result.frame["scope"]) == {SCOPE_TOTAL, SCOPE_SOURCE}
    tracks = tracks_from_stream_frame(result.frame)
    matched, _ = match_streams(result.frame, tracks)
    daily = daily_scope_totals(matched)
    assert daily["streams"].sum() == 1000  # the playlist slice is never added on top


def test_file_marked_as_source_streams_without_source_column_is_warned():
    result = load(raw([["2026-01-01", "A", "", "US", "Spotify", 10]]), default_scope=SCOPE_SOURCE)
    assert (result.frame["scope"] == SCOPE_SOURCE).all()
    assert any("no playlist or source column" in i.message for i in result.issues)


def test_hourly_rows_roll_up_only_for_complete_days():
    hours = pd.date_range("2026-01-01", periods=24 * 2 + 10, freq="h")
    frame = pd.DataFrame({"Timestamp": hours.astype(str), "Track": "A", "Country": "US", "Streams": 10})
    result = load(frame)
    assert result.frame["date"].dt.strftime("%Y-%m-%d").tolist() == ["2026-01-01", "2026-01-02"]
    assert result.frame["streams"].tolist() == [240, 240]
    assert any("24 hours" in i.message for i in result.issues)


def test_default_track_and_dsp_fill_files_that_lack_those_columns():
    frame = pd.DataFrame({"Date": ["2026-01-01"], "Streams": [5]})
    result = load(frame, default_track="Solo", default_dsp="spotify", default_artist="Band")
    row = result.frame.iloc[0]
    assert (row["track_title"], row["dsp"], row["artist"]) == ("Solo", "Spotify", "Band")


def test_isrc_is_cleaned_and_used_as_the_track_identity():
    result = load(raw([["2026-01-01", "Song", "us-ab1-26-00001", "US", "Spotify", 10], ["2026-01-02", "SONG (Remix)", "USAB12600001", "US", "Spotify", 12]]))
    assert result.frame["track_key"].nunique() == 1
    assert result.frame["isrc"].iloc[0] == "USAB12600001"


def test_all_country_rollup_rows_are_dropped_when_country_rows_exist():
    a = load(raw([["2026-01-01", "A", "", "US", "Spotify", 60], ["2026-01-01", "A", "", "DE", "Spotify", 40]]))
    b = load(raw([["2026-01-01", "A", "", "All countries", "Spotify", 100]]))
    combined, issues = combine_stream_frames([a, b])
    assert combined["streams"].sum() == 100
    assert any("All markets" in i.message for i in issues)


def test_all_dsp_rollup_rows_are_dropped_when_service_rows_exist():
    frame = raw([["2026-01-01", "A", "", "US", "Spotify", 60], ["2026-01-01", "A", "", "US", "Apple Music", 40], ["2026-01-01", "A", "", "US", "All", 100]])
    combined, issues = combine_stream_frames([load(frame)])
    assert combined["streams"].sum() == 100
    assert any("All DSPs" in i.message for i in issues)


def test_same_file_twice_is_skipped_and_conflicting_values_are_reported():
    first = load(raw([["2026-01-01", "A", "", "US", "Spotify", 10]]))
    first.file_hash = "x"
    second = load(raw([["2026-01-01", "A", "", "US", "Spotify", 10]]))
    second.file_hash = "x"
    combined, issues = combine_stream_frames([first, second])
    assert len(combined) == 1 and any("identical to a file" in i.message for i in issues)

    third = load(raw([["2026-01-01", "A", "", "US", "Spotify", 99]]))
    third.file_hash = "y"
    combined, issues = combine_stream_frames([first, third])
    assert combined["streams"].tolist() == [99]
    assert any("different stream counts" in i.message for i in issues)


def test_missing_days_stay_missing():
    result = load(raw([["2026-01-01", "A", "", "US", "Spotify", 10], ["2026-01-03", "A", "", "US", "Spotify", 12]]))
    assert result.frame["date"].dt.day.tolist() == [1, 3]


@pytest.mark.parametrize("value", ["2026-01-05", "01/05/2026", "Jan 5, 2026", "2026-01-05 00:00:00"])
def test_common_date_formats_are_read(value):
    result = load(raw([[value, "A", "", "US", "Spotify", 10]]))
    assert result.frame["date"].iloc[0] == pd.Timestamp("2026-01-05")
