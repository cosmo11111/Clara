import streamlit as st
import fitz  # PyMuPDF
import pdfplumber
import io
import base64
import plotly.graph_objects as go

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="PDF Annotator", page_icon="🖊️", layout="wide")

st.markdown("""
<style>
  .stApp { background-color: #f5f5f0; }
  .info-box {
    background:#fffbea; border-left:4px solid #f0c040;
    padding:.75rem 1rem; border-radius:4px;
    font-size:.88rem; color:#555; margin-bottom:.5rem;
  }
  .info-box.blue { background:#e8f4fd; border-left-color:#3b9ede; }
  .stat-box {
    background:white; border-radius:8px; padding:.75rem 1rem;
    box-shadow:0 1px 3px rgba(0,0,0,.08); text-align:center;
  }
</style>
""", unsafe_allow_html=True)

COLORS_RGB = {
    "Yellow": (1,1,0), "Green":(0,1,0.4),
    "Cyan":(0,0.9,1),  "Pink":(1,0.4,0.7), "Orange":(1,0.6,0),
}
COLORS_FILL = {
    "Yellow":"rgba(255,255,0,0.35)",  "Green":"rgba(0,255,100,0.35)",
    "Cyan":"rgba(0,220,255,0.35)",    "Pink":"rgba(255,100,180,0.35)",
    "Orange":"rgba(255,153,0,0.35)",
}

for k,v in [("page_num",0),("annotations",{}),("pdf_bytes",None),("zoom",1.5),("pending",None)]:
    if k not in st.session_state:
        st.session_state[k] = v

@st.cache_data(show_spinner=False)
def render_page_b64(pdf_bytes, page_num, zoom):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pix = doc[page_num].get_pixmap(matrix=fitz.Matrix(zoom,zoom), alpha=False)
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

def build_pdf(original_bytes, annotations):
    doc = fitz.open(stream=original_bytes, filetype="pdf")
    for pn_str, ann_list in annotations.items():
        page = doc[int(pn_str)]
        for ann in ann_list:
            rect = fitz.Rect(*ann["rect"])
            if ann["type"] == "highlight":
                a = page.add_highlight_annot(rect)
                a.set_colors(stroke=COLORS_RGB.get(ann["color"],(1,1,0)))
                a.update()
            elif ann["type"] == "redact":
                page.add_redact_annot(rect, fill=(0,0,0))
        page.apply_redactions()
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()

def make_figure(b64, img_w, img_h, annotations, pending, zm):
    # KEY coordinate system:
    # PDF:    x=0 left, y=0 TOP,    points
    # Plotly: x=0 left, y=0 BOTTOM, pixels (img_h = top of page)
    # PDF -> Plotly:  plotly_y = img_h - (pdf_y * zm)
    # Plotly -> PDF:  pdf_y    = (img_h - plotly_y) / zm

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[0,img_w],y=[0,img_h],mode="markers",
                             marker=dict(opacity=0),showlegend=False,hoverinfo="none"))
    fig.add_layout_image(dict(
        source=f"data:image/png;base64,{b64}",
        xref="x", yref="y", x=0, y=img_h,
        sizex=img_w, sizey=img_h, sizing="stretch", layer="below",
    ))

    shapes = []
    for ann in annotations:
        px0,py0,px1,py1 = ann["rect"]
        # Convert PDF points -> canvas pixels, flip y
        cx0 = px0 * zm;  cx1 = px1 * zm
        cy_top    = img_h - py0 * zm   # py0 is top of box in PDF → higher plotly_y
        cy_bottom = img_h - py1 * zm   # py1 is bottom of box in PDF → lower plotly_y
        fill = "rgba(0,0,0,1)" if ann["type"]=="redact" else COLORS_FILL.get(ann["color"],"rgba(255,255,0,0.35)")
        shapes.append(dict(type="rect",xref="x",yref="y",
                           x0=cx0,x1=cx1,y0=cy_bottom,y1=cy_top,
                           fillcolor=fill,line=dict(width=0),layer="above"))

    if pending:
        px0,py0,px1,py1 = pending
        shapes.append(dict(type="rect",xref="x",yref="y",
                           x0=px0*zm, x1=px1*zm,
                           y0=img_h-py1*zm, y1=img_h-py0*zm,
                           fillcolor="rgba(59,158,222,0.15)",
                           line=dict(width=2,color="rgba(59,158,222,0.9)",dash="dot"),
                           layer="above"))

    fig.update_layout(
        width=img_w, height=img_h,
        margin=dict(l=0,r=0,t=0,b=0),
        xaxis=dict(range=[0,img_w],showgrid=False,zeroline=False,showticklabels=False,fixedrange=False),
        yaxis=dict(range=[0,img_h],showgrid=False,zeroline=False,showticklabels=False,scaleanchor="x",fixedrange=False),
        dragmode="select", selectdirection="any",
        shapes=shapes, plot_bgcolor="white", paper_bgcolor="white",
    )
    return fig

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🖊️ PDF Annotator")
    st.markdown("---")
    uploaded = st.file_uploader("Upload a PDF", type=["pdf"])
    if uploaded:
        b = uploaded.read()
        if b != st.session_state.pdf_bytes:
            st.session_state.pdf_bytes = b
            st.session_state.page_num = 0
            st.session_state.annotations = {}
            st.session_state.pending = None
            render_page_b64.clear()

    color = st.selectbox("Highlight colour", list(COLORS_RGB.keys()))
    zoom  = st.slider("Zoom", 1.0, 3.0, st.session_state.zoom, 0.25)
    if zoom != st.session_state.zoom:
        st.session_state.zoom = zoom
        render_page_b64.clear()
    snap = st.toggle("Snap to word boundaries", value=True)
    st.markdown("---")
    hl = sum(1 for v in st.session_state.annotations.values() for a in v if a["type"]=="highlight")
    rd = sum(1 for v in st.session_state.annotations.values() for a in v if a["type"]=="redact")
    if hl: st.caption(f"🟨 {hl} highlight{'s' if hl!=1 else ''}")
    if rd: st.caption(f"⬛ {rd} redaction{'s' if rd!=1 else ''}")
    if st.button("🗑️ Clear all", use_container_width=True):
        st.session_state.annotations = {}
        st.session_state.pending = None
        st.rerun()

