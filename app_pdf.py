#!/usr/bin/env python3
"""
Enhanced USCIS Form Reader with Proper Sequence Handling
- Handles field numbering like 1a, 1b, 1c
- Maintains proper sequence order
- Validates completeness of extraction
- Shows extracted attributes per part with sequence validation
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
from collections import defaultdict, OrderedDict
from enum import Enum
from pathlib import Path
import difflib

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
    page_title="Enhanced USCIS Form Reader with Validation",
    page_icon="📋",
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
    
    .field-card {
        background: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        padding: 0.8rem;
        margin: 0.5rem 0;
        border-left: 4px solid #007bff;
    }
    
    .field-value {
        background: #e8f5e9;
        padding: 0.5rem;
        border-radius: 4px;
        font-weight: bold;
        color: #2e7d32;
    }
    
    .empty-value {
        background: #ffebee;
        padding: 0.5rem;
        border-radius: 4px;
        color: #c62828;
        font-style: italic;
    }
    
    .part-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
        font-weight: bold;
    }
    
    .sequence-card {
        background: #e3f2fd;
        border: 1px solid #1976d2;
        border-radius: 6px;
        padding: 0.5rem;
        margin: 0.3rem 0;
    }
    
    .missing-field {
        background: #ffebee;
        border: 1px solid #f44336;
        color: #d32f2f;
        padding: 0.5rem;
        border-radius: 4px;
        margin: 0.3rem 0;
    }
    
    .validation-success {
        background: #e8f5e9;
        border: 1px solid #4caf50;
        color: #2e7d32;
        padding: 0.5rem;
        border-radius: 4px;
    }
    
    .debug-info {
        background: #f0f0f0;
        padding: 0.5rem;
        border-radius: 4px;
        font-size: 0.8rem;
        color: #666;
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
    EMAIL = "email"
    PHONE = "phone"
    ADDRESS = "address"
    NAME = "name"
    UNKNOWN = "unknown"

# ===== DATA CLASSES =====
@dataclass
class FieldNumber:
    """Represents a parsed field number like 1.a or 2.b.iii"""
    main: int
    sub_letter: str = ""
    sub_number: str = ""
    sub_roman: str = ""
    
    def __str__(self):
        parts = [str(self.main)]
        if self.sub_letter:
            parts.append(self.sub_letter)
        if self.sub_number:
            parts.append(self.sub_number)
        if self.sub_roman:
            parts.append(self.sub_roman)
        return ".".join(parts)
    
    def to_sort_key(self) -> Tuple:
        """Return a tuple for sorting"""
        # Handle None values properly
        main_key = self.main if self.main is not None else 999
        letter_key = self.sub_letter if self.sub_letter else ""
        
        # Parse sub_number if it's a digit string
        if self.sub_number and self.sub_number.isdigit():
            number_key = int(self.sub_number)
        else:
            number_key = 999
            
        roman_key = self.sub_roman if self.sub_roman else ""
        
        return (main_key, letter_key, number_key, roman_key)

@dataclass
class ExtractedField:
    """Represents an extracted form field with its value"""
    item_number: str
    parsed_number: Optional[FieldNumber] = None
    label: str = ""
    value: str = ""
    field_type: FieldType = FieldType.UNKNOWN
    page: int = 1
    part_number: int = 1
    part_name: str = ""
    bbox: Optional[List[float]] = None
    confidence: float = 0.0
    raw_text: str = ""
    sequence_valid: bool = True
    
    def to_dict(self) -> Dict:
        return {
            'item_number': self.item_number,
            'label': self.label,
            'value': self.value,
            'type': self.field_type.value,
            'page': self.page,
            'part': self.part_number,
            'confidence': self.confidence,
            'sequence_valid': self.sequence_valid
        }

@dataclass 
class FormPart:
    """Represents a form part/section"""
    number: int
    title: str
    start_page: int = 1
    fields: List[ExtractedField] = field(default_factory=list)
    expected_sequence: List[str] = field(default_factory=list)
    missing_fields: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Initialize any missing attributes"""
        if not hasattr(self, 'missing_fields'):
            self.missing_fields = []
    
    def add_field(self, field: ExtractedField):
        field.part_number = self.number
        field.part_name = self.title
        self.fields.append(field)
    
    def sort_fields(self):
        """Sort fields by their parsed numbers"""
        try:
            self.fields.sort(key=lambda f: f.parsed_number.to_sort_key() if f.parsed_number else (999, "", 999, ""))
        except Exception as e:
            # If sorting fails, just leave in original order
            pass
    
    def validate_sequence(self):
        """Validate field sequence and find missing fields"""
        if not self.fields:
            return
        
        # Get all field numbers
        found_numbers = set()
        for field in self.fields:
            if field.parsed_number:
                found_numbers.add(str(field.parsed_number))
        
        # Check for missing numbers in common sequences
        self.missing_fields = []
        
        # Find the max main number
        max_main = max((f.parsed_number.main for f in self.fields if f.parsed_number), default=0)
        
        # Check main sequence
        for i in range(1, max_main + 1):
            if not any(f.parsed_number and f.parsed_number.main == i for f in self.fields):
                self.missing_fields.append(str(i))
        
        # Check for common sub-sequences (a, b, c)
        for field in self.fields:
            if field.parsed_number and field.parsed_number.sub_letter:
                main_num = field.parsed_number.main
                # Check if we have a sequence like 1.a, 1.b, 1.c
                for letter in 'abc':
                    expected = f"{main_num}.{letter}"
                    if not any(str(f.parsed_number) == expected for f in self.fields if f.parsed_number):
                        # Only add if we found at least one letter in this sequence
                        if any(f.parsed_number and f.parsed_number.main == main_num and f.parsed_number.sub_letter 
                               for f in self.fields):
                            if ord(letter) <= ord(field.parsed_number.sub_letter):
                                self.missing_fields.append(expected)

