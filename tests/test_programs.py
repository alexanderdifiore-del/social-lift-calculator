import pytest

from lollie.credits.service import CreditService
from lollie.db.connection import init_database


@pytest.fixture()
def service(tmp_path, monkeypatch):
    monkeypatch.setenv("LOLLIE_DB_PATH", str(tmp_path / "prog.db"))
    init_database()
    return CreditService()


def test_programs_seeded_from_blueprints(service: CreditService):
    programs = service.list_programs()
    assert len(programs) >= 7
    platforms = {p["platform"] for p in programs}
    assert "Spotify" in platforms
    assert "TikTok Ads" in platforms
    assert "Google Ads / YouTube" in platforms
    assert "Meta Ads" in platforms
    assert "Snapchat Ads" in platforms


def test_period_budget_and_allocation_capacity(service: CreditService):
    programs = {p["program_key"]: p for p in service.list_programs()}
    tiktok = programs["tiktok_platform_ad_credits"]
    service.upsert_program_period(tiktok["id"], "2026 Q4", 186_000)
    service.create_allocation(
        tiktok["id"], "2026 Q4", 20_000, artist="Artist A", track="Track 1"
    )
    service.create_allocation(
        tiktok["id"], "2026 Q4", 10_000, artist="Artist B", track="Track 2"
    )
    summary = service.program_capacity_summary()
    row = summary[summary["Program"] == tiktok["program_name"]].iloc[0]
    assert row["Budgeted"] == 186_000
    assert row["Allocated"] == 30_000
    assert row["Remaining (budget − allocated)"] == 156_000


def test_utilization_and_reported_delivered(service: CreditService):
    programs = {p["program_key"]: p for p in service.list_programs()}
    yt = programs["youtube_gratis_impressions"]
    service.upsert_program_period(yt["id"], "2026-10", 51_000_000)
    alloc_id = service.create_allocation(
        yt["id"], "2026-10", 2_000_000, artist="Artist C", track="Video"
    )
    service.record_utilization(
        alloc_id, "2026-10-27", 850_000, impressions_served=850_000
    )
    summary = service.program_capacity_summary()
    row = summary[summary["Program"] == yt["program_name"]].iloc[0]
    assert row["Delivered (reported)"] == 850_000
    assert row["Utilization % (delivered/allocated)"] == pytest.approx(42.5)


def test_project_request_pipeline(service: CreditService):
    programs = {p["program_key"]: p for p in service.list_programs()}
    meta = programs["meta_promotional_fund"]
    project_id = service.create_project_request(
        {
            "artist": "Demo Artist",
            "project_title": "Release week",
            "track": "Song",
            "program_id": meta["id"],
            "period_label": "2026 Q4",
            "requested_value": 20_000,
            "value_unit": "USD",
            "request_status": "submitted",
            "reason_for_consideration": "Trending track, sustained uplift",
            "top_markets": "US, UK, DE, BR, JP",
        }
    )
    service.update_project_status(project_id, "approved")
    requests = service.list_project_requests(status="approved")
    assert any(r["id"] == project_id for r in requests)


def test_funding_overview_keeps_funding_types_separate(service: CreditService):
    programs = {p["program_key"]: p for p in service.list_programs()}
    tiktok = programs["tiktok_platform_ad_credits"]
    meta = programs["meta_promotional_fund"]
    service.upsert_program_period(tiktok["id"], "2026 Q4", 186_000)
    allocation_id = service.create_allocation(tiktok["id"], "2026 Q4", 20_000, artist="Artist A", track="Track 1")
    service.create_allocation(meta["id"], "2026 Q4", 10_000, artist="Artist A")
    service.record_utilization(allocation_id, "2026-10-15", 6_000)

    overview = service.funding_overview()
    tiktok_row = overview[overview["Platform"] == "TikTok Ads"].iloc[0]
    assert tiktok_row["Funding type"] == "In-kind partner funding"
    assert tiktok_row["Credit amount"] == 186_000
    assert tiktok_row["Allocated"] == 20_000
    assert tiktok_row["Utilized"] == 6_000
    assert tiktok_row["Remaining"] == 14_000
    meta_row = overview[overview["Platform"] == "Meta Ads"].iloc[0]
    assert meta_row["Funding type"] == "Prepaid funds"
    assert meta_row["Utilized"] == 0


def test_funding_overview_hides_demo_records_by_default(service: CreditService):
    service.load_demo_records()
    assert service.funding_overview().empty
    demo = service.funding_overview(include_demo=True)
    assert not demo.empty
    assert set(demo["Funding type"]) <= {"Billing credit", "Prepaid funds", "In-kind partner funding"}
