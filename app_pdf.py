#!/usr/bin/env python3
"""
Enhanced Agentic USCIS Form Reader - Final Complete Version
- Fixed Part detection (all parts)
- Fixed Field extraction (1, 1a, 1b, 1c, etc.)
- Complete Knowledge Base integration
- Smart validation with self-correction
- Enhanced mapping with dropdowns
- Questionnaire support
- Full export capabilities
"""

import os
import json
import re
import time
import hashlib
import traceback
import io
import csv
import pickle
import contextlib
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Set, Union
from dataclasses import dataclass, field, asdict
from collections import defaultdict, OrderedDict
from abc import ABC, abstractmethod
import copy
from enum import Enum
from pathlib import Path

import streamlit as st
import pandas as pd

# Initialize globals
OPENAI_AVAILABLE = False
OpenAI = None
XLSXWRITER_AVAILABLE = False

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

try:
    import xlsxwriter
    XLSXWRITER_AVAILABLE = True
except ImportError:
    XLSXWRITER_AVAILABLE = False

# Page config
st.set_page_config(
    page_title="Enhanced Agentic USCIS Form Reader",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Enhanced CSS Styling
st.markdown("""
<style>
    /* Main Header */
    .main-header {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        color: white;
        padding: 2rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    /* Agent Cards */
    .agent-card {
        background: white;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        transition: all 0.3s ease;
    }
    
    .agent-active {
        border-left: 4px solid #2196F3;
        background: #E3F2FD;
        animation: pulse 1s infinite;
    }
    
    .agent-success {
        border-left: 4px solid #4CAF50;
        background: #E8F5E9;
    }
    
    .agent-error {
        border-left: 4px solid #f44336;
        background: #FFEBEE;
    }
    
    /* Knowledge Base Indicator */
    .kb-indicator {
        background: linear-gradient(45deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        display: inline-block;
        font-weight: bold;
        margin: 0.5rem 0;
    }
    
    /* Field Cards */
    .field-card {
        background: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        transition: all 0.2s ease;
    }
    
    .field-card:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        transform: translateY(-2px);
    }
    
    /* Part Header */
    .part-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1.2rem;
        border-radius: 8px;
        margin: 1rem 0;
        font-weight: bold;
        box-shadow: 0 3px 6px rgba(0,0,0,0.1);
    }
    
    /* Mapping Controls */
    .mapping-controls {
        background: #f0f7ff;
        border: 2px solid #2196F3;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    
    /* Questionnaire Item */
    .questionnaire-item {
        background: #fff3cd;
        border-left: 4px solid #ffc107;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 6px;
    }
    
    /* Checkbox Options */
    .checkbox-option {
        background: #e8f5e9;
        border: 1px solid #4caf50;
        padding: 0.25rem 0.75rem;
        margin: 0.25rem;
        border-radius: 15px;
        display: inline-block;
        font-size: 0.9em;
    }
    
    .checkbox-selected {
        background: #4caf50;
        color: white;
        font-weight: bold;
    }
    
    /* Action Buttons */
    .action-button {
        padding: 0.5rem 1rem;
        border-radius: 20px;
        border: none;
        font-weight: bold;
        cursor: pointer;
        transition: all 0.3s ease;
        margin: 0.25rem;
    }
    
    .action-button:hover {
        transform: scale(1.05);
        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    }
    
    /* Animation */
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.8; }
        100% { opacity: 1; }
    }
    
    @keyframes learning {
        0% { transform: scale(1); }
        50% { transform: scale(1.05); }
        100% { transform: scale(1); }
    }
    
    /* Mapping Dropdown */
    .mapping-dropdown {
        background: #f8f9fa;
        border: 2px solid #2196F3;
        border-radius: 4px;
        padding: 0.5rem;
        width: 100%;
    }
    
    /* Debug Info */
    .debug-info {
        background: #f0f0f0;
        border: 1px solid #ccc;
        border-radius: 4px;
        padding: 1rem;
        font-family: monospace;
        font-size: 0.9em;
    }
</style>
""", unsafe_allow_html=True)

# ===== ENUMS =====
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
    CURRENCY = "currency"
    PERCENTAGE = "percentage"
    UNKNOWN = "unknown"

class ExtractionConfidence(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"

class MappingStatus(Enum):
    MAPPED = "mapped"
    UNMAPPED = "unmapped"
    MANUAL = "manual"
    SUGGESTED = "suggested"
    REVIEW = "review"
    QUESTIONNAIRE = "questionnaire"

class AgentRole(Enum):
    EXTRACTOR = "extractor"
    VALIDATOR = "validator"
    MAPPER = "mapper"
    KNOWLEDGE = "knowledge"
    QUESTIONNAIRE = "questionnaire"

# ===== KNOWLEDGE BASE =====
class FormKnowledgeBase:
    """Knowledge base for USCIS forms with enhanced patterns"""
    
    def __init__(self):
        self.form_structures = self._init_form_structures()
        self.field_patterns = self._init_field_patterns()
        self.validation_rules = self._init_validation_rules()
        self.common_values = self._init_common_values()
        self.part_detection_patterns = self._init_part_patterns()
        
    def _init_form_structures(self) -> Dict[str, Dict]:
        """Initialize known form structures"""
        return {
            "I-130": {
                "title": "Petition for Alien Relative",
                "parts": {
                    1: "Information About You",
                    2: "Information About Your Relative", 
                    3: "Biographic Information",
                    4: "Information About Your Family",
                    5: "Other Information",
                    6: "Statement, Contact Information, Declaration, and Signature"
                },
                "expected_fields": 85,
                "page_count": 12,
                "first_fields": ["Family Name", "Given Name", "Middle Name"]
            },
            "I-485": {
                "title": "Application to Register Permanent Residence",
                "parts": {
                    1: "Information About You",
                    2: "Application Type or Filing Category",
                    3: "Additional Information About You",
                    4: "Address History",
                    5: "Marital History",
                    6: "Information About Your Children",
                    7: "Biographic Information",
                    8: "General Eligibility and Inadmissibility Grounds",
                    9: "Accommodations for Individuals With Disabilities",
                    10: "Applicant's Statement, Contact Information, Declaration, Certification, and Signature",
                    11: "Interpreter's Contact Information, Certification, and Signature",
                    12: "Contact Information, Declaration, and Signature of the Person Preparing this Application"
                },
                "expected_fields": 120,
                "page_count": 20,
                "first_fields": ["Family Name", "Given Name", "Middle Name", "Alien Registration Number"]
            },
            "I-90": {
                "title": "Application to Replace Permanent Resident Card",
                "parts": {
                    1: "Information About You",
                    2: "Application Type",
                    3: "Processing Information",
                    4: "Accommodations for Individuals With Disabilities and/or Impairments",
                    5: "Applicant's Statement, Contact Information, Certification, and Signature",
                    6: "Interpreter's Contact Information, Certification, and Signature",
                    7: "Contact Information, Declaration, and Signature"
                },
                "expected_fields": 60,
                "page_count": 10,
                "first_fields": ["Family Name", "Given Name", "Middle Name", "A-Number"]
            },
            "I-765": {
                "title": "Application for Employment Authorization",
                "parts": {
                    1: "Reason for Applying",
                    2: "Information About You",
                    3: "Applicant's Statement, Contact Information, Certification, and Signature",
                    4: "Interpreter's Contact Information, Certification, and Signature",
                    5: "Contact Information, Declaration, and Signature of the Person Preparing this Application"
                },
                "expected_fields": 45,
                "page_count": 7,
                "first_fields": ["Reason for Applying", "Family Name", "Given Name"]
            },
            "I-129": {
                "title": "Petition for a Nonimmigrant Worker",
                "parts": {
                    1: "Petitioner Information",
                    2: "Information About This Petition",
                    3: "Beneficiary Information",
                    4: "Processing Information",
                    5: "Basic Information About the Proposed Employment and Employer",
                    6: "Additional Information",
                    7: "Signature",
                    8: "Contact Information, Declaration, and Signature of the Person Preparing this Petition"
                },
                "expected_fields": 100,
                "page_count": 38,
                "has_supplements": True,
                "first_fields": ["Petitioner Name", "EIN", "Family Name of Beneficiary"]
            }
        }
    
    def _init_part_patterns(self) -> List[Dict]:
        """Initialize patterns for detecting part headers"""
        return [
            {
                'pattern': r'^Part\s+(\d+)[.:]\s*(.+)$',
                'type': 'standard',
                'confidence': 0.9
            },
            {
                'pattern': r'^Part\s+(\d+)\s+[-–—]\s*(.+)$',
                'type': 'dash',
                'confidence': 0.9
            },
            {
                'pattern': r'^Part\s+(\d+)\s*$',
                'type': 'number_only',
                'confidence': 0.7
            },
            {
                'pattern': r'^PART\s+(\d+)[.:]\s*(.+)$',
                'type': 'uppercase',
                'confidence': 0.9
            },
            {
                'pattern': r'^Section\s+([A-Z])[.:]\s*(.+)$',
                'type': 'section',
                'confidence': 0.8
            }
        ]
    
    def _init_field_patterns(self) -> Dict[str, Dict]:
        """Initialize field extraction patterns"""
        return {
            "name_fields": {
                "patterns": [
                    r"Family Name \(Last Name\)",
                    r"Given Name \(First Name\)",
                    r"Middle Name",
                    r"Name \(Family Name\)",
                    r"Name \(Given Name\)",
                    r"Full Name",
                    r"Other Names Used"
                ],
                "type": FieldType.NAME
            },
            "date_fields": {
                "patterns": [
                    r"Date of Birth",
                    r"Date of Filing",
                    r"Expiration Date",
                    r"Date of Last Entry",
                    r"Date From",
                    r"Date To",
                    r"Marriage Date",
                    r"Divorce Date"
                ],
                "type": FieldType.DATE,
                "format": "MM/DD/YYYY"
            },
            "number_fields": {
                "patterns": [
                    r"A-Number",
                    r"Alien Registration Number",
                    r"USCIS Online Account Number",
                    r"Social Security Number",
                    r"Receipt Number",
                    r"I-94 Number",
                    r"Passport Number",
                    r"EIN",
                    r"Priority Date"
                ],
                "type": FieldType.NUMBER
            },
            "address_fields": {
                "patterns": [
                    r"Street Number and Name",
                    r"Apt\.|Suite|Unit",
                    r"City or Town",
                    r"State",
                    r"ZIP Code",
                    r"Postal Code",
                    r"Province",
                    r"Country",
                    r"Mailing Address",
                    r"Physical Address"
                ],
                "type": FieldType.ADDRESS
            },
            "checkbox_fields": {
                "patterns": [
                    r"Check|Select",
                    r"Mark",
                    r"Indicate",
                    r"Yes\s+No",
                    r"□|☐|☑|☒"
                ],
                "type": FieldType.CHECKBOX
            }
        }
    
    def _init_validation_rules(self) -> Dict[str, Dict]:
        """Initialize validation rules"""
        return {
            "a_number": {
                "pattern": r"^[Aa]?[-\s]?\d{7,9}$",
                "description": "7-9 digits, may start with A"
            },
            "ssn": {
                "pattern": r"^\d{3}-?\d{2}-?\d{4}$",
                "description": "XXX-XX-XXXX format"
            },
            "date": {
                "pattern": r"^\d{2}/\d{2}/\d{4}$",
                "description": "MM/DD/YYYY format"
            },
            "zip_code": {
                "pattern": r"^\d{5}(-\d{4})?$",
                "description": "XXXXX or XXXXX-XXXX"
            },
            "phone": {
                "pattern": r"^\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}$",
                "description": "XXX-XXX-XXXX format"
            },
            "email": {
                "pattern": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
                "description": "Valid email format"
            }
        }
    
    def _init_common_values(self) -> Dict[str, List[str]]:
        """Initialize common values for fields"""
        return {
            "country": ["United States", "Mexico", "Canada", "China", "India", "Philippines", "Brazil", "United Kingdom"],
            "state": ["CA", "TX", "FL", "NY", "IL", "PA", "OH", "GA", "NC", "MI", "AZ", "NJ", "VA", "WA", "MA"],
            "gender": ["Male", "Female"],
            "marital_status": ["Single", "Married", "Divorced", "Widowed", "Separated", "Annulled"],
            "yes_no": ["Yes", "No"],
            "eye_color": ["Black", "Blue", "Brown", "Gray", "Green", "Hazel", "Maroon", "Pink", "Unknown"],
            "hair_color": ["Bald", "Black", "Blonde", "Brown", "Gray", "Red", "Sandy", "White", "Unknown"],
            "application_type": ["Initial", "Renewal", "Replacement", "Amendment"],
            "ethnicity": ["Hispanic or Latino", "Not Hispanic or Latino"],
            "race": ["White", "Asian", "Black or African American", "American Indian or Alaska Native", 
                    "Native Hawaiian or Other Pacific Islander"]
        }
    
    def get_form_info(self, form_number: str) -> Optional[Dict]:
        """Get information about a specific form"""
        return self.form_structures.get(form_number)
    
    def get_expected_parts(self, form_number: str) -> Optional[Dict[int, str]]:
        """Get expected parts for a form"""
        form_info = self.get_form_info(form_number)
        return form_info.get("parts") if form_info else None
    
    def suggest_field_type(self, label: str) -> Tuple[FieldType, float]:
        """Suggest field type based on label with enhanced logic"""
        label_lower = label.lower()
        
        # Check specific patterns first
        for pattern_group, info in self.field_patterns.items():
            for pattern in info["patterns"]:
                if re.search(pattern.lower(), label_lower):
                    return info["type"], 0.9
        
        # Enhanced heuristics
        if any(word in label_lower for word in ["check", "select", "choose", "mark", "indicate"]):
            return FieldType.CHECKBOX, 0.85
        elif any(word in label_lower for word in ["email", "e-mail"]):
            return FieldType.EMAIL, 0.95
        elif any(word in label_lower for word in ["phone", "telephone", "mobile", "cell", "fax"]):
            return FieldType.PHONE, 0.9
        elif any(word in label_lower for word in ["date", "day", "month", "year", "dob", "birth"]):
            return FieldType.DATE, 0.85
        elif any(word in label_lower for word in ["number", "no.", "#", "amount", "count", "total"]):
            return FieldType.NUMBER, 0.8
        elif any(word in label_lower for word in ["signature", "sign"]):
            return FieldType.SIGNATURE, 0.95
        elif any(word in label_lower for word in ["address", "street", "city", "state", "zip", "postal"]):
            return FieldType.ADDRESS, 0.85
        elif any(word in label_lower for word in ["name", "first", "last", "middle", "given", "family"]):
            return FieldType.NAME, 0.85
        elif any(word in label_lower for word in ["$", "dollar", "amount", "fee", "cost", "price"]):
            return FieldType.CURRENCY, 0.85
        
        return FieldType.TEXT, 0.5
    
    def validate_value(self, field_type: str, value: str) -> Tuple[bool, str]:
        """Validate a field value"""
        if not value:
            return True, ""
        
        if field_type in self.validation_rules:
            rule = self.validation_rules[field_type]
            if re.match(rule["pattern"], value):
                return True, ""
            else:
                return False, f"Expected format: {rule['description']}"
        
        return True, ""

# ===== DATA CLASSES =====
@dataclass
class CheckboxOption:
    """Represents a checkbox option"""
    text: str
    is_selected: bool = False
    position: Optional[Tuple[float, float]] = None
    confidence: float = 0.0

@dataclass
class FieldNode:
    """Enhanced field node with full support"""
    # Core properties
    item_number: str
    label: str
    field_type: FieldType = FieldType.UNKNOWN
    value: str = ""
    checkbox_options: List[CheckboxOption] = field(default_factory=list)
    
    # Hierarchy
    parent: Optional['FieldNode'] = None
    children: List['FieldNode'] = field(default_factory=list)
    
    # Location
    page: int = 1
    part_number: int = 1
    part_name: str = "Part 1"
    bbox: Optional[Tuple[float, float, float, float]] = None
    
    # Unique identification
    key: str = ""
    content_hash: str = ""
    
    # Extraction metadata
    confidence: ExtractionConfidence = ExtractionConfidence.LOW
    extraction_method: str = ""
    raw_text: str = ""
    context: str = ""
    
    # Mapping
    mapping_status: MappingStatus = MappingStatus.UNMAPPED
    mapped_to: Optional[str] = None
    mapping_confidence: float = 0.0
    suggested_mappings: List[Tuple[str, float]] = field(default_factory=list)
    
    # Questionnaire
    in_questionnaire: bool = False
    questionnaire_order: int = 0
    questionnaire_help_text: str = ""
    
    # Validation
    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)
    is_required: bool = False
    
    def __post_init__(self):
        if not self.content_hash:
            content = f"{self.label}_{self.item_number}_{self.page}_{self.part_number}"
            self.content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        if not self.key:
            self.key = f"P{self.part_number}_{self.item_number}_{self.content_hash}"
    
    def add_child(self, child: 'FieldNode'):
        """Add child and set parent relationship"""
        child.parent = self
        self.children.append(child)
    
    def get_full_path(self) -> str:
        """Get full hierarchical path"""
        path = [self.item_number]
        current = self.parent
        while current:
            path.insert(0, current.item_number)
            current = current.parent
        return ".".join(path)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            'key': self.key,
            'item_number': self.item_number,
            'label': self.label,
            'value': self.value,
            'type': self.field_type.value,
            'part': self.part_number,
            'page': self.page,
            'mapping_status': self.mapping_status.value,
            'mapped_to': self.mapped_to,
            'in_questionnaire': self.in_questionnaire,
            'is_valid': self.is_valid,
            'validation_errors': self.validation_errors,
            'checkbox_options': [
                {'text': opt.text, 'selected': opt.is_selected}
                for opt in self.checkbox_options
            ] if self.checkbox_options else None
        }

