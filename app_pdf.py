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

# Page configuration
st.set_page_config(
    page_title="USCIS PDF Form Mapper",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Comprehensive USCIS Forms Database with exact mappings
USCIS_FORMS_DATABASE = {
    'I-129': {
        'title': 'Petition for a Nonimmigrant Worker',
        'patterns': [r'Form\s*I-129', r'Petition.*Nonimmigrant.*Worker', r'I-129'],
        'field_mappings': {
            # Part 1 - Petitioner Information
            'LegalName': 'customer.customer_name',
            'TradeName': 'customer.trade_name',
            'DBAName': 'customer.trade_name',
            'InCareOf': 'customer.signatory_name',
            'StreetNumberName': 'customer.address_street',
            'StreetNumber': 'customer.address_street',
            'AptSteFlr': 'customer.address_apt',
            'CityOrTown': 'customer.address_city',
            'City': 'customer.address_city',
            'State': 'customer.address_state',
            'ZipCode': 'customer.address_zip',
            'Zip': 'customer.address_zip',
            'Province': 'customer.address_province',
            'PostalCode': 'customer.foreign_postal_code',
            'Country': 'customer.address_country',
            'Telephone': 'customer.signatory_work_phone',
            'Phone': 'customer.signatory_work_phone',
            'DaytimePhone': 'customer.signatory_work_phone',
            'Email': 'customer.signatory_email_id',
            'FEIN': 'customer.customer_tax_id',
            'EIN': 'customer.customer_tax_id',
            'IRS': 'customer.customer_tax_id',
            'SSN': 'customer.signatory_ssn',
            
            # Part 2 - Petition Information
            'Classification': 'case.caseType',
            'Basis': 'case.caseSubType',
            'RequestedAction': 'case.requestedAction',
            
            # Part 3 - Beneficiary Information
            'FamilyName': 'beneficiary.Beneficiary.beneficiaryLastName',
            'LastName': 'beneficiary.Beneficiary.beneficiaryLastName',
            'GivenName': 'beneficiary.Beneficiary.beneficiaryFirstName',
            'FirstName': 'beneficiary.Beneficiary.beneficiaryFirstName',
            'MiddleName': 'beneficiary.Beneficiary.beneficiaryMiddleName',
            'AlienNumber': 'beneficiary.Beneficiary.alien_number',
            'ANumber': 'beneficiary.Beneficiary.alien_number',
            'DOB': 'beneficiary.Beneficiary.beneficiaryDateOfBirth',
            'DateOfBirth': 'beneficiary.Beneficiary.beneficiaryDateOfBirth',
            'CountryOfBirth': 'beneficiary.Beneficiary.beneficiaryCountryOfBirth',
            'BirthCountry': 'beneficiary.Beneficiary.beneficiaryCountryOfBirth',
            'CountryOfCitizenship': 'beneficiary.Beneficiary.beneficiaryCitizenOfCountry',
            'Citizenship': 'beneficiary.Beneficiary.beneficiaryCitizenOfCountry',
            'Gender': 'beneficiary.Beneficiary.beneficiaryGender',
            'Sex': 'beneficiary.Beneficiary.beneficiaryGender',
            'I94Number': 'beneficiary.I94Details.I94.i94Number',
            'I94': 'beneficiary.I94Details.I94.i94Number',
            'PassportNumber': 'beneficiary.PassportDetails.Passport.passportNumber',
            'Passport': 'beneficiary.PassportDetails.Passport.passportNumber',
            'CurrentStatus': 'beneficiary.VisaDetails.Visa.visaStatus',
            'Status': 'beneficiary.VisaDetails.Visa.visaStatus',
            
            # Part 5 - Employment Information
            'JobTitle': 'lca.Lca.position_job_title',
            'Position': 'lca.Lca.position_job_title',
            'LCANumber': 'lca.Lca.lcaNumber',
            'LCA': 'lca.Lca.lcaNumber',
            'NAICS': 'lca.Lca.naics_code',
            'Wages': 'lca.Lca.gross_salary',
            'Salary': 'lca.Lca.gross_salary',
            'Rate': 'lca.Lca.gross_salary',
            'FromDate': 'lca.Lca.start_date',
            'StartDate': 'lca.Lca.start_date',
            'ToDate': 'lca.Lca.end_date',
            'EndDate': 'lca.Lca.end_date'
        }
    },
    'G-28': {
        'title': 'Notice of Entry of Appearance as Attorney',
        'patterns': [r'Form\s*G-28', r'G-28', r'Notice.*Entry.*Appearance'],
        'field_mappings': {
            # Part 1 - Attorney Information
            'FamilyName': 'attorney.attorneyInfo.lastName',
            'LastName': 'attorney.attorneyInfo.lastName',
            'GivenName': 'attorney.attorneyInfo.firstName',
            'FirstName': 'attorney.attorneyInfo.firstName',
            'MiddleName': 'attorney.attorneyInfo.middleName',
            'MiddleInitial': 'attorney.attorneyInfo.middleName',
            'StreetNumberName': 'attorney.attorneyInfo.address_street',
            'Street': 'attorney.attorneyInfo.address_street',
            'AptSteFlr': 'attorney.attorneyInfo.address_apt',
            'Suite': 'attorney.attorneyInfo.address_apt',
            'CityOrTown': 'attorney.attorneyInfo.address_city',
            'City': 'attorney.attorneyInfo.address_city',
            'State': 'attorney.attorneyInfo.address_state',
            'ZipCode': 'attorney.attorneyInfo.address_zip',
            'Zip': 'attorney.attorneyInfo.address_zip',
            'DaytimePhone': 'attorney.attorneyInfo.workPhone',
            'Phone': 'attorney.attorneyInfo.workPhone',
            'MobilePhone': 'attorney.attorneyInfo.mobilePhone',
            'Cell': 'attorney.attorneyInfo.mobilePhone',
            'Email': 'attorney.attorneyInfo.emailAddress',
            'FaxNumber': 'attorney.attorneyInfo.faxNumber',
            'Fax': 'attorney.attorneyInfo.faxNumber',
            
            # Part 2 - Eligibility
            'BarNumber': 'attorney.attorneyInfo.stateBarNumber',
            'AttorneyBarNumber': 'attorney.attorneyInfo.stateBarNumber',
            'USCISNumber': 'attorney.attorneyInfo.uscisNumber',
            'LawFirmName': 'attorneyLawfirmDetails.lawfirmDetails.lawFirmName',
            'FirmName': 'attorneyLawfirmDetails.lawfirmDetails.lawFirmName',
            'FirmEIN': 'attorneyLawfirmDetails.lawfirmDetails.firmEIN',
            'FEIN': 'attorneyLawfirmDetails.lawfirmDetails.firmEIN'
        }
    },
    'I-140': {
        'title': 'Immigrant Petition for Alien Worker',
        'patterns': [r'Form\s*I-140', r'I-140', r'Immigrant.*Petition'],
        'field_mappings': {
            # Part 1 - Petitioner Information
            'PetitionerName': 'customer.customer_name',
            'CompanyName': 'customer.customer_name',
            'LegalName': 'customer.customer_name',
            'StreetNumber': 'customer.address_street',
            'Street': 'customer.address_street',
            'City': 'customer.address_city',
            'State': 'customer.address_state',
            'ZipCode': 'customer.address_zip',
            'FEIN': 'customer.customer_tax_id',
            'Phone': 'customer.signatory_work_phone',
            'Email': 'customer.signatory_email_id',
            'ContactPerson': 'customer.signatory_name',
            
            # Part 2 - Petition Type
            'Classification': 'case.caseType',
            'Category': 'case.caseSubType',
            
            # Part 3 - Beneficiary Information
            'FamilyName': 'beneficiary.Beneficiary.beneficiaryLastName',
            'GivenName': 'beneficiary.Beneficiary.beneficiaryFirstName',
            'MiddleName': 'beneficiary.Beneficiary.beneficiaryMiddleName',
            'DOB': 'beneficiary.Beneficiary.beneficiaryDateOfBirth',
            'CityOfBirth': 'beneficiary.Beneficiary.cityOfBirth',
            'StateOfBirth': 'beneficiary.Beneficiary.stateOfBirth',
            'CountryOfBirth': 'beneficiary.Beneficiary.beneficiaryCountryOfBirth',
            'Gender': 'beneficiary.Beneficiary.beneficiaryGender',
            'AlienNumber': 'beneficiary.Beneficiary.alien_number',
            'SSN': 'beneficiary.Beneficiary.beneficiarySsn',
            'I94Number': 'beneficiary.I94Details.I94.i94Number'
        }
    }
}

# Enhanced CSS
st.markdown("""
<style>
    /* Clean Professional Style */
    .main-header {
        background: #003366;
        color: white;
        padding: 20px;
        border-radius: 8px;
        margin-bottom: 20px;
    }
    
    .part-section {
        background: #f7f9fc;
        border: 1px solid #e1e4e8;
        border-radius: 8px;
        padding: 20px;
        margin-bottom: 20px;
    }
    
    .field-item {
        background: white;
        border: 1px solid #e1e4e8;
        border-radius: 6px;
        padding: 12px;
        margin-bottom: 8px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    
    .field-mapped {
        border-left: 4px solid #28a745;
    }
    
    .field-questionnaire {
        border-left: 4px solid #17a2b8;
    }
    
    .field-unmapped {
        border-left: 4px solid #ffc107;
    }
    
    .mapping-path {
        color: #0066cc;
        font-family: monospace;
        font-size: 0.9em;
    }
    
    .stats-box {
        background: #e7f3ff;
        border: 1px solid #0066cc;
        border-radius: 6px;
        padding: 15px;
        margin-bottom: 15px;
        text-align: center;
    }
    
    .action-button {
        padding: 4px 12px;
        border-radius: 4px;
        font-size: 0.85em;
        cursor: pointer;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
def init_session_state():
    """Initialize session state"""
    defaults = {
        'pdf_fields': [],
        'form_parts': OrderedDict(),
        'mapped_fields': {},
        'questionnaire_fields': {},
        'form_type': None,
        'extracted': False,
        'auto_mapping_done': False,
        'categorized_mappings': {
            'customerData': {},
            'beneficiaryData': {},
            'attorneyData': {},
            'lcaData': {},
            'caseData': {},
            'questionnaireData': {}
        }
    }
    
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

init_session_state()

# Auto-mapping function
def auto_map_fields(fields: List[Dict], form_type: str) -> Dict[str, str]:
    """Automatically map fields based on field description and database"""
    mapped_fields = {}
    
    if form_type and form_type in USCIS_FORMS_DATABASE:
        field_mappings = USCIS_FORMS_DATABASE[form_type]['field_mappings']
        
        for field in fields:
            field_name = field['name']
            
            # Skip if already mapped
            if field_name in mapped_fields:
                continue
            
            # Try to find mapping based on field description
            field_desc = field.get('description', '')
            if field_desc:
                # Clean description
                desc_clean = re.sub(r'[^a-zA-Z]', '', field_desc)
                
                # Look for matching key in mappings
                for key, mapping in field_mappings.items():
                    if key.lower() in desc_clean.lower() or desc_clean.lower() in key.lower():
                        mapped_fields[field_name] = f"{mapping}:{field.get('type', 'TextBox')}"
                        break
            
            # If no mapping found, check full field name
            if field_name not in mapped_fields:
                field_name_clean = re.sub(r'[^a-zA-Z]', '', field_name)
                for key, mapping in field_mappings.items():
                    if key.lower() in field_name_clean.lower():
                        mapped_fields[field_name] = f"{mapping}:{field.get('type', 'TextBox')}"
                        break
    
    return mapped_fields

# Extract and analyze PDF
def extract_pdf_fields(pdf_file) -> Tuple[List[Dict], OrderedDict]:
    """Extract fields from PDF with analysis"""
    fields = []
    form_parts = OrderedDict()
    form_type = None
    
    # Reset file position
    pdf_file.seek(0)
    
    # Try PyMuPDF first
    if PYMUPDF_AVAILABLE:
        try:
            pdf_bytes = pdf_file.read()
            pdf_file.seek(0)
            
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            # Detect form type
            for page_num in range(min(3, len(doc))):
                page = doc[page_num]
                text = page.get_text()
                
                for form_key, form_info in USCIS_FORMS_DATABASE.items():
                    for pattern in form_info['patterns']:
                        if re.search(pattern, text, re.IGNORECASE):
                            form_type = form_key
                            st.session_state.form_type = form_type
                            break
                    if form_type:
                        break
            
            # Extract fields
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                for widget in page.widgets():
                    if widget.field_name:
                        # Parse field name
                        parsed = parse_field_name(widget.field_name)
                        
                        field_data = {
                            'name': parsed['clean_name'],
                            'raw_name': widget.field_name,
                            'type': determine_field_type(widget.field_name),
                            'value': widget.field_value or '',
                            'page': page_num + 1,
                            'part': parsed['part'],
                            'item': parsed['item'],
                            'description': parsed['description']
                        }
                        fields.append(field_data)
            
            doc.close()
            
        except Exception as e:
            st.error(f"Error extracting PDF: {str(e)}")
    
    # Fallback to PyPDF2
    elif PDF_AVAILABLE:
        try:
            pdf_file.seek(0)
            reader = PdfReader(pdf_file)
            
            # Get form fields
            if hasattr(reader, 'get_form_text_fields'):
                form_fields = reader.get_form_text_fields() or {}
                
                for field_name, field_value in form_fields.items():
                    if field_name:
                        parsed = parse_field_name(field_name)
                        
                        field_data = {
                            'name': parsed['clean_name'],
                            'raw_name': field_name,
                            'type': determine_field_type(field_name),
                            'value': field_value or '',
                            'page': 0,
                            'part': parsed['part'],
                            'item': parsed['item'],
                            'description': parsed['description']
                        }
                        fields.append(field_data)
                        
        except Exception as e:
            st.error(f"Error extracting PDF: {str(e)}")
    
    # Organize by parts
    form_parts = organize_by_parts(fields)
    
    return fields, form_parts

def parse_field_name(raw_name: str) -> Dict[str, str]:
    """Parse field name into components"""
    result = {
        'raw_name': raw_name,
        'clean_name': raw_name,
        'part': None,
        'item': None,
        'description': None
    }
    
    # Common patterns
    patterns = [
        # form[0].#subform[0].Pt1Line1a_FamilyName[0]
        r'(?:.*\.)?((?:Pt|Part)(\d+)(?:Line|Item)?(\d+[a-z]?)(?:_(.+?))?)\[?\d*\]?$',
        # Part1_Item2_CompanyName
        r'^(Part(\d+))_(?:Item)?(\d+[a-z]?)_(.+)$',
        # Simple field names
        r'^(\w+)$'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, raw_name, re.IGNORECASE)
        if match:
            groups = match.groups()
            
            if len(groups) >= 4:
                result['clean_name'] = groups[0]
                result['part'] = f"Part {groups[1]}"
                result['item'] = groups[2]
                result['description'] = groups[3] if len(groups) > 3 else None
            elif len(groups) == 1:
                result['clean_name'] = groups[0]
                result['description'] = groups[0]
            
            break
    
    # Clean up description
    if result['description']:
        # Remove underscores and convert to readable format
        desc = result['description']
        desc = re.sub(r'([a-z])([A-Z])', r'\1 \2', desc)  # CamelCase to spaces
        desc = desc.replace('_', ' ')
        result['description'] = desc.strip()
    
    return result

def determine_field_type(field_name: str) -> str:
    """Determine field type from name"""
    name_lower = field_name.lower()
    
    if any(x in name_lower for x in ['cb', 'checkbox', 'choice']):
        return 'CheckBox'
    elif any(x in name_lower for x in ['date', 'dob']):
        return 'Date'
    elif any(x in name_lower for x in ['phone', 'tel']):
        return 'Phone'
    elif any(x in name_lower for x in ['email']):
        return 'Email'
    elif any(x in name_lower for x in ['ssn', 'ein', 'number']):
        return 'Number'
    elif any(x in name_lower for x in ['signature']):
        return 'Signature'
    else:
        return 'TextBox'

def organize_by_parts(fields: List[Dict]) -> OrderedDict:
    """Organize fields by parts"""
    parts = OrderedDict()
    
    # Group by parts
    for field in fields:
        part = field.get('part', 'Unassigned')
        if part not in parts:
            parts[part] = []
        parts[part].append(field)
    
    # Sort parts
    sorted_parts = OrderedDict()
    for key in sorted(parts.keys(), key=lambda x: (x != 'Unassigned', x)):
        sorted_parts[key] = parts[key]
    
    return sorted_parts

# UI Components
def display_part_fields(part_name: str, fields: List[Dict]):
    """Display fields for a part"""
    st.markdown(f"### {part_name}")
    
    # Count statistics
    mapped_count = sum(1 for f in fields if f['name'] in st.session_state.mapped_fields)
    quest_count = sum(1 for f in fields if f['name'] in st.session_state.questionnaire_fields)
    unmapped_count = len(fields) - mapped_count - quest_count
    
    # Display stats
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Fields", len(fields))
    with col2:
        st.metric("Mapped", mapped_count)
    with col3:
        st.metric("Questionnaire", quest_count)
    with col4:
        st.metric("Unmapped", unmapped_count)
    
    # Display fields
    for field in fields:
        field_name = field['name']
        
        # Determine status
        if field_name in st.session_state.mapped_fields:
            status = "mapped"
            mapping = st.session_state.mapped_fields[field_name].split(':')[0]
            status_text = f"✅ Mapped to: {mapping}"
            css_class = "field-mapped"
        elif field_name in st.session_state.questionnaire_fields:
            status = "questionnaire"
            status_text = "📋 In Questionnaire"
            css_class = "field-questionnaire"
        else:
            status = "unmapped"
            status_text = "⚠️ Unmapped"
            css_class = "field-unmapped"
        
        # Create columns for field display
        col1, col2, col3 = st.columns([3, 3, 2])
        
        with col1:
            st.markdown(f"**{field.get('description', field_name)}**")
            st.caption(f"Field: {field_name} | Type: {field.get('type', 'Unknown')}")
        
        with col2:
            st.markdown(status_text)
        
        with col3:
            if status == "mapped":
                if st.button("Edit", key=f"edit_{field_name}"):
                    st.session_state[f"editing_{field_name}"] = True
                    
                if st.session_state.get(f"editing_{field_name}", False):
                    new_mapping = st.text_input("New mapping:", value=mapping, key=f"new_{field_name}")
                    if st.button("Save", key=f"save_{field_name}"):
                        st.session_state.mapped_fields[field_name] = f"{new_mapping}:{field['type']}"
                        st.session_state[f"editing_{field_name}"] = False
                        st.rerun()
                        
            elif status == "unmapped":
                if st.button("Map", key=f"map_{field_name}"):
                    st.session_state[f"mapping_{field_name}"] = True
                
                if st.session_state.get(f"mapping_{field_name}", False):
                    mapping = st.text_input("Map to:", key=f"mapto_{field_name}")
                    col_a, col_b = st.columns(2)
                    with col_a:
                        if st.button("Save", key=f"savemap_{field_name}"):
                            if mapping:
                                st.session_state.mapped_fields[field_name] = f"{mapping}:{field['type']}"
                                st.session_state[f"mapping_{field_name}"] = False
                                st.rerun()
                    with col_b:
                        if st.button("To Questionnaire", key=f"quest_{field_name}"):
                            st.session_state.questionnaire_fields[field_name] = {
                                'type': 'text',
                                'label': field.get('description', field_name),
                                'required': False
                            }
                            st.session_state[f"mapping_{field_name}"] = False
                            st.rerun()

def generate_typescript_config() -> str:
    """Generate TypeScript configuration"""
    form_name = st.session_state.form_type or 'UnknownForm'
    
    # Categorize mappings
    categorized = {
        'customerData': {},
        'beneficiaryData': {},
        'attorneyData': {},
        'lcaData': {},
        'caseData': {},
        'questionnaireData': {}
    }
    
    # Process mapped fields
    for field_name, mapping_info in st.session_state.mapped_fields.items():
        mapping, field_type = mapping_info.split(':')
        category = mapping.split('.')[0]
        
        if category == 'customer':
            categorized['customerData'][field_name] = mapping_info
        elif category == 'beneficiary':
            categorized['beneficiaryData'][field_name] = mapping_info
        elif category == 'attorney' or category == 'attorneyLawfirmDetails':
            categorized['attorneyData'][field_name] = mapping_info
        elif category == 'lca':
            categorized['lcaData'][field_name] = mapping_info
        elif category == 'case':
            categorized['caseData'][field_name] = mapping_info
    
    # Add questionnaire fields
    for field_name, config in st.session_state.questionnaire_fields.items():
        categorized['questionnaireData'][field_name] = f"{field_name}:SingleBox"
    
    # Generate TypeScript
    ts_content = f"""export const {form_name.replace('-', '')} = {{
    formname: "{form_name}",
    customerData: {json.dumps(categorized['customerData'], indent=8) if categorized['customerData'] else 'null'},
    beneficiaryData: {json.dumps(categorized['beneficiaryData'], indent=8) if categorized['beneficiaryData'] else 'null'},
    attorneyData: {json.dumps(categorized['attorneyData'], indent=8) if categorized['attorneyData'] else 'null'},
    lcaData: {json.dumps(categorized['lcaData'], indent=8) if categorized['lcaData'] else 'null'},
    caseData: {json.dumps(categorized['caseData'], indent=8) if categorized['caseData'] else 'null'},
    questionnaireData: {json.dumps(categorized['questionnaireData'], indent=8)},
    defaultData: {{}},
    conditionalData: {{}},
    pdfName: "{form_name}",
    metadata: {{
        formType: "{st.session_state.form_type}",
        totalFields: {len(st.session_state.pdf_fields)},
        mappedFields: {len(st.session_state.mapped_fields)},
        questionnaireFields: {len(st.session_state.questionnaire_fields)},
        timestamp: "{datetime.now().isoformat()}"
    }}
}}"""
    
    return ts_content

def generate_questionnaire_json() -> str:
    """Generate questionnaire JSON"""
    questionnaire_data = []
    
    for field_name, config in st.session_state.questionnaire_fields.items():
        questionnaire_data.append({
            "fieldName": field_name,
            "label": config.get('label', field_name),
            "type": config.get('type', 'text'),
            "required": config.get('required', False),
            "options": config.get('options', []),
            "validation": config.get('validation', '')
        })
    
    return json.dumps({
        "formType": st.session_state.form_type,
        "questionnaireFields": questionnaire_data,
        "totalFields": len(questionnaire_data),
        "timestamp": datetime.now().isoformat()
    }, indent=2)

# Main Application
def main():
    st.markdown('<div class="main-header"><h1>🏛️ USCIS PDF Form Mapper</h1><p>Extract, map, and configure form fields automatically</p></div>', unsafe_allow_html=True)
    
    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📤 Upload & Extract",
        "🗂️ Field Mapping",
        "❓ Questionnaire",
        "📥 Export"
    ])
    
    # Tab 1: Upload
    with tab1:
        st.header("Upload PDF Form")
        
        uploaded_file = st.file_uploader(
            "Choose a USCIS PDF form",
            type="pdf",
            help="Supports I-129, I-140, G-28, and other USCIS forms"
        )
        
        if uploaded_file:
            st.info(f"📄 File: {uploaded_file.name}")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("🔍 Extract Fields", type="primary", use_container_width=True):
                    with st.spinner("Extracting fields..."):
                        fields, form_parts = extract_pdf_fields(uploaded_file)
                        st.session_state.pdf_fields = fields
                        st.session_state.form_parts = form_parts
                        st.session_state.extracted = True
                        
                        if fields:
                            st.success(f"✅ Extracted {len(fields)} fields!")
                            if st.session_state.form_type:
                                st.info(f"📋 Detected Form: {st.session_state.form_type}")
                        else:
                            st.error("No fields found")
            
            with col2:
                if st.session_state.extracted and not st.session_state.auto_mapping_done:
                    if st.button("🤖 Auto-Map Fields", type="secondary", use_container_width=True):
                        with st.spinner("Auto-mapping fields..."):
                            mapped = auto_map_fields(st.session_state.pdf_fields, st.session_state.form_type)
                            st.session_state.mapped_fields.update(mapped)
                            
                            # Move unmapped checkboxes to questionnaire
                            for field in st.session_state.pdf_fields:
                                if field['name'] not in st.session_state.mapped_fields and field['type'] == 'CheckBox':
                                    st.session_state.questionnaire_fields[field['name']] = {
                                        'type': 'checkbox',
                                        'label': field.get('description', field['name']),
                                        'required': False
                                    }
                            
                            st.session_state.auto_mapping_done = True
                            st.success(f"✅ Auto-mapped {len(mapped)} fields!")
                            st.rerun()
        
        # Summary Statistics
        if st.session_state.extracted:
            st.markdown("---")
            st.subheader("Extraction Summary")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Fields", len(st.session_state.pdf_fields))
            with col2:
                st.metric("Mapped", len(st.session_state.mapped_fields))
            with col3:
                st.metric("Questionnaire", len(st.session_state.questionnaire_fields))
            with col4:
                unmapped = len(st.session_state.pdf_fields) - len(st.session_state.mapped_fields) - len(st.session_state.questionnaire_fields)
                st.metric("Unmapped", unmapped)
    
    # Tab 2: Field Mapping
    with tab2:
        st.header("Field Mapping by Parts")
        
        if not st.session_state.form_parts:
            st.info("Please upload and extract a PDF form first")
        else:
            # Display each part
            for part_name, fields in st.session_state.form_parts.items():
                with st.expander(f"{part_name} ({len(fields)} fields)", expanded=True):
                    display_part_fields(part_name, fields)
    
    # Tab 3: Questionnaire
    with tab3:
        st.header("Questionnaire Fields")
        st.caption("Non-mapped fields that will be collected via questionnaire")
        
        if st.session_state.questionnaire_fields:
            # Display questionnaire fields
            for field_name, config in st.session_state.questionnaire_fields.items():
                col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
                
                with col1:
                    st.text_input("Label", value=config['label'], key=f"qlabel_{field_name}")
                
                with col2:
                    field_type = st.selectbox(
                        "Type",
                        ["text", "checkbox", "radio", "select", "date", "textarea"],
                        index=["text", "checkbox", "radio", "select", "date", "textarea"].index(config.get('type', 'text')),
                        key=f"qtype_{field_name}"
                    )
                    config['type'] = field_type
                
                with col3:
                    config['required'] = st.checkbox("Required", value=config.get('required', False), key=f"qreq_{field_name}")
                
                with col4:
                    if st.button("Remove", key=f"qrem_{field_name}"):
                        del st.session_state.questionnaire_fields[field_name]
                        st.rerun()
            
            # Add new field option
            st.markdown("---")
            st.subheader("Add Custom Field")
            
            col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
            with col1:
                new_label = st.text_input("Field Label", key="new_field_label")
            with col2:
                new_type = st.selectbox("Type", ["text", "checkbox", "radio", "select", "date", "textarea"], key="new_field_type")
            with col3:
                new_required = st.checkbox("Required", key="new_field_required")
            with col4:
                if st.button("Add Field", type="primary"):
                    if new_label:
                        field_key = re.sub(r'[^\w]', '_', new_label)
                        st.session_state.questionnaire_fields[field_key] = {
                            'type': new_type,
                            'label': new_label,
                            'required': new_required
                        }
                        st.rerun()
        else:
            st.info("No questionnaire fields yet. Unmapped fields will appear here.")
    
    # Tab 4: Export
    with tab4:
        st.header("Export Configuration")
        
        if st.session_state.mapped_fields or st.session_state.questionnaire_fields:
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📄 TypeScript Configuration")
                ts_config = generate_typescript_config()
                
                # Preview
                with st.expander("Preview TypeScript"):
                    st.code(ts_config, language="typescript")
                
                # Download
                st.download_button(
                    "📥 Download TypeScript",
                    data=ts_config,
                    file_name=f"{st.session_state.form_type or 'form'}_config.ts",
                    mime="text/plain",
                    use_container_width=True
                )
            
            with col2:
                st.subheader("📋 Questionnaire JSON")
                quest_json = generate_questionnaire_json()
                
                # Preview
                with st.expander("Preview JSON"):
                    st.code(quest_json, language="json")
                
                # Download
                st.download_button(
                    "📥 Download Questionnaire JSON",
                    data=quest_json,
                    file_name=f"{st.session_state.form_type or 'form'}_questionnaire.json",
                    mime="application/json",
                    use_container_width=True
                )
            
            # Summary
            st.markdown("---")
            st.subheader("Export Summary")
            
            # Mapping breakdown
            categorized = defaultdict(int)
            for mapping in st.session_state.mapped_fields.values():
                category = mapping.split('.')[0].split(':')[0]
                categorized[category] += 1
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Customer Fields", categorized.get('customer', 0))
                st.metric("Beneficiary Fields", categorized.get('beneficiary', 0))
            with col2:
                st.metric("Attorney Fields", categorized.get('attorney', 0) + categorized.get('attorneyLawfirmDetails', 0))
                st.metric("LCA Fields", categorized.get('lca', 0))
            with col3:
                st.metric("Case Fields", categorized.get('case', 0))
                st.metric("Questionnaire Fields", len(st.session_state.questionnaire_fields))
        else:
            st.info("No data to export. Please extract and map fields first.")

if __name__ == "__main__":
    main()
