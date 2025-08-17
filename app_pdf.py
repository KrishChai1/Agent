#!/usr/bin/env python3
"""
🤖 AGENTIC USCIS FORM READER - FIXED VERSION
============================================

A fully autonomous AI-powered system that can intelligently read, parse, 
and map ANY USCIS form with minimal human intervention.

Fixed Issues:
- Simplified PDF part extraction
- Streamlined manual mapping interface
- Proper OpenAI integration
- Better error handling
- Improved agentic processing

Author: AI Assistant
Version: 2.0.0
"""

import os
import json
import re
import time
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum

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

# Enhanced CSS
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
    
    .field-card {
        background: white;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    
    .field-mapped {
        border-left: 4px solid #4caf50;
        background: #f1f8e9;
    }
    
    .field-unmapped {
        border-left: 4px solid #ff9800;
        background: #fff3e0;
    }
    
    .field-questionnaire {
        border-left: 4px solid #2196f3;
        background: #e3f2fd;
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
    
    .processing-stage {
        background: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        border-left: 4px solid #007bff;
    }
    
    .simple-mapping {
        background: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

# ===== DATA STRUCTURES =====

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

@dataclass
class SmartField:
    field_number: str
    field_label: str
    field_value: str = ""
    field_type: FieldType = FieldType.TEXT
    part_number: int = 1
    extraction_confidence: float = 0.0
    is_mapped: bool = False
    db_object: str = ""
    db_path: str = ""
    in_questionnaire: bool = False
    is_required: bool = False
    manually_edited: bool = False
    
    def get_confidence_color(self) -> str:
        if self.extraction_confidence >= 0.8:
            return "🟢"
        elif self.extraction_confidence >= 0.6:
            return "🟡"
        elif self.extraction_confidence >= 0.4:
            return "🟠"
        else:
            return "🔴"

@dataclass
class SmartPart:
    number: int
    title: str
    description: str = ""
    fields: List[SmartField] = field(default_factory=list)
    
    def add_field(self, field: SmartField):
        field.part_number = self.number
        self.fields.append(field)

@dataclass
class SmartForm:
    form_number: str
    form_title: str
    form_edition: str = ""
    parts: Dict[int, SmartPart] = field(default_factory=dict)
    processing_stage: ProcessingStage = ProcessingStage.UPLOADED
    overall_confidence: float = 0.0
    
    def add_part(self, part: SmartPart):
        self.parts[part.number] = part
        self.calculate_metrics()
    
    def get_all_fields(self) -> List[SmartField]:
        all_fields = []
        for part in sorted(self.parts.values(), key=lambda p: p.number):
            all_fields.extend(part.fields)
        return all_fields
    
    def get_mapped_fields(self) -> List[SmartField]:
        return [f for f in self.get_all_fields() if f.is_mapped and not f.in_questionnaire]
    
    def get_unmapped_fields(self) -> List[SmartField]:
        return [f for f in self.get_all_fields() if not f.is_mapped and not f.in_questionnaire]
    
    def get_questionnaire_fields(self) -> List[SmartField]:
        return [f for f in self.get_all_fields() if f.in_questionnaire]
    
    def calculate_metrics(self):
        all_fields = self.get_all_fields()
        if not all_fields:
            self.overall_confidence = 0.0
            return
        
        confidences = [f.extraction_confidence for f in all_fields]
        self.overall_confidence = np.mean(confidences) if confidences else 0.0

# ===== SIMPLIFIED DATABASE SCHEMA =====

DATABASE_OBJECTS = {
    "attorney": {
        "label": "Attorney Information",
        "description": "Legal representative details",
        "icon": "⚖️"
    },
    "beneficiary": {
        "label": "Beneficiary Information", 
        "description": "Primary applicant details",
        "icon": "👤"
    },
    "customer": {
        "label": "Company/Customer Information",
        "description": "Employer or petitioning organization",
        "icon": "🏢"
    },
    "lawfirm": {
        "label": "Law Firm Information",
        "description": "Law firm details and contacts",
        "icon": "🏛️"
    }
}

# Common field paths for each object
DATABASE_PATHS = {
    "attorney": [
        "firstName", "lastName", "middleName", "workPhone", "mobilePhone", 
        "emailAddress", "stateBarNumber", "addressStreet", "addressCity", 
        "addressState", "addressZip", "addressCountry"
    ],
    "beneficiary": [
        "beneficiaryFirstName", "beneficiaryLastName", "beneficiaryMiddleName",
        "beneficiaryGender", "beneficiaryDateOfBirth", "beneficiarySsn",
        "alienNumber", "beneficiaryCountryOfBirth", "beneficiaryCellNumber",
        "beneficiaryPrimaryEmailAddress", "addressStreet", "addressCity",
        "addressState", "addressZip", "addressCountry"
    ],
    "customer": [
        "customer_name", "customer_tax_id", "customer_website_url",
        "signatory_first_name", "signatory_last_name", "signatory_work_phone",
        "signatory_email_id", "address_street", "address_city", 
        "address_state", "address_zip", "address_country"
    ],
    "lawfirm": [
        "lawFirmName", "uscisOnlineAccountNumber", "lawFirmFein",
        "companyPhone", "addressStreet", "addressCity", "addressState",
        "addressZip", "addressCountry"
    ]
}

# ===== AGENTIC PROCESSOR =====

class AgenticProcessor:
    """Simplified agentic processor with proper OpenAI integration"""
    
    def __init__(self):
        self.openai_client = None
        self.setup_openai()
    
    def setup_openai(self):
        """Setup OpenAI client with proper error handling"""
        try:
            # Try to get API key from secrets
            if hasattr(st, 'secrets') and 'OPENAI_API_KEY' in st.secrets:
                api_key = st.secrets['OPENAI_API_KEY']
            else:
                # Fallback to environment variable
                api_key = os.getenv('OPENAI_API_KEY')
            
            if not api_key:
                st.error("🔑 OpenAI API key not found! Please add it to Streamlit secrets or environment variables.")
                return
            
            self.openai_client = openai.OpenAI(api_key=api_key)
            
            # Test the connection
            try:
                test_response = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": "Hello"}],
                    max_tokens=5
                )
                st.sidebar.success("🔑 OpenAI API connected!")
            except Exception as e:
                st.error(f"❌ OpenAI API test failed: {str(e)}")
                self.openai_client = None
                
        except Exception as e:
            st.error(f"❌ OpenAI setup failed: {str(e)}")
            self.openai_client = None
    
    def process_form_intelligently(self, pdf_text: str, progress_callback=None) -> SmartForm:
        """Main processing pipeline with proper error handling"""
        
        if not self.openai_client:
            st.error("❌ OpenAI client not available")
            return None
        
        try:
            # Stage 1: Form Analysis
            if progress_callback:
                progress_callback("🔍 Analyzing form structure...")
            
            form_info = self._analyze_form_structure(pdf_text)
            
            # Stage 2: Create Smart Form
            smart_form = SmartForm(
                form_number=form_info.get('form_number', 'Unknown'),
                form_title=form_info.get('form_title', 'Unknown Form'),
                form_edition=form_info.get('form_edition', ''),
                processing_stage=ProcessingStage.ANALYZING
            )
            
            # Stage 3: Extract Fields (Simplified)
            if progress_callback:
                progress_callback("📄 Extracting form fields...")
            
            fields = self._extract_fields_simplified(pdf_text)
            
            # Group fields into parts (simplified approach)
            current_part = SmartPart(number=1, title="Form Fields")
            
            for i, field in enumerate(fields):
                field.part_number = 1
                current_part.add_field(field)
            
            smart_form.add_part(current_part)
            
            # Stage 4: Apply intelligent mapping
            if progress_callback:
                progress_callback("🧠 Applying intelligent mapping...")
            
            self._apply_intelligent_mapping(smart_form)
            
            smart_form.processing_stage = ProcessingStage.COMPLETED
            smart_form.calculate_metrics()
            
            return smart_form
            
        except Exception as e:
            logger.error(f"Processing failed: {e}")
            st.error(f"❌ Processing error: {str(e)}")
            return None
    
    def _analyze_form_structure(self, pdf_text: str) -> Dict[str, Any]:
        """Analyze form structure using AI"""
        
        # Truncate text for API limits
        analysis_text = pdf_text[:4000]
        
        prompt = f"""
        Analyze this USCIS form and extract basic information.
        
        Return ONLY a JSON object with these fields:
        {{
            "form_number": "extracted_form_number",
            "form_title": "extracted_form_title", 
            "form_edition": "edition_date_if_found"
        }}
        
        Form text:
        {analysis_text}
        """
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=500
            )
            
            content = response.choices[0].message.content.strip()
            
            # Parse JSON response
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
            
            return json.loads(content.strip())
            
        except Exception as e:
            logger.error(f"Form analysis failed: {e}")
            return {
                'form_number': 'Unknown',
                'form_title': 'Unknown Form',
                'form_edition': ''
            }
    
    def _extract_fields_simplified(self, pdf_text: str) -> List[SmartField]:
        """Extract fields using simplified AI approach"""
        
        # Split text into chunks for processing
        chunks = self._split_text_into_chunks(pdf_text, 6000)
        all_fields = []
        
        for i, chunk in enumerate(chunks):
            try:
                fields = self._extract_fields_from_chunk(chunk, i + 1)
                all_fields.extend(fields)
            except Exception as e:
                logger.error(f"Failed to extract from chunk {i+1}: {e}")
                continue
        
        return all_fields
    
    def _split_text_into_chunks(self, text: str, max_size: int) -> List[str]:
        """Split text into manageable chunks"""
        words = text.split()
        chunks = []
        current_chunk = []
        current_size = 0
        
        for word in words:
            if current_size + len(word) > max_size and current_chunk:
                chunks.append(' '.join(current_chunk))
                current_chunk = [word]
                current_size = len(word)
            else:
                current_chunk.append(word)
                current_size += len(word) + 1
        
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        return chunks
    
    def _extract_fields_from_chunk(self, chunk: str, chunk_num: int) -> List[SmartField]:
        """Extract fields from a text chunk"""
        
        prompt = f"""
        Extract form fields from this USCIS form text chunk. Look for numbered fields, labels, and input areas.
        
        Return ONLY a JSON array of fields:
        [
            {{
                "field_number": "1.a",
                "field_label": "Family Name (Last Name)",
                "field_value": "extracted_value_or_empty_string",
                "field_type": "text",
                "is_required": true,
                "confidence": 0.85
            }}
        ]
        
        Field types can be: text, date, checkbox, radio, number, email, phone, address, ssn, alien_number
        
        Text chunk:
        {chunk}
        """
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content.strip()
            
            # Parse JSON response
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
            
            fields_data = json.loads(content.strip())
            
            fields = []
            for field_data in fields_data:
                try:
                    # Convert field type to enum
                    field_type_str = field_data.get('field_type', 'text')
                    try:
                        field_type = FieldType(field_type_str)
                    except ValueError:
                        field_type = FieldType.TEXT
                    
                    field = SmartField(
                        field_number=field_data.get('field_number', f'chunk_{chunk_num}_field'),
                        field_label=field_data.get('field_label', 'Unknown Field'),
                        field_value=field_data.get('field_value', ''),
                        field_type=field_type,
                        extraction_confidence=field_data.get('confidence', 0.5),
                        is_required=field_data.get('is_required', False)
                    )
                    
                    fields.append(field)
                    
                except Exception as e:
                    logger.error(f"Failed to create field from data: {e}")
                    continue
            
            return fields
            
        except Exception as e:
            logger.error(f"Field extraction failed: {e}")
            return []
    
    def _apply_intelligent_mapping(self, smart_form: SmartForm):
        """Apply intelligent mapping using AI"""
        
        for field in smart_form.get_all_fields():
            if field.is_mapped:
                continue
            
            # Use AI to suggest mapping
            suggestion = self._get_mapping_suggestion(field)
            
            if suggestion and suggestion.get('confidence', 0) > 0.8:
                field.is_mapped = True
                field.db_object = suggestion['db_object']
                field.db_path = suggestion['db_path']
    
    def _get_mapping_suggestion(self, field: SmartField) -> Dict[str, Any]:
        """Get AI mapping suggestion for a field"""
        
        # Create schema summary
        schema_summary = {}
        for obj_name, obj_info in DATABASE_OBJECTS.items():
            schema_summary[obj_name] = {
                'description': obj_info['description'],
                'sample_paths': DATABASE_PATHS[obj_name][:5]  # First 5 paths as examples
            }
        
        prompt = f"""
        Map this USCIS form field to the most appropriate database object and path.
        
        Field Information:
        - Number: {field.field_number}
        - Label: {field.field_label}
        - Type: {field.field_type.value}
        - Value: {field.field_value[:50]}
        
        Available Database Objects:
        {json.dumps(schema_summary, indent=2)}
        
        Return ONLY JSON:
        {{
            "db_object": "best_matching_object",
            "db_path": "best_matching_path",
            "confidence": 0.85,
            "reasoning": "why this mapping makes sense"
        }}
        
        If no good match exists, return confidence below 0.5.
        """
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=300
            )
            
            content = response.choices[0].message.content.strip()
            
            # Parse JSON response
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
            
            return json.loads(content.strip())
            
        except Exception as e:
            logger.error(f"Mapping suggestion failed: {e}")
            return None

