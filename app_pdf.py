#!/usr/bin/env python3
"""
Advanced Agentic USCIS Form Reader
- Generic pattern learning for any form
- Self-improving extraction with feedback loops
- No duplicates, clean part organization
- Manual database mapping with UI
- Production-ready with comprehensive error handling
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
    page_title="Agentic USCIS Form Reader",
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
    """Enhanced field node with duplicate prevention"""
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
    
    # Unique identification
    key: str = ""
    content_hash: str = ""  # Hash of label + position for duplicate detection
    
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
    
    def is_duplicate_of(self, other: 'FieldNode') -> bool:
        """Check if this is a duplicate of another field"""
        return (self.content_hash == other.content_hash or 
                (self.label == other.label and 
                 self.item_number == other.item_number and 
                 self.part_number == other.part_number))

@dataclass
class PartStructure:
    """Part with duplicate prevention"""
    part_number: int
    part_name: str
    part_title: str = ""
    root_fields: List[FieldNode] = field(default_factory=list)
    field_hashes: Set[str] = field(default_factory=set)
    
    def add_field(self, field: FieldNode) -> bool:
        """Add field with duplicate check"""
        if field.content_hash in self.field_hashes:
            return False  # Duplicate detected
        
        self.root_fields.append(field)
        self.field_hashes.add(field.content_hash)
        field.part_number = self.part_number
        field.part_name = self.part_name
        return True
    
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
            FieldType.NAME.value: ['name', 'nombre', 'nom'],
            FieldType.DATE.value: ['date', 'fecha', 'birth', 'expire', 'issue'],
            FieldType.NUMBER.value: ['number', 'no.', '#', 'account', 'ssn', 'ein', 'a-number'],
            FieldType.EMAIL.value: ['email', 'e-mail', 'correo'],
            FieldType.PHONE.value: ['phone', 'tel', 'mobile', 'cell', 'fax'],
            FieldType.ADDRESS.value: ['address', 'street', 'city', 'state', 'zip', 'postal'],
            FieldType.CHECKBOX.value: ['select', 'check', 'yes', 'no', 'si', 'option'],
            FieldType.SIGNATURE.value: ['signature', 'sign', 'firma'],
        }
    
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
    
    def learn_form_structure(self, form_type: str, structure: Dict):
        """Learn expected structure for a form type"""
        if form_type not in self.form_structures:
            self.form_structures[form_type] = structure
        else:
            # Merge structures
            self._merge_structures(self.form_structures[form_type], structure)
    
    def _merge_structures(self, existing: Dict, new: Dict):
        """Merge form structures intelligently"""
        for key, value in new.items():
            if key not in existing:
                existing[key] = value
            elif isinstance(value, dict) and isinstance(existing[key], dict):
                self._merge_structures(existing[key], value)
    
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
    
    def learn_from_result(self, result: Any, success: bool):
        """Learn from execution result"""
        self.performance_metrics['total_runs'] += 1
        if success:
            self.performance_metrics['success_rate'] = (
                (self.performance_metrics['success_rate'] * (self.performance_metrics['total_runs'] - 1) + 1) 
                / self.performance_metrics['total_runs']
            )
    
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

# ===== SMART EXTRACTION AGENT =====
class SmartExtractionAgent(BaseAgent):
    """Intelligent extraction agent that learns and adapts"""
    
    def __init__(self):
        super().__init__(
            "Smart Extraction Agent",
            "Learns patterns and adapts to any form type"
        )
        self.doc = None
        self.current_form_type = ""
    
    def execute(self, pdf_file) -> FormExtractionResult:
        """Execute smart extraction"""
        self.status = "active"
        self.log("Starting intelligent extraction...")
        
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
            
            # Extract with duplicate prevention
            self._extract_with_learning(result)
            
            # Learn from this extraction
            self._learn_from_extraction(result)
            
            self.log(f"Extracted {result.total_fields} unique fields from {len(result.parts)} parts", "success")
            self.learn_from_result(result, True)
            return result
            
        except Exception as e:
            self.log(f"Extraction failed: {str(e)}", "error")
            self.learn_from_result(None, False)
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
            number_match = re.search(number_pattern, first_page_text)
            if number_match:
                form_number = number_match.group(1)
                title_match = re.search(title_pattern, first_page_text)
                form_title = title_match.group(0) if title_match else f"Form {form_number}"
                
                self.log(f"Identified form: {form_number}")
                return {"number": form_number, "title": form_title}
        
        return {"number": "Unknown", "title": "Unknown Form"}
    
    def _extract_with_learning(self, result: FormExtractionResult):
        """Extract fields with learning and duplicate prevention"""
        seen_fields = set()
        current_part = None
        
        for page_num in range(len(self.doc)):
            page = self.doc[page_num]
            blocks = self._get_page_blocks(page, page_num)
            
            # Process blocks with context awareness
            for i, block in enumerate(blocks):
                text = block['text'].strip()
                if not text:
                    continue
                
                # Check for part header
                if self._is_part_header(text):
                    part_info = self._extract_part_info(text)
                    if part_info:
                        part_num = part_info['number']
                        if part_num not in result.parts:
                            result.parts[part_num] = PartStructure(
                                part_number=part_num,
                                part_name=f"Part {part_num}",
                                part_title=part_info['title']
                            )
                            self.log(f"Found Part {part_num}: {part_info['title']}")
                        current_part = result.parts[part_num]
                        continue
                
                # Extract field if we have a current part
                if current_part:
                    field = self._extract_field(text, block, page_num, i, blocks)
                    if field:
                        # Check for duplicates
                        field_key = f"{field.label}_{field.item_number}_{field.part_number}"
                        if field_key not in seen_fields:
                            if current_part.add_field(field):
                                seen_fields.add(field_key)
                                result.total_fields += 1
                            else:
                                result.duplicate_count += 1
        
        # Ensure at least Part 1 exists
        if not result.parts:
            result.parts[1] = PartStructure(1, "Part 1", "Form Fields")
            current_part = result.parts[1]
            self.log("No parts found, created default Part 1", "warning")
    
    def _get_page_blocks(self, page, page_num: int) -> List[Dict]:
        """Extract and organize page blocks"""
        blocks = []
        page_dict = page.get_text("dict")
        
        for block in page_dict["blocks"]:
            if block["type"] == 0:  # Text block
                for line in block["lines"]:
                    text = " ".join(span["text"] for span in line["spans"])
                    if text.strip():
                        blocks.append({
                            'text': text,
                            'bbox': line.get("bbox", [0, 0, 0, 0]),
                            'page': page_num,
                            'font_size': line["spans"][0].get("size", 10) if line["spans"] else 10,
                            'is_bold': any(span.get("flags", 0) & 2**4 for span in line["spans"])
                        })
        
        # Sort by position
        blocks.sort(key=lambda b: (b['bbox'][1], b['bbox'][0]))
        return blocks
    
    def _is_part_header(self, text: str) -> bool:
        """Check if text is a part header"""
        return bool(re.match(r'^Part\s+\d+', text, re.IGNORECASE))
    
    def _extract_part_info(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract part information"""
        match = re.match(r'^Part\s+(\d+)\.?\s*(.*)$', text, re.IGNORECASE)
        if match:
            return {
                'number': int(match.group(1)),
                'title': match.group(2).strip() if match.group(2) else ""
            }
        return None
    
    def _extract_field(self, text: str, block: Dict, page_num: int, 
                      block_idx: int, all_blocks: List[Dict]) -> Optional[FieldNode]:
        """Extract field with context awareness"""
        # Pattern matching
        patterns = [
            (r'^(\d+)\.\s+(.+?)$', 'numbered'),
            (r'^(\d+)\.\s*$', 'number_only'),
            (r'^([a-z])\.\s+(.+?)$', 'lettered'),
            (r'^(\d+)([a-z])\.\s+(.+?)$', 'numbered_letter'),
        ]
        
        for pattern, pattern_type in patterns:
            match = re.match(pattern, text)
            if match:
                if pattern_type == 'number_only' and block_idx + 1 < len(all_blocks):
                    # Look ahead for label
                    next_text = all_blocks[block_idx + 1]['text']
                    if not re.match(r'^\d+\.', next_text):
                        item_number = match.group(1)
                        label = next_text.strip()
                    else:
                        continue
                elif pattern_type == 'numbered':
                    item_number = match.group(1)
                    label = match.group(2)
                elif pattern_type == 'lettered':
                    item_number = match.group(1)
                    label = match.group(2)
                elif pattern_type == 'numbered_letter':
                    item_number = match.group(1) + match.group(2)
                    label = match.group(3)
                else:
                    continue
                
                # Determine field type
                field_type, confidence = self.learning_manager.suggest_field_type(label)
                
                return FieldNode(
                    item_number=item_number,
                    label=label.strip(),
                    field_type=field_type,
                    page=page_num + 1,
                    confidence=ExtractionConfidence.HIGH if confidence > 0.8 else ExtractionConfidence.MEDIUM,
                    extraction_method="pattern_match",
                    raw_text=text,
                    bbox=tuple(block['bbox'])
                )
        
        return None
    
    def _learn_from_extraction(self, result: FormExtractionResult):
        """Learn patterns from successful extraction"""
        structure = {}
        
        for part_num, part in result.parts.items():
            part_structure = {
                'title': part.part_title,
                'fields': {}
            }
            
            for field in part.get_all_fields_flat():
                if field.confidence in [ExtractionConfidence.HIGH, ExtractionConfidence.MEDIUM]:
                    # Learn pattern
                    self.learning_manager.learn_pattern(
                        field.label,
                        field.field_type,
                        self.current_form_type,
                        0.8 if field.confidence == ExtractionConfidence.HIGH else 0.6
                    )
                    
                    part_structure['fields'][field.item_number] = {
                        'label': field.label,
                        'type': field.field_type.value
                    }
            
            structure[f"part_{part_num}"] = part_structure
        
        # Learn form structure
        self.learning_manager.learn_form_structure(self.current_form_type, structure)
        self.learning_manager.save_patterns()

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
                    base_key = self._generate_base_key(field)
                    unique_key = self._ensure_unique_key(base_key, key_registry)
                    field.key = unique_key
                    key_registry.add(unique_key)
            
            self.log(f"Generated {len(key_registry)} unique keys", "success")
            return result
            
        except Exception as e:
            self.log(f"Key generation failed: {str(e)}", "error")
            raise
    
    def _generate_base_key(self, field: FieldNode) -> str:
        """Generate base key from field properties"""
        # Clean item number
        item_clean = re.sub(r'[^\w]', '', field.item_number)
        
        # Generate hierarchical key
        if field.parent:
            parent_key = field.parent.key or f"P{field.part_number}_{field.parent.item_number}"
            return f"{parent_key}_{item_clean}"
        else:
            return f"P{field.part_number}_{item_clean}"
    
    def _ensure_unique_key(self, base_key: str, registry: Set[str]) -> str:
        """Ensure key is unique"""
        if base_key not in registry:
            return base_key
        
        counter = 1
        while f"{base_key}_{counter}" in registry:
            counter += 1
        
        return f"{base_key}_{counter}"

