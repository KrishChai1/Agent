#!/usr/bin/env python3
"""
Complete AI-Powered USCIS Form Processing System
- Enhanced PDF Reading with multiple fallback methods
- AI Agent validation loops with timeout protection
- Manual editing and database integration
- Questionnaire flow for missing data
- Production-ready error handling
"""

import os
import json
import re
import time
import hashlib
import traceback
import io
import csv
import sqlite3
import tempfile
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field, asdict
from collections import defaultdict, OrderedDict
from enum import Enum
from pathlib import Path
import difflib

import streamlit as st
import pandas as pd

# Core imports with fallbacks
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    fitz = None

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    openai = None

try:
    import xlsxwriter
    XLSXWRITER_AVAILABLE = True
except ImportError:
    XLSXWRITER_AVAILABLE = False

# Page config
st.set_page_config(
    page_title="Complete AI USCIS Form Processor",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Enhanced CSS with manual editing styles
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
        background: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        border-left: 4px solid #007bff;
    }
    
    .extractor-agent { border-left-color: #28a745; background: #f8fff9; }
    .validation-agent { border-left-color: #ffc107; background: #fffdf5; }
    .coordinator-agent { border-left-color: #6f42c1; background: #faf9ff; }
    
    .field-editor {
        background: #fff;
        border: 2px solid #e9ecef;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        transition: border-color 0.3s;
    }
    
    .field-editor:hover {
        border-color: #007bff;
        box-shadow: 0 2px 4px rgba(0,123,255,0.1);
    }
    
    .field-value-filled {
        background: #e8f5e9;
        padding: 0.5rem;
        border-radius: 4px;
        font-weight: bold;
        color: #2e7d32;
    }
    
    .field-value-empty {
        background: #fff3cd;
        padding: 0.5rem;
        border-radius: 4px;
        color: #856404;
        font-style: italic;
    }
    
    .validation-error {
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
    
    .questionnaire-card {
        background: #f0f8ff;
        border: 2px solid #4fc3f7;
        border-radius: 8px;
        padding: 1.5rem;
        margin: 1rem 0;
    }
    
    .progress-indicator {
        background: #e3f2fd;
        border: 1px solid #1976d2;
        border-radius: 6px;
        padding: 0.5rem;
        text-align: center;
        margin: 0.5rem 0;
    }
    
    .manual-edit-button {
        background: #ff9800;
        color: white;
        border: none;
        padding: 0.5rem 1rem;
        border-radius: 4px;
        cursor: pointer;
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
    COUNTRY = "country"
    STATE = "state"
    UNKNOWN = "unknown"

class AgentStatus(Enum):
    IDLE = "idle"
    PROCESSING = "processing"
    SUCCESS = "success"
    ERROR = "error"
    VALIDATION_FAILED = "validation_failed"
    MANUAL_REVIEW = "manual_review"

class FormType(Enum):
    I90 = "I-90"
    I130 = "I-130"
    I485 = "I-485"
    I765 = "I-765"
    G28 = "G-28"
    N400 = "N-400"
    I129 = "I-129"
    UNKNOWN = "Unknown"

class ProcessingStage(Enum):
    UPLOAD = "upload"
    EXTRACTION = "extraction"
    VALIDATION = "validation"
    MANUAL_EDIT = "manual_edit"
    QUESTIONNAIRE = "questionnaire"
    COMPLETE = "complete"

# ===== ENHANCED DATA CLASSES =====
@dataclass
class ExtractedField:
    """Enhanced field with manual editing support"""
    field_number: str
    field_label: str
    field_value: str
    field_type: FieldType = FieldType.TEXT
    confidence: float = 0.0
    page_number: int = 1
    part_number: int = 1
    part_name: str = ""
    validation_errors: List[str] = field(default_factory=list)
    is_required: bool = False
    extraction_method: str = "ai_agent"
    manually_edited: bool = False
    edit_timestamp: Optional[datetime] = None
    original_value: str = ""
    suggested_values: List[str] = field(default_factory=list)
    questionnaire_response: str = ""
    
    def edit_value(self, new_value: str, method: str = "manual"):
        """Edit field value with tracking"""
        if not self.manually_edited:
            self.original_value = self.field_value
        self.field_value = new_value
        self.manually_edited = True
        self.edit_timestamp = datetime.now()
        self.extraction_method = method
        self.validation_errors = []  # Clear errors on edit
    
    def to_dict(self) -> Dict:
        return {
            'field_number': self.field_number,
            'field_label': self.field_label,
            'field_value': self.field_value,
            'field_type': self.field_type.value,
            'confidence': self.confidence,
            'page_number': self.page_number,
            'part_number': self.part_number,
            'part_name': self.part_name,
            'validation_errors': self.validation_errors,
            'is_required': self.is_required,
            'extraction_method': self.extraction_method,
            'manually_edited': self.manually_edited,
            'edit_timestamp': self.edit_timestamp.isoformat() if self.edit_timestamp else None,
            'original_value': self.original_value,
            'questionnaire_response': self.questionnaire_response
        }

@dataclass
class FormPart:
    """Enhanced form part with completion tracking"""
    number: int
    title: str
    start_page: int = 1
    end_page: int = 1
    fields: List[ExtractedField] = field(default_factory=list)
    raw_text: str = ""
    validation_score: float = 0.0
    completion_percentage: float = 0.0
    manual_review_required: bool = False
    
    def add_field(self, field: ExtractedField):
        field.part_number = self.number
        field.part_name = self.title
        self.fields.append(field)
        self.calculate_completion()
    
    def calculate_completion(self):
        """Calculate completion percentage"""
        if not self.fields:
            self.completion_percentage = 0.0
            return
        
        filled_fields = sum(1 for f in self.fields if f.field_value and f.field_value.strip())
        self.completion_percentage = (filled_fields / len(self.fields)) * 100
        
        # Check if manual review needed
        self.manual_review_required = any(
            f.is_required and (not f.field_value or len(f.validation_errors) > 0)
            for f in self.fields
        )

@dataclass
class ExtractionResult:
    """Complete extraction result with enhanced tracking"""
    form_number: str
    form_title: str
    parts: Dict[int, FormPart] = field(default_factory=dict)
    total_fields: int = 0
    filled_fields: int = 0
    validation_score: float = 0.0
    extraction_iterations: int = 0
    agent_logs: List[str] = field(default_factory=list)
    processing_time: float = 0.0
    final_validation_report: Dict[str, Any] = field(default_factory=dict)
    current_stage: ProcessingStage = ProcessingStage.EXTRACTION
    manual_edits_count: int = 0
    questionnaire_completed: bool = False
    
    def calculate_stats(self):
        """Calculate comprehensive statistics"""
        self.total_fields = sum(len(part.fields) for part in self.parts.values())
        self.filled_fields = sum(1 for part in self.parts.values() 
                                for field in part.fields if field.field_value and field.field_value.strip())
        self.manual_edits_count = sum(1 for part in self.parts.values()
                                     for field in part.fields if field.manually_edited)
        
        # Calculate overall validation score
        if self.parts:
            for part in self.parts.values():
                part.calculate_completion()
            scores = [part.validation_score for part in self.parts.values()]
            self.validation_score = sum(scores) / len(scores)

# ===== ENHANCED DATABASE MANAGER =====
class DatabaseManager:
    """Complete database manager with manual editing support"""
    def __init__(self, db_path: str = "uscis_forms_complete.db"):
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        return sqlite3.connect(self.db_path)
    
    def init_database(self):
        """Initialize enhanced database schema"""
        with self.get_connection() as conn:
            # Form submissions table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS form_submissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    form_type TEXT NOT NULL,
                    submission_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    entry_mode TEXT DEFAULT 'ai_agents',
                    total_fields INTEGER DEFAULT 0,
                    completed_fields INTEGER DEFAULT 0,
                    validation_score REAL DEFAULT 0.0,
                    pdf_filename TEXT,
                    json_data TEXT,
                    status TEXT DEFAULT 'draft',
                    notes TEXT,
                    iterations INTEGER DEFAULT 0,
                    current_stage TEXT DEFAULT 'extraction',
                    manual_edits_count INTEGER DEFAULT 0,
                    questionnaire_completed BOOLEAN DEFAULT 0,
                    completion_percentage REAL DEFAULT 0.0
                )
            ''')
            
            # Enhanced form fields table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS form_fields (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    submission_id INTEGER NOT NULL,
                    field_number TEXT NOT NULL,
                    field_label TEXT,
                    field_value TEXT,
                    original_value TEXT,
                    field_type TEXT DEFAULT 'text',
                    confidence REAL DEFAULT 0.0,
                    is_required BOOLEAN DEFAULT 0,
                    validation_errors TEXT,
                    part_number INTEGER DEFAULT 1,
                    part_name TEXT,
                    extraction_method TEXT DEFAULT 'ai_agent',
                    manually_edited BOOLEAN DEFAULT 0,
                    edit_timestamp TIMESTAMP,
                    questionnaire_response TEXT,
                    suggested_values TEXT,
                    FOREIGN KEY (submission_id) REFERENCES form_submissions (id)
                )
            ''')
            
            # Manual edits log
            conn.execute('''
                CREATE TABLE IF NOT EXISTS manual_edits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    submission_id INTEGER NOT NULL,
                    field_id INTEGER NOT NULL,
                    old_value TEXT,
                    new_value TEXT,
                    edit_type TEXT DEFAULT 'manual',
                    edit_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    edit_reason TEXT,
                    FOREIGN KEY (submission_id) REFERENCES form_submissions (id),
                    FOREIGN KEY (field_id) REFERENCES form_fields (id)
                )
            ''')
            
            # Questionnaire responses
            conn.execute('''
                CREATE TABLE IF NOT EXISTS questionnaire_responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    submission_id INTEGER NOT NULL,
                    question_id TEXT NOT NULL,
                    question_text TEXT,
                    response_value TEXT,
                    response_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    confidence_score REAL DEFAULT 1.0,
                    FOREIGN KEY (submission_id) REFERENCES form_submissions (id)
                )
            ''')
            
            # Agent processing logs
            conn.execute('''
                CREATE TABLE IF NOT EXISTS agent_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    submission_id INTEGER,
                    agent_type TEXT NOT NULL,
                    iteration INTEGER DEFAULT 1,
                    log_message TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processing_stage TEXT,
                    FOREIGN KEY (submission_id) REFERENCES form_submissions (id)
                )
            ''')
            
            conn.commit()
    
    def save_form_submission(self, submission_data: Dict) -> int:
        """Save enhanced form submission"""
        with self.get_connection() as conn:
            if submission_data.get('id'):
                # Update existing
                conn.execute('''
                    UPDATE form_submissions SET
                    form_type=?, entry_mode=?, total_fields=?, completed_fields=?,
                    validation_score=?, json_data=?, status=?, notes=?, iterations=?,
                    current_stage=?, manual_edits_count=?, questionnaire_completed=?, completion_percentage=?
                    WHERE id=?
                ''', (
                    submission_data['form_type'], submission_data['entry_mode'], 
                    submission_data['total_fields'], submission_data['completed_fields'],
                    submission_data['validation_score'], submission_data['json_data'],
                    submission_data['status'], submission_data['notes'], submission_data['iterations'],
                    submission_data['current_stage'], submission_data['manual_edits_count'],
                    submission_data['questionnaire_completed'], submission_data['completion_percentage'],
                    submission_data['id']
                ))
                return submission_data['id']
            else:
                # Insert new
                cursor = conn.execute('''
                    INSERT INTO form_submissions 
                    (form_type, entry_mode, total_fields, completed_fields, validation_score,
                     pdf_filename, json_data, status, notes, iterations, current_stage,
                     manual_edits_count, questionnaire_completed, completion_percentage)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    submission_data['form_type'], submission_data['entry_mode'],
                    submission_data['total_fields'], submission_data['completed_fields'],
                    submission_data['validation_score'], submission_data.get('pdf_filename', ''),
                    submission_data['json_data'], submission_data['status'],
                    submission_data['notes'], submission_data['iterations'],
                    submission_data['current_stage'], submission_data['manual_edits_count'],
                    submission_data['questionnaire_completed'], submission_data['completion_percentage']
                ))
                return cursor.lastrowid
    
    def save_extracted_fields(self, submission_id: int, extraction_result: ExtractionResult):
        """Save extracted fields with edit tracking"""
        try:
            with self.get_connection() as conn:
                # Clear existing fields for this submission
                conn.execute('DELETE FROM form_fields WHERE submission_id = ?', (submission_id,))
                
                # Insert new fields
                for part in extraction_result.parts.values():
                    for field in part.fields:
                        validation_errors_json = json.dumps(field.validation_errors) if field.validation_errors else ""
                        suggested_values_json = json.dumps(field.suggested_values) if field.suggested_values else ""
                        
                        conn.execute('''
                            INSERT INTO form_fields 
                            (submission_id, field_number, field_label, field_value, original_value,
                             field_type, confidence, is_required, validation_errors, part_number, 
                             part_name, extraction_method, manually_edited, edit_timestamp,
                             questionnaire_response, suggested_values)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            submission_id, field.field_number, field.field_label, field.field_value,
                            field.original_value, field.field_type.value, field.confidence,
                            field.is_required, validation_errors_json, field.part_number,
                            field.part_name, field.extraction_method, field.manually_edited,
                            field.edit_timestamp, field.questionnaire_response, suggested_values_json
                        ))
                
                conn.commit()
        except Exception as e:
            st.error(f"Error saving fields: {e}")
    
    def log_manual_edit(self, submission_id: int, field_id: int, old_value: str, new_value: str, reason: str = ""):
        """Log manual edits for audit trail"""
        try:
            with self.get_connection() as conn:
                conn.execute('''
                    INSERT INTO manual_edits (submission_id, field_id, old_value, new_value, edit_reason)
                    VALUES (?, ?, ?, ?, ?)
                ''', (submission_id, field_id, old_value, new_value, reason))
                conn.commit()
        except Exception as e:
            st.error(f"Error logging edit: {e}")
    
    def save_questionnaire_response(self, submission_id: int, question_id: str, question_text: str, response: str):
        """Save questionnaire responses"""
        try:
            with self.get_connection() as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO questionnaire_responses 
                    (submission_id, question_id, question_text, response_value)
                    VALUES (?, ?, ?, ?)
                ''', (submission_id, question_id, question_text, response))
                conn.commit()
        except Exception as e:
            st.error(f"Error saving questionnaire response: {e}")
    
    def get_form_submissions(self, limit: int = 50) -> List[Dict]:
        """Get form submissions with enhanced data"""
        with self.get_connection() as conn:
            cursor = conn.execute('''
                SELECT id, form_type, submission_date, entry_mode, total_fields, 
                       completed_fields, validation_score, pdf_filename, json_data, 
                       status, notes, iterations, current_stage, manual_edits_count,
                       questionnaire_completed, completion_percentage
                FROM form_submissions 
                ORDER BY submission_date DESC LIMIT ?
            ''', (limit,))
            
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

# ===== ENHANCED PDF EXTRACTION =====
def extract_pdf_text_enhanced(pdf_file) -> str:
    """Production-ready PDF extraction with multiple fallback methods"""
    try:
        # File validation
        if pdf_file is None:
            st.error("❌ No file provided")
            return ""
        
        # Show file info
        if hasattr(pdf_file, 'name'):
            st.info(f"📄 Processing: {pdf_file.name}")
            file_size_mb = pdf_file.size / (1024 * 1024) if hasattr(pdf_file, 'size') else 0
            if file_size_mb > 50:
                st.warning(f"⚠️ Large file ({file_size_mb:.1f} MB) - processing may take longer")
        
        # Read file bytes
        try:
            if hasattr(pdf_file, 'read'):
                pdf_file.seek(0)
                pdf_bytes = pdf_file.read()
            else:
                pdf_bytes = pdf_file
            
            if len(pdf_bytes) == 0:
                st.error("❌ File is empty")
                return ""
            
            st.success(f"✅ Read {len(pdf_bytes):,} bytes")
            
        except Exception as e:
            st.error(f"❌ Failed to read file: {str(e)}")
            return ""
        
        # Validate PDF header
        if not pdf_bytes.startswith(b'%PDF'):
            st.error("❌ Invalid PDF file format")
            return ""
        
        # Multiple extraction methods
        extraction_methods = [
            ("Direct stream", lambda: fitz.open(stream=pdf_bytes, filetype="pdf")),
            ("Temporary file", lambda: _extract_via_temp_file(pdf_bytes))
        ]
        
        doc = None
        for method_name, method_func in extraction_methods:
            try:
                doc = method_func()
                st.success(f"✅ PDF opened using {method_name} method")
                break
            except Exception as e:
                st.warning(f"⚠️ {method_name} method failed: {str(e)}")
                continue
        
        if doc is None:
            st.error("❌ All PDF opening methods failed")
            return ""
        
        # Check for password protection
        if doc.needs_pass:
            st.error("🔒 PDF is password protected")
            doc.close()
            return ""
        
        # Extract text with multiple methods
        full_text = ""
        pages_with_text = 0
        extraction_stats = {"pages": len(doc), "text_found": 0, "errors": 0}
        
        for page_num in range(len(doc)):
            try:
                page = doc[page_num]
                page_text = ""
                
                # Method 1: Standard extraction
                page_text = page.get_text()
                
                # Method 2: Layout preservation if needed
                if not page_text.strip():
                    page_text = page.get_text("text")
                
                # Method 3: Block-based extraction
                if not page_text.strip():
                    blocks = page.get_text("blocks")
                    page_text = " ".join([block[4] for block in blocks if len(block) > 4])
                
                # Add page text if found
                if page_text.strip():
                    full_text += f"\n--- PAGE {page_num + 1} ---\n{page_text}\n"
                    pages_with_text += 1
                    extraction_stats["text_found"] += 1
                    
            except Exception as e:
                st.warning(f"⚠️ Error on page {page_num + 1}: {str(e)}")
                extraction_stats["errors"] += 1
                continue
        
        doc.close()
        
        # Analyze results
        if not full_text.strip():
            st.error("❌ No text extracted from PDF")
            st.info("📝 This could be an image-based PDF requiring OCR")
            
            # Show diagnostic info
            with st.expander("🔍 PDF Analysis"):
                st.write(f"📄 Total pages: {extraction_stats['pages']}")
                st.write(f"📝 Pages with text: {extraction_stats['text_found']}")
                st.write(f"❌ Pages with errors: {extraction_stats['errors']}")
                
                st.markdown("**💡 Solutions:**")
                st.markdown("• Use OCR software (Adobe Acrobat, online tools)")
                st.markdown("• Re-scan document with text recognition")
                st.markdown("• Try a different PDF file")
            
            return ""
        
        # Success metrics
        success_rate = (pages_with_text / len(doc)) * 100 if len(doc) > 0 else 0
        st.success(f"✅ Extracted {len(full_text):,} characters from {pages_with_text}/{len(doc)} pages ({success_rate:.0f}% success)")
        
        # Show preview
        with st.expander("🔍 Text Preview", expanded=False):
            st.text_area("First 500 characters:", full_text[:500], height=100)
        
        return full_text
        
    except Exception as e:
        st.error(f"💥 PDF extraction failed: {str(e)}")
        
        # Detailed error analysis
        with st.expander("🔧 Error Details"):
            st.code(f"Error type: {type(e).__name__}")
            st.code(f"Error message: {str(e)}")
        
        return ""

def _extract_via_temp_file(pdf_bytes: bytes):
    """Fallback extraction via temporary file"""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
        tmp_file.write(pdf_bytes)
        tmp_file.flush()
        
        try:
            doc = fitz.open(tmp_file.name)
            return doc
        finally:
            os.unlink(tmp_file.name)

# ===== ENHANCED AI AGENTS =====
class BaseAgent:
    """Enhanced base agent with better error handling"""
    def __init__(self, name: str, openai_client, debug_mode: bool = False, timeout: int = 45):
        self.name = name
        self.client = openai_client
        self.debug_mode = debug_mode
        self.status = AgentStatus.IDLE
        self.logs = []
        self.timeout = timeout
    
    def log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {self.name}: {message}"
        self.logs.append(log_entry)
        if self.debug_mode:
            st.write(f"🤖 {log_entry}")
    
    def call_openai_with_timeout(self, messages: List[Dict], max_tokens: int = 4000) -> str:
        """Enhanced OpenAI call with retry logic"""
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                self.log(f"API call attempt {attempt + 1}/{max_retries}")
                
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.1,  # Slightly higher for better variety
                    max_tokens=max_tokens,
                    timeout=self.timeout
                )
                
                content = response.choices[0].message.content.strip()
                self.log(f"API response received ({len(content)} chars)")
                return content
                
            except Exception as e:
                self.log(f"API call attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    raise

class ExtractorAgent(BaseAgent):
    """Enhanced extractor with form-specific templates"""
    def __init__(self, openai_client, debug_mode: bool = False, timeout: int = 60):
        super().__init__("Extractor Agent", openai_client, debug_mode, timeout)
        self.model = "gpt-4o"  # Using best model for extraction
    
    def extract_form_data(self, pdf_text: str, form_type: str = None, progress_callback=None) -> ExtractionResult:
        """Enhanced extraction with form-specific processing"""
        self.status = AgentStatus.PROCESSING
        self.log(f"Starting enhanced extraction for form: {form_type or 'Auto-detect'}")
        
        if progress_callback:
            progress_callback(10, "Analyzing document structure...")
        
        try:
            # Auto-detect form type if not provided
            if not form_type:
                form_type = self._identify_form_type(pdf_text[:3000])
                self.log(f"Auto-detected form type: {form_type}")
            
            if progress_callback:
                progress_callback(25, f"Processing {form_type} with specialized extraction...")
            
            # Use form-specific extraction strategy
            result = self._extract_with_form_template(pdf_text, form_type, progress_callback)
            
            if progress_callback:
                progress_callback(90, "Finalizing extraction results...")
            
            result.calculate_stats()
            self.status = AgentStatus.SUCCESS
            self.log(f"Extraction complete: {result.total_fields} fields extracted")
            
            return result
            
        except Exception as e:
            self.status = AgentStatus.ERROR
            self.log(f"Extraction failed: {str(e)}")
            raise
    
    def _identify_form_type(self, text_sample: str) -> str:
        """Enhanced form identification"""
        # Pattern matching first (faster)
        patterns = [
            (r'Form\s+(I-90)', 'I-90'),
            (r'Form\s+(I-130)', 'I-130'),
            (r'Form\s+(I-485)', 'I-485'),
            (r'Form\s+(N-400)', 'N-400'),
            (r'Form\s+(G-28)', 'G-28'),
            (r'Form\s+(I-129)', 'I-129'),
            (r'Form\s+(I-765)', 'I-765'),
        ]
        
        for pattern, form_type in patterns:
            if re.search(pattern, text_sample, re.IGNORECASE):
                return form_type
        
        # AI fallback for complex cases
        try:
            prompt = f"""
            Identify the USCIS form type from this text. Look for form numbers, titles, and content.
            Return ONLY the form number (e.g., "I-90", "N-400").
            
            Text sample: {text_sample[:1500]}
            
            Form type:"""
            
            messages = [{"role": "user", "content": prompt}]
            response = self.call_openai_with_timeout(messages, max_tokens=20)
            
            # Clean response
            form_type = re.sub(r'[^A-Z0-9-]', '', response.upper())
            return form_type if form_type else "Unknown"
            
        except Exception:
            return "Unknown"
    
    def _extract_with_form_template(self, pdf_text: str, form_type: str, progress_callback=None) -> ExtractionResult:
        """Extract using form-specific templates and strategies"""
        
        # Truncate very long text
        max_length = 20000
        if len(pdf_text) > max_length:
            pdf_text = pdf_text[:max_length] + "\n[...text truncated for processing...]"
            self.log(f"Text truncated to {max_length} characters")
        
        # Form-specific extraction prompts
        form_templates = {
            'I-90': self._get_i90_template(),
            'I-130': self._get_i130_template(),
            'I-485': self._get_i485_template(),
            'N-400': self._get_n400_template(),
            'G-28': self._get_g28_template(),
        }
        
        template = form_templates.get(form_type, self._get_generic_template())
        
        prompt = f"""
        {template}
        
        Extract ALL visible form fields from this {form_type} document. Be thorough and accurate.
        
        Form text:
        {pdf_text}
        
        Return ONLY valid JSON in the specified format.
        """
        
        try:
            if progress_callback:
                progress_callback(50, "AI analyzing form content...")
            
            messages = [{"role": "user", "content": prompt}]
            response_text = self.call_openai_with_timeout(messages, max_tokens=8000)
            
            if progress_callback:
                progress_callback(75, "Processing AI response...")
            
            # Clean and parse JSON
            json_text = self._clean_json_response(response_text)
            data = json.loads(json_text)
            
            # Convert to ExtractionResult
            result = self._convert_to_extraction_result(data, form_type)
            return result
            
        except json.JSONDecodeError as e:
            self.log(f"JSON parsing failed: {str(e)}")
            return self._create_minimal_result(form_type)
        except Exception as e:
            self.log(f"Extraction failed: {str(e)}")
            raise
    
    def _get_i90_template(self) -> str:
        return """
        You are extracting data from USCIS Form I-90 (Application to Replace Permanent Resident Card).
        
        Focus on these key sections:
        - Part 1: Information About You (Personal details)
        - Part 2: Application Type (Reason for replacement)
        - Part 3: Processing Information
        - Part 4: Accommodations
        - Part 5: Applicant's Statement
        - Part 6: Additional Information
        - Part 7: Interpreter Information
        - Part 8: Contact Information
        
        Return JSON format:
        {
          "form_type": "I-90",
          "parts": [
            {
              "number": 1,
              "title": "Information About You",
              "fields": [
                {
                  "field_number": "1.a",
                  "field_label": "Family Name (Last Name)",
                  "field_value": "extracted_value_or_empty",
                  "field_type": "name",
                  "is_required": true,
                  "confidence": 0.95
                }
              ]
            }
          ]
        }
        """
    
    def _get_i130_template(self) -> str:
        return """
        You are extracting data from USCIS Form I-130 (Petition for Alien Relative).
        
        Focus on these sections:
        - Part 1: Relationship (petitioner info)
        - Part 2: Information About You (Petitioner)
        - Part 3: Information About Person You Are Filing For
        - Part 4: Information About Relatives
        - Part 5: Other Information
        - Part 6: Sponsor Information
        - Part 7: Additional Information
        
        Return the same JSON format as specified.
        """
    
    def _get_generic_template(self) -> str:
        return """
        Extract all form fields from this USCIS document systematically.
        
        Look for:
        - Numbered fields (1.a, 2.b, etc.)
        - Personal information fields
        - Address fields
        - Date fields
        - Checkbox/Yes/No fields
        - Signature blocks
        
        Return JSON format with parts and fields as shown in examples.
        """
    
    def _clean_json_response(self, response_text: str) -> str:
        """Clean AI response to extract valid JSON"""
        # Remove markdown formatting
        if '```json' in response_text:
            response_text = response_text.split('```json')[1].split('```')[0]
        elif '```' in response_text:
            response_text = response_text.split('```')[1].split('```')[0]
        
        # Remove leading/trailing whitespace
        response_text = response_text.strip()
        
        return response_text
    
    def _convert_to_extraction_result(self, data: Dict, form_type: str) -> ExtractionResult:
        """Convert JSON data to ExtractionResult object"""
        result = ExtractionResult(
            form_number=data.get('form_type', form_type),
            form_title=self._get_form_title(form_type),
            agent_logs=self.logs.copy()
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
                    field_type=FieldType(field_data.get('field_type', 'text')),
                    confidence=field_data.get('confidence', 0.5),
                    is_required=field_data.get('is_required', False),
                    extraction_method="ai_agent_enhanced"
                )
                part.add_field(field)
            
            result.parts[part.number] = part
            self.log(f"Part {part.number}: {len(part.fields)} fields extracted")
        
        return result
    
    def _create_minimal_result(self, form_type: str) -> ExtractionResult:
        """Create minimal result when extraction fails"""
        result = ExtractionResult(
            form_number=form_type,
            form_title=self._get_form_title(form_type),
            agent_logs=self.logs.copy()
        )
        
        # Add a basic part
        part = FormPart(number=1, title="Form Data")
        result.parts[1] = part
        
        return result
    
    def _get_form_title(self, form_type: str) -> str:
        """Get full form title"""
        titles = {
            'I-90': 'Application to Replace Permanent Resident Card',
            'I-130': 'Petition for Alien Relative',
            'I-485': 'Application to Register Permanent Residence',
            'I-765': 'Application for Employment Authorization',
            'G-28': 'Notice of Entry of Appearance as Attorney',
            'N-400': 'Application for Naturalization',
            'I-129': 'Petition for Nonimmigrant Worker',
        }
        return titles.get(form_type, f"USCIS Form {form_type}")

class ValidationAgent(BaseAgent):
    """Enhanced validation agent with detailed analysis"""
    def __init__(self, openai_client, debug_mode: bool = False, timeout: int = 45):
        super().__init__("Validation Agent", openai_client, debug_mode, timeout)
        self.model = "gpt-4o"
    
    def validate_extraction(self, result: ExtractionResult, original_text: str = None, progress_callback=None) -> Tuple[bool, Dict[str, Any]]:
        """Comprehensive validation with specific recommendations"""
        self.status = AgentStatus.PROCESSING
        self.log("Starting comprehensive validation...")
        
        if progress_callback:
            progress_callback(10, "Analyzing field completeness...")
        
        try:
            # Multi-level validation
            validation_report = {
                'overall_valid': True,
                'confidence_score': 0.0,
                'total_fields': result.total_fields,
                'filled_fields': result.filled_fields,
                'fill_rate': 0.0,
                'critical_missing': [],
                'validation_errors': [],
                'recommendations': [],
                'part_scores': {},
                'field_issues': []
            }
            
            if progress_callback:
                progress_callback(30, "Validating field values...")
            
            # Calculate fill rate
            fill_rate = result.filled_fields / result.total_fields if result.total_fields > 0 else 0
            validation_report['fill_rate'] = fill_rate
            
            # Validate each part
            total_score = 0
            for part_num, part in result.parts.items():
                part_score = self._validate_part(part, validation_report)
                validation_report['part_scores'][part_num] = part_score
                total_score += part_score
            
            if progress_callback:
                progress_callback(60, "Checking data consistency...")
            
            # Overall confidence calculation
            if result.parts:
                base_score = total_score / len(result.parts)
                
                # Adjust for fill rate
                if fill_rate >= 0.8:
                    base_score += 0.1
                elif fill_rate >= 0.6:
                    base_score += 0.05
                elif fill_rate < 0.3:
                    base_score -= 0.2
                
                # Adjust for critical fields
                if not validation_report['critical_missing']:
                    base_score += 0.1
                
                validation_report['confidence_score'] = min(base_score, 1.0)
            else:
                validation_report['confidence_score'] = 0.0
            
            if progress_callback:
                progress_callback(80, "Generating recommendations...")
            
            # Generate recommendations
            self._generate_recommendations(validation_report)
            
            # Determine if manual review needed
            overall_valid = (
                validation_report['confidence_score'] >= 0.7 and
                len(validation_report['critical_missing']) == 0 and
                len(validation_report['validation_errors']) < 3
            )
            
            validation_report['overall_valid'] = overall_valid
            result.final_validation_report = validation_report
            
            if progress_callback:
                progress_callback(100, "Validation complete")
            
            self.status = AgentStatus.SUCCESS if overall_valid else AgentStatus.VALIDATION_FAILED
            self.log(f"Validation complete. Score: {validation_report['confidence_score']:.2f}, Valid: {overall_valid}")
            
            return overall_valid, validation_report
            
        except Exception as e:
            self.status = AgentStatus.ERROR
            self.log(f"Validation failed: {str(e)}")
            raise
    
    def _validate_part(self, part: FormPart, validation_report: Dict) -> float:
        """Validate individual part"""
        if not part.fields:
            return 0.0
        
        filled_count = 0
        valid_count = 0
        
        for field in part.fields:
            # Check if filled
            is_filled = bool(field.field_value and field.field_value.strip())
            if is_filled:
                filled_count += 1
            
            # Validate field value
            field_valid = self._validate_field_value(field, validation_report)
            if field_valid:
                valid_count += 1
            
            # Check critical fields
            if field.is_required and not is_filled:
                validation_report['critical_missing'].append({
                    'part': part.number,
                    'field': field.field_number,
                    'label': field.field_label
                })
        
        # Calculate part score
        fill_score = filled_count / len(part.fields)
        validity_score = valid_count / len(part.fields)
        part_score = (fill_score + validity_score) / 2
        
        part.validation_score = part_score
        return part_score
    
    def _validate_field_value(self, field: ExtractedField, validation_report: Dict) -> bool:
        """Validate individual field value"""
        if not field.field_value or not field.field_value.strip():
            return True  # Empty fields are not invalid
        
        value = field.field_value.strip()
        field_type = field.field_type
        
        # Type-specific validation
        try:
            if field_type == FieldType.EMAIL:
                import re
                email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                if not re.match(email_pattern, value):
                    field.validation_errors.append("Invalid email format")
                    validation_report['field_issues'].append(f"{field.field_number}: Invalid email")
                    return False
            
            elif field_type == FieldType.PHONE:
                # Basic phone validation
                phone_clean = re.sub(r'[^\d]', '', value)
                if len(phone_clean) < 10:
                    field.validation_errors.append("Phone number too short")
                    validation_report['field_issues'].append(f"{field.field_number}: Invalid phone")
                    return False
            
            elif field_type == FieldType.DATE:
                # Basic date validation
                date_patterns = [
                    r'\d{1,2}/\d{1,2}/\d{4}',
                    r'\d{4}-\d{1,2}-\d{1,2}',
                    r'\d{1,2}-\d{1,2}-\d{4}'
                ]
                if not any(re.match(pattern, value) for pattern in date_patterns):
                    field.validation_errors.append("Invalid date format")
                    validation_report['field_issues'].append(f"{field.field_number}: Invalid date")
                    return False
            
            elif field_type == FieldType.NUMBER:
                # Basic number validation
                if not re.match(r'^\d+(\.\d+)?$', value):
                    field.validation_errors.append("Invalid number format")
                    validation_report['field_issues'].append(f"{field.field_number}: Invalid number")
                    return False
            
            return True
            
        except Exception:
            return True  # Don't fail validation on validation errors
    
    def _generate_recommendations(self, validation_report: Dict):
        """Generate specific recommendations"""
        recommendations = []
        
        # Fill rate recommendations
        if validation_report['fill_rate'] < 0.5:
            recommendations.append("Low completion rate - consider questionnaire for missing fields")
        elif validation_report['fill_rate'] < 0.8:
            recommendations.append("Some fields missing - review for completeness")
        
        # Critical field recommendations
        if validation_report['critical_missing']:
            recommendations.append(f"{len(validation_report['critical_missing'])} required fields missing - manual review needed")
        
        # Field issue recommendations
        if validation_report['field_issues']:
            recommendations.append("Some field values need correction - check highlighted issues")
        
        # Confidence-based recommendations
        if validation_report['confidence_score'] < 0.6:
            recommendations.append("Low confidence extraction - recommend manual verification")
        elif validation_report['confidence_score'] < 0.8:
            recommendations.append("Moderate confidence - spot check recommended")
        
        validation_report['recommendations'] = recommendations

class CoordinatorAgent(BaseAgent):
    """Enhanced coordinator with stage management"""
    def __init__(self, openai_client, extractor_agent: ExtractorAgent, validation_agent: ValidationAgent, 
                 max_iterations: int = 3, debug_mode: bool = False, timeout: int = 120):
        super().__init__("Coordinator Agent", openai_client, debug_mode, timeout)
        self.extractor = extractor_agent
        self.validator = validation_agent
        self.max_iterations = max_iterations
        self.model = "gpt-4o"
    
    def process_form(self, pdf_text: str, form_type: str = None, progress_callback=None) -> ExtractionResult:
        """Enhanced processing with stage management"""
        self.status = AgentStatus.PROCESSING
        self.log("Starting coordinated form processing with enhanced validation...")
        
        if progress_callback:
            progress_callback(5, "Initializing AI processing pipeline...")
        
        start_time = time.time()
        iteration = 1
        result = None
        
        try:
            while iteration <= self.max_iterations:
                self.log(f"=== ITERATION {iteration}/{self.max_iterations} ===")
                
                if progress_callback:
                    base_progress = 10 + (iteration - 1) * 30
                    progress_callback(base_progress, f"Iteration {iteration}: Extracting form data...")
                
                # EXTRACTION PHASE
                def extraction_progress(pct, msg):
                    if progress_callback:
                        total_progress = 10 + (iteration - 1) * 30 + (pct * 0.2)
                        progress_callback(int(total_progress), f"Iter {iteration}: {msg}")
                
                if iteration == 1:
                    result = self.extractor.extract_form_data(pdf_text, form_type, extraction_progress)
                else:
                    # Improve previous result
                    result = self._improve_extraction(result, pdf_text, extraction_progress)
                
                result.extraction_iterations = iteration
                result.current_stage = ProcessingStage.VALIDATION
                
                if progress_callback:
                    progress = 30 + (iteration - 1) * 30
                    progress_callback(progress, f"Iteration {iteration}: Validating extraction...")
                
                # VALIDATION PHASE
                def validation_progress(pct, msg):
                    if progress_callback:
                        total_progress = 30 + (iteration - 1) * 30 + (pct * 0.2)
                        progress_callback(int(total_progress), f"Iter {iteration}: {msg}")
                
                is_valid, validation_report = self.validator.validate_extraction(result, pdf_text, validation_progress)
                
                # DECISION LOGIC
                confidence_threshold = 0.75  # Higher threshold for quality
                self.log(f"Validation result: Valid={is_valid}, Score={validation_report['confidence_score']:.2f}")
                
                if is_valid and validation_report['confidence_score'] >= confidence_threshold:
                    self.log("✅ High quality extraction achieved!")
                    self.status = AgentStatus.SUCCESS
                    result.current_stage = ProcessingStage.MANUAL_EDIT
                    break
                elif iteration == self.max_iterations:
                    self.log("⚠️ Max iterations reached. Proceeding with best result.")
                    self.status = AgentStatus.MANUAL_REVIEW
                    result.current_stage = ProcessingStage.MANUAL_EDIT
                    break
                else:
                    self.log(f"❌ Quality below threshold. Planning iteration {iteration + 1}...")
                    iteration += 1
            
            if progress_callback:
                progress_callback(95, "Finalizing processing results...")
            
            # Finalize result
            result.processing_time = time.time() - start_time
            result.agent_logs = (self.logs + self.extractor.logs + self.validator.logs)
            
            self.log(f"Processing complete in {result.processing_time:.2f}s with {iteration} iterations")
            
            if progress_callback:
                progress_callback(100, "AI processing complete!")
            
            return result
            
        except Exception as e:
            self.status = AgentStatus.ERROR
            self.log(f"Coordination failed: {str(e)}")
            if progress_callback:
                progress_callback(100, f"Error: {str(e)}")
            raise
    
    def _improve_extraction(self, previous_result: ExtractionResult, pdf_text: str, progress_callback) -> ExtractionResult:
        """Improve extraction based on validation feedback"""
        # For now, return the same result (improvement logic can be added later)
        # This could involve targeted re-extraction of problematic fields
        self.log("Using previous extraction result (improvement logic placeholder)")
        return previous_result

# ===== OPENAI CLIENT SETUP =====
def get_openai_client():
    """Get OpenAI client with enhanced error handling"""
    try:
        api_key = st.secrets.get("OPENAI_API_KEY")
        if not api_key:
            st.error("🔑 OpenAI API key not found in secrets!")
            st.info("Please add your OpenAI API key to Streamlit secrets.")
            return None
        
        client = openai.OpenAI(api_key=api_key, timeout=60.0)
        
        # Test the API key
        try:
            test_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1,
                timeout=10
            )
            st.sidebar.success("🔑 OpenAI API key verified!")
        except Exception as e:
            st.error(f"❌ OpenAI API key test failed: {str(e)}")
            return None
        
        return client
    except Exception as e:
        st.error(f"Failed to initialize OpenAI client: {str(e)}")
        return None

# ===== MANUAL EDITING INTERFACE =====
def display_manual_editing_interface(result: ExtractionResult, db_manager: DatabaseManager, submission_id: int):
    """Complete manual editing interface"""
    st.markdown("### ✏️ Manual Editing & Review")
    
    # Overall stats
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Fields", result.total_fields)
    with col2:
        fill_rate = (result.filled_fields / result.total_fields * 100) if result.total_fields > 0 else 0
        st.metric("Completion", f"{fill_rate:.0f}%")
    with col3:
        st.metric("Manual Edits", result.manual_edits_count)
    with col4:
        st.metric("Validation Score", f"{result.validation_score:.0f}%")
    
    # Part-by-part editing
    for part_num in sorted(result.parts.keys()):
        part = result.parts[part_num]
        
        # Part header with completion status
        filled_in_part = sum(1 for f in part.fields if f.field_value and f.field_value.strip())
        completion = (filled_in_part / len(part.fields) * 100) if part.fields else 0
        
        with st.expander(f"Part {part_num}: {part.title} ({filled_in_part}/{len(part.fields)} completed - {completion:.0f}%)", 
                        expanded=(part_num == 1)):
            
            if not part.fields:
                st.warning("No fields found in this part")
                continue
            
            # Bulk operations
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button(f"🔄 Refresh Part {part_num}", key=f"refresh_{part_num}"):
                    st.rerun()
            with col2:
                if st.button(f"✨ Auto-fill Empty Fields", key=f"autofill_{part_num}"):
                    _autofill_part_fields(part, result.form_number)
                    st.success("Auto-fill suggestions added!")
                    st.rerun()
            with col3:
                if st.button(f"📝 Mark Part Complete", key=f"complete_{part_num}"):
                    _mark_part_complete(part)
                    st.success(f"Part {part_num} marked as complete!")
                    st.rerun()
            
            # Field editing interface
            for field_idx, field in enumerate(part.fields):
                _display_field_editor(field, part_num, field_idx, db_manager, submission_id)
    
    # Save changes
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("💾 Save All Changes", type="primary"):
            _save_manual_changes(result, db_manager, submission_id)
            st.success("✅ All changes saved!")
            st.rerun()
    
    with col2:
        if st.button("🔄 Reset All Changes"):
            if st.confirm("Reset all manual changes? This cannot be undone."):
                _reset_manual_changes(result)
                st.success("Changes reset!")
                st.rerun()
    
    with col3:
        if st.button("➡️ Proceed to Questionnaire"):
            result.current_stage = ProcessingStage.QUESTIONNAIRE
            _save_manual_changes(result, db_manager, submission_id)
            st.rerun()

def _display_field_editor(field: ExtractedField, part_num: int, field_idx: int, db_manager: DatabaseManager, submission_id: int):
    """Individual field editing interface"""
    field_key = f"field_{part_num}_{field_idx}"
    
    st.markdown(f'<div class="field-editor">', unsafe_allow_html=True)
    
    # Field header
    col1, col2, col3, col4 = st.columns([2, 3, 2, 1])
    
    with col1:
        st.markdown(f"**{field.field_number}**")
        if field.is_required:
            st.markdown("🔴 Required")
        if field.manually_edited:
            st.markdown("✏️ Edited")
    
    with col2:
        st.markdown(f"**{field.field_label}**")
        st.caption(f"Type: {field.field_type.value}")
    
    with col3:
        confidence_color = "green" if field.confidence > 0.7 else "orange" if field.confidence > 0.4 else "red"
        st.markdown(f'<span style="color:{confidence_color};">Confidence: {field.confidence:.0%}</span>', 
                   unsafe_allow_html=True)
    
    with col4:
        if field.validation_errors:
            st.markdown("⚠️ Issues")
    
    # Current value display and editing
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Value editor based on field type
        if field.field_type == FieldType.CHECKBOX:
            current_value = st.selectbox(
                f"Value for {field.field_number}",
                ["", "Yes", "No", "N/A"],
                index=["", "Yes", "No", "N/A"].index(field.field_value) if field.field_value in ["", "Yes", "No", "N/A"] else 0,
                key=f"value_{field_key}"
            )
        elif field.field_type == FieldType.DATE:
            try:
                if field.field_value:
                    # Try to parse existing date
                    date_val = pd.to_datetime(field.field_value).date()
                else:
                    date_val = None
            except:
                date_val = None
            
            current_value = st.date_input(
                f"Value for {field.field_number}",
                value=date_val,
                key=f"value_{field_key}"
            )
            current_value = str(current_value) if current_value else ""
        else:
            # Text input for most field types
            current_value = st.text_input(
                f"Value for {field.field_number}",
                value=field.field_value,
                placeholder=f"Enter {field.field_type.value}...",
                key=f"value_{field_key}"
            )
        
        # Update field if value changed
        if current_value != field.field_value:
            old_value = field.field_value
            field.edit_value(current_value, "manual")
            db_manager.log_manual_edit(submission_id, field_idx, old_value, current_value, "Manual edit via interface")
    
    with col2:
        # Additional field actions
        if field.suggested_values:
            st.markdown("**Suggestions:**")
            for i, suggestion in enumerate(field.suggested_values[:3]):
                if st.button(f"Use: {suggestion[:20]}...", key=f"suggest_{field_key}_{i}"):
                    field.edit_value(suggestion, "suggestion")
                    st.rerun()
        
        if field.validation_errors:
            st.markdown("**Issues:**")
            for error in field.validation_errors:
                st.markdown(f"⚠️ {error}")
        
        # Field-specific helpers
        if field.field_type == FieldType.ADDRESS:
            if st.button("🗺️ Address Helper", key=f"addr_{field_key}"):
                _show_address_helper(field)
        elif field.field_type == FieldType.COUNTRY:
            if st.button("🌍 Country List", key=f"country_{field_key}"):
                _show_country_helper(field)
    
    st.markdown('</div>', unsafe_allow_html=True)

def _autofill_part_fields(part: FormPart, form_type: str):
    """Auto-fill empty fields with common values"""
    common_values = {
        'I-90': {
            'country': 'United States',
            'state': 'California',
            'language': 'English'
        },
        'I-130': {
            'country': 'United States',
            'relationship': 'Spouse'
        }
    }
    
    form_defaults = common_values.get(form_type, {})
    
    for field in part.fields:
        if not field.field_value or not field.field_value.strip():
            # Add suggestions based on field type and label
            suggestions = []
            
            label_lower = field.field_label.lower()
            if 'country' in label_lower:
                suggestions = ['United States', 'Canada', 'Mexico', 'United Kingdom']
            elif 'state' in label_lower:
                suggestions = ['California', 'New York', 'Texas', 'Florida']
            elif 'language' in label_lower:
                suggestions = ['English', 'Spanish', 'Chinese', 'French']
            elif 'yes' in label_lower or 'no' in label_lower:
                suggestions = ['No', 'Yes']
            
            field.suggested_values = suggestions

def _mark_part_complete(part: FormPart):
    """Mark part as complete and flag remaining issues"""
    for field in part.fields:
        if field.is_required and (not field.field_value or not field.field_value.strip()):
            field.field_value = "N/A - Not Applicable"
            field.edit_value(field.field_value, "auto_complete")

def _save_manual_changes(result: ExtractionResult, db_manager: DatabaseManager, submission_id: int):
    """Save all manual changes to database"""
    try:
        # Update statistics
        result.calculate_stats()
        
        # Save to database
        submission_data = {
            'id': submission_id,
            'form_type': result.form_number,
            'entry_mode': 'ai_agents_manual',
            'total_fields': result.total_fields,
            'completed_fields': result.filled_fields,
            'validation_score': result.validation_score,
            'json_data': json.dumps(result.final_validation_report),
            'status': 'manual_review',
            'notes': f"Manual editing completed. {result.manual_edits_count} fields edited.",
            'iterations': result.extraction_iterations,
            'current_stage': result.current_stage.value,
            'manual_edits_count': result.manual_edits_count,
            'questionnaire_completed': result.questionnaire_completed,
            'completion_percentage': (result.filled_fields / result.total_fields * 100) if result.total_fields > 0 else 0
        }
        
        db_manager.save_form_submission(submission_data)
        db_manager.save_extracted_fields(submission_id, result)
        
    except Exception as e:
        st.error(f"Error saving changes: {e}")

def _reset_manual_changes(result: ExtractionResult):
    """Reset all manual changes"""
    for part in result.parts.values():
        for field in part.fields:
            if field.manually_edited:
                field.field_value = field.original_value
                field.manually_edited = False
                field.edit_timestamp = None
                field.validation_errors = []

def _show_address_helper(field: ExtractedField):
    """Show address formatting helper"""
    st.info("""
    **Address Format:**
    • Street Number and Name
    • Apartment/Suite (if applicable)
    • City, State ZIP Code
    • Country (if not US)
    
    Example: 123 Main Street, Apt 4B, Anytown, CA 90210
    """)

def _show_country_helper(field: ExtractedField):
    """Show country selection helper"""
    countries = [
        "United States", "Canada", "Mexico", "United Kingdom", "Germany", 
        "France", "Italy", "Spain", "China", "Japan", "India", "Brazil"
    ]
    
    selected = st.selectbox("Select Country:", [""] + countries)
    if selected and st.button("Apply"):
        field.edit_value(selected, "helper")
        st.rerun()

# ===== QUESTIONNAIRE SYSTEM =====
def display_questionnaire_interface(result: ExtractionResult, db_manager: DatabaseManager, submission_id: int):
    """Interactive questionnaire for missing/unclear fields"""
    st.markdown("### 📋 Smart Questionnaire")
    st.info("Let's gather information for fields that need clarification or are missing.")
    
    # Identify fields needing questionnaire
    questionnaire_fields = []
    for part in result.parts.values():
        for field in part.fields:
            if (field.is_required and not field.field_value) or field.validation_errors or field.confidence < 0.5:
                questionnaire_fields.append(field)
    
    if not questionnaire_fields:
        st.success("🎉 No additional information needed! All fields are complete.")
        if st.button("✅ Mark Form Complete"):
            result.current_stage = ProcessingStage.COMPLETE
            result.questionnaire_completed = True
            _save_manual_changes(result, db_manager, submission_id)
            st.rerun()
        return
    
    st.write(f"Found {len(questionnaire_fields)} fields that need your input:")
    
    # Progress indicator
    completed_responses = sum(1 for f in questionnaire_fields if f.questionnaire_response)
    progress = completed_responses / len(questionnaire_fields) if questionnaire_fields else 1
    st.progress(progress)
    st.write(f"Progress: {completed_responses}/{len(questionnaire_fields)} questions answered")
    
    # Group questions by part
    questions_by_part = {}
    for field in questionnaire_fields:
        part_name = f"Part {field.part_number}: {field.part_name}"
        if part_name not in questions_by_part:
            questions_by_part[part_name] = []
        questions_by_part[part_name].append(field)
    
    # Display questionnaire by part
    for part_name, fields in questions_by_part.items():
        with st.expander(f"{part_name} ({len(fields)} questions)", expanded=True):
            for i, field in enumerate(fields):
                _display_questionnaire_question(field, f"{part_name}_{i}", db_manager, submission_id)
    
    # Completion actions
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("💾 Save Responses"):
            _save_questionnaire_responses(questionnaire_fields, db_manager, submission_id)
            st.success("Responses saved!")
            st.rerun()
    
    with col2:
        all_answered = all(f.questionnaire_response for f in questionnaire_fields)
        if st.button("✅ Complete Questionnaire", disabled=not all_answered):
            if all_answered:
                _complete_questionnaire(result, questionnaire_fields, db_manager, submission_id)
                st.success("🎉 Questionnaire completed!")
                st.balloons()
                st.rerun()
            else:
                st.warning("Please answer all questions before completing.")
    
    with col3:
        if st.button("⬅️ Back to Manual Editing"):
            result.current_stage = ProcessingStage.MANUAL_EDIT
            st.rerun()

def _display_questionnaire_question(field: ExtractedField, question_key: str, db_manager: DatabaseManager, submission_id: int):
    """Display individual questionnaire question"""
    st.markdown(f'<div class="questionnaire-card">', unsafe_allow_html=True)
    
    # Question header
    st.markdown(f"**Question for {field.field_number}:** {field.field_label}")
    
    # Show context
    if field.validation_errors:
        st.error(f"Issue with current value: {', '.join(field.validation_errors)}")
    
    if field.field_value:
        st.info(f"Current value: {field.field_value}")
    
    if field.confidence < 0.5:
        st.warning(f"Low confidence extraction (confidence: {field.confidence:.0%})")
    
    # Question based on field type
    question_text = _generate_question_text(field)
    st.markdown(f"*{question_text}*")
    
    # Answer input
    answer_key = f"answer_{question_key}"
    
    if field.field_type == FieldType.CHECKBOX:
        answer = st.radio(
            "Your answer:",
            ["Yes", "No", "Not Applicable"],
            key=answer_key,
            index=["Yes", "No", "Not Applicable"].index(field.questionnaire_response) if field.questionnaire_response in ["Yes", "No", "Not Applicable"] else 0
        )
    elif field.field_type == FieldType.DATE:
        st.write("Please enter the date:")
        answer = st.date_input(
            "Select date:",
            key=answer_key
        )
        answer = str(answer) if answer else ""
    else:
        # Provide suggestions if available
        if field.suggested_values:
            st.write("Common answers:")
            cols = st.columns(min(3, len(field.suggested_values)))
            for i, suggestion in enumerate(field.suggested_values[:3]):
                if cols[i].button(f"Use: {suggestion}", key=f"suggest_{question_key}_{i}"):
                    field.questionnaire_response = suggestion
                    field.field_value = suggestion
                    field.edit_value(suggestion, "questionnaire")
                    st.rerun()
        
        answer = st.text_input(
            "Your answer:",
            value=field.questionnaire_response,
            placeholder=_get_placeholder_text(field),
            key=answer_key
        )
    
    # Update response
    if answer != field.questionnaire_response:
        field.questionnaire_response = answer
        field.field_value = answer  # Also update the field value
        field.edit_value(answer, "questionnaire")
    
    # Additional help
    if st.button(f"❓ Need help with this question?", key=f"help_{question_key}"):
        _show_field_help(field)
    
    st.markdown('</div>', unsafe_allow_html=True)

def _generate_question_text(field: ExtractedField) -> str:
    """Generate appropriate question text for field"""
    label = field.field_label.lower()
    
    if 'name' in label:
        return f"What is your {field.field_label.lower()}?"
    elif 'address' in label:
        return f"What is your {field.field_label.lower()}? Please include street, city, state, and ZIP code."
    elif 'date' in label or 'birth' in label:
        return f"What is the {field.field_label.lower()}? Please use MM/DD/YYYY format."
    elif 'phone' in label:
        return f"What is your {field.field_label.lower()}? Please include area code."
    elif 'email' in label:
        return f"What is your {field.field_label.lower()}?"
    elif 'country' in label:
        return f"What {field.field_label.lower()} should be entered here?"
    elif any(word in label for word in ['yes', 'no', 'have', 'did', 'will', 'are']):
        return f"{field.field_label}?"
    else:
        return f"Please provide the information for: {field.field_label}"

def _get_placeholder_text(field: ExtractedField) -> str:
    """Get placeholder text for field input"""
    if field.field_type == FieldType.NAME:
        return "Enter full name..."
    elif field.field_type == FieldType.ADDRESS:
        return "123 Main St, City, State 12345"
    elif field.field_type == FieldType.PHONE:
        return "(555) 123-4567"
    elif field.field_type == FieldType.EMAIL:
        return "your.email@example.com"
    elif field.field_type == FieldType.NUMBER:
        return "Enter number..."
    else:
        return f"Enter {field.field_type.value}..."

def _show_field_help(field: ExtractedField):
    """Show context-specific help for field"""
    help_text = {
        FieldType.NAME: "Enter your full legal name as it appears on official documents.",
        FieldType.ADDRESS: "Enter your complete mailing address including apartment/suite number if applicable.",
        FieldType.DATE: "Use MM/DD/YYYY format. For example: 12/31/1990",
        FieldType.PHONE: "Include area code. Format: (555) 123-4567",
        FieldType.EMAIL: "Enter a valid email address you check regularly.",
        FieldType.COUNTRY: "Enter the full country name, e.g., 'United States' not 'US'",
    }
    
    help_msg = help_text.get(field.field_type, "Please provide accurate information as requested.")
    st.info(f"💡 {help_msg}")

def _save_questionnaire_responses(fields: List[ExtractedField], db_manager: DatabaseManager, submission_id: int):
    """Save questionnaire responses to database"""
    for field in fields:
        if field.questionnaire_response:
            db_manager.save_questionnaire_response(
                submission_id, 
                field.field_number,
                field.field_label,
                field.questionnaire_response
            )

def _complete_questionnaire(result: ExtractionResult, questionnaire_fields: List[ExtractedField], db_manager: DatabaseManager, submission_id: int):
    """Complete questionnaire and update form"""
    # Apply all questionnaire responses to field values
    for field in questionnaire_fields:
        if field.questionnaire_response:
            field.edit_value(field.questionnaire_response, "questionnaire")
    
    # Update form status
    result.questionnaire_completed = True
    result.current_stage = ProcessingStage.COMPLETE
    
    # Save everything
    _save_questionnaire_responses(questionnaire_fields, db_manager, submission_id)
    _save_manual_changes(result, db_manager, submission_id)

# ===== MAIN APPLICATION =====
def main():
    st.markdown(
        '<div class="main-header">'
        '<h1>🤖 Complete AI-Powered USCIS Form Processing System</h1>'
        '<p>Advanced AI extraction → Validation loops → Manual editing → Smart questionnaire</p>'
        '</div>', 
        unsafe_allow_html=True
    )
    
    # Dependency checks
    if not PYMUPDF_AVAILABLE:
        st.error("❌ PyMuPDF is required! Install with: `pip install PyMuPDF`")
        st.stop()
    
    if not OPENAI_AVAILABLE:
        st.error("❌ OpenAI library is required! Install with: `pip install openai`")
        st.stop()
    
    # Initialize OpenAI client
    openai_client = get_openai_client()
    if not openai_client:
        st.stop()
    
    # Initialize session state
    if 'db_manager' not in st.session_state:
        st.session_state.db_manager = DatabaseManager()
        st.sidebar.success("✅ Database initialized!")
    
    if 'extraction_result' not in st.session_state:
        st.session_state.extraction_result = None
    if 'current_submission_id' not in st.session_state:
        st.session_state.current_submission_id = None
    if 'processing_stage' not in st.session_state:
        st.session_state.processing_stage = ProcessingStage.UPLOAD
    
    db_manager = st.session_state.db_manager
    
    # Enhanced sidebar
    with st.sidebar:
        st.markdown("## ⚙️ System Settings")
        
        # Performance settings
        debug_mode = st.checkbox("🔧 Debug Mode", value=False)
        max_iterations = st.slider("Max AI Iterations", 1, 4, 3)
        processing_timeout = st.slider("Timeout (seconds)", 60, 300, 150)
        
        # Processing options
        st.markdown("## 🚀 Processing Options")
        enable_manual_edit = st.checkbox("✏️ Enable Manual Editing", value=True)
        enable_questionnaire = st.checkbox("📋 Enable Smart Questionnaire", value=True)
        auto_save = st.checkbox("💾 Auto-save Changes", value=True)
        
        # Current session info
        if st.session_state.extraction_result:
            st.markdown("## 📊 Current Session")
            result = st.session_state.extraction_result
            st.metric("Form Type", result.form_number)
            st.metric("Stage", result.current_stage.value.title())
            st.metric("Completion", f"{result.filled_fields}/{result.total_fields}")
            
            # Stage navigation
            st.markdown("### 🔄 Stage Navigation")
            stages = [ProcessingStage.EXTRACTION, ProcessingStage.MANUAL_EDIT, ProcessingStage.QUESTIONNAIRE, ProcessingStage.COMPLETE]
            current_stage_idx = stages.index(result.current_stage) if result.current_stage in stages else 0
            
            for i, stage in enumerate(stages):
                if i <= current_stage_idx:
                    st.success(f"✅ {stage.value.title()}")
                elif i == current_stage_idx + 1:
                    st.info(f"➡️ {stage.value.title()} (Next)")
                else:
                    st.warning(f"⏳ {stage.value.title()}")
        
        # Database management
        st.markdown("## 🗄️ Database")
        submissions = db_manager.get_form_submissions(limit=5)
        st.write(f"📄 {len(submissions)} recent submissions")
        
        if st.button("🗑️ Reset Database"):
            if st.confirm("This will delete all data. Continue?"):
                os.remove(db_manager.db_path)
                st.session_state.db_manager = DatabaseManager()
                st.success("Database reset!")
                st.rerun()
    
    # Main content based on processing stage
    current_stage = st.session_state.processing_stage
    if st.session_state.extraction_result:
        current_stage = st.session_state.extraction_result.current_stage
    
    # Stage-based interface
    if current_stage == ProcessingStage.UPLOAD:
        # File upload and processing
        st.markdown("### 📤 Upload & Process USCIS Form")
        
        uploaded_file = st.file_uploader(
            "Choose a USCIS form PDF",
            type=['pdf'],
            help="Upload any USCIS form for AI processing"
        )
        
        if uploaded_file:
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                st.success(f"✅ File uploaded: {uploaded_file.name}")
                form_type_hint = st.selectbox(
                    "Form Type (optional)",
                    ["Auto-detect", "I-90", "I-130", "I-485", "G-28", "N-400", "I-129"],
                )
            
            with col2:
                if st.button("🔍 Test PDF"):
                    text = extract_pdf_text_enhanced(uploaded_file)
                    if text:
                        st.success("✅ PDF readable")
                        with st.expander("Preview"):
                            st.text_area("Sample:", text[:300], height=100)
            
            with col3:
                if st.button("🚀 Start AI Processing", type="primary"):
                    # Process with full pipeline
                    process_uploaded_file(uploaded_file, form_type_hint, openai_client, db_manager, 
                                        debug_mode, max_iterations, processing_timeout)
    
    elif current_stage == ProcessingStage.MANUAL_EDIT:
        if st.session_state.extraction_result and enable_manual_edit:
            display_manual_editing_interface(
                st.session_state.extraction_result, 
                db_manager, 
                st.session_state.current_submission_id
            )
        else:
            st.info("Manual editing is disabled or no extraction result available.")
    
    elif current_stage == ProcessingStage.QUESTIONNAIRE:
        if st.session_state.extraction_result and enable_questionnaire:
            display_questionnaire_interface(
                st.session_state.extraction_result,
                db_manager,
                st.session_state.current_submission_id
            )
        else:
            st.info("Questionnaire is disabled or no extraction result available.")
    
    elif current_stage == ProcessingStage.COMPLETE:
        display_completion_interface(st.session_state.extraction_result, db_manager)
    
    # Additional tabs for analytics and management
    tabs = st.tabs(["📊 Analytics", "💾 Database", "🔧 System"])
    
    with tabs[0]:
        display_analytics_dashboard(db_manager)
    
    with tabs[1]:
        display_database_management(db_manager)
    
    with tabs[2]:
        display_system_diagnostics()

def process_uploaded_file(uploaded_file, form_type_hint, openai_client, db_manager, debug_mode, max_iterations, processing_timeout):
    """Complete file processing pipeline"""
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    def update_progress(pct, msg):
        progress_bar.progress(pct)
        status_text.write(f"🤖 {msg}")
    
    try:
        # Extract PDF text
        update_progress(10, "Extracting PDF text...")
        pdf_text = extract_pdf_text_enhanced(uploaded_file)
        
        if not pdf_text:
            st.error("❌ Failed to extract text from PDF")
            return
        
        # Initialize agents
        update_progress(20, "Initializing AI agents...")
        extractor = ExtractorAgent(openai_client, debug_mode, timeout=60)
        validator = ValidationAgent(openai_client, debug_mode, timeout=45)
        coordinator = CoordinatorAgent(openai_client, extractor, validator, max_iterations, debug_mode, processing_timeout)
        
        # Process with coordinator
        form_type = None if form_type_hint == "Auto-detect" else form_type_hint
        result = coordinator.process_form(pdf_text, form_type, update_progress)
        
        # Save to database
        update_progress(95, "Saving to database...")
        submission_data = {
            'form_type': result.form_number,
            'entry_mode': 'ai_agents_complete',
            'total_fields': result.total_fields,
            'completed_fields': result.filled_fields,
            'validation_score': result.validation_score,
            'pdf_filename': uploaded_file.name,
            'json_data': json.dumps(result.final_validation_report),
            'status': 'processing',
            'notes': f"AI processing completed with {result.extraction_iterations} iterations",
            'iterations': result.extraction_iterations,
            'current_stage': ProcessingStage.MANUAL_EDIT.value,
            'manual_edits_count': 0,
            'questionnaire_completed': False,
            'completion_percentage': (result.filled_fields / result.total_fields * 100) if result.total_fields > 0 else 0
        }
        
        submission_id = db_manager.save_form_submission(submission_data)
        db_manager.save_extracted_fields(submission_id, result)
        
        # Update session state
        st.session_state.extraction_result = result
        st.session_state.current_submission_id = submission_id
        st.session_state.processing_stage = ProcessingStage.MANUAL_EDIT
        
        progress_bar.progress(100)
        status_text.empty()
        
        # Show results
        if result.validation_score >= 0.8:
            st.success(f"🎉 Excellent extraction! Score: {result.validation_score:.1%}")
            st.balloons()
        elif result.validation_score >= 0.6:
            st.success(f"✅ Good extraction! Score: {result.validation_score:.1%}")
        else:
            st.warning(f"⚠️ Fair extraction. Score: {result.validation_score:.1%}")
        
        st.info("Proceeding to manual editing stage...")
        time.sleep(2)
        st.rerun()
        
    except Exception as e:
        progress_bar.empty()
        status_text.empty()
        st.error(f"💥 Processing failed: {str(e)}")
        if debug_mode:
            st.exception(e)

def display_completion_interface(result: ExtractionResult, db_manager: DatabaseManager):
    """Display completion interface with export options"""
    st.markdown("### 🎉 Form Processing Complete!")
    
    # Final statistics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Fields", result.total_fields)
    with col2:
        st.metric("Completed Fields", result.filled_fields)
    with col3:
        st.metric("Manual Edits", result.manual_edits_count)
    with col4:
        completion = (result.filled_fields / result.total_fields * 100) if result.total_fields > 0 else 0
        st.metric("Completion Rate", f"{completion:.0f}%")
    
    # Success message
    if completion >= 90:
        st.success("🌟 Excellent! Your form is fully completed.")
    elif completion >= 75:
        st.success("✅ Great! Your form is mostly complete.")
    else:
        st.warning("⚠️ Form completed but some fields may need attention.")
    
    # Export options
    st.markdown("### 💾 Export Your Data")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📄 Download PDF Summary", type="primary"):
            pdf_data = generate_pdf_summary(result)
            st.download_button(
                "Download PDF",
                data=pdf_data,
                file_name=f"{result.form_number}_completed.pdf",
                mime="application/pdf"
            )
    
    with col2:
        if st.button("📊 Download Excel Report"):
            excel_data = generate_excel_report(result)
            st.download_button(
                "Download Excel",
                data=excel_data,
                file_name=f"{result.form_number}_report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    
    with col3:
        if st.button("📋 Download JSON Data"):
            json_data = generate_json_export(result)
            st.download_button(
                "Download JSON",
                data=json_data,
                file_name=f"{result.form_number}_data.json",
                mime="application/json"
            )
    
    # New form option
    st.markdown("---")
    if st.button("🆕 Process New Form"):
        st.session_state.extraction_result = None
        st.session_state.current_submission_id = None
        st.session_state.processing_stage = ProcessingStage.UPLOAD
        st.rerun()

def display_analytics_dashboard(db_manager: DatabaseManager):
    """Display analytics dashboard"""
    st.markdown("### 📊 Processing Analytics")
    
    submissions = db_manager.get_form_submissions(100)
    
    if not submissions:
        st.info("No data available yet. Process some forms to see analytics!")
        return
    
    # Create DataFrame
    df = pd.DataFrame(submissions)
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Forms", len(df))
    with col2:
        avg_completion = df['completion_percentage'].mean()
        st.metric("Avg Completion", f"{avg_completion:.1f}%")
    with col3:
        avg_score = df['validation_score'].mean()
        st.metric("Avg AI Score", f"{avg_score:.1f}%")
    with col4:
        manual_edits = df['manual_edits_count'].sum()
        st.metric("Total Manual Edits", manual_edits)
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Form Types Processed")
        form_counts = df['form_type'].value_counts()
        st.bar_chart(form_counts)
    
    with col2:
        st.markdown("#### Processing Stages")
        stage_counts = df['current_stage'].value_counts()
        st.bar_chart(stage_counts)

def display_database_management(db_manager: DatabaseManager):
    """Display database management interface"""
    st.markdown("### 💾 Database Management")
    
    # Recent submissions
    submissions = db_manager.get_form_submissions(20)
    
    if submissions:
        df = pd.DataFrame(submissions)
        st.dataframe(df[['form_type', 'submission_date', 'current_stage', 'completion_percentage', 'validation_score']], 
                    use_container_width=True)
        
        # Detailed view
        if st.selectbox("Select submission for details", [f"ID {s['id']} - {s['form_type']}" for s in submissions]):
            # Show detailed submission info
            st.info("Detailed view would show full submission data here")
    else:
        st.info("No submissions found")

def display_system_diagnostics():
    """Display system diagnostics"""
    st.markdown("### 🔧 System Diagnostics")
    
    # Python environment
    st.markdown("#### Python Environment")
    import sys
    st.code(f"Python version: {sys.version}")
    
    # Package versions
    st.markdown("#### Package Versions")
    packages = ['streamlit', 'openai', 'pandas']
    for pkg in packages:
        try:
            module = __import__(pkg)
            version = getattr(module, '__version__', 'Unknown')
            st.success(f"✅ {pkg}: {version}")
        except ImportError:
            st.error(f"❌ {pkg}: Not installed")
    
    # PyMuPDF check
    if PYMUPDF_AVAILABLE:
        st.success(f"✅ PyMuPDF: {fitz.version[0]}")
    else:
        st.error("❌ PyMuPDF: Not available")

# Helper functions for export
def generate_pdf_summary(result: ExtractionResult) -> bytes:
    """Generate PDF summary (placeholder)"""
    return b"PDF summary placeholder"

def generate_excel_report(result: ExtractionResult) -> bytes:
    """Generate Excel report (placeholder)"""
    return b"Excel report placeholder"

def generate_json_export(result: ExtractionResult) -> str:
    """Generate JSON export"""
    export_data = {
        'form_info': {
            'form_number': result.form_number,
            'form_title': result.form_title,
            'processing_time': result.processing_time,
            'validation_score': result.validation_score
        },
        'parts': {}
    }
    
    for part_num, part in result.parts.items():
        export_data['parts'][f'part_{part_num}'] = {
            'title': part.title,
            'fields': [field.to_dict() for field in part.fields]
        }
    
    return json.dumps(export_data, indent=2)

if __name__ == "__main__":
    main()
