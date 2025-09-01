#!/usr/bin/env python3
"""
USCIS FORM READER - FIXED VERSION WITH MANUAL OVERRIDE
=======================================================
Fixed duplicate key errors and added manual override option
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
    page_title="USCIS Form Reader - Fixed",
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

# Styles
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 10px;
        color: white;
        margin-bottom: 2rem;
    }
    .field-card {
        border: 1px solid #e0e0e0;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 8px;
        background: white;
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
</style>
""", unsafe_allow_html=True)

# ===== DATA STRUCTURES =====

@dataclass
class FormField:
    """Represents a single form field"""
    item_number: str
    label: str
    field_type: str = "text"
    value: str = ""
    part_number: int = 1
    page_number: int = 1
    parent_item: str = ""
    is_subfield: bool = False
    is_mapped: bool = False
    in_questionnaire: bool = False
    is_manual_override: bool = False  # New field for manual override
    db_object: str = ""
    db_path: str = ""
    unique_id: str = ""  # Unique identifier to prevent key conflicts
    
    def __post_init__(self):
        if not self.unique_id:
            self.unique_id = str(uuid.uuid4())[:8]

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
    """Complete USCIS form structure"""
    form_number: str
    form_title: str
    edition_date: str = ""
    total_pages: int = 0
    parts: Dict[int, FormPart] = field(default_factory=dict)
    raw_text: str = ""
    validation_passed: bool = False

# ===== DATABASE SCHEMA =====

