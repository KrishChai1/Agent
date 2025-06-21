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

# PDF library imports with fallbacks
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

# Enhanced USCIS Form Database
USCIS_FORMS_DATABASE = {
    'I-129': {
        'title': 'Petition for a Nonimmigrant Worker',
        'patterns': [r'Form\s*I-129', r'Petition.*Nonimmigrant.*Worker'],
        'parts': OrderedDict([
            ('Part 1', 'Petitioner Information'),
            ('Part 2', 'Information About This Petition'),
            ('Part 3', 'Beneficiary Information'),
            ('Part 4', 'Processing Information'),
            ('Part 5', 'Basic Information About the Proposed Employment and Employer'),
            ('Part 6', 'Certification Regarding the Release of Controlled Technology'),
            ('Part 7', 'Signature of Petitioner'),
            ('Part 8', 'Declaration of Person Preparing Form'),
            ('Part 9', 'Additional Information')
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
            ('Part 5', 'Applicant\'s Statement and Signature'),
            ('Part 6', 'Interpreter\'s Contact Information'),
            ('Part 7', 'Preparer\'s Contact Information')
        ])
    },
    'I-140': {
        'title': 'Immigrant Petition for Alien Worker',
        'patterns': [r'Form\s*I-140', r'Immigrant.*Petition.*Worker'],
        'parts': OrderedDict([
            ('Part 1', 'Information About the Petitioner'),
            ('Part 2', 'Petition Type'),
            ('Part 3', 'Information About the Person You Are Filing For'),
            ('Part 4', 'Processing Information'),
            ('Part 5', 'Additional Information About the Petitioner'),
            ('Part 6', 'Basic Information About the Proposed Employment'),
            ('Part 7', 'Information on Spouse and Children'),
            ('Part 8', 'Certification'),
            ('Part 9', 'Signature'),
            ('Part 10', 'Preparer\'s Information')
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
            ('Part 9', 'Accommodations for Disabilities'),
            ('Part 10', 'Applicant\'s Statement and Signature'),
            ('Part 11', 'Interpreter\'s Information'),
            ('Part 12', 'Preparer\'s Information'),
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
            ('Part 3', 'Applicant\'s Statement and Signature'),
            ('Part 4', 'Interpreter\'s Information'),
            ('Part 5', 'Preparer\'s Information'),
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
            ('Part 4', 'Information About Your Travel'),
            ('Part 5', 'Reentry Permit'),
            ('Part 6', 'Refugee Travel Document'),
            ('Part 7', 'Advance Parole Document'),
            ('Part 8', 'Signature'),
            ('Part 9', 'Preparer\'s Information')
        ])
    },
    'G-28': {
        'title': 'Notice of Entry of Appearance as Attorney or Accredited Representative',
        'patterns': [r'Form\s*G-28', r'Notice.*Entry.*Appearance'],
        'parts': OrderedDict([
            ('Part 1', 'Information About Attorney or Representative'),
            ('Part 2', 'Eligibility Information'),
            ('Part 3', 'Notice of Appearance'),
            ('Part 4', 'Client Consent'),
            ('Part 5', 'Signature of Attorney or Representative')
        ])
    },
    'LCA': {
        'title': 'Labor Condition Application (ETA Form 9035)',
        'patterns': [r'ETA.*9035', r'Labor.*Condition.*Application', r'LCA'],
        'parts': OrderedDict([
            ('Section A', 'Offering Employer'),
            ('Section B', 'Rate of Pay'),
            ('Section C', 'Employer Point of Contact'),
            ('Section D', 'Employer Business Information'),
            ('Section E', 'Attorney/Agent Information'),
            ('Section F', 'Employment and Wage Information'),
            ('Section G', 'Employer Labor Condition Statements'),
            ('Section H', 'Additional Employer Labor Condition Statements'),
            ('Section I', 'Public Disclosure Information'),
            ('Section J', 'Signature')
        ])
    }
}

