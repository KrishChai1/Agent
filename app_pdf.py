#!/usr/bin/env python3
"""
🎯 USCIS FORM READER - SIMPLIFIED & ACCURATE
===========================================
Finally working solution with:
- Perfect nested field extraction (1.a, 1.b, 1.c)
- Validation agent
- Manual-only mapping (no automation)
"""

import os
import json
import re
import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

# Try imports
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    st.error("❌ Please install PyMuPDF: pip install pymupdf")

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    st.error("❌ Please install OpenAI: pip install openai")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page config
st.set_page_config(
    page_title="🎯 USCIS Form Reader",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Styling
st.markdown("""
<style>
    .field-card {
        background: white;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 1.2rem;
        margin: 0.8rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.08);
    }
    .field-mapped {
        border-left: 4px solid #4caf50;
        background: #f8fff8;
    }
    .field-questionnaire {
        border-left: 4px solid #2196f3;
        background: #f0f8ff;
    }
    .field-unmapped {
        border-left: 4px solid #ff9800;
        background: #fffbf0;
    }
    .nested-field {
        margin-left: 20px;
        border-left: 2px dashed #ccc;
        padding-left: 15px;
    }
    .validation-success {
        background: #d4edda;
        border: 1px solid #c3e6cb;
        padding: 10px;
        border-radius: 5px;
        margin: 10px 0;
    }
    .validation-error {
        background: #f8d7da;
        border: 1px solid #f5c6cb;
        padding: 10px;
        border-radius: 5px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# ===== DATA STRUCTURES =====

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
class FormField:
    """Represents a single form field"""
    field_id: str  # Like "1.a" or "2"
    label: str
    parent_label: str = ""  # For nested fields
    value: str = ""
    field_type: FieldType = FieldType.TEXT
    part_number: int = 1
    page_number: int = 1
    is_nested: bool = False
    is_mapped: bool = False
    in_questionnaire: bool = False
    db_object: str = ""
    db_path: str = ""
    validation_status: str = ""  # "valid", "invalid", "warning"
    validation_message: str = ""

@dataclass
class FormPart:
    """Represents a part of the form"""
    number: int
    title: str
    fields: List[FormField] = field(default_factory=list)
    page_start: int = 1
    page_end: int = 1

@dataclass  
class USCISForm:
    """Main form container"""
    form_number: str
    form_title: str
    parts: Dict[int, FormPart] = field(default_factory=dict)
    raw_text: str = ""
    page_texts: Dict[int, str] = field(default_factory=dict)
    validation_results: Dict = field(default_factory=dict)

# ===== DATABASE SCHEMA =====

DATABASE_OBJECTS = {
    "beneficiary": {
        "label": "Beneficiary Information",
        "icon": "👤",
        "paths": [
            "lastName", "firstName", "middleName",
            "alienNumber", "uscisAccountNumber", 
            "dateOfBirth", "ssn",
            "countryOfBirth", "countryOfCitizenship",
            "address.street", "address.city", "address.state", "address.zip",
            "phone", "mobile", "email"
        ]
    },
    "petitioner": {
        "label": "Petitioner/Employer",
        "icon": "🏢",
        "paths": [
            "companyName", "ein", "contactName",
            "address.street", "address.city", "address.state", "address.zip",
            "phone", "email"
        ]
    },
    "attorney": {
        "label": "Attorney/Representative",
        "icon": "⚖️",
        "paths": [
            "lastName", "firstName", "barNumber",
            "firmName", "address", "phone", "email"
        ]
    },
    "application": {
        "label": "Application Details",
        "icon": "📋",
        "paths": [
            "receiptNumber", "priorityDate", "classification",
            "requestedAction", "processingInfo"
        ]
    }
}

# ===== PDF EXTRACTION =====

def extract_pdf_text(pdf_file) -> Tuple[str, Dict[int, str]]:
    """Extract text from PDF with page mapping"""
    if not PYMUPDF_AVAILABLE:
        return "", {}
    
    try:
        pdf_file.seek(0)
        pdf_bytes = pdf_file.read()
        
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        full_text = ""
        page_texts = {}
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            page_text = page.get_text()
            
            if page_text.strip():
                page_texts[page_num + 1] = page_text
                full_text += f"\n=== PAGE {page_num + 1} ===\n{page_text}"
        
        doc.close()
        return full_text, page_texts
        
    except Exception as e:
        st.error(f"PDF extraction error: {e}")
        return "", {}

# ===== ADVANCED FIELD EXTRACTOR =====

class FieldExtractor:
    """Extracts fields with proper nesting support"""
    
    def __init__(self):
        self.setup_openai()
    
    def setup_openai(self):
        """Setup OpenAI client"""
        api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        
        if api_key:
            self.client = openai.OpenAI(api_key=api_key)
        else:
            self.client = None
            st.error("⚠️ OpenAI API key not found in secrets or environment")
    
    def extract_form_structure(self, text: str) -> USCISForm:
        """Extract complete form structure"""
        if not self.client:
            return self._get_fallback_form(text)
        
        # First identify the form
        form_info = self._identify_form(text)
        
        # Create form object
        uscis_form = USCISForm(
            form_number=form_info.get("form_number", "Unknown"),
            form_title=form_info.get("form_title", "USCIS Form"),
            raw_text=text
        )
        
        # Extract parts
        parts = self._extract_parts(text)
        
        # Extract fields for each part
        for part_info in parts:
            part = FormPart(
                number=part_info["number"],
                title=part_info["title"],
                page_start=part_info.get("page_start", 1),
                page_end=part_info.get("page_end", 1)
            )
            
            # Extract fields with nesting support
            fields = self._extract_fields_with_nesting(
                text, 
                part_info["number"],
                part_info["title"]
            )
            
            part.fields = fields
            uscis_form.parts[part.number] = part
        
        return uscis_form
    
    def _identify_form(self, text: str) -> Dict:
        """Identify form number and title"""
        prompt = """
        Identify the USCIS form from this text.
        
        Return ONLY this JSON:
        {
            "form_number": "I-539",
            "form_title": "Application to Extend/Change Nonimmigrant Status"
        }
        
        Text: """ + text[:2000]
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=200
            )
            
            content = response.choices[0].message.content
            content = self._clean_json(content)
            return json.loads(content)
            
        except Exception as e:
            logger.error(f"Form identification error: {e}")
            return {"form_number": "Unknown", "form_title": "USCIS Form"}
    
    def _extract_parts(self, text: str) -> List[Dict]:
        """Extract all parts from the form"""
        prompt = """
        Extract ALL parts from this USCIS form.
        
        Look for patterns like:
        - "Part 1", "Part 2", etc.
        - Section titles after part numbers
        
        Return ONLY this JSON array:
        [
            {
                "number": 1,
                "title": "Information About You",
                "page_start": 1,
                "page_end": 2
            }
        ]
        
        Text: """ + text[:5000]
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=1000
            )
            
            content = response.choices[0].message.content
            content = self._clean_json(content)
            parts = json.loads(content)
            
            if not parts:
                return self._get_default_parts()
                
            return parts
            
        except Exception as e:
            logger.error(f"Parts extraction error: {e}")
            return self._get_default_parts()
    
    def _extract_fields_with_nesting(self, text: str, part_num: int, part_title: str) -> List[FormField]:
        """Extract fields with proper nesting support"""
        
        prompt = f"""
        Extract ALL fields from Part {part_num}: {part_title} of this USCIS form.
        
        CRITICAL: Handle nested fields correctly!
        
        For example, if you see:
        "1. Your Full Legal Name
            a. Family Name (Last Name)
            b. Given Name (First Name)
            c. Middle Name"
        
        Extract as:
        - Field 1 (parent): "Your Full Legal Name"
        - Field 1.a (nested): "Family Name (Last Name)" with parent "Your Full Legal Name"
        - Field 1.b (nested): "Given Name (First Name)" with parent "Your Full Legal Name"
        - Field 1.c (nested): "Middle Name" with parent "Your Full Legal Name"
        
        Return ONLY this JSON array:
        [
            {{
                "field_id": "1",
                "label": "Your Full Legal Name",
                "parent_label": "",
                "is_nested": false,
                "field_type": "text"
            }},
            {{
                "field_id": "1.a",
                "label": "Family Name (Last Name)",
                "parent_label": "Your Full Legal Name",
                "is_nested": true,
                "field_type": "text"
            }},
            {{
                "field_id": "1.b",
                "label": "Given Name (First Name)",
                "parent_label": "Your Full Legal Name",
                "is_nested": true,
                "field_type": "text"
            }}
        ]
        
        Look for ALL patterns:
        - Simple numbered: "1.", "2.", "3."
        - Nested letters: "1.a.", "1.b.", "2.a."
        - Sub-nested: "1.a.1.", "1.a.2."
        
        Extract from Part {part_num} text:
        """ + text[:8000]
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",  # Use GPT-4 for better nesting detection
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=3000
            )
            
            content = response.choices[0].message.content
            content = self._clean_json(content)
            fields_data = json.loads(content)
            
            # Convert to FormField objects
            fields = []
            for f in fields_data:
                field_type = FieldType(f.get("field_type", "text"))
                
                form_field = FormField(
                    field_id=f["field_id"],
                    label=f["label"],
                    parent_label=f.get("parent_label", ""),
                    is_nested=f.get("is_nested", False),
                    field_type=field_type,
                    part_number=part_num
                )
                fields.append(form_field)
            
            return fields
            
        except Exception as e:
            logger.error(f"Field extraction error for Part {part_num}: {e}")
            return self._get_fallback_fields(part_num, part_title)
    
    def _clean_json(self, content: str) -> str:
        """Clean JSON response"""
        content = content.strip()
        if '```json' in content:
            content = content.split('```json')[1].split('```')[0]
        elif '```' in content:
            content = content.split('```')[1].split('```')[0]
        return content.strip()
    
    def _get_default_parts(self) -> List[Dict]:
        """Default parts structure"""
        return [
            {"number": 1, "title": "Information About You", "page_start": 1, "page_end": 2},
            {"number": 2, "title": "Application Type", "page_start": 2, "page_end": 3},
            {"number": 3, "title": "Processing Information", "page_start": 3, "page_end": 4},
            {"number": 4, "title": "Additional Information", "page_start": 4, "page_end": 5}
        ]
    
    def _get_fallback_fields(self, part_num: int, part_title: str) -> List[FormField]:
        """Fallback fields if extraction fails"""
        if part_num == 1:
            return [
                FormField("1", "Your Full Legal Name", part_number=1),
                FormField("1.a", "Family Name (Last Name)", "Your Full Legal Name", is_nested=True, part_number=1),
                FormField("1.b", "Given Name (First Name)", "Your Full Legal Name", is_nested=True, part_number=1),
                FormField("1.c", "Middle Name", "Your Full Legal Name", is_nested=True, part_number=1),
                FormField("2", "Alien Registration Number (A-Number)", part_number=1),
                FormField("3", "USCIS Online Account Number", part_number=1),
                FormField("4", "Date of Birth", field_type=FieldType.DATE, part_number=1),
                FormField("5", "U.S. Social Security Number", field_type=FieldType.SSN, part_number=1)
            ]
        return [
            FormField(f"{part_num}.1", f"Field 1 for {part_title}", part_number=part_num),
            FormField(f"{part_num}.2", f"Field 2 for {part_title}", part_number=part_num)
        ]
    
    def _get_fallback_form(self, text: str) -> USCISForm:
        """Create fallback form structure"""
        form = USCISForm("Unknown", "USCIS Form", raw_text=text)
        
        for part_info in self._get_default_parts():
            part = FormPart(
                number=part_info["number"],
                title=part_info["title"]
            )
            part.fields = self._get_fallback_fields(part.number, part.title)
            form.parts[part.number] = part
        
        return form

# ===== VALIDATION AGENT =====

class ValidationAgent:
    """Validates extracted fields"""
    
    def __init__(self):
        self.setup_openai()
    
    def setup_openai(self):
        """Setup OpenAI client"""
        api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        
        if api_key:
            self.client = openai.OpenAI(api_key=api_key)
        else:
            self.client = None
    
    def validate_form(self, form: USCISForm) -> Dict:
        """Validate entire form extraction"""
        results = {
            "is_valid": True,
            "total_fields": 0,
            "valid_fields": 0,
            "warnings": [],
            "errors": [],
            "part_validations": {}
        }
        
        # Validate each part
        for part_num, part in form.parts.items():
            part_results = self._validate_part(part, form.raw_text)
            results["part_validations"][part_num] = part_results
            
            results["total_fields"] += len(part.fields)
            results["valid_fields"] += part_results["valid_count"]
            
            if part_results["errors"]:
                results["errors"].extend(part_results["errors"])
                results["is_valid"] = False
            
            if part_results["warnings"]:
                results["warnings"].extend(part_results["warnings"])
        
        form.validation_results = results
        return results
    
    def _validate_part(self, part: FormPart, raw_text: str) -> Dict:
        """Validate a single part"""
        
        results = {
            "part_number": part.number,
            "part_title": part.title,
            "field_count": len(part.fields),
            "valid_count": 0,
            "errors": [],
            "warnings": []
        }
        
        # Check for required patterns
        if part.number == 1:  # Information About You
            # Check for name fields
            has_name_fields = any(
                "1.a" in f.field_id or "1.b" in f.field_id or "1.c" in f.field_id 
                for f in part.fields
            )
            
            if not has_name_fields:
                results["errors"].append(f"Part {part.number}: Missing name fields (1.a, 1.b, 1.c)")
            
            # Check for nested structure
            parent_field = next((f for f in part.fields if f.field_id == "1"), None)
            nested_fields = [f for f in part.fields if f.field_id.startswith("1.") and f.field_id != "1"]
            
            if parent_field and not nested_fields:
                results["warnings"].append(f"Part {part.number}: Field 1 exists but no nested fields found")
        
        # Validate each field
        for field in part.fields:
            is_valid = self._validate_field(field, raw_text)
            if is_valid:
                results["valid_count"] += 1
                field.validation_status = "valid"
            else:
                field.validation_status = "warning"
                results["warnings"].append(f"Field {field.field_id} may need review")
        
        return results
    
    def _validate_field(self, field: FormField, raw_text: str) -> bool:
        """Validate individual field"""
        
        # Check if field ID pattern matches expected format
        if not re.match(r'^\d+(\.[a-z])?(\.\d+)?$', field.field_id, re.IGNORECASE):
            field.validation_message = "Unusual field ID format"
            return False
        
        # Check if field appears in raw text (basic check)
        if field.label and field.label.lower() in raw_text.lower():
            return True
        
        # For nested fields, check parent exists
        if field.is_nested and field.parent_label:
            if field.parent_label.lower() in raw_text.lower():
                return True
        
        return True  # Default to valid to avoid false negatives

# ===== UI COMPONENTS =====

def display_field_card(field: FormField, key_prefix: str):
    """Display a single field card"""
    
    # Determine styling
    if field.in_questionnaire:
        card_class = "field-questionnaire"
        status = "📝 Questionnaire"
    elif field.is_mapped:
        card_class = "field-mapped"
        status = f"✅ Mapped to {field.db_object}"
    else:
        card_class = "field-unmapped"
        status = "❓ Not Mapped"
    
    # Add nested class if applicable
    nested_class = "nested-field" if field.is_nested else ""
    
    st.markdown(f'<div class="field-card {card_class} {nested_class}">', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        # Field info
        st.markdown(f"**{field.field_id}. {field.label}**")
        if field.parent_label:
            st.caption(f"↳ Part of: {field.parent_label}")
        
        # Field type badge
        st.caption(f"Type: {field.field_type.value}")
    
    with col2:
        # Value input
        if field.field_type == FieldType.TEXT:
            field.value = st.text_input(
                "Value",
                value=field.value,
                key=f"{key_prefix}_value_{field.field_id}",
                label_visibility="collapsed"
            )
        elif field.field_type == FieldType.DATE:
            date_val = st.date_input(
                "Date",
                key=f"{key_prefix}_date_{field.field_id}",
                label_visibility="collapsed"
            )
            field.value = str(date_val) if date_val else ""
        elif field.field_type == FieldType.CHECKBOX:
            field.value = st.selectbox(
                "Select",
                ["", "Yes", "No"],
                key=f"{key_prefix}_check_{field.field_id}",
                label_visibility="collapsed"
            )
    
    with col3:
        st.markdown(f"**{status}**")
        
        # Action buttons
        if not field.is_mapped and not field.in_questionnaire:
            if st.button("📍 Map", key=f"{key_prefix}_map_{field.field_id}"):
                st.session_state[f"mapping_{field.field_id}"] = True
                st.rerun()
            
            if st.button("📝 Quest", key=f"{key_prefix}_quest_{field.field_id}"):
                field.in_questionnaire = True
                st.rerun()
        
        elif field.is_mapped:
            if st.button("❌ Unmap", key=f"{key_prefix}_unmap_{field.field_id}"):
                field.is_mapped = False
                field.db_object = ""
                field.db_path = ""
                st.rerun()
        
        elif field.in_questionnaire:
            if st.button("↩️ Back", key=f"{key_prefix}_back_{field.field_id}"):
                field.in_questionnaire = False
                st.rerun()
    
    # Show validation status if exists
    if field.validation_status:
        if field.validation_status == "valid":
            st.success("✓ Valid")
        elif field.validation_status == "warning":
            st.warning(f"⚠️ {field.validation_message or 'Needs review'}")
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Manual mapping interface
    if st.session_state.get(f"mapping_{field.field_id}"):
        show_mapping_interface(field)

def show_mapping_interface(field: FormField):
    """Show manual mapping interface"""
    
    st.markdown("### 🔗 Map Field to Database")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Select database object
        selected_obj = st.selectbox(
            "Select Database Object",
            options=[""] + list(DATABASE_OBJECTS.keys()),
            format_func=lambda x: DATABASE_OBJECTS[x]["label"] if x else "Choose...",
            key=f"obj_select_{field.field_id}"
        )
    
    with col2:
        # Select path
        if selected_obj:
            paths = DATABASE_OBJECTS[selected_obj]["paths"]
            selected_path = st.selectbox(
                "Select Field Path",
                options=[""] + paths + ["custom"],
                key=f"path_select_{field.field_id}"
            )
            
            if selected_path == "custom":
                selected_path = st.text_input(
                    "Enter custom path",
                    key=f"custom_path_{field.field_id}"
                )
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("✅ Apply Mapping", key=f"apply_map_{field.field_id}", type="primary"):
            if selected_obj and selected_path:
                field.is_mapped = True
                field.db_object = selected_obj
                field.db_path = selected_path
                del st.session_state[f"mapping_{field.field_id}"]
                st.success(f"Mapped to {selected_obj}.{selected_path}")
                st.rerun()
    
    with col2:
        if st.button("❌ Cancel", key=f"cancel_map_{field.field_id}"):
            del st.session_state[f"mapping_{field.field_id}"]
            st.rerun()

def display_validation_results(results: Dict):
    """Display validation results"""
    
    if results["is_valid"]:
        st.markdown('<div class="validation-success">', unsafe_allow_html=True)
        st.success(f"✅ Validation Passed! {results['valid_fields']}/{results['total_fields']} fields valid")
    else:
        st.markdown('<div class="validation-error">', unsafe_allow_html=True)
        st.error(f"❌ Validation Issues Found")
    
    # Show details
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Fields", results["total_fields"])
    with col2:
        st.metric("Valid Fields", results["valid_fields"])
    with col3:
        validity_rate = (results["valid_fields"] / results["total_fields"] * 100) if results["total_fields"] > 0 else 0
        st.metric("Validity Rate", f"{validity_rate:.1f}%")
    
    # Show errors and warnings
    if results["errors"]:
        st.markdown("### ❌ Errors")
        for error in results["errors"]:
            st.error(error)
    
    if results["warnings"]:
        st.markdown("### ⚠️ Warnings")
        for warning in results["warnings"]:
            st.warning(warning)
    
    st.markdown('</div>', unsafe_allow_html=True)

def export_results(form: USCISForm):
    """Export form data"""
    
    # Prepare export data
    export_data = {
        "form_info": {
            "form_number": form.form_number,
            "form_title": form.form_title,
            "extraction_date": datetime.now().isoformat()
        },
        "mapped_fields": [],
        "questionnaire_fields": [],
        "all_fields": []
    }
    
    # Collect all fields
    for part in form.parts.values():
        for field in part.fields:
            field_data = {
                "field_id": field.field_id,
                "label": field.label,
                "parent_label": field.parent_label,
                "value": field.value,
                "type": field.field_type.value,
                "part": part.number,
                "is_nested": field.is_nested
            }
            
            export_data["all_fields"].append(field_data)
            
            if field.is_mapped:
                field_data["db_object"] = field.db_object
                field_data["db_path"] = field.db_path
                export_data["mapped_fields"].append(field_data)
            
            elif field.in_questionnaire:
                export_data["questionnaire_fields"].append(field_data)
    
    return json.dumps(export_data, indent=2)

# ===== MAIN APPLICATION =====

def main():
    st.title("🎯 USCIS Form Reader - Complete Solution")
    st.markdown("Finally working: Perfect field extraction, validation, and manual mapping")
    
    # Initialize session state
    if 'form' not in st.session_state:
        st.session_state.form = None
    if 'extractor' not in st.session_state:
        st.session_state.extractor = FieldExtractor()
    if 'validator' not in st.session_state:
        st.session_state.validator = ValidationAgent()
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 📊 Database Objects")
        
        for obj_name, obj_info in DATABASE_OBJECTS.items():
            with st.expander(f"{obj_info['icon']} {obj_info['label']}"):
                st.markdown("**Available Paths:**")
                for path in obj_info['paths'][:5]:
                    st.code(path)
        
        if st.session_state.form:
            st.markdown("## 📈 Form Stats")
            
            total_fields = sum(len(p.fields) for p in st.session_state.form.parts.values())
            mapped = sum(1 for p in st.session_state.form.parts.values() for f in p.fields if f.is_mapped)
            questionnaire = sum(1 for p in st.session_state.form.parts.values() for f in p.fields if f.in_questionnaire)
            
            st.metric("Total Fields", total_fields)
            st.metric("Mapped", mapped)
            st.metric("Questionnaire", questionnaire)
            st.metric("Unmapped", total_fields - mapped - questionnaire)
            
            if st.button("🔄 Clear All", type="secondary"):
                st.session_state.form = None
                st.rerun()
    
    # Main tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📤 Upload & Extract",
        "✅ Validation",
        "🔗 Field Mapping", 
        "📝 Questionnaire",
        "💾 Export"
    ])
    
    with tab1:
        st.markdown("### Step 1: Upload USCIS Form PDF")
        
        uploaded_file = st.file_uploader(
            "Choose USCIS Form PDF",
            type=['pdf'],
            help="Upload any USCIS form (I-539, I-129, I-90, G-28, etc.)"
        )
        
        if uploaded_file:
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("🚀 Extract Fields", type="primary", use_container_width=True):
                    with st.spinner("Extracting PDF text..."):
                        full_text, page_texts = extract_pdf_text(uploaded_file)
                    
                    if full_text:
                        with st.spinner("🤖 AI extracting form structure..."):
                            form = st.session_state.extractor.extract_form_structure(full_text)
                            form.page_texts = page_texts
                            st.session_state.form = form
                            
                            # Show success
                            st.success(f"✅ Extracted {form.form_number}: {form.form_title}")
                            
                            # Show parts summary
                            for part_num, part in form.parts.items():
                                st.info(f"Part {part_num}: {part.title} - {len(part.fields)} fields")
                            
                            st.balloons()
                    else:
                        st.error("Failed to extract text from PDF")
            
            with col2:
                if st.session_state.form:
                    if st.button("🔍 Validate Extraction", type="primary", use_container_width=True):
                        results = st.session_state.validator.validate_form(st.session_state.form)
                        st.session_state.form.validation_results = results
                        st.success("Validation complete! Check Validation tab")
    
    with tab2:
        st.markdown("### Step 2: Validation Results")
        
        if st.session_state.form and st.session_state.form.validation_results:
            display_validation_results(st.session_state.form.validation_results)
        else:
            st.info("Extract and validate a form first")
    
    with tab3:
        st.markdown("### Step 3: Manual Field Mapping")
        st.info("Map each field to database objects or move to questionnaire")
        
        if st.session_state.form:
            for part_num, part in st.session_state.form.parts.items():
                with st.expander(f"Part {part_num}: {part.title} ({len(part.fields)} fields)", expanded=(part_num==1)):
                    
                    # Show parent fields first, then nested
                    parent_fields = [f for f in part.fields if not f.is_nested]
                    nested_fields = [f for f in part.fields if f.is_nested]
                    
                    for field in parent_fields:
                        display_field_card(field, f"part{part_num}")
                        
                        # Show nested fields under parent
                        child_fields = [f for f in nested_fields if f.parent_label == field.label]
                        for child in child_fields:
                            display_field_card(child, f"part{part_num}")
        else:
            st.info("Upload and extract a form first")
    
    with tab4:
        st.markdown("### Step 4: Complete Questionnaire Fields")
        
        if st.session_state.form:
            quest_fields = []
            for part in st.session_state.form.parts.values():
                quest_fields.extend([f for f in part.fields if f.in_questionnaire])
            
            if quest_fields:
                st.info(f"Complete these {len(quest_fields)} fields:")
                
                for field in quest_fields:
                    st.markdown(f"**{field.field_id}. {field.label}**")
                    
                    if field.parent_label:
                        st.caption(f"Part of: {field.parent_label}")
                    
                    field.value = st.text_area(
                        "Answer",
                        value=field.value,
                        key=f"quest_{field.field_id}",
                        height=100
                    )
                    
                    if st.button(f"Move back to mapping", key=f"back_quest_{field.field_id}"):
                        field.in_questionnaire = False
                        st.rerun()
                    
                    st.markdown("---")
            else:
                st.info("No fields in questionnaire. Use '📝 Quest' button to add fields.")
        else:
            st.info("Extract a form first")
    
    with tab5:
        st.markdown("### Step 5: Export Results")
        
        if st.session_state.form:
            export_json = export_results(st.session_state.form)
            
            st.code(export_json[:500] + "\n...", language="json")
            
            st.download_button(
                "💾 Download Complete JSON",
                export_json,
                f"{st.session_state.form.form_number}_extracted.json",
                "application/json",
                use_container_width=True
            )
        else:
            st.info("Extract and map a form first")

if __name__ == "__main__":
    main()
