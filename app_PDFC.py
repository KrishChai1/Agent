#!/usr/bin/env python3
"""
UNIVERSAL USCIS FORM READER - CLAUDE OPUS 4.1 AGENTIC
=====================================================
Intelligent extraction using Claude Opus 4.1 with proper field hierarchy
"""

import streamlit as st
import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field as dataclass_field, asdict
import uuid
import base64
from anthropic import Anthropic

# Page configuration
st.set_page_config(
    page_title="USCIS Form Reader - Opus 4.1",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        padding: 2rem;
        border-radius: 15px;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .field-container {
        background: white;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        transition: all 0.3s ease;
    }
    .field-container:hover {
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    .field-main {
        border-left: 4px solid #1e3c72;
        font-weight: 600;
    }
    .field-subfield {
        border-left: 4px solid #5dade2;
        margin-left: 30px;
        background: #f8f9fa;
    }
    .field-choice {
        border-left: 4px solid #85c1e2;
        margin-left: 60px;
        background: #f0f8ff;
    }
    .field-mapped {
        background: #d4edda;
        border-left-color: #28a745;
    }
    .field-questionnaire {
        background: #fff3cd;
        border-left-color: #ffc107;
    }
    .field-number {
        display: inline-block;
        background: #1e3c72;
        color: white;
        padding: 3px 10px;
        border-radius: 5px;
        margin-right: 10px;
        font-weight: bold;
    }
    .status-badge {
        display: inline-block;
        padding: 3px 8px;
        border-radius: 12px;
        font-size: 0.85em;
        font-weight: 500;
    }
    .extraction-stats {
        background: #f8f9fa;
        padding: 15px;
        border-radius: 10px;
        margin: 15px 0;
    }
    .action-button {
        padding: 5px 12px;
        margin: 0 3px;
        border-radius: 5px;
        font-size: 0.9em;
    }
</style>
""", unsafe_allow_html=True)

# ===== DATA MODELS =====

@dataclass
class FieldChoice:
    """Choice/option for a field"""
    letter: str
    text: str
    selected: bool = False

@dataclass
class FormField:
    """Enhanced field structure"""
    number: str
    label: str
    field_type: str = "text"  # text, date, checkbox, radio, parent, etc
    value: Any = ""
    
    # Hierarchy
    part: int = 1
    parent_number: Optional[str] = None
    is_parent: bool = False
    choices: List[FieldChoice] = dataclass_field(default_factory=list)
    
    # Mapping
    is_mapped: bool = False
    db_object: str = ""
    db_path: str = ""
    
    # Questionnaire
    in_questionnaire: bool = False
    
    # Metadata
    page: int = 1
    context: str = ""
    confidence: float = 1.0
    unique_id: str = ""
    
    def __post_init__(self):
        if not self.unique_id:
            self.unique_id = str(uuid.uuid4())[:8]
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for export"""
        data = {
            "number": self.number,
            "label": self.label,
            "type": self.field_type,
            "value": self.value
        }
        
        if self.choices:
            data["choices"] = [
                {"letter": c.letter, "text": c.text, "selected": c.selected}
                for c in self.choices
            ]
        
        if self.is_mapped:
            data["mapping"] = {
                "object": self.db_object,
                "path": self.db_path
            }
        
        return data

@dataclass
class FormPart:
    """Part/section of form"""
    number: int
    title: str
    fields: List[FormField] = dataclass_field(default_factory=list)
    
    def get_hierarchy(self) -> Dict:
        """Get fields organized by hierarchy"""
        hierarchy = {}
        
        # First pass: identify all parent fields
        for field in self.fields:
            if field.is_parent or (not field.parent_number and not any(c.isalpha() for c in field.number.split('.')[-1])):
                hierarchy[field.number] = {
                    "field": field,
                    "children": []
                }
        
        # Second pass: assign children
        for field in self.fields:
            if field.parent_number and field.parent_number in hierarchy:
                hierarchy[field.parent_number]["children"].append(field)
        
        return hierarchy

# ===== DATABASE SCHEMA =====

DB_SCHEMA = {
    "beneficiary": {
        "label": "👤 Beneficiary Information",
        "fields": [
            "lastName", "firstName", "middleName", "otherNames",
            "alienNumber", "uscisNumber", "ssn", "dateOfBirth",
            "countryOfBirth", "cityOfBirth", "citizenship",
            "address.street", "address.apt", "address.city",
            "address.state", "address.zip", "address.country",
            "contact.phone", "contact.mobile", "contact.email"
        ]
    },
    "petitioner": {
        "label": "🏢 Petitioner Information",
        "fields": [
            "lastName", "firstName", "middleName", "companyName",
            "ein", "ssn", "address.street", "address.apt",
            "address.city", "address.state", "address.zip",
            "contact.phone", "contact.email"
        ]
    },
    "employment": {
        "label": "💼 Employment Information",
        "fields": [
            "jobTitle", "socCode", "naicsCode", "wages",
            "startDate", "endDate", "workLocation.address",
            "workLocation.city", "workLocation.state"
        ]
    },
    "education": {
        "label": "🎓 Education Information",
        "fields": [
            "degree", "field", "institution", "country",
            "dateCompleted", "equivalency"
        ]
    }
}

# ===== CLAUDE OPUS 4.1 AGENT =====

class OpusExtractionAgent:
    """Claude Opus 4.1 powered extraction agent"""
    
    def __init__(self):
        self.client = None
        self.model = "claude-opus-4-1-20250805"
        self.initialize_client()
    
    def initialize_client(self):
        """Initialize Anthropic client"""
        try:
            # Try to get API key from Streamlit secrets
            api_key = st.secrets.get("ANTHROPIC_API_KEY", None)
            
            if not api_key:
                st.error("""
                ⚠️ **Claude API Key Not Found**
                
                Please add your Anthropic API key to Streamlit secrets:
                1. Create `.streamlit/secrets.toml` locally
                2. Add: `ANTHROPIC_API_KEY = "your-key-here"`
                
                Or set in Streamlit Cloud settings.
                """)
                return
            
            self.client = Anthropic(api_key=api_key)
            st.success("✅ Claude Opus 4.1 initialized successfully")
            
        except Exception as e:
            st.error(f"Failed to initialize Claude: {str(e)}")
    
    def extract_form_structure(self, text: str, page_num: int = 1) -> Dict:
        """Extract complete form structure using Opus 4.1"""
        
        if not self.client:
            return self._fallback_extraction(text)
        
        prompt = """You are an expert USCIS form analyzer. Extract the COMPLETE structure from this form.

CRITICAL REQUIREMENTS:
1. Extract EVERY numbered field (1, 2, 3...)
2. Extract EVERY subfield (1.a., 1.b., 1.c...)
3. For questions with checkboxes/options, extract each option as a choice
4. Maintain exact numbering from the form
5. Identify field relationships (parent-child)

Return a JSON structure:
{
  "form_number": "I-129",
  "form_title": "...",
  "parts": [
    {
      "number": 1,
      "title": "Part Title",
      "fields": [
        {
          "number": "1",
          "label": "Full Legal Name",
          "type": "parent",
          "is_parent": true
        },
        {
          "number": "1.a",
          "label": "Family Name (Last Name)",
          "type": "text",
          "parent": "1"
        },
        {
          "number": "2",
          "label": "Have you ever...",
          "type": "question",
          "is_parent": true,
          "choices": [
            {"letter": "a", "text": "Yes"},
            {"letter": "b", "text": "No"}
          ]
        }
      ]
    }
  ]
}

Text to analyze:
""" + text[:15000]
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                temperature=0,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            # Parse response
            content = response.content[0].text
            
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return data
            
        except Exception as e:
            st.error(f"Opus extraction error: {str(e)}")
            return self._fallback_extraction(text)
        
        return self._fallback_extraction(text)
    
    def enhance_field_context(self, field: FormField, surrounding_text: str) -> FormField:
        """Enhance field with additional context"""
        
        if not self.client:
            return field
        
        prompt = f"""Analyze this form field and provide additional context:

Field Number: {field.number}
Field Label: {field.label}
Surrounding Text: {surrounding_text[:500]}

Determine:
1. The most appropriate field type (text, date, ssn, ein, checkbox, etc)
2. Any validation rules or format requirements
3. Whether this maps to a common USCIS data field

Return JSON:
{{
  "field_type": "...",
  "format": "optional format hint",
  "common_mapping": "optional suggestion like beneficiary.lastName"
}}"""
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=200,
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = response.content[0].text
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            
            if json_match:
                data = json.loads(json_match.group())
                field.field_type = data.get("field_type", field.field_type)
                
                # Auto-map if common field detected
                if data.get("common_mapping"):
                    parts = data["common_mapping"].split(".")
                    if parts[0] in DB_SCHEMA:
                        field.db_object = parts[0]
                        field.db_path = ".".join(parts[1:]) if len(parts) > 1 else ""
                        field.is_mapped = True
            
        except:
            pass
        
        return field
    
    def _fallback_extraction(self, text: str) -> Dict:
        """Fallback pattern-based extraction"""
        
        # Extract form number
        form_number = "Unknown"
        form_match = re.search(r'Form\s+([I]-\d+[A-Z]?)', text, re.IGNORECASE)
        if form_match:
            form_number = form_match.group(1)
        
        # Extract parts
        parts = []
        part_pattern = r'Part\s+(\d+)[.\s\-–]*([^\n]+)'
        part_matches = re.finditer(part_pattern, text, re.IGNORECASE)
        
        for match in part_matches:
            part_num = int(match.group(1))
            part_title = match.group(2).strip()
            
            # Extract fields for this part
            part_text = self._get_part_text(text, part_num)
            fields = self._extract_fields_from_text(part_text)
            
            parts.append({
                "number": part_num,
                "title": part_title,
                "fields": fields
            })
        
        if not parts:
            # No parts found, treat as single section
            fields = self._extract_fields_from_text(text)
            parts.append({
                "number": 1,
                "title": "Main Section",
                "fields": fields
            })
        
        return {
            "form_number": form_number,
            "form_title": f"USCIS Form {form_number}",
            "parts": parts
        }
    
    def _get_part_text(self, text: str, part_num: int) -> str:
        """Extract text for specific part"""
        pattern = f"Part\\s+{part_num}\\b"
        match = re.search(pattern, text, re.IGNORECASE)
        
        if not match:
            return ""
        
        start = match.start()
        
        # Find next part
        next_pattern = f"Part\\s+{part_num + 1}\\b"
        next_match = re.search(next_pattern, text[start:], re.IGNORECASE)
        
        if next_match:
            end = start + next_match.start()
        else:
            end = min(start + 20000, len(text))
        
        return text[start:end]
    
    def _extract_fields_from_text(self, text: str) -> List[Dict]:
        """Extract fields using patterns"""
        fields = []
        seen = set()
        
        # Pattern for main fields and subfields
        patterns = [
            (r'(\d+)\.([a-z])\.?\s+([^\n]+)', 'subfield'),
            (r'(\d+)\.\s+([^\n]+)', 'main'),
        ]
        
        for pattern, field_type in patterns:
            matches = re.finditer(pattern, text[:10000], re.MULTILINE)
            
            for match in matches:
                if field_type == 'subfield':
                    number = f"{match.group(1)}.{match.group(2)}"
                    label = match.group(3).strip()
                    parent = match.group(1)
                else:
                    number = match.group(1)
                    label = match.group(2).strip()
                    parent = None
                
                if number not in seen and len(label) > 2:
                    seen.add(number)
                    
                    # Check for checkboxes in context
                    context_start = max(0, match.start() - 50)
                    context_end = min(len(text), match.end() + 300)
                    context = text[context_start:context_end]
                    
                    choices = self._extract_choices(context)
                    
                    fields.append({
                        "number": number,
                        "label": label[:200],
                        "type": self._detect_field_type(label),
                        "parent": parent,
                        "is_parent": bool(choices or parent is None),
                        "choices": choices
                    })
        
        return fields
    
    def _extract_choices(self, context: str) -> List[Dict]:
        """Extract checkbox/radio choices"""
        choices = []
        
        # Look for checkbox patterns
        patterns = [
            r'[□☐]\s*([^\n□☐]{2,100})',
            r'\[\s*\]\s*([^\n\[\]]{2,100})'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, context)
            if matches and len(matches) > 1:
                for i, match in enumerate(matches[:5]):
                    choices.append({
                        "letter": chr(ord('a') + i),
                        "text": match.strip()
                    })
                break
        
        return choices
    
    def _detect_field_type(self, label: str) -> str:
        """Detect field type from label"""
        label_lower = label.lower()
        
        if any(word in label_lower for word in ["date", "born", "birth"]):
            return "date"
        elif "email" in label_lower:
            return "email"
        elif any(word in label_lower for word in ["phone", "telephone"]):
            return "phone"
        elif "ssn" in label_lower or "social security" in label_lower:
            return "ssn"
        elif "ein" in label_lower or "employer identification" in label_lower:
            return "ein"
        elif "alien number" in label_lower or "a-number" in label_lower:
            return "alien_number"
        elif any(word in label_lower for word in ["select", "check", "mark"]):
            return "checkbox"
        
        return "text"

# ===== PDF PROCESSING =====

def extract_pdf_text(pdf_file) -> Tuple[str, int]:
    """Extract text from uploaded PDF"""
    try:
        import PyPDF2
        
        pdf_file.seek(0)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        
        full_text = ""
        for page_num, page in enumerate(pdf_reader.pages):
            text = page.extract_text()
            full_text += f"\n\n=== PAGE {page_num + 1} ===\n{text}"
        
        return full_text, len(pdf_reader.pages)
        
    except ImportError:
        st.error("PyPDF2 not installed. Run: pip install PyPDF2")
        return "", 0
    except Exception as e:
        st.error(f"Error reading PDF: {str(e)}")
        return "", 0

# ===== UI COMPONENTS =====

def render_field(field: FormField, key_prefix: str):
    """Render a single field with all controls"""
    
    # Determine styling
    css_class = "field-container"
    if field.is_parent:
        css_class += " field-main"
    elif field.parent_number:
        if any(c.isalpha() for c in field.number.split('.')[-1]):
            css_class += " field-subfield"
    
    if field.is_mapped:
        css_class += " field-mapped"
    elif field.in_questionnaire:
        css_class += " field-questionnaire"
    
    # Render container
    with st.container():
        st.markdown(f'<div class="{css_class}">', unsafe_allow_html=True)
        
        col1, col2, col3, col4 = st.columns([3, 2, 1.5, 1.5])
        
        with col1:
            # Field number and label
            st.markdown(
                f'<span class="field-number">{field.number}</span>'
                f'<strong>{field.label}</strong>',
                unsafe_allow_html=True
            )
            
            # Show choices for questions
            if field.choices:
                for choice in field.choices:
                    choice_key = f"{key_prefix}_{field.unique_id}_{choice.letter}"
                    choice.selected = st.checkbox(
                        f"{choice.letter}. {choice.text}",
                        value=choice.selected,
                        key=choice_key
                    )
        
        with col2:
            if not field.is_parent and not field.choices:
                # Input field based on type
                input_key = f"{key_prefix}_{field.unique_id}_value"
                
                if field.field_type == "date":
                    field.value = st.date_input(
                        "Value",
                        key=input_key,
                        label_visibility="collapsed"
                    )
                elif field.field_type == "checkbox":
                    field.value = st.checkbox(
                        "Selected",
                        key=input_key
                    )
                else:
                    field.value = st.text_input(
                        "Value",
                        value=field.value or "",
                        key=input_key,
                        label_visibility="collapsed"
                    )
        
        with col3:
            # Mapping status/controls
            if field.is_mapped:
                st.success(f"→ {field.db_object}.{field.db_path}")
            else:
                if st.button("Map", key=f"{key_prefix}_{field.unique_id}_map"):
                    st.session_state[f"mapping_{field.unique_id}"] = True
        
        with col4:
            # Questionnaire toggle
            if st.button(
                "📝 Quest" if not field.in_questionnaire else "✓ Quest",
                key=f"{key_prefix}_{field.unique_id}_quest"
            ):
                field.in_questionnaire = not field.in_questionnaire
                st.rerun()
        
        # Mapping dialog
        if st.session_state.get(f"mapping_{field.unique_id}"):
            render_mapping_dialog(field, key_prefix)
        
        st.markdown('</div>', unsafe_allow_html=True)

def render_mapping_dialog(field: FormField, key_prefix: str):
    """Render mapping configuration dialog"""
    
    st.markdown("---")
    st.markdown("**🔗 Map Field to Database**")
    
    col1, col2 = st.columns(2)
    
    with col1:
        db_object = st.selectbox(
            "Object",
            [""] + list(DB_SCHEMA.keys()) + ["custom"],
            key=f"{key_prefix}_{field.unique_id}_map_obj"
        )
    
    with col2:
        if db_object and db_object != "custom":
            db_path = st.selectbox(
                "Field",
                [""] + DB_SCHEMA[db_object]["fields"],
                key=f"{key_prefix}_{field.unique_id}_map_path"
            )
        else:
            db_path = st.text_input(
                "Custom Path",
                key=f"{key_prefix}_{field.unique_id}_map_custom"
            )
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("✅ Apply", key=f"{key_prefix}_{field.unique_id}_map_apply"):
            if db_object and db_path:
                field.is_mapped = True
                field.db_object = db_object
                field.db_path = db_path
                del st.session_state[f"mapping_{field.unique_id}"]
                st.rerun()
    
    with col2:
        if st.button("❌ Cancel", key=f"{key_prefix}_{field.unique_id}_map_cancel"):
            del st.session_state[f"mapping_{field.unique_id}"]
            st.rerun()

def render_part_fields(part: FormPart):
    """Render all fields in a part with hierarchy"""
    
    hierarchy = part.get_hierarchy()
    
    # Render parent fields and their children
    for parent_num in sorted(hierarchy.keys()):
        parent_data = hierarchy[parent_num]
        parent_field = parent_data["field"]
        
        # Render parent
        render_field(parent_field, f"part_{part.number}")
        
        # Render children
        for child in sorted(parent_data["children"], key=lambda f: f.number):
            render_field(child, f"part_{part.number}")
    
    # Render any orphan fields
    orphans = [
        f for f in part.fields
        if f.number not in hierarchy and f.parent_number not in hierarchy
    ]
    
    for field in sorted(orphans, key=lambda f: f.number):
        render_field(field, f"part_{part.number}")

# ===== MAIN APPLICATION =====

def main():
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>🤖 USCIS Form Reader - Claude Opus 4.1</h1>
        <p>Intelligent form extraction with hierarchical field management</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize session state
    if 'form_data' not in st.session_state:
        st.session_state.form_data = None
    if 'agent' not in st.session_state:
        st.session_state.agent = OpusExtractionAgent()
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 📊 Dashboard")
        
        if st.session_state.form_data:
            data = st.session_state.form_data
            
            st.success(f"**Form:** {data.get('form_number', 'Unknown')}")
            
            total_fields = sum(
                len(part.get("fields", []))
                for part in data.get("parts", [])
            )
            
            st.metric("Total Parts", len(data.get("parts", [])))
            st.metric("Total Fields", total_fields)
            
            # Export section
            st.markdown("---")
            st.markdown("### 💾 Export Options")
            
            if st.button("📥 Export All Data", use_container_width=True):
                export_all_data()
            
            if st.button("🔄 Reset Form", use_container_width=True):
                st.session_state.clear()
                st.rerun()
        
        # API Status
        st.markdown("---")
        st.markdown("### 🔑 API Status")
        if st.session_state.agent.client:
            st.success("Claude Opus 4.1 Ready")
        else:
            st.error("API Key Missing")
    
    # Main tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📤 Upload & Extract",
        "🔗 Map Fields",
        "📝 Questionnaire",
        "💾 Export"
    ])
    
    with tab1:
        render_upload_tab()
    
    with tab2:
        render_mapping_tab()
    
    with tab3:
        render_questionnaire_tab()
    
    with tab4:
        render_export_tab()

