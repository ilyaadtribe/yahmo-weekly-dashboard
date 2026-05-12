# Yahmo — Meta & Google Ads Weekly Dashboard

Live dashboard: https://ilyaadtribe.github.io/yahmo-weekly-dashboard/

Weekly performance report for Yahmo combining Meta Ads (`act_10207584714042283`) and Google Ads (`7543821390`), refreshed every Monday via a scheduled Claude agent using the GoMarble MCP connectors.

## What's in the dashboard

- **KPI cards** — latest week spend, blended ROAS, total purchases, KPI compliance over the last 4 weeks.
- **Weekly spend trend** — 12-week bar chart of combined Meta + Google spend.
- **Weekly KPI flags** — ROAS Meta (≥ 3.00), ROAS Google (≥ 5.00). April 2026 targets.
- **Last 12 Months summary** — aggregate spend / revenue / purchases / ROAS / CPA for the trailing 52 weeks, on every tab.
- **Meta Ads weekly table** — spend, purchases, revenue, CPA, ROAS, reach, impressions, clicks, CPM, CTR%, CPC, frequency, hook rate (3-sec views / impressions), hold rate (ThruPlays / 3-sec views).
- **Google Ads weekly table** — spend, conversions, revenue, CPA, ROAS, impressions, clicks, CPM, CTR%, CPC, plus impression share (abs top / top / search lost budget / search lost rank).

## How it refreshes

A scheduled Claude agent runs every Monday and follows [`REFRESH.md`](./REFRESH.md):

1. Pulls weekly Meta insights via `facebook_get_adaccount_insights` (GoMarble MCP).
2. Pulls weekly Google Ads metrics via `google_ads_run_gaql` (GoMarble MCP).
3. Regenerates `data.json` and runs `python3 build.py` to render `index.html`.
4. Commits the changes; GitHub Pages serves the updated dashboard.

## Files

- `index.html` — generated dashboard (do not edit by hand).
- `data.json` — combined weekly data backing the dashboard.
- `build.py` — turns `data.json` into `index.html`.
- `REFRESH.md` — instructions for the weekly Claude agent.

## Manual rebuild

```bash
python3 build.py
```
