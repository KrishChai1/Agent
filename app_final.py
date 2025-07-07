import streamlit as st
import json
import re
import fitz  # PyMuPDF
from datetime import datetime

# Simulated DB object options (example list; extend as needed)
db_objects = ["Attorney", "Beneficiary", "Case", "Customer", "LawFirm", "Petitioner", "Other"]

# Function to extract Parts based on headings (e.g., "Part 1.", "Part 2.")
def extract_parts_from_text(text):
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

# Function to auto-assign DB object (very basic simulation)
def auto_assign_db_object(label):
    for obj in db_objects:
        if obj.lower() in label.lower():
            return obj
    return "Questionnaire"

# Streamlit UI
st.set_page_config(page_title="📄 USCIS Form Smart Reader", layout="wide")
st.title("📄 USCIS Form Smart Reader & Mapper")
st.write("Upload a USCIS PDF form, parse it by parts, map fields to DB objects, and export TypeScript & JSON files.")

uploaded_file = st.file_uploader("Upload a USCIS PDF form", type=["pdf"])

if uploaded_file:
    pdf = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    full_text = ""
    for page in pdf:
        full_text += page.get_text()

    parts = extract_parts_from_text(full_text)

    final_mappings = {}
    questionnaire_fields = []

    st.header("🗂️ Review and Map Parts & Fields")
    for part_name, part_content in parts.items():
        with st.expander(part_name, expanded=True):
            lines = [line.strip() for line in part_content.split("\n") if line.strip()]
            part_mappings = []

            for i, line in enumerate(lines):
                # Simulate line as field label
                default_mapping = auto_assign_db_object(line)
                col1, col2, col3 = st.columns([4, 3, 3])
                with col1:
                    st.text(line[:80])  # Show first 80 chars
                with col2:
                    selected_obj = st.selectbox(
                        f"DB Object for field {i+1} in {part_name}",
                        options=["Questionnaire"] + db_objects,
                        index=db_objects.index(default_mapping) + 1 if default_mapping in db_objects else 0,
                        key=f"{part_name}_{i}_select"
                    )
                with col3:
                    move_to_q = st.checkbox("Move to Questionnaire", key=f"{part_name}_{i}_q")
                
                field_data = {
                    "label": line,
                    "db_object": selected_obj if not move_to_q else "Questionnaire",
                }

                if move_to_q or selected_obj == "Questionnaire":
                    questionnaire_fields.append(field_data)
                else:
                    part_mappings.append(field_data)

            final_mappings[part_name] = part_mappings

    # Generate TS and JSON outputs
    ts_content = "// Auto-generated TypeScript mappings\nexport const formMappings = " + json.dumps(final_mappings, indent=2) + ";"
    ts_filename = f"uscis_form_mappings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.ts"

    questionnaire_json = {
        "questionnaire_fields": questionnaire_fields,
        "generated_at": datetime.now().isoformat()
    }
    json_filename = f"uscis_questionnaire_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    st.header("⬇️ Download Outputs")

    st.download_button("💾 Download TypeScript Mapping", data=ts_content, file_name=ts_filename, mime="text/plain")
    st.download_button("💾 Download Questionnaire JSON", data=json.dumps(questionnaire_json, indent=2), file_name=json_filename, mime="application/json")

    st.success("✅ Parts and fields parsed successfully. You can download files above.")

else:
    st.info("📥 Please upload a USCIS PDF form to get started.")