@dataclass
class ExtractionResult:
    """Complete extraction result"""
    form_number: str
    form_title: str
    parts: Dict[int, FormPart] = field(default_factory=dict)
    total_fields: int = 0
    filled_fields: int = 0
    empty_fields: int = 0
    sequence_issues: int = 0
    extraction_time: float = 0.0
    debug_info: List[str] = field(default_factory=list)
    validation_report: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize any missing attributes"""
        if not hasattr(self, 'sequence_issues'):
            self.sequence_issues = 0
    
    def calculate_stats(self):
        """Calculate statistics"""
        self.total_fields = sum(len(part.fields) for part in self.parts.values())
        self.filled_fields = sum(1 for part in self.parts.values() 
                                for field in part.fields if field.value and field.value.strip())
        self.empty_fields = self.total_fields - self.filled_fields
        
        # Calculate sequence issues safely
        try:
            self.sequence_issues = sum(len(getattr(part, 'missing_fields', [])) for part in self.parts.values())
        except:
            self.sequence_issues = 0

# ===== FIELD NUMBER PARSER =====
class FieldNumberParser:
    """Parse complex field numbers like 1.a, 2.b.iii, etc."""
    
    @staticmethod
    def parse(number_str: str) -> Optional[FieldNumber]:
        """Parse a field number string into components"""
        if not number_str:
            return None
        
        # Clean the number string
        number_str = number_str.strip().rstrip('.')
        
        # Patterns for different number formats
        patterns = [
            # 1.a.2 format
            r'^(\d+)\.([a-zA-Z])\.(\d+)$',
            # 1.a format
            r'^(\d+)\.([a-zA-Z])$',
            # 1a format (no dot)
            r'^(\d+)([a-zA-Z])$',
            # Just number
            r'^(\d+)$',
            # With parentheses like (1)
            r'^\((\d+)\)$',
            # Complex like 1.a.i
            r'^(\d+)\.([a-zA-Z])\.([ivxIVX]+)$',
        ]
        
        for pattern in patterns:
            match = re.match(pattern, number_str)
            if match:
                groups = match.groups()
                field_num = FieldNumber(main=int(groups[0]))
                
                if len(groups) > 1 and groups[1]:
                    field_num.sub_letter = groups[1].lower()
                
                if len(groups) > 2 and groups[2]:
                    if groups[2].isdigit():
                        field_num.sub_number = groups[2]
                    else:
                        field_num.sub_roman = groups[2].lower()
                
                return field_num
        
        return None
    
    @staticmethod
    def normalize_number(number_str: str) -> str:
        """Normalize a field number for comparison"""
        parsed = FieldNumberParser.parse(number_str)
        return str(parsed) if parsed else number_str

# ===== MAIN EXTRACTOR =====
class EnhancedUSCISFormExtractor:
    """Enhanced form extractor with sequence validation"""
    
    def __init__(self, debug_mode=False):
        self.doc = None
        self.form_info = {"number": "Unknown", "title": "Unknown Form"}
        self.debug_mode = debug_mode
        self.debug_logs = []
        self.field_parser = FieldNumberParser()
    
    def log(self, message: str):
        """Log debug message"""
        self.debug_logs.append(message)
        if self.debug_mode:
            st.write(f"🔍 {message}")
    
    def extract(self, pdf_file) -> ExtractionResult:
        """Extract form data from PDF"""
        start_time = time.time()
        
        try:
            # Open PDF
            if hasattr(pdf_file, 'read'):
                pdf_file.seek(0)
                pdf_bytes = pdf_file.read()
            else:
                pdf_bytes = pdf_file
                
            self.doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            self.log(f"Opened PDF with {len(self.doc)} pages")
            
            # Identify form
            self.form_info = self._identify_form()
            self.log(f"Identified form: {self.form_info['number']} - {self.form_info['title']}")
            
            # Create result with proper initialization
            result = ExtractionResult(
                form_number=self.form_info['number'],
                form_title=self.form_info['title'],
                sequence_issues=0  # Explicitly initialize
            )
            
            # Extract all text with positions
            all_text_blocks = []
            for page_num in range(len(self.doc)):
                try:
                    page = self.doc[page_num]
                    blocks = self._extract_page_data(page, page_num + 1)
                    all_text_blocks.extend(blocks)
                    self.log(f"Page {page_num + 1}: Found {len(blocks)} text blocks")
                except Exception as e:
                    self.log(f"Error extracting page {page_num + 1}: {str(e)}")
                    continue
            
            self.log(f"Total text blocks: {len(all_text_blocks)}")
            
            if not all_text_blocks:
                self.log("WARNING: No text blocks extracted from PDF!")
                self.log("This could mean:")
                self.log("1. The PDF is image-based (scanned) and needs OCR")
                self.log("2. The PDF has an unusual structure")
                self.log("3. The PDF is corrupted or encrypted")
                result.debug_info = self.debug_logs
                
                # Try to provide more info
                if self.doc and len(self.doc) > 0:
                    try:
                        # Check if PDF has text
                        sample_text = self.doc[0].get_text()
                        if not sample_text.strip():
                            self.log("The PDF appears to have no extractable text. It might be a scanned image.")
                        else:
                            self.log(f"Found some text but couldn't parse it: {sample_text[:200]}...")
                    except:
                        pass
                
                return result
            
            # Find parts
            parts_info = self._find_parts(all_text_blocks)
            self.log(f"Found {len(parts_info)} parts")
            
            # If no parts found, treat entire document as Part 1
            if not parts_info:
                parts_info = {
                    1: {
                        'title': 'Complete Form',
                        'start_idx': 0,
                        'end_idx': len(all_text_blocks) - 1,
                        'page': 1
                    }
                }
            
            # Extract fields for each part
            for part_num, part_info in parts_info.items():
                try:
                    part = FormPart(
                        number=part_num, 
                        title=part_info['title'],
                        start_page=part_info['page']
                    )
                    
                    # Get blocks for this part
                    start_idx = part_info['start_idx']
                    end_idx = part_info['end_idx']
                    
                    # Ensure indices are valid
                    if start_idx < 0 or end_idx >= len(all_text_blocks):
                        self.log(f"Part {part_num}: Invalid indices, skipping")
                        continue
                        
                    part_blocks = all_text_blocks[start_idx:end_idx + 1]
                    
                    self.log(f"Part {part_num}: Processing {len(part_blocks)} blocks")
                    
                    # Extract fields with enhanced parsing
                    fields = self._extract_fields_enhanced(part_blocks, part_info['page'])
                    
                    self.log(f"Part {part_num}: Found {len(fields)} fields")
                    
                    for field in fields:
                        part.add_field(field)
                    
                    # Sort fields by their parsed numbers
                    part.sort_fields()
                    
                    # Validate sequence
                    part.validate_sequence()
                    
                    result.parts[part_num] = part
                    
                except Exception as e:
                    self.log(f"Error processing part {part_num}: {str(e)}")
                    if self.debug_mode:
                        traceback.print_exc()
                    continue
            
            # Run validation
            try:
                result.validation_report = self._validate_extraction(result)
            except Exception as e:
                self.log(f"Error during validation: {str(e)}")
                result.validation_report = {}
            
            # Calculate stats
            result.calculate_stats()
            result.extraction_time = time.time() - start_time
            result.debug_info = self.debug_logs
            
            self.log(f"Extraction complete: {result.total_fields} fields, {result.filled_fields} filled, {result.sequence_issues} sequence issues")
            
            return result
            
        except Exception as e:
            self.log(f"CRITICAL ERROR during extraction: {str(e)}")
            if self.debug_mode:
                traceback.print_exc()
            
            # Return a minimal result object
            return ExtractionResult(
                form_number="ERROR",
                form_title="Extraction Failed",
                debug_info=self.debug_logs + [f"CRITICAL ERROR: {str(e)}"],
                sequence_issues=0
            )
    
    def _identify_form(self) -> Dict[str, str]:
        """Identify form type"""
        if not self.doc or self.doc.page_count == 0:
            return {"number": "Unknown", "title": "Unknown Form"}
        
        first_page_text = self.doc[0].get_text()
        
        # Common USCIS forms
        form_patterns = [
            (r'Form\s+(I-\d+[A-Z]?)', 'USCIS Immigration Form'),
            (r'Form\s+(N-\d+)', 'USCIS Naturalization Form'),
            (r'Form\s+(G-\d+)', 'USCIS General Form'),
            (r'Form\s+(AR-\d+)', 'USCIS Form'),
        ]
        
        for pattern, prefix in form_patterns:
            match = re.search(pattern, first_page_text, re.IGNORECASE)
            if match:
                form_number = match.group(1).upper()
                
                # Get specific titles
                titles = {
                    'I-130': 'Petition for Alien Relative',
                    'I-485': 'Application to Register Permanent Residence',
                    'I-765': 'Application for Employment Authorization',
                    'I-90': 'Application to Replace Permanent Resident Card',
                    'N-400': 'Application for Naturalization',
                    'I-539': 'Application to Extend/Change Nonimmigrant Status',
                    'I-751': 'Petition to Remove Conditions on Residence',
                    'I-140': 'Immigrant Petition for Alien Worker',
                    'I-129': 'Petition for Nonimmigrant Worker',
                    'G-1145': 'E-Notification of Application/Petition Acceptance'
                }
                
                title = titles.get(form_number, f"{prefix} {form_number}")
                return {"number": form_number, "title": title}
        
        return {"number": "Unknown", "title": "Unknown Form"}
    
    def _extract_page_data(self, page, page_num: int) -> List[Dict]:
        """Extract all text blocks with positions from page"""
        blocks = []
        
        try:
            # Method 1: Get text with detailed position info
            text_dict = page.get_text("dict")
            
            for block in text_dict["blocks"]:
                if block["type"] == 0:  # Text block
                    for line in block["lines"]:
                        line_text = ""
                        line_bbox = None
                        
                        for span in line["spans"]:
                            text = span["text"]
                            if text.strip():
                                if line_text and not line_text.endswith(' '):
                                    line_text += " "
                                line_text += text
                                
                                if line_bbox is None:
                                    line_bbox = list(span["bbox"])
                                else:
                                    # Extend bbox
                                    line_bbox[2] = max(line_bbox[2], span["bbox"][2])
                                    line_bbox[3] = max(line_bbox[3], span["bbox"][3])
                        
                        if line_text.strip():
                            blocks.append({
                                'text': line_text.strip(),
                                'page': page_num,
                                'bbox': line_bbox or [0, 0, 0, 0],
                                'y': line_bbox[1] if line_bbox else 0,
                                'x': line_bbox[0] if line_bbox else 0
                            })
            
            # Method 2: Also try simple text extraction as fallback
            if not blocks:
                self.log(f"Page {page_num}: No blocks from dict method, trying simple extraction")
                simple_text = page.get_text()
                if simple_text:
                    lines = simple_text.split('\n')
                    for idx, line in enumerate(lines):
                        if line.strip():
                            blocks.append({
                                'text': line.strip(),
                                'page': page_num,
                                'bbox': [0, idx * 20, 100, (idx + 1) * 20],  # Dummy bbox
                                'y': idx * 20,
                                'x': 0
                            })
            
            # Sort by position
            blocks.sort(key=lambda b: (b['y'], b['x']))
            
            # Log sample text from page
            if blocks and self.debug_mode:
                sample = blocks[0]['text'] if blocks else "No text"
                self.log(f"Page {page_num} sample: {sample[:100]}...")
                
        except Exception as e:
            self.log(f"Error extracting page {page_num}: {str(e)}")
            # Try simple fallback
            try:
                simple_text = page.get_text()
                if simple_text:
                    lines = simple_text.split('\n')
                    for idx, line in enumerate(lines):
                        if line.strip():
                            blocks.append({
                                'text': line.strip(),
                                'page': page_num,
                                'bbox': [0, idx * 20, 100, (idx + 1) * 20],
                                'y': idx * 20,
                                'x': 0
                            })
            except:
                pass
        
        return blocks
    
    def _find_parts(self, blocks: List[Dict]) -> Dict[int, Dict]:
        """Find all parts in the form"""
        parts = {}
        
        for i, block in enumerate(blocks):
            text = block['text']
            
            # Match part headers - multiple patterns
            patterns = [
                r'^Part\s+(\d+)[.:]*\s*(.*?)$',
                r'^PART\s+(\d+)[.:]*\s*(.*?)$',
                r'^Part\s+(\d+)\s*[-–—]\s*(.*?)$',
                r'^Part\s+(\d+)\.\s*(.*)$',
            ]
            
            for pattern in patterns:
                part_match = re.match(pattern, text, re.IGNORECASE)
                if part_match:
                    part_num = int(part_match.group(1))
                    title = part_match.group(2).strip() if part_match.lastindex >= 2 else ""
                    
                    # Get title from next line if needed
                    if not title and i + 1 < len(blocks):
                        next_text = blocks[i + 1]['text']
                        if not re.match(r'^\d+\.', next_text) and not re.match(r'^Part\s+', next_text, re.IGNORECASE):
                            title = next_text
                    
                    parts[part_num] = {
                        'title': title or f"Part {part_num}",
                        'start_idx': i,
                        'page': block['page']
                    }
                    break
        
        # Set end indices
        part_nums = sorted(parts.keys())
        for i, pn in enumerate(part_nums):
            if i + 1 < len(part_nums):
                parts[pn]['end_idx'] = parts[part_nums[i + 1]]['start_idx'] - 1
            else:
                parts[pn]['end_idx'] = len(blocks) - 1
        
        return parts
    
    def _extract_fields_enhanced(self, blocks: List[Dict], page_num: int) -> List[ExtractedField]:
        """Extract fields with enhanced number parsing"""
        fields = []
        i = 0
        
        # Enhanced field patterns
        field_patterns = [
            # Standard patterns with sub-numbering
            (r'^(\d+\.[a-zA-Z]\.?\d*)\.\s+(.+?)(?:\s*[:：]\s*(.*))?$', 'complex'),
            (r'^(\d+\.[a-zA-Z])\.\s+(.+?)(?:\s*[:：]\s*(.*))?$', 'letter_sub'),
            (r'^(\d+[a-zA-Z])\.\s+(.+?)(?:\s*[:：]\s*(.*))?$', 'letter_no_dot'),
            (r'^(\d+)\.\s+(.+?)(?:\s*[:：]\s*(.*))?$', 'simple'),
            (r'^([A-Z])\.\s+(.+?)(?:\s*[:：]\s*(.*))?$', 'capital'),
            (r'^([a-z])\.\s+(.+?)(?:\s*[:：]\s*(.*))?$', 'lowercase'),
            (r'^\((\d+)\)\s+(.+?)(?:\s*[:：]\s*(.*))?$', 'parentheses'),
            (r'^(\d+)\s+(.+?)(?:\s*[:：]\s*(.*))?$', 'no_dot'),
        ]
        
        while i < len(blocks):
            block = blocks[i]
            text = block['text']
            
            # Skip headers
            if re.match(r'^(Part|Page|Form|Section)\s+', text, re.IGNORECASE):
                i += 1
                continue
            
            # Try field patterns
            field_found = False
            
            for pattern, pattern_type in field_patterns:
                match = re.match(pattern, text)
                if match:
                    groups = match.groups()
                    item_num = groups[0]
                    label = groups[1].strip()
                    value = groups[2].strip() if len(groups) > 2 and groups[2] else ""
                    
                    # Skip if label is too short or looks like instructions
                    if len(label) < 3 or (label.startswith('(') and label.endswith(')')):
                        break
                    
                    # Parse the field number
                    parsed_num = self.field_parser.parse(item_num)
                    
                    # Create field
                    extracted_field = ExtractedField(
                        item_number=item_num,
                        parsed_number=parsed_num,
                        label=label,
                        value=value,
                        page=block.get('page', page_num),
                        bbox=block.get('bbox'),
                        raw_text=text
                    )
                    
                    # If no value on same line, look for it
                    if not value:
                        value = self._find_field_value(blocks, i, label)
                        extracted_field.value = value
                    
                    # Determine field type
                    extracted_field.field_type = self._determine_field_type(label, value)
                    
                    # Set confidence
                    extracted_field.confidence = 0.9 if value else 0.3
                    
                    fields.append(extracted_field)
                    field_found = True
                    break
            
            # Handle checkboxes
            if not field_found:
                checkbox_patterns = [
                    (r'^[□☐]\s*(.+)', False),
                    (r'^[☑☒✓✗×X]\s*(.+)', True),
                    (r'^\[\s*\]\s*(.+)', False),
                    (r'^\[[Xx✓]\]\s*(.+)', True),
                ]
                
                for pattern, is_checked in checkbox_patterns:
                    match = re.match(pattern, text)
                    if match:
                        label = match.group(1).strip()
                        
                        extracted_field = ExtractedField(
                            item_number=f"cb_{i}",
                            label=label,
                            value="Yes" if is_checked else "No",
                            field_type=FieldType.CHECKBOX,
                            page=block.get('page', page_num),
                            confidence=0.95,
                            raw_text=text
                        )
                        fields.append(extracted_field)
                        field_found = True
                        break
            
            i += 1
        
        return fields
    
    def _find_field_value(self, blocks: List[Dict], field_idx: int, label: str) -> str:
        """Find value for a field by looking at surrounding blocks"""
        if field_idx >= len(blocks) - 1:
            return ""
        
        field_block = blocks[field_idx]
        field_bbox = field_block.get('bbox', [0, 0, 0, 0])
        
        # Look at next few blocks
        for i in range(field_idx + 1, min(field_idx + 5, len(blocks))):
            next_block = blocks[i]
            next_text = next_block['text'].strip()
            next_bbox = next_block.get('bbox', [0, 0, 0, 0])
            
            # Skip if it's another field
            if any(re.match(pattern[0], next_text) for pattern, _ in [
                (r'^(\d+\.[a-zA-Z]\.?\d*)\.\s+', 'complex'),
                (r'^(\d+\.[a-zA-Z])\.\s+', 'letter_sub'),
                (r'^(\d+[a-zA-Z])\.\s+', 'letter_no_dot'),
                (r'^(\d+)\.\s+', 'simple'),
            ]):
                break
            
            # Skip checkboxes and headers
            if re.match(r'^[□☐☑☒✓✗×\[\]◯◉]\s*', next_text) or re.match(r'^(Part|Page|Form)\s+', next_text, re.IGNORECASE):
                continue
            
            # Skip if text is too long
            if len(next_text) > 200:
                continue
            
            # Check position - value might be on same line or line below
            if ((next_bbox[0] > field_bbox[2] - 50 and abs(next_bbox[1] - field_bbox[1]) < 20) or
                (next_bbox[1] > field_bbox[3] and next_bbox[1] - field_bbox[3] < 40)):
                
                if self._looks_like_value(next_text):
                    return next_text
        
        return ""
    
    def _looks_like_value(self, text: str) -> bool:
        """Check if text looks like a field value"""
        if len(text) < 2:
            return False
        
        # Common value patterns
        value_patterns = [
            r'^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$',  # Date
            r'^\d{3}-?\d{2}-?\d{4}$',  # SSN
            r'^[A-Z]\d{7,9}$',  # A-Number
            r'^\(\d{3}\)\s*\d{3}-?\d{4}$',  # Phone
            r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',  # Email
            r'^\d+\s+[A-Za-z\s]+,?\s+[A-Z]{2}\s+\d{5}',  # Address
            r'^[A-Z][a-z]+(\s+[A-Z][a-z]+)*$',  # Name
            r'^\d+$',  # Number
            r'^(Yes|No|N/A|None)$',  # Common answers
        ]
        
        for pattern in value_patterns:
            if re.match(pattern, text):
                return True
        
        # If it's a reasonable length and doesn't look like a label
        if 2 <= len(text) <= 50 and not text.endswith(':') and not text.endswith('?'):
            return True
        
        return False
    
    def _determine_field_type(self, label: str, value: str) -> FieldType:
        """Determine field type from label and value"""
        label_lower = label.lower()
        
        # Check by label patterns
        if any(word in label_lower for word in ['date', 'birth', 'expire', 'dob']):
            return FieldType.DATE
        elif any(word in label_lower for word in ['email', 'e-mail']):
            return FieldType.EMAIL
        elif any(word in label_lower for word in ['phone', 'telephone', 'mobile']):
            return FieldType.PHONE
        elif any(word in label_lower for word in ['number', 'no.', '#', 'ssn', 'a-number']):
            return FieldType.NUMBER
        elif any(word in label_lower for word in ['name']):
            return FieldType.NAME
        elif any(word in label_lower for word in ['address', 'street', 'city', 'state', 'zip']):
            return FieldType.ADDRESS
        
        # Check by value patterns
        if value:
            if re.match(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', value):
                return FieldType.DATE
            elif '@' in value:
                return FieldType.EMAIL
            elif re.match(r'[\(\d]\d{2,3}[\)-]?\s*\d{3}[\-]?\d{4}', value):
                return FieldType.PHONE
        
        return FieldType.TEXT
    
    def _validate_extraction(self, result: ExtractionResult) -> Dict[str, Any]:
        """Validate the extraction results"""
        report = {
            'total_parts': len(result.parts),
            'parts_validation': {},
            'overall_score': 0.0
        }
        
        if not result.parts:
            return report
        
        total_score = 0
        
        for part_num, part in result.parts.items():
            part_report = {
                'total_fields': len(part.fields),
                'filled_fields': sum(1 for f in part.fields if f.value),
                'missing_fields': part.missing_fields,
                'sequence_gaps': [],
                'duplicate_numbers': [],
                'score': 0.0
            }
            
            # Check for sequence gaps
            if part.fields:
                parsed_nums = [f.parsed_number for f in part.fields if f.parsed_number]
                if parsed_nums:
                    main_nums = sorted(set(pn.main for pn in parsed_nums))
                    for i in range(len(main_nums) - 1):
                        if main_nums[i+1] - main_nums[i] > 1:
                            for missing in range(main_nums[i] + 1, main_nums[i+1]):
                                part_report['sequence_gaps'].append(str(missing))
            
            # Check for duplicates
            seen_numbers = {}
            for field in part.fields:
                if field.item_number in seen_numbers:
                    part_report['duplicate_numbers'].append(field.item_number)
                else:
                    seen_numbers[field.item_number] = True
            
            # Calculate part score
            issues = len(part.missing_fields) + len(part_report['sequence_gaps']) + len(part_report['duplicate_numbers'])
            if part.fields:
                part_report['score'] = max(0, 100 - (issues * 5))
            else:
                part_report['score'] = 0
            
            total_score += part_report['score']
            report['parts_validation'][f'Part {part_num}'] = part_report
        
        # Calculate overall score
        if result.parts:
            report['overall_score'] = total_score / len(result.parts)
        
        return report

# ===== UI COMPONENTS =====
def display_enhanced_results(result: ExtractionResult):
    """Display extraction results with sequence validation"""
    if not result:
        st.info("No results to display")
        return
    
    # Summary metrics
    st.markdown("### 📊 Extraction Summary")
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Total Fields", result.total_fields)
    with col2:
        percentage = f"{result.filled_fields/result.total_fields*100:.0f}%" if result.total_fields > 0 else "0%"
        st.metric("Filled Fields", result.filled_fields, delta=percentage)
    with col3:
        st.metric("Empty Fields", result.empty_fields)
    with col4:
        sequence_issues = getattr(result, 'sequence_issues', 0)
        st.metric("Sequence Issues", sequence_issues, 
                 delta="Good" if sequence_issues == 0 else f"-{sequence_issues}")
    with col5:
        score = result.validation_report.get('overall_score', 0) if hasattr(result, 'validation_report') else 0
        st.metric("Validation Score", f"{score:.0f}%")
    
    # Validation Report
    if result.validation_report:
        with st.expander("📋 Validation Report", expanded=False):
            for part_name, part_report in result.validation_report.get('parts_validation', {}).items():
                st.markdown(f"**{part_name}**")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write(f"Fields: {part_report['total_fields']} (Filled: {part_report['filled_fields']})")
                with col2:
                    st.write(f"Missing: {len(part_report['missing_fields'])}")
                with col3:
                    st.write(f"Score: {part_report['score']:.0f}%")
                
                if part_report['missing_fields']:
                    st.markdown(f'<div class="missing-field">Missing fields: {", ".join(part_report["missing_fields"])}</div>', 
                               unsafe_allow_html=True)
                
                if part_report['sequence_gaps']:
                    st.markdown(f'<div class="missing-field">Sequence gaps: {", ".join(part_report["sequence_gaps"])}</div>', 
                               unsafe_allow_html=True)
                
                if part_report['duplicate_numbers']:
                    st.warning(f"Duplicate numbers found: {', '.join(part_report['duplicate_numbers'])}")
                
                st.markdown("---")
    
    # Display parts with sequence
    st.markdown("### 📋 Extracted Form Data by Part")
    
    if not result.parts:
        st.warning("No parts were extracted from the PDF.")
        if result.debug_info:
            with st.expander("Debug Information"):
                for log in result.debug_info:
                    st.text(log)
        return
    
    # Add filters
    col1, col2, col3 = st.columns(3)
    with col1:
        show_empty = st.checkbox("Show empty fields", value=True)
    with col2:
        show_sequence = st.checkbox("Show sequence numbers", value=True)
    with col3:
        field_type_filter = st.selectbox("Filter by type", ["All"] + [t.value for t in FieldType])
    
    for part_num in sorted(result.parts.keys()):
        part = result.parts[part_num]
        filled = sum(1 for f in part.fields if f.value and f.value.strip())
        
        # Part header with stats
        st.markdown(
            f'<div class="part-header">'
            f'Part {part_num}: {part.title}<br/>'
            f'<small>Page {part.start_page} | {len(part.fields)} fields | {filled} filled | '
            f'{len(part.missing_fields)} missing in sequence</small>'
            f'</div>',
            unsafe_allow_html=True
        )
        
        with st.expander(f"View Part {part_num} Details", expanded=(part_num == 1)):
            if not part.fields:
                st.warning("No fields found in this part")
            else:
                # Show missing fields alert
                if part.missing_fields:
                    st.markdown(
                        f'<div class="missing-field">⚠️ Missing fields in sequence: {", ".join(part.missing_fields)}</div>',
                        unsafe_allow_html=True
                    )
                
                # Create sequence view
                if show_sequence:
                    st.markdown("#### Field Sequence")
                    sequence_cols = st.columns(6)
                    for idx, field in enumerate(part.fields):
                        col_idx = idx % 6
                        with sequence_cols[col_idx]:
                            seq_class = "sequence-card" if field.sequence_valid else "missing-field"
                            st.markdown(
                                f'<div class="{seq_class}">{field.item_number}</div>',
                                unsafe_allow_html=True
                            )
                
                # Display fields
                st.markdown("#### Field Details")
                for field in part.fields:
                    # Apply filters
                    if not show_empty and not field.value:
                        continue
                    if field_type_filter != "All" and field.field_type.value != field_type_filter:
                        continue
                    
                    # Create field display
                    st.markdown('<div class="field-card">', unsafe_allow_html=True)
                    cols = st.columns([1, 3, 3, 1])
                    
                    with cols[0]:
                        # Field number with validation indicator
                        color = "green" if field.sequence_valid else "red"
                        st.markdown(
                            f'<span style="color:{color};font-weight:bold;">{field.item_number}</span>',
                            unsafe_allow_html=True
                        )
                    
                    with cols[1]:
                        # Field label
                        st.markdown(f"**{field.label}**")
                        st.caption(f"Type: {field.field_type.value} | Page: {field.page}")
                    
                    with cols[2]:
                        # Field value
                        if field.value and field.value.strip():
                            st.markdown(f'<div class="field-value">{field.value}</div>', 
                                      unsafe_allow_html=True)
                        else:
                            st.markdown('<div class="empty-value">Empty / No value found</div>', 
                                      unsafe_allow_html=True)
                    
                    with cols[3]:
                        # Confidence
                        conf_color = "green" if field.confidence > 0.7 else "orange" if field.confidence > 0.4 else "red"
                        st.markdown(f'<span style="color:{conf_color};font-weight:bold;">{field.confidence:.0%}</span>', 
                                  unsafe_allow_html=True)
                    
                    st.markdown('</div>', unsafe_allow_html=True)

def export_to_json_enhanced(result: ExtractionResult) -> str:
    """Export results to JSON with validation info"""
    export_data = {
        'form_info': {
            'number': result.form_number,
            'title': result.form_title,
            'total_fields': result.total_fields,
            'filled_fields': result.filled_fields,
            'empty_fields': result.empty_fields,
            'sequence_issues': result.sequence_issues,
            'extraction_time': result.extraction_time,
            'validation_score': result.validation_report.get('overall_score', 0)
        },
        'validation_report': result.validation_report,
        'parts': {}
    }
    
    for part_num, part in result.parts.items():
        part_data = {
            'title': part.title,
            'missing_fields': part.missing_fields,
            'fields': []
        }
        
        for field in part.fields:
            field_data = field.to_dict()
            field_data['parsed_number'] = str(field.parsed_number) if field.parsed_number else None
            part_data['fields'].append(field_data)
        
        export_data['parts'][f'part_{part_num}'] = part_data
    
    return json.dumps(export_data, indent=2)

def export_to_csv_enhanced(result: ExtractionResult) -> str:
    """Export results to CSV with sequence info"""
    rows = []
    
    for part_num, part in result.parts.items():
        for field in part.fields:
            rows.append({
                'Part': part_num,
                'Part Title': part.title,
                'Sequence': field.item_number,
                'Parsed Number': str(field.parsed_number) if field.parsed_number else "",
                'Label': field.label,
                'Value': field.value,
                'Type': field.field_type.value,
                'Page': field.page,
                'Confidence': f"{field.confidence:.0%}",
                'Has Value': 'Yes' if field.value else 'No',
                'Sequence Valid': 'Yes' if field.sequence_valid else 'No'
            })
    
    df = pd.DataFrame(rows)
    return df.to_csv(index=False)

# ===== MAIN APP =====
def main():
    st.markdown(
        '<div class="main-header">'
        '<h1>📋 Enhanced USCIS Form Reader</h1>'
        '<p>Extract fields with proper sequence validation (1a, 1b, 1c support)</p>'
        '</div>', 
        unsafe_allow_html=True
    )
    
    # Add a note about PDF requirements
    st.info("ℹ️ This tool works with fillable PDFs or PDFs with selectable text. Scanned/image PDFs require OCR processing first.")
    
    # Initialize session state
    if 'extraction_result' not in st.session_state:
        st.session_state.extraction_result = None
    if 'debug_mode' not in st.session_state:
        st.session_state.debug_mode = False
    
    # Sidebar
    with st.sidebar:
        st.markdown("## ⚙️ Settings")
        st.session_state.debug_mode = st.checkbox("Debug Mode", value=st.session_state.debug_mode)
        
        st.markdown("## 📄 About")
        st.info(
            "Enhanced extractor with:\n"
            "• Sub-numbering support (1a, 1b, 1c)\n"
            "• Sequence validation\n"
            "• Missing field detection\n"
            "• Part-by-part analysis"
        )
        
        st.markdown("## 🎯 Features")
        st.markdown("""
        ✅ Handles complex numbering  
        ✅ Validates field sequences  
        ✅ Detects missing fields  
        ✅ Shows extraction per part  
        ✅ Validation scoring  
        ✅ Enhanced reporting  
        """)
        
        if st.session_state.extraction_result:
            st.markdown("## 📊 Current Results")
            result = st.session_state.extraction_result
            st.write(f"Form: {result.form_number}")
            st.write(f"Fields: {result.total_fields}")
            st.write(f"Filled: {result.filled_fields}")
            
            # Safely access sequence_issues
            sequence_issues = getattr(result, 'sequence_issues', 0)
            st.write(f"Issues: {sequence_issues}")
            
            score = result.validation_report.get('overall_score', 0) if hasattr(result, 'validation_report') else 0
            if score >= 90:
                st.success(f"Validation: {score:.0f}% ✅")
            elif score >= 70:
                st.warning(f"Validation: {score:.0f}% ⚠️")
            else:
                st.error(f"Validation: {score:.0f}% ❌")
    
    # Main content
    tabs = st.tabs(["📤 Upload & Extract", "📊 View Results", "🔍 Validation", "💾 Export Data"])
    
    # Upload tab
    with tabs[0]:
        st.markdown("### Upload USCIS Form PDF")
        
        uploaded_file = st.file_uploader(
            "Choose a filled USCIS form PDF",
            type=['pdf'],
            help="Upload any USCIS form with proper field numbering"
        )
        
        if uploaded_file:
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                st.success(f"✅ File uploaded: {uploaded_file.name}")
                st.info("Click 'Extract Data' to process with sequence validation")
            
            with col2:
                if st.button("🔍 Test PDF", help="Quick test to verify PDF can be read"):
                    try:
                        uploaded_file.seek(0)
                        pdf_bytes = uploaded_file.read()
                        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                        st.write(f"Pages: {len(doc)}")
                        
                        # Get first page text
                        if len(doc) > 0:
                            first_page_text = doc[0].get_text()
                            if first_page_text.strip():
                                st.success("✅ PDF has extractable text")
                                st.text_area("First page preview:", first_page_text[:500], height=200)
                            else:
                                st.error("❌ No text found - PDF might be scanned/image-based")
                                st.info("This tool requires PDFs with selectable text. Scanned PDFs need OCR processing first.")
                                
                                # Check if page has images
                                img_list = doc[0].get_images()
                                if img_list:
                                    st.write(f"Found {len(img_list)} images on first page")
                        doc.close()
                        uploaded_file.seek(0)  # Reset file pointer
                    except Exception as e:
                        st.error(f"PDF Test Error: {str(e)}")
                        if hasattr(uploaded_file, 'seek'):
                            uploaded_file.seek(0)  # Reset file pointer
            
            with col3:
                if st.button("🚀 Extract Data", type="primary", use_container_width=True):
                    with st.spinner("Extracting and validating form data..."):
                        try:
                            # Show debug info during extraction
                            if st.session_state.debug_mode:
                                debug_container = st.container()
                                with debug_container:
                                    st.write("Starting extraction...")
                            
                            extractor = EnhancedUSCISFormExtractor(debug_mode=st.session_state.debug_mode)
                            result = extractor.extract(uploaded_file)
                            st.session_state.extraction_result = result
                            
                            # Always show debug info if extraction failed
                            if result.form_number == "ERROR" or result.total_fields == 0:
                                st.error("⚠️ Extraction failed or no fields found!")
                                with st.expander("Debug Information", expanded=True):
                                    for log in result.debug_info:
                                        st.text(log)
                                
                                # Show what we did extract
                                st.write(f"Form identified: {result.form_number}")
                                st.write(f"Parts found: {len(result.parts)}")
                                st.write(f"Total fields: {result.total_fields}")
                            elif result.total_fields > 0:
                                st.success(f"✅ Extracted {result.total_fields} fields from {len(result.parts)} parts!")
                                
                                # Show validation summary
                                score = result.validation_report.get('overall_score', 0)
                                if score >= 90:
                                    st.success(f"Validation Score: {score:.0f}% - Excellent extraction!")
                                elif score >= 70:
                                    st.warning(f"Validation Score: {score:.0f}% - Some issues detected")
                                else:
                                    st.error(f"Validation Score: {score:.0f}% - Multiple issues found")
                                
                                if result.sequence_issues > 0:
                                    st.warning(f"Found {result.sequence_issues} sequence issues")
                                
                                st.info("Check the 'View Results' and 'Validation' tabs for details")
                                st.balloons()
                            else:
                                st.warning("No fields were extracted. The PDF might not be a standard USCIS form.")
                                with st.expander("Debug Information"):
                                    for log in result.debug_info:
                                        st.text(log)
                            
                        except Exception as e:
                            st.error(f"Critical error during extraction: {str(e)}")
                            if st.session_state.debug_mode:
                                st.exception(e)
                            
                            # Try to show any debug info we have
                            if 'extractor' in locals():
                                st.write("Debug logs before error:")
                                for log in extractor.debug_logs:
                                    st.text(log)
    
    # Results tab
    with tabs[1]:
        if st.session_state.extraction_result:
            display_enhanced_results(st.session_state.extraction_result)
        else:
            st.info("No results yet. Please upload and extract a form first.")
    
    # Validation tab
    with tabs[2]:
        if st.session_state.extraction_result and st.session_state.extraction_result.total_fields > 0:
            result = st.session_state.extraction_result
            st.markdown("### 🔍 Detailed Validation Report")
            
            # Overall validation
            score = result.validation_report.get('overall_score', 0) if hasattr(result, 'validation_report') else 0
            if score >= 90:
                st.markdown('<div class="validation-success">✅ Extraction Quality: Excellent</div>', 
                           unsafe_allow_html=True)
            elif score >= 70:
                st.markdown('<div class="missing-field">⚠️ Extraction Quality: Good (Some Issues)</div>', 
                           unsafe_allow_html=True)
            else:
                st.markdown('<div class="missing-field">❌ Extraction Quality: Poor (Many Issues)</div>', 
                           unsafe_allow_html=True)
            
            # Part-by-part validation
            for part_num in sorted(result.parts.keys()):
                part = result.parts[part_num]
                part_report = result.validation_report.get('parts_validation', {}).get(f'Part {part_num}', {})
                
                with st.expander(f"Part {part_num}: {part.title}", expanded=True):
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("Total Fields", len(part.fields))
                    with col2:
                        missing_count = len(getattr(part, 'missing_fields', []))
                        st.metric("Missing in Sequence", missing_count)
                    with col3:
                        st.metric("Part Score", f"{part_report.get('score', 0):.0f}%")
                    
                    # Show field sequence
                    st.markdown("#### Expected vs Found Sequence")
                    
                    # Display found fields in order
                    if part.fields:
                        st.write("**Found fields:**")
                        field_nums = [f.item_number for f in part.fields]
                        st.write(", ".join(field_nums))
                    
                    # Display missing fields
                    if hasattr(part, 'missing_fields') and part.missing_fields:
                        st.write("**Missing fields:**")
                        st.error(", ".join(part.missing_fields))
                    
                    # Show any gaps or duplicates
                    if part_report.get('sequence_gaps'):
                        st.write("**Sequence gaps:**")
                        st.warning(", ".join(part_report['sequence_gaps']))
                    
                    if part_report.get('duplicate_numbers'):
                        st.write("**Duplicate numbers:**")
                        st.error(", ".join(part_report['duplicate_numbers']))
            
        else:
            st.info("No validation data available. Extract a form first.")
    
    # Export tab
    with tabs[3]:
        if st.session_state.extraction_result:
            st.markdown("### 💾 Export Extracted Data")
            
            result = st.session_state.extraction_result
            
            col1, col2 = st.columns(2)
            
            with col1:
                # JSON export
                json_data = export_to_json_enhanced(result)
                st.download_button(
                    "📦 Download as JSON (with validation)",
                    json_data,
                    f"{result.form_number}_extracted_validated.json",
                    mime="application/json",
                    use_container_width=True
                )
            
            with col2:
                # CSV export
                csv_data = export_to_csv_enhanced(result)
                st.download_button(
                    "📊 Download as CSV (with sequence)",
                    csv_data,
                    f"{result.form_number}_extracted_validated.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            # Preview options
            st.markdown("### 📄 Data Preview")
            preview_type = st.radio("Select preview format", 
                                  ["Summary", "Sequence Analysis", "Filled Fields", "All Fields", "JSON"])
            
            if preview_type == "Summary":
                st.json({
                    "form": result.form_number,
                    "title": result.form_title,
                    "total_fields": result.total_fields,
                    "filled_fields": result.filled_fields,
                    "parts": len(result.parts),
                    "sequence_issues": result.sequence_issues,
                    "validation_score": f"{result.validation_report.get('overall_score', 0):.0f}%"
                })
                
            elif preview_type == "Sequence Analysis":
                for part_num, part in result.parts.items():
                    st.write(f"**Part {part_num}:**")
                    
                    # Create sequence visualization
                    seq_data = []
                    for field in part.fields:
                        seq_data.append({
                            'Number': field.item_number,
                            'Parsed': str(field.parsed_number) if field.parsed_number else "N/A",
                            'Has Value': 'Yes' if field.value else 'No'
                        })
                    
                    if seq_data:
                        df = pd.DataFrame(seq_data)
                        st.dataframe(df)
                    
                    if part.missing_fields:
                        st.error(f"Missing: {', '.join(part.missing_fields)}")
                    
            elif preview_type == "Filled Fields":
                filled_data = []
                for part in result.parts.values():
                    for field in part.fields:
                        if field.value:
                            filled_data.append({
                                'Part': part.number,
                                'Number': field.item_number,
                                'Field': field.label,
                                'Value': field.value,
                                'Type': field.field_type.value
                            })
                
                if filled_data:
                    df = pd.DataFrame(filled_data)
                    st.dataframe(df)
                else:
                    st.warning("No filled fields found")
                    
            elif preview_type == "All Fields":
                df = pd.read_csv(io.StringIO(csv_data))
                st.dataframe(df)
                
            else:  # JSON
                st.json(json.loads(json_data))
            
        else:
            st.info("No data to export. Please process a form first.")

if __name__ == "__main__":
    if not PYMUPDF_AVAILABLE:
        st.error("❌ PyMuPDF is required but not installed!")
        st.code("pip install PyMuPDF streamlit pandas xlsxwriter")
        st.stop()
    
    main()
