import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.markdown(
    """
    <style>
    .lollie-title {
        font-size: 4.4rem;
        font-weight: 700;
        letter-spacing: 0.14em;
        color: #8ffcff;
        margin-bottom: 0.1rem;
        text-shadow:
            0 0 8px rgba(143, 252, 255, 0.8),
            0 0 18px rgba(143, 252, 255, 0.45),
            0 0 32px rgba(143, 252, 255, 0.25);
        font-family: "Helvetica Neue", Arial, sans-serif;
    }

    .lollie-subtitle {
        font-size: 0.95rem;
        color: rgba(255, 255, 255, 0.62);
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-top: -0.4rem;
        margin-bottom: 2rem;
    }
    </style>

    <div class="lollie-title">lollie</div>
    <div class="lollie-subtitle">social streaming lift intelligence</div>
    """,
    unsafe_allow_html=True
)

# -----------------------------
# SIDEBAR INPUTS
# -----------------------------

st.sidebar.title("Campaign Inputs")

artist_name = st.sidebar.text_input("Artist Name", "Example Artist")
song_title = st.sidebar.text_input("Song Title", "Example Song")

st.sidebar.markdown("---")
st.sidebar.subheader("Mock Opus / Track Info")

opus_campaign_id = st.sidebar.text_input("Opus Campaign ID", "OPUS-DEMO-001")
isrc = st.sidebar.text_input("ISRC", "USAT00000000")
release_phase = st.sidebar.selectbox(
    "Release Phase",
    ["Pre-release", "Release week", "Catalog/reactivation", "Tour moment", "Sync/viral moment"]
)

st.sidebar.markdown("---")
st.sidebar.subheader("Social Post Event")

platform = st.sidebar.selectbox(
    "Platform",
    ["TikTok", "Instagram Reels", "YouTube Shorts"]
)

post_type = st.sidebar.selectbox(
    "Post Type",
    ["Organic artist post", "Influencer post", "Paid boost", "UGC trend"]
)

post_date = st.sidebar.date_input("Post Date", datetime.now().date())

post_hour = st.sidebar.slider(
    "Post Hour of Day",
    min_value=0,
    max_value=23,
    value=18,
    help="This is the clock hour when the post went live. Example: 18 = 6 PM, 23 = 11 PM."
)

post_timestamp = datetime.combine(post_date, datetime.min.time()) + timedelta(hours=post_hour)

impact_window_hours = st.sidebar.slider(
    "Impact Window Length",
    min_value=6,
    max_value=168,
    value=24,
    step=6,
    help="How many hours after the social post you want to measure lift."
)

multi_post = st.sidebar.checkbox("Simulate Second Post", False)

if multi_post:
    second_post_delay = st.sidebar.slider(
        "Second Post Delay After First Post",
        min_value=6,
        max_value=168,
        value=48,
        step=6
    )

st.sidebar.markdown("---")
st.sidebar.subheader("Artist / Market Assumptions")

artist_tier = st.sidebar.selectbox(
    "Artist Tier",
    ["Emerging", "Mid-tier", "Established", "Superstar"]
)

primary_market = st.sidebar.selectbox(
    "Primary Market",
    ["US", "Global", "Europe", "LATAM", "APAC"]
)

dsp_focus = st.sidebar.selectbox(
    "DSP Focus",
    ["All DSPs", "Spotify-heavy", "Apple-heavy", "YouTube Music-heavy", "Amazon-heavy"]
)

campaign_intensity = st.sidebar.slider(
    "Campaign Intensity Score",
    min_value=1,
    max_value=10,
    value=6,
    help="Mock score representing how strong the social push is."
)

analysis_days = st.sidebar.selectbox(
    "Analysis Window",
    [7, 14, 30],
    index=0
)

st.sidebar.markdown("---")
st.sidebar.subheader("Manual Demo Inputs")

data_mode = st.sidebar.radio(
    "Data Source Mode",
    ["Auto simulation", "Manual demo inputs", "CSV upload"],
    help="Choose whether the dashboard uses simulated data, manual demo numbers, or an uploaded CSV file."
)

uploaded_csv = None

