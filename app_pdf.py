#!/usr/bin/env python3
"""
Enhanced Smart USCIS Form Reader with Recursive Extraction and Validation Loop
Correctly extracts fields with proper hierarchy and validation
"""

import os
import json
import re
import time
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Set, Union
from dataclasses import dataclass, field, asdict
from collections import defaultdict, OrderedDict
from abc import ABC, abstractmethod
import streamlit as st

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
    page_title="Enhanced USCIS Form Reader - Recursive Extraction",
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
    .extraction-status {
        background: #f0f4f8;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
    }
    .field-hierarchy {
        margin-left: 20px;
        border-left: 2px solid #e0e0e0;
        padding-left: 10px;
    }
    .field-item {
        padding: 0.5rem;
        margin: 0.25rem 0;
        background: white;
        border-radius: 4px;
        border: 1px solid #e0e0e0;
    }
    .field-main {
        font-weight: bold;
        background: #e3f2fd;
    }
    .field-sub {
        margin-left: 20px;
        font-size: 0.95em;
    }
    .validation-pass {
        color: #4caf50;
        font-weight: bold;
    }
    .validation-fail {
        color: #f44336;
        font-weight: bold;
    }
    .agent-status {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.85em;
        margin: 0.25rem;
    }
    .status-active {
        background: #4caf50;
        color: white;
    }
    .status-waiting {
        background: #ff9800;
        color: white;
    }
    .status-error {
        background: #f44336;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

@dataclass
class FieldItem:
    """Represents a single field item with proper hierarchy"""
    number: str  # e.g., "1", "1a", "2"
    label: str   # e.g., "Your Full Legal Name", "Family Name (Last Name)"
    type: str    # e.g., "text", "checkbox", "group"
    value: str = ""
    
    # Hierarchy
    parent_number: Optional[str] = None  # e.g., "1" for "1a"
    children: List['FieldItem'] = field(default_factory=list)
    level: int = 0  # 0 for main items, 1 for sub-items, etc.
    
    # Location
    page: int = 1
    line_number: int = 0
    
    # Extraction metadata
    raw_text: str = ""
    confidence: float = 1.0
    extraction_method: str = ""  # "pattern", "structure", "ai"
    
    # Validation
    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)
    
    def get_full_number(self) -> str:
        """Get full hierarchical number"""
        return self.number
    
    def add_child(self, child: 'FieldItem'):
        """Add a child field"""
        child.parent_number = self.number
        child.level = self.level + 1
        self.children.append(child)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary including children"""
        result = {
            "number": self.number,
            "label": self.label,
            "type": self.type,
            "value": self.value,
            "level": self.level,
            "children": [child.to_dict() for child in self.children]
        }
        return result

@dataclass
class PartStructure:
    """Represents a part with its fields"""
    number: int  # 1, 2, 3, etc.
    title: str   # e.g., "Information About You"
    fields: List[FieldItem] = field(default_factory=list)
    
    # Validation
    is_complete: bool = False
    expected_fields: int = 0
    validation_score: float = 0.0
    
    def add_field(self, field: FieldItem):
        """Add a field to this part"""
        self.fields.append(field)
    
    def get_field_by_number(self, number: str) -> Optional[FieldItem]:
        """Get field by its number"""
        for field in self.fields:
            if field.number == number:
                return field
            # Check children recursively
            for child in field.children:
                if child.number == number:
                    return child
        return None
    
    def validate_sequence(self) -> List[str]:
        """Validate field sequence"""
        errors = []
        main_numbers = []
        
        # Get all main field numbers
        for field in self.fields:
            if not field.parent_number and field.number.isdigit():
                main_numbers.append(int(field.number))
        
        # Check sequence
        main_numbers.sort()
        expected = 1
        for num in main_numbers:
            if num != expected:
                if num > expected:
                    for missing in range(expected, num):
                        errors.append(f"Missing field {missing}")
                expected = num + 1
        
        return errors

@dataclass
class FormExtraction:
    """Complete form extraction result"""
    form_number: str  # e.g., "I-539"
    form_title: str
    edition: str = ""
    parts: Dict[int, PartStructure] = field(default_factory=OrderedDict)
    
    # Extraction metadata
    extraction_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    extraction_iterations: int = 0
    
    # Validation
    is_valid: bool = False
    validation_errors: List[str] = field(default_factory=list)
    validation_score: float = 0.0
    
    # Agent logs
    agent_logs: Dict[str, List[str]] = field(default_factory=dict)
    
    def add_part(self, part: PartStructure):
        """Add a part to the form"""
        self.parts[part.number] = part
    
    def get_all_fields(self) -> List[FieldItem]:
        """Get all fields from all parts"""
        all_fields = []
        for part in self.parts.values():
            all_fields.extend(part.fields)
            for field in part.fields:
                all_fields.extend(field.children)
        return all_fields
    
    def to_json(self) -> str:
        """Convert to JSON representation"""
        data = {
            "form_number": self.form_number,
            "form_title": self.form_title,
            "edition": self.edition,
            "extraction_timestamp": self.extraction_timestamp,
            "parts": {}
        }
        
        for part_num, part in self.parts.items():
            data["parts"][f"Part {part_num}"] = {
                "title": part.title,
                "fields": [field.to_dict() for field in part.fields]
            }
        
        return json.dumps(data, indent=2)

# Base Agent
class BaseAgent(ABC):
    """Base class for all agents"""
    
    def __init__(self, name: str):
        self.name = name
        self.status = "waiting"
        self.logs = []
        self.errors = []
    
    def log(self, message: str, level: str = "info"):
        """Log a message"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] {message}"
        self.logs.append((level, log_entry))
        
        # Display in UI
        if 'agent_container' in st.session_state:
            container = st.session_state.agent_container
            with container:
                if level == "error":
                    st.error(f"❌ **{self.name}**: {message}")
                elif level == "success":
                    st.success(f"✅ **{self.name}**: {message}")
                elif level == "warning":
                    st.warning(f"⚠️ **{self.name}**: {message}")
                else:
                    st.info(f"ℹ️ **{self.name}**: {message}")
    
    @abstractmethod
    def process(self, *args, **kwargs):
        """Process method to be implemented by each agent"""
        pass

