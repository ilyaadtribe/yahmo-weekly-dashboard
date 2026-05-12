#!/usr/bin/env python3
"""Render data.json into index.html for the Yahmo weekly dashboard."""
import json
import datetime
import html
from pathlib import Path

ROOT = Path(__file__).parent
DATA = json.loads((ROOT / "data.json").read_text())
WEEKS = DATA["weeks"]
TH = DATA["thresholds"]
ACCT = DATA["account"]
DATE_RANGE = DATA["date_range"]


def usd(v):
    if v is None or v == 0:
        return "$0.00"
    return f"${v:,.2f}"


def num(v, dec=2):
    if v is None:
        return "—"
    return f"{v:,.{dec}f}"


def intf(v):
    if v is None:
        return "—"
    return f"{int(v):,}"


def pct(v, dec=2):
    if v is None:
        return "—"
    return f"{v*100:.{dec}f}%"


def cls_thresh(value, minimum):
    if value is None:
        return "neu"
    return "pos" if value >= minimum else "neg"


def short_date(d):
    return datetime.date.fromisoformat(d).strftime("%b %d, %Y")


def week_label(d, partial_set):
    base = short_date(d)
    if d in partial_set:
        return f'{base} <span class="partial-tag">partial</span>'
    return base


def spend_bg(value, vmin, vmax):
    """Subtle purple heatmap. Darker = higher spend within the visible range."""
    if value is None or value == 0 or vmax == vmin:
        return ""
    norm = max(0.0, min(1.0, (value - vmin) / (vmax - vmin)))
    alpha = 0.04 + 0.22 * norm  # 0.04 → 0.26
    return f' style="background:rgba(108,47,206,{alpha:.2f})"'


def roas_bg(value, target):
    """Gradient: red below target, neutral at target, green above. Intensity scales with distance from target."""
    if value is None or value == 0 or target == 0:
        return ""
    ratio = value / target  # 1.0 = exactly on target
    if ratio < 1.0:
        # 0 → ratio=0 (full red), 1.0 → no fill
        intensity = 1.0 - ratio  # 0..1
        alpha = 0.10 + 0.28 * intensity
        return f' style="background:rgba(255,91,91,{alpha:.2f})"'
    else:
        # 1.0 → no fill, 2.0 → full green; cap at ratio=2 (i.e. 2× target)
        intensity = min(1.0, (ratio - 1.0))
        alpha = 0.06 + 0.24 * intensity
        return f' style="background:rgba(199,243,0,{alpha:.2f})"'


# --- Identify the latest *complete* week (a week is complete if it started ≥ 7 days ago) ---
TODAY = datetime.date.today()
def is_complete(w):
    return (TODAY - datetime.date.fromisoformat(w["week_start"])).days >= 7

# Index of the first complete week (closest to today)
LATEST_COMPLETE_IDX = next((i for i, w in enumerate(WEEKS) if is_complete(w)), 0)
HAS_PARTIAL = LATEST_COMPLETE_IDX > 0  # there's a current in-progress week at the top
PARTIAL_WEEKS = set(w["week_start"] for w in WEEKS[:LATEST_COMPLETE_IDX]) if HAS_PARTIAL else set()

# --- KPI cards reflect the latest *complete* week, not the in-progress one ---
latest = WEEKS[LATEST_COMPLETE_IDX]
latest_meta = latest["meta"] or {}
latest_google = latest["google"] or {}

latest_spend = (latest_meta.get("spend") or 0) + (latest_google.get("spend") or 0)
latest_revenue = (latest_meta.get("revenue") or 0) + (latest_google.get("revenue") or 0)
latest_purchases = (latest_meta.get("purchases") or 0) + (latest_google.get("purchases") or 0)
blended_roas = (latest_revenue / latest_spend) if latest_spend else 0
meta_spend = latest_meta.get("spend") or 0
google_spend = latest_google.get("spend") or 0
meta_roas = latest_meta.get("roas") or 0
google_roas = latest_google.get("roas") or 0
meta_purchases = latest_meta.get("purchases") or 0
google_purchases = latest_google.get("purchases") or 0
meta_revenue = latest_meta.get("revenue") or 0
google_revenue = latest_google.get("revenue") or 0

