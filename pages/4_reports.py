import streamlit as st
import streamlit.components.v1 as components
from auth import require_auth, get_user, clear_session, get_supabase
from db import load_reports, load_report_items, delete_report, DEFAULT_CATEGORY_COLORS
import json

st.set_page_config(page_title="Saved Reports — Expense AI", page_icon="💳", layout="wide")

# ── Shared dark theme CSS ──────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500;600&display=swap');
html, body, .stApp { font-family:'DM Sans',sans-serif; background:#0f0f13; color:#e8e6e1; }
section[data-testid="stSidebar"] { background:#17171d !important; border-right:1px solid #2a2a35; }
section[data-testid="stSidebar"] * { color:#c9c7c0 !important; }
#MainMenu { visibility:hidden; } footer { visibility:hidden; }
.stButton button {
    border-radius:8px !important; font-weight:500 !important; transition:all .15s !important;
}
.stButton button[kind="primary"] {
    background:#f0c040 !important; color:#0f0f13 !important; border:none !important;
}
</style>
""", unsafe_allow_html=True)

# ── Auth guard ─────────────────────────────────────────────────────────────────
require_auth()

user    = get_user()
uid     = user.id if hasattr(user, "id") else user.get("id") if user else None
email   = user.email if hasattr(user, "email") else user.get("email","") if user else ""

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 💳 Expense AI")
    st.markdown("---")
    st.markdown(f"<p style='color:#888;font-size:.8rem;margin-bottom:4px'>Signed in as</p>", unsafe_allow_html=True)
    st.markdown(f"<p style='color:#e8e6e1;font-size:.85rem;font-weight:500;word-break:break-all'>{email}</p>", unsafe_allow_html=True)
    st.markdown("---")
    if st.button("← Back to app", use_container_width=True):
        st.switch_page("frontend.py")
    if st.button("Sign out", use_container_width=True):
        try:
            get_supabase().auth.sign_out()
        except Exception:
            pass
        clear_session()
        st.switch_page("pages/1_login.py")

# ── Handle delete action from query params ─────────────────────────────────────
qp = st.query_params
if "delete_report" in qp:
    report_id = qp["delete_report"]
    ok, err = delete_report(report_id)
    st.query_params.clear()
    if ok:
        st.toast("Report deleted", icon="🗑️")
    else:
        st.toast(f"Could not delete: {err}", icon="⚠️")
    st.rerun()

# ── Load reports ───────────────────────────────────────────────────────────────
if not uid:
    st.warning("Please sign in to view saved reports.")
    st.stop()

reports = load_reports(uid)

# ── Header ─────────────────────────────────────────────────────────────────────
col_title, col_btn = st.columns([4, 1])
with col_title:
    st.markdown("## 📂 Saved Reports")
    if reports:
        st.caption(f"{len(reports)} report{'s' if len(reports)!=1 else ''}")
with col_btn:
    if st.button("＋ New analysis", type="primary", use_container_width=True):
        st.switch_page("frontend.py")

st.markdown("---")

# ── Empty state ────────────────────────────────────────────────────────────────
if not reports:
    st.markdown("""
    <div style="text-align:center;padding:4rem 1rem">
        <div style="font-size:2.5rem;margin-bottom:16px">📂</div>
        <p style="font-size:1.1rem;color:#e8e6e1;margin-bottom:8px">No saved reports yet</p>
        <p style="color:#666;font-size:.9rem">Upload a bank statement, categorize your expenses,<br>then save the report from Step 3.</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ── Report cards ───────────────────────────────────────────────────────────────
# We render each report as an interactive HTML component so the
# expand/collapse and table all live in one self-contained block.
# Delete is handled via query params (same pattern as the redaction tool).

CATEGORY_COLORS = DEFAULT_CATEGORY_COLORS

def amount_color(v):
    return "#f87171" if v < 0 else "#34d399"

def format_amount(v):
    sign = "−" if v < 0 else "+"
    return f"{sign}${abs(v):,.2f}"

def cat_pill(cat):
    color = CATEGORY_COLORS.get(cat, "#6b7280")
    return (f'<span style="display:inline-block;padding:2px 9px;border-radius:20px;'
            f'font-size:11px;background:{color}22;color:{color};border:1px solid {color}44">'
            f'{cat}</span>')

for report in reports:
    rid          = report["id"]
    label        = report["label"]
    period_start = report.get("period_start") or ""
    period_end   = report.get("period_end") or ""
    total_spend  = float(report.get("total_spend") or 0)
    total_income = float(report.get("total_income") or 0)
    created_at   = (report.get("created_at") or "")[:10]

    # Build period string
    period_str = ""
    if period_start and period_end:
        period_str = f"{period_start} – {period_end} · "
    elif period_start:
        period_str = f"From {period_start} · "

    # Load line items for this report
    items = load_report_items(rid)
    n_tx  = len(items)

    # Build transaction rows HTML
    tx_rows_html = ""
    for item in items:
        vendor  = item.get("vendor_name") or ""
        is_red  = item.get("is_redacted", False)
        amt     = float(item.get("amount") or 0)
        cat     = item.get("category","Unknown")
        date    = item.get("date","")

        vendor_cell = (
            '<span style="color:#555;font-style:italic">⬛ redacted</span>'
            if is_red else
            f'<span>{vendor}</span>'
        )
        tx_rows_html += f"""<tr>
            <td style="padding:7px 8px;border-bottom:1px solid #1e1e28;color:#aaa;
                       font-size:12px;white-space:nowrap">{date}</td>
            <td style="padding:7px 8px;border-bottom:1px solid #1e1e28">{vendor_cell}</td>
            <td style="padding:7px 8px;border-bottom:1px solid #1e1e28;
                       color:{amount_color(amt)};font-family:'DM Mono',monospace;
                       white-space:nowrap">{format_amount(amt)}</td>
            <td style="padding:7px 8px;border-bottom:1px solid #1e1e28">{cat_pill(cat)}</td>
        </tr>"""

    net        = total_income + total_spend   # spend is negative
    net_color  = "#34d399" if net >= 0 else "#f87171"
    net_sign   = "+" if net >= 0 else "−"

    card_html = f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500;600&display=swap');
  body {{ margin:0; padding:0; font-family:'DM Sans',sans-serif; background:transparent; }}
  .card {{ background:#1a1a24; border:1px solid #2a2a38; border-radius:12px; overflow:hidden; }}
  .card-header {{
    display:flex; justify-content:space-between; align-items:center;
    padding:16px 20px; cursor:pointer; user-select:none;
    transition:background .15s;
  }}
  .card-header:hover {{ background:#1e1e2e; }}
  .report-label {{ font-size:15px; font-weight:500; color:#e8e6e1; margin:0; }}
  .report-meta {{ font-size:12px; color:#555; margin:3px 0 0; }}
  .stats {{ display:flex; gap:28px; align-items:center; }}
  .stat {{ text-align:right; }}
  .stat-val {{ font-size:14px; font-weight:500; font-family:'DM Mono',monospace; }}
  .stat-lbl {{ font-size:10px; color:#555; margin-top:1px; letter-spacing:.04em; text-transform:uppercase; }}
  .chevron {{ color:#555; margin-left:16px; font-size:11px; transition:transform .2s; display:inline-block; }}
  .chevron.open {{ transform:rotate(180deg); }}
  .card-body {{ display:none; border-top:1px solid #1e1e28; padding:16px 20px; }}
  .card-body.open {{ display:block; }}
  .metric-grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:8px; margin-bottom:16px; }}
  .metric-pill {{ background:#0f0f13; border-radius:8px; padding:10px 12px; }}
  .metric-val {{ font-size:15px; font-weight:500; font-family:'DM Mono',monospace; }}
  .metric-lbl {{ font-size:10px; color:#555; margin-top:3px; text-transform:uppercase; letter-spacing:.04em; }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  th {{ color:#555; font-weight:400; text-align:left; padding:6px 8px;
        border-bottom:1px solid #2a2a38; font-size:10px; text-transform:uppercase; letter-spacing:.06em; }}
  .actions {{ display:flex; gap:8px; margin-top:14px; }}
  .del-btn {{
    background:transparent; border:1px solid #2a2a38; border-radius:8px;
    color:#666; font-size:12px; padding:6px 14px; cursor:pointer; font-family:'DM Sans',sans-serif;
    transition:all .15s;
  }}
  .del-btn:hover {{ border-color:#f87171; color:#f87171; background:#1f0f0f; }}
</style>

<div class="card">
  <div class="card-header" onclick="toggle('{rid}')">
    <div>
      <p class="report-label">{label}</p>
      <p class="report-meta">{period_str}saved {created_at}</p>
    </div>
    <div style="display:flex;align-items:center">
      <div class="stats">
        <div class="stat">
          <div class="stat-val" style="color:#f87171">${abs(total_spend):,.2f}</div>
          <div class="stat-lbl">spent</div>
        </div>
        <div class="stat">
          <div class="stat-val" style="color:#34d399">${total_income:,.2f}</div>
          <div class="stat-lbl">income</div>
        </div>
        <div class="stat">
          <div class="stat-val" style="color:#e8e6e1">{n_tx}</div>
          <div class="stat-lbl">transactions</div>
        </div>
      </div>
      <span class="chevron" id="chev-{rid}">▼</span>
    </div>
  </div>

  <div class="card-body" id="body-{rid}">
    <div class="metric-grid">
      <div class="metric-pill">
        <div class="metric-val" style="color:#f87171">${abs(total_spend):,.2f}</div>
        <div class="metric-lbl">Total spent</div>
      </div>
      <div class="metric-pill">
        <div class="metric-val" style="color:#34d399">${total_income:,.2f}</div>
        <div class="metric-lbl">Income</div>
      </div>
      <div class="metric-pill">
        <div class="metric-val" style="color:{net_color}">{net_sign}${abs(net):,.2f}</div>
        <div class="metric-lbl">Net</div>
      </div>
      <div class="metric-pill">
        <div class="metric-val" style="color:#e8e6e1">{n_tx}</div>
        <div class="metric-lbl">Transactions</div>
      </div>
    </div>

    <table>
      <thead><tr>
        <th style="width:12%">Date</th>
        <th style="width:36%">Merchant</th>
        <th style="width:15%">Amount</th>
        <th style="width:37%">Category</th>
      </tr></thead>
      <tbody>{tx_rows_html}</tbody>
    </table>

    <div class="actions">
      <button class="del-btn" onclick="confirmDelete('{rid}')">🗑 Delete report</button>
    </div>
  </div>
</div>

<script>
function toggle(id) {{
  const body = document.getElementById('body-' + id);
  const chev = document.getElementById('chev-' + id);
  const isOpen = body.classList.contains('open');
  body.classList.toggle('open', !isOpen);
  chev.classList.toggle('open', !isOpen);
}}

function confirmDelete(id) {{
  if (confirm('Delete this report? This cannot be undone.')) {{
    const url = new URL(window.parent.location.href);
    url.searchParams.set('delete_report', id);
    window.parent.location.href = url.toString();
  }}
}}
</script>
"""

    # Height: header (70) + body when open (metric grid ~80, table ~35*n_tx, actions ~50) + padding
    estimated_height = 80 + (n_tx * 38) + 180
    components.html(card_html, height=estimated_height, scrolling=False)
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