# Recursive Extraction Agent
class RecursiveExtractionAgent(BaseAgent):
    """Extracts fields recursively with proper hierarchy"""
    
    def __init__(self):
        super().__init__("Recursive Extraction Agent")
        self.patterns = self._compile_patterns()
    
    def _compile_patterns(self):
        """Compile extraction patterns"""
        return {
            'part_header': re.compile(r'^Part\s+(\d+)\.?\s*(.*?)$', re.IGNORECASE),
            'main_field': re.compile(r'^(\d+)\.\s+(.+?)$'),
            'sub_field': re.compile(r'^([a-z])\.\s+(.+?)$', re.IGNORECASE),
            'numbered_sub': re.compile(r'^(\d+)([a-z])\.\s+(.+?)$'),
            'checkbox': re.compile(r'^\s*□\s+(.+?)$'),
            'arrow_field': re.compile(r'^►\s*(.*)$'),
        }
    
    def process(self, pdf_bytes: bytes) -> FormExtraction:
        """Process PDF and extract fields recursively"""
        self.status = "active"
        self.log("Starting recursive extraction...")
        
        try:
            # Open PDF
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            # Identify form
            form_info = self._identify_form(doc)
            extraction = FormExtraction(
                form_number=form_info['number'],
                form_title=form_info['title'],
                edition=form_info.get('edition', '')
            )
            
            # Extract each page
            for page_num in range(len(doc)):
                self._extract_page(doc[page_num], page_num + 1, extraction)
            
            doc.close()
            
            extraction.extraction_iterations = 1
            self.log(f"Extracted {len(extraction.parts)} parts", "success")
            
            return extraction
            
        except Exception as e:
            self.log(f"Extraction failed: {str(e)}", "error")
            raise
    
    def _identify_form(self, doc) -> Dict:
        """Identify form type from first page"""
        first_page_text = doc[0].get_text()
        
        # Look for form number
        form_patterns = [
            (r'Form\s+(I-\d+[A-Z]?)', r'Form\s+I-\d+[A-Z]?\s+(.+?)(?:\n|Department)'),
            (r'Form\s+(N-\d+)', r'Form\s+N-\d+\s+(.+?)(?:\n|Department)'),
            (r'Form\s+(G-\d+)', r'Form\s+G-\d+\s+(.+?)(?:\n|Department)'),
        ]
        
        form_info = {"number": "Unknown", "title": "Unknown Form", "edition": ""}
        
        for num_pattern, title_pattern in form_patterns:
            num_match = re.search(num_pattern, first_page_text)
            if num_match:
                form_info["number"] = num_match.group(1)
                
                title_match = re.search(title_pattern, first_page_text)
                if title_match:
                    form_info["title"] = title_match.group(1).strip()
                break
        
        # Look for edition
        edition_match = re.search(r'Edition\s+(\d{2}/\d{2}/\d{2})', first_page_text)
        if edition_match:
            form_info["edition"] = edition_match.group(1)
        
        return form_info
    
    def _extract_page(self, page, page_num: int, extraction: FormExtraction):
        """Extract fields from a single page"""
        text = page.get_text()
        lines = text.split('\n')
        
        current_part = None
        current_part_num = 0
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            # Check for part header
            part_match = self.patterns['part_header'].match(line)
            if part_match:
                current_part_num = int(part_match.group(1))
                part_title = part_match.group(2).strip()
                
                # Get full title from next line if needed
                if not part_title and i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line and not any(p.match(next_line) for p in self.patterns.values()):
                        part_title = next_line
                        i += 1
                
                current_part = PartStructure(
                    number=current_part_num,
                    title=part_title
                )
                extraction.add_part(current_part)
                self.log(f"Found Part {current_part_num}: {part_title}")
                
                i += 1
                continue
            
            # Skip if no current part
            if not current_part:
                i += 1
                continue
            
            # Extract fields recursively
            field, lines_consumed = self._extract_field_recursive(lines, i, page_num)
            if field:
                current_part.add_field(field)
                i += lines_consumed
            else:
                i += 1
    
    def _extract_field_recursive(self, lines: List[str], start_idx: int, 
                               page_num: int, parent_number: str = "") -> Tuple[Optional[FieldItem], int]:
        """Recursively extract a field and its sub-fields"""
        line = lines[start_idx].strip()
        if not line:
            return None, 1
        
        # Try main field pattern
        main_match = self.patterns['main_field'].match(line)
        if main_match:
            number = main_match.group(1)
            label = main_match.group(2).strip()
            
            field = FieldItem(
                number=number,
                label=label,
                type=self._determine_field_type(label, lines, start_idx),
                page=page_num,
                line_number=start_idx,
                raw_text=line,
                extraction_method="pattern"
            )
            
            # Look for sub-fields
            lines_consumed = 1
            idx = start_idx + 1
            
            # Check if this is a group field with sub-items
            if self._is_group_field(label, lines, start_idx):
                field.type = "group"
                
                # Extract sub-fields
                while idx < len(lines):
                    sub_line = lines[idx].strip()
                    
                    # Check for sub-field patterns
                    sub_field = None
                    
                    # Numbered sub-field (e.g., "1a. Label")
                    numbered_sub_match = self.patterns['numbered_sub'].match(sub_line)
                    if numbered_sub_match and numbered_sub_match.group(1) == number:
                        sub_number = number + numbered_sub_match.group(2)
                        sub_label = numbered_sub_match.group(3)
                        sub_field = FieldItem(
                            number=sub_number,
                            label=sub_label,
                            type=self._determine_field_type(sub_label, lines, idx),
                            page=page_num,
                            line_number=idx,
                            raw_text=sub_line,
                            extraction_method="pattern"
                        )
                    else:
                        # Letter sub-field (e.g., "a. Label")
                        sub_match = self.patterns['sub_field'].match(sub_line)
                        if sub_match:
                            sub_letter = sub_match.group(1)
                            sub_label = sub_match.group(2)
                            sub_field = FieldItem(
                                number=number + sub_letter,
                                label=sub_label,
                                type=self._determine_field_type(sub_label, lines, idx),
                                page=page_num,
                                line_number=idx,
                                raw_text=sub_line,
                                extraction_method="pattern"
                            )
                        elif self._is_field_component(sub_line):
                            # Handle unmarked components (like address fields)
                            sub_field = FieldItem(
                                number=f"{number}_component_{len(field.children) + 1}",
                                label=sub_line,
                                type="text",
                                page=page_num,
                                line_number=idx,
                                raw_text=sub_line,
                                extraction_method="structure"
                            )
                    
                    if sub_field:
                        field.add_child(sub_field)
                        lines_consumed += 1
                        idx += 1
                    else:
                        # Stop if we hit something that's not a sub-field
                        if self.patterns['main_field'].match(sub_line):
                            break
                        elif not sub_line:
                            # Skip empty lines
                            lines_consumed += 1
                            idx += 1
                        else:
                            break
            
            return field, lines_consumed
        
        # Try arrow field pattern (for fields like "► A-")
        arrow_match = self.patterns['arrow_field'].match(line)
        if arrow_match:
            # This is typically a continuation of a previous field
            return None, 1
        
        # Try checkbox pattern
        checkbox_match = self.patterns['checkbox'].match(line)
        if checkbox_match:
            # This might be an option for a previous field
            return None, 1
        
        return None, 1
    
    def _is_group_field(self, label: str, lines: List[str], current_idx: int) -> bool:
        """Determine if a field is a group field with sub-items"""
        label_lower = label.lower()
        
        # Known group fields
        group_keywords = [
            'name', 'legal name', 'full name',
            'address', 'mailing address', 'physical address',
            'information', 'contact information'
        ]
        
        if any(keyword in label_lower for keyword in group_keywords):
            # Check next lines for sub-items
            for i in range(1, min(5, len(lines) - current_idx)):
                next_line = lines[current_idx + i].strip()
                if self.patterns['sub_field'].match(next_line):
                    return True
                if self.patterns['numbered_sub'].match(next_line):
                    return True
                if self._is_field_component(next_line):
                    return True
        
        return False
    
    def _is_field_component(self, line: str) -> bool:
        """Check if line is a field component (like address parts)"""
        components = [
            'Family Name', 'Given Name', 'Middle Name',
            'In Care Of Name', 'Street Number and Name',
            'Apt.', 'Ste.', 'Flr.', 'Number',
            'City or Town', 'State', 'ZIP Code', 'Country'
        ]
        
        line_stripped = line.strip()
        return any(comp in line_stripped for comp in components)
    
    def _determine_field_type(self, label: str, lines: List[str], current_idx: int) -> str:
        """Determine the type of field"""
        label_lower = label.lower()
        
        # Check patterns
        if 'date' in label_lower or 'mm/dd/yyyy' in label:
            return 'date'
        
        if 'signature' in label_lower:
            return 'signature'
        
        if any(word in label_lower for word in ['number', 'a-number', 'alien registration']):
            return 'number'
        
        if 'email' in label_lower:
            return 'email'
        
        if any(word in label_lower for word in ['phone', 'telephone', 'mobile']):
            return 'phone'
        
        # Check if it's a yes/no question
        question_starters = ['is', 'are', 'do', 'does', 'have', 'has', 'were', 'was', 'will']
        if any(label_lower.startswith(starter + ' ') for starter in question_starters):
            # Check next line for Yes/No options
            if current_idx + 1 < len(lines):
                next_line = lines[current_idx + 1].strip()
                if '□ Yes' in next_line or 'Yes' in next_line and 'No' in next_line:
                    return 'checkbox'
        
        return 'text'

