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
    page_title="Enhanced PDF Form Automation System",
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
</style>
""", unsafe_allow_html=True)

# Check if PDF library is available
if not PDF_AVAILABLE:
    st.error("PDF processing library not found. Please install PyPDF2 or pypdf:")
    st.code("pip install PyPDF2")
    st.stop()

# Enhanced session state initialization
@dataclass
class FormField:
    name: str
    type: str
    value: str = ""
    required: bool = False
    page: int = 0
    options: List[str] = None
    validation: str = ""
    description: str = ""
    coordinates: Dict[str, float] = None

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
        'mapping_history': [],
        'auto_save': True,
        'mapping_templates': {},
        'extracted_text': "",
        'pdf_preview': None
    }
    
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

init_session_state()

# Enhanced mapping patterns with more comprehensive rules
MAPPING_PATTERNS = {
    'customer': {
        'patterns': [
            r'customer[_\s]?name', r'company[_\s]?name', r'employer[_\s]?name',
            r'petitioner[_\s]?name', r'organization[_\s]?name', r'business[_\s]?name',
            r'firm[_\s]?name', r'entity[_\s]?name'
        ],
        'mapping': 'customer.customer_name',
        'type': 'TextBox'
    },
    'customer_tax_id': {
        'patterns': [
            r'ein', r'fein', r'tax[_\s]?id', r'employer[_\s]?id',
            r'federal[_\s]?tax[_\s]?id', r'irs[_\s]?number'
        ],
        'mapping': 'customer.customer_tax_id',
        'type': 'TextBox',
        'validation': r'^\d{2}-\d{7}$'
    },
    'customer_address': {
        'patterns': [
            r'company[_\s]?address', r'employer[_\s]?address', r'business[_\s]?address',
            r'petitioner[_\s]?address'
        ],
        'mapping': 'customer.address',
        'type': 'TextBox'
    },
    'customer_signatory_first': {
        'patterns': [
            r'signatory[_\s]?first[_\s]?name', r'authorized[_\s]?official[_\s]?first',
            r'representative[_\s]?first[_\s]?name'
        ],
        'mapping': 'customer.signatory_first_name',
        'type': 'TextBox'
    },
    'customer_signatory_last': {
        'patterns': [
            r'signatory[_\s]?last[_\s]?name', r'authorized[_\s]?official[_\s]?last',
            r'representative[_\s]?last[_\s]?name'
        ],
        'mapping': 'customer.signatory_last_name',
        'type': 'TextBox'
    },
    'beneficiary_first_name': {
        'patterns': [
            r'beneficiary[_\s]?first[_\s]?name', r'given[_\s]?name',
            r'ben[_\s]?firstname', r'ben[_\s]?givenname', r'employee[_\s]?first[_\s]?name',
            r'worker[_\s]?first[_\s]?name', r'P5_[0-9]+b.*first.*name'
        ],
        'mapping': 'beneficiary.Beneficiary.beneficiaryFirstName',
        'type': 'TextBox'
    },
    'beneficiary_last_name': {
        'patterns': [
            r'beneficiary[_\s]?last[_\s]?name', r'family[_\s]?name',
            r'ben[_\s]?lastname', r'ben[_\s]?familyname', r'employee[_\s]?last[_\s]?name',
            r'worker[_\s]?last[_\s]?name', r'surname', r'P5_[0-9]+a.*family.*name'
        ],
        'mapping': 'beneficiary.Beneficiary.beneficiaryLastName',
        'type': 'TextBox'
    },
    'beneficiary_middle_name': {
        'patterns': [
            r'beneficiary[_\s]?middle[_\s]?name', r'ben[_\s]?middlename',
            r'employee[_\s]?middle[_\s]?name', r'P5_[0-9]+c.*middle.*name'
        ],
        'mapping': 'beneficiary.Beneficiary.beneficiaryMiddleName',
        'type': 'TextBox'
    },
    'attorney_last_name': {
        'patterns': [
            r'attorney[_\s]?last[_\s]?name', r'att[_\s]?lastname',
            r'lawyer[_\s]?last[_\s]?name', r'representative[_\s]?last[_\s]?name'
        ],
        'mapping': 'attorney.attorneyInfo.lastName',
        'type': 'TextBox'
    },
    'attorney_first_name': {
        'patterns': [
            r'attorney[_\s]?first[_\s]?name', r'att[_\s]?firstname',
            r'lawyer[_\s]?first[_\s]?name', r'representative[_\s]?first[_\s]?name'
        ],
        'mapping': 'attorney.attorneyInfo.firstName',
        'type': 'TextBox'
    },
    'attorney_bar_number': {
        'patterns': [
            r'bar[_\s]?number', r'bar[_\s]?no', r'attorney[_\s]?bar[_\s]?number',
            r'license[_\s]?number'
        ],
        'mapping': 'attorney.attorneyInfo.barNumber',
        'type': 'TextBox'
    },
    'address_street': {
        'patterns': [
            r'street[_\s]?number[_\s]?and[_\s]?name', r'address[_\s]?street', 
            r'street[_\s]?address', r'mailing[_\s]?address', r'P5_[0-9]+_strtnumname'
        ],
        'mapping': 'address.addressStreet',
        'type': 'TextBox'
    },
    'address_city': {
        'patterns': [
            r'city', r'address[_\s]?city', r'city[_\s]?or[_\s]?town',
            r'municipality', r'P5_[0-9]+_city'
        ],
        'mapping': 'address.addressCity',
        'type': 'TextBox'
    },
    'address_state': {
        'patterns': [
            r'state', r'address[_\s]?state', r'province', r'P5_[0-9]+_state'
        ],
        'mapping': 'address.addressState',
        'type': 'TextBox'
    },
    'address_zip': {
        'patterns': [
            r'zip[_\s]?code', r'postal[_\s]?code', r'address[_\s]?zip',
            r'zip', r'P5_[0-9]+_zipcode'
        ],
        'mapping': 'address.addressZip',
        'type': 'TextBox',
        'validation': r'^\d{5}(-\d{4})?$'
    },
    'ssn': {
        'patterns': [
            r'social[_\s]?security[_\s]?number', r'ssn', r'ussocialssn',
            r'social[_\s]?security', r'ss[_\s]?no'
        ],
        'mapping': 'beneficiary.Beneficiary.beneficiarySsn',
        'type': 'TextBox',
        'validation': r'^\d{3}-\d{2}-\d{4}$'
    },
    'alien_number': {
        'patterns': [
            r'alien[_\s]?number', r'a[\-\s]?number', r'dbalien',
            r'alien[_\s]?registration[_\s]?number', r'uscis[_\s]?number'
        ],
        'mapping': 'beneficiary.Beneficiary.alienNumber',
        'type': 'TextBox',
        'validation': r'^A\d{8,9}$'
    },
    'date_of_birth': {
        'patterns': [
            r'date[_\s]?of[_\s]?birth', r'dob', r'birth[_\s]?date',
            r'birthdate', r'born[_\s]?on'
        ],
        'mapping': 'beneficiary.Beneficiary.beneficiaryDateOfBirth',
        'type': 'Date'
    },
    'i94_number': {
        'patterns': [
            r'i[\-\s]?94[_\s]?number', r'arrival[_\s]?number',
            r'admission[_\s]?number', r'i94[\-\s]?no'
        ],
        'mapping': 'beneficiary.I94Details.I94.i94Number',
        'type': 'TextBox'
    },
    'passport_number': {
        'patterns': [
            r'passport[_\s]?number', r'travel[_\s]?document',
            r'passport[_\s]?no', r'travel[_\s]?doc[_\s]?number'
        ],
        'mapping': 'beneficiary.PassportDetails.Passport.passportNumber',
        'type': 'TextBox'
    },
    'case_type': {
        'patterns': [
            r'case[_\s]?type', r'petition[_\s]?type', r'classification',
            r'visa[_\s]?type', r'category'
        ],
        'mapping': 'case.caseType',
        'type': 'DropDown'
    },
    'job_title': {
        'patterns': [
            r'job[_\s]?title', r'position[_\s]?title', r'occupation',
            r'employment[_\s]?title', r'P5_1'
        ],
        'mapping': 'case.jobTitle',
        'type': 'TextBox'
    },
    'wages': {
        'patterns': [
            r'wage', r'salary', r'compensation', r'pay[_\s]?rate',
            r'annual[_\s]?salary', r'P5_9_cur'
        ],
        'mapping': 'case.wages',
        'type': 'Currency'
    },
    'email': {
        'patterns': [
            r'email[_\s]?address', r'e[\-\s]?mail', r'electronic[_\s]?mail',
            r'contact[_\s]?email'
        ],
        'mapping': 'contact.email',
        'type': 'TextBox',
        'validation': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    },
    'phone': {
        'patterns': [
            r'phone[_\s]?number', r'telephone', r'contact[_\s]?number',
            r'phone', r'tel', r'daytime[_\s]?phone'
        ],
        'mapping': 'contact.phone',
        'type': 'TextBox',
        'validation': r'^[\d\s\-\(\)\+]+$'
    }
}

# Enhanced field types with more granular detection
FIELD_TYPES = {
    'TextBox': {
        'keywords': ['text', 'name', 'address', 'title', 'number', 'description'],
        'patterns': [r'_{3,}', r'\[[\s]*\]', r'\.{3,}']
    },
    'CheckBox': {
        'keywords': ['checkbox', 'check', 'yes/no', 'option', 'select', 'mark'],
        'patterns': [r'\[\s*\]', r'\(\s*\)', r'☐', r'□']
    },
    'Date': {
        'keywords': ['date', 'dob', 'birth', 'expiry', 'issue', 'mm/dd/yyyy', 'from', 'to'],
        'patterns': [r'\d{1,2}/\d{1,2}/\d{2,4}', r'mm/dd/yyyy', r'__/__/____']
    },
    'RadioButton': {
        'keywords': ['radio', 'select one', 'choice', 'option'],
        'patterns': [r'\(\s*\)', r'○', r'◯']
    },
    'DropDown': {
        'keywords': ['dropdown', 'select', 'list', 'choose from', 'per'],
        'patterns': [r'▼', r'⌄', r'\[Select\]']
    },
    'Signature': {
        'keywords': ['signature', 'sign', 'signed by', 'authorized'],
        'patterns': [r'signature[:\s]*_{3,}', r'sign[:\s]*_{3,}']
    },
    'Currency': {
        'keywords': ['wage', 'salary', 'amount', 'fee', 'cost', 'price', '$'],
        'patterns': [r'\$[\d,]+', r'USD', r'dollars']
    },
    'MultipleBox': {
        'keywords': ['multiple', 'list', 'array', 'add more'],
        'patterns': [r'add\s*another', r'additional']
    },
    'TextArea': {
        'keywords': ['explain', 'describe', 'details', 'notes', 'comments'],
        'patterns': [r'provide\s*details', r'explanation']
    }
}

# Validation patterns
VALIDATION_PATTERNS = {
    'ssn': r'^\d{3}-\d{2}-\d{4}$',
    'ein': r'^\d{2}-\d{7}$',
    'email': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
    'phone': r'^[\d\s\-\(\)\+]+$',
    'zip': r'^\d{5}(-\d{4})?$',
    'alien_number': r'^A\d{8,9}$',
    'date': r'^\d{1,2}/\d{1,2}/\d{4}$'
}

def extract_pdf_fields_enhanced(pdf_file) -> List[Dict[str, Any]]:
    """Enhanced PDF field extraction with multiple methods"""
    fields = []
    extracted_text = ""
    
    try:
        # Method 1: Try PyPDF2 form fields
        pdf_reader = PdfReader(pdf_file)
        
        # Extract text for context
        for page in pdf_reader.pages:
            extracted_text += page.extract_text() + "\n"
        
        st.session_state.extracted_text = extracted_text
        
        # Try to get form fields
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
                        'method': 'form_fields'
                    })
        
        # Try to get fields from annotations
        if hasattr(pdf_reader, 'get_fields'):
            pdf_fields = pdf_reader.get_fields()
            if pdf_fields:
                for field_name, field_obj in pdf_fields.items():
                    field_type = 'TextBox'
                    if isinstance(field_obj, dict):
                        if field_obj.get('/FT') == '/Btn':
                            if field_obj.get('/Ff', 0) & 65536:  # Radio button
                                field_type = 'RadioButton'
                            else:
                                field_type = 'CheckBox'
                        elif field_obj.get('/FT') == '/Ch':
                            field_type = 'DropDown'
                        elif field_obj.get('/FT') == '/Tx':
                            field_type = 'TextBox'
                    
                    if not any(f['name'] == field_name for f in fields):
                        fields.append({
                            'name': field_name,
                            'type': field_type,
                            'value': '',
                            'required': is_field_required(field_name, extracted_text),
                            'page': 0,
                            'method': 'annotations'
                        })
        
        # Method 2: Try pdfplumber if available
        if PDFPLUMBER_AVAILABLE and not fields:
            pdf_file.seek(0)  # Reset file pointer
            import pdfplumber
            with pdfplumber.open(pdf_file) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    # Extract form elements
                    if hasattr(page, 'extract_form_fields'):
                        page_fields = page.extract_form_fields()
                        if page_fields:
                            for field in page_fields:
                                fields.append({
                                    'name': field.get('name', f'field_{len(fields)}'),
                                    'type': field.get('type', 'TextBox'),
                                    'value': field.get('value', ''),
                                    'required': False,
                                    'page': page_num,
                                    'method': 'pdfplumber'
                                })
        
        # Method 3: Extract from text patterns
        if not fields or len(fields) < 5:  # If few fields found, try text extraction
            text_fields = extract_fields_from_text(extracted_text)
            
            # Merge with existing fields
            existing_names = {f['name'].lower() for f in fields}
            for text_field in text_fields:
                if text_field['name'].lower() not in existing_names:
                    fields.append(text_field)
        
        # Sort fields by appearance order
        fields = sorted(fields, key=lambda x: (x['page'], x.get('order', 0)))
        
    except Exception as e:
        st.error(f"Error extracting PDF fields: {str(e)}")
        st.info("You can manually add fields or try a different PDF.")
    
    return fields

def extract_fields_from_text(text: str) -> List[Dict[str, Any]]:
    """Extract potential form fields from text using advanced pattern matching"""
    fields = []
    seen_fields = set()
    
    # Clean and normalize text
    text = re.sub(r'\s+', ' ', text)
    lines = text.split('\n')
    
    # Enhanced patterns for different form structures
    patterns = [
        # USCIS form patterns (e.g., "1.a. Family Name")
        {
            'pattern': r'(\d+\.?[a-z]?\.\s+)([A-Za-z][A-Za-z\s]{2,50})(?:\s*:?\s*)(?:_{3,}|\[[\s]*\]|\([\s]*\))',
            'type': 'TextBox',
            'name_group': 2
        },
        # Label with underscores
        {
            'pattern': r'([A-Za-z][A-Za-z\s\-]{2,50})(?:\s*:?\s*)(?:_{3,})',
            'type': 'TextBox',
            'name_group': 1
        },
        # Checkbox patterns
        {
            'pattern': r'\[\s*\]\s*([A-Za-z][A-Za-z\s\-]{2,50})',
            'type': 'CheckBox',
            'name_group': 1
        },
        # Radio button patterns
        {
            'pattern': r'\(\s*\)\s*([A-Za-z][A-Za-z\s\-]{2,50})',
            'type': 'RadioButton',
            'name_group': 1
        },
        # Date patterns
        {
            'pattern': r'([A-Za-z\s]*Date[A-Za-z\s]*|DOB|Birth\s*Date)(?:\s*:?\s*)(?:_{3,}|mm/dd/yyyy)',
            'type': 'Date',
            'name_group': 1
        },
        # Signature patterns
        {
            'pattern': r'(Signature[A-Za-z\s]*)(?:\s*:?\s*)_{3,}',
            'type': 'Signature',
            'name_group': 1
        },
        # Yes/No patterns
        {
            'pattern': r'([A-Za-z][A-Za-z\s\?]{5,100})\s*(?:Yes|No)\s*\[\s*\]',
            'type': 'CheckBox',
            'name_group': 1
        }
    ]
    
    # Process each pattern
    for pattern_info in patterns:
        pattern = pattern_info['pattern']
        field_type = pattern_info['type']
        name_group = pattern_info['name_group']
        
        matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            field_name = match.group(name_group).strip()
            
            # Clean field name
            field_name = re.sub(r'\s+', ' ', field_name)
            field_name = re.sub(r'[^\w\s\-\.]', '', field_name).strip()
            
            # Skip if too short or already seen
            if len(field_name) < 3 or field_name.lower() in seen_fields:
                continue
            
            # Skip common non-field text
            skip_words = ['page', 'form', 'instructions', 'section', 'part', 'continues']
            if any(skip in field_name.lower() for skip in skip_words):
                continue
            
            seen_fields.add(field_name.lower())
            
            # Determine if field is required
            required = is_field_required(field_name, text)
            
            fields.append({
                'name': field_name,
                'type': determine_field_type(field_name, text, field_type),
                'value': '',
                'required': required,
                'page': 0,
                'method': 'text_extraction',
                'confidence': calculate_field_confidence(field_name, text)
            })
    
    return fields

def determine_field_type(field_name: str, context: str = "", default_type: str = 'TextBox') -> str:
    """Enhanced field type determination using context and patterns"""
    field_lower = field_name.lower()
    
    # Check for explicit type indicators in context
    if context:
        context_lower = context.lower()
        field_context = ""
        
        # Find context around field name
        try:
            index = context_lower.find(field_lower)
            if index != -1:
                start = max(0, index - 100)
                end = min(len(context), index + len(field_lower) + 100)
                field_context = context_lower[start:end]
        except:
            field_context = ""
        
        # Check for type indicators in context
        if any(indicator in field_context for indicator in ['check one', 'select one', 'choose one']):
            if '()' in field_context:
                return 'RadioButton'
            elif '[]' in field_context:
                return 'CheckBox'
        
        if any(indicator in field_context for indicator in ['select from', 'choose from', 'dropdown']):
            return 'DropDown'
        
        if any(indicator in field_context for indicator in ['explain', 'describe', 'provide details']):
            return 'TextArea'
    
    # Check field name patterns
    for field_type, type_info in FIELD_TYPES.items():
        for keyword in type_info['keywords']:
            if keyword in field_lower:
                return field_type
    
    # Special cases
    if re.search(r'\b(ssn|social\s*security)\b', field_lower):
        return 'TextBox'
    elif re.search(r'\b(ein|tax\s*id)\b', field_lower):
        return 'TextBox'
    elif re.search(r'\$|wage|salary|amount|fee', field_lower):
        return 'Currency'
    elif re.search(r'email|e-mail', field_lower):
        return 'TextBox'
    elif re.search(r'phone|tel|fax', field_lower):
        return 'TextBox'
    elif re.search(r'date|dob|birth', field_lower):
        return 'Date'
    elif re.search(r'signature|sign', field_lower):
        return 'Signature'
    
    return default_type

def is_field_required(field_name: str, context: str) -> bool:
    """Determine if a field is required based on context"""
    field_lower = field_name.lower()
    
    # Look for required indicators
    required_indicators = [
        'required', 'mandatory', 'must complete', 'must provide',
        '*', '(required)', '[required]'
    ]
    
    # Check if field name contains required indicators
    for indicator in required_indicators:
        if indicator in field_lower:
            return True
    
    # Check context around field
    if context:
        try:
            index = context.lower().find(field_lower)
            if index != -1:
                start = max(0, index - 50)
                end = min(len(context), index + len(field_lower) + 50)
                field_context = context[start:end].lower()
                
                for indicator in required_indicators:
                    if indicator in field_context:
                        return True
        except:
            pass
    
    # Common required fields
    required_field_patterns = [
        'name', 'date', 'signature', 'ssn', 'ein', 'address',
        'email', 'phone', 'alien number', 'case type'
    ]
    
    for pattern in required_field_patterns:
        if pattern in field_lower:
            return True
    
    return False

def calculate_field_confidence(field_name: str, context: str) -> float:
    """Calculate confidence score for extracted field"""
    score = 0.5  # Base score
    
    # Check if field name is well-formed
    if re.match(r'^[A-Z][a-zA-Z\s]+$', field_name):
        score += 0.1
    
    # Check if field appears multiple times (likely a real field)
    occurrences = len(re.findall(re.escape(field_name), context, re.IGNORECASE))
    if occurrences > 1:
        score += 0.1
    
    # Check if field matches known patterns
    for category, info in MAPPING_PATTERNS.items():
        for pattern in info['patterns']:
            if re.search(pattern, field_name.lower()):
                score += 0.2
                break
    
    # Check field length (too short or too long likely not a field)
    if 5 <= len(field_name) <= 50:
        score += 0.1
    
    return min(score, 1.0)

def auto_map_field_enhanced(field_name: str, context: str = "") -> Tuple[Optional[str], float]:
    """Enhanced auto-mapping with confidence scoring"""
    field_lower = field_name.lower()
    field_lower = re.sub(r'[^\w\s]', ' ', field_lower)
    field_lower = re.sub(r'\s+', ' ', field_lower).strip()
    
    best_match = None
    best_score = 0
    
    for category, info in MAPPING_PATTERNS.items():
        for pattern in info['patterns']:
            # Calculate match score
            if re.search(pattern, field_lower):
                # Exact match gets higher score
                if pattern == field_lower:
                    score = 1.0
                else:
                    # Partial match
                    score = 0.8
                
                # Boost score if context contains related terms
                if context and category in context.lower():
                    score += 0.1
                
                if score > best_score:
                    best_score = score
                    best_match = info['mapping']
    
    # Return mapping only if confidence is high enough
    if best_score >= 0.8:
        return best_match, best_score
    
    return None, 0

def generate_enhanced_typescript(
    form_name: str,
    mapped_fields: Dict,
    questionnaire_fields: Dict,
    conditional_fields: Dict,
    default_fields: Dict,
    validation_rules: Dict,
    field_groups: Dict
) -> str:
    """Generate enhanced TypeScript with validation and grouping"""
    
    # Clean form name
    form_name_clean = re.sub(r'[^\w]', '', form_name)
    
    # Organize fields by category with enhanced structure
    categories = {
        'customer': {},
        'beneficiary': {},
        'attorney': {},
        'case': {},
        'address': {},
        'contact': {},
        'other': {}
    }
    
    # Process mapped fields
    for field_name, mapping in mapped_fields.items():
        field_info = {
            'mapping': mapping,
            'type': determine_field_type(field_name),
            'validation': validation_rules.get(field_name, ''),
            'required': any(f['name'] == field_name and f.get('required', False) 
                          for f in st.session_state.pdf_fields)
        }
        
        # Determine category
        category = 'other'
        for cat in categories.keys():
            if mapping.startswith(f'{cat}.'):
                category = cat
                break
        
        categories[category][field_name] = field_info
    
    # Format questionnaire data with enhanced structure
    formatted_questionnaire = {}
    for field_name, field_info in questionnaire_fields.items():
        field_key = re.sub(r'[^\w]', '_', field_name)
        formatted_questionnaire[field_key] = {
            'type': field_info.get('type', 'TextBox'),
            'required': field_info.get('required', False),
            'options': field_info.get('options', '').split('\n') if field_info.get('options') else [],
            'validation': field_info.get('validation', ''),
            'label': field_name
        }
    
    # Format conditional fields with enhanced logic
    formatted_conditionals = {}
    for cond_name, cond_info in conditional_fields.items():
        formatted_conditionals[cond_name] = {
            'condition': cond_info.get('condition', ''),
            'conditionTrue': cond_info.get('conditionTrue', ''),
            'conditionFalse': cond_info.get('conditionFalse', ''),
            'conditionType': cond_info.get('conditionType', 'TextBox'),
            'validation': cond_info.get('validation', '')
        }
    
    # Generate TypeScript content
    ts_content = f"""// Auto-generated form configuration for {form_name}
// Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

interface FormField {{
    mapping?: string;
    type: string;
    validation?: string;
    required?: boolean;
    options?: string[];
    label?: string;
}}

interface ConditionalField {{
    condition: string;
    conditionTrue: string;
    conditionFalse: string;
    conditionType: string;
    validation?: string;
}}

interface FormConfiguration {{
    formname: string;
    customerData: Record<string, FormField> | null;
    beneficiaryData: Record<string, FormField> | null;
    attorneyData: Record<string, FormField> | null;
    caseData: Record<string, FormField> | null;
    addressData: Record<string, FormField> | null;
    contactData: Record<string, FormField> | null;
    otherData: Record<string, FormField> | null;
    questionnaireData: Record<string, FormField>;
    defaultData: Record<string, string>;
    conditionalData: Record<string, ConditionalField>;
    validationRules: Record<string, string>;
    fieldGroups: Record<string, string[]>;
    pdfName: string;
    metadata: {{
        version: string;
        createdAt: string;
        totalFields: number;
        mappedFields: number;
        questionnaireFields: number;
    }};
}}

export const {form_name_clean}: FormConfiguration = {{
    formname: "{form_name_clean}",
    customerData: {json.dumps(categories['customer'] if categories['customer'] else None, indent=8)},
    beneficiaryData: {json.dumps(categories['beneficiary'] if categories['beneficiary'] else None, indent=8)},
    attorneyData: {json.dumps(categories['attorney'] if categories['attorney'] else None, indent=8)},
    caseData: {json.dumps(categories['case'] if categories['case'] else None, indent=8)},
    addressData: {json.dumps(categories['address'] if categories['address'] else None, indent=8)},
    contactData: {json.dumps(categories['contact'] if categories['contact'] else None, indent=8)},
    otherData: {json.dumps(categories['other'] if categories['other'] else None, indent=8)},
    questionnaireData: {json.dumps(formatted_questionnaire, indent=8)},
    defaultData: {json.dumps(default_fields, indent=8)},
    conditionalData: {json.dumps(formatted_conditionals, indent=8)},
    validationRules: {json.dumps(validation_rules, indent=8)},
    fieldGroups: {json.dumps(field_groups, indent=8)},
    pdfName: "{form_name.replace('_', '-')}",
    metadata: {{
        version: "1.0.0",
        createdAt: "{datetime.now().isoformat()}",
        totalFields: {len(st.session_state.pdf_fields)},
        mappedFields: {len(mapped_fields)},
        questionnaireFields: {len(questionnaire_fields)}
    }}
}};

