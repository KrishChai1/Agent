#!/usr/bin/env python3
"""
🤖 ADVANCED AGENTIC USCIS FORM READER
====================================

Completely rebuilt with:
- Advanced agentic AI for comprehensive field extraction
- Multi-page part handling
- Proper database object selection
- Sequential field processing
- Enhanced pattern recognition

Author: AI Assistant  
Version: 6.0.0 - ADVANCED AGENTIC
"""

import os
import json
import re
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
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
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Page config
st.set_page_config(
    page_title="🤖 Advanced Agentic USCIS Reader",
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
        padding: 2rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        text-align: center;
    }
    
    .field-card {
        background: white;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .field-mapped {
        border-left: 4px solid #4caf50;
        background: #f8fff8;
    }
    
    .field-unmapped {
        border-left: 4px solid #ff9800;
        background: #fff8f0;
    }
    
    .field-questionnaire {
        border-left: 4px solid #2196f3;
        background: #f0f8ff;
    }
    
    .mapping-section {
        background: #f8f9fa;
        padding: 1.5rem;
        border-radius: 8px;
        margin: 1rem 0;
        border: 1px solid #dee2e6;
    }
    
    .part-header {
        background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%);
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
        font-weight: bold;
    }
    
    .db-object-card {
        background: white;
        border: 2px solid #e0e0e0;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        cursor: pointer;
        transition: all 0.2s ease;
    }
    
    .db-object-card:hover {
        border-color: #667eea;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    
    .db-object-selected {
        border-color: #4caf50;
        background: #f8fff8;
    }
</style>
""", unsafe_allow_html=True)

# ===== DATA STRUCTURES =====

class ProcessingStage(Enum):
    UPLOADED = "uploaded"
    EXTRACTING = "extracting"
    COMPLETED = "completed"
    ERROR = "error"

class FieldType(Enum):
    TEXT = "text"
    DATE = "date"
    CHECKBOX = "checkbox"
    NUMBER = "number"
    EMAIL = "email"
    PHONE = "phone"
    ADDRESS = "address"
    SSN = "ssn"
    ALIEN_NUMBER = "alien_number"
    DROPDOWN = "dropdown"

@dataclass
class SmartField:
    field_number: str
    field_label: str
    field_value: str = ""
    field_type: FieldType = FieldType.TEXT
    part_number: int = 1
    page_number: int = 1
    sequence_order: int = 0
    is_mapped: bool = False
    db_object: str = ""
    db_path: str = ""
    in_questionnaire: bool = False
    is_required: bool = False
    manually_edited: bool = False
    
    def __str__(self):
        return f"{self.field_number}: {self.field_label}"

@dataclass
class SmartPart:
    number: int
    title: str
    description: str = ""
    page_start: int = 1
    page_end: int = 1
    fields: List[SmartField] = field(default_factory=list)
    
    def add_field(self, field: SmartField):
        field.part_number = self.number
        self.fields.append(field)
        # Sort fields by sequence order
        self.fields.sort(key=lambda x: x.sequence_order)

@dataclass
class SmartForm:
    form_number: str
    form_title: str
    form_edition: str = ""
    total_pages: int = 0
    parts: Dict[int, SmartPart] = field(default_factory=dict)
    processing_stage: ProcessingStage = ProcessingStage.UPLOADED
    
    def add_part(self, part: SmartPart):
        self.parts[part.number] = part
    
    def get_all_fields(self) -> List[SmartField]:
        all_fields = []
        for part in sorted(self.parts.values(), key=lambda p: p.number):
            all_fields.extend(sorted(part.fields, key=lambda f: f.sequence_order))
        return all_fields
    
    def get_mapped_fields(self) -> List[SmartField]:
        return [f for f in self.get_all_fields() if f.is_mapped and not f.in_questionnaire]
    
    def get_unmapped_fields(self) -> List[SmartField]:
        return [f for f in self.get_all_fields() if not f.is_mapped and not f.in_questionnaire]
    
    def get_questionnaire_fields(self) -> List[SmartField]:
        return [f for f in self.get_all_fields() if f.in_questionnaire]

# ===== ENHANCED DATABASE SCHEMA =====

DATABASE_OBJECTS = {
    "beneficiary": {
        "label": "Beneficiary/Applicant Information",
        "description": "Primary applicant personal details, address, and contact information",
        "icon": "👤",
        "color": "#4CAF50",
        "common_paths": [
            "beneficiaryFirstName",
            "beneficiaryLastName", 
            "beneficiaryMiddleName",
            "beneficiaryDateOfBirth",
            "beneficiarySsn",
            "alienNumber",
            "uscisOnlineAccount",
            "beneficiaryCountryOfBirth",
            "beneficiaryCitizenOfCountry",
            "beneficiaryCellNumber",
            "beneficiaryWorkNumber",
            "beneficiaryPrimaryEmailAddress",
            "homeAddress.addressStreet",
            "homeAddress.addressCity",
            "homeAddress.addressState",
            "homeAddress.addressZip",
            "homeAddress.addressCountry",
            "physicalAddress.addressStreet",
            "physicalAddress.addressCity",
            "physicalAddress.addressState",
            "physicalAddress.addressZip",
            "currentNonimmigrantStatus",
            "statusExpirationDate",
            "lastArrivalDate",
            "passportNumber",
            "passportCountry",
            "passportExpirationDate"
        ]
    },
    "attorney": {
        "label": "Attorney/Representative Information", 
        "description": "Legal representative details and law firm information",
        "icon": "⚖️",
        "color": "#2196F3",
        "common_paths": [
            "attorneyInfo.firstName",
            "attorneyInfo.lastName", 
            "attorneyInfo.middleName",
            "attorneyInfo.workPhone",
            "attorneyInfo.mobilePhone",
            "attorneyInfo.emailAddress",
            "attorneyInfo.stateBarNumber",
            "address.addressStreet",
            "address.addressCity",
            "address.addressState",
            "address.addressZip",
            "address.addressCountry",
            "lawfirmDetails.lawFirmName",
            "lawfirmDetails.lawFirmFein",
            "uscisRepresentation",
            "uscisOnlineAccountNumber"
        ]
    },
    "employer": {
        "label": "Employer/Petitioner Information",
        "description": "Employer or petitioning organization details",
        "icon": "🏢", 
        "color": "#FF9800",
        "common_paths": [
            "customer_name",
            "customer_tax_id",
            "customer_website_url",
            "signatory_first_name",
            "signatory_last_name", 
            "signatory_middle_name",
            "signatory_work_phone",
            "signatory_mobile_phone",
            "signatory_email_id",
            "signatory_job_title",
            "address_street",
            "address_city",
            "address_state",
            "address_zip",
            "address_country"
        ]
    },
    "case": {
        "label": "Case/Application Information",
        "description": "Case-specific details, application type, and processing information",
        "icon": "📋",
        "color": "#9C27B0",
        "common_paths": [
            "caseNumber",
            "receiptNumber",
            "filingDate",
            "priority",
            "status",
            "applicationType",
            "requestedStatus",
            "requestedDuration",
            "changeEffectiveDate",
            "schoolName",
            "sevisId",
            "i94Number",
            "travelDocumentNumber"
        ]
    }
}

# ===== ENHANCED PDF PROCESSING =====

def extract_pdf_text_enhanced(pdf_file) -> Tuple[str, Dict[int, str]]:
    """Enhanced PDF extraction with page-by-page text mapping"""
    try:
        st.info("📄 Processing PDF with enhanced extraction...")
        
        pdf_file.seek(0)
        pdf_bytes = pdf_file.read()
        
        if len(pdf_bytes) == 0:
            st.error("❌ File is empty")
            return "", {}
        
        if not pdf_bytes.startswith(b'%PDF'):
            st.error("❌ Not a valid PDF file")
            return "", {}
        
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        try:
            page_count = len(doc)
            st.success(f"✅ PDF opened - {page_count} pages detected")
            
            page_texts = {}
            full_text_parts = []
            
            for page_num in range(page_count):
                try:
                    page = doc[page_num]
                    
                    # Extract text with multiple methods for better coverage
                    text_dict = page.get_text("dict")
                    page_text = ""
                    
                    # Method 1: Structured extraction from text dict
                    if "blocks" in text_dict:
                        for block in text_dict["blocks"]:
                            if "lines" in block:
                                for line in block["lines"]:
                                    if "spans" in line:
                                        line_text = ""
                                        for span in line["spans"]:
                                            if "text" in span:
                                                line_text += span["text"]
                                        if line_text.strip():
                                            page_text += line_text + "\n"
                    
                    # Method 2: Fallback to simple extraction
                    if not page_text.strip():
                        page_text = page.get_text()
                    
                    # Method 3: Try different extraction modes
                    if not page_text.strip():
                        page_text = page.get_text("text")
                    
                    if page_text.strip():
                        page_number = page_num + 1
                        page_texts[page_number] = page_text
                        page_header = f"=== PAGE {page_number} ==="
                        full_text_parts.append(f"{page_header}\n{page_text}")
                        st.info(f"✅ Page {page_number}: {len(page_text)} characters extracted")
                    else:
                        st.warning(f"⚠️ No text found on page {page_num + 1}")
                        
                except Exception as e:
                    st.warning(f"⚠️ Error on page {page_num + 1}: {str(e)}")
                    continue
            
            full_text = "\n\n".join(full_text_parts)
            
            if not full_text.strip():
                st.error("❌ No text content found in PDF")
                return "", {}
            
            char_count = len(full_text)
            st.success(f"✅ Total extraction: {char_count} characters from {len(page_texts)} pages")
            return full_text, page_texts
            
        finally:
            doc.close()
            
    except Exception as e:
        st.error(f"💥 PDF extraction failed: {str(e)}")
        return "", {}

# ===== ADVANCED AGENTIC FORM PROCESSOR =====

class AdvancedAgenticProcessor:
    """Advanced agentic processor with enhanced AI capabilities"""
    
    def __init__(self):
        self.openai_client = None
        self.setup_openai()
    
    def setup_openai(self):
        """Setup OpenAI client with enhanced error handling"""
        try:
            api_key = None
            
            # Check multiple sources for API key
            if hasattr(st, 'secrets') and 'OPENAI_API_KEY' in st.secrets:
                api_key = st.secrets['OPENAI_API_KEY']
                st.sidebar.success("🔑 API key loaded from Streamlit secrets")
            elif os.getenv('OPENAI_API_KEY'):
                api_key = os.getenv('OPENAI_API_KEY')
                st.sidebar.success("🔑 API key loaded from environment")
            
            if not api_key:
                st.error("""
                🔑 **OpenAI API Key Required!**
                
                Add your API key in one of these ways:
                
                **Streamlit Secrets (.streamlit/secrets.toml):**
                ```
                OPENAI_API_KEY = "your-api-key-here"
                ```
                
                **Environment Variable:**
                ```
                export OPENAI_API_KEY="your-api-key-here"
                ```
                """)
                return
            
            # Initialize OpenAI client
            self.openai_client = openai.OpenAI(api_key=api_key)
            
            # Test the connection
            try:
                test_response = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": "test"}],
                    max_tokens=1
                )
                st.sidebar.success("✅ OpenAI API connection verified!")
            except Exception as e:
                st.error(f"❌ OpenAI API test failed: {str(e)}")
                self.openai_client = None
                
        except Exception as e:
            st.error(f"❌ OpenAI setup failed: {str(e)}")
            self.openai_client = None
    
    def process_form_advanced(self, full_text: str, page_texts: Dict[int, str], progress_callback=None) -> SmartForm:
        """Advanced form processing with multi-stage agentic approach"""
        
        if not self.openai_client:
            st.error("❌ OpenAI client not available")
            return None
        
        try:
            # Stage 1: Advanced form structure analysis
            if progress_callback:
                progress_callback("🔍 Stage 1: Analyzing form structure with advanced AI...")
            
            form_metadata = self._analyze_form_structure_advanced(full_text)
            
            if not form_metadata:
                st.error("❌ Failed to analyze form structure")
                return None
            
            # Stage 2: Create enhanced form object
            smart_form = SmartForm(
                form_number=form_metadata.get('form_number', 'Unknown'),
                form_title=form_metadata.get('form_title', 'Unknown Form'),
                form_edition=form_metadata.get('form_edition', ''),
                total_pages=len(page_texts),
                processing_stage=ProcessingStage.EXTRACTING
            )
            
            # Stage 3: Advanced part extraction with page mapping
            if progress_callback:
                progress_callback("📄 Stage 2: Extracting parts with page mapping...")
            
            parts_info = self._extract_parts_with_pages(full_text, page_texts)
            
            # Stage 4: Comprehensive field extraction per part
            if progress_callback:
                progress_callback("🔍 Stage 3: Comprehensive field extraction...")
            
            for part_info in parts_info:
                part_number = part_info.get('number', 1)
                part_title = part_info.get('title', f'Part {part_number}')
                page_start = part_info.get('page_start', 1)
                page_end = part_info.get('page_end', 1)
                
                if progress_callback:
                    progress_callback(f"📋 Processing {part_title} (Pages {page_start}-{page_end})")
                
                smart_part = SmartPart(
                    number=part_number,
                    title=part_title,
                    description=part_info.get('description', ''),
                    page_start=page_start,
                    page_end=page_end
                )
                
                # Extract all fields for this part across its pages
                part_fields = self._extract_part_fields_comprehensive(
                    part_info, page_texts, full_text
                )
                
                # Add fields to part with proper sequencing
                for field in part_fields:
                    smart_part.add_field(field)
                
                smart_form.add_part(smart_part)
            
            # Stage 5: Intelligent field mapping suggestions
            if progress_callback:
                progress_callback("🧠 Stage 4: Generating intelligent mapping suggestions...")
            
            self._apply_intelligent_mapping_suggestions(smart_form)
            
            smart_form.processing_stage = ProcessingStage.COMPLETED
            
            # Final validation
            total_fields = len(smart_form.get_all_fields())
            if total_fields == 0:
                st.warning("⚠️ No fields extracted. Creating fallback structure...")
                self._create_fallback_structure(smart_form, full_text)
            
            return smart_form
            
        except Exception as e:
            logger.error(f"Advanced processing failed: {e}")
            st.error(f"❌ Advanced processing error: {str(e)}")
            return None
    
    def _analyze_form_structure_advanced(self, full_text: str) -> Dict[str, Any]:
        """Advanced form structure analysis with enhanced AI"""
        
        # Use more text for better analysis
        analysis_text = full_text[:20000]
        
        prompt = f"""
        You are an expert USCIS form analyzer. Analyze this form text and extract comprehensive structure information.
        
        CRITICAL: Return ONLY valid JSON without any markdown, explanations, or extra text.
        
        Look for:
        1. Form number (I-539, I-129, I-90, G-28, etc.)
        2. Form title 
        3. Edition date
        4. All parts and their page ranges
        
        USCIS forms typically have parts like:
        - Part 1: Information About You
        - Part 2: Application Type
        - Part 3: Processing Information
        - Part 4: Additional Information
        - Part 5: Contact Information and Signature
        - Part 6: Interpreter Information
        - Part 7: Preparer Information
        - Part 8: Additional Information
        
        Return this exact JSON structure:
        {{
            "form_number": "I-539",
            "form_title": "Application to Extend/Change Nonimmigrant Status",
            "form_edition": "08/28/24",
            "total_pages": 7,
            "parts": [
                {{
                    "number": 1,
                    "title": "Information About You",
                    "description": "Personal information and contact details",
                    "page_start": 1,
                    "page_end": 2
                }},
                {{
                    "number": 2,
                    "title": "Application Type",
                    "description": "Type of application being filed",
                    "page_start": 2,
                    "page_end": 2
                }}
            ]
        }}
        
        Form text:
        {analysis_text}
        """
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",  # Use GPT-4 for better analysis
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content.strip()
            
            # Clean JSON response
            content = self._clean_json_response(content)
            
            data = json.loads(content)
            
            # Validate and ensure we have parts
            if not data.get('parts'):
                data['parts'] = self._get_default_parts()
            
            return data
            
        except Exception as e:
            logger.error(f"Form structure analysis failed: {e}")
            return self._get_fallback_form_metadata()
    
    def _extract_parts_with_pages(self, full_text: str, page_texts: Dict[int, str]) -> List[Dict[str, Any]]:
        """Extract parts with accurate page mapping"""
        
        parts_info = []
        
        # Analyze the full text to identify parts and their locations
        prompt = f"""
        Analyze this USCIS form and identify ALL parts with their page locations.
        
        Return ONLY a JSON array of parts:
        [
            {{
                "number": 1,
                "title": "Information About You",
                "description": "Personal information",
                "page_start": 1,
                "page_end": 2
            }},
            {{
                "number": 2,
                "title": "Application Type",
                "description": "Application details",
                "page_start": 2,
                "page_end": 2
            }}
        ]
        
        Look for part markers like "Part 1.", "Part 2.", etc.
        Determine which pages each part spans by looking at page markers.
        
        Form text (first 15000 chars):
        {full_text[:15000]}
        """
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=1500
            )
            
            content = response.choices[0].message.content.strip()
            content = self._clean_json_response(content)
            
            parts_info = json.loads(content)
            
            if not parts_info:
                parts_info = self._get_default_parts()
            
            return parts_info
            
        except Exception as e:
            logger.error(f"Parts extraction failed: {e}")
            return self._get_default_parts()
    
    def _extract_part_fields_comprehensive(self, part_info: Dict[str, Any], page_texts: Dict[int, str], full_text: str) -> List[SmartField]:
        """Comprehensive field extraction for a specific part"""
        
        part_number = part_info.get('number', 1)
        part_title = part_info.get('title', f'Part {part_number}')
        page_start = part_info.get('page_start', 1)
        page_end = part_info.get('page_end', 1)
        
        # Gather text from all pages that contain this part
        part_text_sections = []
        for page_num in range(page_start, page_end + 1):
            if page_num in page_texts:
                part_text_sections.append(f"PAGE {page_num}:\n{page_texts[page_num]}")
        
        part_text = "\n\n".join(part_text_sections)
        
        # Limit text size for API call
        if len(part_text) > 15000:
            part_text = part_text[:15000] + "\n[...text truncated...]"
        
        prompt = f"""
        You are an expert USCIS form field extractor. Extract ALL fields from Part {part_number}: {part_title}.
        
        CRITICAL: Return ONLY a valid JSON array without markdown or explanations.
        
        Look for these field patterns:
        1. Numbered items: "1.", "2.", "3.", etc.
        2. Sub-items: "1.a.", "1.b.", "2.a.", "2.b.", etc. 
        3. Name fields: "Family Name", "Given Name", "Middle Name"
        4. Address components: "Street Number and Name", "City", "State", "ZIP Code"
        5. Contact fields: "Daytime Telephone", "Mobile Telephone", "Email Address"
        6. ID fields: "A-Number", "Social Security Number", "USCIS Online Account"
        7. Date fields: "Date of Birth", "Date of Entry", etc.
        8. Yes/No questions and checkboxes
        9. Signature and date fields
        10. Dropdown selections
        
        For each field, determine:
        - Exact field number as it appears
        - Complete field label
        - Appropriate field type
        - Whether it appears required
        - Sequence order (1, 2, 3, etc.)
        
        Return this JSON array structure:
        [
            {{
                "field_number": "1.a.",
                "field_label": "Family Name (Last Name)",
                "field_type": "text",
                "is_required": true,
                "sequence_order": 1,
                "page_number": 1
            }},
            {{
                "field_number": "1.b.",
                "field_label": "Given Name (First Name)",
                "field_type": "text", 
                "is_required": true,
                "sequence_order": 2,
                "page_number": 1
            }}
        ]
        
        Valid field_type values: text, date, checkbox, number, email, phone, address, ssn, alien_number, dropdown
        
        Extract EVERY field you can find, maintaining the original sequence and numbering.
        
        Part {part_number} text:
        {part_text}
        """
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",  # Use GPT-4 for better field extraction
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=4000
            )
            
            content = response.choices[0].message.content.strip()
            content = self._clean_json_response(content)
            
            fields_data = json.loads(content)
            
            fields = []
            for i, field_data in enumerate(fields_data):
                try:
                    # Validate and create field
                    field_type_str = field_data.get('field_type', 'text')
                    try:
                        field_type = FieldType(field_type_str)
                    except ValueError:
                        field_type = FieldType.TEXT
                    
                    field = SmartField(
                        field_number=field_data.get('field_number', f'{part_number}.{i+1}'),
                        field_label=field_data.get('field_label', 'Unknown Field'),
                        field_value="",
                        field_type=field_type,
                        part_number=part_number,
                        page_number=field_data.get('page_number', page_start),
                        sequence_order=field_data.get('sequence_order', i + 1),
                        is_required=field_data.get('is_required', False)
                    )
                    
                    fields.append(field)
                    
                except Exception as e:
                    logger.error(f"Failed to create field {i} for part {part_number}: {e}")
                    continue
            
            if not fields:
                # Create fallback fields if extraction failed
                fields = self._create_fallback_fields_for_part(part_number, part_title)
            
            st.success(f"✅ Extracted {len(fields)} fields from Part {part_number}")
            return fields
            
        except Exception as e:
            logger.error(f"Field extraction failed for part {part_number}: {e}")
            st.warning(f"⚠️ Using fallback fields for Part {part_number}")
            return self._create_fallback_fields_for_part(part_number, part_title)
    
    def _apply_intelligent_mapping_suggestions(self, smart_form: SmartForm):
        """Apply intelligent mapping suggestions using advanced AI"""
        
        unmapped_fields = smart_form.get_unmapped_fields()
        
        if not unmapped_fields:
            return
        
        # Process fields in batches for intelligent mapping
        batch_size = 10
        for i in range(0, len(unmapped_fields), batch_size):
            batch = unmapped_fields[i:i+batch_size]
            self._process_mapping_batch(batch)
    
    def _process_mapping_batch(self, fields: List[SmartField]):
        """Process a batch of fields for intelligent mapping"""
        
        # Prepare field information for AI analysis
        fields_info = []
        for field in fields:
            field_info = {
                "number": field.field_number,
                "label": field.field_label,
                "type": field.field_type.value,
                "part": field.part_number
            }
            fields_info.append(field_info)
        
        # Prepare database schema info
        schema_info = {}
        for obj_name, obj_data in DATABASE_OBJECTS.items():
            schema_info[obj_name] = {
                "description": obj_data["description"],
                "common_paths": obj_data["common_paths"][:10]  # Limit for API call
            }
        
        prompt = f"""
        You are an expert in USCIS form-to-database mapping. Analyze these form fields and suggest the best database mappings.
        
        CRITICAL: Return ONLY a valid JSON array without markdown or explanations.
        
        Fields to map:
        {json.dumps(fields_info, indent=2)}
        
        Available database objects:
        {json.dumps(schema_info, indent=2)}
        
        Mapping rules:
        - beneficiary: Personal info (name, DOB, SSN, address, contact, status)
        - attorney: Legal representative info
        - employer: Company/petitioner info  
        - case: Application/case details
        
        Return this JSON array:
        [
            {{
                "field_number": "1.a.",
                "suggested_object": "beneficiary",
                "suggested_path": "beneficiaryLastName",
                "confidence": 0.95
            }}
        ]
        
        Only suggest mappings with confidence > 0.8.
        """
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content.strip()
            content = self._clean_json_response(content)
            
            suggestions = json.loads(content)
            
            # Apply high-confidence suggestions
            for suggestion in suggestions:
                if suggestion.get('confidence', 0) > 0.85:
                    field_number = suggestion.get('field_number')
                    
                    # Find the field and apply mapping
                    for field in fields:
                        if field.field_number == field_number:
                            field.is_mapped = True
                            field.db_object = suggestion.get('suggested_object', '')
                            field.db_path = suggestion.get('suggested_path', '')
                            break
            
        except Exception as e:
            logger.error(f"Intelligent mapping failed: {e}")
    
    def _clean_json_response(self, content: str) -> str:
        """Clean JSON response from AI"""
        
        # Remove markdown code blocks
        if '```json' in content:
            content = content.split('```json')[1].split('```')[0]
        elif '```' in content:
            content = content.split('```')[1].split('```')[0]
        
        # Find JSON object or array
        content = content.strip()
        
        # Fix common JSON issues
        content = re.sub(r',\s*}', '}', content)  # Remove trailing commas
        content = re.sub(r',\s*]', ']', content)  # Remove trailing commas
        
        return content
    
    def _get_default_parts(self) -> List[Dict[str, Any]]:
        """Get default parts structure"""
        return [
            {"number": 1, "title": "Information About You", "description": "Personal information", "page_start": 1, "page_end": 2},
            {"number": 2, "title": "Application Type", "description": "Application details", "page_start": 2, "page_end": 2},
            {"number": 3, "title": "Processing Information", "description": "Processing details", "page_start": 2, "page_end": 3},
            {"number": 4, "title": "Additional Information", "description": "Additional details", "page_start": 3, "page_end": 4},
            {"number": 5, "title": "Contact Information and Signature", "description": "Contact and certification", "page_start": 5, "page_end": 5}
        ]
    
    def _get_fallback_form_metadata(self) -> Dict[str, Any]:
        """Get fallback form metadata"""
        return {
            'form_number': 'Unknown',
            'form_title': 'USCIS Form',
            'form_edition': '',
            'total_pages': 1,
            'parts': self._get_default_parts()
        }
    
    def _create_fallback_fields_for_part(self, part_number: int, part_title: str) -> List[SmartField]:
        """Create fallback fields for a part"""
        
        fallback_templates = {
            1: [  # Part 1: Information About You
                ("1.a.", "Family Name (Last Name)", FieldType.TEXT),
                ("1.b.", "Given Name (First Name)", FieldType.TEXT),
                ("1.c.", "Middle Name", FieldType.TEXT),
                ("2.", "A-Number", FieldType.ALIEN_NUMBER),
                ("3.", "USCIS Online Account Number", FieldType.TEXT),
                ("4.", "Mailing Address - Street", FieldType.ADDRESS),
                ("5.", "Physical Address Same as Mailing", FieldType.CHECKBOX),
                ("7.", "Country of Birth", FieldType.TEXT),
                ("8.", "Country of Citizenship", FieldType.TEXT),
                ("9.", "Date of Birth", FieldType.DATE),
                ("10.", "U.S. Social Security Number", FieldType.SSN)
            ],
            2: [  # Part 2: Application Type
                ("1.", "Application Type", FieldType.CHECKBOX),
                ("2.", "Change of Status Details", FieldType.TEXT),
                ("3.", "Number of People in Application", FieldType.CHECKBOX),
                ("4.", "Change Effective Date", FieldType.DATE),
                ("5.", "School Name", FieldType.TEXT),
                ("6.", "SEVIS ID Number", FieldType.TEXT)
            ],
            3: [  # Part 3: Processing Information
                ("1.", "Requested Extension Date", FieldType.DATE),
                ("2.", "Based on Extension Granted to Family", FieldType.CHECKBOX),
                ("3.", "Based on Separate Petition", FieldType.CHECKBOX)
            ]
        }
        
        templates = fallback_templates.get(part_number, [
            (f"{part_number}.1", f"{part_title} - Field 1", FieldType.TEXT),
            (f"{part_number}.2", f"{part_title} - Field 2", FieldType.TEXT)
        ])
        
        fields = []
        for i, (field_num, field_label, field_type) in enumerate(templates):
            field = SmartField(
                field_number=field_num,
                field_label=field_label,
                field_value="",
                field_type=field_type,
                part_number=part_number,
                sequence_order=i + 1,
                is_required=False
            )
            fields.append(field)
        
        return fields
    
    def _create_fallback_structure(self, smart_form: SmartForm, full_text: str):
        """Create fallback structure when extraction fails"""
        
        # Create basic parts with fallback fields
        for part_info in self._get_default_parts():
            part_number = part_info['number']
            part_title = part_info['title']
            
            smart_part = SmartPart(
                number=part_number,
                title=part_title,
                description=part_info['description']
            )
            
            fallback_fields = self._create_fallback_fields_for_part(part_number, part_title)
            for field in fallback_fields:
                smart_part.add_field(field)
            
            smart_form.add_part(smart_part)

# ===== ENHANCED UI COMPONENTS =====

def display_field_enhanced(field: SmartField, field_key: str):
    """Enhanced field display with better mapping interface"""
    
    # Determine field status
    if field.in_questionnaire:
        status_class = "field-questionnaire"
        status_icon = "📝"
        status_text = "Questionnaire"
    elif field.is_mapped:
        status_class = "field-mapped"
        status_icon = "✅"
        status_text = "Mapped"
    else:
        status_class = "field-unmapped"
        status_icon = "❓"
        status_text = "Needs Mapping"
    
    st.markdown(f'<div class="field-card {status_class}">', unsafe_allow_html=True)
    
    # Field header with enhanced info
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.markdown(f"**{field.field_number}: {field.field_label}**")
        
        # Show additional field info
        field_info_parts = []
        if field.field_type != FieldType.TEXT:
            field_info_parts.append(f"Type: {field.field_type.value}")
        if field.page_number > 0:
            field_info_parts.append(f"Page: {field.page_number}")
        if field.is_required:
            field_info_parts.append("Required")
        
        if field_info_parts:
            st.caption(" • ".join(field_info_parts))
        
        if field.is_mapped:
            mapping_display = f"📍 **{field.db_object}** → `{field.db_path}`"
            st.markdown(mapping_display)
    
    with col2:
        st.markdown(f"{status_icon} **{status_text}**")
    
    # Value editor
    col1, col2 = st.columns([2, 1])
    
    with col1:
        if field.field_type == FieldType.CHECKBOX:
            checkbox_options = ["", "Yes", "No"]
            current_index = 0
            if field.field_value in checkbox_options:
                current_index = checkbox_options.index(field.field_value)
            
            new_value = st.selectbox(
                "Value:",
                checkbox_options,
                index=current_index,
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
                key=f"text_{field_key}",
                label_visibility="collapsed",
                placeholder=f"Enter {field.field_label.lower()}..."
            )
        
        # Update field value if changed
        if new_value != field.field_value:
            field.field_value = new_value
            field.manually_edited = True
    
    with col2:
        # Action buttons
        if st.button("🔗 Map", key=f"map_{field_key}", help="Map to database"):
            st.session_state[f"show_mapping_{field_key}"] = True
            st.rerun()
        
        if st.button("📝 Quest", key=f"quest_{field_key}", help="Move to questionnaire"):
            field.in_questionnaire = True
            field.is_mapped = False
            st.rerun()
    
    # Enhanced mapping interface
    if st.session_state.get(f"show_mapping_{field_key}", False):
        display_mapping_interface_enhanced(field, field_key)
    
    st.markdown('</div>', unsafe_allow_html=True)

def display_mapping_interface_enhanced(field: SmartField, field_key: str):
    """Enhanced mapping interface with prominent database object selection"""
    
    st.markdown('<div class="mapping-section">', unsafe_allow_html=True)
    st.markdown("### 🔗 Map Field to Database")
    
    # Show current mapping if exists
    if field.is_mapped:
        st.info(f"**Currently mapped to:** {field.db_object} → `{field.db_path}`")
    
    # Enhanced database object selection
    st.markdown("#### Step 1: Choose Database Object")
    
    # Create prominent database object cards
    db_objects = list(DATABASE_OBJECTS.keys())
    
    # Use columns for better layout
    cols = st.columns(2)
    
    selected_object = None
    
    for i, obj_key in enumerate(db_objects):
        obj_info = DATABASE_OBJECTS[obj_key]
        
        with cols[i % 2]:
            # Create a clickable card for each database object
            button_label = f"{obj_info['icon']} {obj_info['label']}"
            
            if st.button(
                button_label,
                key=f"obj_btn_{obj_key}_{field_key}",
                help=obj_info['description'],
                use_container_width=True
            ):
                selected_object = obj_key
                st.session_state[f"selected_obj_{field_key}"] = obj_key
    
    # Get the selected object from session state
    if f"selected_obj_{field_key}" in st.session_state:
        selected_object = st.session_state[f"selected_obj_{field_key}"]
    
    if selected_object:
        st.success(f"✅ Selected: **{DATABASE_OBJECTS[selected_object]['label']}**")
        
        st.markdown("#### Step 2: Choose Field Path")
        
        # Show common paths for the selected object
        common_paths = DATABASE_OBJECTS[selected_object]['common_paths']
        
        # Radio button for path selection method
        path_method = st.radio(
            "How would you like to specify the field path?",
            ["Select from common paths", "Enter custom path"],
            key=f"path_method_{field_key}",
            horizontal=True
        )
        
        selected_path = ""
        
        if path_method == "Select from common paths":
            selected_path = st.selectbox(
                "Choose field path:",
                options=common_paths,
                key=f"path_select_{field_key}",
                help="Select the database field this form field should map to"
            )
        else:
            selected_path = st.text_input(
                "Enter custom field path:",
                key=f"custom_path_{field_key}",
                placeholder="e.g., customField.subField",
                help="Enter a custom database field path"
            )
        
        # Preview the mapping
        if selected_path:
            st.info(f"💡 **Mapping Preview:** {field.field_number} → {selected_object}.{selected_path}")
        
        st.markdown("#### Step 3: Apply Mapping")
        
        # Action buttons
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col1:
            if st.button(
                "✅ Apply Mapping",
                key=f"apply_{field_key}",
                type="primary",
                disabled=not selected_path,
                use_container_width=True
            ):
                field.is_mapped = True
                field.db_object = selected_object
                field.db_path = selected_path
                field.in_questionnaire = False
                
                # Clear session state
                if f"selected_obj_{field_key}" in st.session_state:
                    del st.session_state[f"selected_obj_{field_key}"]
                st.session_state[f"show_mapping_{field_key}"] = False
                
                st.success(f"✅ Mapped {field.field_number} to {selected_object}.{selected_path}")
                st.rerun()
        
        with col2:
            if st.button("🔄 Reset", key=f"reset_{field_key}", use_container_width=True):
                if f"selected_obj_{field_key}" in st.session_state:
                    del st.session_state[f"selected_obj_{field_key}"]
                st.rerun()
        
        with col3:
            if st.button("❌ Cancel", key=f"cancel_{field_key}", use_container_width=True):
                if f"selected_obj_{field_key}" in st.session_state:
                    del st.session_state[f"selected_obj_{field_key}"]
                st.session_state[f"show_mapping_{field_key}"] = False
                st.rerun()
    
    else:
        st.info("👆 **Click on a database object above to start mapping**")
    
    st.markdown('</div>', unsafe_allow_html=True)

def display_form_enhanced(smart_form: SmartForm):
    """Enhanced form display with better organization"""
    
    if not smart_form or not smart_form.parts:
        st.warning("No form data to display")
        return
    
    # Enhanced form header
    st.markdown(f"## 📄 {smart_form.form_number}: {smart_form.form_title}")
    if smart_form.form_edition:
        st.markdown(f"**Edition:** {smart_form.form_edition} • **Pages:** {smart_form.total_pages}")
    
    # Enhanced summary stats
    col1, col2, col3, col4, col5 = st.columns(5)
    
    all_fields = smart_form.get_all_fields()
    mapped_fields = smart_form.get_mapped_fields()
    questionnaire_fields = smart_form.get_questionnaire_fields()
    unmapped_fields = smart_form.get_unmapped_fields()
    
    with col1:
        st.metric("📊 Total Fields", len(all_fields))
    with col2:
        st.metric("✅ Mapped", len(mapped_fields))
    with col3:
        st.metric("📝 Questionnaire", len(questionnaire_fields))
    with col4:
        st.metric("❓ Unmapped", len(unmapped_fields))
    with col5:
        if len(all_fields) > 0:
            completion = (len(mapped_fields) + len(questionnaire_fields)) / len(all_fields)
            st.metric("🎯 Progress", f"{completion:.0%}")
        else:
            st.metric("🎯 Progress", "0%")
    
    # Display parts with enhanced organization
    for part_num in sorted(smart_form.parts.keys()):
        part = smart_form.parts[part_num]
        
        # Enhanced part header
        page_info = f"Pages {part.page_start}-{part.page_end}" if part.page_end > part.page_start else f"Page {part.page_start}"
        part_header = f"📄 Part {part.number}: {part.title} ({page_info})"
        
        with st.expander(part_header, expanded=(part_num <= 2)):
            
            if part.description:
                st.markdown(f"*{part.description}*")
            
            # Part statistics
            part_mapped = sum(1 for f in part.fields if f.is_mapped)
            part_questionnaire = sum(1 for f in part.fields if f.in_questionnaire)
            part_unmapped = len(part.fields) - part_mapped - part_questionnaire
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Fields", len(part.fields))
            with col2:
                st.metric("Mapped", part_mapped)
            with col3:
                st.metric("Questionnaire", part_questionnaire)
            with col4:
                st.metric("Unmapped", part_unmapped)
            
            # Display fields
            if not part.fields:
                st.info("No fields found in this part")
                continue
            
            for i, field in enumerate(part.fields):
                field_key = f"{part_num}_{i}"
                display_field_enhanced(field, field_key)

def display_export_enhanced(smart_form: SmartForm):
    """Enhanced export options"""
    
    st.markdown("## 📤 Export Results")
    
    if not smart_form:
        st.warning("No form data to export")
        return
    
    mapped_fields = smart_form.get_mapped_fields()
    questionnaire_fields = smart_form.get_questionnaire_fields()
    
    # Export tabs
    tab1, tab2, tab3 = st.tabs(["🔗 Database Mappings", "📝 Questionnaire", "📊 Form Summary"])
    
    with tab1:
        st.markdown("### Database Field Mappings")
        st.info(f"Ready to export: **{len(mapped_fields)}** mapped fields")
        
        if mapped_fields:
            # Show preview
            preview_data = []
            for field in mapped_fields[:5]:  # Show first 5
                preview_data.append({
                    "Field": field.field_number,
                    "Label": field.field_label,
                    "Database": f"{field.db_object}.{field.db_path}",
                    "Value": field.field_value[:30] + "..." if len(field.field_value) > 30 else field.field_value
                })
            
            if preview_data:
                st.markdown("**Preview:**")
                st.dataframe(pd.DataFrame(preview_data), use_container_width=True)
                if len(mapped_fields) > 5:
                    st.caption(f"... and {len(mapped_fields) - 5} more fields")
            
            if st.button("📋 Generate Database Mappings", type="primary"):
                mappings_content = generate_enhanced_mappings(smart_form, mapped_fields)
                st.code(mappings_content, language="json")
                
                filename = f"{smart_form.form_number.replace('-', '_')}_mappings.json"
                st.download_button(
                    "💾 Download Mappings JSON",
                    mappings_content,
                    filename,
                    "application/json",
                    use_container_width=True
                )
        else:
            st.info("No mapped fields to export. Map some fields first!")
    
    with tab2:
        st.markdown("### Questionnaire Fields")
        st.info(f"Ready to export: **{len(questionnaire_fields)}** questionnaire fields")
        
        if questionnaire_fields:
            # Show preview
            preview_data = []
            for field in questionnaire_fields[:5]:
                preview_data.append({
                    "Field": field.field_number,
                    "Question": field.field_label,
                    "Type": field.field_type.value,
                    "Value": field.field_value[:30] + "..." if len(field.field_value) > 30 else field.field_value
                })
            
            if preview_data:
                st.markdown("**Preview:**")
                st.dataframe(pd.DataFrame(preview_data), use_container_width=True)
                if len(questionnaire_fields) > 5:
                    st.caption(f"... and {len(questionnaire_fields) - 5} more fields")
            
            if st.button("📋 Generate Questionnaire", type="primary"):
                questionnaire_content = generate_enhanced_questionnaire(smart_form, questionnaire_fields)
                st.code(questionnaire_content, language="json")
                
                filename = f"{smart_form.form_number.replace('-', '_')}_questionnaire.json"
                st.download_button(
                    "💾 Download Questionnaire JSON",
                    questionnaire_content,
                    filename,
                    "application/json",
                    use_container_width=True
                )
        else:
            st.info("No questionnaire fields to export. Move some fields to questionnaire first!")
    
    with tab3:
        st.markdown("### Form Processing Summary")
        
        # Generate comprehensive summary
        summary = {
            "form_info": {
                "form_number": smart_form.form_number,
                "form_title": smart_form.form_title,
                "form_edition": smart_form.form_edition,
                "total_pages": smart_form.total_pages,
                "processing_date": datetime.now().isoformat()
            },
            "extraction_summary": {
                "total_parts": len(smart_form.parts),
                "total_fields": len(smart_form.get_all_fields()),
                "mapped_fields": len(mapped_fields),
                "questionnaire_fields": len(questionnaire_fields),
                "unmapped_fields": len(smart_form.get_unmapped_fields())
            },
            "parts_breakdown": []
        }
        
        for part in sorted(smart_form.parts.values(), key=lambda p: p.number):
            part_summary = {
                "part_number": part.number,
                "part_title": part.title,
                "page_range": f"{part.page_start}-{part.page_end}",
                "field_count": len(part.fields),
                "mapped_count": sum(1 for f in part.fields if f.is_mapped),
                "questionnaire_count": sum(1 for f in part.fields if f.in_questionnaire)
            }
            summary["parts_breakdown"].append(part_summary)
        
        summary_content = json.dumps(summary, indent=2)
        st.code(summary_content, language="json")
        
        filename = f"{smart_form.form_number.replace('-', '_')}_summary.json"
        st.download_button(
            "💾 Download Processing Summary",
            summary_content,
            filename,
            "application/json",
            use_container_width=True
        )

def display_questionnaire_enhanced(smart_form: SmartForm):
    """Enhanced questionnaire interface"""
    
    st.markdown("## 📝 Complete Questionnaire Fields")
    
    questionnaire_fields = smart_form.get_questionnaire_fields()
    
    if not questionnaire_fields:
        st.info("✨ No fields in questionnaire! Use the '📝 Quest' button on any field to move it here for manual completion.")
        return
    
    st.info(f"Complete these **{len(questionnaire_fields)}** fields manually:")
    
    # Group fields by part for better organization
    fields_by_part = {}
    for field in questionnaire_fields:
        if field.part_number not in fields_by_part:
            fields_by_part[field.part_number] = []
        fields_by_part[field.part_number].append(field)
    
    # Display fields organized by part
    for part_number in sorted(fields_by_part.keys()):
        part = smart_form.parts.get(part_number)
        part_title = part.title if part else f"Part {part_number}"
        
        st.markdown(f"### 📄 {part_title}")
        
        fields = fields_by_part[part_number]
        
        for i, field in enumerate(fields):
            field_key = f"quest_{part_number}_{i}"
            
            st.markdown(f"#### {field.field_number}: {field.field_label}")
            
            col1, col2 = st.columns([3, 1])
            
            with col1:
                if field.field_type == FieldType.TEXT:
                    answer = st.text_input(
                        f"Enter {field.field_label.lower()}:",
                        value=field.field_value,
                        key=field_key,
                        placeholder="Enter your answer here..."
                    )
                elif field.field_type == FieldType.DATE:
                    try:
                        date_val = pd.to_datetime(field.field_value).date() if field.field_value else None
                    except:
                        date_val = None
                    
                    answer = st.date_input(
                        "Select date:",
                        value=date_val,
                        key=f"{field_key}_date"
                    )
                    answer = str(answer) if answer else ""
                elif field.field_type == FieldType.CHECKBOX:
                    answer = st.selectbox(
                        "Select option:",
                        ["", "Yes", "No"],
                        index=0,
                        key=f"{field_key}_check"
                    )
                elif field.field_type in [FieldType.EMAIL, FieldType.PHONE]:
                    answer = st.text_input(
                        f"Enter {field.field_type.value}:",
                        value=field.field_value,
                        key=field_key,
                        placeholder=f"Enter {field.field_type.value}..."
                    )
                else:
                    answer = st.text_area(
                        "Enter your answer:",
                        value=field.field_value,
                        key=field_key,
                        height=100,
                        placeholder="Enter your detailed answer here..."
                    )
                
                if answer != field.field_value:
                    field.field_value = answer
                    field.manually_edited = True
            
            with col2:
                # Field info
                if field.is_required:
                    st.markdown("🔴 **Required**")
                
                st.caption(f"Type: {field.field_type.value}")
                if field.page_number > 0:
                    st.caption(f"Page: {field.page_number}")
                
                # Move back button
                if st.button("🔙 Move Back", key=f"back_{field_key}"):
                    field.in_questionnaire = False
                    st.success(f"Moved {field.field_number} back to mapping")
                    st.rerun()
            
            st.markdown("---")

# ===== ENHANCED EXPORT FUNCTIONS =====

def generate_enhanced_mappings(smart_form: SmartForm, mapped_fields: List[SmartField]) -> str:
    """Generate enhanced mappings JSON with full metadata"""
    
    mappings = {
        "form_metadata": {
            "form_number": smart_form.form_number,
            "form_title": smart_form.form_title,
            "form_edition": smart_form.form_edition,
            "total_pages": smart_form.total_pages,
            "generated_date": datetime.now().isoformat(),
            "total_mapped_fields": len(mapped_fields)
        },
        "database_mappings": {},
        "field_list": []
    }
    
    # Group mappings by database object
    for field in mapped_fields:
        if field.db_object not in mappings["database_mappings"]:
            mappings["database_mappings"][field.db_object] = []
        
        field_mapping = {
            "field_number": field.field_number,
            "field_label": field.field_label,
            "field_type": field.field_type.value,
            "database_path": field.db_path,
            "current_value": field.field_value,
            "part_number": field.part_number,
            "page_number": field.page_number,
            "is_required": field.is_required,
            "manually_edited": field.manually_edited
        }
        
        mappings["database_mappings"][field.db_object].append(field_mapping)
        mappings["field_list"].append({
            "field_number": field.field_number,
            "database_object": field.db_object,
            "database_path": field.db_path,
            "current_value": field.field_value
        })
    
    return json.dumps(mappings, indent=2)

def generate_enhanced_questionnaire(smart_form: SmartForm, questionnaire_fields: List[SmartField]) -> str:
    """Generate enhanced questionnaire JSON"""
    
    questionnaire = {
        "form_metadata": {
            "form_number": smart_form.form_number,
            "form_title": smart_form.form_title,
            "form_edition": smart_form.form_edition,
            "generated_date": datetime.now().isoformat(),
            "total_questions": len(questionnaire_fields)
        },
        "questions_by_part": {},
        "all_questions": []
    }
    
    # Group questions by part
    for field in questionnaire_fields:
        part_key = f"part_{field.part_number}"
        if part_key not in questionnaire["questions_by_part"]:
            part = smart_form.parts.get(field.part_number)
            questionnaire["questions_by_part"][part_key] = {
                "part_title": part.title if part else f"Part {field.part_number}",
                "questions": []
            }
        
        question = {
            "field_number": field.field_number,
            "question_text": field.field_label,
            "field_type": field.field_type.value,
            "current_answer": field.field_value,
            "is_required": field.is_required,
            "page_number": field.page_number,
            "part_number": field.part_number
        }
        
        questionnaire["questions_by_part"][part_key]["questions"].append(question)
        questionnaire["all_questions"].append(question)
    
    return json.dumps(questionnaire, indent=2)

# ===== MAIN APPLICATION =====

def main():
    st.markdown(
        '<div class="main-header">'
        '<h1>🤖 Advanced Agentic USCIS Form Reader</h1>'
        '<p>Powered by advanced AI for comprehensive field extraction and intelligent mapping</p>'
        '</div>', 
        unsafe_allow_html=True
    )
    
    # Check dependencies
    if not PYMUPDF_AVAILABLE:
        st.error("❌ PyMuPDF not available! Install with: `pip install pymupdf`")
        st.stop()
    
    if not OPENAI_AVAILABLE:
        st.error("❌ OpenAI not available! Install with: `pip install openai`")
        st.stop()
    
    # Initialize session state
    if 'smart_form' not in st.session_state:
        st.session_state.smart_form = None
    
    if 'processing_stage' not in st.session_state:
        st.session_state.processing_stage = ProcessingStage.UPLOADED
    
    # Initialize advanced processor
    if 'processor' not in st.session_state:
        st.session_state.processor = AdvancedAgenticProcessor()
    
    # Enhanced sidebar
    with st.sidebar:
        st.markdown("## 🎛️ Advanced Controls")
        
        if st.button("🆕 New Form", type="primary", use_container_width=True):
            st.session_state.smart_form = None
            st.session_state.processing_stage = ProcessingStage.UPLOADED
            # Clear all mapping states
            for key in list(st.session_state.keys()):
                if any(prefix in key for prefix in ['show_mapping_', 'selected_obj_', 'obj_btn_', 'path_method_']):
                    del st.session_state[key]
            st.rerun()
        
        # Enhanced database objects reference
        st.markdown("### 📊 Database Objects")
        for obj_name, obj_info in DATABASE_OBJECTS.items():
            with st.expander(f"{obj_info['icon']} {obj_info['label']}"):
                st.markdown(f"**{obj_info['description']}**")
                st.caption("Key fields:")
                for path in obj_info['common_paths'][:6]:
                    st.code(path, language=None)
                if len(obj_info['common_paths']) > 6:
                    st.caption(f"...and {len(obj_info['common_paths']) - 6} more")
        
        # Enhanced form stats
        if st.session_state.smart_form:
            form = st.session_state.smart_form
            st.markdown("### 📈 Current Form Stats")
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Form", form.form_number)
                st.metric("Parts", len(form.parts))
                st.metric("Total Fields", len(form.get_all_fields()))
            
            with col2:
                st.metric("Pages", form.total_pages)
                st.metric("Mapped", len(form.get_mapped_fields()))
                st.metric("Questionnaire", len(form.get_questionnaire_fields()))
            
            # Progress calculation
            total_fields = len(form.get_all_fields())
            if total_fields > 0:
                mapped_count = len(form.get_mapped_fields())
                quest_count = len(form.get_questionnaire_fields())
                progress = (mapped_count + quest_count) / total_fields
                st.progress(progress, text=f"Progress: {progress:.0%}")
            
            # Enhanced bulk actions
            st.markdown("### ⚡ Bulk Actions")
            if st.button("📝 All Unmapped → Questionnaire", use_container_width=True):
                unmapped_count = 0
                for field in form.get_unmapped_fields():
                    field.in_questionnaire = True
                    unmapped_count += 1
                if unmapped_count > 0:
                    st.success(f"Moved {unmapped_count} fields to questionnaire!")
                    st.rerun()
                else:
                    st.info("No unmapped fields to move")
            
            if st.button("🔄 Reset All Mappings", use_container_width=True):
                if st.button("⚠️ Confirm Reset", type="secondary", use_container_width=True):
                    reset_count = 0
                    for field in form.get_all_fields():
                        if field.is_mapped:
                            field.is_mapped = False
                            field.db_object = ""
                            field.db_path = ""
                            reset_count += 1
                    st.warning(f"Reset {reset_count} field mappings")
                    st.rerun()
    
    # Enhanced main interface
    tab1, tab2, tab3, tab4 = st.tabs(["🚀 Process Form", "✏️ Map Fields", "📝 Questionnaire", "📤 Export Results"])
    
    with tab1:
        st.markdown("### 🚀 Upload & Process USCIS Form")
        st.markdown("Upload any USCIS form (I-539, I-129, I-90, G-28, etc.) for intelligent field extraction and mapping.")
        
        uploaded_file = st.file_uploader(
            "Choose USCIS form PDF",
            type=['pdf'],
            help="Upload a completed or blank USCIS form for processing"
        )
        
        if uploaded_file:
            st.success(f"✅ **File uploaded:** {uploaded_file.name}")
            
            if st.button("🚀 Process with Advanced AI", type="primary", use_container_width=True):
                if not st.session_state.processor.openai_client:
                    st.error("❌ OpenAI client not available. Please check your API key setup.")
                    st.stop()
                
                progress_placeholder = st.empty()
                
                def update_progress(text):
                    progress_placeholder.info(f"🤖 {text}")
                
                with st.spinner("🤖 Advanced AI processing in progress..."):
                    try:
                        # Enhanced PDF extraction
                        update_progress("Stage 1: Enhanced PDF text extraction...")
                        full_text, page_texts = extract_pdf_text_enhanced(uploaded_file)
                        
                        if not full_text or len(full_text.strip()) < 100:
                            st.error("❌ Insufficient text content found in PDF. Please ensure the PDF contains readable text.")
                            st.stop()
                        
                        # Advanced AI processing
                        smart_form = st.session_state.processor.process_form_advanced(
                            full_text, page_texts, update_progress
                        )
                        
                        if smart_form and smart_form.parts:
                            st.session_state.smart_form = smart_form
                            st.session_state.processing_stage = ProcessingStage.COMPLETED
                            
                            progress_placeholder.empty()
                            st.balloons()
                            
                            # Enhanced success summary
                            st.markdown("## 🎉 Processing Complete!")
                            
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric("📄 Parts Extracted", len(smart_form.parts))
                            with col2:
                                st.metric("📋 Fields Found", len(smart_form.get_all_fields()))
                            with col3:
                                st.metric("🤖 Auto-Mapped", len(smart_form.get_mapped_fields()))
                            with col4:
                                unmapped_count = len(smart_form.get_unmapped_fields())
                                st.metric("❓ Need Mapping", unmapped_count)
                            
                            st.success(f"🎉 Successfully processed **{smart_form.form_number}** with {len(smart_form.get_all_fields())} fields across {len(smart_form.parts)} parts!")
                            
                            # Show quick stats
                            if len(smart_form.get_all_fields()) > 0:
                                mapped_pct = len(smart_form.get_mapped_fields()) / len(smart_form.get_all_fields())
                                st.info(f"📊 **Ready to use:** {mapped_pct:.0%} of fields are auto-mapped. Review and adjust mappings in the next tab.")
                        else:
                            st.error("❌ Processing failed - could not extract form structure")
                    
                    except Exception as e:
                        progress_placeholder.empty()
                        st.error(f"💥 Processing error: {str(e)}")
                        logger.error(f"Processing error: {e}")
    
    with tab2:
        if st.session_state.smart_form:
            display_form_enhanced(st.session_state.smart_form)
        else:
            st.info("📄 **Upload and process a form first** to see fields for mapping")
    
    with tab3:
        if st.session_state.smart_form:
            display_questionnaire_enhanced(st.session_state.smart_form)
        else:
            st.info("📝 **Process a form first** to access the questionnaire interface")
    
    with tab4:
        if st.session_state.smart_form:
            display_export_enhanced(st.session_state.smart_form)
        else:
            st.info("📤 **Process a form first** to access export options")

if __name__ == "__main__":
    main()
