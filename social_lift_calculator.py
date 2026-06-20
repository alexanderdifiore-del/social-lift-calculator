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
        color: #00a8b8;
        margin-bottom: 0.1rem;
        text-shadow:
            0 0 6px rgba(0, 168, 184, 0.35),
            0 0 14px rgba(0, 168, 184, 0.22),
            0 0 24px rgba(0, 168, 184, 0.14);
        font-family: "Helvetica Neue", Arial, sans-serif;
    }

    .lollie-subtitle {
        font-size: 0.95rem;
        color: #008a99;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        margin-top: -0.4rem;
        margin-bottom: 2rem;
        font-weight: 700;
        text-shadow:
            0 0 4px rgba(0, 168, 184, 0.18);
    }
    </style>

    <div class="lollie-title">lollie</div>
    <div class="lollie-subtitle">streaming • commerce • video asset intelligence</div>
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
    [
    "TikTok",
    "Instagram Reels",
    "YouTube Shorts",
    "YouTube Video",
    "YouTube Visualizer",
    "YouTube Music Video",
    "YouTube Live Performance"
]
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
st.sidebar.subheader("YouTube Upscale Prioritization")

upscale_priority_enabled = st.sidebar.checkbox(
    "Enable YouTube Upscale Priority Calculator",
    value=True,
    help="Score and rank YouTube videos, visualizers, and live performances for potential upscaling."
)

upscale_data_mode = st.sidebar.radio(
    "Upscale Data Mode",
    [
        "Manual table entry",
        "Upscale CSV upload"
    ],
    help="Manually enter video candidates or upload a CSV of YouTube assets."
)

upscale_candidate_count = 5
upscale_csv_file = None

if upscale_priority_enabled:
    if upscale_data_mode == "Manual table entry":
        upscale_candidate_count = st.sidebar.number_input(
            "Number of Video Candidates",
            min_value=1,
            max_value=25,
            value=5,
            step=1,
            help="How many videos you want to manually score."
        )

    elif upscale_data_mode == "Upscale CSV upload":
        upscale_csv_file = st.sidebar.file_uploader(
            "Upload Upscale Priority CSV",
            type=["csv"],
            key="upscale_csv_file",
            help="Upload a CSV with video title, format, resolution, views, momentum, and priority fields."
        )

        with st.sidebar.expander("Upscale CSV format example"):
            st.code(
                """video_title,isrc,content_format,current_resolution,current_youtube_views,last_28_day_views,engagement_rate,catalog_priority,commercial_upside,asset_readiness,rights_confidence,upscale_difficulty,urgency
Example Music Video,USDEMO000001,YouTube Music Video,480p,12500000,240000,4.8,9,8,7,9,4,8
Example Live Performance,USDEMO000002,YouTube Live Performance,720p,3200000,85000,5.2,7,6,8,8,5,6
Example Visualizer,USDEMO000003,YouTube Visualizer,1080p,950000,18000,3.1,5,5,9,9,2,4""",
                language="csv"
            )
st.sidebar.markdown("---")
st.sidebar.subheader("Commerce / Product Revenue")

commerce_enabled = st.sidebar.checkbox(
    "Enable Commerce Revenue Tracking",
    value=True,
    help="Estimate product revenue associated with the social/streaming impact window."
)

show_commerce_overlay = st.sidebar.checkbox(
    "Show Commerce Overlay on Streaming Chart",
    value=True,
    help="Overlay projected product revenue or product sales onto the streaming trend chart."
)

commerce_overlay_window_days = st.sidebar.selectbox(
    "Commerce Overlay Window",
    [7, 14],
    index=0,
    help="How far after the social post to show projected commerce impact."
)

commerce_overlay_metric = st.sidebar.selectbox(
    "Commerce Overlay Metric",
    [
        "Gross Product Revenue",
        "Estimated Net Revenue",
        "Attributed Units Sold"
    ],
    help="Choose what commerce metric should appear on the streaming trend chart."
)


show_commerce_baseline_line = st.sidebar.checkbox(
    "Show Commerce Baseline Line",
    value=True,
    help="Show an estimated baseline for product revenue or units without the social/streaming spike."
)

expected_commerce_baseline_percent = st.sidebar.slider(
    "Commerce Baseline Share (%)",
    min_value=0.0,
    max_value=100.0,
    value=35.0,
    step=5.0,
    help="Estimate what percentage of the commerce result may have happened without the social/streaming spike."
)
commerce_data_mode = st.sidebar.radio(
    "Commerce Data Mode",
    [
        "Auto estimate from product categories",
        "Manual dated sales entries",
        "Commerce CSV upload"
    ],
    help="Choose whether commerce revenue is estimated, manually entered by date/product, or uploaded from a CSV."
)

