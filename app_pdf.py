#!/usr/bin/env python3
"""
USCIS FORM READER - SIMPLIFIED WORKING VERSION
==============================================
Clean implementation with no errors
"""

import os
import json
import re
import streamlit as st
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import logging

# Import checks
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    st.error("Please install PyMuPDF: pip install pymupdf")

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    st.error("Please install OpenAI: pip install openai")

# Page config
st.set_page_config(
    page_title="USCIS KK Form Reader",
    page_icon="📄",
    layout="wide"
)

# CSS
st.markdown("""
<style>
    .stButton > button {
        width: 100%;
    }
    .field-box {
        border: 1px solid #ddd;
        padding: 10px;
        margin: 10px 0;
        border-radius: 5px;
    }
    .mapped {
        background-color: #d4edda;
        border-color: #28a745;
    }
    .questionnaire {
        background-color: #d1ecf1;
        border-color: #17a2b8;
    }
    .unmapped {
        background-color: #fff3cd;
        border-color: #ffc107;
    }
</style>
""", unsafe_allow_html=True)

# ===== DATA MODELS =====

@dataclass
class FormField:
    field_id: str
    label: str
    value: str = ""
    part_number: int = 1
    is_nested: bool = False
    parent_label: str = ""
    field_type: str = "text"
    is_mapped: bool = False
    in_questionnaire: bool = False
    db_object: str = ""
    db_path: str = ""

@dataclass
class FormPart:
    number: int
    title: str
    fields: List[FormField] = field(default_factory=list)

@dataclass
class USCISForm:
    form_number: str = "Unknown"
    form_title: str = "USCIS Form"
    parts: Dict[int, FormPart] = field(default_factory=dict)
    raw_text: str = ""

# ===== DATABASE SCHEMA =====

DATABASE_SCHEMA = {
    "beneficiary": {
        "label": "👤 Beneficiary Information",
        "fields": [
            "lastName",
            "firstName", 
            "middleName",
            "alienNumber",
            "uscisAccountNumber",
            "dateOfBirth",
            "ssn",
            "countryOfBirth",
            "countryOfCitizenship",
            "address.street",
            "address.city",
            "address.state",
            "address.zip",
            "phone",
            "email"
        ]
    },
    "petitioner": {
        "label": "🏢 Petitioner/Employer",
        "fields": [
            "companyName",
            "ein",
            "contactPerson",
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
        "fields": [
            "lastName",
            "firstName",
            "barNumber",
            "firmName",
            "address",
            "phone",
            "email"
        ]
    },
    "application": {
        "label": "📋 Application Details",
        "fields": [
            "receiptNumber",
            "priorityDate",
            "classification",
            "requestedAction"
        ]
    }
}

# ===== CORE FUNCTIONS =====

def extract_pdf_text(pdf_file) -> str:
    """Extract text from PDF"""
    if not PYMUPDF_AVAILABLE:
        return ""
    
    try:
        pdf_file.seek(0)
        doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
        
        text = ""
        for page in doc:
            text += page.get_text()
        
        doc.close()
        return text
    except Exception as e:
        st.error(f"PDF Error: {e}")
        return ""

def extract_fields_with_ai(text: str) -> USCISForm:
    """Extract fields using OpenAI"""
    
    # Get API key
    api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        st.error("Please add OPENAI_API_KEY to secrets")
        return create_sample_form()
    
    try:
        client = openai.OpenAI(api_key=api_key)
        
        # Extract form structure
        prompt = """
        Extract ALL fields from this USCIS form. Pay special attention to nested fields.
        
        For example, if you see:
        "1. Your Full Legal Name
            a. Family Name (Last Name)
            b. Given Name (First Name)
            c. Middle Name"
        
        Return JSON with this structure:
        {
            "form_number": "I-539",
            "form_title": "Application to Extend/Change",
            "parts": [
                {
                    "number": 1,
                    "title": "Information About You",
                    "fields": [
                        {
                            "field_id": "1",
                            "label": "Your Full Legal Name",
                            "is_nested": false,
                            "parent_label": ""
                        },
                        {
                            "field_id": "1.a",
                            "label": "Family Name (Last Name)",
                            "is_nested": true,
                            "parent_label": "Your Full Legal Name"
                        }
                    ]
                }
            ]
        }
        
        Text: """ + text[:8000]
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=3000
        )
        
        # Parse response
        content = response.choices[0].message.content
        if '```json' in content:
            content = content.split('```json')[1].split('```')[0]
        elif '```' in content:
            content = content.split('```')[1].split('```')[0]
        
        data = json.loads(content.strip())
        
        # Create form object
        form = USCISForm(
            form_number=data.get("form_number", "Unknown"),
            form_title=data.get("form_title", "USCIS Form"),
            raw_text=text
        )
        
        # Add parts and fields
        for part_data in data.get("parts", []):
            part = FormPart(
                number=part_data["number"],
                title=part_data["title"]
            )
            
            for field_data in part_data.get("fields", []):
                field = FormField(
                    field_id=field_data["field_id"],
                    label=field_data["label"],
                    part_number=part.number,
                    is_nested=field_data.get("is_nested", False),
                    parent_label=field_data.get("parent_label", ""),
                    field_type=field_data.get("field_type", "text")
                )
                part.fields.append(field)
            
            form.parts[part.number] = part
        
        return form
        
    except Exception as e:
        st.error(f"AI Extraction Error: {e}")
        return create_sample_form()

