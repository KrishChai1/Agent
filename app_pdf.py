#!/usr/bin/env python3
"""
Enhanced Agentic USCIS Form Reader - Final Working Version
Complete extraction with all parts and fields (1, 1a, 1b, 1c, etc.)
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
    page_title="Enhanced Agentic USCIS Form Reader",
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
    
    .kb-indicator {
        background: linear-gradient(45deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        display: inline-block;
        font-weight: bold;
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

class MappingStatus(Enum):
    MAPPED = "mapped"
    UNMAPPED = "unmapped"
    MANUAL = "manual"
    SUGGESTED = "suggested"
    QUESTIONNAIRE = "questionnaire"

class AgentRole(Enum):
    EXTRACTOR = "extractor"
    VALIDATOR = "validator"
    MAPPER = "mapper"
    COORDINATOR = "coordinator"

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
            },
            "I-90": {
                "title": "Application to Replace Permanent Resident Card",
                "parts": {
                    1: "Information About You",
                    2: "Application Type",
                    3: "Processing Information",
                    4: "Accommodations for Individuals With Disabilities",
                    5: "Applicant's Statement",
                    6: "Interpreter's Contact Information",
                    7: "Contact Information, Declaration, and Signature"
                },
                "expected_fields": 60,
                "page_count": 10
            },
            "I-765": {
                "title": "Application for Employment Authorization",
                "parts": {
                    1: "Reason for Applying",
                    2: "Information About You",
                    3: "Applicant's Statement",
                    4: "Interpreter's Contact Information",
                    5: "Contact Information, Declaration, and Signature"
                },
                "expected_fields": 45,
                "page_count": 7
            }
        }
    
    def _init_field_patterns(self) -> Dict[str, Dict]:
        """Initialize field extraction patterns"""
        return {
            "name_fields": {
                "patterns": [
                    r"Family Name \(Last Name\)",
                    r"Given Name \(First Name\)",
                    r"Middle Name",
                    r"Full Name"
                ],
                "type": FieldType.NAME
            },
            "date_fields": {
                "patterns": [
                    r"Date of Birth",
                    r"Date of Filing",
                    r"Expiration Date",
                    r"Marriage Date"
                ],
                "type": FieldType.DATE
            },
            "number_fields": {
                "patterns": [
                    r"A-Number",
                    r"Alien Registration Number",
                    r"USCIS Online Account Number",
                    r"Social Security Number",
                    r"Receipt Number"
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
            },
            "zip_code": {
                "pattern": r"^\d{5}(-\d{4})?$",
                "description": "XXXXX or XXXXX-XXXX"
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

# ===== DATA CLASSES =====
@dataclass
class CheckboxOption:
    """Represents a checkbox option"""
    text: str
    is_selected: bool = False
    confidence: float = 0.0

@dataclass
class FieldNode:
    """Field node with hierarchy support"""
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
    
    # Unique identification
    key: str = ""
    content_hash: str = ""
    
    # Extraction metadata
    confidence: ExtractionConfidence = ExtractionConfidence.LOW
    
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

# ===== BASE AGENT CLASS =====
class BaseAgent(ABC):
    """Base agent with logging"""
    
    def __init__(self, name: str, role: AgentRole):
        self.name = name
        self.role = role
        self.status = "idle"
        self.logs = []
        self.knowledge_base = FormKnowledgeBase()
    
    @abstractmethod
    def execute(self, *args, **kwargs) -> Any:
        pass
    
    def log(self, message: str, level: str = "info"):
        """Log message"""
        entry = {
            "timestamp": datetime.now(),
            "agent": self.name,
            "message": message,
            "level": level
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
                    "error": "❌"
                }.get(level, "📝")
                
                st.markdown(
                    f'<div class="{css_class}">'
                    f'{icon} <strong>{self.name}</strong>: {message}'
                    f'</div>', 
                    unsafe_allow_html=True
                )

# ===== EXTRACTION AGENT =====
class ExtractionAgent(BaseAgent):
    """Extracts form fields with proper hierarchy"""
    
    def __init__(self):
        super().__init__("Extraction Agent", AgentRole.EXTRACTOR)
        self.doc = None
        
    def execute(self, pdf_file) -> FormExtractionResult:
        """Execute extraction"""
        self.status = "active"
        self.log("🚀 Starting form extraction...")
        
        try:
            # Open PDF
            if hasattr(pdf_file, 'read'):
                pdf_file.seek(0)
                pdf_bytes = pdf_file.read()
            else:
                pdf_bytes = pdf_file
            
            self.doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
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
            
            self.log(f"✅ Extraction complete: {result.total_fields} fields in {len(result.parts)} parts", "success")
            
            return result
            
        except Exception as e:
            self.log(f"❌ Extraction failed: {str(e)}", "error")
            raise
        finally:
            if self.doc:
                self.doc.close()
    
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
        
        # Sort by position
        blocks.sort(key=lambda b: (b['page'], b['y_pos'], b['x_pos']))
        
        return blocks
    
    def _find_parts(self, blocks: List[Dict]) -> Dict[int, Dict]:
        """Find all parts in document"""
        parts_info = {}
        
        # Part patterns
        part_patterns = [
            r'^Part\s+(\d+)[.:]\s*(.*)$',
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
            
            self.log(f"📝 Extracting fields for Part {part_num}")
            
            i = start
            while i <= end:
                block = blocks[i]
                
                # Skip part headers
                if re.match(r'^Part\s+\d+', block['text'], re.IGNORECASE):
                    i += 1
                    continue
                
                # Try to extract field
                field = self._extract_field(blocks, i, end)
                if field:
                    part.add_field(field)
                    i += 1
                else:
                    i += 1
            
            result.parts[part_num] = part
            self.log(f"✅ Part {part_num}: {len(part.get_all_fields_flat())} fields")
    
    def _extract_field(self, blocks: List[Dict], idx: int, end_idx: int) -> Optional[FieldNode]:
        """Extract field from block"""
        if idx >= len(blocks):
            return None
        
        block = blocks[idx]
        text = block['text']
        
        # Field patterns
        patterns = [
            (r'^(\d+)\.([a-z])\.(\d+)\.\s+(.+)', lambda m: (m.group(1)+m.group(2)+m.group(3), m.group(4))),
            (r'^(\d+)([a-z])(\d+)\.\s+(.+)', lambda m: (m.group(1)+m.group(2)+m.group(3), m.group(4))),
            (r'^(\d+)\.([a-z])\.\s+(.+)', lambda m: (m.group(1)+m.group(2), m.group(3))),
            (r'^(\d+)([a-z])\.\s+(.+)', lambda m: (m.group(1)+m.group(2), m.group(3))),
            (r'^(\d+)\.\s+(.+)', lambda m: (m.group(1), m.group(2))),
            (r'^\(([a-z])\)\s+(.+)', lambda m: (m.group(1), m.group(2))),
            (r'^([A-Z])\.\s+(.+)', lambda m: (m.group(1), m.group(2)))
        ]
        
        for pattern, parser in patterns:
            match = re.match(pattern, text)
            if match:
                item_number, label = parser(match)
                
                # Create field
                field = FieldNode(
                    item_number=item_number,
                    label=label.strip(),
                    page=block['page']
                )
                
                # Suggest field type
                field.field_type, conf = self.knowledge_base.suggest_field_type(label)
                if conf > 0.7:
                    field.confidence = ExtractionConfidence.HIGH
                
                # Look for checkboxes
                if field.field_type == FieldType.CHECKBOX:
                    field.checkbox_options = self._extract_checkboxes(blocks, idx + 1, end_idx)
                
                return field
        
        return None
    
    def _extract_checkboxes(self, blocks: List[Dict], start_idx: int, end_idx: int) -> List[CheckboxOption]:
        """Extract checkbox options"""
        options = []
        
        patterns = [
            (r'^[□☐]\s*(.+)', False),
            (r'^[☑☒]\s*(.+)', True),
            (r'^\[\s*\]\s*(.+)', False),
            (r'^\[X\]\s*(.+)', True)
        ]
        
        for i in range(start_idx, min(end_idx, start_idx + 10)):
            if i >= len(blocks):
                break
            
            text = blocks[i]['text']
            
            # Stop if we hit another field
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

# ===== VALIDATION AGENT =====
class ValidationAgent(BaseAgent):
    """Validates extraction results"""
    
    def __init__(self):
        super().__init__("Validation Agent", AgentRole.VALIDATOR)
    
    def execute(self, result: FormExtractionResult) -> Tuple[bool, float]:
        """Execute validation"""
        self.status = "active"
        self.log("🔍 Starting validation...")
        
        checks = []
        
        # Check field count
        field_count = result.total_fields
        expected = self.knowledge_base.get_form_info(result.form_number)
        if expected:
            expected_count = expected.get('expected_fields', 20)
            score = min(1.0, field_count / expected_count)
            checks.append(('field_count', score, f"{field_count} fields (expected ~{expected_count})"))
        else:
            score = 1.0 if field_count > 20 else field_count / 20
            checks.append(('field_count', score, f"{field_count} fields"))
        
        # Check parts
        if result.parts:
            checks.append(('parts', 1.0, f"{len(result.parts)} parts found"))
        else:
            checks.append(('parts', 0.0, "No parts found"))
        
        # Calculate overall score
        total_score = sum(score for _, score, _ in checks) / len(checks)
        is_valid = total_score >= 0.7
        
        result.confidence_score = total_score
        
        self.log(f"✅ Validation complete: {total_score:.0%} confidence", "success" if is_valid else "warning")
        
        return is_valid, total_score

# ===== MAPPING AGENT =====
class MappingAgent(BaseAgent):
    """Maps fields to database"""
    
    def __init__(self):
        super().__init__("Mapping Agent", AgentRole.MAPPER)
        self.db_schema = self._init_db_schema()
    
    def _init_db_schema(self) -> Dict[str, List[str]]:
        """Initialize database schema"""
        return {
            "personal_info": ["first_name", "middle_name", "last_name", "date_of_birth", "gender"],
            "identification": ["alien_number", "uscis_number", "social_security_number", "passport_number"],
            "contact_info": ["mailing_address", "city", "state", "zip_code", "country", "phone_number", "email_address"],
            "immigration_info": ["current_status", "last_entry_date", "visa_type", "priority_date"]
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
        self.status = "active"
        self.log("🔗 Starting field mapping...")
        
        # Apply manual mappings
        if manual_mappings:
            for field_key, target in manual_mappings.items():
                if target == "questionnaire":
                    result.move_to_questionnaire(field_key)
                else:
                    result.field_mappings[field_key] = target
                    field = result.get_field_by_key(field_key)
                    if field:
                        field.mapped_to = target
                        field.mapping_status = MappingStatus.MANUAL
        
        # Auto-map remaining fields
        unmapped_count = 0
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
                    else:
                        unmapped_count += 1
        
        self.log(f"✅ Mapping complete: {len(result.field_mappings)} mapped", "success")
        
        return result
    
    def _suggest_mapping(self, field: FieldNode) -> List[Tuple[str, float]]:
        """Suggest mappings for field"""
        suggestions = []
        label_lower = field.label.lower()
        
        # Pattern matching
        patterns = {
            r'family.*name|last.*name': 'personal_info.last_name',
            r'given.*name|first.*name': 'personal_info.first_name',
            r'middle.*name': 'personal_info.middle_name',
            r'date.*birth': 'personal_info.date_of_birth',
            r'a[\-\s]?number|alien.*number': 'identification.alien_number',
            r'city|town': 'contact_info.city',
            r'state|province': 'contact_info.state',
            r'email': 'contact_info.email_address',
            r'phone': 'contact_info.phone_number'
        }
        
        for pattern, db_field in patterns.items():
            if re.search(pattern, label_lower):
                confidence = 0.8
                if field.field_type.value in db_field:
                    confidence += 0.1
                suggestions.append((db_field, confidence))
        
        return sorted(suggestions, key=lambda x: x[1], reverse=True)[:3]

# ===== COORDINATOR =====
class Coordinator(BaseAgent):
    """Coordinates the pipeline"""
    
    def __init__(self):
        super().__init__("Master Coordinator", AgentRole.COORDINATOR)
        self.agents = {
            'extractor': ExtractionAgent(),
            'validator': ValidationAgent(),
            'mapper': MappingAgent()
        }
    
    def execute(self, pdf_file, manual_mappings: Dict[str, str] = None) -> Dict[str, Any]:
        """Execute pipeline"""
        self.status = "active"
        self.log("🚀 Starting form processing pipeline...")
        
        try:
            start_time = time.time()
            
            # Extract
            result = self.agents['extractor'].execute(pdf_file)
            
            # Validate
            is_valid, score = self.agents['validator'].execute(result)
            
            # Map
            result = self.agents['mapper'].execute(result, manual_mappings)
            
            # Prepare output
            output = self._prepare_output(result)
            
            end_time = time.time()
            result.extraction_time = end_time - start_time
            
            self.log(f"✅ Pipeline complete in {result.extraction_time:.2f}s", "success")
            
            # Store in session
            if hasattr(st, 'session_state'):
                st.session_state.extraction_result = result
                st.session_state.pipeline_output = output
            
            return output
            
        except Exception as e:
            self.log(f"❌ Pipeline failed: {str(e)}", "error")
            raise
    
    def _prepare_output(self, result: FormExtractionResult) -> Dict[str, Any]:
        """Prepare output"""
        parts_data = {}
        
        for part_num, part in result.parts.items():
            fields_data = []
            for field in part.root_fields:
                fields_data.append(self._field_to_dict_recursive(field))
            
            parts_data[f"part_{part_num}"] = {
                'number': part_num,
                'title': part.part_title,
                'fields': fields_data,
                'total_fields': len(part.get_all_fields_flat())
            }
        
        return {
            'form_info': {
                'number': result.form_number,
                'title': result.form_title,
                'total_fields': result.total_fields,
                'confidence_score': result.confidence_score,
                'extraction_time': result.extraction_time
            },
            'parts': parts_data,
            'mappings': {
                'field_mappings': result.field_mappings,
                'questionnaire_fields': result.questionnaire_fields
            },
            'statistics': {
                'total_parts': len(result.parts),
                'total_fields': result.total_fields,
                'mapped_fields': len(result.field_mappings),
                'questionnaire_fields': len(result.questionnaire_fields),
                'confidence_score': result.confidence_score
            }
        }
    
    def _field_to_dict_recursive(self, field: FieldNode) -> Dict:
        """Convert field to dict with children"""
        data = field.to_dict()
        if field.children:
            data['children'] = [self._field_to_dict_recursive(child) for child in field.children]
        return data

# ===== UI FUNCTIONS =====
def display_form_parts(result: FormExtractionResult):
    """Display form parts"""
    if not result:
        st.info("No extraction results available")
        return
    
    # Summary
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Fields", result.total_fields)
    with col2:
        st.metric("Parts", len(result.parts))
    with col3:
        st.metric("Confidence", f"{result.confidence_score:.0%}")
    with col4:
        st.metric("Mapped", len(result.field_mappings))
    
    # Display parts
    for part_num in sorted(result.parts.keys()):
        part = result.parts[part_num]
        
        st.markdown(
            f'<div class="part-header">'
            f'Part {part_num}: {part.part_title} '
            f'({len(part.get_all_fields_flat())} fields)'
            f'</div>',
            unsafe_allow_html=True
        )
        
        # Display fields
        for field in part.root_fields:
            display_field_with_controls(field, 0)

def display_field_with_controls(field: FieldNode, level: int = 0):
    """Display field with controls"""
    indent = "  " * level
    
    with st.container():
        cols = st.columns([3, 2, 3, 1])
        
        with cols[0]:
            st.markdown(f"{indent}**{field.item_number}.** {field.label}")
            
            if field.checkbox_options:
                opt_html = ""
                for opt in field.checkbox_options:
                    css_class = "checkbox-selected" if opt.is_selected else ""
                    opt_html += f'<span class="checkbox-option {css_class}">{opt.text}</span>'
                st.markdown(opt_html, unsafe_allow_html=True)
        
        with cols[1]:
            # Value input
            key = f"value_{field.key}"
            if field.field_type == FieldType.DATE:
                field.value = st.date_input("", key=key, label_visibility="collapsed")
            else:
                field.value = st.text_input("", value=field.value, key=key, label_visibility="collapsed")
        
        with cols[2]:
            # Mapping dropdown
            agent = MappingAgent()
            db_fields = ["-- Unmapped --", "Move to Questionnaire"] + agent.get_all_db_fields()
            
            current = field.mapped_to or "-- Unmapped --"
            if field.in_questionnaire:
                current = "Move to Questionnaire"
            
            mapping = st.selectbox("", options=db_fields, index=db_fields.index(current), 
                                 key=f"map_{field.key}", label_visibility="collapsed")
            
            if mapping != current:
                if mapping == "Move to Questionnaire":
                    if 'extraction_result' in st.session_state:
                        st.session_state.extraction_result.move_to_questionnaire(field.key)
                        st.rerun()
                elif mapping != "-- Unmapped --":
                    if 'manual_mappings' not in st.session_state:
                        st.session_state.manual_mappings = {}
                    st.session_state.manual_mappings[field.key] = mapping
                    st.rerun()
        
        with cols[3]:
            st.markdown(f"📝 {field.field_type.value}")
    
    # Display children
    for child in field.children:
        display_field_with_controls(child, level + 1)

def generate_sql_script(result: FormExtractionResult) -> str:
    """Generate SQL insert script"""
    sql_lines = []
    
    sql_lines.append("-- USCIS Form Data Export")
    sql_lines.append(f"-- Form: {result.form_number} - {result.form_title}")
    sql_lines.append(f"-- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    sql_lines.append("")
    
    sql_lines.append("-- Insert form fields")
    for part in result.parts.values():
        for field in part.get_all_fields_flat():
            value = field.value.replace("'", "''") if field.value else ''
            label = field.label.replace("'", "''")
            
            sql_lines.append(
                f"INSERT INTO form_fields (item_number, label, value, field_type, part_number, page_number) "
                f"VALUES ('{field.item_number}', '{label}', '{value}', "
                f"'{field.field_type.value}', {field.part_number}, {field.page});"
            )
    
    return "\n".join(sql_lines)

# ===== MAIN APPLICATION =====
def main():
    st.markdown(
        '<div class="main-header">'
        '<h1>🤖 Enhanced Agentic USCIS Form Reader</h1>'
        '<p>Extract all parts and fields from USCIS forms</p>'
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
        
        st.markdown("---")
        st.markdown("## 📊 Features")
        st.markdown("""
        ✅ All parts detected  
        ✅ All field formats (1, 1a, 1b, etc.)  
        ✅ Hierarchical structure  
        ✅ Smart validation  
        ✅ Database mapping  
        ✅ Export capabilities
        """)
    
    # Main tabs
    tabs = st.tabs(["📄 Upload", "📊 Review", "💾 Export"])
    
    # Upload tab
    with tabs[0]:
        st.markdown("### 📄 Upload USCIS Form")
        
        uploaded_file = st.file_uploader(
            "Choose a PDF form",
            type=['pdf'],
            help="Upload any USCIS form"
        )
        
        if uploaded_file:
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.success(f"✅ Uploaded: {uploaded_file.name}")
            
            with col2:
                if st.button("🚀 Process", type="primary"):
                    if show_agent_logs:
                        st.markdown("### 🤖 Agent Activity")
                        agent_container = st.container()
                        st.session_state.agent_container = agent_container
                    
                    with st.spinner("Processing..."):
                        coordinator = Coordinator()
                        output = coordinator.execute(uploaded_file, st.session_state.manual_mappings)
                        
                        if output:
                            st.success("✅ Processing complete!")
                            st.balloons()
    
    # Review tab
    with tabs[1]:
        st.markdown("### 📊 Review Extracted Fields")
        
        if st.session_state.extraction_result:
            display_form_parts(st.session_state.extraction_result)
        else:
            st.info("No results. Please process a form first.")
    
    # Export tab
    with tabs[2]:
        st.markdown("### 💾 Export Results")
        
        if st.session_state.pipeline_output:
            output = st.session_state.pipeline_output
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # JSON export
                json_str = json.dumps(output, indent=2, default=str)
                st.download_button(
                    "📦 Download JSON",
                    json_str,
                    "form_extraction.json",
                    mime="application/json"
                )
            
            with col2:
                # CSV export
                csv_data = []
                for part_key, part_data in output['parts'].items():
                    def flatten(fields):
                        for field in fields:
                            csv_data.append({
                                'Part': part_data['number'],
                                'Item': field['item_number'],
                                'Label': field['label'],
                                'Value': field['value'],
                                'Type': field['type']
                            })
                            if 'children' in field:
                                flatten(field['children'])
                    
                    flatten(part_data['fields'])
                
                if csv_data:
                    df = pd.DataFrame(csv_data)
                    csv = df.to_csv(index=False)
                    st.download_button(
                        "📊 Download CSV",
                        csv,
                        "form_extraction.csv",
                        mime="text/csv"
                    )
            
            with col3:
                # SQL export
                if st.session_state.extraction_result:
                    sql = generate_sql_script(st.session_state.extraction_result)
                    st.download_button(
                        "🗄️ Download SQL",
                        sql,
                        "form_data.sql",
                        mime="text/plain"
                    )
        else:
            st.info("No results to export.")

if __name__ == "__main__":
    if not PYMUPDF_AVAILABLE:
        st.error("❌ PyMuPDF is required but not installed!")
        st.code("pip install PyMuPDF")
        st.stop()
    
    main()
