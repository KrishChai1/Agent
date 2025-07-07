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

# Try to import openai - make it optional
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Configure page
st.set_page_config(
    page_title="USCIS Form Reader Pro",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Modern clean CSS (same as before)
st.markdown("""
<style>
    /* Clean modern theme */
    .stApp {
        background: #ffffff;
    }
    
    .main .block-container {
        padding: 2rem 3rem;
        max-width: 1600px;
    }
    
    /* Clean cards */
    div[data-testid="stVerticalBlock"] > div:has(> div > div > h2),
    div[data-testid="stVerticalBlock"] > div:has(> div > div > h3) {
        background: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 10px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    
    /* Clean metrics */
    [data-testid="metric-container"] {
        background: #ffffff;
        border: 1px solid #e9ecef;
        border-radius: 8px;
        padding: 1.5rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    
    [data-testid="metric-value"] {
        font-size: 2.5rem;
        font-weight: 600;
        color: #2c3e50;
    }
    
    /* Modern buttons */
    .stButton > button {
        background: #007bff;
        color: white;
        border: none;
        padding: 0.6rem 1.5rem;
        border-radius: 6px;
        font-weight: 500;
        transition: all 0.2s;
    }
    
    .stButton > button:hover {
        background: #0056b3;
        transform: translateY(-1px);
        box-shadow: 0 4px 8px rgba(0,123,255,0.3);
    }
    
    /* Success button */
    div[data-testid="stButton"] button[kind="primary"] {
        background: #28a745;
    }
    
    div[data-testid="stButton"] button[kind="primary"]:hover {
        background: #218838;
    }
    
    /* Headers */
    h1 {
        color: #2c3e50;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    
    h2 {
        color: #34495e;
        font-size: 1.75rem;
        font-weight: 600;
        margin-bottom: 1rem;
        border-bottom: 2px solid #007bff;
        padding-bottom: 0.5rem;
    }
    
    h3 {
        color: #495057;
        font-size: 1.25rem;
        font-weight: 600;
    }
    
    /* Field containers */
    .field-row {
        background: #ffffff;
        border: 1px solid #e9ecef;
        border-radius: 6px;
        padding: 1rem;
        margin-bottom: 0.75rem;
        transition: all 0.2s;
    }
    
    .field-row:hover {
        border-color: #007bff;
        box-shadow: 0 2px 8px rgba(0,123,255,0.1);
    }
</style>
""", unsafe_allow_html=True)

# Database Structure - Comprehensive mapping
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
        "HomeAddress": ["addressStreet", "addressCity", "addressState", "addressZip", 
                       "addressCountry", "addressNumber", "addressType"],
        "ForeignAddress": ["addressStreet", "addressCity", "addressState", "addressZip", 
                          "addressCountry", "addressNumber", "addressType"],
        "ContactInfo": ["daytimeTelephoneNumber", "mobileTelephoneNumber", "emailAddress",
                       "workPhone", "faxNumber"],
        "PassportDetails": {"Passport": ["passportNumber", "passportIssueCountry", 
                                        "passportIssueDate", "passportExpiryDate"]},
        "VisaDetails": {"Visa": ["currentNonimmigrantStatus", "dateStatusExpires", "visaNumber",
                                "visaStatus", "visaConsulateCity", "visaConsulateCountry",
                                "f1SevisNumber", "f1OptEadNumber"]},
        "I94Details": {"I94": ["formI94ArrivalDepartureRecordNumber", "dateOfLastArrival",
                              "i94Number", "i94ArrivalDate", "i94ExpiryDate"]},
        "EducationDetails": {"BeneficiaryEducation": ["majorFieldOfStudy", "degreeType", 
                                                      "universityName", "graduationDate"]}
    },
    "petitioner": {
        "": ["familyName", "givenName", "middleName", "companyOrOrganizationName"],
        "ContactInfo": ["daytimeTelephoneNumber", "mobileTelephoneNumber", "emailAddress"],
        "Address": ["addressStreet", "addressCity", "addressState", "addressZip", "addressCountry"]
    },
    "customer": {
        "": ["customer_name", "customer_tax_id", "customer_type_of_business", 
             "customer_year_established", "customer_gross_annual_income", 
             "customer_net_annual_income", "customer_total_employees",
             "nonprofit_research_organization", "guam_cnmi_cap_exemption"],
        "SignatoryInfo": ["signatory_first_name", "signatory_last_name", "signatory_middle_name",
                         "signatory_job_title", "signatory_work_phone", "signatory_email",
                         "signatory_email_id"],
        "Address": ["address_street", "address_city", "address_state", "address_zip", 
                   "address_country", "address_number", "address_type"]
    },
    "attorney": {
        "attorneyInfo": ["firstName", "lastName", "middleName", "barNumber",
                        "workPhone", "emailAddress", "faxNumber"],
        "address": ["addressStreet", "addressCity", "addressState", "addressZip",
                   "addressCountry", "addressNumber", "addressType"]
    },
    "attorneyLawfirmDetails": {
        "lawfirmDetails": ["lawFirmName", "lawFirmEIN"]
    },
    "lca": {
        "Lca": ["lcaNumber", "lcaStartDate", "lcaEndDate", "lcaPositionJobTitle",
               "lcaGrossSalary", "lcaWageUnit", "inhouseProject", "endClientName",
               "thirdParty"],
        "WorkLocation": ["addressStreet", "addressCity", "addressState", "addressZip"],
        "secAddresses": ["addressStreet", "addressCity", "addressState", "addressZip",
                        "addressNumber", "addressType"]
    },
    "case": {
        "": ["caseType", "caseSubType", "h1bRegistrationNumber", "h1BPetitionType",
            "requestedAction"]
    },
    "h1b": {
        "": ["h1bReceiptNumber", "h1bRegistrationNumber"]
    },
    "employment": {
        "": ["employment", "temporary", "employerName", "employerDate"]
    }
}

