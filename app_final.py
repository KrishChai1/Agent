import streamlit as st
import json
import fitz  # PyMuPDF
import openai
from io import BytesIO

# Configure OpenAI API key
openai.api_key = st.secrets["OPENAI_API_KEY"]

st.set_page_config(page_title="USCIS Form Parser", layout="wide")
st.title("📄 USCIS Form Smart Parser")

st.write("""
Upload a **USCIS form PDF**, extract fields using AI, and map them:
- Map to your database objects (TS JSON)
- Or move them to a questionnaire JSON
- Download both JSONs separately
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

    prompt = f"""
    You are an expert USCIS form parser. Extract all identifiable fields as JSON keys with example values from this text.
    Ignore formatting details and focus on field names and sample values only.
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

            st.subheader("🗂️ Parsed JSON (Preview)")
            st.json(parsed_json)

            # Initialize containers for TS and Questionnaire
            ts_json = {}
            questionnaire_json = {}

            st.subheader("🔧 Map Fields")

            for key, value in parsed_json.items():
                col1, col2, col3 = st.columns([2, 2, 2])
                with col1:
                    st.markdown(f"**Field:** `{key}`")
                with col2:
                    selected_object = st.selectbox(
                        "Map to DB Object",
                        ["None", "Attorney", "Beneficiary", "Case", "Customer", "Lawfirm", "LCA", "Petitioner"],
                        key=f"map_{key}"
                    )
                with col3:
                    move_to_q = st.checkbox("Move to Questionnaire", key=f"q_{key}")

                if move_to_q or selected_object == "None":
                    questionnaire_json[key] = value
                else:
                    ts_json[key] = {"value": value, "mapped_to": selected_object}

            # Download buttons
            ts_str = json.dumps(ts_json, indent=2)
            q_str = json.dumps(questionnaire_json, indent=2)

            st.download_button(
                "📥 Download TS JSON",
                data=ts_str,
                file_name="ts_mapped.json",
                mime="application/json"
            )
            st.download_button(
                "📥 Download Questionnaire JSON",
                data=q_str,
                file_name="questionnaire.json",
                mime="application/json"
            )

            st.success("✔ JSON files ready for download!")
