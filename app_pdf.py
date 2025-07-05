import streamlit as st
import json
import re
import fitz  # PyMuPDF
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict, OrderedDict
import pandas as pd
from dataclasses import dataclass

# Database Object Structure
DB_OBJECTS = {
    "attorney": {
        "attorneyInfo": [
            "firstName", "lastName", "middleName", "workPhone", "mobilePhone", 
            "emailAddress", "faxNumber", "stateBarNumber", "licensingAuthority"
        ],
        "address": [
            "addressStreet", "addressCity", "addressState", "addressZip", 
            "addressCountry"
        ]
    },
    "beneficiary": {
        "Beneficiary": [
            "beneficiaryFirstName", "beneficiaryLastName", "beneficiaryMiddleName",
            "beneficiaryGender", "beneficiaryDateOfBirth", "beneficiarySsn",
            "alienNumber", "beneficiaryCountryOfBirth", "beneficiaryCitizenOfCountry",
            "beneficiaryCellNumber", "beneficiaryHomeNumber", "beneficiaryWorkNumber",
            "beneficiaryPrimaryEmailAddress", "maritalStatus"
        ],
        "HomeAddress": [
            "addressStreet", "addressCity", "addressState", "addressZip", 
            "addressCountry"
        ],
        "MailingAddress": [
            "addressStreet", "addressCity", "addressState", "addressZip", 
            "addressCountry"
        ],
        "PassportDetails": {
            "Passport": [
                "passportNumber", "passportIssueCountry", 
                "passportIssueDate", "passportExpiryDate"
            ]
        },
        "VisaDetails": {
            "Visa": [
                "visaStatus", "visaExpiryDate", "visaNumber"
            ]
        },
        "I94Details": {
            "I94": [
                "i94Number", "i94ArrivalDate", "i94ExpiryDate"
            ]
        }
    },
    "customer": {
        "": [
            "customer_name", "customer_type_of_business", "customer_tax_id"
        ],
        "signatory": [
            "signatory_first_name", "signatory_last_name", "signatory_job_title"
        ],
        "address": [
            "address_street", "address_city", "address_state", "address_zip"
        ]
    }
}

@dataclass
class PDFField:
    """Simple field representation"""
    raw_name: str
    clean_name: str
    part: str
    page: int
    field_type: str
    value: str = ""
    description: str = ""
    item_number: str = ""
    db_mapping: Optional[str] = None
    is_mapped: bool = False
    to_json: bool = False

