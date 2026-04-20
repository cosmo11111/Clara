import streamlit as st
import plotly.graph_objects as go
from auth import require_auth, get_user, clear_session, get_supabase
from db import (load_reports, load_report_items, delete_report,
                DEFAULT_CATEGORY_COLORS, get_profile, TIER_LABELS)


st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500&display=swap');
html, body, .stApp { font-family:'DM Sans',sans-serif; background:#0b0b12; color:#F2EEE6; }
section[data-testid="stSidebar"] { background:#0f0f18 !important; border-right:0.5px solid #1c1c28; }
section[data-testid="stSidebar"] * { color:#c8c5bf !important; }
section[data-testid="stSidebar"] button[kind="primary"] { color: #0f0f13 !important; }
section[data-testid="stSidebar"] button[kind="primary"] * { color: #0f0f13 !important; }
#MainMenu { visibility:hidden; } footer { visibility:hidden; }
[data-testid="stHeader"] { display: none !important; }
[data-testid="stSidebarHeader"] { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }
.block-container { padding-top: 1rem !important; }
section[data-testid="stSidebar"] > div { padding-top: 1rem !important; overflow: hidden !important; }
.stButton button { border-radius:8px !important; font-weight:500 !important; transition:all .15s !important; }
.stButton button[kind="primary"] { background:#F5B731 !important; color:#0f0f13 !important; border:none !important; }
div[data-testid="stExpander"] {
    background:#171720 !important; border:0.5px solid #1c1c28 !important;
    border-radius:12px !important; margin-bottom:12px !important;
}
div[data-testid="stExpander"] summary {
    padding:6px 16px !important; background:#171720 !important;
    border-radius:12px !important; color:#F2EEE6 !important;
}
div[data-testid="stExpander"] summary:hover { background:#1e1e2e !important; }
div[data-testid="stExpander"] summary svg { color:#555 !important; }
div[data-testid="stExpander"] > div:last-child {
    border-top:0.5px solid #1c1c28 !important; background:#171720 !important;
    border-radius:0 0 12px 12px !important; padding:16px !important;
}
[data-testid="stSidebarNav"] { display: none !important; }
</style>
""", unsafe_allow_html=True)


user  = get_user()
uid   = user.id if hasattr(user,"id") else user.get("id") if user else None
email = user.email if hasattr(user,"email") else user.get("email","") if user else ""

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    if st.button("⌂ Home", use_container_width=True):
        st.switch_page(st.session_state["_page_home"])
    st.markdown("<div style='padding-top:1rem'>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

profile    = get_profile(uid) if uid else {}
tier       = profile.get("subscription_tier", "free_trial")
used       = profile.get("analyses_used", 0)
limit      = profile.get("analyses_limit", 3)
tier_label = TIER_LABELS.get(tier, "Free Trial")
TIER_COLORS = {"free_trial":"#666","starter":"#3b82f6","unlimited":"#F5B731"}
tier_color  = TIER_COLORS.get(tier, "#666")
usage_str   = "Unlimited analyses" if tier=="unlimited" else \
              f"{used}/3 lifetime analyses" if tier=="free_trial" else \
              f"{used}/{limit} analyses this month"

with st.sidebar.container(key="sidebar_bottom"):
    st.markdown(f"<p style='color:#888;font-size:.8rem;margin-bottom:2px'>Signed in as</p>",
                unsafe_allow_html=True)
    st.markdown(f"<p style='color:#F2EEE6;font-size:.85rem;font-weight:500;"
                f"word-break:break-all;margin-bottom:8px'>{email}</p>",
                unsafe_allow_html=True)
    st.markdown(f"""
    <div style="background:#171720;border:0.5px solid #1c1c28;border-radius:8px;
                padding:8px 12px;margin-bottom:10px">
      <span style="font-size:11px;font-weight:600;color:#F2EEE6;
                   text-transform:uppercase;letter-spacing:.05em">{tier_label}</span>
      <div style="font-size:11px;color:#555;margin-top:2px">{usage_str}</div>
    </div>
    """, unsafe_allow_html=True)
    if tier == "free_trial":
        if st.button("⚡ Upgrade plan", use_container_width=True, type="primary"):
            st.switch_page(st.session_state["_page_pricing"])
    elif tier == "starter":
        if st.button("⚡ Upgrade to Unlimited", use_container_width=True, type="primary"):
            st.switch_page(st.session_state["_page_pricing"])
    else:
        if st.button("⚡ Manage plan", use_container_width=True, type="primary"):
            st.switch_page(st.session_state["_page_pricing"])
    if st.button("Sign out", use_container_width=True):
        try: get_supabase().auth.sign_out()
        except: pass
        clear_session()
        st.switch_page(st.session_state["_page_login"])

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
    rid        = st.session_state.pop("_view_report_id")
    rid_report = next((r for r in load_reports(uid) if r["id"] == rid), {})
    items      = load_report_items(rid)
    if items:
        import hashlib as _hl, json as _json
        transactions = []
        for it in items:
            transactions.append({
                "date":         it.get("date", ""),
                "name":         it.get("vendor_name") or it.get("vendor_name_clean") or "",
                "vendor_clean": it.get("vendor_name_clean") or it.get("vendor_name") or "",
                "amount":       float(it.get("amount") or 0),
                "category":     it.get("category", "Other"),
            })

        # Pre-populate insight from saved report so AI isn't re-called
        saved_insight = rid_report.get("ai_insight")
        if saved_insight:
            _key = "ai_insight_" + _hl.md5(
                _json.dumps(transactions, default=str, sort_keys=True).encode()
            ).hexdigest()
            st.session_state[_key]             = saved_insight
            st.session_state["_insight_to_save"] = saved_insight

        st.session_state.transactions       = transactions
        st.session_state.categorized        = True
        st.session_state.step               = 3
        st.session_state.tx_rows            = None
        st.session_state.tx_rows_source     = None
        st.session_state.redacted_pdf_bytes = None
        st.session_state._is_demo           = False
        st.switch_page(st.session_state["_page_home"])

reports = load_reports(uid)
CATEGORY_COLORS = DEFAULT_CATEGORY_COLORS
is_paid = tier in ("starter", "unlimited")

# Check if any reports were saved on free tier (no line items)
if is_paid and reports:
    free_tier_reports = [r for r in reports if r.get("tier_required") == "free"]
    if free_tier_reports:
        st.markdown(
            f"<div style='background:#171720;border:0.5px solid #252535;"
            f"border-radius:8px;padding:10px 14px;margin-bottom:1rem;font-size:.8rem;"
            f"color:#555;line-height:1.6'>"
            f"ℹ️ {len(free_tier_reports)} of your saved report"
            f"{'s were' if len(free_tier_reports) != 1 else ' was'} saved on the free plan "
            f"and {'don\'t' if len(free_tier_reports) != 1 else 'doesn\'t'} include full "
            f"transaction detail. New reports saved on your current plan will have the full view."
            f"</div>",
            unsafe_allow_html=True
        )

# ── Header ─────────────────────────────────────────────────────────────────────
hcol1, hcol2 = st.columns([4, 1])
with hcol1:
    st.markdown("""
    <div style="padding:4px 0 2px">
      <span style="font-family:'DM Serif Display',serif;font-style:italic;font-size:2.8rem;
                   color:#F5B731;letter-spacing:-.01em">Clara</span>
    </div>
    <div style="font-size:1.4rem;font-weight:500;color:#F2EEE6;margin-bottom:2px">
      Saved Reports
    </div>
    """, unsafe_allow_html=True)
    if reports:
        st.caption(f"{len(reports)} report{'s' if len(reports)!=1 else ''}")
with hcol2:
    st.markdown("<div style='padding-top:1.8rem'></div>", unsafe_allow_html=True)
    if st.button("＋ New analysis", type="primary", use_container_width=True):
        st.switch_page(st.session_state["_page_home"])

if not reports:
    st.markdown("""
    <div style="text-align:center;padding:4rem 1rem">
        <div style="font-size:2.5rem;margin-bottom:16px">📂</div>
        <p style="font-size:1.1rem;color:#F2EEE6;margin-bottom:8px">No saved reports yet</p>
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

    chart_mode = st.radio("Chart display", ["Value ($)", "Percentage (%)"],
                          horizontal=True, label_visibility="collapsed",
                          key="chart_mode")
    show_pct = chart_mode == "Percentage (%)"

    # Compute month totals for percentage mode
    month_totals = {m: sum(month_data[m].values()) for m in months_sorted}

    fig = go.Figure()
    for cat in all_cats:
        if show_pct:
            y_vals = [
                round(month_data[m].get(cat, 0) / month_totals[m] * 100, 1)
                if month_totals[m] else 0
                for m in months_sorted
            ]
            hover = f"<b>{cat}</b><br>%{{y:.1f}}%<extra></extra>"
        else:
            y_vals = [month_data[m].get(cat, 0) for m in months_sorted]
            hover = f"<b>{cat}</b><br>$%{{y:,.2f}}<extra></extra>"

        fig.add_trace(go.Bar(
            name=cat,
            x=months_sorted,
            y=y_vals,
            marker_color=CATEGORY_COLORS.get(cat, "#6b7280"),
            hovertemplate=hover,
        ))

    fig.update_layout(
        barmode="stack",
        height=280,
        bargap=0.6,
        margin=dict(l=0, r=0, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#c8c5bf", size=11, family="DM Sans"),
        showlegend=True,
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            xanchor="left", x=0, font=dict(size=10),
        ),
        xaxis=dict(
            gridcolor="#1c1c28", tickfont=dict(size=10), linecolor="#252535",
            tickformat="%b %Y",
        ),
        yaxis=dict(
            gridcolor="#1c1c28", tickfont=dict(size=10),
            ticksuffix="%" if show_pct else "",
            tickprefix="" if show_pct else "$",
            range=[0, 100] if show_pct else None,
        ),
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
    tier_required    = report.get("tier_required", "starter")
    has_line_items   = tier_required in ("starter", "unlimited")
    can_view         = is_paid and has_line_items

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
          <div style="background:#0b0b12;border-radius:8px;padding:12px 14px">
            <div style="font-size:16px;font-weight:500;color:#f87171;
                        font-family:'DM Sans',sans-serif;font-weight:300">${abs(total_spend):,.2f}</div>
            <div style="font-size:10px;color:#555;margin-top:4px;
                        text-transform:uppercase;letter-spacing:.05em">Total spent</div>
          </div>
          <div style="background:#0b0b12;border-radius:8px;padding:12px 14px">
            <div style="font-size:16px;font-weight:500;color:#34d399;
                        font-family:'DM Sans',sans-serif;font-weight:300">${total_income:,.2f}</div>
            <div style="font-size:10px;color:#555;margin-top:4px;
                        text-transform:uppercase;letter-spacing:.05em">Income</div>
          </div>
          <div style="background:#0b0b12;border-radius:8px;padding:12px 14px">
            <div style="font-size:16px;font-weight:500;color:#F2EEE6;
                        font-family:'DM Sans',sans-serif;font-weight:300">{tx_count}</div>
            <div style="font-size:10px;color:#555;margin-top:4px;
                        text-transform:uppercase;letter-spacing:.05em">Transactions</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # AI insight if saved
        ai_insight = report.get("ai_insight")
        if ai_insight:
            st.markdown(f"""
            <div style="background:#0b0b12;border-radius:8px;padding:12px 14px;margin-bottom:16px">
              <p style="font-size:.7rem;font-weight:600;color:#F5B731;text-transform:uppercase;
                        letter-spacing:.08em;margin:0 0 6px">✦ AI Insight</p>
              <p style="font-size:.85rem;color:#c8c5bf;line-height:1.6;margin:0">{ai_insight}</p>
            </div>
            """, unsafe_allow_html=True)

        # Top 3 vendors
        if top_vendors:
            max_amt = max(v.get("amount", 0) for v in top_vendors) or 1
            vendor_html = ""
            for v in top_vendors[:3]:
                vname   = v.get("vendor", "Unknown")
                vamt    = float(v.get("amount", 0))
                vcat    = v.get("category", "Other")
                bar_pct = int(vamt / max_amt * 100)
                color   = CATEGORY_COLORS.get(vcat, "#6b7280")
                # Use a non-grey fallback for uncategorised vendors
                display_color = color if color != "#6b7280" else "#888"
                vendor_html += f"""
                <div style="padding:8px 0;border-bottom:0.5px solid #1c1c28">
                  <div style="display:flex;justify-content:space-between;
                              align-items:baseline;margin-bottom:4px">
                    <span style="font-size:.85rem;color:#F2EEE6">{vname}</span>
                    <span style="font-size:.85rem;font-weight:500;color:#F2EEE6;
                                 font-family:'DM Sans',sans-serif;font-weight:300">${vamt:,.2f}</span>
                  </div>
                  <div style="background:#171720;border-radius:3px;height:3px">
                    <div style="width:{bar_pct}%;height:3px;border-radius:3px;
                                background:{display_color}"></div>
                  </div>
                </div>"""
            st.markdown(
                "<p style='font-size:.75rem;color:#555;text-transform:uppercase;"
                "letter-spacing:.06em;margin:0 0 6px'>Top vendors</p>",
                unsafe_allow_html=True
            )
            st.markdown(vendor_html, unsafe_allow_html=True)

        # View full report + Delete
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        btn_col1, btn_col2 = st.columns([3, 1])

        with btn_col1:
            if can_view:
                if st.button("View full report →", key=f"view_{rid}",
                             type="primary", use_container_width=True):
                    st.session_state._view_report_id = rid
                    st.rerun()
            elif is_paid and not has_line_items:
                # User is paid but report was saved on free tier — no line items stored
                st.markdown(
                    "<div style='padding:8px 12px;border:0.5px solid #1c1c28;"
                    "border-radius:8px;font-size:.8rem;color:#555;line-height:1.5'>"
                    "This report was saved on the free plan — full transaction detail "
                    "wasn't stored. Future reports will include the full view.</div>",
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    "<div style='padding:8px 12px;border:0.5px solid #1c1c28;"
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
