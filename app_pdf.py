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
    'G-28': {
        'title': 'Notice of Entry of Appearance as Attorney or Accredited Representative',
        'patterns': [r'Form\s*G-28', r'Notice.*Entry.*Appearance'],
        'parts': OrderedDict([
            ('Part 1', 'Information About Attorney or Accredited Representative'),
            ('Part 2', 'Eligibility Information'),
            ('Part 3', 'Notice of Appearance'),
            ('Part 4', 'Client\'s Consent to Representation'),
            ('Part 5', 'Signature of Attorney'),
            ('Part 6', 'Additional Information')
        ])
    },
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

# Enhanced Mapping Patterns based on your document
ENHANCED_MAPPING_PATTERNS = {
    # Customer/Petitioner Information
    'customer': {
        'patterns': {
            'customer_name': {
                'regex': [r'petitioner.*name', r'company.*name', r'employer.*name', r'legal.*business.*name', r'name.*entity'],
                'mapping': 'customer.customer_name',
                'type': 'TextBox'
            },
            'customer_tax_id': {
                'regex': [r'(?:fein|ein)', r'employer.*identification', r'tax.*id', r'federal.*employer.*identification'],
                'mapping': 'customer.customer_tax_id',
                'type': 'TextBox'
            },
            'address_street': {
                'regex': [r'street.*number.*name', r'address.*1', r'street', r'address'],
                'mapping': 'customer.address_street',
                'type': 'TextBox'
            },
            'address_type': {
                'regex': [r'apt', r'ste', r'flr', r'address.*2'],
                'mapping': 'customer.address_type',
                'type': 'AddressTypeBox'
            },
            'address_number': {
                'regex': [r'apt.*number', r'suite.*number', r'floor.*number'],
                'mapping': 'customer.address_number',
                'type': 'TextBox'
            },
            'address_city': {
                'regex': [r'city', r'town'],
                'mapping': 'customer.address_city',
                'type': 'TextBox'
            },
            'address_state': {
                'regex': [r'state', r'province'],
                'mapping': 'customer.address_state',
                'type': 'TextBox'
            },
            'address_zip': {
                'regex': [r'zip.*code', r'postal.*code'],
                'mapping': 'customer.address_zip',
                'type': 'TextBox'
            },
            'address_country': {
                'regex': [r'country'],
                'mapping': 'customer.address_country',
                'type': 'TextBox'
            },
            'signatory_first_name': {
                'regex': [r'given.*name.*first', r'first.*name', r'authorized.*first'],
                'mapping': 'customer.signatory_first_name',
                'type': 'TextBox'
            },
            'signatory_last_name': {
                'regex': [r'family.*name.*last', r'last.*name', r'authorized.*last'],
                'mapping': 'customer.signatory_last_name',
                'type': 'TextBox'
            },
            'signatory_middle_name': {
                'regex': [r'middle.*name'],
                'mapping': 'customer.signatory_middle_name',
                'type': 'TextBox'
            },
            'signatory_job_title': {
                'regex': [r'title.*authorized', r'job.*title', r'position'],
                'mapping': 'customer.signatory_job_title',
                'type': 'TextBox'
            },
            'signatory_work_phone': {
                'regex': [r'daytime.*phone', r'work.*phone', r'telephone'],
                'mapping': 'customer.signatory_work_phone',
                'type': 'TextBox'
            },
            'signatory_mobile_phone': {
                'regex': [r'mobile.*phone', r'cell.*phone'],
                'mapping': 'customer.signatory_mobile_phone',
                'type': 'TextBox'
            },
            'signatory_email_id': {
                'regex': [r'email.*address', r'e-mail'],
                'mapping': 'customer.signatory_email_id',
                'type': 'TextBox'
            }
        }
    },
    
    # Attorney Information
    'attorney': {
        'patterns': {
            'attorney_last_name': {
                'regex': [r'attorney.*last.*name', r'representative.*last', r'family.*name'],
                'mapping': 'attorney.attorneyInfo.lastName',
                'type': 'TextBox'
            },
            'attorney_first_name': {
                'regex': [r'attorney.*first.*name', r'representative.*first', r'given.*name'],
                'mapping': 'attorney.attorneyInfo.firstName',
                'type': 'TextBox'
            },
            'attorney_middle_name': {
                'regex': [r'attorney.*middle.*name'],
                'mapping': 'attorney.attorneyInfo.middleName',
                'type': 'TextBox'
            },
            'state_bar_number': {
                'regex': [r'bar.*number', r'license.*number', r'state.*bar'],
                'mapping': 'attorney.attorneyInfo.stateBarNumber',
                'type': 'TextBox'
            },
            'law_firm_name': {
                'regex': [r'law.*firm.*name', r'organization.*name', r'firm.*name'],
                'mapping': 'attorneyLawfirmDetails.lawfirmDetails.lawFirmName',
                'type': 'TextBox'
            },
            'attorney_work_phone': {
                'regex': [r'attorney.*phone', r'daytime.*telephone'],
                'mapping': 'attorney.attorneyInfo.workPhone',
                'type': 'TextBox'
            },
            'attorney_email': {
                'regex': [r'attorney.*email', r'email.*address'],
                'mapping': 'attorney.attorneyInfo.emailAddress',
                'type': 'TextBox'
            },
            'attorney_fax': {
                'regex': [r'fax.*number'],
                'mapping': 'attorney.attorneyInfo.faxNumber',
                'type': 'TextBox'
            },
            'licensing_authority': {
                'regex': [r'licensing.*authority'],
                'mapping': 'attorney.attorneyInfo.licensingAuthority',
                'type': 'TextBox'
            }
        }
    },
    
    # Beneficiary Information
    'beneficiary': {
        'patterns': {
            'beneficiary_last_name': {
                'regex': [r'beneficiary.*last.*name', r'client.*last.*name', r'family.*name'],
                'mapping': 'beneficiary.Beneficiary.beneficiaryLastName',
                'type': 'TextBox'
            },
            'beneficiary_first_name': {
                'regex': [r'beneficiary.*first.*name', r'client.*first.*name', r'given.*name'],
                'mapping': 'beneficiary.Beneficiary.beneficiaryFirstName',
                'type': 'TextBox'
            },
            'beneficiary_middle_name': {
                'regex': [r'beneficiary.*middle.*name', r'client.*middle.*name'],
                'mapping': 'beneficiary.Beneficiary.beneficiaryMiddleName',
                'type': 'TextBox'
            },
            'alien_number': {
                'regex': [r'alien.*registration.*number', r'a[\-\s]?number', r'uscis.*number'],
                'mapping': 'beneficiary.Beneficiary.alien_number',
                'type': 'TextBox'
            },
            'beneficiary_dob': {
                'regex': [r'date.*birth', r'birth.*date', r'd\.?o\.?b'],
                'mapping': 'beneficiary.Beneficiary.beneficiaryDateOfBirth',
                'type': 'Date'
            },
            'beneficiary_ssn': {
                'regex': [r'social.*security', r'ssn', r'ss.*number'],
                'mapping': 'beneficiary.Beneficiary.beneficiarySsn',
                'type': 'TextBox'
            },
            'beneficiary_gender': {
                'regex': [r'gender', r'sex'],
                'mapping': 'beneficiary.Beneficiary.beneficiaryGender',
                'type': 'RadioButton'
            }
        }
    },
    
    # LCA Information
    'lca': {
        'patterns': {
            'position_job_title': {
                'regex': [r'job.*title', r'position', r'occupation'],
                'mapping': 'lca.position_job_title',
                'type': 'TextBox'
            },
            'lca_number': {
                'regex': [r'lca.*number', r'eta.*case', r'lca.*case'],
                'mapping': 'lca.lcaNumber',
                'type': 'TextBox'
            },
            'start_date': {
                'regex': [r'start.*date', r'begin.*date', r'from.*date'],
                'mapping': 'lca.start_date',
                'type': 'Date'
            },
            'end_date': {
                'regex': [r'end.*date', r'to.*date'],
                'mapping': 'lca.end_date',
                'type': 'Date'
            },
            'gross_salary': {
                'regex': [r'wage.*rate', r'salary', r'compensation'],
                'mapping': 'lca.gross_salary',
                'type': 'Currency'
            }
        }
    },
    
    # Case Information
    'case': {
        'patterns': {
            'case_type': {
                'regex': [r'classification', r'visa.*type', r'case.*type'],
                'mapping': 'case.caseType',
                'type': 'TextBox'
            },
            'case_sub_type': {
                'regex': [r'basis.*classification', r'sub.*type'],
                'mapping': 'case.caseSubType',
                'type': 'TextBox'
            },
            'receipt_number': {
                'regex': [r'receipt.*number', r'case.*number'],
                'mapping': 'case.uscisReceiptNumber',
                'type': 'TextBox'
            }
        }
    }
}