# ── Main ──────────────────────────────────────────────────────────────────────
st.markdown("## 🖊️ PDF Annotator")
st.caption("Upload · drag to select · Highlight or Redact · download")

if not st.session_state.pdf_bytes:
    st.markdown('<div class="info-box">👆 Upload a PDF in the sidebar to begin.</div>',unsafe_allow_html=True)
    st.stop()

pdf_bytes = st.session_state.pdf_bytes
doc_tmp   = fitz.open(stream=pdf_bytes, filetype="pdf")
n_pages   = len(doc_tmp); doc_tmp.close()

c1,c2,c3 = st.columns([1,4,1])
with c1:
    if st.button("◀ Prev",use_container_width=True,disabled=st.session_state.page_num==0):
        st.session_state.page_num -= 1; st.session_state.pending=None; st.rerun()
with c2:
    st.markdown(f"<p style='text-align:center;margin:6px 0;font-weight:600'>Page {st.session_state.page_num+1} of {n_pages}</p>",unsafe_allow_html=True)
with c3:
    if st.button("Next ▶",use_container_width=True,disabled=st.session_state.page_num==n_pages-1):
        st.session_state.page_num += 1; st.session_state.pending=None; st.rerun()

pn = st.session_state.page_num
zm = st.session_state.zoom
b64, img_w, img_h = render_page_b64(pdf_bytes, pn, zm)
pk = str(pn)

st.markdown('<div class="info-box">🖱️ <b>Click and drag</b> to select an area. Then click <b>Add Highlight</b> or <b>Redact</b>. The dotted blue box shows your pending selection.</div>',unsafe_allow_html=True)

fig = make_figure(b64, img_w, img_h, st.session_state.annotations.get(pk,[]), st.session_state.pending, zm)

event = st.plotly_chart(fig, use_container_width=False,
                        key=f"chart_{pn}_{zm}", on_select="rerun", selection_mode=["box"])

# Parse box-select → PDF coords
try:
    box = (event.selection.box or [{}])[0]
    xs = box.get("x",[])
    ys = box.get("y",[])
    if len(xs)>=2 and len(ys)>=2:
        # Plotly x is already canvas pixels, divide by zoom for PDF points
        pdf_x0 = min(xs) / zm
        pdf_x1 = max(xs) / zm
        # Plotly y=0 is BOTTOM; PDF y=0 is TOP of page
        # max(ys) is the top of selection in Plotly → smallest PDF y (top of box)
        pdf_y0 = (img_h - max(ys)) / zm
        pdf_y1 = (img_h - min(ys)) / zm
        new = (pdf_x0, pdf_y0, pdf_x1, pdf_y1)
        if new != st.session_state.pending:
            st.session_state.pending = new
            st.rerun()
except Exception:
    pass

if st.session_state.pending:
    px0,py0,px1,py1 = st.session_state.pending
    st.markdown(f'<div class="info-box blue">📌 Selection ready ({px0:.0f},{py0:.0f})→({px1:.0f},{py1:.0f}) pt — apply below</div>',unsafe_allow_html=True)

b1,b2,b3 = st.columns(3)

def commit(ann_type):
    if not st.session_state.pending:
        st.warning("Drag to select an area first.")
        return
    x0,y0,x1,y1 = st.session_state.pending
    if snap:
        x0,y0,x1,y1 = snap_to_words(pdf_bytes, pn, (x0,y0,x1,y1))
    st.session_state.annotations.setdefault(pk,[]).append(
        {"rect":[x0,y0,x1,y1],"color":color,"type":ann_type})
    st.session_state.pending = None
    st.rerun()

with b1:
    if st.button("🟨 Add Highlight",use_container_width=True,type="primary"):
        commit("highlight")
with b2:
    if st.button("⬛ Redact",use_container_width=True):
        commit("redact")
with b3:
    if st.button("↩️ Undo last",use_container_width=True):
        if st.session_state.annotations.get(pk):
            st.session_state.annotations[pk].pop()
            if not st.session_state.annotations[pk]:
                del st.session_state.annotations[pk]
        st.session_state.pending = None
        st.rerun()

st.markdown("---")
total_hl = sum(1 for v in st.session_state.annotations.values() for a in v if a["type"]=="highlight")
total_rd = sum(1 for v in st.session_state.annotations.values() for a in v if a["type"]=="redact")
total    = total_hl + total_rd

dc,sc = st.columns([3,1])
with sc:
    st.markdown(f"<div class='stat-box'><b style='font-size:1.3rem'>{total_hl}</b> <span style='font-size:.8rem;color:#888'>highlight{'s' if total_hl!=1 else ''}</span><br><b style='font-size:1.3rem'>{total_rd}</b> <span style='font-size:.8rem;color:#888'>redaction{'s' if total_rd!=1 else ''}</span></div>",unsafe_allow_html=True)
with dc:
    if total > 0:
        st.download_button("⬇️ Download annotated PDF",
                           data=build_pdf(pdf_bytes,st.session_state.annotations),
                           file_name="annotated.pdf",mime="application/pdf",
                           use_container_width=True)
        if total_rd:
            st.caption("⚠️ Redactions are permanently burned into the downloaded PDF.")
    else:
        st.info("Add highlights or redactions above, then download here.")
