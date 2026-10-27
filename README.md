# lollie

A music analytics dashboard built with Streamlit and Plotly. Lollie follows one flow on one page:

**Paid advertising + organic social  ->  streaming performance  ->  commerce revenue**

## What is on the page

| Section | What it shows |
| --- | --- |
| **A. Campaign Overview** | Artist, song, campaign ID, ISRC, release phase, platform, market, DSP focus, and headline paid / streaming / commerce numbers. Data-quality checks appear here. |
| **B. Paid Media Performance** | Impressions, views, engagements, clicks, spend, budget, pacing, CPM, CPC, CTR, results by type, and a campaign-by-market table with goal status (Ahead of goal, On track, At risk, Forecast unavailable). |
| **C. Streaming Impact Analysis** | The original lollie view: baseline rate, actual vs expected streams, estimated social lift, impact window summary, and the interactive expected-vs-actual chart. Paid flights, daily spend, extra organic posts and commerce can be overlaid. |
| **D. Audience & Creative Performance** | Most cost-effective and most engaging audience and creative, using only compatible metrics. |
| **E. Commerce Revenue** | Revenue, net revenue, units, revenue per 1K social views, category charts and tables, dated sales detail. |
| **F. Ad Credits & Funding** | A compact, collapsed summary of in-kind partner funding, billing credits and prepaid funds, with advanced tools behind a switch. |

An optional **Campaign recap** at the bottom writes a short, factual summary from the numbers on the page.

## Real data first

Production mode is the default and only uses data you upload or type in.

* **Streaming:** CSV or Excel, hourly or daily, with column mapping. Daily data is never turned into hourly data.
* **Paid media:** CSV or Excel exports from Meta, TikTok, Google Ads / YouTube, Snapchat and WAVO, with column mapping, validation and duplicate protection.
* **Commerce:** CSV or Excel sales files, or dated sales typed into the sidebar.

Simulated data lives only behind **Advanced / Demo** at the bottom of the sidebar. Turning Demo mode on shows a banner and uses separate synthetic data; turning it off removes all of it.

Lift is an observational, modeled estimate (actual streams minus an expected baseline). It never claims that a post or an ad caused the change.

## Safety

* Nothing is uploaded to outside services and the app is not deployed anywhere by this repository.
* Ad credits are never redeemed automatically, billing pages are not scraped, and no billing API is assumed.
* Amounts in different currencies or units are never added together.

## Running the app

```bash
pip install -r requirements.txt
streamlit run app.py
```

`streamlit run social_lift_calculator.py` opens the same dashboard.

## Tests

```bash
pytest
```

Tests cover streaming baselines and lift, commerce calculations, paid media metrics, budget pacing, goal forecasting, cross-platform imports, credits, and the dashboard itself.

## Project layout

* `social_lift_calculator.py` - the dashboard page.
* `app.py` - launcher for the same page.
* `lollie/streaming.py`, `lollie/commerce.py` - original streaming and commerce math.
* `lollie/paid/` - paid media import, metrics, audience and creative ranking, recap.
* `lollie/ui/` - Streamlit pieces (charts, imports, credits section).
* `lollie/credits/`, `lollie/db/` - ad credits and funding (local SQLite file in `data/`).

Conceptualized and designed by Alexander DiFiore, Rhino. Named "lollie" after his two beloved cats, Lily and Ollie.
