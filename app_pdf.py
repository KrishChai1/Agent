import streamlit as st
import json
import pandas as pd
from typing import Dict, List, Tuple, Any, Optional
import re
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime
import base64
from io import BytesIO
import PyPDF2

class FormType(Enum):
    LCA = "LCA"
    I129 = "I-129"
    I129L = "I-129L"
    I129R = "I-129R"
    I129H = "I-129H"
    I129DC = "I-129DC"
    I140 = "I-140"
    I485 = "I-485"
    I485J = "I-485J"
    I485A = "I-485A"
    I539 = "I-539"
    I539A = "I-539A"
    I765 = "I-765"
    I907 = "I-907"
    I131 = "I-131"
    I864 = "I-864"
    I864A = "I-864A"
    I918 = "I-918"
    I829 = "I-829"
    G28 = "G-28"
    ETA9089 = "ETA-9089"
    H2B = "H-2B"
    UNKNOWN = "Unknown"

@dataclass
class FieldMapping:
    pdf_field_name: str
    database_path: str
    field_type: str
    category: str = "unmapped"
    condition: str = ""
    is_conditional: bool = False

class USCISFormMapper:
    def __init__(self):
        # Database structure patterns for intelligent mapping
        self.database_patterns = {
            "customer": {
                "patterns": ["company", "employer", "petitioner", "organization"],
                "fields": {
                    "customer_name": ["company_name", "employer_name", "organization_name", "petitioner_name"],
                    "customer_tax_id": ["ein", "tax_id", "fein", "employer_id"],
                    "customer_type_of_business": ["type_of_business", "business_type", "nature_of_business"],
                    "customer_year_established": ["year_established", "date_established", "established"],
                    "customer_total_employees": ["total_employees", "number_of_employees", "employee_count"],
                    "customer_gross_annual_income": ["gross_annual_income", "gross_income", "annual_revenue"],
                    "customer_net_annual_income": ["net_annual_income", "net_income"],
                    "customer_naics_code": ["naics_code", "naics"],
                    "address_street": ["street", "address", "street_address"],
                    "address_city": ["city"],
                    "address_state": ["state"],
                    "address_zip": ["zip", "zip_code", "postal_code"],
                    "address_country": ["country"],
                    "address_type": ["apt", "ste", "flr", "address_type"],
                    "address_number": ["number", "unit", "suite"],
                    "signatory_first_name": ["signatory_first", "signer_first", "authorized_first"],
                    "signatory_last_name": ["signatory_last", "signer_last", "authorized_last"],
                    "signatory_middle_name": ["signatory_middle", "signer_middle"],
                    "signatory_job_title": ["signatory_title", "job_title", "position"],
                    "signatory_work_phone": ["signatory_phone", "work_phone", "daytime_phone"],
                    "signatory_email_id": ["signatory_email", "email", "email_address"]
                }
            },
            "beneficiary": {
                "patterns": ["beneficiary", "employee", "worker", "alien"],
                "fields": {
                    "Beneficiary.beneficiaryFirstName": ["first_name", "given_name", "firstname"],
                    "Beneficiary.beneficiaryLastName": ["last_name", "family_name", "surname", "lastname"],
                    "Beneficiary.beneficiaryMiddleName": ["middle_name", "middlename"],
                    "Beneficiary.beneficiaryDateOfBirth": ["date_of_birth", "dob", "birth_date"],
                    "Beneficiary.beneficiaryCountryOfBirth": ["country_of_birth", "birth_country"],
                    "Beneficiary.beneficiaryCitizenOfCountry": ["country_of_citizenship", "citizenship", "nationality"],
                    "Beneficiary.beneficiaryGender": ["gender", "sex"],
                    "Beneficiary.beneficiarySsn": ["ssn", "social_security", "ss_number"],
                    "Beneficiary.alienNumber": ["alien_number", "a_number", "uscis_number"],
                    "I94Details.I94.i94Number": ["i94_number", "arrival_record"],
                    "I94Details.I94.i94ArrivalDate": ["arrival_date", "last_arrival", "entry_date"],
                    "PassportDetails.Passport.passportNumber": ["passport_number", "passport"],
                    "PassportDetails.Passport.passportExpiryDate": ["passport_expiry", "passport_expires"],
                    "PassportDetails.Passport.passportIssueCountry": ["passport_country", "passport_issued"],
                    "VisaDetails.Visa.visaStatus": ["visa_status", "current_status", "nonimmigrant_status"],
                    "VisaDetails.Visa.visaExpiryDate": ["visa_expiry", "status_expires"],
                    "WorkAddress.addressStreet": ["work_street", "work_address"],
                    "WorkAddress.addressCity": ["work_city"],
                    "WorkAddress.addressState": ["work_state"],
                    "WorkAddress.addressZip": ["work_zip"],
                    "HomeAddress.addressStreet": ["home_street", "home_address", "residence"],
                    "HomeAddress.addressCity": ["home_city"],
                    "HomeAddress.addressState": ["home_state"],
                    "HomeAddress.addressZip": ["home_zip"]
                }
            },
            "attorney": {
                "patterns": ["attorney", "lawyer", "representative", "preparer"],
                "fields": {
                    "attorneyInfo.firstName": ["attorney_first", "lawyer_first", "rep_first"],
                    "attorneyInfo.lastName": ["attorney_last", "lawyer_last", "rep_last"],
                    "attorneyInfo.stateBarNumber": ["bar_number", "state_bar", "license"],
                    "attorneyInfo.emailAddress": ["attorney_email", "lawyer_email"],
                    "attorneyInfo.workPhone": ["attorney_phone", "lawyer_phone"],
                    "attorneyInfo.faxNumber": ["fax", "fax_number"],
                    "address.addressStreet": ["attorney_street", "law_office_address"],
                    "address.addressCity": ["attorney_city"],
                    "address.addressState": ["attorney_state"],
                    "address.addressZip": ["attorney_zip"]
                }
            },
            "lca": {
                "patterns": ["lca", "labor", "wage", "position"],
                "fields": {
                    "Lca.positionJobTitle": ["job_title", "position_title", "occupation"],
                    "Lca.grossSalary": ["salary", "wage", "compensation"],
                    "Lca.startDate": ["start_date", "begin_date", "employment_start"],
                    "Lca.endDate": ["end_date", "employment_end"],
                    "Lca.lcaNumber": ["lca_number", "labor_certification"]
                }
            },
            "case": {
                "patterns": ["case", "petition", "application"],
                "fields": {
                    "caseType": ["case_type", "petition_type", "form_type"],
                    "caseSubType": ["case_subtype", "classification", "category"]
                }
            }
        }
        
        # Field type patterns
        self.field_type_patterns = {
            "CheckBox": ["checkbox", "check", "yes_no", "true_false", "option"],
            "Date": ["date", "dob", "expiry", "expires", "issued"],
            "SingleBox": ["ssn", "ein", "a_number", "alien_number", "tax_id"],
            "AddressTypeBox": ["apt", "ste", "flr", "unit"],
            "ConditionBox": ["if", "when", "conditional", "depends"],
            "MultipleBox": ["multiple", "list", "array"],
            "FullName": ["full_name", "complete_name"],
            "TextBox": ["text", "string", "name", "address", "phone", "email"]  # Default
        }

    def detect_form_type(self, content: str) -> FormType:
        """Detect form type from content"""
        content_lower = content.lower()
        
        form_patterns = {
            "LCA": ["labor condition application", "lca", "eca-"],
            "I-129": ["i-129", "petition for a nonimmigrant worker", "form i-129"],
            "I-129L": ["i-129l", "i129l", "l classification"],
            "I-129R": ["i-129r", "i129r", "religious worker"],
            "I-140": ["i-140", "i140", "immigrant petition"],
            "I-485": ["i-485", "i485", "adjustment of status"],
            "I-539": ["i-539", "i539", "extend/change status"],
            "I-765": ["i-765", "i765", "employment authorization"],
            "I-907": ["i-907", "i907", "premium processing"],
            "G-28": ["g-28", "g28", "notice of appearance"],
            "I-131": ["i-131", "i131", "travel document"],
            "I-864": ["i-864", "i864", "affidavit of support"],
            "I-918": ["i-918", "i918", "u nonimmigrant"],
            "I-829": ["i-829", "i829", "remove conditions"],
            "ETA-9089": ["eta-9089", "eta 9089", "eta9089", "perm"],
            "H-2B": ["h-2b", "h2b", "temporary worker"]
        }
        
        for form_type, patterns in form_patterns.items():
            for pattern in patterns:
                if pattern in content_lower:
                    return FormType(form_type.replace("_", "-"))
        
        return FormType.UNKNOWN

    def extract_pdf_fields(self, pdf_content: bytes) -> List[Dict[str, str]]:
        """Extract fields from PDF"""
        fields = []
        try:
            pdf_reader = PyPDF2.PdfReader(BytesIO(pdf_content))
            
            # Try to extract form fields
            if '/AcroForm' in pdf_reader.trailer['/Root']:
                form = pdf_reader.trailer['/Root']['/AcroForm']
                if '/Fields' in form:
                    for field_ref in form['/Fields']:
                        field = field_ref.get_object()
                        field_name = str(field.get('/T', 'Unknown'))
                        field_type = str(field.get('/FT', '/Tx'))
                        
                        # Map PDF field types
                        type_mapping = {
                            '/Tx': 'TextBox',
                            '/Btn': 'CheckBox',
                            '/Ch': 'DropDown',
                            '/Sig': 'Signature'
                        }
                        
                        fields.append({
                            'name': field_name,
                            'type': type_mapping.get(field_type, 'TextBox'),
                            'value': str(field.get('/V', ''))
                        })
            
            # If no form fields, extract from text
            if not fields:
                text_content = ""
                for page in pdf_reader.pages:
                    text_content += page.extract_text() + "\n"
                fields = self._extract_fields_from_text(text_content)
                
        except Exception as e:
            st.error(f"Error extracting PDF fields: {str(e)}")
        
        return fields

    def _extract_fields_from_text(self, text: str) -> List[Dict[str, str]]:
        """Extract potential fields from text content"""
        fields = []
        
        # Common patterns for form fields
        patterns = [
            r'(\d+[a-z]?)\.?\s+([A-Z][^:\n]+):?\s*(?:_+|\[?\s*\]?)',
            r'([A-Z][^:]+):\s*(?:_+|\[?\s*\]?)',
            r'Part\s+(\d+)\.?\s*Item\s+(\d+[a-z]?)\.?\s*([^:\n]+)',
            r'Section\s+([A-Z])\.?\s*Item\s+(\d+)\.?\s*([^:\n]+)'
        ]
        
        seen_fields = set()
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.MULTILINE)
            for match in matches:
                if len(match.groups()) >= 2:
                    field_label = match.group(len(match.groups())).strip()
                else:
                    field_label = match.group(1).strip()
                
                field_name = self._generate_field_name(field_label)
                
                if field_name not in seen_fields and len(field_label) > 3:
                    seen_fields.add(field_name)
                    fields.append({
                        'name': field_name,
                        'type': self._detect_field_type(field_label),
                        'label': field_label
                    })
        
        return fields[:200]  # Limit to 200 fields

    def _generate_field_name(self, label: str) -> str:
        """Generate a field name from label"""
        # Remove special characters and convert to camelCase
        name = re.sub(r'[^\w\s]', '', label)
        words = name.split()
        if words:
            # First word lowercase, rest title case
            name = words[0].lower()
            for word in words[1:]:
                name += word.title()
        return name

    def _detect_field_type(self, field_name: str) -> str:
        """Detect field type based on name patterns"""
        field_lower = field_name.lower()
        
        for field_type, patterns in self.field_type_patterns.items():
            for pattern in patterns:
                if pattern in field_lower:
                    return field_type
        
        return "TextBox"  # Default

    def map_fields_to_database(self, fields: List[Dict[str, str]], form_type: str) -> List[FieldMapping]:
        """Map extracted fields to database structure"""
        mappings = []
        
        for field in fields:
            field_name = field['name']
            field_label = field.get('label', field_name)
            field_type = field.get('type', 'TextBox')
            
            # Try to find matching database field
            mapping = self._find_database_mapping(field_name, field_label)
            
            if mapping:
                category, db_path = mapping
                mappings.append(FieldMapping(
                    pdf_field_name=field_name,
                    database_path=db_path,
                    field_type=field_type,
                    category=category,
                    is_conditional=self._is_conditional_field(field_name, field_label)
                ))
            else:
                # Unmapped field - add to questionnaire
                mappings.append(FieldMapping(
                    pdf_field_name=field_name,
                    database_path="",
                    field_type=field_type,
                    category="questionnaireData",
                    is_conditional=False
                ))
        
        return mappings

    def _find_database_mapping(self, field_name: str, field_label: str) -> Optional[Tuple[str, str]]:
        """Find matching database field"""
        field_lower = field_name.lower()
        label_lower = field_label.lower()
        
        # Check each category
        for category, config in self.database_patterns.items():
            # Check if field matches category patterns
            category_match = any(pattern in field_lower or pattern in label_lower 
                                for pattern in config["patterns"])
            
            if category_match:
                # Check specific field mappings
                for db_field, patterns in config["fields"].items():
                    for pattern in patterns:
                        if pattern in field_lower or pattern in label_lower:
                            # Determine category name for output
                            if category == "customer":
                                return "customerData", f"{category}.{db_field}"
                            elif category == "beneficiary":
                                return "beneficiaryData", f"beneficary.{db_field}"
                            elif category == "attorney":
                                return "attorneyData", f"{category}.{db_field}"
                            elif category == "lca":
                                return "lcaData", f"{category}.{db_field}"
                            elif category == "case":
                                return "caseData", f"{category}.{db_field}"
        
        return None

    def _is_conditional_field(self, field_name: str, field_label: str) -> bool:
        """Check if field is conditional"""
        conditional_patterns = ["if", "when", "depends", "based on", "conditional"]
        combined = (field_name + " " + field_label).lower()
        return any(pattern in combined for pattern in conditional_patterns)

    def generate_typescript_file(self, form_type: str, mappings: List[FieldMapping]) -> str:
        """Generate TypeScript file in the specific format"""
        # Group mappings by category
        categories = {
            "customerData": {},
            "beneficiaryData": {},
            "attorneyData": {},
            "caseData": {},
            "lcaData": {},
            "questionnaireData": {},
            "defaultData": {},
            "conditionalData": {}
        }
        
        # Sort mappings into categories
        for mapping in mappings:
            if mapping.is_conditional:
                # Add to conditionalData with special format
                categories["conditionalData"][mapping.pdf_field_name] = self._generate_conditional_entry(mapping)
            elif mapping.database_path:
                # Add to appropriate category
                category = mapping.category
                if category in categories:
                    categories[category][mapping.pdf_field_name] = f"{mapping.database_path}:{mapping.field_type}"
            else:
                # Add to questionnaire data
                categories["questionnaireData"][mapping.pdf_field_name] = f"{mapping.pdf_field_name}:ConditionBox"
        
        # Generate TypeScript content
        ts_content = f"""export const {form_type.replace('-', '')} = {{
    "formname": "{form_type.replace('-', '')}",
    "pdfName": "{form_type}",
"""
        
        # Add each category
        for category, fields in categories.items():
            ts_content += f'    "{category}": {{\n'
            
            if category == "conditionalData":
                # Special formatting for conditional data
                for field_name, condition_obj in fields.items():
                    ts_content += f'        "{field_name}": {json.dumps(condition_obj, indent=8)[:-1]}        }},\n'
            else:
                # Regular field entries
                for field_name, mapping in fields.items():
                    # Escape quotes in field names
                    escaped_name = field_name.replace('"', '\\"')
                    ts_content += f'        "{escaped_name}": "{mapping}",\n'
            
            # Remove trailing comma and close object
            if fields:
                ts_content = ts_content.rstrip(',\n') + '\n'
            ts_content += '    },\n'
        
        # Remove trailing comma and close main object
        ts_content = ts_content.rstrip(',\n') + '\n}'
        
        return ts_content

    def _generate_conditional_entry(self, mapping: FieldMapping) -> Dict[str, Any]:
        """Generate conditional data entry"""
        return {
            "condition": mapping.condition or "",
            "conditionTrue": mapping.pdf_field_name,
            "conditionFalse": "",
            "conditionType": mapping.field_type,
            "conditionParam": "object",
            "conditionData": ""
        }

    def generate_questionnaire_json(self, unmapped_fields: List[FieldMapping]) -> str:
        """Generate questionnaire JSON for unmapped fields"""
        controls = []
        
        for field in unmapped_fields:
            if not field.database_path:  # Only unmapped fields
                control = {
                    "name": field.pdf_field_name,
                    "label": field.pdf_field_name.replace('_', ' ').title(),
                    "type": self._map_field_type_to_control(field.field_type),
                    "validators": {"required": False},
                    "style": {"col": "6"}
                }
                
                if field.is_conditional:
                    control["className"] = "hide-dummy-class"
                
                controls.append(control)
        
        return json.dumps({"controls": controls}, indent=2)

    def _map_field_type_to_control(self, field_type: str) -> str:
        """Map field type to control type"""
        mapping = {
            "TextBox": "text",
            "CheckBox": "checkbox",
            "Date": "date",
            "SingleBox": "text",
            "DropDown": "dropdown",
            "MultipleBox": "text",
            "ConditionBox": "text",
            "FullName": "text",
            "AddressTypeBox": "radio"
        }
        return mapping.get(field_type, "text")

    def generate_pdf_mapper_entry(self, form_type: str, mappings: List[FieldMapping]) -> str:
        """Generate pdf-mappers.ts style entry"""
        mapper_content = f"public static {form_type.replace('-', '')}: any = [\n"
        
        for mapping in mappings:
            if mapping.database_path:
                mapper_content += f"""    {{
        Name: "{mapping.pdf_field_name}",
        Value: "{mapping.database_path}",
        Type: "{mapping.field_type}",
    }},\n"""
        
        mapper_content += "];"
        return mapper_content

