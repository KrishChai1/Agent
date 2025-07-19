#!/usr/bin/env python3
"""
Multi-Agent USCIS Form Reader with Recursive Extraction and Validation Loop
Extracts fields correctly with proper key assignment (P1_1a format)
"""

import os
import json
import re
import time
import hashlib
import traceback
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Set, Union
from dataclasses import dataclass, field, asdict
from collections import defaultdict, OrderedDict
from abc import ABC, abstractmethod
import copy

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
    page_title="Multi-Agent USCIS Form Reader",
    page_icon="🤖",
    layout="wide"
)

# CSS Styling
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
        background: #f0f0f0;
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
        border-left: 4px solid #4CAF50;
    }
    .agent-error {
        border-left: 4px solid #f44336;
        background: #ffebee;
    }
    .agent-warning {
        border-left: 4px solid #ff9800;
        background: #fff3e0;
    }
    .field-output {
        font-family: monospace;
        background: #f5f5f5;
        padding: 0.5rem;
        border-radius: 4px;
        margin: 0.2rem 0;
    }
    .validation-pass {
        color: #4CAF50;
        font-weight: bold;
    }
    .validation-fail {
        color: #f44336;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Data Classes
@dataclass
class FieldNode:
    """Represents a field in hierarchical structure"""
    item_number: str  # e.g., "1", "1a", "2"
    label: str  # e.g., "Your Full Legal Name"
    field_type: str  # text, checkbox, date, etc.
    value: str = ""
    
    # Hierarchy
    parent: Optional['FieldNode'] = None
    children: List['FieldNode'] = field(default_factory=list)
    
    # Location
    page: int = 1
    part_number: int = 1
    part_name: str = "Part 1"
    
    # Generated key
    key: str = ""  # e.g., "P1_1a"
    
    # Extraction metadata
    confidence: float = 0.0
    extraction_method: str = ""  # recursive, pattern, widget, ai
    raw_text: str = ""
    
    def add_child(self, child: 'FieldNode'):
        """Add child node"""
        child.parent = self
        self.children.append(child)
    
    def get_full_path(self) -> str:
        """Get full path from root"""
        if self.parent:
            return f"{self.parent.get_full_path()}.{self.item_number}"
        return self.item_number
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "key": self.key,
            "item_number": self.item_number,
            "label": self.label,
            "type": self.field_type,
            "value": self.value,
            "children": [child.to_dict() for child in self.children]
        }

@dataclass 
class PartStructure:
    """Represents a part with hierarchical fields"""
    part_number: int
    part_name: str
    part_title: str = ""
    root_fields: List[FieldNode] = field(default_factory=list)
    
    def get_all_fields_flat(self) -> List[FieldNode]:
        """Get all fields in flat list"""
        fields = []
        
        def collect_fields(node: FieldNode):
            fields.append(node)
            for child in node.children:
                collect_fields(child)
        
        for root in self.root_fields:
            collect_fields(root)
        
        return fields
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "part_number": self.part_number,
            "part_name": self.part_name,
            "part_title": self.part_title,
            "fields": [field.to_dict() for field in self.root_fields]
        }

@dataclass
class FormExtractionResult:
    """Complete extraction result"""
    form_number: str  # e.g., "I-539"
    form_title: str
    parts: Dict[int, PartStructure] = field(default_factory=dict)
    
    # Validation status
    is_valid: bool = False
    validation_errors: List[str] = field(default_factory=list)
    validation_score: float = 0.0
    
    # Extraction metadata
    extraction_iterations: int = 0
    total_fields: int = 0
    
    def get_all_fields_with_keys(self) -> Dict[str, FieldNode]:
        """Get all fields indexed by key"""
        fields = {}
        for part in self.parts.values():
            for field in part.get_all_fields_flat():
                if field.key:
                    fields[field.key] = field
        return fields
    
    def to_output_format(self) -> Dict[str, Any]:
        """Convert to expected output format"""
        output = {}
        for part in self.parts.values():
            for field in part.get_all_fields_flat():
                if field.key:
                    output[field.key] = field.value
                    # Add title fields
                    if field.label:
                        output[f"{field.key}_title"] = field.label
        return output

