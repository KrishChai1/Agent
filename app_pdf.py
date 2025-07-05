import streamlit as st
import json
import re
import fitz  # PyMuPDF
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict, OrderedDict
import pandas as pd
from dataclasses import dataclass

# Database Object Structure for mapping
DB_OBJECTS = {
    "attorney": {
        "attorneyInfo": [
            "firstName", "lastName", "middleName", "workPhone", "mobilePhone", 
            "emailAddress", "faxNumber", "stateBarNumber", "licensingAuthority"
        ],
        "address": [
            "addressStreet", "addressCity", "addressState", "addressZip", "addressCountry"
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
            "addressStreet", "addressCity", "addressState", "addressZip", "addressCountry"
        ],
        "MailingAddress": [
            "addressStreet", "addressCity", "addressState", "addressZip", "addressCountry"
        ],
        "PassportDetails": {
            "Passport": [
                "passportNumber", "passportIssueCountry", "passportIssueDate", "passportExpiryDate"
            ]
        },
        "VisaDetails": {
            "Visa": ["visaStatus", "visaExpiryDate", "visaNumber"]
        },
        "I94Details": {
            "I94": ["i94Number", "i94ArrivalDate", "i94ExpiryDate"]
        }
    },
    "customer": {
        "": ["customer_name", "customer_type_of_business", "customer_tax_id"],
        "signatory": ["signatory_first_name", "signatory_last_name", "signatory_job_title"],
        "address": ["address_street", "address_city", "address_state", "address_zip"]
    }
}

@dataclass
class ExtractedField:
    """Represents a field extracted from PDF"""
    field_name: str          # Original PDF field name
    field_id: str           # Clean ID like P1_1, P1_2
    part: str               # Part 1, Part 2, etc.
    page: int               # Page number
    field_type: str         # text, checkbox, radio, etc.
    field_value: str        # Current value if any
    description: str        # Human-readable description
    rect: tuple            # Position on page (x0, y0, x1, y1)
    db_mapping: Optional[str] = None  # Database path if mapped
    is_mapped: bool = False
    to_questionnaire: bool = False

