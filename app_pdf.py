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

# Comprehensive Mapping Patterns for USCIS Forms
USCIS_MAPPING_PATTERNS = {
    # Company/Petitioner Information
    'petitioner_info': {
        'patterns': {
            'company_name': {
                'regex': [r'petitioner.*name', r'company.*name', r'employer.*name', r'organization.*name', r'legal.*business.*name'],
                'mapping': 'customer.customer_name'
            },
            'tax_id': {
                'regex': [r'(?:fein|ein)', r'employer.*identification', r'tax.*id', r'federal.*employer.*identification'],
                'mapping': 'customer.customer_tax_id'
            },
            'address': {
                'regex': [r'petitioner.*address', r'company.*address', r'mailing.*address', r'employer.*address'],
                'mapping': 'customer.address_street'
            },
            'city': {
                'regex': [r'city', r'town'],
                'mapping': 'customer.address_city'
            },
            'state': {
                'regex': [r'state', r'province'],
                'mapping': 'customer.address_state'
            },
            'zip': {
                'regex': [r'zip.*code', r'postal.*code'],
                'mapping': 'customer.address_zip'
            },
            'signatory_name': {
                'regex': [r'signatory', r'authorized.*representative', r'contact.*person', r'in.*care.*of'],
                'mapping': 'customer.signatory_first_name + customer.signatory_last_name'
            },
            'signatory_title': {
                'regex': [r'title', r'job.*title', r'position'],
                'mapping': 'customer.signatory_job_title'
            },
            'phone': {
                'regex': [r'phone', r'telephone', r'daytime.*phone'],
                'mapping': 'customer.signatory_work_phone'
            },
            'email': {
                'regex': [r'email', r'e-mail'],
                'mapping': 'customer.signatory_email_id'
            },
            'naics': {
                'regex': [r'naics.*code', r'industry.*code'],
                'mapping': 'customer.customer_naics_code'
            },
            'employees': {
                'regex': [r'number.*employees', r'total.*employees'],
                'mapping': 'customer.customer_total_employees'
            },
            'h1_dependent': {
                'regex': [r'h.*1.*b.*dependent', r'dependent.*employer'],
                'mapping': 'customer.h1_dependent_employer'
            },
            'willful': {
                'regex': [r'willful.*violator'],
                'mapping': 'customer.willful_violator'
            }
        }
    },
    
    # Beneficiary Information
    'beneficiary_info': {
        'patterns': {
            'first_name': {
                'regex': [r'given.*name', r'first.*name', r'beneficiary.*first'],
                'mapping': 'beneficiary.Beneficiary.beneficiaryFirstName'
            },
            'last_name': {
                'regex': [r'family.*name', r'last.*name', r'surname', r'beneficiary.*last'],
                'mapping': 'beneficiary.Beneficiary.beneficiaryLastName'
            },
            'middle_name': {
                'regex': [r'middle.*name', r'middle.*initial'],
                'mapping': 'beneficiary.Beneficiary.beneficiaryMiddleName'
            },
            'dob': {
                'regex': [r'date.*birth', r'birth.*date', r'd\.?o\.?b'],
                'mapping': 'beneficiary.Beneficiary.beneficiaryDateOfBirth'
            },
            'alien_number': {
                'regex': [r'alien.*number', r'a[\-\s]?number', r'uscis.*number'],
                'mapping': 'beneficiary.Beneficiary.alien_number'
            },
            'ssn': {
                'regex': [r'social.*security', r'ssn', r'ss.*number'],
                'mapping': 'beneficiary.Beneficiary.beneficiarySsn'
            },
            'gender': {
                'regex': [r'gender', r'sex'],
                'mapping': 'beneficiary.Beneficiary.beneficiaryGender'
            },
            'country_birth': {
                'regex': [r'country.*birth', r'birth.*country'],
                'mapping': 'beneficiary.Beneficiary.beneficiaryCountryOfBirth'
            },
            'citizenship': {
                'regex': [r'citizenship', r'nationality', r'citizen.*country'],
                'mapping': 'beneficiary.Beneficiary.beneficiaryCitizenOfCountry'
            },
            'current_status': {
                'regex': [r'current.*status', r'nonimmigrant.*status'],
                'mapping': 'beneficiary.VisaDetails.Visa.visaStatus'
            },
            'i94_number': {
                'regex': [r'i[\-\s]?94.*number', r'arrival.*departure.*record'],
                'mapping': 'beneficiary.I94Details.I94.i94Number'
            },
            'passport': {
                'regex': [r'passport.*number', r'travel.*document.*number'],
                'mapping': 'beneficiary.PassportDetails.Passport.passportNumber'
            }
        }
    },
    
    # Attorney Information
    'attorney_info': {
        'patterns': {
            'last_name': {
                'regex': [r'attorney.*last', r'preparer.*last', r'representative.*last'],
                'mapping': 'attorney.attorneyInfo.lastName'
            },
            'first_name': {
                'regex': [r'attorney.*first', r'preparer.*first', r'representative.*first'],
                'mapping': 'attorney.attorneyInfo.firstName'
            },
            'bar_number': {
                'regex': [r'bar.*number', r'license.*number', r'state.*bar'],
                'mapping': 'attorney.attorneyInfo.stateBarNumber'
            },
            'firm_name': {
                'regex': [r'firm.*name', r'law.*firm', r'organization.*name'],
                'mapping': 'attorneyLawfirmDetails.lawfirmDetails.lawFirmName'
            }
        }
    },
    
    # LCA Information
    'lca_info': {
        'patterns': {
            'job_title': {
                'regex': [r'job.*title', r'position', r'occupation', r'employment.*title'],
                'mapping': 'lca.position_job_title'
            },
            'start_date': {
                'regex': [r'start.*date', r'begin.*date', r'employment.*start', r'from.*date'],
                'mapping': 'lca.start_date'
            },
            'end_date': {
                'regex': [r'end.*date', r'employment.*end', r'to.*date'],
                'mapping': 'lca.end_date'
            },
            'wages': {
                'regex': [r'wage', r'salary', r'compensation', r'pay.*rate'],
                'mapping': 'lca.gross_salary'
            },
            'soc_code': {
                'regex': [r'soc.*code', r'occupation.*code'],
                'mapping': 'lca.soc_onet_oes_code'
            },
            'lca_number': {
                'regex': [r'lca.*number', r'eta.*case', r'lca.*case'],
                'mapping': 'lca.lcaNumber'
            }
        }
    }
}

