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

# ===== DATABASE MODELS (keeping existing) =====
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
    """Database manager (keeping existing implementation)"""
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
    
    def save_agent_log(self, submission_id: int, agent_type: str, iteration: int, message: str):
        """Save agent log entry"""
        with self.get_connection() as conn:
            conn.execute('''
                INSERT INTO agent_logs (submission_id, agent_type, iteration, log_message)
                VALUES (?, ?, ?, ?)
            ''', (submission_id, agent_type, iteration, message))
            conn.commit()

# ===== AI AGENTS =====
class BaseAgent:
    """Base class for AI agents"""
    
    def __init__(self, name: str, openai_client, debug_mode: bool = False):
        self.name = name
        self.client = openai_client
        self.debug_mode = debug_mode
        self.status = AgentStatus.IDLE
        self.logs = []
    
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

class ExtractorAgent(BaseAgent):
    """AI agent for extracting form data from PDFs"""
    
    def __init__(self, openai_client, debug_mode: bool = False):
        super().__init__("Extractor Agent", openai_client, debug_mode)
        self.model = "gpt-4o"  # Using latest model for best results
    
    def extract_form_data(self, pdf_text: str, form_type: str = None) -> ExtractionResult:
        """Extract structured data from PDF text using AI"""
        self.status = AgentStatus.PROCESSING
        self.log(f"Starting extraction for form type: {form_type or 'Unknown'}")
        
        try:
            # First, identify the form if not provided
            if not form_type:
                form_type = self._identify_form_type(pdf_text)
                self.log(f"Identified form type: {form_type}")
            
            # Extract parts and their content
            parts_data = self._extract_parts(pdf_text, form_type)
            self.log(f"Found {len(parts_data)} parts")
            
            # Create result
            result = ExtractionResult(
                form_number=form_type,
                form_title=self._get_form_title(form_type),
                agent_logs=self.get_logs()
            )
            
            # Process each part
            for part_data in parts_data:
                part = FormPart(
                    number=part_data['number'],
                    title=part_data['title'],
                    raw_text=part_data['text']
                )
                
                # Extract fields from this part
                fields = self._extract_fields_from_part(part_data['text'], part_data['number'], form_type)
                for field in fields:
                    part.add_field(field)
                
                result.parts[part.number] = part
                self.log(f"Part {part.number}: Extracted {len(fields)} fields")
            
            result.calculate_stats()
            self.status = AgentStatus.SUCCESS
            self.log(f"Extraction complete: {result.total_fields} fields total")
            
            return result
            
        except Exception as e:
            self.status = AgentStatus.ERROR
            self.log(f"Extraction failed: {str(e)}")
            raise
    
    def _identify_form_type(self, pdf_text: str) -> str:
        """Use AI to identify the form type"""
        self.log("Identifying form type...")
        
        prompt = f"""
        Analyze this USCIS form text and identify the form type (e.g., I-90, I-130, G-28, etc.).
        Look for form numbers, titles, and content clues.
        
        Text: {pdf_text[:2000]}...
        
        Return only the form number (e.g., "I-90", "G-28").
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )
            
            form_type = response.choices[0].message.content.strip()
            return form_type
            
        except Exception as e:
            self.log(f"Form identification failed: {str(e)}")
            return "Unknown"
    
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
    
    def _extract_parts(self, pdf_text: str, form_type: str) -> List[Dict]:
        """Extract form parts using AI"""
        self.log("Extracting form parts...")
        
        prompt = f"""
        Analyze this USCIS {form_type} form and identify all the parts/sections.
        Focus especially on "Part 1 - Information About You" and subsequent parts.
        
        For each part found, provide:
        1. Part number
        2. Part title 
        3. The text content for that part
        
        Text: {pdf_text}
        
        Return as JSON array:
        [
          {{
            "number": 1,
            "title": "Information About You",
            "text": "relevant text content for this part..."
          }},
          ...
        ]
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )
            
            content = response.choices[0].message.content.strip()
            
            # Extract JSON from response
            if content.startswith('```json'):
                content = content[7:-3]
            elif content.startswith('```'):
                content = content[3:-3]
            
            parts_data = json.loads(content)
            return parts_data
            
        except Exception as e:
            self.log(f"Parts extraction failed: {str(e)}")
            # Fallback: create a single part
            return [{
                "number": 1,
                "title": "Complete Form",
                "text": pdf_text
            }]
    
    def _extract_fields_from_part(self, part_text: str, part_number: int, form_type: str) -> List[ExtractedField]:
        """Extract individual fields from a part using AI"""
        self.log(f"Extracting fields from Part {part_number}...")
        
        prompt = f"""
        Extract all form fields from this USCIS {form_type} Part {part_number} text.
        
        For each field, identify:
        1. Field number (e.g., "1.a", "2", "3.b")
        2. Field label/question
        3. Field value (if filled)
        4. Field type (text, date, checkbox, email, phone, address, name, number)
        5. Whether it appears to be required
        
        Part text: {part_text}
        
        Return as JSON array:
        [
          {{
            "field_number": "1.a",
            "field_label": "Family Name (Last Name)",
            "field_value": "Smith",
            "field_type": "name",
            "is_required": true,
            "confidence": 0.95
          }},
          ...
        ]
        
        Be thorough and extract ALL fields, even if they appear empty.
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )
            
            content = response.choices[0].message.content.strip()
            
            # Extract JSON from response
            if content.startswith('```json'):
                content = content[7:-3]
            elif content.startswith('```'):
                content = content[3:-3]
            
            fields_data = json.loads(content)
            
            # Convert to ExtractedField objects
            fields = []
            for field_data in fields_data:
                field = ExtractedField(
                    field_number=field_data.get('field_number', ''),
                    field_label=field_data.get('field_label', ''),
                    field_value=field_data.get('field_value', ''),
                    field_type=FieldType(field_data.get('field_type', 'text')),
                    confidence=field_data.get('confidence', 0.5),
                    is_required=field_data.get('is_required', False),
                    part_number=part_number,
                    extraction_method="ai_agent"
                )
                fields.append(field)
            
            return fields
            
        except Exception as e:
            self.log(f"Field extraction failed: {str(e)}")
            return []

class ValidationAgent(BaseAgent):
    """AI agent for validating extracted form data"""
    
    def __init__(self, openai_client, debug_mode: bool = False):
        super().__init__("Validation Agent", openai_client, debug_mode)
        self.model = "gpt-4o"
    
    def validate_extraction(self, result: ExtractionResult, original_text: str) -> Tuple[bool, Dict[str, Any]]:
        """Validate extracted data and return validation status and report"""
        self.status = AgentStatus.PROCESSING
        self.log("Starting validation of extracted data...")
        
        try:
            validation_report = {
                'overall_valid': True,
                'part_validations': {},
                'missing_fields': [],
                'validation_errors': [],
                'confidence_score': 0.0,
                'recommendations': []
            }
            
            total_score = 0
            part_count = 0
            
            # Validate each part
            for part_num, part in result.parts.items():
                part_validation = self._validate_part(part, original_text)
                validation_report['part_validations'][f'Part {part_num}'] = part_validation
                
                part.validation_score = part_validation['score']
                total_score += part_validation['score']
                part_count += 1
                
                # Update field validation errors
                for i, field in enumerate(part.fields):
                    if i < len(part_validation['field_errors']):
                        field.validation_errors = part_validation['field_errors'][i]
                
                # Check if part validation failed
                if part_validation['score'] < 0.7:
                    validation_report['overall_valid'] = False
                
                self.log(f"Part {part_num} validation score: {part_validation['score']:.2f}")
            
            # Calculate overall confidence
            validation_report['confidence_score'] = total_score / part_count if part_count > 0 else 0
            
            # Check for critical missing fields
            missing_critical = self._check_critical_fields(result)
            if missing_critical:
                validation_report['missing_fields'] = missing_critical
                validation_report['overall_valid'] = False
            
            # Generate recommendations
            validation_report['recommendations'] = self._generate_recommendations(result, validation_report)
            
            result.final_validation_report = validation_report
            
            self.status = AgentStatus.SUCCESS if validation_report['overall_valid'] else AgentStatus.VALIDATION_FAILED
            self.log(f"Validation complete. Valid: {validation_report['overall_valid']}, Score: {validation_report['confidence_score']:.2f}")
            
            return validation_report['overall_valid'], validation_report
            
        except Exception as e:
            self.status = AgentStatus.ERROR
            self.log(f"Validation failed: {str(e)}")
            raise
    
    def _validate_part(self, part: FormPart, original_text: str) -> Dict[str, Any]:
        """Validate a single part using AI"""
        self.log(f"Validating Part {part.number}: {part.title}")
        
        # Prepare fields data for validation
        fields_summary = []
        for field in part.fields:
            fields_summary.append({
                'number': field.field_number,
                'label': field.field_label,
                'value': field.field_value,
                'type': field.field_type.value,
                'confidence': field.confidence
            })
        
        prompt = f"""
        Validate the extracted data for this USCIS form part against the original text.
        
        Part {part.number}: {part.title}
        
        Extracted Fields:
        {json.dumps(fields_summary, indent=2)}
        
        Original Text (relevant section):
        {part.raw_text[:3000]}
        
        Please validate:
        1. Are all visible fields extracted?
        2. Are the field values correct?
        3. Are field types appropriate?
        4. Are required fields properly identified?
        5. Are field numbers/labels accurate?
        
        Return validation as JSON:
        {{
          "score": 0.85,
          "field_errors": [[], ["Invalid date format"], [], ...],
          "missing_fields": ["2.c", "3.a"],
          "incorrect_values": [["1.a", "Should be 'John' not 'Jon'"]],
          "recommendations": ["Check field 2.c for middle name", "Verify date format in field 4"]
        }}
        
        Score should be 0.0-1.0 based on accuracy and completeness.
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )
            
            content = response.choices[0].message.content.strip()
            
            # Extract JSON from response
            if content.startswith('```json'):
                content = content[7:-3]
            elif content.startswith('```'):
                content = content[3:-3]
            
            validation_data = json.loads(content)
            
            # Ensure all required fields exist
            validation_result = {
                'score': validation_data.get('score', 0.5),
                'field_errors': validation_data.get('field_errors', []),
                'missing_fields': validation_data.get('missing_fields', []),
                'incorrect_values': validation_data.get('incorrect_values', []),
                'recommendations': validation_data.get('recommendations', [])
            }
            
            return validation_result
            
        except Exception as e:
            self.log(f"Part validation failed: {str(e)}")
            return {
                'score': 0.3,
                'field_errors': [],
                'missing_fields': [],
                'incorrect_values': [],
                'recommendations': [f"Validation error: {str(e)}"]
            }
    
    def _check_critical_fields(self, result: ExtractionResult) -> List[str]:
        """Check for critical missing fields using AI knowledge"""
        critical_fields_by_form = {
            'I-90': ['1.a', '1.b', '4', '5'],  # Name, DOB, Country of Birth
            'I-130': ['1', '2.a', '2.b', '3.a', '3.b'],  # Relationship, Petitioner/Beneficiary names
            'G-28': ['2.a', '2.b', '5'],  # Attorney name, phone
        }
        
        form_type = result.form_number
        critical_fields = critical_fields_by_form.get(form_type, [])
        
        # Find extracted field numbers
        extracted_numbers = set()
        for part in result.parts.values():
            for field in part.fields:
                extracted_numbers.add(field.field_number)
        
        # Find missing critical fields
        missing = [field for field in critical_fields if field not in extracted_numbers]
        
        if missing:
            self.log(f"Missing critical fields: {missing}")
        
        return missing
    
    def _generate_recommendations(self, result: ExtractionResult, validation_report: Dict) -> List[str]:
        """Generate recommendations for improving extraction"""
        recommendations = []
        
        # Low confidence fields
        low_confidence_fields = []
        for part in result.parts.values():
            for field in part.fields:
                if field.confidence < 0.6:
                    low_confidence_fields.append(f"{field.field_number} ({field.confidence:.2f})")
        
        if low_confidence_fields:
            recommendations.append(f"Review low confidence fields: {', '.join(low_confidence_fields)}")
        
        # Missing values in required fields
        empty_required = []
        for part in result.parts.values():
            for field in part.fields:
                if field.is_required and not field.field_value:
                    empty_required.append(field.field_number)
        
        if empty_required:
            recommendations.append(f"Fill required fields: {', '.join(empty_required)}")
        
        # Overall score recommendations
        if validation_report['confidence_score'] < 0.8:
            recommendations.append("Consider manual review due to low validation score")
        
        return recommendations

