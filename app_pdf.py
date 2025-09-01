#!/usr/bin/env python3
"""
USCIS FORM READER - MINIMAL WORKING VERSION
===========================================
This is app.py - DO NOT name it app_final.py
"""

import streamlit as st
import json
from datetime import datetime
from typing import Dict, List
from dataclasses import dataclass, field, asdict

# Page config MUST be first
st.set_page_config(
    page_title="USCIS Form Reader",
    page_icon="📄",
    layout="wide"
)

# Check for required libraries
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    
try:
    import fitz
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

# ===== SIMPLE DATA CLASSES =====

@dataclass
class Field:
    id: str
    label: str
    value: str = ""
    part: int = 1
    nested: bool = False
    parent: str = ""
    mapped: bool = False
    questionnaire: bool = False
    db_object: str = ""
    db_path: str = ""

@dataclass
class Part:
    number: int
    title: str
    fields: List[Field] = field(default_factory=list)

@dataclass
class Form:
    number: str = "Unknown"
    title: str = "USCIS Form"
    parts: Dict[int, Part] = field(default_factory=dict)

# ===== DATABASE SCHEMA =====

DB_SCHEMA = {
    "beneficiary": {
        "name": "Beneficiary Information",
        "paths": ["lastName", "firstName", "middleName", "alienNumber", "dateOfBirth", "ssn", "address"]
    },
    "petitioner": {
        "name": "Petitioner/Employer",
        "paths": ["companyName", "ein", "contactName", "address", "phone", "email"]
    },
    "attorney": {
        "name": "Attorney Information",
        "paths": ["lastName", "firstName", "barNumber", "firmName", "phone", "email"]
    }
}

# ===== HELPER FUNCTIONS =====

def create_sample_form():
    """Create a sample I-539 form for testing"""
    form = Form("I-539", "Application to Extend/Change Status")
    
    # Part 1
    part1 = Part(1, "Information About You")
    part1.fields = [
        Field("1", "Your Full Legal Name", part=1),
        Field("1.a", "Family Name (Last Name)", part=1, nested=True, parent="Your Full Legal Name"),
        Field("1.b", "Given Name (First Name)", part=1, nested=True, parent="Your Full Legal Name"),
        Field("1.c", "Middle Name", part=1, nested=True, parent="Your Full Legal Name"),
        Field("2", "Alien Registration Number", part=1),
        Field("3", "Date of Birth", part=1),
        Field("4", "Country of Birth", part=1),
        Field("5", "Social Security Number", part=1)
    ]
    form.parts[1] = part1
    
    # Part 2
    part2 = Part(2, "Application Type")
    part2.fields = [
        Field("1", "I am applying for", part=2),
        Field("1.a", "Extension of stay", part=2, nested=True, parent="I am applying for"),
        Field("1.b", "Change of status", part=2, nested=True, parent="I am applying for")
    ]
    form.parts[2] = part2
    
    return form