def render_upload_tab():
    """Render upload and extraction tab"""
    
    st.markdown("### Upload USCIS Form PDF")
    
    uploaded_file = st.file_uploader(
        "Choose a PDF file",
        type=['pdf'],
        help="Upload any USCIS form (I-129, I-140, I-485, etc.)"
    )
    
    if uploaded_file:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.info(f"📄 **File:** {uploaded_file.name}")
        
        with col2:
            if st.button("🚀 Extract with Opus 4.1", type="primary", use_container_width=True):
                with st.spinner("Extracting form structure..."):
                    # Extract text
                    text, pages = extract_pdf_text(uploaded_file)
                    
                    if text:
                        # Use Opus agent to extract
                        data = st.session_state.agent.extract_form_structure(text)
                        
                        # Convert to FormPart objects
                        parts = []
                        for part_data in data.get("parts", []):
                            part = FormPart(
                                number=part_data["number"],
                                title=part_data["title"]
                            )
                            
                            # Convert fields
                            for field_data in part_data.get("fields", []):
                                field = FormField(
                                    number=field_data["number"],
                                    label=field_data["label"],
                                    field_type=field_data.get("type", "text"),
                                    parent_number=field_data.get("parent"),
                                    is_parent=field_data.get("is_parent", False),
                                    part=part.number
                                )
                                
                                # Add choices if present
                                if field_data.get("choices"):
                                    for choice_data in field_data["choices"]:
                                        field.choices.append(
                                            FieldChoice(
                                                letter=choice_data["letter"],
                                                text=choice_data["text"]
                                            )
                                        )
                                
                                part.fields.append(field)
                            
                            parts.append(part)
                        
                        # Store in session
                        st.session_state.form_data = data
                        st.session_state.form_parts = parts
                        
                        st.success(f"✅ Extracted {len(parts)} parts with {sum(len(p.fields) for p in parts)} fields")
                        
                        # Show extraction summary
                        st.markdown("### Extraction Summary")
                        
                        for part in parts:
                            with st.expander(f"Part {part.number}: {part.title} ({len(part.fields)} fields)"):
                                hierarchy = part.get_hierarchy()
                                
                                st.write(f"**Parent Fields:** {len(hierarchy)}")
                                st.write(f"**Total Fields:** {len(part.fields)}")
                                
                                # Show sample fields
                                st.markdown("**Sample Fields:**")
                                for i, field in enumerate(part.fields[:5]):
                                    st.write(f"- {field.number}. {field.label}")
                    else:
                        st.error("Could not extract text from PDF")

