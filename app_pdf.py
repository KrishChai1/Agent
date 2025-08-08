#!/usr/bin/env python3
"""
Enhanced Iterative USCIS Form Reader
With iterative extraction, validation, and refinement
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

# ===== VALIDATION FEEDBACK =====
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

# ===== EXTRACTION CONTEXT =====
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
        elif ExtractionStrategy.CONTEXT_AWARE not in self.strategies_tried:
            return ExtractionStrategy.CONTEXT_AWARE
        
        return ExtractionStrategy.CONTEXT_AWARE

# ===== ENHANCED FIELD NODE =====
@dataclass
class FieldNode:
    """Enhanced field node with value extraction"""
    item_number: str
    label: str
    field_type: FieldType = FieldType.UNKNOWN
    value: str = ""
    raw_value: str = ""  # Original extracted value
    cleaned_value: str = ""  # Cleaned/processed value
    checkbox_options: List['CheckboxOption'] = field(default_factory=list)
    
    # Enhanced extraction metadata
    extraction_confidence: float = 0.0
    value_bbox: Optional[List[float]] = None  # Bounding box of value
    label_bbox: Optional[List[float]] = None  # Bounding box of label
    extraction_method: str = ""  # Method used to extract
    validation_status: ValidationResult = ValidationResult.INVALID
    
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
    mapped_to: Optional[str] = None
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

# ===== ENHANCED EXTRACTION AGENT =====
class EnhancedExtractionAgent:
    """Enhanced extraction with multiple strategies and value extraction"""
    
    def __init__(self):
        self.name = "Enhanced Extraction Agent"
        self.doc = None
        self.current_strategy = ExtractionStrategy.BASIC
        
    def extract_with_strategy(self, pdf_file, strategy: ExtractionStrategy, 
                            previous_result: Optional['FormExtractionResult'] = None,
                            feedback: Optional[ValidationFeedback] = None) -> 'FormExtractionResult':
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
    
    def _basic_extraction(self) -> 'FormExtractionResult':
        """Basic extraction strategy"""
        result = FormExtractionResult(
            form_number="Unknown",
            form_title="Unknown Form"
        )
        
        # Extract all pages
        for page_num in range(len(self.doc)):
            page = self.doc[page_num]
            self._extract_page_fields(page, page_num + 1, result)
        
        return result
    
    def _enhanced_ocr_extraction(self, previous: Optional['FormExtractionResult'], 
                               feedback: Optional[ValidationFeedback]) -> 'FormExtractionResult':
        """Enhanced OCR with better value extraction"""
        self.log("🔤 Using enhanced OCR for better value extraction")
        
        # Start with previous result or create new
        result = copy.deepcopy(previous) if previous else FormExtractionResult(
            form_number="Unknown",
            form_title="Unknown Form"
        )
        
        # Focus on fields that need improvement
        fields_to_improve = []
        if feedback:
            fields_to_improve = feedback.empty_fields + list(feedback.suspicious_values.keys())
        
        # Re-extract with enhanced settings
        for page_num in range(len(self.doc)):
            page = self.doc[page_num]
            
            # Increase resolution for better OCR
            mat = fitz.Matrix(2, 2)  # 2x zoom
            pix = page.get_pixmap(matrix=mat)
            
            # Get enhanced text with positions
            text_instances = page.get_text("words")
            
            # Find and extract field values more carefully
            self._extract_field_values_enhanced(page, text_instances, result, fields_to_improve)
        
        return result
    
    def _layout_based_extraction(self, previous: Optional['FormExtractionResult'], 
                               feedback: Optional[ValidationFeedback]) -> 'FormExtractionResult':
        """Layout-based extraction using spatial relationships"""
        self.log("📐 Using layout analysis for field-value pairing")
        
        result = copy.deepcopy(previous) if previous else FormExtractionResult(
            form_number="Unknown",
            form_title="Unknown Form"
        )
        
        for page_num in range(len(self.doc)):
            page = self.doc[page_num]
            
            # Get all text blocks with positions
            blocks = page.get_text("dict")
            
            # Analyze layout to find field-value pairs
            field_value_pairs = self._analyze_layout_for_pairs(blocks)
            
            # Update result with found pairs
            self._update_result_with_pairs(result, field_value_pairs, page_num + 1)
        
        return result
    
    def _pattern_matching_extraction(self, previous: Optional['FormExtractionResult'], 
                                   feedback: Optional[ValidationFeedback]) -> 'FormExtractionResult':
        """Pattern-based extraction for specific field types"""
        self.log("🎯 Using pattern matching for typed field extraction")
        
        result = copy.deepcopy(previous) if previous else FormExtractionResult(
            form_number="Unknown",
            form_title="Unknown Form"
        )
        
        # Define patterns for common field types
        patterns = {
            'a_number': r'[Aa][-\s]?\d{7,9}',
            'ssn': r'\d{3}-?\d{2}-?\d{4}',
            'date': r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',
            'phone': r'[\(\[]?\d{3}[\)\]]?[-\s]?\d{3}[-\s]?\d{4}',
            'email': r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            'zip': r'\d{5}(-\d{4})?'
        }
        
        # Extract values matching patterns
        for page_num in range(len(self.doc)):
            page = self.doc[page_num]
            text = page.get_text()
            
            # Find all pattern matches
            for field_type, pattern in patterns.items():
                matches = re.finditer(pattern, text)
                for match in matches:
                    self._assign_pattern_match_to_field(result, match.group(), field_type, page_num + 1)
        
        return result
    
    def _context_aware_extraction(self, previous: Optional['FormExtractionResult'], 
                                feedback: Optional[ValidationFeedback]) -> 'FormExtractionResult':
        """Context-aware extraction using surrounding text"""
        self.log("🧠 Using context-aware extraction with field relationships")
        
        result = copy.deepcopy(previous) if previous else FormExtractionResult(
            form_number="Unknown",
            form_title="Unknown Form"
        )
        
        # Build context map
        for page_num in range(len(self.doc)):
            page = self.doc[page_num]
            
            # Get all text with detailed positioning
            words = page.get_text("words")
            
            # Group words into lines and analyze context
            lines = self._group_words_into_lines(words)
            
            # Extract based on context clues
            self._extract_with_context(lines, result, page_num + 1)
        
        return result
    
    def _extract_field_values_enhanced(self, page, text_instances, result, fields_to_improve):
        """Enhanced extraction of field values"""
        # Group text by proximity
        for field_key in fields_to_improve:
            field = result.get_field_by_key(field_key)
            if not field:
                continue
            
            # Look for value near the field label
            label_pattern = re.escape(field.label)
            
            for i, word in enumerate(text_instances):
                if re.search(label_pattern, word[4], re.IGNORECASE):
                    # Found label, look for value nearby
                    label_bbox = list(word[:4])
                    
                    # Check words to the right and below
                    potential_values = []
                    for j in range(i + 1, min(i + 10, len(text_instances))):
                        next_word = text_instances[j]
                        next_bbox = list(next_word[:4])
                        
                        # If word is to the right or below
                        if (next_bbox[0] > label_bbox[2] or  # To the right
                            next_bbox[1] > label_bbox[3]):    # Below
                            potential_values.append(next_word[4])
                    
                    if potential_values:
                        # Join potential values
                        value = " ".join(potential_values[:3])  # Take first 3 words
                        field.value = value
                        field.raw_value = value
                        field.extraction_confidence = 0.8
                        field.extraction_method = "enhanced_ocr"
    
    def _analyze_layout_for_pairs(self, blocks):
        """Analyze layout to find field-value pairs"""
        pairs = []
        
        for block in blocks.get("blocks", []):
            if block["type"] == 0:  # Text block
                lines = block.get("lines", [])
                
                for i, line in enumerate(lines):
                    line_text = " ".join(span["text"] for span in line.get("spans", []))
                    
                    # Check if this looks like a field label
                    if self._is_field_label(line_text):
                        # Look for value in same line or next line
                        value = self._extract_value_from_line(line_text)
                        
                        if not value and i + 1 < len(lines):
                            next_line_text = " ".join(
                                span["text"] for span in lines[i + 1].get("spans", [])
                            )
                            if not self._is_field_label(next_line_text):
                                value = next_line_text.strip()
                        
                        if value:
                            pairs.append({
                                'label': line_text,
                                'value': value,
                                'bbox': line.get("bbox"),
                                'confidence': 0.7
                            })
        
        return pairs
    
    def _is_field_label(self, text):
        """Check if text is likely a field label"""
        # Common patterns for field labels
        patterns = [
            r'^\d+\.',
            r'^[A-Z][a-z]+.*:',
            r'Name\s*$',
            r'Date',
            r'Number',
            r'Address'
        ]
        
        return any(re.search(p, text) for p in patterns)
    
    def _extract_value_from_line(self, line_text):
        """Extract value from a line containing label and value"""
        # Try to split by common separators
        separators = [':', '：', '-', '–', '—']
        
        for sep in separators:
            if sep in line_text:
                parts = line_text.split(sep, 1)
                if len(parts) == 2:
                    value = parts[1].strip()
                    if value and not self._is_field_label(value):
                        return value
        
        return None
    
    def log(self, message: str, level: str = "info"):
        """Log message"""
        if hasattr(st, 'session_state') and 'agent_container' in st.session_state:
            with st.session_state.agent_container:
                icon = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌"}.get(level, "📝")
                st.markdown(f'{icon} **{self.name}**: {message}')

# ===== ENHANCED VALIDATION AGENT =====
class EnhancedValidationAgent:
    """Enhanced validation with detailed feedback"""
    
    def __init__(self):
        self.name = "Enhanced Validation Agent"
        self.form_knowledge = self._init_form_knowledge()
    
    def _init_form_knowledge(self):
        """Initialize expected fields for validation"""
        return {
            "I-130": {
                "required_fields": ["1a", "1b", "1c", "2a", "2b", "3a", "3b"],
                "expected_parts": 6,
                "value_patterns": {
                    "a_number": r'^[Aa]?\d{7,9}$',
                    "date": r'^\d{2}/\d{2}/\d{4}$',
                    "ssn": r'^\d{3}-\d{2}-\d{4}$'
                }
            }
        }
    
    def validate_iteratively(self, result: 'FormExtractionResult', 
                           context: ExtractionContext) -> ValidationFeedback:
        """Validate with detailed feedback for iteration"""
        self.log(f"🔍 Validating extraction (iteration {context.iteration + 1})")
        
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
                "fields": empty_fields[:5]  # First 5 for display
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
    
    def _find_empty_fields(self, result: 'FormExtractionResult') -> List[str]:
        """Find fields without values"""
        empty_fields = []
        
        for part in result.parts.values():
            for field in part.get_all_fields_flat():
                if not field.value and field.field_type != FieldType.CHECKBOX:
                    empty_fields.append(field.key)
        
        return empty_fields
    
    def _validate_field_values(self, result: 'FormExtractionResult') -> Dict[str, str]:
        """Validate field values against patterns"""
        invalid_values = {}
        
        form_info = self.form_knowledge.get(result.form_number, {})
        patterns = form_info.get("value_patterns", {})
        
        for part in result.parts.values():
            for field in part.get_all_fields_flat():
                if field.value:
                    # Check against known patterns
                    for pattern_name, pattern in patterns.items():
                        if pattern_name.lower() in field.label.lower():
                            if not re.match(pattern, field.value):
                                invalid_values[field.key] = f"Expected {pattern_name} format"
        
        return invalid_values
    
    def _validate_structure(self, result: 'FormExtractionResult') -> float:
        """Validate document structure"""
        score = 1.0
        
        # Check parts
        if not result.parts:
            return 0.0
        
        # Check part sequence
        part_numbers = sorted(result.parts.keys())
        expected = list(range(1, max(part_numbers) + 1))
        if part_numbers != expected:
            score *= 0.8
        
        # Check field count
        if result.total_fields < 20:
            score *= 0.7
        
        return score
    
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
    
    def process_iteratively(self, pdf_file, max_iterations: int = 3) -> 'FormExtractionResult':
        """Process form with iterative refinement"""
        self.log("🚀 Starting iterative form processing")
        
        context = ExtractionContext(max_iterations=max_iterations)
        result = None
        
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
        
        # Final summary
        if result:
            result.extraction_context = context
            self.log(f"📊 Final result: {result.total_fields} fields extracted with {feedback.confidence:.2f} confidence")
        
        return result
    
    def log(self, message: str, level: str = "info"):
        """Log message"""
        if hasattr(st, 'session_state') and 'agent_container' in st.session_state:
            with st.session_state.agent_container:
                icon = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌"}.get(level, "📝")
                st.markdown(f'{icon} **{self.name}**: {message}')

# ===== FORM EXTRACTION RESULT =====
@dataclass
class FormExtractionResult:
    """Enhanced extraction result with iteration context"""
    form_number: str
    form_title: str
    parts: Dict[int, 'PartStructure'] = field(default_factory=dict)
    
    # Metadata
    total_fields: int = 0
    confidence_score: float = 0.0
    extraction_time: float = 0.0
    
    # Extraction context
    extraction_context: Optional[ExtractionContext] = None
    
    # Mapping data
    field_mappings: Dict[str, str] = field(default_factory=dict)
    questionnaire_fields: List[str] = field(default_factory=list)
    
    def get_field_by_key(self, key: str) -> Optional[FieldNode]:
        """Get field by its unique key"""
        for part in self.parts.values():
            for field in part.get_all_fields_flat():
                if field.key == key:
                    return field
        return None
    
    def get_extraction_summary(self) -> Dict[str, Any]:
        """Get summary of extraction process"""
        if not self.extraction_context:
            return {}
        
        return {
            "iterations": self.extraction_context.iteration,
            "strategies_used": [s.value for s in self.extraction_context.strategies_tried],
            "final_confidence": self.confidence_score,
            "total_fields": self.total_fields,
            "empty_fields": sum(1 for p in self.parts.values() 
                               for f in p.get_all_fields_flat() if not f.value),
            "high_confidence_fields": sum(1 for p in self.parts.values() 
                                        for f in p.get_all_fields_flat() 
                                        if f.extraction_confidence > 0.8)
        }

@dataclass  
class PartStructure:
    """Part structure"""
    part_number: int
    part_name: str
    part_title: str = ""
    fields: List[FieldNode] = field(default_factory=list)
    
    def get_all_fields_flat(self) -> List[FieldNode]:
        """Get all fields in flat list"""
        return self.fields

# ===== UI ENHANCEMENTS =====
def display_iterative_results(result: FormExtractionResult):
    """Display results with iteration details"""
    if not result or not result.extraction_context:
        return
    
    # Show extraction summary
    st.markdown("### 📊 Extraction Process Summary")
    
    summary = result.get_extraction_summary()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Iterations", summary.get("iterations", 0))
    with col2:
        st.metric("Strategies Used", len(summary.get("strategies_used", [])))
    with col3:
        st.metric("Final Confidence", f"{summary.get('final_confidence', 0):.2%}")
    with col4:
        st.metric("High Confidence Fields", summary.get("high_confidence_fields", 0))
    
    # Show iteration history
    with st.expander("View Iteration History"):
        for i, feedback in enumerate(result.extraction_context.feedback_history):
            st.markdown(f"**Iteration {i+1}**")
            st.write(f"- Result: {feedback.result.value}")
            st.write(f"- Confidence: {feedback.confidence:.2%}")
            if feedback.issues:
                st.write("- Issues found:")
                for issue in feedback.issues:
                    st.write(f"  - {issue['type']}: {issue.get('count', 'N/A')} occurrences")
            st.markdown("---")

# ===== MAIN APPLICATION =====
def main():
    st.set_page_config(
        page_title="Enhanced Iterative USCIS Form Reader",
        page_icon="🤖",
        layout="wide"
    )
    
    st.markdown("""
    <style>
    .main-header {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        color: white;
        padding: 2rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown(
        '<div class="main-header">'
        '<h1>🤖 Enhanced Iterative USCIS Form Reader</h1>'
        '<p>Extract and validate form fields iteratively until correct</p>'
        '</div>', 
        unsafe_allow_html=True
    )
    
    # Sidebar
    with st.sidebar:
        st.markdown("## ⚙️ Configuration")
        max_iterations = st.slider("Max Iterations", 1, 5, 3)
        show_agent_logs = st.checkbox("Show Agent Activity", value=True)
        
        st.markdown("---")
        st.markdown("## 🎯 Features")
        st.markdown("""
        ✅ Iterative extraction & validation  
        ✅ Multiple extraction strategies  
        ✅ Automatic value detection  
        ✅ Pattern-based validation  
        ✅ Context-aware extraction  
        ✅ Self-improving accuracy
        """)
    
    # Main content
    uploaded_file = st.file_uploader("Choose a PDF form", type=['pdf'])
    
    if uploaded_file is not None:
        if st.button("🚀 Process Form Iteratively", type="primary"):
            # Create agent activity container
            if show_agent_logs:
                st.markdown("### 🤖 Agent Activity")
                agent_container = st.container()
                st.session_state.agent_container = agent_container
            
            # Process iteratively
            with st.spinner("Processing form iteratively..."):
                coordinator = IterativeCoordinator()
                result = coordinator.process_iteratively(uploaded_file, max_iterations)
                
                if result:
                    st.success("✅ Processing complete!")
                    
                    # Display results
                    display_iterative_results(result)
                    
                    # Show extracted fields
                    st.markdown("### 📋 Extracted Fields")
                    for part in result.parts.values():
                        with st.expander(f"Part {part.part_number}: {part.part_title}"):
                            for field in part.get_all_fields_flat():
                                col1, col2, col3 = st.columns([2, 2, 1])
                                with col1:
                                    st.write(f"**{field.item_number}.** {field.label}")
                                with col2:
                                    st.write(f"Value: {field.value or '(empty)'}")
                                with col3:
                                    conf_color = "green" if field.extraction_confidence > 0.8 else "orange" if field.extraction_confidence > 0.5 else "red"
                                    st.markdown(f"<span style='color:{conf_color}'>Conf: {field.extraction_confidence:.2f}</span>", unsafe_allow_html=True)

if __name__ == "__main__":
    if not PYMUPDF_AVAILABLE:
        st.error("❌ PyMuPDF is required but not installed!")
        st.code("pip install PyMuPDF")
        st.stop()
    
    main()
