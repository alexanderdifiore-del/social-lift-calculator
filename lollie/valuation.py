"""Optional "Estimated Streaming Value Change".

A deliberately small, separate calculation::

    Estimated Streaming Value Change = Observed Streaming Change x assumed value per stream

The assumed value (default $0.004 USD per Spotify stream) is an illustrative planning figure
that the user can edit or switch off. It is never used to work out expected streams, so the
baseline is the same whether the estimate is on or off.

It is not WMG revenue, royalty income, profit or advertising ROI. Spotify has no universal
fixed per-stream royalty, the rate applies to Spotify streams only (it is not carried over to
other services), and the observed change is not shown to have been caused by advertising. A
negative result is a lower-than-baseline estimate, not a verified financial loss.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

DEFAULT_RATE_USD = 0.004
RATE_DSP = "Spotify"
LABEL = "Estimated Streaming Value Change"
NOT_CALCULATED = "Not calculated"

TOOLTIP = (
    "Observed Streaming Change x an assumed value per stream (default $0.004 USD per Spotify stream; editable under "
    "Advanced Settings). It is a rough planning estimate, not WMG revenue, royalty income, profit or advertising ROI. "
    "Spotify has no universal fixed per-stream royalty, the rate is applied to Spotify streams only, and the change "
    "is not shown to have been caused by advertising. A negative number is not a verified loss."
)


@dataclass
class StreamingValue:
    enabled: bool
    rate: float | None
    streams_change: float | None
    value: float | None
    display: str
    reason: str = ""

    @property
    def calculated(self) -> bool:
        return self.value is not None


def format_money(value: float) -> str:
    sign = "+" if value > 0 else ("-" if value < 0 else "")
    digits = 0 if abs(value) >= 1000 else 2
    return f"{sign}${abs(value):,.{digits}f}"


def estimate_streaming_value(
    observed_change: float | None,
    rate: float | None = DEFAULT_RATE_USD,
    *,
    enabled: bool = True,
    applies: bool = True,
    reason_if_not_applicable: str = "",
) -> StreamingValue:
    """``observed_change`` is the streams change on the service the rate applies to (Spotify)."""
    if not enabled:
        return StreamingValue(False, rate, observed_change, None, "Off")
    if not applies:
        return StreamingValue(True, rate, observed_change, None, NOT_CALCULATED, reason_if_not_applicable)
    if rate is None or pd.isna(rate) or rate <= 0:
        return StreamingValue(True, rate, observed_change, None, NOT_CALCULATED, "No valid value per stream is set.")
    if observed_change is None or pd.isna(observed_change):
        return StreamingValue(True, rate, observed_change, None, NOT_CALCULATED, "There is no valid observed streaming change.")
    value = float(observed_change) * float(rate)
    return StreamingValue(True, float(rate), float(observed_change), value, format_money(value))
