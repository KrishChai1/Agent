#!/usr/bin/env python3
"""
Corrected USCIS Form Processing System
- Extracts actual field values (not database objects)
- Uses knowledge base for field mappings
- Separates mapped vs unmapped fields
- Maintains proper field sequence
- Provides questionnaire for unmapped fields
- Exports mapped data in TypeScript format
- Exports questionnaire data in JSON format
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
    page_title="Corrected USCIS Form Processor",
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
    
    .field-mapped {
        background: #e8f5e9;
        border-left: 4px solid #28a745;
    }
    
    .field-unmapped {
        background: #fff3cd;
        border-left: 4px solid #ffc107;
    }
    
    .field-missing {
        background: #ffebee;
        border-left: 4px solid #f44336;
    }
    
    .export-section {
        background: #e3f2fd;
        border: 1px solid #90caf9;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
    }
    
    .mapping-info {
        background: #f3e5f5;
        border: 1px solid #ce93d8;
        border-radius: 4px;
        padding: 0.5rem;
        margin: 0.5rem 0;
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)

# ===== KNOWLEDGE BASE MAPPINGS =====
def get_form_mappings(form_number: str) -> Dict[str, Any]:
    """Get field mappings from knowledge base for specific form"""
    
    # G-28 mappings from knowledge base
    G28_MAPPINGS = {
        "pt3_1a": {"db_path": "attorney.attorneyInfo.uscisRepresentation", "type": "CheckBox"},
        "pt3_1b": {"db_path": "attorney.attorneyInfo.formNumbers", "type": "TextBox"},
        "pt3_2a": {"db_path": "attorney.attorneyInfo.iceRepresentation", "type": "CheckBox"},
        "pt3_2b": {"db_path": "attorney.attorneyInfo.iceMatters", "type": "TextBox"},
        "pt3_3a": {"db_path": "attorney.attorneyInfo.cbpRepresentation", "type": "CheckBox"},
        "pt3_3b": {"db_path": "attorney.attorneyInfo.cbpMatters", "type": "TextBox"},
        "pt3_4": {"db_path": "attorney.attorneyInfo.receiptNumber", "type": "TextBox"},
        "pt3_5_applicant": {"db_path": "attorney.attorneyInfo.representativeType", "type": "RadioBox"},
        "pt3_5_petitioner": {"db_path": "attorney.attorneyInfo.representativeType", "type": "RadioBox"},
        "pt3_5_requestor": {"db_path": "attorney.attorneyInfo.representativeType", "type": "RadioBox"},
        "pt3_5_beneficiary": {"db_path": "attorney.attorneyInfo.representativeType", "type": "RadioBox"},
        "pt3_5_respondent": {"db_path": "attorney.attorneyInfo.representativeType", "type": "RadioBox"},
        "pt4_6a_family_name": {"db_path": "customer.signatory_last_name", "type": "TextBox"},
        "pt4_6b_given_name": {"db_path": "customer.signatory_first_name", "type": "TextBox"},
        "pt4_6c_middle_name": {"db_path": "customer.signatory_middle_name", "type": "TextBox"},
        "pt4_7a_entity_name": {"db_path": "customer.customer_name", "type": "TextBox"},
        "pt4_7b_entity_title": {"db_path": "customer.signatory_job_title", "type": "TextBox"},
        "pt4_8_client_uscis_number": {"db_path": "customer.uscis_online_account", "type": "TextBox"},
        "pt4_9_alien_number": {"db_path": "beneficiary.alienNumber", "type": "TextBox"},
        "pt4_10_daytime_phone": {"db_path": "customer.signatory_work_phone", "type": "TextBox"},
        "pt4_11_mobile_phone": {"db_path": "customer.signatory_mobile_phone", "type": "TextBox"},
        "pt4_12_email": {"db_path": "customer.signatory_email_id", "type": "TextBox"},
        "pt4_13a_street": {"db_path": "customer.address_street", "type": "TextBox"},
        "pt4_13b_apt_ste_flr": {"db_path": "customer.address_type", "type": "TextBox"},
        "pt4_13b_number": {"db_path": "customer.address_number", "type": "TextBox"},
        "pt4_13c_city": {"db_path": "customer.address_city", "type": "TextBox"},
        "pt4_13d_state": {"db_path": "customer.address_state", "type": "TextBox"},
        "pt4_13e_zip": {"db_path": "customer.address_zip", "type": "TextBox"},
        "pt4_13f_province": {"db_path": "customer.address_province", "type": "TextBox"},
        "pt4_13g_postal_code": {"db_path": "customer.address_postal_code", "type": "TextBox"},
        "pt4_13h_country": {"db_path": "customer.address_country", "type": "TextBox"},
        "pt1_1a_attorney_last_name": {"db_path": "attorney.attorneyInfo.lastName", "type": "TextBox"},
        "pt1_1b_attorney_first_name": {"db_path": "attorney.attorneyInfo.firstName", "type": "TextBox"},
        "pt1_1c_attorney_middle_name": {"db_path": "attorney.attorneyInfo.middleName", "type": "TextBox"},
        "pt1_2_law_firm": {"db_path": "attorneyLawfirmDetails.lawfirmDetails.lawFirmName", "type": "TextBox"},
        "pt1_3a_attorney_street": {"db_path": "attorney.address.addressStreet", "type": "TextBox"},
        "pt1_3b_attorney_apt": {"db_path": "attorney.address.addressType", "type": "TextBox"},
        "pt1_3b_attorney_number": {"db_path": "attorney.address.addressNumber", "type": "TextBox"},
        "pt1_3c_attorney_city": {"db_path": "attorney.address.addressCity", "type": "TextBox"},
        "pt1_3d_attorney_state": {"db_path": "attorney.address.addressState", "type": "TextBox"},
        "pt1_3e_attorney_zip": {"db_path": "attorney.address.addressZip", "type": "TextBox"},
        "pt1_3f_attorney_province": {"db_path": "attorney.address.addressProvince", "type": "TextBox"},
        "pt1_3g_attorney_postal": {"db_path": "attorney.address.addressPostalCode", "type": "TextBox"},
        "pt1_3h_attorney_country": {"db_path": "attorney.address.addressCountry", "type": "TextBox"},
        "pt1_4_attorney_phone": {"db_path": "attorney.attorneyInfo.workPhone", "type": "TextBox"},
        "pt1_5_attorney_fax": {"db_path": "attorney.attorneyInfo.faxNumber", "type": "TextBox"},
        "pt1_6_attorney_email": {"db_path": "attorney.attorneyInfo.emailAddress", "type": "TextBox"},
        "pt1_7_attorney_licensed": {"db_path": "attorney.attorneyInfo.licensingAuthority", "type": "TextBox"},
        "pt1_8_bar_number": {"db_path": "attorney.attorneyInfo.stateBarNumber", "type": "TextBox"},
    }
    
    # I-90 mappings (basic structure)
    I90_MAPPINGS = {
        "pt1_1_alien_number": {"db_path": "beneficiary.alienNumber", "type": "TextBox"},
        "pt1_2_uscis_account": {"db_path": "beneficiary.uscisOnlineAccount", "type": "TextBox"},
        "pt1_3a_family_name": {"db_path": "beneficiary.lastName", "type": "TextBox"},
        "pt1_3b_given_name": {"db_path": "beneficiary.firstName", "type": "TextBox"},
        "pt1_3c_middle_name": {"db_path": "beneficiary.middleName", "type": "TextBox"},
        "pt1_4_name_changed": {"db_path": "beneficiary.nameChanged", "type": "RadioBox"},
        "pt1_5a_previous_family": {"db_path": "beneficiary.previousLastName", "type": "TextBox"},
        "pt1_5b_previous_given": {"db_path": "beneficiary.previousFirstName", "type": "TextBox"},
        "pt1_5c_previous_middle": {"db_path": "beneficiary.previousMiddleName", "type": "TextBox"},
        "pt1_6a_care_of": {"db_path": "beneficiary.mailingCareOf", "type": "TextBox"},
        "pt1_6b_street": {"db_path": "beneficiary.address_street", "type": "TextBox"},
        "pt1_6c_apt_ste_flr": {"db_path": "beneficiary.address_type", "type": "TextBox"},
        "pt1_6d_city": {"db_path": "beneficiary.address_city", "type": "TextBox"},
        "pt1_6e_state": {"db_path": "beneficiary.address_state", "type": "TextBox"},
        "pt1_6f_zip": {"db_path": "beneficiary.address_zip", "type": "TextBox"},
        "pt1_6g_province": {"db_path": "beneficiary.address_province", "type": "TextBox"},
        "pt1_6h_postal": {"db_path": "beneficiary.address_postal_code", "type": "TextBox"},
        "pt1_6i_country": {"db_path": "beneficiary.address_country", "type": "TextBox"},
        "pt1_7_commuter_city": {"db_path": "beneficiary.commuterCityState", "type": "TextBox"},
        "pt1_8a_safe_address_care": {"db_path": "beneficiary.safeAddressCareOf", "type": "TextBox"},
        "pt1_8b_safe_street": {"db_path": "beneficiary.safeAddressStreet", "type": "TextBox"},
        "pt1_8c_safe_apt": {"db_path": "beneficiary.safeAddressType", "type": "TextBox"},
        "pt1_8d_safe_city": {"db_path": "beneficiary.safeAddressCity", "type": "TextBox"},
        "pt1_8e_safe_state": {"db_path": "beneficiary.safeAddressState", "type": "TextBox"},
        "pt1_8f_safe_zip": {"db_path": "beneficiary.safeAddressZip", "type": "TextBox"},
        "pt1_8g_safe_province": {"db_path": "beneficiary.safeAddressProvince", "type": "TextBox"},
        "pt1_8h_safe_postal": {"db_path": "beneficiary.safeAddressPostal", "type": "TextBox"},
        "pt1_8i_safe_country": {"db_path": "beneficiary.safeAddressCountry", "type": "TextBox"},
        "pt1_9a_physical_street": {"db_path": "beneficiary.physicalAddressStreet", "type": "TextBox"},
        "pt1_9b_physical_apt": {"db_path": "beneficiary.physicalAddressType", "type": "TextBox"},
        "pt1_9c_physical_city": {"db_path": "beneficiary.physicalAddressCity", "type": "TextBox"},
        "pt1_9d_physical_state": {"db_path": "beneficiary.physicalAddressState", "type": "TextBox"},
        "pt1_9e_physical_zip": {"db_path": "beneficiary.physicalAddressZip", "type": "TextBox"},
        "pt1_9f_physical_province": {"db_path": "beneficiary.physicalAddressProvince", "type": "TextBox"},
        "pt1_9g_physical_postal": {"db_path": "beneficiary.physicalAddressPostal", "type": "TextBox"},
        "pt1_9h_physical_country": {"db_path": "beneficiary.physicalAddressCountry", "type": "TextBox"},
        "pt1_10_sex": {"db_path": "beneficiary.gender", "type": "RadioBox"},
        "pt1_11_date_birth": {"db_path": "beneficiary.dateOfBirth", "type": "DateBox"},
        "pt1_12_city_birth": {"db_path": "beneficiary.cityOfBirth", "type": "TextBox"},
        "pt1_13_country_birth": {"db_path": "beneficiary.countryOfBirth", "type": "TextBox"},
        "pt1_14_class_admission": {"db_path": "beneficiary.classOfAdmission", "type": "TextBox"},
        "pt1_15_date_admission": {"db_path": "beneficiary.dateOfAdmission", "type": "DateBox"},
        "pt1_16_ssn": {"db_path": "beneficiary.socialSecurityNumber", "type": "TextBox"},
    }
    
    # Return mappings based on form type
    form_mappings = {
        "G-28": G28_MAPPINGS,
        "I-90": I90_MAPPINGS,
        "I-130": {},  # Add I-130 mappings here
        "I-485": {},  # Add I-485 mappings here
        "N-400": {},  # Add N-400 mappings here
    }
    
    return form_mappings.get(form_number, {})

# ===== DATA CLASSES =====
@dataclass
class ExtractedField:
    field_number: str
    field_label: str
    field_value: str
    field_type: str = "text"
    confidence: float = 0.0
    is_required: bool = False
    is_mapped: bool = False
    db_mapping: str = ""
    db_type: str = ""
    manually_edited: bool = False
    page_number: int = 0
    sequence_order: int = 0
    
    def to_dict(self):
        return {
            'field_number': self.field_number,
            'field_label': self.field_label,
            'field_value': self.field_value,
            'field_type': self.field_type,
            'confidence': self.confidence,
            'is_required': self.is_required,
            'is_mapped': self.is_mapped,
            'db_mapping': self.db_mapping,
            'db_type': self.db_type,
            'manually_edited': self.manually_edited,
            'page_number': self.page_number,
            'sequence_order': self.sequence_order
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
    
    def get_mapped_fields(self) -> List[ExtractedField]:
        return [f for f in self.fields if f.is_mapped]
    
    def get_unmapped_fields(self) -> List[ExtractedField]:
        return [f for f in self.fields if not f.is_mapped]

@dataclass
class FormResult:
    form_number: str
    form_title: str
    form_edition: str = ""
    total_pages: int = 0
    parts: Dict[int, FormPart] = field(default_factory=dict)
    total_fields: int = 0
    filled_fields: int = 0
    mapped_fields: int = 0
    unmapped_fields: int = 0
    processing_time: float = 0.0
    
    def calculate_stats(self):
        self.total_fields = sum(len(part.fields) for part in self.parts.values())
        self.filled_fields = sum(1 for part in self.parts.values() 
                                for field in part.fields if field.field_value and field.field_value.strip())
        self.mapped_fields = sum(1 for part in self.parts.values() 
                               for field in part.fields if field.is_mapped)
        self.unmapped_fields = self.total_fields - self.mapped_fields
    
    def get_all_mapped_fields(self) -> List[ExtractedField]:
        mapped = []
        for part in self.parts.values():
            mapped.extend(part.get_mapped_fields())
        return sorted(mapped, key=lambda x: x.sequence_order)
    
    def get_all_unmapped_fields(self) -> List[ExtractedField]:
        unmapped = []
        for part in self.parts.values():
            unmapped.extend(part.get_unmapped_fields())
        return sorted(unmapped, key=lambda x: x.sequence_order)

# ===== DATABASE =====
class SimpleDatabase:
    def __init__(self, db_path: str = "uscis_corrected.db"):
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
                    mapped_fields INTEGER DEFAULT 0,
                    unmapped_fields INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'processing',
                    data TEXT
                )
            ''')
            conn.commit()
    
    def save_submission(self, form_result: FormResult) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                INSERT INTO submissions (form_type, total_fields, filled_fields, mapped_fields, unmapped_fields, data)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                form_result.form_number,
                form_result.total_fields,
                form_result.filled_fields,
                form_result.mapped_fields,
                form_result.unmapped_fields,
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
                SELECT id, form_type, created_at, total_fields, filled_fields, mapped_fields, unmapped_fields, status
                FROM submissions ORDER BY created_at DESC LIMIT ?
            ''', (limit,))
            return cursor.fetchall()
    
    def get_submission_data(self, submission_id: int):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT data FROM submissions WHERE id = ?', (submission_id,))
            result = cursor.fetchone()
            return json.loads(result[0]) if result else None

# ===== PDF EXTRACTION (Same as before but optimized) =====
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

def extract_pdf_text_simple(pdf_file) -> str:
    """Main PDF extraction function with multiple fallback methods"""
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
        
        # Try direct memory extraction
        try:
            with safe_pdf_context(pdf_bytes) as doc:
                st.success(f"✅ PDF opened - {len(doc)} pages")
                
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
                    st.error("❌ No text found")
                    return ""
                
                st.success(f"✅ Extracted text from {pages_with_text}/{len(doc)} pages")
                return full_text
                
        except Exception as e:
            st.error(f"❌ PDF extraction failed: {str(e)}")
            return ""
        
    except Exception as e:
        st.error(f"💥 PDF extraction failed: {str(e)}")
        return ""

# ===== FORM DETECTION =====
def detect_form_info(pdf_text: str) -> tuple:
    """Detect form information from PDF text"""
    
    # Extract form number
    form_patterns = [
        r'Form\s+([A-Z]-?\d+[A-Z]?)',
        r'USCIS\s+Form\s+([A-Z]-?\d+[A-Z]?)',
    ]
    
    form_number = "Unknown"
    for pattern in form_patterns:
        match = re.search(pattern, pdf_text, re.IGNORECASE)
        if match:
            form_number = match.group(1).upper()
            if re.match(r'^[A-Z]\d', form_number) and '-' not in form_number:
                form_number = form_number[0] + '-' + form_number[1:]
            break
    
    # Extract form title
    title_patterns = [
        rf'Form\s+{re.escape(form_number)}.*?\n(.+?)(?:\n|Department)',
        r'(?:Form\s+[A-Z]-?\d+[A-Z]?.*?\n)(.+?)(?:\n|Department)',
    ]
    
    form_title = f"USCIS Form {form_number}"
    for pattern in title_patterns:
        match = re.search(pattern, pdf_text, re.IGNORECASE | re.DOTALL)
        if match:
            title = match.group(1).strip()
            if len(title) > 10 and len(title) < 100:
                form_title = title
                break
    
    # Extract edition
    edition_patterns = [
        r'Edition\s+(\d{2}/\d{2}/\d{2,4})',
        r'(\d{2}/\d{2}/\d{2,4})\s+Edition',
    ]
    
    edition = ""
    for pattern in edition_patterns:
        match = re.search(pattern, pdf_text, re.IGNORECASE)
        if match:
            edition = match.group(1)
            break
    
    # Count pages
    page_count = len(re.findall(r'=== PAGE \d+ ===', pdf_text))
    
    return form_number, form_title, edition, page_count

def extract_all_parts(pdf_text: str) -> List[dict]:
    """Extract all parts from form"""
    
    parts = []
    part_patterns = [
        r'Part\s+(\d+)\.\s*(.+?)(?=\n)',
        r'PART\s+(\d+)\.\s*(.+?)(?=\n)',
    ]
    
    found_parts = set()
    
    for pattern in part_patterns:
        matches = re.finditer(pattern, pdf_text, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            part_num = int(match.group(1))
            part_title = match.group(2).strip()
            part_title = re.sub(r'\s+', ' ', part_title)
            part_title = part_title.replace('(continued)', '').strip()
            
            if part_num not in found_parts and part_title and len(part_title) > 3:
                found_parts.add(part_num)
                parts.append({
                    'number': part_num,
                    'title': part_title,
                    'raw_text': extract_part_text(pdf_text, part_num)
                })
    
    parts.sort(key=lambda x: x['number'])
    return parts

def extract_part_text(pdf_text: str, part_num: int) -> str:
    """Extract text for specific part"""
    
    start_patterns = [rf'Part\s+{part_num}\..*?\n']
    
    start_pos = -1
    for pattern in start_patterns:
        match = re.search(pattern, pdf_text, re.IGNORECASE)
        if match:
            start_pos = match.end()
            break
    
    if start_pos == -1:
        return ""
    
    next_part_patterns = [rf'Part\s+{part_num + 1}\..*?\n']
    
    end_pos = len(pdf_text)
    for pattern in next_part_patterns:
        match = re.search(pattern, pdf_text[start_pos:], re.IGNORECASE)
        if match:
            end_pos = start_pos + match.start()
            break
    
    return pdf_text[start_pos:end_pos]

# ===== CORRECTED AI EXTRACTION =====
def extract_form_data_corrected(pdf_text: str, openai_client) -> FormResult:
    """Corrected AI extraction with proper field mapping"""
    
    try:
        st.info("🤖 Starting corrected AI extraction...")
        
        # Step 1: Detect form
        form_number, form_title, edition, page_count = detect_form_info(pdf_text)
        
        st.markdown(f"""
        <div class="export-section">
        <h4>📋 Form Detection Results</h4>
        <p><strong>Form Number:</strong> {form_number}</p>
        <p><strong>Title:</strong> {form_title}</p>
        <p><strong>Edition:</strong> {edition}</p>
        <p><strong>Pages:</strong> {page_count}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Step 2: Get field mappings from knowledge base
        field_mappings = get_form_mappings(form_number)
        st.info(f"📚 Loaded {len(field_mappings)} field mappings from knowledge base")
        
        # Step 3: Extract parts
        parts_info = extract_all_parts(pdf_text)
        if not parts_info:
            parts_info = [{'number': 1, 'title': 'Form Data', 'raw_text': pdf_text}]
        
        st.success(f"✅ Found {len(parts_info)} parts")
        
        # Step 4: Process each part
        result = FormResult(
            form_number=form_number,
            form_title=form_title,
            form_edition=edition,
            total_pages=page_count
        )
        
        sequence_counter = 0
        
        for part_info in parts_info:
            st.info(f"🔄 Processing Part {part_info['number']}: {part_info['title']}")
            
            part_result = extract_part_with_ai_corrected(
                part_info['raw_text'], 
                openai_client, 
                form_number, 
                part_info['number'], 
                part_info['title'],
                field_mappings,
                sequence_counter
            )
            
            if part_result:
                result.parts[part_info['number']] = part_result
                sequence_counter += len(part_result.fields)
                st.success(f"✅ Part {part_info['number']}: {len(part_result.fields)} fields extracted")
        
        # Step 5: Calculate stats
        result.calculate_stats()
        st.success(f"🎉 Extraction complete! {result.total_fields} total fields, {result.mapped_fields} mapped, {result.unmapped_fields} unmapped")
        
        return result
        
    except Exception as e:
        st.error(f"💥 Corrected extraction failed: {str(e)}")
        return create_empty_result("Unknown")

