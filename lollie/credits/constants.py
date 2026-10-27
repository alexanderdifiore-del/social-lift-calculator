"""Configurable platform and credit metadata — not universal eligibility rules."""

AD_PLATFORMS = [
    "Meta Ads",
    "TikTok Ads",
    "Google Ads / YouTube",
    "Snapchat Ads",
]

VERIFICATION_SOURCES = [
    "Manual entry",
    "CSV import",
    "Excel import",
    "WAVO report",
    "Platform billing export",
    "Reconciled billing",
]

CREDIT_STATUS_VALUES = [
    "available",
    "pending_qualification",
    "pending_issuance",
    "awaiting_activation",
    "reserved",
    "partially_applied",
    "fully_applied",
    "expired",
    "forfeited",
]

CREDIT_CATEGORY_BY_PLATFORM: dict[str, list[str]] = {
    "Meta Ads": [
        "Account-level promotional credit",
        "Campaign-restricted promotional credit",
        "Other / custom",
    ],
    "TikTok Ads": [
        "Free promotional credit",
        "Assignable promotional credit",
        "Conditional promotional credit",
        "Other / custom",
    ],
    "Google Ads / YouTube": [
        "Issued promotional credit (available)",
        "Pending qualification (spend-to-earn)",
        "Other / custom",
    ],
    "Snapchat Ads": [
        "Conditional promotional credit",
        "Other / custom",
    ],
}

APPLICATION_MODES = [
    "Applies automatically (per offer terms)",
    "Must allocate to campaigns",
    "Requires qualifying conditions",
    "Unknown / verify in ad account",
]

IMPORT_FIELD_ALIASES: dict[str, list[str]] = {
    "platform": ["platform", "ad_platform", "network"],
    "ad_account_id": ["ad_account_id", "account_id", "account", "ad_account"],
    "promotion_name": ["promotion_name", "promotion", "promo_name", "offer_name", "promotion_id"],
    "credit_category": ["credit_category", "credit_type", "category", "type"],
    "issued_amount": ["issued_amount", "credit_amount", "amount", "original_amount", "issued"],
    "currency": ["currency", "currency_code"],
    "date_issued": ["date_issued", "issued_date", "issue_date"],
    "activation_date": ["activation_date", "activate_date", "start_date"],
    "expiration_date": ["expiration_date", "expiry_date", "expires", "expiration"],
    "qualifying_spend_requirement": [
        "qualifying_spend_requirement",
        "qualifying_spend",
        "spend_requirement",
        "minimum_spend",
    ],
    "amount_applied": ["amount_applied", "used_amount", "applied_amount", "redeemed"],
    "verification_source": ["verification_source", "source", "report_source"],
    "artist": ["artist", "artist_name"],
    "campaign": ["campaign", "campaign_name", "campaign_id"],
    "market": ["market", "region", "country"],
    "notes": ["notes", "comment", "comments"],
}