DATABASE_SCHEMA = {
    "beneficiary": {
        "label": "👤 Beneficiary/Applicant",
        "paths": [
            "familyName",
            "givenName", 
            "middleName",
            "alienNumber",
            "uscisAccountNumber",
            "mailingAddress.inCareOf",
            "mailingAddress.streetNumberAndName",
            "mailingAddress.apt",
            "mailingAddress.city",
            "mailingAddress.state",
            "mailingAddress.zipCode",
            "physicalAddress.streetNumberAndName",
            "physicalAddress.city",
            "physicalAddress.state",
            "physicalAddress.zipCode",
            "countryOfBirth",
            "countryOfCitizenship",
            "dateOfBirth",
            "socialSecurityNumber",
            "i94Number",
            "passportNumber",
            "dateOfLastArrival",
            "currentNonimmigrantStatus",
            "statusExpirationDate",
            "daytimePhone",
            "mobilePhone",
            "emailAddress"
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
            "email"
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
            "applicationType",
            "requestedStatus",
            "requestedDate",
            "receiptNumber",
            "schoolName",
            "sevisId"
        ]
    },
    "manual_override": {
        "label": "✏️ Manual Override (Custom)",
        "paths": []  # Will be filled by user
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

# ===== FORM EXTRACTOR =====

class FormExtractor:
    """Extracts forms with validation"""
    
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
            st.error("Add OPENAI_API_KEY to secrets!")
    
    def extract_form(self, full_text: str, page_texts: Dict[int, str], total_pages: int) -> USCISForm:
        """Extract form structure from text"""
        
        if not self.client:
            return self.create_sample_form()
        
        # Identify form
        form_info = self._identify_form_type(full_text[:3000])
        
        form = USCISForm(
            form_number=form_info.get("form_number", "Unknown"),
            form_title=form_info.get("form_title", "USCIS Form"),
            edition_date=form_info.get("edition_date", ""),
            total_pages=total_pages,
            raw_text=full_text
        )
        
        # Extract parts
        parts_data = self._extract_all_parts(full_text)
        
        for part_data in parts_data:
            part = FormPart(
                number=part_data["number"],
                title=part_data["title"],
                page_start=part_data.get("page_start", 1),
                page_end=part_data.get("page_end", 1)
            )
            
            # Extract fields
            fields = self._extract_part_fields(full_text, part_data)
            part.fields = fields
            
            form.parts[part.number] = part
        
        # Validate
        is_valid, issues = self._validate_extraction(form)
        form.validation_passed = is_valid
        
        if not is_valid:
            st.warning("Validation issues found:")
            for issue in issues:
                st.write(f"- {issue}")
        
        return form
    
    def _identify_form_type(self, text: str) -> Dict:
        """Identify the form type"""
        
        prompt = """
        Identify this USCIS form.
        
        Return ONLY JSON:
        {
            "form_number": "I-539",
            "form_title": "Application to Extend/Change Nonimmigrant Status",
            "edition_date": "08/28/24"
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
    
    def _extract_all_parts(self, text: str) -> List[Dict]:
        """Extract all parts from the form"""
        
        prompt = """
        Extract ALL parts from this USCIS form.
        
        Look for "Part 1", "Part 2", etc.
        
        Return ONLY JSON array:
        [
            {
                "number": 1,
                "title": "Information About You",
                "page_start": 1,
                "page_end": 2
            }
        ]
        
        Text: """ + text[:10000]
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=1000
            )
            
            content = response.choices[0].message.content.strip()
            if "```" in content:
                content = content.split("```")[1].replace("json", "").strip()
            
            parts = json.loads(content)
            return parts if parts else self._get_default_parts()
            
        except Exception as e:
            st.error(f"Parts extraction error: {e}")
            return self._get_default_parts()
    
    def _extract_part_fields(self, text: str, part_data: Dict) -> List[FormField]:
        """Extract fields for a specific part"""
        
        part_num = part_data["number"]
        part_title = part_data["title"]
        
        prompt = f"""
        Extract ALL fields from Part {part_num}: {part_title}.
        
        CRITICAL for I-539 Part 1:
        - Item 1 is "Your Full Legal Name" with 3 input boxes (NOT 1.a, 1.b, 1.c)
        - Item 2 is "Alien Registration Number (A-Number)"
        - Item 3 is "USCIS Online Account Number"
        - Item 4 is "Your U.S. Mailing Address" (may have sub-components)
        
        Return ONLY JSON:
        [
            {{
                "item_number": "1",
                "label": "Your Full Legal Name",
                "field_type": "text",
                "has_subfields": true,
                "subfields": ["Family Name (Last Name)", "Given Name (First Name)", "Middle Name"]
            }},
            {{
                "item_number": "2",
                "label": "Alien Registration Number (A-Number)",
                "field_type": "text",
                "has_subfields": false
            }}
        ]
        
        Text: """ + text[:15000]
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=3000
            )
            
            content = response.choices[0].message.content.strip()
            if "```" in content:
                content = content.split("```")[1].replace("json", "").strip()
            
            fields_data = json.loads(content)
            
            # Convert to FormField objects
            fields = []
            for item in fields_data:
                # Create main field with unique ID
                main_field = FormField(
                    item_number=item["item_number"],
                    label=item["label"],
                    field_type=item.get("field_type", "text"),
                    part_number=part_num
                )
                fields.append(main_field)
                
                # Add subfields
                if item.get("has_subfields") and item.get("subfields"):
                    for i, subfield_label in enumerate(item["subfields"]):
                        subfield = FormField(
                            item_number=f"{item['item_number']}_sub_{i+1}",
                            label=subfield_label,
                            field_type="text",
                            part_number=part_num,
                            parent_item=item["item_number"],
                            is_subfield=True
                        )
                        fields.append(subfield)
            
            return fields
            
        except Exception as e:
            st.error(f"Field extraction error: {e}")
            return self._get_fallback_fields(part_num, part_title)
    
    def _validate_extraction(self, form: USCISForm) -> Tuple[bool, List[str]]:
        """Validate the extraction"""
        
        issues = []
        
        if not form.parts:
            issues.append("No parts extracted")
        
        # Validate I-539 structure
        if "539" in form.form_number:
            if 1 in form.parts:
                part1_fields = form.parts[1].fields
                field_numbers = [f.item_number for f in part1_fields if not f.is_subfield]
                
                if "1" not in field_numbers:
                    issues.append("Missing Item 1 (Your Full Legal Name)")
                
                if "2" not in field_numbers:
                    issues.append("Missing Item 2 (A-Number)")
                
                # Check for incorrect numbering
                if any(f.item_number in ["1.a", "1.b", "1.c"] for f in part1_fields):
                    issues.append("Incorrect: Name fields should NOT be 1.a, 1.b, 1.c")
        
        return len(issues) == 0, issues
    
    def _get_default_parts(self) -> List[Dict]:
        """Get default parts"""
        return [
            {"number": 1, "title": "Information About You", "page_start": 1, "page_end": 2},
            {"number": 2, "title": "Application Type", "page_start": 2, "page_end": 3},
            {"number": 3, "title": "Processing Information", "page_start": 3, "page_end": 4},
            {"number": 4, "title": "Additional Information", "page_start": 4, "page_end": 5},
            {"number": 5, "title": "Applicant's Contact Information", "page_start": 5, "page_end": 5}
        ]
    
    def _get_fallback_fields(self, part_num: int, part_title: str) -> List[FormField]:
        """Get fallback fields"""
        
        if part_num == 1:
            fields = []
            
            # Correct I-539 Part 1 structure
            fields.append(FormField("1", "Your Full Legal Name", part_number=1))
            fields.append(FormField("1_sub_1", "Family Name (Last Name)", part_number=1, parent_item="1", is_subfield=True))
            fields.append(FormField("1_sub_2", "Given Name (First Name)", part_number=1, parent_item="1", is_subfield=True))
            fields.append(FormField("1_sub_3", "Middle Name", part_number=1, parent_item="1", is_subfield=True))
            
            fields.append(FormField("2", "Alien Registration Number (A-Number)", part_number=1))
            fields.append(FormField("3", "USCIS Online Account Number", part_number=1))
            fields.append(FormField("4", "Your U.S. Mailing Address", part_number=1))
            fields.append(FormField("5", "Is your mailing address the same as your physical address?", field_type="checkbox", part_number=1))
            fields.append(FormField("6", "Your Current Physical Address", part_number=1))
            fields.append(FormField("7", "Country of Birth", part_number=1))
            fields.append(FormField("8", "Country of Citizenship", part_number=1))
            fields.append(FormField("9", "Date of Birth", field_type="date", part_number=1))
            fields.append(FormField("10", "U.S. Social Security Number", part_number=1))
            
            return fields
        
        # Generic fallback
        return [
            FormField(f"{part_num}.1", f"Field 1 for {part_title}", part_number=part_num),
            FormField(f"{part_num}.2", f"Field 2 for {part_title}", part_number=part_num)
        ]
    
    def create_sample_form(self) -> USCISForm:
        """Create sample I-539 form"""
        form = USCISForm(
            form_number="I-539",
            form_title="Application to Extend/Change Nonimmigrant Status",
            edition_date="08/28/24",
            total_pages=7
        )
        
        # Part 1
        part1 = FormPart(1, "Information About You")
        part1.fields = self._get_fallback_fields(1, "Information About You")
        form.parts[1] = part1
        
        # Part 2  
        part2 = FormPart(2, "Application Type")
        part2.fields = [
            FormField("1", "I am applying for", field_type="checkbox", part_number=2),
            FormField("2", "Change of status details", part_number=2),
            FormField("3", "Number of people included", part_number=2),
            FormField("4", "Requested effective date", field_type="date", part_number=2),
            FormField("5", "School name", part_number=2),
            FormField("6", "SEVIS ID Number", part_number=2)
        ]
        form.parts[2] = part2
        
        form.validation_passed = True
        return form

# ===== UI COMPONENTS =====

def display_field_card(field: FormField, key_prefix: str):
    """Display a field with manual mapping interface"""
    
    # Use unique_id in all keys to prevent duplicates
    unique_key = f"{key_prefix}_{field.unique_id}"
    
    # Determine card style
    if field.is_manual_override:
        card_class = "manual-override"
        status = "✏️ Manual Override"
    elif field.in_questionnaire:
        card_class = "field-questionnaire"
        status = "📝 Questionnaire"
    elif field.is_mapped:
        card_class = "field-mapped"
        status = f"✅ Mapped: {field.db_object}"
    else:
        card_class = "field-unmapped"
        status = "❓ Not Mapped"
    
    # Indentation for subfields
    indent = "    " if field.is_subfield else ""
    
    st.markdown(f'<div class="field-card {card_class}">', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([3, 2, 2])
    
    with col1:
        if field.is_subfield:
            st.markdown(f"{indent}↳ **{field.label}**")
            st.caption(f"Part of Item {field.parent_item}")
        else:
            st.markdown(f"**Item {field.item_number}: {field.label}**")
    
    with col2:
        # Value input
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
        if not field.is_mapped and not field.in_questionnaire and not field.is_manual_override:
            c1, c2 = st.columns(2)
            with c1:
                if st.button("📍 Map", key=f"{unique_key}_map"):
                    st.session_state[f"show_mapping_{field.unique_id}"] = True
                    st.rerun()
            with c2:
                if st.button("📝 Quest", key=f"{unique_key}_quest"):
                    field.in_questionnaire = True
                    st.rerun()
        elif field.is_mapped or field.is_manual_override:
            if st.button("❌ Unmap", key=f"{unique_key}_unmap"):
                field.is_mapped = False
                field.is_manual_override = False
                field.db_object = ""
                field.db_path = ""
                st.rerun()
        elif field.in_questionnaire:
            if st.button("↩️ Back", key=f"{unique_key}_back"):
                field.in_questionnaire = False
                st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Manual mapping interface
    if st.session_state.get(f"show_mapping_{field.unique_id}"):
        show_manual_mapping(field, unique_key)

def show_manual_mapping(field: FormField, unique_key: str):
    """Show manual mapping interface with override option"""
    
    st.markdown("---")
    st.markdown("### 🔗 Map Field to Database")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Database object selection (including manual override)
        db_options = list(DATABASE_SCHEMA.keys())
        db_labels = [DATABASE_SCHEMA[k]["label"] for k in db_options]
        
        selected_idx = st.selectbox(
            "Select Database Object",
            range(len(db_options)),
            format_func=lambda x: db_labels[x],
            key=f"{unique_key}_db_obj_select",
            index=None,
            placeholder="Choose database object..."
        )
        
        selected_obj = db_options[selected_idx] if selected_idx is not None else None
    
    with col2:
        if selected_obj == "manual_override":
            # Manual override - custom path entry
            selected_path = st.text_input(
                "Enter custom database path",
                key=f"{unique_key}_manual_path",
                placeholder="e.g., customObject.customField"
            )
        elif selected_obj:
            # Normal path selection
            paths = DATABASE_SCHEMA[selected_obj]["paths"]
            selected_path = st.selectbox(
                "Select Field Path",
                [""] + paths + ["[Custom Path]"],
                key=f"{unique_key}_db_path_select"
            )
            
            if selected_path == "[Custom Path]":
                selected_path = st.text_input(
                    "Enter custom path",
                    key=f"{unique_key}_custom_path",
                    placeholder="e.g., customField"
                )
        else:
            selected_path = None
    
    # Preview mapping
    if selected_obj and selected_path:
        st.info(f"📍 Preview: {field.item_number} → {selected_obj}.{selected_path}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("✅ Apply Mapping", key=f"{unique_key}_apply", type="primary"):
            if selected_obj and selected_path:
                field.is_mapped = True
                field.is_manual_override = (selected_obj == "manual_override")
                field.db_object = selected_obj
                field.db_path = selected_path
                del st.session_state[f"show_mapping_{field.unique_id}"]
                st.success(f"Mapped to {selected_obj}.{selected_path}")
                st.rerun()
            else:
                st.error("Please select both object and path")
    
    with col2:
        if st.button("Cancel", key=f"{unique_key}_cancel"):
            del st.session_state[f"show_mapping_{field.unique_id}"]
            st.rerun()
    
    st.markdown("---")

# ===== MAIN APPLICATION =====

def main():
    st.markdown('<div class="main-header">', unsafe_allow_html=True)
    st.title("🎯 USCIS Form Reader - Fixed Version")
    st.markdown("Accurate extraction with manual override option")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Initialize
    if 'form' not in st.session_state:
        st.session_state.form = None
    if 'extractor' not in st.session_state:
        st.session_state.extractor = FormExtractor()
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 📊 Database Schema")
        
        for key, info in DATABASE_SCHEMA.items():
            with st.expander(info["label"]):
                if key == "manual_override":
                    st.info("Custom mapping - enter any database path")
                else:
                    for path in info["paths"][:5]:
                        st.code(path)
                    if len(info["paths"]) > 5:
                        st.caption(f"... and {len(info['paths'])-5} more")
        
        st.markdown("---")
        
        if st.button("📋 Load Sample I-539", type="secondary", use_container_width=True):
            st.session_state.form = st.session_state.extractor.create_sample_form()
            st.success("Sample form loaded!")
            st.rerun()
        
        if st.button("🔄 Clear All", type="secondary", use_container_width=True):
            st.session_state.form = None
            # Clear all mapping states
            for key in list(st.session_state.keys()):
                if key.startswith("show_mapping_"):
                    del st.session_state[key]
            st.rerun()
        
        if st.session_state.form:
            st.markdown("## 📈 Statistics")
            form = st.session_state.form
            
            total_fields = sum(len(p.fields) for p in form.parts.values())
            mapped = sum(1 for p in form.parts.values() for f in p.fields if f.is_mapped)
            quest = sum(1 for p in form.parts.values() for f in p.fields if f.in_questionnaire)
            manual = sum(1 for p in form.parts.values() for f in p.fields if f.is_manual_override)
            
            st.metric("Total Fields", total_fields)
            st.metric("Mapped", mapped)
            st.metric("Questionnaire", quest)
            st.metric("Manual Override", manual)
            
            if form.validation_passed:
                st.success("✅ Valid")
            else:
                st.warning("⚠️ Check validation")
    
    # Main tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📤 Upload",
        "🔗 Map Fields",
        "📝 Questionnaire",
        "💾 Export"
    ])
    
    with tab1:
        st.markdown("### Upload USCIS Form PDF")
        
        uploaded_file = st.file_uploader(
            "Choose PDF file",
            type=['pdf']
        )
        
        if uploaded_file:
            if st.button("🚀 Extract Fields", type="primary", use_container_width=True):
                with st.spinner("Extracting..."):
                    # Extract PDF
                    full_text, page_texts, total_pages = extract_pdf_with_structure(uploaded_file)
                    
                    if full_text:
                        # Extract form
                        form = st.session_state.extractor.extract_form(
                            full_text, page_texts, total_pages
                        )
                        
                        st.session_state.form = form
                        
                        if form.validation_passed:
                            st.success(f"✅ Extracted {form.form_number}: {form.form_title}")
                        else:
                            st.warning("⚠️ Extraction completed with warnings")
                        
                        # Show stats
                        total_fields = sum(len(p.fields) for p in form.parts.values())
                        st.info(f"Found {len(form.parts)} parts with {total_fields} fields")
                    else:
                        st.error("Failed to extract text from PDF")
    
    with tab2:
        st.markdown("### Map Fields to Database")
        
        if st.session_state.form:
            form = st.session_state.form
            
            # Display parts
            for part_num, part in form.parts.items():
                with st.expander(f"Part {part_num}: {part.title}", expanded=(part_num == 1)):
                    
                    # Part stats
                    part_fields_count = len(part.fields)
                    part_mapped = sum(1 for f in part.fields if f.is_mapped)
                    part_quest = sum(1 for f in part.fields if f.in_questionnaire)
                    part_manual = sum(1 for f in part.fields if f.is_manual_override)
                    
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Fields", part_fields_count)
                    with col2:
                        st.metric("Mapped", part_mapped)
                    with col3:
                        st.metric("Quest", part_quest)
                    with col4:
                        st.metric("Manual", part_manual)
                    
                    st.markdown("---")
                    
                    # Display fields grouped by item
                    displayed_subfields = set()
                    
                    for field in part.fields:
                        # Skip subfields that were already displayed
                        if field.unique_id in displayed_subfields:
                            continue
                        
                        if not field.is_subfield:
                            # Display main field
                            display_field_card(field, f"p{part_num}")
                            
                            # Display its subfields
                            subfields = [f for f in part.fields if f.parent_item == field.item_number]
                            for subfield in subfields:
                                display_field_card(subfield, f"p{part_num}")
                                displayed_subfields.add(subfield.unique_id)
                            
                            st.markdown("---")
        else:
            st.info("Upload and extract a form first")
    
    with tab3:
        st.markdown("### Questionnaire Fields")
        
        if st.session_state.form:
            quest_fields = []
            for part in st.session_state.form.parts.values():
                quest_fields.extend([f for f in part.fields if f.in_questionnaire])
            
            if quest_fields:
                for field in quest_fields:
                    st.markdown(f"**Item {field.item_number}: {field.label}**")
                    
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
                st.info("No questionnaire fields. Use '📝 Quest' button to add fields.")
        else:
            st.info("Extract a form first")
    
    with tab4:
        st.markdown("### Export Results")
        
        if st.session_state.form:
            form = st.session_state.form
            
            # Prepare export
            export_data = {
                "form_metadata": {
                    "form_number": form.form_number,
                    "form_title": form.form_title,
                    "edition_date": form.edition_date,
                    "total_pages": form.total_pages,
                    "validation_passed": form.validation_passed,
                    "export_date": datetime.now().isoformat()
                },
                "mapped_fields": [],
                "questionnaire_fields": [],
                "manual_override_fields": [],
                "all_fields": []
            }
            
            # Collect data
            for part in form.parts.values():
                for field in part.fields:
                    field_data = {
                        "item_number": field.item_number,
                        "label": field.label,
                        "value": field.value,
                        "field_type": field.field_type,
                        "part": part.number,
                        "is_subfield": field.is_subfield,
                        "parent_item": field.parent_item
                    }
                    
                    export_data["all_fields"].append(field_data)
                    
                    if field.is_manual_override:
                        field_data["custom_mapping"] = f"{field.db_object}.{field.db_path}"
                        export_data["manual_override_fields"].append(field_data)
                    elif field.is_mapped:
                        field_data["db_object"] = field.db_object
                        field_data["db_path"] = field.db_path
                        export_data["mapped_fields"].append(field_data)
                    elif field.in_questionnaire:
                        export_data["questionnaire_fields"].append(field_data)
            
            # Show stats
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total", len(export_data["all_fields"]))
            with col2:
                st.metric("Mapped", len(export_data["mapped_fields"]))
            with col3:
                st.metric("Quest", len(export_data["questionnaire_fields"]))
            with col4:
                st.metric("Manual", len(export_data["manual_override_fields"]))
            
            # Export button
            json_str = json.dumps(export_data, indent=2)
            
            st.download_button(
                "📥 Download JSON",
                json_str,
                f"{form.form_number}_export.json",
                "application/json",
                use_container_width=True
            )
            
            # Preview
            with st.expander("Preview"):
                st.json(export_data)
        else:
            st.info("No data to export")

if __name__ == "__main__":
    main()