if data_mode == "CSV upload":
    uploaded_csv = st.sidebar.file_uploader(
        "Upload Streaming CSV",
        type=["csv"],
        help="Upload a CSV with timestamp and actual_streams columns. expected_baseline_streams is optional."
    )

    with st.sidebar.expander("CSV format example"):
        st.code(
            """timestamp,actual_streams,expected_baseline_streams
2026-06-17 00:00:00,2400,2300
2026-06-17 01:00:00,2100,2200
2026-06-17 02:00:00,1900,2100""",
            language="csv"
        )

manual_expected_streams = st.sidebar.number_input(
    "Manual Expected Streams",
    min_value=0,
    value=65000,
    step=1000,
    help="What streams would have been without the social post."
)

manual_actual_streams = st.sidebar.number_input(
    "Manual Actual Streams",
    min_value=0,
    value=148000,
    step=1000,
    help="What streams happened after the social post."
)

manual_social_reach = st.sidebar.number_input(
    "Manual Social Reach / Views",
    min_value=0,
    value=850000,
    step=10000,
    help="Fake TikTok/Reels/Shorts views or reach number for demo purposes."
)

manual_engagement_rate = st.sidebar.slider(
    "Manual Engagement Rate (%)",
    min_value=0.0,
    max_value=25.0,
    value=5.5,
    step=0.1,
    help="Fake engagement rate for the post."
)


st.sidebar.markdown("---")
st.sidebar.subheader("Commerce / Product Revenue")

commerce_enabled = st.sidebar.checkbox(
    "Enable Commerce Revenue Tracking",
    value=True,
    help="Estimate product revenue associated with the social/streaming impact window."
)

revenue_attribution_method = st.sidebar.selectbox(
    "Revenue Attribution Method",
    [
        "Manual attributed units",
        "Estimate from social reach"
    ],
    help="Manual mode lets you type units sold. Estimate mode calculates units from social reach and purchase conversion assumptions."
)

product_catalog = {
    "Vinyl LP": {
        "price": 29.99,
        "cost": 11.00,
        "units": 120,
        "conversion": 0.025,
        "fees": 8.0
    },
    "Limited Color Vinyl": {
        "price": 34.99,
        "cost": 13.00,
        "units": 80,
        "conversion": 0.018,
        "fees": 8.0
    },
    "CD": {
        "price": 14.99,
        "cost": 4.00,
        "units": 95,
        "conversion": 0.015,
        "fees": 7.0
    },
    "Cassette": {
        "price": 12.99,
        "cost": 3.50,
        "units": 40,
        "conversion": 0.008,
        "fees": 7.0
    },
    "Deluxe Edition / Box Set": {
        "price": 89.99,
        "cost": 35.00,
        "units": 25,
        "conversion": 0.004,
        "fees": 9.0
    },
    "Signed Physical Product": {
        "price": 49.99,
        "cost": 18.00,
        "units": 35,
        "conversion": 0.006,
        "fees": 8.0
    },
    "Artist Apparel": {
        "price": 35.00,
        "cost": 12.00,
        "units": 150,
        "conversion": 0.030,
        "fees": 10.0
    },
    "Accessories": {
        "price": 18.00,
        "cost": 6.00,
        "units": 100,
        "conversion": 0.020,
        "fees": 10.0
    },
    "Poster / Print": {
        "price": 25.00,
        "cost": 7.00,
        "units": 60,
        "conversion": 0.012,
        "fees": 8.0
    },
    "Merch Bundle": {
        "price": 65.00,
        "cost": 25.00,
        "units": 45,
        "conversion": 0.007,
        "fees": 9.0
    },
    "Digital Album / Download": {
        "price": 10.99,
        "cost": 1.00,
        "units": 75,
        "conversion": 0.018,
        "fees": 15.0
    },
    "Fan Club / Membership": {
        "price": 9.99,
        "cost": 1.50,
        "units": 50,
        "conversion": 0.010,
        "fees": 12.0
    },
    "Ticket / VIP Upsell": {
        "price": 75.00,
        "cost": 25.00,
        "units": 30,
        "conversion": 0.005,
        "fees": 10.0
    }
}

selected_products = st.sidebar.multiselect(
    "Product Categories",
    list(product_catalog.keys()),
    default=[
        "Vinyl LP",
        "CD",
        "Artist Apparel",
        "Merch Bundle"
    ],
    help="Select the product categories you want to include in the revenue model."
)

commerce_rows = []

