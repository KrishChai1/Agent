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
    page_title="USCIS PDF Form Field Extractor & Mapper",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Enhanced USCIS Form Database with exact field mappings
USCIS_FORMS_DATABASE = {
    'I-129': {
        'title': 'Petition for a Nonimmigrant Worker',
        'patterns': [r'Form\s*I-129', r'Petition.*Nonimmigrant.*Worker'],
        'parts': OrderedDict([
            ('Part 1', {
                'title': 'Petitioner Information',
                'fields': {
                    'Part1_Item1_LegalName': 'customer.customer_name',
                    'Part1_Item2_TradeName': 'customer.trade_name',
                    'Part1_Item3_InCareOf': 'customer.signatory_name',
                    'Part1_Item3a_StreetNumber': 'customer.address_street',
                    'Part1_Item3b_AptSteFlr': 'customer.address_apt',
                    'Part1_Item3c_CityOrTown': 'customer.address_city',
                    'Part1_Item3d_State': 'customer.address_state',
                    'Part1_Item3e_ZipCode': 'customer.address_zip',
                    'Part1_Item4_Country': 'customer.address_country',
                    'Part1_Item5_Province': 'customer.address_province',
                    'Part1_Item6_PostalCode': 'customer.foreign_postal_code',
                    'Part1_Item7_Telephone': 'customer.signatory_work_phone',
                    'Part1_Item8_Email': 'customer.signatory_email_id',
                    'Part1_Item9_FEIN': 'customer.customer_tax_id'
                }
            }),
            ('Part 2', {
                'title': 'Information About This Petition',
                'fields': {
                    'Part2_Item1_Classification': 'case.caseType',
                    'Part2_Item2_Basis': 'case.caseSubType',
                    'Part2_Item3_RequestedAction': 'case.requestedAction'
                }
            }),
            ('Part 3', {
                'title': 'Beneficiary Information',
                'fields': {
                    'Part3_Item1a_FamilyName': 'beneficiary.Beneficiary.beneficiaryLastName',
                    'Part3_Item1b_GivenName': 'beneficiary.Beneficiary.beneficiaryFirstName',
                    'Part3_Item1c_MiddleName': 'beneficiary.Beneficiary.beneficiaryMiddleName',
                    'Part3_Item2_AlienNumber': 'beneficiary.Beneficiary.alien_number',
                    'Part3_Item3_DOB': 'beneficiary.Beneficiary.beneficiaryDateOfBirth',
                    'Part3_Item4_CountryOfBirth': 'beneficiary.Beneficiary.beneficiaryCountryOfBirth',
                    'Part3_Item5_CountryOfCitizenship': 'beneficiary.Beneficiary.beneficiaryCitizenOfCountry',
                    'Part3_Item6_SSN': 'beneficiary.Beneficiary.beneficiarySsn',
                    'Part3_Item7_Gender': 'beneficiary.Beneficiary.beneficiaryGender',
                    'Part3_Item8_I94Number': 'beneficiary.I94Details.I94.i94Number',
                    'Part3_Item9_PassportNumber': 'beneficiary.PassportDetails.Passport.passportNumber',
                    'Part3_Item10_CurrentStatus': 'beneficiary.VisaDetails.Visa.visaStatus'
                }
            }),
            ('Part 4', {
                'title': 'Processing Information',
                'fields': {
                    'Part4_Item1_Priority': 'case.processingPriority',
                    'Part4_Item2_Office': 'case.processingOffice'
                }
            }),
            ('Part 5', {
                'title': 'Basic Information About the Proposed Employment and Employer',
                'fields': {
                    'Part5_Item1_JobTitle': 'lca.Lca.position_job_title',
                    'Part5_Item2_LCANumber': 'lca.Lca.lcaNumber',
                    'Part5_Item3_NAICS': 'lca.Lca.naics_code',
                    'Part5_Item4_Wages': 'lca.Lca.gross_salary',
                    'Part5_Item5_FromDate': 'lca.Lca.start_date',
                    'Part5_Item6_ToDate': 'lca.Lca.end_date'
                }
            })
        ])
    },
    'G-28': {
        'title': 'Notice of Entry of Appearance as Attorney or Accredited Representative',
        'patterns': [r'Form\s*G-28', r'Notice.*Entry.*Appearance'],
        'parts': OrderedDict([
            ('Part 1', {
                'title': 'Information About Attorney or Representative',
                'fields': {
                    'Pt1Line1a_FamilyName': 'attorney.attorneyInfo.lastName',
                    'Pt1Line1b_GivenName': 'attorney.attorneyInfo.firstName',
                    'Pt1Line1c_MiddleName': 'attorney.attorneyInfo.middleName',
                    'Pt1Line2_StreetNumberName': 'attorney.attorneyInfo.address_street',
                    'Pt1Line2_AptSteFlr': 'attorney.attorneyInfo.address_apt',
                    'Pt1Line2_CityOrTown': 'attorney.attorneyInfo.address_city',
                    'Pt1Line2_State': 'attorney.attorneyInfo.address_state',
                    'Pt1Line2_ZipCode': 'attorney.attorneyInfo.address_zip',
                    'Pt1Line3_DaytimePhone': 'attorney.attorneyInfo.workPhone',
                    'Pt1Line4_MobilePhone': 'attorney.attorneyInfo.mobilePhone',
                    'Pt1Line5_Email': 'attorney.attorneyInfo.emailAddress',
                    'Pt1Line6_FaxNumber': 'attorney.attorneyInfo.faxNumber'
                }
            }),
            ('Part 2', {
                'title': 'Eligibility Information',
                'fields': {
                    'Pt2Line1a_AttorneyBarNumber': 'attorney.attorneyInfo.stateBarNumber',
                    'Pt2Line1b_AttorneyUSCISNumber': 'attorney.attorneyInfo.uscisNumber',
                    'Pt2Line2_LawFirmName': 'attorneyLawfirmDetails.lawfirmDetails.lawFirmName',
                    'Pt2Line3_FirmEIN': 'attorneyLawfirmDetails.lawfirmDetails.firmEIN'
                }
            })
        ])
    },
    'I-140': {
        'title': 'Immigrant Petition for Alien Worker',
        'patterns': [r'Form\s*I-140', r'Immigrant.*Petition.*Worker'],
        'parts': OrderedDict([
            ('Part 1', {
                'title': 'Information About the Petitioner',
                'fields': {
                    'Part1_Item1_PetitionerName': 'customer.customer_name',
                    'Part1_Item2_StreetNumber': 'customer.address_street',
                    'Part1_Item2_City': 'customer.address_city',
                    'Part1_Item2_State': 'customer.address_state',
                    'Part1_Item2_ZipCode': 'customer.address_zip',
                    'Part1_Item3_MailingAddress': 'customer.mailing_address',
                    'Part1_Item4_FEIN': 'customer.customer_tax_id',
                    'Part1_Item5_Phone': 'customer.signatory_work_phone',
                    'Part1_Item6_Email': 'customer.signatory_email_id',
                    'Part1_Item7_ContactPerson': 'customer.signatory_name'
                }
            }),
            ('Part 2', {
                'title': 'Petition Type',
                'fields': {
                    'Part2_Item1_Classification': 'case.caseType',
                    'Part2_Item2_Category': 'case.caseSubType'
                }
            }),
            ('Part 3', {
                'title': 'Information About the Person You Are Filing For',
                'fields': {
                    'Part3_Item1a_FamilyName': 'beneficiary.Beneficiary.beneficiaryLastName',
                    'Part3_Item1b_GivenName': 'beneficiary.Beneficiary.beneficiaryFirstName',
                    'Part3_Item1c_MiddleName': 'beneficiary.Beneficiary.beneficiaryMiddleName',
                    'Part3_Item2_OtherNames': 'beneficiary.Beneficiary.otherNames',
                    'Part3_Item3_DOB': 'beneficiary.Beneficiary.beneficiaryDateOfBirth',
                    'Part3_Item4_CityOfBirth': 'beneficiary.Beneficiary.cityOfBirth',
                    'Part3_Item5_StateOfBirth': 'beneficiary.Beneficiary.stateOfBirth',
                    'Part3_Item6_CountryOfBirth': 'beneficiary.Beneficiary.beneficiaryCountryOfBirth',
                    'Part3_Item7_Gender': 'beneficiary.Beneficiary.beneficiaryGender',
                    'Part3_Item8_AlienNumber': 'beneficiary.Beneficiary.alien_number',
                    'Part3_Item9_SSN': 'beneficiary.Beneficiary.beneficiarySsn',
                    'Part3_Item10_I94Number': 'beneficiary.I94Details.I94.i94Number'
                }
            })
        ])
    }
}

