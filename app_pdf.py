#!/usr/bin/env python3
"""
Complete Fixed USCIS Form Processing System
- Fixed PDF reading with improved error handling
- Multiple fallback extraction methods
- Better resource management
- Manual editing and database integration
- Questionnaire for missing fields
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
    page_title="USCIS Form Processor - Fixed",
    page_icon="🤖",
    layout="wide"
)

# Simplified CSS
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
    
    .field-error {
        background: #ffebee;
        border-left: 4px solid #f44336;
    }
    
    .debug-info {
        background: #f5f5f5;
        padding: 1rem;
        border-radius: 4px;
        font-family: monospace;
        font-size: 0.9rem;
        margin: 1rem 0;
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
    questionnaire_response: str = ""
    
    def to_dict(self):
        return {
            'field_number': self.field_number,
            'field_label': self.field_label,
            'field_value': self.field_value,
            'field_type': self.field_type,
            'confidence': self.confidence,
            'is_required': self.is_required,
            'manually_edited': self.manually_edited,
            'questionnaire_response': self.questionnaire_response
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
    parts: Dict[int, FormPart] = field(default_factory=dict)
    total_fields: int = 0
    filled_fields: int = 0
    processing_time: float = 0.0
    
    def calculate_stats(self):
        self.total_fields = sum(len(part.fields) for part in self.parts.values())
        self.filled_fields = sum(1 for part in self.parts.values() 
                                for field in part.fields if field.field_value and field.field_value.strip())

# ===== DATABASE =====
class SimpleDatabase:
    def __init__(self, db_path: str = "uscis_simple.db"):
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

# ===== IMPROVED PDF EXTRACTION =====
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
        # Open document from memory
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        st.success(f"✅ PDF opened from memory - {len(doc)} pages")
        
        full_text = ""
        pages_with_text = 0
        
        # Extract text from each page
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
        # Ensure document is properly closed
        if doc is not None:
            try:
                doc.close()
            except:
                pass  # Ignore close errors

def extract_from_temp_file(pdf_bytes) -> str:
    """Extract PDF text using temporary file approach"""
    temp_file_path = None
    doc = None
    
    try:
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            temp_file.write(pdf_bytes)
            temp_file_path = temp_file.name
        
        st.info(f"📁 Created temporary file: {temp_file_path}")
        
        # Open PDF from file
        doc = fitz.open(temp_file_path)
        st.success(f"✅ PDF opened from file - {len(doc)} pages")
        
        full_text = ""
        pages_with_text = 0
        
        # Extract text from each page
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
            st.info("💡 Try using OCR software first, or use a PDF with selectable text")
            return ""
        
        st.success(f"✅ File extraction: {pages_with_text}/{len(doc)} pages")
        return full_text
        
    except Exception as e:
        st.error(f"❌ File extraction failed: {str(e)}")
        return ""
    finally:
        # Clean up resources
        if doc is not None:
            try:
                doc.close()
            except:
                pass  # Ignore close errors
        
        # Remove temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
                st.info("🗑️ Cleaned up temporary file")
            except:
                pass  # Ignore cleanup errors

def extract_pdf_text_with_context(pdf_file) -> str:
    """Alternative extraction using context manager"""
    try:
        st.info(f"📄 Processing with context manager: {pdf_file.name}")
        
        pdf_file.seek(0)
        pdf_bytes = pdf_file.read()
        
        if len(pdf_bytes) == 0:
            st.error("❌ File is empty")
            return ""
        
        if not pdf_bytes.startswith(b'%PDF'):
            st.error("❌ Not a valid PDF file")
            return ""
        
        full_text = ""
        pages_with_text = 0
        
        with safe_pdf_context(pdf_bytes) as doc:
            st.success(f"✅ PDF opened with context - {len(doc)} pages")
            
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
            st.error("❌ No text found")
            return ""
        
        st.success(f"✅ Context extraction: {pages_with_text} pages")
        return full_text
        
    except Exception as e:
        st.error(f"❌ Context extraction failed: {str(e)}")
        return ""

def extract_pdf_text_simple(pdf_file) -> str:
    """
    Main PDF extraction function with multiple fallback methods
    Fixes the "document closed" error
    """
    try:
        st.info(f"📄 Processing file: {pdf_file.name}")
        
        # Reset file pointer to beginning
        pdf_file.seek(0)
        pdf_bytes = pdf_file.read()
        
        if len(pdf_bytes) == 0:
            st.error("❌ File is empty")
            return ""
        
        st.success(f"✅ Read {len(pdf_bytes):,} bytes")
        
        # Validate PDF header
        if not pdf_bytes.startswith(b'%PDF'):
            st.error("❌ Not a valid PDF file")
            return ""
        
        # Method 1: Try direct memory approach first
        full_text = extract_from_memory(pdf_bytes)
        if full_text:
            return full_text
        
        # Method 2: Fallback to temporary file approach
        st.info("🔄 Trying alternative extraction method...")
        full_text = extract_from_temp_file(pdf_bytes)
        if full_text:
            return full_text
        
        # Method 3: Context manager approach
        st.info("🔄 Trying context manager approach...")
        full_text = extract_pdf_text_with_context(pdf_file)
        if full_text:
            return full_text
        
        # If all methods fail
        st.error("❌ All extraction methods failed")
        st.info("💡 Possible solutions:")
        st.info("   • Try a different PDF file")
        st.info("   • Use OCR if it's an image-based PDF")
        st.info("   • Check if the PDF is corrupted")
        st.info("   • Ensure PyMuPDF is properly installed: pip install --upgrade PyMuPDF")
        
        return ""
        
    except Exception as e:
        st.error(f"💥 PDF extraction failed: {str(e)}")
        return ""

# ===== AI EXTRACTION =====
def extract_form_data_simple(pdf_text: str, openai_client, form_type: str = None) -> FormResult:
    """Simplified AI extraction with immediate results"""
    
    try:
        st.info("🤖 Starting AI extraction...")
        
        # Auto-detect form type if needed
        if not form_type or form_type == "Auto-detect":
            form_type = detect_form_type(pdf_text[:2000])
            st.info(f"🔍 Detected form type: {form_type}")
        
        # Truncate text if too long
        max_length = 15000
        if len(pdf_text) > max_length:
            pdf_text = pdf_text[:max_length] + "\n[...text truncated...]"
            st.info(f"📝 Text truncated to {max_length} characters for processing")
        
        # Create extraction prompt
        prompt = f"""
        Extract form data from this USCIS {form_type} document.
        
        Return ONLY valid JSON in this format:
        {{
          "form_type": "{form_type}",
          "parts": [
            {{
              "number": 1,
              "title": "Information About You",
              "fields": [
                {{
                  "field_number": "1.a",
                  "field_label": "Family Name (Last Name)",
                  "field_value": "extracted_value_or_empty_string",
                  "field_type": "text",
                  "confidence": 0.95,
                  "is_required": true
                }}
              ]
            }}
          ]
        }}
        
        Extract ALL visible fields, even if empty. Focus on accuracy.
        
        Document text:
        {pdf_text}
        """
        
        # Call OpenAI
        st.info("🔄 Calling OpenAI API...")
        
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=6000,
                timeout=60
            )
            
            response_text = response.choices[0].message.content.strip()
            st.success(f"✅ AI response received ({len(response_text)} characters)")
            
        except Exception as e:
            st.error(f"❌ OpenAI API call failed: {str(e)}")
            return create_empty_result(form_type)
        
        # Parse JSON response
        try:
            # Clean response
            if '```json' in response_text:
                response_text = response_text.split('```json')[1].split('```')[0]
            elif '```' in response_text:
                response_text = response_text.split('```')[1].split('```')[0]
            
            data = json.loads(response_text.strip())
            st.success("✅ JSON parsed successfully")
            
        except json.JSONDecodeError as e:
            st.error(f"❌ JSON parsing failed: {str(e)}")
            st.error("Raw response preview:")
            st.code(response_text[:500] + "..." if len(response_text) > 500 else response_text)
            return create_empty_result(form_type)
        
        # Convert to FormResult
        result = FormResult(
            form_number=data.get('form_type', form_type),
            form_title=get_form_title(form_type)
        )
        
        # Process parts
        for part_data in data.get('parts', []):
            part = FormPart(
                number=part_data.get('number', 1),
                title=part_data.get('title', 'Unknown Part')
            )
            
            # Process fields
            for field_data in part_data.get('fields', []):
                field = ExtractedField(
                    field_number=field_data.get('field_number', ''),
                    field_label=field_data.get('field_label', ''),
                    field_value=field_data.get('field_value', ''),
                    field_type=field_data.get('field_type', 'text'),
                    confidence=field_data.get('confidence', 0.5),
                    is_required=field_data.get('is_required', False)
                )
                part.add_field(field)
            
            result.parts[part.number] = part
            st.info(f"📋 Part {part.number}: {len(part.fields)} fields extracted")
        
        # Calculate stats
        result.calculate_stats()
        st.success(f"🎉 Extraction complete! {result.total_fields} total fields, {result.filled_fields} filled")
        
        return result
        
    except Exception as e:
        st.error(f"💥 Extraction failed: {str(e)}")
        return create_empty_result(form_type or "Unknown")

def detect_form_type(text_sample: str) -> str:
    """Simple form type detection"""
    patterns = [
        (r'Form\s+(I-90)', 'I-90'),
        (r'Form\s+(I-130)', 'I-130'),
        (r'Form\s+(I-485)', 'I-485'),
        (r'Form\s+(N-400)', 'N-400'),
        (r'Form\s+(G-28)', 'G-28'),
    ]
    
    for pattern, form_type in patterns:
        if re.search(pattern, text_sample, re.IGNORECASE):
            return form_type
    
    return "Unknown"

def get_form_title(form_type: str) -> str:
    """Get form title"""
    titles = {
        'I-90': 'Application to Replace Permanent Resident Card',
        'I-130': 'Petition for Alien Relative',
        'I-485': 'Application to Register Permanent Residence',
        'N-400': 'Application for Naturalization',
        'G-28': 'Notice of Entry of Appearance as Attorney',
    }
    return titles.get(form_type, f"USCIS Form {form_type}")

def create_empty_result(form_type: str) -> FormResult:
    """Create empty result when extraction fails"""
    result = FormResult(
        form_number=form_type,
        form_title=get_form_title(form_type)
    )
    
    # Add a basic empty part
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
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Form Type", result.form_number)
    with col2:
        st.metric("Total Fields", result.total_fields)
    with col3:
        st.metric("Filled Fields", result.filled_fields)
    with col4:
        fill_rate = (result.filled_fields / result.total_fields * 100) if result.total_fields > 0 else 0
        st.metric("Completion", f"{fill_rate:.0f}%")
    
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
    
    # Determine field status
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
            st.markdown("✏️ Manually Edited")
    
    with col2:
        st.markdown(f"**{field.field_label}**")
        st.caption(f"Type: {field.field_type} | Confidence: {field.confidence:.0%}")
    
    with col3:
        if field.confidence < 0.5:
            st.markdown("⚠️ Low Confidence")
    
    # Value editor
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # Different input types
        if field.field_type == "checkbox" or "yes" in field.field_label.lower() or "no" in field.field_label.lower():
            new_value = st.selectbox(
                f"Value:",
                ["", "Yes", "No", "N/A"],
                index=["", "Yes", "No", "N/A"].index(field.field_value) if field.field_value in ["", "Yes", "No", "N/A"] else 0,
                key=f"field_{field_key}"
            )
        elif field.field_type == "date" or "date" in field.field_label.lower():
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
            st.success("✅ Field updated!")
    
    with col2:
        # Quick actions
        if st.button(f"❌ Clear", key=f"clear_{field_key}"):
            field.field_value = ""
            field.manually_edited = True
            st.rerun()
        
        if field.field_type in ["country", "state"]:
            if st.button(f"🌍", key=f"help_{field_key}"):
                show_field_suggestions(field)
    
    st.markdown('</div>', unsafe_allow_html=True)

def show_field_suggestions(field: ExtractedField):
    """Show suggestions for specific field types"""
    if field.field_type == "country":
        st.info("Common countries: United States, Canada, Mexico, United Kingdom, Germany")
    elif field.field_type == "state":
        st.info("US States: California, New York, Texas, Florida, Illinois")

def display_questionnaire(result: FormResult):
    """Display questionnaire for missing fields"""
    
    st.markdown("## 📝 Complete Missing Information")
    
    # Find fields that need completion
    missing_fields = []
    for part in result.parts.values():
        for field in part.fields:
            if field.is_required and (not field.field_value or not field.field_value.strip()):
                missing_fields.append(field)
    
    if not missing_fields:
        st.success("🎉 All required fields are completed!")
        return
    
    st.info(f"Please complete {len(missing_fields)} required fields:")
    
    # Group by part
    fields_by_part = {}
    for field in missing_fields:
        part_num = 1  # Default since we don't track part in field
        for part_num, part in result.parts.items():
            if field in part.fields:
                break
        
        if part_num not in fields_by_part:
            fields_by_part[part_num] = []
        fields_by_part[part_num].append(field)
    
    # Display questionnaire
    for part_num, fields in fields_by_part.items():
        part_title = result.parts[part_num].title
        
        st.markdown(f"### Part {part_num}: {part_title}")
        
        for i, field in enumerate(fields):
            st.markdown(f"**{field.field_number}: {field.field_label}**")
            
            # Generate question
            question = generate_question(field)
            st.write(question)
            
            # Answer input
            answer = st.text_input(
                "Your answer:",
                key=f"quest_{part_num}_{i}",
                placeholder=get_placeholder(field)
            )
            
            if answer:
                field.questionnaire_response = answer
                field.field_value = answer
                field.manually_edited = True
            
            st.markdown("---")

def generate_question(field: ExtractedField) -> str:
    """Generate question text for field"""
    label = field.field_label.lower()
    
    if 'name' in label:
        return f"What is your {field.field_label.lower()}?"
    elif 'address' in label:
        return f"What is your {field.field_label.lower()}? (Include street, city, state, ZIP)"
    elif 'date' in label or 'birth' in label:
        return f"What is the {field.field_label.lower()}? (MM/DD/YYYY format)"
    elif 'phone' in label:
        return f"What is your {field.field_label.lower()}? (Include area code)"
    elif 'email' in label:
        return f"What is your {field.field_label.lower()}?"
    else:
        return f"Please provide: {field.field_label}"

def get_placeholder(field: ExtractedField) -> str:
    """Get placeholder text"""
    if 'name' in field.field_label.lower():
        return "Enter full name"
    elif 'address' in field.field_label.lower():
        return "123 Main St, City, State 12345"
    elif 'phone' in field.field_label.lower():
        return "(555) 123-4567"
    elif 'email' in field.field_label.lower():
        return "your.email@example.com"
    else:
        return "Enter value"

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
            # Extract ID from selection
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
            form_title=data.get('form_title', 'Unknown Form')
        )
        
        # Rebuild parts
        for part_num_str, part_data in data.get('parts', {}).items():
            part_num = int(part_num_str.replace('part_', ''))
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
                    questionnaire_response=field_data.get('questionnaire_response', '')
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
        '<h1>🤖 USCIS Form Processor - Complete Fixed Version</h1>'
        '<p>AI-powered form extraction with robust PDF handling and manual editing</p>'
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
    tab1, tab2, tab3, tab4 = st.tabs(["📤 Upload & Extract", "✏️ Edit Fields", "📝 Questionnaire", "💾 Database"])
    
    with tab1:
        st.markdown("### 📤 Upload PDF and Extract Data")
        
        uploaded_file = st.file_uploader(
            "Choose a USCIS form PDF",
            type=['pdf'],
            help="Upload any USCIS form"
        )
        
        if uploaded_file:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.success(f"✅ File: {uploaded_file.name}")
                form_type = st.selectbox(
                    "Form Type",
                    ["Auto-detect", "I-90", "I-130", "I-485", "N-400", "G-28"]
                )
            
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
                    
                    # Step 2: AI Extraction
                    st.markdown("#### Step 2: AI Data Extraction")
                    start_time = time.time()
                    
                    result = extract_form_data_simple(pdf_text, openai_client, form_type)
                    
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
        if st.session_state.current_result:
            display_questionnaire(st.session_state.current_result)
            
            if st.button("✅ Complete Form"):
                st.session_state.current_result.calculate_stats()
                submission_id = db.save_submission(st.session_state.current_result)
                st.success("🎉 Form completed and saved!")
                st.balloons()
        else:
            st.info("No form data loaded. Upload and extract a PDF first.")
    
    with tab4:
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
                    "total_fields": result.total_fields,
                    "filled_fields": result.filled_fields,
                    "parts_count": len(result.parts)
                })

if __name__ == "__main__":
    main()