def extract_part_with_ai_corrected(part_text: str, openai_client, form_number: str, part_num: int, part_title: str, field_mappings: Dict, sequence_start: int) -> FormPart:
    """Extract fields with proper mapping and sequence"""
    
    try:
        # Truncate if too long
        max_length = 8000
        if len(part_text) > max_length:
            part_text = part_text[:max_length] + "\n[...truncated...]"
        
        # Create improved extraction prompt
        prompt = f"""
Extract ALL form fields from this USCIS {form_number} Part {part_num} ({part_title}).

Return ONLY valid JSON in this exact format:
{{
  "fields": [
    {{
      "field_number": "1.a",
      "field_label": "Family Name (Last Name)",
      "field_value": "extracted_actual_value_or_empty_string",
      "field_type": "text",
      "confidence": 0.85,
      "is_required": true
    }}
  ]
}}

CRITICAL RULES:
1. Extract ACTUAL VALUES from the form, NOT database object names
2. If a field has a value like "Smith" extract "Smith", NOT "customer.lastName" 
3. If a field is empty, use empty string "", NOT database references
4. Extract field numbers exactly as shown (1.a, 2.b, 3.c, etc.)
5. Extract exact field labels as written
6. Determine field types: "text", "date", "checkbox", "radio", "number", "address", "phone", "email"
7. Set confidence based on extraction certainty
8. Mark as required if field appears mandatory
9. Focus ONLY on actual form input fields, ignore headers/instructions
10. Maintain the sequence order as fields appear in the form

Part text:
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
        
        # Parse JSON
        try:
            if '```json' in response_text:
                response_text = response_text.split('```json')[1].split('```')[0]
            elif '```' in response_text:
                response_text = response_text.split('```')[1].split('```')[0]
            
            data = json.loads(response_text.strip())
        except json.JSONDecodeError as e:
            st.warning(f"⚠️ JSON parsing failed for Part {part_num}: {str(e)}")
            return None
        
        # Create FormPart with mapping
        part = FormPart(number=part_num, title=part_title)
        
        for i, field_data in enumerate(data.get('fields', [])):
            # Create field key for mapping lookup
            field_key = create_field_key(part_num, field_data.get('field_number', ''), field_data.get('field_label', ''))
            
            # Check if field is mapped
            is_mapped = field_key in field_mappings
            db_mapping = ""
            db_type = ""
            
            if is_mapped:
                mapping_info = field_mappings[field_key]
                db_mapping = mapping_info.get("db_path", "")
                db_type = mapping_info.get("type", "")
            
            field = ExtractedField(
                field_number=field_data.get('field_number', ''),
                field_label=field_data.get('field_label', ''),
                field_value=field_data.get('field_value', ''),
                field_type=field_data.get('field_type', 'text'),
                confidence=field_data.get('confidence', 0.5),
                is_required=field_data.get('is_required', False),
                is_mapped=is_mapped,
                db_mapping=db_mapping,
                db_type=db_type,
                sequence_order=sequence_start + i
            )
            part.add_field(field)
        
        return part
        
    except Exception as e:
        st.warning(f"⚠️ AI extraction failed for Part {part_num}: {str(e)}")
        return None

def create_field_key(part_num: int, field_number: str, field_label: str) -> str:
    """Create standardized field key for mapping lookup"""
    
    # Convert field number and label to standardized format
    field_key = f"pt{part_num}_{field_number}".lower().replace(".", "_").replace(" ", "_")
    
    # Add label-based keywords for better matching
    label_lower = field_label.lower()
    if "family name" in label_lower or "last name" in label_lower:
        field_key += "_family_name"
    elif "given name" in label_lower or "first name" in label_lower:
        field_key += "_given_name"
    elif "middle name" in label_lower:
        field_key += "_middle_name"
    elif "street" in label_lower and "number" in label_lower:
        field_key += "_street"
    elif "city" in label_lower:
        field_key += "_city"
    elif "state" in label_lower:
        field_key += "_state"
    elif "zip" in label_lower:
        field_key += "_zip"
    elif "phone" in label_lower:
        if "daytime" in label_lower:
            field_key += "_daytime_phone"
        elif "mobile" in label_lower:
            field_key += "_mobile_phone"
        else:
            field_key += "_phone"
    elif "email" in label_lower:
        field_key += "_email"
    elif "alien" in label_lower and "number" in label_lower:
        field_key += "_alien_number"
    elif "uscis" in label_lower and "account" in label_lower:
        field_key += "_uscis_account"
    
    return field_key

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

# ===== EXPORT FUNCTIONS =====
def export_mapped_fields_typescript(form_result: FormResult) -> str:
    """Export mapped fields in TypeScript format"""
    
    mapped_fields = form_result.get_all_mapped_fields()
    
    # Group by database entity
    entities = {}
    
    for field in mapped_fields:
        if field.db_mapping:
            entity_path = field.db_mapping.split('.')[0]
            if entity_path not in entities:
                entities[entity_path] = {}
            
            entities[entity_path][field.db_mapping] = {
                "value": field.field_value,
                "type": field.db_type,
                "field_number": field.field_number,
                "field_label": field.field_label
            }
    
    # Generate TypeScript
    ts_content = f"export const {form_result.form_number.replace('-', '')} = {{\n"
    ts_content += f'    "formname": "{form_result.form_number}",\n'
    
    for entity, fields in entities.items():
        ts_content += f'    "{entity}Data": {{\n'
        for db_path, field_info in fields.items():
            field_name = db_path.split('.')[-1]
            ts_content += f'        "{field_name}": "{field_info["value"]}:{field_info["type"]}",\n'
        ts_content += '    },\n'
    
    ts_content += '    "questionnaireData": {\n'
    
    # Add questionnaire references for unmapped fields
    unmapped_fields = form_result.get_all_unmapped_fields()
    for field in unmapped_fields:
        field_key = f"{field.field_number.replace('.', '_')}"
        ts_content += f'        "{field_key}": "questionnaire:{field.field_type}Box",\n'
    
    ts_content += '    }\n'
    ts_content += '};'
    
    return ts_content

def export_questionnaire_json(form_result: FormResult) -> str:
    """Export questionnaire data in JSON format"""
    
    unmapped_fields = form_result.get_all_unmapped_fields()
    
    questionnaire = {
        "form_number": form_result.form_number,
        "form_title": form_result.form_title,
        "total_unmapped_fields": len(unmapped_fields),
        "fields": []
    }
    
    for field in unmapped_fields:
        questionnaire["fields"].append({
            "field_number": field.field_number,
            "field_label": field.field_label,
            "field_value": field.field_value,
            "field_type": field.field_type,
            "is_required": field.is_required,
            "confidence": field.confidence,
            "sequence_order": field.sequence_order,
            "question": generate_question_for_field(field),
            "placeholder": get_placeholder_for_field(field)
        })
    
    return json.dumps(questionnaire, indent=2)

def generate_question_for_field(field: ExtractedField) -> str:
    """Generate question for unmapped field"""
    
    label = field.field_label.lower()
    
    if 'name' in label:
        return f"What is your {field.field_label.lower()}?"
    elif 'address' in label:
        return f"What is your {field.field_label.lower()}?"
    elif 'date' in label or 'birth' in label:
        return f"What is the {field.field_label.lower()}? (MM/DD/YYYY format)"
    elif 'phone' in label:
        return f"What is your {field.field_label.lower()}?"
    elif 'email' in label:
        return f"What is your {field.field_label.lower()}?"
    else:
        return f"Please provide: {field.field_label}"

def get_placeholder_for_field(field: ExtractedField) -> str:
    """Get placeholder for field"""
    
    if field.field_type == "date":
        return "MM/DD/YYYY"
    elif 'name' in field.field_label.lower():
        return "Enter full name"
    elif 'address' in field.field_label.lower():
        return "123 Main St, City, State 12345"
    elif 'phone' in field.field_label.lower():
        return "(555) 123-4567"
    elif 'email' in field.field_label.lower():
        return "your.email@example.com"
    else:
        return f"Enter {field.field_type}"

# ===== UI COMPONENTS =====
def display_extraction_results(result: FormResult):
    """Display extraction results with proper mapping information"""
    
    if not result or not result.parts:
        st.warning("No extraction results to display")
        return
    
    st.markdown("## 📋 Extracted Form Data")
    
    # Enhanced metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Form", result.form_number)
    with col2:
        st.metric("Total Fields", result.total_fields)
    with col3:
        st.metric("Filled Fields", result.filled_fields)
    with col4:
        st.metric("Mapped Fields", result.mapped_fields)
    with col5:
        st.metric("Unmapped Fields", result.unmapped_fields)
    
    # Display each part
    for part_num in sorted(result.parts.keys()):
        part = result.parts[part_num]
        completion = part.get_completion_rate()
        mapped_count = len(part.get_mapped_fields())
        unmapped_count = len(part.get_unmapped_fields())
        
        with st.expander(f"Part {part_num}: {part.title} ({len(part.fields)} fields - {mapped_count} mapped, {unmapped_count} unmapped)", 
                        expanded=(part_num == 1)):
            
            if not part.fields:
                st.info("No fields found in this part")
                continue
            
            # Display fields with mapping info
            for i, field in enumerate(part.fields):
                display_field_editor_corrected(field, f"{part_num}_{i}")

def display_field_editor_corrected(field: ExtractedField, field_key: str):
    """Display field with mapping information"""
    
    has_value = field.field_value and field.field_value.strip()
    
    if field.is_mapped:
        css_class = "field-mapped"
        mapping_icon = "🔗"
    else:
        css_class = "field-unmapped"
        mapping_icon = "❓"
    
    st.markdown(f'<div class="field-card {css_class}">', unsafe_allow_html=True)
    
    # Field header
    col1, col2, col3 = st.columns([2, 3, 1])
    
    with col1:
        st.markdown(f"**{field.field_number}** {mapping_icon}")
        if field.is_required:
            st.markdown("🔴 Required")
        if field.manually_edited:
            st.markdown("✏️ Edited")
    
    with col2:
        st.markdown(f"**{field.field_label}**")
        st.caption(f"Type: {field.field_type} | Confidence: {field.confidence:.0%}")
        
        if field.is_mapped:
            st.markdown(f'<div class="mapping-info">📍 Mapped to: {field.db_mapping}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="mapping-info">❓ Unmapped - Will go to questionnaire</div>', unsafe_allow_html=True)
    
    with col3:
        if field.confidence < 0.5:
            st.markdown("⚠️ Low Confidence")
    
    # Value editor
    col1, col2 = st.columns([3, 1])
    
    with col1:
        if field.field_type == "checkbox" or field.field_type == "radio":
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

def display_questionnaire_tab(result: FormResult):
    """Display questionnaire for unmapped fields"""
    
    st.markdown("## 📝 Questionnaire for Unmapped Fields")
    
    unmapped_fields = result.get_all_unmapped_fields()
    
    if not unmapped_fields:
        st.success("🎉 All fields are mapped! No questionnaire needed.")
        return
    
    st.info(f"Complete {len(unmapped_fields)} unmapped fields:")
    
    # Group by part
    fields_by_part = {}
    for field in unmapped_fields:
        # Find which part this field belongs to
        part_num = 1
        for pnum, part in result.parts.items():
            if field in part.fields:
                part_num = pnum
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
            
            question = generate_question_for_field(field)
            st.write(question)
            
            answer = st.text_input(
                "Your answer:",
                value=field.field_value,
                key=f"quest_{part_num}_{i}",
                placeholder=get_placeholder_for_field(field)
            )
            
            if answer != field.field_value:
                field.field_value = answer
                field.manually_edited = True
            
            st.markdown("---")

def display_export_tab(result: FormResult):
    """Display export options"""
    
    st.markdown("## 📤 Export Data")
    
    if not result or not result.parts:
        st.warning("No data to export")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🔗 Mapped Fields (TypeScript)")
        st.info(f"Export {result.mapped_fields} mapped fields to TypeScript format")
        
        if st.button("📥 Generate TypeScript Export", type="primary"):
            ts_content = export_mapped_fields_typescript(result)
            
            st.markdown("**Generated TypeScript:**")
            st.code(ts_content, language="typescript")
            
            # Download button
            st.download_button(
                label="💾 Download TypeScript File",
                data=ts_content,
                file_name=f"{result.form_number.replace('-', '')}_mapped_fields.ts",
                mime="text/typescript"
            )
    
    with col2:
        st.markdown("### ❓ Unmapped Fields (JSON Questionnaire)")
        st.info(f"Export {result.unmapped_fields} unmapped fields as questionnaire JSON")
        
        if st.button("📋 Generate Questionnaire JSON", type="primary"):
            json_content = export_questionnaire_json(result)
            
            st.markdown("**Generated JSON:**")
            st.code(json_content, language="json")
            
            # Download button
            st.download_button(
                label="💾 Download Questionnaire JSON",
                data=json_content,
                file_name=f"{result.form_number.replace('-', '')}_questionnaire.json",
                mime="application/json"
            )
    
    # Combined export
    st.markdown("### 📦 Combined Export")
    if st.button("📦 Generate Combined Export Package"):
        
        # Create combined data
        combined_data = {
            "form_info": {
                "form_number": result.form_number,
                "form_title": result.form_title,
                "form_edition": result.form_edition,
                "total_pages": result.total_pages,
                "extraction_date": datetime.now().isoformat()
            },
            "mapped_fields": {
                "count": result.mapped_fields,
                "typescript_export": export_mapped_fields_typescript(result)
            },
            "questionnaire": json.loads(export_questionnaire_json(result))
        }
        
        combined_json = json.dumps(combined_data, indent=2)
        
        st.download_button(
            label="💾 Download Combined Package (JSON)",
            data=combined_json,
            file_name=f"{result.form_number.replace('-', '')}_complete_export.json",
            mime="application/json"
        )

def display_database_tab(db: SimpleDatabase):
    """Display database with enhanced columns"""
    st.markdown("## 💾 Saved Forms")
    
    submissions = db.get_submissions(20)
    
    if not submissions:
        st.info("No saved forms yet")
        return
    
    # Enhanced table with mapping info
    df = pd.DataFrame(submissions, columns=['ID', 'Form Type', 'Created', 'Total Fields', 'Filled Fields', 'Mapped Fields', 'Unmapped Fields', 'Status'])
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
    """Load submission from database with mapping info"""
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
                    is_mapped=field_data.get('is_mapped', False),
                    db_mapping=field_data.get('db_mapping', ''),
                    db_type=field_data.get('db_type', ''),
                    manually_edited=field_data.get('manually_edited', False),
                    page_number=field_data.get('page_number', 0),
                    sequence_order=field_data.get('sequence_order', 0)
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
        '<h1>🤖 Corrected USCIS Form Processor</h1>'
        '<p>Fixed extraction with proper field mapping, questionnaire export, and TypeScript generation</p>'
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
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📤 Upload & Extract", "✏️ Edit Fields", "📝 Questionnaire", "📤 Export", "💾 Database"])
    
    with tab1:
        st.markdown("### 📤 Upload USCIS Form PDF")
        
        uploaded_file = st.file_uploader(
            "Choose a USCIS form PDF",
            type=['pdf'],
            help="Upload any USCIS form for corrected extraction"
        )
        
        if uploaded_file:
            st.success(f"✅ File: {uploaded_file.name}")
            
            if st.button("🚀 Extract Form Data", type="primary"):
                with st.spinner("Processing..."):
                    # Extract PDF text
                    st.markdown("#### Step 1: PDF Text Extraction")
                    pdf_text = extract_pdf_text_simple(uploaded_file)
                    
                    if not pdf_text:
                        st.error("Cannot proceed without PDF text")
                        st.stop()
                    
                    # Debug: Show text preview
                    if debug_mode:
                        with st.expander("🔍 Extracted Text Preview"):
                            st.text_area("Raw text:", pdf_text[:1000], height=200)
                    
                    # Corrected AI Extraction
                    st.markdown("#### Step 2: Corrected AI Data Extraction")
                    start_time = time.time()
                    
                    result = extract_form_data_corrected(pdf_text, openai_client)
                    
                    if result and result.parts:
                        result.processing_time = time.time() - start_time
                        
                        # Save to database
                        submission_id = db.save_submission(result)
                        st.success(f"✅ Saved to database (ID: {submission_id})")
                        
                        # Store in session
                        st.session_state.current_result = result
                        
                        # Show results
                        st.markdown("#### 🎉 Extraction Results")
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Total Fields", result.total_fields)
                        with col2:
                            st.metric("Filled Fields", result.filled_fields)
                        with col3:
                            st.metric("Mapped Fields", result.mapped_fields)
                        with col4:
                            st.metric("Unmapped Fields", result.unmapped_fields)
                        
                        st.success("✅ Data extracted with proper mapping! Check other tabs for editing, questionnaire, and export.")
                    else:
                        st.error("❌ Extraction failed or returned no data")
    
    with tab2:
        if st.session_state.current_result:
            display_extraction_results(st.session_state.current_result)
            
            if st.button("💾 Save All Changes", type="primary"):
                if st.session_state.current_result:
                    st.session_state.current_result.calculate_stats()
                    submission_id = db.save_submission(st.session_state.current_result)
                    st.success(f"✅ Changes saved! (ID: {submission_id})")
        else:
            st.info("No form data loaded. Upload and extract a PDF first.")
    
    with tab3:
        if st.session_state.current_result:
            display_questionnaire_tab(st.session_state.current_result)
        else:
            st.info("No form data loaded. Upload and extract a PDF first.")
    
    with tab4:
        if st.session_state.current_result:
            display_export_tab(st.session_state.current_result)
        else:
            st.info("No form data loaded. Upload and extract a PDF first.")
    
    with tab5:
        display_database_tab(db)
    
    # Debug info
    if debug_mode:
        st.markdown("---")
        st.markdown("### 🔧 Debug Information")
        
        if st.session_state.current_result:
            with st.expander("Current Result Details"):
                result = st.session_state.current_result
                st.json({
                    "form_number": result.form_number,
                    "total_fields": result.total_fields,
                    "mapped_fields": result.mapped_fields,
                    "unmapped_fields": result.unmapped_fields,
                    "parts_count": len(result.parts)
                })

if __name__ == "__main__":
    main()