if commerce_enabled:
    for index, product_name in enumerate(selected_products):
        defaults = product_catalog[product_name]

        with st.sidebar.expander(product_name, expanded=False):
            average_selling_price = st.number_input(
                f"{product_name} Avg Selling Price ($)",
                min_value=0.0,
                value=float(defaults["price"]),
                step=1.0,
                key=f"price_{index}"
            )

            unit_cost = st.number_input(
                f"{product_name} Unit Cost / COGS ($)",
                min_value=0.0,
                value=float(defaults["cost"]),
                step=1.0,
                key=f"cost_{index}"
            )

            fee_rate = st.slider(
                f"{product_name} Fees / Discounts (%)",
                min_value=0.0,
                max_value=50.0,
                value=float(defaults["fees"]),
                step=0.5,
                key=f"fees_{index}"
            )

            if revenue_attribution_method == "Manual attributed units":
                attributed_units = st.number_input(
                    f"{product_name} Attributed Units Sold",
                    min_value=0,
                    value=int(defaults["units"]),
                    step=1,
                    key=f"units_{index}"
                )
            else:
                purchase_conversion_rate = st.number_input(
                    f"{product_name} Purchase Conversion Rate (%)",
                    min_value=0.0,
                    max_value=10.0,
                    value=float(defaults["conversion"]),
                    step=0.001,
                    format="%.3f",
                    key=f"conversion_{index}"
                )

                attributed_units = int(
                    round(manual_social_reach * (purchase_conversion_rate / 100))
                )

                st.caption(f"Estimated units: {attributed_units:,}")

            commerce_rows.append({
                "Product Category": product_name,
                "Attributed Units": attributed_units,
                "Average Selling Price": average_selling_price,
                "Unit Cost / COGS": unit_cost,
                "Fee Rate (%)": fee_rate
            })
# -----------------------------
# MOCK DATA GENERATION
# -----------------------------

