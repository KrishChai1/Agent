import streamlit as st
import json
import re
import fitz  # PyMuPDF
import os
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field, asdict
from collections import defaultdict, OrderedDict
from abc import ABC, abstractmethod
import time
import hashlib
from datetime import datetime
import traceback
import openai
openai.api_key = st.secrets["OPENAI_API_KEY"]

response = openai.ChatCompletion.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "Hello"}]
)


# Configure page
st.set_page_config(
    page_title="Smart USCIS Form Reader - Multi-Agent System",
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
    .agent-card {
        background: white;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .agent-active {
        border-left: 4px solid #4CAF50;
        background: #f1f8f4;
    }
    .agent-error {
        border-left: 4px solid #f44336;
        background: #fef1f1;
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
    .item-number {
        font-weight: bold;
        color: #1976D2;
        margin-right: 0.5rem;
        font-size: 1.1rem;
    }
    .validation-badge {
        background: #4CAF50;
        color: white;
        padding: 0.2rem 0.6rem;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 500;
        display: inline-block;
        margin-left: 0.5rem;
    }
    .manual-mapping-section {
        background: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
        border: 2px dashed #667eea;
    }
    .checkbox-field {
        background: #e3f2fd;
        border-left: 4px solid #2196F3;
        padding: 0.5rem;
        margin: 0.3rem 0;
        border-radius: 4px;
    }
    .radio-field {
        background: #f3e5f5;
        border-left: 4px solid #9c27b0;
        padding: 0.5rem;
        margin: 0.3rem 0;
        border-radius: 4px;
    }
    .field-type-badge {
        padding: 0.2rem 0.5rem;
        border-radius: 4px;
        font-size: 0.75rem;
        display: inline-block;
        margin-left: 0.5rem;
    }
    .type-text { background: #e8f5e9; color: #2e7d32; }
    .type-checkbox { background: #e3f2fd; color: #1565c0; }
    .type-radio { background: #f3e5f5; color: #6a1b9a; }
    .type-date { background: #fff3e0; color: #e65100; }
    .agent-log {
        background: #f5f5f5;
        padding: 0.5rem;
        margin: 0.2rem 0;
        border-radius: 4px;
        font-size: 0.85rem;
    }
    .extraction-preview {
        background: #e8f5e9;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
        border-left: 4px solid #4caf50;
    }
</style>
""", unsafe_allow_html=True)

# Initialize OpenAI client
def get_openai_client():
    """Get OpenAI client from secrets or environment"""
    if not OPENAI_AVAILABLE:
        return None
        
    try:
        # Try multiple ways to get the API key
        api_key = None
        
        # Method 1: Direct access
        if hasattr(st, 'secrets') and 'OPENAI_API_KEY' in st.secrets:
            api_key = st.secrets['OPENAI_API_KEY']
        
        # Method 2: Using get method
        if not api_key:
            api_key = st.secrets.get('OPENAI_API_KEY', None)
        
        # Method 3: Try lowercase
        if not api_key:
            api_key = st.secrets.get('openai_api_key', None)
        
        # Method 4: Environment variable
        if not api_key:
            import os
            api_key = os.environ.get('OPENAI_API_KEY', None)
        
        if api_key:
            return OpenAI(api_key=api_key)
        return None
    except Exception as e:
        st.error(f"Error loading OpenAI client: {str(e)}")
        return None

# Enhanced Database structure
UNIVERSAL_DB_STRUCTURE = {
    "beneficiary": {
        "PersonalInfo": ["beneficiaryFirstName", "beneficiaryLastName", "beneficiaryMiddleName", 
                        "beneficiaryDateOfBirth", "beneficiaryGender", "beneficiarySsn",
                        "alienNumber", "alienRegistrationNumber", "uscisOnlineAccountNumber",
                        "beneficiaryCountryOfBirth", "beneficiaryCitizenOfCountry",
                        "maritalStatus", "numberOfChildren"],
        "MailingAddress": ["addressStreet", "addressCity", "addressState", "addressZip", 
                          "addressCountry", "addressAptSteFlrNumber", "addressNumber", "addressType",
                          "inCareOfName", "addressProvince", "addressPostalCode"],
        "PhysicalAddress": ["physicalAddressStreet", "physicalAddressCity", "physicalAddressState", 
                           "physicalAddressZip", "physicalAddressCountry", "physicalAddressAptSteFlrNumber"],
        "ContactInfo": ["daytimeTelephoneNumber", "mobileTelephoneNumber", "emailAddress",
                       "workPhone", "eveningPhone", "faxNumber"],
        "PassportDetails": ["passportNumber", "passportIssueCountry", "passportIssueDate", 
                           "passportExpiryDate", "travelDocumentNumber"],
        "VisaDetails": ["currentNonimmigrantStatus", "dateStatusExpires", "visaNumber",
                       "visaIssueDate", "consulateLocation", "i94ArrivalDepartureNumber",
                       "dateOfLastArrival", "durationOfStatus"]
    },
    "petitioner": {
        "PersonalInfo": ["familyName", "givenName", "middleName", "companyOrOrganizationName",
                        "petitionerType", "dateOfBirth", "ssn", "ein"],
        "ContactInfo": ["daytimeTelephoneNumber", "mobileTelephoneNumber", "emailAddress",
                       "workPhone", "faxNumber"],
        "Address": ["addressStreet", "addressCity", "addressState", "addressZip", 
                   "addressCountry", "addressNumber", "addressType"]
    },
    "case": {
        "ProcessingInfo": ["requestedAction", "extensionDate", "changeOfStatusTo", 
                          "reinstatementToStudentStatus", "numberOfPeopleInApplication"],
        "RelatedForms": ["basedOnExtensionGrantedToFamily", "separatePetitionFiled",
                        "formType", "receiptNumber", "dateFiledPreviousForm"],
        "SchoolInfo": ["schoolName", "sevisIdNumber"]
    }
}

# Initialize session state for custom fields
if 'custom_db_fields' not in st.session_state:
    st.session_state.custom_db_fields = {}

@dataclass
class ExtractedField:
    """Enhanced field with validation and accurate extraction"""
    # Basic info
    name: str
    label: str
    type: str  # text, checkbox, radio, date, number, signature
    value: str = ""
    
    # Accurate location info
    page: int = 1
    part: str = "Part 1"
    part_number: int = 1
    part_title: str = ""
    item_number: str = ""  # e.g., "1.a", "1.b", "5", "11"
    
    # Field identification
    field_id: str = ""
    field_hash: str = ""
    raw_field_name: str = ""
    
    # Mapping info
    db_path: Optional[str] = None
    is_questionnaire: bool = False
    manually_assigned: bool = False
    manual_assignment_type: str = ""  # "database" or "questionnaire"
    
    # Validation info
    is_validated: bool = False
    validation_confidence: float = 0.0
    
    # Questionnaire info
    questionnaire_key: str = ""
    questionnaire_type: str = ""
    control_type: str = ""
    
    # AI metadata
    ai_confidence: float = 0.0
    ai_suggestion: Optional[str] = None
    
    def __post_init__(self):
        # Generate unique field ID based on part and item number
        if self.item_number:
            self.field_id = f"pt{self.part_number}_{self.item_number.replace('.', '')}"
        else:
            self.field_id = f"pt{self.part_number}_field_{self.name[:10]}"
        
        # Generate field hash for true uniqueness
        if not self.field_hash:
            content = f"{self.name}_{self.part}_{self.page}_{self.item_number}_{self.label}_{time.time()}"
            self.field_hash = hashlib.md5(content.encode()).hexdigest()[:12]
        
        # Append hash to field_id to ensure uniqueness
        self.field_id = f"{self.field_id}_{self.field_hash[:6]}"
        
        # Set questionnaire key
        self.questionnaire_key = self.field_id
        
        # Set questionnaire type based on field type
        type_mapping = {
            "text": (":SingleBox", "text"),
            "checkbox": (":ConditionBox", "colorSwitch"),
            "radio": (":ConditionBox", "radio"),
            "date": (":Date", "date"),
            "number": (":TextBox", "text"),
            "signature": (":SignatureBox", "signature")
        }
        
        self.questionnaire_type, self.control_type = type_mapping.get(self.type, (":TextBox", "text"))

@dataclass
class FormStructure:
    """Form structure with validation tracking"""
    form_number: str
    form_title: str
    form_edition: str = ""
    total_pages: int = 0
    parts: Dict[str, List[ExtractedField]] = field(default_factory=OrderedDict)
    
    # Agent tracking
    agent_logs: Dict[str, List[str]] = field(default_factory=dict)
    
    # Statistics
    total_fields: int = 0
    validated_fields: int = 0
    mapped_fields: int = 0
    questionnaire_fields: int = 0
    manually_assigned_fields: int = 0
    
    # Validation
    is_validated: bool = False
    validation_score: float = 0.0
    validation_issues: List[str] = field(default_factory=list)
    
    def add_agent_log(self, agent_name: str, message: str):
        """Add log from specific agent"""
        if agent_name not in self.agent_logs:
            self.agent_logs[agent_name] = []
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.agent_logs[agent_name].append(f"{timestamp} - {message}")

# Base Agent Class
class Agent(ABC):
    """Base agent with enhanced logging"""
    
    def __init__(self, name: str, role: str):
        self.name = name
        self.role = role
        self.status = "idle"
        self.logs = []
        
    @abstractmethod
    def execute(self, *args, **kwargs) -> Any:
        """Execute agent's main task"""
        pass
    
    def log(self, message: str, level: str = "info"):
        """Add log entry and display in UI"""
        self.logs.append({
            "timestamp": datetime.now().strftime('%H:%M:%S'),
            "message": message,
            "level": level
        })
        
        # Display in UI container
        if 'agent_status_container' in st.session_state:
            container = st.session_state.agent_status_container
            with container:
                if level == "error":
                    st.error(f"🔴 **{self.name}**: {message}")
                elif level == "success":
                    st.success(f"🟢 **{self.name}**: {message}")
                elif level == "warning":
                    st.warning(f"🟡 **{self.name}**: {message}")
                else:
                    st.info(f"ℹ️ **{self.name}**: {message}")

# Research Agent - Smart field extraction
class ResearchAgent(Agent):
    """Intelligent field extraction with accurate item number recognition"""
    
    def __init__(self):
        super().__init__("Research Agent", "Field Extraction & Analysis")
        # Try to get client from session state first, then from secrets
        self.client = st.session_state.get('openai_client', None) or get_openai_client()
    
    def execute(self, pdf_file, use_ai: bool = True) -> Optional[FormStructure]:
        """Extract fields with intelligent parsing"""
        self.status = "active"
        self.log("Starting intelligent field extraction...")
        
        try:
            pdf_bytes = pdf_file.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            # Step 1: Identify form
            form_info = self._identify_form(doc)
            self.log(f"Identified form: {form_info['number']} - {form_info['title']}", "success")
            
            form_structure = FormStructure(
                form_number=form_info['number'],
                form_title=form_info['title'],
                form_edition=form_info.get('edition', ''),
                total_pages=len(doc)
            )
            
            # Step 2: Extract all text content
            full_text = ""
            page_texts = []
            for page in doc:
                text = page.get_text()
                full_text += text + "\n"
                page_texts.append(text)
            
            # Step 3: AI analysis if available
            ai_parts = None
            if use_ai and self.client:
                ai_parts = self._ai_extract_parts(full_text[:15000], form_info['number'])
                if ai_parts:
                    self.log("AI part structure analysis completed", "success")
            
            # Step 4: Extract fields intelligently
            self._extract_fields_smart(form_structure, doc, page_texts, ai_parts)
            
            doc.close()
            
            form_structure.add_agent_log(self.name, f"Extracted {form_structure.total_fields} fields")
            self.log(f"Extraction complete: {form_structure.total_fields} fields found", "success")
            
            self.status = "completed"
            return form_structure
            
        except Exception as e:
            self.log(f"Extraction failed: {str(e)}", "error")
            self.status = "error"
            return None
    
    def _identify_form(self, doc) -> Dict:
        """Identify form type and metadata"""
        first_page_text = doc[0].get_text().upper()
        
        # Common USCIS forms
        form_mapping = {
            'I-539': 'Application to Extend/Change Nonimmigrant Status',
            'I-824': 'Application for Action on an Approved Application or Petition',
            'I-129': 'Petition for a Nonimmigrant Worker',
            'I-130': 'Petition for Alien Relative',
            'I-140': 'Immigrant Petition for Alien Worker',
            'I-485': 'Application to Register Permanent Residence',
            'I-765': 'Application for Employment Authorization',
            'N-400': 'Application for Naturalization',
            'G-28': 'Notice of Entry of Appearance as Attorney'
        }
        
        form_info = {"number": "Unknown", "title": "Unknown Form", "edition": ""}
        
        # Find form number
        for form_num, title in form_mapping.items():
            if form_num in first_page_text:
                form_info["number"] = form_num
                form_info["title"] = title
                break
        
        # Extract edition
        edition_match = re.search(r'EDITION\s+(\d{2}/\d{2}/\d{2})', first_page_text)
        if edition_match:
            form_info["edition"] = edition_match.group(1)
        
        return form_info
    
    def _ai_extract_parts(self, text: str, form_number: str) -> Optional[Dict[str, Dict]]:
        """Use AI to extract form parts and their fields"""
        if not self.client:
            return None
        
        try:
            prompt = f"""
            Analyze this USCIS {form_number} form and extract the exact part structure with fields.
            
            Text:
            {text}
            
            Extract and return a JSON object with the following structure:
            {{
                "Part 1": {{
                    "title": "Information About You",
                    "fields": [
                        {{"item": "1.a", "label": "Family Name (Last Name)", "type": "text"}},
                        {{"item": "1.b", "label": "Given Name (First Name)", "type": "text"}},
                        {{"item": "1.c", "label": "Middle Name", "type": "text"}},
                        {{"item": "2", "label": "Alien Registration Number (A-Number)", "type": "text"}},
                        {{"item": "3", "label": "USCIS Online Account Number", "type": "text"}}
                    ]
                }},
                "Part 2": {{
                    "title": "Application Type",
                    "fields": [
                        {{"item": "1", "label": "I am applying to", "type": "checkbox"}}
                    ]
                }}
            }}
            
            Rules:
            1. Include ALL parts found in the form
            2. For each part, include the exact title and all fields
            3. Use exact item numbers as they appear (e.g., "1.a", "1.b", "2", "10")
            4. Identify field types: text, checkbox, radio, date, signature
            5. Include the exact label text for each field
            
            Return ONLY valid JSON, no explanation.
            """
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert at analyzing USCIS forms and extracting structured data."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=2000
            )
            
            # Parse response
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            self.log(f"AI part extraction error: {str(e)}", "warning")
            return None
    
    def _extract_fields_smart(self, form_structure: FormStructure, doc, page_texts: List[str], ai_parts: Optional[Dict]):
        """Smart field extraction with AI-enhanced part detection"""
        
        # If we have AI parts, use them
        if ai_parts:
            self._extract_using_ai_parts(form_structure, doc, page_texts, ai_parts)
        else:
            # Fallback to pattern-based extraction
            self._extract_using_patterns(form_structure, doc, page_texts)
    
    def _extract_using_ai_parts(self, form_structure: FormStructure, doc, page_texts: List[str], ai_parts: Dict):
        """Extract fields using AI-identified parts"""
        
        # Process each part from AI
        for part_name, part_info in ai_parts.items():
            part_number = int(re.search(r'Part (\d+)', part_name).group(1)) if 'Part' in part_name else 1
            part_title = part_info.get('title', '')
            
            # Create part if not exists
            if part_name not in form_structure.parts:
                form_structure.parts[part_name] = []
                self.log(f"Processing {part_name}: {part_title}")
            
            # Add fields from AI analysis
            for field_info in part_info.get('fields', []):
                field = ExtractedField(
                    name=f"field_{field_info['item'].replace('.', '_')}",
                    label=field_info['label'],
                    type=field_info['type'],
                    page=1,  # Will be updated when we find it in PDF
                    part=part_name,
                    part_number=part_number,
                    part_title=part_title,
                    item_number=field_info['item']
                )
                
                # Auto-assign checkboxes to questionnaire
                if field.type in ["checkbox", "radio"]:
                    field.is_questionnaire = True
                
                form_structure.parts[part_name].append(field)
                form_structure.total_fields += 1
        
        # Now try to find these fields in the actual PDF
        self._match_fields_to_pages(form_structure, doc, page_texts)
    
    def _extract_using_patterns(self, form_structure: FormStructure, doc, page_texts: List[str]):
        """Fallback pattern-based extraction"""
        current_part = None
        current_part_number = 0
        current_part_title = ""
        
        for page_num, page in enumerate(doc):
            page_text = page_texts[page_num]
            
            # Detect part changes - improved pattern
            part_patterns = [
                r'Part\s+(\d+)\.?\s*[-–]\s*([^\n]+)',  # Part 1 - Title
                r'Part\s+(\d+)\.?\s+([^\n]+)',         # Part 1. Title
                r'PART\s+(\d+)\.?\s*[-–]\s*([^\n]+)',  # PART 1 - Title
                r'PART\s+(\d+)\.?\s+([^\n]+)'          # PART 1 Title
            ]
            
            for pattern in part_patterns:
                part_matches = re.finditer(pattern, page_text, re.IGNORECASE)
                for match in part_matches:
                    part_num = int(match.group(1))
                    part_title = match.group(2).strip()
                    
                    # Clean title
                    part_title = re.sub(r'\s+', ' ', part_title)
                    part_title = part_title.strip('.')
                    
                    if part_num != current_part_number:
                        current_part_number = part_num
                        current_part = f"Part {part_num}"
                        current_part_title = part_title
                        
                        if current_part not in form_structure.parts:
                            form_structure.parts[current_part] = []
                            self.log(f"Found {current_part}: {part_title}")
                        break
            
            if not current_part:
                # If no part found yet, assume Part 1
                current_part = "Part 1"
                current_part_number = 1
                current_part_title = "General Information"
                if current_part not in form_structure.parts:
                    form_structure.parts[current_part] = []
            
            # Extract fields from this page
            fields = self._extract_page_fields_enhanced(
                page, page_num + 1, page_text, current_part, 
                current_part_number, current_part_title, form_structure.form_number
            )
            
            # Add fields to structure
            for field in fields:
                form_structure.parts[current_part].append(field)
                form_structure.total_fields += 1
    
    def _extract_page_fields_enhanced(self, page, page_num: int, text: str, part: str, 
                                    part_number: int, part_title: str, form_number: str) -> List[ExtractedField]:
        """Enhanced field extraction with better patterns"""
        fields = []
        lines = text.split('\n')
        
        # Enhanced patterns for different field formats
        patterns = [
            # Standard item pattern: "1.", "1.a.", "5."
            (re.compile(r'^(\d+)(?:\.([a-z]))?\.?\s+(.+?)(?:\s*(?:Yes|No)\s*$)?', re.IGNORECASE), 'standard'),
            # Item with parentheses: "Item Number 1."
            (re.compile(r'^Item\s+Number\s+(\d+)(?:\.([a-z]))?\.\s*(.+)', re.IGNORECASE), 'item_number'),
            # Question format: "1. Are you..."
            (re.compile(r'^(\d+)\.\s+(Are\s+you|Have\s+you|Do\s+you|Is\s+|Was\s+|Will\s+)(.+)', re.IGNORECASE), 'question'),
            # Field in parentheses or brackets
            (re.compile(r'^\((\d+)(?:\.([a-z]))?\)\s*(.+)', re.IGNORECASE), 'parentheses'),
            # Number with dash: "1 - Field Label"
            (re.compile(r'^(\d+)\s*[-–]\s*(.+)', re.IGNORECASE), 'dash')
        ]
        
        # Process lines
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue
            
            field_found = False
            
            # Try each pattern
            for pattern, pattern_type in patterns:
                match = pattern.match(line)
                if match:
                    # Extract components based on pattern type
                    if pattern_type in ['standard', 'item_number', 'parentheses']:
                        item_main = match.group(1)
                        item_sub = match.group(2) if len(match.groups()) > 2 else ""
                        label_text = match.group(3) if len(match.groups()) > 2 else match.group(2)
                    elif pattern_type == 'question':
                        item_main = match.group(1)
                        item_sub = ""
                        label_text = match.group(2) + match.group(3)
                    elif pattern_type == 'dash':
                        item_main = match.group(1)
                        item_sub = ""
                        label_text = match.group(2)
                    else:
                        continue
                    
                    # Clean label
                    label_text = label_text.strip()
                    
                    # Build item number
                    item_number = item_main
                    if item_sub:
                        item_number += f".{item_sub}"
                    
                    # Determine field type
                    field_type = self._determine_field_type(label_text, lines, i)
                    
                    # Create field
                    field = ExtractedField(
                        name=f"field_{item_number.replace('.', '_')}",
                        label=label_text,
                        type=field_type,
                        page=page_num,
                        part=part,
                        part_number=part_number,
                        part_title=part_title,
                        item_number=item_number,
                        raw_field_name=line
                    )
                    
                    # Auto-assign checkboxes to questionnaire
                    if field_type in ["checkbox", "radio"]:
                        field.is_questionnaire = True
                    
                    fields.append(field)
                    field_found = True
                    break
            
            i += 1
        
        # Also extract from PDF form fields
        widget_fields = self._extract_from_widgets(page, page_num, part, part_number, part_title)
        
        # Merge and deduplicate
        all_fields = self._merge_fields(fields, widget_fields)
        
        return all_fields
    
    def _determine_field_type(self, label: str, lines: List[str], current_index: int) -> str:
        """Determine field type based on label and context"""
        label_lower = label.lower()
        
        # Check for date indicators
        date_keywords = ['date', 'birth', 'expir', 'issue', 'valid']
        if any(keyword in label_lower for keyword in date_keywords):
            return "date"
        
        # Check for number fields
        number_keywords = ['number', 'ssn', 'ein', 'a-number', 'alien', 'receipt', 'case']
        if any(keyword in label_lower for keyword in number_keywords):
            return "number"
        
        # Check for signature
        if 'signature' in label_lower:
            return "signature"
        
        # Check if it's a yes/no question
        question_starters = ['are you', 'have you', 'do you', 'is ', 'was ', 'will ', 'can you']
        if any(label_lower.startswith(starter) for starter in question_starters):
            return "checkbox"
        
        # Check next lines for checkbox indicators
        if current_index + 1 < len(lines):
            next_line = lines[current_index + 1].strip().lower()
            if re.search(r'^\s*(yes|no)\s*$', next_line) or ('yes' in next_line and 'no' in next_line):
                return "checkbox"
        
        # Default to text
        return "text"
    
    def _match_fields_to_pages(self, form_structure: FormStructure, doc, page_texts: List[str]):
        """Match AI-identified fields to actual pages in PDF"""
        # For each page, try to find fields
        for page_num, page_text in enumerate(page_texts):
            for part_name, fields in form_structure.parts.items():
                for field in fields:
                    # Search for field's item number and label in page
                    search_patterns = [
                        f"{field.item_number}\\s*\\.?\\s*{re.escape(field.label[:20])}",
                        f"{field.item_number}\\s*\\.?",
                        re.escape(field.label[:30])
                    ]
                    
                    for pattern in search_patterns:
                        if re.search(pattern, page_text, re.IGNORECASE):
                            field.page = page_num + 1
                            break
    
    def _extract_from_widgets(self, page, page_num: int, part: str, 
                            part_number: int, part_title: str) -> List[ExtractedField]:
        """Extract fields from PDF form widgets"""
        fields = []
        
        try:
            widgets = page.widgets()
            if not widgets:
                return fields
            
            for widget in widgets:
                if not widget:
                    continue
                
                field_name = widget.field_name if hasattr(widget, 'field_name') else ""
                if not field_name:
                    continue
                
                # Clean field name
                clean_name = re.sub(r'topmostSubform\[0\]\.', '', field_name)
                clean_name = re.sub(r'form1\[0\]\.', '', clean_name)
                clean_name = re.sub(r'\[0\]', '', clean_name)
                
                # Try to extract item number from field name
                item_match = re.search(r'(\d+)([a-z])?', clean_name)
                item_number = ""
                if item_match:
                    item_number = item_match.group(1)
                    if item_match.group(2):
                        item_number += f".{item_match.group(2)}"
                
                # Determine field type from widget
                widget_type = widget.field_type if hasattr(widget, 'field_type') else 4
                type_map = {
                    2: "checkbox",
                    3: "radio", 
                    4: "text",
                    5: "dropdown",
                    7: "signature"
                }
                field_type = type_map.get(widget_type, "text")
                
                # Generate label
                label = self._generate_label_from_name(clean_name)
                
                field = ExtractedField(
                    name=clean_name,
                    label=label,
                    type=field_type,
                    page=page_num,
                    part=part,
                    part_number=part_number,
                    part_title=part_title,
                    item_number=item_number,
                    raw_field_name=field_name
                )
                
                # Auto-assign checkboxes/radios to questionnaire
                if field_type in ["checkbox", "radio"]:
                    field.is_questionnaire = True
                
                fields.append(field)
                
        except Exception as e:
            self.log(f"Widget extraction error: {str(e)}", "warning")
        
        return fields
    
    def _generate_label_from_name(self, name: str) -> str:
        """Generate human-readable label from field name"""
        # Remove common patterns
        label = re.sub(r'(field|text|check|box|button)\d*', '', name, flags=re.IGNORECASE)
        
        # Convert camelCase to spaces
        label = re.sub(r'([a-z])([A-Z])', r'\1 \2', label)
        
        # Replace underscores with spaces
        label = label.replace('_', ' ').replace('-', ' ')
        
        # Common abbreviations
        replacements = {
            'fname': 'First Name',
            'lname': 'Last Name',
            'mname': 'Middle Name',
            'dob': 'Date of Birth',
            'ssn': 'Social Security Number',
            'addr': 'Address',
            'tel': 'Telephone',
            'apt': 'Apartment',
            'ste': 'Suite'
        }
        
        for abbr, full in replacements.items():
            if abbr in label.lower():
                return full
        
        # Capitalize words
        return ' '.join(word.capitalize() for word in label.split() if word)
    
    def _merge_fields(self, text_fields: List[ExtractedField], 
                     widget_fields: List[ExtractedField]) -> List[ExtractedField]:
        """Merge fields from different sources"""
        merged = []
        seen_items = set()
        
        # Add text-extracted fields first (better labels)
        for field in text_fields:
            if field.item_number:
                seen_items.add(field.item_number)
            merged.append(field)
        
        # Add widget fields not already found
        for field in widget_fields:
            if field.item_number and field.item_number not in seen_items:
                merged.append(field)
            elif not field.item_number:
                # Always add fields without item numbers
                merged.append(field)
        
        # Sort by item number
        merged.sort(key=lambda f: self._parse_item_number(f.item_number))
        
        return merged
    
    def _parse_item_number(self, item_num: str) -> Tuple[int, str]:
        """Parse item number for sorting"""
        if not item_num:
            return (999, '')
        
        match = re.match(r'(\d+)\.?([a-z])?', item_num)
        if match:
            num = int(match.group(1))
            letter = match.group(2) or ''
            return (num, letter)
        return (999, item_num)

# Validation Agent
class ValidationAgent(Agent):
    """Validates and corrects field extraction"""
    
    def __init__(self):
        super().__init__("Validation Agent", "Field Validation & Correction")
        
        # Expected patterns for forms
        self.expected_patterns = {
            "I-539": {
                "Part 1": {
                    "title": "Information About You",
                    "items": ["1.a", "1.b", "1.c", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"]
                },
                "Part 2": {
                    "title": "Application Type",
                    "items": ["1", "2", "3", "4", "5", "6"]
                },
                "Part 3": {
                    "title": "Processing Information",
                    "items": ["1", "2", "3", "4", "5", "6", "7"]
                }
            }
        }
    
    def execute(self, form_structure: FormStructure) -> FormStructure:
        """Validate and correct form structure"""
        self.status = "active"
        self.log("Starting validation process...")
        
        try:
            # Validate form identification
            if form_structure.form_number == "Unknown":
                form_structure.validation_issues.append("Form type not identified")
                self.log("Warning: Form type not identified", "warning")
            
            # Validate parts
            if form_structure.form_number in self.expected_patterns:
                expected = self.expected_patterns[form_structure.form_number]
                
                for part_name, part_info in expected.items():
                    if part_name not in form_structure.parts:
                        form_structure.validation_issues.append(f"Missing {part_name}")
                        self.log(f"Missing {part_name}", "warning")
                    else:
                        # Check for expected items
                        fields = form_structure.parts[part_name]
                        found_items = {f.item_number for f in fields if f.item_number}
                        missing_items = set(part_info["items"]) - found_items
                        
                        if missing_items:
                            self.log(f"{part_name}: Missing items {missing_items}", "warning")
            
            # Validate field quality
            for part_name, fields in form_structure.parts.items():
                # Check for duplicate item numbers
                item_counts = defaultdict(int)
                for field in fields:
                    if field.item_number:
                        item_counts[field.item_number] += 1
                
                duplicates = {item: count for item, count in item_counts.items() if count > 1}
                if duplicates:
                    self.log(f"{part_name}: Duplicate items found: {duplicates}", "warning")
                
                # Validate and mark fields
                for field in fields:
                    field.is_validated = True
                    field.validation_confidence = 0.9 if field.item_number else 0.5
                    form_structure.validated_fields += 1
            
            # Calculate validation score
            if form_structure.total_fields > 0:
                fields_with_items = sum(1 for fields in form_structure.parts.values() 
                                      for f in fields if f.item_number)
                form_structure.validation_score = fields_with_items / form_structure.total_fields
            
            form_structure.is_validated = True
            form_structure.add_agent_log(self.name, f"Validation score: {form_structure.validation_score:.0%}")
            
            self.log(f"Validation complete. Score: {form_structure.validation_score:.0%}", "success")
            self.status = "completed"
            
            return form_structure
            
        except Exception as e:
            self.log(f"Validation failed: {str(e)}", "error")
            self.status = "error"
            return form_structure

# AI Mapping Agent
class AIMappingAgent(Agent):
    """Intelligent field mapping using AI and patterns"""
    
    def __init__(self):
        super().__init__("AI Mapping Agent", "Intelligent Field Mapping")
        # Try to get client from session state first, then from secrets
        self.client = st.session_state.get('openai_client', None) or get_openai_client()
        
        # Enhanced mapping patterns
        self.mapping_patterns = {
            # Item number based mappings for I-539
            "1.a": "beneficiary.PersonalInfo.beneficiaryLastName",
            "1.b": "beneficiary.PersonalInfo.beneficiaryFirstName",
            "1.c": "beneficiary.PersonalInfo.beneficiaryMiddleName",
            "2": "beneficiary.PersonalInfo.alienNumber",
            "3": "beneficiary.PersonalInfo.uscisOnlineAccountNumber",
            "7": "beneficiary.PersonalInfo.beneficiaryCountryOfBirth",
            "8": "beneficiary.PersonalInfo.beneficiaryCitizenOfCountry", 
            "9": "beneficiary.PersonalInfo.beneficiaryDateOfBirth",
            "10": "beneficiary.PersonalInfo.beneficiarySsn",
            "12": "beneficiary.VisaDetails.currentNonimmigrantStatus",
            
            # Label based patterns
            "street": "beneficiary.MailingAddress.addressStreet",
            "city": "beneficiary.MailingAddress.addressCity",
            "state": "beneficiary.MailingAddress.addressState",
            "zip": "beneficiary.MailingAddress.addressZip",
            "country": "beneficiary.MailingAddress.addressCountry",
            "email": "beneficiary.ContactInfo.emailAddress",
            "phone": "beneficiary.ContactInfo.daytimeTelephoneNumber",
            "passport": "beneficiary.PassportDetails.passportNumber"
        }
    
    def execute(self, form_structure: FormStructure) -> FormStructure:
        """Map fields using patterns and AI"""
        self.status = "active"
        self.log("Starting intelligent field mapping...")
        
        try:
            total_mapped = 0
            
            for part_name, fields in form_structure.parts.items():
                self.log(f"Mapping {part_name}...")
                
                # Get text fields that need mapping
                text_fields = [f for f in fields if f.type in ["text", "number", "date"] 
                             and not f.db_path and not f.is_questionnaire and not f.manually_assigned]
                
                if text_fields:
                    # Phase 1: Pattern matching
                    for field in text_fields:
                        # Try item number first
                        if field.item_number in self.mapping_patterns:
                            field.db_path = self.mapping_patterns[field.item_number]
                            field.ai_confidence = 0.95
                            total_mapped += 1
                            self.log(f"Pattern matched: {field.item_number} → {field.db_path}")
                            continue
                        
                        # Try label matching
                        label_lower = field.label.lower()
                        for pattern, db_path in self.mapping_patterns.items():
                            if len(pattern) > 2 and pattern in label_lower:
                                field.db_path = db_path
                                field.ai_confidence = 0.85
                                total_mapped += 1
                                break
                    
                    # Phase 2: AI mapping for remaining
                    if self.client:
                        unmapped = [f for f in text_fields if not f.db_path]
                        if unmapped:
                            ai_mapped = self._ai_batch_mapping(unmapped, form_structure, part_name)
                            total_mapped += ai_mapped
            
            # Update statistics
            form_structure.mapped_fields = sum(1 for fields in form_structure.parts.values() 
                                             for f in fields if f.db_path)
            
            form_structure.add_agent_log(self.name, f"Mapped {total_mapped} fields")
            self.log(f"Mapping complete. Mapped {total_mapped} fields", "success")
            
            self.status = "completed"
            return form_structure
            
        except Exception as e:
            self.log(f"Mapping failed: {str(e)}", "error")
            self.status = "error"
            return form_structure
    
    def _ai_batch_mapping(self, fields: List[ExtractedField], form_structure: FormStructure, 
                         part_name: str) -> int:
        """Use AI for intelligent mapping"""
        if not self.client or not fields:
            return 0
        
        try:
            # Prepare field info
            field_info = []
            for f in fields[:10]:  # Process up to 10 at a time
                field_info.append({
                    "item_number": f.item_number,
                    "label": f.label,
                    "type": f.type
                })
            
            # Get all DB paths
            db_paths = []
            for obj, categories in UNIVERSAL_DB_STRUCTURE.items():
                for cat, field_list in categories.items():
                    for field_name in field_list:
                        path = f"{obj}.{cat}.{field_name}" if cat else f"{obj}.{field_name}"
                        db_paths.append(path)
            
            # Add custom fields
            custom_fields = st.session_state.get('custom_db_fields', {})
            db_paths.extend(custom_fields.keys())
            
            prompt = f"""
            Map these fields from {form_structure.form_number} {part_name} to database paths.
            
            Fields to map:
            {json.dumps(field_info, indent=2)}
            
            Available database paths (partial list):
            {json.dumps(db_paths[:50], indent=2)}
            
            Important mapping rules:
            - Item 1.a, 1.b, 1.c are ALWAYS Family Name, Given Name, Middle Name
            - Item 2 is A-Number (alienNumber)
            - Item 3 is USCIS Online Account Number
            - Item 9 is Date of Birth
            - Item 10 is SSN
            - Form I-539 fields map to "beneficiary" object
            - Address fields: use MailingAddress for mailing, PhysicalAddress for physical
            
            Return ONLY a JSON object mapping item numbers/labels to database paths.
            Example: {{"1.a": "beneficiary.PersonalInfo.beneficiaryLastName", "2": "beneficiary.PersonalInfo.alienNumber"}}
            """
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert at mapping USCIS form fields to database structures. Always follow the exact mapping rules provided."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=1000
            )
            
            # Parse response
            response_text = response.choices[0].message.content
            # Extract JSON from response
            json_match = re.search(r'\{[^}]+\}', response_text)
            if json_match:
                mappings = json.loads(json_match.group())
            else:
                mappings = json.loads(response_text)
            
            mapped_count = 0
            for field in fields:
                key = field.item_number if field.item_number else field.label
                if key in mappings:
                    field.db_path = mappings[key]
                    field.ai_confidence = 0.75
                    field.ai_suggestion = "AI Mapped"
                    mapped_count += 1
                    self.log(f"AI mapped: {key} → {field.db_path}")
            
            return mapped_count
            
        except Exception as e:
            self.log(f"AI mapping error: {str(e)}", "warning")
            return 0

# Manual Assignment UI
def render_manual_assignment(form_structure: FormStructure, part_name: str):
    """Render manual assignment interface"""
    st.markdown("### 🔧 Manual Field Assignment")
    
    fields = form_structure.parts.get(part_name, [])
    if not fields:
        st.warning("No fields in this part")
        return
    
    # Create tabs
    tab1, tab2 = st.tabs(["📝 Assign Individual Fields", "⚡ Bulk Operations"])
    
    with tab1:
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown("**Unmapped Text Fields:**")
            
            # Get unmapped text fields
            unmapped_text = [f for f in fields if f.type in ["text", "number", "date"] 
                           and not f.db_path and not f.is_questionnaire]
            
            if unmapped_text:
                for idx, field in enumerate(unmapped_text[:5]):  # Show first 5
                    with st.container():
                        label = f"{field.item_number}. {field.label}" if field.item_number else field.label
                        st.text(label)
                        
                        col_a, col_b = st.columns([3, 1])
                        with col_a:
                            # Database path selector
                            db_options = ["-- Select --", "→ Move to Questionnaire", "---"]
                            
                            # Add paths grouped by object
                            for obj in ["beneficiary", "petitioner", "case"]:
                                if obj in UNIVERSAL_DB_STRUCTURE:
                                    db_options.append(f"═══ {obj.upper()} ═══")
                                    for cat, fields_list in UNIVERSAL_DB_STRUCTURE[obj].items():
                                        for field_name in fields_list[:10]:  # Show first 10
                                            path = f"{obj}.{cat}.{field_name}" if cat else f"{obj}.{field_name}"
                                            db_options.append(f"  {path}")
                            
                            selected = st.selectbox(
                                "Map to",
                                db_options,
                                key=f"manual_map_{field.field_id}_{idx}_{part_name.replace(' ', '_')}",
                                label_visibility="collapsed"
                            )
                            
                            if selected and selected != "-- Select --" and not selected.startswith("═══"):
                                if selected == "→ Move to Questionnaire":
                                    field.is_questionnaire = True
                                    field.manually_assigned = True
                                    field.manual_assignment_type = "questionnaire"
                                    form_structure.questionnaire_fields += 1
                                    st.rerun()
                                elif selected != "---":
                                    field.db_path = selected.strip()
                                    field.manually_assigned = True
                                    field.manual_assignment_type = "database"
                                    form_structure.manually_assigned_fields += 1
                                    form_structure.mapped_fields += 1
                                    st.rerun()
                        
                        with col_b:
                            if st.button("→ Quest", key=f"quest_btn_{field.field_id}_{idx}_{part_name.replace(' ', '_')}"):
                                field.is_questionnaire = True
                                field.manually_assigned = True
                                field.manual_assignment_type = "questionnaire"
                                form_structure.questionnaire_fields += 1
                                st.rerun()
            else:
                st.info("All text fields are mapped or assigned")
        
        with col2:
            st.markdown("**Conditional Fields (Checkboxes/Radios):**")
            
            # Get conditional fields
            conditional = [f for f in fields if f.type in ["checkbox", "radio"]]
            
            if conditional:
                for idx, field in enumerate(conditional[:10]):  # Show first 10
                    col_a, col_b = st.columns([3, 1])
                    with col_a:
                        label = f"{field.item_number}. {field.label}" if field.item_number else field.label
                        if field.type == "checkbox":
                            st.markdown(f'<div class="checkbox-field">{label}</div>', unsafe_allow_html=True)
                        else:
                            st.markdown(f'<div class="radio-field">{label}</div>', unsafe_allow_html=True)
                    
                    with col_b:
                        is_quest = st.checkbox(
                            "Quest", 
                            value=field.is_questionnaire,
                            key=f"cond_quest_{field.field_id}_{idx}_{part_name.replace(' ', '_')}"
                        )
                        if is_quest != field.is_questionnaire:
                            field.is_questionnaire = is_quest
                            if is_quest:
                                field.manually_assigned = True
                                field.manual_assignment_type = "questionnaire"
                                form_structure.questionnaire_fields += 1
                            st.rerun()
            else:
                st.info("No conditional fields found")
    
    with tab2:
        st.markdown("**Bulk Assignment Operations:**")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📋 All Unmapped → Questionnaire", use_container_width=True):
                count = 0
                for field in fields:
                    if not field.db_path and not field.is_questionnaire and not field.manually_assigned:
                        field.is_questionnaire = True
                        field.manually_assigned = True
                        field.manual_assignment_type = "questionnaire"
                        count += 1
                form_structure.questionnaire_fields += count
                st.success(f"✅ Moved {count} fields to questionnaire")
                st.rerun()
        
        with col2:
            if st.button("☑️ All Checkboxes → Questionnaire", use_container_width=True):
                count = 0
                for field in fields:
                    if field.type == "checkbox" and not field.is_questionnaire:
                        field.is_questionnaire = True
                        field.manually_assigned = True
                        field.manual_assignment_type = "questionnaire"
                        count += 1
                form_structure.questionnaire_fields += count
                st.success(f"✅ Moved {count} checkboxes")
                st.rerun()
        
        with col3:
            if st.button("🔄 Reset Manual Assignments", use_container_width=True):
                count = 0
                for field in fields:
                    if field.manually_assigned:
                        field.manually_assigned = False
                        field.manual_assignment_type = ""
                        count += 1
                st.success(f"✅ Reset {count} assignments")
                st.rerun()

# Field Display
def render_field_card(field: ExtractedField, idx: int):
    """Render field card with all details"""
    # Determine status
    if field.db_path:
        status_class = "mapped"
        status_text = "✅ Mapped"
    elif field.is_questionnaire:
        status_class = "questionnaire"
        status_text = "📋 Questionnaire"
    else:
        status_class = "unmapped"
        status_text = "❌ Not Mapped"
    
    if field.manually_assigned:
        status_text += " (Manual)"
    
    st.markdown(f'<div class="field-card {status_class}">', unsafe_allow_html=True)
    
    # Main info
    col1, col2, col3 = st.columns([3, 4, 2])
    
    with col1:
        if field.item_number:
            st.markdown(f'<span class="item-number">{field.item_number}</span>{field.label}', 
                       unsafe_allow_html=True)
        else:
            st.markdown(f'**{field.label}**')
        
        # Type badge
        type_class = f"type-{field.type}"
        st.markdown(f'<span class="field-type-badge {type_class}">{field.type}</span>', 
                   unsafe_allow_html=True)
        
        # Validation badge
        if field.is_validated:
            st.markdown(f'<span class="validation-badge">✓ Validated</span>', 
                       unsafe_allow_html=True)
    
    with col2:
        if field.type in ["text", "number", "date"] and not field.is_questionnaire:
            # Database mapping
            current = field.db_path if field.db_path else "-- Select Database Field --"
            
            # Build options
            options = ["-- Select Database Field --", "📋 Move to Questionnaire"]
            
            # Add database paths
            for obj, categories in UNIVERSAL_DB_STRUCTURE.items():
                options.append(f"═══ {obj.upper()} ═══")
                for cat, fields_list in categories.items():
                    for field_name in fields_list:
                        path = f"{obj}.{cat}.{field_name}" if cat else f"{obj}.{field_name}"
                        options.append(f"  {path}")
            
            selected = st.selectbox(
                "Map to",
                options,
                index=options.index(current) if current in options else 0,
                key=f"field_map_{field.field_id}_{idx}",
                label_visibility="collapsed"
            )
            
            if selected != current and not selected.startswith("═══"):
                if selected == "📋 Move to Questionnaire":
                    field.is_questionnaire = True
                    field.db_path = None
                    st.rerun()
                elif selected != "-- Select Database Field --":
                    field.db_path = selected.strip()
                    field.is_questionnaire = False
                    st.rerun()
        else:
            # Questionnaire option
            include = st.checkbox(
                "Include in Questionnaire",
                value=field.is_questionnaire,
                key=f"quest_{field.field_id}_{idx}"
            )
            if include != field.is_questionnaire:
                field.is_questionnaire = include
                st.rerun()
    
    with col3:
        st.markdown(f"**{status_text}**")
        if field.ai_confidence > 0:
            st.caption(f"AI: {field.ai_confidence:.0%}")
    
    st.markdown('</div>', unsafe_allow_html=True)

# Export Functions
def generate_typescript(form_structure: FormStructure) -> str:
    """Generate TypeScript export"""
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
    
    # Process fields
    for part_name, fields in form_structure.parts.items():
        for field in fields:
            if field.db_path:
                # Determine section
                section = None
                if field.db_path.startswith('beneficiary.'):
                    section = 'beneficiaryData'
                elif field.db_path.startswith('petitioner.'):
                    section = 'beneficiaryData'  # Map petitioner to beneficiary for some forms
                elif field.db_path.startswith('case.'):
                    section = 'caseData'
                
                if section:
                    key = field.name
                    suffix = {
                        'text': ':TextBox',
                        'checkbox': ':CheckBox',
                        'radio': ':RadioBox',
                        'date': ':Date',
                        'number': ':TextBox',
                        'signature': ':SignatureBox'
                    }.get(field.type, ':TextBox')
                    
                    sections[section][key] = f"{field.db_path}{suffix}"
            
            elif field.is_questionnaire:
                sections['questionnaireData'][field.questionnaire_key] = f"{field.name}{field.questionnaire_type}"
    
    # Generate TypeScript
    ts = f'export const {form_name} = {{\n'
    
    for key, value in sections.items():
        if key in ['formname', 'pdfName']:
            ts += f'    "{key}": "{value}",\n'
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

def generate_json(form_structure: FormStructure) -> str:
    """Generate JSON export"""
    controls = []
    
    for part_name, fields in form_structure.parts.items():
        # Get questionnaire fields
        quest_fields = [f for f in fields if f.is_questionnaire]
        
        if quest_fields:
            # Add part title
            part_num = quest_fields[0].part_number
            controls.append({
                "name": f"{part_num}_title",
                "label": part_name,
                "type": "title",
                "validators": {},
                "style": {"col": "12"}
            })
            
            # Add fields
            for field in quest_fields:
                label = field.label
                if field.item_number:
                    label = f"{field.item_number}. {label}"
                
                control = {
                    "name": field.name,
                    "label": label,
                    "type": field.control_type,
                    "validators": {"required": False},
                    "style": {"col": "7" if field.type == "text" else "12"}
                }
                
                controls.append(control)
    
    return json.dumps({"controls": controls}, indent=2)

# Main Application
def main():
    st.markdown('<div class="main-header"><h1>🤖 Smart USCIS Form Reader</h1><p>Multi-Agent System with AI-Enhanced Extraction</p></div>', 
               unsafe_allow_html=True)
    
    # Initialize session state
    if 'form_structure' not in st.session_state:
        st.session_state.form_structure = None
    if 'agents' not in st.session_state:
        st.session_state.agents = {}
    if 'selected_part' not in st.session_state:
        st.session_state.selected_part = None
    
    # Check for OpenAI API key
    openai_client = st.session_state.get('openai_client', None) or get_openai_client()
    openai_available = openai_client is not None
    
    # Sidebar
    with st.sidebar:
        st.markdown("## ⚙️ Configuration")
        
        # Debug info for API key
        if st.checkbox("Show Debug Info", value=False):
            st.markdown("### 🔍 Debug Information")
            try:
                # Check if secrets exist
                if hasattr(st, 'secrets'):
                    st.info("✅ Secrets object exists")
                    
                    # Show available keys (without values)
                    secret_keys = list(st.secrets.keys()) if hasattr(st.secrets, 'keys') else []
                    if secret_keys:
                        st.write("Available keys:", secret_keys)
                    else:
                        st.warning("No keys found in secrets")
                else:
                    st.error("❌ Secrets object not found")
                    
                # Check environment
                import os
                env_key = os.environ.get('OPENAI_API_KEY', None)
                if env_key:
                    st.info("✅ Found in environment variables")
            except Exception as e:
                st.error(f"Debug error: {str(e)}")
        
        if not OPENAI_AVAILABLE:
            st.error("❌ OpenAI library not installed")
            st.markdown("""
            **Installation Required:**
            ```bash
            pip install openai
            ```
            
            Or add to requirements.txt:
            ```
            openai>=1.0.0
            ```
            """)
            openai_available = False
        elif openai_available:
            st.success("✅ OpenAI API Key configured")
        else:
            st.warning("⚠️ OpenAI API Key not found")
            with st.expander("Setup Instructions"):
                st.markdown("""
                **Option 1: Streamlit Secrets**
                1. Create `.streamlit/secrets.toml` in your project
                2. Add: `OPENAI_API_KEY = "your-key"`
                
                **Option 2: Manual Entry**
                Enter your API key below (temporary)
                """)
                
                manual_key = st.text_input("OpenAI API Key", type="password", key="manual_api_key")
                if manual_key and OPENAI_AVAILABLE:
                    # Try to create client with manual key
                    try:
                        test_client = OpenAI(api_key=manual_key)
                        # Store in session state
                        st.session_state['openai_client'] = test_client
                        st.success("✅ API Key accepted!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Invalid API key: {str(e)}")
        
        st.markdown("### 🤖 Agent Settings")
        use_ai = st.checkbox("Use AI Enhancement", value=openai_available, disabled=not openai_available)
        auto_validate = st.checkbox("Auto-Validate", value=True)
        auto_map = st.checkbox("Auto-Map with AI", value=openai_available, disabled=not openai_available)
        
        # Form info
        if st.session_state.form_structure:
            form = st.session_state.form_structure
            st.markdown("### 📄 Current Form")
            st.info(f"{form.form_number}: {form.form_title}")
            
            # Statistics
            st.markdown("### 📊 Statistics")
            st.metric("Total Fields", form.total_fields)
            st.metric("Validated", f"{form.validated_fields}/{form.total_fields}")
            st.metric("Mapped", form.mapped_fields)
            st.metric("Questionnaire", form.questionnaire_fields)
            
            if form.is_validated:
                st.metric("Validation Score", f"{form.validation_score:.0%}")
    
    # Main tabs
    tabs = st.tabs(["📤 Upload & Process", "🎯 Field Mapping", "📥 Export"])
    
    with tabs[0]:
        st.markdown("## Upload USCIS Form")
        
        uploaded_file = st.file_uploader(
            "Choose a USCIS PDF form",
            type=['pdf'],
            help="Upload I-539, I-824, or any other USCIS form"
        )
        
        if uploaded_file:
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.success(f"✅ {uploaded_file.name} ready")
            
            with col2:
                if st.button("🚀 Process", type="primary", use_container_width=True):
                    # Create status container
                    st.session_state.agent_status_container = st.container()
                    
                    # Initialize agents
                    agents = {
                        'research': ResearchAgent(),
                        'validation': ValidationAgent(),
                        'mapping': AIMappingAgent() if openai_available else None
                    }
                    st.session_state.agents = agents
                    
                    # Process
                    with st.spinner("Processing..."):
                        # Research
                        form_structure = agents['research'].execute(uploaded_file, use_ai)
                        
                        if form_structure:
                            # Validate
                            if auto_validate:
                                form_structure = agents['validation'].execute(form_structure)
                            
                            # Map
                            if auto_map and openai_available:
                                form_structure = agents['mapping'].execute(form_structure)
                            
                            # Update counts
                            form_structure.questionnaire_fields = sum(
                                1 for fields in form_structure.parts.values() 
                                for f in fields if f.is_questionnaire
                            )
                            
                            st.session_state.form_structure = form_structure
                            st.session_state.selected_part = list(form_structure.parts.keys())[0] if form_structure.parts else None
                            
                            st.success(f"✅ Processed {form_structure.form_number}")
                            
                            # Show summary
                            with st.expander("📊 Extraction Summary", expanded=True):
                                for part, fields in form_structure.parts.items():
                                    st.markdown(f"**{part}**: {len(fields)} fields")
                                    
                                    # Show sample fields
                                    sample_fields = [f for f in fields if f.item_number][:5]
                                    if sample_fields:
                                        st.caption("Sample fields:")
                                        for f in sample_fields:
                                            st.caption(f"  • {f.item_number}. {f.label}")
    
    with tabs[1]:
        form_structure = st.session_state.get('form_structure')
        if form_structure and form_structure.parts:
            st.markdown("## 🎯 Field Mapping")
            
            # Part selector
            selected_part = st.selectbox(
                "Select Part",
                options=list(form_structure.parts.keys()),
                index=0
            )
            
            # Manual assignment section
            render_manual_assignment(form_structure, selected_part)
            
            # Display fields
            if selected_part:
                fields = form_structure.parts[selected_part]
                
                st.markdown(f'''
                <div class="part-header">
                    <h3>{selected_part}</h3>
                    <p>{len(fields)} fields</p>
                </div>
                ''', unsafe_allow_html=True)
                
                # Show extraction preview
                st.markdown('<div class="extraction-preview">', unsafe_allow_html=True)
                st.markdown("**✅ Successfully Extracted Fields:**")
                
                # Group by type
                text_fields = [f for f in fields if f.type in ["text", "number", "date"]]
                checkbox_fields = [f for f in fields if f.type == "checkbox"]
                other_fields = [f for f in fields if f.type not in ["text", "number", "date", "checkbox"]]
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Text Fields", len(text_fields))
                with col2:
                    st.metric("Checkboxes", len(checkbox_fields))
                with col3:
                    st.metric("Other", len(other_fields))
                
                st.markdown('</div>', unsafe_allow_html=True)
                
                # Display fields
                for idx, field in enumerate(fields):
                    render_field_card(field, idx)
        else:
            st.info("👆 Please upload and process a form first")
    
    with tabs[2]:
        form_structure = st.session_state.get('form_structure')
        if form_structure and form_structure.parts:
            st.markdown("## 📥 Export")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("🔨 Generate TypeScript", use_container_width=True, type="primary"):
                    ts_code = generate_typescript(form_structure)
                    
                    st.download_button(
                        "⬇️ Download TypeScript",
                        ts_code,
                        f"{form_structure.form_number}.ts",
                        mime="text/typescript",
                        use_container_width=True
                    )
                    
                    with st.expander("Preview", expanded=True):
                        st.code(ts_code, language="typescript")
            
            with col2:
                if st.button("🔨 Generate JSON", use_container_width=True, type="primary"):
                    json_code = generate_json(form_structure)
                    
                    st.download_button(
                        "⬇️ Download JSON",
                        json_code,
                        f"{form_structure.form_number}-questionnaire.json",
                        mime="application/json",
                        use_container_width=True
                    )
                    
                    with st.expander("Preview", expanded=True):
                        st.code(json_code, language="json")
        else:
            st.info("👆 Please process a form first")

if __name__ == "__main__":
    main()
