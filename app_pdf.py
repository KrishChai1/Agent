#!/usr/bin/env python3
"""
USCIS FORM READER - GENERIC & COMPLETE VERSION
===============================================
Handles all USCIS forms including complex repeating sections
"""

import streamlit as st
import json
import re
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
import uuid

# Page config
st.set_page_config(
    page_title="USCIS Form Reader - Universal",
    page_icon="🎯",
    layout="wide"
)

# Check imports
try:
    import fitz
    PYMUPDF_AVAILABLE = True
except:
    PYMUPDF_AVAILABLE = False
    st.error("Install PyMuPDF: pip install pymupdf")

try:
    import openai
    OPENAI_AVAILABLE = True
except:
    OPENAI_AVAILABLE = False
    st.error("Install OpenAI: pip install openai")

# Enhanced styles
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 10px;
        color: white;
        margin-bottom: 2rem;
        text-align: center;
    }
    .field-card {
        border: 1px solid #e0e0e0;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 8px;
        background: white;
        transition: all 0.2s ease;
    }
    .field-card:hover {
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    .field-mapped {
        border-left: 4px solid #4caf50;
        background: #f1f8f4;
    }
    .field-questionnaire {
        border-left: 4px solid #2196f3;
        background: #e8f4fd;
    }
    .field-unmapped {
        border-left: 4px solid #ff9800;
        background: #fff8e1;
    }
    .manual-override {
        border-left: 4px solid #9c27b0;
        background: #f3e5f5;
    }
    .field-repeating {
        border-left: 4px solid #00bcd4;
        background: #e0f7fa;
    }
    .dependent-section {
        background: #f5f5f5;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 8px;
        border: 2px dashed #9e9e9e;
    }
    .stats-card {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# ===== DATA STRUCTURES =====

@dataclass
class FormField:
    """Enhanced field structure for all USCIS forms"""
    item_number: str
    label: str
    field_type: str = "text"  # text, checkbox, date, address, etc
    value: str = ""
    part_number: int = 1
    page_number: int = 1
    parent_item: str = ""
    is_subfield: bool = False
    is_repeating: bool = False  # For dependent sections
    repeat_group: str = ""  # Group identifier for repeating sections
    repeat_index: int = 0  # Index within repeat group
    is_mapped: bool = False
    in_questionnaire: bool = False
    is_manual_override: bool = False
    db_object: str = ""
    db_path: str = ""
    unique_id: str = ""
    
    def __post_init__(self):
        if not self.unique_id:
            self.unique_id = str(uuid.uuid4())[:8]

@dataclass
class FormPart:
    """Represents a part with support for complex structures"""
    number: int
    title: str
    fields: List[FormField] = field(default_factory=list)
    has_repeating_sections: bool = False
    repeat_groups: Dict[str, List[FormField]] = field(default_factory=dict)
    page_start: int = 1
    page_end: int = 1

@dataclass
class USCISForm:
    """Universal USCIS form structure"""
    form_number: str
    form_title: str
    edition_date: str = ""
    total_pages: int = 0
    parts: Dict[int, FormPart] = field(default_factory=dict)
    raw_text: str = ""
    validation_passed: bool = False
    form_type: str = ""  # I-539, I-824, I-129, etc

# ===== ENHANCED DATABASE SCHEMA =====

DATABASE_SCHEMA = {
    "beneficiary": {
        "label": "👤 Beneficiary/Applicant",
        "paths": [
            "familyName",
            "givenName",
            "middleName",
            "alienNumber",
            "uscisAccountNumber",
            "dateOfBirth",
            "countryOfBirth",
            "countryOfCitizenship",
            "mailingAddress.inCareOf",
            "mailingAddress.streetNumberAndName",
            "mailingAddress.apartment",
            "mailingAddress.city",
            "mailingAddress.state",
            "mailingAddress.zipCode",
            "physicalAddress.streetNumberAndName",
            "physicalAddress.city",
            "physicalAddress.state",
            "physicalAddress.zipCode",
            "socialSecurityNumber",
            "i94Number",
            "passportNumber",
            "currentStatus",
            "daytimePhone",
            "mobilePhone",
            "emailAddress"
        ]
    },
    "dependent": {
        "label": "👥 Dependent Information",
        "paths": [
            "dependent[].familyName",
            "dependent[].givenName",
            "dependent[].middleName",
            "dependent[].dateOfBirth",
            "dependent[].countryOfBirth",
            "dependent[].countryOfCitizenship",
            "dependent[].relationship",
            "dependent[].alienNumber",
            "dependent[].phone",
            "dependent[].email"
        ]
    },
    "petitioner": {
        "label": "🏢 Petitioner/Employer",
        "paths": [
            "organizationName",
            "ein",
            "contactPersonName",
            "address.street",
            "address.city",
            "address.state",
            "address.zip",
            "phone",
            "email",
            "immigrationStatus",
            "certificateNumber"
        ]
    },
    "attorney": {
        "label": "⚖️ Attorney/Representative",
        "paths": [
            "familyName",
            "givenName",
            "firmName",
            "stateBarNumber",
            "uscisAccountNumber",
            "address",
            "phone",
            "email"
        ]
    },
    "application": {
        "label": "📋 Application Information",
        "paths": [
            "formNumber",
            "receiptNumber",
            "filingDate",
            "approvalDate",
            "priorityDate",
            "classificationType",
            "requestType",
            "consulateLocation",
            "portOfEntry"
        ]
    },
    "manual_override": {
        "label": "✏️ Manual Override",
        "paths": []
    }
}

# ===== GENERIC FORM PATTERNS =====

FORM_PATTERNS = {
    "I-539": {
        "parts": ["Information About You", "Application Type", "Processing Information"],
        "special_fields": {
            "name": ["Family Name", "Given Name", "Middle Name"],
            "address": ["Street", "City", "State", "ZIP"]
        }
    },
    "I-824": {
        "parts": ["Information About You", "Reason for Request", "Other Information"],
        "special_fields": {
            "dependents": "repeating",  # Multiple dependent sections
            "previous_application": ["Form Number", "Receipt Number", "Filing Date", "Approval Date"]
        }
    },
    "I-129": {
        "parts": ["Petitioner Information", "Beneficiary Information", "Processing Information"],
        "special_fields": {
            "classification": "checkbox_group",
            "employment": ["Job Title", "SOC Code", "Wage"]
        }
    }
}

# ===== PDF EXTRACTION =====

def extract_pdf_with_structure(pdf_file) -> Tuple[str, Dict[int, str], int]:
    """Extract PDF with page mapping"""
    if not PYMUPDF_AVAILABLE:
        return "", {}, 0
    
    try:
        pdf_file.seek(0)
        doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
        
        full_text = ""
        page_texts = {}
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            
            if text.strip():
                page_texts[page_num + 1] = text
                full_text += f"\n=== PAGE {page_num + 1} ===\n{text}"
        
        total_pages = len(doc)
        doc.close()
        
        return full_text, page_texts, total_pages
        
    except Exception as e:
        st.error(f"PDF extraction error: {e}")
        return "", {}, 0

# ===== GENERIC FORM EXTRACTOR =====

class GenericFormExtractor:
    """Universal extractor for all USCIS forms"""
    
    def __init__(self):
        self.setup_openai()
    
    def setup_openai(self):
        """Setup OpenAI client"""
        api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        
        if api_key:
            self.client = openai.OpenAI(api_key=api_key)
            st.sidebar.success("✅ OpenAI Connected")
        else:
            self.client = None
            st.warning("⚠️ Add OPENAI_API_KEY to secrets!")
    
    def extract_form(self, full_text: str, page_texts: Dict[int, str], total_pages: int) -> USCISForm:
        """Extract any USCIS form with proper structure"""
        
        if not self.client:
            return self.create_sample_form()
        
        # Identify form type
        form_info = self._identify_form_type(full_text[:3000])
        
        form = USCISForm(
            form_number=form_info.get("form_number", "Unknown"),
            form_title=form_info.get("form_title", "USCIS Form"),
            edition_date=form_info.get("edition_date", ""),
            total_pages=total_pages,
            raw_text=full_text,
            form_type=form_info.get("form_number", "").split("-")[0] if form_info.get("form_number") else ""
        )
        
        # Extract all parts
        parts_data = self._extract_all_parts(full_text, form.form_number)
        
        for part_data in parts_data:
            part = FormPart(
                number=part_data["number"],
                title=part_data["title"],
                page_start=part_data.get("page_start", 1),
                page_end=part_data.get("page_end", 1)
            )
            
            # Extract fields with support for repeating sections
            fields = self._extract_part_fields_generic(full_text, part_data, form.form_number)
            
            # Organize fields and detect repeating patterns
            organized_fields = self._organize_fields(fields)
            part.fields = organized_fields["regular"]
            
            if organized_fields["repeating"]:
                part.has_repeating_sections = True
                part.repeat_groups = organized_fields["repeating"]
            
            form.parts[part.number] = part
        
        # Validate
        is_valid = self._validate_extraction(form)
        form.validation_passed = is_valid
        
        return form
    
    def _identify_form_type(self, text: str) -> Dict:
        """Identify any USCIS form type"""
        
        prompt = """
        Identify this USCIS form from the text.
        
        Look for form number (I-539, I-824, I-129, I-90, G-28, etc) and title.
        
        Return ONLY JSON:
        {
            "form_number": "I-824",
            "form_title": "Application for Action on an Approved Application or Petition",
            "edition_date": "04/01/24"
        }
        
        Text: """ + text
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=200
            )
            
            content = response.choices[0].message.content.strip()
            if "```" in content:
                content = content.split("```")[1].replace("json", "").strip()
            
            return json.loads(content)
            
        except Exception as e:
            st.error(f"Form identification error: {e}")
            return {"form_number": "Unknown", "form_title": "USCIS Form"}
    
    def _extract_all_parts(self, text: str, form_number: str) -> List[Dict]:
        """Extract all parts from any USCIS form"""
        
        prompt = f"""
        Extract ALL parts from this {form_number} USCIS form.
        
        Look for patterns like:
        - "Part 1. Information About You"
        - "Part 2. Reason for Request"
        - "Part 3. Other Information"
        
        Return ONLY JSON array:
        [
            {{
                "number": 1,
                "title": "Information About You (Person filing this Application)",
                "page_start": 1,
                "page_end": 2
            }}
        ]
        
        Text: """ + text[:10000]
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=1500
            )
            
            content = response.choices[0].message.content.strip()
            if "```" in content:
                content = content.split("```")[1].replace("json", "").strip()
            
            parts = json.loads(content)
            return parts if parts else self._get_default_parts(form_number)
            
        except Exception as e:
            st.error(f"Parts extraction error: {e}")
            return self._get_default_parts(form_number)
    
    def _extract_part_fields_generic(self, text: str, part_data: Dict, form_number: str) -> List[FormField]:
        """Extract fields from any part, handling complex structures"""
        
        part_num = part_data["number"]
        part_title = part_data["title"]
        
        prompt = f"""
        Extract ALL fields from Part {part_num}: {part_title} of form {form_number}.
        
        IMPORTANT INSTRUCTIONS:
        1. Extract EVERY field with its exact item number (1, 2.a, 2.b, 3, etc)
        2. For name fields: Use the actual structure (NOT always 1.a, 1.b, 1.c)
        3. For addresses: Include all components (street, apt, city, state, zip)
        4. For REPEATING sections (like multiple dependents in I-824 Part 3):
           - Mark as repeating with group name (e.g., "dependent_1", "dependent_2")
           - Include all fields for each repetition
        
        Example for I-824 Part 3 dependents:
        - Items 5.a-11: First dependent
        - Items 12.a-18: Second dependent
        - Items 19.a-25: Third dependent
        - Items 26.a-32: Fourth dependent
        
        Return ONLY JSON:
        [
            {{
                "item_number": "2.a",
                "label": "Family Name (Last Name)",
                "field_type": "text",
                "is_repeating": false
            }},
            {{
                "item_number": "5.a",
                "label": "Family Name (Last Name)",
                "field_type": "text",
                "is_repeating": true,
                "repeat_group": "dependent",
                "repeat_index": 1
            }}
        ]
        
        Extract from Part {part_num} text:
        """ + text[:20000]
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=4000
            )
            
            content = response.choices[0].message.content.strip()
            if "```" in content:
                content = content.split("```")[1].replace("json", "").strip()
            
            fields_data = json.loads(content)
            
            # Convert to FormField objects
            fields = []
            for item in fields_data:
                field = FormField(
                    item_number=item["item_number"],
                    label=item["label"],
                    field_type=item.get("field_type", "text"),
                    part_number=part_num,
                    is_repeating=item.get("is_repeating", False),
                    repeat_group=item.get("repeat_group", ""),
                    repeat_index=item.get("repeat_index", 0)
                )
                fields.append(field)
            
            return fields
            
        except Exception as e:
            st.error(f"Field extraction error: {e}")
            return self._get_fallback_fields(form_number, part_num, part_title)
    
    def _organize_fields(self, fields: List[FormField]) -> Dict[str, Any]:
        """Organize fields into regular and repeating groups"""
        
        organized = {
            "regular": [],
            "repeating": {}
        }
        
        for field in fields:
            if field.is_repeating and field.repeat_group:
                # Add to repeating group
                group_key = f"{field.repeat_group}_{field.repeat_index}"
                if group_key not in organized["repeating"]:
                    organized["repeating"][group_key] = []
                organized["repeating"][group_key].append(field)
            else:
                # Regular field
                organized["regular"].append(field)
        
        return organized
    
    def _validate_extraction(self, form: USCISForm) -> bool:
        """Validate extraction for any form type"""
        
        if not form.parts:
            st.warning("No parts extracted")
            return False
        
        total_fields = sum(
            len(p.fields) + sum(len(group) for group in p.repeat_groups.values())
            for p in form.parts.values()
        )
        
        if total_fields < 5:
            st.warning(f"Only {total_fields} fields extracted - may be incomplete")
            return False
        
        return True
    
    def _get_default_parts(self, form_number: str) -> List[Dict]:
        """Get default parts based on form type"""
        
        if "824" in form_number:
            return [
                {"number": 1, "title": "Information About You", "page_start": 1, "page_end": 2},
                {"number": 2, "title": "Reason for Request", "page_start": 2, "page_end": 2},
                {"number": 3, "title": "Other Information", "page_start": 2, "page_end": 4},
                {"number": 4, "title": "Applicant's Contact Information", "page_start": 4, "page_end": 4}
            ]
        elif "539" in form_number:
            return [
                {"number": 1, "title": "Information About You", "page_start": 1, "page_end": 2},
                {"number": 2, "title": "Application Type", "page_start": 2, "page_end": 3},
                {"number": 3, "title": "Processing Information", "page_start": 3, "page_end": 4}
            ]
        else:
            return [
                {"number": 1, "title": "Part 1", "page_start": 1, "page_end": 2}
            ]
    
    def _get_fallback_fields(self, form_number: str, part_num: int, part_title: str) -> List[FormField]:
        """Get fallback fields based on form and part"""
        
        fields = []
        
        # I-824 specific fallbacks
        if "824" in form_number and part_num == 3:
            # Regular fields
            fields.extend([
                FormField("1.a", "Form Number of Previously Approved Application", part_number=3),
                FormField("1.b", "Receipt Number", part_number=3),
                FormField("1.c", "Filing Date", field_type="date", part_number=3),
                FormField("1.d", "Approval Date", field_type="date", part_number=3),
                FormField("2.a", "Family Name (Principal Beneficiary)", part_number=3),
                FormField("2.b", "Given Name (Principal Beneficiary)", part_number=3),
                FormField("2.c", "Middle Name (Principal Beneficiary)", part_number=3)
            ])
            
            # Add 4 dependent sections
            for i in range(1, 5):
                base_num = 5 + (i-1) * 7  # 5, 12, 19, 26
                fields.extend([
                    FormField(f"{base_num}.a", f"Family Name (Dependent {i})", part_number=3, 
                             is_repeating=True, repeat_group="dependent", repeat_index=i),
                    FormField(f"{base_num}.b", f"Given Name (Dependent {i})", part_number=3,
                             is_repeating=True, repeat_group="dependent", repeat_index=i),
                    FormField(f"{base_num}.c", f"Middle Name (Dependent {i})", part_number=3,
                             is_repeating=True, repeat_group="dependent", repeat_index=i),
                    FormField(f"{base_num+1}", f"Date of Birth (Dependent {i})", field_type="date", part_number=3,
                             is_repeating=True, repeat_group="dependent", repeat_index=i),
                    FormField(f"{base_num+2}", f"Country of Birth (Dependent {i})", part_number=3,
                             is_repeating=True, repeat_group="dependent", repeat_index=i),
                    FormField(f"{base_num+3}", f"Country of Citizenship (Dependent {i})", part_number=3,
                             is_repeating=True, repeat_group="dependent", repeat_index=i),
                    FormField(f"{base_num+4}", f"Relationship (Dependent {i})", part_number=3,
                             is_repeating=True, repeat_group="dependent", repeat_index=i)
                ])
        else:
            # Generic fallback
            fields.append(FormField(f"{part_num}.1", f"Field 1 for {part_title}", part_number=part_num))
            fields.append(FormField(f"{part_num}.2", f"Field 2 for {part_title}", part_number=part_num))
        
        return fields
    
    def create_sample_form(self) -> USCISForm:
        """Create sample form with complex structure"""
        
        form = USCISForm(
            form_number="I-824",
            form_title="Application for Action on an Approved Application or Petition",
            edition_date="04/01/24",
            total_pages=6,
            form_type="I"
        )
        
        # Part 1
        part1 = FormPart(1, "Information About You")
        part1.fields = [
            FormField("1", "I am the", field_type="checkbox", part_number=1),
            FormField("2.a", "Family Name (Last Name)", part_number=1),
            FormField("2.b", "Given Name (First Name)", part_number=1),
            FormField("2.c", "Middle Name", part_number=1),
            FormField("3", "Company or Organization Name", part_number=1),
            FormField("4", "Current/Recent Immigration Status", part_number=1),
            FormField("5", "Certificate of Naturalization Number", part_number=1),
            FormField("6", "Alien Registration Number (A-Number)", part_number=1),
            FormField("7", "Date of Birth", field_type="date", part_number=1)
        ]
        form.parts[1] = part1
        
        # Part 3 with repeating dependents
        part3 = FormPart(3, "Other Information")
        part3.fields = self._get_fallback_fields("I-824", 3, "Other Information")
        
        # Organize into repeating groups
        organized = self._organize_fields(part3.fields)
        part3.fields = organized["regular"]
        part3.repeat_groups = organized["repeating"]
        part3.has_repeating_sections = True
        
        form.parts[3] = part3
        
        form.validation_passed = True
        return form