def extract_pdf_text(file):
    """Extract text from PDF"""
    if not PYMUPDF_AVAILABLE:
        st.error("PyMuPDF not installed. Using sample data instead.")
        return None
    
    try:
        import fitz
        file.seek(0)
        doc = fitz.open(stream=file.read(), filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text
    except Exception as e:
        st.error(f"PDF Error: {e}")
        return None

def extract_with_ai(text):
    """Extract fields using AI"""
    if not OPENAI_AVAILABLE:
        st.warning("OpenAI not available. Using sample form.")
        return create_sample_form()
    
    api_key = st.secrets.get("OPENAI_API_KEY", "")
    if not api_key:
        st.error("No API key found. Using sample form.")
        return create_sample_form()
    
    try:
        client = openai.OpenAI(api_key=api_key)
        
        prompt = f"""Extract fields from this USCIS form. Look for patterns like:
        1. Field Name
        1.a. Nested Field
        
        Return JSON:
        {{
            "number": "I-539",
            "title": "Form Title",
            "parts": [
                {{
                    "number": 1,
                    "title": "Part Title",
                    "fields": [
                        {{"id": "1", "label": "Field", "nested": false, "parent": ""}},
                        {{"id": "1.a", "label": "Nested", "nested": true, "parent": "Field"}}
                    ]
                }}
            ]
        }}
        
        Text: {text[:5000]}"""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=2000
        )
        
        content = response.choices[0].message.content
        if "```" in content:
            content = content.split("```")[1].replace("json", "").strip()
        
        data = json.loads(content)
        
        # Convert to Form object
        form = Form(data.get("number", "Unknown"), data.get("title", "Form"))
        
        for part_data in data.get("parts", []):
            part = Part(part_data["number"], part_data["title"])
            for field_data in part_data.get("fields", []):
                f = Field(
                    id=field_data["id"],
                    label=field_data["label"],
                    part=part.number,
                    nested=field_data.get("nested", False),
                    parent=field_data.get("parent", "")
                )
                part.fields.append(f)
            form.parts[part.number] = part
        
        return form
        
    except Exception as e:
        st.error(f"AI Error: {e}. Using sample form.")
        return create_sample_form()

# ===== MAIN UI =====