# Form-specific field mapping based on G-28 example
FORM_SPECIFIC_MAPPINGS = {
    'G-28': {
        # Part 1 - Attorney Information
        'Part1_Item2a': {'mapping': 'attorney.attorneyInfo.lastName', 'type': 'TextBox'},
        'Part1_Item2b': {'mapping': 'attorney.attorneyInfo.firstName', 'type': 'TextBox'},
        'Part1_Item2c': {'mapping': 'attorney.attorneyInfo.middleName', 'type': 'TextBox'},
        'Part1_Item3a': {'mapping': 'attorneyLawfirmDetails.address.addressStreet', 'type': 'TextBox'},
        'Part1_Item3b_Apt': {'mapping': 'attorneyLawfirmDetails.address.addressType', 'type': 'CheckBox'},
        'Part1_Item3b_Ste': {'mapping': 'attorneyLawfirmDetails.address.addressType', 'type': 'CheckBox'},
        'Part1_Item3b_Flr': {'mapping': 'attorneyLawfirmDetails.address.addressType', 'type': 'CheckBox'},
        'Part1_Item3b_Number': {'mapping': 'attorneyLawfirmDetails.address.addressNumber', 'type': 'TextBox'},
        'Part1_Item3c': {'mapping': 'attorneyLawfirmDetails.address.addressCity', 'type': 'TextBox'},
        'Part1_Item3d': {'mapping': 'attorneyLawfirmDetails.address.addressState', 'type': 'TextBox'},
        'Part1_Item3e': {'mapping': 'attorneyLawfirmDetails.address.addressZip', 'type': 'TextBox'},
        'Part1_Item3h': {'mapping': 'attorneyLawfirmDetails.address.addressCountry', 'type': 'TextBox'},
        'Part1_Item4': {'mapping': 'attorney.attorneyInfo.workPhone', 'type': 'TextBox'},
        'Part1_Item6': {'mapping': 'attorney.attorneyInfo.emailAddress', 'type': 'TextBox'},
        'Part1_Item7': {'mapping': 'attorney.attorneyInfo.faxNumber', 'type': 'TextBox'},
        
        # Part 2 - Eligibility
        'Part2_Item1a_Licensing': {'mapping': 'attorney.attorneyInfo.licensingAuthority', 'type': 'TextBox'},
        'Part2_Item1b': {'mapping': 'attorney.attorneyInfo.stateBarNumber', 'type': 'TextBox'},
        'Part2_Item1d': {'mapping': 'attorneyLawfirmDetails.lawfirmDetails.lawFirmName', 'type': 'TextBox'},
        
        # Part 3 - Client Information
        'Part3_Item6a': {'mapping': 'customer.signatory_last_name', 'type': 'TextBox'},
        'Part3_Item6b': {'mapping': 'customer.signatory_first_name', 'type': 'TextBox'},
        'Part3_Item6c': {'mapping': 'customer.signatory_middle_name', 'type': 'TextBox'},
        'Part3_Item7a': {'mapping': 'customer.customer_name', 'type': 'TextBox'},
        'Part3_Item7b': {'mapping': 'customer.signatory_job_title', 'type': 'TextBox'},
        'Part3_Item10': {'mapping': 'customer.signatory_work_phone', 'type': 'TextBox'},
        'Part3_Item11': {'mapping': 'customer.signatory_mobile_phone', 'type': 'TextBox'},
        'Part3_Item12': {'mapping': 'customer.signatory_email_id', 'type': 'TextBox'},
        'Part3_Item13a': {'mapping': 'customer.address_street', 'type': 'TextBox'},
        'Part3_Item13b_Apt': {'mapping': 'customer.address_type', 'type': 'CheckBox'},
        'Part3_Item13b_Number': {'mapping': 'customer.address_number', 'type': 'TextBox'},
        'Part3_Item13c': {'mapping': 'customer.address_city', 'type': 'TextBox'},
        'Part3_Item13d': {'mapping': 'customer.address_state', 'type': 'TextBox'},
        'Part3_Item13e': {'mapping': 'customer.address_zip', 'type': 'TextBox'},
        'Part3_Item13h': {'mapping': 'customer.address_country', 'type': 'TextBox'}
    }
}

