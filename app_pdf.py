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
            "emailAddress", "faxNumber", "stateBarNumber", "licensingAuthority",
            "uscisOnlineAccountNumber"
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
            "beneficiaryPrimaryEmailAddress", "maritalStatus", "uscisOnlineAccountNumber",
            "inCareOfName"
        ],
        "HomeAddress": [
            "addressStreet", "addressCity", "addressState", "addressZip", "addressCountry",
            "addressAptSteFlrNumber"
        ],
        "MailingAddress": [
            "addressStreet", "addressCity", "addressState", "addressZip", "addressCountry",
            "addressAptSteFlrNumber", "inCareOfName"
        ],
        "PhysicalAddress": [
            "addressStreet", "addressCity", "addressState", "addressZip", "addressCountry",
            "addressAptSteFlrNumber"
        ],
        "PassportDetails": {
            "Passport": [
                "passportNumber", "passportIssueCountry", "passportIssueDate", "passportExpiryDate"
            ]
        },
        "TravelDocument": [
            "travelDocumentNumber", "countryOfIssuance", "expirationDate"
        ],
        "VisaDetails": {
            "Visa": [
                "visaStatus", "visaExpiryDate", "visaNumber", "currentNonimmigrantStatus",
                "dateStatusExpires"
            ]
        },
        "I94Details": {
            "I94": [
                "i94Number", "i94ArrivalDate", "dateOfLastArrival", "formI94ArrivalDepartureRecordNumber"
            ]
        },
        "EducationDetails": [
            "nameOfSchool", "studentEXTInfoSEVISNumber"
        ],
        "ContactInfo": [
            "daytimeTelephoneNumber", "mobileTelephoneNumber", "emailAddress"
        ],
        "BiographicInfo": [
            "eyeColor", "hairColor", "heightFeet", "heightInches", "weightPounds",
            "race", "ethnicity"
        ],
        "PhysicalAddressAbroad": [
            "streetNumberName", "aptSteFlrNumber", "cityOrTown", "province",
            "postalCode", "country"
        ]
    },
    "customer": {
        "": [
            "customer_name", "customer_type_of_business", "customer_tax_id",
            "organizationName", "companyName"
        ],
        "signatory": [
            "signatory_first_name", "signatory_last_name", "signatory_job_title"
        ],
        "address": [
            "address_street", "address_city", "address_state", "address_zip"
        ]
    },
    "petitioner": {
        "": [
            "familyName", "givenName", "middleName", "companyOrOrganizationName"
        ],
        "ContactInfo": [
            "daytimeTelephoneNumber", "mobileTelephoneNumber", "emailAddress"
        ]
    }
}

@dataclass
class PDFField:
    """Represents a field extracted from PDF"""
    widget_name: str        # Raw widget name from PDF
    field_id: str          # P1_1_1a, P2_3_2b, etc.
    part_number: int       # 1, 2, 3, etc.
    item_number: str       # 1, 2a, 3.b, etc.
    field_label: str       # The actual field label/description from PDF
    field_type: str        # text, checkbox, radio, etc.
    page: int             # Page number
    value: str            # Current value if any
    db_mapping: Optional[str] = None
    is_mapped: bool = False
    to_questionnaire: bool = False

