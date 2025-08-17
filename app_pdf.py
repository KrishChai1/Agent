#!/usr/bin/env python3
"""
Complete Generic USCIS Form Processing System
- Properly detects ANY USCIS form type
- Dynamically extracts ALL parts and fields
- No hardcoded assumptions about form structure
- Works with I-90, I-130, I-485, N-400, G-28, I-129, etc.
"""

import os
import json
import re
import time
import sqlite3
import tempfile
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from contextlib import contextmanager

import streamlit as st
import pandas as pd

# Core imports with error handling
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    fitz = None
    st.error("❌ PyMuPDF not installed! Run: pip install PyMuPDF")

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    openai = None
    st.error("❌ OpenAI not installed! Run: pip install openai")

# Page config
st.set_page_config(
    page_title="Generic USCIS Form Processor",
    page_icon="🤖",
    layout="wide"
)

# CSS
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
    
    .field-card {
        background: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    
    .field-filled {
        background: #e8f5e9;
        border-left: 4px solid #28a745;
    }
    
    .field-empty {
        background: #fff3cd;
        border-left: 4px solid #ffc107;
    }
    
    .form-detection {
        background: #e3f2fd;
        border-left: 4px solid #2196f3;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 4px;
    }
</style>
""", unsafe_allow_html=True)

# ===== DATA CLASSES =====
@dataclass
class ExtractedField:
    field_number: str
    field_label: str
    field_value: str
    field_type: str = "text"
    confidence: float = 0.0
    is_required: bool = False
    manually_edited: bool = False
    page_number: int = 0
    
    def to_dict(self):
        return {
            'field_number': self.field_number,
            'field_label': self.field_label,
            'field_value': self.field_value,
            'field_type': self.field_type,
            'confidence': self.confidence,
            'is_required': self.is_required,
            'manually_edited': self.manually_edited,
            'page_number': self.page_number
        }

@dataclass
class FormPart:
    number: int
    title: str
    fields: List[ExtractedField] = field(default_factory=list)
    
    def add_field(self, field: ExtractedField):
        self.fields.append(field)
    
    def get_completion_rate(self):
        if not self.fields:
            return 0.0
        filled = sum(1 for f in self.fields if f.field_value and f.field_value.strip())
        return (filled / len(self.fields)) * 100

@dataclass
class FormResult:
    form_number: str
    form_title: str
    form_edition: str = ""
    total_pages: int = 0
    parts: Dict[int, FormPart] = field(default_factory=dict)
    total_fields: int = 0
    filled_fields: int = 0
    processing_time: float = 0.0
    
    def calculate_stats(self):
        self.total_fields = sum(len(part.fields) for part in self.parts.values())
        self.filled_fields = sum(1 for part in self.parts.values() 
                                for field in part.fields if field.field_value and field.field_value.strip())

# ===== DATABASE (Same as before) =====
class SimpleDatabase:
    def __init__(self, db_path: str = "uscis_generic.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS submissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    form_type TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_fields INTEGER DEFAULT 0,
                    filled_fields INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'processing',
                    data TEXT
                )
            ''')
            conn.commit()
    
    def save_submission(self, form_result: FormResult) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                INSERT INTO submissions (form_type, total_fields, filled_fields, data)
                VALUES (?, ?, ?, ?)
            ''', (
                form_result.form_number,
                form_result.total_fields,
                form_result.filled_fields,
                json.dumps({
                    'form_title': form_result.form_title,
                    'form_edition': form_result.form_edition,
                    'total_pages': form_result.total_pages,
                    'parts': {str(k): {
                        'title': v.title,
                        'fields': [f.to_dict() for f in v.fields]
                    } for k, v in form_result.parts.items()},
                    'processing_time': form_result.processing_time
                })
            ))
            return cursor.lastrowid
    
    def get_submissions(self, limit: int = 10):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT id, form_type, created_at, total_fields, filled_fields, status
                FROM submissions ORDER BY created_at DESC LIMIT ?
            ''', (limit,))
            return cursor.fetchall()
    
    def get_submission_data(self, submission_id: int):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT data FROM submissions WHERE id = ?', (submission_id,))
            result = cursor.fetchone()
            return json.loads(result[0]) if result else None

# ===== IMPROVED PDF EXTRACTION (Same as before) =====
@contextmanager
def safe_pdf_context(pdf_source):
    """Context manager for safe PDF handling"""
    doc = None
    try:
        if isinstance(pdf_source, bytes):
            doc = fitz.open(stream=pdf_source, filetype="pdf")
        else:
            doc = fitz.open(pdf_source)
        yield doc
    finally:
        if doc is not None:
            try:
                doc.close()
            except:
                pass

def extract_from_memory(pdf_bytes) -> str:
    """Extract PDF text directly from memory bytes"""
    doc = None
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        st.success(f"✅ PDF opened from memory - {len(doc)} pages")
        
        full_text = ""
        pages_with_text = 0
        
        for page_num in range(len(doc)):
            try:
                page = doc[page_num]
                page_text = page.get_text()
                
                if page_text.strip():
                    full_text += f"\n=== PAGE {page_num + 1} ===\n{page_text}\n"
                    pages_with_text += 1
                    
            except Exception as e:
                st.warning(f"⚠️ Error on page {page_num + 1}: {str(e)}")
                continue
        
        if not full_text.strip():
            st.warning("⚠️ No text found in memory extraction")
            return ""
        
        st.success(f"✅ Memory extraction: {pages_with_text}/{len(doc)} pages")
        return full_text
        
    except Exception as e:
        st.warning(f"⚠️ Memory extraction failed: {str(e)}")
        return ""
    finally:
        if doc is not None:
            try:
                doc.close()
            except:
                pass

def extract_from_temp_file(pdf_bytes) -> str:
    """Extract PDF text using temporary file approach"""
    temp_file_path = None
    doc = None
    
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            temp_file.write(pdf_bytes)
            temp_file_path = temp_file.name
        
        doc = fitz.open(temp_file_path)
        st.success(f"✅ PDF opened from file - {len(doc)} pages")
        
        full_text = ""
        pages_with_text = 0
        
        for page_num in range(len(doc)):
            try:
                page = doc[page_num]
                page_text = page.get_text()
                
                if page_text.strip():
                    full_text += f"\n=== PAGE {page_num + 1} ===\n{page_text}\n"
                    pages_with_text += 1
                    
            except Exception as e:
                st.warning(f"⚠️ Error on page {page_num + 1}: {str(e)}")
                continue
        
        if not full_text.strip():
            st.error("❌ No text found - this might be an image-based PDF")
            return ""
        
        st.success(f"✅ File extraction: {pages_with_text}/{len(doc)} pages")
        return full_text
        
    except Exception as e:
        st.error(f"❌ File extraction failed: {str(e)}")
        return ""
    finally:
        if doc is not None:
            try:
                doc.close()
            except:
                pass
        
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except:
                pass

def extract_pdf_text_simple(pdf_file) -> str:
    """Main PDF extraction function with multiple fallback methods"""
    try:
        st.info(f"📄 Processing file: {pdf_file.name}")
        
        pdf_file.seek(0)
        pdf_bytes = pdf_file.read()
        
        if len(pdf_bytes) == 0:
            st.error("❌ File is empty")
            return ""
        
        st.success(f"✅ Read {len(pdf_bytes):,} bytes")
        
        if not pdf_bytes.startswith(b'%PDF'):
            st.error("❌ Not a valid PDF file")
            return ""
        
        # Try memory extraction first
        full_text = extract_from_memory(pdf_bytes)
        if full_text:
            return full_text
        
        # Fallback to temporary file
        st.info("🔄 Trying alternative extraction method...")
        full_text = extract_from_temp_file(pdf_bytes)
        if full_text:
            return full_text
        
        st.error("❌ All extraction methods failed")
        return ""
        
    except Exception as e:
        st.error(f"💥 PDF extraction failed: {str(e)}")
        return ""

# ===== GENERIC FORM DETECTION =====
def detect_form_info(pdf_text: str) -> tuple:
    """Generic form detection that works for any USCIS form"""
    
    # Extract form number - look for "Form [LETTER-NUMBER]"
    form_patterns = [
        r'Form\s+([A-Z]-?\d+[A-Z]?)',  # Form I-90, Form N-400, etc.
        r'USCIS\s+Form\s+([A-Z]-?\d+[A-Z]?)',
        r'Form\s+([A-Z]\d+[A-Z]?)',  # FormI90, etc.
    ]
    
    form_number = "Unknown"
    for pattern in form_patterns:
        match = re.search(pattern, pdf_text, re.IGNORECASE)
        if match:
            form_number = match.group(1).upper()
            # Ensure hyphen format
            if re.match(r'^[A-Z]\d', form_number) and '-' not in form_number:
                form_number = form_number[0] + '-' + form_number[1:]
            break
    
    # Extract form title - usually appears after form number
    title_patterns = [
        rf'Form\s+{re.escape(form_number)}.*?\n(.+?)(?:\n|Department)',
        rf'{re.escape(form_number)}.*?\n(.+?)(?:\n|Department)',
        r'(?:Form\s+[A-Z]-?\d+[A-Z]?.*?\n)(.+?)(?:\n|Department)',
    ]
    
    form_title = f"USCIS Form {form_number}"
    for pattern in title_patterns:
        match = re.search(pattern, pdf_text, re.IGNORECASE | re.DOTALL)
        if match:
            title = match.group(1).strip()
            if len(title) > 10 and len(title) < 100:  # Reasonable title length
                form_title = title
                break
    
    # Extract edition/date
    edition_patterns = [
        r'Edition\s+(\d{2}/\d{2}/\d{2,4})',
        r'Rev\.\s+(\d{2}/\d{2}/\d{2,4})',
        r'(\d{2}/\d{2}/\d{2,4})\s+Edition',
    ]
    
    edition = ""
    for pattern in edition_patterns:
        match = re.search(pattern, pdf_text, re.IGNORECASE)
        if match:
            edition = match.group(1)
            break
    
    # Count total pages
    page_count = len(re.findall(r'=== PAGE \d+ ===', pdf_text))
    
    return form_number, form_title, edition, page_count

def extract_all_parts(pdf_text: str) -> List[dict]:
    """Dynamically extract all parts from any USCIS form"""
    
    parts = []
    
    # Find all "Part X." patterns
    part_patterns = [
        r'Part\s+(\d+)\.\s*(.+?)(?=\n)',
        r'PART\s+(\d+)\.\s*(.+?)(?=\n)',
        r'Part\s+(\d+)\s*-\s*(.+?)(?=\n)',
        r'Part\s+(\d+)\s*:\s*(.+?)(?=\n)',
    ]
    
    found_parts = set()
    
    for pattern in part_patterns:
        matches = re.finditer(pattern, pdf_text, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            part_num = int(match.group(1))
            part_title = match.group(2).strip()
            
            # Clean up the title
            part_title = re.sub(r'\s+', ' ', part_title)
            part_title = part_title.replace('(continued)', '').strip()
            
            if part_num not in found_parts and part_title and len(part_title) > 3:
                found_parts.add(part_num)
                parts.append({
                    'number': part_num,
                    'title': part_title,
                    'raw_text': extract_part_text(pdf_text, part_num)
                })
    
    # Sort by part number
    parts.sort(key=lambda x: x['number'])
    
    return parts

def extract_part_text(pdf_text: str, part_num: int) -> str:
    """Extract text for a specific part"""
    
    # Find start of this part
    start_patterns = [
        rf'Part\s+{part_num}\..*?\n',
        rf'PART\s+{part_num}\..*?\n',
    ]
    
    start_pos = -1
    for pattern in start_patterns:
        match = re.search(pattern, pdf_text, re.IGNORECASE)
        if match:
            start_pos = match.end()
            break
    
    if start_pos == -1:
        return ""
    
    # Find end of this part (start of next part or end of document)
    next_part_patterns = [
        rf'Part\s+{part_num + 1}\..*?\n',
        rf'PART\s+{part_num + 1}\..*?\n',
    ]
    
    end_pos = len(pdf_text)
    for pattern in next_part_patterns:
        match = re.search(pattern, pdf_text[start_pos:], re.IGNORECASE)
        if match:
            end_pos = start_pos + match.start()
            break
    
    return pdf_text[start_pos:end_pos]

# ===== IMPROVED AI EXTRACTION =====
def extract_form_data_generic(pdf_text: str, openai_client) -> FormResult:
    """Generic AI extraction that works for any USCIS form"""
    
    try:
        st.info("🤖 Starting generic AI extraction...")
        
        # Step 1: Detect form information
        form_number, form_title, edition, page_count = detect_form_info(pdf_text)
        
        st.markdown(f"""
        <div class="form-detection">
        <h4>📋 Form Detection Results</h4>
        <p><strong>Form Number:</strong> {form_number}</p>
        <p><strong>Title:</strong> {form_title}</p>
        <p><strong>Edition:</strong> {edition}</p>
        <p><strong>Pages:</strong> {page_count}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Step 2: Extract all parts dynamically
        st.info("🔍 Extracting form parts...")
        parts_info = extract_all_parts(pdf_text)
        
        if not parts_info:
            st.warning("⚠️ No parts detected, using full document")
            parts_info = [{'number': 1, 'title': 'Form Data', 'raw_text': pdf_text}]
        
        st.success(f"✅ Found {len(parts_info)} parts: {', '.join([f'Part {p['number']}' for p in parts_info])}")
        
        # Step 3: Process each part with AI
        result = FormResult(
            form_number=form_number,
            form_title=form_title,
            form_edition=edition,
            total_pages=page_count
        )
        
        for part_info in parts_info:
            st.info(f"🔄 Processing Part {part_info['number']}: {part_info['title']}")
            
            part_result = extract_part_with_ai(
                part_info['raw_text'], 
                openai_client, 
                form_number, 
                part_info['number'], 
                part_info['title']
            )
            
            if part_result:
                result.parts[part_info['number']] = part_result
                st.success(f"✅ Part {part_info['number']}: {len(part_result.fields)} fields extracted")
            else:
                st.warning(f"⚠️ Part {part_info['number']}: No fields extracted")
        
        # Calculate final stats
        result.calculate_stats()
        st.success(f"🎉 Extraction complete! {result.total_fields} total fields, {result.filled_fields} filled")
        
        return result
        
    except Exception as e:
        st.error(f"💥 Generic extraction failed: {str(e)}")
        return create_empty_result("Unknown")

def extract_part_with_ai(part_text: str, openai_client, form_number: str, part_num: int, part_title: str) -> FormPart:
    """Extract fields from a single part using AI"""
    
    try:
        # Truncate if too long
        max_length = 8000
        if len(part_text) > max_length:
            part_text = part_text[:max_length] + "\n[...truncated...]"
        
        # Create generic extraction prompt
        prompt = f"""
Extract all form fields from this USCIS {form_number} Part {part_num} ({part_title}).

Return ONLY valid JSON in this exact format:
{{
  "fields": [
    {{
      "field_number": "1.a",
      "field_label": "Family Name (Last Name)",
      "field_value": "extracted_value_or_empty_string",
      "field_type": "text",
      "confidence": 0.85,
      "is_required": true
    }}
  ]
}}

IMPORTANT RULES:
1. Extract ALL visible form fields, even if empty
2. Include field numbers like "1.a", "2.b", "3.c" etc.
3. Extract exact field labels as shown
4. Set field_value to actual value found, or empty string if blank
5. Determine field_type: "text", "date", "checkbox", "select", "number", "address", "phone", "email"
6. Set confidence based on how certain you are about the extraction
7. Mark as required if the field appears mandatory
8. Do NOT include page headers, instructions, or non-field text
9. Focus only on actual form input fields

Part text to analyze:
{part_text}
"""
        
        # Call OpenAI
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=4000,
            timeout=30
        )
        
        response_text = response.choices[0].message.content.strip()
        
        # Parse JSON response
        try:
            if '```json' in response_text:
                response_text = response_text.split('```json')[1].split('```')[0]
            elif '```' in response_text:
                response_text = response_text.split('```')[1].split('```')[0]
            
            data = json.loads(response_text.strip())
        except json.JSONDecodeError as e:
            st.warning(f"⚠️ JSON parsing failed for Part {part_num}: {str(e)}")
            return None
        
        # Create FormPart
        part = FormPart(number=part_num, title=part_title)
        
        for field_data in data.get('fields', []):
            field = ExtractedField(
                field_number=field_data.get('field_number', ''),
                field_label=field_data.get('field_label', ''),
                field_value=field_data.get('field_value', ''),
                field_type=field_data.get('field_type', 'text'),
                confidence=field_data.get('confidence', 0.5),
                is_required=field_data.get('is_required', False)
            )
            part.add_field(field)
        
        return part
        
    except Exception as e:
        st.warning(f"⚠️ AI extraction failed for Part {part_num}: {str(e)}")
        return None

