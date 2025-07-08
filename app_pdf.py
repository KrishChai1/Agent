#!/usr/bin/env python3
"""
Enhanced Smart USCIS Form Reader with Agent Feedback Loops
Agents collaborate and iterate until extraction is complete and validated
"""

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

import streamlit as st

# Initialize globals
OPENAI_AVAILABLE = False
OpenAI = None

# Try imports
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    fitz = None

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None

# Page config
st.set_page_config(
    page_title="Smart USCIS Form Reader - Collaborative Multi-Agent System",
    page_icon="🤖",
    layout="wide"
)

# Enhanced CSS
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
        animation: pulse 1.5s infinite;
    }
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.8; }
        100% { opacity: 1; }
    }
    .agent-error {
        border-left: 4px solid #f44336;
        background: #fef1f1;
    }
    .agent-feedback {
        border-left: 4px solid #ff9800;
        background: #fff3e0;
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
    .feedback-message {
        background: #fff3e0;
        border-left: 4px solid #ff9800;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 4px;
    }
    .iteration-counter {
        background: #e3f2fd;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        display: inline-block;
        margin: 0.5rem 0;
    }
    .extraction-stats {
        background: #f5f5f5;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Database structure (same as before)
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

# Initialize OpenAI client
def get_openai_client():
    """Get OpenAI client from secrets or environment"""
    global OPENAI_AVAILABLE, OpenAI
    
    if not OPENAI_AVAILABLE or not OpenAI:
        return None
        
    try:
        api_key = None
        
        # Check session state first
        if 'openai_api_key' in st.session_state:
            api_key = st.session_state['openai_api_key']
        
        # Check secrets
        if not api_key and hasattr(st, 'secrets'):
            try:
                api_key = st.secrets.get('OPENAI_API_KEY', None)
            except:
                pass
        
        # Check environment
        if not api_key:
            api_key = os.environ.get('OPENAI_API_KEY', None)
        
        if api_key:
            try:
                client = OpenAI(api_key=api_key)
                return client
            except:
                return None
        return None
    except:
        return None

@dataclass
class ValidationFeedback:
    """Feedback from validator to extractor"""
    missing_parts: List[Dict[str, Any]] = field(default_factory=list)
    incomplete_parts: List[Dict[str, Any]] = field(default_factory=list)
    field_issues: List[Dict[str, Any]] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    severity: str = "info"  # info, warning, error
    needs_retry: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "missing_parts": self.missing_parts,
            "incomplete_parts": self.incomplete_parts,
            "field_issues": self.field_issues,
            "suggestions": self.suggestions,
            "severity": self.severity,
            "needs_retry": self.needs_retry
        }

@dataclass
class ExtractedField:
    """Enhanced field with extraction metadata"""
    name: str
    label: str
    type: str
    value: str = ""
    
    # Location info
    page: int = 1
    part: str = "Part 1"
    part_number: int = 1
    part_title: str = ""
    item_number: str = ""
    
    # Identification
    field_id: str = ""
    field_hash: str = ""
    raw_field_name: str = ""
    
    # Extraction metadata
    extraction_method: str = ""  # "pattern", "ai", "widget", "manual"
    extraction_confidence: float = 0.0
    extraction_iteration: int = 1
    
    # Mapping info
    db_path: Optional[str] = None
    is_questionnaire: bool = False
    manually_assigned: bool = False
    
    # Validation
    is_validated: bool = False
    validation_confidence: float = 0.0
    
    def __post_init__(self):
        if self.item_number:
            self.field_id = f"pt{self.part_number}_{self.item_number.replace('.', '')}"
        else:
            self.field_id = f"pt{self.part_number}_field_{self.name[:10]}"
        
        if not self.field_hash:
            content = f"{self.name}_{self.part}_{self.page}_{self.item_number}_{self.label}_{time.time()}"
            self.field_hash = hashlib.md5(content.encode()).hexdigest()[:12]
        
        self.field_id = f"{self.field_id}_{self.field_hash[:6]}"

@dataclass
class FormStructure:
    """Enhanced form structure with iteration tracking"""
    form_number: str
    form_title: str
    form_edition: str = ""
    total_pages: int = 0
    parts: Dict[str, List[ExtractedField]] = field(default_factory=OrderedDict)
    
    # Agent tracking
    agent_logs: Dict[str, List[str]] = field(default_factory=dict)
    agent_feedback: List[ValidationFeedback] = field(default_factory=list)
    extraction_iterations: int = 0
    
    # Statistics
    total_fields: int = 0
    validated_fields: int = 0
    mapped_fields: int = 0
    
    # Expected structure (for validation)
    expected_parts: Optional[List[str]] = None
    expected_fields_per_part: Optional[Dict[str, int]] = None
    
    # Validation
    is_validated: bool = False
    validation_score: float = 0.0
    validation_issues: List[str] = field(default_factory=list)
    
    def add_agent_log(self, agent_name: str, message: str):
        if agent_name not in self.agent_logs:
            self.agent_logs[agent_name] = []
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.agent_logs[agent_name].append(f"{timestamp} - {message}")

# Base Agent Class
class Agent(ABC):
    """Enhanced base agent with feedback handling"""
    
    def __init__(self, name: str, role: str):
        self.name = name
        self.role = role
        self.status = "idle"
        self.logs = []
        self.iteration = 0
        
    @abstractmethod
    def execute(self, *args, **kwargs) -> Any:
        pass
    
    def handle_feedback(self, feedback: ValidationFeedback) -> Any:
        """Handle feedback from other agents"""
        pass
    
    def log(self, message: str, level: str = "info"):
        self.logs.append({
            "timestamp": datetime.now().strftime('%H:%M:%S'),
            "message": message,
            "level": level,
            "iteration": self.iteration
        })
        
        # Display in UI
        if 'agent_status_container' in st.session_state:
            container = st.session_state.agent_status_container
            with container:
                if level == "error":
                    st.error(f"🔴 **{self.name}** (Iteration {self.iteration}): {message}")
                elif level == "success":
                    st.success(f"🟢 **{self.name}** (Iteration {self.iteration}): {message}")
                elif level == "warning":
                    st.warning(f"🟡 **{self.name}** (Iteration {self.iteration}): {message}")
                elif level == "feedback":
                    st.markdown(f'<div class="feedback-message">🔄 **{self.name}**: {message}</div>', 
                              unsafe_allow_html=True)
                else:
                    st.info(f"ℹ️ **{self.name}** (Iteration {self.iteration}): {message}")

# Enhanced Research Agent with feedback handling
class ResearchAgent(Agent):
    """Enhanced extraction with iterative improvement"""
    
    def __init__(self):
        super().__init__("Research Agent", "Intelligent Field Extraction")
        self.client = get_openai_client()
        self.pdf_bytes = None
        self.doc = None
        self.page_texts = []
        self.extraction_strategies = [
            "comprehensive",  # All patterns + AI
            "deep_analysis",  # More aggressive patterns
            "ai_guided",      # AI-first approach
            "manual_search"   # Specific part search
        ]
        self.current_strategy_index = 0
    
    def execute(self, pdf_file=None, use_ai: bool = True, 
                form_structure: Optional[FormStructure] = None,
                feedback: Optional[ValidationFeedback] = None) -> Optional[FormStructure]:
        """Extract with optional feedback-driven refinement"""
        self.status = "active"
        self.iteration += 1
        
        # First iteration - full extraction
        if pdf_file is not None:
            self.pdf_bytes = pdf_file.read() if hasattr(pdf_file, 'read') else pdf_file
            self.doc = fitz.open(stream=self.pdf_bytes, filetype="pdf")
            self.page_texts = [page.get_text() for page in self.doc]
            
            # Identify form
            form_info = self._identify_form(self.doc)
            self.log(f"Identified form: {form_info['number']} - {form_info['title']}", "success")
            
            form_structure = FormStructure(
                form_number=form_info['number'],
                form_title=form_info['title'],
                form_edition=form_info.get('edition', ''),
                total_pages=len(self.doc)
            )
            
            # Set expected structure based on form type
            self._set_expected_structure(form_structure)
        
        # Handle feedback-driven re-extraction
        if feedback and form_structure:
            self.log(f"Received feedback - attempting targeted extraction", "feedback")
            return self._handle_extraction_feedback(form_structure, feedback, use_ai)
        
        # Regular extraction
        strategy = self.extraction_strategies[min(self.current_strategy_index, len(self.extraction_strategies)-1)]
        self.log(f"Using extraction strategy: {strategy}", "info")
        
        form_structure.extraction_iterations = self.iteration
        
        # Execute based on strategy
        if strategy == "comprehensive":
            self._comprehensive_extraction(form_structure, use_ai)
        elif strategy == "deep_analysis":
            self._deep_analysis_extraction(form_structure)
        elif strategy == "ai_guided" and use_ai and self.client:
            self._ai_guided_extraction(form_structure)
        else:
            self._manual_search_extraction(form_structure)
        
        if self.doc:
            self.doc.close()
        
        form_structure.add_agent_log(self.name, f"Iteration {self.iteration}: Extracted {form_structure.total_fields} fields using {strategy}")
        self.log(f"Extraction complete: {form_structure.total_fields} fields found", "success")
        
        self.status = "completed"
        return form_structure
    
    def handle_feedback(self, feedback: ValidationFeedback) -> Any:
        """Process feedback and adjust strategy"""
        self.current_strategy_index = min(self.current_strategy_index + 1, len(self.extraction_strategies) - 1)
        self.log(f"Adjusting strategy based on feedback", "feedback")
        return feedback
    
    def _handle_extraction_feedback(self, form_structure: FormStructure, 
                                  feedback: ValidationFeedback, use_ai: bool) -> FormStructure:
        """Handle specific feedback from validator"""
        self.log("Processing validator feedback...", "feedback")
        
        # Target missing parts
        if feedback.missing_parts:
            self.log(f"Searching for {len(feedback.missing_parts)} missing parts", "warning")
            for missing_part in feedback.missing_parts:
                self._search_for_specific_part(form_structure, missing_part)
        
        # Enhance incomplete parts
        if feedback.incomplete_parts:
            self.log(f"Enhancing {len(feedback.incomplete_parts)} incomplete parts", "warning")
            for incomplete_part in feedback.incomplete_parts:
                self._enhance_part_extraction(form_structure, incomplete_part)
        
        # Address field issues
        if feedback.field_issues:
            self.log(f"Addressing {len(feedback.field_issues)} field issues", "warning")
            for issue in feedback.field_issues:
                self._fix_field_issue(form_structure, issue)
        
        # Apply suggestions
        if feedback.suggestions and use_ai and self.client:
            self._apply_ai_suggestions(form_structure, feedback.suggestions)
        
        # Recalculate totals
        form_structure.total_fields = sum(len(fields) for fields in form_structure.parts.values())
        
        return form_structure
    
    def _search_for_specific_part(self, form_structure: FormStructure, missing_part: Dict):
        """Search for a specific missing part"""
        part_num = missing_part.get('number', 0)
        part_name = missing_part.get('name', f'Part {part_num}')
        expected_fields = missing_part.get('expected_fields', 10)
        
        self.log(f"Targeted search for {part_name}", "info")
        
        # Search all pages for this part
        found_fields = []
        for page_num, page_text in enumerate(self.page_texts):
            # Enhanced patterns for finding parts
            patterns = [
                rf'Part\s+{part_num}\b',
                rf'PART\s+{part_num}\b',
                rf'Section\s+{part_num}\b',
                rf'{part_name}',
                # Roman numerals
                rf'Part\s+{self._to_roman(part_num)}\b' if part_num <= 10 else None,
            ]
            
            for pattern in patterns:
                if pattern and re.search(pattern, page_text, re.IGNORECASE):
                    self.log(f"Found {part_name} on page {page_num + 1}", "success")
                    
                    # Extract fields from this section
                    page = self.doc[page_num]
                    fields = self._extract_fields_aggressive(
                        page, page_num + 1, page_text, 
                        part_name, part_num, ""
                    )
                    
                    found_fields.extend(fields)
                    break
        
        # Add found fields
        if found_fields:
            if part_name not in form_structure.parts:
                form_structure.parts[part_name] = []
            
            # Add unique fields
            existing_items = {f.item_number for f in form_structure.parts[part_name] if f.item_number}
            for field in found_fields:
                if not field.item_number or field.item_number not in existing_items:
                    form_structure.parts[part_name].append(field)
                    form_structure.total_fields += 1
            
            self.log(f"Added {len(found_fields)} fields to {part_name}", "success")
    
    def _enhance_part_extraction(self, form_structure: FormStructure, incomplete_part: Dict):
        """Enhance extraction for incomplete parts"""
        part_name = incomplete_part.get('name', '')
        current_fields = incomplete_part.get('current_fields', 0)
        expected_fields = incomplete_part.get('expected_fields', 10)
        
        if part_name not in form_structure.parts:
            return
        
        self.log(f"Enhancing {part_name} (has {current_fields}, expects ~{expected_fields})", "info")
        
        # Find which pages contain this part
        part_pages = []
        part_num = int(re.search(r'\d+', part_name).group()) if re.search(r'\d+', part_name) else 1
        
        for page_num, page_text in enumerate(self.page_texts):
            if re.search(rf'Part\s+{part_num}\b', page_text, re.IGNORECASE):
                part_pages.append(page_num)
        
        # Also check adjacent pages
        if part_pages:
            min_page = max(0, min(part_pages) - 1)
            max_page = min(len(self.page_texts) - 1, max(part_pages) + 2)
            part_pages = list(range(min_page, max_page + 1))
        
        # Deep extraction on these pages
        new_fields = []
        for page_num in part_pages:
            page = self.doc[page_num]
            page_text = self.page_texts[page_num]
            
            # Use aggressive extraction
            fields = self._extract_fields_aggressive(
                page, page_num + 1, page_text,
                part_name, part_num, ""
            )
            new_fields.extend(fields)
        
        # Add new unique fields
        existing_items = {f.item_number for f in form_structure.parts[part_name] if f.item_number}
        added = 0
        for field in new_fields:
            if not field.item_number or field.item_number not in existing_items:
                form_structure.parts[part_name].append(field)
                form_structure.total_fields += 1
                added += 1
        
        self.log(f"Enhanced {part_name} with {added} additional fields", "success")
    
    def _comprehensive_extraction(self, form_structure: FormStructure, use_ai: bool):
        """Comprehensive extraction using all methods"""
        # Step 1: AI analysis if available
        if use_ai and self.client:
            full_text = "\n".join(self.page_texts[:5])  # First 5 pages
            ai_parts = self._ai_extract_parts(full_text[:30000], form_structure.form_number)
            if ai_parts:
                self.log(f"AI identified {len(ai_parts)} parts", "success")
                self._extract_using_ai_parts(form_structure, ai_parts)
        
        # Step 2: Pattern-based extraction
        self._extract_using_patterns(form_structure)
        
        # Step 3: Widget extraction
        self._extract_from_all_widgets(form_structure)
        
        # Step 4: Validate against expected structure
        self._validate_extraction_completeness(form_structure)
    
    def _deep_analysis_extraction(self, form_structure: FormStructure):
        """Deep analysis with aggressive patterns"""
        self.log("Performing deep analysis extraction", "info")
        
        # Find all possible parts first
        all_parts = self._find_all_parts_aggressive()
        
        for part_info in all_parts:
            part_name = f"Part {part_info['number']}"
            if part_name not in form_structure.parts:
                form_structure.parts[part_name] = []
            
            # Extract from all pages that might contain this part
            for page_num, page_text in enumerate(self.page_texts):
                if self._might_contain_part(page_text, part_info['number']):
                    page = self.doc[page_num]
                    fields = self._extract_fields_aggressive(
                        page, page_num + 1, page_text,
                        part_name, part_info['number'], part_info.get('title', '')
                    )
                    
                    # Add unique fields
                    for field in fields:
                        if not any(f.item_number == field.item_number and f.label == field.label 
                                 for f in form_structure.parts[part_name]):
                            form_structure.parts[part_name].append(field)
                            form_structure.total_fields += 1
    
    def _extract_fields_aggressive(self, page, page_num: int, text: str, 
                                  part: str, part_number: int, part_title: str) -> List[ExtractedField]:
        """Aggressive field extraction with more patterns"""
        fields = []
        lines = text.split('\n')
        
        # Extended patterns
        patterns = [
            # Standard patterns
            (re.compile(r'^(\d+)(?:\.([a-z]))?\.\s+(.+?)(?:\s*\(.*\))?$', re.IGNORECASE), 'standard'),
            (re.compile(r'^(\d+)(?:\.([a-z]))?\s+([A-Z][^\.]+)$', re.IGNORECASE), 'no_period'),
            (re.compile(r'^Item\s+Number\s+(\d+)(?:\.([a-z]))?\.\s*(.+)', re.IGNORECASE), 'item_number'),
            
            # Questions
            (re.compile(r'^(\d+)\.\s+(Are\s+you|Have\s+you|Do\s+you|Is\s+|Was\s+|Will\s+|Did\s+|Were\s+|Can\s+|Would\s+|Should\s+|Could\s+|Has\s+|Does\s+)(.+)', re.IGNORECASE), 'question'),
            
            # More formats
            (re.compile(r'^\((\d+)(?:\.([a-z]))?\)\s*(.+)', re.IGNORECASE), 'parentheses'),
            (re.compile(r'^(\d+)\s*[-–—]\s*(.+)', re.IGNORECASE), 'dash'),
            (re.compile(r'^([A-Z])\.\s+(.+)', re.IGNORECASE), 'letter'),
            (re.compile(r'^Line\s+(\d+)(?:\.([a-z]))?\.\s*(.+)', re.IGNORECASE), 'line_number'),
            (re.compile(r'^\[(\d+)\]\s*(.+)', re.IGNORECASE), 'box_number'),
            (re.compile(r'^(\d+)\.?\s*$', re.IGNORECASE), 'number_only'),
            
            # Field labels
            (re.compile(r'^(Full Name|Legal Name|Name|Date of Birth|Place of Birth|Country of Birth|Social Security|SSN|A-Number|Alien|USCIS)', re.IGNORECASE), 'keyword_field'),
            (re.compile(r'^(Street Address|Street|City|State|ZIP|Postal|Country|Province|Address)', re.IGNORECASE), 'address_field'),
            (re.compile(r'^(Phone|Telephone|Mobile|Cell|Email|Fax)', re.IGNORECASE), 'contact_field'),
            (re.compile(r'^(Passport|Travel Document|Visa|Status|I-94)', re.IGNORECASE), 'document_field'),
            
            # Indented items
            (re.compile(r'^\s{2,}(\d+)(?:\.([a-z]))?\.\s+(.+)', re.IGNORECASE), 'indented'),
            
            # Items with colons
            (re.compile(r'^(\d+)(?:\.([a-z]))?\s*:\s*(.+)', re.IGNORECASE), 'colon'),
            
            # Checkbox patterns
            (re.compile(r'^\s*\[\s*\]\s*(.+)', re.IGNORECASE), 'checkbox_empty'),
            (re.compile(r'^\s*☐\s*(.+)', re.IGNORECASE), 'checkbox_unicode'),
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
                        field.extraction_method = "pattern"
                        field.extraction_iteration = self.iteration
                        fields.append(field)
                        if pattern_type == 'number_only':
                            i += 1  # Skip next line
                    break
            
            i += 1
        
        # Also get widgets
        widget_fields = self._extract_from_widgets(page, page_num, part, part_number, part_title)
        for wf in widget_fields:
            wf.extraction_iteration = self.iteration
        
        # Merge
        all_fields = self._merge_fields(fields, widget_fields)
        
        return all_fields
    
    def _set_expected_structure(self, form_structure: FormStructure):
        """Set expected structure based on form type"""
        expected_structures = {
            "I-539": {
                "parts": ["Part 1", "Part 2", "Part 3", "Part 4", "Part 5", "Part 6", "Part 7", "Part 8"],
                "min_fields_per_part": {"Part 1": 15, "Part 2": 20, "Part 3": 30, "Part 4": 10, 
                                      "Part 5": 5, "Part 6": 15, "Part 7": 5, "Part 8": 5}
            },
            "I-129": {
                "parts": ["Part 1", "Part 2", "Part 3", "Part 4", "Part 5", "Part 6", "Part 7"],
                "min_fields_per_part": {"Part 1": 10, "Part 2": 20, "Part 3": 15, "Part 4": 20}
            },
            "I-485": {
                "parts": ["Part 1", "Part 2", "Part 3", "Part 4", "Part 5", "Part 6", "Part 7", 
                         "Part 8", "Part 9", "Part 10", "Part 11", "Part 12", "Part 13", "Part 14"],
                "min_fields_per_part": {}
            },
            "I-765": {
                "parts": ["Part 1", "Part 2", "Part 3", "Part 4", "Part 5"],
                "min_fields_per_part": {"Part 1": 10, "Part 2": 20, "Part 3": 10}
            }
        }
        
        if form_structure.form_number in expected_structures:
            exp = expected_structures[form_structure.form_number]
            form_structure.expected_parts = exp["parts"]
            form_structure.expected_fields_per_part = exp.get("min_fields_per_part", {})
    
    def _validate_extraction_completeness(self, form_structure: FormStructure):
        """Validate extraction against expected structure"""
        if not form_structure.expected_parts:
            return
        
        missing_parts = []
        incomplete_parts = []
        
        for expected_part in form_structure.expected_parts:
            if expected_part not in form_structure.parts:
                missing_parts.append(expected_part)
            elif form_structure.expected_fields_per_part:
                min_fields = form_structure.expected_fields_per_part.get(expected_part, 5)
                actual_fields = len(form_structure.parts[expected_part])
                if actual_fields < min_fields * 0.7:  # Allow 30% margin
                    incomplete_parts.append({
                        "name": expected_part,
                        "expected": min_fields,
                        "actual": actual_fields
                    })
        
        if missing_parts:
            self.log(f"Missing expected parts: {missing_parts}", "warning")
        
        if incomplete_parts:
            for part in incomplete_parts:
                self.log(f"{part['name']} seems incomplete: {part['actual']} fields (expected ~{part['expected']})", "warning")
    
    def _might_contain_part(self, page_text: str, part_num: int) -> bool:
        """Check if page might contain a specific part"""
        patterns = [
            rf'Part\s+{part_num}\b',
            rf'PART\s+{part_num}\b',
            rf'Section\s+{part_num}\b',
            str(part_num) + '.',  # Just the number with period
        ]
        
        for pattern in patterns:
            if re.search(pattern, page_text, re.IGNORECASE):
                return True
        return False
    
    def _to_roman(self, num: int) -> str:
        """Convert number to Roman numeral"""
        values = [10, 9, 5, 4, 1]
        symbols = ["X", "IX", "V", "IV", "I"]
        roman = ""
        for v, s in zip(values, symbols):
            count = num // v
            if count:
                roman += s * count
                num -= v * count
        return roman
    
    # Keep all the original extraction methods from before
    def _identify_form(self, doc) -> Dict:
        """Identify form type and metadata"""
        first_page_text = doc[0].get_text().upper()
        
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
        
        for form_num, title in form_mapping.items():
            if form_num in first_page_text:
                form_info["number"] = form_num
                form_info["title"] = title
                break
        
        edition_match = re.search(r'EDITION\s+(\d{2}/\d{2}/\d{2})', first_page_text)
        if edition_match:
            form_info["edition"] = edition_match.group(1)
        
        return form_info
    
    def _find_all_parts_aggressive(self) -> List[Dict]:
        """Aggressive part finding"""
        full_text = "\n".join(self.page_texts)
        parts = []
        found_parts = set()
        
        # Multiple pattern strategies
        part_patterns = [
            r'Part\s+(\d+)\.?\s*[-–:]?\s*([^\n]+)',
            r'PART\s+(\d+)\.?\s*[-–:]?\s*([^\n]+)',
            r'Section\s+([A-Z]|[0-9]+)\.?\s*[-–:]?\s*([^\n]+)',
            r'Part\s+(\d+)\s*\n\s*([^\n]+)',
            r'Part\s+([IVX]+)\.?\s*[-–:]?\s*([^\n]+)',
            r'\n(\d+)\.\s+(Information About|Application Type|Processing Information|Additional Information|Contact Information|Signature)',
        ]
        
        for pattern in part_patterns:
            matches = re.finditer(pattern, full_text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                if len(match.groups()) >= 2:
                    part_id = match.group(1)
                    part_title = match.group(2).strip()
                else:
                    part_title = match.group(1) if match.groups() else ""
                    part_id = str(len(parts) + 1)
                
                # Clean and convert
                part_title = re.sub(r'\s+', ' ', part_title)
                part_title = re.sub(r'[^\w\s,()-]', '', part_title).strip()[:150]
                
                try:
                    part_num = int(part_id)
                except:
                    if part_id.isalpha():
                        part_num = ord(part_id.upper()) - ord('A') + 1
                    else:
                        part_num = len(parts) + 1
                
                if part_num not in found_parts and part_title:
                    found_parts.add(part_num)
                    parts.append({'number': part_num, 'title': part_title})
        
        # Always have at least one part
        if not parts:
            parts.append({'number': 1, 'title': 'Form Fields'})
        
        parts.sort(key=lambda x: x['number'])
        return parts
    
    # Include all other extraction methods from original code...
    def _ai_extract_parts(self, text: str, form_number: str) -> Optional[Dict[str, Dict]]:
        """Use AI to extract form parts and fields"""
        if not self.client:
            return None
        
        try:
            prompt = f"""
            Analyze this USCIS {form_number} form and extract ALL parts/sections with their fields.
            Be EXTREMELY thorough - this form should have many parts and hundreds of fields total.
            
            Text sample:
            {text}
            
            Expected structure for {form_number}:
            - I-539 typically has 8 parts
            - I-129 typically has 7 parts  
            - I-485 typically has 14 parts
            - Most parts have 10-40 fields each
            
            Instructions:
            1. Find ALL parts/sections - look for:
               - "Part 1", "Part 2", etc.
               - "Section A", "Section B"
               - "PART I", "PART II"
               - Parts continue across pages - don't stop at page breaks
            
            2. For each part, extract ALL fields including:
               - Item numbers: 1, 2, 3 or 1., 2., 3.
               - Sub-items: 1.a., 1.b., 2.a., 2.b.
               - ALL questions, checkboxes, text fields
               - Don't skip any fields
            
            3. Common field patterns:
               - Personal info: names (1.a, 1.b, 1.c), dates, numbers
               - Yes/No questions with checkboxes
               - Address fields with multiple components
               - Status and document fields
            
            Return comprehensive JSON:
            {{
                "Part 1": {{
                    "title": "Information About You",
                    "fields": [
                        {{"item": "1.a", "label": "Family Name (Last Name)", "type": "text"}},
                        {{"item": "1.b", "label": "Given Name (First Name)", "type": "text"}},
                        {{"item": "1.c", "label": "Middle Name", "type": "text"}},
                        {{"item": "2", "label": "A-Number", "type": "number"}},
                        // ... ALL other fields
                    ]
                }},
                // ... ALL other parts
            }}
            
            Field types: text, number, date, checkbox, radio, signature, email, phone
            
            BE EXHAUSTIVE - find EVERY part and EVERY field. Missing fields is a critical error.
            """
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo-16k" if len(text) > 10000 else "gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert USCIS form analyzer. Be EXTREMELY thorough - these forms have hundreds of fields and you must find them ALL."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=4000
            )
            
            response_text = response.choices[0].message.content
            
            # Extract JSON
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                result = json.loads(json_match.group())
            else:
                result = json.loads(response_text)
            
            # Log findings
            total_fields = sum(len(part.get('fields', [])) for part in result.values())
            self.log(f"AI found {len(result)} parts with {total_fields} total fields", "info")
            
            return result
            
        except Exception as e:
            self.log(f"AI extraction error: {str(e)}", "warning")
            return None
    
    def _extract_using_ai_parts(self, form_structure: FormStructure, ai_parts: Dict):
        """Extract fields using AI-identified parts"""
        for part_name, part_info in ai_parts.items():
            part_number = 1
            num_match = re.search(r'\d+', part_name)
            if num_match:
                part_number = int(num_match.group())
            
            part_title = part_info.get('title', '')
            
            if part_name not in form_structure.parts:
                form_structure.parts[part_name] = []
                self.log(f"Processing {part_name}: {part_title}")
            
            for field_info in part_info.get('fields', []):
                field = ExtractedField(
                    name=f"field_{field_info['item'].replace('.', '_')}",
                    label=field_info['label'],
                    type=field_info.get('type', 'text'),
                    page=1,
                    part=part_name,
                    part_number=part_number,
                    part_title=part_title,
                    item_number=field_info['item'],
                    extraction_method="ai",
                    extraction_iteration=self.iteration
                )
                
                if field.type in ["checkbox", "radio"]:
                    field.is_questionnaire = True
                
                form_structure.parts[part_name].append(field)
                form_structure.total_fields += 1
    
    def _extract_using_patterns(self, form_structure: FormStructure):
        """Pattern-based extraction"""
        all_parts = self._find_all_parts_aggressive()
        self.log(f"Pattern extraction found {len(all_parts)} parts", "info")
        
        for part_info in all_parts:
            part_name = f"Part {part_info['number']}"
            if part_name not in form_structure.parts:
                form_structure.parts[part_name] = []
        
        current_part = 1
        
        for page_num, page in enumerate(self.doc):
            page_text = self.page_texts[page_num]
            
            # Check for part transitions
            for part_info in all_parts:
                if self._is_part_on_page(part_info, page_text):
                    current_part = part_info['number']
            
            part_name = f"Part {current_part}"
            part_info = next((p for p in all_parts if p['number'] == current_part), 
                           {'number': current_part, 'title': part_name})
            
            fields = self._extract_fields_comprehensive(
                page, page_num + 1, page_text, part_name, 
                part_info['number'], part_info.get('title', '')
            )
            
            for field in fields:
                if not any(f.item_number == field.item_number and f.label == field.label 
                         for f in form_structure.parts[part_name]):
                    form_structure.parts[part_name].append(field)
                    form_structure.total_fields += 1
    
    def _extract_from_all_widgets(self, form_structure: FormStructure):
        """Extract from all PDF widgets"""
        current_part = 1
        
        for page_num, page in enumerate(self.doc):
            # Determine current part from page
            page_text = self.page_texts[page_num]
            part_match = re.search(r'Part\s+(\d+)', page_text, re.IGNORECASE)
            if part_match:
                current_part = int(part_match.group(1))
            
            part_name = f"Part {current_part}"
            if part_name not in form_structure.parts:
                form_structure.parts[part_name] = []
            
            widget_fields = self._extract_from_widgets(
                page, page_num + 1, part_name, current_part, ""
            )
            
            for field in widget_fields:
                if not any(f.raw_field_name == field.raw_field_name 
                         for f in form_structure.parts[part_name]):
                    form_structure.parts[part_name].append(field)
                    form_structure.total_fields += 1
    
    def _is_part_on_page(self, part_info: Dict, page_text: str) -> bool:
        """Check if a specific part starts on this page"""
        part_num = part_info['number']
        patterns = [
            f"Part\\s+{part_num}\\b",
            f"PART\\s+{part_num}\\b", 
            f"Section\\s+{part_num}\\b"
        ]
        
        for pattern in patterns:
            if re.search(pattern, page_text, re.IGNORECASE):
                return True
        return False
    
    def _extract_fields_comprehensive(self, page, page_num: int, text: str, part: str, 
                                    part_number: int, part_title: str) -> List[ExtractedField]:
        """Standard comprehensive extraction"""
        return self._extract_fields_aggressive(page, page_num, text, part, part_number, part_title)
    
    def _create_field_from_match(self, match, pattern_type: str, line: str, lines: List[str], 
                               line_index: int, page_num: int, part: str, part_number: int, 
                               part_title: str) -> Optional[ExtractedField]:
        """Create field from regex match"""
        # Extract components
        if pattern_type == 'number_only':
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
        elif pattern_type in ['keyword_field', 'address_field', 'contact_field', 'document_field']:
            item_main = f"F{line_index}"
            item_sub = ""
            label_text = match.group(1)
        elif pattern_type in ['checkbox_empty', 'checkbox_unicode']:
            item_main = f"CB{line_index}"
            item_sub = ""
            label_text = match.group(1)
        elif pattern_type in ['standard', 'no_period', 'item_number', 'parentheses', 'line_number', 'indented', 'colon']:
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
        else:
            return None
        
        # Clean label
        label_text = label_text.strip()
        label_text = re.sub(r'[\.;:]+$', '', label_text)
        
        # Build item number
        item_number = item_main
        if item_sub:
            item_number += f".{item_sub}"
        
        # Skip if too short
        if len(label_text) < 3 or label_text.lower() in ['yes', 'no', 'n/a', 'na', 'page']:
            return None
        
        # Determine field type
        field_type = self._determine_field_type(label_text, lines, line_index)
        
        # For checkbox patterns, force checkbox type
        if pattern_type in ['checkbox_empty', 'checkbox_unicode']:
            field_type = "checkbox"
        
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
            raw_field_name=line,
            extraction_method="pattern",
            extraction_confidence=0.8
        )
        
        if field_type in ["checkbox", "radio"]:
            field.is_questionnaire = True
        
        return field
    
    def _determine_field_type(self, label: str, lines: List[str], current_index: int) -> str:
        """Determine field type based on label and context"""
        label_lower = label.lower()
        
        # Date
        date_keywords = ['date', 'birth', 'expir', 'issue', 'valid']
        if any(keyword in label_lower for keyword in date_keywords):
            return "date"
        
        # Number
        number_keywords = ['number', 'ssn', 'ein', 'a-number', 'alien', 'receipt', 'case']
        if any(keyword in label_lower for keyword in number_keywords):
            return "number"
        
        # Signature
        if 'signature' in label_lower:
            return "signature"
        
        # Questions
        question_starters = ['are you', 'have you', 'do you', 'is ', 'was ', 'will ', 'can you', 
                           'did you', 'were you', 'has ', 'does ', 'would ', 'should ', 'could ']
        if any(label_lower.startswith(starter) for starter in question_starters):
            return "checkbox"
        
        # Check next lines
        if current_index + 1 < len(lines):
            next_line = lines[current_index + 1].strip().lower()
            if re.search(r'^\s*(yes|no)\s*$', next_line) or ('yes' in next_line and 'no' in next_line):
                return "checkbox"
        
        # Email/Phone
        if 'email' in label_lower or 'e-mail' in label_lower:
            return "email"
        
        if any(word in label_lower for word in ['phone', 'telephone', 'mobile', 'cell']):
            return "phone"
        
        return "text"
    
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
                
                # Extract item number
                item_match = re.search(r'(\d+)([a-z])?', clean_name)
                item_number = ""
                if item_match:
                    item_number = item_match.group(1)
                    if item_match.group(2):
                        item_number += f".{item_match.group(2)}"
                
                # Determine type
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
                    name=clean_name[:50],
                    label=label,
                    type=field_type,
                    page=page_num,
                    part=part,
                    part_number=part_number,
                    part_title=part_title,
                    item_number=item_number,
                    raw_field_name=field_name,
                    extraction_method="widget",
                    extraction_confidence=0.9,
                    extraction_iteration=self.iteration
                )
                
                if field_type in ["checkbox", "radio"]:
                    field.is_questionnaire = True
                
                fields.append(field)
                
        except Exception as e:
            self.log(f"Widget extraction error: {str(e)}", "warning")
        
        return fields
    
    def _generate_label_from_name(self, name: str) -> str:
        """Generate human-readable label from field name"""
        label = re.sub(r'(field|text|check|box|button)\d*', '', name, flags=re.IGNORECASE)
        label = re.sub(r'([a-z])([A-Z])', r'\1 \2', label)
        label = label.replace('_', ' ').replace('-', ' ')
        
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
        
        return ' '.join(word.capitalize() for word in label.split() if word)
    
    def _merge_fields(self, text_fields: List[ExtractedField], 
                     widget_fields: List[ExtractedField]) -> List[ExtractedField]:
        """Merge fields from different sources"""
        merged = []
        seen_items = set()
        
        # Text fields first (better labels)
        for field in text_fields:
            if field.item_number:
                seen_items.add(field.item_number)
            merged.append(field)
        
        # Widget fields not already found
        for field in widget_fields:
            if field.item_number and field.item_number not in seen_items:
                merged.append(field)
            elif not field.item_number:
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
                if parts[0].startswith('F'):
                    main_num = 900 + int(parts[0][1:])
                elif parts[0].startswith('CB'):
                    main_num = 800 + int(parts[0][2:])
                else:
                    main_num = 999
            
            if len(parts) > 1:
                sub_letter = parts[1]
            
            return (main_num, sub_letter, f.item_number)
        
        merged.sort(key=sort_key)
        
        return merged

