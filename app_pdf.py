import streamlit as st
import json
import re
import fitz  # PyMuPDF
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Union
from collections import OrderedDict, defaultdict
import pandas as pd
from dataclasses import dataclass, field

# Comprehensive USCIS Forms Database
USCIS_FORMS_DATABASE = {
    "I-90": {
        "title": "Application to Replace Permanent Resident Card",
        "keywords": ["permanent resident card", "green card", "replace", "renew"],
        "identifier_patterns": ["Form I-90", "I-90", "OMB No. 1615-0052"]
    },
    "I-129": {
        "title": "Petition for a Nonimmigrant Worker",
        "keywords": ["nonimmigrant worker", "h1b", "l1", "petition"],
        "identifier_patterns": ["Form I-129", "I-129", "OMB No. 1615-0009"]
    },
    "I-130": {
        "title": "Petition for Alien Relative",
        "keywords": ["alien relative", "family", "petition"],
        "identifier_patterns": ["Form I-130", "I-130", "OMB No. 1615-0012"]
    },
    "I-131": {
        "title": "Application for Travel Document",
        "keywords": ["travel document", "reentry permit", "refugee travel"],
        "identifier_patterns": ["Form I-131", "I-131", "OMB No. 1615-0013"]
    },
    "I-140": {
        "title": "Immigrant Petition for Alien Workers",
        "keywords": ["immigrant petition", "alien worker", "employment based"],
        "identifier_patterns": ["Form I-140", "I-140", "OMB No. 1615-0015"]
    },
    "I-485": {
        "title": "Application to Register Permanent Residence or Adjust Status",
        "keywords": ["adjust status", "permanent residence", "green card application"],
        "identifier_patterns": ["Form I-485", "I-485", "OMB No. 1615-0023"]
    },
    "I-539": {
        "title": "Application To Extend/Change Nonimmigrant Status",
        "keywords": ["extend status", "change status", "nonimmigrant"],
        "identifier_patterns": ["Form I-539", "I-539", "OMB No. 1615-0003"]
    },
    "I-765": {
        "title": "Application for Employment Authorization",
        "keywords": ["employment authorization", "work permit", "ead"],
        "identifier_patterns": ["Form I-765", "I-765", "OMB No. 1615-0040"]
    },
    "N-400": {
        "title": "Application for Naturalization",
        "keywords": ["naturalization", "citizenship", "citizen"],
        "identifier_patterns": ["Form N-400", "N-400", "OMB No. 1615-0052"]
    }
}

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
    "attorneyLawfirmDetails": {
        "lawfirmDetails": ["lawFirmName", "lawFirmFein"],
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
            "customer_name", "customer_type_of_business", "customer_tax_id", 
            "customer_naics_code", "customer_total_employees"
        ],
        "signatory": [
            "signatory_first_name", "signatory_last_name", "signatory_middle_name",
            "signatory_job_title", "signatory_work_phone", "signatory_email_id"
        ],
        "address": [
            "address_street", "address_city", "address_state", "address_zip",
            "address_country"
        ]
    }
}

# Field type mappings
FIELD_TYPE_SUFFIX_MAP = {
    "text": ":TextBox",
    "checkbox": ":CheckBox",
    "radio": ":ConditionBox",
    "select": ":SelectBox",
    "date": ":Date",
    "signature": ":SignatureBox"
}

@dataclass
class PDFField:
    """Field representation"""
    index: int
    raw_name: str
    field_type: str
    value: str = ""
    page: int = 1
    part: str = ""
    item: str = ""
    description: str = ""
    db_mapping: Optional[str] = None
    mapping_type: str = "direct"
    is_mapped: bool = False
    is_questionnaire: bool = False
    field_type_suffix: str = ":TextBox"
    clean_name: str = ""