# Enhanced Mapping Patterns based on the mapping document
ENHANCED_MAPPING_PATTERNS = {
    # Customer/Company Information
    'customer': {
        'customer_name': [
            r'(?:petitioner|company|employer|organization|legal\s*business)\s*name',
            r'name\s*of\s*(?:petitioner|employer|company)',
            r'(?:P|Part)1.*Item2(?:_|\.)?(?:Company|Petitioner)?Name',  # I-129 Part 1 Item 2
            r'legal\s*business\s*name',
            r'entity.*name'
        ],
        'customer_tax_id': [
            r'(?:fein|ein|tax\s*id)',
            r'employer.*identification',
            r'federal.*employer.*identification',
            r'(?:P|Part)1.*Item5(?:_|\.)?FEIN',  # I-129 Part 1 Item 5
            r'(?:P|Part)1.*Item4(?:_|\.)?FEIN'   # I-140 Part 1 Item 4
        ],
        'signatory_name': [
            r'in\s*care\s*of',
            r'signatory',
            r'authorized.*representative',
            r'contact.*person',
            r'(?:P|Part)1.*Item3(?:_|\.)?InCareOf'  # I-129 Part 1 Item 3
        ],
        'signatory_first_name': [
            r'(?:signatory|contact).*first.*name',
            r'first\s*name.*(?:signatory|contact)',
            r'given\s*name.*(?:signatory|contact)',
            r'(?:P|Part)1.*Item3a(?:_|\.)?First'
        ],
        'signatory_last_name': [
            r'(?:signatory|contact).*last.*name',
            r'last\s*name.*(?:signatory|contact)',
            r'family\s*name.*(?:signatory|contact)',
            r'(?:P|Part)1.*Item3a(?:_|\.)?Last'
        ],
        'signatory_job_title': [
            r'(?:title|job\s*title|position)',
            r'contact.*job\s*title',
            r'(?:P|Part)1.*Item7b(?:_|\.)?Title'  # G-28 Part 3 Item 7b
        ],
        'signatory_work_phone': [
            r'(?:daytime\s*)?phone',
            r'telephone.*number',
            r'(?:P|Part)1.*Item4(?:_|\.)?Phone',  # I-129 Part 1 Item 4
            r'(?:P|Part)1.*Item10(?:_|\.)?Phone'  # G-28 Part 3 Item 10
        ],
        'signatory_email_id': [
            r'email',
            r'e-mail',
            r'(?:P|Part)1.*Item4(?:_|\.)?Email',  # I-129 Part 1 Item 4
            r'(?:P|Part)1.*Item12(?:_|\.)?Email'  # G-28 Part 3 Item 12
        ],
        'address_street': [
            r'(?:street|address\s*1)',
            r'petitioner.*address',
            r'company.*address',
            r'employer.*address',
            r'(?:P|Part)1.*Item3(?:_|\.)?Street',  # I-129 Part 1 Item 3
            r'(?:P|Part)1.*Item13a(?:_|\.)?Street'  # G-28 Part 3 Item 13a
        ],
        'address_city': [
            r'city',
            r'town',
            r'(?:P|Part)1.*Item3(?:_|\.)?City',
            r'(?:P|Part)1.*Item13c(?:_|\.)?City'
        ],
        'address_state': [
            r'state',
            r'province',
            r'(?:P|Part)1.*Item3(?:_|\.)?State',
            r'(?:P|Part)1.*Item13d(?:_|\.)?State'
        ],
        'address_zip': [
            r'zip.*code',
            r'postal.*code',
            r'(?:P|Part)1.*Item3(?:_|\.)?Zip',
            r'(?:P|Part)1.*Item13e(?:_|\.)?Zip'
        ]
    },
    
    # Beneficiary Information
    'beneficiary': {
        'beneficiaryFirstName': [
            r'(?:given|first)\s*name',
            r'beneficiary.*first',
            r'(?:P|Part)3.*Item2(?:_|\.)?FirstName',  # I-129 Part 3 Item 2
            r'(?:P|Part)1.*Item1b(?:_|\.)?FirstName',  # I-539 Part 1 Item 1b
            r'(?:P|Part)3.*Item1b(?:_|\.)?FirstName'   # I-140 Part 3 Item 1b
        ],
        'beneficiaryLastName': [
            r'(?:family|last)\s*name',
            r'surname',
            r'beneficiary.*last',
            r'(?:P|Part)3.*Item2(?:_|\.)?LastName',   # I-129 Part 3 Item 2
            r'(?:P|Part)1.*Item1a(?:_|\.)?LastName',   # I-539 Part 1 Item 1a
            r'(?:P|Part)3.*Item1a(?:_|\.)?LastName'    # I-140 Part 3 Item 1a
        ],
        'beneficiaryMiddleName': [
            r'middle.*name',
            r'middle.*initial',
            r'(?:P|Part)1.*Item1c(?:_|\.)?MiddleName',
            r'(?:P|Part)3.*Item1c(?:_|\.)?MiddleName'
        ],
        'beneficiaryDateOfBirth': [
            r'date.*birth',
            r'birth.*date',
            r'd\.?o\.?b',
            r'(?:P|Part)3.*Item5(?:_|\.)?DOB',        # I-129 Part 3 Item 5
            r'(?:P|Part)1.*Item8(?:_|\.)?DOB',        # I-539 Part 1 Item 8
            r'(?:P|Part)3.*Item3(?:_|\.)?DOB'         # I-140 Part 3 Item 3
        ],
        'alien_number': [
            r'alien.*number',
            r'a[\-\s]?number',
            r'uscis.*number',
            r'(?:P|Part)3.*Item5(?:_|\.)?AlienNumber',  # I-129 Part 3 Item 5
            r'(?:P|Part)1.*Item2(?:_|\.)?AlienNumber',  # I-539 Part 1 Item 2
            r'(?:P|Part)3.*Item8(?:_|\.)?AlienNumber'   # I-140 Part 3 Item 8
        ],
        'beneficiarySsn': [
            r'social.*security',
            r'ssn',
            r'ss.*number',
            r'(?:P|Part)3.*Item5(?:_|\.)?SSN',         # I-129 Part 3 Item 5
            r'(?:P|Part)1.*Item9(?:_|\.)?SSN',         # I-539 Part 1 Item 9
            r'(?:P|Part)3.*Item9(?:_|\.)?SSN'          # I-140 Part 3 Item 9
        ],
        'beneficiaryGender': [
            r'gender',
            r'sex',
            r'(?:P|Part)3.*Item5(?:_|\.)?Gender'       # I-129 Part 3 Item 5
        ],
        'beneficiaryCountryOfBirth': [
            r'country.*birth',
            r'birth.*country',
            r'(?:P|Part)3.*Item4(?:_|\.)?CountryOfBirth',  # I-129 Part 3 Item 4
            r'(?:P|Part)1.*Item6(?:_|\.)?CountryOfBirth',  # I-539 Part 1 Item 6
            r'(?:P|Part)3.*Item6(?:_|\.)?CountryOfBirth'   # I-140 Part 3 Item 6
        ],
        'beneficiaryCitizenOfCountry': [
            r'citizenship',
            r'nationality',
            r'citizen.*country',
            r'(?:P|Part)3.*Item4(?:_|\.)?Citizenship',     # I-129 Part 3 Item 4
            r'(?:P|Part)1.*Item7(?:_|\.)?Citizenship'      # I-539 Part 1 Item 7
        ],
        'i94Number': [
            r'i[\-\s]?94.*number',
            r'arrival.*departure.*record',
            r'(?:P|Part)3.*Item6(?:_|\.)?I94',             # I-129 Part 3 Item 6
            r'(?:P|Part)1.*Item11(?:_|\.)?I94'             # I-539 Part 1 Item 11
        ],
        'passportNumber': [
            r'passport.*number',
            r'travel.*document.*number',
            r'(?:P|Part)3.*Item6(?:_|\.)?Passport',        # I-129 Part 3 Item 6
            r'(?:P|Part)1.*Item12(?:_|\.)?Passport'        # I-539 Part 1 Item 12
        ],
        'visaStatus': [
            r'current.*status',
            r'nonimmigrant.*status',
            r'(?:P|Part)1.*Item15a(?:_|\.)?Status'         # I-539 Part 1 Item 15a
        ]
    },
    
    # Attorney Information
    'attorney': {
        'lastName': [
            r'attorney.*last',
            r'preparer.*last',
            r'representative.*last',
            r'(?:P|Part)8.*Item1(?:_|\.)?LastName',     # I-129 Part 8 Item 1
            r'(?:P|Part)1.*Item2a(?:_|\.)?FamilyName',  # G-28 Part 1 Item 2a
            r'(?:Pt|P)1Line1a(?:_|\.)?FamilyName'       # G-28 simplified format
        ],
        'firstName': [
            r'attorney.*first',
            r'preparer.*first',
            r'representative.*first',
            r'(?:P|Part)8.*Item1(?:_|\.)?FirstName',    # I-129 Part 8 Item 1
            r'(?:P|Part)1.*Item2b(?:_|\.)?GivenName',   # G-28 Part 1 Item 2b
            r'(?:Pt|P)1Line1b(?:_|\.)?GivenName'        # G-28 simplified format
        ],
        'stateBarNumber': [
            r'bar.*number',
            r'license.*number',
            r'state.*bar',
            r'(?:P|Part)2.*Item1b(?:_|\.)?BarNumber',   # G-28 Part 2 Item 1b
            r'(?:Pt|P)2Line1b(?:_|\.)?BarNumber'        # G-28 simplified format
        ],
        'lawFirmName': [
            r'firm.*name',
            r'law.*firm',
            r'organization.*name',
            r'(?:P|Part)8.*Item2(?:_|\.)?Organization', # I-129 Part 8 Item 2
            r'(?:P|Part)2.*Item1d(?:_|\.)?LawFirm',     # G-28 Part 2 Item 1d
            r'(?:P|Part)1.*Item1d(?:_|\.)?LawFirm'      # G-28 Part 1 Item 1d
        ],
        'workPhone': [
            r'(?:attorney|preparer).*phone',
            r'daytime.*telephone',
            r'(?:P|Part)1.*Item4(?:_|\.)?DaytimePhone', # G-28 Part 1 Item 4
            r'(?:Pt|P)1Line4(?:_|\.)?DaytimePhone'      # G-28 simplified format
        ],
        'emailAddress': [
            r'(?:attorney|preparer).*email',
            r'email.*address',
            r'(?:P|Part)1.*Item6(?:_|\.)?Email',        # G-28 Part 1 Item 6
            r'(?:Pt|P)1Line6(?:_|\.)?Email'             # G-28 simplified format
        ]
    },
    
    # LCA Information
    'lca': {
        'position_job_title': [
            r'job.*title',
            r'position',
            r'occupation',
            r'employment.*title',
            r'(?:P|Part)5.*Item1(?:_|\.)?JobTitle'      # I-129 Part 5 Item 1
        ],
        'lcaNumber': [
            r'lca.*number',
            r'eta.*case',
            r'lca.*case.*#',
            r'(?:P|Part)5.*Item2(?:_|\.)?LCANumber'     # I-129 Part 5 Item 2
        ],
        'start_date': [
            r'start.*date',
            r'begin.*date',
            r'employment.*start',
            r'from.*date',
            r'(?:P|Part)5.*Item11(?:_|\.)?From'         # I-129 Part 5 Item 11
        ],
        'end_date': [
            r'end.*date',
            r'employment.*end',
            r'to.*date',
            r'(?:P|Part)5.*Item11(?:_|\.)?To'           # I-129 Part 5 Item 11
        ],
        'gross_salary': [
            r'wage',
            r'salary',
            r'compensation',
            r'pay.*rate',
            r'(?:P|Part)5.*Item9(?:_|\.)?Salary'        # I-129 Part 5 Item 9
        ]
    },
    
    # Case Information
    'case': {
        'caseType': [
            r'classification',
            r'visa.*type',
            r'petition.*type',
            r'(?:P|Part)2.*Item1(?:_|\.)?Classification' # I-129 Part 2 Item 1
        ],
        'caseSubType': [
            r'basis.*classification',
            r'requested.*action',
            r'(?:P|Part)2.*Item2(?:_|\.)?Basis'         # I-129 Part 2 Item 2
        ],
        'h1BPetitionType': [
            r'cap.*exempt',
            r'h.*1.*b.*cap'
        ]
    }
}

# Field type detection patterns
FIELD_TYPE_PATTERNS = {
    'CheckBox': [
        r'\[\s*\]',
        r'\(\s*\)',
        r'check.*box',
        r'select.*one',
        r'mark.*x'
    ],
    'RadioButton': [
        r'\(\s*\)',
        r'select.*only.*one',
        r'choose.*one'
    ],
    'Date': [
        r'date',
        r'mm[/\-]dd[/\-]yyyy',
        r'dob',
        r'birth.*date',
        r'expire'
    ],
    'Signature': [
        r'signature',
        r'sign.*here'
    ],
    'Currency': [
        r'amount',
        r'fee',
        r'wage',
        r'salary',
        r'\$',
        r'compensation'
    ],
    'Phone': [
        r'phone',
        r'telephone',
        r'fax'
    ],
    'Email': [
        r'email',
        r'e-mail'
    ],
    'TextArea': [
        r'describe',
        r'explain',
        r'additional.*information',
        r'details'
    ],
    'Number': [
        r'number',
        r'count',
        r'total',
        r'#'
    ]
}

# Enhanced CSS
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
    
    /* Enhanced Metrics */
    div[data-testid="metric-container"] {
        background: var(--light-gray);
        border: 1px solid var(--border-gray);
        padding: 16px;
        border-radius: 6px;
        text-align: center;
    }
    
    /* Mapping Suggestion */
    .mapping-suggestion {
        position: relative;
        background: var(--info-blue);
        color: white;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 0.85em;
        margin-top: 4px;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
def init_session_state():
    """Initialize session state with USCIS-specific structure"""
    defaults = {
        'pdf_fields': [],
        'form_parts': OrderedDict(),
        'mapped_fields': {},
        'questionnaire_fields': {},
        'conditional_fields': {},
        'default_fields': {},
        'form_metadata': {},
        'extracted_text': "",
        'form_name': '',
        'form_type': None,
        'uscis_form_number': None,
        'current_step': 1,
        'show_mapped': True,
        'show_unmapped': True,
        'show_questionnaire': True,
        'show_raw_names': False,
        'removed_fields': [],
        'processing_log': [],
        'attorney_fields': [],
        'expand_all_parts': False,
        'expanded_parts': set(),
        'mapping_suggestions': {},
        'field_detection_confidence': {},
        'categorized_mappings': {
            'customerData': {},
            'beneficiaryData': {},
            'attorneyData': {},
            'lcaData': {},
            'caseData': {},
            'questionnaireData': {},
            'defaultData': {},
            'conditionalData': {}
        }
    }
    
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

init_session_state()

# Enhanced mapping suggestion using the document patterns
def suggest_mapping_enhanced(field_name: str, category: str = None) -> Tuple[Optional[str], float]:
    """Enhanced mapping suggestion with confidence scoring based on mapping document"""
    field_lower = field_name.lower()
    field_clean = re.sub(r'[^\w\s]', ' ', field_lower).strip()
    
    best_match = None
    best_confidence = 0.0
    best_category = None
    best_field = None
    
    # Check patterns from ENHANCED_MAPPING_PATTERNS
    categories_to_check = [category] if category else ENHANCED_MAPPING_PATTERNS.keys()
    
    for cat in categories_to_check:
        if cat not in ENHANCED_MAPPING_PATTERNS:
            continue
            
        category_patterns = ENHANCED_MAPPING_PATTERNS[cat]
        
        for field_key, patterns in category_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, field_clean, re.IGNORECASE)
                if match:
                    # Calculate confidence
                    match_length = len(match.group(0))
                    field_length = len(field_clean)
                    confidence = match_length / field_length if field_length > 0 else 0
                    
                    # Boost confidence for exact matches
                    if match.group(0) == field_clean:
                        confidence = 1.0
                    
                    # Boost confidence for specific patterns
                    if 'item' in field_clean and 'item' in pattern:
                        confidence *= 1.3
                    
                    confidence = min(confidence, 1.0)
                    
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_category = cat
                        best_field = field_key
                        
                        # Construct the mapping path
                        if cat == 'customer':
                            best_match = f"customer.{field_key}"
                        elif cat == 'beneficiary':
                            if field_key.startswith('i94'):
                                best_match = f"beneficiary.I94Details.I94.{field_key}"
                            elif field_key.startswith('passport'):
                                best_match = f"beneficiary.PassportDetails.Passport.{field_key}"
                            elif field_key.startswith('visa'):
                                best_match = f"beneficiary.VisaDetails.Visa.{field_key}"
                            else:
                                best_match = f"beneficiary.Beneficiary.{field_key}"
                        elif cat == 'attorney':
                            if field_key in ['lawFirmName']:
                                best_match = f"attorneyLawfirmDetails.lawfirmDetails.{field_key}"
                            else:
                                best_match = f"attorney.attorneyInfo.{field_key}"
                        elif cat == 'lca':
                            best_match = f"lca.Lca.{field_key}"
                        elif cat == 'case':
                            best_match = f"case.{field_key}"
    
    return best_match, best_confidence