@dataclass
class PartStructure:
    """Enhanced part structure with validation"""
    part_number: int
    part_name: str
    part_title: str = ""
    start_page: int = 1
    end_page: int = 1
    root_fields: List[FieldNode] = field(default_factory=list)
    field_hashes: Set[str] = field(default_factory=set)
    field_registry: Dict[str, FieldNode] = field(default_factory=dict)
    expected_fields: int = 0
    actual_fields: int = 0
    validation_score: float = 0.0
    
    def add_field(self, field: FieldNode) -> bool:
        """Add field with duplicate check and hierarchy management"""
        if not field.key:
            field.key = f"P{self.part_number}_{field.item_number}_{field.content_hash}"
        
        # Check for duplicates
        if field.content_hash in self.field_hashes:
            return False
        
        # Update page range
        if field.page < self.start_page:
            self.start_page = field.page
        if field.page > self.end_page:
            self.end_page = field.page
        
        # Set part info
        field.part_number = self.part_number
        field.part_name = self.part_name
        
        # Register field
        self.field_registry[field.item_number] = field
        self.field_hashes.add(field.content_hash)
        
        # Add to hierarchy
        if self._is_root_field(field.item_number):
            self.root_fields.append(field)
        else:
            parent_num = self._get_parent_number(field.item_number)
            if parent_num and parent_num in self.field_registry:
                parent = self.field_registry[parent_num]
                parent.add_child(field)
            else:
                # Parent not found yet, add as root temporarily
                self.root_fields.append(field)
        
        self.actual_fields += 1
        return True
    
    def _is_root_field(self, item_number: str) -> bool:
        """Check if this is a root field"""
        return bool(re.match(r'^\d+$', item_number))
    
    def _get_parent_number(self, item_number: str) -> Optional[str]:
        """Get parent number from item number"""
        # Handle patterns like "1a" -> "1", "1a1" -> "1a"
        if re.match(r'^\d+[a-z]$', item_number):
            return item_number[:-1]
        elif re.match(r'^\d+[a-z]\d+$', item_number):
            return re.match(r'^(\d+[a-z])', item_number).group(1)
        return None
    
    def reorganize_hierarchy(self):
        """Reorganize fields to ensure proper parent-child relationships"""
        new_roots = []
        for field in self.root_fields:
            if not self._is_root_field(field.item_number):
                parent_num = self._get_parent_number(field.item_number)
                if parent_num and parent_num in self.field_registry:
                    parent = self.field_registry[parent_num]
                    if field not in parent.children:
                        parent.add_child(field)
                else:
                    new_roots.append(field)
            else:
                new_roots.append(field)
        self.root_fields = new_roots
    
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
    
    def get_validation_report(self) -> Dict:
        """Get validation report for this part"""
        total_fields = len(self.get_all_fields_flat())
        valid_fields = sum(1 for f in self.get_all_fields_flat() if f.is_valid)
        
        return {
            'part_number': self.part_number,
            'part_name': self.part_name,
            'total_fields': total_fields,
            'valid_fields': valid_fields,
            'validation_score': valid_fields / total_fields if total_fields > 0 else 0,
            'page_range': f"{self.start_page}-{self.end_page}"
        }

@dataclass
class FormExtractionResult:
    """Complete extraction result with enhanced metadata"""
    form_number: str
    form_title: str
    parts: Dict[int, PartStructure] = field(default_factory=dict)
    
    # Metadata
    total_fields: int = 0
    duplicate_count: int = 0
    extraction_iterations: int = 0
    confidence_score: float = 0.0
    extraction_time: float = 0.0
    
    # Mapping data
    field_mappings: Dict[str, str] = field(default_factory=dict)
    manual_mappings: Dict[str, str] = field(default_factory=dict)
    suggested_mappings: Dict[str, List[Tuple[str, float]]] = field(default_factory=dict)
    
    # Questionnaire
    questionnaire_fields: List[str] = field(default_factory=list)
    
    # Knowledge base integration
    kb_matches: Dict[str, Any] = field(default_factory=dict)
    kb_suggestions: Dict[str, Any] = field(default_factory=dict)
    
    def get_field_by_key(self, key: str) -> Optional[FieldNode]:
        """Get field by its unique key"""
        for part in self.parts.values():
            for field in part.get_all_fields_flat():
                if field.key == key:
                    return field
        return None
    
    def move_to_questionnaire(self, field_key: str):
        """Move a field to questionnaire"""
        field = self.get_field_by_key(field_key)
        if field:
            field.in_questionnaire = True
            field.mapping_status = MappingStatus.QUESTIONNAIRE
            if field_key not in self.questionnaire_fields:
                self.questionnaire_fields.append(field_key)
    
    def get_questionnaire_fields(self) -> List[FieldNode]:
        """Get all fields marked for questionnaire"""
        fields = []
        for key in self.questionnaire_fields:
            field = self.get_field_by_key(key)
            if field:
                fields.append(field)
        return sorted(fields, key=lambda f: f.questionnaire_order)

# ===== BASE AGENT CLASS =====
class BaseAgent(ABC):
    """Enhanced base agent with better logging and metrics"""
    
    def __init__(self, name: str, role: AgentRole, description: str = ""):
        self.name = name
        self.role = role
        self.description = description
        self.status = "idle"
        self.logs = []
        self.metrics = {
            'executions': 0,
            'successes': 0,
            'failures': 0,
            'avg_time': 0.0,
            'last_execution': None
        }
        self.knowledge_base = FormKnowledgeBase()
    
    @abstractmethod
    def execute(self, *args, **kwargs) -> Any:
        pass
    
    def log(self, message: str, level: str = "info", details: Any = None):
        """Enhanced logging with metrics"""
        entry = {
            "timestamp": datetime.now(),
            "agent": self.name,
            "role": self.role.value,
            "message": message,
            "level": level,
            "details": details
        }
        self.logs.append(entry)
        
        # Display in UI if available
        if hasattr(st, 'session_state') and 'agent_container' in st.session_state:
            with st.session_state.agent_container:
                css_class = "agent-card"
                if level == "error":
                    css_class += " agent-error"
                elif level == "success":
                    css_class += " agent-success"
                elif self.status == "active":
                    css_class += " agent-active"
                
                icon = {
                    "info": "ℹ️", 
                    "success": "✅", 
                    "warning": "⚠️", 
                    "error": "❌",
                    "thinking": "🤔",
                    "learning": "🧠"
                }.get(level, "📝")
                
                st.markdown(
                    f'<div class="{css_class}">'
                    f'{icon} <strong>{self.name}</strong>: {message}'
                    f'</div>', 
                    unsafe_allow_html=True
                )

