# Yahmo Dashboard — Refresh Procedure

This file is read by the scheduled Claude agent every Monday. The agent has access to the GoMarble MCP tools and to this GitHub repo (via `gh` / `git`).

## Inputs

- **Brand**: Yahmo
- **Meta ad account**: `act_10207584714042283` (name: "YAHMO Ad Acc")
- **Google Ads customer**: `7543821390` (name: "yahmo.com"), manager `4749583550`
- **Repo**: `ilyaadtribe/yahmo-weekly-dashboard` (main branch, GitHub Pages)
- **Window**: pull a rolling 52-week window ending on yesterday.

## Steps the agent must perform

1. **Clone or pull the repo locally**:
   ```bash
   gh repo clone ilyaadtribe/yahmo-weekly-dashboard /tmp/yahmo-dash || (cd /tmp/yahmo-dash && git pull --rebase)
   ```

2. **Pull Meta weekly insights** via the GoMarble MCP tool `facebook_get_adaccount_insights`:
   - `act_id`: `act_10207584714042283`
   - `level`: `account`
   - `time_increment`: `7`
   - `time_range`: `{"since": "<today minus 364 days>", "until": "<yesterday>"}`
   - `fields`: `["spend", "impressions", "reach", "clicks", "ctr", "cpm", "cpc", "frequency", "actions", "action_values", "purchase_roas"]`
   - **Important**: Meta paginates at 25 weeks per page. The agent MUST follow `paging.next` via `facebook_fetch_pagination_url` until exhausted.
   - For each weekly row, extract:
     - `spend`, `impressions`, `reach`, `clicks`, `ctr`, `cpm`, `cpc`, `frequency`
     - `purchases` = the `omni_purchase` entry in `actions` (fallback: `purchase`)
     - `revenue`  = the `omni_purchase` entry in `action_values` (fallback: `purchase`)
     - `roas`     = the `omni_purchase` entry in `purchase_roas`
     - Derive `cpa = spend / purchases` (or 0 if purchases==0)

3. **Pull Google Ads weekly metrics** via `google_ads_run_gaql`:
   - `customer_id`: `"7543821390"`, `manager_id`: `"4749583550"`
   - Query:
     ```
     SELECT segments.week, metrics.cost_micros, metrics.impressions, metrics.clicks, metrics.conversions, metrics.conversions_value
     FROM customer
     WHERE segments.date BETWEEN '<since>' AND '<until>'
     ORDER BY segments.week ASC
     ```
   - **Note**: although the field name is `cost_micros`, this MCP returns `metrics.cost` in actual currency units. Use `metrics.cost` directly.

4. **Pull Google Ads impression-share** at the campaign level (impression share is not exposed on `customer`), then aggregate per week weighted by impressions:
   ```
   SELECT segments.week, metrics.impressions, metrics.search_budget_lost_impression_share, metrics.search_rank_lost_impression_share, metrics.search_absolute_top_impression_share, metrics.search_top_impression_share
   FROM campaign
   WHERE campaign.advertising_channel_type = 'SEARCH'
     AND segments.date BETWEEN '<since>' AND '<until>'
   ORDER BY segments.week ASC
   ```
   For each week, compute the impression-weighted average of the four shares across SEARCH campaigns.

5. **Build `data.json`** with the schema below and write it to the repo root. Weeks ordered newest first.
   ```json
   {
     "account": {
       "brand": "YAHMO",
       "meta_account_id":   "act_10207584714042283",
       "meta_account_name": "YAHMO Ad Acc",
       "google_customer_id":  "7543821390",
       "google_manager_id":   "4749583550",
       "google_account_name": "yahmo.com"
     },
     "generated_at": "<ISO8601 UTC>",
     "weeks_count":  53,
     "date_range":   {"from": "<oldest_week>", "to": "<latest_week>"},
     "thresholds":   {"purchases_min": 40, "roas_meta_min": 3.0, "roas_google_min": 5.0},
     "weeks": [
       {
         "week_start": "YYYY-MM-DD",
         "meta":   { "week_start", "week_end", "spend", "impressions", "reach", "clicks", "ctr", "cpm", "cpc", "frequency", "purchases", "revenue", "roas", "cpa" },
         "google": { "week_start", "spend", "impressions", "clicks", "purchases", "revenue", "cpa", "roas", "cpm", "ctr", "cpc", "abs_top_pct", "top_pct", "budget_lost_pct", "rank_lost_pct" }
       }
     ]
   }
   ```

6. **Rebuild the dashboard**:
   ```bash
   cd /tmp/yahmo-dash && python3 build.py
   ```

7. **Commit and push**:
   ```bash
   git -C /tmp/yahmo-dash add data.json index.html
   git -C /tmp/yahmo-dash commit -m "Refresh data through $(date -u +%Y-%m-%d)" || echo "no changes"
   git -C /tmp/yahmo-dash push
   ```

8. **Sanity checks before pushing**:
   - `weeks_count` should be ≥ 50 and ≤ 53.
   - Latest week's date should be ≥ (today − 7 days).
   - No week should have both `meta == null` and `google == null`.
   - If any check fails, do NOT commit. Stop and report.

## What not to change

- Do not touch the design/style of `index.html` — `build.py` regenerates it from scratch each run.
- Do not edit `build.py` schema fields unless you are explicitly asked to add a new metric.
- KPI thresholds are fixed: purchases ≥ 40, ROAS Meta ≥ 3.00, ROAS Google ≥ 5.00 (April 2026 targets).