# Base Agent
class BaseAgent(ABC):
    """Base class for all agents"""
    
    def __init__(self, name: str):
        self.name = name
        self.status = "idle"
        self.logs = []
        self.errors = []
        
    @abstractmethod
    def execute(self, *args, **kwargs) -> Any:
        pass
    
    def log(self, message: str, level: str = "info"):
        """Log message"""
        entry = {
            "timestamp": datetime.now().strftime('%H:%M:%S'),
            "message": message,
            "level": level
        }
        self.logs.append(entry)
        
        # Display in UI if container exists
        if hasattr(st.session_state, 'agent_container'):
            with st.session_state.agent_container:
                css_class = "agent-status"
                if level == "error":
                    css_class += " agent-error"
                elif level == "warning":
                    css_class += " agent-warning"
                
                st.markdown(f'<div class="{css_class}"><b>{self.name}</b>: {message}</div>', 
                          unsafe_allow_html=True)

# Recursive Extractor Agent
class RecursiveExtractorAgent(BaseAgent):
    """Extracts fields recursively with proper hierarchy"""
    
    def __init__(self):
        super().__init__("Recursive Extractor")
        self.doc = None
        self.patterns = self._compile_patterns()
    
    def _compile_patterns(self) -> Dict[str, re.Pattern]:
        """Compile regex patterns"""
        return {
            # Part patterns
            'part': re.compile(r'^Part\s+(\d+)(?:\.\s*(.*))?$', re.IGNORECASE),
            
            # Main item patterns
            'main_item': re.compile(r'^(\d+)\.\s+(.+?)$'),
            'item_no_period': re.compile(r'^(\d+)\s+(.+?)$'),
            
            # Sub-item patterns  
            'sub_item': re.compile(r'^(\d+)([a-z])\.\s+(.+?)$'),
            'letter_only': re.compile(r'^([a-z])\.\s+(.+?)$'),
            'indented_sub': re.compile(r'^\s{2,}([a-z])\.\s+(.+?)$'),
            
            # Special patterns
            'checkbox': re.compile(r'^\s*□\s*(.+?)$'),
            'arrow': re.compile(r'^\s*►\s*(.*)$'),
            'yes_no': re.compile(r'^\s*(Yes|No)\s*$', re.IGNORECASE),
        }
    
    def execute(self, pdf_file) -> FormExtractionResult:
        """Execute recursive extraction"""
        self.status = "active"
        self.log("Starting recursive extraction...")
        
        try:
            # Open PDF
            pdf_bytes = pdf_file.read() if hasattr(pdf_file, 'read') else pdf_file
            self.doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            # Identify form
            form_info = self._identify_form()
            result = FormExtractionResult(
                form_number=form_info['number'],
                form_title=form_info['title']
            )
            
            # Extract each page
            for page_num in range(len(self.doc)):
                self._extract_page(page_num, result)
            
            # Calculate totals
            for part in result.parts.values():
                result.total_fields += len(part.get_all_fields_flat())
            
            self.log(f"Extraction complete. Found {len(result.parts)} parts, {result.total_fields} fields", "success")
            self.status = "completed"
            return result
            
        except Exception as e:
            self.log(f"Extraction failed: {str(e)}", "error")
            self.status = "error"
            raise
        finally:
            if self.doc:
                self.doc.close()
    
    def _identify_form(self) -> Dict:
        """Identify form type"""
        first_page = self.doc[0].get_text()
        
        forms = {
            'I-539': 'Application to Extend/Change Nonimmigrant Status',
            'I-129': 'Petition for a Nonimmigrant Worker',
            'I-90': 'Application to Replace Permanent Resident Card',
            'G-28': 'Notice of Entry of Appearance',
            'I-485': 'Application to Register Permanent Residence',
            'I-765': 'Application for Employment Authorization',
            'N-400': 'Application for Naturalization'
        }
        
        for form_num, title in forms.items():
            if form_num in first_page:
                self.log(f"Identified form: {form_num} - {title}")
                return {"number": form_num, "title": title}
        
        return {"number": "Unknown", "title": "Unknown Form"}
    
    def _extract_page(self, page_num: int, result: FormExtractionResult):
        """Extract fields from a page recursively"""
        page = self.doc[page_num]
        text = page.get_text()
        lines = text.split('\n')
        
        current_part = None
        current_parent = None
        line_idx = 0
        
        while line_idx < len(lines):
            line = lines[line_idx].strip()
            
            if not line:
                line_idx += 1
                continue
            
            # Check for part header
            part_match = self.patterns['part'].match(line)
            if part_match:
                part_num = int(part_match.group(1))
                part_title = part_match.group(2) or ""
                
                # Get full title from next line if needed
                if not part_title and line_idx + 1 < len(lines):
                    next_line = lines[line_idx + 1].strip()
                    if next_line and not any(p.match(next_line) for p in self.patterns.values()):
                        part_title = next_line
                        line_idx += 1
                
                # Create or get part
                if part_num not in result.parts:
                    result.parts[part_num] = PartStructure(
                        part_number=part_num,
                        part_name=f"Part {part_num}",
                        part_title=part_title
                    )
                
                current_part = result.parts[part_num]
                current_parent = None
                self.log(f"Processing Part {part_num}: {part_title}")
                line_idx += 1
                continue
            
            # Skip if no current part
            if not current_part:
                line_idx += 1
                continue
            
            # Extract field recursively
            field, lines_consumed = self._extract_field_recursive(
                lines, line_idx, page_num + 1, current_part, current_parent
            )
            
            if field:
                if not field.parent:
                    current_part.root_fields.append(field)
                    
                # Update parent for potential sub-items
                if field.children or self._might_have_children(field.label):
                    current_parent = field
                elif not field.parent:
                    current_parent = None
            
            line_idx += lines_consumed
    
    def _extract_field_recursive(self, lines: List[str], start_idx: int, page_num: int,
                                part: PartStructure, parent: Optional[FieldNode]) -> Tuple[Optional[FieldNode], int]:
        """Recursively extract a field and its children"""
        line = lines[start_idx].strip()
        lines_consumed = 1
        
        # Try main item pattern
        main_match = self.patterns['main_item'].match(line)
        if not main_match:
            main_match = self.patterns['item_no_period'].match(line)
        
        if main_match:
            item_num = main_match.group(1)
            label = main_match.group(2).strip()
            
            # Create field node
            field = FieldNode(
                item_number=item_num,
                label=label,
                field_type=self._determine_field_type(label, lines, start_idx),
                page=page_num,
                part_number=part.part_number,
                part_name=part.part_name,
                extraction_method="recursive",
                raw_text=line
            )
            
            # Check for children
            if self._might_have_children(label):
                child_idx = start_idx + 1
                expected_letter = 'a'
                
                while child_idx < len(lines):
                    # Look for sub-items
                    sub_field, sub_consumed = self._extract_sub_item(
                        lines, child_idx, item_num, expected_letter, page_num, part, field
                    )
                    
                    if sub_field:
                        field.add_child(sub_field)
                        lines_consumed += sub_consumed
                        child_idx += sub_consumed
                        expected_letter = chr(ord(expected_letter) + 1)
                    else:
                        # Check if line belongs to this field
                        next_line = lines[child_idx].strip()
                        
                        # Stop if we hit another main item
                        if self.patterns['main_item'].match(next_line):
                            break
                        
                        # Check for field value indicators
                        if self.patterns['arrow'].match(next_line):
                            lines_consumed += 1
                            child_idx += 1
                        elif self.patterns['checkbox'].match(next_line):
                            lines_consumed += 1
                            child_idx += 1
                        else:
                            break
            
            return field, lines_consumed
        
        # Try sub-item pattern if we have a parent
        if parent:
            sub_field, sub_consumed = self._extract_sub_item(
                lines, start_idx, parent.item_number, None, page_num, part, parent
            )
            if sub_field:
                return sub_field, sub_consumed
        
        return None, 1
    
    def _extract_sub_item(self, lines: List[str], start_idx: int, parent_num: str,
                         expected_letter: Optional[str], page_num: int, 
                         part: PartStructure, parent: FieldNode) -> Tuple[Optional[FieldNode], int]:
        """Extract a sub-item"""
        line = lines[start_idx].strip()
        
        # Try different sub-item patterns
        patterns_to_try = [
            (self.patterns['sub_item'], lambda m: (m.group(2), m.group(3))),
            (self.patterns['letter_only'], lambda m: (m.group(1), m.group(2))),
            (self.patterns['indented_sub'], lambda m: (m.group(1), m.group(2))),
        ]
        
        for pattern, extractor in patterns_to_try:
            match = pattern.match(line)
            if match:
                # Extract parts based on pattern
                if pattern == self.patterns['sub_item']:
                    # Check if parent number matches
                    if match.group(1) != parent_num:
                        continue
                
                letter, label = extractor(match)
                
                # Check if this is the expected letter
                if expected_letter and letter != expected_letter:
                    continue
                
                # Create sub-field
                sub_field = FieldNode(
                    item_number=f"{parent_num}{letter}",
                    label=label.strip(),
                    field_type=self._determine_field_type(label, lines, start_idx),
                    page=page_num,
                    part_number=part.part_number,
                    part_name=part.part_name,
                    extraction_method="recursive",
                    raw_text=line
                )
                
                return sub_field, 1
        
        # Check for special cases (e.g., address fields without letters)
        if self._is_address_component(line) and parent and "address" in parent.label.lower():
            # Create sub-field with auto-generated letter
            if expected_letter:
                sub_field = FieldNode(
                    item_number=f"{parent_num}{expected_letter}",
                    label=line,
                    field_type="text",
                    page=page_num,
                    part_number=part.part_number,
                    part_name=part.part_name,
                    extraction_method="recursive",
                    raw_text=line
                )
                return sub_field, 1
        
        return None, 0
    
    def _might_have_children(self, label: str) -> bool:
        """Check if a field might have children"""
        label_lower = label.lower()
        
        parent_indicators = [
            'name', 'address', 'information', 'contact',
            'mailing', 'physical', 'employment', 'education'
        ]
        
        return any(indicator in label_lower for indicator in parent_indicators)
    
    def _is_address_component(self, text: str) -> bool:
        """Check if text is an address component"""
        components = [
            'street number', 'street name', 'apt', 'ste', 'flr',
            'city', 'town', 'state', 'zip', 'postal', 'country',
            'in care of', 'c/o'
        ]
        
        text_lower = text.lower()
        return any(comp in text_lower for comp in components)
    
    def _determine_field_type(self, label: str, lines: List[str], current_idx: int) -> str:
        """Determine field type from label and context"""
        label_lower = label.lower()
        
        # Date fields
        if any(word in label_lower for word in ['date', 'birth', 'expire', 'issue']):
            return "date"
        
        # Number fields
        if any(word in label_lower for word in ['number', 'ssn', 'ein', 'a-number', 'alien']):
            return "number"
        
        # Email/Phone
        if 'email' in label_lower:
            return "email"
        if any(word in label_lower for word in ['phone', 'telephone', 'mobile']):
            return "phone"
        
        # Checkbox/Radio
        if label_lower.startswith(('are you', 'have you', 'do you', 'is ', 'was ')):
            return "checkbox"
        
        # Check next line for Yes/No
        if current_idx + 1 < len(lines):
            next_line = lines[current_idx + 1].strip().lower()
            if 'yes' in next_line and 'no' in next_line:
                return "checkbox"
        
        # Signature
        if 'signature' in label_lower:
            return "signature"
        
        return "text"