# Default field values
DEFAULT_FIELD_VALUES = {
    'G-28': {
        'licensing': {'value': True, 'type': 'CheckBox'},
        'amnot': {'value': True, 'type': 'CheckBox'},
        'pt4_1a': {'value': True, 'type': 'CheckBox'},
        'pt4_1b': {'value': True, 'type': 'CheckBox'}
    }
}

# Conditional field mappings
CONDITIONAL_FIELD_MAPPINGS = {
    'G-28': {
        'pt3_1a': {
            'condition': '1_ag==true',
            'conditionTrue': 'true',
            'conditionFalse': '',
            'conditionType': 'CheckBox'
        },
        'pt3_1b': {
            'condition': '1_ag==true',
            'conditionTrue': 'formNumApp',
            'conditionFalse': '',
            'conditionType': 'TextBox'
        },
        'applicant': {
            'condition': 'representative==1',
            'conditionTrue': '1',
            'conditionFalse': '',
            'conditionType': 'CheckBox'
        },
        'petitioner': {
            'condition': 'representative==2',
            'conditionTrue': '2',
            'conditionFalse': '',
            'conditionType': 'CheckBox'
        }
    }
}

# CSS Styling
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
    
    /* Progress Ring */
    .progress-ring {
        display: inline-block;
        width: 60px;
        height: 60px;
    }
    
    .progress-ring circle {
        transition: stroke-dashoffset 0.5s ease;
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
        'removed_fields': [],
        'processing_log': [],
        'attorney_fields': [],
        'expand_all_parts': False,
        'expanded_parts': set(),
        'mapping_suggestions': {},
        'field_detection_confidence': {},
        'customer_data': {},
        'beneficiary_data': {},
        'attorney_data': {},
        'lca_data': {},
        'case_data': {},
        'lawfirm_data': {}
    }
    
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

init_session_state()

# Enhanced PDF extraction for USCIS forms
def extract_uscis_pdf(pdf_file) -> Tuple[List[Dict[str, Any]], OrderedDict]:
    """Extract fields from USCIS PDF forms with enhanced part organization"""
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
            
            # Extract all pages text
            for page_num in range(3, len(doc)):
                page = doc[page_num]
                text = page.get_text()
                extracted_text += f"\n--- Page {page_num + 1} ---\n{text}"
            
            # Extract form fields with enhanced detection
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Extract form widgets
                for widget in page.widgets():
                    field_name = widget.field_name
                    if field_name:
                        # Enhanced field analysis
                        field_info = analyze_field_name_enhanced(field_name, extracted_text, form_type)
                        
                        field_data = {
                            'name': field_name,
                            'type': map_widget_type(widget.field_type_string),
                            'value': widget.field_value or '',
                            'required': widget.field_flags & 2 != 0,
                            'page': page_num + 1,
                            'part': field_info['part'],
                            'rect': list(widget.rect),
                            'source': 'PyMuPDF',
                            'suggested_mapping': field_info['suggested_mapping'],
                            'confidence': field_info['confidence'],
                            'db_category': field_info['db_category']
                        }
                        fields.append(field_data)
            
            doc.close()
            processing_log.append(f"Extracted {len(fields)} fields using PyMuPDF")
            
        except Exception as e:
            processing_log.append(f"PyMuPDF error: {str(e)}")
    
    # Fallback to PyPDF2 if needed
    if len(fields) < 10 and PDF_AVAILABLE:
        try:
            processing_log.append("Trying PyPDF2 extraction...")
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
            if '/AcroForm' in reader.trailer['/Root']:
                acroform = reader.trailer['/Root']['/AcroForm']
                if '/Fields' in acroform:
                    for field_ref in acroform['/Fields']:
                        field = field_ref.get_object()
                        field_info = extract_field_info(field)
                        if field_info:
                            # Enhanced field analysis
                            analysis = analyze_field_name_enhanced(field_info['name'], extracted_text, form_type)
                            field_info.update(analysis)
                            fields.append(field_info)
            
            processing_log.append(f"Extracted {len(fields)} fields using PyPDF2")
            
        except Exception as e:
            processing_log.append(f"PyPDF2 error: {str(e)}")
    
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
        text_fields = extract_fields_from_text_enhanced(extracted_text, form_type)
        fields.extend(text_fields)
        processing_log.append(f"Found {len(text_fields)} additional fields from text")
    
    # Organize fields by parts
    form_parts = organize_fields_by_parts_enhanced(fields, form_type)
    
    return fields, form_parts

