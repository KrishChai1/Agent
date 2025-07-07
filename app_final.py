import streamlit as st
import json
import fitz  # PyMuPDF
import openai
from io import BytesIO

# Configure OpenAI API key
openai.api_key = st.secrets["OPENAI_API_KEY"]

st.set_page_config(page_title="🗂️ USCIS Smart Form Mapper", layout="wide")
st.title("🗂️ USCIS Smart Form Reader & DB Object Mapper")

st.markdown("""
Upload a USCIS PDF form, extract fields **part by part**, auto-map to DB objects, or assign manually.
- Move unmapped or checkbox-type fields to Questionnaire JSON.
- Download ready-made TS and Questionnaire JSON files.
""")

# Upload PDF
uploaded_file = st.file_uploader("📄 Upload USCIS form (PDF)", type=["pdf"])

if uploaded_file:
    # Extract text
    pdf = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    text = ""
    for page in pdf:
        text += page.get_text()
    pdf.close()

    st.subheader("📄 Extracted Text Preview")
    st.text_area("Form Text", text, height=300)

    # Define DB object options (example set)
    db_objects = ["Attorney", "Beneficiary", "Case", "Customer", "Lawfirm", "LCA", "Petitioner", "None"]

    prompt = f"""
    You are an expert at extracting structured fields from USCIS forms.
    Please break this text into logical parts (e.g., Part 1, Part 2). 
    For each part, list fields with labels and suggest one DB object (Attorney, Beneficiary, Case, Customer, Lawfirm, LCA, Petitioner).
    Provide JSON format: 
    {{
      "Part 1": {{
          "Field Label": {{"value": "", "suggested_db": "Attorney"}},
          ...
      }},
      ...
    }}
    Here is the text:
    {text}
    """

    if st.button("🔍 Parse & Auto-Map"):
        with st.spinner("Parsing with AI..."):
            response = openai.ChatCompletion.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a precise USCIS form parsing and mapping assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0
            )
            parsed_content = response.choices[0].message.content

            try:
                parts_json = json.loads(parsed_content)
            except json.JSONDecodeError:
                st.error("❌ AI response is not valid JSON. Showing raw output for debugging.")
                st.text_area("Raw AI Response", parsed_content, height=300)
                st.stop()

            ts_json = {}
            questionnaire_json = {}

            st.subheader("🧩 Review & Adjust Mappings Part by Part")

            for part_name, fields in parts_json.items():
                with st.expander(f"📄 {part_name}", expanded=False):
                    if isinstance(fields, dict):
                        for field_label, field_data in fields.items():
                            if isinstance(field_data, dict):
                                value = field_data.get("value", "")
                                suggested_db = field_data.get("suggested_db", "None")
                            else:
                                value = ""
                                suggested_db = "None"

                            col1, col2, col3 = st.columns([4, 3, 3])
                            with col1:
                                st.text_input("Field Label", field_label, key=f"label_{part_name}_{field_label}", disabled=True)
                            with col2:
                                selected_db = st.selectbox(
                                    "DB Object",
                                    db_objects,
                                    index=db_objects.index(suggested_db) if suggested_db in db_objects else db_objects.index("None"),
                                    key=f"db_{part_name}_{field_label}"
                                )
                            with col3:
                                move_to_q = st.checkbox("Move to Questionnaire", key=f"q_{part_name}_{field_label}")

                            # Update mappings
                            if move_to_q or selected_db == "None":
                                questionnaire_json[field_label] = {"value": value}
                            else:
                                ts_json[field_label] = {"value": value, "mapped_to": selected_db}
                    else:
                        st.warning(f"⚠️ Skipping {part_name}: Unexpected structure.")

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

