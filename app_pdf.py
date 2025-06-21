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

# Page configuration with custom theme
st.set_page_config(
    page_title="PDF Form Automation System",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Enhanced Custom CSS with modern design
st.markdown("""
<style>
    /* Modern Color Scheme */
    :root {
        --primary-color: #1e40af;
        --secondary-color: #3730a3;
        --success-color: #059669;
        --warning-color: #d97706;
        --danger-color: #dc2626;
        --info-color: #0891b2;
        --light-bg: #f8fafc;
        --card-bg: #ffffff;
        --border-color: #e5e7eb;
        --text-primary: #111827;
        --text-secondary: #6b7280;
    }
    
    /* Global Styles */
    .stApp {
        background-color: var(--light-bg);
    }
    
    /* Enhanced Buttons */
    .stButton > button {
        width: 100%;
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.3s ease;
        border: 1px solid var(--border-color);
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    }
    
    /* Field Status Cards */
    .field-card {
        background: var(--card-bg);
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 12px;
        border: 1px solid var(--border-color);
        transition: all 0.3s ease;
    }
    
    .field-card:hover {
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
        transform: translateY(-2px);
    }
    
    .field-mapped {
        border-left: 4px solid var(--success-color);
        background: linear-gradient(to right, rgba(5, 150, 105, 0.05), transparent);
    }
    
    .field-questionnaire {
        border-left: 4px solid var(--info-color);
        background: linear-gradient(to right, rgba(8, 145, 178, 0.05), transparent);
    }
    
    .field-unmapped {
        border-left: 4px solid var(--warning-color);
        background: linear-gradient(to right, rgba(217, 119, 6, 0.05), transparent);
    }
    
    .field-removed {
        border-left: 4px solid var(--danger-color);
        background: linear-gradient(to right, rgba(220, 38, 38, 0.05), transparent);
        opacity: 0.6;
    }
    
    /* Part Headers */
    .part-header {
        background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
        color: white;
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 20px;
        font-weight: 600;
        font-size: 1.2em;
        box-shadow: 0 4px 12px rgba(30, 64, 175, 0.2);
    }
    
    /* Statistics Cards */
    div[data-testid="metric-container"] {
        background: var(--card-bg);
        border: 1px solid var(--border-color);
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
        transition: all 0.3s ease;
    }
    
    div[data-testid="metric-container"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    }
    
    /* Field Type Badges */
    .field-type-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.85em;
        font-weight: 500;
        margin-left: 8px;
    }
    
    .field-type-text { background: #dbeafe; color: #1e40af; }
    .field-type-checkbox { background: #fce7f3; color: #be185d; }
    .field-type-radio { background: #e0e7ff; color: #4338ca; }
    .field-type-date { background: #fed7aa; color: #c2410c; }
    .field-type-dropdown { background: #d1fae5; color: #047857; }
    
    /* Progress Bar */
    .progress-container {
        background: var(--card-bg);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
    }
    
    .progress-bar {
        background: #e5e7eb;
        height: 12px;
        border-radius: 6px;
        overflow: hidden;
        margin-top: 10px;
    }
    
    .progress-fill {
        height: 100%;
        background: linear-gradient(to right, var(--primary-color), var(--secondary-color));
        transition: width 0.5s ease;
    }
    
    /* Questionnaire Section */
    .questionnaire-item {
        background: var(--card-bg);
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
        border: 1px solid var(--border-color);
    }
    
    /* Tabs Enhancement */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: var(--card-bg);
        padding: 8px;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        padding: 8px 16px;
        font-weight: 500;
    }
    
    /* Expander Enhancement */
    .streamlit-expanderHeader {
        background: var(--card-bg);
        border-radius: 8px;
        font-weight: 500;
    }
    
    /* PDF Viewer Container */
    .pdf-preview {
        background: var(--card-bg);
        border: 2px dashed var(--border-color);
        border-radius: 12px;
        padding: 40px;
        text-align: center;
        margin-bottom: 20px;
    }
    
    /* Field Preview Grid */
    .field-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
        gap: 16px;
        margin-top: 20px;
    }
    
    /* Action Buttons Group */
    .action-buttons {
        display: flex;
        gap: 12px;
        margin: 20px 0;
        flex-wrap: wrap;
    }
    
    .action-buttons > div {
        flex: 1;
        min-width: 200px;
    }
</style>
""", unsafe_allow_html=True)

# Enhanced session state initialization
def init_session_state():
    """Initialize all session state variables with enhanced structure"""
    defaults = {
        'pdf_fields': [],
        'pdf_structure': {},  # Store PDF structure by parts
        'mapped_fields': {},
        'questionnaire_fields': {},
        'conditional_fields': {},
        'default_fields': {},
        'field_groups': {},
        'validation_rules': {},
        'form_metadata': {},
        'extracted_text': "",
        'form_name': 'UnknownForm',
        'form_type': None,  # I-129, I-539, etc.
        'current_step': 1,
        'auto_save': True,
        'show_removed_fields': False,
        'removed_fields': [],
        'extraction_method': None,
        'extraction_errors': [],
        'field_statistics': {},
        'form_parts': OrderedDict(),  # Store form parts in order
        'mapping_suggestions': {},
        'processing_log': []
    }
    
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

init_session_state()

# Enhanced Form Recognition Patterns
FORM_PATTERNS = {
    'I-129': {
        'patterns': [r'Form I-129', r'Petition for a Nonimmigrant Worker'],
        'parts': {
            'Part 1': 'Information About the Petitioner',
            'Part 2': 'Information About This Petition',
            'Part 3': 'Beneficiary Information',
            'Part 4': 'Processing Information',
            'Part 5': 'Basic Information About the Proposed Employment and Employer',
            'Part 6': 'Signature',
            'Part 7': 'Additional Information',
            'Part 8': 'Preparer and/or Translator Certification'
        }
    },
    'I-539': {
        'patterns': [r'Form I-539', r'Application To Extend/Change Nonimmigrant Status'],
        'parts': {
            'Part 1': 'Information About You',
            'Part 2': 'Application Type',
            'Part 3': 'Processing Information',
            'Part 4': 'Additional Information About the Applicant',
            'Part 5': 'Contact Information',
            'Part 6': 'Signature',
            'Part 7': 'Preparer and/or Translator Certification'
        }
    },
    'LCA': {
        'patterns': [r'Form ETA[\s-]?9035', r'Labor Condition Application'],
        'parts': {
            'Section A': 'Visa Information',
            'Section B': 'Temporary Need Information',
            'Section C': 'Employer Information',
            'Section D': 'Employer Point of Contact',
            'Section E': 'Attorney or Agent Information',
            'Section F': 'Employment and Wage Information',
            'Section G': 'Employer Labor Condition Statements',
            'Section H': 'Additional Employer Labor Condition Statements',
            'Section I': 'Public Disclosure Information',
            'Section J': 'Declaration of Employer'
        }
    }
}

# Enhanced mapping patterns with database paths
ENHANCED_MAPPING_PATTERNS = {
    # Customer/Petitioner patterns
    'customer_patterns': {
        'customer_name': {
            'patterns': [
                r'petitioner.*name', r'company.*name', r'employer.*name',
                r'organization.*name', r'business.*name', r'legal.*name'
            ],
            'mapping': 'customer.customer_name',
            'type': 'TextBox',
            'priority': 1
        },
        'customer_tax_id': {
            'patterns': [
                r'(?:fein|ein|tax.*id|employer.*id.*number|federal.*tax)',
                r'i\.?r\.?s\.?\s*no', r'tax.*identification'
            ],
            'mapping': 'customer.customer_tax_id',
            'type': 'TextBox',
            'priority': 1
        },
        'customer_address': {
            'patterns': [
                r'petitioner.*address', r'company.*address', r'employer.*address',
                r'business.*address', r'mailing.*address'
            ],
            'mapping': 'customer.address_street',
            'type': 'TextBox',
            'priority': 2
        }
    },
    
    # Beneficiary patterns
    'beneficiary_patterns': {
        'beneficiary_first': {
            'patterns': [
                r'beneficiary.*first.*name', r'given.*name', r'employee.*first',
                r'worker.*first', r'applicant.*first'
            ],
            'mapping': 'beneficiary.Beneficiary.beneficiaryFirstName',
            'type': 'TextBox',
            'priority': 1
        },
        'beneficiary_last': {
            'patterns': [
                r'beneficiary.*last.*name', r'family.*name', r'surname',
                r'employee.*last', r'worker.*last'
            ],
            'mapping': 'beneficiary.Beneficiary.beneficiaryLastName',
            'type': 'TextBox',
            'priority': 1
        },
        'beneficiary_dob': {
            'patterns': [
                r'date.*birth', r'birth.*date', r'd\.?o\.?b\.?',
                r'born.*on', r'birthday'
            ],
            'mapping': 'beneficiary.Beneficiary.beneficiaryDateOfBirth',
            'type': 'Date',
            'priority': 1
        }
    }
}

# Enhanced PDF extraction with multiple methods
def extract_pdf_enhanced(pdf_file) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Enhanced PDF extraction using multiple methods"""
    fields = []
    structure = {}
    extracted_text = ""
    extraction_log = []
    
    # Reset file position
    pdf_file.seek(0)
    
    # Method 1: Try PyMuPDF first (best extraction)
    if PYMUPDF_AVAILABLE:
        try:
            extraction_log.append("Trying PyMuPDF extraction...")
            pdf_bytes = pdf_file.read()
            pdf_file.seek(0)
            
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Extract text
                text = page.get_text()
                extracted_text += f"\n--- Page {page_num + 1} ---\n{text}"
                
                # Extract form fields
                for widget in page.widgets():
                    field_name = widget.field_name
                    field_type = widget.field_type_string
                    field_value = widget.field_value
                    
                    if field_name:
                        fields.append({
                            'name': field_name,
                            'type': map_widget_type(field_type),
                            'value': field_value or '',
                            'required': widget.field_flags & 2 != 0,  # Required flag
                            'page': page_num + 1,
                            'rect': list(widget.rect),
                            'source': 'PyMuPDF'
                        })
            
            doc.close()
            extraction_log.append(f"PyMuPDF: Extracted {len(fields)} fields")
            
        except Exception as e:
            extraction_log.append(f"PyMuPDF error: {str(e)}")
    
    # Method 2: Try pdfplumber (good for text extraction)
    if PDFPLUMBER_AVAILABLE and len(fields) < 10:
        try:
            extraction_log.append("Trying pdfplumber extraction...")
            pdf_file.seek(0)
            
            with pdfplumber.open(pdf_file) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    # Extract text
                    page_text = page.extract_text()
                    if page_text:
                        extracted_text += f"\n--- Page {page_num + 1} (pdfplumber) ---\n{page_text}"
                    
                    # Extract form elements
                    if hasattr(page, 'annots') and page.annots:
                        for annot in page.annots:
                            if annot.get('data', {}).get('Subtype') == '/Widget':
                                field_name = annot.get('data', {}).get('T', '')
                                if field_name and not any(f['name'] == field_name for f in fields):
                                    fields.append({
                                        'name': field_name,
                                        'type': 'TextBox',
                                        'value': '',
                                        'required': False,
                                        'page': page_num + 1,
                                        'source': 'pdfplumber'
                                    })
            
            extraction_log.append(f"pdfplumber: Extracted additional fields")
            
        except Exception as e:
            extraction_log.append(f"pdfplumber error: {str(e)}")
    
    # Method 3: Standard PyPDF2/pypdf
    if PDF_AVAILABLE and len(fields) < 10:
        try:
            extraction_log.append(f"Trying {PDF_LIBRARY} extraction...")
            pdf_file.seek(0)
            
            pdf_reader = PdfReader(pdf_file)
            
            # Extract text from all pages
            for page_num, page in enumerate(pdf_reader.pages):
                page_text = page.extract_text()
                extracted_text += f"\n--- Page {page_num + 1} ({PDF_LIBRARY}) ---\n{page_text}"
            
            # Extract form fields
            if hasattr(pdf_reader, 'get_fields'):
                pdf_fields = pdf_reader.get_fields()
                if pdf_fields:
                    for field_name, field_obj in pdf_fields.items():
                        if not any(f['name'] == field_name for f in fields):
                            field_type = determine_pypdf_field_type(field_obj)
                            fields.append({
                                'name': field_name,
                                'type': field_type,
                                'value': field_obj.get('/V', '') if isinstance(field_obj, dict) else '',
                                'required': bool(field_obj.get('/Ff', 0) & 2) if isinstance(field_obj, dict) else False,
                                'page': 0,
                                'source': PDF_LIBRARY
                            })
            
            extraction_log.append(f"{PDF_LIBRARY}: Extracted {len(fields)} fields")
            
        except Exception as e:
            extraction_log.append(f"{PDF_LIBRARY} error: {str(e)}")
    
    # Store extracted text
    st.session_state.extracted_text = extracted_text
    st.session_state.processing_log = extraction_log
    
    # Detect form type
    form_type = detect_form_type(extracted_text)
    st.session_state.form_type = form_type
    
    # Extract fields from text if needed
    if len(fields) < 10:
        extraction_log.append("Attempting text-based field extraction...")
        text_fields = extract_fields_from_text_enhanced(extracted_text, form_type)
        fields.extend(text_fields)
        extraction_log.append(f"Text extraction: Found {len(text_fields)} additional fields")
    
    # Organize fields by parts
    structure = organize_fields_by_form_structure(fields, extracted_text, form_type)
    
    return fields, structure

def map_widget_type(widget_type: str) -> str:
    """Map PyMuPDF widget types to our field types"""
    type_map = {
        'Text': 'TextBox',
        'CheckBox': 'CheckBox',
        'RadioButton': 'RadioButton',
        'ListBox': 'DropDown',
        'ComboBox': 'DropDown',
        'Signature': 'Signature'
    }
    return type_map.get(widget_type, 'TextBox')

def determine_pypdf_field_type(field_obj: Any) -> str:
    """Determine field type from PyPDF2/pypdf field object"""
    if not isinstance(field_obj, dict):
        return 'TextBox'
    
    field_type = field_obj.get('/FT')
    field_flags = field_obj.get('/Ff', 0)
    
    if field_type == '/Btn':
        if field_flags & 65536:  # Radio button
            return 'RadioButton'
        else:
            return 'CheckBox'
    elif field_type == '/Ch':
        return 'DropDown'
    elif field_type == '/Sig':
        return 'Signature'
    
    return 'TextBox'

def detect_form_type(text: str) -> Optional[str]:
    """Detect the form type from extracted text"""
    text_lower = text.lower()
    
    for form_name, form_info in FORM_PATTERNS.items():
        for pattern in form_info['patterns']:
            if re.search(pattern, text, re.IGNORECASE):
                return form_name
    
    return None

def extract_fields_from_text_enhanced(text: str, form_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """Enhanced text-based field extraction with form-specific patterns"""
    fields = []
    seen_fields = set()
    
    # Form-specific patterns
    if form_type == 'I-129':
        patterns = [
            (r'Part\s+(\d+)\.?\s*(?:Item\s*)?(\d+)([a-z]?)\.?\s*([A-Za-z][A-Za-z\s\-]{2,50})', 'i129_part'),
            (r'Section\s+(\d+)\.?\s*(?:Item\s*)?(\d+)([a-z]?)\.?\s*([A-Za-z][A-Za-z\s\-]{2,50})', 'i129_section'),
        ]
    elif form_type == 'LCA':
        patterns = [
            (r'([A-Z])\.\s*(\d+)\.?\s*([A-Za-z][A-Za-z\s\-]{2,50})', 'lca_field'),
            (r'Section\s+([A-Z])\.?\s*(?:Item\s*)?(\d+)([a-z]?)\.?\s*([A-Za-z][A-Za-z\s\-]{2,50})', 'lca_section'),
        ]
    else:
        patterns = []
    
    # Add generic patterns
    patterns.extend([
        (r'(?:P|Part)\s*(\d+)[_\.\s]+(\d+)([a-z]?)\.?\s*([A-Za-z][A-Za-z\s]{2,50})', 'form_section'),
        (r'(\d+)\.([a-z]?\.)?\s*([A-Za-z][A-Za-z\s]{2,50})(?:\s*:?\s*(?:_{3,}|\[[\s]*\]))', 'numbered'),
        (r'([A-Za-z][A-Za-z\s\-]{2,50})(?:\s*:?\s*)(?:_{3,})', 'underscore'),
        (r'\[\s*\]\s*([A-Za-z][A-Za-z\s\-]{2,50})', 'checkbox'),
        (r'\(\s*\)\s*([A-Za-z][A-Za-z\s\-]{2,50})', 'radio'),
    ])
    
    # Extract fields based on patterns
    for pattern, pattern_type in patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            field_name = extract_field_name_from_match(match, pattern_type)
            
            if field_name and len(field_name) > 3 and field_name.lower() not in seen_fields:
                seen_fields.add(field_name.lower())
                
                field_type = determine_field_type_enhanced(field_name, text, pattern_type)
                
                fields.append({
                    'name': field_name,
                    'type': field_type,
                    'value': '',
                    'required': is_field_required_enhanced(field_name, text),
                    'page': 0,
                    'part': extract_part_from_match(match, pattern_type),
                    'source': 'text_extraction'
                })
    
    return fields

def extract_field_name_from_match(match, pattern_type: str) -> str:
    """Extract field name from regex match based on pattern type"""
    if pattern_type in ['i129_part', 'i129_section']:
        part = match.group(1)
        number = match.group(2)
        letter = match.group(3) or ''
        label = match.group(4).strip()
        return f"Part{part}_Item{number}{letter}_{re.sub(r'[^\w]', '', label)}"
    
    elif pattern_type == 'lca_field':
        section = match.group(1)
        number = match.group(2)
        label = match.group(3).strip()
        return f"Section{section}_{number}_{re.sub(r'[^\w]', '', label)}"
    
    elif pattern_type == 'form_section':
        part = match.group(1)
        number = match.group(2)
        letter = match.group(3) or ''
        label = match.group(4).strip()
        return f"P{part}_{number}{letter}_{re.sub(r'[^\w]', '', label)}"
    
    else:
        # Generic extraction
        if pattern_type in ['checkbox', 'radio', 'underscore']:
            return re.sub(r'\s+', '_', match.group(1).strip())
        else:
            return re.sub(r'\s+', '_', match.group(0).strip())

def extract_part_from_match(match, pattern_type: str) -> str:
    """Extract part/section information from match"""
    if pattern_type in ['i129_part', 'form_section']:
        return f"Part {match.group(1)}"
    elif pattern_type in ['lca_section', 'lca_field']:
        return f"Section {match.group(1)}"
    return "General"

def determine_field_type_enhanced(field_name: str, context: str, pattern_type: str) -> str:
    """Enhanced field type determination"""
    field_lower = field_name.lower()
    
    # Pattern-based type determination
    if pattern_type == 'checkbox':
        return 'CheckBox'
    elif pattern_type == 'radio':
        return 'RadioButton'
    
    # Enhanced type detection
    type_patterns = {
        'Date': [
            r'date', r'd\.?o\.?b', r'birth', r'expire', r'expiry',
            r'mm[/\-]dd[/\-]yyyy', r'\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}'
        ],
        'CheckBox': [
            r'check\s*box', r'\[\s*\]', r'yes[\s/]*no', r'select.*applicable'
        ],
        'RadioButton': [
            r'radio', r'\(\s*\)', r'select\s*one', r'choose\s*one'
        ],
        'DropDown': [
            r'select', r'choose.*from', r'dropdown', r'list'
        ],
        'Currency': [
            r'salary', r'wage', r'compensation', r'amount', r'fee', r'\$'
        ],
        'Signature': [
            r'signature', r'sign(?:ed)?\s*by'
        ],
        'TextArea': [
            r'describe', r'explain', r'details', r'comments', r'additional\s*information'
        ]
    }
    
    for field_type, patterns in type_patterns.items():
        for pattern in patterns:
            if re.search(pattern, field_lower):
                return field_type
    
    return 'TextBox'

def is_field_required_enhanced(field_name: str, context: str) -> bool:
    """Enhanced required field detection"""
    field_lower = field_name.lower()
    
    # Required indicators in field name
    if any(indicator in field_lower for indicator in ['required', 'mandatory', 'must']):
        return True
    
    # Common required fields
    required_fields = [
        'name', 'date', 'signature', 'ssn', 'ein', 'address',
        'email', 'phone', 'alien.*number', 'passport', 'visa'
    ]
    
    for req_pattern in required_fields:
        if re.search(req_pattern, field_lower):
            return True
    
    # Check context around field
    if context:
        field_context = context[max(0, context.find(field_name) - 100):context.find(field_name) + 100]
        if any(word in field_context.lower() for word in ['required', 'mandatory', 'must provide']):
            return True
    
    return False

def organize_fields_by_form_structure(fields: List[Dict], text: str, form_type: Optional[str]) -> Dict[str, List[Dict]]:
    """Organize fields by form structure/parts"""
    structure = OrderedDict()
    
    if form_type and form_type in FORM_PATTERNS:
        # Initialize with known parts
        for part_name, part_desc in FORM_PATTERNS[form_type]['parts'].items():
            structure[f"{part_name} - {part_desc}"] = []
    
    # Add general sections
    structure['Unmapped Fields'] = []
    structure['Text-Extracted Fields'] = []
    
    # Organize fields
    for field in fields:
        assigned = False
        
        # Try to assign to a specific part
        if 'part' in field and field['part'] != 'General':
            part_key = None
            for key in structure.keys():
                if field['part'] in key:
                    part_key = key
                    break
            
            if part_key:
                structure[part_key].append(field)
                assigned = True
        
        # If not assigned, try pattern matching
        if not assigned:
            field_lower = field['name'].lower()
            for part_key in structure.keys():
                if any(keyword in field_lower for keyword in part_key.lower().split()):
                    structure[part_key].append(field)
                    assigned = True
                    break
        
        # Default assignment
        if not assigned:
            if field['source'] == 'text_extraction':
                structure['Text-Extracted Fields'].append(field)
            else:
                structure['Unmapped Fields'].append(field)
    
    # Remove empty sections
    structure = OrderedDict((k, v) for k, v in structure.items() if v)
    
    return structure

# UI Helper Functions
def render_field_card(field: Dict[str, Any], index: int):
    """Render a field card with enhanced UI"""
    field_name = field['name']
    field_type = field['type']
    
    # Determine field status
    status = 'unmapped'
    status_icon = '❓'
    if field_name in st.session_state.removed_fields:
        status = 'removed'
        status_icon = '🗑️'
    elif field_name in st.session_state.mapped_fields:
        status = 'mapped'
        status_icon = '✅'
    elif field_name in st.session_state.questionnaire_fields:
        status = 'questionnaire'
        status_icon = '📋'
    
    # Render card
    with st.container():
        st.markdown(f"""
        <div class="field-card field-{status}">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <strong>{status_icon} {field_name}</strong>
                    <span class="field-type-badge field-type-{field_type.lower()}">{field_type}</span>
                </div>
                <div style="text-align: right;">
                    {f'<small>Page {field["page"]}</small>' if field.get("page") else ''}
                    {f'<small style="color: var(--danger-color);">Required</small>' if field.get("required") else ''}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

def render_progress_bar():
    """Render progress bar showing field processing status"""
    total = len(st.session_state.pdf_fields)
    if total == 0:
        return
    
    mapped = len(st.session_state.mapped_fields)
    questionnaire = len(st.session_state.questionnaire_fields)
    removed = len(st.session_state.removed_fields)
    unmapped = total - mapped - questionnaire - removed
    
    progress = ((mapped + questionnaire) / total) * 100
    
    st.markdown(f"""
    <div class="progress-container">
        <h4>Processing Progress</h4>
        <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
            <span>✅ Mapped: {mapped}</span>
            <span>📋 Questionnaire: {questionnaire}</span>
            <span>❓ Unmapped: {unmapped}</span>
            <span>🗑️ Removed: {removed}</span>
        </div>
        <div class="progress-bar">
            <div class="progress-fill" style="width: {progress}%"></div>
        </div>
        <div style="text-align: center; margin-top: 10px;">
            <strong>{progress:.1f}% Complete</strong>
        </div>
    </div>
    """, unsafe_allow_html=True)

def auto_map_fields_enhanced():
    """Enhanced auto-mapping with better pattern matching"""
    mapped_count = 0
    suggestions = {}
    
    for field in st.session_state.pdf_fields:
        field_name = field['name']
        
        # Skip if already processed
        if (field_name in st.session_state.mapped_fields or 
            field_name in st.session_state.questionnaire_fields or
            field_name in st.session_state.removed_fields):
            continue
        
        # Find best mapping
        best_mapping = None
        best_score = 0
        best_category = None
        
        for category, patterns in ENHANCED_MAPPING_PATTERNS.items():
            for pattern_key, pattern_info in patterns.items():
                score = calculate_mapping_score(field_name, pattern_info)
                if score > best_score:
                    best_score = score
                    best_mapping = pattern_info['mapping']
                    best_category = category
        
        # Apply mapping or add to questionnaire
        if best_score >= 0.8:
            st.session_state.mapped_fields[field_name] = f"{best_mapping}:{field['type']}"
            mapped_count += 1
        elif best_score >= 0.5:
            # Store as suggestion
            suggestions[field_name] = {
                'mapping': best_mapping,
                'score': best_score,
                'category': best_category
            }
        else:
            # Auto-add to questionnaire if checkbox or radio
            if field['type'] in ['CheckBox', 'RadioButton']:
                st.session_state.questionnaire_fields[field_name] = {
                    'type': 'checkbox' if field['type'] == 'CheckBox' else 'radio',
                    'required': field.get('required', False),
                    'options': 'Yes\nNo' if field['type'] == 'CheckBox' else '',
                    'validation': '',
                    'label': beautify_field_name(field_name),
                    'style': {"col": "12"}
                }
    
    st.session_state.mapping_suggestions = suggestions
    return mapped_count

def calculate_mapping_score(field_name: str, pattern_info: Dict) -> float:
    """Calculate mapping score based on pattern matching"""
    field_clean = re.sub(r'[^\w\s]', ' ', field_name.lower()).strip()
    best_score = 0
    
    for pattern in pattern_info['patterns']:
        if re.search(pattern, field_clean):
            # Calculate score based on match quality
            match = re.search(pattern, field_clean)
            match_ratio = len(match.group()) / len(field_clean)
            score = 0.6 + (0.4 * match_ratio)
            
            # Boost score for exact matches
            if pattern == field_clean:
                score = 1.0
            
            # Apply priority boost
            score *= pattern_info.get('priority', 1)
            
            best_score = max(best_score, score)
    
    return best_score

def beautify_field_name(field_name: str) -> str:
    """Convert field name to human-readable label"""
    # Remove common prefixes
    name = re.sub(r'^(Part|Section|Item|Field|P)\d+[_\.]?', '', field_name)
    # Replace underscores with spaces
    name = name.replace('_', ' ')
    # Capitalize words
    name = ' '.join(word.capitalize() for word in name.split())
    return name.strip()

# Main Application UI
def main():
    st.title("📄 Enhanced PDF Form Automation System")
    st.markdown("Extract fields from PDF forms and generate TypeScript configurations with intelligent mapping")
    
    # Check PDF library availability
    if not PDF_AVAILABLE:
        st.error("❌ PDF processing library not found. Please install PyPDF2 or pypdf:")
        st.code("pip install PyPDF2")
        st.info("For better extraction, also install:")
        st.code("pip install pdfplumber PyMuPDF")
        st.stop()
    
    # Sidebar with enhanced statistics
    with st.sidebar:
        st.header("🔧 Configuration")
        
        # Form name and type
        col1, col2 = st.columns(2)
        with col1:
            form_name = st.text_input(
                "Form Name",
                value=st.session_state.get('form_name', 'UnknownForm'),
                help="Enter the form name (e.g., I129, I539, H2B)"
            )
            st.session_state.form_name = form_name
        
        with col2:
            if st.session_state.form_type:
                st.text_input("Detected Type", value=st.session_state.form_type, disabled=True)
        
        st.markdown("---")
        
        # Statistics
        if st.session_state.pdf_fields:
            st.header("📊 Field Statistics")
            render_progress_bar()
            
            # Field type breakdown
            if st.session_state.field_statistics:
                st.subheader("Field Types")
                for field_type, count in st.session_state.field_statistics.items():
                    st.metric(field_type, count)
        
        st.markdown("---")
        
        # Tools
        st.header("🛠️ Quick Actions")
        
        if st.button("🤖 Auto-Map All", use_container_width=True, type="primary"):
            count = auto_map_fields_enhanced()
            st.success(f"✅ Auto-mapped {count} fields")
            if st.session_state.mapping_suggestions:
                st.info(f"💡 {len(st.session_state.mapping_suggestions)} fields have mapping suggestions")
            st.rerun()
        
        if st.button("🔄 Reset All", use_container_width=True):
            for key in st.session_state:
                if key not in ['form_name']:
                    st.session_state[key] = {} if 'fields' in key else []
            st.rerun()
        
        st.toggle("Show Removed Fields", key="show_removed_fields")
        st.toggle("Show Extraction Log", key="show_extraction_log")
    
    # Main content tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📤 Upload & Extract",
        "🗂️ Field Mapping",
        "❓ Questionnaire",
        "⚙️ Advanced Settings",
        "📥 Generate & Export"
    ])
    
    # Tab 1: Upload & Extract
    with tab1:
        st.header("Step 1: Upload PDF and Extract Fields")
        
        # File upload with preview
        col1, col2 = st.columns([2, 1])
        
        with col1:
            uploaded_file = st.file_uploader(
                "Choose a PDF file",
                type="pdf",
                help="Upload a PDF form to extract fields automatically"
            )
            
            if uploaded_file:
                st.success(f"📄 Uploaded: {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")
        
        with col2:
            if uploaded_file:
                if st.button("🔍 Extract Fields", type="primary", use_container_width=True):
                    with st.spinner("Extracting fields from PDF..."):
                        try:
                            fields, structure = extract_pdf_enhanced(uploaded_file)
                            st.session_state.pdf_fields = fields
                            st.session_state.pdf_structure = structure
                            
                            # Calculate statistics
                            stats = defaultdict(int)
                            for field in fields:
                                stats[field['type']] += 1
                            st.session_state.field_statistics = dict(stats)
                            
                            if fields:
                                st.success(f"✅ Successfully extracted {len(fields)} fields!")
                                st.info(f"📋 Form Type: {st.session_state.form_type or 'Unknown'}")
                                
                                # Auto-process
                                mapped = auto_map_fields_enhanced()
                                if mapped > 0:
                                    st.success(f"🤖 Auto-mapped {mapped} fields")
                                
                                st.rerun()
                            else:
                                st.warning("⚠️ No fields could be extracted from the PDF")
                                
                        except Exception as e:
                            st.error(f"❌ Error extracting fields: {str(e)}")
                            st.exception(e)
        
        # Show extraction log if enabled
        if st.session_state.show_extraction_log and st.session_state.processing_log:
            with st.expander("🔍 Extraction Log", expanded=True):
                for log_entry in st.session_state.processing_log:
                    st.text(log_entry)
        
        # Display extracted fields by structure
        if st.session_state.pdf_structure:
            st.subheader("📋 Extracted Fields by Form Structure")
            
            for part_name, part_fields in st.session_state.pdf_structure.items():
                if not part_fields:
                    continue
                
                # Calculate part statistics
                part_mapped = sum(1 for f in part_fields if f['name'] in st.session_state.mapped_fields)
                part_quest = sum(1 for f in part_fields if f['name'] in st.session_state.questionnaire_fields)
                part_unmapped = len(part_fields) - part_mapped - part_quest
                
                # Part header with statistics
                header_text = f"{part_name} ({len(part_fields)} fields: "
                header_text += f"✅ {part_mapped} mapped, 📋 {part_quest} questionnaire, ❓ {part_unmapped} unmapped)"
                
                with st.expander(header_text, expanded=(part_unmapped > 0)):
                    # Action buttons for the part
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button(f"Map All in {part_name}", key=f"map_all_{part_name}"):
                            # Map all unmapped fields in this part
                            pass
                    with col2:
                        if st.button(f"Move All to Questionnaire", key=f"quest_all_{part_name}"):
                            # Move all unmapped fields to questionnaire
                            pass
                    with col3:
                        if st.button(f"Remove All", key=f"remove_all_{part_name}"):
                            # Remove all fields in this part
                            pass
                    
                    # Display fields
                    for i, field in enumerate(part_fields):
                        render_field_card(field, i)
                        
                        # Quick actions
                        col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                        
                        with col1:
                            if field['name'] not in st.session_state.mapped_fields:
                                # Show mapping suggestions if available
                                if field['name'] in st.session_state.mapping_suggestions:
                                    suggestion = st.session_state.mapping_suggestions[field['name']]
                                    st.info(f"💡 Suggested: {suggestion['mapping']} (Score: {suggestion['score']:.2f})")
                        
                        with col2:
                            if st.button("📍 Map", key=f"map_{field['name']}", use_container_width=True):
                                # Open mapping dialog
                                pass
                        
                        with col3:
                            if st.button("❓", key=f"quest_{field['name']}", use_container_width=True):
                                # Move to questionnaire
                                st.session_state.questionnaire_fields[field['name']] = {
                                    'type': 'checkbox' if field['type'] == 'CheckBox' else 'text',
                                    'required': field.get('required', False),
                                    'label': beautify_field_name(field['name']),
                                    'style': {"col": "12"}
                                }
                                st.rerun()
                        
                        with col4:
                            if st.button("🗑️", key=f"del_{field['name']}", use_container_width=True):
                                st.session_state.removed_fields.append(field['name'])
                                st.rerun()
                        
                        st.markdown("---")
    
    # Tab 2: Field Mapping
    with tab2:
        st.header("Step 2: Map Fields to Database")
        
        if not st.session_state.pdf_fields:
            st.warning("⚠️ Please upload and extract fields first!")
        else:
            # Mapping interface with suggestions
            st.subheader("🎯 Field Mapping Interface")
            
            # Filter options
            col1, col2, col3 = st.columns(3)
            with col1:
                show_mapped = st.checkbox("Show Mapped", value=True)
            with col2:
                show_unmapped = st.checkbox("Show Unmapped", value=True)
            with col3:
                show_suggestions = st.checkbox("Show Suggestions", value=True)
            
            # Display fields for mapping
            for field in st.session_state.pdf_fields:
                field_name = field['name']
                
                # Filter logic
                is_mapped = field_name in st.session_state.mapped_fields
                if (is_mapped and not show_mapped) or (not is_mapped and not show_unmapped):
                    continue
                
                if field_name in st.session_state.questionnaire_fields or field_name in st.session_state.removed_fields:
                    continue
                
                # Field mapping interface
                with st.container():
                    col1, col2, col3 = st.columns([3, 4, 1])
                    
                    with col1:
                        st.text_input(
                            "Field",
                            value=f"{field_name} ({field['type']})",
                            disabled=True,
                            key=f"field_display_{field_name}"
                        )
                    
                    with col2:
                        current_mapping = st.session_state.mapped_fields.get(field_name, '')
                        if ':' in current_mapping:
                            current_mapping = current_mapping.split(':')[0]
                        
                        # Show suggestion if available
                        suggestion = ""
                        if show_suggestions and field_name in st.session_state.mapping_suggestions:
                            suggestion = st.session_state.mapping_suggestions[field_name]['mapping']
                        
                        new_mapping = st.text_input(
                            "Mapping Path",
                            value=current_mapping,
                            placeholder=suggestion or "e.g., customer.customer_name",
                            key=f"mapping_input_{field_name}"
                        )
                        
                        if new_mapping and new_mapping != current_mapping:
                            st.session_state.mapped_fields[field_name] = f"{new_mapping}:{field['type']}"
                    
                    with col3:
                        if st.button("❌", key=f"clear_mapping_{field_name}"):
                            if field_name in st.session_state.mapped_fields:
                                del st.session_state.mapped_fields[field_name]
                                st.rerun()
    
    # Tab 3: Questionnaire Configuration
    with tab3:
        st.header("Step 3: Configure Questionnaire Fields")
        
        # Add new field interface
        with st.expander("➕ Add New Questionnaire Field", expanded=False):
            col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
            
            with col1:
                new_field_label = st.text_input("Field Label", placeholder="e.g., Have you ever been arrested?")
            
            with col2:
                new_field_type = st.selectbox(
                    "Field Type",
                    ["text", "textarea", "checkbox", "radio", "select", "date", "number", "email", "phone"]
                )
            
            with col3:
                new_field_required = st.checkbox("Required", value=False)
            
            with col4:
                if st.button("Add Field", type="primary", use_container_width=True):
                    if new_field_label:
                        field_key = re.sub(r'[^\w]', '_', new_field_label)
                        st.session_state.questionnaire_fields[field_key] = {
                            'type': new_field_type,
                            'required': new_field_required,
                            'label': new_field_label,
                            'options': '',
                            'validation': '',
                            'style': {"col": "12"}
                        }
                        st.success(f"✅ Added: {new_field_label}")
                        st.rerun()
        
        # Display and edit questionnaire fields
        if st.session_state.questionnaire_fields:
            st.subheader(f"📋 Questionnaire Fields ({len(st.session_state.questionnaire_fields)})")
            
            for field_key, field_config in list(st.session_state.questionnaire_fields.items()):
                with st.expander(f"{field_config['label']} ({field_config['type']})", expanded=False):
                    col1, col2 = st.columns([4, 1])
                    
                    with col1:
                        # Field configuration
                        field_config['label'] = st.text_input(
                            "Label",
                            value=field_config.get('label', field_key),
                            key=f"q_label_{field_key}"
                        )
                        
                        field_config['type'] = st.selectbox(
                            "Type",
                            ["text", "textarea", "checkbox", "radio", "select", "date", "number", "email", "phone"],
                            index=["text", "textarea", "checkbox", "radio", "select", "date", "number", "email", "phone"].index(field_config['type']),
                            key=f"q_type_{field_key}"
                        )
                        
                        field_config['required'] = st.checkbox(
                            "Required",
                            value=field_config.get('required', False),
                            key=f"q_required_{field_key}"
                        )
                        
                        # Options for select/radio
                        if field_config['type'] in ['radio', 'select']:
                            field_config['options'] = st.text_area(
                                "Options (one per line)",
                                value=field_config.get('options', ''),
                                height=100,
                                key=f"q_options_{field_key}"
                            )
                        
                        # Validation pattern
                        field_config['validation'] = st.text_input(
                            "Validation Pattern (regex)",
                            value=field_config.get('validation', ''),
                            placeholder="e.g., ^[0-9]{3}-[0-9]{2}-[0-9]{4}$ for SSN",
                            key=f"q_validation_{field_key}"
                        )
                        
                        # Layout configuration
                        col_size = st.slider(
                            "Column Size (1-12)",
                            min_value=1,
                            max_value=12,
                            value=int(field_config.get('style', {}).get('col', 12)),
                            key=f"q_col_{field_key}"
                        )
                        field_config['style']['col'] = str(col_size)
                    
                    with col2:
                        st.write("")  # Spacer
                        if st.button("🗑️ Remove", key=f"q_remove_{field_key}", use_container_width=True):
                            del st.session_state.questionnaire_fields[field_key]
                            st.rerun()
                        
                        if st.button("➡️ To Mapping", key=f"q_to_map_{field_key}", use_container_width=True):
                            # Move back to unmapped fields
                            del st.session_state.questionnaire_fields[field_key]
                            st.rerun()
        else:
            st.info("No questionnaire fields configured yet. Add fields from unmapped fields or create new ones.")
    
    # Tab 4: Advanced Settings
    with tab4:
        st.header("Step 4: Advanced Configuration")
        
        # Conditional Fields
        st.subheader("⚡ Conditional Fields")
        
        with st.expander("➕ Add Conditional Field", expanded=False):
            col1, col2 = st.columns(2)
            
            with col1:
                cond_name = st.text_input("Condition Name", placeholder="e.g., showAddressFields")
                cond_condition = st.text_input("Condition Expression", placeholder="e.g., mailingAddressDifferent==true")
            
            with col2:
                cond_true = st.text_input("Value if True", placeholder="Show fields or value")
                cond_false = st.text_input("Value if False", placeholder="Hide fields or value")
            
            cond_type = st.selectbox("Result Type", ["Visibility", "Value", "Required", "Calculation"])
            
            if st.button("Add Conditional", type="primary"):
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
                with st.container():
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.markdown(f"""
                        **{cond_name}**  
                        Condition: `{cond_info['condition']}`  
                        True: {cond_info['conditionTrue']} | False: {cond_info['conditionFalse']}  
                        Type: {cond_info['conditionType']}
                        """)
                    with col2:
                        if st.button("🗑️", key=f"del_cond_{cond_name}"):
                            del st.session_state.conditional_fields[cond_name]
                            st.rerun()
        
        st.markdown("---")
        
        # Default Values
        st.subheader("📝 Default Values")
        
        col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
        with col1:
            default_field = st.text_input("Field Name", placeholder="e.g., country")
        with col2:
            default_value = st.text_input("Default Value", placeholder="e.g., United States")
        with col3:
            default_type = st.selectbox("Type", ["TextBox", "CheckBox", "Date", "Number"])
        with col4:
            if st.button("Add Default", use_container_width=True):
                if default_field and default_value:
                    st.session_state.default_fields[default_field] = f"{default_value}:{default_type}"
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
    
    # Tab 5: Generate & Export
    with tab5:
        st.header("Step 5: Generate Configuration and Export")
        
        if not st.session_state.pdf_fields:
            st.warning("⚠️ Please upload and process a PDF first!")
        else:
            # Summary with visual representation
            st.subheader("📊 Configuration Summary")
            
            # Create visual summary
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Fields", len(st.session_state.pdf_fields), delta=None)
            with col2:
                mapped_count = len(st.session_state.mapped_fields)
                st.metric("Mapped", mapped_count, delta=f"{(mapped_count/len(st.session_state.pdf_fields)*100):.1f}%")
            with col3:
                st.metric("Questionnaire", len(st.session_state.questionnaire_fields))
            with col4:
                st.metric("Removed", len(st.session_state.removed_fields))
            
            st.markdown("---")
            
            # Export options
            st.subheader("📥 Export Options")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 📄 TypeScript Configuration")
                
                ts_options = st.multiselect(
                    "Include in TypeScript export:",
                    ["Mapped Fields", "Questionnaire Fields", "Conditional Logic", "Default Values", "Metadata"],
                    default=["Mapped Fields", "Questionnaire Fields", "Conditional Logic", "Default Values", "Metadata"]
                )
                
                if st.button("Generate TypeScript", type="primary", use_container_width=True):
                    ts_content = generate_typescript_enhanced(ts_options)
                    
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
                st.markdown("### 📋 Questionnaire JSON")
                
                json_format = st.radio(
                    "JSON Format:",
                    ["Controls Array", "Nested Object", "Form Schema"],
                    horizontal=True
                )
                
                if st.button("Generate JSON", type="primary", use_container_width=True):
                    json_content = generate_questionnaire_json_enhanced(json_format)
                    
                    st.download_button(
                        label="📥 Download JSON File",
                        data=json_content,
                        file_name=f"{st.session_state.form_name}_questionnaire.json",
                        mime="application/json",
                        use_container_width=True
                    )
                    
                    with st.expander("Preview JSON", expanded=False):
                        st.code(json_content, language="json")
            
            st.markdown("---")
            
            # Complete export
            st.subheader("💾 Complete Configuration Export")
            
            export_format = st.radio(
                "Export Format:",
                ["JSON", "YAML", "Python Dict"],
                horizontal=True
            )
            
            if st.button("📦 Export Complete Configuration", type="primary", use_container_width=True):
                config_content = export_complete_configuration(export_format)
                
                file_ext = export_format.lower() if export_format != "Python Dict" else "py"
                mime_type = {
                    "JSON": "application/json",
                    "YAML": "text/yaml",
                    "Python Dict": "text/plain"
                }[export_format]
                
                st.download_button(
                    label=f"📥 Download Complete Configuration ({export_format})",
                    data=config_content,
                    file_name=f"{st.session_state.form_name}_complete.{file_ext}",
                    mime=mime_type,
                    use_container_width=True
                )