class SimplifiedUSCISMapper:
    """Simplified USCIS Form Mapping System"""
    
    def __init__(self):
        self.db_objects = DB_OBJECTS
        self.uscis_forms = USCIS_FORMS_DATABASE
        self.init_session_state()
        self._build_database_paths()
        
    def init_session_state(self):
        """Initialize session state"""
        if 'form_type' not in st.session_state:
            st.session_state.form_type = None
        if 'pdf_fields' not in st.session_state:
            st.session_state.pdf_fields = []
        if 'field_mappings' not in st.session_state:
            st.session_state.field_mappings = {}
        if 'processed_fields' not in st.session_state:
            st.session_state.processed_fields = set()
    
    def _build_database_paths(self):
        """Build flat list of all database paths for dropdown"""
        self.db_paths = []
        
        def extract_paths(obj_name, structure, prefix=""):
            if isinstance(structure, dict):
                for key, value in structure.items():
                    if key == "":
                        if isinstance(value, list):
                            for field_name in value:
                                path = f"{obj_name}.{field_name}"
                                self.db_paths.append(path)
                    else:
                        new_prefix = f"{obj_name}.{key}"
                        if isinstance(value, list):
                            for field_name in value:
                                path = f"{new_prefix}.{field_name}"
                                self.db_paths.append(path)
                        elif isinstance(value, dict):
                            for nested_key, nested_value in value.items():
                                if isinstance(nested_value, list):
                                    for field_name in nested_value:
                                        path = f"{new_prefix}.{nested_key}.{field_name}"
                                        self.db_paths.append(path)
        
        for obj_name, obj_structure in self.db_objects.items():
            extract_paths(obj_name, obj_structure)
        
        self.db_paths = sorted(list(set(self.db_paths)))
    
    def detect_form_type(self, pdf_file) -> Tuple[Optional[str], float]:
        """Detect USCIS form type from PDF"""
        try:
            pdf_bytes = pdf_file.read()
            pdf_file.seek(0)
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            text_content = ""
            for page_num in range(min(3, len(doc))):
                page = doc[page_num]
                text_content += page.get_text() + " "
            
            doc.close()
            
            text_lower = text_content.lower()
            text_upper = text_content.upper()
            
            form_scores = {}
            
            for form_code, form_info in self.uscis_forms.items():
                score = 0.0
                
                for pattern in form_info["identifier_patterns"]:
                    if pattern in text_content or pattern in text_upper:
                        score += 0.5
                
                if form_code in text_upper or f"FORM {form_code}" in text_upper:
                    score += 0.3
                
                keyword_matches = sum(1 for keyword in form_info["keywords"] if keyword in text_lower)
                if keyword_matches > 0:
                    score += 0.2 * (keyword_matches / len(form_info["keywords"]))
                
                form_scores[form_code] = min(score, 1.0)
            
            best_form = max(form_scores, key=form_scores.get) if form_scores else None
            best_score = form_scores.get(best_form, 0.0) if best_form else 0.0
            
            if best_score >= 0.5:
                return best_form, best_score
            else:
                return None, 0.0
                
        except Exception as e:
            st.error(f"Error detecting form type: {str(e)}")
            return None, 0.0
    
    def extract_pdf_fields(self, pdf_file, form_type: str) -> List[PDFField]:
        """Extract fields from PDF, skipping Part 0"""
        fields = []
        
        try:
            pdf_bytes = pdf_file.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            field_index = 0
            seen_fields = set()
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                for widget in page.widgets():
                    if widget.field_name and widget.field_name not in seen_fields:
                        seen_fields.add(widget.field_name)
                        
                        # Extract part information
                        part = self._extract_part(widget.field_name)
                        
                        # Skip Part 0 fields
                        if "Part 0" in part:
                            continue
                        
                        # Clean field name and extract details
                        clean_name = self._clean_field_name(widget.field_name)
                        field_type = self._get_field_type(widget)
                        item = self._extract_item(clean_name)
                        description = self._generate_description(clean_name, widget.field_display)
                        field_type_suffix = FIELD_TYPE_SUFFIX_MAP.get(field_type, ":TextBox")
                        
                        # Create unique clean name
                        if part:
                            part_num = re.search(r'Part\s*(\d+)', part)
                            if part_num:
                                clean_name = f"P{part_num.group(1)}_{item if item else field_index}"
                        
                        pdf_field = PDFField(
                            index=field_index,
                            raw_name=widget.field_name,
                            field_type=field_type,
                            value=widget.field_value or '',
                            page=page_num + 1,
                            part=part,
                            item=item,
                            description=description,
                            field_type_suffix=field_type_suffix,
                            clean_name=clean_name
                        )
                        
                        fields.append(pdf_field)
                        field_index += 1
            
            doc.close()
            
        except Exception as e:
            st.error(f"Error extracting PDF: {str(e)}")
            return []
        
        return fields
    
    def _extract_part(self, field_name: str) -> str:
        """Extract part number from field name"""
        patterns = [
            r'Part[\s_\-]*(\d+)',
            r'P(\d+)[\._]',
            r'Section[\s_\-]*(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, field_name, re.IGNORECASE)
            if match:
                return f"Part {match.group(1)}"
        
        return "General"
    
    def _clean_field_name(self, field_name: str) -> str:
        """Clean field name"""
        patterns_to_remove = [
            r'form\d*\[\d+\]\.',
            r'#subform\[\d+\]\.',
            r'topmostSubform\[\d+\]\.',
            r'\[\d+\]',
            r'^#',
            r'\.pdf$'
        ]
        
        clean_name = field_name
        for pattern in patterns_to_remove:
            clean_name = re.sub(pattern, '', clean_name, flags=re.IGNORECASE)
        
        return clean_name
    
    def _get_field_type(self, widget) -> str:
        """Determine field type"""
        if widget.field_type == 2:
            return "checkbox"
        elif widget.field_type == 3:
            return "radio"
        elif widget.field_type == 5:
            return "select"
        elif widget.field_type == 7:
            return "signature"
        else:
            return "text"
    
    def _extract_item(self, field_name: str) -> str:
        """Extract item number"""
        patterns = [
            r'Item\s*(\d+[a-zA-Z]?)',
            r'_(\d+[a-zA-Z]?)$',
            r'\.(\d+[a-zA-Z]?)$'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, field_name, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return ""
    
    def _generate_description(self, field_name: str, field_display: str) -> str:
        """Generate field description"""
        if field_display and not field_display.startswith('form'):
            return field_display
        
        # Extract meaningful part from field name
        parts = field_name.split('.')
        meaningful_part = parts[-1] if parts else field_name
        
        # Convert camelCase to readable
        desc = re.sub(r'([a-z])([A-Z])', r'\1 \2', meaningful_part)
        
        return desc.strip()
    
    def generate_typescript_export(self, form_type: str, fields: List[PDFField]) -> str:
        """Generate TypeScript export"""
        form_name = form_type.replace('-', '')
        
        # Group fields by object type
        customer_fields = []
        beneficiary_fields = []
        attorney_fields = []
        questionnaire_fields = []
        
        for field in fields:
            if field.is_questionnaire or not field.db_mapping:
                questionnaire_fields.append(field)
            elif field.db_mapping:
                if field.db_mapping.startswith("customer"):
                    customer_fields.append(field)
                elif field.db_mapping.startswith("beneficiary"):
                    beneficiary_fields.append(field)
                elif field.db_mapping.startswith("attorney"):
                    attorney_fields.append(field)
                else:
                    questionnaire_fields.append(field)
        
        # Generate TypeScript
        ts_content = f"export const {form_name} = {{\n"
        
        if customer_fields:
            ts_content += "  customerData: {\n"
            for field in customer_fields:
                db_path = field.db_mapping.replace("customer.", "")
                ts_content += f'    "{field.clean_name}{field.field_type_suffix}": "{db_path}",\n'
            ts_content = ts_content.rstrip(',\n') + '\n'
            ts_content += "  },\n"
        
        if beneficiary_fields:
            ts_content += "  beneficiaryData: {\n"
            for field in beneficiary_fields:
                db_path = field.db_mapping.replace("beneficiary.", "")
                ts_content += f'    "{field.clean_name}{field.field_type_suffix}": "{db_path}",\n'
            ts_content = ts_content.rstrip(',\n') + '\n'
            ts_content += "  },\n"
        
        if attorney_fields:
            ts_content += "  attorneyData: {\n"
            for field in attorney_fields:
                db_path = field.db_mapping.replace("attorney.", "").replace("attorneyLawfirmDetails.", "")
                ts_content += f'    "{field.clean_name}{field.field_type_suffix}": "{db_path}",\n'
            ts_content = ts_content.rstrip(',\n') + '\n'
            ts_content += "  },\n"
        
        if questionnaire_fields:
            ts_content += "  questionnaireData: {\n"
            for field in questionnaire_fields:
                ts_content += f'    "{field.clean_name}": {{\n'
                ts_content += f'      description: "{field.description}",\n'
                ts_content += f'      fieldType: "{field.field_type}",\n'
                ts_content += f'      part: "{field.part}",\n'
                if field.item:
                    ts_content += f'      item: "{field.item}",\n'
                ts_content += f'      required: true\n'
                ts_content += "    },\n"
            ts_content = ts_content.rstrip(',\n') + '\n'
            ts_content += "  }\n"
        
        ts_content = ts_content.rstrip(',\n') + '\n'
        ts_content += "};\n"
        
        return ts_content

def render_header():
    """Render header"""
    st.markdown("""
    <style>
        .main-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            text-align: center;
        }
        .header-title {
            font-size: 2em;
            font-weight: bold;
            margin: 0;
        }
        .field-card {
            background: white;
            border: 1px solid #e5e7eb;
            padding: 15px;
            margin: 10px 0;
            border-radius: 8px;
        }
        .metric-card {
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            text-align: center;
        }
    </style>
    <div class="main-header">
        <h1 class="header-title">USCIS Form Mapper</h1>
        <p>Auto-detect forms and map to database (Part 1 onwards)</p>
    </div>
    """, unsafe_allow_html=True)

def render_upload_section(mapper: SimplifiedUSCISMapper):
    """Render upload section"""
    st.markdown("## 📤 Upload USCIS Form")
    
    uploaded_file = st.file_uploader(
        "Upload USCIS PDF form",
        type=['pdf'],
        help="Upload any fillable USCIS form"
    )
    
    if uploaded_file:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Filename", uploaded_file.name)
        with col2:
            st.metric("Size", f"{uploaded_file.size / 1024:.1f} KB")
        with col3:
            st.metric("Type", "PDF")
        
        if st.button("🚀 Auto-Detect & Extract", type="primary", use_container_width=True):
            with st.spinner("Detecting form type..."):
                form_type, confidence = mapper.detect_form_type(uploaded_file)
                
                if form_type and confidence >= 0.5:
                    st.session_state.form_type = form_type
                    st.success(f"✅ Detected: {form_type} ({confidence:.0%} confidence)")
                    
                    with st.spinner("Extracting fields (skipping Part 0)..."):
                        fields = mapper.extract_pdf_fields(uploaded_file, form_type)
                        
                        if fields:
                            st.session_state.pdf_fields = fields
                            st.session_state.field_mappings = {f.raw_name: f for f in fields}
                            st.success(f"✅ Extracted {len(fields)} fields from Part 1 onwards!")
                            st.rerun()
                        else:
                            st.error("No fields found in Part 1 onwards")
                else:
                    st.error("Could not detect form type. Please select manually:")
                    
                    form_type = st.selectbox(
                        "Select form type:",
                        [""] + list(USCIS_FORMS_DATABASE.keys())
                    )
                    
                    if form_type and st.button("Extract with Manual Selection"):
                        st.session_state.form_type = form_type
                        fields = mapper.extract_pdf_fields(uploaded_file, form_type)
                        
                        if fields:
                            st.session_state.pdf_fields = fields
                            st.session_state.field_mappings = {f.raw_name: f for f in fields}
                            st.success(f"✅ Extracted {len(fields)} fields!")
                            st.rerun()

def render_mapping_section(mapper: SimplifiedUSCISMapper):
    """Render simplified mapping section"""
    if 'pdf_fields' not in st.session_state or not st.session_state.pdf_fields:
        st.info("Please upload a PDF form first")
        return
    
    st.markdown("## 🎯 Smart Mapping")
    
    fields = st.session_state.pdf_fields
    
    # Quick stats
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Fields", len(fields))
    with col2:
        mapped = sum(1 for f in fields if f.is_mapped)
        st.metric("Mapped", mapped)
    with col3:
        quest = sum(1 for f in fields if f.is_questionnaire)
        st.metric("Questionnaire", quest)
    with col4:
        unmapped = sum(1 for f in fields if not f.is_mapped and not f.is_questionnaire)
        st.metric("Unmapped", unmapped)
    
    # Quick actions
    st.markdown("### ⚡ Quick Actions")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📋 All Unmapped → Questionnaire", use_container_width=True):
            count = 0
            for field in fields:
                if not field.is_mapped and not field.is_questionnaire:
                    field.is_questionnaire = True
                    count += 1
            if count > 0:
                st.success(f"Added {count} fields to questionnaire!")
                st.rerun()
    
    with col2:
        if st.button("🔄 Reset All", use_container_width=True):
            for field in fields:
                field.is_mapped = False
                field.is_questionnaire = False
                field.db_mapping = None
            st.rerun()
    
    # Group fields by part
    fields_by_part = defaultdict(list)
    for field in fields:
        # Skip if field already processed
        field_key = f"{field.clean_name}_{field.description}"
        if field_key not in st.session_state.processed_fields:
            fields_by_part[field.part].append(field)
    
    # Sort parts
    sorted_parts = sorted(fields_by_part.keys(), 
                         key=lambda x: (0, int(re.search(r'\d+', x).group())) if re.search(r'\d+', x) else (1, x))
    
    # Display fields by part
    for part in sorted_parts:
        part_fields = fields_by_part[part]
        if not part_fields:
            continue
            
        with st.expander(f"📄 **{part}** ({len(part_fields)} fields)", expanded=True):
            for field in part_fields:
                render_field_mapping(field, mapper)

def render_field_mapping(field: PDFField, mapper: SimplifiedUSCISMapper):
    """Render individual field mapping with database dropdown"""
    field_key = f"{field.clean_name}_{field.description}"
    
    with st.container():
        st.markdown('<div class="field-card">', unsafe_allow_html=True)
        
        col1, col2 = st.columns([3, 2])
        
        with col1:
            st.markdown(f"**{field.clean_name}** - {field.description}")
            st.caption(f"Type: {field.field_type} | Page: {field.page}")
            
            # Current status
            if field.is_mapped and field.db_mapping:
                st.success(f"✅ Mapped to: `{field.db_mapping}`")
            elif field.is_questionnaire:
                st.warning("📋 In Questionnaire")
            else:
                st.info("❌ Unmapped")
        
        with col2:
            # Mapping action dropdown
            action_key = f"action_{field.index}"
            
            # Create options list
            options = ["Choose Action", "Manual Entry (Questionnaire)"] + mapper.db_paths
            
            # Get current selection
            if field.is_questionnaire:
                current_value = "Manual Entry (Questionnaire)"
            elif field.db_mapping:
                current_value = field.db_mapping
            else:
                current_value = "Choose Action"
            
            # Find index of current value
            try:
                current_index = options.index(current_value)
            except ValueError:
                current_index = 0
            
            selected = st.selectbox(
                "Select mapping",
                options,
                index=current_index,
                key=action_key,
                label_visibility="collapsed"
            )
            
            # Apply button
            if st.button("Apply", key=f"apply_{field.index}"):
                if selected == "Manual Entry (Questionnaire)":
                    field.is_questionnaire = True
                    field.is_mapped = False
                    field.db_mapping = None
                    st.session_state.processed_fields.add(field_key)
                    st.success("Added to questionnaire!")
                    st.rerun()
                elif selected != "Choose Action":
                    field.db_mapping = selected
                    field.is_mapped = True
                    field.is_questionnaire = False
                    st.session_state.processed_fields.add(field_key)
                    st.success("Mapped successfully!")
                    st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)

def render_export_section(mapper: SimplifiedUSCISMapper):
    """Render export section"""
    if 'pdf_fields' not in st.session_state or not st.session_state.pdf_fields:
        st.info("Please complete field mapping first")
        return
    
    st.markdown("## 📥 Export")
    
    fields = st.session_state.pdf_fields
    form_type = st.session_state.form_type
    
    # Export stats
    col1, col2, col3 = st.columns(3)
    
    mapped_count = sum(1 for f in fields if f.is_mapped)
    quest_count = sum(1 for f in fields if f.is_questionnaire)
    unmapped_count = sum(1 for f in fields if not f.is_mapped and not f.is_questionnaire)
    
    with col1:
        st.metric("✅ Ready", mapped_count + quest_count)
    with col2:
        st.metric("⚠️ Unmapped", unmapped_count)
    with col3:
        readiness = ((mapped_count + quest_count) / len(fields)) * 100 if fields else 0
        st.metric("📊 Readiness", f"{readiness:.0f}%")
    
    if unmapped_count > 0:
        st.warning(f"⚠️ {unmapped_count} fields are unmapped. Add them to questionnaire before export.")
    
    # Export buttons
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔧 Generate TypeScript", type="primary", use_container_width=True):
            # Auto-add unmapped to questionnaire
            for field in fields:
                if not field.is_mapped and not field.is_questionnaire:
                    field.is_questionnaire = True
            
            ts_content = mapper.generate_typescript_export(form_type, fields)
            
            st.download_button(
                "📥 Download TypeScript",
                ts_content,
                f"{form_type.replace('-', '')}.ts",
                "text/plain",
                use_container_width=True
            )
    
    with col2:
        if st.button("📊 Export to CSV", type="primary", use_container_width=True):
            data = []
            for field in fields:
                data.append({
                    'Field Name': field.clean_name,
                    'Description': field.description,
                    'Part': field.part,
                    'Type': field.field_type,
                    'Mapped To': field.db_mapping if field.db_mapping else 'Questionnaire' if field.is_questionnaire else 'Unmapped',
                    'Page': field.page
                })
            
            df = pd.DataFrame(data)
            csv = df.to_csv(index=False)
            
            st.download_button(
                "📥 Download CSV",
                csv,
                f"{form_type}_mappings.csv",
                "text/csv",
                use_container_width=True
            )

def main():
    """Main application"""
    st.set_page_config(
        page_title="USCIS Form Mapper",
        page_icon="📄",
        layout="wide"
    )
    
    # Initialize mapper
    mapper = SimplifiedUSCISMapper()
    
    # Render header
    render_header()
    
    # Create tabs
    tabs = st.tabs([
        "📤 Upload Form",
        "🎯 Smart Mapping",
        "📥 Export"
    ])
    
    with tabs[0]:
        render_upload_section(mapper)
    
    with tabs[1]:
        render_mapping_section(mapper)
    
    with tabs[2]:
        render_export_section(mapper)
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 📊 Status")
        
        if 'pdf_fields' in st.session_state and st.session_state.pdf_fields:
            fields = st.session_state.pdf_fields
            
            total = len(fields)
            mapped = sum(1 for f in fields if f.is_mapped)
            quest = sum(1 for f in fields if f.is_questionnaire)
            unmapped = total - mapped - quest
            
            st.metric("Total Fields", total)
            st.metric("Mapped", mapped)
            st.metric("Questionnaire", quest)
            st.metric("Unmapped", unmapped)
            
            if st.session_state.form_type:
                st.markdown("---")
                st.markdown(f"**Form:** {st.session_state.form_type}")
        else:
            st.info("Upload a form to see status")
        
        st.markdown("---")
        st.markdown("### ℹ️ Info")
        st.markdown("""
        - Part 0 fields are skipped
        - Select database object from dropdown
        - Or choose "Manual Entry" for questionnaire
        - All fields must be mapped before export
        """)

if __name__ == "__main__":
    main()