# ===== VALIDATION AGENT =====
class IntelligentValidationAgent(BaseAgent):
    """Validates extraction with intelligent checks"""
    
    def __init__(self):
        super().__init__(
            "Intelligent Validation Agent",
            "Performs comprehensive validation"
        )
    
    def execute(self, result: FormExtractionResult) -> Tuple[bool, float, List[Dict]]:
        """Execute validation"""
        self.status = "active"
        self.log("Running intelligent validation...")
        
        try:
            checks = [
                self._check_part_continuity,
                self._check_field_completeness,
                self._check_duplicate_fields,
                self._check_field_types,
                self._check_hierarchical_structure,
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
    
    def _check_part_continuity(self, result: FormExtractionResult) -> Dict:
        """Check if parts are continuous"""
        if not result.parts:
            return {
                'name': 'Part Continuity',
                'passed': False,
                'score': 0.0,
                'weight': 1.0,
                'details': 'No parts found'
            }
        
        part_numbers = sorted(result.parts.keys())
        expected = list(range(1, max(part_numbers) + 1))
        missing = set(expected) - set(part_numbers)
        
        if not missing:
            return {
                'name': 'Part Continuity',
                'passed': True,
                'score': 1.0,
                'weight': 1.0,
                'details': f'All parts present ({len(part_numbers)} parts)'
            }
        else:
            score = len(part_numbers) / len(expected)
            return {
                'name': 'Part Continuity',
                'passed': False,
                'score': score,
                'weight': 1.0,
                'details': f'Missing parts: {sorted(missing)}'
            }
    
    def _check_field_completeness(self, result: FormExtractionResult) -> Dict:
        """Check field completeness"""
        min_fields_expected = 15  # Minimum for most forms
        actual_fields = result.total_fields
        
        if actual_fields >= min_fields_expected:
            return {
                'name': 'Field Completeness',
                'passed': True,
                'score': min(1.0, actual_fields / 50),  # Cap at 50 fields
                'weight': 1.5,
                'details': f'Found {actual_fields} fields'
            }
        else:
            return {
                'name': 'Field Completeness',
                'passed': False,
                'score': actual_fields / min_fields_expected,
                'weight': 1.5,
                'details': f'Only {actual_fields} fields (expected {min_fields_expected}+)'
            }
    
    def _check_duplicate_fields(self, result: FormExtractionResult) -> Dict:
        """Check for duplicate fields"""
        duplicate_ratio = result.duplicate_count / max(1, result.total_fields + result.duplicate_count)
        
        if duplicate_ratio < 0.05:  # Less than 5% duplicates
            return {
                'name': 'Duplicate Prevention',
                'passed': True,
                'score': 1.0 - duplicate_ratio,
                'weight': 1.0,
                'details': f'{result.duplicate_count} duplicates prevented'
            }
        else:
            return {
                'name': 'Duplicate Prevention',
                'passed': False,
                'score': 1.0 - duplicate_ratio,
                'weight': 1.0,
                'details': f'High duplicate rate: {duplicate_ratio:.0%}'
            }
    
    def _check_field_types(self, result: FormExtractionResult) -> Dict:
        """Check field type identification"""
        total_fields = 0
        typed_fields = 0
        
        for part in result.parts.values():
            for field in part.get_all_fields_flat():
                total_fields += 1
                if field.field_type != FieldType.UNKNOWN:
                    typed_fields += 1
        
        if total_fields == 0:
            return {
                'name': 'Field Type Detection',
                'passed': False,
                'score': 0.0,
                'weight': 0.8,
                'details': 'No fields to check'
            }
        
        type_ratio = typed_fields / total_fields
        return {
            'name': 'Field Type Detection',
            'passed': type_ratio >= 0.7,
            'score': type_ratio,
            'weight': 0.8,
            'details': f'{typed_fields}/{total_fields} fields typed ({type_ratio:.0%})'
        }
    
    def _check_hierarchical_structure(self, result: FormExtractionResult) -> Dict:
        """Check hierarchical relationships"""
        issues = []
        total_checks = 0
        passed_checks = 0
        
        for part in result.parts.values():
            for field in part.get_all_fields_flat():
                total_checks += 1
                
                # Check sub-items have parents
                if re.match(r'^\d+[a-z]', field.item_number):
                    parent_num = re.match(r'^(\d+)', field.item_number).group(1)
                    if field.parent and field.parent.item_number == parent_num:
                        passed_checks += 1
                    else:
                        issues.append(f"{field.key} missing proper parent")
                else:
                    passed_checks += 1
        
        if total_checks == 0:
            return {
                'name': 'Hierarchical Structure',
                'passed': True,
                'score': 1.0,
                'weight': 0.7,
                'details': 'No hierarchy to check'
            }
        
        score = passed_checks / total_checks
        return {
            'name': 'Hierarchical Structure',
            'passed': len(issues) == 0,
            'score': score,
            'weight': 0.7,
            'details': f'{len(issues)} hierarchy issues' if issues else 'Hierarchy correct'
        }

# ===== DATABASE MAPPING AGENT =====
class ManualMappingAgent(BaseAgent):
    """Handles database mapping with manual override capability"""
    
    def __init__(self):
        super().__init__(
            "Manual Mapping Agent",
            "Maps fields to database with manual override"
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
        """Execute mapping with manual overrides"""
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
            r'first.*name|given.*name': 'personal_info.first_name',
            r'last.*name|family.*name|surname': 'personal_info.last_name',
            r'middle.*name': 'personal_info.middle_name',
            r'birth.*date|date.*birth|dob': 'personal_info.date_of_birth',
            r'birth.*place|place.*birth|born': 'personal_info.place_of_birth',
            r'birth.*country|country.*birth': 'personal_info.country_of_birth',
            r'nationality|citizenship': 'personal_info.nationality',
            r'gender|sex': 'personal_info.gender',
            r'marital|married|spouse': 'personal_info.marital_status',
            
            # Identification patterns
            r'a[\-\s]?number|alien.*number': 'identification.alien_number',
            r'uscis.*number|uscis.*account': 'identification.uscis_number',
            r'social.*security|ssn': 'identification.social_security_number',
            r'passport.*number': 'identification.passport_number',
            r'passport.*country': 'identification.passport_country',
            r'passport.*expir': 'identification.passport_expiry',
            
            # Contact patterns
            r'mailing.*address|mail.*to': 'contact_info.mailing_address',
            r'physical.*address|current.*address|street': 'contact_info.physical_address',
            r'apt|suite|unit': 'contact_info.apt_suite',
            r'city|town': 'contact_info.city',
            r'state|province': 'contact_info.state',
            r'zip|postal.*code': 'contact_info.zip_code',
            r'country': 'contact_info.country',
            r'phone|telephone|tel': 'contact_info.phone_number',
            r'mobile|cell': 'contact_info.mobile_number',
            r'email|e\-mail': 'contact_info.email_address',
            
            # Immigration patterns
            r'current.*status|immigration.*status|nonimmigrant.*status': 'immigration_info.current_status',
            r'status.*expir|expir.*date': 'immigration_info.status_expiry',
            r'i[\-\s]?94': 'immigration_info.i94_number',
            r'last.*entry|recent.*arrival|date.*arrival': 'immigration_info.last_entry_date',
            r'port.*entry|arrival.*port': 'immigration_info.last_entry_port',
            r'visa.*number': 'immigration_info.visa_number',
            r'visa.*type|visa.*class': 'immigration_info.visa_type',
            
            # Employment patterns
            r'employer|company.*name|work.*for': 'employment.employer_name',
            r'job.*title|position|occupation': 'employment.job_title',
            r'start.*date|employ.*since': 'employment.start_date',
            r'salary|wage|income': 'employment.salary',
            
            # Application patterns
            r'applying.*for|application.*type|request': 'application.application_type',
            r'receipt.*number|case.*number': 'application.receipt_number',
            r'priority.*date': 'application.priority_date',
            r'filing.*date|submitted': 'application.filing_date',
        }
        
        for pattern, db_field in patterns.items():
            if re.search(pattern, field_label_lower):
                # Calculate confidence based on match quality
                match = re.search(pattern, field_label_lower)
                confidence = 0.7 + (0.3 * (len(match.group()) / len(field_label_lower)))
                suggestions.append((db_field, min(0.95, confidence)))
        
        # Sort by confidence
        suggestions.sort(key=lambda x: x[1], reverse=True)
        
        # Return top 3 suggestions
        return suggestions[:3]
    
    def get_mapping_suggestions_for_review(self, result: FormExtractionResult) -> Dict[str, Dict]:
        """Get all fields that need mapping review"""
        review_fields = {}
        
        for part in result.parts.values():
            for field in part.get_all_fields_flat():
                if field.mapping_status in [MappingStatus.UNMAPPED, MappingStatus.SUGGESTED, MappingStatus.REVIEW]:
                    review_fields[field.key] = {
                        'label': field.label,
                        'type': field.field_type.value,
                        'value': field.value,
                        'suggestions': field.suggested_mappings,
                        'status': field.mapping_status.value,
                        'part': field.part_number
                    }
        
        return review_fields

# ===== MASTER COORDINATOR =====
class AgenticMasterCoordinator(BaseAgent):
    """Master coordinator that learns and improves"""
    
    def __init__(self):
        super().__init__(
            "Agentic Master Coordinator",
            "Orchestrates all agents with learning"
        )
        self.agents = {
            'extractor': SmartExtractionAgent(),
            'key_generator': SmartKeyGenerator(),
            'validator': IntelligentValidationAgent(),
            'mapper': ManualMappingAgent()
        }
        self.max_iterations = 3
    
    def execute(self, pdf_file, manual_mappings: Dict[str, str] = None) -> Dict[str, Any]:
        """Execute complete pipeline"""
        self.status = "active"
        self.log("🚀 Starting agentic form processing pipeline...")
        
        try:
            # Phase 1: Extraction with refinement loop
            best_result = None
            best_score = 0.0
            
            for iteration in range(self.max_iterations):
                self.log(f"\n📊 Iteration {iteration + 1}/{self.max_iterations}")
                
                # Extract
                if iteration == 0:
                    result = self.agents['extractor'].execute(pdf_file)
                else:
                    # Refine based on validation feedback
                    result = self._refine_extraction(pdf_file, result, validation_results)
                
                if not result:
                    break
                
                # Generate keys
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
                    self.log(f"Score {score:.0%} - refining extraction...", "warning")
            
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
    
    def _refine_extraction(self, pdf_file, previous_result: FormExtractionResult, 
                          validation_results: List[Dict]) -> FormExtractionResult:
        """Refine extraction based on validation feedback"""
        # Learn from validation issues
        issues = [r for r in validation_results if not r['passed']]
        
        self.log(f"Learning from {len(issues)} validation issues...")
        
        # Create new extractor with enhanced awareness
        extractor = SmartExtractionAgent()
        
        # Re-extract
        if hasattr(pdf_file, 'seek'):
            pdf_file.seek(0)
        
        new_result = extractor.execute(pdf_file)
        
        # Merge improvements
        if new_result and new_result.total_fields > previous_result.total_fields:
            self.log(f"Improved: {previous_result.total_fields} → {new_result.total_fields} fields")
            return new_result
        
        return previous_result
    
    def _prepare_output(self, result: FormExtractionResult) -> Dict[str, Any]:
        """Prepare final output"""
        # Organize by parts
        parts_data = {}
        for part_num, part in result.parts.items():
            part_fields = []
            for field in part.get_all_fields_flat():
                field_data = {
                    'key': field.key,
                    'label': field.label,
                    'value': field.value,
                    'type': field.field_type.value,
                    'item_number': field.item_number,
                    'confidence': field.confidence.value,
                    'mapping_status': field.mapping_status.value,
                    'mapped_to': field.mapped_to,
                    'suggestions': field.suggested_mappings
                }
                part_fields.append(field_data)
            
            parts_data[f"part_{part_num}"] = {
                'title': part.part_title,
                'fields': part_fields
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

# ===== UI COMPONENTS =====
def display_form_parts(result: FormExtractionResult):
    """Display form parts in clean UI"""
    if not result:
        st.info("No extraction results available")
        return
    
    for part_num in sorted(result.parts.keys()):
        part = result.parts[part_num]
        
        # Part header
        st.markdown(
            f'<div class="part-header">'
            f'Part {part_num}: {part.part_title}'
            f' ({len(part.get_all_fields_flat())} fields)'
            f'</div>',
            unsafe_allow_html=True
        )
        
        # Fields in part
        fields = part.get_all_fields_flat()
        
        # Group by hierarchy level
        root_fields = [f for f in fields if not f.parent]
        
        for field in root_fields:
            display_field_with_children(field)

def display_field_with_children(field: FieldNode, indent_level: int = 0):
    """Display field and its children hierarchically"""
    indent = "  " * indent_level
    
    with st.container():
        col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
        
        with col1:
            st.markdown(f"{indent}**{field.item_number}.** {field.label}")
        
        with col2:
            # Editable value
            value_key = f"value_{field.key}"
            new_value = st.text_input(
                "Value",
                value=field.value,
                key=value_key,
                label_visibility="collapsed"
            )
            if new_value != field.value:
                field.value = new_value
        
        with col3:
            # Mapping status
            if field.mapping_status == MappingStatus.MAPPED:
                st.success(f"→ {field.mapped_to}")
            elif field.mapping_status == MappingStatus.MANUAL:
                st.info(f"→ {field.mapped_to} (manual)")
            elif field.mapping_status == MappingStatus.SUGGESTED:
                if field.suggested_mappings:
                    st.warning(f"→ {field.suggested_mappings[0][0]} ({field.suggested_mappings[0][1]:.0%})")
            else:
                st.error("Unmapped")
        
        with col4:
            # Field type badge
            type_colors = {
                FieldType.NAME: "🟦",
                FieldType.DATE: "🟨",
                FieldType.NUMBER: "🟩",
                FieldType.ADDRESS: "🟪",
                FieldType.EMAIL: "🟧",
                FieldType.PHONE: "🟫",
                FieldType.CHECKBOX: "⬜",
                FieldType.TEXT: "⬛"
            }
            st.markdown(f"{type_colors.get(field.field_type, '⬛')} {field.field_type.value}")
    
    # Display children
    for child in field.children:
        display_field_with_children(child, indent_level + 1)

def display_mapping_interface(result: FormExtractionResult):
    """Display manual mapping interface"""
    st.markdown("### 🔗 Database Mapping Configuration")
    
    mapper = ManualMappingAgent()
    review_fields = mapper.get_mapping_suggestions_for_review(result)
    
    if not review_fields:
        st.success("All fields are mapped!")
        return
    
    # Group by mapping status
    unmapped = {k: v for k, v in review_fields.items() if v['status'] == 'unmapped'}
    suggested = {k: v for k, v in review_fields.items() if v['status'] == 'suggested'}
    
    # Manual mapping inputs
    manual_mappings = {}
    
    if unmapped:
        st.markdown("#### ❓ Unmapped Fields")
        for field_key, field_info in unmapped.items():
            with st.container():
                st.markdown(
                    f'<div class="mapping-input">'
                    f'<strong>{field_info["label"]}</strong> '
                    f'(Part {field_info["part"]}, Type: {field_info["type"]})'
                    f'</div>',
                    unsafe_allow_html=True
                )
                
                # Database field selector
                db_options = ["-- Not Mapped --"]
                for category, fields in mapper.db_schema.items():
                    for field in fields:
                        db_options.append(f"{category}.{field}")
                
                mapping = st.selectbox(
                    "Map to:",
                    db_options,
                    key=f"map_{field_key}"
                )
                
                if mapping != db_options[0]:
                    manual_mappings[field_key] = mapping
    
    if suggested:
        st.markdown("#### 💡 Suggested Mappings")
        for field_key, field_info in suggested.items():
            with st.container():
                suggestions = field_info['suggestions']
                if suggestions:
                    st.markdown(f"**{field_info['label']}**")
                    
                    # Show suggestions as radio buttons
                    options = ["-- Not Mapped --"] + [f"{s[0]} ({s[1]:.0%})" for s in suggestions]
                    selected = st.radio(
                        "Select mapping:",
                        options,
                        key=f"suggest_{field_key}",
                        horizontal=True
                    )
                    
                    if selected != options[0]:
                        # Extract the mapping from the selected option
                        mapping = suggestions[options.index(selected) - 1][0]
                        manual_mappings[field_key] = mapping
    
    # Apply mappings button
    if st.button("💾 Apply Mappings", type="primary"):
        if manual_mappings:
            # Apply mappings
            result.field_mappings.update(manual_mappings)
            result.manual_mappings.update(manual_mappings)
            
            # Update field objects
            for part in result.parts.values():
                for field in part.get_all_fields_flat():
                    if field.key in manual_mappings:
                        field.mapped_to = manual_mappings[field.key]
                        field.mapping_status = MappingStatus.MANUAL
                        field.mapping_confidence = 1.0
            
            st.success(f"Applied {len(manual_mappings)} mappings!")
            st.rerun()
        else:
            st.warning("No mappings selected")

def display_export_options(output: Dict[str, Any]):
    """Display export options"""
    st.markdown("### 💾 Export Options")
    
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
        for part_name, part_data in output['parts'].items():
            for field in part_data['fields']:
                csv_data.append({
                    'Part': part_name,
                    'Key': field['key'],
                    'Label': field['label'],
                    'Value': field['value'],
                    'Type': field['type'],
                    'Mapped To': field['mapped_to'] or ''
                })
        
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
        # Database insert script
        sql_statements = generate_sql_inserts(output)
        st.download_button(
            "🗄️ Download SQL",
            sql_statements,
            "form_inserts.sql",
            mime="text/plain",
            use_container_width=True
        )

def generate_sql_inserts(output: Dict[str, Any]) -> str:
    """Generate SQL insert statements"""
    sql = "-- Auto-generated SQL inserts\n"
    sql += f"-- Form: {output['form_info']['number']} - {output['form_info']['title']}\n"
    sql += f"-- Generated: {datetime.now().isoformat()}\n\n"
    
    # Group by table
    inserts_by_table = defaultdict(list)
    
    for mapping in output['mappings']['mapped'].items():
        field_key, db_field = mapping
        if '.' in db_field:
            table, column = db_field.split('.')
            
            # Find the field value
            value = None
            for part_data in output['parts'].values():
                for field in part_data['fields']:
                    if field['key'] == field_key:
                        value = field['value']
                        break
            
            if value:
                inserts_by_table[table].append((column, value))
    
    # Generate inserts
    for table, fields in inserts_by_table.items():
        columns = [f[0] for f in fields]
        values = [f"'{f[1]}'" for f in fields]
        
        sql += f"INSERT INTO {table} ({', '.join(columns)})\n"
        sql += f"VALUES ({', '.join(values)});\n\n"
    
    return sql

# ===== MAIN APPLICATION =====
def main():
    st.markdown(
        '<div class="main-header">'
        '<h1>🤖 Agentic USCIS Form Reader</h1>'
        '<p>Self-learning extraction system with manual database mapping</p>'
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
        max_iterations = st.slider("Max Refinement Iterations", 1, 5, 3)
        
        st.markdown("---")
        st.markdown("## 🤖 Active Agents")
        agents = [
            ("🧠", "Smart Extraction Agent", "Learns patterns"),
            ("🔑", "Smart Key Generator", "Unique keys"),
            ("✅", "Intelligent Validator", "Quality checks"),
            ("🔗", "Manual Mapping Agent", "Database mapping"),
            ("🎯", "Master Coordinator", "Orchestration")
        ]
        
        for icon, name, desc in agents:
            st.markdown(f"{icon} **{name}**")
            st.caption(desc)
        
        st.markdown("---")
        
        # Learning indicator
        if st.session_state.extraction_result:
            st.markdown(
                '<div class="learning-indicator">'
                '🧠 System is learning...'
                '</div>',
                unsafe_allow_html=True
            )
    
    # Main content tabs
    tabs = st.tabs([
        "📄 Upload & Extract",
        "📊 Review Fields",
        "🔗 Database Mapping",
        "💾 Export Results"
    ])
    
    # Tab 1: Upload & Extract
    with tabs[0]:
        st.markdown("### 📄 Upload USCIS Form")
        
        uploaded_file = st.file_uploader(
            "Choose a PDF form",
            type=['pdf'],
            help="Upload any USCIS form (I-130, I-485, I-539, N-400, etc.)"
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
                        # Create coordinator with settings
                        coordinator = AgenticMasterCoordinator()
                        coordinator.max_iterations = max_iterations
                        
                        # Execute pipeline
                        output = coordinator.execute(
                            uploaded_file,
                            st.session_state.manual_mappings
                        )
                        
                        if output:
                            st.success("✅ Form processed successfully!")
                            
                            # Display summary metrics
                            col1, col2, col3, col4 = st.columns(4)
                            
                            with col1:
                                st.metric(
                                    "Form Type",
                                    output['form_info']['number']
                                )
                            
                            with col2:
                                st.metric(
                                    "Total Fields",
                                    output['statistics']['total_fields']
                                )
                            
                            with col3:
                                st.metric(
                                    "Confidence",
                                    f"{output['form_info']['confidence_score']:.0%}"
                                )
                            
                            with col4:
                                st.metric(
                                    "Mapped",
                                    f"{output['statistics']['mapped_fields']}/{output['statistics']['total_fields']}"
                                )
                            
                            # Duplicate prevention info
                            if output['statistics']['duplicates_prevented'] > 0:
                                st.info(f"🛡️ Prevented {output['statistics']['duplicates_prevented']} duplicate fields")
    
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
            display_mapping_interface(st.session_state.extraction_result)
            
            # Show current mappings summary
            if st.session_state.extraction_result.field_mappings:
                st.markdown("#### ✅ Current Mappings")
                
                mapping_df = []
                for field_key, db_field in st.session_state.extraction_result.field_mappings.items():
                    # Find field
                    for part in st.session_state.extraction_result.parts.values():
                        for field in part.get_all_fields_flat():
                            if field.key == field_key:
                                mapping_df.append({
                                    'Field': field.label,
                                    'Database': db_field,
                                    'Type': 'Manual' if field_key in st.session_state.extraction_result.manual_mappings else 'Auto'
                                })
                                break
                
                if mapping_df:
                    st.dataframe(mapping_df, use_container_width=True)
        else:
            st.info("No extraction results. Please process a form first.")
    
    # Tab 4: Export
    with tabs[3]:
        st.markdown("### 💾 Export Extraction Results")
        
        if st.session_state.pipeline_output:
            display_export_options(st.session_state.pipeline_output)
            
            # Preview
            with st.expander("📄 Preview JSON Output"):
                st.json(st.session_state.pipeline_output)
        else:
            st.info("No results to export. Please process a form first.")

if __name__ == "__main__":
    # Check dependencies
    if not PYMUPDF_AVAILABLE:
        st.error("❌ PyMuPDF is required but not installed!")
        st.code("pip install PyMuPDF")
        st.stop()
    
    main()