# Key Assignment Agent
class KeyAssignmentAgent(BaseAgent):
    """Assigns proper keys (P1_1a format) to fields"""
    
    def __init__(self):
        super().__init__("Key Assignment Agent")
    
    def execute(self, result: FormExtractionResult) -> FormExtractionResult:
        """Assign keys to all fields"""
        self.status = "active"
        self.log("Assigning keys to fields...")
        
        try:
            for part_num, part in result.parts.items():
                for field in part.get_all_fields_flat():
                    # Generate key
                    key = self._generate_key(field)
                    field.key = key
            
            self.log(f"Key assignment complete", "success")
            self.status = "completed"
            return result
            
        except Exception as e:
            self.log(f"Key assignment failed: {str(e)}", "error")
            self.status = "error"
            raise
    
    def _generate_key(self, field: FieldNode) -> str:
        """Generate key in P{part}_{item} format"""
        # Basic format: P{part_number}_{item_number}
        key = f"P{field.part_number}_{field.item_number}"
        
        # Clean up the key
        key = key.replace('.', '')
        key = key.replace(' ', '_')
        
        return key

# Validator Agent
class ValidatorAgent(BaseAgent):
    """Validates extraction results"""
    
    def __init__(self):
        super().__init__("Validator Agent")
        self.expected_patterns = self._load_expected_patterns()
    
    def _load_expected_patterns(self) -> Dict:
        """Load expected patterns for forms"""
        return {
            "I-539": {
                "parts": [1, 2, 3, 4, 5, 6, 7, 8],
                "part_1_items": ["1", "2", "3", "4", "5", "6"],
                "sub_items": {
                    "1": ["a", "b", "c"],  # Name fields
                    "4": [],  # Address has components but not lettered
                    "6": []   # Physical address
                },
                "required_fields": ["P1_1a", "P1_1b", "P1_2"]  # Family name, Given name, A-Number
            },
            "I-129": {
                "parts": [1, 2, 3, 4, 5, 6, 7, 8, 9],
                "required_fields": ["P1_1", "P3_1a", "P3_1b"]
            },
            "G-28": {
                "parts": [1, 2, 3, 4, 5, 6],
                "required_fields": ["P1_2a", "P1_2b", "P3_6a", "P3_6b", "P3_9"]
            }
        }
    
    def execute(self, result: FormExtractionResult) -> Tuple[bool, List[str]]:
        """Validate extraction result"""
        self.status = "active"
        self.log(f"Validating {result.form_number} extraction...")
        
        errors = []
        
        try:
            # Get expected pattern
            expected = self.expected_patterns.get(result.form_number, {})
            
            if expected:
                # Check parts
                errors.extend(self._validate_parts(result, expected))
                
                # Check required fields
                errors.extend(self._validate_required_fields(result, expected))
                
                # Check field sequences
                errors.extend(self._validate_sequences(result))
                
                # Check sub-item structure
                errors.extend(self._validate_sub_items(result, expected))
            
            # Calculate validation score
            if result.total_fields > 0:
                error_penalty = min(len(errors) * 0.05, 0.5)
                result.validation_score = max(0, 1.0 - error_penalty)
            
            result.validation_errors = errors
            result.is_valid = len(errors) == 0
            
            if result.is_valid:
                self.log(f"Validation passed! Score: {result.validation_score:.0%}", "success")
            else:
                self.log(f"Validation found {len(errors)} issues", "warning")
                for error in errors[:5]:  # Show first 5
                    self.log(f"  - {error}", "warning")
            
            self.status = "completed"
            return result.is_valid, errors
            
        except Exception as e:
            self.log(f"Validation failed: {str(e)}", "error")
            self.status = "error"
            return False, [str(e)]
    
    def _validate_parts(self, result: FormExtractionResult, expected: Dict) -> List[str]:
        """Validate parts"""
        errors = []
        expected_parts = expected.get("parts", [])
        
        for part_num in expected_parts:
            if part_num not in result.parts:
                errors.append(f"Missing Part {part_num}")
        
        # Check part sequence
        if result.parts:
            part_nums = sorted(result.parts.keys())
            for i, num in enumerate(part_nums):
                if i > 0 and num != part_nums[i-1] + 1:
                    errors.append(f"Part sequence gap between Part {part_nums[i-1]} and Part {num}")
        
        return errors
    
    def _validate_required_fields(self, result: FormExtractionResult, expected: Dict) -> List[str]:
        """Validate required fields exist"""
        errors = []
        required = expected.get("required_fields", [])
        all_fields = result.get_all_fields_with_keys()
        
        for field_key in required:
            if field_key not in all_fields:
                errors.append(f"Missing required field: {field_key}")
        
        return errors
    
    def _validate_sequences(self, result: FormExtractionResult) -> List[str]:
        """Validate field sequences within parts"""
        errors = []
        
        for part in result.parts.values():
            # Get main items (root fields)
            main_items = {}
            for field in part.root_fields:
                if field.item_number.isdigit():
                    main_items[int(field.item_number)] = field
            
            # Check sequence
            if main_items:
                sorted_nums = sorted(main_items.keys())
                for i, num in enumerate(sorted_nums):
                    if i > 0 and num != sorted_nums[i-1] + 1:
                        errors.append(f"{part.part_name}: Item sequence gap between {sorted_nums[i-1]} and {num}")
        
        return errors
    
    def _validate_sub_items(self, result: FormExtractionResult, expected: Dict) -> List[str]:
        """Validate sub-item structure"""
        errors = []
        expected_subs = expected.get("sub_items", {})
        
        for part in result.parts.values():
            for field in part.get_all_fields_flat():
                # Check if this main item should have sub-items
                if field.item_number in expected_subs:
                    expected_letters = expected_subs[field.item_number]
                    
                    if expected_letters:
                        # Get actual sub-items
                        actual_letters = []
                        for child in field.children:
                            match = re.match(r'\d+([a-z])', child.item_number)
                            if match:
                                actual_letters.append(match.group(1))
                        
                        # Compare
                        for letter in expected_letters:
                            if letter not in actual_letters:
                                errors.append(f"Missing sub-item: {field.item_number}{letter}")
        
        return errors