def create_empty_result(form_type: str) -> FormResult:
    """Create empty result when extraction fails"""
    result = FormResult(
        form_number=form_type,
        form_title=f"USCIS Form {form_type}"
    )
    
    part = FormPart(number=1, title="Form Data")
    result.parts[1] = part
    
    return result

# ===== OPENAI CLIENT =====
def get_openai_client():
    """Get OpenAI client"""
    try:
        api_key = st.secrets.get("OPENAI_API_KEY")
        if not api_key:
            st.error("🔑 OpenAI API key not found in Streamlit secrets!")
            return None
        
        client = openai.OpenAI(api_key=api_key)
        
        # Test the key
        try:
            test_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1
            )
            st.sidebar.success("🔑 OpenAI API connected!")
            return client
        except Exception as e:
            st.error(f"❌ OpenAI API test failed: {str(e)}")
            return None
            
    except Exception as e:
        st.error(f"❌ OpenAI setup failed: {str(e)}")
        return None

# ===== UI COMPONENTS =====
def display_extraction_results(result: FormResult):
    """Display extraction results with editing capabilities"""
    
    if not result or not result.parts:
        st.warning("No extraction results to display")
        return
    
    st.markdown("## 📋 Extracted Form Data")
    
    # Form info
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Form", result.form_number)
    with col2:
        st.metric("Total Fields", result.total_fields)
    with col3:
        st.metric("Filled Fields", result.filled_fields)
    with col4:
        fill_rate = (result.filled_fields / result.total_fields * 100) if result.total_fields > 0 else 0
        st.metric("Completion", f"{fill_rate:.0f}%")
    
    # Display form details
    with st.expander("📄 Form Details", expanded=False):
        st.write(f"**Title:** {result.form_title}")
        if result.form_edition:
            st.write(f"**Edition:** {result.form_edition}")
        if result.total_pages:
            st.write(f"**Pages:** {result.total_pages}")
    
    # Display each part
    for part_num in sorted(result.parts.keys()):
        part = result.parts[part_num]
        completion = part.get_completion_rate()
        
        with st.expander(f"Part {part_num}: {part.title} ({len(part.fields)} fields - {completion:.0f}% complete)", 
                        expanded=(part_num == 1)):
            
            if not part.fields:
                st.info("No fields found in this part")
                continue
            
            # Display fields
            for i, field in enumerate(part.fields):
                display_field_editor(field, f"{part_num}_{i}")