class SmartUSCISExtractor:
    """Smart USCIS Form PDF Field Extractor"""
    
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
        if 'current_field_index' not in st.session_state:
            st.session_state.current_field_index = 0
        if 'one_by_one_mode' not in st.session_state:
            st.session_state.one_by_one_mode = False
    
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
    
    def extract_fields_from_pdf(self, pdf_file) -> bool:
        """Extract all fields from PDF with proper structure"""
        try:
            # Reset state
            st.session_state.extracted_fields = []
            st.session_state.fields_by_part = OrderedDict()
            st.session_state.current_field_index = 0
            
            # Read PDF
            pdf_bytes = pdf_file.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            # Detect form type
            form_info = self._detect_form_type(doc)
            st.session_state.form_info = form_info
            
            # Extract text from all pages to understand structure
            page_texts = {}
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_texts[page_num] = page.get_text()
            
            # Extract all fields with context
            all_fields = []
            field_counter = defaultdict(lambda: defaultdict(int))
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_text = page_texts[page_num]
                
                # Find current part from page text
                current_part = self._detect_current_part(page_text, page_num, page_texts)
                
                # Skip if no valid part or attorney section
                if not current_part or current_part == 0:
                    continue
                
                # Get all widgets on this page
                widgets = page.widgets()
                
                # Group widgets by their position to associate with item numbers
                widgets_by_position = []
                for widget in widgets:
                    if widget.field_name:
                        widgets_by_position.append({
                            'widget': widget,
                            'y_pos': widget.rect.y0,
                            'x_pos': widget.rect.x0,
                            'page': page_num + 1
                        })
                
                # Sort by position (top to bottom, left to right)
                widgets_by_position.sort(key=lambda w: (w['y_pos'], w['x_pos']))
                
                # Extract item numbers and labels from page text
                item_mapping = self._extract_items_from_text(page_text, current_part)
                
                # Process widgets and match with items
                for widget_data in widgets_by_position:
                    widget = widget_data['widget']
                    
                    # Skip attorney fields
                    if self._is_attorney_field(widget.field_name):
                        continue
                    
                    # Find best matching item
                    item_info = self._match_widget_to_item(widget, widget_data['y_pos'], item_mapping, page_text)
                    
                    if not item_info:
                        # Create default item info
                        field_counter[current_part]['default'] += 1
                        item_info = {
                            'number': str(field_counter[current_part]['default']),
                            'label': self._extract_field_label(widget, page_text)
                        }
                    
                    # Generate field ID
                    field_counter[current_part][item_info['number']] += 1
                    sub_index = field_counter[current_part][item_info['number']]
                    
                    if sub_index == 1:
                        field_id = f"P{current_part}_{item_info['number']}"
                    else:
                        # For multiple fields in same item (like name fields)
                        field_id = f"P{current_part}_{item_info['number']}_{chr(96 + sub_index)}"
                    
                    # Get field type
                    field_type = self._get_field_type(widget.field_type)
                    
                    # Create field object
                    field = PDFField(
                        widget_name=widget.field_name,
                        field_id=field_id,
                        part_number=current_part,
                        item_number=item_info['number'],
                        field_label=item_info['label'],
                        field_type=field_type,
                        page=widget_data['page'],
                        value=widget.field_value or ''
                    )
                    
                    # Auto-move checkboxes to questionnaire
                    if field_type in ['checkbox', 'radio']:
                        field.to_questionnaire = True
                    
                    all_fields.append(field)
            
            doc.close()
            
            # Sort fields properly
            all_fields.sort(key=lambda f: (
                f.part_number,
                self._parse_item_number_for_sort(f.item_number),
                f.field_id
            ))
            
            # Store fields
            st.session_state.extracted_fields = all_fields
            
            # Group by part
            for field in all_fields:
                part_key = f"Part {field.part_number}"
                if part_key not in st.session_state.fields_by_part:
                    st.session_state.fields_by_part[part_key] = []
                st.session_state.fields_by_part[part_key].append(field)
            
            return True
            
        except Exception as e:
            st.error(f"Error extracting PDF: {str(e)}")
            import traceback
            st.text(traceback.format_exc())
            return False
    
    def _detect_form_type(self, doc) -> dict:
        """Detect form type from PDF"""
        first_page_text = doc[0].get_text().upper()
        
        # Common USCIS forms
        forms = {
            'I-539': 'Application to Extend/Change Nonimmigrant Status',
            'I-824': 'Application for Action on an Approved Application or Petition',
            'I-90': 'Application to Replace Permanent Resident Card',
            'I-129': 'Petition for a Nonimmigrant Worker',
            'I-130': 'Petition for Alien Relative',
            'I-485': 'Application to Register Permanent Residence or Adjust Status',
            'I-765': 'Application for Employment Authorization',
            'N-400': 'Application for Naturalization'
        }
        
        detected_form = None
        for form_number, form_title in forms.items():
            if form_number in first_page_text or form_number.replace('-', '') in first_page_text:
                detected_form = form_number
                break
        
        return {
            'form_number': detected_form or 'Unknown',
            'form_title': forms.get(detected_form, 'Unknown Form'),
            'total_pages': len(doc)
        }
    
    def _detect_current_part(self, page_text: str, page_num: int, all_page_texts: dict) -> Optional[int]:
        """Detect which part we're in based on page text"""
        # Look for Part headers
        part_match = re.search(r'Part\s+(\d+)\.?\s+[A-Z]', page_text)
        if part_match:
            return int(part_match.group(1))
        
        # If not found on current page, check previous pages
        for i in range(page_num - 1, -1, -1):
            part_match = re.search(r'Part\s+(\d+)\.?\s+[A-Z]', all_page_texts[i])
            if part_match:
                return int(part_match.group(1))
        
        return None
    
    def _is_attorney_field(self, field_name: str) -> bool:
        """Check if field is attorney/preparer related"""
        attorney_keywords = [
            'attorney', 'preparer', 'representative', 'g-28', 'g28',
            'bar number', 'bia', 'accredited'
        ]
        
        field_lower = field_name.lower()
        return any(keyword in field_lower for keyword in attorney_keywords)
    
    def _extract_items_from_text(self, page_text: str, part_number: int) -> List[dict]:
        """Extract item numbers and labels from page text"""
        items = []
        
        # Patterns for item detection
        patterns = [
            r'(\d+)\.\s+([A-Z][^\n]+)',  # 1. Your Full Legal Name
            r'(\d+[a-z]?)\.\s+([A-Z][^\n]+)',  # 2a. Family Name
            r'Item Number (\d+[a-z]?)\.\s+([^\n]+)',  # Item Number 1. 
            r'(\d+)\.\s*([A-Za-z][^\n]+)',  # More flexible pattern
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, page_text)
            for match in matches:
                item_num = match.group(1)
                item_label = match.group(2).strip()
                
                # Clean up label
                item_label = re.sub(r'\s+', ' ', item_label)
                item_label = item_label.split('(')[0].strip()  # Remove parenthetical info
                
                items.append({
                    'number': item_num,
                    'label': item_label,
                    'position': match.start()
                })
        
        # Sort by position
        items.sort(key=lambda x: x['position'])
        
        return items
    
    def _match_widget_to_item(self, widget, y_pos: float, item_mapping: List[dict], page_text: str) -> Optional[dict]:
        """Match a widget to its item number and label"""
        # Try to find the closest item above this widget
        widget_name_lower = widget.field_name.lower()
        
        # Check for specific field patterns
        if 'familyname' in widget_name_lower or 'lastname' in widget_name_lower:
            return {'number': '1a', 'label': 'Family Name (Last Name)'}
        elif 'givenname' in widget_name_lower or 'firstname' in widget_name_lower:
            return {'number': '1b', 'label': 'Given Name (First Name)'}
        elif 'middlename' in widget_name_lower:
            return {'number': '1c', 'label': 'Middle Name'}
        elif 'alien' in widget_name_lower and 'number' in widget_name_lower:
            return {'number': '2', 'label': 'Alien Registration Number (A-Number)'}
        elif 'uscis' in widget_name_lower and 'online' in widget_name_lower:
            return {'number': '3', 'label': 'USCIS Online Account Number'}
        elif 'street' in widget_name_lower or 'address' in widget_name_lower:
            return {'number': '4', 'label': 'Mailing Address'}
        elif 'city' in widget_name_lower:
            return {'number': '4d', 'label': 'City or Town'}
        elif 'state' in widget_name_lower:
            return {'number': '4e', 'label': 'State'}
        elif 'zip' in widget_name_lower:
            return {'number': '4f', 'label': 'ZIP Code'}
        
        # If no specific match, use item mapping
        if item_mapping:
            return item_mapping[0]  # Default to first item if unsure
        
        return None
    
    def _extract_field_label(self, widget, page_text: str) -> str:
        """Extract field label from widget or page context"""
        # First try widget display name
        if widget.field_display and widget.field_display.strip():
            return widget.field_display.strip()
        
        # Try to extract from field name
        field_name = widget.field_name
        
        # Remove common prefixes
        prefixes = ['form1[0].', '#subform[0].', 'Page1[0].', 'Pt', 'Part']
        for prefix in prefixes:
            if field_name.startswith(prefix):
                field_name = field_name[len(prefix):]
        
        # Extract meaningful part
        parts = field_name.split('.')
        if parts:
            label = parts[-1]
            # Convert camelCase to readable
            label = re.sub(r'([a-z])([A-Z])', r'\1 \2', label)
            label = label.replace('_', ' ').strip()
            return label.title()
        
        return "Field"
    
    def _parse_item_number_for_sort(self, item_num: str) -> tuple:
        """Parse item number for proper sorting (e.g., '2a' -> (2, 'a'))"""
        match = re.match(r'(\d+)([a-zA-Z]?)', str(item_num))
        if match:
            num = int(match.group(1))
            letter = match.group(2) or ''
            return (num, letter)
        return (999, item_num)
    
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
    
    def generate_typescript(self, fields: List[PDFField]) -> str:
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
                field_suffix = ":TextBox" if field.field_type == "text" else f":{field.field_type.title()}Box"
                ts += f'    "{field.field_id}{field_suffix}": "{path}",\n'
            ts = ts.rstrip(',\n') + '\n'
            ts += "  },\n"
        
        # Add questionnaire fields
        if questionnaire_fields:
            ts += "  questionnaireData: {\n"
            for field in questionnaire_fields:
                ts += f'    "{field.field_id}": {{\n'
                ts += f'      description: "{field.field_label}",\n'
                ts += f'      fieldType: "{field.field_type}",\n'
                ts += f'      part: "Part {field.part_number}",\n'
                ts += f'      item: "{field.item_number}",\n'
                ts += f'      page: {field.page},\n'
                ts += f'      required: true\n'
                ts += "    },\n"
            ts = ts.rstrip(',\n') + '\n'
            ts += "  }\n"
        
        ts = ts.rstrip(',\n') + '\n'
        ts += "};\n"
        
        return ts
    
    def generate_json(self, fields: List[PDFField]) -> str:
        """Generate JSON for questionnaire fields"""
        questionnaire_fields = [f for f in fields if not f.is_mapped]
        
        # Group by part
        by_part = defaultdict(list)
        for field in questionnaire_fields:
            by_part[field.part_number].append(field)
        
        # Build JSON structure
        data = {
            "form": st.session_state.form_info.get('form_number', 'Unknown'),
            "title": st.session_state.form_info.get('form_title', 'Unknown Form'),
            "generated": datetime.now().isoformat(),
            "totalFields": len(questionnaire_fields),
            "sections": []
        }
        
        for part_num in sorted(by_part.keys()):
            section = {
                "part": f"Part {part_num}",
                "fieldCount": len(by_part[part_num]),
                "fields": []
            }
            
            for field in by_part[part_num]:
                field_data = {
                    "id": field.field_id,
                    "description": field.field_label,
                    "item": field.item_number,
                    "type": field.field_type,
                    "page": field.page
                }
                
                section["fields"].append(field_data)
            
            data["sections"].append(section)
        
        return json.dumps(data, indent=2)

