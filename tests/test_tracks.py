import pandas as pd

from lollie.streams.ingest import normalize_stream_frame, suggest_mapping
from lollie.streams.tracks import (
    MODE_PLAYLIST,
    CampaignScope,
    build_track_table,
    daily_scope_totals,
    load_track_list,
    match_streams,
    parse_playlist_url,
    source_attributed_totals,
    track_level_daily,
    tracks_from_stream_frame,
)


def streams(rows):
    frame = pd.DataFrame(rows, columns=["Date", "Track Title", "Artist", "ISRC", "Country", "Streams"])
    return normalize_stream_frame(frame, suggest_mapping(list(frame.columns))).frame


def listed(*entries):
    return build_track_table(pd.DataFrame(entries, columns=["title", "artist", "isrc"]))


def test_tracks_are_matched_by_isrc_even_when_titles_differ():
    frame = streams([["2026-01-01", "Song (Radio Edit)", "Band", "USAB12600001", "US", 10]])
    table = listed(("Song", "Band", "USAB12600001"))
    matched, coverage = match_streams(frame, table)
    assert len(matched) == 1
    assert coverage.iloc[0]["Matched by"] == "ISRC"


def test_tracks_fall_back_to_title_and_artist_without_isrc():
    frame = streams([["2026-01-01", "Paper Moons", "Band", "", "US", 10], ["2026-01-01", "Other Song", "Band", "", "US", 99]])
    table = listed(("paper moons", "BAND", ""))
    matched, coverage = match_streams(frame, table)
    assert matched["streams"].sum() == 10
    assert "Title" in coverage.iloc[0]["Matched by"]


def test_listed_tracks_missing_from_the_streaming_data_are_reported():
    frame = streams([["2026-01-01", "A", "Band", "", "US", 10]])
    table = listed(("A", "Band", ""), ("Ghost", "Band", ""))
    _, coverage = match_streams(frame, table)
    assert coverage.set_index("Track").loc["Ghost", "Matched by"] == "Not found in streaming data"


def test_playlist_total_adds_each_track_once_and_keeps_song_level_detail():
    rows = []
    for day in ("2026-01-01", "2026-01-02"):
        rows += [[day, "A", "Band", "", "US", 100], [day, "B", "Band", "", "US", 50], [day, "C", "Band", "", "US", 999]]
    frame = streams(rows)
    table = listed(("A", "Band", ""), ("B", "Band", ""))
    matched, _ = match_streams(frame, table)
    daily = daily_scope_totals(matched)
    assert daily["streams"].tolist() == [150, 150]  # track C is not on the playlist
    assert daily["tracks_reporting"].tolist() == [2, 2]
    by_track = track_level_daily(matched).groupby("track_title")["streams"].sum().to_dict()
    assert by_track == {"A": 200, "B": 100}


def test_same_track_arriving_with_and_without_isrc_is_not_double_counted():
    frame = pd.concat(
        [
            streams([["2026-01-01", "A", "Band", "USAB12600001", "US", 100]]),
            streams([["2026-01-01", "A", "Band", "", "US", 100]]),
        ],
        ignore_index=True,
    )
    table = listed(("A", "Band", "USAB12600001"))
    matched, _ = match_streams(frame, table)
    assert daily_scope_totals(matched)["streams"].sum() == 100
    assert matched.attrs["collapsed_rows"] == 1


def test_membership_dates_limit_which_days_count():
    frame = streams([["2026-01-01", "A", "Band", "", "US", 10], ["2026-01-05", "A", "Band", "", "US", 20], ["2026-01-09", "A", "Band", "", "US", 40]])
    table = build_track_table(pd.DataFrame({"title": ["A"], "artist": ["Band"], "member_from": ["2026-01-03"], "member_to": ["2026-01-07"]}))
    matched, _ = match_streams(frame, table)
    assert matched["streams"].tolist() == [20]


def test_playlist_attributed_streams_are_reported_separately():
    frame = pd.DataFrame(
        {"Date": ["2026-01-01"] * 2, "Track": ["A", "A"], "Source": ["Total", "Editorial Playlist"], "Streams": [500, 80]}
    )
    out = normalize_stream_frame(frame, suggest_mapping(list(frame.columns))).frame
    matched, _ = match_streams(out, tracks_from_stream_frame(out))
    sources = source_attributed_totals(matched)
    assert sources["Source"].tolist() == ["Editorial Playlist"]
    assert daily_scope_totals(matched)["streams"].sum() == 500


def test_track_list_upload_is_parsed_with_flexible_headers():
    raw = pd.DataFrame({"Song": ["A", "A", "B"], "ISRC Code": ["usab12600001", "USAB12600001", ""], "Added": ["2026-05-01"] * 3})
    table, issues = load_track_list(raw)
    assert table["title"].tolist() == ["A", "B"]
    assert table.loc[0, "isrc"] == "USAB12600001"
    assert table.loc[0, "member_from"] == pd.Timestamp("2026-05-01")
    assert any("skipped" in i.message for i in issues)


def test_track_list_without_title_or_isrc_is_rejected():
    table, issues = load_track_list(pd.DataFrame({"Notes": ["x"]}))
    assert table.empty and any(i.level == "error" for i in issues)


def test_spotify_link_is_kept_as_reference_only():
    assert parse_playlist_url("https://open.spotify.com/playlist/37i9dQZF1DX0XUsuxWHRQd?si=abc") == "37i9dQZF1DX0XUsuxWHRQd"
    assert parse_playlist_url("https://example.com/not-spotify") is None


def test_scope_labels():
    table = listed(("A", "Band", ""), ("B", "Band", ""))
    scope = CampaignScope(mode=MODE_PLAYLIST, tracks=table, playlist_name="Chill")
    assert scope.label == "Chill (2 tracks)"
