import streamlit as st
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

.stButton button {
    border-radius:8px !important; font-weight:500 !important; transition:all .15s !important;
}
.stButton button[kind="primary"] {
    background:#f0c040 !important; color:#0f0f13 !important; border:none !important;
}

/* Report card header */
.rcard {
    background:#1a1a24; border:1px solid #2a2a38; border-radius:12px;
    padding:16px 20px; margin-bottom:2px;
}
.rcard-body {
    background:#1a1a24; border:1px solid #2a2a38; border-top:none;
    border-radius:0 0 12px 12px; padding:16px 20px; margin-bottom:10px;
}
.rcard-label { font-size:15px; font-weight:500; color:#e8e6e1; margin:0; }
.rcard-meta  { font-size:12px; color:#555; margin:3px 0 0; }
.stat-val    { font-size:14px; font-weight:500; font-family:'DM Mono',monospace; }
.stat-lbl    { font-size:10px; color:#555; text-transform:uppercase; letter-spacing:.04em; }

.metric-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:8px; margin-bottom:16px; }
.metric-pill { background:#0f0f13; border-radius:8px; padding:10px 12px; }
.metric-val  { font-size:15px; font-weight:500; font-family:'DM Mono',monospace; }
.metric-lbl  { font-size:10px; color:#555; margin-top:3px; text-transform:uppercase; letter-spacing:.04em; }

.tx-table { width:100%; border-collapse:collapse; font-size:13px; }
.tx-table th {
    color:#555; font-weight:400; text-align:left; padding:6px 8px;
    border-bottom:1px solid #2a2a38; font-size:10px;
    text-transform:uppercase; letter-spacing:.06em;
}
.tx-table td { padding:7px 8px; border-bottom:1px solid #1e1e28; color:#e8e6e1; }
.tx-table tr:last-child td { border-bottom:none; }

/* Override Streamlit button styles for toggle and delete */
div[data-testid="stHorizontalBlock"] .stButton button {
    font-size:13px !important;
}
</style>
""", unsafe_allow_html=True)

require_auth()

user  = get_user()
uid   = user.id if hasattr(user,"id") else user.get("id") if user else None
email = user.email if hasattr(user,"email") else user.get("email","") if user else ""

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 💳 Expense AI")
    st.markdown("---")
    st.markdown(f"<p style='color:#888;font-size:.8rem;margin-bottom:4px'>Signed in as</p>",
                unsafe_allow_html=True)
    st.markdown(f"<p style='color:#e8e6e1;font-size:.85rem;font-weight:500'>{email}</p>",
                unsafe_allow_html=True)
    st.markdown("---")
    if st.button("← Back to app", use_container_width=True):
        st.switch_page("frontend.py")
    if st.button("Sign out", use_container_width=True):
        try: get_supabase().auth.sign_out()
        except: pass
        clear_session()
        st.switch_page("pages/1_login.py")

if not uid:
    st.warning("Please sign in.")
    st.stop()

# ── Session state ──────────────────────────────────────────────────────────────
if "expanded_reports" not in st.session_state:
    st.session_state.expanded_reports = set()

# ── Handle pending delete ──────────────────────────────────────────────────────
if "pending_delete_report" in st.session_state:
    rid = st.session_state.pop("pending_delete_report")
    st.session_state.expanded_reports.discard(rid)
    ok, err = delete_report(rid)
    st.toast("Report deleted" if ok else f"Error: {err}",
             icon="🗑️" if ok else "⚠️")
    st.rerun()

# ── Load data ──────────────────────────────────────────────────────────────────
reports = load_reports(uid)

# ── Header ─────────────────────────────────────────────────────────────────────
c1, c2 = st.columns([4, 1])
with c1:
    st.markdown("## 📂 Saved Reports")
    if reports:
        st.caption(f"{len(reports)} report{'s' if len(reports)!=1 else ''}")
with c2:
    if st.button("＋ New analysis", type="primary", use_container_width=True):
        st.switch_page("frontend.py")

st.markdown("---")

if not reports:
    st.markdown("""
    <div style="text-align:center;padding:4rem 1rem">
        <div style="font-size:2.5rem;margin-bottom:16px">📂</div>
        <p style="font-size:1.1rem;color:#e8e6e1;margin-bottom:8px">No saved reports yet</p>
        <p style="color:#666;font-size:.9rem">Upload a bank statement, categorize your expenses,
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
    return f"{'−' if v<0 else '+'}${abs(v):,.2f}"

def acol(v):
    return "#f87171" if v < 0 else "#34d399"

# ── Render cards ───────────────────────────────────────────────────────────────
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
    is_open      = rid in st.session_state.expanded_reports

    period_str = ""
    if period_start and period_end:
        period_str = f"{period_start} – {period_end} · "
    elif period_start:
        period_str = f"From {period_start} · "

    items = load_report_items(rid)
    n_tx  = len(items)

    # ── Card header ────────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="rcard" style="border-radius:{'12px 12px 0 0' if is_open else '12px'}">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <div>
          <div class="rcard-label">{label}</div>
          <div class="rcard-meta">{period_str}saved {created_at}</div>
        </div>
        <div style="display:flex;gap:24px;align-items:center">
          <div style="text-align:right">
            <div class="stat-val" style="color:#f87171">${abs(total_spend):,.2f}</div>
            <div class="stat-lbl">spent</div>
          </div>
          <div style="text-align:right">
            <div class="stat-val" style="color:#34d399">${total_income:,.2f}</div>
            <div class="stat-lbl">income</div>
          </div>
          <div style="text-align:right">
            <div class="stat-val" style="color:#e8e6e1">{n_tx}</div>
            <div class="stat-lbl">transactions</div>
          </div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Toggle + delete buttons sit below the card header
    btn_expand = "▲ Collapse" if is_open else "▼ Show details"

    def _make_toggle_cb(report_id, currently_open):
        def _cb():
            if currently_open:
                st.session_state.expanded_reports.discard(report_id)
            else:
                st.session_state.expanded_reports.add(report_id)
        return _cb

    def _make_delete_cb(report_id):
        def _cb():
            st.session_state.pending_delete_report = report_id
        return _cb

    bc1, bc2, bc3 = st.columns([3, 1, 1])
    with bc2:
        st.button(btn_expand, key=f"tog_{rid}",
                  on_click=_make_toggle_cb(rid, is_open),
                  use_container_width=True)
    with bc3:
        st.button("🗑 Delete", key=f"del_{rid}",
                  on_click=_make_delete_cb(rid),
                  use_container_width=True)

    # ── Expanded body ──────────────────────────────────────────────────────────
    if is_open:
        # Metric grid
        st.markdown(f"""
        <div class="rcard-body">
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

          <table class="tx-table">
            <thead><tr>
              <th style="width:12%">Date</th>
              <th style="width:36%">Merchant</th>
              <th style="width:15%">Amount</th>
              <th>Category</th>
            </tr></thead>
            <tbody>
        """, unsafe_allow_html=True)

        # Transaction rows
        rows_html = ""
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
            rows_html += f"""<tr>
              <td>{date}</td>
              <td>{vendor_cell}</td>
              <td style="color:{acol(amt)};font-family:'DM Mono',monospace">{fmt(amt)}</td>
              <td>{cat_pill(cat)}</td>
            </tr>"""

        st.markdown(rows_html + """
            </tbody></table>
          </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
