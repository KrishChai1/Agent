#!/usr/bin/env python3
"""
Smart USCIS Form Reader - Fixed Version 24
Works with ALL USCIS forms generically
"""

# Standard library imports first
import os
import json
import re
import time
import hashlib
import traceback
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field, asdict
from collections import defaultdict, OrderedDict
from abc import ABC, abstractmethod

# Third-party imports with error handling
import streamlit as st

# Initialize globals BEFORE any usage
OPENAI_AVAILABLE = False
OpenAI = None

# Try to import PyMuPDF
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    fitz = None

# Try to import OpenAI
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None

# Configure page - AFTER all imports and globals
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

# Show warnings for missing dependencies
if not PYMUPDF_AVAILABLE:
    st.error("❌ PyMuPDF not installed. Please run: `pip install PyMuPDF`")
    st.stop()

if not OPENAI_AVAILABLE:
    st.warning("⚠️ OpenAI library not installed. The app will work with limited features. To enable AI features, install with: `pip install openai`")

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

# Initialize OpenAI client function
def get_openai_client():
    """Get OpenAI client from secrets or environment"""
    global OPENAI_AVAILABLE, OpenAI
    
    if not OPENAI_AVAILABLE or not OpenAI:
        return None
        
    try:
        # Try multiple ways to get the API key
        api_key = None
        
        # Method 1: Check session state first (for manual entry)
        if 'openai_api_key' in st.session_state:
            api_key = st.session_state['openai_api_key']
        
        # Method 2: Direct access to secrets
        if not api_key and hasattr(st, 'secrets'):
            try:
                api_key = st.secrets['OPENAI_API_KEY']
            except KeyError:
                pass
        
        # Method 3: Using get method
        if not api_key:
            try:
                api_key = st.secrets.get('OPENAI_API_KEY', None)
            except Exception:
                pass
        
        # Method 4: Try lowercase
        if not api_key:
            try:
                api_key = st.secrets.get('openai_api_key', None)
            except Exception:
                pass
        
        # Method 5: Environment variable
        if not api_key:
            api_key = os.environ.get('OPENAI_API_KEY', None)
        
        if api_key:
            # Clean initialization without any extra parameters
            try:
                client = OpenAI(api_key=api_key)
                return client
            except TypeError as e:
                # Handle proxy issue on Streamlit Cloud
                if 'proxies' in str(e):
                    # Try alternative initialization
                    try:
                        import openai
                        openai.api_key = api_key
                        # Return a wrapper that mimics the client interface
                        class OpenAIWrapper:
                            def __init__(self):
                                self.chat = self
                                self.completions = self
                            
                            def create(self, **kwargs):
                                return openai.ChatCompletion.create(**kwargs)
                        
                        return OpenAIWrapper()
                    except:
                        return None
                else:
                    return None
        return None
    except Exception as e:
        # Don't show error here, handle it in the UI
        return None

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
        self.client = None
        if 'openai_client' in st.session_state:
            self.client = st.session_state['openai_client']
        else:
            self.client = get_openai_client()
    
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
            
            # Step 3: Extract with best strategy
            if use_ai and self.client:
                # AI-enhanced extraction
                ai_parts = self._ai_extract_parts(full_text[:20000], form_info['number'])
                if ai_parts:
                    self.log(f"AI found {len(ai_parts)} parts", "success")
                    self._extract_using_ai_parts(form_structure, doc, page_texts, ai_parts)
            
            # Always also do pattern-based extraction to catch anything missed
            self._extract_using_patterns(form_structure, doc, page_texts)
            
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
        """Use AI to extract form parts and fields"""
        if not self.client:
            return None
        
        try:
            prompt = f"""
            Analyze this USCIS {form_number} form and extract ALL parts/sections with their fields.
            Be extremely thorough and find EVERY part.
            
            Text sample:
            {text}
            
            Instructions:
            1. Find ALL parts/sections in this form. Common patterns:
               - "Part 1", "Part 2", etc.
               - "Section A", "Section B", etc.
               - "PART I", "PART II" (Roman numerals)
               - Parts may continue across pages
            
            2. For each part, identify:
               - The exact part number/identifier
               - The complete title
               - ALL numbered fields/items within that part
            
            3. Field patterns to look for:
               - Item numbers: 1, 2, 3 or 1., 2., 3.
               - Sub-items: 1.a., 1.b., 2.a., 2.b.
               - Questions: "Are you...", "Have you...", "Do you..."
               - Line numbers: "Line 1", "Line 2"
               - Fields with labels like "Name", "Address", "Date"
            
            Return a comprehensive JSON with ALL parts found:
            {{
                "Part 1": {{
                    "title": "Full title here",
                    "fields": [
                        {{"item": "1", "label": "Field label", "type": "text"}},
                        {{"item": "1.a", "label": "Sub-field label", "type": "text"}}
                    ]
                }},
                "Part 2": {{
                    "title": "Another section title",
                    "fields": [...]
                }}
            }}
            
            Field types: text, number, date, checkbox, radio, signature, email, phone
            
            IMPORTANT: 
            - Be exhaustive - find EVERY part and EVERY field
            - Return ONLY valid JSON
            - Include parts even if you only see the title without fields
            """
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo-16k" if len(text) > 10000 else "gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert at analyzing USCIS forms. Be extremely thorough and find ALL parts and fields."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=4000
            )
            
            # Parse response
            response_text = response.choices[0].message.content
            
            # Try to extract JSON
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                result = json.loads(json_match.group())
            else:
                result = json.loads(response_text)
            
            # Log what we found
            self.log(f"AI found {len(result)} parts in {form_number}", "info")
            for part_name, part_info in result.items():
                field_count = len(part_info.get('fields', []))
                self.log(f"  {part_name}: {field_count} fields", "info")
            
            return result
            
        except Exception as e:
            self.log(f"AI extraction error: {str(e)}", "warning")
            return None
    
    def _extract_using_ai_parts(self, form_structure: FormStructure, doc, page_texts: List[str], ai_parts: Dict):
        """Extract fields using AI-identified parts"""
        
        # Process each part from AI
        for part_name, part_info in ai_parts.items():
            # Extract part number
            part_number = 1
            num_match = re.search(r'\d+', part_name)
            if num_match:
                part_number = int(num_match.group())
            
            part_title = part_info.get('title', '')
            
            # Create part if not exists
            if part_name not in form_structure.parts:
                form_structure.parts[part_name] = []
                self.log(f"Processing {part_name}: {part_title}")
            
            # Add fields from AI analysis
            for field_info in part_info.get('fields', []):
                # Check if field already exists
                existing = any(
                    f.item_number == field_info['item'] 
                    for f in form_structure.parts[part_name]
                )
                
                if not existing:
                    field = ExtractedField(
                        name=f"field_{field_info['item'].replace('.', '_')}",
                        label=field_info['label'],
                        type=field_info.get('type', 'text'),
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
        
        # Now try to find these fields in the actual PDF pages
        self._match_fields_to_pages(form_structure, doc, page_texts)
    
    def _extract_using_patterns(self, form_structure: FormStructure, doc, page_texts: List[str]):
        """Pattern-based extraction for any USCIS form"""
        # Combine all pages into one text for better part detection
        full_text = "\n".join(page_texts)
        
        # Find all parts dynamically
        all_parts = self._find_all_parts_generic(full_text, form_structure.form_number)
        self.log(f"Pattern extraction found {len(all_parts)} parts in {form_structure.form_number}", "info")
        
        # Initialize all found parts
        for part_info in all_parts:
            part_name = f"Part {part_info['number']}"
            if part_name not in form_structure.parts:
                form_structure.parts[part_name] = []
                self.log(f"Initialized {part_name}: {part_info['title'][:50]}...", "info")
        
        # Process ALL pages
        current_part = 1
        
        for page_num, page in enumerate(doc):
            page_text = page_texts[page_num]
            
            # Check for part transitions
            for part_info in all_parts:
                if self._is_part_on_page(part_info, page_text):
                    current_part = part_info['number']
                    self.log(f"Page {page_num + 1}: Found Part {current_part}", "info")
            
            # Extract fields for current part
            part_name = f"Part {current_part}"
            part_info = next((p for p in all_parts if p['number'] == current_part), 
                           {'number': current_part, 'title': part_name})
            
            # Extract fields with comprehensive patterns
            fields = self._extract_fields_comprehensive(
                page, page_num + 1, page_text, part_name, 
                part_info['number'], part_info['title']
            )
            
            # Add unique fields to structure
            for field in fields:
                # Check if field already exists
                existing = any(
                    f.item_number == field.item_number and f.label == field.label
                    for f in form_structure.parts[part_name]
                )
                
                if not existing:
                    form_structure.parts[part_name].append(field)
                    form_structure.total_fields += 1
            
            if fields:
                self.log(f"Page {page_num + 1}: Extracted {len(fields)} fields for {part_name}", "info")
        
        # Log final summary
        self.log("=== Extraction Summary ===", "info")
        for part_name, fields in form_structure.parts.items():
            item_numbers = sorted(set(f.item_number for f in fields if f.item_number))
            self.log(f"{part_name}: {len(fields)} fields, Items: {item_numbers[:10]}{'...' if len(item_numbers) > 10 else ''}", "info")
    
    def _find_all_parts_generic(self, full_text: str, form_number: str) -> List[Dict]:
        """Find all parts in any USCIS form"""
        parts = []
        found_parts = set()
        
        # Multiple pattern strategies
        part_patterns = [
            # Standard patterns
            r'Part\s+(\d+)\.?\s*[-–:]?\s*([^\n]+)',
            r'PART\s+(\d+)\.?\s*[-–:]?\s*([^\n]+)',
            r'Section\s+([A-Z]|[0-9]+)\.?\s*[-–:]?\s*([^\n]+)',
            r'SECTION\s+([A-Z]|[0-9]+)\.?\s*[-–:]?\s*([^\n]+)',
            # Part with title on next line
            r'Part\s+(\d+)\s*\n\s*([^\n]+)',
            # Roman numerals
            r'Part\s+([IVX]+)\.?\s*[-–:]?\s*([^\n]+)',
            # Just section titles
            r'(Information About|Application Type|Processing Information|Additional Information|Contact Information|Signature)',
        ]
        
        # Search with all patterns
        for pattern in part_patterns:
            matches = re.finditer(pattern, full_text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                if len(match.groups()) == 2:
                    part_id = match.group(1)
                    part_title = match.group(2).strip()
                else:
                    # Single group match (like section titles)
                    part_title = match.group(1)
                    part_id = str(len(parts) + 1)
                
                # Clean title
                part_title = re.sub(r'\s+', ' ', part_title)
                part_title = re.sub(r'[^\w\s,()-]', '', part_title).strip()
                part_title = part_title[:150]  # Limit length
                
                # Convert to number if possible
                try:
                    part_num = int(part_id)
                except:
                    if part_id.isalpha():
                        part_num = ord(part_id.upper()) - ord('A') + 1
                    elif part_id in ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X']:
                        roman_values = {'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5,
                                      'VI': 6, 'VII': 7, 'VIII': 8, 'IX': 9, 'X': 10}
                        part_num = roman_values.get(part_id, len(parts) + 1)
                    else:
                        part_num = len(parts) + 1
                
                if part_num not in found_parts and part_title:
                    found_parts.add(part_num)
                    parts.append({
                        'number': part_num,
                        'title': part_title
                    })
        
        # If no parts found, create at least one
        if not parts:
            parts.append({'number': 1, 'title': 'Form Fields'})
        
        # Sort by part number
        parts.sort(key=lambda x: x['number'])
        
        return parts
    
    def _is_part_on_page(self, part_info: Dict, page_text: str) -> bool:
        """Check if a specific part starts on this page"""
        part_num = part_info['number']
        patterns = [
            f"Part\\s+{part_num}\\b",
            f"PART\\s+{part_num}\\b",
            f"Section\\s+{part_num}\\b",
            f"SECTION\\s+{part_num}\\b"
        ]
        
        for pattern in patterns:
            if re.search(pattern, page_text, re.IGNORECASE):
                return True
        return False
    
    def _extract_fields_comprehensive(self, page, page_num: int, text: str, part: str, 
                                    part_number: int, part_title: str) -> List[ExtractedField]:
        """Comprehensive field extraction with all patterns"""
        fields = []
        lines = text.split('\n')
        
        # All field patterns
        patterns = [
            # Standard item pattern: "1.", "1.a.", "5."
            (re.compile(r'^(\d+)(?:\.([a-z]))?\.\s+(.+?)(?:\s*\(.*\))?$', re.IGNORECASE), 'standard'),
            # Item without period at end
            (re.compile(r'^(\d+)(?:\.([a-z]))?\s+([A-Z][^\.]+)$', re.IGNORECASE), 'no_period'),
            # Item with parentheses: "Item Number 1."
            (re.compile(r'^Item\s+Number\s+(\d+)(?:\.([a-z]))?\.\s*(.+)', re.IGNORECASE), 'item_number'),
            # Question format: "1. Are you..."
            (re.compile(r'^(\d+)\.\s+(Are\s+you|Have\s+you|Do\s+you|Is\s+|Was\s+|Will\s+|Did\s+|Were\s+|Can\s+)(.+)', re.IGNORECASE), 'question'),
            # Field in parentheses or brackets
            (re.compile(r'^\((\d+)(?:\.([a-z]))?\)\s*(.+)', re.IGNORECASE), 'parentheses'),
            # Number with dash: "1 - Field Label"
            (re.compile(r'^(\d+)\s*[-–]\s*(.+)', re.IGNORECASE), 'dash'),
            # Letter fields: "A.", "B."
            (re.compile(r'^([A-Z])\.\s+(.+)', re.IGNORECASE), 'letter'),
            # Line Number format
            (re.compile(r'^Line\s+(\d+)(?:\.([a-z]))?\.\s*(.+)', re.IGNORECASE), 'line_number'),
            # Number in box format []
            (re.compile(r'^\[(\d+)\]\s*(.+)', re.IGNORECASE), 'box_number'),
            # Just number with label on next line
            (re.compile(r'^(\d+)\.?\s*$', re.IGNORECASE), 'number_only'),
            # Question prefix
            (re.compile(r'^Question\s+(\d+)[:\.]?\s*(.+)', re.IGNORECASE), 'question_prefix'),
            # Field labels without numbers
            (re.compile(r'^(Full Name|Date of Birth|Place of Birth|Country of Birth|Social Security)', re.IGNORECASE), 'keyword_field'),
            (re.compile(r'^(Street Address|City|State|ZIP Code|Country|Province)', re.IGNORECASE), 'address_field'),
        ]
        
        # Process lines
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue
            
            # Try each pattern
            for pattern, pattern_type in patterns:
                match = pattern.match(line)
                if match:
                    field = self._create_field_from_match(
                        match, pattern_type, line, lines, i,
                        page_num, part, part_number, part_title
                    )
                    if field:
                        fields.append(field)
                        if pattern_type == 'number_only':
                            i += 1  # Skip next line as we used it
                    break
            
            i += 1
        
        # Also extract from PDF form fields
        widget_fields = self._extract_from_widgets(page, page_num, part, part_number, part_title)
        
        # Merge and deduplicate
        all_fields = self._merge_fields(fields, widget_fields)
        
        return all_fields
    
    def _create_field_from_match(self, match, pattern_type: str, line: str, lines: List[str], 
                               line_index: int, page_num: int, part: str, part_number: int, 
                               part_title: str) -> Optional[ExtractedField]:
        """Create field from regex match"""
        # Extract components based on pattern type
        if pattern_type == 'number_only':
            # Look at next line for label
            if line_index + 1 < len(lines):
                next_line = lines[line_index + 1].strip()
                if next_line and not any(c.isdigit() for c in next_line[:3]):
                    item_main = match.group(1)
                    item_sub = ""
                    label_text = next_line
                else:
                    return None
            else:
                return None
        elif pattern_type in ['standard', 'no_period', 'item_number', 'parentheses', 'line_number']:
            item_main = match.group(1)
            item_sub = match.group(2) if len(match.groups()) > 2 and match.group(2) else ""
            label_text = match.group(3) if len(match.groups()) > 2 else match.group(2)
        elif pattern_type == 'question':
            item_main = match.group(1)
            item_sub = ""
            label_text = match.group(2) + match.group(3)
        elif pattern_type in ['dash', 'letter', 'box_number', 'question_prefix']:
            item_main = match.group(1)
            item_sub = ""
            label_text = match.group(2)
        elif pattern_type in ['keyword_field', 'address_field']:
            # Generate item number based on position
            item_main = f"F{line_index}"
            item_sub = ""
            label_text = match.group(1)
        else:
            return None
        
        # Clean label
        label_text = label_text.strip()
        label_text = re.sub(r'[\.;:]+$', '', label_text)
        
        # Build item number
        item_number = item_main
        if item_sub:
            item_number += f".{item_sub}"
        
        # Skip if label is too short or looks like noise
        if len(label_text) < 3 or label_text.lower() in ['yes', 'no', 'n/a', 'na', 'page']:
            return None
        
        # Determine field type
        field_type = self._determine_field_type(label_text, lines, line_index)
        
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
        
        return field
    
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
        question_starters = ['are you', 'have you', 'do you', 'is ', 'was ', 'will ', 'can you', 'did you', 'were you']
        if any(label_lower.startswith(starter) for starter in question_starters):
            return "checkbox"
        
        # Check next lines for checkbox indicators
        if current_index + 1 < len(lines):
            next_line = lines[current_index + 1].strip().lower()
            if re.search(r'^\s*(yes|no)\s*$', next_line) or ('yes' in next_line and 'no' in next_line):
                return "checkbox"
        
        # Email
        if 'email' in label_lower or 'e-mail' in label_lower:
            return "email"
        
        # Phone
        if any(word in label_lower for word in ['phone', 'telephone', 'mobile', 'cell']):
            return "phone"
        
        # Default to text
        return "text"
    
    def _match_fields_to_pages(self, form_structure: FormStructure, doc, page_texts: List[str]):
        """Match AI-identified fields to actual pages in PDF"""
        # For each page, try to find fields
        for page_num, page_text in enumerate(page_texts):
            for part_name, fields in form_structure.parts.items():
                for field in fields:
                    if field.page == 1:  # Only update if not already set
                        # Search for field's item number and label in page
                        search_patterns = [
                            f"{re.escape(field.item_number)}\\s*\\.?\\s*{re.escape(field.label[:20])}",
                            f"{re.escape(field.item_number)}\\s*\\.?",
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
                    name=clean_name[:50],  # Limit name length
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
        def sort_key(f):
            if not f.item_number:
                return (999, '', '')
            
            parts = f.item_number.split('.')
            main_num = 999
            sub_letter = ''
            
            try:
                main_num = int(parts[0])
            except:
                # Handle non-numeric item numbers
                if parts[0].startswith('F'):
                    main_num = 900 + int(parts[0][1:])
                else:
                    main_num = 999
            
            if len(parts) > 1:
                sub_letter = parts[1]
            
            return (main_num, sub_letter, f.item_number)
        
        merged.sort(key=sort_key)
        
        return merged

# Validation Agent
class ValidationAgent(Agent):
    """Generic validation agent for any USCIS form"""
    
    def __init__(self):
        super().__init__("Validation Agent", "Field Validation & Correction")
        
        # Common validation patterns for USCIS forms
        self.common_field_patterns = {
            # Personal information fields
            "name_fields": ["family name", "last name", "given name", "first name", "middle name"],
            "id_fields": ["a-number", "alien registration", "uscis online account", "receipt number", "case number"],
            "date_fields": ["date of birth", "expiration date", "date of entry", "date signed"],
            "contact_fields": ["telephone", "mobile", "email", "fax"],
            "address_fields": ["street", "city", "state", "zip", "country", "province", "postal code"],
            
            # Common questions
            "yes_no_questions": ["are you", "have you", "do you", "is your", "was", "were you", "will you", "has"],
            
            # Signature sections
            "signature_fields": ["signature", "sign here", "applicant signature", "preparer signature"],
        }
    
    def execute(self, form_structure: FormStructure) -> FormStructure:
        """Validate form structure for any USCIS form"""
        self.status = "active"
        self.log(f"Starting validation for {form_structure.form_number} form...", "info")
        
        try:
            # Basic form validation
            if form_structure.form_number == "Unknown":
                form_structure.validation_issues.append("Form type not identified")
                self.log("⚠️ Warning: Form type not identified", "warning")
            
            # Validate parts exist
            if not form_structure.parts:
                form_structure.validation_issues.append("No parts found in form")
                self.log("❌ No parts found in form", "error")
                return form_structure
            
            # Generic validation for all forms
            total_issues = 0
            total_fields_validated = 0
            fields_with_item_numbers = 0
            
            # Validate each part
            for part_name, fields in form_structure.parts.items():
                part_issues = []
                
                # Check if part has fields
                if not fields:
                    part_issues.append(f"{part_name} has no fields")
                    self.log(f"⚠️ {part_name}: No fields found", "warning")
                    continue
                
                # Count field types
                field_type_counts = defaultdict(int)
                item_number_counts = defaultdict(int)
                
                for field in fields:
                    field_type_counts[field.type] += 1
                    
                    # Validate field
                    field_issues = self._validate_field(field)
                    if field_issues:
                        part_issues.extend(field_issues)
                    
                    # Count item numbers
                    if field.item_number:
                        item_number_counts[field.item_number] += 1
                        fields_with_item_numbers += 1
                    
                    # Mark as validated
                    field.is_validated = True
                    field.validation_confidence = self._calculate_field_confidence(field)
                    total_fields_validated += 1
                
                # Check for duplicates
                duplicates = {item: count for item, count in item_number_counts.items() if count > 1}
                if duplicates:
                    self.log(f"⚠️ {part_name}: Duplicate item numbers: {duplicates}", "warning")
                    part_issues.append(f"Duplicate item numbers: {duplicates}")
                
                # Log part summary
                self.log(f"✓ {part_name}: {len(fields)} fields ({field_type_counts})", "info")
                
                # Add issues to form
                if part_issues:
                    form_structure.validation_issues.extend(part_issues)
                    total_issues += len(part_issues)
            
            # Calculate overall validation score
            form_structure.validated_fields = total_fields_validated
            
            if form_structure.total_fields > 0:
                # Score based on multiple factors
                item_number_score = fields_with_item_numbers / form_structure.total_fields
                completeness_score = 1.0 - (total_issues / max(form_structure.total_fields, 1))
                form_structure.validation_score = (item_number_score + completeness_score) / 2
            else:
                form_structure.validation_score = 0.0
            
            # Perform form-specific validation if available
            self._perform_form_specific_validation(form_structure)
            
            # Summary
            self.log("=== Validation Summary ===", "info")
            self.log(f"Form: {form_structure.form_number}", "info")
            self.log(f"Total parts: {len(form_structure.parts)}", "info")
            self.log(f"Total fields: {form_structure.total_fields}", "info")
            self.log(f"Fields validated: {total_fields_validated}", "info")
            self.log(f"Fields with item numbers: {fields_with_item_numbers}", "info")
            self.log(f"Validation issues: {total_issues}", "info")
            self.log(f"Validation score: {form_structure.validation_score:.0%}", "info")
            
            # Mark as validated
            form_structure.is_validated = True
            form_structure.add_agent_log(self.name, 
                f"Validation complete. Score: {form_structure.validation_score:.0%}, Issues: {total_issues}")
            
            self.status = "completed"
            return form_structure
            
        except Exception as e:
            self.log(f"Validation failed: {str(e)}", "error")
            self.status = "error"
            return form_structure
    
    def _validate_field(self, field: ExtractedField) -> List[str]:
        """Validate individual field"""
        issues = []
        
        # Check basic requirements
        if not field.label:
            issues.append(f"Field {field.name} has no label")
        
        if not field.type:
            issues.append(f"Field {field.name} has no type")
        
        # Validate field type matches content
        if field.type == "date" and "date" not in field.label.lower():
            pass  # This is ok, might be detected from format
        
        if field.type == "email" and "@" in field.label:
            issues.append(f"Email field {field.name} has @ in label")
        
        # Check for very long labels
        if len(field.label) > 200:
            issues.append(f"Field {field.name} has unusually long label")
        
        return issues
    
    def _calculate_field_confidence(self, field: ExtractedField) -> float:
        """Calculate confidence score for a field"""
        confidence = 0.5  # Base confidence
        
        # Boost for having item number
        if field.item_number:
            confidence += 0.3
        
        # Boost for standard field types
        if field.type in ["text", "checkbox", "date", "signature"]:
            confidence += 0.1
        
        # Boost for reasonable label length
        if 3 < len(field.label) < 100:
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    def _perform_form_specific_validation(self, form_structure: FormStructure):
        """Perform validation specific to known forms"""
        form_number = form_structure.form_number
        
        # Common validations for all forms
        self._check_required_sections(form_structure)
        
        # Form-specific checks - just warnings, not requirements
        expected_parts = {
            "I-539": 8,
            "I-129": 7,
            "I-485": 14,
            "N-400": 12,
            "I-765": 5,
            "G-28": 4,
            "I-130": 6,
            "I-140": 6,
            "I-824": 5
        }
        
        if form_number in expected_parts:
            expected = expected_parts[form_number]
            if len(form_structure.parts) < expected * 0.6:  # Allow some flexibility
                self.log(f"⚠️ {form_number} typically has {expected} parts, found {len(form_structure.parts)}", "warning")
                form_structure.validation_issues.append(f"Expected around {expected} parts for {form_number}")
    
    def _check_required_sections(self, form_structure: FormStructure):
        """Check for sections required in most USCIS forms"""
        # Most forms should have
        has_name_fields = False
        has_signature = False
        has_date_fields = False
        has_contact_info = False
        
        for part_name, fields in form_structure.parts.items():
            for field in fields:
                label_lower = field.label.lower()
                
                # Check for name fields
                if any(name_type in label_lower for name_type in self.common_field_patterns["name_fields"]):
                    has_name_fields = True
                
                # Check for signature
                if any(sig_type in label_lower for sig_type in self.common_field_patterns["signature_fields"]):
                    has_signature = True
                
                # Check for dates
                if field.type == "date" or any(date_type in label_lower for date_type in self.common_field_patterns["date_fields"]):
                    has_date_fields = True
                
                # Check for contact
                if any(contact_type in label_lower for contact_type in self.common_field_patterns["contact_fields"]):
                    has_contact_info = True
        
        # Report missing common elements
        if not has_name_fields:
            self.log("⚠️ No name fields found (unusual for USCIS forms)", "warning")
        
        if not has_signature:
            self.log("⚠️ No signature field found (most forms require signatures)", "warning")
            form_structure.validation_issues.append("No signature field found")
        
        if not has_date_fields:
            self.log("⚠️ No date fields found (unusual for USCIS forms)", "warning")

# AI Mapping Agent
class AIMappingAgent(Agent):
    """Intelligent field mapping using AI and patterns"""
    
    def __init__(self):
        super().__init__("AI Mapping Agent", "Intelligent Field Mapping")
        # Try to get client from session state first, then from secrets
        self.client = None
        if 'openai_client' in st.session_state:
            self.client = st.session_state['openai_client']
        else:
            self.client = get_openai_client()
        
        # Universal mapping patterns for all USCIS forms
        self.mapping_patterns = {
            # === Name Fields (Universal) ===
            "family name": "beneficiary.PersonalInfo.beneficiaryLastName",
            "last name": "beneficiary.PersonalInfo.beneficiaryLastName",
            "surname": "beneficiary.PersonalInfo.beneficiaryLastName",
            "given name": "beneficiary.PersonalInfo.beneficiaryFirstName",
            "first name": "beneficiary.PersonalInfo.beneficiaryFirstName",
            "middle name": "beneficiary.PersonalInfo.beneficiaryMiddleName",
            "full name": "beneficiary.PersonalInfo.fullName",
            
            # === Identification Numbers (Universal) ===
            "a-number": "beneficiary.PersonalInfo.alienNumber",
            "alien registration": "beneficiary.PersonalInfo.alienNumber",
            "alien number": "beneficiary.PersonalInfo.alienNumber",
            "uscis online account": "beneficiary.PersonalInfo.uscisOnlineAccountNumber",
            "online account number": "beneficiary.PersonalInfo.uscisOnlineAccountNumber",
            "social security": "beneficiary.PersonalInfo.beneficiarySsn",
            "ssn": "beneficiary.PersonalInfo.beneficiarySsn",
            "ein": "petitioner.PersonalInfo.ein",
            "employer identification": "petitioner.PersonalInfo.ein",
            
            # === Dates (Universal) ===
            "date of birth": "beneficiary.PersonalInfo.beneficiaryDateOfBirth",
            "birth date": "beneficiary.PersonalInfo.beneficiaryDateOfBirth",
            "dob": "beneficiary.PersonalInfo.beneficiaryDateOfBirth",
            "expiration date": "beneficiary.PassportDetails.passportExpiryDate",
            "expiry date": "beneficiary.PassportDetails.passportExpiryDate",
            "issue date": "beneficiary.PassportDetails.passportIssueDate",
            "valid from": "beneficiary.VisaDetails.visaIssueDate",
            "valid until": "beneficiary.VisaDetails.dateStatusExpires",
            
            # === Contact Information (Universal) ===
            "daytime telephone": "beneficiary.ContactInfo.daytimeTelephoneNumber",
            "daytime phone": "beneficiary.ContactInfo.daytimeTelephoneNumber",
            "mobile telephone": "beneficiary.ContactInfo.mobileTelephoneNumber",
            "mobile phone": "beneficiary.ContactInfo.mobileTelephoneNumber",
            "cell phone": "beneficiary.ContactInfo.mobileTelephoneNumber",
            "email address": "beneficiary.ContactInfo.emailAddress",
            "email": "beneficiary.ContactInfo.emailAddress",
            "fax number": "beneficiary.ContactInfo.faxNumber",
            "work phone": "beneficiary.ContactInfo.workPhone",
            "evening phone": "beneficiary.ContactInfo.eveningPhone",
            
            # === Address Components (Universal) ===
            "street number and name": "beneficiary.MailingAddress.addressStreet",
            "street address": "beneficiary.MailingAddress.addressStreet",
            "street": "beneficiary.MailingAddress.addressStreet",
            "address line": "beneficiary.MailingAddress.addressStreet",
            "city or town": "beneficiary.MailingAddress.addressCity",
            "city": "beneficiary.MailingAddress.addressCity",
            "state": "beneficiary.MailingAddress.addressState",
            "province": "beneficiary.MailingAddress.addressProvince",
            "zip code": "beneficiary.MailingAddress.addressZip",
            "postal code": "beneficiary.MailingAddress.addressPostalCode",
            "country": "beneficiary.MailingAddress.addressCountry",
            "apt": "beneficiary.MailingAddress.addressAptSteFlrNumber",
            "apartment": "beneficiary.MailingAddress.addressAptSteFlrNumber",
            "suite": "beneficiary.MailingAddress.addressAptSteFlrNumber",
            "in care of": "beneficiary.MailingAddress.inCareOfName",
            "c/o": "beneficiary.MailingAddress.inCareOfName",
            
            # === Country/Citizenship (Universal) ===
            "country of birth": "beneficiary.PersonalInfo.beneficiaryCountryOfBirth",
            "birth country": "beneficiary.PersonalInfo.beneficiaryCountryOfBirth",
            "country of citizenship": "beneficiary.PersonalInfo.beneficiaryCitizenOfCountry",
            "nationality": "beneficiary.PersonalInfo.beneficiaryCitizenOfCountry",
            "citizen of": "beneficiary.PersonalInfo.beneficiaryCitizenOfCountry",
            
            # === Immigration Status (Universal) ===
            "current nonimmigrant status": "beneficiary.VisaDetails.currentNonimmigrantStatus",
            "current status": "beneficiary.VisaDetails.currentNonimmigrantStatus",
            "visa type": "beneficiary.VisaDetails.currentNonimmigrantStatus",
            "visa class": "beneficiary.VisaDetails.currentNonimmigrantStatus",
            "i-94": "beneficiary.VisaDetails.i94ArrivalDepartureNumber",
            "arrival-departure": "beneficiary.VisaDetails.i94ArrivalDepartureNumber",
            "arrival record": "beneficiary.VisaDetails.i94ArrivalDepartureNumber",
            "date of last arrival": "beneficiary.VisaDetails.dateOfLastArrival",
            "date of entry": "beneficiary.VisaDetails.dateOfLastArrival",
            
            # === Travel Documents (Universal) ===
            "passport number": "beneficiary.PassportDetails.passportNumber",
            "passport": "beneficiary.PassportDetails.passportNumber",
            "travel document number": "beneficiary.PassportDetails.travelDocumentNumber",
            "travel document": "beneficiary.PassportDetails.travelDocumentNumber",
            "country of issuance": "beneficiary.PassportDetails.passportIssueCountry",
            "issuing country": "beneficiary.PassportDetails.passportIssueCountry",
            
            # === Case Information (Universal) ===
            "receipt number": "case.RelatedForms.receiptNumber",
            "case number": "case.RelatedForms.receiptNumber",
            "priority date": "case.ProcessingInfo.priorityDate",
            "filing date": "case.RelatedForms.dateFiledPreviousForm",
            
            # === Organization/Company (Universal) ===
            "company name": "petitioner.PersonalInfo.companyOrOrganizationName",
            "organization name": "petitioner.PersonalInfo.companyOrOrganizationName",
            "employer name": "petitioner.PersonalInfo.companyOrOrganizationName",
            "business name": "petitioner.PersonalInfo.companyOrOrganizationName",
            
            # === Other Common Fields ===
            "gender": "beneficiary.PersonalInfo.beneficiaryGender",
            "sex": "beneficiary.PersonalInfo.beneficiaryGender",
            "marital status": "beneficiary.PersonalInfo.maritalStatus",
            "number of children": "beneficiary.PersonalInfo.numberOfChildren",
            "sevis": "case.SchoolInfo.sevisIdNumber",
            "school name": "case.SchoolInfo.schoolName",
            
            # === Form-specific number patterns ===
            # These work by matching item numbers when present
            "1": "beneficiary.PersonalInfo.fullName",
            "1.a": "beneficiary.PersonalInfo.beneficiaryLastName",
            "1.b": "beneficiary.PersonalInfo.beneficiaryFirstName",
            "1.c": "beneficiary.PersonalInfo.beneficiaryMiddleName",
            "2": "beneficiary.PersonalInfo.alienNumber",
            "3": "beneficiary.PersonalInfo.uscisOnlineAccountNumber",
            "9": "beneficiary.PersonalInfo.beneficiaryDateOfBirth",
            "10": "beneficiary.PersonalInfo.beneficiarySsn",
            
            # === Processing Actions ===
            "extension": "case.ProcessingInfo.requestedAction",
            "change of status": "case.ProcessingInfo.changeOfStatusTo",
            "adjustment": "case.ProcessingInfo.adjustmentOfStatus",
            "renewal": "case.ProcessingInfo.renewal",
            "replacement": "case.ProcessingInfo.replacement",
        }
    
    def execute(self, form_structure: FormStructure) -> FormStructure:
        """Map fields using patterns and AI for any USCIS form"""
        self.status = "active"
        self.log(f"Starting intelligent field mapping for {form_structure.form_number}...")
        
        try:
            total_mapped = 0
            
            for part_name, fields in form_structure.parts.items():
                self.log(f"Mapping {part_name}...")
                
                # Get text fields that need mapping
                text_fields = [f for f in fields if f.type in ["text", "number", "date", "email", "phone"] 
                             and not f.db_path and not f.is_questionnaire and not f.manually_assigned]
                
                if text_fields:
                    # Phase 1: Pattern matching
                    for field in text_fields:
                        mapped = False
                        
                        # Try exact item number match first (if we have common patterns)
                        if field.item_number and field.item_number in self.mapping_patterns:
                            field.db_path = self.mapping_patterns[field.item_number]
                            field.ai_confidence = 0.95
                            total_mapped += 1
                            self.log(f"Item matched: {field.item_number} → {field.db_path}")
                            continue
                        
                        # Try label matching with all patterns
                        label_lower = field.label.lower()
                        
                        # Find best match
                        best_match = None
                        best_score = 0
                        
                        for pattern, db_path in self.mapping_patterns.items():
                            if len(pattern) <= 2:  # Skip single letters/numbers
                                continue
                            
                            # Calculate match score
                            score = self._calculate_match_score(label_lower, pattern.lower())
                            
                            if score > best_score and score > 0.7:  # 70% threshold
                                best_match = db_path
                                best_score = score
                        
                        if best_match:
                            field.db_path = best_match
                            field.ai_confidence = best_score
                            total_mapped += 1
                            self.log(f"Pattern matched: '{field.label}' → {best_match} (score: {best_score:.2f})")
                    
                    # Phase 2: AI mapping for remaining unmapped fields
                    if self.client:
                        unmapped = [f for f in text_fields if not f.db_path]
                        if unmapped:
                            ai_mapped = self._ai_batch_mapping_generic(unmapped, form_structure, part_name)
                            total_mapped += ai_mapped
            
            # Update statistics
            form_structure.mapped_fields = sum(1 for fields in form_structure.parts.values() 
                                             for f in fields if f.db_path)
            
            form_structure.add_agent_log(self.name, f"Mapped {total_mapped} fields")
            self.log(f"Mapping complete. Mapped {total_mapped} fields to database", "success")
            
            # Summary
            self.log("=== Mapping Summary ===", "info")
            mapped_by_type = defaultdict(int)
            for fields in form_structure.parts.values():
                for field in fields:
                    if field.db_path:
                        mapped_by_type[field.type] += 1
            
            for ftype, count in mapped_by_type.items():
                self.log(f"{ftype}: {count} fields mapped", "info")
            
            self.status = "completed"
            return form_structure
            
        except Exception as e:
            self.log(f"Mapping failed: {str(e)}", "error")
            self.status = "error"
            return form_structure
    
    def _calculate_match_score(self, label: str, pattern: str) -> float:
        """Calculate how well a label matches a pattern"""
        # Exact match
        if label == pattern:
            return 1.0
        
        # Contains full pattern
        if pattern in label:
            return 0.9
        
        # Label contains all words from pattern
        pattern_words = pattern.split()
        label_words = label.split()
        
        if all(word in label_words for word in pattern_words):
            return 0.85
        
        # Partial word match
        matching_words = sum(1 for word in pattern_words if word in label)
        if matching_words > 0:
            return 0.6 * (matching_words / len(pattern_words))
        
        return 0.0
    
    def _ai_batch_mapping_generic(self, fields: List[ExtractedField], form_structure: FormStructure, 
                                 part_name: str) -> int:
        """Use AI for intelligent mapping - generic for any form"""
        if not self.client or not fields:
            return 0
        
        try:
            # Prepare field info
            field_info = []
            for f in fields[:15]:  # Process up to 15 at a time
                field_info.append({
                    "item_number": f.item_number,
                    "label": f.label,
                    "type": f.type,
                    "part": part_name
                })
            
            # Get relevant DB paths
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
            Map these fields from USCIS Form {form_structure.form_number} {part_name} to appropriate database paths.
            
            Form Type: {form_structure.form_number} - {form_structure.form_title}
            Current Part: {part_name}
            
            Fields to map:
            {json.dumps(field_info, indent=2)}
            
            Available database paths include (partial list):
            {json.dumps(db_paths[:80], indent=2)}
            
            Universal mapping rules for USCIS forms:
            - Name fields: Item 1.a/1.b/1.c are typically Last/First/Middle names
            - Item 2 is often A-Number (alienNumber)
            - Item 3 is often USCIS Online Account Number
            - Date fields ending with (mm/dd/yyyy) should map to appropriate date fields
            - Address components should map to either MailingAddress or PhysicalAddress
            - Contact fields (phone, email) map to ContactInfo
            - For beneficiary forms (I-539, I-129F, etc.), use "beneficiary" object
            - For petitioner forms, use "petitioner" object
            - For attorney forms (G-28), use "attorney" object
            
            Consider the form type and part when mapping:
            - Immigration status fields → VisaDetails
            - Travel documents → PassportDetails
            - Personal info → PersonalInfo
            - Processing requests → ProcessingInfo
            
            Return ONLY a JSON object mapping item numbers or labels to database paths.
            If a field shouldn't be mapped to database (like Yes/No questions), omit it.
            
            Example: {{"1.a": "beneficiary.PersonalInfo.beneficiaryLastName", "email": "beneficiary.ContactInfo.emailAddress"}}
            """
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert at mapping USCIS form fields to database structures. Consider the form type and field context when mapping."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=1500
            )
            
            # Parse response
            response_text = response.choices[0].message.content
            
            # Extract JSON from response
            json_match = re.search(r'\{[^}]+\}', response_text, re.DOTALL)
            if json_match:
                mappings = json.loads(json_match.group())
            else:
                mappings = json.loads(response_text)
            
            mapped_count = 0
            for field in fields:
                # Try item number first, then label
                keys_to_try = []
                if field.item_number:
                    keys_to_try.append(field.item_number)
                keys_to_try.append(field.label)
                keys_to_try.append(field.label.lower())
                
                for key in keys_to_try:
                    if key in mappings:
                        field.db_path = mappings[key]
                        field.ai_confidence = 0.75
                        field.ai_suggestion = "AI Mapped"
                        mapped_count += 1
                        self.log(f"AI mapped: '{field.label}' → {field.db_path}")
                        break
            
            return mapped_count
            
        except Exception as e:
            self.log(f"AI mapping error: {str(e)}", "warning")
            return 0

# Field Display
def render_field_card(field: ExtractedField, idx: int, part_name: str):
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
                key=f"field_map_{field.field_id}_{idx}_{part_name.replace(' ', '_')}",
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
                key=f"quest_{field.field_id}_{idx}_{part_name.replace(' ', '_')}"
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
    openai_client = None
    openai_available = False
    
    # Try to get client
    if 'openai_client' in st.session_state and st.session_state['openai_client']:
        openai_client = st.session_state['openai_client']
        openai_available = True
    else:
        try:
            openai_client = get_openai_client()
            if openai_client:
                st.session_state['openai_client'] = openai_client
                openai_available = True
        except Exception as e:
            st.error(f"Error initializing OpenAI: {str(e)}")
            openai_available = False
    
    # Sidebar
    with st.sidebar:
        st.markdown("## ⚙️ Configuration")
        
        # Debug info for API key
        if st.checkbox("Show Debug Info", value=False):
            st.markdown("### 🔍 Debug Information")
            try:
                # Check OpenAI library
                st.info(f"OpenAI library available: {OPENAI_AVAILABLE}")
                
                # Check if secrets exist
                if hasattr(st, 'secrets'):
                    st.info("✅ Secrets object exists")
                    
                    # Show available keys (without values)
                    try:
                        secret_keys = list(st.secrets.keys()) if hasattr(st.secrets, 'keys') else []
                        if secret_keys:
                            st.write("Available keys:", [k for k in secret_keys if 'key' in k.lower() or 'openai' in k.lower()])
                        else:
                            st.warning("No keys found in secrets")
                    except Exception as e:
                        st.error(f"Error accessing secrets: {str(e)}")
                else:
                    st.error("❌ Secrets object not found")
                    
                # Check environment
                env_key = os.environ.get('OPENAI_API_KEY', None)
                if env_key:
                    st.info("✅ Found OPENAI_API_KEY in environment variables")
                else:
                    st.warning("❌ OPENAI_API_KEY not in environment")
                    
                # Check session state
                if 'openai_api_key' in st.session_state:
                    st.info("✅ API key stored in session state")
                    
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
            st.success("✅ OpenAI API Key configured and working!")
        else:
            st.warning("⚠️ OpenAI API Key not configured")
            with st.expander("Setup Instructions", expanded=True):
                st.markdown("""
                **Option 1: Add to Streamlit Secrets**
                1. Go to App Settings → Secrets
                2. Add: `OPENAI_API_KEY = "sk-..."`
                3. Reboot the app
                
                **Option 2: Enter API Key Below**
                """)
                
                manual_key = st.text_input(
                    "Enter OpenAI API Key", 
                    type="password", 
                    placeholder="sk-...",
                    help="Your key will be stored for this session only"
                )
                
                if st.button("Test API Key", type="primary"):
                    if manual_key and manual_key.startswith('sk-'):
                        with st.spinner("Testing API key..."):
                            try:
                                # Store the key
                                st.session_state['openai_api_key'] = manual_key
                                
                                # Try to create client
                                test_client = None
                                if OPENAI_AVAILABLE and OpenAI:
                                    try:
                                        test_client = OpenAI(api_key=manual_key)
                                        # Test the client with a simple request
                                        response = test_client.chat.completions.create(
                                            model="gpt-3.5-turbo",
                                            messages=[{"role": "user", "content": "Say 'test'"}],
                                            max_tokens=5
                                        )
                                        
                                        # Store in session state
                                        st.session_state['openai_client'] = test_client
                                        st.success("✅ API Key is valid and working!")
                                        time.sleep(1)
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"API Key test failed: {str(e)}")
                                        if 'proxies' in str(e):
                                            st.info("Note: Proxy issues detected. The app may still work.")
                            except Exception as e:
                                st.error(f"Error: {str(e)}")
                    else:
                        st.error("Please enter a valid OpenAI API key starting with 'sk-'")
        
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
                            
                            # Show summary with expandable details
                            with st.expander("📊 Extraction Summary", expanded=True):
                                # Overall summary
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.metric("Total Parts", len(form_structure.parts))
                                with col2:
                                    st.metric("Total Fields", form_structure.total_fields)
                                with col3:
                                    validated_pct = (form_structure.validated_fields / form_structure.total_fields * 100) if form_structure.total_fields > 0 else 0
                                    st.metric("Validated", f"{validated_pct:.0f}%")
                                
                                # Part-by-part breakdown
                                st.markdown("### 📑 Parts Extracted:")
                                
                                for part_name in sorted(form_structure.parts.keys()):
                                    fields = form_structure.parts[part_name]
                                    
                                    # Part header with field count
                                    st.markdown(f"**{part_name}**: {len(fields)} fields")
                                    
                                    # Show field details in columns
                                    col1, col2 = st.columns([1, 3])
                                    
                                    with col1:
                                        # Count by type
                                        type_counts = defaultdict(int)
                                        for f in fields:
                                            type_counts[f.type] += 1
                                        
                                        for ftype, count in type_counts.items():
                                            st.caption(f"{ftype}: {count}")
                                    
                                    with col2:
                                        # Show sample fields with item numbers
                                        sample_fields = [f for f in fields if f.item_number][:8]
                                        if sample_fields:
                                            items = []
                                            for f in sample_fields:
                                                label = f.label[:40] + "..." if len(f.label) > 40 else f.label
                                                items.append(f"{f.item_number}. {label}")
                                            st.caption("Fields: " + " | ".join(items))
                                        else:
                                            st.caption("No numbered items found")
                                
                                # Show any validation issues
                                if form_structure.validation_issues:
                                    st.markdown("### ⚠️ Validation Issues:")
                                    for issue in form_structure.validation_issues[:5]:
                                        st.warning(issue)
                            
                            # Agent logs
                            with st.expander("🤖 Agent Activity Logs"):
                                for agent_name, logs in form_structure.agent_logs.items():
                                    st.markdown(f"**{agent_name}:**")
                                    for log in logs[-10:]:  # Show last 10 logs
                                        st.caption(log)
    
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
                    render_field_card(field, idx, selected_part)
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
