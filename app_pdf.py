#!/usr/bin/env python3
"""
🤖 SIMPLIFIED USCIS FORM READER
===============================

Simplified, practical version with:
- Better field extraction and sequencing
- User-friendly database mapping
- Manual entry options
- Clean interface without unnecessary indicators

Author: AI Assistant  
Version: 5.0.0 - SIMPLIFIED
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
    page_title="🤖 USCIS Form Reader - Simplified",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Clean CSS
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
        background: #f5f5f5;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    
    .part-header {
        background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%);
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
        font-weight: bold;
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

@dataclass
class SmartField:
    field_number: str
    field_label: str
    field_value: str = ""
    field_type: FieldType = FieldType.TEXT
    part_number: int = 1
    is_mapped: bool = False
    db_object: str = ""
    db_path: str = ""
    in_questionnaire: bool = False
    is_required: bool = False
    manually_edited: bool = False

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
    
    def add_part(self, part: SmartPart):
        self.parts[part.number] = part
    
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

# ===== DATABASE SCHEMA =====

DATABASE_OBJECTS = {
    "beneficiary": {
        "label": "Beneficiary Information",
        "icon": "👤",
        "common_paths": [
            "beneficiaryFirstName",
            "beneficiaryLastName", 
            "beneficiaryMiddleName",
            "beneficiaryDateOfBirth",
            "beneficiarySsn",
            "alienNumber",
            "beneficiaryCountryOfBirth",
            "beneficiaryCitizenOfCountry",
            "beneficiaryCellNumber",
            "beneficiaryWorkNumber",
            "beneficiaryPrimaryEmailAddress",
            "homeAddress.addressStreet",
            "homeAddress.addressCity",
            "homeAddress.addressState",
            "homeAddress.addressZip",
            "workAddress.addressStreet",
            "workAddress.addressCity",
            "workAddress.addressState",
            "workAddress.addressZip"
        ]
    },
    "attorney": {
        "label": "Attorney Information",
        "icon": "⚖️",
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
            "lawfirmDetails.lawFirmName",
            "uscisRepresentation"
        ]
    },
    "employer": {
        "label": "Employer/Company Information",
        "icon": "🏢",
        "common_paths": [
            "customer_name",
            "customer_tax_id",
            "signatory_first_name",
            "signatory_last_name", 
            "signatory_work_phone",
            "signatory_email_id",
            "address_street",
            "address_city",
            "address_state",
            "address_zip"
        ]
    },
    "case": {
        "label": "Case Information",
        "icon": "📋",
        "common_paths": [
            "caseNumber",
            "receiptNumber",
            "filingDate",
            "priority",
            "status"
        ]
    }
}

# ===== PDF PROCESSING =====

def extract_pdf_text_properly(pdf_file) -> str:
    """Extract PDF text with better structure preservation"""
    try:
        st.info("📄 Processing PDF...")
        
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
            page_count = len(doc)
            st.success(f"✅ PDF opened - {page_count} pages")
            
            page_texts = []
            
            for page_num in range(page_count):
                try:
                    page = doc[page_num]
                    page_text = page.get_text()
                    
                    if page_text.strip():
                        page_header = f"=== PAGE {page_num + 1} ==="
                        page_texts.append(f"{page_header}\n{page_text}")
                        
                except Exception as e:
                    st.warning(f"⚠️ Error on page {page_num + 1}: {str(e)}")
                    continue
            
            full_text = "\n\n".join(page_texts)
            
            if not full_text.strip():
                st.error("❌ No text found in PDF")
                return ""
            
            st.success(f"✅ Extracted {len(full_text)} characters")
            return full_text
            
        finally:
            doc.close()
            
    except Exception as e:
        st.error(f"💥 PDF extraction failed: {str(e)}")
        return ""

# ===== IMPROVED FORM PROCESSOR =====

class FormProcessor:
    """Simplified form processor focusing on better extraction"""
    
    def __init__(self):
        self.openai_client = None
        self.setup_openai()
    
    def setup_openai(self):
        """Setup OpenAI client"""
        try:
            api_key = None
            
            if hasattr(st, 'secrets') and 'OPENAI_API_KEY' in st.secrets:
                api_key = st.secrets['OPENAI_API_KEY']
                st.sidebar.success("🔑 API key from secrets")
            elif os.getenv('OPENAI_API_KEY'):
                api_key = os.getenv('OPENAI_API_KEY')
                st.sidebar.success("🔑 API key from environment")
            
            if not api_key:
                st.error("🔑 **OpenAI API Key Required!** Please add to secrets or environment.")
                return
            
            self.openai_client = openai.OpenAI(api_key=api_key)
            
            # Quick test
            try:
                self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": "test"}],
                    max_tokens=1
                )
                st.sidebar.success("✅ OpenAI connected!")
            except Exception as e:
                st.error(f"❌ OpenAI test failed: {str(e)}")
                self.openai_client = None
                
        except Exception as e:
            st.error(f"❌ OpenAI setup failed: {str(e)}")
            self.openai_client = None
    
    def process_form(self, pdf_text: str, progress_callback=None) -> SmartForm:
        """Process form with improved extraction"""
        
        if not self.openai_client:
            st.error("❌ OpenAI not available")
            return None
        
        try:
            # Step 1: Analyze form structure
            if progress_callback:
                progress_callback("🔍 Analyzing form structure...")
            
            form_data = self._analyze_form_structure(pdf_text)
            
            if not form_data:
                st.error("❌ Failed to analyze form")
                return None
            
            # Step 2: Create form object
            smart_form = SmartForm(
                form_number=form_data.get('form_number', 'Unknown'),
                form_title=form_data.get('form_title', 'Unknown Form'),
                form_edition=form_data.get('form_edition', ''),
                processing_stage=ProcessingStage.EXTRACTING
            )
            
            # Step 3: Extract fields with better sequencing
            if progress_callback:
                progress_callback("📄 Extracting all fields...")
            
            all_fields = self._extract_all_fields_improved(pdf_text)
            
            # Step 4: Organize into parts
            parts_data = form_data.get('parts', [])
            
            for part_data in parts_data:
                part_number = part_data.get('number', 1)
                part_title = part_data.get('title', f'Part {part_number}')
                
                smart_part = SmartPart(
                    number=part_number,
                    title=part_title,
                    description=part_data.get('description', '')
                )
                
                # Assign fields to parts based on field numbers or content
                part_fields = self._assign_fields_to_part(all_fields, part_number, part_title)
                
                for field in part_fields:
                    smart_part.add_field(field)
                
                smart_form.add_part(smart_part)
            
            # Add any remaining unassigned fields to a general part
            unassigned_fields = [f for f in all_fields if not any(
                f in part.fields for part in smart_form.parts.values()
            )]
            
            if unassigned_fields:
                general_part = SmartPart(
                    number=99,
                    title="Additional Fields",
                    description="Fields not assigned to specific parts"
                )
                for field in unassigned_fields:
                    general_part.add_field(field)
                smart_form.add_part(general_part)
            
            smart_form.processing_stage = ProcessingStage.COMPLETED
            return smart_form
            
        except Exception as e:
            logger.error(f"Processing failed: {e}")
            st.error(f"❌ Processing error: {str(e)}")
            return None
    
    def _analyze_form_structure(self, pdf_text: str) -> Dict[str, Any]:
        """Analyze form to identify structure and parts"""
        
        analysis_text = pdf_text[:15000]
        
        prompt = f"""
        Analyze this USCIS form and identify its structure.
        
        Return valid JSON with this exact structure:
        {{
            "form_number": "I-90",
            "form_title": "Application to Replace Permanent Resident Card",
            "form_edition": "01/20/25",
            "parts": [
                {{
                    "number": 1,
                    "title": "Information About You",
                    "description": "Personal information"
                }},
                {{
                    "number": 2,
                    "title": "Application Type",
                    "description": "Reason for application"
                }}
            ]
        }}
        
        Look for patterns like:
        - "Part 1.", "Part 2.", etc.
        - Form number (I-90, I-129, G-28, etc.)
        - Form title
        - Edition date
        
        Form text:
        {analysis_text}
        """
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=1500
            )
            
            content = response.choices[0].message.content.strip()
            
            # Clean and parse JSON
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
            
            data = json.loads(content.strip())
            
            # Ensure we have parts
            if not data.get('parts'):
                data['parts'] = [
                    {"number": 1, "title": "Information About You", "description": "Personal information"},
                    {"number": 2, "title": "Application Information", "description": "Application details"},
                    {"number": 3, "title": "Additional Information", "description": "Other information"}
                ]
            
            return data
            
        except Exception as e:
            logger.error(f"Form analysis failed: {e}")
            # Return fallback
            return {
                'form_number': 'Unknown',
                'form_title': 'USCIS Form',
                'form_edition': '',
                'parts': [
                    {"number": 1, "title": "Information About You", "description": "Personal information"},
                    {"number": 2, "title": "Application Information", "description": "Application details"}
                ]
            }
    
    def _extract_all_fields_improved(self, pdf_text: str) -> List[SmartField]:
        """Extract ALL fields with better sequencing and completeness"""
        
        # Use more text for better field extraction
        extraction_text = pdf_text[:25000]
        
        prompt = f"""
        Extract ALL form fields from this USCIS form text in the order they appear.
        
        Look for these patterns:
        1. Numbered items: "1.a.", "1.b.", "2.a.", "2.b.", etc.
        2. Name fields: "Family Name", "Given Name", "Middle Name"
        3. Address fields: "Street Number and Name", "City", "State", "ZIP Code"
        4. Contact fields: "Daytime Phone", "Mobile Phone", "Email Address"
        5. Date fields: "Date of Birth", "Date of Entry", etc.
        6. ID fields: "A-Number", "Social Security Number", "USCIS Online Account"
        7. Checkbox options and Yes/No questions
        8. Signature and date fields
        
        Return a JSON array with ALL fields in order:
        [
            {{
                "field_number": "1.a.",
                "field_label": "Family Name (Last Name)",
                "field_type": "text",
                "is_required": true
            }},
            {{
                "field_number": "1.b.",
                "field_label": "Given Name (First Name)",
                "field_type": "text",
                "is_required": true
            }},
            {{
                "field_number": "2.",
                "field_label": "Date of Birth",
                "field_type": "date",
                "is_required": true
            }}
        ]
        
        Valid field_type values: text, date, checkbox, number, email, phone, address, ssn, alien_number
        
        Extract EVERY field you can find, maintaining the original sequence.
        
        Form text:
        {extraction_text}
        """
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=4000
            )
            
            content = response.choices[0].message.content.strip()
            
            # Clean and parse JSON
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
            
            # Find JSON array
            start = content.find('[')
            end = content.rfind(']') + 1
            if start != -1 and end > start:
                content = content[start:end]
            
            fields_data = json.loads(content.strip())
            
            fields = []
            for i, field_data in enumerate(fields_data):
                try:
                    field_type_str = field_data.get('field_type', 'text')
                    try:
                        field_type = FieldType(field_type_str)
                    except ValueError:
                        field_type = FieldType.TEXT
                    
                    field = SmartField(
                        field_number=field_data.get('field_number', f'Field_{i+1}'),
                        field_label=field_data.get('field_label', 'Unknown Field'),
                        field_value="",
                        field_type=field_type,
                        is_required=field_data.get('is_required', False)
                    )
                    
                    fields.append(field)
                    
                except Exception as e:
                    logger.error(f"Failed to create field {i}: {e}")
                    continue
            
            st.success(f"✅ Extracted {len(fields)} fields")
            return fields
            
        except Exception as e:
            logger.error(f"Field extraction failed: {e}")
            st.warning(f"⚠️ Field extraction failed, using fallback")
            return self._create_fallback_fields()
    
    def _assign_fields_to_part(self, all_fields: List[SmartField], part_number: int, part_title: str) -> List[SmartField]:
        """Assign fields to appropriate parts"""
        
        assigned_fields = []
        
        for field in all_fields:
            # Check if field number indicates it belongs to this part
            field_num = field.field_number.lower()
            
            # Direct part number match (e.g., "1.a." belongs to Part 1)
            if field_num.startswith(f'{part_number}.'):
                assigned_fields.append(field)
                continue
            
            # Content-based assignment
            field_label_lower = field.field_label.lower()
            part_title_lower = part_title.lower()
            
            if part_number == 1 or 'information about you' in part_title_lower:
                # Personal information fields
                if any(keyword in field_label_lower for keyword in [
                    'name', 'birth', 'social security', 'a-number', 'country', 'citizenship'
                ]):
                    assigned_fields.append(field)
            
            elif part_number == 2 or 'application' in part_title_lower:
                # Application type fields
                if any(keyword in field_label_lower for keyword in [
                    'application', 'petition', 'reason', 'category', 'type'
                ]):
                    assigned_fields.append(field)
            
            elif part_number == 3 or 'processing' in part_title_lower or 'contact' in part_title_lower:
                # Contact and processing fields
                if any(keyword in field_label_lower for keyword in [
                    'address', 'phone', 'email', 'mailing', 'contact'
                ]):
                    assigned_fields.append(field)
        
        return assigned_fields
    
    def _create_fallback_fields(self) -> List[SmartField]:
        """Create basic fallback fields"""
        
        fallback_templates = [
            ("1.a.", "Family Name (Last Name)", FieldType.TEXT),
            ("1.b.", "Given Name (First Name)", FieldType.TEXT),
            ("1.c.", "Middle Name", FieldType.TEXT),
            ("2.", "Date of Birth", FieldType.DATE),
            ("3.", "Country of Birth", FieldType.TEXT),
            ("4.", "Country of Citizenship", FieldType.TEXT),
            ("5.", "U.S. Social Security Number", FieldType.SSN),
            ("6.", "A-Number", FieldType.ALIEN_NUMBER),
            ("7.a.", "Street Number and Name", FieldType.ADDRESS),
            ("7.b.", "City or Town", FieldType.TEXT),
            ("7.c.", "State", FieldType.TEXT),
            ("7.d.", "ZIP Code", FieldType.TEXT),
            ("8.", "Daytime Phone Number", FieldType.PHONE),
            ("9.", "Mobile Phone Number", FieldType.PHONE),
            ("10.", "Email Address", FieldType.EMAIL)
        ]
        
        fields = []
        for field_num, field_label, field_type in fallback_templates:
            field = SmartField(
                field_number=field_num,
                field_label=field_label,
                field_value="",
                field_type=field_type,
                is_required=False
            )
            fields.append(field)
        
        return fields

# ===== UI COMPONENTS =====

def display_field_simple(field: SmartField, field_key: str):
    """Simplified field display without confidence indicators"""
    
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
        status_text = "Unmapped"
    
    st.markdown(f'<div class="field-card {status_class}">', unsafe_allow_html=True)
    
    # Field header
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.markdown(f"**{field.field_number}: {field.field_label}**")
        
        if field.is_mapped:
            mapping_info = f"📍 **{field.db_object}** → `{field.db_path}`"
            st.markdown(mapping_info)
    
    with col2:
        st.markdown(f"{status_icon} **{status_text}**")
        if field.field_type != FieldType.TEXT:
            st.caption(f"Type: {field.field_type.value}")
    
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
                label_visibility="collapsed"
            )
        
        # Update field value if changed
        if new_value != field.field_value:
            field.field_value = new_value
            field.manually_edited = True
    
    with col2:
        # Action buttons
        if st.button("🔗 Map", key=f"map_{field_key}"):
            st.session_state[f"show_mapping_{field_key}"] = True
            st.rerun()
        
        if st.button("📝 Quest", key=f"quest_{field_key}"):
            field.in_questionnaire = True
            field.is_mapped = False
            st.rerun()
    
    # Mapping interface
    if st.session_state.get(f"show_mapping_{field_key}", False):
        display_mapping_interface_simple(field, field_key)
    
    st.markdown('</div>', unsafe_allow_html=True)

def display_mapping_interface_simple(field: SmartField, field_key: str):
    """Simplified mapping interface with better user control"""
    
    st.markdown('<div class="mapping-section">', unsafe_allow_html=True)
    st.markdown("### 🔗 Map to Database")
    
    # Show current mapping if exists
    if field.is_mapped:
        st.info(f"Currently mapped to: **{field.db_object}** → `{field.db_path}`")
    
    # Tab for different mapping options
    tab1, tab2 = st.tabs(["📋 Select from Database Objects", "✏️ Manual Entry"])
    
    with tab1:
        st.markdown("**Step 1: Choose Database Object**")
        
        # Create clearer database object options
        db_options = [
            ("beneficiary", "👤 Beneficiary Information", "Primary applicant details"),
            ("attorney", "⚖️ Attorney Information", "Legal representative details"), 
            ("employer", "🏢 Employer/Company Information", "Petitioning organization details"),
            ("case", "📋 Case Information", "Case-specific details")
        ]
        
        # Show radio buttons for better visibility
        selected_obj_key = st.radio(
            "Select the database object for this field:",
            options=[opt[0] for opt in db_options],
            format_func=lambda x: next(opt[1] for opt in db_options if opt[0] == x),
            key=f"obj_radio_{field_key}",
            help="Choose which database object this field should map to"
        )
        
        # Show description
        selected_description = next(opt[2] for opt in db_options if opt[0] == selected_obj_key)
        st.caption(f"📝 {selected_description}")
        
        st.markdown("---")
        st.markdown("**Step 2: Choose Field Path**")
        
        if selected_obj_key and selected_obj_key in DATABASE_OBJECTS:
            common_paths = DATABASE_OBJECTS[selected_obj_key]['common_paths']
            
            # Show common paths with better display
            st.markdown("**Common field paths:**")
            
            path_choice = st.radio(
                "Select field path:",
                options=["common", "custom"],
                format_func=lambda x: "Choose from common paths" if x == "common" else "Enter custom path",
                key=f"path_choice_{field_key}",
                horizontal=True
            )
            
            if path_choice == "common":
                selected_path = st.selectbox(
                    "Choose field path:",
                    options=common_paths,
                    key=f"path_select_{field_key}",
                    help="Select the specific database field this form field should map to"
                )
            else:
                selected_path = st.text_input(
                    "Enter custom field path:",
                    key=f"custom_path_{field_key}",
                    placeholder="e.g., customField.subField",
                    help="Enter a custom database field path"
                )
        else:
            selected_path = ""
        
        st.markdown("---")
        
        # Apply mapping with validation
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col2:
            if st.button("✅ Apply Mapping", key=f"apply_sel_{field_key}", type="primary", use_container_width=True):
                if selected_obj_key and selected_path:
                    field.is_mapped = True
                    field.db_object = selected_obj_key
                    field.db_path = selected_path
                    field.in_questionnaire = False
                    st.session_state[f"show_mapping_{field_key}"] = False
                    st.success(f"✅ Mapped to **{selected_obj_key}**.{selected_path}")
                    st.rerun()
                else:
                    st.error("Please select both database object and field path")
        
        with col3:
            if st.button("❌ Cancel", key=f"cancel_sel_{field_key}", use_container_width=True):
                st.session_state[f"show_mapping_{field_key}"] = False
                st.rerun()
    
    with tab2:
        st.markdown("**Manual Database Mapping**")
        st.caption("Enter database object and field path manually")
        
        col1, col2 = st.columns(2)
        
        with col1:
            manual_object = st.text_input(
                "Database Object:",
                value=field.db_object if field.is_mapped else "",
                key=f"manual_obj_{field_key}",
                placeholder="e.g., beneficiary, attorney, employer, case",
                help="Enter the name of the database object"
            )
        
        with col2:
            manual_path = st.text_input(
                "Field Path:",
                value=field.db_path if field.is_mapped else "",
                key=f"manual_path_{field_key}",
                placeholder="e.g., firstName, address.street",
                help="Enter the field path within the database object"
            )
        
        # Show example
        if manual_object and manual_path:
            st.info(f"💡 This will map to: **{manual_object}**.{manual_path}")
        
        # Apply manual mapping
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col2:
            if st.button("✅ Apply Manual", key=f"apply_man_{field_key}", type="primary", use_container_width=True):
                if manual_object.strip() and manual_path.strip():
                    field.is_mapped = True
                    field.db_object = manual_object.strip()
                    field.db_path = manual_path.strip()
                    field.in_questionnaire = False
                    st.session_state[f"show_mapping_{field_key}"] = False
                    st.success(f"✅ Manually mapped to **{manual_object}**.{manual_path}")
                    st.rerun()
                else:
                    st.error("Please enter both database object and field path")
        
        with col3:
            if st.button("❌ Cancel", key=f"cancel_man_{field_key}", use_container_width=True):
                st.session_state[f"show_mapping_{field_key}"] = False
                st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

def display_form_simple(smart_form: SmartForm):
    """Simplified form display"""
    
    if not smart_form or not smart_form.parts:
        st.warning("No form data to display")
        return
    
    # Form header
    st.markdown(f"## 📄 {smart_form.form_number}: {smart_form.form_title}")
    if smart_form.form_edition:
        st.markdown(f"**Edition:** {smart_form.form_edition}")
    
    # Summary stats
    col1, col2, col3, col4 = st.columns(4)
    
    all_fields = smart_form.get_all_fields()
    mapped_fields = smart_form.get_mapped_fields()
    questionnaire_fields = smart_form.get_questionnaire_fields()
    
    with col1:
        st.metric("Total Fields", len(all_fields))
    with col2:
        st.metric("Mapped", len(mapped_fields))
    with col3:
        st.metric("Questionnaire", len(questionnaire_fields))
    with col4:
        unmapped_count = len(all_fields) - len(mapped_fields) - len(questionnaire_fields)
        st.metric("Unmapped", unmapped_count)
    
    # Display parts
    for part_num in sorted(smart_form.parts.keys()):
        part = smart_form.parts[part_num]
        
        # Part header
        st.markdown(f'<div class="part-header">📄 Part {part.number}: {part.title}</div>', unsafe_allow_html=True)
        
        if part.description:
            st.markdown(f"*{part.description}*")
        
        # Show fields in this part
        if not part.fields:
            st.info("No fields found in this part")
            continue
        
        # Display fields in columns for better layout
        for i, field in enumerate(part.fields):
            field_key = f"{part_num}_{i}"
            display_field_simple(field, field_key)

def display_export_simple(smart_form: SmartForm):
    """Simplified export options"""
    
    st.markdown("## 📤 Export Results")
    
    if not smart_form:
        st.warning("No form data to export")
        return
    
    mapped_fields = smart_form.get_mapped_fields()
    questionnaire_fields = smart_form.get_questionnaire_fields()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🔗 Database Mappings")
        st.info(f"Ready: {len(mapped_fields)} mapped fields")
        
        if mapped_fields and st.button("📋 Generate Mappings", type="primary"):
            mappings_content = generate_mappings_simple(smart_form, mapped_fields)
            st.code(mappings_content, language="json")
            
            filename = f"{smart_form.form_number.replace('-', '_')}_mappings.json"
            st.download_button(
                "💾 Download Mappings",
                mappings_content,
                filename,
                "application/json"
            )
    
    with col2:
        st.markdown("### 📝 Questionnaire")
        st.info(f"Ready: {len(questionnaire_fields)} fields")
        
        if questionnaire_fields and st.button("📋 Generate Questionnaire", type="primary"):
            questionnaire_content = generate_questionnaire_simple(smart_form, questionnaire_fields)
            st.code(questionnaire_content, language="json")
            
            filename = f"{smart_form.form_number.replace('-', '_')}_questionnaire.json"
            st.download_button(
                "💾 Download Questionnaire",
                questionnaire_content,
                filename,
                "application/json"
            )

def display_questionnaire_simple(smart_form: SmartForm):
    """Simplified questionnaire interface"""
    
    st.markdown("## 📝 Complete Questionnaire")
    
    questionnaire_fields = smart_form.get_questionnaire_fields()
    
    if not questionnaire_fields:
        st.info("✨ No fields in questionnaire! Use the 'Quest' button to move fields here.")
        return
    
    st.info(f"Complete these {len(questionnaire_fields)} fields:")
    
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
            if st.button("🔙 Move Back", key=f"back_{i}"):
                field.in_questionnaire = False
                st.rerun()

# ===== EXPORT FUNCTIONS =====

def generate_mappings_simple(smart_form: SmartForm, mapped_fields: List[SmartField]) -> str:
    """Generate simple mappings JSON"""
    
    mappings = {
        "form_info": {
            "form_number": smart_form.form_number,
            "form_title": smart_form.form_title,
            "form_edition": smart_form.form_edition,
            "generated": datetime.now().isoformat()
        },
        "mappings": []
    }
    
    for field in mapped_fields:
        mapping = {
            "field_number": field.field_number,
            "field_label": field.field_label,
            "field_type": field.field_type.value,
            "db_object": field.db_object,
            "db_path": field.db_path,
            "current_value": field.field_value
        }
        mappings["mappings"].append(mapping)
    
    return json.dumps(mappings, indent=2)

def generate_questionnaire_simple(smart_form: SmartForm, questionnaire_fields: List[SmartField]) -> str:
    """Generate simple questionnaire JSON"""
    
    questionnaire = {
        "form_info": {
            "form_number": smart_form.form_number,
            "form_title": smart_form.form_title,
            "generated": datetime.now().isoformat()
        },
        "questions": []
    }
    
    for field in questionnaire_fields:
        question = {
            "field_number": field.field_number,
            "question": field.field_label,
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
        '<h1>🤖 USCIS Form Reader - Simplified</h1>'
        '<p>Clean, practical tool for extracting and mapping USCIS form fields</p>'
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
        st.session_state.processor = FormProcessor()
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 🎛️ Controls")
        
        if st.button("🆕 New Form", type="primary"):
            st.session_state.smart_form = None
            st.session_state.processing_stage = ProcessingStage.UPLOADED
            # Clear all field mapping states
            for key in list(st.session_state.keys()):
                if key.startswith(('show_mapping_', 'obj_select_', 'path_select_')):
                    del st.session_state[key]
            st.rerun()
        
        # Show database objects reference
        st.markdown("### 📊 Database Objects")
        for obj_name, obj_info in DATABASE_OBJECTS.items():
            with st.expander(f"{obj_info['icon']} {obj_info['label']}"):
                st.caption("Common fields:")
                for path in obj_info['common_paths'][:8]:
                    st.code(path, language=None)
                if len(obj_info['common_paths']) > 8:
                    st.caption(f"...and {len(obj_info['common_paths']) - 8} more")
        
        # Show form stats
        if st.session_state.smart_form:
            form = st.session_state.smart_form
            st.markdown("### 📈 Current Form")
            st.metric("Form", form.form_number)
            st.metric("Total Fields", len(form.get_all_fields()))
            st.metric("Mapped", len(form.get_mapped_fields()))
            st.metric("Questionnaire", len(form.get_questionnaire_fields()))
            
            # Bulk actions
            st.markdown("### ⚡ Bulk Actions")
            if st.button("📝 All Unmapped → Questionnaire"):
                for field in form.get_unmapped_fields():
                    field.in_questionnaire = True
                st.success("Moved all unmapped fields to questionnaire!")
                st.rerun()
    
    # Main interface
    tab1, tab2, tab3, tab4 = st.tabs(["🚀 Process", "✏️ Map Fields", "📝 Questionnaire", "📤 Export"])
    
    with tab1:
        st.markdown("### 🚀 Upload & Process USCIS Form")
        
        uploaded_file = st.file_uploader("Choose USCIS form PDF", type=['pdf'])
        
        if uploaded_file:
            st.success(f"✅ File uploaded: {uploaded_file.name}")
            
            if st.button("🚀 Process with AI", type="primary", use_container_width=True):
                if not st.session_state.processor.openai_client:
                    st.error("❌ OpenAI not available. Check API key setup.")
                    st.stop()
                
                progress_placeholder = st.empty()
                
                def update_progress(text):
                    progress_placeholder.info(f"🤖 {text}")
                
                with st.spinner("🤖 Processing..."):
                    try:
                        # Extract PDF
                        update_progress("Extracting text from PDF...")
                        pdf_text = extract_pdf_text_properly(uploaded_file)
                        
                        if not pdf_text or len(pdf_text.strip()) < 100:
                            st.error("❌ Insufficient text in PDF")
                            st.stop()
                        
                        # Process with AI
                        smart_form = st.session_state.processor.process_form(
                            pdf_text, update_progress
                        )
                        
                        if smart_form and smart_form.parts:
                            st.session_state.smart_form = smart_form
                            st.session_state.processing_stage = ProcessingStage.COMPLETED
                            
                            progress_placeholder.empty()
                            st.balloons()
                            
                            # Success summary
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Parts Found", len(smart_form.parts))
                            with col2:
                                st.metric("Fields Extracted", len(smart_form.get_all_fields()))
                            with col3:
                                st.metric("Ready to Map", len(smart_form.get_unmapped_fields()))
                            
                            st.success(f"🎉 Successfully processed {smart_form.form_number}!")
                        else:
                            st.error("❌ Processing failed")
                    
                    except Exception as e:
                        progress_placeholder.empty()
                        st.error(f"💥 Error: {str(e)}")
    
    with tab2:
        if st.session_state.smart_form:
            display_form_simple(st.session_state.smart_form)
        else:
            st.info("📄 Upload and process a form first")
    
    with tab3:
        if st.session_state.smart_form:
            display_questionnaire_simple(st.session_state.smart_form)
        else:
            st.info("📝 Process a form first")
    
    with tab4:
        if st.session_state.smart_form:
            display_export_simple(st.session_state.smart_form)
        else:
            st.info("📤 Process a form first")

if __name__ == "__main__":
    main()