# Structure Validation Agent
class StructureValidationAgent(BaseAgent):
    """Validates the extracted structure against expected patterns"""
    
    def __init__(self):
        super().__init__("Structure Validation Agent")
        self.expected_structures = self._load_expected_structures()
    
    def _load_expected_structures(self):
        """Load expected form structures"""
        return {
            "I-539": {
                "parts": {
                    1: {
                        "title": "Information About You",
                        "required_fields": ["1", "2", "3", "4", "5", "6"],
                        "field_patterns": {
                            "1": {"label_pattern": r"Your Full Legal Name", "has_sub_items": True, "sub_items": ["1a", "1b", "1c"]},
                            "2": {"label_pattern": r"Alien Registration Number.*A-Number", "has_sub_items": False},
                            "3": {"label_pattern": r"USCIS Online Account Number", "has_sub_items": False},
                            "4": {"label_pattern": r"Your U\.S\. Mailing Address", "has_sub_items": True},
                            "5": {"label_pattern": r"Is your mailing address.*same.*physical", "has_sub_items": False},
                            "6": {"label_pattern": r"Your Current Physical Address", "has_sub_items": True}
                        }
                    }
                }
            }
        }
    
    def process(self, extraction: FormExtraction) -> Tuple[bool, List[str]]:
        """Validate the extraction structure"""
        self.status = "active"
        self.log("Validating extraction structure...")
        
        errors = []
        
        # Get expected structure
        expected = self.expected_structures.get(extraction.form_number)
        if not expected:
            self.log(f"No expected structure defined for {extraction.form_number}", "warning")
            return True, []
        
        # Validate parts
        for part_num, part_info in expected.get("parts", {}).items():
            if part_num not in extraction.parts:
                errors.append(f"Missing Part {part_num}")
                continue
            
            part = extraction.parts[part_num]
            
            # Validate title
            if part_info.get("title") and part.title != part_info["title"]:
                self.log(f"Part {part_num} title mismatch: expected '{part_info['title']}', got '{part.title}'", "warning")
            
            # Validate required fields
            for req_field in part_info.get("required_fields", []):
                field = part.get_field_by_number(req_field)
                if not field:
                    errors.append(f"Part {part_num}: Missing required field {req_field}")
                else:
                    # Validate field structure
                    field_pattern = part_info.get("field_patterns", {}).get(req_field)
                    if field_pattern:
                        # Check label pattern
                        if field_pattern.get("label_pattern"):
                            if not re.search(field_pattern["label_pattern"], field.label, re.IGNORECASE):
                                errors.append(f"Part {part_num}, Field {req_field}: Label doesn't match expected pattern")
                        
                        # Check sub-items
                        if field_pattern.get("has_sub_items"):
                            expected_subs = field_pattern.get("sub_items", [])
                            actual_subs = [child.number for child in field.children]
                            
                            for expected_sub in expected_subs:
                                if expected_sub not in actual_subs:
                                    errors.append(f"Part {part_num}, Field {req_field}: Missing sub-item {expected_sub}")
        
        # Validate field sequences
        for part_num, part in extraction.parts.items():
            seq_errors = part.validate_sequence()
            for error in seq_errors:
                errors.append(f"Part {part_num}: {error}")
        
        is_valid = len(errors) == 0
        
        if is_valid:
            self.log("Structure validation passed!", "success")
        else:
            self.log(f"Structure validation found {len(errors)} errors", "error")
            for error in errors[:5]:  # Show first 5 errors
                self.log(f"  - {error}", "error")
        
        return is_valid, errors

