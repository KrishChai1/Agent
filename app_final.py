import streamlit as st
import json
import re
import fitz  # PyMuPDF
import openai
from datetime import datetime

# Configure OpenAI
openai.api_key = st.secrets["OPENAI_API_KEY"]

# Example DB fields (extend or modify as needed)
db_fields = [
    "Beneficiary.name", "Beneficiary.dob", "Beneficiary.passportNumber",
    "Attorney.name", "Attorney.firmName", "Attorney.phone",
    "Petitioner.companyName", "Petitioner.contactPerson",
    "Case.receiptNumber", "Case.filingDate",
    "Customer.accountNumber", "LawFirm.registrationNumber",
    "LCA.lcaNumber", "Other.notes", "None (Move to Questionnaire)"
]

# Function to extract parts starting from "Part 1"
def extract_parts(text):
    part_pattern = r"(Part\s+\d+\.?.*?)(?=Part\s+\d+\.|$)"
    matches = re.findall(part_pattern, text, re.DOTALL | re.IGNORECASE)
    parts = {}
    for match in matches:
        lines = match.strip().split("\n", 1)
        part_title = lines[0].strip()
        part_content = lines[1].strip() if len(lines) > 1 else ""
        parts[part_title] = part_content
    return parts

# Function to extract fields inside parts
def extract_fields(part_content):
    field_pattern = r"(\d+\.\s+[^\n]+)"
    fields = re.findall(field_pattern, part_content)
    return fields

# Streamlit app
st.set_page_config(page_title="🗂️ USCIS Smart Mapper", layout="wide")
st.title("🗂️ USCIS Form AI Mapper (Accurate Part & Field Extraction)")

uploaded_file = st.file_uploader("📄 Upload USCIS PDF", type=["pdf"])

if uploaded_file:
    pdf = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    text = ""
    for page in pdf:
        text += page.get_text()

    # Extract correct parts
    parts = extract_parts(text)

    final_mappings = {}
    questionnaire_fields = []

    st.header("🗂️ Review & Edit Mappings Per Part")

    for part_name, part_content in parts.items():
        st.write(f"Processing: **{part_name}**")
        fields = extract_fields(part_content)

        with st.expander(part_name, expanded=True):
            for i, field_label in enumerate(fields):
                # Suggest default DB mapping using a simple heuristic or AI call
                suggested_db = "None (Move to Questionnaire)"
                for db in db_fields:
                    if db.split(".")[0].lower() in field_label.lower():
                        suggested_db = db
                        break

                col1, col2, col3 = st.columns([4, 4, 2])
                with col1:
                    st.text_input("Field Label", field_label, key=f"label_{part_name}_{i}", disabled=True)
                with col2:
                    selected_db = st.selectbox(
                        "DB Field",
                        db_fields,
                        index=db_fields.index(suggested_db) if suggested_db in db_fields else db_fields.index("None (Move to Questionnaire)"),
                        key=f"db_{part_name}_{i}"
                    )
                with col3:
                    move_to_q = st.checkbox("Move to Questionnaire", key=f"q_{part_name}_{i}")

                field_data = {
                    "label": field_label,
                    "db_field": selected_db if not move_to_q else "Questionnaire"
                }

                if move_to_q or selected_db == "None (Move to Questionnaire)":
                    questionnaire_fields.append(field_data)
                else:
                    if part_name not in final_mappings:
                        final_mappings[part_name] = []
                    final_mappings[part_name].append(field_data)

    # TypeScript mapping
    ts_content = "// Auto-generated TypeScript mappings\nexport const formMappings = " + json.dumps(final_mappings, indent=2) + ";"
    ts_filename = f"uscis_mappings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.ts"

    # Questionnaire JSON
    questionnaire_json = {
        "questionnaire_fields": questionnaire_fields,
        "generated_at": datetime.now().isoformat()
    }
    json_filename = f"uscis_questionnaire_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    st.header("⬇️ Download Your Files")
    st.download_button("💾 Download TypeScript Mapping", data=ts_content, file_name=ts_filename, mime="text/plain")
    st.download_button("💾 Download Questionnaire JSON", data=json.dumps(questionnaire_json, indent=2), file_name=json_filename, mime="application/json")

    st.success("✅ All done! You can download your files above.")

else:
    st.info("📥 Please upload a USCIS PDF to start.")

