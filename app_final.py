import streamlit as st
import json
import re
import fitz  # PyMuPDF
from datetime import datetime

st.set_page_config(page_title="🗂️ USCIS Smart Mapper", layout="wide")
st.title("🗂️ USCIS Form AI Mapper — Correct Parts & Subfields")

# -------------------------------------------------------------------
# Build flattened DB attributes list from uploaded objects
# -------------------------------------------------------------------
def build_db_attributes():
    attributes = []

    # Attorney
    attributes += [
        "Attorney: attorneyInfo.firstName",
        "Attorney: attorneyInfo.lastName",
        "Attorney: attorneyInfo.workPhone",
        "Attorney: attorneyInfo.emailAddress",
        "Attorney: attorneyInfo.stateBarNumber",
        "Attorney: attorneyInfo.stateOfHighestCourt",
        "Attorney: attorneyInfo.licensingAuthority",
        "Attorney: address.addressStreet",
        "Attorney: address.addressCity",
        "Attorney: address.addressState",
        "Attorney: address.addressZip",
        "Attorney: address.addressCountry",
    ]

    # Beneficiary
    attributes += [
        "Beneficiary: Beneficiary.beneficiaryFirstName",
        "Beneficiary: Beneficiary.beneficiaryLastName",
        "Beneficiary: Beneficiary.beneficiaryMiddleName",
        "Beneficiary: Beneficiary.beneficiaryGender",
        "Beneficiary: Beneficiary.beneficiaryDateOfBirth",
        "Beneficiary: Beneficiary.beneficiaryCitizenOfCountry",
        "Beneficiary: Beneficiary.beneficiarySsn",
        "Beneficiary: Beneficiary.beneficiaryPrimaryEmailAddress",
        "Beneficiary: Beneficiary.beneficiaryCellNumber",
        "Beneficiary: HomeAddress.addressStreet",
        "Beneficiary: HomeAddress.addressCity",
        "Beneficiary: HomeAddress.addressState",
        "Beneficiary: HomeAddress.addressZip",
    ]

    # Case
    attributes += [
        "Case: caseId",
        "Case: caseType",
        "Case: caseStatus",
        "Case: caseSubType",
        "Case: uscisReceiptNumber",
        "Case: caseNumber",
        "Case: serviceCenter",
        "Case: h1BPetitionType",
    ]

    # Customer
    attributes += [
        "Customer: customer_name",
        "Customer: customer_tax_id",
        "Customer: customer_naics_code",
        "Customer: customer_website_url",
        "Customer: customer_gross_annual_income",
        "Customer: owner_first_name",
        "Customer: owner_last_name",
        "Customer: signatory_first_name",
        "Customer: signatory_last_name",
        "Customer: customer_address_id",
    ]

    # Lawfirm
    attributes += [
        "Lawfirm: lawFirmDetails.lawFirmName",
        "Lawfirm: lawFirmDetails.companyPhone",
        "Lawfirm: lawFirmDetails.lawFirmFein",
        "Lawfirm: address.addressStreet",
        "Lawfirm: address.addressCity",
        "Lawfirm: address.addressState",
        "Lawfirm: address.addressZip",
    ]

    # LCA
    attributes += [
        "LCA: Lca.positionJobTitle",
        "LCA: Lca.grossSalary",
        "LCA: Lca.startDate",
        "LCA: Lca.endDate",
        "LCA: Lca.socOnetOesCode",
        "LCA: Lca.jobLocation",
        "LCA: Addresses.addressStreet",
        "LCA: Addresses.addressCity",
        "LCA: Addresses.addressState",
        "LCA: Addresses.addressZip",
    ]

    # Petitioner
    attributes += [
        "Petitioner: Beneficiary.beneficiaryFirstName",
        "Petitioner: Beneficiary.beneficiaryLastName",
        "Petitioner: Beneficiary.beneficiaryDateOfBirth",
        "Petitioner: Beneficiary.beneficiaryCitizenOfCountry",
        "Petitioner: Beneficiary.beneficiarySsn",
        "Petitioner: Beneficiary.beneficiaryPrimaryEmailAddress",
        "Petitioner: Beneficiary.beneficiaryCellNumber",
        "Petitioner: Beneficiary.beneficiaryWorkNumber",
        "Petitioner: Beneficiary.beneficiaryHomeAddressId",
        "Petitioner: Beneficiary.beneficiaryWorkAddressId",
    ]

    attributes += ["None (Move to Questionnaire)"]
    return attributes

db_fields = build_db_attributes()

# -------------------------------------------------------------------
# Extract parts starting from Part 1
# -------------------------------------------------------------------
def extract_parts(text):
    # Merge "continued" lines into same part
    text = re.sub(r"(Part\s+\d+\..*?)\s*\(continued\)", r"\1", text, flags=re.IGNORECASE)

    part_pattern = r"(Part\s+\d+\.?.*?)(?=Part\s+\d+\.|$)"
    matches = re.findall(part_pattern, text, re.DOTALL | re.IGNORECASE)

    parts = {}
    for match in matches:
        lines = match.strip().split("\n", 1)
        part_title = lines[0].strip()
        part_content = lines[1].strip() if len(lines) > 1 else ""
        parts[part_title] = part_content
    return parts

# -------------------------------------------------------------------
# Extract subfields (handles 1., 1.a, 1.b etc.)
# -------------------------------------------------------------------
def extract_fields(part_content):
    field_pattern = r"(\d+\.[a-zA-Z]?\s+[^\n]+)"
    fields = re.findall(field_pattern, part_content)
    return fields

uploaded_file = st.file_uploader("📄 Upload USCIS PDF", type=["pdf"])

if uploaded_file:
    pdf = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    text = ""
    for page in pdf:
        text += page.get_text()

    parts = extract_parts(text)

    final_mappings = {}
    questionnaire_fields = []

    st.header("🗂️ Review & Edit All Parts (Full, Sequential View)")

    for part_name, part_content in parts.items():
        st.subheader(part_name)
        fields = extract_fields(part_content)

        if not fields:
            st.warning(f"No numbered fields found in {part_name}.")
            continue

        for i, field_label in enumerate(fields):
            col1, col2, col3 = st.columns([4, 4, 2])
            with col1:
                st.text_input("Field Label", field_label, key=f"label_{part_name}_{i}", disabled=True)
            with col2:
                selected_db = st.selectbox(
                    "DB Field",
                    db_fields,
                    index=db_fields.index("None (Move to Questionnaire)"),
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

    # Generate outputs
    ts_content = "// Auto-generated TypeScript mappings\nexport const formMappings = " + json.dumps(final_mappings, indent=2) + ";"
    ts_filename = f"uscis_mappings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.ts"

    questionnaire_json = {
        "questionnaire_fields": questionnaire_fields,
        "generated_at": datetime.now().isoformat()
    }
    json_filename = f"uscis_questionnaire_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    st.header("⬇️ Download Files")
    st.download_button("💾 Download TypeScript Mapping", data=ts_content, file_name=ts_filename, mime="text/plain")
    st.download_button("💾 Download Questionnaire JSON", data=json.dumps(questionnaire_json, indent=2), file_name=json_filename, mime="application/json")

    st.success("✅ All parts displayed fully and sequentially. Download your files above!")

else:
    st.info("📥 Please upload a USCIS PDF to start.")