# ===== PDF PROCESSING =====

def extract_pdf_text_enhanced(pdf_file) -> str:
    """Enhanced PDF text extraction"""
    try:
        st.info(f"📄 Processing: {pdf_file.name}")
        
        pdf_file.seek(0)
        pdf_bytes = pdf_file.read()
        
        if len(pdf_bytes) == 0:
            st.error("❌ File is empty")
            return ""
        
        if not pdf_bytes.startswith(b'%PDF'):
            st.error("❌ Not a valid PDF file")
            return ""
        
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        try:
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
            
            return full_text
            
        finally:
            doc.close()
            
    except Exception as e:
        st.error(f"💥 PDF extraction failed: {str(e)}")
        return ""

# ===== UI COMPONENTS =====

def display_agent_status(processing_stage: ProcessingStage, progress_text: str = ""):
    """Display agent status"""
    
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
    """Display smart field with simplified interface"""
    
    # Determine field status
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
    
    st.markdown(f'<div class="field-card {status_class}">', unsafe_allow_html=True)
    
    # Field header
    col1, col2, col3 = st.columns([4, 2, 1])
    
    with col1:
        st.markdown(f"**{field.field_number}: {field.field_label}**")
        
        # Confidence indicator
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
            try:
                date_val = pd.to_datetime(field.field_value).date() if field.field_value else None
            except:
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
        
        # Update field value if changed
        if new_value != field.field_value:
            field.field_value = new_value
            field.manually_edited = True
    
    with col2:
        # Action buttons
        if not field.is_mapped and not field.in_questionnaire:
            if st.button("🔗 Map", key=f"map_{field_key}", help="Map to database"):
                st.session_state[f"show_mapping_{field_key}"] = True
                st.rerun()
        
        if st.button("📝 Questionnaire", key=f"quest_{field_key}", help="Move to questionnaire"):
            field.in_questionnaire = True
            field.is_mapped = False
            st.rerun()
    
    # Simplified mapping interface
    if st.session_state.get(f"show_mapping_{field_key}", False):
        display_simplified_mapping_interface(field, field_key)
    
    st.markdown('</div>', unsafe_allow_html=True)