# Determine field type from patterns
def determine_field_type_enhanced(field_name: str) -> str:
    """Enhanced field type determination"""
    field_lower = field_name.lower()
    
    for field_type, patterns in FIELD_TYPE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, field_lower):
                return field_type
    
    return 'TextBox'

# Enhanced field name cleaning for USCIS forms
def clean_uscis_field_name(raw_field_name: str) -> str:
    """
    Clean and standardize USCIS PDF field names by extracting meaningful parts
    from common form naming patterns.

    Parameters:
        raw_field_name (str): The raw field name from the USCIS form.

    Returns:
        str: Cleaned and simplified field name.
    """
    patterns = [
        # G-28 style: form[0].#subform[0].Pt1Line1a_FamilyName[0]
        r'form\[\d+\]\.#?subform\[\d+\]\.(.*?)\[\d+\]',
        # I-129 style: topmostSubform[0].Page1[0].Part1_Item2_CompanyName[0]
        r'topmostSubform\[\d+\]\.Page\d+\[\d+\]\.(.*?)\[\d+\]',
        # Alternate style: Form1[0].Page1[0].Part1_1a_LastName[0]
        r'Form\d*\[\d+\]\.Page\d+\[\d+\]\.(.*?)\[\d+\]',
        # Simple fallback: capture anything after a known dot part
        r'.*\.(P(?:art|t)\d+.*?)'
    ]

    for pattern in patterns:
        match = re.search(pattern, raw_field_name)
        if match:
            return match.group(1)

    # Return original if no pattern matched
    return raw_field_name

def organize_fields_by_parts_enhanced(fields: List[Dict], form_type: Optional[str]) -> OrderedDict:
    """Enhanced organization of fields by form parts using field name analysis"""
    form_parts = OrderedDict()
    
    # Always add attorney section first
    form_parts['Part 0 - Attorney/Preparer Information'] = []
    
    # Collect all parts found in field names
    parts_found = {}
    
    # First pass: identify all parts in the fields
    for field in fields:
        cleaned_name = field['name']
        part_id, part_order = extract_part_from_field_name(cleaned_name)
        
        if part_id != "Unassigned":
            if part_id not in parts_found:
                parts_found[part_id] = part_order
    
    # Sort parts by their order
    sorted_parts = sorted(parts_found.items(), key=lambda x: x[1])
    
    # Add known parts for the form type (if available)
    if form_type and form_type in USCIS_FORMS_DATABASE:
        for part_key, part_desc in USCIS_FORMS_DATABASE[form_type]['parts'].items():
            full_part_name = f'{part_key} - {part_desc}'
            if full_part_name not in form_parts:
                form_parts[full_part_name] = []
    
    # Add discovered parts
    for part_id, _ in sorted_parts:
        if form_type and form_type in USCIS_FORMS_DATABASE:
            # Try to match with known parts
            matched = False
            for part_key, part_desc in USCIS_FORMS_DATABASE[form_type]['parts'].items():
                if part_id.lower() == part_key.lower():
                    full_part_name = f'{part_key} - {part_desc}'
                    if full_part_name not in form_parts:
                        form_parts[full_part_name] = []
                    matched = True
                    break
            if not matched and part_id not in form_parts:
                form_parts[part_id] = []
        else:
            if part_id not in form_parts:
                form_parts[part_id] = []
    
    # Add unassigned section
    form_parts['Unassigned Fields'] = []
    
    # Second pass: organize fields into parts
    for field in fields:
        cleaned_name = field['name']
        field_name_lower = cleaned_name.lower()
        assigned = False
        
        # Check if it's an attorney field
        attorney_keywords = ['attorney', 'preparer', 'representative', 'g-28', 'g28', 'bar', 'accredited']
        if any(keyword in field_name_lower for keyword in attorney_keywords):
            form_parts['Part 0 - Attorney/Preparer Information'].append(field)
            assigned = True
        else:
            # Extract part from field name
            part_id, _ = extract_part_from_field_name(cleaned_name)
            
            # Find the right part to assign to
            if part_id != "Unassigned":
                # Look for exact match first
                if part_id in form_parts:
                    form_parts[part_id].append(field)
                    assigned = True
                else:
                    # Look for matching part in known parts
                    for part_name in form_parts.keys():
                        if part_id.lower() in part_name.lower():
                            form_parts[part_name].append(field)
                            assigned = True
                            break
        
        if not assigned:
            form_parts['Unassigned Fields'].append(field)
    
    # Store suggestions
    for field in fields:
        if field.get('suggested_mapping'):
            st.session_state.mapping_suggestions[field['name']] = {
                'mapping': field['suggested_mapping'],
                'confidence': field.get('confidence', 0.0)
            }
    
    # Remove empty parts (except Part 0 and Unassigned)
    parts_to_keep = OrderedDict()
    for part_name, part_fields in form_parts.items():
        if part_fields or part_name in ['Part 0 - Attorney/Preparer Information', 'Unassigned Fields']:
            parts_to_keep[part_name] = part_fields
    
    return parts_to_keep

def organize_fields_by_parts(fields: List[Dict], form_type: Optional[str]) -> OrderedDict:
    """Organize fields by form parts - enhanced version"""
    return organize_fields_by_parts_enhanced(fields, form_type)

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
        
        # Show fields
        for field_idx, field in enumerate(part_fields):
            if field['name'] in st.session_state.removed_fields:
                continue
            render_field_row(field, f"{part_index}_{field_idx}")
        
        # Add some spacing
        st.markdown("<br>", unsafe_allow_html=True)

def render_field_row(field: Dict, unique_key: str):
    """Render a field row with mapping options"""
    field_name = field['name']
    field_type = field['type']
    raw_name = field.get('raw_name', '')
    
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
        
        # Show additional field info
        info_parts = []
        if field.get('required'):
            info_parts.append("*Required")
        if field.get('page'):
            info_parts.append(f"Page {field['page']}")
        if raw_name and raw_name != field_name and st.session_state.get('show_raw_names', False):
            info_parts.append(f"Raw: {raw_name[:30]}...")
        
        if info_parts:
            st.caption(" | ".join(info_parts))
        
        # Show confidence if available
        if field_name in st.session_state.mapping_suggestions:
            suggestion_info = st.session_state.mapping_suggestions[field_name]
            confidence = suggestion_info['confidence']
            if confidence > 0:
                confidence_color = "#2e8540" if confidence > 0.7 else "#fdb81e" if confidence > 0.4 else "#e21727"
                st.markdown(f'<span style="color: {confidence_color}; font-size: 0.85em;">Confidence: {confidence:.0%}</span>', unsafe_allow_html=True)
    
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
            # Mapping input with suggestion
            suggestion = None
            if field_name in st.session_state.mapping_suggestions:
                suggestion = st.session_state.mapping_suggestions[field_name]['mapping']
            
            new_mapping = st.text_input(
                "Map to",
                placeholder=suggestion or "e.g., customer.customer_name",
                key=f"map_input_{unique_key}",
                help=f"Suggested: {suggestion}" if suggestion else None
            )
            if new_mapping:
                st.session_state.mapped_fields[field_name] = f"{new_mapping}:{field_type}"
                categorize_mapping(field_name, new_mapping, field_type)
                st.rerun()
    
    with col3:
        if is_mapped:
            if st.button("❌", key=f"unmap_{unique_key}", help="Remove mapping"):
                del st.session_state.mapped_fields[field_name]
                uncategorize_mapping(field_name)
                st.rerun()
        else:
            if st.button("✓", key=f"map_{unique_key}", help="Quick map with suggestion"):
                if field_name in st.session_state.mapping_suggestions:
                    suggested = st.session_state.mapping_suggestions[field_name]['mapping']
                    st.session_state.mapped_fields[field_name] = f"{suggested}:{field_type}"
                    categorize_mapping(field_name, suggested, field_type)
                    st.rerun()
    
    with col4:
        if not is_questionnaire:
            if st.button("❓", key=f"quest_{unique_key}", help="Move to questionnaire"):
                st.session_state.questionnaire_fields[field_name] = {
                    'type': 'checkbox' if field_type == 'CheckBox' else 'text',
                    'required': field.get('required', False),
                    'label': beautify_field_name(field_name),
                    'options': 'Yes\nNo' if field_type in ['CheckBox', 'RadioButton'] else '',
                    'validation': '',
                    'style': {"col": "12"}
                }
                st.session_state.categorized_mappings['questionnaireData'][field_name] = f"{field_name}:{determine_questionnaire_type(field_type)}"
                st.rerun()
    
    with col5:
        if st.button("🗑️", key=f"remove_{unique_key}", help="Remove field"):
            st.session_state.removed_fields.append(field_name)
            st.rerun()