def extract_field_info(field_obj) -> Optional[Dict[str, Any]]:
    """Extract field information from PDF field object"""
    try:
        field_info = {
            'name': field_obj.get('/T', ''),
            'type': field_obj.get('/FT', '/Tx'),
            'value': field_obj.get('/V', ''),
            'required': bool(field_obj.get('/Ff', 0) & 2),
            'page': 1,
            'part': 'Unassigned Fields',
            'source': 'PyPDF2'
        }
        
        # Map field types
        type_map = {
            '/Tx': 'TextBox',
            '/Btn': 'CheckBox' if field_obj.get('/Ff', 0) & 65536 else 'RadioButton',
            '/Ch': 'DropDown',
            '/Sig': 'Signature'
        }
        field_info['type'] = type_map.get(field_info['type'], 'TextBox')
        
        return field_info
    except:
        return None

def analyze_field_name_enhanced(field_name: str, text: str, form_type: Optional[str]) -> Dict[str, Any]:
    """Enhanced field analysis with database object categorization"""
    result = {
        'part': 'Unassigned Fields',
        'suggested_mapping': None,
        'confidence': 0.0,
        'db_category': None
    }
    
    field_lower = field_name.lower()
    
    # Check if it's a form-specific field
    if form_type and form_type in FORM_SPECIFIC_MAPPINGS:
        for field_key, mapping_info in FORM_SPECIFIC_MAPPINGS[form_type].items():
            if field_key.lower() in field_lower or field_lower in field_key.lower():
                result['suggested_mapping'] = mapping_info['mapping']
                result['confidence'] = 0.95
                result['db_category'] = determine_db_category(mapping_info['mapping'])
                
                # Determine part from field name
                part_match = re.search(r'Part(\d+)', field_key)
                if part_match and form_type in USCIS_FORMS_DATABASE:
                    part_num = part_match.group(1)
                    parts = USCIS_FORMS_DATABASE[form_type]['parts']
                    part_key = f'Part {part_num}'
                    if part_key in parts:
                        result['part'] = f'{part_key} - {parts[part_key]}'
                
                return result
    
    # Try pattern matching for each database category
    for category, category_info in ENHANCED_MAPPING_PATTERNS.items():
        for field_type, field_patterns in category_info['patterns'].items():
            for pattern in field_patterns['regex']:
                if re.search(pattern, field_lower):
                    result['suggested_mapping'] = field_patterns['mapping']
                    result['confidence'] = 0.8
                    result['db_category'] = category
                    break
            if result['suggested_mapping']:
                break
        if result['suggested_mapping']:
            break
    
    # Try to extract part number from field name
    part_match = re.search(r'(?:part|p)[\s_\-]*(\d+)', field_lower)
    if part_match:
        part_num = part_match.group(1)
        if form_type and form_type in USCIS_FORMS_DATABASE:
            parts = USCIS_FORMS_DATABASE[form_type]['parts']
            part_key = f'Part {part_num}'
            if part_key in parts:
                result['part'] = f'{part_key} - {parts[part_key]}'
    
    return result

def determine_db_category(mapping: str) -> str:
    """Determine database category from mapping string"""
    if mapping.startswith('customer'):
        return 'customer'
    elif mapping.startswith('attorney'):
        return 'attorney'
    elif mapping.startswith('beneficiary'):
        return 'beneficiary'
    elif mapping.startswith('lca'):
        return 'lca'
    elif mapping.startswith('case'):
        return 'case'
    elif mapping.startswith('lawfirm'):
        return 'lawfirm'
    else:
        return 'other'