def display_simplified_mapping_interface(field: SmartField, field_key: str):
    """Display simplified mapping interface showing only database objects"""
    
    st.markdown('<div class="simple-mapping">', unsafe_allow_html=True)
    st.markdown("#### 🔗 Map to Database")
    
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        # Database object selector
        object_options = list(DATABASE_OBJECTS.keys())
        object_labels = [f"{DATABASE_OBJECTS[obj]['icon']} {DATABASE_OBJECTS[obj]['label']}" for obj in object_options]
        
        selected_idx = st.selectbox(
            "Select Database Object:",
            range(len(object_options)),
            format_func=lambda x: object_labels[x],
            key=f"obj_select_{field_key}"
        )
        
        selected_object = object_options[selected_idx]
        
        # Show object description
        st.caption(DATABASE_OBJECTS[selected_object]['description'])
    
    with col2:
        # Path selector for selected object
        available_paths = DATABASE_PATHS.get(selected_object, [])
        
        selected_path = st.selectbox(
            "Select Field Path:",
            available_paths,
            key=f"path_select_{field_key}"
        )
    
    with col3:
        st.write("") # Spacer
        if st.button("✅ Apply", key=f"apply_{field_key}"):
            field.is_mapped = True
            field.db_object = selected_object
            field.db_path = selected_path
            field.in_questionnaire = False
            
            st.session_state[f"show_mapping_{field_key}"] = False
            st.success(f"Mapped to {selected_object}.{selected_path}")
            st.rerun()
        
        if st.button("❌ Cancel", key=f"cancel_{field_key}"):
            st.session_state[f"show_mapping_{field_key}"] = False
            st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

