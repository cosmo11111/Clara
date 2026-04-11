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
    load_categories, save_category, delete_category,
    load_vendor_rules, apply_vendor_rules, save_vendor_rule, delete_vendor_rule,
    save_report, load_reports, load_report_items, delete_report,
    DEFAULT_CATEGORY_COLORS,
)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Expense Categorizer", page_icon="💳", layout="wide")

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500;600&display=swap');

  html, body, .stApp { font-family: 'DM Sans', sans-serif; background-color: #0f0f13; color: #e8e6e1; }

  /* Sidebar */
  section[data-testid="stSidebar"] { background: #17171d !important; border-right: 1px solid #2a2a35; }
  section[data-testid="stSidebar"] * { color: #c9c7c0 !important; }
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
    {"date": "01 Apr 2026", "name": "DANG GOOD CAFE",               "amount": -4.55,    "category": "Food & Dining"},
    {"date": "01 Apr 2026", "name": "STOMPING GROUND BREWIN",        "amount": -22.37,   "category": "Food & Dining"},
    {"date": "01 Apr 2026", "name": "Unknown",                       "amount": -13.00,   "category": "Unknown"},
    {"date": "02 Apr 2026", "name": "AMPOL KEW 33261F",              "amount": -58.77,   "category": "Transport"},
    {"date": "03 Apr 2026", "name": "WOOLWORTHS/18 WALPOLE ST",      "amount": -7.90,    "category": "Shopping"},
    {"date": "04 Apr 2026", "name": "AMPOL KEW 33261F",              "amount": -2.00,    "category": "Transport"},
    {"date": "04 Apr 2026", "name": "Kindle Unltd",                  "amount": -13.99,   "category": "Subscriptions"},
    {"date": "04 Apr 2026", "name": "CANVA* I04841-0173708",         "amount": -20.00,   "category": "Subscriptions"},
    {"date": "05 Apr 2026", "name": "Spotify P411178B22",            "amount": -15.99,   "category": "Subscriptions"},
    {"date": "05 Apr 2026", "name": "WOOLWORTHS/18 WALPOLE ST",      "amount": -83.10,   "category": "Shopping"},
    {"date": "07 Apr 2026", "name": "AMPOL KEW 33261F",              "amount": -64.52,   "category": "Transport"},
    {"date": "07 Apr 2026", "name": "ZLR*Seven Creeks Hotel",        "amount": -25.08,   "category": "Food & Dining"},
    {"date": "07 Apr 2026", "name": "Transfer from Savings Maximiser","amount": 3000.00, "category": "Income"},
    {"date": "07 Apr 2026", "name": "Unknown",                       "amount": -2450.00, "category": "Unknown"},
    {"date": "07 Apr 2026", "name": "Unknown",                       "amount": -400.00,  "category": "Unknown"},
    {"date": "08 Apr 2026", "name": "AMPOL TALLAROOK 30026F",        "amount": -11.00,   "category": "Transport"},
    {"date": "08 Apr 2026", "name": "DANG GOOD CAFE",                "amount": -17.60,   "category": "Food & Dining"},
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
    model = genai.GenerativeModel("gemini-3-flash-preview")
    cat_list = ", ".join(all_categories.keys())
    prompt = f"""Extract ALL transactions from this bank statement text.
Return ONLY a JSON array. Each object must have exactly these keys:
"date" (string), "name" (string), "amount" (number, negative=debit positive=credit),
"category" (one of: {cat_list}).
If category is unclear use "Unknown".

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
    st.markdown("## 💳 Expense AI")
    st.markdown("---")

    # Step progress
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

    st.markdown("---")

    if st.session_state.step == 2:
        st.markdown("**Redaction tools**")
        color = st.selectbox("Highlight colour", list(COLORS_RGB.keys()))
        zoom  = st.slider("Zoom", 1.0, 3.0, st.session_state.zoom, 0.25)
        if zoom != st.session_state.zoom:
            st.session_state.zoom = zoom
            render_page_b64.clear()
        snap = st.toggle("Snap to words", value=True)
        st.markdown("---")
        rd = sum(1 for v in st.session_state.annotations.values() for a in v if a["type"]=="redact")
        if rd:
            st.markdown(f'<div class="info-box red">⬛ {rd} redaction{"s" if rd!=1 else ""} pending</div>', unsafe_allow_html=True)
        if st.button("🗑️ Clear redactions", use_container_width=True):
            st.session_state.annotations = {}
            st.session_state.pending = None
            st.rerun()
    else:
        color = "Yellow"
        snap = True
        zoom = st.session_state.zoom

# ── Header ────────────────────────────────────────────────────────────────────
# ── Auth guard ───────────────────────────────────────────────────────────────
require_auth()

# ── User menu in sidebar ──────────────────────────────────────────────────────
user = get_user()
with st.sidebar:
    st.markdown("---")
    if user:
        email = user.email if hasattr(user, "email") else user.get("email", "")
        st.markdown(f"<p style='color:#888;font-size:.8rem;margin-bottom:4px'>Signed in as</p>", unsafe_allow_html=True)
        st.markdown(f"<p style='color:#e8e6e1;font-size:.85rem;font-weight:500;word-break:break-all'>{email}</p>", unsafe_allow_html=True)
        if st.button("📂 Saved Reports", use_container_width=True):
            st.switch_page("pages/4_reports.py")
        if st.button("Sign out", use_container_width=True):
            try:
                get_supabase().auth.sign_out()
            except Exception:
                pass
            clear_session()
            st.switch_page("pages/1_login.py")

st.markdown("# 💳 Expense Categorizer")
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

        # ── Sticky action bar ─────────────────────────────────────────────
        st.markdown("#### Redaction tools")
        bar1, bar2, bar3, bar4, bar5 = st.columns([2, 2, 2, 2, 1])
        with bar1:
            redact_btn = st.button(
                "⬛ Redact Selection  [R]",
                use_container_width=True, type="primary",
                disabled=st.session_state.pending is None,
            )
        with bar2:
            undo_btn = st.button(
                "↩️ Undo Last  [U]",
                use_container_width=True,
                disabled=not st.session_state.annotations.get(pk),
            )
        with bar3:
            label = f"Analyse ({rd_total} redaction{'s' if rd_total!=1 else ''}) →" if rd_total else "Analyse (no redactions) →"
            analyse_btn = st.button(label, use_container_width=True)
        with bar4:
            # Page nav inline
            pn_c1, pn_c2, pn_c3 = st.columns([1, 2, 1])
            with pn_c1:
                if st.button("◀", use_container_width=True, disabled=pn == 0):
                    st.session_state.page_num -= 1
                    st.session_state.pending = None
                    st.rerun()
            with pn_c2:
                st.markdown(f"<p style='text-align:center;margin:6px 0;font-size:.85rem;color:#888'>p.{pn+1}/{n_pages}</p>", unsafe_allow_html=True)
            with pn_c3:
                if st.button("▶", use_container_width=True, disabled=pn == n_pages - 1):
                    st.session_state.page_num += 1
                    st.session_state.pending = None
                    st.rerun()
        with bar5:
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
        st.markdown("### Upload your bank statement")

    up_col, info_col = st.columns([2, 1]) if not pdf_loaded else (st.container(), None)

    with (up_col if not pdf_loaded else st.container()):
        if not pdf_loaded:
            st.markdown('<div class="info-box">Upload a PDF bank statement. You can redact sensitive information (account numbers, BSB, personal details) before the AI reads it.</div>', unsafe_allow_html=True)

        uploaded = st.file_uploader(
            "Upload PDF", type=["pdf"],
            label_visibility="collapsed" if pdf_loaded else "visible",
        )
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

        if not pdf_loaded:
            st.markdown("---")
            st.markdown('<p style="color:#555;font-size:.8rem;margin-bottom:8px">⚡ DEVELOPER SHORTCUT</p>', unsafe_allow_html=True)
            if st.button("📋 Load Demo Expenses", use_container_width=True):
                st.session_state.transactions = DEMO_DATA
                st.session_state.categorized = True
                st.session_state.redacted_pdf_bytes = None
                st.session_state.annotations = {}
                st.session_state.step = 3
                st.rerun()

    if not pdf_loaded and info_col is not None:
        with info_col:
            st.markdown("""<div class="card">
                <h3>🔒 Privacy first</h3>
                <p>You control what the AI sees. Redact account numbers, BSBs, names, and addresses before analysis.</p>
            </div>
            <div class="card">
                <h3>🤖 Gemini AI</h3>
                <p>Transactions are extracted and categorized automatically across all pages.</p>
            </div>
            <div class="card">
                <h3>📊 Instant insights</h3>
                <p>See spending by category with totals and a breakdown table.</p>
            </div>""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════
# STEP 3 — Categorize
# ═══════════════════════════════════════════════════════════
elif st.session_state.step == 3:
    st.markdown("### Step 3 — AI Expense Categorization")

    rd_count = sum(len(v) for v in st.session_state.annotations.values())
    if rd_count:
        st.markdown(f'<div class="info-box green">🔒 {rd_count} redaction{"s" if rd_count!=1 else ""} applied — the AI will not see that content.</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="info-box blue">ℹ️ No redactions applied. The full document will be analysed.</div>', unsafe_allow_html=True)

    col_btn1, col_btn2, _ = st.columns([1,1,3])
    with col_btn1:
        run = st.button("🤖 Categorize Transactions", type="primary", use_container_width=True)
    with col_btn2:
        if st.button("← Back to Redaction", use_container_width=True):
            st.session_state.step = 2
            st.rerun()

    if run:
        with st.spinner("Extracting text and sending to Gemini…"):
            try:
                text = extract_text_all_pages(st.session_state.redacted_pdf_bytes)
                if not text:
                    st.error("No text could be extracted from the PDF. It may be a scanned image.")
                    st.stop()
                user     = get_user()
                uid      = user.id if hasattr(user,"id") else user.get("id") if user else None
                all_cats = load_categories(uid) if uid else DEFAULT_CATEGORY_COLORS
                v_rules  = load_vendor_rules(uid) if uid else []
                data = categorize_with_gemini(text, all_cats, v_rules)
                st.session_state.transactions = data
                st.session_state.categorized = True
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
            st.session_state.tx_rows = df[["date","name","amount","category"]].copy().to_dict("records")
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
                "date":     _date.today().strftime("%d %b %Y"),
                "name":     "",
                "amount":   "",
                "category": "Unknown",
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
        for i, row in enumerate(rows):
            c_date, c_name, c_amt, c_cat, c_del = st.columns([1.3, 3.0, 1.3, 3.4, 0.6])

            with c_date:
                st.text_input("Date", value=str(row.get("date","")),
                              label_visibility="collapsed",
                              key=f"td_{i}_date", placeholder="DD MMM YYYY")

            with c_name:
                st.text_input("Merchant", value=str(row.get("name","")),
                              label_visibility="collapsed",
                              key=f"td_{i}_name", placeholder="Merchant")

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
                _rows[_i]["date"]     = st.session_state.get(f"td_{_i}_date",     _rows[_i].get("date",""))
                _rows[_i]["name"]     = st.session_state.get(f"td_{_i}_name",     _rows[_i].get("name",""))
                _rows[_i]["amount"]   = st.session_state.get(f"td_{_i}_amt",      _rows[_i].get("amount",""))
                _rows[_i]["category"] = st.session_state.get(f"td_{_i}_cat",      _rows[_i].get("category","Unknown"))
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
                    fig_pie = go.Figure(go.Pie(
                        labels=cat_totals.index.tolist(),
                        values=cat_totals.values.tolist(),
                        marker=dict(
                            colors=[CATEGORY_COLORS.get(c, "#6b7280") for c in cat_totals.index],
                            line=dict(color="#0f0f13", width=2),
                        ),
                        hole=0.52,
                        hovertemplate="<b>%{label}</b><br>$%{value:,.2f}<br>%{percent}<extra></extra>",
                        texttemplate="%{label}<br>%{percent}" if show_pct else "%{label}<br>$%{value:,.0f}",
                        textposition="outside",
                        pull=[0.03] * len(cat_totals),
                    ))
                    centre_text = f"${total_spend_abs:,.0f}" if not show_pct else "100%"
                    fig_pie.update_layout(
                        height=380, margin=dict(l=10,r=10,t=30,b=10),
                        paper_bgcolor="#1e1e28",
                        font=dict(color="#c9c7c0", size=11, family="DM Sans"),
                        showlegend=False,
                        annotations=[dict(
                            text=f"<b>{centre_text}</b><br><span style='font-size:10px'>total spend</span>",
                            x=0.5, y=0.5, font=dict(size=14, color="#e8e6e1"), showarrow=False,
                        )],
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)

                with vendor_col:
                    st.markdown("#### Top Vendors")
                    vtab1, vtab2 = st.tabs(["💰 By Value", "🔢 By Charges"])
                    with vtab1:
                        by_value = (spend_df.groupby("name")["amount_abs"]
                                    .sum().sort_values(ascending=False)
                                    .head(3).reset_index())
                        by_value.columns = ["Vendor", "Total Spent"]
                        by_value["Total Spent"] = by_value["Total Spent"].map(lambda x: f"${x:,.2f}")
                        by_value.index = by_value.index + 1
                        st.dataframe(by_value, use_container_width=True, height=340,
                                     column_config={"Vendor": st.column_config.TextColumn("Vendor"),
                                                    "Total Spent": st.column_config.TextColumn("Total Spent")})
                    with vtab2:
                        by_count = (spend_df.groupby("name")
                                    .agg(Charges=("amount_abs","count"), Total=("amount_abs","sum"))
                                    .sort_values("Charges", ascending=False)
                                    .head(3).reset_index())
                        by_count.columns = ["Vendor", "Charges", "Total Spent"]
                        by_count["Total Spent"] = by_count["Total Spent"].map(lambda x: f"${x:,.2f}")
                        by_count.index = by_count.index + 1
                        st.dataframe(by_count, use_container_width=True, height=340,
                                     column_config={"Vendor": st.column_config.TextColumn("Vendor"),
                                                    "Charges": st.column_config.NumberColumn("Charges"),
                                                    "Total Spent": st.column_config.TextColumn("Total Spent")})

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
                if st.button("💾 Save report", type="primary", use_container_width=True):
                    if not report_label.strip():
                        st.warning("Enter a label for this report.")
                    else:
                        # Convert df_edited to list of dicts for saving
                        save_data = df_edited[["date","name","amount","category"]].to_dict("records")
                        ok, err = save_report(
                            uid,
                            report_label.strip(),
                            str(period_start) if period_start else None,
                            str(period_end)   if period_end   else None,
                            save_data,
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