# Enhanced Validation Agent with feedback generation
class ValidationAgent(Agent):
    """Enhanced validation with feedback generation"""
    
    def __init__(self):
        super().__init__("Validation Agent", "Field Validation & Feedback")
        
        self.expected_structures = {
            "I-539": {
                "parts": 8,
                "min_fields": 100,
                "required_parts": ["Part 1", "Part 2", "Part 3", "Part 4", "Part 5", "Part 6", "Part 7", "Part 8"],
                "min_fields_per_part": {
                    "Part 1": 15,  # Personal info
                    "Part 2": 20,  # Application type
                    "Part 3": 30,  # Processing info
                    "Part 4": 10,  # Additional info
                    "Part 5": 5,   # Applicant statement
                    "Part 6": 15,  # Contact info
                    "Part 7": 5,   # Signature
                    "Part 8": 5    # Preparer
                }
            },
            "I-129": {
                "parts": 7,
                "min_fields": 80,
                "required_parts": ["Part 1", "Part 2", "Part 3", "Part 4", "Part 5", "Part 6", "Part 7"]
            },
            "I-485": {
                "parts": 14,
                "min_fields": 150,
                "required_parts": [f"Part {i}" for i in range(1, 15)]
            }
        }
    
    def execute(self, form_structure: FormStructure, generate_feedback: bool = True) -> Tuple[FormStructure, Optional[ValidationFeedback]]:
        """Validate and generate feedback for extractor"""
        self.status = "active"
        self.iteration += 1
        self.log(f"Validating {form_structure.form_number} (Iteration {self.iteration})...", "info")
        
        feedback = ValidationFeedback() if generate_feedback else None
        
        try:
            # Get expected structure
            expected = self.expected_structures.get(form_structure.form_number, {})
            
            # 1. Check for missing parts
            if expected and "required_parts" in expected:
                missing_parts = self._check_missing_parts(form_structure, expected, feedback)
            
            # 2. Check part completeness
            if expected and "min_fields_per_part" in expected:
                incomplete_parts = self._check_incomplete_parts(form_structure, expected, feedback)
            
            # 3. Validate individual fields
            field_issues = self._validate_all_fields(form_structure, feedback)
            
            # 4. Check overall completeness
            total_issues = self._check_overall_completeness(form_structure, expected, feedback)
            
            # Calculate validation score
            form_structure.validated_fields = sum(
                1 for fields in form_structure.parts.values() 
                for f in fields if f.is_validated
            )
            
            if form_structure.total_fields > 0:
                base_score = form_structure.validated_fields / form_structure.total_fields
                penalty = min(0.3, total_issues * 0.02)  # Max 30% penalty
                form_structure.validation_score = max(0, base_score - penalty)
            else:
                form_structure.validation_score = 0.0
            
            # Determine if retry needed
            if feedback:
                if missing_parts or (incomplete_parts and form_structure.extraction_iterations < 3):
                    feedback.needs_retry = True
                    feedback.severity = "error" if missing_parts else "warning"
                    
                    # Add suggestions
                    if missing_parts:
                        feedback.suggestions.append("Focus on finding missing parts by searching all pages")
                    if incomplete_parts:
                        feedback.suggestions.append("Use more aggressive extraction patterns for incomplete parts")
                    
                    self.log(f"Validation found issues requiring retry", "warning")
            
            # Summary
            self.log("=== Validation Summary ===", "info")
            self.log(f"Parts found: {len(form_structure.parts)}/{expected.get('parts', '?')}", "info")
            self.log(f"Total fields: {form_structure.total_fields}/{expected.get('min_fields', '?')}", "info")
            self.log(f"Validation score: {form_structure.validation_score:.0%}", "info")
            
            if feedback and feedback.needs_retry:
                self.log(f"Recommending retry with {len(feedback.suggestions)} suggestions", "feedback")
            
            form_structure.is_validated = True
            form_structure.add_agent_log(self.name, 
                f"Validation complete. Score: {form_structure.validation_score:.0%}")
            
            self.status = "completed"
            return form_structure, feedback
            
        except Exception as e:
            self.log(f"Validation failed: {str(e)}", "error")
            self.status = "error"
            return form_structure, feedback
    
    def _check_missing_parts(self, form_structure: FormStructure, expected: Dict, 
                           feedback: Optional[ValidationFeedback]) -> List[Dict]:
        """Check for missing parts"""
        missing_parts = []
        
        for required_part in expected.get("required_parts", []):
            if required_part not in form_structure.parts:
                part_num = int(re.search(r'\d+', required_part).group())
                missing_parts.append({
                    "number": part_num,
                    "name": required_part,
                    "expected_fields": expected.get("min_fields_per_part", {}).get(required_part, 10)
                })
                
                self.log(f"❌ Missing: {required_part}", "error")
                form_structure.validation_issues.append(f"Missing {required_part}")
        
        if feedback and missing_parts:
            feedback.missing_parts = missing_parts
        
        return missing_parts
    
    def _check_incomplete_parts(self, form_structure: FormStructure, expected: Dict,
                              feedback: Optional[ValidationFeedback]) -> List[Dict]:
        """Check for incomplete parts"""
        incomplete_parts = []
        min_fields_per_part = expected.get("min_fields_per_part", {})
        
        for part_name, fields in form_structure.parts.items():
            if part_name in min_fields_per_part:
                expected_fields = min_fields_per_part[part_name]
                actual_fields = len(fields)
                
                if actual_fields < expected_fields * 0.6:  # Less than 60% of expected
                    incomplete_parts.append({
                        "name": part_name,
                        "current_fields": actual_fields,
                        "expected_fields": expected_fields
                    })
                    
                    self.log(f"⚠️ {part_name}: Only {actual_fields}/{expected_fields} fields", "warning")
                    form_structure.validation_issues.append(
                        f"{part_name} incomplete: {actual_fields}/{expected_fields} fields"
                    )
        
        if feedback and incomplete_parts:
            feedback.incomplete_parts = incomplete_parts
        
        return incomplete_parts
    
    def _validate_all_fields(self, form_structure: FormStructure, 
                           feedback: Optional[ValidationFeedback]) -> List[Dict]:
        """Validate individual fields"""
        field_issues = []
        
        for part_name, fields in form_structure.parts.items():
            # Check for duplicates
            item_counts = defaultdict(int)
            for field in fields:
                if field.item_number:
                    item_counts[field.item_number] += 1
                
                # Validate field
                issues = self._validate_field(field)
                if issues:
                    field_issues.append({
                        "part": part_name,
                        "field": field.item_number or field.name,
                        "issues": issues
                    })
                
                field.is_validated = True
                field.validation_confidence = self._calculate_field_confidence(field)
            
            # Report duplicates
            duplicates = {item: count for item, count in item_counts.items() if count > 1}
            if duplicates:
                self.log(f"⚠️ {part_name}: Duplicate items: {duplicates}", "warning")
        
        if feedback and field_issues:
            feedback.field_issues = field_issues
        
        return field_issues
    
    def _check_overall_completeness(self, form_structure: FormStructure, expected: Dict,
                                  feedback: Optional[ValidationFeedback]) -> int:
        """Check overall form completeness"""
        issues = 0
        
        # Check total fields
        min_fields = expected.get("min_fields", 50)
        if form_structure.total_fields < min_fields:
            self.log(f"⚠️ Total fields ({form_structure.total_fields}) below expected ({min_fields})", "warning")
            issues += 1
            
            if feedback:
                feedback.suggestions.append(f"Form should have at least {min_fields} fields total")
        
        # Check for required field types
        has_signature = any(f.type == "signature" for fields in form_structure.parts.values() for f in fields)
        has_dates = any(f.type == "date" for fields in form_structure.parts.values() for f in fields)
        has_checkboxes = any(f.type == "checkbox" for fields in form_structure.parts.values() for f in fields)
        
        if not has_signature:
            self.log("⚠️ No signature fields found", "warning")
            issues += 1
        
        if not has_dates:
            self.log("⚠️ No date fields found", "warning")
            issues += 1
        
        if not has_checkboxes:
            self.log("⚠️ No checkbox fields found", "warning")
            issues += 1
        
        return issues
    
    def _validate_field(self, field: ExtractedField) -> List[str]:
        """Validate individual field"""
        issues = []
        
        if not field.label:
            issues.append("No label")
        
        if not field.type:
            issues.append("No type")
        
        if len(field.label) > 200:
            issues.append("Unusually long label")
        
        return issues
    
    def _calculate_field_confidence(self, field: ExtractedField) -> float:
        """Calculate confidence score for a field"""
        confidence = 0.5
        
        if field.item_number:
            confidence += 0.3
        
        if field.type in ["text", "checkbox", "date", "signature"]:
            confidence += 0.1
        
        if 3 < len(field.label) < 100:
            confidence += 0.1
        
        return min(confidence, 1.0)

