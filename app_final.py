import streamlit as st
import json
import fitz  # PyMuPDF
import openai
from io import BytesIO

# Configure OpenAI API key
openai.api_key = st.secrets["OPENAI_API_KEY"]

st.set_page_config(page_title="🗂️ USCIS Smart Form Reader", layout="wide")
st.title("🗂️ USCIS Smart Form Reader & DB Mapper")

st.markdown("""
Upload a USCIS form (PDF). This app will:
- Extract fields **part by part** (e.g., Part 1, Part 2).
- **Auto-assign each field** to a database object (Attorney, Beneficiary, etc.).
- Allow you to override assignments or move fields to a questionnaire.
- Download separate JSON files for DB (TS) and Questionnaire fields.
""")

# Upload PDF
uploaded_file = st.file_uploader("📤 Upload USCIS form (PDF)", type=["pdf"])

if uploaded_file:
    # Extract text from PDF
    pdf = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    text = ""
    for page in pdf:
        text += page.get_text()
    pdf.close()

    st.subheader("🔎 Extracted Text Preview")
    st.text_area("PDF Text", text, height=300)

    # Prompt for AI parsing
    prompt = f"""
    You are an expert USCIS form parsing assistant. 
    Split this text into logical parts (e.g., Part 1, Part 2).
    For each part, extract fields as key-value pairs and suggest a DB object (Attorney, Beneficiary, Case, Customer, Lawfirm, LCA, Petitioner). 
    Example output:
    {{
        "Part 1": {{
            "Family Name": {{"value": "Doe", "suggested_db": "Beneficiary"}},
            ...
        }},
        ...
    }}
    Text:
    {text}
    """

    if st.button("🔍 Extract & Auto-Map Fields"):
        with st.spinner("Analyzing form and auto-mapping..."):
            response = openai.ChatCompletion.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a precise USCIS form parsing and mapping expert."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0
            )
            parsed_content = response.choices[0].message.content

            try:
                parts_json = json.loads(parsed_content)
            except:
                st.error("❌ Could not parse AI response as JSON. Showing raw response below for reference.")
                st.text_area("Raw AI Response", parsed_content, height=300)
                st.stop()

            ts_json = {}
            questionnaire_json = {}

            st.subheader("🧩 Part-by-Part Review & Mapping")

            for part_name, fields in parts_json.items():
                with st.expander(f"📄 {part_name}", expanded=False):

                    if isinstance(fields, dict):
                        for field_name, field_data in fields.items():
                            if isinstance(field_data, dict):
                                value = field_data.get("value", "")
                                suggested_db = field_data.get("suggested_db", "None")
                            else:
                                value = ""
                                suggested_db = "None"

                            col1, col2, col3 = st.columns([3, 3, 2])
                            with col1:
                                st.markdown(f"**{field_name}**")
                                value_input = st.text_input("Value", value, key=f"val_{part_name}_{field_name}")

                            with col2:
                                selected_db = st.selectbox(
                                    "Assign to DB Object",
                                    ["None", "Attorney", "Beneficiary", "Case", "Customer", "Lawfirm", "LCA", "Petitioner"],
                                    index=["None", "Attorney", "Beneficiary", "Case", "Customer", "Lawfirm", "LCA", "Petitioner"].index(
                                        suggested_db if suggested_db in ["Attorney", "Beneficiary", "Case", "Customer", "Lawfirm", "LCA", "Petitioner"] else "None"
                                    ),
                                    key=f"db_{part_name}_{field_name}"
                                )

                            with col3:
                                move_to_q = st.checkbox("Move to Questionnaire", key=f"q_{part_name}_{field_name}")

                            if move_to_q or selected_db == "None":
                                questionnaire_json[field_name] = value_input
                            else:
                                ts_json[field_name] = {"value": value_input, "mapped_to": selected_db}
                    else:
                        st.warning(f"⚠️ Skipping {part_name}: Expected a dictionary but got {type(fields).__name__}.")

            # Download buttons
            ts_str = json.dumps(ts_json, indent=2)
            q_str = json.dumps(questionnaire_json, indent=2)

            st.download_button(
                "📥 Download TS JSON (DB Mappings)",
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