def create_sample_form() -> USCISForm:
    """Create sample form for testing"""
    form = USCISForm("I-539", "Application to Extend/Change Nonimmigrant Status")
    
    # Part 1
    part1 = FormPart(1, "Information About You")
    part1.fields = [
        FormField("1", "Your Full Legal Name", part_number=1),
        FormField("1.a", "Family Name (Last Name)", part_number=1, is_nested=True, parent_label="Your Full Legal Name"),
        FormField("1.b", "Given Name (First Name)", part_number=1, is_nested=True, parent_label="Your Full Legal Name"),
        FormField("1.c", "Middle Name", part_number=1, is_nested=True, parent_label="Your Full Legal Name"),
        FormField("2", "Alien Registration Number (A-Number)", part_number=1),
        FormField("3", "USCIS Online Account Number", part_number=1),
        FormField("4", "U.S. Mailing Address", part_number=1),
        FormField("4.a", "Street Number and Name", part_number=1, is_nested=True, parent_label="U.S. Mailing Address"),
        FormField("4.b", "City or Town", part_number=1, is_nested=True, parent_label="U.S. Mailing Address"),
        FormField("4.c", "State", part_number=1, is_nested=True, parent_label="U.S. Mailing Address"),
        FormField("4.d", "ZIP Code", part_number=1, is_nested=True, parent_label="U.S. Mailing Address"),
        FormField("5", "Date of Birth", part_number=1, field_type="date"),
        FormField("6", "Country of Birth", part_number=1),
        FormField("7", "Country of Citizenship", part_number=1),
        FormField("8", "U.S. Social Security Number", part_number=1, field_type="ssn")
    ]
    form.parts[1] = part1
    
    # Part 2
    part2 = FormPart(2, "Application Type")
    part2.fields = [
        FormField("1", "I am applying for", part_number=2),
        FormField("1.a", "Extension of stay", part_number=2, is_nested=True, parent_label="I am applying for", field_type="checkbox"),
        FormField("1.b", "Change of status", part_number=2, is_nested=True, parent_label="I am applying for", field_type="checkbox"),
        FormField("2", "Requested Nonimmigrant Category", part_number=2)
    ]
    form.parts[2] = part2
    
    return form

def validate_extraction(form: USCISForm) -> Dict:
    """Validate the extracted form"""
    results = {
        "total_fields": 0,
        "issues": [],
        "suggestions": []
    }
    
    # Count fields
    for part in form.parts.values():
        results["total_fields"] += len(part.fields)
    
    # Check Part 1 for expected fields
    if 1 in form.parts:
        part1_fields = [f.field_id for f in form.parts[1].fields]
        
        # Check for name fields
        if not any("1.a" in f or "1a" in f for f in part1_fields):
            results["issues"].append("Missing field 1.a (Family Name)")
        if not any("1.b" in f or "1b" in f for f in part1_fields):
            results["issues"].append("Missing field 1.b (Given Name)")
        
        # Check for nested structure
        nested_count = sum(1 for f in form.parts[1].fields if f.is_nested)
        if nested_count == 0:
            results["suggestions"].append("No nested fields detected - check extraction")
    
    results["is_valid"] = len(results["issues"]) == 0
    
    return results

# ===== UI COMPONENTS =====

