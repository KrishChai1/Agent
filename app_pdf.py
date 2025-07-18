#!/usr/bin/env python3
"""
Enhanced Smart USCIS Form Reader with Sequential Extraction
Correctly extracts fields in exact sequence from USCIS PDFs
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
    page_title="Smart USCIS Form Reader - Sequential Extraction",
    page_icon="🤖",
    layout="wide"
)

def natural_sort_item_number(item_number: str) -> tuple:
    """Convert item number to tuple for natural sorting
    Examples:
    - "1" -> (1, 0, "")
    - "1a" -> (1, 1, "a")
    - "10" -> (10, 0, "")
    - "10b" -> (10, 2, "b")
    """
    if not item_number:
        return (999, 999, "")
    
    # Match number and optional letter
    match = re.match(r'^(\d+)([a-z])?$', item_number.lower())
    if match:
        num = int(match.group(1))
        letter = match.group(2) or ""
        # Convert letter to number for sub-sorting (a=1, b=2, etc.)
        letter_num = ord(letter) - ord('a') + 1 if letter else 0
        return (num, letter_num, letter)
    
    # Fallback for non-standard formats
    return (999, 999, item_number)

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
    .sequence-warning {
        background: #ff9800;
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 5px;
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
            }
        }
        
        if 'json_structures' in st.session_state:
            return st.session_state['json_structures']
        
        return default_structures
        
    except Exception as e:
        return default_structures

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
    sequence_errors: List[Dict[str, Any]] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    severity: str = "info"  # info, warning, error
    needs_retry: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "missing_parts": self.missing_parts,
            "incomplete_parts": self.incomplete_parts,
            "field_issues": self.field_issues,
            "sequence_errors": self.sequence_errors,
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
    extraction_method: str = ""  # "sequential", "widget", "ai", "manual"
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
            for suggestion in feedback.suggestions:
                if "sequence" in suggestion.lower() or "order" in suggestion.lower():
                    self.log("Received feedback about field ordering - will ensure proper sequencing", "feedback")
    
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

# Enhanced Research Agent with Sequential Extraction
class ResearchAgent(Agent):
    """Sequential extraction that maintains exact PDF order"""
    
    def __init__(self):
        super().__init__("Research Agent", "Sequential Field Extraction")
        self.client = get_openai_client()
        self.pdf_bytes = None
        self.doc = None
        self.page_texts = []
    
    def execute(self, pdf_file=None, use_ai: bool = True, 
                form_structure: Optional[FormStructure] = None,
                feedback: Optional[ValidationFeedback] = None) -> Optional[FormStructure]:
        """Extract with sequential processing maintaining exact PDF order"""
        self.status = "active"
        self.iteration += 1
        
        # First iteration - full extraction
        if pdf_file is not None:
            self.pdf_bytes = pdf_file.read() if hasattr(pdf_file, 'read') else pdf_file
            if self.doc:
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
            
            # Set expected structure
            self._set_expected_structure(form_structure)
        
        # Handle feedback-driven re-extraction
        if feedback and form_structure:
            if not self.doc or not hasattr(self, 'pdf_bytes'):
                self.log("Document not available for feedback processing", "error")
                return form_structure
            
            try:
                _ = self.doc.page_count
            except ValueError:
                self.doc = fitz.open(stream=self.pdf_bytes, filetype="pdf")
                self.page_texts = [page.get_text() for page in self.doc]
                self.log("Reopened document for feedback processing", "info")
            
            self.log(f"Received feedback - attempting targeted extraction", "feedback")
            return self._handle_extraction_feedback(form_structure, feedback, use_ai)
        
        # Regular extraction with sequential processing
        form_structure.extraction_iterations = self.iteration
        
        # PRIMARY METHOD: Sequential extraction
        self._sequential_extraction_primary(form_structure)
        
        # SECONDARY: Complement with widgets
        self._extract_from_all_widgets_sequential(form_structure)
        
        # TERTIARY: Use AI only to fill obvious gaps
        if use_ai and self.client and form_structure.total_fields < 50:
            self._ai_fill_missing_fields(form_structure)
        
        # Validate sequence
        validation_results = self._validate_extraction_sequence(form_structure)
        if validation_results["missing_items"]:
            self.log(f"Warning: {len(validation_results['missing_items'])} missing items detected", "warning")
            for missing in validation_results["missing_items"][:5]:  # Show first 5
                self.log(f"  Missing: {missing['part']} Item {missing['item']}", "warning")
        
        # Ensure parts are properly ordered
        form_structure.reorder_parts()
        
        form_structure.add_agent_log(self.name, f"Iteration {self.iteration}: Extracted {form_structure.total_fields} fields")
        self.log(f"Sequential extraction complete: {form_structure.total_fields} fields found", "success")
        
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
    
    def _sequential_extraction_primary(self, form_structure: FormStructure):
        """Primary extraction method that processes PDF sequentially line by line"""
        
        current_part = 0
        current_part_name = ""
        current_part_title = ""
        last_item_number = 0
        
        for page_num, page in enumerate(self.doc):
            if page_num >= len(self.page_texts):
                continue
            
            page_text = self.page_texts[page_num]
            lines = page_text.split('\n')
            
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                
                if not line:
                    i += 1
                    continue
                
                # Check for part header (flexible matching)
                part_patterns = [
                    r'^Part\s+(\d+)\.?\s*(.*)?$',  # Part 1. Title or Part 1 Title
                    r'^PART\s+(\d+)\.?\s*(.*)?$',  # PART 1
                    r'^Part\s+([IVX]+)\.?\s*(.*)?$',  # Part I, Part II, etc.
                ]
                
                part_match = None
                for pattern in part_patterns:
                    part_match = re.match(pattern, line, re.IGNORECASE)
                    if part_match:
                        break
                
                if part_match:
                    # Extract part number
                    part_num_str = part_match.group(1)
                    if part_num_str.isdigit():
                        current_part = int(part_num_str)
                    else:
                        # Handle Roman numerals
                        roman_map = {'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5, 
                                   'VI': 6, 'VII': 7, 'VIII': 8, 'IX': 9, 'X': 10}
                        current_part = roman_map.get(part_num_str.upper(), current_part + 1)
                    
                    current_part_name = f"Part {current_part}"
                    
                    # Get part title
                    current_part_title = part_match.group(2) if part_match.group(2) else ""
                    if not current_part_title and i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        if next_line and not re.match(r'^\d+\.', next_line):
                            current_part_title = next_line
                            i += 1
                    
                    if current_part_name not in form_structure.parts:
                        form_structure.parts[current_part_name] = []
                    
                    self.log(f"Processing {current_part_name}: {current_part_title}", "info")
                    last_item_number = 0
                    i += 1
                    continue
                
                # Skip if no current part
                if not current_part_name:
                    i += 1
                    continue
                
                # Extract numbered field with exact label
                field_patterns = [
                    r'^(\d+)\.\s+(.+?)$',  # Standard: "1. Label"
                    r'^(\d+)\s+(.+?)$',    # Without period: "1 Label"
                    r'^Item\s+(\d+)\.\s+(.+?)$',  # "Item 1. Label"
                    r'^Question\s+(\d+)\.\s+(.+?)$',  # "Question 1. Label"
                ]
                
                field_match = None
                for pattern in field_patterns:
                    field_match = re.match(pattern, line)
                    if field_match:
                        break
                
                if field_match:
                    item_number = field_match.group(1)
                    full_label = field_match.group(2).strip()
                    
                    # Create field with exact label from PDF
                    field = ExtractedField(
                        name=f"field_{item_number}",
                        label=full_label,  # Use exact label, no modifications
                        type=self._determine_field_type_sequential(full_label, lines, i),
                        page=page_num + 1,
                        part=current_part_name,
                        part_number=current_part,
                        part_title=current_part_title,
                        item_number=item_number,
                        extraction_method="sequential",
                        extraction_iteration=self.iteration,
                        raw_field_name=line  # Store complete line
                    )
                    
                    # Check if this field has sub-items
                    has_subitems, sub_items = self._check_and_extract_subitems(
                        lines, i + 1, item_number, page_num + 1, 
                        current_part_name, current_part, current_part_title
                    )
                    
                    if has_subitems:
                        field.type = "group"
                    
                    # Add main field
                    form_structure.parts[current_part_name].append(field)
                    form_structure.total_fields += 1
                    
                    # Add sub-items in order
                    for sub_item in sub_items:
                        form_structure.parts[current_part_name].append(sub_item)
                        form_structure.total_fields += 1
                    
                    last_item_number = int(item_number)
                    
                    # Skip processed lines (but don't skip too many)
                    i += 1
                    continue
                
                # Check for sub-item pattern (only if we have a recent parent)
                if last_item_number > 0:
                    sub_patterns = [
                        rf'^{last_item_number}([a-z])\.\s+(.+?)$',  # 1a. Label
                        rf'^\s+([a-z])\.\s+(.+?)$',  # Indented: a. Label
                        rf'^([a-z])\.\s+(.+?)$',  # Just: a. Label (risky but sometimes needed)
                    ]
                    
                    sub_match = None
                    for pattern in sub_patterns:
                        if pattern.startswith(rf'^{last_item_number}'):
                            sub_match = re.match(pattern, line)
                        else:
                            # For patterns without item number, check context
                            temp_match = re.match(pattern, line)
                            if temp_match:
                                # Verify this is likely a sub-item by checking if it follows the parent
                                expected_letter = chr(ord('a') + len([f for f in form_structure.parts[current_part_name] 
                                                                    if f.parent_item == str(last_item_number)]))
                                if temp_match.group(1) == expected_letter:
                                    sub_match = temp_match
                        
                        if sub_match:
                            break
                    
                    if sub_match:
                        if sub_match.lastindex == 2:  # Has both letter and label
                            sub_letter = sub_match.group(1)
                            full_label = sub_match.group(2).strip()
                        else:
                            # Handle cases where we might not have captured both groups
                            sub_letter = 'a'  # Default
                            full_label = line.strip()
                        
                        sub_field = ExtractedField(
                            name=f"field_{last_item_number}{sub_letter}",
                            label=full_label,
                            type=self._determine_field_type_sequential(full_label, lines, i),
                            page=page_num + 1,
                            part=current_part_name,
                            part_number=current_part,
                            part_title=current_part_title,
                            item_number=f"{last_item_number}{sub_letter}",
                            parent_item=str(last_item_number),
                            extraction_method="sequential",
                            extraction_iteration=self.iteration,
                            raw_field_name=line
                        )
                        
                        form_structure.parts[current_part_name].append(sub_field)
                        form_structure.total_fields += 1
                
                i += 1
    
    def _check_and_extract_subitems(self, lines: List[str], start_idx: int, 
                                   parent_num: str, page_num: int,
                                   part_name: str, part_number: int,
                                   part_title: str) -> Tuple[bool, List[ExtractedField]]:
        """Check if a field has sub-items and extract them in sequence"""
        sub_items = []
        expected_letters = 'abcdefghijklmnopqrstuvwxyz'
        expected_idx = 0
        
        # Peek ahead to check for sub-items
        i = start_idx
        consecutive_empty = 0
        
        while i < len(lines) and expected_idx < len(expected_letters) and consecutive_empty < 3:
            line = lines[i].strip()
            
            if not line:
                consecutive_empty += 1
                i += 1
                continue
            
            consecutive_empty = 0
            
            # Stop if we hit another main item (but not our sub-items)
            if re.match(r'^(\d+)\.\s+', line) and not line.startswith(f"{parent_num}"):
                break
            
            # Check for expected sub-item
            expected_letter = expected_letters[expected_idx]
            
            # Try multiple patterns
            sub_patterns = [
                rf'^{parent_num}{expected_letter}\.\s+(.+?)$',  # 1a. Label
                rf'^{expected_letter}\.\s+(.+?)$',  # a. Label
                rf'^\s+{expected_letter}\.\s+(.+?)$',  # Indented a. Label
                rf'^{expected_letter}\)\s+(.+?)$',  # a) Label
            ]
            
            matched = False
            for pattern in sub_patterns:
                sub_match = re.match(pattern, line)
                if sub_match:
                    full_label = sub_match.group(1).strip() if sub_match.lastindex >= 1 else line.strip()
                    
                    sub_field = ExtractedField(
                        name=f"field_{parent_num}{expected_letter}",
                        label=full_label,
                        type=self._determine_field_type_sequential(full_label, lines, i),
                        page=page_num,
                        part=part_name,
                        part_number=part_number,
                        part_title=part_title,
                        item_number=f"{parent_num}{expected_letter}",
                        parent_item=parent_num,
                        extraction_method="sequential",
                        extraction_iteration=self.iteration,
                        raw_field_name=line
                    )
                    
                    sub_items.append(sub_field)
                    expected_idx += 1
                    matched = True
                    break
            
            if not matched:
                # Check if line looks like it should be a sub-item based on content
                if expected_idx == 0 and any(keyword in line.lower() for keyword in 
                                            ['family name', 'last name', 'surname']):
                    # Likely first sub-item for name field
                    sub_field = ExtractedField(
                        name=f"field_{parent_num}a",
                        label=line,
                        type="text",
                        page=page_num,
                        part=part_name,
                        part_number=part_number,
                        part_title=part_title,
                        item_number=f"{parent_num}a",
                        parent_item=parent_num,
                        extraction_method="sequential",
                        extraction_iteration=self.iteration,
                        raw_field_name=line
                    )
                    sub_items.append(sub_field)
                    expected_idx += 1
                    matched = True
            
            if not matched and consecutive_empty == 0:
                # No more sub-items found
                break
            
            i += 1
        
        has_subitems = len(sub_items) > 0
        return has_subitems, sub_items
    
    def _determine_field_type_sequential(self, label: str, lines: List[str], current_index: int) -> str:
        """Determine field type based on exact label from PDF"""
        label_lower = label.lower()
        
        # Specific field patterns
        if "alien registration number" in label_lower or "a-number" in label_lower:
            return "number"
        
        if any(date_word in label_lower for date_word in ['date', 'birth', 'expir', 'issue']) or "mm/dd/yyyy" in label:
            return "date"
        
        if "signature" in label_lower:
            return "signature"
        
        if "email" in label_lower or "e-mail" in label_lower:
            return "email"
        
        if any(phone_word in label_lower for phone_word in ['phone', 'telephone', 'mobile', 'cell', 'fax']):
            return "phone"
        
        if any(num_word in label_lower for num_word in ['number', 'ssn', 'ein', 'receipt', 'case']):
            return "number"
        
        # Check for yes/no questions
        question_starters = ['are you', 'have you', 'do you', 'is ', 'was ', 'were you', 'did you',
                           'will you', 'would you', 'could you', 'should you', 'may you', 'might you']
        if any(label_lower.startswith(starter) for starter in question_starters):
            return "checkbox"
        
        # Check next line for Yes/No options
        if current_index + 1 < len(lines):
            next_line = lines[current_index + 1].strip().lower()
            if ("yes" in next_line and "no" in next_line) or re.match(r'^\s*(yes|no)\s*$', next_line):
                return "checkbox"
        
        # Check if it's a compound field (has sub-items)
        compound_indicators = [
            ('name', ['legal', 'full', 'your', 'beneficiary', 'petitioner']),
            ('address', ['mailing', 'physical', 'current', 'home', 'foreign']),
            ('information', ['contact', 'personal', 'employment'])
        ]
        
        for field_type, qualifiers in compound_indicators:
            if field_type in label_lower and any(qual in label_lower for qual in qualifiers):
                # Check if next lines have sub-items
                if current_index + 1 < len(lines):
                    for j in range(1, min(4, len(lines) - current_index)):
                        next_line = lines[current_index + j].strip()
                        if re.match(r'^[a-z][\.\)]', next_line):
                            return "group"
        
        return "text"
    
    def _extract_from_all_widgets_sequential(self, form_structure: FormStructure):
        """Extract from widgets while maintaining sequential order"""
        if not self.doc:
            return
        
        # First, collect all widgets with their positions
        all_widgets = []
        
        for page_num, page in enumerate(self.doc):
            try:
                widgets = page.widgets()
                if not widgets:
                    continue
                
                for widget in widgets:
                    if not widget or not hasattr(widget, 'field_name'):
                        continue
                    
                    # Get widget position for ordering
                    rect = widget.rect if hasattr(widget, 'rect') else None
                    y_pos = rect.y0 if rect else 0
                    
                    all_widgets.append({
                        'widget': widget,
                        'page': page_num,
                        'y_position': y_pos,
                        'field_name': widget.field_name
                    })
            except Exception as e:
                self.log(f"Widget extraction error on page {page_num}: {str(e)}", "warning")
        
        # Sort widgets by page and vertical position (top to bottom)
        all_widgets.sort(key=lambda w: (w['page'], -w['y_position']))
        
        # Process widgets in order
        for widget_info in all_widgets:
            widget = widget_info['widget']
            page_num = widget_info['page']
            
            # Extract field info
            field_name = widget.field_name
            
            # Skip if already extracted
            already_exists = False
            for part_fields in form_structure.parts.values():
                if any(f.raw_field_name == field_name for f in part_fields):
                    already_exists = True
                    break
            
            if already_exists:
                continue
            
            # Determine which part this belongs to
            part_name = self._determine_part_from_page(page_num, form_structure)
            
            if not part_name:
                continue
            
            # Create field from widget
            field = self._create_field_from_widget(widget, page_num + 1, part_name)
            
            if field:
                # Check if this field already exists based on item number
                existing = any(f.item_number == field.item_number 
                             for f in form_structure.parts[part_name])
                
                if not existing:
                    form_structure.parts[part_name].append(field)
                    form_structure.total_fields += 1
    
    def _determine_part_from_page(self, page_num: int, form_structure: FormStructure) -> Optional[str]:
        """Determine which part a page belongs to"""
        if page_num >= len(self.page_texts):
            return None
        
        page_text = self.page_texts[page_num]
        
        # Look for part indicator in page
        part_match = re.search(r'Part\s+(\d+)', page_text, re.IGNORECASE)
        if part_match:
            part_num = int(part_match.group(1))
            return f"Part {part_num}"
        
        # Default to Part 1 for first pages
        if page_num == 0:
            return "Part 1"
        
        # Try to use the last known part
        if form_structure.parts:
            return list(form_structure.parts.keys())[-1]
        
        return "Part 1"
    
    def _create_field_from_widget(self, widget, page_num: int, part_name: str) -> Optional[ExtractedField]:
        """Create field from widget data"""
        try:
            field_name = widget.field_name if hasattr(widget, 'field_name') else ""
            if not field_name:
                return None
            
            # Clean field name
            clean_name = re.sub(r'topmostSubform\[0\]\.', '', field_name)
            clean_name = re.sub(r'form1\[0\]\.', '', clean_name)
            clean_name = re.sub(r'\[0\]', '', clean_name)
            
            # Extract item number from field name
            item_match = re.search(r'(\d+)([a-z])?', clean_name)
            item_number = ""
            if item_match:
                item_number = item_match.group(0)
            
            # Determine field type
            widget_type = widget.field_type if hasattr(widget, 'field_type') else 4
            type_map = {
                2: "checkbox",
                3: "radio",
                4: "text",
                5: "dropdown",
                7: "signature"
            }
            field_type = type_map.get(widget_type, "text")
            
            # Generate label from field name
            label = self._generate_label_from_widget_name(clean_name)
            
            # Extract part number
            part_match = re.search(r'Part\s+(\d+)', part_name)
            part_number = int(part_match.group(1)) if part_match else 1
            
            field = ExtractedField(
                name=clean_name[:50],
                label=label,
                type=field_type,
                page=page_num,
                part=part_name,
                part_number=part_number,
                item_number=item_number,
                raw_field_name=field_name,
                extraction_method="widget",
                extraction_confidence=0.8,
                extraction_iteration=self.iteration
            )
            
            return field
            
        except Exception as e:
            self.log(f"Error creating field from widget: {str(e)}", "warning")
            return None
    
    def _generate_label_from_widget_name(self, name: str) -> str:
        """Generate human-readable label from widget name"""
        # Remove common prefixes
        label = re.sub(r'(field|text|check|box|button)\d*', '', name, flags=re.IGNORECASE)
        
        # Convert camelCase to spaces
        label = re.sub(r'([a-z])([A-Z])', r'\1 \2', label)
        
        # Replace underscores and dashes
        label = label.replace('_', ' ').replace('-', ' ')
        
        # Common replacements
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
        
        label_lower = label.lower()
        for abbr, full in replacements.items():
            if abbr in label_lower:
                return full
        
        # Capitalize words
        return ' '.join(word.capitalize() for word in label.split() if word)
    
    def _validate_extraction_sequence(self, form_structure: FormStructure) -> Dict[str, Any]:
        """Validate that extraction maintains proper sequence"""
        validation_results = {
            "sequence_errors": [],
            "missing_items": [],
            "duplicate_items": [],
            "out_of_order": []
        }
        
        for part_name, fields in form_structure.parts.items():
            # Extract part number
            part_match = re.search(r'Part\s+(\d+)', part_name)
            if not part_match:
                continue
            
            # Group fields by item number (main items only)
            main_items = {}
            sub_items_by_parent = defaultdict(list)
            
            for field in fields:
                if not field.item_number:
                    continue
                
                if field.parent_item:
                    sub_items_by_parent[field.parent_item].append(field)
                else:
                    # Main item
                    item_num = int(re.match(r'^(\d+)', field.item_number).group(1))
                    main_items[item_num] = field
            
            # Check main item sequence
            if main_items:
                sorted_nums = sorted(main_items.keys())
                expected_num = 1
                
                for actual_num in sorted_nums:
                    if actual_num != expected_num:
                        if actual_num > expected_num:
                            # Missing items
                            for missing in range(expected_num, actual_num):
                                validation_results["missing_items"].append({
                                    "part": part_name,
                                    "item": str(missing),
                                    "after": str(expected_num - 1) if expected_num > 1 else "start"
                                })
                        else:
                            # Out of order (shouldn't happen with proper sorting)
                            validation_results["out_of_order"].append({
                                "part": part_name,
                                "item": str(actual_num),
                                "expected_position": expected_num
                            })
                    
                    expected_num = actual_num + 1
            
            # Check sub-item sequences
            for parent_num, sub_fields in sub_items_by_parent.items():
                sorted_subs = sorted(sub_fields, key=lambda f: natural_sort_item_number(f.item_number))
                expected_letters = 'abcdefghijklmnopqrstuvwxyz'
                
                for i, field in enumerate(sorted_subs):
                    if i < len(expected_letters):
                        expected_item = f"{parent_num}{expected_letters[i]}"
                        if field.item_number != expected_item:
                            validation_results["sequence_errors"].append({
                                "part": part_name,
                                "found": field.item_number,
                                "expected": expected_item
                            })
        
        return validation_results
    
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
            'G-28': 'Notice of Entry of Appearance as Attorney',
            'I-90': 'Application to Replace Permanent Resident Card'
        }
        
        form_info = {"number": "Unknown", "title": "Unknown Form", "edition": ""}
        
        for form_num, title in form_mapping.items():
            if form_num in first_page_text:
                form_info["number"] = form_num
                form_info["title"] = title
                break
        
        # Look for edition
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
            },
            "G-28": {
                "parts": ["Part 1", "Part 2", "Part 3", "Part 4", "Part 5", "Part 6"],
                "min_fields_per_part": {}
            },
            "I-90": {
                "parts": ["Part 1", "Part 2", "Part 3", "Part 4", "Part 5", "Part 6", "Part 7"],
                "min_fields_per_part": {}
            }
        }
        
        if form_structure.form_number in expected_structures:
            exp = expected_structures[form_structure.form_number]
            form_structure.expected_parts = exp["parts"]
            form_structure.expected_fields_per_part = exp.get("min_fields_per_part", {})
    
    def _handle_extraction_feedback(self, form_structure: FormStructure, 
                                  feedback: ValidationFeedback, use_ai: bool) -> FormStructure:
        """Handle specific feedback from validator"""
        self.log("Processing validator feedback...", "feedback")
        
        # Target missing parts
        if feedback.missing_parts:
            self.log(f"Searching for {len(feedback.missing_parts)} missing parts", "warning")
            for missing_part in feedback.missing_parts:
                self._search_for_specific_part(form_structure, missing_part)
        
        # Fix sequence errors
        if feedback.sequence_errors:
            self.log(f"Fixing {len(feedback.sequence_errors)} sequence errors", "warning")
            # Re-run sequential extraction with more careful processing
            self._sequential_extraction_primary(form_structure)
        
        # Recalculate totals
        form_structure.total_fields = sum(len(fields) for fields in form_structure.parts.values())
        
        # Ensure proper ordering
        form_structure.reorder_parts()
        
        return form_structure
    
    def _search_for_specific_part(self, form_structure: FormStructure, missing_part: Dict):
        """Search for a specific missing part"""
        part_num = missing_part.get('number', 0)
        part_name = missing_part.get('name', f'Part {part_num}')
        
        self.log(f"Targeted search for {part_name}", "info")
        
        # Search all pages for this part
        for page_num, page_text in enumerate(self.page_texts):
            if re.search(rf'Part\s+{part_num}\b', page_text, re.IGNORECASE):
                self.log(f"Found {part_name} on page {page_num + 1}", "success")
                
                # Re-extract this specific part
                lines = page_text.split('\n')
                for i, line in enumerate(lines):
                    if re.search(rf'Part\s+{part_num}\b', line, re.IGNORECASE):
                        # Process from this point
                        self._extract_part_from_position(
                            form_structure, lines, i, page_num, part_num, part_name
                        )
                        break
                break
    
    def _extract_part_from_position(self, form_structure: FormStructure, lines: List[str], 
                                  start_pos: int, page_num: int, part_num: int, part_name: str):
        """Extract a specific part starting from a position"""
        if part_name not in form_structure.parts:
            form_structure.parts[part_name] = []
        
        # Get part title
        part_title = ""
        if start_pos + 1 < len(lines):
            next_line = lines[start_pos + 1].strip()
            if next_line and not re.match(r'^\d+\.', next_line):
                part_title = next_line
        
        # Extract fields from this part
        i = start_pos + 1
        while i < len(lines):
            line = lines[i].strip()
            
            # Stop at next part
            if re.match(r'Part\s+\d+', line, re.IGNORECASE) and not re.search(rf'Part\s+{part_num}\b', line):
                break
            
            # Extract fields
            field_match = re.match(r'^(\d+)\.\s+(.+?)$', line)
            if field_match:
                item_number = field_match.group(1)
                full_label = field_match.group(2).strip()
                
                field = ExtractedField(
                    name=f"field_{item_number}",
                    label=full_label,
                    type=self._determine_field_type_sequential(full_label, lines, i),
                    page=page_num + 1,
                    part=part_name,
                    part_number=part_num,
                    part_title=part_title,
                    item_number=item_number,
                    extraction_method="feedback",
                    extraction_iteration=self.iteration
                )
                
                form_structure.parts[part_name].append(field)
                form_structure.total_fields += 1
            
            i += 1
    
    def _ai_fill_missing_fields(self, form_structure: FormStructure):
        """Use AI to identify obvious missing fields only"""
        if not self.client or form_structure.total_fields > 100:
            return
        
        try:
            # Only check for very obvious missing fields
            prompt = f"""
            I have extracted fields from form {form_structure.form_number}.
            I found {form_structure.total_fields} fields across {len(form_structure.parts)} parts.
            
            Are there any CRITICAL missing fields that every {form_structure.form_number} form must have?
            Only list fields that are absolutely required and obviously missing.
            
            Current parts found: {', '.join(form_structure.parts.keys())}
            
            Return JSON: {{"missing_critical_fields": ["field1", "field2"]}}
            """
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert on USCIS forms."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=500
            )
            
            # Process response if needed
            # But generally we rely on sequential extraction
            
        except Exception as e:
            self.log(f"AI fill error: {str(e)}", "warning")

# Enhanced JSON Mapping Agent
class JSONMappingAgent(Agent):
    """Maps extracted fields to JSON structure"""
    
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
            # I-539 specific mappings
            "alien registration number (a-number) (if any)": [("beneficiary", "Beneficiary.alienNumber")],
            "your full legal name": [("beneficiary", "Beneficiary")],  # Group field
            "family name (last name)": [("beneficiary", "Beneficiary.beneficiaryLastName")],
            "given name (first name)": [("beneficiary", "Beneficiary.beneficiaryFirstName")],
            "middle name (if applicable)": [("beneficiary", "Beneficiary.beneficiaryMiddleName")],
            
            # Item number mappings
            "1a": [("beneficiary", "Beneficiary.beneficiaryLastName")],
            "1b": [("beneficiary", "Beneficiary.beneficiaryFirstName")],
            "1c": [("beneficiary", "Beneficiary.beneficiaryMiddleName")],
            "2": [("beneficiary", "Beneficiary.alienNumber")],
            
            # Common field mappings
            "date of birth": [("beneficiary", "Beneficiary.beneficiaryDateOfBirth")],
            "country of birth": [("beneficiary", "Beneficiary.beneficiaryCountryOfBirth")],
            "country of citizenship": [("beneficiary", "Beneficiary.beneficiaryCitizenOfCountry")],
            "gender": [("beneficiary", "Beneficiary.beneficiaryGender")],
            "marital status": [("beneficiary", "Beneficiary.maritalStatus")],
            "ssn": [("beneficiary", "Beneficiary.beneficiarySsn")],
            "social security number": [("beneficiary", "Beneficiary.beneficiarySsn")],
            "u.s. social security number": [("beneficiary", "Beneficiary.beneficiarySsn")],
            
            # Address mappings
            "street number and name": [("beneficiary", "HomeAddress.addressStreet")],
            "city or town": [("beneficiary", "HomeAddress.addressCity")],
            "state": [("beneficiary", "HomeAddress.addressState")],
            "zip code": [("beneficiary", "HomeAddress.addressZip")],
            
            # Contact info
            "email": [("beneficiary", "Beneficiary.beneficiaryPrimaryEmailAddress")],
            "email address": [("beneficiary", "Beneficiary.beneficiaryPrimaryEmailAddress")],
            "daytime telephone number": [("beneficiary", "Beneficiary.beneficiaryCellNumber")],
            "mobile telephone number": [("beneficiary", "Beneficiary.beneficiaryCellNumber")],
            
            # Attorney mappings
            "attorney state bar number": [("attorney", "attorneyInfo.stateBarNumber")],
            "bar number": [("attorney", "attorneyInfo.stateBarNumber")],
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
                    
                    # 1. Try exact label matching (with full label)
                    if field.label:
                        label_lower = field.label.lower()
                        
                        if label_lower in self.enhanced_mappings:
                            candidates = self.enhanced_mappings[label_lower]
                            if candidates:
                                obj_name, path = candidates[0]
                                field.json_path = f"{obj_name}.{path}"
                                field.db_path = self._convert_to_db_path(obj_name, path)
                                mapped = True
                                total_mapped += 1
                    
                    # 2. Try item number mapping
                    if not mapped and field.item_number:
                        if field.item_number.lower() in self.enhanced_mappings:
                            candidates = self.enhanced_mappings[field.item_number.lower()]
                            if candidates:
                                obj_name, path = candidates[0]
                                field.json_path = f"{obj_name}.{path}"
                                field.db_path = self._convert_to_db_path(obj_name, path)
                                mapped = True
                                total_mapped += 1
                    
                    # 3. Try fuzzy matching on key parts of label
                    if not mapped and field.label:
                        # Extract key terms from label
                        key_terms = self._extract_key_terms(field.label)
                        for term in key_terms:
                            if term in self.enhanced_mappings:
                                candidates = self.enhanced_mappings[term]
                                if candidates:
                                    obj_name, path = candidates[0]
                                    field.json_path = f"{obj_name}.{path}"
                                    field.db_path = self._convert_to_db_path(obj_name, path)
                                    field.extraction_confidence = 0.8
                                    mapped = True
                                    total_mapped += 1
                                    break
            
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
    
    def _extract_key_terms(self, label: str) -> List[str]:
        """Extract key terms from a label for mapping"""
        terms = []
        label_lower = label.lower()
        
        # Remove common words
        stop_words = ['the', 'a', 'an', 'of', 'in', 'if', 'any', 'your', 'or']
        
        # Extract terms in parentheses
        paren_match = re.findall(r'\((.*?)\)', label_lower)
        terms.extend(paren_match)
        
        # Remove parenthetical content for main parsing
        clean_label = re.sub(r'\(.*?\)', '', label_lower).strip()
        
        # Split and filter
        words = clean_label.split()
        terms.extend([w for w in words if w not in stop_words and len(w) > 2])
        
        # Try the full clean label
        if clean_label:
            terms.append(clean_label)
        
        return terms
    
    def _convert_to_db_path(self, obj_name: str, json_path: str) -> str:
        """Convert JSON path to database path format"""
        # Remove nested object references
        parts = json_path.split('.')
        
        # Categorize fields
        categories = {
            'PersonalInfo': ['FirstName', 'LastName', 'MiddleName', 'DateOfBirth', 
                           'Gender', 'Ssn', 'AlienNumber'],
            'ContactInfo': ['Email', 'Phone', 'Cell', 'Mobile', 'Work'],
            'Address': ['Street', 'City', 'State', 'Zip', 'Country'],
        }
        
        # Find appropriate category
        category = "PersonalInfo"  # default
        field_name = parts[-1] if parts else json_path
        
        for cat, keywords in categories.items():
            if any(keyword.lower() in field_name.lower() for keyword in keywords):
                category = cat
                break
        
        return f"{obj_name}.{category}.{field_name}"

# Enhanced Validation Agent
class ValidationAgent(Agent):
    """Validates extraction with sequence checking"""
    
    def __init__(self):
        super().__init__("Validation Agent", "Field Validation & Sequence Checking")
        self.json_structures = load_json_structures()
        
        self.expected_structures = {
            "I-539": {
                "parts": 8,
                "min_fields": 100,
                "required_parts": ["Part 1", "Part 2", "Part 3", "Part 4", "Part 5", "Part 6", "Part 7", "Part 8"],
                "min_fields_per_part": {
                    "Part 1": 15,
                    "Part 2": 20,
                    "Part 3": 30,
                    "Part 4": 10,
                    "Part 5": 5,
                    "Part 6": 15,
                    "Part 7": 5,
                    "Part 8": 5
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
            },
            "G-28": {
                "parts": 6,
                "min_fields": 30,
                "required_parts": ["Part 1", "Part 2", "Part 3", "Part 4", "Part 5", "Part 6"]
            },
            "I-90": {
                "parts": 7,
                "min_fields": 50,
                "required_parts": ["Part 1", "Part 2", "Part 3", "Part 4", "Part 5", "Part 6", "Part 7"]
            }
        }
    
    def execute(self, form_structure: FormStructure, generate_feedback: bool = True) -> Tuple[FormStructure, Optional[ValidationFeedback]]:
        """Validate form structure and field sequences"""
        self.status = "active"
        self.iteration += 1
        self.log(f"Validating {form_structure.form_number} (Iteration {self.iteration})...", "info")
        
        feedback = ValidationFeedback() if generate_feedback else None
        
        try:
            # Get expected structure
            expected = self.expected_structures.get(form_structure.form_number, {})
            
            # 1. Check part ordering and sequence
            part_issues = self._check_part_sequence(form_structure, feedback)
            
            # 2. Check field sequences within parts
            field_sequence_issues = self._check_field_sequences(form_structure, feedback)
            
            # 3. Check for missing parts
            if expected and "required_parts" in expected:
                missing_parts = self._check_missing_parts(form_structure, expected, feedback)
            
            # 4. Check part completeness
            if expected and "min_fields_per_part" in expected:
                incomplete_parts = self._check_incomplete_parts(form_structure, expected, feedback)
            
            # 5. Validate specific field requirements
            field_issues = self._validate_required_fields(form_structure, feedback)
            
            # Calculate validation score
            form_structure.validated_fields = sum(
                1 for fields in form_structure.parts.values() 
                for f in fields if f.item_number  # Has proper item number
            )
            
            if form_structure.total_fields > 0:
                base_score = form_structure.validated_fields / form_structure.total_fields
                
                # Penalties
                penalty = 0
                penalty += min(0.2, part_issues * 0.05)
                penalty += min(0.2, field_sequence_issues * 0.02)
                penalty += min(0.1, len(missing_parts) * 0.02) if 'missing_parts' in locals() else 0
                penalty += min(0.1, field_issues * 0.01)
                
                form_structure.validation_score = max(0, base_score - penalty)
            else:
                form_structure.validation_score = 0.0
            
            # Determine if retry needed
            if feedback:
                critical_issues = part_issues > 2 or field_sequence_issues > 5
                if critical_issues and form_structure.extraction_iterations < 3:
                    feedback.needs_retry = True
                    feedback.severity = "error"
                    feedback.suggestions.append("Re-run sequential extraction with stricter ordering")
            
            # Summary
            self.log("=== Validation Summary ===", "info")
            self.log(f"Parts found: {len(form_structure.parts)}/{expected.get('parts', '?')}", "info")
            if part_issues > 0:
                self.log(f"Part sequence issues: {part_issues}", "warning")
            if field_sequence_issues > 0:
                self.log(f"Field sequence issues: {field_sequence_issues}", "warning")
            self.log(f"Total fields: {form_structure.total_fields}/{expected.get('min_fields', '?')}", "info")
            self.log(f"Validation score: {form_structure.validation_score:.0%}", "info")
            
            form_structure.is_validated = True
            form_structure.add_agent_log(self.name, 
                f"Validation complete. Score: {form_structure.validation_score:.0%}")
            
            self.status = "completed"
            return form_structure, feedback
            
        except Exception as e:
            self.log(f"Validation failed: {str(e)}", "error")
            self.status = "error"
            return form_structure, feedback
    
    def _check_part_sequence(self, form_structure: FormStructure, 
                           feedback: Optional[ValidationFeedback]) -> int:
        """Check if parts are in proper sequence"""
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
                            self.log(f"⚠️ Missing Part {missing}", "warning")
                            if feedback:
                                feedback.missing_parts.append({
                                    "number": missing,
                                    "name": f"Part {missing}",
                                    "expected_fields": 10
                                })
                    
                    if feedback:
                        feedback.sequence_errors.append({
                            "type": "part",
                            "expected": expected_num,
                            "found": actual_num
                        })
                
                expected_num = actual_num + 1
        
        return issues
    
    def _check_field_sequences(self, form_structure: FormStructure, 
                             feedback: Optional[ValidationFeedback]) -> int:
        """Check if fields within each part are in proper sequence"""
        total_issues = 0
        
        for part_name, fields in form_structure.parts.items():
            # Group by main items
            main_items = {}
            sub_items_by_parent = defaultdict(list)
            
            for field in fields:
                if not field.item_number:
                    continue
                
                if field.parent_item:
                    sub_items_by_parent[field.parent_item].append(field)
                else:
                    item_num = int(re.match(r'^(\d+)', field.item_number).group(1))
                    main_items[item_num] = field
            
            # Check main item sequence
            if main_items:
                sorted_nums = sorted(main_items.keys())
                expected = 1
                
                for actual in sorted_nums:
                    if actual != expected:
                        total_issues += 1
                        self.log(f"⚠️ {part_name}: Expected item {expected}, found {actual}", "warning")
                        
                        if feedback and actual > expected:
                            for missing in range(expected, actual):
                                feedback.field_issues.append({
                                    "part": part_name,
                                    "issue": f"Missing item {missing}",
                                    "severity": "high"
                                })
                    
                    expected = actual + 1
            
            # Check sub-item sequences
            for parent_num, sub_fields in sub_items_by_parent.items():
                sorted_subs = sorted(sub_fields, key=lambda f: natural_sort_item_number(f.item_number))
                expected_letters = 'abcdefghijklmnopqrstuvwxyz'
                
                for i, field in enumerate(sorted_subs):
                    if i < len(expected_letters):
                        expected_item = f"{parent_num}{expected_letters[i]}"
                        if field.item_number != expected_item:
                            total_issues += 1
                            self.log(f"⚠️ Sub-item issue: Expected {expected_item}, found {field.item_number}", "warning")
                            
                            if feedback:
                                feedback.sequence_errors.append({
                                    "type": "sub-item",
                                    "expected": expected_item,
                                    "found": field.item_number
                                })
        
        return total_issues
    
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
    
    def _validate_required_fields(self, form_structure: FormStructure, 
                                 feedback: Optional[ValidationFeedback]) -> int:
        """Validate that required fields are present"""
        issues = 0
        
        # Check for essential fields based on form type
        if form_structure.form_number == "I-539":
            # Check Part 1 has name fields
            part1_fields = form_structure.parts.get("Part 1", [])
            name_items = [f for f in part1_fields if f.item_number in ["1", "1a", "1b", "1c"]]
            if len(name_items) < 4:  # Should have item 1 and 1a, 1b, 1c
                issues += 1
                self.log("⚠️ Part 1 missing complete name fields (1, 1a, 1b, 1c)", "warning")
                
                if feedback:
                    feedback.field_issues.append({
                        "part": "Part 1",
                        "issue": "Incomplete name field structure",
                        "severity": "high"
                    })
            
            # Check for A-Number field
            a_number_field = next((f for f in part1_fields if f.item_number == "2"), None)
            if not a_number_field:
                issues += 1
                self.log("⚠️ Part 1 missing A-Number field (item 2)", "warning")
            elif "alien registration number" not in a_number_field.label.lower():
                issues += 1
                self.log("⚠️ Item 2 label incorrect (should be 'Alien Registration Number...')", "warning")
        
        # Similar checks for other forms...
        
        return issues

# Coordinator Agent
class CoordinatorAgent(Agent):
    """Coordinates collaboration between agents"""
    
    def __init__(self):
        super().__init__("Coordinator", "Agent Orchestration")
        self.max_iterations = 3
        
    def execute(self, pdf_file, use_ai: bool = True, auto_validate: bool = True, 
               auto_map: bool = True) -> Optional[FormStructure]:
        """Orchestrate agent collaboration"""
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
            self.log("📊 Phase 1: Sequential Extraction", "info")
            form_structure = research_agent.execute(pdf_file, use_ai)
            
            if not form_structure:
                self.log("Initial extraction failed", "error")
                return None
            
            # Show initial results
            st.info(f"Initial extraction: {form_structure.total_fields} fields in {len(form_structure.parts)} parts")
            
            # Validation and feedback loop
            while iteration < self.max_iterations and auto_validate:
                iteration += 1
                self.log(f"📊 Phase 2: Validation Loop (Iteration {iteration})", "info")
                
                # Validate
                form_structure, feedback = validation_agent.execute(form_structure, generate_feedback=True)
                
                # Check if retry needed
                if feedback and feedback.needs_retry and iteration < self.max_iterations:
                    self.log(f"Validation identified issues requiring re-extraction", "feedback")
                    
                    # Display feedback
                    if feedback.sequence_errors:
                        st.warning(f"Found {len(feedback.sequence_errors)} sequence errors")
                    if feedback.missing_parts:
                        st.warning(f"Missing {len(feedback.missing_parts)} parts")
                    
                    # Re-extract with feedback
                    form_structure = research_agent.execute(
                        None,  # No file needed
                        use_ai,
                        form_structure,
                        feedback
                    )
                else:
                    # No retry needed
                    break
            
            # Mapping phase
            if auto_map and mapping_agent and form_structure:
                self.log("📊 Phase 3: JSON Structure Mapping", "info")
                form_structure = mapping_agent.execute(form_structure)
            
            # Final results
            if form_structure:
                self.log("=== Final Results ===", "success")
                self.log(f"Total iterations: {iteration}", "info")
                self.log(f"Parts found: {len(form_structure.parts)}", "info")
                self.log(f"Fields extracted: {form_structure.total_fields}", "info")
                self.log(f"Validation score: {form_structure.validation_score:.0%}", "info")
                
                # Check for sequence warnings
                validation_results = research_agent._validate_extraction_sequence(form_structure)
                if validation_results["missing_items"]:
                    st.markdown('<div class="sequence-warning">⚠️ Some items may be missing from the sequence. Review the extraction carefully.</div>', 
                              unsafe_allow_html=True)
            
            self.status = "completed"
            return form_structure
            
        finally:
            # Cleanup
            if hasattr(research_agent, 'cleanup'):
                research_agent.cleanup()

# Field rendering functions
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
            # Display mode - show exact label from PDF
            if field.item_number:
                st.markdown(f'**{field.item_number}.** {field.label}')
            else:
                st.markdown(f'**{field.label}**')
            
            # Type badge
            st.caption(f"Type: {field.type}")
    
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
                        existing_nums.sort()
                        next_num = existing_nums[-1] + 1 if existing_nums else 1
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
    """Generate enhanced JSON with proper sequence"""
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
            # Sort fields by item number
            quest_fields.sort(key=lambda f: natural_sort_item_number(f.item_number if f.item_number else "999"))
            
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
            
            # Process main items with their sub-items
            all_items = {}
            for field in standalone_fields:
                if field.item_number and field.item_number.isdigit():
                    all_items[int(field.item_number)] = {
                        'main': field,
                        'subs': sorted(item_groups.get(field.item_number, []), 
                                     key=lambda f: natural_sort_item_number(f.item_number or ""))
                    }
            
            # Add items in numerical order
            for item_num in sorted(all_items.keys()):
                item_data = all_items[item_num]
                main_field = item_data['main']
                sub_fields = item_data['subs']
                
                # Add main field
                if sub_fields:
                    # This is a group with sub-items
                    controls.append({
                        "name": f"group_{main_field.item_number}",
                        "label": f"{main_field.item_number}. {main_field.label}",
                        "type": "group",
                        "style": {"col": "12"}
                    })
                    
                    # Add sub-fields
                    for sub_field in sub_fields:
                        control = {
                            "name": sub_field.name,
                            "label": f"{sub_field.item_number}. {sub_field.label}",
                            "type": sub_field.type if sub_field.type != "checkbox" else "colorSwitch",
                            "validators": {"required": False},
                            "style": {"col": "6", "indent": True}
                        }
                        controls.append(control)
                else:
                    # Standalone field
                    control = {
                        "name": main_field.name,
                        "label": f"{main_field.item_number}. {main_field.label}",
                        "type": main_field.type if main_field.type != "checkbox" else "colorSwitch",
                        "validators": {"required": False},
                        "style": {"col": "12" if main_field.type == "checkbox" else "7"}
                    }
                    controls.append(control)
    
    return json.dumps({"controls": controls}, indent=2)

# Main Application
def main():
    st.markdown('<div class="main-header"><h1>🤖 Smart USCIS Form Reader</h1><p>Sequential Extraction with Exact PDF Structure</p></div>', 
               unsafe_allow_html=True)
    
    # Initialize session state
    if 'form_structure' not in st.session_state:
        st.session_state.form_structure = None
    if 'agents' not in st.session_state:
        st.session_state.agents = {}
    if 'json_structures' not in st.session_state:
        st.session_state.json_structures = load_json_structures()
    
    # Check dependencies
    if not PYMUPDF_AVAILABLE:
        st.error("❌ PyMuPDF library not installed. Please install with: pip install PyMuPDF")
        return
    
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
            
            # Sequence check
            if hasattr(form, 'parts'):
                st.markdown("### 📋 Sequence Check")
                validation_results = ResearchAgent()._validate_extraction_sequence(form)
                if validation_results["missing_items"]:
                    st.warning(f"Missing {len(validation_results['missing_items'])} items")
                else:
                    st.success("✅ Sequence complete")
    
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
                    
                    with st.spinner("Processing with sequential extraction..."):
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
                                st.markdown("### Parts Extracted (in sequence):")
                                
                                for part_name, fields in form_structure.parts.items():
                                    # Count sub-items
                                    main_items = sum(1 for f in fields if not f.parent_item)
                                    sub_items = sum(1 for f in fields if f.parent_item)
                                    st.markdown(f"**{part_name}**: {len(fields)} fields ({main_items} main, {sub_items} sub-items)")
                                
                                # Sample extraction
                                st.markdown("### Sample Field Extraction:")
                                for part_name, fields in form_structure.parts.items():
                                    if part_name == "Part 1" and fields:
                                        st.markdown(f"**From {part_name}:**")
                                        for field in fields[:5]:  # Show first 5
                                            if field.item_number:
                                                st.markdown(f"- **{field.item_number}.** {field.label}")
                                            else:
                                                st.markdown(f"- {field.label}")
                                        break
    
    with tabs[1]:
        form_structure = st.session_state.get('form_structure')
        if form_structure and form_structure.parts:
            st.markdown("## 🎯 Field Mapping to JSON Structure")
            
            # Natural sort for parts
            def natural_sort_key(part_name):
                match = re.search(r'Part\s+(\d+)', part_name)
                if match:
                    return int(match.group(1))
                return 999
            
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
                col1, col2, col3, col4 = st.columns(4)
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
                
                # Display fields in sequence
                sorted_fields = sorted(fields, key=lambda f: natural_sort_item_number(f.item_number if f.item_number else "999"))
                
                # Group by parent item
                current_parent = None
                for idx, field in enumerate(sorted_fields):
                    # Start new group for main items
                    if not field.parent_item and field.item_number and field.item_number.isdigit():
                        if current_parent is not None:
                            st.markdown('</div>', unsafe_allow_html=True)
                        
                        # Check if this item has sub-items
                        has_subs = any(f.parent_item == field.item_number for f in fields)
                        if has_subs:
                            st.markdown('<div class="item-group">', unsafe_allow_html=True)
                            current_parent = field.item_number
                    
                    render_field_card_enhanced(field, idx, selected_part, form_structure)
                
                # Close last group if needed
                if current_parent is not None:
                    st.markdown('</div>', unsafe_allow_html=True)
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
            
            # Export summary
            st.markdown("### 📊 Export Summary")
            
            # Count mappings
            mapping_counts = defaultdict(int)
            unmapped_count = 0
            questionnaire_count = 0
            
            for part_name, fields in form_structure.parts.items():
                for field in fields:
                    if field.json_path:
                        obj_type = field.json_path.split('.')[0]
                        mapping_counts[obj_type] += 1
                    elif field.is_questionnaire:
                        questionnaire_count += 1
                    else:
                        unmapped_count += 1
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("**Mapped Fields:**")
                for obj_type, count in sorted(mapping_counts.items()):
                    st.caption(f"{obj_type.capitalize()}: {count} fields")
            
            with col2:
                st.markdown("**Questionnaire Fields:**")
                st.caption(f"{questionnaire_count} fields")
            
            with col3:
                st.markdown("**Unmapped Fields:**")
                st.caption(f"{unmapped_count} fields")
    
    with tabs[3]:
        form_structure = st.session_state.get('form_structure')
        if form_structure and form_structure.agent_logs:
            st.markdown("## 📊 Agent Activity Logs")
            
            for agent_name, logs in form_structure.agent_logs.items():
                with st.expander(f"🤖 {agent_name}", expanded=True):
                    for log in logs:
                        st.caption(log)
                    
            # Validation details
            if hasattr(form_structure, 'validation_issues') and form_structure.validation_issues:
                st.markdown("### ⚠️ Validation Issues")
                for issue in form_structure.validation_issues:
                    st.warning(issue)
        else:
            st.info("No agent logs available yet")

if __name__ == "__main__":
    main()
