import streamlit as st
import json
import fitz  # PyMuPDF
import openai
import re

# Configure OpenAI API key
openai.api_key = st.secrets["OPENAI_API_KEY"]

st.set_page_config(page_title="🗂️ USCIS Smart Form Reader", layout="wide")
st.title("🗂️ USCIS Smart Form Reader & Flexible DB Mapper")

st.markdown("""
Upload a USCIS PDF form. The app will:
- Auto-assign each field to a suggested DB object using AI.
- You can **modify or override** any mapping using dropdowns.
- Move any field to Questionnaire if you'd like.
- Download TS JSON and Questionnaire JSON separately.
""")

uploaded_file = st.file_uploader("📄 Upload USCIS form (PDF)", type=["pdf"])

if uploaded_file:
    pdf = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    text = ""
    for page in pdf:
        text += page.get_text()
    pdf.close()

    st.subheader("📄 Extracted Text Preview")
    st.text_area("Form Text", text, height=300)

    parts = re.split(r"(Part\s\d+)", text)
    grouped_parts = {}

    for i in range(1, len(parts), 2):
        part_title = parts[i].strip()
        part_content = parts[i + 1].strip() if i + 1 < len(parts) else ""
        grouped_parts[part_title] = part_content

    db_objects = ["None", "Attorney", "Beneficiary", "Case", "Customer", "Lawfirm", "LCA", "Petitioner"]

    ts_json = {}
    questionnaire_json = {}

    if st.button("🔍 Parse & Auto-Assign (Editable)"):
        for part_name, part_text in grouped_parts.items():
            st.write(f"Processing: **{part_name}**")

            short_prompt = f"""
            Extract field labels and example values from this USCIS form part.
            Suggest a likely DB object for each field: Attorney, Beneficiary, Case, Customer, Lawfirm, LCA, Petitioner, or None.
            Return **strict valid JSON only**, no commentary, no markdown. Format:
            {{
              "Field Label": {{"value": "example value", "suggested_db": "Beneficiary"}},
              ...
            }}
            Text:
            {part_text[:3000]}
            """

            response = openai.ChatCompletion.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a precise USCIS parser. Reply strictly in valid JSON only. No explanations, no markdown, no comments."},
                    {"role": "user", "content": short_prompt}
                ],
                temperature=0
            )
            raw_content = response.choices[0].message.content.strip()

            # Try direct JSON parse first
            try:
                fields_dict = json.loads(raw_content)
            except json.JSONDecodeError:
                # Try to extract JSON content using regex as fallback
                match = re.search(r"(\{.*\})", raw_content, re.DOTALL)
                if match:
                    json_str = match.group(1)
                    try:
                        fields_dict = json.loads(json_str)
                    except json.JSONDecodeError:
                        st.error(f"⚠️ Still couldn't parse JSON for {part_name}. Showing raw output below for manual review.")
                        st.text_area(f"Raw AI Output for {part_name}", raw_content, height=300)
                        continue
                else:
                    st.error(f"⚠️ No JSON structure found in AI output for {part_name}. Showing raw output below.")
                    st.text_area(f"Raw AI Output for {part_name}", raw_content, height=300)
                    continue

            with st.expander(f"📄 {part_name}", expanded=False):
                for field_label, field_info in fields_dict.items():
                    value = field_info.get("value", "")
                    suggested_db = field_info.get("suggested_db", "None")

                    col1, col2, col3 = st.columns([4, 3, 3])
                    with col1:
                        st.text_input("Field Label", field_label, key=f"label_{part_name}_{field_label}", disabled=True)
                    with col2:
                        selected_db = st.selectbox(
                            "DB Object",
                            db_objects,
                            index=db_objects.index(suggested_db) if suggested_db in db_objects else 0,
                            key=f"db_{part_name}_{field_label}"
                        )
                    with col3:
                        move_to_q = st.checkbox("Move to Questionnaire", key=f"q_{part_name}_{field_label}")

                    if move_to_q or selected_db == "None":
                        questionnaire_json[field_label] = {"value": value}
                    else:
                        ts_json[field_label] = {"value": value, "mapped_to": selected_db}

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