# Field Assignment Agent
class FieldAssignmentAgent(BaseAgent):
    """Assigns fields to database structure"""
    
    def __init__(self):
        super().__init__("Field Assignment Agent")
        self.mappings = self._load_mappings()
    
    def _load_mappings(self):
        """Load field mappings"""
        return {
            "I-539": {
                "1a": "beneficiary.Beneficiary.beneficiaryLastName",
                "1b": "beneficiary.Beneficiary.beneficiaryFirstName",
                "1c": "beneficiary.Beneficiary.beneficiaryMiddleName",
                "2": "beneficiary.Beneficiary.alienNumber",
                "3": "beneficiary.Beneficiary.uscisAccountNumber",
                # Add more mappings...
            }
        }
    
    def process(self, extraction: FormExtraction) -> Dict[str, str]:
        """Assign fields to database paths"""
        self.status = "active"
        self.log("Assigning fields to database structure...")
        
        assignments = {}
        form_mappings = self.mappings.get(extraction.form_number, {})
        
        for part in extraction.parts.values():
            for field in part.fields:
                # Assign main field
                if field.number in form_mappings:
                    assignments[field.number] = form_mappings[field.number]
                    self.log(f"Assigned field {field.number} to {form_mappings[field.number]}")
                
                # Assign children
                for child in field.children:
                    if child.number in form_mappings:
                        assignments[child.number] = form_mappings[child.number]
                        self.log(f"Assigned field {child.number} to {form_mappings[child.number]}")
        
        self.log(f"Assigned {len(assignments)} fields", "success")
        return assignments