def render_header():
    """Render application header"""
    st.markdown("""
    <style>
        .main-header {
            background: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%);
            color: white;
            padding: 2rem;
            border-radius: 10px;
            margin-bottom: 2rem;
            text-align: center;
        }
        .field-card {
            background: white;
            border: 1px solid #e5e7eb;
            padding: 1.5rem;
            margin: 1rem 0;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .field-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }
        .field-info {
            flex: 1;
        }
        .field-id {
            font-weight: bold;
            color: #2563eb;
            font-size: 1.1rem;
        }
        .field-label {
            font-size: 1rem;
            color: #374151;
            margin: 0.5rem 0;
        }
        .field-meta {
            font-size: 0.875rem;
            color: #6b7280;
        }
        .status-badge {
            padding: 0.25rem 0.75rem;
            border-radius: 999px;
            font-size: 0.875rem;
            font-weight: 500;
        }
        .status-mapped { background: #d1fae5; color: #065f46; }
        .status-questionnaire { background: #fed7aa; color: #92400e; }
        .status-unmapped { background: #fee2e2; color: #991b1b; }
        .part-header {
            background: #f3f4f6;
            padding: 1rem;
            margin: 1rem 0;
            border-radius: 8px;
            border-left: 4px solid #2563eb;
            font-weight: bold;
        }
        .progress-indicator {
            background: #e5e7eb;
            height: 8px;
            border-radius: 4px;
            margin: 1rem 0;
            overflow: hidden;
        }
        .progress-fill {
            background: #2563eb;
            height: 100%;
            transition: width 0.3s ease;
        }
        .nav-buttons {
            display: flex;
            justify-content: space-between;
            margin: 2rem 0;
            gap: 1rem;
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="main-header">
        <h1>📄 Smart USCIS Form Field Extractor</h1>
        <p>Accurate extraction with proper Part and Item structure</p>
    </div>
    """, unsafe_allow_html=True)

