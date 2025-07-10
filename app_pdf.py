#!/usr/bin/env python3
"""
Enhanced Smart USCIS Form Reader with Agent Feedback Loops
Now with proper sub-item extraction (1a, 1b, 1c) and JSON structure mapping
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
    page_title="Smart USCIS Form Reader - Enhanced JSON Mapping",
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
    .add-field-button {
        background: #4CAF50;
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 5px;
        border: none;
        cursor: pointer;
        margin: 1rem 0;
    }
    .add-field-button:hover {
        background: #45a049;
    }
    .edit-mode {
        border: 2px dashed #2196F3;
        background: #e3f2fd;
    }
    .sub-item {
        margin-left: 2rem;
        font-size: 0.95em;
    }
    .item-group {
        background: #f5f5f5;
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Load JSON structures
def load_json_structures():
    """Load the database structures from JSON"""
    try:
        # Default structures if file not found
        default_structures = {
            "AttorneyObject": {
                "attorneyInfo": {
                    "firstName": "",
                    "lastName": "",
                    "workPhone": "",
                    "emailAddress": "",
                    "stateBarNumber": "",
                    "addressId": ""
                },
                "address": {
                    "addressStreet": "",
                    "addressCity": "",
                    "addressState": "",
                    "addressZip": "",
                    "addressCountry": ""
                }
            },
            "BeneficiaryObject": {
                "Beneficiary": {
                    "beneficiaryFirstName": "",
                    "beneficiaryLastName": "",
                    "beneficiaryMiddleName": "",
                    "beneficiaryDateOfBirth": "",
                    "beneficiaryGender": "",
                    "beneficiarySsn": "",
                    "alienNumber": "",
                    "beneficiaryCountryOfBirth": "",
                    "beneficiaryCitizenOfCountry": [],
                    "maritalStatus": "",
                    "beneficiaryPrimaryEmailAddress": "",
                    "beneficiaryCellNumber": ""
                },
                "HomeAddress": {
                    "addressStreet": "",
                    "addressCity": "",
                    "addressState": "",
                    "addressZip": "",
                    "addressCountry": ""
                },
                "PassportDetails": [],
                "VisaDetails": [],
                "I94Details": []
            },
            "CaseObject": {
                "caseType": "",
                "caseSubType": "",
                "premiumProcessing": False,
                "uscisReceiptNumber": "",
                "caseStatus": "",
                "beneficiaryId": "",
                "serviceCenter": ""
            },
            "CustomerObject": {
                "customer_name": "",
                "customer_tax_id": "",
                "customer_type_of_business": "",
                "e_verified": False,
                "e_verify_number": "",
                "address_street": "",
                "address_city": "",
                "address_state": "",
                "address_zip": ""
            },
            "PetitionerObject": {
                "Beneficiary": {
                    "beneficiaryFirstName": "",
                    "beneficiaryLastName": "",
                    "beneficiaryMiddleName": "",
                    "beneficiarySsn": "",
                    "beneficiaryDateOfBirth": ""
                }
            }
        }
        
        # Try to load from session state or file
        if 'json_structures' in st.session_state:
            return st.session_state['json_structures']
        
        # You can load from file here if needed
        # with open('empty_json_structures.json', 'r') as f:
        #     return json.load(f)
        
        return default_structures
        
    except Exception as e:
        return default_structures

# Enhanced field mapping structure
ENHANCED_DB_STRUCTURE = {
    "beneficiary": {
        "PersonalInfo": {
            "beneficiaryFirstName": ["given name", "first name", "1b"],
            "beneficiaryLastName": ["family name", "last name", "surname", "1a"],
            "beneficiaryMiddleName": ["middle name", "1c"],
            "beneficiaryDateOfBirth": ["date of birth", "birth date", "dob", "2"],
            "beneficiaryGender": ["gender", "sex", "3"],
            "beneficiarySsn": ["social security", "ssn", "4"],
            "alienNumber": ["alien number", "a-number", "a number", "5"],
            "beneficiaryCountryOfBirth": ["country of birth", "birth country", "6"],
            "beneficiaryCitizenOfCountry": ["citizenship", "citizen of", "nationality", "7"],
            "maritalStatus": ["marital status", "married", "single", "8"]
        },
        "ContactInfo": {
            "beneficiaryPrimaryEmailAddress": ["email", "email address", "e-mail"],
            "beneficiaryCellNumber": ["mobile", "cell", "mobile phone", "cell phone"],
            "beneficiaryWorkNumber": ["work phone", "office phone", "business phone"]
        },
        "Address": {
            "addressStreet": ["street address", "street", "address line 1"],
            "addressCity": ["city", "town"],
            "addressState": ["state", "province"],
            "addressZip": ["zip", "zip code", "postal code"],
            "addressCountry": ["country"]
        }
    },
    "petitioner": {
        "PersonalInfo": {
            "firstName": ["given name", "first name"],
            "lastName": ["family name", "last name", "surname"],
            "middleName": ["middle name"],
            "ssn": ["social security", "ssn"],
            "ein": ["employer identification", "ein", "fein"]
        }
    },
    "attorney": {
        "Info": {
            "firstName": ["attorney first name", "representative first name"],
            "lastName": ["attorney last name", "representative last name"],
            "stateBarNumber": ["bar number", "state bar"],
            "emailAddress": ["attorney email", "representative email"]
        }
    },
    "case": {
        "ProcessingInfo": {
            "requestedAction": ["requested action", "action requested"],
            "caseType": ["case type", "petition type"],
            "premiumProcessing": ["premium processing", "expedited"]
        }
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
    parent_item: Optional[str] = None  # For sub-items like 1a, 1b, 1c
    
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
    json_path: Optional[str] = None  # Path in JSON structure
    is_questionnaire: bool = False
    manually_assigned: bool = False
    
    # Validation
    is_validated: bool = False
    validation_confidence: float = 0.0
    
    # Edit mode
    is_editable: bool = True
    is_user_added: bool = False
    
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
    
    # JSON mapping
    json_mappings: Dict[str, str] = field(default_factory=dict)
    
    def add_agent_log(self, agent_name: str, message: str):
        if agent_name not in self.agent_logs:
            self.agent_logs[agent_name] = []
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.agent_logs[agent_name].append(f"{timestamp} - {message}")
    
    def reorder_parts(self):
        """Reorder parts in natural order (Part 1, Part 2, ..., Part 10, etc.)"""
        def natural_sort_key(part_name):
            match = re.search(r'Part\s+(\d+)', part_name, re.IGNORECASE)
            if match:
                return int(match.group(1))
            return 999  # Put non-standard parts at end
        
        # Create new OrderedDict with natural ordering
        sorted_parts = sorted(self.parts.items(), key=lambda x: natural_sort_key(x[0]))
        self.parts = OrderedDict(sorted_parts)

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
        if feedback and feedback.suggestions:
            # Check for part ordering feedback
            for suggestion in feedback.suggestions:
                if "part numbering" in suggestion.lower() or "sequential order" in suggestion.lower():
                    self.log("Received feedback about part ordering - will ensure proper sequencing", "feedback")
                    # This will be handled by reorder_parts() after extraction
    
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

# Enhanced Research Agent with sub-item extraction
class ResearchAgent(Agent):
    """Enhanced extraction with proper sub-item handling"""
    
    def __init__(self):
        super().__init__("Research Agent", "Intelligent Field Extraction")
        self.client = get_openai_client()
        self.pdf_bytes = None
        self.doc = None
        self.page_texts = []
        self.sub_item_patterns = self._compile_sub_item_patterns()
    
    def _compile_sub_item_patterns(self):
        """Compile regex patterns for sub-item extraction"""
        return {
            'main_with_subs': re.compile(r'^(\d+)\.\s+(.+?)(?:\s*\(.*\))?$', re.IGNORECASE),
            'sub_item': re.compile(r'^(\d+)([a-z])\.\s+(.+?)(?:\s*\(.*\))?$', re.IGNORECASE),
            'indented_sub': re.compile(r'^\s{2,}([a-z])\.\s+(.+?)(?:\s*\(.*\))?$', re.IGNORECASE),
            'question_with_parts': re.compile(r'^(\d+)\.\s+(.*?):\s*$', re.IGNORECASE),
            'name_fields': re.compile(r'(family|given|middle|first|last)\s*(name)', re.IGNORECASE)
        }
    
    def execute(self, pdf_file=None, use_ai: bool = True, 
                form_structure: Optional[FormStructure] = None,
                feedback: Optional[ValidationFeedback] = None) -> Optional[FormStructure]:
        """Extract with enhanced sub-item detection"""
        self.status = "active"
        self.iteration += 1
        
        # First iteration - full extraction
        if pdf_file is not None:
            self.pdf_bytes = pdf_file.read() if hasattr(pdf_file, 'read') else pdf_file
            if self.doc:  # Close any existing document
                self.doc.close()
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
            # Reopen document if needed
            if not self.doc or not hasattr(self, 'pdf_bytes'):
                self.log("Document not available for feedback processing", "error")
                return form_structure
            
            # Ensure document is open
            try:
                # Test if document is still open
                _ = self.doc.page_count
            except ValueError:
                # Document is closed, reopen it
                self.doc = fitz.open(stream=self.pdf_bytes, filetype="pdf")
                self.page_texts = [page.get_text() for page in self.doc]
                self.log("Reopened document for feedback processing", "info")
            
            self.log(f"Received feedback - attempting targeted extraction", "feedback")
            return self._handle_extraction_feedback(form_structure, feedback, use_ai)
        
        # Regular extraction with enhanced sub-item detection
        form_structure.extraction_iterations = self.iteration
        
        # Execute comprehensive extraction
        self._comprehensive_extraction_with_subitems(form_structure, use_ai)
        
        # Ensure parts are properly ordered
        form_structure.reorder_parts()
        
        # Don't close document here - let it be closed by cleanup method
        
        form_structure.add_agent_log(self.name, f"Iteration {self.iteration}: Extracted {form_structure.total_fields} fields")
        self.log(f"Extraction complete: {form_structure.total_fields} fields found", "success")
        
        self.status = "completed"
        return form_structure
    
    def cleanup(self):
        """Clean up resources"""
        if hasattr(self, 'doc') and self.doc:
            try:
                self.doc.close()
                self.log("Document closed", "info")
            except:
                pass
    
    def _comprehensive_extraction_with_subitems(self, form_structure: FormStructure, use_ai: bool):
        """Enhanced extraction that properly handles sub-items"""
        
        # Step 1: AI analysis if available
        if use_ai and self.client:
            self._ai_guided_extraction_enhanced(form_structure)
        
        # Step 2: Pattern-based extraction with sub-item detection
        self._extract_with_sub_items(form_structure)
        
        # Step 3: Widget extraction
        self._extract_from_all_widgets(form_structure)
        
        # Step 4: Post-process to ensure proper sub-item structure
        self._post_process_sub_items(form_structure)
    
    def _extract_with_sub_items(self, form_structure: FormStructure):
        """Extract fields with proper sub-item handling"""
        # Check if document is available
        if not self.doc or not self.page_texts:
            self.log("Document not available for extraction", "error")
            return
            
        current_part = 1
        current_main_item = None
        
        for page_num, page in enumerate(self.doc):
            if page_num >= len(self.page_texts):
                self.log(f"Page text not available for page {page_num}", "warning")
                continue
                
            page_text = self.page_texts[page_num]
            lines = page_text.split('\n')
            
            # Check for part transitions
            part_match = re.search(r'Part\s+(\d+)', page_text, re.IGNORECASE)
            if part_match:
                current_part = int(part_match.group(1))
            
            part_name = f"Part {current_part}"
            if part_name not in form_structure.parts:
                form_structure.parts[part_name] = []
            
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                if not line:
                    i += 1
                    continue
                
                # Check for main item with potential sub-items
                main_match = self.sub_item_patterns['main_with_subs'].match(line)
                if main_match:
                    item_num = main_match.group(1)
                    label = main_match.group(2)
                    
                    # Check if this is a compound field (like "Your Legal Name")
                    if self._is_compound_field(label, lines, i):
                        current_main_item = item_num
                        
                        # Create main field
                        main_field = ExtractedField(
                            name=f"field_{item_num}",
                            label=label,
                            type="group",
                            page=page_num + 1,
                            part=part_name,
                            part_number=current_part,
                            item_number=item_num,
                            extraction_method="pattern",
                            extraction_iteration=self.iteration
                        )
                        form_structure.parts[part_name].append(main_field)
                        
                        # Extract sub-items
                        sub_items = self._extract_sub_items(lines, i + 1, item_num)
                        for sub_item in sub_items:
                            sub_item.page = page_num + 1
                            sub_item.part = part_name
                            sub_item.part_number = current_part
                            sub_item.parent_item = item_num
                            sub_item.extraction_iteration = self.iteration
                            form_structure.parts[part_name].append(sub_item)
                        
                        # Skip lines we've processed
                        i += len(sub_items) + 1
                        continue
                    else:
                        # Regular field
                        field = ExtractedField(
                            name=f"field_{item_num}",
                            label=label,
                            type=self._determine_field_type(label, lines, i),
                            page=page_num + 1,
                            part=part_name,
                            part_number=current_part,
                            item_number=item_num,
                            extraction_method="pattern",
                            extraction_iteration=self.iteration
                        )
                        form_structure.parts[part_name].append(field)
                
                # Check for sub-item pattern
                sub_match = self.sub_item_patterns['sub_item'].match(line)
                if sub_match and current_main_item:
                    item_num = sub_match.group(1)
                    sub_letter = sub_match.group(2)
                    label = sub_match.group(3)
                    
                    if item_num == current_main_item:
                        field = ExtractedField(
                            name=f"field_{item_num}{sub_letter}",
                            label=label,
                            type=self._determine_field_type(label, lines, i),
                            page=page_num + 1,
                            part=part_name,
                            part_number=current_part,
                            item_number=f"{item_num}{sub_letter}",
                            parent_item=item_num,
                            extraction_method="pattern",
                            extraction_iteration=self.iteration
                        )
                        form_structure.parts[part_name].append(field)
                
                i += 1
            
            # Update total fields
            form_structure.total_fields = sum(len(fields) for fields in form_structure.parts.values())
    
    def _is_compound_field(self, label: str, lines: List[str], current_index: int) -> bool:
        """Check if a field has sub-items"""
        label_lower = label.lower()
        
        # Known compound fields
        compound_keywords = [
            'legal name', 'full name', 'your name', 'mailing address', 
            'physical address', 'contact information', 'passport information'
        ]
        
        if any(keyword in label_lower for keyword in compound_keywords):
            return True
        
        # Check next few lines for sub-items
        for i in range(1, min(5, len(lines) - current_index)):
            next_line = lines[current_index + i].strip()
            if re.match(r'^[a-z]\.\s+', next_line) or re.match(r'^\s{2,}[a-z]\.\s+', next_line):
                return True
        
        return False
    
    def _extract_sub_items(self, lines: List[str], start_index: int, parent_num: str) -> List[ExtractedField]:
        """Extract sub-items for a parent field"""
        sub_items = []
        
        # Common sub-item patterns
        sub_patterns = [
            (re.compile(r'^([a-z])\.\s+(.+?)(?:\s*\(.*\))?$'), 'direct'),
            (re.compile(r'^\s{2,}([a-z])\.\s+(.+?)(?:\s*\(.*\))?$'), 'indented'),
            (re.compile(r'^([a-z])\s*\)\s*(.+?)(?:\s*\(.*\))?$'), 'parentheses'),
        ]
        
        # Also check for implicit sub-items
        name_parts = ['Family Name', 'Given Name', 'Middle Name']
        address_parts = ['Street', 'City', 'State', 'ZIP Code', 'Country']
        
        i = start_index
        sub_letter = 'a'
        
        while i < len(lines) and len(sub_items) < 10:  # Max 10 sub-items
            line = lines[i].strip()
            
            if not line:
                i += 1
                continue
            
            # Check if we've hit a new main item
            if re.match(r'^(\d+)\.\s+', line):
                break
            
            found = False
            
            # Try explicit patterns
            for pattern, pattern_type in sub_patterns:
                match = pattern.match(line)
                if match:
                    sub_letter_found = match.group(1)
                    label = match.group(2)
                    
                    sub_items.append(ExtractedField(
                        name=f"field_{parent_num}{sub_letter_found}",
                        label=label,
                        type=self._determine_field_type(label, lines, i),
                        item_number=f"{parent_num}{sub_letter_found}",
                        parent_item=parent_num,
                        extraction_method="pattern"
                    ))
                    found = True
                    break
            
            # Check for implicit patterns (like name parts)
            if not found:
                for idx, part in enumerate(name_parts):
                    if part.lower() in line.lower():
                        sub_items.append(ExtractedField(
                            name=f"field_{parent_num}{chr(ord('a') + idx)}",
                            label=part,
                            type="text",
                            item_number=f"{parent_num}{chr(ord('a') + idx)}",
                            parent_item=parent_num,
                            extraction_method="pattern"
                        ))
                        found = True
                        break
            
            if found:
                i += 1
            else:
                # If line doesn't match patterns but seems related, might be continuation
                if len(line) > 20 and not line[0].isdigit():
                    i += 1
                else:
                    break
        
        return sub_items
    
    def _post_process_sub_items(self, form_structure: FormStructure):
        """Post-process to ensure proper sub-item structure"""
        for part_name, fields in form_structure.parts.items():
            # Group fields by parent item
            item_groups = defaultdict(list)
            
            for field in fields:
                if field.parent_item:
                    item_groups[field.parent_item].append(field)
                elif field.item_number and not field.item_number[-1].isalpha():
                    # Main item
                    item_groups[field.item_number].append(field)
            
            # Ensure sub-items are properly ordered
            for main_item, group_fields in item_groups.items():
                if len(group_fields) > 1:
                    # Sort sub-items
                    group_fields.sort(key=lambda f: f.item_number if f.item_number else "")
                    
                    # Ensure proper lettering
                    sub_items = [f for f in group_fields if f.parent_item]
                    for idx, field in enumerate(sub_items):
                        expected_letter = chr(ord('a') + idx)
                        if field.item_number and not field.item_number.endswith(expected_letter):
                            # Fix the item number
                            field.item_number = f"{main_item}{expected_letter}"
                            field.name = f"field_{main_item}{expected_letter}"
    
    def _ai_guided_extraction_enhanced(self, form_structure: FormStructure):
        """Enhanced AI extraction with sub-item awareness"""
        if not self.client:
            return
        
        # Check if page texts are available
        if not self.page_texts:
            self.log("Page texts not available for AI extraction", "warning")
            return
        
        try:
            # Limit text to first 5 pages or available pages
            max_pages = min(5, len(self.page_texts))
            full_text = "\n".join(self.page_texts[:max_pages])
            
            prompt = f"""
            Analyze this USCIS {form_structure.form_number} form and extract ALL parts/sections with their fields.
            Pay special attention to sub-items (like 1a, 1b, 1c for compound fields).
            
            Text sample:
            {full_text[:15000]}
            
            IMPORTANT: For compound fields like "Legal Name", extract sub-items as:
            - 1. Your Legal Name
              - 1a. Family Name (Last Name)
              - 1b. Given Name (First Name)  
              - 1c. Middle Name
            
            Return JSON with this exact structure:
            {{
                "Part 1": {{
                    "title": "Information About You",
                    "fields": [
                        {{
                            "item": "1",
                            "label": "Your Legal Name",
                            "type": "group",
                            "sub_items": [
                                {{"item": "1a", "label": "Family Name (Last Name)", "type": "text"}},
                                {{"item": "1b", "label": "Given Name (First Name)", "type": "text"}},
                                {{"item": "1c", "label": "Middle Name", "type": "text"}}
                            ]
                        }},
                        {{"item": "2", "label": "Date of Birth", "type": "date"}},
                        // ... more fields
                    ]
                }}
            }}
            """
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert USCIS form analyzer. Extract all fields with proper sub-item structure."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=4000
            )
            
            response_text = response.choices[0].message.content
            result = json.loads(re.search(r'\{[\s\S]*\}', response_text).group())
            
            # Process AI results
            for part_name, part_info in result.items():
                if part_name not in form_structure.parts:
                    form_structure.parts[part_name] = []
                
                part_number = int(re.search(r'\d+', part_name).group()) if re.search(r'\d+', part_name) else 1
                
                for field_info in part_info.get('fields', []):
                    # Main field
                    main_field = ExtractedField(
                        name=f"field_{field_info['item'].replace('.', '_')}",
                        label=field_info['label'],
                        type=field_info.get('type', 'text'),
                        part=part_name,
                        part_number=part_number,
                        item_number=field_info['item'],
                        extraction_method="ai",
                        extraction_iteration=self.iteration
                    )
                    form_structure.parts[part_name].append(main_field)
                    
                    # Sub-items
                    if 'sub_items' in field_info:
                        for sub_item in field_info['sub_items']:
                            sub_field = ExtractedField(
                                name=f"field_{sub_item['item'].replace('.', '_')}",
                                label=sub_item['label'],
                                type=sub_item.get('type', 'text'),
                                part=part_name,
                                part_number=part_number,
                                item_number=sub_item['item'],
                                parent_item=field_info['item'],
                                extraction_method="ai",
                                extraction_iteration=self.iteration
                            )
                            form_structure.parts[part_name].append(sub_field)
            
            form_structure.total_fields = sum(len(fields) for fields in form_structure.parts.values())
            self.log(f"AI extraction found {form_structure.total_fields} fields with sub-items", "success")
            
        except Exception as e:
            self.log(f"AI extraction error: {str(e)}", "warning")
    
    # Keep all other methods from original implementation
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
        
        # Group type for compound fields
        if self._is_compound_field(label, lines, current_index):
            return "group"
        
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
                        item_number += item_match.group(2)
                
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
    
    def _extract_from_all_widgets(self, form_structure: FormStructure):
        """Extract from all PDF widgets"""
        # Check if document is available
        if not self.doc or not self.page_texts:
            self.log("Document not available for widget extraction", "warning")
            return
            
        current_part = 1
        
        for page_num, page in enumerate(self.doc):
            try:
                # Determine current part from page
                if page_num < len(self.page_texts):
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
                        
            except Exception as e:
                self.log(f"Error extracting widgets from page {page_num}: {str(e)}", "warning")
    
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
        
        # Apply suggestions
        if feedback.suggestions and use_ai and self.client:
            self._apply_ai_suggestions(form_structure, feedback.suggestions)
        
        # Recalculate totals
        form_structure.total_fields = sum(len(fields) for fields in form_structure.parts.values())
        
        # Ensure proper ordering after feedback processing
        form_structure.reorder_parts()
        
        return form_structure
    
    def _search_for_specific_part(self, form_structure: FormStructure, missing_part: Dict):
        """Search for a specific missing part"""
        part_num = missing_part.get('number', 0)
        part_name = missing_part.get('name', f'Part {part_num}')
        
        self.log(f"Targeted search for {part_name}", "info")
        
        # Check if document is available
        if not self.doc or not self.page_texts:
            self.log("Document not available for part search", "warning")
            return
        
        # Search all pages for this part
        found_fields = []
        for page_num, page_text in enumerate(self.page_texts):
            # Enhanced patterns for finding parts
            patterns = [
                rf'Part\s+{part_num}\b',
                rf'PART\s+{part_num}\b',
                rf'Section\s+{part_num}\b',
                rf'{part_name}',
            ]
            
            for pattern in patterns:
                if pattern and re.search(pattern, page_text, re.IGNORECASE):
                    self.log(f"Found {part_name} on page {page_num + 1}", "success")
                    
                    # Ensure page number is valid
                    if page_num >= len(self.doc):
                        self.log(f"Page {page_num} out of range", "warning")
                        continue
                    
                    try:
                        # Extract fields from this section with sub-items
                        page = self.doc[page_num]
                        lines = page_text.split('\n')
                        
                        # Find the part header and extract subsequent fields
                        part_start = None
                        for i, line in enumerate(lines):
                            if re.search(pattern, line, re.IGNORECASE):
                                part_start = i
                                break
                        
                        if part_start is not None:
                            # Extract fields from this part
                            i = part_start + 1
                            while i < len(lines):
                                line = lines[i].strip()
                                
                                # Stop at next part
                                if re.match(r'Part\s+\d+', line, re.IGNORECASE) and not re.search(pattern, line, re.IGNORECASE):
                                    break
                                
                                # Extract fields with sub-items
                                if re.match(r'^(\d+)\.\s+', line):
                                    main_match = self.sub_item_patterns['main_with_subs'].match(line)
                                    if main_match:
                                        item_num = main_match.group(1)
                                        label = main_match.group(2)
                                        
                                        field = ExtractedField(
                                            name=f"field_{item_num}",
                                            label=label,
                                            type=self._determine_field_type(label, lines, i),
                                            page=page_num + 1,
                                            part=part_name,
                                            part_number=part_num,
                                            item_number=item_num,
                                            extraction_method="feedback",
                                            extraction_iteration=self.iteration
                                        )
                                        found_fields.append(field)
                                        
                                        # Check for sub-items
                                        if self._is_compound_field(label, lines, i):
                                            sub_items = self._extract_sub_items(lines, i + 1, item_num)
                                            for sub_item in sub_items:
                                                sub_item.page = page_num + 1
                                                sub_item.part = part_name
                                                sub_item.part_number = part_num
                                                sub_item.extraction_method = "feedback"
                                                sub_item.extraction_iteration = self.iteration
                                                found_fields.append(sub_item)
                                
                                i += 1
                    except Exception as e:
                        self.log(f"Error extracting from page {page_num}: {str(e)}", "warning")
                    
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
        
        # Check if document is available
        if not self.doc or not self.page_texts:
            self.log("Document not available for enhancement", "warning")
            return
        
        # Re-extract with more aggressive patterns
        part_num = int(re.search(r'\d+', part_name).group()) if re.search(r'\d+', part_name) else 1
        
        # Find pages containing this part
        for page_num, page_text in enumerate(self.page_texts):
            if re.search(rf'Part\s+{part_num}\b', page_text, re.IGNORECASE):
                # Ensure page number is valid
                if page_num >= len(self.doc):
                    self.log(f"Page {page_num} out of range", "warning")
                    continue
                    
                # Use more aggressive extraction
                try:
                    page = self.doc[page_num]
                    
                    # Try widget extraction again
                    widget_fields = self._extract_from_widgets(
                        page, page_num + 1, part_name, part_num, ""
                    )
                    
                    # Add new unique fields
                    existing_names = {f.name for f in form_structure.parts[part_name]}
                    added = 0
                    for field in widget_fields:
                        if field.name not in existing_names:
                            form_structure.parts[part_name].append(field)
                            form_structure.total_fields += 1
                            added += 1
                    
                    if added > 0:
                        self.log(f"Enhanced {part_name} with {added} additional widget fields", "success")
                except Exception as e:
                    self.log(f"Error enhancing page {page_num}: {str(e)}", "warning")
    
    def _apply_ai_suggestions(self, form_structure: FormStructure, suggestions: List[str]):
        """Apply AI suggestions for improvement"""
        # Implementation for applying AI suggestions
        pass

# Enhanced JSON Mapping Agent
class JSONMappingAgent(Agent):
    """Enhanced mapping agent using JSON structures"""
    
    def __init__(self):
        super().__init__("JSON Mapping Agent", "JSON Structure Mapping")
        self.client = get_openai_client()
        self.json_structures = load_json_structures()
        self.enhanced_mappings = self._build_enhanced_mappings()
    
    def _build_enhanced_mappings(self) -> Dict[str, List[Tuple[str, str]]]:
        """Build mapping patterns from JSON structures"""
        mappings = defaultdict(list)
        
        # Process each object type
        for obj_type, obj_structure in self.json_structures.items():
            obj_name = obj_type.replace('Object', '').lower()
            
            # Recursive function to extract paths
            def extract_paths(data, prefix=""):
                if isinstance(data, dict):
                    for key, value in data.items():
                        if isinstance(value, dict):
                            extract_paths(value, f"{prefix}.{key}" if prefix else key)
                        else:
                            full_path = f"{prefix}.{key}" if prefix else key
                            # Create variations of the key for matching
                            variations = self._create_key_variations(key)
                            for var in variations:
                                mappings[var.lower()].append((obj_name, full_path))
            
            extract_paths(obj_structure)
        
        # Add specific mappings for common USCIS fields
        specific_mappings = {
            "1a": [("beneficiary", "Beneficiary.beneficiaryLastName")],
            "1b": [("beneficiary", "Beneficiary.beneficiaryFirstName")],
            "1c": [("beneficiary", "Beneficiary.beneficiaryMiddleName")],
            "family name": [("beneficiary", "Beneficiary.beneficiaryLastName")],
            "given name": [("beneficiary", "Beneficiary.beneficiaryFirstName")],
            "middle name": [("beneficiary", "Beneficiary.beneficiaryMiddleName")],
            "date of birth": [("beneficiary", "Beneficiary.beneficiaryDateOfBirth")],
            "a-number": [("beneficiary", "Beneficiary.alienNumber")],
            "alien number": [("beneficiary", "Beneficiary.alienNumber")],
            "ssn": [("beneficiary", "Beneficiary.beneficiarySsn")],
            "social security": [("beneficiary", "Beneficiary.beneficiarySsn")],
            "email": [("beneficiary", "Beneficiary.beneficiaryPrimaryEmailAddress")],
            "phone": [("beneficiary", "Beneficiary.beneficiaryCellNumber")],
            "street": [("beneficiary", "HomeAddress.addressStreet")],
            "city": [("beneficiary", "HomeAddress.addressCity")],
            "state": [("beneficiary", "HomeAddress.addressState")],
            "zip": [("beneficiary", "HomeAddress.addressZip")],
        }
        
        for key, paths in specific_mappings.items():
            mappings[key].extend(paths)
        
        return dict(mappings)
    
    def _create_key_variations(self, key: str) -> List[str]:
        """Create variations of a key for better matching"""
        variations = [key]
        
        # CamelCase to space separated
        spaced = re.sub(r'([A-Z])', r' \1', key).strip()
        variations.append(spaced)
        
        # Remove common prefixes
        prefixes = ['beneficiary', 'attorney', 'customer', 'petitioner']
        for prefix in prefixes:
            if key.lower().startswith(prefix):
                cleaned = key[len(prefix):]
                variations.append(cleaned)
                variations.append(re.sub(r'([A-Z])', r' \1', cleaned).strip())
        
        # Common abbreviations
        abbreviations = {
            'FirstName': ['first name', 'given name', 'fname'],
            'LastName': ['last name', 'family name', 'surname', 'lname'],
            'MiddleName': ['middle name', 'middle', 'mname'],
            'DateOfBirth': ['date of birth', 'birth date', 'dob'],
            'EmailAddress': ['email', 'email address', 'e-mail'],
            'PhoneNumber': ['phone', 'telephone', 'phone number'],
            'StreetAddress': ['street', 'address', 'street address'],
        }
        
        for full, abbrs in abbreviations.items():
            if full in key:
                variations.extend(abbrs)
        
        return variations
    
    def execute(self, form_structure: FormStructure) -> FormStructure:
        """Map fields to JSON structure"""
        self.status = "active"
        self.iteration += 1
        self.log(f"Starting JSON structure mapping (Iteration {self.iteration})...")
        
        try:
            total_mapped = 0
            
            for part_name, fields in form_structure.parts.items():
                self.log(f"Mapping {part_name}...")
                
                # Process each field
                for field in fields:
                    if field.is_questionnaire or field.type == "group":
                        continue
                    
                    # Skip if already mapped
                    if field.json_path:
                        continue
                    
                    # Try different mapping strategies
                    mapped = False
                    
                    # 1. Try item number mapping (e.g., 1a, 1b, 1c)
                    if field.item_number:
                        if field.item_number.lower() in self.enhanced_mappings:
                            candidates = self.enhanced_mappings[field.item_number.lower()]
                            if candidates:
                                obj_name, path = candidates[0]  # Take first match
                                field.json_path = f"{obj_name}.{path}"
                                field.db_path = self._convert_to_db_path(obj_name, path)
                                mapped = True
                                total_mapped += 1
                    
                    # 2. Try label matching
                    if not mapped and field.label:
                        label_lower = field.label.lower()
                        
                        # Direct match
                        if label_lower in self.enhanced_mappings:
                            candidates = self.enhanced_mappings[label_lower]
                            if candidates:
                                obj_name, path = candidates[0]
                                field.json_path = f"{obj_name}.{path}"
                                field.db_path = self._convert_to_db_path(obj_name, path)
                                mapped = True
                                total_mapped += 1
                        else:
                            # Fuzzy matching
                            best_match = self._find_best_match(field.label)
                            if best_match:
                                obj_name, path = best_match
                                field.json_path = f"{obj_name}.{path}"
                                field.db_path = self._convert_to_db_path(obj_name, path)
                                field.extraction_confidence = 0.8
                                mapped = True
                                total_mapped += 1
                    
                    # 3. AI mapping for remaining fields
                    if not mapped and self.client:
                        ai_mapping = self._ai_map_field(field, form_structure)
                        if ai_mapping:
                            field.json_path = ai_mapping['json_path']
                            field.db_path = ai_mapping['db_path']
                            field.extraction_confidence = 0.7
                            mapped = True
                            total_mapped += 1
            
            # Update statistics
            form_structure.mapped_fields = sum(
                1 for fields in form_structure.parts.values() 
                for f in fields if f.db_path or f.json_path
            )
            
            form_structure.add_agent_log(self.name, f"Mapped {total_mapped} fields to JSON structure")
            self.log(f"Mapping complete. Mapped {total_mapped} fields", "success")
            
            self.status = "completed"
            return form_structure
            
        except Exception as e:
            self.log(f"Mapping failed: {str(e)}", "error")
            self.status = "error"
            return form_structure
    
    def _convert_to_db_path(self, obj_name: str, json_path: str) -> str:
        """Convert JSON path to database path format"""
        # Remove nested object references
        parts = json_path.split('.')
        
        # Categorize fields
        categories = {
            'PersonalInfo': ['FirstName', 'LastName', 'MiddleName', 'DateOfBirth', 'Gender', 'Ssn'],
            'ContactInfo': ['Email', 'Phone', 'Cell', 'Mobile', 'Work'],
            'Address': ['Street', 'City', 'State', 'Zip', 'Country'],
            'PassportDetails': ['Passport'],
            'VisaDetails': ['Visa', 'Status'],
        }
        
        # Find appropriate category
        category = "PersonalInfo"  # default
        for cat, keywords in categories.items():
            if any(keyword.lower() in json_path.lower() for keyword in keywords):
                category = cat
                break
        
        # Build database path
        field_name = parts[-1] if parts else json_path
        return f"{obj_name}.{category}.{field_name}"
    
    def _find_best_match(self, label: str) -> Optional[Tuple[str, str]]:
        """Find best match using fuzzy matching"""
        label_lower = label.lower()
        label_words = set(label_lower.split())
        
        best_match = None
        best_score = 0
        
        for pattern, candidates in self.enhanced_mappings.items():
            pattern_words = set(pattern.split())
            
            # Calculate similarity
            common_words = label_words.intersection(pattern_words)
            if common_words:
                score = len(common_words) / max(len(label_words), len(pattern_words))
                
                if score > best_score and score > 0.5:
                    best_score = score
                    best_match = candidates[0] if candidates else None
        
        return best_match
    
    def _ai_map_field(self, field: ExtractedField, form_structure: FormStructure) -> Optional[Dict]:
        """Use AI to map field to JSON structure"""
        if not self.client:
            return None
        
        try:
            # Create a summary of available paths
            available_paths = []
            for obj_type, structure in self.json_structures.items():
                obj_name = obj_type.replace('Object', '').lower()
                
                def extract_leaf_paths(data, prefix=""):
                    if isinstance(data, dict):
                        for key, value in data.items():
                            if isinstance(value, dict):
                                extract_leaf_paths(value, f"{prefix}.{key}" if prefix else key)
                            else:
                                available_paths.append(f"{obj_name}.{prefix}.{key}" if prefix else f"{obj_name}.{key}")
                
                extract_leaf_paths(structure)
            
            prompt = f"""
            Map this USCIS form field to the appropriate JSON structure path:
            
            Field:
            - Item Number: {field.item_number}
            - Label: {field.label}
            - Type: {field.type}
            - Part: {field.part}
            
            Available JSON paths (partial list):
            {chr(10).join(available_paths[:50])}  # Show first 50 paths
            
            Return JSON:
            {{
                "json_path": "objectname.path.to.field",
                "db_path": "objectname.Category.fieldName",
                "confidence": 0.8
            }}
            
            If no good match exists, return null.
            """
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert at mapping USCIS form fields to database structures."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=200
            )
            
            result = json.loads(response.choices[0].message.content)
            return result if result else None
            
        except Exception as e:
            self.log(f"AI mapping error for field {field.item_number}: {str(e)}", "warning")
            return None

# Enhanced Validation Agent
class ValidationAgent(Agent):
    """Enhanced validation with JSON structure awareness"""
    
    def __init__(self):
        super().__init__("Validation Agent", "Field Validation & Feedback")
        self.json_structures = load_json_structures()
        
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
    
    def _check_part_ordering(self, form_structure: FormStructure, feedback: Optional[ValidationFeedback]) -> int:
        """Check if parts are properly ordered and numbered"""
        issues = 0
        
        # Extract part numbers
        part_numbers = []
        for part_name in form_structure.parts.keys():
            match = re.search(r'Part\s+(\d+)', part_name, re.IGNORECASE)
            if match:
                part_numbers.append((int(match.group(1)), part_name))
        
        part_numbers.sort(key=lambda x: x[0])
        
        # Check for gaps or misnumbering
        if part_numbers:
            expected_num = 1
            for actual_num, part_name in part_numbers:
                if actual_num != expected_num:
                    issues += 1
                    
                    if actual_num > expected_num:
                        # Missing parts
                        for missing in range(expected_num, actual_num):
                            self.log(f"⚠️ Part ordering issue: Part {missing} is missing", "warning")
                            if feedback:
                                feedback.missing_parts.append({
                                    "number": missing,
                                    "name": f"Part {missing}",
                                    "expected_fields": 10
                                })
                    else:
                        # Duplicate or misnumbered
                        self.log(f"⚠️ Part ordering issue: Unexpected {part_name} (expected Part {expected_num})", "warning")
                        if feedback:
                            feedback.field_issues.append({
                                "part": part_name,
                                "issue": f"Should be Part {expected_num}"
                            })
                
                expected_num = actual_num + 1
        
        # Ensure parts are stored in correct order
        if issues > 0 and feedback:
            feedback.suggestions.append("Fix part numbering to ensure sequential order (Part 1, Part 2, etc.)")
            
        return issues
    
    def execute(self, form_structure: FormStructure, generate_feedback: bool = True) -> Tuple[FormStructure, Optional[ValidationFeedback]]:
        """Validate and generate feedback"""
        self.status = "active"
        self.iteration += 1
        self.log(f"Validating {form_structure.form_number} (Iteration {self.iteration})...", "info")
        
        feedback = ValidationFeedback() if generate_feedback else None
        
        try:
            # Get expected structure
            expected = self.expected_structures.get(form_structure.form_number, {})
            
            # 1. Check part ordering first
            ordering_issues = self._check_part_ordering(form_structure, feedback)
            
            # 2. Check for missing parts
            if expected and "required_parts" in expected:
                missing_parts = self._check_missing_parts(form_structure, expected, feedback)
            
            # 3. Check part completeness
            if expected and "min_fields_per_part" in expected:
                incomplete_parts = self._check_incomplete_parts(form_structure, expected, feedback)
            
            # 4. Validate sub-item structure
            sub_item_issues = self._validate_sub_items(form_structure, feedback)
            
            # 5. Validate JSON mappings
            mapping_issues = self._validate_json_mappings(form_structure, feedback)
            
            # 6. Check overall completeness
            total_issues = self._check_overall_completeness(form_structure, expected, feedback)
            
            # Calculate validation score
            form_structure.validated_fields = sum(
                1 for fields in form_structure.parts.values() 
                for f in fields if f.is_validated
            )
            
            if form_structure.total_fields > 0:
                base_score = form_structure.validated_fields / form_structure.total_fields
                
                # Penalties
                penalty = 0
                penalty += min(0.1, len(missing_parts) * 0.02) if 'missing_parts' in locals() else 0
                penalty += min(0.1, len(incomplete_parts) * 0.01) if 'incomplete_parts' in locals() else 0
                penalty += min(0.1, sub_item_issues * 0.01)
                penalty += min(0.1, mapping_issues * 0.005)
                penalty += min(0.05, ordering_issues * 0.01)
                
                form_structure.validation_score = max(0, base_score - penalty)
            else:
                form_structure.validation_score = 0.0
            
            # Determine if retry needed
            if feedback:
                if missing_parts or (incomplete_parts and form_structure.extraction_iterations < 3) or ordering_issues > 2:
                    feedback.needs_retry = True
                    feedback.severity = "error" if (missing_parts or ordering_issues > 3) else "warning"
                    
                    # Add suggestions
                    if missing_parts:
                        feedback.suggestions.append("Focus on finding missing parts by searching all pages")
                    if incomplete_parts:
                        feedback.suggestions.append("Use more aggressive extraction patterns for incomplete parts")
                    if sub_item_issues > 5:
                        feedback.suggestions.append("Improve sub-item extraction for compound fields")
                    if ordering_issues > 0:
                        feedback.suggestions.append("Fix part numbering to ensure sequential order (Part 1, Part 2, etc.)")
                    
                    self.log(f"Validation found issues requiring retry", "warning")
            
            # Summary
            self.log("=== Validation Summary ===", "info")
            self.log(f"Parts found: {len(form_structure.parts)}/{expected.get('parts', '?')}", "info")
            if ordering_issues > 0:
                self.log(f"Part ordering issues: {ordering_issues}", "warning")
            self.log(f"Total fields: {form_structure.total_fields}/{expected.get('min_fields', '?')}", "info")
            self.log(f"Fields mapped to JSON: {form_structure.mapped_fields}", "info")
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
    
    def _validate_sub_items(self, form_structure: FormStructure, 
                          feedback: Optional[ValidationFeedback]) -> int:
        """Validate sub-item structure"""
        issues = 0
        
        # Expected sub-item patterns
        expected_sub_items = {
            "legal name": ["a", "b", "c"],  # Family, Given, Middle
            "your name": ["a", "b", "c"],
            "mailing address": ["a", "b", "c", "d", "e"],  # Street, City, State, ZIP, Country
            "physical address": ["a", "b", "c", "d", "e"],
        }
        
        for part_name, fields in form_structure.parts.items():
            # Group by parent item
            item_groups = defaultdict(list)
            
            for field in fields:
                if field.parent_item:
                    item_groups[field.parent_item].append(field)
                elif field.item_number and not field.item_number[-1].isalpha():
                    # Check if this should have sub-items
                    label_lower = field.label.lower()
                    for pattern, expected_subs in expected_sub_items.items():
                        if pattern in label_lower:
                            # This should have sub-items
                            item_groups[field.item_number].append(field)
            
            # Validate sub-item structure
            for parent_item, group_fields in item_groups.items():
                sub_items = [f for f in group_fields if f.parent_item == parent_item]
                
                # Check ordering
                expected_order = ['a', 'b', 'c', 'd', 'e', 'f']
                for i, field in enumerate(sub_items):
                    if field.item_number:
                        expected_suffix = expected_order[i] if i < len(expected_order) else ''
                        if not field.item_number.endswith(expected_suffix):
                            issues += 1
                            self.log(f"⚠️ Sub-item ordering issue: {field.item_number} (expected {parent_item}{expected_suffix})", "warning")
                            
                            if feedback:
                                feedback.field_issues.append({
                                    "part": part_name,
                                    "field": field.item_number,
                                    "issue": f"Expected sub-item {parent_item}{expected_suffix}"
                                })
        
        return issues
    
    def _validate_json_mappings(self, form_structure: FormStructure, 
                               feedback: Optional[ValidationFeedback]) -> int:
        """Validate JSON mappings against structure"""
        issues = 0
        
        for part_name, fields in form_structure.parts.items():
            for field in fields:
                if field.json_path:
                    # Validate path exists in JSON structure
                    path_parts = field.json_path.split('.')
                    if path_parts:
                        obj_name = path_parts[0]
                        obj_type = f"{obj_name.capitalize()}Object"
                        
                        if obj_type not in self.json_structures:
                            issues += 1
                            self.log(f"⚠️ Invalid object type in mapping: {obj_type}", "warning")
                            
                            if feedback:
                                feedback.field_issues.append({
                                    "part": part_name,
                                    "field": field.item_number or field.name,
                                    "issue": f"Invalid JSON object type: {obj_type}"
                                })
        
        return issues
    
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

# Coordinator Agent
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
        mapping_agent = JSONMappingAgent() if auto_map else None
        
        form_structure = None
        iteration = 0
        
        try:
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
                self.log("📊 Phase 3: JSON Structure Mapping", "info")
                form_structure = mapping_agent.execute(form_structure)
            
            # Final statistics
            if form_structure:
                self.log("=== Final Results ===", "success")
                self.log(f"Total iterations: {iteration}", "info")
                self.log(f"Parts found: {len(form_structure.parts)}", "info") 
                
                # Check part ordering
                part_numbers = []
                for part_name in form_structure.parts.keys():
                    match = re.search(r'Part\s+(\d+)', part_name)
                    if match:
                        part_numbers.append(int(match.group(1)))
                
                if part_numbers:
                    part_numbers.sort()
                    self.log(f"Part sequence: {', '.join([f'Part {n}' for n in part_numbers])}", "info")
                
                self.log(f"Fields extracted: {form_structure.total_fields}", "info")
                self.log(f"Fields validated: {form_structure.validated_fields}", "info")
                self.log(f"Fields mapped: {form_structure.mapped_fields}", "info")
                self.log(f"Validation score: {form_structure.validation_score:.0%}", "info")
            
            self.status = "completed"
            return form_structure
            
        finally:
            # Cleanup resources
            if hasattr(research_agent, 'cleanup'):
                research_agent.cleanup()

# Enhanced field rendering with edit capabilities
def render_field_card_enhanced(field: ExtractedField, idx: int, part_name: str, form_structure: FormStructure):
    """Render field card with edit capabilities"""
    status_class = "mapped" if field.json_path else ("questionnaire" if field.is_questionnaire else "unmapped")
    status_text = "✅ Mapped" if field.json_path else ("📋 Questionnaire" if field.is_questionnaire else "❌ Not Mapped")
    
    if field.manually_assigned:
        status_text += " (Manual)"
    
    if field.extraction_iteration > 1:
        status_text += f" (Iter {field.extraction_iteration})"
    
    if field.is_user_added:
        status_text += " (Added)"
    
    # Edit mode
    edit_key = f"edit_{field.field_id}"
    if edit_key not in st.session_state:
        st.session_state[edit_key] = False
    
    card_class = f"field-card {status_class}"
    if st.session_state[edit_key]:
        card_class += " edit-mode"
    
    st.markdown(f'<div class="{card_class}">', unsafe_allow_html=True)
    
    # Sub-item styling
    if field.parent_item:
        st.markdown('<div class="sub-item">', unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns([2.5, 4, 2, 0.5])
    
    with col1:
        if st.session_state[edit_key]:
            # Edit mode
            new_item = st.text_input("Item #", value=field.item_number or "", key=f"item_{field.field_id}")
            new_label = st.text_input("Label", value=field.label, key=f"label_{field.field_id}")
            
            if st.button("💾 Save", key=f"save_{field.field_id}"):
                field.item_number = new_item
                field.label = new_label
                st.session_state[edit_key] = False
                st.rerun()
        else:
            # Display mode
            if field.item_number:
                st.markdown(f'<span class="item-number">{field.item_number}</span>{field.label}', 
                           unsafe_allow_html=True)
            else:
                st.markdown(f'**{field.label}**')
            
            # Type badge
            st.markdown(f'<span class="field-type-badge type-{field.type}">{field.type}</span>', 
                       unsafe_allow_html=True)
    
    with col2:
        if field.type in ["text", "number", "date", "email", "phone"] and not field.is_questionnaire:
            # JSON structure mapping
            json_structures = load_json_structures()
            options = ["-- Select JSON Field --", "📋 Move to Questionnaire"]
            
            # Build options from JSON structures
            for obj_type, structure in json_structures.items():
                obj_name = obj_type.replace('Object', '').lower()
                options.append(f"═══ {obj_type} ═══")
                
                def add_paths(data, prefix=""):
                    if isinstance(data, dict):
                        for key, value in data.items():
                            if isinstance(value, dict):
                                add_paths(value, f"{prefix}.{key}" if prefix else key)
                            else:
                                path = f"{prefix}.{key}" if prefix else key
                                options.append(f"  {obj_name}.{path}")
                
                add_paths(structure)
            
            current = field.json_path if field.json_path else "-- Select JSON Field --"
            
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
                    field.json_path = None
                    field.db_path = None
                    st.rerun()
                elif selected != "-- Select JSON Field --":
                    field.json_path = selected.strip()
                    field.is_questionnaire = False
                    field.manually_assigned = True
                    # Convert to db_path
                    parts = field.json_path.split('.')
                    if len(parts) >= 2:
                        obj_name = parts[0]
                        field_name = parts[-1]
                        field.db_path = f"{obj_name}.PersonalInfo.{field_name}"  # Simplified
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
        if field.parent_item:
            st.caption(f"Parent: {field.parent_item}")
    
    with col4:
        if st.button("✏️", key=f"edit_btn_{field.field_id}", help="Edit field"):
            st.session_state[edit_key] = not st.session_state[edit_key]
            st.rerun()
    
    if field.parent_item:
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

def add_new_field(part_name: str, form_structure: FormStructure):
    """Add a new field to a part"""
    with st.expander("➕ Add New Field", expanded=False):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            new_item = st.text_input("Item Number", placeholder="e.g., 9a")
            new_label = st.text_input("Field Label", placeholder="e.g., Previous Address")
        
        with col2:
            new_type = st.selectbox("Field Type", ["text", "date", "number", "checkbox", "email", "phone"])
            parent_item = st.text_input("Parent Item (optional)", placeholder="e.g., 9")
        
        with col3:
            if st.button("Add Field", type="primary", use_container_width=True):
                if new_label:
                    # Find next available number if not provided
                    if not new_item:
                        existing_nums = []
                        for field in form_structure.parts[part_name]:
                            if field.item_number and field.item_number[0].isdigit():
                                try:
                                    num = int(re.match(r'(\d+)', field.item_number).group(1))
                                    existing_nums.append(num)
                                except:
                                    pass
                        next_num = max(existing_nums) + 1 if existing_nums else 1
                        new_item = str(next_num)
                    
                    # Create new field
                    part_num = int(re.search(r'\d+', part_name).group()) if re.search(r'\d+', part_name) else 1
                    
                    new_field = ExtractedField(
                        name=f"field_{new_item.replace('.', '_')}",
                        label=new_label,
                        type=new_type,
                        part=part_name,
                        part_number=part_num,
                        item_number=new_item,
                        parent_item=parent_item if parent_item else None,
                        extraction_method="manual",
                        is_user_added=True,
                        extraction_iteration=1
                    )
                    
                    form_structure.parts[part_name].append(new_field)
                    form_structure.total_fields += 1
                    st.success(f"Added field {new_item}: {new_label}")
                    st.rerun()
                else:
                    st.error("Please provide a field label")

# Export functions
def generate_typescript_enhanced(form_structure: FormStructure) -> str:
    """Generate TypeScript with JSON structure mapping"""
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
    
    # Natural sort function for parts
    def natural_sort_key(part_name):
        match = re.search(r'Part\s+(\d+)', part_name[0])
        if match:
            return int(match.group(1))
        return 999
    
    sorted_parts = sorted(form_structure.parts.items(), key=natural_sort_key)
    
    # Map fields using JSON paths
    for part_name, fields in sorted_parts:
        for field in fields:
            if field.json_path:
                # Determine section from path
                path_parts = field.json_path.split('.')
                obj_name = path_parts[0] if path_parts else ""
                
                section_map = {
                    'beneficiary': 'beneficiaryData',
                    'petitioner': 'beneficiaryData',
                    'attorney': 'attorneyData',
                    'case': 'caseData',
                    'customer': 'customerData'
                }
                
                section = section_map.get(obj_name, 'defaultData')
                
                # Create key
                key = field.name
                suffix = {
                    'text': ':TextBox',
                    'checkbox': ':CheckBox',
                    'radio': ':RadioBox',
                    'date': ':Date',
                    'number': ':TextBox',
                    'signature': ':SignatureBox',
                    'email': ':TextBox',
                    'phone': ':TextBox'
                }.get(field.type, ':TextBox')
                
                sections[section][key] = f"{field.json_path}{suffix}"
            
            elif field.is_questionnaire:
                sections['questionnaireData'][field.field_id] = f"{field.name}:{field.type}"
    
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

def generate_json_enhanced(form_structure: FormStructure) -> str:
    """Generate enhanced JSON with sub-items"""
    controls = []
    
    # Natural sort function for parts
    def natural_sort_key(part_name):
        match = re.search(r'Part\s+(\d+)', part_name[0])
        if match:
            return int(match.group(1))
        return 999
    
    sorted_parts = sorted(form_structure.parts.items(), key=natural_sort_key)
    
    for part_name, fields in sorted_parts:
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
            
            # Group by parent item
            item_groups = defaultdict(list)
            standalone_fields = []
            
            for field in quest_fields:
                if field.parent_item:
                    item_groups[field.parent_item].append(field)
                else:
                    standalone_fields.append(field)
            
            # Add grouped fields
            for parent_item, sub_fields in sorted(item_groups.items()):
                # Find parent field
                parent_field = next((f for f in fields if f.item_number == parent_item), None)
                if parent_field:
                    # Add parent as group header
                    controls.append({
                        "name": f"group_{parent_item}",
                        "label": f"{parent_item}. {parent_field.label}",
                        "type": "group",
                        "style": {"col": "12"}
                    })
                
                # Add sub-fields
                for field in sorted(sub_fields, key=lambda f: f.item_number):
                    label = f"{field.item_number}. {field.label}"
                    
                    control = {
                        "name": field.name,
                        "label": label,
                        "type": field.type if field.type != "checkbox" else "colorSwitch",
                        "validators": {"required": False},
                        "style": {"col": "6", "indent": True}
                    }
                    
                    controls.append(control)
            
            # Add standalone fields
            for field in standalone_fields:
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
    st.markdown('<div class="main-header"><h1>🤖 Smart USCIS Form Reader</h1><p>Enhanced with JSON Structure Mapping & Sub-Item Extraction</p></div>', 
               unsafe_allow_html=True)
    
    # Initialize session state
    if 'form_structure' not in st.session_state:
        st.session_state.form_structure = None
    if 'agents' not in st.session_state:
        st.session_state.agents = {}
    if 'json_structures' not in st.session_state:
        st.session_state.json_structures = load_json_structures()
    
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
        auto_map = st.checkbox("Auto-Map to JSON Structure", value=True)
        max_iterations = st.slider("Max Feedback Iterations", 1, 5, 3)
        
        # JSON Structure info
        st.markdown("### 📊 JSON Structures")
        st.caption(f"Loaded {len(st.session_state.json_structures)} object types")
        
        with st.expander("View Structures"):
            for obj_type in st.session_state.json_structures:
                st.caption(f"• {obj_type}")
        
        # Form info
        if st.session_state.form_structure:
            form = st.session_state.form_structure
            st.markdown("### 📄 Current Form")
            st.info(f"{form.form_number}: {form.form_title}")
            
            st.markdown("### 📊 Statistics")
            st.metric("Extraction Iterations", form.extraction_iterations)
            st.metric("Total Fields", form.total_fields)
            st.metric("Validated", f"{form.validated_fields}/{form.total_fields}")
            st.metric("Mapped to JSON", form.mapped_fields)
            
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
                    coordinator.max_iterations = max_iterations
                    
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
                                
                                # Natural sort function
                                def natural_sort_key(part_name):
                                    match = re.search(r'Part\s+(\d+)', part_name[0])
                                    if match:
                                        return int(match.group(1))
                                    return 999
                                
                                sorted_parts = sorted(form_structure.parts.items(), key=natural_sort_key)
                                
                                for part_name, fields in sorted_parts:
                                    # Count sub-items
                                    main_items = sum(1 for f in fields if not f.parent_item)
                                    sub_items = sum(1 for f in fields if f.parent_item)
                                    st.markdown(f"**{part_name}**: {len(fields)} fields ({main_items} main, {sub_items} sub-items)")
                                    
                                # Sample sub-items
                                st.markdown("### Sample Sub-Item Structure:")
                                for part_name, fields in sorted_parts:
                                    # Find a good example
                                    for field in fields:
                                        if field.item_number == "1" and field.label.lower().find("name") >= 0:
                                            sub_fields = [f for f in fields if f.parent_item == "1"]
                                            if sub_fields:
                                                st.markdown(f"**Example from {part_name}:**")
                                                st.markdown(f"- {field.item_number}. {field.label}")
                                                for sub in sorted(sub_fields, key=lambda f: f.item_number):
                                                    st.markdown(f"  - {sub.item_number}. {sub.label}")
                                                break
                                    else:
                                        continue
                                    break
    
    with tabs[1]:
        form_structure = st.session_state.get('form_structure')
        if form_structure and form_structure.parts:
            st.markdown("## 🎯 Field Mapping to JSON Structure")
            
            # Natural sort for parts
            def natural_sort_key(part_name):
                """Extract number for natural sorting"""
                match = re.search(r'Part\s+(\d+)', part_name)
                if match:
                    return int(match.group(1))
                return 999  # Put non-standard parts at end
            
            sorted_parts = sorted(form_structure.parts.keys(), key=natural_sort_key)
            
            selected_part = st.selectbox(
                "Select Part",
                options=sorted_parts,
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
                
                # Add new field button
                add_new_field(selected_part, form_structure)
                
                # Stats
                st.markdown('<div class="extraction-stats">', unsafe_allow_html=True)
                
                col1, col2, col3, col4, col5 = st.columns(5)
                with col1:
                    text_fields = sum(1 for f in fields if f.type in ["text", "number", "date"])
                    st.metric("Text Fields", text_fields)
                with col2:
                    checkbox_fields = sum(1 for f in fields if f.type == "checkbox")
                    st.metric("Checkboxes", checkbox_fields)
                with col3:
                    mapped = sum(1 for f in fields if f.json_path)
                    st.metric("Mapped", mapped)
                with col4:
                    sub_items = sum(1 for f in fields if f.parent_item)
                    st.metric("Sub-Items", sub_items)
                with col5:
                    user_added = sum(1 for f in fields if f.is_user_added)
                    st.metric("User Added", user_added)
                
                st.markdown('</div>', unsafe_allow_html=True)
                
                # Group fields by parent item
                item_groups = defaultdict(list)
                standalone_fields = []
                
                for field in fields:
                    if field.parent_item:
                        item_groups[field.parent_item].append(field)
                    elif field.item_number and any(f.parent_item == field.item_number for f in fields):
                        # This is a parent item
                        item_groups[field.item_number].append(field)
                    else:
                        standalone_fields.append(field)
                
                # Display grouped fields first
                for parent_item in sorted(item_groups.keys()):
                    group_fields = sorted(item_groups[parent_item], 
                                        key=lambda f: (f.parent_item == parent_item, f.item_number or ""))
                    
                    # Show parent field first
                    parent_field = next((f for f in group_fields if f.item_number == parent_item), None)
                    
                    if parent_field:
                        st.markdown('<div class="item-group">', unsafe_allow_html=True)
                        render_field_card_enhanced(parent_field, fields.index(parent_field), selected_part, form_structure)
                        
                        # Show sub-items
                        sub_fields = [f for f in group_fields if f.parent_item == parent_item]
                        for sub_field in sorted(sub_fields, key=lambda f: f.item_number or ""):
                            render_field_card_enhanced(sub_field, fields.index(sub_field), selected_part, form_structure)
                        
                        st.markdown('</div>', unsafe_allow_html=True)
                
                # Display standalone fields
                for field in sorted(standalone_fields, key=lambda f: f.item_number or "ZZZ"):
                    render_field_card_enhanced(field, fields.index(field), selected_part, form_structure)
        else:
            st.info("👆 Please upload and process a form first")
    
    with tabs[2]:
        form_structure = st.session_state.get('form_structure')
        if form_structure and form_structure.parts:
            st.markdown("## 📥 Export with JSON Mapping")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("🔨 Generate TypeScript", use_container_width=True, type="primary"):
                    ts_code = generate_typescript_enhanced(form_structure)
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
                    json_code = generate_json_enhanced(form_structure)
                    st.download_button(
                        "⬇️ Download JSON",
                        json_code,
                        f"{form_structure.form_number}-questionnaire.json",
                        mime="application/json",
                        use_container_width=True
                    )
                    with st.expander("Preview", expanded=True):
                        st.code(json_code, language="json")
            
            # Export mapping summary
            st.markdown("### 📊 Mapping Summary")
            
            # Count mappings by object type
            mapping_counts = defaultdict(int)
            unmapped_count = 0
            
            # Natural sort function
            def natural_sort_key(part_name):
                match = re.search(r'Part\s+(\d+)', part_name[0])
                if match:
                    return int(match.group(1))
                return 999
            
            sorted_parts = sorted(form_structure.parts.items(), key=natural_sort_key)
            
            for part_name, fields in sorted_parts:
                for field in fields:
                    if field.json_path:
                        obj_type = field.json_path.split('.')[0]
                        mapping_counts[obj_type] += 1
                    elif not field.is_questionnaire:
                        unmapped_count += 1
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("**Mapped Fields by Object:**")
                for obj_type, count in sorted(mapping_counts.items()):
                    st.caption(f"{obj_type.capitalize()}: {count} fields")
            
            with col2:
                st.markdown("**Unmapped Fields:**")
                st.caption(f"{unmapped_count} fields")
            
            with col3:
                st.markdown("**Questionnaire Fields:**")
                quest_count = sum(1 for fields in form_structure.parts.values() 
                                for f in fields if f.is_questionnaire)
                st.caption(f"{quest_count} fields")
    
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