# Output Verification Agent
class OutputVerificationAgent(BaseAgent):
    """Verifies the final output is correct"""
    
    def __init__(self):
        super().__init__("Output Verification Agent")
    
    def process(self, extraction: FormExtraction, validation_errors: List[str], 
                assignments: Dict[str, str]) -> bool:
        """Verify the output is correct"""
        self.status = "active"
        self.log("Verifying final output...")
        
        # Check extraction completeness
        total_fields = len(extraction.get_all_fields())
        if total_fields < 10:
            self.log(f"Warning: Only {total_fields} fields extracted", "warning")
            return False
        
        # Check validation
        if validation_errors:
            self.log(f"Validation errors present: {len(validation_errors)}", "error")
            return False
        
        # Check assignments
        assigned_fields = len(assignments)
        if assigned_fields < total_fields * 0.5:
            self.log(f"Warning: Only {assigned_fields}/{total_fields} fields assigned", "warning")
            return False
        
        # Verify critical fields
        critical_checks = self._verify_critical_fields(extraction)
        if not all(critical_checks.values()):
            failed = [k for k, v in critical_checks.items() if not v]
            self.log(f"Critical field checks failed: {failed}", "error")
            return False
        
        self.log("Output verification passed!", "success")
        return True
    
    def _verify_critical_fields(self, extraction: FormExtraction) -> Dict[str, bool]:
        """Verify critical fields are present and correct"""
        checks = {}
        
        # For I-539, check Part 1
        if extraction.form_number == "I-539":
            part1 = extraction.parts.get(1)
            if part1:
                # Check name field
                name_field = part1.get_field_by_number("1")
                checks["has_name_field"] = name_field is not None
                checks["name_has_subitems"] = name_field and len(name_field.children) >= 3
                
                # Check A-Number field
                a_number_field = part1.get_field_by_number("2")
                checks["has_a_number"] = a_number_field is not None
                checks["a_number_label_correct"] = (
                    a_number_field and 
                    "alien registration number" in a_number_field.label.lower()
                )
        
        return checks

