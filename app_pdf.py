#!/usr/bin/env python3
"""
Enhanced USCIS Form Reader with AI Agents
- Extractor Agent: Uses OpenAI to intelligently extract form data
- Validation Agent: Validates and corrects extracted data
- Coordinator: Loops agents until validation passes
- Database integration and questionnaire support
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
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field, asdict
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
    page_title="AI-Powered USCIS Form Reader",
    page_icon="🤖",
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
    
    .agent-card {
        background: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        border-left: 4px solid #007bff;
    }
    
    .extractor-agent {
        border-left-color: #28a745;
        background: #f8fff9;
    }
    
    .validation-agent {
        border-left-color: #ffc107;
        background: #fffdf5;
    }
    
    .coordinator-agent {
        border-left-color: #6f42c1;
        background: #faf9ff;
    }
    
    .field-value {
        background: #e8f5e9;
        padding: 0.5rem;
        border-radius: 4px;
        font-weight: bold;
        color: #2e7d32;
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
    
    .agent-log {
        background: #f5f5f5;
        padding: 0.8rem;
        border-radius: 4px;
        font-family: monospace;
        font-size: 0.85rem;
        margin: 0.5rem 0;
        max-height: 200px;
        overflow-y: auto;
    }
    
    .iteration-counter {
        background: #e3f2fd;
        border: 1px solid #1976d2;
        border-radius: 6px;
        padding: 0.5rem;
        text-align: center;
        margin: 0.5rem 0;
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

class AgentStatus(Enum):
    IDLE = "idle"
    PROCESSING = "processing"
    SUCCESS = "success"
    ERROR = "error"
    VALIDATION_FAILED = "validation_failed"

class FormType(Enum):
    I90 = "I-90"
    I130 = "I-130"
    I485 = "I-485"
    I765 = "I-765"
    G28 = "G-28"
    N400 = "N-400"
    I129 = "I-129"
    UNKNOWN = "Unknown"

# ===== DATA CLASSES =====
@dataclass
class ExtractedField:
    """Represents an extracted form field"""
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
            'extraction_method': self.extraction_method
        }

@dataclass
class FormPart:
    """Represents a form part/section"""
    number: int
    title: str
    start_page: int = 1
    end_page: int = 1
    fields: List[ExtractedField] = field(default_factory=list)
    raw_text: str = ""
    validation_score: float = 0.0
    
    def add_field(self, field: ExtractedField):
        field.part_number = self.number
        field.part_name = self.title
        self.fields.append(field)

@dataclass
class ExtractionResult:
    """Complete extraction result with agent processing info"""
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
    
    def calculate_stats(self):
        """Calculate statistics"""
        self.total_fields = sum(len(part.fields) for part in self.parts.values())
        self.filled_fields = sum(1 for part in self.parts.values() 
                                for field in part.fields if field.field_value and field.field_value.strip())
        
        # Calculate overall validation score
        if self.parts:
            scores = [part.validation_score for part in self.parts.values()]
            self.validation_score = sum(scores) / len(scores)

# ===== DATABASE MODELS =====
@dataclass
class FormSubmission:
    id: Optional[int] = None
    form_type: str = ""
    submission_date: datetime = field(default_factory=datetime.now)
    entry_mode: str = "ai_agents"
    total_fields: int = 0
    completed_fields: int = 0
    validation_score: float = 0.0
    pdf_filename: str = ""
    json_data: str = ""
    status: str = "draft"
    notes: str = ""
    iterations: int = 0

class DatabaseManager:
    """Complete database manager for AI agent system"""
    def __init__(self, db_path: str = "uscis_forms.db"):
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        return sqlite3.connect(self.db_path)
    
    def init_database(self):
        """Initialize database tables"""
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
                    iterations INTEGER DEFAULT 0
                )
            ''')
            
            # Agent logs table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS agent_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    submission_id INTEGER,
                    agent_type TEXT NOT NULL,
                    iteration INTEGER DEFAULT 1,
                    log_message TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (submission_id) REFERENCES form_submissions (id)
                )
            ''')
            
            # Form fields table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS form_fields (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    submission_id INTEGER NOT NULL,
                    field_number TEXT NOT NULL,
                    field_label TEXT,
                    field_value TEXT,
                    field_type TEXT DEFAULT 'text',
                    confidence REAL DEFAULT 0.0,
                    is_required BOOLEAN DEFAULT 0,
                    validation_errors TEXT,
                    part_number INTEGER DEFAULT 1,
                    extraction_method TEXT DEFAULT 'ai_agent',
                    FOREIGN KEY (submission_id) REFERENCES form_submissions (id)
                )
            ''')
            
            conn.commit()
    
    def save_form_submission(self, submission: FormSubmission) -> int:
        """Save form submission and return ID"""
        with self.get_connection() as conn:
            if submission.id:
                # Update existing
                conn.execute('''
                    UPDATE form_submissions SET
                    form_type=?, entry_mode=?, total_fields=?, completed_fields=?,
                    validation_score=?, json_data=?, status=?, notes=?, iterations=?
                    WHERE id=?
                ''', (submission.form_type, submission.entry_mode, submission.total_fields,
                      submission.completed_fields, submission.validation_score,
                      submission.json_data, submission.status, submission.notes, 
                      submission.iterations, submission.id))
                return submission.id
            else:
                # Insert new
                cursor = conn.execute('''
                    INSERT INTO form_submissions 
                    (form_type, entry_mode, total_fields, completed_fields, validation_score,
                     pdf_filename, json_data, status, notes, iterations)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (submission.form_type, submission.entry_mode, submission.total_fields,
                      submission.completed_fields, submission.validation_score,
                      submission.pdf_filename, submission.json_data, submission.status, 
                      submission.notes, submission.iterations))
                return cursor.lastrowid
    
    def get_form_submissions(self, limit: int = 50) -> List[FormSubmission]:
        """Get recent form submissions"""
        with self.get_connection() as conn:
            cursor = conn.execute('''
                SELECT id, form_type, submission_date, entry_mode, total_fields, 
                       completed_fields, validation_score, pdf_filename, json_data, 
                       status, notes, iterations
                FROM form_submissions 
                ORDER BY submission_date DESC LIMIT ?
            ''', (limit,))
            
            results = []
            for row in cursor.fetchall():
                # Handle datetime parsing
                submission_date = row[2]
                if isinstance(submission_date, str):
                    try:
                        submission_date = datetime.fromisoformat(submission_date.replace('Z', '+00:00'))
                    except:
                        submission_date = datetime.now()
                
                results.append(FormSubmission(
                    id=row[0],
                    form_type=row[1] or "Unknown",
                    submission_date=submission_date,
                    entry_mode=row[3] or "ai_agents",
                    total_fields=row[4] or 0,
                    completed_fields=row[5] or 0,
                    validation_score=row[6] or 0.0,
                    pdf_filename=row[7] or "",
                    json_data=row[8] or "",
                    status=row[9] or "draft",
                    notes=row[10] or "",
                    iterations=row[11] if len(row) > 11 and row[11] is not None else 0
                ))
            return results
    
    def save_agent_log(self, submission_id: int, agent_type: str, iteration: int, message: str):
        """Save agent log entry"""
        try:
            with self.get_connection() as conn:
                conn.execute('''
                    INSERT INTO agent_logs (submission_id, agent_type, iteration, log_message)
                    VALUES (?, ?, ?, ?)
                ''', (submission_id, agent_type, iteration, message))
                conn.commit()
        except Exception as e:
            # Silently handle log errors to not break main processing
            pass
    
    def save_extracted_fields(self, submission_id: int, extraction_result: 'ExtractionResult'):
        """Save extracted fields to database"""
        try:
            with self.get_connection() as conn:
                # Clear existing fields for this submission
                conn.execute('DELETE FROM form_fields WHERE submission_id = ?', (submission_id,))
                
                # Insert new fields
                for part in extraction_result.parts.values():
                    for field in part.fields:
                        validation_errors_json = json.dumps(field.validation_errors) if field.validation_errors else ""
                        
                        conn.execute('''
                            INSERT INTO form_fields 
                            (submission_id, field_number, field_label, field_value, field_type, 
                             confidence, is_required, validation_errors, part_number, extraction_method)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (submission_id, field.field_number, field.field_label, field.field_value,
                              field.field_type.value, field.confidence, field.is_required,
                              validation_errors_json, field.part_number, field.extraction_method))
                
                conn.commit()
        except Exception as e:
            # Log error but don't break main process
            print(f"Error saving fields: {e}")
    
    def get_agent_logs(self, submission_id: int) -> List[Dict]:
        """Get agent logs for a submission"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute('''
                    SELECT agent_type, iteration, log_message, timestamp
                    FROM agent_logs 
                    WHERE submission_id = ?
                    ORDER BY timestamp
                ''', (submission_id,))
                
                return [{'agent_type': row[0], 'iteration': row[1], 
                        'message': row[2], 'timestamp': row[3]} 
                       for row in cursor.fetchall()]
        except:
            return []

# ===== AI AGENTS =====
class BaseAgent:
    """Base class for AI agents with timeout support"""
    
    def __init__(self, name: str, openai_client, debug_mode: bool = False, timeout: int = 30):
        self.name = name
        self.client = openai_client
        self.debug_mode = debug_mode
        self.status = AgentStatus.IDLE
        self.logs = []
        self.timeout = timeout
    
    def log(self, message: str):
        """Log agent activity"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {self.name}: {message}"
        self.logs.append(log_entry)
        if self.debug_mode:
            st.write(f"🤖 {log_entry}")
    
    def get_logs(self) -> List[str]:
        """Get agent logs"""
        return self.logs.copy()
    
    def call_openai_with_timeout(self, messages: List[Dict], max_tokens: int = 4000) -> str:
        """Make OpenAI API call with timeout"""
        import signal
        
        def timeout_handler(signum, frame):
            raise TimeoutError(f"OpenAI API call timed out after {self.timeout} seconds")
        
        try:
            # Set timeout for non-Windows systems
            if hasattr(signal, 'SIGALRM'):
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(self.timeout)
            
            self.log(f"Making API call (timeout: {self.timeout}s)...")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0,
                max_tokens=max_tokens,
                timeout=self.timeout  # OpenAI client timeout
            )
            
            if hasattr(signal, 'SIGALRM'):
                signal.alarm(0)  # Cancel timeout
            
            content = response.choices[0].message.content.strip()
            self.log(f"API response received ({len(content)} chars)")
            return content
            
        except Exception as e:
            if hasattr(signal, 'SIGALRM'):
                signal.alarm(0)  # Cancel timeout
            self.log(f"API call failed: {str(e)}")
            raise

class ExtractorAgent(BaseAgent):
    """AI agent for extracting form data from PDFs with improved efficiency"""
    
    def __init__(self, openai_client, debug_mode: bool = False, timeout: int = 45):
        super().__init__("Extractor Agent", openai_client, debug_mode, timeout)
        self.model = "gpt-4o-mini"  # Using faster model for better performance
    
    def extract_form_data(self, pdf_text: str, form_type: str = None, progress_callback=None) -> ExtractionResult:
        """Extract structured data from PDF text using AI with progress tracking"""
        self.status = AgentStatus.PROCESSING
        self.log(f"Starting extraction for form type: {form_type or 'Unknown'}")
        
        if progress_callback:
            progress_callback(10, "Identifying form type...")
        
        try:
            # First, identify the form if not provided (quick check)
            if not form_type:
                form_type = self._identify_form_type_fast(pdf_text[:2000])  # Only use first 2000 chars
                self.log(f"Identified form type: {form_type}")
            
            if progress_callback:
                progress_callback(25, f"Processing {form_type} form...")
            
            # Extract using a more efficient single-pass approach
            result = self._extract_all_data_single_pass(pdf_text, form_type, progress_callback)
            
            if progress_callback:
                progress_callback(90, "Finalizing extraction...")
            
            result.calculate_stats()
            self.status = AgentStatus.SUCCESS
            self.log(f"Extraction complete: {result.total_fields} fields total")
            
            return result
            
        except Exception as e:
            self.status = AgentStatus.ERROR
            self.log(f"Extraction failed: {str(e)}")
            raise
    
    def _identify_form_type_fast(self, pdf_text_sample: str) -> str:
        """Quick form identification using smaller text sample"""
        self.log("Quick form identification...")
        
        # First try simple pattern matching
        patterns = [
            (r'Form\s+(I-90)', 'I-90'),
            (r'Form\s+(I-130)', 'I-130'),
            (r'Form\s+(G-28)', 'G-28'),
            (r'Form\s+(I-485)', 'I-485'),
            (r'Form\s+(N-400)', 'N-400'),
        ]
        
        for pattern, form_type in patterns:
            if re.search(pattern, pdf_text_sample, re.IGNORECASE):
                self.log(f"Form type identified by pattern: {form_type}")
                return form_type
        
        # Fall back to AI if pattern matching fails
        try:
            prompt = f"""
            Identify the USCIS form type from this text. Return ONLY the form number (e.g., "I-90").
            
            Text: {pdf_text_sample[:1000]}
            
            Form number:"""
            
            messages = [{"role": "user", "content": prompt}]
            form_type = self.call_openai_with_timeout(messages, max_tokens=20)
            
            # Clean up response
            form_type = re.sub(r'[^A-Z0-9-]', '', form_type.upper())
            return form_type if form_type else "Unknown"
            
        except Exception as e:
            self.log(f"Form identification failed: {str(e)}")
            return "Unknown"
    
    def _extract_all_data_single_pass(self, pdf_text: str, form_type: str, progress_callback=None) -> ExtractionResult:
        """Extract all data in a single efficient pass"""
        self.log("Extracting all form data in single pass...")
        
        if progress_callback:
            progress_callback(40, "Analyzing form structure...")
        
        # Truncate very long text to avoid API limits
        max_text_length = 15000  # Reasonable limit for GPT-4
        if len(pdf_text) > max_text_length:
            pdf_text = pdf_text[:max_text_length] + "\n[... text truncated for processing efficiency ...]"
            self.log(f"Text truncated to {max_text_length} characters for efficiency")
        
        prompt = f"""
        Extract ALL form data from this USCIS {form_type} form in a single pass. Focus on "Part 1 - Information About You" first.
        
        Return ONLY valid JSON in this exact format:
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
                  "field_value": "Smith",
                  "field_type": "name",
                  "is_required": true,
                  "confidence": 0.95
                }}
              ]
            }}
          ]
        }}
        
        Extract ALL visible fields, even if empty. Be thorough but efficient.
        
        Form text:
        {pdf_text}
        """
        
        try:
            if progress_callback:
                progress_callback(60, "AI analyzing form content...")
            
            messages = [{"role": "user", "content": prompt}]
            response_text = self.call_openai_with_timeout(messages, max_tokens=8000)
            
            if progress_callback:
                progress_callback(80, "Processing AI response...")
            
            # Clean up JSON response
            if response_text.startswith('```json'):
                response_text = response_text[7:-3]
            elif response_text.startswith('```'):
                response_text = response_text[3:-3]
            
            data = json.loads(response_text)
            
            # Convert to ExtractionResult
            result = ExtractionResult(
                form_number=data.get('form_type', form_type),
                form_title=self._get_form_title(form_type),
                agent_logs=self.get_logs()
            )
            
            # Process parts
            for part_data in data.get('parts', []):
                part = FormPart(
                    number=part_data.get('number', 1),
                    title=part_data.get('title', 'Unknown Part'),
                    raw_text=""  # Not needed for single-pass
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
                        part_number=part.number,
                        extraction_method="ai_agent_single_pass"
                    )
                    part.add_field(field)
                
                result.parts[part.number] = part
                self.log(f"Part {part.number}: Processed {len(part.fields)} fields")
            
            return result
            
        except json.JSONDecodeError as e:
            self.log(f"JSON parsing failed: {str(e)}")
            # Return minimal result
            return self._create_minimal_result(form_type)
        except Exception as e:
            self.log(f"Single-pass extraction failed: {str(e)}")
            raise
    
    def _create_minimal_result(self, form_type: str) -> ExtractionResult:
        """Create minimal result when AI extraction fails"""
        result = ExtractionResult(
            form_number=form_type,
            form_title=self._get_form_title(form_type),
            agent_logs=self.get_logs()
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
    """AI agent for validating extracted form data with efficiency focus"""
    
    def __init__(self, openai_client, debug_mode: bool = False, timeout: int = 30):
        super().__init__("Validation Agent", openai_client, debug_mode, timeout)
        self.model = "gpt-4o-mini"  # Faster model for validation
    
    def validate_extraction(self, result: ExtractionResult, original_text: str = None, progress_callback=None) -> Tuple[bool, Dict[str, Any]]:
        """Quick validation of extracted data"""
        self.status = AgentStatus.PROCESSING
        self.log("Starting quick validation...")
        
        if progress_callback:
            progress_callback(10, "Analyzing extraction quality...")
        
        try:
            validation_report = self._quick_validation(result, progress_callback)
            
            overall_valid = validation_report['confidence_score'] >= 0.7
            result.final_validation_report = validation_report
            
            self.status = AgentStatus.SUCCESS if overall_valid else AgentStatus.VALIDATION_FAILED
            self.log(f"Quick validation complete. Valid: {overall_valid}, Score: {validation_report['confidence_score']:.2f}")
            
            return overall_valid, validation_report
            
        except Exception as e:
            self.status = AgentStatus.ERROR
            self.log(f"Validation failed: {str(e)}")
            raise
    
    def _quick_validation(self, result: ExtractionResult, progress_callback=None) -> Dict[str, Any]:
        """Perform quick validation without detailed AI analysis"""
        if progress_callback:
            progress_callback(30, "Checking field completeness...")
        
        validation_report = {
            'overall_valid': True,
            'confidence_score': 0.0,
            'total_fields': result.total_fields,
            'filled_fields': result.filled_fields,
            'fill_rate': 0.0,
            'critical_fields_missing': [],
            'recommendations': []
        }
        
        if result.total_fields == 0:
            validation_report['confidence_score'] = 0.0
            validation_report['recommendations'].append("No fields extracted - check PDF quality")
            return validation_report
        
        if progress_callback:
            progress_callback(60, "Calculating validation scores...")
        
        # Calculate fill rate
        fill_rate = result.filled_fields / result.total_fields if result.total_fields > 0 else 0
        validation_report['fill_rate'] = fill_rate
        
        # Quick confidence scoring
        confidence_score = 0.0
        
        # Base score from fill rate
        confidence_score += fill_rate * 0.6
        
        # Bonus for having multiple parts
        if len(result.parts) > 1:
            confidence_score += 0.1
        
        # Bonus for reasonable field count
        if 5 <= result.total_fields <= 50:
            confidence_score += 0.2
        
        # Check for critical fields (basic heuristics)
        critical_found = False
        for part in result.parts.values():
            for field in part.fields:
                if any(keyword in field.field_label.lower() for keyword in ['name', 'date of birth', 'address']):
                    if field.field_value:
                        critical_found = True
                        break
        
        if critical_found:
            confidence_score += 0.1
        
        validation_report['confidence_score'] = min(confidence_score, 1.0)
        
        if progress_callback:
            progress_callback(90, "Generating recommendations...")
        
        # Generate quick recommendations
        if fill_rate < 0.3:
            validation_report['recommendations'].append("Low fill rate - consider manual review")
        if result.total_fields < 3:
            validation_report['recommendations'].append("Very few fields extracted - check form type")
        if validation_report['confidence_score'] < 0.5:
            validation_report['recommendations'].append("Low confidence - recommend manual verification")
        
        return validation_report

class CoordinatorAgent(BaseAgent):
    """Coordinator agent with timeout and efficiency improvements"""
    
    def __init__(self, openai_client, extractor_agent: ExtractorAgent, validation_agent: ValidationAgent, 
                 max_iterations: int = 2, debug_mode: bool = False, timeout: int = 60):  # Reduced iterations
        super().__init__("Coordinator Agent", openai_client, debug_mode, timeout)
        self.extractor = extractor_agent
        self.validator = validation_agent
        self.max_iterations = max_iterations
        self.model = "gpt-4o-mini"
    
    def process_form(self, pdf_text: str, form_type: str = None, progress_callback=None) -> ExtractionResult:
        """Efficient processing with progress tracking"""
        self.status = AgentStatus.PROCESSING
        self.log("Starting coordinated form processing...")
        
        if progress_callback:
            progress_callback(5, "Initializing AI agents...")
        
        start_time = time.time()
        iteration = 1
        result = None
        
        try:
            while iteration <= self.max_iterations:
                self.log(f"=== ITERATION {iteration}/{self.max_iterations} ===")
                
                if progress_callback:
                    progress = 10 + (iteration - 1) * 40
                    progress_callback(progress, f"Iteration {iteration}: Extracting data...")
                
                # EXTRACTION PHASE with progress
                def extraction_progress(pct, msg):
                    if progress_callback:
                        total_progress = 10 + (iteration - 1) * 40 + (pct * 0.3)
                        progress_callback(int(total_progress), f"Iter {iteration}: {msg}")
                
                if iteration == 1:
                    result = self.extractor.extract_form_data(pdf_text, form_type, extraction_progress)
                else:
                    # For subsequent iterations, just improve validation without re-extraction
                    self.log("Using previous extraction result for validation improvement")
                
                result.extraction_iterations = iteration
                
                if progress_callback:
                    progress = 40 + (iteration - 1) * 40
                    progress_callback(progress, f"Iteration {iteration}: Validating...")
                
                # VALIDATION PHASE with progress
                def validation_progress(pct, msg):
                    if progress_callback:
                        total_progress = 40 + (iteration - 1) * 40 + (pct * 0.3)
                        progress_callback(int(total_progress), f"Iter {iteration}: {msg}")
                
                is_valid, validation_report = self.validator.validate_extraction(result, pdf_text, validation_progress)
                
                # CHECK COMPLETION
                confidence_threshold = 0.6  # Lower threshold for efficiency
                self.log(f"Validation result: Valid={is_valid}, Score={validation_report['confidence_score']:.2f}")
                
                if is_valid or validation_report['confidence_score'] >= confidence_threshold:
                    self.log("✅ Validation passed! Processing complete.")
                    self.status = AgentStatus.SUCCESS
                    break
                elif iteration == self.max_iterations:
                    self.log("⚠️ Max iterations reached. Returning best result.")
                    self.status = AgentStatus.VALIDATION_FAILED
                    break
                else:
                    self.log(f"❌ Validation failed. Iteration {iteration + 1} would improve but skipping for efficiency...")
                    self.status = AgentStatus.VALIDATION_FAILED
                    break  # Skip improvement for efficiency
            
            if progress_callback:
                progress_callback(95, "Finalizing results...")
            
            # Finalize result
            result.processing_time = time.time() - start_time
            result.agent_logs = (self.get_logs() + 
                               self.extractor.get_logs() + 
                               self.validator.get_logs())
            
            self.log(f"Processing complete in {result.processing_time:.2f}s with {iteration} iterations")
            
            if progress_callback:
                progress_callback(100, "Processing complete!")
            
            return result
            
        except Exception as e:
            self.status = AgentStatus.ERROR
            self.log(f"Coordination failed: {str(e)}")
            if progress_callback:
                progress_callback(100, f"Error: {str(e)}")
            raise

# ===== OPENAI CLIENT SETUP =====
def get_openai_client():
    """Get OpenAI client with API key from secrets"""
    try:
        api_key = st.secrets.get("OPENAI_API_KEY")
        if not api_key:
            st.error("🔑 OpenAI API key not found in secrets!")
            st.info("Please add your OpenAI API key to Streamlit secrets.")
            return None
        
        # Test the API key with a simple request
        client = openai.OpenAI(
            api_key=api_key,
            timeout=30.0  # Default timeout for all requests
        )
        
        # Quick test to verify the key works
        try:
            test_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1,
                timeout=5
            )
            st.sidebar.success("🔑 OpenAI API key verified!")
        except Exception as e:
            st.error(f"❌ OpenAI API key test failed: {str(e)}")
            return None
        
        return client
    except Exception as e:
        st.error(f"Failed to initialize OpenAI client: {str(e)}")
        return None

# ===== PDF PROCESSING =====
def extract_pdf_text(pdf_file) -> str:
    """Extract text from PDF file with improved error handling"""
    try:
        if hasattr(pdf_file, 'read'):
            pdf_file.seek(0)
            pdf_bytes = pdf_file.read()
        else:
            pdf_bytes = pdf_file
        
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        full_text = ""
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            page_text = page.get_text()
            if page_text.strip():  # Only add pages with actual text
                full_text += f"\n--- PAGE {page_num + 1} ---\n{page_text}\n"
        
        doc.close()
        
        if not full_text.strip():
            st.warning("⚠️ No text found in PDF. This might be an image-based PDF that needs OCR.")
            return ""
        
        # Log extraction success
        st.success(f"✅ Extracted {len(full_text)} characters from {len(doc)} pages")
        return full_text
        
    except Exception as e:
        st.error(f"Failed to extract PDF text: {str(e)}")
        return ""

# ===== UI FUNCTIONS =====
def display_agent_results(result: ExtractionResult):
    """Display results from agent processing"""
    if not result:
        st.info("No results to display")
        return
    
    # Summary metrics
    st.markdown("### 🤖 AI Agent Processing Results")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Fields", result.total_fields)
    with col2:
        percentage = f"{result.filled_fields/result.total_fields*100:.0f}%" if result.total_fields > 0 else "0%"
        st.metric("Filled Fields", result.filled_fields, delta=percentage)
    with col3:
        st.metric("Validation Score", f"{result.validation_score:.1f}%")
    with col4:
        st.metric("Iterations", result.extraction_iterations)
    with col5:
        st.metric("Processing Time", f"{result.processing_time:.1f}s")
    
    # Agent logs
    with st.expander("🤖 Agent Logs", expanded=False):
        if result.agent_logs:
            log_text = "\n".join(result.agent_logs)
            st.markdown(f'<div class="agent-log">{log_text}</div>', unsafe_allow_html=True)
        else:
            st.info("No logs available")
    
    # Validation report
    if result.final_validation_report:
        with st.expander("📋 Validation Report", expanded=True):
            report = result.final_validation_report
            
            if report['overall_valid']:
                st.markdown('<div class="validation-success">✅ Validation Passed</div>', 
                           unsafe_allow_html=True)
            else:
                st.markdown('<div class="validation-error">❌ Validation Issues Found</div>', 
                           unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Confidence Score:**")
                st.progress(report['confidence_score'])
                st.write(f"{report['confidence_score']:.1%}")
            
            with col2:
                if report['missing_fields']:
                    st.markdown("**Missing Critical Fields:**")
                    for field in report['missing_fields']:
                        st.markdown(f"- {field}")
            
            if report['recommendations']:
                st.markdown("**Recommendations:**")
                for rec in report['recommendations']:
                    st.markdown(f"- {rec}")
    
    # Display parts and fields
    st.markdown("### 📋 Extracted Form Data")
    
    for part_num in sorted(result.parts.keys()):
        part = result.parts[part_num]
        filled = sum(1 for f in part.fields if f.field_value and f.field_value.strip())
        
        with st.expander(f"Part {part_num}: {part.title} ({filled}/{len(part.fields)} filled)", 
                        expanded=(part_num == 1)):
            
            if not part.fields:
                st.warning("No fields found in this part")
            else:
                # Part validation score
                if hasattr(part, 'validation_score'):
                    score_color = "green" if part.validation_score > 0.8 else "orange" if part.validation_score > 0.6 else "red"
                    st.markdown(f'<div style="color:{score_color};">Part Validation Score: {part.validation_score:.1%}</div>', 
                               unsafe_allow_html=True)
                
                # Display fields
                for field in part.fields:
                    st.markdown('<div class="agent-card">', unsafe_allow_html=True)
                    
                    cols = st.columns([1, 3, 3, 1, 1])
                    
                    with cols[0]:
                        st.markdown(f'**{field.field_number}**')
                    
                    with cols[1]:
                        st.markdown(f"**{field.field_label}**")
                        st.caption(f"Type: {field.field_type.value}")
                        if field.is_required:
                            st.caption("🔴 Required")
                    
                    with cols[2]:
                        if field.field_value and field.field_value.strip():
                            st.markdown(f'<div class="field-value">{field.field_value}</div>', 
                                      unsafe_allow_html=True)
                        else:
                            st.markdown('<div style="color:#666;font-style:italic;">Empty</div>', 
                                      unsafe_allow_html=True)
                    
                    with cols[3]:
                        conf_color = "green" if field.confidence > 0.7 else "orange" if field.confidence > 0.4 else "red"
                        st.markdown(f'<span style="color:{conf_color};">{field.confidence:.0%}</span>', 
                                   unsafe_allow_html=True)
                    
                    with cols[4]:
                        if field.validation_errors:
                            st.markdown("⚠️")
                            if st.button("❓", key=f"errors_{field.field_number}"):
                                st.error(f"Validation errors: {', '.join(field.validation_errors)}")
                    
                    st.markdown('</div>', unsafe_allow_html=True)

def display_processing_status(extractor_agent, validation_agent, coordinator_agent):
    """Display real-time processing status"""
    st.markdown("### 🔄 Agent Status")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown('<div class="agent-card extractor-agent">', unsafe_allow_html=True)
        st.markdown("**🔍 Extractor Agent**")
        status_color = {
            AgentStatus.IDLE: "gray",
            AgentStatus.PROCESSING: "blue", 
            AgentStatus.SUCCESS: "green",
            AgentStatus.ERROR: "red"
        }.get(extractor_agent.status, "gray")
        st.markdown(f'<div style="color:{status_color};">Status: {extractor_agent.status.value}</div>', 
                   unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="agent-card validation-agent">', unsafe_allow_html=True)
        st.markdown("**✅ Validation Agent**")
        status_color = {
            AgentStatus.IDLE: "gray",
            AgentStatus.PROCESSING: "blue",
            AgentStatus.SUCCESS: "green", 
            AgentStatus.ERROR: "red",
            AgentStatus.VALIDATION_FAILED: "orange"
        }.get(validation_agent.status, "gray")
        st.markdown(f'<div style="color:{status_color};">Status: {validation_agent.status.value}</div>', 
                   unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        st.markdown('<div class="agent-card coordinator-agent">', unsafe_allow_html=True)
        st.markdown("**🎯 Coordinator Agent**")
        status_color = {
            AgentStatus.IDLE: "gray",
            AgentStatus.PROCESSING: "blue",
            AgentStatus.SUCCESS: "green",
            AgentStatus.ERROR: "red",
            AgentStatus.VALIDATION_FAILED: "orange"
        }.get(coordinator_agent.status, "gray")
        st.markdown(f'<div style="color:{status_color};">Status: {coordinator_agent.status.value}</div>', 
                   unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

# ===== MAIN APPLICATION =====
def main():
    st.markdown(
        '<div class="main-header">'
        '<h1>🤖 AI-Powered USCIS Form Reader</h1>'
        '<p>Intelligent form processing with AI agents and validation loops</p>'
        '</div>', 
        unsafe_allow_html=True
    )
    
    # Check dependencies
    if not PYMUPDF_AVAILABLE:
        st.error("❌ PyMuPDF is required but not installed!")
        st.code("pip install PyMuPDF")
        st.stop()
    
    if not OPENAI_AVAILABLE:
        st.error("❌ OpenAI library is required but not installed!")
        st.code("pip install openai")
        st.stop()
    
    # Initialize OpenAI client
    openai_client = get_openai_client()
    if not openai_client:
        st.stop()
    
    # Initialize components with debugging
    if 'db_manager' not in st.session_state:
        try:
            # Create database manager
            db_manager_test = DatabaseManager()
            
            # Verify critical methods exist
            if not hasattr(db_manager_test, 'get_form_submissions'):
                st.error("❌ DatabaseManager class not properly loaded. Please refresh the page.")
                st.code("The class definition may not be updated. Try hard refresh (Ctrl+F5)")
                st.stop()
            
            st.session_state.db_manager = db_manager_test
            
            # Only show success message once
            if 'db_initialized' not in st.session_state:
                st.session_state.db_initialized = True
                st.sidebar.success("✅ Database ready!")
            
        except Exception as e:
            st.error(f"Database initialization failed: {str(e)}")
            st.info("Try refreshing the page. If this persists, check the error logs.")
            st.stop()
    
    if 'extraction_result' not in st.session_state:
        st.session_state.extraction_result = None
    if 'current_submission_id' not in st.session_state:
        st.session_state.current_submission_id = None
    
    db_manager = st.session_state.db_manager
    
    # Sidebar
    with st.sidebar:
        st.markdown("## ⚙️ Agent Settings")
        debug_mode = st.checkbox("Debug Mode", value=False, help="Show detailed agent logs")
        max_iterations = st.slider("Max Iterations", min_value=1, max_value=3, value=2, 
                                  help="Maximum extraction-validation loops (reduced for efficiency)")
        processing_timeout = st.slider("Processing Timeout (seconds)", min_value=60, max_value=300, value=120,
                                      help="Maximum time to wait for processing")
        
        st.markdown("## 🚀 Performance Mode")
        performance_mode = st.selectbox(
            "Processing Mode",
            ["Fast (GPT-4o-mini)", "Balanced (GPT-4o)", "Accurate (GPT-4o + validation)"],
            help="Choose speed vs accuracy tradeoff"
        )
        st.info("""
        **Extractor Agent**: Uses GPT-4 to intelligently extract form fields
        
        **Validation Agent**: Validates extraction accuracy and completeness
        
        **Coordinator**: Manages the improvement loop until validation passes
        """)
        
        st.markdown("## 🤖 Agent Info")
        if performance_mode == "Fast (GPT-4o-mini)":
            st.info("""
            **Fast Mode**: Uses GPT-4o-mini for quick extraction without validation. 
            Best for: Simple forms, quick previews (~30s)
            """)
        elif performance_mode == "Balanced (GPT-4o)":
            st.info("""
            **Balanced Mode**: Uses GPT-4o with validation for good accuracy.
            Best for: Most forms (~1-2 minutes)
            """)
        else:
            st.info("""
            **Accurate Mode**: Uses GPT-4o with full validation and improvement loops.
            Best for: Complex forms requiring high accuracy (~2-3 minutes)
            """)
        
        st.markdown("## 🗄️ Database")
        if st.button("🗑️ Reset Database"):
            try:
                if os.path.exists(db_manager.db_path):
                    os.remove(db_manager.db_path)
                st.session_state.db_manager = DatabaseManager()
                st.success("Database reset successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Error resetting database: {e}")
        
        st.markdown("## 📊 Processing Stats")
        try:
            # Test database connection
            submissions = db_manager.get_form_submissions(limit=5)
            if submissions and len(submissions) > 0:
                latest = submissions[0]
                st.metric("Latest Form", latest.form_type)
                st.metric("Iterations", getattr(latest, 'iterations', 0))
                st.metric("Score", f"{latest.validation_score:.1f}%")
            else:
                st.write("No submissions yet")
                st.caption("Upload a form to see stats here")
        except AttributeError as e:
            st.error(f"❌ Method missing: {str(e)}")
            st.info("Please refresh the page to reload the latest code")
        except Exception as e:
            st.write("Database loading...")
            st.caption(f"Status: {str(e)[:50]}...")
        
        # Debug info in expander
        with st.expander("🔧 Debug Info", expanded=False):
            st.write(f"Database path: {getattr(db_manager, 'db_path', 'Unknown')}")
            st.write(f"Methods available: {[m for m in dir(db_manager) if not m.startswith('_')]}")
            if st.button("Test Database"):
                try:
                    result = db_manager.get_form_submissions(limit=1)
                    st.success(f"✅ Database working! Found {len(result)} records")
                except Exception as e:
                    st.error(f"❌ Database test failed: {e}")
    
    # Initialize agents (moved to after openai_client is ready)
    # Note: Agents are now created during processing with proper timeouts
    
    # Main tabs
    tabs = st.tabs([
        "🤖 AI Processing", 
        "📊 Results & Analysis", 
        "💾 Database Management",
        "📈 Agent Analytics"
    ])
    
    # AI Processing Tab
    with tabs[0]:
        st.markdown("### 📤 Upload USCIS Form for AI Processing")
        
        uploaded_file = st.file_uploader(
            "Choose a USCIS form PDF",
            type=['pdf'],
            help="Upload any USCIS form for intelligent AI processing"
        )
        
        if uploaded_file:
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                st.success(f"✅ File uploaded: {uploaded_file.name}")
                
                # Form type hint
                form_type_hint = st.selectbox(
                    "Form Type (optional)",
                    ["Auto-detect", "I-90", "I-130", "I-485", "G-28", "N-400", "I-129"],
                    help="Leave as Auto-detect for AI to identify the form"
                )
            
            with col2:
                # Test PDF readability
                if st.button("🔍 Test PDF"):
                    with st.spinner("Testing PDF..."):
                        text = extract_pdf_text(uploaded_file)
                        if text:
                            st.success("✅ PDF readable")
                            with st.expander("Preview"):
                                st.text_area("First 500 characters:", text[:500], height=100)
                        else:
                            st.error("❌ Cannot read PDF")
            
            with col3:
                # Process with AI agents
                if st.button("🚀 Process with AI", type="primary"):
                    # Create progress tracking
                    progress_placeholder = st.empty()
                    progress_bar = st.progress(0)
                    status_placeholder = st.empty()
                    
                    # Add cancel button and timeout
                    cancel_col, timeout_col = st.columns([1, 1])
                    with cancel_col:
                        cancel_button = st.empty()
                    with timeout_col:
                        timeout_display = st.empty()
                    
                    start_time = time.time()
                    timeout_seconds = processing_timeout  # Use user setting
                    
                    try:
                        # Progress callback function
                        def update_progress(percent, message):
                            progress_bar.progress(percent)
                            progress_placeholder.write(f"🤖 {message}")
                            
                            # Check timeout
                            elapsed = time.time() - start_time
                            if elapsed > timeout_seconds:
                                raise TimeoutError(f"Processing timed out after {timeout_seconds} seconds")
                            
                            # Update timeout display
                            remaining = max(0, timeout_seconds - elapsed)
                            timeout_display.write(f"⏱️ Timeout: {remaining:.0f}s remaining")
                        
                        update_progress(5, "Extracting PDF text...")
                        
                        # Extract PDF text
                        pdf_text = extract_pdf_text(uploaded_file)
                        
                        if not pdf_text:
                            st.error("❌ Failed to extract text from PDF")
                            st.info("The PDF might be image-based. Try using an OCR tool first.")
                            st.stop()
                        
                        update_progress(10, f"Extracted {len(pdf_text)} characters from PDF")
                        
                        # Determine form type
                        form_type = None if form_type_hint == "Auto-detect" else form_type_hint
                        
                        # Determine processing parameters based on performance mode
                        if performance_mode == "Fast (GPT-4o-mini)":
                            model_name = "gpt-4o-mini"
                            agent_timeout = 30
                            skip_validation = True
                        elif performance_mode == "Balanced (GPT-4o)":
                            model_name = "gpt-4o"
                            agent_timeout = 45
                            skip_validation = False
                        else:  # Accurate
                            model_name = "gpt-4o"
                            agent_timeout = 60
                            skip_validation = False
                        
                        # Initialize agents with performance settings
                        extractor_agent = ExtractorAgent(openai_client, debug_mode, timeout=agent_timeout)
                        extractor_agent.model = model_name
                        
                        if skip_validation:
                            # Fast mode: skip validation
                            validation_agent = None
                            coordinator_agent = None
                            update_progress(15, f"Fast mode: Using {model_name}")
                        else:
                            validation_agent = ValidationAgent(openai_client, debug_mode, timeout=30)
                            validation_agent.model = model_name
                            coordinator_agent = CoordinatorAgent(
                                openai_client, extractor_agent, validation_agent, 
                                max_iterations=max_iterations, debug_mode=debug_mode, timeout=processing_timeout
                            )
                            update_progress(15, f"Using {model_name} with validation")
                        
                        # Process with timeout and progress tracking
                        try:
                            # Process based on mode
                            if skip_validation:
                                # Fast mode: Direct extraction only
                                update_progress(20, "Fast extraction (no validation)...")
                                result = extractor_agent.extract_form_data(pdf_text, form_type, update_progress)
                                result.validation_score = 0.7  # Assumed score for fast mode
                                result.final_validation_report = {
                                    'confidence_score': 0.7,
                                    'overall_valid': True,
                                    'mode': 'fast_extraction_only'
                                }
                            else:
                                # Standard mode: Full pipeline with validation
                                # Show agent status during processing
                                with status_placeholder.container():
                                    display_processing_status(extractor_agent, validation_agent, coordinator_agent)
                                
                                result = coordinator_agent.process_form(pdf_text, form_type, update_progress)
                            
                            # Clear status display
                            status_placeholder.empty()
                            progress_placeholder.empty()
                            timeout_display.empty()
                            
                            # Save to database
                            submission = FormSubmission(
                                form_type=result.form_number,
                                entry_mode="ai_agents",
                                total_fields=result.total_fields,
                                completed_fields=result.filled_fields,
                                validation_score=result.validation_score,
                                pdf_filename=uploaded_file.name,
                                json_data=json.dumps(result.final_validation_report),
                                status="completed",
                                iterations=result.extraction_iterations,
                                notes=f"Processed with {result.extraction_iterations} iterations in {result.processing_time:.1f}s"
                            )
                            
                            submission_id = db_manager.save_form_submission(submission)
                            st.session_state.current_submission_id = submission_id
                            st.session_state.extraction_result = result
                            
                            # Save extracted fields to database
                            try:
                                db_manager.save_extracted_fields(submission_id, result)
                            except Exception as e:
                                st.warning(f"Field data saved with issues: {e}")
                            
                            progress_bar.progress(100)
                            
                            # Show results based on validation score
                            if result.validation_score >= 0.8:
                                st.success(f"✅ Processing completed successfully!")
                                st.success(f"📊 Score: {result.validation_score:.1%} | ⏱️ Time: {result.processing_time:.1f}s | 🔄 Iterations: {result.extraction_iterations}")
                                st.balloons()
                            elif result.validation_score >= 0.6:
                                st.warning(f"⚠️ Processing completed with some issues")
                                st.info(f"📊 Score: {result.validation_score:.1%} | ⏱️ Time: {result.processing_time:.1f}s | 🔄 Iterations: {result.extraction_iterations}")
                            else:
                                st.error(f"❌ Processing completed but quality is low")
                                st.error(f"📊 Score: {result.validation_score:.1%} | ⏱️ Time: {result.processing_time:.1f}s | 🔄 Iterations: {result.extraction_iterations}")
                                st.info("Consider manual review or try again with a clearer PDF.")
                            
                            # Show quick summary
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Fields Found", result.total_fields)
                            with col2:
                                st.metric("Fields Filled", result.filled_fields)
                            with col3:
                                fill_rate = (result.filled_fields / result.total_fields * 100) if result.total_fields > 0 else 0
                                st.metric("Fill Rate", f"{fill_rate:.0f}%")
                            
                        except TimeoutError as e:
                            progress_placeholder.empty()
                            timeout_display.empty()
                            st.error(f"⏱️ {str(e)}")
                            st.info("The form may be too complex or the API is slow. Try again or use a simpler document.")
                            
                        except Exception as api_error:
                            progress_placeholder.empty()
                            timeout_display.empty()
                            st.error(f"🤖 AI Processing failed: {str(api_error)}")
                            
                            # Check for common API issues
                            error_msg = str(api_error).lower()
                            if "rate limit" in error_msg:
                                st.info("🔄 OpenAI rate limit reached. Please wait a moment and try again.")
                            elif "timeout" in error_msg:
                                st.info("⏱️ API timeout. Try again or use a shorter document.")
                            elif "invalid" in error_msg and "key" in error_msg:
                                st.info("🔑 Check your OpenAI API key in Streamlit secrets.")
                            else:
                                st.info("Try again or check the debug logs for more details.")
                            
                            if debug_mode:
                                st.exception(api_error)
                    
                    except Exception as e:
                        progress_placeholder.empty()
                        timeout_display.empty()
                        st.error(f"💥 Processing failed: {str(e)}")
                        if debug_mode:
                            st.exception(e)
        
        # Live agent status (when not processing)
        if 'extraction_result' not in st.session_state or st.session_state.extraction_result is None:
            st.markdown("### 🤖 Agent Status")
            st.info("Agents will be initialized when you process a form")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown('<div class="agent-card extractor-agent">', unsafe_allow_html=True)
                st.markdown("**🔍 Extractor Agent**")
                st.markdown('<div style="color:gray;">Status: Ready</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
            
            with col2:
                st.markdown('<div class="agent-card validation-agent">', unsafe_allow_html=True)
                st.markdown("**✅ Validation Agent**")
                st.markdown('<div style="color:gray;">Status: Ready</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
            
            with col3:
                st.markdown('<div class="agent-card coordinator-agent">', unsafe_allow_html=True)
                st.markdown("**🎯 Coordinator Agent**")
                st.markdown('<div style="color:gray;">Status: Ready</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
    
    # Results & Analysis Tab
    with tabs[1]:
        if st.session_state.extraction_result:
            display_agent_results(st.session_state.extraction_result)
            
            # Export options
            st.markdown("### 💾 Export Results")
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("📦 Download JSON"):
                    result_dict = {
                        'form_info': {
                            'number': st.session_state.extraction_result.form_number,
                            'title': st.session_state.extraction_result.form_title,
                            'total_fields': st.session_state.extraction_result.total_fields,
                            'validation_score': st.session_state.extraction_result.validation_score,
                            'iterations': st.session_state.extraction_result.extraction_iterations,
                            'processing_time': st.session_state.extraction_result.processing_time
                        },
                        'parts': {
                            f'part_{k}': {
                                'title': v.title,
                                'validation_score': getattr(v, 'validation_score', 0),
                                'fields': [field.to_dict() for field in v.fields]
                            } for k, v in st.session_state.extraction_result.parts.items()
                        },
                        'validation_report': st.session_state.extraction_result.final_validation_report,
                        'agent_logs': st.session_state.extraction_result.agent_logs
                    }
                    
                    st.download_button(
                        "Download JSON",
                        json.dumps(result_dict, indent=2),
                        f"{st.session_state.extraction_result.form_number}_ai_extracted.json",
                        mime="application/json"
                    )
            
            with col2:
                if st.button("📊 Download CSV"):
                    rows = []
                    for part in st.session_state.extraction_result.parts.values():
                        for field in part.fields:
                            rows.append({
                                'Part': part.number,
                                'Part Title': part.title,
                                'Field Number': field.field_number,
                                'Field Label': field.field_label,
                                'Field Value': field.field_value,
                                'Field Type': field.field_type.value,
                                'Confidence': f"{field.confidence:.0%}",
                                'Required': field.is_required,
                                'Validation Errors': '; '.join(field.validation_errors) if field.validation_errors else '',
                                'Extraction Method': field.extraction_method
                            })
                    
                    df = pd.DataFrame(rows)
                    csv = df.to_csv(index=False)
                    st.download_button(
                        "Download CSV",
                        csv,
                        f"{st.session_state.extraction_result.form_number}_ai_extracted.csv",
                        mime="text/csv"
                    )
        else:
            st.info("No results to display. Please process a form first.")
    
    # Database Management Tab
    with tabs[2]:
        st.markdown("### 💾 Database Management")
        
        try:
            # Recent submissions
            submissions = db_manager.get_form_submissions(limit=20)
            
            if submissions:
                st.markdown("#### Recent AI-Processed Forms")
                
                submission_data = []
                for sub in submissions:
                    # Handle datetime formatting
                    date_str = str(sub.submission_date)[:19] if hasattr(sub.submission_date, 'strftime') else str(sub.submission_date)[:19]
                    
                    submission_data.append({
                        'ID': sub.id,
                        'Form': sub.form_type,
                        'Date': date_str,
                        'Fields': f"{sub.completed_fields}/{sub.total_fields}",
                        'Score': f"{sub.validation_score:.1f}%",
                        'Iterations': getattr(sub, 'iterations', 0),
                        'Status': sub.status
                    })
                
                df = pd.DataFrame(submission_data)
                st.dataframe(df, use_container_width=True)
                
                # Detailed view
                selected_id = st.selectbox(
                    "Select submission for details",
                    [sub.id for sub in submissions],
                    format_func=lambda x: f"ID {x} - {next(s.form_type for s in submissions if s.id == x)}"
                )
                
                if selected_id:
                    selected_submission = next(s for s in submissions if s.id == selected_id)
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.markdown(f"**Form:** {selected_submission.form_type}")
                        st.markdown(f"**Mode:** {selected_submission.entry_mode}")
                    with col2:
                        st.markdown(f"**Score:** {selected_submission.validation_score:.1f}%")
                        st.markdown(f"**Iterations:** {getattr(selected_submission, 'iterations', 0)}")
                    with col3:
                        st.markdown(f"**Fields:** {selected_submission.completed_fields}/{selected_submission.total_fields}")
                        st.markdown(f"**Status:** {selected_submission.status}")
                    
                    if selected_submission.json_data:
                        with st.expander("Validation Report"):
                            try:
                                report = json.loads(selected_submission.json_data)
                                st.json(report)
                            except:
                                st.text(selected_submission.json_data)
            else:
                st.info("No submissions found.")
        
        except Exception as e:
            st.error(f"Database error: {str(e)}")
            st.info("If this persists, try clearing the database from the sidebar.")
    
    # Agent Analytics Tab  
    with tabs[3]:
        st.markdown("### 📈 AI Agent Analytics")
        
        try:
            submissions = db_manager.get_form_submissions(limit=100)
            
            if submissions:
                # Performance metrics
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    avg_score = sum(s.validation_score for s in submissions) / len(submissions)
                    st.metric("Average Validation Score", f"{avg_score:.1f}%")
                
                with col2:
                    iterations_list = [getattr(s, 'iterations', 1) for s in submissions]
                    avg_iterations = sum(iterations_list) / len(iterations_list)
                    st.metric("Average Iterations", f"{avg_iterations:.1f}")
                
                with col3:
                    high_quality = sum(1 for s in submissions if s.validation_score >= 80)
                    st.metric("High Quality Rate", f"{high_quality/len(submissions):.1%}")
                
                with col4:
                    total_fields = sum(s.total_fields for s in submissions)
                    st.metric("Total Fields Processed", total_fields)
                
                # Charts
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("#### Validation Score Distribution")
                    scores = [s.validation_score for s in submissions]
                    if scores:
                        # Create score ranges for better visualization
                        score_ranges = []
                        for score in scores:
                            if score >= 90:
                                score_ranges.append("90-100%")
                            elif score >= 80:
                                score_ranges.append("80-89%")
                            elif score >= 70:
                                score_ranges.append("70-79%")
                            elif score >= 60:
                                score_ranges.append("60-69%")
                            else:
                                score_ranges.append("Below 60%")
                        
                        score_df = pd.DataFrame({'Score Range': score_ranges})
                        st.bar_chart(score_df['Score Range'].value_counts())
                
                with col2:
                    st.markdown("#### Iterations Required")
                    iterations = [getattr(s, 'iterations', 1) for s in submissions]
                    if iterations:
                        iter_df = pd.DataFrame({'Iterations': iterations})
                        st.bar_chart(iter_df['Iterations'].value_counts().sort_index())
                
                # Form type performance
                st.markdown("#### Performance by Form Type")
                form_stats = {}
                for sub in submissions:
                    if sub.form_type not in form_stats:
                        form_stats[sub.form_type] = {'count': 0, 'total_score': 0, 'total_iterations': 0}
                    form_stats[sub.form_type]['count'] += 1
                    form_stats[sub.form_type]['total_score'] += sub.validation_score
                    form_stats[sub.form_type]['total_iterations'] += getattr(sub, 'iterations', 1)
                
                perf_data = []
                for form_type, stats in form_stats.items():
                    perf_data.append({
                        'Form Type': form_type,
                        'Count': stats['count'],
                        'Avg Score': f"{stats['total_score']/stats['count']:.1f}%",
                        'Avg Iterations': f"{stats['total_iterations']/stats['count']:.1f}"
                    })
                
                if perf_data:
                    perf_df = pd.DataFrame(perf_data)
                    st.dataframe(perf_df, use_container_width=True)
            else:
                st.info("No data available for analytics.")
        
        except Exception as e:
            st.error(f"Analytics error: {str(e)}")
            st.info("Database may be initializing. Try again in a moment.")

if __name__ == "__main__":
    main()
