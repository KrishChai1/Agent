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
    G28 = "G-28"
    I129DC = "I-129DC"
    I129H = "I-129H"
    I907 = "I-907"
    I539 = "I-539"
    I539A = "I-539A"
    I765 = "I-765"
    I140 = "I-140"
    I129L = "I-129L"
    I129R = "I-129R"
    I918 = "I-918"
    I131 = "I-131"
    I485 = "I-485"
    I485J = "I-485J"
    I485A = "I-485A"
    I864 = "I-864"
    I829 = "I-829"
    UNKNOWN = "Unknown"

@dataclass
class FormField:
    pdf_field_name: str
    field_type: str
    label: str = ""
    database_mapping: str = ""
    is_mapped: bool = False
    default_value: str = ""
    value: str = ""
    section: str = ""
    is_conditional: bool = False
    condition: str = ""

class IntelligentFormMapper:
    def __init__(self):
        # Define database field patterns for intelligent mapping
        self.database_patterns = {
            # Customer fields
            "customer_name": ["customer.customer_name", "TextBox"],
            "company_name": ["customer.customer_name", "TextBox"],
            "employer_name": ["customer.customer_name", "TextBox"],
            "petitioner_name": ["customer.customer_name", "TextBox"],
            "organization_name": ["customer.customer_name", "TextBox"],
            
            "tax_id": ["customer.customer_tax_id", "SingleBox"],
            "ein": ["customer.customer_tax_id", "SingleBox"],
            "fein": ["customer.customer_tax_id", "SingleBox"],
            
            "customer_street": ["customer.address_street", "TextBox"],
            "customer_address": ["customer.address_street", "TextBox"],
            "employer_street": ["customer.address_street", "TextBox"],
            "company_street": ["customer.address_street", "TextBox"],
            
            "customer_city": ["customer.address_city", "TextBox"],
            "customer_state": ["customer.address_state", "TextBox"],
            "customer_zip": ["customer.address_zip", "TextBox"],
            "customer_country": ["customer.address_country", "TextBox"],
            
            "signatory_first": ["customer.signatory_first_name", "TextBox"],
            "signatory_last": ["customer.signatory_last_name", "TextBox"],
            "signatory_title": ["customer.signatory_job_title", "TextBox"],
            "signatory_phone": ["customer.signatory_work_phone", "TextBox"],
            "signatory_email": ["customer.signatory_email_id", "TextBox"],
            
            # Beneficiary fields
            "beneficiary_last": ["beneficary.Beneficiary.beneficiaryLastName", "TextBox"],
            "beneficiary_first": ["beneficary.Beneficiary.beneficiaryFirstName", "TextBox"],
            "beneficiary_middle": ["beneficary.Beneficiary.beneficiaryMiddleName", "TextBox"],
            "alien_number": ["beneficary.Beneficiary.alienNumber", "SingleBox"],
            "a_number": ["beneficary.Beneficiary.alienNumber", "SingleBox"],
            "ssn": ["beneficary.Beneficiary.beneficiarySsn", "SingleBox"],
            "social_security": ["beneficary.Beneficiary.beneficiarySsn", "SingleBox"],
            
            "date_birth": ["beneficary.Beneficiary.beneficiaryDateOfBirth", "TextBox"],
            "birth_date": ["beneficary.Beneficiary.beneficiaryDateOfBirth", "TextBox"],
            "dob": ["beneficary.Beneficiary.beneficiaryDateOfBirth", "TextBox"],
            
            "country_birth": ["beneficary.Beneficiary.beneficiaryCountryOfBirth", "TextBox"],
            "birth_country": ["beneficary.Beneficiary.beneficiaryCountryOfBirth", "TextBox"],
            "citizenship": ["beneficary.Beneficiary.beneficiaryCitizenOfCountry", "TextBox"],
            "nationality": ["beneficary.Beneficiary.beneficiaryCitizenOfCountry", "TextBox"],
            
            "work_street": ["beneficary.WorkAddress.addressStreet", "TextBox"],
            "work_city": ["beneficary.WorkAddress.addressCity", "TextBox"],
            "work_state": ["beneficary.WorkAddress.addressState", "TextBox"],
            "work_zip": ["beneficary.WorkAddress.addressZip", "TextBox"],
            
            "home_street": ["beneficary.HomeAddress.addressStreet", "TextBox"],
            "home_city": ["beneficary.HomeAddress.addressCity", "TextBox"],
            "home_state": ["beneficary.HomeAddress.addressState", "TextBox"],
            "home_zip": ["beneficary.HomeAddress.addressZip", "TextBox"],
            
            "foreign_street": ["beneficary.ForeignAddress.addressStreet", "TextBox"],
            "foreign_city": ["beneficary.ForeignAddress.addressCity", "TextBox"],
            "foreign_state": ["beneficary.ForeignAddress.addressState", "TextBox"],
            "foreign_zip": ["beneficary.ForeignAddress.addressZip", "TextBox"],
            "foreign_country": ["beneficary.ForeignAddress.addressCountry", "TextBox"],
            
            # Attorney fields
            "attorney_last": ["attorney.attorneyInfo.lastName", "TextBox"],
            "attorney_first": ["attorney.attorneyInfo.firstName", "TextBox"],
            "attorney_bar": ["attorney.attorneyInfo.stateBarNumber", "TextBox"],
            "state_bar": ["attorney.attorneyInfo.stateBarNumber", "TextBox"],
            "attorney_firm": ["attorneyLawfirmDetails.lawfirmDetails.lawFirmName", "TextBox"],
            "law_firm": ["attorneyLawfirmDetails.lawfirmDetails.lawFirmName", "TextBox"],
            "attorney_phone": ["attorney.attorneyInfo.workPhone", "TextBox"],
            "attorney_email": ["attorney.attorneyInfo.emailAddress", "TextBox"],
            
            # I-94 fields
            "i94_number": ["beneficary.I94Details.I94.i94Number", "TextBox"],
            "i94_arrival": ["beneficary.I94Details.I94.i94ArrivalDate", "TextBox"],
            "arrival_date": ["beneficary.I94Details.I94.i94ArrivalDate", "TextBox"],
            
            # Passport fields
            "passport_number": ["beneficary.PassportDetails.Passport.passportNumber", "TextBox"],
            "passport_country": ["beneficary.PassportDetails.Passport.passportIssueCountry", "TextBox"],
            "passport_expiry": ["beneficary.PassportDetails.Passport.passportExpiryDate", "TextBox"],
            
            # Visa fields
            "visa_status": ["beneficary.VisaDetails.Visa.visaStatus", "TextBox"],
            "visa_expiry": ["beneficary.VisaDetails.Visa.visaExpiryDate", "TextBox"],
            
            # LCA fields
            "lca_number": ["lca.Lca.lcaNumber", "TextBox"],
            "job_title": ["lca.Lca.positionJobTitle", "TextBox"],
            "start_date": ["lca.Lca.startDate", "TextBox"],
            "end_date": ["lca.Lca.endDate", "TextBox"],
            "wage_rate": ["lca.Lca.grossSalary", "TextBox"],
            "prevailing_wage": ["lca.Lca.prevailingWateRate", "TextBox"],
            
            # Case fields
            "case_type": ["case.caseType", "TextBox"],
            "case_subtype": ["case.caseSubType", "CheckBox"],
            "receipt_number": ["case.receiptNumber", "TextBox"],
        }
        
        # Field type patterns
        self.field_type_patterns = {
            "checkbox": ["CheckBox", "checkbox", "chk", "check"],
            "radio": ["RadioButton", "radio", "option"],
            "date": ["Date", "date", "dob", "expiry"],
            "dropdown": ["DropDown", "dropdown", "select", "combo"],
            "single": ["SingleBox", "ein", "ssn", "tax", "alien"],
            "condition": ["ConditionBox", "condition", "if"],
            "address": ["AddressTypeBox", "apt", "ste", "flr"],
            "fullname": ["FullName", "care_of", "careof"],
            "multiple": ["MultipleBox", "multiple", "list"]
        }
    
    def detect_form_type(self, content: str, filename: str = "") -> FormType:
        """Detect the type of form based on content and filename"""
        content_lower = content.lower()
        filename_lower = filename.lower()
        
        # Check filename first
        for form_type in FormType:
            if form_type.value != "Unknown" and form_type.value.lower().replace("-", "") in filename_lower.replace("-", ""):
                return form_type
        
        # Then check content
        form_patterns = {
            "LCA": ["labor condition application", "lca", "prevailing wage"],
            "I-129": ["i-129", "petition for a nonimmigrant worker", "h-1b"],
            "G-28": ["g-28", "g28", "notice of entry of appearance"],
            "I-140": ["i-140", "i140", "immigrant petition for alien worker"],
            "I-539": ["i-539", "i539", "extend/change nonimmigrant status"],
            "I-765": ["i-765", "i765", "employment authorization"],
            "I-485": ["i-485", "i485", "adjust status", "green card"],
            "I-907": ["i-907", "i907", "premium processing"],
            "I-131": ["i-131", "i131", "travel document"],
            "I-129R": ["i-129r", "i129r", "religious worker"],
            "I-829": ["i-829", "i829", "remove conditions"],
        }
        
        for form_type, patterns in form_patterns.items():
            for pattern in patterns:
                if pattern in content_lower:
                    try:
                        return FormType(form_type.upper().replace("_", "-"))
                    except:
                        pass
        
        return FormType.UNKNOWN
    
    def extract_pdf_fields(self, pdf_content: bytes, filename: str = "") -> Tuple[FormType, List[FormField]]:
        """Extract fields from PDF and detect form type"""
        fields = []
        form_type = FormType.UNKNOWN
        
        try:
            pdf_reader = PyPDF2.PdfReader(BytesIO(pdf_content))
            
            # Extract text to detect form type
            text_content = ""
            for page in pdf_reader.pages:
                text_content += page.extract_text() + "\n"
            
            form_type = self.detect_form_type(text_content, filename)
            
            # Try to extract form fields
            if '/AcroForm' in pdf_reader.trailer['/Root']:
                form = pdf_reader.trailer['/Root']['/AcroForm']
                if '/Fields' in form:
                    for field_ref in form['/Fields']:
                        field_obj = field_ref.get_object()
                        field = self._extract_field_info(field_obj)
                        if field:
                            fields.append(field)
            
            # If no form fields, extract from text
            if not fields:
                fields = self._extract_fields_from_text(text_content)
            
        except Exception as e:
            st.error(f"Error extracting PDF fields: {str(e)}")
        
        return form_type, fields
    
    def _extract_field_info(self, field_obj) -> Optional[FormField]:
        """Extract field information from PDF field object"""
        try:
            field_name = str(field_obj.get('/T', 'Unknown'))
            field_type_pdf = str(field_obj.get('/FT', '/Tx'))
            field_value = str(field_obj.get('/V', ''))
            
            # Determine field type
            field_type = self._determine_field_type(field_name, field_type_pdf)
            
            # Generate label
            label = self._generate_label(field_name)
            
            # Get database mapping
            mapping_info = self._get_database_mapping(field_name)
            database_mapping = mapping_info[0] if mapping_info else ""
            
            # Determine section
            section = self._determine_section(field_name)
            
            return FormField(
                pdf_field_name=field_name,
                field_type=field_type,
                label=label,
                database_mapping=database_mapping,
                is_mapped=bool(database_mapping),
                value=field_value,
                section=section
            )
        except:
            return None
    
    def _extract_fields_from_text(self, text: str) -> List[FormField]:
        """Extract fields from text content"""
        fields = []
        
        # Common patterns
        patterns = [
            r'(?:Part|Section)\s+(\d+)[:\s]+([^\n]+)',
            r'(\d+[a-z]?)\.?\s+([A-Z][^:\n]+):?',
            r'([A-Z][^:]+):\s*_{3,}',
            r'Item Number\s+(\d+[a-z]?)\.?\s*([^\n]+)',
            r'\[?\s*\]?\s*([A-Z][^:\n]+)',
        ]
        
        seen_fields = set()
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.MULTILINE)
            for match in matches:
                if len(match.groups()) >= 2:
                    field_id = match.group(1)
                    field_label = match.group(2).strip()
                else:
                    field_label = match.group(1).strip()
                    field_id = re.sub(r'[^a-zA-Z0-9]', '_', field_label)[:20]
                
                field_name = f"{field_id}_{re.sub(r'[^a-zA-Z0-9]', '_', field_label)[:30]}".lower()
                
                if field_name not in seen_fields and len(field_label) > 3:
                    seen_fields.add(field_name)
                    
                    # Determine field type
                    field_type = self._determine_field_type(field_name, field_label)
                    
                    # Get database mapping
                    mapping_info = self._get_database_mapping(field_name)
                    database_mapping = mapping_info[0] if mapping_info else ""
                    
                    # Determine section
                    section = self._determine_section(field_name)
                    
                    fields.append(FormField(
                        pdf_field_name=field_name,
                        field_type=field_type,
                        label=field_label,
                        database_mapping=database_mapping,
                        is_mapped=bool(database_mapping),
                        section=section
                    ))
        
        return fields[:200]  # Limit fields
    
    def _determine_field_type(self, field_name: str, additional_info: str = "") -> str:
        """Determine the field type based on field name and additional info"""
        field_lower = field_name.lower()
        info_lower = additional_info.lower()
        combined = f"{field_lower} {info_lower}"
        
        # Check patterns
        for type_name, patterns in self.field_type_patterns.items():
            for pattern in patterns:
                if pattern in combined:
                    if type_name == "checkbox":
                        return "CheckBox"
                    elif type_name == "radio":
                        return "CheckBox"  # Use CheckBox for radio in TS format
                    elif type_name == "date":
                        return "Date"
                    elif type_name == "single":
                        return "SingleBox"
                    elif type_name == "condition":
                        return "ConditionBox"
                    elif type_name == "address":
                        return "AddressTypeBox"
                    elif type_name == "fullname":
                        return "FullName"
                    elif type_name == "multiple":
                        return "MultipleBox"
        
        return "TextBox"  # Default
    
    def _generate_label(self, field_name: str) -> str:
        """Generate a readable label from field name"""
        # Remove common prefixes
        label = re.sub(r'^(txt|chk|cbo|rad|btn|frm)', '', field_name)
        # Replace underscores and camelCase
        label = re.sub(r'([A-Z])', r' \1', label)
        label = label.replace('_', ' ').replace('-', ' ')
        # Remove extra spaces and title case
        label = ' '.join(word.capitalize() for word in label.split() if word)
        return label
    
    def _get_database_mapping(self, field_name: str) -> Optional[Tuple[str, str]]:
        """Get database mapping based on field name"""
        field_lower = field_name.lower()
        
        # Check each pattern
        for pattern, mapping in self.database_patterns.items():
            if pattern in field_lower:
                return (mapping[0], mapping[1])
        
        # More complex pattern matching
        if any(term in field_lower for term in ['customer', 'company', 'employer', 'petitioner']):
            if 'name' in field_lower and 'signatory' not in field_lower:
                return ("customer.customer_name", "TextBox")
            elif 'street' in field_lower or 'address' in field_lower:
                return ("customer.address_street", "TextBox")
            elif 'city' in field_lower:
                return ("customer.address_city", "TextBox")
            elif 'state' in field_lower:
                return ("customer.address_state", "TextBox")
            elif 'zip' in field_lower:
                return ("customer.address_zip", "TextBox")
        
        if 'beneficiary' in field_lower or 'alien' in field_lower:
            if 'last' in field_lower or 'family' in field_lower:
                return ("beneficary.Beneficiary.beneficiaryLastName", "TextBox")
            elif 'first' in field_lower or 'given' in field_lower:
                return ("beneficary.Beneficiary.beneficiaryFirstName", "TextBox")
            elif 'middle' in field_lower:
                return ("beneficary.Beneficiary.beneficiaryMiddleName", "TextBox")
        
        if 'attorney' in field_lower:
            if 'last' in field_lower:
                return ("attorney.attorneyInfo.lastName", "TextBox")
            elif 'first' in field_lower:
                return ("attorney.attorneyInfo.firstName", "TextBox")
            elif 'bar' in field_lower:
                return ("attorney.attorneyInfo.stateBarNumber", "TextBox")
            elif 'firm' in field_lower:
                return ("attorneyLawfirmDetails.lawfirmDetails.lawFirmName", "TextBox")
        
        return None
    
    def _determine_section(self, field_name: str) -> str:
        """Determine which section a field belongs to"""
        field_lower = field_name.lower()
        
        if any(term in field_lower for term in ['customer', 'company', 'employer', 'petitioner', 'signatory']):
            return "customerData"
        elif any(term in field_lower for term in ['beneficiary', 'alien', 'worker', 'employee']):
            return "beneficiaryData"
        elif any(term in field_lower for term in ['attorney', 'lawyer', 'representative', 'bar']):
            return "attorneyData"
        elif any(term in field_lower for term in ['case', 'petition', 'application']):
            return "caseData"
        elif 'default' in field_lower or 'checkbox' in field_lower:
            return "defaultData"
        else:
            return "questionnaireData"
    
    def generate_typescript_mapping(self, form_type: str, form_name: str, fields: List[FormField]) -> str:
        """Generate TypeScript mapping in the exact format of the examples"""
        # Group fields by section
        sections = {
            "customerData": {},
            "beneficiaryData": {},
            "attorneyData": {},
            "caseData": {},
            "defaultData": {},
            "questionnaireData": {},
            "conditionalData": {}
        }
        
        # Process fields
        for field in fields:
            section = field.section if field.section else "questionnaireData"
            
            if field.is_mapped and field.database_mapping:
                # Format: "fieldName": "database.path:FieldType"
                field_entry = f'"{field.pdf_field_name}": "{field.database_mapping}:{field.field_type}"'
                
                if field.is_conditional:
                    # Add to conditional data
                    sections["conditionalData"][field.pdf_field_name] = field_entry
                else:
                    # Add to appropriate section
                    if section in sections:
                        sections[section][field.pdf_field_name] = field_entry
            else:
                # Unmapped fields go to questionnaire
                field_entry = f'"{field.pdf_field_name}": "{field.label}:{field.field_type}"'
                sections["questionnaireData"][field.pdf_field_name] = field_entry
        
        # Build TypeScript
        ts_content = f"""export const {form_type.replace('-', '')} = {{
    "formname": "{form_type}",
    "pdfName": "{form_type}","""
        
        # Add each section
        for section_name, section_fields in sections.items():
            if section_fields:  # Only add non-empty sections
                ts_content += f'\n    "{section_name}": {{'
                
                # Add fields
                field_entries = []
                for field_name, field_entry in section_fields.items():
                    field_entries.append(f'\n        {field_entry}')
                
                ts_content += ','.join(field_entries)
                ts_content += '\n    },'
        
        # Remove last comma and close
        ts_content = ts_content.rstrip(',')
        ts_content += '\n};'
        
        return ts_content
    
    def generate_questionnaire_json(self, fields: List[FormField], form_type: str) -> Dict[str, Any]:
        """Generate questionnaire JSON for unmapped fields"""
        controls = []
        
        # Add form title
        controls.append({
            "name": f"{form_type.lower()}_title",
            "label": f"{form_type} Additional Information",
            "type": "title",
            "validators": {},
            "className": "h5",
            "style": {"col": "12"}
        })
        
        # Process unmapped fields
        for i, field in enumerate(fields):
            if not field.is_mapped:
                # Create control based on field type
                control = {
                    "name": field.pdf_field_name,
                    "label": field.label,
                    "type": self._map_field_type_to_control(field.field_type),
                    "validators": {"required": False},
                    "style": {"col": "6"}
                }
                
                # Add specific properties based on type
                if field.field_type == "CheckBox":
                    control["type"] = "checkbox"
                    control["style"]["success"] = True
                elif field.field_type == "Date":
                    control["type"] = "date"
                elif field.field_type == "ConditionBox":
                    control["className"] = "hide-dummy-class"
                elif field.field_type == "AddressTypeBox":
                    # Create radio buttons for Apt/Ste/Flr
                    controls.extend([
                        {
                            "id": f"{field.pdf_field_name}_apt",
                            "name": field.pdf_field_name,
                            "label": "Apt",
                            "type": "radio",
                            "value": "Apt",
                            "validators": {},
                            "style": {"col": "1", "radio": True, "success": True}
                        },
                        {
                            "id": f"{field.pdf_field_name}_ste",
                            "name": field.pdf_field_name,
                            "label": "Ste",
                            "type": "radio",
                            "value": "Ste",
                            "validators": {},
                            "style": {"col": "1", "radio": True, "success": True}
                        },
                        {
                            "id": f"{field.pdf_field_name}_flr",
                            "name": field.pdf_field_name,
                            "label": "Flr",
                            "type": "radio",
                            "value": "Flr",
                            "validators": {},
                            "style": {"col": "1", "radio": True, "success": True}
                        }
                    ])
                    continue
                
                controls.append(control)
                
                # Add notes field for certain types
                if field.field_type in ["CheckBox", "ConditionBox"]:
                    notes_control = {
                        "name": f"{field.pdf_field_name}_notes",
                        "label": "Notes",
                        "type": "textarea",
                        "validators": {"required": False},
                        "style": {"col": "12"},
                        "className": "hide-dummy-class"
                    }
                    controls.append(notes_control)
        
        return {"controls": controls}
    
    def _map_field_type_to_control(self, field_type: str) -> str:
        """Map field type to questionnaire control type"""
        mapping = {
            "TextBox": "text",
            "CheckBox": "checkbox",
            "SingleBox": "text",
            "ConditionBox": "text",
            "AddressTypeBox": "radio",
            "FullName": "text",
            "Date": "date",
            "MultipleBox": "text"
        }
        return mapping.get(field_type, "text")
    
    def generate_consolidated_output(self, form_type: str, form_name: str, fields: List[FormField]) -> Dict[str, Any]:
        """Generate consolidated output with all information"""
        mapped_fields = [f for f in fields if f.is_mapped]
        unmapped_fields = [f for f in fields if not f.is_mapped]
        
        # Create sections summary
        sections_summary = {}
        for field in fields:
            section = field.section if field.section else "questionnaireData"
            if section not in sections_summary:
                sections_summary[section] = {"mapped": 0, "unmapped": 0, "fields": []}
            
            if field.is_mapped:
                sections_summary[section]["mapped"] += 1
            else:
                sections_summary[section]["unmapped"] += 1
            
            sections_summary[section]["fields"].append({
                "pdf_field": field.pdf_field_name,
                "label": field.label,
                "type": field.field_type,
                "mapping": field.database_mapping if field.is_mapped else None
            })
        
        return {
            "form_info": {
                "form_type": form_type,
                "form_name": form_name,
                "extraction_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "total_fields": len(fields),
                "mapped_fields": len(mapped_fields),
                "unmapped_fields": len(unmapped_fields),
                "coverage_percentage": round((len(mapped_fields) / len(fields) * 100), 2) if fields else 0
            },
            "sections_summary": sections_summary,
            "field_type_distribution": {
                field_type: len([f for f in fields if f.field_type == field_type])
                for field_type in set(f.field_type for f in fields)
            }
        }

