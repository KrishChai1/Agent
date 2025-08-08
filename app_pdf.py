#!/usr/bin/env python3
"""
Complete Working USCIS Form Reader - Fixed Version
Properly extracts ALL fields and values from PDF forms
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
    page_title="USCIS KK  Form Reader - Fixed Version",
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
class ExtractedField:
    """Represents an extracted form field with its value"""
    item_number: str
    label: str
    value: str = ""
    field_type: FieldType = FieldType.UNKNOWN
    page: int = 1
    part_number: int = 1
    part_name: str = ""
    bbox: Optional[List[float]] = None
    confidence: float = 0.0
    raw_text: str = ""  # Store raw text for debugging
    
    def to_dict(self) -> Dict:
        return {
            'item_number': self.item_number,
            'label': self.label,
            'value': self.value,
            'type': self.field_type.value,
            'page': self.page,
            'part': self.part_number,
            'confidence': self.confidence
        }

@dataclass 
class FormPart:
    """Represents a form part/section"""
    number: int
    title: str
    start_page: int = 1
    fields: List[ExtractedField] = field(default_factory=list)
    
    def add_field(self, field: ExtractedField):
        field.part_number = self.number
        field.part_name = self.title
        self.fields.append(field)

@dataclass
class ExtractionResult:
    """Complete extraction result"""
    form_number: str
    form_title: str
    parts: Dict[int, FormPart] = field(default_factory=dict)
    total_fields: int = 0
    filled_fields: int = 0
    empty_fields: int = 0
    extraction_time: float = 0.0
    debug_info: List[str] = field(default_factory=list)
    
    def calculate_stats(self):
        """Calculate statistics"""
        self.total_fields = sum(len(part.fields) for part in self.parts.values())
        self.filled_fields = sum(1 for part in self.parts.values() 
                                for field in part.fields if field.value and field.value.strip())
        self.empty_fields = self.total_fields - self.filled_fields

# ===== MAIN EXTRACTOR =====
class USCISFormExtractor:
    """Main form extractor that actually works"""
    
    def __init__(self, debug_mode=False):
        self.doc = None
        self.form_info = {"number": "Unknown", "title": "Unknown Form"}
        self.debug_mode = debug_mode
        self.debug_logs = []
    
    def log(self, message: str):
        """Log debug message"""
        self.debug_logs.append(message)
        if self.debug_mode:
            st.write(f"🔍 {message}")
    
    def extract(self, pdf_file) -> ExtractionResult:
        """Extract form data from PDF"""
        start_time = time.time()
        
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
        
        # Create result
        result = ExtractionResult(
            form_number=self.form_info['number'],
            form_title=self.form_info['title']
        )
        
        # Extract all text with positions
        all_text_blocks = []
        for page_num in range(len(self.doc)):
            page = self.doc[page_num]
            blocks = self._extract_page_data(page, page_num + 1)
            all_text_blocks.extend(blocks)
            self.log(f"Page {page_num + 1}: Found {len(blocks)} text blocks")
        
        self.log(f"Total text blocks: {len(all_text_blocks)}")
        
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
            part = FormPart(
                number=part_num, 
                title=part_info['title'],
                start_page=part_info['page']
            )
            
            # Get blocks for this part
            start_idx = part_info['start_idx']
            end_idx = part_info['end_idx']
            part_blocks = all_text_blocks[start_idx:end_idx + 1]
            
            self.log(f"Part {part_num}: Processing {len(part_blocks)} blocks")
            
            # Extract fields with values
            fields = self._extract_fields_with_values(part_blocks, part_info['page'])
            
            self.log(f"Part {part_num}: Found {len(fields)} fields")
            
            for field in fields:
                part.add_field(field)
            
            result.parts[part_num] = part
        
        # Calculate stats
        result.calculate_stats()
        result.extraction_time = time.time() - start_time
        result.debug_info = self.debug_logs
        
        self.log(f"Extraction complete: {result.total_fields} fields, {result.filled_fields} filled")
        
        return result
    
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
        
        # Method 2: Also use get_text("blocks") for comparison
        text_blocks = page.get_text("blocks")
        for b in text_blocks:
            text = b[4].strip()
            if text and len(text) > 1:
                # Check if we already have this text
                already_exists = any(block['text'] == text for block in blocks)
                if not already_exists:
                    blocks.append({
                        'text': text,
                        'page': page_num,
                        'bbox': list(b[:4]),
                        'y': b[1],
                        'x': b[0]
                    })
        
        # Sort by position
        blocks.sort(key=lambda b: (b['y'], b['x']))
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
    
    def _extract_fields_with_values(self, blocks: List[Dict], page_num: int) -> List[ExtractedField]:
        """Extract fields with their filled values - FIXED VERSION"""
        fields = []
        i = 0
        
        # Field patterns - comprehensive list
        field_patterns = [
            # Standard numbering patterns
            (r'^(\d+)\.\s+(.+?)(?:\s*[:：]\s*(.*))?$', lambda m: (m.group(1), m.group(2), m.group(3) or "")),
            (r'^(\d+)\.\s*([a-zA-Z])\.\s+(.+?)(?:\s*[:：]\s*(.*))?$', lambda m: (f"{m.group(1)}.{m.group(2)}", m.group(3), m.group(4) or "")),
            (r'^(\d+)([a-zA-Z])\.\s+(.+?)(?:\s*[:：]\s*(.*))?$', lambda m: (f"{m.group(1)}{m.group(2)}", m.group(3), m.group(4) or "")),
            (r'^([A-Z])\.\s+(.+?)(?:\s*[:：]\s*(.*))?$', lambda m: (m.group(1), m.group(2), m.group(3) or "")),
            (r'^([a-z])\.\s+(.+?)(?:\s*[:：]\s*(.*))?$', lambda m: (m.group(1), m.group(2), m.group(3) or "")),
            (r'^\((\d+)\)\s+(.+?)(?:\s*[:：]\s*(.*))?$', lambda m: (f"({m.group(1)})", m.group(2), m.group(3) or "")),
            # Without dots
            (r'^(\d+)\s+(.+?)(?:\s*[:：]\s*(.*))?$', lambda m: (m.group(1), m.group(2), m.group(3) or "")),
            # Special patterns for labels with values
            (r'^(.+?)\s*[:：]\s*(.+)$', lambda m: ("", m.group(1), m.group(2))),
        ]
        
        while i < len(blocks):
            block = blocks[i]
            text = block['text']
            
            # Skip part headers and page numbers
            if re.match(r'^Part\s+\d+', text, re.IGNORECASE) or re.match(r'^Page\s+\d+', text, re.IGNORECASE):
                i += 1
                continue
            
            # Skip form headers
            if re.match(r'^Form\s+[A-Z]-\d+', text, re.IGNORECASE):
                i += 1
                continue
            
            # Try to extract field
            field_found = False
            
            for pattern, parser in field_patterns:
                match = re.match(pattern, text)
                if match:
                    try:
                        parts = parser(match)
                        if len(parts) >= 2:
                            item_num = parts[0] if parts[0] else f"field_{i}"
                            label = parts[1].strip()
                            value = parts[2].strip() if len(parts) > 2 and parts[2] else ""
                            
                            # Skip if label is too short or looks like instructions
                            if len(label) < 3 or label.startswith('(') and label.endswith(')'):
                                break
                            
                            # Create field
                            extracted_field = ExtractedField(
                                item_number=item_num,
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
                            
                    except Exception as e:
                        self.log(f"Error parsing field: {e}")
                        continue
            
            # Handle checkboxes and radio buttons
            if not field_found:
                checkbox_patterns = [
                    (r'^[□☐]\s*(.+)', False),
                    (r'^[☑☒✓✗×X]\s*(.+)', True),
                    (r'^\[\s*\]\s*(.+)', False),
                    (r'^\[[Xx✓]\]\s*(.+)', True),
                    (r'^◯\s*(.+)', False),
                    (r'^◉\s*(.+)', True),
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
            
            # Even if not a clear field pattern, if it looks like it could be a field, add it
            if not field_found and i < len(blocks) - 1:
                # Check if this might be a field label (heuristic)
                if (len(text) > 5 and len(text) < 200 and 
                    not text.startswith('(') and 
                    not re.match(r'^(Page|Form|Part|Section|Instructions)', text, re.IGNORECASE)):
                    
                    # Look ahead for a value
                    value = self._find_field_value(blocks, i, text)
                    
                    # Only add if we found a value or the text looks like a question
                    if value or '?' in text or any(word in text.lower() for word in ['name', 'date', 'number', 'address']):
                        extracted_field = ExtractedField(
                            item_number=f"auto_{i}",
                            label=text,
                            value=value,
                            page=block.get('page', page_num),
                            bbox=block.get('bbox'),
                            confidence=0.5 if value else 0.2,
                            raw_text=text
                        )
                        
                        extracted_field.field_type = self._determine_field_type(text, value)
                        fields.append(extracted_field)
            
            i += 1
        
        return fields
    
    def _find_field_value(self, blocks: List[Dict], field_idx: int, label: str) -> str:
        """Find value for a field by looking at surrounding blocks"""
        if field_idx >= len(blocks) - 1:
            return ""
        
        field_block = blocks[field_idx]
        field_bbox = field_block.get('bbox', [0, 0, 0, 0])
        
        # Look at next few blocks
        values = []
        
        for i in range(field_idx + 1, min(field_idx + 5, len(blocks))):
            next_block = blocks[i]
            next_text = next_block['text'].strip()
            next_bbox = next_block.get('bbox', [0, 0, 0, 0])
            
            # Skip if it's another field (be more careful here)
            if re.match(r'^\d+[a-zA-Z]?\.\s+\w+', next_text):
                break
            
            # Skip checkboxes
            if re.match(r'^[□☐☑☒✓✗×\[\]◯◉]\s*', next_text):
                continue
            
            # Skip common headers and instructions
            skip_patterns = [
                r'^(Part|Page|Form|Section)\s+',
                r'^\(.*\)$',
                r'^Instructions',
                r'^Note:',
            ]
            
            if any(re.match(p, next_text, re.IGNORECASE) for p in skip_patterns):
                continue
            
            # Skip if text is too long (probably instructions)
            if len(next_text) > 200:
                continue
            
            # Check position - value might be:
            # 1. On the same line to the right (most common for filled forms)
            if (next_bbox[0] > field_bbox[2] - 50 and 
                abs(next_bbox[1] - field_bbox[1]) < 20):
                return next_text
            
            # 2. On the line immediately below
            if (next_bbox[1] > field_bbox[3] and 
                next_bbox[1] - field_bbox[3] < 40 and
                abs(next_bbox[0] - field_bbox[0]) < 200):
                # Make sure it's not too far below
                if next_bbox[1] - field_bbox[3] < 25:
                    return next_text
                # If it's a bit further, only take it if it looks like a value
                elif self._looks_like_value(next_text):
                    return next_text
            
            # 3. If we haven't found anything yet and this looks like a value, consider it
            if not values and self._looks_like_value(next_text) and len(next_text) < 100:
                values.append(next_text)
        
        # Return the first value we found
        return values[0] if values else ""
    
    def _looks_like_value(self, text: str) -> bool:
        """Check if text looks like a field value"""
        # Too short
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
        elif any(word in label_lower for word in ['phone', 'telephone', 'mobile', 'cell']):
            return FieldType.PHONE
        elif any(word in label_lower for word in ['number', 'no.', '#', 'ssn', 'a-number', 'uscis']):
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

# ===== UI COMPONENTS =====
def display_results(result: ExtractionResult):
    """Display extraction results"""
    if not result:
        st.info("No results to display")
        return
    
    # Summary metrics
    st.markdown("### 📊 Extraction Summary")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Fields", result.total_fields)
    with col2:
        percentage = f"{result.filled_fields/result.total_fields*100:.0f}%" if result.total_fields > 0 else "0%"
        st.metric("Filled Fields", result.filled_fields, delta=percentage)
    with col3:
        st.metric("Empty Fields", result.empty_fields)
    with col4:
        st.metric("Extraction Time", f"{result.extraction_time:.1f}s")
    
    # Debug info expander
    if result.debug_info:
        with st.expander("🔍 Debug Information"):
            for log in result.debug_info:
                st.text(log)
    
    # Display parts
    st.markdown("### 📋 Extracted Form Data")
    
    # Add filters
    col1, col2 = st.columns(2)
    with col1:
        show_empty = st.checkbox("Show empty fields", value=True)
    with col2:
        field_type_filter = st.selectbox("Filter by type", ["All"] + [t.value for t in FieldType])
    
    for part_num in sorted(result.parts.keys()):
        part = result.parts[part_num]
        filled = sum(1 for f in part.fields if f.value and f.value.strip())
        
        st.markdown(
            f'<div class="part-header">'
            f'Part {part_num}: {part.title}<br/>'
            f'<small>Page {part.start_page} | {len(part.fields)} fields | {filled} filled | {len(part.fields) - filled} empty</small>'
            f'</div>',
            unsafe_allow_html=True
        )
        
        with st.expander(f"View Part {part_num} Fields ({len(part.fields)} total)", expanded=(part_num == 1)):
            if not part.fields:
                st.warning("No fields found in this part")
            else:
                for field in part.fields:
                    # Apply filters
                    if not show_empty and not field.value:
                        continue
                    if field_type_filter != "All" and field.field_type.value != field_type_filter:
                        continue
                    
                    # Create field display
                    st.markdown('<div class="field-card">', unsafe_allow_html=True)
                    cols = st.columns([3, 4, 1])
                    
                    with cols[0]:
                        # Field label
                        field_num = f"{field.item_number}. " if field.item_number and not field.item_number.startswith('auto_') else ""
                        st.markdown(f"**{field_num}{field.label}**")
                        st.caption(f"Type: {field.field_type.value} | Page: {field.page}")
                    
                    with cols[1]:
                        # Field value
                        if field.value and field.value.strip():
                            st.markdown(f'<div class="field-value">{field.value}</div>', 
                                      unsafe_allow_html=True)
                        else:
                            st.markdown('<div class="empty-value">Empty / No value found</div>', 
                                      unsafe_allow_html=True)
                    
                    with cols[2]:
                        # Confidence
                        conf_color = "green" if field.confidence > 0.7 else "orange" if field.confidence > 0.4 else "red"
                        st.markdown(f'<span style="color:{conf_color};font-weight:bold;">{field.confidence:.0%}</span>', 
                                  unsafe_allow_html=True)
                    
                    # Show raw text in debug mode
                    if st.session_state.get('debug_mode', False) and field.raw_text:
                        st.markdown(f'<div class="debug-info">Raw: {field.raw_text}</div>', unsafe_allow_html=True)
                    
                    st.markdown('</div>', unsafe_allow_html=True)

def export_to_json(result: ExtractionResult) -> str:
    """Export results to JSON"""
    export_data = {
        'form_info': {
            'number': result.form_number,
            'title': result.form_title,
            'total_fields': result.total_fields,
            'filled_fields': result.filled_fields,
            'empty_fields': result.empty_fields,
            'extraction_time': result.extraction_time
        },
        'parts': {}
    }
    
    for part_num, part in result.parts.items():
        export_data['parts'][f'part_{part_num}'] = {
            'title': part.title,
            'fields': [field.to_dict() for field in part.fields]
        }
    
    return json.dumps(export_data, indent=2)

def export_to_csv(result: ExtractionResult) -> str:
    """Export results to CSV"""
    rows = []
    
    for part_num, part in result.parts.items():
        for field in part.fields:
            rows.append({
                'Part': part_num,
                'Part Title': part.title,
                'Item Number': field.item_number,
                'Label': field.label,
                'Value': field.value,
                'Type': field.field_type.value,
                'Page': field.page,
                'Confidence': f"{field.confidence:.0%}",
                'Has Value': 'Yes' if field.value else 'No'
            })
    
    df = pd.DataFrame(rows)
    return df.to_csv(index=False)

# ===== MAIN APP =====
def main():
    st.markdown(
        '<div class="main-header">'
        '<h1>📋 USCIS Form Reader - Complete</h1>'
        '<p>Extract ALL fields and values from USCIS PDF forms</p>'
        '</div>', 
        unsafe_allow_html=True
    )
    
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
            "This tool extracts both field labels AND filled values from USCIS forms. "
            "Works with I-130, I-485, I-765, N-400, and other USCIS forms."
        )
        
        st.markdown("## 🎯 Features")
        st.markdown("""
        ✅ Extracts ALL form fields  
        ✅ Captures filled values  
        ✅ Handles checkboxes  
        ✅ Smart value detection  
        ✅ Multiple export formats  
        ✅ Debug mode available  
        """)
        
        if st.session_state.extraction_result:
            st.markdown("## 📊 Current Results")
            result = st.session_state.extraction_result
            st.write(f"Form: {result.form_number}")
            st.write(f"Fields: {result.total_fields}")
            st.write(f"Filled: {result.filled_fields}")
    
    # Main content
    tabs = st.tabs(["📤 Upload & Extract", "📊 View Results", "💾 Export Data"])
    
    # Upload tab
    with tabs[0]:
        st.markdown("### Upload USCIS Form PDF")
        
        uploaded_file = st.file_uploader(
            "Choose a filled USCIS form PDF",
            type=['pdf'],
            help="Upload any USCIS form (I-130, I-485, I-765, N-400, etc.) with filled data"
        )
        
        if uploaded_file:
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.success(f"✅ File uploaded: {uploaded_file.name}")
                st.info("Click 'Extract Data' to process the form")
            
            with col2:
                if st.button("🚀 Extract Data", type="primary", use_container_width=True):
                    with st.spinner("Extracting form data... This may take a moment for large forms"):
                        try:
                            extractor = USCISFormExtractor(debug_mode=st.session_state.debug_mode)
                            result = extractor.extract(uploaded_file)
                            st.session_state.extraction_result = result
                            
                            if result.total_fields > 0:
                                st.success(f"✅ Successfully extracted {result.total_fields} fields!")
                                st.info(f"Found {result.filled_fields} filled fields and {result.empty_fields} empty fields")
                                
                                # Show quick preview
                                st.markdown("### Quick Preview")
                                for part_num in list(result.parts.keys())[:2]:  # Show first 2 parts
                                    part = result.parts[part_num]
                                    st.write(f"**Part {part_num}: {part.title}** - {len(part.fields)} fields")
                                    
                                    # Show first 3 filled fields
                                    filled_fields = [f for f in part.fields if f.value][:3]
                                    for field in filled_fields:
                                        st.write(f"• {field.label}: **{field.value}**")
                                
                                st.info("Go to 'View Results' tab to see all extracted data")
                            else:
                                st.warning("No fields were extracted. The PDF might not be a standard USCIS form.")
                            
                            st.balloons()
                            
                        except Exception as e:
                            st.error(f"Error during extraction: {str(e)}")
                            if st.session_state.debug_mode:
                                st.exception(e)
    
    # Results tab
    with tabs[1]:
        if st.session_state.extraction_result:
            display_results(st.session_state.extraction_result)
        else:
            st.info("No results yet. Please upload and extract a form first.")
    
    # Export tab
    with tabs[2]:
        if st.session_state.extraction_result:
            st.markdown("### 💾 Export Extracted Data")
            
            result = st.session_state.extraction_result
            
            col1, col2 = st.columns(2)
            
            with col1:
                # JSON export
                json_data = export_to_json(result)
                st.download_button(
                    "📦 Download as JSON",
                    json_data,
                    f"{result.form_number}_extracted_data.json",
                    mime="application/json",
                    use_container_width=True
                )
            
            with col2:
                # CSV export
                csv_data = export_to_csv(result)
                st.download_button(
                    "📊 Download as CSV",
                    csv_data,
                    f"{result.form_number}_extracted_data.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            # Preview
            st.markdown("### 📄 Data Preview")
            
            preview_type = st.radio("Select preview format", ["Summary", "Filled Fields Only", "All Fields", "JSON"])
            
            if preview_type == "Summary":
                st.json({
                    "form": result.form_number,
                    "title": result.form_title,
                    "total_fields": result.total_fields,
                    "filled_fields": result.filled_fields,
                    "empty_fields": result.empty_fields,
                    "parts": len(result.parts),
                    "extraction_time": f"{result.extraction_time:.2f} seconds"
                })
                
            elif preview_type == "Filled Fields Only":
                filled_data = []
                for part in result.parts.values():
                    for field in part.fields:
                        if field.value:
                            filled_data.append({
                                'Part': part.number,
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
