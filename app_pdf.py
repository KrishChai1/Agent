import streamlit as st
import PyPDF2
import pdfplumber
import json
import re
from typing import Dict, List, Any, Tuple
import pandas as pd
from datetime import datetime
import io
import base64

# Initialize session state
if 'form_mappings' not in st.session_state:
    st.session_state.form_mappings = {}
if 'questionnaire_data' not in st.session_state:
    st.session_state.questionnaire_data = {}

# Known form mappings structure based on provided examples
KNOWN_FORM_STRUCTURES = {
    "I-90": {
        "beneficiaryData": ["beneficiaryLastName", "beneficiaryFirstName", "beneficiaryMiddleName", 
                           "beneficiaryDateOfBirth", "alienNumber", "beneficiaryGender", "beneficiarySsn"],
        "customerData": [],
        "attorneyData": ["lastName", "firstName", "lawFirmName", "workPhone", "emailAddress", 
                        "stateBarNumber"],
        "questionnaireData": [],
        "defaultData": [],
        "conditionalData": []
    },
    "I-129": {
        "customerData": ["customer_name", "signatory_first_name", "signatory_last_name", 
                        "address_street", "address_city", "address_state", "address_zip", 
                        "customer_tax_id"],
        "beneficiaryData": ["beneficiaryLastName", "beneficiaryFirstName", "beneficiaryMiddleName",
                           "beneficiaryDateOfBirth", "beneficiaryGender", "alienNumber", "beneficiarySsn"],
        "attorneyData": ["lastName", "firstName", "lawFirmName", "workPhone", "emailAddress"],
        "questionnaireData": [],
        "caseData": ["caseType", "caseSubType"],
        "defaultData": [],
        "conditionalData": []
    },
    "G-28": {
        "attorneyData": ["lastName", "firstName", "middleName", "lawFirmName", "addressStreet",
                        "addressCity", "addressState", "addressZip", "workPhone", "emailAddress",
                        "stateBarNumber", "licensingAuthority"],
        "clientData": ["familyName", "givenName", "middleName", "alienNumber", "uscisAccountNumber"],
        "defaultData": [],
        "conditionalData": []
    }
}