class CoordinatorAgent(BaseAgent):
    """Coordinator agent that manages the extraction-validation loop"""
    
    def __init__(self, openai_client, extractor_agent: ExtractorAgent, validation_agent: ValidationAgent, 
                 max_iterations: int = 3, debug_mode: bool = False):
        super().__init__("Coordinator Agent", openai_client, debug_mode)
        self.extractor = extractor_agent
        self.validator = validation_agent
        self.max_iterations = max_iterations
        self.model = "gpt-4o"
    
    def process_form(self, pdf_text: str, form_type: str = None) -> ExtractionResult:
        """Main processing loop: extract -> validate -> improve until acceptable"""
        self.status = AgentStatus.PROCESSING
        self.log("Starting coordinated form processing...")
        
        start_time = time.time()
        iteration = 1
        result = None
        
        try:
            while iteration <= self.max_iterations:
                self.log(f"=== ITERATION {iteration} ===")
                
                # EXTRACTION PHASE
                self.log("Phase 1: Extraction")
                if iteration == 1:
                    # First extraction
                    result = self.extractor.extract_form_data(pdf_text, form_type)
                else:
                    # Improved extraction based on validation feedback
                    result = self._improve_extraction(pdf_text, form_type, result, last_validation_report)
                
                result.extraction_iterations = iteration
                
                # VALIDATION PHASE
                self.log("Phase 2: Validation")
                is_valid, validation_report = self.validator.validate_extraction(result, pdf_text)
                last_validation_report = validation_report
                
                # CHECK COMPLETION
                self.log(f"Validation result: Valid={is_valid}, Score={validation_report['confidence_score']:.2f}")
                
                if is_valid or validation_report['confidence_score'] >= 0.85:
                    self.log("✅ Validation passed! Processing complete.")
                    self.status = AgentStatus.SUCCESS
                    break
                elif iteration == self.max_iterations:
                    self.log("⚠️ Max iterations reached. Returning best result.")
                    self.status = AgentStatus.VALIDATION_FAILED
                    break
                else:
                    self.log(f"❌ Validation failed. Preparing iteration {iteration + 1}...")
                    iteration += 1
            
            # Finalize result
            result.processing_time = time.time() - start_time
            result.agent_logs = (self.get_logs() + 
                               self.extractor.get_logs() + 
                               self.validator.get_logs())
            
            self.log(f"Processing complete in {result.processing_time:.2f}s with {iteration} iterations")
            return result
            
        except Exception as e:
            self.status = AgentStatus.ERROR
            self.log(f"Coordination failed: {str(e)}")
            raise
    
    def _improve_extraction(self, pdf_text: str, form_type: str, previous_result: ExtractionResult, 
                          validation_report: Dict) -> ExtractionResult:
        """Improve extraction based on validation feedback"""
        self.log("Improving extraction based on validation feedback...")
        
        # Analyze what went wrong
        issues = []
        if validation_report.get('missing_fields'):
            issues.append(f"Missing fields: {', '.join(validation_report['missing_fields'])}")
        
        for part_name, part_val in validation_report.get('part_validations', {}).items():
            if part_val.get('incorrect_values'):
                for field_num, issue in part_val['incorrect_values']:
                    issues.append(f"Field {field_num}: {issue}")
        
        # Create improvement prompt
        improvement_prompt = f"""
        The previous extraction had these issues:
        {chr(10).join(issues)}
        
        Previous extraction summary:
        - Total fields: {previous_result.total_fields}
        - Filled fields: {previous_result.filled_fields}
        - Validation score: {validation_report['confidence_score']:.2f}
        
        Recommendations from validator:
        {chr(10).join(validation_report.get('recommendations', []))}
        
        Please re-extract the form data with special attention to these issues.
        Focus on accuracy and completeness.
        """
        
        # Use the improvement guidance to re-extract
        self.extractor.log("Re-extracting with improvements...")
        self.extractor.log(improvement_prompt)
        
        # Perform improved extraction (reuse existing logic but with context)
        return self.extractor.extract_form_data(pdf_text, form_type)