def extract_fields_from_text_enhanced(text: str, form_type: Optional[str]) -> List[Dict[str, Any]]:
    """Enhanced field extraction from text using USCIS-specific patterns"""
    fields = []
    seen_fields = set()
    
    # Enhanced USCIS-specific field patterns
    patterns = [
        # Part-based patterns (standard forms)
        (r'Part\s+(\d+)[\.\s]*(?:Item\s*Number\s*)?(\d+)\.?([a-z]?)[\.\s]*([A-Za-z][A-Za-z\s\-\(\)]{2,50})', 'uscis_part'),
        # Section patterns (LCA style)
        (r'Section\s+([A-Z])[\.\s]*(?:Item\s*)?(\d+)\.?([a-z]?)[\.\s]*([A-Za-z][A-Za-z\s\-]{2,50})', 'uscis_section'),
        # Item patterns
        (r'Item\s*(?:Number\s*)?(\d+)\.?([a-z]?)[\.\s]*([A-Za-z][A-Za-z\s\-]{2,50})', 'uscis_item'),
        # Question patterns
        (r'(\d+)\.?([a-z]?)[\.\s]*([A-Za-z][A-Za-z\s\?]{5,50})', 'question'),
        # Checkbox patterns
        (r'\[\s*\]\s*([A-Za-z][A-Za-z\s\-]{2,50})', 'checkbox'),
        # Radio button patterns
        (r'\(\s*\)\s*([A-Za-z][A-Za-z\s\-]{2,50})', 'radio')
    ]
    
    for pattern, pattern_type in patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            field_name = create_field_name_enhanced(match, pattern_type, form_type)
            
            if field_name and field_name.lower() not in seen_fields:
                seen_fields.add(field_name.lower())
                
                # Enhanced field analysis
                field_info = analyze_field_name_enhanced(field_name, text, form_type)
                field_type = determine_field_type_enhanced(field_name, pattern_type)
                
                fields.append({
                    'name': field_name,
                    'type': field_type,
                    'value': '',
                    'required': is_field_required_enhanced(field_name),
                    'page': 0,
                    'part': field_info['part'],
                    'source': 'text_extraction',
                    'suggested_mapping': field_info['suggested_mapping'],
                    'confidence': field_info['confidence'],
                    'db_category': field_info['db_category']
                })
    
    return fields

def create_field_name_enhanced(match, pattern_type: str, form_type: Optional[str]) -> str:
    """Create enhanced standardized USCIS field names"""
    if pattern_type == 'uscis_part':
        part = match.group(1)
        item = match.group(2)
        sub = match.group(3) or ''
        desc = match.group(4).strip()
        desc_clean = re.sub(r'[^\w]', '_', desc)[:40]
        
        # Form-specific naming
        if form_type:
            return f"Part{part}_Item{item}{sub}_{desc_clean}"
        return f"Part{part}_Item{item}{sub}_{desc_clean}"
    
    elif pattern_type == 'uscis_section':
        section = match.group(1)
        item = match.group(2)
        sub = match.group(3) or ''
        desc = match.group(4).strip()
        desc_clean = re.sub(r'[^\w]', '_', desc)[:40]
        return f"Section{section}_Item{item}{sub}_{desc_clean}"
    
    elif pattern_type == 'checkbox':
        field_text = match.group(1).strip()
        return re.sub(r'\s+', '_', field_text)
    
    elif pattern_type == 'radio':
        field_text = match.group(1).strip()
        return re.sub(r'\s+', '_', field_text)
    
    else:
        # Generic field name
        if match.groups():
            field_text = match.group(0).strip()
        else:
            field_text = match.string[match.start():match.end()].strip()
        return re.sub(r'[^\w]', '_', field_text)[:50]

def determine_field_type_enhanced(field_name: str, pattern_type: str) -> str:
    """Enhanced field type determination for USCIS forms"""
    if pattern_type == 'checkbox':
        return 'CheckBox'
    elif pattern_type == 'radio':
        return 'RadioButton'
    
    field_lower = field_name.lower()
    
    # Enhanced type patterns
    if any(word in field_lower for word in ['date', 'dob', 'birth', 'expire', 'mm/dd/yyyy']):
        return 'Date'
    elif any(word in field_lower for word in ['signature', 'sign']):
        return 'Signature'
    elif any(word in field_lower for word in ['amount', 'fee', 'wage', 'salary', '$', 'compensation']):
        return 'Currency'
    elif any(word in field_lower for word in ['select', 'choose', 'dropdown', 'pick one']):
        return 'DropDown'
    elif any(word in field_lower for word in ['describe', 'explain', 'additional', 'details', 'summary']):
        return 'TextArea'
    elif any(word in field_lower for word in ['phone', 'telephone', 'fax']):
        return 'TextBox'
    elif any(word in field_lower for word in ['email', 'e-mail']):
        return 'TextBox'
    elif any(word in field_lower for word in ['number', 'count', 'total']):
        return 'TextBox'
    elif any(word in field_lower for word in ['apt', 'ste', 'flr']):
        return 'AddressTypeBox'
    
    return 'TextBox'

def is_field_required_enhanced(field_name: str) -> bool:
    """Enhanced determination if a USCIS field is required"""
    field_lower = field_name.lower()
    
    # Enhanced required field patterns
    required_patterns = [
        'name', 'date', 'signature', 'alien number', 'a-number',
        'ssn', 'social security', 'address', 'city', 'state',
        'country', 'birth', 'citizenship', 'employer', 'fein',
        'ein', 'phone', 'email', 'classification', 'petition type'
    ]
    
    return any(pattern in field_lower for pattern in required_patterns)

def organize_fields_by_parts_enhanced(fields: List[Dict], form_type: Optional[str]) -> OrderedDict:
    """Enhanced organization of fields by form parts"""
    form_parts = OrderedDict()
    
    # Add known parts for the form type
    if form_type and form_type in USCIS_FORMS_DATABASE:
        for part_key, part_desc in USCIS_FORMS_DATABASE[form_type]['parts'].items():
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
        
        # Store suggestions
        if field.get('suggested_mapping'):
            st.session_state.mapping_suggestions[field['name']] = {
                'mapping': field['suggested_mapping'],
                'confidence': field.get('confidence', 0.0),
                'db_category': field.get('db_category', 'other')
            }
    
    # Remove empty parts
    parts_to_keep = OrderedDict()
    for part_name, part_fields in form_parts.items():
        if part_fields or part_name == 'Unassigned Fields':
            parts_to_keep[part_name] = part_fields
    
    return parts_to_keep

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

