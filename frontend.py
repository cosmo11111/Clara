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
                # 1. Clean the text first
                clean_text = raw_text.replace('\xa0', ' ').strip()
                
                # 2. Use a more explicit config
                generation_config = {
                    "temperature": 0.1,  # Low temperature is better for data extraction
                    "response_mime_type": "application/json",
                }
                
                try:
                    # Use a simpler prompt for the prototype test
                    simple_prompt = f"Convert this bank statement text into a JSON list of transactions. Text: {clean_text}"
                    
                    response = model.generate_content(
                        simple_prompt,
                        generation_config=generation_config
                    )
                    
                    # 3. Print the raw response to the screen so you can see it if it fails
                    st.write("AI Response Received!")
                    st.json(response.text)
                    
                except Exception as e:
                    st.error("Something went wrong with the AI call.")
                    st.write(str(e)) # This will show the EXACT reason (e.g., 400 Invalid Argument)
    else:
        st.error("Could not read text from this PDF. Is it a scanned image?")