# ===== FIXED ENHANCED EXTRACTION AGENT =====
class FixedEnhancedExtractionAgent(BaseAgent):
    """Fixed extraction with better field and part detection"""
    
    def __init__(self):
        super().__init__(
            "Fixed Enhanced Extraction Agent",
            AgentRole.EXTRACTOR,
            "Advanced extraction with better pattern matching"
        )
        self.doc = None
        self.current_form_type = ""
        self.extraction_context = {}
        
    def execute(self, pdf_file) -> FormExtractionResult:
        """Execute enhanced extraction"""
        self.status = "active"
        self.metrics['executions'] += 1
        start_time = time.time()
        
        self.log("🚀 Starting fixed enhanced extraction...", "info")
        
        try:
            # Open PDF
            if hasattr(pdf_file, 'read'):
                pdf_file.seek(0)
                pdf_bytes = pdf_file.read()
            else:
                pdf_bytes = pdf_file
            
            self.doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            # Phase 1: Identify form with KB
            form_info = self._identify_form_with_kb()
            self.current_form_type = form_info['number']
            
            # Get expected structure from KB
            expected_structure = self.knowledge_base.get_form_info(self.current_form_type)
            
            if expected_structure:
                self.log(f"📚 Found form structure in knowledge base: {expected_structure['title']}", "learning")
            
            result = FormExtractionResult(
                form_number=form_info['number'],
                form_title=form_info['title']
            )
            
            # Store KB matches
            if expected_structure:
                result.kb_matches['form_structure'] = expected_structure
            
            # Phase 2: Extract all text blocks from all pages first
            all_pages_blocks = []
            for page_num in range(len(self.doc)):
                page = self.doc[page_num]
                page_blocks = self._extract_all_page_blocks(page, page_num + 1)
                all_pages_blocks.extend(page_blocks)
            
            # Phase 3: Find all parts first
            parts_info = self._find_all_parts(all_pages_blocks, expected_structure)
            
            # Phase 4: Extract fields for each part
            self._extract_fields_by_parts(all_pages_blocks, parts_info, result)
            
            # Phase 5: Post-processing
            self._post_process_extraction(result)
            
            # Calculate metrics
            end_time = time.time()
            result.extraction_time = end_time - start_time
            result.total_fields = sum(len(part.get_all_fields_flat()) for part in result.parts.values())
            
            self.metrics['successes'] += 1
            self.log(f"✅ Extraction complete: {result.total_fields} fields in {len(result.parts)} parts in {result.extraction_time:.2f}s", "success")
            
            return result
            
        except Exception as e:
            self.metrics['failures'] += 1
            self.log(f"❌ Extraction failed: {str(e)}", "error", traceback.format_exc())
            raise
        finally:
            if self.doc:
                self.doc.close()
    
    def _extract_all_page_blocks(self, page, page_num: int) -> List[Dict]:
        """Extract all text blocks from a page with position info"""
        blocks = []
        page_dict = page.get_text("dict")
        
        for block in page_dict["blocks"]:
            if block["type"] == 0:  # Text block
                for line in block["lines"]:
                    text = " ".join(span["text"] for span in line["spans"])
                    if text.strip():
                        # Get font information
                        fonts = [span.get("font", "") for span in line["spans"]]
                        sizes = [span.get("size", 10) for span in line["spans"]]
                        
                        blocks.append({
                            'text': text.strip(),
                            'raw_text': text,
                            'bbox': line.get("bbox", [0, 0, 0, 0]),
                            'page': page_num,
                            'spans': line["spans"],
                            'is_bold': any(span.get("flags", 0) & 2**4 for span in line["spans"]),
                            'font_size': max(sizes) if sizes else 10,
                            'fonts': list(set(fonts)),
                            'y_pos': line.get("bbox", [0, 0, 0, 0])[1],
                            'x_pos': line.get("bbox", [0, 0, 0, 0])[0]
                        })
        
        # Sort blocks by page, then Y position, then X position
        blocks.sort(key=lambda b: (b['page'], b['y_pos'], b['x_pos']))
        
        return blocks
    
    def _find_all_parts(self, all_blocks: List[Dict], expected_structure: Optional[Dict]) -> Dict[int, Dict]:
        """Find all parts in the document"""
        parts_info = {}
        current_part_num = 0
        
        # Enhanced part patterns
        part_patterns = [
            (r'^Part\s+(\d+)[.:]\s*(.*)$', 'standard'),
            (r'^Part\s+(\d+)\s+[-–—]\s*(.*)$', 'dash'),
            (r'^Part\s+(\d+)\s*$', 'number_only'),
            (r'^PART\s+(\d+)[.:]\s*(.*)$', 'uppercase'),
            (r'^Section\s+([A-Z]|[IVX]+)[.:]\s*(.*)$', 'section'),
        ]
        
        # First pass: find explicit part headers
        for i, block in enumerate(all_blocks):
            text = block['text']
            
            for pattern, pattern_type in part_patterns:
                match = re.match(pattern, text, re.IGNORECASE)
                if match:
                    if pattern_type in ['standard', 'dash', 'uppercase']:
                        part_num = int(match.group(1))
                        title = match.group(2).strip() if match.lastindex >= 2 else ""
                        
                        # Look for title in next line if empty
                        if not title and i + 1 < len(all_blocks):
                            next_block = all_blocks[i + 1]
                            # Check if next line is likely a title (not a field)
                            if not re.match(r'^\d+[a-z]?\.|^[A-Z]\.|^\([a-z]\)', next_block['text']):
                                title = next_block['text']
                        
                        parts_info[part_num] = {
                            'number': part_num,
                            'title': title,
                            'start_block': i,
                            'page': block['page']
                        }
                        current_part_num = part_num
                        self.log(f"📋 Found Part {part_num}: {title or '(title on next line)'}", "success")
                        break
                    
                    elif pattern_type == 'number_only':
                        part_num = int(match.group(1))
                        # Look for title in next line
                        title = ""
                        if i + 1 < len(all_blocks):
                            next_block = all_blocks[i + 1]
                            if not re.match(r'^\d+[a-z]?\.|^[A-Z]\.|^\([a-z]\)', next_block['text']):
                                title = next_block['text']
                        
                        parts_info[part_num] = {
                            'number': part_num,
                            'title': title,
                            'start_block': i,
                            'page': block['page']
                        }
                        current_part_num = part_num
                        self.log(f"📋 Found Part {part_num}: {title}", "success")
                        break
        
        # If no parts found or Part 1 is missing, check if form starts with fields
        if 1 not in parts_info:
            # Look for fields at the beginning
            for i, block in enumerate(all_blocks[:50]):  # Check first 50 blocks
                if self._is_field_start(block['text']):
                    # Found fields before any part header - create Part 1
                    title = "Information About You"  # Default title
                    if expected_structure and 'parts' in expected_structure:
                        title = expected_structure['parts'].get(1, title)
                    
                    parts_info[1] = {
                        'number': 1,
                        'title': title,
                        'start_block': 0,
                        'page': 1
                    }
                    self.log(f"📋 Created implicit Part 1: {title} (fields found before part header)", "info")
                    break
        
        # Fill in missing parts from expected structure
        if expected_structure and 'parts' in expected_structure:
            for part_num, part_title in expected_structure['parts'].items():
                if part_num not in parts_info:
                    self.log(f"⚠️ Part {part_num}: {part_title} not found in document", "warning")
        
        # Set end blocks for each part
        part_numbers = sorted(parts_info.keys())
        for i, part_num in enumerate(part_numbers):
            if i + 1 < len(part_numbers):
                next_part_num = part_numbers[i + 1]
                parts_info[part_num]['end_block'] = parts_info[next_part_num]['start_block'] - 1
            else:
                parts_info[part_num]['end_block'] = len(all_blocks) - 1
        
        return parts_info
    
    def _is_field_start(self, text: str) -> bool:
        """Check if text looks like a field start"""
        field_patterns = [
            r'^\d+\.\s+\w+',  # 1. Something
            r'^\d+[a-z]\.\s+\w+',  # 1a. Something
            r'^[A-Z]\.\s+\w+',  # A. Something
            r'^\(\d+\)\s+\w+',  # (1) Something
            r'^(Family Name|Given Name|Middle Name|Date of Birth)',  # Common field names
            r'^(A-Number|USCIS|Alien Registration)',  # Common USCIS fields
        ]
        
        return any(re.match(pattern, text, re.IGNORECASE) for pattern in field_patterns)
    
    def _extract_fields_by_parts(self, all_blocks: List[Dict], parts_info: Dict[int, Dict], 
                                 result: FormExtractionResult):
        """Extract fields for each part"""
        
        # Process each part
        for part_num in sorted(parts_info.keys()):
            part_info = parts_info[part_num]
            
            # Create part structure
            part = PartStructure(
                part_number=part_num,
                part_name=f"Part {part_num}",
                part_title=part_info['title'],
                start_page=part_info['page']
            )
            
            # Extract fields for this part
            start_block = part_info['start_block']
            end_block = part_info['end_block']
            
            self.log(f"📝 Extracting fields for Part {part_num} (blocks {start_block}-{end_block})", "info")
            
            # Track what we've processed
            processed_indices = set()
            
            # Process blocks in this part
            i = start_block
            while i <= end_block:
                if i in processed_indices:
                    i += 1
                    continue
                
                block = all_blocks[i]
                
                # Skip part headers
                if re.match(r'^Part\s+\d+', block['text'], re.IGNORECASE):
                    i += 1
                    continue
                
                # Try to extract field
                field, next_index = self._extract_field_from_block(all_blocks, i, end_block)
                
                if field:
                    field.part_number = part_num
                    field.part_name = part.part_name
                    
                    if part.add_field(field):
                        self.log(f"  Found field {field.item_number}: {field.label[:50]}...", "info")
                    
                    # Mark blocks as processed
                    for j in range(i, next_index):
                        processed_indices.add(j)
                    
                    i = next_index
                else:
                    i += 1
            
            # Reorganize hierarchy
            part.reorganize_hierarchy()
            
            # Add part to result
            result.parts[part_num] = part
            
            self.log(f"✅ Part {part_num} complete: {len(part.get_all_fields_flat())} fields", "success")
    
    def _extract_field_from_block(self, all_blocks: List[Dict], start_idx: int, 
                                  end_idx: int) -> Tuple[Optional[FieldNode], int]:
        """Extract a field starting from a block index"""
        if start_idx >= len(all_blocks):
            return None, start_idx + 1
            
        block = all_blocks[start_idx]
        text = block['text']
        
        # Enhanced field patterns - ordered by specificity
        field_patterns = [
            # Nested sub-fields (most specific)
            (r'^(\d+)\.([a-z])\.(\d+)\.\s+(.+?)(?:\s*\(|:|$)', 'nested_field_dots'),
            (r'^(\d+)([a-z])(\d+)\.\s+(.+?)(?:\s*\(|:|$)', 'nested_field_no_dots'),
            
            # Sub-fields with letters
            (r'^(\d+)\.([a-z])\.\s+(.+?)(?:\s*\(|:|$)', 'sub_field_dot'),
            (r'^(\d+)([a-z])\.\s+(.+?)(?:\s*\(|:|$)', 'sub_field_no_dot'),
            (r'^(\d+)\.([a-z])\.\s*$', 'sub_number_only_dot'),
            (r'^(\d+)([a-z])\.\s*$', 'sub_number_only_no_dot'),
            
            # Main numbered fields
            (r'^(\d+)\.\s+(.+?)(?:\s*\(|:|$)', 'main_field'),
            (r'^(\d+)\.\s*$', 'main_number_only'),
            
            # Fields in parentheses
            (r'^\(([a-z])\)\s+(.+?)(?:\s*\(|:|$)', 'paren_letter'),
            (r'^\((\d+)\)\s+(.+?)(?:\s*\(|:|$)', 'paren_number'),
            
            # Letter fields
            (r'^([A-Z])\.\s+(.+?)(?:\s*\(|:|$)', 'letter_field'),
            (r'^([A-Z])\.\s*$', 'letter_only'),
            
            # Special USCIS fields
            (r'^(A-Number|Alien Registration Number)\s*[:\.]?\s*$', 'special_field'),
            (r'^(USCIS Online Account Number)\s*[:\.]?\s*$', 'special_field'),
            (r'^(Date of Birth|Country of Birth|Family Name|Given Name|Middle Name)\s*[:\.]?\s*$', 'special_field'),
        ]
        
        # Try each pattern
        for pattern, pattern_type in field_patterns:
            match = re.match(pattern, text)
            if match:
                # Extract field info based on pattern type
                field_info = self._parse_field_match(match, pattern_type, all_blocks, 
                                                    start_idx, end_idx)
                
                if field_info:
                    # Create field node
                    field = FieldNode(
                        item_number=field_info['item_number'],
                        label=field_info['label'],
                        page=block['page'],
                        extraction_method=f"pattern_{pattern_type}",
                        raw_text=text,
                        bbox=tuple(block['bbox'])
                    )
                    
                    # Check for value on same line
                    if field_info.get('value'):
                        field.value = field_info['value']
                    
                    # Extract additional info (checkboxes, etc.)
                    next_idx = self._extract_field_details(field, all_blocks, 
                                                          field_info['next_index'], end_idx)
                    
                    return field, next_idx
        
        return None, start_idx + 1
    
    def _parse_field_match(self, match, pattern_type: str, all_blocks: List[Dict], 
                          start_idx: int, end_idx: int) -> Optional[Dict]:
        """Parse field match based on pattern type"""
        
        if pattern_type == 'main_field':
            return {
                'item_number': match.group(1),
                'label': match.group(2).strip(),
                'next_index': start_idx + 1
            }
        
        elif pattern_type == 'main_number_only':
            # Look for label on next line
            if start_idx + 1 <= end_idx and start_idx + 1 < len(all_blocks):
                next_text = all_blocks[start_idx + 1]['text']
                # Make sure next line is not another field
                if not self._is_field_start(next_text):
                    return {
                        'item_number': match.group(1),
                        'label': next_text,
                        'next_index': start_idx + 2
                    }
            return None
        
        elif pattern_type in ['sub_field_dot', 'sub_field_no_dot']:
            item_number = match.group(1) + match.group(2)
            label = match.group(3).strip() if match.lastindex >= 3 else ""
            
            if not label and start_idx + 1 <= end_idx and start_idx + 1 < len(all_blocks):
                next_text = all_blocks[start_idx + 1]['text']
                if not self._is_field_start(next_text):
                    label = next_text
                    return {
                        'item_number': item_number,
                        'label': label,
                        'next_index': start_idx + 2
                    }
            
            return {
                'item_number': item_number,
                'label': label,
                'next_index': start_idx + 1
            }
        
        elif pattern_type in ['sub_number_only_dot', 'sub_number_only_no_dot']:
            item_number = match.group(1) + match.group(2)
            
            # Look for label on next line
            if start_idx + 1 <= end_idx and start_idx + 1 < len(all_blocks):
                next_text = all_blocks[start_idx + 1]['text']
                if not self._is_field_start(next_text):
                    return {
                        'item_number': item_number,
                        'label': next_text,
                        'next_index': start_idx + 2
                    }
            return None
        
        elif pattern_type in ['nested_field_dots', 'nested_field_no_dots']:
            item_number = match.group(1) + match.group(2) + match.group(3)
            label = match.group(4).strip() if match.lastindex >= 4 else ""
            
            if not label and start_idx + 1 <= end_idx and start_idx + 1 < len(all_blocks):
                next_text = all_blocks[start_idx + 1]['text']
                if not self._is_field_start(next_text):
                    label = next_text
                    return {
                        'item_number': item_number,
                        'label': label,
                        'next_index': start_idx + 2
                    }
            
            return {
                'item_number': item_number,
                'label': label,
                'next_index': start_idx + 1
            }
        
        elif pattern_type in ['paren_letter', 'paren_number']:
            return {
                'item_number': match.group(1),
                'label': match.group(2).strip(),
                'next_index': start_idx + 1
            }
        
        elif pattern_type == 'letter_field':
            return {
                'item_number': match.group(1),
                'label': match.group(2).strip(),
                'next_index': start_idx + 1
            }
        
        elif pattern_type == 'letter_only':
            # Look for label on next line
            if start_idx + 1 <= end_idx and start_idx + 1 < len(all_blocks):
                next_text = all_blocks[start_idx + 1]['text']
                if not self._is_field_start(next_text):
                    return {
                        'item_number': match.group(1),
                        'label': next_text,
                        'next_index': start_idx + 2
                    }
            return None
        
        elif pattern_type == 'special_field':
            # Generate unique item number for special fields
            field_name = match.group(1)
            item_number = f"S{abs(hash(field_name)) % 1000}"
            
            return {
                'item_number': item_number,
                'label': field_name,
                'next_index': start_idx + 1
            }
        
        return None
    
    def _extract_field_details(self, field: FieldNode, all_blocks: List[Dict], 
                              start_idx: int, end_idx: int) -> int:
        """Extract additional field details like checkboxes, additional text"""
        
        # Get field type suggestion from KB
        suggested_type, confidence = self.knowledge_base.suggest_field_type(field.label)
        if confidence > 0.7:
            field.field_type = suggested_type
            field.confidence = ExtractionConfidence.HIGH if confidence > 0.85 else ExtractionConfidence.MEDIUM
        
        # Look for checkboxes or options
        if field.field_type == FieldType.CHECKBOX or any(word in field.label.lower() 
                                                         for word in ["check", "select", "mark", "choose"]):
            options = []
            current_idx = start_idx
            
            # Checkbox patterns
            checkbox_patterns = [
                (r'^[□☐]\s*(.+)', False),
                (r'^[☑☒]\s*(.+)', True),
                (r'^\[\s*\]\s*(.+)', False),
                (r'^\[X\]\s*(.+)', True),
                (r'^○\s*(.+)', False),
                (r'^●\s*(.+)', True),
                (r'^\(\s*\)\s*(.+)', False),
                (r'^\(X\)\s*(.+)', True),
            ]
            
            # Look for checkbox options
            while current_idx <= min(end_idx, start_idx + 20):  # Limit search
                if current_idx >= len(all_blocks):
                    break
                
                block = all_blocks[current_idx]
                text = block['text']
                
                # Stop if we hit another field
                if self._is_field_start(text) and current_idx != start_idx:
                    break
                
                # Check for checkbox patterns
                found_checkbox = False
                for pattern, is_selected in checkbox_patterns:
                    match = re.match(pattern, text)
                    if match:
                        options.append(CheckboxOption(
                            text=match.group(1).strip(),
                            is_selected=is_selected,
                            position=(block['x_pos'], block['y_pos']),
                            confidence=0.9
                        ))
                        found_checkbox = True
                        break
                
                # Check for indented text that might be options
                if not found_checkbox and current_idx > start_idx:
                    if block['x_pos'] > all_blocks[start_idx]['x_pos'] + 20:
                        if len(text) < 100 and not text.endswith(':'):
                            options.append(CheckboxOption(
                                text=text,
                                is_selected=False,
                                position=(block['x_pos'], block['y_pos']),
                                confidence=0.7
                            ))
                
                current_idx += 1
            
            if options:
                field.checkbox_options = options
                return current_idx
        
        # For other field types, check if there's additional descriptive text
        if start_idx <= end_idx and start_idx < len(all_blocks):
            next_block = all_blocks[start_idx]
            # If next line is indented and not a field, it might be help text
            if (next_block['x_pos'] > field.bbox[0] + 20 and 
                not self._is_field_start(next_block['text'])):
                field.context = next_block['text']
                return start_idx + 1
        
        return start_idx
    
    def _identify_form_with_kb(self) -> Dict[str, str]:
        """Identify form using knowledge base"""
        if not self.doc or self.doc.page_count == 0:
            return {"number": "Unknown", "title": "Unknown Form"}
        
        first_page_text = self.doc[0].get_text()
        
        # Try to match against known forms
        for form_number, form_info in self.knowledge_base.form_structures.items():
            # Check form number pattern
            pattern = rf"Form\s+{re.escape(form_number)}\b"
            if re.search(pattern, first_page_text, re.IGNORECASE):
                self.log(f"🎯 Identified form using KB: {form_number} - {form_info['title']}", "success")
                return {"number": form_number, "title": form_info['title']}
        
        # Fallback to pattern matching
        form_patterns = [
            (r'Form\s+(I-\d+[A-Z]?)', r'Form\s+I-\d+[A-Z]?\s*[^\n]+'),
            (r'Form\s+(N-\d+)', r'Form\s+N-\d+\s*[^\n]+'),
            (r'Form\s+(G-\d+)', r'Form\s+G-\d+\s*[^\n]+'),
        ]
        
        for number_pattern, title_pattern in form_patterns:
            number_match = re.search(number_pattern, first_page_text, re.IGNORECASE)
            if number_match:
                form_number = number_match.group(1)
                title_match = re.search(title_pattern, first_page_text, re.IGNORECASE)
                form_title = title_match.group(0) if title_match else f"Form {form_number}"
                return {"number": form_number, "title": form_title}
        
        return {"number": "Unknown", "title": "Unknown Form"}
    
    def _post_process_extraction(self, result: FormExtractionResult):
        """Post-process extraction results"""
        # Reorganize all parts
        for part in result.parts.values():
            part.reorganize_hierarchy()
        
        # Apply knowledge base suggestions
        for part in result.parts.values():
            for field in part.get_all_fields_flat():
                # Validate field type
                if field.field_type == FieldType.UNKNOWN:
                    suggested_type, confidence = self.knowledge_base.suggest_field_type(field.label)
                    if confidence > 0.6:
                        field.field_type = suggested_type
                
                # Mark required fields based on KB
                if any(req in field.label.lower() for req in ['name', 'date of birth', 'signature', 'a-number']):
                    field.is_required = True

