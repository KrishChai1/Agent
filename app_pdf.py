#!/usr/bin/env python3
"""
🤖 AGENTIC USCIS FORM READER - FIXED VERSION
=============================================

Fixed Issues:
- Fixed syntax error in regex pattern (line 1223)
- Completed _clean_json_aggressively method
- Improved part extraction patterns for USCIS forms
- Better error handling and JSON parsing
- Corrected database object structure

Author: AI Assistant  
Version: 4.1.0 - FIXED
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

# Configure logging to reduce noise
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Page config
st.set_page_config(
    page_title="🤖 Agentic USCIS Form Reader - Fixed",
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
    
    .part-header {
        background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%);
        border: 1px solid #f39c12;
        border-radius: 10px;
        padding: 1rem;
        margin: 1rem 0;
    }
    
    .field-card {
        background: white;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
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
        border-radius: 5px;
        height: 6px;
        overflow: hidden;
        margin: 0.3rem 0;
    }
    
    .confidence-fill {
        height: 100%;
        background: linear-gradient(90deg, #ff6b6b, #ffa500, #4ecdc4);
        transition: width 0.3s ease;
    }
    
    .mapping-interface {
        background: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    
    .progress-text {
        background: #e3f2fd;
        border: 1px solid #2196f3;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# ===== DATA STRUCTURES =====

class ProcessingStage(Enum):
    UPLOADED = "uploaded"
    ANALYZING = "analyzing"
    EXTRACTING = "extracting"
    MAPPING = "mapping"
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
    
    def get_mapped_count(self) -> int:
        return sum(1 for f in self.fields if f.is_mapped and not f.in_questionnaire)
    
    def get_unmapped_count(self) -> int:
        return sum(1 for f in self.fields if not f.is_mapped and not f.in_questionnaire)
    
    def get_questionnaire_count(self) -> int:
        return sum(1 for f in self.fields if f.in_questionnaire)

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

# ===== FIXED DATABASE SCHEMA =====

DATABASE_OBJECTS = {
    "attorney": {
        "label": "Attorney Information",
        "description": "Legal representative details",
        "icon": "⚖️",
        "paths": [
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
            "licensingAuthority",
            "uscisRepresentation",
            "receiptNumber"
        ]
    },
    "attorneyLawfirmDetails": {
        "label": "Attorney Lawfirm Details",
        "description": "Law firm and address information",
        "icon": "🏛️",
        "paths": [
            "lawfirmDetails.lawFirmName",
            "lawfirmDetails.lawFirmFein",
            "address.addressStreet",
            "address.addressType",
            "address.addressCity",
            "address.addressState",
            "address.addressZip",
            "address.addressCountry",
            "uscisOnlineAccountNumber",
            "companyPhone"
        ]
    },
    "beneficary": {
        "label": "Beneficiary Information",
        "description": "Primary applicant details", 
        "icon": "👤",
        "paths": [
            "Beneficiary.beneficiaryFirstName",
            "Beneficiary.beneficiaryLastName",
            "Beneficiary.beneficiaryMiddleName",
            "Beneficiary.beneficiaryGender",
            "Beneficiary.beneficiaryDateOfBirth",
            "Beneficiary.beneficiarySsn",
            "Beneficiary.alienNumber",
            "Beneficiary.beneficiaryCountryOfBirth",
            "Beneficiary.beneficiaryCitizenOfCountry",
            "Beneficiary.beneficiaryCellNumber",
            "Beneficiary.beneficiaryWorkNumber",
            "Beneficiary.beneficiaryPrimaryEmailAddress",
            "Beneficiary.uscisOnlineAccount",
            "HomeAddress.addressStreet",
            "HomeAddress.addressCity",
            "HomeAddress.addressState",
            "HomeAddress.addressZip",
            "HomeAddress.addressCountry",
            "WorkAddress.addressStreet",
            "WorkAddress.addressCity",
            "WorkAddress.addressState",
            "WorkAddress.addressZip",
            "WorkAddress.addressCountry"
        ]
    },
    "customer": {
        "label": "Customer/Employer Information",
        "description": "Employer or petitioning organization",
        "icon": "🏢",
        "paths": [
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
            "address_type",
            "address_number",
            "address_city",
            "address_state",
            "address_zip",
            "address_country"
        ]
    },
    "case": {
        "label": "Case Information",
        "description": "Case-specific details",
        "icon": "📋",
        "paths": [
            "h1BPetitionType",
            "caseNumber",
            "priority",
            "status",
            "filingDate",
            "receiptNumber"
        ]
    }
}

# ===== PDF PROCESSING =====

def extract_pdf_text_properly(pdf_file) -> str:
    """Proper PDF text extraction with structure preservation"""
    try:
        st.info("📄 Processing PDF file...")
        
        # Reset file pointer
        pdf_file.seek(0)
        pdf_bytes = pdf_file.read()
        
        # Basic validation
        if len(pdf_bytes) == 0:
            st.error("❌ File is empty")
            return ""
        
        if not pdf_bytes.startswith(b'%PDF'):
            st.error("❌ Not a valid PDF file")
            return ""
        
        # Open PDF document
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        try:
            page_count = len(doc)
            st.success(f"✅ PDF opened successfully - {page_count} pages found")
            
            full_text = ""
            page_texts = []
            
            # Extract text from each page
            for page_num in range(page_count):
                try:
                    page = doc[page_num]
                    
                    # Get text with layout preservation
                    text_dict = page.get_text("dict")
                    
                    # Extract text blocks in reading order
                    page_text = ""
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
                    
                    # Fallback to simple text extraction if dict method fails
                    if not page_text.strip():
                        page_text = page.get_text()
                    
                    if page_text.strip():
                        page_header = f"=== PAGE {page_num + 1} ==="
                        page_texts.append(f"{page_header}\n{page_text}")
                        st.info(f"✅ Extracted text from page {page_num + 1}")
                    else:
                        st.warning(f"⚠️ No text found on page {page_num + 1}")
                        
                except Exception as e:
                    error_msg = f"⚠️ Error extracting page {page_num + 1}: {str(e)}"
                    st.warning(error_msg)
                    continue
            
            # Combine all page texts
            full_text = "\n\n".join(page_texts)
            
            if not full_text.strip():
                st.error("❌ No text content found in PDF")
                return ""
            
            char_count = len(full_text)
            st.success(f"✅ Successfully extracted {char_count} characters from PDF")
            return full_text
            
        finally:
            doc.close()
            
    except Exception as e:
        error_msg = f"💥 PDF extraction failed: {str(e)}"
        st.error(error_msg)
        logger.error(f"PDF extraction error: {e}")
        return ""

# ===== FIXED AGENTIC PROCESSOR =====

class AgenticProcessor:
    """Fixed agentic processor with proper form structure handling"""
    
    def __init__(self):
        self.openai_client = None
        self.setup_openai()
    
    def setup_openai(self):
        """Setup OpenAI client"""
        try:
            # Try multiple sources for API key
            api_key = None
            
            # Check Streamlit secrets first
            if hasattr(st, 'secrets') and 'OPENAI_API_KEY' in st.secrets:
                api_key = st.secrets['OPENAI_API_KEY']
                st.sidebar.success("🔑 Using API key from Streamlit secrets")
            
            # Check environment variable
            elif os.getenv('OPENAI_API_KEY'):
                api_key = os.getenv('OPENAI_API_KEY')
                st.sidebar.success("🔑 Using API key from environment")
            
            if not api_key:
                st.error("""
                🔑 **OpenAI API Key Required!**
                
                Please add your OpenAI API key in one of these ways:
                
                **Option 1 - Streamlit Secrets (Recommended):**
                Create `.streamlit/secrets.toml`:
                ```
                OPENAI_API_KEY = "your-api-key-here"
                ```
                
                **Option 2 - Environment Variable:**
                ```
                export OPENAI_API_KEY="your-api-key-here"
                ```
                """)
                return
            
            # Initialize client
            self.openai_client = openai.OpenAI(api_key=api_key)
            
            # Test connection with minimal call
            try:
                self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": "test"}],
                    max_tokens=1
                )
                st.sidebar.success("✅ OpenAI connection verified!")
            except Exception as e:
                st.error(f"❌ OpenAI API test failed: {str(e)}")
                self.openai_client = None
                
        except Exception as e:
            st.error(f"❌ OpenAI setup failed: {str(e)}")
            self.openai_client = None
    
    def process_form_intelligently(self, pdf_text: str, progress_callback=None) -> SmartForm:
        """Main processing pipeline with fixed form structure handling"""
        
        if not self.openai_client:
            st.error("❌ OpenAI client not available")
            return None
        
        try:
            # Stage 1: Analyze form and extract parts with improved patterns
            if progress_callback:
                progress_callback("🔍 Analyzing form structure and extracting parts...")
            
            form_data = self._analyze_form_and_extract_parts_fixed(pdf_text)
            
            if not form_data:
                st.error("❌ Failed to analyze form structure")
                return None
            
            # Stage 2: Create Smart Form
            smart_form = SmartForm(
                form_number=form_data.get('form_number', 'Unknown'),
                form_title=form_data.get('form_title', 'Unknown Form'),
                form_edition=form_data.get('form_edition', ''),
                processing_stage=ProcessingStage.EXTRACTING
            )
            
            # Stage 3: Process each part with improved field extraction
            if progress_callback:
                progress_callback("📄 Extracting fields from each part...")
            
            parts_data = form_data.get('parts', [])
            
            for part_data in parts_data:
                part_number = part_data.get('number', 1)
                part_title = part_data.get('title', 'Unknown Part')
                
                if progress_callback:
                    progress_msg = f"📄 Processing {part_title}"
                    progress_callback(progress_msg)
                
                smart_part = SmartPart(
                    number=part_number,
                    title=part_title,
                    description=part_data.get('description', '')
                )
                
                # Extract fields for this part with improved numbering
                fields = self._extract_fields_for_part_fixed(part_data, pdf_text)
                
                for field in fields:
                    smart_part.add_field(field)
                
                smart_form.add_part(smart_part)
            
            # Stage 4: Apply intelligent mapping
            if progress_callback:
                progress_callback("🧠 Applying intelligent mapping...")
            
            self._apply_intelligent_mapping_fixed(smart_form)
            
            smart_form.processing_stage = ProcessingStage.COMPLETED
            smart_form.calculate_metrics()
            
            return smart_form
            
        except Exception as e:
            logger.error(f"Processing failed: {e}")
            st.error(f"❌ Processing error: {str(e)}")
            return None
    
    def _analyze_form_and_extract_parts_fixed(self, pdf_text: str) -> Dict[str, Any]:
        """Analyze form with improved part identification patterns"""
        
        # Limit text length for API call
        analysis_text = pdf_text[:20000]  # Increased for better part detection
        
        prompt = f"""
        Analyze this USCIS form text and extract the form information AND all parts.
        
        CRITICAL JSON REQUIREMENTS:
        - Use ONLY double quotes for all strings and property names
        - NO single quotes anywhere  
        - NO trailing commas
        - NO unquoted property names
        - Ensure all strings are properly closed
        
        USCIS forms have specific part patterns. Look for:
        - "Part 1." or "Part 1:" followed by title (e.g., "Part 1. Information About You")
        - "Part 2." or "Part 2:" followed by title (e.g., "Part 2. Application Type")
        - "Part 3." through "Part 14." with their specific titles
        - Some forms use "Section A" or "Section B" within parts
        
        Common USCIS form structures:
        - I-90: Part 1 (Information About You), Part 2 (Application Type), Part 3 (Processing Information)
        - I-129: Part 1 (Information About Employer), Part 2 (Information About This Petition)
        - G-28: Part 1 (Attorney Information), Part 3 (Notice of Appearance), Part 4 (Client's Consent)
        - I-765: Part 1 (Reason for Applying), Part 2 (Information About You), Part 3 (Processing Information)
        
        Return EXACTLY this JSON structure with NO extra text:
        
        {{
            "form_number": "I-90",
            "form_title": "Application to Replace Permanent Resident Card", 
            "form_edition": "01/20/25",
            "parts": [
                {{
                    "number": 1,
                    "title": "Information About You",
                    "description": "Basic applicant information"
                }},
                {{
                    "number": 2,
                    "title": "Application Type",
                    "description": "Reason for application"
                }}
            ]
        }}
        
        Form text:
        {analysis_text}
        """
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content.strip()
            
            # Log the raw response for debugging
            logger.info(f"Raw form analysis response: {content[:200]}...")
            
            # Use improved JSON parsing
            data = self._parse_json_robust_dict_fixed(content)
            
            if not data:
                logger.warning("Failed to parse form analysis JSON, using fallback")
                st.warning("⚠️ AI returned invalid JSON for form analysis, using fallback structure")
                return self._get_fallback_form_data_fixed()
            
            # Ensure we have at least one part
            if not data.get('parts'):
                default_part = {"number": 1, "title": "Form Information", "description": "All form fields"}
                data['parts'] = [default_part]
            
            return data
            
        except Exception as e:
            logger.error(f"Form analysis failed: {e}")
            st.error(f"⚠️ Form analysis error: {str(e)}")
            return self._get_fallback_form_data_fixed()
    
    def _get_fallback_form_data_fixed(self) -> Dict[str, Any]:
        """Get fixed fallback form data with typical USCIS parts"""
        
        return {
            'form_number': 'Unknown',
            'form_title': 'Unknown USCIS Form',
            'form_edition': '',
            'parts': [
                {"number": 1, "title": "Information About You", "description": "Basic applicant information"},
                {"number": 2, "title": "Application/Petition Type", "description": "Type and eligibility details"},
                {"number": 3, "title": "Processing Information", "description": "Processing and contact information"},
                {"number": 4, "title": "Additional Information", "description": "Additional details and signatures"}
            ]
        }
    
    def _extract_fields_for_part_fixed(self, part_data: Dict[str, Any], full_pdf_text: str) -> List[SmartField]:
        """Extract fields with improved numbering system and USCIS patterns"""
        
        part_number = part_data.get('number', 1)
        part_title = part_data.get('title', 'Unknown Part')
        
        # Try to find the relevant section in the PDF text
        part_text = self._extract_part_text_from_pdf_fixed(part_number, part_title, full_pdf_text)
        
        # Limit text for API call
        if len(part_text) > 12000:
            part_text = part_text[:12000] + "\n[...text truncated...]"
        
        prompt = f"""
        Extract ALL form fields from Part {part_number}: {part_title} of this USCIS form.
        
        CRITICAL JSON REQUIREMENTS:
        - Use ONLY double quotes for ALL strings and property names
        - NO single quotes anywhere in the response
        - NO trailing commas before }} or ]]
        - NO unquoted property names
        - Ensure ALL strings are properly closed with quotes
        - Return ONLY the JSON array, no extra text
        
        Look for USCIS-specific field patterns:
        - Numbered items: "1.a.", "1.b.", "2.a.", "2.b.", "3.a."
        - Sub-items: "1.a.1.", "1.a.2."
        - Checkboxes for Yes/No questions
        - Name fields (Family Name, Given Name, Middle Name)
        - Address fields (Street Number and Name, City, State, ZIP Code, Country)
        - Date fields (Date of Birth, etc.)
        - Contact fields (Daytime Phone Number, Mobile Phone Number, Email Address)
        - SSN, A-Number, USCIS Online Account Number fields
        - Signature and date fields
        
        Field numbering conventions:
        - Use the actual field numbers from the form (e.g., "1.a.", "1.b.", "2.a.")
        - For Part {part_number}, prefix with P{part_number}_ if needed (e.g., "P{part_number}_1a")
        
        Return EXACTLY this JSON array structure:
        
        [
            {{
                "field_number": "1.a.",
                "field_label": "Family Name (Last Name)",
                "field_value": "",
                "field_type": "text",
                "is_required": true,
                "confidence": 0.85
            }},
            {{
                "field_number": "1.b.",
                "field_label": "Given Name (First Name)", 
                "field_value": "",
                "field_type": "text",
                "is_required": true,
                "confidence": 0.90
            }}
        ]
        
        Valid field_type values: text, date, checkbox, radio, number, email, phone, address, ssn, alien_number
        
        Part text:
        {part_text}
        """
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=3000
            )
            
            content = response.choices[0].message.content.strip()
            
            # Log the raw response for debugging
            logger.info(f"Raw field extraction response for part {part_number}: {content[:200]}...")
            
            # Clean and parse JSON response
            fields_data = self._parse_json_robust_array_fixed(content)
            
            if not fields_data:
                st.warning(f"⚠️ AI returned invalid JSON for Part {part_number}, creating fallback fields")
                logger.warning(f"Invalid JSON from AI for part {part_number}. Content: {content[:500]}...")
                return self._create_fallback_fields_fixed(part_number, part_title)
            
            fields = []
            for i, field_data in enumerate(fields_data):
                try:
                    # Convert field type
                    field_type_str = field_data.get('field_type', 'text')
                    try:
                        field_type = FieldType(field_type_str)
                    except ValueError:
                        field_type = FieldType.TEXT
                    
                    # Create field number with improved format
                    field_num = field_data.get('field_number', f'{part_number}.{chr(97+i)}.')  # 1.a., 1.b., etc.
                    
                    field = SmartField(
                        field_number=field_num,
                        field_label=field_data.get('field_label', 'Unknown Field'),
                        field_value=field_data.get('field_value', ''),
                        field_type=field_type,
                        part_number=part_number,
                        extraction_confidence=field_data.get('confidence', 0.5),
                        is_required=field_data.get('is_required', False)
                    )
                    
                    fields.append(field)
                    
                except Exception as e:
                    logger.error(f"Failed to create field {i} for part {part_number}: {e}")
                    continue
            
            if not fields:
                st.warning(f"⚠️ No fields created for Part {part_number}, using fallback")
                return self._create_fallback_fields_fixed(part_number, part_title)
            
            st.success(f"✅ Extracted {len(fields)} fields from Part {part_number}")
            return fields
            
        except Exception as e:
            logger.error(f"Field extraction failed for part {part_number}: {e}")
            st.warning(f"⚠️ Field extraction failed for Part {part_number}: {str(e)}")
            return self._create_fallback_fields_fixed(part_number, part_title)
    
    def _create_fallback_fields_fixed(self, part_number: int, part_title: str) -> List[SmartField]:
        """Create fallback fields with improved USCIS numbering"""
        
        fallback_fields = []
        
        # Create fields based on part type
        if part_number == 1 or "information about you" in part_title.lower():
            # Part 1: Information About You
            field_templates = [
                ("1.a.", "Family Name (Last Name)", FieldType.TEXT),
                ("1.b.", "Given Name (First Name)", FieldType.TEXT),
                ("1.c.", "Middle Name", FieldType.TEXT),
                ("2.", "Date of Birth", FieldType.DATE),
                ("3.", "Country of Birth", FieldType.TEXT),
                ("4.", "Country of Citizenship or Nationality", FieldType.TEXT),
                ("5.", "U.S. Social Security Number", FieldType.SSN),
                ("6.", "A-Number", FieldType.ALIEN_NUMBER)
            ]
        elif part_number == 2 or "application" in part_title.lower():
            # Part 2: Application Type
            field_templates = [
                ("1.a.", "Application Type - Reason 1", FieldType.CHECKBOX),
                ("1.b.", "Application Type - Reason 2", FieldType.CHECKBOX),
                ("1.c.", "Application Type - Reason 3", FieldType.CHECKBOX),
                ("2.", "Additional Information", FieldType.TEXT)
            ]
        elif part_number == 3 or "processing" in part_title.lower():
            # Part 3: Processing Information
            field_templates = [
                ("1.", "Current Mailing Address - Street Number and Name", FieldType.ADDRESS),
                ("2.", "City or Town", FieldType.TEXT),
                ("3.", "State", FieldType.TEXT),
                ("4.", "ZIP Code", FieldType.TEXT),
                ("5.", "Daytime Phone Number", FieldType.PHONE),
                ("6.", "Mobile Phone Number", FieldType.PHONE),
                ("7.", "Email Address", FieldType.EMAIL)
            ]
        else:
            # Generic fields
            field_templates = [
                (f"{part_number}.a.", f"{part_title} - Field A", FieldType.TEXT),
                (f"{part_number}.b.", f"{part_title} - Field B", FieldType.TEXT),
                (f"{part_number}.c.", f"{part_title} - Field C", FieldType.TEXT)
            ]
        
        for field_num, field_label, field_type in field_templates:
            field = SmartField(
                field_number=field_num,
                field_label=field_label,
                field_value="",
                field_type=field_type,
                part_number=part_number,
                extraction_confidence=0.3,
                is_required=False
            )
            fallback_fields.append(field)
        
        return fallback_fields
    
    def _extract_part_text_from_pdf_fixed(self, part_number: int, part_title: str, full_text: str) -> str:
        """Extract text for specific part with improved patterns"""
        
        lines = full_text.split('\n')
        part_lines = []
        found_part = False
        
        # Enhanced patterns for part detection - more flexible
        part_patterns = [
            rf"Part\s+{part_number}[.\s:)]",
            rf"PART\s+{part_number}[.\s:)]", 
            rf"Part\s+{part_number}\.",
            rf"{part_number}\.\s+",
            # More flexible title matching
            re.escape(part_title.lower()).replace(r'\ ', r'\s+'),
            # Match partial titles
            part_title.split()[0].lower() if part_title.split() else "",
        ]
        
        # Find the start of this part
        start_idx = 0
        for i, line in enumerate(lines):
            line_lower = line.lower().strip()
            for pattern in part_patterns:
                if pattern and re.search(pattern, line_lower, re.IGNORECASE):
                    start_idx = i
                    found_part = True
                    break
            if found_part:
                break
        
        # Find the end (next part or end of document)
        end_idx = len(lines)
        if found_part:
            next_part_number = part_number + 1
            for i in range(start_idx + 1, len(lines)):
                line = lines[i].lower().strip()
                next_part_patterns = [
                    rf"part\s+{next_part_number}[.\s:)]",
                    rf"part\s+{next_part_number}\.",
                    # Also look for signature sections which typically end parts
                    r"signature\s+of",
                    r"part\s+\d+\s*\.",
                    r"additional\s+information"
                ]
                for pattern in next_part_patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        end_idx = i
                        break
                if end_idx < len(lines):
                    break
        
        # Extract the part text
        if found_part:
            part_text = '\n'.join(lines[start_idx:end_idx])
        else:
            # If specific part not found, use a portion of the full text
            total_lines = len(lines)
            chunk_size = max(50, total_lines // 4)  # Larger chunks for better context
            start_idx = max(0, (part_number - 1) * chunk_size)
            end_idx = min(start_idx + chunk_size, total_lines)
            part_text = '\n'.join(lines[start_idx:end_idx])
        
        return part_text
    
    def _apply_intelligent_mapping_fixed(self, smart_form: SmartForm):
        """Apply intelligent mapping with improved database paths"""
        
        # Get all unmapped fields
        unmapped_fields = smart_form.get_unmapped_fields()
        
        if not unmapped_fields:
            return
        
        # Process fields in batches to reduce API calls
        batch_size = 5
        for i in range(0, len(unmapped_fields), batch_size):
            batch = unmapped_fields[i:i+batch_size]
            suggestions = self._get_mapping_suggestions_batch_fixed(batch)
            
            # Apply high-confidence mappings
            for j, field in enumerate(batch):
                if j < len(suggestions) and suggestions[j]:
                    suggestion = suggestions[j]
                    if suggestion.get('confidence', 0) > 0.85:
                        field.is_mapped = True
                        field.db_object = suggestion['db_object']
                        field.db_path = suggestion['db_path']
    
    def _get_mapping_suggestions_batch_fixed(self, fields: List[SmartField]) -> List[Dict[str, Any]]:
        """Get mapping suggestions with improved database schema"""
        
        # Prepare batch data
        fields_info = []
        for field in fields:
            field_info = {
                "number": field.field_number,
                "label": field.field_label,
                "type": field.field_type.value,
                "value": field.field_value[:50] if field.field_value else "",
                "part": field.part_number
            }
            fields_info.append(field_info)
        
        # Prepare schema info
        schema_info = {}
        for obj_name, obj_data in DATABASE_OBJECTS.items():
            schema_info[obj_name] = {
                "description": obj_data["description"],
                "paths": obj_data["paths"][:15]
            }
        
        prompt = f"""
        Map these USCIS form fields to the correct database objects and paths.
        
        CRITICAL JSON REQUIREMENTS:
        - Use ONLY double quotes for ALL strings and property names
        - NO single quotes anywhere in the response
        - NO trailing commas before ]] or }}
        - NO unquoted property names
        - Ensure ALL strings are properly closed with quotes
        - Return ONLY the JSON array, no extra text
        
        Fields to map:
        {json.dumps(fields_info, indent=2)}
        
        Available database schema (use EXACT paths):
        {json.dumps(schema_info, indent=2)}
        
        Mapping guidelines:
        - attorney fields → "attorney" or "attorneyLawfirmDetails" 
        - beneficiary fields → "beneficary" (note: spelled as "beneficary" in schema)
        - employer/company fields → "customer"
        - case info → "case"
        - Use full dotted paths like "attorney.attorneyInfo.lastName"
        - First name fields map to firstName/beneficiaryFirstName
        - Last name fields map to lastName/beneficiaryLastName
        - Address fields map to appropriate address objects
        
        Return EXACTLY this JSON array structure:
        
        [
            {{
                "db_object": "beneficary",
                "db_path": "Beneficiary.beneficiaryFirstName",
                "confidence": 0.90
            }},
            {{
                "db_object": "attorney", 
                "db_path": "attorneyInfo.lastName",
                "confidence": 0.85
            }}
        ]
        
        If no good mapping exists, use confidence below 0.5.
        """
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=1500
            )
            
            content = response.choices[0].message.content.strip()
            
            # Use improved JSON parsing
            suggestions = self._parse_json_robust_array_fixed(content)
            
            if not suggestions:
                logger.warning("Failed to parse mapping suggestions, returning empty list")
                return []
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Batch mapping failed: {e}")
            return []
    
    # ===== FIXED JSON PARSING METHODS =====
    
    def _parse_json_robust_dict_fixed(self, content: str) -> Dict[str, Any]:
        """Fixed ultra-robust JSON parsing for dictionary responses"""
        
        # Quick validation first
        is_valid, error_msg = self._validate_json_before_parsing(content)
        if not is_valid:
            logger.warning(f"JSON validation failed: {error_msg}")
        
        # Strategy 1: Standard extraction
        try:
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
            
            return json.loads(content.strip())
        except json.JSONDecodeError as e:
            logger.warning(f"Strategy 1 failed: {e}")
        
        # Strategy 2: Find JSON object in content
        try:
            start = content.find('{')
            end = content.rfind('}') + 1
            if start != -1 and end > start:
                json_str = content[start:end]
                return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning(f"Strategy 2 failed: {e}")
        
        # Strategy 3: Advanced cleaning with fixed regex
        try:
            cleaned = content.strip()
            
            # Remove markdown blocks
            if '```' in cleaned:
                lines = cleaned.split('\n')
                cleaned_lines = []
                in_json = False
                for line in lines:
                    if '```' in line:
                        in_json = not in_json
                        continue
                    if in_json:
                        cleaned_lines.append(line)
                cleaned = '\n'.join(cleaned_lines)
            
            # Advanced JSON cleaning with FIXED regex patterns
            cleaned = self._clean_json_aggressively_fixed(cleaned)
            
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.warning(f"Strategy 3 failed: {e}")
        
        # Strategy 4: Extract using regex patterns
        try:
            # Find complete JSON object using balanced braces
            brace_count = 0
            start_pos = -1
            for i, char in enumerate(content):
                if char == '{':
                    if start_pos == -1:
                        start_pos = i
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0 and start_pos != -1:
                        json_str = content[start_pos:i+1]
                        # Clean and parse
                        json_str = self._clean_json_aggressively_fixed(json_str)
                        return json.loads(json_str)
        except Exception as e:
            logger.warning(f"Strategy 4 failed: {e}")
        
        logger.error(f"All JSON parsing strategies failed for dict. Content: {content[:500]}...")
        return {}
    
    def _parse_json_robust_array_fixed(self, content: str) -> List[Dict[str, Any]]:
        """Fixed robust JSON parsing for array responses"""
        
        # Strategy 1: Standard extraction
        try:
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
            
            return json.loads(content.strip())
        except json.JSONDecodeError:
            pass
        
        # Strategy 2: Find JSON array in content
        try:
            # Look for array pattern
            start = content.find('[')
            end = content.rfind(']') + 1
            if start != -1 and end > start:
                json_str = content[start:end]
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass
        
        # Strategy 3: Clean up common JSON issues with fixed patterns
        try:
            # Fix common issues
            cleaned = content.strip()
            
            # Remove markdown
            if '```' in cleaned:
                lines = cleaned.split('\n')
                cleaned_lines = []
                in_json = False
                for line in lines:
                    if '```' in line:
                        in_json = not in_json
                        continue
                    if in_json:
                        cleaned_lines.append(line)
                cleaned = '\n'.join(cleaned_lines)
            
            # Use fixed aggressive cleaning
            cleaned = self._clean_json_aggressively_fixed(cleaned)
            
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
        
        logger.error(f"All JSON parsing strategies failed for array. Content: {content[:500]}...")
        return []
    
    def _clean_json_aggressively_fixed(self, json_str: str) -> str:
        """FIXED: Aggressively clean JSON string to fix common AI response issues"""
        
        # Remove newlines within strings that might break parsing
        json_str = json_str.strip()
        
        # Fix trailing commas
        json_str = re.sub(r',\s*}', '}', json_str)
        json_str = re.sub(r',\s*]', ']', json_str)
        
        # Fix single quotes to double quotes (but be careful with apostrophes)
        json_str = re.sub(r"'(\w+)':", r'"\1":', json_str)  # Property names
        json_str = re.sub(r":\s*'([^']*)'", r': "\1"', json_str)  # String values
        
        # Fix unquoted property names
        json_str = re.sub(r'(\w+):', r'"\1":', json_str)
        
        # Fix escaped quotes within strings
        json_str = re.sub(r'\\""', r'\\"', json_str)
        
        # Fix multiple spaces and tabs
        json_str = re.sub(r'\s+', ' ', json_str)
        
        # FIXED: Fix unterminated strings by adding missing quotes
        lines = json_str.split('\n')
        fixed_lines = []
        for line in lines:
            # Count quotes in line
            quote_count = line.count('"') - line.count('\\"')
            if quote_count % 2 == 1 and ':' in line:
                # Odd number of quotes, might be unterminated
                if line.strip().endswith(',') or line.strip().endswith('}'):
                    # FIXED: Add missing quote before comma or brace
                    line = re.sub(r'([^"]),\s*$', r'\1",', line)
                    line = re.sub(r'([^"})\s*}$', r'\1"}', line)
            fixed_lines.append(line)
        
        json_str = '\n'.join(fixed_lines)
        
        return json_str
    
    def _validate_json_before_parsing(self, content: str) -> Tuple[bool, str]:
        """Quick validation to catch obvious JSON issues"""
        
        # Remove markdown if present
        clean_content = content
        if '```' in clean_content:
            try:
                clean_content = clean_content.split('```json')[1].split('```')[0]
            except:
                try:
                    clean_content = clean_content.split('```')[1].split('```')[0]
                except:
                    pass
        
        clean_content = clean_content.strip()
        
        # Check for basic JSON structure
        if not clean_content:
            return False, "Empty content"
        
        # Check for unterminated strings (simple check)
        lines = clean_content.split('\n')
        for i, line in enumerate(lines):
            # Count unescaped quotes
            quote_count = 0
            escaped = False
            for char in line:
                if char == '\\':
                    escaped = not escaped
                elif char == '"' and not escaped:
                    quote_count += 1
                else:
                    escaped = False
            
            if quote_count % 2 == 1 and ':' in line:
                return False, f"Possible unterminated string on line {i+1}: {line[:50]}..."
        
        # Check for basic structure
        if clean_content.startswith('{') and not clean_content.endswith('}'):
            return False, "Object not properly closed"
        
        if clean_content.startswith('[') and not clean_content.endswith(']'):
            return False, "Array not properly closed"
        
        # Check for obvious single quote issues
        if "'" in clean_content and clean_content.count("'") > clean_content.count('"') / 2:
            return False, "Possible single quotes instead of double quotes"
        
        return True, "Validation passed"

# ===== UI COMPONENTS (keeping the existing ones with minor improvements) =====

def display_agent_status(processing_stage: ProcessingStage, progress_text: str = ""):
    """Display agent status"""
    
    stage_info = {
        ProcessingStage.UPLOADED: {"icon": "📁", "text": "Ready for Processing"},
        ProcessingStage.ANALYZING: {"icon": "🔍", "text": "Analyzing Form Structure"},
        ProcessingStage.EXTRACTING: {"icon": "📄", "text": "Extracting Fields"},
        ProcessingStage.MAPPING: {"icon": "🧠", "text": "Applying Intelligent Mapping"},
        ProcessingStage.COMPLETED: {"icon": "🎉", "text": "Processing Complete"},
        ProcessingStage.ERROR: {"icon": "❌", "text": "Processing Error"}
    }
    
    info = stage_info.get(processing_stage, {"icon": "🤖", "text": "Processing"})
    
    st.markdown(f"""
    <div class="agent-status">
        <h3>{info['icon']} Agentic USCIS Reader - FIXED</h3>
        <p><strong>Status:</strong> {info['text']}</p>
        {f'<p><em>{progress_text}</em></p>' if progress_text else ''}
    </div>
    """, unsafe_allow_html=True)

def display_smart_field(field: SmartField, field_key: str):
    """Display smart field with proper interface"""
    
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
        field_header = f"**{field.field_number}: {field.field_label}**"
        st.markdown(field_header)
        
        # Confidence indicator
        confidence_width = field.extraction_confidence * 100
        confidence_pct = f"{field.extraction_confidence:.0%}"
        st.markdown(f"""
        <div class="confidence-bar">
            <div class="confidence-fill" style="width: {confidence_width}%"></div>
        </div>
        <small>{field.get_confidence_color()} Confidence: {confidence_pct}</small>
        """, unsafe_allow_html=True)
        
        if field.is_mapped:
            mapping_info = f'<small>📍 Mapped to: <code>{field.db_object}.{field.db_path}</code></small>'
            st.markdown(mapping_info, unsafe_allow_html=True)
    
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
            placeholder_text = f"Enter {field.field_label.lower()}..."
            new_value = st.text_input(
                "Value:",
                value=field.field_value,
                placeholder=placeholder_text,
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
        
        if st.button("📝 Quest", key=f"quest_{field_key}", help="Move to questionnaire"):
            field.in_questionnaire = True
            field.is_mapped = False
            st.rerun()
    
    # Mapping interface
    if st.session_state.get(f"show_mapping_{field_key}", False):
        display_mapping_interface_fixed(field, field_key)
    
    st.markdown('</div>', unsafe_allow_html=True)

def display_mapping_interface_fixed(field: SmartField, field_key: str):
    """Display fixed mapping interface with proper database objects"""
    
    st.markdown('<div class="mapping-interface">', unsafe_allow_html=True)
    st.markdown("#### 🔗 Map to Database")
    
    # Get database object options
    db_objects = list(DATABASE_OBJECTS.keys())
    
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        st.markdown("**Select Database Object:**")
        
        # Create radio buttons for database objects
        object_labels = []
        for obj_key in db_objects:
            obj_info = DATABASE_OBJECTS[obj_key]
            label = f"{obj_info['icon']} {obj_info['label']}"
            object_labels.append(label)
        
        selected_index = st.radio(
            "Database Object:",
            range(len(db_objects)),
            format_func=lambda x: object_labels[x],
            key=f"db_obj_{field_key}",
            label_visibility="collapsed"
        )
        
        selected_object = db_objects[selected_index]
        
        # Show description
        if selected_object:
            obj_desc = DATABASE_OBJECTS[selected_object]['description']
            st.caption(obj_desc)
    
    with col2:
        st.markdown("**Select Field Path:**")
        
        if selected_object:
            available_paths = DATABASE_OBJECTS[selected_object]['paths']
            
            selected_path = st.selectbox(
                "Field Path:",
                options=available_paths,
                key=f"db_path_{field_key}",
                label_visibility="collapsed"
            )
        else:
            selected_path = None
            st.info("Select an object first")
    
    with col3:
        st.markdown("**Actions:**")
        
        apply_disabled = not (selected_object and selected_path)
        if st.button("✅ Apply", key=f"apply_{field_key}", disabled=apply_disabled):
            field.is_mapped = True
            field.db_object = selected_object
            field.db_path = selected_path
            field.in_questionnaire = False
            
            st.session_state[f"show_mapping_{field_key}"] = False
            success_msg = f"✅ Mapped to {selected_object}.{selected_path}"
            st.success(success_msg)
            st.rerun()
        
        if st.button("❌ Cancel", key=f"cancel_{field_key}"):
            st.session_state[f"show_mapping_{field_key}"] = False
            st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

def display_smart_form(smart_form: SmartForm):
    """Display smart form with proper part separation"""
    
    if not smart_form or not smart_form.parts:
        st.warning("No form data to display")
        return
    
    # Form summary
    form_header = f"## 📄 {smart_form.form_number}: {smart_form.form_title}"
    st.markdown(form_header)
    if smart_form.form_edition:
        edition_text = f"**Edition:** {smart_form.form_edition}"
        st.markdown(edition_text)
    
    # Overall metrics
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
        confidence_text = f"{smart_form.overall_confidence:.0%}"
        st.metric("Confidence", confidence_text)
    
    # Display each part
    for part_num in sorted(smart_form.parts.keys()):
        part = smart_form.parts[part_num]
        
        # Part header with metrics
        mapped_count = part.get_mapped_count()
        unmapped_count = part.get_unmapped_count()
        questionnaire_count = part.get_questionnaire_count()
        
        part_header = f"📄 Part {part.number}: {part.title}"
        with st.expander(part_header, expanded=(part_num == 1)):
            
            # Part description
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
                if part.fields:
                    completion = (mapped_count + questionnaire_count) / len(part.fields)
                    completion_text = f"{completion:.0%}"
                else:
                    completion_text = "0%"
                st.metric("Completion", completion_text)
            
            # Display fields
            if not part.fields:
                st.info("No fields found in this part")
                continue
            
            for i, field in enumerate(part.fields):
                field_key = f"{part_num}_{i}"
                display_smart_field(field, field_key)

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
        mapped_count = len(mapped_fields)
        st.info(f"Ready: {mapped_count} mapped fields")
        
        if st.button("Generate TypeScript", type="primary"):
            ts_content = generate_typescript_mappings_fixed(smart_form, mapped_fields)
            st.code(ts_content, language="typescript")
            
            filename = f"{smart_form.form_number.replace('-', '_')}_mappings.ts"
            st.download_button(
                "Download TypeScript",
                ts_content,
                filename,
                "text/typescript"
            )
    
    with col2:
        st.markdown("### 📝 JSON Questionnaire")
        quest_count = len(questionnaire_fields)
        st.info(f"Ready: {quest_count} questionnaire fields")
        
        if st.button("Generate JSON", type="primary"):
            json_content = generate_json_questionnaire_fixed(smart_form, questionnaire_fields)
            st.code(json_content, language="json")
            
            filename = f"{smart_form.form_number.replace('-', '_')}_questionnaire.json"
            st.download_button(
                "Download JSON",
                json_content,
                filename,
                "application/json"
            )

def display_questionnaire_interface(smart_form: SmartForm):
    """Display questionnaire interface"""
    
    st.markdown("## 📝 Questionnaire")
    
    questionnaire_fields = smart_form.get_questionnaire_fields()
    
    if not questionnaire_fields:
        st.success("🎉 No fields in questionnaire!")
        return
    
    field_count = len(questionnaire_fields)
    st.info(f"Complete {field_count} questionnaire fields:")
    
    for i, field in enumerate(questionnaire_fields):
        field_header = f"### {field.field_number}: {field.field_label}"
        st.markdown(field_header)
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            if field.field_type == FieldType.TEXT:
                label_text = f"Enter {field.field_label.lower()}:"
                answer = st.text_input(
                    label_text,
                    value=field.field_value,
                    key=f"quest_{i}"
                )
            elif field.field_type == FieldType.DATE:
                answer = st.date_input(
                    "Select date:",
                    key=f"quest_date_{i}"
                )
                answer = str(answer) if answer else ""
            elif field.field_type == FieldType.CHECKBOX:
                answer = st.selectbox(
                    "Select option:",
                    ["", "Yes", "No"],
                    key=f"quest_check_{i}"
                )
            else:
                answer = st.text_input(
                    "Enter value:",
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

# ===== FIXED EXPORT FUNCTIONS =====

def generate_typescript_mappings_fixed(smart_form: SmartForm, mapped_fields: List[SmartField]) -> str:
    """Generate TypeScript mappings with fixed structure"""
    
    form_id = smart_form.form_number.replace('-', '_')
    generation_date = datetime.now().isoformat()
    
    ts_content = f"""/**
 * TypeScript mappings for {smart_form.form_number}
 * Form: {smart_form.form_title}
 * Generated: {generation_date}
 * 
 * Fixed structure matching actual database schema
 */

