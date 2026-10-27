# Social Media Streaming Lift Calculator (lollie)

A prototype music analytics dashboard built with Streamlit and Plotly.

**lollie v2** adds a multipage paid media intelligence workspace (`app.py`) plus a shared `lollie/` Python package. The original full dashboard remains in `social_lift_calculator.py`.

The **Ad Credits & Funding** module tracks **partner-funded ad credit allocations** (Global Catalog style: TikTok quarterly budgets, YouTube gratis impressions, Spotify monthly slots, Snap match, Meta promotional fund) via SQLite-backed programs, project requests, allocations, and reported utilization. A legacy tab covers **billing-level promotional credits** that reduce invoiced ad spend, with CSV/Excel imports and audit history.

This tool simulates the impact of social media activity on streaming performance by comparing expected baseline streams against actual streams after a social media event.

## Features

* Artist and song inputs
* Simulated hourly streaming data
* Natural daily streaming patterns
* TikTok, Instagram Reels, and YouTube Shorts modeling
* Social lift estimation
* Interactive Plotly visualizations
* Campaign impact window analysis

## Example Use Case

An artist posts a TikTok at 6 PM.

The dashboard estimates:

* Expected streams without the post
* Actual streams after the post
* Incremental streams attributable to social activity
* Overall campaign lift percentage

## Running the apps

Multipage paid media v2 dashboard:

```bash
pip install -r requirements.txt
streamlit run app.py
```

Classic single-page social lift calculator (commerce, upscale scoring, CSV uploads):

```bash
streamlit run social_lift_calculator.py
```

## Tests

```bash
pytest
```

## Technology

* Python
* Streamlit
* Pandas
* NumPy
* Plotly
* pytest

## Future Enhancements

* Spotify CSV uploads
* Apple Music analytics integration
* Multi-platform attribution modeling
* Campaign ROI analysis
* Executive PDF reporting

## Disclaimer

This project uses simulated data and is intended as a prototype analytics concept.