# Threshold compliance: last 4 complete weeks (skip the in-progress week if any)
compliance_weeks = WEEKS[LATEST_COMPLETE_IDX:LATEST_COMPLETE_IDX + 4]
def hits_kpi(w):
    m = w["meta"] or {}
    g = w["google"] or {}
    return (
        (m.get("roas") or 0) >= TH["roas_meta_min"]
        and (g.get("roas") or 0) >= TH["roas_google_min"]
    )
hits = sum(1 for w in compliance_weeks if hits_kpi(w))
meta_hits   = sum(1 for w in compliance_weeks if ((w["meta"] or {}).get("roas") or 0) >= TH["roas_meta_min"])
google_hits = sum(1 for w in compliance_weeks if ((w["google"] or {}).get("roas") or 0) >= TH["roas_google_min"])

# --- Last 12 months (52 weeks) aggregate ---
TTM = WEEKS[:52]
def agg_platform(weeks, side):
    spend = sum((w[side] or {}).get("spend") or 0 for w in weeks)
    rev   = sum((w[side] or {}).get("revenue") or 0 for w in weeks)
    purch = sum((w[side] or {}).get("purchases") or 0 for w in weeks)
    imp   = sum((w[side] or {}).get("impressions") or 0 for w in weeks)
    clk   = sum((w[side] or {}).get("clicks") or 0 for w in weeks)
    v3    = sum((w[side] or {}).get("video_3s") or 0 for w in weeks)
    thru  = sum((w[side] or {}).get("thruplays") or 0 for w in weeks)
    return {
        "spend": spend, "revenue": rev, "purchases": purch,
        "impressions": imp, "clicks": clk,
        "video_3s": v3, "thruplays": thru,
        "roas":      (rev / spend) if spend else 0,
        "cpa":       (spend / purch) if purch else 0,
        "cpm":       (spend / imp * 1000) if imp else 0,
        "ctr":       (clk / imp * 100) if imp else 0,
        "cpc":       (spend / clk) if clk else 0,
        "hook_rate": (v3 / imp) if imp else 0,
        "hold_rate": (thru / v3) if v3 else 0,
    }
meta_ttm = agg_platform(TTM, "meta")
google_ttm = agg_platform(TTM, "google")
combined_ttm_spend = meta_ttm["spend"] + google_ttm["spend"]
combined_ttm_revenue = meta_ttm["revenue"] + google_ttm["revenue"]
combined_ttm_purchases = meta_ttm["purchases"] + google_ttm["purchases"]
combined_ttm_roas = (combined_ttm_revenue / combined_ttm_spend) if combined_ttm_spend else 0
ttm_weeks = len(TTM)
ttm_label = f"Last {ttm_weeks} weeks · {short_date(TTM[-1]['week_start'])} – {short_date(TTM[0]['week_start'])}"

# --- KPI flag rows (Overall tab) — ROAS only ---
kpi_rows = []
for w in WEEKS:
    m = w["meta"] or {}
    g = w["google"] or {}
    m_roas = m.get("roas") or 0
    g_roas = g.get("roas") or 0
    kpi_rows.append(f"""<tr>
      <td class="acct">{week_label(w['week_start'], PARTIAL_WEEKS)}</td>
      <td class="{cls_thresh(m_roas, TH['roas_meta_min'])}">{num(m_roas)}</td>
      <td class="{cls_thresh(g_roas, TH['roas_google_min'])}">{num(g_roas)}</td>
    </tr>""")