def categorize_mapping(field_name: str, mapping: str, field_type: str):
    """Categorize a mapping into appropriate data section"""
    # Remove from all categories first
    uncategorize_mapping(field_name)
    
    # Determine category based on mapping path
    if mapping.startswith('customer.'):
        st.session_state.categorized_mappings['customerData'][field_name] = f"{mapping}:{field_type}"
    elif mapping.startswith('beneficiary.'):
        st.session_state.categorized_mappings['beneficiaryData'][field_name] = f"{mapping}:{field_type}"
    elif mapping.startswith('attorney.') or mapping.startswith('attorneyLawfirmDetails.'):
        st.session_state.categorized_mappings['attorneyData'][field_name] = f"{mapping}:{field_type}"
    elif mapping.startswith('lca.'):
        st.session_state.categorized_mappings['lcaData'][field_name] = f"{mapping}:{field_type}"
    elif mapping.startswith('case.'):
        st.session_state.categorized_mappings['caseData'][field_name] = f"{mapping}:{field_type}"
    else:
        # Default to questionnaire if no clear category
        st.session_state.categorized_mappings['questionnaireData'][field_name] = f"{mapping}:{field_type}"

def uncategorize_mapping(field_name: str):
    """Remove a field from all categories"""
    for category in st.session_state.categorized_mappings.values():
        if field_name in category:
            del category[field_name]

def determine_questionnaire_type(field_type: str) -> str:
    """Map field types to questionnaire types"""
    type_map = {
        'CheckBox': 'ConditionBox',
        'RadioButton': 'ConditionBox',
        'TextBox': 'SingleBox',
        'TextArea': 'MultilineBox',
        'Date': 'DateBox',
        'Number': 'NumberBox',
        'Phone': 'PhoneBox',
        'Email': 'EmailBox',
        'Currency': 'CurrencyBox'
    }
    return type_map.get(field_type, 'SingleBox')

def beautify_field_name(field_name: str) -> str:
    """Convert field name to human-readable label"""
    # Handle specific USCIS patterns
    patterns = [
        # P1Line1a_FamilyName -> Family Name
        (r'(?:P|Part)(\d+)(?:Line|Item)(\d+[a-z]?)(?:_|\.)?(.+)', r'Part \1 Item \2 - \3'),
        # Part1_Item2_CompanyName -> Company Name  
        (r'Part(\d+)_Item(\d+[a-z]?)_(.+)', r'Part \1 Item \2 - \3'),
        # Pt1Line1a_FamilyName -> Family Name
        (r'Pt(\d+)Line(\d+[a-z]?)(?:_|\.)?(.+)', r'Part \1 Line \2 - \3'),
        # Item2_FirstName -> First Name
        (r'Item(\d+[a-z]?)_(.+)', r'Item \1 - \2'),
        # Remove form type prefix
        (r'^[A-Z]-?\d+[A-Z]?_', ''),
        # Remove other prefixes
        (r'^(Part|Section|Item|Field|Q)\d+[_\.\s]*', '')
    ]
    
    # Apply patterns
    result = field_name
    for pattern, replacement in patterns:
        match = re.match(pattern, result)
        if match:
            if '\3' in replacement:  # Has capture groups
                # Extract the field description part
                field_desc = match.group(3)
                # Convert CamelCase/snake_case to words
                field_desc = re.sub(r'([a-z])([A-Z])', r'\1 \2', field_desc)
                field_desc = field_desc.replace('_', ' ')
                # Capitalize properly
                words = field_desc.split()
                capitalized = []
                for word in words:
                    if word.upper() in ['SSN', 'DOB', 'EIN', 'FEIN', 'LCA', 'US', 'USA', 'I94']:
                        capitalized.append(word.upper())
                    else:
                        capitalized.append(word.capitalize())
                field_desc = ' '.join(capitalized)
                # Apply the replacement
                result = re.sub(pattern, replacement.replace(r'\3', field_desc), result)
            else:
                result = re.sub(pattern, replacement, result)
            break
    
    # If no pattern matched, do basic cleanup
    if result == field_name:
        # Replace underscores
        result = result.replace('_', ' ')
        # Capitalize properly
        words = result.split()
        capitalized = []
        for word in words:
            if word.upper() in ['SSN', 'DOB', 'EIN', 'FEIN', 'LCA', 'US', 'USA', 'I94']:
                capitalized.append(word.upper())
            else:
                capitalized.append(word.capitalize())
        result = ' '.join(capitalized).strip()
    
    return result

def auto_map_part_fields(part_fields: List[Dict]):
    """Auto-map all unmapped fields in a part"""
    for field in part_fields:
        field_name = field['name']
        if (field_name not in st.session_state.mapped_fields and 
            field_name not in st.session_state.questionnaire_fields and
            field_name not in st.session_state.removed_fields):
            
            # Check if we have a suggestion with high confidence
            if field_name in st.session_state.mapping_suggestions:
                suggestion_info = st.session_state.mapping_suggestions[field_name]
                if suggestion_info['confidence'] > 0.5:  # Only auto-map if confidence > 50%
                    mapping = suggestion_info['mapping']
                    field_type = field['type']
                    st.session_state.mapped_fields[field_name] = f"{mapping}:{field_type}"
                    categorize_mapping(field_name, mapping, field_type)

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
                'options': 'Yes\nNo' if field['type'] in ['CheckBox', 'RadioButton'] else '',
                'validation': '',
                'style': {"col": "12"}
            }
            st.session_state.categorized_mappings['questionnaireData'][field_name] = f"{field_name}:{determine_questionnaire_type(field['type'])}"

def remove_part_fields(part_fields: List[Dict]):
    """Remove all fields in a part"""
    for field in part_fields:
        if field['name'] not in st.session_state.removed_fields:
            st.session_state.removed_fields.append(field['name'])

def generate_typescript_g28_style() -> str:
    """Generate TypeScript configuration in G28 style format"""
    form_name = st.session_state.form_name or 'USCISForm'
    form_name_clean = re.sub(r'[^\w]', '', form_name)
    
    # Prepare categorized data
    customer_data = st.session_state.categorized_mappings.get('customerData', {})
    beneficiary_data = st.session_state.categorized_mappings.get('beneficiaryData', {})
    attorney_data = st.session_state.categorized_mappings.get('attorneyData', {})
    lca_data = st.session_state.categorized_mappings.get('lcaData', {})
    case_data = st.session_state.categorized_mappings.get('caseData', {})
    questionnaire_data = st.session_state.categorized_mappings.get('questionnaireData', {})
    
    # Add questionnaire fields that were added via UI
    for field_name, config in st.session_state.questionnaire_fields.items():
        if field_name not in questionnaire_data:
            questionnaire_data[field_name] = f"{field_name}:{determine_questionnaire_type(config.get('type', 'text'))}"
    
    # Prepare default data (checkboxes that should be checked by default)
    default_data = {}
    for field in st.session_state.pdf_fields:
        if field['type'] == 'CheckBox' and field.get('value'):
            default_data[field['name']] = ":CheckBox"
    
    # Generate TypeScript content
    ts_content = f"""export const {form_name_clean} = {{
    "formname": "{form_name_clean}",
    "customerData": {json.dumps(customer_data, indent=8) if customer_data else 'null'},
    "beneficiaryData": {json.dumps(beneficiary_data, indent=8) if beneficiary_data else 'null'},
    "attorneyData": {json.dumps(attorney_data, indent=8) if attorney_data else 'null'},
    "lcaData": {json.dumps(lca_data, indent=8) if lca_data else 'null'},
    "caseData": {json.dumps(case_data, indent=8) if case_data else 'null'},
    "questionnaireData": {json.dumps(questionnaire_data, indent=8)},
    "defaultData": {json.dumps(default_data, indent=8) if default_data else '{}'},
    "conditionalData": {json.dumps(st.session_state.conditional_fields, indent=8) if st.session_state.conditional_fields else '{}'},
    "pdfName": "{form_name_clean}",
    "metadata": {{
        "formType": "{st.session_state.form_type or 'Unknown'}",
        "totalFields": {len(st.session_state.pdf_fields)},
        "mappedFields": {len(st.session_state.mapped_fields)},
        "questionnaireFields": {len(st.session_state.questionnaire_fields)},
        "extractedFrom": "{st.session_state.form_type or 'Unknown USCIS Form'}",
        "timestamp": "{datetime.now().isoformat()}"
    }}
}}"""
    
    return ts_content

def generate_json_for_unmapped() -> str:
    """Generate JSON for unmapped fields with suggestions"""
    unmapped_fields = []
    
    for field in st.session_state.pdf_fields:
        field_name = field['name']
        if (field_name not in st.session_state.mapped_fields and 
            field_name not in st.session_state.questionnaire_fields and
            field_name not in st.session_state.removed_fields):
            
            suggestion_info = st.session_state.mapping_suggestions.get(field_name, {})
            
            # Extract part information
            part_id, _ = extract_part_from_field_name(field_name)
            
            unmapped_field = {
                "fieldName": field_name,
                "fieldType": field['type'],
                "required": field.get('required', False),
                "page": field.get('page', 0),
                "part": part_id,
                "rawFieldName": field.get('raw_name', field_name),
                "suggestedMapping": suggestion_info.get('mapping'),
                "confidence": suggestion_info.get('confidence', 0.0),
                "humanReadableLabel": beautify_field_name(field_name)
            }
            unmapped_fields.append(unmapped_field)
    
    # Sort by confidence (highest first), then by part, then by field name
    unmapped_fields.sort(key=lambda x: (-x['confidence'], x['part'], x['fieldName']))
    
    # Group by part for better organization
    grouped_fields = {}
    for field in unmapped_fields:
        part = field['part']
        if part not in grouped_fields:
            grouped_fields[part] = []
        grouped_fields[part].append(field)
    
    result = {
        "formName": st.session_state.form_name or "Unknown",
        "formType": st.session_state.form_type or "Unknown",
        "unmappedFieldsCount": len(unmapped_fields),
        "timestamp": datetime.now().isoformat(),
        "unmappedFieldsByPart": grouped_fields,
        "highConfidenceSuggestions": [f for f in unmapped_fields if f['confidence'] > 0.7][:10]  # Top 10 high confidence
    }
    
    return json.dumps(result, indent=2)

