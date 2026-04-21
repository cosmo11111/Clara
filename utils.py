"""
utils.py — Shared helper functions for PDF processing, Gemini AI, and data parsing.
"""
from __future__ import annotations
import io
import base64
import json

import fitz
import pdfplumber
import streamlit as st
import plotly.graph_objects as go
import google.generativeai as genai


# ── Colour fill map for redaction annotations ─────────────────────────────────
COLORS_FILL = {
    "Yellow":  "rgba(255,230,0,0.35)",
    "Red":     "rgba(248,113,113,0.35)",
    "Blue":    "rgba(96,165,250,0.35)",
    "Green":   "rgba(52,211,153,0.35)",
}


# ── Amount parsing ────────────────────────────────────────────────────────────
def parse_amount(v) -> float:
    """Parse a transaction amount from various formats to float."""
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace(",", "").replace("$", "").replace("+", "").strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


# ── PDF rendering ─────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def render_page_b64(pdf_bytes: bytes, page_num: int, zoom: float):
    """Render a PDF page to a base64-encoded PNG."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pix = doc[page_num].get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    doc.close()
    return base64.b64encode(pix.tobytes("png")).decode(), pix.width, pix.height


def snap_to_words(pdf_bytes: bytes, page_num: int, rect: tuple) -> tuple:
    """Expand a selection rect to snap to the nearest word boundaries."""
    x0, y0, x1, y1 = rect
    hits = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for w in (pdf.pages[page_num].extract_words() or []):
            if w["x0"] < x1 and w["x1"] > x0 and w["top"] < y1 and w["bottom"] > y0:
                hits.append((w["x0"], w["top"], w["x1"], w["bottom"]))
    if not hits:
        return rect
    return (
        min(h[0] for h in hits),
        min(h[1] for h in hits),
        max(h[2] for h in hits),
        max(h[3] for h in hits),
    )


def apply_redactions(original_bytes: bytes, annotations: dict) -> bytes:
    """Burn redaction annotations into a new PDF and return the bytes."""
    doc = fitz.open(stream=original_bytes, filetype="pdf")
    for pn_str, ann_list in annotations.items():
        page = doc[int(pn_str)]
        for ann in [a for a in ann_list if a["type"] == "redact"]:
            page.add_redact_annot(fitz.Rect(*ann["rect"]), fill=(0, 0, 0))
        page.apply_redactions()
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def extract_text_all_pages(pdf_bytes: bytes) -> str:
    """Extract all text from a PDF, page by page."""
    text = ""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for i, page in enumerate(pdf.pages):
            t = page.extract_text()
            if t:
                text += f"\n--- Page {i+1} ---\n{t}"
    return text.strip()


# ── Plotly figure builder ─────────────────────────────────────────────────────
def make_figure(b64: str, img_w: int, img_h: int,
                annotations: list, pending, zm: float) -> go.Figure:
    """Build a Plotly figure for the PDF viewer with redaction overlays."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=[0, img_w], y=[0, img_h], mode="markers",
        marker=dict(opacity=0), showlegend=False, hoverinfo="none"
    ))
    fig.add_layout_image(dict(
        source=f"data:image/png;base64,{b64}",
        xref="x", yref="y", x=0, y=img_h,
        sizex=img_w, sizey=img_h, sizing="stretch", layer="below",
    ))
    shapes = []
    for ann in annotations:
        px0, py0, px1, py1 = ann["rect"]
        cx0, cx1 = px0 * zm, px1 * zm
        cy_top, cy_bottom = img_h - py0 * zm, img_h - py1 * zm
        fill = ("rgba(0,0,0,1)" if ann["type"] == "redact"
                else COLORS_FILL.get(ann["color"], "rgba(255,255,0,0.35)"))
        shapes.append(dict(
            type="rect", xref="x", yref="y",
            x0=cx0, x1=cx1, y0=cy_bottom, y1=cy_top,
            fillcolor=fill, line=dict(width=0), layer="above"
        ))
    if pending:
        px0, py0, px1, py1 = pending
        shapes.append(dict(
            type="rect", xref="x", yref="y",
            x0=px0 * zm, x1=px1 * zm,
            y0=img_h - py1 * zm, y1=img_h - py0 * zm,
            fillcolor="rgba(248,113,113,0.15)",
            line=dict(width=2, color="rgba(248,113,113,0.8)", dash="dot"),
            layer="above"
        ))
    fig.update_layout(
        width=img_w, height=img_h,
        margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(range=[0, img_w], showgrid=False, zeroline=False,
                   showticklabels=False, fixedrange=False),
        yaxis=dict(range=[0, img_h], showgrid=False, zeroline=False,
                   showticklabels=False, scaleanchor="x", fixedrange=False),
        dragmode="select", selectdirection="any",
        newselection=dict(line=dict(color="rgba(220,50,50,0.9)", width=2, dash="dot")),
        selections=[],
        shapes=shapes,
        plot_bgcolor="#1a1a1a", paper_bgcolor="#1a1a1a",
    )
    return fig


# ── Gemini categorisation ─────────────────────────────────────────────────────
def categorize_with_gemini(text: str, all_categories: dict,
                           vendor_rules: list) -> list:
    """Send bank statement text to Gemini and return categorised transactions."""
    from db import apply_vendor_rules
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel("gemini-2.5-flash-lite-preview-09-2025")
    cat_list = ", ".join(all_categories.keys())
    prompt = f"""Extract ALL transactions from this bank statement text.
Return ONLY a JSON array. Each object must have exactly these keys:
- "date"         (string, e.g. "01 Mar 2026")
- "name"         (string, the raw transaction description exactly as it appears)
- "vendor_clean" (string, a clean human-readable vendor name — e.g. "Ampol" from
                  "AMPOL SUBIACO 44321F", "Netflix" from "NETFLIX 3421987234".
                  For transfers, salary, or transactions with no clear vendor use
                  the raw name as-is. For redacted entries use null.)
- "amount"       (number, negative=debit/expense, positive=credit/income)
- "category"     (one of: {cat_list}. Use "Other" if unclear.)

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
    for t in transactions:
        matched = apply_vendor_rules(vendor_rules, t.get("name", ""))
        if matched:
            t["category"] = matched
    return transactions


# ── Gemini insight ────────────────────────────────────────────────────────────
def generate_insight(total_spend: float, total_income: float,
                     n_tx: int, cat_totals_dict: dict,
                     top_vendors: list) -> str | None:
    """Generate a one-paragraph AI spending insight via Gemini."""
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel("gemini-3-flash-preview")
    prompt = f"""You are a personal finance assistant. Given this spending summary,
provide 1-2 sentences of genuinely useful insight. Focus on something specific and
interesting — a pattern, a standout category, a vendor worth noticing, or a
spend/income relationship. Be conversational and non-judgmental. Do not restate
obvious totals. Do not use the word "great".

Total spend: ${abs(total_spend):,.2f}
Total income: ${total_income:,.2f}
Transaction count: {n_tx}
Category breakdown: {cat_totals_dict}
Top vendors: {top_vendors}"""
    response = model.generate_content(prompt)
    return response.text.strip()