@dataclass
class PDFField:
    """Represents a unique field from PDF"""
    widget_name: str
    field_id: str
    part_number: int
    part_name: str  # Added to store the actual part name
    field_label: str
    field_type: str
    page: int
    value: str = ""
    db_mapping: Optional[str] = None
    is_mapped: bool = False
    to_questionnaire: bool = False
    ai_suggestion: Optional[str] = None
    confidence: float = 0.0
    
    def __hash__(self):
        return hash(self.widget_name)
    
    def __eq__(self, other):
        if isinstance(other, PDFField):
            return self.widget_name == other.widget_name
        return False
    
    def get_status(self) -> str:
        if self.is_mapped:
            return "✅ Mapped"
        elif self.to_questionnaire:
            return "📋 Questionnaire"
        else:
            return "⚪ Unmapped"
    
    def get_status_color(self) -> str:
        if self.is_mapped:
            return "success"
        elif self.to_questionnaire:
            return "warning"
        else:
            return "info"

class AIFieldMapper:
    """AI-powered field mapping assistant"""
    
    def __init__(self):
        # Get API key from secrets
        self.api_key = None
        try:
            self.api_key = st.secrets["OPENAI_API_KEY"]
        except:
            pass
        
        if self.api_key and OPENAI_AVAILABLE:
            openai.api_key = self.api_key
        self.mapping_cache = {}
    
    def has_api_key(self) -> bool:
        """Check if API key is available"""
        return bool(self.api_key) and OPENAI_AVAILABLE
    
    def get_field_mapping_suggestion(self, field: PDFField, db_paths: List[str]) -> Tuple[Optional[str], float]:
        """Get AI suggestion for field mapping"""
        if not self.has_api_key():
            return None, 0.0
        
        # Check cache
        cache_key = f"{field.field_label}_{field.field_type}"
        if cache_key in self.mapping_cache:
            return self.mapping_cache[cache_key]
        
        try:
            # Prepare context
            db_paths_text = "\n".join(db_paths[:50])  # Limit to prevent token overflow
            
            prompt = f"""Given a form field, suggest the best database path mapping.

Field Information:
- Label: {field.field_label}
- Type: {field.field_type}
- Widget Name: {field.widget_name}
- Part: {field.part_name}

Available Database Paths (partial list):
{db_paths_text}

Instructions:
1. If the field clearly matches a database path, return that exact path
2. If no good match exists, return "questionnaire"
3. Only return the path or "questionnaire", nothing else
4. Be precise - the path must exist in the list

Response format: <path>|<confidence>
Where confidence is 0.0 to 1.0

Example: beneficiary.Beneficiary.beneficiaryFirstName|0.95"""

            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=100
            )
            
            result = response.choices[0].message.content.strip()
            
            # Parse response
            if "|" in result:
                suggestion, confidence = result.split("|")
                confidence = float(confidence)
            else:
                suggestion = result
                confidence = 0.5
            
            # Validate suggestion
            if suggestion != "questionnaire" and suggestion not in db_paths:
                suggestion = None
                confidence = 0.0
            
            # Cache result
            self.mapping_cache[cache_key] = (suggestion, confidence)
            return suggestion, confidence
            
        except Exception as e:
            st.warning(f"AI suggestion failed: {str(e)}")
            return None, 0.0