def show_field(field: FormField, key_prefix: str):
    """Display a single field"""
    
    # Determine status
    if field.in_questionnaire:
        status = "📝 Questionnaire"
        css_class = "questionnaire"
    elif field.is_mapped:
        status = f"✅ {field.db_object}"
        css_class = "mapped"
    else:
        status = "❓ Not Mapped"
        css_class = "unmapped"
    
    # Field container
    with st.container():
        if field.is_nested:
            st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;↳ **{field.field_id}. {field.label}**")
        else:
            st.markdown(f"**{field.field_id}. {field.label}**")
        
        col1, col2, col3 = st.columns([3, 2, 2])
        
        with col1:
            # Value input
            if field.field_type == "date":
                field.value = st.date_input(
                    "Value",
                    key=f"{key_prefix}_val_{field.field_id}",
                    label_visibility="collapsed"
                )
            elif field.field_type == "checkbox":
                field.value = st.selectbox(
                    "Value",
                    ["", "Yes", "No"],
                    key=f"{key_prefix}_val_{field.field_id}",
                    label_visibility="collapsed"
                )
            else:
                field.value = st.text_input(
                    "Value",
                    value=field.value,
                    key=f"{key_prefix}_val_{field.field_id}",
                    label_visibility="collapsed"
                )
        
        with col2:
            st.markdown(f"**Status:** {status}")
        
        with col3:
            # Action buttons
            if not field.is_mapped and not field.in_questionnaire:
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("Map", key=f"{key_prefix}_map_{field.field_id}"):
                        st.session_state[f"mapping_{field.field_id}"] = True
                        st.rerun()
                with col_b:
                    if st.button("Quest", key=f"{key_prefix}_quest_{field.field_id}"):
                        field.in_questionnaire = True
                        st.rerun()
            elif field.is_mapped:
                if st.button("Unmap", key=f"{key_prefix}_unmap_{field.field_id}"):
                    field.is_mapped = False
                    field.db_object = ""
                    field.db_path = ""
                    st.rerun()
            elif field.in_questionnaire:
                if st.button("Back", key=f"{key_prefix}_back_{field.field_id}"):
                    field.in_questionnaire = False
                    st.rerun()
    
    # Mapping interface
    if st.session_state.get(f"mapping_{field.field_id}"):
        with st.container():
            st.markdown("---")
            st.markdown("### Map to Database")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Database object dropdown
                db_options = list(DATABASE_SCHEMA.keys())
                db_labels = [DATABASE_SCHEMA[k]["label"] for k in db_options]
                
                selected_idx = st.selectbox(
                    "Database Object",
                    range(len(db_options)),
                    format_func=lambda x: db_labels[x],
                    key=f"db_obj_{field.field_id}"
                )
                
                selected_obj = db_options[selected_idx] if selected_idx is not None else None
            
            with col2:
                # Field path dropdown
                if selected_obj:
                    field_paths = DATABASE_SCHEMA[selected_obj]["fields"]
                    selected_path = st.selectbox(
                        "Field Path",
                        field_paths,
                        key=f"db_path_{field.field_id}"
                    )
                else:
                    selected_path = None
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("✅ Apply", key=f"apply_{field.field_id}"):
                    if selected_obj and selected_path:
                        field.is_mapped = True
                        field.db_object = selected_obj
                        field.db_path = selected_path
                        del st.session_state[f"mapping_{field.field_id}"]
                        st.success(f"Mapped to {selected_obj}.{selected_path}")
                        st.rerun()
            
            with col2:
                if st.button("Cancel", key=f"cancel_{field.field_id}"):
                    del st.session_state[f"mapping_{field.field_id}"]
                    st.rerun()
            
            st.markdown("---")

# ===== MAIN APP =====