# Form-specific field mapping rules
FORM_SPECIFIC_MAPPINGS = {
    'I-129': {
        'Part1_Item2': 'customer.customer_name',
        'Part1_Item3_InCareOf': 'customer.signatory_first_name + customer.signatory_last_name',
        'Part1_Item3_Street': 'customer.address_street',
        'Part1_Item3_City': 'customer.address_city',
        'Part1_Item3_State': 'customer.address_state',
        'Part1_Item3_Zip': 'customer.address_zip',
        'Part1_Item4_Phone': 'customer.signatory_work_phone',
        'Part1_Item4_Email': 'customer.signatory_email_id',
        'Part1_Item5_FEIN': 'customer.customer_tax_id',
        'Part1_Item6': 'customer.nonprofit_research_organization',
        'Part2_Item1': 'case.caseType',
        'Part2_Item2': 'case.caseSubType',
        'Part2_Item3': 'beneficiary.H1bDetails.H1b.h1bReceiptNumber',
        'Part3_Item2_LastName': 'beneficiary.Beneficiary.beneficiaryLastName',
        'Part3_Item2_FirstName': 'beneficiary.Beneficiary.beneficiaryFirstName',
        'Part3_Item5_DOB': 'beneficiary.Beneficiary.beneficiaryDateOfBirth',
        'Part3_Item5_Gender': 'beneficiary.Beneficiary.beneficiaryGender',
        'Part3_Item5_SSN': 'beneficiary.Beneficiary.beneficiarySsn',
        'Part3_Item5_AlienNumber': 'beneficiary.Beneficiary.alien_number',
        'Part3_Item6_I94': 'beneficiary.I94Details.I94.i94Number',
        'Part3_Item6_Passport': 'beneficiary.PassportDetails.Passport.passportNumber',
        'Part5_Item1': 'lca.position_job_title',
        'Part5_Item2': 'lca.lcaNumber',
        'Part5_Item9': 'lca.gross_salary'
    },
    
    'I-539': {
        'Part1_Item1a': 'beneficiary.Beneficiary.beneficiaryLastName',
        'Part1_Item1b': 'beneficiary.Beneficiary.beneficiaryFirstName',
        'Part1_Item1c': 'beneficiary.Beneficiary.beneficiaryMiddleName',
        'Part1_Item2': 'beneficiary.Beneficiary.alien_number',
        'Part1_Item4b_Street': 'beneficiary.WorkAddress.addressStreet',
        'Part1_Item4d_City': 'beneficiary.WorkAddress.addressCity',
        'Part1_Item4e_State': 'beneficiary.WorkAddress.addressState',
        'Part1_Item4f_Zip': 'beneficiary.WorkAddress.addressZip',
        'Part1_Item6': 'beneficiary.Beneficiary.beneficiaryCountryOfBirth',
        'Part1_Item7': 'beneficiary.Beneficiary.beneficiaryCitizenOfCountry',
        'Part1_Item8': 'beneficiary.Beneficiary.beneficiaryDateOfBirth',
        'Part1_Item9': 'beneficiary.Beneficiary.beneficiarySsn',
        'Part1_Item10': 'beneficiary.I94Details.I94.i94ArrivalDate',
        'Part1_Item11': 'beneficiary.I94Details.I94.i94Number',
        'Part1_Item12': 'beneficiary.PassportDetails.Passport.passportNumber',
        'Part1_Item15a': 'beneficiary.VisaDetails.Visa.visaStatus',
        'Part1_Item15b': 'beneficiary.VisaDetails.Visa.visaExpiryDate'
    },
    
    'I-140': {
        'Part1_Item2': 'customer.customer_name',
        'Part1_Item3a': 'customer.signatory_first_name + customer.signatory_last_name',
        'Part1_Item3b_Street': 'customer.address_street',
        'Part1_Item3d_City': 'customer.address_city',
        'Part1_Item3e_State': 'customer.address_state',
        'Part1_Item3f_Zip': 'customer.address_zip',
        'Part1_Item4_FEIN': 'customer.customer_tax_id',
        'Part3_Item1a': 'beneficiary.Beneficiary.beneficiaryLastName',
        'Part3_Item1b': 'beneficiary.Beneficiary.beneficiaryFirstName',
        'Part3_Item1c': 'beneficiary.Beneficiary.beneficiaryMiddleName',
        'Part3_Item3': 'beneficiary.Beneficiary.beneficiaryDateOfBirth',
        'Part3_Item6': 'beneficiary.Beneficiary.beneficiaryCountryOfBirth',
        'Part3_Item7': 'beneficiary.Beneficiary.beneficiaryCitizenOfCountry',
        'Part3_Item8': 'beneficiary.Beneficiary.alien_number',
        'Part3_Item9': 'beneficiary.Beneficiary.beneficiarySsn'
    },
    
    'G-28': {
        'Part1_Item2a': 'attorney.attorneyInfo.lastName',
        'Part1_Item2b': 'attorney.attorneyInfo.firstName',
        'Part1_Item3a': 'attorney.address.addressStreet',
        'Part1_Item3c': 'attorney.address.addressCity',
        'Part1_Item3d': 'attorney.address.addressState',
        'Part1_Item3e': 'attorney.address.addressZip',
        'Part1_Item4': 'attorney.attorneyInfo.workPhone',
        'Part1_Item6': 'attorney.attorneyInfo.emailAddress',
        'Part2_Item1b': 'attorney.attorneyInfo.stateBarNumber',
        'Part2_Item1d': 'attorneyLawfirmDetails.lawfirmDetails.lawFirmName'
    }
}