# Master Coordinator Agent
class MasterCoordinatorAgent(BaseAgent):
    """Coordinates all agents and manages the extraction loop"""
    
    def __init__(self):
        super().__init__("Master Coordinator")
        self.max_iterations = 5
        self.agents = {
            'extractor': RecursiveExtractionAgent(),
            'validator': StructureValidationAgent(),
            'assigner': FieldAssignmentAgent(),
            'verifier': OutputVerificationAgent()
        }
    
    def process(self, pdf_bytes: bytes) -> Optional[FormExtraction]:
        """Coordinate the extraction process"""
        self.status = "active"
        self.log("Starting coordinated extraction process...")
        
        iteration = 0
        extraction = None
        
        while iteration < self.max_iterations:
            iteration += 1
            self.log(f"=== Iteration {iteration} ===")
            
            try:
                # Step 1: Extract
                if iteration == 1:
                    extraction = self.agents['extractor'].process(pdf_bytes)
                else:
                    # Re-extract with feedback
                    self.log("Re-extracting with enhanced patterns...")
                    extraction = self._enhanced_extraction(pdf_bytes, extraction)
                
                # Step 2: Validate
                is_valid, validation_errors = self.agents['validator'].process(extraction)
                
                # Step 3: Assign
                assignments = self.agents['assigner'].process(extraction)
                
                # Step 4: Verify
                is_correct = self.agents['verifier'].process(
                    extraction, validation_errors, assignments
                )
                
                if is_correct:
                    self.log(f"Extraction successful after {iteration} iterations!", "success")
                    
                    # Add metadata
                    extraction.extraction_iterations = iteration
                    extraction.is_valid = True
                    extraction.validation_score = 1.0
                    
                    # Add logs
                    for agent_name, agent in self.agents.items():
                        extraction.agent_logs[agent_name] = [log[1] for log in agent.logs]
                    
                    return extraction
                else:
                    self.log(f"Iteration {iteration} failed verification, retrying...", "warning")
                    
            except Exception as e:
                self.log(f"Error in iteration {iteration}: {str(e)}", "error")
                
        self.log("Max iterations reached without success", "error")
        return extraction
    
    def _enhanced_extraction(self, pdf_bytes: bytes, previous_extraction: FormExtraction) -> FormExtraction:
        """Enhanced extraction based on previous results"""
        # This would implement more sophisticated extraction based on what was missed
        # For now, just re-run the basic extraction
        return self.agents['extractor'].process(pdf_bytes)

