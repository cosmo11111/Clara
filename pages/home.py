"""
pages/home.py — Main Clara app: upload, redact, categorise, review results.
"""
import json
import hashlib
import streamlit as st
import streamlit.components.v1 as components
import plotly.graph_objects as go
import pandas as pd
from datetime import date as _date

from auth import get_user, get_supabase, clear_session
from db import (
    can_analyse, increment_usage, get_profile,
    TIER_LABELS, TIER_LIMITS,
    load_categories, save_category, delete_category, auto_assign_color,
    load_vendor_rules, apply_vendor_rules, save_vendor_rule,
    save_report, check_duplicate_report,
    DEFAULT_CATEGORY_COLORS,
)
from utils import (
    parse_amount, render_page_b64, snap_to_words,
    apply_redactions, extract_text_all_pages,
    make_figure, categorize_with_gemini, generate_insight,
)
from demo import DEMO_DATA

CATEGORY_COLORS = DEFAULT_CATEGORY_COLORS

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500&display=swap');

html, body, .stApp { font-family:'DM Sans',sans-serif; background:#0b0b12; color:#F2EEE6; }
[data-testid="stHeader"] { display:none !important; }
[data-testid="stSidebarHeader"] { display:none !important; }
[data-testid="collapsedControl"] { display:none !important; }
[data-testid="stSidebarNav"] { display:none !important; }
[data-testid="stToolbar"] { display:none !important; }
#MainMenu { visibility:hidden !important; }
.block-container { padding-top:1rem !important; }
section[data-testid="stSidebar"] > div { padding-top:1rem !important; overflow:hidden !important; }
section[data-testid="stSidebar"] { background:#0f0f18 !important; border-right:0.5px solid #1c1c28; }
section[data-testid="stSidebar"] * { color:#c8c5bf !important; }
section[data-testid="stSidebar"] button[kind="primary"] { color:#0b0b12 !important; }
section[data-testid="stSidebar"] button[kind="primary"] * { color:#0b0b12 !important; }
section[data-testid="stSidebar"] > div > div[data-testid="stVerticalBlock"] {
    display:flex !important; flex-direction:column !important; height:100vh !important;
}
div[data-testid="stSidebarUserContent"] { display:flex !important; flex-direction:column !important; height:100% !important; }

.step-badge { display:inline-flex; align-items:center; gap:10px; background:#171720;
  border:0.5px solid #1c1c28; border-radius:12px; padding:14px 20px; margin-bottom:12px; width:100%; }
.step-num { width:28px; height:28px; border-radius:50%; background:#F5B731; color:#0b0b12;
  font-weight:700; font-size:13px; display:flex; align-items:center; justify-content:center; flex-shrink:0; }
.step-num.done { background:#2e8f66; }
.step-num.active { background:#F5B731; box-shadow:0 0 12px rgba(245,183,49,0.4); }

.info-box { background:#171720; border-left:3px solid #F5B731; border-radius:6px; padding:10px 14px; margin-bottom:12px; font-size:.875rem; color:#c8c5bf; }
.info-box.green { border-left-color:#2e8f66; background:#0f1a14; }
.info-box.blue  { border-left-color:#5B8DB8; background:#0f1624; }
.info-box.red   { border-left-color:#C4604A; background:#1a0f0f; }

.metric-strip { display:flex; gap:1rem; margin-bottom:1.5rem; flex-wrap:wrap; }
.metric { background:#171720; border:0.5px solid #1c1c28; border-radius:10px; padding:14px 20px; flex:1; min-width:120px; }
.metric .val { font-size:1.5rem; font-weight:300; font-family:'DM Sans',sans-serif; color:#F5B731; }
.metric .lbl { font-size:.75rem; color:#555; margin-top:4px; text-transform:uppercase; letter-spacing:.05em; }

.card { background:#171720; border:0.5px solid #1c1c28; border-radius:12px; padding:20px; margin-bottom:12px; }
.card h3 { font-size:.95rem; font-weight:500; color:#F2EEE6; margin-bottom:8px; }
.card p  { font-size:.85rem; color:#888; line-height:1.6; margin:0; }

.tx-table .stButton button { background:transparent !important; border:none !important; color:#555 !important; padding:2px 6px !important; font-size:.75rem !important; }
.tx-table .del-btn button { color:#555 !important; }
.tx-table .del-btn button:hover { color:#C4604A !important; background:#1a0f0f !important; }

.stFileUploader { background:#171720 !important; border:0.5px dashed #252535 !important; border-radius:10px !important; }
.stFileUploader:hover { border-color:#F5B731 !important; color:#F5B731 !important; background:#1c1c28 !important; }

.stButton button[kind="primary"] { background:#F5B731 !important; color:#0b0b12 !important; border:none !important; }
.stButton button[kind="primary"]:hover { opacity:0.88 !important; }

[data-testid="InputInstructions"] { display:none !important; }
</style>
""", unsafe_allow_html=True)

# ── Auth ──────────────────────────────────────────────────────────────────────
user   = get_user()
uid    = user.id if hasattr(user, "id") else user.get("id") if user else None
email  = user.email if hasattr(user, "email") else user.get("email", "") if user else ""
profile   = get_profile(uid) if uid else {}
tier      = profile.get("subscription_tier", "starter")
used      = profile.get("analyses_used", 0)
limit     = profile.get("analyses_limit", 10)
TIER_COLORS = {"free_trial": "#666", "starter": "#3b82f6", "unlimited": "#F5B731"}
tier_color  = TIER_COLORS.get(tier, "#666")
tier_label  = TIER_LABELS.get(tier, "Free Trial")
if tier == "unlimited":
    usage_str = "Unlimited analyses"
elif tier == "free_trial":
    usage_str = f"{used}/3 lifetime analyses"
else:
    usage_str = f"{used}/{limit} analyses this month"

# ── Session state defaults ────────────────────────────────────────────────────
for k, v in [
    ("step", 1), ("pdf_bytes", None), ("redacted_pdf_bytes", None),
    ("annotations", {}), ("pending", None), ("page_num", 0),
    ("zoom", 1.5), ("transactions", None), ("categorized", False),
]:
    if k not in st.session_state:
        st.session_state[k] = v

snap = True
zoom = st.session_state.zoom

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    if st.button("⌂ Home", use_container_width=True):
        for k in ["step", "pdf_bytes", "redacted_pdf_bytes", "annotations",
                  "pending", "page_num", "transactions", "categorized",
                  "tx_rows", "tx_rows_source", "_tx_pending_delete",
                  "_tx_pending_add", "_is_demo", "_insight_to_save", "_insight_error"]:
            st.session_state.pop(k, None)
        for k in [k for k in st.session_state
                  if k.startswith("td_") or k.startswith("ai_insight_")]:
            del st.session_state[k]
        render_page_b64.clear()
        st.rerun()

with st.sidebar.container(key="sidebar_bottom"):
    st.markdown(f"<p style='color:#555;font-size:.8rem;margin-bottom:2px'>Signed in as</p>",
                unsafe_allow_html=True)
    st.markdown(f"<p style='color:#F2EEE6;font-size:.85rem;font-weight:500;"
                f"word-break:break-all;margin-bottom:8px'>{email}</p>",
                unsafe_allow_html=True)
    st.markdown(f"""
    <div style="background:#171720;border:0.5px solid #1c1c28;border-radius:8px;
                padding:8px 12px;margin-bottom:10px">
      <span style="font-size:11px;font-weight:600;color:{tier_color};
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
    if st.button("📂 Saved Reports", use_container_width=True):
        st.switch_page(st.session_state["_page_reports"])
    if st.button("⚙ Settings", use_container_width=True):
        st.switch_page(st.session_state["_page_settings"])
    if st.button("Sign out", use_container_width=True):
        try:
            get_supabase().auth.sign_out()
        except Exception:
            pass
        clear_session()
        st.switch_page(st.session_state["_page_login"])

st.html("""
<style>
  .st-key-sidebar_bottom {
    position:absolute; bottom:16px; left:0; right:0; padding:0 1rem;
  }
</style>
""")

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="padding:12px 0 4px">
  <span style="font-family:'DM Serif Display',serif;font-style:italic;font-size:2.8rem;
               color:#F5B731;letter-spacing:-.01em">Clara</span>
</div>
""", unsafe_allow_html=True)
if st.session_state.step == 1:
    st.markdown("*AI-powered bank statement analysis with privacy-first redaction*")
    st.markdown("---")

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1 + 2 — Upload & Redact
# ═══════════════════════════════════════════════════════════════════════════════
if st.session_state.step in (1, 2):
    pdf_loaded = st.session_state.pdf_bytes is not None

    if pdf_loaded:
        import fitz as _fitz
        pdf_bytes = st.session_state.pdf_bytes
        doc_tmp   = _fitz.open(stream=pdf_bytes, filetype="pdf")
        n_pages   = len(doc_tmp); doc_tmp.close()
        pn = st.session_state.page_num
        zm = st.session_state.zoom
        pk = str(pn)

        st.markdown("#### 2. Redaction tool")
        bar1, bar2, bar3, bar4 = st.columns([2, 2, 2, 1])
        with bar1:
            redact_btn = st.button("⬛ Redact Selection  [R]", use_container_width=True,
                                   disabled=st.session_state.pending is None)
        with bar2:
            undo_btn = st.button("↩️ Undo Last  [U]", use_container_width=True,
                                 disabled=not st.session_state.annotations.get(pk))
        with bar3:
            analyse_btn = st.button("🤖 Categorize Transactions",
                                    use_container_width=True, type="primary")
        with bar4:
            if st.button("✕ Reset", use_container_width=True):
                st.session_state.pdf_bytes    = None
                st.session_state.annotations  = {}
                st.session_state.pending      = None
                st.session_state.page_num     = 0
                st.session_state.step         = 1
                render_page_b64.clear()
                st.rerun()

        if st.session_state.pending:
            st.markdown('<div class="info-box red">🔴 Selection ready — click <b>Redact Selection</b> to black it out</div>',
                        unsafe_allow_html=True)
        else:
            rd_count_pg = len(st.session_state.annotations.get(pk, []))
            status = (f"⬛ {rd_count_pg} redaction{'s' if rd_count_pg != 1 else ''} on this page"
                      if rd_count_pg else "🖱️ Drag on the document to select an area to redact")
            st.markdown(f'<div class="info-box">{status}</div>', unsafe_allow_html=True)

        _, nav1, nav2, nav3, _ = st.columns([1, 0.4, 1, 0.4, 3])
        with nav1:
            if st.button("◀", use_container_width=True, disabled=pn == 0, key="pg_prev"):
                st.session_state.page_num -= 1
                st.session_state.pending   = None
                st.rerun()
        with nav2:
            st.markdown(f"<p style='text-align:center;margin:6px 0;font-size:.85rem;"
                        f"color:#888'>{pn+1} / {n_pages}</p>", unsafe_allow_html=True)
        with nav3:
            if st.button("▶", use_container_width=True,
                         disabled=pn == n_pages - 1, key="pg_next"):
                st.session_state.page_num += 1
                st.session_state.pending   = None
                st.rerun()

        if redact_btn and st.session_state.pending:
            x0, y0, x1, y1 = st.session_state.pending
            if snap:
                x0, y0, x1, y1 = snap_to_words(pdf_bytes, pn, (x0, y0, x1, y1))
            st.session_state.annotations.setdefault(pk, []).append(
                {"rect": [x0, y0, x1, y1], "color": "black", "type": "redact"})
            st.session_state.pending = None
            st.rerun()

        if undo_btn and st.session_state.annotations.get(pk):
            st.session_state.annotations[pk].pop()
            if not st.session_state.annotations[pk]:
                del st.session_state.annotations[pk]
            st.session_state.pending = None
            st.rerun()

        if analyse_btn:
            with st.spinner("Applying redactions…"):
                st.session_state.redacted_pdf_bytes = (
                    apply_redactions(pdf_bytes, st.session_state.annotations)
                    if st.session_state.annotations else pdf_bytes
                )
            st.session_state.step       = 3
            st.session_state.categorized = False
            st.rerun()

        # Keyboard shortcuts
        components.html("""
<script>
(function() {
  if (window._redactKeysRegistered) return;
  window._redactKeysRegistered = true;
  function clickButtonByText(text) {
    const btns = window.parent.document.querySelectorAll('button');
    for (const btn of btns) {
      if (btn.innerText.trim().includes(text) && !btn.disabled) { btn.click(); return true; }
    }
    return false;
  }
  window.parent.document.addEventListener('keydown', function(e) {
    const tag = e.target.tagName.toLowerCase();
    if (tag === 'input' || tag === 'textarea' || e.target.isContentEditable) return;
    if (e.key === 'r' || e.key === 'R') { e.preventDefault(); clickButtonByText('Redact Selection'); }
    if (e.key === 'u' || e.key === 'U') { e.preventDefault(); clickButtonByText('Undo Last'); }
  });
})();
</script>""", height=0)

        b64, img_w, img_h = render_page_b64(pdf_bytes, pn, zm)
        fig   = make_figure(b64, img_w, img_h,
                            st.session_state.annotations.get(pk, []),
                            st.session_state.pending, zm)
        event = st.plotly_chart(fig, use_container_width=False,
                                key=f"chart_{pn}_{zm}",
                                on_select="rerun", selection_mode=["box"])
        try:
            box = (event.selection.box or [{}])[0]
            xs, ys = box.get("x", []), box.get("y", [])
            if len(xs) >= 2 and len(ys) >= 2:
                new = (min(xs)/zm, (img_h-max(ys))/zm, max(xs)/zm, (img_h-min(ys))/zm)
                if new != st.session_state.pending:
                    st.session_state.pending = new
                    st.rerun()
        except Exception:
            pass

    if not pdf_loaded:
        up_col, info_col = st.columns([2, 1])
        with up_col:
            st.markdown("### 1. Upload your bank statement")
            st.markdown('<div class="info-box">Upload a PDF bank statement. You can redact sensitive '
                        'information (account numbers, BSB, personal details) before the AI reads it.</div>',
                        unsafe_allow_html=True)
            st.markdown("<div style='padding-top:8px'></div>", unsafe_allow_html=True)
            uploaded = st.file_uploader("Upload PDF", type=["pdf"], label_visibility="visible")
            if uploaded:
                b = uploaded.read()
                if b != st.session_state.pdf_bytes:
                    st.session_state.pdf_bytes    = b
                    st.session_state.annotations  = {}
                    st.session_state.pending      = None
                    st.session_state.transactions = None
                    st.session_state.categorized  = False
                    st.session_state.step         = 2
                    render_page_b64.clear()
                    st.rerun()
            st.markdown("---")
            st.markdown('<p style="color:#333345;font-size:.8rem;margin-bottom:8px;'
                        'text-transform:uppercase;letter-spacing:.06em">⚡ Developer shortcut</p>',
                        unsafe_allow_html=True)
            if st.button("📋 Load demo expenses", use_container_width=True):
                st.session_state.transactions = DEMO_DATA
                st.session_state.categorized  = True
                st.session_state.redacted_pdf_bytes = None
                st.session_state.annotations  = {}
                st.session_state.step         = 3
                st.session_state._is_demo     = True
                st.rerun()

        with info_col:
            st.markdown("### How it works")
            st.markdown("""
            <div class="card"><h3>🔒 Privacy first</h3>
            <p>Before the AI reads anything, you can black out sensitive details such as account numbers,
            BSBs, names, and addresses. Redacted areas are permanently removed from the document the AI
            receives. We don't store your PDF at any point.</p></div>
            <div class="card"><h3>🤖 AI categorisation</h3>
            <p>Our AI categorises each transaction automatically. Add custom categories, edit any
            categorisation, and set vendor rules so your regular merchants are always categorised
            correctly in future uploads.</p></div>
            <div class="card"><h3>📊 Instant insights</h3>
            <p>See a top-level view of your spending, review the detailed transaction list, and save
            reports to compare month over month.</p></div>
            """, unsafe_allow_html=True)

    if pdf_loaded:
        uploaded = st.file_uploader("Upload PDF", type=["pdf"], label_visibility="collapsed")
        if uploaded:
            b = uploaded.read()
            if b != st.session_state.pdf_bytes:
                st.session_state.pdf_bytes    = b
                st.session_state.annotations  = {}
                st.session_state.pending      = None
                st.session_state.transactions = None
                st.session_state.categorized  = False
                st.session_state.step         = 2
                render_page_b64.clear()
                st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Results
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state.step == 3:
    run = not st.session_state.categorized

    if run:
        if uid:
            allowed, reason = can_analyse(uid)
            if not allowed:
                reason_display = reason.replace("(9/mo)", "($9/mo)").replace("(29/mo)", "($29/mo)")
                st.markdown(f"""
                <div style="background:#1a0f0f;border:0.5px solid #6b2d2d;border-radius:8px;
                            padding:12px 16px;margin-bottom:16px;font-size:.9rem;color:#f87171">
                  🔒 {reason_display}
                </div>""", unsafe_allow_html=True)
                if st.button("⚡ View upgrade options", type="primary"):
                    st.switch_page(st.session_state["_page_pricing"])
                st.stop()

        with st.spinner("Extracting text and sending to Gemini…"):
            try:
                text = extract_text_all_pages(st.session_state.redacted_pdf_bytes)
                if not text:
                    st.error("No text could be extracted from the PDF. It may be a scanned image.")
                    st.stop()
                all_cats = load_categories(uid) if uid else DEFAULT_CATEGORY_COLORS
                v_rules  = load_vendor_rules(uid) if uid else []
                data = categorize_with_gemini(text, all_cats, v_rules)
                st.session_state.transactions = data
                st.session_state.categorized  = True
                if uid:
                    increment_usage(uid)
                st.session_state._is_demo = False
                st.session_state.pop("_insight_to_save", None)
            except Exception as e:
                st.error(f"Gemini error: {e}")
                st.stop()

    if st.session_state.categorized and st.session_state.transactions:
        data = st.session_state.transactions
        df   = pd.DataFrame(data)
        df["amount"] = df["amount"].map(parse_amount)

        _metrics_placeholder = st.empty()
        _insight_placeholder = st.empty()
        _charts_placeholder  = st.empty()
        cat_totals = pd.Series(dtype=float)

        # ── Transaction table ─────────────────────────────────────────────────
        st.markdown("#### All Transactions")
        st.markdown(
            "<p style='font-size:.85rem;color:#888;margin:-8px 0 8px'>Manage custom categories "
            "and vendor rules in "
            "<a href='/settings' target='_self' style='color:#aaa;text-decoration:underline'>"
            "Settings</a>.</p>",
            unsafe_allow_html=True,
        )

        all_cats  = load_categories(uid) if uid else DEFAULT_CATEGORY_COLORS
        v_rules   = load_vendor_rules(uid) if uid else []
        cat_names = list(all_cats.keys())
        ADD_NEW   = "＋ Add new category…"
        cat_options = cat_names + [ADD_NEW]

        _src_key = hashlib.md5(
            json.dumps(st.session_state.transactions, default=str, sort_keys=True).encode()
        ).hexdigest()

        if ("tx_rows" not in st.session_state
                or st.session_state.get("tx_rows_source") != _src_key):
            cols = ["date", "name", "amount", "category"]
            if "vendor_clean" in df.columns:
                cols.append("vendor_clean")
            st.session_state.tx_rows       = df[cols].copy().to_dict("records")
            st.session_state.tx_rows_source = _src_key

        if st.session_state.get("_tx_pending_delete") is not None:
            idx = st.session_state.pop("_tx_pending_delete")
            rows_before = st.session_state.tx_rows
            n = len(rows_before)
            if 0 <= idx < n:
                rows_before.pop(idx)
                fields = ("date", "name", "amt", "cat")
                for j in range(idx, n - 1):
                    for f in fields:
                        src, dst = f"td_{j+1}_{f}", f"td_{j}_{f}"
                        if src in st.session_state:
                            st.session_state[dst] = st.session_state[src]
                        elif dst in st.session_state:
                            del st.session_state[dst]
                for f in fields:
                    st.session_state.pop(f"td_{n-1}_{f}", None)
                for k in [k for k in st.session_state
                          if k.startswith("td_") and k.endswith("_del")]:
                    del st.session_state[k]
            st.rerun()

        if st.session_state.get("_tx_pending_add"):
            st.session_state.tx_rows.append({
                "date": _date.today().strftime("%d %b %Y"),
                "name": "", "vendor_clean": "", "amount": "", "category": "Other",
            })
            st.session_state._tx_pending_add = False
            for k in [k for k in st.session_state if k.startswith("td_")]:
                del st.session_state[k]
            st.rerun()

        rows = st.session_state.tx_rows
        vendor_rule_queue = []
        new_cats_needed   = []

        h_date, h_vendor, h_raw, h_amt, h_cat, h_del = st.columns([1.3, 2.0, 2.0, 1.3, 3.4, 0.6])
        with h_date:   st.markdown("<p style='font-size:.75rem;color:#555;margin:0'>Date</p>", unsafe_allow_html=True)
        with h_vendor: st.markdown("<p style='font-size:.75rem;color:#555;margin:0'>Vendor</p>", unsafe_allow_html=True)
        with h_raw:    st.markdown("<p style='font-size:.75rem;color:#555;margin:0'>Raw description</p>", unsafe_allow_html=True)
        with h_amt:    st.markdown("<p style='font-size:.75rem;color:#555;margin:0'>Amount</p>", unsafe_allow_html=True)
        with h_cat:    st.markdown("<p style='font-size:.75rem;color:#555;margin:0'>Category</p>", unsafe_allow_html=True)
        with h_del:    st.markdown("", unsafe_allow_html=True)

        for i, row in enumerate(rows):
            c_date, c_name, c_raw, c_amt, c_cat, c_del = st.columns([1.3, 2.0, 2.0, 1.3, 3.4, 0.6])
            with c_date:
                st.text_input("Date", value=str(row.get("date", "")),
                              label_visibility="collapsed", key=f"td_{i}_date")
            with c_name:
                raw_val = row.get("vendor_clean") or row.get("name", "")
                if str(raw_val).lower() in ("nan", "none", ""):
                    raw_val = row.get("name", "")
                st.text_input("Vendor", value=str(raw_val),
                              label_visibility="collapsed", key=f"td_{i}_name")
            with c_raw:
                raw_desc = str(row.get("name", ""))
                if raw_desc.lower() in ("nan", "none"):
                    raw_desc = ""
                st.markdown(
                    f"<p style='font-size:.8rem;color:#555;margin:6px 0;overflow:hidden;"
                    f"white-space:nowrap;text-overflow:ellipsis' title='{raw_desc}'>{raw_desc}</p>",
                    unsafe_allow_html=True)
            with c_amt:
                st.text_input("Amount", value=str(row.get("amount", "")),
                              label_visibility="collapsed", key=f"td_{i}_amt")
            with c_cat:
                prev_cat = str(row.get("category", "Other"))
                if prev_cat not in cat_options:
                    prev_cat = "Other"
                current_name = st.session_state.get(f"td_{i}_name",
                                                     row.get("name", "")).strip()
                if current_name and current_name.lower() not in ("", "other"):
                    matched = apply_vendor_rules(v_rules, current_name)
                    if matched and matched in cat_names and matched != prev_cat:
                        if prev_cat == "Other":
                            prev_cat = matched
                            rows[i]["category"] = matched
                new_cat = st.selectbox("Category", cat_options,
                                       index=cat_options.index(prev_cat),
                                       label_visibility="collapsed",
                                       key=f"td_{i}_cat")
                if new_cat != prev_cat:
                    if new_cat == ADD_NEW:
                        new_cats_needed.append(i)
                    else:
                        rows[i]["category"] = new_cat
                        vendor = str(rows[i].get("name", "")).strip()
                        if vendor and vendor.lower() not in ("", "other") and uid:
                            vendor_rule_queue.append((vendor, new_cat))
            with c_del:
                def _make_delete_cb(idx):
                    def _cb(): st.session_state._tx_pending_delete = idx
                    return _cb
                st.button("✕", key=f"td_{i}_del", on_click=_make_delete_cb(i),
                          help="Delete this row", use_container_width=True)

        for vendor, category in vendor_rule_queue:
            save_vendor_rule(uid, vendor, category, "contains")

        def _add_row_cb():
            st.session_state._tx_pending_add = True

        def _update_charts_cb():
            _rows = st.session_state.tx_rows
            for _i in range(len(_rows)):
                _rows[_i]["date"]         = st.session_state.get(f"td_{_i}_date", _rows[_i].get("date", ""))
                _rows[_i]["vendor_clean"] = st.session_state.get(f"td_{_i}_name", _rows[_i].get("vendor_clean", ""))
                _rows[_i]["name"]         = _rows[_i].get("name", _rows[_i]["vendor_clean"])
                _rows[_i]["amount"]       = st.session_state.get(f"td_{_i}_amt", _rows[_i].get("amount", ""))
                _rows[_i]["category"]     = st.session_state.get(f"td_{_i}_cat", _rows[_i].get("category", "Other"))
            st.session_state.tx_rows = _rows

        _update_charts_cb()
        st.button("＋  Add transaction", use_container_width=True,
                  on_click=_add_row_cb, key="add_tx_btn")

        for i in range(len(rows)):
            rows[i]["category"] = st.session_state.get(f"td_{i}_cat", rows[i].get("category", "Other"))
        st.session_state.tx_rows = rows

        df_edited = (pd.DataFrame(st.session_state.tx_rows) if st.session_state.tx_rows
                     else pd.DataFrame(columns=["date", "name", "amount", "category"]))
        df_edited["amount"] = df_edited["amount"].map(parse_amount)

        total_spend  = df_edited[df_edited["amount"] < 0]["amount"].sum()
        total_income = df_edited[df_edited["amount"] > 0]["amount"].sum()
        n_tx         = len(df_edited)
        top_cat      = (df_edited[df_edited["amount"] < 0]
                        .groupby("category")["amount"].sum().idxmin()
                        if len(df_edited[df_edited["amount"] < 0]) else "—")

        _metrics_placeholder.markdown(f"""<div class="metric-strip">
            <div class="metric"><div class="val">{n_tx}</div><div class="lbl">Transactions</div></div>
            <div class="metric"><div class="val" style="color:#C4604A">${abs(total_spend):,.2f}</div><div class="lbl">Total Spent</div></div>
            <div class="metric"><div class="val" style="color:#2e8f66">${total_income:,.2f}</div><div class="lbl">Total Income</div></div>
            <div class="metric"><div class="val" style="font-size:1rem;padding-top:4px">{top_cat}</div><div class="lbl">Biggest Category</div></div>
        </div>""", unsafe_allow_html=True)

        spend_df = df_edited[df_edited["amount"] < 0].copy()
        spend_df["name"]       = spend_df["name"].astype(str)
        spend_df["amount_abs"] = spend_df["amount"].abs()
        cat_totals = spend_df.groupby("category")["amount_abs"].sum().sort_values(ascending=False)

        # ── AI Insight ────────────────────────────────────────────────────────
        _is_paid_insight = tier in ("starter", "unlimited")
        _is_demo         = st.session_state.get("_is_demo", False)
        _cat_totals_dict = cat_totals.to_dict() if not cat_totals.empty else {}
        _top_v = []
        if "vendor_clean" in spend_df.columns:
            _tv = (spend_df.groupby("vendor_clean")["amount_abs"]
                   .sum().sort_values(ascending=False).head(3))
            _top_v = [{"vendor": k, "amount": round(v, 2)} for k, v in _tv.items()]

        if _is_paid_insight and not _is_demo:
            _insight_key = "ai_insight_" + hashlib.md5(
                json.dumps(st.session_state.get("transactions", []),
                           default=str, sort_keys=True).encode()
            ).hexdigest()
            if _insight_key not in st.session_state:
                try:
                    text = generate_insight(total_spend, total_income,
                                            n_tx, _cat_totals_dict, _top_v)
                    st.session_state[_insight_key] = text
                except Exception as err:
                    st.session_state[_insight_key]  = None
                    st.session_state["_insight_error"] = str(err)

            _insight_text = st.session_state.get(_insight_key)
            if _insight_text:
                st.session_state["_insight_to_save"] = _insight_text
                _insight_placeholder.markdown(f"""
                <div style="background:#171720;border:0.5px solid #1c1c28;border-radius:10px;
                            padding:14px 18px;margin:0 0 16px">
                  <p style="font-size:.7rem;font-weight:600;color:#F5B731;text-transform:uppercase;
                            letter-spacing:.08em;margin:0 0 6px">✦ AI Insight</p>
                  <p style="font-size:.9rem;color:#c8c5bf;line-height:1.6;margin:0">{_insight_text}</p>
                </div>""", unsafe_allow_html=True)
            elif st.session_state.get("_insight_error"):
                _insight_placeholder.caption(f"⚠️ Insight unavailable: {st.session_state['_insight_error']}")
        else:
            _top_cat_name = cat_totals.index[0] if not cat_totals.empty else "spending"
            _top_cat_amt  = cat_totals.iloc[0]  if not cat_totals.empty else 0
            _teasers = [
                f"Your biggest spending category was {_top_cat_name} at ${_top_cat_amt:,.0f}, which accounts for",
                f"You made {n_tx} transactions this month, with {_top_v[0]['vendor'] if _top_v else 'your top vendor'} appearing the most",
                f"Your spending was spread across {len(_cat_totals_dict)} categories, with {_top_cat_name} and",
            ]
            _teaser = _teasers[hash(str(_cat_totals_dict)) % len(_teasers)]
            _insight_placeholder.markdown(f"""
            <div style="background:#171720;border:0.5px solid #1c1c28;border-radius:10px;
                        padding:14px 18px;margin:0 0 16px;position:relative;overflow:hidden">
              <p style="font-size:.7rem;font-weight:600;color:#555;text-transform:uppercase;
                        letter-spacing:.08em;margin:0 0 6px">✦ AI Insight</p>
              <p style="font-size:.9rem;color:#c8c5bf;line-height:1.6;margin:0 0 8px">
                {_teaser}
                <span style="background:linear-gradient(to right,#c8c5bf,transparent);
                             -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                             background-clip:text">&nbsp;your top categories driving 80% of...</span>
              </p>
              <div style="position:absolute;right:0;top:0;bottom:0;width:60%;
                          background:linear-gradient(to right,transparent,#1a1a24 70%)"></div>
              <p style="font-size:.8rem;color:#F5B731;margin:0;position:relative;z-index:1">
                🔒 Upgrade to Starter to unlock AI insights
              </p>
            </div>""", unsafe_allow_html=True)

        if not cat_totals.empty:
            with _charts_placeholder.container():
                pie_col, vendor_col = st.columns([1, 1])

                with pie_col:
                    st.markdown("#### Spending by Category")
                    pie_mode = st.radio("Display", ["Value ($)", "Percentage (%)"],
                                        horizontal=True, label_visibility="collapsed",
                                        key="pie_mode")
                    show_pct        = pie_mode == "Percentage (%)"
                    total_spend_abs = cat_totals.sum()
                    threshold  = total_spend_abs * 0.03
                    main_cats  = cat_totals[cat_totals >= threshold]
                    other_sum  = cat_totals[cat_totals < threshold].sum()
                    if other_sum > 0:
                        main_cats = pd.concat([main_cats, pd.Series({"Other": other_sum})])

                    fig_pie = go.Figure(go.Pie(
                        labels=main_cats.index.tolist(),
                        values=main_cats.values.tolist(),
                        marker=dict(
                            colors=[CATEGORY_COLORS.get(c, "#6b7280") for c in main_cats.index],
                            line=dict(color="#0b0b12", width=2),
                        ),
                        hole=0.52,
                        hovertemplate="<b>%{label}</b><br>$%{value:,.2f}<br>%{percent}<extra></extra>",
                        texttemplate="%{label}<br>%{percent}" if show_pct else "%{label}<br>$%{value:,.0f}",
                        textposition="outside",
                        pull=[0.03] * len(main_cats),
                    ))
                    centre_text = f"${total_spend_abs:,.0f}" if not show_pct else "100%"
                    fig_pie.update_layout(
                        height=460, margin=dict(l=60, r=60, t=100, b=80),
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        font=dict(color="#c8c5bf", size=11, family="DM Sans"),
                        showlegend=False,
                        annotations=[dict(
                            text=f"<b>{centre_text}</b><br><span style='font-size:10px'>total spend</span>",
                            x=0.5, y=0.5, font=dict(size=14, color="#F2EEE6"), showarrow=False,
                        )],
                    )
                    st.plotly_chart(fig_pie, use_container_width=True,
                                    config={"displayModeBar": False})

                with vendor_col:
                    st.markdown("#### Top Vendors")
                    vtab1, vtab2 = st.tabs(["By value", "By charges"])

                    with vtab1:
                        if "vendor_clean" in spend_df.columns:
                            spend_df["vendor"] = (spend_df["vendor_clean"]
                                                  .replace("nan", None).fillna(spend_df["name"])
                                                  .replace("", None).fillna(spend_df["name"]))
                        else:
                            spend_df["vendor"] = spend_df["name"]
                        spend_df["vendor"] = spend_df["vendor"].astype(str).str.strip()

                        by_value = (spend_df.groupby("vendor")["amount_abs"]
                                    .sum().sort_values(ascending=False).head(5).reset_index())
                        max_val  = by_value["amount_abs"].max()
                        rows_html = ""
                        for _, vrow in by_value.iterrows():
                            vname   = vrow["vendor"]
                            bar_pct = int(vrow["amount_abs"] / max_val * 100)
                            matched = spend_df[spend_df["vendor"] == vname]["category"].mode()
                            color   = CATEGORY_COLORS.get(
                                matched.iloc[0] if not matched.empty else "Other", "#6b7280")
                            rows_html += f"""
                            <div style="padding:10px 0;border-bottom:0.5px solid #1c1c28">
                              <div style="display:flex;justify-content:space-between;
                                          align-items:baseline;margin-bottom:5px">
                                <span style="font-size:.85rem;color:#F2EEE6;white-space:nowrap;
                                             overflow:hidden;text-overflow:ellipsis;max-width:65%">{vname}</span>
                                <span style="font-size:.85rem;font-family:'DM Sans',sans-serif;
                                             font-weight:300;color:#F2EEE6">${vrow["amount_abs"]:,.2f}</span>
                              </div>
                              <div style="background:#171720;border-radius:3px;height:4px">
                                <div style="width:{bar_pct}%;height:4px;border-radius:3px;background:{color}"></div>
                              </div>
                            </div>"""
                        st.markdown(rows_html, unsafe_allow_html=True)

                    with vtab2:
                        by_count = (spend_df.groupby("vendor")
                                    .agg(charges=("amount_abs", "count"), total=("amount_abs", "sum"))
                                    .sort_values("charges", ascending=False)
                                    .head(5).reset_index())
                        max_count = by_count["charges"].max()
                        rows_html = ""
                        for _, vrow in by_count.iterrows():
                            bar_pct = int(vrow["charges"] / max_count * 100)
                            matched = spend_df[spend_df["vendor"] == vrow["vendor"]]["category"].mode()
                            color   = CATEGORY_COLORS.get(
                                matched.iloc[0] if not matched.empty else "Other", "#6b7280")
                            rows_html += f"""
                            <div style="padding:10px 0;border-bottom:0.5px solid #1c1c28">
                              <div style="display:flex;justify-content:space-between;
                                          align-items:baseline;margin-bottom:5px">
                                <span style="font-size:.85rem;color:#F2EEE6">{vrow["vendor"]}</span>
                                <span style="font-size:.85rem;color:#888">{int(vrow["charges"])} charge{"s" if vrow["charges"] != 1 else ""}</span>
                              </div>
                              <div style="background:#171720;border-radius:3px;height:4px">
                                <div style="width:{bar_pct}%;height:4px;border-radius:3px;background:{color}"></div>
                              </div>
                            </div>"""
                        st.markdown(rows_html, unsafe_allow_html=True)

                    # ── Save report ───────────────────────────────────────────
                    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
                    st.markdown("#### Save Report")
                    if not uid:
                        st.markdown("<p style='color:#888;font-size:.85rem;margin:0'>Sign in to save reports.</p>",
                                    unsafe_allow_html=True)
                    else:
                        with st.form("save_report_form", border=False):
                            report_label = st.text_input(
                                "Label", placeholder="e.g. March 2026",
                                label_visibility="collapsed", key="report_label")
                            sv1, sv2 = st.columns(2)
                            with sv1:
                                period_start = st.date_input("From", value=None,
                                                             format="DD/MM/YYYY",
                                                             key="period_start")
                            with sv2:
                                period_end = st.date_input("To", value=None,
                                                           format="DD/MM/YYYY",
                                                           key="period_end")
                            submitted = st.form_submit_button(
                                "Save report", use_container_width=True, type="primary")

                        if submitted:
                            ps_str = str(period_start) if period_start else None
                            pe_str = str(period_end)   if period_end   else None
                            if not report_label.strip():
                                st.warning("Enter a label.")
                            elif ps_str and pe_str and check_duplicate_report(uid, ps_str, pe_str):
                                st.warning("⚠️ Overlapping report already exists.")
                            else:
                                _rows = st.session_state.get("tx_rows", [])
                                for _i in range(len(_rows)):
                                    _rows[_i]["date"]         = st.session_state.get(f"td_{_i}_date", _rows[_i].get("date", ""))
                                    _rows[_i]["vendor_clean"] = st.session_state.get(f"td_{_i}_name", _rows[_i].get("vendor_clean", ""))
                                    _rows[_i]["name"]         = _rows[_i].get("name", _rows[_i]["vendor_clean"])
                                    _rows[_i]["amount"]       = st.session_state.get(f"td_{_i}_amt", _rows[_i].get("amount", 0))
                                    _rows[_i]["category"]     = st.session_state.get(f"td_{_i}_cat", _rows[_i].get("category", "Other"))
                                save_data = []
                                for row in _rows:
                                    try:
                                        amt = float(str(row.get("amount", 0)).replace("$", "").replace(",", "").strip() or 0)
                                    except (ValueError, TypeError):
                                        amt = 0.0
                                    vc = row.get("vendor_clean") or ""
                                    if str(vc).lower() in ("nan", "none", ""):
                                        vc = row.get("name", "")
                                    save_data.append({
                                        "date":         str(row.get("date", "")),
                                        "name":         str(row.get("name", "") or ""),
                                        "vendor_clean": str(vc),
                                        "amount":       amt,
                                        "category":     str(row.get("category", "Other")),
                                    })
                                _profile  = get_profile(uid)
                                _tier     = _profile.get("subscription_tier", "free_trial")
                                _tier_req = "free" if _tier == "free_trial" else _tier
                                ok, err = save_report(
                                    uid, report_label.strip(), ps_str, pe_str,
                                    save_data, tier_required=_tier_req,
                                    ai_insight=st.session_state.get("_insight_to_save"),
                                )
                                if ok:
                                    st.success("✅ Report saved!")
                                else:
                                    st.error(f"Could not save: {err}")

        if new_cats_needed:
            st.markdown('<div class="info-box blue">You selected <b>＋ Add new category…</b> — '
                        'enter the name below, then save.</div>', unsafe_allow_html=True)
            nc1, nc2 = st.columns([4, 1])
            with nc1:
                inline_cat_name = st.text_input("New category name",
                                                 placeholder="e.g. Pet Care",
                                                 key="inline_cat_name")
            with nc2:
                st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                if st.button("Save", type="primary", use_container_width=True,
                             key="save_inline_cat"):
                    name = inline_cat_name.strip()
                    if not name:
                        st.warning("Enter a category name.")
                    elif not uid:
                        st.warning("Sign in to save categories.")
                    else:
                        ok, err = save_category(uid, name)
                        if ok:
                            for i in new_cats_needed:
                                rows[i]["category"] = name
                                vendor = str(rows[i].get("name", "")).strip()
                                if vendor and vendor.lower() not in ("", "other"):
                                    save_vendor_rule(uid, vendor, name, "contains")
                            st.session_state.tx_rows = rows
                            st.success(f"✅ '{name}' added!")
                            st.rerun()
                        else:
                            st.error(f"Could not save: {err}")

        if vendor_rule_queue:
            st.markdown(
                f'<div class="info-box green">✅ {len(vendor_rule_queue)} vendor rule'
                f'{"s" if len(vendor_rule_queue) != 1 else ""} saved automatically. '
                f'Manage in <a href="/settings" target="_self" style="color:#2e8f66">Settings</a>.</div>',
                unsafe_allow_html=True)

        st.markdown("---")
        d1, d2, d3 = st.columns(3)
        with d1:
            csv = (df_edited.copy()
                   .assign(amount=df_edited["amount"].map(lambda x: f"${x:+,.2f}"))
                   .to_csv(index=False))
            st.download_button("⬇️ Download CSV", data=csv,
                               file_name="expenses.csv", mime="text/csv",
                               use_container_width=True)
        with d2:
            if st.session_state.redacted_pdf_bytes:
                st.download_button("⬇️ Download redacted PDF",
                                   data=st.session_state.redacted_pdf_bytes,
                                   file_name="redacted_statement.pdf",
                                   mime="application/pdf",
                                   use_container_width=True)
            else:
                st.caption("📋 Demo mode — no PDF to download")
        with d3:
            if st.button("🔄 Start over", use_container_width=True):
                for k in ["step", "pdf_bytes", "redacted_pdf_bytes", "annotations",
                          "pending", "page_num", "transactions", "categorized",
                          "tx_rows", "tx_rows_source", "_tx_pending_delete", "_tx_pending_add"]:
                    st.session_state.pop(k, None)
                for k in list(st.session_state.keys()):
                    if k.startswith("td_"):
                        del st.session_state[k]
                render_page_b64.clear()
                st.rerun()