def display_smart_form(smart_form: SmartForm):
    """Display smart form"""
    
    if not smart_form or not smart_form.parts:
        st.warning("No form data to display")
        return
    
    # Form summary
    st.markdown(f"## 📄 {smart_form.form_number}: {smart_form.form_title}")
    
    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    
    all_fields = smart_form.get_all_fields()
    mapped_fields = smart_form.get_mapped_fields()
    unmapped_fields = smart_form.get_unmapped_fields()
    questionnaire_fields = smart_form.get_questionnaire_fields()
    
    with col1:
        st.metric("Total Fields", len(all_fields))
    with col2:
        st.metric("Mapped", len(mapped_fields))
    with col3:
        st.metric("Questionnaire", len(questionnaire_fields))
    with col4:
        st.metric("Confidence", f"{smart_form.overall_confidence:.0%}")
    
    # Display fields by part
    for part_num in sorted(smart_form.parts.keys()):
        part = smart_form.parts[part_num]
        
        with st.expander(f"📄 {part.title}", expanded=True):
            if not part.fields:
                st.info("No fields found in this part")
                continue
            
            for i, field in enumerate(part.fields):
                display_smart_field(field, f"{part_num}_{i}")

def display_export_options(smart_form: SmartForm):
    """Display export options"""
    
    st.markdown("## 📤 Export Options")
    
    if not smart_form:
        st.warning("No form data to export")
        return
    
    mapped_fields = smart_form.get_mapped_fields()
    questionnaire_fields = smart_form.get_questionnaire_fields()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🔗 TypeScript Mappings")
        st.info(f"Ready: {len(mapped_fields)} mapped fields")
        
        if st.button("Generate TypeScript", type="primary"):
            ts_content = generate_typescript_mappings(smart_form, mapped_fields)
            st.code(ts_content, language="typescript")
            
            st.download_button(
                "Download TypeScript",
                ts_content,
                f"{smart_form.form_number}_mappings.ts",
                "text/typescript"
            )
    
    with col2:
        st.markdown("### 📝 JSON Questionnaire")
        st.info(f"Ready: {len(questionnaire_fields)} questionnaire fields")
        
        if st.button("Generate JSON", type="primary"):
            json_content = generate_json_questionnaire(smart_form, questionnaire_fields)
            st.code(json_content, language="json")
            
            st.download_button(
                "Download JSON",
                json_content,
                f"{smart_form.form_number}_questionnaire.json",
                "application/json"
            )