# ===== SMART VALIDATION AGENT =====
class SmartValidationAgent(BaseAgent):
    """Enhanced validation with self-correction"""
    
    def __init__(self):
        super().__init__(
            "Smart Validation Agent",
            AgentRole.VALIDATOR,
            "Validates and corrects extraction results"
        )
        self.validation_rules = self._init_validation_rules()
    
    def _init_validation_rules(self) -> Dict[str, Any]:
        """Initialize validation rules"""
        return {
            'field_count': {
                'min': 15,
                'weight': 1.5,
                'critical': True
            },
            'hierarchy': {
                'min_children': 5,
                'weight': 1.0,
                'critical': False
            },
            'part_continuity': {
                'weight': 0.8,
                'critical': False
            },
            'checkbox_detection': {
                'min_checkboxes': 3,
                'weight': 0.7,
                'critical': False
            },
            'field_numbering': {
                'max_gap': 5,
                'weight': 0.5,
                'critical': False
            },
            'field_types': {
                'min_typed': 0.7,
                'weight': 1.0,
                'critical': False
            }
        }
    
    def execute(self, result: FormExtractionResult) -> Tuple[bool, float, List[Dict], FormExtractionResult]:
        """Execute validation with corrections"""
        self.status = "active"
        self.log("🔍 Starting smart validation with self-correction...", "thinking")
        
        try:
            # Phase 1: Run validation checks
            validation_results = []
            total_score = 0.0
            total_weight = 0.0
            
            for check_name, check_func in self._get_validation_checks().items():
                check_result = check_func(result)
                validation_results.append(check_result)
                total_score += check_result['score'] * check_result['weight']
                total_weight += check_result['weight']
                
                # Log result
                if check_result['passed']:
                    self.log(f"✅ {check_result['name']}: {check_result['score']:.0%}", "success")
                else:
                    self.log(f"⚠️ {check_result['name']}: {check_result['score']:.0%} - {check_result['details']}", "warning")
            
            # Calculate final score
            final_score = total_score / total_weight if total_weight > 0 else 0
            is_valid = final_score >= 0.7
            
            # Phase 2: Apply corrections if needed
            if not is_valid:
                self.log("🔧 Applying corrections...", "thinking")
                corrected_result = self._apply_corrections(result, validation_results)
                
                # Re-validate after corrections
                re_validation_results = []
                re_total_score = 0.0
                re_total_weight = 0.0
                
                for check_name, check_func in self._get_validation_checks().items():
                    check_result = check_func(corrected_result)
                    re_validation_results.append(check_result)
                    re_total_score += check_result['score'] * check_result['weight']
                    re_total_weight += check_result['weight']
                
                re_final_score = re_total_score / re_total_weight if re_total_weight > 0 else 0
                
                if re_final_score > final_score:
                    self.log(f"✨ Validation improved from {final_score:.0%} to {re_final_score:.0%}", "success")
                    result = corrected_result
                    validation_results = re_validation_results
                    final_score = re_final_score
                    is_valid = final_score >= 0.7
            
            result.confidence_score = final_score
            
            # Phase 3: Field-level validation
            self._validate_fields(result)
            
            self.log(f"✅ Validation complete: {final_score:.0%} confidence", "success" if is_valid else "warning")
            return is_valid, final_score, validation_results, result
            
        except Exception as e:
            self.log(f"❌ Validation failed: {str(e)}", "error")
            return False, 0.0, [], result
    
    def _get_validation_checks(self) -> Dict[str, Any]:
        """Get validation check functions"""
        return {
            'field_count': self._check_field_count,
            'hierarchy': self._check_hierarchy,
            'part_continuity': self._check_part_continuity,
            'checkbox_detection': self._check_checkbox_detection,
            'field_numbering': self._check_field_numbering,
            'field_types': self._check_field_types,
            'required_fields': self._check_required_fields,
        }
    
    def _check_field_count(self, result: FormExtractionResult) -> Dict:
        """Check if enough fields were extracted"""
        rule = self.validation_rules['field_count']
        actual = result.total_fields
        
        # Check against KB expectations
        expected_info = self.knowledge_base.get_form_info(result.form_number)
        if expected_info:
            expected = expected_info.get('expected_fields', rule['min'])
        else:
            expected = rule['min']
        
        if actual >= expected * 0.7:  # Allow 70% threshold
            return {
                'name': 'Field Count',
                'passed': True,
                'score': min(1.0, actual / expected),
                'weight': rule['weight'],
                'details': f'{actual} fields found (expected ~{expected})'
            }
        else:
            return {
                'name': 'Field Count',
                'passed': False,
                'score': actual / expected if expected > 0 else 0,
                'weight': rule['weight'],
                'details': f'Only {actual} fields (expected ~{expected})'
            }
    
    def _check_hierarchy(self, result: FormExtractionResult) -> Dict:
        """Check hierarchical structure"""
        rule = self.validation_rules['hierarchy']
        total_children = 0
        fields_with_children = 0
        
        for part in result.parts.values():
            for field in part.get_all_fields_flat():
                if field.children:
                    fields_with_children += 1
                    total_children += len(field.children)
        
        if total_children >= rule['min_children']:
            return {
                'name': 'Hierarchy Detection',
                'passed': True,
                'score': min(1.0, total_children / 20),
                'weight': rule['weight'],
                'details': f'{total_children} sub-items in {fields_with_children} fields'
            }
        else:
            return {
                'name': 'Hierarchy Detection',
                'passed': False,
                'score': total_children / rule['min_children'],
                'weight': rule['weight'],
                'details': f'Only {total_children} sub-items found'
            }
    
    def _check_part_continuity(self, result: FormExtractionResult) -> Dict:
        """Check part organization"""
        rule = self.validation_rules['part_continuity']
        
        if not result.parts:
            return {
                'name': 'Part Organization',
                'passed': False,
                'score': 0.0,
                'weight': rule['weight'],
                'details': 'No parts found'
            }
        
        part_numbers = sorted(result.parts.keys())
        expected = list(range(1, max(part_numbers) + 1))
        missing = set(expected) - set(part_numbers)
        
        # Check against KB
        expected_parts = self.knowledge_base.get_expected_parts(result.form_number)
        if expected_parts:
            kb_missing = set(expected_parts.keys()) - set(part_numbers)
            if kb_missing:
                missing.update(kb_missing)
        
        if not missing:
            return {
                'name': 'Part Organization',
                'passed': True,
                'score': 1.0,
                'weight': rule['weight'],
                'details': f'{len(part_numbers)} parts found correctly'
            }
        else:
            score = len(part_numbers) / (len(part_numbers) + len(missing))
            return {
                'name': 'Part Organization',
                'passed': False,
                'score': score,
                'weight': rule['weight'],
                'details': f'Missing parts: {sorted(missing)}'
            }
    
    def _check_checkbox_detection(self, result: FormExtractionResult) -> Dict:
        """Check checkbox detection"""
        rule = self.validation_rules['checkbox_detection']
        checkbox_fields = 0
        total_options = 0
        
        for part in result.parts.values():
            for field in part.get_all_fields_flat():
                if field.checkbox_options:
                    checkbox_fields += 1
                    total_options += len(field.checkbox_options)
        
        if checkbox_fields >= rule['min_checkboxes']:
            return {
                'name': 'Checkbox Detection',
                'passed': True,
                'score': min(1.0, checkbox_fields / 10),
                'weight': rule['weight'],
                'details': f'{checkbox_fields} checkbox fields with {total_options} options'
            }
        else:
            return {
                'name': 'Checkbox Detection',
                'passed': checkbox_fields > 0,
                'score': checkbox_fields / rule['min_checkboxes'],
                'weight': rule['weight'],
                'details': f'Only {checkbox_fields} checkbox fields found'
            }
    
    def _check_field_numbering(self, result: FormExtractionResult) -> Dict:
        """Check field numbering consistency"""
        rule = self.validation_rules['field_numbering']
        issues = []
        
        for part_num, part in result.parts.items():
            numbers = []
            for field in part.get_all_fields_flat():
                if field.item_number.isdigit():
                    numbers.append(int(field.item_number))
            
            if numbers:
                numbers.sort()
                for i in range(1, len(numbers)):
                    gap = numbers[i] - numbers[i-1]
                    if gap > rule['max_gap']:
                        issues.append(f"Part {part_num}: gap {gap} between {numbers[i-1]} and {numbers[i]}")
        
        if not issues:
            return {
                'name': 'Field Numbering',
                'passed': True,
                'score': 1.0,
                'weight': rule['weight'],
                'details': 'Consistent numbering'
            }
        else:
            return {
                'name': 'Field Numbering',
                'passed': False,
                'score': max(0.3, 1.0 - len(issues) * 0.1),
                'weight': rule['weight'],
                'details': f'{len(issues)} numbering issues'
            }
    
    def _check_field_types(self, result: FormExtractionResult) -> Dict:
        """Check field type identification"""
        rule = self.validation_rules['field_types']
        total_fields = 0
        typed_fields = 0
        
        for part in result.parts.values():
            for field in part.get_all_fields_flat():
                total_fields += 1
                if field.field_type != FieldType.UNKNOWN:
                    typed_fields += 1
        
        ratio = typed_fields / total_fields if total_fields > 0 else 0
        
        if ratio >= rule['min_typed']:
            return {
                'name': 'Field Type Detection',
                'passed': True,
                'score': ratio,
                'weight': rule['weight'],
                'details': f'{typed_fields}/{total_fields} fields typed ({ratio:.0%})'
            }
        else:
            return {
                'name': 'Field Type Detection',
                'passed': False,
                'score': ratio,
                'weight': rule['weight'],
                'details': f'Only {typed_fields}/{total_fields} fields typed ({ratio:.0%})'
            }
    
    def _check_required_fields(self, result: FormExtractionResult) -> Dict:
        """Check for required fields based on form type"""
        # Common required fields for most forms
        required_patterns = [
            r'family.*name|last.*name',
            r'given.*name|first.*name',
            r'date.*birth',
            r'signature'
        ]
        
        # Add form-specific required fields
        form_info = self.knowledge_base.get_form_info(result.form_number)
        if form_info and 'first_fields' in form_info:
            for field_name in form_info['first_fields']:
                pattern = re.escape(field_name.lower())
                if pattern not in required_patterns:
                    required_patterns.append(pattern)
        
        found_required = 0
        missing_required = []
        
        all_labels = []
        for part in result.parts.values():
            for field in part.get_all_fields_flat():
                all_labels.append(field.label.lower())
        
        for pattern in required_patterns:
            if any(re.search(pattern, label) for label in all_labels):
                found_required += 1
            else:
                missing_required.append(pattern)
        
        score = found_required / len(required_patterns)
        
        return {
            'name': 'Required Fields',
            'passed': score >= 0.75,
            'score': score,
            'weight': 1.2,
            'details': f'{found_required}/{len(required_patterns)} required fields found'
        }
    
    def _apply_corrections(self, result: FormExtractionResult, validation_results: List[Dict]) -> FormExtractionResult:
        """Apply corrections based on validation results"""
        corrected = copy.deepcopy(result)
        
        for val_result in validation_results:
            if not val_result['passed']:
                if val_result['name'] == 'Field Type Detection':
                    # Try to improve field type detection
                    self._improve_field_types(corrected)
                elif val_result['name'] == 'Hierarchy Detection':
                    # Try to detect more hierarchical relationships
                    self._improve_hierarchy(corrected)
                elif val_result['name'] == 'Part Organization':
                    # Try to find missing parts
                    self._find_missing_parts(corrected)
        
        return corrected
    
    def _improve_field_types(self, result: FormExtractionResult):
        """Improve field type detection using context"""
        for part in result.parts.values():
            for field in part.get_all_fields_flat():
                if field.field_type == FieldType.UNKNOWN:
                    # Use context and KB to suggest type
                    suggested_type, confidence = self.knowledge_base.suggest_field_type(field.label)
                    if confidence > 0.5:
                        field.field_type = suggested_type
                        field.confidence = ExtractionConfidence.MEDIUM
    
    def _improve_hierarchy(self, result: FormExtractionResult):
        """Improve hierarchical structure detection"""
        for part in result.parts.values():
            part.reorganize_hierarchy()
            
            # Look for orphaned sub-items
            for field in part.get_all_fields_flat():
                if not field.parent and re.match(r'^\d+[a-z]', field.item_number):
                    # This should be a child
                    parent_num = re.match(r'^(\d+)', field.item_number).group(1)
                    if parent_num in part.field_registry:
                        parent = part.field_registry[parent_num]
                        parent.add_child(field)
    
    def _find_missing_parts(self, result: FormExtractionResult):
        """Try to find missing parts"""
        # This would require re-examining the original document
        # For now, just log the issue
        pass
    
    def _validate_fields(self, result: FormExtractionResult):
        """Validate individual fields"""
        for part in result.parts.values():
            for field in part.get_all_fields_flat():
                # Validate value if present
                if field.value:
                    # Validate based on field type
                    if field.field_type == FieldType.DATE:
                        is_valid, error = self.knowledge_base.validate_value('date', field.value)
                        if not is_valid:
                            field.is_valid = False
                            field.validation_errors.append(error)
                    elif field.field_type == FieldType.NUMBER:
                        # Check specific number types
                        if 'a-number' in field.label.lower() or 'alien' in field.label.lower():
                            is_valid, error = self.knowledge_base.validate_value('a_number', field.value)
                            if not is_valid:
                                field.is_valid = False
                                field.validation_errors.append(error)
                        elif 'ssn' in field.label.lower() or 'social security' in field.label.lower():
                            is_valid, error = self.knowledge_base.validate_value('ssn', field.value)
                            if not is_valid:
                                field.is_valid = False
                                field.validation_errors.append(error)
                    elif field.field_type == FieldType.EMAIL:
                        is_valid, error = self.knowledge_base.validate_value('email', field.value)
                        if not is_valid:
                            field.is_valid = False
                            field.validation_errors.append(error)
                
                # Mark required fields
                if field.is_required and not field.value:
                    field.validation_errors.append("This field is required")

