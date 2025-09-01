#!/usr/bin/env python3
"""
UNIVERSAL USCIS FORM READER - ZERO HARDCODING
==============================================
Works with ANY USCIS form - no hardcoded patterns
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
        transition: all 0.2s ease;
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
    .field-repeating {
        border-left: 4px solid #00bcd4;
        background: #e0f7fa;
    }
    .stats-box {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# ===== DATA STRUCTURES =====

@dataclass
class FormField:
    """Universal field structure - no assumptions about form type"""
    item_number: str
    label: str
    field_type: str = "text"
    value: str = ""
    part_number: int = 1
    page_number: int = 1
    parent_item: str = ""
    is_subfield: bool = False
    is_repeating: bool = False
    repeat_pattern: str = ""  # Pattern detected (e.g., every 7 fields)
    repeat_index: int = 0
    is_mapped: bool = False
    in_questionnaire: bool = False
    db_object: str = ""
    db_path: str = ""
    unique_id: str = ""
    
    def __post_init__(self):
        if not self.unique_id:
            self.unique_id = str(uuid.uuid4())[:8]

@dataclass
class FormPart:
    """Generic part structure"""
    number: int
    title: str
    fields: List[FormField] = field(default_factory=list)
    page_start: int = 1
    page_end: int = 1

@dataclass
class USCISForm:
    """Universal form container"""
    form_number: str = "Unknown"
    form_title: str = "USCIS Form"
    edition_date: str = ""
    total_pages: int = 0
    parts: Dict[int, FormPart] = field(default_factory=dict)
    raw_text: str = ""
    detected_patterns: List[str] = field(default_factory=list)

# ===== GENERIC DATABASE SCHEMA =====

DATABASE_SCHEMA = {
    "applicant": {
        "label": "👤 Applicant/Beneficiary",
        "common_patterns": ["name", "birth", "address", "contact"],
        "paths": []  # Will be dynamically generated
    },
    "dependent": {
        "label": "👥 Dependent/Family",
        "common_patterns": ["dependent", "spouse", "child", "family"],
        "paths": []
    },
    "employer": {
        "label": "🏢 Employer/Organization",
        "common_patterns": ["company", "organization", "employer"],
        "paths": []
    },
    "attorney": {
        "label": "⚖️ Attorney/Representative",
        "common_patterns": ["attorney", "representative", "preparer"],
        "paths": []
    },
    "application": {
        "label": "📋 Application Details",
        "common_patterns": ["application", "petition", "request"],
        "paths": []
    },
    "custom": {
        "label": "✏️ Custom Mapping",
        "common_patterns": [],
        "paths": []
    }
}

# ===== PDF EXTRACTION =====

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

# ===== INTELLIGENT PATTERN DETECTOR =====

class PatternDetector:
    """Detects patterns in forms without hardcoding"""
    
    @staticmethod
    def detect_repeating_patterns(fields: List[FormField]) -> Dict[str, Any]:
        """Detect repeating field patterns dynamically"""
        patterns = {
            "repeating_groups": [],
            "field_sequences": []
        }
        
        # Look for repeating label patterns
        label_sequences = {}
        for i, field in enumerate(fields):
            # Clean label for pattern matching
            clean_label = re.sub(r'\d+', 'N', field.label.lower())
            
            if clean_label not in label_sequences:
                label_sequences[clean_label] = []
            label_sequences[clean_label].append(i)
        
        # Find sequences that repeat
        for label, positions in label_sequences.items():
            if len(positions) > 1:
                # Check if positions follow a pattern
                if len(positions) >= 2:
                    intervals = [positions[i+1] - positions[i] for i in range(len(positions)-1)]
                    
                    # If intervals are consistent, we have a pattern
                    if intervals and all(abs(i - intervals[0]) <= 2 for i in intervals):
                        patterns["repeating_groups"].append({
                            "label_pattern": label,
                            "positions": positions,
                            "interval": intervals[0] if intervals else 0
                        })
        
        return patterns
    
    @staticmethod
    def detect_field_types(label: str, text_context: str = "") -> str:
        """Intelligently detect field type from label and context"""
        label_lower = label.lower()
        
        # Date patterns
        if any(word in label_lower for word in ["date", "dob", "birth", "expir", "issued"]):
            return "date"
        
        # Checkbox patterns
        if any(word in label_lower for word in ["check", "select", "mark", "yes/no", "indicate"]):
            return "checkbox"
        
        # Number patterns
        if any(word in label_lower for word in ["number", "ssn", "ein", "a-number", "receipt"]):
            return "number"
        
        # Email patterns
        if any(word in label_lower for word in ["email", "e-mail"]):
            return "email"
        
        # Phone patterns
        if any(word in label_lower for word in ["phone", "telephone", "mobile", "cell"]):
            return "phone"
        
        # Address patterns
        if any(word in label_lower for word in ["address", "street", "city", "state", "zip"]):
            return "address"
        
        return "text"
    
    @staticmethod
    def detect_subfields(fields: List[Dict]) -> List[Dict]:
        """Detect parent-child relationships in fields"""
        enhanced_fields = []
        current_parent = None
        
        for field in fields:
            item_num = field.get("item_number", "")
            
            # Pattern: N.a, N.b, N.c are subfields of N
            if re.match(r'^\d+\.[a-z]$', item_num):
                parent_num = item_num.split('.')[0]
                field["parent_item"] = parent_num
                field["is_subfield"] = True
            
            # Pattern: N-N (range) or N.N.N (nested)
            elif '.' in item_num and len(item_num.split('.')) > 2:
                parts = item_num.split('.')
                field["parent_item"] = '.'.join(parts[:-1])
                field["is_subfield"] = True
            
            enhanced_fields.append(field)
        
        return enhanced_fields

# ===== UNIVERSAL FORM EXTRACTOR =====

class UniversalFormExtractor:
    """Extracts ANY USCIS form without hardcoding"""
    
    def __init__(self):
        self.setup_openai()
        self.pattern_detector = PatternDetector()
    
    def setup_openai(self):
        """Setup OpenAI client"""
        api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        
        if api_key:
            self.client = openai.OpenAI(api_key=api_key)
        else:
            self.client = None
            st.warning("Add OPENAI_API_KEY to secrets")
    
    def extract_form(self, full_text: str, page_texts: Dict[int, str], total_pages: int) -> USCISForm:
        """Extract any form dynamically"""
        
        # Identify form
        form_info = self._identify_form(full_text[:3000])
        
        form = USCISForm(
            form_number=form_info.get("form_number", "Unknown"),
            form_title=form_info.get("form_title", "USCIS Form"),
            edition_date=form_info.get("edition_date", ""),
            total_pages=total_pages,
            raw_text=full_text
        )
        
        # Extract parts dynamically
        parts_data = self._extract_parts(full_text)
        
        # Extract fields for each part
        for part_data in parts_data:
            part = FormPart(
                number=part_data["number"],
                title=part_data["title"],
                page_start=part_data.get("page_start", 1),
                page_end=part_data.get("page_end", 1)
            )
            
            # Extract fields without any assumptions
            fields_data = self._extract_fields_generic(full_text, part_data)
            
            # Enhance with pattern detection
            enhanced_fields = self.pattern_detector.detect_subfields(fields_data)
            
            # Convert to FormField objects
            fields = []
            for field_data in enhanced_fields:
                field = FormField(
                    item_number=field_data.get("item_number", ""),
                    label=field_data.get("label", ""),
                    field_type=self.pattern_detector.detect_field_types(
                        field_data.get("label", "")
                    ),
                    part_number=part.number,
                    parent_item=field_data.get("parent_item", ""),
                    is_subfield=field_data.get("is_subfield", False)
                )
                fields.append(field)
            
            # Detect repeating patterns
            patterns = self.pattern_detector.detect_repeating_patterns(fields)
            if patterns["repeating_groups"]:
                form.detected_patterns.append(f"Part {part.number}: Repeating patterns detected")
                
                # Mark repeating fields
                for pattern in patterns["repeating_groups"]:
                    for pos in pattern["positions"]:
                        if pos < len(fields):
                            fields[pos].is_repeating = True
                            fields[pos].repeat_pattern = pattern["label_pattern"]
                            fields[pos].repeat_index = pattern["positions"].index(pos) + 1
            
            part.fields = fields
            form.parts[part.number] = part
        
        # Generate dynamic database paths based on detected fields
        self._generate_dynamic_paths(form)
        
        return form
    
    def _identify_form(self, text: str) -> Dict:
        """Identify form without assumptions"""
        
        if not self.client:
            # Fallback pattern matching
            form_match = re.search(r'Form\s+([A-Z]-?\d+[A-Z]?)', text)
            form_number = form_match.group(1) if form_match else "Unknown"
            
            return {
                "form_number": form_number,
                "form_title": "USCIS Form",
                "edition_date": ""
            }
        
        prompt = """
        Identify the form number, title, and edition date from this text.
        
        Return ONLY JSON:
        {
            "form_number": "form number here",
            "form_title": "full form title",
            "edition_date": "edition date if found"
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
            return {"form_number": "Unknown", "form_title": "USCIS Form", "edition_date": ""}
    
    def _extract_parts(self, text: str) -> List[Dict]:
        """Extract parts without knowing form structure"""
        
        if not self.client:
            # Fallback to regex pattern matching
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
        
        prompt = """
        Extract ALL parts/sections from this form.
        
        Return ONLY a JSON array of parts:
        [
            {
                "number": 1,
                "title": "part title here",
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
                max_tokens=1500
            )
            
            content = response.choices[0].message.content.strip()
            if "```" in content:
                content = content.split("```")[1].replace("json", "").strip()
            
            parts = json.loads(content)
            return parts if parts else [{"number": 1, "title": "Main Section", "page_start": 1, "page_end": 1}]
            
        except Exception as e:
            st.error(f"Parts extraction error: {e}")
            return [{"number": 1, "title": "Main Section", "page_start": 1, "page_end": 1}]
    
    def _extract_fields_generic(self, text: str, part_data: Dict) -> List[Dict]:
        """Extract fields without any form-specific knowledge"""
        
        part_num = part_data["number"]
        part_title = part_data["title"]
        
        if not self.client:
            # Fallback to pattern matching
            fields = []
            
            # Look for numbered items
            field_matches = re.finditer(r'(\d+\.?[a-z]?\.?)\s+([^\n]+)', text[:5000])
            
            for match in field_matches:
                fields.append({
                    "item_number": match.group(1),
                    "label": match.group(2).strip()[:100]  # Limit label length
                })
            
            return fields[:50]  # Limit to 50 fields for performance
        
        prompt = f"""
        Extract ALL fields from Part {part_num}: {part_title}.
        
        Look for ANY numbered or lettered items, questions, or input fields.
        Include everything that looks like a form field.
        
        Return ONLY a JSON array:
        [
            {{
                "item_number": "field number here",
                "label": "field label here"
            }}
        ]
        
        Text: """ + text[:15000]
        
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
            
            fields = json.loads(content)
            return fields if fields else []
            
        except Exception as e:
            st.error(f"Field extraction error: {e}")
            return []
    
    def _generate_dynamic_paths(self, form: USCISForm):
        """Generate database paths based on detected fields"""
        
        # Analyze all fields to suggest paths
        all_labels = []
        for part in form.parts.values():
            for field in part.fields:
                all_labels.append(field.label.lower())
        
        # Generate paths for each database object based on field labels
        for obj_key, obj_data in DATABASE_SCHEMA.items():
            if obj_key == "custom":
                continue
            
            paths = []
            
            # Generate paths based on common patterns
            for pattern in obj_data["common_patterns"]:
                for label in all_labels:
                    if pattern in label:
                        # Create a suggested path
                        clean_label = re.sub(r'[^\w\s]', '', label)
                        clean_label = clean_label.replace(' ', '_')[:30]
                        if clean_label and clean_label not in paths:
                            paths.append(clean_label)
            
            # Add some generic paths
            if obj_key == "applicant":
                paths.extend(["name", "address", "phone", "email", "date_of_birth"])
            elif obj_key == "dependent":
                paths.extend(["dependent_name", "relationship", "date_of_birth"])
            
            obj_data["paths"] = paths[:20]  # Limit to 20 paths

# ===== UI COMPONENTS =====

def display_field(field: FormField, key_prefix: str):
    """Display field with mapping interface"""
    
    unique_key = f"{key_prefix}_{field.unique_id}"
    
    # Determine style
    if field.is_repeating:
        card_class = "field-repeating"
        status = f"🔁 Repeating"
    elif field.in_questionnaire:
        card_class = "field-questionnaire"
        status = "📝 Quest"
    elif field.is_mapped:
        card_class = "field-mapped"
        status = f"✅ Mapped"
    else:
        card_class = "field-unmapped"
        status = "❓ Unmapped"
    
    st.markdown(f'<div class="field-card {card_class}">', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([3, 2, 2])
    
    with col1:
        if field.is_subfield:
            st.markdown(f"↳ **{field.item_number}. {field.label}**")
            st.caption(f"Subfield of {field.parent_item}")
        else:
            st.markdown(f"**{field.item_number}. {field.label}**")
        
        if field.is_repeating:
            st.caption(f"Pattern: {field.repeat_pattern} | Instance #{field.repeat_index}")
    
    with col2:
        # Value input
        if field.field_type == "date":
            date_val = st.date_input("", key=f"{unique_key}_date", label_visibility="collapsed")
            field.value = str(date_val) if date_val else ""
        elif field.field_type == "checkbox":
            field.value = st.selectbox("", ["", "Yes", "No"], key=f"{unique_key}_check", label_visibility="collapsed")
        else:
            field.value = st.text_input("", value=field.value, key=f"{unique_key}_val", label_visibility="collapsed")
    
    with col3:
        st.markdown(f"**{status}**")
        
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
    
    # Mapping interface
    if st.session_state.get(f"mapping_{field.unique_id}"):
        show_mapping(field, unique_key)

def show_mapping(field: FormField, unique_key: str):
    """Mapping interface"""
    
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        # Suggest best database object based on field label
        suggested_obj = suggest_database_object(field.label)
        
        db_options = list(DATABASE_SCHEMA.keys())
        db_labels = [DATABASE_SCHEMA[k]["label"] for k in db_options]
        
        default_idx = db_options.index(suggested_obj) if suggested_obj in db_options else 0
        
        selected_idx = st.selectbox(
            "Database Object",
            range(len(db_options)),
            format_func=lambda x: db_labels[x],
            key=f"{unique_key}_dbobj",
            index=default_idx
        )
        
        selected_obj = db_options[selected_idx] if selected_idx is not None else None
    
    with col2:
        if selected_obj:
            if selected_obj == "custom":
                path = st.text_input("Custom path", key=f"{unique_key}_custom")
            else:
                paths = DATABASE_SCHEMA[selected_obj]["paths"]
                if not paths:
                    paths = ["field1", "field2", "custom"]
                
                path = st.selectbox("Path", [""] + paths + ["[custom]"], key=f"{unique_key}_path")
                
                if path == "[custom]":
                    path = st.text_input("Enter path", key=f"{unique_key}_custpath")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Apply", key=f"{unique_key}_apply", type="primary"):
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
    
    st.markdown("---")

def suggest_database_object(label: str) -> str:
    """Suggest database object based on label"""
    label_lower = label.lower()
    
    if any(word in label_lower for word in ["dependent", "spouse", "child", "family"]):
        return "dependent"
    elif any(word in label_lower for word in ["company", "employer", "organization"]):
        return "employer"
    elif any(word in label_lower for word in ["attorney", "representative", "preparer"]):
        return "attorney"
    elif any(word in label_lower for word in ["application", "petition", "request", "receipt"]):
        return "application"
    else:
        return "applicant"

# ===== MAIN APPLICATION =====

def main():
    st.markdown('<div class="main-header">', unsafe_allow_html=True)
    st.title("📄 Universal USCIS Form Reader")
    st.markdown("Works with ANY USCIS form - No hardcoding, fully dynamic")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Initialize
    if 'form' not in st.session_state:
        st.session_state.form = None
    if 'extractor' not in st.session_state:
        st.session_state.extractor = UniversalFormExtractor()
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 📊 Dynamic Database Schema")
        st.info("Schema adapts to your form automatically")
        
        for key, info in DATABASE_SCHEMA.items():
            with st.expander(info["label"]):
                if key == "custom":
                    st.info("Enter any custom path")
                else:
                    paths = info.get("paths", [])
                    if paths:
                        for path in paths[:5]:
                            st.code(path)
                        if len(paths) > 5:
                            st.caption(f"... +{len(paths)-5} more")
                    else:
                        st.info("Paths will be generated after extraction")
        
        st.markdown("---")
        
        if st.button("🔄 Clear All", type="secondary", use_container_width=True):
            st.session_state.form = None
            for key in list(st.session_state.keys()):
                if key.startswith("mapping_"):
                    del st.session_state[key]
            st.rerun()
        
        if st.session_state.form:
            st.markdown("## 📈 Form Statistics")
            form = st.session_state.form
            
            st.markdown('<div class="stats-box">', unsafe_allow_html=True)
            st.metric("Form", form.form_number)
            st.metric("Pages", form.total_pages)
            st.metric("Parts", len(form.parts))
            
            total_fields = sum(len(p.fields) for p in form.parts.values())
            st.metric("Total Fields", total_fields)
            
            if form.detected_patterns:
                st.markdown("**Detected Patterns:**")
                for pattern in form.detected_patterns:
                    st.caption(f"• {pattern}")
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    # Main tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📤 Upload", "🔗 Map", "📝 Questionnaire", "💾 Export"])
    
    with tab1:
        st.markdown("### Upload ANY USCIS Form")
        st.info("This reader automatically adapts to any USCIS form structure")
        
        uploaded_file = st.file_uploader("Choose PDF", type=['pdf'])
        
        if uploaded_file:
            if st.button("🚀 Extract Form", type="primary", use_container_width=True):
                with st.spinner("Analyzing form structure..."):
                    # Extract PDF
                    full_text, page_texts, total_pages = extract_pdf_text(uploaded_file)
                    
                    if full_text:
                        # Extract form dynamically
                        form = st.session_state.extractor.extract_form(
                            full_text, page_texts, total_pages
                        )
                        
                        st.session_state.form = form
                        
                        # Show results
                        st.success(f"✅ Extracted: {form.form_number}")
                        
                        # Show what was found
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Parts Found", len(form.parts))
                        with col2:
                            total_fields = sum(len(p.fields) for p in form.parts.values())
                            st.metric("Fields Found", total_fields)
                        with col3:
                            repeating = sum(1 for p in form.parts.values() for f in p.fields if f.is_repeating)
                            st.metric("Repeating Fields", repeating)
                        
                        if form.detected_patterns:
                            st.info(f"🔍 Detected patterns: {', '.join(form.detected_patterns)}")
                    else:
                        st.error("Could not extract text from PDF")
    
    with tab2:
        st.markdown("### Map Fields to Database")
        
        if st.session_state.form:
            form = st.session_state.form
            
            for part_num, part in form.parts.items():
                with st.expander(f"Part {part_num}: {part.title}", expanded=(part_num == 1)):
                    
                    # Stats
                    mapped = sum(1 for f in part.fields if f.is_mapped)
                    quest = sum(1 for f in part.fields if f.in_questionnaire)
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Fields", len(part.fields))
                    with col2:
                        st.metric("Mapped", mapped)
                    with col3:
                        st.metric("Questionnaire", quest)
                    
                    st.markdown("---")
                    
                    # Display fields
                    for field in part.fields:
                        display_field(field, f"p{part_num}")
        else:
            st.info("Upload a form first")
    
    with tab3:
        st.markdown("### Questionnaire Fields")
        
        if st.session_state.form:
            quest_fields = []
            for part in st.session_state.form.parts.values():
                quest_fields.extend([f for f in part.fields if f.in_questionnaire])
            
            if quest_fields:
                for field in quest_fields:
                    st.markdown(f"**{field.item_number}. {field.label}**")
                    field.value = st.text_area("", value=field.value, key=f"q_{field.unique_id}", height=100)
                    
                    if st.button("Remove", key=f"qr_{field.unique_id}"):
                        field.in_questionnaire = False
                        st.rerun()
                    
                    st.markdown("---")
            else:
                st.info("No questionnaire fields")
        else:
            st.info("Upload a form first")
    
    with tab4:
        st.markdown("### Export Data")
        
        if st.session_state.form:
            form = st.session_state.form
            
            # Build export
            export_data = {
                "form_info": {
                    "form_number": form.form_number,
                    "form_title": form.form_title,
                    "edition_date": form.edition_date,
                    "total_pages": form.total_pages,
                    "detected_patterns": form.detected_patterns
                },
                "parts": [],
                "all_fields": []
            }
            
            for part in form.parts.values():
                part_data = {
                    "number": part.number,
                    "title": part.title,
                    "fields": []
                }
                
                for field in part.fields:
                    field_data = {
                        "item_number": field.item_number,
                        "label": field.label,
                        "value": field.value,
                        "type": field.field_type,
                        "is_repeating": field.is_repeating
                    }
                    
                    if field.is_mapped:
                        field_data["mapping"] = f"{field.db_object}.{field.db_path}"
                    
                    part_data["fields"].append(field_data)
                    export_data["all_fields"].append(field_data)
                
                export_data["parts"].append(part_data)
            
            # Download
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
