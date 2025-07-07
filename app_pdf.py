import streamlit as st
import json
import re
import fitz  # PyMuPDF
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Set
from collections import defaultdict, OrderedDict
import pandas as pd
from dataclasses import dataclass, field
import hashlib
from io import BytesIO
import openai

# Configure page
st.set_page_config(
    page_title="USCIS Form Reader Pro",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Modern clean CSS
st.markdown("""
<style>
    /* Clean modern theme */
    .stApp {
        background: #ffffff;
    }
    
    .main .block-container {
        padding: 2rem 3rem;
        max-width: 1600px;
    }
    
    /* Clean cards */
    div[data-testid="stVerticalBlock"] > div:has(> div > div > h2),
    div[data-testid="stVerticalBlock"] > div:has(> div > div > h3) {
        background: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 10px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    
    /* Headers */
    h1 {
        color: #2c3e50;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    
    h2 {
        color: #34495e;
        font-size: 1.75rem;
        font-weight: 600;
        margin-bottom: 1rem;
        border-bottom: 2px solid #007bff;
        padding-bottom: 0.5rem;
    }
    
    /* Mapping interface */
    .mapping-container {
        background: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 1rem;
    }
    
    .field-info {
        background: #e9ecef;
        padding: 0.5rem;
        border-radius: 4px;
        margin-bottom: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# Database Structure - Comprehensive mapping
DB_OBJECTS = {
    "beneficiary": {
        "Beneficiary": ["beneficiaryFirstName", "beneficiaryLastName", "beneficiaryMiddleName",
                       "beneficiaryGender", "beneficiaryDateOfBirth", "beneficiarySsn",
                       "alienNumber", "alienRegistrationNumber", "beneficiaryCountryOfBirth", 
                       "beneficiaryCitizenOfCountry", "beneficiaryProvinceOfBirth",
                       "maritalStatus", "uscisOnlineAccountNumber"],
        "MailingAddress": ["addressStreet", "addressCity", "addressState", "addressZip", 
                          "addressCountry", "addressAptSteFlrNumber", "inCareOfName",
                          "addressNumber", "addressType"],
        "HomeAddress": ["addressStreet", "addressCity", "addressState", "addressZip", 
                       "addressCountry", "addressNumber", "addressType"],
        "ContactInfo": ["daytimeTelephoneNumber", "mobileTelephoneNumber", "emailAddress",
                       "workPhone", "faxNumber"],
        "PassportDetails": {"Passport": ["passportNumber", "passportIssueCountry", 
                                        "passportIssueDate", "passportExpiryDate"]},
        "VisaDetails": {"Visa": ["currentNonimmigrantStatus", "dateStatusExpires", "visaNumber",
                                "visaStatus", "visaConsulateCity", "visaConsulateCountry"]}
    },
    "petitioner": {
        "": ["familyName", "givenName", "middleName", "companyOrOrganizationName"],
        "ContactInfo": ["daytimeTelephoneNumber", "mobileTelephoneNumber", "emailAddress"],
        "Address": ["addressStreet", "addressCity", "addressState", "addressZip", "addressCountry"]
    },
    "customer": {
        "": ["customer_name", "customer_tax_id", "customer_type_of_business", 
             "customer_year_established", "customer_gross_annual_income", 
             "customer_net_annual_income", "customer_total_employees"],
        "SignatoryInfo": ["signatory_first_name", "signatory_last_name", "signatory_middle_name",
                         "signatory_job_title", "signatory_work_phone", "signatory_email",
                         "signatory_email_id", "signatory_mobile_phone"],
        "Address": ["address_street", "address_city", "address_state", "address_zip", 
                   "address_country", "address_number", "address_type"]
    },
    "attorney": {
        "attorneyInfo": ["firstName", "lastName", "middleName", "barNumber", "stateBarNumber",
                        "workPhone", "emailAddress", "faxNumber", "licensingAuthority"],
        "address": ["addressStreet", "addressCity", "addressState", "addressZip",
                   "addressCountry", "addressNumber", "addressType"]
    },
    "attorneyLawfirmDetails": {
        "lawfirmDetails": ["lawFirmName", "lawFirmEIN"],
        "address": ["addressStreet", "addressCity", "addressState", "addressZip",
                   "addressCountry", "addressNumber", "addressType"]
    },
    "case": {
        "": ["caseType", "caseSubType", "h1bRegistrationNumber", "h1BPetitionType",
            "requestedAction"]
    },
    "employment": {
        "": ["employment", "temporary", "employerName", "employerDate"]
    }
}

@dataclass
class PDFField:
    """Represents a unique field from PDF"""
    widget_name: str = ""
    field_id: str = ""
    field_key: str = ""  # Short key for TS/JSON export
    part_number: int = 1
    part_name: str = "Part 1"
    field_label: str = "Unnamed Field"
    field_type: str = "text"
    page: int = 1
    value: str = ""
    db_mapping: Optional[str] = None
    is_mapped: bool = False
    to_questionnaire: bool = False
    ai_suggestion: Optional[str] = None
    confidence: float = 0.0
    
    def __hash__(self):
        return hash(self.widget_name)
    
    def get_status(self) -> str:
        if self.is_mapped:
            return "✅ Mapped"
        elif self.to_questionnaire:
            return "📋 Questionnaire"
        else:
            return "⚪ Unmapped"

class AIFieldMapper:
    """AI-powered field mapping assistant using OpenAI"""
    
    def __init__(self):
        # Get API key from secrets
        self.api_key = None
        try:
            self.api_key = st.secrets["OPENAI_API_KEY"]
            openai.api_key = self.api_key
        except:
            pass
        self.mapping_cache = {}
    
    def extract_field_info(self, widget_name: str, form_type: str, part_info: dict) -> dict:
        """Use OpenAI to extract better field information"""
        if not self.api_key:
            return self._fallback_extraction(widget_name)
        
        try:
            prompt = f"""Given a USCIS form field widget name, extract and format the field information.

Form Type: {form_type}
Part: {part_info.get('name', 'Unknown')}
Widget Name: {widget_name}

Please analyze this widget name and return a JSON object with:
{{
    "field_key": "short key for this field (e.g., 'pt1_2a', 'familyName')",
    "field_label": "human readable label (e.g., 'Family Name (Last Name)')",
    "field_type": "text|checkbox|radio|dropdown|signature|date",
    "db_suggestion": "suggested database path or 'questionnaire'"
}}

Common patterns:
- Family/Last names -> beneficiary.Beneficiary.beneficiaryLastName
- First/Given names -> beneficiary.Beneficiary.beneficiaryFirstName
- Attorney fields -> attorney.attorneyInfo.fieldName
- Customer fields -> customer.fieldName
- Checkboxes/radios usually go to questionnaire

Be concise and accurate."""

            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=200
            )
            
            result = json.loads(response.choices[0].message.content.strip())
            return result
            
        except Exception as e:
            st.warning(f"AI extraction failed: {str(e)}")
            return self._fallback_extraction(widget_name)
    
    def _fallback_extraction(self, widget_name: str) -> dict:
        """Fallback extraction without AI"""
        # Clean widget name
        clean = re.sub(r'form\d*\[?\d*\]?\.|#subform\[?\d*\]?\.', '', widget_name)
        clean = re.sub(r'Part\d+\[?\d*\]?\.', '', clean)
        clean = clean.strip('._[]#')
        
        # Generate field key
        field_key = clean.replace(' ', '_').replace('-', '_').lower()
        if len(field_key) > 20:
            field_key = field_key[:20]
        
        # Generate label
        label = ' '.join(word.capitalize() for word in clean.replace('_', ' ').split())
        
        return {
            "field_key": field_key,
            "field_label": label,
            "field_type": "text",
            "db_suggestion": None
        }

class USCISExtractor:
    """Enhanced USCIS form extractor"""
    
    def __init__(self):
        self.init_session_state()
        self.db_paths = self._build_db_paths()
        self.ai_mapper = AIFieldMapper()
        self.seen_fields = set()
    
    def init_session_state(self):
        """Initialize session state"""
        if 'fields' not in st.session_state:
            st.session_state.fields = []
        if 'fields_by_part' not in st.session_state:
            st.session_state.fields_by_part = OrderedDict()
        if 'form_info' not in st.session_state:
            st.session_state.form_info = {}
        if 'pdf_processed' not in st.session_state:
            st.session_state.pdf_processed = False
        if 'extraction_log' not in st.session_state:
            st.session_state.extraction_log = []
    
    def _build_db_paths(self) -> List[str]:
        """Build flat list of all database paths"""
        paths = []
        
        def add_paths(obj_name: str, structure: dict, prefix: str = ""):
            for key, value in structure.items():
                current_prefix = f"{prefix}.{key}" if key and prefix else prefix or obj_name
                
                if isinstance(value, list):
                    for field in value:
                        full_path = f"{current_prefix}.{field}" if current_prefix else field
                        paths.append(full_path)
                elif isinstance(value, dict):
                    add_paths(obj_name, value, current_prefix)
        
        for obj_name, structure in DB_OBJECTS.items():
            add_paths(obj_name, structure, obj_name)
        
        return sorted(set(paths))
    
    def extract_pdf(self, pdf_file) -> bool:
        """Extract fields from PDF"""
        try:
            # Reset state
            st.session_state.fields = []
            st.session_state.fields_by_part = OrderedDict()
            st.session_state.extraction_log = []
            self.seen_fields.clear()
            
            # Read PDF
            pdf_bytes = pdf_file.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            # Detect form type
            st.session_state.form_info = self._detect_form_type(doc)
            form_type = st.session_state.form_info.get('form_number', 'Unknown')
            
            # Build part mapping
            part_mapping = self._build_part_mapping(doc)
            
            # Extract fields
            all_fields = []
            progress_bar = st.progress(0)
            
            for page_num in range(len(doc)):
                progress_bar.progress((page_num + 1) / len(doc))
                page = doc[page_num]
                
                # Get part info
                part_info = part_mapping.get(page_num, {
                    'number': 1, 
                    'name': 'Part 1', 
                    'title': 'General Information'
                })
                
                # Skip attorney/preparer sections
                if self._should_skip_section(part_info.get('title', '')):
                    continue
                
                # Get widgets
                widgets = page.widgets()
                if widgets:
                    widget_list = list(widgets)
                    
                    for widget in widget_list:
                        if widget and hasattr(widget, 'field_name') and widget.field_name:
                            if widget.field_name not in self.seen_fields:
                                self.seen_fields.add(widget.field_name)
                                
                                # Create field with AI assistance
                                field = self._create_field_with_ai(
                                    widget, 
                                    part_info,
                                    page_num + 1,
                                    form_type
                                )
                                
                                all_fields.append(field)
            
            progress_bar.empty()
            doc.close()
            
            # Sort fields by part and page
            all_fields.sort(key=lambda f: (f.part_number or 0, f.page or 0))
            st.session_state.fields = all_fields
            
            # Group by part
            for field in all_fields:
                part_key = field.part_name
                if part_key not in st.session_state.fields_by_part:
                    st.session_state.fields_by_part[part_key] = []
                st.session_state.fields_by_part[part_key].append(field)
            
            st.session_state.pdf_processed = True
            return True
            
        except Exception as e:
            st.error(f"❌ Error processing PDF: {str(e)}")
            import traceback
            st.code(traceback.format_exc())
            return False
    
    def _detect_form_type(self, doc) -> dict:
        """Detect form type from PDF"""
        first_page_text = doc[0].get_text().upper()
        
        forms = {
            'I-90': 'Application to Replace Permanent Resident Card',
            'I-129': 'Petition for a Nonimmigrant Worker',
            'I-130': 'Petition for Alien Relative',
            'I-140': 'Immigrant Petition for Alien Worker',
            'I-485': 'Application to Register Permanent Residence',
            'I-539': 'Application to Extend/Change Nonimmigrant Status',
            'I-765': 'Application for Employment Authorization',
            'N-400': 'Application for Naturalization',
            'G-28': 'Notice of Entry of Appearance as Attorney'
        }
        
        for form_num, title in forms.items():
            if form_num in first_page_text:
                return {
                    'form_number': form_num,
                    'form_title': title,
                    'pages': len(doc)
                }
        
        # Check for H supplement forms
        if 'H CLASSIFICATION SUPPLEMENT' in first_page_text:
            if 'H-2B' in first_page_text:
                return {
                    'form_number': 'H-2B',
                    'form_title': 'H-2B Classification Supplement',
                    'pages': len(doc)
                }
            else:
                return {
                    'form_number': 'H-1B',
                    'form_title': 'H Classification Supplement',
                    'pages': len(doc)
                }
        
        return {
            'form_number': 'Unknown',
            'form_title': 'Unknown USCIS Form',
            'pages': len(doc)
        }
    
    def _build_part_mapping(self, doc) -> Dict[int, dict]:
        """Build mapping of pages to parts/sections"""
        part_mapping = {}
        current_part = {'number': 1, 'name': 'Part 1', 'title': 'General Information'}
        
        # Patterns for parts and sections
        patterns = [
            r'Part\s+(\d+)[\.\s\-:]*([^\n]*)',
            r'Section\s+(\d+)[\.\s\-:]*([^\n]*)',
            r'PART\s+(\d+)[\.\s\-:]*([^\n]*)',
            r'SECTION\s+(\d+)[\.\s\-:]*([^\n]*)'
        ]
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            page_text = page.get_text()
            
            found_new_part = False
            for pattern in patterns:
                matches = list(re.finditer(pattern, page_text, re.IGNORECASE))
                if matches:
                    match = matches[0]
                    part_type = "Section" if "section" in match.group(0).lower() else "Part"
                    part_num = int(match.group(1))
                    part_title = match.group(2).strip() if match.group(2) else ""
                    
                    current_part = {
                        'number': part_num,
                        'name': f"{part_type} {part_num}",
                        'title': part_title or f"{part_type} {part_num}"
                    }
                    found_new_part = True
                    break
            
            part_mapping[page_num] = current_part.copy()
        
        return part_mapping
    
    def _should_skip_section(self, title: str) -> bool:
        """Check if section should be skipped"""
        skip_keywords = [
            'attorney', 'preparer', 'interpreter', 
            'signature of the person preparing',
            'declaration', 'certification',
            'additional information'
        ]
        title_lower = title.lower()
        return any(keyword in title_lower for keyword in skip_keywords)
    
    def _create_field_with_ai(self, widget, part_info: dict, page: int, form_type: str) -> PDFField:
        """Create field using AI for better extraction"""
        widget_name = widget.field_name or ""
        
        # Get AI extraction
        field_info = self.ai_mapper.extract_field_info(widget_name, form_type, part_info)
        
        # Get widget type
        field_type = self._get_field_type(widget.field_type if hasattr(widget, 'field_type') else 4)
        
        # Override AI type if we have widget info
        if field_type in ['checkbox', 'radio', 'button']:
            field_info['field_type'] = field_type
        
        # Generate unique field ID
        field_id = f"P{part_info['number']}_{field_info['field_key']}"
        
        # Get value
        field_value = ""
        if hasattr(widget, 'field_value') and widget.field_value:
            field_value = str(widget.field_value)
        
        # Create field
        field = PDFField(
            widget_name=widget_name,
            field_id=field_id,
            field_key=field_info['field_key'],
            part_number=part_info['number'],
            part_name=part_info['name'],
            field_label=field_info['field_label'],
            field_type=field_info['field_type'],
            page=page,
            value=field_value,
            ai_suggestion=field_info.get('db_suggestion')
        )
        
        # Auto-categorize checkboxes/radios
        if field.field_type in ['checkbox', 'radio', 'button']:
            field.to_questionnaire = True
        
        return field
    
    def _get_field_type(self, widget_type: int) -> str:
        """Map widget type to field type"""
        type_map = {
            1: "button",
            2: "checkbox", 
            3: "radio",
            4: "text",
            5: "dropdown",
            6: "list",
            7: "signature"
        }
        return type_map.get(widget_type, "text")
    
    def generate_typescript(self) -> str:
        """Generate TypeScript mapping file matching the example format"""
        form_name = st.session_state.form_info.get('form_number', 'Form').replace('-', '')
        
        # Group fields by type
        customer_fields = []
        beneficiary_fields = []
        attorney_fields = []
        questionnaire_fields = []
        default_fields = []
        conditional_fields = []
        
        for field in st.session_state.fields:
            if field.is_mapped and field.db_mapping:
                # Determine field suffix based on type
                suffix = self._get_field_suffix(field.field_type)
                field_entry = f'        "{field.field_key}": "{field.db_mapping}{suffix}"'
                
                # Sort into appropriate category
                if field.db_mapping.startswith('customer.'):
                    customer_fields.append(field_entry)
                elif field.db_mapping.startswith('beneficiary.'):
                    beneficiary_fields.append(field_entry)
                elif field.db_mapping.startswith('attorney.') or field.db_mapping.startswith('attorneyLawfirmDetails.'):
                    attorney_fields.append(field_entry)
            elif field.to_questionnaire:
                # Format for questionnaire
                quest_entry = f'        "{field.field_key}": "{field.field_key}:{self._get_field_suffix(field.field_type)}"'
                questionnaire_fields.append(quest_entry)
        
        # Build TypeScript
        ts = f"""export const {form_name} = {{
    "formname": "{form_name}","""
        
        # Add customer data
        if customer_fields:
            ts += '\n    "customerData": {\n'
            ts += ',\n'.join(customer_fields)
            ts += '\n    },'
        else:
            ts += '\n    "customerData": null,'
        
        # Add beneficiary data
        if beneficiary_fields:
            ts += '\n    "beneficiaryData": {\n'
            ts += ',\n'.join(beneficiary_fields)
            ts += '\n    },'
        else:
            ts += '\n    "beneficiaryData": null,'
        
        # Add questionnaire data
        if questionnaire_fields:
            ts += '\n    "questionnaireData": {\n'
            ts += ',\n'.join(questionnaire_fields)
            ts += '\n    },'
        else:
            ts += '\n    "questionnaireData": {},'
        
        # Add default data (empty for now)
        ts += '\n    "defaultData": {},'
        
        # Add conditional data (empty for now)
        ts += '\n    "conditionalData": {},'
        
        # Add attorney data
        if attorney_fields:
            ts += '\n    "attorneyData": {\n'
            ts += ',\n'.join(attorney_fields)
            ts += '\n    },'
        else:
            ts += '\n    "attorneyData": null,'
        
        # Add PDF name and case data
        ts += f"""
    "pdfName": "{st.session_state.form_info.get('form_number', 'Unknown')}",
    "caseData": null
}}"""
        
        return ts
    
    def _get_field_suffix(self, field_type: str) -> str:
        """Get TypeScript field suffix based on type"""
        suffix_map = {
            'text': ':TextBox',
            'checkbox': ':CheckBox',
            'radio': ':RadioBox',
            'dropdown': ':DropdownBox',
            'signature': ':SignatureBox',
            'date': ':Date',
            'button': ':ButtonBox'
        }
        return suffix_map.get(field_type, ':TextBox')
    
    def generate_json(self) -> str:
        """Generate JSON for questionnaire matching the example format"""
        controls = []
        
        # Group by part
        for part_name, fields in st.session_state.fields_by_part.items():
            # Get questionnaire fields for this part
            quest_fields = [f for f in fields if f.to_questionnaire or not f.is_mapped]
            
            if quest_fields:
                # Add part title
                part_num = int(re.search(r'\d+', part_name).group()) if re.search(r'\d+', part_name) else 1
                
                controls.append({
                    "name": f"p{part_num}_title",
                    "label": part_name,
                    "type": "title",
                    "validators": {},
                    "className": "h5",
                    "style": {"col": "12"}
                })
                
                # Add fields
                for field in quest_fields:
                    field_control = {
                        "name": field.field_key,
                        "label": field.field_label,
                        "type": field.field_type,
                        "validators": {}
                    }
                    
                    # Add style based on field type
                    if field.field_type == "text":
                        field_control["style"] = {"col": "4"}
                        field_control["validators"]["required"] = False
                    elif field.field_type in ["checkbox", "radio"]:
                        field_control["style"] = {"col": "12", "success": True}
                        field_control["className"] = "custom-control-success"
                        if field.field_type == "radio":
                            field_control["id"] = f"{field.field_key}_id"
                            field_control["value"] = "1"
                    
                    controls.append(field_control)
        
        # Build final JSON
        data = {
            "controls": controls
        }
        
        return json.dumps(data, indent=4)

def main():
    """Main application"""
    extractor = USCISExtractor()
    
    # Header
    st.markdown("# 🤖 USCIS Form Reader Pro")
    st.markdown("### AI-Powered PDF Form Field Extraction & Mapping")
    
    # Check OpenAI availability
    if not extractor.ai_mapper.api_key:
        st.warning("⚠️ OpenAI API key not found in secrets. Add OPENAI_API_KEY for better extraction.")
    
    # Main tabs
    tab1, tab2, tab3 = st.tabs(["📤 Upload & Extract", "🎯 Map Fields", "📥 Export"])
    
    with tab1:
        col1, col2 = st.columns([3, 2])
        
        with col1:
            st.markdown("## Upload USCIS Form")
            
            uploaded_file = st.file_uploader(
                "Select a USCIS PDF form",
                type=['pdf'],
                help="Upload any fillable USCIS form (I-90, I-129, G-28, etc.)"
            )
            
            if uploaded_file:
                if st.button("🚀 Extract Fields", type="primary", use_container_width=True):
                    with st.spinner("Extracting fields with AI..."):
                        if extractor.extract_pdf(uploaded_file):
                            st.success(f"✅ Extracted {len(st.session_state.fields)} fields!")
                            st.balloons()
        
        with col2:
            if st.session_state.pdf_processed:
                st.markdown("## Form Details")
                
                form_info = st.session_state.form_info
                st.info(f"""
                **Form:** {form_info.get('form_number', 'Unknown')}  
                **Title:** {form_info.get('form_title', 'Unknown')}  
                **Pages:** {form_info.get('pages', 0)}  
                **Fields:** {len(st.session_state.fields)}  
                **Parts:** {len(st.session_state.fields_by_part)}
                """)
                
                # Stats
                total = len(st.session_state.fields)
                mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
                quest = sum(1 for f in st.session_state.fields if f.to_questionnaire)
                
                m1, m2, m3 = st.columns(3)
                m1.metric("Mapped", mapped)
                m2.metric("Questionnaire", quest)
                m3.metric("Unmapped", total - mapped - quest)
    
    with tab2:
        if not st.session_state.pdf_processed:
            st.info("📤 Please upload and extract a PDF form first.")
        else:
            st.markdown("## Field Mapping Dashboard")
            
            # Quick actions
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("📋 All Checkboxes → Questionnaire", use_container_width=True):
                    count = 0
                    for field in st.session_state.fields:
                        if field.field_type in ['checkbox', 'radio', 'button'] and not field.to_questionnaire:
                            field.to_questionnaire = True
                            field.is_mapped = False
                            count += 1
                    st.success(f"Moved {count} fields to questionnaire!")
                    st.rerun()
            
            with col2:
                if st.button("🔄 Reset All Mappings", use_container_width=True):
                    for field in st.session_state.fields:
                        field.is_mapped = False
                        field.db_mapping = None
                        field.to_questionnaire = False
                        if field.field_type in ['checkbox', 'radio', 'button']:
                            field.to_questionnaire = True
                    st.success("Reset all mappings!")
                    st.rerun()
            
            with col3:
                if st.button("📊 Auto-Map Common Fields", use_container_width=True):
                    count = 0
                    # Implement basic auto-mapping logic
                    st.info("Auto-mapping coming soon!")
            
            st.markdown("---")
            
            # Field mapping interface
            for part_name, fields in st.session_state.fields_by_part.items():
                with st.expander(f"{part_name} ({len(fields)} fields)", expanded=True):
                    for field in fields:
                        # Create mapping container
                        with st.container():
                            st.markdown(f"""
                            <div class="mapping-container">
                                <div class="field-info">
                                    <strong>{field.field_label}</strong> ({field.field_type})
                                    <br><small>Widget: {field.widget_name}</small>
                                    <br><small>Key: {field.field_key}</small>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Mapping controls
                            col1, col2, col3 = st.columns([4, 3, 1])
                            
                            with col1:
                                if field.field_type == 'text':
                                    # Database object dropdown
                                    db_options = ["-- Select Database Field --", "📋 Move to Questionnaire"] + extractor.db_paths
                                    
                                    # Get current selection
                                    current_idx = 0
                                    if field.is_mapped and field.db_mapping:
                                        try:
                                            current_idx = db_options.index(field.db_mapping)
                                        except ValueError:
                                            db_options.insert(2, field.db_mapping)
                                            current_idx = 2
                                    elif field.to_questionnaire:
                                        current_idx = 1
                                    
                                    selected = st.selectbox(
                                        "Database Mapping",
                                        db_options,
                                        index=current_idx,
                                        key=f"db_{field.field_id}",
                                        label_visibility="collapsed"
                                    )
                                    
                                    if selected != db_options[current_idx]:
                                        if selected == "📋 Move to Questionnaire":
                                            field.to_questionnaire = True
                                            field.is_mapped = False
                                            field.db_mapping = None
                                        elif selected != "-- Select Database Field --":
                                            field.db_mapping = selected
                                            field.is_mapped = True
                                            field.to_questionnaire = False
                                        st.rerun()
                            
                            with col2:
                                if field.field_type == 'text':
                                    # Manual entry
                                    manual = st.text_input(
                                        "Or enter custom path",
                                        value="",
                                        key=f"manual_{field.field_id}",
                                        placeholder="e.g., customer.custom.field",
                                        label_visibility="collapsed"
                                    )
                                    
                                    if manual and st.button("Apply", key=f"apply_{field.field_id}"):
                                        field.db_mapping = manual
                                        field.is_mapped = True
                                        field.to_questionnaire = False
                                        st.rerun()
                                else:
                                    # Checkbox for questionnaire
                                    include = st.checkbox(
                                        "Include in Questionnaire",
                                        value=field.to_questionnaire,
                                        key=f"quest_{field.field_id}"
                                    )
                                    if include != field.to_questionnaire:
                                        field.to_questionnaire = include
                                        st.rerun()
                            
                            with col3:
                                st.markdown(f"**{field.get_status()}**")
                            
                            # Show AI suggestion if available
                            if field.ai_suggestion and not field.is_mapped:
                                st.caption(f"🤖 AI suggests: {field.ai_suggestion}")
                            
                            st.markdown("---")
    
    with tab3:
        if not st.session_state.pdf_processed:
            st.info("📤 Please upload and extract a PDF form first.")
        else:
            st.markdown("## Export Options")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 📄 TypeScript Export")
                
                if st.button("Generate TypeScript", type="primary", use_container_width=True):
                    ts_code = extractor.generate_typescript()
                    
                    st.download_button(
                        "⬇️ Download .ts file",
                        ts_code,
                        f"{st.session_state.form_info.get('form_number', 'form')}.ts",
                        mime="text/typescript",
                        use_container_width=True
                    )
                    
                    with st.expander("Preview TypeScript"):
                        st.code(ts_code, language="typescript")
            
            with col2:
                st.markdown("### 📋 JSON Export")
                
                if st.button("Generate JSON", type="primary", use_container_width=True):
                    json_code = extractor.generate_json()
                    
                    st.download_button(
                        "⬇️ Download .json file",
                        json_code,
                        f"{st.session_state.form_info.get('form_number', 'form')}-questionnaire.json",
                        mime="application/json",
                        use_container_width=True
                    )
                    
                    with st.expander("Preview JSON"):
                        st.code(json_code, language="json")
            
            st.markdown("---")
            
            # Summary
            total = len(st.session_state.fields)
            mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
            quest = sum(1 for f in st.session_state.fields if f.to_questionnaire)
            
            st.info(f"""
            **Export Summary:**
            - Total Fields: {total}
            - Database Mapped: {mapped}
            - Questionnaire: {quest}
            - Unmapped: {total - mapped - quest}
            """)

if __name__ == "__main__":
    main()
