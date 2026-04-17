import streamlit as st
import fitz
import pdfplumber
import io
import base64
import json
import plotly.graph_objects as go
import google.generativeai as genai
import pandas as pd
from auth import require_auth, get_user, clear_session, get_supabase
from db import (
    can_analyse, increment_usage, get_profile, TIER_LABELS, TIER_LIMITS,
    load_categories, save_category, delete_category,
    load_vendor_rules, apply_vendor_rules, save_vendor_rule, delete_vendor_rule,
    save_report, load_reports, load_report_items, delete_report, check_duplicate_report,
    DEFAULT_CATEGORY_COLORS,
)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Expense Categorizer", page_icon="💳", layout="wide")

# ── Auth check before anything renders ────────────────────────────────────────
# Show a branded loading screen immediately, then redirect if not logged in.
# This prevents the upload page flashing before the login redirect.
from auth import is_logged_in
if not is_logged_in():
    st.markdown("""
    <style>
      html, body, .stApp { background-color:#0f0f13; }
      #MainMenu, footer, header { visibility:hidden; }
      [data-testid="stSidebar"] { display:none; }
      [data-testid="stToolbar"] { display:none; }
    </style>
    <div style="display:flex;flex-direction:column;align-items:center;
                justify-content:center;height:100vh;background:#0f0f13">
      <div style="font-family:'DM Sans',sans-serif;font-size:2.4rem;font-weight:700;
                  font-style:italic;color:#f0c040;letter-spacing:.04em;margin-bottom:16px">
        CATEGORIZ
      </div>
      <div style="color:#555;font-size:.9rem">Loading...</div>
    </div>
    """, unsafe_allow_html=True)
    st.switch_page("pages/1_login.py")
    st.stop()

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500;600&display=swap');

  html, body, .stApp { font-family: 'DM Sans', sans-serif; background-color: #0f0f13; color: #e8e6e1; }

  /* Remove Streamlit header bar */
  [data-testid="stHeader"] { display: none !important; }
  /* Remove the gap the header leaves behind */
  .block-container { padding-top: 1rem !important; }
  /* Remove sidebar top decoration and collapse button */
  [data-testid="stSidebarHeader"] { display: none !important; }
  [data-testid="collapsedControl"] { display: none !important; }
  /* Remove gap at top of sidebar content */
  section[data-testid="stSidebar"] > div { padding-top: 1rem !important; }

  /* Sidebar */
  section[data-testid="stSidebar"] { background: #17171d !important; border-right: 1px solid #2a2a35; }
  section[data-testid="stSidebar"] * { color: #c9c7c0 !important; }
  /* Hide auto-generated page list */
  [data-testid="stSidebarNav"] { display: none !important; }
  /* Hide the settings/hamburger menu to prevent theme switching */
  #MainMenu { visibility: hidden !important; }
  [data-testid="stToolbar"] { display: none !important; }
  /* Upgrade button — yellow bg needs black text */
  section[data-testid="stSidebar"] button[kind="primary"] { color: #0f0f13 !important; }
  section[data-testid="stSidebar"] button[kind="primary"] * { color: #0f0f13 !important; }
  section[data-testid="stSidebar"] button[kind="primary"] p { color: #0f0f13 !important; }
  /* No scrollbar on sidebar */
  section[data-testid="stSidebar"] > div { overflow: hidden !important; }
  /* Flex layout: top / middle / bottom */
  section[data-testid="stSidebar"] > div > div[data-testid="stVerticalBlock"] {
      display: flex !important;
      flex-direction: column !important;
      height: 100vh !important;
  }
  div[data-testid="stSidebarUserContent"] {
      display: flex !important;
      flex-direction: column !important;
      height: 100% !important;
  }
  section[data-testid="stSidebar"] .stSelectbox label,
  section[data-testid="stSidebar"] .stSlider label { color: #888 !important; }

  /* Step badges */
  .step-badge {
    display:inline-flex; align-items:center; gap:10px;
    background:#1e1e28; border:1px solid #2e2e3e;
    border-radius:12px; padding:14px 20px; margin-bottom:12px; width:100%;
  }
  .step-num {
    width:28px; height:28px; border-radius:50%;
    background:#f0c040; color:#0f0f13;
    font-weight:700; font-size:13px;
    display:flex; align-items:center; justify-content:center; flex-shrink:0;
  }
  .step-num.done { background:#34d399; }
  .step-num.active { background:#f0c040; box-shadow: 0 0 12px rgba(240,192,64,0.4); }
  .step-text { font-size:14px; color:#c9c7c0; line-height:1.4; }
  .step-text b { color:#e8e6e1; }

  /* Info boxes */
  .info-box {
    background:#1a1a24; border-left:3px solid #f0c040;
    padding:.7rem 1rem; border-radius:6px;
    font-size:.85rem; color:#aaa; margin-bottom:.75rem;
  }
  .info-box.green { border-left-color:#34d399; background:#0f1f1a; }
  .info-box.blue  { border-left-color:#60a5fa; background:#0f1624; }
  .info-box.red   { border-left-color:#f87171; background:#1f0f0f; }

  /* Cards */
  .card {
    background:#1e1e28; border:1px solid #2a2a38;
    border-radius:12px; padding:20px; margin-bottom:16px;
  }
  .card h3 { margin:0 0 4px; font-size:1rem; color:#e8e6e1; }
  .card p  { margin:0; font-size:.82rem; color:#888; }

  /* Metric strip */
  .metric-strip { display:flex; gap:12px; margin-bottom:16px; flex-wrap:wrap; }
  .metric {
    background:#1e1e28; border:1px solid #2a2a38;
    border-radius:10px; padding:14px 18px; flex:1; min-width:120px;
  }
  .metric .val { font-size:1.5rem; font-weight:600; font-family:'DM Mono',monospace; color:#f0c040; }
  .metric .lbl { font-size:.75rem; color:#666; margin-top:2px; }

  /* Category pill */
  .pill {
    display:inline-block; padding:2px 10px; border-radius:20px;
    font-size:.75rem; font-weight:500; background:#2a2a38; color:#c9c7c0;
  }

  /* Redact warning */
  .redact-warn {
    background:#1f1008; border:1px solid #f59e0b44;
    border-radius:8px; padding:12px 16px; font-size:.83rem; color:#d97706;
    margin-bottom:12px;
  }

  /* Override Streamlit dataframe for dark theme */
  .stDataFrame { border-radius:8px; overflow:hidden; }

  /* Custom expense table */
  .tx-table { width:100%; border-collapse:collapse; margin-bottom:0; }
  .tx-table th {
    background:#17171d; color:#666; font-size:.75rem; font-weight:500;
    padding:8px 10px; text-align:left; border-bottom:1px solid #2a2a38;
    text-transform:uppercase; letter-spacing:.04em;
  }
  .tx-table td { padding:2px 4px; border-bottom:1px solid #1e1e28; vertical-align:middle; }
  .tx-table tr:hover td { background:#1a1a24; }
  .tx-table tr:last-child td { border-bottom:none; }

  /* Make inputs inside table rows look flush */
  .tx-table .stTextInput input {
    background:transparent !important; border:none !important;
    border-radius:0 !important; padding:6px 6px !important;
    font-size:.85rem !important; color:#e8e6e1 !important;
  }
  .tx-table .stTextInput input:focus {
    background:#1e1e28 !important; border-radius:4px !important;
    box-shadow:none !important;
  }
  .tx-table .stSelectbox > div > div {
    background:transparent !important; border:none !important;
    font-size:.85rem !important;
  }
  /* Delete button — small, subtle red */
  .tx-table .del-btn button {
    background:transparent !important; border:none !important;
    color:#666 !important; font-size:.9rem !important;
    padding:4px 8px !important; min-height:0 !important;
    line-height:1 !important; width:100% !important;
  }
  .tx-table .del-btn button:hover { color:#f87171 !important; background:#1f0f0f !important; }

  /* Add transaction button */
  .add-tx-btn button {
    background:#1e1e28 !important; border:1px dashed #2a2a38 !important;
    color:#888 !important; border-radius:8px !important;
    font-size:.85rem !important; transition: all .15s !important;
  }
  .add-tx-btn button:hover {
    border-color:#f0c040 !important; color:#f0c040 !important;
    background:#1e1e24 !important;
  }

  /* Buttons */
  .stButton button {
    border-radius:8px !important; font-weight:500 !important;
    transition: all .15s !important;
  }
  .stButton button[kind="primary"] {
    background:#f0c040 !important; color:#0f0f13 !important; border:none !important;
  }
  .stButton button[kind="primary"]:hover { background:#e5b830 !important; }

  /* Download button */
  .stDownloadButton button {
    background:#1e1e28 !important; border:1px solid #2a2a38 !important;
    color:#e8e6e1 !important; border-radius:8px !important;
  }
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
COLORS_RGB = {
    "Yellow": (1,1,0), "Green":(0,1,0.4),
    "Cyan":(0,0.9,1),  "Pink":(1,0.4,0.7), "Orange":(1,0.6,0),
}
COLORS_FILL = {
    "Yellow":"rgba(255,255,0,0.35)",  "Green":"rgba(0,255,100,0.35)",
    "Cyan":"rgba(0,220,255,0.35)",    "Pink":"rgba(255,100,180,0.35)",
    "Orange":"rgba(255,153,0,0.35)",
}
DEMO_DATA = [
    {"date": "01 Apr 2026", "name": "DANG GOOD CAFE",                "vendor_clean": "Dang Good Cafe",    "amount": -4.55,    "category": "Food & Dining"},
    {"date": "01 Apr 2026", "name": "STOMPING GROUND BREWIN",        "vendor_clean": "Stomping Ground",   "amount": -22.37,   "category": "Food & Dining"},
    {"date": "01 Apr 2026", "name": "Unknown",                       "vendor_clean": None,                "amount": -13.00,   "category": "Unknown"},
    {"date": "02 Apr 2026", "name": "AMPOL KEW 33261F",              "vendor_clean": "Ampol",             "amount": -58.77,   "category": "Transport"},
    {"date": "03 Apr 2026", "name": "WOOLWORTHS/18 WALPOLE ST",      "vendor_clean": "Woolworths",        "amount": -7.90,    "category": "Shopping"},
    {"date": "04 Apr 2026", "name": "AMPOL KEW 33261F",              "vendor_clean": "Ampol",             "amount": -2.00,    "category": "Transport"},
    {"date": "04 Apr 2026", "name": "Kindle Unltd",                  "vendor_clean": "Kindle Unlimited",  "amount": -13.99,   "category": "Subscriptions"},
    {"date": "04 Apr 2026", "name": "CANVA* I04841-0173708",         "vendor_clean": "Canva",             "amount": -20.00,   "category": "Subscriptions"},
    {"date": "05 Apr 2026", "name": "Spotify P411178B22",            "vendor_clean": "Spotify",           "amount": -15.99,   "category": "Subscriptions"},
    {"date": "05 Apr 2026", "name": "WOOLWORTHS/18 WALPOLE ST",      "vendor_clean": "Woolworths",        "amount": -83.10,   "category": "Shopping"},
    {"date": "07 Apr 2026", "name": "AMPOL KEW 33261F",              "vendor_clean": "Ampol",             "amount": -64.52,   "category": "Transport"},
    {"date": "07 Apr 2026", "name": "ZLR*Seven Creeks Hotel",        "vendor_clean": "Seven Creeks Hotel","amount": -25.08,   "category": "Food & Dining"},
    {"date": "07 Apr 2026", "name": "Transfer from Savings Maximiser","vendor_clean": "Transfer",         "amount": 3000.00,  "category": "Income"},
    {"date": "07 Apr 2026", "name": "Unknown",                       "vendor_clean": None,                "amount": -2450.00, "category": "Unknown"},
    {"date": "07 Apr 2026", "name": "Unknown",                       "vendor_clean": None,                "amount": -400.00,  "category": "Unknown"},
    {"date": "08 Apr 2026", "name": "AMPOL TALLAROOK 30026F",        "vendor_clean": "Ampol",             "amount": -11.00,   "category": "Transport"},
    {"date": "08 Apr 2026", "name": "DANG GOOD CAFE",                "vendor_clean": "Dang Good Cafe",    "amount": -17.60,   "category": "Food & Dining"},
]

# CATEGORY_COLORS now lives in db.py as DEFAULT_CATEGORY_COLORS
CATEGORY_COLORS = DEFAULT_CATEGORY_COLORS

# ── Session state ─────────────────────────────────────────────────────────────
for k,v in [
    ("step", 1),
    ("pdf_bytes", None),
    ("redacted_pdf_bytes", None),
    ("annotations", {}),
    ("pending", None),
    ("page_num", 0),
    ("zoom", 1.5),
    ("transactions", None),
    ("categorized", False),
]:
    if k not in st.session_state:
        st.session_state[k] = v

# ── Helpers ───────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def render_page_b64(pdf_bytes, page_num, zoom):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pix = doc[page_num].get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    doc.close()
    return base64.b64encode(pix.tobytes("png")).decode(), pix.width, pix.height

def snap_to_words(pdf_bytes, page_num, rect):
    x0,y0,x1,y1 = rect
    hits = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for w in (pdf.pages[page_num].extract_words() or []):
            if w["x0"]<x1 and w["x1"]>x0 and w["top"]<y1 and w["bottom"]>y0:
                hits.append((w["x0"],w["top"],w["x1"],w["bottom"]))
    if not hits:
        return rect
    return min(h[0] for h in hits),min(h[1] for h in hits),max(h[2] for h in hits),max(h[3] for h in hits)

def apply_redactions(original_bytes, annotations):
    """Burn redactions into a new PDF bytes object."""
    doc = fitz.open(stream=original_bytes, filetype="pdf")
    for pn_str, ann_list in annotations.items():
        page = doc[int(pn_str)]
        for ann in [a for a in ann_list if a["type"]=="redact"]:
            page.add_redact_annot(fitz.Rect(*ann["rect"]), fill=(0,0,0))
        page.apply_redactions()
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()

def extract_text_all_pages(pdf_bytes):
    """Extract text from all pages of a PDF."""
    text = ""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for i, page in enumerate(pdf.pages):
            t = page.extract_text()
            if t:
                text += f"\n--- Page {i+1} ---\n{t}"
    return text.strip()

def make_figure(b64, img_w, img_h, annotations, pending, zm):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[0,img_w],y=[0,img_h],mode="markers",
                             marker=dict(opacity=0),showlegend=False,hoverinfo="none"))
    fig.add_layout_image(dict(
        source=f"data:image/png;base64,{b64}",
        xref="x",yref="y",x=0,y=img_h,
        sizex=img_w,sizey=img_h,sizing="stretch",layer="below",
    ))
    shapes = []
    for ann in annotations:
        px0,py0,px1,py1 = ann["rect"]
        cx0,cx1 = px0*zm, px1*zm
        cy_top, cy_bottom = img_h-py0*zm, img_h-py1*zm
        fill = "rgba(0,0,0,1)" if ann["type"]=="redact" else COLORS_FILL.get(ann["color"],"rgba(255,255,0,0.35)")
        shapes.append(dict(type="rect",xref="x",yref="y",
                           x0=cx0,x1=cx1,y0=cy_bottom,y1=cy_top,
                           fillcolor=fill,line=dict(width=0),layer="above"))
    if pending:
        px0,py0,px1,py1 = pending
        shapes.append(dict(type="rect",xref="x",yref="y",
                           x0=px0*zm,x1=px1*zm,y0=img_h-py1*zm,y1=img_h-py0*zm,
                           fillcolor="rgba(248,113,113,0.15)",
                           line=dict(width=2,color="rgba(248,113,113,0.8)",dash="dot"),
                           layer="above"))
    fig.update_layout(
        width=img_w,height=img_h,margin=dict(l=0,r=0,t=0,b=0),
        xaxis=dict(range=[0,img_w],showgrid=False,zeroline=False,showticklabels=False,fixedrange=False),
        yaxis=dict(range=[0,img_h],showgrid=False,zeroline=False,showticklabels=False,scaleanchor="x",fixedrange=False),
        dragmode="select", selectdirection="any",
        newselection=dict(
            line=dict(color="rgba(220,50,50,0.9)", width=2, dash="dot"),
        ),
        selections=[dict(
            type="rect",
            line=dict(color="rgba(220,50,50,0.9)", width=2, dash="dot"),
            fillcolor="rgba(220,50,50,0.1)",
        )] if False else [],  # placeholder; actual selections driven by on_select
        shapes=shapes,plot_bgcolor="#1a1a1a",paper_bgcolor="#1a1a1a",
    )
    return fig

def categorize_with_gemini(text, all_categories: dict, vendor_rules: list):
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel("gemini-3.1-flash-lite-preview")
    cat_list = ", ".join(all_categories.keys())
    prompt = f"""Extract ALL transactions from this bank statement text.
Return ONLY a JSON array. Each object must have exactly these keys:
- "date"         (string, e.g. "01 Mar 2026")
- "name"         (string, the raw transaction description exactly as it appears)
- "vendor_clean" (string, a clean human-readable vendor name — e.g. "Ampol" from "AMPOL SUBIACO 44321F",
                  "Netflix" from "NETFLIX 3421987234", "Woolworths" from "WOOLWORTHS/18 WALPOLE ST".
                  For transfers, salary, or transactions with no clear vendor use the raw name as-is.
                  For redacted entries use null.)
- "amount"       (number, negative=debit/expense, positive=credit/income)
- "category"     (one of: {cat_list}. Use "Unknown" if unclear.)

Rules:
- Include every transaction, including income, transfers, and redacted rows.
- Do not skip or merge any transactions.
- vendor_clean should be a short recognisable brand/company name, not a description.

Bank statement text:
{text}
"""
    response = model.generate_content(
        prompt,
        generation_config={"response_mime_type": "application/json"}
    )
    raw = response.text.strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:-1])
    transactions = json.loads(raw)
    # Apply vendor rules on top of AI categorization
    for t in transactions:
        matched = apply_vendor_rules(vendor_rules, t.get("name", ""))
        if matched:
            t["category"] = matched
    return transactions

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    # Top: Home button
    if st.button("⌂ Home", use_container_width=True):
        for k in ["step","pdf_bytes","redacted_pdf_bytes","annotations",
                  "pending","page_num","transactions","categorized",
                  "tx_rows","tx_rows_source","_tx_pending_delete","_tx_pending_add",
                  "_is_demo","_insight_to_save"]:
            st.session_state.pop(k, None)
        for k in [k for k in st.session_state if k.startswith("td_")]:
            del st.session_state[k]
        render_page_b64.clear()
        st.rerun()

    # Step progress — sits directly under the Home button, no offset
    st.markdown("<div style='padding-top:1rem'>", unsafe_allow_html=True)
    steps = [
        (1, "Upload statement"),
        (2, "Redact private info"),
        (3, "Categorize expenses"),
    ]
    for num, label in steps:
        cls = "done" if st.session_state.step > num else ("active" if st.session_state.step == num else "")
        icon = "✓" if st.session_state.step > num else str(num)
        st.markdown(f"""<div class="step-badge">
            <div class="step-num {cls}">{icon}</div>
            <div class="step-text"><b>{label}</b></div>
        </div>""", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # Redaction defaults (controls removed from sidebar)
    color = "Yellow"
    snap  = True
    zoom  = st.session_state.zoom

# ── Header ────────────────────────────────────────────────────────────────────
# ── Auth guard ───────────────────────────────────────────────────────────────
require_auth()

# ── User menu — anchored to bottom of sidebar ────────────────────────────────
user = get_user()
if user:
    email  = user.email if hasattr(user, "email") else user.get("email", "")
    uid_sb = user.id if hasattr(user, "id") else user.get("id") if user else None
    from db import get_profile, TIER_LABELS, TIER_LIMITS
    profile    = get_profile(uid_sb) if uid_sb else {}
    tier       = profile.get("subscription_tier", "free_trial")
    used       = profile.get("analyses_used", 0)
    limit      = profile.get("analyses_limit", 3)
    TIER_COLORS = {"free_trial":"#666","starter":"#3b82f6","unlimited":"#f0c040"}
    tier_color = TIER_COLORS.get(tier, "#666")
    tier_label = TIER_LABELS.get(tier, "Free Trial")
    if tier == "unlimited":
        usage_str = "Unlimited analyses"
    elif tier == "free_trial":
        usage_str = f"{used}/3 lifetime analyses"
    else:
        usage_str = f"{used}/{limit} analyses this month"

    with st.sidebar.container(key="sidebar_bottom"):
        st.markdown(f"<p style='color:#888;font-size:.8rem;margin-bottom:2px'>Signed in as</p>",
                    unsafe_allow_html=True)
        st.markdown(f"<p style='color:#e8e6e1;font-size:.85rem;font-weight:500;"
                    f"word-break:break-all;margin-bottom:8px'>{email}</p>",
                    unsafe_allow_html=True)
        st.markdown(f"""
        <div style="background:#1a1a24;border:1px solid #2a2a38;border-radius:8px;
                    padding:8px 12px;margin-bottom:10px">
          <span style="font-size:11px;font-weight:600;color:{tier_color};
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
        if st.button("📂 Saved Reports", use_container_width=True):
            st.switch_page("pages/4_reports.py")
        if st.button("⚙ Settings", use_container_width=True):
            st.switch_page("pages/6_settings.py")
        if st.button("Sign out", use_container_width=True):
            try:
                get_supabase().auth.sign_out()
            except Exception:
                pass
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

st.markdown("""
<div style="padding:12px 0 4px">
  <span style="font-family:'DM Sans',sans-serif;font-size:2.4rem;font-weight:700;
               font-style:italic;color:#f0c040;letter-spacing:.04em">CATEGORIZ</span>
</div>
""", unsafe_allow_html=True)
if st.session_state.step == 1:
    st.markdown("*AI-powered bank statement analysis with privacy-first redaction*")
    st.markdown("---")

# ═══════════════════════════════════════════════════════════
# STEP 1 + 2 — Upload & Redact (single combined page)
# ═══════════════════════════════════════════════════════════
if st.session_state.step in (1, 2):

    pdf_loaded = st.session_state.pdf_bytes is not None

    # ── Top action bar (always visible once PDF loaded) ───────────────────
    if pdf_loaded:
        pdf_bytes = st.session_state.pdf_bytes
        doc_tmp = fitz.open(stream=pdf_bytes, filetype="pdf")
        n_pages = len(doc_tmp); doc_tmp.close()
        pn = st.session_state.page_num
        zm = st.session_state.zoom
        pk = str(pn)
        rd_total = sum(len(v) for v in st.session_state.annotations.values())

        # ── Toolbar: redact, undo, categorize, reset ─────────────────────
        st.markdown("#### 2. Redaction tool")
        bar1, bar2, bar3, bar4 = st.columns([2, 2, 2, 1])
        with bar1:
            redact_btn = st.button(
                "⬛ Redact Selection  [R]",
                use_container_width=True,
                disabled=st.session_state.pending is None,
            )
        with bar2:
            undo_btn = st.button(
                "↩️ Undo Last  [U]",
                use_container_width=True,
                disabled=not st.session_state.annotations.get(pk),
            )
        with bar3:
            analyse_btn = st.button(
                "🤖 Categorize Transactions",
                use_container_width=True, type="primary",
            )
        with bar4:
            if st.button("✕ Reset", use_container_width=True):
                st.session_state.pdf_bytes = None
                st.session_state.annotations = {}
                st.session_state.pending = None
                st.session_state.page_num = 0
                st.session_state.step = 1
                render_page_b64.clear()
                st.rerun()

        # Pending selection status
        if st.session_state.pending:
            st.markdown('<div class="info-box red">🔴 Selection ready — click <b>Redact Selection</b> to black it out</div>', unsafe_allow_html=True)
        else:
            rd_count_pg = len(st.session_state.annotations.get(pk, []))
            status = f"⬛ {rd_count_pg} redaction{'s' if rd_count_pg!=1 else ''} on this page" if rd_count_pg else "🖱️ Drag on the document to select an area to redact"
            st.markdown(f'<div class="info-box">{status}</div>', unsafe_allow_html=True)

        # ── Page nav — below info box, centred over A4 document ─────────────
        # Left padding col shifts the group ~10% right from the left edge.
        # Arrow buttons are narrow (0.4), page count wider (1) for readability.
        _, nav1, nav2, nav3, _ = st.columns([1, 0.4, 1, 0.4, 3])
        with nav1:
            if st.button("◀", use_container_width=True, disabled=pn == 0,
                         key="pg_prev"):
                st.session_state.page_num -= 1
                st.session_state.pending = None
                st.rerun()
        with nav2:
            st.markdown(
                f"<p style='text-align:center;margin:6px 0;font-size:.85rem;"
                f"color:#888'>{pn+1} / {n_pages}</p>",
                unsafe_allow_html=True,
            )
        with nav3:
            if st.button("▶", use_container_width=True,
                         disabled=pn == n_pages - 1, key="pg_next"):
                st.session_state.page_num += 1
                st.session_state.pending = None
                st.rerun()

        # Handle button actions
        if redact_btn:
            if st.session_state.pending:
                x0,y0,x1,y1 = st.session_state.pending
                if snap:
                    x0,y0,x1,y1 = snap_to_words(pdf_bytes, pn, (x0,y0,x1,y1))
                st.session_state.annotations.setdefault(pk,[]).append(
                    {"rect":[x0,y0,x1,y1],"color":"black","type":"redact"})
                st.session_state.pending = None
                st.rerun()

        if undo_btn:
            if st.session_state.annotations.get(pk):
                st.session_state.annotations[pk].pop()
                if not st.session_state.annotations[pk]:
                    del st.session_state.annotations[pk]
            st.session_state.pending = None
            st.rerun()

        if analyse_btn:
            with st.spinner("Applying redactions…"):
                if st.session_state.annotations:
                    st.session_state.redacted_pdf_bytes = apply_redactions(
                        pdf_bytes, st.session_state.annotations)
                else:
                    st.session_state.redacted_pdf_bytes = pdf_bytes
            st.session_state.step = 3
            st.session_state.categorized = False
            st.rerun()

        # ── Keyboard shortcuts ────────────────────────────────────────────────
        # Inject a JS listener into the Streamlit parent page.
        # 'r' clicks the Redact button, 'u' clicks Undo.
        # We match buttons by their visible text content so it's label-stable.
        import streamlit.components.v1 as components
        components.html("""
<script>
(function() {
  // Only register once
  if (window._redactKeysRegistered) return;
  window._redactKeysRegistered = true;

  function clickButtonByText(text) {
    const doc = window.parent.document;
    const btns = doc.querySelectorAll('button[kind="primary"], button[kind="secondary"], button');
    for (const btn of btns) {
      if (btn.innerText.trim().includes(text) && !btn.disabled) {
        btn.click();
        return true;
      }
    }
    return false;
  }

  window.parent.document.addEventListener('keydown', function(e) {
    // Ignore if user is typing in an input/textarea
    const tag = e.target.tagName.toLowerCase();
    if (tag === 'input' || tag === 'textarea' || e.target.isContentEditable) return;

    if (e.key === 'r' || e.key === 'R') {
      e.preventDefault();
      clickButtonByText('Redact Selection');
    }
    if (e.key === 'u' || e.key === 'U') {
      e.preventDefault();
      clickButtonByText('Undo Last');
    }
  });
})();
</script>
""", height=0)

        # ── PDF viewer ────────────────────────────────────────────────────
        b64, img_w, img_h = render_page_b64(pdf_bytes, pn, zm)
        fig = make_figure(b64, img_w, img_h,
                          st.session_state.annotations.get(pk, []),
                          st.session_state.pending, zm)

        event = st.plotly_chart(fig, use_container_width=False,
                                key=f"chart_{pn}_{zm}",
                                on_select="rerun", selection_mode=["box"])

        # Parse box-select → PDF coords
        try:
            box = (event.selection.box or [{}])[0]
            xs, ys = box.get("x",[]), box.get("y",[])
            if len(xs)>=2 and len(ys)>=2:
                new = (min(xs)/zm, (img_h-max(ys))/zm, max(xs)/zm, (img_h-min(ys))/zm)
                if new != st.session_state.pending:
                    st.session_state.pending = new
                    st.rerun()
        except Exception:
            pass

    # ── Upload area + info cards (hidden once PDF is loaded) ──────────────
    if not pdf_loaded:
        up_col, info_col = st.columns([2, 1])

        with up_col:
            st.markdown("### 1. Upload your bank statement")
            st.markdown('<div class="info-box">Upload a PDF bank statement. You can redact sensitive information (account numbers, BSB, personal details) before the AI reads it.</div>', unsafe_allow_html=True)
            uploaded = st.file_uploader("Upload PDF", type=["pdf"],
                                        label_visibility="visible")
            if uploaded:
                b = uploaded.read()
                if b != st.session_state.pdf_bytes:
                    st.session_state.pdf_bytes = b
                    st.session_state.annotations = {}
                    st.session_state.pending = None
                    st.session_state.transactions = None
                    st.session_state.categorized = False
                    st.session_state.step = 2
                    render_page_b64.clear()
                    st.rerun()
            st.markdown("---")
            st.markdown('<p style="color:#555;font-size:.8rem;margin-bottom:8px">⚡ DEVELOPER SHORTCUT</p>', unsafe_allow_html=True)
            if st.button("📋 Load Demo Expenses", use_container_width=True):
                st.session_state.transactions = DEMO_DATA
                st.session_state.categorized = True
                st.session_state.redacted_pdf_bytes = None
                st.session_state.annotations = {}
                st.session_state.step = 3
                st.session_state._is_demo = True
                st.rerun()

        with info_col:
            st.markdown("### How it works")
            st.markdown("""<div class="card">
                <h3>🔒 Privacy first</h3>
                <p>Before the AI reads anything, you can black out sensitive details such as account numbers, BSBs, names, addresses, or anything else you'd rather keep private. Redacted areas are permanently removed from the document the AI receives. We don't store your PDF at any point.</p>
            </div>
            <div class="card">
                <h3>🤖 AI categorization</h3>
                <p>Our AI then categorizes each transaction within your statement. You can add your own custom categories, edit any categorization, and set vendor rules so your regular merchants are always categorized correctly in future uploads.</p>
            </div>
            <div class="card">
                <h3>📊 Instant insights</h3>
                <p>See a top level view of your spending and also review the detailed list of your transactions. Add or remove transactions manually, then save the report to your account so you can come back and compare month over month.</p>
            </div>""", unsafe_allow_html=True)

    # File uploader still needed when PDF is loaded (hidden label)
    if pdf_loaded:
        uploaded = st.file_uploader("Upload PDF", type=["pdf"],
                                    label_visibility="collapsed")
        if uploaded:
            b = uploaded.read()
            if b != st.session_state.pdf_bytes:
                st.session_state.pdf_bytes = b
                st.session_state.annotations = {}
                st.session_state.pending = None
                st.session_state.transactions = None
                st.session_state.categorized = False
                st.session_state.step = 2
                render_page_b64.clear()
                st.rerun()

# ═══════════════════════════════════════════════════════════
# STEP 3 — Results (auto-runs AI on arrival)
# ═══════════════════════════════════════════════════════════
elif st.session_state.step == 3:
    run = not st.session_state.categorized

    if run:
        # ── Usage gate ────────────────────────────────────────────────────────
        user = get_user()
        uid  = user.id if hasattr(user,"id") else user.get("id") if user else None

        if uid:
            allowed, reason = can_analyse(uid)
            if not allowed:
                st.error(f"🔒 {reason}")
                profile = get_profile(uid)
                tier    = profile.get("subscription_tier", "free_trial")
                used    = profile.get("analyses_used", 0)
                limit   = profile.get("analyses_limit", 3)

                st.markdown(f"""
                <div style="background:#1a1a24;border:1px solid #2a2a38;border-radius:12px;
                            padding:20px 24px;margin:16px 0">
                  <p style="color:#666;font-size:.85rem;margin:0 0 12px">
                    Current plan: <b style="color:#e8e6e1">{TIER_LABELS.get(tier,'Free Trial')}</b>
                    &nbsp;·&nbsp; {used} / {'∞' if tier=='unlimited' else limit} analyses used
                  </p>
                  <p style="color:#e8e6e1;font-size:.95rem;margin:0">
                    Upgrade to keep categorizing your expenses.
                  </p>
                </div>
                """, unsafe_allow_html=True)

                if st.button("⚡ View upgrade options", type="primary"):
                    st.switch_page("pages/5_pricing.py")
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
                st.session_state.categorized = True
                # Increment usage counter after successful analysis
                if uid:
                    increment_usage(uid)
                st.session_state._is_demo = False
                st.session_state.pop("_insight_to_save", None)
            except Exception as e:
                st.error(f"Gemini error: {e}")
                st.stop()

    if st.session_state.categorized and st.session_state.transactions:
        data = st.session_state.transactions
        df = pd.DataFrame(data)

        # Parse amounts — handles raw floats (demo) and "$-1,234.56" strings (Gemini/CSV)
        def parse_amount(v):
            if isinstance(v, (int, float)): return float(v)
            s = str(v).replace(",","").replace("$","").replace("+","").strip()
            try: return float(s)
            except ValueError: return 0.0
        df["amount"] = df["amount"].map(parse_amount)

        # ── df_edited is built from tx_rows after the table renders below ─────
        # We use a placeholder here; it gets replaced with the real value after
        # the table section runs. For metrics we read from tx_rows directly.
        def parse_amount(v):
            if isinstance(v, (int, float)): return float(v)
            s = str(v).replace(",","").replace("$","").replace("+","").strip()
            try: return float(s)
            except ValueError: return 0.0

        # Placeholders — filled after the table renders with live df_edited
        _metrics_placeholder = st.empty()
        _insight_placeholder = st.empty()
        _charts_placeholder  = st.empty()

        # ── Category pie + vendor tables — rendered after table below ─────────
        # (cat_totals computed after sync loop; placeholder filled there)
        cat_totals = pd.Series(dtype=float)  # will be overwritten below

        # ── Transaction table ─────────────────────────────────────────────────
        st.markdown("#### All Transactions")

        user     = get_user()
        uid      = user.id if hasattr(user,"id") else user.get("id") if user else None
        all_cats = load_categories(uid) if uid else DEFAULT_CATEGORY_COLORS
        v_rules  = load_vendor_rules(uid) if uid else []
        cat_names = list(all_cats.keys())
        ADD_NEW_SENTINEL = "＋ Add new category…"
        cat_options = cat_names + [ADD_NEW_SENTINEL]

        # ── Row state ─────────────────────────────────────────────────────────
        # Use a hash of the raw transactions list as the stable source key.
        # id(df) changes every rerun because pandas creates a new object each
        # time — that was causing tx_rows to reset on every interaction.
        import hashlib as _hl
        _src_key = _hl.md5(
            json.dumps(st.session_state.transactions, default=str, sort_keys=True).encode()
        ).hexdigest()

        if "tx_rows" not in st.session_state or st.session_state.get("tx_rows_source") != _src_key:
            cols = ["date","name","amount","category"]
            if "vendor_clean" in df.columns:
                cols.append("vendor_clean")
            st.session_state.tx_rows = df[cols].copy().to_dict("records")
            st.session_state.tx_rows_source = _src_key

        # ── Handle pending actions set by callbacks ──────────────────────────
        if st.session_state.get("_tx_pending_delete") is not None:
            idx = st.session_state.pop("_tx_pending_delete")
            rows_before = st.session_state.tx_rows
            n = len(rows_before)
            if 0 <= idx < n:
                rows_before.pop(idx)
                # Shift data widget state keys above idx down by one.
                # Exclude _del keys — Streamlit forbids manual assignment
                # of button state and will error if you try.
                fields = ("date", "name", "amt", "cat")
                for j in range(idx, n - 1):
                    for f in fields:
                        src = f"td_{j+1}_{f}"
                        dst = f"td_{j}_{f}"
                        if src in st.session_state:
                            st.session_state[dst] = st.session_state[src]
                        elif dst in st.session_state:
                            del st.session_state[dst]
                # Remove the last row's stale data keys
                for f in fields:
                    st.session_state.pop(f"td_{n-1}_{f}", None)
                # Wipe all _del button keys — Streamlit will recreate them
                for k in [k for k in st.session_state if k.startswith("td_") and k.endswith("_del")]:
                    del st.session_state[k]
            st.rerun()

        if st.session_state.get("_tx_pending_add"):
            from datetime import date as _date
            st.session_state.tx_rows.append({
                "date":         _date.today().strftime("%d %b %Y"),
                "name":         "",
                "vendor_clean": "",
                "amount":       "",
                "category":     "Unknown",
            })
            st.session_state._tx_pending_add = False
            for k in [k for k in st.session_state if k.startswith("td_")]:
                del st.session_state[k]
            st.rerun()

        rows = st.session_state.tx_rows
        vendor_rule_queue = []
        new_cats_needed   = []

        # ── Render each row ───────────────────────────────────────────────────
        # IMPORTANT: we do NOT write widget values back to rows[] during render.
        # Widget state lives in st.session_state under td_{i}_* keys.
        # We only sync back to tx_rows when delete/add fires (via rerun).
        # Column headers
        h_date, h_vendor, h_raw, h_amt, h_cat, h_del = st.columns([1.3, 2.0, 2.0, 1.3, 3.4, 0.6])
        with h_date:  st.markdown("<p style='font-size:.75rem;color:#555;margin:0'>Date</p>", unsafe_allow_html=True)
        with h_vendor: st.markdown("<p style='font-size:.75rem;color:#555;margin:0'>Vendor</p>", unsafe_allow_html=True)
        with h_raw:   st.markdown("<p style='font-size:.75rem;color:#555;margin:0'>Raw description</p>", unsafe_allow_html=True)
        with h_amt:   st.markdown("<p style='font-size:.75rem;color:#555;margin:0'>Amount</p>", unsafe_allow_html=True)
        with h_cat:   st.markdown("<p style='font-size:.75rem;color:#555;margin:0'>Category</p>", unsafe_allow_html=True)
        with h_del:   st.markdown("<p style='font-size:.75rem;color:#555;margin:0'></p>", unsafe_allow_html=True)

        for i, row in enumerate(rows):
            c_date, c_name, c_raw, c_amt, c_cat, c_del = st.columns([1.3, 2.0, 2.0, 1.3, 3.4, 0.6])

            with c_date:
                st.text_input("Date", value=str(row.get("date","")),
                              label_visibility="collapsed",
                              key=f"td_{i}_date", placeholder="DD MMM YYYY")

            with c_name:
                # Cleaned vendor name — editable
                raw_val = row.get("vendor_clean") or row.get("name", "")
                if str(raw_val).lower() in ("nan", "none", ""):
                    raw_val = row.get("name", "")
                st.text_input("Vendor", value=str(raw_val),
                              label_visibility="collapsed",
                              key=f"td_{i}_name", placeholder="Vendor")

            with c_raw:
                # Raw bank description — read only display
                raw_desc = str(row.get("name", ""))
                if raw_desc.lower() in ("nan", "none"):
                    raw_desc = ""
                st.markdown(
                    f"<p style='font-size:.8rem;color:#555;margin:6px 0;overflow:hidden;"
                    f"white-space:nowrap;text-overflow:ellipsis' title='{raw_desc}'>{raw_desc}</p>",
                    unsafe_allow_html=True
                )

            with c_amt:
                st.text_input("Amount", value=str(row.get("amount","")),
                              label_visibility="collapsed",
                              key=f"td_{i}_amt", placeholder="-0.00 (debit) or +0.00 (income)")

            with c_cat:
                prev_cat = str(row.get("category","Unknown"))
                if prev_cat not in cat_options:
                    prev_cat = "Unknown"

                # Auto-match vendor rules when merchant name is typed/changed.
                # Read the current name from widget state (may differ from row dict
                # if the user just typed something without clicking Update Charts).
                current_name = st.session_state.get(f"td_{i}_name", row.get("name","")).strip()
                if current_name and current_name.lower() != "unknown":
                    matched = apply_vendor_rules(v_rules, current_name)
                    if matched and matched in cat_names and matched != prev_cat:
                        # Only auto-apply if the row still has "Unknown" or default —
                        # don't override a category the user has already set manually.
                        if prev_cat == "Unknown":
                            prev_cat = matched
                            rows[i]["category"] = matched

                new_cat = st.selectbox("Category", cat_options,
                                       index=cat_options.index(prev_cat),
                                       label_visibility="collapsed",
                                       key=f"td_{i}_cat")
                if new_cat != prev_cat:
                    if new_cat == ADD_NEW_SENTINEL:
                        new_cats_needed.append(i)
                    else:
                        rows[i]["category"] = new_cat
                        vendor = str(rows[i].get("name","")).strip()
                        if vendor and vendor.lower() not in ("","unknown") and uid:
                            vendor_rule_queue.append((vendor, new_cat))

            with c_del:
                def _make_delete_cb(idx):
                    def _cb():
                        st.session_state._tx_pending_delete = idx
                    return _cb
                st.button("✕", key=f"td_{i}_del",
                          on_click=_make_delete_cb(i),
                          help="Delete this row",
                          use_container_width=True)

        # Auto-save vendor rules from category changes
        for vendor, category in vendor_rule_queue:
            save_vendor_rule(uid, vendor, category, "contains")

        # ── Bottom action row: Add + Update Charts ───────────────────────────
        def _add_row_cb():
            st.session_state._tx_pending_add = True

        def _update_charts_cb():
            # Sync widget state → tx_rows and flag charts to refresh
            _rows = st.session_state.tx_rows
            for _i in range(len(_rows)):
                _rows[_i]["date"]         = st.session_state.get(f"td_{_i}_date", _rows[_i].get("date",""))
                # td_{i}_name widget shows the cleaned name — save back as vendor_clean
                _rows[_i]["vendor_clean"] = st.session_state.get(f"td_{_i}_name", _rows[_i].get("vendor_clean",""))
                _rows[_i]["name"]         = _rows[_i].get("name", _rows[_i]["vendor_clean"])
                _rows[_i]["amount"]       = st.session_state.get(f"td_{_i}_amt",  _rows[_i].get("amount",""))
                _rows[_i]["category"]     = st.session_state.get(f"td_{_i}_cat",  _rows[_i].get("category","Unknown"))
            st.session_state.tx_rows = _rows
            st.session_state._charts_dirty = False

        act1, act2 = st.columns([1, 1])
        with act1:
            st.button("＋  Add transaction", use_container_width=True,
                      on_click=_add_row_cb, key="add_tx_btn")
        with act2:
            st.button("📊  Update charts", use_container_width=True,
                      on_click=_update_charts_cb, key="update_charts_btn",
                      type="primary")

        # ── Always sync rows back (captures add/delete/category changes) ──────
        # Text field edits are only synced when Update Charts is clicked.
        for i in range(len(rows)):
            rows[i]["category"] = st.session_state.get(f"td_{i}_cat", rows[i].get("category","Unknown"))
        st.session_state.tx_rows = rows

        # ── Build df_edited from current tx_rows ─────────────────────────────
        df_edited = pd.DataFrame(st.session_state.tx_rows) if st.session_state.tx_rows else pd.DataFrame(
            columns=["date","name","amount","category"])
        df_edited["amount"] = df_edited["amount"].map(parse_amount)

        # ── Fill metrics placeholder ──────────────────────────────────────────
        total_spend  = df_edited[df_edited["amount"] < 0]["amount"].sum()
        total_income = df_edited[df_edited["amount"] > 0]["amount"].sum()
        n_tx         = len(df_edited)
        top_cat      = (df_edited[df_edited["amount"]<0]
                        .groupby("category")["amount"].sum().idxmin()
                        if len(df_edited[df_edited["amount"]<0]) else "—")

        _metrics_placeholder.markdown(f"""<div class="metric-strip">
            <div class="metric"><div class="val">{n_tx}</div><div class="lbl">Transactions</div></div>
            <div class="metric"><div class="val" style="color:#f87171">${abs(total_spend):,.2f}</div><div class="lbl">Total Spent</div></div>
            <div class="metric"><div class="val" style="color:#34d399">${total_income:,.2f}</div><div class="lbl">Total Income</div></div>
            <div class="metric"><div class="val" style="font-size:1rem;padding-top:4px">{top_cat}</div><div class="lbl">Biggest Category</div></div>
        </div>""", unsafe_allow_html=True)

        # ── Fill charts placeholder ───────────────────────────────────────────
        # Charts only show debits (negative amounts). Income/positive rows
        # are counted in the metrics but excluded from the pie + vendor tables.
        spend_df   = df_edited[df_edited["amount"] < 0].copy()
        spend_df["name"] = spend_df["name"].astype(str)
        spend_df["amount_abs"] = spend_df["amount"].abs()
        cat_totals = spend_df.groupby("category")["amount_abs"].sum().sort_values(ascending=False)

        n_income = len(df_edited[df_edited["amount"] >= 0])
        # ── AI Insight (above charts) ─────────────────────────────────────────
        _insight_profile  = get_profile(uid) if uid else {}
        _insight_tier     = _insight_profile.get("subscription_tier", "free_trial")
        _is_paid_insight  = _insight_tier in ("starter", "unlimited")
        _is_demo          = st.session_state.get("_is_demo", False)
        _cat_totals_dict  = cat_totals.to_dict() if not cat_totals.empty else {}
        _top_v = []
        if "vendor" in spend_df.columns:
            _tv = (spend_df.groupby("vendor")["amount_abs"]
                   .sum().sort_values(ascending=False).head(3))
            _top_v = [{"vendor": k, "amount": round(v, 2)} for k, v in _tv.items()]

        if _is_paid_insight and not _is_demo:
            _insight_key = f"ai_insight_{id(df_edited)}"
            if _insight_key not in st.session_state:
                try:
                    import google.generativeai as _genai
                    _genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                    _imodel = _genai.GenerativeModel("gemini-3.1-flash-lite-preview")
                    _iprompt = f"""You are a personal finance assistant. Given this spending summary, provide 1-2 sentences of genuinely useful insight. Focus on something specific and interesting — a pattern, a standout category, a vendor worth noticing, or a spend/income relationship. Be conversational and non-judgmental. Do not restate obvious totals. Do not use the word "great".

Total spend: ${abs(total_spend):,.2f}
Total income: ${total_income:,.2f}
Transaction count: {n_tx}
Category breakdown: {_cat_totals_dict}
Top vendors: {_top_v}"""
                    _iresp = _imodel.generate_content(_iprompt)
                    st.session_state[_insight_key] = _iresp.text.strip()
                except Exception as _insight_err:
                    st.session_state[_insight_key] = None
                    st.session_state["_insight_error"] = str(_insight_err)

            _insight_text = st.session_state.get(_insight_key)
            if not _insight_text and st.session_state.get("_insight_error"):
                _insight_placeholder.caption(f"⚠️ Insight unavailable: {st.session_state['_insight_error']}")
            if _insight_text:
                # Cache for saving with report
                st.session_state["_insight_to_save"] = _insight_text
                _insight_placeholder.markdown(f"""
                <div style="background:#1a1a24;border:1px solid #2a2a38;border-radius:10px;
                            padding:14px 18px;margin:0 0 16px">
                  <p style="font-size:.7rem;font-weight:600;color:#f0c040;text-transform:uppercase;
                            letter-spacing:.08em;margin:0 0 6px">✦ AI Insight</p>
                  <p style="font-size:.9rem;color:#c9c7c0;line-height:1.6;margin:0">{_insight_text}</p>
                </div>
                """, unsafe_allow_html=True)
        else:
            # Free tier or demo — teaser with fade
            _top_cat_name = cat_totals.index[0] if not cat_totals.empty else "spending"
            _top_cat_amt  = cat_totals.iloc[0]  if not cat_totals.empty else 0
            _teasers = [
                f"Your biggest spending category was {_top_cat_name} at ${_top_cat_amt:,.0f}, which accounts for",
                f"You made {n_tx} transactions this month, with {_top_v[0]['vendor'] if _top_v else 'your top vendor'} appearing the most",
                f"Your spending was spread across {len(_cat_totals_dict)} categories, with {_top_cat_name} and",
                f"This month's total spend of ${abs(total_spend):,.0f} was {'above' if abs(total_spend) > total_income else 'below'} your income, suggesting",
            ]
            _teaser = _teasers[hash(str(_cat_totals_dict)) % len(_teasers)]
            _insight_placeholder.markdown(f"""
            <div style="background:#1a1a24;border:1px solid #2a2a38;border-radius:10px;
                        padding:14px 18px;margin:0 0 16px;position:relative;overflow:hidden">
              <p style="font-size:.7rem;font-weight:600;color:#555;text-transform:uppercase;
                        letter-spacing:.08em;margin:0 0 6px">✦ AI Insight</p>
              <p style="font-size:.9rem;color:#c9c7c0;line-height:1.6;margin:0 0 8px">
                {_teaser}
                <span style="background:linear-gradient(to right,#c9c7c0,transparent);
                             -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                             background-clip:text">
                  &nbsp;your top categories driving 80% of...
                </span>
              </p>
              <div style="position:absolute;right:0;top:0;bottom:0;width:60%;
                          background:linear-gradient(to right,transparent,#1a1a24 70%)"></div>
              <p style="font-size:.8rem;color:#f0c040;margin:0;position:relative;z-index:1">
                🔒 Upgrade to Starter to unlock AI insights
              </p>
            </div>
            """, unsafe_allow_html=True)

        if not cat_totals.empty:
            with _charts_placeholder.container():
                if n_income > 0:
                    st.caption(f"ℹ️ Charts show spending only. "
                               f"{n_income} income/zero row{'s' if n_income!=1 else ''} "
                               f"excluded — visible in metrics above.")
                pie_col, vendor_col = st.columns([1, 1])

                with pie_col:
                    st.markdown("#### Spending by Category")
                    pie_mode = st.radio(
                        "Display", ["Value ($)", "Percentage (%)"],
                        horizontal=True, label_visibility="collapsed",
                        key="pie_mode",
                    )
                    show_pct = pie_mode == "Percentage (%)"
                    total_spend_abs = cat_totals.sum()
                    # Group small slices (< 3%) into "Other" to avoid label clipping
                    threshold = total_spend_abs * 0.03
                    main_cats  = cat_totals[cat_totals >= threshold]
                    other_sum  = cat_totals[cat_totals < threshold].sum()
                    if other_sum > 0:
                        import pandas as pd
                        main_cats = pd.concat([main_cats,
                                               pd.Series({"Other": other_sum})])

                    fig_pie = go.Figure(go.Pie(
                        labels=main_cats.index.tolist(),
                        values=main_cats.values.tolist(),
                        marker=dict(
                            colors=[CATEGORY_COLORS.get(c, "#6b7280") for c in main_cats.index],
                            line=dict(color="#0f0f13", width=2),
                        ),
                        hole=0.52,
                        hovertemplate="<b>%{label}</b><br>$%{value:,.2f}<br>%{percent}<extra></extra>",
                        texttemplate="%{label}<br>%{percent}" if show_pct else "%{label}<br>$%{value:,.0f}",
                        textposition="outside",
                        pull=[0.03] * len(main_cats),
                    ))
                    centre_text = f"${total_spend_abs:,.0f}" if not show_pct else "100%"
                    fig_pie.update_layout(
                        height=460,
                        margin=dict(l=60, r=60, t=100, b=80),
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        font=dict(color="#c9c7c0", size=11, family="DM Sans"),
                        showlegend=False,
                        annotations=[dict(
                            text=f"<b>{centre_text}</b><br><span style='font-size:10px'>total spend</span>",
                            x=0.5, y=0.5, font=dict(size=14, color="#e8e6e1"), showarrow=False,
                        )],
                    )
                    st.plotly_chart(fig_pie, use_container_width=True,
                                    config={"displayModeBar": False})

                with vendor_col:
                    st.markdown("#### Top Vendors")
                    vtab1, vtab2 = st.tabs(["By value", "By charges"])

                    with vtab1:
                        # Use vendor_clean for grouping if available
                        # Build clean vendor column — no NaN, no "nan" strings
                        if "vendor_clean" in spend_df.columns:
                            spend_df["vendor"] = (spend_df["vendor_clean"]
                                                  .replace("nan", None)
                                                  .fillna(spend_df["name"])
                                                  .replace("", None)
                                                  .fillna(spend_df["name"]))
                        else:
                            spend_df["vendor"] = spend_df["name"]
                        spend_df["vendor"] = spend_df["vendor"].astype(str).str.strip()

                        by_value = (spend_df.groupby("vendor")["amount_abs"]
                                    .sum().sort_values(ascending=False)
                                    .head(5).reset_index())
                        max_val = by_value["amount_abs"].max()
                        rows_html = ""
                        for rank, (_, vrow) in enumerate(by_value.iterrows(), 1):
                            vname   = vrow["vendor"]
                            bar_pct = int(vrow["amount_abs"] / max_val * 100)
                            matched = spend_df[spend_df["vendor"] == vname]["category"].mode()
                            color   = CATEGORY_COLORS.get(
                                matched.iloc[0] if not matched.empty else "Unknown",
                                "#6b7280"
                            )
                            rows_html += f"""
                            <div style="padding:10px 0;border-bottom:1px solid #1e1e28">
                              <div style="display:flex;justify-content:space-between;
                                          align-items:baseline;margin-bottom:5px">
                                <span style="font-size:.85rem;color:#e8e6e1;
                                             white-space:nowrap;overflow:hidden;
                                             text-overflow:ellipsis;max-width:65%">{vname}</span>
                                <span style="font-size:.85rem;font-weight:500;
                                             color:#e8e6e1;font-family:'DM Mono',monospace">
                                  ${vrow["amount_abs"]:,.2f}</span>
                              </div>
                              <div style="background:#1e1e28;border-radius:3px;height:4px">
                                <div style="width:{bar_pct}%;height:4px;border-radius:3px;
                                            background:{color}"></div>
                              </div>
                            </div>"""
                        st.markdown(rows_html, unsafe_allow_html=True)

                    with vtab2:
                        by_count = (spend_df.groupby("vendor")
                                    .agg(charges=("amount_abs","count"),
                                         total=("amount_abs","sum"))
                                    .sort_values("charges", ascending=False)
                                    .head(5).reset_index())
                        max_count = by_count["charges"].max()
                        rows_html = ""
                        for rank, (_, vrow) in enumerate(by_count.iterrows(), 1):
                            vname   = vrow["vendor"]
                            bar_pct = int(vrow["charges"] / max_count * 100)
                            matched = spend_df[spend_df["vendor"] == vname]["category"].mode()
                            color   = CATEGORY_COLORS.get(
                                matched.iloc[0] if not matched.empty else "Unknown",
                                "#6b7280"
                            )
                            rows_html += f"""
                            <div style="padding:10px 0;border-bottom:1px solid #1e1e28">
                              <div style="display:flex;justify-content:space-between;
                                          align-items:baseline;margin-bottom:5px">
                                <span style="font-size:.85rem;color:#e8e6e1;
                                             white-space:nowrap;overflow:hidden;
                                             text-overflow:ellipsis;max-width:65%">{vname}</span>
                                <span style="font-size:.75rem;color:#888">
                                  {int(vrow["charges"])} charge{'s' if int(vrow["charges"])!=1 else ''}
                                  &nbsp;·&nbsp;
                                  <span style="color:#e8e6e1;font-family:'DM Mono',monospace">
                                    ${vrow["total"]:,.2f}</span></span>
                              </div>
                              <div style="background:#1e1e28;border-radius:3px;height:4px">
                                <div style="width:{bar_pct}%;height:4px;border-radius:3px;
                                            background:{color}"></div>
                              </div>
                            </div>"""
                        st.markdown(rows_html, unsafe_allow_html=True)

        # ── Sentinel: inline add-new-category UI ─────────────────────────────
        if new_cats_needed:
            st.markdown('<div class="info-box blue">You selected <b>＋ Add new category…</b> — '
                        'enter the name and colour below, then save.</div>', unsafe_allow_html=True)
            nc1, nc2, nc3 = st.columns([3, 2, 1])
            with nc1:
                inline_cat_name  = st.text_input("New category name",
                                                  placeholder="e.g. Pet Care",
                                                  key="inline_cat_name")
            with nc2:
                inline_cat_color = st.color_picker("Colour", value="#a78bfa",
                                                    key="inline_cat_color")
            with nc3:
                st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                if st.button("Save category", type="primary", use_container_width=True):
                    name = inline_cat_name.strip()
                    if not name:
                        st.warning("Enter a category name.")
                    elif not uid:
                        st.warning("Sign in to save categories.")
                    else:
                        ok, err = save_category(uid, name, inline_cat_color)
                        if ok:
                            for i in new_cats_needed:
                                rows[i]["category"] = name
                                vendor = str(rows[i].get("name","")).strip()
                                if vendor and vendor.lower() not in ("","unknown"):
                                    save_vendor_rule(uid, vendor, name, "contains")
                            st.session_state.tx_rows = rows
                            st.success(f"✅ '{name}' added!")
                            st.rerun()
                        else:
                            st.error(f"Could not save: {err}")

        # ── Manage categories expander ────────────────────────────────────────
        with st.expander("⚙️ Manage categories"):
            custom = {k: v for k, v in all_cats.items() if k not in DEFAULT_CATEGORY_COLORS}
            if custom:
                st.markdown("**Your custom categories**")
                for cname, ccolor in custom.items():
                    cc1, cc2 = st.columns([4, 1])
                    with cc1:
                        st.markdown(
                            f'<span style="display:inline-block;width:12px;height:12px;'
                            f'border-radius:50%;background:{ccolor};margin-right:8px;'
                            f'vertical-align:middle"></span>{cname}',
                            unsafe_allow_html=True,
                        )
                    with cc2:
                        if st.button("✕", key=f"del_cat_{cname}"):
                            delete_category(uid, cname)
                            st.rerun()
            else:
                st.caption("No custom categories yet — select '＋ Add new category…' in the table above to create one.")

        # ── Vendor rules expander ─────────────────────────────────────────────
        with st.expander("🏪 Vendor auto-categorization rules"):
            # Show auto-created rules notice if any were just created
            if vendor_rule_queue:
                st.markdown(
                    f'<div class="info-box green">✅ {len(vendor_rule_queue)} vendor rule'
                    f'{"s" if len(vendor_rule_queue)!=1 else ""} saved automatically.</div>',
                    unsafe_allow_html=True,
                )

            st.caption("Rules are created automatically when you change a category in the table. "
                       "You can also add or delete them manually here.")

            # Manual add
            vr1, vr2, vr3, vr4 = st.columns([3, 2, 2, 1])
            with vr1:
                new_vr_vendor = st.text_input("Vendor", placeholder="e.g. AMPOL",
                                              label_visibility="collapsed", key="new_vr_vendor")
            with vr2:
                new_vr_cat = st.selectbox("Category", cat_names,
                                          label_visibility="collapsed", key="new_vr_cat")
            with vr3:
                new_vr_type = st.selectbox("Match type", ["contains", "exact"],
                                           label_visibility="collapsed", key="new_vr_type")
            with vr4:
                if st.button("Add", use_container_width=True, key="add_vr"):
                    vendor = new_vr_vendor.strip()
                    if not vendor:
                        st.warning("Enter a vendor name.")
                    elif not uid:
                        st.warning("Sign in to save rules.")
                    else:
                        ok, err = save_vendor_rule(uid, vendor, new_vr_cat, new_vr_type)
                        if ok:
                            st.success(f"Rule saved: {vendor} → {new_vr_cat}")
                            st.rerun()
                        else:
                            st.error(f"Could not save: {err}")

            # List existing rules
            v_rules_fresh = load_vendor_rules(uid) if uid else []
            if v_rules_fresh:
                st.markdown("**Active rules**")
                for rule in v_rules_fresh:
                    rc1, rc2 = st.columns([5, 1])
                    with rc1:
                        st.markdown(
                            f'`{rule["vendor_name"]}` ({rule["match_type"]}) → '
                            f'**{rule["category"]}**'
                        )
                    with rc2:
                        if st.button("✕", key=f"del_vr_{rule['vendor_name']}"):
                            delete_vendor_rule(uid, rule["vendor_name"])
                            st.rerun()
            else:
                st.caption("No rules yet.")

        # ── Save report ───────────────────────────────────────────────────────
        with st.expander("💾 Save this report to your account"):
            if not uid:
                st.info("Sign in to save reports.")
            else:
                sr1, sr2, sr3 = st.columns([3, 2, 2])
                with sr1:
                    report_label = st.text_input("Label", placeholder="e.g. March 2026",
                                                 label_visibility="collapsed", key="report_label")
                with sr2:
                    period_start = st.date_input("Period start", value=None,
                                                 label_visibility="collapsed", key="period_start")
                with sr3:
                    period_end = st.date_input("Period end", value=None,
                                               label_visibility="collapsed", key="period_end")

                # Duplicate warning
                ps_str = str(period_start) if period_start else None
                pe_str = str(period_end)   if period_end   else None
                if ps_str and pe_str and check_duplicate_report(uid, ps_str, pe_str):
                    st.warning(
                        "⚠️ A saved report already overlaps this date range. "
                        "You can still save but check you're not duplicating data."
                    )

                if st.button("💾 Save report", type="primary", use_container_width=True):
                    if not report_label.strip():
                        st.warning("Enter a label for this report.")
                    else:
                        # Sync latest widget state into tx_rows before saving
                        _rows = st.session_state.get("tx_rows", [])
                        for _i in range(len(_rows)):
                            _rows[_i]["date"]         = st.session_state.get(f"td_{_i}_date",     _rows[_i].get("date",""))
                            _rows[_i]["vendor_clean"] = st.session_state.get(f"td_{_i}_name",     _rows[_i].get("vendor_clean",""))
                            _rows[_i]["name"]         = _rows[_i].get("name", _rows[_i]["vendor_clean"])
                            _rows[_i]["amount"]       = st.session_state.get(f"td_{_i}_amt",      _rows[_i].get("amount", 0))
                            _rows[_i]["category"]     = st.session_state.get(f"td_{_i}_cat",      _rows[_i].get("category","Unknown"))

                        save_data = []
                        for row in _rows:
                            try:
                                amt = float(str(row.get("amount", 0)).replace("$","").replace(",","").strip() or 0)
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
                                "category":     str(row.get("category", "Unknown")),
                            })

                        # Determine tier_required based on user's subscription
                        from db import get_profile as _gp
                        _profile = _gp(uid)
                        _tier    = _profile.get("subscription_tier", "free_trial")
                        _tier_req = "free_trial" if _tier == "free_trial" else "starter"

                        ok, err = save_report(
                            uid,
                            report_label.strip(),
                            ps_str, pe_str,
                            save_data,
                            tier_required=_tier_req,
                            ai_insight=st.session_state.get("_insight_to_save"),
                        )
                        if ok:
                            st.success("✅ Report saved!")
                        else:
                            st.error(f"Could not save: {err}")

        # ── Downloads ─────────────────────────────────────────────────────────
        st.markdown("---")
        d1, d2, d3 = st.columns(3)
        with d1:
            csv = df_edited.copy().assign(amount=df_edited["amount"].map(lambda x: f"${x:+,.2f}")).to_csv(index=False)
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
                for k in ["step","pdf_bytes","redacted_pdf_bytes","annotations",
                          "pending","page_num","transactions","categorized",
                          "tx_rows","tx_rows_source",
                          "_tx_pending_delete","_tx_pending_add"]:
                    st.session_state.pop(k, None)
                # Clear any row widget keys
                for k in list(st.session_state.keys()):
                    if k.startswith("td_"):
                        del st.session_state[k]
                render_page_b64.clear()
                st.rerun()
