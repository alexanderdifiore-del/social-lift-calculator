"""Reusable Streamlit fragments for the credits dashboard."""

from __future__ import annotations

from datetime import date

import plotly.graph_objects as go
import streamlit as st

from lollie.credits.constants import (
    AD_PLATFORMS,
    APPLICATION_MODES,
    CREDIT_CATEGORY_BY_PLATFORM,
    CREDIT_STATUS_VALUES,
    VERIFICATION_SOURCES,
)
from lollie.credits.metrics import (
    build_inventory_dataframe,
    expiration_warnings,
    platform_comparison,
    summarize_by_currency,
)
from lollie.credits.service import CreditService
from lollie.credits.settings import WarningSettings, load_warning_settings, save_warning_settings
from lollie.imports.file_loader import load_tabular_upload


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
    statuses = ["All"] + CREDIT_STATUS_VALUES

    return {
        "include_demo": include_demo,
        "platform": st.sidebar.selectbox("Platform", platforms),
        "ad_account_id": st.sidebar.selectbox("Ad account", accounts),
        "artist": st.sidebar.selectbox("Artist", artists),
        "campaign": st.sidebar.selectbox("Campaign", campaigns),
        "market": st.sidebar.selectbox("Market", markets),
        "credit_status": st.sidebar.selectbox("Credit status", statuses),
        "date_from": (
            st.sidebar.date_input("Issued from")
            if st.sidebar.checkbox("Filter issued from", value=False)
            else None
        ),
        "date_to": (
            st.sidebar.date_input("Issued to")
            if st.sidebar.checkbox("Filter issued to", value=False)
            else None
        ),
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
        st.caption(f"+ {len(warnings) - 12} additional notices (see Advanced settings).")


def render_inventory_tab(service: CreditService, filters: dict) -> None:
    settings = load_warning_settings()
    filter_payload = {k: v for k, v in filters.items() if k != "include_demo"}
    if filter_payload.get("date_from"):
        filter_payload["date_from"] = str(filter_payload["date_from"])
    if filter_payload.get("date_to"):
        filter_payload["date_to"] = str(filter_payload["date_to"])

    rows = service.list_credits(
        include_demo=filters["include_demo"],
        filters=filter_payload,
    )
    inventory = build_inventory_dataframe(rows)
    summary = summarize_by_currency(inventory)

    st.subheader("Credit inventory")
    if summary.empty:
        st.info(
            "No promotional credits recorded yet. Use **Register Credit** to add your first offer, "
            "or import a billing / promotional credit report."
        )
    else:
        for _, row in summary.iterrows():
            currency = row["Currency"]
            st.markdown(f"#### Totals ({currency})")
            c1, c2, c3, c4, c5, c6 = st.columns(6)
            c1.metric("Issued", f"{row['Total Issued']:,.2f}")
            c2.metric("Available", f"{row['Total Available']:,.2f}")
            c3.metric("Used", f"{row['Total Used']:,.2f}")
            c4.metric("Pending qualification", f"{row['Pending Qualification']:,.2f}")
            c5.metric("Expired / forfeited", f"{row['Expired / Forfeited']:,.2f}")
            net_note = "Net media cost appears under **Cost Analysis** (verified credits only)."
            c6.metric("Net cost", "See Cost Analysis", help=net_note)

        st.dataframe(inventory.drop(columns=["_credit_id", "Demo"], errors="ignore"), use_container_width=True)

    warnings = expiration_warnings(rows, settings)
    flags = service.discrepancy_flags(include_demo=filters["include_demo"])
    for flag in flags:
        warnings.append({"level": "warning", "message": flag})
    if warnings:
        st.subheader("Alerts")
        render_warning_banner(warnings)

    comparison = platform_comparison(inventory)
    if not comparison.empty:
        st.subheader("Platform comparison")
        st.dataframe(comparison, use_container_width=True)
        fig = go.Figure()
        for _, row in comparison.iterrows():
            fig.add_trace(
                go.Bar(
                    name=row["Platform"],
                    x=["Issued", "Utilized", "Remaining"],
                    y=[
                        row["Promotional Value Issued"],
                        row["Utilized"],
                        row["Remaining Available"],
                    ],
                )
            )
        fig.update_layout(barmode="group", height=380, title="Promotional value by platform (per currency group)")
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Amounts are not combined across currencies.")


def render_register_tab(service: CreditService) -> None:
    st.subheader("Register promotional credit")
    st.caption(
        "Manual entries are labeled **manually reported** until reconciled with an authoritative billing export. "
        "Promotional offer terms are configurable — Lollie does not enforce platform-specific thresholds."
    )
    with st.form("register_credit_form"):
        c1, c2 = st.columns(2)
        platform = c1.selectbox("Platform *", AD_PLATFORMS)
        categories = CREDIT_CATEGORY_BY_PLATFORM.get(platform, ["Other / custom"])
        ad_account_id = c2.text_input("Ad account ID *")
        promotion_name = st.text_input("Promotion name or identifier *")
        credit_category = st.selectbox("Credit category *", categories + ["Other / custom"])
        application_mode = st.selectbox("How credit applies (per your offer terms)", APPLICATION_MODES)
        c3, c4, c5 = st.columns(3)
        issued_amount = c3.number_input("Original issued amount *", min_value=0.0, step=100.0)
        currency = c4.text_input("Currency *", value="USD")
        amount_applied = c5.number_input(
            "Amount actually applied (optional)",
            min_value=0.0,
            step=50.0,
            help="Only enter amounts verified from billing. Do not guess from spend.",
        )
        c6, c7, c8 = st.columns(3)
        date_issued = c6.date_input("Date issued", value=date.today())
        activation_date = c7.date_input("Activation date", value=date.today())
        expiration_date = c8.date_input("Expiration date", value=date.today())
        c9, c10 = st.columns(2)
        qualifying_spend = c9.number_input(
            "Qualifying spend requirement (optional)",
            min_value=0.0,
            step=500.0,
            help="Enter the requirement from the promotion terms — not a system default.",
        )
        qualifying_currency = c10.text_input("Qualifying spend currency", value="USD")
        eligibility = st.text_area("Eligibility restrictions (optional)")
        eligible_campaigns = st.text_input("Eligible campaigns (comma-separated, optional)")
        c11, c12, c13 = st.columns(3)
        artist = c11.text_input("Artist")
        campaign = c12.text_input("Campaign")
        market = c13.selectbox("Market", ["", "US", "Global", "Europe", "LATAM", "APAC"])
        credit_status = st.selectbox("Credit status", CREDIT_STATUS_VALUES, index=0)
        verification_source = st.selectbox("Verification source", VERIFICATION_SOURCES)
        last_verified = st.date_input("Last verified date", value=date.today())
        notes = st.text_area("Notes")
        submitted = st.form_submit_button("Save credit", type="primary")

    if submitted:
        if not ad_account_id or not promotion_name:
            st.error("Ad account ID and promotion name are required.")
            return
        payload = {
            "platform": platform,
            "ad_account_id": ad_account_id,
            "promotion_name": promotion_name,
            "credit_category": credit_category,
            "application_mode": application_mode,
            "original_issued_amount": issued_amount,
            "currency": currency,
            "date_issued": str(date_issued) if date_issued else None,
            "activation_date": str(activation_date) if activation_date else None,
            "expiration_date": str(expiration_date) if expiration_date else None,
            "qualifying_spend_requirement": qualifying_spend or None,
            "qualifying_spend_currency": qualifying_currency,
            "eligibility_restrictions": eligibility or None,
            "eligible_campaigns": eligible_campaigns or None,
            "artist": artist or None,
            "campaign": campaign or None,
            "market": market or None,
            "credit_status": credit_status,
            "verification_source": verification_source,
            "last_verified_date": str(last_verified),
            "amount_applied": amount_applied,
            "notes": notes or None,
        }
        try:
            credit_id = service.create_credit(payload)
            st.success(f"Credit saved (ID {credit_id}). Marked manually reported until reconciled with billing.")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))