# Main Application
def main():
    st.title("🏛️ USCIS PDF Form Automation System")
    st.markdown("Extract and intelligently map fields from USCIS immigration forms to database objects")
    
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
            if st.session_state.form_type in USCIS_FORMS_DATABASE:
                st.caption(USCIS_FORMS_DATABASE[st.session_state.form_type]['title'])
        
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
        
        # Debug options
        with st.expander("🔧 Debug Options"):
            st.session_state.show_raw_names = st.checkbox("Show raw field names", value=False)
        
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
            
            # Confidence metrics
            if st.session_state.mapping_suggestions:
                avg_confidence = sum(s['confidence'] for s in st.session_state.mapping_suggestions.values()) / len(st.session_state.mapping_suggestions)
                st.metric("Avg. Confidence", f"{avg_confidence:.0%}")
        
        st.markdown("---")
        
        # Actions
        st.header("⚡ Quick Actions")
        
        if st.button("🤖 Auto-Map All", use_container_width=True, type="primary"):
            count = 0
            for field in st.session_state.pdf_fields:
                field_name = field['name']
                if (field_name not in st.session_state.mapped_fields and 
                    field_name not in st.session_state.questionnaire_fields and
                    field_name not in st.session_state.removed_fields):
                    
                    # Checkboxes and radio buttons go to questionnaire
                    if field['type'] in ['CheckBox', 'RadioButton']:
                        st.session_state.questionnaire_fields[field_name] = {
                            'type': 'checkbox' if field['type'] == 'CheckBox' else 'radio',
                            'required': field.get('required', False),
                            'label': beautify_field_name(field_name),
                            'options': 'Yes\nNo' if field['type'] == 'CheckBox' else '',
                            'validation': '',
                            'style': {"col": "12"}
                        }
                        st.session_state.categorized_mappings['questionnaireData'][field_name] = f"{field_name}:{determine_questionnaire_type(field['type'])}"
                        count += 1
                    else:
                        # Try to map with confidence threshold
                        if field_name in st.session_state.mapping_suggestions:
                            suggestion_info = st.session_state.mapping_suggestions[field_name]
                            if suggestion_info['confidence'] > 0.3:  # Lower threshold for auto-map all
                                mapping = suggestion_info['mapping']
                                field_type = field['type']
                                st.session_state.mapped_fields[field_name] = f"{mapping}:{field_type}"
                                categorize_mapping(field_name, mapping, field_type)
                                count += 1
            
            st.success(f"Auto-mapped {count} fields!")
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
        
        # Form type selector
        col1, col2 = st.columns([2, 1])
        with col1:
            form_options = ["Auto-detect"] + list(USCIS_FORMS_DATABASE.keys())
            selected_form = st.selectbox(
                "Select form type (optional)",
                form_options,
                help="Pre-select a form type for better field detection"
            )
            if selected_form != "Auto-detect":
                st.session_state.form_type = selected_form
        
        uploaded_file = st.file_uploader(
            "Choose a USCIS PDF form",
            type="pdf",
            help="Supported forms: I-129, I-539, I-140, I-485, I-765, I-131, G-28, LCA, and more"
        )
        
        if uploaded_file:
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.info(f"📄 {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")
            
            with col2:
                if st.button("🔍 Extract", type="primary", use_container_width=True):
                    with st.spinner("Extracting fields with intelligent detection..."):
                        try:
                            fields, form_parts = extract_uscis_pdf(uploaded_file)
                            st.session_state.pdf_fields = fields
                            st.session_state.form_parts = form_parts
                            
                            if fields:
                                st.success(f"✅ Extracted {len(fields)} fields!")
                                if st.session_state.form_type:
                                    st.info(f"📋 Form Type: {st.session_state.form_type}")
                                
                                # Show confidence summary
                                if st.session_state.mapping_suggestions:
                                    high_conf = sum(1 for s in st.session_state.mapping_suggestions.values() if s['confidence'] > 0.7)
                                    st.caption(f"Found {high_conf} high-confidence mapping suggestions")
                                
                                st.rerun()
                            else:
                                st.warning("No fields found. Try selecting the form type manually.")
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
                            st.exception(e)
        
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
            # Field extraction summary
            with st.expander("📋 Field Extraction Summary", expanded=False):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Parts", len(st.session_state.form_parts))
                    st.caption("Including attorney section")
                with col2:
                    st.metric("Fields per Part", 
                             f"~{len(st.session_state.pdf_fields) // max(len(st.session_state.form_parts)-2, 1)}")
                    st.caption("Average distribution")
                with col3:
                    st.metric("Field Name Pattern", 
                             "USCIS Standard" if any('Part' in f['name'] or 'Line' in f['name'] for f in st.session_state.pdf_fields) else "Unknown")
                    st.caption("Detected naming convention")
                
                # Show sample field names
                if st.session_state.pdf_fields:
                    st.subheader("Sample Extracted Field Names:")
                    sample_fields = st.session_state.pdf_fields[:5]
                    for field in sample_fields:
                        st.code(f"{field['name']} → {beautify_field_name(field['name'])}")
                    if len(st.session_state.pdf_fields) > 5:
                        st.caption(f"... and {len(st.session_state.pdf_fields) - 5} more fields")
            
            # Mapping statistics
            col1, col2, col3 = st.columns(3)
            with col1:
                high_conf_fields = [f for f in st.session_state.pdf_fields 
                                   if f['name'] in st.session_state.mapping_suggestions 
                                   and st.session_state.mapping_suggestions[f['name']]['confidence'] > 0.7]
                st.info(f"🎯 {len(high_conf_fields)} high-confidence suggestions")
            
            with col2:
                db_mapped = sum(1 for cat in ['customerData', 'beneficiaryData', 'attorneyData', 'lcaData', 'caseData'] 
                               for _ in st.session_state.categorized_mappings.get(cat, {}))
                st.info(f"🔗 {db_mapped} database mappings")
            
            with col3:
                unmapped_required = sum(1 for f in st.session_state.pdf_fields 
                                      if f.get('required') and f['name'] not in st.session_state.mapped_fields 
                                      and f['name'] not in st.session_state.questionnaire_fields)
                if unmapped_required > 0:
                    st.warning(f"⚠️ {unmapped_required} required fields unmapped")
                else:
                    st.success("✅ All required fields mapped")
            
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
            
            if q_type in ['radio', 'select']:
                q_options = st.text_area("Options (one per line)", placeholder="Yes\nNo")
            else:
                q_options = ""
            
            if st.button("Add Field", type="primary"):
                if q_label:
                    field_key = re.sub(r'[^\w]', '_', q_label)
                    st.session_state.questionnaire_fields[field_key] = {
                        'type': q_type,
                        'required': q_required,
                        'label': q_label,
                        'options': q_options,
                        'validation': '',
                        'style': {"col": "12"}
                    }
                    st.session_state.categorized_mappings['questionnaireData'][field_key] = f"{field_key}:{determine_questionnaire_type(q_type)}"
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
                            if field_key in st.session_state.categorized_mappings['questionnaireData']:
                                del st.session_state.categorized_mappings['questionnaireData'][field_key]
                            st.rerun()
        else:
            st.info("No questionnaire fields added yet. Fields marked as checkboxes or radio buttons will appear here.")
    
    # Tab 4: Export
    with tab4:
        st.header("Export Configuration")
        
        if not st.session_state.pdf_fields:
            st.warning("⚠️ No data to export")
        else:
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📄 TypeScript Export (G28 Style)")
                st.caption("Mapped fields organized by database objects")
                
                if st.button("Generate TypeScript", type="primary", use_container_width=True):
                    ts_content = generate_typescript_g28_style()
                    st.download_button(
                        "📥 Download TypeScript",
                        data=ts_content,
                        file_name=f"{st.session_state.form_name or 'USCIS_Form'}.ts",
                        mime="text/plain"
                    )
                    with st.expander("Preview TypeScript"):
                        st.code(ts_content, language="typescript")
            
            with col2:
                st.subheader("📋 JSON Export (Unmapped Fields)")
                st.caption("Fields that need manual mapping with suggestions")
                
                if st.button("Generate JSON", type="primary", use_container_width=True):
                    json_content = generate_json_for_unmapped()
                    st.download_button(
                        "📥 Download JSON",
                        data=json_content,
                        file_name=f"{st.session_state.form_name or 'USCIS_Form'}_unmapped.json",
                        mime="application/json"
                    )
                    with st.expander("Preview JSON"):
                        st.code(json_content, language="json")
            
            # Summary statistics
            st.markdown("---")
            st.subheader("📊 Mapping Summary")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                customer_count = len(st.session_state.categorized_mappings.get('customerData', {}))
                st.metric("Customer Fields", customer_count)
            
            with col2:
                beneficiary_count = len(st.session_state.categorized_mappings.get('beneficiaryData', {}))
                st.metric("Beneficiary Fields", beneficiary_count)
            
            with col3:
                attorney_count = len(st.session_state.categorized_mappings.get('attorneyData', {}))
                st.metric("Attorney Fields", attorney_count)
            
            with col4:
                lca_count = len(st.session_state.categorized_mappings.get('lcaData', {}))
                st.metric("LCA Fields", lca_count)
            
            # Show categorized mappings
            with st.expander("View Categorized Mappings"):
                for category, mappings in st.session_state.categorized_mappings.items():
                    if mappings:
                        st.subheader(category)
                        for field, mapping in mappings.items():
                            st.text(f"{field} → {mapping}")

