#!/usr/bin/env python3
"""
🤖 AGENTIC USCIS FORM READER - COMPLETE SYSTEM
===================================================

A fully autonomous AI-powered system that can intelligently read, parse, 
and map ANY USCIS form with minimal human intervention.

Features:
- Universal form detection and parsing
- Intelligent field extraction with proper numbering  
- AI-powered database mapping
- Multi-form support
- Advanced validation and error correction
- Real-time processing
- Production-ready architecture
- Comprehensive export capabilities

Author: AI Assistant
Version: 1.0.0
"""

import os
import json
import re
import time
import sqlite3
import tempfile
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from contextlib import contextmanager
import hashlib
from pathlib import Path

import streamlit as st
import pandas as pd
import numpy as np

# Core imports with error handling
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
    from sentence_transformers import SentenceTransformer
    import faiss
    SEMANTIC_SEARCH_AVAILABLE = True
except ImportError:
    SEMANTIC_SEARCH_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page config
st.set_page_config(
    page_title="🤖 Agentic USCIS Form Reader",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Enhanced CSS with modern design
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 2.5rem;
        border-radius: 15px;
        margin-bottom: 2rem;
        text-align: center;
        box-shadow: 0 10px 30px rgba(0,0,0,0.1);
    }
    
    .agent-status {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
        text-align: center;
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(56, 239, 125, 0.7); }
        70% { box-shadow: 0 0 0 10px rgba(56, 239, 125, 0); }
        100% { box-shadow: 0 0 0 0 rgba(56, 239, 125, 0); }
    }
    
    .form-analysis {
        background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%);
        border: 1px solid #f39c12;
        border-radius: 10px;
        padding: 1.5rem;
        margin: 1rem 0;
    }
    
    .field-intelligent {
        background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);
        border-left: 4px solid #667eea;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        position: relative;
        transition: all 0.3s ease;
    }
    
    .field-intelligent:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(0,0,0,0.1);
    }
    
    .confidence-bar {
        background: #e0e0e0;
        border-radius: 10px;
        height: 8px;
        overflow: hidden;
        margin: 0.5rem 0;
    }
    
    .confidence-fill {
        height: 100%;
        background: linear-gradient(90deg, #ff6b6b, #ffa500, #4ecdc4);
        transition: width 0.3s ease;
    }
    
    .ai-suggestion {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 0.5rem;
        border-radius: 5px;
        margin: 0.3rem 0;
        font-size: 0.9rem;
    }
    
    .processing-stage {
        background: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        border-left: 4px solid #007bff;
    }
    
    .validation-error {
        background: #ffebee;
        border: 1px solid #f44336;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        color: #c62828;
    }
    
    .validation-success {
        background: #e8f5e9;
        border: 1px solid #4caf50;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        color: #2e7d32;
    }
    
    .agent-thinking {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
        text-align: center;
    }
    
    .metrics-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1rem;
        margin: 1rem 0;
    }
    
    .metric-card {
        background: white;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 1.5rem;
        text-align: center;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
    }
    
    .export-ready {
        background: linear-gradient(135deg, #56ab2f 0%, #a8e6cf 100%);
        color: #2d5016;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
        text-align: center;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# ===== ADVANCED DATA STRUCTURES =====

class ProcessingStage(Enum):
    UPLOADED = "uploaded"
    ANALYZING = "analyzing"
    EXTRACTING = "extracting"
    MAPPING = "mapping"
    VALIDATING = "validating"
    COMPLETED = "completed"
    ERROR = "error"

class FieldType(Enum):
    TEXT = "text"
    DATE = "date"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    NUMBER = "number"
    EMAIL = "email"
    PHONE = "phone"
    ADDRESS = "address"
    SSN = "ssn"
    ALIEN_NUMBER = "alien_number"
    CURRENCY = "currency"

class ConfidenceLevel(Enum):
    VERY_HIGH = 0.9
    HIGH = 0.75
    MEDIUM = 0.5
    LOW = 0.25
    VERY_LOW = 0.1

@dataclass
class ValidationResult:
    is_valid: bool
    score: float
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

@dataclass
class AIInsight:
    insight_type: str
    confidence: float
    description: str
    action_recommended: str
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SmartField:
    # Basic field information
    field_number: str
    field_label: str
    field_value: str = ""
    field_type: FieldType = FieldType.TEXT
    
    # Position and context
    part_number: int = 1
    sequence_order: int = 0
    page_number: int = 1
    coordinates: Tuple[float, float, float, float] = (0, 0, 0, 0)  # x1, y1, x2, y2
    
    # AI-powered attributes
    extraction_confidence: float = 0.0
    ai_insights: List[AIInsight] = field(default_factory=list)
    semantic_keywords: List[str] = field(default_factory=list)
    
    # Mapping information
    is_mapped: bool = False
    db_object: str = ""
    db_path: str = ""
    db_type: str = "TextBox"
    mapping_confidence: float = 0.0
    alternative_mappings: List[Dict[str, Any]] = field(default_factory=list)
    
    # Validation and processing
    validation_result: Optional[ValidationResult] = None
    is_required: bool = False
    dependencies: List[str] = field(default_factory=list)
    
    # User interaction
    manually_edited: bool = False
    in_questionnaire: bool = False
    user_validated: bool = False
    processing_notes: List[str] = field(default_factory=list)
    
    # Advanced features
    regex_pattern: Optional[str] = None
    format_mask: Optional[str] = None
    lookup_table: Optional[Dict[str, str]] = None
    
    def add_insight(self, insight: AIInsight):
        self.ai_insights.append(insight)
    
    def get_confidence_color(self) -> str:
        if self.extraction_confidence >= 0.9:
            return "🟢"
        elif self.extraction_confidence >= 0.7:
            return "🟡"
        elif self.extraction_confidence >= 0.5:
            return "🟠"
        else:
            return "🔴"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'field_number': self.field_number,
            'field_label': self.field_label,
            'field_value': self.field_value,
            'field_type': self.field_type.value,
            'part_number': self.part_number,
            'sequence_order': self.sequence_order,
            'page_number': self.page_number,
            'coordinates': self.coordinates,
            'extraction_confidence': self.extraction_confidence,
            'ai_insights': [asdict(insight) for insight in self.ai_insights],
            'semantic_keywords': self.semantic_keywords,
            'is_mapped': self.is_mapped,
            'db_object': self.db_object,
            'db_path': self.db_path,
            'db_type': self.db_type,
            'mapping_confidence': self.mapping_confidence,
            'alternative_mappings': self.alternative_mappings,
            'validation_result': asdict(self.validation_result) if self.validation_result else None,
            'is_required': self.is_required,
            'dependencies': self.dependencies,
            'manually_edited': self.manually_edited,
            'in_questionnaire': self.in_questionnaire,
            'user_validated': self.user_validated,
            'processing_notes': self.processing_notes,
            'regex_pattern': self.regex_pattern,
            'format_mask': self.format_mask,
            'lookup_table': self.lookup_table
        }

@dataclass
class SmartPart:
    number: int
    title: str
    description: str = ""
    fields: List[SmartField] = field(default_factory=list)
    ai_analysis: Dict[str, Any] = field(default_factory=dict)
    completion_score: float = 0.0
    validation_status: str = "pending"
    
    def add_field(self, field: SmartField):
        field.part_number = self.number
        self.fields.append(field)
        self.fields.sort(key=lambda f: f.sequence_order)
    
    def get_mapped_fields(self) -> List[SmartField]:
        return [f for f in self.fields if f.is_mapped and not f.in_questionnaire]
    
    def get_unmapped_fields(self) -> List[SmartField]:
        return [f for f in self.fields if not f.is_mapped and not f.in_questionnaire]
    
    def get_questionnaire_fields(self) -> List[SmartField]:
        return [f for f in self.fields if f.in_questionnaire]
    
    def calculate_completion_score(self):
        if not self.fields:
            self.completion_score = 0.0
            return
        
        filled_fields = sum(1 for f in self.fields if f.field_value.strip())
        mapped_fields = sum(1 for f in self.fields if f.is_mapped or f.in_questionnaire)
        
        completion = (filled_fields + mapped_fields) / (len(self.fields) * 2)
        self.completion_score = min(completion, 1.0)

@dataclass
class SmartForm:
    # Basic form information
    form_number: str
    form_title: str
    form_edition: str = ""
    total_pages: int = 0
    
    # Structure
    parts: Dict[int, SmartPart] = field(default_factory=dict)
    
    # Processing information
    processing_stage: ProcessingStage = ProcessingStage.UPLOADED
    processing_time: float = 0.0
    ai_analysis: Dict[str, Any] = field(default_factory=dict)
    
    # Quality metrics
    overall_confidence: float = 0.0
    validation_score: float = 0.0
    completion_percentage: float = 0.0
    
    # Advanced features
    form_signature: str = ""  # Unique identifier based on structure
    similar_forms: List[str] = field(default_factory=list)
    processing_history: List[Dict[str, Any]] = field(default_factory=list)
    
    def add_part(self, part: SmartPart):
        self.parts[part.number] = part
        self.calculate_metrics()
    
    def get_all_fields(self) -> List[SmartField]:
        all_fields = []
        for part in sorted(self.parts.values(), key=lambda p: p.number):
            all_fields.extend(part.fields)
        return all_fields
    
    def get_mapped_fields(self) -> List[SmartField]:
        mapped = []
        for part in self.parts.values():
            mapped.extend(part.get_mapped_fields())
        return mapped
    
    def get_unmapped_fields(self) -> List[SmartField]:
        unmapped = []
        for part in self.parts.values():
            unmapped.extend(part.get_unmapped_fields())
        return unmapped
    
    def get_questionnaire_fields(self) -> List[SmartField]:
        questionnaire = []
        for part in self.parts.values():
            questionnaire.extend(part.get_questionnaire_fields())
        return questionnaire
    
    def calculate_metrics(self):
        all_fields = self.get_all_fields()
        
        if not all_fields:
            self.overall_confidence = 0.0
            self.completion_percentage = 0.0
            return
        
        # Calculate overall confidence
        confidences = [f.extraction_confidence for f in all_fields]
        self.overall_confidence = np.mean(confidences) if confidences else 0.0
        
        # Calculate completion percentage
        filled_fields = sum(1 for f in all_fields if f.field_value.strip())
        mapped_or_questionnaire = sum(1 for f in all_fields if f.is_mapped or f.in_questionnaire)
        
        self.completion_percentage = (filled_fields + mapped_or_questionnaire) / (len(all_fields) * 2) if all_fields else 0.0
        self.completion_percentage = min(self.completion_percentage, 1.0)
        
        # Update part completion scores
        for part in self.parts.values():
            part.calculate_completion_score()
    
    def generate_signature(self):
        """Generate unique signature based on form structure"""
        structure_data = {
            'form_number': self.form_number,
            'parts': {p.number: p.title for p in self.parts.values()},
            'field_count': len(self.get_all_fields())
        }
        
        signature_string = json.dumps(structure_data, sort_keys=True)
        self.form_signature = hashlib.md5(signature_string.encode()).hexdigest()

# ===== COMPREHENSIVE DATABASE SCHEMA =====

UNIVERSAL_DB_SCHEMA = {
    "attorney": {
        "attorneyInfo": {
            "firstName": {"type": "string", "keywords": ["first", "given", "name"], "patterns": [r"first\s+name", r"given\s+name"]},
            "lastName": {"type": "string", "keywords": ["last", "family", "surname"], "patterns": [r"last\s+name", r"family\s+name", r"surname"]},
            "middleName": {"type": "string", "keywords": ["middle"], "patterns": [r"middle\s+name", r"middle\s+initial"]},
            "workPhone": {"type": "phone", "keywords": ["work", "office", "phone"], "patterns": [r"work\s+phone", r"office\s+phone", r"business\s+phone"]},
            "mobilePhone": {"type": "phone", "keywords": ["mobile", "cell", "cellular"], "patterns": [r"mobile\s+phone", r"cell\s+phone"]},
            "faxNumber": {"type": "phone", "keywords": ["fax"], "patterns": [r"fax\s+number", r"facsimile"]},
            "emailAddress": {"type": "email", "keywords": ["email"], "patterns": [r"email\s+address", r"e-mail"]},
            "stateBarNumber": {"type": "string", "keywords": ["bar", "license"], "patterns": [r"bar\s+number", r"license\s+number"]},
            "licensingAuthority": {"type": "string", "keywords": ["licensing", "authority"], "patterns": [r"licensing\s+authority"]},
            "uscisRepresentation": {"type": "boolean", "keywords": ["uscis", "representation"], "patterns": [r"uscis.*representation"]},
            "iceRepresentation": {"type": "boolean", "keywords": ["ice", "representation"], "patterns": [r"ice.*representation"]},
            "cbpRepresentation": {"type": "boolean", "keywords": ["cbp", "representation"], "patterns": [r"cbp.*representation"]},
            "formNumbers": {"type": "string", "keywords": ["form", "numbers"], "patterns": [r"form\s+numbers"]},
            "iceMatters": {"type": "string", "keywords": ["ice", "matters"], "patterns": [r"ice.*matters"]},
            "cbpMatters": {"type": "string", "keywords": ["cbp", "matters"], "patterns": [r"cbp.*matters"]},
            "receiptNumber": {"type": "string", "keywords": ["receipt", "number"], "patterns": [r"receipt\s+number"]},
            "representativeType": {"type": "string", "keywords": ["representative", "type"], "patterns": [r"representative\s+type"]}
        },
        "address": {
            "addressStreet": {"type": "address", "keywords": ["street", "address"], "patterns": [r"street.*address", r"street.*name"]},
            "addressCity": {"type": "string", "keywords": ["city", "town"], "patterns": [r"city", r"town"]},
            "addressState": {"type": "string", "keywords": ["state"], "patterns": [r"state", r"province"]},
            "addressZip": {"type": "string", "keywords": ["zip", "postal"], "patterns": [r"zip\s+code", r"postal\s+code"]},
            "addressCountry": {"type": "string", "keywords": ["country"], "patterns": [r"country"]},
            "addressType": {"type": "string", "keywords": ["apt", "suite", "floor"], "patterns": [r"apt", r"suite", r"floor", r"unit"]},
            "addressNumber": {"type": "string", "keywords": ["number"], "patterns": [r"number"]},
            "addressProvince": {"type": "string", "keywords": ["province"], "patterns": [r"province"]},
            "addressPostalCode": {"type": "string", "keywords": ["postal"], "patterns": [r"postal\s+code"]}
        }
    },
    "beneficiary": {
        "Beneficiary": {
            "beneficiaryFirstName": {"type": "string", "keywords": ["first", "given"], "patterns": [r"first\s+name", r"given\s+name"]},
            "beneficiaryLastName": {"type": "string", "keywords": ["last", "family", "surname"], "patterns": [r"last\s+name", r"family\s+name", r"surname"]},
            "beneficiaryMiddleName": {"type": "string", "keywords": ["middle"], "patterns": [r"middle\s+name", r"middle\s+initial"]},
            "beneficiaryGender": {"type": "radio", "keywords": ["gender", "sex"], "patterns": [r"gender", r"sex", r"male", r"female"]},
            "beneficiaryDateOfBirth": {"type": "date", "keywords": ["birth", "date"], "patterns": [r"date.*birth", r"birth.*date", r"dob"]},
            "beneficiarySsn": {"type": "ssn", "keywords": ["ssn", "social", "security"], "patterns": [r"social\s+security", r"ssn"]},
            "alienNumber": {"type": "alien_number", "keywords": ["alien", "number"], "patterns": [r"alien.*number", r"a-number", r"a\s+number"]},
            "beneficiaryCountryOfBirth": {"type": "string", "keywords": ["country", "birth"], "patterns": [r"country.*birth"]},
            "beneficiaryProvinceOfBirth": {"type": "string", "keywords": ["province", "birth"], "patterns": [r"province.*birth"]},
            "beneficiaryCellNumber": {"type": "phone", "keywords": ["cell", "mobile"], "patterns": [r"cell.*phone", r"mobile.*phone"]},
            "beneficiaryHomeNumber": {"type": "phone", "keywords": ["home", "phone"], "patterns": [r"home.*phone"]},
            "beneficiaryWorkNumber": {"type": "phone", "keywords": ["work", "phone"], "patterns": [r"work.*phone", r"office.*phone"]},
            "beneficiaryPrimaryEmailAddress": {"type": "email", "keywords": ["email"], "patterns": [r"email\s+address", r"e-mail"]},
            "uscisOnlineAccount": {"type": "string", "keywords": ["uscis", "account"], "patterns": [r"uscis.*account", r"online.*account"]},
            "nameChanged": {"type": "boolean", "keywords": ["name", "changed"], "patterns": [r"name.*changed"]},
            "previousFirstName": {"type": "string", "keywords": ["previous", "first"], "patterns": [r"previous.*first", r"former.*first"]},
            "previousLastName": {"type": "string", "keywords": ["previous", "last"], "patterns": [r"previous.*last", r"former.*last"]},
            "previousMiddleName": {"type": "string", "keywords": ["previous", "middle"], "patterns": [r"previous.*middle", r"former.*middle"]}
        },
        "HomeAddress": {
            "addressStreet": {"type": "address", "keywords": ["home", "street"], "patterns": [r"home.*street", r"residential.*street"]},
            "addressCity": {"type": "string", "keywords": ["home", "city"], "patterns": [r"home.*city", r"residential.*city"]},
            "addressState": {"type": "string", "keywords": ["home", "state"], "patterns": [r"home.*state", r"residential.*state"]},
            "addressZip": {"type": "string", "keywords": ["home", "zip"], "patterns": [r"home.*zip", r"residential.*zip"]},
            "addressCountry": {"type": "string", "keywords": ["home", "country"], "patterns": [r"home.*country", r"residential.*country"]},
            "addressType": {"type": "string", "keywords": ["apt", "suite"], "patterns": [r"apt", r"suite", r"unit"]},
            "addressNumber": {"type": "string", "keywords": ["number"], "patterns": [r"number"]},
            "addressProvince": {"type": "string", "keywords": ["province"], "patterns": [r"province"]},
            "addressPostalCode": {"type": "string", "keywords": ["postal"], "patterns": [r"postal\s+code"]}
        },
        "WorkAddress": {
            "addressStreet": {"type": "address", "keywords": ["work", "street"], "patterns": [r"work.*street", r"business.*street"]},
            "addressCity": {"type": "string", "keywords": ["work", "city"], "patterns": [r"work.*city", r"business.*city"]},
            "addressState": {"type": "string", "keywords": ["work", "state"], "patterns": [r"work.*state", r"business.*state"]},
            "addressZip": {"type": "string", "keywords": ["work", "zip"], "patterns": [r"work.*zip", r"business.*zip"]},
            "addressCountry": {"type": "string", "keywords": ["work", "country"], "patterns": [r"work.*country", r"business.*country"]},
            "addressType": {"type": "string", "keywords": ["suite", "floor"], "patterns": [r"suite", r"floor", r"unit"]},
            "addressNumber": {"type": "string", "keywords": ["number"], "patterns": [r"number"]}
        }
    },
    "customer": {
        "customer_name": {"type": "string", "keywords": ["company", "organization"], "patterns": [r"company.*name", r"organization.*name"]},
        "customer_tax_id": {"type": "string", "keywords": ["tax", "ein"], "patterns": [r"tax.*id", r"ein", r"federal.*id"]},
        "customer_website_url": {"type": "string", "keywords": ["website", "url"], "patterns": [r"website", r"url"]},
        "signatory_first_name": {"type": "string", "keywords": ["signatory", "first"], "patterns": [r"signatory.*first"]},
        "signatory_last_name": {"type": "string", "keywords": ["signatory", "last"], "patterns": [r"signatory.*last"]},
        "signatory_middle_name": {"type": "string", "keywords": ["signatory", "middle"], "patterns": [r"signatory.*middle"]},
        "signatory_work_phone": {"type": "phone", "keywords": ["signatory", "phone"], "patterns": [r"signatory.*phone"]},
        "signatory_mobile_phone": {"type": "phone", "keywords": ["signatory", "mobile"], "patterns": [r"signatory.*mobile"]},
        "signatory_email_id": {"type": "email", "keywords": ["signatory", "email"], "patterns": [r"signatory.*email"]},
        "signatory_job_title": {"type": "string", "keywords": ["signatory", "title"], "patterns": [r"signatory.*title"]},
        "address_street": {"type": "address", "keywords": ["company", "street"], "patterns": [r"company.*street", r"business.*street"]},
        "address_city": {"type": "string", "keywords": ["company", "city"], "patterns": [r"company.*city", r"business.*city"]},
        "address_state": {"type": "string", "keywords": ["company", "state"], "patterns": [r"company.*state", r"business.*state"]},
        "address_zip": {"type": "string", "keywords": ["company", "zip"], "patterns": [r"company.*zip", r"business.*zip"]},
        "address_country": {"type": "string", "keywords": ["company", "country"], "patterns": [r"company.*country", r"business.*country"]},
        "address_type": {"type": "string", "keywords": ["suite", "floor"], "patterns": [r"suite", r"floor"]},
        "address_number": {"type": "string", "keywords": ["number"], "patterns": [r"number"]}
    },
    "lawfirm": {
        "lawfirmDetails": {
            "lawFirmName": {"type": "string", "keywords": ["law", "firm"], "patterns": [r"law.*firm", r"firm.*name"]},
            "uscisOnlineAccountNumber": {"type": "string", "keywords": ["uscis", "account"], "patterns": [r"uscis.*account"]},
            "lawFirmFein": {"type": "string", "keywords": ["fein", "tax"], "patterns": [r"fein", r"federal.*id"]},
            "companyPhone": {"type": "phone", "keywords": ["company", "phone"], "patterns": [r"company.*phone", r"firm.*phone"]}
        },
        "address": {
            "addressStreet": {"type": "address", "keywords": ["firm", "street"], "patterns": [r"firm.*street", r"law.*street"]},
            "addressCity": {"type": "string", "keywords": ["firm", "city"], "patterns": [r"firm.*city", r"law.*city"]},
            "addressState": {"type": "string", "keywords": ["firm", "state"], "patterns": [r"firm.*state", r"law.*state"]},
            "addressZip": {"type": "string", "keywords": ["firm", "zip"], "patterns": [r"firm.*zip", r"law.*zip"]},
            "addressCountry": {"type": "string", "keywords": ["firm", "country"], "patterns": [r"firm.*country", r"law.*country"]}
        }
    }
}

# ===== AGENTIC AI PROCESSOR =====

class AgenticProcessor:
    """Main agentic processor that orchestrates all AI operations"""
    
    def __init__(self, openai_client):
        self.openai_client = openai_client
        self.semantic_model = None
        self.field_embeddings = None
        self.processing_history = []
        
        # Initialize semantic search if available
        if SEMANTIC_SEARCH_AVAILABLE:
            try:
                self.semantic_model = SentenceTransformer('all-MiniLM-L6-v2')
                self._build_field_embeddings()
            except Exception as e:
                logger.warning(f"Failed to initialize semantic search: {e}")
    
    def _build_field_embeddings(self):
        """Build embeddings for all database fields for semantic matching"""
        if not self.semantic_model:
            return
        
        field_descriptions = []
        field_metadata = []
        
        for obj_name, obj_data in UNIVERSAL_DB_SCHEMA.items():
            for field_path, field_info in self._flatten_schema(obj_data, obj_name):
                description = f"{field_path} {' '.join(field_info.get('keywords', []))}"
                field_descriptions.append(description)
                field_metadata.append({
                    'object': obj_name,
                    'path': field_path,
                    'type': field_info.get('type', 'string'),
                    'keywords': field_info.get('keywords', []),
                    'patterns': field_info.get('patterns', [])
                })
        
        if field_descriptions:
            embeddings = self.semantic_model.encode(field_descriptions)
            self.field_embeddings = {
                'embeddings': embeddings,
                'metadata': field_metadata,
                'descriptions': field_descriptions
            }
    
    def _flatten_schema(self, schema, prefix=""):
        """Flatten nested schema for embedding creation"""
        flattened = []
        
        for key, value in schema.items():
            current_path = f"{prefix}.{key}" if prefix else key
            
            if isinstance(value, dict) and 'type' in value:
                # This is a field definition
                flattened.append((current_path, value))
            elif isinstance(value, dict):
                # This is a nested object
                flattened.extend(self._flatten_schema(value, current_path))
        
        return flattened
    
    async def process_form_intelligently(self, pdf_text: str, progress_callback=None) -> SmartForm:
        """Main intelligent processing pipeline"""
        
        try:
            # Stage 1: Form Analysis
            if progress_callback:
                progress_callback("🔍 Analyzing form structure...")
            
            form_info = await self._analyze_form_structure(pdf_text)
            
            # Stage 2: Create Smart Form
            smart_form = SmartForm(
                form_number=form_info['form_number'],
                form_title=form_info['form_title'],
                form_edition=form_info.get('form_edition', ''),
                total_pages=form_info.get('total_pages', 0),
                processing_stage=ProcessingStage.ANALYZING
            )
            
            # Stage 3: Extract Parts and Fields
            if progress_callback:
                progress_callback("📄 Extracting parts and fields...")
            
            parts_data = await self._extract_parts_intelligently(pdf_text, smart_form)
            
            for part_data in parts_data:
                smart_part = SmartPart(
                    number=part_data['number'],
                    title=part_data['title'],
                    description=part_data.get('description', '')
                )
                
                # Extract fields for this part
                fields = await self._extract_fields_intelligently(
                    part_data['text'], 
                    part_data['number'],
                    smart_form
                )
                
                for field in fields:
                    smart_part.add_field(field)
                
                smart_form.add_part(smart_part)
            
            # Stage 4: Intelligent Mapping
            if progress_callback:
                progress_callback("🧠 Applying intelligent mapping...")
            
            await self._apply_intelligent_mapping(smart_form)
            
            # Stage 5: Validation and Quality Assurance
            if progress_callback:
                progress_callback("✅ Validating results...")
            
            await self._validate_and_enhance(smart_form)
            
            smart_form.processing_stage = ProcessingStage.COMPLETED
            smart_form.generate_signature()
            
            return smart_form
            
        except Exception as e:
            logger.error(f"Intelligent processing failed: {e}")
            raise
    
    async def _analyze_form_structure(self, pdf_text: str) -> Dict[str, Any]:
        """Analyze form structure using advanced AI"""
        
        prompt = f"""
        You are an expert USCIS form analyst. Analyze this form text and provide comprehensive insights.
        
        Extract and analyze:
        1. Form identification (number, title, edition)
        2. Form complexity and structure
        3. Key sections and parts
        4. Field density and types
        5. Special requirements or patterns
        
        Return ONLY valid JSON:
        {{
            "form_number": "extracted_form_number",
            "form_title": "extracted_title",
            "form_edition": "edition_date",
            "total_pages": estimated_pages,
            "complexity_score": 0.0-1.0,
            "estimated_fields": number,
            "special_features": ["list", "of", "features"],
            "processing_recommendations": ["recommendations"]
        }}
        
        Form text (first 8000 chars):
        {pdf_text[:8000]}
        """
        
        try:
            response = await self._call_openai_async(prompt)
            return self._parse_json_response(response)
        except Exception as e:
            logger.error(f"Form analysis failed: {e}")
            return {
                'form_number': 'Unknown',
                'form_title': 'Unknown Form',
                'form_edition': '',
                'total_pages': 0,
                'complexity_score': 0.5,
                'estimated_fields': 0,
                'special_features': [],
                'processing_recommendations': []
            }
    
    async def _extract_parts_intelligently(self, pdf_text: str, smart_form: SmartForm) -> List[Dict[str, Any]]:
        """Extract form parts with intelligent analysis"""
        
        prompt = f"""
        You are an expert at analyzing USCIS form structure. Extract all parts from this {smart_form.form_number} form.
        
        Rules for part extraction:
        1. Identify clear part boundaries (Part 1, Part 2, etc.)
        2. Extract exact titles as they appear
        3. Provide meaningful descriptions
        4. Include the text content for each part
        5. Maintain sequential order
        
        Return ONLY valid JSON:
        {{
            "parts": [
                {{
                    "number": 1,
                    "title": "Information About You",
                    "description": "Basic applicant information",
                    "text": "extracted_text_for_this_part",
                    "estimated_fields": 10,
                    "complexity": "low|medium|high"
                }}
            ]
        }}
        
        Form text:
        {pdf_text[:12000]}
        """
        
        try:
            response = await self._call_openai_async(prompt, model="gpt-4o", max_tokens=4000)
            data = self._parse_json_response(response)
            return data.get('parts', [])
        except Exception as e:
            logger.error(f"Parts extraction failed: {e}")
            # Fallback: create single part
            return [{
                'number': 1,
                'title': 'Form Data',
                'description': 'All form fields',
                'text': pdf_text,
                'estimated_fields': 20,
                'complexity': 'medium'
            }]
    
    async def _extract_fields_intelligently(self, part_text: str, part_number: int, smart_form: SmartForm) -> List[SmartField]:
        """Extract fields with advanced AI analysis"""
        
        # Truncate if too long
        if len(part_text) > 8000:
            part_text = part_text[:8000] + "\n[...truncated...]"
        
        prompt = f"""
        You are an expert USCIS form field extractor. Extract ALL fields from Part {part_number} of form {smart_form.form_number}.
        
        Field Numbering Rules:
        - Use proper sequential numbering: 1.a, 1.b, 1.c, 2.a, 2.b, etc.
        - Maintain logical grouping within questions
        - Follow standard USCIS numbering conventions
        
        Field Analysis Requirements:
        - Extract ACTUAL VALUES, not database references
        - Determine precise field types
        - Assess extraction confidence
        - Identify semantic keywords
        - Note dependencies between fields
        - Determine if field is required
        
        Return ONLY valid JSON:
        {{
            "fields": [
                {{
                    "field_number": "1.a",
                    "field_label": "Family Name (Last Name)",
                    "field_value": "extracted_value_or_empty",
                    "field_type": "text|date|checkbox|radio|number|email|phone|address|ssn|alien_number",
                    "sequence_order": 0,
                    "extraction_confidence": 0.85,
                    "semantic_keywords": ["name", "family", "last"],
                    "is_required": true,
                    "dependencies": [],
                    "regex_pattern": null,
                    "format_mask": null
                }}
            ]
        }}
        
        Part {part_number} text:
        {part_text}
        """
        
        try:
            response = await self._call_openai_async(prompt, model="gpt-4o", max_tokens=4000)
            data = self._parse_json_response(response)
            
            fields = []
            for i, field_data in enumerate(data.get('fields', [])):
                # Determine field type enum
                field_type_str = field_data.get('field_type', 'text')
                try:
                    field_type = FieldType(field_type_str)
                except ValueError:
                    field_type = FieldType.TEXT
                
                field = SmartField(
                    field_number=field_data.get('field_number', f"{part_number}.{chr(97+i)}"),
                    field_label=field_data.get('field_label', ''),
                    field_value=field_data.get('field_value', ''),
                    field_type=field_type,
                    part_number=part_number,
                    sequence_order=field_data.get('sequence_order', i),
                    extraction_confidence=field_data.get('extraction_confidence', 0.5),
                    semantic_keywords=field_data.get('semantic_keywords', []),
                    is_required=field_data.get('is_required', False),
                    dependencies=field_data.get('dependencies', []),
                    regex_pattern=field_data.get('regex_pattern'),
                    format_mask=field_data.get('format_mask')
                )
                
                # Add AI insights
                if field.extraction_confidence >= 0.8:
                    field.add_insight(AIInsight(
                        insight_type="high_confidence",
                        confidence=field.extraction_confidence,
                        description=f"High confidence extraction for {field.field_label}",
                        action_recommended="proceed_with_mapping"
                    ))
                
                fields.append(field)
            
            return fields
            
        except Exception as e:
            logger.error(f"Field extraction failed for Part {part_number}: {e}")
            return []
    
    async def _apply_intelligent_mapping(self, smart_form: SmartForm):
        """Apply intelligent mapping using AI and semantic search"""
        
        for field in smart_form.get_all_fields():
            if field.is_mapped:
                continue
            
            # Get mapping suggestions
            suggestions = await self._get_mapping_suggestions(field)
            
            if suggestions:
                # Apply best suggestion if confidence is high enough
                best_suggestion = suggestions[0]
                
                if best_suggestion['confidence'] >= 0.85:
                    field.is_mapped = True
                    field.db_object = best_suggestion['db_object']
                    field.db_path = best_suggestion['db_path']
                    field.db_type = best_suggestion.get('db_type', 'TextBox')
                    field.mapping_confidence = best_suggestion['confidence']
                    
                    field.add_insight(AIInsight(
                        insight_type="auto_mapped",
                        confidence=best_suggestion['confidence'],
                        description=f"Automatically mapped to {field.db_object}.{field.db_path}",
                        action_recommended="validate_mapping"
                    ))
                
                # Store alternative mappings
                field.alternative_mappings = suggestions[1:4]  # Top 3 alternatives
    
    async def _get_mapping_suggestions(self, field: SmartField) -> List[Dict[str, Any]]:
        """Get intelligent mapping suggestions for a field"""
        
        suggestions = []
        
        # Method 1: Semantic similarity (if available)
        if self.semantic_model and self.field_embeddings:
            semantic_suggestions = self._get_semantic_suggestions(field)
            suggestions.extend(semantic_suggestions)
        
        # Method 2: Keyword and pattern matching
        pattern_suggestions = self._get_pattern_suggestions(field)
        suggestions.extend(pattern_suggestions)
        
        # Method 3: AI-powered analysis
        ai_suggestions = await self._get_ai_suggestions(field)
        suggestions.extend(ai_suggestions)
        
        # Deduplicate and sort by confidence
        unique_suggestions = {}
        for suggestion in suggestions:
            key = f"{suggestion['db_object']}.{suggestion['db_path']}"
            if key not in unique_suggestions or suggestion['confidence'] > unique_suggestions[key]['confidence']:
                unique_suggestions[key] = suggestion
        
        sorted_suggestions = sorted(unique_suggestions.values(), key=lambda x: x['confidence'], reverse=True)
        return sorted_suggestions[:10]  # Top 10 suggestions
    
    def _get_semantic_suggestions(self, field: SmartField) -> List[Dict[str, Any]]:
        """Get suggestions using semantic similarity"""
        
        if not self.semantic_model or not self.field_embeddings:
            return []
        
        try:
            # Create query from field information
            query = f"{field.field_label} {' '.join(field.semantic_keywords)}"
            query_embedding = self.semantic_model.encode([query])
            
            # Calculate similarities
            similarities = np.dot(self.field_embeddings['embeddings'], query_embedding.T).flatten()
            
            # Get top matches
            top_indices = np.argsort(similarities)[-10:][::-1]
            
            suggestions = []
            for idx in top_indices:
                if similarities[idx] > 0.3:  # Minimum similarity threshold
                    metadata = self.field_embeddings['metadata'][idx]
                    suggestions.append({
                        'db_object': metadata['object'],
                        'db_path': metadata['path'],
                        'confidence': float(similarities[idx]),
                        'method': 'semantic',
                        'db_type': self._infer_db_type(field.field_type)
                    })
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Semantic suggestions failed: {e}")
            return []
    
    def _get_pattern_suggestions(self, field: SmartField) -> List[Dict[str, Any]]:
        """Get suggestions using pattern and keyword matching"""
        
        suggestions = []
        field_label_lower = field.field_label.lower()
        field_keywords = [kw.lower() for kw in field.semantic_keywords]
        
        for obj_name, obj_schema in UNIVERSAL_DB_SCHEMA.items():
            for field_path, field_info in self._flatten_schema(obj_schema, obj_name):
                score = 0.0
                
                # Keyword matching
                db_keywords = [kw.lower() for kw in field_info.get('keywords', [])]
                common_keywords = set(field_keywords) & set(db_keywords)
                if common_keywords:
                    score += len(common_keywords) * 0.3
                
                # Pattern matching
                patterns = field_info.get('patterns', [])
                for pattern in patterns:
                    if re.search(pattern, field_label_lower, re.IGNORECASE):
                        score += 0.4
                
                # Direct label matching
                for keyword in db_keywords:
                    if keyword in field_label_lower:
                        score += 0.2
                
                # Field type matching
                expected_type = field_info.get('type', 'string')
                if self._types_compatible(field.field_type, expected_type):
                    score += 0.1
                
                if score > 0.3:
                    suggestions.append({
                        'db_object': obj_name,
                        'db_path': field_path.split('.', 1)[1] if '.' in field_path else field_path,
                        'confidence': min(score, 1.0),
                        'method': 'pattern',
                        'db_type': self._infer_db_type(field.field_type)
                    })
        
        return suggestions
    
    async def _get_ai_suggestions(self, field: SmartField) -> List[Dict[str, Any]]:
        """Get suggestions using AI analysis"""
        
        # Prepare schema summary for AI
        schema_summary = {}
        for obj_name, obj_schema in UNIVERSAL_DB_SCHEMA.items():
            schema_summary[obj_name] = list(self._flatten_schema(obj_schema, obj_name))[:10]  # Limit for token count
        
        prompt = f"""
        You are an expert at mapping USCIS form fields to database objects. 
        
        Field to map:
        - Number: {field.field_number}
        - Label: {field.field_label}
        - Type: {field.field_type.value}
        - Keywords: {field.semantic_keywords}
        - Value: {field.field_value[:50]}...
        
        Available database schema (partial):
        {json.dumps(schema_summary, indent=2)}
        
        Provide mapping suggestions in JSON format:
        {{
            "suggestions": [
                {{
                    "db_object": "object_name",
                    "db_path": "path.to.field",
                    "confidence": 0.85,
                    "reasoning": "explanation"
                }}
            ]
        }}
        
        Consider:
        1. Semantic meaning of field label
        2. Field type compatibility
        3. Common USCIS form patterns
        4. Context from field number and position
        """
        
        try:
            response = await self._call_openai_async(prompt, model="gpt-4o-mini", max_tokens=1000)
            data = self._parse_json_response(response)
            
            suggestions = []
            for suggestion in data.get('suggestions', []):
                suggestions.append({
                    'db_object': suggestion.get('db_object', ''),
                    'db_path': suggestion.get('db_path', ''),
                    'confidence': suggestion.get('confidence', 0.5),
                    'method': 'ai_analysis',
                    'reasoning': suggestion.get('reasoning', ''),
                    'db_type': self._infer_db_type(field.field_type)
                })
            
            return suggestions
            
        except Exception as e:
            logger.error(f"AI suggestions failed: {e}")
            return []
    
    async def _validate_and_enhance(self, smart_form: SmartForm):
        """Validate and enhance the form with quality checks"""
        
        # Validate field values
        for field in smart_form.get_all_fields():
            validation = await self._validate_field(field)
            field.validation_result = validation
            
            if not validation.is_valid:
                field.add_insight(AIInsight(
                    insight_type="validation_warning",
                    confidence=0.8,
                    description=f"Validation issues: {', '.join(validation.issues)}",
                    action_recommended="review_and_correct"
                ))
        
        # Calculate overall metrics
        smart_form.calculate_metrics()
        
        # Generate processing insights
        await self._generate_processing_insights(smart_form)
    
    async def _validate_field(self, field: SmartField) -> ValidationResult:
        """Validate a single field"""
        
        issues = []
        suggestions = []
        score = 1.0
        
        # Type-specific validation
        if field.field_type == FieldType.EMAIL and field.field_value:
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, field.field_value):
                issues.append("Invalid email format")
                suggestions.append("Check email format")
                score -= 0.3
        
        elif field.field_type == FieldType.PHONE and field.field_value:
            # Remove all non-digits
            digits_only = re.sub(r'\D', '', field.field_value)
            if len(digits_only) not in [10, 11]:
                issues.append("Invalid phone number length")
                suggestions.append("Check phone number format")
                score -= 0.3
        
        elif field.field_type == FieldType.SSN and field.field_value:
            ssn_digits = re.sub(r'\D', '', field.field_value)
            if len(ssn_digits) != 9:
                issues.append("Invalid SSN format")
                suggestions.append("SSN should be 9 digits")
                score -= 0.5
        
        elif field.field_type == FieldType.DATE and field.field_value:
            try:
                pd.to_datetime(field.field_value)
            except:
                issues.append("Invalid date format")
                suggestions.append("Use MM/DD/YYYY format")
                score -= 0.3
        
        # Required field validation
        if field.is_required and not field.field_value.strip():
            issues.append("Required field is empty")
            suggestions.append("This field must be filled")
            score -= 0.5
        
        # Confidence validation
        if field.extraction_confidence < 0.5:
            issues.append("Low extraction confidence")
            suggestions.append("Consider manual review")
            score -= 0.2
        
        return ValidationResult(
            is_valid=len(issues) == 0,
            score=max(score, 0.0),
            issues=issues,
            suggestions=suggestions
        )
    
    async def _generate_processing_insights(self, smart_form: SmartForm):
        """Generate overall processing insights"""
        
        all_fields = smart_form.get_all_fields()
        mapped_fields = smart_form.get_mapped_fields()
        
        # Mapping coverage insight
        mapping_coverage = len(mapped_fields) / len(all_fields) if all_fields else 0
        if mapping_coverage < 0.7:
            smart_form.ai_analysis['low_mapping_coverage'] = {
                'issue': 'Low mapping coverage',
                'coverage': mapping_coverage,
                'recommendation': 'Review unmapped fields for potential database assignments'
            }
        
        # Confidence distribution
        confidences = [f.extraction_confidence for f in all_fields]
        low_confidence_count = sum(1 for c in confidences if c < 0.5)
        if low_confidence_count > len(all_fields) * 0.2:
            smart_form.ai_analysis['low_confidence_fields'] = {
                'issue': 'Many low confidence extractions',
                'count': low_confidence_count,
                'recommendation': 'Manual review recommended for low confidence fields'
            }
        
        # Validation issues
        validation_issues = []
        for field in all_fields:
            if field.validation_result and not field.validation_result.is_valid:
                validation_issues.extend(field.validation_result.issues)
        
        if validation_issues:
            smart_form.ai_analysis['validation_issues'] = {
                'issue': 'Field validation problems detected',
                'count': len(validation_issues),
                'recommendation': 'Address validation issues before final submission'
            }
    
    async def _call_openai_async(self, prompt: str, model: str = "gpt-4o", max_tokens: int = 2000) -> str:
        """Call OpenAI API with async support"""
        
        response = self.openai_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=max_tokens,
            timeout=30
        )
        
        return response.choices[0].message.content.strip()
    
    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """Parse JSON response with error handling"""
        
        try:
            # Clean up response
            if '```json' in response_text:
                response_text = response_text.split('```json')[1].split('```')[0]
            elif '```' in response_text:
                response_text = response_text.split('```')[1].split('```')[0]
            
            return json.loads(response_text.strip())
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {e}")
            logger.error(f"Response text: {response_text}")
            return {}
    
    def _infer_db_type(self, field_type: FieldType) -> str:
        """Infer database type from field type"""
        
        type_mapping = {
            FieldType.TEXT: "TextBox",
            FieldType.DATE: "DateBox",
            FieldType.CHECKBOX: "CheckBox",
            FieldType.RADIO: "RadioBox",
            FieldType.NUMBER: "NumberBox",
            FieldType.EMAIL: "TextBox",
            FieldType.PHONE: "TextBox",
            FieldType.ADDRESS: "TextBox",
            FieldType.SSN: "TextBox",
            FieldType.ALIEN_NUMBER: "TextBox",
            FieldType.CURRENCY: "NumberBox"
        }
        
        return type_mapping.get(field_type, "TextBox")
    
    def _types_compatible(self, field_type: FieldType, db_type: str) -> bool:
        """Check if field type is compatible with database type"""
        
        compatible_types = {
            FieldType.TEXT: ["string"],
            FieldType.DATE: ["date"],
            FieldType.CHECKBOX: ["boolean"],
            FieldType.RADIO: ["boolean", "string"],
            FieldType.NUMBER: ["number", "string"],
            FieldType.EMAIL: ["email", "string"],
            FieldType.PHONE: ["phone", "string"],
            FieldType.ADDRESS: ["address", "string"],
            FieldType.SSN: ["ssn", "string"],
            FieldType.ALIEN_NUMBER: ["alien_number", "string"],
            FieldType.CURRENCY: ["currency", "number", "string"]
        }
        
        return db_type in compatible_types.get(field_type, ["string"])