# Enhanced CSS with improved styling
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
        'field_detection_confidence': {}
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
                        field_info = analyze_field_name(field_name, extracted_text, form_type)
                        
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
                            'confidence': field_info['confidence']
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
                            for form_key, form_info in USCIS_FORMS_DATABASE.items():
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
        text_fields = extract_fields_from_text_enhanced(extracted_text, form_type)
        fields.extend(text_fields)
        processing_log.append(f"Found {len(text_fields)} additional fields from text")
    
    # Organize fields by parts
    form_parts = organize_fields_by_parts_enhanced(fields, form_type)
    
    return fields, form_parts

def analyze_field_name(field_name: str, text: str, form_type: Optional[str]) -> Dict[str, Any]:
    """Enhanced field analysis with intelligent mapping suggestions"""
    result = {
        'part': 'Unassigned Fields',
        'suggested_mapping': None,
        'confidence': 0.0
    }
    
    field_lower = field_name.lower()
    
    # Check if it's an attorney/preparer field
    attorney_keywords = ['attorney', 'preparer', 'representative', 'declaration', 'g-28']
    if any(keyword in field_lower for keyword in attorney_keywords):
        result['part'] = 'Part 0 - Attorney/Preparer Information'
        result['suggested_mapping'], result['confidence'] = suggest_mapping_enhanced(field_name, 'attorney')
        return result
    
    # Try to extract part number from field name
    part_match = re.search(r'(?:part|p)[\s_\-]*(\d+)', field_lower)
    if part_match:
        part_num = part_match.group(1)
        if form_type and form_type in USCIS_FORMS_DATABASE:
            parts = USCIS_FORMS_DATABASE[form_type]['parts']
            part_key = f'Part {part_num}'
            if part_key in parts:
                result['part'] = f'{part_key} - {parts[part_key]}'
    
    # Check form-specific mappings
    if form_type and form_type in FORM_SPECIFIC_MAPPINGS:
        for field_key, mapping in FORM_SPECIFIC_MAPPINGS[form_type].items():
            if field_key.lower() in field_lower or field_lower in field_key.lower():
                result['suggested_mapping'] = mapping
                result['confidence'] = 0.9
                return result
    
    # Use pattern matching for suggestions
    if not result['suggested_mapping']:
        result['suggested_mapping'], result['confidence'] = suggest_mapping_enhanced(field_name)
    
    return result

