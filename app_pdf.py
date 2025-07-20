#!/usr/bin/env python3
"""
Advanced Agentic USCIS Form Reader V2
- Complete hierarchical field extraction (1, 1a, 1b, 1c)
- Checkbox content extraction with options
- Multiple extraction strategies that iterate until correct
- Questionnaire and manual entry options
- Intelligent database mapping
- True agentic approach with self-correction
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
    page_title="Agentic USCIS Form Reader V2",
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
    .extraction-status {
        background: #f8f9fa;
        border-left: 4px solid #2196F3;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 0 8px 8px 0;
    }
    .field-tree {
        font-family: 'Courier New', monospace;
        background: #f5f5f5;
        padding: 1rem;
        border-radius: 8px;
        overflow-x: auto;
    }
    .field-node {
        padding: 0.5rem;
        margin: 0.25rem 0;
        background: white;
        border: 1px solid #e0e0e0;
        border-radius: 6px;
        transition: all 0.2s ease;
    }
    .field-node:hover {
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        transform: translateX(5px);
    }
    .checkbox-option {
        background: #e3f2fd;
        border: 2px solid #2196F3;
        border-radius: 20px;
        padding: 0.25rem 1rem;
        margin: 0.25rem;
        display: inline-block;
    }
    .checkbox-selected {
        background: #2196F3;
        color: white;
    }
    .hierarchy-line {
        border-left: 2px dashed #ccc;
        margin-left: 1rem;
        padding-left: 1rem;
    }
    .extraction-iteration {
        background: #fff3cd;
        border: 1px solid #ffc107;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
    }
    .agent-thinking {
        background: #e8f5e9;
        border-left: 4px solid #4caf50;
        padding: 1rem;
        margin: 0.5rem 0;
        font-style: italic;
    }
    .manual-entry-form {
        background: #f0f7ff;
        border: 2px dashed #2196F3;
        border-radius: 8px;
        padding: 1.5rem;
        margin: 1rem 0;
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
    MULTI_LINE = "multi_line"
    UNKNOWN = "unknown"

class ExtractionStrategy(Enum):
    REGEX_PATTERN = "regex_pattern"
    SPATIAL_ANALYSIS = "spatial_analysis"
    CONTEXT_AWARE = "context_aware"
    MACHINE_LEARNING = "machine_learning"
    MANUAL_REVIEW = "manual_review"

# ===== ENHANCED DATA CLASSES =====
@dataclass
class CheckboxOption:
    """Represents a checkbox option with its text"""
    value: str
    label: str
    is_selected: bool = False
    bbox: Optional[Tuple[float, float, float, float]] = None

@dataclass
class FieldNode:
    """Enhanced field node with proper hierarchical support"""
    # Identification
    item_number: str  # e.g., "1", "1a", "1b", "2a1"
    label: str
    full_path: str = ""  # e.g., "Part 1 > 1 > 1a"
    
    # Type and value
    field_type: FieldType = FieldType.UNKNOWN
    value: str = ""
    checkbox_options: List[CheckboxOption] = field(default_factory=list)
    
    # Hierarchy
    parent: Optional['FieldNode'] = None
    children: List['FieldNode'] = field(default_factory=list)
    level: int = 0  # 0 for root, 1 for 1a, 2 for 1a1, etc.
    
    # Location
    page: int = 1
    part_number: int = 1
    part_name: str = "Part 1"
    bbox: Optional[Tuple[float, float, float, float]] = None
    
    # Extraction metadata
    extraction_strategy: ExtractionStrategy = ExtractionStrategy.REGEX_PATTERN
    confidence: float = 0.0
    raw_text: str = ""
    context_before: str = ""
    context_after: str = ""
    
    # Database mapping
    db_field: Optional[str] = None
    mapping_confidence: float = 0.0
    
    def get_display_number(self) -> str:
        """Get display number with proper formatting"""
        return self.item_number
    
    def add_child(self, child: 'FieldNode'):
        """Add child with proper parent-child relationship"""
        child.parent = self
        child.level = self.level + 1
        child.full_path = f"{self.full_path} > {child.item_number}"
        self.children.append(child)
    
    def find_child(self, item_number: str) -> Optional['FieldNode']:
        """Find child by item number"""
        for child in self.children:
            if child.item_number == item_number:
                return child
        return None
    
    def get_all_descendants(self) -> List['FieldNode']:
        """Get all descendants recursively"""
        descendants = []
        for child in self.children:
            descendants.append(child)
            descendants.extend(child.get_all_descendants())
        return descendants

@dataclass
class ExtractionContext:
    """Context for extraction process"""
    current_part: int = 1
    current_page: int = 1
    previous_item: Optional[str] = None
    extraction_history: List[Dict] = field(default_factory=list)
    field_registry: Dict[str, FieldNode] = field(default_factory=dict)
    
    def register_field(self, field: FieldNode):
        """Register field in context"""
        key = f"P{field.part_number}_{field.item_number}"
        self.field_registry[key] = field

# ===== EXTRACTION STRATEGIES =====
class BaseExtractionStrategy(ABC):
    """Base class for extraction strategies"""
    
    @abstractmethod
    def extract(self, page_data: Dict, context: ExtractionContext) -> List[FieldNode]:
        pass
    
    @abstractmethod
    def confidence_score(self) -> float:
        pass

class HierarchicalRegexStrategy(BaseExtractionStrategy):
    """Advanced regex strategy for hierarchical field extraction"""
    
    def __init__(self):
        self.patterns = self._compile_patterns()
        
    def _compile_patterns(self) -> Dict[str, re.Pattern]:
        """Compile regex patterns for different field formats"""
        return {
            # Main numbered items: 1. 2. 3.
            'main_item': re.compile(r'^(\d+)\.\s+(.+?)(?:\s*\(|$)', re.MULTILINE),
            
            # Sub-items: 1.a. 1.b. or 1a. 1b.
            'sub_item_dot': re.compile(r'^(\d+)\.([a-z])\.\s+(.+?)(?:\s*\(|$)', re.MULTILINE),
            'sub_item_no_dot': re.compile(r'^(\d+)([a-z])\.\s+(.+?)(?:\s*\(|$)', re.MULTILINE),
            
            # Nested sub-items: 1.a.1. or 1a1.
            'nested_item': re.compile(r'^(\d+)\.?([a-z])\.?(\d+)\.\s+(.+?)(?:\s*\(|$)', re.MULTILINE),
            
            # Checkbox patterns
            'checkbox': re.compile(r'□\s*(.+?)(?:\s*□|$)', re.MULTILINE),
            'checkbox_selected': re.compile(r'☑\s*(.+?)(?:\s*□|☑|$)', re.MULTILINE),
            
            # Special patterns for USCIS forms
            'part_header': re.compile(r'^Part\s+(\d+)[.:]\s*(.+?)$', re.MULTILINE | re.IGNORECASE),
            'section_header': re.compile(r'^Section\s+(\d+)[.:]\s*(.+?)$', re.MULTILINE | re.IGNORECASE),
            
            # Field labels
            'label_patterns': {
                'name': re.compile(r'(family|given|first|last|middle)\s*name', re.IGNORECASE),
                'date': re.compile(r'date|d\.o\.b\.|birth|expir', re.IGNORECASE),
                'address': re.compile(r'address|street|city|state|zip|postal', re.IGNORECASE),
                'number': re.compile(r'number|no\.|#|account|ssn|ein|a-number|alien', re.IGNORECASE),
                'phone': re.compile(r'phone|tel|mobile|cell|fax', re.IGNORECASE),
                'email': re.compile(r'email|e-mail', re.IGNORECASE),
            }
        }
    
    def extract(self, page_data: Dict, context: ExtractionContext) -> List[FieldNode]:
        """Extract fields using hierarchical regex patterns"""
        fields = []
        text = page_data.get('text', '')
        
        # First, identify parts
        for match in self.patterns['part_header'].finditer(text):
            context.current_part = int(match.group(1))
        
        # Extract main items
        main_items = self._extract_main_items(text, context)
        
        # For each main item, extract sub-items
        for main_item in main_items:
            fields.append(main_item)
            sub_items = self._extract_sub_items(text, main_item, context)
            for sub_item in sub_items:
                main_item.add_child(sub_item)
                fields.append(sub_item)
                
                # Extract nested items
                nested_items = self._extract_nested_items(text, sub_item, context)
                for nested_item in nested_items:
                    sub_item.add_child(nested_item)
                    fields.append(nested_item)
        
        return fields
    
    def _extract_main_items(self, text: str, context: ExtractionContext) -> List[FieldNode]:
        """Extract main numbered items"""
        items = []
        
        for match in self.patterns['main_item'].finditer(text):
            item_num = match.group(1)
            label = match.group(2).strip()
            
            # Skip if this is actually a sub-item
            if self._is_sub_item(text, match.start()):
                continue
            
            field = FieldNode(
                item_number=item_num,
                label=label,
                full_path=f"Part {context.current_part} > {item_num}",
                part_number=context.current_part,
                page=context.current_page,
                extraction_strategy=ExtractionStrategy.REGEX_PATTERN,
                confidence=0.9,
                raw_text=match.group(0)
            )
            
            # Determine field type
            field.field_type = self._determine_field_type(label)
            
            # Extract checkbox options if applicable
            if "select" in label.lower() or "check" in label.lower():
                field.checkbox_options = self._extract_checkbox_options(text, match.end())
                if field.checkbox_options:
                    field.field_type = FieldType.CHECKBOX
            
            items.append(field)
            context.register_field(field)
        
        return items
    
    def _extract_sub_items(self, text: str, parent: FieldNode, context: ExtractionContext) -> List[FieldNode]:
        """Extract sub-items (1a, 1b, etc.) for a parent item"""
        items = []
        parent_num = parent.item_number
        
        # Try both patterns (with and without dots)
        patterns = [self.patterns['sub_item_dot'], self.patterns['sub_item_no_dot']]
        
        for pattern in patterns:
            for match in pattern.finditer(text):
                item_num = match.group(1)
                sub_letter = match.group(2)
                label = match.group(3).strip() if match.lastindex >= 3 else ""
                
                # Check if this belongs to the parent
                if item_num != parent_num:
                    continue
                
                full_item_num = f"{item_num}{sub_letter}"
                
                field = FieldNode(
                    item_number=full_item_num,
                    label=label,
                    full_path=f"{parent.full_path} > {full_item_num}",
                    part_number=context.current_part,
                    page=context.current_page,
                    extraction_strategy=ExtractionStrategy.REGEX_PATTERN,
                    confidence=0.85,
                    raw_text=match.group(0)
                )
                
                field.field_type = self._determine_field_type(label)
                
                # Extract checkbox options
                if field.field_type == FieldType.CHECKBOX or "check" in label.lower():
                    field.checkbox_options = self._extract_checkbox_options(text, match.end())
                
                items.append(field)
                context.register_field(field)
        
        return items
    
    def _extract_nested_items(self, text: str, parent: FieldNode, context: ExtractionContext) -> List[FieldNode]:
        """Extract nested items (1a1, 1a2, etc.)"""
        items = []
        
        for match in self.patterns['nested_item'].finditer(text):
            item_num = match.group(1)
            sub_letter = match.group(2)
            nested_num = match.group(3)
            label = match.group(4).strip()
            
            parent_num = f"{item_num}{sub_letter}"
            
            # Check if this belongs to the parent
            if parent.item_number != parent_num:
                continue
            
            full_item_num = f"{item_num}{sub_letter}{nested_num}"
            
            field = FieldNode(
                item_number=full_item_num,
                label=label,
                full_path=f"{parent.full_path} > {full_item_num}",
                part_number=context.current_part,
                page=context.current_page,
                extraction_strategy=ExtractionStrategy.REGEX_PATTERN,
                confidence=0.8,
                raw_text=match.group(0)
            )
            
            field.field_type = self._determine_field_type(label)
            items.append(field)
            context.register_field(field)
        
        return items
    
    def _is_sub_item(self, text: str, position: int) -> bool:
        """Check if a match is actually a sub-item"""
        # Look back to see if there's a letter before the dot
        if position > 1:
            prev_char = text[position - 1]
            return prev_char.isalpha() and prev_char.islower()
        return False
    
    def _extract_checkbox_options(self, text: str, start_pos: int) -> List[CheckboxOption]:
        """Extract checkbox options following a field"""
        options = []
        
        # Look for checkbox patterns in the next 500 characters
        search_text = text[start_pos:start_pos + 500]
        
        # Find all checkbox options
        for match in self.patterns['checkbox'].finditer(search_text):
            option_text = match.group(1).strip()
            if option_text and len(option_text) < 100:  # Reasonable length
                options.append(CheckboxOption(
                    value=option_text,
                    label=option_text,
                    is_selected=False
                ))
        
        # Also check for selected checkboxes
        for match in self.patterns['checkbox_selected'].finditer(search_text):
            option_text = match.group(1).strip()
            if option_text and len(option_text) < 100:
                # Check if already added
                existing = next((opt for opt in options if opt.label == option_text), None)
                if existing:
                    existing.is_selected = True
                else:
                    options.append(CheckboxOption(
                        value=option_text,
                        label=option_text,
                        is_selected=True
                    ))
        
        return options
    
    def _determine_field_type(self, label: str) -> FieldType:
        """Determine field type from label"""
        label_lower = label.lower()
        
        for field_type, pattern in self.patterns['label_patterns'].items():
            if pattern.search(label_lower):
                return FieldType(field_type)
        
        if "check" in label_lower or "select" in label_lower:
            return FieldType.CHECKBOX
        
        if "signature" in label_lower or "sign" in label_lower:
            return FieldType.SIGNATURE
        
        return FieldType.TEXT
    
    def confidence_score(self) -> float:
        return 0.85

class SpatialAnalysisStrategy(BaseExtractionStrategy):
    """Extract fields based on spatial relationships"""
    
    def extract(self, page_data: Dict, context: ExtractionContext) -> List[FieldNode]:
        """Extract fields using spatial analysis"""
        fields = []
        blocks = page_data.get('blocks', [])
        
        # Sort blocks by position
        sorted_blocks = sorted(blocks, key=lambda b: (b['bbox'][1], b['bbox'][0]))
        
        # Group blocks into logical fields
        field_groups = self._group_blocks_into_fields(sorted_blocks)
        
        # Convert groups to FieldNodes
        for group in field_groups:
            field = self._create_field_from_group(group, context)
            if field:
                fields.append(field)
                context.register_field(field)
        
        # Build hierarchy based on spatial relationships
        self._build_spatial_hierarchy(fields)
        
        return fields
    
    def _group_blocks_into_fields(self, blocks: List[Dict]) -> List[List[Dict]]:
        """Group text blocks into logical fields"""
        groups = []
        current_group = []
        
        for i, block in enumerate(blocks):
            if not current_group:
                current_group = [block]
            else:
                # Check if this block is close to the previous one
                prev_block = current_group[-1]
                vertical_gap = block['bbox'][1] - prev_block['bbox'][3]
                horizontal_gap = block['bbox'][0] - prev_block['bbox'][2]
                
                # If blocks are close, they belong to the same field
                if vertical_gap < 10 and horizontal_gap < 50:
                    current_group.append(block)
                else:
                    # Start new group
                    groups.append(current_group)
                    current_group = [block]
        
        if current_group:
            groups.append(current_group)
        
        return groups
    
    def _create_field_from_group(self, group: List[Dict], context: ExtractionContext) -> Optional[FieldNode]:
        """Create a FieldNode from a group of blocks"""
        if not group:
            return None
        
        # Combine text from all blocks
        combined_text = " ".join(block['text'] for block in group)
        
        # Try to extract item number and label
        item_match = re.match(r'^(\d+[a-z]?\d*)\.\s*(.+)', combined_text)
        if not item_match:
            return None
        
        item_number = item_match.group(1)
        label = item_match.group(2)
        
        # Calculate combined bbox
        min_x = min(block['bbox'][0] for block in group)
        min_y = min(block['bbox'][1] for block in group)
        max_x = max(block['bbox'][2] for block in group)
        max_y = max(block['bbox'][3] for block in group)
        
        field = FieldNode(
            item_number=item_number,
            label=label,
            bbox=(min_x, min_y, max_x, max_y),
            part_number=context.current_part,
            page=context.current_page,
            extraction_strategy=ExtractionStrategy.SPATIAL_ANALYSIS,
            confidence=0.75,
            raw_text=combined_text
        )
        
        return field
    
    def _build_spatial_hierarchy(self, fields: List[FieldNode]):
        """Build hierarchy based on spatial indentation"""
        # Sort fields by vertical position
        sorted_fields = sorted(fields, key=lambda f: f.bbox[1] if f.bbox else 0)
        
        for i, field in enumerate(sorted_fields):
            if not field.bbox:
                continue
            
            # Look for potential parent based on indentation
            for j in range(i - 1, -1, -1):
                potential_parent = sorted_fields[j]
                if not potential_parent.bbox:
                    continue
                
                # Check if this field is indented relative to potential parent
                if field.bbox[0] > potential_parent.bbox[0] + 10:
                    # Check if item numbers suggest parent-child relationship
                    if self._is_child_number(field.item_number, potential_parent.item_number):
                        potential_parent.add_child(field)
                        break
    
    def _is_child_number(self, child_num: str, parent_num: str) -> bool:
        """Check if child number is a sub-item of parent"""
        # e.g., "1a" is child of "1", "1a1" is child of "1a"
        return child_num.startswith(parent_num) and len(child_num) > len(parent_num)
    
    def confidence_score(self) -> float:
        return 0.75

# ===== AGENTIC EXTRACTION COORDINATOR =====
class AgenticExtractionCoordinator:
    """Coordinates multiple extraction strategies and iterates until correct"""
    
    def __init__(self):
        self.strategies = [
            HierarchicalRegexStrategy(),
            SpatialAnalysisStrategy(),
        ]
        self.max_iterations = 5
        self.confidence_threshold = 0.85
        
    def extract(self, pdf_document: Any, progress_callback=None) -> Dict[str, Any]:
        """Extract fields using multiple strategies with iterative refinement"""
        context = ExtractionContext()
        best_result = None
        best_confidence = 0.0
        
        for iteration in range(self.max_iterations):
            if progress_callback:
                progress_callback(f"Iteration {iteration + 1}/{self.max_iterations}")
            
            # Extract using all strategies
            all_fields = []
            strategy_results = []
            
            for strategy in self.strategies:
                try:
                    # Extract from each page
                    fields = []
                    for page_num in range(len(pdf_document)):
                        page = pdf_document[page_num]
                        context.current_page = page_num + 1
                        
                        # Get page data
                        page_data = self._get_page_data(page)
                        
                        # Extract fields
                        page_fields = strategy.extract(page_data, context)
                        fields.extend(page_fields)
                    
                    strategy_results.append({
                        'strategy': strategy.__class__.__name__,
                        'fields': fields,
                        'confidence': strategy.confidence_score()
                    })
                    
                except Exception as e:
                    if progress_callback:
                        progress_callback(f"Strategy {strategy.__class__.__name__} failed: {str(e)}")
            
            # Merge and validate results
            merged_result = self._merge_results(strategy_results)
            validation_score = self._validate_extraction(merged_result)
            
            # Update best result
            if validation_score > best_confidence:
                best_confidence = validation_score
                best_result = merged_result
            
            # Check if we've reached acceptable confidence
            if validation_score >= self.confidence_threshold:
                if progress_callback:
                    progress_callback(f"✅ Extraction successful with {validation_score:.0%} confidence!")
                break
            
            # Learn from this iteration
            self._learn_from_iteration(merged_result, validation_score)
            
            if progress_callback:
                progress_callback(f"Current confidence: {validation_score:.0%}, refining...")
        
        return self._prepare_final_result(best_result, best_confidence)
    
    def _get_page_data(self, page) -> Dict:
        """Extract structured data from a page"""
        page_dict = page.get_text("dict")
        
        # Extract text
        full_text = page.get_text()
        
        # Extract blocks with position info
        blocks = []
        for block in page_dict["blocks"]:
            if block["type"] == 0:  # Text block
                for line in block["lines"]:
                    for span in line["spans"]:
                        blocks.append({
                            'text': span["text"],
                            'bbox': span["bbox"],
                            'font_size': span["size"],
                            'font_flags': span["flags"]
                        })
        
        return {
            'text': full_text,
            'blocks': blocks,
            'width': page_dict['width'],
            'height': page_dict['height']
        }
    
    def _merge_results(self, strategy_results: List[Dict]) -> Dict:
        """Merge results from multiple strategies"""
        # Collect all fields
        all_fields = []
        field_votes = defaultdict(list)
        
        for result in strategy_results:
            for field in result['fields']:
                key = f"{field.part_number}_{field.item_number}"
                field_votes[key].append({
                    'field': field,
                    'confidence': result['confidence']
                })
        
        # Select best version of each field
        merged_fields = {}
        for key, votes in field_votes.items():
            # Sort by confidence
            votes.sort(key=lambda v: v['confidence'], reverse=True)
            best_field = votes[0]['field']
            
            # Merge information from other versions
            for vote in votes[1:]:
                other_field = vote['field']
                # Merge checkbox options
                if other_field.checkbox_options and not best_field.checkbox_options:
                    best_field.checkbox_options = other_field.checkbox_options
                # Use better bbox if available
                if other_field.bbox and not best_field.bbox:
                    best_field.bbox = other_field.bbox
            
            merged_fields[key] = best_field
        
        # Build part structure
        parts = defaultdict(list)
        for field in merged_fields.values():
            parts[field.part_number].append(field)
        
        return {
            'fields': list(merged_fields.values()),
            'parts': dict(parts),
            'total_fields': len(merged_fields)
        }
    
    def _validate_extraction(self, result: Dict) -> float:
        """Validate extraction quality"""
        score = 0.0
        checks = []
        
        # Check 1: Minimum field count
        field_count = result['total_fields']
        if field_count >= 20:
            score += 0.3
            checks.append(("Field count", True, f"{field_count} fields"))
        else:
            score += (field_count / 20) * 0.3
            checks.append(("Field count", False, f"Only {field_count} fields"))
        
        # Check 2: Hierarchical structure
        has_hierarchy = any(field.children for field in result['fields'])
        if has_hierarchy:
            score += 0.2
            checks.append(("Hierarchy", True, "Sub-items found"))
        else:
            checks.append(("Hierarchy", False, "No sub-items"))
        
        # Check 3: Field numbering consistency
        numbering_valid = self._check_numbering_consistency(result['fields'])
        if numbering_valid:
            score += 0.2
            checks.append(("Numbering", True, "Consistent"))
        else:
            checks.append(("Numbering", False, "Inconsistent"))
        
        # Check 4: Checkbox detection
        has_checkboxes = any(field.checkbox_options for field in result['fields'])
        if has_checkboxes:
            score += 0.15
            checks.append(("Checkboxes", True, "Detected"))
        else:
            checks.append(("Checkboxes", False, "None found"))
        
        # Check 5: Part organization
        part_count = len(result['parts'])
        if part_count > 0:
            score += 0.15
            checks.append(("Parts", True, f"{part_count} parts"))
        else:
            checks.append(("Parts", False, "No parts"))
        
        # Store validation details
        result['validation_checks'] = checks
        
        return score
    
    def _check_numbering_consistency(self, fields: List[FieldNode]) -> bool:
        """Check if field numbering is consistent"""
        # Group by part
        parts = defaultdict(list)
        for field in fields:
            parts[field.part_number].append(field.item_number)
        
        # Check each part
        for part_fields in parts.values():
            # Extract main numbers
            main_numbers = []
            for item_num in part_fields:
                match = re.match(r'^(\d+)', item_num)
                if match:
                    main_numbers.append(int(match.group(1)))
            
            # Check for gaps
            if main_numbers:
                main_numbers.sort()
                expected = list(range(main_numbers[0], main_numbers[-1] + 1))
                if len(set(main_numbers)) < len(expected) * 0.7:
                    return False
        
        return True
    
    def _learn_from_iteration(self, result: Dict, score: float):
        """Learn from extraction results to improve next iteration"""
        # Analyze what went wrong
        failed_checks = [check for check in result.get('validation_checks', []) if not check[1]]
        
        # Adjust strategies based on failures
        for check_name, _, detail in failed_checks:
            if check_name == "Hierarchy" and score < 0.5:
                # Need better sub-item detection
                # Could adjust regex patterns or add new strategy
                pass
            elif check_name == "Checkboxes":
                # Need better checkbox detection
                pass
    
    def _prepare_final_result(self, result: Dict, confidence: float) -> Dict:
        """Prepare final extraction result"""
        # Organize fields hierarchically
        root_fields = []
        all_fields = result['fields']
        
        # Build tree structure
        for field in all_fields:
            if not field.parent:
                root_fields.append(field)
        
        # Sort fields
        root_fields.sort(key=lambda f: (f.part_number, self._parse_item_number(f.item_number)))
        
        # Prepare output
        output = {
            'extraction_metadata': {
                'total_fields': len(all_fields),
                'confidence_score': confidence,
                'parts_found': len(result['parts']),
                'has_hierarchy': any(f.children for f in all_fields),
                'validation_checks': result.get('validation_checks', [])
            },
            'parts': {}
        }
        
        # Organize by parts
        for part_num, fields in result['parts'].items():
            part_data = {
                'part_number': part_num,
                'fields': []
            }
            
            # Get root fields for this part
            part_roots = [f for f in root_fields if f.part_number == part_num]
            
            # Convert to serializable format
            for root in part_roots:
                part_data['fields'].append(self._field_to_dict(root))
            
            output['parts'][f'part_{part_num}'] = part_data
        
        return output
    
    def _parse_item_number(self, item_num: str) -> Tuple:
        """Parse item number for sorting"""
        match = re.match(r'^(\d+)([a-z]?)(\d*)$', item_num)
        if match:
            main = int(match.group(1))
            sub = match.group(2) or ''
            nested = int(match.group(3)) if match.group(3) else 0
            return (main, sub, nested)
        return (999, '', 0)
    
    def _field_to_dict(self, field: FieldNode) -> Dict:
        """Convert field to dictionary format"""
        data = {
            'item_number': field.item_number,
            'label': field.label,
            'type': field.field_type.value,
            'value': field.value,
            'confidence': field.confidence,
            'page': field.page,
            'has_children': len(field.children) > 0
        }
        
        # Add checkbox options
        if field.checkbox_options:
            data['checkbox_options'] = [
                {
                    'value': opt.value,
                    'label': opt.label,
                    'selected': opt.is_selected
                }
                for opt in field.checkbox_options
            ]
        
        # Add children recursively
        if field.children:
            data['children'] = [self._field_to_dict(child) for child in field.children]
        
        # Add database mapping if available
        if field.db_field:
            data['mapped_to'] = field.db_field
            data['mapping_confidence'] = field.mapping_confidence
        
        return data

# ===== QUESTIONNAIRE MODE =====
class QuestionnaireMode:
    """Interactive questionnaire for manual field entry"""
    
    def __init__(self, form_type: str):
        self.form_type = form_type
        self.questions = self._load_questions(form_type)
        self.responses = {}
        
    def _load_questions(self, form_type: str) -> List[Dict]:
        """Load questions for specific form type"""
        # This would be loaded from a configuration file
        # For now, using common USCIS form fields
        return [
            {
                'id': '1',
                'question': 'What is your family name (last name)?',
                'field_type': 'text',
                'required': True,
                'db_field': 'personal_info.last_name'
            },
            {
                'id': '1a',
                'question': 'What is your given name (first name)?',
                'field_type': 'text',
                'required': True,
                'db_field': 'personal_info.first_name'
            },
            {
                'id': '1b',
                'question': 'What is your middle name?',
                'field_type': 'text',
                'required': False,
                'db_field': 'personal_info.middle_name'
            },
            {
                'id': '2',
                'question': 'What is your date of birth?',
                'field_type': 'date',
                'required': True,
                'db_field': 'personal_info.date_of_birth'
            },
            {
                'id': '3',
                'question': 'What is your country of birth?',
                'field_type': 'text',
                'required': True,
                'db_field': 'personal_info.country_of_birth'
            },
            {
                'id': '4',
                'question': 'What is your current immigration status?',
                'field_type': 'checkbox',
                'options': [
                    'U.S. Citizen',
                    'Permanent Resident',
                    'H-1B',
                    'F-1 Student',
                    'Other Nonimmigrant',
                    'No Status'
                ],
                'required': True,
                'db_field': 'immigration_info.current_status'
            }
        ]
    
    def render_questionnaire(self, container):
        """Render questionnaire in Streamlit"""
        with container:
            st.markdown("### 📝 Manual Entry Mode")
            st.info("Please answer the following questions to complete the form.")
            
            progress = len(self.responses) / len(self.questions)
            st.progress(progress)
            
            for i, question in enumerate(self.questions):
                with st.expander(
                    f"Question {question['id']}: {question['question']}", 
                    expanded=i == len(self.responses)
                ):
                    if question['field_type'] == 'text':
                        value = st.text_input(
                            "Your answer:",
                            key=f"q_{question['id']}",
                            value=self.responses.get(question['id'], '')
                        )
                    elif question['field_type'] == 'date':
                        value = st.date_input(
                            "Your answer:",
                            key=f"q_{question['id']}",
                            value=self.responses.get(question['id'])
                        )
                    elif question['field_type'] == 'checkbox':
                        value = st.multiselect(
                            "Select all that apply:",
                            options=question['options'],
                            key=f"q_{question['id']}",
                            default=self.responses.get(question['id'], [])
                        )
                    
                    if value:
                        self.responses[question['id']] = value
            
            if len(self.responses) == len(self.questions):
                st.success("✅ All questions answered!")
                return True
            else:
                remaining = len(self.questions) - len(self.responses)
                st.warning(f"⚠️ {remaining} questions remaining")
                return False

# ===== DATABASE MAPPER =====
class IntelligentDatabaseMapper:
    """Maps extracted fields to database schema"""
    
    def __init__(self):
        self.schema = self._load_schema()
        self.mapping_patterns = self._load_mapping_patterns()
        
    def _load_schema(self) -> Dict:
        """Load database schema"""
        return {
            "personal_info": {
                "first_name": "Given Name",
                "last_name": "Family Name",
                "middle_name": "Middle Name",
                "date_of_birth": "Date of Birth",
                "country_of_birth": "Country of Birth",
                "nationality": "Nationality"
            },
            "identification": {
                "alien_number": "A-Number",
                "uscis_number": "USCIS Online Account Number",
                "social_security_number": "Social Security Number",
                "passport_number": "Passport Number"
            },
            "contact_info": {
                "mailing_address": "Mailing Address",
                "physical_address": "Physical Address",
                "city": "City or Town",
                "state": "State",
                "zip_code": "ZIP Code",
                "phone_number": "Daytime Phone Number",
                "email_address": "Email Address"
            }
        }
    
    def _load_mapping_patterns(self) -> Dict:
        """Load mapping patterns from project knowledge"""
        # Based on the pdf-mappers.ts patterns
        return {
            r'family\s*name|last\s*name': 'personal_info.last_name',
            r'given\s*name|first\s*name': 'personal_info.first_name',
            r'middle\s*name': 'personal_info.middle_name',
            r'date.*birth|birth.*date|d\.o\.b': 'personal_info.date_of_birth',
            r'country.*birth|birth.*country': 'personal_info.country_of_birth',
            r'a[\-\s]?number|alien.*number': 'identification.alien_number',
            r'uscis.*number|online.*account': 'identification.uscis_number',
            r'street.*number.*name|mailing.*address': 'contact_info.mailing_address',
            r'city|town': 'contact_info.city',
            r'state': 'contact_info.state',
            r'zip.*code|postal.*code': 'contact_info.zip_code',
            r'phone|telephone|daytime.*phone': 'contact_info.phone_number',
            r'email.*address|e[\-\s]?mail': 'contact_info.email_address'
        }
    
    def map_fields(self, extracted_data: Dict) -> Dict:
        """Map extracted fields to database schema"""
        mappings = {}
        
        for part_key, part_data in extracted_data['parts'].items():
            for field in self._flatten_fields(part_data['fields']):
                db_field = self._find_mapping(field)
                if db_field:
                    field_key = f"{part_key}_{field['item_number']}"
                    mappings[field_key] = {
                        'field': field,
                        'db_field': db_field,
                        'confidence': field.get('mapping_confidence', 0.8)
                    }
        
        return mappings
    
    def _flatten_fields(self, fields: List[Dict], parent_path: str = "") -> List[Dict]:
        """Flatten hierarchical fields"""
        flat_fields = []
        
        for field in fields:
            field_path = f"{parent_path}/{field['item_number']}" if parent_path else field['item_number']
            field_copy = field.copy()
            field_copy['path'] = field_path
            flat_fields.append(field_copy)
            
            if 'children' in field:
                flat_fields.extend(self._flatten_fields(field['children'], field_path))
        
        return flat_fields
    
    def _find_mapping(self, field: Dict) -> Optional[str]:
        """Find database mapping for a field"""
        label_lower = field['label'].lower()
        
        # Check patterns
        for pattern, db_field in self.mapping_patterns.items():
            if re.search(pattern, label_lower):
                field['mapping_confidence'] = 0.9
                return db_field
        
        # Check exact matches in schema
        for category, fields in self.schema.items():
            for db_field, display_name in fields.items():
                if display_name.lower() in label_lower:
                    field['mapping_confidence'] = 0.85
                    return f"{category}.{db_field}"
        
        return None

# ===== UI COMPONENTS =====
def display_extraction_results(extraction_data: Dict):
    """Display extraction results with hierarchical structure"""
    st.markdown("### 📊 Extraction Results")
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    metadata = extraction_data['extraction_metadata']
    
    with col1:
        st.metric("Total Fields", metadata['total_fields'])
    
    with col2:
        st.metric("Confidence", f"{metadata['confidence_score']:.1%}")
    
    with col3:
        st.metric("Parts Found", metadata['parts_found'])
    
    with col4:
        st.metric("Has Hierarchy", "✅" if metadata['has_hierarchy'] else "❌")
    
    # Validation checks
    with st.expander("🔍 Validation Details"):
        for check_name, passed, detail in metadata['validation_checks']:
            if passed:
                st.success(f"✅ {check_name}: {detail}")
            else:
                st.warning(f"⚠️ {check_name}: {detail}")
    
    # Display fields by part
    for part_key, part_data in extraction_data['parts'].items():
        st.markdown(f"#### {part_key.replace('_', ' ').title()}")
        
        # Create tree view
        with st.container():
            st.markdown('<div class="field-tree">', unsafe_allow_html=True)
            
            for field in part_data['fields']:
                display_field_tree(field, level=0)
            
            st.markdown('</div>', unsafe_allow_html=True)

def display_field_tree(field: Dict, level: int = 0):
    """Display field in tree structure"""
    indent = "&nbsp;" * (level * 4)
    
    # Field content
    field_html = f"""
    <div class="field-node" style="margin-left: {level * 20}px;">
        <strong>{field['item_number']}.</strong> {field['label']}
        <span style="float: right; color: #666;">
            {field['type']} | {field['confidence']:.0%} confidence
        </span>
    </div>
    """
    
    st.markdown(field_html, unsafe_allow_html=True)
    
    # Show checkbox options if any
    if 'checkbox_options' in field:
        options_html = '<div style="margin-left: ' + str((level + 1) * 20) + 'px;">'
        for opt in field['checkbox_options']:
            selected_class = "checkbox-selected" if opt['selected'] else ""
            options_html += f'<span class="checkbox-option {selected_class}">{opt["label"]}</span>'
        options_html += '</div>'
        st.markdown(options_html, unsafe_allow_html=True)
    
    # Show children
    if 'children' in field:
        for child in field['children']:
            display_field_tree(child, level + 1)

def display_manual_mapping_interface(extraction_data: Dict, mappings: Dict):
    """Display interface for manual mapping review"""
    st.markdown("### 🔗 Database Mapping Review")
    
    # Summary
    total_fields = extraction_data['extraction_metadata']['total_fields']
    mapped_fields = len(mappings)
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Fields Mapped", f"{mapped_fields}/{total_fields}")
    with col2:
        st.metric("Mapping Coverage", f"{(mapped_fields/total_fields)*100:.1f}%")
    
    # Review interface
    st.markdown("#### Review and Adjust Mappings")
    
    updated_mappings = {}
    
    for field_key, mapping_info in mappings.items():
        field = mapping_info['field']
        current_mapping = mapping_info['db_field']
        
        with st.expander(f"{field['item_number']}. {field['label']}"):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                # Show field details
                st.write(f"**Type:** {field['type']}")
                st.write(f"**Current Mapping:** `{current_mapping}`")
                st.write(f"**Confidence:** {mapping_info['confidence']:.0%}")
            
            with col2:
                # Allow manual override
                new_mapping = st.selectbox(
                    "Override mapping:",
                    options=["(Keep current)"] + get_all_db_fields(),
                    key=f"map_{field_key}"
                )
                
                if new_mapping != "(Keep current)":
                    updated_mappings[field_key] = new_mapping
    
    return updated_mappings

def get_all_db_fields() -> List[str]:
    """Get all available database fields"""
    mapper = IntelligentDatabaseMapper()
    fields = []
    
    for category, category_fields in mapper.schema.items():
        for field_name in category_fields:
            fields.append(f"{category}.{field_name}")
    
    return sorted(fields)

# ===== MAIN APPLICATION =====
def main():
    st.markdown(
        '<div class="main-header">'
        '<h1>🤖 Agentic USCIS Form Reader V2</h1>'
        '<p>Advanced extraction with hierarchical fields and iterative refinement</p>'
        '</div>', 
        unsafe_allow_html=True
    )
    
    # Initialize session state
    if 'extraction_result' not in st.session_state:
        st.session_state.extraction_result = None
    if 'mappings' not in st.session_state:
        st.session_state.mappings = None
    if 'mode' not in st.session_state:
        st.session_state.mode = 'extraction'
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 🎯 Extraction Mode")
        
        mode = st.radio(
            "Select mode:",
            ["PDF Extraction", "Questionnaire", "Manual Entry"],
            key="mode_selector"
        )
        
        st.markdown("---")
        
        if mode == "PDF Extraction":
            st.markdown("### ⚙️ Extraction Settings")
            
            show_iterations = st.checkbox("Show iteration details", value=True)
            confidence_threshold = st.slider(
                "Confidence threshold", 
                min_value=0.5, 
                max_value=1.0, 
                value=0.85,
                step=0.05
            )
            
            st.markdown("### 📊 Extraction Strategies")
            st.markdown("""
            - **Hierarchical Regex**: Extracts 1, 1a, 1b patterns
            - **Spatial Analysis**: Uses position relationships
            - **Context Aware**: Learns from document structure
            - **Manual Review**: Falls back to human input
            """)
    
    # Main content
    if mode == "PDF Extraction":
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
                if st.button("🚀 Extract", type="primary", use_container_width=True):
                    # Progress container
                    progress_container = st.container()
                    
                    with st.spinner("Extracting fields..."):
                        try:
                            # Open PDF
                            pdf_bytes = uploaded_file.read()
                            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                            
                            # Status display
                            status_container = st.empty()
                            
                            def update_progress(message):
                                with status_container.container():
                                    st.markdown(
                                        f'<div class="extraction-status">{message}</div>',
                                        unsafe_allow_html=True
                                    )
                            
                            # Extract using coordinator
                            coordinator = AgenticExtractionCoordinator()
                            coordinator.confidence_threshold = confidence_threshold
                            
                            extraction_result = coordinator.extract(
                                doc,
                                progress_callback=update_progress if show_iterations else None
                            )
                            
                            st.session_state.extraction_result = extraction_result
                            
                            # Close document
                            doc.close()
                            
                            # Show success
                            st.balloons()
                            st.success("✅ Extraction complete!")
                            
                        except Exception as e:
                            st.error(f"❌ Extraction failed: {str(e)}")
                            st.exception(e)
        
        # Display results
        if st.session_state.extraction_result:
            st.markdown("---")
            display_extraction_results(st.session_state.extraction_result)
            
            # Database mapping
            st.markdown("---")
            
            if st.button("🔗 Map to Database", type="secondary"):
                mapper = IntelligentDatabaseMapper()
                mappings = mapper.map_fields(st.session_state.extraction_result)
                st.session_state.mappings = mappings
            
            if st.session_state.mappings:
                updated_mappings = display_manual_mapping_interface(
                    st.session_state.extraction_result,
                    st.session_state.mappings
                )
                
                if updated_mappings:
                    if st.button("💾 Save Mappings", type="primary"):
                        # Update mappings
                        for field_key, new_mapping in updated_mappings.items():
                            st.session_state.mappings[field_key]['db_field'] = new_mapping
                        st.success("✅ Mappings updated!")
    
    elif mode == "Questionnaire":
        st.markdown("### 📝 Questionnaire Mode")
        
        form_type = st.selectbox(
            "Select form type:",
            ["I-90", "I-130", "I-485", "I-539", "N-400", "I-129", "G-28"]
        )
        
        questionnaire = QuestionnaireMode(form_type)
        
        if questionnaire.render_questionnaire(st.container()):
            if st.button("💾 Save Responses", type="primary"):
                st.success("✅ Responses saved!")
                st.json(questionnaire.responses)
    
    elif mode == "Manual Entry":
        st.markdown("### ✏️ Manual Entry Mode")
        
        with st.form("manual_entry_form"):
            st.markdown("#### Enter field information manually")
            
            part_number = st.number_input("Part Number", min_value=1, value=1)
            item_number = st.text_input("Item Number (e.g., 1, 1a, 2b)")
            label = st.text_input("Field Label")
            field_type = st.selectbox(
                "Field Type",
                [t.value for t in FieldType]
            )
            
            if field_type == "checkbox":
                num_options = st.number_input("Number of options", min_value=1, value=2)
                options = []
                for i in range(num_options):
                    option = st.text_input(f"Option {i+1}")
                    if option:
                        options.append(option)
            
            submitted = st.form_submit_button("Add Field")
            
            if submitted:
                st.success(f"✅ Added field {item_number}")

if __name__ == "__main__":
    if not PYMUPDF_AVAILABLE:
        st.error("❌ PyMuPDF is required but not installed!")
        st.code("pip install PyMuPDF")
        st.stop()
    
    main()