// Helper functions for form processing
export const {form_name_clean}Helpers = {{
    validateField: (fieldName: string, value: string): boolean => {{
        const rule = {form_name_clean}.validationRules[fieldName];
        if (!rule) return true;
        const regex = new RegExp(rule);
        return regex.test(value);
    }},
    
    evaluateCondition: (conditionName: string, data: any): string => {{
        const conditional = {form_name_clean}.conditionalData[conditionName];
        if (!conditional) return '';
        
        try {{
            const condition = conditional.condition.replace(/([a-zA-Z_][a-zA-Z0-9_.]*)/g, 'data.$1');
            const result = eval(condition);
            return result ? conditional.conditionTrue : conditional.conditionFalse;
        }} catch (e) {{
            console.error('Error evaluating condition:', e);
            return conditional.conditionFalse;
        }}
    }},
    
    getRequiredFields: (): string[] => {{
        const required: string[] = [];
        const allData = {{
            ...{form_name_clean}.customerData,
            ...{form_name_clean}.beneficiaryData,
            ...{form_name_clean}.attorneyData,
            ...{form_name_clean}.caseData,
            ...{form_name_clean}.addressData,
            ...{form_name_clean}.contactData,
            ...{form_name_clean}.otherData,
            ...{form_name_clean}.questionnaireData
        }};
        
        Object.entries(allData).forEach(([fieldName, fieldInfo]) => {{
            if (fieldInfo && fieldInfo.required) {{
                required.push(fieldName);
            }}
        }});
        
        return required;
    }}
}};

