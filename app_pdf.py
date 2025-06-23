import streamlit as st
import json
import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from collections import OrderedDict, defaultdict
import pandas as pd

# PDF library imports
PDF_AVAILABLE = False
PYMUPDF_AVAILABLE = False

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
    PDF_AVAILABLE = True
except ImportError:
    pass

if not PDF_AVAILABLE:
    try:
        import PyPDF2
        from PyPDF2 import PdfReader
        PDF_AVAILABLE = True
    except ImportError:
        pass

# Page configuration
st.set_page_config(
    page_title="USCIS Universal Form Mapper",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Database Object Structure Reference
DB_OBJECTS = {
    "attorney": {
        "attorneyInfo": ["firstName", "lastName", "middleName", "workPhone", "mobilePhone", 
                        "emailAddress", "faxNumber", "stateBarNumber", "licensingAuthority", 
                        "stateOfHighestCourt", "nameOfHighestCourt", "signature"],
        "address": ["addressStreet", "addressCity", "addressState", "addressZip", 
                   "addressCountry", "addressNumber", "addressType"]
    },
    "attorneyLawfirmDetails": {
        "lawfirmDetails": ["lawFirmName", "lawFirmFein"],
        "address": ["addressStreet", "addressCity", "addressState", "addressZip", 
                   "addressCountry", "addressNumber", "addressType"]
    },
    "beneficiary": {
        "Beneficiary": ["beneficiaryFirstName", "beneficiaryLastName", "beneficiaryMiddleName",
                       "beneficiaryGender", "beneficiaryDateOfBirth", "beneficiarySsn",
                       "alienNumber", "beneficiaryCountryOfBirth", "beneficiaryProvinceOfBirth",
                       "stateBirth", "beneficiaryCitizenOfCountry", "beneficiaryCellNumber",
                       "beneficiaryHomeNumber", "beneficiaryWorkNumber", "beneficiaryPrimaryEmailAddress",
                       "maritalStatus", "fatherFirstName", "fatherLastName", "motherFirstName", 
                       "motherLastName"],
        "HomeAddress": ["addressStreet", "addressCity", "addressState", "addressZip", 
                       "addressCountry", "addressNumber", "addressType"],
        "WorkAddress": ["addressStreet", "addressCity", "addressState", "addressZip", 
                       "addressCountry", "addressNumber", "addressType"],
        "ForeignAddress": ["addressStreet", "addressCity", "addressState", "addressZip", 
                          "addressCountry", "addressNumber", "addressType"],
        "PassportDetails": {"Passport": ["passportNumber", "passportIssueCountry", 
                                        "passportIssueDate", "passportExpiryDate"]},
        "VisaDetails": {"Visa": ["visaStatus", "visaExpiryDate", "visaConsulateCity", 
                                "visaConsulateCountry", "visaNumber", "f1SevisNumber", 
                                "eligibilityCategory"]},
        "I94Details": {"I94": ["i94Number", "i94ArrivalDate", "i94ExpiryDate", 
                              "i94DepartureDate", "placeLastArrival", "statusAtArrival"]},
        "H1bDetails": {"H1b": ["h1bReceiptNumber", "h1bStartDate", "h1bExpiryDate", 
                              "h1bType", "h1bStatus"]},
        "EducationDetails": {"BeneficiaryEducation": ["universityName", "degreeType", 
                                                     "majorFieldOfStudy", "graduationYear"]}
    },
    "customer": {
        "": ["customer_name", "customer_type_of_business", "customer_tax_id", "customer_naics_code",
             "customer_total_employees", "customer_total_h1b_employees", "customer_gross_annual_income",
             "customer_net_annual_income", "customer_year_established", "customer_dot_code",
             "h1_dependent_employer", "willful_violator", "higher_education_institution",
             "nonprofit_organization", "nonprofit_research_organization", "cap_exempt_institution",
             "primary_secondary_education_institution", "nonprofit_clinical_institution"],
        "signatory": ["signatory_first_name", "signatory_last_name", "signatory_middle_name",
                     "signatory_job_title", "signatory_work_phone", "signatory_mobile_phone",
                     "signatory_email_id", "signatory_digital_signature"],
        "address": ["address_street", "address_city", "address_state", "address_zip",
                   "address_country", "address_number", "address_type"]
    },
    "case": {
        "": ["caseType", "caseSubType", "h1BPetitionType", "premiumProcessing", 
             "h1BRegistrationNumber", "h4Filing", "carrier", "serviceCenter"]
    },
    "lca": {
        "": ["positionJobTitle", "inhouseProject", "endClientName", "jobLocation",
             "grossSalary", "swageUnit", "startDate", "endDate", "prevailingWateRate",
             "pwageUnit", "socOnetOesCode", "socOnetOesTitle", "fullTimePosition",
             "wageLevel", "sourceYear", "lcaNumber"],
        "Addresses": ["addressStreet", "addressCity", "addressState", "addressZip",
                     "addressCounty", "addressType", "addressNumber"]
    }
}

# Common field patterns for automatic mapping
FIELD_PATTERNS = {
    "lastName": r"(last.*name|family.*name|surname)",
    "firstName": r"(first.*name|given.*name)",
    "middleName": r"(middle.*name|middle.*initial)",
    "dateOfBirth": r"(date.*birth|dob|birth.*date)",
    "alienNumber": r"(alien.*number|a.*number|uscis.*number)",
    "ssn": r"(social.*security|ssn)",
    "phone": r"(phone|telephone|contact.*number)",
    "email": r"(email|e-mail|electronic.*mail)",
    "street": r"(street|address.*1|address.*line.*1)",
    "city": r"(city|town)",
    "state": r"(state|province)",
    "zip": r"(zip|postal.*code)",
    "country": r"(country|nation)",
    "gender": r"(gender|sex)",
    "barNumber": r"(bar.*number|state.*bar|license.*number)",
    "receiptNumber": r"(receipt.*number|case.*number)",
    "signature": r"(signature|sign)",
    "date": r"(date|mm/dd/yyyy)"
}

# CSS Styles
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1e3c72, #2a5298);
        color: white;
        padding: 25px;
        border-radius: 10px;
        margin-bottom: 25px;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    .part-header {
        background: #f0f8ff;
        padding: 15px;
        border-left: 5px solid #1e3c72;
        margin: 15px 0;
        font-size: 1.1em;
        font-weight: bold;
        border-radius: 0 5px 5px 0;
    }
    
    .field-card {
        background: white;
        border: 1px solid #e0e0e0;
        padding: 12px;
        margin: 8px 0;
        border-radius: 8px;
        transition: all 0.3s ease;
    }
    
    .field-card:hover {
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        border-color: #1e3c72;
    }
    
    .field-name {
        font-family: 'Courier New', monospace;
        font-size: 0.85em;
        color: #495057;
        background: #f8f9fa;
        padding: 4px 8px;
        border-radius: 3px;
        word-break: break-all;
    }
    
    .mapping-info {
        font-family: monospace;
        font-size: 0.85em;
        color: #0066cc;
        background: #e7f3ff;
        padding: 4px 8px;
        border-radius: 3px;
    }
    
    .mapping-score {
        font-size: 2em;
        font-weight: bold;
        text-align: center;
        padding: 20px;
    }
    
    .status-mapped { 
        color: #28a745; 
        font-weight: bold;
        padding: 2px 8px;
        background: #d4edda;
        border-radius: 3px;
    }
    .status-questionnaire { 
        color: #17a2b8; 
        font-weight: bold;
        padding: 2px 8px;
        background: #d1ecf1;
        border-radius: 3px;
    }
    .status-unmapped { 
        color: #dc3545; 
        font-weight: bold;
        padding: 2px 8px;
        background: #f8d7da;
        border-radius: 3px;
    }
    
    .db-object-tag {
        display: inline-block;
        padding: 3px 8px;
        margin: 2px;
        background: #6c757d;
        color: white;
        border-radius: 3px;
        font-size: 0.8em;
    }
    
    .metric-card {
        background: white;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        text-align: center;
        margin: 10px 0;
    }
    
    .metric-value {
        font-size: 2.5em;
        font-weight: bold;
        color: #1e3c72;
    }
    
    .metric-label {
        color: #6c757d;
        font-size: 0.9em;
        margin-top: 5px;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
def init_session_state():
    if 'form_type' not in st.session_state:
        st.session_state.form_type = None
    if 'pdf_fields' not in st.session_state:
        st.session_state.pdf_fields = []
    if 'fields_by_part' not in st.session_state:
        st.session_state.fields_by_part = OrderedDict()
    if 'mapped_fields' not in st.session_state:
        st.session_state.mapped_fields = {}
    if 'questionnaire_fields' not in st.session_state:
        st.session_state.questionnaire_fields = {}
    if 'unmapped_fields' not in st.session_state:
        st.session_state.unmapped_fields = []
    if 'mapping_score' not in st.session_state:
        st.session_state.mapping_score = 0
    if 'field_mappings' not in st.session_state:
        st.session_state.field_mappings = {}

init_session_state()

def extract_pdf_fields(pdf_file):
    """Extract all fields from PDF"""
    fields = []
    
    if PYMUPDF_AVAILABLE:
        try:
            pdf_bytes = pdf_file.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            field_index = 0
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                for widget in page.widgets():
                    if widget.field_name:
                        field_index += 1
                        
                        # Determine field type
                        field_type = "TextBox"
                        if hasattr(widget, 'field_type'):
                            if widget.field_type == 1:
                                field_type = "CheckBox"
                            elif widget.field_type == 2:
                                field_type = "RadioButton"
                        
                        field_info = {
                            'index': field_index,
                            'raw_name': widget.field_name,
                            'type': field_type,
                            'value': widget.field_value or '',
                            'page': page_num + 1,
                            'part': extract_part_from_name(widget.field_name),
                            'item': extract_item_from_name(widget.field_name),
                            'description': generate_field_description(widget.field_name)
                        }
                        
                        fields.append(field_info)
            
            doc.close()
            
        except Exception as e:
            st.error(f"Error extracting PDF: {str(e)}")
    
    return fields

def extract_part_from_name(field_name):
    """Extract part number from field name"""
    # Try different patterns
    patterns = [
        r'Part(\d+)',
        r'Pt(\d+)',
        r'P(\d+)_',
        r'part(\d+)',
        r'Section(\d+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, field_name, re.IGNORECASE)
        if match:
            return f"Part {match.group(1)}"
    
    # Check for other sections
    if 'signature' in field_name.lower():
        return "Signatures"
    elif 'preparer' in field_name.lower():
        return "Preparer"
    elif 'attorney' in field_name.lower():
        return "Attorney"
    
    return "Other"

def extract_item_from_name(field_name):
    """Extract item number from field name"""
    patterns = [
        r'Item(\d+[a-z]?)',
        r'Line(\d+[a-z]?)',
        r'_(\d+[a-z]?)_',
        r'\.(\d+[a-z]?)\.',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, field_name, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return ""

def generate_field_description(field_name):
    """Generate human-readable description from field name"""
    # Clean up the field name
    desc = field_name
    
    # Remove common prefixes
    desc = re.sub(r'^form\[\d+\]\.', '', desc)
    desc = re.sub(r'#subform\[\d+\]\.', '', desc)
    desc = re.sub(r'\[\d+\]', '', desc)
    
    # Extract meaningful parts
    if '_' in desc:
        parts = desc.split('_')
        desc = ' '.join([p for p in parts if p and not p.isdigit()])
    
    # Convert camelCase to spaces
    desc = re.sub(r'([a-z])([A-Z])', r'\1 \2', desc)
    
    # Clean up
    desc = desc.replace('Pt', 'Part').replace('Ln', 'Line')
    desc = ' '.join(desc.split())
    
    return desc.title()

def organize_by_parts(fields):
    """Organize fields by parts"""
    parts = OrderedDict()
    
    # Group fields by part
    for field in fields:
        part = field['part']
        if part not in parts:
            parts[part] = []
        parts[part].append(field)
    
    # Sort parts
    sorted_parts = OrderedDict()
    
    # First add numbered parts in order
    for i in range(1, 20):
        part_name = f"Part {i}"
        if part_name in parts:
            sorted_parts[part_name] = parts[part_name]
    
    # Then add special sections
    for section in ["Attorney", "Preparer", "Signatures", "Other"]:
        if section in parts:
            sorted_parts[section] = parts[section]
    
    return sorted_parts

def suggest_mapping(field_name, field_type):
    """Suggest database mapping based on field name and patterns"""
    field_lower = field_name.lower()
    
    # Check each pattern
    for pattern_key, pattern in FIELD_PATTERNS.items():
        if re.search(pattern, field_lower):
            # Find matching database fields
            for obj_name, obj_structure in DB_OBJECTS.items():
                if isinstance(obj_structure, dict):
                    for sub_obj, fields in obj_structure.items():
                        if isinstance(fields, list):
                            for field in fields:
                                if pattern_key in field.lower():
                                    if sub_obj:
                                        return f"{obj_name}.{sub_obj}.{field}:{field_type}"
                                    else:
                                        return f"{obj_name}.{field}:{field_type}"
    
    return None

def calculate_mapping_score():
    """Calculate overall mapping score"""
    total_fields = len(st.session_state.pdf_fields)
    mapped_fields = len(st.session_state.mapped_fields)
    questionnaire_fields = len(st.session_state.questionnaire_fields)
    
    if total_fields == 0:
        return 0
    
    # Mapped fields get 100%, questionnaire fields get 50%
    score = ((mapped_fields * 100) + (questionnaire_fields * 50)) / total_fields
    return round(score, 1)

def display_part_summary(part_name, fields):
    """Display summary of fields in a part"""
    col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
    
    with col1:
        st.markdown(f'<div class="part-header">{part_name}</div>', unsafe_allow_html=True)
    
    # Count field statuses
    mapped = sum(1 for f in fields if f['raw_name'] in st.session_state.mapped_fields)
    questionnaire = sum(1 for f in fields if f['raw_name'] in st.session_state.questionnaire_fields)
    unmapped = len(fields) - mapped - questionnaire
    
    with col2:
        st.metric("Total", len(fields))
    with col3:
        st.metric("Mapped", mapped)
    with col4:
        st.metric("Unmapped", unmapped)
    
    # Display fields in a clean format
    for field in fields:
        with st.container():
            col1, col2, col3 = st.columns([5, 3, 2])
            
            with col1:
                item_info = f"Item {field.get('item', '')}" if field.get('item') else ""
                st.markdown(f"**{item_info}** - {field['description']}")
                st.caption(f"Field: `{field['raw_name']}` | Type: {field['type']}")
            
            with col2:
                if field['raw_name'] in st.session_state.mapped_fields:
                    mapping = st.session_state.mapped_fields[field['raw_name']]
                    st.markdown(f'<div class="mapping-info">{mapping}</div>', unsafe_allow_html=True)
                elif field['raw_name'] in st.session_state.questionnaire_fields:
                    st.markdown('<span class="status-questionnaire">In Questionnaire</span>', unsafe_allow_html=True)
                else:
                    st.markdown('<span class="status-unmapped">Not Mapped</span>', unsafe_allow_html=True)
            
            with col3:
                # Quick action buttons
                if field['raw_name'] not in st.session_state.mapped_fields:
                    if st.button("Map", key=f"map_{field['index']}"):
                        st.session_state.selected_field = field
                        st.session_state.show_mapping_dialog = True

def display_mapping_interface():
    """Display the mapping interface"""
    st.header("Field Mapping Configuration")
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        filter_part = st.selectbox("Filter by Part", ["All"] + list(st.session_state.fields_by_part.keys()))
    
    with col2:
        filter_status = st.selectbox("Filter by Status", ["All", "Mapped", "Questionnaire", "Unmapped"])
    
    with col3:
        search_term = st.text_input("Search fields", placeholder="Enter field name or description")
    
    # Display fields with mapping interface
    for part_name, fields in st.session_state.fields_by_part.items():
        if filter_part != "All" and part_name != filter_part:
            continue
        
        filtered_fields = []
        for field in fields:
            # Apply status filter
            if filter_status == "Mapped" and field['raw_name'] not in st.session_state.mapped_fields:
                continue
            elif filter_status == "Questionnaire" and field['raw_name'] not in st.session_state.questionnaire_fields:
                continue
            elif filter_status == "Unmapped" and (field['raw_name'] in st.session_state.mapped_fields or field['raw_name'] in st.session_state.questionnaire_fields):
                continue
            
            # Apply search filter
            if search_term and search_term.lower() not in field['raw_name'].lower() and search_term.lower() not in field['description'].lower():
                continue
            
            filtered_fields.append(field)
        
        if filtered_fields:
            st.subheader(part_name)
            
            for field in filtered_fields:
                with st.expander(f"{field['description']} ({field['raw_name']})", expanded=False):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Type:** {field['type']}")
                        st.write(f"**Page:** {field['page']}")
                        st.write(f"**Current Mapping:** {st.session_state.mapped_fields.get(field['raw_name'], 'None')}")
                    
                    with col2:
                        # Mapping options
                        mapping_type = st.radio(
                            "Mapping Type",
                            ["Database Field", "Questionnaire", "Default Value", "Skip"],
                            key=f"type_{field['index']}"
                        )
                        
                        if mapping_type == "Database Field":
                            # Database object selection
                            db_obj = st.selectbox(
                                "Database Object",
                                list(DB_OBJECTS.keys()),
                                key=f"obj_{field['index']}"
                            )
                            
                            # Sub-object selection
                            sub_objects = list(DB_OBJECTS[db_obj].keys())
                            if sub_objects:
                                sub_obj = st.selectbox(
                                    "Sub-Object",
                                    sub_objects,
                                    key=f"subobj_{field['index']}"
                                )
                                
                                # Field selection
                                if isinstance(DB_OBJECTS[db_obj][sub_obj], list):
                                    db_field = st.selectbox(
                                        "Field",
                                        DB_OBJECTS[db_obj][sub_obj],
                                        key=f"field_{field['index']}"
                                    )
                                    
                                    if st.button("Apply Mapping", key=f"apply_{field['index']}"):
                                        if sub_obj:
                                            mapping = f"{db_obj}.{sub_obj}.{db_field}:{field['type']}"
                                        else:
                                            mapping = f"{db_obj}.{db_field}:{field['type']}"
                                        st.session_state.mapped_fields[field['raw_name']] = mapping
                                        st.rerun()
                        
                        elif mapping_type == "Questionnaire":
                            quest_name = st.text_input(
                                "Questionnaire Field Name",
                                value=f"q_{field['index']}",
                                key=f"quest_{field['index']}"
                            )
                            
                            if st.button("Add to Questionnaire", key=f"addquest_{field['index']}"):
                                st.session_state.questionnaire_fields[field['raw_name']] = {
                                    'name': quest_name,
                                    'type': field['type'],
                                    'description': field['description']
                                }
                                st.rerun()

def generate_questionnaire_json():
    """Generate questionnaire JSON for unmapped fields"""
    controls = []
    
    for field_name, field_info in st.session_state.questionnaire_fields.items():
        control = {
            "name": field_info['name'],
            "label": field_info['description'],
            "type": "text" if field_info['type'] == "TextBox" else "colorSwitch",
            "validators": {"required": False},
            "style": {"col": "12"}
        }
        controls.append(control)
    
    return json.dumps({"controls": controls}, indent=2)

def generate_typescript_mapping():
    """Generate TypeScript mapping file"""
    form_name = st.session_state.form_type or "UnknownForm"
    
    # Group mappings by category
    customer_data = {}
    beneficiary_data = {}
    attorney_data = {}
    case_data = {}
    lca_data = {}
    questionnaire_data = {}
    default_data = {}
    
    # Process mapped fields
    for field_name, mapping in st.session_state.mapped_fields.items():
        parts = mapping.split('.')
        
        if parts[0] == 'customer':
            customer_data[field_name] = mapping
        elif parts[0] == 'beneficiary':
            beneficiary_data[field_name] = mapping
        elif parts[0] == 'attorney' or parts[0] == 'attorneyLawfirmDetails':
            attorney_data[field_name] = mapping
        elif parts[0] == 'case':
            case_data[field_name] = mapping
        elif parts[0] == 'lca':
            lca_data[field_name] = mapping
    
    # Process questionnaire fields
    for field_name, field_info in st.session_state.questionnaire_fields.items():
        questionnaire_data[field_info['name']] = f"{field_info['name']}:{field_info['type']}"
    
    ts_content = f"""export const {form_name} = {{
    "formname": "{form_name}",
    "customerData": {json.dumps(customer_data, indent=8) if customer_data else 'null'},
    "beneficiaryData": {json.dumps(beneficiary_data, indent=8) if beneficiary_data else 'null'},
    "attorneyData": {json.dumps(attorney_data, indent=8) if attorney_data else 'null'},
    "questionnaireData": {json.dumps(questionnaire_data, indent=8) if questionnaire_data else '{}'},
    "defaultData": {json.dumps(default_data, indent=8) if default_data else '{}'},
    "conditionalData": {{}},
    "pdfName": "{form_name}",
    "caseData": {json.dumps(case_data, indent=8) if case_data else 'null'},
    "lcaData": {json.dumps(lca_data, indent=8) if lca_data else 'null'}
}}"""
    
    return ts_content

# Main Application
def main():
    st.markdown('<div class="main-header"><h1>🏛️ USCIS Universal Form Mapper</h1><p>Map any USCIS form to your database structure</p></div>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.header("📊 Mapping Overview")
        
        if st.session_state.pdf_fields:
            # Metrics
            total = len(st.session_state.pdf_fields)
            mapped = len(st.session_state.mapped_fields)
            questionnaire = len(st.session_state.questionnaire_fields)
            unmapped = total - mapped - questionnaire
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown('<div class="metric-card"><div class="metric-value">{}</div><div class="metric-label">Total Fields</div></div>'.format(total), unsafe_allow_html=True)
            with col2:
                st.markdown('<div class="metric-card"><div class="metric-value">{}</div><div class="metric-label">Mapped</div></div>'.format(mapped), unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown('<div class="metric-card"><div class="metric-value">{}</div><div class="metric-label">Questionnaire</div></div>'.format(questionnaire), unsafe_allow_html=True)
            with col2:
                st.markdown('<div class="metric-card"><div class="metric-value">{}</div><div class="metric-label">Unmapped</div></div>'.format(unmapped), unsafe_allow_html=True)
            
            # Mapping Score
            score = calculate_mapping_score()
            st.session_state.mapping_score = score
            
            st.markdown("---")
            st.markdown(f'<div class="mapping-score">Mapping Score<br/>{score}%</div>', unsafe_allow_html=True)
            
            # Progress bar
            st.progress(score / 100)
    
    # Main tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📤 Upload & Extract",
        "📋 Fields by Parts",
        "🔗 Field Mapping",
        "❓ Questionnaire Builder",
        "📥 Export"
    ])
    
    # Tab 1: Upload & Extract
    with tab1:
        st.header("Upload USCIS Form")
        
        # Form type selection
        col1, col2 = st.columns(2)
        
        with col1:
            form_types = ["G-28", "I-129", "I-140", "I-485", "I-539", "I-765", "I-131", "I-90", "I-918", "N-400", "N-600", "Other"]
            st.session_state.form_type = st.selectbox("Select Form Type", form_types)
        
        with col2:
            uploaded_file = st.file_uploader("Choose PDF file", type="pdf")
        
        if uploaded_file:
            st.success(f"📄 Form Type: {st.session_state.form_type} | File: {uploaded_file.name}")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("🔍 Extract Fields", type="primary", use_container_width=True):
                    with st.spinner("Extracting fields..."):
                        fields = extract_pdf_fields(uploaded_file)
                        
                        if fields:
                            st.session_state.pdf_fields = fields
                            st.session_state.fields_by_part = organize_by_parts(fields)
                            st.success(f"✅ Extracted {len(fields)} fields from {len(st.session_state.fields_by_part)} parts")
                        else:
                            st.error("No fields found in PDF")
            
            with col2:
                if st.session_state.pdf_fields:
                    if st.button("🤖 Auto-Map Fields", type="secondary", use_container_width=True):
                        with st.spinner("Auto-mapping fields..."):
                            mapped_count = 0
                            
                            for field in st.session_state.pdf_fields:
                                suggestion = suggest_mapping(field['raw_name'], field['type'])
                                if suggestion:
                                    st.session_state.mapped_fields[field['raw_name']] = suggestion
                                    mapped_count += 1
                            
                            st.success(f"✅ Auto-mapped {mapped_count} fields")
                            st.rerun()
            
            with col3:
                if st.session_state.pdf_fields:
                    if st.button("🔄 Reset All", type="secondary", use_container_width=True):
                        st.session_state.mapped_fields = {}
                        st.session_state.questionnaire_fields = {}
                        st.session_state.unmapped_fields = []
                        st.rerun()
    
    # Tab 2: Fields by Parts
    with tab2:
        st.header("PDF Fields by Parts")
        
        if st.session_state.fields_by_part:
            # Summary statistics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Parts", len(st.session_state.fields_by_part))
            with col2:
                st.metric("Total Fields", len(st.session_state.pdf_fields))
            with col3:
                st.metric("Average Fields/Part", round(len(st.session_state.pdf_fields) / len(st.session_state.fields_by_part), 1))
            with col4:
                st.metric("Mapping Score", f"{st.session_state.mapping_score}%")
            
            st.markdown("---")
            
            # Display each part
            for part_name, fields in st.session_state.fields_by_part.items():
                with st.expander(f"{part_name} ({len(fields)} fields)", expanded=False):
                    display_part_summary(part_name, fields)
        else:
            st.info("Please upload and extract a PDF first")
    
    # Tab 3: Field Mapping
    with tab3:
        if st.session_state.pdf_fields:
            display_mapping_interface()
        else:
            st.info("Please upload and extract a PDF first")
    
    # Tab 4: Questionnaire Builder
    with tab4:
        st.header("Questionnaire Configuration")
        
        if st.session_state.pdf_fields:
            # Show current questionnaire fields
            if st.session_state.questionnaire_fields:
                st.subheader("Current Questionnaire Fields")
                
                df_data = []
                for field_name, field_info in st.session_state.questionnaire_fields.items():
                    df_data.append({
                        'Field Name': field_info['name'],
                        'Description': field_info['description'],
                        'Type': field_info['type'],
                        'PDF Field': field_name
                    })
                
                df = pd.DataFrame(df_data)
                st.dataframe(df, use_container_width=True)
            
            # Add unmapped fields to questionnaire
            st.subheader("Add Unmapped Fields to Questionnaire")
            
            unmapped = [f for f in st.session_state.pdf_fields 
                       if f['raw_name'] not in st.session_state.mapped_fields 
                       and f['raw_name'] not in st.session_state.questionnaire_fields]
            
            if unmapped:
                st.write(f"Found {len(unmapped)} unmapped fields")
                
                if st.button("Add All Unmapped to Questionnaire"):
                    for field in unmapped:
                        st.session_state.questionnaire_fields[field['raw_name']] = {
                            'name': f"q_{field['index']}",
                            'type': field['type'],
                            'description': field['description']
                        }
                    st.rerun()
            else:
                st.success("All fields are mapped!")
        else:
            st.info("Please upload and extract a PDF first")
    
    # Tab 5: Export
    with tab5:
        st.header("Export Configuration")
        
        if st.session_state.pdf_fields and (st.session_state.mapped_fields or st.session_state.questionnaire_fields):
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📄 TypeScript Export")
                ts_content = generate_typescript_mapping()
                
                st.download_button(
                    f"📥 Download {st.session_state.form_type}.ts",
                    data=ts_content,
                    file_name=f"{st.session_state.form_type}.ts",
                    mime="text/plain",
                    use_container_width=True
                )
                
                with st.expander("Preview TypeScript"):
                    st.code(ts_content[:1000] + "...", language="typescript")
            
            with col2:
                st.subheader("📋 Questionnaire JSON")
                json_content = generate_questionnaire_json()
                
                st.download_button(
                    f"📥 Download {st.session_state.form_type.lower()}.json",
                    data=json_content,
                    file_name=f"{st.session_state.form_type.lower()}.json",
                    mime="application/json",
                    use_container_width=True
                )
                
                with st.expander("Preview JSON"):
                    st.code(json_content, language="json")
            
            # Export summary
            st.markdown("---")
            st.subheader("Export Summary")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Form Type", st.session_state.form_type)
                st.metric("Total Fields", len(st.session_state.pdf_fields))
            
            with col2:
                st.metric("Mapped Fields", len(st.session_state.mapped_fields))
                st.metric("Questionnaire Fields", len(st.session_state.questionnaire_fields))
            
            with col3:
                st.metric("Mapping Score", f"{st.session_state.mapping_score}%")
                st.metric("Parts", len(st.session_state.fields_by_part))
        else:
            st.info("No data to export. Please complete mapping first.")

if __name__ == "__main__":
    main()
