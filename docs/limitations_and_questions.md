# Known limitations and questions for the analytics team

## Known limitations

* **Observational only.** A rise in streams during a campaign can come from releases, playlist adds, social posts, press, touring,
  seasonality or other campaigns. Lollie flags overlapping campaigns and a drifting baseline but cannot remove these effects.
* **Baseline is history-based.** The Global Catalog baseline follows a recording's own recent history (level, weekday pattern,
  gentle trend) but does not know about releases, holidays, playlist changes, tours or press that happen during the campaign.
  Strongly wandering recordings are only roughly calibrated, so "outside normal range" can appear more often than it should.
* **Other campaigns stay in the history.** Earlier flights are not removed from the history window; they make a recording look
  more variable, which makes Lollie more cautious.
* **Estimated Streaming Value Change is a planning figure.** USD 0.004 per Spotify stream is an editable assumption, not a
  royalty rate, and is not revenue, profit or ad return.
* **Daily data only.** Hourly rows are summed into complete days; hour-level analysis is not done.
* **Country-level streaming.** Paid media is matched to streaming at country level, not by city, audience or ad set.
* **Streaming reports vary.** Opus export columns are not known, so column matching is flexible and manual. Lollie does not
  connect to Opus.
* **Playlist membership is user-supplied.** Lollie cannot see Spotify playlist history or private streaming data.
* **Total versus attributed streams.** Source-attributed streams are shown separately and never summed with totals. A source row
  does not prove that source created the streams.
* **Reference countries are not controls.** Differences between paid and unpaid countries are not evidence of advertising
  impact.
* **Small samples.** Few countries, few days, or sparse data make rank and timing correlations unreliable.
* **Date formats.** Ambiguous dates such as `03/04/2026` are read month-first.
* **Currency.** Amounts are not converted between currencies.
* **Prototype.** Synthetic data only has been used to test it. Any production use needs company approval and technical and security
  review. The app makes no network calls to company systems and must not be deployed publicly.

## Questions for the analytics team

1. What are the exact columns, file formats and delivery process for approved Opus (or other) streaming exports? Is there a
   standard file that includes ISRC, country, DSP and source?
2. Do WAVO exports include campaign start and end dates, promoted song or playlist, ISRC and landing page views? Which
   column holds each?
3. How should results be defined for each objective, and can WAVO label the result type on every row?
4. Are streaming dates in UTC or local time, and do ad platform reporting days use the account time zone? A one-day offset
   would change the timing analysis.
5. How complete is streaming data for the most recent days (reporting lag), and should recent days be excluded?
6. Is there an approved way to get playlist membership and add / remove dates for a campaign?
7. Is a 56-day history window (auto-falling back to 28 / 14) the right default for established catalog? Do the damped-trend
   rules (28+ days, 1.5% change, 0.99 damping, 25% cap) and the spike rule (3.5 robust sigma, at most 15% of days) look
   sensible? What counts as a valid comparison country?
8. How should overlapping campaigns, artist release events and organic social posts be recorded so they can be controlled for?
9. Are the thresholds right? "Within normal range" is |z| < 1 (or under 2% change), "slightly outside" is 1 to 2, "outside" is
   2 or more, where z compares the change with the recording's own period variability (the largest of a parametric, a
   rolling-window and a backtest estimate). The timing label uses a correlation of 0.5 as a placeholder.
10. What data handling, storage and approval steps are needed before real company files can be used?
11. Should days from other paid flights be excluded from the history window and backtest, and where would that campaign list come from?
12. Should playlist campaigns be summed from per-track baselines (current) or fitted on the combined series?
13. Is a Spotify-only USD 0.004 per stream an acceptable planning assumption, and should other DSPs get their own rates?
14. Is the year-ago (364-day) seasonal check useful, and how should recordings with release-year anniversaries be treated?