# Run the application
if __name__ == "__main__":
    main()
,
        # Extract anything that looks like Part/Item pattern
        r'.*((?:Part|Pt|P)\d+.*(?:Item|Line|Field|_)\d+.*?)[\[\.]',
    ]
    
    cleaned_name = raw_field_name
    
    # Try each pattern to extract the meaningful part
    for pattern in patterns:
        match = re.search(pattern, raw_field_name, re.IGNORECASE)
        if match:
            cleaned_name = match.group(1)
            break
    
    # Additional cleaning
    # Remove extra dots and brackets
    cleaned_name = re.sub(r'[\[\]]+', '', cleaned_name)
    cleaned_name = re.sub(r'\.+', '_', cleaned_name)
    
    # Standardize part/item notation
    cleaned_name = re.sub(r'Part(\d+)', r'P\1', cleaned_name)
    cleaned_name = re.sub(r'Pt(\d+)', r'P\1', cleaned_name)
    cleaned_name = re.sub(r'Item(\d+)', r'Item\1', cleaned_name)
    cleaned_name = re.sub(r'Line(\d+)', r'Line\1', cleaned_name)
    
    # Remove trailing underscores
    cleaned_name = cleaned_name.strip('_')
    
    return cleaned_name

# Extract part information from field name
def extract_part_from_field_name(field_name: str) -> Tuple[str, int]:
    """Extract part number and create part identifier from field name"""
    # Try to find part number in various formats
    patterns = [
        r'(?:Part|Pt|P)[\s_\-]*(\d+)',
        r'Section[\s_\-]*([A-Z])',
        r'(?:Page|Pg)[\s_\-]*(\d+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, field_name, re.IGNORECASE)
        if match:
            part_id = match.group(1)
            if pattern.startswith('(?:Part'):
                return f"Part {part_id}", int(part_id)
            elif pattern.startswith('Section'):
                # Convert section letter to number (A=1, B=2, etc.)
                return f"Section {part_id}", ord(part_id.upper()) - ord('A') + 1
            elif pattern.startswith('(?:Page'):
                return f"Page {part_id}", int(part_id)
    
    return "Unassigned", 999

# Extract fields from PDF
def extract_uscis_pdf(pdf_file) -> Tuple[List[Dict[str, Any]], OrderedDict]:
    """Extract fields from USCIS PDF forms with enhanced part organization"""
    fields = []
    form_parts = OrderedDict()
    extracted_text = ""
    processing_log = []
    raw_field_names = []  # Store raw field names for debugging
    
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
            for page_num in range(min(3, len(doc))):
                page = doc[page_num]
                text = page.get_text()
                extracted_text += f"\n--- Page {page_num + 1} ---\n{text}"
                
                # Detect form type
                if not form_type:
                    for form_key, form_info in USCIS_FORMS_DATABASE.items():
                        for pattern in form_info['patterns']:
                            if re.search(pattern, text, re.IGNORECASE):
                                form_type = form_key
                                form_number = form_key
                                processing_log.append(f"Detected form type: {form_key} - {form_info['title']}")
                                break
                        if form_type:
                            break
            
            # Extract form fields
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Extract form widgets
                for widget in page.widgets():
                    raw_field_name = widget.field_name
                    if raw_field_name:
                        # Store raw name for debugging
                        raw_field_names.append(raw_field_name)
                        
                        # Clean the field name
                        cleaned_name = clean_uscis_field_name(raw_field_name)
                        
                        # Determine field type
                        field_type = determine_field_type_enhanced(cleaned_name)
                        
                        # Get mapping suggestion
                        suggested_mapping, confidence = suggest_mapping_enhanced(cleaned_name)
                        
                        field_data = {
                            'name': cleaned_name,
                            'raw_name': raw_field_name,
                            'type': field_type,
                            'value': widget.field_value or '',
                            'required': widget.field_flags & 2 != 0,
                            'page': page_num + 1,
                            'rect': list(widget.rect),
                            'source': 'PyMuPDF',
                            'suggested_mapping': suggested_mapping,
                            'confidence': confidence
                        }
                        fields.append(field_data)
            
            doc.close()
            processing_log.append(f"Extracted {len(fields)} fields using PyMuPDF")
            
        except Exception as e:
            processing_log.append(f"PyMuPDF error: {str(e)}")
    
    # Fallback to PyPDF2/pypdf
    if len(fields) < 10 and PDF_AVAILABLE:
        try:
            processing_log.append(f"Using {PDF_LIBRARY} for extraction...")
            pdf_file.seek(0)
            reader = PdfReader(pdf_file)
            
            # Extract text for form detection
            for page_num in range(min(3, len(reader.pages))):
                page = reader.pages[page_num]
                text = page.extract_text()
                extracted_text += f"\n--- Page {page_num + 1} ---\n{text}"
                
                # Detect form type
                if not form_type:
                    for form_key, form_info in USCIS_FORMS_DATABASE.items():
                        for pattern in form_info['patterns']:
                            if re.search(pattern, text, re.IGNORECASE):
                                form_type = form_key
                                form_number = form_key
                                processing_log.append(f"Detected form type: {form_key}")
                                break
                        if form_type:
                            break
            
            # Extract form fields
            if hasattr(reader, 'get_form_text_fields'):
                form_fields = reader.get_form_text_fields() or {}
                for raw_field_name, field_value in form_fields.items():
                    if raw_field_name:
                        # Store raw name
                        raw_field_names.append(raw_field_name)
                        
                        # Clean the field name
                        cleaned_name = clean_uscis_field_name(raw_field_name)
                        
                        field_type = determine_field_type_enhanced(cleaned_name)
                        suggested_mapping, confidence = suggest_mapping_enhanced(cleaned_name)
                        
                        field_data = {
                            'name': cleaned_name,
                            'raw_name': raw_field_name,
                            'type': field_type,
                            'value': field_value or '',
                            'required': False,
                            'page': 0,
                            'source': PDF_LIBRARY,
                            'suggested_mapping': suggested_mapping,
                            'confidence': confidence
                        }
                        fields.append(field_data)
            
            # Also try to get fields through AcroForm
            if hasattr(reader, 'get_fields'):
                acro_fields = reader.get_fields()
                if acro_fields:
                    for field_name, field_obj in acro_fields.items():
                        if field_name and field_name not in raw_field_names:
                            raw_field_names.append(field_name)
                            cleaned_name = clean_uscis_field_name(field_name)
                            
                            # Extract field properties
                            field_type = 'TextBox'
                            field_value = ''
                            
                            if isinstance(field_obj, dict):
                                if '/FT' in field_obj:
                                    ft = field_obj['/FT']
                                    if ft == '/Btn':
                                        field_type = 'CheckBox'
                                    elif ft == '/Tx':
                                        field_type = 'TextBox'
                                    elif ft == '/Ch':
                                        field_type = 'DropDown'
                                
                                if '/V' in field_obj:
                                    field_value = str(field_obj['/V'])
                            
                            field_type = determine_field_type_enhanced(cleaned_name)
                            suggested_mapping, confidence = suggest_mapping_enhanced(cleaned_name)
                            
                            field_data = {
                                'name': cleaned_name,
                                'raw_name': field_name,
                                'type': field_type,
                                'value': field_value,
                                'required': False,
                                'page': 0,
                                'source': 'AcroForm',
                                'suggested_mapping': suggested_mapping,
                                'confidence': confidence
                            }
                            fields.append(field_data)
            
            processing_log.append(f"Extracted {len(fields)} fields using {PDF_LIBRARY}")
            
        except Exception as e:
            processing_log.append(f"{PDF_LIBRARY} error: {str(e)}")
    
    # Add raw field names to processing log for debugging
    if raw_field_names:
        processing_log.append("\nRaw field names found:")
        for i, raw_name in enumerate(raw_field_names[:10]):  # Show first 10
            processing_log.append(f"  {i+1}. {raw_name}")
        if len(raw_field_names) > 10:
            processing_log.append(f"  ... and {len(raw_field_names) - 10} more fields")
    
    # Store extracted info
    st.session_state.extracted_text = extracted_text
    st.session_state.processing_log = processing_log
    st.session_state.form_type = form_type
    st.session_state.uscis_form_number = form_number
    
    if form_type:
        st.session_state.form_name = form_type
    
    # Organize fields by parts
    form_parts = organize_fields_by_parts_enhanced(fields, form_type)
    
    return fields, form_parts

def organize_fields_by_parts(fields: List[Dict], form_type: Optional[str]) -> OrderedDict:
    """Organize fields by form parts"""
    form_parts = OrderedDict()
    
    # Always add attorney section first
    form_parts['Part 0 - Attorney/Preparer Information'] = []
    
    # Add known parts for the form type
    if form_type and form_type in USCIS_FORMS_DATABASE:
        for part_key, part_desc in USCIS_FORMS_DATABASE[form_type]['parts'].items():
            form_parts[f'{part_key} - {part_desc}'] = []
    
    # Add unassigned section
    form_parts['Unassigned Fields'] = []
    
    # Organize fields into parts
    for field in fields:
        field_name_lower = field['name'].lower()
        assigned = False
        
        # Check if it's an attorney field
        attorney_keywords = ['attorney', 'preparer', 'representative', 'g-28', 'bar']
        if any(keyword in field_name_lower for keyword in attorney_keywords):
            form_parts['Part 0 - Attorney/Preparer Information'].append(field)
            assigned = True
        else:
            # Try to extract part number from field name
            part_match = re.search(r'(?:part|pt|p)[\s_\-]*(\d+)', field_name_lower)
            if part_match:
                part_num = part_match.group(1)
                if form_type and form_type in USCIS_FORMS_DATABASE:
                    parts = USCIS_FORMS_DATABASE[form_type]['parts']
                    part_key = f'Part {part_num}'
                    if part_key in parts:
                        part_full = f'{part_key} - {parts[part_key]}'
                        if part_full in form_parts:
                            form_parts[part_full].append(field)
                            assigned = True
        
        if not assigned:
            form_parts['Unassigned Fields'].append(field)
    
    # Store suggestions
    for field in fields:
        if field.get('suggested_mapping'):
            st.session_state.mapping_suggestions[field['name']] = {
                'mapping': field['suggested_mapping'],
                'confidence': field.get('confidence', 0.0)
            }
    
    return form_parts

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
        
        # Show fields
        for field_idx, field in enumerate(part_fields):
            if field['name'] in st.session_state.removed_fields:
                continue
            render_field_row(field, f"{part_index}_{field_idx}")
        
        # Add some spacing
        st.markdown("<br>", unsafe_allow_html=True)

def render_field_row(field: Dict, unique_key: str):
    """Render a field row with mapping options"""
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
        
        # Show confidence if available
        if field_name in st.session_state.mapping_suggestions:
            suggestion_info = st.session_state.mapping_suggestions[field_name]
            confidence = suggestion_info['confidence']
            if confidence > 0:
                confidence_color = "#2e8540" if confidence > 0.7 else "#fdb81e" if confidence > 0.4 else "#e21727"
                st.markdown(f'<span style="color: {confidence_color}; font-size: 0.85em;">Confidence: {confidence:.0%}</span>', unsafe_allow_html=True)
    
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
            # Mapping input with suggestion
            suggestion = None
            if field_name in st.session_state.mapping_suggestions:
                suggestion = st.session_state.mapping_suggestions[field_name]['mapping']
            
            new_mapping = st.text_input(
                "Map to",
                placeholder=suggestion or "e.g., customer.customer_name",
                key=f"map_input_{unique_key}",
                help=f"Suggested: {suggestion}" if suggestion else None
            )
            if new_mapping:
                st.session_state.mapped_fields[field_name] = f"{new_mapping}:{field_type}"
                categorize_mapping(field_name, new_mapping, field_type)
                st.rerun()
    
    with col3:
        if is_mapped:
            if st.button("❌", key=f"unmap_{unique_key}", help="Remove mapping"):
                del st.session_state.mapped_fields[field_name]
                uncategorize_mapping(field_name)
                st.rerun()
        else:
            if st.button("✓", key=f"map_{unique_key}", help="Quick map with suggestion"):
                if field_name in st.session_state.mapping_suggestions:
                    suggested = st.session_state.mapping_suggestions[field_name]['mapping']
                    st.session_state.mapped_fields[field_name] = f"{suggested}:{field_type}"
                    categorize_mapping(field_name, suggested, field_type)
                    st.rerun()
    
    with col4:
        if not is_questionnaire:
            if st.button("❓", key=f"quest_{unique_key}", help="Move to questionnaire"):
                st.session_state.questionnaire_fields[field_name] = {
                    'type': 'checkbox' if field_type == 'CheckBox' else 'text',
                    'required': field.get('required', False),
                    'label': beautify_field_name(field_name),
                    'options': 'Yes\nNo' if field_type in ['CheckBox', 'RadioButton'] else '',
                    'validation': '',
                    'style': {"col": "12"}
                }
                st.session_state.categorized_mappings['questionnaireData'][field_name] = f"{field_name}:{determine_questionnaire_type(field_type)}"
                st.rerun()
    
    with col5:
        if st.button("🗑️", key=f"remove_{unique_key}", help="Remove field"):
            st.session_state.removed_fields.append(field_name)
            st.rerun()

def categorize_mapping(field_name: str, mapping: str, field_type: str):
    """Categorize a mapping into appropriate data section"""
    # Remove from all categories first
    uncategorize_mapping(field_name)
    
    # Determine category based on mapping path
    if mapping.startswith('customer.'):
        st.session_state.categorized_mappings['customerData'][field_name] = f"{mapping}:{field_type}"
    elif mapping.startswith('beneficiary.'):
        st.session_state.categorized_mappings['beneficiaryData'][field_name] = f"{mapping}:{field_type}"
    elif mapping.startswith('attorney.') or mapping.startswith('attorneyLawfirmDetails.'):
        st.session_state.categorized_mappings['attorneyData'][field_name] = f"{mapping}:{field_type}"
    elif mapping.startswith('lca.'):
        st.session_state.categorized_mappings['lcaData'][field_name] = f"{mapping}:{field_type}"
    elif mapping.startswith('case.'):
        st.session_state.categorized_mappings['caseData'][field_name] = f"{mapping}:{field_type}"
    else:
        # Default to questionnaire if no clear category
        st.session_state.categorized_mappings['questionnaireData'][field_name] = f"{mapping}:{field_type}"

def uncategorize_mapping(field_name: str):
    """Remove a field from all categories"""
    for category in st.session_state.categorized_mappings.values():
        if field_name in category:
            del category[field_name]

def determine_questionnaire_type(field_type: str) -> str:
    """Map field types to questionnaire types"""
    type_map = {
        'CheckBox': 'ConditionBox',
        'RadioButton': 'ConditionBox',
        'TextBox': 'SingleBox',
        'TextArea': 'MultilineBox',
        'Date': 'DateBox',
        'Number': 'NumberBox',
        'Phone': 'PhoneBox',
        'Email': 'EmailBox',
        'Currency': 'CurrencyBox'
    }
    return type_map.get(field_type, 'SingleBox')

def beautify_field_name(field_name: str) -> str:
    """Convert field name to human-readable label"""
    # Remove form type prefix if present
    name = re.sub(r'^[A-Z]-?\d+[A-Z]?_', '', field_name)
    # Remove prefixes
    name = re.sub(r'^(Part|Section|Item|Field|Q)\d+[_\.\s]*', '', name)
    # Replace underscores
    name = name.replace('_', ' ')
    # Capitalize properly
    words = name.split()
    capitalized = []
    for word in words:
        if word.upper() in ['SSN', 'DOB', 'EIN', 'FEIN', 'LCA', 'US', 'USA', 'I94']:
            capitalized.append(word.upper())
        else:
            capitalized.append(word.capitalize())
    return ' '.join(capitalized).strip()

def auto_map_part_fields(part_fields: List[Dict]):
    """Auto-map all unmapped fields in a part"""
    for field in part_fields:
        field_name = field['name']
        if (field_name not in st.session_state.mapped_fields and 
            field_name not in st.session_state.questionnaire_fields and
            field_name not in st.session_state.removed_fields):
            
            # Check if we have a suggestion with high confidence
            if field_name in st.session_state.mapping_suggestions:
                suggestion_info = st.session_state.mapping_suggestions[field_name]
                if suggestion_info['confidence'] > 0.5:  # Only auto-map if confidence > 50%
                    mapping = suggestion_info['mapping']
                    field_type = field['type']
                    st.session_state.mapped_fields[field_name] = f"{mapping}:{field_type}"
                    categorize_mapping(field_name, mapping, field_type)

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
                'options': 'Yes\nNo' if field['type'] in ['CheckBox', 'RadioButton'] else '',
                'validation': '',
                'style': {"col": "12"}
            }
            st.session_state.categorized_mappings['questionnaireData'][field_name] = f"{field_name}:{determine_questionnaire_type(field['type'])}"

