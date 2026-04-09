import streamlit as st
import pdfplumber
import google.generativeai as genai
import json

# 1. Setup API
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# Use the 2026 current flash model
model = genai.GenerativeModel('gemini-3-flash-preview')

st.title("AI Expense Prototype")

uploaded_file = st.file_uploader("Upload bank statement (PDF)", type="pdf")

if uploaded_file:
    with pdfplumber.open(uploaded_file) as pdf:
        # Extract text from the first page for the test
        text = pdf.pages[0].extract_text()

    if st.button("Categorize Transactions"):
        # Explicitly ask for JSON so the API doesn't complain
        prompt = f"""
        Extract transactions from this text. 
        Return a JSON list of objects with: "date", "name", "price", "category".
        If category is unclear, use "unknown".
        Text: {text}
        """
        
        try:
            response = model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            data = json.loads(response.text)
            st.dataframe(data) # Interactive table
        except Exception as e:
            st.error(f"Error: {e}")