# ===== UI COMPONENTS =====

def display_field_card(field: FormField, key_prefix: str):
    """Display field with enhanced UI"""
    
    unique_key = f"{key_prefix}_{field.unique_id}"
    
    # Determine card style
    if field.is_repeating:
        card_class = "field-repeating"
        status = f"🔁 Repeating ({field.repeat_group} #{field.repeat_index})"
    elif field.is_manual_override:
        card_class = "manual-override"
        status = "✏️ Manual Override"
    elif field.in_questionnaire:
        card_class = "field-questionnaire"
        status = "📝 Questionnaire"
    elif field.is_mapped:
        card_class = "field-mapped"
        status = f"✅ {field.db_object}"
    else:
        card_class = "field-unmapped"
        status = "❓ Not Mapped"
    
    st.markdown(f'<div class="field-card {card_class}">', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([3, 2, 2])
    
    with col1:
        st.markdown(f"**{field.item_number}. {field.label}**")
        if field.is_repeating:
            st.caption(f"Part of {field.repeat_group} group")
    
    with col2:
        # Value input based on type
        if field.field_type == "checkbox":
            field.value = st.selectbox(
                "Value",
                ["", "Yes", "No", "N/A"],
                key=f"{unique_key}_val",
                label_visibility="collapsed"
            )
        elif field.field_type == "date":
            date_val = st.date_input(
                "Date",
                key=f"{unique_key}_date",
                label_visibility="collapsed"
            )
            field.value = str(date_val) if date_val else ""
        else:
            field.value = st.text_input(
                "Value",
                value=field.value,
                key=f"{unique_key}_text",
                label_visibility="collapsed",
                placeholder=f"Enter {field.label.lower()}..."
            )
    
    with col3:
        st.markdown(f"**{status}**")
        
        # Action buttons
        if not field.is_mapped and not field.in_questionnaire:
            c1, c2 = st.columns(2)
            with c1:
                if st.button("📍", key=f"{unique_key}_map", help="Map to database"):
                    st.session_state[f"show_mapping_{field.unique_id}"] = True
                    st.rerun()
            with c2:
                if st.button("📝", key=f"{unique_key}_quest", help="Add to questionnaire"):
                    field.in_questionnaire = True
                    st.rerun()
        elif field.is_mapped or field.is_manual_override:
            if st.button("❌", key=f"{unique_key}_unmap", help="Remove mapping"):
                field.is_mapped = False
                field.is_manual_override = False
                field.db_object = ""
                field.db_path = ""
                st.rerun()
        elif field.in_questionnaire:
            if st.button("↩️", key=f"{unique_key}_back", help="Move back"):
                field.in_questionnaire = False
                st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Mapping interface
    if st.session_state.get(f"show_mapping_{field.unique_id}"):
        show_mapping_interface(field, unique_key)

def show_mapping_interface(field: FormField, unique_key: str):
    """Enhanced mapping interface"""
    
    st.markdown("---")
    st.markdown("### 🔗 Map Field to Database")
    
    # Special handling for repeating fields
    if field.is_repeating:
        st.info(f"📌 This is part of repeating group '{field.repeat_group}' (instance #{field.repeat_index})")
    
    col1, col2 = st.columns(2)
    
    with col1:
        db_options = list(DATABASE_SCHEMA.keys())
        db_labels = [DATABASE_SCHEMA[k]["label"] for k in db_options]
        
        # Pre-select dependent for repeating dependent fields
        default_idx = None
        if field.is_repeating and "dependent" in field.repeat_group.lower():
            default_idx = db_options.index("dependent") if "dependent" in db_options else None
        
        selected_idx = st.selectbox(
            "Database Object",
            range(len(db_options)),
            format_func=lambda x: db_labels[x],
            key=f"{unique_key}_db_obj",
            index=default_idx,
            placeholder="Choose object..."
        )
        
        selected_obj = db_options[selected_idx] if selected_idx is not None else None
    
    with col2:
        if selected_obj == "manual_override":
            selected_path = st.text_input(
                "Custom path",
                key=f"{unique_key}_manual",
                placeholder="e.g., custom.field.path"
            )
        elif selected_obj:
            paths = DATABASE_SCHEMA[selected_obj]["paths"]
            
            # For repeating fields, suggest array notation
            if field.is_repeating and selected_obj == "dependent":
                suggested_path = f"dependent[{field.repeat_index-1}].{field.label.split('(')[0].strip().replace(' ', '')}"
                paths = [suggested_path] + paths
            
            selected_path = st.selectbox(
                "Field Path",
                [""] + paths + ["[Custom]"],
                key=f"{unique_key}_path"
            )
            
            if selected_path == "[Custom]":
                selected_path = st.text_input(
                    "Custom path",
                    key=f"{unique_key}_custom",
                    placeholder="Enter custom path"
                )
        else:
            selected_path = None
    
    if selected_obj and selected_path:
        st.success(f"📍 Preview: {field.item_number} → {selected_obj}.{selected_path}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("✅ Apply", key=f"{unique_key}_apply", type="primary"):
            if selected_obj and selected_path:
                field.is_mapped = True
                field.is_manual_override = (selected_obj == "manual_override")
                field.db_object = selected_obj
                field.db_path = selected_path
                del st.session_state[f"show_mapping_{field.unique_id}"]
                st.success(f"Mapped!")
                st.rerun()
    
    with col2:
        if st.button("Cancel", key=f"{unique_key}_cancel"):
            del st.session_state[f"show_mapping_{field.unique_id}"]
            st.rerun()
    
    st.markdown("---")

def display_repeating_group(group_name: str, fields: List[FormField], key_prefix: str):
    """Display a repeating group (like dependents)"""
    
    st.markdown(f'<div class="dependent-section">', unsafe_allow_html=True)
    
    # Extract group info
    parts = group_name.split("_")
    group_type = parts[0]
    group_index = parts[1] if len(parts) > 1 else "1"
    
    st.markdown(f"### {group_type.title()} #{group_index}")
    
    for field in fields:
        display_field_card(field, f"{key_prefix}_{group_name}")
    
    st.markdown('</div>', unsafe_allow_html=True)

# ===== MAIN APPLICATION =====

def main():
    st.markdown('<div class="main-header">', unsafe_allow_html=True)
    st.title("🎯 Universal USCIS Form Reader")
    st.markdown("Handles all forms including complex repeating sections (I-824 Part 3 dependents, etc.)")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Initialize
    if 'form' not in st.session_state:
        st.session_state.form = None
    if 'extractor' not in st.session_state:
        st.session_state.extractor = GenericFormExtractor()
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 📊 Database Schema")
        
        for key, info in DATABASE_SCHEMA.items():
            with st.expander(info["label"]):
                if key == "manual_override":
                    st.info("Enter any custom path")
                elif key == "dependent":
                    st.info("For repeating dependents:\n`dependent[0].fieldName`")
                    for path in info["paths"][:3]:
                        st.code(path)
                else:
                    for path in info["paths"][:5]:
                        st.code(path)
                    if len(info["paths"]) > 5:
                        st.caption(f"... +{len(info['paths'])-5} more")
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📋 Sample I-539", use_container_width=True):
                # Load I-539 sample
                st.info("Loading I-539 sample...")
        with col2:
            if st.button("📋 Sample I-824", use_container_width=True):
                st.session_state.form = st.session_state.extractor.create_sample_form()
                st.success("I-824 loaded!")
                st.rerun()
        
        if st.button("🔄 Clear All", type="secondary", use_container_width=True):
            st.session_state.form = None
            for key in list(st.session_state.keys()):
                if key.startswith("show_mapping_"):
                    del st.session_state[key]
            st.rerun()
        
        if st.session_state.form:
            st.markdown("## 📈 Statistics")
            form = st.session_state.form
            
            st.markdown(f'<div class="stats-card">', unsafe_allow_html=True)
            st.metric("Form", f"{form.form_number}")
            st.metric("Edition", form.edition_date)
            
            # Count all fields including repeating
            total_fields = sum(
                len(p.fields) + sum(len(group) for group in p.repeat_groups.values())
                for p in form.parts.values()
            )
            
            mapped = sum(
                sum(1 for f in p.fields if f.is_mapped) +
                sum(sum(1 for f in group if f.is_mapped) for group in p.repeat_groups.values())
                for p in form.parts.values()
            )
            
            st.metric("Total Fields", total_fields)
            st.metric("Mapped", mapped)
            
            # Show repeating groups count
            total_repeating = sum(
                len(p.repeat_groups) for p in form.parts.values()
            )
            if total_repeating > 0:
                st.metric("Repeat Groups", total_repeating)
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    # Main tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📤 Upload",
        "🔗 Map Fields",
        "📝 Questionnaire",
        "💾 Export"
    ])
    
    with tab1:
        st.markdown("### Upload Any USCIS Form")
        st.info("Supports all forms: I-539, I-824, I-129, I-90, G-28, and more")
        
        uploaded_file = st.file_uploader(
            "Choose PDF file",
            type=['pdf']
        )
        
        if uploaded_file:
            if st.button("🚀 Extract Fields", type="primary", use_container_width=True):
                with st.spinner("Extracting form structure..."):
                    # Extract PDF
                    full_text, page_texts, total_pages = extract_pdf_with_structure(uploaded_file)
                    
                    if full_text:
                        # Extract form
                        form = st.session_state.extractor.extract_form(
                            full_text, page_texts, total_pages
                        )
                        
                        st.session_state.form = form
                        
                        # Show results
                        st.success(f"✅ Extracted {form.form_number}: {form.form_title}")
                        
                        # Show statistics
                        total_fields = sum(
                            len(p.fields) + sum(len(group) for group in p.repeat_groups.values())
                            for p in form.parts.values()
                        )
                        
                        total_repeating = sum(
                            sum(len(group) for group in p.repeat_groups.values())
                            for p in form.parts.values()
                        )
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Parts", len(form.parts))
                        with col2:
                            st.metric("Total Fields", total_fields)
                        with col3:
                            st.metric("Repeating Fields", total_repeating)
                        
                        if total_repeating > 0:
                            st.info(f"📌 Found {total_repeating} fields in repeating sections (e.g., multiple dependents)")
                    else:
                        st.error("Failed to extract text from PDF")
    
    with tab2:
        st.markdown("### Map Fields to Database")
        
        if st.session_state.form:
            form = st.session_state.form
            
            # Display parts
            for part_num, part in form.parts.items():
                with st.expander(f"Part {part_num}: {part.title}", expanded=(part_num == 1)):
                    
                    # Part statistics
                    regular_count = len(part.fields)
                    repeating_count = sum(len(group) for group in part.repeat_groups.values())
                    total_count = regular_count + repeating_count
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Regular Fields", regular_count)
                    with col2:
                        st.metric("Repeating Fields", repeating_count)
                    with col3:
                        st.metric("Total", total_count)
                    
                    if part.has_repeating_sections:
                        st.info(f"📌 This part contains {len(part.repeat_groups)} repeating groups")
                    
                    st.markdown("---")
                    
                    # Display regular fields
                    if part.fields:
                        st.markdown("#### Regular Fields")
                        for field in part.fields:
                            display_field_card(field, f"p{part_num}")
                    
                    # Display repeating groups
                    if part.repeat_groups:
                        st.markdown("#### Repeating Sections")
                        for group_name, group_fields in part.repeat_groups.items():
                            display_repeating_group(group_name, group_fields, f"p{part_num}")
        else:
            st.info("Upload and extract a form first")
    
    with tab3:
        st.markdown("### Questionnaire Fields")
        
        if st.session_state.form:
            quest_fields = []
            
            # Collect from regular and repeating fields
            for part in st.session_state.form.parts.values():
                quest_fields.extend([f for f in part.fields if f.in_questionnaire])
                
                for group_fields in part.repeat_groups.values():
                    quest_fields.extend([f for f in group_fields if f.in_questionnaire])
            
            if quest_fields:
                for field in quest_fields:
                    st.markdown(f"**{field.item_number}. {field.label}**")
                    
                    if field.is_repeating:
                        st.caption(f"From {field.repeat_group} group #{field.repeat_index}")
                    
                    field.value = st.text_area(
                        "Answer",
                        value=field.value,
                        key=f"quest_{field.unique_id}",
                        height=100
                    )
                    
                    if st.button("Move back", key=f"quest_back_{field.unique_id}"):
                        field.in_questionnaire = False
                        st.rerun()
                    
                    st.markdown("---")
            else:
                st.info("No questionnaire fields")
        else:
            st.info("Extract a form first")
    
    with tab4:
        st.markdown("### Export Results")
        
        if st.session_state.form:
            form = st.session_state.form
            
            # Prepare comprehensive export
            export_data = {
                "form_metadata": {
                    "form_number": form.form_number,
                    "form_title": form.form_title,
                    "edition_date": form.edition_date,
                    "total_pages": form.total_pages,
                    "export_date": datetime.now().isoformat()
                },
                "parts": [],
                "repeating_groups": {},
                "mapped_fields": [],
                "all_fields": []
            }
            
            # Export all fields including repeating
            for part in form.parts.values():
                part_data = {
                    "part_number": part.number,
                    "part_title": part.title,
                    "regular_fields": [],
                    "repeating_sections": {}
                }
                
                # Regular fields
                for field in part.fields:
                    field_data = {
                        "item_number": field.item_number,
                        "label": field.label,
                        "value": field.value,
                        "field_type": field.field_type
                    }
                    
                    if field.is_mapped:
                        field_data["mapping"] = f"{field.db_object}.{field.db_path}"
                        export_data["mapped_fields"].append(field_data)
                    
                    part_data["regular_fields"].append(field_data)
                    export_data["all_fields"].append(field_data)
                
                # Repeating groups
                for group_name, group_fields in part.repeat_groups.items():
                    group_data = []
                    for field in group_fields:
                        field_data = {
                            "item_number": field.item_number,
                            "label": field.label,
                            "value": field.value,
                            "repeat_group": field.repeat_group,
                            "repeat_index": field.repeat_index
                        }
                        
                        if field.is_mapped:
                            field_data["mapping"] = f"{field.db_object}.{field.db_path}"
                            export_data["mapped_fields"].append(field_data)
                        
                        group_data.append(field_data)
                        export_data["all_fields"].append(field_data)
                    
                    part_data["repeating_sections"][group_name] = group_data
                
                export_data["parts"].append(part_data)
            
            # Show statistics
            st.info(f"📊 Total fields: {len(export_data['all_fields'])} | Mapped: {len(export_data['mapped_fields'])}")
            
            # Export button
            json_str = json.dumps(export_data, indent=2)
            
            st.download_button(
                "📥 Download Complete JSON",
                json_str,
                f"{form.form_number}_complete_export.json",
                "application/json",
                use_container_width=True
            )
            
            # Preview
            with st.expander("Preview Export"):
                st.json(export_data)
        else:
            st.info("No data to export")

if __name__ == "__main__":
    main()
