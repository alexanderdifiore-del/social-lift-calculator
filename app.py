"""Lollie v2 multipage dashboard entrypoint."""

import streamlit as st

from lollie.branding import render_lollie_header

st.set_page_config(
    page_title="lollie",
    page_icon="🍭",
    layout="wide",
    initial_sidebar_state="expanded",
)

render_lollie_header("paid media intelligence • streaming • commerce")

st.markdown(
    """
Welcome to **lollie v2** — a multipage workspace for paid media planning,
streaming lift analysis, and commerce-aware campaign intelligence.

Use the sidebar to open a page:

| Page | Purpose |
| --- | --- |
| **Paid Media Intelligence** | Budget mix, CPM assumptions, and incremental stream forecasts |
| **Scenario Lab** | Compare spend levels and intensity scores side by side |
| **Ad Credits & Funding** | Promotional credit inventory, imports, reconciliation, and net cost analysis |

### Classic social lift calculator

The original full-featured dashboard (commerce overlay, YouTube upscale scoring,
CSV uploads) remains available as a standalone app:

```bash
streamlit run social_lift_calculator.py
```

Run `streamlit run app.py` for this multipage experience.
"""
)

col1, col2, col3 = st.columns(3)
col1.metric("Surfaces", "2 planner pages + classic app")
col2.metric("Package", "lollie v2")
col3.metric("Model alignment", "Shared platform multipliers")
