"""Reusable Streamlit fragments for the credits dashboard."""

from __future__ import annotations

from datetime import date

import plotly.graph_objects as go
import streamlit as st

from lollie.credits.constants import AD_PLATFORMS
from lollie.credits.metrics import (
    build_inventory_dataframe,
    expiration_warnings,
    platform_comparison,
    summarize_by_currency,
)
from lollie.credits.programs import BUDGET_MODEL_LABELS, VALUE_UNIT_LABELS
from lollie.credits.service import CreditService
from lollie.credits.settings import WarningSettings, load_warning_settings, save_warning_settings
from lollie.imports.file_loader import load_tabular_upload

UNIT_FORMAT = {
    "USD": lambda v: f"${v:,.0f}",
    "impressions": lambda v: f"{v:,.0f}",
    "share_percent": lambda v: f"{v:.1f}%",
    "other": lambda v: f"{v:,.0f}",
}


def _fmt(value: float | None, unit: str) -> str:
    if value is None:
        return "—"
    formatter = UNIT_FORMAT.get(unit, lambda v: f"{v:,.0f}")
    return formatter(value)


def credit_filters_sidebar(service: CreditService) -> dict:
    st.sidebar.subheader("Filters")
    include_demo = st.sidebar.checkbox(
        "Include demo records",
        value=False,
        help="Demo data loads only when you enable Demo Mode on this page.",
    )
    credits = service.list_credits(include_demo=include_demo)
    platforms = ["All"] + sorted({c["platform"] for c in credits} or AD_PLATFORMS)
    accounts = ["All"] + sorted({c["ad_account_id"] for c in credits})
    artists = ["All"] + sorted({c["artist"] for c in credits if c.get("artist")})
    campaigns = ["All"] + sorted({c["campaign"] for c in credits if c.get("campaign")})
    markets = ["All"] + sorted({c["market"] for c in credits if c.get("market")})

    return {
        "include_demo": include_demo,
        "platform": st.sidebar.selectbox("Platform", platforms),
        "ad_account_id": st.sidebar.selectbox("Ad account", accounts),
        "artist": st.sidebar.selectbox("Artist", artists),
        "campaign": st.sidebar.selectbox("Campaign", campaigns),
        "market": st.sidebar.selectbox("Market", markets),
    }


def render_warning_banner(warnings: list[dict[str, str]]) -> None:
    for item in warnings[:12]:
        level = item["level"]
        if level == "error":
            st.error(item["message"])
        elif level == "warning":
            st.warning(item["message"])
        else:
            st.info(item["message"])
    if len(warnings) > 12:
        st.caption(f"+ {len(warnings) - 12} additional notices.")


# ----------------------------------------------------------------------
# Programs overview
# ----------------------------------------------------------------------


def render_programs_tab(service: CreditService) -> None:
    st.subheader("Partner-funded programs")
    st.caption(
        "These are **in-kind partner allocations** (budgets, impression grants, match capacity, "
        "share-of-pool) — not billing coupons in your ad accounts. Program terms below come from the "
        "Global Catalog deck; edit period budgets per quarter/month as allocations change."
    )
    programs = service.list_programs()
    if not programs:
        st.info("No programs configured.")
        return

    capacity = service.program_capacity_summary()
    for program in programs:
        with st.expander(
            f"{program['platform']} — {program['program_name']}", expanded=False
        ):
            st.caption(
                f"**Model:** {BUDGET_MODEL_LABELS.get(program['budget_model'], program['budget_model'])} · "
                f"**Unit:** {VALUE_UNIT_LABELS.get(program['value_unit'], program['value_unit'])}"
            )
            if program.get("notes_template"):
                st.markdown(program["notes_template"])
            if program.get("project_criteria_hint"):
                st.info(f"**Project criteria:** {program['project_criteria_hint']}")
            if program.get("source_reference"):
                st.caption(f"Source: {program['source_reference']}")

            with st.form(f"period_form_{program['id']}"):
                c1, c2 = st.columns(2)
                default_label = (
                    "2026 Q4" if program["budget_model"] == "quarterly" else date.today().strftime("%Y-%m")
                )
                period_label = c1.text_input("Period label", value=default_label, key=f"pl_{program['id']}")
                budgeted = c2.number_input(
                    f"Budgeted value ({VALUE_UNIT_LABELS.get(program['value_unit'], program['value_unit'])})",
                    min_value=0.0,
                    step=1000.0,
                    key=f"pv_{program['id']}",
                )
                if st.form_submit_button("Save period budget"):
                    service.upsert_program_period(program["id"], period_label, budgeted or None)
                    st.success(f"Saved {period_label} budget for {program['program_name']}.")
                    st.rerun()

    if not capacity.empty:
        st.subheader("Budget vs allocated vs delivered")
        st.dataframe(capacity, use_container_width=True, hide_index=True)
        st.caption(
            "Units are kept separate per program (USD, impressions, share %). "
            "Delivered reflects reported utilization — partner-served value is often a fraction of committed."
        )