def suggest_mapping_enhanced(field_name: str, category: str = None) -> Tuple[Optional[str], float]:
    """Enhanced mapping suggestion with confidence scoring"""
    field_lower = field_name.lower()
    field_clean = re.sub(r'[^\w\s]', ' ', field_lower).strip()
    
    best_match = None
    best_confidence = 0.0
    
    # Check specific category if provided
    categories_to_check = [category] if category else USCIS_MAPPING_PATTERNS.keys()
    
    for cat in categories_to_check:
        if cat not in USCIS_MAPPING_PATTERNS:
            continue
            
        category_patterns = USCIS_MAPPING_PATTERNS[cat]['patterns']
        
        for field_type, field_info in category_patterns.items():
            for pattern in field_info['regex']:
                match = re.search(pattern, field_clean)
                if match:
                    # Calculate confidence based on match quality
                    match_length = len(match.group(0))
                    field_length = len(field_clean)
                    confidence = match_length / field_length if field_length > 0 else 0
                    
                    # Boost confidence for exact matches
                    if match.group(0) == field_clean:
                        confidence = 1.0
                    
                    # Boost confidence for specific patterns
                    if any(keyword in field_clean for keyword in ['item', 'part', 'section']):
                        confidence *= 1.2
                    
                    confidence = min(confidence, 1.0)
                    
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_match = field_info['mapping']
    
    return best_match, best_confidence

def extract_fields_from_text_enhanced(text: str, form_type: Optional[str]) -> List[Dict[str, Any]]:
    """Enhanced field extraction from text using USCIS-specific patterns"""
    fields = []
    seen_fields = set()
    
    # Enhanced USCIS-specific field patterns
    patterns = [
        # Part-based patterns (I-129 style)
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
        (r'\(\s*\)\s*([A-Za-z][A-Za-z\s\-]{2,50})', 'radio'),
        # Field with underscores
        (r'([A-Za-z][A-Za-z\s\-]{2,50})[\s]*:?[\s]*_{3,}', 'text_field'),
        # Field with parentheses instructions
        (r'([A-Za-z][A-Za-z\s\-]{2,50})\s*\([^)]+\)', 'field_with_instruction')
    ]
    
    for pattern, pattern_type in patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            field_name = create_field_name_enhanced(match, pattern_type, form_type)
            
            if field_name and field_name.lower() not in seen_fields:
                seen_fields.add(field_name.lower())
                
                # Enhanced field analysis
                field_info = analyze_field_name(field_name, text, form_type)
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
                    'confidence': field_info['confidence']
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
            return f"{form_type}_Part{part}_Item{item}{sub}_{desc_clean}"
        return f"Part{part}_Item{item}{sub}_{desc_clean}"
    
    elif pattern_type == 'uscis_section':
        section = match.group(1)
        item = match.group(2)
        sub = match.group(3) or ''
        desc = match.group(4).strip()
        desc_clean = re.sub(r'[^\w]', '_', desc)[:40]
        return f"Section{section}_Item{item}{sub}_{desc_clean}"
    
    elif pattern_type == 'uscis_item':
        item = match.group(1)
        sub = match.group(2) or ''
        desc = match.group(3).strip()
        desc_clean = re.sub(r'[^\w]', '_', desc)[:40]
        return f"Item{item}{sub}_{desc_clean}"
    
    elif pattern_type == 'question':
        num = match.group(1)
        sub = match.group(2) or ''
        desc = match.group(3).strip()
        desc_clean = re.sub(r'[^\w]', '_', desc)[:40]
        return f"Q{num}{sub}_{desc_clean}"
    
    else:
        # Generic field name
        field_text = match.group(1).strip()
        return re.sub(r'\s+', '_', field_text)

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
        return 'Phone'
    elif any(word in field_lower for word in ['email', 'e-mail']):
        return 'Email'
    elif any(word in field_lower for word in ['number', 'count', 'total']):
        return 'Number'
    
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
    
    # Always add attorney section first
    form_parts['Part 0 - Attorney/Preparer Information'] = []
    
    # Add known parts for the form type
    if form_type and form_type in USCIS_FORMS_DATABASE:
        for part_key, part_desc in USCIS_FORMS_DATABASE[form_type]['parts'].items():
            form_parts[f'{part_key} - {part_desc}'] = []
    
    # Add unassigned section
    form_parts['Unassigned Fields'] = []
    
    # Organize fields into parts with confidence tracking
    for field in fields:
        part = field.get('part', 'Unassigned Fields')
        
        # Ensure part exists
        if part not in form_parts:
            form_parts[part] = []
        
        # Store confidence and suggestion
        if field.get('suggested_mapping'):
            st.session_state.mapping_suggestions[field['name']] = {
                'mapping': field['suggested_mapping'],
                'confidence': field.get('confidence', 0.0)
            }
        
        form_parts[part].append(field)
    
    # Remove empty parts except Part 0 and Unassigned
    parts_to_keep = OrderedDict()
    for part_name, part_fields in form_parts.items():
        if part_fields or part_name in ['Part 0 - Attorney/Preparer Information', 'Unassigned Fields']:
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
            render_field_row_enhanced(field, f"{part_index}_{field_idx}")
        
        # Add some spacing
        st.markdown("<br>", unsafe_allow_html=True)