def render_upload_tab(extractor: SmartUSCISExtractor):
    """Upload and extract PDF fields"""
    st.markdown("## 📤 Upload USCIS Form")
    
    uploaded_file = st.file_uploader(
        "Choose a USCIS form PDF file",
        type=['pdf'],
        help="Upload any USCIS form (I-539, I-824, I-90, etc.)"
    )
    
    if uploaded_file:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.info(f"📄 **File:** {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")
        with col2:
            if st.button("🔍 Extract Fields", type="primary", use_container_width=True):
                with st.spinner("Extracting fields from PDF..."):
                    if extractor.extract_fields_from_pdf(uploaded_file):
                        st.success(f"✅ Extracted {len(st.session_state.extracted_fields)} fields!")
                        st.rerun()
    
    # Display extracted fields
    if st.session_state.extracted_fields:
        st.markdown("---")
        st.markdown("## 📊 Extracted Fields Overview")
        
        # Summary
        fields = st.session_state.extracted_fields
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("Form", st.session_state.form_info.get('form_number', 'Unknown'))
        with col2:
            st.metric("Total Fields", len(fields))
        with col3:
            st.metric("Parts", len(st.session_state.fields_by_part))
        with col4:
            checkboxes = sum(1 for f in fields if f.field_type in ['checkbox', 'radio'])
            st.metric("Checkboxes", checkboxes)
        with col5:
            st.metric("Pages", st.session_state.form_info.get('total_pages', 0))
        
        # Display by parts
        st.markdown("### 📑 Fields by Part")
        
        for part, part_fields in st.session_state.fields_by_part.items():
            with st.expander(f"**{part}** ({len(part_fields)} fields)", expanded=(part == "Part 1")):
                # Create a clean table view
                df_data = []
                for field in part_fields:
                    df_data.append({
                        "Field ID": field.field_id,
                        "Item": field.item_number,
                        "Description": field.field_label,
                        "Type": field.field_type,
                        "Page": field.page,
                        "Status": "📋 Quest" if field.to_questionnaire else "⚪ Unmapped"
                    })
                
                df = pd.DataFrame(df_data)
                st.dataframe(df, use_container_width=True, hide_index=True)