# UI Helper Functions
def display_extraction_results(extraction: FormExtraction):
    """Display extraction results in a structured way"""
    st.markdown("## 📋 Extraction Results")
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Form", extraction.form_number)
    with col2:
        st.metric("Parts", len(extraction.parts))
    with col3:
        total_fields = len(extraction.get_all_fields())
        st.metric("Total Fields", total_fields)
    with col4:
        st.metric("Iterations", extraction.extraction_iterations)
    
    # Display parts and fields
    for part_num, part in extraction.parts.items():
        with st.expander(f"Part {part_num}: {part.title}", expanded=(part_num == 1)):
            display_fields_recursive(part.fields)

def display_fields_recursive(fields: List[FieldItem], level: int = 0):
    """Display fields recursively with proper indentation"""
    for field in fields:
        # Display main field
        indent = "  " * level
        if field.children:
            st.markdown(f"{indent}**{field.number}. {field.label}** (Group)")
        else:
            st.markdown(f"{indent}**{field.number}.** {field.label} `[{field.type}]`")
        
        # Display children
        if field.children:
            display_fields_recursive(field.children, level + 1)

# Main Application
def main():
    st.markdown('<div class="main-header"><h1>🤖 Enhanced USCIS Form Reader</h1><p>Recursive Extraction with Validation Loop</p></div>', 
               unsafe_allow_html=True)
    
    # Check dependencies
    if not PYMUPDF_AVAILABLE:
        st.error("❌ PyMuPDF not installed. Please install: pip install PyMuPDF")
        return
    
    # Initialize session state
    if 'extraction_result' not in st.session_state:
        st.session_state.extraction_result = None
    
    # Sidebar
    with st.sidebar:
        st.markdown("## ⚙️ Configuration")
        
        max_iterations = st.slider("Max Iterations", 1, 10, 5)
        show_agent_logs = st.checkbox("Show Agent Logs", value=True)
        
        if st.session_state.extraction_result:
            st.markdown("### 📊 Current Extraction")
            extraction = st.session_state.extraction_result
            st.info(f"Form: {extraction.form_number}")
            st.metric("Validation Score", f"{extraction.validation_score:.0%}")
    
    # Main content
    st.markdown("## 📤 Upload USCIS Form")
    
    uploaded_file = st.file_uploader(
        "Choose a USCIS PDF form",
        type=['pdf'],
        help="Upload any USCIS form (I-539, I-129, I-485, etc.)"
    )
    
    if uploaded_file:
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.success(f"✅ {uploaded_file.name} uploaded")
        
        with col2:
            if st.button("🚀 Process", type="primary", use_container_width=True):
                # Create containers for agent output
                st.session_state.agent_container = st.container()
                
                # Process with coordinator
                with st.spinner("Processing with recursive extraction..."):
                    coordinator = MasterCoordinatorAgent()
                    coordinator.max_iterations = max_iterations
                    
                    pdf_bytes = uploaded_file.read()
                    extraction = coordinator.process(pdf_bytes)
                    
                    if extraction and extraction.is_valid:
                        st.session_state.extraction_result = extraction
                        st.success("✅ Extraction completed successfully!")
                        
                        # Display results
                        display_extraction_results(extraction)
                        
                        # Show agent logs if enabled
                        if show_agent_logs:
                            with st.expander("🤖 Agent Logs"):
                                for agent_name, logs in extraction.agent_logs.items():
                                    st.markdown(f"### {agent_name}")
                                    for log in logs[-10:]:  # Show last 10 logs
                                        st.text(log)
                        
                        # Export options
                        st.markdown("## 📥 Export Options")
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            json_data = extraction.to_json()
                            st.download_button(
                                "📄 Download JSON",
                                json_data,
                                f"{extraction.form_number}_extraction.json",
                                mime="application/json"
                            )
                        
                        with col2:
                            if st.button("🔄 Re-process"):
                                st.session_state.extraction_result = None
                                st.experimental_rerun()
                    else:
                        st.error("❌ Extraction failed after maximum iterations")
    
    # Display existing results
    elif st.session_state.extraction_result:
        extraction = st.session_state.extraction_result
        st.info(f"Showing results for previously processed form: {extraction.form_number}")
        display_extraction_results(extraction)

if __name__ == "__main__":
    main()
