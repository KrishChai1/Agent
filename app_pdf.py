#!/usr/bin/env python3
"""
Advanced Multi-Agent USCIS Form Reader
With Adaptive Pattern Recognition, Smart Assignment, and Questionnaire Validation
FIXED: Correct class definition order
"""

import os
import json
import re
import time
import hashlib
import traceback
import io
import csv
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

# ===== ENUMS - Define first =====
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

# ===== DATA CLASSES - Define second (in dependency order) =====

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

# ===== PATTERN LIBRARY - Now safe to define =====
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

# ===== BASE AGENT CLASS =====
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

# ===== AGENT IMPLEMENTATIONS =====

# Include all your agent classes here in this order:
# 1. AdaptivePatternExtractor
# 2. SmartKeyAssignment  
# 3. QuestionnaireValidator
# 4. OutputFormatter
# 5. MasterCoordinator

# [Copy the rest of your agent classes here, they should work now that the dependencies are defined]

# ===== MAIN APPLICATION =====
def main():
    st.markdown(
        '<div class="main-header">'
        '<h1>🤖 Advanced USCIS Form Reader</h1>'
        '<p>Multi-Agent System with Adaptive Pattern Recognition</p>'
        '</div>', 
        unsafe_allow_html=True
    )
    
    # Check dependencies first
    if not PYMUPDF_AVAILABLE:
        st.error("❌ PyMuPDF is required but not installed!")
        st.code("pip install PyMuPDF")
        st.info("After installing, refresh this page.")
        st.stop()
    
    st.success("✅ All dependencies loaded successfully!")
    
    # [Continue with the rest of your main() function]

if __name__ == "__main__":
    main()