product_catalog = {
    "Vinyl LP": {"price": 29.99, "cost": 11.00, "units": 120, "conversion": 0.025, "fees": 8.0},
    "Limited Color Vinyl": {"price": 34.99, "cost": 13.00, "units": 80, "conversion": 0.018, "fees": 8.0},
    "CD": {"price": 14.99, "cost": 4.00, "units": 95, "conversion": 0.015, "fees": 7.0},
    "Cassette": {"price": 12.99, "cost": 3.50, "units": 40, "conversion": 0.008, "fees": 7.0},
    "Deluxe Edition / Box Set": {"price": 89.99, "cost": 35.00, "units": 25, "conversion": 0.004, "fees": 9.0},
    "Signed Physical Product": {"price": 49.99, "cost": 18.00, "units": 35, "conversion": 0.006, "fees": 8.0},
    "Artist Apparel": {"price": 35.00, "cost": 12.00, "units": 150, "conversion": 0.030, "fees": 10.0},
    "Accessories": {"price": 18.00, "cost": 6.00, "units": 100, "conversion": 0.020, "fees": 10.0},
    "Poster / Print": {"price": 25.00, "cost": 7.00, "units": 60, "conversion": 0.012, "fees": 8.0},
    "Merch Bundle": {"price": 65.00, "cost": 25.00, "units": 45, "conversion": 0.007, "fees": 9.0},
    "Digital Album / Download": {"price": 10.99, "cost": 1.00, "units": 75, "conversion": 0.018, "fees": 15.0},
    "Fan Club / Membership": {"price": 9.99, "cost": 1.50, "units": 50, "conversion": 0.010, "fees": 12.0},
    "Ticket / VIP Upsell": {"price": 75.00, "cost": 25.00, "units": 30, "conversion": 0.005, "fees": 10.0}
}

commerce_rows = []

