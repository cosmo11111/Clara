import streamlit as st
import plotly.graph_objects as go
from auth import require_auth, get_user, clear_session, get_supabase
from db import (load_reports, load_report_items, delete_report,
                DEFAULT_CATEGORY_COLORS, get_profile, TIER_LABELS)

st.set_page_config(page_title="Saved Reports — Categoriz", page_icon="💳", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500;600&display=swap');
html, body, .stApp { font-family:'DM Sans',sans-serif; background:#0f0f13; color:#e8e6e1; }
section[data-testid="stSidebar"] { background:#17171d !important; border-right:1px solid #2a2a35; }
section[data-testid="stSidebar"] * { color:#c9c7c0 !important; }
section[data-testid="stSidebar"] button[kind="primary"] { color: #0f0f13 !important; }
section[data-testid="stSidebar"] button[kind="primary"] * { color: #0f0f13 !important; }
#MainMenu { visibility:hidden; } footer { visibility:hidden; }
[data-testid="stHeader"] { display: none !important; }
[data-testid="stSidebarHeader"] { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }
.block-container { padding-top: 1rem !important; }
section[data-testid="stSidebar"] > div { padding-top: 1rem !important; overflow: hidden !important; }
.stButton button { border-radius:8px !important; font-weight:500 !important; transition:all .15s !important; }
.stButton button[kind="primary"] { background:#f0c040 !important; color:#0f0f13 !important; border:none !important; }
div[data-testid="stExpander"] {
    background:#1a1a24 !important; border:1px solid #2a2a38 !important;
    border-radius:12px !important; margin-bottom:12px !important;
}
div[data-testid="stExpander"] summary {
    padding:6px 16px !important; background:#1a1a24 !important;
    border-radius:12px !important; color:#e8e6e1 !important;
}
div[data-testid="stExpander"] summary:hover { background:#1e1e2e !important; }
div[data-testid="stExpander"] summary svg { color:#555 !important; }
div[data-testid="stExpander"] > div:last-child {
    border-top:1px solid #2a2a38 !important; background:#1a1a24 !important;
    border-radius:0 0 12px 12px !important; padding:16px !important;
}
[data-testid="stSidebarNav"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

require_auth()

user  = get_user()
uid   = user.id if hasattr(user,"id") else user.get("id") if user else None
email = user.email if hasattr(user,"email") else user.get("email","") if user else ""

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    if st.button("⌂ Home", use_container_width=True):
        st.switch_page("frontend.py")
    st.markdown("<div style='padding-top:1rem'>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

profile    = get_profile(uid) if uid else {}
tier       = profile.get("subscription_tier", "free_trial")
used       = profile.get("analyses_used", 0)
limit      = profile.get("analyses_limit", 3)
tier_label = TIER_LABELS.get(tier, "Free Trial")
TIER_COLORS = {"free_trial":"#666","starter":"#3b82f6","unlimited":"#f0c040"}
tier_color  = TIER_COLORS.get(tier, "#666")
usage_str   = "Unlimited analyses" if tier=="unlimited" else \
              f"{used}/3 lifetime analyses" if tier=="free_trial" else \
              f"{used}/{limit} analyses this month"

with st.sidebar.container(key="sidebar_bottom"):
    st.markdown(f"<p style='color:#888;font-size:.8rem;margin-bottom:2px'>Signed in as</p>",
                unsafe_allow_html=True)
    st.markdown(f"<p style='color:#e8e6e1;font-size:.85rem;font-weight:500;"
                f"word-break:break-all;margin-bottom:8px'>{email}</p>",
                unsafe_allow_html=True)
    st.markdown(f"""
    <div style="background:#1a1a24;border:1px solid #2a2a38;border-radius:8px;
                padding:8px 12px;margin-bottom:10px">
      <span style="font-size:11px;font-weight:600;color:#e8e6e1;
                   text-transform:uppercase;letter-spacing:.05em">{tier_label}</span>
      <div style="font-size:11px;color:#555;margin-top:2px">{usage_str}</div>
    </div>
    """, unsafe_allow_html=True)
    if tier == "free_trial":
        if st.button("⚡ Upgrade plan", use_container_width=True, type="primary"):
            st.switch_page("pages/5_pricing.py")
    elif tier == "starter":
        if st.button("⚡ Upgrade to Unlimited", use_container_width=True, type="primary"):
            st.switch_page("pages/5_pricing.py")
    else:
        if st.button("⚡ Manage plan", use_container_width=True, type="primary"):
            st.switch_page("pages/5_pricing.py")
    if st.button("Sign out", use_container_width=True):
        try: get_supabase().auth.sign_out()
        except: pass
        clear_session()
        st.switch_page("pages/1_login.py")

st.html("""
<style>
  .st-key-sidebar_bottom {
    position: absolute; bottom: 16px; left: 0; right: 0; padding: 0 1rem;
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

# ── Handle "view full report" ──────────────────────────────────────────────────
if st.session_state.get("_view_report_id"):
    rid = st.session_state.pop("_view_report_id")
    items = load_report_items(rid)
    if items:
        transactions = []
        for it in items:
            transactions.append({
                "date":         it.get("date", ""),
                "name":         it.get("vendor_name") or it.get("vendor_name_clean") or "",
                "vendor_clean": it.get("vendor_name_clean") or it.get("vendor_name") or "",
                "amount":       float(it.get("amount") or 0),
                "category":     it.get("category", "Unknown"),
            })
        st.session_state.transactions    = transactions
        st.session_state.categorized     = True
        st.session_state.step            = 3
        st.session_state.tx_rows         = None
        st.session_state.tx_rows_source  = None
        st.session_state.redacted_pdf_bytes = None
        st.switch_page("frontend.py")

reports = load_reports(uid)
CATEGORY_COLORS = DEFAULT_CATEGORY_COLORS
is_paid = tier in ("starter", "unlimited")

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="padding:4px 0 8px">
  <span style="font-family:'DM Sans',sans-serif;font-size:1.2rem;font-weight:700;
               font-style:italic;color:#f0c040;letter-spacing:.04em">CATEGORIZ</span>
</div>
""", unsafe_allow_html=True)

c1, c2 = st.columns([4, 1])
with c1:
    st.markdown("## Saved Reports")
    if reports:
        st.caption(f"{len(reports)} report{'s' if len(reports)!=1 else ''}")
with c2:
    if st.button("＋ New analysis", type="primary", use_container_width=True):
        st.switch_page("frontend.py")

if not reports:
    st.markdown("""
    <div style="text-align:center;padding:4rem 1rem">
        <div style="font-size:2.5rem;margin-bottom:16px">📂</div>
        <p style="font-size:1.1rem;color:#e8e6e1;margin-bottom:8px">No saved reports yet</p>
        <p style="color:#666;font-size:.9rem">Upload a bank statement, categorize your expenses,
        then save the report from the results page.</p>
    </div>""", unsafe_allow_html=True)
    st.stop()

# ── Historical bar chart ───────────────────────────────────────────────────────
from collections import defaultdict
month_data: dict = defaultdict(lambda: defaultdict(float))

for r in reports:
    mt = r.get("monthly_totals") or {}
    for month, cats in mt.items():
        for cat, amt in cats.items():
            month_data[month][cat] += amt

if month_data:
    months_sorted = sorted(month_data.keys())
    all_cats = sorted({cat for m in month_data.values() for cat in m})

    fig = go.Figure()
    for cat in all_cats:
        fig.add_trace(go.Bar(
            name=cat,
            x=months_sorted,
            y=[month_data[m].get(cat, 0) for m in months_sorted],
            marker_color=CATEGORY_COLORS.get(cat, "#6b7280"),
            hovertemplate=f"<b>{cat}</b><br>$%{{y:,.2f}}<extra></extra>",
        ))

    fig.update_layout(
        barmode="stack",
        height=280,
        margin=dict(l=0, r=0, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#c9c7c0", size=11, family="DM Sans"),
        showlegend=True,
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            xanchor="left", x=0, font=dict(size=10),
        ),
        xaxis=dict(gridcolor="#1e1e28", tickfont=dict(size=10), linecolor="#2a2a38"),
        yaxis=dict(gridcolor="#1e1e28", tickprefix="$", tickfont=dict(size=10)),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.markdown("---")

# ── Report cards ───────────────────────────────────────────────────────────────
for report in reports:
    rid           = report["id"]
    label         = report["label"]
    period_start  = report.get("period_start") or ""
    period_end    = report.get("period_end") or ""
    total_spend   = float(report.get("total_spend") or 0)
    total_income  = float(report.get("total_income") or 0)
    tx_count      = report.get("transaction_count") or 0
    top_vendors   = report.get("top_vendors") or []
    tier_required = report.get("tier_required", "starter")
    can_view      = is_paid

    period_str = ""
    if period_start and period_end:
        period_str = f"{period_start[:10]} – {period_end[:10]}"
    elif period_start:
        period_str = period_start[:10]

    expander_label = (
        f"**{label}**"
        f"{'  ·  ' + period_str if period_str else ''}"
    )

    with st.expander(expander_label, expanded=False):

        # 3 metric tiles
        st.markdown(f"""
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:20px">
          <div style="background:#0f0f13;border-radius:8px;padding:12px 14px">
            <div style="font-size:16px;font-weight:500;color:#f87171;
                        font-family:'DM Mono',monospace">${abs(total_spend):,.2f}</div>
            <div style="font-size:10px;color:#555;margin-top:4px;
                        text-transform:uppercase;letter-spacing:.05em">Total spent</div>
          </div>
          <div style="background:#0f0f13;border-radius:8px;padding:12px 14px">
            <div style="font-size:16px;font-weight:500;color:#34d399;
                        font-family:'DM Mono',monospace">${total_income:,.2f}</div>
            <div style="font-size:10px;color:#555;margin-top:4px;
                        text-transform:uppercase;letter-spacing:.05em">Income</div>
          </div>
          <div style="background:#0f0f13;border-radius:8px;padding:12px 14px">
            <div style="font-size:16px;font-weight:500;color:#e8e6e1;
                        font-family:'DM Mono',monospace">{tx_count}</div>
            <div style="font-size:10px;color:#555;margin-top:4px;
                        text-transform:uppercase;letter-spacing:.05em">Transactions</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # Top 3 vendors
        if top_vendors:
            max_amt = max(v.get("amount", 0) for v in top_vendors) or 1
            vendor_html = ""
            for v in top_vendors[:3]:
                vname   = v.get("vendor", "Unknown")
                vamt    = float(v.get("amount", 0))
                vcat    = v.get("category", "Unknown")
                bar_pct = int(vamt / max_amt * 100)
                color   = CATEGORY_COLORS.get(vcat, "#6b7280")
                vendor_html += f"""
                <div style="padding:8px 0;border-bottom:1px solid #1e1e28">
                  <div style="display:flex;justify-content:space-between;
                              align-items:baseline;margin-bottom:4px">
                    <span style="font-size:.85rem;color:#e8e6e1">{vname}</span>
                    <span style="font-size:.85rem;font-weight:500;color:#e8e6e1;
                                 font-family:'DM Mono',monospace">${vamt:,.2f}</span>
                  </div>
                  <div style="background:#1e1e28;border-radius:3px;height:3px">
                    <div style="width:{bar_pct}%;height:3px;border-radius:3px;
                                background:{color}"></div>
                  </div>
                </div>"""
            st.markdown(f"""
            <p style="font-size:.75rem;color:#555;text-transform:uppercase;
                      letter-spacing:.06em;margin:0 0 6px">Top vendors</p>
            {vendor_html}
            """, unsafe_allow_html=True)

        # View full report + Delete
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        btn_col1, btn_col2 = st.columns([3, 1])

        with btn_col1:
            if can_view:
                if st.button("View full report →", key=f"view_{rid}",
                             type="primary", use_container_width=True):
                    st.session_state._view_report_id = rid
                    st.rerun()
            else:
                st.markdown(
                    "<div style='padding:8px 12px;border:1px solid #2a2a38;"
                    "border-radius:8px;font-size:.85rem;color:#555;"
                    "text-align:center'>🔒 Upgrade to Starter to view full report</div>",
                    unsafe_allow_html=True
                )

        with btn_col2:
            def _make_cb(r):
                def _cb(): st.session_state.pending_delete_report = r
                return _cb
            st.button("🗑 Delete", key=f"del_{rid}",
                      on_click=_make_cb(rid),
                      use_container_width=True)