# ===== INTELLIGENT MAPPING AGENT =====
class IntelligentMappingAgent(BaseAgent):
    """Enhanced mapping with manual controls and questionnaire support"""
    
    def __init__(self):
        super().__init__(
            "Intelligent Mapping Agent",
            AgentRole.MAPPER,
            "Maps fields to database with manual controls"
        )
        self.db_schema = self._init_enhanced_db_schema()
        self.mapping_history = self._load_mapping_history()
    
    def _init_enhanced_db_schema(self) -> Dict[str, Dict]:
        """Initialize enhanced database schema"""
        return {
            "personal_info": {
                "fields": {
                    "first_name": {"type": "string", "max_length": 50, "required": True},
                    "middle_name": {"type": "string", "max_length": 50, "required": False},
                    "last_name": {"type": "string", "max_length": 50, "required": True},
                    "other_names": {"type": "string", "max_length": 100, "required": False},
                    "date_of_birth": {"type": "date", "required": True},
                    "place_of_birth": {"type": "string", "max_length": 100, "required": False},
                    "country_of_birth": {"type": "string", "max_length": 50, "required": True},
                    "nationality": {"type": "string", "max_length": 50, "required": True},
                    "gender": {"type": "enum", "values": ["Male", "Female"], "required": True},
                    "marital_status": {"type": "enum", "values": ["Single", "Married", "Divorced", "Widowed"], "required": True}
                },
                "description": "Personal identification information"
            },
            "identification": {
                "fields": {
                    "alien_number": {"type": "string", "pattern": r"^\d{7,9}$", "required": False},
                    "uscis_number": {"type": "string", "max_length": 12, "required": False},
                    "social_security_number": {"type": "string", "pattern": r"^\d{3}-?\d{2}-?\d{4}$", "required": False},
                    "passport_number": {"type": "string", "max_length": 20, "required": False},
                    "passport_country": {"type": "string", "max_length": 50, "required": False},
                    "passport_expiry": {"type": "date", "required": False},
                    "driver_license": {"type": "string", "max_length": 20, "required": False},
                    "state_id": {"type": "string", "max_length": 20, "required": False}
                },
                "description": "Official identification numbers"
            },
            "contact_info": {
                "fields": {
                    "mailing_address": {"type": "string", "max_length": 100, "required": True},
                    "physical_address": {"type": "string", "max_length": 100, "required": False},
                    "apt_suite": {"type": "string", "max_length": 10, "required": False},
                    "city": {"type": "string", "max_length": 50, "required": True},
                    "state": {"type": "string", "max_length": 2, "required": True},
                    "zip_code": {"type": "string", "pattern": r"^\d{5}(-\d{4})?$", "required": True},
                    "country": {"type": "string", "max_length": 50, "required": True},
                    "phone_number": {"type": "string", "pattern": r"^\d{3}-?\d{3}-?\d{4}$", "required": True},
                    "mobile_number": {"type": "string", "pattern": r"^\d{3}-?\d{3}-?\d{4}$", "required": False},
                    "email_address": {"type": "email", "max_length": 100, "required": True},
                    "emergency_contact": {"type": "string", "max_length": 100, "required": False}
                },
                "description": "Contact and address information"
            },
            "immigration_info": {
                "fields": {
                    "current_status": {"type": "string", "max_length": 50, "required": True},
                    "status_expiry": {"type": "date", "required": False},
                    "i94_number": {"type": "string", "max_length": 11, "required": False},
                    "last_entry_date": {"type": "date", "required": False},
                    "last_entry_port": {"type": "string", "max_length": 50, "required": False},
                    "visa_number": {"type": "string", "max_length": 20, "required": False},
                    "visa_type": {"type": "string", "max_length": 10, "required": False},
                    "priority_date": {"type": "date", "required": False},
                    "category": {"type": "string", "max_length": 20, "required": False}
                },
                "description": "Immigration status and history"
            },
            "employment": {
                "fields": {
                    "employer_name": {"type": "string", "max_length": 100, "required": False},
                    "employer_address": {"type": "string", "max_length": 200, "required": False},
                    "job_title": {"type": "string", "max_length": 100, "required": False},
                    "start_date": {"type": "date", "required": False},
                    "occupation_code": {"type": "string", "max_length": 10, "required": False},
                    "salary": {"type": "currency", "required": False},
                    "work_address": {"type": "string", "max_length": 200, "required": False}
                },
                "description": "Employment information"
            },
            "family": {
                "fields": {
                    "spouse_name": {"type": "string", "max_length": 100, "required": False},
                    "spouse_dob": {"type": "date", "required": False},
                    "children_count": {"type": "integer", "min": 0, "required": False},
                    "parent_names": {"type": "string", "max_length": 200, "required": False},
                    "sibling_info": {"type": "text", "required": False}
                },
                "description": "Family information"
            }
        }
    
    def get_all_db_fields(self) -> List[str]:
        """Get all database fields for dropdown"""
        fields = []
        for category, cat_info in self.db_schema.items():
            for field_name in cat_info['fields']:
                fields.append(f"{category}.{field_name}")
        return sorted(fields)
    
    def _load_mapping_history(self) -> Dict[str, str]:
        """Load mapping history from previous sessions"""
        try:
            if Path('mapping_history.json').exists():
                with open('mapping_history.json', 'r') as f:
                    return json.load(f)
        except:
            pass
        return {}
    
    def _save_mapping_history(self):
        """Save mapping history for future use"""
        try:
            with open('mapping_history.json', 'w') as f:
                json.dump(self.mapping_history, f, indent=2)
        except:
            pass
    
    def execute(self, result: FormExtractionResult, 
                manual_mappings: Dict[str, str] = None,
                auto_map: bool = True) -> FormExtractionResult:
        """Execute intelligent mapping"""
        self.status = "active"
        self.log("🔗 Starting intelligent field mapping...", "thinking")
        
        try:
            # Phase 1: Apply manual mappings
            if manual_mappings:
                for field_key, target in manual_mappings.items():
                    if target == "questionnaire":
                        result.move_to_questionnaire(field_key)
                        self.log(f"📋 Moved field {field_key} to questionnaire")
                    else:
                        result.manual_mappings[field_key] = target
                        result.field_mappings[field_key] = target
                        # Update field
                        field = result.get_field_by_key(field_key)
                        if field:
                            field.mapped_to = target
                            field.mapping_status = MappingStatus.MANUAL
                            field.mapping_confidence = 1.0
                
                self.log(f"✅ Applied {len(manual_mappings)} manual mappings")
            
            # Phase 2: Auto-mapping if enabled
            if auto_map:
                unmapped_count = 0
                auto_mapped_count = 0
                suggested_count = 0
                
                for part in result.parts.values():
                    for field in part.get_all_fields_flat():
                        if field.key not in result.field_mappings and not field.in_questionnaire:
                            # Try to map automatically
                            suggestions = self._suggest_mapping(field)
                            
                            if suggestions:
                                result.suggested_mappings[field.key] = suggestions
                                field.suggested_mappings = suggestions
                                field.mapping_status = MappingStatus.SUGGESTED
                                suggested_count += 1
                                
                                # Auto-map high confidence suggestions
                                if suggestions[0][1] >= 0.85:
                                    result.field_mappings[field.key] = suggestions[0][0]
                                    field.mapped_to = suggestions[0][0]
                                    field.mapping_status = MappingStatus.MAPPED
                                    field.mapping_confidence = suggestions[0][1]
                                    auto_mapped_count += 1
                                    
                                    # Learn from this mapping
                                    self._learn_mapping(field.label, suggestions[0][0])
                            else:
                                field.mapping_status = MappingStatus.UNMAPPED
                                unmapped_count += 1
                
                self.log(f"📊 Auto-mapping: {auto_mapped_count} mapped, "
                        f"{suggested_count} suggested, {unmapped_count} unmapped")
            
            # Phase 3: Validate mappings
            self._validate_mappings(result)
            
            # Save mapping history
            self._save_mapping_history()
            
            self.log("✅ Mapping complete", "success")
            return result
            
        except Exception as e:
            self.log(f"❌ Mapping failed: {str(e)}", "error")
            raise
    
    def _suggest_mapping(self, field: FieldNode) -> List[Tuple[str, float]]:
        """Suggest database mappings using multiple strategies"""
        suggestions = []
        field_label_lower = field.label.lower()
        
        # Strategy 1: Check mapping history
        if field.label in self.mapping_history:
            historical_mapping = self.mapping_history[field.label]
            suggestions.append((historical_mapping, 0.95))
        
        # Strategy 2: Pattern-based matching
        patterns = {
            # Personal info
            r'family.*name|last.*name|surname': 'personal_info.last_name',
            r'given.*name|first.*name': 'personal_info.first_name',
            r'middle.*name|middle.*initial': 'personal_info.middle_name',
            r'other.*names?|aliases?|aka': 'personal_info.other_names',
            r'date.*birth|birth.*date|d\.?o\.?b|born': 'personal_info.date_of_birth',
            r'place.*birth|birth.*place|birthplace': 'personal_info.place_of_birth',
            r'country.*birth|birth.*country': 'personal_info.country_of_birth',
            r'nationality|citizenship|citizen': 'personal_info.nationality',
            r'gender|sex': 'personal_info.gender',
            r'marital.*status|married|single': 'personal_info.marital_status',
            
            # Identification
            r'a[\-\s]?number|alien.*number|alien.*registration': 'identification.alien_number',
            r'uscis.*number|online.*account': 'identification.uscis_number',
            r'social.*security|ssn': 'identification.social_security_number',
            r'passport.*number|passport.*no': 'identification.passport_number',
            r'passport.*country|country.*passport': 'identification.passport_country',
            r'passport.*expir|expir.*passport': 'identification.passport_expiry',
            r'driver.*license|driving.*license': 'identification.driver_license',
            r'state.*id|identification.*card': 'identification.state_id',
            
            # Contact info
            r'mailing.*address|mail.*to': 'contact_info.mailing_address',
            r'physical.*address|street.*address|current.*address': 'contact_info.physical_address',
            r'apt|apartment|suite|unit|ste': 'contact_info.apt_suite',
            r'city|town': 'contact_info.city',
            r'state|province': 'contact_info.state',
            r'zip.*code|postal.*code': 'contact_info.zip_code',
            r'country|nation': 'contact_info.country',
            r'phone.*number|telephone|phone|daytime.*phone': 'contact_info.phone_number',
            r'mobile|cell.*phone': 'contact_info.mobile_number',
            r'email.*address|e[\-\s]?mail': 'contact_info.email_address',
            r'emergency.*contact': 'contact_info.emergency_contact',
            
            # Immigration info
            r'current.*status|immigration.*status|legal.*status': 'immigration_info.current_status',
            r'status.*expir|expir.*date': 'immigration_info.status_expiry',
            r'i[\-\s]?94.*number|arrival.*departure': 'immigration_info.i94_number',
            r'last.*entry.*date|date.*last.*entry': 'immigration_info.last_entry_date',
            r'last.*entry.*port|port.*entry': 'immigration_info.last_entry_port',
            r'visa.*number': 'immigration_info.visa_number',
            r'visa.*type|type.*visa': 'immigration_info.visa_type',
            r'priority.*date': 'immigration_info.priority_date',
            r'category|classification': 'immigration_info.category',
            
            # Employment
            r'employer.*name|company.*name|business.*name': 'employment.employer_name',
            r'employer.*address|company.*address': 'employment.employer_address',
            r'job.*title|position|occupation': 'employment.job_title',
            r'start.*date|employment.*date|hire.*date': 'employment.start_date',
            r'occupation.*code|soc.*code': 'employment.occupation_code',
            r'salary|wage|income|compensation': 'employment.salary',
            r'work.*address|work.*location': 'employment.work_address',
            
            # Family
            r'spouse.*name|husband|wife': 'family.spouse_name',
            r'spouse.*birth|spouse.*dob': 'family.spouse_dob',
            r'children|child.*count|number.*children': 'family.children_count',
            r'parent.*name|mother|father': 'family.parent_names',
            r'sibling|brother|sister': 'family.sibling_info',
        }
        
        for pattern, db_field in patterns.items():
            if re.search(pattern, field_label_lower):
                match = re.search(pattern, field_label_lower)
                # Calculate confidence based on match quality
                match_ratio = len(match.group()) / len(field_label_lower)
                confidence = 0.7 + (0.25 * match_ratio)
                
                # Boost confidence if field type matches
                expected_type = self._get_expected_type(db_field)
                if expected_type and field.field_type == expected_type:
                    confidence += 0.1
                
                suggestions.append((db_field, min(0.95, confidence)))
        
        # Strategy 3: Use field type and context
        if not suggestions and field.field_type != FieldType.UNKNOWN:
            context_suggestions = self._suggest_by_context(field)
            suggestions.extend(context_suggestions)
        
        # Remove duplicates and sort by confidence
        seen = set()
        unique_suggestions = []
        for db_field, conf in suggestions:
            if db_field not in seen:
                seen.add(db_field)
                unique_suggestions.append((db_field, conf))
        
        unique_suggestions.sort(key=lambda x: x[1], reverse=True)
        
        return unique_suggestions[:5]  # Return top 5 suggestions
    
    def _get_expected_type(self, db_field: str) -> Optional[FieldType]:
        """Get expected field type for a database field"""
        category, field_name = db_field.split('.')
        field_info = self.db_schema.get(category, {}).get('fields', {}).get(field_name, {})
        
        type_mapping = {
            'string': FieldType.TEXT,
            'date': FieldType.DATE,
            'email': FieldType.EMAIL,
            'integer': FieldType.NUMBER,
            'currency': FieldType.CURRENCY,
            'enum': FieldType.TEXT,
            'text': FieldType.TEXT
        }
        
        return type_mapping.get(field_info.get('type'))
    
    def _suggest_by_context(self, field: FieldNode) -> List[Tuple[str, float]]:
        """Suggest mapping based on field context"""
        suggestions = []
        
        # Use field type to narrow down possibilities
        if field.field_type == FieldType.DATE:
            date_fields = [
                ('personal_info.date_of_birth', 0.6),
                ('immigration_info.last_entry_date', 0.5),
                ('immigration_info.status_expiry', 0.5),
                ('employment.start_date', 0.4),
                ('identification.passport_expiry', 0.4)
            ]
            suggestions.extend(date_fields)
        
        elif field.field_type == FieldType.EMAIL:
            suggestions.append(('contact_info.email_address', 0.9))
        
        elif field.field_type == FieldType.PHONE:
            phone_fields = [
                ('contact_info.phone_number', 0.8),
                ('contact_info.mobile_number', 0.7)
            ]
            suggestions.extend(phone_fields)
        
        return suggestions
    
    def _learn_mapping(self, field_label: str, db_field: str):
        """Learn from a successful mapping"""
        self.mapping_history[field_label] = db_field
        self.log(f"🧠 Learned mapping: '{field_label}' -> '{db_field}'", "learning")
    
    def _validate_mappings(self, result: FormExtractionResult):
        """Validate all mappings"""
        for field_key, db_field in result.field_mappings.items():
            field = result.get_field_by_key(field_key)
            if field and field.value:
                # Validate value against DB schema
                category, field_name = db_field.split('.')
                field_info = self.db_schema.get(category, {}).get('fields', {}).get(field_name, {})
                
                # Check pattern if exists
                if 'pattern' in field_info:
                    pattern = field_info['pattern']
                    if not re.match(pattern, field.value):
                        field.validation_errors.append(f"Value doesn't match expected pattern")
                        field.is_valid = False
                
                # Check enum values
                if field_info.get('type') == 'enum' and 'values' in field_info:
                    if field.value not in field_info['values']:
                        field.validation_errors.append(f"Value must be one of: {', '.join(field_info['values'])}")
                        field.is_valid = False

