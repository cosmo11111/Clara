import streamlit as st
import fitz  # PyMuPDF
import pdfplumber
import io
import base64
import json
from PIL import Image
import streamlit.components.v1 as components

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PDF Highlighter",
    page_icon="🖊️",
    layout="wide",
)

# ── Styling ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .stApp { background-color: #f5f5f0; }
    .main-title {
        font-size: 2rem; font-weight: 700; color: #1a1a2e;
        margin-bottom: 0; padding-bottom: 0;
    }
    .subtitle {
        font-size: 0.95rem; color: #555; margin-top: 0;
        margin-bottom: 1.5rem;
    }
    .info-box {
        background: #fffbea; border-left: 4px solid #f0c040;
        padding: 0.75rem 1rem; border-radius: 4px;
        font-size: 0.88rem; color: #555; margin-bottom: 1rem;
    }
    .stat-box {
        background: white; border-radius: 8px; padding: 0.75rem 1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08); text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# ── Session state defaults ────────────────────────────────────────────────────
for key, default in [
    ("page_num", 0),
    ("highlights", {}),
    ("pdf_bytes", None),
    ("zoom", 1.5),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Constants ─────────────────────────────────────────────────────────────────
HIGHLIGHT_COLORS_RGB = {
    "Yellow":  (1,    1,    0   ),
    "Green":   (0,    1,    0.4 ),
    "Cyan":    (0,    0.9,  1   ),
    "Pink":    (1,    0.4,  0.7 ),
    "Orange":  (1,    0.6,  0   ),
}
CANVAS_COLORS = {
    "Yellow":  "rgba(255,255,  0,0.35)",
    "Green":   "rgba(  0,255,100,0.35)",
    "Cyan":    "rgba(  0,230,255,0.35)",
    "Pink":    "rgba(255,100,180,0.35)",
    "Orange":  "rgba(255,153,  0,0.35)",
}

# ── Helpers ───────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def render_page_b64(pdf_bytes: bytes, page_num: int, zoom: float):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[page_num]
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img_bytes = pix.tobytes("png")
    doc.close()
    b64 = base64.b64encode(img_bytes).decode()
    return b64, pix.width, pix.height


def snap_to_words(pdf_bytes, page_num, rect, zoom):
    x0, y0, x1, y1 = rect
    snapped = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        page = pdf.pages[page_num]
        for word in (page.extract_words() or []):
            wx0, wy0, wx1, wy1 = word["x0"], word["top"], word["x1"], word["bottom"]
            if wx0 < x1 and wx1 > x0 and wy0 < y1 and wy1 > y0:
                snapped.append((wx0, wy0, wx1, wy1))
    if not snapped:
        return rect
    return (
        min(w[0] for w in snapped), min(w[1] for w in snapped),
        max(w[2] for w in snapped), max(w[3] for w in snapped),
    )


def build_annotated_pdf(original_bytes, highlights):
    doc = fitz.open(stream=original_bytes, filetype="pdf")
    for page_num_str, page_highlights in highlights.items():
        page = doc[int(page_num_str)]
        for h in page_highlights:
            rect = fitz.Rect(*h["rect"])
            color_rgb = HIGHLIGHT_COLORS_RGB.get(h["color"], (1, 1, 0))
            annot = page.add_highlight_annot(rect)
            annot.set_colors(stroke=color_rgb)
            annot.update()
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def make_canvas_html(b64_img, img_w, img_h, fill_color, existing):
    existing_json = json.dumps(existing)
    return f"""<!DOCTYPE html>
<html>
<head>
<style>
  body {{ margin:0; padding:0; overflow:hidden; background:transparent; }}
  #c {{ cursor:crosshair; display:block; }}
  #hint {{ font-family:sans-serif; font-size:12px; color:#888;
           padding:4px 0 0 2px; }}
</style>
</head>
<body>
<canvas id="c" width="{img_w}" height="{img_h}"></canvas>
<div id="hint">Drag to highlight · release to confirm</div>
<script>
const canvas = document.getElementById('c');
const ctx    = canvas.getContext('2d');
const fill   = "{fill_color}";
const saved  = {existing_json};

const img = new Image();
img.src = "data:image/png;base64,{b64_img}";

function redraw(active) {{
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(img, 0, 0);
  saved.forEach(r => {{
    ctx.fillStyle = r.color;
    ctx.fillRect(r.x, r.y, r.w, r.h);
  }});
  if (active) {{
    ctx.fillStyle = fill;
    ctx.fillRect(active.x, active.y, active.w, active.h);
  }}
}}

img.onload = () => redraw(null);

let sx, sy, dragging = false;

function getPos(e) {{
  const r = canvas.getBoundingClientRect();
  const src = e.touches ? e.touches[0] : e;
  return [src.clientX - r.left, src.clientY - r.top];
}}

function onStart(e) {{
  e.preventDefault();
  [sx, sy] = getPos(e);
  dragging = true;
}}

function onMove(e) {{
  e.preventDefault();
  if (!dragging) return;
  const [ex, ey] = getPos(e);
  redraw({{ x: sx, y: sy, w: ex - sx, h: ey - sy }});
}}

function onEnd(e) {{
  e.preventDefault();
  if (!dragging) return;
  dragging = false;
  const src = e.changedTouches ? e.changedTouches[0] : e;
  const r   = canvas.getBoundingClientRect();
  const ex  = src.clientX - r.left;
  const ey  = src.clientY - r.top;
  const w = ex - sx, h = ey - sy;
  if (Math.abs(w) < 5 || Math.abs(h) < 5) {{ redraw(null); return; }}
  const rect = {{
    x: w >= 0 ? sx : ex, y: h >= 0 ? sy : ey,
    w: Math.abs(w),       h: Math.abs(h)
  }};
  redraw(null);
  window.parent.postMessage({{ type:"pdf_highlight", rect }}, "*");
}}

canvas.addEventListener('mousedown',  onStart);
canvas.addEventListener('mousemove',  onMove);
canvas.addEventListener('mouseup',    onEnd);
canvas.addEventListener('touchstart', onStart, {{passive:false}});
canvas.addEventListener('touchmove',  onMove,  {{passive:false}});
canvas.addEventListener('touchend',   onEnd,   {{passive:false}});
</script>
</body>
</html>"""


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🖊️ PDF Highlighter")
    st.markdown("---")
    uploaded = st.file_uploader("Upload a PDF", type=["pdf"])
    if uploaded:
        new_bytes = uploaded.read()
        if new_bytes != st.session_state.pdf_bytes:
            st.session_state.pdf_bytes = new_bytes
            st.session_state.page_num = 0
            st.session_state.highlights = {}
            render_page_b64.clear()

    st.markdown("### Highlight colour")
    color_choice = st.selectbox("Colour", list(HIGHLIGHT_COLORS_RGB.keys()),
                                label_visibility="collapsed")

    st.markdown("### Zoom")
    zoom = st.slider("Zoom", 1.0, 3.0, 1.5, 0.25, label_visibility="collapsed")
    if zoom != st.session_state.zoom:
        st.session_state.zoom = zoom
        render_page_b64.clear()

    st.markdown("### Options")
    snap = st.toggle("Snap to word boundaries", value=True)

    st.markdown("---")
    total_h = sum(len(v) for v in st.session_state.highlights.values())
    if total_h:
        st.markdown(f"**{total_h}** highlight{'s' if total_h != 1 else ''} added")
    if st.button("🗑️ Clear all highlights", use_container_width=True):
        st.session_state.highlights = {}
        st.rerun()

# ── Main ──────────────────────────────────────────────────────────────────────
st.markdown('<p class="main-title">PDF Highlighter</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="subtitle">Upload a PDF → drag to select text → download with highlights</p>',
    unsafe_allow_html=True,
)

if not st.session_state.pdf_bytes:
    st.markdown('<div class="info-box">👆 Upload a PDF using the sidebar to get started.</div>',
                unsafe_allow_html=True)
    st.stop()

pdf_bytes = st.session_state.pdf_bytes
doc_tmp = fitz.open(stream=pdf_bytes, filetype="pdf")
total_pages = len(doc_tmp)
doc_tmp.close()

# Page navigation
col1, col2, col3 = st.columns([1, 3, 1])
with col1:
    if st.button("◀ Prev", use_container_width=True,
                 disabled=st.session_state.page_num == 0):
        st.session_state.page_num -= 1
        st.rerun()
with col2:
    st.markdown(
        f"<div style='text-align:center;padding-top:6px;font-weight:600;color:#333'>"
        f"Page {st.session_state.page_num + 1} of {total_pages}</div>",
        unsafe_allow_html=True,
    )
with col3:
    if st.button("Next ▶", use_container_width=True,
                 disabled=st.session_state.page_num == total_pages - 1):
        st.session_state.page_num += 1
        st.rerun()

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

page_num = st.session_state.page_num
zoom     = st.session_state.zoom
b64_img, img_w, img_h = render_page_b64(pdf_bytes, page_num, zoom)
page_key = str(page_num)
saved    = st.session_state.highlights.get(page_key, [])

existing_canvas = [
    {
        "x": h["rect"][0] * zoom,
        "y": h["rect"][1] * zoom,
        "w": (h["rect"][2] - h["rect"][0]) * zoom,
        "h": (h["rect"][3] - h["rect"][1]) * zoom,
        "color": CANVAS_COLORS.get(h["color"], "rgba(255,255,0,0.35)"),
    }
    for h in saved
]

st.markdown(
    '<div class="info-box">🖱️ <strong>Click and drag</strong> over text to highlight. '
    'After dragging, click <strong>Apply highlight</strong> below.</div>',
    unsafe_allow_html=True,
)

# Render the HTML5 canvas
components.html(
    make_canvas_html(b64_img, img_w, img_h, CANVAS_COLORS[color_choice], existing_canvas),
    height=img_h + 30,
    scrolling=False,
)

# ── Capture rect from canvas via hidden text input ────────────────────────────
# JS posts a message; we intercept it and inject it into a Streamlit text_input
st.markdown("""
<script>
window.addEventListener("message", function(e) {
    if (!e.data || e.data.type !== "pdf_highlight") return;
    const json = JSON.stringify(e.data.rect);
    // Find our target input by its data-testid or placeholder
    const inputs = window.parent.document.querySelectorAll('input[type="text"]');
    for (const inp of inputs) {
        if (inp.dataset.rectTarget === "1" ||
            (inp.placeholder && inp.placeholder.includes("rect-data"))) {
            inp.value = json;
            inp.dispatchEvent(new Event("input", {bubbles: true}));
            break;
        }
    }
});
</script>
""", unsafe_allow_html=True)

rect_json = st.text_input(
    "rect-data",
    key="rect_input",
    label_visibility="collapsed",
    placeholder="rect-data — auto-filled after drag",
)

col_apply, col_undo = st.columns(2)
with col_apply:
    if st.button("✅ Apply highlight", use_container_width=True):
        raw = (rect_json or "").strip()
        if raw:
            try:
                r = json.loads(raw)
                cx, cy, cw, ch = r["x"], r["y"], r["w"], r["h"]
                px0, py0 = cx / zoom, cy / zoom
                px1, py1 = (cx + cw) / zoom, (cy + ch) / zoom
                if snap:
                    px0, py0, px1, py1 = snap_to_words(
                        pdf_bytes, page_num, (px0, py0, px1, py1), zoom
                    )
                hl = {"rect": [px0, py0, px1, py1], "color": color_choice}
                st.session_state.highlights.setdefault(page_key, []).append(hl)
                st.rerun()
            except Exception as ex:
                st.error(f"Could not parse selection: {ex}")
        else:
            st.warning("Draw a selection on the PDF first.")

with col_undo:
    if st.button("↩️ Undo last", use_container_width=True):
        if st.session_state.highlights.get(page_key):
            st.session_state.highlights[page_key].pop()
            if not st.session_state.highlights[page_key]:
                del st.session_state.highlights[page_key]
            st.rerun()

# ── Download ──────────────────────────────────────────────────────────────────
st.markdown("---")
total_highlights = sum(len(v) for v in st.session_state.highlights.values())

dl_col, stat_col = st.columns([3, 1])
with stat_col:
    st.markdown(
        f"<div class='stat-box'><strong style='font-size:1.4rem'>{total_highlights}</strong>"
        f"<br><span style='font-size:0.8rem;color:#888'>"
        f"highlight{'s' if total_highlights != 1 else ''}</span></div>",
        unsafe_allow_html=True,
    )
with dl_col:
    if total_highlights > 0:
        annotated = build_annotated_pdf(pdf_bytes, st.session_state.highlights)
        st.download_button(
            label="⬇️ Download highlighted PDF",
            data=annotated,
            file_name="highlighted.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    else:
        st.info("Draw highlights on the page above, then download here.")