# Field type detection patterns - Enhanced
FIELD_TYPE_PATTERNS = {
    'CheckBox': [
        r'\[\s*\]',
        r'\(\s*\)',
        r'check.*box',
        r'select.*one',
        r'mark.*x',
        r'Yes.*No',
        r'Choice\d+'
    ],
    'RadioButton': [
        r'\(\s*\)',
        r'select.*only.*one',
        r'choose.*one',
        r'option\d+'
    ],
    'Date': [
        r'date',
        r'mm[/\-]dd[/\-]yyyy',
        r'dob',
        r'birth.*date',
        r'expire',
        r'from.*date',
        r'to.*date'
    ],
    'Signature': [
        r'signature',
        r'sign.*here',
        r'petitioner.*signature',
        r'preparer.*signature'
    ],
    'Currency': [
        r'amount',
        r'fee',
        r'wage',
        r'salary',
        r'\$',
        r'compensation',
        r'rate.*pay'
    ],
    'Phone': [
        r'phone',
        r'telephone',
        r'fax',
        r'mobile',
        r'daytime.*phone'
    ],
    'Email': [
        r'email',
        r'e-mail',
        r'electronic.*mail'
    ],
    'TextArea': [
        r'describe',
        r'explain',
        r'additional.*information',
        r'details',
        r'comments'
    ],
    'Number': [
        r'number',
        r'count',
        r'total',
        r'#',
        r'ein',
        r'fein',
        r'ssn',
        r'alien.*number',
        r'receipt.*number'
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
    
    /* Field Display */
    .field-display {
        background: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 4px;
        padding: 12px;
        margin: 8px 0;
        font-family: monospace;
    }
    
    .field-raw {
        color: #6c757d;
        font-size: 0.875rem;
    }
    
    .field-clean {
        color: #212529;
        font-weight: 600;
    }
    
    .field-mapping {
        color: #0066cc;
        background: #e7f3ff;
        padding: 4px 8px;
        border-radius: 4px;
        display: inline-block;
        margin-top: 4px;
    }
    
    .confidence-high {
        background: #d4edda;
        color: #155724;
    }
    
    .confidence-medium {
        background: #fff3cd;
        color: #856404;
    }
    
    .confidence-low {
        background: #f8d7da;
        color: #721c24;
    }
    
    /* Part Header */
    .part-header {
        background: var(--uscis-blue);
        color: white;
        padding: 12px 20px;
        border-radius: 4px;
        margin: 16px 0 8px 0;
        font-weight: 600;
    }
    
    /* Field Analysis Box */
    .field-analysis {
        background: white;
        border: 2px solid var(--border-gray);
        border-radius: 8px;
        padding: 16px;
        margin: 16px 0;
    }
    
    /* Debug Information */
    .debug-info {
        background: #f8f9fa;
        border-left: 4px solid #6c757d;
        padding: 12px;
        margin: 8px 0;
        font-size: 0.875rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
def init_session_state():
    """Initialize session state with enhanced structure"""
    defaults = {
        'pdf_fields': [],
        'raw_fields': [],  # Store raw field data
        'field_analysis': {},  # Detailed field analysis
        'form_parts': OrderedDict(),
        'mapped_fields': {},
        'questionnaire_fields': {},
        'form_metadata': {},
        'extracted_text': "",
        'form_name': '',
        'form_type': None,
        'show_raw_fields': True,
        'show_field_analysis': True,
        'removed_fields': [],
        'processing_log': [],
        'mapping_confidence': {},
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

# Enhanced field extraction and analysis
def analyze_field_name(raw_field_name: str) -> Dict[str, Any]:
    """Analyze a field name and extract all components"""
    analysis = {
        'raw_name': raw_field_name,
        'form_prefix': None,
        'part': None,
        'item': None,
        'field_description': None,
        'field_type': 'TextBox',
        'cleaned_name': raw_field_name,
        'hierarchical_path': [],
        'confidence': 0.0,
        'suggested_mapping': None
    }
    
    # Common patterns for USCIS forms
    patterns = {
        # form[0].#subform[0].Pt1Line1a_FamilyName[0]
        'g28_pattern': r'form\[\d+\]\.#?subform\[\d+\]\.(Pt(\d+)Line(\d+[a-z]?)(?:_(.+?))?)\[\d+\]',
        # topmostSubform[0].Page1[0].Part1_Item2_CompanyName[0]
        'i129_pattern': r'topmostSubform\[\d+\]\.Page\d+\[\d+\]\.(Part(\d+)_Item(\d+[a-z]?)(?:_(.+?))?)\[\d+\]',
        # Form1[0].Page1[0].Part1_1a_LastName[0]
        'generic_pattern': r'Form\d*\[\d+\]\.Page\d+\[\d+\]\.(Part(\d+)_(\d+[a-z]?)(?:_(.+?))?)\[\d+\]',
        # Simple: Part1_Item2_CompanyName
        'simple_pattern': r'(Part|Pt)(\d+)[\._](?:Item|Line)?(\d+[a-z]?)(?:[\._](.+))?$'
    }
    
    # Try each pattern
    for pattern_name, pattern in patterns.items():
        match = re.search(pattern, raw_field_name, re.IGNORECASE)
        if match:
            groups = match.groups()
            
            if pattern_name == 'g28_pattern':
                analysis['form_prefix'] = 'G-28'
                analysis['cleaned_name'] = groups[0]
                analysis['part'] = f"Part {groups[1]}"
                analysis['item'] = f"Line {groups[2]}"
                analysis['field_description'] = groups[3] if len(groups) > 3 else None
                
            elif pattern_name == 'i129_pattern':
                analysis['form_prefix'] = 'I-129'
                analysis['cleaned_name'] = groups[0]
                analysis['part'] = f"Part {groups[1]}"
                analysis['item'] = f"Item {groups[2]}"
                analysis['field_description'] = groups[3] if len(groups) > 3 else None
                
            elif pattern_name == 'simple_pattern':
                analysis['cleaned_name'] = match.group(0)
                analysis['part'] = f"Part {groups[1]}"
                analysis['item'] = f"Item {groups[2]}" if 'Item' in groups[0] else f"Line {groups[2]}"
                analysis['field_description'] = groups[3] if len(groups) > 3 else None
            
            break
    
    # Build hierarchical path
    if analysis['part']:
        analysis['hierarchical_path'].append(analysis['part'])
    if analysis['item']:
        analysis['hierarchical_path'].append(analysis['item'])
    if analysis['field_description']:
        analysis['hierarchical_path'].append(analysis['field_description'])
    
    # Determine field type
    analysis['field_type'] = determine_field_type_from_name(analysis['cleaned_name'])
    
    return analysis

def determine_field_type_from_name(field_name: str) -> str:
    """Determine field type from field name with improved detection"""
    field_lower = field_name.lower()
    
    # Check for specific patterns
    if any(pattern in field_lower for pattern in ['cb', 'checkbox', 'choice']):
        return 'CheckBox'
    
    if any(pattern in field_lower for pattern in ['date', 'dob', 'from', 'to']):
        return 'Date'
    
    if any(pattern in field_lower for pattern in ['phone', 'telephone', 'fax', 'mobile']):
        return 'Phone'
    
    if any(pattern in field_lower for pattern in ['email', 'e-mail']):
        return 'Email'
    
    if any(pattern in field_lower for pattern in ['ssn', 'ein', 'fein', 'number', 'zip']):
        return 'Number'
    
    if any(pattern in field_lower for pattern in ['signature', 'sign']):
        return 'Signature'
    
    if any(pattern in field_lower for pattern in ['amount', 'fee', 'wage', 'salary', 'compensation']):
        return 'Currency'
    
    return 'TextBox'

def get_mapping_from_database(form_type: str, part: str, item: str, field_desc: str) -> Tuple[Optional[str], float]:
    """Get mapping from USCIS database with confidence score"""
    if not form_type or form_type not in USCIS_FORMS_DATABASE:
        return None, 0.0
    
    form_data = USCIS_FORMS_DATABASE[form_type]
    
    # Try to find exact match in database
    for part_key, part_data in form_data['parts'].items():
        if part and part.lower() == part_key.lower():
            fields = part_data.get('fields', {})
            
            # Try different field key formats
            possible_keys = []
            if item and field_desc:
                # Part1_Item2_CompanyName format
                item_num = re.search(r'\d+[a-z]?', item)
                if item_num:
                    possible_keys.extend([
                        f"{part.replace(' ', '')}_Item{item_num.group(0)}_{field_desc}",
                        f"{part.replace(' ', '')}_{item}_{field_desc}",
                        f"Pt{part.split()[-1]}Line{item_num.group(0)}_{field_desc}"
                    ])
            
            for key in possible_keys:
                if key in fields:
                    return fields[key], 1.0  # Exact match
                
                # Try partial matching
                for field_key, mapping in fields.items():
                    if key.lower() in field_key.lower() or field_key.lower() in key.lower():
                        return mapping, 0.8  # Partial match
    
    return None, 0.0

# Extract fields from PDF with enhanced analysis
def extract_pdf_fields_enhanced(pdf_file) -> Tuple[List[Dict], OrderedDict, List[Dict]]:
    """Enhanced PDF field extraction with detailed analysis"""
    fields = []
    raw_fields = []
    form_parts = OrderedDict()
    processing_log = []
    
    # Reset file position
    pdf_file.seek(0)
    
    # Detect form type
    form_type = None
    
    # Try PyMuPDF first
    if PYMUPDF_AVAILABLE:
        try:
            processing_log.append("Using PyMuPDF for extraction...")
            pdf_bytes = pdf_file.read()
            pdf_file.seek(0)
            
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            # Detect form type from text
            for page_num in range(min(3, len(doc))):
                page = doc[page_num]
                text = page.get_text()
                
                for form_key, form_info in USCIS_FORMS_DATABASE.items():
                    for pattern in form_info['patterns']:
                        if re.search(pattern, text, re.IGNORECASE):
                            form_type = form_key
                            processing_log.append(f"Detected form type: {form_key}")
                            st.session_state.form_type = form_type
                            break
                    if form_type:
                        break
            
            # Extract all form fields
            field_count = 0
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                for widget in page.widgets():
                    if widget.field_name:
                        field_count += 1
                        
                        # Analyze field
                        analysis = analyze_field_name(widget.field_name)
                        
                        # Get mapping from database
                        if form_type and analysis['part'] and analysis['item']:
                            mapping, confidence = get_mapping_from_database(
                                form_type, 
                                analysis['part'], 
                                analysis['item'], 
                                analysis['field_description']
                            )
                            analysis['suggested_mapping'] = mapping
                            analysis['confidence'] = confidence
                        
                        # Store raw field data
                        raw_field = {
                            'index': field_count,
                            'raw_name': widget.field_name,
                            'page': page_num + 1,
                            'type': widget.field_type_string if hasattr(widget, 'field_type_string') else 'Unknown',
                            'value': widget.field_value,
                            'flags': widget.field_flags if hasattr(widget, 'field_flags') else 0,
                            'rect': list(widget.rect) if hasattr(widget, 'rect') else []
                        }
                        raw_fields.append(raw_field)
                        
                        # Create processed field
                        field_data = {
                            'index': field_count,
                            'name': analysis['cleaned_name'],
                            'raw_name': widget.field_name,
                            'type': analysis['field_type'],
                            'value': widget.field_value or '',
                            'required': widget.field_flags & 2 != 0 if hasattr(widget, 'field_flags') else False,
                            'page': page_num + 1,
                            'part': analysis['part'],
                            'item': analysis['item'],
                            'description': analysis['field_description'],
                            'suggested_mapping': analysis['suggested_mapping'],
                            'confidence': analysis['confidence'],
                            'analysis': analysis
                        }
                        fields.append(field_data)
            
            doc.close()
            processing_log.append(f"Extracted {field_count} fields using PyMuPDF")
            
        except Exception as e:
            processing_log.append(f"PyMuPDF error: {str(e)}")
            st.error(f"PyMuPDF extraction failed: {str(e)}")
    
    # Fallback to PyPDF2
    if len(fields) == 0 and PDF_AVAILABLE:
        try:
            processing_log.append(f"Using {PDF_LIBRARY} for extraction...")
            pdf_file.seek(0)
            reader = PdfReader(pdf_file)
            
            # Try to get form fields
            if hasattr(reader, 'get_form_text_fields'):
                form_fields = reader.get_form_text_fields() or {}
                field_count = 0
                
                for field_name, field_value in form_fields.items():
                    if field_name:
                        field_count += 1
                        
                        # Analyze field
                        analysis = analyze_field_name(field_name)
                        
                        # Store raw field
                        raw_field = {
                            'index': field_count,
                            'raw_name': field_name,
                            'value': field_value,
                            'page': 0
                        }
                        raw_fields.append(raw_field)
                        
                        # Create processed field
                        field_data = {
                            'index': field_count,
                            'name': analysis['cleaned_name'],
                            'raw_name': field_name,
                            'type': analysis['field_type'],
                            'value': field_value or '',
                            'page': 0,
                            'part': analysis['part'],
                            'item': analysis['item'],
                            'description': analysis['field_description'],
                            'analysis': analysis
                        }
                        fields.append(field_data)
                
                processing_log.append(f"Extracted {field_count} fields using {PDF_LIBRARY}")
                
        except Exception as e:
            processing_log.append(f"{PDF_LIBRARY} error: {str(e)}")
            st.error(f"PDF extraction failed: {str(e)}")
    
    # Organize fields by parts
    form_parts = organize_fields_by_parts_detailed(fields, form_type)
    
    # Store in session state
    st.session_state.processing_log = processing_log
    st.session_state.raw_fields = raw_fields
    st.session_state.field_analysis = {f['raw_name']: f['analysis'] for f in fields}
    
    return fields, form_parts, raw_fields

def organize_fields_by_parts_detailed(fields: List[Dict], form_type: str) -> OrderedDict:
    """Organize fields by parts with detailed structure"""
    form_parts = OrderedDict()
    
    # Create parts from database structure if available
    if form_type and form_type in USCIS_FORMS_DATABASE:
        form_data = USCIS_FORMS_DATABASE[form_type]
        for part_key, part_info in form_data['parts'].items():
            form_parts[part_key] = {
                'title': part_info['title'],
                'fields': [],
                'expected_fields': part_info.get('fields', {})
            }
    
    # Add unassigned part
    form_parts['Unassigned'] = {
        'title': 'Unassigned Fields',
        'fields': [],
        'expected_fields': {}
    }
    
    # Organize fields
    for field in fields:
        assigned = False
        
        if field.get('part'):
            # Try to find matching part
            for part_key in form_parts.keys():
                if field['part'].lower() in part_key.lower():
                    form_parts[part_key]['fields'].append(field)
                    assigned = True
                    break
        
        if not assigned:
            form_parts['Unassigned']['fields'].append(field)
    
    # Remove empty parts except Unassigned
    parts_to_keep = OrderedDict()
    for part_key, part_data in form_parts.items():
        if part_data['fields'] or part_key == 'Unassigned':
            parts_to_keep[part_key] = part_data
    
    return parts_to_keep

# UI Components
def display_field_analysis(field: Dict, index: int):
    """Display detailed field analysis"""
    with st.expander(f"Field {field['index']}: {field['name']}", expanded=st.session_state.show_field_analysis):
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown("**Raw Field Information:**")
            st.code(field['raw_name'], language='text')
            
            st.markdown("**Field Components:**")
            if field.get('part'):
                st.write(f"📁 Part: {field['part']}")
            if field.get('item'):
                st.write(f"📋 Item: {field['item']}")
            if field.get('description'):
                st.write(f"📝 Description: {field['description']}")
            
            st.write(f"📄 Page: {field.get('page', 'Unknown')}")
            st.write(f"🔧 Type: {field.get('type', 'Unknown')}")
            
            if field.get('value'):
                st.write(f"✏️ Current Value: {field['value']}")
        
        with col2:
            st.markdown("**Mapping Information:**")
            
            if field.get('suggested_mapping'):
                confidence = field.get('confidence', 0)
                conf_class = 'high' if confidence > 0.8 else 'medium' if confidence > 0.5 else 'low'
                
                st.markdown(f"""
                <div class="field-mapping confidence-{conf_class}">
                    Suggested: {field['suggested_mapping']}<br>
                    Confidence: {confidence:.0%}
                </div>
                """, unsafe_allow_html=True)
                
                # Mapping controls
                col_a, col_b = st.columns([3, 1])
                with col_a:
                    if st.button(f"Accept Mapping", key=f"accept_{index}"):
                        st.session_state.mapped_fields[field['name']] = f"{field['suggested_mapping']}:{field['type']}"
                        st.success(f"Mapped to {field['suggested_mapping']}")
                        st.rerun()
                
                with col_b:
                    if st.button(f"Reject", key=f"reject_{index}"):
                        st.session_state.questionnaire_fields[field['name']] = {
                            'type': 'text',
                            'label': field.get('description', field['name']),
                            'required': field.get('required', False)
                        }
                        st.rerun()
            else:
                st.warning("No automatic mapping found")
                
                # Manual mapping
                manual_mapping = st.text_input(
                    "Manual mapping path:",
                    placeholder="e.g., customer.customer_name",
                    key=f"manual_{index}"
                )
                
                if manual_mapping:
                    if st.button(f"Apply", key=f"apply_{index}"):
                        st.session_state.mapped_fields[field['name']] = f"{manual_mapping}:{field['type']}"
                        st.success(f"Mapped to {manual_mapping}")
                        st.rerun()

def display_raw_fields_table(raw_fields: List[Dict]):
    """Display raw fields in a table format"""
    if not raw_fields:
        st.warning("No raw fields to display")
        return
    
    # Create DataFrame for display
    df_data = []
    for field in raw_fields:
        df_data.append({
            'Index': field.get('index', ''),
            'Raw Field Name': field.get('raw_name', ''),
            'Page': field.get('page', ''),
            'Type': field.get('type', ''),
            'Value': field.get('value', '')[:50] + '...' if field.get('value') and len(field.get('value', '')) > 50 else field.get('value', '')
        })
    
    df = pd.DataFrame(df_data)
    st.dataframe(df, use_container_width=True, height=400)

def display_part_fields(part_key: str, part_data: Dict):
    """Display fields for a specific part"""
    st.markdown(f"""
    <div class="part-header">
        {part_key} - {part_data['title']}
        <span style="float: right;">Fields: {len(part_data['fields'])}</span>
    </div>
    """, unsafe_allow_html=True)
    
    if part_data['fields']:
        for idx, field in enumerate(part_data['fields']):
            display_field_analysis(field, f"{part_key}_{idx}")
    else:
        st.info("No fields found in this part")
    
    # Show expected fields if available
    if part_data.get('expected_fields'):
        with st.expander("Expected Fields Reference"):
            for field_key, mapping in part_data['expected_fields'].items():
                st.code(f"{field_key} → {mapping}")

# Main Application
def main():
    st.title("🏛️ USCIS PDF Form Field Extractor & Mapper")
    st.markdown("Extract and analyze PDF form fields with precise mapping to database structure")
    
    # Sidebar
    with st.sidebar:
        st.header("📋 Form Analysis Settings")
        
        st.session_state.show_raw_fields = st.checkbox("Show Raw Fields Table", value=True)
        st.session_state.show_field_analysis = st.checkbox("Expand Field Analysis", value=True)
        
        if st.session_state.form_type:
            st.success(f"Detected: {st.session_state.form_type}")
            if st.session_state.form_type in USCIS_FORMS_DATABASE:
                st.caption(USCIS_FORMS_DATABASE[st.session_state.form_type]['title'])
        
        st.markdown("---")
        
        # Statistics
        if st.session_state.pdf_fields:
            st.header("📊 Extraction Statistics")
            
            total = len(st.session_state.pdf_fields)
            mapped = len(st.session_state.mapped_fields)
            
            st.metric("Total Fields", total)
            st.metric("Mapped Fields", mapped)
            st.metric("Success Rate", f"{(mapped/total*100):.1f}%" if total > 0 else "0%")
            
            # Part breakdown
            st.markdown("**Fields by Part:**")
            for part_key, part_data in st.session_state.form_parts.items():
                if part_data['fields']:
                    st.caption(f"{part_key}: {len(part_data['fields'])} fields")
    
    # Main content
    tab1, tab2, tab3, tab4 = st.tabs([
        "📤 Upload PDF",
        "🔍 Field Analysis",
        "📊 Raw Fields",
        "📥 Export"
    ])
    
    # Tab 1: Upload
    with tab1:
        st.header("Upload USCIS Form PDF")
        
        uploaded_file = st.file_uploader(
            "Choose a USCIS PDF form",
            type="pdf",
            help="Upload forms like I-129, I-140, G-28, etc."
        )
        
        if uploaded_file:
            st.info(f"📄 Uploaded: {uploaded_file.name}")
            
            if st.button("🔍 Extract Fields", type="primary"):
                with st.spinner("Extracting and analyzing fields..."):
                    try:
                        fields, form_parts, raw_fields = extract_pdf_fields_enhanced(uploaded_file)
                        
                        st.session_state.pdf_fields = fields
                        st.session_state.form_parts = form_parts
                        st.session_state.raw_fields = raw_fields
                        
                        if fields:
                            st.success(f"✅ Extracted {len(fields)} fields!")
                            
                            # Show processing log
                            with st.expander("Processing Log"):
                                for log in st.session_state.processing_log:
                                    st.text(log)
                            
                            st.rerun()
                        else:
                            st.error("No fields found in the PDF")
                            
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
                        st.exception(e)
    
    # Tab 2: Field Analysis
    with tab2:
        st.header("Field-by-Field Analysis")
        
        if not st.session_state.form_parts:
            st.warning("Please upload and extract a PDF form first")
        else:
            # Display parts and fields
            for part_key, part_data in st.session_state.form_parts.items():
                display_part_fields(part_key, part_data)
    
    # Tab 3: Raw Fields
    with tab3:
        st.header("Raw Field Data")
        
        if st.session_state.raw_fields:
            st.markdown("### Complete list of extracted fields:")
            display_raw_fields_table(st.session_state.raw_fields)
            
            # Download raw data
            if st.button("📥 Download Raw Field Data (JSON)"):
                json_data = json.dumps(st.session_state.raw_fields, indent=2)
                st.download_button(
                    "Download JSON",
                    data=json_data,
                    file_name=f"raw_fields_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )
        else:
            st.info("No raw field data available")
    
    # Tab 4: Export
    with tab4:
        st.header("Export Configuration")
        
        if st.session_state.mapped_fields:
            # Generate TypeScript configuration
            ts_config = generate_typescript_config()
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("TypeScript Configuration")
                st.code(ts_config[:500] + "...", language="typescript")
                
                st.download_button(
                    "📥 Download TypeScript Config",
                    data=ts_config,
                    file_name=f"{st.session_state.form_type or 'form'}_config.ts",
                    mime="text/plain"
                )
            
            with col2:
                st.subheader("Mapping Summary")
                
                # Show mapping statistics
                mappings_by_category = defaultdict(list)
                for field_name, mapping in st.session_state.mapped_fields.items():
                    category = mapping.split('.')[0].split(':')[0]
                    mappings_by_category[category].append(field_name)
                
                for category, fields in mappings_by_category.items():
                    st.metric(f"{category.title()} Fields", len(fields))
        else:
            st.info("No mapped fields to export")

def generate_typescript_config() -> str:
    """Generate TypeScript configuration from mapped fields"""
    form_name = st.session_state.form_type or 'UnknownForm'
    
    # Categorize mappings
    categorized = defaultdict(dict)
    for field_name, mapping_info in st.session_state.mapped_fields.items():
        mapping, field_type = mapping_info.split(':')
        category = mapping.split('.')[0]
        categorized[category][field_name] = f"{mapping}:{field_type}"
    
    # Generate TypeScript
    ts_content = f"""export const {form_name.replace('-', '')} = {{
    formname: "{form_name}",
    customerData: {json.dumps(categorized.get('customer', {}), indent=8) if categorized.get('customer') else 'null'},
    beneficiaryData: {json.dumps(categorized.get('beneficiary', {}), indent=8) if categorized.get('beneficiary') else 'null'},
    attorneyData: {json.dumps(categorized.get('attorney', {}), indent=8) if categorized.get('attorney') else 'null'},
    lcaData: {json.dumps(categorized.get('lca', {}), indent=8) if categorized.get('lca') else 'null'},
    caseData: {json.dumps(categorized.get('case', {}), indent=8) if categorized.get('case') else 'null'},
    questionnaireData: {json.dumps(st.session_state.questionnaire_fields, indent=8)},
    metadata: {{
        formType: "{st.session_state.form_type}",
        totalFields: {len(st.session_state.pdf_fields)},
        mappedFields: {len(st.session_state.mapped_fields)},
        extractionDate: "{datetime.now().isoformat()}"
    }}
}}"""
    
    return ts_content

# Run the application
if __name__ == "__main__":
    main()
