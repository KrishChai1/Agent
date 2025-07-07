import streamlit as st
import json
import fitz  # PyMuPDF for PDF parsing
import openai
from io import BytesIO

# Configure OpenAI API key
openai.api_key = st.secrets["OPENAI_API_KEY"]

st.set_page_config(page_title="USCIS Form Parser", layout="wide")
st.title("📄 USCIS Form Smart Parser")

st.write("""
Upload a USCIS form (PDF). The app will extract fields, let you review or map them,
and prepare a structured JSON output for your database or questionnaires.
""")

# Upload file
uploaded_file = st.file_uploader("Upload USCIS form (PDF)", type=["pdf"])

if uploaded_file:
    # Read PDF text
    pdf = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    text = ""
    for page in pdf:
        text += page.get_text()
    pdf.close()

    st.subheader("🔎 Extracted Raw Text Preview")
    st.text_area("PDF Text", text, height=300)

    # Send to OpenAI to get key-value pairs (basic example)
    prompt = f"""
    You are an expert USCIS form parser. Extract all identifiable fields as JSON keys with example values from this text.
    Ignore formatting details and just focus on fields.
    Text:
    {text}
    """

    if st.button("Parse with OpenAI"):
        with st.spinner("Parsing..."):
            response = openai.ChatCompletion.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a precise USCIS form parsing assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0
            )
            parsed_content = response.choices[0].message.content

            try:
                parsed_json = json.loads(parsed_content)
            except:
                parsed_json = {"raw_text": parsed_content}

            st.subheader("🗂️ Parsed JSON")
            st.json(parsed_json)

            # Map fields manually
            st.subheader("🔧 Map Fields to Database Objects")

            mapped_json = {}
            for key, value in parsed_json.items():
                col1, col2 = st.columns([2, 2])
                with col1:
                    st.write(f"**Field:** {key}")
                    st.text_input("Value", value, key=f"value_{key}")
                with col2:
                    db_obj = st.selectbox(
                        "Map to DB Object",
                        ["Attorney", "Beneficiary", "Case", "Customer", "Lawfirm", "LCA", "Petitioner", "Questionnaire"],
                        index=7,
                        key=f"map_{key}"
                    )
                    mapped_json[key] = {
                        "value": value,
                        "mapped_to": db_obj
                    }

            # Download button
            json_str = json.dumps(mapped_json, indent=2)
            st.download_button(
                "📥 Download Mapped JSON",
                data=json_str,
                file_name="uscis_form_mapped.json",
                mime="application/json"
            )

            st.success("✔ JSON ready! You can download it now.")

