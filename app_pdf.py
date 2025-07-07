import streamlit as st
import json
import re
import fitz  # PyMuPDF
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict, OrderedDict
import openai
from abc import ABC, abstractmethod
import time
import hashlib
from datetime import datetime

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
</style>
""", unsafe_allow_html=True)

# Enhanced Database structure for universal forms
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
    
    # Questionnaire generation
    questionnaire_name: str = ""
    questionnaire_key: str = ""
    control_type: str = ""
    
    def __post_init__(self):
        # Generate unique hash
        if not self.field_hash:
            content = f"{self.name}_{self.part}_{self.page}_{self.item_number}"
            self.field_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        
        # Generate widget ID
        if not self.widget_id:
            self.widget_id = f"{self.part_number}_{self.field_hash}"

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
    
    def __post_init__(self):
        if not self.upload_time:
            self.upload_time = datetime.now().isoformat()
        if not self.form_hash:
            self.form_hash = hashlib.md5(f"{self.form_number}_{self.upload_time}".encode()).hexdigest()[:8]
    
    def get_part_numbers(self) -> List[str]:
        """Get sorted list of part numbers"""
        return sorted(self.parts.keys(), 
                     key=lambda x: int(re.search(r'\d+', x).group() if re.search(r'\d+', x) else 0))
    
    def clear(self):
        """Clear all data"""
        self.parts.clear()
        self.total_fields = 0
        self.total_pages = 0

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
            
            # Detect form type
            form_info = self._detect_form_type(doc)
            form_structure = FormStructure(
                form_number=form_info['number'],
                form_title=form_info['title'],
                total_pages=len(doc),
                ai_extraction_used=use_ai and self.api_key is not None
            )
            
            self.update_status("active", f"Processing {form_info['number']} - {form_info['title']}")
            
            # Extract text for AI context
            full_text = ""
            if use_ai and self.api_key:
                for page in doc:
                    full_text += page.get_text() + "\n"
            
            # Extract fields by parts
            current_part = "Part 1"
            current_part_number = 1
            current_part_title = ""
            seen_fields = set()
            
            # Use AI to understand form structure
            if use_ai and self.api_key and full_text:
                parts_info = self._ai_extract_parts(full_text[:3000])  # First 3000 chars
                self.update_status("active", "AI analyzing form structure...")
            else:
                parts_info = None
            
            # Process each page
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_text = page.get_text()
                
                # Update part information
                part_info = self._detect_current_part(page_text, current_part_number)
                if part_info:
                    current_part = part_info['part']
                    current_part_number = part_info['number']
                    current_part_title = part_info['title']
                
                # Extract widgets
                widgets = page.widgets()
                if widgets:
                    if current_part not in form_structure.parts:
                        form_structure.parts[current_part] = []
                    
                    # Process widgets with AI enhancement
                    for widget in widgets:
                        if widget and hasattr(widget, 'field_name'):
                            field = self._extract_field_with_ai(
                                widget, 
                                page_num + 1, 
                                current_part, 
                                current_part_number,
                                current_part_title,
                                page_text if use_ai else None
                            )
                            
                            if field and field.field_hash not in seen_fields:
                                seen_fields.add(field.field_hash)
                                form_structure.parts[current_part].append(field)
                                form_structure.total_fields += 1
            
            doc.close()
            
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
            
            self.update_status("completed", 
                             f"Extracted {form_structure.total_fields} fields from {len(form_structure.parts)} parts")
            
            return form_structure
            
        except Exception as e:
            self.update_status("error", f"Failed: {str(e)}")
            st.error(f"Error processing PDF: {str(e)}")
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
        
        # Check for form numbers
        for form_num, title in forms.items():
            if form_num in first_pages_text:
                # Try to extract revision date
                rev_match = re.search(r'Edition\s+(\d+/\d+/\d+)', first_pages_text)
                if rev_match:
                    title += f" (Rev. {rev_match.group(1)})"
                return {'number': form_num, 'title': title}
        
        # Check for supplement forms
        if 'H CLASSIFICATION SUPPLEMENT' in first_pages_text:
            return {'number': 'I-129H', 'title': 'H Classification Supplement to Form I-129'}
        elif 'L CLASSIFICATION SUPPLEMENT' in first_pages_text:
            return {'number': 'I-129L', 'title': 'L Classification Supplement to Form I-129'}
        
        return {'number': 'Unknown', 'title': 'Unknown USCIS Form'}
    
    def _detect_current_part(self, page_text: str, current_number: int) -> Optional[Dict]:
        """Detect part information from page text"""
        patterns = [
            r'Part\s+(\d+)\.?\s*[–-]?\s*([^\n]{0,100})',
            r'PART\s+(\d+)\.?\s*[–-]?\s*([^\n]{0,100})',
            r'Section\s+(\d+)\.?\s*[–-]?\s*([^\n]{0,100})',
        ]
        
        for pattern in patterns:
            matches = list(re.finditer(pattern, page_text, re.MULTILINE))
            if matches:
                match = matches[0]
                part_num = int(match.group(1))
                if part_num != current_number:
                    title = match.group(2).strip()
                    # Clean title
                    title = re.sub(r'[.\s]+$', '', title)
                    title = re.sub(r'\s+', ' ', title)
                    
                    return {
                        'part': f"Part {part_num}",
                        'number': part_num,
                        'title': title
                    }
        
        return None
    
    def _ai_extract_parts(self, text: str) -> Optional[Dict]:
        """Use AI to understand form structure"""
        if not self.api_key:
            return None
        
        try:
            prompt = f"""
            Analyze this USCIS form text and identify the parts/sections structure.
            
            Text:
            {text}
            
            Return a JSON object with parts information:
            {{
                "parts": [
                    {{"number": 1, "title": "Information About You", "description": "..."}},
                    ...
                ]
            }}
            """
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=500
            )
            
            return json.loads(response.choices[0].message.content)
            
        except:
            return None
    
    def _extract_field_with_ai(self, widget, page: int, part: str, part_number: int, 
                              part_title: str, page_text: Optional[str]) -> Optional[ExtractedField]:
        """Extract field with AI enhancement"""
        try:
            if not widget.field_name:
                return None
            
            # Basic extraction
            field_name = widget.field_name
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
                quest_name = f"{item_number.replace('.', '_')}"
                quest_key = f"pt{part_number}_{item_number.replace('.', '')}"
            else:
                quest_name = clean_name[:20]
                quest_key = f"pt{part_number}_{clean_name[:10]}"
            
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
                is_questionnaire=field_type in ["checkbox", "radio"],
                questionnaire_name=quest_name,
                questionnaire_key=quest_key,
                control_type=control_type_map.get(field_type, 'text'),
                ai_confidence=0.8 if page_text and self.api_key else 0.0
            )
            
            # Check for conditional logic
            if field_type in ["checkbox", "radio"] and item_number:
                field.is_conditional = True
            
            return field
            
        except Exception:
            return None
    
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
            r'\[0\]'
        ]
        
        for prefix in prefixes:
            clean = re.sub(prefix, '', clean, flags=re.IGNORECASE)
        
        # Clean up
        clean = clean.strip('.')
        
        return clean
    
    def _extract_item_number(self, field_name: str, clean_name: str) -> str:
        """Extract item number from field name"""
        patterns = [
            r'(?:^|[^\d])(\d+)\.([a-z])\b',  # 1.a, 2.b
            r'(?:^|[^\d])(\d+)([a-z])\b',     # 1a, 2b
            r'^\s*(\d+)\s*$',                 # Just numbers
        ]
        
        # Try original name first
        for text in [field_name, clean_name]:
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    if len(match.groups()) == 2:
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
            'email': 'Email Address'
        }
        
        label_lower = label.lower()
        for old, new in replacements.items():
            if old in label_lower:
                return new
        
        return label.title()
    
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
            if 'date' in name_lower:
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
        
        # Process in batches for efficiency
        for part_name, fields in form_structure.parts.items():
            self.update_status("active", f"Mapping {part_name}...")
            
            # Group text fields for batch processing
            text_fields = [f for f in fields if f.type == "text" and not f.db_path]
            
            if text_fields:
                # Try pattern matching first
                for field in text_fields:
                    suggestion = self._pattern_match(field, form_structure.form_number)
                    if suggestion:
                        field.db_path = suggestion
                        field.ai_confidence = 0.9
                        total_mapped += 1
                
                # Use AI for remaining fields
                if self.api_key:
                    unmapped = [f for f in text_fields if not f.db_path]
                    if unmapped:
                        mapped = self._batch_ai_mapping(unmapped, form_structure.form_number)
                        total_mapped += mapped
        
        self.update_status("completed", 
                          f"Mapped {total_mapped} fields ({total_mapped/total_fields*100:.1f}% success rate)")
    
    def _pattern_match(self, field: ExtractedField, form_type: str) -> Optional[str]:
        """Enhanced pattern matching for universal forms"""
        label_lower = field.label.lower()
        name_lower = field.name.lower()
        combined = f"{label_lower} {name_lower}"
        
        # Universal patterns
        patterns = {
            # Names
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
                # Adjust path based on form context
                if form_type == "G-28" and "beneficiary" in db_path:
                    # G-28 uses customer instead of beneficiary
                    db_path = db_path.replace("beneficiary.", "customer.")
                
                return db_path
        
        return None
    
    def _batch_ai_mapping(self, fields: List[ExtractedField], form_type: str) -> int:
        """Batch process fields with AI"""
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
            
            # Get all possible DB paths
            db_paths = []
            for obj, cats in UNIVERSAL_DB_STRUCTURE.items():
                for cat, fields_list in cats.items():
                    for field in fields_list:
                        path = f"{obj}.{cat}.{field}" if cat else f"{obj}.{field}"
                        db_paths.append(path)
            
            prompt = f"""
            You are mapping fields from USCIS form {form_type} to database paths.
            
            Fields to map:
            {json.dumps(field_info, indent=2)}
            
            Available database paths:
            {json.dumps(db_paths, indent=2)}
            
            Return a JSON object mapping field labels to database paths.
            Only include fields that have clear matches.
            
            Example:
            {{"First Name": "beneficiary.Beneficiary.beneficiaryFirstName"}}
            """
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=500
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
                    # Add to questionnaire
                    sections['questionnaireData'][field.questionnaire_key] = f"{field.questionnaire_name}:ConditionBox"
                    
                    # Track conditionals
                    if field.type == "radio":
                        group_name = re.sub(r'\d+.*', '', field.questionnaire_name)
                        conditional_groups[group_name].append(field)
        
        # Generate conditional data
        for group, fields in conditional_groups.items():
            for field in fields:
                if field.type == "radio":
                    value = field.item_number.split('.')[0] if field.item_number else "1"
                    sections['conditionalData'][field.questionnaire_key] = {
                        "condition": f"{group}=={value}",
                        "conditionTrue": value,
                        "conditionFalse": "",
                        "conditionType": "CheckBox",
                        "conditionParam": "",
                        "conditionData": ""
                    }
                elif field.type == "checkbox" and field.is_conditional:
                    sections['conditionalData'][field.questionnaire_key] = {
                        "condition": f"{field.questionnaire_name}==true",
                        "conditionTrue": "true",
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
                        group = re.sub(r'\d+.*', '', field.questionnaire_name)
                        radio_groups[group].append(field)
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
                control["validators"]["maxLength"] = "50"
        else:
            control["style"] = {"col": "12"}
        
        return control
    
    def _create_radio_control(self, field: ExtractedField, group: str) -> dict:
        """Create radio button control"""
        label = field.label
        if field.item_number:
            label = f"{field.item_number}. {label}"
        
        value = field.item_number.split('.')[0] if field.item_number else "1"
        
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

# Main UI Functions
def clear_session_state():
    """Clear all session state data"""
    keys_to_clear = ['form_structure', 'agents', 'selected_part', 'last_upload_hash']
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]

def render_field_mapping(form_structure: FormStructure, selected_part: str):
    """Render field mapping interface"""
    st.markdown("## 🎯 Field Mapping Interface")
    
    # Part selector
    st.markdown('<div class="part-selector">', unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
    
    with col1:
        part_options = form_structure.get_part_numbers()
        selected_part = st.selectbox(
            "📑 Select Part to View",
            part_options,
            index=part_options.index(selected_part) if selected_part in part_options else 0,
            key="part_selector"
        )
    
    with col2:
        if selected_part in form_structure.parts:
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
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🤖 AI Auto-Map", use_container_width=True, 
                    help="Use AI to map all unmapped fields"):
            if 'agents' in st.session_state and 'mapper' in st.session_state.agents:
                mapper = st.session_state.agents['mapper']
                mapper.execute(form_structure, auto_map=True)
                st.rerun()
    
    with col2:
        if st.button("📋 Checkboxes → Quest", use_container_width=True,
                    help="Move all checkboxes/radios to questionnaire"):
            count = 0
            for fields in form_structure.parts.values():
                for field in fields:
                    if field.type in ["checkbox", "radio"] and not field.is_questionnaire:
                        field.is_questionnaire = True
                        count += 1
            st.success(f"Moved {count} fields")
            st.rerun()
    
    with col3:
        if st.button("📝 Unmapped → Quest", use_container_width=True,
                    help="Move all unmapped text fields to questionnaire"):
            count = 0
            for fields in form_structure.parts.values():
                for field in fields:
                    if not field.db_path and not field.is_questionnaire:
                        field.is_questionnaire = True
                        count += 1
            st.success(f"Moved {count} fields")
            st.rerun()
    
    with col4:
        if st.button("🔄 Reset Part", use_container_width=True,
                    help="Reset mappings for current part"):
            if selected_part in form_structure.parts:
                for field in form_structure.parts[selected_part]:
                    field.db_path = None
                    field.is_questionnaire = field.type in ["checkbox", "radio"]
                st.rerun()
    
    # Display fields for selected part
    if selected_part in form_structure.parts:
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
                    f"Page: {field.page}"
                ]
                if field.questionnaire_key:
                    meta_items.append(f"Key: {field.questionnaire_key}")
                
                st.markdown(f'<div class="field-info">{" • ".join(meta_items)}</div>', 
                          unsafe_allow_html=True)
            
            with col2:
                if field.type == "text":
                    # Database mapping
                    db_options = ["-- Select Database Field --", "📋 Move to Questionnaire", "---"]
                    
                    # Group by object
                    for obj, cats in UNIVERSAL_DB_STRUCTURE.items():
                        obj_paths = []
                        for cat, fields_list in cats.items():
                            for f in fields_list:
                                path = f"{obj}.{cat}.{f}" if cat else f"{obj}.{f}"
                                obj_paths.append(path)
                        
                        if obj_paths:
                            db_options.append(f"=== {obj.upper()} ===")
                            db_options.extend(sorted(obj_paths))
                    
                    current = field.db_path if field.db_path else "-- Select Database Field --"
                    if field.is_questionnaire:
                        current = "📋 Move to Questionnaire"
                    
                    selected = st.selectbox(
                        "Map to",
                        db_options,
                        index=db_options.index(current) if current in db_options else 0,
                        key=f"map_{field.widget_id}_{idx}",
                        label_visibility="collapsed"
                    )
                    
                    if selected != current and not selected.startswith("===") and selected != "---":
                        if selected == "📋 Move to Questionnaire":
                            field.is_questionnaire = True
                            field.db_path = None
                        elif selected != "-- Select Database Field --":
                            field.db_path = selected
                            field.is_questionnaire = False
                        st.rerun()
                else:
                    # Checkbox/Radio options
                    include = st.checkbox(
                        "Include in Questionnaire",
                        value=field.is_questionnaire,
                        key=f"quest_{field.widget_id}_{idx}"
                    )
                    if include != field.is_questionnaire:
                        field.is_questionnaire = include
                        st.rerun()
                    
                    if field.is_conditional:
                        st.caption("✨ Has conditional logic")
            
            with col3:
                st.markdown(f"**{status_text}**")
                if field.ai_suggestion:
                    st.caption(f"💡 {field.ai_suggestion}")
            
            st.markdown('</div>', unsafe_allow_html=True)
    
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
    
    # Sidebar
    with st.sidebar:
        st.markdown("## ⚙️ Configuration")
        
        # OpenAI API Key
        api_key = st.text_input(
            "OpenAI API Key",
            type="password",
            value=st.secrets.get("OPENAI_API_KEY", ""),
            help="Required for AI-enhanced extraction and mapping"
        )
        
        # AI Options
        st.markdown("### 🤖 AI Options")
        use_ai_extraction = st.checkbox("Use AI for extraction", value=True,
                                      help="Enhance field extraction with AI")
        use_ai_mapping = st.checkbox("Use AI for mapping", value=True,
                                   help="Auto-map fields using AI")
        
        # Agent Status
        if st.session_state.agents:
            st.markdown("### 📊 Agent Status")
            for name, agent in st.session_state.agents.items():
                st.markdown(f"**{name}**")
                st.caption(f"Status: {agent.status}")
                if agent.last_action:
                    st.caption(f"Last: {agent.last_action}")
        
        # Form Info
        if st.session_state.form_structure:
            st.markdown("### 📄 Current Form")
            form = st.session_state.form_structure
            st.info(f"{form.form_number}: {form.form_title}")
            st.caption(f"Form ID: {form.form_hash}")
            
            # Statistics
            st.markdown("### 📊 Statistics")
            col1, col2 = st.columns(2)
            col1.metric("Parts", len(form.parts))
            col2.metric("Fields", form.total_fields)
            
            col1, col2 = st.columns(2)
            mapped = sum(1 for fields in form.parts.values() for f in fields if f.db_path)
            quest = sum(1 for fields in form.parts.values() for f in fields if f.is_questionnaire)
            col1.metric("Mapped", mapped)
            col2.metric("Quest", quest)
    
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
            if st.session_state.last_upload_hash != file_hash:
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
                            st.session_state.selected_part = form_structure.get_part_numbers()[0]
                            
                            # Auto-map if enabled
                            if use_ai_mapping and api_key:
                                st.session_state.agents['mapper'].execute(
                                    form_structure, 
                                    auto_map=True
                                )
                            
                            st.success(f"✅ Successfully processed {form_structure.form_number}")
                            st.balloons()
                            
                            # Show summary
                            with st.expander("📊 Extraction Summary", expanded=True):
                                cols = st.columns(len(form_structure.parts))
                                for idx, (part, fields) in enumerate(form_structure.parts.items()):
                                    with cols[idx % len(cols)]:
                                        st.metric(part, len(fields))
                                        
                                        # Field type breakdown
                                        types = defaultdict(int)
                                        for field in fields:
                                            types[field.type] += 1
                                        
                                        for t, count in types.items():
                                            st.caption(f"{t}: {count}")
    
    with tabs[1]:
        if st.session_state.form_structure:
            st.session_state.selected_part = render_field_mapping(
                st.session_state.form_structure,
                st.session_state.selected_part
            )
        else:
            st.info("👆 Please upload and process a PDF form first")
    
    with tabs[2]:
        if st.session_state.form_structure:
            st.markdown("## 📥 Export Options")
            st.info("Generate TypeScript and JSON files in the exact format required for your application.")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### TypeScript Export")
                st.markdown("Database field mappings for your application")
                
                if st.button("🔨 Generate TypeScript", use_container_width=True, type="primary"):
                    exporter = st.session_state.agents['exporter']
                    ts_code = exporter.execute(st.session_state.form_structure, "typescript")
                    
                    if ts_code:
                        st.download_button(
                            "⬇️ Download TypeScript File",
                            ts_code,
                            f"{st.session_state.form_structure.form_number}.ts",
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
                    json_code = exporter.execute(st.session_state.form_structure, "json")
                    
                    if json_code:
                        st.download_button(
                            "⬇️ Download JSON File",
                            json_code,
                            f"{st.session_state.form_structure.form_number}-questionnaire.json",
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
        - Upload any USCIS form (I-129, I-130, G-28, N-400, etc.)
        - The system automatically detects the form type
        - AI extracts all fields with their labels and types
        
        ### 2️⃣ Map Fields
        - Review extracted fields part by part
        - Fields are automatically mapped to database objects using AI
        - Manually adjust mappings as needed
        - Move unmapped fields to questionnaire
        
        ### 3️⃣ Export
        - Generate TypeScript file with database mappings
        - Generate JSON file with questionnaire configuration
        - Both formats match your exact requirements
        
        ### 🤖 AI Features
        - **Smart Extraction**: AI understands form context and improves label extraction
        - **Intelligent Mapping**: Automatically maps fields to correct database paths
        - **Universal Support**: Works with any USCIS form
        - **Confidence Scoring**: Shows AI confidence for each mapping
        
        ### 💡 Tips
        - Enable AI features for best results
        - Review AI suggestions before exporting
        - Use "Move to Questionnaire" for dynamic fields
        - Check conditional logic for radio buttons and checkboxes
        """)

if __name__ == "__main__":
    main()