# Output Checker Agent
class OutputCheckerAgent(BaseAgent):
    """Checks if output matches expected format"""
    
    def __init__(self):
        super().__init__("Output Checker")
    
    def execute(self, result: FormExtractionResult, expected_sample: Optional[Dict] = None) -> bool:
        """Check if output is correct"""
        self.status = "active"
        self.log("Checking output format...")
        
        try:
            output = result.to_output_format()
            
            # Basic checks
            if not output:
                self.log("Output is empty", "error")
                return False
            
            # Check key format
            for key in output.keys():
                if not self._is_valid_key_format(key):
                    self.log(f"Invalid key format: {key}", "error")
                    return False
            
            # Check against expected sample if provided
            if expected_sample:
                missing_keys = set(expected_sample.keys()) - set(output.keys())
                if missing_keys:
                    self.log(f"Missing expected keys: {missing_keys}", "warning")
                    return False
            
            # Check for common fields based on form type
            if not self._check_common_fields(result.form_number, output):
                return False
            
            self.log("Output check passed", "success")
            self.status = "completed"
            return True
            
        except Exception as e:
            self.log(f"Output check failed: {str(e)}", "error")
            self.status = "error"
            return False
    
    def _is_valid_key_format(self, key: str) -> bool:
        """Check if key matches expected format"""
        # Should match patterns like P1_1, P1_1a, P1_1_title
        patterns = [
            r'^P\d+_\d+[a-z]?$',  # P1_1, P1_1a
            r'^P\d+_\d+[a-z]?_title$',  # P1_1_title
            r'^P\d+_\d+[a-z]?_\w+$',  # P1_1_other_suffix
        ]
        
        return any(re.match(pattern, key) for pattern in patterns)
    
    def _check_common_fields(self, form_number: str, output: Dict) -> bool:
        """Check for common fields that should exist"""
        common_fields = {
            "I-539": ["P1_1a", "P1_1b", "P1_2"],  # Name and A-Number
            "I-129": ["P1_1", "P3_1a", "P3_1b"],  # Petitioner and beneficiary
            "G-28": ["P1_2a", "P1_2b", "P3_6a", "P3_6b"],  # Attorney and client names
        }
        
        required = common_fields.get(form_number, [])
        missing = [field for field in required if field not in output]
        
        if missing:
            self.log(f"Missing common fields: {missing}", "error")
            return False
        
        return True