# ===== ENHANCED MASTER COORDINATOR =====
class EnhancedMasterCoordinator(BaseAgent):
    """Enhanced coordinator with full pipeline"""
    
    def __init__(self):
        super().__init__(
            "Enhanced Master Coordinator",
            AgentRole.KNOWLEDGE,
            "Orchestrates the entire extraction pipeline"
        )
        # Use the FIXED extraction agent
        self.agents = {
            'extractor': FixedEnhancedExtractionAgent(),
            'validator': SmartValidationAgent(),
            'mapper': IntelligentMappingAgent()
        }
        self.max_iterations = 3
    
    def execute(self, pdf_file, manual_mappings: Dict[str, str] = None) -> Dict[str, Any]:
        """Execute enhanced pipeline"""
        self.status = "active"
        self.log("🚀 Starting enhanced agentic form processing pipeline...", "info")
        
        try:
            start_time = time.time()
            
            # Phase 1: Extraction with KB
            self.log("\n📊 Phase 1: Enhanced Extraction", "info")
            best_result = None
            best_score = 0.0
            
            for iteration in range(self.max_iterations):
                self.log(f"\n🔄 Iteration {iteration + 1}/{self.max_iterations}", "info")
                
                # Extract
                result = self.agents['extractor'].execute(pdf_file)
                
                if not result:
                    self.log("Extraction failed", "error")
                    break
                
                # Validate
                is_valid, score, validation_results, corrected_result = self.agents['validator'].execute(result)
                result = corrected_result
                result.extraction_iterations = iteration + 1
                
                if score > best_score:
                    best_score = score
                    best_result = copy.deepcopy(result)
                
                if is_valid and score >= 0.85:
                    self.log(f"✨ Extraction successful with {score:.0%} confidence!", "success")
                    break
                
                if iteration < self.max_iterations - 1:
                    self.log(f"Current score {score:.0%} - attempting to improve...", "warning")
            
            if not best_result:
                self.log("Pipeline failed: No valid extraction", "error")
                return None
            
            # Phase 2: Intelligent Mapping
            self.log("\n🔗 Phase 2: Intelligent Database Mapping", "info")
            mapped_result = self.agents['mapper'].execute(best_result, manual_mappings)
            
            # Phase 3: Prepare comprehensive output
            output = self._prepare_enhanced_output(mapped_result)
            
            # Calculate final metrics
            end_time = time.time()
            total_time = end_time - start_time
            
            self.log(f"\n✅ Pipeline completed in {total_time:.2f}s!", "success")
            self.log(f"📊 Results: {mapped_result.total_fields} fields, "
                    f"{len(mapped_result.field_mappings)} mapped, "
                    f"{len(mapped_result.questionnaire_fields)} in questionnaire", "success")
            
            # Store in session
            if hasattr(st, 'session_state'):
                st.session_state.extraction_result = mapped_result
                st.session_state.pipeline_output = output
            
            return output
            
        except Exception as e:
            self.log(f"❌ Pipeline failed: {str(e)}", "error", traceback.format_exc())
            raise
    
    def _prepare_enhanced_output(self, result: FormExtractionResult) -> Dict[str, Any]:
        """Prepare enhanced output with all information"""
        parts_data = {}
        
        for part_num, part in result.parts.items():
            part_fields = []
            
            # Process fields with full information
            for root_field in sorted(part.root_fields, key=lambda f: self._parse_item_number(f.item_number)):
                field_data = self._field_to_enhanced_dict(root_field)
                part_fields.append(field_data)
            
            # Get validation report
            validation_report = part.get_validation_report()
            
            parts_data[f"part_{part_num}"] = {
                'number': part_num,
                'title': part.part_title,
                'page_range': f"{part.start_page}-{part.end_page}",
                'fields': part_fields,
                'total_fields': len(part.get_all_fields_flat()),
                'validation': validation_report
            }
        
        return {
            'form_info': {
                'number': result.form_number,
                'title': result.form_title,
                'total_fields': result.total_fields,
                'confidence_score': result.confidence_score,
                'extraction_iterations': result.extraction_iterations,
                'extraction_time': result.extraction_time
            },
            'parts': parts_data,
            'mappings': {
                'mapped': result.field_mappings,
                'manual': result.manual_mappings,
                'suggested': result.suggested_mappings,
                'questionnaire': result.questionnaire_fields
            },
            'statistics': {
                'total_parts': len(result.parts),
                'total_fields': result.total_fields,
                'mapped_fields': len(result.field_mappings),
                'questionnaire_fields': len(result.questionnaire_fields),
                'confidence_score': result.confidence_score,
                'valid_fields': sum(1 for p in result.parts.values() 
                                  for f in p.get_all_fields_flat() if f.is_valid)
            },
            'knowledge_base': {
                'form_matched': result.form_number in FormKnowledgeBase().form_structures,
                'kb_suggestions': len(result.kb_suggestions)
            }
        }
    
    def _field_to_enhanced_dict(self, field: FieldNode) -> Dict:
        """Convert field to enhanced dictionary"""
        data = field.to_dict()
        
        # Add children recursively
        if field.children:
            data['children'] = []
            for child in sorted(field.children, key=lambda f: self._parse_item_number(f.item_number)):
                data['children'].append(self._field_to_enhanced_dict(child))
        
        return data
    
    def _parse_item_number(self, item_num: str) -> Tuple:
        """Parse item number for sorting"""
        # Handle manual fields
        if item_num.startswith('M'):
            return (999, '', int(item_num[1:]))
        
        # Handle special fields
        if item_num.startswith('S'):
            return (998, '', int(item_num[1:]))
        
        # Regular parsing
        match = re.match(r'^(\d+)([a-z]?)(\d*)$', item_num)
        if match:
            main = int(match.group(1))
            sub = match.group(2) or ''
            nested = int(match.group(3)) if match.group(3) else 0
            return (main, sub, nested)
        return (999, '', 0)

# ===== UI HELPER FUNCTIONS =====
def display_enhanced_form_parts(result: FormExtractionResult):
    """Display form parts with enhanced controls"""
    if not result:
        st.info("No extraction results available")
        return
    
    # Summary metrics with KB indicator
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Total Fields", result.total_fields)
    
    with col2:
        st.metric("Parts", len(result.parts))
    
    with col3:
        st.metric("Confidence", f"{result.confidence_score:.0%}")
    
    with col4:
        mapped = len(result.field_mappings)
        st.metric("Mapped", f"{mapped}/{result.total_fields}")
    
    with col5:
        questionnaire = len(result.questionnaire_fields)
        st.metric("Questionnaire", questionnaire)
    
    # KB indicator
    if result.kb_matches:
        st.markdown('<div class="kb-indicator">📚 Knowledge Base Active</div>', unsafe_allow_html=True)
    
    # Display each part
    for part_num in sorted(result.parts.keys()):
        part = result.parts[part_num]
        
        # Part header with validation score
        validation_report = part.get_validation_report()
        st.markdown(
            f'<div class="part-header">'
            f'Part {part_num}: {part.part_title} '
            f'(Pages {part.start_page}-{part.end_page}, '
            f'{len(part.get_all_fields_flat())} fields, '
            f'{validation_report["validation_score"]:.0%} valid)'
            f'</div>',
            unsafe_allow_html=True
        )
        
        # Display fields with enhanced controls
        for i, root_field in enumerate(sorted(part.root_fields, 
                                             key=lambda f: int(f.item_number) if f.item_number.isdigit() else 999)):
            display_field_with_controls(root_field, level=0, parent_path=f"part{part_num}_field{i}")

def display_field_with_controls(field: FieldNode, level: int = 0, parent_path: str = ""):
    """Display field with enhanced controls including dropdown mapping"""
    indent = "  " * level
    field_path = f"{parent_path}_{field.key}" if parent_path else field.key
    
    # Create unique container
    with st.container():
        cols = st.columns([3, 2, 3, 1])
        
        with cols[0]:
            # Field number and label
            status_icon = ""
            if field.in_questionnaire:
                status_icon = "📋"
            elif not field.is_valid:
                status_icon = "⚠️"
            elif field.is_required and not field.value:
                status_icon = "❗"
            
            st.markdown(f"{indent}{status_icon} **{field.item_number}.** {field.label}")
            
            # Show checkbox options
            if field.checkbox_options:
                option_html = ""
                for opt in field.checkbox_options:
                    css_class = "checkbox-selected" if opt.is_selected else ""
                    option_html += f'<span class="checkbox-option {css_class}">{opt.text}</span>'
                st.markdown(option_html, unsafe_allow_html=True)
            
            # Show validation errors
            if field.validation_errors:
                for error in field.validation_errors:
                    st.error(f"❌ {error}", icon="🚫")
        
        with cols[1]:
            # Value input
            value_key = f"value_{field_path}_{id(field)}"
            
            if field.field_type == FieldType.DATE:
                try:
                    # Try to parse existing date value
                    if field.value:
                        try:
                            date_val = datetime.strptime(field.value, "%m/%d/%Y").date()
                        except:
                            date_val = None
                    else:
                        date_val = None
                    
                    new_value = st.date_input(
                        "Value",
                        value=date_val,
                        key=value_key,
                        label_visibility="collapsed"
                    )
                    if new_value:
                        field.value = new_value.strftime("%m/%d/%Y")
                except:
                    field.value = st.text_input(
                        "Value",
                        value=field.value,
                        key=value_key,
                        label_visibility="collapsed"
                    )
            
            elif field.field_type == FieldType.CHECKBOX and field.checkbox_options:
                # Multi-select for checkbox options
                selected = st.multiselect(
                    "Selected",
                    options=[opt.text for opt in field.checkbox_options],
                    default=[opt.text for opt in field.checkbox_options if opt.is_selected],
                    key=value_key,
                    label_visibility="collapsed"
                )
                # Update selections
                for opt in field.checkbox_options:
                    opt.is_selected = opt.text in selected
                field.value = ", ".join(selected)
            
            else:
                # Regular text input
                field.value = st.text_input(
                    "Value",
                    value=field.value,
                    key=value_key,
                    label_visibility="collapsed",
                    placeholder=f"Enter {field.field_type.value}"
                )
        
        with cols[2]:
            # Enhanced mapping dropdown
            mapping_key = f"mapping_{field_path}_{id(field)}"
            
            # Get mapping agent to access database fields
            agent = IntelligentMappingAgent()
            db_fields = agent.get_all_db_fields()
            
            # Build options list
            options = ["-- Unmapped --", "Move to Questionnaire"]
            
            # Add grouped database fields
            categories = {}
            for db_field in db_fields:
                category = db_field.split('.')[0]
                if category not in categories:
                    categories[category] = []
                categories[category].append(db_field)
            
            # Add options with categories
            for category in sorted(categories.keys()):
                options.append(f"--- {category.replace('_', ' ').title()} ---")
                options.extend(sorted(categories[category]))
            
            # Current selection
            current_selection = "-- Unmapped --"
            if field.in_questionnaire:
                current_selection = "Move to Questionnaire"
            elif field.mapped_to:
                current_selection = field.mapped_to
            elif field.suggested_mappings:
                # Show best suggestion
                best_suggestion = field.suggested_mappings[0]
                if best_suggestion[1] >= 0.7:
                    current_selection = best_suggestion[0]
            
            # Find index of current selection
            try:
                current_index = options.index(current_selection)
            except ValueError:
                current_index = 0
            
            # Mapping dropdown
            selected_mapping = st.selectbox(
                "Mapping",
                options=options,
                index=current_index,
                key=mapping_key,
                label_visibility="collapsed",
                help="Select database field to map to"
            )
            
            # Handle selection
            if selected_mapping and selected_mapping != current_selection:
                if selected_mapping == "Move to Questionnaire":
                    if 'extraction_result' in st.session_state:
                        st.session_state.extraction_result.move_to_questionnaire(field.key)
                        st.rerun()
                elif selected_mapping != "-- Unmapped --" and not selected_mapping.startswith("---"):
                    # Apply mapping
                    if 'manual_mappings' not in st.session_state:
                        st.session_state.manual_mappings = {}
                    st.session_state.manual_mappings[field.key] = selected_mapping
                    st.rerun()
            
            # Show mapping confidence if available
            if field.mapping_status == MappingStatus.SUGGESTED and field.suggested_mappings:
                best = field.suggested_mappings[0]
                st.caption(f"Suggested: {best[1]:.0%} confidence")
        
        with cols[3]:
            # Field type and confidence
            type_emoji = {
                FieldType.NAME: "👤",
                FieldType.DATE: "📅",
                FieldType.NUMBER: "🔢",
                FieldType.ADDRESS: "📍",
                FieldType.EMAIL: "📧",
                FieldType.PHONE: "📞",
                FieldType.CHECKBOX: "☑️",
                FieldType.SIGNATURE: "✍️",
                FieldType.CURRENCY: "💰"
            }
            st.markdown(f"{type_emoji.get(field.field_type, '📝')} {field.field_type.value}")
            
            # Confidence indicator
            conf_color = {
                ExtractionConfidence.HIGH: "🟢",
                ExtractionConfidence.MEDIUM: "🟡",
                ExtractionConfidence.LOW: "🔴"
            }
            st.markdown(f"{conf_color.get(field.confidence, '⚫')} {field.confidence.value}")
    
    # Display children
    for child in field.children:
        display_field_with_controls(child, level + 1, field_path)

