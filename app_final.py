import streamlit as st
import json
import re
import fitz  # PyMuPDF
import openai
from datetime import datetime

# Configure OpenAI
openai.api_key = st.secrets["OPENAI_API_KEY"]

db_fields = [
    "Beneficiary.name", "Beneficiary.dob", "Beneficiary.passportNumber",
    "Attorney.name", "Attorney.firmName", "Attorney.phone",
    "Petitioner.companyName", "Petitioner.contactPerson",
    "Case.receiptNumber", "Case.filingDate",
    "Customer.accountNumber", "LawFirm.registrationNumber",
    "LCA.lcaNumber", "Other.notes", "None (Move to Questionnaire)"
]

def extract_parts(text):
    part_pattern = r"(Part\s+\d+\.?\s+[^\n]*)"
    matches = list(re.finditer(part_pattern, text, re.IGNORECASE))
    parts = {}

    for i, match in enumerate(matches):
        part_title = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        part_content = text[start:end].strip()
        parts[part_title] = part_content

    return parts

def ai_smart_map(part_name, part_text):
    prompt = f"""
You are an expert USCIS form parser. Extract key field labels from this part and suggest the most precise DB field from this list:

{', '.join(db_fields)}

Reply strictly as valid JSON only, no explanation or markdown, format:
{{
  "Field Label": {{"suggested_db": "Beneficiary.name"}}
}}

Part title: {part_name}
Part text:
{part_text[:2000]}
"""
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a precise USCIS parser. Reply strictly in valid JSON only, no text or explanation."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )
    content = response.choices[0].message.content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {}

# Streamlit app
st.set_page_config(page_title="🗂️ USCIS Super Smart Mapper", layout="wide")
st.title("🗂️ USCIS Super Smart AI Mapper")

uploaded_file = st.file_uploader("📄 Upload USCIS PDF", type=["pdf"])

if uploaded_file:
    pdf = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    text = ""
    for page in pdf:
        text += page.get_text()

    parts = extract_parts(text)

    final_mappings = {}
    questionnaire_fields = []

    st.header("🗂️ Review & Edit Each Part")

    for part_name, part_text in parts.items():
        st.write(f"Processing: **{part_name}** (using AI smart mapping)")
        ai_fields = ai_smart_map(part_name, part_text)

        with st.expander(part_name, expanded=True):
            lines = [line.strip() for line in part_text.split("\n") if line.strip()]

            # If AI gave valid suggestions, use them. Else fallback to raw lines.
            if ai_fields:
                field_labels = list(ai_fields.keys())
            else:
                field_labels = lines[:20]  # fallback: first 20 lines to avoid overload

            for i, field_label in enumerate(field_labels):
                suggested_db = ai_fields.get(field_label, {}).get("suggested_db", "None (Move to Questionnaire)")

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

    st.header("⬇️ Download Files")
    st.download_button("💾 Download TypeScript Mapping", data=ts_content, file_name=ts_filename, mime="text/plain")
    st.download_button("💾 Download Questionnaire JSON", data=json.dumps(questionnaire_json, indent=2), file_name=json_filename, mime="application/json")

    st.success("✅ Ready! You can download your files above.")

else:
    st.info("📥 Please upload a USCIS PDF to start.")

