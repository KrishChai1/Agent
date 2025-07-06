import streamlit as st
import json
import re
import fitz  # PyMuPDF
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict, OrderedDict
import pandas as pd
from dataclasses import dataclass, field
import base64
from io import BytesIO

# Configure page
st.set_page_config(
    page_title="USCIS Form Reader & Mapper",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for modern UI
st.markdown("""
<style>
    /* Main theme */
    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
    }
    
    /* Cards */
    .css-1r6slb0 {
        background: rgba(30, 41, 59, 0.8) !important;
        backdrop-filter: blur(10px);
        border: 1px solid rgba(59, 130, 246, 0.2);
        border-radius: 16px;
        padding: 2rem;
    }
    
    /* Metrics */
    [data-testid="metric-container"] {
        background: rgba(15, 23, 42, 0.8);
        border: 1px solid rgba(59, 130, 246, 0.2);
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
    }
    
    [data-testid="metric-value"] {
        font-size: 2rem;
        font-weight: 700;
        background: linear-gradient(to right, #3b82f6, #8b5cf6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #3b82f6, #8b5cf6);
        color: white;
        border: none;
        padding: 0.75rem 1.5rem;
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 20px rgba(59, 130, 246, 0.4);
    }
    
    /* File uploader */
    .stFileUploader {
        background: rgba(59, 130, 246, 0.05);
        border: 2px dashed rgba(59, 130, 246, 0.5);
        border-radius: 12px;
        padding: 2rem;
    }
    
    /* Selectbox */
    .stSelectbox > div > div {
        background: rgba(15, 23, 42, 0.8);
        border: 1px solid rgba(59, 130, 246, 0.3);
        border-radius: 6px;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 1rem;
        border-bottom: 1px solid rgba(59, 130, 246, 0.2);
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        padding: 0.5rem 1rem;
    }
    
    .stTabs [aria-selected="true"] {
        background: rgba(59, 130, 246, 0.1);
        border-bottom: 2px solid #3b82f6;
    }
    
    /* Progress bar */
    .stProgress > div > div {
        background: linear-gradient(to right, #3b82f6, #8b5cf6);
    }
    
    /* Success/Info/Warning messages */
    .stSuccess {
        background: rgba(34, 197, 94, 0.1);
        border: 1px solid rgba(34, 197, 94, 0.3);
        border-radius: 8px;
    }
    
    .stInfo {
        background: rgba(59, 130, 246, 0.1);
        border: 1px solid rgba(59, 130, 246, 0.3);
        border-radius: 8px;
    }
    
    /* DataFrames */
    .stDataFrame {
        background: rgba(15, 23, 42, 0.5);
        border-radius: 8px;
    }
    
    /* Expanders */
    .streamlit-expanderHeader {
        background: rgba(30, 41, 59, 0.8);
        border: 1px solid rgba(59, 130, 246, 0.2);
        border-radius: 8px;
    }
    
    /* Headers */
    h1 {
        background: linear-gradient(to right, #3b82f6, #8b5cf6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        font-size: 3rem;
        margin-bottom: 0.5rem;
    }
    
    h2 {
        color: #e2e8f0;
    }
    
    h3 {
        color: #cbd5e1;
    }
    
    /* Custom classes */
    .subtitle {
        text-align: center;
        color: #94a3b8;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    
    .field-item {
        background: rgba(30, 41, 59, 0.8);
        border: 1px solid rgba(59, 130, 246, 0.2);
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 0.75rem;
    }
    
    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 500;
        text-transform: uppercase;
    }
    
    .status-mapped {
        background: rgba(34, 197, 94, 0.2);
        color: #22c55e;
    }
    
    .status-questionnaire {
        background: rgba(251, 146, 60, 0.2);
        color: #fb923c;
    }
    
    .status-unmapped {
        background: rgba(100, 116, 139, 0.2);
        color: #94a3b8;
    }
</style>
""", unsafe_allow_html=True)

# Database Object Structure
DB_OBJECTS = {
    "beneficiary": {
        "Beneficiary": ["beneficiaryFirstName", "beneficiaryLastName", "beneficiaryMiddleName",
                       "beneficiaryGender", "beneficiaryDateOfBirth", "beneficiarySsn",
                       "alienNumber", "beneficiaryCountryOfBirth", "beneficiaryCitizenOfCountry",
                       "maritalStatus", "uscisOnlineAccountNumber"],
        "MailingAddress": ["addressStreet", "addressCity", "addressState", "addressZip", 
                          "addressCountry", "addressAptSteFlrNumber", "inCareOfName"],
        "ContactInfo": ["daytimeTelephoneNumber", "mobileTelephoneNumber", "emailAddress"],
        "PassportDetails": {"Passport": ["passportNumber", "passportIssueCountry", 
                                        "passportIssueDate", "passportExpiryDate"]},
        "VisaDetails": {"Visa": ["currentNonimmigrantStatus", "dateStatusExpires", "visaNumber"]},
        "I94Details": {"I94": ["formI94ArrivalDepartureRecordNumber", "dateOfLastArrival"]}
    },
    "petitioner": {
        "": ["familyName", "givenName", "middleName", "companyOrOrganizationName"],
        "ContactInfo": ["daytimeTelephoneNumber", "mobileTelephoneNumber", "emailAddress"]
    },
    "customer": {
        "": ["customer_name", "customer_tax_id", "customer_type_of_business", 
             "customer_year_established", "customer_gross_annual_income", 
             "customer_net_annual_income", "customer_total_employees"],
        "SignatoryInfo": ["signatory_first_name", "signatory_last_name", "signatory_middle_name",
                         "signatory_job_title", "signatory_work_phone", "signatory_email"],
        "Address": ["address_street", "address_city", "address_state", "address_zip", "address_country"]
    },
    "lca": {
        "Lca": ["lcaNumber", "lcaStartDate", "lcaEndDate", "lcaPositionJobTitle",
               "lcaGrossSalary", "lcaWageUnit"],
        "WorkLocation": ["addressStreet", "addressCity", "addressState", "addressZip"]
    }
}

@dataclass
class PDFField:
    """Represents a field extracted from PDF"""
    widget_name: str
    field_id: str
    part_number: int
    item_number: str
    field_label: str
    field_type: str
    page: int
    value: str = ""
    db_mapping: Optional[str] = None
    is_mapped: bool = False
    to_questionnaire: bool = False
    
    def to_dict(self) -> dict:
        return {
            "id": self.field_id,
            "widget_name": self.widget_name,
            "label": self.field_label,
            "type": self.field_type,
            "part": self.part_number,
            "page": self.page,
            "status": self.get_status(),
            "mapping": self.db_mapping or "",
            "questionnaire": self.to_questionnaire
        }
    
    def get_status(self) -> str:
        if self.is_mapped:
            return "✅ Mapped"
        elif self.to_questionnaire:
            return "📋 Questionnaire"
        else:
            return "⚪ Unmapped"

class USCISExtractor:
    """Main class for extracting and processing USCIS forms"""
    
    def __init__(self):
        self.init_session_state()
        self.db_paths = self._build_db_paths()
    
    def init_session_state(self):
        """Initialize Streamlit session state"""
        if 'fields' not in st.session_state:
            st.session_state.fields = []
        if 'fields_by_part' not in st.session_state:
            st.session_state.fields_by_part = OrderedDict()
        if 'form_info' not in st.session_state:
            st.session_state.form_info = {}
        if 'pdf_processed' not in st.session_state:
            st.session_state.pdf_processed = False
    
    def _build_db_paths(self) -> List[str]:
        """Build list of all database paths"""
        paths = []
        for obj_name, structure in DB_OBJECTS.items():
            for key, fields in structure.items():
                if isinstance(fields, list):
                    prefix = f"{obj_name}.{key}." if key else f"{obj_name}."
                    paths.extend([prefix + field for field in fields])
                elif isinstance(fields, dict):
                    for sub_key, sub_fields in fields.items():
                        prefix = f"{obj_name}.{key}.{sub_key}."
                        paths.extend([prefix + field for field in sub_fields])
        return sorted(paths)
    
    def extract_pdf(self, pdf_file) -> bool:
        """Extract fields from PDF file"""
        try:
            # Reset state
            st.session_state.fields = []
            st.session_state.fields_by_part = OrderedDict()
            
            # Read PDF
            pdf_bytes = pdf_file.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            # Detect form type
            st.session_state.form_info = self._detect_form_type(doc)
            
            # Find all parts
            parts = self._find_parts(doc)
            
            # Extract fields from each part
            all_fields = []
            seen_widgets = set()
            
            progress_bar = st.progress(0)
            total_pages = len(doc)
            
            for page_num in range(total_pages):
                progress_bar.progress((page_num + 1) / total_pages)
                page = doc[page_num]
                
                # Get page text to determine part
                text = page.get_text()
                current_part = self._get_current_part(text, parts, page_num)
                
                # Skip attorney/preparer parts
                if self._is_attorney_part(current_part.get('title', '')):
                    continue
                
                # Extract form fields
                widgets = page.widgets()
                if widgets:
                    for widget in widgets:
                        if not widget.field_name or widget.field_name in seen_widgets:
                            continue
                        
                        seen_widgets.add(widget.field_name)
                        
                        # Create field
                        field = self._create_field(widget, current_part.get('number', 1), page_num + 1)
                        
                        # Auto-move checkboxes to questionnaire
                        if field.field_type in ['checkbox', 'radio']:
                            field.to_questionnaire = True
                        
                        all_fields.append(field)
            
            progress_bar.empty()
            doc.close()
            
            # Sort and store fields
            all_fields.sort(key=lambda f: (f.part_number, f.page))
            st.session_state.fields = all_fields
            
            # Group by part
            for field in all_fields:
                part_key = f"Part {field.part_number}"
                if part_key not in st.session_state.fields_by_part:
                    st.session_state.fields_by_part[part_key] = []
                st.session_state.fields_by_part[part_key].append(field)
            
            st.session_state.pdf_processed = True
            return True
            
        except Exception as e:
            st.error(f"Error extracting PDF: {str(e)}")
            return False
    
    def _detect_form_type(self, doc) -> dict:
        """Detect USCIS form type from PDF"""
        text = doc[0].get_text().upper()
        forms = {
            'I-539': 'Application to Extend/Change Nonimmigrant Status',
            'I-824': 'Application for Action on an Approved Application or Petition',
            'I-90': 'Application to Replace Permanent Resident Card',
            'I-129': 'Petition for a Nonimmigrant Worker',
            'I-485': 'Application to Register Permanent Residence or Adjust Status',
            'I-765': 'Application for Employment Authorization',
            'N-400': 'Application for Naturalization',
            'I-130': 'Petition for Alien Relative',
            'I-140': 'Immigrant Petition for Alien Worker',
            'I-526': 'Immigrant Petition by Alien Investor',
            'I-751': 'Petition to Remove Conditions on Residence'
        }
        
        for form_num, title in forms.items():
            if form_num in text:
                return {'form_number': form_num, 'form_title': title, 'pages': len(doc)}
        
        return {'form_number': 'Unknown', 'form_title': 'Unknown Form', 'pages': len(doc)}
    
    def _find_parts(self, doc) -> dict:
        """Find all parts in the PDF"""
        parts = {}
        
        for page_num in range(len(doc)):
            text = doc[page_num].get_text()
            
            # Find part headers
            matches = re.finditer(r'Part\s+(\d+)\.?\s*([^\n]*)', text, re.IGNORECASE)
            for match in matches:
                part_num = int(match.group(1))
                title = match.group(2).strip()
                
                if part_num not in parts:
                    parts[part_num] = {
                        'number': part_num,
                        'title': title,
                        'start_page': page_num,
                        'pages': []
                    }
                
                parts[part_num]['pages'].append(page_num)
        
        return parts
    
    def _get_current_part(self, text: str, parts: dict, page_num: int) -> dict:
        """Determine which part a page belongs to"""
        for part_num, part_info in sorted(parts.items(), reverse=True):
            if page_num >= part_info['start_page']:
                return part_info
        return {'number': 1, 'title': 'General Information'}
    
    def _is_attorney_part(self, title: str) -> bool:
        """Check if part is for attorney/preparer information"""
        keywords = ['attorney', 'preparer', 'interpreter', 'signature of the person', 
                   'declaration', 'contact information of the person preparing']
        return any(kw in title.lower() for kw in keywords)
    
    def _create_field(self, widget, part_num: int, page: int) -> PDFField:
        """Create PDFField object from widget"""
        # Extract field info
        field_name = widget.field_name
        field_type = self._get_field_type(widget.field_type)
        
        # Generate field ID
        clean_name = re.sub(r'[^\w]', '_', field_name)[:30]
        field_id = f"P{part_num}_{clean_name}"
        
        # Extract label
        label = self._extract_label(field_name)
        
        # Determine item number
        item_match = re.search(r'(\d+[a-z]?)', field_name)
        item_number = item_match.group(1) if item_match else "1"
        
        return PDFField(
            widget_name=field_name,
            field_id=field_id,
            part_number=part_num,
            item_number=item_number,
            field_label=label,
            field_type=field_type,
            page=page,
            value=widget.field_value or ''
        )
    
    def _get_field_type(self, widget_type: int) -> str:
        """Get field type from widget type number"""
        types = {
            1: "button", 
            2: "checkbox", 
            3: "radio", 
            4: "text", 
            5: "dropdown", 
            6: "list", 
            7: "signature"
        }
        return types.get(widget_type, "text")
    
    def _extract_label(self, field_name: str) -> str:
        """Extract human-readable label from field name"""
        # Clean field name
        clean = re.sub(r'form1\[0\]\.|#subform\[\d+\]\.|Page\d+\[0\]\.', '', field_name)
        clean = re.sub(r'\[\d+\]', '', clean)
        clean = clean.strip('._[]')
        
        # Common mappings
        mappings = {
            'familyname': 'Family Name (Last Name)',
            'givenname': 'Given Name (First Name)',
            'middlename': 'Middle Name',
            'anumber': 'Alien Registration Number',
            'alienregistrationnumber': 'Alien Registration Number (A-Number)',
            'uscisaccount': 'USCIS Online Account Number',
            'dateofbirth': 'Date of Birth',
            'ssn': 'Social Security Number',
            'socialsecuritynumber': 'U.S. Social Security Number',
            'passport': 'Passport Number',
            'passportnumber': 'Passport Number',
            'street': 'Street Address',
            'streetnumber': 'Street Number and Name',
            'city': 'City or Town',
            'state': 'State',
            'zip': 'ZIP Code',
            'zipcode': 'ZIP Code',
            'email': 'Email Address',
            'emailaddress': 'Email Address',
            'phone': 'Phone Number',
            'telephone': 'Telephone Number',
            'daytimephone': 'Daytime Telephone Number',
            'mobilephone': 'Mobile Telephone Number',
            'country': 'Country',
            'countryofbirth': 'Country of Birth',
            'countryofcitizenship': 'Country of Citizenship',
            'gender': 'Gender',
            'maritalstatus': 'Marital Status',
            'currentstatus': 'Current Nonimmigrant Status',
            'ein': 'Federal Employer Identification Number (FEIN)',
            'companyname': 'Company or Organization Name',
            'jobtitle': 'Job Title',
            'typeofbusiness': 'Type of Business',
            'yearestablished': 'Year Established',
            'grossannualincome': 'Gross Annual Income',
            'netannualincome': 'Net Annual Income',
            'currentemployees': 'Current Number of Employees'
        }
        
        clean_lower = clean.lower().replace('_', '').replace('-', '').replace(' ', '')
        
        # Check for exact matches first
        if clean_lower in mappings:
            return mappings[clean_lower]
        
        # Check for partial matches
        for key, label in mappings.items():
            if key in clean_lower or clean_lower in key:
                return label
        
        # Convert to readable format
        label = re.sub(r'([a-z])([A-Z])', r'\1 \2', clean)
        label = label.replace('_', ' ').replace('-', ' ')
        
        # Title case
        label = ' '.join(word.capitalize() for word in label.split())
        
        return label
    
    def auto_map_fields(self) -> int:
        """Automatically map fields to database paths"""
        mapped_count = 0
        
        for field in st.session_state.fields:
            if not field.is_mapped and not field.to_questionnaire and field.field_type == 'text':
                # Try to auto-map
                label_lower = field.field_label.lower()
                label_words = set(label_lower.split())
                
                best_match = None
                best_score = 0
                
                for path in self.db_paths:
                    path_parts = path.lower().split('.')
                    path_words = set()
                    for part in path_parts:
                        path_words.update(re.findall(r'[a-z]+', part))
                    
                    # Calculate match score
                    common_words = label_words & path_words
                    if common_words:
                        score = len(common_words) / max(len(label_words), len(path_words))
                        if score > best_score:
                            best_score = score
                            best_match = path
                
                # Apply mapping if good match found
                if best_match and best_score > 0.3:
                    field.db_mapping = best_match
                    field.is_mapped = True
                    mapped_count += 1
        
        return mapped_count
    
    def generate_typescript(self) -> str:
        """Generate TypeScript mapping file"""
        fields = st.session_state.fields
        form_name = st.session_state.form_info.get('form_number', 'Form').replace('-', '')
        
        # Group fields
        db_fields = defaultdict(list)
        quest_fields = []
        
        for field in fields:
            if field.is_mapped:
                obj = field.db_mapping.split('.')[0]
                db_fields[obj].append(field)
            elif field.to_questionnaire:
                quest_fields.append(field)
        
        # Build output
        ts = f"// {st.session_state.form_info.get('form_number')} Field Mappings\n"
        ts += f"// Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        ts += f"export const {form_name} = {{\n"
        ts += f'  "formname": "{form_name}",\n'
        
        # Database mappings
        for obj, fields_list in sorted(db_fields.items()):
            ts += f'  "{obj}Data": {{\n'
            for field in fields_list:
                path = field.db_mapping
                suffix = ":TextBox" if field.field_type == "text" else f":{field.field_type.title()}Box"
                ts += f'    "{field.field_id}": "{path}{suffix}",\n'
            ts += "  },\n"
        
        # Questionnaire
        if quest_fields:
            ts += '  "questionnaireData": {\n'
            for field in quest_fields:
                ts += f'    "{field.field_id}": {{\n'
                ts += f'      "description": "{field.field_label}",\n'
                ts += f'      "type": "{field.field_type}",\n'
                ts += f'      "part": {field.part_number},\n'
                ts += f'      "page": {field.page}\n'
                ts += "    },\n"
            ts += "  },\n"
        
        # Default data (empty for now)
        ts += '  "defaultData": {},\n'
        ts += '  "conditionalData": {},\n'
        ts += '  "attorneyData": null,\n'
        ts += f'  "pdfName": "{st.session_state.form_info.get("form_number", "Unknown")}",\n'
        ts += '  "caseData": {}\n'
        
        ts += "};\n"
        return ts
    
    def generate_json(self) -> str:
        """Generate JSON questionnaire file"""
        quest_fields = [f for f in st.session_state.fields if f.to_questionnaire and not f.is_mapped]
        
        data = {
            "form": st.session_state.form_info.get('form_number'),
            "generated": datetime.now().isoformat(),
            "controls": []
        }
        
        # Group by part
        parts = defaultdict(list)
        for field in quest_fields:
            parts[field.part_number].append(field)
        
        for part_num, fields in sorted(parts.items()):
            part_data = {
                "group_name": f"Part {part_num}",
                "group_key": f"part_{part_num}",
                "group_definition": []
            }
            
            for field in fields:
                field_def = {
                    "name": field.field_id,
                    "label": field.field_label,
                    "type": field.field_type,
                    "showInTable": True,
                    "validators": {},
                    "group": f"Part {part_num}",
                    "style": {"col": "6"}
                }
                
                if field.field_type == "text":
                    field_def["validators"]["required"] = True
                
                part_data["group_definition"].append(field_def)
            
            data["controls"].append(part_data)
        
        return json.dumps(data, indent=2)

def main():
    """Main Streamlit application"""
    # Initialize extractor
    extractor = USCISExtractor()
    
    # Header
    st.markdown("<h1>USCIS Form Reader & Mapper</h1>", unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Extract and map PDF form fields to database objects with intelligent automation</p>', unsafe_allow_html=True)
    
    # Main layout
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("### 📄 Upload USCIS Form")
        
        uploaded_file = st.file_uploader(
            "Choose a USCIS form PDF",
            type=['pdf'],
            help="Supports all USCIS forms (I-90, I-129, I-485, etc.)"
        )
        
        if uploaded_file is not None:
            if st.button("🔍 Extract Fields", type="primary", use_container_width=True):
                with st.spinner("Extracting fields from PDF..."):
                    if extractor.extract_pdf(uploaded_file):
                        st.success(f"✅ Successfully extracted {len(st.session_state.fields)} fields!")
                        st.rerun()
        
        # Form info
        if st.session_state.pdf_processed:
            st.markdown("### 📊 Form Information")
            info_cols = st.columns(2)
            with info_cols[0]:
                st.metric("Form Type", st.session_state.form_info.get('form_number', 'Unknown'))
                st.metric("Total Pages", st.session_state.form_info.get('pages', 0))
            with info_cols[1]:
                st.metric("Fields Found", len(st.session_state.fields))
                st.metric("Parts Detected", len(st.session_state.fields_by_part))
    
    with col2:
        if st.session_state.pdf_processed:
            st.markdown("### 🎯 Field Mapping Statistics")
            
            # Calculate stats
            total = len(st.session_state.fields)
            mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
            questionnaire = sum(1 for f in st.session_state.fields if f.to_questionnaire and not f.is_mapped)
            unmapped = total - mapped - questionnaire
            
            # Display metrics
            metric_cols = st.columns(4)
            with metric_cols[0]:
                st.metric("Total Fields", total)
            with metric_cols[1]:
                st.metric("Mapped", mapped)
            with metric_cols[2]:
                st.metric("Questionnaire", questionnaire)
            with metric_cols[3]:
                st.metric("Unmapped", unmapped)
            
            # Progress bar
            if total > 0:
                progress = (mapped + questionnaire) / total
                st.progress(progress, text=f"Completion: {progress*100:.1f}%")
            
            # Quick actions
            st.markdown("### ⚡ Quick Actions")
            action_cols = st.columns(2)
            
            with action_cols[0]:
                if st.button("⚡ Auto-map Common Fields", use_container_width=True):
                    count = extractor.auto_map_fields()
                    st.success(f"✅ Auto-mapped {count} fields!")
                    st.rerun()
            
            with action_cols[1]:
                if st.button("📋 All Unmapped → Questionnaire", use_container_width=True):
                    count = 0
                    for field in st.session_state.fields:
                        if not field.is_mapped and not field.to_questionnaire:
                            field.to_questionnaire = True
                            count += 1
                    st.success(f"✅ Moved {count} fields to questionnaire!")
                    st.rerun()
    
    # Fields section
    if st.session_state.pdf_processed:
        st.markdown("---")
        st.markdown("### 📝 Extracted Fields")
        
        # Search
        search_query = st.text_input("🔍 Search fields...", placeholder="Enter field name or label")
        
        # Tabs for parts
        if st.session_state.fields_by_part:
            tabs = st.tabs(list(st.session_state.fields_by_part.keys()))
            
            for idx, (part_name, fields) in enumerate(st.session_state.fields_by_part.items()):
                with tabs[idx]:
                    # Filter fields based on search
                    filtered_fields = fields
                    if search_query:
                        query_lower = search_query.lower()
                        filtered_fields = [f for f in fields if query_lower in f.field_label.lower() or query_lower in f.widget_name.lower()]
                    
                    if not filtered_fields:
                        st.info("No fields found matching your search.")
                        continue
                    
                    # Display fields as dataframe for better performance
                    fields_data = []
                    for field in filtered_fields:
                        fields_data.append({
                            "Label": field.field_label,
                            "Type": field.field_type,
                            "Page": field.page,
                            "Status": field.get_status(),
                            "field_obj": field  # Keep reference for later
                        })
                    
                    df = pd.DataFrame(fields_data)
                    
                    # Display fields with mapping controls
                    for idx, row in df.iterrows():
                        field = row['field_obj']
                        
                        with st.container():
                            col1, col2, col3 = st.columns([3, 3, 1])
                            
                            with col1:
                                st.markdown(f"**{field.field_label}**")
                                st.caption(f"Type: {field.field_type} | Page: {field.page}")
                            
                            with col2:
                                if field.field_type == 'text' and not field.to_questionnaire:
                                    # Database mapping dropdown
                                    mapping_key = f"mapping_{field.field_id}"
                                    current_value = field.db_mapping or ""
                                    
                                    options = [""] + ["📋 Move to Questionnaire"] + extractor.db_paths
                                    
                                    # Find index of current value
                                    try:
                                        index = options.index(current_value) if current_value in options else 0
                                    except:
                                        index = 0
                                    
                                    selected = st.selectbox(
                                        "Map to",
                                        options,
                                        index=index,
                                        key=mapping_key,
                                        label_visibility="collapsed"
                                    )
                                    
                                    if selected != current_value:
                                        if selected == "📋 Move to Questionnaire":
                                            field.to_questionnaire = True
                                            field.is_mapped = False
                                            field.db_mapping = None
                                        elif selected:
                                            field.db_mapping = selected
                                            field.is_mapped = True
                                            field.to_questionnaire = False
                                        else:
                                            field.db_mapping = None
                                            field.is_mapped = False
                                        st.rerun()
                                else:
                                    # Questionnaire checkbox
                                    quest_key = f"quest_{field.field_id}"
                                    include = st.checkbox(
                                        "Include in Questionnaire",
                                        value=field.to_questionnaire,
                                        key=quest_key
                                    )
                                    if include != field.to_questionnaire:
                                        field.to_questionnaire = include
                                        st.rerun()
                            
                            with col3:
                                status = field.get_status()
                                if "Mapped" in status:
                                    st.success(status)
                                elif "Questionnaire" in status:
                                    st.warning(status)
                                else:
                                    st.info(status)
        
        # Export section
        st.markdown("---")
        st.markdown("### 📥 Export Mappings")
        
        export_cols = st.columns(2)
        
        with export_cols[0]:
            st.markdown("#### TypeScript Export")
            if st.button("📄 Generate TypeScript", use_container_width=True):
                ts_content = extractor.generate_typescript()
                st.code(ts_content, language="typescript")
                
                # Download button
                st.download_button(
                    label="💾 Download TypeScript File",
                    data=ts_content,
                    file_name=f"{st.session_state.form_info.get('form_number', 'form')}.ts",
                    mime="text/plain",
                    use_container_width=True
                )
        
        with export_cols[1]:
            st.markdown("#### JSON Export")
            if st.button("📋 Generate JSON", use_container_width=True):
                json_content = extractor.generate_json()
                st.code(json_content, language="json")
                
                # Download button
                st.download_button(
                    label="💾 Download JSON File",
                    data=json_content,
                    file_name=f"{st.session_state.form_info.get('form_number', 'form')}.json",
                    mime="application/json",
                    use_container_width=True
                )
    
    # Sidebar
    with st.sidebar:
        st.markdown("### 📚 About")
        st.markdown("""
        This tool extracts fields from USCIS PDF forms and maps them to database objects.
        
        **Features:**
        - 🔍 Automatic field extraction
        - 🎯 Smart field mapping
        - 📋 Questionnaire management
        - 📄 TypeScript/JSON export
        - ⚡ Auto-mapping capabilities
        
        **Supported Forms:**
        - I-90 (Green Card Replacement)
        - I-129 (Nonimmigrant Worker)
        - I-485 (Adjustment of Status)
        - I-765 (Employment Authorization)
        - And many more...
        """)
        
        st.markdown("---")
        st.markdown("### 🔧 Settings")
        
        if st.button("🔄 Reset Application", use_container_width=True):
            for key in ['fields', 'fields_by_part', 'form_info', 'pdf_processed']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

if __name__ == "__main__":
    main()