def remove_part_fields(part_fields: List[Dict]):
    """Remove all fields in a part"""
    for field in part_fields:
        if field['name'] not in st.session_state.removed_fields:
            st.session_state.removed_fields.append(field['name'])

def generate_typescript_g28_style() -> str:
    """Generate TypeScript configuration in G28 style format"""
    form_name = st.session_state.form_name or 'USCISForm'
    form_name_clean = re.sub(r'[^\w]', '', form_name)
    
    # Prepare categorized data
    customer_data = st.session_state.categorized_mappings.get('customerData', {})
    beneficiary_data = st.session_state.categorized_mappings.get('beneficiaryData', {})
    attorney_data = st.session_state.categorized_mappings.get('attorneyData', {})
    lca_data = st.session_state.categorized_mappings.get('lcaData', {})
    case_data = st.session_state.categorized_mappings.get('caseData', {})
    questionnaire_data = st.session_state.categorized_mappings.get('questionnaireData', {})
    
    # Add questionnaire fields that were added via UI
    for field_name, config in st.session_state.questionnaire_fields.items():
        if field_name not in questionnaire_data:
            questionnaire_data[field_name] = f"{field_name}:{determine_questionnaire_type(config.get('type', 'text'))}"
    
    # Prepare default data (checkboxes that should be checked by default)
    default_data = {}
    for field in st.session_state.pdf_fields:
        if field['type'] == 'CheckBox' and field.get('value'):
            default_data[field['name']] = ":CheckBox"
    
    # Generate TypeScript content
    ts_content = f"""export const {form_name_clean} = {{
    "formname": "{form_name_clean}",
    "customerData": {json.dumps(customer_data, indent=8) if customer_data else 'null'},
    "beneficiaryData": {json.dumps(beneficiary_data, indent=8) if beneficiary_data else 'null'},
    "attorneyData": {json.dumps(attorney_data, indent=8) if attorney_data else 'null'},
    "lcaData": {json.dumps(lca_data, indent=8) if lca_data else 'null'},
    "caseData": {json.dumps(case_data, indent=8) if case_data else 'null'},
    "questionnaireData": {json.dumps(questionnaire_data, indent=8)},
    "defaultData": {json.dumps(default_data, indent=8) if default_data else '{}'},
    "conditionalData": {json.dumps(st.session_state.conditional_fields, indent=8) if st.session_state.conditional_fields else '{}'},
    "pdfName": "{form_name_clean}",
    "metadata": {{
        "formType": "{st.session_state.form_type or 'Unknown'}",
        "totalFields": {len(st.session_state.pdf_fields)},
        "mappedFields": {len(st.session_state.mapped_fields)},
        "questionnaireFields": {len(st.session_state.questionnaire_fields)},
        "extractedFrom": "{st.session_state.form_type or 'Unknown USCIS Form'}",
        "timestamp": "{datetime.now().isoformat()}"
    }}
}}"""
    
    return ts_content