def render_mapping_tab():
    """Render field mapping tab"""
    
    if not st.session_state.get('form_parts'):
        st.info("👆 Please upload and extract a form first")
        return
    
    st.markdown("### Map Form Fields to Database")
    
    parts = st.session_state.form_parts
    
    # Part selector
    part_options = {
        p.number: f"Part {p.number}: {p.title}"
        for p in parts
    }
    
    selected_part = st.selectbox(
        "Select Part",
        options=list(part_options.keys()),
        format_func=lambda x: part_options[x]
    )
    
    if selected_part:
        part = next(p for p in parts if p.number == selected_part)
        
        st.markdown(f"#### {part_options[selected_part]}")
        st.info(f"Total fields: {len(part.fields)}")
        
        # Quick actions
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🎯 Auto-Map Common Fields"):
                auto_map_fields(part)
                st.rerun()
        
        with col2:
            mapped_count = sum(1 for f in part.fields if f.is_mapped)
            st.metric("Mapped", f"{mapped_count}/{len(part.fields)}")
        
        with col3:
            quest_count = sum(1 for f in part.fields if f.in_questionnaire)
            st.metric("In Questionnaire", quest_count)
        
        st.markdown("---")
        
        # Render fields
        render_part_fields(part)

def render_questionnaire_tab():
    """Render questionnaire tab"""
    
    if not st.session_state.get('form_parts'):
        st.info("👆 Please upload and extract a form first")
        return
    
    st.markdown("### Form Questionnaire")
    
    parts = st.session_state.form_parts
    
    # Collect all questionnaire fields
    quest_fields_by_part = {}
    
    for part in parts:
        quest_fields = [f for f in part.fields if f.in_questionnaire]
        if quest_fields:
            quest_fields_by_part[part.number] = {
                "title": part.title,
                "fields": quest_fields
            }
    
    if not quest_fields_by_part:
        st.info("No fields added to questionnaire yet. Use the Map Fields tab to add fields.")
        return
    
    # Display questionnaire
    for part_num, part_data in sorted(quest_fields_by_part.items()):
        st.markdown(f"#### Part {part_num}: {part_data['title']}")
        
        for field in part_data["fields"]:
            with st.container():
                st.markdown(f"**{field.number}. {field.label}**")
                
                if field.choices:
                    # Multiple choice question
                    for choice in field.choices:
                        choice_key = f"quest_{field.unique_id}_{choice.letter}"
                        choice.selected = st.checkbox(
                            f"{choice.letter}. {choice.text}",
                            value=choice.selected,
                            key=choice_key
                        )
                else:
                    # Regular input
                    input_key = f"quest_{field.unique_id}"
                    
                    if field.field_type == "date":
                        field.value = st.date_input(
                            "Answer",
                            key=input_key
                        )
                    elif field.field_type == "checkbox":
                        field.value = st.checkbox(
                            "Yes",
                            key=input_key
                        )
                    else:
                        field.value = st.text_area(
                            "Answer",
                            value=field.value or "",
                            key=input_key
                        )
                
                st.markdown("---")