def render_import_tab(service: CreditService) -> None:
    st.subheader("Import promotional credits")
    st.caption(
        "Upload CSV or Excel billing / promotional credit reports. Map columns flexibly. "
        "Lollie will **not** treat ordinary ad spend as credit utilization."
    )
    uploaded = st.file_uploader("Upload file", type=["csv", "xlsx", "xls"])
    if not uploaded:
        st.info("Example columns: platform, ad_account_id, promotion_name, issued_amount, currency, expiration_date")
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


def render_allocation_tab(service: CreditService, filters: dict) -> None:
    st.subheader("Allocation & reconciliation")
    credits = service.list_credits(include_demo=filters["include_demo"])
    if not credits:
        st.info("Register credits before allocating to campaigns.")
        return
    options = {
        f"#{c['id']} — {c['platform']} — {c['promotion_name']}": c["id"] for c in credits
    }
    selected = st.selectbox("Credit", list(options.keys()))
    credit_id = options[selected]
    st.markdown("**Ledger history**")
    ledger = service.ledger_for_credit(credit_id)
    st.dataframe(ledger, use_container_width=True)
    with st.form("allocation_form"):
        campaign_name = st.text_input("Campaign name *")
        campaign_id = st.text_input("Campaign ID (optional)")
        allocation_type = st.selectbox(
            "Allocation type",
            ["eligible", "planned", "applied"],
            format_func=lambda x: {
                "eligible": "Eligible campaign",
                "planned": "Planned / reserved (does not reduce billed cost)",
                "applied": "Applied / redeemed (verified utilization)",
            }[x],
        )
        amount = st.number_input("Amount", min_value=0.0, step=50.0)
        notes = st.text_input("Notes")
        submit = st.form_submit_button("Add allocation")
    if submit and campaign_name:
        service.add_allocation(
            credit_id,
            campaign_name,
            allocation_type,
            campaign_id=campaign_id or None,
            amount=amount or None,
            notes=notes or None,
        )
        st.success("Allocation recorded in transaction history.")
        st.rerun()

    st.divider()
    st.markdown("**Reconcile with billing**")
    with st.form("reconcile_form"):
        applied_amount = st.number_input("Verified applied amount from billing", min_value=0.0, step=50.0)
        reference = st.text_input("Billing reference / invoice line")
        if st.form_submit_button("Record verified application"):
            service.add_ledger_entry(
                credit_id,
                "import_reconcile",
                applied_amount,
                reference=reference,
                verification_source="Reconciled billing",
            )
            st.success("Reconciliation entry added; manual flag cleared when source is reconciled billing.")
            st.rerun()