def generate_typescript_enhanced(options: List[str]) -> str:
    """Generate enhanced TypeScript configuration"""
    form_name = st.session_state.get('form_name', 'UnknownForm')
    form_name_clean = re.sub(r'[^\w]', '', form_name)
    
    # Build configuration object
    config = {
        'formname': form_name_clean,
        'formType': st.session_state.form_type,
        'extractionMethod': st.session_state.extraction_method,
        'generatedAt': datetime.now().isoformat()
    }
    
    # Organize mapped fields by category
    if "Mapped Fields" in options:
        categories = defaultdict(dict)
        for field_name, mapping in st.session_state.mapped_fields.items():
            if ':' in mapping:
                mapping_path, field_type = mapping.split(':', 1)
            else:
                mapping_path = mapping
                field_type = 'TextBox'
            
            # Determine category from mapping path
            category = mapping_path.split('.')[0] + 'Data'
            categories[category][field_name] = f"{mapping_path}:{field_type}"
        
        config.update(dict(categories))
    
    # Add questionnaire data
    if "Questionnaire Fields" in options:
        questionnaire_data = {}
        for field_name, field_info in st.session_state.questionnaire_fields.items():
            field_key = re.sub(r'[^\w]', '_', field_name)
            questionnaire_data[field_key] = {
                'type': field_info['type'],
                'label': field_info['label'],
                'required': field_info.get('required', False),
                'validation': field_info.get('validation', ''),
                'options': field_info.get('options', '').split('\n') if field_info.get('options') else []
            }
        config['questionnaireData'] = questionnaire_data
    
    # Add conditional logic
    if "Conditional Logic" in options and st.session_state.conditional_fields:
        config['conditionalData'] = st.session_state.conditional_fields
    
    # Add default values
    if "Default Values" in options and st.session_state.default_fields:
        config['defaultData'] = st.session_state.default_fields
    
    # Add metadata
    if "Metadata" in options:
        config['metadata'] = {
            'totalFields': len(st.session_state.pdf_fields),
            'mappedFields': len(st.session_state.mapped_fields),
            'questionnaireFields': len(st.session_state.questionnaire_fields),
            'conditionalFields': len(st.session_state.conditional_fields),
            'defaultFields': len(st.session_state.default_fields),
            'removedFields': len(st.session_state.removed_fields),
            'fieldTypes': dict(st.session_state.field_statistics)
        }
    
    # Generate TypeScript
    ts_content = f"""// Auto-generated form configuration for {form_name}
// Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
// Form Type: {st.session_state.form_type or 'Unknown'}

import {{ FormConfiguration }} from './types';

export const {form_name_clean}: FormConfiguration = {json.dumps(config, indent=2)};

export default {form_name_clean};"""
    
    return ts_content

