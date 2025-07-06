import streamlit as st
import json
import re
import fitz  # PyMuPDF
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Set
from collections import defaultdict, OrderedDict
import pandas as pd
from dataclasses import dataclass, field

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
    widget_rect: Tuple[float, float, float, float] = field(default_factory=tuple)  # x0, y0, x1, y1
    db_mapping: Optional[str] = None
    is_mapped: bool = False
    to_questionnaire: bool = False
    
    def __hash__(self):
        """Make PDFField hashable for deduplication"""
        return hash((self.widget_name, self.part_number, self.item_number))
    
    def __eq__(self, other):
        """Check equality based on key fields"""
        if not isinstance(other, PDFField):
            return False
        return (self.widget_name == other.widget_name and 
                self.part_number == other.part_number and 
                self.item_number == other.item_number)

class SmartUSCISExtractor:
    """Smart USCIS Form PDF Field Extractor with improved accuracy"""
    
    def __init__(self):
        self.init_session_state()
        self.db_paths = self._build_database_paths()
        self.part_patterns = [
            r'Part\s+(\d+)\.?\s*[-–—]\s*([A-Z][^\.]+)',  # Part 1 - Information About You
            r'Part\s+(\d+)\.?\s+([A-Z][^\.]+)',         # Part 1. Information About You
            r'Part\s+(\d+)\.?\s*([A-Z])',               # Part 1. I
            r'Part\s+(\d+)\.',                           # Part 1.
            r'Part\s+(\d+)\s'                            # Part 1 
        ]
    
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
        if 'extraction_log' not in st.session_state:
            st.session_state.extraction_log = []
    
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
        """Extract all fields from PDF with proper structure and deduplication"""
        try:
            # Reset state
            st.session_state.extracted_fields = []
            st.session_state.fields_by_part = OrderedDict()
            st.session_state.current_field_index = 0
            st.session_state.extraction_log = []
            
            # Read PDF
            pdf_bytes = pdf_file.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            # Detect form type
            form_info = self._detect_form_type(doc)
            st.session_state.form_info = form_info
            
            # Build comprehensive page analysis
            page_analysis = self._analyze_pdf_structure(doc)
            
            # Extract fields with improved logic
            all_fields = []
            seen_fields = set()  # For deduplication
            
            # Process each part starting from Part 1
            for part_num in sorted(page_analysis['parts'].keys()):
                if part_num == 0:  # Skip attorney/preparer sections
                    continue
                    
                part_info = page_analysis['parts'][part_num]
                st.session_state.extraction_log.append(f"Processing Part {part_num}: {part_info['title']}")
                
                # Process pages for this part
                for page_num in part_info['pages']:
                    fields_on_page = self._extract_fields_from_page(
                        doc, page_num, part_num, page_analysis
                    )
                    
                    # Deduplicate fields
                    for field in fields_on_page:
                        field_key = (field.widget_name, field.part_number, field.item_number)
                        if field_key not in seen_fields:
                            seen_fields.add(field_key)
                            all_fields.append(field)
                            st.session_state.extraction_log.append(
                                f"Added field: {field.field_id} - {field.field_label}"
                            )
            
            doc.close()
            
            # Sort fields properly
            all_fields.sort(key=lambda f: (
                f.part_number,
                self._parse_item_number_for_sort(f.item_number),
                f.page,
                f.widget_rect[1] if f.widget_rect else 0  # y position
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
    
    def _analyze_pdf_structure(self, doc) -> dict:
        """Analyze PDF structure to understand parts and pages"""
        analysis = {
            'parts': {},
            'page_to_part': {},
            'items_by_page': {}
        }
        
        current_part = 0
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            
            # Detect part changes
            for pattern in self.part_patterns:
                matches = re.finditer(pattern, text, re.MULTILINE)
                for match in matches:
                    part_num = int(match.group(1))
                    part_title = match.group(2) if len(match.groups()) > 1 else f"Part {part_num}"
                    
                    # Only process if it's a new part or Part 1 and we haven't started
                    if part_num > current_part or (part_num == 1 and current_part == 0):
                        current_part = part_num
                        if part_num not in analysis['parts']:
                            analysis['parts'][part_num] = {
                                'title': part_title.strip(),
                                'start_page': page_num,
                                'pages': []
                            }
                        break
            
            # Skip pages before Part 1
            if current_part == 0:
                continue
                
            # Assign page to current part
            analysis['page_to_part'][page_num] = current_part
            if current_part in analysis['parts']:
                analysis['parts'][current_part]['pages'].append(page_num)
            
            # Extract items on this page
            analysis['items_by_page'][page_num] = self._extract_items_from_text(text, current_part)
        
        return analysis
    
    def _extract_fields_from_page(self, doc, page_num: int, part_num: int, 
                                  page_analysis: dict) -> List[PDFField]:
        """Extract fields from a specific page with context"""
        fields = []
        page = doc[page_num]
        page_text = page.get_text()
        
        # Get items for this page
        items_on_page = page_analysis['items_by_page'].get(page_num, [])
        
        # Get all widgets
        widgets = page.widgets()
        if not widgets:
            return fields
        
        # Process widgets
        field_counter = defaultdict(int)
        
        for widget in widgets:
            if not widget.field_name:
                continue
                
            # Skip attorney/preparer fields
            if self._is_attorney_field(widget.field_name, page_text):
                continue
            
            # Get widget position
            rect = widget.rect
            widget_y = rect.y0
            
            # Match to item
            item_info = self._match_widget_to_item_improved(
                widget, widget_y, items_on_page, page_text
            )
            
            # Generate field ID
            field_counter[item_info['number']] += 1
            sub_index = field_counter[item_info['number']]
            
            if sub_index == 1:
                field_id = f"P{part_num}_{item_info['number']}"
            else:
                # For multiple fields in same item
                field_id = f"P{part_num}_{item_info['number']}_{chr(96 + sub_index)}"
            
            # Create field
            pdf_field = PDFField(
                widget_name=widget.field_name,
                field_id=field_id,
                part_number=part_num,
                item_number=item_info['number'],
                field_label=item_info['label'],
                field_type=self._get_field_type(widget.field_type),
                page=page_num + 1,
                value=widget.field_value or '',
                widget_rect=(rect.x0, rect.y0, rect.x1, rect.y1)
            )
            
            # Auto-assign checkboxes to questionnaire
            if pdf_field.field_type in ['checkbox', 'radio']:
                pdf_field.to_questionnaire = True
            
            fields.append(pdf_field)
        
        return fields
    
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
            'I-131': 'Application for Travel Document',
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
    
    def _is_attorney_field(self, field_name: str, page_text: str = "") -> bool:
        """Check if field is attorney/preparer related"""
        attorney_keywords = [
            'attorney', 'preparer', 'representative', 'g-28', 'g28',
            'bar number', 'bia', 'accredited', 'interpreter',
            'Part 5', 'Part 6', 'Part 7', 'Part 8', 'Part 9'  # Common attorney parts
        ]
        
        field_lower = field_name.lower()
        page_lower = page_text.lower()
        
        # Check field name
        if any(keyword in field_lower for keyword in attorney_keywords):
            return True
            
        # Check if we're in attorney section of the page
        if 'preparer' in page_lower and 'attorney' in page_lower:
            # More sophisticated check could go here
            return True
            
        return False
    
    def _extract_items_from_text(self, page_text: str, part_number: int) -> List[dict]:
        """Extract item numbers and labels from page text with improved patterns"""
        items = []
        
        # Comprehensive patterns for item detection
        patterns = [
            # Standard patterns
            r'(?:Item\s+Number\s+)?(\d+)\.\s+([A-Z][^\n\r]+?)(?=\s*(?:\n|\r|$|Item|\d+\.))',
            r'(?:Item\s+Number\s+)?(\d+[a-z])\.\s+([A-Z][^\n\r]+?)(?=\s*(?:\n|\r|$|Item|\d+[a-z]?\.))',
            r'(\d+)\.\s*([A-Za-z][^\n\r]{5,100})',
            
            # Letter patterns (a., b., c.)
            r'([a-z])\.\s+([A-Z][^\n\r]+?)(?=\s*(?:\n|\r|$|[a-z]\.))',
            
            # Checkbox patterns
            r'□\s*(\d+[a-z]?)\.\s*([^\n\r]+)',
            r'\[\s*\]\s*(\d+[a-z]?)\.\s*([^\n\r]+)',
        ]
        
        seen_items = set()
        
        for pattern in patterns:
            matches = re.finditer(pattern, page_text, re.MULTILINE)
            for match in matches:
                item_num = match.group(1)
                item_label = match.group(2).strip()
                
                # Clean up label
                item_label = re.sub(r'\s+', ' ', item_label)
                item_label = re.sub(r'\s*\([^)]*\)\s*$', '', item_label)  # Remove trailing parentheses
                item_label = item_label.strip()
                
                # Skip if too short or already seen
                if len(item_label) < 3 or item_num in seen_items:
                    continue
                
                seen_items.add(item_num)
                
                items.append({
                    'number': item_num,
                    'label': item_label[:100],  # Limit length
                    'position': match.start(),
                    'y_position': self._estimate_y_position(page_text, match.start())
                })
        
        # Sort by position
        items.sort(key=lambda x: x['position'])
        
        return items
    
    def _estimate_y_position(self, text: str, char_position: int) -> float:
        """Estimate Y position based on character position in text"""
        # Count newlines before this position
        newlines_before = text[:char_position].count('\n')
        # Rough estimate: each line is about 20 units
        return newlines_before * 20
    
    def _match_widget_to_item_improved(self, widget, y_pos: float, 
                                       items: List[dict], page_text: str) -> dict:
        """Improved widget to item matching with better heuristics"""
        widget_name_lower = widget.field_name.lower()
        
        # First, try specific field patterns
        specific_mappings = {
            ('familyname', 'lastname'): {'number': '1a', 'label': 'Family Name (Last Name)'},
            ('givenname', 'firstname'): {'number': '1b', 'label': 'Given Name (First Name)'},
            ('middlename',): {'number': '1c', 'label': 'Middle Name'},
            ('alien', 'anumber', 'a-number'): {'number': '2', 'label': 'Alien Registration Number (A-Number)'},
            ('uscis', 'online', 'account'): {'number': '3', 'label': 'USCIS Online Account Number'},
            ('date', 'birth', 'dob'): {'number': '4', 'label': 'Date of Birth'},
            ('country', 'birth'): {'number': '5', 'label': 'Country of Birth'},
            ('country', 'citizenship'): {'number': '6', 'label': 'Country of Citizenship'},
            ('gender', 'sex'): {'number': '7', 'label': 'Gender'},
            ('marital', 'status'): {'number': '8', 'label': 'Marital Status'},
            ('ssn', 'social', 'security'): {'number': '9', 'label': 'U.S. Social Security Number'},
        }
        
        for keywords, mapping in specific_mappings.items():
            if any(kw in widget_name_lower for kw in keywords):
                return mapping
        
        # Try to find closest item by Y position
        if items:
            closest_item = None
            min_distance = float('inf')
            
            for item in items:
                # Calculate distance
                distance = abs(item.get('y_position', 0) - y_pos)
                if distance < min_distance and distance < 50:  # Within 50 units
                    min_distance = distance
                    closest_item = item
            
            if closest_item:
                return {
                    'number': closest_item['number'],
                    'label': closest_item['label']
                }
        
        # Default fallback
        return {
            'number': '99',
            'label': self._extract_field_label(widget, page_text)
        }
    
    def _extract_field_label(self, widget, page_text: str) -> str:
        """Extract field label from widget or page context"""
        # First try widget display name
        if hasattr(widget, 'field_display') and widget.field_display and widget.field_display.strip():
            return widget.field_display.strip()
        
        # Try to extract from field name
        field_name = widget.field_name
        
        # Remove common prefixes
        prefixes_to_remove = [
            'form1[0].', '#subform[0].', 'Page1[0].', 'Page2[0].', 'Page3[0].',
            'Pt1', 'Pt2', 'Pt3', 'Part1', 'Part2', 'Part3',
            'TextField[', 'CheckBox[', 'RadioButton['
        ]
        
        for prefix in prefixes_to_remove:
            if field_name.startswith(prefix):
                field_name = field_name[len(prefix):]
        
        # Remove array indices and closing brackets
        field_name = re.sub(r'\[\d+\]', '', field_name)
        field_name = field_name.rstrip(']')
        
        # Extract meaningful part
        parts = field_name.split('.')
        if parts:
            label = parts[-1]
            # Convert camelCase to readable
            label = re.sub(r'([a-z])([A-Z])', r'\1 \2', label)
            label = label.replace('_', ' ').strip()
            
            # Capitalize appropriately
            words = label.split()
            label = ' '.join(word.capitalize() for word in words)
            
            return label
        
        return "Field"
    
    def _parse_item_number_for_sort(self, item_num: str) -> tuple:
        """Parse item number for proper sorting (e.g., '2a' -> (2, 'a'))"""
        if not item_num:
            return (999, '')
            
        # Try to parse number and letter
        match = re.match(r'(\d+)([a-zA-Z]?)', str(item_num))
        if match:
            num = int(match.group(1))
            letter = match.group(2) or ''
            return (num, letter)
            
        # Try letter only (for sub-items)
        if len(item_num) == 1 and item_num.isalpha():
            return (0, item_num)
            
        return (999, str(item_num))
    
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
        ts += f"// Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        ts += f"// Total Fields: {len(fields)} (DB: {sum(len(f) for f in db_fields.values())}, "
        ts += f"Questionnaire: {len(questionnaire_fields)})\n\n"
        ts += f"export const {form_name} = {{\n"
        
        # Add database mappings
        for obj, fields_list in sorted(db_fields.items()):
            ts += f"  {obj}Data: {{\n"
            for field in sorted(fields_list, key=lambda f: (f.part_number, f.item_number)):
                path = field.db_mapping.replace(f"{obj}.", "")
                field_suffix = ":TextBox" if field.field_type == "text" else f":{field.field_type.title()}Box"
                comment = f" // Part {field.part_number}, Item {field.item_number}: {field.field_label[:50]}"
                ts += f'    "{field.field_id}{field_suffix}": "{path}",{comment}\n'
            ts = ts.rstrip(',\n') + '\n'
            ts += "  },\n\n"
        
        # Add questionnaire fields
        if questionnaire_fields:
            ts += "  questionnaireData: {\n"
            for field in sorted(questionnaire_fields, key=lambda f: (f.part_number, f.item_number)):
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
            
            for field in sorted(by_part[part_num], key=lambda f: self._parse_item_number_for_sort(f.item_number)):
                field_data = {
                    "id": field.field_id,
                    "description": field.field_label,
                    "item": field.item_number,
                    "type": field.field_type,
                    "page": field.page,
                    "widgetName": field.widget_name  # Include for debugging
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
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        .main-header h1 {
            margin: 0 0 0.5rem 0;
            font-size: 2.5rem;
        }
        .main-header p {
            margin: 0;
            opacity: 0.9;
        }
        .field-card {
            background: white;
            border: 1px solid #e5e7eb;
            padding: 1.5rem;
            margin: 1rem 0;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            transition: box-shadow 0.3s ease;
        }
        .field-card:hover {
            box-shadow: 0 4px 8px rgba(0,0,0,0.15);
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
            padding: 1rem 1.5rem;
            margin: 1.5rem 0 1rem 0;
            border-radius: 8px;
            border-left: 4px solid #2563eb;
            font-weight: bold;
            font-size: 1.1rem;
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
        .extraction-log {
            background: #f9fafb;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 1rem;
            margin: 1rem 0;
            max-height: 300px;
            overflow-y: auto;
            font-family: monospace;
            font-size: 0.875rem;
        }
        .extraction-log-entry {
            margin: 0.25rem 0;
            padding: 0.25rem 0;
            border-bottom: 1px solid #f3f4f6;
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="main-header">
        <h1>📄 Smart USCIS Form Field Extractor</h1>
        <p>Advanced extraction with accurate Part and Item structure</p>
    </div>
    """, unsafe_allow_html=True)

def render_upload_tab(extractor: SmartUSCISExtractor):
    """Upload and extract PDF fields"""
    st.markdown("## 📤 Upload USCIS Form")
    
    uploaded_file = st.file_uploader(
        "Choose a USCIS form PDF file",
        type=['pdf'],
        help="Upload any USCIS form (I-539, I-824, I-90, I-129, I-485, etc.)"
    )
    
    if uploaded_file:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.info(f"📄 **File:** {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")
        with col2:
            if st.button("🔍 Extract Fields", type="primary", use_container_width=True):
                with st.spinner("Analyzing PDF structure and extracting fields..."):
                    if extractor.extract_fields_from_pdf(uploaded_file):
                        st.success(f"✅ Successfully extracted {len(st.session_state.extracted_fields)} unique fields!")
                        st.rerun()
    
    # Display extracted fields
    if st.session_state.extracted_fields:
        st.markdown("---")
        st.markdown("## 📊 Extraction Results")
        
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
        
        # Show extraction log
        with st.expander("📝 Extraction Log", expanded=False):
            st.markdown('<div class="extraction-log">', unsafe_allow_html=True)
            for log_entry in st.session_state.extraction_log[-50:]:  # Show last 50 entries
                st.markdown(f'<div class="extraction-log-entry">{log_entry}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        
        # Display by parts
        st.markdown("### 📑 Fields by Part")
        
        for part, part_fields in st.session_state.fields_by_part.items():
            # Count field types
            text_count = sum(1 for f in part_fields if f.field_type == 'text')
            checkbox_count = sum(1 for f in part_fields if f.field_type in ['checkbox', 'radio'])
            other_count = len(part_fields) - text_count - checkbox_count
            
            with st.expander(
                f"**{part}** ({len(part_fields)} fields: {text_count} text, {checkbox_count} checkbox/radio, {other_count} other)", 
                expanded=(part == "Part 1")
            ):
                # Create a clean table view
                df_data = []
                for field in part_fields:
                    status = "📋 Quest" if field.to_questionnaire else ("✅ Mapped" if field.is_mapped else "⚪ Unmapped")
                    df_data.append({
                        "Field ID": field.field_id,
                        "Item": field.item_number,
                        "Description": field.field_label[:60] + "..." if len(field.field_label) > 60 else field.field_label,
                        "Type": field.field_type,
                        "Page": field.page,
                        "Status": status
                    })
                
                df = pd.DataFrame(df_data)
                st.dataframe(
                    df, 
                    use_container_width=True, 
                    hide_index=True,
                    column_config={
                        "Field ID": st.column_config.TextColumn("Field ID", width="small"),
                        "Item": st.column_config.TextColumn("Item", width="small"),
                        "Type": st.column_config.TextColumn("Type", width="small"),
                        "Page": st.column_config.NumberColumn("Page", width="small"),
                        "Status": st.column_config.TextColumn("Status", width="small"),
                    }
                )

def render_mapping_tab(extractor: SmartUSCISExtractor):
    """Map fields - either one by one or all at once"""
    if not st.session_state.extracted_fields:
        st.info("👆 Please upload and extract a PDF form first")
        return
    
    st.markdown("## 🎯 Field Mapping")
    
    # Mode selection and stats
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        mapping_mode = st.radio(
            "Mapping Mode",
            ["View All Fields", "One by One"],
            horizontal=True,
            help="Choose between viewing all fields at once or mapping them one by one"
        )
        st.session_state.one_by_one_mode = (mapping_mode == "One by One")
    
    with col2:
        # Quick stats
        fields = st.session_state.extracted_fields
        mapped = sum(1 for f in fields if f.is_mapped)
        quest = sum(1 for f in fields if f.to_questionnaire)
        unmapped = len(fields) - mapped - quest
        
        st.metric("Progress", f"{mapped + quest}/{len(fields)}")
        progress = (mapped + quest) / len(fields) if fields else 0
        st.progress(progress)
    
    with col3:
        st.metric("Unmapped", unmapped)
        if unmapped > 0:
            st.caption("⚠️ Will go to questionnaire")
    
    # Quick actions
    st.markdown("### ⚡ Quick Actions")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("📋 All Unmapped → Quest", use_container_width=True):
            count = 0
            for field in fields:
                if not field.is_mapped and not field.to_questionnaire:
                    field.to_questionnaire = True
                    count += 1
            if count > 0:
                st.success(f"Moved {count} fields to questionnaire")
                st.rerun()
    
    with col2:
        if st.button("☑️ All Checkboxes → Quest", use_container_width=True):
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
        if st.button("🗺️ Auto-map Common Fields", use_container_width=True):
            count = auto_map_common_fields(extractor)
            if count > 0:
                st.success(f"Auto-mapped {count} fields")
                st.rerun()
    
    with col4:
        if st.button("🔄 Reset All Mappings", use_container_width=True):
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

def auto_map_common_fields(extractor: SmartUSCISExtractor) -> int:
    """Auto-map common fields based on patterns"""
    count = 0
    fields = st.session_state.extracted_fields
    
    # Common field mappings
    auto_mappings = {
        # Name fields
        r'family\s*name|last\s*name': 'beneficiary.Beneficiary.beneficiaryLastName',
        r'given\s*name|first\s*name': 'beneficiary.Beneficiary.beneficiaryFirstName',
        r'middle\s*name': 'beneficiary.Beneficiary.beneficiaryMiddleName',
        
        # ID numbers
        r'alien\s*(?:registration\s*)?number|a[-\s]*number': 'beneficiary.Beneficiary.alienNumber',
        r'uscis\s*online\s*account': 'beneficiary.Beneficiary.uscisOnlineAccountNumber',
        r'social\s*security|ssn': 'beneficiary.Beneficiary.beneficiarySsn',
        
        # Personal info
        r'date\s*of\s*birth|birth\s*date|dob': 'beneficiary.Beneficiary.beneficiaryDateOfBirth',
        r'country\s*of\s*birth': 'beneficiary.Beneficiary.beneficiaryCountryOfBirth',
        r'country\s*of\s*citizenship': 'beneficiary.Beneficiary.beneficiaryCitizenOfCountry',
        r'gender|sex': 'beneficiary.Beneficiary.beneficiaryGender',
        r'marital\s*status': 'beneficiary.Beneficiary.maritalStatus',
        
        # Contact info
        r'daytime\s*telephone|day\s*phone': 'beneficiary.ContactInfo.daytimeTelephoneNumber',
        r'mobile\s*telephone|cell\s*phone': 'beneficiary.ContactInfo.mobileTelephoneNumber',
        r'email\s*address': 'beneficiary.ContactInfo.emailAddress',
        
        # Address fields
        r'street\s*(?:number\s*and\s*)?name|street\s*address': 'beneficiary.MailingAddress.addressStreet',
        r'apt.*number|apartment|suite': 'beneficiary.MailingAddress.addressAptSteFlrNumber',
        r'city\s*(?:or\s*town)?': 'beneficiary.MailingAddress.addressCity',
        r'^state$|state\s*(?:or\s*province)?': 'beneficiary.MailingAddress.addressState',
        r'zip\s*code|postal\s*code': 'beneficiary.MailingAddress.addressZip',
        r'^country$': 'beneficiary.MailingAddress.addressCountry',
        
        # Document fields
        r'passport\s*number': 'beneficiary.PassportDetails.Passport.passportNumber',
        r'passport\s*(?:issue|issuance)\s*country': 'beneficiary.PassportDetails.Passport.passportIssueCountry',
        r'passport\s*(?:issue|issuance)\s*date': 'beneficiary.PassportDetails.Passport.passportIssueDate',
        r'passport\s*expir': 'beneficiary.PassportDetails.Passport.passportExpiryDate',
        
        # Immigration status
        r'current\s*(?:nonimmigrant\s*)?status': 'beneficiary.VisaDetails.Visa.currentNonimmigrantStatus',
        r'date\s*(?:status\s*)?expires|expiration\s*date': 'beneficiary.VisaDetails.Visa.dateStatusExpires',
        r'i-94\s*number|form\s*i-94': 'beneficiary.I94Details.I94.formI94ArrivalDepartureRecordNumber',
        r'date\s*of\s*(?:last\s*)?arrival': 'beneficiary.I94Details.I94.dateOfLastArrival',
        r'sevis\s*number': 'beneficiary.EducationDetails.studentEXTInfoSEVISNumber',
    }
    
    for field in fields:
        if field.is_mapped or field.to_questionnaire:
            continue
            
        label_lower = field.field_label.lower().strip()
        
        for pattern, db_path in auto_mappings.items():
            if re.search(pattern, label_lower, re.IGNORECASE):
                field.db_mapping = db_path
                field.is_mapped = True
                count += 1
                break
    
    return count

def render_one_by_one_mapping(extractor: SmartUSCISExtractor):
    """Render one-by-one field mapping with better UX"""
    fields = st.session_state.extracted_fields
    current_idx = st.session_state.current_field_index
    
    # Skip already processed fields
    unmapped_indices = [i for i, f in enumerate(fields) if not f.is_mapped and not f.to_questionnaire]
    
    if not unmapped_indices:
        st.success("✅ All fields have been processed!")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Review All Fields", use_container_width=True):
                st.session_state.one_by_one_mode = False
                st.rerun()
        with col2:
            if st.button("📥 Go to Export", use_container_width=True):
                st.session_state.current_tab = 2  # Switch to export tab
                st.rerun()
        return
    
    # Find next unmapped field
    if current_idx not in unmapped_indices:
        current_idx = unmapped_indices[0]
        st.session_state.current_field_index = current_idx
    
    # Progress
    processed = len(fields) - len(unmapped_indices)
    progress = processed / len(fields) if fields else 0
    st.markdown(f"""
    <div class="progress-indicator">
        <div class="progress-fill" style="width: {progress * 100}%"></div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown(f"### Processing Field {processed + 1} of {len(fields)} ({len(unmapped_indices)} remaining)")
    
    # Current field
    field = fields[current_idx]
    
    # Field card with better styling
    st.markdown('<div class="field-card">', unsafe_allow_html=True)
    
    # Field information
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f'<div class="field-id">Part {field.part_number}, Item {field.item_number}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="field-label">{field.field_label}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="field-meta">Field ID: {field.field_id} | Type: {field.field_type} | Page: {field.page}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="field-meta">Widget: {field.widget_name}</div>', unsafe_allow_html=True)
    
    with col2:
        if field.field_type == "checkbox":
            st.info("☑️ Checkbox Field")
        elif field.field_type == "radio":
            st.info("⭕ Radio Field")
        else:
            st.info("📝 Text Field")
    
    # Mapping options
    st.markdown("### 🎯 Map this field to:")
    
    # Smart suggestions
    suggestions = get_smart_suggestions(field.field_label, field.item_number, extractor.db_paths)
    
    if suggestions:
        st.markdown("**🤖 AI Suggestions:**")
        for i, suggestion in enumerate(suggestions[:5]):  # Show top 5
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"→ `{suggestion}`")
            with col2:
                if st.button("Use", key=f"sugg_{current_idx}_{i}"):
                    field.db_mapping = suggestion
                    field.is_mapped = True
                    field.to_questionnaire = False
                    st.success(f"✅ Mapped to: {suggestion}")
                    # Move to next unmapped
                    next_unmapped = next((i for i in unmapped_indices if i > current_idx), unmapped_indices[0])
                    st.session_state.current_field_index = next_unmapped
                    st.rerun()
    
    # Manual selection
    st.markdown("**📋 Manual Selection:**")
    col1, col2 = st.columns([4, 1])
    
    with col1:
        # Group paths by object for better organization
        grouped_paths = defaultdict(list)
        for path in extractor.db_paths:
            obj = path.split('.')[0]
            grouped_paths[obj].append(path)
        
        # Create options with groups
        options = ["-- Select Database Field --"]
        for obj in sorted(grouped_paths.keys()):
            options.append(f"--- {obj.upper()} ---")
            options.extend(sorted(grouped_paths[obj]))
        
        selected = st.selectbox(
            "Select database field",
            options,
            key=f"select_{current_idx}",
            label_visibility="collapsed"
        )
    
    with col2:
        if selected and selected != "-- Select Database Field --" and not selected.startswith("---"):
            if st.button("Apply", use_container_width=True, type="primary"):
                field.db_mapping = selected
                field.is_mapped = True
                field.to_questionnaire = False
                # Move to next unmapped
                next_unmapped = next((i for i in unmapped_indices if i > current_idx), unmapped_indices[0])
                st.session_state.current_field_index = next_unmapped
                st.rerun()
    
    # Or send to questionnaire
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📋 Send to Questionnaire", use_container_width=True, type="secondary"):
            field.to_questionnaire = True
            field.is_mapped = False
            field.db_mapping = None
            # Move to next unmapped
            next_unmapped = next((i for i in unmapped_indices if i > current_idx), unmapped_indices[0])
            st.session_state.current_field_index = next_unmapped
            st.rerun()
    
    with col2:
        if st.button("⏭️ Skip for Now", use_container_width=True):
            # Move to next unmapped
            next_unmapped = next((i for i in unmapped_indices if i > current_idx), unmapped_indices[0])
            st.session_state.current_field_index = next_unmapped
            st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

def render_all_fields_mapping(extractor: SmartUSCISExtractor):
    """Render all fields for mapping with better filtering"""
    fields = st.session_state.extracted_fields
    
    # Advanced filters
    st.markdown("### 🔍 Filters")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        parts = ["All Parts"] + list(st.session_state.fields_by_part.keys())
        selected_part = st.selectbox("Filter by Part", parts)
    
    with col2:
        field_types = ["All Types", "Text", "Checkbox", "Radio", "Other"]
        selected_type = st.selectbox("Filter by Type", field_types)
    
    with col3:
        status_options = ["All", "Unmapped Only", "Mapped Only", "Questionnaire Only"]
        selected_status = st.selectbox("Filter by Status", status_options)
    
    with col4:
        search_term = st.text_input("Search", placeholder="Search in labels...")
    
    # Apply filters
    display_fields = fields.copy()
    
    if selected_part != "All Parts":
        display_fields = [f for f in display_fields if f"Part {f.part_number}" == selected_part]
    
    if selected_type != "All Types":
        type_map = {
            "Text": "text",
            "Checkbox": "checkbox",
            "Radio": "radio"
        }
        if selected_type in type_map:
            display_fields = [f for f in display_fields if f.field_type == type_map[selected_type]]
        else:
            display_fields = [f for f in display_fields if f.field_type not in type_map.values()]
    
    if selected_status == "Unmapped Only":
        display_fields = [f for f in display_fields if not f.is_mapped and not f.to_questionnaire]
    elif selected_status == "Mapped Only":
        display_fields = [f for f in display_fields if f.is_mapped]
    elif selected_status == "Questionnaire Only":
        display_fields = [f for f in display_fields if f.to_questionnaire]
    
    if search_term:
        search_lower = search_term.lower()
        display_fields = [f for f in display_fields if search_lower in f.field_label.lower()]
    
    st.markdown(f"### Showing {len(display_fields)} of {len(fields)} fields")
    
    # Bulk actions for filtered fields
    if display_fields:
        col1, col2 = st.columns(2)
        with col1:
            if st.button(f"📋 Send All {len(display_fields)} to Questionnaire"):
                for field in display_fields:
                    if not field.is_mapped:
                        field.to_questionnaire = True
                st.success(f"Sent {len(display_fields)} fields to questionnaire")
                st.rerun()
    
    # Display fields with better layout
    for i, field in enumerate(display_fields):
        with st.container():
            col1, col2, col3, col4 = st.columns([3, 3.5, 1, 0.5])
            
            with col1:
                # Field info with better formatting
                st.markdown(f"**{field.field_id}**")
                st.markdown(f"Part {field.part_number}, Item {field.item_number} • {field.field_type} • Page {field.page}")
                st.caption(field.field_label[:80] + "..." if len(field.field_label) > 80 else field.field_label)
            
            with col2:
                if field.is_mapped:
                    st.success(f"✅ Mapped to: {field.db_mapping}")
                elif field.to_questionnaire:
                    st.warning("📋 In Questionnaire")
                else:
                    # Quick mapping with search
                    suggestions = get_smart_suggestions(field.field_label, field.item_number, extractor.db_paths)
                    
                    # Combine suggestions with all paths
                    options = ["-- Select --", "📋 → Questionnaire"]
                    if suggestions:
                        options.append("--- Suggestions ---")
                        options.extend(suggestions[:3])
                        options.append("--- All Fields ---")
                    options.extend(extractor.db_paths)
                    
                    selected = st.selectbox(
                        "Map to",
                        options,
                        key=f"map_{field.field_id}_{i}",
                        label_visibility="collapsed"
                    )
                    
                    if selected == "📋 → Questionnaire":
                        field.to_questionnaire = True
                        st.rerun()
                    elif selected not in ["-- Select --", "--- Suggestions ---", "--- All Fields ---"]:
                        field.db_mapping = selected
                        field.is_mapped = True
                        st.rerun()
            
            with col3:
                # Quick action buttons
                if field.is_mapped or field.to_questionnaire:
                    if st.button("↩️ Reset", key=f"reset_{field.field_id}_{i}", help="Reset mapping"):
                        field.is_mapped = False
                        field.to_questionnaire = False
                        field.db_mapping = None
                        st.rerun()
                else:
                    if st.button("📋 Quest", key=f"quest_{field.field_id}_{i}", help="Send to questionnaire"):
                        field.to_questionnaire = True
                        st.rerun()
            
            with col4:
                # Visual indicator
                if field.is_mapped:
                    st.markdown("✅")
                elif field.to_questionnaire:
                    st.markdown("📋")
                else:
                    st.markdown("⚪")
            
            st.divider()

def get_smart_suggestions(field_label: str, item_number: str, db_paths: List[str]) -> List[str]:
    """Get smart mapping suggestions based on field label with improved matching"""
    suggestions = []
    label_lower = field_label.lower().strip()
    
    # Remove common words for better matching
    noise_words = ['the', 'of', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'if', 'any']
    clean_label = ' '.join(word for word in label_lower.split() if word not in noise_words)
    
    # Score each path
    scored_paths = []
    
    for path in db_paths:
        score = 0
        path_parts = path.split('.')
        field_name = path_parts[-1].lower()
        
        # Exact match bonus
        if field_name == clean_label.replace(' ', ''):
            score += 100
        
        # Word matching
        label_words = set(clean_label.split())
        field_words = set(re.split(r'(?=[A-Z])|_', field_name.replace('_', ' ')))
        field_words = {w.lower() for w in field_words if w}
        
        # Common words bonus
        common_words = label_words & field_words
        score += len(common_words) * 20
        
        # Partial word matching
        for label_word in label_words:
            for field_word in field_words:
                if len(label_word) > 3 and len(field_word) > 3:
                    if label_word in field_word or field_word in label_word:
                        score += 10
        
        # Context bonus (check parent object)
        if len(path_parts) > 1:
            parent = path_parts[-2].lower()
            if any(word in parent for word in ['beneficiary', 'contact', 'address', 'passport']):
                # Check if context matches
                if 'address' in label_lower and 'address' in parent:
                    score += 30
                elif 'passport' in label_lower and 'passport' in parent:
                    score += 30
                elif 'contact' in label_lower and 'contact' in parent:
                    score += 30
        
        # Special patterns
        special_patterns = {
            r'family\s*name|last\s*name': ['lastname', 'familyname', 'beneficiarylastname'],
            r'given\s*name|first\s*name': ['firstname', 'givenname', 'beneficiaryfirstname'],
            r'middle\s*name': ['middlename', 'beneficiarymiddlename'],
            r'a[-\s]*number|alien.*number': ['aliennumber', 'anumber'],
            r'date.*birth|birth.*date|dob': ['dateofbirth', 'birthdate', 'beneficiarydateofbirth'],
            r'country.*birth': ['countryofbirth', 'birthcountry'],
            r'country.*citizenship': ['countryofcitizenship', 'citizenshipcountry'],
            r'street|address.*line.*1': ['addressstreet', 'streetaddress'],
            r'city|town': ['addresscity', 'city'],
            r'state|province': ['addressstate', 'state'],
            r'zip|postal': ['addresszip', 'zipcode', 'postalcode'],
        }
        
        for pattern, field_patterns in special_patterns.items():
            if re.search(pattern, label_lower):
                if any(fp in field_name for fp in field_patterns):
                    score += 50
        
        if score > 0:
            scored_paths.append((path, score))
    
    # Sort by score and return top suggestions
    scored_paths.sort(key=lambda x: x[1], reverse=True)
    suggestions = [path for path, score in scored_paths[:10] if score >= 20]
    
    return suggestions

def render_export_tab(extractor: SmartUSCISExtractor):
    """Export mapped fields with preview"""
    if not st.session_state.extracted_fields:
        st.info("👆 Please extract and map fields first")
        return
    
    st.markdown("## 📥 Export Configuration")
    
    # Summary with visual indicators
    fields = st.session_state.extracted_fields
    mapped = sum(1 for f in fields if f.is_mapped)
    questionnaire = sum(1 for f in fields if f.to_questionnaire)
    unmapped = len(fields) - mapped - questionnaire
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Fields", len(fields))
    with col2:
        st.metric("Database Mapped", mapped, f"{mapped/len(fields)*100:.0f}%")
    with col3:
        st.metric("Questionnaire", questionnaire, f"{questionnaire/len(fields)*100:.0f}%")
    with col4:
        st.metric("Unmapped", unmapped, "⚠️" if unmapped > 0 else "✅")
    
    if unmapped > 0:
        st.warning(f"""
        ⚠️ **{unmapped} unmapped fields** will be automatically added to the questionnaire on export.
        
        Consider reviewing these fields before exporting.
        """)
        
        # Show unmapped fields
        with st.expander("View Unmapped Fields"):
            unmapped_fields = [f for f in fields if not f.is_mapped and not f.to_questionnaire]
            for field in unmapped_fields[:10]:  # Show first 10
                st.write(f"• **{field.field_id}** - {field.field_label} (Part {field.part_number}, Item {field.item_number})")
            if len(unmapped_fields) > 10:
                st.write(f"... and {len(unmapped_fields) - 10} more")
    
    st.markdown("---")
    
    # Export options
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📝 TypeScript Export")
        st.markdown("Database field mappings for your application")
        
        # Options
        include_comments = st.checkbox("Include field descriptions as comments", value=True)
        
        # Generate content
        ts_content = extractor.generate_typescript(fields)
        
        # Preview
        with st.expander("Preview TypeScript Output"):
            st.code(ts_content[:2000] + "\n\n// ... truncated for preview", language="typescript")
        
        # Download button
        st.download_button(
            label="📥 Download TypeScript File",
            data=ts_content,
            file_name=f"{st.session_state.form_info.get('form_number', 'form').replace('-', '')}_mappings.ts",
            mime="text/plain",
            use_container_width=True,
            type="primary"
        )
    
    with col2:
        st.markdown("### 📋 JSON Questionnaire")
        st.markdown("Fields requiring user input via questionnaire")
        
        # Auto-add unmapped to questionnaire
        if unmapped > 0:
            for field in fields:
                if not field.is_mapped and not field.to_questionnaire:
                    field.to_questionnaire = True
        
        # Generate content
        json_content = extractor.generate_json(fields)
        json_data = json.loads(json_content)
        
        # Preview
        with st.expander("Preview JSON Output"):
            st.json(json_data)
        
        # Download button
        st.download_button(
            label="📥 Download JSON File",
            data=json_content,
            file_name=f"{st.session_state.form_info.get('form_number', 'form')}_questionnaire.json",
            mime="application/json",
            use_container_width=True,
            type="primary"
        )
    
    # Additional export options
    st.markdown("---")
    st.markdown("### 📊 Additional Export Options")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Export field summary as CSV
        if st.button("📄 Export Field Summary (CSV)", use_container_width=True):
            summary_data = []
            for field in fields:
                summary_data.append({
                    "Field ID": field.field_id,
                    "Part": field.part_number,
                    "Item": field.item_number,
                    "Label": field.field_label,
                    "Type": field.field_type,
                    "Page": field.page,
                    "Status": "Mapped" if field.is_mapped else ("Questionnaire" if field.to_questionnaire else "Unmapped"),
                    "Mapping": field.db_mapping or ""
                })
            
            df = pd.DataFrame(summary_data)
            csv = df.to_csv(index=False)
            
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"{st.session_state.form_info.get('form_number', 'form')}_field_summary.csv",
                mime="text/csv"
            )
    
    with col2:
        # Export mapping report
        if st.button("📑 Generate Mapping Report", use_container_width=True):
            report = generate_mapping_report(extractor)
            st.download_button(
                label="Download Report",
                data=report,
                file_name=f"{st.session_state.form_info.get('form_number', 'form')}_mapping_report.md",
                mime="text/markdown"
            )
    
    with col3:
        # Copy to clipboard functionality
        if st.button("📋 Copy Summary to Clipboard", use_container_width=True):
            summary = f"""
Form: {st.session_state.form_info.get('form_number', 'Unknown')}
Total Fields: {len(fields)}
Mapped to Database: {mapped}
In Questionnaire: {questionnaire + unmapped}
            """
            st.code(summary)
            st.info("Copy the above summary manually")

def generate_mapping_report(extractor: SmartUSCISExtractor) -> str:
    """Generate a detailed mapping report"""
    fields = st.session_state.extracted_fields
    form_info = st.session_state.form_info
    
    report = f"""# Field Mapping Report

## Form Information
- **Form Number**: {form_info.get('form_number', 'Unknown')}
- **Form Title**: {form_info.get('form_title', 'Unknown')}
- **Total Pages**: {form_info.get('total_pages', 0)}
- **Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Summary Statistics
- **Total Fields Extracted**: {len(fields)}
- **Fields Mapped to Database**: {sum(1 for f in fields if f.is_mapped)}
- **Fields in Questionnaire**: {sum(1 for f in fields if f.to_questionnaire or (not f.is_mapped and not f.to_questionnaire))}
- **Unique Parts**: {len(st.session_state.fields_by_part)}

## Field Mappings by Part

"""
    
    for part, part_fields in st.session_state.fields_by_part.items():
        report += f"### {part}\n\n"
        report += "| Field ID | Item | Label | Type | Status | Mapping |\n"
        report += "|----------|------|-------|------|--------|----------|\n"
        
        for field in part_fields:
            status = "Mapped" if field.is_mapped else ("Questionnaire" if field.to_questionnaire else "Unmapped")
            mapping = field.db_mapping or "-"
            report += f"| {field.field_id} | {field.item_number} | {field.field_label[:40]}... | {field.field_type} | {status} | {mapping} |\n"
        
        report += "\n"
    
    return report

def main():
    st.set_page_config(
        page_title="Smart USCIS Form Extractor",
        page_icon="📄",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize extractor
    extractor = SmartUSCISExtractor()
    
    # Render header
    render_header()
    
    # Create tabs with icons
    tab1, tab2, tab3 = st.tabs(["📤 Upload & Extract", "🎯 Map Fields", "📥 Export"])
    
    with tab1:
        render_upload_tab(extractor)
    
    with tab2:
        render_mapping_tab(extractor)
    
    with tab3:
        render_export_tab(extractor)
    
    # Enhanced sidebar
    with st.sidebar:
        st.markdown("## 📊 Extraction Status")
        
        if st.session_state.extracted_fields:
            fields = st.session_state.extracted_fields
            total = len(fields)
            mapped = sum(1 for f in fields if f.is_mapped)
            quest = sum(1 for f in fields if f.to_questionnaire)
            unmapped = total - mapped - quest
            progress = (mapped + quest) / total if total > 0 else 0
            
            # Visual progress
            st.progress(progress)
            st.caption(f"{progress:.0%} Complete")
            
            # Detailed metrics
            st.metric("Total Fields", total)
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Mapped", mapped)
            with col2:
                st.metric("Quest", quest)
            
            if unmapped > 0:
                st.warning(f"⚠️ {unmapped} unmapped")
            
            st.markdown("---")
            
            # Part breakdown with progress
            st.markdown("### 📑 Parts Progress")
            for part, part_fields in st.session_state.fields_by_part.items():
                complete = sum(1 for f in part_fields if f.is_mapped or f.to_questionnaire)
                part_progress = complete / len(part_fields) if part_fields else 0
                
                st.markdown(f"**{part}**")
                st.progress(part_progress)
                st.caption(f"{complete}/{len(part_fields)} fields")
        else:
            st.info("Upload a PDF to begin")
        
        st.markdown("---")
        st.markdown("### ℹ️ Features")
        st.markdown("""
        - ✅ **Accurate Extraction** - Proper Part/Item structure
        - 🤖 **Smart Suggestions** - AI-powered field matching
        - 🎯 **Flexible Mapping** - One-by-one or bulk mode
        - 📋 **Auto-Questionnaire** - Checkboxes auto-sorted
        - 📥 **Clean Export** - TypeScript & JSON formats
        """)
        
        st.markdown("---")
        st.markdown("### 🚀 Quick Tips")
        st.markdown("""
        1. Start with **Part 1** extraction
        2. Use **Auto-map** for common fields
        3. Send checkboxes to questionnaire
        4. Review unmapped before export
        """)

if __name__ == "__main__":
    main()
