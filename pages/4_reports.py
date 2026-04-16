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
.stButton button { border-radius:8px !important; font-weight:500 !important; transition:all .15s !important; }
.stButton button[kind="primary"] { background:#f0c040 !important; color:#0f0f13 !important; border:none !important; }

/* Style st.expander to match dark card theme */
div[data-testid="stExpander"] {
    background:#1a1a24 !important;
    border:1px solid #2a2a38 !important;
    border-radius:12px !important;
    margin-bottom:12px !important;
}
div[data-testid="stExpander"] summary {
    padding:6px 16px !important;
    background:#1a1a24 !important;
    border-radius:12px !important;
    color:#e8e6e1 !important;
}
div[data-testid="stExpander"] summary:hover {
    background:#1e1e2e !important;
}
div[data-testid="stExpander"] summary svg {
    color:#555 !important;
}
div[data-testid="stExpander"] > div:last-child {
    border-top:1px solid #2a2a38 !important;
    background:#1a1a24 !important;
    border-radius:0 0 12px 12px !important;
    padding:16px !important;
}
</style>
""", unsafe_allow_html=True)

require_auth()

user  = get_user()
uid   = user.id if hasattr(user,"id") else user.get("id") if user else None
email = user.email if hasattr(user,"email") else user.get("email","") if user else ""

with st.sidebar:
    if st.button("⌂ Home", use_container_width=True):
        st.switch_page("frontend.py")
    st.markdown("<div style='padding-top:20vh'>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

with st.sidebar.container(key="sidebar_bottom"):
    st.markdown(f"<p style='color:#888;font-size:.8rem;margin-bottom:2px'>Signed in as</p>",
                unsafe_allow_html=True)
    st.markdown(f"<p style='color:#e8e6e1;font-size:.85rem;font-weight:500;"
                f"word-break:break-all;margin-bottom:8px'>{email}</p>",
                unsafe_allow_html=True)
    if st.button("Sign out", use_container_width=True):
        try: get_supabase().auth.sign_out()
        except: pass
        clear_session()
        st.switch_page("pages/1_login.py")

st.html("""
<style>
  .st-key-sidebar_bottom {
    position: absolute;
    bottom: 16px;
    left: 0;
    right: 0;
    padding: 0 1rem;
  }
</style>
""")


if not uid:
    st.warning("Please sign in.")
    st.stop()

# ── Handle delete ──────────────────────────────────────────────────────────────
if "pending_delete_report" in st.session_state:
    rid = st.session_state.pop("pending_delete_report")
    ok, err = delete_report(rid)
    st.toast("Report deleted" if ok else f"Error: {err}",
             icon="🗑️" if ok else "⚠️")
    st.rerun()

reports = load_reports(uid)

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
    </div>""", unsafe_allow_html=True)
    st.stop()

CATEGORY_COLORS = DEFAULT_CATEGORY_COLORS

def cat_pill(cat):
    color = CATEGORY_COLORS.get(cat, "#6b7280")
    return (f'<span style="display:inline-block;padding:2px 9px;border-radius:20px;font-size:11px;'
            f'background:{color}22;color:{color};border:1px solid {color}44">{cat}</span>')

def fmt(v):
    return f"{'−' if v<0 else '+'}${abs(v):,.2f}"

def acol(v):
    return "#f87171" if v < 0 else "#34d399"

# ── Render each report as a styled st.expander ─────────────────────────────────
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
        period_str = f"{period_start} – {period_end}"
    elif period_start:
        period_str = f"From {period_start}"

    items = load_report_items(rid)
    n_tx  = len(items)

    # Build expander label — shows label + key stats always visible
    expander_label = (
        f"**{label}**"
        f"{'  ·  ' + period_str if period_str else ''}"
        f"  ·  saved {created_at}"
    )

    with st.expander(expander_label, expanded=False):

        # ── Summary metrics (visible in the collapsed preview area) ────────────
        # These sit at the top of the expander body, seen first when opened.
        # We show them here AND replicate the key numbers in the label above
        # so the card is informative both collapsed and expanded.
        st.markdown(f"""
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:20px">
          <div style="background:#0f0f13;border-radius:8px;padding:12px 14px">
            <div style="font-size:16px;font-weight:500;color:#f87171;font-family:'DM Mono',monospace">${abs(total_spend):,.2f}</div>
            <div style="font-size:10px;color:#555;margin-top:4px;text-transform:uppercase;letter-spacing:.05em">Total spent</div>
          </div>
          <div style="background:#0f0f13;border-radius:8px;padding:12px 14px">
            <div style="font-size:16px;font-weight:500;color:#34d399;font-family:'DM Mono',monospace">${total_income:,.2f}</div>
            <div style="font-size:10px;color:#555;margin-top:4px;text-transform:uppercase;letter-spacing:.05em">Income</div>
          </div>
          <div style="background:#0f0f13;border-radius:8px;padding:12px 14px">
            <div style="font-size:16px;font-weight:500;color:{net_color};font-family:'DM Mono',monospace">{net_sign}${abs(net):,.2f}</div>
            <div style="font-size:10px;color:#555;margin-top:4px;text-transform:uppercase;letter-spacing:.05em">Net</div>
          </div>
          <div style="background:#0f0f13;border-radius:8px;padding:12px 14px">
            <div style="font-size:16px;font-weight:500;color:#e8e6e1;font-family:'DM Mono',monospace">{n_tx}</div>
            <div style="font-size:10px;color:#555;margin-top:4px;text-transform:uppercase;letter-spacing:.05em">Transactions</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # ── Transaction table — built in one pass, rendered in one call ─────────
        th = "color:#555;font-weight:400;text-align:left;padding:6px 10px;border-bottom:1px solid #2a2a38;font-size:10px;text-transform:uppercase;letter-spacing:.06em"
        rows_html = ""
        for item in items:
            vendor = item.get("vendor_name") or ""
            is_red = item.get("is_redacted", False)
            amt    = float(item.get("amount") or 0)
            cat    = item.get("category","Unknown")
            date   = item.get("date","")
            v_cell = '<i style="color:#444">⬛ redacted</i>' if is_red else vendor
            rows_html += f"""<tr>
              <td style="padding:8px 10px;border-bottom:1px solid #1e1e28;color:#888;font-size:12px;white-space:nowrap">{date}</td>
              <td style="padding:8px 10px;border-bottom:1px solid #1e1e28;color:#e8e6e1">{v_cell}</td>
              <td style="padding:8px 10px;border-bottom:1px solid #1e1e28;color:{acol(amt)};font-family:'DM Mono',monospace;white-space:nowrap">{fmt(amt)}</td>
              <td style="padding:8px 10px;border-bottom:1px solid #1e1e28">{cat_pill(cat)}</td>
            </tr>"""

        st.markdown(f"""
        <table style="width:100%;border-collapse:collapse;font-size:13px">
          <thead><tr>
            <th style="{th};width:12%">Date</th>
            <th style="{th};width:38%">Merchant</th>
            <th style="{th};width:15%">Amount</th>
            <th style="{th}">Category</th>
          </tr></thead>
          <tbody>{rows_html}</tbody>
        </table>""", unsafe_allow_html=True)

        # ── Delete button — inside expander, full native Streamlit ─────────────
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        _, del_col = st.columns([4, 1])
        with del_col:
            def _make_cb(r):
                def _cb():
                    st.session_state.pending_delete_report = r
                return _cb
            st.button("🗑 Delete report", key=f"del_{rid}",
                      on_click=_make_cb(rid),
                      use_container_width=True)