def render_export_tab():
    """Render export tab"""
    
    if not st.session_state.get('form_parts'):
        st.info("👆 Please upload and extract a form first")
        return
    
    st.markdown("### Export Form Data")
    
    parts = st.session_state.form_parts
    
    # Export options
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🗂️ Export by Part")
        
        for part in parts:
            if st.button(
                f"Export Part {part.number}: {part.title}",
                key=f"export_part_{part.number}",
                use_container_width=True
            ):
                export_part_data(part)
    
    with col2:
        st.markdown("#### 📋 Export Categories")
        
        if st.button("Export All Mapped Fields", use_container_width=True):
            export_mapped_fields()
        
        if st.button("Export Questionnaire", use_container_width=True):
            export_questionnaire()
        
        if st.button("Export Complete Form", use_container_width=True):
            export_all_data()

def auto_map_fields(part: FormPart):
    """Auto-map common fields"""
    
    # Common mappings
    mappings = {
        "last name": ("beneficiary", "lastName"),
        "family name": ("beneficiary", "lastName"),
        "first name": ("beneficiary", "firstName"),
        "given name": ("beneficiary", "firstName"),
        "middle name": ("beneficiary", "middleName"),
        "date of birth": ("beneficiary", "dateOfBirth"),
        "country of birth": ("beneficiary", "countryOfBirth"),
        "alien number": ("beneficiary", "alienNumber"),
        "a-number": ("beneficiary", "alienNumber"),
        "social security": ("beneficiary", "ssn"),
        "email": ("beneficiary", "contact.email"),
        "phone": ("beneficiary", "contact.phone"),
        "street": ("beneficiary", "address.street"),
        "city": ("beneficiary", "address.city"),
        "state": ("beneficiary", "address.state"),
        "zip": ("beneficiary", "address.zip"),
    }
    
    for field in part.fields:
        if not field.is_mapped:
            label_lower = field.label.lower()
            
            for key, (obj, path) in mappings.items():
                if key in label_lower:
                    field.is_mapped = True
                    field.db_object = obj
                    field.db_path = path
                    break