def generate_questionnaire_json_enhanced(format_type: str) -> str:
    """Generate questionnaire JSON in various formats"""
    if format_type == "Controls Array":
        controls = []
        for field_name, field_info in st.session_state.questionnaire_fields.items():
            control = {
                "name": re.sub(r'[^\w]', '_', field_name),
                "label": field_info.get('label', field_name),
                "type": field_info.get('type', 'text'),
                "required": field_info.get('required', False),
                "style": field_info.get('style', {"col": "12"})
            }
            
            if field_info.get('validation'):
                control['validators'] = {"pattern": field_info['validation']}
            
            if field_info.get('options'):
                control['options'] = field_info['options'].split('\n')
            
            controls.append(control)
        
        return json.dumps({"controls": controls}, indent=2)
    
    elif format_type == "Nested Object":
        nested = {}
        for field_name, field_info in st.session_state.questionnaire_fields.items():
            field_key = re.sub(r'[^\w]', '_', field_name)
            nested[field_key] = field_info
        
        return json.dumps(nested, indent=2)
    
    else:  # Form Schema
        schema = {
            "title": st.session_state.form_name,
            "type": "object",
            "properties": {},
            "required": []
        }
        
        for field_name, field_info in st.session_state.questionnaire_fields.items():
            field_key = re.sub(r'[^\w]', '_', field_name)
            
            prop = {
                "title": field_info.get('label', field_name),
                "type": "string" if field_info['type'] != 'number' else 'number'
            }
            
            if field_info.get('options'):
                prop['enum'] = field_info['options'].split('\n')
            
            if field_info.get('validation'):
                prop['pattern'] = field_info['validation']
            
            schema['properties'][field_key] = prop
            
            if field_info.get('required', False):
                schema['required'].append(field_key)
        
        return json.dumps(schema, indent=2)