def render_cost_tab(service: CreditService, filters: dict) -> None:
    st.subheader("Advertising cost analysis")
    st.caption(
        "Gross media spend drives delivery metrics (CPM/CPC). "
        "Net media cost uses **verified** promotional credit utilization only."
    )
    with st.expander("Record gross campaign spend"):
        with st.form("campaign_spend_form"):
            c1, c2 = st.columns(2)
            platform = c1.selectbox("Platform", AD_PLATFORMS)
            campaign_name = c2.text_input("Campaign name *")
            gross = st.number_input("Gross media spend *", min_value=0.0, step=100.0)
            currency = st.text_input("Currency", value="USD")
            artist = st.text_input("Artist")
            if st.form_submit_button("Save spend"):
                service.record_campaign_spend(
                    {
                        "platform": platform,
                        "campaign_name": campaign_name,
                        "gross_media_spend": gross,
                        "currency": currency,
                        "artist": artist or None,
                    }
                )
                st.success("Campaign spend saved.")
                st.rerun()

    summary = service.campaign_cost_summary(include_demo=filters["include_demo"])
    if summary.empty:
        st.info("Add campaign spend records to see gross vs net analysis.")
    else:
        st.dataframe(summary, use_container_width=True)
        for _, row in summary.iterrows():
            st.markdown(
                f"**{row['Campaign']}** ({row['Platform']}): "
                f"Gross **{row['Gross Media Spend']:,.2f} {row['Currency']}** · "
                f"Verified credits **{row['Verified Promotional Credits Applied']:,.2f}** · "
                f"Net **{row['Net Media Cost (verified credits only)']:,.2f}**"
            )


def render_settings_tab() -> None:
    st.subheader("Advanced settings")
    settings = load_warning_settings()
    with st.form("warning_settings"):
        soon = st.number_input("Expiring soon threshold (days)", min_value=1, max_value=60, value=settings.expiring_soon_days)
        warn = st.number_input("Expiration warning threshold (days)", min_value=1, max_value=180, value=settings.expiring_warning_days)
        if st.form_submit_button("Save thresholds"):
            save_warning_settings(WarningSettings(expiring_soon_days=int(soon), expiring_warning_days=int(warn)))
            st.success("Warning thresholds updated.")