def export_part_data(part: FormPart):
    """Export single part data"""
    
    data = {
        "part": part.number,
        "title": part.title,
        "fields": [field.to_dict() for field in part.fields]
    }
    
    json_str = json.dumps(data, indent=2)
    
    st.download_button(
        label=f"📥 Download Part {part.number}",
        data=json_str,
        file_name=f"part_{part.number}_data.json",
        mime="application/json"
    )

def export_mapped_fields():
    """Export all mapped fields"""
    
    parts = st.session_state.form_parts
    
    mapped_data = {}
    
    for part in parts:
        for field in part.fields:
            if field.is_mapped:
                if field.db_object not in mapped_data:
                    mapped_data[field.db_object] = {}
                
                path = field.db_path or field.number
                mapped_data[field.db_object][path] = {
                    "field": field.number,
                    "label": field.label,
                    "value": field.value
                }
    
    json_str = json.dumps(mapped_data, indent=2)
    
    st.download_button(
        label="📥 Download Mapped Fields",
        data=json_str,
        file_name="mapped_fields.json",
        mime="application/json"
    )

def export_questionnaire():
    """Export questionnaire responses"""
    
    parts = st.session_state.form_parts
    
    quest_data = {}
    
    for part in parts:
        quest_fields = [f for f in part.fields if f.in_questionnaire]
        
        if quest_fields:
            quest_data[f"Part {part.number}"] = {
                "title": part.title,
                "responses": [field.to_dict() for field in quest_fields]
            }
    
    json_str = json.dumps(quest_data, indent=2)
    
    st.download_button(
        label="📥 Download Questionnaire",
        data=json_str,
        file_name="questionnaire.json",
        mime="application/json"
    )

def export_all_data():
    """Export complete form data"""
    
    parts = st.session_state.form_parts
    form_data = st.session_state.form_data
    
    export = {
        "form": {
            "number": form_data.get("form_number", "Unknown"),
            "title": form_data.get("form_title", "")
        },
        "parts": []
    }
    
    for part in parts:
        part_data = {
            "number": part.number,
            "title": part.title,
            "fields": [field.to_dict() for field in part.fields],
            "mapped_count": sum(1 for f in part.fields if f.is_mapped),
            "questionnaire_count": sum(1 for f in part.fields if f.in_questionnaire)
        }
        export["parts"].append(part_data)
    
    json_str = json.dumps(export, indent=2)
    
    st.download_button(
        label="📥 Download Complete Form Data",
        data=json_str,
        file_name=f"{form_data.get('form_number', 'form')}_complete.json",
        mime="application/json"
    )

if __name__ == "__main__":
    main()