# ===== PDF PROCESSING =====

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

def extract_pdf_text_enhanced(pdf_file) -> str:
    """Enhanced PDF text extraction with structure preservation"""
    try:
        st.info(f"📄 Processing file: {pdf_file.name}")
        
        pdf_file.seek(0)
        pdf_bytes = pdf_file.read()
        
        if len(pdf_bytes) == 0:
            st.error("❌ File is empty")
            return ""
        
        if not pdf_bytes.startswith(b'%PDF'):
            st.error("❌ Not a valid PDF file")
            return ""
        
        with safe_pdf_context(pdf_bytes) as doc:
            st.success(f"✅ PDF opened - {len(doc)} pages")
            
            full_text = ""
            for page_num in range(len(doc)):
                try:
                    page = doc[page_num]
                    page_text = page.get_text()
                    
                    if page_text.strip():
                        full_text += f"\n=== PAGE {page_num + 1} ===\n{page_text}\n"
                        
                except Exception as e:
                    st.warning(f"⚠️ Error on page {page_num + 1}: {str(e)}")
                    continue
            
            if not full_text.strip():
                st.error("❌ No text found")
                return ""
            
            return full_text
            
    except Exception as e:
        st.error(f"💥 PDF extraction failed: {str(e)}")
        return ""

# ===== INTELLIGENT UI COMPONENTS =====