# UI Components
def render_field_row_enhanced(field: Dict, unique_key: str):
    """Enhanced field row rendering with database categorization"""
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
        
        # Show confidence and category if available
        if field_name in st.session_state.mapping_suggestions:
            suggestion_info = st.session_state.mapping_suggestions[field_name]
            confidence = suggestion_info['confidence']
            db_category = suggestion_info.get('db_category', 'other')
            if confidence > 0:
                confidence_color = "#2e8540" if confidence > 0.7 else "#fdb81e" if confidence > 0.4 else "#e21727"
                st.markdown(f'<span style="color: {confidence_color}; font-size: 0.85em;">Confidence: {confidence:.0%} | Category: {db_category}</span>', unsafe_allow_html=True)
    
    with col2:
        if is_mapped:
            # Show current mapping
            mapping = st.session_state.mapped_fields[field_name]
            if ':' in mapping:
                mapping_path, mapping_type = mapping.split(':', 1)
            else:
                mapping_path = mapping
                mapping_type = field_type
            st.text_input("Mapped to", value=mapping_path, disabled=True, key=f"mapped_{unique_key}")
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
                # Categorize the mapping
                db_cat = determine_db_category(new_mapping)
                if db_cat:
                    if db_cat not in st.session_state:
                        st.session_state[f'{db_cat}_data'] = {}
                    st.session_state[f'{db_cat}_data'][field_name] = f"{new_mapping}:{field_type}"
                st.rerun()
    
    with col3:
        if is_mapped:
            if st.button("❌", key=f"unmap_{unique_key}", help="Remove mapping"):
                del st.session_state.mapped_fields[field_name]
                # Remove from categorized data
                for cat in ['customer_data', 'attorney_data', 'beneficiary_data', 'lca_data', 'case_data', 'lawfirm_data']:
                    if field_name in st.session_state.get(cat, {}):
                        del st.session_state[cat][field_name]
                st.rerun()
        else:
            if st.button("✓", key=f"map_{unique_key}", help="Quick map with suggestion"):
                if field_name in st.session_state.mapping_suggestions:
                    suggested = st.session_state.mapping_suggestions[field_name]['mapping']
                    field_type_to_use = field_type
                    
                    # Check if there's a specific type in the mapping patterns
                    db_cat = st.session_state.mapping_suggestions[field_name].get('db_category')
                    if db_cat and db_cat in ENHANCED_MAPPING_PATTERNS:
                        for pattern_key, pattern_info in ENHANCED_MAPPING_PATTERNS[db_cat]['patterns'].items():
                            if pattern_info['mapping'] == suggested and 'type' in pattern_info:
                                field_type_to_use = pattern_info['type']
                                break
                    
                    st.session_state.mapped_fields[field_name] = f"{suggested}:{field_type_to_use}"
                    
                    # Add to categorized data
                    if db_cat:
                        if f'{db_cat}_data' not in st.session_state:
                            st.session_state[f'{db_cat}_data'] = {}
                        st.session_state[f'{db_cat}_data'][field_name] = f"{suggested}:{field_type_to_use}"
                    
                    st.rerun()
    
    with col4:
        if not is_questionnaire:
            if st.button("❓", key=f"quest_{unique_key}", help="Move to questionnaire"):
                # Determine appropriate questionnaire type
                q_type = 'checkbox' if field_type == 'CheckBox' else 'radio' if field_type == 'RadioButton' else 'text'
                
                st.session_state.questionnaire_fields[field_name] = {
                    'type': q_type,
                    'required': field.get('required', False),
                    'label': beautify_field_name(field_name),
                    'options': 'Yes\nNo' if field_type in ['CheckBox', 'RadioButton'] else '',
                    'validation': '',
                    'style': {"col": "12"},
                    'original_type': field_type
                }
                st.rerun()
    
    with col5:
        if st.button("🗑️", key=f"remove_{unique_key}", help="Remove field"):
            st.session_state.removed_fields.append(field_name)
            st.rerun()

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
        if word.upper() in ['SSN', 'DOB', 'EIN', 'FEIN', 'LCA', 'US', 'USA', 'USCIS', 'ICE', 'CBP']:
            capitalized.append(word.upper())
        else:
            capitalized.append(word.capitalize())
    return ' '.join(capitalized).strip()