# Coordinator Agent
class CoordinatorAgent(BaseAgent):
    """Coordinates all agents with retry loop"""
    
    def __init__(self, max_iterations: int = 5):
        super().__init__("Coordinator")
        self.max_iterations = max_iterations
        self.agents = {
            'extractor': RecursiveExtractorAgent(),
            'assigner': KeyAssignmentAgent(),
            'validator': ValidatorAgent(),
            'checker': OutputCheckerAgent()
        }
    
    def execute(self, pdf_file) -> Optional[FormExtractionResult]:
        """Execute extraction with validation loop"""
        self.status = "active"
        self.log(f"Starting coordinated extraction (max {self.max_iterations} iterations)...")
        
        iteration = 0
        result = None
        
        try:
            while iteration < self.max_iterations:
                iteration += 1
                self.log(f"\n=== Iteration {iteration} ===")
                
                # Step 1: Extract
                if iteration == 1:
                    result = self.agents['extractor'].execute(pdf_file)
                else:
                    # Re-extract with feedback
                    self.log("Re-extracting with improved patterns...")
                    result = self._re_extract_with_feedback(pdf_file, result)
                
                if not result:
                    self.log("Extraction failed", "error")
                    break
                
                # Step 2: Assign keys
                result = self.agents['assigner'].execute(result)
                
                # Step 3: Validate
                is_valid, errors = self.agents['validator'].execute(result)
                
                # Step 4: Check output
                output_ok = self.agents['checker'].execute(result)
                
                # Check if we're done
                if is_valid and output_ok:
                    self.log(f"✅ Extraction successful after {iteration} iterations!", "success")
                    result.extraction_iterations = iteration
                    break
                
                # Log issues
                if not is_valid:
                    self.log(f"Validation failed with {len(errors)} errors", "warning")
                if not output_ok:
                    self.log("Output format check failed", "warning")
                
                # Prepare for next iteration
                if iteration < self.max_iterations:
                    self.log("Preparing for next iteration...")
                    time.sleep(0.5)  # Brief pause
            
            if iteration >= self.max_iterations:
                self.log(f"⚠️ Reached max iterations ({self.max_iterations})", "warning")
            
            self.status = "completed"
            return result
            
        except Exception as e:
            self.log(f"Coordination failed: {str(e)}", "error")
            self.status = "error"
            return None
    
    def _re_extract_with_feedback(self, pdf_file, previous_result: FormExtractionResult) -> FormExtractionResult:
        """Re-extract with feedback from validation"""
        # This is where we could implement smarter re-extraction
        # For now, just re-run extraction
        return self.agents['extractor'].execute(pdf_file)

