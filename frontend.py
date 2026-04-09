import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import io
from streamlit_drawable_canvas import st_canvas

st.set_page_config(page_title="PDF Redaction Tool", layout="wide")
st.title("🖍️ PDF Redaction Tool")
st.caption("Upload → Draw to redact → Apply permanent blackouts → Download redacted PDF → Send to AI")

# ====================== SESSION STATE ======================
if "original_bytes" not in st.session_state:
    st.session_state.original_bytes = None
if "working_doc" not in st.session_state:
    st.session_state.working_doc = None
if "current_page" not in st.session_state:
    st.session_state.current_page = 0

# ====================== UPLOAD ======================
uploaded_file = st.file_uploader("Upload your bank statement (PDF)", type="pdf")

if uploaded_file and st.session_state.original_bytes is None:
    st.session_state.original_bytes = uploaded_file.getvalue()
    st.session_state.working_doc = fitz.open(stream=st.session_state.original_bytes, filetype="pdf")
    st.session_state.current_page = 0
    st.success("PDF loaded! Start redacting below.")

# ====================== MAIN APP ======================
if st.session_state.working_doc:
    doc = st.session_state.working_doc
    num_pages = len(doc)

    col1, col2 = st.columns([1, 3])

    with col1:
        st.subheader("Navigation")
        
        # Use the key "current_page" directly in the slider. 
        # This automatically syncs st.session_state.current_page with the slider.
        page_num = st.slider(
            "Page", 
            0, 
            num_pages - 1, 
            key="current_page"
        )

    st.caption(f"Showing page {page_num + 1} of {num_pages}")

    if st.button("🔄 Reset all redactions (start over)"):
        st.session_state.working_doc = fitz.open(stream=st.session_state.original_bytes, filetype="pdf")
        # When resetting, we also reset the session state page number
        st.session_state.current_page = 0
        st.rerun()

    with col2:
        # Render current page as high-res image
        page = doc[page_num]
        pix = page.get_pixmap(dpi=220)  # High resolution for crisp drawing
        img_bytes = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_bytes))

        st.image(img, caption=f"Page {page_num + 1} — Draw over anything you want hidden", use_column_width=True)

        # ====================== REDACTION CANVAS ======================
        st.subheader("Draw your redactions")
        st.info("Use **freedraw** to freely highlight anything (account numbers, names, addresses). Use **rect** for clean boxes.")

        drawing_mode = st.selectbox("Tool", ["freedraw", "rect"], index=0)
        stroke_width = st.slider("Brush thickness", 5, 60, 25)

        canvas_result = st_canvas(
            fill_color="rgba(0, 0, 0, 0.9)",      # Black fill for redactions
            stroke_width=stroke_width,
            stroke_color="#000000",
            background_image=img,
            update_streamlit=True,
            height=img.height,
            width=img.width,
            drawing_mode=drawing_mode,
            key=f"canvas_page_{page_num}",       # Unique key per page
        )

        # ====================== APPLY REDACTION ======================
        if st.button("✅ Apply Redactions to This Page", type="primary"):
            if canvas_result.json_data is not None:
                objects = canvas_result.json_data.get("objects", [])
                if objects:
                    # Scale canvas pixels → PDF points
                    scale_x = page.rect.width / img.width
                    scale_y = page.rect.height / img.height

                    for obj in objects:
                        # Every object (rect or freedraw path) has a bounding box
                        if "left" in obj and "top" in obj and "width" in obj and "height" in obj:
                            x0 = obj["left"] * scale_x
                            y0 = obj["top"] * scale_y
                            x1 = (obj["left"] + obj.get("width", 0)) * scale_x
                            y1 = (obj["top"] + obj.get("height", 0)) * scale_y

                            rect = fitz.Rect(x0, y0, x1, y1)
                            page.add_redact_annot(rect, fill=(0, 0, 0))  # Black fill

                    # This actually removes the text underneath and bakes in the black box
                    page.apply_redactions()
                    st.success(f"✅ Redactions permanently applied to page {page_num + 1}!")
                    st.rerun()  # Refresh the image so you see the blacked-out areas
                else:
                    st.warning("Nothing drawn yet!")
            else:
                st.warning("Draw something first")

    # ====================== REDACTED PREVIEW & DOWNLOAD ======================
    st.divider()
    st.subheader("Redacted PDF Preview")
    st.info("The image above now shows the permanent redactions. Scroll through pages to verify.")

    # Download button
    redacted_bytes = doc.write()
    st.download_button(
        label="📥 Download Redacted PDF",
        data=redacted_bytes,
        file_name="redacted_statement.pdf",
        mime="application/pdf",
        use_container_width=True,
    )

    # Optional full redacted PDF viewer (iframe)
    if st.toggle("Show full redacted PDF in browser"):
        base64_pdf = redacted_bytes.decode("latin1") if isinstance(redacted_bytes, bytes) else redacted_bytes
        pdf_display = f"""
        <iframe src="data:application/pdf;base64,{base64_pdf}" 
                width="100%" height="800px" 
                type="application/pdf"></iframe>
        """
        st.markdown(pdf_display, unsafe_allow_html=True)

    # ====================== SEND TO AI (placeholder for later) ======================
    st.divider()
    if st.button("🚀 Send Redacted PDF to AI for categorization", type="secondary"):
        st.info("✅ Redacted PDF ready! (This is where you’ll call your AI model in the next phase)")
        st.session_state.redacted_for_ai = redacted_bytes
        # Future: st.switch_page or call your extraction function here

else:
    st.info("👆 Upload a PDF to begin redaction.")

st.caption("Built as a clean MVP — permanent redaction using PyMuPDF (text is actually removed, not just covered).")