export default {form_name_clean};
"""
    
    return ts_content

def export_mapping_configuration(form_name: str) -> str:
    """Export complete mapping configuration as JSON"""
    config = {
        "formName": form_name,
        "version": "1.0.0",
        "exportDate": datetime.now().isoformat(),
        "pdfFields": st.session_state.pdf_fields,
        "mappedFields": st.session_state.mapped_fields,
        "questionnaireFields": st.session_state.questionnaire_fields,
        "conditionalFields": st.session_state.conditional_fields,
        "defaultFields": st.session_state.default_fields,
        "validationRules": st.session_state.validation_rules,
        "fieldGroups": st.session_state.field_groups,
        "metadata": {
            "totalFields": len(st.session_state.pdf_fields),
            "mappedFields": len(st.session_state.mapped_fields),
            "questionnaireFields": len(st.session_state.questionnaire_fields),
            "conditionalFields": len(st.session_state.conditional_fields),
            "unmappedFields": len(st.session_state.pdf_fields) - 
                            len(st.session_state.mapped_fields) - 
                            len(st.session_state.questionnaire_fields)
        }
    }
    
    return json.dumps(config, indent=2)

def import_mapping_configuration(config_json: str):
    """Import mapping configuration from JSON"""
    try:
        config = json.loads(config_json)
        
        # Validate configuration
        required_keys = ['mappedFields', 'questionnaireFields', 'conditionalFields', 'defaultFields']
        for key in required_keys:
            if key not in config:
                raise ValueError(f"Missing required key: {key}")
        
        # Import configuration
        st.session_state.mapped_fields = config.get('mappedFields', {})
        st.session_state.questionnaire_fields = config.get('questionnaireFields', {})
        st.session_state.conditional_fields = config.get('conditionalFields', {})
        st.session_state.default_fields = config.get('defaultFields', {})
        st.session_state.validation_rules = config.get('validationRules', {})
        st.session_state.field_groups = config.get('fieldGroups', {})
        
        return True, "Configuration imported successfully!"
    
    except Exception as e:
        return False, f"Error importing configuration: {str(e)}"

def create_field_group(group_name: str, fields: List[str]):
    """Create a logical group of fields"""
    if group_name not in st.session_state.field_groups:
        st.session_state.field_groups[group_name] = []
    
    st.session_state.field_groups[group_name].extend(fields)
    st.session_state.field_groups[group_name] = list(set(st.session_state.field_groups[group_name]))

def suggest_validation_rule(field_name: str, field_type: str) -> str:
    """Suggest validation rule based on field name and type"""
    field_lower = field_name.lower()
    
    # Check common patterns
    for pattern_name, pattern in VALIDATION_PATTERNS.items():
        if pattern_name in field_lower:
            return pattern
    
    # Type-based suggestions
    if field_type == 'Date':
        return r'^\d{1,2}/\d{1,2}/\d{4}$'
    elif field_type == 'Currency':
        return r'^\$?[\d,]+(\.\d{2})?$'
    elif 'number' in field_lower:
        return r'^\d+$'
    
    return ''

def display_mapping_visualization():
    """Display visual representation of field mappings"""
    st.subheader("📊 Mapping Visualization")
    
    # Create summary metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Total Fields", len(st.session_state.pdf_fields))
    
    with col2:
        mapped_count = len(st.session_state.mapped_fields)
        st.metric("Mapped Fields", mapped_count,
                 f"{(mapped_count/len(st.session_state.pdf_fields)*100):.1f}%" if st.session_state.pdf_fields else "0%")
    
    with col3:
        st.metric("Questionnaire", len(st.session_state.questionnaire_fields))
    
    with col4:
        st.metric("Conditional", len(st.session_state.conditional_fields))
    
    with col5:
        unmapped = len(st.session_state.pdf_fields) - mapped_count - len(st.session_state.questionnaire_fields)
        st.metric("Unmapped", unmapped)
    
    # Field status breakdown
    if st.session_state.pdf_fields:
        st.markdown("### Field Status Breakdown")
        
        # Categorize fields
        field_categories = defaultdict(list)
        for field in st.session_state.pdf_fields:
            field_name = field['name']
            if field_name in st.session_state.mapped_fields:
                mapping = st.session_state.mapped_fields[field_name]
                category = mapping.split('.')[0]
                field_categories[category].append(field_name)
            elif field_name in st.session_state.questionnaire_fields:
                field_categories['questionnaire'].append(field_name)
            else:
                field_categories['unmapped'].append(field_name)
        
        # Display categories
        for category, fields in sorted(field_categories.items()):
            with st.expander(f"{category.title()} ({len(fields)} fields)", expanded=False):
                for field in sorted(fields):
                    if category == 'unmapped':
                        st.markdown(f'<div class="field-unmapped">❌ {field}</div>', 
                                  unsafe_allow_html=True)
                    elif category == 'questionnaire':
                        st.markdown(f'<div class="field-questionnaire">❓ {field}</div>', 
                                  unsafe_allow_html=True)
                    else:
                        mapping = st.session_state.mapped_fields.get(field, '')
                        st.markdown(f'<div class="field-mapped">✅ {field} → {mapping}</div>', 
                                  unsafe_allow_html=True)

# Main UI
st.title("📄 Enhanced PDF Form Automation System")
st.markdown("---")

# Sidebar for navigation and tools
with st.sidebar:
    st.header("🧭 Navigation")
    
    # Step selector
    step = st.selectbox(
        "Current Step:",
        ["1. Upload & Extract", "2. Field Mapping", "3. Questionnaire Setup", 
         "4. Validation & Groups", "5. Generate Output", "6. Mapping Overview"],
        key="navigation_step"
    )
    
    st.markdown("---")
    
    # Quick actions
    st.header("⚡ Quick Actions")
    
    if st.button("📥 Import Configuration", use_container_width=True):
        st.session_state.show_import = True
    
    if st.session_state.pdf_fields:
        if st.button("📤 Export Configuration", use_container_width=True):
            config_json = export_mapping_configuration(
                st.session_state.get('form_name', 'form')
            )
            st.download_button(
                label="💾 Download Configuration",
                data=config_json,
                file_name=f"{st.session_state.get('form_name', 'form')}_config.json",
                mime="application/json",
                use_container_width=True
            )
    
    # Auto-save toggle
    st.session_state.auto_save = st.checkbox(
        "🔄 Auto-save changes",
        value=st.session_state.get('auto_save', True)
    )
    
    st.markdown("---")
    
    # Statistics
    if st.session_state.pdf_fields:
        st.header("📊 Statistics")
        st.info(f"""
        **Total Fields:** {len(st.session_state.pdf_fields)}  
        **Mapped:** {len(st.session_state.mapped_fields)}  
        **Questionnaire:** {len(st.session_state.questionnaire_fields)}  
        **Conditional:** {len(st.session_state.conditional_fields)}  
        **Groups:** {len(st.session_state.field_groups)}
        """)

# Import configuration dialog
if st.session_state.get('show_import', False):
    with st.form("import_form"):
        st.subheader("📥 Import Configuration")
        config_file = st.file_uploader("Choose configuration file", type="json")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("Import", type="primary"):
                if config_file:
                    config_content = config_file.read().decode('utf-8')
                    success, message = import_mapping_configuration(config_content)
                    if success:
                        st.success(message)
                        st.session_state.show_import = False
                        st.rerun()
                    else:
                        st.error(message)
        
        with col2:
            if st.form_submit_button("Cancel"):
                st.session_state.show_import = False
                st.rerun()

# Step 1: Upload & Extract
if step == "1. Upload & Extract":
    st.header("📤 Step 1: Upload PDF & Extract Fields")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        uploaded_file = st.file_uploader(
            "Choose a PDF file",
            type="pdf",
            help="Upload a fillable PDF form to extract fields"
        )
        
        if uploaded_file is not None:
            # Form name input
            default_name = uploaded_file.name.replace('.pdf', '').replace('-', '').replace(' ', '_').upper()
            form_name = st.text_input(
                "Form Name (e.g., I129, G28, I90):",
                value=default_name,
                help="Enter a clean form name without spaces or special characters"
            )
            
            # Extract button
            if st.button("🔍 Extract Fields", type="primary", use_container_width=True):
                with st.spinner("Extracting fields from PDF..."):
                    fields = extract_pdf_fields_enhanced(uploaded_file)
                    
                    st.session_state.pdf_fields = fields
                    st.session_state.form_name = form_name
                    
                    if fields:
                        st.success(f"✅ Successfully extracted {len(fields)} fields!")
                        
                        # Auto-map fields
                        auto_mapped = 0
                        for field in fields:
                            field_name = field['name']
                            mapping, confidence = auto_map_field_enhanced(
                                field_name, 
                                st.session_state.get('extracted_text', '')
                            )
                            if mapping and confidence >= 0.8:
                                st.session_state.mapped_fields[field_name] = mapping
                                auto_mapped += 1
                        
                        if auto_mapped > 0:
                            st.info(f"🤖 Auto-mapped {auto_mapped} fields with high confidence")
                    else:
                        st.warning("No fields could be extracted automatically.")
                        st.info("You can add fields manually in the next step.")
    
    with col2:
        if uploaded_file:
            st.subheader("📋 File Information")
            st.write(f"**Filename:** {uploaded_file.name}")
            st.write(f"**Size:** {uploaded_file.size / 1024:.2f} KB")
            st.write(f"**Type:** PDF Document")
            
            # Preview option
            if st.checkbox("Show PDF Preview"):
                try:
                    base64_pdf = base64.b64encode(uploaded_file.read()).decode('utf-8')
                    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="500" type="application/pdf"></iframe>'
                    st.markdown(pdf_display, unsafe_allow_html=True)
                    uploaded_file.seek(0)  # Reset file pointer
                except:
                    st.error("Unable to display PDF preview")
    
    # Display extracted fields
    if st.session_state.pdf_fields:
        st.subheader("📝 Extracted Fields")
        
        # Filter options
        col1, col2, col3 = st.columns(3)
        with col1:
            filter_type = st.selectbox(
                "Filter by Type:",
                ["All"] + list(FIELD_TYPES.keys())
            )
        with col2:
            filter_status = st.selectbox(
                "Filter by Status:",
                ["All", "Mapped", "Questionnaire", "Unmapped"]
            )
        with col3:
            search_term = st.text_input("Search fields:", placeholder="Enter field name...")
        
        # Filter fields
        filtered_fields = []
        for field in st.session_state.pdf_fields:
            # Type filter
            if filter_type != "All" and field['type'] != filter_type:
                continue
            
            # Status filter
            field_name = field['name']
            if filter_status == "Mapped" and field_name not in st.session_state.mapped_fields:
                continue
            elif filter_status == "Questionnaire" and field_name not in st.session_state.questionnaire_fields:
                continue
            elif filter_status == "Unmapped" and (
                field_name in st.session_state.mapped_fields or 
                field_name in st.session_state.questionnaire_fields
            ):
                continue
            
            # Search filter
            if search_term and search_term.lower() not in field_name.lower():
                continue
            
            filtered_fields.append(field)
        
        # Display fields
        if filtered_fields:
            df = pd.DataFrame(filtered_fields)
            
            # Add status column
            df['status'] = df['name'].apply(lambda x: 
                'Mapped' if x in st.session_state.mapped_fields 
                else 'Questionnaire' if x in st.session_state.questionnaire_fields 
                else 'Unmapped'
            )
            
            # Style the dataframe
            def style_status(val):
                if val == 'Mapped':
                    return 'background-color: #d4edda'
                elif val == 'Questionnaire':
                    return 'background-color: #d1ecf1'
                else:
                    return 'background-color: #f8d7da'
            
            styled_df = df.style.applymap(style_status, subset=['status'])
            st.dataframe(styled_df, use_container_width=True)
        else:
            st.info("No fields match the current filters")

# Step 2: Field Mapping
elif step == "2. Field Mapping":
    st.header("🔗 Step 2: Field Mapping")
    
    if not st.session_state.pdf_fields:
        st.warning("⚠️ Please upload a PDF and extract fields first!")
        if st.button("Go to Upload Step"):
            st.session_state.navigation_step = "1. Upload & Extract"
            st.rerun()
    else:
        st.subheader(f"Mapping fields for: {st.session_state.get('form_name', 'Unknown Form')}")
        
        # Mapping tools
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button("🤖 Auto-map All", type="primary", use_container_width=True):
                auto_mapped = 0
                for field in st.session_state.pdf_fields:
                    field_name = field['name']
                    if field_name not in st.session_state.mapped_fields:
                        mapping, confidence = auto_map_field_enhanced(
                            field_name,
                            st.session_state.get('extracted_text', '')
                        )
                        if mapping and confidence >= 0.7:
                            st.session_state.mapped_fields[field_name] = mapping
                            auto_mapped += 1
                st.success(f"✅ Auto-mapped {auto_mapped} additional fields!")
        
        with col2:
            if st.button("📋 Apply Template", use_container_width=True):
                st.session_state.show_template_selector = True
        
        with col3:
            if st.button("💾 Save Template", use_container_width=True):
                st.session_state.show_save_template = True
        
        with col4:
            if st.button("🗑️ Clear All", type="secondary", use_container_width=True):
                if st.session_state.mapped_fields:
                    st.session_state.mapped_fields = {}
                    st.success("All mappings cleared!")
        
        # Template dialogs
        if st.session_state.get('show_template_selector', False):
            with st.form("template_selector"):
                st.subheader("📋 Select Mapping Template")
                template_name = st.selectbox(
                    "Choose template:",
                    ["I-129 Standard", "G-28 Standard", "I-90 Standard", "Custom..."]
                )
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("Apply", type="primary"):
                        # Apply template logic here
                        st.success(f"Applied {template_name} template!")
                        st.session_state.show_template_selector = False
                        st.rerun()
                
                with col2:
                    if st.form_submit_button("Cancel"):
                        st.session_state.show_template_selector = False
                        st.rerun()
        
        # Manual field addition
        with st.expander("➕ Add Field Manually", expanded=False):
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                new_field_name = st.text_input("Field Name", placeholder="e.g., Additional_Notes")
            with col2:
                new_field_type = st.selectbox(
                    "Field Type",
                    list(FIELD_TYPES.keys())
                )
            with col3:
                st.write("")  # Spacer
                st.write("")  # Spacer
                if st.button("Add Field", use_container_width=True):
                    if new_field_name and new_field_name not in [f['name'] for f in st.session_state.pdf_fields]:
                        st.session_state.pdf_fields.append({
                            'name': new_field_name,
                            'type': new_field_type,
                            'value': '',
                            'required': False,
                            'page': 0,
                            'method': 'manual'
                        })
                        st.success(f"Added field: {new_field_name}")
                        st.rerun()
        
        # Batch operations
        st.subheader("🔧 Batch Operations")
        
        col1, col2 = st.columns(2)
        
        with col1:
            batch_prefix = st.text_input(
                "Map all fields starting with:",
                placeholder="e.g., P5_ for Part 5 fields"
            )
        
        with col2:
            batch_mapping = st.text_input(
                "To mapping prefix:",
                placeholder="e.g., case.employment."
            )
        
        if st.button("Apply Batch Mapping", use_container_width=True):
            if batch_prefix and batch_mapping:
                batch_count = 0
                for field in st.session_state.pdf_fields:
                    if field['name'].startswith(batch_prefix):
                        field_suffix = field['name'][len(batch_prefix):].lower()
                        st.session_state.mapped_fields[field['name']] = batch_mapping + field_suffix
                        batch_count += 1
                
                if batch_count > 0:
                    st.success(f"Batch mapped {batch_count} fields!")
                else:
                    st.warning("No fields matched the prefix")
        
        # Field mapping interface
        st.subheader("📝 Individual Field Mappings")
        
        # Group unmapped fields first
        unmapped_fields = []
        mapped_fields = []
        questionnaire_fields = []
        
        for field in st.session_state.pdf_fields:
            field_name = field['name']
            if field_name in st.session_state.mapped_fields:
                mapped_fields.append(field)
            elif field_name in st.session_state.questionnaire_fields:
                questionnaire_fields.append(field)
            else:
                unmapped_fields.append(field)
        
        # Display unmapped fields first
        if unmapped_fields:
            st.markdown("#### 🔴 Unmapped Fields")
            for field in unmapped_fields:
                display_field_mapping_row(field)
        
        # Then questionnaire fields
        if questionnaire_fields:
            st.markdown("#### 🔵 Questionnaire Fields")
            for field in questionnaire_fields:
                display_field_mapping_row(field)
        
        # Finally mapped fields
        if mapped_fields:
            st.markdown("#### 🟢 Mapped Fields")
            for field in mapped_fields:
                display_field_mapping_row(field)

# Step 3: Questionnaire Setup
elif step == "3. Questionnaire Setup":
    st.header("❓ Step 3: Questionnaire Setup")
    
    # Add new questionnaire field
    with st.expander("➕ Add New Questionnaire Field", expanded=True):
        col1, col2, col3 = st.columns([3, 2, 1])
        
        with col1:
            new_q_name = st.text_input(
                "Question/Field Name",
                placeholder="e.g., Have you ever been arrested?"
            )
        
        with col2:
            new_q_type = st.selectbox(
                "Field Type",
                ["TextBox", "CheckBox", "RadioButton", "DropDown", "Date", 
                 "TextArea", "MultipleBox", "Currency"]
            )
        
        with col3:
            new_q_required = st.checkbox("Required", value=True)
            
            if st.button("Add Question", use_container_width=True):
                if new_q_name:
                    st.session_state.questionnaire_fields[new_q_name] = {
                        'type': new_q_type,
                        'required': new_q_required,
                        'options': '',
                        'validation': '',
                        'description': ''
                    }
                    st.success(f"Added question: {new_q_name}")
                    st.rerun()
    
    # Questionnaire builder
    if st.session_state.questionnaire_fields:
        st.subheader("📋 Current Questionnaire Fields")
        
        # Sort options
        sort_option = st.radio(
            "Sort by:",
            ["Order Added", "Alphabetical", "Type", "Required First"],
            horizontal=True
        )
        
        # Sort fields
        sorted_fields = list(st.session_state.questionnaire_fields.items())
        if sort_option == "Alphabetical":
            sorted_fields.sort(key=lambda x: x[0])
        elif sort_option == "Type":
            sorted_fields.sort(key=lambda x: x[1].get('type', ''))
        elif sort_option == "Required First":
            sorted_fields.sort(key=lambda x: not x[1].get('required', False))
        
        # Display fields
        for idx, (field_name, field_info) in enumerate(sorted_fields):
            with st.expander(
                f"{'🔴' if field_info.get('required') else '⚪'} {field_name} ({field_info.get('type', 'TextBox')})",
                expanded=False
            ):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    # Field properties
                    field_info['type'] = st.selectbox(
                        "Field Type",
                        ["TextBox", "CheckBox", "RadioButton", "DropDown", 
                         "Date", "TextArea", "MultipleBox", "Currency"],
                        index=["TextBox", "CheckBox", "RadioButton", "DropDown", 
                               "Date", "TextArea", "MultipleBox", "Currency"].index(
                            field_info.get('type', 'TextBox')
                        ),
                        key=f"q_type_{idx}_{field_name}"
                    )
                    
                    field_info['required'] = st.checkbox(
                        "Required Field",
                        value=field_info.get('required', False),
                        key=f"q_req_{idx}_{field_name}"
                    )
                    
                    # Type-specific options
                    if field_info['type'] in ["RadioButton", "DropDown", "CheckBox"]:
                        field_info['options'] = st.text_area(
                            "Options (one per line)",
                            value=field_info.get('options', ''),
                            height=100,
                            key=f"q_opt_{idx}_{field_name}",
                            placeholder="Yes\nNo\nNot Applicable"
                        )
                    
                    elif field_info['type'] == "MultipleBox":
                        field_info['sub_fields'] = st.text_area(
                            "Sub-fields (one per line)",
                            value=field_info.get('sub_fields', ''),
                            height=100,
                            key=f"q_sub_{idx}_{field_name}",
                            placeholder="First Name\nLast Name\nMiddle Name"
                        )
                    
                    # Validation rule
                    col_val1, col_val2 = st.columns([3, 1])
                    with col_val1:
                        field_info['validation'] = st.text_input(
                            "Validation Pattern (regex)",
                            value=field_info.get('validation', ''),
                            key=f"q_val_{idx}_{field_name}",
                            placeholder=suggest_validation_rule(field_name, field_info['type'])
                        )
                    
                    with col_val2:
                        if st.button("Suggest", key=f"q_suggest_{idx}_{field_name}"):
                            suggested = suggest_validation_rule(field_name, field_info['type'])
                            if suggested:
                                field_info['validation'] = suggested
                                st.rerun()
                    
                    # Description/Help text
                    field_info['description'] = st.text_area(
                        "Help Text / Description",
                        value=field_info.get('description', ''),
                        height=60,
                        key=f"q_desc_{idx}_{field_name}",
                        placeholder="Provide additional guidance for this field..."
                    )
                
                with col2:
                    st.write("")  # Spacer
                    
                    # Actions
                    if st.button("🗑️ Remove", key=f"q_remove_{idx}_{field_name}", 
                               use_container_width=True):
                        del st.session_state.questionnaire_fields[field_name]
                        st.rerun()
                    
                    if st.button("📋 Duplicate", key=f"q_dup_{idx}_{field_name}",
                               use_container_width=True):
                        new_name = f"{field_name} (Copy)"
                        st.session_state.questionnaire_fields[new_name] = field_info.copy()
                        st.rerun()
                    
                    # Move to mapping
                    if st.button("➡️ To Mapping", key=f"q_to_map_{idx}_{field_name}",
                               use_container_width=True):
                        del st.session_state.questionnaire_fields[field_name]
                        # Add to PDF fields if not exists
                        if not any(f['name'] == field_name for f in st.session_state.pdf_fields):
                            st.session_state.pdf_fields.append({
                                'name': field_name,
                                'type': field_info['type'],
                                'value': '',
                                'required': field_info.get('required', False),
                                'page': 0,
                                'method': 'questionnaire'
                            })
                        st.rerun()
                
                # Update the field info
                st.session_state.questionnaire_fields[field_name] = field_info
    
    else:
        st.info("No questionnaire fields added yet. Add fields using the form above or move unmapped fields here.")
    
    # Conditional fields section
    st.markdown("---")
    st.subheader("⚡ Conditional Fields")
    
    # Add new conditional
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown("Define fields that appear based on conditions")
    with col2:
        if st.button("➕ Add Conditional", use_container_width=True):
            cond_id = f"condition_{len(st.session_state.conditional_fields) + 1}"
            st.session_state.conditional_fields[cond_id] = {
                "condition": "",
                "conditionTrue": "",
                "conditionFalse": "",
                "conditionType": "TextBox",
                "description": ""
            }
            st.rerun()
    
    # Display conditionals
    if st.session_state.conditional_fields:
        for cond_id, cond_info in list(st.session_state.conditional_fields.items()):
            with st.expander(f"⚡ {cond_id}", expanded=True):
                col1, col2 = st.columns([4, 1])
                
                with col1:
                    # Condition builder
                    st.markdown("**Condition Builder**")
                    
                    col_if1, col_if2, col_if3 = st.columns([2, 1, 2])
                    with col_if1:
                        field_select = st.selectbox(
                            "If field",
                            [""] + list(st.session_state.mapped_fields.keys()) + 
                            list(st.session_state.questionnaire_fields.keys()),
                            key=f"cond_field_{cond_id}"
                        )
                    
                    with col_if2:
                        operator = st.selectbox(
                            "is",
                            ["==", "!=", ">", "<", ">=", "<=", "contains", "starts with"],
                            key=f"cond_op_{cond_id}"
                        )
                    
                    with col_if3:
                        value = st.text_input(
                            "value",
                            key=f"cond_value_{cond_id}",
                            placeholder="e.g., Yes, H1B, true"
                        )
                    
                    # Build condition string
                    if field_select and operator and value:
                        if operator == "contains":
                            condition = f"{field_select}.includes('{value}')"
                        elif operator == "starts with":
                            condition = f"{field_select}.startsWith('{value}')"
                        else:
                            condition = f"{field_select} {operator} '{value}'"
                        
                        cond_info['condition'] = condition
                    
                    # Display full condition
                    st.text_input(
                        "Full Condition",
                        value=cond_info.get('condition', ''),
                        key=f"cond_full_{cond_id}",
                        help="You can also write complex conditions manually"
                    )
                    
                    # Results
                    col_true, col_false = st.columns(2)
                    
                    with col_true:
                        cond_info['conditionTrue'] = st.text_input(
                            "✅ If True, show/set",
                            value=cond_info.get('conditionTrue', ''),
                            key=f"cond_true_{cond_id}",
                            placeholder="e.g., Additional H1B Information"
                        )
                    
                    with col_false:
                        cond_info['conditionFalse'] = st.text_input(
                            "❌ If False, show/set",
                            value=cond_info.get('conditionFalse', ''),
                            key=f"cond_false_{cond_id}",
                            placeholder="e.g., Not Applicable"
                        )
                    
                    # Result type
                    cond_info['conditionType'] = st.selectbox(
                        "Result Type",
                        ["TextBox", "CheckBox", "Value", "ConditionBox", "Section"],
                        index=["TextBox", "CheckBox", "Value", "ConditionBox", "Section"].index(
                            cond_info.get('conditionType', 'TextBox')
                        ),
                        key=f"cond_type_{cond_id}"
                    )
                    
                    # Description
                    cond_info['description'] = st.text_area(
                        "Description",
                        value=cond_info.get('description', ''),
                        height=60,
                        key=f"cond_desc_{cond_id}",
                        placeholder="Explain when this condition applies..."
                    )
                
                with col2:
                    st.write("")  # Spacer
                    if st.button("🗑️ Remove", key=f"remove_cond_{cond_id}",
                               use_container_width=True):
                        del st.session_state.conditional_fields[cond_id]
                        st.rerun()
                    
                    if st.button("📋 Duplicate", key=f"dup_cond_{cond_id}",
                               use_container_width=True):
                        new_id = f"condition_{len(st.session_state.conditional_fields) + 1}"
                        st.session_state.conditional_fields[new_id] = cond_info.copy()
                        st.rerun()
                
                # Update condition
                st.session_state.conditional_fields[cond_id] = cond_info
    
    else:
        st.info("No conditional fields defined yet. Click 'Add Conditional' to create one.")

# Step 4: Validation & Groups
elif step == "4. Validation & Groups":
    st.header("✅ Step 4: Validation Rules & Field Groups")
    
    # Field Groups Section
    st.subheader("📁 Field Groups")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("Organize related fields into logical groups")
    with col2:
        if st.button("➕ Create Group", use_container_width=True):
            st.session_state.show_create_group = True
    
    # Create group dialog
    if st.session_state.get('show_create_group', False):
        with st.form("create_group_form"):
            st.subheader("Create Field Group")
            
            group_name = st.text_input(
                "Group Name",
                placeholder="e.g., Personal Information, Employment Details"
            )
            
            # Field selector
            all_fields = [f['name'] for f in st.session_state.pdf_fields]
            selected_fields = st.multiselect(
                "Select Fields",
                all_fields,
                help="Choose fields to include in this group"
            )
            
            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("Create", type="primary"):
                    if group_name and selected_fields:
                        create_field_group(group_name, selected_fields)
                        st.success(f"Created group: {group_name}")
                        st.session_state.show_create_group = False
                        st.rerun()
            
            with col2:
                if st.form_submit_button("Cancel"):
                    st.session_state.show_create_group = False
                    st.rerun()
    
    # Display existing groups
    if st.session_state.field_groups:
        for group_name, fields in st.session_state.field_groups.items():
            with st.expander(f"📁 {group_name} ({len(fields)} fields)", expanded=False):
                col1, col2 = st.columns([4, 1])
                
                with col1:
                    # Display fields in group
                    st.write("**Fields in this group:**")
                    for field in fields:
                        status = "✅" if field in st.session_state.mapped_fields else "❓" if field in st.session_state.questionnaire_fields else "❌"
                        st.write(f"{status} {field}")
                    
                    # Add more fields
                    available_fields = [f['name'] for f in st.session_state.pdf_fields if f['name'] not in fields]
                    new_fields = st.multiselect(
                        "Add more fields",
                        available_fields,
                        key=f"group_add_{group_name}"
                    )
                    
                    if new_fields:
                        st.session_state.field_groups[group_name].extend(new_fields)
                        st.rerun()
                
                with col2:
                    if st.button("🗑️ Delete Group", key=f"del_group_{group_name}",
                               use_container_width=True):
                        del st.session_state.field_groups[group_name]
                        st.rerun()
    
    else:
        st.info("No field groups created yet. Groups help organize related fields together.")
    
    # Validation Rules Section
    st.markdown("---")
    st.subheader("🔍 Validation Rules")
    
    # Quick validation templates
    st.markdown("**Quick Templates:**")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("📧 Email Fields", use_container_width=True):
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            for field in st.session_state.pdf_fields:
                if 'email' in field['name'].lower():
                    st.session_state.validation_rules[field['name']] = email_pattern
            st.success("Applied email validation!")
    
    with col2:
        if st.button("📞 Phone Fields", use_container_width=True):
            phone_pattern = r'^[\d\s\-\(\)\+]+$'
            for field in st.session_state.pdf_fields:
                if any(term in field['name'].lower() for term in ['phone', 'tel', 'fax']):
                    st.session_state.validation_rules[field['name']] = phone_pattern
            st.success("Applied phone validation!")
    
    with col3:
        if st.button("📅 Date Fields", use_container_width=True):
            date_pattern = r'^\d{1,2}/\d{1,2}/\d{4}$'
            for field in st.session_state.pdf_fields:
                if field['type'] == 'Date' or 'date' in field['name'].lower():
                    st.session_state.validation_rules[field['name']] = date_pattern
            st.success("Applied date validation!")
    
    with col4:
        if st.button("🔢 Number Fields", use_container_width=True):
            number_pattern = r'^\d+$'
            for field in st.session_state.pdf_fields:
                if 'number' in field['name'].lower() and field['type'] == 'TextBox':
                    st.session_state.validation_rules[field['name']] = number_pattern
            st.success("Applied number validation!")
    
    # Individual validation rules
    st.markdown("**Field-Specific Rules:**")
    
    # Filter to show only fields that might need validation
    validatable_fields = [f for f in st.session_state.pdf_fields 
                         if f['type'] in ['TextBox', 'Date', 'Currency']]
    
    if validatable_fields:
        for field in validatable_fields[:10]:  # Show first 10
            col1, col2, col3 = st.columns([2, 3, 1])
            
            with col1:
                st.text_input(
                    "Field",
                    value=field['name'],
                    disabled=True,
                    key=f"val_field_{field['name']}"
                )
            
            with col2:
                current_rule = st.session_state.validation_rules.get(field['name'], '')
                new_rule = st.text_input(
                    "Validation Pattern",
                    value=current_rule,
                    key=f"val_pattern_{field['name']}",
                    placeholder=suggest_validation_rule(field['name'], field['type'])
                )
                
                if new_rule != current_rule:
                    if new_rule:
                        st.session_state.validation_rules[field['name']] = new_rule
                    elif field['name'] in st.session_state.validation_rules:
                        del st.session_state.validation_rules[field['name']]
            
            with col3:
                if st.button("Test", key=f"val_test_{field['name']}",
                           use_container_width=True):
                    st.session_state[f"show_test_{field['name']}"] = True
            
            # Test validation
            if st.session_state.get(f"show_test_{field['name']}", False):
                test_value = st.text_input(
                    "Test value:",
                    key=f"val_test_value_{field['name']}",
                    placeholder="Enter a test value"
                )
                
                if test_value and field['name'] in st.session_state.validation_rules:
                    try:
                        import re
                        pattern = st.session_state.validation_rules[field['name']]
                        if re.match(pattern, test_value):
                            st.success("✅ Valid!")
                        else:
                            st.error("❌ Invalid!")
                    except:
                        st.error("Invalid regex pattern!")
        
        if len(validatable_fields) > 10:
            st.info(f"Showing 10 of {len(validatable_fields)} fields. More fields available.")
    
    # Validation summary
    if st.session_state.validation_rules:
        with st.expander("📊 Validation Summary", expanded=False):
            val_df = pd.DataFrame(
                [(field, rule) for field, rule in st.session_state.validation_rules.items()],
                columns=["Field", "Validation Pattern"]
            )
            st.dataframe(val_df, use_container_width=True)

# Step 5: Generate Output
elif step == "5. Generate Output":
    st.header("🚀 Step 5: Generate TypeScript Output")
    
    if not st.session_state.pdf_fields:
        st.warning("⚠️ Please complete the previous steps first!")
    else:
        form_name = st.session_state.get('form_name', 'Form')
        
        # Summary section
        st.subheader("📊 Configuration Summary")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Fields", len(st.session_state.pdf_fields))
            st.metric("Field Groups", len(st.session_state.field_groups))
        
        with col2:
            st.metric("Mapped Fields", len(st.session_state.mapped_fields))
            st.metric("Validation Rules", len(st.session_state.validation_rules))
        
        with col3:
            st.metric("Questionnaire", len(st.session_state.questionnaire_fields))
            st.metric("Default Values", len(st.session_state.default_fields))
        
        with col4:
            st.metric("Conditional", len(st.session_state.conditional_fields))
            completion = (len(st.session_state.mapped_fields) + 
                         len(st.session_state.questionnaire_fields)) / len(st.session_state.pdf_fields) * 100
            st.metric("Completion", f"{completion:.1f}%")
        
        # Default values section
        st.markdown("---")
        st.subheader("🔧 Default Values")
        
        col1, col2, col3, col4, col5 = st.columns([3, 3, 2, 1, 1])
        
        with col1:
            default_field = st.selectbox(
                "Field",
                [""] + [f['name'] for f in st.session_state.pdf_fields],
                key="default_field_select"
            )
        
        with col2:
            default_value = st.text_input(
                "Default Value",
                key="default_value_input",
                placeholder="Enter default value"
            )
        
        with col3:
            default_type = st.selectbox(
                "Type",
                ["TextBox", "CheckBox", "Value"],
                key="default_type_select"
            )
        
        with col4:
            st.write("")  # Spacer
            st.write("")  # Spacer
            if st.button("Add", use_container_width=True):
                if default_field and default_value:
                    st.session_state.default_fields[default_field] = f"{default_value}:{default_type}"
                    st.success(f"Added default for {default_field}")
                    st.rerun()
        
        with col5:
            st.write("")  # Spacer
            st.write("")  # Spacer
            if st.button("Clear All", use_container_width=True):
                st.session_state.default_fields = {}
                st.rerun()
        
        # Display current defaults
        if st.session_state.default_fields:
            st.markdown("**Current Default Values:**")
            for field, value in st.session_state.default_fields.items():
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.text(f"• {field} = {value}")
                with col2:
                    if st.button("Remove", key=f"del_default_{field}"):
                        del st.session_state.default_fields[field]
                        st.rerun()
        
        # Generation options
        st.markdown("---")
        st.subheader("⚙️ Generation Options")
        
        col1, col2 = st.columns(2)
        
        with col1:
            include_helpers = st.checkbox(
                "Include helper functions",
                value=True,
                help="Add validation and conditional evaluation functions"
            )
            
            include_types = st.checkbox(
                "Include TypeScript interfaces",
                value=True,
                help="Add type definitions for better IDE support"
            )
            
            minify_output = st.checkbox(
                "Minify output",
                value=False,
                help="Remove extra whitespace and comments"
            )
        
        with col2:
            output_format = st.selectbox(
                "Output Format",
                ["TypeScript (.ts)", "JavaScript (.js)", "JSON (.json)"],
                help="Choose the output file format"
            )
            
            add_comments = st.checkbox(
                "Add documentation comments",
                value=True,
                help="Include JSDoc comments for better documentation"
            )
            
            validate_output = st.checkbox(
                "Validate output",
                value=True,
                help="Check for common issues before generating"
            )
        
        # Generate button
        st.markdown("---")
        
        col1, col2, col3 = st.columns([2, 2, 2])
        
        with col2:
            if st.button("🚀 Generate TypeScript", type="primary", use_container_width=True):
                
                # Validation
                if validate_output:
                    issues = []
                    
                    # Check for unmapped fields
                    unmapped_count = len(st.session_state.pdf_fields) - \
                                   len(st.session_state.mapped_fields) - \
                                   len(st.session_state.questionnaire_fields)
                    
                    if unmapped_count > 5:
                        issues.append(f"⚠️ {unmapped_count} fields are still unmapped")
                    
                    # Check for empty questionnaire options
                    for field_name, field_info in st.session_state.questionnaire_fields.items():
                        if field_info['type'] in ['RadioButton', 'DropDown'] and not field_info.get('options'):
                            issues.append(f"⚠️ {field_name} is missing options")
                    
                    # Check conditional fields
                    for cond_id, cond_info in st.session_state.conditional_fields.items():
                        if not cond_info.get('condition'):
                            issues.append(f"⚠️ {cond_id} is missing condition")
                    
                    if issues:
                        st.warning("**Validation Issues Found:**")
                        for issue in issues:
                            st.write(issue)
                        
                        if not st.checkbox("Generate anyway", value=False):
                            st.stop()
                
                # Generate TypeScript
                with st.spinner("Generating TypeScript..."):
                    ts_content = generate_enhanced_typescript(
                        form_name,
                        st.session_state.mapped_fields,
                        st.session_state.questionnaire_fields,
                        st.session_state.conditional_fields,
                        st.session_state.default_fields,
                        st.session_state.validation_rules,
                        st.session_state.field_groups
                    )
                    
                    # Apply output options
                    if minify_output:
                        # Basic minification
                        ts_content = re.sub(r'\n\s*\n', '\n', ts_content)
                        ts_content = re.sub(r'    ', ' ', ts_content)
                    
                    # Convert to JavaScript if needed
                    if output_format == "JavaScript (.js)":
                        # Remove TypeScript-specific syntax
                        ts_content = re.sub(r'interface \w+ {[^}]+}', '', ts_content)
                        ts_content = re.sub(r': \w+(\[\])?', '', ts_content)
                        ts_content = ts_content.replace('.ts', '.js')
                    
                    elif output_format == "JSON (.json)":
                        # Extract just the configuration object
                        match = re.search(r'export const \w+ = ({[\s\S]+});', ts_content)
                        if match:
                            ts_content = match.group(1)
                
                st.success("✅ TypeScript generated successfully!")
                
                # Display output
                st.subheader("📄 Generated Output")
                
                # Code display with syntax highlighting
                st.code(ts_content, language="typescript" if output_format.startswith("Type") else "javascript")
                
                # Download options
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    file_extension = ".ts" if output_format.startswith("Type") else ".js" if output_format.startswith("Java") else ".json"
                    st.download_button(
                        label=f"📥 Download {output_format}",
                        data=ts_content,
                        file_name=f"{form_name}{file_extension}",
                        mime="text/plain",
                        use_container_width=True
                    )
                
                with col2:
                    # Export full configuration
                    config_json = export_mapping_configuration(form_name)
                    st.download_button(
                        label="💾 Download Full Config",
                        data=config_json,
                        file_name=f"{form_name}_config.json",
                        mime="application/json",
                        use_container_width=True
                    )
                
                with col3:
                    # Copy to clipboard button (using a workaround)
                    if st.button("📋 Copy to Clipboard", use_container_width=True):
                        st.info("Select all text above and copy (Ctrl+C / Cmd+C)")

# Step 6: Mapping Overview
elif step == "6. Mapping Overview":
    st.header("🗺️ Complete Mapping Overview")
    
    if not st.session_state.pdf_fields:
        st.warning("⚠️ No form data available. Please upload a PDF first.")
    else:
        # Display comprehensive mapping visualization
        display_mapping_visualization()
        
        # Export/Import section
        st.markdown("---")
        st.subheader("💾 Export/Import Configuration")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Export Options:**")
            
            export_format = st.selectbox(
                "Export Format",
                ["Complete Configuration (JSON)", "Mappings Only (CSV)", 
                 "TypeScript File", "Documentation (Markdown)"]
            )
            
            if st.button("Generate Export", type="primary", use_container_width=True):
                if export_format == "Complete Configuration (JSON)":
                    export_data = export_mapping_configuration(
                        st.session_state.get('form_name', 'form')
                    )
                    mime_type = "application/json"
                    file_ext = ".json"
                
                elif export_format == "Mappings Only (CSV)":
                    # Create CSV of mappings
                    mapping_data = []
                    for field_name, mapping in st.session_state.mapped_fields.items():
                        mapping_data.append({
                            'Field': field_name,
                            'Mapping': mapping,
                            'Type': next((f['type'] for f in st.session_state.pdf_fields 
                                        if f['name'] == field_name), 'Unknown')
                        })
                    
                    df = pd.DataFrame(mapping_data)
                    export_data = df.to_csv(index=False)
                    mime_type = "text/csv"
                    file_ext = ".csv"
                
                elif export_format == "TypeScript File":
                    export_data = generate_enhanced_typescript(
                        st.session_state.get('form_name', 'form'),
                        st.session_state.mapped_fields,
                        st.session_state.questionnaire_fields,
                        st.session_state.conditional_fields,
                        st.session_state.default_fields,
                        st.session_state.validation_rules,
                        st.session_state.field_groups
                    )
                    mime_type = "text/plain"
                    file_ext = ".ts"
                
                else:  # Documentation
                    # Generate markdown documentation
                    doc_lines = [
                        f"# Form Documentation: {st.session_state.get('form_name', 'Form')}",
                        f"\nGenerated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                        "\n## Summary",
                        f"- Total Fields: {len(st.session_state.pdf_fields)}",
                        f"- Mapped Fields: {len(st.session_state.mapped_fields)}",
                        f"- Questionnaire Fields: {len(st.session_state.questionnaire_fields)}",
                        f"- Conditional Fields: {len(st.session_state.conditional_fields)}",
                        "\n## Field Mappings",
                    ]
                    
                    for field_name, mapping in sorted(st.session_state.mapped_fields.items()):
                        doc_lines.append(f"- **{field_name}** → `{mapping}`")
                    
                    doc_lines.extend([
                        "\n## Questionnaire Fields",
                    ])
                    
                    for field_name, field_info in st.session_state.questionnaire_fields.items():
                        doc_lines.append(f"- **{field_name}** ({field_info['type']})")
                        if field_info.get('options'):
                            doc_lines.append(f"  - Options: {field_info['options']}")
                    
                    export_data = "\n".join(doc_lines)
                    mime_type = "text/markdown"
                    file_ext = ".md"
                
                st.download_button(
                    label=f"📥 Download {export_format}",
                    data=export_data,
                    file_name=f"{st.session_state.get('form_name', 'form')}{file_ext}",
                    mime=mime_type,
                    use_container_width=True
                )
        
        with col2:
            st.markdown("**Import Configuration:**")
            
            uploaded_config = st.file_uploader(
                "Choose configuration file",
                type=["json", "csv"],
                help="Import a previously exported configuration"
            )
            
            if uploaded_config:
                if st.button("Import Configuration", type="primary", use_container_width=True):
                    try:
                        if uploaded_config.type == "application/json":
                            config_content = uploaded_config.read().decode('utf-8')
                            success, message = import_mapping_configuration(config_content)
                            
                            if success:
                                st.success(message)
                                st.balloons()
                                st.rerun()
                            else:
                                st.error(message)
                        
                        elif uploaded_config.type == "text/csv":
                            # Import CSV mappings
                            df = pd.read_csv(uploaded_config)
                            
                            if 'Field' in df.columns and 'Mapping' in df.columns:
                                st.session_state.mapped_fields = {}
                                for _, row in df.iterrows():
                                    st.session_state.mapped_fields[row['Field']] = row['Mapping']
                                
                                st.success(f"Imported {len(df)} field mappings!")
                                st.rerun()
                            else:
                                st.error("CSV must contain 'Field' and 'Mapping' columns")
                    
                    except Exception as e:
                        st.error(f"Import failed: {str(e)}")
        
        # Field search and filter
        st.markdown("---")
        st.subheader("🔍 Field Search & Analysis")
        
        search_term = st.text_input(
            "Search across all fields:",
            placeholder="Enter field name, mapping, or type..."
        )
        
        if search_term:
            results = []
            
            # Search in all fields
            for field in st.session_state.pdf_fields:
                field_name = field['name']
                field_type = field['type']
                
                # Check if search term matches
                if (search_term.lower() in field_name.lower() or 
                    search_term.lower() in field_type.lower()):
                    
                    # Determine status and mapping
                    if field_name in st.session_state.mapped_fields:
                        status = "Mapped"
                        mapping = st.session_state.mapped_fields[field_name]
                    elif field_name in st.session_state.questionnaire_fields:
                        status = "Questionnaire"
                        mapping = "N/A"
                    else:
                        status = "Unmapped"
                        mapping = "N/A"
                    
                    results.append({
                        'Field': field_name,
                        'Type': field_type,
                        'Status': status,
                        'Mapping': mapping,
                        'Validation': '✓' if field_name in st.session_state.validation_rules else '',
                        'Group': next((g for g, fields in st.session_state.field_groups.items() 
                                     if field_name in fields), '')
                    })
            
            # Search in mappings
            for field_name, mapping in st.session_state.mapped_fields.items():
                if search_term.lower() in mapping.lower():
                    if not any(r['Field'] == field_name for r in results):
                        field_type = next((f['type'] for f in st.session_state.pdf_fields 
                                         if f['name'] == field_name), 'Unknown')
                        results.append({
                            'Field': field_name,
                            'Type': field_type,
                            'Status': 'Mapped',
                            'Mapping': mapping,
                            'Validation': '✓' if field_name in st.session_state.validation_rules else '',
                            'Group': next((g for g, fields in st.session_state.field_groups.items() 
                                         if field_name in fields), '')
                        })
            
            if results:
                st.write(f"Found {len(results)} results:")
                results_df = pd.DataFrame(results)
                st.dataframe(results_df, use_container_width=True)
            else:
                st.info("No results found")

# Helper function for field mapping display
def display_field_mapping_row(field):
    """Display a single field mapping row"""
    field_name = field['name']
    field_type = field['type']
    
    # Create unique key for this field
    field_key = hashlib.md5(field_name.encode()).hexdigest()[:8]
    
    col1, col2, col3, col4, col5 = st.columns([3, 3, 1, 1, 1])
    
    with col1:
        # Field name and type
        st.text_input(
            "Field",
            value=f"{field_name} ({field_type})",
            disabled=True,
            key=f"display_{field_key}"
        )
    
    with col2:
        # Mapping input
        current_mapping = st.session_state.mapped_fields.get(field_name, '')
        
        # Suggest mapping if none exists
        if not current_mapping and field_name not in st.session_state.questionnaire_fields:
            suggested, confidence = auto_map_field_enhanced(
                field_name,
                st.session_state.get('extracted_text', '')
            )
            placeholder = suggested if suggested else "e.g., customer.field_name"
        else:
            placeholder = "e.g., customer.field_name"
        
        mapping = st.text_input(
            "Mapping",
            value=current_mapping,
            key=f"map_{field_key}",
            placeholder=placeholder,
            disabled=field_name in st.session_state.questionnaire_fields
        )
        
        # Update mapping if changed
        if mapping != current_mapping and field_name not in st.session_state.questionnaire_fields:
            if mapping:
                st.session_state.mapped_fields[field_name] = mapping
            elif field_name in st.session_state.mapped_fields:
                del st.session_state.mapped_fields[field_name]
    
    with col3:
        # Quick actions
        if field_name not in st.session_state.questionnaire_fields:
            if st.button("❓", key=f"quest_{field_key}",
                       help="Move to questionnaire", use_container_width=True):
                st.session_state.questionnaire_fields[field_name] = {
                    'type': field_type,
                    'required': field.get('required', False),
                    'options': '',
                    'validation': ''
                }
                if field_name in st.session_state.mapped_fields:
                    del st.session_state.mapped_fields[field_name]
                st.rerun()
    
    with col4:
        # Validation indicator
        if field_name in st.session_state.validation_rules:
            st.button("✓", key=f"val_ind_{field_key}",
                    help=f"Validation: {st.session_state.validation_rules[field_name]}",
                    use_container_width=True, disabled=True)
        else:
            if st.button("＋", key=f"add_val_{field_key}",
                       help="Add validation", use_container_width=True):
                suggested = suggest_validation_rule(field_name, field_type)
                if suggested:
                    st.session_state.validation_rules[field_name] = suggested
                    st.rerun()
    
    with col5:
        # Status indicator
        if field_name in st.session_state.mapped_fields:
            st.success("✅")
        elif field_name in st.session_state.questionnaire_fields:
            st.info("❓")
        else:
            st.error("❌")

# Footer
st.markdown("---")
with st.expander("💡 Help & Documentation", expanded=False):
    st.markdown("""
    ### 📚 Enhanced PDF Form Automation System
    
    This tool helps you create TypeScript configurations for PDF form automation with advanced features:
    
    #### 🚀 Key Features:
    - **Smart Field Extraction**: Multiple methods to extract fields from PDFs
    - **Intelligent Auto-Mapping**: Pattern-based field mapping with confidence scoring
    - **Questionnaire Builder**: Create dynamic forms with validation
    - **Conditional Logic**: Define fields that appear based on conditions
    - **Field Groups**: Organize related fields together
    - **Validation Rules**: Regex-based field validation
    - **Import/Export**: Save and reuse configurations
    
    #### 📋 Workflow:
    1. **Upload PDF**: Select your form PDF file
    2. **Extract Fields**: Automatically extract form fields
    3. **Map Fields**: Connect PDF fields to database paths
    4. **Setup Questionnaire**: Configure dynamic form fields
    5. **Add Validation**: Define field validation rules
    6. **Generate Output**: Create TypeScript/JavaScript files
    
    #### 🎯 Best Practices:
    - Use auto-mapping for common fields
    - Group related fields together
    - Add validation for data integrity
    - Test conditional logic thoroughly
    - Export configurations for reuse
    
    #### 🔧 Common Mappings:
    - Customer: `customer.customer_name`, `customer.customer_tax_id`
    - Beneficiary: `beneficiary.Beneficiary.beneficiaryFirstName`
    - Attorney: `attorney.attorneyInfo.lastName`
    - Address: `address.addressStreet`, `address.addressCity`
    - Case: `case.caseType`, `case.jobTitle`
    
    #### ⌨️ Keyboard Shortcuts:
    - `Tab`: Navigate between fields
    - `Enter`: Confirm input
    - `Escape`: Close dialogs
    
    For more help, check the documentation or contact support.
    """)

# Save state on change
if st.session_state.get('auto_save', True):
    # This would typically save to a database or file
    pass