def display_field_editor(field: ExtractedField, field_key: str):
    """Display individual field with editing capability"""
    
    has_value = field.field_value and field.field_value.strip()
    css_class = "field-filled" if has_value else "field-empty"
    
    st.markdown(f'<div class="field-card {css_class}">', unsafe_allow_html=True)
    
    # Field header
    col1, col2, col3 = st.columns([2, 3, 1])
    
    with col1:
        st.markdown(f"**{field.field_number}**")
        if field.is_required:
            st.markdown("🔴 Required")
        if field.manually_edited:
            st.markdown("✏️ Edited")
    
    with col2:
        st.markdown(f"**{field.field_label}**")
        st.caption(f"Type: {field.field_type} | Confidence: {field.confidence:.0%}")
    
    with col3:
        if field.confidence < 0.5:
            st.markdown("⚠️ Low Confidence")
    
    # Value editor
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # Different input types based on field type
        if field.field_type == "checkbox":
            new_value = st.selectbox(
                "Value:",
                ["", "Yes", "No", "N/A"],
                index=["", "Yes", "No", "N/A"].index(field.field_value) if field.field_value in ["", "Yes", "No", "N/A"] else 0,
                key=f"field_{field_key}"
            )
        elif field.field_type == "date":
            if field.field_value:
                try:
                    date_val = pd.to_datetime(field.field_value).date()
                except:
                    date_val = None
            else:
                date_val = None
            
            date_input = st.date_input(
                "Date:",
                value=date_val,
                key=f"field_{field_key}"
            )
            new_value = str(date_input) if date_input else ""
        elif field.field_type == "select":
            # For select fields, show as text input for now
            new_value = st.text_input(
                "Value:",
                value=field.field_value,
                placeholder="Select option...",
                key=f"field_{field_key}"
            )
        else:
            new_value = st.text_input(
                "Value:",
                value=field.field_value,
                placeholder=f"Enter {field.field_type}...",
                key=f"field_{field_key}"
            )
        
        # Update field if changed
        if new_value != field.field_value:
            field.field_value = new_value
            field.manually_edited = True
    
    with col2:
        if st.button(f"❌", key=f"clear_{field_key}", help="Clear field"):
            field.field_value = ""
            field.manually_edited = True
            st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