def render_field_row_enhanced(field: Dict, unique_key: str):
    """Enhanced field row rendering with confidence display"""
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
                st.rerun()
    
    with col3:
        if is_mapped:
            if st.button("❌", key=f"unmap_{unique_key}", help="Remove mapping"):
                del st.session_state.mapped_fields[field_name]
                st.rerun()
        else:
            if st.button("✓", key=f"map_{unique_key}", help="Quick map with suggestion"):
                if field_name in st.session_state.mapping_suggestions:
                    suggested = st.session_state.mapping_suggestions[field_name]['mapping']
                    st.session_state.mapped_fields[field_name] = f"{suggested}:{field_type}"
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
        if word.upper() in ['SSN', 'DOB', 'EIN', 'FEIN', 'LCA', 'US', 'USA']:
            capitalized.append(word.upper())
        else:
            capitalized.append(word.capitalize())
    return ' '.join(capitalized).strip()

def auto_map_part_fields(part_fields: List[Dict]):
    """Auto-map all unmapped fields in a part with enhanced intelligence"""
    for field in part_fields:
        field_name = field['name']
        if (field_name not in st.session_state.mapped_fields and 
            field_name not in st.session_state.questionnaire_fields and
            field_name not in st.session_state.removed_fields):
            
            # Check if we have a suggestion with high confidence
            if field_name in st.session_state.mapping_suggestions:
                suggestion_info = st.session_state.mapping_suggestions[field_name]
                if suggestion_info['confidence'] > 0.5:  # Only auto-map if confidence > 50%
                    st.session_state.mapped_fields[field_name] = f"{suggestion_info['mapping']}:{field['type']}"

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
            field_type = st.selectbox("Type", ["TextBox", "CheckBox", "RadioButton", "Date", "DropDown", "TextArea", "Signature", "Currency", "Phone", "Email"])
        
        with col3:
            is_required = st.checkbox("Required")
        
        with col4:
            if st.button("Add", type="primary"):
                if field_name:
                    # Analyze the new field
                    field_info = analyze_field_name(field_name, "", st.session_state.form_type)
                    
                    new_field = {
                        'name': field_name,
                        'type': field_type,
                        'value': '',
                        'required': is_required,
                        'page': 0,
                        'part': part_name,
                        'source': 'manual',
                        'suggested_mapping': field_info['suggested_mapping'],
                        'confidence': field_info['confidence']
                    }
                    st.session_state.pdf_fields.append(new_field)
                    
                    # Add to the part
                    if part_name in st.session_state.form_parts:
                        st.session_state.form_parts[part_name].append(new_field)
                    
                    # Add suggestion if found
                    if field_info['suggested_mapping']:
                        st.session_state.mapping_suggestions[field_name] = {
                            'mapping': field_info['suggested_mapping'],
                            'confidence': field_info['confidence']
                        }
                    
                    st.rerun()