def generate_typescript_g28_format() -> str:
    """Generate TypeScript in exact G-28 format"""
    form_name = st.session_state.form_name or 'USCISForm'
    form_name_clean = re.sub(r'[^\w]', '', form_name)
    
    # Organize mapped fields by database category
    customer_data = {}
    beneficiary_data = {}
    attorney_data = {}
    lca_data = {}
    case_data = {}
    
    # Process mapped fields
    for field_name, mapping in st.session_state.mapped_fields.items():
        if ':' in mapping:
            mapping_path, field_type = mapping.split(':', 1)
        else:
            mapping_path = mapping
            field_type = 'TextBox'
        
        # Create a clean field key
        field_key = re.sub(r'^Part\d+_Item\d+[a-z]?_', '', field_name)
        field_key = re.sub(r'[^\w]', '', field_key)
        
        # Categorize by database object
        if mapping_path.startswith('customer'):
            customer_data[field_key] = f"{mapping_path}:{field_type}"
        elif mapping_path.startswith('beneficiary'):
            beneficiary_data[field_key] = f"{mapping_path}:{field_type}"
        elif mapping_path.startswith('attorney'):
            attorney_data[field_key] = f"{mapping_path}:{field_type}"
        elif mapping_path.startswith('lca'):
            lca_data[field_key] = f"{mapping_path}:{field_type}"
        elif mapping_path.startswith('case'):
            case_data[field_key] = f"{mapping_path}:{field_type}"
    
    # Process questionnaire fields
    questionnaire_data = {}
    for field_name, config in st.session_state.questionnaire_fields.items():
        # Create questionnaire field key
        field_key = re.sub(r'[^\w]', '', field_name)[:30]
        
        # Determine questionnaire type
        q_type = 'ConditionBox' if config['type'] in ['checkbox', 'radio'] else 'SingleBox'
        
        questionnaire_data[field_key] = f"{field_key}:{q_type}"
    
    # Process default fields
    default_data = {}
    if st.session_state.form_type in DEFAULT_FIELD_VALUES:
        for field_key, field_info in DEFAULT_FIELD_VALUES[st.session_state.form_type].items():
            default_data[field_key] = f":{field_info['type']}"
    
    # Process conditional fields
    conditional_data = {}
    if st.session_state.form_type in CONDITIONAL_FIELD_MAPPINGS:
        conditional_data = CONDITIONAL_FIELD_MAPPINGS[st.session_state.form_type]
    
    # Generate TypeScript
    ts_content = f"""export const {form_name_clean} = {{
    "formname": "{form_name_clean}",
    "customerData": {json.dumps(customer_data, indent=8) if customer_data else 'null'},
    "beneficiaryData": {json.dumps(beneficiary_data, indent=8) if beneficiary_data else 'null'},
    "questionnaireData": {json.dumps(questionnaire_data, indent=8)},
    "defaultData": {json.dumps(default_data, indent=8) if default_data else '{}'},
    "conditionalData": {json.dumps(conditional_data, indent=8) if conditional_data else '{}'},
    "attorneyData": {json.dumps(attorney_data, indent=8) if attorney_data else 'null'},
    "pdfName": "{form_name_clean}",
    "caseData": {json.dumps(case_data, indent=8) if case_data else 'null'}
}}"""
    
    return ts_content

def generate_json_for_unmapped() -> str:
    """Generate JSON for unmapped fields with questionnaire format"""
    unmapped_fields = []
    
    for field in st.session_state.pdf_fields:
        field_name = field['name']
        if (field_name not in st.session_state.mapped_fields and 
            field_name not in st.session_state.questionnaire_fields and
            field_name not in st.session_state.removed_fields):
            
            # Create questionnaire control structure
            control = {
                "name": field_name,
                "label": beautify_field_name(field_name),
                "type": map_field_type_to_questionnaire(field['type']),
                "validators": {
                    "required": field.get('required', False)
                },
                "style": {
                    "col": "12" if field['type'] in ['TextArea', 'Signature'] else "7"
                }
            }
            
            # Add specific properties based on type
            if field['type'] in ['CheckBox', 'RadioButton']:
                control["value"] = "1"
                control["className"] = "pt-15"
            elif field['type'] == 'TextBox' and 'email' in field_name.lower():
                control["validators"]["email"] = True
            elif field['type'] == 'Date':
                control["validators"]["date"] = True
            
            unmapped_fields.append(control)
    
    # Create the questionnaire structure
    questionnaire = {
        "controls": unmapped_fields
    }
    
    return json.dumps(questionnaire, indent=2)

def map_field_type_to_questionnaire(field_type: str) -> str:
    """Map PDF field types to questionnaire control types"""
    type_map = {
        'TextBox': 'text',
        'TextArea': 'textarea',
        'CheckBox': 'colorSwitch',
        'RadioButton': 'radio',
        'DropDown': 'select',
        'Date': 'date',
        'Signature': 'signature',
        'Currency': 'text',
        'Email': 'text',
        'Phone': 'text',
        'Number': 'number'
    }
    return type_map.get(field_type, 'text')