# ----------------------------------------------------------------------
# Project requests (submission pipeline)
# ----------------------------------------------------------------------

REQUEST_STATUSES = [
    "draft",
    "submitted",
    "under_review",
    "approved",
    "allocated",
    "completed",
    "declined",
]


def render_project_requests_tab(service: CreditService) -> None:
    st.subheader("Project requests")
    st.caption(
        "Use this tab only if you want a **lightweight log** of requests alongside the allocations. "
        "Your existing internal submission process stays exactly the same — this does not replace it. "
        "Spotify and YouTube are managed monthly; mid-month requests typically roll to the next month."
    )
    programs = service.list_programs()
    program_options = {f"{p['platform']} — {p['program_name']}": p["id"] for p in programs}

    with st.expander("New project request", expanded=True):
        with st.form("project_request_form"):
            c1, c2, c3 = st.columns(3)
            artist = c1.text_input("Artist *")
            project_title = c2.text_input("Project title")
            track = c3.text_input("Track")
            program_label = st.selectbox("Program *", list(program_options.keys()))
            c4, c5, c6 = st.columns(3)
            period_label = c4.text_input("Period (e.g. 2026 Q4 or 2026-11)")
            requested_value = c5.number_input("Requested value", min_value=0.0, step=1000.0)
            status = c6.selectbox("Status", REQUEST_STATUSES, index=0)
            c7, c8 = st.columns(2)
            run_start = c7.date_input("Desired run start", value=None)
            run_end = c8.date_input("Desired run end", value=None)
            reason = st.text_area("Type of support requested & reason for consideration")
            streaming_uplift = st.text_input("Metrics (streaming uplift, platform creates, etc.)")
            top_markets = st.text_input("Top 5 markets for artist/track")
            territory = st.text_area("Territory rights constraints (explicit geographic limitations)")
            notes = st.text_area("Internal notes")
            submitted = st.form_submit_button("Save request", type="primary")

    if submitted:
        if not artist:
            st.error("Artist is required.")
            return
        program_id = program_options[program_label]
        program = service.get_program(program_id)
        service.create_project_request(
            {
                "artist": artist,
                "project_title": project_title or None,
                "track": track or None,
                "program_id": program_id,
                "period_label": period_label or None,
                "requested_value": requested_value or None,
                "value_unit": program["value_unit"] if program else None,
                "request_status": status,
                "run_start": str(run_start) if run_start else None,
                "run_end": str(run_end) if run_end else None,
                "reason_for_consideration": reason or None,
                "streaming_uplift": streaming_uplift or None,
                "top_markets": top_markets or None,
                "territory_constraints": territory or None,
                "submitted_at": date.today().isoformat() if status in {"submitted", "under_review", "approved"} else None,
                "approved_at": date.today().isoformat() if status == "approved" else None,
                "notes": notes or None,
            }
        )
        st.success("Project request saved.")
        st.rerun()

    requests = service.list_project_requests()
    if requests:
        st.markdown("**Request pipeline**")
        st.dataframe(
            [
                {
                    "Artist": r["artist"],
                    "Project": r.get("project_title") or "",
                    "Track": r.get("track") or "",
                    "Program": r["program_name"],
                    "Period": r.get("period_label") or "",
                    "Status": r["request_status"],
                    "Requested": _fmt(r.get("requested_value"), r.get("value_unit") or "other"),
                    "Run window": f"{r.get('run_start') or ''} → {r.get('run_end') or ''}",
                }
                for r in requests
            ],
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("**Update status**")
        options = {f"#{r['id']} — {r['artist']} ({r['program_name']})": r["id"] for r in requests}
        selected = st.selectbox("Request", list(options.keys()))
        new_status = st.selectbox("New status", REQUEST_STATUSES, key="req_status_update")
        if st.button("Update status"):
            service.update_project_status(
                options[selected],
                new_status,
                submitted_at=date.today().isoformat() if new_status in {"submitted", "under_review"} else None,
                approved_at=date.today().isoformat() if new_status == "approved" else None,
            )
            st.success("Status updated.")
            st.rerun()
    else:
        st.info("No project requests yet. Create one above.")


# ----------------------------------------------------------------------
# Allocations & utilization
# ----------------------------------------------------------------------


def render_allocations_tab(service: CreditService, filters: dict) -> None:
    st.subheader("Allocations & utilization")
    st.caption(
        "Commit partner-funded value to projects, then record reported delivery "
        "(impressions served, spend matched, value used). Delivered is often a fraction of committed."
    )
    programs = service.list_programs()
    program_options = {f"{p['platform']} — {p['program_name']}": p["id"] for p in programs}

    approved_requests = service.list_project_requests(status="approved") + service.list_project_requests(status="allocated")
    request_options = {
        f"#{r['id']} — {r['artist']} — {r.get('track') or ''} ({r['program_name']})": r for r in approved_requests
    }

    with st.expander("New allocation", expanded=True):
        with st.form("allocation_form"):
            program_label = st.selectbox("Program *", list(program_options.keys()))
            c1, c2 = st.columns(2)
            period_label = c1.text_input("Period label *", value="2026 Q4")
            request_label = c2.selectbox("Link to approved request (optional)", ["— none —"] + list(request_options.keys()))
            program_id = program_options[program_label]
            program = service.get_program(program_id)
            allocated_value = st.number_input(
                f"Allocated value ({VALUE_UNIT_LABELS.get(program['value_unit'], program['value_unit'])}) *",
                min_value=0.0,
                step=1000.0,
            )
            c3, c4 = st.columns(2)
            artist = c3.text_input("Artist (if not linked to request)")
            track = c4.text_input("Track (if not linked to request)")
            allocated_at = st.date_input("Allocation date", value=date.today())
            notes = st.text_area("Notes")
            submitted = st.form_submit_button("Save allocation", type="primary")

    if submitted:
        selected_request = request_options.get(request_label)
        service.create_allocation(
            program_id,
            period_label,
            allocated_value,
            project_id=selected_request["id"] if selected_request else None,
            artist=(selected_request.get("artist") if selected_request else artist) or None,
            track=(selected_request.get("track") if selected_request else track) or None,
            allocated_at=str(allocated_at),
            notes=notes or None,
        )
        if selected_request:
            service.update_project_status(selected_request["id"], "allocated")
        st.success("Allocation saved.")
        st.rerun()

    allocations = service.list_allocations_by_program(include_demo=filters["include_demo"])
    if allocations:
        st.markdown("**Current allocations**")
        st.dataframe(
            [
                {
                    "Program": a["program_name"],
                    "Platform": a["platform"],
                    "Period": a["period_label"],
                    "Artist": a.get("artist") or a.get("project_artist") or "",
                    "Track": a.get("track") or a.get("project_track") or "",
                    "Allocated": _fmt(a["allocated_value"], a["value_unit"]),
                    "Unit": a["value_unit"],
                }
                for a in allocations
            ],
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("**Record reported utilization**")
        alloc_options = {
            f"#{a['id']} — {a['program_name']} — {a['period_label']} — {a.get('artist') or a.get('project_artist') or ''}": a
            for a in allocations
        }
        with st.form("utilization_form"):
            alloc_label = st.selectbox("Allocation", list(alloc_options.keys()))
            selected_alloc = alloc_options[alloc_label]
            c1, c2 = st.columns(2)
            record_date = c1.date_input("Report date", value=date.today())
            delivered = c2.number_input(
                f"Delivered value ({VALUE_UNIT_LABELS.get(selected_alloc['value_unit'], selected_alloc['value_unit'])})",
                min_value=0.0,
                step=1000.0,
            )
            c3, c4 = st.columns(2)
            impressions = c3.number_input("Impressions served (if applicable)", min_value=0.0, step=1000.0)
            gross_spend = c4.number_input("Associated gross media spend", min_value=0.0, step=100.0)
            verification = st.selectbox(
                "Verification source",
                ["Manual entry", "WAVO report", "Platform report", "Partner confirmation"],
            )
            reference = st.text_input("Reference / link")
            if st.form_submit_button("Record utilization"):
                service.record_utilization(
                    selected_alloc["id"],
                    str(record_date),
                    delivered,
                    impressions_served=impressions or None,
                    gross_media_spend=gross_spend or None,
                    verification_source=verification,
                    reference=reference or None,
                )
                st.success("Utilization recorded.")
                st.rerun()

        capacity = service.program_capacity_summary(include_demo=filters["include_demo"])
        if not capacity.empty:
            st.subheader("Program capacity summary")
            st.dataframe(capacity, use_container_width=True, hide_index=True)
    else:
        st.info("No allocations yet. Approve a project request and allocate partner-funded value.")


# ----------------------------------------------------------------------
# Legacy billing-credit inventory (kept for classic promotional credits)
# ----------------------------------------------------------------------


def render_inventory_tab(service: CreditService, filters: dict) -> None:
    settings = load_warning_settings()
    filter_payload = {k: v for k, v in filters.items() if k != "include_demo"}
    rows = service.list_credits(
        include_demo=filters["include_demo"],
        filters=filter_payload,
    )
    inventory = build_inventory_dataframe(rows)
    summary = summarize_by_currency(inventory)

    st.subheader("Billing-level promotional credits (legacy)")
    st.caption(
        "Use this only for **actual billing coupons** that reduce invoiced ad spend. "
        "For Global Catalog partner allocations (TikTok, YouTube gratis, Spotify, Snap match, Meta fund), "
        "use **Programs**, **Project requests**, and **Allocations** instead."
    )
    if summary.empty:
        st.info("No billing-level promotional credits recorded. This is expected for partner-funded allocations.")
    else:
        for _, row in summary.iterrows():
            currency = row["Currency"]
            st.markdown(f"#### Totals ({currency})")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Issued", f"{row['Total Issued']:,.2f}")
            c2.metric("Available", f"{row['Total Available']:,.2f}")
            c3.metric("Used", f"{row['Total Used']:,.2f}")
            c4.metric("Expired / forfeited", f"{row['Expired / Forfeited']:,.2f}")
        st.dataframe(inventory.drop(columns=["_credit_id", "Demo"], errors="ignore"), use_container_width=True)

        warnings = expiration_warnings(rows, settings)
        if warnings:
            render_warning_banner(warnings)


def render_import_tab(service: CreditService) -> None:
    st.subheader("Import promotional credits (billing-level only)")
    st.caption(
        "Upload CSV or Excel of **billing promotional credit reports** that reduce invoiced spend. "
        "Do not import ordinary ad spend as credit utilization. "
        "Partner allocations (YouTube gratis, TikTok programs, etc.) belong in **Allocations**, not here."
    )
    uploaded = st.file_uploader("Upload file", type=["csv", "xlsx", "xls"])
    if not uploaded:
        return
    try:
        frame = load_tabular_upload(uploaded)
    except Exception as exc:
        st.error(f"Could not read file: {exc}")
        return
    st.dataframe(frame.head(15), use_container_width=True)
    suggested = service.suggest_column_map(list(frame.columns))
    st.markdown("**Column mapping**")
    mapping: dict[str, str | None] = {}
    cols = ["— skip —"] + list(frame.columns)
    for field in suggested:
        default = suggested[field]
        index = cols.index(default) if default in cols else 0
        mapping[field] = st.selectbox(field, cols, index=index)
        if mapping[field] == "— skip —":
            mapping[field] = None
    if st.button("Import rows", type="primary"):
        imported, errors = service.import_rows(
            frame,
            mapping,
            file_type="csv" if uploaded.name.lower().endswith(".csv") else "excel",
            filename=uploaded.name,
        )
        st.success(f"Imported {imported} credit row(s).")
        for err in errors[:20]:
            st.warning(err)


def render_settings_tab() -> None:
    st.subheader("Advanced settings")
    settings = load_warning_settings()
    with st.form("warning_settings"):
        soon = st.number_input("Expiring soon threshold (days)", min_value=1, max_value=60, value=settings.expiring_soon_days)
        warn = st.number_input("Expiration warning threshold (days)", min_value=1, max_value=180, value=settings.expiring_warning_days)
        if st.form_submit_button("Save thresholds"):
            save_warning_settings(WarningSettings(expiring_soon_days=int(soon), expiring_warning_days=int(warn)))
            st.success("Warning thresholds updated.")
