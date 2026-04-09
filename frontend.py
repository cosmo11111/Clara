import streamlit as st
import pdfplumber
import google.generativeai as genai
import json

# 1. Setup API (Use st.secrets in production)
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-1.5-flash')

st.set_page_config(page_title="AI Expense Tracker", page_icon="💰")
st.title("Simple AI Budgeter")

uploaded_file = st.file_uploader("Upload a redacted PDF bank statement", type="pdf")

if uploaded_file is not None:
    # 2. Extract Text from PDF
    with st.spinner("Reading PDF..."):
        with pdfplumber.open(uploaded_file) as pdf:
            # For simplicity, we just grab all text from the first 2 pages
            raw_text = ""
            for page in pdf.pages[:2]:
                raw_text += page.extract_text() or ""

    if raw_text:
        st.success("PDF Text Extracted!")
        
        # 3. AI Categorization Prompt
        # We tell the AI to return ONLY clean JSON
        prompt = f"""
        Extract the transaction date, description, and amount from the following bank statement text. 
        Categorize each transaction. If you can't work it out, return "unknown".
        Return the data as a JSON list of objects with keys: "date", "name", "price", "category".
        
        Statement Text:
        {raw_text}
        """

        if st.button("Categorize with AI"):
            with st.spinner("AI is thinking..."):
                st.write(f"API Key found: {st.secrets['GEMINI_API_KEY'][:5]}***")
                response = model.generate_content(
                    prompt, 
                    generation_config={"response_mime_type": "application/json"}
                )
                
                try:
                    data = json.loads(response.text)
                    st.table(data) # Show the result as a clean table
                except Exception as e:
                    st.error("Failed to parse AI response. Try again.")
                    st.write(response.text)
                    st.exception(e)
    else:
        st.error("Could not read text from this PDF. Is it a scanned image?")