# --- Heatmap ranges (computed from complete weeks only so partial doesn't distort) ---
complete_only = [w for w in WEEKS if w["week_start"] not in PARTIAL_WEEKS]
meta_spend_vals   = [(w["meta"] or {}).get("spend")  or 0 for w in complete_only if w["meta"]]
google_spend_vals = [(w["google"] or {}).get("spend") or 0 for w in complete_only if w["google"]]
META_SPEND_MIN, META_SPEND_MAX     = (min(meta_spend_vals), max(meta_spend_vals))     if meta_spend_vals else (0, 0)
GOOGLE_SPEND_MIN, GOOGLE_SPEND_MAX = (min(google_spend_vals), max(google_spend_vals)) if google_spend_vals else (0, 0)

# --- Meta rows ---
meta_rows = []
for w in WEEKS:
    m = w["meta"] or {}
    if not m:
        meta_rows.append(f"""<tr><td class="acct">{week_label(w['week_start'], PARTIAL_WEEKS)}</td><td colspan="14" class="neu">no data</td></tr>""")
        continue
    is_partial = w["week_start"] in PARTIAL_WEEKS
    spend_attrs = "" if is_partial else spend_bg(m.get('spend'), META_SPEND_MIN, META_SPEND_MAX)
    roas_attrs  = "" if is_partial else roas_bg(m.get('roas'), TH['roas_meta_min'])
    meta_rows.append(f"""<tr>
      <td class="acct">{week_label(w['week_start'], PARTIAL_WEEKS)}</td>
      <td{spend_attrs}>{usd(m.get('spend'))}</td>
      <td>{intf(m.get('purchases'))}</td>
      <td>{usd(m.get('revenue'))}</td>
      <td>{usd(m.get('cpa'))}</td>
      <td{roas_attrs}>{num(m.get('roas'))}</td>
      <td>{intf(m.get('reach'))}</td>
      <td>{intf(m.get('impressions'))}</td>
      <td>{intf(m.get('clicks'))}</td>
      <td>{num(m.get('cpm'))}</td>
      <td>{num(m.get('ctr'))}%</td>
      <td>{usd(m.get('cpc'))}</td>
      <td>{num(m.get('frequency'))}</td>
      <td>{pct(m.get('hook_rate'))}</td>
      <td>{pct(m.get('hold_rate'))}</td>
    </tr>""")

# --- Google rows ---
google_rows = []
for w in WEEKS:
    g = w["google"] or {}
    if not g:
        google_rows.append(f"""<tr><td class="acct">{week_label(w['week_start'], PARTIAL_WEEKS)}</td><td colspan="14" class="neu">no data</td></tr>""")
        continue
    is_partial = w["week_start"] in PARTIAL_WEEKS
    spend_attrs = "" if is_partial else spend_bg(g.get('spend'), GOOGLE_SPEND_MIN, GOOGLE_SPEND_MAX)
    roas_attrs  = "" if is_partial else roas_bg(g.get('roas'), TH['roas_google_min'])
    google_rows.append(f"""<tr>
      <td class="acct">{week_label(w['week_start'], PARTIAL_WEEKS)}</td>
      <td{spend_attrs}>{usd(g.get('spend'))}</td>
      <td>{num(g.get('purchases'), 1)}</td>
      <td>{usd(g.get('revenue'))}</td>
      <td>{usd(g.get('cpa'))}</td>
      <td{roas_attrs}>{num(g.get('roas'))}</td>
      <td>{intf(g.get('impressions'))}</td>
      <td>{intf(g.get('clicks'))}</td>
      <td>{num(g.get('cpm'))}</td>
      <td>{num(g.get('ctr'))}%</td>
      <td>{usd(g.get('cpc'))}</td>
      <td>{pct(g.get('abs_top_pct'))}</td>
      <td>{pct(g.get('top_pct'))}</td>
      <td>{pct(g.get('budget_lost_pct'))}</td>
      <td>{pct(g.get('rank_lost_pct'))}</td>
    </tr>""")


HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{ACCT['brand']} — Meta & Google Ads Weekly</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {{
    --black: #010101;
    --purple: #6c2fce;
    --purple-2: #8b56e3;
    --lime: #c7f300;
    --white: #ffffff;
    --bg: var(--black);
    --panel: #0a0a0c;
    --panel-2: #111114;
    --border: rgba(255,255,255,0.08);
    --border-2: rgba(255,255,255,0.14);
    --text: var(--white);
    --muted: rgba(255,255,255,0.55);
    --muted-2: rgba(255,255,255,0.38);
    --accent: var(--purple);
    --accent-2: var(--purple-2);
    --good: var(--lime);
    --bad: #ff5b5b;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; }}
  body {{
    font-family: "DM Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background:
      radial-gradient(900px 500px at 85% -10%, rgba(108,47,206,0.18) 0%, transparent 60%),
      radial-gradient(700px 400px at 0% 110%, rgba(199,243,0,0.05) 0%, transparent 55%),
      var(--bg);
    color: var(--text);
    min-height: 100vh;
    padding: 36px 24px 64px;
    -webkit-font-smoothing: antialiased;
    text-rendering: optimizeLegibility;
  }}
  .wrap {{ max-width: 1400px; margin: 0 auto; }}
  header {{ display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 28px; gap: 16px; flex-wrap: wrap; }}
  h1 {{ font-size: 24px; margin: 0; letter-spacing: -0.02em; font-weight: 600; }}
  .sub {{ color: var(--muted); font-size: 13px; }}
  .badge {{
    display: inline-block; padding: 4px 10px; border-radius: 999px;
    background: rgba(108,47,206,0.18); color: var(--lime);
    font-size: 10px; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase;
    border: 1px solid rgba(108,47,206,0.35);
  }}
  .tabs {{
    display: flex; gap: 4px; margin-bottom: 22px;
    background: var(--panel); border: 1px solid var(--border); border-radius: 12px;
    padding: 6px; width: fit-content;
  }}
  .tab-btn {{
    appearance: none; background: transparent; color: var(--muted);
    border: 1px solid transparent; padding: 8px 18px; border-radius: 8px;
    font-family: inherit; font-size: 12px; font-weight: 600;
    letter-spacing: 0.06em; text-transform: uppercase;
    cursor: pointer; transition: all 0.15s ease;
  }}
  .tab-btn:hover {{ color: var(--text); }}
  .tab-btn.active {{
    background: linear-gradient(180deg, rgba(108,47,206,0.20), rgba(108,47,206,0.10));
    color: var(--lime);
    border-color: rgba(108,47,206,0.35);
  }}
  .tab-panel {{ display: none; }}
  .tab-panel.active {{ display: block; }}
  .kpis {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 22px; }}
  @media (max-width: 800px) {{ .kpis {{ grid-template-columns: repeat(2, 1fr); }} }}
  .kpi {{
    background: linear-gradient(180deg, var(--panel) 0%, var(--panel-2) 100%);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 18px 18px 16px;
    position: relative;
    overflow: hidden;
  }}
  .kpi::before {{
    content: ""; position: absolute; inset: 0;
    background: radial-gradient(300px 120px at 110% 0%, rgba(108,47,206,0.10), transparent 70%);
    pointer-events: none;
  }}
  .kpi .label {{ color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 0.10em; margin-bottom: 8px; font-weight: 500; }}
  .kpi .value {{ font-size: 28px; font-weight: 600; letter-spacing: -0.025em; }}
  .kpi .meta {{ color: var(--muted); font-size: 12px; margin-top: 4px; }}
  .kpi.accent .value {{ color: var(--lime); }}
  .panel {{
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 14px;
    overflow: hidden;
  }}
  .panel + .panel {{ margin-top: 20px; }}
  .panel-h {{
    padding: 16px 20px; border-bottom: 1px solid var(--border);
    display: flex; align-items: center; justify-content: space-between;
  }}
  .panel-h h2 {{ margin: 0; font-size: 14px; font-weight: 600; letter-spacing: -0.01em; }}
  .scroll {{ overflow-x: auto; }}
  table {{ width: 100%; border-collapse: collapse; min-width: 1280px; }}
  th, td {{ padding: 10px 12px; text-align: right; font-variant-numeric: tabular-nums; font-size: 12.5px; white-space: nowrap; }}
  th:first-child, td:first-child {{ text-align: left; position: sticky; left: 0; background: var(--panel); z-index: 1; }}
  thead th:first-child {{ background: var(--panel-2); }}
  thead th {{
    color: var(--muted); font-size: 10px; font-weight: 600;
    letter-spacing: 0.10em; text-transform: uppercase;
    border-bottom: 1px solid var(--border);
    background: var(--panel-2);
  }}
  tbody tr {{ border-bottom: 1px solid var(--border); }}
  tbody tr:last-child {{ border-bottom: none; }}
  tbody tr:hover td {{ background: rgba(108,47,206,0.06); }}
  tbody tr:hover td:first-child {{ background: rgba(108,47,206,0.06); }}
  .acct {{ font-weight: 500; }}
  .partial-tag {{
    display: inline-block; margin-left: 6px;
    padding: 1px 6px; border-radius: 999px;
    background: rgba(255,255,255,0.06); color: var(--muted);
    font-size: 9px; font-weight: 600; letter-spacing: 0.08em;
    text-transform: uppercase; border: 1px solid var(--border);
    vertical-align: middle;
  }}
  .pos {{ color: var(--lime); font-weight: 500; }}
  .neg {{ color: var(--bad); font-weight: 500; }}
  .neu {{ color: var(--muted); }}
  tfoot td {{
    border-top: 1px solid var(--border-2);
    font-weight: 600;
    background: var(--panel-2);
    color: var(--text);
  }}
  tfoot td:first-child {{ background: var(--panel-2); }}
  footer {{ color: var(--muted-2); font-size: 11px; margin-top: 24px; text-align: right; letter-spacing: 0.02em; }}
</style>
</head>
<body>
<div class="wrap">

  <header>
    <div>
      <div class="badge">{ACCT['brand']} · Weekly Performance</div>
      <h1 style="margin-top:10px">{ACCT['brand']} — Meta &amp; Google Ads Weekly</h1>
      <div class="sub">{short_date(DATE_RANGE['from'])} – {short_date(DATE_RANGE['to'])} · {DATA['weeks_count']} weeks · Meta {ACCT['meta_account_id']} · Google {ACCT['google_customer_id']}</div>
      <div class="sub" style="margin-top:4px">Latest complete week: <strong style="color:var(--text)">{short_date(latest['week_start'])}</strong>{(' · current week ' + short_date(WEEKS[0]['week_start']) + ' is in progress') if HAS_PARTIAL else ''}</div>
    </div>
    <div class="sub">Source: GoMarble · KPIs: ROAS Meta ≥ {TH['roas_meta_min']:.2f} · ROAS Google ≥ {TH['roas_google_min']:.2f}</div>
  </header>

  <nav class="tabs" role="tablist">
    <button class="tab-btn active" data-tab="meta" role="tab" aria-selected="true">Meta Ads</button>
    <button class="tab-btn" data-tab="google" role="tab" aria-selected="false">Google Ads</button>
    <button class="tab-btn" data-tab="overall" role="tab" aria-selected="false">Overall</button>
  </nav>

  <!-- ============ OVERALL TAB ============ -->
  <section class="tab-panel" id="tab-overall" role="tabpanel">
    <section class="kpis">
      <div class="kpi">
        <div class="label">Latest Week Spend</div>
        <div class="value">{usd(latest_spend)}</div>
        <div class="meta">Meta {usd(meta_spend)} · Google {usd(google_spend)}</div>
      </div>
      <div class="kpi">
        <div class="label">Latest Week Blended ROAS</div>
        <div class="value" style="color:{'var(--lime)' if blended_roas >= TH['roas_meta_min'] else 'var(--bad)'}">{num(blended_roas)}</div>
        <div class="meta">Meta {num(meta_roas)} · Google {num(google_roas)}</div>
      </div>
      <div class="kpi accent">
        <div class="label">Latest Week Purchases</div>
        <div class="value">{intf(latest_purchases)}</div>
        <div class="meta">Meta {intf(meta_purchases)} · Google {num(google_purchases, 1)}</div>
      </div>
      <div class="kpi">
        <div class="label">ROAS Compliance · Last 4 Weeks</div>
        <div class="value">{hits} <span style="color:var(--muted-2);font-size:18px;font-weight:500">/ 4</span></div>
        <div class="meta">Weeks meeting Meta & Google ROAS targets</div>
      </div>
    </section>

    <section class="panel">
      <div class="panel-h">
        <h2>Last 12 Months · Combined</h2>
        <span class="sub">{ttm_label}</span>
      </div>
      <div class="scroll">
        <table>
          <thead>
            <tr>
              <th>Source</th>
              <th>Spend</th>
              <th>Revenue</th>
              <th>Purchases</th>
              <th>ROAS</th>
              <th>CPA</th>
              <th>Impressions</th>
              <th>Clicks</th>
              <th>CPM</th>
              <th>CTR%</th>
              <th>CPC</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td class="acct">Meta Ads</td>
              <td>{usd(meta_ttm['spend'])}</td>
              <td>{usd(meta_ttm['revenue'])}</td>
              <td>{intf(meta_ttm['purchases'])}</td>
              <td class="{cls_thresh(meta_ttm['roas'], TH['roas_meta_min'])}">{num(meta_ttm['roas'])}</td>
              <td>{usd(meta_ttm['cpa'])}</td>
              <td>{intf(meta_ttm['impressions'])}</td>
              <td>{intf(meta_ttm['clicks'])}</td>
              <td>{num(meta_ttm['cpm'])}</td>
              <td>{num(meta_ttm['ctr'])}%</td>
              <td>{usd(meta_ttm['cpc'])}</td>
            </tr>
            <tr>
              <td class="acct">Google Ads</td>
              <td>{usd(google_ttm['spend'])}</td>
              <td>{usd(google_ttm['revenue'])}</td>
              <td>{num(google_ttm['purchases'], 1)}</td>
              <td class="{cls_thresh(google_ttm['roas'], TH['roas_google_min'])}">{num(google_ttm['roas'])}</td>
              <td>{usd(google_ttm['cpa'])}</td>
              <td>{intf(google_ttm['impressions'])}</td>
              <td>{intf(google_ttm['clicks'])}</td>
              <td>{num(google_ttm['cpm'])}</td>
              <td>{num(google_ttm['ctr'])}%</td>
              <td>{usd(google_ttm['cpc'])}</td>
            </tr>
          </tbody>
          <tfoot>
            <tr>
              <td>Combined</td>
              <td>{usd(combined_ttm_spend)}</td>
              <td>{usd(combined_ttm_revenue)}</td>
              <td>{num(combined_ttm_purchases, 1)}</td>
              <td>{num(combined_ttm_roas)}</td>
              <td>{usd((combined_ttm_spend / combined_ttm_purchases) if combined_ttm_purchases else 0)}</td>
              <td>{intf(meta_ttm['impressions'] + google_ttm['impressions'])}</td>
              <td>{intf(meta_ttm['clicks'] + google_ttm['clicks'])}</td>
              <td>—</td>
              <td>—</td>
              <td>—</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </section>

    <section class="panel">
      <div class="panel-h">
        <h2>Weekly KPIs</h2>
        <span class="sub">Green = threshold met</span>
      </div>
      <div class="scroll">
        <table>
          <thead>
            <tr>
              <th>Week</th>
              <th>ROAS Meta (≥ {TH['roas_meta_min']:.2f})</th>
              <th>ROAS Google (≥ {TH['roas_google_min']:.2f})</th>
            </tr>
          </thead>
          <tbody>
            {''.join(kpi_rows)}
          </tbody>
        </table>
      </div>
    </section>
  </section>

  <!-- ============ META ADS TAB ============ -->
  <section class="tab-panel active" id="tab-meta" role="tabpanel">
    <section class="kpis">
      <div class="kpi">
        <div class="label">Meta · Latest Week Spend</div>
        <div class="value">{usd(meta_spend)}</div>
        <div class="meta">{short_date(latest['week_start'])}</div>
      </div>
      <div class="kpi">
        <div class="label">Meta · Latest Week ROAS</div>
        <div class="value" style="color:{'var(--lime)' if meta_roas >= TH['roas_meta_min'] else 'var(--bad)'}">{num(meta_roas)}</div>
        <div class="meta">Target ≥ {TH['roas_meta_min']:.0f} · Revenue {usd(meta_revenue)}</div>
      </div>
      <div class="kpi accent">
        <div class="label">Meta · Latest Week Purchases</div>
        <div class="value">{intf(meta_purchases)}</div>
        <div class="meta">CPA {usd(latest_meta.get('cpa'))}</div>
      </div>
      <div class="kpi">
        <div class="label">Meta · Latest Week Revenue</div>
        <div class="value">{usd(meta_revenue)}</div>
        <div class="meta">AOV {usd((meta_revenue / meta_purchases) if meta_purchases else 0)} · ROAS {num(meta_roas)}</div>
      </div>
    </section>

    <section class="panel">
      <div class="panel-h">
        <h2>Meta Ads — Weekly Detail</h2>
        <span class="sub">{ACCT['meta_account_name']} · Spend shaded by volume · ROAS shaded vs target {TH['roas_meta_min']:.2f}</span>
      </div>
      <div class="scroll">
        <table>
          <thead>
            <tr>
              <th>Week</th>
              <th>Amount Spent</th>
              <th>Purchases</th>
              <th>Revenue</th>
              <th>CPA</th>
              <th>ROAS</th>
              <th>Reach</th>
              <th>Impressions</th>
              <th>Clicks</th>
              <th>CPM</th>
              <th>CTR%</th>
              <th>CPC</th>
              <th>Frequency</th>
              <th>Hook Rate</th>
              <th>Hold Rate</th>
            </tr>
          </thead>
          <tbody>
            {''.join(meta_rows)}
          </tbody>
          <tfoot>
            <tr>
              <td>Last 12 Months</td>
              <td>{usd(meta_ttm['spend'])}</td>
              <td>{intf(meta_ttm['purchases'])}</td>
              <td>{usd(meta_ttm['revenue'])}</td>
              <td>{usd(meta_ttm['cpa'])}</td>
              <td class="{cls_thresh(meta_ttm['roas'], TH['roas_meta_min'])}">{num(meta_ttm['roas'])}</td>
              <td>—</td>
              <td>{intf(meta_ttm['impressions'])}</td>
              <td>{intf(meta_ttm['clicks'])}</td>
              <td>{num(meta_ttm['cpm'])}</td>
              <td>{num(meta_ttm['ctr'])}%</td>
              <td>{usd(meta_ttm['cpc'])}</td>
              <td>—</td>
              <td>{pct(meta_ttm['hook_rate'])}</td>
              <td>{pct(meta_ttm['hold_rate'])}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  </section>

  <!-- ============ GOOGLE ADS TAB ============ -->
  <section class="tab-panel" id="tab-google" role="tabpanel">
    <section class="kpis">
      <div class="kpi">
        <div class="label">Google · Latest Week Spend</div>
        <div class="value">{usd(google_spend)}</div>
        <div class="meta">{short_date(latest['week_start'])}</div>
      </div>
      <div class="kpi">
        <div class="label">Google · Latest Week ROAS</div>
        <div class="value" style="color:{'var(--lime)' if google_roas >= TH['roas_google_min'] else 'var(--bad)'}">{num(google_roas)}</div>
        <div class="meta">Target ≥ {TH['roas_google_min']:.0f} · Revenue {usd(google_revenue)}</div>
      </div>
      <div class="kpi accent">
        <div class="label">Google · Latest Week Conversions</div>
        <div class="value">{num(google_purchases, 1)}</div>
        <div class="meta">CPA {usd(latest_google.get('cpa'))}</div>
      </div>
      <div class="kpi">
        <div class="label">Google · Latest Week Revenue</div>
        <div class="value">{usd(google_revenue)}</div>
        <div class="meta">AOV {usd((google_revenue / google_purchases) if google_purchases else 0)} · ROAS {num(google_roas)}</div>
      </div>
    </section>

    <section class="panel">
      <div class="panel-h">
        <h2>Google Ads — Weekly Detail</h2>
        <span class="sub">{ACCT['google_account_name']} · Spend shaded by volume · ROAS shaded vs target {TH['roas_google_min']:.2f}</span>
      </div>
      <div class="scroll">
        <table>
          <thead>
            <tr>
              <th>Week</th>
              <th>Amount Spent</th>
              <th>Purchase</th>
              <th>Revenue</th>
              <th>CPA</th>
              <th>ROAS</th>
              <th>Impressions</th>
              <th>Clicks</th>
              <th>CPM</th>
              <th>CTR%</th>
              <th>CPC</th>
              <th>Impr. (Abs. top) %</th>
              <th>Impr. (Top) %</th>
              <th>Search lost IS (budget)</th>
              <th>Search lost IS (rank)</th>
            </tr>
          </thead>
          <tbody>
            {''.join(google_rows)}
          </tbody>
          <tfoot>
            <tr>
              <td>Last 12 Months</td>
              <td>{usd(google_ttm['spend'])}</td>
              <td>{num(google_ttm['purchases'], 1)}</td>
              <td>{usd(google_ttm['revenue'])}</td>
              <td>{usd(google_ttm['cpa'])}</td>
              <td class="{cls_thresh(google_ttm['roas'], TH['roas_google_min'])}">{num(google_ttm['roas'])}</td>
              <td>{intf(google_ttm['impressions'])}</td>
              <td>{intf(google_ttm['clicks'])}</td>
              <td>{num(google_ttm['cpm'])}</td>
              <td>{num(google_ttm['ctr'])}%</td>
              <td>{usd(google_ttm['cpc'])}</td>
              <td>—</td>
              <td>—</td>
              <td>—</td>
              <td>—</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  </section>

  <footer>Generated {DATA['generated_at']} · Source: GoMarble (Meta Graph API + Google Ads API)</footer>
</div>

<script>
  (function () {{
    const buttons = document.querySelectorAll(".tab-btn");
    const panels  = document.querySelectorAll(".tab-panel");
    function show(name) {{
      buttons.forEach(b => {{
        const on = b.dataset.tab === name;
        b.classList.toggle("active", on);
        b.setAttribute("aria-selected", on ? "true" : "false");
      }});
      panels.forEach(p => p.classList.toggle("active", p.id === "tab-" + name));
      if (history.replaceState) history.replaceState(null, "", "#" + name);
    }}
    buttons.forEach(b => b.addEventListener("click", () => show(b.dataset.tab)));
    const initial = (location.hash || "#meta").slice(1);
    if (["meta", "google", "overall"].includes(initial)) show(initial);
  }})();
</script>
</body>
</html>
"""

(ROOT / "index.html").write_text(HTML)
print(f"Wrote {ROOT / 'index.html'} ({len(HTML):,} chars)")