if commerce_enabled:
    if commerce_data_mode == "Auto estimate from product categories":
        revenue_attribution_method = st.sidebar.selectbox(
            "Revenue Attribution Method",
            [
                "Manual attributed units",
                "Estimate from social reach"
            ],
            help="Manual mode lets you type units sold. Estimate mode calculates units from social reach and purchase conversion assumptions."
        )

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

        for index, product_name in enumerate(selected_products):
            defaults = product_catalog[product_name]

            with st.sidebar.expander(product_name, expanded=False):
                average_selling_price = st.number_input(
                    f"{product_name} Avg Selling Price ($)",
                    min_value=0.0,
                    value=float(defaults["price"]),
                    step=1.0,
                    key=f"auto_price_{index}"
                )

                unit_cost = st.number_input(
                    f"{product_name} Unit Cost / COGS ($)",
                    min_value=0.0,
                    value=float(defaults["cost"]),
                    step=1.0,
                    key=f"auto_cost_{index}"
                )

                fee_rate = st.slider(
                    f"{product_name} Fees / Discounts (%)",
                    min_value=0.0,
                    max_value=50.0,
                    value=float(defaults["fees"]),
                    step=0.5,
                    key=f"auto_fees_{index}"
                )

                if revenue_attribution_method == "Manual attributed units":
                    attributed_units = st.number_input(
                        f"{product_name} Attributed Units Sold",
                        min_value=0,
                        value=int(defaults["units"]),
                        step=1,
                        key=f"auto_units_{index}"
                    )
                else:
                    purchase_conversion_rate = st.number_input(
                        f"{product_name} Purchase Conversion Rate (%)",
                        min_value=0.0,
                        max_value=10.0,
                        value=float(defaults["conversion"]),
                        step=0.001,
                        format="%.3f",
                        key=f"auto_conversion_{index}"
                    )

                    attributed_units = int(
                        round(manual_social_reach * (purchase_conversion_rate / 100))
                    )

                    st.caption(f"Estimated units: {attributed_units:,}")

                commerce_rows.append({
                    "Sale Date": post_timestamp.date(),
                    "Product Category": product_name,
                    "Attributed Units": attributed_units,
                    "Average Selling Price": average_selling_price,
                    "Unit Cost / COGS": unit_cost,
                    "Fee Rate (%)": fee_rate,
                    "Source": "Auto estimate"
                })

    elif commerce_data_mode == "Manual dated sales entries":
        manual_commerce_row_count = st.sidebar.number_input(
            "Number of Sales Rows",
            min_value=1,
            max_value=25,
            value=5,
            step=1,
            help="Add dated sales rows by product category."
        )

        for row_index in range(manual_commerce_row_count):
            with st.sidebar.expander(f"Sales Row {row_index + 1}", expanded=row_index == 0):
                sale_date = st.date_input(
                    "Sale Date",
                    value=(post_timestamp + timedelta(days=row_index)).date(),
                    key=f"manual_sale_date_{row_index}"
                )

                product_name = st.selectbox(
                    "Product Category",
                    list(product_catalog.keys()),
                    index=row_index % len(product_catalog),
                    key=f"manual_product_{row_index}"
                )

                defaults = product_catalog[product_name]

                attributed_units = st.number_input(
                    "Units Sold",
                    min_value=0,
                    value=int(defaults["units"] / 4),
                    step=1,
                    key=f"manual_units_{row_index}"
                )

                average_selling_price = st.number_input(
                    "Average Selling Price ($)",
                    min_value=0.0,
                    value=float(defaults["price"]),
                    step=1.0,
                    key=f"manual_price_{row_index}"
                )

                unit_cost = st.number_input(
                    "Unit Cost / COGS ($)",
                    min_value=0.0,
                    value=float(defaults["cost"]),
                    step=1.0,
                    key=f"manual_cost_{row_index}"
                )

                fee_rate = st.slider(
                    "Fees / Discounts (%)",
                    min_value=0.0,
                    max_value=50.0,
                    value=float(defaults["fees"]),
                    step=0.5,
                    key=f"manual_fee_{row_index}"
                )

                commerce_rows.append({
                    "Sale Date": sale_date,
                    "Product Category": product_name,
                    "Attributed Units": attributed_units,
                    "Average Selling Price": average_selling_price,
                    "Unit Cost / COGS": unit_cost,
                    "Fee Rate (%)": fee_rate,
                    "Source": "Manual entry"
                })

    elif commerce_data_mode == "Commerce CSV upload":
        commerce_csv_file = st.sidebar.file_uploader(
            "Upload Commerce CSV",
            type=["csv"],
            key="commerce_csv_file",
            help="Upload a CSV with date, product, units, price, cost, and fee columns."
        )

        with st.sidebar.expander("Commerce CSV format example"):
            st.code(
                """sale_date,product_category,units_sold,average_selling_price,unit_cost,fee_rate
2026-06-17,Vinyl LP,45,29.99,11.00,8
2026-06-18,Artist Apparel,32,35.00,12.00,10
2026-06-19,Deluxe Edition / Box Set,8,89.99,35.00,9""",
                language="csv"
            )

        if commerce_csv_file is not None:
            try:
                commerce_uploaded_df = pd.read_csv(commerce_csv_file)
            except Exception:
                commerce_csv_file.seek(0)
                try:
                    commerce_uploaded_df = pd.read_csv(commerce_csv_file, sep=None, engine="python")
                except Exception:
                    st.sidebar.error("The commerce CSV could not be read. Try exporting again as CSV.")
                    commerce_uploaded_df = pd.DataFrame()

            if not commerce_uploaded_df.empty:
                commerce_uploaded_df.columns = [
                    str(col).strip().replace("\n", " ").replace("\r", " ")
                    for col in commerce_uploaded_df.columns
                ]

                st.sidebar.success("Commerce CSV uploaded.")

                with st.sidebar.expander("Preview Commerce CSV"):
                    st.dataframe(commerce_uploaded_df.head(10), use_container_width=True)
                    st.write(list(commerce_uploaded_df.columns))

                commerce_columns = list(commerce_uploaded_df.columns)
                optional_columns = ["Use default / zero"] + commerce_columns

                sale_date_column = st.sidebar.selectbox(
                    "Select sale date column",
                    commerce_columns,
                    index=0
                )

                product_column = st.sidebar.selectbox(
                    "Select product column",
                    commerce_columns,
                    index=1 if len(commerce_columns) > 1 else 0
                )

                units_column = st.sidebar.selectbox(
                    "Select units sold column",
                    commerce_columns,
                    index=2 if len(commerce_columns) > 2 else 0
                )

                price_column = st.sidebar.selectbox(
                    "Select average selling price column",
                    commerce_columns,
                    index=3 if len(commerce_columns) > 3 else 0
                )

                cost_column = st.sidebar.selectbox(
                    "Select unit cost / COGS column",
                    optional_columns,
                    index=4 if len(optional_columns) > 4 else 0
                )

                fee_column = st.sidebar.selectbox(
                    "Select fee / discount rate column",
                    optional_columns,
                    index=5 if len(optional_columns) > 5 else 0
                )

                working_commerce_df = commerce_uploaded_df.copy()

                for _, row in working_commerce_df.iterrows():
                    product_name = str(row[product_column])

                    sale_date = pd.to_datetime(
                        row[sale_date_column],
                        errors="coerce"
                    )

                    if pd.isna(sale_date):
                        continue

                    attributed_units = pd.to_numeric(
                        row[units_column],
                        errors="coerce"
                    )

                    average_selling_price = pd.to_numeric(
                        row[price_column],
                        errors="coerce"
                    )

                    if pd.isna(attributed_units) or pd.isna(average_selling_price):
                        continue

                    if cost_column != "Use default / zero":
                        unit_cost = pd.to_numeric(row[cost_column], errors="coerce")
                        if pd.isna(unit_cost):
                            unit_cost = 0
                    else:
                        unit_cost = 0

                    if fee_column != "Use default / zero":
                        fee_rate = pd.to_numeric(row[fee_column], errors="coerce")
                        if pd.isna(fee_rate):
                            fee_rate = 0
                    else:
                        fee_rate = 0

                    commerce_rows.append({
                        "Sale Date": sale_date.date(),
                        "Product Category": product_name,
                        "Attributed Units": int(attributed_units),
                        "Average Selling Price": float(average_selling_price),
                        "Unit Cost / COGS": float(unit_cost),
                        "Fee Rate (%)": float(fee_rate),
                        "Source": "CSV upload"
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
    "YouTube Shorts": 1.45,
    "YouTube Video": 1.20,
    "YouTube Visualizer": 1.15,
    "YouTube Music Video": 1.30,
    "YouTube Live Performance": 1.25
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
    product_sales_detail_df = pd.DataFrame(commerce_rows)

    product_sales_detail_df["Sale Date"] = pd.to_datetime(
        product_sales_detail_df["Sale Date"],
        errors="coerce"
    )

    product_sales_detail_df["Attributed Units"] = pd.to_numeric(
        product_sales_detail_df["Attributed Units"],
        errors="coerce"
    ).fillna(0)

    product_sales_detail_df["Average Selling Price"] = pd.to_numeric(
        product_sales_detail_df["Average Selling Price"],
        errors="coerce"
    ).fillna(0)

    product_sales_detail_df["Unit Cost / COGS"] = pd.to_numeric(
        product_sales_detail_df["Unit Cost / COGS"],
        errors="coerce"
    ).fillna(0)

    product_sales_detail_df["Fee Rate (%)"] = pd.to_numeric(
        product_sales_detail_df["Fee Rate (%)"],
        errors="coerce"
    ).fillna(0)

    product_sales_detail_df = product_sales_detail_df.dropna(subset=["Sale Date"])

    product_sales_detail_df["Gross Revenue"] = (
        product_sales_detail_df["Attributed Units"]
        * product_sales_detail_df["Average Selling Price"]
    )

    product_sales_detail_df["Total COGS"] = (
        product_sales_detail_df["Attributed Units"]
        * product_sales_detail_df["Unit Cost / COGS"]
    )

    product_sales_detail_df["Fees / Discounts"] = (
        product_sales_detail_df["Gross Revenue"]
        * (product_sales_detail_df["Fee Rate (%)"] / 100)
    )

    product_sales_detail_df["Estimated Net Revenue"] = (
        product_sales_detail_df["Gross Revenue"]
        - product_sales_detail_df["Total COGS"]
        - product_sales_detail_df["Fees / Discounts"]
    )

    product_sales_detail_df["Estimated Margin (%)"] = np.where(
        product_sales_detail_df["Gross Revenue"] > 0,
        (
            product_sales_detail_df["Estimated Net Revenue"]
            / product_sales_detail_df["Gross Revenue"]
        ) * 100,
        0
    )

    product_df = product_sales_detail_df.groupby("Product Category", as_index=False).agg({
        "Attributed Units": "sum",
        "Average Selling Price": "mean",
        "Unit Cost / COGS": "mean",
        "Fee Rate (%)": "mean",
        "Gross Revenue": "sum",
        "Total COGS": "sum",
        "Fees / Discounts": "sum",
        "Estimated Net Revenue": "sum"
    })

    product_df["Estimated Margin (%)"] = np.where(
        product_df["Gross Revenue"] > 0,
        (product_df["Estimated Net Revenue"] / product_df["Gross Revenue"]) * 100,
        0
    )

    product_daily_df = product_sales_detail_df.groupby("Sale Date", as_index=False).agg({
        "Attributed Units": "sum",
        "Gross Revenue": "sum",
        "Estimated Net Revenue": "sum"
    })

    product_daily_df = product_daily_df.rename(columns={"Sale Date": "timestamp"})

    total_product_units = product_sales_detail_df["Attributed Units"].sum()
    total_product_gross_revenue = product_sales_detail_df["Gross Revenue"].sum()
    total_product_net_revenue = product_sales_detail_df["Estimated Net Revenue"].sum()

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
    product_sales_detail_df = pd.DataFrame()
    product_df = pd.DataFrame()
    product_daily_df = pd.DataFrame()
    total_product_units = 0
    total_product_gross_revenue = 0
    total_product_net_revenue = 0
    revenue_per_1k_social_views = 0
    revenue_per_lift_stream = 0
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
    if not product_sales_detail_df.empty:
        st.markdown("#### Dated Product Sales Detail")

        display_detail_df = product_sales_detail_df.copy()

        display_detail_df["Sale Date"] = display_detail_df["Sale Date"].dt.strftime("%Y-%m-%d")

        detail_currency_columns = [
            "Average Selling Price",
            "Unit Cost / COGS",
            "Gross Revenue",
            "Total COGS",
            "Fees / Discounts",
            "Estimated Net Revenue"
        ]

        for column in detail_currency_columns:
            display_detail_df[column] = display_detail_df[column].map(
                lambda value: f"${value:,.2f}"
            )

        display_detail_df["Estimated Margin (%)"] = display_detail_df[
            "Estimated Margin (%)"
        ].map(lambda value: f"{value:,.1f}%")

        st.dataframe(
            display_detail_df,
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
# YOUTUBE UPSCALE PRIORITY CALCULATOR
# -----------------------------

if upscale_priority_enabled:
    st.markdown("### YouTube Upscale Priority Calculator")

    st.caption(
        "Rank YouTube videos, visualizers, live performances, and other video assets "
        "based on demand, catalog importance, commercial upside, asset readiness, "
        "rights confidence, and technical need for upscaling."
    )

    upscale_columns = [
        "Video Title",
        "ISRC",
        "Content Format",
        "Current Max Resolution",
        "Current YouTube Views",
        "Last 28 Day Views",
        "Engagement Rate (%)",
        "Catalog Priority (1-10)",
        "Commercial Upside (1-10)",
        "Asset Readiness (1-10)",
        "Rights Confidence (1-10)",
        "Upscale Difficulty (1-10)",
        "Urgency / Deadline (1-10)"
    ]

    content_format_options = [
        "YouTube Music Video",
        "YouTube Live Performance",
        "YouTube Visualizer",
        "YouTube Video",
        "YouTube Shorts",
        "Lyric Video",
        "TV Performance",
        "Interview / EPK",
        "Documentary Clip",
        "Other"
    ]

    resolution_options = [
        "240p",
        "360p",
        "480p",
        "720p",
        "1080p",
        "1440p",
        "2160p / 4K"
    ]

    if upscale_data_mode == "Manual table entry":
        default_upscale_rows = []

        for row_index in range(int(upscale_candidate_count)):
            default_upscale_rows.append({
                "Video Title": f"Video Candidate {row_index + 1}",
                "ISRC": f"USDEMO{row_index + 1:06d}",
                "Content Format": content_format_options[row_index % len(content_format_options)],
                "Current Max Resolution": "480p" if row_index == 0 else "720p",
                "Current YouTube Views": 1000000 * (row_index + 1),
                "Last 28 Day Views": 50000 * (row_index + 1),
                "Engagement Rate (%)": 4.0,
                "Catalog Priority (1-10)": 7,
                "Commercial Upside (1-10)": 6,
                "Asset Readiness (1-10)": 7,
                "Rights Confidence (1-10)": 8,
                "Upscale Difficulty (1-10)": 4,
                "Urgency / Deadline (1-10)": 5
            })

        upscale_input_df = pd.DataFrame(default_upscale_rows)

    else:
        if upscale_csv_file is not None:
            try:
                upscale_input_df = pd.read_csv(upscale_csv_file)
            except Exception:
                upscale_csv_file.seek(0)
                try:
                    upscale_input_df = pd.read_csv(
                        upscale_csv_file,
                        sep=None,
                        engine="python"
                    )
                except Exception:
                    st.error("The upscale CSV could not be read. Try exporting it again as a clean CSV.")
                    upscale_input_df = pd.DataFrame()
        else:
            upscale_input_df = pd.DataFrame(columns=upscale_columns)

        if not upscale_input_df.empty:
            upscale_input_df.columns = [
                str(col).strip().lower().replace(" ", "_")
                for col in upscale_input_df.columns
            ]

            upscale_column_aliases = {
                "video_title": "Video Title",
                "title": "Video Title",
                "isrc": "ISRC",
                "isrc_code": "ISRC",
                "content_format": "Content Format",
                "format": "Content Format",
                "current_resolution": "Current Max Resolution",
                "resolution": "Current Max Resolution",
                "current_max_resolution": "Current Max Resolution",
                "current_youtube_views": "Current YouTube Views",
                "youtube_views": "Current YouTube Views",
                "views": "Current YouTube Views",
                "last_28_day_views": "Last 28 Day Views",
                "recent_views": "Last 28 Day Views",
                "engagement_rate": "Engagement Rate (%)",
                "engagement_rate_%": "Engagement Rate (%)",
                "catalog_priority": "Catalog Priority (1-10)",
                "commercial_upside": "Commercial Upside (1-10)",
                "asset_readiness": "Asset Readiness (1-10)",
                "rights_confidence": "Rights Confidence (1-10)",
                "upscale_difficulty": "Upscale Difficulty (1-10)",
                "urgency": "Urgency / Deadline (1-10)",
                "urgency_deadline": "Urgency / Deadline (1-10)"
            }

            upscale_input_df = upscale_input_df.rename(
                columns={
                    col: upscale_column_aliases.get(col, col)
                    for col in upscale_input_df.columns
                }
            )

        for column in upscale_columns:
            if column not in upscale_input_df.columns:
                if column == "Video Title":
                    upscale_input_df[column] = "Untitled Video"
                elif column == "ISRC":
                    upscale_input_df[column] = ""
                elif column == "Content Format":
                    upscale_input_df[column] = "YouTube Music Video"
                elif column == "Current Max Resolution":
                    upscale_input_df[column] = "720p"
                elif column in [
                    "Catalog Priority (1-10)",
                    "Commercial Upside (1-10)",
                    "Asset Readiness (1-10)",
                    "Rights Confidence (1-10)",
                    "Upscale Difficulty (1-10)",
                    "Urgency / Deadline (1-10)"
                ]:
                    upscale_input_df[column] = 5
                else:
                    upscale_input_df[column] = 0

    st.markdown("#### Video Candidate Inputs")

    edited_upscale_df = st.data_editor(
        upscale_input_df,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "Video Title": st.column_config.TextColumn(
                "Video Title",
                help="Name of the YouTube video, performance, visualizer, or asset."
            ),
            "ISRC": st.column_config.TextColumn(
                "ISRC",
                help="International Standard Recording Code tied to the audio recording."
            ),
            "Content Format": st.column_config.SelectboxColumn(
                "Content Format",
                options=content_format_options
            ),
            "Current Max Resolution": st.column_config.SelectboxColumn(
                "Current Max Resolution",
                options=resolution_options
            ),
            "Current YouTube Views": st.column_config.NumberColumn(
                "Current YouTube Views",
                min_value=0,
                step=1000
            ),
            "Last 28 Day Views": st.column_config.NumberColumn(
                "Last 28 Day Views",
                min_value=0,
                step=1000
            ),
            "Engagement Rate (%)": st.column_config.NumberColumn(
                "Engagement Rate (%)",
                min_value=0.0,
                max_value=100.0,
                step=0.1
            ),
            "Catalog Priority (1-10)": st.column_config.NumberColumn(
                "Catalog Priority (1-10)",
                min_value=1,
                max_value=10,
                step=1
            ),
            "Commercial Upside (1-10)": st.column_config.NumberColumn(
                "Commercial Upside (1-10)",
                min_value=1,
                max_value=10,
                step=1
            ),
            "Asset Readiness (1-10)": st.column_config.NumberColumn(
                "Asset Readiness (1-10)",
                min_value=1,
                max_value=10,
                step=1
            ),
            "Rights Confidence (1-10)": st.column_config.NumberColumn(
                "Rights Confidence (1-10)",
                min_value=1,
                max_value=10,
                step=1
            ),
            "Upscale Difficulty (1-10)": st.column_config.NumberColumn(
                "Upscale Difficulty (1-10)",
                min_value=1,
                max_value=10,
                step=1,
                help="Higher means more technically difficult."
            ),
            "Urgency / Deadline (1-10)": st.column_config.NumberColumn(
                "Urgency / Deadline (1-10)",
                min_value=1,
                max_value=10,
                step=1
            )
        }
    )

    score_df = edited_upscale_df.copy()

    numeric_upscale_columns = [
        "Current YouTube Views",
        "Last 28 Day Views",
        "Engagement Rate (%)",
        "Catalog Priority (1-10)",
        "Commercial Upside (1-10)",
        "Asset Readiness (1-10)",
        "Rights Confidence (1-10)",
        "Upscale Difficulty (1-10)",
        "Urgency / Deadline (1-10)"
    ]

    for column in numeric_upscale_columns:
        score_df[column] = pd.to_numeric(score_df[column], errors="coerce").fillna(0)

    def resolution_quality_gap_score(resolution):
        resolution_text = str(resolution).lower()

        if "2160" in resolution_text or "4k" in resolution_text:
            return 0
        elif "1440" in resolution_text:
            return 10
        elif "1080" in resolution_text:
            return 20
        elif "720" in resolution_text:
            return 50
        elif "480" in resolution_text:
            return 75
        elif "360" in resolution_text:
            return 90
        elif "240" in resolution_text:
            return 100
        else:
            return 50

    score_df["Quality Gap Score"] = score_df["Current Max Resolution"].apply(
        resolution_quality_gap_score
    )

    score_df["Lifetime Demand Score"] = np.minimum(
        np.log10(score_df["Current YouTube Views"] + 1) / 7 * 100,
        100
    )

    score_df["Recent Momentum Score"] = np.minimum(
        np.log10(score_df["Last 28 Day Views"] + 1) / 5 * 100,
        100
    )

    score_df["Engagement Score"] = np.minimum(
        score_df["Engagement Rate (%)"] / 8 * 100,
        100
    )

    score_df["Catalog Priority Score"] = score_df["Catalog Priority (1-10)"] * 10
    score_df["Commercial Upside Score"] = score_df["Commercial Upside (1-10)"] * 10

    score_df["Readiness Score"] = (
        (
            score_df["Asset Readiness (1-10)"]
            + score_df["Rights Confidence (1-10)"]
        )
        / 2
        * 10
    )

    score_df["Ease Score"] = (11 - score_df["Upscale Difficulty (1-10)"]) * 10
    score_df["Urgency Score"] = score_df["Urgency / Deadline (1-10)"] * 10

    score_df["Upscale Priority Score"] = (
        score_df["Quality Gap Score"] * 0.18
        + score_df["Lifetime Demand Score"] * 0.15
        + score_df["Recent Momentum Score"] * 0.15
        + score_df["Engagement Score"] * 0.08
        + score_df["Catalog Priority Score"] * 0.14
        + score_df["Commercial Upside Score"] * 0.12
        + score_df["Readiness Score"] * 0.10
        + score_df["Ease Score"] * 0.05
        + score_df["Urgency Score"] * 0.03
    )

    def upscale_priority_tier(score):
        if score >= 80:
            return "Immediate Priority"
        elif score >= 65:
            return "High Priority"
        elif score >= 50:
            return "Medium Priority"
        else:
            return "Low Priority"

    def upscale_rationale(row):
        reasons = []

        if row["Quality Gap Score"] >= 75:
            reasons.append("large quality gap")
        if row["Recent Momentum Score"] >= 70:
            reasons.append("strong recent momentum")
        if row["Catalog Priority (1-10)"] >= 8:
            reasons.append("high catalog priority")
        if row["Commercial Upside (1-10)"] >= 8:
            reasons.append("strong commercial upside")
        if row["Asset Readiness (1-10)"] <= 4:
            reasons.append("asset readiness review needed")
        if row["Rights Confidence (1-10)"] <= 4:
            reasons.append("rights/clearance review needed")
        if row["Upscale Difficulty (1-10)"] >= 8:
            reasons.append("technically difficult upscale")

        if len(reasons) == 0:
            return "balanced candidate"

        return "; ".join(reasons)

    score_df["Priority Tier"] = score_df["Upscale Priority Score"].apply(
        upscale_priority_tier
    )

    score_df["Priority Rationale"] = score_df.apply(upscale_rationale, axis=1)

    ranked_upscale_df = score_df.sort_values(
        "Upscale Priority Score",
        ascending=False
    ).reset_index(drop=True)

    ranked_upscale_df.insert(
        0,
        "Rank",
        range(1, len(ranked_upscale_df) + 1)
    )

    st.markdown("#### Upscale Priority Ranking")

    top_upscale_df = ranked_upscale_df.head(10)

    if not top_upscale_df.empty:
        upscale_fig = go.Figure()

        upscale_fig.add_trace(go.Bar(
            x=top_upscale_df["Upscale Priority Score"],
            y=top_upscale_df["Video Title"],
            orientation="h",
            text=[
                f"{score:,.1f}"
                for score in top_upscale_df["Upscale Priority Score"]
            ],
            textposition="outside",
            hovertemplate=(
                "Video: %{y}<br>"
                "Priority Score: %{x:,.1f}<extra></extra>"
            )
        ))

        upscale_fig.update_layout(
            title="Top YouTube Upscale Candidates",
            xaxis_title="Upscale Priority Score",
            yaxis_title="Video Asset",
            template="plotly_white",
            height=450,
            margin=dict(l=40, r=40, t=80, b=40),
            yaxis=dict(autorange="reversed")
        )

        st.plotly_chart(upscale_fig, use_container_width=True)

    display_upscale_df = ranked_upscale_df[[
        "Rank",
        "Video Title",
        "ISRC",
        "Content Format",
        "Current Max Resolution",
        "Current YouTube Views",
        "Last 28 Day Views",
        "Upscale Priority Score",
        "Priority Tier",
        "Priority Rationale"
    ]].copy()

    display_upscale_df["Upscale Priority Score"] = display_upscale_df[
        "Upscale Priority Score"
    ].map(lambda value: f"{value:,.1f}")

    st.dataframe(
        display_upscale_df,
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        "Priority Score is directional and intended for planning. It combines technical need, "
        "audience demand, recent momentum, catalog importance, commercial upside, readiness, "
        "rights confidence, difficulty, and urgency."
    )# -----------------------------
# CHART
# -----------------------------
# Commerce overlay projection for the streaming trend chart
commerce_overlay_df = pd.DataFrame()
commerce_overlay_label = ""
commerce_overlay_axis_title = ""
commerce_overlay_hover_prefix = ""
commerce_overlay_hover_suffix = ""

if (
    commerce_enabled
    and show_commerce_overlay
    and not product_df.empty
):
    if commerce_overlay_metric == "Gross Product Revenue":
        commerce_overlay_total_value = total_product_gross_revenue
        commerce_overlay_label = "Projected Gross Product Revenue"
        commerce_overlay_axis_title = "Product Revenue ($)"
        commerce_overlay_hover_prefix = "$"
        commerce_value_column = "Gross Revenue"

    elif commerce_overlay_metric == "Estimated Net Revenue":
        commerce_overlay_total_value = total_product_net_revenue
        commerce_overlay_label = "Projected Net Product Revenue"
        commerce_overlay_axis_title = "Product Revenue ($)"
        commerce_overlay_hover_prefix = "$"
        commerce_value_column = "Estimated Net Revenue"

    else:
        commerce_overlay_total_value = total_product_units
        commerce_overlay_label = "Projected Attributed Units Sold"
        commerce_overlay_axis_title = "Attributed Product Units"
        commerce_overlay_hover_suffix = " units"
        commerce_value_column = "Attributed Units"

    if not product_daily_df.empty:
        overlay_start = post_timestamp
        overlay_end = post_timestamp + timedelta(days=commerce_overlay_window_days)

        commerce_overlay_df = product_daily_df.copy()
        commerce_overlay_df["timestamp"] = pd.to_datetime(
            commerce_overlay_df["timestamp"],
            errors="coerce"
        )

        commerce_overlay_df = commerce_overlay_df[
            (commerce_overlay_df["timestamp"] >= overlay_start)
            &
            (commerce_overlay_df["timestamp"] < overlay_end)
        ]

        commerce_overlay_df = commerce_overlay_df.sort_values("timestamp")


        # Add a starting point so commerce lines begin at the same left edge as the streaming chart.
        chart_start_time = df["timestamp"].min()

        if not commerce_overlay_df.empty:
            starting_row = pd.DataFrame({
                "timestamp": [chart_start_time],
                "Attributed Units": [0],
                "Gross Revenue": [0],
                "Estimated Net Revenue": [0]
            })

            commerce_overlay_df = pd.concat(
                [starting_row, commerce_overlay_df],
                ignore_index=True
            )

            commerce_overlay_df = commerce_overlay_df.sort_values("timestamp")

        if not commerce_overlay_df.empty:
            commerce_overlay_df["commerce_value"] = commerce_overlay_df[commerce_value_column]
            commerce_overlay_df["cumulative_commerce_value"] = commerce_overlay_df[
                "commerce_value"
            ].cumsum()

        if not commerce_overlay_df.empty:
            commerce_overlay_df["commerce_value"] = commerce_overlay_df[commerce_value_column]
            commerce_overlay_df["cumulative_commerce_value"] = commerce_overlay_df[
                "commerce_value"
            ].cumsum()

    if commerce_overlay_df.empty and commerce_overlay_total_value > 0:
        commerce_overlay_dates = [
            post_timestamp + timedelta(days=day)
            for day in range(commerce_overlay_window_days)
        ]

        commerce_decay_weights = np.exp(
            -np.linspace(0, 2.4, commerce_overlay_window_days)
        )

        commerce_decay_weights = commerce_decay_weights / commerce_decay_weights.sum()

        commerce_overlay_values = commerce_overlay_total_value * commerce_decay_weights

        commerce_overlay_df = pd.DataFrame({
            "timestamp": commerce_overlay_dates,
            "commerce_value": commerce_overlay_values,
            "cumulative_commerce_value": np.cumsum(commerce_overlay_values)
        })
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
if not commerce_overlay_df.empty:
    if show_commerce_baseline_line:
        fig.add_trace(go.Scatter(
            x=commerce_overlay_df["timestamp"],
            y=commerce_overlay_df["cumulative_commerce_value"] * (
                expected_commerce_baseline_percent / 100
            ),
            mode="lines",
            name="Expected Product Revenue Baseline",
            yaxis="y2",
            line=dict(width=2, dash="dash"),
            hovertemplate=(
                "Date: %{x}<br>"
                "Expected Commerce Baseline: "
                + commerce_overlay_hover_prefix
                + "%{y:,.0f}"
                + commerce_overlay_hover_suffix
                + "<extra></extra>"
            )
        ))

    fig.add_trace(go.Scatter(
        x=commerce_overlay_df["timestamp"],
        y=commerce_overlay_df["cumulative_commerce_value"],
        mode="lines+markers",
        name="Attributed Product Revenue",
        yaxis="y2",
        line=dict(width=3),
        hovertemplate=(
            "Date: %{x}<br>"
            + commerce_overlay_label
            + ": "
            + commerce_overlay_hover_prefix
            + "%{y:,.0f}"
            + commerce_overlay_hover_suffix
            + "<extra></extra>"
        )
    ))
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
            yaxis2=dict(
            title=commerce_overlay_axis_title,
            overlaying="y",
            side="right",
            showgrid=False
        ) if not commerce_overlay_df.empty else None,
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
The streaming lift section can run in three modes:

* **Auto simulation** generates mock hourly streaming data using the sidebar assumptions.
* **Manual demo inputs** lets you type campaign numbers directly into the sidebar so the KPIs, lift estimate, and summary bar chart update during a demo.
* **CSV upload** lets you upload spreadsheet-style streaming data and map the timestamp, actual streams, and expected baseline columns.

**Expected Baseline Streams**
The model’s estimate of how many streams the track would have received without the selected social, video, or campaign event.

**Actual Streams**
The simulated, manually entered, or uploaded stream count after the selected social/video event goes live.

**Estimated Social Lift**
The difference between actual streams and expected baseline streams during the selected impact window.

**Formula**
Estimated Social Lift = Actual Streams - Expected Baseline Streams

**Impact Window**
The selected measurement period after the post or video event. A 24-hour window is useful for fast TikTok/Reels/Shorts spikes. A 72-hour or 168-hour window is better for slower campaign effects, catalog activity, YouTube videos, music videos, visualizers, and live performances.

**Impact Window Summary**
The summary chart compares expected streams, actual streams, and estimated lift so the campaign impact is easy to read at a glance.

**Commerce Revenue Attribution**
The commerce section estimates product revenue that may be associated with the social and streaming impact window. Product categories can include vinyl, CDs, cassettes, deluxe editions, box sets, signed products, apparel, accessories, posters, merch bundles, digital downloads, fan memberships, and ticket or VIP upsells.

Commerce revenue can be modeled through auto-estimated product categories, manual dated sales entries, or commerce CSV upload. The model calculates attributed units sold, gross product revenue, estimated net revenue, revenue per 1,000 social views, and revenue per lift stream.

**Commerce Overlay**
When enabled, the chart can overlay attributed product revenue or product units on top of the streaming trend. The commerce line uses a separate right-side axis because streams and revenue are different measurements.

**YouTube Upscale Priority Calculator**
The YouTube upscale section helps prioritize which video assets should be considered first for upscaling. It can score music videos, visualizers, live performances, Shorts, lyric videos, TV performances, interviews, EPK clips, documentary clips, and other video assets.

The calculator ranks candidates using a weighted priority model. It considers:

* **Current resolution / quality gap:** Lower-resolution videos receive a higher need score because they have more room for improvement.
* **Lifetime YouTube views:** Videos with stronger long-term demand are treated as higher-value catalog assets.
* **Recent 28-day views:** Videos with current momentum are prioritized because an upscale may have more immediate impact.
* **Engagement rate:** Higher engagement can suggest stronger fan interest beyond passive viewing.
* **Catalog priority:** Manually reflects how important the artist, track, era, or campaign is to the broader catalog strategy.
* **Commercial upside:** Estimates how much the asset may support streaming, commerce, sync, playlisting, anniversary campaigns, or other revenue opportunities.
* **Asset readiness:** Measures whether usable source files, masters, metadata, and supporting materials are available.
* **Rights confidence:** Helps flag whether the video is clear enough to move forward without major rights or clearance concerns.
* **Upscale difficulty:** Accounts for how technically difficult the upscale may be. Easier upscales are more efficient to prioritize.
* **Urgency / deadline:** Gives extra weight to assets tied to a campaign, anniversary, artist moment, release cycle, or internal deadline.

The final **Upscale Priority Score** combines these inputs into a ranked list. Higher scores indicate stronger candidates for near-term upscaling. The priority tier is meant to support triage and planning, not replace human review, creative judgment, rights review, or technical assessment.

**Important note**
This is a prototype using mock, manually entered, or uploaded demo data. It is designed to show the logic and workflow of a music analytics tool, not to represent real Opus, DSP, YouTube, D2C, retail, financial, or confidential label data unless connected to approved internal systems.

Conceptualized and designed by Alexander DiFiore, Rhino. Named "lollie" after his two beloved cats, Lily and Ollie.
""")