def display_agent_status(processing_stage: ProcessingStage, progress_text: str = ""):
    """Display current agent processing status"""
    
    stage_info = {
        ProcessingStage.UPLOADED: {"icon": "📁", "text": "Ready for Processing"},
        ProcessingStage.ANALYZING: {"icon": "🔍", "text": "Analyzing Form Structure"},
        ProcessingStage.EXTRACTING: {"icon": "📄", "text": "Extracting Fields"},
        ProcessingStage.MAPPING: {"icon": "🧠", "text": "Applying Intelligent Mapping"},
        ProcessingStage.VALIDATING: {"icon": "✅", "text": "Validating Results"},
        ProcessingStage.COMPLETED: {"icon": "🎉", "text": "Processing Complete"},
        ProcessingStage.ERROR: {"icon": "❌", "text": "Processing Error"}
    }
    
    info = stage_info.get(processing_stage, {"icon": "🤖", "text": "Processing"})
    
    st.markdown(f"""
    <div class="agent-status">
        <h3>{info['icon']} Agentic USCIS Reader</h3>
        <p><strong>Status:</strong> {info['text']}</p>
        {f'<p><em>{progress_text}</em></p>' if progress_text else ''}
    </div>
    """, unsafe_allow_html=True)

def display_smart_field(field: SmartField, field_key: str):
    """Display smart field with AI insights"""
    
    # Determine status and styling
    if field.in_questionnaire:
        status_class = "field-questionnaire"
        status_icon = "📝"
        status_text = "Questionnaire"
    elif field.is_mapped:
        status_class = "field-mapped"
        status_icon = "🔗"
        status_text = "Mapped"
    else:
        status_class = "field-unmapped"
        status_icon = "❓"
        status_text = "Unmapped"
    
    st.markdown(f'<div class="field-intelligent {status_class}">', unsafe_allow_html=True)
    
    # Field header with confidence indicator
    col1, col2, col3 = st.columns([4, 2, 1])
    
    with col1:
        st.markdown(f"**{field.field_number}: {field.field_label}**")
        
        # Confidence bar
        confidence_width = field.extraction_confidence * 100
        st.markdown(f"""
        <div class="confidence-bar">
            <div class="confidence-fill" style="width: {confidence_width}%"></div>
        </div>
        <small>{field.get_confidence_color()} Confidence: {field.extraction_confidence:.0%}</small>
        """, unsafe_allow_html=True)
        
        if field.is_mapped:
            st.markdown(f'<small>📍 Mapped to: <code>{field.db_object}.{field.db_path}</code></small>', unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"{status_icon} **{status_text}**")
        if field.manually_edited:
            st.markdown("✏️ *User Edited*")
        if field.user_validated:
            st.markdown("✅ *Validated*")
    
    with col3:
        st.markdown(f"**{field.field_type.value}**")
        if field.is_required:
            st.markdown("🔴 *Required*")
    
    # Value editor
    col1, col2 = st.columns([3, 1])
    
    with col1:
        if field.field_type == FieldType.CHECKBOX:
            new_value = st.selectbox(
                "Value:",
                ["", "Yes", "No"],
                index=["", "Yes", "No"].index(field.field_value) if field.field_value in ["", "Yes", "No"] else 0,
                key=f"field_{field_key}",
                label_visibility="collapsed"
            )
        elif field.field_type == FieldType.DATE:
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
                key=f"date_{field_key}",
                label_visibility="collapsed"
            )
            new_value = str(date_input) if date_input else ""
        else:
            new_value = st.text_input(
                "Value:",
                value=field.field_value,
                placeholder=f"Enter {field.field_label.lower()}...",
                key=f"text_{field_key}",
                label_visibility="collapsed"
            )
        
        if new_value != field.field_value:
            field.field_value = new_value
            field.manually_edited = True
    
    with col2:
        # Action buttons
        if not field.is_mapped and not field.in_questionnaire:
            if st.button("🧠 Smart Map", key=f"smart_{field_key}", help="Use AI to map this field"):
                st.session_state[f"show_smart_mapping_{field_key}"] = True
                st.rerun()
        
        if st.button("📝 Questionnaire", key=f"quest_{field_key}", help="Move to questionnaire"):
            field.in_questionnaire = True
            field.is_mapped = False
            st.rerun()
    
    # AI Insights
    if field.ai_insights:
        st.markdown("**🧠 AI Insights:**")
        for insight in field.ai_insights[-2:]:  # Show last 2 insights
            st.markdown(f"""
            <div class="ai-suggestion">
                <strong>{insight.insight_type.replace('_', ' ').title()}:</strong> {insight.description}
                <br><small>Confidence: {insight.confidence:.0%} | Action: {insight.action_recommended}</small>
            </div>
            """, unsafe_allow_html=True)
    
    # Smart mapping interface
    if st.session_state.get(f"show_smart_mapping_{field_key}", False):
        display_smart_mapping_interface(field, field_key)
    
    # Validation results
    if field.validation_result and not field.validation_result.is_valid:
        st.markdown(f"""
        <div class="validation-error">
            <strong>⚠️ Validation Issues:</strong><br>
            {('<br>'.join(field.validation_result.issues))}
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

def display_smart_mapping_interface(field: SmartField, field_key: str):
    """Display smart mapping interface with AI suggestions"""
    
    st.markdown("#### 🧠 Smart Mapping Assistant")
    
    # Show alternative mappings if available
    if field.alternative_mappings:
        st.markdown("**AI Suggested Mappings:**")
        
        for i, mapping in enumerate(field.alternative_mappings[:3]):
            confidence = mapping.get('confidence', 0.0)
            confidence_color = "🟢" if confidence > 0.8 else "🟡" if confidence > 0.6 else "🟠"
            
            col1, col2, col3, col4 = st.columns([1, 2, 3, 1])
            
            with col1:
                st.write(f"{confidence_color} {confidence:.0%}")
            
            with col2:
                st.write(f"**{mapping['db_object']}**")
            
            with col3:
                st.write(f"`{mapping['db_path']}`")
                if 'reasoning' in mapping:
                    st.caption(mapping['reasoning'])
            
            with col4:
                if st.button("Apply", key=f"apply_mapping_{field_key}_{i}"):
                    field.is_mapped = True
                    field.db_object = mapping['db_object']
                    field.db_path = mapping['db_path']
                    field.db_type = mapping.get('db_type', 'TextBox')
                    field.mapping_confidence = confidence
                    field.in_questionnaire = False
                    
                    field.add_insight(AIInsight(
                        insight_type="user_mapped",
                        confidence=confidence,
                        description=f"User applied mapping to {field.db_object}.{field.db_path}",
                        action_recommended="validate_mapping"
                    ))
                    
                    st.session_state[f"show_smart_mapping_{field_key}"] = False
                    st.rerun()
    
    # Manual mapping option
    st.markdown("**Manual Database Selection:**")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Object selector
        selected_object = st.selectbox(
            "Database Object:",
            list(UNIVERSAL_DB_SCHEMA.keys()),
            key=f"manual_obj_{field_key}"
        )
        
        if selected_object:
            # Path selector
            paths = []
            for path, info in AgenticProcessor(None)._flatten_schema(UNIVERSAL_DB_SCHEMA[selected_object], selected_object):
                display_path = path.split('.', 1)[1] if '.' in path else path
                paths.append(display_path)
            
            selected_path = st.selectbox(
                "Field Path:",
                paths,
                key=f"manual_path_{field_key}"
            )
    
    with col2:
        st.write("") # Spacer
        if st.button("✅ Apply Manual Mapping", key=f"manual_apply_{field_key}"):
            field.is_mapped = True
            field.db_object = selected_object
            field.db_path = selected_path
            field.db_type = AgenticProcessor(None)._infer_db_type(field.field_type)
            field.mapping_confidence = 0.7  # Manual mapping confidence
            field.in_questionnaire = False
            
            field.add_insight(AIInsight(
                insight_type="manual_mapped",
                confidence=0.7,
                description=f"User manually mapped to {field.db_object}.{field.db_path}",
                action_recommended="validate_mapping"
            ))
            
            st.session_state[f"show_smart_mapping_{field_key}"] = False
            st.rerun()
        
        if st.button("❌ Cancel", key=f"cancel_mapping_{field_key}"):
            st.session_state[f"show_smart_mapping_{field_key}"] = False
            st.rerun()

def display_form_analysis(smart_form: SmartForm):
    """Display comprehensive form analysis"""
    
    st.markdown(f"""
    <div class="form-analysis">
        <h3>📊 Form Analysis: {smart_form.form_number}</h3>
        <p><strong>Title:</strong> {smart_form.form_title}</p>
        <p><strong>Edition:</strong> {smart_form.form_edition}</p>
        <p><strong>Processing Stage:</strong> {smart_form.processing_stage.value.title()}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Metrics grid
    col1, col2, col3, col4 = st.columns(4)
    
    all_fields = smart_form.get_all_fields()
    mapped_fields = smart_form.get_mapped_fields()
    unmapped_fields = smart_form.get_unmapped_fields()
    questionnaire_fields = smart_form.get_questionnaire_fields()
    
    with col1:
        st.metric("Total Fields", len(all_fields))
    
    with col2:
        st.metric("Mapped", len(mapped_fields), delta=f"{len(mapped_fields)/len(all_fields)*100:.0f}%" if all_fields else "0%")
    
    with col3:
        st.metric("Questionnaire", len(questionnaire_fields))
    
    with col4:
        st.metric("Overall Confidence", f"{smart_form.overall_confidence:.0%}")
    
    # Progress visualization
    if all_fields:
        progress = (len(mapped_fields) + len(questionnaire_fields)) / len(all_fields)
        st.progress(progress)
        st.caption(f"Processing Progress: {progress:.0%}")
    
    # AI Analysis insights
    if smart_form.ai_analysis:
        st.markdown("### 🧠 AI Analysis")
        
        for analysis_key, analysis_data in smart_form.ai_analysis.items():
            if isinstance(analysis_data, dict) and 'issue' in analysis_data:
                st.markdown(f"""
                <div class="validation-error">
                    <strong>⚠️ {analysis_data['issue']}</strong><br>
                    {analysis_data.get('recommendation', '')}
                </div>
                """, unsafe_allow_html=True)

def display_smart_form(smart_form: SmartForm):
    """Display smart form with all enhancements"""
    
    if not smart_form or not smart_form.parts:
        st.warning("No form data to display")
        return
    
    # Form analysis header
    display_form_analysis(smart_form)
    
    # Parts display
    for part_num in sorted(smart_form.parts.keys()):
        part = smart_form.parts[part_num]
        
        # Part header with metrics
        mapped_count = len(part.get_mapped_fields())
        unmapped_count = len(part.get_unmapped_fields())
        questionnaire_count = len(part.get_questionnaire_fields())
        
        with st.expander(f"📄 Part {part.number}: {part.title}", expanded=(part_num == 1)):
            
            if part.description:
                st.markdown(f"*{part.description}*")
            
            # Part metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Fields", len(part.fields))
            with col2:
                st.metric("Mapped", mapped_count)
            with col3:
                st.metric("Questionnaire", questionnaire_count)
            with col4:
                st.metric("Completion", f"{part.completion_score:.0%}")
            
            # Display fields
            if not part.fields:
                st.info("No fields found in this part")
                continue
            
            for i, field in enumerate(part.fields):
                display_smart_field(field, f"{part_num}_{i}")

def display_intelligent_export(smart_form: SmartForm):
    """Display intelligent export options"""
    
    st.markdown("## 📤 Intelligent Export")
    
    if not smart_form or not smart_form.parts:
        st.warning("No data to export")
        return
    
    # Export readiness check
    all_fields = smart_form.get_all_fields()
    mapped_fields = smart_form.get_mapped_fields()
    questionnaire_fields = smart_form.get_questionnaire_fields()
    processed_fields = len(mapped_fields) + len(questionnaire_fields)
    
    readiness_score = processed_fields / len(all_fields) if all_fields else 0
    
    if readiness_score >= 0.9:
        st.markdown(f"""
        <div class="export-ready">
            🎉 Form Ready for Export! ({readiness_score:.0%} processed)
        </div>
        """, unsafe_allow_html=True)
    else:
        st.warning(f"⚠️ Form {readiness_score:.0%} processed. Consider mapping more fields before export.")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("### 🔗 TypeScript Mappings")
        st.info(f"Ready: {len(mapped_fields)} mapped fields")
        
        if st.button("📥 Generate TypeScript", type="primary"):
            ts_content = generate_enhanced_typescript(mapped_fields, smart_form)
            
            st.code(ts_content, language="typescript")
            
            st.download_button(
                label="💾 Download TypeScript",
                data=ts_content,
                file_name=f"{smart_form.form_number.replace('-', '')}_mappings.ts",
                mime="text/typescript"
            )
    
    with col2:
        st.markdown("### 📝 JSON Questionnaire")
        st.info(f"Ready: {len(questionnaire_fields)} questionnaire fields")
        
        if st.button("📋 Generate JSON", type="primary"):
            json_content = generate_enhanced_json(questionnaire_fields, smart_form)
            
            st.code(json_content, language="json")
            
            st.download_button(
                label="💾 Download JSON",
                data=json_content,
                file_name=f"{smart_form.form_number.replace('-', '')}_questionnaire.json",
                mime="application/json"
            )
    
    with col3:
        st.markdown("### 📦 Complete Form Data")
        st.info("Comprehensive export with AI insights")
        
        if st.button("📦 Generate Complete Export", type="primary"):
            complete_data = generate_complete_export(smart_form)
            
            st.download_button(
                label="💾 Download Complete Data",
                data=complete_data,
                file_name=f"{smart_form.form_number.replace('-', '')}_complete.json",
                mime="application/json"
            )

# ===== ENHANCED EXPORT FUNCTIONS =====

def generate_enhanced_typescript(mapped_fields: List[SmartField], smart_form: SmartForm) -> str:
    """Generate enhanced TypeScript with AI insights"""
    
    ts_content = f"""/**
 * Auto-generated TypeScript mappings for {smart_form.form_number}
 * Generated by Agentic USCIS Reader
 * Form: {smart_form.form_title}
 * Processing Date: {datetime.now().isoformat()}
 * Overall Confidence: {smart_form.overall_confidence:.0%}
 */

export interface {smart_form.form_number.replace('-', '')}Mapping {{
"""
    
    # Group by database object
    objects = {}
    for field in mapped_fields:
        if field.db_object not in objects:
            objects[field.db_object] = []
        objects[field.db_object].append(field)
    
    for obj_name, fields in objects.items():
        ts_content += f"\n  // {obj_name} mappings\n"
        ts_content += f"  {obj_name}: {{\n"
        
        for field in fields:
            ts_content += f"    \"{field.field_number}\": {{\n"
            ts_content += f"      path: \"{field.db_path}\",\n"
            ts_content += f"      value: \"{field.field_value}\",\n"
            ts_content += f"      type: \"{field.db_type}\",\n"
            ts_content += f"      confidence: {field.mapping_confidence:.2f},\n"
            ts_content += f"      fieldType: \"{field.field_type.value}\",\n"
            ts_content += f"      label: \"{field.field_label}\",\n"
            ts_content += f"      required: {str(field.is_required).lower()}\n"
            ts_content += f"    }},\n"
        
        ts_content += f"  }},\n"
    
    ts_content += "}\n\n"
    
    # Add utility functions
    ts_content += f"""
export const {smart_form.form_number.replace('-', '')}Utils = {{
  getFormInfo: () => ({{
    formNumber: "{smart_form.form_number}",
    formTitle: "{smart_form.form_title}",
    formEdition: "{smart_form.form_edition}",
    totalFields: {len(smart_form.get_all_fields())},
    mappedFields: {len(mapped_fields)},
    overallConfidence: {smart_form.overall_confidence:.2f}
  }}),
  
  validateMapping: (fieldNumber: string, value: string): boolean => {{
    // Add validation logic here
    return true;
  }},
  
  getMappingByFieldNumber: (fieldNumber: string) => {{
    // Implementation for field lookup
    return null;
  }}
}};
"""
    
    return ts_content

def generate_enhanced_json(questionnaire_fields: List[SmartField], smart_form: SmartForm) -> str:
    """Generate enhanced JSON questionnaire with AI insights"""
    
    questionnaire_data = {
        "form_info": {
            "form_number": smart_form.form_number,
            "form_title": smart_form.form_title,
            "form_edition": smart_form.form_edition,
            "generation_date": datetime.now().isoformat(),
            "total_questionnaire_fields": len(questionnaire_fields)
        },
        "questions": [],
        "metadata": {
            "processing_stage": smart_form.processing_stage.value,
            "overall_confidence": smart_form.overall_confidence,
            "ai_analysis": smart_form.ai_analysis
        }
    }
    
    for field in questionnaire_fields:
        question_data = {
            "field_number": field.field_number,
            "question": f"Please provide: {field.field_label}",
            "field_type": field.field_type.value,
            "current_value": field.field_value,
            "is_required": field.is_required,
            "part_number": field.part_number,
            "sequence_order": field.sequence_order,
            "extraction_confidence": field.extraction_confidence,
            "semantic_keywords": field.semantic_keywords,
            "validation_info": {
                "regex_pattern": field.regex_pattern,
                "format_mask": field.format_mask,
                "validation_required": field.is_required
            },
            "ai_insights": [
                {
                    "type": insight.insight_type,
                    "confidence": insight.confidence,
                    "description": insight.description,
                    "action": insight.action_recommended
                }
                for insight in field.ai_insights
            ],
            "alternative_mappings": field.alternative_mappings,
            "processing_notes": field.processing_notes
        }
        
        questionnaire_data["questions"].append(question_data)
    
    return json.dumps(questionnaire_data, indent=2)

def generate_complete_export(smart_form: SmartForm) -> str:
    """Generate complete form export with all data and AI insights"""
    
    complete_data = {
        "form_info": {
            "form_number": smart_form.form_number,
            "form_title": smart_form.form_title,
            "form_edition": smart_form.form_edition,
            "total_pages": smart_form.total_pages,
            "processing_stage": smart_form.processing_stage.value,
            "processing_time": smart_form.processing_time,
            "form_signature": smart_form.form_signature,
            "export_date": datetime.now().isoformat()
        },
        "metrics": {
            "overall_confidence": smart_form.overall_confidence,
            "validation_score": smart_form.validation_score,
            "completion_percentage": smart_form.completion_percentage,
            "total_fields": len(smart_form.get_all_fields()),
            "mapped_fields": len(smart_form.get_mapped_fields()),
            "unmapped_fields": len(smart_form.get_unmapped_fields()),
            "questionnaire_fields": len(smart_form.get_questionnaire_fields())
        },
        "ai_analysis": smart_form.ai_analysis,
        "parts": {},
        "all_fields": [],
        "processing_history": smart_form.processing_history
    }
    
    # Export all parts
    for part_num, part in smart_form.parts.items():
        complete_data["parts"][str(part_num)] = {
            "title": part.title,
            "description": part.description,
            "completion_score": part.completion_score,
            "validation_status": part.validation_status,
            "ai_analysis": part.ai_analysis,
            "field_count": len(part.fields)
        }
    
    # Export all fields with full detail
    for field in smart_form.get_all_fields():
        complete_data["all_fields"].append(field.to_dict())
    
    return json.dumps(complete_data, indent=2)

# ===== OPENAI CLIENT =====

def get_openai_client():
    """Get OpenAI client with enhanced error handling"""
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

# ===== MAIN APPLICATION =====

def main():
    st.markdown(
        '<div class="main-header">'
        '<h1>🤖 Agentic USCIS Form Reader</h1>'
        '<p>Fully autonomous AI-powered system for intelligent USCIS form processing</p>'
        '<p><em>Powered by GPT-4o, Semantic Search, and Advanced AI Agents</em></p>'
        '</div>', 
        unsafe_allow_html=True
    )
    
    # Check dependencies
    if not PYMUPDF_AVAILABLE or not OPENAI_AVAILABLE:
        st.error("❌ Missing required dependencies!")
        st.stop()
    
    # Initialize session state
    if 'smart_form' not in st.session_state:
        st.session_state.smart_form = None
    
    if 'processing_stage' not in st.session_state:
        st.session_state.processing_stage = ProcessingStage.UPLOADED
    
    # Get OpenAI client
    openai_client = get_openai_client()
    if not openai_client:
        st.error("❌ OpenAI client not available")
        st.stop()
    
    # Initialize agentic processor
    if 'agentic_processor' not in st.session_state:
        st.session_state.agentic_processor = AgenticProcessor(openai_client)
    
    # Display agent status
    display_agent_status(st.session_state.processing_stage)
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 🤖 Agentic Controls")
        
        if st.button("🆕 New Form"):
            st.session_state.smart_form = None
            st.session_state.processing_stage = ProcessingStage.UPLOADED
            st.rerun()
        
        if st.session_state.smart_form:
            smart_form = st.session_state.smart_form
            
            st.markdown("### 📊 Quick Stats")
            all_fields = smart_form.get_all_fields()
            mapped_fields = smart_form.get_mapped_fields()
            
            st.metric("Overall Confidence", f"{smart_form.overall_confidence:.0%}")
            st.metric("Completion", f"{smart_form.completion_percentage:.0%}")
            st.metric("Processing Stage", smart_form.processing_stage.value.title())
            
            # Quick actions
            st.markdown("### ⚡ Quick Actions")
            
            if st.button("🧠 Auto-Map High Confidence"):
                with st.spinner("Auto-mapping fields..."):
                    asyncio.run(auto_map_high_confidence_fields_async(smart_form))
                st.rerun()
            
            if st.button("📝 Move Unmapped to Questionnaire"):
                for field in smart_form.get_unmapped_fields():
                    field.in_questionnaire = True
                st.success("Moved all unmapped fields to questionnaire!")
                st.rerun()
            
            if st.button("✅ Validate All Fields"):
                with st.spinner("Validating fields..."):
                    asyncio.run(validate_all_fields_async(smart_form))
                st.rerun()
        
        # System info
        st.markdown("### 🔧 System Info")
        st.info(f"Semantic Search: {'✅' if SEMANTIC_SEARCH_AVAILABLE else '❌'}")
        st.info(f"PyMuPDF: {'✅' if PYMUPDF_AVAILABLE else '❌'}")
        st.info(f"OpenAI: {'✅' if OPENAI_AVAILABLE else '❌'}")
    
    # Main tabs
    tab1, tab2, tab3, tab4 = st.tabs(["🚀 Intelligent Processing", "✏️ Smart Editing", "📝 Questionnaire", "📤 Export"])
    
    with tab1:
        st.markdown("### 🚀 Upload & Intelligent Processing")
        
        uploaded_file = st.file_uploader(
            "Choose any USCIS form PDF",
            type=['pdf'],
            help="The agentic system can process any USCIS form intelligently"
        )
        
        if uploaded_file:
            st.success(f"✅ File: {uploaded_file.name}")
            
            col1, col2 = st.columns([3, 1])
            
            with col1:
                processing_mode = st.selectbox(
                    "Processing Mode:",
                    ["Fully Automatic", "Semi-Automatic", "Manual Review"],
                    help="Choose how much AI automation to apply"
                )
            
            with col2:
                st.write("") # Spacer
                process_button = st.button("🚀 Process with AI", type="primary")
            
            if process_button:
                # Progress tracking
                progress_placeholder = st.empty()
                
                def update_progress(text):
                    with progress_placeholder:
                        st.markdown(f"""
                        <div class="agent-thinking">
                            🤖 Agent Working: {text}
                        </div>
                        """, unsafe_allow_html=True)
                
                with st.spinner("🤖 Agentic processing in progress..."):
                    try:
                        # Extract PDF text
                        update_progress("📄 Extracting text from PDF...")
                        pdf_text = extract_pdf_text_enhanced(uploaded_file)
                        
                        if not pdf_text:
                            st.error("Cannot proceed without PDF text")
                            st.stop()
                        
                        # Process with agentic system
                        start_time = time.time()
                        
                        smart_form = asyncio.run(
                            st.session_state.agentic_processor.process_form_intelligently(
                                pdf_text, 
                                update_progress
                            )
                        )
                        
                        smart_form.processing_time = time.time() - start_time
                        
                        if smart_form and smart_form.parts:
                            st.session_state.smart_form = smart_form
                            st.session_state.processing_stage = ProcessingStage.COMPLETED
                            
                            progress_placeholder.empty()
                            
                            st.balloons()
                            st.success(f"🎉 Intelligent processing complete! Processed {len(smart_form.get_all_fields())} fields in {smart_form.processing_time:.1f}s")
                            
                            # Show quick results
                            col1, col2, col3, col4 = st.columns(4)
                            
                            with col1:
                                st.metric("Fields Extracted", len(smart_form.get_all_fields()))
                            with col2:
                                st.metric("Auto-Mapped", len(smart_form.get_mapped_fields()))
                            with col3:
                                st.metric("For Review", len(smart_form.get_unmapped_fields()))
                            with col4:
                                st.metric("Confidence", f"{smart_form.overall_confidence:.0%}")
                        else:
                            st.error("❌ Processing failed")
                    
                    except Exception as e:
                        st.error(f"💥 Processing error: {str(e)}")
                        logger.error(f"Processing error: {e}")
    
    with tab2:
        if st.session_state.smart_form:
            display_smart_form(st.session_state.smart_form)
        else:
            st.info("📄 No form loaded. Process a PDF in the first tab to begin smart editing.")
    
    with tab3:
        if st.session_state.smart_form:
            display_questionnaire_interface(st.session_state.smart_form)
        else:
            st.info("📝 No form loaded. Process a PDF to access the questionnaire.")
    
    with tab4:
        if st.session_state.smart_form:
            display_intelligent_export(st.session_state.smart_form)
        else:
            st.info("📤 No form loaded. Process a PDF to access export options.")

def display_questionnaire_interface(smart_form: SmartForm):
    """Display intelligent questionnaire interface"""
    
    st.markdown("## 📝 Intelligent Questionnaire")
    
    questionnaire_fields = smart_form.get_questionnaire_fields()
    
    if not questionnaire_fields:
        st.success("🎉 No fields in questionnaire! All fields are mapped or handled.")
        return
    
    st.info(f"Complete {len(questionnaire_fields)} questionnaire fields with AI assistance:")
    
    # Group by part
    fields_by_part = {}
    for field in questionnaire_fields:
        if field.part_number not in fields_by_part:
            fields_by_part[field.part_number] = []
        fields_by_part[field.part_number].append(field)
    
    # Display questionnaire by parts
    for part_num, fields in fields_by_part.items():
        part_title = smart_form.parts[part_num].title
        
        with st.expander(f"📄 Part {part_num}: {part_title}", expanded=True):
            
            for i, field in enumerate(fields):
                st.markdown(f"### {field.field_number}: {field.field_label}")
                
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    # Smart input based on field type
                    if field.field_type == FieldType.TEXT:
                        answer = st.text_input(
                            f"Enter {field.field_label.lower()}:",
                            value=field.field_value,
                            key=f"quest_text_{part_num}_{i}",
                            help=f"Field type: {field.field_type.value}"
                        )
                    elif field.field_type == FieldType.DATE:
                        answer = st.date_input(
                            f"Select date for {field.field_label}:",
                            key=f"quest_date_{part_num}_{i}",
                            help="Use MM/DD/YYYY format"
                        )
                        answer = str(answer) if answer else ""
                    elif field.field_type == FieldType.CHECKBOX:
                        answer = st.selectbox(
                            f"Select option for {field.field_label}:",
                            ["", "Yes", "No"],
                            key=f"quest_check_{part_num}_{i}"
                        )
                    elif field.field_type == FieldType.EMAIL:
                        answer = st.text_input(
                            f"Enter email for {field.field_label}:",
                            value=field.field_value,
                            placeholder="example@email.com",
                            key=f"quest_email_{part_num}_{i}"
                        )
                    elif field.field_type == FieldType.PHONE:
                        answer = st.text_input(
                            f"Enter phone number for {field.field_label}:",
                            value=field.field_value,
                            placeholder="(555) 123-4567",
                            key=f"quest_phone_{part_num}_{i}"
                        )
                    else:
                        answer = st.text_input(
                            f"Enter {field.field_label.lower()}:",
                            value=field.field_value,
                            key=f"quest_other_{part_num}_{i}"
                        )
                    
                    if answer != field.field_value:
                        field.field_value = answer
                        field.manually_edited = True
                
                with col2:
                    if field.is_required:
                        st.markdown("🔴 **Required**")
                    
                    st.caption(f"Type: {field.field_type.value}")
                    st.caption(f"Confidence: {field.extraction_confidence:.0%}")
                    
                    if st.button("🔙 Back to Form", key=f"back_to_form_{part_num}_{i}"):
                        field.in_questionnaire = False
                        st.rerun()
                
                # Show AI insights for questionnaire fields
                if field.ai_insights:
                    with st.expander("🧠 AI Insights", expanded=False):
                        for insight in field.ai_insights:
                            st.write(f"**{insight.insight_type.replace('_', ' ').title()}:** {insight.description}")
                
                st.markdown("---")

# ===== ASYNC UTILITY FUNCTIONS =====

async def auto_map_high_confidence_fields_async(smart_form: SmartForm):
    """Auto-map fields with high confidence asynchronously"""
    
    mapped_count = 0
    processor = st.session_state.agentic_processor
    
    for field in smart_form.get_unmapped_fields():
        if not field.in_questionnaire:
            suggestions = await processor._get_mapping_suggestions(field)
            
            if suggestions and suggestions[0]['confidence'] >= 0.85:
                best = suggestions[0]
                field.is_mapped = True
                field.db_object = best['db_object']
                field.db_path = best['db_path']
                field.db_type = best.get('db_type', 'TextBox')
                field.mapping_confidence = best['confidence']
                
                field.add_insight(AIInsight(
                    insight_type="auto_mapped_high_confidence",
                    confidence=best['confidence'],
                    description=f"Auto-mapped with high confidence to {field.db_object}.{field.db_path}",
                    action_recommended="validate"
                ))
                
                mapped_count += 1
    
    if mapped_count > 0:
        st.success(f"🎉 Auto-mapped {mapped_count} high-confidence fields!")

async def validate_all_fields_async(smart_form: SmartForm):
    """Validate all fields asynchronously"""
    
    processor = st.session_state.agentic_processor
    
    for field in smart_form.get_all_fields():
        validation = await processor._validate_field(field)
        field.validation_result = validation
        
        if not validation.is_valid:
            field.add_insight(AIInsight(
                insight_type="validation_warning",
                confidence=0.8,
                description=f"Validation issues found: {', '.join(validation.issues)}",
                action_recommended="review_and_correct"
            ))
    
    # Recalculate metrics
    smart_form.calculate_metrics()
    
    st.success("✅ All fields validated!")

if __name__ == "__main__":
    main()