def main():
    st.title("📄 USCIS Form Reader - Working Version")
    
    # Initialize
    if 'form' not in st.session_state:
        st.session_state.form = None
    
    # Sidebar
    with st.sidebar:
        st.markdown("## Quick Actions")
        
        if st.button("📋 Load Sample Form", use_container_width=True):
            st.session_state.form = create_sample_form()
            st.success("Sample I-539 loaded!")
            st.rerun()
        
        if st.button("🔄 Clear All", use_container_width=True):
            st.session_state.form = None
            st.rerun()
        
        st.markdown("---")
        st.markdown("## Database Objects")
        for key, val in DB_SCHEMA.items():
            st.markdown(f"**{val['name']}**")
            for p in val['paths'][:3]:
                st.caption(f"• {p}")
    
    # Main tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📤 Upload", "🔗 Map Fields", "📝 Questionnaire", "💾 Export"])
    
    with tab1:
        st.markdown("### Upload USCIS Form PDF")
        
        file = st.file_uploader("Choose PDF", type=['pdf'])
        
        if file:
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🚀 Extract Fields", type="primary"):
                    with st.spinner("Processing..."):
                        text = extract_pdf_text(file)
                        if text:
                            form = extract_with_ai(text)
                        else:
                            form = create_sample_form()
                        
                        st.session_state.form = form
                        st.success(f"Loaded: {form.number} - {form.title}")
                        
                        # Show stats
                        total = sum(len(p.fields) for p in form.parts.values())
                        st.info(f"Found {len(form.parts)} parts with {total} fields")
        
        # Show current form info
        if st.session_state.form:
            st.markdown("### Current Form")
            form = st.session_state.form
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Form Number", form.number)
            with col2:
                st.metric("Parts", len(form.parts))
            with col3:
                total = sum(len(p.fields) for p in form.parts.values())
                st.metric("Total Fields", total)
    
    with tab2:
        st.markdown("### Map Fields to Database")
        
        if st.session_state.form:
            form = st.session_state.form
            
            for part_num, part in form.parts.items():
                with st.expander(f"Part {part_num}: {part.title}", expanded=(part_num==1)):
                    
                    for field in part.fields:
                        # Field display
                        prefix = "  ↳ " if field.nested else ""
                        st.markdown(f"**{prefix}{field.id}. {field.label}**")
                        
                        col1, col2, col3 = st.columns([3, 2, 2])
                        
                        with col1:
                            field.value = st.text_input(
                                "Value",
                                value=field.value,
                                key=f"val_{part_num}_{field.id}",
                                label_visibility="collapsed"
                            )
                        
                        with col2:
                            if field.mapped:
                                st.success(f"Mapped: {field.db_object}")
                            elif field.questionnaire:
                                st.info("In Questionnaire")
                            else:
                                st.warning("Not Mapped")
                        
                        with col3:
                            if not field.mapped and not field.questionnaire:
                                c1, c2 = st.columns(2)
                                with c1:
                                    if st.button("Map", key=f"map_{part_num}_{field.id}"):
                                        st.session_state[f"show_map_{field.id}"] = True
                                        st.rerun()
                                with c2:
                                    if st.button("Q", key=f"q_{part_num}_{field.id}"):
                                        field.questionnaire = True
                                        st.rerun()
                            elif field.mapped:
                                if st.button("Unmap", key=f"unmap_{part_num}_{field.id}"):
                                    field.mapped = False
                                    field.db_object = ""
                                    field.db_path = ""
                                    st.rerun()
                        
                        # Mapping interface
                        if st.session_state.get(f"show_map_{field.id}"):
                            st.markdown("---")
                            c1, c2 = st.columns(2)
                            
                            with c1:
                                obj = st.selectbox(
                                    "Database Object",
                                    list(DB_SCHEMA.keys()),
                                    format_func=lambda x: DB_SCHEMA[x]["name"],
                                    key=f"obj_{field.id}"
                                )
                            
                            with c2:
                                if obj:
                                    path = st.selectbox(
                                        "Field Path",
                                        DB_SCHEMA[obj]["paths"],
                                        key=f"path_{field.id}"
                                    )
                            
                            c1, c2 = st.columns(2)
                            with c1:
                                if st.button("✅ Apply", key=f"apply_{field.id}"):
                                    field.mapped = True
                                    field.db_object = obj
                                    field.db_path = path
                                    del st.session_state[f"show_map_{field.id}"]
                                    st.rerun()
                            with c2:
                                if st.button("Cancel", key=f"cancel_{field.id}"):
                                    del st.session_state[f"show_map_{field.id}"]
                                    st.rerun()
                            st.markdown("---")
        else:
            st.info("Load a form first (Upload tab or 'Load Sample Form' button)")
    
    with tab3:
        st.markdown("### Questionnaire Fields")
        
        if st.session_state.form:
            q_fields = []
            for part in st.session_state.form.parts.values():
                q_fields.extend([f for f in part.fields if f.questionnaire])
            
            if q_fields:
                for field in q_fields:
                    st.markdown(f"**{field.id}. {field.label}**")
                    field.value = st.text_area(
                        "Answer",
                        value=field.value,
                        key=f"qa_{field.id}"
                    )
                    if st.button("Remove", key=f"qr_{field.id}"):
                        field.questionnaire = False
                        st.rerun()
                    st.markdown("---")
            else:
                st.info("No questionnaire fields. Use 'Q' button to add.")
        else:
            st.info("Load a form first")
    
    with tab4:
        st.markdown("### Export Data")
        
        if st.session_state.form:
            form = st.session_state.form
            
            # Prepare export
            export = {
                "form": {
                    "number": form.number,
                    "title": form.title
                },
                "fields": []
            }
            
            for part in form.parts.values():
                for field in part.fields:
                    field_data = {
                        "id": field.id,
                        "label": field.label,
                        "value": field.value,
                        "part": part.number
                    }
                    if field.mapped:
                        field_data["mapping"] = f"{field.db_object}.{field.db_path}"
                    export["fields"].append(field_data)
            
            # Stats
            total = len(export["fields"])
            mapped = sum(1 for f in export["fields"] if "mapping" in f)
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Fields", total)
            with col2:
                st.metric("Mapped", mapped)
            
            # Download
            json_str = json.dumps(export, indent=2)
            st.download_button(
                "📥 Download JSON",
                json_str,
                "export.json",
                "application/json"
            )
            
            # Preview
            with st.expander("Preview"):
                st.json(export)
        else:
            st.info("No data to export")

if __name__ == "__main__":
    main()