def render_mapping_tab(extractor: SmartUSCISExtractor):
    """Map fields - either one by one or all at once"""
    if not st.session_state.extracted_fields:
        st.info("👆 Please upload and extract a PDF form first")
        return
    
    st.markdown("## 🎯 Field Mapping")
    
    # Mode selection
    col1, col2 = st.columns([2, 1])
    with col1:
        mapping_mode = st.radio(
            "Mapping Mode",
            ["View All Fields", "One by One"],
            horizontal=True
        )
        st.session_state.one_by_one_mode = (mapping_mode == "One by One")
    
    with col2:
        # Quick stats
        fields = st.session_state.extracted_fields
        mapped = sum(1 for f in fields if f.is_mapped)
        quest = sum(1 for f in fields if f.to_questionnaire)
        unmapped = len(fields) - mapped - quest
        
        st.metric("Progress", f"{mapped + quest}/{len(fields)}")
    
    # Quick actions
    st.markdown("### ⚡ Quick Actions")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📋 All Unmapped → Questionnaire"):
            for field in fields:
                if not field.is_mapped and not field.to_questionnaire:
                    field.to_questionnaire = True
            st.success("Moved all unmapped to questionnaire")
            st.rerun()
    
    with col2:
        if st.button("☑️ All Checkboxes → Questionnaire"):
            count = 0
            for field in fields:
                if field.field_type in ['checkbox', 'radio'] and not field.to_questionnaire:
                    field.to_questionnaire = True
                    field.is_mapped = False
                    field.db_mapping = None
                    count += 1
            if count > 0:
                st.success(f"Moved {count} checkboxes to questionnaire")
                st.rerun()
    
    with col3:
        if st.button("🔄 Reset All"):
            for field in fields:
                field.is_mapped = False
                field.to_questionnaire = False
                field.db_mapping = None
            st.session_state.current_field_index = 0
            st.rerun()
    
    st.markdown("---")
    
    if st.session_state.one_by_one_mode:
        render_one_by_one_mapping(extractor)
    else:
        render_all_fields_mapping(extractor)