def display_database_tab(db: SimpleDatabase):
    """Display database management"""
    st.markdown("## 💾 Saved Forms")
    
    submissions = db.get_submissions(20)
    
    if not submissions:
        st.info("No saved forms yet")
        return
    
    # Display submissions table
    df = pd.DataFrame(submissions, columns=['ID', 'Form Type', 'Created', 'Total Fields', 'Filled Fields', 'Status'])
    st.dataframe(df, use_container_width=True)
    
    # Load specific submission
    if submissions:
        selected_id = st.selectbox(
            "Load saved form:",
            [f"ID {s[0]} - {s[1]} ({s[2]})" for s in submissions]
        )
        
        if st.button("📂 Load Form"):
            submission_id = int(selected_id.split()[1])
            load_submission(db, submission_id)

def load_submission(db: SimpleDatabase, submission_id: int):
    """Load submission from database"""
    try:
        data = db.get_submission_data(submission_id)
        if not data:
            st.error("Submission not found")
            return
        
        # Convert back to FormResult
        result = FormResult(
            form_number=data.get('form_title', 'Unknown'),
            form_title=data.get('form_title', 'Unknown Form'),
            form_edition=data.get('form_edition', ''),
            total_pages=data.get('total_pages', 0)
        )
        
        # Rebuild parts
        for part_num_str, part_data in data.get('parts', {}).items():
            part_num = int(part_num_str)
            part = FormPart(
                number=part_num,
                title=part_data.get('title', f'Part {part_num}')
            )
            
            for field_data in part_data.get('fields', []):
                field = ExtractedField(
                    field_number=field_data.get('field_number', ''),
                    field_label=field_data.get('field_label', ''),
                    field_value=field_data.get('field_value', ''),
                    field_type=field_data.get('field_type', 'text'),
                    confidence=field_data.get('confidence', 0.5),
                    is_required=field_data.get('is_required', False),
                    manually_edited=field_data.get('manually_edited', False),
                    page_number=field_data.get('page_number', 0)
                )
                part.add_field(field)
            
            result.parts[part_num] = part
        
        result.calculate_stats()
        
        # Store in session state
        st.session_state.current_result = result
        st.success(f"✅ Loaded form: {result.form_number}")
        st.rerun()
        
    except Exception as e:
        st.error(f"Error loading submission: {e}")

