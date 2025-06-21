import streamlit as st
import json
import re
from datetime import datetime
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple, Set
import io
import base64
from dataclasses import dataclass, asdict, field
from collections import defaultdict, OrderedDict
import hashlib
import traceback

# Try to import PDF libraries with multiple fallbacks
PDF_AVAILABLE = False
PDF_LIBRARY = None

# Try PyPDF2 first
try:
    import PyPDF2
    from PyPDF2 import PdfReader
    PDF_AVAILABLE = True
    PDF_LIBRARY = "PyPDF2"
except ImportError:
    pass

# Try pypdf as fallback
if not PDF_AVAILABLE:
    try:
        import pypdf
        from pypdf import PdfReader
        PDF_AVAILABLE = True
        PDF_LIBRARY = "pypdf"
    except ImportError:
        pass

# Try pdfplumber for better text extraction
PDFPLUMBER_AVAILABLE = False
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    pass

# Try fitz (PyMuPDF) for even better extraction
PYMUPDF_AVAILABLE = False
try:
    import fitz
    PYMUPDF_AVAILABLE = True
except ImportError:
    pass

# Page configuration with USCIS theme
st.set_page_config(
    page_title="USCIS PDF Form Automation System",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# USCIS-themed CSS with enhanced part display
st.markdown("""
<style>
    /* USCIS Color Scheme */
    :root {
        --uscis-blue: #003366;
        --uscis-light-blue: #005ea2;
        --uscis-red: #e21727;
        --success-green: #2e8540;
        --warning-yellow: #fdb81e;
        --info-blue: #00a6d2;
        --light-gray: #f7f7f7;
        --border-gray: #d6d7d9;
        --text-dark: #212121;
        --text-gray: #5b616b;
    }
    
    /* Global Styles */
    .stApp {
        background-color: #ffffff;
    }
    
    /* Part Container Styling */
    .part-container {
        background: var(--light-gray);
        border: 2px solid var(--border-gray);
        border-radius: 8px;
        margin-bottom: 16px;
        overflow: hidden;
        transition: all 0.3s ease;
    }
    
    .part-container:hover {
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    }
    
    .part-header {
        background: var(--uscis-blue);
        color: white;
        padding: 16px 20px;
        cursor: pointer;
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-weight: 600;
        font-size: 1.1em;
        transition: background 0.3s ease;
    }
    
    .part-header:hover {
        background: var(--uscis-light-blue);
    }
    
    .part-header.attorney {
        background: var(--uscis-red);
    }
    
    .part-stats {
        display: flex;
        gap: 20px;
        font-size: 0.9em;
        font-weight: normal;
    }
    
    .stat-item {
        display: flex;
        align-items: center;
        gap: 5px;
    }
    
    .stat-mapped { color: #90ee90; }
    .stat-unmapped { color: #ffeb9c; }
    .stat-questionnaire { color: #9cc5ff; }
    
    /* Field Cards */
    .field-card {
        background: white;
        border: 1px solid var(--border-gray);
        border-radius: 6px;
        padding: 12px 16px;
        margin: 8px 16px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        transition: all 0.2s ease;
    }
    
    .field-card:hover {
        border-color: var(--uscis-light-blue);
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
    }
    
    .field-card.mapped {
        border-left: 4px solid var(--success-green);
    }
    
    .field-card.unmapped {
        border-left: 4px solid var(--warning-yellow);
    }
    
    .field-card.questionnaire {
        border-left: 4px solid var(--info-blue);
    }
    
    .field-info {
        flex: 1;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    
    .field-name {
        font-weight: 500;
        color: var(--text-dark);
    }
    
    .field-type {
        background: var(--light-gray);
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.85em;
        color: var(--text-gray);
    }
    
    .field-mapping {
        color: var(--success-green);
        font-size: 0.9em;
        font-style: italic;
    }
    
    .field-actions {
        display: flex;
        gap: 8px;
    }
    
    /* Action Buttons */
    .action-btn {
        padding: 4px 12px;
        border-radius: 4px;
        border: 1px solid var(--border-gray);
        background: white;
        cursor: pointer;
        font-size: 0.85em;
        transition: all 0.2s ease;
    }
    
    .action-btn:hover {
        background: var(--light-gray);
        border-color: var(--uscis-light-blue);
    }
    
    .action-btn.primary {
        background: var(--uscis-blue);
        color: white;
        border-color: var(--uscis-blue);
    }
    
    .action-btn.primary:hover {
        background: var(--uscis-light-blue);
        border-color: var(--uscis-light-blue);
    }
    
    /* Progress Indicator */
    .progress-ring {
        display: inline-block;
        width: 60px;
        height: 60px;
    }
    
    .progress-ring circle {
        transition: stroke-dashoffset 0.5s ease;
    }
    
    /* Section Divider */
    .section-divider {
        border-top: 2px solid var(--border-gray);
        margin: 24px 0;
        position: relative;
    }
    
    .section-divider::before {
        content: attr(data-text);
        position: absolute;
        top: -12px;
        left: 50%;
        transform: translateX(-50%);
        background: white;
        padding: 0 16px;
        color: var(--text-gray);
        font-size: 0.9em;
        font-weight: 500;
    }
    
    /* Enhanced Metrics */
    div[data-testid="metric-container"] {
        background: var(--light-gray);
        border: 1px solid var(--border-gray);
        padding: 16px;
        border-radius: 6px;
        text-align: center;
    }
    
    div[data-testid="metric-container"] > div[data-testid="metric"] {
        font-size: 2em;
        font-weight: 600;
        color: var(--uscis-blue);
    }
    
    /* Tabs Enhancement */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        border-bottom: 2px solid var(--border-gray);
    }
    
    .stTabs [data-baseweb="tab"] {
        color: var(--text-gray);
        font-weight: 500;
        padding: 12px 20px;
        border-bottom: 3px solid transparent;
    }
    
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        color: var(--uscis-blue);
        border-bottom-color: var(--uscis-blue);
    }
    
    /* Add Field Form */
    .add-field-form {
        background: var(--light-gray);
        border: 1px dashed var(--uscis-light-blue);
        border-radius: 6px;
        padding: 16px;
        margin: 16px;
    }
    
    /* Mapping Input Enhancement */
    .mapping-input-container {
        position: relative;
    }
    
    .mapping-suggestion {
        position: absolute;
        top: 100%;
        left: 0;
        right: 0;
        background: white;
        border: 1px solid var(--border-gray);
        border-radius: 4px;
        margin-top: 4px;
        padding: 8px;
        font-size: 0.85em;
        color: var(--info-blue);
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state for USCIS forms
def init_session_state():
    """Initialize session state with USCIS-specific structure"""
    defaults = {
        'pdf_fields': [],
        'form_parts': OrderedDict(),  # Organized by parts
        'mapped_fields': {},
        'questionnaire_fields': {},
        'conditional_fields': {},
        'default_fields': {},
        'form_metadata': {},
        'extracted_text': "",
        'form_name': '',
        'form_type': None,  # I-129, I-539, etc.
        'uscis_form_number': None,
        'current_step': 1,
        'show_mapped': True,
        'show_unmapped': True,
        'show_questionnaire': True,
        'removed_fields': [],
        'processing_log': [],
        'attorney_fields': [],  # Separate attorney fields
        'expand_all_parts': False,
        'expanded_parts': set()
    }
    
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

init_session_state()

# USCIS Form Patterns and Structure
USCIS_FORMS = {
    'I-129': {
        'title': 'Petition for a Nonimmigrant Worker',
        'patterns': [r'Form\s*I-129', r'Petition.*Nonimmigrant.*Worker'],
        'parts': OrderedDict([
            ('Part 1', 'Information About the Petitioner'),
            ('Part 2', 'Information About This Petition'),
            ('Part 3', 'Beneficiary Information'),
            ('Part 4', 'Processing Information'),
            ('Part 5', 'Basic Information About the Proposed Employment and Employer'),
            ('Part 6', 'Certification Regarding the Release of Controlled Technology'),
            ('Part 7', 'Signature of Petitioner'),
            ('Part 8', 'Additional Information About the Petitioner'),
            ('Part 9', 'Statement, Contact Information, Declaration, and Signature of the Person Preparing This Petition')
        ])
    },
    'I-539': {
        'title': 'Application To Extend/Change Nonimmigrant Status',
        'patterns': [r'Form\s*I-539', r'Application.*Extend.*Change.*Status'],
        'parts': OrderedDict([
            ('Part 1', 'Information About You'),
            ('Part 2', 'Application Type'),
            ('Part 3', 'Processing Information'),
            ('Part 4', 'Additional Information About the Applicant'),
            ('Part 5', 'Applicant\'s Statement, Contact Information, Certification, and Signature'),
            ('Part 6', 'Interpreter\'s Contact Information, Certification, and Signature'),
            ('Part 7', 'Contact Information, Declaration, and Signature of the Person Preparing This Application')
        ])
    },
    'I-140': {
        'title': 'Immigrant Petition for Alien Worker',
        'patterns': [r'Form\s*I-140', r'Immigrant.*Petition.*Worker'],
        'parts': OrderedDict([
            ('Part 1', 'Information About the Petitioner'),
            ('Part 2', 'Petition Type'),
            ('Part 3', 'Information About the Person for Whom You Are Filing'),
            ('Part 4', 'Processing Information'),
            ('Part 5', 'Additional Information About the Petitioner'),
            ('Part 6', 'Basic Information About the Proposed Employment'),
            ('Part 7', 'Information on Spouse and All Children of the Person for Whom You Are Filing'),
            ('Part 8', 'Certification'),
            ('Part 9', 'Signature'),
            ('Part 10', 'Contact Information, Declaration, and Signature of the Person Preparing This Petition')
        ])
    },
    'I-485': {
        'title': 'Application to Register Permanent Residence or Adjust Status',
        'patterns': [r'Form\s*I-485', r'Application.*Adjust.*Status'],
        'parts': OrderedDict([
            ('Part 1', 'Information About You'),
            ('Part 2', 'Application Type or Filing Category'),
            ('Part 3', 'Additional Information About You'),
            ('Part 4', 'Addresses and Telephone Numbers'),
            ('Part 5', 'Marital History'),
            ('Part 6', 'Information About Your Children'),
            ('Part 7', 'Biographic Information'),
            ('Part 8', 'General Eligibility and Inadmissibility Grounds'),
            ('Part 9', 'Accommodations for Individuals With Disabilities and/or Impairments'),
            ('Part 10', 'Applicant\'s Statement, Contact Information, Declaration, and Signature'),
            ('Part 11', 'Interpreter\'s Contact Information, Certification, and Signature'),
            ('Part 12', 'Contact Information, Declaration, and Signature of the Person Preparing This Application'),
            ('Part 13', 'Signature at Interview'),
            ('Part 14', 'Additional Information')
        ])
    },
    'I-765': {
        'title': 'Application for Employment Authorization',
        'patterns': [r'Form\s*I-765', r'Application.*Employment.*Authorization'],
        'parts': OrderedDict([
            ('Part 1', 'Reason for Applying'),
            ('Part 2', 'Information About You'),
            ('Part 3', 'Applicant\'s Statement, Contact Information, Certification, and Signature'),
            ('Part 4', 'Interpreter\'s Contact Information, Certification, and Signature'),
            ('Part 5', 'Contact Information, Declaration, and Signature of the Person Preparing This Application'),
            ('Part 6', 'Additional Information')
        ])
    },
    'I-131': {
        'title': 'Application for Travel Document',
        'patterns': [r'Form\s*I-131', r'Application.*Travel.*Document'],
        'parts': OrderedDict([
            ('Part 1', 'Information About You'),
            ('Part 2', 'Application Type'),
            ('Part 3', 'Processing Information'),
            ('Part 4', 'Information About Your Proposed Travel'),
            ('Part 5', 'Complete Only If Applying for a Reentry Permit'),
            ('Part 6', 'Complete Only If Applying for a Refugee Travel Document'),
            ('Part 7', 'Complete Only If Applying for an Advance Parole Document'),
            ('Part 8', 'Signature'),
            ('Part 9', 'Contact Information, Declaration, and Signature of the Person Preparing This Application')
        ])
    }
}

# Enhanced mapping patterns for USCIS forms
USCIS_MAPPING_PATTERNS = {
    'petitioner_info': {
        'patterns': {
            'company_name': [r'petitioner.*name', r'company.*name', r'employer.*name', r'organization'],
            'tax_id': [r'(?:fein|ein|tax.*id)', r'employer.*identification'],
            'address': [r'petitioner.*address', r'company.*address', r'mailing.*address'],
            'signatory': [r'signatory', r'authorized.*representative', r'contact.*person']
        },
        'prefix': 'customer'
    },
    'beneficiary_info': {
        'patterns': {
            'first_name': [r'given.*name', r'first.*name', r'beneficiary.*first'],
            'last_name': [r'family.*name', r'last.*name', r'surname', r'beneficiary.*last'],
            'dob': [r'date.*birth', r'birth.*date', r'd\.?o\.?b'],
            'alien_number': [r'alien.*number', r'a[\-\s]?number', r'uscis.*number'],
            'ssn': [r'social.*security', r'ssn', r'ss.*number']
        },
        'prefix': 'beneficiary.Beneficiary'
    },
    'attorney_info': {
        'patterns': {
            'last_name': [r'attorney.*last', r'preparer.*last', r'representative.*last'],
            'first_name': [r'attorney.*first', r'preparer.*first', r'representative.*first'],
            'bar_number': [r'bar.*number', r'license.*number', r'state.*bar'],
            'firm_name': [r'firm.*name', r'law.*firm', r'organization.*name']
        },
        'prefix': 'attorney.attorneyInfo'
    },
    'employment_info': {
        'patterns': {
            'job_title': [r'job.*title', r'position', r'occupation', r'employment.*title'],
            'start_date': [r'start.*date', r'begin.*date', r'employment.*start'],
            'end_date': [r'end.*date', r'employment.*end'],
            'wages': [r'wage', r'salary', r'compensation', r'pay.*rate']
        },
        'prefix': 'case'
    }
}

# Enhanced PDF extraction for USCIS forms
def extract_uscis_pdf(pdf_file) -> Tuple[List[Dict[str, Any]], OrderedDict]:
    """Extract fields from USCIS PDF forms with part organization"""
    fields = []
    form_parts = OrderedDict()
    extracted_text = ""
    processing_log = []
    
    # Reset file position
    pdf_file.seek(0)
    
    # Detect form type first
    form_type = None
    form_number = None
    
    # Try PyMuPDF first for best extraction
    if PYMUPDF_AVAILABLE:
        try:
            processing_log.append("Using PyMuPDF for extraction...")
            pdf_bytes = pdf_file.read()
            pdf_file.seek(0)
            
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            # Extract text and detect form type
            for page_num in range(min(3, len(doc))):  # Check first 3 pages
                page = doc[page_num]
                text = page.get_text()
                extracted_text += f"\n--- Page {page_num + 1} ---\n{text}"
                
                # Detect form type
                if not form_type:
                    for form_key, form_info in USCIS_FORMS.items():
                        for pattern in form_info['patterns']:
                            if re.search(pattern, text, re.IGNORECASE):
                                form_type = form_key
                                form_number = form_key
                                processing_log.append(f"Detected form type: {form_key} - {form_info['title']}")
                                break
                        if form_type:
                            break
            
            # Extract all pages text
            for page_num in range(3, len(doc)):
                page = doc[page_num]
                text = page.get_text()
                extracted_text += f"\n--- Page {page_num + 1} ---\n{text}"
            
            # Extract form fields
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Extract form widgets
                for widget in page.widgets():
                    field_name = widget.field_name
                    if field_name:
                        # Determine which part this field belongs to
                        part = determine_field_part(field_name, extracted_text, form_type)
                        
                        field_data = {
                            'name': field_name,
                            'type': map_widget_type(widget.field_type_string),
                            'value': widget.field_value or '',
                            'required': widget.field_flags & 2 != 0,
                            'page': page_num + 1,
                            'part': part,
                            'rect': list(widget.rect),
                            'source': 'PyMuPDF'
                        }
                        fields.append(field_data)
            
            doc.close()
            processing_log.append(f"Extracted {len(fields)} fields using PyMuPDF")
            
        except Exception as e:
            processing_log.append(f"PyMuPDF error: {str(e)}")
    
    # Fallback to other methods if needed
    if len(fields) < 10:
        if PDFPLUMBER_AVAILABLE:
            try:
                processing_log.append("Trying pdfplumber extraction...")
                pdf_file.seek(0)
                
                with pdfplumber.open(pdf_file) as pdf:
                    for page_num, page in enumerate(pdf.pages):
                        page_text = page.extract_text()
                        if page_text and not form_type:
                            # Detect form type
                            for form_key, form_info in USCIS_FORMS.items():
                                for pattern in form_info['patterns']:
                                    if re.search(pattern, page_text, re.IGNORECASE):
                                        form_type = form_key
                                        form_number = form_key
                                        break
                                if form_type:
                                    break
                
                processing_log.append("pdfplumber extraction completed")
                
            except Exception as e:
                processing_log.append(f"pdfplumber error: {str(e)}")
    
    # Store extracted info
    st.session_state.extracted_text = extracted_text
    st.session_state.processing_log = processing_log
    st.session_state.form_type = form_type
    st.session_state.uscis_form_number = form_number
    
    if form_type:
        st.session_state.form_name = form_type
    
    # Extract fields from text if needed
    if len(fields) < 10:
        processing_log.append("Extracting fields from text patterns...")
        text_fields = extract_fields_from_text_uscis(extracted_text, form_type)
        fields.extend(text_fields)
        processing_log.append(f"Found {len(text_fields)} additional fields from text")
    
    # Organize fields by parts
    form_parts = organize_fields_by_parts(fields, form_type)
    
    return fields, form_parts

def map_widget_type(widget_type: str) -> str:
    """Map widget types to field types"""
    type_map = {
        'Text': 'TextBox',
        'CheckBox': 'CheckBox',
        'RadioButton': 'RadioButton',
        'ListBox': 'DropDown',
        'ComboBox': 'DropDown',
        'Signature': 'Signature',
        'Button': 'Button'
    }
    return type_map.get(widget_type, 'TextBox')

def determine_field_part(field_name: str, text: str, form_type: Optional[str]) -> str:
    """Determine which part a field belongs to"""
    field_lower = field_name.lower()
    
    # Check if it's an attorney/preparer field
    attorney_keywords = ['attorney', 'preparer', 'representative', 'declaration', 'g-28']
    if any(keyword in field_lower for keyword in attorney_keywords):
        return 'Part 0 - Attorney/Preparer Information'
    
    # Try to extract part number from field name
    part_match = re.search(r'(?:part|p)[\s_\-]*(\d+)', field_lower)
    if part_match:
        part_num = part_match.group(1)
        if form_type and form_type in USCIS_FORMS:
            parts = USCIS_FORMS[form_type]['parts']
            part_key = f'Part {part_num}'
            if part_key in parts:
                return f'{part_key} - {parts[part_key]}'
    
    # Try pattern matching based on content
    if form_type and form_type in USCIS_FORMS:
        for part_key, part_desc in USCIS_FORMS[form_type]['parts'].items():
            part_keywords = part_desc.lower().split()
            if any(keyword in field_lower for keyword in part_keywords if len(keyword) > 3):
                return f'{part_key} - {part_desc}'
    
    return 'Unassigned Fields'

def extract_fields_from_text_uscis(text: str, form_type: Optional[str]) -> List[Dict[str, Any]]:
    """Extract fields from text using USCIS-specific patterns"""
    fields = []
    seen_fields = set()
    
    # USCIS-specific field patterns
    patterns = [
        # Part-based patterns
        (r'Part\s+(\d+)[\.\s]*(?:Item\s*Number\s*)?(\d+)\.?([a-z]?)[\.\s]*([A-Za-z][A-Za-z\s\-\(\)]{2,50})', 'uscis_part'),
        # Section patterns
        (r'Section\s+([A-Z])[\.\s]*(?:Item\s*)?(\d+)\.?([a-z]?)[\.\s]*([A-Za-z][A-Za-z\s\-]{2,50})', 'uscis_section'),
        # Item patterns
        (r'Item\s*(?:Number\s*)?(\d+)\.?([a-z]?)[\.\s]*([A-Za-z][A-Za-z\s\-]{2,50})', 'uscis_item'),
        # Checkbox patterns
        (r'\[\s*\]\s*([A-Za-z][A-Za-z\s\-]{2,50})', 'checkbox'),
        # Radio button patterns
        (r'\(\s*\)\s*([A-Za-z][A-Za-z\s\-]{2,50})', 'radio'),
        # Field with underscores
        (r'([A-Za-z][A-Za-z\s\-]{2,50})[\s]*:?[\s]*_{3,}', 'text_field'),
    ]
    
    for pattern, pattern_type in patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            field_name = create_field_name_uscis(match, pattern_type)
            
            if field_name and field_name.lower() not in seen_fields:
                seen_fields.add(field_name.lower())
                
                # Determine part
                if pattern_type == 'uscis_part':
                    part_num = match.group(1)
                    part = f'Part {part_num}'
                    if form_type and form_type in USCIS_FORMS:
                        parts = USCIS_FORMS[form_type]['parts']
                        if f'Part {part_num}' in parts:
                            part = f'Part {part_num} - {parts[f"Part {part_num}"]}'
                else:
                    part = determine_field_part(field_name, text, form_type)
                
                field_type = determine_field_type_uscis(field_name, pattern_type)
                
                fields.append({
                    'name': field_name,
                    'type': field_type,
                    'value': '',
                    'required': is_field_required_uscis(field_name),
                    'page': 0,
                    'part': part,
                    'source': 'text_extraction'
                })
    
    return fields

def create_field_name_uscis(match, pattern_type: str) -> str:
    """Create standardized USCIS field names"""
    if pattern_type == 'uscis_part':
        part = match.group(1)
        item = match.group(2)
        sub = match.group(3) or ''
        desc = match.group(4).strip()
        desc_clean = re.sub(r'[^\w]', '_', desc)[:30]
        return f"Part{part}_Item{item}{sub}_{desc_clean}"
    
    elif pattern_type == 'uscis_section':
        section = match.group(1)
        item = match.group(2)
        sub = match.group(3) or ''
        desc = match.group(4).strip()
        desc_clean = re.sub(r'[^\w]', '_', desc)[:30]
        return f"Section{section}_Item{item}{sub}_{desc_clean}"
    
    elif pattern_type == 'uscis_item':
        item = match.group(1)
        sub = match.group(2) or ''
        desc = match.group(3).strip()
        desc_clean = re.sub(r'[^\w]', '_', desc)[:30]
        return f"Item{item}{sub}_{desc_clean}"
    
    else:
        # Generic field name
        field_text = match.group(1).strip()
        return re.sub(r'\s+', '_', field_text)

def determine_field_type_uscis(field_name: str, pattern_type: str) -> str:
    """Determine field type for USCIS forms"""
    if pattern_type == 'checkbox':
        return 'CheckBox'
    elif pattern_type == 'radio':
        return 'RadioButton'
    
    field_lower = field_name.lower()
    
    # Type patterns
    if any(word in field_lower for word in ['date', 'dob', 'birth', 'expire']):
        return 'Date'
    elif any(word in field_lower for word in ['signature', 'sign']):
        return 'Signature'
    elif any(word in field_lower for word in ['amount', 'fee', 'wage', 'salary', '$']):
        return 'Currency'
    elif any(word in field_lower for word in ['select', 'choose', 'dropdown']):
        return 'DropDown'
    elif any(word in field_lower for word in ['describe', 'explain', 'additional', 'details']):
        return 'TextArea'
    
    return 'TextBox'

def is_field_required_uscis(field_name: str) -> bool:
    """Determine if a USCIS field is required"""
    field_lower = field_name.lower()
    
    # Required field patterns
    required_patterns = [
        'name', 'date', 'signature', 'alien number', 'a-number',
        'ssn', 'social security', 'address', 'city', 'state',
        'country', 'birth', 'citizenship'
    ]
    
    return any(pattern in field_lower for pattern in required_patterns)

def organize_fields_by_parts(fields: List[Dict], form_type: Optional[str]) -> OrderedDict:
    """Organize fields by form parts"""
    form_parts = OrderedDict()
    
    # Always add attorney section first
    form_parts['Part 0 - Attorney/Preparer Information'] = []
    
    # Add known parts for the form type
    if form_type and form_type in USCIS_FORMS:
        for part_key, part_desc in USCIS_FORMS[form_type]['parts'].items():
            form_parts[f'{part_key} - {part_desc}'] = []
    
    # Add unassigned section
    form_parts['Unassigned Fields'] = []
    
    # Organize fields into parts
    for field in fields:
        part = field.get('part', 'Unassigned Fields')
        
        # Ensure part exists
        if part not in form_parts:
            form_parts[part] = []
        
        form_parts[part].append(field)
    
    # Remove empty parts except Part 0 and Unassigned
    parts_to_keep = OrderedDict()
    for part_name, part_fields in form_parts.items():
        if part_fields or part_name in ['Part 0 - Attorney/Preparer Information', 'Unassigned Fields']:
            parts_to_keep[part_name] = part_fields
    
    return parts_to_keep

# UI Components
def render_part_container(part_name: str, part_fields: List[Dict], part_index: int):
    """Render a collapsible part container"""
    # Calculate statistics
    total = len(part_fields)
    mapped = sum(1 for f in part_fields if f['name'] in st.session_state.mapped_fields)
    questionnaire = sum(1 for f in part_fields if f['name'] in st.session_state.questionnaire_fields)
    unmapped = total - mapped - questionnaire
    
    # Check if part is expanded
    is_expanded = part_name in st.session_state.expanded_parts or st.session_state.expand_all_parts
    
    # Part header
    header_class = "attorney" if "Attorney" in part_name else ""
    
    col1, col2 = st.columns([4, 1])
    
    with col1:
        if st.button(
            f"{'▼' if is_expanded else '▶'} {part_name}",
            key=f"toggle_{part_index}",
            use_container_width=True,
            help=f"Click to {'collapse' if is_expanded else 'expand'}"
        ):
            if is_expanded:
                st.session_state.expanded_parts.discard(part_name)
            else:
                st.session_state.expanded_parts.add(part_name)
            st.rerun()
    
    with col2:
        # Statistics
        st.markdown(f"""
        <div style="text-align: right; font-size: 0.9em;">
            Total: {total} | 
            <span style="color: #2e8540;">✓ {mapped}</span> | 
            <span style="color: #00a6d2;">? {questionnaire}</span> | 
            <span style="color: #fdb81e;">○ {unmapped}</span>
        </div>
        """, unsafe_allow_html=True)
    
    # Part content (if expanded)
    if is_expanded:
        # Part actions
        if unmapped > 0:
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button(f"🤖 Auto-map all in {part_name[:6]}...", key=f"automap_{part_index}"):
                    auto_map_part_fields(part_fields)
                    st.rerun()
            with col2:
                if st.button(f"❓ All to questionnaire", key=f"quest_{part_index}"):
                    move_part_to_questionnaire(part_fields)
                    st.rerun()
            with col3:
                if st.button(f"🗑️ Remove all", key=f"remove_{part_index}"):
                    remove_part_fields(part_fields)
                    st.rerun()
        
        # Add field button
        if st.button(f"➕ Add field to {part_name[:20]}...", key=f"add_{part_index}"):
            show_add_field_form(part_name)
        
        # Show fields
        for field_idx, field in enumerate(part_fields):
            if field['name'] in st.session_state.removed_fields:
                continue
            render_field_row(field, f"{part_index}_{field_idx}")
        
        # Add some spacing
        st.markdown("<br>", unsafe_allow_html=True)

def render_field_row(field: Dict, unique_key: str):
    """Render a single field row"""
    field_name = field['name']
    field_type = field['type']
    
    # Determine status
    is_mapped = field_name in st.session_state.mapped_fields
    is_questionnaire = field_name in st.session_state.questionnaire_fields
    
    # Filter based on view settings
    if (is_mapped and not st.session_state.show_mapped) or \
       (is_questionnaire and not st.session_state.show_questionnaire) or \
       (not is_mapped and not is_questionnaire and not st.session_state.show_unmapped):
        return
    
    col1, col2, col3, col4, col5 = st.columns([3, 3, 1, 1, 1])
    
    with col1:
        # Field name and type
        status_icon = "✅" if is_mapped else "📋" if is_questionnaire else "❓"
        st.markdown(f"{status_icon} **{field_name}** `{field_type}`")
        if field.get('required'):
            st.caption("*Required")
    
    with col2:
        if is_mapped:
            # Show current mapping
            mapping = st.session_state.mapped_fields[field_name]
            if ':' in mapping:
                mapping = mapping.split(':')[0]
            st.text_input("Mapped to", value=mapping, disabled=True, key=f"mapped_{unique_key}")
        elif is_questionnaire:
            # Show questionnaire status
            st.info("In questionnaire")
        else:
            # Mapping input
            suggested_mapping = suggest_mapping_for_field(field_name)
            new_mapping = st.text_input(
                "Map to",
                placeholder=suggested_mapping or "e.g., customer.customer_name",
                key=f"map_input_{unique_key}"
            )
            if new_mapping:
                st.session_state.mapped_fields[field_name] = f"{new_mapping}:{field_type}"
                st.rerun()
    
    with col3:
        if is_mapped:
            if st.button("❌", key=f"unmap_{unique_key}", help="Remove mapping"):
                del st.session_state.mapped_fields[field_name]
                st.rerun()
        else:
            if st.button("✓", key=f"map_{unique_key}", help="Quick map with suggestion"):
                if suggested_mapping := suggest_mapping_for_field(field_name):
                    st.session_state.mapped_fields[field_name] = f"{suggested_mapping}:{field_type}"
                    st.rerun()
    
    with col4:
        if not is_questionnaire:
            if st.button("❓", key=f"quest_{unique_key}", help="Move to questionnaire"):
                st.session_state.questionnaire_fields[field_name] = {
                    'type': 'checkbox' if field_type == 'CheckBox' else 'text',
                    'required': field.get('required', False),
                    'label': beautify_field_name(field_name),
                    'options': 'Yes\nNo' if field_type == 'CheckBox' else '',
                    'validation': '',
                    'style': {"col": "12"}
                }
                st.rerun()
    
    with col5:
        if st.button("🗑️", key=f"remove_{unique_key}", help="Remove field"):
            st.session_state.removed_fields.append(field_name)
            st.rerun()

def suggest_mapping_for_field(field_name: str) -> Optional[str]:
    """Suggest mapping based on field name patterns"""
    field_lower = field_name.lower()
    field_clean = re.sub(r'[^\w\s]', ' ', field_lower).strip()
    
    # Check all mapping patterns
    for category, category_info in USCIS_MAPPING_PATTERNS.items():
        for field_type, patterns in category_info['patterns'].items():
            for pattern in patterns:
                if re.search(pattern, field_clean):
                    prefix = category_info['prefix']
                    if field_type == 'company_name':
                        return f"{prefix}.customer_name"
                    elif field_type == 'tax_id':
                        return f"{prefix}.customer_tax_id"
                    elif field_type == 'first_name':
                        return f"{prefix}.{field_type}"
                    elif field_type == 'last_name':
                        return f"{prefix}.{field_type}"
                    else:
                        return f"{prefix}.{field_type}"
    
    return None

def beautify_field_name(field_name: str) -> str:
    """Convert field name to human-readable label"""
    # Remove prefixes
    name = re.sub(r'^(Part|Section|Item|Field)\d+[_\.\s]*', '', field_name)
    # Replace underscores
    name = name.replace('_', ' ')
    # Capitalize
    name = ' '.join(word.capitalize() for word in name.split())
    return name.strip()

def auto_map_part_fields(part_fields: List[Dict]):
    """Auto-map all unmapped fields in a part"""
    for field in part_fields:
        field_name = field['name']
        if (field_name not in st.session_state.mapped_fields and 
            field_name not in st.session_state.questionnaire_fields and
            field_name not in st.session_state.removed_fields):
            
            suggested = suggest_mapping_for_field(field_name)
            if suggested:
                st.session_state.mapped_fields[field_name] = f"{suggested}:{field['type']}"

def move_part_to_questionnaire(part_fields: List[Dict]):
    """Move all unmapped fields in a part to questionnaire"""
    for field in part_fields:
        field_name = field['name']
        if (field_name not in st.session_state.mapped_fields and 
            field_name not in st.session_state.questionnaire_fields and
            field_name not in st.session_state.removed_fields):
            
            st.session_state.questionnaire_fields[field_name] = {
                'type': 'checkbox' if field['type'] == 'CheckBox' else 'text',
                'required': field.get('required', False),
                'label': beautify_field_name(field_name),
                'options': 'Yes\nNo' if field['type'] == 'CheckBox' else '',
                'validation': '',
                'style': {"col": "12"}
            }

def remove_part_fields(part_fields: List[Dict]):
    """Remove all fields in a part"""
    for field in part_fields:
        if field['name'] not in st.session_state.removed_fields:
            st.session_state.removed_fields.append(field['name'])

def show_add_field_form(part_name: str):
    """Show form to add a new field to a part"""
    with st.expander(f"Add field to {part_name}", expanded=True):
        col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
        
        with col1:
            field_name = st.text_input("Field name", placeholder="e.g., Part1_Item5a_MiddleName")
        
        with col2:
            field_type = st.selectbox("Type", ["TextBox", "CheckBox", "RadioButton", "Date", "DropDown", "TextArea"])
        
        with col3:
            is_required = st.checkbox("Required")
        
        with col4:
            if st.button("Add", type="primary"):
                if field_name:
                    new_field = {
                        'name': field_name,
                        'type': field_type,
                        'value': '',
                        'required': is_required,
                        'page': 0,
                        'part': part_name,
                        'source': 'manual'
                    }
                    st.session_state.pdf_fields.append(new_field)
                    
                    # Add to the part
                    if part_name in st.session_state.form_parts:
                        st.session_state.form_parts[part_name].append(new_field)
                    
                    st.rerun()

# Main Application
def main():
    st.title("🏛️ USCIS PDF Form Automation System")
    st.markdown("Extract and map fields from USCIS immigration forms")
    
    # Check PDF library
    if not PDF_AVAILABLE:
        st.error("❌ PDF processing library not found.")
        st.code("pip install PyPDF2 pdfplumber PyMuPDF")
        st.stop()
    
    # Sidebar
    with st.sidebar:
        st.header("📋 Form Information")
        
        if st.session_state.form_type:
            st.success(f"Form: {st.session_state.form_type}")
            if st.session_state.form_type in USCIS_FORMS:
                st.caption(USCIS_FORMS[st.session_state.form_type]['title'])
        
        st.markdown("---")
        
        # View controls
        st.header("👁️ View Options")
        col1, col2 = st.columns(2)
        with col1:
            st.session_state.show_mapped = st.checkbox("Mapped", value=True)
            st.session_state.show_questionnaire = st.checkbox("Questionnaire", value=True)
        with col2:
            st.session_state.show_unmapped = st.checkbox("Unmapped", value=True)
            st.session_state.expand_all_parts = st.checkbox("Expand all", value=False)
        
        st.markdown("---")
        
        # Statistics
        if st.session_state.pdf_fields:
            st.header("📊 Statistics")
            
            total = len(st.session_state.pdf_fields)
            mapped = len(st.session_state.mapped_fields)
            quest = len(st.session_state.questionnaire_fields)
            removed = len(st.session_state.removed_fields)
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Fields", total)
                st.metric("Mapped", mapped)
            with col2:
                st.metric("Questionnaire", quest)
                st.metric("Unmapped", total - mapped - quest - removed)
            
            # Progress
            if total > 0:
                progress = ((mapped + quest) / total) * 100
                st.progress(progress / 100)
                st.caption(f"{progress:.1f}% Complete")
        
        st.markdown("---")
        
        # Actions
        st.header("⚡ Quick Actions")
        
        if st.button("🤖 Auto-Map All", use_container_width=True, type="primary"):
            auto_map_all_fields()
            st.rerun()
        
        if st.button("🔄 Reset All", use_container_width=True):
            init_session_state()
            st.rerun()
    
    # Main content
    tab1, tab2, tab3, tab4 = st.tabs([
        "📤 Upload & Process",
        "🗂️ Field Mapping",
        "❓ Questionnaire",
        "📥 Export"
    ])
    
    # Tab 1: Upload
    with tab1:
        st.header("Upload USCIS Form")
        
        uploaded_file = st.file_uploader(
            "Choose a USCIS PDF form",
            type="pdf",
            help="Supported forms: I-129, I-539, I-140, I-485, I-765, I-131, and more"
        )
        
        if uploaded_file:
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.info(f"📄 {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")
            
            with col2:
                if st.button("🔍 Extract", type="primary", use_container_width=True):
                    with st.spinner("Extracting fields..."):
                        try:
                            fields, form_parts = extract_uscis_pdf(uploaded_file)
                            st.session_state.pdf_fields = fields
                            st.session_state.form_parts = form_parts
                            
                            if fields:
                                st.success(f"✅ Extracted {len(fields)} fields!")
                                if st.session_state.form_type:
                                    st.info(f"📋 Form Type: {st.session_state.form_type}")
                                st.rerun()
                            else:
                                st.warning("No fields found")
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
        
        # Show extraction log
        if st.session_state.processing_log:
            with st.expander("📜 Extraction Log"):
                for log in st.session_state.processing_log:
                    st.text(log)
    
    # Tab 2: Field Mapping
    with tab2:
        st.header("Field Mapping by Parts")
        
        if not st.session_state.form_parts:
            st.warning("⚠️ Please upload and extract a form first")
        else:
            # Part navigation
            for idx, (part_name, part_fields) in enumerate(st.session_state.form_parts.items()):
                render_part_container(part_name, part_fields, idx)
    
    # Tab 3: Questionnaire
    with tab3:
        st.header("Questionnaire Configuration")
        
        # Add new field
        with st.expander("➕ Add Questionnaire Field"):
            col1, col2, col3 = st.columns([3, 2, 1])
            
            with col1:
                q_label = st.text_input("Label", placeholder="e.g., Have you ever been arrested?")
            
            with col2:
                q_type = st.selectbox("Type", ["text", "checkbox", "radio", "select", "date", "textarea"])
            
            with col3:
                q_required = st.checkbox("Required", value=False)
            
            if st.button("Add Field", type="primary"):
                if q_label:
                    field_key = re.sub(r'[^\w]', '_', q_label)
                    st.session_state.questionnaire_fields[field_key] = {
                        'type': q_type,
                        'required': q_required,
                        'label': q_label,
                        'options': '',
                        'validation': '',
                        'style': {"col": "12"}
                    }
                    st.rerun()
        
        # Display questionnaire fields
        if st.session_state.questionnaire_fields:
            for field_key, config in list(st.session_state.questionnaire_fields.items()):
                with st.expander(f"{config['label']} ({config['type']})"):
                    col1, col2 = st.columns([4, 1])
                    
                    with col1:
                        config['label'] = st.text_input("Label", value=config['label'], key=f"q_label_{field_key}")
                        config['type'] = st.selectbox(
                            "Type",
                            ["text", "checkbox", "radio", "select", "date", "textarea"],
                            index=["text", "checkbox", "radio", "select", "date", "textarea"].index(config['type']),
                            key=f"q_type_{field_key}"
                        )
                        config['required'] = st.checkbox("Required", value=config.get('required', False), key=f"q_req_{field_key}")
                        
                        if config['type'] in ['radio', 'select']:
                            config['options'] = st.text_area(
                                "Options (one per line)",
                                value=config.get('options', ''),
                                key=f"q_opt_{field_key}"
                            )
                    
                    with col2:
                        if st.button("🗑️", key=f"q_del_{field_key}"):
                            del st.session_state.questionnaire_fields[field_key]
                            st.rerun()
    
    # Tab 4: Export
    with tab4:
        st.header("Export Configuration")
        
        if not st.session_state.pdf_fields:
            st.warning("⚠️ No data to export")
        else:
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📄 TypeScript Export")
                if st.button("Generate TypeScript", type="primary", use_container_width=True):
                    ts_content = generate_typescript_uscis()
                    st.download_button(
                        "📥 Download TypeScript",
                        data=ts_content,
                        file_name=f"{st.session_state.form_name or 'USCIS_Form'}.ts",
                        mime="text/plain"
                    )
                    with st.expander("Preview"):
                        st.code(ts_content, language="typescript")
            
            with col2:
                st.subheader("📋 JSON Export")
                if st.button("Generate JSON", type="primary", use_container_width=True):
                    json_content = generate_json_uscis()
                    st.download_button(
                        "📥 Download JSON",
                        data=json_content,
                        file_name=f"{st.session_state.form_name or 'USCIS_Form'}.json",
                        mime="application/json"
                    )
                    with st.expander("Preview"):
                        st.code(json_content, language="json")

def auto_map_all_fields():
    """Auto-map all unmapped fields"""
    mapped_count = 0
    
    for field in st.session_state.pdf_fields:
        field_name = field['name']
        if (field_name not in st.session_state.mapped_fields and 
            field_name not in st.session_state.questionnaire_fields and
            field_name not in st.session_state.removed_fields):
            
            # Checkboxes go to questionnaire
            if field['type'] in ['CheckBox', 'RadioButton']:
                st.session_state.questionnaire_fields[field_name] = {
                    'type': 'checkbox' if field['type'] == 'CheckBox' else 'radio',
                    'required': field.get('required', False),
                    'label': beautify_field_name(field_name),
                    'options': 'Yes\nNo' if field['type'] == 'CheckBox' else '',
                    'validation': '',
                    'style': {"col": "12"}
                }
                mapped_count += 1
            else:
                # Try to map
                suggested = suggest_mapping_for_field(field_name)
                if suggested:
                    st.session_state.mapped_fields[field_name] = f"{suggested}:{field['type']}"
                    mapped_count += 1
    
    return mapped_count

def generate_typescript_uscis() -> str:
    """Generate TypeScript configuration for USCIS forms"""
    form_name = st.session_state.form_name or 'USCISForm'
    form_name_clean = re.sub(r'[^\w]', '', form_name)
    
    # Organize mapped fields by category
    categories = defaultdict(dict)
    for field_name, mapping in st.session_state.mapped_fields.items():
        if ':' in mapping:
            mapping_path, field_type = mapping.split(':', 1)
        else:
            mapping_path = mapping
            field_type = 'TextBox'
        
        # Determine category
        if mapping_path.startswith('customer'):
            categories['customerData'][field_name] = f"{mapping_path}:{field_type}"
        elif mapping_path.startswith('beneficiary'):
            categories['beneficiaryData'][field_name] = f"{mapping_path}:{field_type}"
        elif mapping_path.startswith('attorney'):
            categories['attorneyData'][field_name] = f"{mapping_path}:{field_type}"
        else:
            categories['otherData'][field_name] = f"{mapping_path}:{field_type}"
    
    # Format questionnaire
    questionnaire_data = {}
    for field_name, config in st.session_state.questionnaire_fields.items():
        questionnaire_data[field_name] = {
            'type': config['type'],
            'label': config['label'],
            'required': config.get('required', False)
        }
    
    # Generate TypeScript
    ts_content = f"""// Auto-generated USCIS form configuration
// Form: {form_name}
// Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

export const {form_name_clean} = {{
    formname: "{form_name_clean}",
    formType: "{st.session_state.form_type or 'Unknown'}",
    customerData: {json.dumps(categories.get('customerData', {}), indent=8) if categories.get('customerData') else 'null'},
    beneficiaryData: {json.dumps(categories.get('beneficiaryData', {}), indent=8) if categories.get('beneficiaryData') else 'null'},
    attorneyData: {json.dumps(categories.get('attorneyData', {}), indent=8) if categories.get('attorneyData') else 'null'},
    otherData: {json.dumps(categories.get('otherData', {}), indent=8) if categories.get('otherData') else 'null'},
    questionnaireData: {json.dumps(questionnaire_data, indent=8)},
    metadata: {{
        totalFields: {len(st.session_state.pdf_fields)},
        mappedFields: {len(st.session_state.mapped_fields)},
        questionnaireFields: {len(st.session_state.questionnaire_fields)},
        extractedFrom: "{st.session_state.form_type or 'Unknown USCIS Form'}"
    }}
}};

export default {form_name_clean};"""
    
    return ts_content

def generate_json_uscis() -> str:
    """Generate JSON configuration for USCIS forms"""
    config = {
        "formName": st.session_state.form_name or "USCISForm",
        "formType": st.session_state.form_type,
        "mappedFields": st.session_state.mapped_fields,
        "questionnaireFields": st.session_state.questionnaire_fields,
        "formStructure": {
            part_name: [f['name'] for f in fields]
            for part_name, fields in st.session_state.form_parts.items()
        },
        "metadata": {
            "totalFields": len(st.session_state.pdf_fields),
            "mappedFields": len(st.session_state.mapped_fields),
            "questionnaireFields": len(st.session_state.questionnaire_fields),
            "timestamp": datetime.now().isoformat()
        }
    }
    
    return json.dumps(config, indent=2)

# Run the application
if __name__ == "__main__":
    main()