class PDFFieldExtractor:
    """Accurate PDF field extractor for USCIS forms"""
    
    def __init__(self):
        self.init_session_state()
        self.db_paths = self._build_database_paths()
    
    def init_session_state(self):
        """Initialize session state"""
        if 'extracted_fields' not in st.session_state:
            st.session_state.extracted_fields = []
        if 'fields_by_part' not in st.session_state:
            st.session_state.fields_by_part = OrderedDict()
        if 'form_info' not in st.session_state:
            st.session_state.form_info = {}
    
    def _build_database_paths(self) -> List[str]:
        """Build flat list of all database paths"""
        paths = []
        
        for obj_name, structure in DB_OBJECTS.items():
            for key, fields in structure.items():
                if isinstance(fields, list):
                    if key == "":
                        for field in fields:
                            paths.append(f"{obj_name}.{field}")
                    else:
                        for field in fields:
                            paths.append(f"{obj_name}.{key}.{field}")
                elif isinstance(fields, dict):
                    for sub_key, sub_fields in fields.items():
                        for field in sub_fields:
                            paths.append(f"{obj_name}.{key}.{sub_key}.{field}")
        
        return sorted(paths)
    
    def extract_from_pdf(self, pdf_file) -> bool:
        """Extract all fields from uploaded PDF"""
        try:
            # Reset state
            st.session_state.extracted_fields = []
            st.session_state.fields_by_part = OrderedDict()
            
            # Read PDF
            pdf_bytes = pdf_file.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            # Detect form type
            form_info = self._detect_form_type(doc)
            st.session_state.form_info = form_info
            
            # Extract all fields with their parts
            all_fields = []
            
            # First, find where Part 1 starts
            part1_page = 0
            for page_num in range(len(doc)):
                page_text = doc[page_num].get_text()
                if re.search(r'Part\s+1\b', page_text, re.IGNORECASE):
                    part1_page = page_num
                    break
            
            # Extract fields starting from Part 1
            current_part = None
            field_counter = defaultdict(int)
            
            for page_num in range(part1_page, len(doc)):
                page = doc[page_num]
                page_text = page.get_text()
                
                # Detect current part from page
                part_match = re.search(r'Part\s+(\d+)\b', page_text, re.IGNORECASE)
                if part_match:
                    current_part = f"Part {part_match.group(1)}"
                
                # Skip if we haven't found Part 1 yet
                if not current_part:
                    continue
                
                # Extract widgets from this page
                widgets = page.widgets()
                
                for widget in widgets:
                    if not widget.field_name:
                        continue
                    
                    # Clean field name
                    field_name = widget.field_name
                    
                    # Get field properties
                    field_type = self._get_field_type(widget.field_type)
                    field_value = widget.field_value or ""
                    rect = widget.rect
                    
                    # Generate field ID
                    part_num = re.search(r'(\d+)', current_part).group(1)
                    field_counter[current_part] += 1
                    field_id = f"P{part_num}_{field_counter[current_part]}"
                    
                    # Generate description
                    description = self._generate_description(field_name, widget.field_display)
                    
                    # Create field object
                    field = ExtractedField(
                        field_name=field_name,
                        field_id=field_id,
                        part=current_part,
                        page=page_num + 1,
                        field_type=field_type,
                        field_value=field_value,
                        description=description,
                        rect=(rect.x0, rect.y0, rect.x1, rect.y1)
                    )
                    
                    all_fields.append(field)
            
            doc.close()
            
            # Store fields
            st.session_state.extracted_fields = all_fields
            
            # Group by part
            for field in all_fields:
                if field.part not in st.session_state.fields_by_part:
                    st.session_state.fields_by_part[field.part] = []
                st.session_state.fields_by_part[field.part].append(field)
            
            # Sort parts naturally
            sorted_parts = sorted(st.session_state.fields_by_part.keys(), 
                                key=lambda x: int(re.search(r'\d+', x).group()))
            st.session_state.fields_by_part = OrderedDict(
                (part, st.session_state.fields_by_part[part]) for part in sorted_parts
            )
            
            return True
            
        except Exception as e:
            st.error(f"Error extracting PDF: {str(e)}")
            return False
    
    def _detect_form_type(self, doc) -> dict:
        """Detect form type from PDF"""
        first_page_text = doc[0].get_text().upper()
        
        # Common USCIS forms
        forms = {
            'I-90': 'Application to Replace Permanent Resident Card',
            'I-129': 'Petition for a Nonimmigrant Worker',
            'I-130': 'Petition for Alien Relative',
            'I-131': 'Application for Travel Document',
            'I-140': 'Immigrant Petition for Alien Workers',
            'I-485': 'Application to Register Permanent Residence',
            'I-539': 'Application To Extend/Change Nonimmigrant Status',
            'I-765': 'Application for Employment Authorization',
            'N-400': 'Application for Naturalization'
        }
        
        detected_form = None
        for form_number, form_title in forms.items():
            if form_number in first_page_text:
                detected_form = form_number
                break
        
        return {
            'form_number': detected_form or 'Unknown',
            'form_title': forms.get(detected_form, 'Unknown Form'),
            'total_pages': len(doc)
        }
    
    def _get_field_type(self, widget_type: int) -> str:
        """Convert widget type to field type"""
        types = {
            1: "button",
            2: "checkbox", 
            3: "radio",
            4: "text",
            5: "dropdown",
            6: "list",
            7: "signature"
        }
        return types.get(widget_type, "text")
    
    def _generate_description(self, field_name: str, display_name: str) -> str:
        """Generate human-readable description"""
        # Use display name if available
        if display_name and display_name.strip():
            return display_name.strip()
        
        # Otherwise clean up field name
        # Remove common prefixes
        clean = field_name
        prefixes = ['form[0].', '#subform[0].', 'Page1[0].', 'Part']
        for prefix in prefixes:
            if clean.startswith(prefix):
                clean = clean[len(prefix):]
        
        # Extract last component
        if '.' in clean:
            clean = clean.split('.')[-1]
        
        # Remove brackets and numbers
        clean = re.sub(r'\[\d+\]', '', clean)
        
        # Convert to readable format
        clean = clean.replace('_', ' ')
        clean = re.sub(r'([a-z])([A-Z])', r'\1 \2', clean)
        
        return clean.strip()
    
    def generate_typescript(self, fields: List[ExtractedField]) -> str:
        """Generate TypeScript export"""
        form_name = st.session_state.form_info.get('form_number', 'Form').replace('-', '')
        
        # Group fields by mapping type
        db_fields = defaultdict(list)
        questionnaire_fields = []
        
        for field in fields:
            if field.is_mapped and field.db_mapping:
                obj = field.db_mapping.split('.')[0]
                db_fields[obj].append(field)
            else:
                questionnaire_fields.append(field)
        
        # Build TypeScript
        ts = f"// {st.session_state.form_info.get('form_number', 'Form')} Field Mappings\n"
        ts += f"// Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        ts += f"export const {form_name} = {{\n"
        
        # Add database mappings
        for obj, fields_list in sorted(db_fields.items()):
            ts += f"  {obj}Data: {{\n"
            for field in fields_list:
                path = field.db_mapping.replace(f"{obj}.", "")
                field_type = ":TextBox" if field.field_type == "text" else f":{field.field_type.title()}Box"
                ts += f'    "{field.field_id}{field_type}": "{path}",\n'
            ts = ts.rstrip(',\n') + '\n'
            ts += "  },\n"
        
        # Add questionnaire fields
        if questionnaire_fields:
            ts += "  questionnaireData: {\n"
            for field in questionnaire_fields:
                ts += f'    "{field.field_id}": {{\n'
                ts += f'      description: "{field.description}",\n'
                ts += f'      fieldType: "{field.field_type}",\n'
                ts += f'      part: "{field.part}",\n'
                ts += f'      page: {field.page},\n'
                ts += f'      required: true\n'
                ts += "    },\n"
            ts = ts.rstrip(',\n') + '\n'
            ts += "  }\n"
        
        ts = ts.rstrip(',\n') + '\n'
        ts += "};\n"
        
        return ts
    
    def generate_questionnaire_json(self, fields: List[ExtractedField]) -> str:
        """Generate JSON for questionnaire fields"""
        questionnaire_fields = [f for f in fields if not f.is_mapped]
        
        # Group by part
        by_part = defaultdict(list)
        for field in questionnaire_fields:
            by_part[field.part].append(field)
        
        # Build JSON structure
        data = {
            "form": st.session_state.form_info.get('form_number', 'Unknown'),
            "title": st.session_state.form_info.get('form_title', 'Unknown Form'),
            "generated": datetime.now().isoformat(),
            "totalFields": len(questionnaire_fields),
            "sections": []
        }
        
        for part in sorted(by_part.keys(), key=lambda x: int(re.search(r'\d+', x).group())):
            section = {
                "part": part,
                "fieldCount": len(by_part[part]),
                "fields": []
            }
            
            for field in by_part[part]:
                section["fields"].append({
                    "id": field.field_id,
                    "fieldName": field.field_name,
                    "description": field.description,
                    "type": field.field_type,
                    "page": field.page,
                    "position": {
                        "x": field.rect[0],
                        "y": field.rect[1]
                    }
                })
            
            data["sections"].append(section)
        
        return json.dumps(data, indent=2)

def render_header():
    """Render application header"""
    st.markdown("""
    <style>
        .main-header {
            background: linear-gradient(135deg, #1e3a8a 0%, #3730a3 100%);
            color: white;
            padding: 2rem;
            border-radius: 10px;
            margin-bottom: 2rem;
            text-align: center;
        }
        .part-header {
            background: #f3f4f6;
            padding: 1rem;
            border-radius: 8px;
            margin: 1rem 0;
            border-left: 4px solid #3730a3;
        }
        .field-card {
            background: white;
            border: 1px solid #e5e7eb;
            padding: 1rem;
            margin: 0.5rem 0;
            border-radius: 6px;
            transition: all 0.2s;
        }
        .field-card:hover {
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .status-badge {
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.875rem;
            font-weight: 500;
        }
        .status-mapped { background: #d1fae5; color: #065f46; }
        .status-questionnaire { background: #fed7aa; color: #92400e; }
        .status-unmapped { background: #fee2e2; color: #991b1b; }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="main-header">
        <h1>📄 USCIS PDF Form Field Extractor</h1>
        <p>Extract fields from PDF → Map to database → Export unmapped to JSON</p>
    </div>
    """, unsafe_allow_html=True)

def render_upload_tab(extractor: PDFFieldExtractor):
    """Upload and extract PDF fields"""
    st.markdown("## 📤 Upload USCIS Form PDF")
    
    uploaded_file = st.file_uploader(
        "Choose a USCIS form PDF file",
        type=['pdf'],
        help="Upload any USCIS form (I-90, I-129, I-485, N-400, etc.)"
    )
    
    if uploaded_file:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.info(f"📄 **File:** {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")
        with col2:
            if st.button("🔍 Extract Fields", type="primary"):
                with st.spinner("Reading PDF and extracting fields..."):
                    if extractor.extract_from_pdf(uploaded_file):
                        st.success(f"✅ Successfully extracted {len(st.session_state.extracted_fields)} fields!")
                        st.rerun()
    
    # Display extracted fields
    if st.session_state.extracted_fields:
        st.markdown("---")
        st.markdown("## 📊 Extracted Fields by Part")
        
        # Form info
        form_info = st.session_state.form_info
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Form", form_info.get('form_number', 'Unknown'))
        with col2:
            st.metric("Total Fields", len(st.session_state.extracted_fields))
        with col3:
            st.metric("Parts", len(st.session_state.fields_by_part))
        with col4:
            st.metric("Pages", form_info.get('total_pages', 0))
        
        # Display fields by part
        for part, fields in st.session_state.fields_by_part.items():
            with st.expander(f"📑 **{part}** - {len(fields)} fields", expanded=(part == "Part 1")):
                # Part summary
                field_types = defaultdict(int)
                for field in fields:
                    field_types[field.field_type] += 1
                
                type_summary = ", ".join([f"{t}: {c}" for t, c in field_types.items()])
                st.caption(f"Field types: {type_summary}")
                
                # Fields table
                df_data = []
                for field in fields:
                    df_data.append({
                        "ID": field.field_id,
                        "Description": field.description,
                        "Type": field.field_type,
                        "Page": field.page,
                        "Status": "Mapped" if field.is_mapped else "Questionnaire" if field.to_questionnaire else "Unmapped"
                    })
                
                df = pd.DataFrame(df_data)
                st.dataframe(df, use_container_width=True, hide_index=True)

def render_mapping_tab(extractor: PDFFieldExtractor):
    """Map fields to database objects"""
    if not st.session_state.extracted_fields:
        st.info("👆 Please upload and extract a PDF form first")
        return
    
    st.markdown("## 🎯 Field Mapping")
    
    # Summary stats
    fields = st.session_state.extracted_fields
    mapped = sum(1 for f in fields if f.is_mapped)
    questionnaire = sum(1 for f in fields if f.to_questionnaire)
    unmapped = len(fields) - mapped - questionnaire
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Fields", len(fields))
    with col2:
        st.metric("Mapped to DB", mapped)
    with col3:
        st.metric("To Questionnaire", questionnaire)
    with col4:
        st.metric("Unmapped", unmapped)
    
    # Quick actions
    st.markdown("### ⚡ Quick Actions")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📋 All Unmapped → Questionnaire"):
            for field in fields:
                if not field.is_mapped:
                    field.to_questionnaire = True
            st.success(f"Moved {unmapped} fields to questionnaire")
            st.rerun()
    with col2:
        if st.button("🔄 Reset All Mappings"):
            for field in fields:
                field.is_mapped = False
                field.to_questionnaire = False
                field.db_mapping = None
            st.rerun()
    
    # Part filter
    st.markdown("### 📑 Map Fields by Part")
    parts = ["All Parts"] + list(st.session_state.fields_by_part.keys())
    selected_part = st.selectbox("Select Part", parts)
    
    # Get fields to display
    if selected_part == "All Parts":
        display_fields = fields
    else:
        display_fields = st.session_state.fields_by_part[selected_part]
    
    # Display fields for mapping
    st.markdown(f"<div class='part-header'>Showing {len(display_fields)} fields</div>", unsafe_allow_html=True)
    
    for field in display_fields:
        col1, col2, col3, col4 = st.columns([1.5, 2.5, 3, 1])
        
        with col1:
            st.markdown(f"**{field.field_id}**")
            st.caption(f"{field.part}")
        
        with col2:
            st.markdown(f"**{field.description}**")
            st.caption(f"Type: {field.field_type} | Page: {field.page}")
        
        with col3:
            if field.is_mapped:
                st.success(f"✅ Mapped to: {field.db_mapping}")
            elif field.to_questionnaire:
                st.warning("📋 In Questionnaire")
            else:
                # Mapping dropdown
                options = ["-- Select Mapping --"] + ["📋 Send to Questionnaire"] + extractor.db_paths
                
                selected = st.selectbox(
                    "Map to",
                    options,
                    key=f"map_{field.field_id}",
                    label_visibility="collapsed"
                )
                
                if selected == "📋 Send to Questionnaire":
                    field.to_questionnaire = True
                    st.rerun()
                elif selected != "-- Select Mapping --":
                    field.db_mapping = selected
                    field.is_mapped = True
                    st.rerun()
        
        with col4:
            if field.is_mapped or field.to_questionnaire:
                if st.button("❌", key=f"reset_{field.field_id}", help="Reset mapping"):
                    field.is_mapped = False
                    field.to_questionnaire = False
                    field.db_mapping = None
                    st.rerun()

def render_export_tab(extractor: PDFFieldExtractor):
    """Export mapped fields"""
    if not st.session_state.extracted_fields:
        st.info("👆 Please extract and map fields first")
        return
    
    st.markdown("## 📥 Export Mappings")
    
    # Summary
    fields = st.session_state.extracted_fields
    mapped = sum(1 for f in fields if f.is_mapped)
    questionnaire = sum(1 for f in fields if f.to_questionnaire)
    unmapped = len(fields) - mapped - questionnaire
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown('<div class="status-badge status-mapped">Database Mapped: ' + str(mapped) + '</div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="status-badge status-questionnaire">Questionnaire: ' + str(questionnaire) + '</div>', unsafe_allow_html=True)
    with col3:
        st.markdown('<div class="status-badge status-unmapped">Unmapped: ' + str(unmapped) + '</div>', unsafe_allow_html=True)
    
    if unmapped > 0:
        st.warning(f"⚠️ {unmapped} unmapped fields will be automatically added to the questionnaire JSON")
    
    st.markdown("---")
    
    # Export options
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📝 TypeScript Export")
        st.markdown("Database field mappings for your application")
        
        ts_content = extractor.generate_typescript(fields)
        
        st.download_button(
            label="📥 Download TypeScript File",
            data=ts_content,
            file_name=f"{st.session_state.form_info.get('form_number', 'form')}.ts",
            mime="text/plain",
            use_container_width=True
        )
        
        with st.expander("Preview TypeScript"):
            st.code(ts_content[:1000] + "\n...", language="typescript")
    
    with col2:
        st.markdown("### 📋 Questionnaire JSON")
        st.markdown("Fields requiring manual entry")
        
        # Auto-add unmapped to questionnaire for JSON
        temp_fields = []
        for field in fields:
            if not field.is_mapped:
                temp_field = field
                temp_field.to_questionnaire = True
                temp_fields.append(temp_field)
            else:
                temp_fields.append(field)
        
        json_content = extractor.generate_questionnaire_json(temp_fields)
        
        st.download_button(
            label="📥 Download JSON File",
            data=json_content,
            file_name=f"{st.session_state.form_info.get('form_number', 'form')}-questionnaire.json",
            mime="application/json",
            use_container_width=True
        )
        
        with st.expander("Preview JSON"):
            preview_data = json.loads(json_content)
            preview_data["sections"] = preview_data["sections"][:1]  # Show first section only
            if preview_data["sections"]:
                preview_data["sections"][0]["fields"] = preview_data["sections"][0]["fields"][:3]
            st.json(preview_data)

def main():
    st.set_page_config(
        page_title="USCIS PDF Field Extractor",
        page_icon="📄",
        layout="wide"
    )
    
    # Initialize extractor
    extractor = PDFFieldExtractor()
    
    # Render header
    render_header()
    
    # Create tabs
    tab1, tab2, tab3 = st.tabs(["📤 Upload & Extract", "🎯 Map Fields", "📥 Export"])
    
    with tab1:
        render_upload_tab(extractor)
    
    with tab2:
        render_mapping_tab(extractor)
    
    with tab3:
        render_export_tab(extractor)
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 📊 Progress Overview")
        
        if st.session_state.extracted_fields:
            fields = st.session_state.extracted_fields
            total = len(fields)
            mapped = sum(1 for f in fields if f.is_mapped)
            quest = sum(1 for f in fields if f.to_questionnaire)
            progress = (mapped + quest) / total if total > 0 else 0
            
            st.progress(progress)
            st.caption(f"{progress:.0%} Complete")
            
            st.markdown("---")
            
            # Part breakdown
            st.markdown("### 📑 Parts Summary")
            for part, part_fields in st.session_state.fields_by_part.items():
                part_mapped = sum(1 for f in part_fields if f.is_mapped or f.to_questionnaire)
                st.write(f"**{part}**: {part_mapped}/{len(part_fields)} done")
        
        st.markdown("---")
        st.markdown("### ℹ️ Instructions")
        st.markdown("""
        1. **Upload** your USCIS PDF form
        2. **Extract** fields (starts from Part 1)
        3. **Map** fields to database or questionnaire
        4. **Export** TypeScript and JSON files
        
        **Notes:**
        - Part 0 (attorney) is skipped
        - Unmapped fields → JSON automatically
        - Fields numbered as P1_1, P1_2, etc.
        """)

if __name__ == "__main__":
    main()
