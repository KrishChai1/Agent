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
    "beneficiary": {
        "Beneficiary": ["beneficiaryFirstName", "beneficiaryLastName", "beneficiaryMiddleName",
                       "beneficiaryGender", "beneficiaryDateOfBirth", "beneficiarySsn",
                       "alienNumber", "beneficiaryCountryOfBirth", "beneficiaryCitizenOfCountry",
                       "maritalStatus", "uscisOnlineAccountNumber"],
        "MailingAddress": ["addressStreet", "addressCity", "addressState", "addressZip", 
                          "addressCountry", "addressAptSteFlrNumber", "inCareOfName"],
        "ContactInfo": ["daytimeTelephoneNumber", "mobileTelephoneNumber", "emailAddress"],
        "PassportDetails": {"Passport": ["passportNumber", "passportIssueCountry", 
                                        "passportIssueDate", "passportExpiryDate"]},
        "VisaDetails": {"Visa": ["currentNonimmigrantStatus", "dateStatusExpires", "visaNumber"]},
        "I94Details": {"I94": ["formI94ArrivalDepartureRecordNumber", "dateOfLastArrival"]}
    },
    "petitioner": {
        "": ["familyName", "givenName", "middleName", "companyOrOrganizationName"],
        "ContactInfo": ["daytimeTelephoneNumber", "mobileTelephoneNumber", "emailAddress"]
    }
}

@dataclass
class PDFField:
    widget_name: str
    field_id: str
    part_number: int
    item_number: str
    field_label: str
    field_type: str
    page: int
    value: str = ""
    db_mapping: Optional[str] = None
    is_mapped: bool = False
    to_questionnaire: bool = False

