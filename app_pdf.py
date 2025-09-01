#!/usr/bin/env python3
"""
UNIVERSAL USCIS FORM READER - ENHANCED VERSION
===============================================
Extracts fields with options, maps to TypeScript, exports questionnaires
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
    page_title="Universal USCIS Form Reader",
    page_icon="📄",
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
        text-align: center;
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
    .field-subfield {
        margin-left: 30px;
        border-left: 3px dashed #9e9e9e;
        padding-left: 15px;
    }
    .parent-field {
        background: #f5f5f5;
        font-weight: bold;
    }
    .field-number-badge {
        background: #673ab7;
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: bold;
        display: inline-block;
        margin-right: 8px;
    }
    .option-chip {
        display: inline-block;
        padding: 4px 8px;
        margin: 2px;
        background: #e3f2fd;
        border: 1px solid #2196f3;
        border-radius: 16px;
        font-size: 0.9em;
    }
</style>
""", unsafe_allow_html=True)

# ===== DATA STRUCTURES =====

@dataclass
class FormField:
    """Field structure with options support"""
    item_number: str
    label: str
    field_type: str = "text"
    value: str = ""
    part_number: int = 1
    page_number: int = 1
    parent_number: str = ""
    is_parent: bool = False
    is_subfield: bool = False
    subfield_labels: List[str] = field(default_factory=list)
    is_mapped: bool = False
    in_questionnaire: bool = False
    db_object: str = ""
    db_path: str = ""
    unique_id: str = ""
    options: List[str] = field(default_factory=list)
    has_options: bool = False
    
    def __post_init__(self):
        if not self.unique_id:
            self.unique_id = str(uuid.uuid4())[:8]
        if self.options:
            self.has_options = True

@dataclass
class FormPart:
    """Part structure"""
    number: int
    title: str
    fields: List[FormField] = field(default_factory=list)
    page_start: int = 1
    page_end: int = 1

@dataclass
class USCISForm:
    """Form container"""
    form_number: str = "Unknown"
    form_title: str = "USCIS Form"
    edition_date: str = ""
    total_pages: int = 0
    parts: Dict[int, FormPart] = field(default_factory=dict)
    raw_text: str = ""

# ===== DATABASE SCHEMA =====

DATABASE_SCHEMA = {
    "beneficiary": {
        "label": "👤 Beneficiary Information",
        "paths": [
            "beneficiaryLastName", "beneficiaryFirstName", "beneficiaryMiddleName",
            "beneficiaryDateOfBirth", "beneficiarySsn", "alienNumber",
            "beneficiaryCountryOfBirth", "beneficiaryCitizenOfCountry",
            "beneficiaryCellNumber", "beneficiaryEmailAddress",
            "homeAddress.street", "homeAddress.city", "homeAddress.state", "homeAddress.zip"
        ]
    },
    "petitioner": {
        "label": "🏢 Petitioner Information",
        "paths": [
            "petitionerName", "companyName", "companyTaxId",
            "signatoryFirstName", "signatoryLastName", "signatoryEmailAddress",
            "companyAddress.street", "companyAddress.city", "companyAddress.state"
        ]
    },
    "attorney": {
        "label": "⚖️ Attorney Information",
        "paths": [
            "attorneyLastName", "attorneyFirstName", "attorneyBarNumber",
            "attorneyEmailAddress", "lawFirmName"
        ]
    },
    "custom": {
        "label": "✏️ Custom Fields",
        "paths": []
    }
}

# ===== HELPER FUNCTIONS =====

def extract_field_options(label: str) -> List[str]:
    """Extract options for checkbox/select fields"""
    label_lower = label.lower()
    
    if any(word in label_lower for word in ["yes/no", "yes or no", "are you", "do you"]):
        return ["Yes", "No"]
    if "gender" in label_lower:
        return ["Male", "Female", "Other"]
    if "marital" in label_lower:
        return ["Single", "Married", "Divorced", "Widowed"]
    
    return []

def detect_field_type(label: str) -> Tuple[str, List[str]]:
    """Detect field type and options"""
    label_lower = label.lower()
    options = extract_field_options(label)
    
    if any(word in label_lower for word in ["check", "select", "yes/no"]):
        return ("checkbox" if options else "select"), options
    if any(word in label_lower for word in ["date", "birth", "expir"]):
        return "date", []
    if any(word in label_lower for word in ["email"]):
        return "email", []
    if any(word in label_lower for word in ["phone", "mobile"]):
        return "phone", []
    
    return "text", []

def detect_subfield_components(label: str) -> List[str]:
    """Detect if field should have subfields"""
    label_lower = label.lower()
    
    if "name" in label_lower and ("full" in label_lower or "legal" in label_lower):
        return ["Family Name", "Given Name", "Middle Name"]
    if "address" in label_lower and "foreign" not in label_lower:
        return ["Street", "Apt/Ste", "City", "State", "ZIP"]
    
    return []