def render_one_by_one_mapping(extractor: SmartUSCISExtractor):
    """Render one-by-one field mapping"""
    fields = st.session_state.extracted_fields
    current_idx = st.session_state.current_field_index
    
    # Progress
    progress = current_idx / len(fields) if fields else 0
    st.markdown(f"""
    <div class="progress-indicator">
        <div class="progress-fill" style="width: {progress * 100}%"></div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown(f"### Field {current_idx + 1} of {len(fields)}")
    
    if current_idx >= len(fields):
        st.success("✅ All fields have been processed!")
        if st.button("Start Over", use_container_width=True):
            st.session_state.current_field_index = 0
            st.rerun()
        return
    
    # Current field
    field = fields[current_idx]
    
    # Field card
    st.markdown('<div class="field-card">', unsafe_allow_html=True)
    
    # Field information
    st.markdown(f'<div class="field-id">Part {field.part_number}, Item {field.item_number}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="field-label">{field.field_label}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="field-meta">Field ID: {field.field_id} | Type: {field.field_type} | Page: {field.page}</div>', unsafe_allow_html=True)
    
    # Current status
    if field.is_mapped:
        st.success(f"✅ Already mapped to: {field.db_mapping}")
    elif field.to_questionnaire:
        st.warning("📋 Already in Questionnaire")
    
    # Mapping options
    st.markdown("### 🎯 Map this field to:")
    
    # Smart suggestions based on field label
    suggestions = get_smart_suggestions(field.field_label, field.item_number, extractor.db_paths)
    
    if suggestions:
        st.markdown("**🤖 Suggestions:**")
        for i, suggestion in enumerate(suggestions[:3]):
            if st.button(f"→ {suggestion}", key=f"sugg_{current_idx}_{i}"):
                field.db_mapping = suggestion
                field.is_mapped = True
                field.to_questionnaire = False
                st.success(f"Mapped to: {suggestion}")
                st.session_state.current_field_index += 1
                st.rerun()
    
    # Manual selection
    st.markdown("**Manual Selection:**")
    col1, col2 = st.columns([3, 1])
    
    with col1:
        selected = st.selectbox(
            "Select database field",
            ["-- Select --"] + extractor.db_paths,
            key=f"select_{current_idx}"
        )
    
    with col2:
        if selected != "-- Select --":
            if st.button("Apply", use_container_width=True):
                field.db_mapping = selected
                field.is_mapped = True
                field.to_questionnaire = False
                st.session_state.current_field_index += 1
                st.rerun()
    
    # Or send to questionnaire
    if st.button("📋 Send to Questionnaire", use_container_width=True):
        field.to_questionnaire = True
        field.is_mapped = False
        field.db_mapping = None
        st.session_state.current_field_index += 1
        st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Navigation
    st.markdown('<div class="nav-buttons">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if current_idx > 0:
            if st.button("⬅️ Previous", use_container_width=True):
                st.session_state.current_field_index -= 1
                st.rerun()
    
    with col2:
        if st.button("⏭️ Skip", use_container_width=True):
            st.session_state.current_field_index += 1
            st.rerun()
    
    with col3:
        remaining = len(fields) - current_idx - 1
        st.caption(f"{remaining} fields remaining")
    
    st.markdown('</div>', unsafe_allow_html=True)

def render_all_fields_mapping(extractor: SmartUSCISExtractor):
    """Render all fields for mapping"""
    fields = st.session_state.extracted_fields
    
    # Filter options
    col1, col2, col3 = st.columns(3)
    
    with col1:
        parts = ["All Parts"] + list(st.session_state.fields_by_part.keys())
        selected_part = st.selectbox("Filter by Part", parts)
    
    with col2:
        field_types = ["All Types"] + list(set(f.field_type for f in fields))
        selected_type = st.selectbox("Filter by Type", field_types)
    
    with col3:
        status_options = ["All", "Unmapped Only", "Mapped Only", "Questionnaire Only"]
        selected_status = st.selectbox("Filter by Status", status_options)
    
    # Apply filters
    display_fields = fields.copy()
    
    if selected_part != "All Parts":
        display_fields = [f for f in display_fields if f"Part {f.part_number}" == selected_part]
    
    if selected_type != "All Types":
        display_fields = [f for f in display_fields if f.field_type == selected_type]
    
    if selected_status == "Unmapped Only":
        display_fields = [f for f in display_fields if not f.is_mapped and not f.to_questionnaire]
    elif selected_status == "Mapped Only":
        display_fields = [f for f in display_fields if f.is_mapped]
    elif selected_status == "Questionnaire Only":
        display_fields = [f for f in display_fields if f.to_questionnaire]
    
    st.markdown(f"### Showing {len(display_fields)} fields")
    
    # Display fields
    for field in display_fields:
        with st.container():
            col1, col2, col3 = st.columns([2.5, 3, 1])
            
            with col1:
                st.markdown(f"**{field.field_id}** - Part {field.part_number}, Item {field.item_number}")
                st.markdown(f"{field.field_label}")
                st.caption(f"Type: {field.field_type} | Page: {field.page}")
            
            with col2:
                if field.is_mapped:
                    st.success(f"✅ {field.db_mapping}")
                elif field.to_questionnaire:
                    st.warning("📋 Questionnaire")
                else:
                    # Quick mapping
                    options = ["-- Select --", "📋 Questionnaire"] + extractor.db_paths
                    selected = st.selectbox(
                        "Map to",
                        options,
                        key=f"map_{field.field_id}",
                        label_visibility="collapsed"
                    )
                    
                    if selected == "📋 Questionnaire":
                        field.to_questionnaire = True
                        st.rerun()
                    elif selected != "-- Select --":
                        field.db_mapping = selected
                        field.is_mapped = True
                        st.rerun()
            
            with col3:
                if field.is_mapped or field.to_questionnaire:
                    if st.button("Reset", key=f"reset_{field.field_id}"):
                        field.is_mapped = False
                        field.to_questionnaire = False
                        field.db_mapping = None
                        st.rerun()
            
            st.divider()

def get_smart_suggestions(field_label: str, item_number: str, db_paths: List[str]) -> List[str]:
    """Get smart mapping suggestions based on field label"""
    suggestions = []
    label_lower = field_label.lower()
    
    # Direct mappings
    mappings = {
        'family name': 'beneficiary.Beneficiary.beneficiaryLastName',
        'last name': 'beneficiary.Beneficiary.beneficiaryLastName',
        'given name': 'beneficiary.Beneficiary.beneficiaryFirstName',
        'first name': 'beneficiary.Beneficiary.beneficiaryFirstName',
        'middle name': 'beneficiary.Beneficiary.beneficiaryMiddleName',
        'alien registration number': 'beneficiary.Beneficiary.alienNumber',
        'a-number': 'beneficiary.Beneficiary.alienNumber',
        'uscis online account number': 'beneficiary.Beneficiary.uscisOnlineAccountNumber',
        'date of birth': 'beneficiary.Beneficiary.beneficiaryDateOfBirth',
        'country of birth': 'beneficiary.Beneficiary.beneficiaryCountryOfBirth',
        'country of citizenship': 'beneficiary.Beneficiary.beneficiaryCitizenOfCountry',
        'social security number': 'beneficiary.Beneficiary.beneficiarySsn',
        'gender': 'beneficiary.Beneficiary.beneficiaryGender',
        'marital status': 'beneficiary.Beneficiary.maritalStatus',
        'daytime telephone': 'beneficiary.ContactInfo.daytimeTelephoneNumber',
        'mobile telephone': 'beneficiary.ContactInfo.mobileTelephoneNumber',
        'email address': 'beneficiary.ContactInfo.emailAddress',
        'street number and name': 'beneficiary.MailingAddress.addressStreet',
        'city or town': 'beneficiary.MailingAddress.addressCity',
        'state': 'beneficiary.MailingAddress.addressState',
        'zip code': 'beneficiary.MailingAddress.addressZip',
        'passport number': 'beneficiary.PassportDetails.Passport.passportNumber',
        'travel document number': 'beneficiary.TravelDocument.travelDocumentNumber',
        'current nonimmigrant status': 'beneficiary.VisaDetails.Visa.currentNonimmigrantStatus',
        'date status expires': 'beneficiary.VisaDetails.Visa.dateStatusExpires',
        'form i-94': 'beneficiary.I94Details.I94.formI94ArrivalDepartureRecordNumber',
        'sevis': 'beneficiary.EducationDetails.studentEXTInfoSEVISNumber'
    }
    
    # Check for direct matches
    for key, path in mappings.items():
        if key in label_lower:
            suggestions.append(path)
    
    # Check for partial matches
    if not suggestions:
        for path in db_paths:
            path_parts = path.split('.')
            field_name = path_parts[-1].lower()
            
            # Score based on similarity
            if any(word in field_name for word in label_lower.split()):
                suggestions.append(path)
    
    return suggestions[:3]  # Return top 3 suggestions

def render_export_tab(extractor: SmartUSCISExtractor):
    """Export mapped fields"""
    if not st.session_state.extracted_fields:
        st.info("👆 Please extract and map fields first")
        return
    
    st.markdown("## 📥 Export")
    
    # Summary
    fields = st.session_state.extracted_fields
    mapped = sum(1 for f in fields if f.is_mapped)
    questionnaire = sum(1 for f in fields if f.to_questionnaire)
    unmapped = len(fields) - mapped - questionnaire
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Database Mapped", mapped)
    with col2:
        st.metric("Questionnaire", questionnaire)
    with col3:
        st.metric("Unmapped", unmapped)
    
    if unmapped > 0:
        st.warning(f"⚠️ {unmapped} unmapped fields will be added to questionnaire on export")
    
    st.markdown("---")
    
    # Export options
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📝 TypeScript Export")
        
        ts_content = extractor.generate_typescript(fields)
        
        st.download_button(
            label="📥 Download TypeScript",
            data=ts_content,
            file_name=f"{st.session_state.form_info.get('form_number', 'form').replace('-', '')}.ts",
            mime="text/plain",
            use_container_width=True
        )
        
        with st.expander("Preview"):
            st.code(ts_content[:1000] + "\n...", language="typescript")
    
    with col2:
        st.markdown("### 📋 JSON Questionnaire")
        
        # Auto-add unmapped to questionnaire
        for field in fields:
            if not field.is_mapped and not field.to_questionnaire:
                field.to_questionnaire = True
        
        json_content = extractor.generate_json(fields)
        
        st.download_button(
            label="📥 Download JSON",
            data=json_content,
            file_name=f"{st.session_state.form_info.get('form_number', 'form')}-questionnaire.json",
            mime="application/json",
            use_container_width=True
        )
        
        with st.expander("Preview"):
            st.json(json.loads(json_content))

def main():
    st.set_page_config(
        page_title="Smart USCIS Form Extractor",
        page_icon="📄",
        layout="wide"
    )
    
    # Initialize extractor
    extractor = SmartUSCISExtractor()
    
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
        st.markdown("## 📊 Status")
        
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
                complete = sum(1 for f in part_fields if f.is_mapped or f.to_questionnaire)
                st.write(f"**{part}**: {complete}/{len(part_fields)}")
        
        st.markdown("---")
        st.markdown("### ℹ️ How it Works")
        st.markdown("""
        1. **Upload** USCIS form PDF
        2. **Extract** with proper Part/Item structure
        3. **Map** one-by-one or view all
        4. **Export** TypeScript & JSON
        
        **Features:**
        - Accurate item number extraction
        - Smart field label detection
        - AI-powered suggestions
        - Checkbox auto-handling
        """)

if __name__ == "__main__":
    main()