# ===== MAIN APPLICATION =====
def main():
    st.markdown(
        '<div class="main-header">'
        '<h1>🤖 Generic USCIS Form Processor</h1>'
        '<p>AI-powered extraction for ANY USCIS form - I-90, I-130, I-485, N-400, G-28, I-129, etc.</p>'
        '</div>', 
        unsafe_allow_html=True
    )
    
    # Check dependencies
    if not PYMUPDF_AVAILABLE or not OPENAI_AVAILABLE:
        st.error("❌ Missing required dependencies!")
        st.stop()
    
    # Initialize
    if 'db' not in st.session_state:
        st.session_state.db = SimpleDatabase()
    
    if 'current_result' not in st.session_state:
        st.session_state.current_result = None
    
    db = st.session_state.db
    
    # Get OpenAI client
    openai_client = get_openai_client()
    if not openai_client:
        st.error("❌ OpenAI client not available")
        st.stop()
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 🔧 Settings")
        debug_mode = st.checkbox("Debug Mode", False)
        
        st.markdown("## 📊 Stats")
        submissions = db.get_submissions(5)
        st.metric("Total Forms", len(submissions))
        
        if st.button("🗑️ Clear Database"):
            if st.confirm("Delete all data?"):
                os.remove(db.db_path)
                st.session_state.db = SimpleDatabase()
                st.success("Database cleared!")
                st.rerun()
    
    # Main tabs
    tab1, tab2, tab3 = st.tabs(["📤 Upload & Extract", "✏️ Edit Fields", "💾 Database"])
    
    with tab1:
        st.markdown("### 📤 Upload ANY USCIS Form PDF")
        
        uploaded_file = st.file_uploader(
            "Choose a USCIS form PDF",
            type=['pdf'],
            help="Upload any USCIS form - I-90, I-130, I-485, N-400, G-28, I-129, etc."
        )
        
        if uploaded_file:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.success(f"✅ File: {uploaded_file.name}")
            
            with col2:
                if st.button("🔍 Test PDF Read"):
                    with st.spinner("Testing PDF..."):
                        text = extract_pdf_text_simple(uploaded_file)
                        if text:
                            st.success("✅ PDF readable!")
                            with st.expander("Preview"):
                                st.text_area("First 300 chars:", text[:300], height=100)
                        else:
                            st.error("❌ Cannot read PDF")
            
            if st.button("🚀 Extract Form Data", type="primary"):
                with st.spinner("Processing..."):
                    # Step 1: Extract PDF text
                    st.markdown("#### Step 1: PDF Text Extraction")
                    pdf_text = extract_pdf_text_simple(uploaded_file)
                    
                    if not pdf_text:
                        st.error("Cannot proceed without PDF text")
                        st.stop()
                    
                    # Debug: Show text preview
                    if debug_mode:
                        with st.expander("🔍 Extracted Text Preview"):
                            st.text_area("Raw text:", pdf_text[:1000], height=200)
                    
                    # Step 2: Generic AI Extraction
                    st.markdown("#### Step 2: Generic AI Data Extraction")
                    start_time = time.time()
                    
                    result = extract_form_data_generic(pdf_text, openai_client)
                    
                    if result and result.parts:
                        result.processing_time = time.time() - start_time
                        
                        # Save to database
                        submission_id = db.save_submission(result)
                        st.success(f"✅ Saved to database (ID: {submission_id})")
                        
                        # Store in session
                        st.session_state.current_result = result
                        
                        # Show immediate results
                        st.markdown("#### 🎉 Extraction Results")
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Total Fields", result.total_fields)
                        with col2:
                            st.metric("Filled Fields", result.filled_fields)
                        with col3:
                            fill_rate = (result.filled_fields / result.total_fields * 100) if result.total_fields > 0 else 0
                            st.metric("Fill Rate", f"{fill_rate:.0f}%")
                        
                        if result.total_fields > 0:
                            st.success("✅ Data extracted! Check the 'Edit Fields' tab to review and modify.")
                        else:
                            st.warning("⚠️ No fields extracted. Check PDF quality or try a different file.")
                    else:
                        st.error("❌ Extraction failed or returned no data")
    
    with tab2:
        if st.session_state.current_result:
            display_extraction_results(st.session_state.current_result)
            
            # Save changes button
            if st.button("💾 Save All Changes", type="primary"):
                if st.session_state.current_result:
                    st.session_state.current_result.calculate_stats()
                    submission_id = db.save_submission(st.session_state.current_result)
                    st.success(f"✅ Changes saved! (ID: {submission_id})")
        else:
            st.info("No form data loaded. Upload and extract a PDF first.")
    
    with tab3:
        display_database_tab(db)
    
    # Debug info
    if debug_mode:
        st.markdown("---")
        st.markdown("### 🔧 Debug Information")
        
        with st.expander("Session State"):
            st.json({
                "has_current_result": st.session_state.current_result is not None,
                "db_path": db.db_path,
                "pymupdf_available": PYMUPDF_AVAILABLE,
                "openai_available": OPENAI_AVAILABLE
            })
        
        if st.session_state.current_result:
            with st.expander("Current Result"):
                result = st.session_state.current_result
                st.json({
                    "form_number": result.form_number,
                    "form_title": result.form_title,
                    "total_fields": result.total_fields,
                    "filled_fields": result.filled_fields,
                    "parts_count": len(result.parts)
                })

if __name__ == "__main__":
    main()
