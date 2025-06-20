import streamlit as st
import json
import pandas as pd
from typing import Dict, List, Tuple, Any, Optional
import re
from dataclasses import dataclass, field
from datetime import datetime
import PyPDF2
from io import BytesIO
import base64

@dataclass
class SmartFormField:
    pdf_field_name: str
    field_type: str
    database_mapping: str = ""
    section: str = ""  # customerData, beneficiaryData, etc.
    label: str = ""
    is_conditional: bool = False
    condition_data: Dict[str, Any] = field(default_factory=dict)

class USCISSmartMapper:
    def __init__(self):
        # Database field patterns for intelligent mapping
        self.database_patterns = {
            "customer": {
                "patterns": ["petitioner", "employer", "company", "organization", "pet_"],
                "fields": {
                    "name": ["customer_name", "company_name", "organization_name", "employer_name"],
                    "address": ["address_street", "address_number", "address_city", "address_state", "address_zip", "address_country"],
                    "tax": ["customer_tax_id", "ein", "fein"],
                    "business": ["customer_type_of_business", "customer_year_established", "customer_total_employees", 
                                "customer_gross_annual_income", "customer_net_annual_income", "customer_naics_code"],
                    "signatory": ["signatory_first_name", "signatory_last_name", "signatory_middle_name", 
                                 "signatory_job_title", "signatory_work_phone", "signatory_email_id"]
                }
            },
            "beneficiary": {
                "patterns": ["ben_", "beneficiary", "applicant", "alien", "worker"],
                "fields": {
                    "name": ["beneficiaryLastName", "beneficiaryFirstName", "beneficiaryMiddleName"],
                    "personal": ["beneficiaryDateOfBirth", "beneficiaryGender", "beneficiarySsn", "alienNumber"],
                    "birth": ["beneficiaryCountryOfBirth", "beneficiaryProvinceOfBirth", "stateBirth", "beneficiaryCityOfBirth"],
                    "citizenship": ["beneficiaryCitizenOfCountry"],
                    "contact": ["beneficiaryHomeNumber", "beneficiaryCellNumber", "beneficiaryPrimaryEmailAddress"],
                    "parents": ["fatherLastName", "fatherFirstName", "motherLastName", "motherFirstName"]
                }
            },
            "attorney": {
                "patterns": ["att_", "attorney", "lawyer", "representative"],
                "fields": {
                    "info": ["lastName", "firstName", "middleName", "stateBarNumber", "licensingAuthority"],
                    "contact": ["workPhone", "faxNumber", "emailAddress"],
                    "firm": ["lawFirmName", "lawFirmFein"]
                }
            },
            "addresses": {
                "work": ["WorkAddress", "workAddress", "employment_address"],
                "home": ["HomeAddress", "homeAddress", "residence_address"],
                "foreign": ["ForeignAddress", "foreignAddress", "abroad_address"]
            },
            "documents": {
                "i94": ["i94Number", "i94ArrivalDate", "i94ExpiryDate", "statusAtArrival", "placeLastArrival"],
                "passport": ["passportNumber", "passportIssueDate", "passportExpiryDate", "passportIssueCountry"],
                "visa": ["visaStatus", "visaExpiryDate", "visaConsulateCity", "visaConsulateCountry"]
            }
        }
    
    def detect_form_type(self, pdf_content: bytes) -> str:
        """Detect USCIS form type from PDF content"""
        try:
            pdf_reader = PyPDF2.PdfReader(BytesIO(pdf_content))
            text = ""
            for page in pdf_reader.pages[:3]:  # Check first 3 pages
                text += page.extract_text()
            
            text_lower = text.lower()
            
            # Form detection patterns
            form_patterns = {
                "I-140": ["i-140", "immigrant petition for alien worker"],
                "I-129": ["i-129", "petition for a nonimmigrant worker"],
                "I-765": ["i-765", "employment authorization"],
                "I-485": ["i-485", "application to register permanent residence"],
                "I-539": ["i-539", "extend/change nonimmigrant status"],
                "I-907": ["i-907", "request for premium processing"],
                "I-131": ["i-131", "application for travel document"],
                "I-864": ["i-864", "affidavit of support"],
                "I-829": ["i-829", "remove conditions"],
                "I-918": ["i-918", "u nonimmigrant status"],
                "G-28": ["g-28", "notice of entry of appearance"],
                "ETA-9089": ["eta-9089", "eta 9089", "permanent employment certification"],
                "LCA": ["lca", "labor condition application"],
            }
            
            for form_type, patterns in form_patterns.items():
                for pattern in patterns:
                    if pattern in text_lower:
                        return form_type
            
            return "UNKNOWN"
        except Exception as e:
            st.error(f"Error detecting form type: {str(e)}")
            return "UNKNOWN"
    
    def extract_pdf_fields(self, pdf_content: bytes) -> List[SmartFormField]:
        """Extract form fields from PDF with smart mapping"""
        fields = []
        try:
            pdf_reader = PyPDF2.PdfReader(BytesIO(pdf_content))
            
            # Try to extract AcroForm fields
            if '/AcroForm' in pdf_reader.trailer['/Root']:
                form = pdf_reader.trailer['/Root']['/AcroForm']
                if '/Fields' in form:
                    for field_ref in form['/Fields']:
                        field_obj = field_ref.get_object()
                        field_info = self._extract_field_info(field_obj)
                        if field_info:
                            fields.append(field_info)
            
            # If no form fields, extract from text
            if not fields:
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
                fields = self._extract_fields_from_text(text)
            
        except Exception as e:
            st.error(f"Error extracting fields: {str(e)}")
        
        return fields
    
    def _extract_field_info(self, field_obj) -> Optional[SmartFormField]:
        """Extract field information with smart mapping"""
        try:
            field_name = str(field_obj.get('/T', 'Unknown'))
            field_type = str(field_obj.get('/FT', '/Tx'))
            
            # Map PDF field types
            type_mapping = {
                '/Tx': 'TextBox',
                '/Btn': 'CheckBox',
                '/Ch': 'DropDown',
                '/Sig': 'Signature'
            }
            
            field_type_mapped = type_mapping.get(field_type, 'TextBox')
            
            # Smart mapping
            mapping_info = self._smart_map_field(field_name)
            
            return SmartFormField(
                pdf_field_name=field_name,
                field_type=field_type_mapped,
                database_mapping=mapping_info['mapping'],
                section=mapping_info['section'],
                label=self._generate_label(field_name),
                is_conditional=mapping_info.get('is_conditional', False),
                condition_data=mapping_info.get('condition_data', {})
            )
        except:
            return None
    
    def _smart_map_field(self, field_name: str) -> Dict[str, Any]:
        """Intelligently map field to database structure"""
        field_lower = field_name.lower()
        result = {
            'mapping': '',
            'section': 'questionnaireData',
            'is_conditional': False,
            'condition_data': {}
        }
        
        # Customer fields
        if any(pattern in field_lower for pattern in self.database_patterns['customer']['patterns']):
            result['section'] = 'customerData'
            
            if 'name' in field_lower and 'company' in field_lower:
                result['mapping'] = 'customer.customer_name'
            elif 'street' in field_lower:
                result['mapping'] = 'customer.address_street'
            elif 'city' in field_lower:
                result['mapping'] = 'customer.address_city'
            elif 'state' in field_lower and 'address' in field_lower:
                result['mapping'] = 'customer.address_state'
            elif 'zip' in field_lower:
                result['mapping'] = 'customer.address_zip'
            elif 'tax' in field_lower or 'ein' in field_lower:
                result['mapping'] = 'customer.customer_tax_id'
            elif 'naics' in field_lower:
                result['mapping'] = 'customer.customer_naics_code'
            elif 'signatory' in field_lower:
                if 'first' in field_lower:
                    result['mapping'] = 'customer.signatory_first_name'
                elif 'last' in field_lower:
                    result['mapping'] = 'customer.signatory_last_name'
                elif 'title' in field_lower or 'job' in field_lower:
                    result['mapping'] = 'customer.signatory_job_title'
                elif 'phone' in field_lower:
                    result['mapping'] = 'customer.signatory_work_phone'
                elif 'email' in field_lower:
                    result['mapping'] = 'customer.signatory_email_id'
        
        # Beneficiary fields
        elif any(pattern in field_lower for pattern in self.database_patterns['beneficiary']['patterns']):
            result['section'] = 'beneficiaryData'
            
            if 'last' in field_lower and 'name' in field_lower:
                result['mapping'] = 'beneficary.Beneficiary.beneficiaryLastName'
            elif 'first' in field_lower and 'name' in field_lower:
                result['mapping'] = 'beneficary.Beneficiary.beneficiaryFirstName'
            elif 'middle' in field_lower and 'name' in field_lower:
                result['mapping'] = 'beneficary.Beneficiary.beneficiaryMiddleName'
            elif 'birth' in field_lower and 'date' in field_lower:
                result['mapping'] = 'beneficary.Beneficiary.beneficiaryDateOfBirth'
            elif 'birth' in field_lower and 'country' in field_lower:
                result['mapping'] = 'beneficary.Beneficiary.beneficiaryCountryOfBirth'
            elif 'citizen' in field_lower and 'country' in field_lower:
                result['mapping'] = 'beneficary.Beneficiary.beneficiaryCitizenOfCountry'
            elif 'ssn' in field_lower or 'social' in field_lower:
                result['mapping'] = 'beneficary.Beneficiary.beneficiarySsn'
            elif 'alien' in field_lower and ('number' in field_lower or '#' in field_lower):
                result['mapping'] = 'beneficary.Beneficiary.alienNumber'
            elif 'gender' in field_lower:
                result['mapping'] = 'beneficary.Beneficiary.beneficiaryGender'
        
        # Attorney fields
        elif any(pattern in field_lower for pattern in self.database_patterns['attorney']['patterns']):
            result['section'] = 'attorneyData'
            
            if 'last' in field_lower and 'name' in field_lower:
                result['mapping'] = 'attorney.attorneyInfo.lastName'
            elif 'first' in field_lower and 'name' in field_lower:
                result['mapping'] = 'attorney.attorneyInfo.firstName'
            elif 'bar' in field_lower and 'number' in field_lower:
                result['mapping'] = 'attorney.attorneyInfo.stateBarNumber'
            elif 'email' in field_lower:
                result['mapping'] = 'attorney.attorneyInfo.emailAddress'
            elif 'phone' in field_lower:
                result['mapping'] = 'attorney.attorneyInfo.workPhone'
            elif 'firm' in field_lower and 'name' in field_lower:
                result['mapping'] = 'attorneyLawfirmDetails.lawfirmDetails.lawFirmName'
        
        # Document fields
        elif 'i94' in field_lower or 'i-94' in field_lower:
            result['section'] = 'beneficiaryData'
            if 'number' in field_lower:
                result['mapping'] = 'beneficary.I94Details.I94.i94Number'
            elif 'arrival' in field_lower:
                result['mapping'] = 'beneficary.I94Details.I94.i94ArrivalDate'
            elif 'expir' in field_lower:
                result['mapping'] = 'beneficary.I94Details.I94.i94ExpiryDate'
        
        elif 'passport' in field_lower:
            result['section'] = 'beneficiaryData'
            if 'number' in field_lower:
                result['mapping'] = 'beneficary.PassportDetails.Passport.passportNumber'
            elif 'issue' in field_lower and 'date' in field_lower:
                result['mapping'] = 'beneficary.PassportDetails.Passport.passportIssueDate'
            elif 'expir' in field_lower:
                result['mapping'] = 'beneficary.PassportDetails.Passport.passportExpiryDate'
            elif 'country' in field_lower:
                result['mapping'] = 'beneficary.PassportDetails.Passport.passportIssueCountry'
        
        # Address fields
        elif 'address' in field_lower:
            if 'work' in field_lower:
                result['section'] = 'beneficiaryData'
                if 'street' in field_lower:
                    result['mapping'] = 'beneficary.WorkAddress.addressStreet'
                elif 'city' in field_lower:
                    result['mapping'] = 'beneficary.WorkAddress.addressCity'
                elif 'state' in field_lower:
                    result['mapping'] = 'beneficary.WorkAddress.addressState'
                elif 'zip' in field_lower:
                    result['mapping'] = 'beneficary.WorkAddress.addressZip'
            elif 'home' in field_lower:
                result['section'] = 'beneficiaryData'
                if 'street' in field_lower:
                    result['mapping'] = 'beneficary.HomeAddress.addressStreet'
                elif 'city' in field_lower:
                    result['mapping'] = 'beneficary.HomeAddress.addressCity'
            elif 'foreign' in field_lower:
                result['section'] = 'beneficiaryData'
                if 'street' in field_lower:
                    result['mapping'] = 'beneficary.ForeignAddress.addressStreet'
        
        # Check for conditional fields
        if any(word in field_lower for word in ['if', 'when', 'condition', 'dependent']):
            result['is_conditional'] = True
            result['condition_data'] = {
                'condition': '',
                'conditionTrue': result['mapping'] or field_name,
                'conditionFalse': '',
                'conditionType': result.get('field_type', 'TextBox')
            }
        
        # Default mappings
        if not result['mapping']:
            if 'date' in field_lower:
                result['mapping'] = f"questionnaire.{field_name}:Date"
            elif 'phone' in field_lower:
                result['mapping'] = f"questionnaire.{field_name}:TextBox"
            elif 'email' in field_lower:
                result['mapping'] = f"questionnaire.{field_name}:TextBox"
            else:
                result['mapping'] = f"{field_name}:ConditionBox"
        
        return result
    
    def _generate_label(self, field_name: str) -> str:
        """Generate human-readable label from field name"""
        # Remove common prefixes
        label = re.sub(r'^(txt|chk|cbo|rad|btn|BEN_|ATT_|PET_)', '', field_name)
        # Replace underscores and camelCase
        label = re.sub(r'([A-Z])', r' \1', label)
        label = label.replace('_', ' ').replace('-', ' ')
        # Clean up
        label = ' '.join(word.capitalize() for word in label.split())
        return label.strip()
    
    def _extract_fields_from_text(self, text: str) -> List[SmartFormField]:
        """Extract fields from text content"""
        fields = []
        
        # Common USCIS form field patterns
        patterns = [
            r'Part\s+(\d+)[:\s]+([^\n]+)',
            r'Section\s+(\d+)[:\s]+([^\n]+)',
            r'Item\s+Number\s+(\d+[a-z]?)\.?\s*([^\n]+)',
            r'(\d+[a-z]?)\.?\s+([A-Z][^:\n]+):?\s*(?:_+|\[?\s*\]?)',
            r'([A-Z][^:]+):\s*(?:_+|\[?\s*\]?)',
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
                    field_id = field_label
                
                field_name = re.sub(r'[^a-zA-Z0-9_]', '_', f"field_{field_id}")
                
                if field_name not in seen_fields and len(field_label) > 3:
                    seen_fields.add(field_name)
                    
                    mapping_info = self._smart_map_field(field_name + " " + field_label)
                    
                    fields.append(SmartFormField(
                        pdf_field_name=field_name,
                        field_type="TextBox",
                        database_mapping=mapping_info['mapping'],
                        section=mapping_info['section'],
                        label=field_label,
                        is_conditional=mapping_info.get('is_conditional', False),
                        condition_data=mapping_info.get('condition_data', {})
                    ))
        
        return fields[:200]  # Limit to 200 fields
    
    def generate_typescript(self, form_name: str, form_type: str, fields: List[SmartFormField]) -> str:
        """Generate TypeScript in the exact format of I140.ts"""
        # Group fields by section
        sections = {
            'customerData': {},
            'beneficiaryData': {},
            'attorneyData': {},
            'questionnaireData': {},
            'defaultData': {},
            'conditionalData': {},
            'caseData': {}
        }
        
        # Organize fields into sections
        for field in fields:
            section = field.section
            if field.is_conditional and field.condition_data:
                sections['conditionalData'][field.pdf_field_name] = field.condition_data
            else:
                mapping_parts = field.database_mapping.split(':')
                mapping = mapping_parts[0] if mapping_parts else field.database_mapping
                field_type = mapping_parts[1] if len(mapping_parts) > 1 else field.field_type
                
                sections[section][field.pdf_field_name] = f"{mapping}:{field_type}"
        
        # Add default fields
        sections['defaultData']['default'] = ":CheckBox"
        sections['defaultData']['selectFormG28'] = ":CheckBox"
        
        # Generate TypeScript
        ts_content = f"""export const {form_type.replace('-', '')} = {{
    "formname": "{form_type.replace('-', '')}",
    "pdfName": "{form_type}","""
        
        # Add sections
        for section_name, section_data in sections.items():
            if section_data:  # Only add non-empty sections
                ts_content += f'\n    "{section_name}": {{'
                
                if section_name == 'conditionalData':
                    for field_name, condition_data in section_data.items():
                        ts_content += f'\n        "{field_name}": {json.dumps(condition_data, indent=8).replace("    ", "        ")},'
                else:
                    for field_name, mapping in section_data.items():
                        ts_content += f'\n        "{field_name}": "{mapping}",'
                
                # Remove trailing comma and close section
                ts_content = ts_content.rstrip(',')
                ts_content += '\n    },'
        
        # Remove trailing comma and close main object
        ts_content = ts_content.rstrip(',')
        ts_content += '\n}'
        
        return ts_content
    
    def generate_questionnaire_json(self, fields: List[SmartFormField]) -> Dict[str, Any]:
        """Generate questionnaire JSON for unmapped fields"""
        controls = []
        
        for field in fields:
            if field.section == 'questionnaireData' or not field.database_mapping:
                control = {
                    "name": field.pdf_field_name,
                    "label": field.label or field.pdf_field_name,
                    "type": self._map_field_type_to_control(field.field_type),
                    "validators": {"required": False},
                    "style": {"col": "6"}
                }
                
                if field.is_conditional:
                    control["className"] = "hide-dummy-class"
                
                if field.field_type == "CheckBox":
                    control["type"] = "colorSwitch"
                elif field.field_type == "DropDown":
                    control["options"] = []
                    control["lookup"] = "TBD"
                
                controls.append(control)
        
        return {"controls": controls}
    
    def _map_field_type_to_control(self, field_type: str) -> str:
        """Map field type to questionnaire control type"""
        mapping = {
            "TextBox": "text",
            "CheckBox": "colorSwitch",
            "DropDown": "dropdown",
            "Signature": "text",
            "RadioButton": "radio"
        }
        return mapping.get(field_type, "text")
    
    def generate_consolidated_mapping(self, form_type: str, fields: List[SmartFormField]) -> Dict[str, Any]:
        """Generate comprehensive mapping report"""
        mapped_fields = [f for f in fields if f.database_mapping and f.section != 'questionnaireData']
        unmapped_fields = [f for f in fields if not f.database_mapping or f.section == 'questionnaireData']
        
        # Group by database objects
        object_mappings = {}
        for field in mapped_fields:
            if '.' in field.database_mapping:
                obj_path = field.database_mapping.split('.')[0]
                if obj_path not in object_mappings:
                    object_mappings[obj_path] = []
                object_mappings[obj_path].append({
                    "pdf_field": field.pdf_field_name,
                    "mapping": field.database_mapping,
                    "field_type": field.field_type,
                    "label": field.label
                })
        
        return {
            "form_info": {
                "form_type": form_type,
                "extraction_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "total_fields": len(fields),
                "mapped_fields": len(mapped_fields),
                "unmapped_fields": len(unmapped_fields),
                "coverage_percentage": round((len(mapped_fields) / len(fields) * 100), 2) if fields else 0
            },
            "section_distribution": {
                section: len([f for f in fields if f.section == section])
                for section in ['customerData', 'beneficiaryData', 'attorneyData', 'questionnaireData', 'caseData']
            },
            "object_mappings": object_mappings,
            "intelligent_mapping_summary": {
                "customer_fields": len([f for f in fields if f.section == 'customerData']),
                "beneficiary_fields": len([f for f in fields if f.section == 'beneficiaryData']),
                "attorney_fields": len([f for f in fields if f.section == 'attorneyData']),
                "questionnaire_fields": len([f for f in fields if f.section == 'questionnaireData']),
                "conditional_fields": len([f for f in fields if f.is_conditional])
            }
        }

def main():
    st.set_page_config(
        page_title="USCIS Smart Form Mapper",
        page_icon="🇺🇸",
        layout="wide"
    )
    
    st.title("🇺🇸 USCIS Smart Form Mapper with Intelligent Database Mapping")
    st.markdown("Upload any USCIS form to generate TypeScript mappings with automatic database field detection")
    
    # Initialize mapper
    mapper = USCISSmartMapper()
    
    # Sidebar with information
    with st.sidebar:
        st.header("📋 Supported Features")
        st.markdown("""
        - ✅ **Automatic Form Detection** - Identifies USCIS form type
        - ✅ **Smart Field Mapping** - Intelligently maps to database structure
        - ✅ **Section Organization** - Groups fields by data type
        - ✅ **Conditional Logic** - Handles dependent fields
        - ✅ **TypeScript Generation** - Creates production-ready TS files
        - ✅ **Questionnaire Generation** - For unmapped fields
        - ✅ **Coverage Analysis** - Shows mapping completeness
        """)
        
        st.header("🗂️ Database Structure")
        st.markdown("""
        **Customer Data:**
        - Company information
        - Signatory details
        - Business metrics
        
        **Beneficiary Data:**
        - Personal information
        - Document details (I-94, Passport, Visa)
        - Multiple addresses
        
        **Attorney Data:**
        - Professional information
        - Law firm details
        - Contact information
        """)
    
    # Main content
    uploaded_file = st.file_uploader(
        "Upload USCIS Form (PDF)",
        type=['pdf'],
        help="Upload any USCIS form PDF to analyze and map fields"
    )
    
    if uploaded_file is not None:
        pdf_content = uploaded_file.read()
        
        # Detect form type
        with st.spinner("Detecting form type..."):
            form_type = mapper.detect_form_type(pdf_content)
        
        if form_type == "UNKNOWN":
            st.warning("⚠️ Could not auto-detect form type. Please enter it manually:")
            form_type = st.text_input("Form Type (e.g., I-140, I-129, I-765)", value="I-XXX")
        else:
            st.success(f"✅ Detected Form Type: **{form_type}**")
        
        # Extract fields
        with st.spinner("Extracting and mapping fields..."):
            fields = mapper.extract_pdf_fields(pdf_content)
        
        if not fields:
            st.error("No fields could be extracted from this PDF.")
        else:
            st.info(f"📊 Extracted **{len(fields)}** fields with smart mapping")
            
            # Create tabs
            tab1, tab2, tab3, tab4, tab5 = st.tabs([
                "💻 TypeScript Export",
                "❓ Questionnaire JSON",
                "📊 Mapping Analytics",
                "📋 Field Details",
                "🔄 Full Report"
            ])
            
            with tab1:
                st.header("TypeScript Export")
                st.markdown("Generated in the exact format of your existing I140.ts structure")
                
                ts_content = mapper.generate_typescript(uploaded_file.name, form_type, fields)
                
                # Syntax highlighting
                st.code(ts_content, language="typescript")
                
                # Download button
                st.download_button(
                    label=f"📥 Download {form_type.replace('-', '')}.ts",
                    data=ts_content,
                    file_name=f"{form_type.replace('-', '')}.ts",
                    mime="text/typescript"
                )
            
            with tab2:
                st.header("Questionnaire JSON")
                
                unmapped_count = len([f for f in fields if f.section == 'questionnaireData'])
                if unmapped_count > 0:
                    st.info(f"Found {unmapped_count} fields requiring questionnaire entries")
                    
                    questionnaire = mapper.generate_questionnaire_json(fields)
                    st.json(questionnaire)
                    
                    st.download_button(
                        label="📥 Download Questionnaire JSON",
                        data=json.dumps(questionnaire, indent=2),
                        file_name=f"{form_type.lower()}-questionnaire.json",
                        mime="application/json"
                    )
                else:
                    st.success("🎉 All fields successfully mapped to database!")
            
            with tab3:
                st.header("Mapping Analytics")
                
                consolidated = mapper.generate_consolidated_mapping(form_type, fields)
                
                # Metrics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Fields", consolidated["form_info"]["total_fields"])
                with col2:
                    st.metric("Mapped Fields", consolidated["form_info"]["mapped_fields"])
                with col3:
                    st.metric("Coverage", f"{consolidated['form_info']['coverage_percentage']}%")
                with col4:
                    conditional_count = consolidated["intelligent_mapping_summary"]["conditional_fields"]
                    st.metric("Conditional Fields", conditional_count)
                
                # Section distribution chart
                st.subheader("Field Distribution by Section")
                section_data = pd.DataFrame([
                    {"Section": section.replace("Data", ""), "Count": count}
                    for section, count in consolidated["section_distribution"].items()
                    if count > 0
                ])
                if not section_data.empty:
                    st.bar_chart(section_data.set_index("Section"))
                
                # Object mappings
                st.subheader("Database Object Mappings")
                for obj_name, mappings in consolidated["object_mappings"].items():
                    with st.expander(f"📁 {obj_name} ({len(mappings)} fields)"):
                        df = pd.DataFrame(mappings)
                        st.dataframe(df, use_container_width=True)
            
            with tab4:
                st.header("Field Details")
                
                # Group fields by section
                sections = {}
                for field in fields:
                    if field.section not in sections:
                        sections[field.section] = []
                    sections[field.section].append(field)
                
                # Display by section
                for section_name, section_fields in sections.items():
                    st.subheader(f"{section_name} ({len(section_fields)} fields)")
                    
                    field_data = []
                    for field in section_fields:
                        field_data.append({
                            "PDF Field": field.pdf_field_name,
                            "Label": field.label,
                            "Type": field.field_type,
                            "Database Mapping": field.database_mapping,
                            "Conditional": "Yes" if field.is_conditional else "No"
                        })
                    
                    df = pd.DataFrame(field_data)
                    st.dataframe(df, use_container_width=True, height=300)
            
            with tab5:
                st.header("Full Mapping Report")
                
                full_report = mapper.generate_consolidated_mapping(form_type, fields)
                st.json(full_report)
                
                st.download_button(
                    label="📥 Download Full Report JSON",
                    data=json.dumps(full_report, indent=2),
                    file_name=f"{form_type.lower()}_mapping_report.json",
                    mime="application/json"
                )
    
    else:
        st.info("👆 Please upload a USCIS form PDF to begin intelligent mapping")
        
        with st.expander("🤖 How Smart Mapping Works"):
            st.markdown("""
            This tool uses intelligent pattern matching to automatically map PDF fields to your database structure:
            
            **1. Customer Fields Detection:**
            - Looks for patterns like "petitioner", "employer", "company"
            - Maps to customer.* database fields
            - Handles signatory information
            
            **2. Beneficiary Fields Detection:**
            - Identifies "beneficiary", "applicant", "alien" patterns
            - Maps personal info, documents (I-94, passport, visa)
            - Handles multiple address types
            
            **3. Attorney Fields Detection:**
            - Recognizes attorney/lawyer related fields
            - Maps to attorney info and law firm details
            
            **4. Conditional Logic:**
            - Detects dependent fields
            - Creates proper condition structures
            
            **5. Section Organization:**
            - Automatically groups fields into appropriate data sections
            - Maintains the exact structure of your existing TypeScript files
            """)

if __name__ == "__main__":
    main()