hours = analysis_days * 24
start_time = post_timestamp - timedelta(days=analysis_days // 2)

timestamps = pd.date_range(start=start_time, periods=hours, freq="h")

np.random.seed(42)

tier_multiplier = {
    "Emerging": 0.8,
    "Mid-tier": 1.4,
    "Established": 2.2,
    "Superstar": 3.5
}[artist_tier]

platform_multiplier = {
    "TikTok": 1.65,
    "Instagram Reels": 1.35,
    "YouTube Shorts": 1.45
}[platform]

market_multiplier = {
    "US": 1.25,
    "Global": 1.0,
    "Europe": 1.1,
    "LATAM": 1.2,
    "APAC": 1.15
}[primary_market]

dsp_multiplier = {
    "All DSPs": 1.0,
    "Spotify-heavy": 1.15,
    "Apple-heavy": 1.05,
    "YouTube Music-heavy": 1.1,
    "Amazon-heavy": 0.95
}[dsp_focus]

post_type_multiplier = {
    "Organic artist post": 1.15,
    "Influencer post": 1.35,
    "Paid boost": 1.25,
    "UGC trend": 1.6
}[post_type]

def daily_rhythm(hour):
    if 0 <= hour <= 5:
        return 0.55
    elif 6 <= hour <= 9:
        return 0.85
    elif 10 <= hour <= 15:
        return 1.0
    elif 16 <= hour <= 20:
        return 1.45
    else:
        return 1.2

baseline_values = []

for ts in timestamps:
    base = 2800
    base *= daily_rhythm(ts.hour)
    base *= tier_multiplier
    base *= market_multiplier
    base *= dsp_multiplier
    base += np.random.normal(0, 180)

    baseline_values.append(max(base, 500))

df = pd.DataFrame({
    "timestamp": timestamps,
    "expected_baseline_streams": baseline_values
})

df["actual_streams"] = df["expected_baseline_streams"].copy()

# -----------------------------
# SOCIAL LIFT MODEL
# -----------------------------

def apply_social_lift(dataframe, event_time, strength_multiplier=1.0):
    impact_mask = (
        (dataframe["timestamp"] >= event_time)
        &
        (dataframe["timestamp"] < event_time + timedelta(hours=impact_window_hours))
    )

    n = impact_mask.sum()

    if n == 0:
        return dataframe

    starting_lift = (
        1.4
        + campaign_intensity * 0.22
        + platform_multiplier * 0.25
        + post_type_multiplier * 0.3
    ) * strength_multiplier

    ending_lift = 1.05

    decay_curve = np.linspace(starting_lift, ending_lift, n)

    dataframe.loc[impact_mask, "actual_streams"] = (
        dataframe.loc[impact_mask, "actual_streams"].values * decay_curve
    )

    return dataframe

df = apply_social_lift(df, post_timestamp, 1.0)

if multi_post:
    second_post_timestamp = post_timestamp + timedelta(hours=second_post_delay)
    df = apply_social_lift(df, second_post_timestamp, 0.65)

# -----------------------------
# CSV UPLOAD OVERRIDE WITH SMART COLUMN MAPPING
# -----------------------------

if data_mode == "CSV upload":
    if uploaded_csv is not None:
        import io

        raw_bytes = uploaded_csv.getvalue()

        decoded_text = None
        for encoding in ["utf-8-sig", "utf-8", "latin-1"]:
            try:
                decoded_text = raw_bytes.decode(encoding)
                break
            except Exception:
                pass

        if decoded_text is None:
            st.error("The uploaded file could not be decoded. Please export it again as a CSV.")
            st.stop()

        lines = [line for line in decoded_text.splitlines() if line.strip()]

        # Numbers sometimes exports a table title like "Table 1" before the real headers.
        # This finds the first row that looks like the real header row.
        header_line_index = 0

        for i, line in enumerate(lines[:30]):
            normalized_line = line.lower().replace(" ", "_")
            if "timestamp" in normalized_line and (
                "actual_streams" in normalized_line
                or "actual" in normalized_line
                or "streams" in normalized_line
            ):
                header_line_index = i
                break

        cleaned_text = "\n".join(lines[header_line_index:])

        uploaded_df = None

        # Try common separators: comma CSV, tab-separated, semicolon CSV.
        for separator in [",", "\t", ";"]:
            try:
                candidate_df = pd.read_csv(io.StringIO(cleaned_text), sep=separator)
                candidate_df = candidate_df.dropna(axis=1, how="all")

                if len(candidate_df.columns) >= 2:
                    uploaded_df = candidate_df
                    break
            except Exception:
                pass

        # Final fallback: let pandas guess the separator.
        if uploaded_df is None:
            try:
                uploaded_df = pd.read_csv(
                    io.StringIO(cleaned_text),
                    sep=None,
                    engine="python"
                )
                uploaded_df = uploaded_df.dropna(axis=1, how="all")
            except Exception:
                st.error(
                    "The uploaded file could not be read as a clean CSV. "
                    "Try exporting again from Numbers using File → Export To → CSV."
                )
                st.stop()

        # Clean column names
        uploaded_df.columns = [
            str(col)
            .strip()
            .replace("\n", " ")
            .replace("\r", " ")
            .replace("\ufeff", "")
            for col in uploaded_df.columns
        ]

        # Remove empty/unnamed columns
        uploaded_df = uploaded_df.loc[
            :,
            [
                not str(col).lower().startswith("unnamed")
                for col in uploaded_df.columns
            ]
        ]

        columns = list(uploaded_df.columns)

        if len(columns) < 2:
            st.error(
                "The CSV was uploaded, but lollie only detected one usable column. "
                "Please make sure your first real row contains: timestamp, actual_streams, expected_baseline_streams."
            )
            st.stop()

        st.success("CSV uploaded. Map your columns below.")

        with st.expander("Preview uploaded CSV", expanded=False):
            st.dataframe(uploaded_df.head(10), use_container_width=True)
            st.write("Detected columns:")
            st.write(columns)

        def guess_column_index(keywords, fallback_index):
            for keyword in keywords:
                for i, col in enumerate(columns):
                    normalized_col = str(col).lower().replace(" ", "_")
                    if keyword in normalized_col:
                        return i

            return min(fallback_index, len(columns) - 1)

        timestamp_default = guess_column_index(
            ["timestamp", "date", "time"],
            0
        )

        actual_default = guess_column_index(
            ["actual_streams", "actual", "streams"],
            1
        )

        baseline_guess_index = None
        for i, col in enumerate(columns):
            normalized_col = str(col).lower().replace(" ", "_")
            if "expected" in normalized_col or "baseline" in normalized_col:
                baseline_guess_index = i
                break

        timestamp_column = st.selectbox(
            "Select timestamp column",
            columns,
            index=timestamp_default
        )

        actual_column = st.selectbox(
            "Select actual streams column",
            columns,
            index=actual_default
        )

        baseline_column_options = ["Auto-estimate baseline"] + columns

        baseline_default_index = 0
        if baseline_guess_index is not None:
            baseline_default_index = baseline_guess_index + 1

        baseline_column = st.selectbox(
            "Select expected baseline column",
            baseline_column_options,
            index=baseline_default_index
        )

        if timestamp_column == actual_column:
            st.error("Timestamp column and actual streams column cannot be the same column.")
            st.stop()

        if baseline_column != "Auto-estimate baseline" and baseline_column in [
            timestamp_column,
            actual_column
        ]:
            st.error("Expected baseline column must be different from timestamp and actual streams.")
            st.stop()

        working_df = uploaded_df.copy()

        working_df = working_df.rename(columns={
            timestamp_column: "timestamp",
            actual_column: "actual_streams"
        })

        working_df["timestamp"] = (
            working_df["timestamp"]
            .astype(str)
            .str.replace("\n", " ", regex=False)
            .str.replace("\r", " ", regex=False)
        )

        working_df["timestamp"] = pd.to_datetime(
            working_df["timestamp"],
            errors="coerce"
        )

        working_df["actual_streams"] = pd.to_numeric(
            working_df["actual_streams"],
            errors="coerce"
        )

        working_df = working_df.dropna(subset=["timestamp", "actual_streams"])
        working_df = working_df.sort_values("timestamp")

        if working_df.empty:
            st.error(
                "The CSV uploaded, but no valid timestamp/stream rows were found. "
                "Check that timestamps look like 2026-06-17 12:00:00 and streams are numbers."
            )
            st.stop()

        if baseline_column != "Auto-estimate baseline":
            working_df = working_df.rename(columns={
                baseline_column: "expected_baseline_streams"
            })

            working_df["expected_baseline_streams"] = pd.to_numeric(
                working_df["expected_baseline_streams"],
                errors="coerce"
            )

            working_df["expected_baseline_streams"] = working_df[
                "expected_baseline_streams"
            ].fillna(working_df["actual_streams"].median())

        else:
            temp_impact_end = post_timestamp + timedelta(hours=impact_window_hours)

            non_impact_mask = (
                (working_df["timestamp"] < post_timestamp)
                |
                (working_df["timestamp"] >= temp_impact_end)
            )

            baseline_source = working_df.loc[non_impact_mask].copy()

            if baseline_source.empty:
                working_df["expected_baseline_streams"] = working_df[
                    "actual_streams"
                ].median()
            else:
                baseline_source["hour"] = baseline_source["timestamp"].dt.hour

                hourly_profile = baseline_source.groupby("hour")[
                    "actual_streams"
                ].median()

                working_df["hour"] = working_df["timestamp"].dt.hour

                working_df["expected_baseline_streams"] = (
                    working_df["hour"]
                    .map(hourly_profile)
                    .fillna(baseline_source["actual_streams"].median())
                )

                working_df = working_df.drop(columns=["hour"])

        df = working_df[[
            "timestamp",
            "expected_baseline_streams",
            "actual_streams"
        ]].copy()

        st.success("CSV data is now powering the dashboard.")

    else:
        st.warning(
            "CSV upload mode selected, but no CSV has been uploaded yet. "
            "Showing simulated data until a file is added."
        )

impact_end = post_timestamp + timedelta(hours=impact_window_hours)

impact_mask = (
    (df["timestamp"] >= post_timestamp)
    &
    (df["timestamp"] < impact_end)
)

expected_streams = df.loc[impact_mask, "expected_baseline_streams"].sum()
actual_streams = df.loc[impact_mask, "actual_streams"].sum()
social_lift_streams = actual_streams - expected_streams
lift_percent = (social_lift_streams / expected_streams) * 100

hourly_baseline_rate = df["expected_baseline_streams"].mean()

df["lift_area"] = df["actual_streams"] - df["expected_baseline_streams"]
df.loc[df["lift_area"] < 0, "lift_area"] = 0

# -----------------------------
# COMMERCE REVENUE MODEL
# -----------------------------

if commerce_enabled and len(commerce_rows) > 0:
    product_df = pd.DataFrame(commerce_rows)

    product_df["Gross Revenue"] = (
        product_df["Attributed Units"]
        * product_df["Average Selling Price"]
    )

    product_df["Total COGS"] = (
        product_df["Attributed Units"]
        * product_df["Unit Cost / COGS"]
    )

    product_df["Fees / Discounts"] = (
        product_df["Gross Revenue"]
        * (product_df["Fee Rate (%)"] / 100)
    )

    product_df["Estimated Net Revenue"] = (
        product_df["Gross Revenue"]
        - product_df["Total COGS"]
        - product_df["Fees / Discounts"]
    )

    product_df["Estimated Margin (%)"] = np.where(
        product_df["Gross Revenue"] > 0,
        (product_df["Estimated Net Revenue"] / product_df["Gross Revenue"]) * 100,
        0
    )

    total_product_units = product_df["Attributed Units"].sum()
    total_product_gross_revenue = product_df["Gross Revenue"].sum()
    total_product_net_revenue = product_df["Estimated Net Revenue"].sum()

    revenue_per_1k_social_views = (
        total_product_gross_revenue / (manual_social_reach / 1000)
        if manual_social_reach > 0
        else 0
    )

    revenue_per_lift_stream = (
        total_product_gross_revenue / social_lift_streams
        if social_lift_streams > 0
        else 0
    )

else:
    product_df = pd.DataFrame()
    total_product_units = 0
    total_product_gross_revenue = 0
    total_product_net_revenue = 0
    revenue_per_1k_social_views = 0
    revenue_per_lift_stream = 0

# Manual demo override:
# If selected, these sidebar numbers replace the simulated impact-window totals.
if data_mode == "Manual demo inputs":
    current_expected_total = df.loc[impact_mask, "expected_baseline_streams"].sum()
    current_actual_total = df.loc[impact_mask, "actual_streams"].sum()

    if current_expected_total > 0:
        df.loc[impact_mask, "expected_baseline_streams"] *= (
            manual_expected_streams / current_expected_total
        )

    if current_actual_total > 0:
        df.loc[impact_mask, "actual_streams"] *= (
            manual_actual_streams / current_actual_total
        )

    expected_streams = df.loc[impact_mask, "expected_baseline_streams"].sum()
    actual_streams = df.loc[impact_mask, "actual_streams"].sum()
    social_lift_streams = actual_streams - expected_streams

    if expected_streams > 0:
        lift_percent = (social_lift_streams / expected_streams) * 100
    else:
        lift_percent = 0

    hourly_baseline_rate = expected_streams / impact_window_hours

    df["lift_area"] = df["actual_streams"] - df["expected_baseline_streams"]
    df.loc[df["lift_area"] < 0, "lift_area"] = 0

# -----------------------------
# MAIN PAGE
# -----------------------------

st.markdown(
    """
    <div style="
        font-size: 1.35rem;
        font-weight: 600;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: rgba(143, 252, 255, 0.82);
        text-shadow:
            0 0 6px rgba(143, 252, 255, 0.35),
            0 0 14px rgba(143, 252, 255, 0.18);
        font-family: 'Helvetica Neue', Arial, sans-serif;
        margin-top: 0.75rem;
        margin-bottom: 1.5rem;
    ">
        Social Media Streaming Lift Calculator
    </div>
    """,
    unsafe_allow_html=True
)

st.subheader(f"{artist_name} — {song_title}")

st.caption(
    f"Campaign: {opus_campaign_id} | ISRC: {isrc} | Platform: {platform} | Market: {primary_market}"
)

st.info(
    f"""
    **Social post time:** {post_timestamp.strftime('%B %d, %Y at %I:%M %p')}

    The post hour is the clock hour when the post went live.
    For example, hour **23** means **11:00 PM** on the selected post date.
    """
)

col1, col2, col3, col4 = st.columns(4)

col1.metric("Hourly Baseline Rate", f"{hourly_baseline_rate:,.0f}")
col2.metric(f"Actual Streams ({impact_window_hours}h)", f"{actual_streams:,.0f}")
col3.metric(f"Expected Streams ({impact_window_hours}h)", f"{expected_streams:,.0f}")
col4.metric("Estimated Social Lift", f"{social_lift_streams:,.0f}", f"{lift_percent:,.1f}%")

st.markdown("### Impact Window Summary")

summary_df = pd.DataFrame({
    "Metric": [
        "Expected Baseline",
        "Actual Streams",
        "Estimated Social Lift"
    ],
    "Streams": [
        expected_streams,
        actual_streams,
        social_lift_streams
    ]
})

bar_fig = go.Figure()

bar_fig.add_trace(go.Bar(
    x=summary_df["Metric"],
    y=summary_df["Streams"],
    text=[f"{x:,.0f}" for x in summary_df["Streams"]],
    textposition="outside",
    marker=dict(
        color=[
            "rgba(143, 252, 255, 0.45)",
            "rgba(143, 252, 255, 0.90)",
            "rgba(88, 255, 166, 0.85)"
        ],
        line=dict(
            color="rgba(255,255,255,0.35)",
            width=1
        )
    )
))

bar_fig.update_layout(
    title="Campaign Performance Summary",
    xaxis_title="Metric",
    yaxis_title="Streams",
    template="plotly_dark",
    height=420,
    margin=dict(l=40, r=40, t=70, b=40),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(
        family="Helvetica Neue, Arial, sans-serif",
        color="rgba(255,255,255,0.86)"
    )
)

st.plotly_chart(bar_fig, use_container_width=True)

if data_mode == "Manual demo inputs":
    st.caption(
        f"Manual demo mode active: reach/views set to {manual_social_reach:,.0f} "
        f"with {manual_engagement_rate:.1f}% engagement."
    )
elif data_mode == "CSV upload" and uploaded_csv is not None:
    st.caption("CSV upload mode active: dashboard is using uploaded streaming data.")
elif data_mode == "CSV upload":
    st.caption("CSV upload mode selected, but no file has been uploaded yet. Showing simulated data.")
else:
    st.caption("Auto simulation mode active: values are generated from the model assumptions.")

# -----------------------------
# COMMERCE REVENUE DASHBOARD
# -----------------------------

if commerce_enabled and not product_df.empty:
    st.markdown("### Commerce Revenue Attribution")

    revenue_col1, revenue_col2, revenue_col3, revenue_col4 = st.columns(4)

    revenue_col1.metric(
        "Attributed Product Revenue",
        f"${total_product_gross_revenue:,.0f}"
    )

    revenue_col2.metric(
        "Estimated Net Revenue",
        f"${total_product_net_revenue:,.0f}"
    )

    revenue_col3.metric(
        "Attributed Units Sold",
        f"{total_product_units:,.0f}"
    )

    revenue_col4.metric(
        "Revenue per 1K Social Views",
        f"${revenue_per_1k_social_views:,.2f}"
    )

    commerce_fig = go.Figure()

    commerce_fig.add_trace(go.Bar(
        x=product_df["Product Category"],
        y=product_df["Gross Revenue"],
        name="Gross Revenue",
        text=[f"${x:,.0f}" for x in product_df["Gross Revenue"]],
        textposition="outside",
        marker=dict(
            color="rgba(143, 252, 255, 0.75)",
            line=dict(
                color="rgba(255,255,255,0.35)",
                width=1
            )
        )
    ))

    commerce_fig.add_trace(go.Bar(
        x=product_df["Product Category"],
        y=product_df["Estimated Net Revenue"],
        name="Estimated Net Revenue",
        text=[f"${x:,.0f}" for x in product_df["Estimated Net Revenue"]],
        textposition="outside",
        marker=dict(
            color="rgba(88, 255, 166, 0.75)",
            line=dict(
                color="rgba(255,255,255,0.35)",
                width=1
            )
        )
    ))

    commerce_fig.update_layout(
        title="Attributed Product Revenue by Category",
        xaxis_title="Product Category",
        yaxis_title="Revenue ($)",
        barmode="group",
        template="plotly_dark",
        height=500,
        margin=dict(l=40, r=40, t=80, b=120),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(
            family="Helvetica Neue, Arial, sans-serif",
            color="rgba(255,255,255,0.86)"
        ),
        legend_title="Revenue Type"
    )

    st.plotly_chart(commerce_fig, use_container_width=True)

    display_product_df = product_df.copy()

    currency_columns = [
        "Average Selling Price",
        "Unit Cost / COGS",
        "Gross Revenue",
        "Total COGS",
        "Fees / Discounts",
        "Estimated Net Revenue"
    ]

    for column in currency_columns:
        display_product_df[column] = display_product_df[column].map(
            lambda value: f"${value:,.2f}"
        )

    display_product_df["Estimated Margin (%)"] = display_product_df[
        "Estimated Margin (%)"
    ].map(lambda value: f"{value:,.1f}%")

    st.dataframe(
        display_product_df,
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        f"Commerce model active: estimated ${total_product_gross_revenue:,.0f} "
        f"in attributed gross product revenue and ${total_product_net_revenue:,.0f} "
        f"in estimated net revenue. Revenue per lift stream is approximately "
        f"${revenue_per_lift_stream:,.2f}."
    )
else:
    st.info(
        "Commerce revenue tracking is currently off. Enable it in the sidebar to model merch, physical product, and other campaign-related sales."
    )

# -----------------------------
# CHART
# -----------------------------

fig = go.Figure()

fig.add_trace(go.Scatter(
    x=df["timestamp"],
    y=df["expected_baseline_streams"],
    mode="lines",
    name="Expected Baseline Streams",
    line=dict(width=2),
    hovertemplate="Time: %{x}<br>Expected: %{y:,.0f}<extra></extra>"
))

fig.add_trace(go.Scatter(
    x=df["timestamp"],
    y=df["actual_streams"],
    mode="lines",
    name="Actual Streams",
    line=dict(width=3),
    hovertemplate="Time: %{x}<br>Actual: %{y:,.0f}<extra></extra>"
))

lift_df = df.loc[impact_mask]

fig.add_trace(go.Scatter(
    x=pd.concat([lift_df["timestamp"], lift_df["timestamp"][::-1]]),
    y=pd.concat([lift_df["actual_streams"], lift_df["expected_baseline_streams"][::-1]]),
    fill="toself",
    name="Estimated Social Lift Area",
    opacity=0.25,
    line=dict(width=0),
    hoverinfo="skip"
))

fig.add_vline(
    x=post_timestamp,
    line_width=2,
    line_dash="dash",
    annotation_text="Social Post Goes Live",
    annotation_position="top"
)

fig.add_vrect(
    x0=post_timestamp,
    x1=impact_end,
    fillcolor="gray",
    opacity=0.08,
    line_width=0,
    annotation_text=f"{impact_window_hours}h Impact Window",
    annotation_position="top left"
)

if multi_post:
    fig.add_vline(
        x=second_post_timestamp,
        line_width=2,
        line_dash="dot",
        annotation_text="Second Post",
        annotation_position="top"
    )

fig.update_layout(
    title=f"{song_title} Streaming Trend: Expected vs Actual",
    xaxis_title="Date / Time",
    yaxis_title="Hourly Streams",
    legend_title="Chart Labels",
    hovermode="x unified",
    template="plotly_white",
    height=675,
    margin=dict(l=40, r=40, t=80, b=40)
)

st.plotly_chart(fig, use_container_width=True)

# -----------------------------
# EXPLANATION
# -----------------------------

st.markdown("""
### How to read this dashboard

**Data Source Mode**  
The dashboard can run in two modes:

- **Auto simulation** generates mock hourly streaming data using the sidebar assumptions.
- **Manual demo inputs** lets you type fake campaign numbers directly into the sidebar so the KPIs, lift estimate, and summary bar chart update during a demo.

**Expected Baseline Streams**  
The model’s estimate of how many streams the track would have received without the social post.

**Actual Streams**  
The simulated or manually entered stream count after the social post goes live.

**Estimated Social Lift**  
The difference between actual streams and expected baseline streams.

**Formula**  
Estimated Social Lift = Actual Streams - Expected Baseline Streams

**Impact Window**  
The selected measurement period after the post. A 24-hour window is useful for fast TikTok/Reels/Shorts spikes. A 72-hour or 168-hour window is better for slower campaign effects.

**Impact Window Summary**  
The bar chart compares expected streams, actual streams, and estimated lift so the campaign impact is easy to read at a glance.

**Important note**  
This is a prototype using mock or manually entered demo data. It is designed to show the logic and workflow of a music analytics tool, not to represent real Opus, DSP, or confidential label data.




Conceptualized and designed by Alexander DiFiore, Rhino. Named "lollie" after his two beloved cats, Lily and Ollie.

""")
