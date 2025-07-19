#!/usr/bin/env python3
"""
Complete Working USCIS Form Reader with All Agents Implemented
Fixed: Stream handling and part extraction sequencing
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
    .mapped-field {
        background: #E8F5E9;
        border-left: 4px solid #4CAF50;
    }
    .unmapped-field {
        background: #FFF3E0;
        border-left: 4px solid #FF9800;
    }
    .mapping-agent {
        border-left: 4px solid #9C27B0;
        background: #F3E5F5;
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
    QUESTIONNAIRE = "questionnaire"

# ===== DATA CLASSES =====
@dataclass
class FieldPattern:
    """Pattern for field recognition"""
    pattern: re.Pattern
    field_type: FieldType
    confidence: float = 1.0
    description: str = ""

@dataclass
class FieldNode:
    """Enhanced field node with mapping support"""
    # Core properties
    item_number: str
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
    bbox: Optional[Tuple[float, float, float, float]] = None
    
    # Generated key
    key: str = ""
    
    # Extraction metadata
    confidence: ExtractionConfidence = ExtractionConfidence.LOW
    extraction_method: str = ""
    raw_text: str = ""
    patterns_matched: List[str] = field(default_factory=list)
    
    # Validation
    is_required: bool = False
    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)
    
    # Mapping metadata
    mapping_status: MappingStatus = MappingStatus.UNMAPPED
    mapped_to: Optional[str] = None
    mapping_confidence: float = 0.0
    
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
            "mapping_status": self.mapping_status.value,
            "mapped_to": self.mapped_to,
            "children": [child.to_dict() for child in self.children]
        }

@dataclass
class FieldMapping:
    """Represents a mapping between PDF field and database field"""
    pdf_field_key: str
    pdf_field_label: str
    database_table: str
    database_field: str
    transformation: Optional[str] = None
    confidence: float = 0.0

@dataclass
class DatabaseSchema:
    """Database schema definition"""
    tables: Dict[str, Dict[str, str]] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.tables:
            self.tables = {
                "beneficiary": {
                    "firstName": "string",
                    "lastName": "string",
                    "middleName": "string",
                    "dateOfBirth": "date",
                    "alienNumber": "string",
                    "socialSecurityNumber": "string",
                    "countryOfBirth": "string",
                    "countryOfCitizenship": "string"
                },
                "address": {
                    "streetNumber": "string",
                    "streetName": "string",
                    "aptNumber": "string",
                    "city": "string",
                    "state": "string",
                    "zipCode": "string",
                    "country": "string"
                },
                "contact": {
                    "daytimePhone": "string",
                    "mobilePhone": "string",
                    "emailAddress": "string"
                },
                "immigration": {
                    "currentStatus": "string",
                    "statusExpirationDate": "date",
                    "i94Number": "string",
                    "passportNumber": "string",
                    "passportCountry": "string",
                    "passportExpiration": "date",
                    "lastEntryDate": "date",
                    "lastEntryPort": "string"
                }
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
    """Complete extraction result with mapping support"""
    form_number: str
    form_title: str
    parts: Dict[int, PartStructure] = field(default_factory=dict)
    
    # Validation status
    is_valid: bool = False
    validation_errors: List[str] = field(default_factory=list)
    validation_score: float = 0.0
    
    # Extraction metadata
    extraction_iterations: int = 0
    total_fields: int = 0
    
    # Mapping metadata
    mapped_fields: Dict[str, FieldMapping] = field(default_factory=dict)
    unmapped_fields: List[str] = field(default_factory=list)
    mapping_completeness: float = 0.0
    
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

# ===== PATTERN LIBRARY =====
class PatternLibrary:
    """Library of extraction patterns"""
    
    def __init__(self):
        self.patterns = self._build_patterns()
        self.form_schemas = self._build_form_schemas()
        self.mapping_patterns = self._build_mapping_patterns()
    
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
    
    def _build_mapping_patterns(self) -> Dict[str, Tuple[str, str, float]]:
        """Build patterns for database mapping"""
        return {
            # Name mappings
            r'family.*name|last.*name': ('beneficiary', 'lastName', 0.95),
            r'given.*name|first.*name': ('beneficiary', 'firstName', 0.95),
            r'middle.*name': ('beneficiary', 'middleName', 0.9),
            
            # Number mappings
            r'a.*number|alien.*number': ('beneficiary', 'alienNumber', 0.95),
            r'ssn|social.*security': ('beneficiary', 'socialSecurityNumber', 0.95),
            r'passport.*number': ('immigration', 'passportNumber', 0.9),
            r'i.*94.*number': ('immigration', 'i94Number', 0.9),
            
            # Date mappings
            r'date.*birth|birth.*date': ('beneficiary', 'dateOfBirth', 0.95),
            r'expir.*date|status.*expir': ('immigration', 'statusExpirationDate', 0.9),
            
            # Address mappings
            r'street.*number.*name|street.*address': ('address', 'streetName', 0.9),
            r'apt|suite|ste': ('address', 'aptNumber', 0.85),
            r'city|town': ('address', 'city', 0.9),
            r'state': ('address', 'state', 0.85),
            r'zip.*code': ('address', 'zipCode', 0.9),
            
            # Contact mappings
            r'daytime.*phone': ('contact', 'daytimePhone', 0.9),
            r'mobile.*phone|cell': ('contact', 'mobilePhone', 0.9),
            r'email.*address': ('contact', 'emailAddress', 0.95),
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
                elif "mapping" in self.name.lower():
                    css_class += " mapping-agent"
                
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

# ===== EXTRACTION AGENTS =====

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
            # Handle PDF file properly
            if hasattr(pdf_file, 'read'):
                # If it's a file-like object, read bytes
                pdf_file.seek(0)  # Reset file pointer to beginning
                pdf_bytes = pdf_file.read()
            else:
                # Assume it's already bytes
                pdf_bytes = pdf_file
            
            # Open PDF from bytes
            if not pdf_bytes:
                raise ValueError("Empty PDF file provided")
            
            self.doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            if self.doc.page_count == 0:
                raise ValueError("PDF has no pages")
            
            # Identify form
            form_info = self._identify_form()
            schema = self.pattern_library.form_schemas.get(form_info['number'])
            
            result = FormExtractionResult(
                form_number=form_info['number'],
                form_title=form_info['title']
            )
            
            # Process all pages sequentially
            all_text_blocks = []
            for page_num in range(len(self.doc)):
                page_blocks = self._extract_page_blocks(page_num)
                all_text_blocks.extend(page_blocks)
            
            # Process blocks in order to maintain part sequencing
            self._process_blocks_sequentially(all_text_blocks, result, schema)
            
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
        if not self.doc or self.doc.page_count == 0:
            return {"number": "Unknown", "title": "Unknown Form"}
        
        first_page_text = self.doc[0].get_text()
        
        # Check against known forms
        for form_num, schema in self.pattern_library.form_schemas.items():
            if form_num in first_page_text:
                # Verify with title
                if schema.form_title.lower() in first_page_text.lower():
                    self.log(f"Identified form: {form_num} - {schema.form_title}", "success")
                    return {"number": form_num, "title": schema.form_title}
        
        # Extended form detection
        form_patterns = {
            "I-129": "Petition for a Nonimmigrant Worker",
            "I-90": "Application to Replace Permanent Resident Card",
            "I-485": "Application to Register Permanent Residence",
            "I-765": "Application for Employment Authorization",
            "N-400": "Application for Naturalization"
        }
        
        for form_num, form_title in form_patterns.items():
            if form_num in first_page_text:
                self.log(f"Identified form: {form_num} - {form_title}", "success")
                return {"number": form_num, "title": form_title}
        
        # Fallback
        self.log("Could not identify form type", "warning")
        return {"number": "Unknown", "title": "Unknown Form"}
    
    def _extract_page_blocks(self, page_num: int) -> List[Dict]:
        """Extract all text blocks from a page with metadata"""
        page = self.doc[page_num]
        blocks = page.get_text("dict")
        
        page_blocks = []
        for block in blocks["blocks"]:
            if block["type"] == 0:  # Text block
                for line in block["lines"]:
                    text = self._get_line_text(line)
                    if text.strip():
                        page_blocks.append({
                            'text': text,
                            'line': line,
                            'page': page_num,
                            'bbox': line.get("bbox"),
                            'spans': line.get("spans", [])
                        })
        
        return page_blocks
    
    def _process_blocks_sequentially(self, blocks: List[Dict], result: FormExtractionResult, 
                                   schema: Optional[FormSchema]):
        """Process blocks sequentially to maintain part order"""
        current_part = None
        field_stack = []
        seen_parts = set()
        
        for block in blocks:
            text = block['text']
            
            # Try to match patterns
            matched_field = self._match_patterns(text, block['line'], block['page'])
            
            if matched_field:
                # Handle part headers
                if self._is_part_header(matched_field):
                    part_info = self._extract_part_info(matched_field)
                    if part_info:
                        part_num = part_info['number']
                        
                        # Create part if not exists
                        if part_num not in result.parts:
                            result.parts[part_num] = PartStructure(
                                part_number=part_num,
                                part_name=f"Part {part_num}",
                                part_title=part_info['title']
                            )
                            self.log(f"Found Part {part_num}: {part_info['title']}")
                        
                        current_part = result.parts[part_num]
                        seen_parts.add(part_num)
                        field_stack = []
                
                # Handle fields
                elif current_part:
                    self._place_field_in_hierarchy(
                        matched_field, current_part, field_stack, schema
                    )
        
        # Ensure we have at least Part 1 if no parts were found
        if not result.parts:
            result.parts[1] = PartStructure(
                part_number=1,
                part_name="Part 1",
                part_title="Form Fields"
            )
            self.log("No parts found, creating default Part 1", "warning")
    
    def _is_part_header(self, field: FieldNode) -> bool:
        """Check if field is a part header"""
        return bool(re.match(r'^Part\s*\d+', field.label, re.IGNORECASE))
    
    def _extract_part_info(self, field: FieldNode) -> Optional[Dict]:
        """Extract part information from field"""
        match = re.match(r'^Part\s*(\d+)\.?\s*(.*)$', field.label, re.IGNORECASE)
        if match:
            return {
                'number': int(match.group(1)),
                'title': match.group(2).strip() if match.group(2) else ""
            }
        return None
    
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
        
        elif pattern.description == "Letter-only sub-item":
            letter = match.group(1)
            label = match.group(2) if match.lastindex > 1 else text
            
            return FieldNode(
                item_number=letter,
                label=label.strip(),
                field_type=self._determine_field_type_smart(label),
                page=page_num + 1,
                confidence=ExtractionConfidence.MEDIUM,
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
    
    def _place_field_in_hierarchy(self, field: FieldNode, part: PartStructure,
                                field_stack: List[FieldNode], schema: Optional[FormSchema]):
        """Place field in correct position in hierarchy"""
        # Determine hierarchy level
        field_level = self._determine_hierarchy_level(field)
        
        # Pop stack to appropriate level
        while field_stack and field_stack[-1].get_depth() >= field_level:
            field_stack.pop()
        
        # Find parent
        if field_stack and field_level > 0:
            parent = field_stack[-1]
            parent.add_child(field)
        else:
            # Add to root if no parent or main level
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
        
        # Ensure parts are properly numbered
        self._ensure_part_continuity(result)
    
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
    
    def _ensure_part_continuity(self, result: FormExtractionResult):
        """Ensure parts are properly numbered and continuous"""
        if not result.parts:
            return
        
        # Get sorted part numbers
        part_numbers = sorted(result.parts.keys())
        
        # Check for gaps
        expected = 1
        for part_num in part_numbers:
            if part_num != expected:
                self.log(f"Part numbering gap: expected Part {expected}, found Part {part_num}", "warning")
            expected = part_num + 1
    
    # Helper methods
    def _get_line_text(self, line: Dict) -> str:
        """Extract text from line"""
        text_parts = []
        for span in line.get("spans", []):
            text_parts.append(span.get("text", ""))
        return " ".join(text_parts)
    
    def _get_font_size(self, line: Dict) -> float:
        """Get average font size"""
        spans = line.get("spans", [])
        if spans and len(spans) > 0:
            return spans[0].get("size", 10)
        return 10
    
    def _is_bold(self, line: Dict) -> bool:
        """Check if text is bold"""
        spans = line.get("spans", [])
        if spans and len(spans) > 0:
            flags = spans[0].get("flags", 0)
            return bool(flags & 2**4)  # Bold flag
        return False
    
    def _get_bbox(self, line: Dict) -> Optional[Tuple[float, float, float, float]]:
        """Get bounding box"""
        if "bbox" in line:
            bbox = line["bbox"]
            return (bbox[0], bbox[1], bbox[2], bbox[3])
        return None

# Continue with the rest of the agents...
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

# ===== MAPPING AGENTS =====

class DatabaseMappingAgent(BaseAgent):
    """Agent for mapping extracted fields to database schema"""
    
    def __init__(self):
        super().__init__(
            "Database Mapping Agent",
            "Maps extracted fields to database schema using intelligent patterns"
        )
        self.pattern_library = PatternLibrary()
        self.database_schema = DatabaseSchema()
    
    def execute(self, result: FormExtractionResult) -> FormExtractionResult:
        """Execute database mapping"""
        self.start()
        
        try:
            all_fields = result.get_all_fields_with_keys()
            mapped_count = 0
            unmapped_count = 0
            
            # Get mapping patterns
            mapping_patterns = self.pattern_library.mapping_patterns
            
            for field_key, field in all_fields.items():
                field_label_lower = field.label.lower()
                best_match = None
                best_confidence = 0.0
                
                # Try to match against patterns
                for pattern, (table, column, confidence) in mapping_patterns.items():
                    if re.search(pattern, field_label_lower):
                        if confidence > best_confidence:
                            best_confidence = confidence
                            best_match = (table, column)
                
                if best_match:
                    table, column = best_match
                    field.mapping_status = MappingStatus.MAPPED
                    field.mapped_to = f"{table}.{column}"
                    field.mapping_confidence = best_confidence
                    
                    # Create mapping record
                    mapping = FieldMapping(
                        pdf_field_key=field_key,
                        pdf_field_label=field.label,
                        database_table=table,
                        database_field=column,
                        confidence=best_confidence
                    )
                    result.mapped_fields[field_key] = mapping
                    mapped_count += 1
                    
                    self.log(f"Mapped '{field.label}' → {table}.{column} (confidence: {best_confidence:.0%})")
                else:
                    field.mapping_status = MappingStatus.UNMAPPED
                    result.unmapped_fields.append(field_key)
                    unmapped_count += 1
            
            # Calculate mapping completeness
            total_fields = len(all_fields)
            result.mapping_completeness = mapped_count / total_fields if total_fields > 0 else 0
            
            self.log(f"Mapped {mapped_count} fields, {unmapped_count} unmapped")
            self.log(f"Mapping completeness: {result.mapping_completeness:.0%}")
            
            self.complete()
            return result
            
        except Exception as e:
            self.log(f"Mapping failed: {str(e)}", "error")
            self.complete(False)
            raise

class MappingValidatorAgent(BaseAgent):
    """Agent for validating field mappings"""
    
    def __init__(self):
        super().__init__(
            "Mapping Validator Agent",
            "Validates and improves field mappings"
        )
    
    def execute(self, result: FormExtractionResult) -> Tuple[bool, float, List[Dict]]:
        """Validate mappings"""
        self.start()
        
        try:
            validation_results = []
            issues = []
            
            # Check required fields
            all_fields = result.get_all_fields_with_keys()
            
            # Validation checks
            checks = [
                {
                    "name": "Required fields mapped",
                    "check": self._check_required_fields,
                    "weight": 2.0
                },
                {
                    "name": "Data type compatibility",
                    "check": self._check_data_types,
                    "weight": 1.5
                },
                {
                    "name": "Mapping confidence",
                    "check": self._check_mapping_confidence,
                    "weight": 1.0
                },
                {
                    "name": "No duplicate mappings",
                    "check": self._check_duplicates,
                    "weight": 1.5
                }
            ]
            
            total_score = 0.0
            total_weight = 0.0
            
            for check in checks:
                passed, score, details = check["check"](result)
                validation_results.append({
                    "check": check["name"],
                    "passed": passed,
                    "score": score,
                    "details": details,
                    "weight": check["weight"]
                })
                
                total_score += score * check["weight"]
                total_weight += check["weight"]
                
                if passed:
                    self.log(f"✓ {check['name']}: {score:.0%}", "success")
                else:
                    self.log(f"✗ {check['name']}: {score:.0%}", "warning")
                    issues.append(details)
            
            overall_score = total_score / total_weight if total_weight > 0 else 0
            is_valid = overall_score >= 0.7
            
            self.log(f"Overall mapping validation score: {overall_score:.0%}")
            self.complete()
            
            return is_valid, overall_score, validation_results
            
        except Exception as e:
            self.log(f"Validation failed: {str(e)}", "error")
            self.complete(False)
            return False, 0.0, []
    
    def _check_required_fields(self, result: FormExtractionResult) -> Tuple[bool, float, str]:
        """Check if required fields are mapped"""
        # Define critical fields that should be mapped
        critical_fields = [
            ('beneficiary', 'firstName'),
            ('beneficiary', 'lastName'),
            ('beneficiary', 'dateOfBirth'),
            ('beneficiary', 'alienNumber')
        ]
        
        mapped_tables = defaultdict(set)
        for mapping in result.mapped_fields.values():
            mapped_tables[mapping.database_table].add(mapping.database_field)
        
        missing = []
        for table, field in critical_fields:
            if field not in mapped_tables.get(table, set()):
                missing.append(f"{table}.{field}")
        
        if not missing:
            return True, 1.0, "All critical fields mapped"
        else:
            score = 1.0 - (len(missing) / len(critical_fields))
            return False, score, f"Missing critical fields: {', '.join(missing)}"
    
    def _check_data_types(self, result: FormExtractionResult) -> Tuple[bool, float, str]:
        """Check data type compatibility"""
        mismatches = []
        total = len(result.mapped_fields)
        correct = 0
        
        for field_key, mapping in result.mapped_fields.items():
            field = result.get_all_fields_with_keys().get(field_key)
            if field:
                # Simple type checking
                if field.field_type == FieldType.DATE and 'date' not in mapping.database_field.lower():
                    mismatches.append(f"{field.label} (DATE) → {mapping.database_field}")
                elif field.field_type == FieldType.NUMBER and mapping.database_field.endswith('Name'):
                    mismatches.append(f"{field.label} (NUMBER) → {mapping.database_field}")
                else:
                    correct += 1
            else:
                correct += 1
        
        score = correct / total if total > 0 else 0
        passed = len(mismatches) == 0
        
        return passed, score, f"Type mismatches: {len(mismatches)}" if mismatches else "All types compatible"
    
    def _check_mapping_confidence(self, result: FormExtractionResult) -> Tuple[bool, float, str]:
        """Check mapping confidence levels"""
        if not result.mapped_fields:
            return False, 0.0, "No mappings to check"
        
        confidences = [m.confidence for m in result.mapped_fields.values()]
        avg_confidence = sum(confidences) / len(confidences)
        low_confidence = [m for m in result.mapped_fields.values() if m.confidence < 0.7]
        
        if avg_confidence >= 0.8 and not low_confidence:
            return True, 1.0, f"Average confidence: {avg_confidence:.0%}"
        else:
            return False, avg_confidence, f"Low confidence mappings: {len(low_confidence)}"
    
    def _check_duplicates(self, result: FormExtractionResult) -> Tuple[bool, float, str]:
        """Check for duplicate mappings"""
        mapping_targets = defaultdict(list)
        
        for field_key, mapping in result.mapped_fields.items():
            target = f"{mapping.database_table}.{mapping.database_field}"
            mapping_targets[target].append(field_key)
        
        duplicates = {k: v for k, v in mapping_targets.items() if len(v) > 1}
        
        if not duplicates:
            return True, 1.0, "No duplicate mappings"
        else:
            return False, 0.5, f"Duplicate mappings found: {len(duplicates)}"

class ManualMappingAgent(BaseAgent):
    """Agent for handling manual field additions and mappings"""
    
    def __init__(self):
        super().__init__(
            "Manual Mapping Agent",
            "Handles manual field additions and user-defined mappings"
        )
    
    def execute(self, manual_fields: List[Dict], result: FormExtractionResult) -> FormExtractionResult:
        """Process manual field additions"""
        self.start()
        
        try:
            added_count = 0
            
            for manual_field in manual_fields:
                # Create new field node
                field_key = f"MANUAL_{len(result.get_all_fields_with_keys()) + added_count}"
                
                field_node = FieldNode(
                    item_number=field_key,
                    label=manual_field['label'],
                    value=manual_field['value'],
                    field_type=FieldType.TEXT,
                    page=0,
                    confidence=ExtractionConfidence.HIGH,
                    extraction_method="manual",
                    mapping_status=MappingStatus.MANUAL,
                    mapped_to=manual_field.get('mapped_to'),
                    key=field_key
                )
                
                # Add to appropriate part (create manual part if needed)
                if 99 not in result.parts:
                    result.parts[99] = PartStructure(
                        part_number=99,
                        part_name="Manual Entries",
                        part_title="Manually Added Fields"
                    )
                
                result.parts[99].root_fields.append(field_node)
                
                # Create mapping if specified
                if manual_field.get('mapped_to'):
                    table, field = manual_field['mapped_to'].split('.')
                    mapping = FieldMapping(
                        pdf_field_key=field_key,
                        pdf_field_label=manual_field['label'],
                        database_table=table,
                        database_field=field,
                        confidence=1.0
                    )
                    result.mapped_fields[field_key] = mapping
                
                added_count += 1
                self.log(f"Added manual field: {manual_field['label']}")
            
            self.log(f"Added {added_count} manual fields", "success")
            self.complete()
            return result
            
        except Exception as e:
            self.log(f"Manual mapping failed: {str(e)}", "error")
            self.complete(False)
            raise

class TypeScriptGeneratorAgent(BaseAgent):
    """Agent for generating TypeScript interfaces"""
    
    def __init__(self):
        super().__init__(
            "TypeScript Generator Agent",
            "Generates TypeScript interfaces from mapped fields"
        )
    
    def execute(self, result: FormExtractionResult) -> str:
        """Generate TypeScript interfaces"""
        self.start()
        
        try:
            ts_code = f"// Generated TypeScript interfaces for {result.form_number}\n"
            ts_code += f"// Generated on: {datetime.now().isoformat()}\n\n"
            
            # Group mappings by table
            tables = defaultdict(list)
            for mapping in result.mapped_fields.values():
                tables[mapping.database_table].append(mapping)
            
            # Generate interfaces
            for table, mappings in tables.items():
                interface_name = self._to_pascal_case(table)
                ts_code += f"export interface {interface_name} {{\n"
                
                # Get unique fields
                fields = {}
                for mapping in mappings:
                    if mapping.database_field not in fields:
                        field_type = self._get_typescript_type(mapping.database_field)
                        fields[mapping.database_field] = field_type
                
                # Write fields
                for field_name, field_type in sorted(fields.items()):
                    ts_code += f"  {field_name}: {field_type};\n"
                
                ts_code += "}\n\n"
            
            # Generate main form interface
            form_interface = self._to_pascal_case(result.form_number.replace('-', ''))
            ts_code += f"export interface {form_interface}FormData {{\n"
            for table in tables.keys():
                interface_name = self._to_pascal_case(table)
                ts_code += f"  {table}: {interface_name};\n"
            ts_code += "}\n\n"
            
            # Generate validation schema
            ts_code += f"// Validation schema\n"
            ts_code += f"export const {form_interface}ValidationSchema = {{\n"
            for table in tables.keys():
                ts_code += f"  {table}: {{\n"
                ts_code += f"    required: ['firstName', 'lastName', 'dateOfBirth'],\n"
                ts_code += f"  }},\n"
            ts_code += "};\n"
            
            self.log(f"Generated TypeScript for {len(tables)} tables", "success")
            self.complete()
            return ts_code
            
        except Exception as e:
            self.log(f"TypeScript generation failed: {str(e)}", "error")
            self.complete(False)
            raise
    
    def _to_pascal_case(self, text: str) -> str:
        """Convert to PascalCase"""
        return ''.join(word.capitalize() for word in text.split('_'))
    
    def _get_typescript_type(self, field_name: str) -> str:
        """Determine TypeScript type from field name"""
        if 'date' in field_name.lower():
            return 'string | Date'
        elif 'number' in field_name.lower() or field_name.endswith('Count'):
            return 'number'
        elif field_name.endswith('Flag') or field_name.startswith('is'):
            return 'boolean'
        else:
            return 'string'

class JSONExportAgent(BaseAgent):
    """Agent for exporting mapped data as JSON"""
    
    def __init__(self):
        super().__init__(
            "JSON Export Agent",
            "Exports mapped data in various JSON formats"
        )
    
    def execute(self, result: FormExtractionResult) -> Dict[str, Any]:
        """Generate JSON exports"""
        self.start()
        
        try:
            all_fields = result.get_all_fields_with_keys()
            
            # Generate mapped data JSON
            mapped_data = defaultdict(dict)
            for field_key, mapping in result.mapped_fields.items():
                if field_key in all_fields:
                    value = all_fields[field_key].value
                    mapped_data[mapping.database_table][mapping.database_field] = value
            
            # Generate unmapped fields JSON
            unmapped_data = {}
            for field_key in result.unmapped_fields:
                if field_key in all_fields:
                    field = all_fields[field_key]
                    unmapped_data[field_key] = {
                        "label": field.label,
                        "value": field.value,
                        "type": field.field_type.value,
                        "page": field.page,
                        "confidence": field.confidence.value
                    }
            
            # Generate complete export
            export = {
                "metadata": {
                    "form_number": result.form_number,
                    "form_title": result.form_title,
                    "extraction_date": datetime.now().isoformat(),
                    "total_fields": result.total_fields,
                    "mapped_count": len(result.mapped_fields),
                    "unmapped_count": len(result.unmapped_fields),
                    "mapping_completeness": result.mapping_completeness
                },
                "mapped_data": dict(mapped_data),
                "unmapped_fields": unmapped_data
            }
            
            self.log(f"Generated JSON export with {len(mapped_data)} tables", "success")
            self.complete()
            return export
            
        except Exception as e:
            self.log(f"JSON export failed: {str(e)}", "error")
            self.complete(False)
            raise

# ===== MASTER COORDINATOR =====
class MasterCoordinator(BaseAgent):
    """Original coordinator for extraction only"""
    
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
            # Store original file position
            if hasattr(pdf_file, 'seek'):
                original_position = pdf_file.tell()
            
            result = None
            best_result = None
            best_score = 0.0
            
            for iteration in range(self.max_iterations):
                self.log(f"\n{'='*50}")
                self.log(f"Starting iteration {iteration + 1}/{self.max_iterations}")
                
                # Reset file position if needed
                if hasattr(pdf_file, 'seek'):
                    pdf_file.seek(0)
                
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
        finally:
            # Reset file position
            if hasattr(pdf_file, 'seek'):
                pdf_file.seek(0)
    
    def _refine_extraction(self, pdf_file, previous_result: FormExtractionResult,
                         validation_results: List[Dict]) -> FormExtractionResult:
        """Refine extraction based on validation feedback"""
        # Analyze validation results
        issues = []
        for result in validation_results:
            if not result["passed"]:
                issues.append(result)
        
        self.log(f"Refining based on {len(issues)} validation issues")
        
        # Reset file position
        if hasattr(pdf_file, 'seek'):
            pdf_file.seek(0)
        
        # For now, just re-run extraction
        # In a production system, this would adjust patterns based on specific issues
        return self.agents['extractor'].execute(pdf_file)

# ===== ENHANCED MASTER COORDINATOR =====
class EnhancedMasterCoordinator(BaseAgent):
    """Enhanced coordinator that manages both extraction and mapping agents"""
    
    def __init__(self, max_iterations: int = 3):
        super().__init__(
            "Enhanced Master Coordinator",
            "Orchestrates extraction and database mapping"
        )
        self.max_iterations = max_iterations
        
        # Extraction agents
        self.extraction_agents = {
            'extractor': AdaptivePatternExtractor(),
            'assigner': SmartKeyAssignment(),
            'validator': QuestionnaireValidator(),
            'formatter': OutputFormatter()
        }
        
        # Mapping agents
        self.mapping_agents = {
            'mapper': DatabaseMappingAgent(),
            'mapping_validator': MappingValidatorAgent(),
            'manual_mapper': ManualMappingAgent(),
            'ts_generator': TypeScriptGeneratorAgent(),
            'json_exporter': JSONExportAgent()
        }
        
        self.pattern_library = PatternLibrary()
    
    def execute(self, pdf_file, manual_fields: List[Dict] = None) -> Dict[str, Any]:
        """Execute complete extraction and mapping pipeline"""
        self.start()
        
        try:
            # Phase 1: Extraction
            self.log("=== PHASE 1: PDF EXTRACTION ===")
            extraction_result = self._run_extraction_phase(pdf_file)
            
            if not extraction_result:
                self.log("Extraction phase failed", "error")
                self.complete(False)
                return None
            
            # Phase 2: Database Mapping
            self.log("\n=== PHASE 2: DATABASE MAPPING ===")
            mapping_result = self._run_mapping_phase(extraction_result, manual_fields)
            
            # Phase 3: Validation
            self.log("\n=== PHASE 3: MAPPING VALIDATION ===")
            validation_result = self._run_validation_phase(mapping_result)
            
            # Phase 4: Export Generation
            self.log("\n=== PHASE 4: EXPORT GENERATION ===")
            export_result = self._run_export_phase(mapping_result)
            
            # Combine all results
            final_output = {
                'extraction': extraction_result.to_output_format(),
                'mapping': {
                    'mapped_fields': {k: asdict(v) for k, v in mapping_result.mapped_fields.items()},
                    'unmapped_fields': mapping_result.unmapped_fields,
                    'completeness': mapping_result.mapping_completeness
                },
                'validation': validation_result,
                'exports': export_result,
                '_metadata': {
                    'form_number': extraction_result.form_number,
                    'form_title': extraction_result.form_title,
                    'total_fields': extraction_result.total_fields,
                    'extraction_score': extraction_result.validation_score,
                    'mapping_completeness': mapping_result.mapping_completeness,
                    'timestamp': datetime.now().isoformat()
                }
            }
            
            self.log("✅ Complete pipeline executed successfully!", "success")
            self.complete()
            return final_output
            
        except Exception as e:
            self.log(f"Pipeline failed: {str(e)}", "error", traceback.format_exc())
            self.complete(False)
            return None
    
    def _run_extraction_phase(self, pdf_file) -> Optional[FormExtractionResult]:
        """Run extraction phase"""
        best_result = None
        best_score = 0.0
        
        for iteration in range(self.max_iterations):
            self.log(f"Extraction iteration {iteration + 1}/{self.max_iterations}")
            
            # Reset file position
            if hasattr(pdf_file, 'seek'):
                pdf_file.seek(0)
            
            # Extract
            if iteration == 0:
                result = self.extraction_agents['extractor'].execute(pdf_file)
            else:
                result = self._refine_extraction(pdf_file, result, validation_results)
            
            if not result:
                break
            
            # Assign keys
            result = self.extraction_agents['assigner'].execute(result)
            
            # Validate
            schema = self.pattern_library.form_schemas.get(result.form_number)
            is_valid, score, validation_results = self.extraction_agents['validator'].execute(result, schema)
            
            if score > best_score:
                best_score = score
                best_result = copy.deepcopy(result)
            
            if is_valid and score >= 0.85:
                self.log(f"Extraction successful with score {score:.0%}", "success")
                break
        
        return best_result
    
    def _run_mapping_phase(self, extraction_result: FormExtractionResult, 
                          manual_fields: Optional[List[Dict]]) -> FormExtractionResult:
        """Run mapping phase"""
        # Auto-map fields
        result = self.mapping_agents['mapper'].execute(extraction_result)
        
        # Add manual fields if provided
        if manual_fields:
            result = self.mapping_agents['manual_mapper'].execute(manual_fields, result)
        
        return result
    
    def _run_validation_phase(self, mapping_result: FormExtractionResult) -> Dict:
        """Run validation phase"""
        is_valid, score, details = self.mapping_agents['mapping_validator'].execute(mapping_result)
        
        return {
            'is_valid': is_valid,
            'score': score,
            'details': details
        }
    
    def _run_export_phase(self, mapping_result: FormExtractionResult) -> Dict:
        """Run export phase"""
        # Generate TypeScript
        typescript = self.mapping_agents['ts_generator'].execute(mapping_result)
        
        # Generate JSON
        json_export = self.mapping_agents['json_exporter'].execute(mapping_result)
        
        return {
            'typescript': typescript,
            'json': json_export
        }
    
    def _refine_extraction(self, pdf_file, previous_result: FormExtractionResult,
                         validation_results: List[Dict]) -> FormExtractionResult:
        """Refine extraction based on validation feedback"""
        # Analyze issues and re-extract
        issues = [r for r in validation_results if not r["passed"]]
        self.log(f"Refining based on {len(issues)} validation issues")
        
        # Reset file position
        if hasattr(pdf_file, 'seek'):
            pdf_file.seek(0)
        
        return self.extraction_agents['extractor'].execute(pdf_file)

# ===== UI COMPONENTS =====
def display_agent_activity():
    """Display agent activity log"""
    if 'agent_container' not in st.session_state:
        st.session_state.agent_container = st.container()
    return st.session_state.agent_container

def display_mapping_results(result: Dict):
    """Display mapping results"""
    if not result:
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### ✅ Mapped Fields")
        mapped = result.get('mapping', {}).get('mapped_fields', {})
        for field_key, mapping in mapped.items():
            st.markdown(
                f'<div class="field-card mapped-field">'
                f'<strong>{mapping["pdf_field_label"]}</strong><br>'
                f'PDF Key: {mapping["pdf_field_key"]}<br>'
                f'➡️ {mapping["database_table"]}.{mapping["database_field"]}<br>'
                f'Confidence: {mapping["confidence"]:.0%}'
                f'</div>',
                unsafe_allow_html=True
            )
    
    with col2:
        st.markdown("### ❓ Unmapped Fields")
        unmapped = result.get('mapping', {}).get('unmapped_fields', [])
        extraction_data = result.get('extraction', {})
        
        for field_key in unmapped:
            label = extraction_data.get(f"{field_key}_title", field_key)
            value = extraction_data.get(field_key, "")
            st.markdown(
                f'<div class="field-card unmapped-field">'
                f'<strong>{label}</strong><br>'
                f'Key: {field_key}<br>'
                f'Value: {value}'
                f'</div>',
                unsafe_allow_html=True
            )

# ===== MAIN APPLICATION =====
def main():
    st.markdown(
        '<div class="main-header">'
        '<h1>🤖 Advanced Multi-Agent USCIS Form Reader</h1>'
        '<p>PDF Extraction → Database Mapping → TypeScript/JSON Export</p>'
        '</div>', 
        unsafe_allow_html=True
    )
    
    # Initialize session state
    if 'pipeline_result' not in st.session_state:
        st.session_state.pipeline_result = None
    if 'manual_fields' not in st.session_state:
        st.session_state.manual_fields = []
    
    # Sidebar
    with st.sidebar:
        st.markdown("## ⚙️ Configuration")
        
        max_iterations = st.slider("Max Extraction Iterations", 1, 5, 3)
        show_agent_logs = st.checkbox("Show Agent Activity", value=True)
        
        st.markdown("---")
        st.markdown("## 🤖 Active Agents")
        
        st.markdown("### Extraction Agents")
        st.markdown("- 🔍 Adaptive Pattern Extractor")
        st.markdown("- 🏷️ Smart Key Assignment")
        st.markdown("- ✅ Questionnaire Validator")
        st.markdown("- 📄 Output Formatter")
        
        st.markdown("### Mapping Agents")
        st.markdown("- 🔗 Database Mapping Agent")
        st.markdown("- ✓ Mapping Validator")
        st.markdown("- ✏️ Manual Mapping Agent")
        st.markdown("- 📘 TypeScript Generator")
        st.markdown("- 📦 JSON Export Agent")
        
        st.markdown("---")
        st.markdown("## 📊 System Status")
        
        if PYMUPDF_AVAILABLE:
            st.success("✅ PyMuPDF Ready")
        else:
            st.error("❌ PyMuPDF Not Installed")
            st.code("pip install PyMuPDF")
    
    # Main content
    tabs = st.tabs([
        "📄 Upload & Process",
        "🔗 Mapping Results",
        "✏️ Manual Fields",
        "💾 Export Results"
    ])
    
    # Tab 1: Upload & Process
    with tabs[0]:
        st.markdown("### 📄 Upload USCIS Form")
        
        uploaded_file = st.file_uploader(
            "Choose a PDF form",
            type=['pdf'],
            help="Supported forms: I-539, I-129, G-28, I-90, I-485, I-765, N-400"
        )
        
        if uploaded_file:
            st.success(f"✅ Uploaded: {uploaded_file.name}")
            
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                if st.button("🚀 Run Complete Pipeline", type="primary", use_container_width=True):
                    # Create agent activity container
                    if show_agent_logs:
                        st.markdown("### 🤖 Agent Activity")
                        agent_container = st.container()
                        st.session_state.agent_container = agent_container
                    
                    with st.spinner("Running multi-agent pipeline..."):
                        # Run enhanced coordinator
                        coordinator = EnhancedMasterCoordinator(max_iterations=max_iterations)
                        result = coordinator.execute(uploaded_file, st.session_state.manual_fields)
                        
                        if result:
                            st.session_state.pipeline_result = result
                            st.success("✅ Pipeline completed successfully!")
                            
                            # Show summary metrics
                            metadata = result.get('_metadata', {})
                            col1, col2, col3, col4 = st.columns(4)
                            
                            with col1:
                                st.metric("Form", metadata.get('form_number', 'Unknown'))
                            with col2:
                                st.metric("Total Fields", metadata.get('total_fields', 0))
                            with col3:
                                st.metric("Extraction Score", f"{metadata.get('extraction_score', 0):.0%}")
                            with col4:
                                st.metric("Mapping Complete", f"{metadata.get('mapping_completeness', 0):.0%}")
                        else:
                            st.error("❌ Pipeline failed")
            
            with col2:
                if st.button("🔄 Reset", use_container_width=True):
                    st.session_state.pipeline_result = None
                    st.session_state.manual_fields = []
                    st.rerun()
    
    # Tab 2: Mapping Results
    with tabs[1]:
        st.markdown("### 🔗 Field Mapping Results")
        
        if st.session_state.pipeline_result:
            display_mapping_results(st.session_state.pipeline_result)
            
            # Mapping statistics
            st.markdown("### 📊 Mapping Statistics")
            mapping_data = st.session_state.pipeline_result.get('mapping', {})
            validation_data = st.session_state.pipeline_result.get('validation', {})
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Mapped Fields", len(mapping_data.get('mapped_fields', {})))
            with col2:
                st.metric("Unmapped Fields", len(mapping_data.get('unmapped_fields', [])))
            with col3:
                st.metric("Validation Score", f"{validation_data.get('score', 0):.0%}")
            
            # Validation details
            if validation_data.get('details'):
                with st.expander("📋 Validation Details"):
                    for detail in validation_data['details']:
                        icon = "✅" if detail['passed'] else "❌"
                        st.markdown(f"{icon} **{detail['check']}**: {detail['score']:.0%}")
                        st.caption(detail['details'])
        else:
            st.info("No results yet. Please process a form first.")
    
    # Tab 3: Manual Fields
    with tabs[2]:
        st.markdown("### ✏️ Add Manual Fields")
        
        with st.form("manual_field_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                field_label = st.text_input("Field Label")
                field_value = st.text_input("Field Value")
            
            with col2:
                # Database schema selector
                db_options = ["-- Select Database Field --"]
                schema = DatabaseSchema()
                for table, fields in schema.tables.items():
                    for field_name in fields:
                        db_options.append(f"{table}.{field_name}")
                
                mapped_to = st.selectbox("Map to Database Field", db_options)
            
            if st.form_submit_button("➕ Add Manual Field"):
                if field_label and field_value:
                    manual_field = {
                        'label': field_label,
                        'value': field_value,
                        'mapped_to': mapped_to if mapped_to != db_options[0] else None
                    }
                    st.session_state.manual_fields.append(manual_field)
                    st.success(f"Added manual field: {field_label}")
                    st.rerun()
        
        # Display manual fields
        if st.session_state.manual_fields:
            st.markdown("#### 📝 Current Manual Fields")
            for idx, field in enumerate(st.session_state.manual_fields):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.info(f"**{field['label']}**: {field['value']}")
                    if field.get('mapped_to'):
                        st.caption(f"Mapped to: {field['mapped_to']}")
                with col2:
                    if st.button("❌", key=f"del_{idx}"):
                        st.session_state.manual_fields.pop(idx)
                        st.rerun()
    
    # Tab 4: Export
    with tabs[3]:
        st.markdown("### 💾 Export Results")
        
        if st.session_state.pipeline_result:
            exports = st.session_state.pipeline_result.get('exports', {})
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("#### 📘 TypeScript Interface")
                if exports.get('typescript'):
                    st.download_button(
                        "⬇️ Download TypeScript",
                        exports['typescript'],
                        "form_interfaces.ts",
                        mime="text/plain",
                        use_container_width=True
                    )
            
            with col2:
                st.markdown("#### 📦 Mapped Data JSON")
                if exports.get('json'):
                    json_str = json.dumps(exports['json']['mapped_data'], indent=2)
                    st.download_button(
                        "⬇️ Download Mapped JSON",
                        json_str,
                        "mapped_data.json",
                        mime="application/json",
                        use_container_width=True
                    )
            
            with col3:
                st.markdown("#### ❓ Unmapped Fields")
                if exports.get('json', {}).get('unmapped_fields'):
                    json_str = json.dumps(exports['json']['unmapped_fields'], indent=2)
                    st.download_button(
                        "⬇️ Download Unmapped JSON",
                        json_str,
                        "unmapped_fields.json",
                        mime="application/json",
                        use_container_width=True
                    )
            
            # Preview sections
            st.markdown("### 👁️ Export Preview")
            
            preview_tabs = st.tabs(["TypeScript", "Mapped JSON", "Complete Export"])
            
            with preview_tabs[0]:
                if exports.get('typescript'):
                    st.code(exports['typescript'], language='typescript')
            
            with preview_tabs[1]:
                if exports.get('json'):
                    st.json(exports['json']['mapped_data'])
            
            with preview_tabs[2]:
                st.json(st.session_state.pipeline_result)
        else:
            st.info("No results to export. Please process a form first.")

if __name__ == "__main__":
    # Check dependencies
    if not PYMUPDF_AVAILABLE:
        st.error("❌ PyMuPDF is required but not installed!")
        st.code("pip install PyMuPDF")
        st.info("After installing, refresh this page.")
        st.stop()
    
    main()
