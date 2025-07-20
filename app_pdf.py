#!/usr/bin/env python3
"""
Advanced Agentic USCIS Form Reader - Improved Version
- Part-by-part extraction (even across pages)
- Proper hierarchical field extraction (1, 1a, 1b, 1c)
- Checkbox content extraction
- Self-improving with validation loops
- Database mapping with manual override
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
    page_title="Agentic KRISH USCIS Form Reader",
    page_icon="🤖",
    layout="wide"
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
        transition: all 0.3s ease;
    }
    .agent-active {
        border-left: 4px solid #2196F3;
        background: #E3F2FD;
        animation: pulse 1s infinite;
    }
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.8; }
        100% { opacity: 1; }
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
        background: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 6px;
        padding: 1rem;
        margin: 0.5rem 0;
        transition: all 0.2s ease;
    }
    .field-card:hover {
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        transform: translateY(-2px);
    }
    .part-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
        font-weight: bold;
    }
    .mapping-input {
        background: #f0f7ff;
        border: 2px dashed #2196F3;
        border-radius: 6px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    .duplicate-warning {
        background: #fff3cd;
        border-left: 4px solid #ffc107;
        padding: 0.5rem;
        margin: 0.5rem 0;
    }
    .learning-indicator {
        background: #e3f2fd;
        border: 1px solid #2196F3;
        border-radius: 20px;
        padding: 0.25rem 1rem;
        display: inline-block;
        animation: learning 2s infinite;
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
    }
    @keyframes learning {
        0% { transform: scale(1); }
        50% { transform: scale(1.05); }
        100% { transform: scale(1); }
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
    SUGGESTED = "suggested"
    REVIEW = "review"

# ===== DATA CLASSES =====
@dataclass
class CheckboxOption:
    """Represents a checkbox option"""
    text: str
    is_selected: bool = False
    position: Optional[Tuple[float, float]] = None

@dataclass
class LearnedPattern:
    """Pattern learned from successful extractions"""
    pattern: str
    field_type: FieldType
    confidence: float
    form_types: Set[str] = field(default_factory=set)
    success_count: int = 0
    last_seen: datetime = field(default_factory=datetime.now)
    
    def update_success(self, form_type: str):
        self.success_count += 1
        self.form_types.add(form_type)
        self.last_seen = datetime.now()
        self.confidence = min(0.95, self.confidence + 0.05)

@dataclass
class FieldNode:
    """Enhanced field node with better hierarchical support"""
    # Core properties
    item_number: str  # e.g., "1", "1a", "1b", "2a1"
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
    
    # Mapping
    mapping_status: MappingStatus = MappingStatus.UNMAPPED
    mapped_to: Optional[str] = None
    mapping_confidence: float = 0.0
    suggested_mappings: List[Tuple[str, float]] = field(default_factory=list)
    
    def __post_init__(self):
        # Generate content hash for duplicate detection
        if not self.content_hash:
            content = f"{self.label}_{self.item_number}_{self.page}_{self.part_number}"
            self.content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        # Generate unique key including content hash to ensure uniqueness
        if not self.key:
            self.key = f"P{self.part_number}_{self.item_number}_{self.content_hash}"
    
    def is_duplicate_of(self, other: 'FieldNode') -> bool:
        """Check if this is a duplicate of another field"""
        return (self.content_hash == other.content_hash or 
                (self.label == other.label and 
                 self.item_number == other.item_number and 
                 self.part_number == other.part_number))
    
    def add_child(self, child: 'FieldNode'):
        """Add child and set parent relationship"""
        child.parent = self
        self.children.append(child)

@dataclass
class PartStructure:
    """Part structure that can span multiple pages"""
    part_number: int
    part_name: str
    part_title: str = ""
    start_page: int = 1
    end_page: int = 1
    root_fields: List[FieldNode] = field(default_factory=list)
    field_hashes: Set[str] = field(default_factory=set)
    field_registry: Dict[str, FieldNode] = field(default_factory=dict)  # item_number -> FieldNode
    
    def add_field(self, field: FieldNode) -> bool:
        """Add field with duplicate check"""
        # Generate unique key if not already set
        if not field.key:
            field.key = f"P{self.part_number}_{field.item_number}_{field.content_hash}"
        
        if field.content_hash in self.field_hashes:
            return False  # Duplicate detected
        
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
            # Find parent
            parent_num = self._get_parent_number(field.item_number)
            if parent_num in self.field_registry:
                parent = self.field_registry[parent_num]
                parent.add_child(field)
            else:
                # Parent not found yet, add as root temporarily
                self.root_fields.append(field)
        
        return True
    
    def _is_root_field(self, item_number: str) -> bool:
        """Check if this is a root field (e.g., "1", "2", not "1a", "2b")"""
        return item_number.isdigit()
    
    def _get_parent_number(self, item_number: str) -> str:
        """Get parent number (e.g., "1a" -> "1", "1a1" -> "1a")"""
        # Match patterns like "1a", "1b", "2a1"
        if re.match(r'^\d+[a-z]$', item_number):
            # Simple sub-item like "1a"
            return item_number[:-1]
        elif re.match(r'^\d+[a-z]\d+$', item_number):
            # Nested item like "1a1"
            return re.match(r'^(\d+[a-z])', item_number).group(1)
        return ""
    
    def reorganize_hierarchy(self):
        """Reorganize fields to ensure proper parent-child relationships"""
        # Move misplaced children to their proper parents
        new_roots = []
        for field in self.root_fields:
            if not self._is_root_field(field.item_number):
                parent_num = self._get_parent_number(field.item_number)
                if parent_num in self.field_registry:
                    parent = self.field_registry[parent_num]
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

@dataclass
class FormExtractionResult:
    """Complete extraction result"""
    form_number: str
    form_title: str
    parts: Dict[int, PartStructure] = field(default_factory=dict)
    
    # Metadata
    total_fields: int = 0
    duplicate_count: int = 0
    extraction_iterations: int = 0
    confidence_score: float = 0.0
    
    # Mapping data
    field_mappings: Dict[str, str] = field(default_factory=dict)  # key -> db field
    manual_mappings: Dict[str, str] = field(default_factory=dict)
    suggested_mappings: Dict[str, List[Tuple[str, float]]] = field(default_factory=dict)

# ===== LEARNING PATTERN MANAGER =====
class PatternLearningManager:
    """Manages learned patterns across extractions"""
    
    def __init__(self):
        self.learned_patterns: Dict[str, LearnedPattern] = {}
        self.form_structures: Dict[str, Dict] = {}  # Form type -> expected structure
        self.field_type_indicators: Dict[str, List[str]] = self._init_type_indicators()
        self.load_patterns()
    
    def _init_type_indicators(self) -> Dict[str, List[str]]:
        """Initialize field type indicators"""
        return {
            FieldType.NAME.value: ['name', 'nombre', 'nom', 'family', 'given', 'middle'],
            FieldType.DATE.value: ['date', 'fecha', 'birth', 'expire', 'issue', 'dob', 'd.o.b'],
            FieldType.NUMBER.value: ['number', 'no.', '#', 'account', 'ssn', 'ein', 'a-number', 'alien', 'uscis'],
            FieldType.EMAIL.value: ['email', 'e-mail', 'correo', 'electronic mail'],
            FieldType.PHONE.value: ['phone', 'tel', 'mobile', 'cell', 'fax', 'daytime', 'evening'],
            FieldType.ADDRESS.value: ['address', 'street', 'city', 'state', 'zip', 'postal', 'apt', 'suite'],
            FieldType.CHECKBOX.value: ['select', 'check', 'yes', 'no', 'si', 'option', 'box below'],
            FieldType.SIGNATURE.value: ['signature', 'sign', 'firma', 'authorized'],
        }
    
    def suggest_field_type(self, text: str) -> Tuple[FieldType, float]:
        """Suggest field type based on learned patterns"""
        text_lower = text.lower()
        
        # Check learned patterns first
        if text_lower in self.learned_patterns:
            pattern = self.learned_patterns[text_lower]
            return pattern.field_type, pattern.confidence
        
        # Check indicators
        for field_type, indicators in self.field_type_indicators.items():
            for indicator in indicators:
                if indicator in text_lower:
                    return FieldType(field_type), 0.8
        
        return FieldType.UNKNOWN, 0.5
    
    def learn_pattern(self, text: str, field_type: FieldType, form_type: str, confidence: float = 0.7):
        """Learn a new pattern from successful extraction"""
        pattern_key = text.lower().strip()
        
        if pattern_key in self.learned_patterns:
            self.learned_patterns[pattern_key].update_success(form_type)
        else:
            self.learned_patterns[pattern_key] = LearnedPattern(
                pattern=text,
                field_type=field_type,
                confidence=confidence,
                form_types={form_type},
                success_count=1
            )
    
    def save_patterns(self):
        """Save learned patterns to file"""
        data = {
            'patterns': {k: asdict(v) for k, v in self.learned_patterns.items()},
            'structures': self.form_structures
        }
        try:
            with open('learned_patterns.json', 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except:
            pass
    
    def load_patterns(self):
        """Load patterns from file"""
        try:
            with open('learned_patterns.json', 'r') as f:
                data = json.load(f)
                # Reconstruct patterns
                for k, v in data.get('patterns', {}).items():
                    self.learned_patterns[k] = LearnedPattern(
                        pattern=v['pattern'],
                        field_type=FieldType(v['field_type']),
                        confidence=v['confidence'],
                        form_types=set(v['form_types']),
                        success_count=v['success_count']
                    )
                self.form_structures = data.get('structures', {})
        except:
            pass

# ===== BASE AGENT CLASS =====
class BaseAgent(ABC):
    """Enhanced base agent with learning capabilities"""
    
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.status = "idle"
        self.logs = []
        self.performance_metrics = {
            'success_rate': 0.0,
            'avg_time': 0.0,
            'total_runs': 0
        }
        self.learning_manager = PatternLearningManager()
    
    @abstractmethod
    def execute(self, *args, **kwargs) -> Any:
        pass
    
    def log(self, message: str, level: str = "info", details: Any = None):
        """Enhanced logging with UI display"""
        entry = {
            "timestamp": datetime.now(),
            "message": message,
            "level": level,
            "details": details
        }
        self.logs.append(entry)
        
        # Display in UI
        if 'agent_container' in st.session_state:
            with st.session_state.agent_container:
                css_class = "agent-card"
                if level == "error":
                    css_class += " agent-error"
                elif level == "success":
                    css_class += " agent-success"
                elif self.status == "active":
                    css_class += " agent-active"
                
                icon = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌"}.get(level, "📝")
                
                st.markdown(
                    f'<div class="{css_class}">'
                    f'{icon} <strong>{self.name}</strong>: {message}'
                    f'</div>', 
                    unsafe_allow_html=True
                )

# ===== IMPROVED EXTRACTION AGENT =====
class ImprovedSmartExtractionAgent(BaseAgent):
    """Improved extraction that handles parts across pages and hierarchical fields"""
    
    def __init__(self):
        super().__init__(
            "Improved Smart Extraction Agent",
            "Extracts fields part-by-part with proper hierarchy"
        )
        self.doc = None
        self.current_form_type = ""
        self.current_part = None
        
    def execute(self, pdf_file) -> FormExtractionResult:
        """Execute improved extraction"""
        self.status = "active"
        self.log("Starting improved part-by-part extraction...")
        
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
            self.current_form_type = form_info['number']
            
            result = FormExtractionResult(
                form_number=form_info['number'],
                form_title=form_info['title']
            )
            
            # Extract part by part
            self._extract_all_parts(result)
            
            # Reorganize hierarchy for all parts
            for part in result.parts.values():
                part.reorganize_hierarchy()
            
            # Calculate total fields
            result.total_fields = sum(len(part.get_all_fields_flat()) for part in result.parts.values())
            
            self.log(f"Extracted {result.total_fields} unique fields from {len(result.parts)} parts", "success")
            return result
            
        except Exception as e:
            self.log(f"Extraction failed: {str(e)}", "error")
            raise
        finally:
            if self.doc:
                self.doc.close()
    
    def _identify_form(self) -> Dict[str, str]:
        """Identify form using multiple strategies"""
        if not self.doc or self.doc.page_count == 0:
            return {"number": "Unknown", "title": "Unknown Form"}
        
        first_page_text = self.doc[0].get_text()
        
        # Common USCIS form patterns
        form_patterns = [
            (r'Form\s+(I-\d+[A-Z]?)', r'Form\s+I-\d+[A-Z]?\s*[^\n]+'),
            (r'Form\s+(N-\d+)', r'Form\s+N-\d+\s*[^\n]+'),
            (r'Form\s+(G-\d+)', r'Form\s+G-\d+\s*[^\n]+'),
            (r'Form\s+(AR-\d+)', r'Form\s+AR-\d+\s*[^\n]+'),
        ]
        
        for number_pattern, title_pattern in form_patterns:
            number_match = re.search(number_pattern, first_page_text, re.IGNORECASE)
            if number_match:
                form_number = number_match.group(1)
                title_match = re.search(title_pattern, first_page_text, re.IGNORECASE)
                form_title = title_match.group(0) if title_match else f"Form {form_number}"
                
                self.log(f"Identified form: {form_number}")
                return {"number": form_number, "title": form_title}
        
        return {"number": "Unknown", "title": "Unknown Form"}
    
    def _extract_all_parts(self, result: FormExtractionResult):
        """Extract all parts, handling parts that span pages"""
        all_pages_data = []
        
        # First, collect all page data
        for page_num in range(len(self.doc)):
            page = self.doc[page_num]
            page_data = self._extract_page_data(page, page_num)
            all_pages_data.append(page_data)
        
        # Now process pages to identify parts and fields
        current_part = None
        
        for page_num, page_data in enumerate(all_pages_data):
            self.log(f"Processing page {page_num + 1}/{len(all_pages_data)}")
            
            # Look for part headers in this page
            part_headers = self._find_part_headers(page_data['text'])
            
            if part_headers:
                # Process each part header found
                for part_info in part_headers:
                    if current_part:
                        # Finalize previous part
                        current_part.reorganize_hierarchy()
                    
                    # Create new part
                    part_num = part_info['number']
                    current_part = PartStructure(
                        part_number=part_num,
                        part_name=f"Part {part_num}",
                        part_title=part_info['title'],
                        start_page=page_num + 1
                    )
                    result.parts[part_num] = current_part
                    self.log(f"Found Part {part_num}: {part_info['title']}")
            
            # Extract fields from this page
            if current_part:
                self._extract_fields_from_page(page_data, current_part, page_num + 1)
            else:
                # No part found yet, create default Part 1
                if 1 not in result.parts:
                    current_part = PartStructure(1, "Part 1", "Form Fields")
                    result.parts[1] = current_part
                    self.log("No part header found, using default Part 1", "warning")
                else:
                    current_part = result.parts[1]
                
                self._extract_fields_from_page(page_data, current_part, page_num + 1)
    
    def _extract_page_data(self, page, page_num: int) -> Dict:
        """Extract structured data from a page"""
        page_dict = page.get_text("dict")
        
        # Extract blocks with detailed information
        blocks = []
        for block in page_dict["blocks"]:
            if block["type"] == 0:  # Text block
                for line in block["lines"]:
                    text = " ".join(span["text"] for span in line["spans"])
                    if text.strip():
                        blocks.append({
                            'text': text,
                            'bbox': line.get("bbox", [0, 0, 0, 0]),
                            'page': page_num,
                            'spans': line["spans"],
                            'is_bold': any(span.get("flags", 0) & 2**4 for span in line["spans"]),
                            'font_size': line["spans"][0].get("size", 10) if line["spans"] else 10
                        })
        
        # Sort blocks by position (top to bottom, left to right)
        blocks.sort(key=lambda b: (b['bbox'][1], b['bbox'][0]))
        
        return {
            'text': page.get_text(),
            'blocks': blocks,
            'page_num': page_num
        }
    
    def _find_part_headers(self, text: str) -> List[Dict[str, Any]]:
        """Find all part headers in text"""
        part_headers = []
        
        # Pattern for part headers
        part_pattern = re.compile(r'^Part\s+(\d+)[.:]\s*(.*)$', re.MULTILINE | re.IGNORECASE)
        
        for match in part_pattern.finditer(text):
            part_headers.append({
                'number': int(match.group(1)),
                'title': match.group(2).strip()
            })
        
        return part_headers
    
    def _extract_fields_from_page(self, page_data: Dict, current_part: PartStructure, page_num: int):
        """Extract all fields from a page"""
        blocks = page_data['blocks']
        
        i = 0
        while i < len(blocks):
            block = blocks[i]
            text = block['text'].strip()
            
            # Skip empty blocks
            if not text:
                i += 1
                continue
            
            # Try to extract field
            field = self._extract_field_from_block(block, blocks, i, page_num)
            
            if field:
                # Check for checkbox options after this field
                if "check" in field.label.lower() or "select" in field.label.lower():
                    checkbox_options = self._extract_checkbox_options(blocks, i + 1)
                    field.checkbox_options = checkbox_options
                    if checkbox_options:
                        field.field_type = FieldType.CHECKBOX
                
                # Add field to part
                if current_part.add_field(field):
                    self.log(f"Found field {field.item_number}: {field.label[:50]}...")
            
            i += 1
    
    def _extract_field_from_block(self, block: Dict, all_blocks: List[Dict], 
                                 block_idx: int, page_num: int) -> Optional[FieldNode]:
        """Extract field from block with improved pattern matching"""
        text = block['text'].strip()
        
        # Enhanced patterns for USCIS forms
        patterns = [
            # Main numbered items: "1.", "2.", etc.
            (r'^(\d+)\.\s+(.+?)(?:\s*\(|$)', 'main'),
            
            # Sub-items with dots: "1.a.", "1.b.", etc.
            (r'^(\d+)\.([a-z])\.\s+(.+?)(?:\s*\(|$)', 'sub_dot'),
            
            # Sub-items without dots: "1a.", "1b.", etc.
            (r'^(\d+)([a-z])\.\s+(.+?)(?:\s*\(|$)', 'sub_no_dot'),
            
            # Nested items: "1.a.1.", "1a1.", etc.
            (r'^(\d+)\.?([a-z])\.?(\d+)\.\s+(.+?)(?:\s*\(|$)', 'nested'),
            
            # Items with just number and no label on same line
            (r'^(\d+)\.\s*$', 'number_only'),
            (r'^(\d+)([a-z])\.\s*$', 'sub_number_only'),
        ]
        
        for pattern, pattern_type in patterns:
            match = re.match(pattern, text)
            if match:
                if pattern_type == 'main':
                    item_number = match.group(1)
                    label = match.group(2).strip()
                    
                elif pattern_type in ['sub_dot', 'sub_no_dot']:
                    item_number = match.group(1) + match.group(2)
                    label = match.group(3).strip() if match.lastindex >= 3 else ""
                    
                elif pattern_type == 'nested':
                    item_number = match.group(1) + match.group(2) + match.group(3)
                    label = match.group(4).strip()
                    
                elif pattern_type in ['number_only', 'sub_number_only']:
                    # Look ahead for label
                    if pattern_type == 'number_only':
                        item_number = match.group(1)
                    else:
                        item_number = match.group(1) + match.group(2)
                    
                    # Check next block for label
                    if block_idx + 1 < len(all_blocks):
                        next_block = all_blocks[block_idx + 1]
                        next_text = next_block['text'].strip()
                        
                        # Make sure next block isn't another numbered item
                        if not re.match(r'^\d+[a-z]?\d*\.', next_text):
                            label = next_text
                        else:
                            continue
                    else:
                        continue
                else:
                    continue
                
                # Create field node
                field_type, confidence = self.learning_manager.suggest_field_type(label)
                
                field = FieldNode(
                    item_number=item_number,
                    label=label,
                    field_type=field_type,
                    page=page_num,
                    confidence=ExtractionConfidence.HIGH if confidence > 0.8 else ExtractionConfidence.MEDIUM,
                    extraction_method="pattern_match",
                    raw_text=text,
                    bbox=tuple(block['bbox'])
                )
                
                return field
        
                        return None
    
    def _extract_checkbox_options(self, blocks: List[Dict], start_idx: int) -> List[CheckboxOption]:
        """Extract checkbox options from subsequent blocks"""
        options = []
        
        # Look at next several blocks for checkbox patterns
        for i in range(start_idx, min(start_idx + 10, len(blocks))):
            block = blocks[i]
            text = block['text'].strip()
            
            # Skip if this is a new field
            if re.match(r'^\d+[a-z]?\d*\.', text):
                break
            
            # Check for checkbox patterns
            # Pattern 1: "□ Option text" or "☐ Option text"
            checkbox_match = re.match(r'^[□☐]\s*(.+)', text)
            if checkbox_match:
                option_text = checkbox_match.group(1).strip()
                options.append(CheckboxOption(
                    text=option_text,
                    is_selected=False,
                    position=(block['bbox'][0], block['bbox'][1])
                ))
                continue
            
            # Pattern 2: "☑ Option text" or "☒ Option text" (selected)
            selected_match = re.match(r'^[☑☒]\s*(.+)', text)
            if selected_match:
                option_text = selected_match.group(1).strip()
                options.append(CheckboxOption(
                    text=option_text,
                    is_selected=True,
                    position=(block['bbox'][0], block['bbox'][1])
                ))
                continue
            
            # Pattern 3: Indented text that might be an option
            if block['bbox'][0] > blocks[start_idx - 1]['bbox'][0] + 20:  # Indented
                if len(text) < 100 and not text.endswith(':'):  # Reasonable length, not a label
                    options.append(CheckboxOption(
                        text=text,
                        is_selected=False,
                        position=(block['bbox'][0], block['bbox'][1])
                    ))
        
        return options

# ===== SMART KEY GENERATOR =====
class SmartKeyGenerator(BaseAgent):
    """Generates unique, meaningful keys"""
    
    def __init__(self):
        super().__init__(
            "Smart Key Generator",
            "Creates unique, hierarchical keys"
        )
    
    def execute(self, result: FormExtractionResult) -> FormExtractionResult:
        """Generate smart keys"""
        self.status = "active"
        self.log("Generating unique keys...")
        
        try:
            key_registry = set()
            
            for part_num, part in result.parts.items():
                for field in part.get_all_fields_flat():
                    # Generate base key
                    base_key = f"P{part_num}_{field.item_number}"
                    
                    # Ensure uniqueness
                    if base_key in key_registry:
                        # Add content hash for uniqueness
                        base_key = f"{base_key}_{field.content_hash}"
                    
                    # Still not unique? Add counter
                    unique_key = self._ensure_unique_key(base_key, key_registry)
                    field.key = unique_key
                    key_registry.add(unique_key)
            
            self.log(f"Generated {len(key_registry)} unique keys", "success")
            return result
            
        except Exception as e:
            self.log(f"Key generation failed: {str(e)}", "error")
            raise
    
    def _ensure_unique_key(self, base_key: str, registry: Set[str]) -> str:
        """Ensure key is unique"""
        if base_key not in registry:
            return base_key
        
        counter = 1
        while f"{base_key}_{counter}" in registry:
            counter += 1
        
        return f"{base_key}_{counter}"

# ===== VALIDATION AGENT =====
class ValidationAgent(BaseAgent):
    """Validates extraction with checks"""
    
    def __init__(self):
        super().__init__(
            "Validation Agent",
            "Validates extraction quality"
        )
    
    def execute(self, result: FormExtractionResult) -> Tuple[bool, float, List[Dict]]:
        """Execute validation"""
        self.status = "active"
        self.log("Running validation checks...")
        
        try:
            checks = [
                self._check_field_count,
                self._check_hierarchy,
                self._check_part_continuity,
                self._check_checkbox_detection,
                self._check_field_numbering,
            ]
            
            results = []
            total_score = 0.0
            
            for check in checks:
                check_result = check(result)
                results.append(check_result)
                total_score += check_result['score'] * check_result['weight']
                
                if check_result['passed']:
                    self.log(f"✅ {check_result['name']}: {check_result['score']:.0%}")
                else:
                    self.log(f"⚠️ {check_result['name']}: {check_result['score']:.0%} - {check_result['details']}", "warning")
            
            total_weight = sum(r['weight'] for r in results)
            final_score = total_score / total_weight if total_weight > 0 else 0
            is_valid = final_score >= 0.7
            
            result.confidence_score = final_score
            
            self.log(f"Validation complete: {final_score:.0%}", "success" if is_valid else "warning")
            return is_valid, final_score, results
            
        except Exception as e:
            self.log(f"Validation failed: {str(e)}", "error")
            return False, 0.0, []
    
    def _check_field_count(self, result: FormExtractionResult) -> Dict:
        """Check if enough fields were extracted"""
        min_expected = 15
        actual = result.total_fields
        
        if actual >= min_expected:
            return {
                'name': 'Field Count',
                'passed': True,
                'score': min(1.0, actual / 50),
                'weight': 1.5,
                'details': f'{actual} fields found'
            }
        else:
            return {
                'name': 'Field Count',
                'passed': False,
                'score': actual / min_expected,
                'weight': 1.5,
                'details': f'Only {actual} fields (expected {min_expected}+)'
            }
    
    def _check_hierarchy(self, result: FormExtractionResult) -> Dict:
        """Check if hierarchical structure is detected"""
        has_subitems = False
        subitem_count = 0
        
        for part in result.parts.values():
            for field in part.get_all_fields_flat():
                if field.children:
                    has_subitems = True
                    subitem_count += len(field.children)
        
        if has_subitems:
            return {
                'name': 'Hierarchy Detection',
                'passed': True,
                'score': min(1.0, subitem_count / 10),
                'weight': 1.0,
                'details': f'{subitem_count} sub-items found'
            }
        else:
            return {
                'name': 'Hierarchy Detection',
                'passed': False,
                'score': 0.0,
                'weight': 1.0,
                'details': 'No hierarchical structure detected'
            }
    
    def _check_part_continuity(self, result: FormExtractionResult) -> Dict:
        """Check if parts are properly organized"""
        if not result.parts:
            return {
                'name': 'Part Organization',
                'passed': False,
                'score': 0.0,
                'weight': 0.8,
                'details': 'No parts found'
            }
        
        part_numbers = sorted(result.parts.keys())
        expected = list(range(1, max(part_numbers) + 1))
        missing = set(expected) - set(part_numbers)
        
        if not missing:
            return {
                'name': 'Part Organization',
                'passed': True,
                'score': 1.0,
                'weight': 0.8,
                'details': f'{len(part_numbers)} parts found'
            }
        else:
            score = len(part_numbers) / len(expected)
            return {
                'name': 'Part Organization',
                'passed': False,
                'score': score,
                'weight': 0.8,
                'details': f'Missing parts: {sorted(missing)}'
            }
    
    def _check_checkbox_detection(self, result: FormExtractionResult) -> Dict:
        """Check if checkboxes are detected"""
        checkbox_fields = 0
        total_options = 0
        
        for part in result.parts.values():
            for field in part.get_all_fields_flat():
                if field.checkbox_options:
                    checkbox_fields += 1
                    total_options += len(field.checkbox_options)
        
        if checkbox_fields > 0:
            return {
                'name': 'Checkbox Detection',
                'passed': True,
                'score': min(1.0, checkbox_fields / 5),
                'weight': 0.7,
                'details': f'{checkbox_fields} checkbox fields with {total_options} options'
            }
        else:
            return {
                'name': 'Checkbox Detection',
                'passed': False,
                'score': 0.0,
                'weight': 0.7,
                'details': 'No checkboxes detected'
            }
    
    def _check_field_numbering(self, result: FormExtractionResult) -> Dict:
        """Check field numbering consistency"""
        issues = []
        
        for part_num, part in result.parts.items():
            # Get all field numbers
            numbers = []
            for field in part.get_all_fields_flat():
                if field.item_number.isdigit():
                    numbers.append(int(field.item_number))
            
            if numbers:
                numbers.sort()
                # Check for large gaps
                for i in range(1, len(numbers)):
                    if numbers[i] - numbers[i-1] > 5:
                        issues.append(f"Part {part_num}: gap between {numbers[i-1]} and {numbers[i]}")
        
        if not issues:
            return {
                'name': 'Field Numbering',
                'passed': True,
                'score': 1.0,
                'weight': 0.5,
                'details': 'Consistent numbering'
            }
        else:
            return {
                'name': 'Field Numbering',
                'passed': False,
                'score': max(0.3, 1.0 - len(issues) * 0.2),
                'weight': 0.5,
                'details': f'{len(issues)} numbering issues'
            }

# ===== MANUAL MAPPING AGENT =====
class DatabaseMappingAgent(BaseAgent):
    """Enhanced database mapping agent"""
    
    def __init__(self):
        super().__init__(
            "Database Mapping Agent",
            "Maps fields to database schema"
        )
        self.db_schema = self._get_default_schema()
    
    def _get_default_schema(self) -> Dict[str, List[str]]:
        """Get default database schema"""
        return {
            "personal_info": [
                "first_name", "last_name", "middle_name", "other_names",
                "date_of_birth", "place_of_birth", "country_of_birth",
                "nationality", "gender", "marital_status"
            ],
            "identification": [
                "alien_number", "uscis_number", "social_security_number",
                "passport_number", "passport_country", "passport_expiry",
                "driver_license", "state_id"
            ],
            "contact_info": [
                "mailing_address", "physical_address", "apt_suite",
                "city", "state", "zip_code", "country",
                "phone_number", "mobile_number", "email_address",
                "emergency_contact"
            ],
            "immigration_info": [
                "current_status", "status_expiry", "i94_number",
                "last_entry_date", "last_entry_port", "visa_number",
                "visa_type", "priority_date", "category"
            ],
            "employment": [
                "employer_name", "employer_address", "job_title",
                "start_date", "occupation_code", "salary",
                "work_address"
            ],
            "family": [
                "spouse_name", "spouse_dob", "children_count",
                "parent_names", "sibling_info"
            ],
            "application": [
                "application_type", "receipt_number", "priority_date",
                "filing_date", "decision_date", "notes"
            ]
        }
    
    def execute(self, result: FormExtractionResult, manual_mappings: Dict[str, str] = None) -> FormExtractionResult:
        """Execute mapping"""
        self.status = "active"
        self.log("Starting database mapping...")
        
        try:
            # Apply manual mappings first
            if manual_mappings:
                for field_key, db_field in manual_mappings.items():
                    result.manual_mappings[field_key] = db_field
                    result.field_mappings[field_key] = db_field
                self.log(f"Applied {len(manual_mappings)} manual mappings")
            
            # Auto-suggest mappings for unmapped fields
            unmapped_count = 0
            suggested_count = 0
            
            for part in result.parts.values():
                for field in part.get_all_fields_flat():
                    if field.key not in result.field_mappings:
                        suggestions = self._suggest_mapping(field)
                        if suggestions:
                            result.suggested_mappings[field.key] = suggestions
                            field.suggested_mappings = suggestions
                            field.mapping_status = MappingStatus.SUGGESTED
                            suggested_count += 1
                            
                            # Auto-map high confidence suggestions
                            if suggestions[0][1] >= 0.9:
                                result.field_mappings[field.key] = suggestions[0][0]
                                field.mapped_to = suggestions[0][0]
                                field.mapping_status = MappingStatus.MAPPED
                                field.mapping_confidence = suggestions[0][1]
                        else:
                            field.mapping_status = MappingStatus.UNMAPPED
                            unmapped_count += 1
                    else:
                        # Already mapped (manual)
                        field.mapped_to = result.field_mappings[field.key]
                        field.mapping_status = MappingStatus.MANUAL
                        field.mapping_confidence = 1.0
            
            self.log(f"Mapping complete: {len(result.field_mappings)} mapped, "
                    f"{suggested_count} suggested, {unmapped_count} unmapped", "success")
            
            return result
            
        except Exception as e:
            self.log(f"Mapping failed: {str(e)}", "error")
            raise
    
    def _suggest_mapping(self, field: FieldNode) -> List[Tuple[str, float]]:
        """Suggest database mappings for a field"""
        suggestions = []
        field_label_lower = field.label.lower()
        
        # Pattern-based matching
        patterns = {
            # Personal info patterns
            r'family.*name|last.*name': 'personal_info.last_name',
            r'given.*name|first.*name': 'personal_info.first_name',
            r'middle.*name': 'personal_info.middle_name',
            r'date.*birth|birth.*date|d\.?o\.?b': 'personal_info.date_of_birth',
            r'place.*birth|birth.*place': 'personal_info.place_of_birth',
            r'country.*birth|birth.*country': 'personal_info.country_of_birth',
            r'nationality|citizenship': 'personal_info.nationality',
            r'gender|sex': 'personal_info.gender',
            r'marital.*status': 'personal_info.marital_status',
            
            # Identification patterns
            r'a[\-\s]?number|alien.*number': 'identification.alien_number',
            r'uscis.*number|online.*account': 'identification.uscis_number',
            r'social.*security|ssn': 'identification.social_security_number',
            r'passport.*number': 'identification.passport_number',
            r'passport.*country': 'identification.passport_country',
            r'passport.*expir': 'identification.passport_expiry',
            
            # Contact patterns
            r'mailing.*address': 'contact_info.mailing_address',
            r'street.*number.*name': 'contact_info.physical_address',
            r'apt|suite|unit': 'contact_info.apt_suite',
            r'city|town': 'contact_info.city',
            r'state|province': 'contact_info.state',
            r'zip.*code|postal.*code': 'contact_info.zip_code',
            r'country': 'contact_info.country',
            r'daytime.*phone|phone.*number': 'contact_info.phone_number',
            r'mobile|cell': 'contact_info.mobile_number',
            r'email.*address|e[\-\s]?mail': 'contact_info.email_address',
        }
        
        for pattern, db_field in patterns.items():
            if re.search(pattern, field_label_lower):
                match = re.search(pattern, field_label_lower)
                confidence = 0.7 + (0.3 * (len(match.group()) / len(field_label_lower)))
                suggestions.append((db_field, min(0.95, confidence)))
        
        # Sort by confidence
        suggestions.sort(key=lambda x: x[1], reverse=True)
        
        return suggestions[:3]

# ===== MASTER COORDINATOR =====
class ImprovedMasterCoordinator(BaseAgent):
    """Improved coordinator with iterative refinement"""
    
    def __init__(self):
        super().__init__(
            "Improved Master Coordinator",
            "Orchestrates extraction with iterations"
        )
        self.agents = {
            'extractor': ImprovedSmartExtractionAgent(),
            'key_generator': SmartKeyGenerator(),
            'validator': ValidationAgent(),
            'mapper': DatabaseMappingAgent()
        }
        self.max_iterations = 3
    
    def execute(self, pdf_file, manual_mappings: Dict[str, str] = None) -> Dict[str, Any]:
        """Execute complete pipeline"""
        self.status = "active"
        self.log("🚀 Starting improved form processing pipeline...")
        
        try:
            # Phase 1: Extraction with refinement
            best_result = None
            best_score = 0.0
            
            for iteration in range(self.max_iterations):
                self.log(f"\n📊 Extraction Iteration {iteration + 1}/{self.max_iterations}")
                
                # Extract
                result = self.agents['extractor'].execute(pdf_file)
                
                if not result:
                    break
                
                # Generate unique keys
                result = self.agents['key_generator'].execute(result)
                
                # Validate
                is_valid, score, validation_results = self.agents['validator'].execute(result)
                result.extraction_iterations = iteration + 1
                
                if score > best_score:
                    best_score = score
                    best_result = copy.deepcopy(result)
                
                if is_valid and score >= 0.85:
                    self.log(f"✨ Extraction successful with {score:.0%} confidence!", "success")
                    break
                
                if iteration < self.max_iterations - 1:
                    self.log(f"Current score {score:.0%} - can improve further...", "warning")
                    # Could add logic here to guide next iteration based on validation results
            
            if not best_result:
                self.log("Extraction failed", "error")
                return None
            
            # Phase 2: Database Mapping
            self.log("\n🔗 Phase 2: Database Mapping")
            mapped_result = self.agents['mapper'].execute(best_result, manual_mappings)
            
            # Phase 3: Prepare output
            output = self._prepare_output(mapped_result)
            
            self.log("✅ Pipeline completed successfully!", "success")
            
            # Store in session for UI access
            if hasattr(st, 'session_state'):
                st.session_state.extraction_result = mapped_result
                st.session_state.pipeline_output = output
            
            return output
            
        except Exception as e:
            self.log(f"Pipeline failed: {str(e)}", "error")
            raise
    
    def _prepare_output(self, result: FormExtractionResult) -> Dict[str, Any]:
        """Prepare final output"""
        parts_data = {}
        
        for part_num, part in result.parts.items():
            part_fields = []
            
            # Process root fields with hierarchy
            for root_field in sorted(part.root_fields, key=lambda f: self._parse_item_number(f.item_number)):
                field_data = self._field_to_dict(root_field)
                part_fields.append(field_data)
            
            parts_data[f"part_{part_num}"] = {
                'number': part_num,
                'title': part.part_title,
                'page_range': f"{part.start_page}-{part.end_page}" if part.start_page != part.end_page else str(part.start_page),
                'fields': part_fields,
                'total_fields': len(part.get_all_fields_flat())
            }
        
        return {
            'form_info': {
                'number': result.form_number,
                'title': result.form_title,
                'total_fields': result.total_fields,
                'confidence_score': result.confidence_score,
                'extraction_iterations': result.extraction_iterations
            },
            'parts': parts_data,
            'mappings': {
                'mapped': result.field_mappings,
                'manual': result.manual_mappings,
                'suggested': result.suggested_mappings
            },
            'statistics': {
                'total_parts': len(result.parts),
                'total_fields': result.total_fields,
                'duplicates_prevented': result.duplicate_count,
                'mapped_fields': len(result.field_mappings),
                'confidence_score': result.confidence_score
            }
        }
    
    def _field_to_dict(self, field: FieldNode) -> Dict:
        """Convert field to dictionary with hierarchy"""
        data = {
            'item_number': field.item_number,
            'label': field.label,
            'value': field.value,
            'type': field.field_type.value,
            'confidence': field.confidence.value,
            'page': field.page,
            'mapping_status': field.mapping_status.value,
            'mapped_to': field.mapped_to
        }
        
        # Add checkbox options if any
        if field.checkbox_options:
            data['checkbox_options'] = [
                {
                    'text': opt.text,
                    'selected': opt.is_selected
                }
                for opt in field.checkbox_options
            ]
        
        # Add children recursively
        if field.children:
            data['children'] = []
            for child in sorted(field.children, key=lambda f: self._parse_item_number(f.item_number)):
                data['children'].append(self._field_to_dict(child))
        
        return data
    
    def _parse_item_number(self, item_num: str) -> Tuple:
        """Parse item number for sorting"""
        # Match patterns like "1", "1a", "1a1"
        match = re.match(r'^(\d+)([a-z]?)(\d*)$', item_num)
        if match:
            main = int(match.group(1))
            sub = match.group(2) or ''
            nested = int(match.group(3)) if match.group(3) else 0
            return (main, sub, nested)
        return (999, '', 0)

# ===== UI COMPONENTS =====
def display_form_parts(result: FormExtractionResult):
    """Display form parts with hierarchy"""
    if not result:
        st.info("No extraction results available")
        return
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Fields", result.total_fields)
    
    with col2:
        st.metric("Parts", len(result.parts))
    
    with col3:
        st.metric("Confidence", f"{result.confidence_score:.0%}")
    
    with col4:
        mapped = len(result.field_mappings)
        st.metric("Mapped", f"{mapped}/{result.total_fields}")
    
    # Display each part
    for part_num in sorted(result.parts.keys()):
        part = result.parts[part_num]
        
        # Part header
        st.markdown(
            f'<div class="part-header">'
            f'Part {part_num}: {part.part_title} '
            f'(Pages {part.start_page}-{part.end_page}, '
            f'{len(part.get_all_fields_flat())} fields)'
            f'</div>',
            unsafe_allow_html=True
        )
        
        # Display root fields with hierarchy
        for i, root_field in enumerate(sorted(part.root_fields, key=lambda f: int(f.item_number) if f.item_number.isdigit() else 999)):
            display_field_hierarchical(root_field, level=0, parent_path=f"part{part_num}_field{i}")

def display_field_hierarchical(field: FieldNode, level: int = 0, parent_path: str = ""):
    """Display field with its hierarchy"""
    indent = "  " * level
    
    # Create unique path for this field instance
    field_path = f"{parent_path}_{field.key}" if parent_path else field.key
    
    with st.container():
        cols = st.columns([4, 2, 2, 1])
        
        with cols[0]:
            # Field number and label
            st.markdown(f"{indent}**{field.item_number}.** {field.label}")
            
            # Show checkbox options if any
            if field.checkbox_options:
                option_html = ""
                for i, opt in enumerate(field.checkbox_options):
                    css_class = "checkbox-selected" if opt.is_selected else ""
                    option_html += f'<span class="checkbox-option {css_class}">{opt.text}</span>'
                st.markdown(option_html, unsafe_allow_html=True)
        
        with cols[1]:
            # Value input with unique key based on field path
            value_key = f"value_{field_path}_{id(field)}"  # Added id(field) for absolute uniqueness
            try:
                new_value = st.text_input(
                    "Value",
                    value=field.value,
                    key=value_key,
                    label_visibility="collapsed"
                )
                if new_value != field.value:
                    field.value = new_value
            except Exception as e:
                # Fallback if still duplicate
                st.text(f"Value: {field.value}")
        
        with cols[2]:
            # Mapping status
            if field.mapping_status == MappingStatus.MAPPED:
                st.success(f"→ {field.mapped_to}")
            elif field.mapping_status == MappingStatus.MANUAL:
                st.info(f"→ {field.mapped_to}")
            elif field.mapping_status == MappingStatus.SUGGESTED and field.suggested_mappings:
                st.warning(f"→ {field.suggested_mappings[0][0]} ({field.suggested_mappings[0][1]:.0%})")
            else:
                st.error("Unmapped")
        
        with cols[3]:
            # Field type
            type_emoji = {
                FieldType.NAME: "👤",
                FieldType.DATE: "📅",
                FieldType.NUMBER: "🔢",
                FieldType.ADDRESS: "📍",
                FieldType.EMAIL: "📧",
                FieldType.PHONE: "📞",
                FieldType.CHECKBOX: "☑️",
                FieldType.SIGNATURE: "✍️"
            }
            st.markdown(f"{type_emoji.get(field.field_type, '📝')} {field.field_type.value}")
    
    # Display children
    for child in field.children:
        display_field_hierarchical(child, level + 1, field_path)

def display_questionnaire_mode():
    """Display questionnaire for manual entry"""
    st.markdown("### 📝 Questionnaire Mode")
    
    # Common USCIS form questions
    questions = {
        "Part 1": [
            ("1", "Family Name (Last Name)", "text", "personal_info.last_name"),
            ("1a", "Given Name (First Name)", "text", "personal_info.first_name"),
            ("1b", "Middle Name", "text", "personal_info.middle_name"),
            ("2", "Date of Birth", "date", "personal_info.date_of_birth"),
            ("3", "Country of Birth", "text", "personal_info.country_of_birth"),
            ("4", "Country of Citizenship or Nationality", "text", "personal_info.nationality"),
        ],
        "Part 2": [
            ("5", "Alien Registration Number (A-Number)", "text", "identification.alien_number"),
            ("6", "USCIS Online Account Number", "text", "identification.uscis_number"),
            ("7", "U.S. Social Security Number", "text", "identification.social_security_number"),
        ]
    }
    
    responses = {}
    
    for part_name, part_questions in questions.items():
        st.markdown(f"#### {part_name}")
        
        for item_num, question, field_type, db_field in part_questions:
            key = f"q_{item_num}"
            
            if field_type == "text":
                value = st.text_input(f"{item_num}. {question}", key=key)
            elif field_type == "date":
                value = st.date_input(f"{item_num}. {question}", key=key, value=None)
            
            if value:
                responses[item_num] = {
                    'value': str(value),
                    'db_field': db_field
                }
    
    if st.button("💾 Save Responses", type="primary"):
        st.success("✅ Responses saved!")
        st.json(responses)

# ===== MAIN APPLICATION =====
def main():
    st.markdown(
        '<div class="main-header">'
        '<h1>🤖 Agentic USCIS Form Reader</h1>'
        '<p>Improved extraction with proper hierarchy and part handling</p>'
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
        - ✅ Part-by-part extraction
        - ✅ Handles parts across pages
        - ✅ Hierarchical fields (1, 1a, 1b)
        - ✅ Checkbox content extraction
        - ✅ Iterative refinement
        - ✅ Database mapping
        """)
    
    # Main content tabs
    tabs = st.tabs([
        "📄 Upload & Extract",
        "📊 Review Fields",
        "🔗 Database Mapping",
        "📝 Questionnaire",
        "💾 Export Results"
    ])
    
    # Tab 1: Upload & Extract
    with tabs[0]:
        st.markdown("### 📄 Upload USCIS Form")
        
        uploaded_file = st.file_uploader(
            "Choose a PDF form",
            type=['pdf'],
            help="Upload any USCIS form (I-90, I-130, I-485, etc.)"
        )
        
        if uploaded_file:
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.success(f"✅ Uploaded: {uploaded_file.name}")
            
            with col2:
                if st.button("🚀 Process Form", type="primary", use_container_width=True):
                    # Create agent activity container
                    if show_agent_logs:
                        st.markdown("### 🤖 Agent Activity")
                        agent_container = st.container()
                        st.session_state.agent_container = agent_container
                    
                    with st.spinner("Processing form..."):
                        # Create coordinator
                        coordinator = ImprovedMasterCoordinator()
                        
                        # Execute pipeline
                        output = coordinator.execute(
                            uploaded_file,
                            st.session_state.manual_mappings
                        )
                        
                        if output:
                            st.success("✅ Form processed successfully!")
                            st.balloons()
    
    # Tab 2: Review Fields
    with tabs[1]:
        st.markdown("### 📊 Review Extracted Fields")
        
        if st.session_state.extraction_result:
            display_form_parts(st.session_state.extraction_result)
        else:
            st.info("No extraction results. Please process a form first.")
    
    # Tab 3: Database Mapping
    with tabs[2]:
        st.markdown("### 🔗 Configure Database Mapping")
        
        if st.session_state.extraction_result:
            result = st.session_state.extraction_result
            
            # Show unmapped fields
            unmapped_fields = []
            for part in result.parts.values():
                for field in part.get_all_fields_flat():
                    if field.mapping_status == MappingStatus.UNMAPPED:
                        unmapped_fields.append(field)
            
            if unmapped_fields:
                st.warning(f"📌 {len(unmapped_fields)} fields need mapping")
                
                # Manual mapping interface
                for field in unmapped_fields[:10]:  # Show first 10
                    with st.expander(f"{field.item_number}. {field.label}"):
                        db_options = ["-- Select --"]
                        agent = DatabaseMappingAgent()
                        for category, fields in agent.db_schema.items():
                            for db_field in fields:
                                db_options.append(f"{category}.{db_field}")
                        
                        selected = st.selectbox(
                            "Map to:",
                            db_options,
                            key=f"map_{field.key}_{id(field)}"  # Added id() for uniqueness
                        )
                        
                        if selected != "-- Select --":
                            st.session_state.manual_mappings[field.key] = selected
                
                if st.button("💾 Apply Mappings", type="primary"):
                    # Re-run mapping
                    agent = DatabaseMappingAgent()
                    agent.execute(result, st.session_state.manual_mappings)
                    st.success("Mappings applied!")
                    st.rerun()
            else:
                st.success("✅ All fields are mapped!")
        else:
            st.info("No extraction results. Please process a form first.")
    
    # Tab 4: Questionnaire
    with tabs[3]:
        display_questionnaire_mode()
    
    # Tab 5: Export
    with tabs[4]:
        st.markdown("### 💾 Export Results")
        
        if st.session_state.pipeline_output:
            output = st.session_state.pipeline_output
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # JSON export
                json_str = json.dumps(output, indent=2)
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
                                'Mapped To': field.get('mapped_to', '')
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
                # Preview
                with st.expander("👁️ Preview Data"):
                    st.json(output)
        else:
            st.info("No results to export. Please process a form first.")

if __name__ == "__main__":
    if not PYMUPDF_AVAILABLE:
        st.error("❌ PyMuPDF is required but not installed!")
        st.code("pip install PyMuPDF")
        st.stop()
    
    main()
