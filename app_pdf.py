import streamlit as st
import json
import re
import fitz  # PyMuPDF
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Set
from collections import defaultdict, OrderedDict
import pandas as pd
from dataclasses import dataclass, field
import hashlib
from io import BytesIO
import traceback
import time

# Try to import openai - make it optional
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    st.warning("OpenAI not installed. Running without AI assistance.")

# Configure page
st.set_page_config(
    page_title="USCIS Form Reader Pro",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS styling
st.markdown("""
<style>
    .stApp {
        background: #f5f5f5;
    }
    .main .block-container {
        padding: 2rem;
        max-width: 1400px;
    }
    .mapping-row {
        background: white;
        border: 1px solid #ddd;
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 0.5rem;
        transition: all 0.2s ease;
    }
    .mapping-row:hover {
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .field-label {
        font-weight: 600;
        color: #2c3e50;
        font-size: 1.05rem;
        margin-bottom: 0.25rem;
    }
    .field-type {
        background: #e3f2fd;
        color: #1976d2;
        padding: 0.15rem 0.4rem;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 500;
        margin-right: 0.25rem;
        display: inline-block;
    }
    .field-type.checkbox {
        background: #fce4ec;
        color: #c2185b;
    }
    .field-type.radio {
        background: #f3e5f5;
        color: #7b1fa2;
    }
    .status-badge {
        padding: 0.25rem 0.75rem;
        border-radius: 15px;
        font-size: 0.85rem;
        font-weight: 500;
        display: inline-block;
        margin-top: 0.5rem;
    }
    .status-mapped {
        background: #d4edda;
        color: #155724;
    }
    .status-questionnaire {
        background: #fff3cd;
        color: #856404;
    }
    .status-unmapped {
        background: #f8d7da;
        color: #721c24;
    }
    .part-selector {
        background: white;
        padding: 1.5rem;
        border-radius: 8px;
        border: 1px solid #ddd;
        margin-bottom: 1rem;
    }
    .db-path-tree {
        background: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 4px;
        padding: 0.5rem;
        max-height: 200px;
        overflow-y: auto;
    }
    .field-meta {
        color: #666;
        font-size: 0.8rem;
        margin-top: 0.25rem;
        line-height: 1.4;
    }
    .field-meta span {
        margin-right: 0.75rem;
    }
    .part-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 1rem;
        font-weight: 600;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .part-expander {
        background: white;
        border: 2px solid #e0e0e0;
        border-radius: 10px;
        margin-bottom: 1rem;
        padding: 0.5rem;
    }
    /* Clean up Streamlit's default styles */
    .stSelectbox > div > div {
        background-color: white;
    }
    .stButton > button {
        transition: all 0.2s ease;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# Database Structure
DB_OBJECTS = {
    "beneficiary": {
        "Beneficiary": ["beneficiaryFirstName", "beneficiaryLastName", "beneficiaryMiddleName",
                       "beneficiaryGender", "beneficiaryDateOfBirth", "beneficiarySsn",
                       "alienNumber", "alienRegistrationNumber", "beneficiaryCountryOfBirth", 
                       "beneficiaryCitizenOfCountry", "beneficiaryProvinceOfBirth",
                       "maritalStatus", "uscisOnlineAccountNumber"],
        "MailingAddress": ["addressStreet", "addressCity", "addressState", "addressZip", 
                          "addressCountry", "addressAptSteFlrNumber", "inCareOfName",
                          "addressNumber", "addressType"],
        "ContactInfo": ["daytimeTelephoneNumber", "mobileTelephoneNumber", "emailAddress",
                       "workPhone", "faxNumber"],
        "PassportDetails": ["passportNumber", "passportIssueCountry", 
                           "passportIssueDate", "passportExpiryDate"],
        "VisaDetails": ["currentNonimmigrantStatus", "dateStatusExpires", "visaNumber",
                       "visaStatus", "visaConsulateCity", "visaConsulateCountry"]
    },
    "petitioner": {
        "": ["familyName", "givenName", "middleName", "companyOrOrganizationName"],
        "ContactInfo": ["daytimeTelephoneNumber", "mobileTelephoneNumber", "emailAddress"],
        "Address": ["addressStreet", "addressCity", "addressState", "addressZip", "addressCountry"]
    },
    "customer": {
        "": ["customer_name", "customer_tax_id", "customer_type_of_business", 
             "customer_year_established", "customer_gross_annual_income", 
             "customer_net_annual_income", "customer_total_employees"],
        "SignatoryInfo": ["signatory_first_name", "signatory_last_name", "signatory_middle_name",
                         "signatory_job_title", "signatory_work_phone", "signatory_email",
                         "signatory_email_id", "signatory_mobile_phone"],
        "Address": ["address_street", "address_city", "address_state", "address_zip", 
                   "address_country", "address_number", "address_type"]
    },
    "attorney": {
        "attorneyInfo": ["firstName", "lastName", "middleName", "barNumber", "stateBarNumber",
                        "workPhone", "emailAddress", "faxNumber", "licensingAuthority"],
        "address": ["addressStreet", "addressCity", "addressState", "addressZip",
                   "addressCountry", "addressNumber", "addressType"]
    },
    "attorneyLawfirmDetails": {
        "lawfirmDetails": ["lawFirmName", "lawFirmEIN"],
        "address": ["addressStreet", "addressCity", "addressState", "addressZip",
                   "addressCountry", "addressNumber", "addressType"]
    },
    "case": {
        "": ["caseType", "caseSubType", "h1bRegistrationNumber", "h1BPetitionType",
            "requestedAction"]
    },
    "employment": {
        "": ["employment", "temporary", "employerName", "employerDate"]
    }
}

@dataclass
class PDFField:
    """Represents a field extracted from PDF"""
    widget_name: str = ""
    field_id: str = ""
    field_key: str = ""
    part_number: int = 1
    part_name: str = "Part 1"
    part_title: str = ""
    field_label: str = "Unnamed Field"
    field_type: str = "text"
    page: int = 1
    value: str = ""
    db_mapping: Optional[str] = None
    is_mapped: bool = False
    to_questionnaire: bool = False
    item_number: str = ""  # For USCIS item numbers like "1.a", "2.b"
    ai_suggestion: Optional[str] = None
    confidence_score: float = 0.0
    question_key: str = ""  # For questionnaire naming like "pt3_1a"
    
    def get_status(self) -> str:
        if self.is_mapped:
            return "✅ Mapped"
        elif self.to_questionnaire:
            return "📋 Questionnaire"
        else:
            return "❌ Unmapped"

class FieldExtractor:
    """Handles field extraction and mapping"""
    
    def __init__(self):
        self.init_session_state()
        self.db_paths = self._build_db_paths()
        self.field_patterns = self._build_field_patterns()
        self.db_tree = self._build_db_tree()
    
    def init_session_state(self):
        """Initialize Streamlit session state"""
        defaults = {
            'fields': [],
            'fields_by_part': OrderedDict(),
            'form_info': {},
            'pdf_processed': False,
            'extraction_stats': {},
            'debug_mode': False,
            'selected_part': 'All Parts',
            'mapping_filter': 'all',
            'ai_suggestions_enabled': False,
            'seen_fields': set(),  # Track unique fields
            'part_structure': OrderedDict(),  # Store part information
            'show_db_browser': False
        }
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value
    
    def _build_db_paths(self) -> List[str]:
        """Build all database paths"""
        paths = []
        
        for obj_name, structure in DB_OBJECTS.items():
            for sub_obj, fields in structure.items():
                if isinstance(fields, list):
                    for field in fields:
                        if sub_obj:
                            path = f"{obj_name}.{sub_obj}.{field}"
                        else:
                            path = f"{obj_name}.{field}"
                        paths.append(path)
        
        return sorted(paths)
    
    def _build_db_tree(self) -> Dict[str, Any]:
        """Build hierarchical tree of database paths"""
        tree = {}
        
        for path in self.db_paths:
            parts = path.split('.')
            current = tree
            
            for i, part in enumerate(parts):
                if part not in current:
                    current[part] = {}
                current = current[part]
        
        return tree
    
    def _build_field_patterns(self) -> dict:
        """Build patterns for common field mappings"""
        return {
            # Name fields
            r'(family|last)\s*name': ['beneficiary.Beneficiary.beneficiaryLastName', 
                                      'customer.SignatoryInfo.signatory_last_name',
                                      'attorney.attorneyInfo.lastName'],
            r'(given|first)\s*name': ['beneficiary.Beneficiary.beneficiaryFirstName',
                                      'customer.SignatoryInfo.signatory_first_name',
                                      'attorney.attorneyInfo.firstName'],
            r'middle\s*name': ['beneficiary.Beneficiary.beneficiaryMiddleName',
                              'customer.SignatoryInfo.signatory_middle_name',
                              'attorney.attorneyInfo.middleName'],
            
            # Contact fields
            r'email': ['beneficiary.ContactInfo.emailAddress',
                      'customer.SignatoryInfo.signatory_email',
                      'attorney.attorneyInfo.emailAddress'],
            r'(phone|telephone)': ['beneficiary.ContactInfo.daytimeTelephoneNumber',
                                  'customer.SignatoryInfo.signatory_work_phone',
                                  'attorney.attorneyInfo.workPhone'],
            r'mobile': ['beneficiary.ContactInfo.mobileTelephoneNumber',
                       'customer.SignatoryInfo.signatory_mobile_phone'],
            
            # Address fields
            r'street': ['beneficiary.MailingAddress.addressStreet',
                       'customer.Address.address_street',
                       'attorney.address.addressStreet',
                       'attorneyLawfirmDetails.address.addressStreet'],
            r'city': ['beneficiary.MailingAddress.addressCity',
                     'customer.Address.address_city',
                     'attorney.address.addressCity',
                     'attorneyLawfirmDetails.address.addressCity'],
            r'state': ['beneficiary.MailingAddress.addressState',
                      'customer.Address.address_state',
                      'attorney.address.addressState',
                      'attorneyLawfirmDetails.address.addressState'],
            r'zip': ['beneficiary.MailingAddress.addressZip',
                    'customer.Address.address_zip',
                    'attorney.address.addressZip',
                    'attorneyLawfirmDetails.address.addressZip'],
            
            # Other common fields
            r'a[\s\-]?number': ['beneficiary.Beneficiary.alienNumber'],
            r'alien\s*registration': ['beneficiary.Beneficiary.alienRegistrationNumber'],
            r'ssn|social\s*security': ['beneficiary.Beneficiary.beneficiarySsn'],
            r'date\s*of\s*birth': ['beneficiary.Beneficiary.beneficiaryDateOfBirth'],
            r'gender': ['beneficiary.Beneficiary.beneficiaryGender'],
            r'country\s*of\s*birth': ['beneficiary.Beneficiary.beneficiaryCountryOfBirth'],
            r'marital\s*status': ['beneficiary.Beneficiary.maritalStatus'],
            r'bar\s*number': ['attorney.attorneyInfo.barNumber', 'attorney.attorneyInfo.stateBarNumber'],
            r'law\s*firm': ['attorneyLawfirmDetails.lawfirmDetails.lawFirmName'],
            r'passport\s*number': ['beneficiary.PassportDetails.passportNumber'],
            r'visa\s*number': ['beneficiary.VisaDetails.visaNumber'],
            r'licensing\s*authority': ['attorney.attorneyInfo.licensingAuthority']
        }
    
    def extract_from_pdf(self, pdf_file) -> bool:
        """Extract fields from PDF organized by parts"""
        try:
            # Reset state
            st.session_state.fields = []
            st.session_state.fields_by_part = OrderedDict()
            st.session_state.seen_fields = set()
            st.session_state.part_structure = OrderedDict()
            st.session_state.extraction_stats = {
                'total_pages': 0,
                'total_fields': 0,
                'total_parts': 0,
                'extraction_time': 0,
                'errors': []
            }
            
            start_time = time.time()
            
            # Read PDF
            pdf_bytes = pdf_file.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            st.session_state.extraction_stats['total_pages'] = len(doc)
            
            # Detect form type
            st.session_state.form_info = self._detect_form_type(doc)
            
            # Extract fields with progress
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # First pass: analyze document structure and find parts
            status_text.text("Analyzing document structure...")
            part_mapping = self._analyze_document_structure(doc)
            
            # Second pass: extract fields organized by parts
            all_fields = []
            seen_widget_hashes = set()
            
            # Group pages by parts
            pages_by_part = defaultdict(list)
            for page_num, part_info in part_mapping.items():
                part_key = f"Part {part_info['number']}"
                pages_by_part[part_key].append((page_num, part_info))
            
            # Extract fields by part
            part_count = 0
            for part_name, pages in pages_by_part.items():
                part_count += 1
                progress = part_count / len(pages_by_part)
                progress_bar.progress(progress)
                status_text.text(f"Processing {part_name}...")
                
                part_fields = []
                
                for page_num, part_info in pages:
                    try:
                        page = doc[page_num]
                        widgets = page.widgets()
                        
                        if widgets:
                            for widget in widgets:
                                try:
                                    if widget and hasattr(widget, 'field_name') and widget.field_name:
                                        # Create field first to get its properties
                                        field = self._create_field_from_widget(
                                            widget, part_info, page_num + 1
                                        )
                                        
                                        if field:
                                            # Create unique identifier based on field properties
                                            field_identifier = f"{field.part_number}_{field.field_key}_{field.item_number}_{field.field_type}"
                                            widget_hash = hashlib.md5(field_identifier.encode()).hexdigest()
                                            
                                            # Check if we already have a similar field
                                            duplicate_found = False
                                            for existing_field in part_fields:
                                                # Check for exact duplicates (same key, item, and type)
                                                if (existing_field.field_key == field.field_key and 
                                                    existing_field.item_number == field.item_number and
                                                    existing_field.field_type == field.field_type):
                                                    duplicate_found = True
                                                    break
                                            
                                            # Only add if not a duplicate
                                            if not duplicate_found and widget_hash not in seen_widget_hashes:
                                                seen_widget_hashes.add(widget_hash)
                                                part_fields.append(field)
                                                
                                except Exception as e:
                                    st.session_state.extraction_stats['errors'].append(
                                        f"Widget error on page {page_num + 1}: {str(e)}"
                                    )
                    
                    except Exception as e:
                        st.session_state.extraction_stats['errors'].append(
                            f"Page error on page {page_num + 1}: {str(e)}"
                        )
                
                # Sort fields within part by item number
                part_fields.sort(key=lambda f: (
                    self._parse_item_number(f.item_number),
                    f.field_label
                ))
                
                all_fields.extend(part_fields)
                
                # Store fields by part
                if part_fields:
                    st.session_state.fields_by_part[part_name] = part_fields
                    
                    # Store part structure info
                    if pages:
                        st.session_state.part_structure[part_name] = {
                            'number': pages[0][1]['number'],
                            'title': pages[0][1].get('title', ''),
                            'field_count': len(part_fields),
                            'pages': [p[0] + 1 for p in pages]
                        }
            
            progress_bar.empty()
            status_text.empty()
            doc.close()
            
            # Store all fields
            st.session_state.fields = all_fields
            st.session_state.extraction_stats['total_fields'] = len(all_fields)
            st.session_state.extraction_stats['total_parts'] = len(st.session_state.fields_by_part)
            
            # Auto-categorize checkboxes and radios
            for field in all_fields:
                if field.field_type in ['checkbox', 'radio', 'button']:
                    field.to_questionnaire = True
            
            st.session_state.extraction_stats['extraction_time'] = time.time() - start_time
            st.session_state.pdf_processed = True
            
            return True
            
        except Exception as e:
            st.error(f"❌ Error processing PDF: {str(e)}")
            if st.session_state.debug_mode:
                st.code(traceback.format_exc())
            return False
    
    def _parse_item_number(self, item_number: str) -> tuple:
        """Parse item number for sorting (e.g., "1.a" -> (1, 'a'))"""
        if not item_number:
            return (999, '')
        
        match = re.match(r'(\d+)\.?([a-z]?)', item_number)
        if match:
            num = int(match.group(1))
            letter = match.group(2) or ''
            return (num, letter)
        return (999, item_number)
    
    def _detect_form_type(self, doc) -> dict:
        """Detect USCIS form type"""
        first_page_text = doc[0].get_text().upper()
        
        # Form mappings
        forms = {
            'I-90': 'Application to Replace Permanent Resident Card',
            'I-129': 'Petition for a Nonimmigrant Worker',
            'I-130': 'Petition for Alien Relative',
            'I-140': 'Immigrant Petition for Alien Worker',
            'I-485': 'Application to Register Permanent Residence',
            'I-539': 'Application to Extend/Change Nonimmigrant Status',
            'I-765': 'Application for Employment Authorization',
            'I-824': 'Application for Action on an Approved Application',
            'N-400': 'Application for Naturalization',
            'N-600': 'Application for Certificate of Citizenship',
            'G-28': 'Notice of Entry of Appearance as Attorney or Accredited Representative',
            'G-1145': 'E-Notification of Application/Petition Acceptance'
        }
        
        # Check for standard forms
        for form_num, title in forms.items():
            if form_num in first_page_text:
                return {
                    'form_number': form_num,
                    'form_title': title,
                    'pages': len(doc)
                }
        
        # Check for supplement forms
        if 'H CLASSIFICATION SUPPLEMENT' in first_page_text:
            return {
                'form_number': 'I-129H',
                'form_title': 'H Classification Supplement to Form I-129',
                'pages': len(doc)
            }
        
        return {
            'form_number': 'Unknown',
            'form_title': 'Unknown USCIS Form',
            'pages': len(doc)
        }
    
    def _analyze_document_structure(self, doc) -> dict:
        """Analyze document to find parts/sections"""
        part_mapping = {}
        current_part = {
            'number': 1,
            'name': 'Part 1',
            'title': ''
        }
        
        # Common patterns for parts
        patterns = [
            # Standard Part patterns
            r'Part\s+(\d+)[\.\s\-:]*([^\n]{0,100})',
            r'PART\s+(\d+)[\.\s\-:]*([^\n]{0,100})',
            # Section patterns
            r'Section\s+(\d+)[\.\s\-:]*([^\n]{0,100})',
            r'SECTION\s+(\d+)[\.\s\-:]*([^\n]{0,100})',
            # Specific form patterns (like G-28)
            r'Part\s+(\d+):\s*([^\n]{0,100})',
        ]
        
        for page_num in range(len(doc)):
            page_text = doc[page_num].get_text()
            
            # Look for part indicators
            found_new_part = False
            for pattern in patterns:
                matches = list(re.finditer(pattern, page_text, re.MULTILINE | re.IGNORECASE))
                if matches:
                    # Take the first match on the page
                    match = matches[0]
                    part_num = int(match.group(1))
                    part_title = match.group(2).strip() if match.group(2) else ""
                    
                    # Clean title
                    part_title = re.sub(r'\s+', ' ', part_title)
                    part_title = re.sub(r'[\.\s]+$', '', part_title)
                    
                    # Only update if it's a new part number
                    if part_num != current_part['number']:
                        current_part = {
                            'number': part_num,
                            'name': f"Part {part_num}",
                            'title': part_title
                        }
                        found_new_part = True
                    break
            
            part_mapping[page_num] = current_part.copy()
        
        return part_mapping
    
    def _create_field_from_widget(self, widget, part_info: dict, page: int) -> Optional[PDFField]:
        """Create field from widget with better naming"""
        try:
            widget_name = widget.field_name or ""
            if not widget_name:
                return None
            
            # Extract field info
            field_info = self._extract_field_info(widget_name)
            
            # Get widget type
            widget_type = widget.field_type if hasattr(widget, 'field_type') else 4
            field_type = self._map_widget_type(widget_type)
            
            # Extract item number from widget name or label
            item_number = ""
            question_key = ""
            
            # Look for patterns like "1a", "2.b", "3", etc. in the widget name
            item_patterns = [
                r'(?:^|[^\d])(\d+)\.([a-z])\b',  # Matches "1.a", "2.b"
                r'(?:^|[^\d])(\d+)([a-z])\b',     # Matches "1a", "2b"
                r'(?:^|[^\d])(\d+)\b(?![a-z])',   # Matches standalone numbers
            ]
            
            # Try to extract from original widget name first
            for pattern in item_patterns:
                match = re.search(pattern, widget_name, re.IGNORECASE)
                if match:
                    if len(match.groups()) == 2:
                        item_number = f"{match.group(1)}.{match.group(2)}"
                    else:
                        item_number = match.group(1)
                    break
            
            # If no item number found in widget name, try the label
            if not item_number:
                item_match = re.search(r'^(\d+)\.?([a-z]?)', field_info['label'])
                if item_match:
                    if item_match.group(2):
                        item_number = f"{item_match.group(1)}.{item_match.group(2)}"
                    else:
                        item_number = item_match.group(1)
            
            # Generate unique question key
            if item_number:
                # Include field key to make it unique
                clean_item = item_number.replace('.', '')
                question_key = f"pt{part_info['number']}_{clean_item}_{field_info['key'][:10]}"
            else:
                # Use field key with part number
                question_key = f"pt{part_info['number']}_{field_info['key']}"
            
            # Create unique field ID
            unique_hash = hashlib.md5(f"{widget_name}_{part_info['number']}_{page}".encode()).hexdigest()[:8]
            field_id = f"P{part_info['number']}_{field_info['key']}_{unique_hash}"
            
            # Get value
            value = ""
            if hasattr(widget, 'field_value') and widget.field_value:
                value = str(widget.field_value)
            
            return PDFField(
                widget_name=widget_name,
                field_id=field_id,
                field_key=field_info['key'],
                part_number=part_info['number'],
                part_name=part_info['name'],
                part_title=part_info.get('title', ''),
                field_label=field_info['label'],
                field_type=field_type,
                page=page,
                value=value,
                item_number=item_number,
                question_key=question_key
            )
            
        except Exception as e:
            if st.session_state.debug_mode:
                st.warning(f"Failed to create field: {str(e)}")
            return None
    
    def _extract_field_info(self, widget_name: str) -> dict:
        """Extract field information from widget name"""
        # Clean widget name
        clean_name = widget_name
        
        # Remove common prefixes
        prefixes = [
            r'form\d*\[?\d*\]?\.',
            r'#subform\[?\d*\]?\.',
            r'Page\d+\[?\d*\]?\.',
            r'Part\d+\[?\d*\]?\.',
            r'topmostSubform\[?\d*\]?\.',
            r'#area\[?\d*\]?\.',
            r'TextField\[?\d*\]?\.',
            r'Subform\[?\d*\]?\.',
            r'Sub[pP]\d+',
            r'CheckBox\[?\d*\]?\.'
        ]
        
        for prefix in prefixes:
            clean_name = re.sub(prefix, '', clean_name, flags=re.IGNORECASE)
        
        # Remove array indices
        clean_name = re.sub(r'\[\d+\]', '', clean_name)
        
        # Extract parts
        parts = clean_name.split('.')
        last_part = parts[-1] if parts else clean_name
        
        # Clean up the last part
        last_part = last_part.strip()
        
        # Generate field key (short identifier)
        field_key = self._generate_field_key(last_part)
        
        # Generate human-readable label
        field_label = self._generate_field_label(last_part)
        
        return {
            'key': field_key,
            'label': field_label,
            'original': widget_name
        }
    
    def _generate_field_key(self, name: str) -> str:
        """Generate short field key"""
        # Remove special characters
        key = re.sub(r'[^\w]', '_', name)
        
        # Remove common checkbox/field suffixes
        key = re.sub(r'(?i)(checkbox|check|box|field|text)\d*
    
    def _generate_field_label(self, name: str) -> str:
        """Generate human-readable label"""
        # Remove common suffixes first
        cleaned_name = re.sub(r'(?i)(checkbox|check|box|field|text)\d*
    
    def _map_widget_type(self, widget_type: int) -> str:
        """Map PDF widget type to field type"""
        type_map = {
            1: "button",
            2: "checkbox",
            3: "radio",
            4: "text",
            5: "dropdown",
            6: "list",
            7: "signature"
        }
        return type_map.get(widget_type, "text")
    
    def suggest_mapping(self, field: PDFField) -> Optional[str]:
        """Suggest database mapping for field"""
        label_lower = field.field_label.lower()
        key_lower = field.field_key.lower()
        
        # Try pattern matching with both label and key
        for pattern, suggestions in self.field_patterns.items():
            if re.search(pattern, label_lower) or re.search(pattern, key_lower):
                # Return first matching suggestion
                for suggestion in suggestions:
                    if suggestion in self.db_paths:
                        return suggestion
        
        # Try exact field name matching
        for db_path in self.db_paths:
            path_parts = db_path.split('.')
            field_name = path_parts[-1].lower()
            
            # Check both label and key
            if field_name in label_lower.replace(' ', '').lower() or field_name in key_lower:
                return db_path
        
        return None
    
    def generate_typescript(self) -> str:
        """Generate TypeScript export"""
        form_name = st.session_state.form_info.get('form_number', 'Form').replace('-', '')
        
        # Group fields
        sections = {
            'customerData': {},
            'beneficiaryData': {},
            'attorneyData': {},
            'questionnaireData': {},
            'caseData': {},
            'defaultData': {},
            'conditionalData': {}
        }
        
        # Track used keys to avoid duplicates
        used_keys = set()
        
        for field in st.session_state.fields:
            if field.is_mapped and field.db_mapping:
                # Determine section
                if field.db_mapping.startswith('customer.'):
                    section = 'customerData'
                elif field.db_mapping.startswith('beneficiary.'):
                    section = 'beneficiaryData'
                elif field.db_mapping.startswith('attorney.') or field.db_mapping.startswith('attorneyLawfirmDetails.'):
                    section = 'attorneyData'
                elif field.db_mapping.startswith('case.'):
                    section = 'caseData'
                else:
                    continue
                
                # Add field
                suffix = self._get_ts_suffix(field.field_type)
                sections[section][field.field_key] = f"{field.db_mapping}{suffix}"
            
            elif field.to_questionnaire:
                # Use question_key if available and unique
                key = field.question_key if field.question_key else field.field_key
                
                # Ensure unique key
                base_key = key
                counter = 1
                while key in used_keys:
                    key = f"{base_key}_{counter}"
                    counter += 1
                
                used_keys.add(key)
                sections['questionnaireData'][key] = f"{field.field_key}:ConditionBox"
        
        # Generate TypeScript
        ts = f'export const {form_name} = {{\n'
        ts += f'    "formname": "{form_name}",\n'
        
        # Add sections
        for section_name, fields in sections.items():
            if section_name == 'conditionalData':
                continue  # Handle separately
            
            if fields:
                ts += f'    "{section_name}": {{\n'
                field_entries = []
                for key, value in fields.items():
                    field_entries.append(f'        "{key}": "{value}"')
                ts += ',\n'.join(field_entries)
                ts += '\n    },\n'
            else:
                ts += f'    "{section_name}": null,\n'
        
        # Add conditional data (empty for now)
        ts += '    "conditionalData": {},\n'
        
        # Add PDF name
        ts += f'    "pdfName": "{st.session_state.form_info.get("form_number", "Unknown")}"\n'
        ts += '};\n\n'
        ts += f'export default {form_name};'
        
        return ts
    
    def _get_ts_suffix(self, field_type: str) -> str:
        """Get TypeScript suffix for field type"""
        suffix_map = {
            'text': ':TextBox',
            'checkbox': ':CheckBox',
            'radio': ':RadioBox',
            'dropdown': ':DropdownBox',
            'signature': ':SignatureBox',
            'date': ':Date',
            'button': ':ButtonBox'
        }
        return suffix_map.get(field_type, ':TextBox')
    
    def generate_json(self) -> str:
        """Generate JSON export for questionnaire"""
        controls = []
        
        # Add fields by part
        for part_name, fields in st.session_state.fields_by_part.items():
            # Get part info
            part_info = st.session_state.part_structure.get(part_name, {})
            
            # Get questionnaire fields
            quest_fields = [f for f in fields if f.to_questionnaire]
            
            if quest_fields:
                # Add part title
                title_text = f"{part_name}"
                if part_info.get('title'):
                    title_text += f": {part_info['title']}"
                
                controls.append({
                    "name": f"{part_name.lower().replace(' ', '_')}_title",
                    "label": title_text,
                    "type": "title",
                    "validators": {},
                    "style": {"col": "12"}
                })
                
                # Track used names to avoid duplicates
                used_names = set()
                
                # Add fields
                for idx, field in enumerate(quest_fields):
                    # Use question_key if available and unique, otherwise generate unique name
                    if field.question_key and field.question_key not in used_names:
                        control_name = field.question_key
                    else:
                        # Generate unique name
                        base_name = field.field_key
                        counter = 1
                        control_name = base_name
                        while control_name in used_names:
                            control_name = f"{base_name}_{counter}"
                            counter += 1
                    
                    used_names.add(control_name)
                    
                    control = {
                        "name": control_name,
                        "label": field.field_label if not field.item_number else f"{field.item_number}. {field.field_label}",
                        "type": "colorSwitch" if field.field_type in ["checkbox", "radio"] else field.field_type,
                        "validators": {}
                    }
                    
                    # Add field-specific properties
                    if field.field_type == "text":
                        control["style"] = {"col": "7"}
                    elif field.field_type in ["checkbox", "radio"]:
                        control["style"] = {"col": "12"}
                        if field.field_type == "radio":
                            control["id"] = control_name
                            control["value"] = "1"
                    
                    controls.append(control)
        
        return json.dumps({"controls": controls}, indent=2)

def render_mapping_interface(extractor: FieldExtractor):
    """Render the enhanced field mapping interface organized by parts"""
    st.markdown("## 🎯 Field Mapping by Parts")
    
    # Top controls
    with st.container():
        st.markdown('<div class="part-selector">', unsafe_allow_html=True)
        
        col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
        
        with col1:
            # Part selector
            part_options = ['All Parts'] + list(st.session_state.fields_by_part.keys())
            selected_part = st.selectbox(
                "📑 Select Part",
                part_options,
                index=part_options.index(st.session_state.selected_part) if st.session_state.selected_part in part_options else 0,
                key="part_selector"
            )
            st.session_state.selected_part = selected_part
        
        with col2:
            # Mapping filter
            mapping_filter = st.selectbox(
                "🔍 Filter by Status",
                ["All Fields", "Mapped", "Unmapped", "Questionnaire"],
                key="mapping_filter_select"
            )
            st.session_state.mapping_filter = mapping_filter.lower().replace(' fields', '').replace(' ', '_')
        
        with col3:
            # Database browser toggle
            st.session_state.show_db_browser = st.checkbox(
                "🗂️ Show DB Browser",
                value=st.session_state.show_db_browser,
                help="Show database structure browser"
            )
        
        with col4:
            # Field count
            if selected_part == 'All Parts':
                total_fields = len(st.session_state.fields)
            else:
                total_fields = len(st.session_state.fields_by_part.get(selected_part, []))
            
            mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
            st.metric("Progress", f"{mapped}/{total_fields}", f"{mapped/total_fields*100:.0f}%")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Quick actions
    st.markdown("### ⚡ Quick Actions")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🤖 Auto-Map Current View", use_container_width=True):
            fields_to_map = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_map = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            mapped_count = 0
            for field in fields_to_map:
                if not field.is_mapped and not field.to_questionnaire and field.field_type == 'text':
                    suggestion = extractor.suggest_mapping(field)
                    if suggestion:
                        field.db_mapping = suggestion
                        field.is_mapped = True
                        mapped_count += 1
            st.success(f"Auto-mapped {mapped_count} fields!")
            st.rerun()
    
    with col2:
        if st.button("📋 All Checkboxes → Quest", use_container_width=True):
            fields_to_move = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_move = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            count = 0
            for field in fields_to_move:
                if field.field_type in ['checkbox', 'radio'] and not field.to_questionnaire:
                    field.to_questionnaire = True
                    field.is_mapped = False
                    count += 1
            st.success(f"Moved {count} fields to questionnaire!")
            st.rerun()
    
    with col3:
        if st.button("🔄 Reset Current View", use_container_width=True):
            fields_to_reset = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_reset = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            for field in fields_to_reset:
                field.is_mapped = False
                field.db_mapping = None
                field.to_questionnaire = field.field_type in ['checkbox', 'radio', 'button']
            st.success("Reset complete!")
            st.rerun()
    
    with col4:
        unmapped = sum(1 for f in st.session_state.fields if not f.is_mapped and not f.to_questionnaire)
        if st.button(f"📋 All Unmapped → Quest ({unmapped})", use_container_width=True):
            fields_to_move = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_move = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            count = 0
            for field in fields_to_move:
                if not field.is_mapped and not field.to_questionnaire:
                    field.to_questionnaire = True
                    count += 1
            st.success(f"Moved {count} fields to questionnaire!")
            st.rerun()
    
    # Database object browser
    if st.session_state.show_db_browser:
        with st.expander("🗂️ Database Structure Browser", expanded=True):
            st.markdown("### Available Database Paths")
            st.caption("Click any path to copy it")
            
            # Create tabs for each main object
            tabs = st.tabs(list(DB_OBJECTS.keys()))
            
            for i, (obj_name, tab) in enumerate(zip(DB_OBJECTS.keys(), tabs)):
                with tab:
                    for sub_obj, fields in DB_OBJECTS[obj_name].items():
                        if sub_obj:
                            st.markdown(f"**{sub_obj}:**")
                        
                        # Display fields in columns
                        field_cols = st.columns(3)
                        for j, field in enumerate(fields):
                            col_idx = j % 3
                            with field_cols[col_idx]:
                                if sub_obj:
                                    path = f"{obj_name}.{sub_obj}.{field}"
                                else:
                                    path = f"{obj_name}.{field}"
                                
                                if st.button(f"📋 {field}", key=f"copy_{path}", use_container_width=True):
                                    st.code(path, language="text")
    
    # Field mapping interface organized by parts
    st.markdown("### 📝 Field Mappings by Part")
    
    # Get parts to display
    if st.session_state.selected_part == 'All Parts':
        parts_to_show = st.session_state.fields_by_part.items()
    else:
        parts_to_show = [(st.session_state.selected_part, 
                         st.session_state.fields_by_part.get(st.session_state.selected_part, []))]
    
    # Display each part
    for part_name, fields in parts_to_show:
        # Filter fields based on mapping filter
        if st.session_state.mapping_filter == 'mapped':
            display_fields = [f for f in fields if f.is_mapped]
        elif st.session_state.mapping_filter == 'unmapped':
            display_fields = [f for f in fields if not f.is_mapped and not f.to_questionnaire]
        elif st.session_state.mapping_filter == 'questionnaire':
            display_fields = [f for f in fields if f.to_questionnaire]
        else:
            display_fields = fields
        
        if not display_fields:
            continue
        
        # Get part info
        part_info = st.session_state.part_structure.get(part_name, {})
        
        # Part header with stats
        part_mapped = sum(1 for f in fields if f.is_mapped)
        part_quest = sum(1 for f in fields if f.to_questionnaire)
        part_unmapped = len(fields) - part_mapped - part_quest
        
        with st.container():
            st.markdown(f'''
            <div class="part-header">
                <strong>{part_name}</strong> {part_info.get('title', '')} 
                <br>
                <small>Total: {len(fields)} | Mapped: {part_mapped} | Questionnaire: {part_quest} | Unmapped: {part_unmapped}</small>
                <br>
                <small>Pages: {', '.join(map(str, part_info.get('pages', [])))}</small>
            </div>
            ''', unsafe_allow_html=True)
        
        # Display fields for this part
        for idx, field in enumerate(display_fields):
            with st.container():
                st.markdown('<div class="mapping-row">', unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    # Field info
                    display_label = field.field_label
                    if field.item_number:
                        display_label = f"{field.item_number}. {display_label}"
                    
                    st.markdown(f'<div class="field-label">{display_label}</div>', unsafe_allow_html=True)
                    
                    # Build field metadata
                    type_class = f"field-type {field.field_type}"
                    meta_parts = [
                        f'<span class="{type_class}">{field.field_type.upper()}</span>',
                        f'Field: {field.field_key}',
                        f'Page {field.page}'
                    ]
                    
                    # Only show quest key if it's different from field key
                    if field.to_questionnaire and field.question_key and field.question_key != field.field_key:
                        quest_key_short = field.question_key.split('_')[-1] if '_' in field.question_key else field.question_key
                        meta_parts.append(f'Quest: {quest_key_short}')
                    
                    st.markdown(f"""
                    <div class="field-meta">
                        {' • '.join(meta_parts)}
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    # Create unique key for this field
                    unique_key = f"{part_name}_{field.field_id}_{idx}"
                    
                    col2a, col2b = st.columns([3, 1])
                    
                    with col2a:
                        # Database mapping dropdown
                        grouped_options = {
                            "Actions": ["-- Select Database Field --", "📋 Move to Questionnaire"],
                            "beneficiary": [],
                            "petitioner": [],
                            "customer": [],
                            "attorney": [],
                            "attorneyLawfirmDetails": [],
                            "case": [],
                            "employment": []
                        }
                        
                        # Group database paths
                        for path in extractor.db_paths:
                            obj_name = path.split('.')[0]
                            if obj_name in grouped_options:
                                grouped_options[obj_name].append(path)
                        
                        # Build flat list with separators
                        options = []
                        for group, items in grouped_options.items():
                            if items:
                                if options:  # Add separator between groups
                                    options.append(f"── {group} ──")
                                options.extend(items)
                        
                        # Current selection
                        if field.is_mapped and field.db_mapping:
                            current_value = field.db_mapping
                        elif field.to_questionnaire:
                            current_value = "📋 Move to Questionnaire"
                        else:
                            # Try to get suggestion
                            suggestion = extractor.suggest_mapping(field)
                            current_value = suggestion if suggestion else "-- Select Database Field --"
                        
                        # Find index
                        try:
                            current_index = options.index(current_value)
                        except ValueError:
                            current_index = 0
                        
                        selected = st.selectbox(
                            "Database Mapping",
                            options,
                            index=current_index,
                            key=f"map_{unique_key}",
                            label_visibility="collapsed"
                        )
                        
                        # Handle selection
                        if selected != current_value and not selected.startswith("──"):
                            if selected == "📋 Move to Questionnaire":
                                field.to_questionnaire = True
                                field.is_mapped = False
                                field.db_mapping = None
                            elif selected != "-- Select Database Field --":
                                field.db_mapping = selected
                                field.is_mapped = True
                                field.to_questionnaire = False
                            st.rerun()
                    
                    with col2b:
                        # Quick questionnaire toggle
                        if st.button("📋", key=f"quest_btn_{unique_key}", 
                                   help="Quick add to questionnaire",
                                   use_container_width=True):
                            field.to_questionnaire = True
                            field.is_mapped = False
                            field.db_mapping = None
                            st.rerun()
                
                with col3:
                    # Status
                    status = field.get_status()
                    if "Mapped" in status:
                        badge_class = "status-mapped"
                    elif "Questionnaire" in status:
                        badge_class = "status-questionnaire"
                    else:
                        badge_class = "status-unmapped"
                    
                    st.markdown(f'<span class="status-badge {badge_class}">{status}</span>', 
                              unsafe_allow_html=True)
                
                st.markdown('</div>', unsafe_allow_html=True)
        
        # Add spacing between parts
        st.markdown("<br>", unsafe_allow_html=True)

def main():
    """Main application"""
    st.markdown("# 🤖 USCIS Form Reader Pro")
    st.markdown("### Complete PDF Form Field Extraction & Mapping Solution")
    
    # Initialize extractor
    extractor = FieldExtractor()
    
    # Sidebar
    with st.sidebar:
        st.markdown("## ⚙️ Settings")
        st.session_state.debug_mode = st.checkbox("Debug Mode", value=False)
        
        if st.session_state.pdf_processed:
            st.markdown("---")
            st.markdown("### 📊 Statistics")
            stats = st.session_state.extraction_stats
            st.metric("Total Pages", stats.get('total_pages', 0))
            st.metric("Total Parts", stats.get('total_parts', 0))
            st.metric("Total Fields", stats.get('total_fields', 0))
            st.metric("Extraction Time", f"{stats.get('extraction_time', 0):.2f}s")
            
            if stats.get('errors'):
                st.warning(f"{len(stats['errors'])} errors occurred")
                with st.expander("View Errors"):
                    for error in stats['errors']:
                        st.text(error)
            
            # Field summary
            total = len(st.session_state.fields)
            mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
            quest = sum(1 for f in st.session_state.fields if f.to_questionnaire)
            
            st.markdown("---")
            st.markdown("### 📈 Mapping Progress")
            st.metric("Mapped to DB", f"{mapped} ({mapped/total*100:.1f}%)")
            st.metric("In Questionnaire", f"{quest} ({quest/total*100:.1f}%)")
            st.metric("Unmapped", f"{total - mapped - quest}")
            
            # Progress bar
            progress = (mapped + quest) / total if total > 0 else 0
            st.progress(progress)
            
            # Part breakdown
            st.markdown("---")
            st.markdown("### 📑 Parts Overview")
            for part_name, part_info in st.session_state.part_structure.items():
                fields = st.session_state.fields_by_part.get(part_name, [])
                mapped = sum(1 for f in fields if f.is_mapped)
                quest = sum(1 for f in fields if f.to_questionnaire)
                st.caption(f"{part_name}: {len(fields)} fields ({mapped} mapped, {quest} quest)")
    
    # Main tabs
    tab1, tab2, tab3 = st.tabs(["📤 Upload & Extract", "🎯 Map Fields", "📥 Export & Download"])
    
    with tab1:
        st.markdown("## Upload USCIS PDF Form")
        
        uploaded_file = st.file_uploader(
            "Choose a USCIS PDF form",
            type=['pdf'],
            help="Upload any fillable USCIS form (I-90, I-129, G-28, etc.)",
            key="pdf_uploader"
        )
        
        if uploaded_file:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                if st.button("🚀 Extract Fields by Parts", type="primary", use_container_width=True):
                    with st.spinner("Analyzing PDF structure and extracting fields by parts..."):
                        if extractor.extract_from_pdf(uploaded_file):
                            st.success(f"""
                            ✅ Successfully extracted {len(st.session_state.fields)} fields from {st.session_state.form_info.get('form_number', 'form')}!
                            
                            Found {len(st.session_state.fields_by_part)} parts with fields.
                            """)
                            
                            # Show extraction summary
                            with st.expander("📊 Extraction Summary", expanded=True):
                                for part_name, fields in st.session_state.fields_by_part.items():
                                    part_info = st.session_state.part_structure.get(part_name, {})
                                    
                                    st.write(f"**{part_name}** {part_info.get('title', '')}")
                                    st.write(f"- Fields: {len(fields)}")
                                    st.write(f"- Pages: {', '.join(map(str, part_info.get('pages', [])))}")
                                    
                                    # Field type breakdown
                                    types = defaultdict(int)
                                    for field in fields:
                                        types[field.field_type] += 1
                                    
                                    type_summary = ", ".join([f"{count} {ftype}" for ftype, count in types.items()])
                                    st.caption(f"Field types: {type_summary}")
                                    st.divider()
            
            with col2:
                if st.session_state.pdf_processed:
                    if st.button("🔄 Reset", type="secondary", use_container_width=True):
                        # Clear all session state
                        for key in list(st.session_state.keys()):
                            if key != 'debug_mode':
                                del st.session_state[key]
                        extractor.init_session_state()
                        st.rerun()
    
    with tab2:
        if not st.session_state.pdf_processed:
            st.info("👆 Please upload and extract a PDF form first.")
        else:
            render_mapping_interface(extractor)
    
    with tab3:
        if not st.session_state.pdf_processed:
            st.info("👆 Please upload and extract a PDF form first.")
        else:
            st.markdown("## 📥 Export & Download")
            
            # Summary
            total = len(st.session_state.fields)
            mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
            quest = sum(1 for f in st.session_state.fields if f.to_questionnaire)
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Fields", total)
            col2.metric("Mapped to Database", mapped)
            col3.metric("In Questionnaire", quest)
            
            st.markdown("---")
            
            # Export options
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 📄 TypeScript Export")
                st.markdown("Database mappings for your application")
                
                ts_code = extractor.generate_typescript()
                
                st.download_button(
                    label="⬇️ Download TypeScript File",
                    data=ts_code,
                    file_name=f"{st.session_state.form_info.get('form_number', 'form')}.ts",
                    mime="text/typescript",
                    use_container_width=True
                )
                
                with st.expander("Preview TypeScript"):
                    st.code(ts_code, language="typescript")
            
            with col2:
                st.markdown("### 📋 JSON Export")
                st.markdown("Questionnaire configuration")
                
                json_code = extractor.generate_json()
                
                st.download_button(
                    label="⬇️ Download JSON File",
                    data=json_code,
                    file_name=f"{st.session_state.form_info.get('form_number', 'form')}-questionnaire.json",
                    mime="application/json",
                    use_container_width=True
                )
                
                with st.expander("Preview JSON"):
                    st.code(json_code, language="json")
            
            # Combined export
            st.markdown("---")
            if st.button("📦 Download Both Files", type="primary", use_container_width=True):
                st.markdown("### Downloads Ready:")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button(
                        "TypeScript (.ts)",
                        extractor.generate_typescript(),
                        f"{st.session_state.form_info.get('form_number', 'form')}.ts",
                        mime="text/typescript"
                    )
                with col2:
                    st.download_button(
                        "JSON (.json)",
                        extractor.generate_json(),
                        f"{st.session_state.form_info.get('form_number', 'form')}-questionnaire.json",
                        mime="application/json"
                    )

if __name__ == "__main__":
    main()
, '', key)
        key = re.sub(r'_+
    
    def _generate_field_label(self, name: str) -> str:
        """Generate human-readable label"""
        # Common label mappings
        label_map = {
            'familyname': 'Family Name (Last Name)',
            'lastname': 'Last Name',
            'givenname': 'Given Name (First Name)', 
            'firstname': 'First Name',
            'middlename': 'Middle Name',
            'anumber': 'Alien Registration Number (A-Number)',
            'uscisaccount': 'USCIS Online Account Number',
            'dateofbirth': 'Date of Birth',
            'ssn': 'Social Security Number',
            'email': 'Email Address',
            'phone': 'Phone Number',
            'daytimephone': 'Daytime Phone Number',
            'mobile': 'Mobile Phone Number',
            'street': 'Street Address',
            'city': 'City or Town',
            'state': 'State',
            'zip': 'ZIP Code',
            'country': 'Country',
            'barnumber': 'Bar Number',
            'statebarnumber': 'State Bar Number',
            'lawfirm': 'Law Firm Name',
            'lawfirmname': 'Law Firm Name',
            'licensingauthority': 'Licensing Authority',
            'workphone': 'Work Phone Number',
            'faxnumber': 'Fax Number'
        }
        
        # Check for exact match
        name_lower = name.lower().replace('_', '').replace('-', '').replace(' ', '')
        for key, label in label_map.items():
            if key in name_lower or name_lower in key:
                return label
        
        # Convert to title case
        label = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
        label = label.replace('_', ' ').replace('-', ' ')
        label = ' '.join(label.split())
        label = label.title()
        
        return label
    
    def _map_widget_type(self, widget_type: int) -> str:
        """Map PDF widget type to field type"""
        type_map = {
            1: "button",
            2: "checkbox",
            3: "radio",
            4: "text",
            5: "dropdown",
            6: "list",
            7: "signature"
        }
        return type_map.get(widget_type, "text")
    
    def suggest_mapping(self, field: PDFField) -> Optional[str]:
        """Suggest database mapping for field"""
        label_lower = field.field_label.lower()
        key_lower = field.field_key.lower()
        
        # Try pattern matching with both label and key
        for pattern, suggestions in self.field_patterns.items():
            if re.search(pattern, label_lower) or re.search(pattern, key_lower):
                # Return first matching suggestion
                for suggestion in suggestions:
                    if suggestion in self.db_paths:
                        return suggestion
        
        # Try exact field name matching
        for db_path in self.db_paths:
            path_parts = db_path.split('.')
            field_name = path_parts[-1].lower()
            
            # Check both label and key
            if field_name in label_lower.replace(' ', '').lower() or field_name in key_lower:
                return db_path
        
        return None
    
    def generate_typescript(self) -> str:
        """Generate TypeScript export"""
        form_name = st.session_state.form_info.get('form_number', 'Form').replace('-', '')
        
        # Group fields
        sections = {
            'customerData': {},
            'beneficiaryData': {},
            'attorneyData': {},
            'questionnaireData': {},
            'caseData': {},
            'defaultData': {},
            'conditionalData': {}
        }
        
        for field in st.session_state.fields:
            if field.is_mapped and field.db_mapping:
                # Determine section
                if field.db_mapping.startswith('customer.'):
                    section = 'customerData'
                elif field.db_mapping.startswith('beneficiary.'):
                    section = 'beneficiaryData'
                elif field.db_mapping.startswith('attorney.') or field.db_mapping.startswith('attorneyLawfirmDetails.'):
                    section = 'attorneyData'
                elif field.db_mapping.startswith('case.'):
                    section = 'caseData'
                else:
                    continue
                
                # Add field
                suffix = self._get_ts_suffix(field.field_type)
                sections[section][field.field_key] = f"{field.db_mapping}{suffix}"
            
            elif field.to_questionnaire:
                # Use question_key for questionnaire items
                key = field.question_key if field.question_key else field.field_key
                sections['questionnaireData'][key] = f"{field.field_key}:ConditionBox"
        
        # Generate TypeScript
        ts = f'export const {form_name} = {{\n'
        ts += f'    "formname": "{form_name}",\n'
        
        # Add sections
        for section_name, fields in sections.items():
            if section_name == 'conditionalData':
                continue  # Handle separately
            
            if fields:
                ts += f'    "{section_name}": {{\n'
                field_entries = []
                for key, value in fields.items():
                    field_entries.append(f'        "{key}": "{value}"')
                ts += ',\n'.join(field_entries)
                ts += '\n    },\n'
            else:
                ts += f'    "{section_name}": null,\n'
        
        # Add conditional data (empty for now)
        ts += '    "conditionalData": {},\n'
        
        # Add PDF name
        ts += f'    "pdfName": "{st.session_state.form_info.get("form_number", "Unknown")}"\n'
        ts += '};\n\n'
        ts += f'export default {form_name};'
        
        return ts
    
    def _get_ts_suffix(self, field_type: str) -> str:
        """Get TypeScript suffix for field type"""
        suffix_map = {
            'text': ':TextBox',
            'checkbox': ':CheckBox',
            'radio': ':RadioBox',
            'dropdown': ':DropdownBox',
            'signature': ':SignatureBox',
            'date': ':Date',
            'button': ':ButtonBox'
        }
        return suffix_map.get(field_type, ':TextBox')
    
    def generate_json(self) -> str:
        """Generate JSON export for questionnaire"""
        controls = []
        
        # Add fields by part
        for part_name, fields in st.session_state.fields_by_part.items():
            # Get part info
            part_info = st.session_state.part_structure.get(part_name, {})
            
            # Get questionnaire fields
            quest_fields = [f for f in fields if f.to_questionnaire]
            
            if quest_fields:
                # Add part title
                title_text = f"{part_name}"
                if part_info.get('title'):
                    title_text += f": {part_info['title']}"
                
                controls.append({
                    "name": f"{part_name.lower().replace(' ', '_')}_title",
                    "label": title_text,
                    "type": "title",
                    "validators": {},
                    "style": {"col": "12"}
                })
                
                # Add fields
                for field in quest_fields:
                    control = {
                        "name": field.field_key,
                        "label": field.field_label,
                        "type": "colorSwitch" if field.field_type in ["checkbox", "radio"] else field.field_type,
                        "validators": {}
                    }
                    
                    # Add field-specific properties
                    if field.field_type == "text":
                        control["style"] = {"col": "7"}
                    elif field.field_type in ["checkbox", "radio"]:
                        control["style"] = {"col": "12"}
                        if field.field_type == "radio":
                            control["id"] = field.field_key
                            control["value"] = "1"
                    
                    controls.append(control)
        
        return json.dumps({"controls": controls}, indent=2)

def render_mapping_interface(extractor: FieldExtractor):
    """Render the enhanced field mapping interface organized by parts"""
    st.markdown("## 🎯 Field Mapping by Parts")
    
    # Top controls
    with st.container():
        st.markdown('<div class="part-selector">', unsafe_allow_html=True)
        
        col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
        
        with col1:
            # Part selector
            part_options = ['All Parts'] + list(st.session_state.fields_by_part.keys())
            selected_part = st.selectbox(
                "📑 Select Part",
                part_options,
                index=part_options.index(st.session_state.selected_part) if st.session_state.selected_part in part_options else 0,
                key="part_selector"
            )
            st.session_state.selected_part = selected_part
        
        with col2:
            # Mapping filter
            mapping_filter = st.selectbox(
                "🔍 Filter by Status",
                ["All Fields", "Mapped", "Unmapped", "Questionnaire"],
                key="mapping_filter_select"
            )
            st.session_state.mapping_filter = mapping_filter.lower().replace(' fields', '').replace(' ', '_')
        
        with col3:
            # Database browser toggle
            st.session_state.show_db_browser = st.checkbox(
                "🗂️ Show DB Browser",
                value=st.session_state.show_db_browser,
                help="Show database structure browser"
            )
        
        with col4:
            # Field count
            if selected_part == 'All Parts':
                total_fields = len(st.session_state.fields)
            else:
                total_fields = len(st.session_state.fields_by_part.get(selected_part, []))
            
            mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
            st.metric("Progress", f"{mapped}/{total_fields}", f"{mapped/total_fields*100:.0f}%")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Quick actions
    st.markdown("### ⚡ Quick Actions")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🤖 Auto-Map Current View", use_container_width=True):
            fields_to_map = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_map = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            mapped_count = 0
            for field in fields_to_map:
                if not field.is_mapped and not field.to_questionnaire and field.field_type == 'text':
                    suggestion = extractor.suggest_mapping(field)
                    if suggestion:
                        field.db_mapping = suggestion
                        field.is_mapped = True
                        mapped_count += 1
            st.success(f"Auto-mapped {mapped_count} fields!")
            st.rerun()
    
    with col2:
        if st.button("📋 All Checkboxes → Quest", use_container_width=True):
            fields_to_move = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_move = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            count = 0
            for field in fields_to_move:
                if field.field_type in ['checkbox', 'radio'] and not field.to_questionnaire:
                    field.to_questionnaire = True
                    field.is_mapped = False
                    count += 1
            st.success(f"Moved {count} fields to questionnaire!")
            st.rerun()
    
    with col3:
        if st.button("🔄 Reset Current View", use_container_width=True):
            fields_to_reset = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_reset = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            for field in fields_to_reset:
                field.is_mapped = False
                field.db_mapping = None
                field.to_questionnaire = field.field_type in ['checkbox', 'radio', 'button']
            st.success("Reset complete!")
            st.rerun()
    
    with col4:
        unmapped = sum(1 for f in st.session_state.fields if not f.is_mapped and not f.to_questionnaire)
        if st.button(f"📋 All Unmapped → Quest ({unmapped})", use_container_width=True):
            fields_to_move = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_move = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            count = 0
            for field in fields_to_move:
                if not field.is_mapped and not field.to_questionnaire:
                    field.to_questionnaire = True
                    count += 1
            st.success(f"Moved {count} fields to questionnaire!")
            st.rerun()
    
    # Database object browser
    if st.session_state.show_db_browser:
        with st.expander("🗂️ Database Structure Browser", expanded=True):
            st.markdown("### Available Database Paths")
            st.caption("Click any path to copy it")
            
            # Create tabs for each main object
            tabs = st.tabs(list(DB_OBJECTS.keys()))
            
            for i, (obj_name, tab) in enumerate(zip(DB_OBJECTS.keys(), tabs)):
                with tab:
                    for sub_obj, fields in DB_OBJECTS[obj_name].items():
                        if sub_obj:
                            st.markdown(f"**{sub_obj}:**")
                        
                        # Display fields in columns
                        field_cols = st.columns(3)
                        for j, field in enumerate(fields):
                            col_idx = j % 3
                            with field_cols[col_idx]:
                                if sub_obj:
                                    path = f"{obj_name}.{sub_obj}.{field}"
                                else:
                                    path = f"{obj_name}.{field}"
                                
                                if st.button(f"📋 {field}", key=f"copy_{path}", use_container_width=True):
                                    st.code(path, language="text")
    
    # Field mapping interface organized by parts
    st.markdown("### 📝 Field Mappings by Part")
    
    # Get parts to display
    if st.session_state.selected_part == 'All Parts':
        parts_to_show = st.session_state.fields_by_part.items()
    else:
        parts_to_show = [(st.session_state.selected_part, 
                         st.session_state.fields_by_part.get(st.session_state.selected_part, []))]
    
    # Display each part
    for part_name, fields in parts_to_show:
        # Filter fields based on mapping filter
        if st.session_state.mapping_filter == 'mapped':
            display_fields = [f for f in fields if f.is_mapped]
        elif st.session_state.mapping_filter == 'unmapped':
            display_fields = [f for f in fields if not f.is_mapped and not f.to_questionnaire]
        elif st.session_state.mapping_filter == 'questionnaire':
            display_fields = [f for f in fields if f.to_questionnaire]
        else:
            display_fields = fields
        
        if not display_fields:
            continue
        
        # Get part info
        part_info = st.session_state.part_structure.get(part_name, {})
        
        # Part header with stats
        part_mapped = sum(1 for f in fields if f.is_mapped)
        part_quest = sum(1 for f in fields if f.to_questionnaire)
        part_unmapped = len(fields) - part_mapped - part_quest
        
        with st.container():
            st.markdown(f'''
            <div class="part-header">
                <strong>{part_name}</strong> {part_info.get('title', '')} 
                <br>
                <small>Total: {len(fields)} | Mapped: {part_mapped} | Questionnaire: {part_quest} | Unmapped: {part_unmapped}</small>
                <br>
                <small>Pages: {', '.join(map(str, part_info.get('pages', [])))}</small>
            </div>
            ''', unsafe_allow_html=True)
        
        # Display fields for this part
        for idx, field in enumerate(display_fields):
            with st.container():
                st.markdown('<div class="mapping-row">', unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    # Field info
                    display_label = field.field_label
                    if field.item_number:
                        display_label = f"{field.item_number}. {display_label}"
                    
                    st.markdown(f'<div class="field-label">{display_label}</div>', unsafe_allow_html=True)
                    
                    # Build field metadata
                    meta_parts = [
                        f'<span class="field-type">{field.field_type}</span>',
                        f'Field: {field.field_key}',
                        f'Page {field.page}'
                    ]
                    
                    # Only show quest key if it's different from field key
                    if field.to_questionnaire and field.question_key and field.question_key != field.field_key:
                        meta_parts.append(f'Quest: {field.question_key}')
                    
                    st.markdown(f"""
                    <div class="field-meta">
                        {' • '.join(meta_parts)}
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    # Create unique key for this field
                    unique_key = f"{part_name}_{field.field_id}_{idx}"
                    
                    col2a, col2b = st.columns([3, 1])
                    
                    with col2a:
                        # Database mapping dropdown
                        grouped_options = {
                            "Actions": ["-- Select Database Field --", "📋 Move to Questionnaire"],
                            "beneficiary": [],
                            "petitioner": [],
                            "customer": [],
                            "attorney": [],
                            "attorneyLawfirmDetails": [],
                            "case": [],
                            "employment": []
                        }
                        
                        # Group database paths
                        for path in extractor.db_paths:
                            obj_name = path.split('.')[0]
                            if obj_name in grouped_options:
                                grouped_options[obj_name].append(path)
                        
                        # Build flat list with separators
                        options = []
                        for group, items in grouped_options.items():
                            if items:
                                if options:  # Add separator between groups
                                    options.append(f"── {group} ──")
                                options.extend(items)
                        
                        # Current selection
                        if field.is_mapped and field.db_mapping:
                            current_value = field.db_mapping
                        elif field.to_questionnaire:
                            current_value = "📋 Move to Questionnaire"
                        else:
                            # Try to get suggestion
                            suggestion = extractor.suggest_mapping(field)
                            current_value = suggestion if suggestion else "-- Select Database Field --"
                        
                        # Find index
                        try:
                            current_index = options.index(current_value)
                        except ValueError:
                            current_index = 0
                        
                        selected = st.selectbox(
                            "Database Mapping",
                            options,
                            index=current_index,
                            key=f"map_{unique_key}",
                            label_visibility="collapsed"
                        )
                        
                        # Handle selection
                        if selected != current_value and not selected.startswith("──"):
                            if selected == "📋 Move to Questionnaire":
                                field.to_questionnaire = True
                                field.is_mapped = False
                                field.db_mapping = None
                            elif selected != "-- Select Database Field --":
                                field.db_mapping = selected
                                field.is_mapped = True
                                field.to_questionnaire = False
                            st.rerun()
                    
                    with col2b:
                        # Quick questionnaire toggle
                        if st.button("📋", key=f"quest_btn_{unique_key}", 
                                   help="Quick add to questionnaire",
                                   use_container_width=True):
                            field.to_questionnaire = True
                            field.is_mapped = False
                            field.db_mapping = None
                            st.rerun()
                
                with col3:
                    # Status
                    status = field.get_status()
                    if "Mapped" in status:
                        badge_class = "status-mapped"
                    elif "Questionnaire" in status:
                        badge_class = "status-questionnaire"
                    else:
                        badge_class = "status-unmapped"
                    
                    st.markdown(f'<span class="status-badge {badge_class}">{status}</span>', 
                              unsafe_allow_html=True)
                
                st.markdown('</div>', unsafe_allow_html=True)
        
        # Add spacing between parts
        st.markdown("<br>", unsafe_allow_html=True)

def main():
    """Main application"""
    st.markdown("# 🤖 USCIS Form Reader Pro")
    st.markdown("### Complete PDF Form Field Extraction & Mapping Solution")
    
    # Initialize extractor
    extractor = FieldExtractor()
    
    # Sidebar
    with st.sidebar:
        st.markdown("## ⚙️ Settings")
        st.session_state.debug_mode = st.checkbox("Debug Mode", value=False)
        
        if st.session_state.pdf_processed:
            st.markdown("---")
            st.markdown("### 📊 Statistics")
            stats = st.session_state.extraction_stats
            st.metric("Total Pages", stats.get('total_pages', 0))
            st.metric("Total Parts", stats.get('total_parts', 0))
            st.metric("Total Fields", stats.get('total_fields', 0))
            st.metric("Extraction Time", f"{stats.get('extraction_time', 0):.2f}s")
            
            if stats.get('errors'):
                st.warning(f"{len(stats['errors'])} errors occurred")
                with st.expander("View Errors"):
                    for error in stats['errors']:
                        st.text(error)
            
            # Field summary
            total = len(st.session_state.fields)
            mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
            quest = sum(1 for f in st.session_state.fields if f.to_questionnaire)
            
            st.markdown("---")
            st.markdown("### 📈 Mapping Progress")
            st.metric("Mapped to DB", f"{mapped} ({mapped/total*100:.1f}%)")
            st.metric("In Questionnaire", f"{quest} ({quest/total*100:.1f}%)")
            st.metric("Unmapped", f"{total - mapped - quest}")
            
            # Progress bar
            progress = (mapped + quest) / total if total > 0 else 0
            st.progress(progress)
            
            # Part breakdown
            st.markdown("---")
            st.markdown("### 📑 Parts Overview")
            for part_name, part_info in st.session_state.part_structure.items():
                fields = st.session_state.fields_by_part.get(part_name, [])
                mapped = sum(1 for f in fields if f.is_mapped)
                quest = sum(1 for f in fields if f.to_questionnaire)
                st.caption(f"{part_name}: {len(fields)} fields ({mapped} mapped, {quest} quest)")
    
    # Main tabs
    tab1, tab2, tab3 = st.tabs(["📤 Upload & Extract", "🎯 Map Fields", "📥 Export & Download"])
    
    with tab1:
        st.markdown("## Upload USCIS PDF Form")
        
        uploaded_file = st.file_uploader(
            "Choose a USCIS PDF form",
            type=['pdf'],
            help="Upload any fillable USCIS form (I-90, I-129, G-28, etc.)",
            key="pdf_uploader"
        )
        
        if uploaded_file:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                if st.button("🚀 Extract Fields by Parts", type="primary", use_container_width=True):
                    with st.spinner("Analyzing PDF structure and extracting fields by parts..."):
                        if extractor.extract_from_pdf(uploaded_file):
                            st.success(f"""
                            ✅ Successfully extracted {len(st.session_state.fields)} fields from {st.session_state.form_info.get('form_number', 'form')}!
                            
                            Found {len(st.session_state.fields_by_part)} parts with fields.
                            """)
                            
                            # Show extraction summary
                            with st.expander("📊 Extraction Summary", expanded=True):
                                for part_name, fields in st.session_state.fields_by_part.items():
                                    part_info = st.session_state.part_structure.get(part_name, {})
                                    
                                    st.write(f"**{part_name}** {part_info.get('title', '')}")
                                    st.write(f"- Fields: {len(fields)}")
                                    st.write(f"- Pages: {', '.join(map(str, part_info.get('pages', [])))}")
                                    
                                    # Field type breakdown
                                    types = defaultdict(int)
                                    for field in fields:
                                        types[field.field_type] += 1
                                    
                                    type_summary = ", ".join([f"{count} {ftype}" for ftype, count in types.items()])
                                    st.caption(f"Field types: {type_summary}")
                                    st.divider()
            
            with col2:
                if st.session_state.pdf_processed:
                    if st.button("🔄 Reset", type="secondary", use_container_width=True):
                        # Clear all session state
                        for key in list(st.session_state.keys()):
                            if key != 'debug_mode':
                                del st.session_state[key]
                        extractor.init_session_state()
                        st.rerun()
    
    with tab2:
        if not st.session_state.pdf_processed:
            st.info("👆 Please upload and extract a PDF form first.")
        else:
            render_mapping_interface(extractor)
    
    with tab3:
        if not st.session_state.pdf_processed:
            st.info("👆 Please upload and extract a PDF form first.")
        else:
            st.markdown("## 📥 Export & Download")
            
            # Summary
            total = len(st.session_state.fields)
            mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
            quest = sum(1 for f in st.session_state.fields if f.to_questionnaire)
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Fields", total)
            col2.metric("Mapped to Database", mapped)
            col3.metric("In Questionnaire", quest)
            
            st.markdown("---")
            
            # Export options
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 📄 TypeScript Export")
                st.markdown("Database mappings for your application")
                
                ts_code = extractor.generate_typescript()
                
                st.download_button(
                    label="⬇️ Download TypeScript File",
                    data=ts_code,
                    file_name=f"{st.session_state.form_info.get('form_number', 'form')}.ts",
                    mime="text/typescript",
                    use_container_width=True
                )
                
                with st.expander("Preview TypeScript"):
                    st.code(ts_code, language="typescript")
            
            with col2:
                st.markdown("### 📋 JSON Export")
                st.markdown("Questionnaire configuration")
                
                json_code = extractor.generate_json()
                
                st.download_button(
                    label="⬇️ Download JSON File",
                    data=json_code,
                    file_name=f"{st.session_state.form_info.get('form_number', 'form')}-questionnaire.json",
                    mime="application/json",
                    use_container_width=True
                )
                
                with st.expander("Preview JSON"):
                    st.code(json_code, language="json")
            
            # Combined export
            st.markdown("---")
            if st.button("📦 Download Both Files", type="primary", use_container_width=True):
                st.markdown("### Downloads Ready:")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button(
                        "TypeScript (.ts)",
                        extractor.generate_typescript(),
                        f"{st.session_state.form_info.get('form_number', 'form')}.ts",
                        mime="text/typescript"
                    )
                with col2:
                    st.download_button(
                        "JSON (.json)",
                        extractor.generate_json(),
                        f"{st.session_state.form_info.get('form_number', 'form')}-questionnaire.json",
                        mime="application/json"
                    )

if __name__ == "__main__":
    main()
, '', key)  # Remove trailing underscores
        
        # Common abbreviations
        abbreviations = {
            'family_name': 'familyName',
            'last_name': 'lastName',
            'given_name': 'givenName',
            'first_name': 'firstName',
            'middle_name': 'middleName',
            'date_of_birth': 'dob',
            'social_security': 'ssn',
            'alien_number': 'aNumber',
            'email_address': 'email',
            'phone_number': 'phone',
            'street_address': 'street',
            'zip_code': 'zip',
            'state_bar_number': 'stateBarNumber',
            'law_firm_name': 'lawFirmName',
            'licensing_authority': 'licensingAuthority'
        }
        
        key_lower = key.lower()
        for pattern, replacement in abbreviations.items():
            if pattern in key_lower:
                return replacement
        
        # Convert to camelCase
        parts = key.split('_')
        if len(parts) > 1:
            key = parts[0].lower() + ''.join(p.capitalize() for p in parts[1:] if p)
        else:
            key = key.lower() if key else 'field'
        
        # Ensure we have a valid key
        if not key or key.isdigit():
            key = 'field'
        
        # Limit length
        if len(key) > 30:
            key = key[:30]
        
        return key
    
    def _generate_field_label(self, name: str) -> str:
        """Generate human-readable label"""
        # Common label mappings
        label_map = {
            'familyname': 'Family Name (Last Name)',
            'lastname': 'Last Name',
            'givenname': 'Given Name (First Name)', 
            'firstname': 'First Name',
            'middlename': 'Middle Name',
            'anumber': 'Alien Registration Number (A-Number)',
            'uscisaccount': 'USCIS Online Account Number',
            'dateofbirth': 'Date of Birth',
            'ssn': 'Social Security Number',
            'email': 'Email Address',
            'phone': 'Phone Number',
            'daytimephone': 'Daytime Phone Number',
            'mobile': 'Mobile Phone Number',
            'street': 'Street Address',
            'city': 'City or Town',
            'state': 'State',
            'zip': 'ZIP Code',
            'country': 'Country',
            'barnumber': 'Bar Number',
            'statebarnumber': 'State Bar Number',
            'lawfirm': 'Law Firm Name',
            'lawfirmname': 'Law Firm Name',
            'licensingauthority': 'Licensing Authority',
            'workphone': 'Work Phone Number',
            'faxnumber': 'Fax Number'
        }
        
        # Check for exact match
        name_lower = name.lower().replace('_', '').replace('-', '').replace(' ', '')
        for key, label in label_map.items():
            if key in name_lower or name_lower in key:
                return label
        
        # Convert to title case
        label = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
        label = label.replace('_', ' ').replace('-', ' ')
        label = ' '.join(label.split())
        label = label.title()
        
        return label
    
    def _map_widget_type(self, widget_type: int) -> str:
        """Map PDF widget type to field type"""
        type_map = {
            1: "button",
            2: "checkbox",
            3: "radio",
            4: "text",
            5: "dropdown",
            6: "list",
            7: "signature"
        }
        return type_map.get(widget_type, "text")
    
    def suggest_mapping(self, field: PDFField) -> Optional[str]:
        """Suggest database mapping for field"""
        label_lower = field.field_label.lower()
        key_lower = field.field_key.lower()
        
        # Try pattern matching with both label and key
        for pattern, suggestions in self.field_patterns.items():
            if re.search(pattern, label_lower) or re.search(pattern, key_lower):
                # Return first matching suggestion
                for suggestion in suggestions:
                    if suggestion in self.db_paths:
                        return suggestion
        
        # Try exact field name matching
        for db_path in self.db_paths:
            path_parts = db_path.split('.')
            field_name = path_parts[-1].lower()
            
            # Check both label and key
            if field_name in label_lower.replace(' ', '').lower() or field_name in key_lower:
                return db_path
        
        return None
    
    def generate_typescript(self) -> str:
        """Generate TypeScript export"""
        form_name = st.session_state.form_info.get('form_number', 'Form').replace('-', '')
        
        # Group fields
        sections = {
            'customerData': {},
            'beneficiaryData': {},
            'attorneyData': {},
            'questionnaireData': {},
            'caseData': {},
            'defaultData': {},
            'conditionalData': {}
        }
        
        for field in st.session_state.fields:
            if field.is_mapped and field.db_mapping:
                # Determine section
                if field.db_mapping.startswith('customer.'):
                    section = 'customerData'
                elif field.db_mapping.startswith('beneficiary.'):
                    section = 'beneficiaryData'
                elif field.db_mapping.startswith('attorney.') or field.db_mapping.startswith('attorneyLawfirmDetails.'):
                    section = 'attorneyData'
                elif field.db_mapping.startswith('case.'):
                    section = 'caseData'
                else:
                    continue
                
                # Add field
                suffix = self._get_ts_suffix(field.field_type)
                sections[section][field.field_key] = f"{field.db_mapping}{suffix}"
            
            elif field.to_questionnaire:
                # Use question_key for questionnaire items
                key = field.question_key if field.question_key else field.field_key
                sections['questionnaireData'][key] = f"{field.field_key}:ConditionBox"
        
        # Generate TypeScript
        ts = f'export const {form_name} = {{\n'
        ts += f'    "formname": "{form_name}",\n'
        
        # Add sections
        for section_name, fields in sections.items():
            if section_name == 'conditionalData':
                continue  # Handle separately
            
            if fields:
                ts += f'    "{section_name}": {{\n'
                field_entries = []
                for key, value in fields.items():
                    field_entries.append(f'        "{key}": "{value}"')
                ts += ',\n'.join(field_entries)
                ts += '\n    },\n'
            else:
                ts += f'    "{section_name}": null,\n'
        
        # Add conditional data (empty for now)
        ts += '    "conditionalData": {},\n'
        
        # Add PDF name
        ts += f'    "pdfName": "{st.session_state.form_info.get("form_number", "Unknown")}"\n'
        ts += '};\n\n'
        ts += f'export default {form_name};'
        
        return ts
    
    def _get_ts_suffix(self, field_type: str) -> str:
        """Get TypeScript suffix for field type"""
        suffix_map = {
            'text': ':TextBox',
            'checkbox': ':CheckBox',
            'radio': ':RadioBox',
            'dropdown': ':DropdownBox',
            'signature': ':SignatureBox',
            'date': ':Date',
            'button': ':ButtonBox'
        }
        return suffix_map.get(field_type, ':TextBox')
    
    def generate_json(self) -> str:
        """Generate JSON export for questionnaire"""
        controls = []
        
        # Add fields by part
        for part_name, fields in st.session_state.fields_by_part.items():
            # Get part info
            part_info = st.session_state.part_structure.get(part_name, {})
            
            # Get questionnaire fields
            quest_fields = [f for f in fields if f.to_questionnaire]
            
            if quest_fields:
                # Add part title
                title_text = f"{part_name}"
                if part_info.get('title'):
                    title_text += f": {part_info['title']}"
                
                controls.append({
                    "name": f"{part_name.lower().replace(' ', '_')}_title",
                    "label": title_text,
                    "type": "title",
                    "validators": {},
                    "style": {"col": "12"}
                })
                
                # Add fields
                for field in quest_fields:
                    control = {
                        "name": field.field_key,
                        "label": field.field_label,
                        "type": "colorSwitch" if field.field_type in ["checkbox", "radio"] else field.field_type,
                        "validators": {}
                    }
                    
                    # Add field-specific properties
                    if field.field_type == "text":
                        control["style"] = {"col": "7"}
                    elif field.field_type in ["checkbox", "radio"]:
                        control["style"] = {"col": "12"}
                        if field.field_type == "radio":
                            control["id"] = field.field_key
                            control["value"] = "1"
                    
                    controls.append(control)
        
        return json.dumps({"controls": controls}, indent=2)

def render_mapping_interface(extractor: FieldExtractor):
    """Render the enhanced field mapping interface organized by parts"""
    st.markdown("## 🎯 Field Mapping by Parts")
    
    # Top controls
    with st.container():
        st.markdown('<div class="part-selector">', unsafe_allow_html=True)
        
        col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
        
        with col1:
            # Part selector
            part_options = ['All Parts'] + list(st.session_state.fields_by_part.keys())
            selected_part = st.selectbox(
                "📑 Select Part",
                part_options,
                index=part_options.index(st.session_state.selected_part) if st.session_state.selected_part in part_options else 0,
                key="part_selector"
            )
            st.session_state.selected_part = selected_part
        
        with col2:
            # Mapping filter
            mapping_filter = st.selectbox(
                "🔍 Filter by Status",
                ["All Fields", "Mapped", "Unmapped", "Questionnaire"],
                key="mapping_filter_select"
            )
            st.session_state.mapping_filter = mapping_filter.lower().replace(' fields', '').replace(' ', '_')
        
        with col3:
            # Database browser toggle
            st.session_state.show_db_browser = st.checkbox(
                "🗂️ Show DB Browser",
                value=st.session_state.show_db_browser,
                help="Show database structure browser"
            )
        
        with col4:
            # Field count
            if selected_part == 'All Parts':
                total_fields = len(st.session_state.fields)
            else:
                total_fields = len(st.session_state.fields_by_part.get(selected_part, []))
            
            mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
            st.metric("Progress", f"{mapped}/{total_fields}", f"{mapped/total_fields*100:.0f}%")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Quick actions
    st.markdown("### ⚡ Quick Actions")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🤖 Auto-Map Current View", use_container_width=True):
            fields_to_map = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_map = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            mapped_count = 0
            for field in fields_to_map:
                if not field.is_mapped and not field.to_questionnaire and field.field_type == 'text':
                    suggestion = extractor.suggest_mapping(field)
                    if suggestion:
                        field.db_mapping = suggestion
                        field.is_mapped = True
                        mapped_count += 1
            st.success(f"Auto-mapped {mapped_count} fields!")
            st.rerun()
    
    with col2:
        if st.button("📋 All Checkboxes → Quest", use_container_width=True):
            fields_to_move = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_move = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            count = 0
            for field in fields_to_move:
                if field.field_type in ['checkbox', 'radio'] and not field.to_questionnaire:
                    field.to_questionnaire = True
                    field.is_mapped = False
                    count += 1
            st.success(f"Moved {count} fields to questionnaire!")
            st.rerun()
    
    with col3:
        if st.button("🔄 Reset Current View", use_container_width=True):
            fields_to_reset = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_reset = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            for field in fields_to_reset:
                field.is_mapped = False
                field.db_mapping = None
                field.to_questionnaire = field.field_type in ['checkbox', 'radio', 'button']
            st.success("Reset complete!")
            st.rerun()
    
    with col4:
        unmapped = sum(1 for f in st.session_state.fields if not f.is_mapped and not f.to_questionnaire)
        if st.button(f"📋 All Unmapped → Quest ({unmapped})", use_container_width=True):
            fields_to_move = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_move = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            count = 0
            for field in fields_to_move:
                if not field.is_mapped and not field.to_questionnaire:
                    field.to_questionnaire = True
                    count += 1
            st.success(f"Moved {count} fields to questionnaire!")
            st.rerun()
    
    # Database object browser
    if st.session_state.show_db_browser:
        with st.expander("🗂️ Database Structure Browser", expanded=True):
            st.markdown("### Available Database Paths")
            st.caption("Click any path to copy it")
            
            # Create tabs for each main object
            tabs = st.tabs(list(DB_OBJECTS.keys()))
            
            for i, (obj_name, tab) in enumerate(zip(DB_OBJECTS.keys(), tabs)):
                with tab:
                    for sub_obj, fields in DB_OBJECTS[obj_name].items():
                        if sub_obj:
                            st.markdown(f"**{sub_obj}:**")
                        
                        # Display fields in columns
                        field_cols = st.columns(3)
                        for j, field in enumerate(fields):
                            col_idx = j % 3
                            with field_cols[col_idx]:
                                if sub_obj:
                                    path = f"{obj_name}.{sub_obj}.{field}"
                                else:
                                    path = f"{obj_name}.{field}"
                                
                                if st.button(f"📋 {field}", key=f"copy_{path}", use_container_width=True):
                                    st.code(path, language="text")
    
    # Field mapping interface organized by parts
    st.markdown("### 📝 Field Mappings by Part")
    
    # Get parts to display
    if st.session_state.selected_part == 'All Parts':
        parts_to_show = st.session_state.fields_by_part.items()
    else:
        parts_to_show = [(st.session_state.selected_part, 
                         st.session_state.fields_by_part.get(st.session_state.selected_part, []))]
    
    # Display each part
    for part_name, fields in parts_to_show:
        # Filter fields based on mapping filter
        if st.session_state.mapping_filter == 'mapped':
            display_fields = [f for f in fields if f.is_mapped]
        elif st.session_state.mapping_filter == 'unmapped':
            display_fields = [f for f in fields if not f.is_mapped and not f.to_questionnaire]
        elif st.session_state.mapping_filter == 'questionnaire':
            display_fields = [f for f in fields if f.to_questionnaire]
        else:
            display_fields = fields
        
        if not display_fields:
            continue
        
        # Get part info
        part_info = st.session_state.part_structure.get(part_name, {})
        
        # Part header with stats
        part_mapped = sum(1 for f in fields if f.is_mapped)
        part_quest = sum(1 for f in fields if f.to_questionnaire)
        part_unmapped = len(fields) - part_mapped - part_quest
        
        with st.container():
            st.markdown(f'''
            <div class="part-header">
                <strong>{part_name}</strong> {part_info.get('title', '')} 
                <br>
                <small>Total: {len(fields)} | Mapped: {part_mapped} | Questionnaire: {part_quest} | Unmapped: {part_unmapped}</small>
                <br>
                <small>Pages: {', '.join(map(str, part_info.get('pages', [])))}</small>
            </div>
            ''', unsafe_allow_html=True)
        
        # Display fields for this part
        for idx, field in enumerate(display_fields):
            with st.container():
                st.markdown('<div class="mapping-row">', unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    # Field info
                    display_label = field.field_label
                    if field.item_number:
                        display_label = f"{field.item_number}. {display_label}"
                    
                    st.markdown(f'<div class="field-label">{display_label}</div>', unsafe_allow_html=True)
                    
                    # Build field metadata
                    meta_parts = [
                        f'<span class="field-type">{field.field_type}</span>',
                        f'Field: {field.field_key}',
                        f'Page {field.page}'
                    ]
                    
                    # Only show quest key if it's different from field key
                    if field.to_questionnaire and field.question_key and field.question_key != field.field_key:
                        meta_parts.append(f'Quest: {field.question_key}')
                    
                    st.markdown(f"""
                    <div class="field-meta">
                        {' • '.join(meta_parts)}
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    # Create unique key for this field
                    unique_key = f"{part_name}_{field.field_id}_{idx}"
                    
                    col2a, col2b = st.columns([3, 1])
                    
                    with col2a:
                        # Database mapping dropdown
                        grouped_options = {
                            "Actions": ["-- Select Database Field --", "📋 Move to Questionnaire"],
                            "beneficiary": [],
                            "petitioner": [],
                            "customer": [],
                            "attorney": [],
                            "attorneyLawfirmDetails": [],
                            "case": [],
                            "employment": []
                        }
                        
                        # Group database paths
                        for path in extractor.db_paths:
                            obj_name = path.split('.')[0]
                            if obj_name in grouped_options:
                                grouped_options[obj_name].append(path)
                        
                        # Build flat list with separators
                        options = []
                        for group, items in grouped_options.items():
                            if items:
                                if options:  # Add separator between groups
                                    options.append(f"── {group} ──")
                                options.extend(items)
                        
                        # Current selection
                        if field.is_mapped and field.db_mapping:
                            current_value = field.db_mapping
                        elif field.to_questionnaire:
                            current_value = "📋 Move to Questionnaire"
                        else:
                            # Try to get suggestion
                            suggestion = extractor.suggest_mapping(field)
                            current_value = suggestion if suggestion else "-- Select Database Field --"
                        
                        # Find index
                        try:
                            current_index = options.index(current_value)
                        except ValueError:
                            current_index = 0
                        
                        selected = st.selectbox(
                            "Database Mapping",
                            options,
                            index=current_index,
                            key=f"map_{unique_key}",
                            label_visibility="collapsed"
                        )
                        
                        # Handle selection
                        if selected != current_value and not selected.startswith("──"):
                            if selected == "📋 Move to Questionnaire":
                                field.to_questionnaire = True
                                field.is_mapped = False
                                field.db_mapping = None
                            elif selected != "-- Select Database Field --":
                                field.db_mapping = selected
                                field.is_mapped = True
                                field.to_questionnaire = False
                            st.rerun()
                    
                    with col2b:
                        # Quick questionnaire toggle
                        if st.button("📋", key=f"quest_btn_{unique_key}", 
                                   help="Quick add to questionnaire",
                                   use_container_width=True):
                            field.to_questionnaire = True
                            field.is_mapped = False
                            field.db_mapping = None
                            st.rerun()
                
                with col3:
                    # Status
                    status = field.get_status()
                    if "Mapped" in status:
                        badge_class = "status-mapped"
                    elif "Questionnaire" in status:
                        badge_class = "status-questionnaire"
                    else:
                        badge_class = "status-unmapped"
                    
                    st.markdown(f'<span class="status-badge {badge_class}">{status}</span>', 
                              unsafe_allow_html=True)
                
                st.markdown('</div>', unsafe_allow_html=True)
        
        # Add spacing between parts
        st.markdown("<br>", unsafe_allow_html=True)

def main():
    """Main application"""
    st.markdown("# 🤖 USCIS Form Reader Pro")
    st.markdown("### Complete PDF Form Field Extraction & Mapping Solution")
    
    # Initialize extractor
    extractor = FieldExtractor()
    
    # Sidebar
    with st.sidebar:
        st.markdown("## ⚙️ Settings")
        st.session_state.debug_mode = st.checkbox("Debug Mode", value=False)
        
        if st.session_state.pdf_processed:
            st.markdown("---")
            st.markdown("### 📊 Statistics")
            stats = st.session_state.extraction_stats
            st.metric("Total Pages", stats.get('total_pages', 0))
            st.metric("Total Parts", stats.get('total_parts', 0))
            st.metric("Total Fields", stats.get('total_fields', 0))
            st.metric("Extraction Time", f"{stats.get('extraction_time', 0):.2f}s")
            
            if stats.get('errors'):
                st.warning(f"{len(stats['errors'])} errors occurred")
                with st.expander("View Errors"):
                    for error in stats['errors']:
                        st.text(error)
            
            # Field summary
            total = len(st.session_state.fields)
            mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
            quest = sum(1 for f in st.session_state.fields if f.to_questionnaire)
            
            st.markdown("---")
            st.markdown("### 📈 Mapping Progress")
            st.metric("Mapped to DB", f"{mapped} ({mapped/total*100:.1f}%)")
            st.metric("In Questionnaire", f"{quest} ({quest/total*100:.1f}%)")
            st.metric("Unmapped", f"{total - mapped - quest}")
            
            # Progress bar
            progress = (mapped + quest) / total if total > 0 else 0
            st.progress(progress)
            
            # Part breakdown
            st.markdown("---")
            st.markdown("### 📑 Parts Overview")
            for part_name, part_info in st.session_state.part_structure.items():
                fields = st.session_state.fields_by_part.get(part_name, [])
                mapped = sum(1 for f in fields if f.is_mapped)
                quest = sum(1 for f in fields if f.to_questionnaire)
                st.caption(f"{part_name}: {len(fields)} fields ({mapped} mapped, {quest} quest)")
    
    # Main tabs
    tab1, tab2, tab3 = st.tabs(["📤 Upload & Extract", "🎯 Map Fields", "📥 Export & Download"])
    
    with tab1:
        st.markdown("## Upload USCIS PDF Form")
        
        uploaded_file = st.file_uploader(
            "Choose a USCIS PDF form",
            type=['pdf'],
            help="Upload any fillable USCIS form (I-90, I-129, G-28, etc.)",
            key="pdf_uploader"
        )
        
        if uploaded_file:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                if st.button("🚀 Extract Fields by Parts", type="primary", use_container_width=True):
                    with st.spinner("Analyzing PDF structure and extracting fields by parts..."):
                        if extractor.extract_from_pdf(uploaded_file):
                            st.success(f"""
                            ✅ Successfully extracted {len(st.session_state.fields)} fields from {st.session_state.form_info.get('form_number', 'form')}!
                            
                            Found {len(st.session_state.fields_by_part)} parts with fields.
                            """)
                            
                            # Show extraction summary
                            with st.expander("📊 Extraction Summary", expanded=True):
                                for part_name, fields in st.session_state.fields_by_part.items():
                                    part_info = st.session_state.part_structure.get(part_name, {})
                                    
                                    st.write(f"**{part_name}** {part_info.get('title', '')}")
                                    st.write(f"- Fields: {len(fields)}")
                                    st.write(f"- Pages: {', '.join(map(str, part_info.get('pages', [])))}")
                                    
                                    # Field type breakdown
                                    types = defaultdict(int)
                                    for field in fields:
                                        types[field.field_type] += 1
                                    
                                    type_summary = ", ".join([f"{count} {ftype}" for ftype, count in types.items()])
                                    st.caption(f"Field types: {type_summary}")
                                    st.divider()
            
            with col2:
                if st.session_state.pdf_processed:
                    if st.button("🔄 Reset", type="secondary", use_container_width=True):
                        # Clear all session state
                        for key in list(st.session_state.keys()):
                            if key != 'debug_mode':
                                del st.session_state[key]
                        extractor.init_session_state()
                        st.rerun()
    
    with tab2:
        if not st.session_state.pdf_processed:
            st.info("👆 Please upload and extract a PDF form first.")
        else:
            render_mapping_interface(extractor)
    
    with tab3:
        if not st.session_state.pdf_processed:
            st.info("👆 Please upload and extract a PDF form first.")
        else:
            st.markdown("## 📥 Export & Download")
            
            # Summary
            total = len(st.session_state.fields)
            mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
            quest = sum(1 for f in st.session_state.fields if f.to_questionnaire)
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Fields", total)
            col2.metric("Mapped to Database", mapped)
            col3.metric("In Questionnaire", quest)
            
            st.markdown("---")
            
            # Export options
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 📄 TypeScript Export")
                st.markdown("Database mappings for your application")
                
                ts_code = extractor.generate_typescript()
                
                st.download_button(
                    label="⬇️ Download TypeScript File",
                    data=ts_code,
                    file_name=f"{st.session_state.form_info.get('form_number', 'form')}.ts",
                    mime="text/typescript",
                    use_container_width=True
                )
                
                with st.expander("Preview TypeScript"):
                    st.code(ts_code, language="typescript")
            
            with col2:
                st.markdown("### 📋 JSON Export")
                st.markdown("Questionnaire configuration")
                
                json_code = extractor.generate_json()
                
                st.download_button(
                    label="⬇️ Download JSON File",
                    data=json_code,
                    file_name=f"{st.session_state.form_info.get('form_number', 'form')}-questionnaire.json",
                    mime="application/json",
                    use_container_width=True
                )
                
                with st.expander("Preview JSON"):
                    st.code(json_code, language="json")
            
            # Combined export
            st.markdown("---")
            if st.button("📦 Download Both Files", type="primary", use_container_width=True):
                st.markdown("### Downloads Ready:")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button(
                        "TypeScript (.ts)",
                        extractor.generate_typescript(),
                        f"{st.session_state.form_info.get('form_number', 'form')}.ts",
                        mime="text/typescript"
                    )
                with col2:
                    st.download_button(
                        "JSON (.json)",
                        extractor.generate_json(),
                        f"{st.session_state.form_info.get('form_number', 'form')}-questionnaire.json",
                        mime="application/json"
                    )

if __name__ == "__main__":
    main()
, '', name)
        cleaned_name = cleaned_name.strip('_- ')
        
        # If the name is just a number or empty after cleaning, use a generic label
        if not cleaned_name or cleaned_name.isdigit():
            return f"Field {name}" if name and not name.isdigit() else "Field"
        
        # Common label mappings
        label_map = {
            'familyname': 'Family Name (Last Name)',
            'lastname': 'Last Name',
            'givenname': 'Given Name (First Name)', 
            'firstname': 'First Name',
            'middlename': 'Middle Name',
            'anumber': 'Alien Registration Number (A-Number)',
            'uscisaccount': 'USCIS Online Account Number',
            'dateofbirth': 'Date of Birth',
            'ssn': 'Social Security Number',
            'email': 'Email Address',
            'phone': 'Phone Number',
            'daytimephone': 'Daytime Phone Number',
            'mobile': 'Mobile Phone Number',
            'street': 'Street Address',
            'city': 'City or Town',
            'state': 'State',
            'zip': 'ZIP Code',
            'country': 'Country',
            'barnumber': 'Bar Number',
            'statebarnumber': 'State Bar Number',
            'lawfirm': 'Law Firm Name',
            'lawfirmname': 'Law Firm Name',
            'licensingauthority': 'Licensing Authority',
            'workphone': 'Work Phone Number',
            'faxnumber': 'Fax Number',
            'aptstefloornumber': 'Apt/Ste/Floor Number',
            'incareof': 'In Care Of',
            'yearsresiding': 'Years Residing',
            'monthsresiding': 'Months Residing'
        }
        
        # Check for exact match
        name_lower = cleaned_name.lower().replace('_', '').replace('-', '').replace(' ', '')
        for key, label in label_map.items():
            if key in name_lower or name_lower in key:
                return label
        
        # Convert to title case
        label = re.sub(r'([a-z])([A-Z])', r'\1 \2', cleaned_name)
        label = label.replace('_', ' ').replace('-', ' ')
        label = ' '.join(label.split())
        
        # Title case but preserve certain acronyms
        words = label.split()
        formatted_words = []
        acronyms = ['USCIS', 'US', 'USA', 'SSN', 'EIN', 'ID']
        
        for word in words:
            upper_word = word.upper()
            if upper_word in acronyms:
                formatted_words.append(upper_word)
            else:
                formatted_words.append(word.title())
        
        label = ' '.join(formatted_words)
        
        return label
    
    def _map_widget_type(self, widget_type: int) -> str:
        """Map PDF widget type to field type"""
        type_map = {
            1: "button",
            2: "checkbox",
            3: "radio",
            4: "text",
            5: "dropdown",
            6: "list",
            7: "signature"
        }
        return type_map.get(widget_type, "text")
    
    def suggest_mapping(self, field: PDFField) -> Optional[str]:
        """Suggest database mapping for field"""
        label_lower = field.field_label.lower()
        key_lower = field.field_key.lower()
        
        # Try pattern matching with both label and key
        for pattern, suggestions in self.field_patterns.items():
            if re.search(pattern, label_lower) or re.search(pattern, key_lower):
                # Return first matching suggestion
                for suggestion in suggestions:
                    if suggestion in self.db_paths:
                        return suggestion
        
        # Try exact field name matching
        for db_path in self.db_paths:
            path_parts = db_path.split('.')
            field_name = path_parts[-1].lower()
            
            # Check both label and key
            if field_name in label_lower.replace(' ', '').lower() or field_name in key_lower:
                return db_path
        
        return None
    
    def generate_typescript(self) -> str:
        """Generate TypeScript export"""
        form_name = st.session_state.form_info.get('form_number', 'Form').replace('-', '')
        
        # Group fields
        sections = {
            'customerData': {},
            'beneficiaryData': {},
            'attorneyData': {},
            'questionnaireData': {},
            'caseData': {},
            'defaultData': {},
            'conditionalData': {}
        }
        
        for field in st.session_state.fields:
            if field.is_mapped and field.db_mapping:
                # Determine section
                if field.db_mapping.startswith('customer.'):
                    section = 'customerData'
                elif field.db_mapping.startswith('beneficiary.'):
                    section = 'beneficiaryData'
                elif field.db_mapping.startswith('attorney.') or field.db_mapping.startswith('attorneyLawfirmDetails.'):
                    section = 'attorneyData'
                elif field.db_mapping.startswith('case.'):
                    section = 'caseData'
                else:
                    continue
                
                # Add field
                suffix = self._get_ts_suffix(field.field_type)
                sections[section][field.field_key] = f"{field.db_mapping}{suffix}"
            
            elif field.to_questionnaire:
                # Use question_key for questionnaire items
                key = field.question_key if field.question_key else field.field_key
                sections['questionnaireData'][key] = f"{field.field_key}:ConditionBox"
        
        # Generate TypeScript
        ts = f'export const {form_name} = {{\n'
        ts += f'    "formname": "{form_name}",\n'
        
        # Add sections
        for section_name, fields in sections.items():
            if section_name == 'conditionalData':
                continue  # Handle separately
            
            if fields:
                ts += f'    "{section_name}": {{\n'
                field_entries = []
                for key, value in fields.items():
                    field_entries.append(f'        "{key}": "{value}"')
                ts += ',\n'.join(field_entries)
                ts += '\n    },\n'
            else:
                ts += f'    "{section_name}": null,\n'
        
        # Add conditional data (empty for now)
        ts += '    "conditionalData": {},\n'
        
        # Add PDF name
        ts += f'    "pdfName": "{st.session_state.form_info.get("form_number", "Unknown")}"\n'
        ts += '};\n\n'
        ts += f'export default {form_name};'
        
        return ts
    
    def _get_ts_suffix(self, field_type: str) -> str:
        """Get TypeScript suffix for field type"""
        suffix_map = {
            'text': ':TextBox',
            'checkbox': ':CheckBox',
            'radio': ':RadioBox',
            'dropdown': ':DropdownBox',
            'signature': ':SignatureBox',
            'date': ':Date',
            'button': ':ButtonBox'
        }
        return suffix_map.get(field_type, ':TextBox')
    
    def generate_json(self) -> str:
        """Generate JSON export for questionnaire"""
        controls = []
        
        # Add fields by part
        for part_name, fields in st.session_state.fields_by_part.items():
            # Get part info
            part_info = st.session_state.part_structure.get(part_name, {})
            
            # Get questionnaire fields
            quest_fields = [f for f in fields if f.to_questionnaire]
            
            if quest_fields:
                # Add part title
                title_text = f"{part_name}"
                if part_info.get('title'):
                    title_text += f": {part_info['title']}"
                
                controls.append({
                    "name": f"{part_name.lower().replace(' ', '_')}_title",
                    "label": title_text,
                    "type": "title",
                    "validators": {},
                    "style": {"col": "12"}
                })
                
                # Add fields
                for field in quest_fields:
                    control = {
                        "name": field.field_key,
                        "label": field.field_label,
                        "type": "colorSwitch" if field.field_type in ["checkbox", "radio"] else field.field_type,
                        "validators": {}
                    }
                    
                    # Add field-specific properties
                    if field.field_type == "text":
                        control["style"] = {"col": "7"}
                    elif field.field_type in ["checkbox", "radio"]:
                        control["style"] = {"col": "12"}
                        if field.field_type == "radio":
                            control["id"] = field.field_key
                            control["value"] = "1"
                    
                    controls.append(control)
        
        return json.dumps({"controls": controls}, indent=2)

def render_mapping_interface(extractor: FieldExtractor):
    """Render the enhanced field mapping interface organized by parts"""
    st.markdown("## 🎯 Field Mapping by Parts")
    
    # Top controls
    with st.container():
        st.markdown('<div class="part-selector">', unsafe_allow_html=True)
        
        col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
        
        with col1:
            # Part selector
            part_options = ['All Parts'] + list(st.session_state.fields_by_part.keys())
            selected_part = st.selectbox(
                "📑 Select Part",
                part_options,
                index=part_options.index(st.session_state.selected_part) if st.session_state.selected_part in part_options else 0,
                key="part_selector"
            )
            st.session_state.selected_part = selected_part
        
        with col2:
            # Mapping filter
            mapping_filter = st.selectbox(
                "🔍 Filter by Status",
                ["All Fields", "Mapped", "Unmapped", "Questionnaire"],
                key="mapping_filter_select"
            )
            st.session_state.mapping_filter = mapping_filter.lower().replace(' fields', '').replace(' ', '_')
        
        with col3:
            # Database browser toggle
            st.session_state.show_db_browser = st.checkbox(
                "🗂️ Show DB Browser",
                value=st.session_state.show_db_browser,
                help="Show database structure browser"
            )
        
        with col4:
            # Field count
            if selected_part == 'All Parts':
                total_fields = len(st.session_state.fields)
            else:
                total_fields = len(st.session_state.fields_by_part.get(selected_part, []))
            
            mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
            st.metric("Progress", f"{mapped}/{total_fields}", f"{mapped/total_fields*100:.0f}%")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Quick actions
    st.markdown("### ⚡ Quick Actions")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🤖 Auto-Map Current View", use_container_width=True):
            fields_to_map = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_map = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            mapped_count = 0
            for field in fields_to_map:
                if not field.is_mapped and not field.to_questionnaire and field.field_type == 'text':
                    suggestion = extractor.suggest_mapping(field)
                    if suggestion:
                        field.db_mapping = suggestion
                        field.is_mapped = True
                        mapped_count += 1
            st.success(f"Auto-mapped {mapped_count} fields!")
            st.rerun()
    
    with col2:
        if st.button("📋 All Checkboxes → Quest", use_container_width=True):
            fields_to_move = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_move = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            count = 0
            for field in fields_to_move:
                if field.field_type in ['checkbox', 'radio'] and not field.to_questionnaire:
                    field.to_questionnaire = True
                    field.is_mapped = False
                    count += 1
            st.success(f"Moved {count} fields to questionnaire!")
            st.rerun()
    
    with col3:
        if st.button("🔄 Reset Current View", use_container_width=True):
            fields_to_reset = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_reset = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            for field in fields_to_reset:
                field.is_mapped = False
                field.db_mapping = None
                field.to_questionnaire = field.field_type in ['checkbox', 'radio', 'button']
            st.success("Reset complete!")
            st.rerun()
    
    with col4:
        unmapped = sum(1 for f in st.session_state.fields if not f.is_mapped and not f.to_questionnaire)
        if st.button(f"📋 All Unmapped → Quest ({unmapped})", use_container_width=True):
            fields_to_move = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_move = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            count = 0
            for field in fields_to_move:
                if not field.is_mapped and not field.to_questionnaire:
                    field.to_questionnaire = True
                    count += 1
            st.success(f"Moved {count} fields to questionnaire!")
            st.rerun()
    
    # Database object browser
    if st.session_state.show_db_browser:
        with st.expander("🗂️ Database Structure Browser", expanded=True):
            st.markdown("### Available Database Paths")
            st.caption("Click any path to copy it")
            
            # Create tabs for each main object
            tabs = st.tabs(list(DB_OBJECTS.keys()))
            
            for i, (obj_name, tab) in enumerate(zip(DB_OBJECTS.keys(), tabs)):
                with tab:
                    for sub_obj, fields in DB_OBJECTS[obj_name].items():
                        if sub_obj:
                            st.markdown(f"**{sub_obj}:**")
                        
                        # Display fields in columns
                        field_cols = st.columns(3)
                        for j, field in enumerate(fields):
                            col_idx = j % 3
                            with field_cols[col_idx]:
                                if sub_obj:
                                    path = f"{obj_name}.{sub_obj}.{field}"
                                else:
                                    path = f"{obj_name}.{field}"
                                
                                if st.button(f"📋 {field}", key=f"copy_{path}", use_container_width=True):
                                    st.code(path, language="text")
    
    # Field mapping interface organized by parts
    st.markdown("### 📝 Field Mappings by Part")
    
    # Get parts to display
    if st.session_state.selected_part == 'All Parts':
        parts_to_show = st.session_state.fields_by_part.items()
    else:
        parts_to_show = [(st.session_state.selected_part, 
                         st.session_state.fields_by_part.get(st.session_state.selected_part, []))]
    
    # Display each part
    for part_name, fields in parts_to_show:
        # Filter fields based on mapping filter
        if st.session_state.mapping_filter == 'mapped':
            display_fields = [f for f in fields if f.is_mapped]
        elif st.session_state.mapping_filter == 'unmapped':
            display_fields = [f for f in fields if not f.is_mapped and not f.to_questionnaire]
        elif st.session_state.mapping_filter == 'questionnaire':
            display_fields = [f for f in fields if f.to_questionnaire]
        else:
            display_fields = fields
        
        if not display_fields:
            continue
        
        # Get part info
        part_info = st.session_state.part_structure.get(part_name, {})
        
        # Part header with stats
        part_mapped = sum(1 for f in fields if f.is_mapped)
        part_quest = sum(1 for f in fields if f.to_questionnaire)
        part_unmapped = len(fields) - part_mapped - part_quest
        
        with st.container():
            st.markdown(f'''
            <div class="part-header">
                <strong>{part_name}</strong> {part_info.get('title', '')} 
                <br>
                <small>Total: {len(fields)} | Mapped: {part_mapped} | Questionnaire: {part_quest} | Unmapped: {part_unmapped}</small>
                <br>
                <small>Pages: {', '.join(map(str, part_info.get('pages', [])))}</small>
            </div>
            ''', unsafe_allow_html=True)
        
        # Display fields for this part
        for idx, field in enumerate(display_fields):
            with st.container():
                st.markdown('<div class="mapping-row">', unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    # Field info
                    display_label = field.field_label
                    if field.item_number:
                        display_label = f"{field.item_number}. {display_label}"
                    
                    st.markdown(f'<div class="field-label">{display_label}</div>', unsafe_allow_html=True)
                    
                    # Build field metadata
                    meta_parts = [
                        f'<span class="field-type">{field.field_type}</span>',
                        f'Field: {field.field_key}',
                        f'Page {field.page}'
                    ]
                    
                    # Only show quest key if it's different from field key
                    if field.to_questionnaire and field.question_key and field.question_key != field.field_key:
                        meta_parts.append(f'Quest: {field.question_key}')
                    
                    st.markdown(f"""
                    <div class="field-meta">
                        {' • '.join(meta_parts)}
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    # Create unique key for this field
                    unique_key = f"{part_name}_{field.field_id}_{idx}"
                    
                    col2a, col2b = st.columns([3, 1])
                    
                    with col2a:
                        # Database mapping dropdown
                        grouped_options = {
                            "Actions": ["-- Select Database Field --", "📋 Move to Questionnaire"],
                            "beneficiary": [],
                            "petitioner": [],
                            "customer": [],
                            "attorney": [],
                            "attorneyLawfirmDetails": [],
                            "case": [],
                            "employment": []
                        }
                        
                        # Group database paths
                        for path in extractor.db_paths:
                            obj_name = path.split('.')[0]
                            if obj_name in grouped_options:
                                grouped_options[obj_name].append(path)
                        
                        # Build flat list with separators
                        options = []
                        for group, items in grouped_options.items():
                            if items:
                                if options:  # Add separator between groups
                                    options.append(f"── {group} ──")
                                options.extend(items)
                        
                        # Current selection
                        if field.is_mapped and field.db_mapping:
                            current_value = field.db_mapping
                        elif field.to_questionnaire:
                            current_value = "📋 Move to Questionnaire"
                        else:
                            # Try to get suggestion
                            suggestion = extractor.suggest_mapping(field)
                            current_value = suggestion if suggestion else "-- Select Database Field --"
                        
                        # Find index
                        try:
                            current_index = options.index(current_value)
                        except ValueError:
                            current_index = 0
                        
                        selected = st.selectbox(
                            "Database Mapping",
                            options,
                            index=current_index,
                            key=f"map_{unique_key}",
                            label_visibility="collapsed"
                        )
                        
                        # Handle selection
                        if selected != current_value and not selected.startswith("──"):
                            if selected == "📋 Move to Questionnaire":
                                field.to_questionnaire = True
                                field.is_mapped = False
                                field.db_mapping = None
                            elif selected != "-- Select Database Field --":
                                field.db_mapping = selected
                                field.is_mapped = True
                                field.to_questionnaire = False
                            st.rerun()
                    
                    with col2b:
                        # Quick questionnaire toggle
                        if st.button("📋", key=f"quest_btn_{unique_key}", 
                                   help="Quick add to questionnaire",
                                   use_container_width=True):
                            field.to_questionnaire = True
                            field.is_mapped = False
                            field.db_mapping = None
                            st.rerun()
                
                with col3:
                    # Status
                    status = field.get_status()
                    if "Mapped" in status:
                        badge_class = "status-mapped"
                    elif "Questionnaire" in status:
                        badge_class = "status-questionnaire"
                    else:
                        badge_class = "status-unmapped"
                    
                    st.markdown(f'<span class="status-badge {badge_class}">{status}</span>', 
                              unsafe_allow_html=True)
                
                st.markdown('</div>', unsafe_allow_html=True)
        
        # Add spacing between parts
        st.markdown("<br>", unsafe_allow_html=True)

def main():
    """Main application"""
    st.markdown("# 🤖 USCIS Form Reader Pro")
    st.markdown("### Complete PDF Form Field Extraction & Mapping Solution")
    
    # Initialize extractor
    extractor = FieldExtractor()
    
    # Sidebar
    with st.sidebar:
        st.markdown("## ⚙️ Settings")
        st.session_state.debug_mode = st.checkbox("Debug Mode", value=False)
        
        if st.session_state.pdf_processed:
            st.markdown("---")
            st.markdown("### 📊 Statistics")
            stats = st.session_state.extraction_stats
            st.metric("Total Pages", stats.get('total_pages', 0))
            st.metric("Total Parts", stats.get('total_parts', 0))
            st.metric("Total Fields", stats.get('total_fields', 0))
            st.metric("Extraction Time", f"{stats.get('extraction_time', 0):.2f}s")
            
            if stats.get('errors'):
                st.warning(f"{len(stats['errors'])} errors occurred")
                with st.expander("View Errors"):
                    for error in stats['errors']:
                        st.text(error)
            
            # Field summary
            total = len(st.session_state.fields)
            mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
            quest = sum(1 for f in st.session_state.fields if f.to_questionnaire)
            
            st.markdown("---")
            st.markdown("### 📈 Mapping Progress")
            st.metric("Mapped to DB", f"{mapped} ({mapped/total*100:.1f}%)")
            st.metric("In Questionnaire", f"{quest} ({quest/total*100:.1f}%)")
            st.metric("Unmapped", f"{total - mapped - quest}")
            
            # Progress bar
            progress = (mapped + quest) / total if total > 0 else 0
            st.progress(progress)
            
            # Part breakdown
            st.markdown("---")
            st.markdown("### 📑 Parts Overview")
            for part_name, part_info in st.session_state.part_structure.items():
                fields = st.session_state.fields_by_part.get(part_name, [])
                mapped = sum(1 for f in fields if f.is_mapped)
                quest = sum(1 for f in fields if f.to_questionnaire)
                st.caption(f"{part_name}: {len(fields)} fields ({mapped} mapped, {quest} quest)")
    
    # Main tabs
    tab1, tab2, tab3 = st.tabs(["📤 Upload & Extract", "🎯 Map Fields", "📥 Export & Download"])
    
    with tab1:
        st.markdown("## Upload USCIS PDF Form")
        
        uploaded_file = st.file_uploader(
            "Choose a USCIS PDF form",
            type=['pdf'],
            help="Upload any fillable USCIS form (I-90, I-129, G-28, etc.)",
            key="pdf_uploader"
        )
        
        if uploaded_file:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                if st.button("🚀 Extract Fields by Parts", type="primary", use_container_width=True):
                    with st.spinner("Analyzing PDF structure and extracting fields by parts..."):
                        if extractor.extract_from_pdf(uploaded_file):
                            st.success(f"""
                            ✅ Successfully extracted {len(st.session_state.fields)} fields from {st.session_state.form_info.get('form_number', 'form')}!
                            
                            Found {len(st.session_state.fields_by_part)} parts with fields.
                            """)
                            
                            # Show extraction summary
                            with st.expander("📊 Extraction Summary", expanded=True):
                                for part_name, fields in st.session_state.fields_by_part.items():
                                    part_info = st.session_state.part_structure.get(part_name, {})
                                    
                                    st.write(f"**{part_name}** {part_info.get('title', '')}")
                                    st.write(f"- Fields: {len(fields)}")
                                    st.write(f"- Pages: {', '.join(map(str, part_info.get('pages', [])))}")
                                    
                                    # Field type breakdown
                                    types = defaultdict(int)
                                    for field in fields:
                                        types[field.field_type] += 1
                                    
                                    type_summary = ", ".join([f"{count} {ftype}" for ftype, count in types.items()])
                                    st.caption(f"Field types: {type_summary}")
                                    st.divider()
            
            with col2:
                if st.session_state.pdf_processed:
                    if st.button("🔄 Reset", type="secondary", use_container_width=True):
                        # Clear all session state
                        for key in list(st.session_state.keys()):
                            if key != 'debug_mode':
                                del st.session_state[key]
                        extractor.init_session_state()
                        st.rerun()
    
    with tab2:
        if not st.session_state.pdf_processed:
            st.info("👆 Please upload and extract a PDF form first.")
        else:
            render_mapping_interface(extractor)
    
    with tab3:
        if not st.session_state.pdf_processed:
            st.info("👆 Please upload and extract a PDF form first.")
        else:
            st.markdown("## 📥 Export & Download")
            
            # Summary
            total = len(st.session_state.fields)
            mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
            quest = sum(1 for f in st.session_state.fields if f.to_questionnaire)
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Fields", total)
            col2.metric("Mapped to Database", mapped)
            col3.metric("In Questionnaire", quest)
            
            st.markdown("---")
            
            # Export options
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 📄 TypeScript Export")
                st.markdown("Database mappings for your application")
                
                ts_code = extractor.generate_typescript()
                
                st.download_button(
                    label="⬇️ Download TypeScript File",
                    data=ts_code,
                    file_name=f"{st.session_state.form_info.get('form_number', 'form')}.ts",
                    mime="text/typescript",
                    use_container_width=True
                )
                
                with st.expander("Preview TypeScript"):
                    st.code(ts_code, language="typescript")
            
            with col2:
                st.markdown("### 📋 JSON Export")
                st.markdown("Questionnaire configuration")
                
                json_code = extractor.generate_json()
                
                st.download_button(
                    label="⬇️ Download JSON File",
                    data=json_code,
                    file_name=f"{st.session_state.form_info.get('form_number', 'form')}-questionnaire.json",
                    mime="application/json",
                    use_container_width=True
                )
                
                with st.expander("Preview JSON"):
                    st.code(json_code, language="json")
            
            # Combined export
            st.markdown("---")
            if st.button("📦 Download Both Files", type="primary", use_container_width=True):
                st.markdown("### Downloads Ready:")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button(
                        "TypeScript (.ts)",
                        extractor.generate_typescript(),
                        f"{st.session_state.form_info.get('form_number', 'form')}.ts",
                        mime="text/typescript"
                    )
                with col2:
                    st.download_button(
                        "JSON (.json)",
                        extractor.generate_json(),
                        f"{st.session_state.form_info.get('form_number', 'form')}-questionnaire.json",
                        mime="application/json"
                    )

if __name__ == "__main__":
    main()
, '', key)
        key = re.sub(r'_+
    
    def _generate_field_label(self, name: str) -> str:
        """Generate human-readable label"""
        # Common label mappings
        label_map = {
            'familyname': 'Family Name (Last Name)',
            'lastname': 'Last Name',
            'givenname': 'Given Name (First Name)', 
            'firstname': 'First Name',
            'middlename': 'Middle Name',
            'anumber': 'Alien Registration Number (A-Number)',
            'uscisaccount': 'USCIS Online Account Number',
            'dateofbirth': 'Date of Birth',
            'ssn': 'Social Security Number',
            'email': 'Email Address',
            'phone': 'Phone Number',
            'daytimephone': 'Daytime Phone Number',
            'mobile': 'Mobile Phone Number',
            'street': 'Street Address',
            'city': 'City or Town',
            'state': 'State',
            'zip': 'ZIP Code',
            'country': 'Country',
            'barnumber': 'Bar Number',
            'statebarnumber': 'State Bar Number',
            'lawfirm': 'Law Firm Name',
            'lawfirmname': 'Law Firm Name',
            'licensingauthority': 'Licensing Authority',
            'workphone': 'Work Phone Number',
            'faxnumber': 'Fax Number'
        }
        
        # Check for exact match
        name_lower = name.lower().replace('_', '').replace('-', '').replace(' ', '')
        for key, label in label_map.items():
            if key in name_lower or name_lower in key:
                return label
        
        # Convert to title case
        label = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
        label = label.replace('_', ' ').replace('-', ' ')
        label = ' '.join(label.split())
        label = label.title()
        
        return label
    
    def _map_widget_type(self, widget_type: int) -> str:
        """Map PDF widget type to field type"""
        type_map = {
            1: "button",
            2: "checkbox",
            3: "radio",
            4: "text",
            5: "dropdown",
            6: "list",
            7: "signature"
        }
        return type_map.get(widget_type, "text")
    
    def suggest_mapping(self, field: PDFField) -> Optional[str]:
        """Suggest database mapping for field"""
        label_lower = field.field_label.lower()
        key_lower = field.field_key.lower()
        
        # Try pattern matching with both label and key
        for pattern, suggestions in self.field_patterns.items():
            if re.search(pattern, label_lower) or re.search(pattern, key_lower):
                # Return first matching suggestion
                for suggestion in suggestions:
                    if suggestion in self.db_paths:
                        return suggestion
        
        # Try exact field name matching
        for db_path in self.db_paths:
            path_parts = db_path.split('.')
            field_name = path_parts[-1].lower()
            
            # Check both label and key
            if field_name in label_lower.replace(' ', '').lower() or field_name in key_lower:
                return db_path
        
        return None
    
    def generate_typescript(self) -> str:
        """Generate TypeScript export"""
        form_name = st.session_state.form_info.get('form_number', 'Form').replace('-', '')
        
        # Group fields
        sections = {
            'customerData': {},
            'beneficiaryData': {},
            'attorneyData': {},
            'questionnaireData': {},
            'caseData': {},
            'defaultData': {},
            'conditionalData': {}
        }
        
        for field in st.session_state.fields:
            if field.is_mapped and field.db_mapping:
                # Determine section
                if field.db_mapping.startswith('customer.'):
                    section = 'customerData'
                elif field.db_mapping.startswith('beneficiary.'):
                    section = 'beneficiaryData'
                elif field.db_mapping.startswith('attorney.') or field.db_mapping.startswith('attorneyLawfirmDetails.'):
                    section = 'attorneyData'
                elif field.db_mapping.startswith('case.'):
                    section = 'caseData'
                else:
                    continue
                
                # Add field
                suffix = self._get_ts_suffix(field.field_type)
                sections[section][field.field_key] = f"{field.db_mapping}{suffix}"
            
            elif field.to_questionnaire:
                # Use question_key for questionnaire items
                key = field.question_key if field.question_key else field.field_key
                sections['questionnaireData'][key] = f"{field.field_key}:ConditionBox"
        
        # Generate TypeScript
        ts = f'export const {form_name} = {{\n'
        ts += f'    "formname": "{form_name}",\n'
        
        # Add sections
        for section_name, fields in sections.items():
            if section_name == 'conditionalData':
                continue  # Handle separately
            
            if fields:
                ts += f'    "{section_name}": {{\n'
                field_entries = []
                for key, value in fields.items():
                    field_entries.append(f'        "{key}": "{value}"')
                ts += ',\n'.join(field_entries)
                ts += '\n    },\n'
            else:
                ts += f'    "{section_name}": null,\n'
        
        # Add conditional data (empty for now)
        ts += '    "conditionalData": {},\n'
        
        # Add PDF name
        ts += f'    "pdfName": "{st.session_state.form_info.get("form_number", "Unknown")}"\n'
        ts += '};\n\n'
        ts += f'export default {form_name};'
        
        return ts
    
    def _get_ts_suffix(self, field_type: str) -> str:
        """Get TypeScript suffix for field type"""
        suffix_map = {
            'text': ':TextBox',
            'checkbox': ':CheckBox',
            'radio': ':RadioBox',
            'dropdown': ':DropdownBox',
            'signature': ':SignatureBox',
            'date': ':Date',
            'button': ':ButtonBox'
        }
        return suffix_map.get(field_type, ':TextBox')
    
    def generate_json(self) -> str:
        """Generate JSON export for questionnaire"""
        controls = []
        
        # Add fields by part
        for part_name, fields in st.session_state.fields_by_part.items():
            # Get part info
            part_info = st.session_state.part_structure.get(part_name, {})
            
            # Get questionnaire fields
            quest_fields = [f for f in fields if f.to_questionnaire]
            
            if quest_fields:
                # Add part title
                title_text = f"{part_name}"
                if part_info.get('title'):
                    title_text += f": {part_info['title']}"
                
                controls.append({
                    "name": f"{part_name.lower().replace(' ', '_')}_title",
                    "label": title_text,
                    "type": "title",
                    "validators": {},
                    "style": {"col": "12"}
                })
                
                # Add fields
                for field in quest_fields:
                    control = {
                        "name": field.field_key,
                        "label": field.field_label,
                        "type": "colorSwitch" if field.field_type in ["checkbox", "radio"] else field.field_type,
                        "validators": {}
                    }
                    
                    # Add field-specific properties
                    if field.field_type == "text":
                        control["style"] = {"col": "7"}
                    elif field.field_type in ["checkbox", "radio"]:
                        control["style"] = {"col": "12"}
                        if field.field_type == "radio":
                            control["id"] = field.field_key
                            control["value"] = "1"
                    
                    controls.append(control)
        
        return json.dumps({"controls": controls}, indent=2)

def render_mapping_interface(extractor: FieldExtractor):
    """Render the enhanced field mapping interface organized by parts"""
    st.markdown("## 🎯 Field Mapping by Parts")
    
    # Top controls
    with st.container():
        st.markdown('<div class="part-selector">', unsafe_allow_html=True)
        
        col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
        
        with col1:
            # Part selector
            part_options = ['All Parts'] + list(st.session_state.fields_by_part.keys())
            selected_part = st.selectbox(
                "📑 Select Part",
                part_options,
                index=part_options.index(st.session_state.selected_part) if st.session_state.selected_part in part_options else 0,
                key="part_selector"
            )
            st.session_state.selected_part = selected_part
        
        with col2:
            # Mapping filter
            mapping_filter = st.selectbox(
                "🔍 Filter by Status",
                ["All Fields", "Mapped", "Unmapped", "Questionnaire"],
                key="mapping_filter_select"
            )
            st.session_state.mapping_filter = mapping_filter.lower().replace(' fields', '').replace(' ', '_')
        
        with col3:
            # Database browser toggle
            st.session_state.show_db_browser = st.checkbox(
                "🗂️ Show DB Browser",
                value=st.session_state.show_db_browser,
                help="Show database structure browser"
            )
        
        with col4:
            # Field count
            if selected_part == 'All Parts':
                total_fields = len(st.session_state.fields)
            else:
                total_fields = len(st.session_state.fields_by_part.get(selected_part, []))
            
            mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
            st.metric("Progress", f"{mapped}/{total_fields}", f"{mapped/total_fields*100:.0f}%")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Quick actions
    st.markdown("### ⚡ Quick Actions")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🤖 Auto-Map Current View", use_container_width=True):
            fields_to_map = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_map = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            mapped_count = 0
            for field in fields_to_map:
                if not field.is_mapped and not field.to_questionnaire and field.field_type == 'text':
                    suggestion = extractor.suggest_mapping(field)
                    if suggestion:
                        field.db_mapping = suggestion
                        field.is_mapped = True
                        mapped_count += 1
            st.success(f"Auto-mapped {mapped_count} fields!")
            st.rerun()
    
    with col2:
        if st.button("📋 All Checkboxes → Quest", use_container_width=True):
            fields_to_move = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_move = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            count = 0
            for field in fields_to_move:
                if field.field_type in ['checkbox', 'radio'] and not field.to_questionnaire:
                    field.to_questionnaire = True
                    field.is_mapped = False
                    count += 1
            st.success(f"Moved {count} fields to questionnaire!")
            st.rerun()
    
    with col3:
        if st.button("🔄 Reset Current View", use_container_width=True):
            fields_to_reset = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_reset = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            for field in fields_to_reset:
                field.is_mapped = False
                field.db_mapping = None
                field.to_questionnaire = field.field_type in ['checkbox', 'radio', 'button']
            st.success("Reset complete!")
            st.rerun()
    
    with col4:
        unmapped = sum(1 for f in st.session_state.fields if not f.is_mapped and not f.to_questionnaire)
        if st.button(f"📋 All Unmapped → Quest ({unmapped})", use_container_width=True):
            fields_to_move = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_move = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            count = 0
            for field in fields_to_move:
                if not field.is_mapped and not field.to_questionnaire:
                    field.to_questionnaire = True
                    count += 1
            st.success(f"Moved {count} fields to questionnaire!")
            st.rerun()
    
    # Database object browser
    if st.session_state.show_db_browser:
        with st.expander("🗂️ Database Structure Browser", expanded=True):
            st.markdown("### Available Database Paths")
            st.caption("Click any path to copy it")
            
            # Create tabs for each main object
            tabs = st.tabs(list(DB_OBJECTS.keys()))
            
            for i, (obj_name, tab) in enumerate(zip(DB_OBJECTS.keys(), tabs)):
                with tab:
                    for sub_obj, fields in DB_OBJECTS[obj_name].items():
                        if sub_obj:
                            st.markdown(f"**{sub_obj}:**")
                        
                        # Display fields in columns
                        field_cols = st.columns(3)
                        for j, field in enumerate(fields):
                            col_idx = j % 3
                            with field_cols[col_idx]:
                                if sub_obj:
                                    path = f"{obj_name}.{sub_obj}.{field}"
                                else:
                                    path = f"{obj_name}.{field}"
                                
                                if st.button(f"📋 {field}", key=f"copy_{path}", use_container_width=True):
                                    st.code(path, language="text")
    
    # Field mapping interface organized by parts
    st.markdown("### 📝 Field Mappings by Part")
    
    # Get parts to display
    if st.session_state.selected_part == 'All Parts':
        parts_to_show = st.session_state.fields_by_part.items()
    else:
        parts_to_show = [(st.session_state.selected_part, 
                         st.session_state.fields_by_part.get(st.session_state.selected_part, []))]
    
    # Display each part
    for part_name, fields in parts_to_show:
        # Filter fields based on mapping filter
        if st.session_state.mapping_filter == 'mapped':
            display_fields = [f for f in fields if f.is_mapped]
        elif st.session_state.mapping_filter == 'unmapped':
            display_fields = [f for f in fields if not f.is_mapped and not f.to_questionnaire]
        elif st.session_state.mapping_filter == 'questionnaire':
            display_fields = [f for f in fields if f.to_questionnaire]
        else:
            display_fields = fields
        
        if not display_fields:
            continue
        
        # Get part info
        part_info = st.session_state.part_structure.get(part_name, {})
        
        # Part header with stats
        part_mapped = sum(1 for f in fields if f.is_mapped)
        part_quest = sum(1 for f in fields if f.to_questionnaire)
        part_unmapped = len(fields) - part_mapped - part_quest
        
        with st.container():
            st.markdown(f'''
            <div class="part-header">
                <strong>{part_name}</strong> {part_info.get('title', '')} 
                <br>
                <small>Total: {len(fields)} | Mapped: {part_mapped} | Questionnaire: {part_quest} | Unmapped: {part_unmapped}</small>
                <br>
                <small>Pages: {', '.join(map(str, part_info.get('pages', [])))}</small>
            </div>
            ''', unsafe_allow_html=True)
        
        # Display fields for this part
        for idx, field in enumerate(display_fields):
            with st.container():
                st.markdown('<div class="mapping-row">', unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    # Field info
                    display_label = field.field_label
                    if field.item_number:
                        display_label = f"{field.item_number}. {display_label}"
                    
                    st.markdown(f'<div class="field-label">{display_label}</div>', unsafe_allow_html=True)
                    
                    # Build field metadata
                    meta_parts = [
                        f'<span class="field-type">{field.field_type}</span>',
                        f'Field: {field.field_key}',
                        f'Page {field.page}'
                    ]
                    
                    # Only show quest key if it's different from field key
                    if field.to_questionnaire and field.question_key and field.question_key != field.field_key:
                        meta_parts.append(f'Quest: {field.question_key}')
                    
                    st.markdown(f"""
                    <div class="field-meta">
                        {' • '.join(meta_parts)}
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    # Create unique key for this field
                    unique_key = f"{part_name}_{field.field_id}_{idx}"
                    
                    col2a, col2b = st.columns([3, 1])
                    
                    with col2a:
                        # Database mapping dropdown
                        grouped_options = {
                            "Actions": ["-- Select Database Field --", "📋 Move to Questionnaire"],
                            "beneficiary": [],
                            "petitioner": [],
                            "customer": [],
                            "attorney": [],
                            "attorneyLawfirmDetails": [],
                            "case": [],
                            "employment": []
                        }
                        
                        # Group database paths
                        for path in extractor.db_paths:
                            obj_name = path.split('.')[0]
                            if obj_name in grouped_options:
                                grouped_options[obj_name].append(path)
                        
                        # Build flat list with separators
                        options = []
                        for group, items in grouped_options.items():
                            if items:
                                if options:  # Add separator between groups
                                    options.append(f"── {group} ──")
                                options.extend(items)
                        
                        # Current selection
                        if field.is_mapped and field.db_mapping:
                            current_value = field.db_mapping
                        elif field.to_questionnaire:
                            current_value = "📋 Move to Questionnaire"
                        else:
                            # Try to get suggestion
                            suggestion = extractor.suggest_mapping(field)
                            current_value = suggestion if suggestion else "-- Select Database Field --"
                        
                        # Find index
                        try:
                            current_index = options.index(current_value)
                        except ValueError:
                            current_index = 0
                        
                        selected = st.selectbox(
                            "Database Mapping",
                            options,
                            index=current_index,
                            key=f"map_{unique_key}",
                            label_visibility="collapsed"
                        )
                        
                        # Handle selection
                        if selected != current_value and not selected.startswith("──"):
                            if selected == "📋 Move to Questionnaire":
                                field.to_questionnaire = True
                                field.is_mapped = False
                                field.db_mapping = None
                            elif selected != "-- Select Database Field --":
                                field.db_mapping = selected
                                field.is_mapped = True
                                field.to_questionnaire = False
                            st.rerun()
                    
                    with col2b:
                        # Quick questionnaire toggle
                        if st.button("📋", key=f"quest_btn_{unique_key}", 
                                   help="Quick add to questionnaire",
                                   use_container_width=True):
                            field.to_questionnaire = True
                            field.is_mapped = False
                            field.db_mapping = None
                            st.rerun()
                
                with col3:
                    # Status
                    status = field.get_status()
                    if "Mapped" in status:
                        badge_class = "status-mapped"
                    elif "Questionnaire" in status:
                        badge_class = "status-questionnaire"
                    else:
                        badge_class = "status-unmapped"
                    
                    st.markdown(f'<span class="status-badge {badge_class}">{status}</span>', 
                              unsafe_allow_html=True)
                
                st.markdown('</div>', unsafe_allow_html=True)
        
        # Add spacing between parts
        st.markdown("<br>", unsafe_allow_html=True)

def main():
    """Main application"""
    st.markdown("# 🤖 USCIS Form Reader Pro")
    st.markdown("### Complete PDF Form Field Extraction & Mapping Solution")
    
    # Initialize extractor
    extractor = FieldExtractor()
    
    # Sidebar
    with st.sidebar:
        st.markdown("## ⚙️ Settings")
        st.session_state.debug_mode = st.checkbox("Debug Mode", value=False)
        
        if st.session_state.pdf_processed:
            st.markdown("---")
            st.markdown("### 📊 Statistics")
            stats = st.session_state.extraction_stats
            st.metric("Total Pages", stats.get('total_pages', 0))
            st.metric("Total Parts", stats.get('total_parts', 0))
            st.metric("Total Fields", stats.get('total_fields', 0))
            st.metric("Extraction Time", f"{stats.get('extraction_time', 0):.2f}s")
            
            if stats.get('errors'):
                st.warning(f"{len(stats['errors'])} errors occurred")
                with st.expander("View Errors"):
                    for error in stats['errors']:
                        st.text(error)
            
            # Field summary
            total = len(st.session_state.fields)
            mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
            quest = sum(1 for f in st.session_state.fields if f.to_questionnaire)
            
            st.markdown("---")
            st.markdown("### 📈 Mapping Progress")
            st.metric("Mapped to DB", f"{mapped} ({mapped/total*100:.1f}%)")
            st.metric("In Questionnaire", f"{quest} ({quest/total*100:.1f}%)")
            st.metric("Unmapped", f"{total - mapped - quest}")
            
            # Progress bar
            progress = (mapped + quest) / total if total > 0 else 0
            st.progress(progress)
            
            # Part breakdown
            st.markdown("---")
            st.markdown("### 📑 Parts Overview")
            for part_name, part_info in st.session_state.part_structure.items():
                fields = st.session_state.fields_by_part.get(part_name, [])
                mapped = sum(1 for f in fields if f.is_mapped)
                quest = sum(1 for f in fields if f.to_questionnaire)
                st.caption(f"{part_name}: {len(fields)} fields ({mapped} mapped, {quest} quest)")
    
    # Main tabs
    tab1, tab2, tab3 = st.tabs(["📤 Upload & Extract", "🎯 Map Fields", "📥 Export & Download"])
    
    with tab1:
        st.markdown("## Upload USCIS PDF Form")
        
        uploaded_file = st.file_uploader(
            "Choose a USCIS PDF form",
            type=['pdf'],
            help="Upload any fillable USCIS form (I-90, I-129, G-28, etc.)",
            key="pdf_uploader"
        )
        
        if uploaded_file:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                if st.button("🚀 Extract Fields by Parts", type="primary", use_container_width=True):
                    with st.spinner("Analyzing PDF structure and extracting fields by parts..."):
                        if extractor.extract_from_pdf(uploaded_file):
                            st.success(f"""
                            ✅ Successfully extracted {len(st.session_state.fields)} fields from {st.session_state.form_info.get('form_number', 'form')}!
                            
                            Found {len(st.session_state.fields_by_part)} parts with fields.
                            """)
                            
                            # Show extraction summary
                            with st.expander("📊 Extraction Summary", expanded=True):
                                for part_name, fields in st.session_state.fields_by_part.items():
                                    part_info = st.session_state.part_structure.get(part_name, {})
                                    
                                    st.write(f"**{part_name}** {part_info.get('title', '')}")
                                    st.write(f"- Fields: {len(fields)}")
                                    st.write(f"- Pages: {', '.join(map(str, part_info.get('pages', [])))}")
                                    
                                    # Field type breakdown
                                    types = defaultdict(int)
                                    for field in fields:
                                        types[field.field_type] += 1
                                    
                                    type_summary = ", ".join([f"{count} {ftype}" for ftype, count in types.items()])
                                    st.caption(f"Field types: {type_summary}")
                                    st.divider()
            
            with col2:
                if st.session_state.pdf_processed:
                    if st.button("🔄 Reset", type="secondary", use_container_width=True):
                        # Clear all session state
                        for key in list(st.session_state.keys()):
                            if key != 'debug_mode':
                                del st.session_state[key]
                        extractor.init_session_state()
                        st.rerun()
    
    with tab2:
        if not st.session_state.pdf_processed:
            st.info("👆 Please upload and extract a PDF form first.")
        else:
            render_mapping_interface(extractor)
    
    with tab3:
        if not st.session_state.pdf_processed:
            st.info("👆 Please upload and extract a PDF form first.")
        else:
            st.markdown("## 📥 Export & Download")
            
            # Summary
            total = len(st.session_state.fields)
            mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
            quest = sum(1 for f in st.session_state.fields if f.to_questionnaire)
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Fields", total)
            col2.metric("Mapped to Database", mapped)
            col3.metric("In Questionnaire", quest)
            
            st.markdown("---")
            
            # Export options
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 📄 TypeScript Export")
                st.markdown("Database mappings for your application")
                
                ts_code = extractor.generate_typescript()
                
                st.download_button(
                    label="⬇️ Download TypeScript File",
                    data=ts_code,
                    file_name=f"{st.session_state.form_info.get('form_number', 'form')}.ts",
                    mime="text/typescript",
                    use_container_width=True
                )
                
                with st.expander("Preview TypeScript"):
                    st.code(ts_code, language="typescript")
            
            with col2:
                st.markdown("### 📋 JSON Export")
                st.markdown("Questionnaire configuration")
                
                json_code = extractor.generate_json()
                
                st.download_button(
                    label="⬇️ Download JSON File",
                    data=json_code,
                    file_name=f"{st.session_state.form_info.get('form_number', 'form')}-questionnaire.json",
                    mime="application/json",
                    use_container_width=True
                )
                
                with st.expander("Preview JSON"):
                    st.code(json_code, language="json")
            
            # Combined export
            st.markdown("---")
            if st.button("📦 Download Both Files", type="primary", use_container_width=True):
                st.markdown("### Downloads Ready:")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button(
                        "TypeScript (.ts)",
                        extractor.generate_typescript(),
                        f"{st.session_state.form_info.get('form_number', 'form')}.ts",
                        mime="text/typescript"
                    )
                with col2:
                    st.download_button(
                        "JSON (.json)",
                        extractor.generate_json(),
                        f"{st.session_state.form_info.get('form_number', 'form')}-questionnaire.json",
                        mime="application/json"
                    )

if __name__ == "__main__":
    main()
, '', key)  # Remove trailing underscores
        
        # Common abbreviations
        abbreviations = {
            'family_name': 'familyName',
            'last_name': 'lastName',
            'given_name': 'givenName',
            'first_name': 'firstName',
            'middle_name': 'middleName',
            'date_of_birth': 'dob',
            'social_security': 'ssn',
            'alien_number': 'aNumber',
            'email_address': 'email',
            'phone_number': 'phone',
            'street_address': 'street',
            'zip_code': 'zip',
            'state_bar_number': 'stateBarNumber',
            'law_firm_name': 'lawFirmName',
            'licensing_authority': 'licensingAuthority'
        }
        
        key_lower = key.lower()
        for pattern, replacement in abbreviations.items():
            if pattern in key_lower:
                return replacement
        
        # Convert to camelCase
        parts = key.split('_')
        if len(parts) > 1:
            key = parts[0].lower() + ''.join(p.capitalize() for p in parts[1:] if p)
        else:
            key = key.lower() if key else 'field'
        
        # Ensure we have a valid key
        if not key or key.isdigit():
            key = 'field'
        
        # Limit length
        if len(key) > 30:
            key = key[:30]
        
        return key
    
    def _generate_field_label(self, name: str) -> str:
        """Generate human-readable label"""
        # Common label mappings
        label_map = {
            'familyname': 'Family Name (Last Name)',
            'lastname': 'Last Name',
            'givenname': 'Given Name (First Name)', 
            'firstname': 'First Name',
            'middlename': 'Middle Name',
            'anumber': 'Alien Registration Number (A-Number)',
            'uscisaccount': 'USCIS Online Account Number',
            'dateofbirth': 'Date of Birth',
            'ssn': 'Social Security Number',
            'email': 'Email Address',
            'phone': 'Phone Number',
            'daytimephone': 'Daytime Phone Number',
            'mobile': 'Mobile Phone Number',
            'street': 'Street Address',
            'city': 'City or Town',
            'state': 'State',
            'zip': 'ZIP Code',
            'country': 'Country',
            'barnumber': 'Bar Number',
            'statebarnumber': 'State Bar Number',
            'lawfirm': 'Law Firm Name',
            'lawfirmname': 'Law Firm Name',
            'licensingauthority': 'Licensing Authority',
            'workphone': 'Work Phone Number',
            'faxnumber': 'Fax Number'
        }
        
        # Check for exact match
        name_lower = name.lower().replace('_', '').replace('-', '').replace(' ', '')
        for key, label in label_map.items():
            if key in name_lower or name_lower in key:
                return label
        
        # Convert to title case
        label = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
        label = label.replace('_', ' ').replace('-', ' ')
        label = ' '.join(label.split())
        label = label.title()
        
        return label
    
    def _map_widget_type(self, widget_type: int) -> str:
        """Map PDF widget type to field type"""
        type_map = {
            1: "button",
            2: "checkbox",
            3: "radio",
            4: "text",
            5: "dropdown",
            6: "list",
            7: "signature"
        }
        return type_map.get(widget_type, "text")
    
    def suggest_mapping(self, field: PDFField) -> Optional[str]:
        """Suggest database mapping for field"""
        label_lower = field.field_label.lower()
        key_lower = field.field_key.lower()
        
        # Try pattern matching with both label and key
        for pattern, suggestions in self.field_patterns.items():
            if re.search(pattern, label_lower) or re.search(pattern, key_lower):
                # Return first matching suggestion
                for suggestion in suggestions:
                    if suggestion in self.db_paths:
                        return suggestion
        
        # Try exact field name matching
        for db_path in self.db_paths:
            path_parts = db_path.split('.')
            field_name = path_parts[-1].lower()
            
            # Check both label and key
            if field_name in label_lower.replace(' ', '').lower() or field_name in key_lower:
                return db_path
        
        return None
    
    def generate_typescript(self) -> str:
        """Generate TypeScript export"""
        form_name = st.session_state.form_info.get('form_number', 'Form').replace('-', '')
        
        # Group fields
        sections = {
            'customerData': {},
            'beneficiaryData': {},
            'attorneyData': {},
            'questionnaireData': {},
            'caseData': {},
            'defaultData': {},
            'conditionalData': {}
        }
        
        for field in st.session_state.fields:
            if field.is_mapped and field.db_mapping:
                # Determine section
                if field.db_mapping.startswith('customer.'):
                    section = 'customerData'
                elif field.db_mapping.startswith('beneficiary.'):
                    section = 'beneficiaryData'
                elif field.db_mapping.startswith('attorney.') or field.db_mapping.startswith('attorneyLawfirmDetails.'):
                    section = 'attorneyData'
                elif field.db_mapping.startswith('case.'):
                    section = 'caseData'
                else:
                    continue
                
                # Add field
                suffix = self._get_ts_suffix(field.field_type)
                sections[section][field.field_key] = f"{field.db_mapping}{suffix}"
            
            elif field.to_questionnaire:
                # Use question_key for questionnaire items
                key = field.question_key if field.question_key else field.field_key
                sections['questionnaireData'][key] = f"{field.field_key}:ConditionBox"
        
        # Generate TypeScript
        ts = f'export const {form_name} = {{\n'
        ts += f'    "formname": "{form_name}",\n'
        
        # Add sections
        for section_name, fields in sections.items():
            if section_name == 'conditionalData':
                continue  # Handle separately
            
            if fields:
                ts += f'    "{section_name}": {{\n'
                field_entries = []
                for key, value in fields.items():
                    field_entries.append(f'        "{key}": "{value}"')
                ts += ',\n'.join(field_entries)
                ts += '\n    },\n'
            else:
                ts += f'    "{section_name}": null,\n'
        
        # Add conditional data (empty for now)
        ts += '    "conditionalData": {},\n'
        
        # Add PDF name
        ts += f'    "pdfName": "{st.session_state.form_info.get("form_number", "Unknown")}"\n'
        ts += '};\n\n'
        ts += f'export default {form_name};'
        
        return ts
    
    def _get_ts_suffix(self, field_type: str) -> str:
        """Get TypeScript suffix for field type"""
        suffix_map = {
            'text': ':TextBox',
            'checkbox': ':CheckBox',
            'radio': ':RadioBox',
            'dropdown': ':DropdownBox',
            'signature': ':SignatureBox',
            'date': ':Date',
            'button': ':ButtonBox'
        }
        return suffix_map.get(field_type, ':TextBox')
    
    def generate_json(self) -> str:
        """Generate JSON export for questionnaire"""
        controls = []
        
        # Add fields by part
        for part_name, fields in st.session_state.fields_by_part.items():
            # Get part info
            part_info = st.session_state.part_structure.get(part_name, {})
            
            # Get questionnaire fields
            quest_fields = [f for f in fields if f.to_questionnaire]
            
            if quest_fields:
                # Add part title
                title_text = f"{part_name}"
                if part_info.get('title'):
                    title_text += f": {part_info['title']}"
                
                controls.append({
                    "name": f"{part_name.lower().replace(' ', '_')}_title",
                    "label": title_text,
                    "type": "title",
                    "validators": {},
                    "style": {"col": "12"}
                })
                
                # Add fields
                for field in quest_fields:
                    control = {
                        "name": field.field_key,
                        "label": field.field_label,
                        "type": "colorSwitch" if field.field_type in ["checkbox", "radio"] else field.field_type,
                        "validators": {}
                    }
                    
                    # Add field-specific properties
                    if field.field_type == "text":
                        control["style"] = {"col": "7"}
                    elif field.field_type in ["checkbox", "radio"]:
                        control["style"] = {"col": "12"}
                        if field.field_type == "radio":
                            control["id"] = field.field_key
                            control["value"] = "1"
                    
                    controls.append(control)
        
        return json.dumps({"controls": controls}, indent=2)

def render_mapping_interface(extractor: FieldExtractor):
    """Render the enhanced field mapping interface organized by parts"""
    st.markdown("## 🎯 Field Mapping by Parts")
    
    # Top controls
    with st.container():
        st.markdown('<div class="part-selector">', unsafe_allow_html=True)
        
        col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
        
        with col1:
            # Part selector
            part_options = ['All Parts'] + list(st.session_state.fields_by_part.keys())
            selected_part = st.selectbox(
                "📑 Select Part",
                part_options,
                index=part_options.index(st.session_state.selected_part) if st.session_state.selected_part in part_options else 0,
                key="part_selector"
            )
            st.session_state.selected_part = selected_part
        
        with col2:
            # Mapping filter
            mapping_filter = st.selectbox(
                "🔍 Filter by Status",
                ["All Fields", "Mapped", "Unmapped", "Questionnaire"],
                key="mapping_filter_select"
            )
            st.session_state.mapping_filter = mapping_filter.lower().replace(' fields', '').replace(' ', '_')
        
        with col3:
            # Database browser toggle
            st.session_state.show_db_browser = st.checkbox(
                "🗂️ Show DB Browser",
                value=st.session_state.show_db_browser,
                help="Show database structure browser"
            )
        
        with col4:
            # Field count
            if selected_part == 'All Parts':
                total_fields = len(st.session_state.fields)
            else:
                total_fields = len(st.session_state.fields_by_part.get(selected_part, []))
            
            mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
            st.metric("Progress", f"{mapped}/{total_fields}", f"{mapped/total_fields*100:.0f}%")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Quick actions
    st.markdown("### ⚡ Quick Actions")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🤖 Auto-Map Current View", use_container_width=True):
            fields_to_map = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_map = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            mapped_count = 0
            for field in fields_to_map:
                if not field.is_mapped and not field.to_questionnaire and field.field_type == 'text':
                    suggestion = extractor.suggest_mapping(field)
                    if suggestion:
                        field.db_mapping = suggestion
                        field.is_mapped = True
                        mapped_count += 1
            st.success(f"Auto-mapped {mapped_count} fields!")
            st.rerun()
    
    with col2:
        if st.button("📋 All Checkboxes → Quest", use_container_width=True):
            fields_to_move = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_move = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            count = 0
            for field in fields_to_move:
                if field.field_type in ['checkbox', 'radio'] and not field.to_questionnaire:
                    field.to_questionnaire = True
                    field.is_mapped = False
                    count += 1
            st.success(f"Moved {count} fields to questionnaire!")
            st.rerun()
    
    with col3:
        if st.button("🔄 Reset Current View", use_container_width=True):
            fields_to_reset = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_reset = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            for field in fields_to_reset:
                field.is_mapped = False
                field.db_mapping = None
                field.to_questionnaire = field.field_type in ['checkbox', 'radio', 'button']
            st.success("Reset complete!")
            st.rerun()
    
    with col4:
        unmapped = sum(1 for f in st.session_state.fields if not f.is_mapped and not f.to_questionnaire)
        if st.button(f"📋 All Unmapped → Quest ({unmapped})", use_container_width=True):
            fields_to_move = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_move = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            count = 0
            for field in fields_to_move:
                if not field.is_mapped and not field.to_questionnaire:
                    field.to_questionnaire = True
                    count += 1
            st.success(f"Moved {count} fields to questionnaire!")
            st.rerun()
    
    # Database object browser
    if st.session_state.show_db_browser:
        with st.expander("🗂️ Database Structure Browser", expanded=True):
            st.markdown("### Available Database Paths")
            st.caption("Click any path to copy it")
            
            # Create tabs for each main object
            tabs = st.tabs(list(DB_OBJECTS.keys()))
            
            for i, (obj_name, tab) in enumerate(zip(DB_OBJECTS.keys(), tabs)):
                with tab:
                    for sub_obj, fields in DB_OBJECTS[obj_name].items():
                        if sub_obj:
                            st.markdown(f"**{sub_obj}:**")
                        
                        # Display fields in columns
                        field_cols = st.columns(3)
                        for j, field in enumerate(fields):
                            col_idx = j % 3
                            with field_cols[col_idx]:
                                if sub_obj:
                                    path = f"{obj_name}.{sub_obj}.{field}"
                                else:
                                    path = f"{obj_name}.{field}"
                                
                                if st.button(f"📋 {field}", key=f"copy_{path}", use_container_width=True):
                                    st.code(path, language="text")
    
    # Field mapping interface organized by parts
    st.markdown("### 📝 Field Mappings by Part")
    
    # Get parts to display
    if st.session_state.selected_part == 'All Parts':
        parts_to_show = st.session_state.fields_by_part.items()
    else:
        parts_to_show = [(st.session_state.selected_part, 
                         st.session_state.fields_by_part.get(st.session_state.selected_part, []))]
    
    # Display each part
    for part_name, fields in parts_to_show:
        # Filter fields based on mapping filter
        if st.session_state.mapping_filter == 'mapped':
            display_fields = [f for f in fields if f.is_mapped]
        elif st.session_state.mapping_filter == 'unmapped':
            display_fields = [f for f in fields if not f.is_mapped and not f.to_questionnaire]
        elif st.session_state.mapping_filter == 'questionnaire':
            display_fields = [f for f in fields if f.to_questionnaire]
        else:
            display_fields = fields
        
        if not display_fields:
            continue
        
        # Get part info
        part_info = st.session_state.part_structure.get(part_name, {})
        
        # Part header with stats
        part_mapped = sum(1 for f in fields if f.is_mapped)
        part_quest = sum(1 for f in fields if f.to_questionnaire)
        part_unmapped = len(fields) - part_mapped - part_quest
        
        with st.container():
            st.markdown(f'''
            <div class="part-header">
                <strong>{part_name}</strong> {part_info.get('title', '')} 
                <br>
                <small>Total: {len(fields)} | Mapped: {part_mapped} | Questionnaire: {part_quest} | Unmapped: {part_unmapped}</small>
                <br>
                <small>Pages: {', '.join(map(str, part_info.get('pages', [])))}</small>
            </div>
            ''', unsafe_allow_html=True)
        
        # Display fields for this part
        for idx, field in enumerate(display_fields):
            with st.container():
                st.markdown('<div class="mapping-row">', unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    # Field info
                    display_label = field.field_label
                    if field.item_number:
                        display_label = f"{field.item_number}. {display_label}"
                    
                    st.markdown(f'<div class="field-label">{display_label}</div>', unsafe_allow_html=True)
                    
                    # Build field metadata
                    meta_parts = [
                        f'<span class="field-type">{field.field_type}</span>',
                        f'Field: {field.field_key}',
                        f'Page {field.page}'
                    ]
                    
                    # Only show quest key if it's different from field key
                    if field.to_questionnaire and field.question_key and field.question_key != field.field_key:
                        meta_parts.append(f'Quest: {field.question_key}')
                    
                    st.markdown(f"""
                    <div class="field-meta">
                        {' • '.join(meta_parts)}
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    # Create unique key for this field
                    unique_key = f"{part_name}_{field.field_id}_{idx}"
                    
                    col2a, col2b = st.columns([3, 1])
                    
                    with col2a:
                        # Database mapping dropdown
                        grouped_options = {
                            "Actions": ["-- Select Database Field --", "📋 Move to Questionnaire"],
                            "beneficiary": [],
                            "petitioner": [],
                            "customer": [],
                            "attorney": [],
                            "attorneyLawfirmDetails": [],
                            "case": [],
                            "employment": []
                        }
                        
                        # Group database paths
                        for path in extractor.db_paths:
                            obj_name = path.split('.')[0]
                            if obj_name in grouped_options:
                                grouped_options[obj_name].append(path)
                        
                        # Build flat list with separators
                        options = []
                        for group, items in grouped_options.items():
                            if items:
                                if options:  # Add separator between groups
                                    options.append(f"── {group} ──")
                                options.extend(items)
                        
                        # Current selection
                        if field.is_mapped and field.db_mapping:
                            current_value = field.db_mapping
                        elif field.to_questionnaire:
                            current_value = "📋 Move to Questionnaire"
                        else:
                            # Try to get suggestion
                            suggestion = extractor.suggest_mapping(field)
                            current_value = suggestion if suggestion else "-- Select Database Field --"
                        
                        # Find index
                        try:
                            current_index = options.index(current_value)
                        except ValueError:
                            current_index = 0
                        
                        selected = st.selectbox(
                            "Database Mapping",
                            options,
                            index=current_index,
                            key=f"map_{unique_key}",
                            label_visibility="collapsed"
                        )
                        
                        # Handle selection
                        if selected != current_value and not selected.startswith("──"):
                            if selected == "📋 Move to Questionnaire":
                                field.to_questionnaire = True
                                field.is_mapped = False
                                field.db_mapping = None
                            elif selected != "-- Select Database Field --":
                                field.db_mapping = selected
                                field.is_mapped = True
                                field.to_questionnaire = False
                            st.rerun()
                    
                    with col2b:
                        # Quick questionnaire toggle
                        if st.button("📋", key=f"quest_btn_{unique_key}", 
                                   help="Quick add to questionnaire",
                                   use_container_width=True):
                            field.to_questionnaire = True
                            field.is_mapped = False
                            field.db_mapping = None
                            st.rerun()
                
                with col3:
                    # Status
                    status = field.get_status()
                    if "Mapped" in status:
                        badge_class = "status-mapped"
                    elif "Questionnaire" in status:
                        badge_class = "status-questionnaire"
                    else:
                        badge_class = "status-unmapped"
                    
                    st.markdown(f'<span class="status-badge {badge_class}">{status}</span>', 
                              unsafe_allow_html=True)
                
                st.markdown('</div>', unsafe_allow_html=True)
        
        # Add spacing between parts
        st.markdown("<br>", unsafe_allow_html=True)

def main():
    """Main application"""
    st.markdown("# 🤖 USCIS Form Reader Pro")
    st.markdown("### Complete PDF Form Field Extraction & Mapping Solution")
    
    # Initialize extractor
    extractor = FieldExtractor()
    
    # Sidebar
    with st.sidebar:
        st.markdown("## ⚙️ Settings")
        st.session_state.debug_mode = st.checkbox("Debug Mode", value=False)
        
        if st.session_state.pdf_processed:
            st.markdown("---")
            st.markdown("### 📊 Statistics")
            stats = st.session_state.extraction_stats
            st.metric("Total Pages", stats.get('total_pages', 0))
            st.metric("Total Parts", stats.get('total_parts', 0))
            st.metric("Total Fields", stats.get('total_fields', 0))
            st.metric("Extraction Time", f"{stats.get('extraction_time', 0):.2f}s")
            
            if stats.get('errors'):
                st.warning(f"{len(stats['errors'])} errors occurred")
                with st.expander("View Errors"):
                    for error in stats['errors']:
                        st.text(error)
            
            # Field summary
            total = len(st.session_state.fields)
            mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
            quest = sum(1 for f in st.session_state.fields if f.to_questionnaire)
            
            st.markdown("---")
            st.markdown("### 📈 Mapping Progress")
            st.metric("Mapped to DB", f"{mapped} ({mapped/total*100:.1f}%)")
            st.metric("In Questionnaire", f"{quest} ({quest/total*100:.1f}%)")
            st.metric("Unmapped", f"{total - mapped - quest}")
            
            # Progress bar
            progress = (mapped + quest) / total if total > 0 else 0
            st.progress(progress)
            
            # Part breakdown
            st.markdown("---")
            st.markdown("### 📑 Parts Overview")
            for part_name, part_info in st.session_state.part_structure.items():
                fields = st.session_state.fields_by_part.get(part_name, [])
                mapped = sum(1 for f in fields if f.is_mapped)
                quest = sum(1 for f in fields if f.to_questionnaire)
                st.caption(f"{part_name}: {len(fields)} fields ({mapped} mapped, {quest} quest)")
    
    # Main tabs
    tab1, tab2, tab3 = st.tabs(["📤 Upload & Extract", "🎯 Map Fields", "📥 Export & Download"])
    
    with tab1:
        st.markdown("## Upload USCIS PDF Form")
        
        uploaded_file = st.file_uploader(
            "Choose a USCIS PDF form",
            type=['pdf'],
            help="Upload any fillable USCIS form (I-90, I-129, G-28, etc.)",
            key="pdf_uploader"
        )
        
        if uploaded_file:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                if st.button("🚀 Extract Fields by Parts", type="primary", use_container_width=True):
                    with st.spinner("Analyzing PDF structure and extracting fields by parts..."):
                        if extractor.extract_from_pdf(uploaded_file):
                            st.success(f"""
                            ✅ Successfully extracted {len(st.session_state.fields)} fields from {st.session_state.form_info.get('form_number', 'form')}!
                            
                            Found {len(st.session_state.fields_by_part)} parts with fields.
                            """)
                            
                            # Show extraction summary
                            with st.expander("📊 Extraction Summary", expanded=True):
                                for part_name, fields in st.session_state.fields_by_part.items():
                                    part_info = st.session_state.part_structure.get(part_name, {})
                                    
                                    st.write(f"**{part_name}** {part_info.get('title', '')}")
                                    st.write(f"- Fields: {len(fields)}")
                                    st.write(f"- Pages: {', '.join(map(str, part_info.get('pages', [])))}")
                                    
                                    # Field type breakdown
                                    types = defaultdict(int)
                                    for field in fields:
                                        types[field.field_type] += 1
                                    
                                    type_summary = ", ".join([f"{count} {ftype}" for ftype, count in types.items()])
                                    st.caption(f"Field types: {type_summary}")
                                    st.divider()
            
            with col2:
                if st.session_state.pdf_processed:
                    if st.button("🔄 Reset", type="secondary", use_container_width=True):
                        # Clear all session state
                        for key in list(st.session_state.keys()):
                            if key != 'debug_mode':
                                del st.session_state[key]
                        extractor.init_session_state()
                        st.rerun()
    
    with tab2:
        if not st.session_state.pdf_processed:
            st.info("👆 Please upload and extract a PDF form first.")
        else:
            render_mapping_interface(extractor)
    
    with tab3:
        if not st.session_state.pdf_processed:
            st.info("👆 Please upload and extract a PDF form first.")
        else:
            st.markdown("## 📥 Export & Download")
            
            # Summary
            total = len(st.session_state.fields)
            mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
            quest = sum(1 for f in st.session_state.fields if f.to_questionnaire)
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Fields", total)
            col2.metric("Mapped to Database", mapped)
            col3.metric("In Questionnaire", quest)
            
            st.markdown("---")
            
            # Export options
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 📄 TypeScript Export")
                st.markdown("Database mappings for your application")
                
                ts_code = extractor.generate_typescript()
                
                st.download_button(
                    label="⬇️ Download TypeScript File",
                    data=ts_code,
                    file_name=f"{st.session_state.form_info.get('form_number', 'form')}.ts",
                    mime="text/typescript",
                    use_container_width=True
                )
                
                with st.expander("Preview TypeScript"):
                    st.code(ts_code, language="typescript")
            
            with col2:
                st.markdown("### 📋 JSON Export")
                st.markdown("Questionnaire configuration")
                
                json_code = extractor.generate_json()
                
                st.download_button(
                    label="⬇️ Download JSON File",
                    data=json_code,
                    file_name=f"{st.session_state.form_info.get('form_number', 'form')}-questionnaire.json",
                    mime="application/json",
                    use_container_width=True
                )
                
                with st.expander("Preview JSON"):
                    st.code(json_code, language="json")
            
            # Combined export
            st.markdown("---")
            if st.button("📦 Download Both Files", type="primary", use_container_width=True):
                st.markdown("### Downloads Ready:")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button(
                        "TypeScript (.ts)",
                        extractor.generate_typescript(),
                        f"{st.session_state.form_info.get('form_number', 'form')}.ts",
                        mime="text/typescript"
                    )
                with col2:
                    st.download_button(
                        "JSON (.json)",
                        extractor.generate_json(),
                        f"{st.session_state.form_info.get('form_number', 'form')}-questionnaire.json",
                        mime="application/json"
                    )

if __name__ == "__main__":
    main()
, '', key)
    
    def _generate_field_label(self, name: str) -> str:
        """Generate human-readable label"""
        # Remove common suffixes first
        cleaned_name = re.sub(r'(?i)(checkbox|check|box|field|text)\d*
    
    def _map_widget_type(self, widget_type: int) -> str:
        """Map PDF widget type to field type"""
        type_map = {
            1: "button",
            2: "checkbox",
            3: "radio",
            4: "text",
            5: "dropdown",
            6: "list",
            7: "signature"
        }
        return type_map.get(widget_type, "text")
    
    def suggest_mapping(self, field: PDFField) -> Optional[str]:
        """Suggest database mapping for field"""
        label_lower = field.field_label.lower()
        key_lower = field.field_key.lower()
        
        # Try pattern matching with both label and key
        for pattern, suggestions in self.field_patterns.items():
            if re.search(pattern, label_lower) or re.search(pattern, key_lower):
                # Return first matching suggestion
                for suggestion in suggestions:
                    if suggestion in self.db_paths:
                        return suggestion
        
        # Try exact field name matching
        for db_path in self.db_paths:
            path_parts = db_path.split('.')
            field_name = path_parts[-1].lower()
            
            # Check both label and key
            if field_name in label_lower.replace(' ', '').lower() or field_name in key_lower:
                return db_path
        
        return None
    
    def generate_typescript(self) -> str:
        """Generate TypeScript export"""
        form_name = st.session_state.form_info.get('form_number', 'Form').replace('-', '')
        
        # Group fields
        sections = {
            'customerData': {},
            'beneficiaryData': {},
            'attorneyData': {},
            'questionnaireData': {},
            'caseData': {},
            'defaultData': {},
            'conditionalData': {}
        }
        
        # Track used keys to avoid duplicates
        used_keys = set()
        
        for field in st.session_state.fields:
            if field.is_mapped and field.db_mapping:
                # Determine section
                if field.db_mapping.startswith('customer.'):
                    section = 'customerData'
                elif field.db_mapping.startswith('beneficiary.'):
                    section = 'beneficiaryData'
                elif field.db_mapping.startswith('attorney.') or field.db_mapping.startswith('attorneyLawfirmDetails.'):
                    section = 'attorneyData'
                elif field.db_mapping.startswith('case.'):
                    section = 'caseData'
                else:
                    continue
                
                # Add field
                suffix = self._get_ts_suffix(field.field_type)
                sections[section][field.field_key] = f"{field.db_mapping}{suffix}"
            
            elif field.to_questionnaire:
                # Use question_key if available and unique
                key = field.question_key if field.question_key else field.field_key
                
                # Ensure unique key
                base_key = key
                counter = 1
                while key in used_keys:
                    key = f"{base_key}_{counter}"
                    counter += 1
                
                used_keys.add(key)
                sections['questionnaireData'][key] = f"{field.field_key}:ConditionBox"
        
        # Generate TypeScript
        ts = f'export const {form_name} = {{\n'
        ts += f'    "formname": "{form_name}",\n'
        
        # Add sections
        for section_name, fields in sections.items():
            if section_name == 'conditionalData':
                continue  # Handle separately
            
            if fields:
                ts += f'    "{section_name}": {{\n'
                field_entries = []
                for key, value in fields.items():
                    field_entries.append(f'        "{key}": "{value}"')
                ts += ',\n'.join(field_entries)
                ts += '\n    },\n'
            else:
                ts += f'    "{section_name}": null,\n'
        
        # Add conditional data (empty for now)
        ts += '    "conditionalData": {},\n'
        
        # Add PDF name
        ts += f'    "pdfName": "{st.session_state.form_info.get("form_number", "Unknown")}"\n'
        ts += '};\n\n'
        ts += f'export default {form_name};'
        
        return ts
    
    def _get_ts_suffix(self, field_type: str) -> str:
        """Get TypeScript suffix for field type"""
        suffix_map = {
            'text': ':TextBox',
            'checkbox': ':CheckBox',
            'radio': ':RadioBox',
            'dropdown': ':DropdownBox',
            'signature': ':SignatureBox',
            'date': ':Date',
            'button': ':ButtonBox'
        }
        return suffix_map.get(field_type, ':TextBox')
    
    def generate_json(self) -> str:
        """Generate JSON export for questionnaire"""
        controls = []
        
        # Add fields by part
        for part_name, fields in st.session_state.fields_by_part.items():
            # Get part info
            part_info = st.session_state.part_structure.get(part_name, {})
            
            # Get questionnaire fields
            quest_fields = [f for f in fields if f.to_questionnaire]
            
            if quest_fields:
                # Add part title
                title_text = f"{part_name}"
                if part_info.get('title'):
                    title_text += f": {part_info['title']}"
                
                controls.append({
                    "name": f"{part_name.lower().replace(' ', '_')}_title",
                    "label": title_text,
                    "type": "title",
                    "validators": {},
                    "style": {"col": "12"}
                })
                
                # Track used names to avoid duplicates
                used_names = set()
                
                # Add fields
                for idx, field in enumerate(quest_fields):
                    # Use question_key if available and unique, otherwise generate unique name
                    if field.question_key and field.question_key not in used_names:
                        control_name = field.question_key
                    else:
                        # Generate unique name
                        base_name = field.field_key
                        counter = 1
                        control_name = base_name
                        while control_name in used_names:
                            control_name = f"{base_name}_{counter}"
                            counter += 1
                    
                    used_names.add(control_name)
                    
                    control = {
                        "name": control_name,
                        "label": field.field_label if not field.item_number else f"{field.item_number}. {field.field_label}",
                        "type": "colorSwitch" if field.field_type in ["checkbox", "radio"] else field.field_type,
                        "validators": {}
                    }
                    
                    # Add field-specific properties
                    if field.field_type == "text":
                        control["style"] = {"col": "7"}
                    elif field.field_type in ["checkbox", "radio"]:
                        control["style"] = {"col": "12"}
                        if field.field_type == "radio":
                            control["id"] = control_name
                            control["value"] = "1"
                    
                    controls.append(control)
        
        return json.dumps({"controls": controls}, indent=2)

def render_mapping_interface(extractor: FieldExtractor):
    """Render the enhanced field mapping interface organized by parts"""
    st.markdown("## 🎯 Field Mapping by Parts")
    
    # Top controls
    with st.container():
        st.markdown('<div class="part-selector">', unsafe_allow_html=True)
        
        col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
        
        with col1:
            # Part selector
            part_options = ['All Parts'] + list(st.session_state.fields_by_part.keys())
            selected_part = st.selectbox(
                "📑 Select Part",
                part_options,
                index=part_options.index(st.session_state.selected_part) if st.session_state.selected_part in part_options else 0,
                key="part_selector"
            )
            st.session_state.selected_part = selected_part
        
        with col2:
            # Mapping filter
            mapping_filter = st.selectbox(
                "🔍 Filter by Status",
                ["All Fields", "Mapped", "Unmapped", "Questionnaire"],
                key="mapping_filter_select"
            )
            st.session_state.mapping_filter = mapping_filter.lower().replace(' fields', '').replace(' ', '_')
        
        with col3:
            # Database browser toggle
            st.session_state.show_db_browser = st.checkbox(
                "🗂️ Show DB Browser",
                value=st.session_state.show_db_browser,
                help="Show database structure browser"
            )
        
        with col4:
            # Field count
            if selected_part == 'All Parts':
                total_fields = len(st.session_state.fields)
            else:
                total_fields = len(st.session_state.fields_by_part.get(selected_part, []))
            
            mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
            st.metric("Progress", f"{mapped}/{total_fields}", f"{mapped/total_fields*100:.0f}%")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Quick actions
    st.markdown("### ⚡ Quick Actions")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🤖 Auto-Map Current View", use_container_width=True):
            fields_to_map = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_map = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            mapped_count = 0
            for field in fields_to_map:
                if not field.is_mapped and not field.to_questionnaire and field.field_type == 'text':
                    suggestion = extractor.suggest_mapping(field)
                    if suggestion:
                        field.db_mapping = suggestion
                        field.is_mapped = True
                        mapped_count += 1
            st.success(f"Auto-mapped {mapped_count} fields!")
            st.rerun()
    
    with col2:
        if st.button("📋 All Checkboxes → Quest", use_container_width=True):
            fields_to_move = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_move = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            count = 0
            for field in fields_to_move:
                if field.field_type in ['checkbox', 'radio'] and not field.to_questionnaire:
                    field.to_questionnaire = True
                    field.is_mapped = False
                    count += 1
            st.success(f"Moved {count} fields to questionnaire!")
            st.rerun()
    
    with col3:
        if st.button("🔄 Reset Current View", use_container_width=True):
            fields_to_reset = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_reset = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            for field in fields_to_reset:
                field.is_mapped = False
                field.db_mapping = None
                field.to_questionnaire = field.field_type in ['checkbox', 'radio', 'button']
            st.success("Reset complete!")
            st.rerun()
    
    with col4:
        unmapped = sum(1 for f in st.session_state.fields if not f.is_mapped and not f.to_questionnaire)
        if st.button(f"📋 All Unmapped → Quest ({unmapped})", use_container_width=True):
            fields_to_move = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_move = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            count = 0
            for field in fields_to_move:
                if not field.is_mapped and not field.to_questionnaire:
                    field.to_questionnaire = True
                    count += 1
            st.success(f"Moved {count} fields to questionnaire!")
            st.rerun()
    
    # Database object browser
    if st.session_state.show_db_browser:
        with st.expander("🗂️ Database Structure Browser", expanded=True):
            st.markdown("### Available Database Paths")
            st.caption("Click any path to copy it")
            
            # Create tabs for each main object
            tabs = st.tabs(list(DB_OBJECTS.keys()))
            
            for i, (obj_name, tab) in enumerate(zip(DB_OBJECTS.keys(), tabs)):
                with tab:
                    for sub_obj, fields in DB_OBJECTS[obj_name].items():
                        if sub_obj:
                            st.markdown(f"**{sub_obj}:**")
                        
                        # Display fields in columns
                        field_cols = st.columns(3)
                        for j, field in enumerate(fields):
                            col_idx = j % 3
                            with field_cols[col_idx]:
                                if sub_obj:
                                    path = f"{obj_name}.{sub_obj}.{field}"
                                else:
                                    path = f"{obj_name}.{field}"
                                
                                if st.button(f"📋 {field}", key=f"copy_{path}", use_container_width=True):
                                    st.code(path, language="text")
    
    # Field mapping interface organized by parts
    st.markdown("### 📝 Field Mappings by Part")
    
    # Get parts to display
    if st.session_state.selected_part == 'All Parts':
        parts_to_show = st.session_state.fields_by_part.items()
    else:
        parts_to_show = [(st.session_state.selected_part, 
                         st.session_state.fields_by_part.get(st.session_state.selected_part, []))]
    
    # Display each part
    for part_name, fields in parts_to_show:
        # Filter fields based on mapping filter
        if st.session_state.mapping_filter == 'mapped':
            display_fields = [f for f in fields if f.is_mapped]
        elif st.session_state.mapping_filter == 'unmapped':
            display_fields = [f for f in fields if not f.is_mapped and not f.to_questionnaire]
        elif st.session_state.mapping_filter == 'questionnaire':
            display_fields = [f for f in fields if f.to_questionnaire]
        else:
            display_fields = fields
        
        if not display_fields:
            continue
        
        # Get part info
        part_info = st.session_state.part_structure.get(part_name, {})
        
        # Part header with stats
        part_mapped = sum(1 for f in fields if f.is_mapped)
        part_quest = sum(1 for f in fields if f.to_questionnaire)
        part_unmapped = len(fields) - part_mapped - part_quest
        
        with st.container():
            st.markdown(f'''
            <div class="part-header">
                <strong>{part_name}</strong> {part_info.get('title', '')} 
                <br>
                <small>Total: {len(fields)} | Mapped: {part_mapped} | Questionnaire: {part_quest} | Unmapped: {part_unmapped}</small>
                <br>
                <small>Pages: {', '.join(map(str, part_info.get('pages', [])))}</small>
            </div>
            ''', unsafe_allow_html=True)
        
        # Display fields for this part
        for idx, field in enumerate(display_fields):
            with st.container():
                st.markdown('<div class="mapping-row">', unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    # Field info
                    display_label = field.field_label
                    if field.item_number:
                        display_label = f"{field.item_number}. {display_label}"
                    
                    st.markdown(f'<div class="field-label">{display_label}</div>', unsafe_allow_html=True)
                    
                    # Build field metadata
                    type_class = f"field-type {field.field_type}"
                    meta_parts = [
                        f'<span class="{type_class}">{field.field_type.upper()}</span>',
                        f'Field: {field.field_key}',
                        f'Page {field.page}'
                    ]
                    
                    # Only show quest key if it's different from field key
                    if field.to_questionnaire and field.question_key and field.question_key != field.field_key:
                        quest_key_short = field.question_key.split('_')[-1] if '_' in field.question_key else field.question_key
                        meta_parts.append(f'Quest: {quest_key_short}')
                    
                    st.markdown(f"""
                    <div class="field-meta">
                        {' • '.join(meta_parts)}
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    # Create unique key for this field
                    unique_key = f"{part_name}_{field.field_id}_{idx}"
                    
                    col2a, col2b = st.columns([3, 1])
                    
                    with col2a:
                        # Database mapping dropdown
                        grouped_options = {
                            "Actions": ["-- Select Database Field --", "📋 Move to Questionnaire"],
                            "beneficiary": [],
                            "petitioner": [],
                            "customer": [],
                            "attorney": [],
                            "attorneyLawfirmDetails": [],
                            "case": [],
                            "employment": []
                        }
                        
                        # Group database paths
                        for path in extractor.db_paths:
                            obj_name = path.split('.')[0]
                            if obj_name in grouped_options:
                                grouped_options[obj_name].append(path)
                        
                        # Build flat list with separators
                        options = []
                        for group, items in grouped_options.items():
                            if items:
                                if options:  # Add separator between groups
                                    options.append(f"── {group} ──")
                                options.extend(items)
                        
                        # Current selection
                        if field.is_mapped and field.db_mapping:
                            current_value = field.db_mapping
                        elif field.to_questionnaire:
                            current_value = "📋 Move to Questionnaire"
                        else:
                            # Try to get suggestion
                            suggestion = extractor.suggest_mapping(field)
                            current_value = suggestion if suggestion else "-- Select Database Field --"
                        
                        # Find index
                        try:
                            current_index = options.index(current_value)
                        except ValueError:
                            current_index = 0
                        
                        selected = st.selectbox(
                            "Database Mapping",
                            options,
                            index=current_index,
                            key=f"map_{unique_key}",
                            label_visibility="collapsed"
                        )
                        
                        # Handle selection
                        if selected != current_value and not selected.startswith("──"):
                            if selected == "📋 Move to Questionnaire":
                                field.to_questionnaire = True
                                field.is_mapped = False
                                field.db_mapping = None
                            elif selected != "-- Select Database Field --":
                                field.db_mapping = selected
                                field.is_mapped = True
                                field.to_questionnaire = False
                            st.rerun()
                    
                    with col2b:
                        # Quick questionnaire toggle
                        if st.button("📋", key=f"quest_btn_{unique_key}", 
                                   help="Quick add to questionnaire",
                                   use_container_width=True):
                            field.to_questionnaire = True
                            field.is_mapped = False
                            field.db_mapping = None
                            st.rerun()
                
                with col3:
                    # Status
                    status = field.get_status()
                    if "Mapped" in status:
                        badge_class = "status-mapped"
                    elif "Questionnaire" in status:
                        badge_class = "status-questionnaire"
                    else:
                        badge_class = "status-unmapped"
                    
                    st.markdown(f'<span class="status-badge {badge_class}">{status}</span>', 
                              unsafe_allow_html=True)
                
                st.markdown('</div>', unsafe_allow_html=True)
        
        # Add spacing between parts
        st.markdown("<br>", unsafe_allow_html=True)

def main():
    """Main application"""
    st.markdown("# 🤖 USCIS Form Reader Pro")
    st.markdown("### Complete PDF Form Field Extraction & Mapping Solution")
    
    # Initialize extractor
    extractor = FieldExtractor()
    
    # Sidebar
    with st.sidebar:
        st.markdown("## ⚙️ Settings")
        st.session_state.debug_mode = st.checkbox("Debug Mode", value=False)
        
        if st.session_state.pdf_processed:
            st.markdown("---")
            st.markdown("### 📊 Statistics")
            stats = st.session_state.extraction_stats
            st.metric("Total Pages", stats.get('total_pages', 0))
            st.metric("Total Parts", stats.get('total_parts', 0))
            st.metric("Total Fields", stats.get('total_fields', 0))
            st.metric("Extraction Time", f"{stats.get('extraction_time', 0):.2f}s")
            
            if stats.get('errors'):
                st.warning(f"{len(stats['errors'])} errors occurred")
                with st.expander("View Errors"):
                    for error in stats['errors']:
                        st.text(error)
            
            # Field summary
            total = len(st.session_state.fields)
            mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
            quest = sum(1 for f in st.session_state.fields if f.to_questionnaire)
            
            st.markdown("---")
            st.markdown("### 📈 Mapping Progress")
            st.metric("Mapped to DB", f"{mapped} ({mapped/total*100:.1f}%)")
            st.metric("In Questionnaire", f"{quest} ({quest/total*100:.1f}%)")
            st.metric("Unmapped", f"{total - mapped - quest}")
            
            # Progress bar
            progress = (mapped + quest) / total if total > 0 else 0
            st.progress(progress)
            
            # Part breakdown
            st.markdown("---")
            st.markdown("### 📑 Parts Overview")
            for part_name, part_info in st.session_state.part_structure.items():
                fields = st.session_state.fields_by_part.get(part_name, [])
                mapped = sum(1 for f in fields if f.is_mapped)
                quest = sum(1 for f in fields if f.to_questionnaire)
                st.caption(f"{part_name}: {len(fields)} fields ({mapped} mapped, {quest} quest)")
    
    # Main tabs
    tab1, tab2, tab3 = st.tabs(["📤 Upload & Extract", "🎯 Map Fields", "📥 Export & Download"])
    
    with tab1:
        st.markdown("## Upload USCIS PDF Form")
        
        uploaded_file = st.file_uploader(
            "Choose a USCIS PDF form",
            type=['pdf'],
            help="Upload any fillable USCIS form (I-90, I-129, G-28, etc.)",
            key="pdf_uploader"
        )
        
        if uploaded_file:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                if st.button("🚀 Extract Fields by Parts", type="primary", use_container_width=True):
                    with st.spinner("Analyzing PDF structure and extracting fields by parts..."):
                        if extractor.extract_from_pdf(uploaded_file):
                            st.success(f"""
                            ✅ Successfully extracted {len(st.session_state.fields)} fields from {st.session_state.form_info.get('form_number', 'form')}!
                            
                            Found {len(st.session_state.fields_by_part)} parts with fields.
                            """)
                            
                            # Show extraction summary
                            with st.expander("📊 Extraction Summary", expanded=True):
                                for part_name, fields in st.session_state.fields_by_part.items():
                                    part_info = st.session_state.part_structure.get(part_name, {})
                                    
                                    st.write(f"**{part_name}** {part_info.get('title', '')}")
                                    st.write(f"- Fields: {len(fields)}")
                                    st.write(f"- Pages: {', '.join(map(str, part_info.get('pages', [])))}")
                                    
                                    # Field type breakdown
                                    types = defaultdict(int)
                                    for field in fields:
                                        types[field.field_type] += 1
                                    
                                    type_summary = ", ".join([f"{count} {ftype}" for ftype, count in types.items()])
                                    st.caption(f"Field types: {type_summary}")
                                    st.divider()
            
            with col2:
                if st.session_state.pdf_processed:
                    if st.button("🔄 Reset", type="secondary", use_container_width=True):
                        # Clear all session state
                        for key in list(st.session_state.keys()):
                            if key != 'debug_mode':
                                del st.session_state[key]
                        extractor.init_session_state()
                        st.rerun()
    
    with tab2:
        if not st.session_state.pdf_processed:
            st.info("👆 Please upload and extract a PDF form first.")
        else:
            render_mapping_interface(extractor)
    
    with tab3:
        if not st.session_state.pdf_processed:
            st.info("👆 Please upload and extract a PDF form first.")
        else:
            st.markdown("## 📥 Export & Download")
            
            # Summary
            total = len(st.session_state.fields)
            mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
            quest = sum(1 for f in st.session_state.fields if f.to_questionnaire)
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Fields", total)
            col2.metric("Mapped to Database", mapped)
            col3.metric("In Questionnaire", quest)
            
            st.markdown("---")
            
            # Export options
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 📄 TypeScript Export")
                st.markdown("Database mappings for your application")
                
                ts_code = extractor.generate_typescript()
                
                st.download_button(
                    label="⬇️ Download TypeScript File",
                    data=ts_code,
                    file_name=f"{st.session_state.form_info.get('form_number', 'form')}.ts",
                    mime="text/typescript",
                    use_container_width=True
                )
                
                with st.expander("Preview TypeScript"):
                    st.code(ts_code, language="typescript")
            
            with col2:
                st.markdown("### 📋 JSON Export")
                st.markdown("Questionnaire configuration")
                
                json_code = extractor.generate_json()
                
                st.download_button(
                    label="⬇️ Download JSON File",
                    data=json_code,
                    file_name=f"{st.session_state.form_info.get('form_number', 'form')}-questionnaire.json",
                    mime="application/json",
                    use_container_width=True
                )
                
                with st.expander("Preview JSON"):
                    st.code(json_code, language="json")
            
            # Combined export
            st.markdown("---")
            if st.button("📦 Download Both Files", type="primary", use_container_width=True):
                st.markdown("### Downloads Ready:")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button(
                        "TypeScript (.ts)",
                        extractor.generate_typescript(),
                        f"{st.session_state.form_info.get('form_number', 'form')}.ts",
                        mime="text/typescript"
                    )
                with col2:
                    st.download_button(
                        "JSON (.json)",
                        extractor.generate_json(),
                        f"{st.session_state.form_info.get('form_number', 'form')}-questionnaire.json",
                        mime="application/json"
                    )

if __name__ == "__main__":
    main()
, '', key)
        key = re.sub(r'_+
    
    def _generate_field_label(self, name: str) -> str:
        """Generate human-readable label"""
        # Common label mappings
        label_map = {
            'familyname': 'Family Name (Last Name)',
            'lastname': 'Last Name',
            'givenname': 'Given Name (First Name)', 
            'firstname': 'First Name',
            'middlename': 'Middle Name',
            'anumber': 'Alien Registration Number (A-Number)',
            'uscisaccount': 'USCIS Online Account Number',
            'dateofbirth': 'Date of Birth',
            'ssn': 'Social Security Number',
            'email': 'Email Address',
            'phone': 'Phone Number',
            'daytimephone': 'Daytime Phone Number',
            'mobile': 'Mobile Phone Number',
            'street': 'Street Address',
            'city': 'City or Town',
            'state': 'State',
            'zip': 'ZIP Code',
            'country': 'Country',
            'barnumber': 'Bar Number',
            'statebarnumber': 'State Bar Number',
            'lawfirm': 'Law Firm Name',
            'lawfirmname': 'Law Firm Name',
            'licensingauthority': 'Licensing Authority',
            'workphone': 'Work Phone Number',
            'faxnumber': 'Fax Number'
        }
        
        # Check for exact match
        name_lower = name.lower().replace('_', '').replace('-', '').replace(' ', '')
        for key, label in label_map.items():
            if key in name_lower or name_lower in key:
                return label
        
        # Convert to title case
        label = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
        label = label.replace('_', ' ').replace('-', ' ')
        label = ' '.join(label.split())
        label = label.title()
        
        return label
    
    def _map_widget_type(self, widget_type: int) -> str:
        """Map PDF widget type to field type"""
        type_map = {
            1: "button",
            2: "checkbox",
            3: "radio",
            4: "text",
            5: "dropdown",
            6: "list",
            7: "signature"
        }
        return type_map.get(widget_type, "text")
    
    def suggest_mapping(self, field: PDFField) -> Optional[str]:
        """Suggest database mapping for field"""
        label_lower = field.field_label.lower()
        key_lower = field.field_key.lower()
        
        # Try pattern matching with both label and key
        for pattern, suggestions in self.field_patterns.items():
            if re.search(pattern, label_lower) or re.search(pattern, key_lower):
                # Return first matching suggestion
                for suggestion in suggestions:
                    if suggestion in self.db_paths:
                        return suggestion
        
        # Try exact field name matching
        for db_path in self.db_paths:
            path_parts = db_path.split('.')
            field_name = path_parts[-1].lower()
            
            # Check both label and key
            if field_name in label_lower.replace(' ', '').lower() or field_name in key_lower:
                return db_path
        
        return None
    
    def generate_typescript(self) -> str:
        """Generate TypeScript export"""
        form_name = st.session_state.form_info.get('form_number', 'Form').replace('-', '')
        
        # Group fields
        sections = {
            'customerData': {},
            'beneficiaryData': {},
            'attorneyData': {},
            'questionnaireData': {},
            'caseData': {},
            'defaultData': {},
            'conditionalData': {}
        }
        
        for field in st.session_state.fields:
            if field.is_mapped and field.db_mapping:
                # Determine section
                if field.db_mapping.startswith('customer.'):
                    section = 'customerData'
                elif field.db_mapping.startswith('beneficiary.'):
                    section = 'beneficiaryData'
                elif field.db_mapping.startswith('attorney.') or field.db_mapping.startswith('attorneyLawfirmDetails.'):
                    section = 'attorneyData'
                elif field.db_mapping.startswith('case.'):
                    section = 'caseData'
                else:
                    continue
                
                # Add field
                suffix = self._get_ts_suffix(field.field_type)
                sections[section][field.field_key] = f"{field.db_mapping}{suffix}"
            
            elif field.to_questionnaire:
                # Use question_key for questionnaire items
                key = field.question_key if field.question_key else field.field_key
                sections['questionnaireData'][key] = f"{field.field_key}:ConditionBox"
        
        # Generate TypeScript
        ts = f'export const {form_name} = {{\n'
        ts += f'    "formname": "{form_name}",\n'
        
        # Add sections
        for section_name, fields in sections.items():
            if section_name == 'conditionalData':
                continue  # Handle separately
            
            if fields:
                ts += f'    "{section_name}": {{\n'
                field_entries = []
                for key, value in fields.items():
                    field_entries.append(f'        "{key}": "{value}"')
                ts += ',\n'.join(field_entries)
                ts += '\n    },\n'
            else:
                ts += f'    "{section_name}": null,\n'
        
        # Add conditional data (empty for now)
        ts += '    "conditionalData": {},\n'
        
        # Add PDF name
        ts += f'    "pdfName": "{st.session_state.form_info.get("form_number", "Unknown")}"\n'
        ts += '};\n\n'
        ts += f'export default {form_name};'
        
        return ts
    
    def _get_ts_suffix(self, field_type: str) -> str:
        """Get TypeScript suffix for field type"""
        suffix_map = {
            'text': ':TextBox',
            'checkbox': ':CheckBox',
            'radio': ':RadioBox',
            'dropdown': ':DropdownBox',
            'signature': ':SignatureBox',
            'date': ':Date',
            'button': ':ButtonBox'
        }
        return suffix_map.get(field_type, ':TextBox')
    
    def generate_json(self) -> str:
        """Generate JSON export for questionnaire"""
        controls = []
        
        # Add fields by part
        for part_name, fields in st.session_state.fields_by_part.items():
            # Get part info
            part_info = st.session_state.part_structure.get(part_name, {})
            
            # Get questionnaire fields
            quest_fields = [f for f in fields if f.to_questionnaire]
            
            if quest_fields:
                # Add part title
                title_text = f"{part_name}"
                if part_info.get('title'):
                    title_text += f": {part_info['title']}"
                
                controls.append({
                    "name": f"{part_name.lower().replace(' ', '_')}_title",
                    "label": title_text,
                    "type": "title",
                    "validators": {},
                    "style": {"col": "12"}
                })
                
                # Add fields
                for field in quest_fields:
                    control = {
                        "name": field.field_key,
                        "label": field.field_label,
                        "type": "colorSwitch" if field.field_type in ["checkbox", "radio"] else field.field_type,
                        "validators": {}
                    }
                    
                    # Add field-specific properties
                    if field.field_type == "text":
                        control["style"] = {"col": "7"}
                    elif field.field_type in ["checkbox", "radio"]:
                        control["style"] = {"col": "12"}
                        if field.field_type == "radio":
                            control["id"] = field.field_key
                            control["value"] = "1"
                    
                    controls.append(control)
        
        return json.dumps({"controls": controls}, indent=2)

def render_mapping_interface(extractor: FieldExtractor):
    """Render the enhanced field mapping interface organized by parts"""
    st.markdown("## 🎯 Field Mapping by Parts")
    
    # Top controls
    with st.container():
        st.markdown('<div class="part-selector">', unsafe_allow_html=True)
        
        col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
        
        with col1:
            # Part selector
            part_options = ['All Parts'] + list(st.session_state.fields_by_part.keys())
            selected_part = st.selectbox(
                "📑 Select Part",
                part_options,
                index=part_options.index(st.session_state.selected_part) if st.session_state.selected_part in part_options else 0,
                key="part_selector"
            )
            st.session_state.selected_part = selected_part
        
        with col2:
            # Mapping filter
            mapping_filter = st.selectbox(
                "🔍 Filter by Status",
                ["All Fields", "Mapped", "Unmapped", "Questionnaire"],
                key="mapping_filter_select"
            )
            st.session_state.mapping_filter = mapping_filter.lower().replace(' fields', '').replace(' ', '_')
        
        with col3:
            # Database browser toggle
            st.session_state.show_db_browser = st.checkbox(
                "🗂️ Show DB Browser",
                value=st.session_state.show_db_browser,
                help="Show database structure browser"
            )
        
        with col4:
            # Field count
            if selected_part == 'All Parts':
                total_fields = len(st.session_state.fields)
            else:
                total_fields = len(st.session_state.fields_by_part.get(selected_part, []))
            
            mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
            st.metric("Progress", f"{mapped}/{total_fields}", f"{mapped/total_fields*100:.0f}%")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Quick actions
    st.markdown("### ⚡ Quick Actions")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🤖 Auto-Map Current View", use_container_width=True):
            fields_to_map = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_map = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            mapped_count = 0
            for field in fields_to_map:
                if not field.is_mapped and not field.to_questionnaire and field.field_type == 'text':
                    suggestion = extractor.suggest_mapping(field)
                    if suggestion:
                        field.db_mapping = suggestion
                        field.is_mapped = True
                        mapped_count += 1
            st.success(f"Auto-mapped {mapped_count} fields!")
            st.rerun()
    
    with col2:
        if st.button("📋 All Checkboxes → Quest", use_container_width=True):
            fields_to_move = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_move = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            count = 0
            for field in fields_to_move:
                if field.field_type in ['checkbox', 'radio'] and not field.to_questionnaire:
                    field.to_questionnaire = True
                    field.is_mapped = False
                    count += 1
            st.success(f"Moved {count} fields to questionnaire!")
            st.rerun()
    
    with col3:
        if st.button("🔄 Reset Current View", use_container_width=True):
            fields_to_reset = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_reset = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            for field in fields_to_reset:
                field.is_mapped = False
                field.db_mapping = None
                field.to_questionnaire = field.field_type in ['checkbox', 'radio', 'button']
            st.success("Reset complete!")
            st.rerun()
    
    with col4:
        unmapped = sum(1 for f in st.session_state.fields if not f.is_mapped and not f.to_questionnaire)
        if st.button(f"📋 All Unmapped → Quest ({unmapped})", use_container_width=True):
            fields_to_move = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_move = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            count = 0
            for field in fields_to_move:
                if not field.is_mapped and not field.to_questionnaire:
                    field.to_questionnaire = True
                    count += 1
            st.success(f"Moved {count} fields to questionnaire!")
            st.rerun()
    
    # Database object browser
    if st.session_state.show_db_browser:
        with st.expander("🗂️ Database Structure Browser", expanded=True):
            st.markdown("### Available Database Paths")
            st.caption("Click any path to copy it")
            
            # Create tabs for each main object
            tabs = st.tabs(list(DB_OBJECTS.keys()))
            
            for i, (obj_name, tab) in enumerate(zip(DB_OBJECTS.keys(), tabs)):
                with tab:
                    for sub_obj, fields in DB_OBJECTS[obj_name].items():
                        if sub_obj:
                            st.markdown(f"**{sub_obj}:**")
                        
                        # Display fields in columns
                        field_cols = st.columns(3)
                        for j, field in enumerate(fields):
                            col_idx = j % 3
                            with field_cols[col_idx]:
                                if sub_obj:
                                    path = f"{obj_name}.{sub_obj}.{field}"
                                else:
                                    path = f"{obj_name}.{field}"
                                
                                if st.button(f"📋 {field}", key=f"copy_{path}", use_container_width=True):
                                    st.code(path, language="text")
    
    # Field mapping interface organized by parts
    st.markdown("### 📝 Field Mappings by Part")
    
    # Get parts to display
    if st.session_state.selected_part == 'All Parts':
        parts_to_show = st.session_state.fields_by_part.items()
    else:
        parts_to_show = [(st.session_state.selected_part, 
                         st.session_state.fields_by_part.get(st.session_state.selected_part, []))]
    
    # Display each part
    for part_name, fields in parts_to_show:
        # Filter fields based on mapping filter
        if st.session_state.mapping_filter == 'mapped':
            display_fields = [f for f in fields if f.is_mapped]
        elif st.session_state.mapping_filter == 'unmapped':
            display_fields = [f for f in fields if not f.is_mapped and not f.to_questionnaire]
        elif st.session_state.mapping_filter == 'questionnaire':
            display_fields = [f for f in fields if f.to_questionnaire]
        else:
            display_fields = fields
        
        if not display_fields:
            continue
        
        # Get part info
        part_info = st.session_state.part_structure.get(part_name, {})
        
        # Part header with stats
        part_mapped = sum(1 for f in fields if f.is_mapped)
        part_quest = sum(1 for f in fields if f.to_questionnaire)
        part_unmapped = len(fields) - part_mapped - part_quest
        
        with st.container():
            st.markdown(f'''
            <div class="part-header">
                <strong>{part_name}</strong> {part_info.get('title', '')} 
                <br>
                <small>Total: {len(fields)} | Mapped: {part_mapped} | Questionnaire: {part_quest} | Unmapped: {part_unmapped}</small>
                <br>
                <small>Pages: {', '.join(map(str, part_info.get('pages', [])))}</small>
            </div>
            ''', unsafe_allow_html=True)
        
        # Display fields for this part
        for idx, field in enumerate(display_fields):
            with st.container():
                st.markdown('<div class="mapping-row">', unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    # Field info
                    display_label = field.field_label
                    if field.item_number:
                        display_label = f"{field.item_number}. {display_label}"
                    
                    st.markdown(f'<div class="field-label">{display_label}</div>', unsafe_allow_html=True)
                    
                    # Build field metadata
                    meta_parts = [
                        f'<span class="field-type">{field.field_type}</span>',
                        f'Field: {field.field_key}',
                        f'Page {field.page}'
                    ]
                    
                    # Only show quest key if it's different from field key
                    if field.to_questionnaire and field.question_key and field.question_key != field.field_key:
                        meta_parts.append(f'Quest: {field.question_key}')
                    
                    st.markdown(f"""
                    <div class="field-meta">
                        {' • '.join(meta_parts)}
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    # Create unique key for this field
                    unique_key = f"{part_name}_{field.field_id}_{idx}"
                    
                    col2a, col2b = st.columns([3, 1])
                    
                    with col2a:
                        # Database mapping dropdown
                        grouped_options = {
                            "Actions": ["-- Select Database Field --", "📋 Move to Questionnaire"],
                            "beneficiary": [],
                            "petitioner": [],
                            "customer": [],
                            "attorney": [],
                            "attorneyLawfirmDetails": [],
                            "case": [],
                            "employment": []
                        }
                        
                        # Group database paths
                        for path in extractor.db_paths:
                            obj_name = path.split('.')[0]
                            if obj_name in grouped_options:
                                grouped_options[obj_name].append(path)
                        
                        # Build flat list with separators
                        options = []
                        for group, items in grouped_options.items():
                            if items:
                                if options:  # Add separator between groups
                                    options.append(f"── {group} ──")
                                options.extend(items)
                        
                        # Current selection
                        if field.is_mapped and field.db_mapping:
                            current_value = field.db_mapping
                        elif field.to_questionnaire:
                            current_value = "📋 Move to Questionnaire"
                        else:
                            # Try to get suggestion
                            suggestion = extractor.suggest_mapping(field)
                            current_value = suggestion if suggestion else "-- Select Database Field --"
                        
                        # Find index
                        try:
                            current_index = options.index(current_value)
                        except ValueError:
                            current_index = 0
                        
                        selected = st.selectbox(
                            "Database Mapping",
                            options,
                            index=current_index,
                            key=f"map_{unique_key}",
                            label_visibility="collapsed"
                        )
                        
                        # Handle selection
                        if selected != current_value and not selected.startswith("──"):
                            if selected == "📋 Move to Questionnaire":
                                field.to_questionnaire = True
                                field.is_mapped = False
                                field.db_mapping = None
                            elif selected != "-- Select Database Field --":
                                field.db_mapping = selected
                                field.is_mapped = True
                                field.to_questionnaire = False
                            st.rerun()
                    
                    with col2b:
                        # Quick questionnaire toggle
                        if st.button("📋", key=f"quest_btn_{unique_key}", 
                                   help="Quick add to questionnaire",
                                   use_container_width=True):
                            field.to_questionnaire = True
                            field.is_mapped = False
                            field.db_mapping = None
                            st.rerun()
                
                with col3:
                    # Status
                    status = field.get_status()
                    if "Mapped" in status:
                        badge_class = "status-mapped"
                    elif "Questionnaire" in status:
                        badge_class = "status-questionnaire"
                    else:
                        badge_class = "status-unmapped"
                    
                    st.markdown(f'<span class="status-badge {badge_class}">{status}</span>', 
                              unsafe_allow_html=True)
                
                st.markdown('</div>', unsafe_allow_html=True)
        
        # Add spacing between parts
        st.markdown("<br>", unsafe_allow_html=True)

def main():
    """Main application"""
    st.markdown("# 🤖 USCIS Form Reader Pro")
    st.markdown("### Complete PDF Form Field Extraction & Mapping Solution")
    
    # Initialize extractor
    extractor = FieldExtractor()
    
    # Sidebar
    with st.sidebar:
        st.markdown("## ⚙️ Settings")
        st.session_state.debug_mode = st.checkbox("Debug Mode", value=False)
        
        if st.session_state.pdf_processed:
            st.markdown("---")
            st.markdown("### 📊 Statistics")
            stats = st.session_state.extraction_stats
            st.metric("Total Pages", stats.get('total_pages', 0))
            st.metric("Total Parts", stats.get('total_parts', 0))
            st.metric("Total Fields", stats.get('total_fields', 0))
            st.metric("Extraction Time", f"{stats.get('extraction_time', 0):.2f}s")
            
            if stats.get('errors'):
                st.warning(f"{len(stats['errors'])} errors occurred")
                with st.expander("View Errors"):
                    for error in stats['errors']:
                        st.text(error)
            
            # Field summary
            total = len(st.session_state.fields)
            mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
            quest = sum(1 for f in st.session_state.fields if f.to_questionnaire)
            
            st.markdown("---")
            st.markdown("### 📈 Mapping Progress")
            st.metric("Mapped to DB", f"{mapped} ({mapped/total*100:.1f}%)")
            st.metric("In Questionnaire", f"{quest} ({quest/total*100:.1f}%)")
            st.metric("Unmapped", f"{total - mapped - quest}")
            
            # Progress bar
            progress = (mapped + quest) / total if total > 0 else 0
            st.progress(progress)
            
            # Part breakdown
            st.markdown("---")
            st.markdown("### 📑 Parts Overview")
            for part_name, part_info in st.session_state.part_structure.items():
                fields = st.session_state.fields_by_part.get(part_name, [])
                mapped = sum(1 for f in fields if f.is_mapped)
                quest = sum(1 for f in fields if f.to_questionnaire)
                st.caption(f"{part_name}: {len(fields)} fields ({mapped} mapped, {quest} quest)")
    
    # Main tabs
    tab1, tab2, tab3 = st.tabs(["📤 Upload & Extract", "🎯 Map Fields", "📥 Export & Download"])
    
    with tab1:
        st.markdown("## Upload USCIS PDF Form")
        
        uploaded_file = st.file_uploader(
            "Choose a USCIS PDF form",
            type=['pdf'],
            help="Upload any fillable USCIS form (I-90, I-129, G-28, etc.)",
            key="pdf_uploader"
        )
        
        if uploaded_file:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                if st.button("🚀 Extract Fields by Parts", type="primary", use_container_width=True):
                    with st.spinner("Analyzing PDF structure and extracting fields by parts..."):
                        if extractor.extract_from_pdf(uploaded_file):
                            st.success(f"""
                            ✅ Successfully extracted {len(st.session_state.fields)} fields from {st.session_state.form_info.get('form_number', 'form')}!
                            
                            Found {len(st.session_state.fields_by_part)} parts with fields.
                            """)
                            
                            # Show extraction summary
                            with st.expander("📊 Extraction Summary", expanded=True):
                                for part_name, fields in st.session_state.fields_by_part.items():
                                    part_info = st.session_state.part_structure.get(part_name, {})
                                    
                                    st.write(f"**{part_name}** {part_info.get('title', '')}")
                                    st.write(f"- Fields: {len(fields)}")
                                    st.write(f"- Pages: {', '.join(map(str, part_info.get('pages', [])))}")
                                    
                                    # Field type breakdown
                                    types = defaultdict(int)
                                    for field in fields:
                                        types[field.field_type] += 1
                                    
                                    type_summary = ", ".join([f"{count} {ftype}" for ftype, count in types.items()])
                                    st.caption(f"Field types: {type_summary}")
                                    st.divider()
            
            with col2:
                if st.session_state.pdf_processed:
                    if st.button("🔄 Reset", type="secondary", use_container_width=True):
                        # Clear all session state
                        for key in list(st.session_state.keys()):
                            if key != 'debug_mode':
                                del st.session_state[key]
                        extractor.init_session_state()
                        st.rerun()
    
    with tab2:
        if not st.session_state.pdf_processed:
            st.info("👆 Please upload and extract a PDF form first.")
        else:
            render_mapping_interface(extractor)
    
    with tab3:
        if not st.session_state.pdf_processed:
            st.info("👆 Please upload and extract a PDF form first.")
        else:
            st.markdown("## 📥 Export & Download")
            
            # Summary
            total = len(st.session_state.fields)
            mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
            quest = sum(1 for f in st.session_state.fields if f.to_questionnaire)
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Fields", total)
            col2.metric("Mapped to Database", mapped)
            col3.metric("In Questionnaire", quest)
            
            st.markdown("---")
            
            # Export options
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 📄 TypeScript Export")
                st.markdown("Database mappings for your application")
                
                ts_code = extractor.generate_typescript()
                
                st.download_button(
                    label="⬇️ Download TypeScript File",
                    data=ts_code,
                    file_name=f"{st.session_state.form_info.get('form_number', 'form')}.ts",
                    mime="text/typescript",
                    use_container_width=True
                )
                
                with st.expander("Preview TypeScript"):
                    st.code(ts_code, language="typescript")
            
            with col2:
                st.markdown("### 📋 JSON Export")
                st.markdown("Questionnaire configuration")
                
                json_code = extractor.generate_json()
                
                st.download_button(
                    label="⬇️ Download JSON File",
                    data=json_code,
                    file_name=f"{st.session_state.form_info.get('form_number', 'form')}-questionnaire.json",
                    mime="application/json",
                    use_container_width=True
                )
                
                with st.expander("Preview JSON"):
                    st.code(json_code, language="json")
            
            # Combined export
            st.markdown("---")
            if st.button("📦 Download Both Files", type="primary", use_container_width=True):
                st.markdown("### Downloads Ready:")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button(
                        "TypeScript (.ts)",
                        extractor.generate_typescript(),
                        f"{st.session_state.form_info.get('form_number', 'form')}.ts",
                        mime="text/typescript"
                    )
                with col2:
                    st.download_button(
                        "JSON (.json)",
                        extractor.generate_json(),
                        f"{st.session_state.form_info.get('form_number', 'form')}-questionnaire.json",
                        mime="application/json"
                    )

if __name__ == "__main__":
    main()
, '', key)  # Remove trailing underscores
        
        # Common abbreviations
        abbreviations = {
            'family_name': 'familyName',
            'last_name': 'lastName',
            'given_name': 'givenName',
            'first_name': 'firstName',
            'middle_name': 'middleName',
            'date_of_birth': 'dob',
            'social_security': 'ssn',
            'alien_number': 'aNumber',
            'email_address': 'email',
            'phone_number': 'phone',
            'street_address': 'street',
            'zip_code': 'zip',
            'state_bar_number': 'stateBarNumber',
            'law_firm_name': 'lawFirmName',
            'licensing_authority': 'licensingAuthority'
        }
        
        key_lower = key.lower()
        for pattern, replacement in abbreviations.items():
            if pattern in key_lower:
                return replacement
        
        # Convert to camelCase
        parts = key.split('_')
        if len(parts) > 1:
            key = parts[0].lower() + ''.join(p.capitalize() for p in parts[1:] if p)
        else:
            key = key.lower() if key else 'field'
        
        # Ensure we have a valid key
        if not key or key.isdigit():
            key = 'field'
        
        # Limit length
        if len(key) > 30:
            key = key[:30]
        
        return key
    
    def _generate_field_label(self, name: str) -> str:
        """Generate human-readable label"""
        # Common label mappings
        label_map = {
            'familyname': 'Family Name (Last Name)',
            'lastname': 'Last Name',
            'givenname': 'Given Name (First Name)', 
            'firstname': 'First Name',
            'middlename': 'Middle Name',
            'anumber': 'Alien Registration Number (A-Number)',
            'uscisaccount': 'USCIS Online Account Number',
            'dateofbirth': 'Date of Birth',
            'ssn': 'Social Security Number',
            'email': 'Email Address',
            'phone': 'Phone Number',
            'daytimephone': 'Daytime Phone Number',
            'mobile': 'Mobile Phone Number',
            'street': 'Street Address',
            'city': 'City or Town',
            'state': 'State',
            'zip': 'ZIP Code',
            'country': 'Country',
            'barnumber': 'Bar Number',
            'statebarnumber': 'State Bar Number',
            'lawfirm': 'Law Firm Name',
            'lawfirmname': 'Law Firm Name',
            'licensingauthority': 'Licensing Authority',
            'workphone': 'Work Phone Number',
            'faxnumber': 'Fax Number'
        }
        
        # Check for exact match
        name_lower = name.lower().replace('_', '').replace('-', '').replace(' ', '')
        for key, label in label_map.items():
            if key in name_lower or name_lower in key:
                return label
        
        # Convert to title case
        label = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
        label = label.replace('_', ' ').replace('-', ' ')
        label = ' '.join(label.split())
        label = label.title()
        
        return label
    
    def _map_widget_type(self, widget_type: int) -> str:
        """Map PDF widget type to field type"""
        type_map = {
            1: "button",
            2: "checkbox",
            3: "radio",
            4: "text",
            5: "dropdown",
            6: "list",
            7: "signature"
        }
        return type_map.get(widget_type, "text")
    
    def suggest_mapping(self, field: PDFField) -> Optional[str]:
        """Suggest database mapping for field"""
        label_lower = field.field_label.lower()
        key_lower = field.field_key.lower()
        
        # Try pattern matching with both label and key
        for pattern, suggestions in self.field_patterns.items():
            if re.search(pattern, label_lower) or re.search(pattern, key_lower):
                # Return first matching suggestion
                for suggestion in suggestions:
                    if suggestion in self.db_paths:
                        return suggestion
        
        # Try exact field name matching
        for db_path in self.db_paths:
            path_parts = db_path.split('.')
            field_name = path_parts[-1].lower()
            
            # Check both label and key
            if field_name in label_lower.replace(' ', '').lower() or field_name in key_lower:
                return db_path
        
        return None
    
    def generate_typescript(self) -> str:
        """Generate TypeScript export"""
        form_name = st.session_state.form_info.get('form_number', 'Form').replace('-', '')
        
        # Group fields
        sections = {
            'customerData': {},
            'beneficiaryData': {},
            'attorneyData': {},
            'questionnaireData': {},
            'caseData': {},
            'defaultData': {},
            'conditionalData': {}
        }
        
        for field in st.session_state.fields:
            if field.is_mapped and field.db_mapping:
                # Determine section
                if field.db_mapping.startswith('customer.'):
                    section = 'customerData'
                elif field.db_mapping.startswith('beneficiary.'):
                    section = 'beneficiaryData'
                elif field.db_mapping.startswith('attorney.') or field.db_mapping.startswith('attorneyLawfirmDetails.'):
                    section = 'attorneyData'
                elif field.db_mapping.startswith('case.'):
                    section = 'caseData'
                else:
                    continue
                
                # Add field
                suffix = self._get_ts_suffix(field.field_type)
                sections[section][field.field_key] = f"{field.db_mapping}{suffix}"
            
            elif field.to_questionnaire:
                # Use question_key for questionnaire items
                key = field.question_key if field.question_key else field.field_key
                sections['questionnaireData'][key] = f"{field.field_key}:ConditionBox"
        
        # Generate TypeScript
        ts = f'export const {form_name} = {{\n'
        ts += f'    "formname": "{form_name}",\n'
        
        # Add sections
        for section_name, fields in sections.items():
            if section_name == 'conditionalData':
                continue  # Handle separately
            
            if fields:
                ts += f'    "{section_name}": {{\n'
                field_entries = []
                for key, value in fields.items():
                    field_entries.append(f'        "{key}": "{value}"')
                ts += ',\n'.join(field_entries)
                ts += '\n    },\n'
            else:
                ts += f'    "{section_name}": null,\n'
        
        # Add conditional data (empty for now)
        ts += '    "conditionalData": {},\n'
        
        # Add PDF name
        ts += f'    "pdfName": "{st.session_state.form_info.get("form_number", "Unknown")}"\n'
        ts += '};\n\n'
        ts += f'export default {form_name};'
        
        return ts
    
    def _get_ts_suffix(self, field_type: str) -> str:
        """Get TypeScript suffix for field type"""
        suffix_map = {
            'text': ':TextBox',
            'checkbox': ':CheckBox',
            'radio': ':RadioBox',
            'dropdown': ':DropdownBox',
            'signature': ':SignatureBox',
            'date': ':Date',
            'button': ':ButtonBox'
        }
        return suffix_map.get(field_type, ':TextBox')
    
    def generate_json(self) -> str:
        """Generate JSON export for questionnaire"""
        controls = []
        
        # Add fields by part
        for part_name, fields in st.session_state.fields_by_part.items():
            # Get part info
            part_info = st.session_state.part_structure.get(part_name, {})
            
            # Get questionnaire fields
            quest_fields = [f for f in fields if f.to_questionnaire]
            
            if quest_fields:
                # Add part title
                title_text = f"{part_name}"
                if part_info.get('title'):
                    title_text += f": {part_info['title']}"
                
                controls.append({
                    "name": f"{part_name.lower().replace(' ', '_')}_title",
                    "label": title_text,
                    "type": "title",
                    "validators": {},
                    "style": {"col": "12"}
                })
                
                # Add fields
                for field in quest_fields:
                    control = {
                        "name": field.field_key,
                        "label": field.field_label,
                        "type": "colorSwitch" if field.field_type in ["checkbox", "radio"] else field.field_type,
                        "validators": {}
                    }
                    
                    # Add field-specific properties
                    if field.field_type == "text":
                        control["style"] = {"col": "7"}
                    elif field.field_type in ["checkbox", "radio"]:
                        control["style"] = {"col": "12"}
                        if field.field_type == "radio":
                            control["id"] = field.field_key
                            control["value"] = "1"
                    
                    controls.append(control)
        
        return json.dumps({"controls": controls}, indent=2)

def render_mapping_interface(extractor: FieldExtractor):
    """Render the enhanced field mapping interface organized by parts"""
    st.markdown("## 🎯 Field Mapping by Parts")
    
    # Top controls
    with st.container():
        st.markdown('<div class="part-selector">', unsafe_allow_html=True)
        
        col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
        
        with col1:
            # Part selector
            part_options = ['All Parts'] + list(st.session_state.fields_by_part.keys())
            selected_part = st.selectbox(
                "📑 Select Part",
                part_options,
                index=part_options.index(st.session_state.selected_part) if st.session_state.selected_part in part_options else 0,
                key="part_selector"
            )
            st.session_state.selected_part = selected_part
        
        with col2:
            # Mapping filter
            mapping_filter = st.selectbox(
                "🔍 Filter by Status",
                ["All Fields", "Mapped", "Unmapped", "Questionnaire"],
                key="mapping_filter_select"
            )
            st.session_state.mapping_filter = mapping_filter.lower().replace(' fields', '').replace(' ', '_')
        
        with col3:
            # Database browser toggle
            st.session_state.show_db_browser = st.checkbox(
                "🗂️ Show DB Browser",
                value=st.session_state.show_db_browser,
                help="Show database structure browser"
            )
        
        with col4:
            # Field count
            if selected_part == 'All Parts':
                total_fields = len(st.session_state.fields)
            else:
                total_fields = len(st.session_state.fields_by_part.get(selected_part, []))
            
            mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
            st.metric("Progress", f"{mapped}/{total_fields}", f"{mapped/total_fields*100:.0f}%")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Quick actions
    st.markdown("### ⚡ Quick Actions")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🤖 Auto-Map Current View", use_container_width=True):
            fields_to_map = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_map = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            mapped_count = 0
            for field in fields_to_map:
                if not field.is_mapped and not field.to_questionnaire and field.field_type == 'text':
                    suggestion = extractor.suggest_mapping(field)
                    if suggestion:
                        field.db_mapping = suggestion
                        field.is_mapped = True
                        mapped_count += 1
            st.success(f"Auto-mapped {mapped_count} fields!")
            st.rerun()
    
    with col2:
        if st.button("📋 All Checkboxes → Quest", use_container_width=True):
            fields_to_move = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_move = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            count = 0
            for field in fields_to_move:
                if field.field_type in ['checkbox', 'radio'] and not field.to_questionnaire:
                    field.to_questionnaire = True
                    field.is_mapped = False
                    count += 1
            st.success(f"Moved {count} fields to questionnaire!")
            st.rerun()
    
    with col3:
        if st.button("🔄 Reset Current View", use_container_width=True):
            fields_to_reset = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_reset = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            for field in fields_to_reset:
                field.is_mapped = False
                field.db_mapping = None
                field.to_questionnaire = field.field_type in ['checkbox', 'radio', 'button']
            st.success("Reset complete!")
            st.rerun()
    
    with col4:
        unmapped = sum(1 for f in st.session_state.fields if not f.is_mapped and not f.to_questionnaire)
        if st.button(f"📋 All Unmapped → Quest ({unmapped})", use_container_width=True):
            fields_to_move = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_move = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            count = 0
            for field in fields_to_move:
                if not field.is_mapped and not field.to_questionnaire:
                    field.to_questionnaire = True
                    count += 1
            st.success(f"Moved {count} fields to questionnaire!")
            st.rerun()
    
    # Database object browser
    if st.session_state.show_db_browser:
        with st.expander("🗂️ Database Structure Browser", expanded=True):
            st.markdown("### Available Database Paths")
            st.caption("Click any path to copy it")
            
            # Create tabs for each main object
            tabs = st.tabs(list(DB_OBJECTS.keys()))
            
            for i, (obj_name, tab) in enumerate(zip(DB_OBJECTS.keys(), tabs)):
                with tab:
                    for sub_obj, fields in DB_OBJECTS[obj_name].items():
                        if sub_obj:
                            st.markdown(f"**{sub_obj}:**")
                        
                        # Display fields in columns
                        field_cols = st.columns(3)
                        for j, field in enumerate(fields):
                            col_idx = j % 3
                            with field_cols[col_idx]:
                                if sub_obj:
                                    path = f"{obj_name}.{sub_obj}.{field}"
                                else:
                                    path = f"{obj_name}.{field}"
                                
                                if st.button(f"📋 {field}", key=f"copy_{path}", use_container_width=True):
                                    st.code(path, language="text")
    
    # Field mapping interface organized by parts
    st.markdown("### 📝 Field Mappings by Part")
    
    # Get parts to display
    if st.session_state.selected_part == 'All Parts':
        parts_to_show = st.session_state.fields_by_part.items()
    else:
        parts_to_show = [(st.session_state.selected_part, 
                         st.session_state.fields_by_part.get(st.session_state.selected_part, []))]
    
    # Display each part
    for part_name, fields in parts_to_show:
        # Filter fields based on mapping filter
        if st.session_state.mapping_filter == 'mapped':
            display_fields = [f for f in fields if f.is_mapped]
        elif st.session_state.mapping_filter == 'unmapped':
            display_fields = [f for f in fields if not f.is_mapped and not f.to_questionnaire]
        elif st.session_state.mapping_filter == 'questionnaire':
            display_fields = [f for f in fields if f.to_questionnaire]
        else:
            display_fields = fields
        
        if not display_fields:
            continue
        
        # Get part info
        part_info = st.session_state.part_structure.get(part_name, {})
        
        # Part header with stats
        part_mapped = sum(1 for f in fields if f.is_mapped)
        part_quest = sum(1 for f in fields if f.to_questionnaire)
        part_unmapped = len(fields) - part_mapped - part_quest
        
        with st.container():
            st.markdown(f'''
            <div class="part-header">
                <strong>{part_name}</strong> {part_info.get('title', '')} 
                <br>
                <small>Total: {len(fields)} | Mapped: {part_mapped} | Questionnaire: {part_quest} | Unmapped: {part_unmapped}</small>
                <br>
                <small>Pages: {', '.join(map(str, part_info.get('pages', [])))}</small>
            </div>
            ''', unsafe_allow_html=True)
        
        # Display fields for this part
        for idx, field in enumerate(display_fields):
            with st.container():
                st.markdown('<div class="mapping-row">', unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    # Field info
                    display_label = field.field_label
                    if field.item_number:
                        display_label = f"{field.item_number}. {display_label}"
                    
                    st.markdown(f'<div class="field-label">{display_label}</div>', unsafe_allow_html=True)
                    
                    # Build field metadata
                    meta_parts = [
                        f'<span class="field-type">{field.field_type}</span>',
                        f'Field: {field.field_key}',
                        f'Page {field.page}'
                    ]
                    
                    # Only show quest key if it's different from field key
                    if field.to_questionnaire and field.question_key and field.question_key != field.field_key:
                        meta_parts.append(f'Quest: {field.question_key}')
                    
                    st.markdown(f"""
                    <div class="field-meta">
                        {' • '.join(meta_parts)}
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    # Create unique key for this field
                    unique_key = f"{part_name}_{field.field_id}_{idx}"
                    
                    col2a, col2b = st.columns([3, 1])
                    
                    with col2a:
                        # Database mapping dropdown
                        grouped_options = {
                            "Actions": ["-- Select Database Field --", "📋 Move to Questionnaire"],
                            "beneficiary": [],
                            "petitioner": [],
                            "customer": [],
                            "attorney": [],
                            "attorneyLawfirmDetails": [],
                            "case": [],
                            "employment": []
                        }
                        
                        # Group database paths
                        for path in extractor.db_paths:
                            obj_name = path.split('.')[0]
                            if obj_name in grouped_options:
                                grouped_options[obj_name].append(path)
                        
                        # Build flat list with separators
                        options = []
                        for group, items in grouped_options.items():
                            if items:
                                if options:  # Add separator between groups
                                    options.append(f"── {group} ──")
                                options.extend(items)
                        
                        # Current selection
                        if field.is_mapped and field.db_mapping:
                            current_value = field.db_mapping
                        elif field.to_questionnaire:
                            current_value = "📋 Move to Questionnaire"
                        else:
                            # Try to get suggestion
                            suggestion = extractor.suggest_mapping(field)
                            current_value = suggestion if suggestion else "-- Select Database Field --"
                        
                        # Find index
                        try:
                            current_index = options.index(current_value)
                        except ValueError:
                            current_index = 0
                        
                        selected = st.selectbox(
                            "Database Mapping",
                            options,
                            index=current_index,
                            key=f"map_{unique_key}",
                            label_visibility="collapsed"
                        )
                        
                        # Handle selection
                        if selected != current_value and not selected.startswith("──"):
                            if selected == "📋 Move to Questionnaire":
                                field.to_questionnaire = True
                                field.is_mapped = False
                                field.db_mapping = None
                            elif selected != "-- Select Database Field --":
                                field.db_mapping = selected
                                field.is_mapped = True
                                field.to_questionnaire = False
                            st.rerun()
                    
                    with col2b:
                        # Quick questionnaire toggle
                        if st.button("📋", key=f"quest_btn_{unique_key}", 
                                   help="Quick add to questionnaire",
                                   use_container_width=True):
                            field.to_questionnaire = True
                            field.is_mapped = False
                            field.db_mapping = None
                            st.rerun()
                
                with col3:
                    # Status
                    status = field.get_status()
                    if "Mapped" in status:
                        badge_class = "status-mapped"
                    elif "Questionnaire" in status:
                        badge_class = "status-questionnaire"
                    else:
                        badge_class = "status-unmapped"
                    
                    st.markdown(f'<span class="status-badge {badge_class}">{status}</span>', 
                              unsafe_allow_html=True)
                
                st.markdown('</div>', unsafe_allow_html=True)
        
        # Add spacing between parts
        st.markdown("<br>", unsafe_allow_html=True)

def main():
    """Main application"""
    st.markdown("# 🤖 USCIS Form Reader Pro")
    st.markdown("### Complete PDF Form Field Extraction & Mapping Solution")
    
    # Initialize extractor
    extractor = FieldExtractor()
    
    # Sidebar
    with st.sidebar:
        st.markdown("## ⚙️ Settings")
        st.session_state.debug_mode = st.checkbox("Debug Mode", value=False)
        
        if st.session_state.pdf_processed:
            st.markdown("---")
            st.markdown("### 📊 Statistics")
            stats = st.session_state.extraction_stats
            st.metric("Total Pages", stats.get('total_pages', 0))
            st.metric("Total Parts", stats.get('total_parts', 0))
            st.metric("Total Fields", stats.get('total_fields', 0))
            st.metric("Extraction Time", f"{stats.get('extraction_time', 0):.2f}s")
            
            if stats.get('errors'):
                st.warning(f"{len(stats['errors'])} errors occurred")
                with st.expander("View Errors"):
                    for error in stats['errors']:
                        st.text(error)
            
            # Field summary
            total = len(st.session_state.fields)
            mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
            quest = sum(1 for f in st.session_state.fields if f.to_questionnaire)
            
            st.markdown("---")
            st.markdown("### 📈 Mapping Progress")
            st.metric("Mapped to DB", f"{mapped} ({mapped/total*100:.1f}%)")
            st.metric("In Questionnaire", f"{quest} ({quest/total*100:.1f}%)")
            st.metric("Unmapped", f"{total - mapped - quest}")
            
            # Progress bar
            progress = (mapped + quest) / total if total > 0 else 0
            st.progress(progress)
            
            # Part breakdown
            st.markdown("---")
            st.markdown("### 📑 Parts Overview")
            for part_name, part_info in st.session_state.part_structure.items():
                fields = st.session_state.fields_by_part.get(part_name, [])
                mapped = sum(1 for f in fields if f.is_mapped)
                quest = sum(1 for f in fields if f.to_questionnaire)
                st.caption(f"{part_name}: {len(fields)} fields ({mapped} mapped, {quest} quest)")
    
    # Main tabs
    tab1, tab2, tab3 = st.tabs(["📤 Upload & Extract", "🎯 Map Fields", "📥 Export & Download"])
    
    with tab1:
        st.markdown("## Upload USCIS PDF Form")
        
        uploaded_file = st.file_uploader(
            "Choose a USCIS PDF form",
            type=['pdf'],
            help="Upload any fillable USCIS form (I-90, I-129, G-28, etc.)",
            key="pdf_uploader"
        )
        
        if uploaded_file:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                if st.button("🚀 Extract Fields by Parts", type="primary", use_container_width=True):
                    with st.spinner("Analyzing PDF structure and extracting fields by parts..."):
                        if extractor.extract_from_pdf(uploaded_file):
                            st.success(f"""
                            ✅ Successfully extracted {len(st.session_state.fields)} fields from {st.session_state.form_info.get('form_number', 'form')}!
                            
                            Found {len(st.session_state.fields_by_part)} parts with fields.
                            """)
                            
                            # Show extraction summary
                            with st.expander("📊 Extraction Summary", expanded=True):
                                for part_name, fields in st.session_state.fields_by_part.items():
                                    part_info = st.session_state.part_structure.get(part_name, {})
                                    
                                    st.write(f"**{part_name}** {part_info.get('title', '')}")
                                    st.write(f"- Fields: {len(fields)}")
                                    st.write(f"- Pages: {', '.join(map(str, part_info.get('pages', [])))}")
                                    
                                    # Field type breakdown
                                    types = defaultdict(int)
                                    for field in fields:
                                        types[field.field_type] += 1
                                    
                                    type_summary = ", ".join([f"{count} {ftype}" for ftype, count in types.items()])
                                    st.caption(f"Field types: {type_summary}")
                                    st.divider()
            
            with col2:
                if st.session_state.pdf_processed:
                    if st.button("🔄 Reset", type="secondary", use_container_width=True):
                        # Clear all session state
                        for key in list(st.session_state.keys()):
                            if key != 'debug_mode':
                                del st.session_state[key]
                        extractor.init_session_state()
                        st.rerun()
    
    with tab2:
        if not st.session_state.pdf_processed:
            st.info("👆 Please upload and extract a PDF form first.")
        else:
            render_mapping_interface(extractor)
    
    with tab3:
        if not st.session_state.pdf_processed:
            st.info("👆 Please upload and extract a PDF form first.")
        else:
            st.markdown("## 📥 Export & Download")
            
            # Summary
            total = len(st.session_state.fields)
            mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
            quest = sum(1 for f in st.session_state.fields if f.to_questionnaire)
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Fields", total)
            col2.metric("Mapped to Database", mapped)
            col3.metric("In Questionnaire", quest)
            
            st.markdown("---")
            
            # Export options
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 📄 TypeScript Export")
                st.markdown("Database mappings for your application")
                
                ts_code = extractor.generate_typescript()
                
                st.download_button(
                    label="⬇️ Download TypeScript File",
                    data=ts_code,
                    file_name=f"{st.session_state.form_info.get('form_number', 'form')}.ts",
                    mime="text/typescript",
                    use_container_width=True
                )
                
                with st.expander("Preview TypeScript"):
                    st.code(ts_code, language="typescript")
            
            with col2:
                st.markdown("### 📋 JSON Export")
                st.markdown("Questionnaire configuration")
                
                json_code = extractor.generate_json()
                
                st.download_button(
                    label="⬇️ Download JSON File",
                    data=json_code,
                    file_name=f"{st.session_state.form_info.get('form_number', 'form')}-questionnaire.json",
                    mime="application/json",
                    use_container_width=True
                )
                
                with st.expander("Preview JSON"):
                    st.code(json_code, language="json")
            
            # Combined export
            st.markdown("---")
            if st.button("📦 Download Both Files", type="primary", use_container_width=True):
                st.markdown("### Downloads Ready:")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button(
                        "TypeScript (.ts)",
                        extractor.generate_typescript(),
                        f"{st.session_state.form_info.get('form_number', 'form')}.ts",
                        mime="text/typescript"
                    )
                with col2:
                    st.download_button(
                        "JSON (.json)",
                        extractor.generate_json(),
                        f"{st.session_state.form_info.get('form_number', 'form')}-questionnaire.json",
                        mime="application/json"
                    )

if __name__ == "__main__":
    main()
, '', name)
        cleaned_name = cleaned_name.strip('_- ')
        
        # If the name is just a number or empty after cleaning, use a generic label
        if not cleaned_name or cleaned_name.isdigit():
            return f"Field {name}" if name and not name.isdigit() else "Field"
        
        # Common label mappings
        label_map = {
            'familyname': 'Family Name (Last Name)',
            'lastname': 'Last Name',
            'givenname': 'Given Name (First Name)', 
            'firstname': 'First Name',
            'middlename': 'Middle Name',
            'anumber': 'Alien Registration Number (A-Number)',
            'uscisaccount': 'USCIS Online Account Number',
            'dateofbirth': 'Date of Birth',
            'ssn': 'Social Security Number',
            'email': 'Email Address',
            'phone': 'Phone Number',
            'daytimephone': 'Daytime Phone Number',
            'mobile': 'Mobile Phone Number',
            'street': 'Street Address',
            'city': 'City or Town',
            'state': 'State',
            'zip': 'ZIP Code',
            'country': 'Country',
            'barnumber': 'Bar Number',
            'statebarnumber': 'State Bar Number',
            'lawfirm': 'Law Firm Name',
            'lawfirmname': 'Law Firm Name',
            'licensingauthority': 'Licensing Authority',
            'workphone': 'Work Phone Number',
            'faxnumber': 'Fax Number',
            'aptstefloornumber': 'Apt/Ste/Floor Number',
            'incareof': 'In Care Of',
            'yearsresiding': 'Years Residing',
            'monthsresiding': 'Months Residing'
        }
        
        # Check for exact match
        name_lower = cleaned_name.lower().replace('_', '').replace('-', '').replace(' ', '')
        for key, label in label_map.items():
            if key in name_lower or name_lower in key:
                return label
        
        # Convert to title case
        label = re.sub(r'([a-z])([A-Z])', r'\1 \2', cleaned_name)
        label = label.replace('_', ' ').replace('-', ' ')
        label = ' '.join(label.split())
        
        # Title case but preserve certain acronyms
        words = label.split()
        formatted_words = []
        acronyms = ['USCIS', 'US', 'USA', 'SSN', 'EIN', 'ID']
        
        for word in words:
            upper_word = word.upper()
            if upper_word in acronyms:
                formatted_words.append(upper_word)
            else:
                formatted_words.append(word.title())
        
        label = ' '.join(formatted_words)
        
        return label
    
    def _map_widget_type(self, widget_type: int) -> str:
        """Map PDF widget type to field type"""
        type_map = {
            1: "button",
            2: "checkbox",
            3: "radio",
            4: "text",
            5: "dropdown",
            6: "list",
            7: "signature"
        }
        return type_map.get(widget_type, "text")
    
    def suggest_mapping(self, field: PDFField) -> Optional[str]:
        """Suggest database mapping for field"""
        label_lower = field.field_label.lower()
        key_lower = field.field_key.lower()
        
        # Try pattern matching with both label and key
        for pattern, suggestions in self.field_patterns.items():
            if re.search(pattern, label_lower) or re.search(pattern, key_lower):
                # Return first matching suggestion
                for suggestion in suggestions:
                    if suggestion in self.db_paths:
                        return suggestion
        
        # Try exact field name matching
        for db_path in self.db_paths:
            path_parts = db_path.split('.')
            field_name = path_parts[-1].lower()
            
            # Check both label and key
            if field_name in label_lower.replace(' ', '').lower() or field_name in key_lower:
                return db_path
        
        return None
    
    def generate_typescript(self) -> str:
        """Generate TypeScript export"""
        form_name = st.session_state.form_info.get('form_number', 'Form').replace('-', '')
        
        # Group fields
        sections = {
            'customerData': {},
            'beneficiaryData': {},
            'attorneyData': {},
            'questionnaireData': {},
            'caseData': {},
            'defaultData': {},
            'conditionalData': {}
        }
        
        for field in st.session_state.fields:
            if field.is_mapped and field.db_mapping:
                # Determine section
                if field.db_mapping.startswith('customer.'):
                    section = 'customerData'
                elif field.db_mapping.startswith('beneficiary.'):
                    section = 'beneficiaryData'
                elif field.db_mapping.startswith('attorney.') or field.db_mapping.startswith('attorneyLawfirmDetails.'):
                    section = 'attorneyData'
                elif field.db_mapping.startswith('case.'):
                    section = 'caseData'
                else:
                    continue
                
                # Add field
                suffix = self._get_ts_suffix(field.field_type)
                sections[section][field.field_key] = f"{field.db_mapping}{suffix}"
            
            elif field.to_questionnaire:
                # Use question_key for questionnaire items
                key = field.question_key if field.question_key else field.field_key
                sections['questionnaireData'][key] = f"{field.field_key}:ConditionBox"
        
        # Generate TypeScript
        ts = f'export const {form_name} = {{\n'
        ts += f'    "formname": "{form_name}",\n'
        
        # Add sections
        for section_name, fields in sections.items():
            if section_name == 'conditionalData':
                continue  # Handle separately
            
            if fields:
                ts += f'    "{section_name}": {{\n'
                field_entries = []
                for key, value in fields.items():
                    field_entries.append(f'        "{key}": "{value}"')
                ts += ',\n'.join(field_entries)
                ts += '\n    },\n'
            else:
                ts += f'    "{section_name}": null,\n'
        
        # Add conditional data (empty for now)
        ts += '    "conditionalData": {},\n'
        
        # Add PDF name
        ts += f'    "pdfName": "{st.session_state.form_info.get("form_number", "Unknown")}"\n'
        ts += '};\n\n'
        ts += f'export default {form_name};'
        
        return ts
    
    def _get_ts_suffix(self, field_type: str) -> str:
        """Get TypeScript suffix for field type"""
        suffix_map = {
            'text': ':TextBox',
            'checkbox': ':CheckBox',
            'radio': ':RadioBox',
            'dropdown': ':DropdownBox',
            'signature': ':SignatureBox',
            'date': ':Date',
            'button': ':ButtonBox'
        }
        return suffix_map.get(field_type, ':TextBox')
    
    def generate_json(self) -> str:
        """Generate JSON export for questionnaire"""
        controls = []
        
        # Add fields by part
        for part_name, fields in st.session_state.fields_by_part.items():
            # Get part info
            part_info = st.session_state.part_structure.get(part_name, {})
            
            # Get questionnaire fields
            quest_fields = [f for f in fields if f.to_questionnaire]
            
            if quest_fields:
                # Add part title
                title_text = f"{part_name}"
                if part_info.get('title'):
                    title_text += f": {part_info['title']}"
                
                controls.append({
                    "name": f"{part_name.lower().replace(' ', '_')}_title",
                    "label": title_text,
                    "type": "title",
                    "validators": {},
                    "style": {"col": "12"}
                })
                
                # Add fields
                for field in quest_fields:
                    control = {
                        "name": field.field_key,
                        "label": field.field_label,
                        "type": "colorSwitch" if field.field_type in ["checkbox", "radio"] else field.field_type,
                        "validators": {}
                    }
                    
                    # Add field-specific properties
                    if field.field_type == "text":
                        control["style"] = {"col": "7"}
                    elif field.field_type in ["checkbox", "radio"]:
                        control["style"] = {"col": "12"}
                        if field.field_type == "radio":
                            control["id"] = field.field_key
                            control["value"] = "1"
                    
                    controls.append(control)
        
        return json.dumps({"controls": controls}, indent=2)

def render_mapping_interface(extractor: FieldExtractor):
    """Render the enhanced field mapping interface organized by parts"""
    st.markdown("## 🎯 Field Mapping by Parts")
    
    # Top controls
    with st.container():
        st.markdown('<div class="part-selector">', unsafe_allow_html=True)
        
        col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
        
        with col1:
            # Part selector
            part_options = ['All Parts'] + list(st.session_state.fields_by_part.keys())
            selected_part = st.selectbox(
                "📑 Select Part",
                part_options,
                index=part_options.index(st.session_state.selected_part) if st.session_state.selected_part in part_options else 0,
                key="part_selector"
            )
            st.session_state.selected_part = selected_part
        
        with col2:
            # Mapping filter
            mapping_filter = st.selectbox(
                "🔍 Filter by Status",
                ["All Fields", "Mapped", "Unmapped", "Questionnaire"],
                key="mapping_filter_select"
            )
            st.session_state.mapping_filter = mapping_filter.lower().replace(' fields', '').replace(' ', '_')
        
        with col3:
            # Database browser toggle
            st.session_state.show_db_browser = st.checkbox(
                "🗂️ Show DB Browser",
                value=st.session_state.show_db_browser,
                help="Show database structure browser"
            )
        
        with col4:
            # Field count
            if selected_part == 'All Parts':
                total_fields = len(st.session_state.fields)
            else:
                total_fields = len(st.session_state.fields_by_part.get(selected_part, []))
            
            mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
            st.metric("Progress", f"{mapped}/{total_fields}", f"{mapped/total_fields*100:.0f}%")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Quick actions
    st.markdown("### ⚡ Quick Actions")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🤖 Auto-Map Current View", use_container_width=True):
            fields_to_map = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_map = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            mapped_count = 0
            for field in fields_to_map:
                if not field.is_mapped and not field.to_questionnaire and field.field_type == 'text':
                    suggestion = extractor.suggest_mapping(field)
                    if suggestion:
                        field.db_mapping = suggestion
                        field.is_mapped = True
                        mapped_count += 1
            st.success(f"Auto-mapped {mapped_count} fields!")
            st.rerun()
    
    with col2:
        if st.button("📋 All Checkboxes → Quest", use_container_width=True):
            fields_to_move = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_move = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            count = 0
            for field in fields_to_move:
                if field.field_type in ['checkbox', 'radio'] and not field.to_questionnaire:
                    field.to_questionnaire = True
                    field.is_mapped = False
                    count += 1
            st.success(f"Moved {count} fields to questionnaire!")
            st.rerun()
    
    with col3:
        if st.button("🔄 Reset Current View", use_container_width=True):
            fields_to_reset = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_reset = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            for field in fields_to_reset:
                field.is_mapped = False
                field.db_mapping = None
                field.to_questionnaire = field.field_type in ['checkbox', 'radio', 'button']
            st.success("Reset complete!")
            st.rerun()
    
    with col4:
        unmapped = sum(1 for f in st.session_state.fields if not f.is_mapped and not f.to_questionnaire)
        if st.button(f"📋 All Unmapped → Quest ({unmapped})", use_container_width=True):
            fields_to_move = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_move = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            count = 0
            for field in fields_to_move:
                if not field.is_mapped and not field.to_questionnaire:
                    field.to_questionnaire = True
                    count += 1
            st.success(f"Moved {count} fields to questionnaire!")
            st.rerun()
    
    # Database object browser
    if st.session_state.show_db_browser:
        with st.expander("🗂️ Database Structure Browser", expanded=True):
            st.markdown("### Available Database Paths")
            st.caption("Click any path to copy it")
            
            # Create tabs for each main object
            tabs = st.tabs(list(DB_OBJECTS.keys()))
            
            for i, (obj_name, tab) in enumerate(zip(DB_OBJECTS.keys(), tabs)):
                with tab:
                    for sub_obj, fields in DB_OBJECTS[obj_name].items():
                        if sub_obj:
                            st.markdown(f"**{sub_obj}:**")
                        
                        # Display fields in columns
                        field_cols = st.columns(3)
                        for j, field in enumerate(fields):
                            col_idx = j % 3
                            with field_cols[col_idx]:
                                if sub_obj:
                                    path = f"{obj_name}.{sub_obj}.{field}"
                                else:
                                    path = f"{obj_name}.{field}"
                                
                                if st.button(f"📋 {field}", key=f"copy_{path}", use_container_width=True):
                                    st.code(path, language="text")
    
    # Field mapping interface organized by parts
    st.markdown("### 📝 Field Mappings by Part")
    
    # Get parts to display
    if st.session_state.selected_part == 'All Parts':
        parts_to_show = st.session_state.fields_by_part.items()
    else:
        parts_to_show = [(st.session_state.selected_part, 
                         st.session_state.fields_by_part.get(st.session_state.selected_part, []))]
    
    # Display each part
    for part_name, fields in parts_to_show:
        # Filter fields based on mapping filter
        if st.session_state.mapping_filter == 'mapped':
            display_fields = [f for f in fields if f.is_mapped]
        elif st.session_state.mapping_filter == 'unmapped':
            display_fields = [f for f in fields if not f.is_mapped and not f.to_questionnaire]
        elif st.session_state.mapping_filter == 'questionnaire':
            display_fields = [f for f in fields if f.to_questionnaire]
        else:
            display_fields = fields
        
        if not display_fields:
            continue
        
        # Get part info
        part_info = st.session_state.part_structure.get(part_name, {})
        
        # Part header with stats
        part_mapped = sum(1 for f in fields if f.is_mapped)
        part_quest = sum(1 for f in fields if f.to_questionnaire)
        part_unmapped = len(fields) - part_mapped - part_quest
        
        with st.container():
            st.markdown(f'''
            <div class="part-header">
                <strong>{part_name}</strong> {part_info.get('title', '')} 
                <br>
                <small>Total: {len(fields)} | Mapped: {part_mapped} | Questionnaire: {part_quest} | Unmapped: {part_unmapped}</small>
                <br>
                <small>Pages: {', '.join(map(str, part_info.get('pages', [])))}</small>
            </div>
            ''', unsafe_allow_html=True)
        
        # Display fields for this part
        for idx, field in enumerate(display_fields):
            with st.container():
                st.markdown('<div class="mapping-row">', unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    # Field info
                    display_label = field.field_label
                    if field.item_number:
                        display_label = f"{field.item_number}. {display_label}"
                    
                    st.markdown(f'<div class="field-label">{display_label}</div>', unsafe_allow_html=True)
                    
                    # Build field metadata
                    meta_parts = [
                        f'<span class="field-type">{field.field_type}</span>',
                        f'Field: {field.field_key}',
                        f'Page {field.page}'
                    ]
                    
                    # Only show quest key if it's different from field key
                    if field.to_questionnaire and field.question_key and field.question_key != field.field_key:
                        meta_parts.append(f'Quest: {field.question_key}')
                    
                    st.markdown(f"""
                    <div class="field-meta">
                        {' • '.join(meta_parts)}
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    # Create unique key for this field
                    unique_key = f"{part_name}_{field.field_id}_{idx}"
                    
                    col2a, col2b = st.columns([3, 1])
                    
                    with col2a:
                        # Database mapping dropdown
                        grouped_options = {
                            "Actions": ["-- Select Database Field --", "📋 Move to Questionnaire"],
                            "beneficiary": [],
                            "petitioner": [],
                            "customer": [],
                            "attorney": [],
                            "attorneyLawfirmDetails": [],
                            "case": [],
                            "employment": []
                        }
                        
                        # Group database paths
                        for path in extractor.db_paths:
                            obj_name = path.split('.')[0]
                            if obj_name in grouped_options:
                                grouped_options[obj_name].append(path)
                        
                        # Build flat list with separators
                        options = []
                        for group, items in grouped_options.items():
                            if items:
                                if options:  # Add separator between groups
                                    options.append(f"── {group} ──")
                                options.extend(items)
                        
                        # Current selection
                        if field.is_mapped and field.db_mapping:
                            current_value = field.db_mapping
                        elif field.to_questionnaire:
                            current_value = "📋 Move to Questionnaire"
                        else:
                            # Try to get suggestion
                            suggestion = extractor.suggest_mapping(field)
                            current_value = suggestion if suggestion else "-- Select Database Field --"
                        
                        # Find index
                        try:
                            current_index = options.index(current_value)
                        except ValueError:
                            current_index = 0
                        
                        selected = st.selectbox(
                            "Database Mapping",
                            options,
                            index=current_index,
                            key=f"map_{unique_key}",
                            label_visibility="collapsed"
                        )
                        
                        # Handle selection
                        if selected != current_value and not selected.startswith("──"):
                            if selected == "📋 Move to Questionnaire":
                                field.to_questionnaire = True
                                field.is_mapped = False
                                field.db_mapping = None
                            elif selected != "-- Select Database Field --":
                                field.db_mapping = selected
                                field.is_mapped = True
                                field.to_questionnaire = False
                            st.rerun()
                    
                    with col2b:
                        # Quick questionnaire toggle
                        if st.button("📋", key=f"quest_btn_{unique_key}", 
                                   help="Quick add to questionnaire",
                                   use_container_width=True):
                            field.to_questionnaire = True
                            field.is_mapped = False
                            field.db_mapping = None
                            st.rerun()
                
                with col3:
                    # Status
                    status = field.get_status()
                    if "Mapped" in status:
                        badge_class = "status-mapped"
                    elif "Questionnaire" in status:
                        badge_class = "status-questionnaire"
                    else:
                        badge_class = "status-unmapped"
                    
                    st.markdown(f'<span class="status-badge {badge_class}">{status}</span>', 
                              unsafe_allow_html=True)
                
                st.markdown('</div>', unsafe_allow_html=True)
        
        # Add spacing between parts
        st.markdown("<br>", unsafe_allow_html=True)

def main():
    """Main application"""
    st.markdown("# 🤖 USCIS Form Reader Pro")
    st.markdown("### Complete PDF Form Field Extraction & Mapping Solution")
    
    # Initialize extractor
    extractor = FieldExtractor()
    
    # Sidebar
    with st.sidebar:
        st.markdown("## ⚙️ Settings")
        st.session_state.debug_mode = st.checkbox("Debug Mode", value=False)
        
        if st.session_state.pdf_processed:
            st.markdown("---")
            st.markdown("### 📊 Statistics")
            stats = st.session_state.extraction_stats
            st.metric("Total Pages", stats.get('total_pages', 0))
            st.metric("Total Parts", stats.get('total_parts', 0))
            st.metric("Total Fields", stats.get('total_fields', 0))
            st.metric("Extraction Time", f"{stats.get('extraction_time', 0):.2f}s")
            
            if stats.get('errors'):
                st.warning(f"{len(stats['errors'])} errors occurred")
                with st.expander("View Errors"):
                    for error in stats['errors']:
                        st.text(error)
            
            # Field summary
            total = len(st.session_state.fields)
            mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
            quest = sum(1 for f in st.session_state.fields if f.to_questionnaire)
            
            st.markdown("---")
            st.markdown("### 📈 Mapping Progress")
            st.metric("Mapped to DB", f"{mapped} ({mapped/total*100:.1f}%)")
            st.metric("In Questionnaire", f"{quest} ({quest/total*100:.1f}%)")
            st.metric("Unmapped", f"{total - mapped - quest}")
            
            # Progress bar
            progress = (mapped + quest) / total if total > 0 else 0
            st.progress(progress)
            
            # Part breakdown
            st.markdown("---")
            st.markdown("### 📑 Parts Overview")
            for part_name, part_info in st.session_state.part_structure.items():
                fields = st.session_state.fields_by_part.get(part_name, [])
                mapped = sum(1 for f in fields if f.is_mapped)
                quest = sum(1 for f in fields if f.to_questionnaire)
                st.caption(f"{part_name}: {len(fields)} fields ({mapped} mapped, {quest} quest)")
    
    # Main tabs
    tab1, tab2, tab3 = st.tabs(["📤 Upload & Extract", "🎯 Map Fields", "📥 Export & Download"])
    
    with tab1:
        st.markdown("## Upload USCIS PDF Form")
        
        uploaded_file = st.file_uploader(
            "Choose a USCIS PDF form",
            type=['pdf'],
            help="Upload any fillable USCIS form (I-90, I-129, G-28, etc.)",
            key="pdf_uploader"
        )
        
        if uploaded_file:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                if st.button("🚀 Extract Fields by Parts", type="primary", use_container_width=True):
                    with st.spinner("Analyzing PDF structure and extracting fields by parts..."):
                        if extractor.extract_from_pdf(uploaded_file):
                            st.success(f"""
                            ✅ Successfully extracted {len(st.session_state.fields)} fields from {st.session_state.form_info.get('form_number', 'form')}!
                            
                            Found {len(st.session_state.fields_by_part)} parts with fields.
                            """)
                            
                            # Show extraction summary
                            with st.expander("📊 Extraction Summary", expanded=True):
                                for part_name, fields in st.session_state.fields_by_part.items():
                                    part_info = st.session_state.part_structure.get(part_name, {})
                                    
                                    st.write(f"**{part_name}** {part_info.get('title', '')}")
                                    st.write(f"- Fields: {len(fields)}")
                                    st.write(f"- Pages: {', '.join(map(str, part_info.get('pages', [])))}")
                                    
                                    # Field type breakdown
                                    types = defaultdict(int)
                                    for field in fields:
                                        types[field.field_type] += 1
                                    
                                    type_summary = ", ".join([f"{count} {ftype}" for ftype, count in types.items()])
                                    st.caption(f"Field types: {type_summary}")
                                    st.divider()
            
            with col2:
                if st.session_state.pdf_processed:
                    if st.button("🔄 Reset", type="secondary", use_container_width=True):
                        # Clear all session state
                        for key in list(st.session_state.keys()):
                            if key != 'debug_mode':
                                del st.session_state[key]
                        extractor.init_session_state()
                        st.rerun()
    
    with tab2:
        if not st.session_state.pdf_processed:
            st.info("👆 Please upload and extract a PDF form first.")
        else:
            render_mapping_interface(extractor)
    
    with tab3:
        if not st.session_state.pdf_processed:
            st.info("👆 Please upload and extract a PDF form first.")
        else:
            st.markdown("## 📥 Export & Download")
            
            # Summary
            total = len(st.session_state.fields)
            mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
            quest = sum(1 for f in st.session_state.fields if f.to_questionnaire)
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Fields", total)
            col2.metric("Mapped to Database", mapped)
            col3.metric("In Questionnaire", quest)
            
            st.markdown("---")
            
            # Export options
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 📄 TypeScript Export")
                st.markdown("Database mappings for your application")
                
                ts_code = extractor.generate_typescript()
                
                st.download_button(
                    label="⬇️ Download TypeScript File",
                    data=ts_code,
                    file_name=f"{st.session_state.form_info.get('form_number', 'form')}.ts",
                    mime="text/typescript",
                    use_container_width=True
                )
                
                with st.expander("Preview TypeScript"):
                    st.code(ts_code, language="typescript")
            
            with col2:
                st.markdown("### 📋 JSON Export")
                st.markdown("Questionnaire configuration")
                
                json_code = extractor.generate_json()
                
                st.download_button(
                    label="⬇️ Download JSON File",
                    data=json_code,
                    file_name=f"{st.session_state.form_info.get('form_number', 'form')}-questionnaire.json",
                    mime="application/json",
                    use_container_width=True
                )
                
                with st.expander("Preview JSON"):
                    st.code(json_code, language="json")
            
            # Combined export
            st.markdown("---")
            if st.button("📦 Download Both Files", type="primary", use_container_width=True):
                st.markdown("### Downloads Ready:")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button(
                        "TypeScript (.ts)",
                        extractor.generate_typescript(),
                        f"{st.session_state.form_info.get('form_number', 'form')}.ts",
                        mime="text/typescript"
                    )
                with col2:
                    st.download_button(
                        "JSON (.json)",
                        extractor.generate_json(),
                        f"{st.session_state.form_info.get('form_number', 'form')}-questionnaire.json",
                        mime="application/json"
                    )

if __name__ == "__main__":
    main()
, '', key)
        key = re.sub(r'_+
    
    def _generate_field_label(self, name: str) -> str:
        """Generate human-readable label"""
        # Common label mappings
        label_map = {
            'familyname': 'Family Name (Last Name)',
            'lastname': 'Last Name',
            'givenname': 'Given Name (First Name)', 
            'firstname': 'First Name',
            'middlename': 'Middle Name',
            'anumber': 'Alien Registration Number (A-Number)',
            'uscisaccount': 'USCIS Online Account Number',
            'dateofbirth': 'Date of Birth',
            'ssn': 'Social Security Number',
            'email': 'Email Address',
            'phone': 'Phone Number',
            'daytimephone': 'Daytime Phone Number',
            'mobile': 'Mobile Phone Number',
            'street': 'Street Address',
            'city': 'City or Town',
            'state': 'State',
            'zip': 'ZIP Code',
            'country': 'Country',
            'barnumber': 'Bar Number',
            'statebarnumber': 'State Bar Number',
            'lawfirm': 'Law Firm Name',
            'lawfirmname': 'Law Firm Name',
            'licensingauthority': 'Licensing Authority',
            'workphone': 'Work Phone Number',
            'faxnumber': 'Fax Number'
        }
        
        # Check for exact match
        name_lower = name.lower().replace('_', '').replace('-', '').replace(' ', '')
        for key, label in label_map.items():
            if key in name_lower or name_lower in key:
                return label
        
        # Convert to title case
        label = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
        label = label.replace('_', ' ').replace('-', ' ')
        label = ' '.join(label.split())
        label = label.title()
        
        return label
    
    def _map_widget_type(self, widget_type: int) -> str:
        """Map PDF widget type to field type"""
        type_map = {
            1: "button",
            2: "checkbox",
            3: "radio",
            4: "text",
            5: "dropdown",
            6: "list",
            7: "signature"
        }
        return type_map.get(widget_type, "text")
    
    def suggest_mapping(self, field: PDFField) -> Optional[str]:
        """Suggest database mapping for field"""
        label_lower = field.field_label.lower()
        key_lower = field.field_key.lower()
        
        # Try pattern matching with both label and key
        for pattern, suggestions in self.field_patterns.items():
            if re.search(pattern, label_lower) or re.search(pattern, key_lower):
                # Return first matching suggestion
                for suggestion in suggestions:
                    if suggestion in self.db_paths:
                        return suggestion
        
        # Try exact field name matching
        for db_path in self.db_paths:
            path_parts = db_path.split('.')
            field_name = path_parts[-1].lower()
            
            # Check both label and key
            if field_name in label_lower.replace(' ', '').lower() or field_name in key_lower:
                return db_path
        
        return None
    
    def generate_typescript(self) -> str:
        """Generate TypeScript export"""
        form_name = st.session_state.form_info.get('form_number', 'Form').replace('-', '')
        
        # Group fields
        sections = {
            'customerData': {},
            'beneficiaryData': {},
            'attorneyData': {},
            'questionnaireData': {},
            'caseData': {},
            'defaultData': {},
            'conditionalData': {}
        }
        
        for field in st.session_state.fields:
            if field.is_mapped and field.db_mapping:
                # Determine section
                if field.db_mapping.startswith('customer.'):
                    section = 'customerData'
                elif field.db_mapping.startswith('beneficiary.'):
                    section = 'beneficiaryData'
                elif field.db_mapping.startswith('attorney.') or field.db_mapping.startswith('attorneyLawfirmDetails.'):
                    section = 'attorneyData'
                elif field.db_mapping.startswith('case.'):
                    section = 'caseData'
                else:
                    continue
                
                # Add field
                suffix = self._get_ts_suffix(field.field_type)
                sections[section][field.field_key] = f"{field.db_mapping}{suffix}"
            
            elif field.to_questionnaire:
                # Use question_key for questionnaire items
                key = field.question_key if field.question_key else field.field_key
                sections['questionnaireData'][key] = f"{field.field_key}:ConditionBox"
        
        # Generate TypeScript
        ts = f'export const {form_name} = {{\n'
        ts += f'    "formname": "{form_name}",\n'
        
        # Add sections
        for section_name, fields in sections.items():
            if section_name == 'conditionalData':
                continue  # Handle separately
            
            if fields:
                ts += f'    "{section_name}": {{\n'
                field_entries = []
                for key, value in fields.items():
                    field_entries.append(f'        "{key}": "{value}"')
                ts += ',\n'.join(field_entries)
                ts += '\n    },\n'
            else:
                ts += f'    "{section_name}": null,\n'
        
        # Add conditional data (empty for now)
        ts += '    "conditionalData": {},\n'
        
        # Add PDF name
        ts += f'    "pdfName": "{st.session_state.form_info.get("form_number", "Unknown")}"\n'
        ts += '};\n\n'
        ts += f'export default {form_name};'
        
        return ts
    
    def _get_ts_suffix(self, field_type: str) -> str:
        """Get TypeScript suffix for field type"""
        suffix_map = {
            'text': ':TextBox',
            'checkbox': ':CheckBox',
            'radio': ':RadioBox',
            'dropdown': ':DropdownBox',
            'signature': ':SignatureBox',
            'date': ':Date',
            'button': ':ButtonBox'
        }
        return suffix_map.get(field_type, ':TextBox')
    
    def generate_json(self) -> str:
        """Generate JSON export for questionnaire"""
        controls = []
        
        # Add fields by part
        for part_name, fields in st.session_state.fields_by_part.items():
            # Get part info
            part_info = st.session_state.part_structure.get(part_name, {})
            
            # Get questionnaire fields
            quest_fields = [f for f in fields if f.to_questionnaire]
            
            if quest_fields:
                # Add part title
                title_text = f"{part_name}"
                if part_info.get('title'):
                    title_text += f": {part_info['title']}"
                
                controls.append({
                    "name": f"{part_name.lower().replace(' ', '_')}_title",
                    "label": title_text,
                    "type": "title",
                    "validators": {},
                    "style": {"col": "12"}
                })
                
                # Add fields
                for field in quest_fields:
                    control = {
                        "name": field.field_key,
                        "label": field.field_label,
                        "type": "colorSwitch" if field.field_type in ["checkbox", "radio"] else field.field_type,
                        "validators": {}
                    }
                    
                    # Add field-specific properties
                    if field.field_type == "text":
                        control["style"] = {"col": "7"}
                    elif field.field_type in ["checkbox", "radio"]:
                        control["style"] = {"col": "12"}
                        if field.field_type == "radio":
                            control["id"] = field.field_key
                            control["value"] = "1"
                    
                    controls.append(control)
        
        return json.dumps({"controls": controls}, indent=2)

def render_mapping_interface(extractor: FieldExtractor):
    """Render the enhanced field mapping interface organized by parts"""
    st.markdown("## 🎯 Field Mapping by Parts")
    
    # Top controls
    with st.container():
        st.markdown('<div class="part-selector">', unsafe_allow_html=True)
        
        col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
        
        with col1:
            # Part selector
            part_options = ['All Parts'] + list(st.session_state.fields_by_part.keys())
            selected_part = st.selectbox(
                "📑 Select Part",
                part_options,
                index=part_options.index(st.session_state.selected_part) if st.session_state.selected_part in part_options else 0,
                key="part_selector"
            )
            st.session_state.selected_part = selected_part
        
        with col2:
            # Mapping filter
            mapping_filter = st.selectbox(
                "🔍 Filter by Status",
                ["All Fields", "Mapped", "Unmapped", "Questionnaire"],
                key="mapping_filter_select"
            )
            st.session_state.mapping_filter = mapping_filter.lower().replace(' fields', '').replace(' ', '_')
        
        with col3:
            # Database browser toggle
            st.session_state.show_db_browser = st.checkbox(
                "🗂️ Show DB Browser",
                value=st.session_state.show_db_browser,
                help="Show database structure browser"
            )
        
        with col4:
            # Field count
            if selected_part == 'All Parts':
                total_fields = len(st.session_state.fields)
            else:
                total_fields = len(st.session_state.fields_by_part.get(selected_part, []))
            
            mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
            st.metric("Progress", f"{mapped}/{total_fields}", f"{mapped/total_fields*100:.0f}%")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Quick actions
    st.markdown("### ⚡ Quick Actions")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🤖 Auto-Map Current View", use_container_width=True):
            fields_to_map = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_map = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            mapped_count = 0
            for field in fields_to_map:
                if not field.is_mapped and not field.to_questionnaire and field.field_type == 'text':
                    suggestion = extractor.suggest_mapping(field)
                    if suggestion:
                        field.db_mapping = suggestion
                        field.is_mapped = True
                        mapped_count += 1
            st.success(f"Auto-mapped {mapped_count} fields!")
            st.rerun()
    
    with col2:
        if st.button("📋 All Checkboxes → Quest", use_container_width=True):
            fields_to_move = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_move = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            count = 0
            for field in fields_to_move:
                if field.field_type in ['checkbox', 'radio'] and not field.to_questionnaire:
                    field.to_questionnaire = True
                    field.is_mapped = False
                    count += 1
            st.success(f"Moved {count} fields to questionnaire!")
            st.rerun()
    
    with col3:
        if st.button("🔄 Reset Current View", use_container_width=True):
            fields_to_reset = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_reset = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            for field in fields_to_reset:
                field.is_mapped = False
                field.db_mapping = None
                field.to_questionnaire = field.field_type in ['checkbox', 'radio', 'button']
            st.success("Reset complete!")
            st.rerun()
    
    with col4:
        unmapped = sum(1 for f in st.session_state.fields if not f.is_mapped and not f.to_questionnaire)
        if st.button(f"📋 All Unmapped → Quest ({unmapped})", use_container_width=True):
            fields_to_move = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_move = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            count = 0
            for field in fields_to_move:
                if not field.is_mapped and not field.to_questionnaire:
                    field.to_questionnaire = True
                    count += 1
            st.success(f"Moved {count} fields to questionnaire!")
            st.rerun()
    
    # Database object browser
    if st.session_state.show_db_browser:
        with st.expander("🗂️ Database Structure Browser", expanded=True):
            st.markdown("### Available Database Paths")
            st.caption("Click any path to copy it")
            
            # Create tabs for each main object
            tabs = st.tabs(list(DB_OBJECTS.keys()))
            
            for i, (obj_name, tab) in enumerate(zip(DB_OBJECTS.keys(), tabs)):
                with tab:
                    for sub_obj, fields in DB_OBJECTS[obj_name].items():
                        if sub_obj:
                            st.markdown(f"**{sub_obj}:**")
                        
                        # Display fields in columns
                        field_cols = st.columns(3)
                        for j, field in enumerate(fields):
                            col_idx = j % 3
                            with field_cols[col_idx]:
                                if sub_obj:
                                    path = f"{obj_name}.{sub_obj}.{field}"
                                else:
                                    path = f"{obj_name}.{field}"
                                
                                if st.button(f"📋 {field}", key=f"copy_{path}", use_container_width=True):
                                    st.code(path, language="text")
    
    # Field mapping interface organized by parts
    st.markdown("### 📝 Field Mappings by Part")
    
    # Get parts to display
    if st.session_state.selected_part == 'All Parts':
        parts_to_show = st.session_state.fields_by_part.items()
    else:
        parts_to_show = [(st.session_state.selected_part, 
                         st.session_state.fields_by_part.get(st.session_state.selected_part, []))]
    
    # Display each part
    for part_name, fields in parts_to_show:
        # Filter fields based on mapping filter
        if st.session_state.mapping_filter == 'mapped':
            display_fields = [f for f in fields if f.is_mapped]
        elif st.session_state.mapping_filter == 'unmapped':
            display_fields = [f for f in fields if not f.is_mapped and not f.to_questionnaire]
        elif st.session_state.mapping_filter == 'questionnaire':
            display_fields = [f for f in fields if f.to_questionnaire]
        else:
            display_fields = fields
        
        if not display_fields:
            continue
        
        # Get part info
        part_info = st.session_state.part_structure.get(part_name, {})
        
        # Part header with stats
        part_mapped = sum(1 for f in fields if f.is_mapped)
        part_quest = sum(1 for f in fields if f.to_questionnaire)
        part_unmapped = len(fields) - part_mapped - part_quest
        
        with st.container():
            st.markdown(f'''
            <div class="part-header">
                <strong>{part_name}</strong> {part_info.get('title', '')} 
                <br>
                <small>Total: {len(fields)} | Mapped: {part_mapped} | Questionnaire: {part_quest} | Unmapped: {part_unmapped}</small>
                <br>
                <small>Pages: {', '.join(map(str, part_info.get('pages', [])))}</small>
            </div>
            ''', unsafe_allow_html=True)
        
        # Display fields for this part
        for idx, field in enumerate(display_fields):
            with st.container():
                st.markdown('<div class="mapping-row">', unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    # Field info
                    display_label = field.field_label
                    if field.item_number:
                        display_label = f"{field.item_number}. {display_label}"
                    
                    st.markdown(f'<div class="field-label">{display_label}</div>', unsafe_allow_html=True)
                    
                    # Build field metadata
                    meta_parts = [
                        f'<span class="field-type">{field.field_type}</span>',
                        f'Field: {field.field_key}',
                        f'Page {field.page}'
                    ]
                    
                    # Only show quest key if it's different from field key
                    if field.to_questionnaire and field.question_key and field.question_key != field.field_key:
                        meta_parts.append(f'Quest: {field.question_key}')
                    
                    st.markdown(f"""
                    <div class="field-meta">
                        {' • '.join(meta_parts)}
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    # Create unique key for this field
                    unique_key = f"{part_name}_{field.field_id}_{idx}"
                    
                    col2a, col2b = st.columns([3, 1])
                    
                    with col2a:
                        # Database mapping dropdown
                        grouped_options = {
                            "Actions": ["-- Select Database Field --", "📋 Move to Questionnaire"],
                            "beneficiary": [],
                            "petitioner": [],
                            "customer": [],
                            "attorney": [],
                            "attorneyLawfirmDetails": [],
                            "case": [],
                            "employment": []
                        }
                        
                        # Group database paths
                        for path in extractor.db_paths:
                            obj_name = path.split('.')[0]
                            if obj_name in grouped_options:
                                grouped_options[obj_name].append(path)
                        
                        # Build flat list with separators
                        options = []
                        for group, items in grouped_options.items():
                            if items:
                                if options:  # Add separator between groups
                                    options.append(f"── {group} ──")
                                options.extend(items)
                        
                        # Current selection
                        if field.is_mapped and field.db_mapping:
                            current_value = field.db_mapping
                        elif field.to_questionnaire:
                            current_value = "📋 Move to Questionnaire"
                        else:
                            # Try to get suggestion
                            suggestion = extractor.suggest_mapping(field)
                            current_value = suggestion if suggestion else "-- Select Database Field --"
                        
                        # Find index
                        try:
                            current_index = options.index(current_value)
                        except ValueError:
                            current_index = 0
                        
                        selected = st.selectbox(
                            "Database Mapping",
                            options,
                            index=current_index,
                            key=f"map_{unique_key}",
                            label_visibility="collapsed"
                        )
                        
                        # Handle selection
                        if selected != current_value and not selected.startswith("──"):
                            if selected == "📋 Move to Questionnaire":
                                field.to_questionnaire = True
                                field.is_mapped = False
                                field.db_mapping = None
                            elif selected != "-- Select Database Field --":
                                field.db_mapping = selected
                                field.is_mapped = True
                                field.to_questionnaire = False
                            st.rerun()
                    
                    with col2b:
                        # Quick questionnaire toggle
                        if st.button("📋", key=f"quest_btn_{unique_key}", 
                                   help="Quick add to questionnaire",
                                   use_container_width=True):
                            field.to_questionnaire = True
                            field.is_mapped = False
                            field.db_mapping = None
                            st.rerun()
                
                with col3:
                    # Status
                    status = field.get_status()
                    if "Mapped" in status:
                        badge_class = "status-mapped"
                    elif "Questionnaire" in status:
                        badge_class = "status-questionnaire"
                    else:
                        badge_class = "status-unmapped"
                    
                    st.markdown(f'<span class="status-badge {badge_class}">{status}</span>', 
                              unsafe_allow_html=True)
                
                st.markdown('</div>', unsafe_allow_html=True)
        
        # Add spacing between parts
        st.markdown("<br>", unsafe_allow_html=True)

def main():
    """Main application"""
    st.markdown("# 🤖 USCIS Form Reader Pro")
    st.markdown("### Complete PDF Form Field Extraction & Mapping Solution")
    
    # Initialize extractor
    extractor = FieldExtractor()
    
    # Sidebar
    with st.sidebar:
        st.markdown("## ⚙️ Settings")
        st.session_state.debug_mode = st.checkbox("Debug Mode", value=False)
        
        if st.session_state.pdf_processed:
            st.markdown("---")
            st.markdown("### 📊 Statistics")
            stats = st.session_state.extraction_stats
            st.metric("Total Pages", stats.get('total_pages', 0))
            st.metric("Total Parts", stats.get('total_parts', 0))
            st.metric("Total Fields", stats.get('total_fields', 0))
            st.metric("Extraction Time", f"{stats.get('extraction_time', 0):.2f}s")
            
            if stats.get('errors'):
                st.warning(f"{len(stats['errors'])} errors occurred")
                with st.expander("View Errors"):
                    for error in stats['errors']:
                        st.text(error)
            
            # Field summary
            total = len(st.session_state.fields)
            mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
            quest = sum(1 for f in st.session_state.fields if f.to_questionnaire)
            
            st.markdown("---")
            st.markdown("### 📈 Mapping Progress")
            st.metric("Mapped to DB", f"{mapped} ({mapped/total*100:.1f}%)")
            st.metric("In Questionnaire", f"{quest} ({quest/total*100:.1f}%)")
            st.metric("Unmapped", f"{total - mapped - quest}")
            
            # Progress bar
            progress = (mapped + quest) / total if total > 0 else 0
            st.progress(progress)
            
            # Part breakdown
            st.markdown("---")
            st.markdown("### 📑 Parts Overview")
            for part_name, part_info in st.session_state.part_structure.items():
                fields = st.session_state.fields_by_part.get(part_name, [])
                mapped = sum(1 for f in fields if f.is_mapped)
                quest = sum(1 for f in fields if f.to_questionnaire)
                st.caption(f"{part_name}: {len(fields)} fields ({mapped} mapped, {quest} quest)")
    
    # Main tabs
    tab1, tab2, tab3 = st.tabs(["📤 Upload & Extract", "🎯 Map Fields", "📥 Export & Download"])
    
    with tab1:
        st.markdown("## Upload USCIS PDF Form")
        
        uploaded_file = st.file_uploader(
            "Choose a USCIS PDF form",
            type=['pdf'],
            help="Upload any fillable USCIS form (I-90, I-129, G-28, etc.)",
            key="pdf_uploader"
        )
        
        if uploaded_file:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                if st.button("🚀 Extract Fields by Parts", type="primary", use_container_width=True):
                    with st.spinner("Analyzing PDF structure and extracting fields by parts..."):
                        if extractor.extract_from_pdf(uploaded_file):
                            st.success(f"""
                            ✅ Successfully extracted {len(st.session_state.fields)} fields from {st.session_state.form_info.get('form_number', 'form')}!
                            
                            Found {len(st.session_state.fields_by_part)} parts with fields.
                            """)
                            
                            # Show extraction summary
                            with st.expander("📊 Extraction Summary", expanded=True):
                                for part_name, fields in st.session_state.fields_by_part.items():
                                    part_info = st.session_state.part_structure.get(part_name, {})
                                    
                                    st.write(f"**{part_name}** {part_info.get('title', '')}")
                                    st.write(f"- Fields: {len(fields)}")
                                    st.write(f"- Pages: {', '.join(map(str, part_info.get('pages', [])))}")
                                    
                                    # Field type breakdown
                                    types = defaultdict(int)
                                    for field in fields:
                                        types[field.field_type] += 1
                                    
                                    type_summary = ", ".join([f"{count} {ftype}" for ftype, count in types.items()])
                                    st.caption(f"Field types: {type_summary}")
                                    st.divider()
            
            with col2:
                if st.session_state.pdf_processed:
                    if st.button("🔄 Reset", type="secondary", use_container_width=True):
                        # Clear all session state
                        for key in list(st.session_state.keys()):
                            if key != 'debug_mode':
                                del st.session_state[key]
                        extractor.init_session_state()
                        st.rerun()
    
    with tab2:
        if not st.session_state.pdf_processed:
            st.info("👆 Please upload and extract a PDF form first.")
        else:
            render_mapping_interface(extractor)
    
    with tab3:
        if not st.session_state.pdf_processed:
            st.info("👆 Please upload and extract a PDF form first.")
        else:
            st.markdown("## 📥 Export & Download")
            
            # Summary
            total = len(st.session_state.fields)
            mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
            quest = sum(1 for f in st.session_state.fields if f.to_questionnaire)
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Fields", total)
            col2.metric("Mapped to Database", mapped)
            col3.metric("In Questionnaire", quest)
            
            st.markdown("---")
            
            # Export options
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 📄 TypeScript Export")
                st.markdown("Database mappings for your application")
                
                ts_code = extractor.generate_typescript()
                
                st.download_button(
                    label="⬇️ Download TypeScript File",
                    data=ts_code,
                    file_name=f"{st.session_state.form_info.get('form_number', 'form')}.ts",
                    mime="text/typescript",
                    use_container_width=True
                )
                
                with st.expander("Preview TypeScript"):
                    st.code(ts_code, language="typescript")
            
            with col2:
                st.markdown("### 📋 JSON Export")
                st.markdown("Questionnaire configuration")
                
                json_code = extractor.generate_json()
                
                st.download_button(
                    label="⬇️ Download JSON File",
                    data=json_code,
                    file_name=f"{st.session_state.form_info.get('form_number', 'form')}-questionnaire.json",
                    mime="application/json",
                    use_container_width=True
                )
                
                with st.expander("Preview JSON"):
                    st.code(json_code, language="json")
            
            # Combined export
            st.markdown("---")
            if st.button("📦 Download Both Files", type="primary", use_container_width=True):
                st.markdown("### Downloads Ready:")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button(
                        "TypeScript (.ts)",
                        extractor.generate_typescript(),
                        f"{st.session_state.form_info.get('form_number', 'form')}.ts",
                        mime="text/typescript"
                    )
                with col2:
                    st.download_button(
                        "JSON (.json)",
                        extractor.generate_json(),
                        f"{st.session_state.form_info.get('form_number', 'form')}-questionnaire.json",
                        mime="application/json"
                    )

if __name__ == "__main__":
    main()
, '', key)  # Remove trailing underscores
        
        # Common abbreviations
        abbreviations = {
            'family_name': 'familyName',
            'last_name': 'lastName',
            'given_name': 'givenName',
            'first_name': 'firstName',
            'middle_name': 'middleName',
            'date_of_birth': 'dob',
            'social_security': 'ssn',
            'alien_number': 'aNumber',
            'email_address': 'email',
            'phone_number': 'phone',
            'street_address': 'street',
            'zip_code': 'zip',
            'state_bar_number': 'stateBarNumber',
            'law_firm_name': 'lawFirmName',
            'licensing_authority': 'licensingAuthority'
        }
        
        key_lower = key.lower()
        for pattern, replacement in abbreviations.items():
            if pattern in key_lower:
                return replacement
        
        # Convert to camelCase
        parts = key.split('_')
        if len(parts) > 1:
            key = parts[0].lower() + ''.join(p.capitalize() for p in parts[1:] if p)
        else:
            key = key.lower() if key else 'field'
        
        # Ensure we have a valid key
        if not key or key.isdigit():
            key = 'field'
        
        # Limit length
        if len(key) > 30:
            key = key[:30]
        
        return key
    
    def _generate_field_label(self, name: str) -> str:
        """Generate human-readable label"""
        # Common label mappings
        label_map = {
            'familyname': 'Family Name (Last Name)',
            'lastname': 'Last Name',
            'givenname': 'Given Name (First Name)', 
            'firstname': 'First Name',
            'middlename': 'Middle Name',
            'anumber': 'Alien Registration Number (A-Number)',
            'uscisaccount': 'USCIS Online Account Number',
            'dateofbirth': 'Date of Birth',
            'ssn': 'Social Security Number',
            'email': 'Email Address',
            'phone': 'Phone Number',
            'daytimephone': 'Daytime Phone Number',
            'mobile': 'Mobile Phone Number',
            'street': 'Street Address',
            'city': 'City or Town',
            'state': 'State',
            'zip': 'ZIP Code',
            'country': 'Country',
            'barnumber': 'Bar Number',
            'statebarnumber': 'State Bar Number',
            'lawfirm': 'Law Firm Name',
            'lawfirmname': 'Law Firm Name',
            'licensingauthority': 'Licensing Authority',
            'workphone': 'Work Phone Number',
            'faxnumber': 'Fax Number'
        }
        
        # Check for exact match
        name_lower = name.lower().replace('_', '').replace('-', '').replace(' ', '')
        for key, label in label_map.items():
            if key in name_lower or name_lower in key:
                return label
        
        # Convert to title case
        label = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
        label = label.replace('_', ' ').replace('-', ' ')
        label = ' '.join(label.split())
        label = label.title()
        
        return label
    
    def _map_widget_type(self, widget_type: int) -> str:
        """Map PDF widget type to field type"""
        type_map = {
            1: "button",
            2: "checkbox",
            3: "radio",
            4: "text",
            5: "dropdown",
            6: "list",
            7: "signature"
        }
        return type_map.get(widget_type, "text")
    
    def suggest_mapping(self, field: PDFField) -> Optional[str]:
        """Suggest database mapping for field"""
        label_lower = field.field_label.lower()
        key_lower = field.field_key.lower()
        
        # Try pattern matching with both label and key
        for pattern, suggestions in self.field_patterns.items():
            if re.search(pattern, label_lower) or re.search(pattern, key_lower):
                # Return first matching suggestion
                for suggestion in suggestions:
                    if suggestion in self.db_paths:
                        return suggestion
        
        # Try exact field name matching
        for db_path in self.db_paths:
            path_parts = db_path.split('.')
            field_name = path_parts[-1].lower()
            
            # Check both label and key
            if field_name in label_lower.replace(' ', '').lower() or field_name in key_lower:
                return db_path
        
        return None
    
    def generate_typescript(self) -> str:
        """Generate TypeScript export"""
        form_name = st.session_state.form_info.get('form_number', 'Form').replace('-', '')
        
        # Group fields
        sections = {
            'customerData': {},
            'beneficiaryData': {},
            'attorneyData': {},
            'questionnaireData': {},
            'caseData': {},
            'defaultData': {},
            'conditionalData': {}
        }
        
        for field in st.session_state.fields:
            if field.is_mapped and field.db_mapping:
                # Determine section
                if field.db_mapping.startswith('customer.'):
                    section = 'customerData'
                elif field.db_mapping.startswith('beneficiary.'):
                    section = 'beneficiaryData'
                elif field.db_mapping.startswith('attorney.') or field.db_mapping.startswith('attorneyLawfirmDetails.'):
                    section = 'attorneyData'
                elif field.db_mapping.startswith('case.'):
                    section = 'caseData'
                else:
                    continue
                
                # Add field
                suffix = self._get_ts_suffix(field.field_type)
                sections[section][field.field_key] = f"{field.db_mapping}{suffix}"
            
            elif field.to_questionnaire:
                # Use question_key for questionnaire items
                key = field.question_key if field.question_key else field.field_key
                sections['questionnaireData'][key] = f"{field.field_key}:ConditionBox"
        
        # Generate TypeScript
        ts = f'export const {form_name} = {{\n'
        ts += f'    "formname": "{form_name}",\n'
        
        # Add sections
        for section_name, fields in sections.items():
            if section_name == 'conditionalData':
                continue  # Handle separately
            
            if fields:
                ts += f'    "{section_name}": {{\n'
                field_entries = []
                for key, value in fields.items():
                    field_entries.append(f'        "{key}": "{value}"')
                ts += ',\n'.join(field_entries)
                ts += '\n    },\n'
            else:
                ts += f'    "{section_name}": null,\n'
        
        # Add conditional data (empty for now)
        ts += '    "conditionalData": {},\n'
        
        # Add PDF name
        ts += f'    "pdfName": "{st.session_state.form_info.get("form_number", "Unknown")}"\n'
        ts += '};\n\n'
        ts += f'export default {form_name};'
        
        return ts
    
    def _get_ts_suffix(self, field_type: str) -> str:
        """Get TypeScript suffix for field type"""
        suffix_map = {
            'text': ':TextBox',
            'checkbox': ':CheckBox',
            'radio': ':RadioBox',
            'dropdown': ':DropdownBox',
            'signature': ':SignatureBox',
            'date': ':Date',
            'button': ':ButtonBox'
        }
        return suffix_map.get(field_type, ':TextBox')
    
    def generate_json(self) -> str:
        """Generate JSON export for questionnaire"""
        controls = []
        
        # Add fields by part
        for part_name, fields in st.session_state.fields_by_part.items():
            # Get part info
            part_info = st.session_state.part_structure.get(part_name, {})
            
            # Get questionnaire fields
            quest_fields = [f for f in fields if f.to_questionnaire]
            
            if quest_fields:
                # Add part title
                title_text = f"{part_name}"
                if part_info.get('title'):
                    title_text += f": {part_info['title']}"
                
                controls.append({
                    "name": f"{part_name.lower().replace(' ', '_')}_title",
                    "label": title_text,
                    "type": "title",
                    "validators": {},
                    "style": {"col": "12"}
                })
                
                # Add fields
                for field in quest_fields:
                    control = {
                        "name": field.field_key,
                        "label": field.field_label,
                        "type": "colorSwitch" if field.field_type in ["checkbox", "radio"] else field.field_type,
                        "validators": {}
                    }
                    
                    # Add field-specific properties
                    if field.field_type == "text":
                        control["style"] = {"col": "7"}
                    elif field.field_type in ["checkbox", "radio"]:
                        control["style"] = {"col": "12"}
                        if field.field_type == "radio":
                            control["id"] = field.field_key
                            control["value"] = "1"
                    
                    controls.append(control)
        
        return json.dumps({"controls": controls}, indent=2)

def render_mapping_interface(extractor: FieldExtractor):
    """Render the enhanced field mapping interface organized by parts"""
    st.markdown("## 🎯 Field Mapping by Parts")
    
    # Top controls
    with st.container():
        st.markdown('<div class="part-selector">', unsafe_allow_html=True)
        
        col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
        
        with col1:
            # Part selector
            part_options = ['All Parts'] + list(st.session_state.fields_by_part.keys())
            selected_part = st.selectbox(
                "📑 Select Part",
                part_options,
                index=part_options.index(st.session_state.selected_part) if st.session_state.selected_part in part_options else 0,
                key="part_selector"
            )
            st.session_state.selected_part = selected_part
        
        with col2:
            # Mapping filter
            mapping_filter = st.selectbox(
                "🔍 Filter by Status",
                ["All Fields", "Mapped", "Unmapped", "Questionnaire"],
                key="mapping_filter_select"
            )
            st.session_state.mapping_filter = mapping_filter.lower().replace(' fields', '').replace(' ', '_')
        
        with col3:
            # Database browser toggle
            st.session_state.show_db_browser = st.checkbox(
                "🗂️ Show DB Browser",
                value=st.session_state.show_db_browser,
                help="Show database structure browser"
            )
        
        with col4:
            # Field count
            if selected_part == 'All Parts':
                total_fields = len(st.session_state.fields)
            else:
                total_fields = len(st.session_state.fields_by_part.get(selected_part, []))
            
            mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
            st.metric("Progress", f"{mapped}/{total_fields}", f"{mapped/total_fields*100:.0f}%")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Quick actions
    st.markdown("### ⚡ Quick Actions")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🤖 Auto-Map Current View", use_container_width=True):
            fields_to_map = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_map = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            mapped_count = 0
            for field in fields_to_map:
                if not field.is_mapped and not field.to_questionnaire and field.field_type == 'text':
                    suggestion = extractor.suggest_mapping(field)
                    if suggestion:
                        field.db_mapping = suggestion
                        field.is_mapped = True
                        mapped_count += 1
            st.success(f"Auto-mapped {mapped_count} fields!")
            st.rerun()
    
    with col2:
        if st.button("📋 All Checkboxes → Quest", use_container_width=True):
            fields_to_move = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_move = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            count = 0
            for field in fields_to_move:
                if field.field_type in ['checkbox', 'radio'] and not field.to_questionnaire:
                    field.to_questionnaire = True
                    field.is_mapped = False
                    count += 1
            st.success(f"Moved {count} fields to questionnaire!")
            st.rerun()
    
    with col3:
        if st.button("🔄 Reset Current View", use_container_width=True):
            fields_to_reset = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_reset = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            for field in fields_to_reset:
                field.is_mapped = False
                field.db_mapping = None
                field.to_questionnaire = field.field_type in ['checkbox', 'radio', 'button']
            st.success("Reset complete!")
            st.rerun()
    
    with col4:
        unmapped = sum(1 for f in st.session_state.fields if not f.is_mapped and not f.to_questionnaire)
        if st.button(f"📋 All Unmapped → Quest ({unmapped})", use_container_width=True):
            fields_to_move = st.session_state.fields
            if st.session_state.selected_part != 'All Parts':
                fields_to_move = st.session_state.fields_by_part.get(st.session_state.selected_part, [])
            
            count = 0
            for field in fields_to_move:
                if not field.is_mapped and not field.to_questionnaire:
                    field.to_questionnaire = True
                    count += 1
            st.success(f"Moved {count} fields to questionnaire!")
            st.rerun()
    
    # Database object browser
    if st.session_state.show_db_browser:
        with st.expander("🗂️ Database Structure Browser", expanded=True):
            st.markdown("### Available Database Paths")
            st.caption("Click any path to copy it")
            
            # Create tabs for each main object
            tabs = st.tabs(list(DB_OBJECTS.keys()))
            
            for i, (obj_name, tab) in enumerate(zip(DB_OBJECTS.keys(), tabs)):
                with tab:
                    for sub_obj, fields in DB_OBJECTS[obj_name].items():
                        if sub_obj:
                            st.markdown(f"**{sub_obj}:**")
                        
                        # Display fields in columns
                        field_cols = st.columns(3)
                        for j, field in enumerate(fields):
                            col_idx = j % 3
                            with field_cols[col_idx]:
                                if sub_obj:
                                    path = f"{obj_name}.{sub_obj}.{field}"
                                else:
                                    path = f"{obj_name}.{field}"
                                
                                if st.button(f"📋 {field}", key=f"copy_{path}", use_container_width=True):
                                    st.code(path, language="text")
    
    # Field mapping interface organized by parts
    st.markdown("### 📝 Field Mappings by Part")
    
    # Get parts to display
    if st.session_state.selected_part == 'All Parts':
        parts_to_show = st.session_state.fields_by_part.items()
    else:
        parts_to_show = [(st.session_state.selected_part, 
                         st.session_state.fields_by_part.get(st.session_state.selected_part, []))]
    
    # Display each part
    for part_name, fields in parts_to_show:
        # Filter fields based on mapping filter
        if st.session_state.mapping_filter == 'mapped':
            display_fields = [f for f in fields if f.is_mapped]
        elif st.session_state.mapping_filter == 'unmapped':
            display_fields = [f for f in fields if not f.is_mapped and not f.to_questionnaire]
        elif st.session_state.mapping_filter == 'questionnaire':
            display_fields = [f for f in fields if f.to_questionnaire]
        else:
            display_fields = fields
        
        if not display_fields:
            continue
        
        # Get part info
        part_info = st.session_state.part_structure.get(part_name, {})
        
        # Part header with stats
        part_mapped = sum(1 for f in fields if f.is_mapped)
        part_quest = sum(1 for f in fields if f.to_questionnaire)
        part_unmapped = len(fields) - part_mapped - part_quest
        
        with st.container():
            st.markdown(f'''
            <div class="part-header">
                <strong>{part_name}</strong> {part_info.get('title', '')} 
                <br>
                <small>Total: {len(fields)} | Mapped: {part_mapped} | Questionnaire: {part_quest} | Unmapped: {part_unmapped}</small>
                <br>
                <small>Pages: {', '.join(map(str, part_info.get('pages', [])))}</small>
            </div>
            ''', unsafe_allow_html=True)
        
        # Display fields for this part
        for idx, field in enumerate(display_fields):
            with st.container():
                st.markdown('<div class="mapping-row">', unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    # Field info
                    display_label = field.field_label
                    if field.item_number:
                        display_label = f"{field.item_number}. {display_label}"
                    
                    st.markdown(f'<div class="field-label">{display_label}</div>', unsafe_allow_html=True)
                    
                    # Build field metadata
                    meta_parts = [
                        f'<span class="field-type">{field.field_type}</span>',
                        f'Field: {field.field_key}',
                        f'Page {field.page}'
                    ]
                    
                    # Only show quest key if it's different from field key
                    if field.to_questionnaire and field.question_key and field.question_key != field.field_key:
                        meta_parts.append(f'Quest: {field.question_key}')
                    
                    st.markdown(f"""
                    <div class="field-meta">
                        {' • '.join(meta_parts)}
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    # Create unique key for this field
                    unique_key = f"{part_name}_{field.field_id}_{idx}"
                    
                    col2a, col2b = st.columns([3, 1])
                    
                    with col2a:
                        # Database mapping dropdown
                        grouped_options = {
                            "Actions": ["-- Select Database Field --", "📋 Move to Questionnaire"],
                            "beneficiary": [],
                            "petitioner": [],
                            "customer": [],
                            "attorney": [],
                            "attorneyLawfirmDetails": [],
                            "case": [],
                            "employment": []
                        }
                        
                        # Group database paths
                        for path in extractor.db_paths:
                            obj_name = path.split('.')[0]
                            if obj_name in grouped_options:
                                grouped_options[obj_name].append(path)
                        
                        # Build flat list with separators
                        options = []
                        for group, items in grouped_options.items():
                            if items:
                                if options:  # Add separator between groups
                                    options.append(f"── {group} ──")
                                options.extend(items)
                        
                        # Current selection
                        if field.is_mapped and field.db_mapping:
                            current_value = field.db_mapping
                        elif field.to_questionnaire:
                            current_value = "📋 Move to Questionnaire"
                        else:
                            # Try to get suggestion
                            suggestion = extractor.suggest_mapping(field)
                            current_value = suggestion if suggestion else "-- Select Database Field --"
                        
                        # Find index
                        try:
                            current_index = options.index(current_value)
                        except ValueError:
                            current_index = 0
                        
                        selected = st.selectbox(
                            "Database Mapping",
                            options,
                            index=current_index,
                            key=f"map_{unique_key}",
                            label_visibility="collapsed"
                        )
                        
                        # Handle selection
                        if selected != current_value and not selected.startswith("──"):
                            if selected == "📋 Move to Questionnaire":
                                field.to_questionnaire = True
                                field.is_mapped = False
                                field.db_mapping = None
                            elif selected != "-- Select Database Field --":
                                field.db_mapping = selected
                                field.is_mapped = True
                                field.to_questionnaire = False
                            st.rerun()
                    
                    with col2b:
                        # Quick questionnaire toggle
                        if st.button("📋", key=f"quest_btn_{unique_key}", 
                                   help="Quick add to questionnaire",
                                   use_container_width=True):
                            field.to_questionnaire = True
                            field.is_mapped = False
                            field.db_mapping = None
                            st.rerun()
                
                with col3:
                    # Status
                    status = field.get_status()
                    if "Mapped" in status:
                        badge_class = "status-mapped"
                    elif "Questionnaire" in status:
                        badge_class = "status-questionnaire"
                    else:
                        badge_class = "status-unmapped"
                    
                    st.markdown(f'<span class="status-badge {badge_class}">{status}</span>', 
                              unsafe_allow_html=True)
                
                st.markdown('</div>', unsafe_allow_html=True)
        
        # Add spacing between parts
        st.markdown("<br>", unsafe_allow_html=True)

def main():
    """Main application"""
    st.markdown("# 🤖 USCIS Form Reader Pro")
    st.markdown("### Complete PDF Form Field Extraction & Mapping Solution")
    
    # Initialize extractor
    extractor = FieldExtractor()
    
    # Sidebar
    with st.sidebar:
        st.markdown("## ⚙️ Settings")
        st.session_state.debug_mode = st.checkbox("Debug Mode", value=False)
        
        if st.session_state.pdf_processed:
            st.markdown("---")
            st.markdown("### 📊 Statistics")
            stats = st.session_state.extraction_stats
            st.metric("Total Pages", stats.get('total_pages', 0))
            st.metric("Total Parts", stats.get('total_parts', 0))
            st.metric("Total Fields", stats.get('total_fields', 0))
            st.metric("Extraction Time", f"{stats.get('extraction_time', 0):.2f}s")
            
            if stats.get('errors'):
                st.warning(f"{len(stats['errors'])} errors occurred")
                with st.expander("View Errors"):
                    for error in stats['errors']:
                        st.text(error)
            
            # Field summary
            total = len(st.session_state.fields)
            mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
            quest = sum(1 for f in st.session_state.fields if f.to_questionnaire)
            
            st.markdown("---")
            st.markdown("### 📈 Mapping Progress")
            st.metric("Mapped to DB", f"{mapped} ({mapped/total*100:.1f}%)")
            st.metric("In Questionnaire", f"{quest} ({quest/total*100:.1f}%)")
            st.metric("Unmapped", f"{total - mapped - quest}")
            
            # Progress bar
            progress = (mapped + quest) / total if total > 0 else 0
            st.progress(progress)
            
            # Part breakdown
            st.markdown("---")
            st.markdown("### 📑 Parts Overview")
            for part_name, part_info in st.session_state.part_structure.items():
                fields = st.session_state.fields_by_part.get(part_name, [])
                mapped = sum(1 for f in fields if f.is_mapped)
                quest = sum(1 for f in fields if f.to_questionnaire)
                st.caption(f"{part_name}: {len(fields)} fields ({mapped} mapped, {quest} quest)")
    
    # Main tabs
    tab1, tab2, tab3 = st.tabs(["📤 Upload & Extract", "🎯 Map Fields", "📥 Export & Download"])
    
    with tab1:
        st.markdown("## Upload USCIS PDF Form")
        
        uploaded_file = st.file_uploader(
            "Choose a USCIS PDF form",
            type=['pdf'],
            help="Upload any fillable USCIS form (I-90, I-129, G-28, etc.)",
            key="pdf_uploader"
        )
        
        if uploaded_file:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                if st.button("🚀 Extract Fields by Parts", type="primary", use_container_width=True):
                    with st.spinner("Analyzing PDF structure and extracting fields by parts..."):
                        if extractor.extract_from_pdf(uploaded_file):
                            st.success(f"""
                            ✅ Successfully extracted {len(st.session_state.fields)} fields from {st.session_state.form_info.get('form_number', 'form')}!
                            
                            Found {len(st.session_state.fields_by_part)} parts with fields.
                            """)
                            
                            # Show extraction summary
                            with st.expander("📊 Extraction Summary", expanded=True):
                                for part_name, fields in st.session_state.fields_by_part.items():
                                    part_info = st.session_state.part_structure.get(part_name, {})
                                    
                                    st.write(f"**{part_name}** {part_info.get('title', '')}")
                                    st.write(f"- Fields: {len(fields)}")
                                    st.write(f"- Pages: {', '.join(map(str, part_info.get('pages', [])))}")
                                    
                                    # Field type breakdown
                                    types = defaultdict(int)
                                    for field in fields:
                                        types[field.field_type] += 1
                                    
                                    type_summary = ", ".join([f"{count} {ftype}" for ftype, count in types.items()])
                                    st.caption(f"Field types: {type_summary}")
                                    st.divider()
            
            with col2:
                if st.session_state.pdf_processed:
                    if st.button("🔄 Reset", type="secondary", use_container_width=True):
                        # Clear all session state
                        for key in list(st.session_state.keys()):
                            if key != 'debug_mode':
                                del st.session_state[key]
                        extractor.init_session_state()
                        st.rerun()
    
    with tab2:
        if not st.session_state.pdf_processed:
            st.info("👆 Please upload and extract a PDF form first.")
        else:
            render_mapping_interface(extractor)
    
    with tab3:
        if not st.session_state.pdf_processed:
            st.info("👆 Please upload and extract a PDF form first.")
        else:
            st.markdown("## 📥 Export & Download")
            
            # Summary
            total = len(st.session_state.fields)
            mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
            quest = sum(1 for f in st.session_state.fields if f.to_questionnaire)
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Fields", total)
            col2.metric("Mapped to Database", mapped)
            col3.metric("In Questionnaire", quest)
            
            st.markdown("---")
            
            # Export options
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 📄 TypeScript Export")
                st.markdown("Database mappings for your application")
                
                ts_code = extractor.generate_typescript()
                
                st.download_button(
                    label="⬇️ Download TypeScript File",
                    data=ts_code,
                    file_name=f"{st.session_state.form_info.get('form_number', 'form')}.ts",
                    mime="text/typescript",
                    use_container_width=True
                )
                
                with st.expander("Preview TypeScript"):
                    st.code(ts_code, language="typescript")
            
            with col2:
                st.markdown("### 📋 JSON Export")
                st.markdown("Questionnaire configuration")
                
                json_code = extractor.generate_json()
                
                st.download_button(
                    label="⬇️ Download JSON File",
                    data=json_code,
                    file_name=f"{st.session_state.form_info.get('form_number', 'form')}-questionnaire.json",
                    mime="application/json",
                    use_container_width=True
                )
                
                with st.expander("Preview JSON"):
                    st.code(json_code, language="json")
            
            # Combined export
            st.markdown("---")
            if st.button("📦 Download Both Files", type="primary", use_container_width=True):
                st.markdown("### Downloads Ready:")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button(
                        "TypeScript (.ts)",
                        extractor.generate_typescript(),
                        f"{st.session_state.form_info.get('form_number', 'form')}.ts",
                        mime="text/typescript"
                    )
                with col2:
                    st.download_button(
                        "JSON (.json)",
                        extractor.generate_json(),
                        f"{st.session_state.form_info.get('form_number', 'form')}-questionnaire.json",
                        mime="application/json"
                    )

if __name__ == "__main__":
    main()