class USCISExtractor:
    """Enhanced USCIS form extractor with better part detection"""
    
    def __init__(self):
        self.init_session_state()
        self.db_paths = self._build_db_paths()
        self.ai_mapper = AIFieldMapper()
        self.seen_fields = set()  # Track unique fields
        self.debug_mode = False  # Add debug mode
    
    def init_session_state(self):
        """Initialize session state"""
        if 'fields' not in st.session_state:
            st.session_state.fields = []
        if 'fields_by_part' not in st.session_state:
            st.session_state.fields_by_part = OrderedDict()
        if 'form_info' not in st.session_state:
            st.session_state.form_info = {}
        if 'pdf_processed' not in st.session_state:
            st.session_state.pdf_processed = False
        if 'ai_suggestions' not in st.session_state:
            st.session_state.ai_suggestions = {}
        if 'show_summary' not in st.session_state:
            st.session_state.show_summary = False
        if 'extraction_log' not in st.session_state:
            st.session_state.extraction_log = []
    
    def _build_db_paths(self) -> List[str]:
        """Build database paths"""
        paths = []
        for obj_name, structure in DB_OBJECTS.items():
            for key, fields in structure.items():
                if isinstance(fields, list):
                    prefix = f"{obj_name}.{key}." if key else f"{obj_name}."
                    paths.extend([prefix + field for field in fields])
                elif isinstance(fields, dict):
                    for sub_key, sub_fields in fields.items():
                        prefix = f"{obj_name}.{key}.{sub_key}."
                        paths.extend([prefix + field for field in sub_fields])
        return sorted(paths)
    
    def extract_pdf(self, pdf_file) -> bool:
        """Extract fields from PDF with improved part detection"""
        try:
            # Reset state
            st.session_state.fields = []
            st.session_state.fields_by_part = OrderedDict()
            st.session_state.extraction_log = []
            self.seen_fields.clear()
            
            # Read PDF
            pdf_bytes = pdf_file.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            # Detect form type
            st.session_state.form_info = self._detect_form_type(doc)
            
            # Extract all fields with improved part detection
            all_fields = []
            progress_bar = st.progress(0)
            
            # First, scan all pages to build a part mapping
            part_mapping = self._build_part_mapping(doc)
            
            # Log the part mapping for debugging
            self._log(f"Part mapping: {part_mapping}")
            
            # Extract fields with accurate part information
            for page_num in range(len(doc)):
                progress_bar.progress((page_num + 1) / len(doc))
                page = doc[page_num]
                
                # Get part info for this page
                part_info = part_mapping.get(page_num, {'number': 1, 'name': 'Part 1', 'title': 'General Information'})
                
                # Skip attorney/preparer sections
                if self._is_skippable_section(part_info.get('title', '')):
                    self._log(f"Skipping page {page_num + 1}: {part_info.get('title', '')}")
                    continue
                
                # Get widgets
                widgets = page.widgets()
                widget_count = len(widgets) if widgets else 0
                self._log(f"Page {page_num + 1}: Found {widget_count} widgets in {part_info['name']}")
                
                if widgets:
                    for widget in widgets:
                        if widget and hasattr(widget, 'field_name') and widget.field_name:
                            # Check if we've seen this field
                            if widget.field_name not in self.seen_fields:
                                self.seen_fields.add(widget.field_name)
                                
                                # Create field
                                field = self._create_field(
                                    widget, 
                                    part_info['number'],
                                    part_info['name'],
                                    page_num + 1
                                )
                                
                                # Auto-categorize checkboxes/radios to questionnaire
                                if field.field_type in ['checkbox', 'radio', 'button']:
                                    field.to_questionnaire = True
                                
                                all_fields.append(field)
                                self._log(f"  - Field: {field.field_label} ({field.field_type})")
            
            progress_bar.empty()
            doc.close()
            
            # Sort fields
            all_fields.sort(key=lambda f: (f.part_number, f.page, f.field_label))
            st.session_state.fields = all_fields
            
            # Group by part
            for field in all_fields:
                part_key = field.part_name
                if part_key not in st.session_state.fields_by_part:
                    st.session_state.fields_by_part[part_key] = []
                st.session_state.fields_by_part[part_key].append(field)
            
            self._log(f"Total fields extracted: {len(all_fields)}")
            self._log(f"Parts found: {list(st.session_state.fields_by_part.keys())}")
            
            st.session_state.pdf_processed = True
            return True
            
        except Exception as e:
            st.error(f"❌ Error processing PDF: {str(e)}")
            import traceback
            st.code(traceback.format_exc())
            return False
    
    def _build_part_mapping(self, doc) -> Dict[int, dict]:
        """Build a comprehensive mapping of pages to parts/sections"""
        part_mapping = {}
        current_part = {'number': 1, 'name': 'Part 1', 'title': 'General Information'}
        
        # Pattern to match both "Part X" and "Section X"
        part_pattern = r'(?:Part|Section)\s+(\d+)[\.\s\-:]*([^\n]*)'
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            page_text = page.get_text()
            
            # Look for part/section indicators
            matches = list(re.finditer(part_pattern, page_text, re.IGNORECASE))
            
            if matches:
                # Found part/section on this page
                for match in matches:
                    part_type = "Section" if "section" in match.group(0).lower() else "Part"
                    part_num = int(match.group(1))
                    part_title = match.group(2).strip() if match.group(2) else ""
                    
                    # Clean up the title
                    part_title = re.sub(r'[\.\s]+$', '', part_title)
                    if part_title and not part_title.endswith('.'):
                        part_title = part_title.split('\n')[0].strip()
                    
                    current_part = {
                        'number': part_num,
                        'name': f"{part_type} {part_num}",
                        'title': part_title or f"{part_type} {part_num}"
                    }
                    break  # Use the first match
            
            # Assign current part to this page
            part_mapping[page_num] = current_part.copy()
        
        return part_mapping
    
    def _is_skippable_section(self, title: str) -> bool:
        """Check if section should be skipped"""
        skip_keywords = [
            'attorney', 'preparer', 'interpreter', 
            'signature of the person preparing',
            'declaration', 'certification',
            'person preparing form',
            'paid preparer',
            'additional information'  # Often just free text areas
        ]
        title_lower = title.lower()
        return any(keyword in title_lower for keyword in skip_keywords)
    
    def _detect_form_type(self, doc) -> dict:
        """Detect form type from PDF"""
        first_page_text = doc[0].get_text().upper()
        
        forms = {
            'I-90': 'Application to Replace Permanent Resident Card',
            'I-129': 'Petition for a Nonimmigrant Worker',
            'I-130': 'Petition for Alien Relative',
            'I-140': 'Immigrant Petition for Alien Worker',
            'I-485': 'Application to Register Permanent Residence',
            'I-526': 'Immigrant Petition by Alien Investor',
            'I-539': 'Application to Extend/Change Nonimmigrant Status',
            'I-751': 'Petition to Remove Conditions on Residence',
            'I-765': 'Application for Employment Authorization',
            'I-824': 'Application for Action on an Approved Application',
            'N-400': 'Application for Naturalization',
            'N-600': 'Application for Certificate of Citizenship',
            'N-565': 'Application for Replacement Naturalization/Citizenship Document',
            'G-28': 'Notice of Entry of Appearance as Attorney or Accredited Representative'
        }
        
        for form_num, title in forms.items():
            if form_num in first_page_text:
                return {
                    'form_number': form_num,
                    'form_title': title,
                    'pages': len(doc)
                }
        
        return {
            'form_number': 'Unknown',
            'form_title': 'Unknown USCIS Form',
            'pages': len(doc)
        }
    
    def _create_field(self, widget, part_num: int, part_name: str, page: int) -> PDFField:
        """Create field object from widget"""
        field_name = widget.field_name
        field_type = self._get_field_type(widget.field_type)
        
        # Generate unique field ID
        field_hash = hashlib.md5(f"{field_name}_{part_num}_{page}".encode()).hexdigest()[:8]
        field_id = f"P{part_num}_{field_hash}"
        
        # Extract human-readable label
        label = self._extract_smart_label(field_name)
        
        return PDFField(
            widget_name=field_name,
            field_id=field_id,
            part_number=part_num,
            part_name=part_name,
            field_label=label,
            field_type=field_type,
            page=page,
            value=widget.field_value or ''
        )
    
    def _get_field_type(self, widget_type: int) -> str:
        """Map widget type to field type"""
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
    
    def _extract_smart_label(self, field_name: str) -> str:
        """Extract readable label with smart parsing"""
        # Remove common prefixes
        clean = re.sub(r'form\d*\[?\d*\]?\.|#subform\[?\d*\]?\.|Page\d+\[?\d*\]?\.', '', field_name)
        clean = re.sub(r'Part\d+\[?\d*\]?\.', '', clean)
        clean = re.sub(r'Section\d+\[?\d*\]?\.', '', clean)
        clean = re.sub(r'\[[\d\]]+', '', clean)
        clean = clean.strip('._[]#')
        
        # Common field mappings (expanded)
        label_map = {
            'familyname': 'Family Name (Last Name)',
            'lastname': 'Last Name',
            'surname': 'Surname',
            'givenname': 'Given Name (First Name)',
            'firstname': 'First Name',
            'middlename': 'Middle Name',
            'middleinitial': 'Middle Initial',
            'anumber': 'Alien Registration Number (A-Number)',
            'alienregistration': 'Alien Registration Number',
            'uscisaccount': 'USCIS Online Account Number',
            'uscisaccountnumber': 'USCIS Online Account Number',
            'dateofbirth': 'Date of Birth',
            'dob': 'Date of Birth',
            'birthdate': 'Birth Date',
            'ssn': 'Social Security Number',
            'socialsecurity': 'Social Security Number',
            'passport': 'Passport Number',
            'passportnumber': 'Passport Number',
            'street': 'Street Address',
            'streetaddress': 'Street Address',
            'streetnumberandname': 'Street Number and Name',
            'address': 'Address',
            'city': 'City or Town',
            'state': 'State',
            'province': 'Province',
            'zip': 'ZIP Code',
            'zipcode': 'ZIP Code',
            'postalcode': 'Postal Code',
            'country': 'Country',
            'email': 'Email Address',
            'emailaddress': 'Email Address',
            'phone': 'Phone Number',
            'telephone': 'Telephone Number',
            'mobile': 'Mobile Number',
            'cell': 'Cell Phone',
            'daytimephone': 'Daytime Phone Number',
            'daytimetelephonenumber': 'Daytime Telephone Number',
            'gender': 'Gender',
            'sex': 'Sex',
            'maritalstatus': 'Marital Status',
            'citizenship': 'Country of Citizenship',
            'nationality': 'Nationality',
            'countryofbirth': 'Country of Birth',
            'placeofbirth': 'Place of Birth',
            'apt': 'Apartment',
            'ste': 'Suite',
            'flr': 'Floor',
            'receiptnumber': 'Receipt Number',
            'barNumber': 'Bar Number',
            'lawfirm': 'Law Firm',
            'organization': 'Organization'
        }
        
        # Check for exact matches
        clean_lower = clean.lower().replace('_', '').replace('-', '').replace(' ', '')
        
        for key, label in label_map.items():
            if key in clean_lower:
                return label
        
        # Smart case conversion
        # Handle camelCase
        label = re.sub(r'([a-z])([A-Z])', r'\1 \2', clean)
        # Handle underscores and hyphens
        label = label.replace('_', ' ').replace('-', ' ')
        # Remove extra spaces
        label = ' '.join(label.split())
        # Title case
        label = label.title()
        
        # Fix common abbreviations
        label = label.replace('Dob', 'Date of Birth')
        label = label.replace('Ssn', 'SSN')
        label = label.replace('Ein', 'EIN')
        label = label.replace('Uscis', 'USCIS')
        label = label.replace('Ste', 'Suite')
        label = label.replace('Apt', 'Apartment')
        label = label.replace('Flr', 'Floor')
        
        return label
    
    def _log(self, message: str):
        """Add message to extraction log"""
        if 'extraction_log' in st.session_state:
            st.session_state.extraction_log.append(message)
    
    def generate_typescript(self) -> str:
        """Generate TypeScript mapping file"""
        fields = st.session_state.fields
        form_name = st.session_state.form_info.get('form_number', 'Form').replace('-', '')
        
        # Group fields by mapping type
        db_fields = defaultdict(list)
        quest_fields = []
        
        for field in fields:
            if field.is_mapped and field.db_mapping:
                obj = field.db_mapping.split('.')[0]
                db_fields[obj].append(field)
            elif field.to_questionnaire:
                quest_fields.append(field)
        
        # Generate TypeScript
        ts = f"""// {st.session_state.form_info.get('form_number')} Field Mappings
// Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
// Total Fields: {len(fields)}
// Mapped: {sum(1 for f in fields if f.is_mapped)}
// Questionnaire: {len(quest_fields)}

export const {form_name} = {{
  formname: "{form_name}",
  formTitle: "{st.session_state.form_info.get('form_title', '')}",
  """
        
        # Add database mappings
        for obj, obj_fields in sorted(db_fields.items()):
            ts += f'\n  {obj}Data: {{\n'
            for field in sorted(obj_fields, key=lambda f: f.field_label):
                suffix = ":TextBox" if field.field_type == "text" else f":{field.field_type.capitalize()}Box"
                ts += f'    "{field.field_id}": "{field.db_mapping}{suffix}",\n'
            ts += '  },\n'
        
        # Add questionnaire data
        if quest_fields:
            ts += '\n  questionnaireData: {\n'
            for field in sorted(quest_fields, key=lambda f: (f.part_number, f.page)):
                ts += f'    "{field.field_id}": {{\n'
                ts += f'      description: "{field.field_label}",\n'
                ts += f'      type: "{field.field_type}",\n'
                ts += f'      part: {field.part_number},\n'
                ts += f'      partName: "{field.part_name}",\n'
                ts += f'      page: {field.page},\n'
                if field.value:
                    ts += f'      defaultValue: "{field.value}",\n'
                ts += '    },\n'
            ts += '  },\n'
        
        ts += """
  defaultData: {},
  conditionalData: {},
  validationRules: {},
  pdfName: \"""" + st.session_state.form_info.get('form_number', 'Unknown') + """",
};

export default """ + form_name + ";"
        
        return ts
    
    def generate_json(self) -> str:
        """Generate JSON configuration for all questionnaire fields including unmapped"""
        # Get all fields that should be in questionnaire
        quest_fields = []
        for field in st.session_state.fields:
            # Include if explicitly marked for questionnaire OR if it's a checkbox/radio/button OR if unmapped
            if field.to_questionnaire or field.field_type in ['checkbox', 'radio', 'button'] or (not field.is_mapped):
                quest_fields.append(field)
        
        # Group by parts
        parts = defaultdict(list)
        for field in quest_fields:
            parts[field.part_name].append(field)
        
        # Build JSON structure
        data = {
            "form": st.session_state.form_info.get('form_number'),
            "title": st.session_state.form_info.get('form_title'),
            "generated": datetime.now().isoformat(),
            "totalFields": len(st.session_state.fields),
            "mappedFields": sum(1 for f in st.session_state.fields if f.is_mapped),
            "questionnaireFields": len(quest_fields),
            "controls": []
        }
        
        for part_name in sorted(parts.keys(), key=lambda x: int(re.search(r'\d+', x).group() if re.search(r'\d+', x) else 0)):
            part_fields = parts[part_name]
            part_control = {
                "group_name": part_name,
                "group_key": part_name.lower().replace(' ', '_'),
                "field_count": len(part_fields),
                "group_definition": []
            }
            
            for field in sorted(part_fields, key=lambda f: (f.page, f.field_label)):
                field_def = {
                    "id": field.field_id,
                    "name": field.widget_name,
                    "label": field.field_label,
                    "type": field.field_type,
                    "page": field.page,
                    "required": field.field_type == "text",  # Text fields are required by default
                    "validators": {
                        "required": field.field_type == "text"
                    },
                    "options": [],  # For dropdowns/radios if needed
                    "style": {
                        "col": "12" if field.field_type in ["signature", "text"] and len(field.field_label) > 30 else "6"
                    }
                }
                
                # Add field type specific properties
                if field.field_type == "checkbox":
                    field_def["defaultChecked"] = False
                elif field.field_type == "dropdown":
                    field_def["options"] = ["Option 1", "Option 2", "Option 3"]  # Placeholder
                
                if field.value:
                    field_def["defaultValue"] = field.value
                
                part_control["group_definition"].append(field_def)
            
            data["controls"].append(part_control)
        
        return json.dumps(data, indent=2)

