#!/usr/bin/env python3
"""
Enhanced K Iterative USCIS Form Reader
With iterative extraction, validation, field mapping, and export functionality
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
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from collections import defaultdict
from abc import ABC, abstractmethod
import copy
from enum import Enum
from pathlib import Path

import streamlit as st
import pandas as pd

# Try imports
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    fitz = None

try:
    import xlsxwriter
    XLSXWRITER_AVAILABLE = True
except ImportError:
    XLSXWRITER_AVAILABLE = False

# Page config
st.set_page_config(
    page_title="Enhanced Iterative USCIS Form Reader",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS Styling
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        color: white;
        padding: 2rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
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
    
    .iteration-card {
        background: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    
    .part-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1.2rem;
        border-radius: 8px;
        margin: 1rem 0;
        font-weight: bold;
        box-shadow: 0 3px 6px rgba(0,0,0,0.1);
    }
    
    .field-card {
        background: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    
    .field-row {
        border-bottom: 1px solid #e0e0e0;
        padding: 0.5rem 0;
    }
    
    .field-row:hover {
        background: #f5f5f5;
    }
    
    .confidence-high { color: #4CAF50; font-weight: bold; }
    .confidence-medium { color: #FF9800; font-weight: bold; }
    .confidence-low { color: #f44336; font-weight: bold; }
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
    UNKNOWN = "unknown"

class ExtractionConfidence(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"

class ValidationResult(Enum):
    VALID = "valid"
    NEEDS_IMPROVEMENT = "needs_improvement"
    INVALID = "invalid"

class ExtractionStrategy(Enum):
    BASIC = "basic"
    ENHANCED_OCR = "enhanced_ocr"
    LAYOUT_BASED = "layout_based"
    PATTERN_MATCHING = "pattern_matching"
    CONTEXT_AWARE = "context_aware"

class MappingStatus(Enum):
    MAPPED = "mapped"
    UNMAPPED = "unmapped"
    MANUAL = "manual"
    SUGGESTED = "suggested"
    QUESTIONNAIRE = "questionnaire"

# ===== DATA CLASSES =====
@dataclass
class CheckboxOption:
    """Represents a checkbox option"""
    text: str
    is_selected: bool = False
    confidence: float = 0.0

@dataclass
class ValidationFeedback:
    """Feedback from validation to guide re-extraction"""
    result: ValidationResult
    confidence: float
    issues: List[Dict[str, Any]] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    missing_fields: List[str] = field(default_factory=list)
    empty_fields: List[str] = field(default_factory=list)
    suspicious_values: Dict[str, str] = field(default_factory=dict)

@dataclass
class ExtractionContext:
    """Context for iterative extraction"""
    iteration: int = 0
    max_iterations: int = 3
    strategies_tried: List[ExtractionStrategy] = field(default_factory=list)
    feedback_history: List[ValidationFeedback] = field(default_factory=list)
    improvements: Dict[str, Any] = field(default_factory=dict)
    
    def should_continue(self) -> bool:
        """Check if we should continue iterating"""
        return self.iteration < self.max_iterations
    
    def get_next_strategy(self) -> ExtractionStrategy:
        """Get next extraction strategy based on feedback"""
        if not self.strategies_tried:
            return ExtractionStrategy.BASIC
        
        if ExtractionStrategy.ENHANCED_OCR not in self.strategies_tried:
            return ExtractionStrategy.ENHANCED_OCR
        elif ExtractionStrategy.LAYOUT_BASED not in self.strategies_tried:
            return ExtractionStrategy.LAYOUT_BASED
        elif ExtractionStrategy.PATTERN_MATCHING not in self.strategies_tried:
            return ExtractionStrategy.PATTERN_MATCHING
        else:
            return ExtractionStrategy.CONTEXT_AWARE

@dataclass
class FieldNode:
    """Enhanced field node with value extraction"""
    item_number: str
    label: str
    field_type: FieldType = FieldType.UNKNOWN
    value: str = ""
    raw_value: str = ""  # Original extracted value
    cleaned_value: str = ""  # Cleaned/processed value
    checkbox_options: List[CheckboxOption] = field(default_factory=list)
    
    # Enhanced extraction metadata
    extraction_confidence: float = 0.0
    value_bbox: Optional[List[float]] = None
    label_bbox: Optional[List[float]] = None
    extraction_method: str = ""
    
    # Hierarchy
    parent: Optional['FieldNode'] = None
    children: List['FieldNode'] = field(default_factory=list)
    
    # Location
    page: int = 1
    part_number: int = 1
    part_name: str = "Part 1"
    
    # Unique identification
    key: str = ""
    content_hash: str = ""
    
    # Mapping
    mapping_status: MappingStatus = MappingStatus.UNMAPPED
    mapped_to: Optional[str] = None
    mapping_confidence: float = 0.0
    suggested_mappings: List[Tuple[str, float]] = field(default_factory=list)
    
    # Questionnaire
    in_questionnaire: bool = False
    
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
            'extraction_confidence': self.extraction_confidence,
            'extraction_method': self.extraction_method,
            'mapping_status': self.mapping_status.value,
            'mapped_to': self.mapped_to,
            'in_questionnaire': self.in_questionnaire,
            'is_valid': self.is_valid,
            'checkbox_options': [
                {'text': opt.text, 'selected': opt.is_selected}
                for opt in self.checkbox_options
            ] if self.checkbox_options else None
        }

@dataclass
class PartStructure:
    """Part structure with fields"""
    part_number: int
    part_name: str
    part_title: str = ""
    start_page: int = 1
    end_page: int = 1
    root_fields: List[FieldNode] = field(default_factory=list)
    field_registry: Dict[str, FieldNode] = field(default_factory=dict)
    
    def add_field(self, field_node: FieldNode) -> bool:
        """Add field with hierarchy management"""
        field_node.part_number = self.part_number
        field_node.part_name = self.part_name
        
        # Register field
        self.field_registry[field_node.item_number] = field_node
        
        # Add to hierarchy
        if self._is_root_field(field_node.item_number):
            self.root_fields.append(field_node)
        else:
            parent_num = self._get_parent_number(field_node.item_number)
            if parent_num and parent_num in self.field_registry:
                parent = self.field_registry[parent_num]
                parent.add_child(field_node)
            else:
                self.root_fields.append(field_node)
        
        return True
    
    def _is_root_field(self, item_number: str) -> bool:
        """Check if this is a root field"""
        return bool(re.match(r'^\d+$', item_number))
    
    def _get_parent_number(self, item_number: str) -> Optional[str]:
        """Get parent number from item number"""
        if re.match(r'^\d+[a-z]$', item_number):
            return item_number[:-1]
        elif re.match(r'^\d+[a-z]\d+$', item_number):
            return re.match(r'^(\d+[a-z])', item_number).group(1)
        elif re.match(r'^\d+\.\d+$', item_number):
            return item_number.split('.')[0]
        return None
    
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

@dataclass
class FormExtractionResult:
    """Complete extraction result"""
    form_number: str
    form_title: str
    parts: Dict[int, PartStructure] = field(default_factory=dict)
    
    # Metadata
    total_fields: int = 0
    confidence_score: float = 0.0
    extraction_time: float = 0.0
    
    # Extraction context
    extraction_context: Optional[ExtractionContext] = None
    
    # Mapping data
    field_mappings: Dict[str, str] = field(default_factory=dict)
    questionnaire_fields: List[str] = field(default_factory=list)
    
    # Knowledge base
    kb_matches: Dict[str, Any] = field(default_factory=dict)
    
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
    
    def update_mapping(self, field_key: str, target: str):
        """Update field mapping"""
        field = self.get_field_by_key(field_key)
        if field:
            if target == "questionnaire":
                self.move_to_questionnaire(field_key)
            else:
                self.field_mappings[field_key] = target
                field.mapped_to = target
                field.mapping_status = MappingStatus.MANUAL
    
    def get_extraction_summary(self) -> Dict[str, Any]:
        """Get summary of extraction process"""
        summary = {
            "total_fields": self.total_fields,
            "confidence_score": self.confidence_score,
            "extraction_time": self.extraction_time,
            "empty_fields": sum(1 for p in self.parts.values() 
                               for f in p.get_all_fields_flat() if not f.value),
            "high_confidence_fields": sum(1 for p in self.parts.values() 
                                        for f in p.get_all_fields_flat() 
                                        if f.extraction_confidence > 0.8)
        }
        
        if self.extraction_context:
            summary.update({
                "iterations": self.extraction_context.iteration,
                "strategies_used": [s.value for s in self.extraction_context.strategies_tried],
            })
        
        return summary

# ===== KNOWLEDGE BASE =====
class FormKnowledgeBase:
    """Knowledge base for USCIS forms"""
    
    def __init__(self):
        self.form_structures = self._init_form_structures()
        self.field_patterns = self._init_field_patterns()
        self.validation_rules = self._init_validation_rules()
        
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
                "page_count": 12
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
                    10: "Applicant's Statement",
                    11: "Interpreter's Contact Information",
                    12: "Contact Information, Declaration, and Signature"
                },
                "expected_fields": 120,
                "page_count": 20
            }
        }
    
    def _init_field_patterns(self) -> Dict[str, Dict]:
        """Initialize field extraction patterns"""
        return {
            "name_fields": {
                "patterns": [
                    r"Family Name \(Last Name\)",
                    r"Given Name \(First Name\)",
                    r"Middle Name"
                ],
                "type": FieldType.NAME
            },
            "date_fields": {
                "patterns": [
                    r"Date of Birth",
                    r"Date of Filing",
                    r"Expiration Date"
                ],
                "type": FieldType.DATE
            },
            "number_fields": {
                "patterns": [
                    r"A-Number",
                    r"USCIS Online Account Number",
                    r"Social Security Number"
                ],
                "type": FieldType.NUMBER
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
            }
        }
    
    def get_form_info(self, form_number: str) -> Optional[Dict]:
        """Get information about a specific form"""
        return self.form_structures.get(form_number)
    
    def suggest_field_type(self, label: str) -> Tuple[FieldType, float]:
        """Suggest field type based on label"""
        label_lower = label.lower()
        
        # Check specific patterns
        for pattern_group, info in self.field_patterns.items():
            for pattern in info["patterns"]:
                if re.search(pattern.lower(), label_lower):
                    return info["type"], 0.9
        
        # General heuristics
        if any(word in label_lower for word in ["check", "select", "mark"]):
            return FieldType.CHECKBOX, 0.8
        elif any(word in label_lower for word in ["date", "birth", "expir"]):
            return FieldType.DATE, 0.85
        elif any(word in label_lower for word in ["number", "no.", "#"]):
            return FieldType.NUMBER, 0.8
        elif any(word in label_lower for word in ["email", "e-mail"]):
            return FieldType.EMAIL, 0.95
        elif any(word in label_lower for word in ["phone", "telephone"]):
            return FieldType.PHONE, 0.9
        elif any(word in label_lower for word in ["signature", "sign"]):
            return FieldType.SIGNATURE, 0.95
        
        return FieldType.TEXT, 0.5

# ===== ENHANCED EXTRACTION AGENT =====
class EnhancedExtractionAgent:
    """Enhanced extraction with multiple strategies and value extraction"""
    
    def __init__(self):
        self.name = "Enhanced Extraction Agent"
        self.doc = None
        self.current_strategy = ExtractionStrategy.BASIC
        self.knowledge_base = FormKnowledgeBase()
        
    def extract_with_strategy(self, pdf_file, strategy: ExtractionStrategy, 
                            previous_result: Optional[FormExtractionResult] = None,
                            feedback: Optional[ValidationFeedback] = None) -> FormExtractionResult:
        """Extract using specific strategy"""
        self.current_strategy = strategy
        self.log(f"🔍 Extracting with strategy: {strategy.value}")
        
        # Open PDF if needed
        if not self.doc:
            if hasattr(pdf_file, 'read'):
                pdf_file.seek(0)
                pdf_bytes = pdf_file.read()
            else:
                pdf_bytes = pdf_file
            self.doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        # Apply strategy
        if strategy == ExtractionStrategy.BASIC:
            return self._basic_extraction()
        elif strategy == ExtractionStrategy.ENHANCED_OCR:
            return self._enhanced_ocr_extraction(previous_result, feedback)
        elif strategy == ExtractionStrategy.LAYOUT_BASED:
            return self._layout_based_extraction(previous_result, feedback)
        elif strategy == ExtractionStrategy.PATTERN_MATCHING:
            return self._pattern_matching_extraction(previous_result, feedback)
        elif strategy == ExtractionStrategy.CONTEXT_AWARE:
            return self._context_aware_extraction(previous_result, feedback)
        
        return self._basic_extraction()
    
    def _basic_extraction(self) -> FormExtractionResult:
        """Basic extraction strategy"""
        # Identify form
        form_info = self._identify_form()
        
        result = FormExtractionResult(
            form_number=form_info['number'],
            form_title=form_info['title']
        )
        
        # Extract all text blocks
        all_blocks = []
        for page_num in range(len(self.doc)):
            page = self.doc[page_num]
            blocks = self._extract_page_blocks(page, page_num + 1)
            all_blocks.extend(blocks)
        
        # Find parts
        parts_info = self._find_parts(all_blocks)
        
        # Extract fields by parts
        self._extract_fields_by_parts(all_blocks, parts_info, result)
        
        # Calculate totals
        result.total_fields = sum(len(part.get_all_fields_flat()) for part in result.parts.values())
        
        self.log(f"Basic extraction found {result.total_fields} fields")
        
        return result
    
    def _identify_form(self) -> Dict[str, str]:
        """Identify form type"""
        if not self.doc or self.doc.page_count == 0:
            return {"number": "Unknown", "title": "Unknown Form"}
        
        first_page_text = self.doc[0].get_text()
        
        # Try to match against known forms
        for form_number, form_info in self.knowledge_base.form_structures.items():
            pattern = rf"Form\s+{re.escape(form_number)}\b"
            if re.search(pattern, first_page_text, re.IGNORECASE):
                self.log(f"🎯 Identified form: {form_number} - {form_info['title']}", "success")
                return {"number": form_number, "title": form_info['title']}
        
        # Fallback to pattern matching
        form_patterns = [
            (r'Form\s+(I-\d+[A-Z]?)', 'USCIS Form'),
            (r'Form\s+(N-\d+)', 'USCIS Form'),
            (r'Form\s+(G-\d+)', 'USCIS Form'),
        ]
        
        for pattern, prefix in form_patterns:
            match = re.search(pattern, first_page_text, re.IGNORECASE)
            if match:
                form_number = match.group(1)
                return {"number": form_number, "title": f"{prefix} {form_number}"}
        
        return {"number": "Unknown", "title": "Unknown Form"}
    
    def _extract_page_blocks(self, page, page_num: int) -> List[Dict]:
        """Extract text blocks from page"""
        blocks = []
        page_dict = page.get_text("dict")
        
        for block in page_dict["blocks"]:
            if block["type"] == 0:  # Text block
                for line in block["lines"]:
                    text = " ".join(span["text"] for span in line["spans"])
                    if text.strip():
                        blocks.append({
                            'text': text.strip(),
                            'page': page_num,
                            'bbox': line.get("bbox", [0, 0, 0, 0]),
                            'y_pos': line.get("bbox", [0, 0, 0, 0])[1],
                            'x_pos': line.get("bbox", [0, 0, 0, 0])[0]
                        })
        
        blocks.sort(key=lambda b: (b['page'], b['y_pos'], b['x_pos']))
        return blocks
    
    def _find_parts(self, blocks: List[Dict]) -> Dict[int, Dict]:
        """Find all parts in document"""
        parts_info = {}
        
        part_patterns = [
            r'^Part\s+(\d+)[.:]\s*(.*)$',
            r'^Part\s+(\d+)\s*[-–—]\s*(.*)$',
            r'^Part\s+(\d+)\s*$',
            r'^PART\s+(\d+)[.:]\s*(.*)$'
        ]
        
        for i, block in enumerate(blocks):
            text = block['text']
            
            for pattern in part_patterns:
                match = re.match(pattern, text, re.IGNORECASE)
                if match:
                    part_num = int(match.group(1))
                    title = match.group(2).strip() if match.lastindex >= 2 else ""
                    
                    # Look for title in next line if empty
                    if not title and i + 1 < len(blocks):
                        next_block = blocks[i + 1]
                        if not self._is_field_start(next_block['text']):
                            title = next_block['text']
                    
                    parts_info[part_num] = {
                        'number': part_num,
                        'title': title,
                        'start_block': i,
                        'page': block['page']
                    }
                    
                    self.log(f"📋 Found Part {part_num}: {title}", "success")
                    break
        
        # Set end blocks
        part_numbers = sorted(parts_info.keys())
        for i, part_num in enumerate(part_numbers):
            if i + 1 < len(part_numbers):
                next_part = part_numbers[i + 1]
                parts_info[part_num]['end_block'] = parts_info[next_part]['start_block'] - 1
            else:
                parts_info[part_num]['end_block'] = len(blocks) - 1
        
        return parts_info
    
    def _is_field_start(self, text: str) -> bool:
        """Check if text is a field start"""
        patterns = [
            r'^\d+\.\s+\w+',
            r'^\d+\.\s*[a-z]\.\s+\w+',
            r'^\d+[a-z]\.\s+\w+',
            r'^[A-Z]\.\s+\w+',
            r'^\(\d+\)\s+\w+'
        ]
        return any(re.match(p, text) for p in patterns)
    
    def _extract_fields_by_parts(self, blocks: List[Dict], parts_info: Dict[int, Dict], 
                                 result: FormExtractionResult):
        """Extract fields for each part"""
        for part_num in sorted(parts_info.keys()):
            part_info = parts_info[part_num]
            
            # Create part
            part = PartStructure(
                part_number=part_num,
                part_name=f"Part {part_num}",
                part_title=part_info['title'],
                start_page=part_info['page']
            )
            
            # Extract fields
            start = part_info['start_block']
            end = part_info['end_block']
            
            i = start
            while i <= end and i < len(blocks):
                block = blocks[i]
                
                # Skip part headers
                if re.match(r'^Part\s+\d+', block['text'], re.IGNORECASE):
                    i += 1
                    continue
                
                # Try to extract field
                field = self._extract_field(blocks, i, end)
                if field:
                    part.add_field(field)
                    if field.checkbox_options:
                        i += len(field.checkbox_options) + 1
                    else:
                        i += 1
                else:
                    i += 1
            
            result.parts[part_num] = part
    
   def _extract_field(self, blocks: List[Dict], idx: int, end_idx: int) -> Optional[FieldNode]:
    """Extract field from block WITH VALUE"""
    if idx >= len(blocks):
        return None
    
    block = blocks[idx]
    text = block['text']
    
    patterns = [
        (r'^(\d+)\.([a-z])\.(\d+)\.\s+(.+)', lambda m: (m.group(1)+m.group(2)+m.group(3), m.group(4))),
        (r'^(\d+)([a-z])(\d+)\.\s+(.+)', lambda m: (m.group(1)+m.group(2)+m.group(3), m.group(4))),
        (r'^(\d+)\.([a-z])\.\s+(.+)', lambda m: (m.group(1)+m.group(2), m.group(3))),
        (r'^(\d+)([a-z])\.\s+(.+)', lambda m: (m.group(1)+m.group(2), m.group(3))),
        (r'^(\d+)\.\s+(.+)', lambda m: (m.group(1), m.group(2))),
    ]
    
    for pattern, parser in patterns:
        match = re.match(pattern, text)
        if match:
            try:
                item_number, label = parser(match)
                
                field = FieldNode(
                    item_number=item_number,
                    label=label.strip(),
                    page=block['page'],
                    label_bbox=block.get('bbox')
                )
                
                # Suggest field type
                field.field_type, conf = self.knowledge_base.suggest_field_type(label)
                field.extraction_confidence = conf * 0.5  # Basic extraction, lower confidence
                field.extraction_method = "basic"
                
                # Look for checkboxes
                if field.field_type == FieldType.CHECKBOX or "select" in label.lower():
                    field.checkbox_options = self._extract_checkboxes(blocks, idx + 1, end_idx)
                else:
                    # EXTRACT VALUE - Look ahead for the field value
                    field.value = self._extract_field_value(blocks, idx, end_idx, field)
                
                return field
            except Exception:
                continue
    
    return None


    def _extract_page_blocks(self, page, page_num: int) -> List[Dict]:
    """Extract text blocks from page with better structure"""
    blocks = []
    page_dict = page.get_text("dict")
    
    for block in page_dict["blocks"]:
        if block["type"] == 0:  # Text block
            for line in block["lines"]:
                # Get full line text
                line_text = ""
                line_bbox = [float('inf'), float('inf'), float('-inf'), float('-inf')]
                
                for span in line["spans"]:
                    span_text = span["text"]
                    if span_text.strip():
                        if line_text and not line_text.endswith(' '):
                            line_text += " "
                        line_text += span_text
                        
                        # Update line bbox
                        span_bbox = span.get("bbox", [0, 0, 0, 0])
                        line_bbox[0] = min(line_bbox[0], span_bbox[0])
                        line_bbox[1] = min(line_bbox[1], span_bbox[1])
                        line_bbox[2] = max(line_bbox[2], span_bbox[2])
                        line_bbox[3] = max(line_bbox[3], span_bbox[3])
                
                if line_text.strip():
                    blocks.append({
                        'text': line_text.strip(),
                        'page': page_num,
                        'bbox': line_bbox,
                        'y_pos': line_bbox[1],
                        'x_pos': line_bbox[0]
                    })
    
    # Sort by position (top to bottom, left to right)
    blocks.sort(key=lambda b: (b['page'], b['y_pos'], b['x_pos']))
    return blocks
    
    def _extract_checkboxes(self, blocks: List[Dict], start_idx: int, end_idx: int) -> List[CheckboxOption]:
        """Extract checkbox options"""
        options = []
        
        patterns = [
            (r'^[□☐]\s*(.+)', False),
            (r'^[☑☒✓]\s*(.+)', True),
            (r'^\[\s*\]\s*(.+)', False),
            (r'^\[X\]\s*(.+)', True),
        ]
        
        for i in range(start_idx, min(end_idx + 1, start_idx + 10)):
            if i >= len(blocks):
                break
            
            text = blocks[i]['text']
            
            if self._is_field_start(text):
                break
            
            for pattern, is_selected in patterns:
                match = re.match(pattern, text)
                if match:
                    options.append(CheckboxOption(
                        text=match.group(1).strip(),
                        is_selected=is_selected
                    ))
                    break
        
        return options
    
    def _enhanced_ocr_extraction(self, previous: Optional[FormExtractionResult], 
                               feedback: Optional[ValidationFeedback]) -> FormExtractionResult:
        """Enhanced OCR with better value extraction"""
        self.log("🔤 Using enhanced OCR for better value extraction")
        
        result = copy.deepcopy(previous) if previous else self._basic_extraction()
        
        # Focus on empty fields
        fields_to_improve = []
        if feedback:
            for field_key in feedback.empty_fields:
                field = result.get_field_by_key(field_key)
                if field:
                    fields_to_improve.append(field)
        
        # Re-extract with enhanced settings
        for page_num in range(len(self.doc)):
            page = self.doc[page_num]
            
            # Get text with positions
            words = page.get_text("words")
            
            # Try to find values for empty fields
            for field in fields_to_improve:
                if field.page == page_num + 1:
                    value = self._find_field_value(field, words)
                    if value:
                        field.value = value
                        field.raw_value = value
                        field.extraction_confidence = 0.7
                        field.extraction_method = "enhanced_ocr"
        
        return result
    
    def _find_field_value(self, field: FieldNode, words: List) -> Optional[str]:
        """Find value for a field using word positions"""
        if not field.label_bbox:
            return None
        
        # Look for words to the right or below the label
        potential_values = []
        
        for word in words:
            word_bbox = list(word[:4])
            word_text = word[4]
            
            # Skip if it's part of the label
            if word_text in field.label:
                continue
            
            # Check if word is to the right
            if (word_bbox[0] > field.label_bbox[2] and 
                abs(word_bbox[1] - field.label_bbox[1]) < 20):
                potential_values.append((word_text, word_bbox[0]))
            
            # Check if word is below
            elif (word_bbox[1] > field.label_bbox[3] and 
                  word_bbox[1] - field.label_bbox[3] < 50):
                potential_values.append((word_text, word_bbox[1]))
        
        if potential_values:
            # Sort by proximity and join
            potential_values.sort(key=lambda x: x[1])
            return " ".join(v[0] for v in potential_values[:3])
        
        return None
    
    def _layout_based_extraction(self, previous: Optional[FormExtractionResult], 
                               feedback: Optional[ValidationFeedback]) -> FormExtractionResult:
        """Layout-based extraction using spatial relationships"""
        self.log("📐 Using layout analysis for field-value pairing")
        
        result = copy.deepcopy(previous) if previous else self._basic_extraction()
        
        # Implement layout-based improvements
        # This is a simplified version - would need more sophisticated layout analysis
        
        return result
    
    def _pattern_matching_extraction(self, previous: Optional[FormExtractionResult], 
                                   feedback: Optional[ValidationFeedback]) -> FormExtractionResult:
        """Pattern-based extraction for specific field types"""
        self.log("🎯 Using pattern matching for typed field extraction")
        
        result = copy.deepcopy(previous) if previous else self._basic_extraction()
        
        # Define patterns for common field types
        patterns = {
            'a_number': (r'[Aa][-\s]?\d{7,9}', FieldType.NUMBER),
            'ssn': (r'\d{3}-?\d{2}-?\d{4}', FieldType.NUMBER),
            'date': (r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', FieldType.DATE),
            'phone': (r'[\(\[]?\d{3}[\)\]]?[-\s]?\d{3}[-\s]?\d{4}', FieldType.PHONE),
            'email': (r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', FieldType.EMAIL),
        }
        
        # Extract values matching patterns
        for page_num in range(len(self.doc)):
            page = self.doc[page_num]
            text = page.get_text()
            
            # Find fields that might match these patterns
            for part in result.parts.values():
                for field in part.get_all_fields_flat():
                    if field.page == page_num + 1 and not field.value:
                        # Check if field label suggests a pattern type
                        for pattern_name, (pattern, field_type) in patterns.items():
                            if pattern_name in field.label.lower().replace('-', '').replace(' ', ''):
                                # Look for pattern in page text
                                matches = re.finditer(pattern, text)
                                for match in matches:
                                    field.value = match.group()
                                    field.field_type = field_type
                                    field.extraction_confidence = 0.85
                                    field.extraction_method = "pattern_matching"
                                    break
        
        return result
    
    def _context_aware_extraction(self, previous: Optional[FormExtractionResult], 
                                feedback: Optional[ValidationFeedback]) -> FormExtractionResult:
        """Context-aware extraction using surrounding text"""
        self.log("🧠 Using context-aware extraction with field relationships")
        
        result = copy.deepcopy(previous) if previous else self._basic_extraction()
        
        # This would implement more sophisticated context analysis
        # For now, it's a placeholder for the most advanced strategy
        
        return result
    
    def log(self, message: str, level: str = "info"):
        """Log message"""
        if hasattr(st, 'session_state') and 'agent_container' in st.session_state:
            with st.session_state.agent_container:
                icon = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌"}.get(level, "📝")
                css_class = "agent-card"
                if level == "error":
                    css_class += " agent-error"
                elif level == "success":
                    css_class += " agent-success"
                else:
                    css_class += " agent-active"
                
                st.markdown(
                    f'<div class="{css_class}">'
                    f'{icon} <strong>{self.name}</strong>: {message}'
                    f'</div>', 
                    unsafe_allow_html=True
                )

# ===== ENHANCED VALIDATION AGENT =====
class EnhancedValidationAgent:
    """Enhanced validation with detailed feedback"""
    
    def __init__(self):
        self.name = "Enhanced Validation Agent"
        self.knowledge_base = FormKnowledgeBase()
    
    def validate_iteratively(self, result: FormExtractionResult, 
                           context: ExtractionContext) -> ValidationFeedback:
        """Validate with detailed feedback for iteration"""
        self.log(f"🔍 Validating extraction (iteration {context.iteration})")
        
        feedback = ValidationFeedback(
            result=ValidationResult.VALID,
            confidence=1.0
        )
        
        # Check completeness
        empty_fields = self._find_empty_fields(result)
        if empty_fields:
            feedback.empty_fields = empty_fields
            feedback.confidence *= 0.8
            feedback.issues.append({
                "type": "empty_fields",
                "count": len(empty_fields),
                "fields": empty_fields[:5]
            })
            feedback.suggestions.append(f"Found {len(empty_fields)} empty fields that need values")
        
        # Check field patterns
        invalid_values = self._validate_field_values(result)
        if invalid_values:
            feedback.suspicious_values = invalid_values
            feedback.confidence *= 0.9
            feedback.issues.append({
                "type": "invalid_values",
                "count": len(invalid_values),
                "examples": list(invalid_values.items())[:3]
            })
            feedback.suggestions.append("Some field values don't match expected patterns")
        
        # Check structure
        structure_score = self._validate_structure(result)
        feedback.confidence *= structure_score
        
        if structure_score < 0.8:
            feedback.issues.append({
                "type": "structure",
                "score": structure_score
            })
            feedback.suggestions.append("Document structure needs improvement")
        
        # Determine overall result
        if feedback.confidence >= 0.9:
            feedback.result = ValidationResult.VALID
        elif feedback.confidence >= 0.7:
            feedback.result = ValidationResult.NEEDS_IMPROVEMENT
        else:
            feedback.result = ValidationResult.INVALID
        
        # Log results
        self.log(f"Validation result: {feedback.result.value} (confidence: {feedback.confidence:.2f})")
        for suggestion in feedback.suggestions:
            self.log(f"💡 {suggestion}", "warning")
        
        return feedback
    
    def _find_empty_fields(self, result: FormExtractionResult) -> List[str]:
        """Find fields without values"""
        empty_fields = []
        
        for part in result.parts.values():
            for field in part.get_all_fields_flat():
                if not field.value and field.field_type != FieldType.CHECKBOX:
                    empty_fields.append(field.key)
        
        return empty_fields
    
    def _validate_field_values(self, result: FormExtractionResult) -> Dict[str, str]:
        """Validate field values against patterns"""
        invalid_values = {}
        
        patterns = self.knowledge_base.validation_rules
        
        for part in result.parts.values():
            for field in part.get_all_fields_flat():
                if field.value:
                    # Check against known patterns
                    for pattern_name, rule in patterns.items():
                        if pattern_name.lower() in field.label.lower():
                            if not re.match(rule['pattern'], field.value):
                                invalid_values[field.key] = f"Expected {rule['description']}"
        
        return invalid_values
    
    def _validate_structure(self, result: FormExtractionResult) -> float:
        """Validate document structure"""
        score = 1.0
        
        if not result.parts:
            return 0.0
        
        # Check field count
        if result.total_fields < 20:
            score *= 0.7
        elif result.total_fields < 40:
            score *= 0.85
        
        # Check part sequence
        part_numbers = sorted(result.parts.keys())
        expected = list(range(1, max(part_numbers) + 1))
        if part_numbers != expected:
            score *= 0.9
        
        return score
    
    def log(self, message: str, level: str = "info"):
        """Log message"""
        if hasattr(st, 'session_state') and 'agent_container' in st.session_state:
            with st.session_state.agent_container:
                icon = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌"}.get(level, "📝")
                css_class = "agent-card"
                if level == "error":
                    css_class += " agent-error"
                elif level == "success":
                    css_class += " agent-success"
                elif level == "warning":
                    css_class += " agent-active"
                
                st.markdown(
                    f'<div class="{css_class}">'
                    f'{icon} <strong>{self.name}</strong>: {message}'
                    f'</div>', 
                    unsafe_allow_html=True
                )

# ===== MAPPING AGENT =====
class MappingAgent:
    """Maps fields to database"""
    
    def __init__(self):
        self.name = "Mapping Agent"
        self.db_schema = self._init_db_schema()
    
    def _init_db_schema(self) -> Dict[str, List[str]]:
        """Initialize database schema"""
        return {
            "personal_info": ["first_name", "middle_name", "last_name", "date_of_birth", "gender", "country_of_birth"],
            "identification": ["alien_number", "uscis_number", "social_security_number", "passport_number"],
            "contact_info": ["mailing_address", "street_number", "street_name", "apt_number", "city", "state", "zip_code", "country", "phone_number", "email_address"],
            "immigration_info": ["current_status", "last_entry_date", "visa_type", "priority_date"],
            "attorney_info": ["attorney_name", "attorney_bar_number", "law_firm_name"],
            "family_info": ["spouse_name", "spouse_alien_number", "children_count"],
            "employment_info": ["employer_name", "occupation", "employment_start_date"]
        }
    
    def get_all_db_fields(self) -> List[str]:
        """Get all database fields"""
        fields = []
        for category, field_list in self.db_schema.items():
            for field in field_list:
                fields.append(f"{category}.{field}")
        return sorted(fields)
    
    def execute(self, result: FormExtractionResult, manual_mappings: Dict[str, str] = None) -> FormExtractionResult:
        """Execute mapping"""
        self.log("🔗 Starting field mapping...")
        
        # Apply manual mappings first
        if manual_mappings:
            for field_key, target in manual_mappings.items():
                result.update_mapping(field_key, target)
        
        # Auto-map remaining fields
        unmapped_count = 0
        auto_mapped_count = 0
        
        for part in result.parts.values():
            for field in part.get_all_fields_flat():
                if field.key not in result.field_mappings and not field.in_questionnaire:
                    suggestions = self._suggest_mapping(field)
                    if suggestions:
                        field.suggested_mappings = suggestions
                        field.mapping_status = MappingStatus.SUGGESTED
                        
                        # Auto-map high confidence
                        if suggestions[0][1] >= 0.85:
                            result.field_mappings[field.key] = suggestions[0][0]
                            field.mapped_to = suggestions[0][0]
                            field.mapping_status = MappingStatus.MAPPED
                            auto_mapped_count += 1
                    else:
                        unmapped_count += 1
        
        self.log(f"✅ Mapping complete: {len(result.field_mappings)} mapped ({auto_mapped_count} auto-mapped)", "success")
        
        return result
    
    def _suggest_mapping(self, field: FieldNode) -> List[Tuple[str, float]]:
        """Suggest mappings for field"""
        suggestions = []
        label_lower = field.label.lower()
        
        patterns = {
            r'family.*name|last.*name|surname': 'personal_info.last_name',
            r'given.*name|first.*name': 'personal_info.first_name',
            r'middle.*name': 'personal_info.middle_name',
            r'date.*birth|birth.*date|dob': 'personal_info.date_of_birth',
            r'a[\-\s]?number|alien.*number': 'identification.alien_number',
            r'uscis.*number|uscis.*account': 'identification.uscis_number',
            r'social.*security|ssn': 'identification.social_security_number',
            r'street.*number.*name|address.*line.*1': 'contact_info.street_number',
            r'apt|apartment|suite|unit': 'contact_info.apt_number',
            r'city|town': 'contact_info.city',
            r'state|province': 'contact_info.state',
            r'zip.*code|postal.*code': 'contact_info.zip_code',
            r'country': 'contact_info.country',
            r'email.*address|e\-mail': 'contact_info.email_address',
            r'phone.*number|telephone': 'contact_info.phone_number',
        }
        
        for pattern, db_field in patterns.items():
            if re.search(pattern, label_lower):
                confidence = 0.8
                if field.field_type.value in db_field:
                    confidence += 0.1
                suggestions.append((db_field, confidence))
        
        return sorted(suggestions, key=lambda x: x[1], reverse=True)[:3]
    
    def log(self, message: str, level: str = "info"):
        """Log message"""
        if hasattr(st, 'session_state') and 'agent_container' in st.session_state:
            with st.session_state.agent_container:
                icon = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌"}.get(level, "📝")
                st.markdown(f'{icon} **{self.name}**: {message}')

# ===== ITERATIVE COORDINATOR =====
class IterativeCoordinator:
    """Coordinates iterative extraction and validation"""
    
    def __init__(self):
        self.name = "Iterative Coordinator"
        self.extractor = EnhancedExtractionAgent()
        self.validator = EnhancedValidationAgent()
        self.mapper = MappingAgent()
    
    def process_iteratively(self, pdf_file, max_iterations: int = 3, 
                          manual_mappings: Dict[str, str] = None) -> FormExtractionResult:
        """Process form with iterative refinement"""
        self.log("🚀 Starting iterative form processing")
        
        context = ExtractionContext(max_iterations=max_iterations)
        result = None
        
        start_time = time.time()
        
        while context.should_continue():
            context.iteration += 1
            self.log(f"📍 Iteration {context.iteration}/{max_iterations}")
            
            # Get extraction strategy
            strategy = context.get_next_strategy()
            context.strategies_tried.append(strategy)
            
            # Extract with current strategy
            previous_feedback = context.feedback_history[-1] if context.feedback_history else None
            result = self.extractor.extract_with_strategy(
                pdf_file, strategy, result, previous_feedback
            )
            
            # Validate extraction
            feedback = self.validator.validate_iteratively(result, context)
            context.feedback_history.append(feedback)
            
            # Check if we're done
            if feedback.result == ValidationResult.VALID:
                self.log(f"✅ Extraction validated successfully after {context.iteration} iterations!", "success")
                break
            
            # Log improvements needed
            if feedback.result == ValidationResult.NEEDS_IMPROVEMENT:
                self.log(f"🔄 Extraction needs improvement (confidence: {feedback.confidence:.2f})", "warning")
            else:
                self.log(f"❌ Extraction invalid, trying different strategy", "error")
        
        # Apply mapping
        if result:
            result = self.mapper.execute(result, manual_mappings)
            result.extraction_context = context
            result.extraction_time = time.time() - start_time
            result.confidence_score = context.feedback_history[-1].confidence if context.feedback_history else 0.0
            
            self.log(f"📊 Final result: {result.total_fields} fields extracted with {result.confidence_score:.2f} confidence")
        
        return result
    
    def log(self, message: str, level: str = "info"):
        """Log message"""
        if hasattr(st, 'session_state') and 'agent_container' in st.session_state:
            with st.session_state.agent_container:
                icon = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌"}.get(level, "📝")
                css_class = "agent-card"
                if level == "error":
                    css_class += " agent-error"
                elif level == "success":
                    css_class += " agent-success"
                else:
                    css_class += " agent-active"
                
                st.markdown(
                    f'<div class="{css_class}">'
                    f'{icon} <strong>{self.name}</strong>: {message}'
                    f'</div>', 
                    unsafe_allow_html=True
                )

# ===== UI FUNCTIONS =====
def display_iterative_results(result: FormExtractionResult):
    """Display results with iteration details"""
    if not result or not result.extraction_context:
        return
    
    # Show extraction summary
    st.markdown("### 📊 Extraction Process Summary")
    
    summary = result.get_extraction_summary()
    
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Iterations", summary.get("iterations", 0))
    with col2:
        st.metric("Strategies", len(summary.get("strategies_used", [])))
    with col3:
        st.metric("Confidence", f"{summary.get('confidence_score', 0):.0%}")
    with col4:
        st.metric("Empty Fields", summary.get("empty_fields", 0))
    with col5:
        st.metric("High Conf Fields", summary.get("high_confidence_fields", 0))
    
    # Show iteration history
    with st.expander("📈 View Iteration History"):
        for i, feedback in enumerate(result.extraction_context.feedback_history):
            col1, col2, col3 = st.columns([1, 2, 3])
            
            with col1:
                st.markdown(f"**Iteration {i+1}**")
            
            with col2:
                result_color = {
                    ValidationResult.VALID: "green",
                    ValidationResult.NEEDS_IMPROVEMENT: "orange",
                    ValidationResult.INVALID: "red"
                }.get(feedback.result, "gray")
                
                st.markdown(f"<span style='color:{result_color}'>**{feedback.result.value}**</span>", 
                          unsafe_allow_html=True)
                st.write(f"Confidence: {feedback.confidence:.0%}")
            
            with col3:
                if feedback.issues:
                    st.write("Issues found:")
                    for issue in feedback.issues:
                        st.write(f"• {issue['type']}: {issue.get('count', 'N/A')}")
            
            if i < len(result.extraction_context.feedback_history) - 1:
                st.markdown("---")

def display_form_parts(result: FormExtractionResult):
    """Display form parts with enhanced field information"""
    if not result:
        st.info("No extraction results available")
        return
    
    # Display iteration summary if available
    if result.extraction_context:
        display_iterative_results(result)
    
    # Field filters
    st.markdown("### 🔍 Field Filters")
    col1, col2, col3 = st.columns(3)
    with col1:
        filter_unmapped = st.checkbox("Show only unmapped fields", value=False)
    with col2:
        filter_empty = st.checkbox("Show only empty fields", value=False)
    with col3:
        filter_type = st.selectbox("Filter by type", ["All"] + [t.value for t in FieldType])
    
    # Display parts
    st.markdown("### 📋 Extracted Fields by Part")
    
    for part_num in sorted(result.parts.keys()):
        part = result.parts[part_num]
        
        # Count statistics
        all_fields = part.get_all_fields_flat()
        mapped_count = sum(1 for f in all_fields if f.mapped_to)
        questionnaire_count = sum(1 for f in all_fields if f.in_questionnaire)
        empty_count = sum(1 for f in all_fields if not f.value)
        high_conf_count = sum(1 for f in all_fields if f.extraction_confidence > 0.8)
        
        # Part header
        st.markdown(
            f'<div class="part-header">'
            f'Part {part_num}: {part.part_title}<br/>'
            f'<small>Total: {len(all_fields)} | Mapped: {mapped_count} | '
            f'Empty: {empty_count} | High Confidence: {high_conf_count}</small>'
            f'</div>',
            unsafe_allow_html=True
        )
        
        # Display fields
        with st.expander(f"View Part {part_num} Fields", expanded=(part_num == 1)):
            for field in part.root_fields:
                should_display = True
                
                # Apply filters
                if filter_unmapped and field.mapped_to:
                    should_display = False
                if filter_empty and field.value:
                    should_display = False
                if filter_type != "All" and field.field_type.value != filter_type:
                    should_display = False
                
                if should_display:
                    display_field_with_controls(field, 0, filter_unmapped, filter_empty, filter_type)

def display_field_with_controls(field: FieldNode, level: int = 0, 
                               filter_unmapped: bool = False, 
                               filter_empty: bool = False,
                               filter_type: str = "All"):
    """Display field with controls"""
    indent = "  " * level
    
    # Apply filtering to children
    display_children = []
    for child in field.children:
        should_display = True
        if filter_unmapped and child.mapped_to:
            should_display = False
        if filter_empty and child.value:
            should_display = False
        if filter_type != "All" and child.field_type.value != filter_type:
            should_display = False
        if should_display:
            display_children.append(child)
    
    # Field display
    with st.container():
        st.markdown(f'<div class="field-row">', unsafe_allow_html=True)
        cols = st.columns([3, 2, 3, 1, 1])
        
        with cols[0]:
            # Field label with confidence indicator
            conf_class = "confidence-high" if field.extraction_confidence > 0.8 else \
                        "confidence-medium" if field.extraction_confidence > 0.5 else \
                        "confidence-low"
            
            label_html = f"{indent}<strong>{field.item_number}.</strong> {field.label}"
            if field.extraction_confidence > 0:
                label_html += f' <span class="{conf_class}">({field.extraction_confidence:.0%})</span>'
            
            st.markdown(label_html, unsafe_allow_html=True)
            
            # Display checkbox options
            if field.checkbox_options:
                opt_html = ""
                for opt in field.checkbox_options:
                    style = "background:#4caf50;color:white;" if opt.is_selected else ""
                    opt_html += f'<span style="padding:2px 8px;margin:2px;border:1px solid #ddd;border-radius:4px;{style}">{opt.text}</span>'
                st.markdown(opt_html, unsafe_allow_html=True)
        
        with cols[1]:
            # Value input
            value_key = f"value_{field.key}"
            if field.field_type == FieldType.DATE:
                field.value = st.text_input("", value=field.value or "", key=value_key, label_visibility="collapsed")
            else:
                field.value = st.text_input("", value=field.value or "", key=value_key, label_visibility="collapsed")
        
        with cols[2]:
            # Mapping dropdown
            agent = MappingAgent()
            db_fields = ["-- Unmapped --", "Move to Questionnaire"] + agent.get_all_db_fields()
            
            # Determine current selection
            if field.in_questionnaire:
                current_idx = 1
            elif field.mapped_to:
                try:
                    current_idx = db_fields.index(field.mapped_to)
                except ValueError:
                    current_idx = 0
            else:
                current_idx = 0
            
            mapping_key = f"map_{field.key}"
            selected = st.selectbox(
                "", 
                options=db_fields, 
                index=current_idx,
                key=mapping_key, 
                label_visibility="collapsed"
            )
            
            # Handle mapping changes
            if selected != db_fields[current_idx]:
                if 'extraction_result' in st.session_state:
                    if selected == "Move to Questionnaire":
                        st.session_state.extraction_result.move_to_questionnaire(field.key)
                    elif selected != "-- Unmapped --":
                        st.session_state.extraction_result.update_mapping(field.key, selected)
                    
                    if 'manual_mappings' not in st.session_state:
                        st.session_state.manual_mappings = {}
                    
                    if selected == "Move to Questionnaire":
                        st.session_state.manual_mappings[field.key] = "questionnaire"
                    elif selected != "-- Unmapped --":
                        st.session_state.manual_mappings[field.key] = selected
                    
                    st.rerun()
        
        with cols[3]:
            # Field type
            type_icon = {
                FieldType.TEXT: "📝",
                FieldType.DATE: "📅",
                FieldType.NUMBER: "🔢",
                FieldType.CHECKBOX: "☑️",
                FieldType.EMAIL: "📧",
                FieldType.PHONE: "📞",
                FieldType.ADDRESS: "📍",
                FieldType.NAME: "👤",
                FieldType.SIGNATURE: "✍️"
            }.get(field.field_type, "❓")
            st.markdown(f"{type_icon} {field.field_type.value}")
        
        with cols[4]:
            # Extraction method
            if field.extraction_method:
                method_icon = {
                    "basic": "🔤",
                    "enhanced_ocr": "🔍",
                    "pattern_matching": "🎯",
                    "layout_based": "📐",
                    "context_aware": "🧠"
                }.get(field.extraction_method, "❓")
                st.markdown(f"{method_icon}", help=field.extraction_method)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Display children recursively
    for child in display_children:
        display_field_with_controls(child, level + 1, filter_unmapped, filter_empty, filter_type)

def generate_sql_script(result: FormExtractionResult) -> str:
    """Generate SQL insert script"""
    sql_lines = []
    
    sql_lines.append("-- USCIS Form Data Export")
    sql_lines.append(f"-- Form: {result.form_number} - {result.form_title}")
    sql_lines.append(f"-- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    sql_lines.append(f"-- Extraction Confidence: {result.confidence_score:.2%}")
    if result.extraction_context:
        sql_lines.append(f"-- Iterations: {result.extraction_context.iteration}")
    sql_lines.append("")
    
    # Create table
    sql_lines.append("CREATE TABLE IF NOT EXISTS form_fields (")
    sql_lines.append("    id INT AUTO_INCREMENT PRIMARY KEY,")
    sql_lines.append("    form_number VARCHAR(50),")
    sql_lines.append("    item_number VARCHAR(20),")
    sql_lines.append("    label VARCHAR(500),")
    sql_lines.append("    value TEXT,")
    sql_lines.append("    field_type VARCHAR(50),")
    sql_lines.append("    part_number INT,")
    sql_lines.append("    page_number INT,")
    sql_lines.append("    extraction_confidence DECIMAL(3,2),")
    sql_lines.append("    extraction_method VARCHAR(50),")
    sql_lines.append("    mapped_to VARCHAR(100),")
    sql_lines.append("    in_questionnaire BOOLEAN,")
    sql_lines.append("    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    sql_lines.append(");")
    sql_lines.append("")
    
    # Insert data
    sql_lines.append("-- Insert form fields")
    for part in result.parts.values():
        sql_lines.append(f"-- Part {part.part_number}: {part.part_title}")
        for field in part.get_all_fields_flat():
            value = field.value.replace("'", "''") if field.value else ''
            label = field.label.replace("'", "''")
            mapped_to = field.mapped_to or 'NULL'
            in_questionnaire = 'TRUE' if field.in_questionnaire else 'FALSE'
            
            mapped_value = 'NULL' if mapped_to == 'NULL' else f"'{mapped_to}'"
            
            sql_lines.append(
                f"INSERT INTO form_fields "
                f"(form_number, item_number, label, value, field_type, part_number, page_number, "
                f"extraction_confidence, extraction_method, mapped_to, in_questionnaire) "
                f"VALUES ('{result.form_number}', '{field.item_number}', '{label}', '{value}', "
                f"'{field.field_type.value}', {field.part_number}, {field.page}, "
                f"{field.extraction_confidence:.2f}, '{field.extraction_method}', "
                f"{mapped_value}, {in_questionnaire});"
            )
    
    return "\n".join(sql_lines)

def export_to_excel(result: FormExtractionResult) -> io.BytesIO:
    """Export to Excel with multiple sheets"""
    output = io.BytesIO()
    
    if XLSXWRITER_AVAILABLE:
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            # Summary sheet
            summary_data = {
                'Metric': ['Form Number', 'Form Title', 'Total Parts', 'Total Fields', 
                          'Mapped Fields', 'Questionnaire Fields', 'Confidence Score',
                          'Empty Fields', 'High Confidence Fields'],
                'Value': [result.form_number, result.form_title, len(result.parts), 
                         result.total_fields, len(result.field_mappings), 
                         len(result.questionnaire_fields), f"{result.confidence_score:.2%}",
                         result.get_extraction_summary().get('empty_fields', 0),
                         result.get_extraction_summary().get('high_confidence_fields', 0)]
            }
            
            if result.extraction_context:
                summary_data['Metric'].extend(['Iterations', 'Strategies Used'])
                summary_data['Value'].extend([
                    result.extraction_context.iteration,
                    ', '.join(s.value for s in result.extraction_context.strategies_tried)
                ])
            
            pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)
            
            # All fields sheet
            all_fields_data = []
            for part in result.parts.values():
                for field in part.get_all_fields_flat():
                    all_fields_data.append({
                        'Part': part.part_number,
                        'Part Title': part.part_title,
                        'Item Number': field.item_number,
                        'Label': field.label,
                        'Value': field.value,
                        'Type': field.field_type.value,
                        'Page': field.page,
                        'Confidence': f"{field.extraction_confidence:.2f}",
                        'Method': field.extraction_method,
                        'Mapped To': field.mapped_to or '',
                        'In Questionnaire': 'Yes' if field.in_questionnaire else 'No'
                    })
            
            pd.DataFrame(all_fields_data).to_excel(writer, sheet_name='All Fields', index=False)
            
            # High confidence fields
            high_conf_data = [row for row in all_fields_data if float(row['Confidence']) > 0.8]
            if high_conf_data:
                pd.DataFrame(high_conf_data).to_excel(writer, sheet_name='High Confidence', index=False)
            
            # Low confidence fields
            low_conf_data = [row for row in all_fields_data if float(row['Confidence']) < 0.5]
            if low_conf_data:
                pd.DataFrame(low_conf_data).to_excel(writer, sheet_name='Needs Review', index=False)
            
            # Mapped fields
            mapped_data = [row for row in all_fields_data if row['Mapped To']]
            if mapped_data:
                pd.DataFrame(mapped_data).to_excel(writer, sheet_name='Mapped Fields', index=False)
            
            # Questionnaire fields
            quest_data = [row for row in all_fields_data if row['In Questionnaire'] == 'Yes']
            if quest_data:
                pd.DataFrame(quest_data).to_excel(writer, sheet_name='Questionnaire', index=False)
    
    output.seek(0)
    return output

# ===== MAIN APPLICATION =====
def main():
    st.markdown(
        '<div class="main-header">'
        '<h1>🤖 Enhanced Iterative USCIS Form Reader</h1>'
        '<p>Extract, validate, and map form fields with intelligent iterative processing</p>'
        '</div>', 
        unsafe_allow_html=True
    )
    
    # Initialize session state
    if 'extraction_result' not in st.session_state:
        st.session_state.extraction_result = None
    if 'manual_mappings' not in st.session_state:
        st.session_state.manual_mappings = {}
    
    # Sidebar
    with st.sidebar:
        st.markdown("## ⚙️ Configuration")
        max_iterations = st.slider("Max Iterations", 1, 5, 3, 
                                 help="Maximum attempts to improve extraction")
        show_agent_logs = st.checkbox("Show Agent Activity", value=True)
        
        st.markdown("---")
        st.markdown("## 🎯 Features")
        st.markdown("""
        ✅ **Iterative extraction** - keeps improving  
        ✅ **Multiple strategies** - adapts approach  
        ✅ **Value extraction** - finds field values  
        ✅ **Confidence tracking** - shows reliability  
        ✅ **Smart validation** - detailed feedback  
        ✅ **Database mapping** - manual control  
        ✅ **Multiple exports** - SQL, Excel, JSON
        """)
        
        st.markdown("---")
        st.markdown("## 🎯 Quick Actions")
        if st.button("🔄 Reset All Mappings"):
            st.session_state.manual_mappings = {}
            if st.session_state.extraction_result:
                st.session_state.extraction_result.field_mappings = {}
                st.session_state.extraction_result.questionnaire_fields = []
                for part in st.session_state.extraction_result.parts.values():
                    for field in part.get_all_fields_flat():
                        field.mapped_to = None
                        field.mapping_status = MappingStatus.UNMAPPED
                        field.in_questionnaire = False
            st.rerun()
    
    # Main tabs
    tabs = st.tabs(["📄 Upload", "📊 Review & Map", "💾 Export", "📋 Questionnaire"])
    
    # Upload tab
    with tabs[0]:
        st.markdown("### 📄 Upload USCIS Form")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            uploaded_file = st.file_uploader(
                "Choose a PDF form",
                type=['pdf'],
                help="Upload any USCIS form (I-130, I-485, I-90, I-765, G-28, etc.)"
            )
        
        if uploaded_file:
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.success(f"✅ Uploaded: {uploaded_file.name}")
            
            with col2:
                if st.button("🚀 Process", type="primary", use_container_width=True):
                    if show_agent_logs:
                        st.markdown("### 🤖 Agent Activity")
                        agent_container = st.container()
                        st.session_state.agent_container = agent_container
                    
                    with st.spinner("Processing form iteratively..."):
                        coordinator = IterativeCoordinator()
                        result = coordinator.process_iteratively(
                            uploaded_file, 
                            max_iterations,
                            st.session_state.manual_mappings
                        )
                        
                        if result:
                            st.session_state.extraction_result = result
                            st.success("✅ Processing complete!")
                            st.balloons()
                            
                            # Show quick stats
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Total Fields", result.total_fields)
                            with col2:
                                st.metric("Confidence", f"{result.confidence_score:.0%}")
                            with col3:
                                st.metric("Time", f"{result.extraction_time:.1f}s")
                            
                            st.info("Go to the 'Review & Map' tab to see results and assign mappings.")
    
    # Review tab
    with tabs[1]:
        st.markdown("### 📊 Review Extracted Fields & Assign Mappings")
        
        if st.session_state.extraction_result:
            st.info("💡 Use dropdowns to assign database fields or move to questionnaire. Confidence scores show extraction reliability.")
            display_form_parts(st.session_state.extraction_result)
        else:
            st.info("No results. Please process a form first in the Upload tab.")
    
    # Export tab
    with tabs[2]:
        st.markdown("### 💾 Export Results")
        
        if st.session_state.extraction_result:
            result = st.session_state.extraction_result
            
            # Export options
            st.markdown("#### Export Formats")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                # JSON export
                export_data = {
                    'form_info': {
                        'number': result.form_number,
                        'title': result.form_title,
                        'confidence': result.confidence_score,
                        'extraction_time': result.extraction_time,
                        'total_fields': result.total_fields
                    },
                    'extraction_summary': result.get_extraction_summary(),
                    'parts': {}
                }
                
                for part_num, part in result.parts.items():
                    export_data['parts'][f'part_{part_num}'] = {
                        'title': part.part_title,
                        'fields': [field.to_dict() for field in part.get_all_fields_flat()]
                    }
                
                json_str = json.dumps(export_data, indent=2, default=str)
                st.download_button(
                    "📦 Download JSON",
                    json_str,
                    f"{result.form_number}_extraction.json",
                    mime="application/json",
                    use_container_width=True
                )
            
            with col2:
                # CSV export
                csv_data = []
                for part in result.parts.values():
                    for field in part.get_all_fields_flat():
                        csv_data.append({
                            'Part': part.part_number,
                            'Item': field.item_number,
                            'Label': field.label,
                            'Value': field.value,
                            'Type': field.field_type.value,
                            'Confidence': field.extraction_confidence,
                            'Method': field.extraction_method,
                            'Mapped To': field.mapped_to or '',
                            'In Questionnaire': field.in_questionnaire
                        })
                
                if csv_data:
                    df = pd.DataFrame(csv_data)
                    csv = df.to_csv(index=False)
                    st.download_button(
                        "📊 Download CSV",
                        csv,
                        f"{result.form_number}_extraction.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
            
            with col3:
                # SQL export
                sql = generate_sql_script(result)
                st.download_button(
                    "🗄️ Download SQL",
                    sql,
                    f"{result.form_number}_data.sql",
                    mime="text/plain",
                    use_container_width=True
                )
            
            with col4:
                # Excel export
                if XLSXWRITER_AVAILABLE:
                    excel_data = export_to_excel(result)
                    st.download_button(
                        "📑 Download Excel",
                        excel_data,
                        f"{result.form_number}_extraction.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                else:
                    st.info("Install xlsxwriter for Excel export")
            
            # Preview
            st.markdown("#### Preview Extracted Data")
            preview_type = st.radio("Preview format", ["Summary", "All Fields", "Low Confidence Fields"])
            
            if preview_type == "Summary":
                st.json(result.get_extraction_summary())
            elif preview_type == "All Fields":
                with st.expander("View All Fields"):
                    for part in result.parts.values():
                        st.markdown(f"**Part {part.part_number}: {part.part_title}**")
                        for field in part.get_all_fields_flat():
                            st.write(f"- {field.item_number}. {field.label}: {field.value or '(empty)'} "
                                   f"[{field.extraction_confidence:.0%}]")
            else:
                low_conf_fields = []
                for part in result.parts.values():
                    for field in part.get_all_fields_flat():
                        if field.extraction_confidence < 0.5:
                            low_conf_fields.append(field)
                
                if low_conf_fields:
                    st.warning(f"Found {len(low_conf_fields)} fields with low confidence")
                    for field in low_conf_fields:
                        st.write(f"- {field.item_number}. {field.label}: {field.value or '(empty)'} "
                               f"[{field.extraction_confidence:.0%}] - {field.extraction_method}")
                else:
                    st.success("No low confidence fields found!")
        else:
            st.info("No results to export. Please process a form first.")
    
    # Questionnaire tab
    with tabs[3]:
        st.markdown("### 📋 Questionnaire Fields")
        
        if st.session_state.extraction_result:
            result = st.session_state.extraction_result
            questionnaire_fields = []
            
            for part in result.parts.values():
                for field in part.get_all_fields_flat():
                    if field.in_questionnaire:
                        questionnaire_fields.append(field)
            
            if questionnaire_fields:
                st.info(f"Found {len(questionnaire_fields)} fields marked for questionnaire")
                
                # Display questionnaire fields
                for i, field in enumerate(questionnaire_fields):
                    st.markdown(f"**{i+1}. {field.label}** (Item {field.item_number}, Part {field.part_number})")
                    
                    # Show extraction confidence
                    conf_color = "green" if field.extraction_confidence > 0.8 else "orange" if field.extraction_confidence > 0.5 else "red"
                    st.markdown(f"<small>Extraction confidence: <span style='color:{conf_color}'>{field.extraction_confidence:.0%}</span></small>", 
                              unsafe_allow_html=True)
                    
                    answer_key = f"quest_{field.key}"
                    field.value = st.text_area(
                        "Answer:", 
                        value=field.value or "", 
                        key=answer_key,
                        height=100
                    )
                    st.markdown("---")
                
                # Export questionnaire
                if st.button("💾 Export Questionnaire Responses"):
                    quest_data = []
                    for field in questionnaire_fields:
                        quest_data.append({
                            'Question Number': field.item_number,
                            'Question': field.label,
                            'Answer': field.value,
                            'Part': field.part_number,
                            'Page': field.page,
                            'Confidence': field.extraction_confidence
                        })
                    
                    df = pd.DataFrame(quest_data)
                    csv = df.to_csv(index=False)
                    st.download_button(
                        "📋 Download Questionnaire CSV",
                        csv,
                        f"{result.form_number}_questionnaire.csv",
                        mime="text/csv"
                    )
            else:
                st.info("No fields assigned to questionnaire. Use the 'Review & Map' tab to move fields to the questionnaire.")
        else:
            st.info("No form processed yet.")

if __name__ == "__main__":
    if not PYMUPDF_AVAILABLE:
        st.error("❌ PyMuPDF is required but not installed!")
        st.code("pip install PyMuPDF")
        st.stop()
    
    main()