def generate_json_for_unmapped() -> str:
    """Generate JSON for unmapped fields with suggestions"""
    unmapped_fields = []
    
    for field in st.session_state.pdf_fields:
        field_name = field['name']
        if (field_name not in st.session_state.mapped_fields and 
            field_name not in st.session_state.questionnaire_fields and
            field_name not in st.session_state.removed_fields):
            
            suggestion_info = st.session_state.mapping_suggestions.get(field_name, {})
            
            unmapped_field = {
                "fieldName": field_name,
                "fieldType": field['type'],
                "required": field.get('required', False),
                "page": field.get('page', 0),
                "part": field.get('part', 'Unassigned'),
                "suggestedMapping": suggestion_info.get('mapping'),
                "confidence": suggestion_info.get('confidence', 0.0),
                "humanReadableLabel": beautify_field_name(field_name)
            }
            unmapped_fields.append(unmapped_field)
    
    # Sort by confidence (highest first)
    unmapped_fields.sort(key=lambda x: x['confidence'], reverse=True)
    
    result = {
        "formName": st.session_state.form_name or "Unknown",
        "formType": st.session_state.form_type or "Unknown",
        "unmappedFieldsCount": len(unmapped_fields),
        "timestamp": datetime.now().isoformat(),
        "unmappedFields": unmapped_fields
    }
    
    return json.dumps(result, indent=2)

# Main Application
def main():
    st.title("🏛️ USCIS PDF Form Automation System")
    st.markdown("Extract and intelligently map fields from USCIS immigration forms to database objects")
    
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
            if st.session_state.form_type in USCIS_FORMS_DATABASE:
                st.caption(USCIS_FORMS_DATABASE[st.session_state.form_type]['title'])
        
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
            
            # Confidence metrics
            if st.session_state.mapping_suggestions:
                avg_confidence = sum(s['confidence'] for s in st.session_state.mapping_suggestions.values()) / len(st.session_state.mapping_suggestions)
                st.metric("Avg. Confidence", f"{avg_confidence:.0%}")
        
        st.markdown("---")
        
        # Actions
        st.header("⚡ Quick Actions")
        
        if st.button("🤖 Auto-Map All", use_container_width=True, type="primary"):
            count = 0
            for field in st.session_state.pdf_fields:
                field_name = field['name']
                if (field_name not in st.session_state.mapped_fields and 
                    field_name not in st.session_state.questionnaire_fields and
                    field_name not in st.session_state.removed_fields):
                    
                    # Checkboxes and radio buttons go to questionnaire
                    if field['type'] in ['CheckBox', 'RadioButton']:
                        st.session_state.questionnaire_fields[field_name] = {
                            'type': 'checkbox' if field['type'] == 'CheckBox' else 'radio',
                            'required': field.get('required', False),
                            'label': beautify_field_name(field_name),
                            'options': 'Yes\nNo' if field['type'] == 'CheckBox' else '',
                            'validation': '',
                            'style': {"col": "12"}
                        }
                        st.session_state.categorized_mappings['questionnaireData'][field_name] = f"{field_name}:{determine_questionnaire_type(field['type'])}"
                        count += 1
                    else:
                        # Try to map with confidence threshold
                        if field_name in st.session_state.mapping_suggestions:
                            suggestion_info = st.session_state.mapping_suggestions[field_name]
                            if suggestion_info['confidence'] > 0.3:  # Lower threshold for auto-map all
                                mapping = suggestion_info['mapping']
                                field_type = field['type']
                                st.session_state.mapped_fields[field_name] = f"{mapping}:{field_type}"
                                categorize_mapping(field_name, mapping, field_type)
                                count += 1
            
            st.success(f"Auto-mapped {count} fields!")
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
        
        # Form type selector
        col1, col2 = st.columns([2, 1])
        with col1:
            form_options = ["Auto-detect"] + list(USCIS_FORMS_DATABASE.keys())
            selected_form = st.selectbox(
                "Select form type (optional)",
                form_options,
                help="Pre-select a form type for better field detection"
            )
            if selected_form != "Auto-detect":
                st.session_state.form_type = selected_form
        
        uploaded_file = st.file_uploader(
            "Choose a USCIS PDF form",
            type="pdf",
            help="Supported forms: I-129, I-539, I-140, I-485, I-765, I-131, G-28, LCA, and more"
        )
        
        if uploaded_file:
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.info(f"📄 {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")
            
            with col2:
                if st.button("🔍 Extract", type="primary", use_container_width=True):
                    with st.spinner("Extracting fields with intelligent detection..."):
                        try:
                            fields, form_parts = extract_uscis_pdf(uploaded_file)
                            st.session_state.pdf_fields = fields
                            st.session_state.form_parts = form_parts
                            
                            if fields:
                                st.success(f"✅ Extracted {len(fields)} fields!")
                                if st.session_state.form_type:
                                    st.info(f"📋 Form Type: {st.session_state.form_type}")
                                
                                # Show confidence summary
                                if st.session_state.mapping_suggestions:
                                    high_conf = sum(1 for s in st.session_state.mapping_suggestions.values() if s['confidence'] > 0.7)
                                    st.caption(f"Found {high_conf} high-confidence mapping suggestions")
                                
                                st.rerun()
                            else:
                                st.warning("No fields found. Try selecting the form type manually.")
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
                            st.exception(e)
        
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
            # Mapping statistics
            col1, col2, col3 = st.columns(3)
            with col1:
                high_conf_fields = [f for f in st.session_state.pdf_fields 
                                   if f['name'] in st.session_state.mapping_suggestions 
                                   and st.session_state.mapping_suggestions[f['name']]['confidence'] > 0.7]
                st.info(f"🎯 {len(high_conf_fields)} high-confidence suggestions")
            
            with col2:
                db_mapped = sum(1 for cat in ['customerData', 'beneficiaryData', 'attorneyData', 'lcaData', 'caseData'] 
                               for _ in st.session_state.categorized_mappings.get(cat, {}))
                st.info(f"🔗 {db_mapped} database mappings")
            
            with col3:
                unmapped_required = sum(1 for f in st.session_state.pdf_fields 
                                      if f.get('required') and f['name'] not in st.session_state.mapped_fields 
                                      and f['name'] not in st.session_state.questionnaire_fields)
                if unmapped_required > 0:
                    st.warning(f"⚠️ {unmapped_required} required fields unmapped")
                else:
                    st.success("✅ All required fields mapped")
            
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
            
            if q_type in ['radio', 'select']:
                q_options = st.text_area("Options (one per line)", placeholder="Yes\nNo")
            else:
                q_options = ""
            
            if st.button("Add Field", type="primary"):
                if q_label:
                    field_key = re.sub(r'[^\w]', '_', q_label)
                    st.session_state.questionnaire_fields[field_key] = {
                        'type': q_type,
                        'required': q_required,
                        'label': q_label,
                        'options': q_options,
                        'validation': '',
                        'style': {"col": "12"}
                    }
                    st.session_state.categorized_mappings['questionnaireData'][field_key] = f"{field_key}:{determine_questionnaire_type(q_type)}"
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
                            if field_key in st.session_state.categorized_mappings['questionnaireData']:
                                del st.session_state.categorized_mappings['questionnaireData'][field_key]
                            st.rerun()
        else:
            st.info("No questionnaire fields added yet. Fields marked as checkboxes or radio buttons will appear here.")
    
    # Tab 4: Export
    with tab4:
        st.header("Export Configuration")
        
        if not st.session_state.pdf_fields:
            st.warning("⚠️ No data to export")
        else:
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📄 TypeScript Export (G28 Style)")
                st.caption("Mapped fields organized by database objects")
                
                if st.button("Generate TypeScript", type="primary", use_container_width=True):
                    ts_content = generate_typescript_g28_style()
                    st.download_button(
                        "📥 Download TypeScript",
                        data=ts_content,
                        file_name=f"{st.session_state.form_name or 'USCIS_Form'}.ts",
                        mime="text/plain"
                    )
                    with st.expander("Preview TypeScript"):
                        st.code(ts_content, language="typescript")
            
            with col2:
                st.subheader("📋 JSON Export (Unmapped Fields)")
                st.caption("Fields that need manual mapping with suggestions")
                
                if st.button("Generate JSON", type="primary", use_container_width=True):
                    json_content = generate_json_for_unmapped()
                    st.download_button(
                        "📥 Download JSON",
                        data=json_content,
                        file_name=f"{st.session_state.form_name or 'USCIS_Form'}_unmapped.json",
                        mime="application/json"
                    )
                    with st.expander("Preview JSON"):
                        st.code(json_content, language="json")
            
            # Summary statistics
            st.markdown("---")
            st.subheader("📊 Mapping Summary")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                customer_count = len(st.session_state.categorized_mappings.get('customerData', {}))
                st.metric("Customer Fields", customer_count)
            
            with col2:
                beneficiary_count = len(st.session_state.categorized_mappings.get('beneficiaryData', {}))
                st.metric("Beneficiary Fields", beneficiary_count)
            
            with col3:
                attorney_count = len(st.session_state.categorized_mappings.get('attorneyData', {}))
                st.metric("Attorney Fields", attorney_count)
            
            with col4:
                lca_count = len(st.session_state.categorized_mappings.get('lcaData', {}))
                st.metric("LCA Fields", lca_count)
            
            # Show categorized mappings
            with st.expander("View Categorized Mappings"):
                for category, mappings in st.session_state.categorized_mappings.items():
                    if mappings:
                        st.subheader(category)
                        for field, mapping in mappings.items():
                            st.text(f"{field} → {mapping}")

# Run the application
if __name__ == "__main__":
    main()