def main():
    """Main application"""
    extractor = USCISExtractor()
    
    # Header
    st.markdown("# 🤖 USCIS Form Reader Pro")
    st.markdown("### AI-Powered PDF Form Field Extraction & Mapping")
    
    # Main content area
    tab1, tab2, tab3, tab4 = st.tabs(["📤 Upload & Extract", "🎯 Map Fields", "📥 Export", "🐛 Debug"])
    
    with tab1:
        col1, col2 = st.columns([3, 2])
        
        with col1:
            st.markdown("## Upload USCIS Form")
            
            uploaded_file = st.file_uploader(
                "Select a USCIS PDF form",
                type=['pdf'],
                help="Upload any fillable USCIS form (I-90, I-129, I-485, G-28, etc.)"
            )
            
            if uploaded_file:
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("🚀 Extract Fields", type="primary", use_container_width=True):
                        with st.spinner("Extracting fields..."):
                            if extractor.extract_pdf(uploaded_file):
                                st.success(f"✅ Extracted {len(st.session_state.fields)} unique fields!")
                                st.balloons()
                with col_b:
                    if st.session_state.pdf_processed:
                        if st.button("🔄 Reset", use_container_width=True):
                            for key in ['fields', 'fields_by_part', 'form_info', 'pdf_processed', 'ai_suggestions', 'show_summary']:
                                if key in st.session_state:
                                    del st.session_state[key]
                            st.rerun()
        
        with col2:
            if st.session_state.pdf_processed:
                st.markdown("## Form Details")
                
                # Form info card
                form_info = st.session_state.form_info
                st.info(f"""
                **Form:** {form_info.get('form_number', 'Unknown')}  
                **Title:** {form_info.get('form_title', 'Unknown')}  
                **Pages:** {form_info.get('pages', 0)}  
                **Fields:** {len(st.session_state.fields)}  
                **Parts:** {len(st.session_state.fields_by_part)}
                """)
                
                # Show parts found
                st.markdown("### Parts Found")
                for part_name in st.session_state.fields_by_part.keys():
                    field_count = len(st.session_state.fields_by_part[part_name])
                    st.caption(f"• {part_name} ({field_count} fields)")
                
                # Quick stats
                total = len(st.session_state.fields)
                mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
                quest = sum(1 for f in st.session_state.fields if f.to_questionnaire and not f.is_mapped)
                
                st.markdown("### Mapping Progress")
                progress = (mapped + quest) / total if total > 0 else 0
                st.progress(progress)
                st.caption(f"{int(progress * 100)}% Complete")
                
                # Metrics
                m1, m2, m3 = st.columns(3)
                m1.metric("Mapped", mapped, f"{mapped/total*100:.0f}%")
                m2.metric("Questionnaire", quest, f"{quest/total*100:.0f}%")
                m3.metric("Unmapped", total - mapped - quest)
    
    with tab2:
        if not st.session_state.pdf_processed:
            st.info("📤 Please upload and extract a PDF form first.")
        else:
            st.markdown("## Field Mapping Dashboard")
            
            # AI Assistant Section
            with st.container():
                st.markdown("### 🤖 AI Mapping Assistant")
                col1, col2, col3 = st.columns([1, 1, 1])
                
                with col1:
                    if not OPENAI_AVAILABLE:
                        st.error("❌ OpenAI not installed")
                        st.caption("Run: pip install openai")
                    elif extractor.ai_mapper.has_api_key():
                        st.success("✅ AI Ready (API key found)")
                    else:
                        st.warning("⚠️ No API key found in secrets")
                        st.caption("Add OPENAI_API_KEY to secrets.toml")
                
                with col2:
                    if st.button("🎯 AI Auto-Map", type="primary", use_container_width=True, 
                                disabled=not OPENAI_AVAILABLE or not extractor.ai_mapper.has_api_key()):
                        if extractor.ai_mapper.has_api_key():
                            count = extractor.auto_map_with_ai()
                            if count > 0:
                                st.success(f"✨ AI mapped {count} fields with high confidence!")
                            else:
                                st.info("No additional fields could be mapped with high confidence.")
                            st.rerun()
                
                with col3:
                    if st.button("📋 All Unmapped → Questionnaire", use_container_width=True):
                        count = 0
                        for field in st.session_state.fields:
                            if not field.is_mapped and not field.to_questionnaire:
                                field.to_questionnaire = True
                                count += 1
                        if count > 0:
                            st.success(f"Moved {count} fields to questionnaire!")
                            st.rerun()
            
            st.markdown("---")
            
            # Quick Actions Bar
            st.markdown("### ⚡ Quick Actions")
            qa1, qa2, qa3, qa4 = st.columns(4)
            
            with qa1:
                if st.button("✅ Auto-map Simple Fields", use_container_width=True):
                    # Simple pattern matching for common fields
                    count = 0
                    for field in st.session_state.fields:
                        if not field.is_mapped and not field.to_questionnaire and field.field_type == 'text':
                            label_lower = field.field_label.lower()
                            # Try exact matches
                            for db_path in extractor.db_paths:
                                path_end = db_path.split('.')[-1].lower()
                                if (path_end in label_lower.replace(' ', '').replace('-', '') or 
                                    label_lower.replace(' ', '').replace('-', '') in path_end):
                                    field.db_mapping = db_path
                                    field.is_mapped = True
                                    count += 1
                                    break
                    st.success(f"Mapped {count} fields using pattern matching!")
                    st.rerun()
            
            with qa2:
                if st.button("📋 Checkboxes → Questionnaire", use_container_width=True):
                    count = 0
                    for field in st.session_state.fields:
                        if field.field_type in ['checkbox', 'radio', 'button'] and not field.to_questionnaire:
                            field.to_questionnaire = True
                            field.is_mapped = False
                            count += 1
                    st.success(f"Moved {count} checkbox/radio fields to questionnaire!")
                    st.rerun()
            
            with qa3:
                if st.button("🔄 Reset All Mappings", use_container_width=True):
                    for field in st.session_state.fields:
                        field.is_mapped = False
                        field.db_mapping = None
                        field.to_questionnaire = False
                        # Re-auto-assign checkboxes
                        if field.field_type in ['checkbox', 'radio', 'button']:
                            field.to_questionnaire = True
                    st.success("Reset all mappings!")
                    st.rerun()
            
            with qa4:
                if st.button("📊 Show Summary", use_container_width=True):
                    st.session_state.show_summary = not st.session_state.get('show_summary', False)
            
            # Summary Panel
            if st.session_state.get('show_summary', False):
                st.markdown("---")
                st.markdown("### 📊 Mapping Summary")
                
                # Create summary by part
                summary_data = []
                for part_name, fields in st.session_state.fields_by_part.items():
                    mapped = sum(1 for f in fields if f.is_mapped)
                    quest = sum(1 for f in fields if f.to_questionnaire and not f.is_mapped)
                    unmapped = len(fields) - mapped - quest
                    
                    summary_data.append({
                        "Part": part_name,
                        "Total": len(fields),
                        "Mapped": mapped,
                        "Questionnaire": quest,
                        "Unmapped": unmapped,
                        "Complete %": f"{(mapped + quest) / len(fields) * 100:.0f}%"
                    })
                
                df = pd.DataFrame(summary_data)
                st.dataframe(df, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            
            # Filters
            st.markdown("### 🔍 Filter Fields")
            fc1, fc2, fc3, fc4 = st.columns(4)
            
            with fc1:
                search = st.text_input("Search", placeholder="Type to search...")
            with fc2:
                part_filter = st.selectbox(
                    "Part",
                    ["All"] + list(st.session_state.fields_by_part.keys())
                )
            with fc3:
                status_filter = st.selectbox(
                    "Status",
                    ["All", "✅ Mapped", "📋 Questionnaire", "⚪ Unmapped"]
                )
            with fc4:
                type_filter = st.selectbox(
                    "Type",
                    ["All"] + list(set(f.field_type for f in st.session_state.fields))
                )
            
            # Apply filters
            filtered = st.session_state.fields.copy()
            
            if search:
                filtered = [f for f in filtered if search.lower() in f.field_label.lower() or search.lower() in f.widget_name.lower()]
            if part_filter != "All":
                filtered = [f for f in filtered if f.part_name == part_filter]
            if status_filter != "All":
                if "Mapped" in status_filter:
                    filtered = [f for f in filtered if f.is_mapped]
                elif "Questionnaire" in status_filter:
                    filtered = [f for f in filtered if f.to_questionnaire and not f.is_mapped]
                else:
                    filtered = [f for f in filtered if not f.is_mapped and not f.to_questionnaire]
            if type_filter != "All":
                filtered = [f for f in filtered if f.field_type == type_filter]
            
            # Display fields
            st.markdown(f"### 📋 Fields ({len(filtered)} shown)")
            
            if filtered:
                # Group by part
                for part_name in st.session_state.fields_by_part:
                    part_fields = [f for f in filtered if f.part_name == part_name]
                    
                    if part_fields:
                        with st.expander(f"{part_name} ({len(part_fields)} fields)", expanded=True):
                            for field in part_fields:
                                with st.container():
                                    col1, col2, col3 = st.columns([3, 4, 1])
                                    
                                    with col1:
                                        # Field type emoji
                                        type_emoji = {
                                            "text": "📝",
                                            "checkbox": "☑️",
                                            "radio": "⭕",
                                            "dropdown": "📋",
                                            "signature": "✍️",
                                            "button": "🔘",
                                            "list": "📃"
                                        }
                                        emoji = type_emoji.get(field.field_type, "📄")
                                        
                                        st.markdown(f"**{emoji} {field.field_label}**")
                                        st.caption(f"{field.field_type} • Page {field.page} • `{field.widget_name[:30]}...`")
                                        
                                        # Show AI suggestion if available
                                        if field.ai_suggestion and not field.is_mapped:
                                            conf_color = "🟢" if field.confidence > 0.8 else "🟡" if field.confidence > 0.6 else "🔴"
                                            st.caption(f"🤖 AI suggests: {field.ai_suggestion} {conf_color} {field.confidence:.0%}")
                                    
                                    with col2:
                                        if field.field_type == 'text' and not field.to_questionnaire:
                                            # Mapping options
                                            mapping_key = f"mapping_{field.field_id}"
                                            
                                            # Get current mapping
                                            current_mapping = field.db_mapping if field.is_mapped else ""
                                            
                                            # Create options
                                            db_options = [""] + extractor.db_paths
                                            
                                            # Selectbox for database mapping
                                            selected_db = st.selectbox(
                                                "Map to database field",
                                                db_options,
                                                index=db_options.index(current_mapping) if current_mapping in db_options else 0,
                                                key=f"db_{field.field_id}",
                                                placeholder="Select database field...",
                                                label_visibility="collapsed"
                                            )
                                            
                                            # Manual entry option
                                            manual_entry = st.text_input(
                                                "Or enter custom path",
                                                value="" if selected_db else current_mapping,
                                                key=f"manual_{field.field_id}",
                                                placeholder="e.g., beneficiary.custom.fieldName",
                                                label_visibility="collapsed"
                                            )
                                            
                                            # Update mapping
                                            new_mapping = selected_db if selected_db else manual_entry
                                            
                                            if new_mapping != current_mapping:
                                                if new_mapping:
                                                    field.db_mapping = new_mapping
                                                    field.is_mapped = True
                                                    field.to_questionnaire = False
                                                else:
                                                    field.db_mapping = None
                                                    field.is_mapped = False
                                                st.rerun()
                                            
                                            # Move to questionnaire button
                                            if st.button("📋 → Questionnaire", key=f"quest_{field.field_id}"):
                                                field.to_questionnaire = True
                                                field.is_mapped = False
                                                field.db_mapping = None
                                                st.rerun()
                                        else:
                                            # For non-text fields or questionnaire items
                                            include = st.checkbox(
                                                "Include in Questionnaire",
                                                value=field.to_questionnaire,
                                                key=f"q_{field.field_id}",
                                                help="Check to include this field in the questionnaire"
                                            )
                                            if include != field.to_questionnaire:
                                                field.to_questionnaire = include
                                                if include:
                                                    field.is_mapped = False
                                                    field.db_mapping = None
                                                st.rerun()
                                    
                                    with col3:
                                        st.markdown(f"**{field.get_status()}**")
                                
                                st.markdown("---")
            else:
                st.info("No fields match your filters.")
    
    with tab3:
        if not st.session_state.pdf_processed:
            st.info("📤 Please upload and extract a PDF form first.")
        else:
            st.markdown("## Export Options")
            
            st.markdown("ℹ️ **Note:** JSON export automatically includes all checkboxes, radio buttons, and unmapped fields in the questionnaire.")
            
            st.markdown("---")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 📄 TypeScript Export")
                st.markdown("Generate TypeScript mappings for your application")
                
                # Preview stats
                mapped_count = sum(1 for f in st.session_state.fields if f.is_mapped)
                quest_count = sum(1 for f in st.session_state.fields if f.to_questionnaire)
                
                st.info(f"""
                **Will Export:**  
                • {mapped_count} mapped fields  
                • {quest_count} questionnaire fields  
                • All database mappings
                """)
                
                if st.button("🚀 Generate TypeScript", type="primary", use_container_width=True):
                    ts_code = extractor.generate_typescript()
                    
                    st.download_button(
                        "⬇️ Download .ts file",
                        ts_code,
                        f"{st.session_state.form_info.get('form_number', 'form')}.ts",
                        mime="text/typescript",
                        use_container_width=True
                    )
                    
                    with st.expander("Preview TypeScript", expanded=True):
                        st.code(ts_code, language="typescript", line_numbers=True)
            
            with col2:
                st.markdown("### 📋 JSON Export")
                st.markdown("Generate JSON configuration for questionnaires")
                
                # Calculate what will be included
                quest_fields = []
                for field in st.session_state.fields:
                    if field.to_questionnaire or field.field_type in ['checkbox', 'radio', 'button'] or not field.is_mapped:
                        quest_fields.append(field)
                
                explicitly_quest = sum(1 for f in st.session_state.fields if f.to_questionnaire)
                auto_checkboxes = sum(1 for f in st.session_state.fields if f.field_type in ['checkbox', 'radio', 'button'] and not f.to_questionnaire)
                unmapped_text = sum(1 for f in st.session_state.fields if not f.is_mapped and not f.to_questionnaire and f.field_type not in ['checkbox', 'radio', 'button'])
                
                st.info(f"""
                **Will Export to JSON:**  
                • {explicitly_quest} marked for questionnaire  
                • {auto_checkboxes} checkboxes/radios (auto-included)  
                • {unmapped_text} unmapped fields  
                • **Total: {len(quest_fields)} fields**
                """)
                
                if st.button("🚀 Generate JSON", type="primary", use_container_width=True):
                    json_code = extractor.generate_json()
                    
                    st.download_button(
                        "⬇️ Download .json file",
                        json_code,
                        f"{st.session_state.form_info.get('form_number', 'form')}_questionnaire.json",
                        mime="application/json",
                        use_container_width=True
                    )
                    
                    with st.expander("Preview JSON", expanded=True):
                        st.code(json_code, language="json", line_numbers=True)
            
            # Summary and batch export
            st.markdown("---")
            st.markdown("### 📊 Export Summary & Batch Download")
            
            total = len(st.session_state.fields)
            mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
            quest = sum(1 for f in st.session_state.fields if f.to_questionnaire)
            unmapped = total - mapped - quest
            
            # Summary metrics
            sum1, sum2, sum3, sum4 = st.columns(4)
            sum1.metric("Total Fields", total)
            sum2.metric("DB Mapped", f"{mapped} ({mapped/total*100:.0f}%)")
            sum3.metric("Questionnaire", f"{quest} ({quest/total*100:.0f}%)")
            sum4.metric("Unmapped", f"{unmapped} ({unmapped/total*100:.0f}%)")
            
            # Batch export
            if st.button("📦 Download All (TS + JSON + Report)", type="primary", use_container_width=True):
                # Generate all files
                ts_code = extractor.generate_typescript()
                json_code = extractor.generate_json()
                
                # Generate detailed report
                report = f"""USCIS Form Processing Report
=====================================
Form: {st.session_state.form_info.get('form_number')}
Title: {st.session_state.form_info.get('form_title')}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

SUMMARY
-------
Total Fields: {total}
Database Mapped: {mapped} ({mapped/total*100:.1f}%)
Questionnaire: {quest} ({quest/total*100:.1f}%)
Unmapped: {unmapped} ({unmapped/total*100:.1f}%)

FIELD DETAILS BY PART
--------------------
"""
                for part, fields in st.session_state.fields_by_part.items():
                    report += f"\n{part} ({len(fields)} fields)\n"
                    report += "=" * len(part) + "\n\n"
                    
                    # Group by status
                    mapped_fields = [f for f in fields if f.is_mapped]
                    quest_fields = [f for f in fields if f.to_questionnaire and not f.is_mapped]
                    unmapped_fields = [f for f in fields if not f.is_mapped and not f.to_questionnaire]
                    
                    if mapped_fields:
                        report += "MAPPED TO DATABASE:\n"
                        for f in mapped_fields:
                            report += f"  - {f.field_label} [{f.field_type}] → {f.db_mapping}\n"
                        report += "\n"
                    
                    if quest_fields:
                        report += "QUESTIONNAIRE:\n"
                        for f in quest_fields:
                            report += f"  - {f.field_label} [{f.field_type}]\n"
                        report += "\n"
                    
                    if unmapped_fields:
                        report += "UNMAPPED:\n"
                        for f in unmapped_fields:
                            report += f"  - {f.field_label} [{f.field_type}]\n"
                        report += "\n"
                
                # Create download columns
                d1, d2, d3 = st.columns(3)
                
                with d1:
                    st.download_button(
                        "📄 TypeScript",
                        ts_code,
                        f"{st.session_state.form_info.get('form_number')}.ts",
                        mime="text/typescript"
                    )
                
                with d2:
                    st.download_button(
                        "📋 JSON",
                        json_code,
                        f"{st.session_state.form_info.get('form_number')}_questionnaire.json",
                        mime="application/json"
                    )
                
                with d3:
                    st.download_button(
                        "📊 Report",
                        report,
                        f"{st.session_state.form_info.get('form_number')}_report.txt",
                        mime="text/plain"
                    )
                
                st.success("✅ All files ready for download!")
    
    with tab4:
        st.markdown("## 🐛 Debug Information")
        
        if st.session_state.pdf_processed:
            st.markdown("### Extraction Log")
            if st.session_state.get('extraction_log'):
                log_text = "\n".join(st.session_state.extraction_log)
                st.text_area("Log", log_text, height=400)
            
            st.markdown("### Field Details")
            
            # Show all fields with full details
            if st.checkbox("Show all field details"):
                for part_name, fields in st.session_state.fields_by_part.items():
                    with st.expander(f"{part_name} - Raw Field Data"):
                        for field in fields:
                            st.json({
                                "field_id": field.field_id,
                                "widget_name": field.widget_name,
                                "field_label": field.field_label,
                                "field_type": field.field_type,
                                "part_number": field.part_number,
                                "part_name": field.part_name,
                                "page": field.page,
                                "value": field.value,
                                "is_mapped": field.is_mapped,
                                "db_mapping": field.db_mapping,
                                "to_questionnaire": field.to_questionnaire
                            })
        else:
            st.info("Upload and extract a PDF to see debug information.")
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 🤖 USCIS Form Reader Pro")
        st.markdown("---")
        
        st.markdown("""
        ### Features
        - 🔍 Smart field extraction
        - 🤖 AI-powered mapping
        - 📊 No duplicate fields
        - 🎯 Accurate part detection
        - 📥 Clean exports
        
        ### Supported Forms
        - I-90, I-129, I-130
        - I-140, I-485, I-526
        - I-539, I-751, I-765
        - N-400, N-600, N-565
        - G-28 and more...
        """)
        
        st.markdown("---")
        
        if st.session_state.pdf_processed:
            st.markdown("### Current Form")
            st.info(f"""
            **{st.session_state.form_info.get('form_number', 'Unknown')}**  
            {st.session_state.form_info.get('form_title', '')}
            """)
            
            if st.button("📊 Download Report", use_container_width=True):
                report = f"""USCIS Form Analysis Report
Form: {st.session_state.form_info.get('form_number')}
Title: {st.session_state.form_info.get('form_title')}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*50}

SUMMARY
Total Fields: {len(st.session_state.fields)}
Parts: {len(st.session_state.fields_by_part)}
Pages: {st.session_state.form_info.get('pages')}

FIELD BREAKDOWN BY PART
"""
                for part, fields in st.session_state.fields_by_part.items():
                    report += f"\n{part} ({len(fields)} fields)\n"
                    report += "-" * len(part) + "\n"
                    for f in fields:
                        report += f"  - {f.field_label} [{f.field_type}] - {f.get_status()}\n"
                
                st.download_button(
                    "💾 Save Report",
                    report,
                    f"{st.session_state.form_info.get('form_number')}_analysis.txt",
                    mime="text/plain"
                )

if __name__ == "__main__":
    main()