def auto_map_all_fields():
    """Enhanced auto-mapping with intelligent detection"""
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
                    'options': 'Yes\nNo' if field['type'] == 'CheckBox' else '',
                    'validation': '',
                    'style': {"col": "12"}
                }
                mapped_count += 1
            else:
                # Try to map with confidence threshold
                if field_name in st.session_state.mapping_suggestions:
                    suggestion_info = st.session_state.mapping_suggestions[field_name]
                    if suggestion_info['confidence'] > 0.3:  # Lower threshold for auto-map all
                        st.session_state.mapped_fields[field_name] = f"{suggestion_info['mapping']}:{field['type']}"
                        mapped_count += 1
    
    return mapped_count

def generate_typescript_enhanced() -> str:
    """Generate enhanced TypeScript configuration for USCIS forms"""
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
        elif mapping_path.startswith('lca'):
            categories['lcaData'][field_name] = f"{mapping_path}:{field_type}"
        else:
            categories['otherData'][field_name] = f"{mapping_path}:{field_type}"
    
    # Format questionnaire
    questionnaire_data = {}
    for field_name, config in st.session_state.questionnaire_fields.items():
        questionnaire_data[field_name] = {
            'type': config['type'],
            'label': config['label'],
            'required': config.get('required', False),
            'options': config.get('options', '').split('\n') if config.get('options') else []
        }
    
    # Generate TypeScript with interfaces
    ts_content = f"""// Auto-generated USCIS form configuration
// Form: {form_name} ({st.session_state.form_type or 'Unknown'})
// Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

interface FormField {{
    mapping: string;
    type: string;
}}

interface QuestionnaireField {{
    type: string;
    label: string;
    required: boolean;
    options?: string[];
}}

interface USCISFormConfig {{
    formname: string;
    formType: string;
    customerData: {{ [key: string]: string }} | null;
    beneficiaryData: {{ [key: string]: string }} | null;
    attorneyData: {{ [key: string]: string }} | null;
    lcaData: {{ [key: string]: string }} | null;
    otherData: {{ [key: string]: string }} | null;
    questionnaireData: {{ [key: string]: QuestionnaireField }};
    formStructure: {{ [part: string]: string[] }};
    metadata: {{
        totalFields: number;
        mappedFields: number;
        questionnaireFields: number;
        extractedFrom: string;
        mappingConfidence: {{ [field: string]: number }};
    }};
}}

export const {form_name_clean}: USCISFormConfig = {{
    formname: "{form_name_clean}",
    formType: "{st.session_state.form_type or 'Unknown'}",
    customerData: {json.dumps(categories.get('customerData', {}), indent=8) if categories.get('customerData') else 'null'},
    beneficiaryData: {json.dumps(categories.get('beneficiaryData', {}), indent=8) if categories.get('beneficiaryData') else 'null'},
    attorneyData: {json.dumps(categories.get('attorneyData', {}), indent=8) if categories.get('attorneyData') else 'null'},
    lcaData: {json.dumps(categories.get('lcaData', {}), indent=8) if categories.get('lcaData') else 'null'},
    otherData: {json.dumps(categories.get('otherData', {}), indent=8) if categories.get('otherData') else 'null'},
    questionnaireData: {json.dumps(questionnaire_data, indent=8)},
    formStructure: {{
{format_form_structure()}
    }},
    metadata: {{
        totalFields: {len(st.session_state.pdf_fields)},
        mappedFields: {len(st.session_state.mapped_fields)},
        questionnaireFields: {len(st.session_state.questionnaire_fields)},
        extractedFrom: "{st.session_state.form_type or 'Unknown USCIS Form'}",
        mappingConfidence: {json.dumps(get_mapping_confidence(), indent=12)}
    }}
}};

export default {form_name_clean};"""
    
    return ts_content

def format_form_structure() -> str:
    """Format form structure for TypeScript export"""
    structure_lines = []
    for part_name, fields in st.session_state.form_parts.items():
        field_names = [f['name'] for f in fields if f['name'] not in st.session_state.removed_fields]
        structure_lines.append(f'        "{part_name}": {json.dumps(field_names)}')
    return ',\n'.join(structure_lines)

def get_mapping_confidence() -> Dict[str, float]:
    """Get mapping confidence scores"""
    confidence_scores = {}
    for field_name, suggestion_info in st.session_state.mapping_suggestions.items():
        if field_name in st.session_state.mapped_fields:
            confidence_scores[field_name] = suggestion_info['confidence']
    return confidence_scores