def display_mapping_interface(result: FormExtractionResult):
    """Display enhanced mapping interface with dropdown support"""
    st.markdown("### 🔗 Database Mapping Interface")
    
    # Get mapping statistics
    agent = IntelligentMappingAgent()
    all_db_fields = agent.get_all_db_fields()
    
    unmapped_fields = []
    suggested_fields = []
    mapped_fields = []
    
    for part in result.parts.values():
        for field in part.get_all_fields_flat():
            if field.in_questionnaire:
                continue
            elif field.mapping_status == MappingStatus.UNMAPPED:
                unmapped_fields.append(field)
            elif field.mapping_status == MappingStatus.SUGGESTED:
                suggested_fields.append(field)
            elif field.mapping_status in [MappingStatus.MAPPED, MappingStatus.MANUAL]:
                mapped_fields.append(field)
    
    # Display statistics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Unmapped", len(unmapped_fields))
    with col2:
        st.metric("Suggested", len(suggested_fields))
    with col3:
        st.metric("Mapped", len(mapped_fields))
    with col4:
        st.metric("Total DB Fields", len(all_db_fields))
    
    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(["🔴 Unmapped", "🟡 Suggested", "🟢 Mapped", "🔧 Bulk Operations"])
    
    with tab1:
        if unmapped_fields:
            st.info(f"📌 {len(unmapped_fields)} fields need mapping")
            
            # Add search/filter
            search_term = st.text_input("Search unmapped fields", key="unmapped_search")
            
            filtered_fields = unmapped_fields
            if search_term:
                filtered_fields = [f for f in unmapped_fields 
                                 if search_term.lower() in f.label.lower() 
                                 or search_term.lower() in f.item_number.lower()]
            
            for field in filtered_fields[:20]:  # Show first 20
                with st.expander(f"{field.item_number}. {field.label} (Part {field.part_number})"):
                    display_enhanced_mapping_widget(field, result, all_db_fields)
            
            if len(filtered_fields) > 20:
                st.info(f"Showing 20 of {len(filtered_fields)} fields")
        else:
            st.success("✅ No unmapped fields!")
    
    with tab2:
        if suggested_fields:
            st.info(f"💡 {len(suggested_fields)} fields have suggestions")
            
            # Group by confidence level
            high_conf = [f for f in suggested_fields 
                        if f.suggested_mappings and f.suggested_mappings[0][1] >= 0.8]
            medium_conf = [f for f in suggested_fields 
                          if f.suggested_mappings and 0.6 <= f.suggested_mappings[0][1] < 0.8]
            low_conf = [f for f in suggested_fields 
                       if f.suggested_mappings and f.suggested_mappings[0][1] < 0.6]
            
            if high_conf:
                st.subheader("High Confidence Suggestions")
                for field in high_conf[:10]:
                    display_suggestion_widget_enhanced(field, result, all_db_fields)
            
            if medium_conf:
                st.subheader("Medium Confidence Suggestions")
                for field in medium_conf[:10]:
                    display_suggestion_widget_enhanced(field, result, all_db_fields)
            
            if low_conf:
                st.subheader("Low Confidence Suggestions")
                for field in low_conf[:5]:
                    display_suggestion_widget_enhanced(field, result, all_db_fields)
        else:
            st.info("No fields with suggestions")
    
    with tab3:
        if mapped_fields:
            st.success(f"✅ {len(mapped_fields)} fields mapped")
            
            # Group by category
            by_category = defaultdict(list)
            for field in mapped_fields:
                if field.mapped_to:
                    category = field.mapped_to.split('.')[0]
                    by_category[category].append(field)
            
            for category in sorted(by_category.keys()):
                with st.expander(f"{category.replace('_', ' ').title()} ({len(by_category[category])} fields)"):
                    for field in by_category[category]:
                        st.text(f"{field.item_number}. {field.label} → {field.mapped_to}")
        else:
            st.info("No mapped fields yet")
    
    with tab4:
        st.markdown("#### Bulk Operations")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🚀 Accept All High Confidence Suggestions", type="primary"):
                accepted = 0
                for field in suggested_fields:
                    if field.suggested_mappings and field.suggested_mappings[0][1] >= 0.8:
                        if 'manual_mappings' not in st.session_state:
                            st.session_state.manual_mappings = {}
                        st.session_state.manual_mappings[field.key] = field.suggested_mappings[0][0]
                        accepted += 1
                
                if accepted > 0:
                    st.success(f"✅ Accepted {accepted} high-confidence mappings")
                    st.rerun()
        
        with col2:
            if st.button("📋 Move All Unmapped to Questionnaire"):
                moved = 0
                for field in unmapped_fields:
                    result.move_to_questionnaire(field.key)
                    moved += 1
                
                if moved > 0:
                    st.success(f"✅ Moved {moved} fields to questionnaire")
                    st.rerun()
        
        # Manual field addition
        st.markdown("#### Add Custom Field")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            new_label = st.text_input("Field Label", key="new_field_label")
        
        with col2:
            new_type = st.selectbox(
                "Field Type",
                [t.value for t in FieldType],
                key="new_field_type"
            )
        
        with col3:
            new_part = st.number_input("Part Number", min_value=1, value=1, key="new_field_part")
        
        with col4:
            new_mapping = st.selectbox(
                "Map to",
                ["-- Select --"] + all_db_fields,
                key="new_field_mapping"
            )
        
        if st.button("➕ Add Field", type="primary"):
            if new_label and new_mapping != "-- Select --":
                # Create new field
                new_field = FieldNode(
                    item_number="M" + str(len(result.manual_mappings) + 1),
                    label=new_label,
                    field_type=FieldType(new_type),
                    part_number=new_part,
                    extraction_method="manual",
                    mapped_to=new_mapping,
                    mapping_status=MappingStatus.MANUAL
                )
                
                # Add to appropriate part
                if new_part in result.parts:
                    result.parts[new_part].add_field(new_field)
                    result.field_mappings[new_field.key] = new_mapping
                    st.success(f"Added field: {new_label} → {new_mapping}")
                    st.rerun()

def display_enhanced_mapping_widget(field: FieldNode, result: FormExtractionResult, all_db_fields: List[str]):
    """Enhanced mapping widget with full dropdown"""
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # Build grouped options
        options = ["-- Select Database Field --", "Move to Questionnaire"]
        
        # Group by category
        categories = {}
        for db_field in all_db_fields:
            category = db_field.split('.')[0]
            if category not in categories:
                categories[category] = []
            categories[category].append(db_field)
        
        # Add categorized options
        for category in sorted(categories.keys()):
            for field_name in sorted(categories[category]):
                options.append(field_name)
        
        selected = st.selectbox(
            f"Map '{field.label}' to:",
            options,
            key=f"map_widget_{field.key}_{id(field)}"
        )
    
    with col2:
        if selected == "Move to Questionnaire":
            if st.button("📋 Move", key=f"move_{field.key}_{id(field)}"):
                result.move_to_questionnaire(field.key)
                st.success(f"Moved to questionnaire")
                st.rerun()
        
        elif selected != "-- Select Database Field --":
            if st.button("✅ Apply", key=f"apply_{field.key}_{id(field)}", type="primary"):
                if 'manual_mappings' not in st.session_state:
                    st.session_state.manual_mappings = {}
                st.session_state.manual_mappings[field.key] = selected
                st.success(f"Mapped to: {selected}")
                st.rerun()

def display_suggestion_widget_enhanced(field: FieldNode, result: FormExtractionResult, all_db_fields: List[str]):
    """Enhanced suggestion widget"""
    if field.suggested_mappings:
        best_suggestion = field.suggested_mappings[0]
        
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            st.text(f"{field.item_number}. {field.label}")
            st.caption(f"→ {best_suggestion[0]} ({best_suggestion[1]:.0%})")
        
        with col2:
            if st.button("✅ Accept", key=f"accept_{field.key}_{id(field)}"):
                if 'manual_mappings' not in st.session_state:
                    st.session_state.manual_mappings = {}
                st.session_state.manual_mappings[field.key] = best_suggestion[0]
                st.rerun()
        
        with col3:
            if st.button("📋 Questionnaire", key=f"quest_{field.key}_{id(field)}"):
                result.move_to_questionnaire(field.key)
                st.rerun()

def display_questionnaire_interface(result: FormExtractionResult):
    """Display enhanced questionnaire interface"""
    st.markdown("### 📝 Questionnaire Interface")
    
    questionnaire_fields = result.get_questionnaire_fields()
    
    if not questionnaire_fields:
        st.info("No fields in questionnaire. Move fields here from the mapping interface.")
        return
    
    st.markdown(f"**{len(questionnaire_fields)} fields in questionnaire**")
    
    # Progress indicator
    completed = sum(1 for f in questionnaire_fields if f.value)
    progress = completed / len(questionnaire_fields) if questionnaire_fields else 0
    st.progress(progress)
    st.caption(f"{completed}/{len(questionnaire_fields)} completed")
    
    # Group by part
    parts_dict = defaultdict(list)
    for field in questionnaire_fields:
        parts_dict[field.part_number].append(field)
    
    # Display questionnaire
    responses = {}
    
    for part_num in sorted(parts_dict.keys()):
        st.markdown(f"#### Part {part_num}")
        
        for field in parts_dict[part_num]:
            # Create field container
            with st.container():
                col1, col2 = st.columns([4, 1])
                
                with col1:
                    # Display field with help text
                    if field.questionnaire_help_text:
                        st.caption(field.questionnaire_help_text)
                    
                    key = f"quest_input_{field.key}_{id(field)}"
                    
                    if field.field_type == FieldType.DATE:
                        value = st.date_input(
                            f"{field.item_number}. {field.label}",
                            key=key,
                            value=None
                        )
                        if value:
                            responses[field.key] = value.strftime("%m/%d/%Y")
                    
                    elif field.field_type == FieldType.CHECKBOX and field.checkbox_options:
                        selected = st.multiselect(
                            f"{field.item_number}. {field.label}",
                            options=[opt.text for opt in field.checkbox_options],
                            key=key
                        )
                        responses[field.key] = selected
                    
                    elif field.field_type in [FieldType.TEXT, FieldType.NAME, FieldType.ADDRESS]:
                        value = st.text_area(
                            f"{field.item_number}. {field.label}",
                            key=key,
                            height=100,
                            value=field.value or ""
                        )
                        if value:
                            responses[field.key] = value
                    
                    else:
                        value = st.text_input(
                            f"{field.item_number}. {field.label}",
                            key=key,
                            value=field.value or ""
                        )
                        if value:
                            responses[field.key] = value
                
                with col2:
                    # Option to remove from questionnaire
                    if st.button("❌", key=f"remove_quest_{field.key}_{id(field)}", 
                                help="Remove from questionnaire"):
                        field.in_questionnaire = False
                        field.mapping_status = MappingStatus.UNMAPPED
                        result.questionnaire_fields.remove(field.key)
                        st.rerun()
    
    # Save responses
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("💾 Save Responses", type="primary"):
            # Update field values
            for field_key, value in responses.items():
                field = result.get_field_by_key(field_key)
                if field:
                    field.value = str(value)
            
            st.success(f"✅ Saved {len(responses)} responses!")
    
    with col2:
        if st.button("📧 Email Questionnaire"):
            # Generate questionnaire as text
            questionnaire_text = generate_questionnaire_text(result, questionnaire_fields)
            st.text_area("Copy this questionnaire:", questionnaire_text, height=300)
    
    with col3:
        if st.button("📄 Download as PDF"):
            st.info("PDF generation would be implemented here")

def generate_questionnaire_text(result: FormExtractionResult, fields: List[FieldNode]) -> str:
    """Generate questionnaire as text"""
    lines = []
    lines.append(f"QUESTIONNAIRE - {result.form_number} {result.form_title}")
    lines.append("=" * 60)
    lines.append("")
    
    # Group by part
    parts_dict = defaultdict(list)
    for field in fields:
        parts_dict[field.part_number].append(field)
    
    for part_num in sorted(parts_dict.keys()):
        lines.append(f"PART {part_num}")
        lines.append("-" * 20)
        
        for field in parts_dict[part_num]:
            lines.append(f"\n{field.item_number}. {field.label}")
            
            if field.questionnaire_help_text:
                lines.append(f"   ({field.questionnaire_help_text})")
            
            if field.checkbox_options:
                for opt in field.checkbox_options:
                    lines.append(f"   [ ] {opt.text}")
            else:
                lines.append("   _" * 30)
            
            lines.append("")
    
    return "\n".join(lines)

