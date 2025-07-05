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
class PDFField:
    """Represents a field extracted from PDF"""
    raw_field_name: str     # Original full field name from PDF
    field_id: str          # P1_1, P2_1, etc.
    part_number: int       # 1, 2, 3, etc.
    line_number: str       # 1a, 2b, etc.
    field_label: str       # FamilyName, AlienNumber, etc.
    description: str       # Human readable description
    field_type: str        # text, checkbox, radio, etc.
    page: int             # Page number
    value: str            # Current value if any
    db_mapping: Optional[str] = None
    is_mapped: bool = False
    to_questionnaire: bool = False

class USCISFormExtractor:
    """USCIS Form PDF Field Extractor"""
    
    def __init__(self):
        self.init_session_state()
        self.db_paths = self._build_database_paths()
        
        # Field label to description mapping
        self.field_descriptions = {
            'AlienNumber': 'Alien Registration Number (A-Number)',
            'USCISOnlineAcctNumber': 'USCIS Online Account Number',
            'FamilyName': 'Family Name (Last Name)',
            'GivenName': 'Given Name (First Name)',
            'MiddleName': 'Middle Name',
            'InCareOfName': 'In Care Of Name',
            'StreetNumberName': 'Street Number and Name',
            'AptSteFlrNumber': 'Apt./Ste./Flr. Number',
            'CityOrTown': 'City or Town',
            'State': 'State',
            'ZipCode': 'ZIP Code',
            'Province': 'Province',
            'PostalCode': 'Postal Code',
            'Country': 'Country',
            'DateOfBirth': 'Date of Birth',
            'CountryOfBirth': 'Country of Birth',
            'CountryOfCitizenship': 'Country of Citizenship or Nationality',
            'SSN': 'U.S. Social Security Number',
            'DateFrom': 'Date From',
            'DateTo': 'Date To',
            'EmployerName': 'Employer or Company Name',
            'YourOccupation': 'Your Occupation',
            'CurrentAnnualSalary': 'Current Annual Salary',
            'StateOrProvince': 'State or Province',
            'Gender': 'Gender',
            'MaritalStatus': 'Marital Status',
            'PreviousArrivalDate': 'Date of Previous Arrival',
            'PassportNumber': 'Passport Number',
            'TravelDocumentNumber': 'Travel Document Number',
            'CountryOfIssuance': 'Country of Issuance',
            'ExpirationDate': 'Expiration Date',
            'CurrentNonimmigrantStatus': 'Current Nonimmigrant Status',
            'DateStatusExpires': 'Date Status Expires',
            'StudentEXTInfoSEVISNumber': 'SEVIS Number',
            'ReceiptNumber': 'Receipt Number',
            'Priority Date': 'Priority Date'
        }
    
    def init_session_state(self):
        """Initialize session state"""
        if 'extracted_fields' not in st.session_state:
            st.session_state.extracted_fields = []
        if 'fields_by_part' not in st.session_state:
            st.session_state.fields_by_part = OrderedDict()
        if 'form_info' not in st.session_state:
            st.session_state.form_info = {}
        if 'raw_field_names' not in st.session_state:
            st.session_state.raw_field_names = []
    
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
        """Extract all fields from PDF with proper part detection"""
        try:
            # Reset state
            st.session_state.extracted_fields = []
            st.session_state.fields_by_part = OrderedDict()
            st.session_state.raw_field_names = []
            
            # Read PDF
            pdf_bytes = pdf_file.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            # Detect form type
            form_info = self._detect_form_type(doc)
            st.session_state.form_info = form_info
            
            # Extract all fields
            all_fields = []
            raw_fields = []
            
            # Collect all widgets first
            for page_num in range(len(doc)):
                page = doc[page_num]
                for widget in page.widgets():
                    if widget.field_name:
                        raw_fields.append({
                            'name': widget.field_name,
                            'type': widget.field_type,
                            'value': widget.field_value or '',
                            'page': page_num + 1,
                            'widget': widget
                        })
            
            # Store raw field names for debugging
            st.session_state.raw_field_names = [f['name'] for f in raw_fields]
            
            # Process fields and extract part information
            field_counter = defaultdict(int)
            
            for raw_field in raw_fields:
                # Parse field information
                field_info = self._parse_field_name(raw_field['name'])
                
                # Skip if no part number or part 0
                if not field_info['part_number'] or field_info['part_number'] == 0:
                    continue
                
                # Skip attorney/preparer fields
                if self._is_attorney_field(raw_field['name'], field_info):
                    continue
                
                # Generate field ID
                part_key = f"Part {field_info['part_number']}"
                field_counter[part_key] += 1
                field_id = f"P{field_info['part_number']}_{field_counter[part_key]}"
                
                # Get field type
                field_type = self._get_field_type(raw_field['type'])
                
                # Generate description
                description = self._generate_description(field_info)
                
                # Create field object
                field = PDFField(
                    raw_field_name=raw_field['name'],
                    field_id=field_id,
                    part_number=field_info['part_number'],
                    line_number=field_info['line_number'],
                    field_label=field_info['field_label'],
                    description=description,
                    field_type=field_type,
                    page=raw_field['page'],
                    value=raw_field['value']
                )
                
                # Auto-move checkboxes to questionnaire
                if field_type in ['checkbox', 'radio']:
                    field.to_questionnaire = True
                
                all_fields.append(field)
            
            doc.close()
            
            # Sort fields by part and line number
            all_fields.sort(key=lambda f: (f.part_number, f.line_number or 'ZZ', f.field_id))
            
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
            'I-90': 'Application to Replace Permanent Resident Card',
            'I-129': 'Petition for a Nonimmigrant Worker',
            'I-130': 'Petition for Alien Relative',
            'I-131': 'Application for Travel Document',
            'I-140': 'Immigrant Petition for Alien Workers',
            'I-485': 'Application to Register Permanent Residence or Adjust Status',
            'I-539': 'Application To Extend/Change Nonimmigrant Status',
            'I-765': 'Application for Employment Authorization',
            'I-821': 'Application for Temporary Protected Status',
            'N-400': 'Application for Naturalization',
            'N-600': 'Application for Certificate of Citizenship'
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
    
    def _parse_field_name(self, field_name: str) -> dict:
        """Parse USCIS field name to extract part, line, and field information"""
        result = {
            'part_number': None,
            'line_number': None,
            'field_label': None,
            'original': field_name
        }
        
        # Common USCIS field patterns
        patterns = [
            # Pattern: Part1[0].Line1a[0].FamilyName[0]
            r'Part(\d+)\[?\d*\]?\.Line(\d+[a-zA-Z]?)\[?\d*\]?\.([A-Za-z]+)',
            # Pattern: Pt1Line1a_FamilyName[0]
            r'Pt(\d+)Line(\d+[a-zA-Z]?)_([A-Za-z]+)',
            # Pattern: Part1Line1aFamilyName
            r'Part(\d+)Line(\d+[a-zA-Z]?)([A-Z][A-Za-z]+)',
            # Pattern: Pt1Line1a_FamilyName
            r'Pt(\d+)Line(\d+[a-zA-Z]?)_([A-Za-z]+)',
            # Pattern: Part1_Line1a_FamilyName
            r'Part(\d+)_Line(\d+[a-zA-Z]?)_([A-Za-z]+)',
            # Pattern with subform: form1[0].#subform[0].Pt1Line1a_AlienNumber[0]
            r'Pt(\d+)Line(\d+[a-zA-Z]?)_([A-Za-z]+)\[?\d*\]?$',
            # Pattern: Part1_1a_FamilyName
            r'Part(\d+)_(\d+[a-zA-Z]?)_([A-Za-z]+)',
            # Simple part pattern: Part1[0] or Pt1Line1[0]
            r'(?:Part|Pt)(\d+)(?:Line(\d+[a-zA-Z]?))?',
            # CheckBox pattern: Part1Line1_CheckBox[0]
            r'Part(\d+)Line(\d+[a-zA-Z]?)_CheckBox',
            r'Pt(\d+)Line(\d+[a-zA-Z]?)_CheckBox'
        ]
        
        # Remove common prefixes
        clean_name = field_name
        prefixes_to_remove = ['form1[0].', 'form[0].', '#subform[0].', 'Page1[0].', 'Page2[0].', 'Page3[0].']
        for prefix in prefixes_to_remove:
            if clean_name.startswith(prefix):
                clean_name = clean_name[len(prefix):]
        
        # Try each pattern
        for pattern in patterns:
            match = re.search(pattern, clean_name)
            if match:
                groups = match.groups()
                if len(groups) >= 1:
                    result['part_number'] = int(groups[0])
                if len(groups) >= 2 and groups[1]:
                    result['line_number'] = groups[1]
                if len(groups) >= 3 and groups[2]:
                    result['field_label'] = groups[2]
                else:
                    # For checkbox patterns
                    if 'CheckBox' in clean_name:
                        result['field_label'] = 'CheckBox'
                break
        
        # If no pattern matched but contains Part/Pt, extract part number
        if not result['part_number']:
            part_match = re.search(r'(?:Part|Pt)\s*(\d+)', clean_name, re.IGNORECASE)
            if part_match:
                result['part_number'] = int(part_match.group(1))
        
        # Extract field label if not found
        if not result['field_label']:
            # Look for common field labels
            label_patterns = [
                'AlienNumber', 'USCISOnlineAcctNumber', 'FamilyName', 'GivenName', 'MiddleName',
                'StreetNumberName', 'AptSteFlrNumber', 'CityOrTown', 'State', 'ZipCode',
                'DateOfBirth', 'CountryOfBirth', 'SSN', 'Gender', 'MaritalStatus',
                'CheckBox', 'YesNo', 'Checkbox'
            ]
            
            for label in label_patterns:
                if label in clean_name:
                    result['field_label'] = label
                    break
        
        return result
    
    def _is_attorney_field(self, field_name: str, field_info: dict) -> bool:
        """Check if field is attorney/preparer related"""
        field_lower = field_name.lower()
        
        # Attorney keywords
        attorney_keywords = [
            'attorney', 'preparer', 'lawyer', 'representative', 
            'bar number', 'law firm', 'g-28', 'g28',
            'signature of attorney', 'daytime telephone number of attorney'
        ]
        
        # Check keywords
        for keyword in attorney_keywords:
            if keyword in field_lower:
                return True
        
        # Part 0 is always attorney
        if field_info.get('part_number') == 0:
            return True
        
        return False
    
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
    
    def _generate_description(self, field_info: dict) -> str:
        """Generate human-readable description from field info"""
        # Check if we have a known field label
        if field_info['field_label'] and field_info['field_label'] in self.field_descriptions:
            desc = self.field_descriptions[field_info['field_label']]
        elif field_info['field_label']:
            # Convert camelCase to readable
            desc = re.sub(r'([a-z])([A-Z])', r'\1 \2', field_info['field_label'])
            desc = desc.replace('_', ' ').strip()
        else:
            desc = "Field"
        
        # Add line number if available
        if field_info['line_number']:
            desc = f"Line {field_info['line_number']} - {desc}"
        
        return desc
    
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
                ts += f'      description: "{field.description}",\n'
                ts += f'      fieldType: "{field.field_type}",\n'
                ts += f'      part: "Part {field.part_number}",\n'
                if field.line_number:
                    ts += f'      line: "{field.line_number}",\n'
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
                    "description": field.description,
                    "type": field.field_type,
                    "page": field.page,
                    "originalFieldName": field.raw_field_name
                }
                
                if field.line_number:
                    field_data["line"] = field.line_number
                
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
        .metric-card {
            background: white;
            padding: 1.5rem;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            text-align: center;
        }
        .part-section {
            background: #f9fafb;
            border: 1px solid #e5e7eb;
            padding: 1rem;
            margin: 1rem 0;
            border-radius: 8px;
        }
        .field-item {
            background: white;
            border: 1px solid #e5e7eb;
            padding: 0.75rem;
            margin: 0.5rem 0;
            border-radius: 6px;
        }
        .status-badge {
            padding: 0.25rem 0.75rem;
            border-radius: 999px;
            font-size: 0.875rem;
            font-weight: 500;
            display: inline-block;
        }
        .status-mapped { background: #d1fae5; color: #065f46; }
        .status-questionnaire { background: #fed7aa; color: #92400e; }
        .status-unmapped { background: #fee2e2; color: #991b1b; }
        .debug-section {
            background: #f3f4f6;
            padding: 1rem;
            border-radius: 8px;
            margin: 1rem 0;
            font-family: monospace;
            font-size: 0.875rem;
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="main-header">
        <h1>📄 USCIS Form Field Extractor</h1>
        <p>Properly extracts fields from multi-part USCIS forms</p>
    </div>
    """, unsafe_allow_html=True)

def render_upload_tab(extractor: USCISFormExtractor):
    """Upload and extract PDF fields"""
    st.markdown("## 📤 Upload USCIS Form")
    
    uploaded_file = st.file_uploader(
        "Choose a USCIS form PDF file",
        type=['pdf'],
        help="Upload any USCIS form (I-90, I-129, I-485, N-400, etc.)"
    )
    
    if uploaded_file:
        col1, col2 = st.columns([2, 1])
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
        
        # Summary metrics
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
        
        # Show fields by part
        st.markdown("### 📑 Fields by Part")
        
        for part, part_fields in st.session_state.fields_by_part.items():
            with st.expander(f"**{part}** ({len(part_fields)} fields)", expanded=(part == "Part 1")):
                # Part statistics
                field_types = defaultdict(int)
                for field in part_fields:
                    field_types[field.field_type] += 1
                
                stats = " | ".join([f"{t}: {c}" for t, c in field_types.items()])
                st.caption(f"Field types: {stats}")
                
                # Display fields in a table
                df_data = []
                for field in part_fields:
                    df_data.append({
                        "ID": field.field_id,
                        "Line": field.line_number or "-",
                        "Description": field.description,
                        "Type": field.field_type,
                        "Page": field.page,
                        "Status": "📋 Questionnaire" if field.to_questionnaire else "⚪ Unmapped"
                    })
                
                df = pd.DataFrame(df_data)
                st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Debug section
        with st.expander("🔍 Debug: Raw Field Names"):
            st.markdown("First 10 raw field names from PDF:")
            for i, name in enumerate(st.session_state.raw_field_names[:10], 1):
                st.code(f"{i}. {name}")

def render_mapping_tab(extractor: USCISFormExtractor):
    """Map fields to database objects"""
    if not st.session_state.extracted_fields:
        st.info("👆 Please upload and extract a PDF form first")
        return
    
    st.markdown("## 🎯 Field Mapping")
    
    # Summary
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
            count = 0
            for field in fields:
                if not field.is_mapped and not field.to_questionnaire:
                    field.to_questionnaire = True
                    count += 1
            if count > 0:
                st.success(f"Moved {count} fields to questionnaire")
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
            st.rerun()
    
    # Filters
    st.markdown("### 🔍 Filter Options")
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
    
    # Display fields
    st.markdown(f"### Showing {len(display_fields)} fields")
    
    for field in display_fields:
        with st.container():
            col1, col2, col3 = st.columns([2, 3, 1])
            
            with col1:
                st.markdown(f"**{field.field_id}** - Part {field.part_number}")
                st.caption(f"Type: {field.field_type} | Page: {field.page}")
            
            with col2:
                st.markdown(f"**{field.description}**")
                
                if field.is_mapped:
                    st.success(f"✅ Mapped to: {field.db_mapping}")
                elif field.to_questionnaire:
                    st.warning("📋 In Questionnaire")
                else:
                    # Mapping dropdown
                    options = ["-- Select Mapping --", "📋 To Questionnaire"] + extractor.db_paths
                    
                    selected = st.selectbox(
                        "Map to",
                        options,
                        key=f"map_{field.field_id}",
                        label_visibility="collapsed"
                    )
                    
                    if selected == "📋 To Questionnaire":
                        field.to_questionnaire = True
                        st.rerun()
                    elif selected != "-- Select Mapping --":
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

def render_export_tab(extractor: USCISFormExtractor):
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
        st.markdown(f'<div class="status-badge status-mapped">Database Mapped: {mapped}</div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="status-badge status-questionnaire">Questionnaire: {questionnaire}</div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="status-badge status-unmapped">Unmapped: {unmapped}</div>', unsafe_allow_html=True)
    
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
            file_name=f"{st.session_state.form_info.get('form_number', 'form').replace('-', '')}.ts",
            mime="text/plain",
            use_container_width=True
        )
        
        with st.expander("Preview TypeScript"):
            st.code(ts_content[:1500] + "\n...", language="typescript")
    
    with col2:
        st.markdown("### 📋 Questionnaire JSON")
        st.markdown("Fields requiring manual entry")
        
        # Create a copy for JSON generation
        json_fields = []
        for field in fields:
            if not field.is_mapped:
                json_field = field
                json_field.to_questionnaire = True
                json_fields.append(json_field)
            else:
                json_fields.append(field)
        
        json_content = extractor.generate_json(json_fields)
        
        st.download_button(
            label="📥 Download JSON File",
            data=json_content,
            file_name=f"{st.session_state.form_info.get('form_number', 'form')}-questionnaire.json",
            mime="application/json",
            use_container_width=True
        )
        
        with st.expander("Preview JSON"):
            preview = json.loads(json_content)
            if preview.get("sections"):
                preview["sections"] = preview["sections"][:2]  # Show first 2 sections
                for section in preview["sections"]:
                    if section.get("fields"):
                        section["fields"] = section["fields"][:3]  # Show first 3 fields
            st.json(preview)

def main():
    st.set_page_config(
        page_title="USCIS Form Field Extractor",
        page_icon="📄",
        layout="wide"
    )
    
    # Initialize extractor
    extractor = USCISFormExtractor()
    
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
        2. **Extract** fields by parts
        3. **Map** to database or questionnaire
        4. **Export** TypeScript & JSON
        
        **Features:**
        - Properly parses USCIS field names
        - Groups by Part 1, Part 2, etc.
        - Extracts line numbers (1a, 2b, etc.)
        - Auto-detects checkboxes
        - Skips attorney/Part 0 fields
        """)

if __name__ == "__main__":
    main()
