import streamlit as st
import json
import re
import fitz  # PyMuPDF
from typing import Dict, List, Optional
from collections import defaultdict, OrderedDict
from dataclasses import dataclass
import hashlib
import time

# Configure page
st.set_page_config(
    page_title="USCIS Form Reader Pro",
    page_icon="🤖",
    layout="wide"
)

# CSS styling
st.markdown("""
<style>
    .mapping-row {
        background: white;
        border: 1px solid #ddd;
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 0.5rem;
    }
    .field-label {
        font-weight: 600;
        color: #2c3e50;
        font-size: 1.05rem;
    }
    .field-type {
        background: #e3f2fd;
        color: #1976d2;
        padding: 0.15rem 0.4rem;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 500;
        display: inline-block;
        margin-right: 0.5rem;
    }
    .status-badge {
        padding: 0.25rem 0.75rem;
        border-radius: 15px;
        font-size: 0.85rem;
        font-weight: 500;
    }
    .status-mapped { background: #d4edda; color: #155724; }
    .status-questionnaire { background: #fff3cd; color: #856404; }
    .status-unmapped { background: #f8d7da; color: #721c24; }
    .part-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 1rem;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# Database Structure
DB_OBJECTS = {
    "beneficiary": {
        "Beneficiary": ["beneficiaryFirstName", "beneficiaryLastName", "beneficiaryMiddleName",
                       "beneficiaryGender", "beneficiaryDateOfBirth", "beneficiarySsn",
                       "alienNumber", "alienRegistrationNumber", "beneficiaryCountryOfBirth",
                       "maritalStatus", "uscisOnlineAccountNumber"],
        "MailingAddress": ["addressStreet", "addressCity", "addressState", "addressZip", 
                          "addressCountry", "addressAptSteFlrNumber", "inCareOfName"],
        "ContactInfo": ["daytimeTelephoneNumber", "mobileTelephoneNumber", "emailAddress"],
        "PassportDetails": ["passportNumber", "passportIssueCountry", "passportIssueDate", "passportExpiryDate"],
        "VisaDetails": ["currentNonimmigrantStatus", "dateStatusExpires", "visaNumber"]
    },
    "petitioner": {
        "": ["familyName", "givenName", "middleName", "companyOrOrganizationName"],
        "ContactInfo": ["daytimeTelephoneNumber", "mobileTelephoneNumber", "emailAddress"],
        "Address": ["addressStreet", "addressCity", "addressState", "addressZip", "addressCountry"]
    },
    "customer": {
        "": ["customer_name", "customer_tax_id", "customer_type_of_business"],
        "SignatoryInfo": ["signatory_first_name", "signatory_last_name", "signatory_middle_name",
                         "signatory_job_title", "signatory_work_phone", "signatory_email"],
        "Address": ["address_street", "address_city", "address_state", "address_zip", "address_country"]
    },
    "attorney": {
        "attorneyInfo": ["firstName", "lastName", "middleName", "barNumber", "stateBarNumber",
                        "workPhone", "emailAddress", "faxNumber", "licensingAuthority"],
        "address": ["addressStreet", "addressCity", "addressState", "addressZip", "addressCountry"]
    },
    "attorneyLawfirmDetails": {
        "lawfirmDetails": ["lawFirmName", "lawFirmEIN"],
        "address": ["addressStreet", "addressCity", "addressState", "addressZip", "addressCountry"]
    },
    "case": {
        "": ["caseType", "caseSubType", "h1bRegistrationNumber", "h1BPetitionType", "requestedAction"]
    }
}

@dataclass
class PDFField:
    """Represents a field extracted from PDF"""
    widget_name: str = ""
    field_id: str = ""
    field_key: str = ""
    part_number: int = 1
    part_name: str = "Part 1"
    part_title: str = ""
    field_label: str = "Unnamed Field"
    field_type: str = "text"
    page: int = 1
    value: str = ""
    db_mapping: Optional[str] = None
    is_mapped: bool = False
    to_questionnaire: bool = False
    item_number: str = ""
    question_key: str = ""
    
    def get_status(self) -> str:
        if self.is_mapped:
            return "✅ Mapped"
        elif self.to_questionnaire:
            return "📋 Questionnaire"
        return "❌ Unmapped"

class FieldExtractor:
    """Handles field extraction and mapping"""
    
    def __init__(self):
        self.init_session_state()
        self.db_paths = self._build_db_paths()
        self.field_patterns = self._build_field_patterns()
    
    def init_session_state(self):
        """Initialize Streamlit session state"""
        defaults = {
            'fields': [],
            'fields_by_part': OrderedDict(),
            'form_info': {},
            'pdf_processed': False,
            'extraction_stats': {},
            'selected_part': 'All Parts',
            'part_structure': OrderedDict()
        }
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value
    
    def _build_db_paths(self) -> List[str]:
        """Build all database paths"""
        paths = []
        for obj_name, structure in DB_OBJECTS.items():
            for sub_obj, fields in structure.items():
                for field in fields:
                    path = f"{obj_name}.{sub_obj}.{field}" if sub_obj else f"{obj_name}.{field}"
                    paths.append(path)
        return sorted(paths)
    
    def _build_field_patterns(self) -> dict:
        """Build patterns for common field mappings"""
        return {
            r'(family|last)\s*name': ['beneficiary.Beneficiary.beneficiaryLastName'],
            r'(given|first)\s*name': ['beneficiary.Beneficiary.beneficiaryFirstName'],
            r'middle\s*name': ['beneficiary.Beneficiary.beneficiaryMiddleName'],
            r'email': ['beneficiary.ContactInfo.emailAddress'],
            r'phone': ['beneficiary.ContactInfo.daytimeTelephoneNumber'],
            r'street': ['beneficiary.MailingAddress.addressStreet'],
            r'city': ['beneficiary.MailingAddress.addressCity'],
            r'state': ['beneficiary.MailingAddress.addressState'],
            r'zip': ['beneficiary.MailingAddress.addressZip'],
            r'a[\s\-]?number': ['beneficiary.Beneficiary.alienNumber'],
            r'ssn|social\s*security': ['beneficiary.Beneficiary.beneficiarySsn'],
            r'date\s*of\s*birth': ['beneficiary.Beneficiary.beneficiaryDateOfBirth'],
            r'gender': ['beneficiary.Beneficiary.beneficiaryGender'],
            r'country\s*of\s*birth': ['beneficiary.Beneficiary.beneficiaryCountryOfBirth'],
            r'marital\s*status': ['beneficiary.Beneficiary.maritalStatus']
        }
    
    def extract_from_pdf(self, pdf_file) -> bool:
        """Extract fields from PDF organized by parts"""
        try:
            # Reset state
            st.session_state.fields = []
            st.session_state.fields_by_part = OrderedDict()
            st.session_state.part_structure = OrderedDict()
            
            start_time = time.time()
            pdf_bytes = pdf_file.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            # Detect form type
            st.session_state.form_info = self._detect_form_type(doc)
            
            # Analyze document structure
            part_mapping = self._analyze_document_structure(doc)
            
            # Group pages by parts
            pages_by_part = defaultdict(list)
            for page_num, part_info in part_mapping.items():
                part_key = f"Part {part_info['number']}"
                pages_by_part[part_key].append((page_num, part_info))
            
            # Extract fields by part
            all_fields = []
            seen_fields = set()
            
            for part_name, pages in pages_by_part.items():
                part_fields = []
                
                for page_num, part_info in pages:
                    page = doc[page_num]
                    widgets = page.widgets()
                    
                    if widgets:
                        for widget in widgets:
                            if widget and hasattr(widget, 'field_name') and widget.field_name:
                                field = self._create_field_from_widget(widget, part_info, page_num + 1)
                                
                                if field:
                                    # Check for duplicates
                                    field_key = f"{field.part_number}_{field.field_key}_{field.item_number}"
                                    if field_key not in seen_fields:
                                        seen_fields.add(field_key)
                                        part_fields.append(field)
                
                # Sort fields by item number
                part_fields.sort(key=lambda f: (self._parse_item_number(f.item_number), f.field_label))
                all_fields.extend(part_fields)
                
                if part_fields:
                    st.session_state.fields_by_part[part_name] = part_fields
                    st.session_state.part_structure[part_name] = {
                        'number': pages[0][1]['number'],
                        'title': pages[0][1].get('title', ''),
                        'field_count': len(part_fields),
                        'pages': [p[0] + 1 for p in pages]
                    }
            
            doc.close()
            
            # Store results
            st.session_state.fields = all_fields
            st.session_state.extraction_stats = {
                'total_fields': len(all_fields),
                'total_parts': len(st.session_state.fields_by_part),
                'extraction_time': time.time() - start_time
            }
            
            # Auto-categorize checkboxes and radios
            for field in all_fields:
                if field.field_type in ['checkbox', 'radio', 'button']:
                    field.to_questionnaire = True
            
            st.session_state.pdf_processed = True
            return True
            
        except Exception as e:
            st.error(f"❌ Error processing PDF: {str(e)}")
            return False
    
    def _parse_item_number(self, item_number: str) -> tuple:
        """Parse item number for sorting"""
        if not item_number:
            return (999, '')
        match = re.match(r'(\d+)\.?([a-z]?)', item_number)
        if match:
            return (int(match.group(1)), match.group(2) or '')
        return (999, item_number)
    
    def _detect_form_type(self, doc) -> dict:
        """Detect USCIS form type"""
        first_page_text = doc[0].get_text().upper()
        forms = {
            'I-129': 'Petition for a Nonimmigrant Worker',
            'I-130': 'Petition for Alien Relative',
            'I-140': 'Immigrant Petition for Alien Worker',
            'I-485': 'Application to Register Permanent Residence',
            'I-539': 'Application to Extend/Change Nonimmigrant Status',
            'I-765': 'Application for Employment Authorization',
            'N-400': 'Application for Naturalization',
            'G-28': 'Notice of Entry of Appearance as Attorney'
        }
        
        for form_num, title in forms.items():
            if form_num in first_page_text:
                return {'form_number': form_num, 'form_title': title}
        
        return {'form_number': 'Unknown', 'form_title': 'Unknown USCIS Form'}
    
    def _analyze_document_structure(self, doc) -> dict:
        """Analyze document to find parts"""
        part_mapping = {}
        current_part = {'number': 1, 'name': 'Part 1', 'title': ''}
        
        patterns = [
            r'Part\s+(\d+)[\.\s\-:]*([^\n]{0,100})',
            r'PART\s+(\d+)[\.\s\-:]*([^\n]{0,100})',
            r'Section\s+(\d+)[\.\s\-:]*([^\n]{0,100})'
        ]
        
        for page_num in range(len(doc)):
            page_text = doc[page_num].get_text()
            
            for pattern in patterns:
                matches = list(re.finditer(pattern, page_text, re.MULTILINE | re.IGNORECASE))
                if matches:
                    match = matches[0]
                    part_num = int(match.group(1))
                    part_title = match.group(2).strip() if match.group(2) else ""
                    
                    if part_num != current_part['number']:
                        current_part = {
                            'number': part_num,
                            'name': f"Part {part_num}",
                            'title': part_title
                        }
                    break
            
            part_mapping[page_num] = current_part.copy()
        
        return part_mapping
    
    def _create_field_from_widget(self, widget, part_info: dict, page: int) -> Optional[PDFField]:
        """Create field from widget"""
        try:
            widget_name = widget.field_name or ""
            if not widget_name:
                return None
            
            # Clean widget name
            clean_name = re.sub(r'form\d*\[?\d*\]?\.', '', widget_name, flags=re.IGNORECASE)
            clean_name = re.sub(r'\[\d+\]', '', clean_name)
            parts = clean_name.split('.')
            last_part = parts[-1] if parts else clean_name
            
            # Generate field key
            field_key = re.sub(r'[^\w]', '_', last_part)
            field_key = re.sub(r'(?i)(checkbox|check|box|field|text)\d*$', '', field_key)
            field_key = re.sub(r'_+$', '', field_key) or 'field'
            
            # Generate label
            field_label = re.sub(r'([a-z])([A-Z])', r'\1 \2', last_part)
            field_label = field_label.replace('_', ' ').replace('-', ' ').title()
            
            # Extract item number
            item_number = ""
            item_patterns = [r'(?:^|[^\d])(\d+)\.([a-z])\b', r'(?:^|[^\d])(\d+)([a-z])\b', r'(?:^|[^\d])(\d+)\b']
            
            for pattern in item_patterns:
                match = re.search(pattern, widget_name, re.IGNORECASE)
                if match:
                    if len(match.groups()) == 2:
                        item_number = f"{match.group(1)}.{match.group(2)}"
                    else:
                        item_number = match.group(1)
                    break
            
            # Generate question key
            if item_number:
                clean_item = item_number.replace('.', '')
                question_key = f"pt{part_info['number']}_{clean_item}_{field_key[:10]}"
            else:
                question_key = f"pt{part_info['number']}_{field_key}"
            
            # Get widget type
            widget_type = widget.field_type if hasattr(widget, 'field_type') else 4
            type_map = {1: "button", 2: "checkbox", 3: "radio", 4: "text", 5: "dropdown", 6: "list", 7: "signature"}
            field_type = type_map.get(widget_type, "text")
            
            # Create field ID
            unique_hash = hashlib.md5(f"{widget_name}_{part_info['number']}_{page}".encode()).hexdigest()[:8]
            field_id = f"P{part_info['number']}_{field_key}_{unique_hash}"
            
            return PDFField(
                widget_name=widget_name,
                field_id=field_id,
                field_key=field_key,
                part_number=part_info['number'],
                part_name=part_info['name'],
                part_title=part_info.get('title', ''),
                field_label=field_label,
                field_type=field_type,
                page=page,
                item_number=item_number,
                question_key=question_key
            )
            
        except Exception:
            return None
    
    def suggest_mapping(self, field: PDFField) -> Optional[str]:
        """Suggest database mapping for field"""
        label_lower = field.field_label.lower()
        
        for pattern, suggestions in self.field_patterns.items():
            if re.search(pattern, label_lower):
                return suggestions[0] if suggestions else None
        
        return None
    
    def generate_typescript(self) -> str:
        """Generate TypeScript export"""
        form_name = st.session_state.form_info.get('form_number', 'Form').replace('-', '')
        sections = {
            'customerData': {},
            'beneficiaryData': {},
            'attorneyData': {},
            'questionnaireData': {},
            'caseData': {}
        }
        
        for field in st.session_state.fields:
            if field.is_mapped and field.db_mapping:
                if field.db_mapping.startswith('customer.'):
                    section = 'customerData'
                elif field.db_mapping.startswith('beneficiary.'):
                    section = 'beneficiaryData'
                elif field.db_mapping.startswith('attorney.'):
                    section = 'attorneyData'
                elif field.db_mapping.startswith('case.'):
                    section = 'caseData'
                else:
                    continue
                
                suffix = ':TextBox' if field.field_type == 'text' else f':{field.field_type.capitalize()}Box'
                sections[section][field.field_key] = f"{field.db_mapping}{suffix}"
            
            elif field.to_questionnaire:
                sections['questionnaireData'][field.question_key] = f"{field.field_key}:ConditionBox"
        
        # Build TypeScript
        ts = f'export const {form_name} = {{\n'
        ts += f'    "formname": "{form_name}",\n'
        
        for section_name, fields in sections.items():
            if fields:
                ts += f'    "{section_name}": {{\n'
                entries = [f'        "{k}": "{v}"' for k, v in fields.items()]
                ts += ',\n'.join(entries) + '\n    },\n'
            else:
                ts += f'    "{section_name}": null,\n'
        
        ts += '    "conditionalData": {},\n'
        ts += f'    "pdfName": "{st.session_state.form_info.get("form_number", "Unknown")}"\n'
        ts += '};\n\n'
        ts += f'export default {form_name};'
        
        return ts
    
    def generate_json(self) -> str:
        """Generate JSON export for questionnaire"""
        controls = []
        
        for part_name, fields in st.session_state.fields_by_part.items():
            quest_fields = [f for f in fields if f.to_questionnaire]
            
            if quest_fields:
                # Add part title
                part_info = st.session_state.part_structure.get(part_name, {})
                title_text = f"{part_name}"
                if part_info.get('title'):
                    title_text += f": {part_info['title']}"
                
                controls.append({
                    "name": f"{part_name.lower().replace(' ', '_')}_title",
                    "label": title_text,
                    "type": "title",
                    "validators": {},
                    "style": {"col": "12"}
                })
                
                # Add fields
                for field in quest_fields:
                    label = field.field_label
                    if field.item_number:
                        label = f"{field.item_number}. {label}"
                    
                    control = {
                        "name": field.question_key,
                        "label": label,
                        "type": "colorSwitch" if field.field_type in ["checkbox", "radio"] else field.field_type,
                        "validators": {}
                    }
                    
                    if field.field_type == "text":
                        control["style"] = {"col": "7"}
                    elif field.field_type in ["checkbox", "radio"]:
                        control["style"] = {"col": "12"}
                    
                    controls.append(control)
        
        return json.dumps({"controls": controls}, indent=2)

def render_mapping_interface(extractor: FieldExtractor):
    """Render field mapping interface"""
    st.markdown("## 🎯 Field Mapping by Parts")
    
    # Controls
    col1, col2, col3 = st.columns([3, 2, 3])
    
    with col1:
        part_options = ['All Parts'] + list(st.session_state.fields_by_part.keys())
        selected_part = st.selectbox("📑 Select Part", part_options)
        st.session_state.selected_part = selected_part
    
    with col2:
        total = len(st.session_state.fields)
        mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
        st.metric("Progress", f"{mapped}/{total}", f"{mapped/total*100:.0f}%")
    
    with col3:
        cols = st.columns(3)
        if cols[0].button("🤖 Auto-Map", use_container_width=True):
            fields = st.session_state.fields
            if selected_part != 'All Parts':
                fields = st.session_state.fields_by_part.get(selected_part, [])
            
            count = 0
            for field in fields:
                if not field.is_mapped and field.field_type == 'text':
                    suggestion = extractor.suggest_mapping(field)
                    if suggestion:
                        field.db_mapping = suggestion
                        field.is_mapped = True
                        count += 1
            st.success(f"Auto-mapped {count} fields!")
            st.rerun()
        
        if cols[1].button("📋 To Quest", use_container_width=True):
            fields = st.session_state.fields
            if selected_part != 'All Parts':
                fields = st.session_state.fields_by_part.get(selected_part, [])
            
            count = 0
            for field in fields:
                if not field.is_mapped and not field.to_questionnaire:
                    field.to_questionnaire = True
                    count += 1
            st.success(f"Moved {count} fields!")
            st.rerun()
        
        if cols[2].button("🔄 Reset", use_container_width=True):
            fields = st.session_state.fields
            if selected_part != 'All Parts':
                fields = st.session_state.fields_by_part.get(selected_part, [])
            
            for field in fields:
                field.is_mapped = False
                field.db_mapping = None
                field.to_questionnaire = field.field_type in ['checkbox', 'radio']
            st.rerun()
    
    # Display fields
    parts_to_show = st.session_state.fields_by_part.items() if selected_part == 'All Parts' else [(selected_part, st.session_state.fields_by_part.get(selected_part, []))]
    
    for part_name, fields in parts_to_show:
        if not fields:
            continue
        
        part_info = st.session_state.part_structure.get(part_name, {})
        
        # Part header
        st.markdown(f'''
        <div class="part-header">
            <strong>{part_name}</strong> {part_info.get('title', '')} 
            <br>
            <small>{len(fields)} fields • Pages: {', '.join(map(str, part_info.get('pages', [])))}</small>
        </div>
        ''', unsafe_allow_html=True)
        
        # Display fields
        for idx, field in enumerate(fields):
            with st.container():
                st.markdown('<div class="mapping-row">', unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    # Field info
                    label = f"{field.item_number}. {field.field_label}" if field.item_number else field.field_label
                    st.markdown(f'<div class="field-label">{label}</div>', unsafe_allow_html=True)
                    st.markdown(f'<span class="field-type">{field.field_type.upper()}</span> • {field.field_key} • Page {field.page}', unsafe_allow_html=True)
                
                with col2:
                    unique_key = f"{part_name}_{field.field_id}_{idx}"
                    
                    # Database mapping dropdown
                    options = ["-- Select --", "📋 To Questionnaire"] + extractor.db_paths
                    
                    if field.is_mapped and field.db_mapping:
                        current_value = field.db_mapping
                    elif field.to_questionnaire:
                        current_value = "📋 To Questionnaire"
                    else:
                        current_value = "-- Select --"
                    
                    selected = st.selectbox(
                        "Map to",
                        options,
                        index=options.index(current_value) if current_value in options else 0,
                        key=f"map_{unique_key}",
                        label_visibility="collapsed"
                    )
                    
                    if selected != current_value:
                        if selected == "📋 To Questionnaire":
                            field.to_questionnaire = True
                            field.is_mapped = False
                            field.db_mapping = None
                        elif selected != "-- Select --":
                            field.db_mapping = selected
                            field.is_mapped = True
                            field.to_questionnaire = False
                        st.rerun()
                
                with col3:
                    status = field.get_status()
                    badge_class = "status-mapped" if "Mapped" in status else "status-questionnaire" if "Questionnaire" in status else "status-unmapped"
                    st.markdown(f'<span class="status-badge {badge_class}">{status}</span>', unsafe_allow_html=True)
                
                st.markdown('</div>', unsafe_allow_html=True)

def main():
    """Main application"""
    st.markdown("# 🤖 USCIS Form Reader Pro")
    
    extractor = FieldExtractor()
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 📊 Statistics")
        
        if st.session_state.pdf_processed:
            total = len(st.session_state.fields)
            mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
            quest = sum(1 for f in st.session_state.fields if f.to_questionnaire)
            
            st.metric("Total Fields", total)
            st.metric("Mapped to DB", f"{mapped} ({mapped/total*100:.0f}%)")
            st.metric("In Questionnaire", f"{quest} ({quest/total*100:.0f}%)")
            st.metric("Unmapped", total - mapped - quest)
            
            st.progress((mapped + quest) / total if total > 0 else 0)
    
    # Main tabs
    tab1, tab2, tab3 = st.tabs(["📤 Upload", "🎯 Map Fields", "📥 Export"])
    
    with tab1:
        st.markdown("## Upload USCIS PDF Form")
        uploaded_file = st.file_uploader("Choose a USCIS PDF form", type=['pdf'])
        
        if uploaded_file:
            if st.button("🚀 Extract Fields", type="primary", use_container_width=True):
                with st.spinner("Extracting fields..."):
                    if extractor.extract_from_pdf(uploaded_file):
                        st.success(f"✅ Extracted {len(st.session_state.fields)} fields from {st.session_state.form_info.get('form_number', 'form')}!")
                        
                        # Show summary
                        with st.expander("📊 Extraction Summary", expanded=True):
                            for part_name, fields in st.session_state.fields_by_part.items():
                                part_info = st.session_state.part_structure.get(part_name, {})
                                st.write(f"**{part_name}** {part_info.get('title', '')}")
                                st.write(f"- {len(fields)} fields on pages {', '.join(map(str, part_info.get('pages', [])))}")
    
    with tab2:
        if not st.session_state.pdf_processed:
            st.info("👆 Please upload and extract a PDF form first.")
        else:
            render_mapping_interface(extractor)
    
    with tab3:
        if not st.session_state.pdf_processed:
            st.info("👆 Please upload and extract a PDF form first.")
        else:
            st.markdown("## 📥 Export")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### TypeScript")
                ts_code = extractor.generate_typescript()
                st.download_button(
                    "⬇️ Download TypeScript",
                    ts_code,
                    f"{st.session_state.form_info.get('form_number', 'form')}.ts",
                    mime="text/typescript"
                )
                with st.expander("Preview"):
                    st.code(ts_code, language="typescript")
            
            with col2:
                st.markdown("### JSON")
                json_code = extractor.generate_json()
                st.download_button(
                    "⬇️ Download JSON",
                    json_code,
                    f"{st.session_state.form_info.get('form_number', 'form')}-questionnaire.json",
                    mime="application/json"
                )
                with st.expander("Preview"):
                    st.code(json_code, language="json")

if __name__ == "__main__":
    main()