def extract_pdf_text(pdf_file) -> Tuple[str, Dict[int, str], int]:
    """Extract text from PDF"""
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
        st.error(f"PDF error: {e}")
        return "", {}, 0

# ===== FORM EXTRACTOR =====

class UniversalFormExtractor:
    """Extract USCIS forms with subfields and options"""
    
    def __init__(self):
        self.setup_openai()
    
    def setup_openai(self):
        """Setup OpenAI client"""
        api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.client = openai.OpenAI(api_key=api_key) if api_key else None
        if not self.client:
            st.warning("Add OPENAI_API_KEY to secrets for better extraction")
    
    def extract_form(self, full_text: str, page_texts: Dict[int, str], total_pages: int) -> USCISForm:
        """Extract form structure"""
        form_info = self._identify_form(full_text[:3000])
        
        form = USCISForm(
            form_number=form_info.get("form_number", "Unknown"),
            form_title=form_info.get("form_title", "USCIS Form"),
            edition_date=form_info.get("edition_date", ""),
            total_pages=total_pages,
            raw_text=full_text
        )
        
        parts_data = self._extract_parts(full_text)
        
        for part_data in parts_data:
            part = FormPart(
                number=part_data["number"],
                title=part_data["title"],
                page_start=part_data.get("page_start", 1),
                page_end=part_data.get("page_end", 1)
            )
            part.fields = self._extract_and_split_fields(full_text, part_data)
            form.parts[part.number] = part
        
        return form
    
    def _identify_form(self, text: str) -> Dict:
        """Identify form type"""
        form_match = re.search(r'Form\s+([A-Z]-?\d+[A-Z]?)', text)
        form_number = form_match.group(1) if form_match else "Unknown"
        
        if not self.client:
            return {"form_number": form_number, "form_title": "USCIS Form", "edition_date": ""}
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": f"Extract form number, title, and edition date from:\n{text}\n\nReturn JSON only."}],
                temperature=0,
                max_tokens=200
            )
            content = response.choices[0].message.content.strip()
            if "```" in content:
                content = content.split("```")[1].replace("json", "").strip()
            return json.loads(content)
        except:
            return {"form_number": form_number, "form_title": "USCIS Form", "edition_date": ""}
    
    def _extract_parts(self, text: str) -> List[Dict]:
        """Extract parts from form"""
        parts = []
        part_matches = re.finditer(r'Part\s+(\d+)[.\s]+([^\n]+)', text)
        
        for match in part_matches:
            parts.append({
                "number": int(match.group(1)),
                "title": match.group(2).strip(),
                "page_start": 1,
                "page_end": 1
            })
        
        return parts if parts else [{"number": 1, "title": "Main Section", "page_start": 1, "page_end": 1}]
    
    def _extract_and_split_fields(self, text: str, part_data: Dict) -> List[FormField]:
        """Extract fields with subfield detection"""
        part_num = part_data["number"]
        raw_fields = self._extract_raw_fields(text[:5000])
        
        # Track existing subfields
        existing_subfields = set()
        for field_data in raw_fields:
            item_num = field_data.get("item_number", "")
            if '.' in item_num and len(item_num.split('.')[1]) == 1:
                existing_subfields.add(item_num)
        
        processed_fields = []
        processed_numbers = set()
        
        for field_data in raw_fields:
            item_number = field_data.get("item_number", "")
            label = field_data.get("label", "")
            
            if item_number in processed_numbers:
                continue
            processed_numbers.add(item_number)
            
            field_type, options = detect_field_type(label)
            
            # Check if already a subfield
            is_subfield = '.' in item_number and len(item_number.split('.')[1]) == 1
            
            if is_subfield:
                parent_num = item_number.split('.')[0]
                field = FormField(
                    item_number=item_number,
                    label=label,
                    field_type=field_type,
                    part_number=part_num,
                    parent_number=parent_num,
                    is_subfield=True,
                    options=options
                )
                processed_fields.append(field)
            else:
                subfield_components = detect_subfield_components(label)
                has_existing = any(f"{item_number}.{l}" in existing_subfields for l in ['a','b','c'])
                
                if subfield_components and not has_existing:
                    # Create parent and subfields
                    parent_field = FormField(
                        item_number=item_number,
                        label=label,
                        field_type="parent",
                        part_number=part_num,
                        is_parent=True,
                        subfield_labels=subfield_components
                    )
                    processed_fields.append(parent_field)
                    
                    for i, component in enumerate(subfield_components[:5]):
                        letter = chr(ord('a') + i)
                        subfield_type, sub_options = detect_field_type(component)
                        subfield = FormField(
                            item_number=f"{item_number}.{letter}",
                            label=component,
                            field_type=subfield_type,
                            part_number=part_num,
                            parent_number=item_number,
                            is_subfield=True,
                            options=sub_options
                        )
                        processed_fields.append(subfield)
                        processed_numbers.add(f"{item_number}.{letter}")
                elif has_existing:
                    # Parent with existing subfields
                    parent_field = FormField(
                        item_number=item_number,
                        label=label,
                        field_type="parent",
                        part_number=part_num,
                        is_parent=True
                    )
                    processed_fields.append(parent_field)
                else:
                    # Regular field
                    field = FormField(
                        item_number=item_number,
                        label=label,
                        field_type=field_type,
                        part_number=part_num,
                        options=options
                    )
                    processed_fields.append(field)
        
        return processed_fields
    
    def _extract_raw_fields(self, text: str) -> List[Dict]:
        """Extract raw fields from text"""
        fields = []
        # Simple regex extraction
        pattern = r'(\d+\.?[a-z]?\.?)\s+([^\n]{5,100})'
        matches = re.finditer(pattern, text)
        
        for match in matches[:50]:  # Limit to 50 fields
            fields.append({
                "item_number": match.group(1).rstrip('.'),
                "label": match.group(2).strip()
            })
        
        return fields