# Keep the AIMappingAgent from before (same implementation)
class AIMappingAgent(Agent):
    """Intelligent field mapping using AI and patterns"""
    
    def __init__(self):
        super().__init__("AI Mapping Agent", "Intelligent Field Mapping")
        self.client = get_openai_client()
        
        # Universal mapping patterns (same as before)
        self.mapping_patterns = {
            # Name Fields
            "family name": "beneficiary.PersonalInfo.beneficiaryLastName",
            "last name": "beneficiary.PersonalInfo.beneficiaryLastName",
            "given name": "beneficiary.PersonalInfo.beneficiaryFirstName",
            "first name": "beneficiary.PersonalInfo.beneficiaryFirstName",
            "middle name": "beneficiary.PersonalInfo.beneficiaryMiddleName",
            # ... (rest of patterns from original)
        }
    
    def execute(self, form_structure: FormStructure) -> FormStructure:
        """Map fields using patterns and AI"""
        self.status = "active"
        self.iteration += 1
        self.log(f"Starting intelligent field mapping (Iteration {self.iteration})...")
        
        try:
            total_mapped = 0
            
            for part_name, fields in form_structure.parts.items():
                self.log(f"Mapping {part_name}...")
                
                text_fields = [f for f in fields if f.type in ["text", "number", "date", "email", "phone"] 
                             and not f.db_path and not f.is_questionnaire]
                
                if text_fields:
                    # Pattern matching
                    for field in text_fields:
                        # Try exact item number match
                        if field.item_number and field.item_number in self.mapping_patterns:
                            field.db_path = self.mapping_patterns[field.item_number]
                            field.extraction_confidence = 0.95
                            total_mapped += 1
                            continue
                        
                        # Try label matching
                        label_lower = field.label.lower()
                        best_match = None
                        best_score = 0
                        
                        for pattern, db_path in self.mapping_patterns.items():
                            if len(pattern) <= 2:
                                continue
                            
                            score = self._calculate_match_score(label_lower, pattern.lower())
                            
                            if score > best_score and score > 0.7:
                                best_match = db_path
                                best_score = score
                        
                        if best_match:
                            field.db_path = best_match
                            field.extraction_confidence = best_score
                            total_mapped += 1
                    
                    # AI mapping for remaining
                    if self.client:
                        unmapped = [f for f in text_fields if not f.db_path]
                        if unmapped:
                            ai_mapped = self._ai_batch_mapping(unmapped, form_structure, part_name)
                            total_mapped += ai_mapped
            
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
    
    def _calculate_match_score(self, label: str, pattern: str) -> float:
        """Calculate match score"""
        if label == pattern:
            return 1.0
        
        if pattern in label:
            return 0.9
        
        pattern_words = pattern.split()
        label_words = label.split()
        
        if all(word in label_words for word in pattern_words):
            return 0.85
        
        matching_words = sum(1 for word in pattern_words if word in label)
        if matching_words > 0:
            return 0.6 * (matching_words / len(pattern_words))
        
        return 0.0
    
    def _ai_batch_mapping(self, fields: List[ExtractedField], form_structure: FormStructure, 
                         part_name: str) -> int:
        """AI mapping (simplified for space)"""
        # Similar to original implementation
        return 0