# ===== EXPORT FUNCTIONS =====

def generate_typescript_mappings(smart_form: SmartForm, mapped_fields: List[SmartField]) -> str:
    """Generate TypeScript mappings"""
    
    ts_content = f"""/**
 * TypeScript mappings for {smart_form.form_number}
 * Generated: {datetime.now().isoformat()}
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
        ts_content += f"  {obj_name}: {{\n"
        for field in fields:
            ts_content += f"    \"{field.field_number}\": {{\n"
            ts_content += f"      path: \"{field.db_path}\",\n"
            ts_content += f"      value: \"{field.field_value}\",\n"
            ts_content += f"      type: \"{field.field_type.value}\"\n"
            ts_content += f"    }},\n"
        ts_content += f"  }},\n"
    
    ts_content += "}\n"
    
    return ts_content

def generate_json_questionnaire(smart_form: SmartForm, questionnaire_fields: List[SmartField]) -> str:
    """Generate JSON questionnaire"""
    
    questionnaire = {
        "form_info": {
            "form_number": smart_form.form_number,
            "form_title": smart_form.form_title,
            "generation_date": datetime.now().isoformat()
        },
        "questions": []
    }
    
    for field in questionnaire_fields:
        question = {
            "field_number": field.field_number,
            "question": f"Please provide: {field.field_label}",
            "field_type": field.field_type.value,
            "current_value": field.field_value,
            "is_required": field.is_required
        }
        questionnaire["questions"].append(question)
    
    return json.dumps(questionnaire, indent=2)

# ===== MAIN APPLICATION =====

def main():
    st.markdown(
        '<div class="main-header">'
        '<h1>🤖 Agentic USCIS Form Reader</h1>'
        '<p>AI-powered system for intelligent USCIS form processing</p>'
        '</div>', 
        unsafe_allow_html=True
    )
    
    # Check dependencies
    if not PYMUPDF_AVAILABLE:
        st.error("❌ PyMuPDF not available! Install with: pip install pymupdf")
        st.stop()
    
    if not OPENAI_AVAILABLE:
        st.error("❌ OpenAI not available! Install with: pip install openai")
        st.stop()
    
    # Initialize session state
    if 'smart_form' not in st.session_state:
        st.session_state.smart_form = None
    
    if 'processing_stage' not in st.session_state:
        st.session_state.processing_stage = ProcessingStage.UPLOADED
    
    # Initialize processor
    if 'processor' not in st.session_state:
        st.session_state.processor = AgenticProcessor()
    
    # Display status
    display_agent_status(st.session_state.processing_stage)
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 🤖 Controls")
        
        if st.button("🆕 New Form"):
            st.session_state.smart_form = None
            st.session_state.processing_stage = ProcessingStage.UPLOADED
            st.rerun()
        
        # Show stats if form is loaded
        if st.session_state.smart_form:
            form = st.session_state.smart_form
            st.markdown("### 📊 Stats")
            st.metric("Fields", len(form.get_all_fields()))
            st.metric("Mapped", len(form.get_mapped_fields()))
            st.metric("Confidence", f"{form.overall_confidence:.0%}")
    
    # Main tabs
    tab1, tab2, tab3, tab4 = st.tabs(["🚀 Process", "✏️ Edit", "📝 Questionnaire", "📤 Export"])
    
    with tab1:
        st.markdown("### 🚀 Upload & Process")
        
        uploaded_file = st.file_uploader("Choose USCIS form PDF", type=['pdf'])
        
        if uploaded_file:
            st.success(f"✅ File: {uploaded_file.name}")
            
            if st.button("🚀 Process with AI", type="primary"):
                progress_placeholder = st.empty()
                
                def update_progress(text):
                    with progress_placeholder:
                        st.info(f"🤖 {text}")
                
                with st.spinner("Processing..."):
                    try:
                        # Extract PDF text
                        update_progress("Extracting PDF text...")
                        pdf_text = extract_pdf_text_enhanced(uploaded_file)
                        
                        if not pdf_text:
                            st.error("No text found in PDF")
                            st.stop()
                        
                        # Process with AI
                        smart_form = st.session_state.processor.process_form_intelligently(
                            pdf_text, update_progress
                        )
                        
                        if smart_form:
                            st.session_state.smart_form = smart_form
                            st.session_state.processing_stage = ProcessingStage.COMPLETED
                            
                            progress_placeholder.empty()
                            st.balloons()
                            st.success(f"🎉 Processing complete! Found {len(smart_form.get_all_fields())} fields")
                        else:
                            st.error("Processing failed")
                    
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
    
    with tab2:
        if st.session_state.smart_form:
            display_smart_form(st.session_state.smart_form)
        else:
            st.info("No form loaded. Process a PDF first.")
    
    with tab3:
        if st.session_state.smart_form:
            display_questionnaire_interface(st.session_state.smart_form)
        else:
            st.info("No form loaded. Process a PDF first.")
    
    with tab4:
        if st.session_state.smart_form:
            display_export_options(st.session_state.smart_form)
        else:
            st.info("No form loaded. Process a PDF first.")

def display_questionnaire_interface(smart_form: SmartForm):
    """Display questionnaire interface"""
    
    st.markdown("## 📝 Questionnaire")
    
    questionnaire_fields = smart_form.get_questionnaire_fields()
    
    if not questionnaire_fields:
        st.success("🎉 No fields in questionnaire!")
        return
    
    st.info(f"Complete {len(questionnaire_fields)} questionnaire fields:")
    
    for i, field in enumerate(questionnaire_fields):
        st.markdown(f"### {field.field_number}: {field.field_label}")
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            if field.field_type == FieldType.TEXT:
                answer = st.text_input(
                    f"Enter {field.field_label.lower()}:",
                    value=field.field_value,
                    key=f"quest_{i}"
                )
            elif field.field_type == FieldType.DATE:
                answer = st.date_input(
                    f"Select date:",
                    key=f"quest_date_{i}"
                )
                answer = str(answer) if answer else ""
            elif field.field_type == FieldType.CHECKBOX:
                answer = st.selectbox(
                    f"Select option:",
                    ["", "Yes", "No"],
                    key=f"quest_check_{i}"
                )
            else:
                answer = st.text_input(
                    f"Enter value:",
                    value=field.field_value,
                    key=f"quest_other_{i}"
                )
            
            if answer != field.field_value:
                field.field_value = answer
                field.manually_edited = True
        
        with col2:
            if field.is_required:
                st.markdown("🔴 **Required**")
            
            if st.button("🔙 Back", key=f"back_{i}"):
                field.in_questionnaire = False
                st.rerun()

if __name__ == "__main__":
    main()
