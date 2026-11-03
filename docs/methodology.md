# How Lollie calculates things

Lollie describes what happened to streaming around a paid campaign. It does **not** attribute streams to advertising.

## Global Catalog baseline (expected streams)

Established catalog recordings are not flat: they have weekly cycles, seasonality, viral moments, tours and playlist
placements. Lollie therefore asks, for each recording separately, *what does normal look like in the weeks before launch?*
Only data **before** the campaign start is used (nothing from the campaign or after it, so there is no leakage). Days without
streaming data are never filled in or treated as zero.

### In plain English

1. Take the recording's own history before launch: 14, 28, **56 (preferred default)** or 90 days. "Auto" uses 56 when at least
   70% of those days have data, otherwise 28, then 14, and says which it used.
2. Find its normal level (the **median**, so a few big days do not pull it).
3. Work out its usual weekday pattern (Fridays compared with Fridays), once there are 14+ days with at least 2 of each weekday.
4. If the history shows a steady rise or fall, let the baseline follow it gently (needs 28+ days, a consistent direction and
   at least a 1.5% change over the window). The trend fades out rather than continuing forever and is capped at 25% beyond
   the end level. There is no universal growth or decay curve; a recording with no clear trend gets none.
5. Set aside spike days (more than 3.5 robust standard deviations from normal, at most 15% of days). They stay in the actual
   line but do not shape the baseline.
6. Measure how much this recording's streams normally wander, and show that as a "typical range from history".
7. Compare the campaign result with that wander before calling it unusual.

### Technical detail

* **Level and weekday factors.** Level is the median of weekday-adjusted values. A weekday factor is the median of
  `streams / level` for that weekday, rescaled to average 1.
* **Trend.** Theil-Sen slope (median of pairwise slopes), accepted only if the rank correlation of the series with time is at
  least `max(0.3, 2/sqrt(n-1))` and the fitted change over the window is at least 1.5%. Projection uses damping 0.99 per day
  and a cap of +/-25% of the end level.
* **Spikes.** Residuals are computed leave-one-out; a day is a spike if more than 3.5 robust sigma (MAD x 1.4826) from the
  median residual. Sigma is estimated from all points; at most 15% of days can be set aside.
* **Variability.** Daily relative sigma (floored at 0.5%) is scaled to a multi-day period using the lag-1 autocorrelation of
  consecutive days (clipped 0 to 0.8) and the number of baseline days. The period sigma used for judgements is the
  largest of: this parametric figure, how far real rolling windows of the same length landed from the baseline inside the
  history window, and the root-mean-square miss of the backtest below. Extra uncertainty is added for unmodelled drift or
  trend extrapolation.
* **Judgement.** `z = percentage change / period sigma`. |z| < 1 or |change| < 2%: *within normal range*; 1 to 2:
  *slightly above / below range*; 2 or more: *above / below normal range*. A small change is never called significant just
  because it is positive. The words describe size relative to the recording's own history, not statistical proof of an
  effect.
* **Backtest (validation against history).** Using only data up to the day before launch, Lollie repeats the same forecast from
  up to 16 earlier start dates (every 3 days) over periods as long as the campaign, and records how far the baseline missed.
  It also reports how often daily streams landed inside the typical range and how it compares with a naive flat baseline.
  At least 6 earlier periods are needed, otherwise it says so. Isolated spike days are set aside in this check.
* **Missing history.** Fewer than 7 days (configurable): no baseline, with the reason shown. Fewer than 14 days: a "short
  history" warning, no weekday pattern. Fewer than 28 days: no trend.
* **Year-ago check.** If a year of history exists, the same dates 364 days earlier are analysed the same way and noted when
  they moved by 3% or more, as a hint of seasonality.
* **Concentration.** If the top 3 days make up more than 50% of the observed increase (over 7+ days), the summary says
  the result is concentrated in a few days.

## Observed streaming change

* **Expected streams** = baseline summed over days that have actual data.
* **Actual streams** = streams on those same days.
* **Observed streaming change** = actual minus expected. **Percentage change vs. baseline** = change / expected.
* Missing days are left out of both totals, so a gap cannot look like a drop or a gain.
* Coverage (days with data / days in the window) is reported, with a warning below 80%.
* The after-campaign figures use the same baseline (it is not re-fitted), so they show whether streams stayed above or below
  normal; they are not a separate experiment.
* Expected streams are **never** multiplied by a per-stream value.

## Estimated Streaming Value Change (optional)

`Observed Streaming Change x assumed value per stream`, default **USD 0.004 per Spotify stream**.
Example: expected 100,000, actual 125,000 gives +25,000 streams and +USD 100.

* Editable in **Advanced Settings** (collapsed) and can be switched off.
* Spotify only. It is not applied to other DSPs, not used in the baseline, and not shown as WMG revenue, royalties, profit or
  ad return. Spotify has no universal fixed per-stream royalty, so it is a planning estimate.
* A negative value is described as a negative estimate, never a verified loss.
* Shows "Not calculated" when there is no applicable rate or no valid difference. In an "All DSPs" view the estimate uses a
  separate Spotify-only analysis.

## Several tracks, countries and campaigns

* **Playlists and multi-track campaigns.** Each track has its own baseline from its own history. Expected and actual streams
  are added up over the days all usable tracks reported, so each track is counted once. Tracks with too little history are
  left out and named. Source-attributed (playlist-attributed) streams are shown separately and never added to track totals.
* Totals across several countries only include days when **every** selected country reported.
* Each country in Section D has its own baseline, using that country's own paid dates when the report has them.
* Countries with little or no paid spend (default under 2% of spend) are labelled **Reference only**, not a control group.
* Section D's rank correlation asks only whether countries with higher spend also had a larger change; it needs at least four
  paid countries and is a rough guide.
* Overlapping campaigns are listed whenever they fall in the baseline, the campaign or the after window. Days from other
  campaigns are **not** removed from the history window, so earlier flights make a recording look more variable (which
  makes Lollie more cautious, not less).

## Spend and streaming timing

For each delay from 0 to 7 days, Lollie correlates daily ad spend with the daily streaming change (actual minus expected) that
many days later and reports the strongest match.

* It needs at least 14 days with both spend and streaming data, and spend must vary.
* Because eight delays are tried, a moderate match can occur by chance.
* It is called a **Potential positive relationship** only when the correlation is at least +0.5 and the streaming change was
  positive. Weaker matches are labelled *Weak positive pattern* or *No clear relationship*.

## Language

The app and summaries use: *Observed streaming change*, *Change versus baseline*, *Streaming performance was X% above the
historical baseline during the campaign*, *Potential positive relationship*. They do not say that advertising caused, drove or
generated streams.

## Not included

Radio statistics are not part of Lollie. Streaming on Spotify, Apple Music, Amazon Music, YouTube Music and other DSPs, and
YouTube paid advertising, are supported.
