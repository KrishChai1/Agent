#!/usr/bin/env python3
"""
Streamlined USCIS Form Reader
Focuses on accurate extraction without over-interpretation
"""

import os
import json
import re
import time
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, OrderedDict

import streamlit as st

# Try imports
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    fitz = None

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None

# Page config
st.set_page_config(
    page_title="USCIS Form Reader",
    page_icon="📄",
    layout="wide"
)

# CSS
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 2rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        text-align: center;
    }
    .field-card {
        background: white;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        transition: all 0.2s;
    }
    .field-card:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    .mapped {
        border-left: 4px solid #4CAF50;
    }
    .questionnaire {
        border-left: 4px solid #FFC107;
    }
    .unmapped {
        border-left: 4px solid #f44336;
    }
    .part-header {
        background: #2196F3;
        color: white;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

@dataclass
class Field:
    """Simple field representation"""
    item_number: str
    label: str
    type: str = "text"
    value: str = ""
    page: int = 1
    part: str = "Part 1"
    parent_item: Optional[str] = None
    is_questionnaire: bool = False
    json_path: Optional[str] = None
    
    @property
    def field_id(self):
        return f"{self.part}_{self.item_number}".replace(" ", "_")

@dataclass 
class FormData:
    """Form structure"""
    form_number: str
    form_title: str
    parts: Dict[str, List[Field]] = field(default_factory=OrderedDict)
    
    def add_field(self, part: str, field: Field):
        if part not in self.parts:
            self.parts[part] = []
        self.parts[part].append(field)
    
    def get_stats(self):
        total = sum(len(fields) for fields in self.parts.values())
        mapped = sum(1 for fields in self.parts.values() for f in fields if f.json_path)
        quest = sum(1 for fields in self.parts.values() for f in fields if f.is_questionnaire)
        return {"total": total, "mapped": mapped, "questionnaire": quest}

# JSON Structures
DEFAULT_JSON_STRUCTURES = {
    "beneficiary": {
        "personalInfo": {
            "familyName": "",
            "givenName": "",
            "middleName": "",
            "alienNumber": "",
            "uscisAccountNumber": "",
            "dateOfBirth": "",
            "ssn": "",
            "countryOfBirth": "",
            "countryOfCitizenship": ""
        },
        "address": {
            "inCareOf": "",
            "streetNumber": "",
            "apartment": "",
            "city": "",
            "state": "",
            "zipCode": ""
        },
        "contactInfo": {
            "daytimePhone": "",
            "mobilePhone": "",
            "email": ""
        },
        "entryInfo": {
            "dateOfLastArrival": "",
            "i94Number": "",
            "passportNumber": "",
            "travelDocNumber": "",
            "countryOfIssuance": "",
            "expirationDate": "",
            "currentStatus": "",
            "statusExpirationDate": ""
        }
    }
}

# Field mappings for common fields
FIELD_MAPPINGS = {
    # Part 1 mappings
    "1": None,  # Group field - Your Full Legal Name
    "Family Name": "beneficiary.personalInfo.familyName",
    "Given Name": "beneficiary.personalInfo.givenName", 
    "Middle Name": "beneficiary.personalInfo.middleName",
    "2": "beneficiary.personalInfo.alienNumber",
    "3": "beneficiary.personalInfo.uscisAccountNumber",
    "4": None,  # Group field - Mailing Address
    "In Care Of Name": "beneficiary.address.inCareOf",
    "Street Number and Name": "beneficiary.address.streetNumber",
    "Apt. Ste. Flr.": "beneficiary.address.apartment",
    "City or Town": "beneficiary.address.city",
    "State": "beneficiary.address.state",
    "ZIP Code": "beneficiary.address.zipCode",
    "5": None,  # Yes/No question
    "7": "beneficiary.personalInfo.countryOfBirth",
    "8": "beneficiary.personalInfo.countryOfCitizenship",
    "9": "beneficiary.personalInfo.dateOfBirth",
    "10": "beneficiary.personalInfo.ssn",
    "11": None,  # Group field - Entry info
    "Date of Last Arrival": "beneficiary.entryInfo.dateOfLastArrival",
    "Form I-94": "beneficiary.entryInfo.i94Number",
    "Passport Number": "beneficiary.entryInfo.passportNumber",
    "12": "beneficiary.entryInfo.currentStatus",
    
    # Part 5 mappings
    "Applicant's Daytime Telephone": "beneficiary.contactInfo.daytimePhone",
    "Applicant's Mobile Telephone": "beneficiary.contactInfo.mobilePhone",
    "Applicant's Email": "beneficiary.contactInfo.email"
}

def natural_sort_key(item_number: str) -> tuple:
    """Natural sorting for item numbers like 1, 1a, 2, 10, 10a"""
    if not item_number:
        return (999,)
    
    match = re.match(r'^(\d+)([a-z])?', item_number.lower())
    if match:
        num = int(match.group(1))
        letter = match.group(2) or ''
        return (num, letter)
    return (999, item_number)

class FormExtractor:
    """Simplified form extractor"""
    
    def __init__(self):
        self.doc = None
        self.form_data = None
    
    def extract(self, pdf_file) -> FormData:
        """Extract form data from PDF"""
        pdf_bytes = pdf_file.read()
        self.doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        # Identify form
        form_info = self._identify_form()
        self.form_data = FormData(
            form_number=form_info['number'],
            form_title=form_info['title']
        )
        
        # Extract fields
        self._extract_fields()
        
        self.doc.close()
        return self.form_data
    
    def _identify_form(self) -> Dict:
        """Identify form type"""
        first_page_text = self.doc[0].get_text().upper()
        
        forms = {
            'I-539': 'Application to Extend/Change Nonimmigrant Status',
            'I-129': 'Petition for a Nonimmigrant Worker',
            'I-485': 'Application to Register Permanent Residence',
            'I-765': 'Application for Employment Authorization'
        }
        
        for form_num, title in forms.items():
            if form_num in first_page_text:
                return {"number": form_num, "title": title}
        
        return {"number": "Unknown", "title": "Unknown Form"}
    
    def _extract_fields(self):
        """Extract fields from form"""
        for page_num, page in enumerate(self.doc):
            page_text = page.get_text()
            
            # Find current part
            part_match = re.search(r'Part\s+(\d+)', page_text)
            current_part = f"Part {part_match.group(1)}" if part_match else "Part 1"
            
            # Extract text fields with patterns
            self._extract_text_fields(page_text, page_num + 1, current_part)
            
            # Extract form widgets
            self._extract_widgets(page, page_num + 1, current_part)
    
    def _extract_text_fields(self, text: str, page: int, part: str):
        """Extract fields from text using patterns"""
        lines = text.split('\n')
        
        # Pattern for numbered items
        item_pattern = re.compile(r'^(\d+[a-z]?)\.\s+(.+?)$')
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Check for item number
            match = item_pattern.match(line)
            if match:
                item_num = match.group(1)
                label = match.group(2)
                
                # Determine field type
                field_type = self._determine_type(label, lines, i)
                
                # Create field
                field = Field(
                    item_number=item_num,
                    label=label,
                    type=field_type,
                    page=page,
                    part=part,
                    is_questionnaire=(field_type in ["checkbox", "radio"])
                )
                
                # Check if it's a compound field (like name or address)
                if self._is_compound_field(label, lines, i):
                    # Add parent field
                    self.form_data.add_field(part, field)
                    
                    # Extract sub-fields
                    sub_fields = self._extract_sub_fields(lines, i + 1, item_num)
                    for sub_field in sub_fields:
                        sub_field.page = page
                        sub_field.part = part
                        self.form_data.add_field(part, sub_field)
                    
                    i += len(sub_fields) + 1
                    continue
                else:
                    self.form_data.add_field(part, field)
            
            i += 1
    
    def _is_compound_field(self, label: str, lines: List[str], index: int) -> bool:
        """Check if field has sub-components"""
        # Check if next line has field labels without numbers
        if index + 1 < len(lines):
            next_line = lines[index + 1].strip()
            # Look for patterns like "Family Name (Last Name)" without item numbers
            if any(keyword in next_line for keyword in ['Family Name', 'Given Name', 'Street Number']):
                return True
        return False
    
    def _extract_sub_fields(self, lines: List[str], start: int, parent_num: str) -> List[Field]:
        """Extract sub-fields for compound fields"""
        sub_fields = []
        
        # For name fields
        name_patterns = [
            ('Family Name (Last Name)', 'familyName'),
            ('Given Name (First Name)', 'givenName'),
            ('Middle Name (if applicable)', 'middleName'),
            ('Middle Name', 'middleName')
        ]
        
        # For address fields
        address_patterns = [
            ('In Care Of Name', 'inCareOf'),
            ('Street Number and Name', 'streetNumber'),
            ('Apt. Ste. Flr.', 'apartment'),
            ('City or Town', 'city'),
            ('State', 'state'),
            ('ZIP Code', 'zipCode')
        ]
        
        # Check next few lines
        for i in range(start, min(start + 10, len(lines))):
            line = lines[i].strip()
            if not line or re.match(r'^\d+\.', line):  # Stop at next numbered item
                break
            
            # Check patterns
            for pattern, field_key in name_patterns + address_patterns:
                if pattern in line:
                    sub_fields.append(Field(
                        item_number=f"{parent_num}-{field_key}",
                        label=pattern,
                        type="text",
                        parent_item=parent_num
                    ))
                    break
        
        return sub_fields
    
    def _extract_widgets(self, page, page_num: int, part: str):
        """Extract form widgets"""
        widgets = page.widgets()
        if not widgets:
            return
        
        for widget in widgets:
            if not widget:
                continue
            
            field_name = widget.field_name if hasattr(widget, 'field_name') else ""
            if not field_name:
                continue
            
            # Extract item number from field name
            item_match = re.search(r'(\d+[a-z]?)', field_name)
            item_num = item_match.group(1) if item_match else f"widget_{len(self.form_data.parts.get(part, []))}"
            
            # Determine type
            widget_type = widget.field_type if hasattr(widget, 'field_type') else 4
            type_map = {2: "checkbox", 3: "radio", 4: "text", 5: "dropdown", 7: "signature"}
            field_type = type_map.get(widget_type, "text")
            
            # Create field
            field = Field(
                item_number=item_num,
                label=self._clean_field_name(field_name),
                type=field_type,
                page=page_num,
                part=part,
                is_questionnaire=(field_type in ["checkbox", "radio"])
            )
            
            # Check if already exists
            existing = [f for f in self.form_data.parts.get(part, []) if f.item_number == item_num]
            if not existing:
                self.form_data.add_field(part, field)
    
    def _determine_type(self, label: str, lines: List[str], index: int) -> str:
        """Determine field type from context"""
        label_lower = label.lower()
        
        # Questions are usually checkboxes
        if any(label_lower.startswith(q) for q in ['are you', 'have you', 'is ', 'do you']):
            return "checkbox"
        
        # Check for Yes/No pattern
        if index + 1 < len(lines):
            next_line = lines[index + 1].strip().lower()
            if 'yes' in next_line and 'no' in next_line:
                return "checkbox"
        
        # Dates
        if any(word in label_lower for word in ['date', 'expir']):
            return "date"
        
        # Numbers
        if any(word in label_lower for word in ['number', 'ssn', 'a-number']):
            return "number"
        
        # Signatures
        if 'signature' in label_lower:
            return "signature"
        
        return "text"
    
    def _clean_field_name(self, name: str) -> str:
        """Clean widget field name"""
        # Remove form prefixes
        name = re.sub(r'(topmostSubform|form1|Page\d+)\[0\]\.', '', name)
        name = re.sub(r'\[0\]', '', name)
        
        # Convert to readable format
        name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
        name = name.replace('_', ' ').replace('-', ' ')
        
        return name.strip()

def render_field(field: Field, idx: int, form_data: FormData):
    """Render a field card"""
    status_class = "mapped" if field.json_path else ("questionnaire" if field.is_questionnaire else "unmapped")
    
    with st.container():
        st.markdown(f'<div class="field-card {status_class}">', unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([2, 3, 1])
        
        with col1:
            if field.parent_item:
                st.caption(f"↳ {field.item_number}")
            else:
                st.markdown(f"**{field.item_number}.** {field.label}")
            
            st.caption(f"Type: {field.type}")
        
        with col2:
            if field.type in ["text", "number", "date"] and not field.is_questionnaire:
                # JSON mapping dropdown
                options = ["-- Not Mapped --", "📋 Questionnaire"]
                
                # Add JSON paths
                for path, json_path in FIELD_MAPPINGS.items():
                    if json_path:
                        options.append(json_path)
                
                current = field.json_path if field.json_path else "-- Not Mapped --"
                if field.is_questionnaire:
                    current = "📋 Questionnaire"
                
                selected = st.selectbox(
                    "Map to",
                    options,
                    index=options.index(current) if current in options else 0,
                    key=f"map_{field.field_id}_{idx}",
                    label_visibility="collapsed"
                )
                
                if selected != current:
                    if selected == "📋 Questionnaire":
                        field.is_questionnaire = True
                        field.json_path = None
                    elif selected != "-- Not Mapped --":
                        field.json_path = selected
                        field.is_questionnaire = False
                    st.rerun()
            else:
                include = st.checkbox(
                    "Include in Questionnaire",
                    value=field.is_questionnaire,
                    key=f"quest_{field.field_id}_{idx}"
                )
                if include != field.is_questionnaire:
                    field.is_questionnaire = include
                    st.rerun()
        
        with col3:
            if field.json_path:
                st.success("✅ Mapped")
            elif field.is_questionnaire:
                st.info("📋 Quest")
            else:
                st.warning("❌ Unmapped")
        
        st.markdown('</div>', unsafe_allow_html=True)

def generate_exports(form_data: FormData) -> Tuple[str, str]:
    """Generate TypeScript and JSON exports"""
    # TypeScript
    ts_code = f"export const {form_data.form_number.replace('-', '')} = {{\n"
    ts_code += f'  formname: "{form_data.form_number}",\n'
    ts_code += '  customerData: {},\n'
    ts_code += '  beneficiaryData: {\n'
    
    # Add mapped fields
    for part_name, fields in form_data.parts.items():
        for field in fields:
            if field.json_path and 'beneficiary' in field.json_path:
                path_parts = field.json_path.split('.')
                if len(path_parts) >= 3:
                    ts_code += f'    "{field.field_id}": "{field.json_path}:TextBox",\n'
    
    ts_code += '  },\n'
    ts_code += '  questionnaireData: {\n'
    
    # Add questionnaire fields
    for part_name, fields in form_data.parts.items():
        for field in fields:
            if field.is_questionnaire:
                ts_code += f'    "{field.field_id}": "{field.label}",\n'
    
    ts_code += '  },\n'
    ts_code += '  defaultData: null,\n'
    ts_code += f'  pdfName: "{form_data.form_number}"\n'
    ts_code += '};\n'
    
    # JSON for questionnaire
    controls = []
    for part_name, fields in form_data.parts.items():
        part_fields = [f for f in fields if f.is_questionnaire]
        if part_fields:
            # Add part header
            controls.append({
                "name": f"{part_name}_title",
                "label": part_name,
                "type": "title",
                "style": {"col": "12"}
            })
            
            # Add fields
            for field in sorted(part_fields, key=lambda f: natural_sort_key(f.item_number)):
                controls.append({
                    "name": field.field_id,
                    "label": f"{field.item_number}. {field.label}",
                    "type": "colorSwitch" if field.type == "checkbox" else field.type,
                    "validators": {"required": False},
                    "style": {"col": "6" if field.parent_item else "12"}
                })
    
    json_code = json.dumps({"controls": controls}, indent=2)
    
    return ts_code, json_code

# Main app
def main():
    st.markdown('<div class="main-header"><h1>📄 USCIS Form Reader</h1><p>Streamlined form field extraction and mapping</p></div>', 
               unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("## ℹ️ About")
        st.info("""
        This tool extracts fields from USCIS forms and allows you to:
        - Map fields to JSON structure
        - Mark fields for questionnaire
        - Export TypeScript and JSON
        """)
        
        if st.session_state.get('form_data'):
            stats = st.session_state.form_data.get_stats()
            st.markdown("### 📊 Statistics")
            st.metric("Total Fields", stats['total'])
            st.metric("Mapped", stats['mapped'])
            st.metric("Questionnaire", stats['questionnaire'])
    
    # Main content
    tabs = st.tabs(["📤 Upload", "🎯 Map Fields", "📥 Export"])
    
    with tabs[0]:
        st.markdown("### Upload USCIS Form")
        
        uploaded_file = st.file_uploader(
            "Choose a PDF form",
            type=['pdf'],
            help="Upload any USCIS form (I-539, I-129, etc.)"
        )
        
        if uploaded_file:
            if st.button("🚀 Extract Fields", type="primary"):
                with st.spinner("Extracting fields..."):
                    extractor = FormExtractor()
                    form_data = extractor.extract(uploaded_file)
                    st.session_state.form_data = form_data
                    
                    st.success(f"✅ Extracted {form_data.get_stats()['total']} fields from {form_data.form_number}")
                    
                    # Show summary
                    with st.expander("📊 Extraction Summary", expanded=True):
                        for part_name in form_data.parts:
                            fields = form_data.parts[part_name]
                            st.write(f"**{part_name}**: {len(fields)} fields")
    
    with tabs[1]:
        if form_data := st.session_state.get('form_data'):
            st.markdown("### Map Fields to JSON Structure")
            
            # Part selector
            part_names = list(form_data.parts.keys())
            selected_part = st.selectbox("Select Part", part_names)
            
            if selected_part:
                fields = form_data.parts[selected_part]
                
                st.markdown(f'<div class="part-header"><h3>{selected_part}</h3><p>{len(fields)} fields</p></div>', 
                           unsafe_allow_html=True)
                
                # Render fields sorted by item number
                for idx, field in enumerate(sorted(fields, key=lambda f: natural_sort_key(f.item_number))):
                    render_field(field, idx, form_data)
        else:
            st.info("👈 Please upload a form first")
    
    with tabs[2]:
        if form_data := st.session_state.get('form_data'):
            st.markdown("### Export Options")
            
            col1, col2 = st.columns(2)
            
            ts_code, json_code = generate_exports(form_data)
            
            with col1:
                st.markdown("#### TypeScript Export")
                st.download_button(
                    "⬇️ Download TypeScript",
                    ts_code,
                    f"{form_data.form_number}.ts",
                    mime="text/typescript"
                )
                with st.expander("Preview"):
                    st.code(ts_code, language="typescript")
            
            with col2:
                st.markdown("#### JSON Export")
                st.download_button(
                    "⬇️ Download JSON",
                    json_code,
                    f"{form_data.form_number}-questionnaire.json",
                    mime="application/json"
                )
                with st.expander("Preview"):
                    st.code(json_code, language="json")
        else:
            st.info("👈 Please upload a form first")

if __name__ == "__main__":
    main()
