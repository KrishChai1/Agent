import streamlit as st
import json
import re
from datetime import datetime
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
import io
import base64
from dataclasses import dataclass, asdict
from collections import defaultdict
import hashlib

# Try to import PDF libraries
try:
    import PyPDF2
    from PyPDF2 import PdfReader
    PDF_AVAILABLE = True
except ImportError:
    try:
        import pypdf as PyPDF2
        from pypdf import PdfReader
        PDF_AVAILABLE = True
    except ImportError:
        PDF_AVAILABLE = False

# Try to import additional PDF libraries
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

# Page configuration
st.set_page_config(
    page_title="PDF Form Automation System",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .stButton>button {
        width: 100%;
    }
    .field-mapped {
        background-color: #d4edda;
        padding: 5px;
        border-radius: 3px;
    }
    .field-questionnaire {
        background-color: #d1ecf1;
        padding: 5px;
        border-radius: 3px;
    }
    .field-unmapped {
        background-color: #f8d7da;
        padding: 5px;
        border-radius: 3px;
    }
    .mapping-summary {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 5px;
        border: 1px solid #dee2e6;
    }
    div[data-testid="metric-container"] {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        padding: 15px;
        border-radius: 5px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .part-header {
        background-color: #e9ecef;
        padding: 10px;
        border-radius: 5px;
        margin-bottom: 10px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Check if PDF library is available
if not PDF_AVAILABLE:
    st.error("PDF processing library not found. Please install PyPDF2 or pypdf:")
    st.code("pip install PyPDF2")
    st.stop()

# Session state initialization
def init_session_state():
    """Initialize all session state variables"""
    defaults = {
        'pdf_fields': [],
        'mapped_fields': {},
        'questionnaire_fields': {},
        'conditional_fields': {},
        'default_fields': {},
        'field_groups': {},
        'validation_rules': {},
        'form_metadata': {},
        'extracted_text': "",
        'form_name': 'UnknownForm',
        'current_step': 1,
        'auto_save': True,
        'show_removed_fields': False,
        'removed_fields': []
    }
    
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

init_session_state()

# Enhanced mapping patterns
MAPPING_PATTERNS = {
    # Customer/Petitioner patterns
    'customer_name': {
        'patterns': [r'customer.*name', r'petitioner.*name', r'employer.*name', r'company.*name'],
        'mapping': 'customer.customer_name',
        'type': 'TextBox'
    },
    'customer_tax_id': {
        'patterns': [r'ein', r'fein', r'tax.*id', r'employer.*id'],
        'mapping': 'customer.customer_tax_id',
        'type': 'TextBox'
    },
    'signatory_first': {
        'patterns': [r'signatory.*first', r'authorized.*first', r'representative.*first'],
        'mapping': 'customer.signatory_first_name',
        'type': 'TextBox'
    },
    'signatory_last': {
        'patterns': [r'signatory.*last', r'authorized.*last', r'representative.*last'],
        'mapping': 'customer.signatory_last_name',
        'type': 'TextBox'
    },
    
    # Beneficiary patterns
    'beneficiary_first': {
        'patterns': [r'beneficiary.*first', r'given.*name', r'employee.*first', r'worker.*first'],
        'mapping': 'beneficiary.Beneficiary.beneficiaryFirstName',
        'type': 'TextBox'
    },
    'beneficiary_last': {
        'patterns': [r'beneficiary.*last', r'family.*name', r'employee.*last', r'surname'],
        'mapping': 'beneficiary.Beneficiary.beneficiaryLastName',
        'type': 'TextBox'
    },
    'beneficiary_dob': {
        'patterns': [r'date.*birth', r'dob', r'birth.*date'],
        'mapping': 'beneficiary.Beneficiary.beneficiaryDateOfBirth',
        'type': 'Date'
    },
    'alien_number': {
        'patterns': [r'alien.*number', r'a[\-\s]?number', r'uscis.*number'],
        'mapping': 'beneficiary.Beneficiary.alienNumber',
        'type': 'TextBox'
    },
    'ssn': {
        'patterns': [r'social.*security', r'ssn', r'ss.*number'],
        'mapping': 'beneficiary.Beneficiary.beneficiarySsn',
        'type': 'TextBox'
    },
    
    # Attorney patterns
    'attorney_last': {
        'patterns': [r'attorney.*last', r'lawyer.*last', r'att.*last'],
        'mapping': 'attorney.attorneyInfo.lastName',
        'type': 'TextBox'
    },
    'attorney_first': {
        'patterns': [r'attorney.*first', r'lawyer.*first', r'att.*first'],
        'mapping': 'attorney.attorneyInfo.firstName',
        'type': 'TextBox'
    },
    'attorney_bar': {
        'patterns': [r'bar.*number', r'license.*number', r'attorney.*bar'],
        'mapping': 'attorney.attorneyInfo.barNumber',
        'type': 'TextBox'
    },
    
    # Address patterns
    'street_address': {
        'patterns': [r'street.*address', r'address.*street', r'street.*name'],
        'mapping': 'address.addressStreet',
        'type': 'TextBox'
    },
    'city': {
        'patterns': [r'city', r'town', r'municipality'],
        'mapping': 'address.addressCity',
        'type': 'TextBox'
    },
    'state': {
        'patterns': [r'state', r'province'],
        'mapping': 'address.addressState',
        'type': 'TextBox'
    },
    'zip': {
        'patterns': [r'zip.*code', r'postal.*code', r'zip'],
        'mapping': 'address.addressZip',
        'type': 'TextBox'
    },
    
    # Case patterns
    'case_type': {
        'patterns': [r'case.*type', r'petition.*type', r'classification', r'visa.*type'],
        'mapping': 'case.caseType',
        'type': 'DropDown'
    },
    'job_title': {
        'patterns': [r'job.*title', r'position.*title', r'occupation', r'employment.*title'],
        'mapping': 'case.jobTitle',
        'type': 'TextBox'
    },
    'wages': {
        'patterns': [r'wage', r'salary', r'compensation', r'pay.*rate'],
        'mapping': 'case.wages',
        'type': 'Currency'
    }
}

# Field type detection patterns
FIELD_TYPES = {
    'CheckBox': {
        'patterns': [r'\[\s*\]', r'\(\s*\)', r'☐', r'□', r'checkbox', r'check\s+box'],
        'keywords': ['yes/no', 'check', 'select', 'mark']
    },
    'RadioButton': {
        'patterns': [r'\(\s*\)', r'○', r'◯', r'radio'],
        'keywords': ['select one', 'choose one', 'option']
    },
    'Date': {
        'patterns': [r'\d{1,2}/\d{1,2}/\d{4}', r'mm/dd/yyyy', r'__/__/____'],
        'keywords': ['date', 'dob', 'birth', 'expiry', 'expire']
    },
    'Currency': {
        'patterns': [r'\$[\d,]+', r'USD', r'dollars'],
        'keywords': ['wage', 'salary', 'amount', 'fee', 'cost', '$']
    },
    'DropDown': {
        'patterns': [r'▼', r'⌄', r'\[Select\]'],
        'keywords': ['dropdown', 'select', 'choose from', 'list']
    },
    'TextArea': {
        'patterns': [],
        'keywords': ['explain', 'describe', 'details', 'notes', 'comments']
    },
    'Signature': {
        'patterns': [r'signature[:\s]*_{3,}', r'sign[:\s]*_{3,}'],
        'keywords': ['signature', 'sign', 'signed by']
    }
}

def extract_pdf_fields(pdf_file) -> List[Dict[str, Any]]:
    """Extract fields from PDF using multiple methods"""
    fields = []
    extracted_text = ""
    
    try:
        pdf_reader = PdfReader(pdf_file)
        
        # Extract text
        for page in pdf_reader.pages:
            extracted_text += page.extract_text() + "\n"
        
        st.session_state.extracted_text = extracted_text
        
        # Method 1: Try form fields
        if hasattr(pdf_reader, 'get_form_text_fields'):
            form_fields = pdf_reader.get_form_text_fields()
            if form_fields:
                for field_name, field_value in form_fields.items():
                    field_type = determine_field_type(field_name, extracted_text)
                    fields.append({
                        'name': field_name,
                        'type': field_type,
                        'value': field_value or '',
                        'required': is_field_required(field_name, extracted_text),
                        'page': 0,
                        'source': 'form_fields'
                    })
        
        # Method 2: Try annotations
        if hasattr(pdf_reader, 'get_fields'):
            pdf_fields = pdf_reader.get_fields()
            if pdf_fields:
                for field_name, field_obj in pdf_fields.items():
                    if not any(f['name'] == field_name for f in fields):
                        field_type = 'TextBox'
                        if isinstance(field_obj, dict):
                            if field_obj.get('/FT') == '/Btn':
                                field_type = 'CheckBox' if not (field_obj.get('/Ff', 0) & 65536) else 'RadioButton'
                            elif field_obj.get('/FT') == '/Ch':
                                field_type = 'DropDown'
                        
                        fields.append({
                            'name': field_name,
                            'type': field_type,
                            'value': '',
                            'required': is_field_required(field_name, extracted_text),
                            'page': 0,
                            'source': 'annotations'
                        })
        
        # Method 3: Extract from text patterns
        if len(fields) < 10:  # If few fields found, try text extraction
            text_fields = extract_fields_from_text(extracted_text)
            existing_names = {f['name'].lower() for f in fields}
            
            for text_field in text_fields:
                if text_field['name'].lower() not in existing_names:
                    fields.append(text_field)
        
    except Exception as e:
        st.error(f"Error extracting PDF fields: {str(e)}")
    
    return fields

def extract_fields_from_text(text: str) -> List[Dict[str, Any]]:
    """Extract potential form fields from text"""
    fields = []
    seen_fields = set()
    
    # Common form field patterns
    patterns = [
        # Part.Number.Letter format (e.g., P1_1a, Part 2.3.b)
        (r'(?:P|Part)\s*(\d+)[_\.\s]+(\d+)([a-z]?)\.\s*([A-Za-z][A-Za-z\s]{2,50})', 'form_section'),
        # Numbered fields (e.g., 1. Name, 2.a. Address)
        (r'(\d+)\.([a-z]?\.)?\s*([A-Za-z][A-Za-z\s]{2,50})(?:\s*:?\s*(?:_{3,}|\[[\s]*\]))', 'numbered'),
        # Label with underscores
        (r'([A-Za-z][A-Za-z\s\-]{2,50})(?:\s*:?\s*)(?:_{3,})', 'underscore'),
        # Checkbox patterns
        (r'\[\s*\]\s*([A-Za-z][A-Za-z\s\-]{2,50})', 'checkbox'),
        # Radio button patterns
        (r'\(\s*\)\s*([A-Za-z][A-Za-z\s\-]{2,50})', 'radio'),
        # Date patterns
        (r'([A-Za-z\s]*Date[A-Za-z\s]*|DOB|Birth\s*Date)(?:\s*:?\s*)(?:_{3,}|mm/dd/yyyy)', 'date')
    ]
    
    for pattern, pattern_type in patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            # Extract field name based on pattern type
            if pattern_type == 'form_section':
                part = match.group(1)
                number = match.group(2)
                letter = match.group(3) or ''
                label = match.group(4).strip()
                field_name = f"P{part}_{number}{letter}_{re.sub(r'[^\w]', '', label)}"
            elif pattern_type == 'numbered':
                number = match.group(1)
                letter = match.group(2) or ''
                label = match.group(3).strip()
                field_name = f"Field_{number}{letter.strip('.')}_{re.sub(r'[^\w]', '', label)}"
            elif pattern_type in ['underscore', 'checkbox', 'radio', 'date']:
                field_name = match.group(1).strip()
                field_name = re.sub(r'\s+', '_', field_name)
                field_name = re.sub(r'[^\w\-\.]', '', field_name)
            else:
                continue
            
            # Skip if already seen or too short
            if len(field_name) < 3 or field_name.lower() in seen_fields:
                continue
            
            seen_fields.add(field_name.lower())
            
            # Determine field type
            if pattern_type == 'checkbox':
                field_type = 'CheckBox'
            elif pattern_type == 'radio':
                field_type = 'RadioButton'
            elif pattern_type == 'date':
                field_type = 'Date'
            else:
                field_type = determine_field_type(field_name, text)
            
            fields.append({
                'name': field_name,
                'type': field_type,
                'value': '',
                'required': is_field_required(field_name, text),
                'page': 0,
                'source': 'text_extraction'
            })
    
    return fields

def determine_field_type(field_name: str, context: str = "") -> str:
    """Determine field type based on name and context"""
    field_lower = field_name.lower()
    
    # Check each field type
    for field_type, type_info in FIELD_TYPES.items():
        # Check patterns
        for pattern in type_info['patterns']:
            if re.search(pattern, field_name, re.IGNORECASE):
                return field_type
        
        # Check keywords
        for keyword in type_info['keywords']:
            if keyword.lower() in field_lower:
                return field_type
    
    # Default to TextBox
    return 'TextBox'

def is_field_required(field_name: str, context: str) -> bool:
    """Determine if a field is required"""
    field_lower = field_name.lower()
    
    # Common required field indicators
    required_indicators = ['required', 'mandatory', '*', 'must']
    required_fields = ['name', 'date', 'signature', 'ssn', 'ein', 'address', 'email', 'phone']
    
    # Check field name
    for indicator in required_indicators:
        if indicator in field_lower:
            return True
    
    # Check common required fields
    for req_field in required_fields:
        if req_field in field_lower:
            return True
    
    return False

def auto_map_field(field_name: str) -> Tuple[Optional[str], float]:
    """Auto-map field based on patterns"""
    field_lower = field_name.lower()
    field_clean = re.sub(r'[^\w\s]', ' ', field_lower).strip()
    
    best_match = None
    best_score = 0
    
    for category, pattern_info in MAPPING_PATTERNS.items():
        for pattern in pattern_info['patterns']:
            if re.search(pattern, field_clean):
                score = 0.8
                # Exact match gets higher score
                if pattern == field_clean:
                    score = 1.0
                
                if score > best_score:
                    best_score = score
                    best_match = pattern_info['mapping']
    
    return best_match, best_score

def auto_process_fields():
    """Auto process all fields - map or move to questionnaire"""
    processed = 0
    
    for field in st.session_state.pdf_fields:
        field_name = field['name']
        field_type = field['type']
        
        # Skip if already processed
        if field_name in st.session_state.mapped_fields or field_name in st.session_state.questionnaire_fields:
            continue
        
        # Move checkboxes and radio buttons to questionnaire
        if field_type in ['CheckBox', 'RadioButton']:
            st.session_state.questionnaire_fields[field_name] = {
                'type': 'checkbox' if field_type == 'CheckBox' else 'radio',
                'required': field.get('required', False),
                'options': 'Yes\nNo' if field_type == 'CheckBox' else '',
                'validation': '',
                'label': field_name,
                'style': {"col": "12"}
            }
            processed += 1
        else:
            # Try to auto-map
            mapping, score = auto_map_field(field_name)
            if mapping and score >= 0.8:
                st.session_state.mapped_fields[field_name] = f"{mapping}:{field_type}"
                processed += 1
            else:
                # If can't map, move to questionnaire
                st.session_state.questionnaire_fields[field_name] = {
                    'type': get_questionnaire_type(field_type),
                    'required': field.get('required', False),
                    'options': '',
                    'validation': '',
                    'label': field_name,
                    'style': {"col": "12"}
                }
                processed += 1
    
    return processed

def get_questionnaire_type(pdf_type: str) -> str:
    """Convert PDF field type to questionnaire type"""
    type_map = {
        'TextBox': 'text',
        'CheckBox': 'checkbox',
        'RadioButton': 'radio',
        'DropDown': 'select',
        'Date': 'date',
        'TextArea': 'textarea',
        'Currency': 'text',
        'Signature': 'text'
    }
    return type_map.get(pdf_type, 'text')

def organize_fields_by_part():
    """Organize fields by form parts"""
    parts = {
        "Part 1 - Petitioner/Customer Information": [],
        "Part 2 - Beneficiary Information": [],
        "Part 3 - Attorney Information": [],
        "Part 4 - Case Information": [],
        "Part 5 - Address Information": [],
        "Part 6 - Contact Information": [],
        "Part 7 - Additional Information": [],
        "Questionnaire Fields": [],
        "Unmapped Fields": []
    }
    
    # Categorize each field
    for field in st.session_state.pdf_fields:
        field_name = field['name']
        field_lower = field_name.lower()
        
        # Check if in removed fields
        if field_name in st.session_state.removed_fields:
            continue
        
        # Check if in questionnaire
        if field_name in st.session_state.questionnaire_fields:
            parts["Questionnaire Fields"].append(field)
        # Check if mapped
        elif field_name in st.session_state.mapped_fields:
            mapping = st.session_state.mapped_fields[field_name]
            if 'customer' in mapping or 'petitioner' in field_lower:
                parts["Part 1 - Petitioner/Customer Information"].append(field)
            elif 'beneficiary' in mapping or 'employee' in field_lower:
                parts["Part 2 - Beneficiary Information"].append(field)
            elif 'attorney' in mapping or 'lawyer' in field_lower:
                parts["Part 3 - Attorney Information"].append(field)
            elif 'case' in mapping or 'petition' in field_lower:
                parts["Part 4 - Case Information"].append(field)
            elif 'address' in mapping or any(addr in field_lower for addr in ['street', 'city', 'state', 'zip']):
                parts["Part 5 - Address Information"].append(field)
            elif any(contact in field_lower for contact in ['phone', 'email', 'fax']):
                parts["Part 6 - Contact Information"].append(field)
            else:
                parts["Part 7 - Additional Information"].append(field)
        else:
            parts["Unmapped Fields"].append(field)
    
    return parts

def generate_typescript_output():
    """Generate TypeScript configuration"""
    form_name = st.session_state.get('form_name', 'UnknownForm')
    form_name_clean = re.sub(r'[^\w]', '', form_name)
    
    # Organize fields by category
    categories = {
        'customerData': {},
        'beneficiaryData': {},
        'attorneyData': {},
        'caseData': {},
        'addressData': {},
        'contactData': {},
        'otherData': {}
    }
    
    # Process mapped fields
    for field_name, mapping in st.session_state.mapped_fields.items():
        # Extract mapping and type
        if ':' in mapping:
            mapping_path, field_type = mapping.split(':', 1)
        else:
            mapping_path = mapping
            field_type = next((f['type'] for f in st.session_state.pdf_fields if f['name'] == field_name), 'TextBox')
        
        # Determine category
        category = 'otherData'
        for cat in categories.keys():
            if mapping_path.startswith(cat.replace('Data', '')):
                category = cat
                break
        
        categories[category][field_name] = f"{mapping_path}:{field_type}"
    
    # Format questionnaire data
    questionnaire_data = {}
    for field_name, field_info in st.session_state.questionnaire_fields.items():
        field_key = re.sub(r'[^\w]', '_', field_name)
        questionnaire_data[field_key] = f"{field_key}:{field_info['type']}"
    
    # Format conditional fields
    conditional_data = {}
    for cond_name, cond_info in st.session_state.conditional_fields.items():
        conditional_data[cond_name] = {
            "condition": cond_info.get('condition', ''),
            "conditionTrue": cond_info.get('conditionTrue', ''),
            "conditionFalse": cond_info.get('conditionFalse', ''),
            "conditionType": cond_info.get('conditionType', 'TextBox')
        }
    
    # Generate TypeScript
    ts_content = f"""// Auto-generated form configuration for {form_name}
// Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

export const {form_name_clean} = {{
    formname: "{form_name_clean}",
    customerData: {json.dumps(categories['customerData'] if categories['customerData'] else None, indent=8)},
    beneficiaryData: {json.dumps(categories['beneficiaryData'] if categories['beneficiaryData'] else None, indent=8)},
    attorneyData: {json.dumps(categories['attorneyData'] if categories['attorneyData'] else None, indent=8)},
    caseData: {json.dumps(categories['caseData'] if categories['caseData'] else None, indent=8)},
    addressData: {json.dumps(categories['addressData'] if categories['addressData'] else None, indent=8)},
    contactData: {json.dumps(categories['contactData'] if categories['contactData'] else None, indent=8)},
    otherData: {json.dumps(categories['otherData'] if categories['otherData'] else None, indent=8)},
    questionnaireData: {json.dumps(questionnaire_data, indent=8)},
    defaultData: {json.dumps(st.session_state.default_fields, indent=8)},
    conditionalData: {json.dumps(conditional_data, indent=8)},
    pdfName: "{form_name.replace('_', '-')}",
    metadata: {{
        totalFields: {len(st.session_state.pdf_fields)},
        mappedFields: {len(st.session_state.mapped_fields)},
        questionnaireFields: {len(st.session_state.questionnaire_fields)},
        removedFields: {len(st.session_state.removed_fields)}
    }}
}};

export default {form_name_clean};"""
    
    return ts_content

def generate_questionnaire_json():
    """Generate JSON controls format for questionnaire"""
    controls = []
    
    for field_name, field_info in st.session_state.questionnaire_fields.items():
        control = {
            "name": re.sub(r'[^\w]', '_', field_name),
            "label": field_info.get('label', field_name),
            "type": field_info.get('type', 'text'),
            "validators": {
                "required": field_info.get('required', False)
            },
            "style": field_info.get('style', {"col": "12"})
        }
        
        # Add validation pattern if exists
        if field_info.get('validation'):
            control['validators']['pattern'] = field_info['validation']
        
        # Add options for select/radio
        if control['type'] in ['select', 'radio'] and field_info.get('options'):
            options = field_info['options'].split('\n')
            if control['type'] == 'radio':
                # For radio, create separate controls
                for idx, option in enumerate(options):
                    radio_control = control.copy()
                    radio_control['value'] = str(idx + 1)
                    radio_control['label'] = option
                    radio_control['id'] = f"{control['name']}_{idx}"
                    controls.append(radio_control)
                continue
            else:
                control['options'] = options
        
        controls.append(control)
    
    return json.dumps({"controls": controls}, indent=2)

# Main Application
st.title("📄 PDF Form Automation System")
st.markdown("Extract fields from PDF forms and generate TypeScript configurations")

# Sidebar
with st.sidebar:
    st.header("🔧 Configuration")
    
    # Form name
    form_name = st.text_input(
        "Form Name",
        value=st.session_state.get('form_name', 'UnknownForm'),
        help="Enter the form name (e.g., I129, I539, H2B)"
    )
    st.session_state.form_name = form_name
    
    st.markdown("---")
    
    # Quick stats
    if st.session_state.pdf_fields:
        st.header("📊 Statistics")
        
        total_fields = len(st.session_state.pdf_fields)
        mapped = len(st.session_state.mapped_fields)
        questionnaire = len(st.session_state.questionnaire_fields)
        removed = len(st.session_state.removed_fields)
        unmapped = total_fields - mapped - questionnaire - removed
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Fields", total_fields)
            st.metric("Mapped", mapped)
        with col2:
            st.metric("Questionnaire", questionnaire)
            st.metric("Unmapped", unmapped)
        
        if removed > 0:
            st.metric("Removed", removed)
    
    st.markdown("---")
    
    # Tools
    st.header("🛠️ Tools")
    
    if st.button("🔄 Reset All", use_container_width=True):
        for key in ['pdf_fields', 'mapped_fields', 'questionnaire_fields', 
                   'conditional_fields', 'default_fields', 'removed_fields']:
            st.session_state[key] = {} if 'fields' in key else []
        st.rerun()
    
    st.toggle("Show Removed Fields", key="show_removed_fields")

# Main content area with tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📤 Upload & Extract",
    "🗂️ Field Mapping",
    "❓ Questionnaire",
    "⚙️ Advanced Settings",
    "📥 Generate & Download"
])

# Tab 1: Upload & Extract
with tab1:
    st.header("Step 1: Upload PDF and Extract Fields")
    
    uploaded_file = st.file_uploader(
        "Choose a PDF file",
        type="pdf",
        help="Upload a PDF form to extract fields"
    )
    
    if uploaded_file is not None:
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.info(f"📄 Uploaded: {uploaded_file.name}")
        
        with col2:
            if st.button("🔍 Extract Fields", type="primary", use_container_width=True):
                with st.spinner("Extracting fields from PDF..."):
                    fields = extract_pdf_fields(uploaded_file)
                    st.session_state.pdf_fields = fields
                    
                    if fields:
                        st.success(f"✅ Extracted {len(fields)} fields!")
                        
                        # Auto process fields
                        processed = auto_process_fields()
                        if processed > 0:
                            st.info(f"🤖 Auto-processed {processed} fields")
                        
                        st.rerun()
                    else:
                        st.warning("⚠️ No fields could be extracted from the PDF")
    
    # Display extracted fields
    if st.session_state.pdf_fields:
        st.subheader("📋 Extracted Fields")
        
        # Field summary
        parts = organize_fields_by_part()
        
        for part_name, fields in parts.items():
            if fields:
                with st.expander(f"{part_name} ({len(fields)} fields)", expanded=(part_name == "Unmapped Fields")):
                    for field in fields:
                        col1, col2, col3 = st.columns([3, 2, 1])
                        
                        with col1:
                            icon = "☑️" if field['type'] == 'CheckBox' else "📝"
                            st.text(f"{icon} {field['name']}")
                        
                        with col2:
                            st.text(f"Type: {field['type']}")
                        
                        with col3:
                            if st.button("🗑️", key=f"remove_{field['name']}", help="Remove field"):
                                st.session_state.removed_fields.append(field['name'])
                                st.rerun()

# Tab 2: Field Mapping
with tab2:
    st.header("Step 2: Map Fields to Database")
    
    if not st.session_state.pdf_fields:
        st.warning("⚠️ Please upload and extract fields first!")
    else:
        # Quick actions
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🤖 Auto-Map All", type="primary", use_container_width=True):
                mapped_count = 0
                for field in st.session_state.pdf_fields:
                    field_name = field['name']
                    if field_name not in st.session_state.mapped_fields and \
                       field_name not in st.session_state.questionnaire_fields and \
                       field_name not in st.session_state.removed_fields:
                        mapping, score = auto_map_field(field_name)
                        if mapping and score >= 0.8:
                            st.session_state.mapped_fields[field_name] = f"{mapping}:{field['type']}"
                            mapped_count += 1
                
                st.success(f"✅ Auto-mapped {mapped_count} fields")
                st.rerun()
        
        with col2:
            if st.button("❓ Unmapped to Questionnaire", use_container_width=True):
                moved = 0
                for field in st.session_state.pdf_fields:
                    field_name = field['name']
                    if field_name not in st.session_state.mapped_fields and \
                       field_name not in st.session_state.questionnaire_fields and \
                       field_name not in st.session_state.removed_fields:
                        st.session_state.questionnaire_fields[field_name] = {
                            'type': get_questionnaire_type(field['type']),
                            'required': field.get('required', False),
                            'options': 'Yes\nNo' if field['type'] == 'CheckBox' else '',
                            'validation': '',
                            'label': field_name,
                            'style': {"col": "12"}
                        }
                        moved += 1
                
                if moved > 0:
                    st.success(f"✅ Moved {moved} fields to questionnaire")
                    st.rerun()
        
        with col3:
            if st.button("🗑️ Clear All Mappings", use_container_width=True):
                st.session_state.mapped_fields = {}
                st.success("✅ Cleared all mappings")
                st.rerun()
        
        st.markdown("---")
        
        # Display fields by parts for mapping
        parts = organize_fields_by_part()
        
        # Show unmapped fields first
        if parts["Unmapped Fields"]:
            st.subheader(f"🔴 Unmapped Fields ({len(parts['Unmapped Fields'])})")
            
            for field in parts["Unmapped Fields"]:
                if field['name'] not in st.session_state.removed_fields:
                    col1, col2, col3, col4 = st.columns([3, 3, 1, 1])
                    
                    with col1:
                        st.text_input(
                            "Field",
                            value=f"{field['name']} ({field['type']})",
                            disabled=True,
                            key=f"display_map_{field['name']}"
                        )
                    
                    with col2:
                        mapping = st.text_input(
                            "Mapping",
                            placeholder="e.g., customer.customer_name",
                            key=f"mapping_{field['name']}"
                        )
                        
                        if mapping:
                            st.session_state.mapped_fields[field['name']] = f"{mapping}:{field['type']}"
                    
                    with col3:
                        if st.button("❓", key=f"to_quest_{field['name']}", help="Move to questionnaire"):
                            st.session_state.questionnaire_fields[field['name']] = {
                                'type': get_questionnaire_type(field['type']),
                                'required': field.get('required', False),
                                'options': '',
                                'validation': '',
                                'label': field['name'],
                                'style': {"col": "12"}
                            }
                            st.rerun()
                    
                    with col4:
                        if st.button("🗑️", key=f"remove_map_{field['name']}", help="Remove field"):
                            st.session_state.removed_fields.append(field['name'])
                            st.rerun()
        
        # Show mapped fields
        st.subheader("🟢 Mapped Fields")
        
        mapped_fields = [f for f in st.session_state.pdf_fields 
                        if f['name'] in st.session_state.mapped_fields and 
                        f['name'] not in st.session_state.removed_fields]
        
        if mapped_fields:
            for field in mapped_fields:
                col1, col2, col3 = st.columns([3, 3, 1])
                
                with col1:
                    st.text_input(
                        "Field",
                        value=f"{field['name']} ({field['type']})",
                        disabled=True,
                        key=f"mapped_display_{field['name']}"
                    )
                
                with col2:
                    st.text_input(
                        "Mapped to",
                        value=st.session_state.mapped_fields[field['name']],
                        disabled=True,
                        key=f"mapped_to_{field['name']}"
                    )
                
                with col3:
                    if st.button("❌", key=f"unmap_{field['name']}", help="Remove mapping"):
                        del st.session_state.mapped_fields[field['name']]
                        st.rerun()
        else:
            st.info("No fields mapped yet")

# Tab 3: Questionnaire
with tab3:
    st.header("Step 3: Configure Questionnaire Fields")
    
    # Add new questionnaire field
    with st.expander("➕ Add New Questionnaire Field", expanded=False):
        col1, col2, col3 = st.columns([3, 2, 1])
        
        with col1:
            new_field_name = st.text_input("Field Name/Label", placeholder="e.g., Have you ever been arrested?")
        
        with col2:
            new_field_type = st.selectbox(
                "Field Type",
                ["text", "checkbox", "radio", "select", "date", "textarea"]
            )
        
        with col3:
            new_field_required = st.checkbox("Required", value=True)
        
        if st.button("Add Field", type="primary"):
            if new_field_name:
                st.session_state.questionnaire_fields[new_field_name] = {
                    'type': new_field_type,
                    'required': new_field_required,
                    'options': '',
                    'validation': '',
                    'label': new_field_name,
                    'style': {"col": "12"}
                }
                st.success(f"✅ Added: {new_field_name}")
                st.rerun()
    
    # Display questionnaire fields
    if st.session_state.questionnaire_fields:
        st.subheader(f"📋 Questionnaire Fields ({len(st.session_state.questionnaire_fields)})")
        
        for field_name, field_info in list(st.session_state.questionnaire_fields.items()):
            with st.expander(f"{field_name} ({field_info['type']})", expanded=False):
                col1, col2 = st.columns([4, 1])
                
                with col1:
                    # Field properties
                    field_info['type'] = st.selectbox(
                        "Type",
                        ["text", "checkbox", "radio", "select", "date", "textarea"],
                        index=["text", "checkbox", "radio", "select", "date", "textarea"].index(field_info['type']),
                        key=f"q_type_{field_name}"
                    )
                    
                    field_info['required'] = st.checkbox(
                        "Required",
                        value=field_info.get('required', False),
                        key=f"q_req_{field_name}"
                    )
                    
                    if field_info['type'] in ['radio', 'select']:
                        field_info['options'] = st.text_area(
                            "Options (one per line)",
                            value=field_info.get('options', ''),
                            height=100,
                            key=f"q_opt_{field_name}"
                        )
                    
                    field_info['validation'] = st.text_input(
                        "Validation Pattern (regex)",
                        value=field_info.get('validation', ''),
                        key=f"q_val_{field_name}",
                        placeholder="e.g., ^[0-9]{3}-[0-9]{2}-[0-9]{4}$ for SSN"
                    )
                
                with col2:
                    st.write("")  # Spacer
                    if st.button("🗑️ Remove", key=f"q_remove_{field_name}", use_container_width=True):
                        del st.session_state.questionnaire_fields[field_name]
                        st.rerun()
                    
                    if st.button("➡️ To Mapping", key=f"q_to_map_{field_name}", use_container_width=True):
                        del st.session_state.questionnaire_fields[field_name]
                        st.rerun()
    else:
        st.info("No questionnaire fields configured yet")

# Tab 4: Advanced Settings
with tab4:
    st.header("Step 4: Advanced Configuration")
    
    # Conditional Fields
    st.subheader("⚡ Conditional Fields")
    
    with st.expander("➕ Add Conditional Field", expanded=False):
        cond_name = st.text_input("Condition Name", placeholder="e.g., showAddressFields")
        cond_condition = st.text_input("Condition", placeholder="e.g., mailingAddressDifferent==true")
        
        col1, col2 = st.columns(2)
        with col1:
            cond_true = st.text_input("If True", placeholder="Value or action when true")
        with col2:
            cond_false = st.text_input("If False", placeholder="Value or action when false")
        
        cond_type = st.selectbox("Result Type", ["TextBox", "CheckBox", "Visibility", "Calculation"])
        
        if st.button("Add Conditional"):
            if cond_name and cond_condition:
                st.session_state.conditional_fields[cond_name] = {
                    'condition': cond_condition,
                    'conditionTrue': cond_true,
                    'conditionFalse': cond_false,
                    'conditionType': cond_type
                }
                st.success(f"✅ Added conditional: {cond_name}")
                st.rerun()
    
    # Display conditionals
    if st.session_state.conditional_fields:
        for cond_name, cond_info in list(st.session_state.conditional_fields.items()):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.text(f"**{cond_name}**: {cond_info['condition']}")
                st.text(f"True: {cond_info['conditionTrue']}, False: {cond_info['conditionFalse']}")
            with col2:
                if st.button("🗑️", key=f"del_cond_{cond_name}"):
                    del st.session_state.conditional_fields[cond_name]
                    st.rerun()
    
    st.markdown("---")
    
    # Default Values
    st.subheader("📝 Default Values")
    
    col1, col2, col3 = st.columns([3, 2, 1])
    with col1:
        default_field = st.text_input("Field Name", placeholder="e.g., country")
    with col2:
        default_value = st.text_input("Default Value", placeholder="e.g., United States")
    with col3:
        if st.button("Add Default"):
            if default_field and default_value:
                st.session_state.default_fields[default_field] = f"{default_value}:TextBox"
                st.rerun()
    
    # Display defaults
    if st.session_state.default_fields:
        for field, value in list(st.session_state.default_fields.items()):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.text(f"{field} = {value}")
            with col2:
                if st.button("🗑️", key=f"del_def_{field}"):
                    del st.session_state.default_fields[field]
                    st.rerun()

# Tab 5: Generate & Download
with tab5:
    st.header("Step 5: Generate Configuration and Download")
    
    if not st.session_state.pdf_fields:
        st.warning("⚠️ Please upload and process a PDF first!")
    else:
        # Summary
        st.subheader("📊 Configuration Summary")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Fields", len(st.session_state.pdf_fields))
        with col2:
            st.metric("Mapped", len(st.session_state.mapped_fields))
        with col3:
            st.metric("Questionnaire", len(st.session_state.questionnaire_fields))
        with col4:
            st.metric("Removed", len(st.session_state.removed_fields))
        
        st.markdown("---")
        
        # Generate outputs
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📄 TypeScript Configuration")
            
            if st.button("Generate TypeScript", type="primary", use_container_width=True):
                ts_content = generate_typescript_output()
                
                st.download_button(
                    label="📥 Download TypeScript File",
                    data=ts_content,
                    file_name=f"{st.session_state.form_name}.ts",
                    mime="text/plain",
                    use_container_width=True
                )
                
                with st.expander("Preview TypeScript", expanded=False):
                    st.code(ts_content, language="typescript")
        
        with col2:
            st.subheader("📋 Questionnaire JSON")
            
            if st.button("Generate Questionnaire JSON", type="primary", use_container_width=True):
                json_content = generate_questionnaire_json()
                
                st.download_button(
                    label="📥 Download JSON Controls",
                    data=json_content,
                    file_name=f"{st.session_state.form_name}_controls.json",
                    mime="application/json",
                    use_container_width=True
                )
                
                with st.expander("Preview JSON", expanded=False):
                    st.code(json_content, language="json")
        
        st.markdown("---")
        
        # Complete configuration export
        st.subheader("💾 Complete Configuration")
        
        if st.button("Export Complete Configuration", type="primary", use_container_width=True):
            config = {
                "formName": st.session_state.form_name,
                "timestamp": datetime.now().isoformat(),
                "pdfFields": st.session_state.pdf_fields,
                "mappedFields": st.session_state.mapped_fields,
                "questionnaireFields": st.session_state.questionnaire_fields,
                "conditionalFields": st.session_state.conditional_fields,
                "defaultFields": st.session_state.default_fields,
                "removedFields": st.session_state.removed_fields,
                "metadata": {
                    "totalFields": len(st.session_state.pdf_fields),
                    "mappedFields": len(st.session_state.mapped_fields),
                    "questionnaireFields": len(st.session_state.questionnaire_fields),
                    "removedFields": len(st.session_state.removed_fields)
                }
            }
            
            config_json = json.dumps(config, indent=2)
            
            st.download_button(
                label="📥 Download Complete Configuration",
                data=config_json,
                file_name=f"{st.session_state.form_name}_complete_config.json",
                mime="application/json",
                use_container_width=True
            )

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666;'>
    PDF Form Automation System v1.0 | Built with Streamlit
</div>
""", unsafe_allow_html=True)
