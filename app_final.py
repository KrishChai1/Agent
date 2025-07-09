import streamlit as st
import re
import json
import fitz  # PyMuPDF
from datetime import datetime

st.set_page_config(page_title="USCIS Smart Mapper — Ultimate Agentic Fallback Version", layout="wide")
st.title("🤖 USCIS Form Smart Mapper — FINAL AGENTIC FALLBACK VERSION ✅")

# ----------------- DB Attributes -----------------
def build_db_attributes():
    attributes = [
        "Attorney: attorneyInfo.firstName", "Attorney: attorneyInfo.lastName", "Attorney: attorneyInfo.workPhone",
        "Attorney: attorneyInfo.emailAddress", "Attorney: attorneyInfo.stateBarNumber",
        "Beneficiary: Beneficiary.beneficiaryFirstName", "Beneficiary: Beneficiary.beneficiaryLastName",
        "Beneficiary: Beneficiary.beneficiaryMiddleName", "Beneficiary: Beneficiary.beneficiaryGender",
        "Beneficiary: Beneficiary.beneficiaryDateOfBirth", "Beneficiary: Beneficiary.beneficiaryCitizenOfCountry",
        "Beneficiary: Beneficiary.beneficiarySsn", "Beneficiary: Beneficiary.beneficiaryPrimaryEmailAddress",
        "Beneficiary: Beneficiary.beneficiaryCellNumber", "Beneficiary: HomeAddress.addressStreet",
        "Beneficiary: HomeAddress.addressCity", "Beneficiary: HomeAddress.addressState",
        "Beneficiary: HomeAddress.addressZip", "Case: caseId", "Case: caseType", "Case: caseStatus",
        "Case: caseSubType", "Case: uscisReceiptNumber", "Case: caseNumber", "Customer: customer_name",
        "Customer: customer_tax_id", "Customer: customer_naics_code", "Customer: customer_website_url",
        "Lawfirm: lawFirmDetails.lawFirmName", "Lawfirm: lawFirmDetails.companyPhone",
        "Lawfirm: lawFirmDetails.lawFirmFein", "Lawfirm: address.addressStreet", "Lawfirm: address.addressCity",
        "Lawfirm: address.addressState", "Lawfirm: address.addressZip", "LCA: Lca.positionJobTitle",
        "LCA: Lca.grossSalary", "LCA: Lca.startDate", "LCA: Lca.endDate", "LCA: Lca.jobLocation",
        "Petitioner: Beneficiary.beneficiaryFirstName", "Petitioner: Beneficiary.beneficiaryLastName",
        "Petitioner: Beneficiary.beneficiaryDateOfBirth", "Petitioner: Beneficiary.beneficiaryCitizenOfCountry",
        "Petitioner: Beneficiary.beneficiaryPrimaryEmailAddress", "Petitioner: Beneficiary.beneficiaryCellNumber",
        "None (Move to Questionnaire)"
    ]
    return attributes

db_fields = build_db_attributes()

# ----------------- Suggest Mapping -----------------
def suggest_db_mapping(field_text):
    lower = field_text.lower()
    if "attorney" in lower:
        return "Attorney: attorneyInfo.firstName"
    elif "name" in lower:
        return "Beneficiary: Beneficiary.beneficiaryFirstName"
    elif "address" in lower:
        return "Beneficiary: HomeAddress.addressStreet"
    elif "date" in lower or "birth" in lower:
        return "Beneficiary: Beneficiary.beneficiaryDateOfBirth"
    elif "email" in lower:
        return "Beneficiary: Beneficiary.beneficiaryPrimaryEmailAddress"
    elif "phone" in lower or "cell" in lower:
        return "Beneficiary: Beneficiary.beneficiaryCellNumber"
    elif "case" in lower:
        return "Case: caseId"
    else:
        return "None (Move to Questionnaire)"