def debug_extraction_results(result: FormExtractionResult):
    """Debug function to analyze extraction results"""
    print(f"\n=== EXTRACTION DEBUG ===")
    print(f"Form: {result.form_number} - {result.form_title}")
    print(f"Total fields extracted: {result.total_fields}")
    print(f"Parts found: {len(result.parts)}")
    
    for part_num in sorted(result.parts.keys()):
        part = result.parts[part_num]
        print(f"\n--- Part {part_num}: {part.part_title} ---")
        print(f"Pages: {part.start_page}-{part.end_page}")
        print(f"Total fields in part: {len(part.get_all_fields_flat())}")
        
        # Show field distribution
        field_numbers = defaultdict(int)
        for field in part.get_all_fields_flat():
            # Count main vs sub fields
            if re.match(r'^\d+, field.item_number):
                field_numbers['main'] += 1
            elif re.match(r'^\d+[a-z], field.item_number):
                field_numbers['sub_letter'] += 1
            elif re.match(r'^\d+[a-z]\d+, field.item_number):
                field_numbers['nested'] += 1
            else:
                field_numbers['other'] += 1
        
        print(f"Field distribution: {dict(field_numbers)}")
        
        # Show first few fields
        fields = part.get_all_fields_flat()[:10]
        print(f"\nFirst {len(fields)} fields:")
        for field in fields:
            print(f"  {field.item_number}. {field.label[:50]}{'...' if len(field.label) > 50 else ''}")
            if field.checkbox_options:
                print(f"    - Has {len(field.checkbox_options)} checkbox options")

def generate_sql_script(result: FormExtractionResult) -> str:
    """Generate SQL insert script from extraction results"""
    sql_lines = []
    
    # Header
    sql_lines.append("-- USCIS Form Data Export")
    sql_lines.append(f"-- Form: {result.form_number} - {result.form_title}")
    sql_lines.append(f"-- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    sql_lines.append("-- ===============================================\n")
    
    # Create tables if needed
    sql_lines.append("-- Create tables if they don't exist")
    sql_lines.append("""
CREATE TABLE IF NOT EXISTS form_submissions (
    id SERIAL PRIMARY KEY,
    form_number VARCHAR(50),
    form_title VARCHAR(200),
    submission_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confidence_score DECIMAL(3,2),
    status VARCHAR(50) DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS form_fields (
    id SERIAL PRIMARY KEY,
    submission_id INTEGER REFERENCES form_submissions(id),
    field_key VARCHAR(100),
    item_number VARCHAR(20),
    label TEXT,
    value TEXT,
    field_type VARCHAR(50),
    part_number INTEGER,
    page_number INTEGER,
    mapped_to VARCHAR(100),
    is_valid BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")
    
    # Insert submission
    sql_lines.append("\n-- Insert form submission")
    sql_lines.append(f"""
INSERT INTO form_submissions (form_number, form_title, confidence_score)
VALUES ('{result.form_number}', '{result.form_title}', {result.confidence_score:.2f})
RETURNING id;
""")
    
    sql_lines.append("\n-- Assuming the submission ID is 1 (replace with actual ID)")
    sql_lines.append("SET @submission_id = 1;\n")
    
    # Insert fields
    sql_lines.append("-- Insert form fields")
    
    for part in result.parts.values():
        for field in part.get_all_fields_flat():
            # Escape single quotes in values
            value = field.value.replace("'", "''") if field.value else ''
            label = field.label.replace("'", "''")
            mapped_to = field.mapped_to.replace("'", "''") if field.mapped_to else 'NULL'
            
            sql_lines.append(f"""
INSERT INTO form_fields (submission_id, field_key, item_number, label, value, 
                        field_type, part_number, page_number, mapped_to, is_valid)
VALUES (@submission_id, '{field.key}', '{field.item_number}', '{label}', '{value}',
        '{field.field_type.value}', {field.part_number}, {field.page}, 
        {f"'{mapped_to}'" if mapped_to != 'NULL' else 'NULL'}, {str(field.is_valid).upper()});""")
    
    # Add indexes
    sql_lines.append("\n-- Create indexes for better performance")
    sql_lines.append("""
CREATE INDEX IF NOT EXISTS idx_form_fields_submission_id ON form_fields(submission_id);
CREATE INDEX IF NOT EXISTS idx_form_fields_mapped_to ON form_fields(mapped_to);
CREATE INDEX IF NOT EXISTS idx_form_fields_field_type ON form_fields(field_type);
""")
    
    return "\n".join(sql_lines)

# ===== MAIN APPLICATION =====
def main():
    st.markdown(
        '<div class="main-header">'
        '<h1>🤖 Enhanced Agentic USCIS Form Reader</h1>'
        '<p>Complete extraction with all parts and fields (1, 1a, 1b, 1c, etc.)</p>'
        '</div>', 
        unsafe_allow_html=True
    )
    
    # Initialize session state
    if 'extraction_result' not in st.session_state:
        st.session_state.extraction_result = None
    if 'pipeline_output' not in st.session_state:
        st.session_state.pipeline_output = None
    if 'manual_mappings' not in st.session_state:
        st.session_state.manual_mappings = {}
    
    # Sidebar
    with st.sidebar:
        st.markdown("## ⚙️ Configuration")
        
        show_agent_logs = st.checkbox("Show Agent Activity", value=True)
        auto_map = st.checkbox("Auto-map fields", value=True)
        use_kb = st.checkbox("Use Knowledge Base", value=True)
        show_debug = st.checkbox("Show Debug Info", value=False)
        
        st.markdown("---")
        st.markdown("## 📊 Features Status")
        st.markdown("""
        ✅ **Fixed in this version:**
        - All parts detected (1, 2, 3, etc.)
        - All field formats (1, 1a, 1b, 1c, 1a1, etc.)
        - Hierarchical structure preserved
        - Knowledge Base integration
        - Smart validation
        - Database mapping
        - Questionnaire support
        """)
        
        # KB Status
        if use_kb:
            kb = FormKnowledgeBase()
            st.markdown("---")
            st.markdown("### 📚 Knowledge Base")
            st.markdown(f"**Forms:** {len(kb.form_structures)}")
            st.markdown(f"**Patterns:** {len(kb.field_patterns)}")
            st.markdown(f"**Rules:** {len(kb.validation_rules)}")
    
    # Main content tabs
    tabs = st.tabs([
        "📄 Upload & Extract",
        "📊 Review & Edit Fields",
        "🔗 Database Mapping",
        "📝 Questionnaire",
        "📈 Analytics",
        "💾 Export Results"
    ])
    
    # Tab 1: Upload & Extract
    with tabs[0]:
        st.markdown("### 📄 Upload USCIS Form")
        
        uploaded_file = st.file_uploader(
            "Choose a PDF form",
            type=['pdf'],
            help="Upload any USCIS form (I-90, I-130, I-485, I-765, I-129, etc.)"
        )
        
        if uploaded_file:
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.success(f"✅ Uploaded: {uploaded_file.name}")
                
                # Show file info
                file_size = len(uploaded_file.getvalue()) / 1024 / 1024
                st.caption(f"Size: {file_size:.2f} MB")
            
            with col2:
                if st.button("🚀 Process Form", type="primary", use_container_width=True):
                    # Create agent activity container
                    if show_agent_logs:
                        st.markdown("### 🤖 Agent Activity")
                        agent_container = st.container()
                        st.session_state.agent_container = agent_container
                    
                    with st.spinner("Processing form with enhanced agents..."):
                        # Create coordinator
                        coordinator = EnhancedMasterCoordinator()
                        
                        # Execute pipeline
                        output = coordinator.execute(
                            uploaded_file,
                            st.session_state.manual_mappings
                        )
                        
                        if output:
                            st.success("✅ Form processed successfully!")
                            st.balloons()
                            
                            # Show summary
                            st.markdown("### 📊 Processing Summary")
                            
                            col1, col2, col3, col4 = st.columns(4)
                            
                            with col1:
                                st.metric(
                                    "Total Fields",
                                    output['statistics']['total_fields']
                                )
                            
                            with col2:
                                st.metric(
                                    "Confidence",
                                    f"{output['statistics']['confidence_score']:.0%}"
                                )
                            
                            with col3:
                                st.metric(
                                    "Valid Fields",
                                    output['statistics']['valid_fields']
                                )
                            
                            with col4:
                                if output['knowledge_base']['form_matched']:
                                    st.metric(
                                        "KB Match",
                                        "✅ Yes"
                                    )
                                else:
                                    st.metric(
                                        "KB Match",
                                        "❌ No"
                                    )
        
        # Debug info
        if show_debug and st.session_state.extraction_result:
            with st.expander("🐛 Extraction Debug Info"):
                debug_info = io.StringIO()
                with contextlib.redirect_stdout(debug_info):
                    debug_extraction_results(st.session_state.extraction_result)
                st.code(debug_info.getvalue())
    
    # Tab 2: Review & Edit Fields
    with tabs[1]:
        st.markdown("### 📊 Review & Edit Extracted Fields")
        
        if st.session_state.extraction_result:
            # Add controls
            col1, col2, col3 = st.columns(3)
            
            with col1:
                show_invalid = st.checkbox("Show only invalid fields", value=False)
            
            with col2:
                show_unmapped = st.checkbox("Show only unmapped fields", value=False)
            
            with col3:
                if st.button("🔄 Refresh View"):
                    st.rerun()
            
            # Display fields
            display_enhanced_form_parts(st.session_state.extraction_result)
        else:
            st.info("No extraction results. Please process a form first.")
    
    # Tab 3: Database Mapping
    with tabs[2]:
        st.markdown("### 🔗 Configure Database Mapping")
        
        if st.session_state.extraction_result:
            display_mapping_interface(st.session_state.extraction_result)
            
            # Apply mappings button
            if st.button("💾 Apply All Mappings", type="primary"):
                # Re-run mapping agent
                agent = IntelligentMappingAgent()
                result = agent.execute(
                    st.session_state.extraction_result,
                    st.session_state.manual_mappings,
                    auto_map=auto_map
                )
                st.session_state.extraction_result = result
                st.success("✅ Mappings applied!")
                st.rerun()
        else:
            st.info("No extraction results. Please process a form first.")
    
    # Tab 4: Questionnaire
    with tabs[3]:
        if st.session_state.extraction_result:
            display_questionnaire_interface(st.session_state.extraction_result)
        else:
            st.info("No extraction results. Please process a form first.")
    
    # Tab 5: Analytics
    with tabs[4]:
        st.markdown("### 📈 Extraction Analytics")
        
        if st.session_state.pipeline_output:
            output = st.session_state.pipeline_output
            
            # Form info
            st.markdown("#### Form Information")
            form_df = pd.DataFrame([output['form_info']])
            st.dataframe(form_df)
            
            # Parts analysis
            st.markdown("#### Parts Analysis")
            parts_data = []
            for part_key, part_info in output['parts'].items():
                parts_data.append({
                    'Part': part_info['number'],
                    'Title': part_info['title'],
                    'Pages': part_info['page_range'],
                    'Fields': part_info['total_fields'],
                    'Valid %': f"{part_info['validation']['validation_score']:.0%}"
                })
            
            parts_df = pd.DataFrame(parts_data)
            st.dataframe(parts_df)
            
            # Field type distribution
            st.markdown("#### Field Type Distribution")
            type_counts = defaultdict(int)
            
            if st.session_state.extraction_result:
                for part in st.session_state.extraction_result.parts.values():
                    for field in part.get_all_fields_flat():
                        type_counts[field.field_type.value] += 1
            
            if type_counts:
                type_df = pd.DataFrame(
                    list(type_counts.items()),
                    columns=['Type', 'Count']
                )
                st.bar_chart(type_df.set_index('Type'))
            
            # Mapping statistics
            st.markdown("#### Mapping Statistics")
            stats = output['statistics']
            
            mapping_data = {
                'Status': ['Mapped', 'Questionnaire', 'Unmapped'],
                'Count': [
                    stats['mapped_fields'],
                    stats['questionnaire_fields'],
                    stats['total_fields'] - stats['mapped_fields'] - stats['questionnaire_fields']
                ]
            }
            
            mapping_df = pd.DataFrame(mapping_data)
            st.bar_chart(mapping_df.set_index('Status'))
        else:
            st.info("No analytics available. Please process a form first.")
    
    # Tab 6: Export
    with tabs[5]:
        st.markdown("### 💾 Export Results")
        
        if st.session_state.pipeline_output:
            output = st.session_state.pipeline_output
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                # JSON export
                json_str = json.dumps(output, indent=2, default=str)
                st.download_button(
                    "📦 Download JSON",
                    json_str,
                    "form_extraction.json",
                    mime="application/json",
                    use_container_width=True
                )
            
            with col2:
                # CSV export
                csv_data = []
                for part_key, part_data in output['parts'].items():
                    def flatten_fields(fields, parent_num=""):
                        for field in fields:
                            csv_data.append({
                                'Part': part_data['number'],
                                'Item': field['item_number'],
                                'Label': field['label'],
                                'Value': field['value'],
                                'Type': field['type'],
                                'Page': field['page'],
                                'Mapped To': field.get('mapped_to', ''),
                                'Status': field.get('mapping_status', ''),
                                'Valid': field.get('is_valid', True),
                                'In Questionnaire': field.get('in_questionnaire', False)
                            })
                            if 'children' in field:
                                flatten_fields(field['children'], field['item_number'])
                    
                    flatten_fields(part_data['fields'])
                
                if csv_data:
                    csv_buffer = io.StringIO()
                    writer = csv.DictWriter(csv_buffer, fieldnames=csv_data[0].keys())
                    writer.writeheader()
                    writer.writerows(csv_data)
                    
                    st.download_button(
                        "📊 Download CSV",
                        csv_buffer.getvalue(),
                        "form_extraction.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
            
            with col3:
                # Excel export - only if xlsxwriter is available
                if XLSXWRITER_AVAILABLE and csv_data:
                    df = pd.DataFrame(csv_data)
                    excel_buffer = io.BytesIO()
                    
                    with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                        # Main data
                        df.to_excel(writer, sheet_name='Fields', index=False)
                        
                        # Summary sheet
                        summary_data = {
                            'Metric': ['Form Number', 'Form Title', 'Total Fields', 
                                      'Mapped Fields', 'Questionnaire Fields', 
                                      'Confidence Score', 'Processing Time'],
                            'Value': [
                                output['form_info']['number'],
                                output['form_info']['title'],
                                output['statistics']['total_fields'],
                                output['statistics']['mapped_fields'],
                                output['statistics']['questionnaire_fields'],
                                f"{output['statistics']['confidence_score']:.2%}",
                                f"{output['form_info'].get('extraction_time', 0):.2f}s"
                            ]
                        }
                        summary_df = pd.DataFrame(summary_data)
                        summary_df.to_excel(writer, sheet_name='Summary', index=False)
                        
                        # Format the Excel file
                        workbook = writer.book
                        worksheet = writer.sheets['Fields']
                        
                        # Add filters
                        worksheet.autofilter(0, 0, len(df), len(df.columns) - 1)
                        
                        # Adjust column widths
                        for i, col in enumerate(df.columns):
                            max_length = max(
                                df[col].astype(str).map(len).max(),
                                len(col)
                            )
                            worksheet.set_column(i, i, max_length + 2)
                    
                    excel_buffer.seek(0)
                    
                    st.download_button(
                        "📑 Download Excel",
                        excel_buffer.read(),
                        "form_extraction.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                else:
                    st.info("Excel export requires xlsxwriter. Install with: pip install xlsxwriter")
            
            with col4:
                # Database insert script
                if st.session_state.extraction_result:
                    sql_script = generate_sql_script(st.session_state.extraction_result)
                    
                    st.download_button(
                        "🗄️ Download SQL",
                        sql_script,
                        "form_data_insert.sql",
                        mime="text/plain",
                        use_container_width=True
                    )
            
            # Preview section
            st.markdown("---")
            st.markdown("### 👁️ Preview Export Data")
            
            preview_tabs = st.tabs(["JSON", "Table View", "SQL Script"])
            
            with preview_tabs[0]:
                st.json(output)
            
            with preview_tabs[1]:
                if csv_data:
                    preview_df = pd.DataFrame(csv_data[:20])  # Show first 20 rows
                    st.dataframe(preview_df)
                    if len(csv_data) > 20:
                        st.caption(f"Showing first 20 of {len(csv_data)} rows")
            
            with preview_tabs[2]:
                if 'sql_script' in locals():
                    st.code(sql_script[:1000] + "..." if len(sql_script) > 1000 else sql_script, 
                           language='sql')
        else:
            st.info("No results to export. Please process a form first.")

# ===== RUN APPLICATION =====
if __name__ == "__main__":
    # Check dependencies
    if not PYMUPDF_AVAILABLE:
        st.error("❌ PyMuPDF is required but not installed!")
        st.code("pip install PyMuPDF")
        st.stop()
    
    if not XLSXWRITER_AVAILABLE:
        st.warning("⚠️ xlsxwriter not installed. Excel export will not be available.")
        st.code("pip install xlsxwriter")
    
    # Run main application
    main()