def generate_json_enhanced() -> str:
    """Generate enhanced JSON configuration for USCIS forms"""
    config = {
        "formName": st.session_state.form_name or "USCISForm",
        "formType": st.session_state.form_type,
        "formDatabase": USCIS_FORMS_DATABASE.get(st.session_state.form_type, {}),
        "mappedFields": st.session_state.mapped_fields,
        "questionnaireFields": st.session_state.questionnaire_fields,
        "formStructure": {
            part_name: [f['name'] for f in fields if f['name'] not in st.session_state.removed_fields]
            for part_name, fields in st.session_state.form_parts.items()
        },
        "mappingSuggestions": st.session_state.mapping_suggestions,
        "metadata": {
            "totalFields": len(st.session_state.pdf_fields),
            "mappedFields": len(st.session_state.mapped_fields),
            "questionnaireFields": len(st.session_state.questionnaire_fields),
            "removedFields": len(st.session_state.removed_fields),
            "timestamp": datetime.now().isoformat(),
            "extractionMethod": st.session_state.processing_log[-1] if st.session_state.processing_log else "Unknown"
        }
    }
    
    return json.dumps(config, indent=2)

# Main Application
def main():
    st.title("🏛️ USCIS PDF Form Automation System")
    st.markdown("Extract and intelligently map fields from USCIS immigration forms")
    
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
                        'style': {"col": "12"}
                    }
                    count += 1
            st.success(f"Moved {count} fields to questionnaire!")
            st.rerun()
        
        if st.button("🔄 Reset All", use_container_width=True):
            init_session_state()
            st.rerun()
    
    # Main content
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📤 Upload & Process",
        "🗂️ Field Mapping",
        "❓ Questionnaire",
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
        
        # Show extracted text preview
        if st.session_state.extracted_text:
            with st.expander("📄 Extracted Text Preview"):
                st.text_area("Text", st.session_state.extracted_text[:2000] + "...", height=200)
    
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
                form_specific = sum(1 for f in st.session_state.mapped_fields.values() 
                                  if any(db_field in f for db_field in ['customer', 'beneficiary', 'lca', 'attorney']))
                st.info(f"🔗 {form_specific} database mappings")
            
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
                        
                        # Add validation rules
                        if config['type'] == 'text':
                            config['validation'] = st.text_input(
                                "Validation pattern (regex)",
                                value=config.get('validation', ''),
                                placeholder="e.g., ^[A-Za-z]+$",
                                key=f"q_val_{field_key}"
                            )
                    
                    with col2:
                        if st.button("🗑️", key=f"q_del_{field_key}"):
                            del st.session_state.questionnaire_fields[field_key]
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
                st.subheader("📄 TypeScript Export")
                if st.button("Generate TypeScript", type="primary", use_container_width=True):
                    ts_content = generate_typescript_enhanced()
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
                    json_content = generate_json_enhanced()
                    st.download_button(
                        "📥 Download JSON",
                        data=json_content,
                        file_name=f"{st.session_state.form_name or 'USCIS_Form'}.json",
                        mime="application/json"
                    )
                    with st.expander("Preview"):
                        st.code(json_content, language="json")
            
            # Additional export options
            st.subheader("🔧 Advanced Export Options")
            col1, col2 = st.columns(2)
            
            with col1:
                if st.checkbox("Include unmapped fields in export"):
                    st.info("Unmapped fields will be included with null mappings")
                
                if st.checkbox("Include field metadata"):
                    st.info("Field types, requirements, and confidence scores will be included")
            
            with col2:
                export_format = st.selectbox(
                    "Export format",
                    ["Standard", "Compact", "Detailed"],
                    help="Choose the level of detail in the export"
                )
                
                if st.button("📊 Export Mapping Report"):
                    # Generate detailed mapping report
                    report = generate_mapping_report()
                    st.download_button(
                        "📥 Download Report",
                        data=report,
                        file_name=f"{st.session_state.form_name or 'USCIS_Form'}_mapping_report.md",
                        mime="text/markdown"
                    )
    
    # Tab 5: Analysis
    with tab5:
        st.header("Form Analysis & Insights")
        
        if st.session_state.pdf_fields:
            # Field type distribution
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📊 Field Type Distribution")
                field_types = defaultdict(int)
                for field in st.session_state.pdf_fields:
                    field_types[field['type']] += 1
                
                # Create a simple bar chart representation
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
                'Customer Data': 0,
                'Beneficiary Data': 0,
                'Attorney Data': 0,
                'LCA Data': 0,
                'Other Data': 0
            }
            
            for mapping in st.session_state.mapped_fields.values():
                if 'customer' in mapping:
                    db_coverage['Customer Data'] += 1
                elif 'beneficiary' in mapping:
                    db_coverage['Beneficiary Data'] += 1
                elif 'attorney' in mapping:
                    db_coverage['Attorney Data'] += 1
                elif 'lca' in mapping:
                    db_coverage['LCA Data'] += 1
                else:
                    db_coverage['Other Data'] += 1
            
            cols = st.columns(len(db_coverage))
            for idx, (category, count) in enumerate(db_coverage.items()):
                with cols[idx]:
                    st.metric(category, count)
            
            # Required fields analysis
            st.subheader("⚠️ Required Fields Analysis")
            required_fields = [f for f in st.session_state.pdf_fields if f.get('required')]
            required_mapped = sum(1 for f in required_fields if f['name'] in st.session_state.mapped_fields)
            required_questionnaire = sum(1 for f in required_fields if f['name'] in st.session_state.questionnaire_fields)
            required_unmapped = len(required_fields) - required_mapped - required_questionnaire
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Required", len(required_fields))
            with col2:
                st.metric("Mapped", required_mapped)
            with col3:
                st.metric("Unmapped", required_unmapped)
            
            if required_unmapped > 0:
                st.warning(f"⚠️ {required_unmapped} required fields are not mapped!")
                with st.expander("Show unmapped required fields"):
                    for field in required_fields:
                        if (field['name'] not in st.session_state.mapped_fields and 
                            field['name'] not in st.session_state.questionnaire_fields):
                            st.write(f"- {field['name']} ({field['type']})")