def main():
    st.set_page_config(
        page_title="USCIS Form Mapper - TypeScript Generator",
        page_icon="🗂️",
        layout="wide"
    )
    
    st.title("🗂️ USCIS Form Mapper & TypeScript Generator")
    st.markdown("Upload USCIS forms to generate TypeScript mappings in your specific format")
    
    # Initialize mapper
    mapper = USCISFormMapper()
    
    # File upload
    uploaded_file = st.file_uploader(
        "Upload USCIS Form (PDF)",
        type=['pdf'],
        help="Upload a USCIS form PDF to analyze and generate mappings"
    )
    
    if uploaded_file is not None:
        # Read PDF content
        pdf_content = uploaded_file.read()
        
        # Extract form type
        try:
            pdf_reader = PyPDF2.PdfReader(BytesIO(pdf_content))
            text_content = ""
            for page in pdf_reader.pages:
                text_content += page.extract_text() + "\n"
            
            form_type = mapper.detect_form_type(text_content)
            
            if form_type == FormType.UNKNOWN:
                # Allow manual selection
                form_type_str = st.selectbox(
                    "Could not auto-detect form type. Please select:",
                    [ft.value for ft in FormType if ft != FormType.UNKNOWN]
                )
                form_type = FormType(form_type_str)
            else:
                st.success(f"✅ Detected Form Type: **{form_type.value}**")
            
            # Extract fields
            fields = mapper.extract_pdf_fields(pdf_content)
            
            if not fields:
                st.warning("No form fields could be extracted. Parsing text content...")
                fields = mapper._extract_fields_from_text(text_content)
            
            st.info(f"📊 Extracted **{len(fields)}** fields from the PDF")
            
            # Map fields to database
            mappings = mapper.map_fields_to_database(fields, form_type.value)
            
            # Calculate statistics
            mapped_count = len([m for m in mappings if m.database_path])
            unmapped_count = len([m for m in mappings if not m.database_path])
            
            # Display metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Fields", len(mappings))
            with col2:
                st.metric("Mapped Fields", mapped_count)
            with col3:
                st.metric("Unmapped Fields", unmapped_count)
            with col4:
                coverage = (mapped_count / len(mappings) * 100) if mappings else 0
                st.metric("Coverage %", f"{coverage:.1f}%")
            
            # Create tabs
            tab1, tab2, tab3, tab4, tab5 = st.tabs([
                "📄 TypeScript File",
                "📋 PDF Mapper Entry",
                "❓ Questionnaire JSON",
                "🔍 Field Analysis",
                "📊 Mapping Summary"
            ])
            
            with tab1:
                st.header(f"{form_type.value}.ts")
                
                # Generate TypeScript file
                ts_content = mapper.generate_typescript_file(form_type.value, mappings)
                st.code(ts_content, language="typescript")
                
                # Download button
                st.download_button(
                    label=f"📥 Download {form_type.value}.ts",
                    data=ts_content,
                    file_name=f"{form_type.value}.ts",
                    mime="text/typescript"
                )
            
            with tab2:
                st.header("pdf-mappers.ts Entry")
                
                # Generate pdf-mappers entry
                mapper_entry = mapper.generate_pdf_mapper_entry(form_type.value, mappings)
                st.code(mapper_entry, language="typescript")
                
                # Download button
                st.download_button(
                    label="📥 Download PDF Mapper Entry",
                    data=mapper_entry,
                    file_name=f"{form_type.value}_mapper.ts",
                    mime="text/typescript"
                )
            
            with tab3:
                st.header("Questionnaire JSON")
                
                unmapped_fields = [m for m in mappings if not m.database_path]
                if unmapped_fields:
                    questionnaire_json = mapper.generate_questionnaire_json(unmapped_fields)
                    st.code(questionnaire_json, language="json")
                    
                    # Download button
                    st.download_button(
                        label="📥 Download Questionnaire JSON",
                        data=questionnaire_json,
                        file_name=f"{form_type.value}_questionnaire.json",
                        mime="application/json"
                    )
                else:
                    st.success("🎉 All fields are mapped! No questionnaire needed.")
            
            with tab4:
                st.header("Field Analysis")
                
                # Create dataframe for analysis
                analysis_data = []
                for mapping in mappings:
                    analysis_data.append({
                        "PDF Field": mapping.pdf_field_name,
                        "Database Path": mapping.database_path or "UNMAPPED",
                        "Field Type": mapping.field_type,
                        "Category": mapping.category,
                        "Conditional": "Yes" if mapping.is_conditional else "No"
                    })
                
                df = pd.DataFrame(analysis_data)
                
                # Filter options
                col1, col2 = st.columns(2)
                with col1:
                    show_mapped = st.checkbox("Show Mapped", value=True)
                with col2:
                    show_unmapped = st.checkbox("Show Unmapped", value=True)
                
                # Apply filters
                filtered_df = df
                if not show_mapped:
                    filtered_df = filtered_df[filtered_df["Database Path"] == "UNMAPPED"]
                if not show_unmapped:
                    filtered_df = filtered_df[filtered_df["Database Path"] != "UNMAPPED"]
                
                st.dataframe(filtered_df, use_container_width=True, height=400)
            
            with tab5:
                st.header("Mapping Summary")
                
                # Category breakdown
                st.subheader("Fields by Category")
                category_counts = {}
                for mapping in mappings:
                    if mapping.database_path:
                        category = mapping.category
                        category_counts[category] = category_counts.get(category, 0) + 1
                
                if category_counts:
                    df_categories = pd.DataFrame(
                        list(category_counts.items()),
                        columns=["Category", "Count"]
                    )
                    st.bar_chart(df_categories.set_index("Category"))
                
                # Field type breakdown
                st.subheader("Fields by Type")
                type_counts = {}
                for mapping in mappings:
                    field_type = mapping.field_type
                    type_counts[field_type] = type_counts.get(field_type, 0) + 1
                
                if type_counts:
                    df_types = pd.DataFrame(
                        list(type_counts.items()),
                        columns=["Field Type", "Count"]
                    )
                    st.bar_chart(df_types.set_index("Field Type"))
                
                # Mapping suggestions
                st.subheader("📝 Mapping Improvement Suggestions")
                unmapped_fields = [m for m in mappings if not m.database_path]
                if unmapped_fields[:5]:  # Show first 5
                    st.write("Consider adding these fields to your database structure:")
                    for field in unmapped_fields[:5]:
                        st.write(f"• **{field.pdf_field_name}** ({field.field_type})")
                
        except Exception as e:
            st.error(f"Error processing PDF: {str(e)}")
            st.exception(e)
    
    else:
        st.info("👆 Please upload a USCIS form PDF to begin analysis")
        
        # Show example format
        with st.expander("📋 Example TypeScript Output Format"):
            example_ts = """export const I140 = {
    "formname": "I140",
    "pdfName": "I-140",
    "customerData": {
        "companyName": "customer.customer_name:TextBox",
        "ein_1": "customer.customer_tax_id:SingleBox",
        // ... more fields
    },
    "beneficiaryData": {
        "beneficiaryLastName": "beneficary.Beneficiary.beneficiaryLastName:TextBox",
        "beneficiaryFirstName": "beneficary.Beneficiary.beneficiaryFirstName:TextBox",
        // ... more fields
    },
    "conditionalData": {
        "passportNumber": {
            "condition": "",
            "conditionTrue": "passportNumber",
            "conditionFalse": "",
            "conditionType": "TextBox",
            "conditionParam": "object",
            "conditionData": "passport"
        }
    }
}"""
            st.code(example_ts, language="typescript")
        
        with st.expander("🔧 Supported Field Types"):
            field_types = [
                ("TextBox", "Standard text input field"),
                ("CheckBox", "Boolean checkbox field"),
                ("Date", "Date picker field"),
                ("SingleBox", "Single-digit input boxes (SSN, EIN, etc.)"),
                ("AddressTypeBox", "Address type selector (Apt/Ste/Flr)"),
                ("ConditionBox", "Conditional field based on other values"),
                ("MultipleBox", "Multiple value input field"),
                ("FullName", "Complete name field"),
                ("DropDown", "Dropdown selection field")
            ]
            
            for ft, desc in field_types:
                st.write(f"• **{ft}**: {desc}")

if __name__ == "__main__":
    main()