class USCISExtractor:
    def __init__(self):
        self.init_session_state()
        self.db_paths = self._build_db_paths()
    
    def init_session_state(self):
        if 'fields' not in st.session_state:
            st.session_state.fields = []
        if 'fields_by_part' not in st.session_state:
            st.session_state.fields_by_part = OrderedDict()
        if 'form_info' not in st.session_state:
            st.session_state.form_info = {}
    
    def _build_db_paths(self) -> List[str]:
        paths = []
        for obj_name, structure in DB_OBJECTS.items():
            for key, fields in structure.items():
                if isinstance(fields, list):
                    prefix = f"{obj_name}.{key}." if key else f"{obj_name}."
                    paths.extend([prefix + field for field in fields])
                elif isinstance(fields, dict):
                    for sub_key, sub_fields in fields.items():
                        prefix = f"{obj_name}.{key}.{sub_key}."
                        paths.extend([prefix + field for field in sub_fields])
        return sorted(paths)
    
    def extract_pdf(self, pdf_file) -> bool:
        try:
            # Reset state
            st.session_state.fields = []
            st.session_state.fields_by_part = OrderedDict()
            
            # Read PDF
            pdf_bytes = pdf_file.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            # Detect form type
            st.session_state.form_info = self._detect_form_type(doc)
            
            # Find all parts
            parts = self._find_parts(doc)
            
            # Extract fields from each part
            all_fields = []
            seen_widgets = set()
            
            for part_num, part_info in parts.items():
                if self._is_attorney_part(part_info['title']):
                    continue
                
                for page_num in part_info['pages']:
                    page = doc[page_num]
                    widgets = page.widgets()
                    
                    for widget in widgets:
                        if not widget.field_name or widget.field_name in seen_widgets:
                            continue
                        
                        seen_widgets.add(widget.field_name)
                        
                        # Create field
                        field = self._create_field(widget, part_num, page_num + 1)
                        
                        # Auto-move checkboxes to questionnaire
                        if field.field_type in ['checkbox', 'radio']:
                            field.to_questionnaire = True
                        
                        all_fields.append(field)
            
            doc.close()
            
            # Sort and store fields
            all_fields.sort(key=lambda f: (f.part_number, f.page))
            st.session_state.fields = all_fields
            
            # Group by part
            for field in all_fields:
                part_key = f"Part {field.part_number}"
                if part_key not in st.session_state.fields_by_part:
                    st.session_state.fields_by_part[part_key] = []
                st.session_state.fields_by_part[part_key].append(field)
            
            return True
            
        except Exception as e:
            st.error(f"Error: {str(e)}")
            return False
    
    def _detect_form_type(self, doc) -> dict:
        text = doc[0].get_text().upper()
        forms = {
            'I-539': 'Application to Extend/Change Nonimmigrant Status',
            'I-824': 'Application for Action on an Approved Application or Petition',
            'I-90': 'Application to Replace Permanent Resident Card',
            'I-129': 'Petition for a Nonimmigrant Worker',
            'I-485': 'Application to Register Permanent Residence or Adjust Status',
            'I-765': 'Application for Employment Authorization',
            'N-400': 'Application for Naturalization'
        }
        
        for form_num, title in forms.items():
            if form_num in text:
                return {'form_number': form_num, 'form_title': title, 'pages': len(doc)}
        
        return {'form_number': 'Unknown', 'form_title': 'Unknown Form', 'pages': len(doc)}
    
    def _find_parts(self, doc) -> dict:
        parts = {}
        current_part = 0
        
        for page_num in range(len(doc)):
            text = doc[page_num].get_text()
            
            # Find part headers
            matches = re.finditer(r'Part\s+(\d+)\.?\s*([^\n]*)', text, re.IGNORECASE)
            for match in matches:
                part_num = int(match.group(1))
                title = match.group(2).strip()
                
                if part_num not in parts:
                    parts[part_num] = {
                        'title': title,
                        'start_page': page_num,
                        'pages': []
                    }
                
                current_part = part_num
            
            # Add page to current part
            if current_part > 0:
                if current_part in parts:
                    parts[current_part]['pages'].append(page_num)
        
        return parts
    
    def _is_attorney_part(self, title: str) -> bool:
        keywords = ['attorney', 'preparer', 'interpreter', 'signature of the person']
        return any(kw in title.lower() for kw in keywords)
    
    def _create_field(self, widget, part_num: int, page: int) -> PDFField:
        # Extract field info
        field_name = widget.field_name
        field_type = self._get_field_type(widget.field_type)
        
        # Generate field ID
        clean_name = re.sub(r'[^\w]', '_', field_name)
        field_id = f"P{part_num}_{clean_name[:20]}"
        
        # Extract label
        label = self._extract_label(field_name)
        
        # Determine item number
        item_match = re.search(r'(\d+[a-z]?)', field_name)
        item_number = item_match.group(1) if item_match else "1"
        
        return PDFField(
            widget_name=field_name,
            field_id=field_id,
            part_number=part_num,
            item_number=item_number,
            field_label=label,
            field_type=field_type,
            page=page,
            value=widget.field_value or ''
        )
    
    def _get_field_type(self, widget_type: int) -> str:
        types = {1: "button", 2: "checkbox", 3: "radio", 4: "text", 
                5: "dropdown", 6: "list", 7: "signature"}
        return types.get(widget_type, "text")
    
    def _extract_label(self, field_name: str) -> str:
        # Clean field name
        clean = re.sub(r'form1\[0\]\.|#subform\[\d+\]\.|Page\d+\[0\]\.', '', field_name)
        clean = re.sub(r'\[\d+\]', '', clean)
        clean = clean.strip('._[]')
        
        # Common mappings
        mappings = {
            'familyname': 'Family Name (Last Name)',
            'givenname': 'Given Name (First Name)',
            'middlename': 'Middle Name',
            'anumber': 'Alien Registration Number',
            'uscisaccount': 'USCIS Online Account Number',
            'dateofbirth': 'Date of Birth',
            'ssn': 'Social Security Number',
            'passport': 'Passport Number',
            'street': 'Street Address',
            'city': 'City or Town',
            'state': 'State',
            'zip': 'ZIP Code',
            'email': 'Email Address',
            'phone': 'Phone Number'
        }
        
        clean_lower = clean.lower().replace('_', '').replace('-', '')
        for key, label in mappings.items():
            if key in clean_lower:
                return label
        
        # Convert to readable format
        label = re.sub(r'([a-z])([A-Z])', r'\1 \2', clean)
        label = label.replace('_', ' ').title()
        return label
    
    def generate_typescript(self) -> str:
        fields = st.session_state.fields
        form_name = st.session_state.form_info.get('form_number', 'Form').replace('-', '')
        
        # Group fields
        db_fields = defaultdict(list)
        quest_fields = []
        
        for field in fields:
            if field.is_mapped:
                obj = field.db_mapping.split('.')[0]
                db_fields[obj].append(field)
            else:
                quest_fields.append(field)
        
        # Build output
        ts = f"// {st.session_state.form_info.get('form_number')} Field Mappings\n"
        ts += f"// Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        ts += f"export const {form_name} = {{\n"
        
        # Database mappings
        for obj, fields_list in sorted(db_fields.items()):
            ts += f"  {obj}Data: {{\n"
            for field in fields_list:
                path = field.db_mapping.replace(f"{obj}.", "")
                suffix = ":TextBox" if field.field_type == "text" else f":{field.field_type.title()}Box"
                ts += f'    "{field.field_id}{suffix}": "{path}",\n'
            ts += "  },\n"
        
        # Questionnaire
        if quest_fields:
            ts += "  questionnaireData: {\n"
            for field in quest_fields:
                ts += f'    "{field.field_id}": {{\n'
                ts += f'      description: "{field.field_label}",\n'
                ts += f'      type: "{field.field_type}",\n'
                ts += f'      part: {field.part_number},\n'
                ts += f'      page: {field.page}\n'
                ts += "    },\n"
            ts += "  }\n"
        
        ts += "};\n"
        return ts
    
    def generate_json(self) -> str:
        quest_fields = [f for f in st.session_state.fields if not f.is_mapped]
        
        data = {
            "form": st.session_state.form_info.get('form_number'),
            "generated": datetime.now().isoformat(),
            "fields": []
        }
        
        for field in quest_fields:
            data["fields"].append({
                "id": field.field_id,
                "label": field.field_label,
                "type": field.field_type,
                "part": field.part_number,
                "page": field.page
            })
        
        return json.dumps(data, indent=2)

def main():
    st.set_page_config(page_title="USCIS Form Extractor", page_icon="📄", layout="wide")
    
    st.title("📄 USCIS Form Field Extractor")
    st.markdown("Extract and map fields from USCIS PDF forms")
    
    extractor = USCISExtractor()
    
    # Tabs
    tab1, tab2, tab3 = st.tabs(["📤 Upload", "🎯 Map", "📥 Export"])
    
    with tab1:
        uploaded_file = st.file_uploader("Choose a USCIS form PDF", type=['pdf'])
        
        if uploaded_file:
            if st.button("Extract Fields", type="primary"):
                with st.spinner("Extracting..."):
                    if extractor.extract_pdf(uploaded_file):
                        st.success(f"✅ Extracted {len(st.session_state.fields)} fields")
                        st.rerun()
        
        if st.session_state.fields:
            st.markdown("### Extracted Fields")
            
            for part, fields in st.session_state.fields_by_part.items():
                with st.expander(f"{part} ({len(fields)} fields)"):
                    df = pd.DataFrame([{
                        "ID": f.field_id,
                        "Label": f.field_label,
                        "Type": f.field_type,
                        "Page": f.page,
                        "Status": "📋" if f.to_questionnaire else ("✅" if f.is_mapped else "⚪")
                    } for f in fields])
                    st.dataframe(df, use_container_width=True, hide_index=True)
    
    with tab2:
        if not st.session_state.fields:
            st.info("Upload and extract a PDF first")
        else:
            st.markdown("### Field Mapping")
            
            # Quick actions
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Auto-map Common Fields"):
                    count = 0
                    for field in st.session_state.fields:
                        if not field.is_mapped and not field.to_questionnaire:
                            # Try to auto-map
                            label_lower = field.field_label.lower()
                            for path in extractor.db_paths:
                                if any(word in path.lower() for word in label_lower.split()):
                                    field.db_mapping = path
                                    field.is_mapped = True
                                    count += 1
                                    break
                    st.success(f"Mapped {count} fields")
                    st.rerun()
            
            with col2:
                if st.button("All Unmapped → Questionnaire"):
                    for field in st.session_state.fields:
                        if not field.is_mapped and not field.to_questionnaire:
                            field.to_questionnaire = True
                    st.rerun()
            
            # Display fields for mapping
            for field in st.session_state.fields:
                if field.field_type == 'text' and not field.is_mapped and not field.to_questionnaire:
                    col1, col2, col3 = st.columns([2, 3, 1])
                    
                    with col1:
                        st.write(f"**{field.field_label}**")
                        st.caption(f"Part {field.part_number}, Page {field.page}")
                    
                    with col2:
                        selected = st.selectbox(
                            "Map to",
                            ["-- Select --", "📋 Questionnaire"] + extractor.db_paths,
                            key=f"map_{field.field_id}"
                        )
                        
                        if selected == "📋 Questionnaire":
                            field.to_questionnaire = True
                            st.rerun()
                        elif selected != "-- Select --":
                            field.db_mapping = selected
                            field.is_mapped = True
                            st.rerun()
    
    with tab3:
        if not st.session_state.fields:
            st.info("No fields to export")
        else:
            st.markdown("### Export Options")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### TypeScript")
                ts_content = extractor.generate_typescript()
                st.download_button(
                    "Download TypeScript",
                    ts_content,
                    f"{st.session_state.form_info.get('form_number', 'form')}.ts",
                    mime="text/plain"
                )
                with st.expander("Preview"):
                    st.code(ts_content[:500] + "...", language="typescript")
            
            with col2:
                st.markdown("#### JSON")
                json_content = extractor.generate_json()
                st.download_button(
                    "Download JSON",
                    json_content,
                    f"{st.session_state.form_info.get('form_number', 'form')}.json",
                    mime="application/json"
                )
                with st.expander("Preview"):
                    st.json(json.loads(json_content))
    
    # Sidebar
    with st.sidebar:
        if st.session_state.fields:
            total = len(st.session_state.fields)
            mapped = sum(1 for f in st.session_state.fields if f.is_mapped)
            quest = sum(1 for f in st.session_state.fields if f.to_questionnaire)
            
            st.metric("Total Fields", total)
            st.metric("Mapped", mapped)
            st.metric("Questionnaire", quest)
            st.progress((mapped + quest) / total if total > 0 else 0)

if __name__ == "__main__":
    main()
