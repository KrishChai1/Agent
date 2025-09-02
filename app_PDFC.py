#!/usr/bin/env python3
"""
UNIVERSAL USCIS FORM READER - PRODUCTION VERSION
================================================
Complete extraction system with fallback patterns
"""

# Standard library imports
import json
import re
import uuid
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field as dataclass_field

# Third-party imports
import streamlit as st

# Try to import Anthropic
try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

# Page configuration
st.set_page_config(
    page_title="USCIS Form Reader",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Show import status
if not ANTHROPIC_AVAILABLE:
    st.sidebar.warning("Anthropic not installed. Using pattern extraction only.")

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
    }
    .field-container {
        background: white;
        border-radius: 8px;
        padding: 12px;
        margin: 8px 0;
        border-left: 4px solid #e0e0e0;
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
    extraction_method: str = "pattern"
    position: int = 0
    
    def get_unique_key(self) -> str:
        """Generate unique key"""
        return f"{self.part_number}_{self.number}_{uuid.uuid4().hex[:8]}"
    
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
        """Convert to dictionary"""
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
            data["mapping"] = {"object": self.db_object, "path": self.db_path}
        
        return data

@dataclass
class FormPart:
    """Form part/section"""
    number: int
    title: str
    fields: List[FormField] = dataclass_field(default_factory=list)
    
    def get_stats(self) -> Dict:
        """Get statistics"""
        return {
            "total_fields": len(self.fields),
            "mapped_fields": sum(1 for f in self.fields if f.is_mapped),
            "questionnaire_fields": sum(1 for f in self.fields if f.in_questionnaire)
        }

# ===== DATABASE SCHEMA =====

DB_SCHEMA = {
    "beneficiary": {
        "label": "👤 Beneficiary",
        "fields": [
            "lastName", "firstName", "middleName",
            "alienNumber", "uscisNumber", "ssn",
            "dateOfBirth", "countryOfBirth", "citizenship",
            "address.street", "address.city", "address.state", "address.zip",
            "phone", "email"
        ]
    },
    "petitioner": {
        "label": "🏢 Petitioner",
        "fields": [
            "lastName", "firstName", "companyName",
            "ein", "ssn", "address.street",
            "address.city", "address.state", "address.zip",
            "phone", "email"
        ]
    },
    "employment": {
        "label": "💼 Employment",
        "fields": [
            "jobTitle", "socCode", "wages",
            "startDate", "endDate",
            "worksite.city", "worksite.state"
        ]
    }
}

# ===== EXTRACTION ENGINE =====

class FormExtractor:
    """Main extraction engine"""
    
    def __init__(self):
        self.client = None
        self.setup_client()
    
    def setup_client(self):
        """Setup Anthropic client"""
        if not ANTHROPIC_AVAILABLE:
            return
        
        try:
            api_key = st.secrets.get("ANTHROPIC_API_KEY", None)
            if api_key:
                self.client = Anthropic(api_key=api_key)
                st.sidebar.success("✅ Claude API Ready")
        except Exception as e:
            st.sidebar.warning(f"API setup issue: {str(e)[:30]}")
    
    def extract_form(self, text: str) -> Dict:
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
                fields = self._extract_fields(part_text, part.number)
                
                # Sort fields
                fields.sort(key=lambda f: f.get_sort_key())
                part.fields = fields
                result["parts"].append(part)
            
            # Default part if none found
            if not result["parts"]:
                part = FormPart(number=1, title="Main Section")
                fields = self._extract_fields(text[:10000], 1)
                fields.sort(key=lambda f: f.get_sort_key())
                part.fields = fields
                result["parts"].append(part)
            
            # Stats
            result["stats"] = {
                "total_parts": len(result["parts"]),
                "total_fields": sum(len(p.fields) for p in result["parts"])
            }
            
            result["success"] = True
            
        except Exception as e:
            st.error(f"Extraction error: {str(e)[:100]}")
        
        return result
    
    def _extract_form_info(self, text: str) -> Dict:
        """Extract form number"""
        info = {"form_number": "Unknown", "form_title": "USCIS Form"}
        
        patterns = [
            r'Form\s+([I]-\d+[A-Z]?)',
            r'USCIS\s+Form\s+([I]-\d+[A-Z]?)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text[:3000], re.IGNORECASE)
            if match:
                info["form_number"] = match.group(1).upper()
                info["form_title"] = f"USCIS Form {info['form_number']}"
                break
        
        return info
    
    def _extract_parts(self, text: str) -> List[Dict]:
        """Extract parts"""
        parts = []
        seen = set()
        
        pattern = r'Part\s+(\d+)[.\s\-–]*([^\n]{3,100})'
        matches = re.finditer(pattern, text, re.IGNORECASE)
        
        for match in matches:
            try:
                num = int(match.group(1))
                if num not in seen:
                    title = match.group(2).strip()
                    title = re.sub(r'^[.\-–\s]+', '', title)[:100]
                    
                    parts.append({
                        "number": num,
                        "title": title
                    })
                    seen.add(num)
            except:
                continue
        
        return sorted(parts, key=lambda x: x["number"])
    
    def _get_part_text(self, text: str, part_num: int) -> str:
        """Get text for part"""
        pattern = f"Part\\s+{part_num}\\b"
        match = re.search(pattern, text, re.IGNORECASE)
        
        if not match:
            return text[:10000]
        
        start = match.start()
        
        # Find next part
        next_pattern = f"Part\\s+{part_num + 1}\\b"
        next_match = re.search(next_pattern, text[start:], re.IGNORECASE)
        
        if next_match:
            end = start + next_match.start()
        else:
            end = min(start + 15000, len(text))
        
        return text[start:end]
    
    def _extract_fields(self, text: str, part_num: int) -> List[FormField]:
        """Extract fields from text"""
        # Try AI if available
        if self.client:
            fields = self._extract_fields_ai(text, part_num)
            if fields:
                return fields
        
        # Fallback to patterns
        return self._extract_fields_pattern(text, part_num)
    
    def _extract_fields_pattern(self, text: str, part_num: int) -> List[FormField]:
        """Pattern-based extraction"""
        fields = []
        seen = set()
        pos = 0
        
        patterns = [
            # Subfields: 1.a.
            (r'(\d+)\.([a-z])\.?\s+([^\n]{3,150})', 'subfield'),
            # Main fields: 1.
            (r'(\d+)\.\s+([^\n]{3,150})', 'main'),
        ]
        
        for pattern, ftype in patterns:
            matches = re.finditer(pattern, text[:10000], re.IGNORECASE)
            
            for match in matches:
                try:
                    if ftype == 'subfield':
                        number = f"{match.group(1)}.{match.group(2)}"
                        label = match.group(3).strip()
                        parent = match.group(1)
                        is_sub = True
                    else:
                        number = match.group(1)
                        label = match.group(2).strip()
                        parent = None
                        is_sub = False
                    
                    if number in seen:
                        continue
                    
                    seen.add(number)
                    
                    # Clean label
                    label = re.sub(r'\s+', ' ', label)[:150]
                    
                    # Detect type
                    field_type = self._detect_type(label)
                    
                    # Check for choices
                    ctx_end = min(len(text), match.end() + 300)
                    ctx = text[match.start():ctx_end]
                    choices = self._extract_choices(ctx)
                    
                    field = FormField(
                        number=number,
                        label=label,
                        field_type=field_type,
                        part_number=part_num,
                        parent_number=parent,
                        is_parent=(not is_sub and not parent),
                        is_subfield=is_sub,
                        choices=choices,
                        position=pos
                    )
                    
                    fields.append(field)
                    pos += 1
                    
                except:
                    continue
        
        # Create parents for orphans
        self._create_parents(fields, part_num)
        
        return fields
    
    def _extract_fields_ai(self, text: str, part_num: int) -> List[FormField]:
        """AI extraction"""
        if not self.client:
            return []
        
        try:
            prompt = f"""Extract ALL fields from Part {part_num}.

Include every field number and label.

Return JSON array:
[
  {{"number": "1", "label": "Full Name", "type": "parent"}},
  {{"number": "1.a", "label": "Last Name", "parent": "1"}}
]

Text: {text[:6000]}"""
            
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2000,
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = response.content[0].text
            
            # Extract JSON
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                
                fields = []
                pos = 0
                
                for item in data:
                    if item.get("number"):
                        field = FormField(
                            number=item["number"],
                            label=item.get("label", ""),
                            field_type=item.get("type", "text"),
                            part_number=part_num,
                            parent_number=item.get("parent"),
                            is_parent=item.get("type") == "parent",
                            position=pos,
                            extraction_method="AI"
                        )
                        fields.append(field)
                        pos += 1
                
                return fields
                
        except Exception as e:
            st.warning(f"AI extraction failed: {str(e)[:50]}")
        
        return []
    
    def _extract_choices(self, text: str) -> List[FieldChoice]:
        """Extract checkbox options"""
        choices = []
        
        patterns = [
            r'[□☐]\s*([^\n□☐]{2,80})',
            r'\[\s*\]\s*([^\n\[\]]{2,80})'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text[:500])
            if matches and len(matches) >= 2:
                for i, txt in enumerate(matches[:5]):
                    choices.append(FieldChoice(
                        letter=chr(ord('a') + i),
                        text=txt.strip(),
                        selected=False
                    ))
                break
        
        return choices
    
    def _create_parents(self, fields: List[FormField], part_num: int):
        """Create parent fields"""
        parent_nums = {f.parent_number for f in fields if f.parent_number}
        existing = {f.number for f in fields}
        
        for pnum in parent_nums:
            if pnum and pnum not in existing:
                fields.append(FormField(
                    number=pnum,
                    label=f"Field {pnum}",
                    field_type="parent",
                    part_number=part_num,
                    is_parent=True
                ))
    
    def _detect_type(self, label: str) -> str:
        """Detect field type"""
        lower = label.lower()
        
        if any(w in lower for w in ["date", "birth", "expire"]):
            return "date"
        elif "email" in lower:
            return "email"
        elif any(w in lower for w in ["phone", "telephone"]):
            return "phone"
        elif "ssn" in lower:
            return "ssn"
        elif any(w in lower for w in ["check", "select"]):
            return "checkbox"
        
        return "text"

# ===== PDF EXTRACTION =====

def extract_pdf_text(pdf_file) -> Tuple[str, int]:
    """Extract text from PDF"""
    try:
        # Try PyMuPDF
        try:
            import fitz
            pdf_file.seek(0)
            doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
            
            text = ""
            for i in range(len(doc)):
                page = doc[i]
                text += f"\n=== PAGE {i+1} ===\n{page.get_text()}"
            
            pages = len(doc)
            doc.close()
            return text, pages
            
        except ImportError:
            # Try PyPDF2
            import PyPDF2
            pdf_file.seek(0)
            reader = PyPDF2.PdfReader(pdf_file)
            
            text = ""
            for i, page in enumerate(reader.pages):
                text += f"\n=== PAGE {i+1} ===\n{page.extract_text()}"
            
            return text, len(reader.pages)
            
    except:
        st.error("Could not read PDF. Install PyPDF2 or pymupdf.")
        return "", 0

# ===== UI COMPONENTS =====

def render_field(field: FormField, key_prefix: str):
    """Render field UI"""
    unique_key = f"{key_prefix}_{field.get_unique_key()}"
    
    # CSS class
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
            st.markdown(
                f'<span class="field-number-badge">{field.number}</span>'
                f'<strong>{field.label}</strong>',
                unsafe_allow_html=True
            )
            
            # Choices
            if field.choices:
                for choice in field.choices:
                    choice.selected = st.checkbox(
                        f"{choice.letter}. {choice.text}",
                        value=choice.selected,
                        key=f"{unique_key}_c_{choice.letter}"
                    )
        
        with col2:
            # Value input
            if not field.is_parent and not field.choices:
                if field.field_type == "date":
                    val = st.date_input("", key=f"{unique_key}_val", label_visibility="collapsed")
                    field.value = str(val) if val else ""
                elif field.field_type == "checkbox":
                    field.value = st.checkbox("", key=f"{unique_key}_val")
                else:
                    field.value = st.text_input(
                        "", value=field.value or "",
                        key=f"{unique_key}_val",
                        label_visibility="collapsed"
                    )
        
        with col3:
            c1, c2 = st.columns(2)
            
            with c1:
                if field.is_mapped:
                    st.success("✓")
                else:
                    if st.button("Map", key=f"{unique_key}_map"):
                        st.session_state[f"map_{unique_key}"] = True
            
            with c2:
                label = "Q✓" if field.in_questionnaire else "Q+"
                if st.button(label, key=f"{unique_key}_q"):
                    field.in_questionnaire = not field.in_questionnaire
                    st.rerun()
        
        # Mapping dialog
        if st.session_state.get(f"map_{unique_key}"):
            st.markdown("---")
            
            c1, c2 = st.columns(2)
            
            with c1:
                obj = st.selectbox(
                    "Object",
                    [""] + list(DB_SCHEMA.keys()),
                    key=f"{unique_key}_obj"
                )
            
            with c2:
                if obj:
                    path = st.selectbox(
                        "Field",
                        [""] + DB_SCHEMA[obj]["fields"],
                        key=f"{unique_key}_path"
                    )
                else:
                    path = ""
            
            if st.button("Apply", key=f"{unique_key}_apply"):
                if obj and path:
                    field.is_mapped = True
                    field.db_object = obj
                    field.db_path = path
                    del st.session_state[f"map_{unique_key}"]
                    st.rerun()
            
            if st.button("Cancel", key=f"{unique_key}_cancel"):
                del st.session_state[f"map_{unique_key}"]
                st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)

# ===== MAIN APP =====

def main():
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>📋 USCIS Form Reader</h1>
        <p>Extract • Map • Export</p>
    </div>
    """, unsafe_allow_html=True)
    
    # State
    if 'form_data' not in st.session_state:
        st.session_state.form_data = None
    if 'extractor' not in st.session_state:
        st.session_state.extractor = FormExtractor()
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 📊 Status")
        
        if st.session_state.form_data and st.session_state.form_data.get("success"):
            data = st.session_state.form_data
            
            st.success(f"Form: {data['form_number']}")
            st.metric("Parts", len(data["parts"]))
            st.metric("Fields", data["stats"]["total_fields"])
        
        if st.button("🔄 Reset", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    
    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📤 Upload", "🔗 Map", "📝 Quest", "💾 Export"
    ])
    
    with tab1:
        render_upload_tab()
    
    with tab2:
        render_map_tab()
    
    with tab3:
        render_quest_tab()
    
    with tab4:
        render_export_tab()

def render_upload_tab():
    """Upload tab"""
    st.markdown("### Upload USCIS Form")
    
    file = st.file_uploader("Choose PDF", type=['pdf'])
    
    if file:
        st.info(f"📄 {file.name}")
        
        if st.button("🚀 Extract", type="primary"):
            with st.spinner("Extracting..."):
                text, pages = extract_pdf_text(file)
                
                if text:
                    data = st.session_state.extractor.extract_form(text)
                    
                    if data["success"]:
                        st.session_state.form_data = data
                        st.success(f"✅ Extracted {data['stats']['total_fields']} fields")
                        
                        with st.expander("Summary"):
                            for part in data["parts"]:
                                st.write(f"**Part {part.number}:** {len(part.fields)} fields")
                else:
                    st.error("Could not read PDF")

def render_map_tab():
    """Map tab"""
    if not st.session_state.form_data:
        st.info("Upload a form first")
        return
    
    st.markdown("### Map Fields")
    
    data = st.session_state.form_data
    
    # Part selector
    part_nums = [p.number for p in data["parts"]]
    sel = st.selectbox(
        "Part",
        part_nums,
        format_func=lambda x: f"Part {x}: {next(p.title for p in data['parts'] if p.number == x)}"
    )
    
    if sel:
        part = next(p for p in data["parts"] if p.number == sel)
        
        # Stats
        stats = part.get_stats()
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Total", stats["total_fields"])
        with c2:
            st.metric("Mapped", stats["mapped_fields"])
        with c3:
            st.metric("Quest", stats["questionnaire_fields"])
        
        st.markdown("---")
        
        # Fields
        for field in part.fields:
            render_field(field, f"map_p{part.number}")

def render_quest_tab():
    """Questionnaire tab"""
    if not st.session_state.form_data:
        st.info("Upload a form first")
        return
    
    st.markdown("### Questionnaire")
    
    data = st.session_state.form_data
    
    # Get quest fields
    quest = []
    for part in data["parts"]:
        for field in part.fields:
            if field.in_questionnaire:
                quest.append((part, field))
    
    if not quest:
        st.info("No fields in questionnaire")
        return
    
    # Display
    current = None
    for part, field in quest:
        if part != current:
            st.markdown(f"#### Part {part.number}")
            current = part
        
        st.markdown(f"**{field.number}. {field.label}**")
        
        key = f"q_{field.get_unique_key()}"
        
        if field.choices:
            for c in field.choices:
                c.selected = st.checkbox(
                    f"{c.letter}. {c.text}",
                    value=c.selected,
                    key=f"{key}_{c.letter}"
                )
        else:
            field.value = st.text_area(
                "",
                value=field.value or "",
                key=key,
                height=70,
                label_visibility="collapsed"
            )
        
        st.markdown("---")

def render_export_tab():
    """Export tab"""
    if not st.session_state.form_data:
        st.info("Upload a form first")
        return
    
    st.markdown("### Export")
    
    data = st.session_state.form_data
    
    c1, c2 = st.columns(2)
    
    with c1:
        st.markdown("#### By Part")
        
        for i, part in enumerate(data["parts"]):
            key = f"exp_p_{i}_{uuid.uuid4().hex[:8]}"
            if st.button(f"Part {part.number}", key=key, use_container_width=True):
                export_part(part, key)
    
    with c2:
        st.markdown("#### All Data")
        
        if st.button("Mapped Fields", key=f"exp_m_{uuid.uuid4().hex[:8]}"):
            export_mapped(data)
        
        if st.button("Questionnaire", key=f"exp_q_{uuid.uuid4().hex[:8]}"):
            export_quest(data)
        
        if st.button("Complete", key=f"exp_a_{uuid.uuid4().hex[:8]}"):
            export_all(data)

def export_part(part: FormPart, key: str):
    """Export part"""
    data = {
        "part": part.number,
        "title": part.title,
        "fields": [f.to_dict() for f in part.fields]
    }
    
    st.download_button(
        "Download",
        json.dumps(data, indent=2),
        f"part_{part.number}.json",
        "application/json",
        key=f"dl_{key}"
    )

def export_mapped(data: Dict):
    """Export mapped"""
    mapped = {}
    
    for part in data["parts"]:
        for field in part.fields:
            if field.is_mapped:
                if field.db_object not in mapped:
                    mapped[field.db_object] = {}
                mapped[field.db_object][field.db_path] = {
                    "field": field.number,
                    "label": field.label,
                    "value": str(field.value) if field.value else ""
                }
    
    st.download_button(
        "Download",
        json.dumps(mapped, indent=2),
        "mapped.json",
        "application/json",
        key=f"dl_m_{uuid.uuid4().hex[:8]}"
    )

def export_quest(data: Dict):
    """Export questionnaire"""
    quest = {}
    
    for part in data["parts"]:
        fields = [f for f in part.fields if f.in_questionnaire]
        if fields:
            quest[f"Part_{part.number}"] = [f.to_dict() for f in fields]
    
    st.download_button(
        "Download",
        json.dumps(quest, indent=2),
        "questionnaire.json",
        "application/json",
        key=f"dl_q_{uuid.uuid4().hex[:8]}"
    )

def export_all(data: Dict):
    """Export all"""
    export = {
        "form": {
            "number": data["form_number"],
            "title": data["form_title"]
        },
        "parts": []
    }
    
    for part in data["parts"]:
        export["parts"].append({
            "number": part.number,
            "title": part.title,
            "fields": [f.to_dict() for f in part.fields]
        })
    
    st.download_button(
        "Download",
        json.dumps(export, indent=2),
        f"{data['form_number']}.json",
        "application/json",
        key=f"dl_a_{uuid.uuid4().hex[:8]}"
    )

if __name__ == "__main__":
    main()
