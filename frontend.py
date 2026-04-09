import streamlit as st
import fitz  # PyMuPDF
from streamlit_pdf_viewer import pdf_viewer
import io

st.set_page_config(page_title="Highlighter Redactor", layout="wide")
st.title("📑 Highlight to Redact")
st.caption("Upload → Swipe text to highlight → Execute permanent blackout")

# ====================== SESSION STATE ======================
if "pdf_bytes" not in st.session_state:
    st.session_state.pdf_bytes = None
if "redaction_queues" not in st.session_state:
    st.session_state.redaction_queues = []  # Stores selection coordinates

# ====================== UPLOAD ======================
uploaded_file = st.file_uploader("Upload bank statement", type="pdf")

if uploaded_file:
    st.session_state.pdf_bytes = uploaded_file.read()

# ====================== MAIN UI ======================
if st.session_state.pdf_bytes:
    doc = fitz.open(stream=st.session_state.pdf_bytes, filetype="pdf")
    first_page_text = doc[0].get_text()
    
    if not first_page_text.strip():
        st.error("🚨 This PDF is a scanned image. There is no selectable text layer for the highlighter to grab.")
    else:
        st.write("✅ Text detected in PDF. Highlighting should be possible.")
        
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("PDF Viewer")
        st.info("💡 Click and drag your mouse over text to mark it for redaction.")
        
        # Render the PDF with text selection enabled
        # This component returns a dictionary when text is highlighted
        viewer_data = pdf_viewer(
            input=st.session_state.pdf_bytes,
            render_text=True,
            annotations=st.session_state.redaction_queues  # Shows existing marks
        )

        # Capture new highlights from the viewer
        if viewer_data and "last_selection" in viewer_data:
            new_selection = viewer_data["last_selection"]
            if new_selection not in st.session_state.redaction_queues:
                st.session_state.redaction_queues.append(new_selection)
                st.rerun()

    with col2:
        st.subheader("Redaction Queue")
        
        if not st.session_state.redaction_queues:
            st.write("No items marked yet.")
        else:
            st.write(f"Items to redact: {len(st.session_state.redaction_queues)}")
            if st.button("🗑️ Clear All Marks"):
                st.session_state.redaction_queues = []
                st.rerun()

            st.divider()

            if st.button("🔒 Execute Permanent Redaction", type="primary"):
                with st.spinner("Deleting text layers..."):
                    # Open PDF from memory
                    doc = fitz.open(stream=st.session_state.pdf_bytes, filetype="pdf")
                    
                    for item in st.session_state.redaction_queues:
                        # item usually contains: page, x, y, width, height
                        page = doc[item["page"] - 1]
                        # Create a rectangle from coordinates
                        rect = fitz.Rect(item["x"], item["y"], 
                                         item["x"] + item["width"], 
                                         item["y"] + item["height"])
                        
                        # Apply the "Burn"
                        page.add_redact_annot(rect, fill=(0,0,0))
                        page.apply_redactions()

                    # Save the new version to session state
                    st.session_state.pdf_bytes = doc.write()
                    st.session_state.redaction_queues = [] # Clear queue after apply
                    st.success("Redaction Complete!")
                    st.rerun()

    # ====================== DOWNLOAD ======================
    if st.session_state.pdf_bytes:
        st.divider()
        st.download_button(
            label="📥 Download Redacted PDF",
            data=st.session_state.pdf_bytes,
            file_name="redacted_statement.pdf",
            mime="application/pdf"
        )