def generate_mapping_report() -> str:
    """Generate a detailed mapping report"""
    report = f"""# USCIS Form Mapping Report

## Form Information
- **Form Type**: {st.session_state.form_type or 'Unknown'}
- **Form Name**: {st.session_state.form_name or 'Unknown'}
- **Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Summary Statistics
- **Total Fields**: {len(st.session_state.pdf_fields)}
- **Mapped Fields**: {len(st.session_state.mapped_fields)}
- **Questionnaire Fields**: {len(st.session_state.questionnaire_fields)}
- **Removed Fields**: {len(st.session_state.removed_fields)}
- **Unmapped Fields**: {len(st.session_state.pdf_fields) - len(st.session_state.mapped_fields) - len(st.session_state.questionnaire_fields) - len(st.session_state.removed_fields)}

## Field Mappings by Part

"""
    
    for part_name, part_fields in st.session_state.form_parts.items():
        report += f"### {part_name}\n\n"
        
        if part_fields:
            report += "| Field Name | Type | Status | Mapping | Confidence |\n"
            report += "|------------|------|--------|---------|------------|\n"
            
            for field in part_fields:
                field_name = field['name']
                field_type = field['type']
                
                if field_name in st.session_state.mapped_fields:
                    status = "Mapped"
                    mapping = st.session_state.mapped_fields[field_name].split(':')[0]
                elif field_name in st.session_state.questionnaire_fields:
                    status = "Questionnaire"
                    mapping = "N/A"
                elif field_name in st.session_state.removed_fields:
                    status = "Removed"
                    mapping = "N/A"
                else:
                    status = "Unmapped"
                    mapping = st.session_state.mapping_suggestions.get(field_name, {}).get('mapping', 'No suggestion')
                
                confidence = ""
                if field_name in st.session_state.mapping_suggestions:
                    conf = st.session_state.mapping_suggestions[field_name]['confidence']
                    confidence = f"{conf:.0%}"
                
                report += f"| {field_name} | {field_type} | {status} | {mapping} | {confidence} |\n"
        else:
            report += "_No fields in this part_\n"
        
        report += "\n"
    
    # Add questionnaire configuration
    if st.session_state.questionnaire_fields:
        report += "## Questionnaire Configuration\n\n"
        for field_key, config in st.session_state.questionnaire_fields.items():
            report += f"- **{config['label']}**\n"
            report += f"  - Type: {config['type']}\n"
            report += f"  - Required: {config.get('required', False)}\n"
            if config.get('options'):
                report += f"  - Options: {config['options'].replace(chr(10), ', ')}\n"
            report += "\n"
    
    return report

# Run the application
if __name__ == "__main__":
    main()