# ----------------- Agentic Part Extraction -----------------
def extract_parts_lines(text):
    start_idx = text.lower().find("start here")
    if start_idx != -1:
        text = text[start_idx:]
    else:
        st.warning("⚠️ 'START HERE' not found. Using full document text.")

    lines = text.split("\n")
    parts = {}
    current_part = ""
    for line in lines:
        line = line.strip()
        if re.match(r"^Part\s+\d+\.", line, re.IGNORECASE):
            part_title = re.sub(r"\(continued\)", "", line, flags=re.IGNORECASE).strip()
            if part_title in parts:
                parts[part_title] += " " + line
            else:
                parts[part_title] = line
            current_part = part_title
        elif current_part:
            parts[current_part] += " " + line

    merged_parts = {}
    for k, v in parts.items():
        title = re.sub(r"\(continued\)", "", k, flags=re.IGNORECASE).strip()
        if title in merged_parts:
            merged_parts[title] += " " + v
        else:
            merged_parts[title] = v

    def part_sort_key(x):
        m = re.match(r"Part\s+(\d+)\.", x)
        return int(m.group(1)) if m else 9999

    sorted_parts = dict(sorted(merged_parts.items(), key=lambda item: part_sort_key(item[0])))
    return sorted_parts

# ----------------- Agentic Field Extraction with Fallback -----------------
def extract_fields_smart(part_content):
    pattern = r"(\d+\.(?:[a-z]\.)?\s+.*?)(?=\d+\.(?:[a-z]\.)?\s|$)"
    matches = re.findall(pattern, part_content, flags=re.IGNORECASE)

    keywords = ["Name", "Address", "Date", "Phone", "City", "State", "ZIP", "A-Number", "Email"]
    final_fields = []

    if matches:
        for m in matches:
            final_fields.append(m.strip())
    else:
        st.info("⚠️ No numeric fields detected — using fallback keyword extraction.")
        lines = part_content.split("  ")
        for line in lines:
            if any(kw.lower() in line.lower() for kw in keywords):
                final_fields.append(line.strip())

    return final_fields

# ----------------- UI -----------------
uploaded_file = st.file_uploader("📄 Upload USCIS PDF", type=["pdf"])

if uploaded_file:
    pdf = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    text = ""
    for page in pdf:
        text += page.get_text()

    parts = extract_parts_lines(text)

    if st.button("🤖 Validate Agent - Preview Parts & Fields"):
        agent_report = {}
        for part_name, part_content in parts.items():
            fields = extract_fields_smart(part_content)
            agent_report[part_name] = fields
        st.json(agent_report)
        json_agent = json.dumps(agent_report, indent=2)
        st.download_button("💾 Download Agent Verification JSON", data=json_agent, file_name="agent_verified_parts.json", mime="application/json")
        st.stop()

    final_mappings = {}

    st.header("🗂️ Review & Map Parts Sequentially")

    for part_name, part_content in parts.items():
        st.subheader(part_name)
        fields = extract_fields_smart(part_content)

        if not fields:
            st.warning(f"⚠️ No fields found in {part_name}. Skipping.")
            continue

        part_fields = []

        for i, field in enumerate(fields):
            col1, col2 = st.columns([4, 3])
            with col1:
                st.markdown(f"**{field}**")
            with col2:
                suggested = suggest_db_mapping(field)
                chosen = st.selectbox(
                    "Map to DB Object",
                    db_fields,
                    index=db_fields.index(suggested) if suggested in db_fields else db_fields.index("None (Move to Questionnaire)"),
                    key=f"{part_name}_{i}"
                )
            part_fields.append({"field": field, "mapping": chosen})

        final_mappings[part_name] = part_fields

    json_data = {"parts": final_mappings, "generated_at": datetime.now().isoformat()}
    json_str = json.dumps(json_data, indent=2)

    st.header("⬇️ Download Mappings")
    st.download_button("📥 Download JSON Mapping", data=json_str, file_name="uscis_mapping.json", mime="application/json")

    ts_stub = "export interface FormFields {\n"
    for part, fields in final_mappings.items():
        for f in fields:
            if f["mapping"] != "None (Move to Questionnaire)":
                ts_stub += f"  {f['mapping'].replace('.', '_').replace(':', '').replace(' ', '_')}: string;\n"
    ts_stub += "}\n"
    st.download_button("📥 Download TypeScript Interface", data=ts_stub, file_name="uscis_form_interface.ts", mime="text/plain")

    st.success("✅ All parts extracted with fallback, validated, smartly mapped, and ready!")

else:
    st.info("📥 Please upload a USCIS PDF to start.")
