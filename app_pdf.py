import streamlit as st
import json
import re
import fitz  # PyMuPDF
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field, asdict
from collections import defaultdict, OrderedDict
import openai
from abc import ABC, abstractmethod
import time
import hashlib
from datetime import datetime
import traceback

# Configure page
st.set_page_config(
    page_title="Universal USCIS Form Reader - AI Powered",
    page_icon="🤖",
    layout="wide"
)

# CSS styling
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 2rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        text-align: center;
    }
    .agent-status {
        background: #f0f7ff;
        border-left: 4px solid #2196F3;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 4px;
        animation: slideIn 0.3s ease-out;
    }
    @keyframes slideIn {
        from { transform: translateX(-20px); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    .field-card {
        background: white;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 1.2rem;
        margin: 0.5rem 0;
        transition: all 0.2s;
    }
    .field-card:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        transform: translateY(-2px);
    }
    .mapped { 
        border-left: 4px solid #4CAF50;
        background: #f1f8f4;
    }
    .questionnaire { 
        border-left: 4px solid #FFC107;
        background: #fffbf0;
    }
    .unmapped { 
        border-left: 4px solid #f44336;
        background: #fef1f1;
    }
    .part-header {
        background: linear-gradient(135deg, #2196F3, #1976D2);
        color: white;
        padding: 1.2rem;
        border-radius: 8px;
        margin: 1rem 0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    }
    .field-info {
        font-size: 0.85rem;
        color: #666;
        margin-top: 0.5rem;
        font-style: italic;
    }
    .item-number {
        font-weight: bold;
        color: #1976D2;
        margin-right: 0.5rem;
        font-size: 1.1rem;
    }
    .part-selector {
        background: white;
        padding: 1.5rem;
        border-radius: 8px;
        border: 1px solid #ddd;
        margin-bottom: 1.5rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .stats-card {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid #e0e0e0;
        text-align: center;
        height: 100%;
    }
    .ai-badge {
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white;
        padding: 0.2rem 0.6rem;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 500;
        display: inline-block;
        margin-left: 0.5rem;
    }
    .questionnaire-key {
        background: #fff3cd;
        color: #856404;
        padding: 0.2rem 0.5rem;
        border-radius: 4px;
        font-size: 0.75rem;
        font-family: monospace;
        display: inline-block;
        margin-left: 0.5rem;
    }
    .custom-field-dialog {
        background: linear-gradient(135deg, #e3f2fd 0%, #f3e5f5 100%);
        padding: 1.5rem;
        border-radius: 10px;
        margin-bottom: 1.5rem;
        border: 2px dashed #667eea;
    }
    .action-button-row {
        display: flex;
        gap: 1rem;
        margin-bottom: 1.5rem;
    }
    .dropdown-header {
        background: #f5f5f5;
        font-weight: bold;
        color: #666;
        font-size: 0.85rem;
        padding: 0.5rem;
        text-transform: uppercase;
    }
    .dropdown-item {
        padding-left: 1.5rem;
        font-size: 0.9rem;
    }
    .ai-analysis-box {
        background: #e8f5e9;
        border-left: 4px solid #4caf50;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 4px;
    }
    .progress-bar {
        width: 100%;
        height: 20px;
        background: #e0e0e0;
        border-radius: 10px;
        overflow: hidden;
        margin-top: 10px;
    }
    .progress-fill {
        height: 100%;
        background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
        transition: width 0.3s ease;
    }
</style>
""", unsafe_allow_html=True)

# Enhanced Database structure
UNIVERSAL_DB_STRUCTURE = {
    "beneficiary": {
        "Beneficiary": ["beneficiaryFirstName", "beneficiaryLastName", "beneficiaryMiddleName", 
                       "beneficiaryDateOfBirth", "beneficiaryGender", "beneficiarySsn",
                       "alienNumber", "alienRegistrationNumber", "uscisOnlineAccountNumber",
                       "beneficiaryCountryOfBirth", "beneficiaryCitizenOfCountry",
                       "maritalStatus", "numberOfChildren"],
        "MailingAddress": ["addressStreet", "addressCity", "addressState", "addressZip", 
                          "addressCountry", "addressAptSteFlrNumber", "addressNumber", "addressType",
                          "inCareOfName", "addressProvince", "addressPostalCode"],
        "ContactInfo": ["daytimeTelephoneNumber", "mobileTelephoneNumber", "emailAddress",
                       "workPhone", "eveningPhone", "faxNumber"],
        "PassportDetails": ["passportNumber", "passportIssueCountry", "passportIssueDate", 
                           "passportExpiryDate"],
        "VisaDetails": ["currentNonimmigrantStatus", "dateStatusExpires", "visaNumber",
                       "visaIssueDate", "consulateLocation"]
    },
    "petitioner": {
        "": ["familyName", "givenName", "middleName", "companyOrOrganizationName",
             "petitionerType", "dateOfBirth", "ssn", "ein"],
        "ContactInfo": ["daytimeTelephoneNumber", "mobileTelephoneNumber", "emailAddress",
                       "workPhone", "faxNumber"],
        "Address": ["addressStreet", "addressCity", "addressState", "addressZip", 
                   "addressCountry", "addressNumber", "addressType"]
    },
    "customer": {
        "": ["customer_name", "customer_tax_id", "customer_type_of_business",
             "customer_year_established", "customer_gross_annual_income",
             "customer_net_annual_income", "customer_total_employees"],
        "SignatoryInfo": ["signatory_first_name", "signatory_last_name", "signatory_middle_name",
                         "signatory_job_title", "signatory_work_phone", "signatory_mobile_phone", 
                         "signatory_email_id", "signatory_email"],
        "Address": ["address_street", "address_city", "address_state", "address_zip", 
                   "address_country", "address_number", "address_type", "address_apt_ste_flr"]
    },
    "attorney": {
        "attorneyInfo": ["firstName", "lastName", "middleName", "stateBarNumber", "barNumber",
                        "workPhone", "emailAddress", "faxNumber", "licensingAuthority",
                        "eligibilityCategory", "eligibilityNumber"],
        "address": ["addressStreet", "addressCity", "addressState", "addressZip", 
                   "addressCountry", "addressNumber", "addressType"]
    },
    "attorneyLawfirmDetails": {
        "lawfirmDetails": ["lawFirmName", "lawFirmEIN"],
        "address": ["addressStreet", "addressCity", "addressState", "addressZip", 
                   "addressCountry", "addressNumber", "addressType"]
    },
    "case": {
        "": ["caseType", "caseSubType", "receiptNumber", "priorityDate",
             "h1bRegistrationNumber", "requestedAction", "filingType"]
    },
    "employment": {
        "": ["jobTitle", "socCode", "naicsCode", "employerName", "employmentStartDate",
             "employmentEndDate", "workLocation", "annualSalary", "wageUnit"]
    }
}

# Initialize custom fields in session state
if 'custom_db_fields' not in st.session_state:
    st.session_state.custom_db_fields = {}

@dataclass
class ExtractedField:
    """Enhanced field representation with AI metadata"""
    # Basic info
    name: str
    label: str
    type: str  # text, checkbox, radio, dropdown, signature, date
    value: str = ""
    
    # Location info
    page: int = 1
    part: str = "Part 1"
    part_number: int = 1
    part_title: str = ""
    section: str = ""
    
    # Identification
    item_number: str = ""  # e.g., "1.a", "2.b"
    widget_id: str = ""
    field_hash: str = ""
    raw_name: str = ""  # Store original field name
    
    # Mapping info
    db_path: Optional[str] = None
    is_questionnaire: bool = False
    is_conditional: bool = False
    conditional_data: Optional[Dict] = None
    
    # AI metadata
    ai_confidence: float = 0.0
    ai_suggestion: Optional[str] = None
    ai_extracted_label: Optional[str] = None
    ai_context: Optional[str] = None
    ai_part_context: Optional[str] = None  # Part-specific context for mapping
    
    # Questionnaire generation
    questionnaire_name: str = ""
    questionnaire_key: str = ""
    control_type: str = ""
    questionnaire_type: str = ":ConditionBox"  # Default for checkboxes/radios
    
    # Debug info
    debug_info: Dict = field(default_factory=dict)
    
    def __post_init__(self):
        # Generate unique hash
        if not self.field_hash:
            content = f"{self.name}_{self.part}_{self.page}_{self.item_number}_{self.raw_name}"
            self.field_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        
        # Generate widget ID
        if not self.widget_id:
            self.widget_id = f"{self.part_number}_{self.field_hash}"
        
        # Update questionnaire key to match format pt{part}_{item}
        if self.item_number:
            # Convert item number like "1.a" to "1a"
            item_clean = self.item_number.replace('.', '')
            self.questionnaire_key = f"pt{self.part_number}_{item_clean}"
        else:
            self.questionnaire_key = f"pt{self.part_number}_{self.name[:10]}"
        
        # Set questionnaire type based on field type
        if self.type == "text" and self.is_questionnaire:
            self.questionnaire_type = ":SingleBox"
        elif self.type in ["checkbox", "radio"]:
            self.questionnaire_type = ":ConditionBox"

@dataclass
class FormStructure:
    """Enhanced form structure with metadata"""
    form_number: str
    form_title: str
    form_hash: str = ""
    upload_time: str = ""
    parts: Dict[str, List[ExtractedField]] = field(default_factory=OrderedDict)
    total_fields: int = 0
    total_pages: int = 0
    ai_extraction_used: bool = False
    extraction_confidence: float = 0.0
    extraction_logs: List[str] = field(default_factory=list)
    ai_form_analysis: Optional[Dict] = None  # Store AI analysis of the form
    
    def __post_init__(self):
        if not self.upload_time:
            self.upload_time = datetime.now().isoformat()
        if not self.form_hash:
            self.form_hash = hashlib.md5(f"{self.form_number}_{self.upload_time}".encode()).hexdigest()[:8]
    
    def get_part_numbers(self) -> List[str]:
        """Get sorted list of part numbers"""
        parts = list(self.parts.keys())
        # Sort by part number
        def extract_number(part_name):
            match = re.search(r'\d+', part_name)
            return int(match.group()) if match else 999
        
        return sorted(parts, key=extract_number)
    
    def add_log(self, message: str):
        """Add extraction log"""
        self.extraction_logs.append(f"{datetime.now().strftime('%H:%M:%S')} - {message}")

# Base Agent Class
class Agent(ABC):
    """Enhanced base agent with logging"""
    
    def __init__(self, name: str):
        self.name = name
        self.status = "idle"
        self.last_action = ""
        self.start_time = None
        self.logs = []
    
    @abstractmethod
    def execute(self, *args, **kwargs) -> Any:
        """Execute the agent's main task"""
        pass
    
    def update_status(self, status: str, action: str = ""):
        """Update agent status with timing"""
        self.status = status
        self.last_action = action
        
        if status == "active" and not self.start_time:
            self.start_time = time.time()
        elif status in ["completed", "error"] and self.start_time:
            duration = time.time() - self.start_time
            action += f" (took {duration:.2f}s)"
            self.start_time = None
        
        self.logs.append(f"{status}: {action}")
        
        if status != "idle":
            status_icon = "🟢" if status == "completed" else "🟡" if status == "active" else "🔴"
            st.markdown(f'<div class="agent-status">{status_icon} **{self.name}**: {action}</div>', 
                       unsafe_allow_html=True)

# Enhanced PDF Reader Agent with AI
class AIEnhancedPDFReader(Agent):
    """PDF Reader with AI enhancement capabilities"""
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__("AI-Enhanced PDF Reader")
        self.api_key = api_key
        if api_key:
            openai.api_key = api_key
    
    def execute(self, pdf_file, use_ai: bool = True) -> Optional[FormStructure]:
        """Extract fields with optional AI enhancement"""
        self.update_status("active", "Initializing PDF analysis...")
        
        try:
            # Clear any existing data
            if 'form_structure' in st.session_state:
                del st.session_state.form_structure
            
            pdf_bytes = pdf_file.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            # Extract full text for AI analysis
            full_text = ""
            page_texts = []
            for page in doc:
                page_text = page.get_text()
                full_text += page_text + "\n"
                page_texts.append(page_text)
            
            # AI-powered form detection and analysis
            form_info = None
            form_analysis = None
            if use_ai and self.api_key and full_text:
                self.update_status("active", "AI analyzing form structure...")
                form_analysis = self._ai_comprehensive_form_analysis(full_text[:10000])
                if form_analysis:
                    form_info = {
                        'number': form_analysis.get('form_number', 'Unknown'),
                        'title': form_analysis.get('form_title', 'Unknown Form')
                    }
            
            # Fallback to pattern-based detection
            if not form_info:
                form_info = self._detect_form_type(doc)
            
            form_structure = FormStructure(
                form_number=form_info['number'],
                form_title=form_info['title'],
                total_pages=len(doc),
                ai_extraction_used=use_ai and self.api_key is not None,
                ai_form_analysis=form_analysis
            )
            
            form_structure.add_log(f"Detected form: {form_info['number']} - {form_info['title']}")
            self.update_status("active", f"Processing {form_info['number']} - {form_info['title']}")
            
            # Extract parts using AI if available
            parts_structure = None
            if form_analysis and 'parts' in form_analysis:
                parts_structure = form_analysis['parts']
                form_structure.add_log(f"AI detected {len(parts_structure)} parts")
            
            # Extract fields by parts
            current_part = "Part 1"
            current_part_number = 1
            current_part_title = "General Information"
            current_part_context = ""
            seen_fields = set()
            field_count = 0
            
            # Process each page
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_text = page_texts[page_num]
                
                # Update part information based on page content
                if not parts_structure:
                    part_info = self._detect_current_part(page_text, current_part_number)
                    if part_info:
                        current_part = part_info['part']
                        current_part_number = part_info['number']
                        current_part_title = part_info['title']
                        form_structure.add_log(f"Found {current_part}: {current_part_title}")
                else:
                    # Find which part this page belongs to using AI analysis
                    for part in parts_structure:
                        if part.get('start_page', 1) <= page_num + 1 <= part.get('end_page', len(doc)):
                            current_part = f"Part {part['number']}"
                            current_part_number = part['number']
                            current_part_title = part['title']
                            current_part_context = part.get('context', '')
                            break
                
                # Initialize part if needed
                if current_part not in form_structure.parts:
                    form_structure.parts[current_part] = []
                
                # Extract widgets
                widgets = page.widgets()
                
                if widgets:
                    self.update_status("active", f"Extracting fields from page {page_num + 1} ({current_part})...")
                    
                    # Process widgets with AI enhancement
                    for widget in widgets:
                        try:
                            if widget:
                                field = self._extract_field_with_ai(
                                    widget, 
                                    page_num + 1, 
                                    current_part, 
                                    current_part_number,
                                    current_part_title,
                                    page_text if use_ai else None,
                                    field_count,
                                    current_part_context
                                )
                                
                                if field and field.field_hash not in seen_fields:
                                    seen_fields.add(field.field_hash)
                                    form_structure.parts[current_part].append(field)
                                    form_structure.total_fields += 1
                                    field_count += 1
                        except Exception as e:
                            form_structure.add_log(f"Error processing widget: {str(e)}")
                            continue
                else:
                    # Try alternative extraction methods
                    form_fields = self._extract_form_fields_alternative(page, page_num + 1, 
                                                                      current_part, current_part_number,
                                                                      current_part_title, field_count)
                    for field in form_fields:
                        field.ai_part_context = current_part_context
                        if field.field_hash not in seen_fields:
                            seen_fields.add(field.field_hash)
                            form_structure.parts[current_part].append(field)
                            form_structure.total_fields += 1
                            field_count += 1
            
            doc.close()
            
            # Ensure we have at least Part 1
            if not form_structure.parts:
                form_structure.parts["Part 1"] = []
                form_structure.add_log("No parts detected, created default Part 1")
            
            # Sort fields within each part
            for part_name in form_structure.parts:
                form_structure.parts[part_name].sort(
                    key=lambda f: (self._parse_item_number(f.item_number), f.label)
                )
            
            # Calculate extraction confidence
            if form_structure.total_fields > 0:
                fields_with_ai = sum(1 for fields in form_structure.parts.values() 
                                   for f in fields if f.ai_confidence > 0)
                form_structure.extraction_confidence = fields_with_ai / form_structure.total_fields
            
            form_structure.add_log(f"Extraction complete: {form_structure.total_fields} fields found in {len(form_structure.parts)} parts")
            self.update_status("completed", 
                             f"Extracted {form_structure.total_fields} fields from {len(form_structure.parts)} parts")
            
            return form_structure
            
        except Exception as e:
            self.update_status("error", f"Failed: {str(e)}")
            st.error(f"Error processing PDF: {str(e)}")
            return None
    
    def _ai_comprehensive_form_analysis(self, text: str) -> Optional[Dict]:
        """Use AI to comprehensively analyze the form"""
        if not self.api_key:
            return None
        
        try:
            prompt = f"""
            You are an expert at analyzing USCIS forms. Analyze this form text and provide a comprehensive analysis.
            
            Text (first 10000 characters):
            {text}
            
            Return a detailed JSON object with:
            {{
                "form_number": "The exact form number (e.g., I-539, G-28, I-129)",
                "form_title": "The complete form title",
                "form_edition": "Edition date if available",
                "parts": [
                    {{
                        "number": 1,
                        "title": "Part title from the form",
                        "description": "What this part is about",
                        "context": "Who fills this part and what kind of information it contains",
                        "start_page": 1,
                        "end_page": 2,
                        "typical_fields": ["field types typically found in this part"]
                    }}
                ],
                "form_purpose": "What this form is used for",
                "primary_applicant": "Who is the primary person filling this form"
            }}
            
            Be very accurate about the form number and parts structure. Look for patterns like "Part 1.", "Part 2.", etc.
            """
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo-16k",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=2000
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            st.warning(f"AI form analysis failed: {str(e)}")
            return None
    
    def _detect_form_type(self, doc) -> dict:
        """Enhanced form type detection"""
        first_pages_text = ""
        for i in range(min(3, len(doc))):
            first_pages_text += doc[i].get_text().upper()
        
        forms = {
            'I-90': 'Application to Replace Permanent Resident Card',
            'I-129': 'Petition for a Nonimmigrant Worker',
            'I-130': 'Petition for Alien Relative',
            'I-131': 'Application for Travel Document',
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
        
        # Look for form number patterns
        form_patterns = [
            r'FORM\s+(I-\d+[A-Z]?)',
            r'Form\s+(I-\d+[A-Z]?)',
            r'FORM\s+(N-\d+)',
            r'Form\s+(N-\d+)',
            r'FORM\s+(G-\d+)',
            r'Form\s+(G-\d+)',
        ]
        
        for pattern in form_patterns:
            match = re.search(pattern, first_pages_text)
            if match:
                form_num = match.group(1)
                if form_num in forms:
                    return {'number': form_num, 'title': forms[form_num]}
        
        return {'number': 'Unknown', 'title': 'Unknown USCIS Form'}
    
    def _detect_current_part(self, page_text: str, current_number: int) -> Optional[Dict]:
        """Detect part information from page text"""
        patterns = [
            r'Part\s+(\d+)\.?\s*[–-]?\s*([^\n]{0,100})',
            r'PART\s+(\d+)\.?\s*[–-]?\s*([^\n]{0,100})',
        ]
        
        for pattern in patterns:
            matches = list(re.finditer(pattern, page_text, re.MULTILINE))
            if matches:
                match = matches[0]
                part_num = int(match.group(1))
                if part_num != current_number:
                    title = match.group(2).strip()
                    title = re.sub(r'[.\s]+$', '', title)
                    title = re.sub(r'\s+', ' ', title)
                    
                    return {
                        'part': f"Part {part_num}",
                        'number': part_num,
                        'title': title if title else f"Section {part_num}"
                    }
        
        return None
    
    def _extract_field_with_ai(self, widget, page: int, part: str, part_number: int, 
                              part_title: str, page_text: Optional[str], field_count: int,
                              part_context: str = "") -> Optional[ExtractedField]:
        """Extract field with AI enhancement"""
        try:
            # Get field name
            field_name = ""
            if hasattr(widget, 'field_name') and widget.field_name:
                field_name = widget.field_name
            elif hasattr(widget, 'field_value'):
                field_name = f"field_{field_count}"
            else:
                return None
            
            # Store raw name for debugging
            raw_name = field_name
            
            # Basic extraction
            clean_name = self._clean_field_name(field_name)
            
            # Extract item number
            item_number = self._extract_item_number(field_name, clean_name)
            
            # Generate label
            label = self._generate_label(clean_name)
            
            # Use AI to enhance label if available
            if page_text and self.api_key and item_number:
                ai_label = self._ai_enhance_label(item_number, page_text, label)
                if ai_label:
                    label = ai_label
            
            # Determine field type
            field_type = self._get_field_type(widget)
            
            # Generate questionnaire names
            if item_number:
                quest_name = item_number.replace('.', '_')
            else:
                quest_name = re.sub(r'[^a-zA-Z0-9_]', '', clean_name)[:20]
                if not quest_name:
                    quest_name = f"field_{field_count}"
            
            # Determine control type for questionnaire
            control_type_map = {
                'checkbox': 'colorSwitch',
                'radio': 'radio',
                'text': 'text',
                'dropdown': 'select',
                'date': 'date',
                'signature': 'signature'
            }
            
            # Create field
            field = ExtractedField(
                name=clean_name,
                label=label,
                type=field_type,
                page=page,
                part=part,
                part_number=part_number,
                part_title=part_title,
                item_number=item_number,
                raw_name=raw_name,
                is_questionnaire=field_type in ["checkbox", "radio"],
                questionnaire_name=quest_name,
                control_type=control_type_map.get(field_type, 'text'),
                ai_confidence=0.8 if page_text and self.api_key else 0.0,
                ai_part_context=part_context,
                debug_info={
                    'raw_name': raw_name,
                    'clean_name': clean_name,
                    'widget_type': getattr(widget, 'field_type', 'unknown')
                }
            )
            
            # Check for conditional logic
            if field_type in ["checkbox", "radio"] and item_number:
                field.is_conditional = True
            
            return field
            
        except Exception as e:
            st.warning(f"Error extracting field: {str(e)}")
            return None
    
    def _extract_form_fields_alternative(self, page, page_num: int, part: str, 
                                       part_number: int, part_title: str, field_count: int) -> List[ExtractedField]:
        """Alternative extraction method using form annotations"""
        fields = []
        
        try:
            # Try to get form fields from annotations
            for annot in page.annots():
                if annot.type[0] in [17, 18, 19, 20]:  # Form field types
                    field_name = annot.field_name or f"field_{field_count}"
                    field_type = self._get_annot_field_type(annot.type[0])
                    
                    field = ExtractedField(
                        name=field_name,
                        label=self._generate_label(field_name),
                        type=field_type,
                        page=page_num,
                        part=part,
                        part_number=part_number,
                        part_title=part_title,
                        raw_name=field_name,
                        is_questionnaire=field_type in ["checkbox", "radio"],
                        questionnaire_name=f"field_{field_count}",
                        debug_info={'annot_type': annot.type[0]}
                    )
                    fields.append(field)
                    field_count += 1
        except:
            pass
        
        return fields
    
    def _get_annot_field_type(self, annot_type: int) -> str:
        """Map annotation type to field type"""
        type_map = {
            17: "text",      # Text field
            18: "checkbox",  # Checkbox
            19: "radio",     # Radio button
            20: "dropdown"   # Combo box
        }
        return type_map.get(annot_type, "text")
    
    def _clean_field_name(self, field_name: str) -> str:
        """Clean field name from PDF artifacts"""
        clean = field_name
        
        # Remove common prefixes
        prefixes = [
            r'topmostSubform\[0\]\.',
            r'form1\[0\]\.',
            r'#subform\[\d+\]\.',
            r'Page\d+\[0\]\.',
            r'Part\d+\.',
            r'TextField\d*\.',
            r'CheckBox\d*\.',
            r'\[0\]',
            r'#field\[\d+\]'
        ]
        
        for prefix in prefixes:
            clean = re.sub(prefix, '', clean, flags=re.IGNORECASE)
        
        # Clean up brackets and dots
        clean = re.sub(r'\[\d+\]', '', clean)
        clean = clean.strip('.')
        
        return clean
    
    def _extract_item_number(self, field_name: str, clean_name: str) -> str:
        """Extract item number from field name"""
        patterns = [
            r'(?:^|[^\d])(\d+)\.([a-z])\b',  # 1.a, 2.b
            r'(?:^|[^\d])(\d+)([a-z])\b',     # 1a, 2b
            r'Item(\d+)([a-z]?)',             # Item1a
            r'^\s*(\d+)\s*$',                 # Just numbers
        ]
        
        # Try original name first
        for text in [field_name, clean_name]:
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    if len(match.groups()) >= 2 and match.group(2):
                        return f"{match.group(1)}.{match.group(2)}"
                    else:
                        return match.group(1)
        
        return ""
    
    def _generate_label(self, clean_name: str) -> str:
        """Generate human-readable label"""
        # Remove common suffixes
        label = re.sub(r'(?i)(field|text|check|box|button)\d*$', '', clean_name)
        
        # Convert to readable format
        label = re.sub(r'([a-z])([A-Z])', r'\1 \2', label)
        label = label.replace('_', ' ').replace('-', ' ')
        label = ' '.join(label.split())
        
        # Common replacements
        replacements = {
            'fname': 'First Name',
            'lname': 'Last Name',
            'mname': 'Middle Name',
            'dob': 'Date of Birth',
            'ssn': 'Social Security Number',
            'addr': 'Address',
            'tel': 'Telephone',
            'email': 'Email Address',
            'apt': 'Apartment',
            'ste': 'Suite'
        }
        
        label_lower = label.lower()
        for old, new in replacements.items():
            if old in label_lower:
                return new
        
        # Capitalize properly
        return ' '.join(word.capitalize() for word in label.split())
    
    def _get_field_type(self, widget) -> str:
        """Determine field type from widget"""
        type_map = {
            1: "button",
            2: "checkbox", 
            3: "radio",
            4: "text",
            5: "dropdown",
            6: "list",
            7: "signature"
        }
        
        widget_type = widget.field_type if hasattr(widget, 'field_type') else 4
        field_type = type_map.get(widget_type, "text")
        
        # Additional detection based on field name
        if hasattr(widget, 'field_name'):
            name_lower = widget.field_name.lower()
            if any(date_word in name_lower for date_word in ['date', 'dob', 'birth']):
                field_type = "date"
            elif 'signature' in name_lower:
                field_type = "signature"
        
        return field_type
    
    def _ai_enhance_label(self, item_number: str, page_text: str, current_label: str) -> Optional[str]:
        """Use AI to find the actual label from form text"""
        try:
            # Extract relevant context around item number
            context_lines = []
            lines = page_text.split('\n')
            
            for i, line in enumerate(lines):
                if item_number in line:
                    # Get surrounding lines
                    start = max(0, i - 2)
                    end = min(len(lines), i + 3)
                    context_lines = lines[start:end]
                    break
            
            if not context_lines:
                return None
            
            context = '\n'.join(context_lines)
            
            prompt = f"""
            Find the label/question for item {item_number} in this form text:
            
            {context}
            
            Current extracted label: {current_label}
            
            Return ONLY the actual label text, nothing else.
            """
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=100
            )
            
            ai_label = response.choices[0].message.content.strip()
            
            # Validate the response
            if ai_label and len(ai_label) < 200 and not ai_label.startswith("I"):
                return ai_label
                
        except:
            pass
        
        return None
    
    def _parse_item_number(self, item_num: str) -> Tuple[int, str]:
        """Parse item number for sorting"""
        if not item_num:
            return (999, '')
        
        match = re.match(r'(\d+)\.?([a-z]?)', item_num)
        if match:
            return (int(match.group(1)), match.group(2) or '')
        return (999, item_num)

# Universal Mapping Agent
class UniversalMappingAgent(Agent):
    """AI-powered universal field mapping"""
    
    def __init__(self, api_key: str):
        super().__init__("Universal AI Mapper")
        self.api_key = api_key
        if api_key:
            openai.api_key = api_key
    
    def execute(self, form_structure: FormStructure, auto_map: bool = True) -> None:
        """Map fields using AI and patterns"""
        if not auto_map:
            return
        
        self.update_status("active", "Starting AI-powered field mapping...")
        
        total_mapped = 0
        total_fields = sum(len(fields) for fields in form_structure.parts.values())
        
        if total_fields == 0:
            self.update_status("error", "No fields found to map")
            return
        
        # Process in batches for efficiency
        for part_name, fields in form_structure.parts.items():
            self.update_status("active", f"Mapping {part_name}...")
            
            # Get part context
            part_context = ""
            if form_structure.ai_form_analysis and 'parts' in form_structure.ai_form_analysis:
                for part_info in form_structure.ai_form_analysis['parts']:
                    if f"Part {part_info['number']}" == part_name:
                        part_context = part_info.get('context', '')
                        break
            
            # Group text fields for batch processing
            text_fields = [f for f in fields if f.type == "text" and not f.db_path]
            
            if text_fields:
                # Try pattern matching first
                for field in text_fields:
                    suggestion = self._pattern_match(field, form_structure.form_number, part_context)
                    if suggestion:
                        field.db_path = suggestion
                        field.ai_confidence = 0.9
                        total_mapped += 1
                
                # Use AI for remaining fields
                if self.api_key:
                    unmapped = [f for f in text_fields if not f.db_path]
                    if unmapped:
                        mapped = self._batch_ai_mapping(unmapped, form_structure.form_number, 
                                                      part_name, part_context)
                        total_mapped += mapped
        
        success_rate = (total_mapped/total_fields*100) if total_fields > 0 else 0
        self.update_status("completed", 
                          f"Mapped {total_mapped} fields ({success_rate:.1f}% success rate)")
    
    def _pattern_match(self, field: ExtractedField, form_type: str, part_context: str) -> Optional[str]:
        """Enhanced pattern matching for universal forms with part context"""
        label_lower = field.label.lower()
        name_lower = field.name.lower()
        combined = f"{label_lower} {name_lower}"
        
        # Get all custom fields
        custom_fields = st.session_state.get('custom_db_fields', {})
        
        # Universal patterns with part context awareness
        patterns = {
            # Names - check part context for who this refers to
            r'(?:petitioner|applicant|your).*(?:given|first).*name': 'petitioner.givenName',
            r'(?:petitioner|applicant|your).*(?:family|last).*name': 'petitioner.familyName',
            r'(?:beneficiary|spouse|their).*(?:given|first).*name': 'beneficiary.Beneficiary.beneficiaryFirstName',
            r'(?:beneficiary|spouse|their).*(?:family|last).*name': 'beneficiary.Beneficiary.beneficiaryLastName',
            r'(?:attorney|representative).*first.*name': 'attorney.attorneyInfo.firstName',
            r'(?:attorney|representative).*last.*name': 'attorney.attorneyInfo.lastName',
            r'signatory.*first': 'customer.SignatoryInfo.signatory_first_name',
            r'signatory.*last': 'customer.SignatoryInfo.signatory_last_name',
            
            # Identification
            r'alien.*(?:registration|number)|a[\s-]?number': 'beneficiary.Beneficiary.alienNumber',
            r'uscis.*(?:online|account).*number': 'beneficiary.Beneficiary.uscisOnlineAccountNumber',
            r'receipt.*number': 'case.receiptNumber',
            r'social.*security|ssn': 'beneficiary.Beneficiary.beneficiarySsn',
            r'state.*bar.*number': 'attorney.attorneyInfo.stateBarNumber',
            r'passport.*number': 'beneficiary.PassportDetails.passportNumber',
            
            # Contact
            r'(?:day.*time|daytime).*(?:phone|telephone)': 'beneficiary.ContactInfo.daytimeTelephoneNumber',
            r'mobile.*(?:phone|number)|cell.*(?:phone|number)': 'beneficiary.ContactInfo.mobileTelephoneNumber',
            r'email.*address|e[\s-]?mail': 'beneficiary.ContactInfo.emailAddress',
            r'fax.*number': 'attorney.attorneyInfo.faxNumber',
            r'work.*phone': 'attorney.attorneyInfo.workPhone',
            
            # Address
            r'street.*address|address.*line.*1': 'beneficiary.MailingAddress.addressStreet',
            r'city.*town': 'beneficiary.MailingAddress.addressCity',
            r'state.*province': 'beneficiary.MailingAddress.addressState',
            r'zip.*code|postal.*code': 'beneficiary.MailingAddress.addressZip',
            r'country': 'beneficiary.MailingAddress.addressCountry',
            r'apt.*ste.*flr|apartment|suite': 'beneficiary.MailingAddress.addressAptSteFlrNumber',
            
            # Dates
            r'date.*birth|birth.*date': 'beneficiary.Beneficiary.beneficiaryDateOfBirth',
            r'expir.*date|date.*expir': 'beneficiary.VisaDetails.dateStatusExpires',
            
            # Organization
            r'(?:company|organization|employer).*name': 'customer.customer_name',
            r'law.*firm.*name': 'attorneyLawfirmDetails.lawfirmDetails.lawFirmName',
            r'job.*title|position': 'customer.SignatoryInfo.signatory_job_title',
        }
        
        # Check patterns
        for pattern, db_path in patterns.items():
            if re.search(pattern, combined, re.IGNORECASE):
                # Adjust path based on form context and part context
                if form_type == "G-28":
                    # G-28 uses customer instead of beneficiary for client info
                    if "beneficiary" in db_path and "client" in part_context.lower():
                        db_path = db_path.replace("beneficiary.", "customer.")
                elif form_type == "I-539":
                    # I-539 context-specific adjustments
                    if "applicant" in part_context.lower() and "beneficiary" in db_path:
                        # In I-539, the applicant is the beneficiary
                        pass  # Keep as beneficiary
                
                return db_path
        
        # Check custom fields
        for custom_path in custom_fields.keys():
            field_name = custom_path.split('.')[-1].lower()
            if field_name in combined:
                return custom_path
        
        return None
    
    def _batch_ai_mapping(self, fields: List[ExtractedField], form_type: str, 
                         part_name: str, part_context: str) -> int:
        """Batch process fields with AI including part context"""
        if not self.api_key or not fields:
            return 0
        
        try:
            # Build field descriptions
            field_info = []
            for f in fields[:10]:  # Process up to 10 at a time
                info = {
                    'label': f.label,
                    'name': f.name,
                    'part': f.part,
                    'item': f.item_number
                }
                field_info.append(info)
            
            # Get all possible DB paths including custom
            db_paths = []
            for obj, cats in UNIVERSAL_DB_STRUCTURE.items():
                for cat, fields_list in cats.items():
                    for field in fields_list:
                        path = f"{obj}.{cat}.{field}" if cat else f"{obj}.{field}"
                        db_paths.append(path)
            
            # Add custom fields
            custom_fields = st.session_state.get('custom_db_fields', {})
            db_paths.extend(custom_fields.keys())
            
            prompt = f"""
            You are mapping fields from USCIS form {form_type} to database paths.
            
            Part: {part_name}
            Part Context: {part_context}
            
            Fields to map:
            {json.dumps(field_info, indent=2)}
            
            Available database paths:
            {json.dumps(db_paths, indent=2)}
            
            Consider the context of this part when mapping. For example:
            - If this part is about the applicant, map name fields to petitioner or beneficiary based on form type
            - If this part is about an attorney, map to attorney fields
            - If this part is about the client in G-28, map to customer fields
            
            Return a JSON object mapping field labels to database paths.
            Only include fields that have clear matches.
            
            Example:
            {{"First Name": "beneficiary.Beneficiary.beneficiaryFirstName"}}
            """
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=1000
            )
            
            mappings = json.loads(response.choices[0].message.content)
            
            # Apply mappings
            mapped_count = 0
            for field in fields:
                if field.label in mappings:
                    field.db_path = mappings[field.label]
                    field.ai_confidence = 0.7
                    field.ai_suggestion = "AI Mapped"
                    mapped_count += 1
            
            return mapped_count
            
        except Exception as e:
            self.update_status("warning", f"AI mapping error: {str(e)}")
            return 0

# Universal Export Agent
class UniversalExportAgent(Agent):
    """Export agent for all USCIS forms"""
    
    def __init__(self):
        super().__init__("Universal Export Agent")
    
    def execute(self, form_structure: FormStructure, format: str) -> str:
        """Export in requested format"""
        self.update_status("active", f"Generating {format} export...")
        
        try:
            if format == "typescript":
                result = self._generate_typescript(form_structure)
            elif format == "json":
                result = self._generate_json(form_structure)
            else:
                result = ""
            
            self.update_status("completed", f"{format} export generated successfully")
            return result
            
        except Exception as e:
            self.update_status("error", f"Export failed: {str(e)}")
            return ""
    
    def _generate_typescript(self, form_structure: FormStructure) -> str:
        """Generate TypeScript matching exact format"""
        form_name = form_structure.form_number.replace('-', '')
        
        # Initialize sections
        sections = OrderedDict([
            ('formname', form_name),
            ('customerData', {}),
            ('beneficiaryData', {}),
            ('attorneyData', {}),
            ('questionnaireData', {}),
            ('defaultData', {}),
            ('conditionalData', {}),
            ('caseData', {}),
            ('pdfName', form_structure.form_number)
        ])
        
        # Track conditional relationships
        conditional_groups = defaultdict(list)
        radio_groups = defaultdict(list)
        
        # Process fields
        for part_name, fields in form_structure.parts.items():
            for field in fields:
                if field.db_path:
                    # Determine section
                    section = self._get_section_for_path(field.db_path)
                    if section:
                        # Generate key
                        prefix = ""
                        if 'customer' in field.db_path:
                            prefix = "customer"
                        elif 'attorney' in field.db_path:
                            prefix = "attorney"
                        
                        key = f"{prefix}{field.name}" if prefix else field.name
                        suffix = self._get_suffix_for_type(field.type)
                        
                        sections[section][key] = f"{field.db_path}{suffix}"
                
                elif field.is_questionnaire:
                    # Add to questionnaire with proper suffix
                    sections['questionnaireData'][field.questionnaire_key] = f"{field.questionnaire_name}{field.questionnaire_type}"
                    
                    # Track conditionals
                    if field.type == "radio":
                        # Extract base name for radio group
                        base_name = re.sub(r'_?\d+[a-z]?$', '', field.questionnaire_name)
                        radio_groups[base_name].append(field)
                    elif field.type == "checkbox" and field.is_conditional:
                        conditional_groups[field.questionnaire_name] = field
        
        # Generate conditional data for checkboxes
        for checkbox_name, field in conditional_groups.items():
            sections['conditionalData'][field.questionnaire_key] = {
                "condition": f"{field.questionnaire_name}==true",
                "conditionTrue": "true",
                "conditionFalse": "",
                "conditionType": "CheckBox",
                "conditionParam": "",
                "conditionData": ""
            }
        
        # Generate conditional data for radio groups
        for group_name, fields in radio_groups.items():
            for field in fields:
                # Extract value from item number or use index
                if field.item_number:
                    value = field.item_number.split('.')[0]
                else:
                    value = str(fields.index(field) + 1)
                
                sections['conditionalData'][field.questionnaire_key] = {
                    "condition": f"{group_name}=={value}",
                    "conditionTrue": value,
                    "conditionFalse": "",
                    "conditionType": "CheckBox",
                    "conditionParam": "",
                    "conditionData": ""
                }
        
        # Generate TypeScript
        ts = f'export const {form_name} = {{\n'
        
        for key, value in sections.items():
            if key in ['formname', 'pdfName']:
                ts += f'    "{key}": "{value}",\n'
            elif key == 'conditionalData' and value:
                ts += f'    "{key}": {{\n'
                for cond_key, cond_data in value.items():
                    ts += f'        "{cond_key}": {{\n'
                    for k, v in cond_data.items():
                        ts += f'            "{k}": "{v}",\n'
                    ts = ts.rstrip(',\n') + '\n'
                    ts += '        },\n'
                ts = ts.rstrip(',\n') + '\n'
                ts += '    },\n'
            elif isinstance(value, dict) and value:
                ts += f'    "{key}": {{\n'
                for k, v in value.items():
                    ts += f'        "{k}": "{v}",\n'
                ts = ts.rstrip(',\n') + '\n'
                ts += '    },\n'
            else:
                ts += f'    "{key}": null,\n'
        
        ts = ts.rstrip(',\n') + '\n'
        ts += '};\n\n'
        ts += f'export default {form_name};'
        
        return ts
    
    def _generate_json(self, form_structure: FormStructure) -> str:
        """Generate JSON matching exact format"""
        controls = []
        
        for part_name, fields in form_structure.parts.items():
            # Get questionnaire fields
            quest_fields = [f for f in fields 
                           if f.is_questionnaire or (f.type == "text" and not f.db_path)]
            
            if quest_fields:
                # Add part title
                part_num = quest_fields[0].part_number
                title_text = f"{part_name}: {quest_fields[0].part_title}" if quest_fields[0].part_title else part_name
                
                controls.append({
                    "name": f"{part_num}_title",
                    "label": title_text,
                    "type": "title",
                    "validators": {},
                    "style": {"col": "12"}
                })
                
                # Group radio buttons
                radio_groups = defaultdict(list)
                
                for field in quest_fields:
                    if field.type == "radio":
                        # Extract base name for grouping
                        base_name = re.sub(r'_?\d+[a-z]?$', '', field.questionnaire_name)
                        radio_groups[base_name].append(field)
                    else:
                        # Add non-radio fields
                        control = self._create_control(field)
                        controls.append(control)
                
                # Add radio groups
                for group, radios in radio_groups.items():
                    for radio in radios:
                        control = self._create_radio_control(radio, group)
                        controls.append(control)
        
        return json.dumps({"controls": controls}, indent=2)
    
    def _get_section_for_path(self, db_path: str) -> Optional[str]:
        """Determine section from database path"""
        if db_path.startswith('customer.'):
            return 'customerData'
        elif db_path.startswith('beneficiary.'):
            return 'beneficiaryData'
        elif db_path.startswith('attorney.') or db_path.startswith('attorneyLawfirmDetails.'):
            return 'attorneyData'
        elif db_path.startswith('case.'):
            return 'caseData'
        return None
    
    def _get_suffix_for_type(self, field_type: str) -> str:
        """Get TypeScript suffix for field type"""
        suffix_map = {
            'text': ':TextBox',
            'checkbox': ':CheckBox',
            'radio': ':RadioBox',
            'dropdown': ':DropdownBox',
            'date': ':Date',
            'signature': ':SignatureBox'
        }
        return suffix_map.get(field_type, ':TextBox')
    
    def _create_control(self, field: ExtractedField) -> dict:
        """Create control object for JSON"""
        label = field.label
        if field.item_number:
            label = f"{field.item_number}. {label}"
        
        control = {
            "name": field.questionnaire_name,
            "label": label,
            "type": field.control_type,
            "validators": {"required": False}
        }
        
        # Style based on type
        if field.type == "text":
            control["style"] = {"col": "7"}
            if "maxlength" in field.name.lower():
                match = re.search(r'(\d+)', field.name.lower())
                if match:
                    control["validators"]["maxLength"] = match.group(1)
        else:
            control["style"] = {"col": "12"}
        
        return control
    
    def _create_radio_control(self, field: ExtractedField, group: str) -> dict:
        """Create radio button control"""
        label = field.label
        if field.item_number:
            label = f"{field.item_number}. {label}"
        
        # Extract value from item number
        if field.item_number:
            value = field.item_number.split('.')[0]
        else:
            value = "1"
        
        return {
            "id": field.questionnaire_name,
            "name": group,
            "label": label,
            "type": "radio",
            "value": value,
            "validators": {"required": False},
            "style": {"col": "12", "success": True},
            "className": "pt-15"
        }

# Helper function to get all database paths grouped properly
def get_all_db_paths_grouped() -> List[tuple]:
    """Get all database paths properly grouped for dropdown"""
    grouped_paths = []
    
    # Add all standard paths grouped by object
    for obj, categories in UNIVERSAL_DB_STRUCTURE.items():
        # Add group header
        grouped_paths.append(("group", f"═══ {obj.upper()} ═══", ""))
        
        # Add paths for this object
        for cat, fields_list in categories.items():
            for field in fields_list:
                path = f"{obj}.{cat}.{field}" if cat else f"{obj}.{field}"
                grouped_paths.append(("option", path, path))
    
    # Add custom fields if any
    custom_fields = st.session_state.get('custom_db_fields', {})
    if custom_fields:
        grouped_paths.append(("group", "═══ CUSTOM ═══", ""))
        for path in custom_fields.keys():
            grouped_paths.append(("option", path, path))
    
    return grouped_paths

# Main UI Functions
def clear_session_state():
    """Clear all session state data"""
    keys_to_clear = ['form_structure', 'agents', 'selected_part', 'last_upload_hash']
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]

def show_add_database_field_dialog():
    """Show dialog to add custom database field"""
    st.markdown('<div class="custom-field-dialog">', unsafe_allow_html=True)
    st.markdown("### ➕ Add Custom Database Field")
    
    col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
    
    with col1:
        obj_name = st.selectbox(
            "Object",
            ["beneficiary", "petitioner", "customer", "attorney", "case", "employment", "custom"],
            key="new_obj"
        )
    
    with col2:
        category = st.text_input("Category (optional)", key="new_cat")
    
    with col3:
        field_name = st.text_input("Field Name *", key="new_field")
    
    with col4:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Add Field", type="primary", use_container_width=True):
            if field_name:
                # Generate path
                if category:
                    path = f"{obj_name}.{category}.{field_name}"
                else:
                    path = f"{obj_name}.{field_name}"
                
                # Add to custom fields
                if 'custom_db_fields' not in st.session_state:
                    st.session_state.custom_db_fields = {}
                
                st.session_state.custom_db_fields[path] = {
                    'object': obj_name,
                    'category': category,
                    'field': field_name,
                    'created': datetime.now().isoformat()
                }
                
                st.success(f"✅ Added custom field: {path}")
                st.rerun()
            else:
                st.error("Please enter a field name")
    
    st.markdown('</div>', unsafe_allow_html=True)

def render_field_mapping(form_structure: FormStructure, selected_part: str):
    """Render field mapping interface"""
    st.markdown("## 🎯 Field Mapping Interface")
    
    # Add custom database field option
    show_add_database_field_dialog()
    
    # Show AI analysis if available
    if form_structure.ai_form_analysis:
        with st.expander("🤖 AI Form Analysis", expanded=False):
            st.markdown('<div class="ai-analysis-box">', unsafe_allow_html=True)
            st.markdown("### Form Understanding")
            st.write(f"**Form Purpose**: {form_structure.ai_form_analysis.get('form_purpose', 'N/A')}")
            st.write(f"**Primary Applicant**: {form_structure.ai_form_analysis.get('primary_applicant', 'N/A')}")
            if 'parts' in form_structure.ai_form_analysis:
                st.markdown("### Parts Structure")
                for part in form_structure.ai_form_analysis['parts']:
                    st.write(f"**Part {part['number']}**: {part['title']} - {part.get('description', '')}")
            st.markdown('</div>', unsafe_allow_html=True)
    
    # Part selector
    st.markdown('<div class="part-selector">', unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
    
    with col1:
        part_options = form_structure.get_part_numbers()
        if not part_options:
            st.error("No parts found in the form structure!")
            return selected_part
            
        selected_part = st.selectbox(
            "📑 Select Part to View",
            part_options,
            index=part_options.index(selected_part) if selected_part in part_options else 0,
            key="part_selector"
        )
    
    with col2:
        if selected_part and selected_part in form_structure.parts:
            part_fields = form_structure.parts[selected_part]
            mapped = sum(1 for f in part_fields if f.db_path)
            quest = sum(1 for f in part_fields if f.is_questionnaire)
            st.markdown(f'''
            <div class="stats-card">
                <strong>{len(part_fields)}</strong> fields<br>
                <small>{mapped} mapped • {quest} quest</small>
            </div>
            ''', unsafe_allow_html=True)
    
    with col3:
        # AI confidence indicator
        if form_structure.ai_extraction_used:
            confidence = form_structure.extraction_confidence * 100
            st.markdown(f'''
            <div class="stats-card">
                <strong>AI Confidence</strong><br>
                <small>{confidence:.0f}%</small>
            </div>
            ''', unsafe_allow_html=True)
    
    with col4:
        # Overall progress
        total_fields = form_structure.total_fields
        total_mapped = sum(1 for fields in form_structure.parts.values() for f in fields if f.db_path)
        total_quest = sum(1 for fields in form_structure.parts.values() for f in fields if f.is_questionnaire)
        progress = (total_mapped + total_quest) / total_fields if total_fields > 0 else 0
        
        st.markdown(f'''
        <div class="stats-card">
            <strong>{progress*100:.0f}%</strong> complete<br>
            <small>{total_mapped + total_quest}/{total_fields}</small>
        </div>
        ''', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Quick actions
    st.markdown('<div class="action-button-row">', unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🤖 AI Auto-Map All Fields", use_container_width=True, type="primary",
                    help="Use AI to map all unmapped fields across all parts"):
            if 'agents' in st.session_state and 'mapper' in st.session_state.agents:
                with st.spinner("AI mapping fields..."):
                    mapper = st.session_state.agents['mapper']
                    mapper.execute(form_structure, auto_map=True)
                    st.success("✅ AI mapping completed!")
                    st.rerun()
    
    with col2:
        if st.button("📋 All Checkboxes → Quest", use_container_width=True,
                    help="Move all checkboxes/radios to questionnaire"):
            count = 0
            for fields in form_structure.parts.values():
                for field in fields:
                    if field.type in ["checkbox", "radio"] and not field.is_questionnaire:
                        field.is_questionnaire = True
                        field.db_path = None
                        count += 1
            st.success(f"✅ Moved {count} fields to questionnaire")
            st.rerun()
    
    with col3:
        if st.button("📝 All Unmapped → Quest", use_container_width=True,
                    help="Move all unmapped text fields to questionnaire"):
            count = 0
            for fields in form_structure.parts.values():
                for field in fields:
                    if not field.db_path and not field.is_questionnaire:
                        field.is_questionnaire = True
                        count += 1
            st.success(f"✅ Moved {count} fields to questionnaire")
            st.rerun()
    
    with col4:
        if st.button("🔄 Reset Current Part", use_container_width=True,
                    help="Reset all mappings for current part"):
            if selected_part in form_structure.parts:
                for field in form_structure.parts[selected_part]:
                    field.db_path = None
                    field.is_questionnaire = field.type in ["checkbox", "radio"]
                st.success(f"✅ Reset {selected_part}")
                st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Display fields for selected part
    if selected_part and selected_part in form_structure.parts:
        fields = form_structure.parts[selected_part]
        
        # Part header
        st.markdown(f'''
        <div class="part-header">
            <h3>{selected_part}</h3>
            {f'<p>{fields[0].part_title}</p>' if fields and fields[0].part_title else ''}
            <small>{len(fields)} fields extracted</small>
            {f'<span class="ai-badge">AI Enhanced</span>' if form_structure.ai_extraction_used else ''}
        </div>
        ''', unsafe_allow_html=True)
        
        if not fields:
            st.warning(f"No fields found in {selected_part}")
        else:
            # Display each field
            for idx, field in enumerate(fields):
                # Determine status
                if field.db_path:
                    status_class = "mapped"
                    status_text = "✅ Mapped"
                    if field.ai_confidence > 0.5:
                        status_text += f" (AI: {field.ai_confidence*100:.0f}%)"
                elif field.is_questionnaire:
                    status_class = "questionnaire"
                    status_text = "📋 Questionnaire"
                else:
                    status_class = "unmapped"
                    status_text = "❌ Not Mapped"
                
                # Field card
                st.markdown(f'<div class="field-card {status_class}">', unsafe_allow_html=True)
                
                # Main field info row
                col1, col2, col3 = st.columns([3, 4, 2])
                
                with col1:
                    # Field label with item number
                    if field.item_number:
                        st.markdown(f'<span class="item-number">{field.item_number}</span>{field.label}', 
                                  unsafe_allow_html=True)
                    else:
                        st.markdown(f'**{field.label}**')
                    
                    # Field metadata
                    meta_items = [
                        f"Type: {field.type}",
                        f"{field.part}"
                    ]
                    
                    # Show questionnaire key
                    if field.is_questionnaire:
                        st.markdown(f'<span class="questionnaire-key">{field.questionnaire_key}</span>', 
                                  unsafe_allow_html=True)
                    
                    st.markdown(f'<div class="field-info">{" • ".join(meta_items)}</div>', 
                              unsafe_allow_html=True)
                
                with col2:
                    if field.type == "text":
                        # Build options for selectbox
                        options = ["-- Select Database Field --", "📋 Move to Questionnaire"]
                        values = ["", "questionnaire"]
                        
                        # Get grouped paths
                        grouped_paths = get_all_db_paths_grouped()
                        
                        # Build options from grouped paths
                        for path_type, display, value in grouped_paths:
                            if path_type == "group":
                                # Can't use disabled in streamlit selectbox, so use it as a visual separator
                                options.append(display)
                                values.append("")
                            else:
                                options.append(f"    {display}")  # Indent options
                                values.append(value)
                        
                        # Determine current selection
                        if field.is_questionnaire:
                            current_value = "questionnaire"
                        elif field.db_path:
                            current_value = field.db_path
                        else:
                            current_value = ""
                        
                        # Find current index
                        try:
                            current_index = values.index(current_value)
                        except ValueError:
                            current_index = 0
                        
                        # Create unique key for this selectbox
                        select_key = f"map_{field.widget_id}_{idx}_{selected_part}"
                        
                        selected_index = st.selectbox(
                            "Map to",
                            range(len(options)),
                            format_func=lambda x: options[x],
                            index=current_index,
                            key=select_key,
                            label_visibility="collapsed"
                        )
                        
                        selected_value = values[selected_index]
                        
                        # Handle selection change
                        if selected_value != current_value and selected_value != "":
                            if selected_value == "questionnaire":
                                field.is_questionnaire = True
                                field.db_path = None
                                field.questionnaire_type = ":SingleBox"
                            elif not options[selected_index].startswith("═══"):  # Not a group header
                                field.db_path = selected_value
                                field.is_questionnaire = False
                            st.rerun()
                    else:
                        # Checkbox/Radio options
                        include = st.checkbox(
                            "Include in Questionnaire",
                            value=field.is_questionnaire,
                            key=f"quest_{field.widget_id}_{idx}_{selected_part}"
                        )
                        if include != field.is_questionnaire:
                            field.is_questionnaire = include
                            if include:
                                field.db_path = None
                            st.rerun()
                        
                        if field.is_conditional:
                            st.caption("✨ Has conditional logic")
                
                with col3:
                    st.markdown(f"**{status_text}**")
                    if field.ai_suggestion:
                        st.caption(f"💡 {field.ai_suggestion}")
                
                st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.error(f"Part '{selected_part}' not found in form structure!")
    
    return selected_part

def main():
    st.markdown('<div class="main-header"><h1>🤖 Universal USCIS Form Reader</h1><p>Next-Generation AI-Powered Form Processing</p></div>', 
               unsafe_allow_html=True)
    
    # Initialize session state
    if 'form_structure' not in st.session_state:
        st.session_state.form_structure = None
    if 'agents' not in st.session_state:
        st.session_state.agents = {}
    if 'selected_part' not in st.session_state:
        st.session_state.selected_part = "Part 1"
    if 'last_upload_hash' not in st.session_state:
        st.session_state.last_upload_hash = None
    if 'custom_db_fields' not in st.session_state:
        st.session_state.custom_db_fields = {}
    
    # Sidebar
    with st.sidebar:
        st.markdown("## ⚙️ Configuration")
        
        # OpenAI API Key
        api_key = st.text_input(
            "OpenAI API Key",
            type="password",
            value=st.secrets.get("OPENAI_API_KEY", "") if "OPENAI_API_KEY" in st.secrets else "",
            help="Required for AI-enhanced extraction and mapping"
        )
        
        # AI Options
        st.markdown("### 🤖 AI Options")
        use_ai_extraction = st.checkbox("Use AI for extraction", value=True,
                                      help="Enhance field extraction with AI")
        use_ai_mapping = st.checkbox("Use AI for mapping", value=True,
                                   help="Auto-map fields using AI")
        
        # Custom Fields Manager
        if st.session_state.custom_db_fields:
            st.markdown("### 🔧 Custom Fields")
            for path, info in st.session_state.custom_db_fields.items():
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.caption(path)
                with col2:
                    if st.button("❌", key=f"del_{path}"):
                        del st.session_state.custom_db_fields[path]
                        st.rerun()
        
        # Form Info
        form_structure = st.session_state.get('form_structure')
        if form_structure:
            st.markdown("### 📄 Current Form")
            st.info(f"{form_structure.form_number}: {form_structure.form_title}")
            st.caption(f"Form ID: {form_structure.form_hash}")
            
            # Statistics
            st.markdown("### 📊 Statistics")
            col1, col2 = st.columns(2)
            col1.metric("Parts", len(form_structure.parts))
            col2.metric("Fields", form_structure.total_fields)
            
            col1, col2 = st.columns(2)
            mapped = sum(1 for fields in form_structure.parts.values() for f in fields if f.db_path)
            quest = sum(1 for fields in form_structure.parts.values() for f in fields if f.is_questionnaire)
            col1.metric("Mapped", mapped)
            col2.metric("Quest", quest)
            
            # Progress bar
            progress = (mapped + quest) / form_structure.total_fields if form_structure.total_fields > 0 else 0
            st.markdown(f'''
            <div class="progress-bar">
                <div class="progress-fill" style="width: {progress*100}%"></div>
            </div>
            ''', unsafe_allow_html=True)
    
    # Main tabs
    tabs = st.tabs(["📤 Upload & Extract", "🎯 Map Fields", "📥 Export", "📚 Help"])
    
    with tabs[0]:
        st.markdown("## Upload USCIS Form")
        st.info("Upload any USCIS form PDF. The AI will automatically detect the form type and extract all fields.")
        
        uploaded_file = st.file_uploader(
            "Choose a USCIS PDF form",
            type=['pdf'],
            help="Supports all USCIS forms: I-129, I-130, I-140, I-485, I-765, N-400, G-28, etc.",
            key="pdf_uploader"
        )
        
        if uploaded_file:
            # Check if this is a new upload
            file_hash = hashlib.md5(uploaded_file.name.encode()).hexdigest()
            if st.session_state.get('last_upload_hash') != file_hash:
                # Clear previous data
                clear_session_state()
                st.session_state.last_upload_hash = file_hash
            
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.success(f"✅ {uploaded_file.name} ready to process")
            
            with col2:
                if st.button("🚀 Process PDF", type="primary", use_container_width=True):
                    # Initialize agents
                    st.session_state.agents = {
                        'reader': AIEnhancedPDFReader(api_key if use_ai_extraction else None),
                        'mapper': UniversalMappingAgent(api_key),
                        'exporter': UniversalExportAgent()
                    }
                    
                    # Process PDF
                    with st.spinner("Processing PDF..."):
                        form_structure = st.session_state.agents['reader'].execute(
                            uploaded_file, 
                            use_ai=use_ai_extraction
                        )
                        
                        if form_structure:
                            st.session_state.form_structure = form_structure
                            
                            # Set selected part
                            part_numbers = form_structure.get_part_numbers()
                            if part_numbers:
                                st.session_state.selected_part = part_numbers[0]
                            else:
                                st.session_state.selected_part = "Part 1"
                            
                            # Auto-map if enabled
                            if use_ai_mapping and api_key:
                                with st.spinner("AI mapping fields..."):
                                    st.session_state.agents['mapper'].execute(
                                        form_structure, 
                                        auto_map=True
                                    )
                            
                            st.success(f"✅ Successfully processed {form_structure.form_number}")
                            
                            # Show summary
                            with st.expander("📊 Extraction Summary", expanded=True):
                                if form_structure.parts:
                                    cols = st.columns(min(len(form_structure.parts), 4))
                                    for idx, (part, fields) in enumerate(form_structure.parts.items()):
                                        with cols[idx % len(cols)]:
                                            st.metric(part, len(fields))
                                            
                                            # Field type breakdown
                                            types = defaultdict(int)
                                            for field in fields:
                                                types[field.type] += 1
                                            
                                            for t, count in types.items():
                                                st.caption(f"{t}: {count}")
                                else:
                                    st.warning("No fields extracted. The PDF might not contain form fields.")
    
    with tabs[1]:
        form_structure = st.session_state.get('form_structure')
        if form_structure:
            if form_structure.parts:
                st.session_state.selected_part = render_field_mapping(
                    form_structure,
                    st.session_state.get('selected_part', 'Part 1')
                )
            else:
                st.error("No fields found in the form. The PDF might not contain fillable fields.")
        else:
            st.info("👆 Please upload and process a PDF form first")
    
    with tabs[2]:
        form_structure = st.session_state.get('form_structure')
        if form_structure and form_structure.parts:
            st.markdown("## 📥 Export Options")
            st.info("Generate TypeScript and JSON files in the exact format required for your application.")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### TypeScript Export")
                st.markdown("Database field mappings for your application")
                
                if st.button("🔨 Generate TypeScript", use_container_width=True, type="primary"):
                    exporter = st.session_state.agents['exporter']
                    ts_code = exporter.execute(form_structure, "typescript")
                    
                    if ts_code:
                        st.download_button(
                            "⬇️ Download TypeScript File",
                            ts_code,
                            f"{form_structure.form_number}.ts",
                            mime="text/typescript",
                            use_container_width=True
                        )
                        
                        with st.expander("Preview TypeScript", expanded=True):
                            st.code(ts_code, language="typescript")
            
            with col2:
                st.markdown("### JSON Export")
                st.markdown("Questionnaire configuration for dynamic forms")
                
                if st.button("🔨 Generate JSON", use_container_width=True, type="primary"):
                    exporter = st.session_state.agents['exporter']
                    json_code = exporter.execute(form_structure, "json")
                    
                    if json_code:
                        st.download_button(
                            "⬇️ Download JSON File",
                            json_code,
                            f"{form_structure.form_number}-questionnaire.json",
                            mime="application/json",
                            use_container_width=True
                        )
                        
                        with st.expander("Preview JSON", expanded=True):
                            st.code(json_code, language="json")
        else:
            st.info("👆 Please process a form first")
    
    with tabs[3]:
        st.markdown("""
        ## 📚 How to Use
        
        ### 1️⃣ Upload PDF
        - Upload any USCIS form (I-129, I-130, I-539, G-28, N-400, etc.)
        - The AI system automatically detects the exact form type
        - AI analyzes the form structure and extracts all fields with their parts
        
        ### 2️⃣ Map Fields
        - Review extracted fields part by part
        - **Click "🤖 AI Auto-Map All Fields" to automatically map all fields using AI**
        - Database objects are properly grouped in the dropdown (BENEFICIARY, PETITIONER, etc.)
        - Manually adjust mappings as needed using the dropdowns
        - Add custom database fields using the form at the top
        - Move unmapped fields to questionnaire
        
        ### 3️⃣ Export
        - Generate TypeScript file with database mappings
        - Generate JSON file with questionnaire configuration
        - Both formats match your exact requirements
        
        ### 🤖 AI Features
        - **Smart Form Detection**: AI accurately identifies form type (I-539, G-28, etc.)
        - **Intelligent Part Extraction**: AI understands form parts and their context
        - **Context-Aware Mapping**: Uses part descriptions to map fields correctly
        - **One-Click Auto-Mapping**: AI maps all fields across all parts automatically
        - **Field Enhancement**: AI improves field labels and descriptions
        - **Universal Support**: Works with any USCIS form
        - **Confidence Scoring**: Shows AI confidence for each mapping
        
        ### 💡 Tips
        - Enable AI features for best results
        - Use "AI Auto-Map All Fields" button for quick complete mapping
        - Database fields are grouped by object in dropdowns for easy navigation
        - Review AI form analysis to understand the structure
        - Check conditional logic for radio buttons and checkboxes
        - Add custom database fields for form-specific requirements
        
        ### 🐛 Troubleshooting
        - If form type is detected incorrectly, check the AI analysis
        - If dropdown shows empty, ensure fields are extracted properly
        - Edit field attributes directly if labels are incorrect
        - Check extraction logs in the debug panel
        - Some PDFs may require OCR for text extraction
        """)

if __name__ == "__main__":
    main()
