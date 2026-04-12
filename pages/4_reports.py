import streamlit as st
import streamlit.components.v1 as components
from auth import require_auth, get_user, clear_session, get_supabase
from db import load_reports, load_report_items, delete_report, DEFAULT_CATEGORY_COLORS

st.set_page_config(page_title="Saved Reports — Expense AI", page_icon="💳", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500;600&display=swap');
html, body, .stApp { font-family:'DM Sans',sans-serif; background:#0f0f13; color:#e8e6e1; }
section[data-testid="stSidebar"] { background:#17171d !important; border-right:1px solid #2a2a35; }
section[data-testid="stSidebar"] * { color:#c9c7c0 !important; }
#MainMenu { visibility:hidden; } footer { visibility:hidden; }
.stButton button { border-radius:8px !important; font-weight:500 !important; transition:all .15s !important; }
.stButton button[kind="primary"] { background:#f0c040 !important; color:#0f0f13 !important; border:none !important; }
</style>
""", unsafe_allow_html=True)

require_auth()

user  = get_user()
uid   = user.id if hasattr(user, "id") else user.get("id") if user else None
email = user.email if hasattr(user, "email") else user.get("email","") if user else ""

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

if not uid:
    st.warning("Please sign in to view saved reports.")
    st.stop()

# ── Handle delete via query params ─────────────────────────────────────────────
qp = st.query_params
if "delete_report" in qp:
    rid_to_delete = qp["delete_report"]
    st.query_params.clear()
    ok, err = delete_report(rid_to_delete)
    st.toast("Report deleted" if ok else f"Error: {err}", icon="🗑️" if ok else "⚠️")
    st.rerun()

reports = load_reports(uid)

col_title, col_btn = st.columns([4, 1])
with col_title:
    st.markdown("## 📂 Saved Reports")
    if reports:
        st.caption(f"{len(reports)} report{'s' if len(reports)!=1 else ''}")
with col_btn:
    if st.button("＋ New analysis", type="primary", use_container_width=True):
        st.switch_page("frontend.py")

st.markdown("---")

if not reports:
    st.markdown("""
    <div style="text-align:center;padding:4rem 1rem">
        <div style="font-size:2.5rem;margin-bottom:16px">📂</div>
        <p style="font-size:1.1rem;color:#e8e6e1;margin-bottom:8px">No saved reports yet</p>
        <p style="color:#666;font-size:.9rem">Upload a bank statement, categorize your expenses,<br>
        then save the report from Step 3.</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

CATEGORY_COLORS = DEFAULT_CATEGORY_COLORS

def cat_pill(cat):
    color = CATEGORY_COLORS.get(cat, "#6b7280")
    return (f'<span style="display:inline-block;padding:2px 9px;border-radius:20px;'
            f'font-size:11px;background:{color}22;color:{color};border:1px solid {color}44">'
            f'{cat}</span>')

def fmt(v):
    sign = "−" if v < 0 else "+"
    return f"{sign}${abs(v):,.2f}"

def acol(v):
    return "#f87171" if v < 0 else "#34d399"

# ── Render all reports as one big HTML block ───────────────────────────────────
# Rendering everything in a single components.html call means:
# - One fixed height we can calculate accurately upfront
# - No iframe-to-parent communication needed for expand/collapse
# - Delete uses window.parent.location which reliably triggers Streamlit rerun

all_cards_html = ""
total_height   = 0

for report in reports:
    rid          = report["id"]
    label        = report["label"]
    period_start = report.get("period_start") or ""
    period_end   = report.get("period_end") or ""
    total_spend  = float(report.get("total_spend") or 0)
    total_income = float(report.get("total_income") or 0)
    created_at   = (report.get("created_at") or "")[:10]
    net          = total_income + total_spend
    net_color    = "#34d399" if net >= 0 else "#f87171"
    net_sign     = "+" if net >= 0 else "−"

    period_str = ""
    if period_start and period_end:
        period_str = f"{period_start} – {period_end} · "
    elif period_start:
        period_str = f"From {period_start} · "

    items = load_report_items(rid)
    n_tx  = len(items)

    tx_rows_html = ""
    for item in items:
        vendor  = item.get("vendor_name") or ""
        is_red  = item.get("is_redacted", False)
        amt     = float(item.get("amount") or 0)
        cat     = item.get("category", "Unknown")
        date    = item.get("date", "")
        vendor_cell = (
            '<span style="color:#444;font-style:italic">⬛ redacted</span>'
            if is_red else vendor
        )
        tx_rows_html += f"""<tr>
          <td class="td">{date}</td>
          <td class="td">{vendor_cell}</td>
          <td class="td" style="color:{acol(amt)};font-family:'DM Mono',monospace">{fmt(amt)}</td>
          <td class="td">{cat_pill(cat)}</td>
        </tr>"""

    # Card height: header=72, metric grid=100, table header=32, rows=38each, actions=52, padding=32
    card_collapsed_h = 76
    card_expanded_h  = card_collapsed_h + 100 + 32 + (n_tx * 38) + 52 + 32
    total_height    += card_collapsed_h + 12  # start collapsed + gap

    all_cards_html += f"""
<div class="card" id="card-{rid}">
  <div class="hdr" onclick="toggle('{rid}', {card_expanded_h})">
    <div>
      <div class="lbl">{label}</div>
      <div class="meta">{period_str}saved {created_at}</div>
    </div>
    <div style="display:flex;align-items:center">
      <div class="stats">
        <div class="stat">
          <div class="sv" style="color:#f87171">${abs(total_spend):,.2f}</div>
          <div class="sl">spent</div>
        </div>
        <div class="stat">
          <div class="sv" style="color:#34d399">${total_income:,.2f}</div>
          <div class="sl">income</div>
        </div>
        <div class="stat">
          <div class="sv" style="color:#e8e6e1">{n_tx}</div>
          <div class="sl">transactions</div>
        </div>
      </div>
      <span class="chev" id="chev-{rid}">▼</span>
    </div>
  </div>

  <div class="body" id="body-{rid}">
    <div class="mgs">
      <div class="mp"><div class="mv" style="color:#f87171">${abs(total_spend):,.2f}</div><div class="ml">Total spent</div></div>
      <div class="mp"><div class="mv" style="color:#34d399">${total_income:,.2f}</div><div class="ml">Income</div></div>
      <div class="mp"><div class="mv" style="color:{net_color}">{net_sign}${abs(net):,.2f}</div><div class="ml">Net</div></div>
      <div class="mp"><div class="mv" style="color:#e8e6e1">{n_tx}</div><div class="ml">Transactions</div></div>
    </div>
    <table>
      <thead><tr>
        <th style="width:12%">Date</th>
        <th style="width:36%">Merchant</th>
        <th style="width:15%">Amount</th>
        <th>Category</th>
      </tr></thead>
      <tbody>{tx_rows_html}</tbody>
    </table>
    <div class="actions">
      <button class="del-btn" onclick="delReport('{rid}')">🗑 Delete report</button>
    </div>
  </div>
</div>
<div style="height:10px"></div>
"""

page_html = f"""<!DOCTYPE html><html><head>
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500;600&display=swap');
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'DM Sans',sans-serif;background:transparent}}
.card{{background:#1a1a24;border:1px solid #2a2a38;border-radius:12px;overflow:hidden;
       transition:all .2s}}
.hdr{{display:flex;justify-content:space-between;align-items:center;
      padding:16px 20px;cursor:pointer;user-select:none;min-height:72px;transition:background .15s}}
.hdr:hover{{background:#1e1e2e}}
.lbl{{font-size:15px;font-weight:500;color:#e8e6e1}}
.meta{{font-size:12px;color:#555;margin-top:3px}}
.stats{{display:flex;gap:24px;align-items:center}}
.stat{{text-align:right}}
.sv{{font-size:14px;font-weight:500;font-family:'DM Mono',monospace}}
.sl{{font-size:10px;color:#555;margin-top:1px;text-transform:uppercase;letter-spacing:.04em}}
.chev{{color:#555;margin-left:14px;font-size:11px;transition:transform .25s;display:inline-block}}
.chev.open{{transform:rotate(180deg)}}
.body{{display:none;border-top:1px solid #1e1e28;padding:16px 20px}}
.body.open{{display:block}}
.mgs{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:16px}}
.mp{{background:#0f0f13;border-radius:8px;padding:10px 12px}}
.mv{{font-size:15px;font-weight:500;font-family:'DM Mono',monospace}}
.ml{{font-size:10px;color:#555;margin-top:3px;text-transform:uppercase;letter-spacing:.04em}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{color:#555;font-weight:400;text-align:left;padding:6px 8px;
    border-bottom:1px solid #2a2a38;font-size:10px;text-transform:uppercase;letter-spacing:.06em}}
.td{{padding:7px 8px;border-bottom:1px solid #1e1e28;color:#e8e6e1}}
tr:last-child .td{{border-bottom:none}}
.actions{{display:flex;gap:8px;margin-top:14px}}
.del-btn{{background:transparent;border:1px solid #2a2a38;border-radius:8px;
          color:#666;font-size:12px;padding:6px 14px;cursor:pointer;
          font-family:'DM Sans',sans-serif;transition:all .15s}}
.del-btn:hover{{border-color:#f87171;color:#f87171;background:#1f0f0f}}
</style>
</head><body>
{all_cards_html}
<script>
var heights = {{}};

function toggle(id, expandedH) {{
  var body = document.getElementById('body-' + id);
  var chev = document.getElementById('chev-' + id);
  var card = document.getElementById('card-' + id);
  var isOpen = body.classList.contains('open');
  body.classList.toggle('open', !isOpen);
  chev.classList.toggle('open', !isOpen);
  heights[id] = !isOpen;
  updateFrameHeight();
}}

function updateFrameHeight() {{
  var total = 0;
  document.querySelectorAll('.card').forEach(function(card) {{
    total += card.scrollHeight + 10;
  }});
  window.parent.postMessage({{
    isStreamlitMessage: true,
    type: 'streamlit:setFrameHeight',
    height: total + 20
  }}, '*');
}}

function delReport(id) {{
  if (confirm('Delete this report? This cannot be undone.')) {{
    var url = new URL(window.parent.location.href);
    url.searchParams.set('delete_report', id);
    window.parent.location.href = url.toString();
  }}
}}

// Set initial height after render
window.addEventListener('load', function() {{
  updateFrameHeight();
}});
</script>
</body></html>"""

# Render everything in ONE iframe — height starts at collapsed total
# JS will adjust after any toggle
components.html(page_html, height=total_height + 40, scrolling=True)