# Utility Functions
def get_openai_client():
    """Get OpenAI client if available"""
    if not OPENAI_AVAILABLE:
        return None
    
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key and hasattr(st, 'secrets'):
        api_key = st.secrets.get('OPENAI_API_KEY')
    
    if api_key:
        return OpenAI(api_key=api_key)
    
    return None

# Display Functions
def display_extraction_result(result: FormExtractionResult):
    """Display extraction result in UI"""
    st.markdown("### 📊 Extraction Results")
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Form", result.form_number)
    with col2:
        st.metric("Parts", len(result.parts))
    with col3:
        st.metric("Total Fields", result.total_fields)
    with col4:
        if result.is_valid:
            st.markdown('<span class="validation-pass">✅ Valid</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="validation-fail">❌ Invalid</span>', unsafe_allow_html=True)
    
    # Parts breakdown
    with st.expander("Parts Breakdown", expanded=True):
        for part_num in sorted(result.parts.keys()):
            part = result.parts[part_num]
            st.markdown(f"**Part {part_num}**: {part.part_title}")
            
            # Show sample fields
            all_fields = part.get_all_fields_flat()
            st.caption(f"{len(all_fields)} fields")
            
            # Show first few fields
            for field in all_fields[:5]:
                indent = "  " * (field.item_number.count(chr) for chr in 'abcdefghij' if chr in field.item_number)
                st.markdown(f'<div class="field-output">{indent}{field.key}: {field.label}</div>', 
                          unsafe_allow_html=True)
            
            if len(all_fields) > 5:
                st.caption(f"... and {len(all_fields) - 5} more fields")
    
    # Validation errors
    if result.validation_errors:
        with st.expander(f"⚠️ Validation Issues ({len(result.validation_errors)})", expanded=False):
            for error in result.validation_errors:
                st.warning(error)
    
    # Output format
    with st.expander("Output Format", expanded=False):
        output = result.to_output_format()
        
        # Show sample
        sample_keys = list(output.keys())[:20]
        for key in sorted(sample_keys):
            value = output[key]
            if value and not key.endswith('_title'):
                st.code(f'{key} = "{value}"')
            elif not value:
                st.code(f'{key} = null')