# Auto-mapping functions
def auto_map_all_fields():
    """Enhanced auto-mapping with database categorization"""
    mapped_count = 0
    
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
                    'options': 'Yes\nNo',
                    'validation': '',
                    'style': {"col": "12"},
                    'original_type': field['type']
                }
                mapped_count += 1
            else:
                # Try to map with confidence threshold
                if field_name in st.session_state.mapping_suggestions:
                    suggestion_info = st.session_state.mapping_suggestions[field_name]
                    if suggestion_info['confidence'] > 0.3:
                        mapping = suggestion_info['mapping']
                        db_cat = suggestion_info.get('db_category', 'other')
                        
                        # Get the appropriate field type
                        field_type = field['type']
                        if db_cat in ENHANCED_MAPPING_PATTERNS:
                            for pattern_key, pattern_info in ENHANCED_MAPPING_PATTERNS[db_cat]['patterns'].items():
                                if pattern_info['mapping'] == mapping and 'type' in pattern_info:
                                    field_type = pattern_info['type']
                                    break
                        
                        st.session_state.mapped_fields[field_name] = f"{mapping}:{field_type}"
                        
                        # Add to categorized data
                        if db_cat:
                            if f'{db_cat}_data' not in st.session_state:
                                st.session_state[f'{db_cat}_data'] = {}
                            st.session_state[f'{db_cat}_data'][field_name] = f"{mapping}:{field_type}"
                        
                        mapped_count += 1
    
    return mapped_count

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
            
            # Database object distribution
            st.markdown("---")
            st.header("🗄️ Database Objects")
            
            db_counts = {
                'Customer': len(st.session_state.get('customer_data', {})),
                'Attorney': len(st.session_state.get('attorney_data', {})),
                'Beneficiary': len(st.session_state.get('beneficiary_data', {})),
                'LCA': len(st.session_state.get('lca_data', {})),
                'Case': len(st.session_state.get('case_data', {}))
            }
            
            for obj_name, count in db_counts.items():
                if count > 0:
                    st.metric(obj_name, count)
        
        st.markdown("---")
        
        # Actions
        st.header("⚡ Quick Actions")
        
        if st.button("🤖 Auto-Map All", use_container_width=True, type="primary"):
            count = auto_map_all_fields()
            st.success(f"Auto-mapped {count} fields!")
            st.rerun()
        
        if st.button("📋 All Checkboxes to Questionnaire", use_container_width=True):
            count = 0
            for field in st.session_state.pdf_fields:
                if field['type'] in ['CheckBox', 'RadioButton'] and field['name'] not in st.session_state.questionnaire_fields:
                    st.session_state.questionnaire_fields[field['name']] = {
                        'type': 'checkbox' if field['type'] == 'CheckBox' else 'radio',
                        'required': field.get('required', False),
                        'label': beautify_field_name(field['name']),
                        'options': 'Yes\nNo',
                        'validation': '',
                        'style': {"col": "12"},
                        'original_type': field['type']
                    }
                    count += 1
            st.success(f"Moved {count} fields to questionnaire!")
            st.rerun()
        
        if st.button("🔄 Reset All", use_container_width=True):
            init_session_state()
            st.rerun()
    
    # Main content
    tab1, tab2, tab3, tab4 = st.tabs([
        "📤 Upload & Process",
        "🗂️ Field Mapping",
        "📥 Export",
        "📊 Analysis"
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
            help="Supported forms: G-28, I-129, I-539, I-140, I-485, I-765, I-131, LCA, and more"
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
            # Show form parts
            for idx, (part_name, part_fields) in enumerate(st.session_state.form_parts.items()):
                with st.expander(f"{part_name} ({len(part_fields)} fields)", expanded=idx == 0):
                    for field_idx, field in enumerate(part_fields):
                        if field['name'] not in st.session_state.removed_fields:
                            render_field_row_enhanced(field, f"{idx}_{field_idx}")
    
    # Tab 3: Export
    with tab3:
        st.header("Export Configuration")
        
        if not st.session_state.pdf_fields:
            st.warning("⚠️ No data to export")
        else:
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📄 TypeScript Export (G-28 Format)")
                st.caption("For mapped fields organized by database objects")
                
                if st.button("Generate TypeScript", type="primary", use_container_width=True):
                    ts_content = generate_typescript_g28_format()
                    st.download_button(
                        "📥 Download TypeScript",
                        data=ts_content,
                        file_name=f"{st.session_state.form_name or 'USCIS_Form'}.ts",
                        mime="text/plain"
                    )
                    with st.expander("Preview TypeScript"):
                        st.code(ts_content, language="typescript")
            
            with col2:
                st.subheader("📋 JSON Export (Questionnaire Format)")
                st.caption("For unmapped fields as questionnaire controls")
                
                if st.button("Generate JSON", type="primary", use_container_width=True):
                    json_content = generate_json_for_unmapped()
                    st.download_button(
                        "📥 Download JSON",
                        data=json_content,
                        file_name=f"{st.session_state.form_name or 'USCIS_Form'}_questionnaire.json",
                        mime="application/json"
                    )
                    with st.expander("Preview JSON"):
                        st.code(json_content, language="json")
    
    # Tab 4: Analysis
    with tab4:
        st.header("Form Analysis & Insights")
        
        if st.session_state.pdf_fields:
            # Field type distribution
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📊 Field Type Distribution")
                field_types = defaultdict(int)
                for field in st.session_state.pdf_fields:
                    field_types[field['type']] += 1
                
                for ftype, count in sorted(field_types.items(), key=lambda x: x[1], reverse=True):
                    progress = count / len(st.session_state.pdf_fields)
                    st.metric(ftype, count)
                    st.progress(progress)
            
            with col2:
                st.subheader("🎯 Mapping Confidence")
                if st.session_state.mapping_suggestions:
                    confidence_ranges = {
                        'High (>70%)': 0,
                        'Medium (40-70%)': 0,
                        'Low (<40%)': 0
                    }
                    
                    for suggestion in st.session_state.mapping_suggestions.values():
                        conf = suggestion['confidence']
                        if conf > 0.7:
                            confidence_ranges['High (>70%)'] += 1
                        elif conf > 0.4:
                            confidence_ranges['Medium (40-70%)'] += 1
                        else:
                            confidence_ranges['Low (<40%)'] += 1
                    
                    for range_name, count in confidence_ranges.items():
                        st.metric(range_name, count)
            
            # Database mapping coverage
            st.subheader("🗄️ Database Mapping Coverage")
            db_coverage = {
                'Customer Data': len(st.session_state.get('customer_data', {})),
                'Beneficiary Data': len(st.session_state.get('beneficiary_data', {})),
                'Attorney Data': len(st.session_state.get('attorney_data', {})),
                'LCA Data': len(st.session_state.get('lca_data', {})),
                'Case Data': len(st.session_state.get('case_data', {}))
            }
            
            cols = st.columns(len(db_coverage))
            for idx, (category, count) in enumerate(db_coverage.items()):
                with cols[idx]:
                    st.metric(category, count)

# Run the application
if __name__ == "__main__":
    main()