def main():
    st.title("📄 USCIS Form Reader")
    st.markdown("Extract fields from USCIS forms with proper nesting support")
    
    # Initialize session state
    if 'form' not in st.session_state:
        st.session_state.form = None
    
    # Sidebar
    with st.sidebar:
        st.markdown("## Database Schema")
        
        for key, info in DATABASE_SCHEMA.items():
            with st.expander(info["label"]):
                for field in info["fields"][:5]:
                    st.code(field)
                if len(info["fields"]) > 5:
                    st.caption(f"... and {len(info['fields'])-5} more")
        
        st.markdown("---")
        
        if st.button("Load Sample Form", type="secondary"):
            st.session_state.form = create_sample_form()
            st.success("Sample form loaded!")
            st.rerun()
        
        if st.button("Clear All", type="secondary"):
            st.session_state.form = None
            for key in list(st.session_state.keys()):
                if key.startswith("mapping_"):
                    del st.session_state[key]
            st.rerun()
    
    # Main content
    tab1, tab2, tab3, tab4 = st.tabs(["Upload", "Fields", "Questionnaire", "Export"])
    
    with tab1:
        st.markdown("### Upload USCIS Form")
        
        uploaded_file = st.file_uploader("Choose PDF file", type=['pdf'])
        
        if uploaded_file:
            if st.button("Extract Fields", type="primary"):
                with st.spinner("Extracting..."):
                    # Extract text
                    text = extract_pdf_text(uploaded_file)
                    
                    if text:
                        # Extract fields with AI
                        form = extract_fields_with_ai(text)
                        st.session_state.form = form
                        
                        # Validate
                        validation = validate_extraction(form)
                        
                        # Show results
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Form", form.form_number)
                        with col2:
                            st.metric("Parts", len(form.parts))
                        with col3:
                            st.metric("Fields", validation["total_fields"])
                        
                        if validation["is_valid"]:
                            st.success("✅ Extraction successful!")
                        else:
                            st.warning("⚠️ Some issues detected")
                            for issue in validation["issues"]:
                                st.error(issue)
                        
                        for suggestion in validation.get("suggestions", []):
                            st.info(suggestion)
                    else:
                        st.error("Could not extract text from PDF")
    
    with tab2:
        st.markdown("### Map Fields")
        
        if st.session_state.form:
            for part_num, part in st.session_state.form.parts.items():
                with st.expander(f"Part {part_num}: {part.title}", expanded=(part_num==1)):
                    
                    # Group fields by parent
                    parent_fields = [f for f in part.fields if not f.is_nested]
                    
                    for parent in parent_fields:
                        # Show parent field
                        show_field(parent, f"p{part_num}")
                        
                        # Show nested fields
                        nested = [f for f in part.fields 
                                 if f.is_nested and f.parent_label == parent.label]
                        for child in nested:
                            show_field(child, f"p{part_num}")
                        
                        if parent != parent_fields[-1] or nested:
                            st.markdown("---")
        else:
            st.info("Upload a form or load sample to begin")
    
    with tab3:
        st.markdown("### Questionnaire Fields")
        
        if st.session_state.form:
            quest_fields = []
            for part in st.session_state.form.parts.values():
                quest_fields.extend([f for f in part.fields if f.in_questionnaire])
            
            if quest_fields:
                for field in quest_fields:
                    st.markdown(f"**{field.field_id}. {field.label}**")
                    
                    field.value = st.text_area(
                        "Answer",
                        value=str(field.value),
                        key=f"q_{field.field_id}"
                    )
                    
                    if st.button("Move Back", key=f"qback_{field.field_id}"):
                        field.in_questionnaire = False
                        st.rerun()
                    
                    st.markdown("---")
            else:
                st.info("No questionnaire fields. Use 'Quest' button to add fields.")
        else:
            st.info("No form loaded")
    
    with tab4:
        st.markdown("### Export Data")
        
        if st.session_state.form:
            # Prepare export
            export_data = {
                "form_info": {
                    "form_number": st.session_state.form.form_number,
                    "form_title": st.session_state.form.form_title,
                    "export_date": datetime.now().isoformat()
                },
                "mapped_fields": [],
                "questionnaire_fields": [],
                "all_fields": []
            }
            
            for part in st.session_state.form.parts.values():
                for field in part.fields:
                    field_data = {
                        "field_id": field.field_id,
                        "label": field.label,
                        "value": str(field.value),
                        "part": part.number,
                        "is_nested": field.is_nested,
                        "parent_label": field.parent_label
                    }
                    
                    export_data["all_fields"].append(field_data)
                    
                    if field.is_mapped:
                        field_data["db_object"] = field.db_object
                        field_data["db_path"] = field.db_path
                        export_data["mapped_fields"].append(field_data)
                    elif field.in_questionnaire:
                        export_data["questionnaire_fields"].append(field_data)
            
            # Show summary
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Fields", len(export_data["all_fields"]))
            with col2:
                st.metric("Mapped", len(export_data["mapped_fields"]))
            with col3:
                st.metric("Questionnaire", len(export_data["questionnaire_fields"]))
            
            # Export button
            json_str = json.dumps(export_data, indent=2)
            
            st.download_button(
                "📥 Download JSON",
                json_str,
                f"{st.session_state.form.form_number}_export.json",
                "application/json"
            )
            
            # Preview
            with st.expander("Preview Export"):
                st.json(export_data)
        else:
            st.info("No form to export")

if __name__ == "__main__":
    main()
