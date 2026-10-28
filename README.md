# lollie: paid media and streaming intelligence

Lollie is a small Streamlit prototype that answers one question:

> When we run paid media campaigns, what happens to the streaming performance of the music we are promoting?

It lines up an advertising report (WAVO or similar) with a streaming report (Opus or similar) and shows, for one campaign:
paid media performance, streams before / during / after the campaign against an expected baseline, a country-by-country
comparison, and a short factual summary.

It is **observational**. It describes *observed streaming change versus baseline*; it never claims the advertising caused it.

> **Prototype safeguards.** Lollie makes no connection to company APIs or systems, and files you upload stay in the running app
> session. Do not upload confidential reports to an environment that has not been approved, and do not deploy this app
> publicly. Any production use needs company approval and technical / security review. The included data is synthetic.

## Run it

```bash
pip install -r requirements.txt
streamlit run app.py
```

Open the address Streamlit prints (usually http://localhost:8501).

## Try it with practice files

Synthetic practice files are in `sample_data/`:

| File | Upload it as |
| --- | --- |
| `sample_wavo_paid_media.csv` | 1 · Paid media report |
| `sample_streaming_daily.csv` or `.xlsx` | 2 · Streaming report |
| `sample_playlist_track_list.csv` | 3 · Track list (only for the "Summer Playlist push" campaign) |

Or switch on **Demo mode** (sidebar, *Advanced / Demo*) to see the same data without uploading anything. Demo mode is clearly
labelled and never mixed with real data. Regenerate the files with `python -m lollie.demo sample_data`.

## Using your own files

1. **Upload one paid media report** in the sidebar (CSV or Excel). Open *Import settings* under the page title to check how
   columns were matched. Only Spend is required; campaign, date, country and platform make it useful.
2. **Upload one streaming report.** Only Date and Streams are required; track or ISRC, country and DSP make it useful.
3. In **Campaign Overview**, pick the artist, campaign, platform, countries and DSP, then say what was promoted: a single song,
   a playlist / several songs, or the catalog.
4. Read sections **B** (paid media), **C** (streaming vs expected), **D** (countries) and **E** (summary). The summary can be
   downloaded as text.

Details: [`docs/data_requirements.md`](docs/data_requirements.md), [`docs/methodology.md`](docs/methodology.md),
[`docs/limitations_and_questions.md`](docs/limitations_and_questions.md).

## What is on the page

| Section | What it shows |
| --- | --- |
| A · Campaign Overview | Artist, campaign, platform, country, DSP and date filters; promoted song or playlist; campaign start / end |
| B · Paid Media Performance | Spend, impressions, views, engagements, clicks, landing page views, CPM, CPC, budget, results and goal attainment by result type, by-country table |
| C · Streaming Intelligence | Actual vs expected streams, 7-day trend, campaign start / end markers, ad spend on a shared date axis, optional organic social post markers, before / during / after figures |
| D · Market Comparison | Ad spend, landing page views and streaming change by country, with low-paid countries shown for reference only |
| E · Campaign Summary | Plain factual summary with data limitations, plus comparison with other campaigns |

The original Lollie look (teal branding, white background, simple sidebar, large KPIs, interactive Plotly expected-versus-actual
chart, impact window and social post markers, artist / track information) is kept.

## Project layout

```
app.py, social_lift_calculator.py   the Streamlit page (app.py is a launcher)
lollie/
  paid/       advertising report import, metrics, daily series
  streams/    streaming report import, track and playlist matching
  analysis/   baseline, pre / during / post, countries, overlaps, timing
  ui/         charts and section helpers
  summary.py  factual campaign summary
  geo.py      country matching
  demo.py     synthetic demo data and sample files
tests/        automated tests (python -m pytest)
docs/         data requirements, methodology, limitations and open questions
sample_data/  synthetic practice files
archive/      V1 features set aside (see archive/README.md); not imported, tested or maintained
```

## What changed from V1

Removed from the app and moved to `archive/`: e-commerce revenue tracking, ad credits and funding, hypothetical streaming
simulators (artist tier, intensity score, lift multipliers), Scenario Lab, audience / creative ranking and the V1 dashboard.
YouTube video upscaling was removed earlier and is only in git history. YouTube **advertising** can still be imported like any
other platform.

## Tests

```bash
python -m pytest
```

Tests use synthetic data only.