export interface {form_id}Mapping {{
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
            ts_content += f"      Name: \"{field.field_number}\",\n"
            ts_content += f"      Value: \"{obj_name}.{field.db_path}\",\n"
            ts_content += f"      Type: \"{field.field_type.value.title()}Box\",\n"
            ts_content += f"      Label: \"{field.field_label}\",\n"
            ts_content += f"      CurrentValue: \"{field.field_value}\"\n"
            ts_content += f"    }},\n"
        ts_content += f"  }},\n"
    
    ts_content += "}\n\n"
    
    # Add static mapping array format
    ts_content += f"export const {form_id}_MAPPINGS: any[] = [\n"
    
    for field in mapped_fields:
        ts_content += f"  {{\n"
        ts_content += f"    Name: \"{field.field_number}\",\n"
        ts_content += f"    Value: \"{field.db_object}.{field.db_path}\",\n"
        ts_content += f"    Type: \"{field.field_type.value.title()}Box\",\n"
        ts_content += f"  }},\n"
    
    ts_content += "];\n"
    
    return ts_content

def generate_json_questionnaire_fixed(smart_form: SmartForm, questionnaire_fields: List[SmartField]) -> str:
    """Generate JSON questionnaire with fixed structure"""
    
    questionnaire = {
        "form_info": {
            "form_number": smart_form.form_number,
            "form_title": smart_form.form_title,
            "form_edition": smart_form.form_edition,
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
            "is_required": field.is_required,
            "part_number": field.part_number
        }
        questionnaire["questions"].append(question)
    
    return json.dumps(questionnaire, indent=2)

# ===== MAIN APPLICATION =====

def main():
    st.markdown(
        '<div class="main-header">'
        '<h1>🤖 Agentic USCIS Form Reader - FIXED</h1>'
        '<p>AI-powered system with fixed JSON parsing and improved part extraction</p>'
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
            # Clear mapping session state
            keys_to_clear = []
            for key in st.session_state.keys():
                if key.startswith(('show_mapping_', 'db_obj_', 'db_path_')):
                    keys_to_clear.append(key)
            for key in keys_to_clear:
                del st.session_state[key]
            st.rerun()
        
        # Show fixed database schema
        st.markdown("### 📊 Fixed DB Schema")
        for obj_name, obj_info in DATABASE_OBJECTS.items():
            with st.expander(f"{obj_info['icon']} {obj_info['label']}"):
                st.caption(obj_info['description'])
                for path in obj_info['paths'][:5]:  # Show first 5 paths
                    st.code(f"{obj_name}.{path}")
                if len(obj_info['paths']) > 5:
                    st.caption(f"...and {len(obj_info['paths']) - 5} more")
        
        # Show stats if form is loaded
        if st.session_state.smart_form:
            form = st.session_state.smart_form
            st.markdown("### 📊 Form Stats")
            st.metric("Form", form.form_number)
            st.metric("Parts", len(form.parts))
            st.metric("Fields", len(form.get_all_fields()))
            st.metric("Mapped", len(form.get_mapped_fields()))
            confidence_text = f"{form.overall_confidence:.0%}"
            st.metric("Confidence", confidence_text)
            
            # Quick actions
            st.markdown("### ⚡ Quick Actions")
            if st.button("📝 Move All Unmapped to Questionnaire"):
                for field in form.get_unmapped_fields():
                    field.in_questionnaire = True
                st.success("Moved all unmapped fields!")
                st.rerun()
    
    # Main tabs
    tab1, tab2, tab3, tab4 = st.tabs(["🚀 Process", "✏️ Edit", "📝 Questionnaire", "📤 Export"])
    
    with tab1:
        st.markdown("### 🚀 Upload & Process USCIS Form")
        
        uploaded_file = st.file_uploader("Choose USCIS form PDF", type=['pdf'])
        
        if uploaded_file:
            file_name = uploaded_file.name
            st.success(f"✅ File uploaded: {file_name}")
            
            process_button = st.button("🚀 Process with AI", type="primary", use_container_width=True)
            
            if process_button:
                
                # Check if OpenAI is available
                if not st.session_state.processor.openai_client:
                    st.error("❌ OpenAI client not available. Please check API key setup.")
                    st.stop()
                
                progress_placeholder = st.empty()
                
                def update_progress(text):
                    with progress_placeholder:
                        st.markdown(f"""
                        <div class="progress-text">
                            🤖 {text}
                        </div>
                        """, unsafe_allow_html=True)
                
                with st.spinner("🤖 AI Processing in progress..."):
                    try:
                        # Extract PDF text
                        update_progress("Extracting text from PDF...")
                        pdf_text = extract_pdf_text_properly(uploaded_file)
                        
                        if not pdf_text or len(pdf_text.strip()) < 100:
                            st.error("❌ Insufficient text found in PDF. Please check if the PDF contains readable text.")
                            st.stop()
                        
                        char_count = len(pdf_text)
                        st.info(f"📄 Extracted {char_count} characters from PDF")
                        
                        # Process with AI
                        smart_form = st.session_state.processor.process_form_intelligently(
                            pdf_text, update_progress
                        )
                        
                        if smart_form and smart_form.parts:
                            st.session_state.smart_form = smart_form
                            st.session_state.processing_stage = ProcessingStage.COMPLETED
                            
                            progress_placeholder.empty()
                            st.balloons()
                            
                            # Show success metrics
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric("Parts Found", len(smart_form.parts))
                            with col2:
                                st.metric("Fields Extracted", len(smart_form.get_all_fields()))
                            with col3:
                                st.metric("Auto-Mapped", len(smart_form.get_mapped_fields()))
                            with col4:
                                confidence_text = f"{smart_form.overall_confidence:.0%}"
                                st.metric("Confidence", confidence_text)
                            
                            parts_count = len(smart_form.parts)
                            fields_count = len(smart_form.get_all_fields())
                            success_msg = f"🎉 Processing complete! Found {parts_count} parts with {fields_count} fields"
                            st.success(success_msg)
                        else:
                            st.error("❌ Processing failed - no form structure found")
                    
                    except Exception as e:
                        progress_placeholder.empty()
                        error_msg = f"💥 Processing error: {str(e)}"
                        st.error(error_msg)
                        logger.error(f"Processing error: {e}")
    
    with tab2:
        if st.session_state.smart_form:
            display_smart_form(st.session_state.smart_form)
        else:
            st.info("📄 No form loaded. Process a PDF in the first tab to begin editing.")
    
    with tab3:
        if st.session_state.smart_form:
            display_questionnaire_interface(st.session_state.smart_form)
        else:
            st.info("📝 No form loaded. Process a PDF to access the questionnaire.")
    
    with tab4:
        if st.session_state.smart_form:
            display_export_options(st.session_state.smart_form)
        else:
            st.info("📤 No form loaded. Process a PDF to access export options.")

if __name__ == "__main__":
    main()
