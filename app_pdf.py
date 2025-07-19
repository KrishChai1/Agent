#!/usr/bin/env python3
"""
Advanced Multi-Agent USCIS Form Reader
With Adaptive Pattern Recognition, Smart Assignment, and Questionnaire Validation
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
from enum import Enum

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
    page_title="Advanced USCIS Form Reader",
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
    .agent-card {
        background: white;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .agent-active {
        border-left: 4px solid #2196F3;
        background: #E3F2FD;
    }
    .agent-success {
        border-left: 4px solid #4CAF50;
        background: #E8F5E9;
    }
    .agent-error {
        border-left: 4px solid #f44336;
        background: #FFEBEE;
    }
    .field-card {
        background: #f5f5f5;
        border: 1px solid #ddd;
        border-radius: 4px;
        padding: 0.5rem;
        margin: 0.2rem 0;
        font-family: monospace;
    }
    .hierarchy-tree {
        font-family: monospace;
        white-space: pre;
        background: #f5f5f5;
        padding: 1rem;
        border-radius: 4px;
        overflow-x: auto;
    }
    .validation-badge {
        display: inline-block;
        padding: 0.2rem 0.5rem;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: bold;
    }
    .badge-success {
        background: #4CAF50;
        color: white;
    }
    .badge-warning {
        background: #FF9800;
        color: white;
    }
    .badge-error {
        background: #f44336;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# Enums
class FieldType(Enum):
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    SIGNATURE = "signature"
    EMAIL = "email"
    PHONE = "phone"
    ADDRESS = "address"
    NAME = "name"
    UNKNOWN = "unknown"

class ExtractionConfidence(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"

# Enhanced Data Classes
@dataclass
class FieldPattern:
    """Pattern for field recognition"""
    pattern: re.Pattern
    field_type: FieldType
    confidence: float = 1.0
    description: str = ""
    
@dataclass
class FieldNode:
    """Enhanced field node with better metadata"""
    # Core properties
    item_number: str  # e.g., "1", "1a", "2"
    label: str
    field_type: FieldType = FieldType.UNKNOWN
    value: str = ""
    
    # Hierarchy
    parent: Optional['FieldNode'] = None
    children: List['FieldNode'] = field(default_factory=list)
    
    # Location
    page: int = 1
    part_number: int = 1
    part_name: str = "Part 1"
    bbox: Optional[Tuple[float, float, float, float]] = None  # x0, y0, x1, y1
    
    # Generated key
    key: str = ""  # e.g., "P1_1a"
    
    # Extraction metadata
    confidence: ExtractionConfidence = ExtractionConfidence.LOW
    extraction_method: str = ""
    raw_text: str = ""
    patterns_matched: List[str] = field(default_factory=list)
    
    # Validation
    is_required: bool = False
    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)
    
    def add_child(self, child: 'FieldNode'):
        """Add child node"""
        child.parent = self
        self.children.append(child)
    
    def get_full_path(self) -> str:
        """Get full hierarchical path"""
        if self.parent:
            return f"{self.parent.get_full_path()}.{self.item_number}"
        return self.item_number
    
    def get_depth(self) -> int:
        """Get depth in hierarchy"""
        if self.parent:
            return self.parent.get_depth() + 1
        return 0
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "key": self.key,
            "item_number": self.item_number,
            "label": self.label,
            "type": self.field_type.value,
            "value": self.value,
            "confidence": self.confidence.value,
            "page": self.page,
            "children": [child.to_dict() for child in self.children]
        }

@dataclass
class FormSchema:
    """Schema definition for a form"""
    form_number: str
    form_title: str
    parts: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    required_fields: List[str] = field(default_factory=list)
    field_patterns: Dict[str, FieldPattern] = field(default_factory=dict)
    
    def get_expected_structure(self) -> Dict:
        """Get expected structure"""
        return {
            "form_number": self.form_number,
            "parts": self.parts,
            "required_fields": self.required_fields
        }

# Pattern Library
class PatternLibrary:
    """Library of extraction patterns"""
    
    def __init__(self):
        self.patterns = self._build_patterns()
        self.form_schemas = self._build_form_schemas()
    
    def _build_patterns(self) -> Dict[str, List[FieldPattern]]:
        """Build comprehensive pattern library"""
        return {
            "structure": [
                FieldPattern(
                    re.compile(r'^Part\s+(\d+)\.?\s*(.*)$', re.IGNORECASE),
                    FieldType.UNKNOWN,
                    1.0,
                    "Part header"
                ),
                FieldPattern(
                    re.compile(r'^Section\s+([A-Z])\.\s*(.*)$', re.IGNORECASE),
                    FieldType.UNKNOWN,
                    0.9,
                    "Section header"
                ),
            ],
            "item": [
                # Standard numbered items
                FieldPattern(
                    re.compile(r'^(\d+)\.\s+(.+?)(?:\s*\(.*\))?$'),
                    FieldType.UNKNOWN,
                    0.95,
                    "Numbered item with period"
                ),
                FieldPattern(
                    re.compile(r'^(\d+)\s+([A-Z].+?)(?:\s*\(.*\))?$'),
                    FieldType.UNKNOWN,
                    0.85,
                    "Numbered item without period"
                ),
                # Sub-items
                FieldPattern(
                    re.compile(r'^(\d+)([a-z])\.\s+(.+?)$'),
                    FieldType.UNKNOWN,
                    0.95,
                    "Sub-item with number and letter"
                ),
                FieldPattern(
                    re.compile(r'^\s*([a-z])\.\s+(.+?)$'),
                    FieldType.UNKNOWN,
                    0.9,
                    "Letter-only sub-item"
                ),
            ],
            "field_type": [
                # Names
                FieldPattern(
                    re.compile(r'(family|last|sur)\s*name', re.IGNORECASE),
                    FieldType.NAME,
                    0.95,
                    "Family/Last name"
                ),
                FieldPattern(
                    re.compile(r'(given|first)\s*name', re.IGNORECASE),
                    FieldType.NAME,
                    0.95,
                    "Given/First name"
                ),
                FieldPattern(
                    re.compile(r'middle\s*name', re.IGNORECASE),
                    FieldType.NAME,
                    0.95,
                    "Middle name"
                ),
                # Dates
                FieldPattern(
                    re.compile(r'date\s*of\s*birth', re.IGNORECASE),
                    FieldType.DATE,
                    0.95,
                    "Date of birth"
                ),
                FieldPattern(
                    re.compile(r'(expir|issue|effective)\s*date', re.IGNORECASE),
                    FieldType.DATE,
                    0.9,
                    "Expiration/Issue date"
                ),
                # Numbers
                FieldPattern(
                    re.compile(r'(a[\-\s]?number|alien\s*(registration)?\s*number)', re.IGNORECASE),
                    FieldType.NUMBER,
                    0.95,
                    "A-Number"
                ),
                FieldPattern(
                    re.compile(r'(ssn|social\s*security)', re.IGNORECASE),
                    FieldType.NUMBER,
                    0.95,
                    "SSN"
                ),
                # Contact
                FieldPattern(
                    re.compile(r'(e[\-\s]?mail|email)', re.IGNORECASE),
                    FieldType.EMAIL,
                    0.95,
                    "Email"
                ),
                FieldPattern(
                    re.compile(r'(phone|telephone|mobile)', re.IGNORECASE),
                    FieldType.PHONE,
                    0.95,
                    "Phone"
                ),
                # Address
                FieldPattern(
                    re.compile(r'(street|address|apt|suite)', re.IGNORECASE),
                    FieldType.ADDRESS,
                    0.9,
                    "Address"
                ),
                # Checkbox/Radio
                FieldPattern(
                    re.compile(r'^\s*[□☐]\s*(.+)$'),
                    FieldType.CHECKBOX,
                    0.95,
                    "Checkbox"
                ),
                FieldPattern(
                    re.compile(r'(are you|have you|do you|is this|was)', re.IGNORECASE),
                    FieldType.CHECKBOX,
                    0.85,
                    "Yes/No question"
                ),
            ]
        }
    
    def _build_form_schemas(self) -> Dict[str, FormSchema]:
        """Build form schemas"""
        schemas = {}
        
        # I-539 Schema
        schemas["I-539"] = FormSchema(
            form_number="I-539",
            form_title="Application to Extend/Change Nonimmigrant Status",
            parts={
                1: {
                    "title": "Information About You",
                    "items": {
                        "1": {"label": "Your Full Legal Name", "sub_items": ["a", "b", "c"]},
                        "2": {"label": "Alien Registration Number (A-Number)"},
                        "3": {"label": "Date of Birth"},
                        "4": {"label": "U.S. Mailing Address"},
                        "5": {"label": "Physical Address"},
                        "6": {"label": "Contact Information"}
                    }
                },
                2: {"title": "Application Type"},
                3: {"title": "Processing Information"},
                4: {"title": "Additional Information"},
                5: {"title": "Applicant's Statement"},
                6: {"title": "Interpreter's Contact Information"},
                7: {"title": "Contact Information"},
                8: {"title": "Additional Information"}
            },
            required_fields=["P1_1a", "P1_1b", "P1_2", "P1_3"]
        )
        
        # G-28 Schema
        schemas["G-28"] = FormSchema(
            form_number="G-28",
            form_title="Notice of Entry of Appearance",
            parts={
                1: {"title": "Information About Attorney"},
                2: {"title": "Information About Representative"},
                3: {"title": "Client Information"},
                4: {"title": "Client Consent"},
                5: {"title": "Signature of Attorney"},
                6: {"title": "Signature of Client"}
            },
            required_fields=["P1_2a", "P1_2b", "P3_6a", "P3_6b", "P3_9"]
        )
        
        return schemas
    
    def get_patterns_for_context(self, context: str) -> List[FieldPattern]:
        """Get relevant patterns for context"""
        relevant_patterns = []
        
        for category, patterns in self.patterns.items():
            if category == context or context == "all":
                relevant_patterns.extend(patterns)
        
        return sorted(relevant_patterns, key=lambda p: p.confidence, reverse=True)

# Base Agent Class
class BaseAgent(ABC):
    """Enhanced base agent with better logging"""
    
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.status = "idle"
        self.logs = []
        self.errors = []
        self.start_time = None
        self.end_time = None
    
    @abstractmethod
    def execute(self, *args, **kwargs) -> Any:
        pass
    
    def log(self, message: str, level: str = "info", details: Any = None):
        """Enhanced logging"""
        entry = {
            "timestamp": datetime.now(),
            "message": message,
            "level": level,
            "details": details
        }
        self.logs.append(entry)
        
        # Display in UI
        self._display_log(entry)
    
    def _display_log(self, entry: Dict):
        """Display log in UI"""
        if hasattr(st.session_state, 'agent_container'):
            with st.session_state.agent_container:
                css_class = "agent-card"
                if entry["level"] == "error":
                    css_class += " agent-error"
                elif entry["level"] == "success":
                    css_class += " agent-success"
                elif self.status == "active":
                    css_class += " agent-active"
                
                st.markdown(
                    f'<div class="{css_class}">'
                    f'<strong>{self.name}</strong>: {entry["message"]}'
                    f'</div>', 
                    unsafe_allow_html=True
                )
    
    def start(self):
        """Start agent execution"""
        self.status = "active"
        self.start_time = datetime.now()
        self.log(f"Starting {self.description}")
    
    def complete(self, success: bool = True):
        """Complete agent execution"""
        self.end_time = datetime.now()
        duration = (self.end_time - self.start_time).total_seconds()
        
        if success:
            self.status = "completed"
            self.log(f"Completed successfully in {duration:.2f}s", "success")
        else:
            self.status = "error"
            self.log(f"Failed after {duration:.2f}s", "error")

# Adaptive Pattern Extractor Agent
class AdaptivePatternExtractor(BaseAgent):
    """Extracts fields using adaptive pattern matching"""
    
    def __init__(self):
        super().__init__(
            "Adaptive Pattern Extractor",
            "Extracts form fields using adaptive pattern recognition"
        )
        self.pattern_library = PatternLibrary()
        self.doc = None
    
    def execute(self, pdf_file) -> FormExtractionResult:
        """Execute adaptive extraction"""
        self.start()
        
        try:
            # Open PDF
            pdf_bytes = pdf_file.read() if hasattr(pdf_file, 'read') else pdf_file
            self.doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            # Identify form
            form_info = self._identify_form()
            schema = self.pattern_library.form_schemas.get(form_info['number'])
            
            result = FormExtractionResult(
                form_number=form_info['number'],
                form_title=form_info['title']
            )
            
            # Extract with adaptive patterns
            for page_num in range(len(self.doc)):
                self._extract_page_adaptive(page_num, result, schema)
            
            # Post-process extraction
            self._post_process_extraction(result, schema)
            
            # Calculate metrics
            for part in result.parts.values():
                result.total_fields += len(part.get_all_fields_flat())
            
            self.log(f"Extracted {len(result.parts)} parts, {result.total_fields} fields")
            self.complete()
            return result
            
        except Exception as e:
            self.log(f"Extraction failed: {str(e)}", "error", traceback.format_exc())
            self.complete(False)
            raise
        finally:
            if self.doc:
                self.doc.close()
    
    def _identify_form(self) -> Dict:
        """Identify form type with confidence"""
        first_page_text = self.doc[0].get_text()
        
        # Check against known forms
        for form_num, schema in self.pattern_library.form_schemas.items():
            if form_num in first_page_text:
                # Verify with title
                if schema.form_title.lower() in first_page_text.lower():
                    self.log(f"Identified form: {form_num} - {schema.form_title}", "success")
                    return {"number": form_num, "title": schema.form_title}
        
        # Fallback
        self.log("Could not identify form type", "warning")
        return {"number": "Unknown", "title": "Unknown Form"}
    
    def _extract_page_adaptive(self, page_num: int, result: FormExtractionResult, 
                              schema: Optional[FormSchema]):
        """Extract page using adaptive patterns"""
        page = self.doc[page_num]
        
        # Get text with layout preservation
        blocks = page.get_text("dict")
        
        # Extract hierarchical structure
        current_part = None
        field_stack = []  # Stack for maintaining hierarchy
        
        for block in blocks["blocks"]:
            if block["type"] == 0:  # Text block
                for line in block["lines"]:
                    text = self._get_line_text(line)
                    if not text.strip():
                        continue
                    
                    # Try to match patterns
                    matched_field = self._match_patterns(text, line, page_num)
                    
                    if matched_field:
                        # Handle part headers
                        if matched_field.label.lower().startswith("part"):
                            current_part = self._handle_part_header(matched_field, result)
                            field_stack = []
                        
                        # Handle fields
                        elif current_part:
                            self._place_field_in_hierarchy(
                                matched_field, current_part, field_stack, schema
                            )
    
    def _match_patterns(self, text: str, line_data: Dict, page_num: int) -> Optional[FieldNode]:
        """Match text against patterns"""
        text = text.strip()
        
        # Get all patterns
        all_patterns = self.pattern_library.get_patterns_for_context("all")
        
        best_match = None
        best_confidence = 0.0
        
        for pattern_def in all_patterns:
            match = pattern_def.pattern.match(text)
            if match:
                # Calculate confidence based on pattern and context
                confidence = self._calculate_confidence(
                    pattern_def, match, text, line_data
                )
                
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = (pattern_def, match)
        
        if best_match:
            pattern_def, match = best_match
            return self._create_field_from_match(
                pattern_def, match, text, line_data, page_num, best_confidence
            )
        
        return None
    
    def _calculate_confidence(self, pattern: FieldPattern, match: re.Match, 
                            text: str, line_data: Dict) -> float:
        """Calculate match confidence"""
        base_confidence = pattern.confidence
        
        # Adjust based on text properties
        font_size = self._get_font_size(line_data)
        is_bold = self._is_bold(line_data)
        
        # Boost confidence for headers
        if font_size > 12 or is_bold:
            base_confidence *= 1.1
        
        # Check pattern quality
        if match.group(0) == text:  # Full match
            base_confidence *= 1.05
        
        return min(base_confidence, 1.0)
    
    def _create_field_from_match(self, pattern: FieldPattern, match: re.Match,
                               text: str, line_data: Dict, page_num: int,
                               confidence: float) -> FieldNode:
        """Create field node from pattern match"""
        # Extract components based on pattern
        if pattern.description == "Part header":
            part_num = match.group(1)
            part_title = match.group(2) if match.lastindex > 1 else ""
            
            return FieldNode(
                item_number=f"Part{part_num}",
                label=f"Part {part_num}" + (f": {part_title}" if part_title else ""),
                field_type=FieldType.UNKNOWN,
                page=page_num + 1,
                confidence=ExtractionConfidence.HIGH if confidence > 0.9 else ExtractionConfidence.MEDIUM,
                extraction_method="pattern",
                raw_text=text,
                patterns_matched=[pattern.description]
            )
        
        elif pattern.description in ["Numbered item with period", "Numbered item without period"]:
            item_num = match.group(1)
            label = match.group(2) if match.lastindex > 1 else text
            
            # Determine field type from label
            field_type = self._determine_field_type_smart(label)
            
            return FieldNode(
                item_number=item_num,
                label=label.strip(),
                field_type=field_type,
                page=page_num + 1,
                confidence=ExtractionConfidence.HIGH if confidence > 0.9 else ExtractionConfidence.MEDIUM,
                extraction_method="pattern",
                raw_text=text,
                patterns_matched=[pattern.description],
                bbox=self._get_bbox(line_data)
            )
        
        elif pattern.description == "Sub-item with number and letter":
            full_num = match.group(1) + match.group(2)
            label = match.group(3) if match.lastindex > 2 else text
            
            return FieldNode(
                item_number=full_num,
                label=label.strip(),
                field_type=self._determine_field_type_smart(label),
                page=page_num + 1,
                confidence=ExtractionConfidence.HIGH if confidence > 0.9 else ExtractionConfidence.MEDIUM,
                extraction_method="pattern",
                raw_text=text,
                patterns_matched=[pattern.description],
                bbox=self._get_bbox(line_data)
            )
        
        # Default field
        return FieldNode(
            item_number="",
            label=text,
            field_type=pattern.field_type,
            page=page_num + 1,
            confidence=ExtractionConfidence.LOW,
            extraction_method="pattern",
            raw_text=text,
            patterns_matched=[pattern.description]
        )
    
    def _determine_field_type_smart(self, label: str) -> FieldType:
        """Smart field type determination"""
        label_lower = label.lower()
        
        # Check against field type patterns
        field_patterns = self.pattern_library.get_patterns_for_context("field_type")
        
        for pattern in field_patterns:
            if pattern.pattern.search(label):
                return pattern.field_type
        
        # Fallback heuristics
        if any(word in label_lower for word in ['name']):
            return FieldType.NAME
        elif any(word in label_lower for word in ['date', 'born', 'birth']):
            return FieldType.DATE
        elif any(word in label_lower for word in ['number', 'no.', '#']):
            return FieldType.NUMBER
        elif any(word in label_lower for word in ['address', 'street', 'city', 'state']):
            return FieldType.ADDRESS
        elif any(word in label_lower for word in ['email', 'e-mail']):
            return FieldType.EMAIL
        elif any(word in label_lower for word in ['phone', 'tel', 'mobile']):
            return FieldType.PHONE
        elif any(word in label_lower for word in ['signature', 'sign']):
            return FieldType.SIGNATURE
        elif label_lower.startswith(('are ', 'is ', 'do ', 'have ', 'was ', 'were ')):
            return FieldType.CHECKBOX
        
        return FieldType.TEXT
    
    def _handle_part_header(self, field: FieldNode, result: FormExtractionResult) -> PartStructure:
        """Handle part header"""
        # Extract part number
        match = re.search(r'Part\s*(\d+)', field.label, re.IGNORECASE)
        if match:
            part_num = int(match.group(1))
            
            if part_num not in result.parts:
                result.parts[part_num] = PartStructure(
                    part_number=part_num,
                    part_name=f"Part {part_num}",
                    part_title=field.label
                )
            
            self.log(f"Processing {field.label}")
            return result.parts[part_num]
        
        return None
    
    def _place_field_in_hierarchy(self, field: FieldNode, part: PartStructure,
                                field_stack: List[FieldNode], schema: Optional[FormSchema]):
        """Place field in correct position in hierarchy"""
        # Determine hierarchy level
        field_level = self._determine_hierarchy_level(field)
        
        # Pop stack to appropriate level
        while field_stack and field_stack[-1].get_depth() >= field_level:
            field_stack.pop()
        
        # Find parent
        if field_stack:
            parent = field_stack[-1]
            parent.add_child(field)
        else:
            part.root_fields.append(field)
        
        # Update field metadata
        field.part_number = part.part_number
        field.part_name = part.part_name
        
        # Add to stack if it might have children
        if self._might_have_children(field, schema):
            field_stack.append(field)
    
    def _determine_hierarchy_level(self, field: FieldNode) -> int:
        """Determine hierarchy level of field"""
        item_num = field.item_number
        
        # Check if it's a sub-item
        if re.match(r'^\d+[a-z]', item_num):
            return 1  # Sub-item
        elif re.match(r'^\d+$', item_num):
            return 0  # Main item
        elif re.match(r'^[a-z]$', item_num):
            return 1  # Letter-only sub-item
        
        return 0  # Default to main level
    
    def _might_have_children(self, field: FieldNode, schema: Optional[FormSchema]) -> bool:
        """Check if field might have children"""
        # Check schema first
        if schema and field.part_number in schema.parts:
            part_schema = schema.parts[field.part_number]
            items = part_schema.get("items", {})
            
            if field.item_number in items:
                item_schema = items[field.item_number]
                return "sub_items" in item_schema
        
        # Fallback to heuristics
        label_lower = field.label.lower()
        parent_indicators = [
            'name', 'address', 'information', 'contact',
            'mailing', 'physical', 'employment', 'education'
        ]
        
        return any(indicator in label_lower for indicator in parent_indicators)
    
    def _post_process_extraction(self, result: FormExtractionResult, schema: Optional[FormSchema]):
        """Post-process extraction results"""
        # Fill in missing sub-items based on schema
        if schema:
            for part_num, part in result.parts.items():
                if part_num in schema.parts:
                    self._fill_missing_items(part, schema.parts[part_num])
        
        # Validate field relationships
        self._validate_relationships(result)
    
    def _fill_missing_items(self, part: PartStructure, part_schema: Dict):
        """Fill in missing items based on schema"""
        items = part_schema.get("items", {})
        
        for item_num, item_info in items.items():
            # Find or create main item
            main_field = None
            for field in part.root_fields:
                if field.item_number == item_num:
                    main_field = field
                    break
            
            if not main_field:
                # Create missing main item
                main_field = FieldNode(
                    item_number=item_num,
                    label=item_info.get("label", f"Item {item_num}"),
                    field_type=FieldType.UNKNOWN,
                    page=1,
                    part_number=part.part_number,
                    part_name=part.part_name,
                    confidence=ExtractionConfidence.LOW,
                    extraction_method="schema"
                )
                part.root_fields.append(main_field)
                self.log(f"Added missing field {item_num} from schema", "warning")
            
            # Check sub-items
            if "sub_items" in item_info:
                for sub_letter in item_info["sub_items"]:
                    sub_num = f"{item_num}{sub_letter}"
                    
                    # Check if sub-item exists
                    exists = any(child.item_number == sub_num for child in main_field.children)
                    
                    if not exists:
                        # Create missing sub-item
                        sub_field = FieldNode(
                            item_number=sub_num,
                            label=f"Sub-item {sub_letter}",
                            field_type=FieldType.TEXT,
                            page=main_field.page,
                            part_number=part.part_number,
                            part_name=part.part_name,
                            confidence=ExtractionConfidence.LOW,
                            extraction_method="schema"
                        )
                        main_field.add_child(sub_field)
                        self.log(f"Added missing sub-field {sub_num} from schema", "warning")
    
    def _validate_relationships(self, result: FormExtractionResult):
        """Validate field relationships"""
        for part in result.parts.values():
            # Sort root fields by item number
            part.root_fields.sort(key=lambda f: (
                int(re.search(r'\d+', f.item_number).group()) if re.search(r'\d+', f.item_number) else 999,
                f.item_number
            ))
            
            # Sort children
            for field in part.get_all_fields_flat():
                if field.children:
                    field.children.sort(key=lambda f: f.item_number)
    
    # Helper methods
    def _get_line_text(self, line: Dict) -> str:
        """Extract text from line"""
        text_parts = []
        for span in line["spans"]:
            text_parts.append(span["text"])
        return " ".join(text_parts)
    
    def _get_font_size(self, line: Dict) -> float:
        """Get average font size"""
        if line["spans"]:
            return line["spans"][0].get("size", 10)
        return 10
    
    def _is_bold(self, line: Dict) -> bool:
        """Check if text is bold"""
        if line["spans"]:
            flags = line["spans"][0].get("flags", 0)
            return bool(flags & 2**4)  # Bold flag
        return False
    
    def _get_bbox(self, line: Dict) -> Optional[Tuple[float, float, float, float]]:
        """Get bounding box"""
        if "bbox" in line:
            bbox = line["bbox"]
            return (bbox[0], bbox[1], bbox[2], bbox[3])
        return None

# Smart Key Assignment Agent
class SmartKeyAssignment(BaseAgent):
    """Assigns keys using smart logic"""
    
    def __init__(self):
        super().__init__(
            "Smart Key Assignment",
            "Assigns hierarchical keys to fields"
        )
    
    def execute(self, result: FormExtractionResult) -> FormExtractionResult:
        """Execute key assignment"""
        self.start()
        
        try:
            assigned_count = 0
            
            for part_num, part in result.parts.items():
                for field in part.get_all_fields_flat():
                    # Generate smart key
                    key = self._generate_smart_key(field)
                    field.key = key
                    assigned_count += 1
            
            self.log(f"Assigned {assigned_count} keys")
            self.complete()
            return result
            
        except Exception as e:
            self.log(f"Key assignment failed: {str(e)}", "error")
            self.complete(False)
            raise
    
    def _generate_smart_key(self, field: FieldNode) -> str:
        """Generate smart hierarchical key"""
        # Basic format: P{part}_{item}
        base_key = f"P{field.part_number}_{field.item_number}"
        
        # Clean up
        base_key = base_key.replace('.', '').replace(' ', '_')
        
        # Handle special cases
        if field.field_type == FieldType.ADDRESS and field.parent:
            # For address components, add parent context
            parent_key = f"P{field.part_number}_{field.parent.item_number}"
            return f"{parent_key}_{field.item_number}"
        
        return base_key

# Questionnaire Validator Agent
class QuestionnaireValidator(BaseAgent):
    """Validates using questionnaire approach"""
    
    def __init__(self):
        super().__init__(
            "Questionnaire Validator",
            "Validates extraction using intelligent questions"
        )
        self.validation_questions = self._build_questions()
    
    def _build_questions(self) -> List[Dict]:
        """Build validation questions"""
        return [
            {
                "id": "parts_complete",
                "question": "Are all expected parts present?",
                "check": self._check_parts_complete,
                "weight": 1.0
            },
            {
                "id": "required_fields",
                "question": "Are all required fields present?",
                "check": self._check_required_fields,
                "weight": 1.5
            },
            {
                "id": "field_hierarchy",
                "question": "Is the field hierarchy correct?",
                "check": self._check_field_hierarchy,
                "weight": 1.0
            },
            {
                "id": "field_types",
                "question": "Are field types correctly identified?",
                "check": self._check_field_types,
                "weight": 0.8
            },
            {
                "id": "key_format",
                "question": "Are all keys in correct format?",
                "check": self._check_key_format,
                "weight": 1.2
            },
            {
                "id": "data_completeness",
                "question": "Is the extraction reasonably complete?",
                "check": self._check_data_completeness,
                "weight": 1.0
            }
        ]
    
    def execute(self, result: FormExtractionResult, schema: Optional[FormSchema] = None) -> Tuple[bool, float, List[Dict]]:
        """Execute questionnaire validation"""
        self.start()
        
        try:
            validation_results = []
            total_score = 0.0
            total_weight = 0.0
            
            # Run each validation question
            for question in self.validation_questions:
                self.log(f"Checking: {question['question']}")
                
                passed, score, details = question["check"](result, schema)
                
                validation_results.append({
                    "question": question["question"],
                    "passed": passed,
                    "score": score,
                    "weight": question["weight"],
                    "details": details
                })
                
                total_score += score * question["weight"]
                total_weight += question["weight"]
                
                # Log result
                if passed:
                    self.log(f"✓ {question['question']} - Score: {score:.0%}", "success")
                else:
                    self.log(f"✗ {question['question']} - Score: {score:.0%}", "warning")
            
            # Calculate overall score
            overall_score = total_score / total_weight if total_weight > 0 else 0
            is_valid = overall_score >= 0.7  # 70% threshold
            
            # Update result
            result.validation_score = overall_score
            result.is_valid = is_valid
            
            self.log(f"Overall validation score: {overall_score:.0%}")
            self.complete()
            
            return is_valid, overall_score, validation_results
            
        except Exception as e:
            self.log(f"Validation failed: {str(e)}", "error")
            self.complete(False)
            return False, 0.0, []
    
    def _check_parts_complete(self, result: FormExtractionResult, schema: Optional[FormSchema]) -> Tuple[bool, float, str]:
        """Check if all parts are present"""
        if not schema:
            # Basic check
            has_parts = len(result.parts) > 0
            return has_parts, 1.0 if has_parts else 0.0, f"Found {len(result.parts)} parts"
        
        expected_parts = set(schema.parts.keys())
        found_parts = set(result.parts.keys())
        
        missing = expected_parts - found_parts
        extra = found_parts - expected_parts
        
        if not missing:
            return True, 1.0, "All expected parts found"
        else:
            score = len(found_parts & expected_parts) / len(expected_parts)
            details = f"Missing parts: {missing}"
            if extra:
                details += f", Extra parts: {extra}"
            return False, score, details
    
    def _check_required_fields(self, result: FormExtractionResult, schema: Optional[FormSchema]) -> Tuple[bool, float, str]:
        """Check required fields"""
        if not schema:
            return True, 1.0, "No schema to check against"
        
        all_fields = result.get_all_fields_with_keys()
        required = set(schema.required_fields)
        found = set(all_fields.keys())
        
        missing = required - found
        
        if not missing:
            return True, 1.0, "All required fields found"
        else:
            score = len(found & required) / len(required) if required else 1.0
            return False, score, f"Missing required fields: {missing}"
    
    def _check_field_hierarchy(self, result: FormExtractionResult, schema: Optional[FormSchema]) -> Tuple[bool, float, str]:
        """Check field hierarchy"""
        issues = []
        total_fields = 0
        correct_fields = 0
        
        for part in result.parts.values():
            for field in part.get_all_fields_flat():
                total_fields += 1
                
                # Check parent-child relationships
                if re.match(r'^\d+[a-z]', field.item_number):
                    # Should have a parent
                    if not field.parent:
                        issues.append(f"{field.key} should have a parent")
                    else:
                        parent_num = re.match(r'^(\d+)', field.item_number).group(1)
                        if field.parent.item_number != parent_num:
                            issues.append(f"{field.key} has wrong parent")
                        else:
                            correct_fields += 1
                else:
                    correct_fields += 1
        
        score = correct_fields / total_fields if total_fields > 0 else 0
        passed = len(issues) == 0
        
        return passed, score, f"Found {len(issues)} hierarchy issues" if issues else "Hierarchy correct"
    
    def _check_field_types(self, result: FormExtractionResult, schema: Optional[FormSchema]) -> Tuple[bool, float, str]:
        """Check field types"""
        total = 0
        correct = 0
        
        for part in result.parts.values():
            for field in part.get_all_fields_flat():
                total += 1
                if field.field_type != FieldType.UNKNOWN:
                    correct += 1
        
        score = correct / total if total > 0 else 0
        passed = score >= 0.8  # 80% should have types
        
        return passed, score, f"{correct}/{total} fields have identified types"
    
    def _check_key_format(self, result: FormExtractionResult, schema: Optional[FormSchema]) -> Tuple[bool, float, str]:
        """Check key format"""
        pattern = re.compile(r'^P\d+_\d+[a-z]?(_\w+)?$')
        
        total = 0
        correct = 0
        invalid_keys = []
        
        for part in result.parts.values():
            for field in part.get_all_fields_flat():
                total += 1
                if pattern.match(field.key):
                    correct += 1
                else:
                    invalid_keys.append(field.key)
        
        score = correct / total if total > 0 else 0
        passed = len(invalid_keys) == 0
        
        details = "All keys valid" if passed else f"Invalid keys: {invalid_keys[:5]}"
        if len(invalid_keys) > 5:
            details += f" and {len(invalid_keys) - 5} more"
        
        return passed, score, details
    
    def _check_data_completeness(self, result: FormExtractionResult, schema: Optional[FormSchema]) -> Tuple[bool, float, str]:
        """Check overall completeness"""
        # Simple heuristic: expect at least 20 fields for most forms
        min_expected = 20
        actual = result.total_fields
        
        if actual >= min_expected:
            return True, 1.0, f"Found {actual} fields (expected at least {min_expected})"
        else:
            score = actual / min_expected
            return False, score, f"Found only {actual} fields (expected at least {min_expected})"

# Output Formatter Agent
class OutputFormatter(BaseAgent):
    """Formats output correctly"""
    
    def __init__(self):
        super().__init__(
            "Output Formatter",
            "Formats extraction output"
        )
    
    def execute(self, result: FormExtractionResult) -> Dict[str, Any]:
        """Format output"""
        self.start()
        
        try:
            output = {}
            
            # Extract all fields with keys
            for part in result.parts.values():
                for field in part.get_all_fields_flat():
                    if field.key:
                        # Add field value
                        output[field.key] = field.value or ""
                        
                        # Add title for reference
                        title_key = f"{field.key}_title"
                        output[title_key] = field.label
                        
                        # Add metadata if needed
                        if field.confidence == ExtractionConfidence.LOW:
                            confidence_key = f"{field.key}_confidence"
                            output[confidence_key] = field.confidence.value
            
            self.log(f"Formatted {len(output)} output entries")
            self.complete()
            return output
            
        except Exception as e:
            self.log(f"Formatting failed: {str(e)}", "error")
            self.complete(False)
            raise

# Master Coordinator Agent
class MasterCoordinator(BaseAgent):
    """Coordinates all agents"""
    
    def __init__(self, max_iterations: int = 3):
        super().__init__(
            "Master Coordinator",
            "Orchestrates the extraction process"
        )
        self.max_iterations = max_iterations
        self.agents = {
            'extractor': AdaptivePatternExtractor(),
            'assigner': SmartKeyAssignment(),
            'validator': QuestionnaireValidator(),
            'formatter': OutputFormatter()
        }
        self.pattern_library = PatternLibrary()
    
    def execute(self, pdf_file) -> Optional[Dict[str, Any]]:
        """Execute coordinated extraction"""
        self.start()
        
        try:
            result = None
            best_result = None
            best_score = 0.0
            
            for iteration in range(self.max_iterations):
                self.log(f"\n{'='*50}")
                self.log(f"Starting iteration {iteration + 1}/{self.max_iterations}")
                
                # Step 1: Extract
                if iteration == 0:
                    result = self.agents['extractor'].execute(pdf_file)
                else:
                    # Re-extract with improvements
                    self.log("Re-extracting with refined patterns...")
                    result = self._refine_extraction(pdf_file, result, validation_results)
                
                if not result:
                    self.log("Extraction failed", "error")
                    break
                
                # Step 2: Assign keys
                result = self.agents['assigner'].execute(result)
                
                # Step 3: Validate
                schema = self.pattern_library.form_schemas.get(result.form_number)
                is_valid, score, validation_results = self.agents['validator'].execute(result, schema)
                
                # Track best result
                if score > best_score:
                    best_score = score
                    best_result = copy.deepcopy(result)
                
                # Check if good enough
                if is_valid and score >= 0.85:
                    self.log(f"✅ Extraction successful with score {score:.0%}!", "success")
                    break
                
                # Log status
                self.log(f"Iteration {iteration + 1} score: {score:.0%}")
                
                if iteration < self.max_iterations - 1:
                    self.log("Score below threshold, refining...")
                    time.sleep(0.5)
            
            # Use best result
            if best_result:
                # Step 4: Format output
                output = self.agents['formatter'].execute(best_result)
                
                # Add metadata
                output['_metadata'] = {
                    'form_number': best_result.form_number,
                    'form_title': best_result.form_title,
                    'total_fields': best_result.total_fields,
                    'validation_score': best_score,
                    'iterations': iteration + 1
                }
                
                self.complete()
                return output
            
            self.log("No valid extraction produced", "error")
            self.complete(False)
            return None
            
        except Exception as e:
            self.log(f"Coordination failed: {str(e)}", "error", traceback.format_exc())
            self.complete(False)
            return None
    
    def _refine_extraction(self, pdf_file, previous_result: FormExtractionResult,
                         validation_results: List[Dict]) -> FormExtractionResult:
        """Refine extraction based on validation feedback"""
        # Analyze validation results
        issues = []
        for result in validation_results:
            if not result["passed"]:
                issues.append(result)
        
        self.log(f"Refining based on {len(issues)} validation issues")
        
        # For now, just re-run extraction
        # In a production system, this would adjust patterns based on specific issues
        return self.agents['extractor'].execute(pdf_file)

# Enhanced UI Components
def display_form_structure(result: FormExtractionResult):
    """Display form structure as tree"""
    st.markdown("### 🌳 Form Structure")
    
    tree_lines = []
    
    for part_num in sorted(result.parts.keys()):
        part = result.parts[part_num]
        tree_lines.append(f"📁 Part {part_num}: {part.part_title}")
        
        for field in part.root_fields:
            _add_field_to_tree(field, tree_lines, "  ")
    
    st.markdown(
        f'<div class="hierarchy-tree">{chr(10).join(tree_lines)}</div>',
        unsafe_allow_html=True
    )

def _add_field_to_tree(field: FieldNode, lines: List[str], indent: str):
    """Add field to tree display"""
    icon = "📄" if not field.children else "📂"
    confidence_badge = {
        ExtractionConfidence.HIGH: "🟢",
        ExtractionConfidence.MEDIUM: "🟡",
        ExtractionConfidence.LOW: "🔴",
        ExtractionConfidence.NONE: "⚫"
    }[field.confidence]
    
    lines.append(
        f"{indent}{icon} {field.item_number}. {field.label} "
        f"[{field.field_type.value}] {confidence_badge}"
    )
    
    for child in field.children:
        _add_field_to_tree(child, lines, indent + "  ")

def display_validation_results(validation_results: List[Dict], overall_score: float):
    """Display validation results"""
    st.markdown("### 🔍 Validation Results")
    
    # Overall score
    col1, col2 = st.columns([1, 3])
    with col1:
        if overall_score >= 0.85:
            badge_class = "badge-success"
            status = "Excellent"
        elif overall_score >= 0.7:
            badge_class = "badge-warning"
            status = "Good"
        else:
            badge_class = "badge-error"
            status = "Needs Review"
        
        st.markdown(
            f'<div class="validation-badge {badge_class}">'
            f'{overall_score:.0%} - {status}'
            f'</div>',
            unsafe_allow_html=True
        )
    
    with col2:
        st.progress(overall_score)
    
    # Individual results
    with st.expander("Detailed Validation Results", expanded=False):
        for result in validation_results:
            icon = "✅" if result["passed"] else "❌"
            st.markdown(
                f"{icon} **{result['question']}** - "
                f"Score: {result['score']:.0%} (Weight: {result['weight']})"
            )
            if result["details"]:
                st.caption(result["details"])

# Main Application
def main():
    st.markdown(
        '<div class="main-header">'
        '<h1>🤖 Advanced USCIS Form Reader</h1>'
        '<p>Multi-Agent System with Adaptive Pattern Recognition</p>'
        '</div>', 
        unsafe_allow_html=True
    )
    
    # Initialize session state
    if 'extraction_output' not in st.session_state:
        st.session_state.extraction_output = None
    if 'extraction_result' not in st.session_state:
        st.session_state.extraction_result = None
    
    # Sidebar
    with st.sidebar:
        st.markdown("## ⚙️ Configuration")
        
        max_iterations = st.slider("Max Iterations", 1, 5, 3)
        show_agent_logs = st.checkbox("Show Agent Activity", value=True)
        show_structure = st.checkbox("Show Form Structure", value=True)
        
        st.markdown("---")
        st.markdown("### 📊 System Status")
        
        # Check dependencies
        if PYMUPDF_AVAILABLE:
            st.success("✅ PyMuPDF Ready")
        else:
            st.error("❌ PyMuPDF Not Installed")
            st.code("pip install PyMuPDF")
        
        if OPENAI_AVAILABLE:
            if os.environ.get('OPENAI_API_KEY'):
                st.success("✅ OpenAI Ready")
            else:
                st.warning("⚠️ OpenAI Key Missing")
        else:
            st.info("ℹ️ OpenAI Optional")
    
    # Main content
    st.markdown("## 📄 Upload USCIS Form")
    
    uploaded_file = st.file_uploader(
        "Choose a PDF form",
        type=['pdf'],
        help="Supported forms: I-539, I-129, G-28, I-90, I-485, I-765, N-400"
    )
    
    if uploaded_file:
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            st.success(f"✅ Uploaded: {uploaded_file.name}")
        
        with col2:
            process_btn = st.button(
                "🚀 Extract",
                type="primary",
                use_container_width=True
            )
        
        with col3:
            if st.session_state.extraction_output:
                st.button(
                    "🔄 Reset",
                    use_container_width=True,
                    on_click=lambda: st.session_state.update({
                        'extraction_output': None,
                        'extraction_result': None
                    })
                )
        
        if process_btn:
            # Create containers
            if show_agent_logs:
                st.session_state.agent_container = st.container()
            
            with st.spinner("Processing with multi-agent system..."):
                # Run extraction
                coordinator = MasterCoordinator(max_iterations=max_iterations)
                output = coordinator.execute(uploaded_file)
                
                if output:
                    st.session_state.extraction_output = output
                    st.session_state.extraction_result = coordinator.agents['extractor'].doc
                    st.success("✅ Extraction Complete!")
                else:
                    st.error("❌ Extraction Failed")
    
    # Display results
    if st.session_state.extraction_output:
        st.markdown("---")
        st.markdown("## 📊 Extraction Results")
        
        output = st.session_state.extraction_output
        metadata = output.get('_metadata', {})
        
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Form", metadata.get('form_number', 'Unknown'))
        with col2:
            st.metric("Fields", metadata.get('total_fields', 0))
        with col3:
            score = metadata.get('validation_score', 0)
            st.metric("Score", f"{score:.0%}")
        with col4:
            st.metric("Iterations", metadata.get('iterations', 1))
        
        # Export options
        st.markdown("### 💾 Export Options")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Clean output for export
            export_data = {k: v for k, v in output.items() if not k.startswith('_')}
            json_str = json.dumps(export_data, indent=2, ensure_ascii=False)
            
            st.download_button(
                "📥 Download JSON",
                json_str,
                f"{metadata.get('form_number', 'form')}_extracted.json",
                mime="application/json",
                use_container_width=True
            )
        
        with col2:
            # CSV export
            import csv
            import io
            
            csv_buffer = io.StringIO()
            writer = csv.writer(csv_buffer)
            writer.writerow(["Field Key", "Value", "Label"])
            
            for key, value in sorted(export_data.items()):
                if not key.endswith('_title') and not key.endswith('_confidence'):
                    label = export_data.get(f"{key}_title", "")
                    writer.writerow([key, value, label])
            
            st.download_button(
                "📥 Download CSV",
                csv_buffer.getvalue(),
                f"{metadata.get('form_number', 'form')}_extracted.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        with col3:
            if st.button("👁️ View Raw Output", use_container_width=True):
                with st.expander("Raw JSON Output", expanded=True):
                    st.json(export_data)
        
        # Field browser
        st.markdown("### 🔍 Field Browser")
        
        search_term = st.text_input("Search fields", placeholder="e.g., name, date, number")
        
        # Filter and display fields
        filtered_fields = {}
        for key, value in sorted(output.items()):
            if key.startswith('_') or key.endswith('_title') or key.endswith('_confidence'):
                continue
            
            label = output.get(f"{key}_title", "")
            
            if search_term:
                search_lower = search_term.lower()
                if (search_lower in key.lower() or 
                    search_lower in str(value).lower() or 
                    search_lower in label.lower()):
                    filtered_fields[key] = (value, label)
            else:
                filtered_fields[key] = (value, label)
        
        # Display filtered fields
        if filtered_fields:
            st.info(f"Showing {len(filtered_fields)} fields")
            
            for key, (value, label) in list(filtered_fields.items())[:50]:
                col1, col2, col3 = st.columns([2, 3, 3])
                
                with col1:
                    st.markdown(f'<div class="field-card">{key}</div>', unsafe_allow_html=True)
                with col2:
                    st.text(label[:50] + "..." if len(label) > 50 else label)
                with col3:
                    if value:
                        st.text(str(value)[:50] + "..." if len(str(value)) > 50 else str(value))
                    else:
                        st.text("(empty)")
            
            if len(filtered_fields) > 50:
                st.warning(f"Showing first 50 of {len(filtered_fields)} results")
        else:
            st.warning("No fields match your search")

if __name__ == "__main__":
    main()