# ===== OPENAI CLIENT SETUP =====
def get_openai_client():
    """Get OpenAI client with API key from secrets"""
    try:
        api_key = st.secrets.get("OPENAI_API_KEY")
        if not api_key:
            st.error("OpenAI API key not found in secrets!")
            return None
        
        client = openai.OpenAI(api_key=api_key)
        return client
    except Exception as e:
        st.error(f"Failed to initialize OpenAI client: {str(e)}")
        return None

# ===== PDF PROCESSING =====
def extract_pdf_text(pdf_file) -> str:
    """Extract text from PDF file"""
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
            full_text += f"\n--- PAGE {page_num + 1} ---\n{page_text}\n"
        
        doc.close()
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
    
    # Initialize components
    if 'db_manager' not in st.session_state:
        st.session_state.db_manager = DatabaseManager()
    if 'extraction_result' not in st.session_state:
        st.session_state.extraction_result = None
    if 'current_submission_id' not in st.session_state:
        st.session_state.current_submission_id = None
    
    db_manager = st.session_state.db_manager
    
    # Sidebar
    with st.sidebar:
        st.markdown("## ⚙️ Agent Settings")
        debug_mode = st.checkbox("Debug Mode", value=False, help="Show detailed agent logs")
        max_iterations = st.slider("Max Iterations", min_value=1, max_value=5, value=3, 
                                  help="Maximum extraction-validation loops")
        
        st.markdown("## 🤖 Agent Info")
        st.info("""
        **Extractor Agent**: Uses GPT-4 to intelligently extract form fields
        
        **Validation Agent**: Validates extraction accuracy and completeness
        
        **Coordinator**: Manages the improvement loop until validation passes
        """)
        
        st.markdown("## 📊 Processing Stats")
        try:
            submissions = db_manager.get_form_submissions(limit=5)
            if submissions:
                latest = submissions[0]
                st.metric("Latest Form", latest.form_type)
                st.metric("Iterations", latest.iterations)
                st.metric("Score", f"{latest.validation_score:.1f}%")
        except:
            st.write("No submissions yet")
    
    # Initialize agents
    extractor_agent = ExtractorAgent(openai_client, debug_mode)
    validation_agent = ValidationAgent(openai_client, debug_mode)
    coordinator_agent = CoordinatorAgent(openai_client, extractor_agent, validation_agent, 
                                       max_iterations, debug_mode)
    
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
                    # Show processing status
                    status_placeholder = st.empty()
                    progress_bar = st.progress(0)
                    
                    with st.spinner("Processing with AI agents..."):
                        try:
                            # Extract PDF text
                            progress_bar.progress(10)
                            st.write("📄 Extracting PDF text...")
                            pdf_text = extract_pdf_text(uploaded_file)
                            
                            if not pdf_text:
                                st.error("Failed to extract text from PDF")
                                st.stop()
                            
                            progress_bar.progress(20)
                            
                            # Determine form type
                            form_type = None if form_type_hint == "Auto-detect" else form_type_hint
                            
                            # Process with coordinator agent
                            st.write("🤖 Starting AI agent processing...")
                            progress_bar.progress(30)
                            
                            # Show agent status during processing
                            with status_placeholder.container():
                                display_processing_status(extractor_agent, validation_agent, coordinator_agent)
                            
                            # Process
                            result = coordinator_agent.process_form(pdf_text, form_type)
                            progress_bar.progress(90)
                            
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
                                notes=f"Processed with {result.extraction_iterations} iterations"
                            )
                            
                            submission_id = db_manager.save_form_submission(submission)
                            st.session_state.current_submission_id = submission_id
                            st.session_state.extraction_result = result
                            
                            progress_bar.progress(100)
                            
                            # Final status
                            status_placeholder.empty()
                            
                            if result.validation_score >= 0.8:
                                st.success(f"✅ Processing completed! Score: {result.validation_score:.1%}")
                                st.balloons()
                            elif result.validation_score >= 0.6:
                                st.warning(f"⚠️ Processing completed with issues. Score: {result.validation_score:.1%}")
                            else:
                                st.error(f"❌ Processing completed but validation failed. Score: {result.validation_score:.1%}")
                            
                            st.info(f"Completed in {result.extraction_iterations} iterations ({result.processing_time:.1f}s)")
                            
                        except Exception as e:
                            st.error(f"Processing failed: {str(e)}")
                            if debug_mode:
                                st.exception(e)
        
        # Live agent status (when not processing)
        if 'extraction_result' not in st.session_state or st.session_state.extraction_result is None:
            st.markdown("### 🤖 Agent Status")
            display_processing_status(extractor_agent, validation_agent, coordinator_agent)
    
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
        
        # Recent submissions
        submissions = db_manager.get_form_submissions(limit=20)
        
        if submissions:
            st.markdown("#### Recent AI-Processed Forms")
            
            submission_data = []
            for sub in submissions:
                submission_data.append({
                    'ID': sub.id,
                    'Form': sub.form_type,
                    'Date': str(sub.submission_date)[:19],
                    'Fields': f"{sub.completed_fields}/{sub.total_fields}",
                    'Score': f"{sub.validation_score:.1f}%",
                    'Iterations': sub.iterations,
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
                    st.markdown(f"**Iterations:** {selected_submission.iterations}")
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
    
    # Agent Analytics Tab  
    with tabs[3]:
        st.markdown("### 📈 AI Agent Analytics")
        
        submissions = db_manager.get_form_submissions(limit=100)
        
        if submissions:
            # Performance metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                avg_score = sum(s.validation_score for s in submissions) / len(submissions)
                st.metric("Average Validation Score", f"{avg_score:.1f}%")
            
            with col2:
                avg_iterations = sum(s.iterations for s in submissions) / len(submissions)
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
                score_df = pd.DataFrame({'Validation Score': scores})
                st.bar_chart(score_df['Validation Score'].value_counts().sort_index())
            
            with col2:
                st.markdown("#### Iterations Required")
                iterations = [s.iterations for s in submissions]
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
                form_stats[sub.form_type]['total_iterations'] += sub.iterations
            
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

if __name__ == "__main__":
    main()