# Coordinator Agent - New!
class CoordinatorAgent(Agent):
    """Coordinates collaboration between agents"""
    
    def __init__(self):
        super().__init__("Coordinator", "Agent Orchestration")
        self.max_iterations = 3
        
    def execute(self, pdf_file, use_ai: bool = True, auto_validate: bool = True, 
               auto_map: bool = True) -> Optional[FormStructure]:
        """Orchestrate agent collaboration with feedback loops"""
        self.status = "active"
        self.log("Starting multi-agent collaboration...", "info")
        
        # Initialize agents
        research_agent = ResearchAgent()
        validation_agent = ValidationAgent()
        mapping_agent = AIMappingAgent() if auto_map else None
        
        form_structure = None
        iteration = 0
        
        # Initial extraction
        self.log("📊 Phase 1: Initial Extraction", "info")
        form_structure = research_agent.execute(pdf_file, use_ai)
        
        if not form_structure:
            self.log("Initial extraction failed", "error")
            return None
        
        # Validation and feedback loop
        while iteration < self.max_iterations and auto_validate:
            iteration += 1
            self.log(f"📊 Phase 2: Validation & Feedback Loop (Iteration {iteration})", "info")
            
            # Validate
            form_structure, feedback = validation_agent.execute(form_structure, generate_feedback=True)
            
            # Check if retry needed
            if feedback and feedback.needs_retry and iteration < self.max_iterations:
                self.log(f"Validation feedback requires re-extraction", "feedback")
                
                # Display feedback
                with st.expander(f"🔄 Iteration {iteration} Feedback", expanded=True):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if feedback.missing_parts:
                            st.warning(f"Missing {len(feedback.missing_parts)} parts")
                            for part in feedback.missing_parts[:3]:
                                st.caption(f"- {part['name']}")
                    
                    with col2:
                        if feedback.incomplete_parts:
                            st.info(f"Incomplete {len(feedback.incomplete_parts)} parts")
                            for part in feedback.incomplete_parts[:3]:
                                st.caption(f"- {part['name']}: {part['current_fields']}/{part['expected_fields']} fields")
                
                # Re-extract with feedback
                form_structure = research_agent.execute(
                    None,  # No file needed, already loaded
                    use_ai,
                    form_structure,
                    feedback
                )
                
                # Let research agent adjust strategy
                research_agent.handle_feedback(feedback)
            else:
                # No retry needed
                break
        
        # Mapping phase
        if auto_map and mapping_agent and form_structure:
            self.log("📊 Phase 3: Intelligent Field Mapping", "info")
            form_structure = mapping_agent.execute(form_structure)
        
        # Final statistics
        if form_structure:
            self.log("=== Final Results ===", "success")
            self.log(f"Total iterations: {iteration}", "info")
            self.log(f"Parts found: {len(form_structure.parts)}", "info") 
            self.log(f"Fields extracted: {form_structure.total_fields}", "info")
            self.log(f"Fields validated: {form_structure.validated_fields}", "info")
            self.log(f"Fields mapped: {form_structure.mapped_fields}", "info")
            self.log(f"Validation score: {form_structure.validation_score:.0%}", "info")
        
        self.status = "completed"
        return form_structure