class SimpleUSCISMapper:
    """Simple USCIS Form Mapper"""
    
    def __init__(self):
        self.init_session_state()
        self.db_paths = self._build_database_paths()
        
    def init_session_state(self):
        """Initialize session state"""
        if 'form_type' not in st.session_state:
            st.session_state.form_type = None
        if 'pdf_fields' not in st.session_state:
            st.session_state.pdf_fields = []
        if 'fields_by_part' not in st.session_state:
            st.session_state.fields_by_part = OrderedDict()
    
    def _build_database_paths(self) -> List[str]:
        """Build list of all database paths"""
        paths = []
        
        for obj_name, obj_structure in DB_OBJECTS.items():
            for key, value in obj_structure.items():
                if isinstance(value, list):
                    if key == "":
                        paths.extend([f"{obj_name}.{field}" for field in value])
                    else:
                        paths.extend([f"{obj_name}.{key}.{field}" for field in value])
                elif isinstance(value, dict):
                    for nested_key, nested_fields in value.items():
                        paths.extend([f"{obj_name}.{key}.{nested_key}.{field}" for field in nested_fields])
        
        return sorted(paths)
    
    def extract_pdf_fields(self, pdf_file) -> Tuple[str, List[PDFField]]:
        """Extract fields from PDF with proper part detection"""
        fields = []
        form_type = None
        
        try:
            pdf_bytes = pdf_file.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            # Detect form type from first page
            first_page_text = doc[0].get_text().upper()
            form_patterns = {
                'I-90': r'FORM\s*I-90|I-90',
                'I-129': r'FORM\s*I-129|I-129',
                'I-130': r'FORM\s*I-130|I-130',
                'I-131': r'FORM\s*I-131|I-131',
                'I-140': r'FORM\s*I-140|I-140',
                'I-485': r'FORM\s*I-485|I-485',
                'I-539': r'FORM\s*I-539|I-539',
                'I-765': r'FORM\s*I-765|I-765',
                'N-400': r'FORM\s*N-400|N-400'
            }
            
            for form, pattern in form_patterns.items():
                if re.search(pattern, first_page_text):
                    form_type = form
                    break
            
            # Extract all widgets with their page info
            all_widgets = []
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_text = page.get_text()
                
                # Detect current part from page text
                current_part = "Part 1"  # Default
                part_matches = re.findall(r'Part\s+(\d+)', page_text, re.IGNORECASE)
                if part_matches:
                    # Use the most common part number on this page
                    current_part = f"Part {max(set(part_matches), key=part_matches.count)}"
                
                for widget in page.widgets():
                    if widget.field_name:
                        # Skip Part 0 fields
                        if "Part 0" in current_part or self._is_part_0_field(widget.field_name, page_text):
                            continue
                        
                        all_widgets.append({
                            'widget': widget,
                            'page': page_num + 1,
                            'part': current_part,
                            'page_text': page_text
                        })
            
            # Process widgets
            field_counters = defaultdict(int)
            
            for widget_info in all_widgets:
                widget = widget_info['widget']
                part = widget_info['part']
                
                # Clean field name
                raw_name = widget.field_name
                clean_name = self._clean_field_name(raw_name)
                
                # Extract item number if present
                item_number = self._extract_item_number(clean_name)
                
                # Generate field ID
                part_num = re.search(r'Part\s*(\d+)', part)
                if part_num:
                    field_counters[part] += 1
                    field_id = f"P{part_num.group(1)}_{field_counters[part]}"
                else:
                    field_id = f"Field_{len(fields) + 1}"
                
                # Get field type
                field_type = self._get_field_type(widget)
                
                # Generate description
                description = self._generate_description(widget, clean_name)
                
                field = PDFField(
                    raw_name=raw_name,
                    clean_name=field_id,
                    part=part,
                    page=widget_info['page'],
                    field_type=field_type,
                    value=widget.field_value or '',
                    description=description,
                    item_number=item_number
                )
                
                fields.append(field)
            
            doc.close()
            
            # Group fields by part
            fields_by_part = OrderedDict()
            for field in fields:
                if field.part not in fields_by_part:
                    fields_by_part[field.part] = []
                fields_by_part[field.part].append(field)
            
            # Sort parts
            sorted_parts = sorted(fields_by_part.keys(), 
                                key=lambda x: int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 999)
            
            st.session_state.fields_by_part = OrderedDict((k, fields_by_part[k]) for k in sorted_parts)
            
        except Exception as e:
            st.error(f"Error extracting PDF: {str(e)}")
            return None, []
        
        return form_type, fields
    
    def _is_part_0_field(self, field_name: str, page_text: str) -> bool:
        """Check if field belongs to Part 0 (attorney section)"""
        field_lower = field_name.lower()
        page_lower = page_text.lower()
        
        # Check for attorney section indicators
        attorney_indicators = [
            "attorney or accredited representative",
            "form g-28",
            "g-28 is attached",
            "attorney or representative"
        ]
        
        return any(indicator in page_lower for indicator in attorney_indicators)
    
    def _clean_field_name(self, field_name: str) -> str:
        """Clean field name"""
        # Remove form prefixes
        patterns = [
            r'form\d*\[\d+\]\.',
            r'#subform\[\d+\]\.',
            r'topmostSubform\[\d+\]\.',
            r'\[\d+\]',
            r'^#'
        ]
        
        clean = field_name
        for pattern in patterns:
            clean = re.sub(pattern, '', clean, flags=re.IGNORECASE)
        
        # Extract last meaningful part
        parts = clean.split('.')
        return parts[-1] if parts else clean
    
    def _extract_item_number(self, field_name: str) -> str:
        """Extract item number from field name"""
        # Look for patterns like Item1, Line2a, etc.
        patterns = [
            r'Item[\s_]*(\d+[a-zA-Z]?)',
            r'Line[\s_]*(\d+[a-zA-Z]?)',
            r'Number[\s_]*(\d+[a-zA-Z]?)',
            r'_(\d+[a-zA-Z]?)$'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, field_name, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return ""
    
    def _get_field_type(self, widget) -> str:
        """Get field type"""
        widget_types = {
            2: "checkbox",
            3: "radio",
            4: "text",
            5: "select",
            7: "signature"
        }
        return widget_types.get(widget.field_type, "text")
    
    def _generate_description(self, widget, clean_name: str) -> str:
        """Generate human-readable description"""
        # Use display name if available
        if widget.field_display and not widget.field_display.startswith('form'):
            return widget.field_display
        
        # Otherwise, make field name readable
        desc = clean_name
        desc = re.sub(r'([a-z])([A-Z])', r'\1 \2', desc)  # CamelCase to spaces
        desc = desc.replace('_', ' ')
        
        # Common replacements
        replacements = {
            'fname': 'First Name',
            'lname': 'Last Name',
            'mname': 'Middle Name',
            'dob': 'Date of Birth',
            'ssn': 'Social Security Number'
        }
        
        desc_lower = desc.lower()
        for key, value in replacements.items():
            if key in desc_lower:
                desc = value
                break
        
        return desc.title()
    
    def generate_typescript(self, fields: List[PDFField]) -> str:
        """Generate TypeScript export"""
        form_name = st.session_state.form_type.replace('-', '') if st.session_state.form_type else 'Form'
        
        # Group fields
        mapped_fields = defaultdict(list)
        json_fields = []
        
        for field in fields:
            if field.is_mapped and field.db_mapping:
                obj = field.db_mapping.split('.')[0]
                mapped_fields[obj].append(field)
            elif field.to_json or not field.is_mapped:
                json_fields.append(field)
        
        # Generate TypeScript
        ts = f"export const {form_name} = {{\n"
        
        # Add mapped fields by object
        for obj, fields_list in mapped_fields.items():
            ts += f"  {obj}Data: {{\n"
            for field in fields_list:
                path = field.db_mapping.replace(f"{obj}.", "")
                ts += f'    "{field.clean_name}": "{path}",\n'
            ts = ts.rstrip(',\n') + '\n'
            ts += "  },\n"
        
        # Add JSON fields
        if json_fields:
            ts += "  questionnaireData: {\n"
            for field in json_fields:
                ts += f'    "{field.clean_name}": {{\n'
                ts += f'      description: "{field.description}",\n'
                ts += f'      type: "{field.field_type}",\n'
                ts += f'      part: "{field.part}",\n'
                if field.item_number:
                    ts += f'      item: "{field.item_number}",\n'
                ts += "    },\n"
            ts = ts.rstrip(',\n') + '\n'
            ts += "  }\n"
        
        ts = ts.rstrip(',\n') + '\n'
        ts += "};\n"
        
        return ts
    
    def generate_json(self, fields: List[PDFField]) -> str:
        """Generate JSON questionnaire"""
        json_fields = [f for f in fields if f.to_json or not f.is_mapped]
        
        # Group by part
        by_part = defaultdict(list)
        for field in json_fields:
            by_part[field.part].append(field)
        
        # Build JSON
        data = {
            "form": st.session_state.form_type,
            "generated": datetime.now().isoformat(),
            "sections": []
        }
        
        for part in sorted(by_part.keys()):
            section = {
                "part": part,
                "fields": []
            }
            
            for field in by_part[part]:
                section["fields"].append({
                    "id": field.clean_name,
                    "description": field.description,
                    "type": field.field_type,
                    "page": field.page,
                    "item": field.item_number if field.item_number else None
                })
            
            data["sections"].append(section)
        
        return json.dumps(data, indent=2)

def render_header():
    """Render header"""
    st.markdown("""
    <style>
        .main-header {
            background: #4f46e5;
            color: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            text-align: center;
        }
        .part-section {
            background: #f9fafb;
            border: 1px solid #e5e7eb;
            padding: 15px;
            margin: 10px 0;
            border-radius: 8px;
        }
        .field-row {
            background: white;
            border: 1px solid #e5e7eb;
            padding: 10px;
            margin: 5px 0;
            border-radius: 4px;
        }
        .field-row:hover {
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .status-badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: bold;
        }
        .mapped { background: #d1fae5; color: #065f46; }
        .json { background: #fef3c7; color: #92400e; }
        .unmapped { background: #fee2e2; color: #991b1b; }
    </style>
    <div class="main-header">
        <h1>Simple USCIS Form Mapper</h1>
        <p>Extract fields by parts → Map to database → Export</p>
    </div>
    """, unsafe_allow_html=True)

def render_upload_section(mapper: SimpleUSCISMapper):
    """Upload and extract fields"""
    st.markdown("## 📤 Upload Form")
    
    uploaded_file = st.file_uploader(
        "Upload USCIS PDF form",
        type=['pdf'],
        help="Upload any USCIS form (I-90, I-129, I-485, etc.)"
    )
    
    if uploaded_file:
        if st.button("Extract Fields", type="primary", use_container_width=True):
            with st.spinner("Extracting fields..."):
                form_type, fields = mapper.extract_pdf_fields(uploaded_file)
                
                if form_type and fields:
                    st.session_state.form_type = form_type
                    st.session_state.pdf_fields = fields
                    st.success(f"✅ Extracted {len(fields)} fields from {form_type}")
                    st.rerun()
                else:
                    st.error("Could not extract fields. Please check the PDF.")
    
    # Show extracted fields
    if st.session_state.pdf_fields:
        st.markdown("---")
        st.markdown("## 📊 Extracted Fields by Part")
        
        # Summary
        total_fields = len(st.session_state.pdf_fields)
        total_parts = len(st.session_state.fields_by_part)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Form", st.session_state.form_type)
        with col2:
            st.metric("Total Fields", total_fields)
        with col3:
            st.metric("Parts", total_parts)
        
        # Show fields by part
        for part, fields in st.session_state.fields_by_part.items():
            st.markdown(f'<div class="part-section">', unsafe_allow_html=True)
            st.markdown(f"### {part} ({len(fields)} fields)")
            
            # Create simple table
            for i, field in enumerate(fields):
                col1, col2, col3, col4 = st.columns([1, 3, 2, 1])
                
                with col1:
                    st.write(field.clean_name)
                
                with col2:
                    st.write(field.description)
                    if field.item_number:
                        st.caption(f"Item {field.item_number}")
                
                with col3:
                    st.write(f"Type: {field.field_type}")
                    st.caption(f"Page {field.page}")
                
                with col4:
                    if field.is_mapped:
                        st.markdown('<span class="status-badge mapped">Mapped</span>', unsafe_allow_html=True)
                    elif field.to_json:
                        st.markdown('<span class="status-badge json">JSON</span>', unsafe_allow_html=True)
                    else:
                        st.markdown('<span class="status-badge unmapped">Unmapped</span>', unsafe_allow_html=True)
            
            st.markdown('</div>', unsafe_allow_html=True)

def render_mapping_section(mapper: SimpleUSCISMapper):
    """Map fields to database"""
    if not st.session_state.pdf_fields:
        st.info("Please upload and extract a form first")
        return
    
    st.markdown("## 🎯 Field Mapping")
    
    # Quick actions
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("All Unmapped → JSON", type="secondary"):
            count = 0
            for field in st.session_state.pdf_fields:
                if not field.is_mapped:
                    field.to_json = True
                    count += 1
            st.success(f"Moved {count} fields to JSON")
            st.rerun()
    
    with col2:
        if st.button("Reset All", type="secondary"):
            for field in st.session_state.pdf_fields:
                field.is_mapped = False
                field.to_json = False
                field.db_mapping = None
            st.rerun()
    
    # Stats
    total = len(st.session_state.pdf_fields)
    mapped = sum(1 for f in st.session_state.pdf_fields if f.is_mapped)
    json_count = sum(1 for f in st.session_state.pdf_fields if f.to_json)
    unmapped = total - mapped - json_count
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total", total)
    with col2:
        st.metric("Mapped", mapped)
    with col3:
        st.metric("To JSON", json_count)
    with col4:
        st.metric("Unmapped", unmapped)
    
    # Part selector
    parts = ["All"] + list(st.session_state.fields_by_part.keys())
    selected_part = st.selectbox("View Part", parts)
    
    # Get fields to display
    if selected_part == "All":
        display_fields = st.session_state.pdf_fields
    else:
        display_fields = st.session_state.fields_by_part.get(selected_part, [])
    
    # Display fields for mapping
    st.markdown("---")
    
    for field in display_fields:
        col1, col2, col3, col4 = st.columns([2, 3, 3, 1])
        
        with col1:
            st.write(f"**{field.clean_name}**")
            st.caption(f"{field.part} • {field.field_type}")
        
        with col2:
            st.write(field.description)
            if field.item_number:
                st.caption(f"Item {field.item_number}")
        
        with col3:
            # Mapping options
            if field.is_mapped:
                st.info(f"→ {field.db_mapping}")
            elif field.to_json:
                st.warning("→ JSON Questionnaire")
            else:
                options = ["Select..."] + ["To JSON"] + mapper.db_paths
                selected = st.selectbox(
                    "Map to",
                    options,
                    key=f"map_{field.clean_name}",
                    label_visibility="collapsed"
                )
                
                if selected == "To JSON":
                    field.to_json = True
                    st.rerun()
                elif selected != "Select...":
                    field.db_mapping = selected
                    field.is_mapped = True
                    st.rerun()
        
        with col4:
            if field.is_mapped or field.to_json:
                if st.button("Reset", key=f"reset_{field.clean_name}"):
                    field.is_mapped = False
                    field.to_json = False
                    field.db_mapping = None
                    st.rerun()

def render_export_section(mapper: SimpleUSCISMapper):
    """Export mappings"""
    if not st.session_state.pdf_fields:
        st.info("Please map fields first")
        return
    
    st.markdown("## 📥 Export")
    
    # Summary
    fields = st.session_state.pdf_fields
    mapped = sum(1 for f in fields if f.is_mapped)
    json_count = sum(1 for f in fields if f.to_json)
    unmapped = len(fields) - mapped - json_count
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Database Mapped", mapped)
    with col2:
        st.metric("To JSON", json_count)
    with col3:
        st.metric("Unmapped", unmapped)
    
    if unmapped > 0:
        st.warning(f"⚠️ {unmapped} fields are unmapped. They will be added to JSON on export.")
    
    # Export buttons
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Generate TypeScript", type="primary", use_container_width=True):
            # Auto-add unmapped to JSON
            for field in fields:
                if not field.is_mapped and not field.to_json:
                    field.to_json = True
            
            ts_content = mapper.generate_typescript(fields)
            
            st.download_button(
                "📥 Download TypeScript",
                ts_content,
                f"{st.session_state.form_type.replace('-', '')}.ts",
                "text/plain"
            )
    
    with col2:
        if st.button("Generate JSON", type="primary", use_container_width=True):
            # Auto-add unmapped to JSON
            for field in fields:
                if not field.is_mapped and not field.to_json:
                    field.to_json = True
            
            json_content = mapper.generate_json(fields)
            
            st.download_button(
                "📥 Download JSON",
                json_content,
                f"{st.session_state.form_type.lower()}-questionnaire.json",
                "application/json"
            )
    
    # Preview
    st.markdown("### Preview")
    
    tab1, tab2 = st.tabs(["TypeScript", "JSON"])
    
    with tab1:
        ts_preview = mapper.generate_typescript(fields[:10])
        st.code(ts_preview, language="typescript")
    
    with tab2:
        json_fields = [f for f in fields[:10] if f.to_json or not f.is_mapped]
        if json_fields:
            preview_data = {
                "form": st.session_state.form_type,
                "sample_fields": [
                    {
                        "id": f.clean_name,
                        "description": f.description,
                        "part": f.part
                    } for f in json_fields[:5]
                ]
            }
            st.json(preview_data)

def main():
    st.set_page_config(
        page_title="Simple USCIS Form Mapper",
        page_icon="📄",
        layout="wide"
    )
    
    # Initialize mapper
    mapper = SimpleUSCISMapper()
    
    # Render header
    render_header()
    
    # Create tabs
    tab1, tab2, tab3 = st.tabs(["📤 Upload & Extract", "🎯 Map Fields", "📥 Export"])
    
    with tab1:
        render_upload_section(mapper)
    
    with tab2:
        render_mapping_section(mapper)
    
    with tab3:
        render_export_section(mapper)

if __name__ == "__main__":
    main()
