"""Lollie analytics package — streaming, commerce, and paid media intelligence."""

__version__ = "2.0.0"

from lollie.branding import render_lollie_header
from lollie.paid_media import (
    PaidMediaPlan,
    build_paid_media_plan,
    channel_efficiency_table,
)

__all__ = [
    "__version__",
    "render_lollie_header",
    "PaidMediaPlan",
    "build_paid_media_plan",
    "channel_efficiency_table",
]