# Field Display and Export functions (same as before)
def render_field_card(field: ExtractedField, idx: int, part_name: str):
    """Render field card with all details"""
    # Same implementation as before
    status_class = "mapped" if field.db_path else ("questionnaire" if field.is_questionnaire else "unmapped")
    status_text = "✅ Mapped" if field.db_path else ("📋 Questionnaire" if field.is_questionnaire else "❌ Not Mapped")
    
    if field.manually_assigned:
        status_text += " (Manual)"
    
    if field.extraction_iteration > 1:
        status_text += f" (Iter {field.extraction_iteration})"
    
    st.markdown(f'<div class="field-card {status_class}">', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([3, 4, 2])
    
    with col1:
        if field.item_number:
            st.markdown(f'<span class="item-number">{field.item_number}</span>{field.label}', 
                       unsafe_allow_html=True)
        else:
            st.markdown(f'**{field.label}**')
        
        # Type badge
        st.markdown(f'<span class="field-type-badge type-{field.type}">{field.type}</span>', 
                   unsafe_allow_html=True)
    
    with col2:
        if field.type in ["text", "number", "date"] and not field.is_questionnaire:
            current = field.db_path if field.db_path else "-- Select Database Field --"
            options = ["-- Select Database Field --", "📋 Move to Questionnaire"]
            
            for obj, categories in UNIVERSAL_DB_STRUCTURE.items():
                options.append(f"═══ {obj.upper()} ═══")
                for cat, fields_list in categories.items():
                    for field_name in fields_list:
                        path = f"{obj}.{cat}.{field_name}"
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
        if field.extraction_confidence > 0:
            st.caption(f"Confidence: {field.extraction_confidence:.0%}")
    
    st.markdown('</div>', unsafe_allow_html=True)

def generate_typescript(form_structure: FormStructure) -> str:
    """Generate TypeScript export"""
    # Same implementation as before
    form_name = form_structure.form_number.replace('-', '')
    
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
    
    for part_name, fields in form_structure.parts.items():
        for field in fields:
            if field.db_path:
                section = None
                if field.db_path.startswith('beneficiary.'):
                    section = 'beneficiaryData'
                elif field.db_path.startswith('petitioner.'):
                    section = 'beneficiaryData'
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
                sections['questionnaireData'][field.field_id] = f"{field.name}:{field.type}"
    
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
        quest_fields = [f for f in fields if f.is_questionnaire]
        
        if quest_fields:
            part_num = quest_fields[0].part_number
            controls.append({
                "name": f"{part_num}_title",
                "label": part_name,
                "type": "title",
                "validators": {},
                "style": {"col": "12"}
            })
            
            for field in quest_fields:
                label = field.label
                if field.item_number:
                    label = f"{field.item_number}. {label}"
                
                control = {
                    "name": field.name,
                    "label": label,
                    "type": field.type if field.type != "checkbox" else "colorSwitch",
                    "validators": {"required": False},
                    "style": {"col": "7" if field.type == "text" else "12"}
                }
                
                controls.append(control)
    
    return json.dumps({"controls": controls}, indent=2)

# Main Application
def main():
    st.markdown('<div class="main-header"><h1>🤖 Smart USCIS Form Reader</h1><p>Collaborative Multi-Agent System with Feedback Loops</p></div>', 
               unsafe_allow_html=True)
    
    # Initialize session state
    if 'form_structure' not in st.session_state:
        st.session_state.form_structure = None
    if 'agents' not in st.session_state:
        st.session_state.agents = {}
    
    # Check OpenAI
    openai_client = get_openai_client()
    openai_available = openai_client is not None
    
    # Sidebar
    with st.sidebar:
        st.markdown("## ⚙️ Configuration")
        
        if not OPENAI_AVAILABLE:
            st.error("❌ OpenAI library not installed")
        elif openai_available:
            st.success("✅ OpenAI API configured")
        else:
            st.warning("⚠️ OpenAI API Key not configured")
            
            manual_key = st.text_input("Enter OpenAI API Key", type="password", placeholder="sk-...")
            
            if st.button("Test API Key"):
                if manual_key and manual_key.startswith('sk-'):
                    st.session_state['openai_api_key'] = manual_key
                    st.rerun()
        
        st.markdown("### 🤖 Agent Settings")
        use_ai = st.checkbox("Use AI Enhancement", value=openai_available, disabled=not openai_available)
        auto_validate = st.checkbox("Auto-Validate with Feedback", value=True)
        auto_map = st.checkbox("Auto-Map with AI", value=openai_available, disabled=not openai_available)
        max_iterations = st.slider("Max Feedback Iterations", 1, 5, 3)
        
        # Form info
        if st.session_state.form_structure:
            form = st.session_state.form_structure
            st.markdown("### 📄 Current Form")
            st.info(f"{form.form_number}: {form.form_title}")
            
            st.markdown("### 📊 Statistics")
            st.metric("Extraction Iterations", form.extraction_iterations)
            st.metric("Total Fields", form.total_fields)
            st.metric("Validated", f"{form.validated_fields}/{form.total_fields}")
            st.metric("Mapped", form.mapped_fields)
            
            if form.is_validated:
                st.metric("Validation Score", f"{form.validation_score:.0%}")
    
    # Main tabs
    tabs = st.tabs(["📤 Upload & Process", "🎯 Field Mapping", "📥 Export", "📊 Agent Logs"])
    
    with tabs[0]:
        st.markdown("## Upload USCIS Form")
        
        uploaded_file = st.file_uploader(
            "Choose a USCIS PDF form",
            type=['pdf'],
            help="Upload any USCIS form (I-539, I-129, I-485, etc.)"
        )
        
        if uploaded_file:
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.success(f"✅ {uploaded_file.name} ready")
            
            with col2:
                if st.button("🚀 Process", type="primary", use_container_width=True):
                    # Create status container
                    st.session_state.agent_status_container = st.container()
                    
                    # Use coordinator for orchestration
                    coordinator = CoordinatorAgent()
                    
                    with st.spinner("Processing with collaborative agents..."):
                        form_structure = coordinator.execute(
                            uploaded_file, use_ai, auto_validate, auto_map
                        )
                        
                        if form_structure:
                            st.session_state.form_structure = form_structure
                            st.success(f"✅ Processed {form_structure.form_number}")
                            
                            # Show summary
                            with st.expander("📊 Processing Summary", expanded=True):
                                col1, col2, col3, col4 = st.columns(4)
                                
                                with col1:
                                    st.metric("Iterations", form_structure.extraction_iterations)
                                with col2:
                                    st.metric("Parts Found", len(form_structure.parts))
                                with col3:
                                    st.metric("Total Fields", form_structure.total_fields) 
                                with col4:
                                    st.metric("Score", f"{form_structure.validation_score:.0%}")
                                
                                # Part breakdown
                                st.markdown("### Parts Extracted:")
                                for part_name, fields in form_structure.parts.items():
                                    st.markdown(f"**{part_name}**: {len(fields)} fields")
                                    
                                # Validation issues
                                if form_structure.validation_issues:
                                    st.markdown("### ⚠️ Validation Issues:")
                                    for issue in form_structure.validation_issues[:5]:
                                        st.warning(issue)
    
    with tabs[1]:
        form_structure = st.session_state.get('form_structure')
        if form_structure and form_structure.parts:
            st.markdown("## 🎯 Field Mapping")
            
            selected_part = st.selectbox(
                "Select Part",
                options=list(form_structure.parts.keys()),
                index=0
            )
            
            if selected_part:
                fields = form_structure.parts[selected_part]
                
                st.markdown(f'''
                <div class="part-header">
                    <h3>{selected_part}</h3>
                    <p>{len(fields)} fields</p>
                </div>
                ''', unsafe_allow_html=True)
                
                # Stats
                st.markdown('<div class="extraction-stats">', unsafe_allow_html=True)
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    text_fields = sum(1 for f in fields if f.type in ["text", "number", "date"])
                    st.metric("Text Fields", text_fields)
                with col2:
                    checkbox_fields = sum(1 for f in fields if f.type == "checkbox")
                    st.metric("Checkboxes", checkbox_fields)
                with col3:
                    mapped = sum(1 for f in fields if f.db_path)
                    st.metric("Mapped", mapped)
                with col4:
                    iterations = max((f.extraction_iteration for f in fields), default=1)
                    st.metric("Max Iterations", iterations)
                
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
    
    with tabs[3]:
        form_structure = st.session_state.get('form_structure')
        if form_structure and form_structure.agent_logs:
            st.markdown("## 📊 Agent Activity Logs")
            
            for agent_name, logs in form_structure.agent_logs.items():
                with st.expander(f"🤖 {agent_name}", expanded=True):
                    for log in logs:
                        st.caption(log)
                    
            # Feedback history
            if hasattr(form_structure, 'agent_feedback') and form_structure.agent_feedback:
                st.markdown("### 🔄 Feedback History")
                for i, feedback in enumerate(form_structure.agent_feedback):
                    with st.expander(f"Iteration {i+1} Feedback"):
                        st.json(feedback.to_dict())
        else:
            st.info("No agent logs available yet")

if __name__ == "__main__":
    main()