# ===== UI COMPONENTS =====

def display_field(field: FormField, key_prefix: str):
    """Display field with options"""
    unique_key = f"{key_prefix}_{field.unique_id}"
    
    # Determine style
    if field.is_parent:
        card_class = "parent-field"
        status = "📁 Parent"
    elif field.is_subfield:
        card_class = "field-subfield"
        status = f"↳ Sub"
    elif field.in_questionnaire:
        card_class = "field-questionnaire"
        status = "📝 Quest"
    elif field.is_mapped:
        card_class = "field-mapped"
        status = "✅ Mapped"
    else:
        card_class = "field-unmapped"
        status = "❓ Unmapped"
    
    st.markdown(f'<div class="field-card {card_class}">', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([3, 2, 2])
    
    with col1:
        st.markdown(f'<span class="field-number-badge">{field.item_number}</span>**{field.label}**', unsafe_allow_html=True)
        if field.has_options and field.options:
            options_html = ''.join([f'<span class="option-chip">{opt}</span>' for opt in field.options])
            st.markdown(options_html, unsafe_allow_html=True)
    
    with col2:
        if not field.is_parent:
            if field.field_type == "date":
                date_val = st.date_input("", key=f"{unique_key}_date", label_visibility="collapsed")
                field.value = str(date_val) if date_val else ""
            elif field.options:
                field.value = st.selectbox("", [""] + field.options, key=f"{unique_key}_sel", label_visibility="collapsed")
            else:
                field.value = st.text_input("", value=field.value, key=f"{unique_key}_val", label_visibility="collapsed")
    
    with col3:
        st.markdown(f"**{status}**")
        if not field.is_parent:
            c1, c2 = st.columns(2)
            with c1:
                if not field.is_mapped and not field.in_questionnaire:
                    if st.button("Map", key=f"{unique_key}_map"):
                        st.session_state[f"mapping_{field.unique_id}"] = True
                        st.rerun()
            with c2:
                if not field.is_mapped and not field.in_questionnaire:
                    if st.button("Quest", key=f"{unique_key}_quest"):
                        field.in_questionnaire = True
                        st.rerun()
                elif field.is_mapped or field.in_questionnaire:
                    if st.button("Clear", key=f"{unique_key}_clear"):
                        field.is_mapped = False
                        field.in_questionnaire = False
                        field.db_object = ""
                        field.db_path = ""
                        st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Mapping dialog
    if st.session_state.get(f"mapping_{field.unique_id}"):
        show_mapping(field, unique_key)

def show_mapping(field: FormField, unique_key: str):
    """Show mapping interface"""
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        db_options = list(DATABASE_SCHEMA.keys())
        selected_idx = st.selectbox(
            "Database Object",
            range(len(db_options)),
            format_func=lambda x: DATABASE_SCHEMA[db_options[x]]["label"],
            key=f"{unique_key}_dbobj"
        )
        selected_obj = db_options[selected_idx] if selected_idx is not None else None
    
    with col2:
        if selected_obj:
            paths = DATABASE_SCHEMA[selected_obj]["paths"]
            path = st.selectbox("Field Path", [""] + paths, key=f"{unique_key}_path")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Apply", key=f"{unique_key}_apply", type="primary"):
            if selected_obj and path:
                field.is_mapped = True
                field.db_object = selected_obj
                field.db_path = path
                del st.session_state[f"mapping_{field.unique_id}"]
                st.rerun()
    with col2:
        if st.button("Cancel", key=f"{unique_key}_cancel"):
            del st.session_state[f"mapping_{field.unique_id}"]
            st.rerun()

# ===== EXPORT FUNCTIONS =====

def generate_typescript(form: USCISForm) -> str:
    """Generate TypeScript interface"""
    ts = "// Generated TypeScript Interface\n\n"
    mapped_fields = {}
    
    for part in form.parts.values():
        for field in part.fields:
            if field.is_mapped and not field.is_parent:
                if field.db_object not in mapped_fields:
                    mapped_fields[field.db_object] = []
                mapped_fields[field.db_object].append(field)
    
    for obj_name, fields in mapped_fields.items():
        ts += f"interface {obj_name.capitalize()}Data {{\n"
        for field in fields:
            ts_type = "string"
            if field.field_type == "date":
                ts_type = "Date"
            elif field.options:
                ts_type = " | ".join([f'"{opt}"' for opt in field.options])
            ts += f"  {field.db_path.split('.')[-1]}: {ts_type}; // {field.item_number}\n"
        ts += "}\n\n"
    
    return ts

def generate_questionnaire_json(form: USCISForm) -> Dict:
    """Generate questionnaire JSON"""
    questionnaire = {"form": form.form_number, "parts": {}}
    
    for part in form.parts.values():
        questions = []
        for field in part.fields:
            if field.in_questionnaire and not field.is_parent:
                q = {
                    "number": field.item_number,
                    "question": field.label,
                    "answer": field.value,
                    "type": field.field_type
                }
                if field.options:
                    q["options"] = field.options
                questions.append(q)
        
        if questions:
            questionnaire["parts"][f"Part_{part.number}"] = questions
    
    return questionnaire

# ===== MAIN APP =====

def main():
    st.markdown('<div class="main-header"><h1>📄 Universal USCIS Form Reader</h1></div>', unsafe_allow_html=True)
    
    # Initialize
    if 'form' not in st.session_state:
        st.session_state.form = None
    if 'extractor' not in st.session_state:
        st.session_state.extractor = UniversalFormExtractor()
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 📊 Database Schema")
        for key, info in DATABASE_SCHEMA.items():
            with st.expander(info["label"]):
                for path in info["paths"][:5]:
                    st.code(path)
        
        if st.button("🔄 Clear All", type="secondary", use_container_width=True):
            st.session_state.clear()
            st.rerun()
    
    # Main tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📤 Upload", "🔗 Map", "📝 Questionnaire", "💾 Export"])
    
    with tab1:
        uploaded_file = st.file_uploader("Choose PDF", type=['pdf'])
        if uploaded_file and st.button("🚀 Extract", type="primary"):
            with st.spinner("Extracting..."):
                full_text, page_texts, total_pages = extract_pdf_text(uploaded_file)
                if full_text:
                    form = st.session_state.extractor.extract_form(full_text, page_texts, total_pages)
                    st.session_state.form = form
                    st.success(f"✅ Extracted {form.form_number}")
    
    with tab2:
        if st.session_state.form:
            form = st.session_state.form
            for part_num, part in form.parts.items():
                with st.expander(f"Part {part_num}: {part.title}"):
                    displayed = set()
                    for field in part.fields:
                        if field.item_number not in displayed:
                            if not field.is_subfield:
                                display_field(field, f"p{part_num}")
                                displayed.add(field.item_number)
                                if field.is_parent:
                                    for sub in part.fields:
                                        if sub.parent_number == field.item_number:
                                            display_field(sub, f"p{part_num}")
                                            displayed.add(sub.item_number)
        else:
            st.info("Upload a form first")
    
    with tab3:
        if st.session_state.form:
            for part in st.session_state.form.parts.values():
                quest_fields = [f for f in part.fields if f.in_questionnaire and not f.is_parent]
                if quest_fields:
                    st.markdown(f"#### Part {part.number}: {part.title}")
                    for field in quest_fields:
                        st.markdown(f'<span class="field-number-badge">{field.item_number}</span>**{field.label}**', unsafe_allow_html=True)
                        if field.options:
                            field.value = st.selectbox("Answer", [""] + field.options, key=f"q_{field.unique_id}")
                        else:
                            field.value = st.text_area("Answer", value=field.value, key=f"q_{field.unique_id}")
                        if st.button("Remove", key=f"qr_{field.unique_id}"):
                            field.in_questionnaire = False
                            st.rerun()
        else:
            st.info("No questionnaire fields")
    
    with tab4:
        if st.session_state.form:
            form = st.session_state.form
            
            # TypeScript export
            ts_code = generate_typescript(form)
            st.download_button(
                "📥 Download TypeScript",
                ts_code,
                f"{form.form_number}_interface.ts",
                "text/plain"
            )
            
            # Questionnaire JSON
            quest_json = generate_questionnaire_json(form)
            st.download_button(
                "📥 Download Questionnaire JSON",
                json.dumps(quest_json, indent=2),
                f"{form.form_number}_questionnaire.json",
                "application/json"
            )

if __name__ == "__main__":
    main()