def export_complete_configuration(format_type: str) -> str:
    """Export complete configuration in various formats"""
    config = {
        "formName": st.session_state.form_name,
        "formType": st.session_state.form_type,
        "timestamp": datetime.now().isoformat(),
        "pdfFields": st.session_state.pdf_fields,
        "mappedFields": st.session_state.mapped_fields,
        "questionnaireFields": st.session_state.questionnaire_fields,
        "conditionalFields": st.session_state.conditional_fields,
        "defaultFields": st.session_state.default_fields,
        "removedFields": st.session_state.removed_fields,
        "fieldStructure": st.session_state.pdf_structure,
        "mappingSuggestions": st.session_state.mapping_suggestions,
        "metadata": {
            "totalFields": len(st.session_state.pdf_fields),
            "mappedFields": len(st.session_state.mapped_fields),
            "questionnaireFields": len(st.session_state.questionnaire_fields),
            "conditionalFields": len(st.session_state.conditional_fields),
            "defaultFields": len(st.session_state.default_fields),
            "removedFields": len(st.session_state.removed_fields),
            "extractionMethod": st.session_state.extraction_method,
            "fieldTypes": dict(st.session_state.field_statistics)
        }
    }
    
    if format_type == "JSON":
        return json.dumps(config, indent=2)
    
    elif format_type == "YAML":
        try:
            import yaml
            return yaml.dump(config, default_flow_style=False)
        except ImportError:
            st.error("YAML export requires PyYAML. Install with: pip install pyyaml")
            return json.dumps(config, indent=2)
    
    else:  # Python Dict
        return f"# Auto-generated configuration\n# {datetime.now()}\n\nconfig = {repr(config)}"

# Footer
def render_footer():
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: var(--text-secondary); padding: 20px;'>
        <p>📄 Enhanced PDF Form Automation System v2.0</p>
        <p>Built with Streamlit • Powered by AI-assisted mapping</p>
    </div>
    """, unsafe_allow_html=True)

# Run the application
if __name__ == "__main__":
    main()
    render_footer()