class USCISFormProcessor:
    def __init__(self):
        self.extracted_fields = {}
        self.form_type = None
        self.missing_fields = []
        
    def detect_form_type(self, text: str) -> str:
        """Detect the type of USCIS form from extracted text"""
        form_patterns = {
            "I-90": r"Form I-90.*Application to Replace",
            "I-129": r"Form I-129.*Petition for.*Nonimmigrant Worker",
            "I-140": r"Form I-140.*Immigrant Petition",
            "I-485": r"Form I-485.*Application to Register",
            "I-539": r"Form I-539.*Application to Extend",
            "I-765": r"Form I-765.*Application for Employment",
            "G-28": r"Form G-28.*Notice of Entry.*Appearance",
            "I-130": r"Form I-130.*Petition for Alien Relative",
            "I-131": r"Form I-131.*Application for Travel Document",
            "I-864": r"Form I-864.*Affidavit of Support"
        }
        
        for form_type, pattern in form_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                return form_type
                
        # Try to detect from common keywords
        upper_text = text.upper()
        if "H CLASSIFICATION" in upper_text:
            return "I-129H"
        elif "ADVANCE PAROLE" in upper_text:
            return "I-131"
            
        return "Unknown"
    
    def extract_form_fields(self, pdf_file) -> Dict[str, Any]:
        """Extract form fields from PDF using multiple methods"""
        fields = {}
        text_content = ""
        
        # Method 1: Try to extract form fields using PyPDF2
        try:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            # Extract text content
            for page in pdf_reader.pages:
                text_content += page.extract_text()
            
            # Extract form fields if available
            if '/AcroForm' in pdf_reader.trailer['/Root']:
                form_fields = pdf_reader.get_fields()
                if form_fields:
                    for field_name, field_data in form_fields.items():
                        field_value = field_data.get('/V', '')
                        if field_value:
                            fields[field_name] = field_value
        except Exception as e:
            st.warning(f"PyPDF2 extraction warning: {str(e)}")
        
        # Method 2: Use pdfplumber for better text extraction
        try:
            pdf_file.seek(0)  # Reset file pointer
            with pdfplumber.open(pdf_file) as pdf:
                for page in pdf.pages:
                    # Extract tables if present
                    tables = page.extract_tables()
                    for table in tables:
                        for row in table:
                            if row and len(row) >= 2:
                                # Simple heuristic: first column might be field name
                                if row[0] and row[1]:
                                    fields[self.clean_field_name(str(row[0]))] = str(row[1])
                    
                    # Extract text for form type detection
                    page_text = page.extract_text()
                    if page_text:
                        text_content += page_text
        except Exception as e:
            st.warning(f"pdfplumber extraction warning: {str(e)}")
        
        # Detect form type
        self.form_type = self.detect_form_type(text_content)
        
        # Extract common fields using regex patterns
        common_patterns = {
            "lastName": r"(?:Family Name|Last Name)[:\s]*([A-Za-z\s]+)",
            "firstName": r"(?:Given Name|First Name)[:\s]*([A-Za-z\s]+)",
            "middleName": r"(?:Middle Name)[:\s]*([A-Za-z\s]+)",
            "dateOfBirth": r"(?:Date of Birth)[:\s]*(\d{1,2}/\d{1,2}/\d{4})",
            "alienNumber": r"(?:A-Number|Alien Number)[:\s]*([A]\d{8,9})",
            "ssn": r"(?:Social Security Number|SSN)[:\s]*(\d{3}-\d{2}-\d{4})",
            "phoneNumber": r"(?:Phone Number|Telephone)[:\s]*(\d{3}-\d{3}-\d{4})",
            "email": r"(?:Email Address)[:\s]*([\w\.-]+@[\w\.-]+)",
            "addressStreet": r"(?:Street Address|Street Number and Name)[:\s]*([^\n]+)",
            "city": r"(?:City)[:\s]*([A-Za-z\s]+)",
            "state": r"(?:State)[:\s]*([A-Z]{2})",
            "zipCode": r"(?:ZIP Code|Postal Code)[:\s]*(\d{5}(?:-\d{4})?)"
        }
        
        for field_name, pattern in common_patterns.items():
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                fields[field_name] = match.group(1).strip()
        
        self.extracted_fields = fields
        return {
            "form_type": self.form_type,
            "fields": fields,
            "text_content": text_content[:1000]  # First 1000 chars for preview
        }
    
    def clean_field_name(self, field_name: str) -> str:
        """Clean and standardize field names"""
        # Remove special characters and normalize
        cleaned = re.sub(r'[^\w\s]', '', field_name)
        cleaned = re.sub(r'\s+', '_', cleaned.strip())
        return cleaned.lower()
    
    def map_to_database_structure(self, extracted_fields: Dict[str, Any]) -> Dict[str, Any]:
        """Map extracted fields to database structure"""
        form_structure = KNOWN_FORM_STRUCTURES.get(self.form_type, {})
        mapped_data = {
            "formname": self.form_type.lower().replace("-", ""),
            "pdfName": self.form_type,
            "customerData": {},
            "beneficiaryData": {},
            "attorneyData": {},
            "questionnaireData": {},
            "caseData": {},
            "defaultData": {},
            "conditionalData": {}
        }
        
        # Map fields based on common patterns
        field_mapping_rules = {
            "customerData": ["customer", "petitioner", "employer", "company"],
            "beneficiaryData": ["beneficiary", "applicant", "alien", "worker"],
            "attorneyData": ["attorney", "representative", "lawyer"],
            "caseData": ["case", "petition", "application"]
        }
        
        for field_name, field_value in extracted_fields.items():
            mapped = False
            lower_field = field_name.lower()
            
            # Try to map based on field name patterns
            for data_type, patterns in field_mapping_rules.items():
                for pattern in patterns:
                    if pattern in lower_field:
                        mapped_data[data_type][field_name] = field_value
                        mapped = True
                        break
                if mapped:
                    break
            
            # If not mapped, add to questionnaire data
            if not mapped:
                mapped_data["questionnaireData"][field_name] = field_value
        
        return mapped_data
    
    def identify_missing_fields(self, mapped_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify fields that need to be collected via questionnaire"""
        missing_fields = []
        
        # Get expected structure for this form type
        expected_structure = KNOWN_FORM_STRUCTURES.get(self.form_type, {})
        
        # Check each data category
        for category, expected_fields in expected_structure.items():
            if category in mapped_data:
                extracted_field_names = set(mapped_data[category].keys())
                
                for expected_field in expected_fields:
                    if expected_field not in extracted_field_names:
                        missing_fields.append({
                            "category": category,
                            "fieldName": expected_field,
                            "fieldType": self.determine_field_type(expected_field),
                            "required": True,
                            "label": self.generate_field_label(expected_field)
                        })
        
        self.missing_fields = missing_fields
        return missing_fields
    
    def determine_field_type(self, field_name: str) -> str:
        """Determine the appropriate field type based on field name"""
        lower_field = field_name.lower()
        
        if any(date_word in lower_field for date_word in ["date", "dob", "birth"]):
            return "date"
        elif any(num_word in lower_field for num_word in ["number", "phone", "ssn", "zip", "ein"]):
            return "text"  # Will add pattern validation
        elif any(email_word in lower_field for email_word in ["email", "mail"]):
            return "email"
        elif any(check_word in lower_field for check_word in ["is", "has", "yes", "no"]):
            return "checkbox"
        elif any(select_word in lower_field for select_word in ["type", "status", "state"]):
            return "select"
        else:
            return "text"
    
    def generate_field_label(self, field_name: str) -> str:
        """Generate human-readable label from field name"""
        # Convert camelCase to Title Case
        label = re.sub(r'([A-Z])', r' \1', field_name)
        label = label.strip().title()
        
        # Replace common abbreviations
        replacements = {
            "Ssn": "SSN",
            "Ein": "EIN",
            "Dob": "Date of Birth",
            "Id": "ID"
        }
        
        for old, new in replacements.items():
            label = label.replace(old, new)
            
        return label
    
    def generate_questionnaire_json(self, missing_fields: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate questionnaire JSON for missing fields"""
        questionnaire = {
            "formType": self.form_type,
            "version": "1.0",
            "createdAt": datetime.now().isoformat(),
            "sections": {}
        }
        
        # Group fields by category
        for field in missing_fields:
            category = field["category"]
            if category not in questionnaire["sections"]:
                questionnaire["sections"][category] = {
                    "title": category.replace("Data", " Information").title(),
                    "fields": []
                }
            
            field_def = {
                "id": field["fieldName"],
                "label": field["label"],
                "type": field["fieldType"],
                "required": field["required"],
                "validation": self.get_field_validation(field["fieldName"], field["fieldType"])
            }
            
            # Add options for select fields
            if field["fieldType"] == "select":
                field_def["options"] = self.get_field_options(field["fieldName"])
            
            questionnaire["sections"][category]["fields"].append(field_def)
        
        return questionnaire
    
    def get_field_validation(self, field_name: str, field_type: str) -> Dict[str, Any]:
        """Get validation rules for specific fields"""
        validations = {
            "ssn": {"pattern": r"^\d{3}-\d{2}-\d{4}$", "message": "Format: XXX-XX-XXXX"},
            "phone": {"pattern": r"^\d{3}-\d{3}-\d{4}$", "message": "Format: XXX-XXX-XXXX"},
            "zip": {"pattern": r"^\d{5}(-\d{4})?$", "message": "Format: XXXXX or XXXXX-XXXX"},
            "alienNumber": {"pattern": r"^A\d{8,9}$", "message": "Format: A followed by 8-9 digits"},
            "email": {"pattern": r"^[\w\.-]+@[\w\.-]+\.\w+$", "message": "Valid email required"}
        }
        
        for key, validation in validations.items():
            if key in field_name.lower():
                return validation
                
        return {}
    
    def get_field_options(self, field_name: str) -> List[Dict[str, str]]:
        """Get options for select fields"""
        options_map = {
            "state": [{"value": state, "label": state} for state in 
                     ["AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", 
                      "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
                      "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
                      "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
                      "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"]],
            "gender": [
                {"value": "M", "label": "Male"},
                {"value": "F", "label": "Female"},
                {"value": "O", "label": "Other"}
            ],
            "maritalStatus": [
                {"value": "single", "label": "Single"},
                {"value": "married", "label": "Married"},
                {"value": "divorced", "label": "Divorced"},
                {"value": "widowed", "label": "Widowed"}
            ]
        }
        
        for key, options in options_map.items():
            if key.lower() in field_name.lower():
                return options
                
        return []
    
    def generate_typescript_file(self, mapped_data: Dict[str, Any], 
                               questionnaire: Dict[str, Any]) -> str:
        """Generate TypeScript file for the form"""
        ts_content = f"""export const {self.form_type.replace('-', '')} = {{
    "formname": "{mapped_data['formname']}",
    "pdfName": "{mapped_data['pdfName']}",
"""
        
        # Add data sections
        for section in ["customerData", "beneficiaryData", "attorneyData", 
                       "questionnaireData", "caseData", "defaultData", "conditionalData"]:
            if section in mapped_data and mapped_data[section]:
                ts_content += f'    "{section}": {{\n'
                for field_name, field_value in mapped_data[section].items():
                    # Generate mapping string
                    mapping = self.generate_field_mapping(section, field_name)
                    ts_content += f'        "{field_name}": "{mapping}",\n'
                ts_content = ts_content.rstrip(',\n') + '\n'
                ts_content += '    },\n'
            else:
                ts_content += f'    "{section}": {{}},\n'
        
        ts_content = ts_content.rstrip(',\n') + '\n}'
        
        # Add questionnaire fields as comments
        if questionnaire and questionnaire.get("sections"):
            ts_content += "\n\n// Questionnaire fields for missing data:\n"
            for section, section_data in questionnaire["sections"].items():
                ts_content += f"// {section}:\n"
                for field in section_data["fields"]:
                    ts_content += f"//   - {field['id']}: {field['type']} ({field['label']})\n"
        
        return ts_content
    
    def generate_field_mapping(self, section: str, field_name: str) -> str:
        """Generate field mapping string based on section and field name"""
        # Common mapping patterns
        if section == "customerData":
            return f"customer.{field_name}:TextBox"
        elif section == "beneficiaryData":
            return f"beneficiary.Beneficiary.{field_name}:TextBox"
        elif section == "attorneyData":
            return f"attorney.attorneyInfo.{field_name}:TextBox"
        elif section == "caseData":
            return f"case.{field_name}:TextBox"
        else:
            return f"{field_name}:TextBox"

# Streamlit UI
def main():
    st.set_page_config(page_title="USCIS Form Processor", layout="wide")
    
    st.title("USCIS Form Processor")
    st.markdown("Upload USCIS forms to extract data, map to database, and generate questionnaires")
    
    # File upload
    uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")
    
    if uploaded_file is not None:
        processor = USCISFormProcessor()
        
        # Create columns for layout
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("Form Analysis")
            
            # Extract form fields
            with st.spinner("Extracting form fields..."):
                extraction_result = processor.extract_form_fields(uploaded_file)
            
            st.success(f"Form Type Detected: **{extraction_result['form_type']}**")
            
            # Display extracted fields
            st.write("### Extracted Fields")
            if extraction_result['fields']:
                df_fields = pd.DataFrame(
                    [(k, v) for k, v in extraction_result['fields'].items()],
                    columns=['Field Name', 'Value']
                )
                st.dataframe(df_fields, use_container_width=True)
            else:
                st.warning("No form fields could be extracted. The PDF might not contain fillable fields.")
            
            # Map to database structure
            st.write("### Database Mapping")
            mapped_data = processor.map_to_database_structure(extraction_result['fields'])
            
            # Display mapping summary
            mapping_summary = {}
            for category, data in mapped_data.items():
                if isinstance(data, dict) and data:
                    mapping_summary[category] = len(data)
            
            if mapping_summary:
                df_summary = pd.DataFrame(
                    [(k, v) for k, v in mapping_summary.items()],
                    columns=['Category', 'Field Count']
                )
                st.dataframe(df_summary, use_container_width=True)
        
        with col2:
            st.subheader("Missing Fields & Questionnaire")
            
            # Identify missing fields
            missing_fields = processor.identify_missing_fields(mapped_data)
            
            if missing_fields:
                st.write(f"### {len(missing_fields)} Missing Fields Identified")
                
                # Display missing fields by category
                missing_by_category = {}
                for field in missing_fields:
                    category = field['category']
                    if category not in missing_by_category:
                        missing_by_category[category] = []
                    missing_by_category[category].append(field)
                
                for category, fields in missing_by_category.items():
                    with st.expander(f"{category} ({len(fields)} fields)"):
                        for field in fields:
                            st.write(f"- **{field['label']}** ({field['fieldType']})")
                
                # Generate questionnaire
                questionnaire = processor.generate_questionnaire_json(missing_fields)
                
                st.write("### Generated Questionnaire")
                st.json(questionnaire)
                
                # Download questionnaire JSON
                json_str = json.dumps(questionnaire, indent=2)
                b64 = base64.b64encode(json_str.encode()).decode()
                href = f'<a href="data:application/json;base64,{b64}" download="{processor.form_type}_questionnaire.json">Download Questionnaire JSON</a>'
                st.markdown(href, unsafe_allow_html=True)
            else:
                st.success("All expected fields were found in the form!")
        
        # Generate TypeScript file
        st.subheader("TypeScript File Generation")
        ts_content = processor.generate_typescript_file(mapped_data, 
                                                       questionnaire if missing_fields else {})
        
        # Display TypeScript content
        with st.expander("View Generated TypeScript File"):
            st.code(ts_content, language="typescript")
        
        # Download TypeScript file
        b64_ts = base64.b64encode(ts_content.encode()).decode()
        href_ts = f'<a href="data:text/typescript;base64,{b64_ts}" download="{processor.form_type.replace("-", "")}.ts">Download TypeScript File</a>'
        st.markdown(href_ts, unsafe_allow_html=True)
        
        # Save to session state
        st.session_state.form_mappings[processor.form_type] = mapped_data
        if missing_fields:
            st.session_state.questionnaire_data[processor.form_type] = questionnaire
        
        # Display session summary
        st.subheader("Processing Summary")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Form Type", processor.form_type)
        with col2:
            st.metric("Fields Extracted", len(extraction_result['fields']))
        with col3:
            st.metric("Missing Fields", len(missing_fields))
    
    # Show processed forms history
    if st.session_state.form_mappings:
        st.subheader("Processed Forms History")
        for form_type, mapping in st.session_state.form_mappings.items():
            st.write(f"- {form_type}")

if __name__ == "__main__":
    main()
