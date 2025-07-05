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
    line: str               # Line number if available
    page: int               # Page number
    field_type: str         # text, checkbox, radio, etc.
    field_value: str        # Current value if any
    description: str        # Human-readable description
    db_mapping: Optional[str] = None  # Database path if mapped
    is_mapped: bool = False
    to_questionnaire: bool = False

class PDFFieldExtractor:
    """Accurate PDF field extractor for USCIS forms"""
    
    def __init__(self):
        self.init_session_state()
        self.db_paths = self._build_database_paths()
        
        # Attorney field indicators to skip
        self.attorney_indicators = [
            "attorney", "lawyer", "representative", "bar number", "law firm",
            "g-28", "g28", "bia", "accredited", "licensing", "preparer",
            "ein", "fein", "firm name", "law office"
        ]
    
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
    
    def extract_from_pdf(self, pdf_file, auto_checkboxes_to_json: bool = True) -> bool:
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
            
            # Extract all fields
            all_fields = []
            field_counter = defaultdict(int)
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                widgets = page.widgets()
                
                for widget in widgets:
                    if not widget.field_name:
                        continue
                    
                    field_name = widget.field_name
                    
                    # Skip attorney/Part 0 fields
                    if self._is_attorney_field(field_name):
                        continue
                    
                    # Parse part and line from field name
                    part_info = self._parse_part_from_field(field_name)
                    
                    # Skip if no valid part found or Part 0
                    if not part_info['part'] or part_info['part'] == "Part 0":
                        continue
                    
                    # Get field properties
                    field_type = self._get_field_type(widget.field_type)
                    field_value = widget.field_value or ""
                    
                    # Generate field ID
                    part_num = re.search(r'(\d+)', part_info['part'])
                    if part_num:
                        field_counter[part_info['part']] += 1
                        field_id = f"P{part_num.group(1)}_{field_counter[part_info['part']]}"
                    else:
                        continue
                    
                    # Generate description
                    description = self._generate_clean_description(field_name, widget.field_display, part_info)
                    
                    # Create field object
                    field = ExtractedField(
                        field_name=field_name,
                        field_id=field_id,
                        part=part_info['part'],
                        line=part_info['line'],
                        page=page_num + 1,
                        field_type=field_type,
                        field_value=field_value,
                        description=description
                    )
                    
                    # Auto-move checkboxes to questionnaire if requested
                    if auto_checkboxes_to_json and field_type == "checkbox":
                        field.to_questionnaire = True
                    
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
                                key=lambda x: int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 999)
            st.session_state.fields_by_part = OrderedDict(
                (part, st.session_state.fields_by_part[part]) for part in sorted_parts
            )
            
            return True
            
        except Exception as e:
            st.error(f"Error extracting PDF: {str(e)}")
            return False
    
    def _is_attorney_field(self, field_name: str) -> bool:
        """Check if field is attorney/Part 0 related"""
        field_lower = field_name.lower()
        
        # Check for attorney indicators
        for indicator in self.attorney_indicators:
            if indicator in field_lower:
                return True
        
        # Check for Part 0
        if "pt0" in field_lower or "part0" in field_lower:
            return True
        
        return False
    
    def _parse_part_from_field(self, field_name: str) -> dict:
        """Parse part and line information from field name"""
        result = {'part': None, 'line': None}
        
        # Look for patterns like Pt1Line2, Part1Line3, etc.
        patterns = [
            r'Pt(\d+)Line(\d+[a-zA-Z]?)',
            r'Part(\d+)Line(\d+[a-zA-Z]?)',
            r'Pt(\d+)_Line(\d+[a-zA-Z]?)',
            r'Part\s*(\d+).*Line\s*(\d+[a-zA-Z]?)',
            r'P(\d+)L(\d+[a-zA-Z]?)',
            r'Pt(\d+)',
            r'Part(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, field_name, re.IGNORECASE)
            if match:
                part_num = match.group(1)
                result['part'] = f"Part {part_num}"
                if len(match.groups()) > 1:
                    result['line'] = match.group(2)
                break
        
        # If no part found, check if field belongs to a specific page range
        if not result['part']:
            # Default to Part 1 for fields without explicit part
            if any(x in field_name.lower() for x in ['alien', 'uscis', 'information', 'name']):
                result['part'] = "Part 1"
        
        return result
    
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
    
    def _generate_clean_description(self, field_name: str, display_name: str, part_info: dict) -> str:
        """Generate clean human-readable description"""
        # Use display name if available and meaningful
        if display_name and display_name.strip() and not display_name.startswith('Check Box'):
            return display_name.strip()
        
        # Clean up field name
        clean = field_name
        
        # Remove common prefixes and patterns
        patterns_to_remove = [
            r'form\[\d+\]\.',
            r'#subform\[\d+\]\.',
            r'Page\d+\[\d+\]\.',
            r'Pt\d+Line\d+[a-zA-Z]?',
            r'Part\d+Line\d+[a-zA-Z]?',
            r'CheckBox\d+',
            r'Text\d+',
            r'PDF417BarCode\d+',
            r'\[\d+\]',
            r'^#'
        ]
        
        for pattern in patterns_to_remove:
            clean = re.sub(pattern, '', clean, flags=re.IGNORECASE)
        
        # Extract last meaningful component
        if '.' in clean:
            parts = clean.split('.')
            clean = parts[-1] if parts[-1] else parts[-2] if len(parts) > 1 else clean
        
        # Handle specific field types
        if 'alien' in clean.lower() and 'number' in clean.lower():
            return "Alien Number (A-Number)"
        elif 'uscis' in clean.lower() and 'online' in clean.lower():
            return "USCIS Online Account Number"
        elif 'checkbox' in field_name.lower():
            if part_info['line']:
                return f"Line {part_info['line']} Selection"
            else:
                return "Selection Box"
        elif 'barcode' in clean.lower():
            return "Barcode (System Use)"
        
        # Convert to readable format
        clean = clean.replace('_', ' ')
        clean = re.sub(r'([a-z])([A-Z])', r'\1 \2', clean)
        
        # Add line info if available
        if part_info['line'] and 'line' not in clean.lower():
            clean = f"Line {part_info['line']} - {clean}"
        
        return clean.strip() if clean.strip() else "Field"
    
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
                if field.line:
                    ts += f'      line: "{field.line}",\n'
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
        
        for part in sorted(by_part.keys(), key=lambda x: int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 999):
            section = {
                "part": part,
                "fieldCount": len(by_part[part]),
                "fields": []
            }
            
            for field in by_part[part]:
                field_data = {
                    "id": field.field_id,
                    "description": field.description,
                    "type": field.field_type,
                    "page": field.page
                }
                
                if field.line:
                    field_data["line"] = field.line
                
                section["fields"].append(field_data)
            
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
        .checkbox-notice {
            background: #fef3c7;
            border-left: 4px solid #f59e0b;
            padding: 1rem;
            margin: 1rem 0;
            border-radius: 4px;
        }
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
            auto_checkbox = st.checkbox("Auto-move checkboxes to JSON", value=True)
        
        if st.button("🔍 Extract Fields", type="primary", use_container_width=True):
            with st.spinner("Reading PDF and extracting fields..."):
                if extractor.extract_from_pdf(uploaded_file, auto_checkbox):
                    st.success(f"✅ Successfully extracted {len(st.session_state.extracted_fields)} fields!")
                    if auto_checkbox:
                        checkbox_count = sum(1 for f in st.session_state.extracted_fields if f.field_type == "checkbox")
                        if checkbox_count > 0:
                            st.info(f"📋 Automatically moved {checkbox_count} checkboxes to questionnaire")
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
            checkbox_count = sum(1 for f in st.session_state.extracted_fields if f.field_type == "checkbox")
            st.metric("Checkboxes", checkbox_count)
        
        # Notice about checkboxes
        if any(f.field_type == "checkbox" for f in st.session_state.extracted_fields):
            st.markdown("""
            <div class="checkbox-notice">
                <strong>📋 Note:</strong> All checkbox fields have been automatically moved to the questionnaire 
                as they typically require manual selection based on the applicant's situation.
            </div>
            """, unsafe_allow_html=True)
        
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
                    status = "Mapped" if field.is_mapped else "Questionnaire" if field.to_questionnaire else "Unmapped"
                    df_data.append({
                        "ID": field.field_id,
                        "Description": field.description,
                        "Type": field.field_type,
                        "Line": field.line or "-",
                        "Page": field.page,
                        "Status": status
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
        if st.button("☑️ All Checkboxes → Questionnaire"):
            count = 0
            for field in fields:
                if field.field_type == "checkbox" and not field.to_questionnaire:
                    field.to_questionnaire = True
                    field.is_mapped = False
                    field.db_mapping = None
                    count += 1
            if count > 0:
                st.success(f"Moved {count} checkboxes to questionnaire")
                st.rerun()
    with col3:
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
    
    # Filter by field type
    field_types = ["All Types"] + list(set(f.field_type for f in fields))
    selected_type = st.selectbox("Filter by Type", field_types)
    
    # Get fields to display
    if selected_part == "All Parts":
        display_fields = fields
    else:
        display_fields = st.session_state.fields_by_part[selected_part]
    
    # Apply type filter
    if selected_type != "All Types":
        display_fields = [f for f in display_fields if f.field_type == selected_type]
    
    # Display fields for mapping
    st.markdown(f"<div class='part-header'>Showing {len(display_fields)} fields</div>", unsafe_allow_html=True)
    
    for field in display_fields:
        col1, col2, col3, col4 = st.columns([1.5, 2.5, 3, 1])
        
        with col1:
            st.markdown(f"**{field.field_id}**")
            st.caption(f"{field.part} • {field.field_type}")
        
        with col2:
            st.markdown(f"**{field.description}**")
            if field.line:
                st.caption(f"Line: {field.line} | Page: {field.page}")
            else:
                st.caption(f"Page: {field.page}")
        
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
        2. **Extract** fields (skips attorney fields)
        3. **Map** fields to database or questionnaire
        4. **Export** TypeScript and JSON files
        
        **Notes:**
        - Attorney/Part 0 fields are skipped
        - Checkboxes auto-moved to JSON
        - Fields parsed from actual PDF names
        - Line numbers extracted when available
        """)

if __name__ == "__main__":
    main()