def main():
    st.set_page_config(
        page_title="USCIS Form Mapper - TypeScript & Questionnaire Generator",
        page_icon="📄",
        layout="wide"
    )
    
    st.title("📄 USCIS Form Mapper - TypeScript & Questionnaire Generator")
    st.markdown("Upload a USCIS form to generate TypeScript mappings and questionnaires in the exact format needed")
    
    # Initialize mapper
    mapper = IntelligentFormMapper()
    
    # File upload
    uploaded_file = st.file_uploader(
        "Upload USCIS Form (PDF)",
        type=['pdf'],
        help="Upload any USCIS form PDF to analyze and generate mappings"
    )
    
    if uploaded_file is not None:
        # Read PDF content
        pdf_content = uploaded_file.read()
        
        # Extract fields and detect form type
        form_type, fields = mapper.extract_pdf_fields(pdf_content, uploaded_file.name)
        
        if not fields:
            st.warning("No fields could be extracted from this PDF. The form might be scanned or image-based.")
        else:
            st.success(f"✅ Detected Form Type: **{form_type.value}**")
            st.info(f"📊 Extracted **{len(fields)}** fields from the PDF")
            
            # Quick metrics
            col1, col2, col3, col4 = st.columns(4)
            mapped_count = len([f for f in fields if f.is_mapped])
            unmapped_count = len([f for f in fields if not f.is_mapped])
            
            with col1:
                st.metric("Total Fields", len(fields))
            with col2:
                st.metric("Auto-Mapped", mapped_count)
            with col3:
                st.metric("Needs Mapping", unmapped_count)
            with col4:
                coverage = (mapped_count / len(fields) * 100) if fields else 0
                st.metric("Coverage", f"{coverage:.1f}%")
            
            # Create tabs
            tab1, tab2, tab3, tab4, tab5 = st.tabs([
                "💻 TypeScript Mapping",
                "❓ Questionnaire JSON",
                "📊 Field Analysis",
                "🔄 Consolidated View",
                "📥 Download All"
            ])
            
            with tab1:
                st.header("TypeScript Mapping")
                st.markdown("Generated in the exact format of your examples (I140.ts, I129L.ts)")
                
                ts_content = mapper.generate_typescript_mapping(
                    form_type.value,
                    uploaded_file.name,
                    fields
                )
                
                # Display with syntax highlighting
                st.code(ts_content, language="typescript")
                
                # Download button
                st.download_button(
                    label=f"📥 Download {form_type.value}.ts",
                    data=ts_content,
                    file_name=f"{form_type.value}.ts",
                    mime="text/typescript"
                )
            
            with tab2:
                st.header("Questionnaire JSON")
                st.markdown("For unmapped fields requiring user input")
                
                questionnaire = mapper.generate_questionnaire_json(fields, form_type.value)
                
                if questionnaire["controls"]:
                    # Display formatted JSON
                    st.json(questionnaire)
                    
                    # Download button
                    st.download_button(
                        label=f"📥 Download {form_type.value.lower()}-questionnaire.json",
                        data=json.dumps(questionnaire, indent=2),
                        file_name=f"{form_type.value.lower()}-questionnaire.json",
                        mime="application/json"
                    )
                else:
                    st.success("🎉 All fields are mapped! No questionnaire needed.")
            
            with tab3:
                st.header("Field Analysis")
                
                # Field type distribution
                st.subheader("Field Type Distribution")
                field_type_counts = {}
                for field in fields:
                    field_type_counts[field.field_type] = field_type_counts.get(field.field_type, 0) + 1
                
                df_types = pd.DataFrame(
                    list(field_type_counts.items()),
                    columns=["Field Type", "Count"]
                )
                st.bar_chart(df_types.set_index("Field Type"))
                
                # Section distribution
                st.subheader("Section Distribution")
                section_counts = {}
                for field in fields:
                    section = field.section if field.section else "questionnaireData"
                    section_counts[section] = section_counts.get(section, 0) + 1
                
                df_sections = pd.DataFrame(
                    list(section_counts.items()),
                    columns=["Section", "Field Count"]
                )
                st.dataframe(df_sections, use_container_width=True)
                
                # Detailed field list
                st.subheader("All Fields")
                field_data = []
                for field in fields:
                    field_data.append({
                        "PDF Field": field.pdf_field_name,
                        "Label": field.label,
                        "Type": field.field_type,
                        "Section": field.section,
                        "Mapped": "✅" if field.is_mapped else "❌",
                        "Database Mapping": field.database_mapping if field.is_mapped else "-"
                    })
                
                df_fields = pd.DataFrame(field_data)
                st.dataframe(df_fields, use_container_width=True, height=400)
            
            with tab4:
                st.header("Consolidated View")
                
                consolidated = mapper.generate_consolidated_output(
                    form_type.value,
                    uploaded_file.name,
                    fields
                )
                
                # Display as formatted JSON
                st.json(consolidated)
                
                # Download button
                st.download_button(
                    label="📥 Download Consolidated Analysis",
                    data=json.dumps(consolidated, indent=2),
                    file_name=f"{form_type.value.lower()}_analysis.json",
                    mime="application/json"
                )
            
            with tab5:
                st.header("Download All Files")
                st.markdown("Download all generated files in one click")
                
                # Create a zip file with all outputs
                import zipfile
                from io import BytesIO
                
                zip_buffer = BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    # Add TypeScript file
                    ts_content = mapper.generate_typescript_mapping(
                        form_type.value,
                        uploaded_file.name,
                        fields
                    )
                    zip_file.writestr(f"{form_type.value}.ts", ts_content)
                    
                    # Add Questionnaire JSON
                    questionnaire = mapper.generate_questionnaire_json(fields, form_type.value)
                    if questionnaire["controls"]:
                        zip_file.writestr(
                            f"{form_type.value.lower()}-questionnaire.json",
                            json.dumps(questionnaire, indent=2)
                        )
                    
                    # Add Consolidated Analysis
                    consolidated = mapper.generate_consolidated_output(
                        form_type.value,
                        uploaded_file.name,
                        fields
                    )
                    zip_file.writestr(
                        f"{form_type.value.lower()}_analysis.json",
                        json.dumps(consolidated, indent=2)
                    )
                
                # Download button for zip
                st.download_button(
                    label=f"📥 Download All Files ({form_type.value}.zip)",
                    data=zip_buffer.getvalue(),
                    file_name=f"{form_type.value.lower()}_mapping_package.zip",
                    mime="application/zip"
                )
    
    else:
        st.info("👆 Please upload a USCIS form PDF to begin analysis")
        
        # Show example output format
        with st.expander("📋 Example TypeScript Output Format"):
            example_ts = '''export const I140 = {
    "formname": "I140",
    "pdfName": "I-140",
    "customerData": {
        "companyName": "customer.customer_name:TextBox",
        "customerAddressStreet": "customer.address_street:TextBox",
        "ein": "customer.customer_tax_id:SingleBox"
    },
    "beneficiaryData": {
        "beneficiaryLastName": "beneficary.Beneficiary.beneficiaryLastName:TextBox",
        "beneficiaryFirstName": "beneficary.Beneficiary.beneficiaryFirstName:TextBox"
    },
    "attorneyData": {
        "attorneyStateBarNumber": "attorney.attorneyInfo.stateBarNumber:TextBox"
    },
    "questionnaireData": {
        "additionalInfo": "Additional Information:TextBox"
    }
};'''
            st.code(example_ts, language="typescript")

if __name__ == "__main__":
    main()
