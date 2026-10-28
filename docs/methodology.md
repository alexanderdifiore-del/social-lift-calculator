# How Lollie calculates things

Lollie describes what happened to streaming around a paid campaign. It does **not** attribute streams to advertising.

## Expected baseline

1. **Baseline window.** The days just before the campaign start (default 28; configurable from 7 to 56, with an optional gap of
   up to 7 days right before launch).
2. **Only days with streaming data count.** A missing day is never treated as zero.
3. **Method.**
   * If every weekday has at least 3 baseline days, the expected value for a day is the **median of the same weekday** in the
     baseline window.
   * Otherwise it is the **median of all baseline days**.
   * If there are fewer than the minimum baseline days (default 7), no expected line is drawn and the reason is shown.
4. The expected level is carried flat across the campaign and after-campaign windows. It is not adjusted for trends, new
   releases, playlist changes, social posts, press or seasonality beyond the weekday pattern.

## Pre / during / post comparison

* **Before campaign:** average daily streams in the baseline window.
* **During campaign:** average daily streams from the campaign start date to the end date.
* **After campaign:** average daily streams in the configured number of days after the end date (default 14).
* **Observed streaming change:** actual streams minus expected streams, adding up only the days that have streaming data.
* **Change versus baseline:** observed change divided by expected streams.
* Missing days are left out of both the actual and the expected total, so a data gap cannot look like a drop or a gain.
* Streaming data coverage (days with data / days in the window) is reported, with a warning below 80%.
* The after-campaign change uses the same baseline, so it shows whether streams stayed above or below it; it is not a
  separate experiment.
* A warning appears when streams were already rising or falling before launch (more than 10% between the first and second half
  of the baseline window), because a flat baseline is then too low or too high.

## Several countries, tracks and campaigns

* Totals across several countries only include days when **every** selected country reported, so a country's missing day does not
  look like a fall in the total.
* Each country in Section D has its own baseline, using that country's own paid dates when the report has them.
* Countries with little or no paid spend (default under 2% of spend) are labelled **Reference only**. They are shown for
  context but are not treated as a control group, because they may differ in size, release timing, playlisting and more.
* Section D's rank correlation asks only whether countries with higher spend also had a larger change. It needs at least
  four paid countries and is described as a rough guide.
* Overlapping campaigns in the same countries are listed whenever they fall in the baseline, the campaign or the after window.
* When several campaigns are loaded, each is compared with its own baseline, and the summary only says whether the direction
  was the same across campaigns.

## Spend and streaming timing

For each delay from 0 to 7 days, Lollie correlates daily ad spend with the daily streaming change (actual minus expected) that
many days later and reports the strongest match.

* It needs at least 14 days with both spend and streaming data, and spend must vary.
* Because eight delays are tried, a moderate match can occur by chance.
* It is called a **Potential positive relationship** only when the correlation is at least +0.5, and (for a country) streams
  were also at least 5% above baseline overall. Weaker matches are labelled *Weak positive pattern* or *No clear relationship*.

## Language

The app and summaries use: *Observed streaming change*, *Change versus baseline*, *Streaming activity during campaign*,
*Potential positive relationship*. They do not say that advertising caused, drove or generated streams.