# Main Application
def main():
    st.markdown('<div class="main-header"><h1>🤖 Multi-Agent USCIS Form Reader</h1><p>Recursive Extraction with Validation Loop</p></div>', 
               unsafe_allow_html=True)
    
    # Initialize session state
    if 'extraction_result' not in st.session_state:
        st.session_state.extraction_result = None
    
    # Sidebar
    with st.sidebar:
        st.markdown("## ⚙️ Configuration")
        
        max_iterations = st.slider("Max Iterations", 1, 10, 5)
        show_agent_logs = st.checkbox("Show Agent Logs", value=True)
        
        # OpenAI status
        if OPENAI_AVAILABLE:
            client = get_openai_client()
            if client:
                st.success("✅ OpenAI Available")
            else:
                st.warning("⚠️ OpenAI API key not configured")
        else:
            st.error("❌ OpenAI not installed")
        
        # PyMuPDF status
        if PYMUPDF_AVAILABLE:
            st.success("✅ PyMuPDF Available")
        else:
            st.error("❌ PyMuPDF not installed")
            st.caption("Install with: pip install PyMuPDF")
    
    # Main content
    st.markdown("## Upload USCIS Form")
    
    uploaded_file = st.file_uploader(
        "Choose a USCIS PDF form",
        type=['pdf'],
        help="Upload forms like I-539, I-129, G-28, etc."
    )
    
    if uploaded_file:
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.success(f"✅ {uploaded_file.name} uploaded")
        
        with col2:
            if st.button("🚀 Extract", type="primary", use_container_width=True):
                # Create containers
                if show_agent_logs:
                    st.session_state.agent_container = st.container()
                
                progress_container = st.container()
                
                with progress_container:
                    with st.spinner("Extracting with multi-agent system..."):
                        # Create coordinator
                        coordinator = CoordinatorAgent(max_iterations=max_iterations)
                        
                        # Execute extraction
                        result = coordinator.execute(uploaded_file)
                        
                        if result:
                            st.session_state.extraction_result = result
                            st.success("✅ Extraction complete!")
                        else:
                            st.error("❌ Extraction failed")
    
    # Display results
    if st.session_state.extraction_result:
        st.markdown("---")
        display_extraction_result(st.session_state.extraction_result)
        
        # Export options
        st.markdown("### 📥 Export Options")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("Export as JSON", use_container_width=True):
                output = st.session_state.extraction_result.to_output_format()
                json_str = json.dumps(output, indent=2)
                
                st.download_button(
                    "⬇️ Download JSON",
                    json_str,
                    f"{st.session_state.extraction_result.form_number}_extracted.json",
                    mime="application/json"
                )
        
        with col2:
            if st.button("Export Structure", use_container_width=True):
                structure = {
                    "form_number": st.session_state.extraction_result.form_number,
                    "form_title": st.session_state.extraction_result.form_title,
                    "parts": {
                        part_num: part.to_dict() 
                        for part_num, part in st.session_state.extraction_result.parts.items()
                    }
                }
                json_str = json.dumps(structure, indent=2)
                
                st.download_button(
                    "⬇️ Download Structure",
                    json_str,
                    f"{st.session_state.extraction_result.form_number}_structure.json",
                    mime="application/json"
                )
        
        with col3:
            if st.button("View Raw Output", use_container_width=True):
                with st.expander("Raw Output", expanded=True):
                    output = st.session_state.extraction_result.to_output_format()
                    st.json(output)

if __name__ == "__main__":
    if not PYMUPDF_AVAILABLE:
        st.error("PyMuPDF is required. Install with: pip install PyMuPDF")
    else:
        main()
