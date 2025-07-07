import streamlit as st
import json
import fitz  # PyMuPDF
import openai
from io import BytesIO
import re

# Configure OpenAI API key
openai.api_key = st.secrets["OPENAI_API_KEY"]

st.set_page_config(page_title="🗂️ USCIS Form Smart Parser", layout="wide")
st.title("🗂️ USCIS Form Smart Parser & DB Mapper")

st.markdown("""
Upload a USCIS form PDF and extract fields part by part. 
The app tries to assign each field automatically to database objects, but you can override or move them to a questionnaire.
""")

# Upload PDF
uploaded_file = st.file_uploader("📤 Upload USCIS form (PDF)", type=["pdf"])

if uploaded_file:
    # Read PDF text
    pdf = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    text = ""
    for page in pdf:
        text += page.get_text()
    pdf.close()

    st.subheader("🔎 Extracted Text Preview")
    st.text_area("PDF Text", text, height=300)

    prompt = f"""
    You are an expert USCIS form parsing assistant. Extract the fields part by part (e.g., Part 1, Part 2, etc.).
    Output a JSON with each part as a key containing a dictionary of fields with example values.
    Also suggest which DB object each field could be assigned to: Attorney, Beneficiary, Case, Customer, Lawfirm, LCA, Petitioner, or leave blank.
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

    if st.button("🔍 Extract and Suggest Assignments"):
        with st.spinner("Parsing and analyzing..."):
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
                parts_json = {"error": "Could not parse JSON", "raw_response": parsed_content}

            ts_json = {}
            questionnaire_json = {}

            st.subheader("🧩 Part-by-Part Review & Mapping")

           for part_name, fields in parts_json.items():
    with st.expander(f"📄 {part_name}", expanded=False):

        if isinstance(fields, dict):
            for field_name, field_data in fields.items():
                value = field_data.get("value", "") if isinstance(field_data, dict) else ""
                suggested_db = field_data.get("suggested_db", "") if isinstance(field_data, dict) else "None"

                col1, col2, col3 = st.columns([3, 3, 2])
                with col1:
                    st.markdown(f"**{field_name}**")
                    st.text_input("Value", value, key=f"val_{part_name}_{field_name}")

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
                    move_to_q = st.checkbox("Questionnaire", key=f"q_{part_name}_{field_name}")

                if move_to_q or selected_db == "None":
                    questionnaire_json[field_name] = value
                else:
                    ts_json[field_name] = {"value": value, "mapped_to": selected_db}
        else:
            st.warning(f"⚠️ Skipping {part_name}: Expected a dictionary, got {type(fields).__name__}.")


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

            st.success("✔ JSON files are ready for download!")

