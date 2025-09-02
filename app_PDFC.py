#!/usr/bin/env python3
"""
UNIVERSAL USCIS FORM READER - COMPLETE FINAL VERSION
====================================================
Multi-agent extraction system with Claude Opus API integration
"""

import streamlit as st
import json
import re
import uuid
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field as dataclass_field

# Page configuration
st.set_page_config(
    page_title="USCIS Form Reader",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Try to import Anthropic
try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    st.warning("Anthropic library not installed. Running in pattern-only mode.")

# Custom CSS
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 10px;
        color: white;
        margin-bottom: 2rem;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .field-container {
        background: white;
        border-radius: 8px;
        padding: 12px;
        margin: 8px 0;
        border-left: 4px solid #e0e0e0;
        transition: all 0.3s ease;
    }
    .field-container:hover {
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    .field-parent {
        border-left-color: #667eea;
        background: #f8f9ff;
        font-weight: 600;
    }
    .field-subfield {
        margin-left: 30px;
        border-left-color: #a8b4ff;
    }
    .field-mapped {
        background: #e8f5e9;
        border-left-color: #4caf50;
    }
    .field-questionnaire {
        background: #fff8e1;
        border-left-color: #ffc107;
    }
    .field-number-badge {
        background: #667eea;
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.85em;
        font-weight: bold;
        margin-right: 8px;
        display: inline-block;
    }
    .extraction-stats {
        background: #f5f5f5;
        padding: 15px;
        border-radius: 8px;
        margin: 15px 0;
    }
    .success-badge {
        background: #d4edda;
        color: #155724;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.85em;
    }
    .warning-badge {
        background: #fff3cd;
        color: #856404;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.85em;
    }
</style>
""", unsafe_allow_html=True)

# ===== DATA MODELS =====

@dataclass
class FieldChoice:
    """Choice option for fields"""
    letter: str
    text: str
    selected: bool = False

@dataclass
class FormField:
    """Form field structure"""
    number: str
    label: str
    field_type: str = "text"
    value: Any = ""
    
    # Hierarchy
    part_number: int = 1
    parent_number: Optional[str] = None
    is_parent: bool = False
    is_subfield: bool = False
    choices: List[FieldChoice] = dataclass_field(default_factory=list)
    
    # Mapping
    is_mapped: bool = False
    db_object: str = ""
    db_path: str = ""
    
    # Questionnaire
    in_questionnaire: bool = False
    
    # Metadata
    page: int = 1
    extraction_method: str = "pattern"
    confidence: float = 1.0
    position: int = 0
    
    def get_unique_key(self) -> str:
        """Generate unique key for this field"""
        return hashlib.md5(f"{self.part_number}_{self.number}_{uuid.uuid4()}".encode()).hexdigest()[:12]
    
    def get_sort_key(self) -> Tuple:
        """Get sort key for ordering"""
        try:
            parts = self.number.replace('-', '.').split('.')
            main = int(parts[0]) if parts[0].isdigit() else 999
            
            sub = 0
            if len(parts) > 1 and parts[1]:
                if parts[1][0].isalpha():
                    sub = ord(parts[1][0].lower()) - ord('a') + 1
                elif parts[1].isdigit():
                    sub = int(parts[1]) + 100
            
            return (main, sub, self.position)
        except:
            return (999, 0, self.position)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for export"""
        data = {
            "number": self.number,
            "label": self.label,
            "type": self.field_type,
            "value": str(self.value) if self.value else "",
            "part": self.part_number
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
        
        if self.parent_number:
            data["parent"] = self.parent_number
        
        return data

@dataclass
class FormPart:
    """Form part/section"""
    number: int
    title: str
    fields: List[FormField] = dataclass_field(default_factory=list)
    
    def get_stats(self) -> Dict:
        """Get statistics for this part"""
        return {
            "total_fields": len(self.fields),
            "mapped_fields": sum(1 for f in self.fields if f.is_mapped),
            "questionnaire_fields": sum(1 for f in self.fields if f.in_questionnaire),
            "parent_fields": sum(1 for f in self.fields if f.is_parent),
            "subfields": sum(1 for f in self.fields if f.is_subfield)
        }

# ===== DATABASE SCHEMA =====

DB_SCHEMA = {
    "beneficiary": {
        "label": "👤 Beneficiary/Applicant",
        "fields": [
            "lastName", "firstName", "middleName", "otherNames",
            "alienNumber", "uscisNumber", "ssn", "dateOfBirth",
            "countryOfBirth", "cityOfBirth", "citizenship",
            "address.street", "address.apt", "address.city",
            "address.state", "address.zip", "address.country",
            "phone.daytime", "phone.mobile", "email"
        ]
    },
    "petitioner": {
        "label": "🏢 Petitioner/Employer",
        "fields": [
            "lastName", "firstName", "middleName", "companyName",
            "ein", "ssn", "address.street", "address.suite",
            "address.city", "address.state", "address.zip",
            "phone", "email", "website"
        ]
    },
    "employment": {
        "label": "💼 Employment",
        "fields": [
            "jobTitle", "socCode", "naicsCode", "wages",
            "startDate", "endDate", "worksite.address",
            "worksite.city", "worksite.state"
        ]
    },
    "custom": {
        "label": "✏️ Custom",
        "fields": []
    }
}

# ===== EXTRACTION ENGINE =====

class FormExtractor:
    """Main extraction engine"""
    
    def __init__(self):
        self.client = None
        self.setup_client()
    
    def setup_client(self):
        """Setup Anthropic client if available"""
        if not ANTHROPIC_AVAILABLE:
            return
        
        try:
            api_key = st.secrets.get("ANTHROPIC_API_KEY", None)
            if api_key:
                self.client = Anthropic(api_key=api_key)
                st.sidebar.success("✅ Claude API Ready")
            else:
                st.sidebar.info("ℹ️ Add API key for AI extraction")
        except Exception as e:
            st.sidebar.warning(f"⚠️ API setup failed: {str(e)[:50]}")
    
    def extract_form(self, text: str, page_count: int) -> Dict:
        """Extract form data"""
        result = {
            "success": False,
            "form_number": "Unknown",
            "form_title": "USCIS Form",
            "parts": [],
            "stats": {}
        }
        
        try:
            # Extract form info
            form_info = self._extract_form_info(text)
            result.update(form_info)
            
            # Extract parts
            parts_info = self._extract_parts(text)
            
            # Process each part
            for part_info in parts_info:
                part = FormPart(
                    number=part_info["number"],
                    title=part_info["title"]
                )
                
                # Get part text
                part_text = self._get_part_text(text, part.number)
                
                # Extract fields
                if self.client:
                    # Try AI extraction
                    fields = self._extract_fields_ai(part_text, part.number)
                    if not fields:
                        fields = self._extract_fields_pattern(part_text, part.number)
                else:
                    # Pattern extraction only
                    fields = self._extract_fields_pattern(part_text, part.number)
                
                # Sort fields
                fields.sort(key=lambda f: f.get_sort_key())
                part.fields = fields
                result["parts"].append(part)
            
            # If no parts found, treat as single section
            if not result["parts"]:
                part = FormPart(number=1, title="Main Section")
                fields = self._extract_fields_pattern(text[:15000], 1)
                fields.sort(key=lambda f: f.get_sort_key())
                part.fields = fields
                result["parts"].append(part)
            
            # Calculate stats
            result["stats"] = {
                "total_parts": len(result["parts"]),
                "total_fields": sum(len(p.fields) for p in result["parts"])
            }
            
            result["success"] = True
            
        except Exception as e:
            st.error(f"Extraction error: {str(e)[:100]}")
        
        return result
    
    def _extract_form_info(self, text: str) -> Dict:
        """Extract form number and title"""
        info = {"form_number": "Unknown", "form_title": "USCIS Form"}
        
        # Patterns for form number
        patterns = [
            r'Form\s+([I]-\d+[A-Z]?)',
            r'USCIS\s+Form\s+([I]-\d+[A-Z]?)',
            r'([I]-\d+[A-Z]?)\s+[,\s]*'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text[:3000], re.IGNORECASE)
            if match:
                info["form_number"] = match.group(1).upper()
                info["form_title"] = f"USCIS Form {info['form_number']}"
                break
        
        return info
    
    def _extract_parts(self, text: str) -> List[Dict]:
        """Extract all parts from form"""
        parts = []
        seen_numbers = set()
        
        # Pattern for parts
        pattern = r'Part\s+(\d+)[.\s\-–]*([^\n]{3,100})'
        matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
        
        for match in matches:
            try:
                part_num = int(match.group(1))
                if part_num not in seen_numbers:
                    title = match.group(2).strip()
                    title = re.sub(r'^[.\-–\s]+', '', title)
                    title = re.sub(r'[.\s]+$', '', title)
                    
                    parts.append({
                        "number": part_num,
                        "title": title[:100],
                        "position": match.start()
                    })
                    seen_numbers.add(part_num)
            except:
                continue
        
        return sorted(parts, key=lambda x: x["number"])
    
    def _get_part_text(self, text: str, part_number: int) -> str:
        """Get text for specific part"""
        # Find part start
        pattern = f"Part\\s+{part_number}\\b"
        match = re.search(pattern, text, re.IGNORECASE)
        
        if not match:
            return text[:15000]
        
        start = match.start()
        
        # Find next part
        next_pattern = f"Part\\s+{part_number + 1}\\b"
        next_match = re.search(next_pattern, text[start:], re.IGNORECASE)
        
        if next_match:
            end = start + next_match.start()
        else:
            end = min(start + 20000, len(text))
        
        return text[start:end]
    
    def _extract_fields_pattern(self, text: str, part_number: int) -> List[FormField]:
        """Extract fields using patterns"""
        fields = []
        seen = set()
        position = 0
        
        # Comprehensive patterns
        patterns = [
            # Subfields: 1.a. or 1a.
            (r'(\d+)\.([a-z])\.?\s+([^\n]{3,150})', 'subfield'),
            # Main fields: 1.
            (r'(\d+)\.\s+([^\n]{3,150})', 'main'),
            # Item Number format
            (r'Item\s+Number\s+(\d+)[.\s]*([^\n]{3,150})', 'item'),
        ]
        
        for pattern, field_type in patterns:
            matches = re.finditer(pattern, text[:15000], re.IGNORECASE)
            
            for match in matches:
                try:
                    if field_type == 'subfield':
                        number = f"{match.group(1)}.{match.group(2)}"
                        label = match.group(3).strip()
                        parent = match.group(1)
                        is_sub = True
                    else:
                        number = match.group(1)
                        label = match.group(2).strip() if len(match.groups()) > 1 else f"Field {number}"
                        parent = None
                        is_sub = False
                    
                    # Skip if already seen
                    if number in seen:
                        continue
                    
                    seen.add(number)
                    
                    # Clean label
                    label = re.sub(r'\s+', ' ', label)[:150]
                    
                    # Detect field type
                    detected_type = self._detect_field_type(label)
                    
                    # Check for choices
                    context_start = max(0, match.start())
                    context_end = min(len(text), match.end() + 300)
                    context = text[context_start:context_end]
                    choices = self._extract_choices(context)
                    
                    # Create field
                    field = FormField(
                        number=number,
                        label=label,
                        field_type=detected_type,
                        part_number=part_number,
                        parent_number=parent,
                        is_parent=(not is_sub and not parent),
                        is_subfield=is_sub,
                        choices=choices,
                        position=position,
                        extraction_method="pattern"
                    )
                    
                    fields.append(field)
                    position += 1
                    
                except Exception:
                    continue
        
        # Create parent fields for orphan subfields
        self._create_parent_fields(fields, part_number)
        
        return fields
    
    def _extract_fields_ai(self, text: str, part_number: int) -> List[FormField]:
        """Extract fields using AI"""
        if not self.client:
            return []
        
        try:
            prompt = f"""Extract ALL fields from Part {part_number} of this USCIS form.

Include:
1. Every numbered field (1, 2, 3...)
2. Every subfield (1.a, 1.b, 1.c...)
3. Any checkbox/radio options

Return JSON array:
[
  {{
    "number": "1",
    "label": "Full Legal Name",
    "type": "parent",
    "is_parent": true
  }},
  {{
    "number": "1.a",
    "label": "Family Name (Last Name)",
    "type": "text",
    "parent": "1"
  }}
]

Text:
{text[:8000]}"""
            
            response = self.client.messages.create(
                model="claude-3-opus-20240229",
                max_tokens=3000,
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = response.content[0].text
            
            # Extract JSON
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                
                fields = []
                position = 0
                
                for item in data:
                    field = FormField(
                        number=item.get("number", ""),
                        label=item.get("label", ""),
                        field_type=item.get("type", "text"),
                        part_number=part_number,
                        parent_number=item.get("parent"),
                        is_parent=item.get("is_parent", False),
                        position=position,
                        extraction_method="AI"
                    )
                    
                    if field.number:
                        fields.append(field)
                        position += 1
                
                return fields
                
        except Exception as e:
            st.warning(f"AI extraction failed: {str(e)[:50]}")
        
        return []
    
    def _extract_choices(self, context: str) -> List[FieldChoice]:
        """Extract checkbox/radio options"""
        choices = []
        
        # Patterns for checkboxes
        patterns = [
            r'[□☐]\s*([^\n□☐]{2,80})',
            r'\[\s*\]\s*([^\n\[\]]{2,80})'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, context[:500])
            if matches and len(matches) >= 2:
                for i, text in enumerate(matches[:5]):
                    choices.append(FieldChoice(
                        letter=chr(ord('a') + i),
                        text=text.strip()
                    ))
                break
        
        return choices
    
    def _create_parent_fields(self, fields: List[FormField], part_number: int):
        """Create parent fields for orphan subfields"""
        # Find parent numbers that need to be created
        parent_nums = {f.parent_number for f in fields if f.parent_number}
        existing_nums = {f.number for f in fields}
        
        for parent_num in parent_nums:
            if parent_num and parent_num not in existing_nums:
                parent_field = FormField(
                    number=parent_num,
                    label=f"Field {parent_num}",
                    field_type="parent",
                    part_number=part_number,
                    is_parent=True,
                    extraction_method="inferred"
                )
                fields.append(parent_field)
    
    def _detect_field_type(self, label: str) -> str:
        """Detect field type from label"""
        label_lower = label.lower()
        
        if any(w in label_lower for w in ["date", "birth", "expire", "issued"]):
            return "date"
        elif "email" in label_lower:
            return "email"
        elif any(w in label_lower for w in ["phone", "telephone", "mobile"]):
            return "phone"
        elif "ssn" in label_lower or "social security" in label_lower:
            return "ssn"
        elif any(w in label_lower for w in ["check", "select", "mark", "choose"]):
            return "checkbox"
        
        return "text"

# ===== PDF EXTRACTION =====

def extract_pdf_text(pdf_file) -> Tuple[str, int]:
    """Extract text from PDF"""
    try:
        # Try PyMuPDF first (better extraction)
        try:
            import fitz
            pdf_file.seek(0)
            pdf_bytes = pdf_file.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            full_text = ""
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                full_text += f"\n\n=== PAGE {page_num + 1} ===\n{text}"
            
            total_pages = len(doc)
            doc.close()
            
            return full_text, total_pages
            
        except ImportError:
            # Fallback to PyPDF2
            import PyPDF2
            pdf_file.seek(0)
            reader = PyPDF2.PdfReader(pdf_file)
            
            full_text = ""
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                full_text += f"\n\n=== PAGE {i + 1} ===\n{text}"
            
            return full_text, len(reader.pages)
            
    except ImportError:
        st.error("Please install PyPDF2 or pymupdf: pip install PyPDF2 pymupdf")
        return "", 0
    except Exception as e:
        st.error(f"PDF reading error: {str(e)}")
        return "", 0

# ===== UI COMPONENTS =====

def render_field(field: FormField, session_key: str):
    """Render a single field"""
    # Generate unique key for this field
    unique_key = f"{session_key}_{field.get_unique_key()}"
    
    # Determine CSS class
    css_class = "field-container"
    if field.is_parent:
        css_class += " field-parent"
    elif field.is_subfield:
        css_class += " field-subfield"
    if field.is_mapped:
        css_class += " field-mapped"
    elif field.in_questionnaire:
        css_class += " field-questionnaire"
    
    with st.container():
        st.markdown(f'<div class="{css_class}">', unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([4, 2, 2])
        
        with col1:
            # Field info
            st.markdown(
                f'<span class="field-number-badge">{field.number}</span>'
                f'<strong>{field.label}</strong>',
                unsafe_allow_html=True
            )
            
            # Show choices
            if field.choices:
                for choice in field.choices:
                    choice.selected = st.checkbox(
                        f"{choice.letter}. {choice.text}",
                        value=choice.selected,
                        key=f"{unique_key}_choice_{choice.letter}"
                    )
        
        with col2:
            # Value input
            if not field.is_parent and not field.choices:
                if field.field_type == "date":
                    value = st.date_input(
                        "Value",
                        key=f"{unique_key}_value",
                        label_visibility="collapsed"
                    )
                    field.value = str(value) if value else ""
                elif field.field_type == "checkbox":
                    field.value = st.checkbox(
                        "Check",
                        key=f"{unique_key}_value"
                    )
                else:
                    field.value = st.text_input(
                        "Value",
                        value=field.value or "",
                        key=f"{unique_key}_value",
                        label_visibility="collapsed"
                    )
        
        with col3:
            # Actions
            c1, c2 = st.columns(2)
            
            with c1:
                if field.is_mapped:
                    st.success("✓ Mapped")
                else:
                    if st.button("Map", key=f"{unique_key}_map"):
                        st.session_state[f"mapping_{unique_key}"] = True
            
            with c2:
                if field.in_questionnaire:
                    if st.button("Quest ✓", key=f"{unique_key}_quest"):
                        field.in_questionnaire = False
                        st.rerun()
                else:
                    if st.button("Quest +", key=f"{unique_key}_quest"):
                        field.in_questionnaire = True
                        st.rerun()
        
        # Mapping dialog
        if st.session_state.get(f"mapping_{unique_key}"):
            render_mapping_dialog(field, unique_key)
        
        st.markdown('</div>', unsafe_allow_html=True)

def render_mapping_dialog(field: FormField, unique_key: str):
    """Render mapping configuration"""
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        db_obj = st.selectbox(
            "Database Object",
            [""] + list(DB_SCHEMA.keys()),
            key=f"{unique_key}_obj"
        )
    
    with col2:
        if db_obj and db_obj != "custom":
            db_path = st.selectbox(
                "Field Path",
                [""] + DB_SCHEMA[db_obj]["fields"],
                key=f"{unique_key}_path"
            )
        else:
            db_path = st.text_input(
                "Custom Path",
                key=f"{unique_key}_custom"
            )
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("✅ Apply", key=f"{unique_key}_apply"):
            if db_obj and db_path:
                field.is_mapped = True
                field.db_object = db_obj
                field.db_path = db_path
                del st.session_state[f"mapping_{unique_key}"]
                st.rerun()
    
    with col2:
        if st.button("❌ Cancel", key=f"{unique_key}_cancel"):
            del st.session_state[f"mapping_{unique_key}"]
            st.rerun()

# ===== MAIN APPLICATION =====

def main():
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>📋 USCIS Form Reader</h1>
        <p>Extract, Map, and Export Form Data</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize session state
    if 'form_data' not in st.session_state:
        st.session_state.form_data = None
    if 'extractor' not in st.session_state:
        st.session_state.extractor = FormExtractor()
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 📊 Dashboard")
        
        if st.session_state.form_data and st.session_state.form_data.get("success"):
            data = st.session_state.form_data
            
            st.success(f"**Form:** {data['form_number']}")
            st.metric("Parts", len(data["parts"]))
            st.metric("Total Fields", data["stats"]["total_fields"])
            
            # Part statistics
            st.markdown("### Parts Overview")
            for part in data["parts"]:
                stats = part.get_stats()
                st.write(f"**Part {part.number}:** {stats['total_fields']} fields")
        
        st.markdown("---")
        if st.button("🔄 Reset All", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    
    # Main tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📤 Upload",
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
    """Upload and extraction tab"""
    st.markdown("### Upload USCIS Form PDF")
    
    uploaded_file = st.file_uploader(
        "Choose a PDF file",
        type=['pdf'],
        help="Upload any USCIS form (I-129, I-140, etc.)"
    )
    
    if uploaded_file:
        st.info(f"📄 File: {uploaded_file.name} ({uploaded_file.size:,} bytes)")
        
        if st.button("🚀 Extract Form Data", type="primary", use_container_width=True):
            with st.spinner("Extracting form data..."):
                # Extract PDF text
                text, page_count = extract_pdf_text(uploaded_file)
                
                if text:
                    # Extract form data
                    form_data = st.session_state.extractor.extract_form(text, page_count)
                    
                    if form_data["success"]:
                        st.session_state.form_data = form_data
                        
                        # Success message
                        st.success(
                            f"✅ Successfully extracted {form_data['stats']['total_fields']} fields "
                            f"from {len(form_data['parts'])} parts"
                        )
                        
                        # Show summary
                        with st.expander("📊 Extraction Summary"):
                            for part in form_data["parts"]:
                                st.write(f"**Part {part.number}: {part.title}**")
                                st.write(f"  • Total fields: {len(part.fields)}")
                                
                                # Show sample fields
                                if part.fields:
                                    st.write("  • Sample fields:")
                                    for field in part.fields[:3]:
                                        st.write(f"    - {field.number}: {field.label[:50]}")
                    else:
                        st.error("Failed to extract form data")
                else:
                    st.error("Could not read PDF text")

def render_mapping_tab():
    """Field mapping tab"""
    if not st.session_state.form_data or not st.session_state.form_data.get("success"):
        st.info("👆 Please upload and extract a form first")
        return
    
    st.markdown("### Map Form Fields to Database")
    
    data = st.session_state.form_data
    
    # Part selector
    part_nums = [p.number for p in data["parts"]]
    selected_part = st.selectbox(
        "Select Part",
        part_nums,
        format_func=lambda x: f"Part {x}: {next(p.title for p in data['parts'] if p.number == x)}"
    )
    
    if selected_part:
        part = next(p for p in data["parts"] if p.number == selected_part)
        
        # Statistics
        stats = part.get_stats()
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Fields", stats["total_fields"])
        with col2:
            st.metric("Mapped", stats["mapped_fields"])
        with col3:
            st.metric("In Questionnaire", stats["questionnaire_fields"])
        
        st.markdown("---")
        
        # Display fields
        for field in part.fields:
            render_field(field, f"map_p{part.number}")

def render_questionnaire_tab():
    """Questionnaire tab"""
    if not st.session_state.form_data or not st.session_state.form_data.get("success"):
        st.info("👆 Please upload and extract a form first")
        return
    
    st.markdown("### Form Questionnaire")
    
    data = st.session_state.form_data
    
    # Collect questionnaire fields
    quest_fields = []
    for part in data["parts"]:
        for field in part.fields:
            if field.in_questionnaire:
                quest_fields.append((part, field))
    
    if not quest_fields:
        st.info("No fields in questionnaire. Use the Map Fields tab to add fields.")
        return
    
    # Display questionnaire fields
    current_part = None
    for part, field in quest_fields:
        if part != current_part:
            st.markdown(f"#### Part {part.number}: {part.title}")
            current_part = part
        
        with st.container():
            st.markdown(f"**{field.number}. {field.label}**")
            
            quest_key = f"quest_{field.get_unique_key()}"
            
            if field.choices:
                for choice in field.choices:
                    choice.selected = st.checkbox(
                        f"{choice.letter}. {choice.text}",
                        value=choice.selected,
                        key=f"{quest_key}_c_{choice.letter}"
                    )
            elif field.field_type == "date":
                field.value = st.date_input("Answer", key=quest_key)
            else:
                field.value = st.text_area(
                    "Answer",
                    value=field.value or "",
                    key=quest_key,
                    height=70
                )
            
            st.markdown("---")

def render_export_tab():
    """Export tab"""
    if not st.session_state.form_data or not st.session_state.form_data.get("success"):
        st.info("👆 Please upload and extract a form first")
        return
    
    st.markdown("### Export Form Data")
    
    data = st.session_state.form_data
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Export by Part")
        
        for i, part in enumerate(data["parts"]):
            export_key = f"exp_{i}_{uuid.uuid4().hex[:8]}"
            if st.button(
                f"📥 Part {part.number}: {part.title[:30]}",
                key=export_key,
                use_container_width=True
            ):
                export_part_data(part, export_key)
    
    with col2:
        st.markdown("#### Export All")
        
        if st.button("📥 Export Mapped Fields", key=f"exp_mapped_{uuid.uuid4().hex[:8]}"):
            export_mapped_fields(data)
        
        if st.button("📥 Export Questionnaire", key=f"exp_quest_{uuid.uuid4().hex[:8]}"):
            export_questionnaire(data)
        
        if st.button("📥 Export Complete Form", key=f"exp_all_{uuid.uuid4().hex[:8]}"):
            export_all_data(data)

# ===== EXPORT FUNCTIONS =====

def export_part_data(part: FormPart, key: str):
    """Export single part data"""
    data = {
        "part": part.number,
        "title": part.title,
        "fields": [f.to_dict() for f in part.fields],
        "stats": part.get_stats()
    }
    
    json_str = json.dumps(data, indent=2, default=str)
    
    st.download_button(
        "💾 Download Part Data",
        json_str,
        f"part_{part.number}_data.json",
        "application/json",
        key=f"dl_{key}"
    )

def export_mapped_fields(data: Dict):
    """Export all mapped fields"""
    mapped = {}
    
    for part in data["parts"]:
        for field in part.fields:
            if field.is_mapped:
                if field.db_object not in mapped:
                    mapped[field.db_object] = {}
                
                mapped[field.db_object][field.db_path] = {
                    "field": field.number,
                    "label": field.label,
                    "value": str(field.value) if field.value else "",
                    "part": part.number
                }
    
    json_str = json.dumps(mapped, indent=2, default=str)
    
    st.download_button(
        "💾 Download Mapped Fields",
        json_str,
        "mapped_fields.json",
        "application/json",
        key=f"dl_mapped_{uuid.uuid4().hex[:8]}"
    )

def export_questionnaire(data: Dict):
    """Export questionnaire responses"""
    quest_data = {}
    
    for part in data["parts"]:
        quest_fields = [f for f in part.fields if f.in_questionnaire]
        
        if quest_fields:
            quest_data[f"Part_{part.number}"] = {
                "title": part.title,
                "responses": [f.to_dict() for f in quest_fields]
            }
    
    json_str = json.dumps(quest_data, indent=2, default=str)
    
    st.download_button(
        "💾 Download Questionnaire",
        json_str,
        "questionnaire.json",
        "application/json",
        key=f"dl_quest_{uuid.uuid4().hex[:8]}"
    )

def export_all_data(data: Dict):
    """Export complete form data"""
    export = {
        "form": {
            "number": data["form_number"],
            "title": data["form_title"]
        },
        "stats": data["stats"],
        "parts": []
    }
    
    for part in data["parts"]:
        part_data = {
            "number": part.number,
            "title": part.title,
            "fields": [f.to_dict() for f in part.fields],
            "stats": part.get_stats()
        }
        export["parts"].append(part_data)
    
    json_str = json.dumps(export, indent=2, default=str)
    
    st.download_button(
        "💾 Download Complete Form",
        json_str,
        f"{data['form_number']}_complete.json",
        "application/json",
        key=f"dl_all_{uuid.uuid4().hex[:8]}"
    )

if __name__ == "__main__":
    main()
