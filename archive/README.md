# Archive of Lollie v1 features

These files were removed from the Lollie V2 application (paid media + streaming only) but are kept for reference so useful code is not lost. **Nothing here is imported by the app and none of it is tested or maintained.** The code expects the older `lollie/` package layout, so it will not run as-is.

| Folder | What it was | Why it was archived |
| --- | --- | --- |
| `v1_features/ecommerce/` | Product revenue model, commerce charts, sales upload and sidebar controls | V2 is scoped to paid media and streaming |
| `v1_features/ad_credits/` | Ad credits and funding database, programs, allocations, imports, UI | Out of scope for V2 |
| `v1_features/streaming_simulation/` | The original simulated hourly baseline with artist-tier, platform, market, DSP and post-type multipliers, plus the lift decay curve | Arbitrary multipliers are not part of V2; V2 measures real data only |
| `v1_features/audience_creative/` | Audience / creative ranking and the first campaign recap | Not requested for V2 |
| `v1_features/unified_dashboard_v1/` | The previous single-page dashboard, its UI helpers and tests | Superseded by V2 |

**YouTube video upscaling** was removed earlier and is not archived. It can be recovered from the git history before commit `8860465`, in the original `social_lift_calculator.py`. YouTube *advertising* data is still fully supported.
