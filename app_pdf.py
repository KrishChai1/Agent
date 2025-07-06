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
        return hash((self.widget_name, self.field_id))
    
    def __eq__(self, other):
        """Check equality based on key fields"""
        if not isinstance(other, PDFField):
            return False
        return self.widget_name == other.widget_name and self.field_id == other.field_id

class SmartUSCISExtractor:
    """Smart USCIS Form PDF Field Extractor with improved accuracy"""
    
    def __init__(self):
        self.init_session_state()
        self.db_paths = self._build_database_paths()
        # Comprehensive part detection patterns
        self.part_patterns = [
            r'Part\s+(\d+)\.?\s*[-–—:]\s*([^\n\r]+)',  # Part 1 - Information About You
            r'Part\s+(\d+)\.?\s+([A-Z][^\n\r]+)',      # Part 1. Information About You
            r'Part\s+(\d+)\.\s*$',                      # Part 1. (at end of line)
            r'Part\s+(\d+)\s+[-–—]',                   # Part 1 -
            r'^Part\s+(\d+)\s*$',                       # Part 1 (standalone)
            r'PART\s+(\d+)',                            # PART 1 (uppercase)
        ]
        self.attorney_part_numbers = set()  # Track which parts are attorney/preparer
    
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
        if 'part_info' not in st.session_state:
            st.session_state.part_info = {}
    
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
            st.session_state.part_info = {}
            self.attorney_part_numbers = set()
            
            # Read PDF
            pdf_bytes = pdf_file.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            # Detect form type
            form_info = self._detect_form_type(doc)
            st.session_state.form_info = form_info
            
            # Build comprehensive page analysis
            page_analysis = self._analyze_pdf_structure(doc)
            
            # Log detected parts
            st.session_state.extraction_log.append(f"=== PDF STRUCTURE ANALYSIS ===")
            st.session_state.extraction_log.append(f"Total pages: {len(doc)}")
            st.session_state.extraction_log.append(f"Detected {len(page_analysis['parts'])} parts in the form")
            
            # Log part details
            for part_num, part_info in sorted(page_analysis['parts'].items()):
                st.session_state.extraction_log.append(
                    f"Part {part_num}: '{part_info['title']}' (Pages: {part_info['start_page']+1}-{part_info['end_page']+1})"
                )
            
            # Log part detection details
            if page_analysis.get('part_locations'):
                st.session_state.extraction_log.append("\n=== PART DETECTION DETAILS ===")
                for loc in page_analysis['part_locations']:
                    st.session_state.extraction_log.append(
                        f"Found Part {loc['part']} on page {loc['page']+1}: '{loc['title']}'"
                    )
            
            # Extract fields with improved logic
            all_fields = []
            seen_fields = set()  # For deduplication
            
            # Process each part
            for part_num in sorted(page_analysis['parts'].keys()):
                part_info = page_analysis['parts'][part_num]
                
                # Skip attorney/preparer parts
                if part_num in self.attorney_part_numbers:
                    st.session_state.extraction_log.append(f"\nSkipping Part {part_num} (Attorney/Preparer section)")
                    continue
                
                st.session_state.extraction_log.append(f"\n=== PROCESSING PART {part_num}: {part_info['title']} ===")
                st.session_state.part_info[part_num] = part_info['title']
                
                # Process all pages for this part
                part_field_count = 0
                for page_idx, page_num in enumerate(part_info['pages']):
                    st.session_state.extraction_log.append(f"  Processing page {page_num + 1} (page {page_idx + 1} of {len(part_info['pages'])} in this part)")
                    
                    fields_on_page = self._extract_fields_from_page(
                        doc, page_num, part_num, page_analysis
                    )
                    
                    st.session_state.extraction_log.append(f"  Found {len(fields_on_page)} fields on page {page_num + 1}")
                    
                    # Deduplicate and add fields
                    for field in fields_on_page:
                        if field.widget_name not in seen_fields:
                            seen_fields.add(field.widget_name)
                            
                            # AUTO-MOVE CHECKBOXES TO QUESTIONNAIRE
                            if field.field_type in ['checkbox', 'radio']:
                                field.to_questionnaire = True
                                st.session_state.extraction_log.append(
                                    f"  Auto-moved {field.field_type}: {field.field_id} - {field.field_label}"
                                )
                            
                            all_fields.append(field)
                            part_field_count += 1
                        else:
                            st.session_state.extraction_log.append(
                                f"  Skipped duplicate: {field.widget_name}"
                            )
                
                st.session_state.extraction_log.append(f"Part {part_num} total: {part_field_count} unique fields")
            
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
            
            # Log summary
            st.session_state.extraction_log.append(f"\n=== EXTRACTION COMPLETE ===")
            st.session_state.extraction_log.append(f"Total fields extracted: {len(all_fields)}")
            st.session_state.extraction_log.append(f"Total parts processed: {len([p for p in page_analysis['parts'].keys() if p not in self.attorney_part_numbers])}")
            
            # Summary by part
            st.session_state.extraction_log.append("\nFields per part:")
            part_counts = defaultdict(int)
            for field in all_fields:
                part_counts[field.part_number] += 1
            
            for part_num in sorted(part_counts.keys()):
                checkboxes_in_part = sum(1 for f in all_fields if f.part_number == part_num and f.field_type in ['checkbox', 'radio'])
                text_in_part = sum(1 for f in all_fields if f.part_number == part_num and f.field_type == 'text')
                st.session_state.extraction_log.append(
                    f"  Part {part_num}: {part_counts[part_num]} fields ({text_in_part} text, {checkboxes_in_part} checkbox/radio)"
                )
            
            checkboxes = sum(1 for f in all_fields if f.field_type in ['checkbox', 'radio'])
            st.session_state.extraction_log.append(f"\nCheckboxes/Radio auto-moved to questionnaire: {checkboxes}")
            
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
            'items_by_page': {},
            'part_locations': []  # Track exact locations of parts
        }
        
        # Enhanced patterns to catch all part variations
        enhanced_patterns = [
            # Standard patterns
            (r'Part\s+(\d+)\.?\s*[-–—:]\s*([^\n\r]+)', re.MULTILINE),
            (r'Part\s+(\d+)\.?\s+([A-Z][^\n\r]+)', re.MULTILINE),
            # Specific pattern for sections like "Part 2. Application Type"
            (r'Part\s+(\d+)\.\s+([A-Za-z\s]+?)(?=\n|\r|$)', re.MULTILINE),
            # Pattern for parts at the beginning of lines
            (r'^Part\s+(\d+)\.?\s*([^\n\r]*)', re.MULTILINE),
            # Pattern with potential whitespace
            (r'^\s*Part\s+(\d+)\.?\s*([^\n\r]*)', re.MULTILINE),
            # All caps
            (r'PART\s+(\d+)\.?\s*([^\n\r]*)', re.MULTILINE | re.IGNORECASE),
            # Without line start requirement (catches parts mid-line)
            (r'Part\s+(\d+)\.?\s+([A-Za-z][A-Za-z\s]+)', 0),
        ]
        
        # First pass: detect all parts and their exact locations
        all_parts = {}
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            
            # Try each pattern
            for pattern, flags in enhanced_patterns:
                matches = list(re.finditer(pattern, text, flags))
                for match in matches:
                    try:
                        part_num = int(match.group(1))
                        part_title = match.group(2).strip() if len(match.groups()) > 1 else ""
                        
                        # Skip if title is too short or looks like noise
                        if part_title and len(part_title) < 100:  # Reasonable title length
                            # Clean title
                            part_title = re.sub(r'\s+', ' ', part_title)
                            part_title = part_title.split('\n')[0].strip()
                            
                            # Remove trailing periods or colons
                            part_title = part_title.rstrip('.:')
                            
                            # Check if it's attorney/preparer section
                            title_lower = part_title.lower()
                            if any(keyword in title_lower for keyword in [
                                'attorney', 'preparer', 'interpreter', 
                                'contact information, declaration', 
                                'person preparing'
                            ]):
                                self.attorney_part_numbers.add(part_num)
                            
                            if part_num not in all_parts or len(part_title) > len(all_parts.get(part_num, {}).get('title', '')):
                                all_parts[part_num] = {
                                    'title': part_title,
                                    'first_page': page_num,
                                    'position': match.start()
                                }
                                
                                # Track location for debugging
                                analysis['part_locations'].append({
                                    'part': part_num,
                                    'title': part_title,
                                    'page': page_num,
                                    'pattern': pattern
                                })
                    except:
                        continue
        
        # If no parts found, try to find them in a different way
        if not all_parts:
            st.session_state.extraction_log.append("Warning: No parts detected with standard patterns, trying alternative detection")
            # Try without multiline flag
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                
                # Simple pattern
                simple_match = re.search(r'Part\s+(\d+)', text)
                if simple_match:
                    part_num = int(simple_match.group(1))
                    if part_num not in all_parts:
                        all_parts[part_num] = {
                            'title': f"Part {part_num}",
                            'first_page': page_num,
                            'position': simple_match.start()
                        }
                        st.session_state.extraction_log.append(f"Found Part {part_num} on page {page_num + 1} using simple pattern")
        
        # Validation check for common USCIS forms
        if not all_parts:
            st.session_state.extraction_log.append("⚠️ WARNING: No parts detected in the PDF!")
        else:
            # Check for expected parts based on form type
            form_number = st.session_state.form_info.get('form_number', '')
            if form_number == 'I-539':
                expected_parts = [1, 2, 3, 4, 5]  # Parts 1-5 are main content
                missing_parts = [p for p in expected_parts if p not in all_parts]
                if missing_parts:
                    st.session_state.extraction_log.append(f"⚠️ WARNING: Expected parts missing: {missing_parts}")
            elif form_number == 'I-824':
                expected_parts = [1, 2, 3, 4]  # Parts 1-4 are main content
                missing_parts = [p for p in expected_parts if p not in all_parts]
                if missing_parts:
                    st.session_state.extraction_log.append(f"⚠️ WARNING: Expected parts missing: {missing_parts}")
        
        # Second pass: determine page ranges for each part
        sorted_parts = sorted(all_parts.keys())
        
        # Build page-to-part mapping
        current_part = 0
        for page_num in range(len(doc)):
            page_text = doc[page_num].get_text()
            
            # Check if a new part starts on this page
            for part_num in sorted_parts:
                if all_parts[part_num]['first_page'] == page_num:
                    current_part = part_num
                    break
            
            if current_part > 0:
                analysis['page_to_part'][page_num] = current_part
        
        # Build parts dictionary with page ranges
        for i, part_num in enumerate(sorted_parts):
            part_info = all_parts[part_num]
            
            # Determine pages for this part
            start_page = part_info['first_page']
            
            # Find end page (start of next part or end of document)
            end_page = len(doc) - 1
            for j in range(i + 1, len(sorted_parts)):
                next_part_start = all_parts[sorted_parts[j]]['first_page']
                if next_part_start > start_page:
                    end_page = next_part_start - 1
                    break
            
            # Create part entry
            analysis['parts'][part_num] = {
                'title': part_info['title'],
                'start_page': start_page,
                'end_page': end_page,
                'pages': list(range(start_page, end_page + 1))
            }
            
            st.session_state.extraction_log.append(
                f"Part {part_num} spans pages {start_page + 1} to {end_page + 1}"
            )
        
        # Third pass: extract items from each page
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            
            # Get part number for this page
            part_num = analysis['page_to_part'].get(page_num, 0)
            
            # Extract items
            if part_num > 0:
                analysis['items_by_page'][page_num] = self._extract_items_from_text(text, part_num)
        
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
        
        # Log widget extraction
        st.session_state.extraction_log.append(f"Page {page_num + 1}: Found {len(widgets)} widgets")
        
        # Group widgets by position for better item association
        widgets_by_position = []
        for widget in widgets:
            if not widget.field_name:
                continue
                
            # Skip if this looks like an attorney field
            if self._is_attorney_field(widget.field_name, page_text):
                continue
            
            rect = widget.rect
            widgets_by_position.append({
                'widget': widget,
                'y_pos': rect.y0,
                'x_pos': rect.x0,
                'rect': (rect.x0, rect.y0, rect.x1, rect.y1),
                'name': widget.field_name,
                'type': widget.field_type,
                'value': widget.field_value
            })
            
            # Debug logging
            st.session_state.extraction_log.append(
                f"  Widget: {widget.field_name} at ({rect.x0:.1f}, {rect.y0:.1f})"
            )
        
        # Sort by position (top to bottom, left to right)
        widgets_by_position.sort(key=lambda w: (w['y_pos'], w['x_pos']))
        
        # Process widgets in groups based on Y position
        widget_groups = []
        current_group = []
        last_y = None
        
        for widget_data in widgets_by_position:
            if last_y is None or abs(widget_data['y_pos'] - last_y) < 5:  # Same line threshold
                current_group.append(widget_data)
            else:
                if current_group:
                    widget_groups.append(current_group)
                current_group = [widget_data]
            last_y = widget_data['y_pos']
        
        if current_group:
            widget_groups.append(current_group)
        
        # Process each group
        field_counter = defaultdict(lambda: defaultdict(int))
        
        for group_idx, group in enumerate(widget_groups):
            # Sort group by X position (left to right)
            group.sort(key=lambda w: w['x_pos'])
            
            # Determine the main item for this group
            group_y = group[0]['y_pos']
            
            # Find closest item
            closest_item = None
            min_distance = float('inf')
            for item in items_on_page:
                distance = abs(item['y_position'] - group_y)
                if distance < min_distance:
                    min_distance = distance
                    closest_item = item
            
            # If no close item, try to infer from widget names
            if not closest_item or min_distance > 50:
                # Try to extract item info from first widget in group
                first_widget = group[0]['widget']
                item_info = self._match_widget_to_item_improved(
                    first_widget, group_y, items_on_page, page_text
                )
            else:
                item_info = {
                    'number': closest_item['number'],
                    'label': closest_item['label']
                }
            
            # Process each widget in the group
            for widget_idx, widget_data in enumerate(group):
                widget = widget_data['widget']
                
                # Generate sub-item letter if multiple widgets in same group
                if len(group) > 1:
                    sub_letter = chr(97 + widget_idx)  # a, b, c, etc.
                    field_item_number = f"{item_info['number']}{sub_letter}"
                else:
                    field_item_number = item_info['number']
                
                # Count fields per item
                field_counter[part_num][field_item_number] += 1
                count = field_counter[part_num][field_item_number]
                
                # Generate field ID
                if count == 1:
                    field_id = f"P{part_num}_{field_item_number}"
                else:
                    field_id = f"P{part_num}_{field_item_number}_{count}"
                
                # Determine field label
                if len(group) > 1:
                    # For grouped fields, try to extract specific label
                    specific_label = self._extract_field_label_from_group_context(
                        widget, widget_idx, group, page_text
                    )
                    field_label = specific_label
                else:
                    field_label = item_info['label']
                
                # Create field
                pdf_field = PDFField(
                    widget_name=widget.field_name,
                    field_id=field_id,
                    part_number=part_num,
                    item_number=field_item_number,
                    field_label=field_label,
                    field_type=self._get_field_type(widget.field_type),
                    page=page_num + 1,
                    value=widget.field_value or '',
                    widget_rect=widget_data['rect']
                )
                
                fields.append(pdf_field)
        
        return fields
    
    def _extract_field_label_from_group_context(self, widget, widget_idx: int, 
                                                group: List[dict], page_text: str) -> str:
        """Extract field label for widgets in a group (like name fields)"""
        widget_name = widget.field_name.lower()
        
        # Common patterns for grouped fields
        if widget_idx == 0:
            if any(x in widget_name for x in ['family', 'last', 'surname']):
                return "Family Name (Last Name)"
            elif any(x in widget_name for x in ['street', 'address']):
                return "Street Number and Name"
            elif 'in care' in widget_name or 'careof' in widget_name:
                return "In Care Of Name"
        elif widget_idx == 1:
            if any(x in widget_name for x in ['given', 'first']):
                return "Given Name (First Name)"
            elif any(x in widget_name for x in ['apt', 'apartment', 'suite']):
                return "Apt. Ste. Flr. Number"
        elif widget_idx == 2:
            if any(x in widget_name for x in ['middle']):
                return "Middle Name"
            elif any(x in widget_name for x in ['city', 'town']):
                return "City or Town"
        elif widget_idx == 3:
            if 'state' in widget_name:
                return "State"
        elif widget_idx == 4:
            if any(x in widget_name for x in ['zip', 'postal']):
                return "ZIP Code"
        
        # Default to extracting from widget
        return self._extract_field_label(widget, page_text)
    
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
            'I-140': 'Immigrant Petition for Alien Worker',
            'I-526': 'Immigrant Petition by Alien Entrepreneur',
            'I-751': 'Petition to Remove Conditions on Residence',
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
            'signature of attorney', 'law firm', 'eligibility'
        ]
        
        field_lower = field_name.lower()
        
        # Check field name
        if any(keyword in field_lower for keyword in attorney_keywords):
            return True
            
        return False
    
    def _extract_items_from_text(self, page_text: str, part_number: int) -> List[dict]:
        """Extract item numbers and labels from page text with improved patterns"""
        items = []
        
        # Enhanced patterns for USCIS forms
        patterns = [
            # Item Number X. pattern (most common in USCIS forms)
            r'^\s*Item\s+Number\s+(\d+[a-z]?)\.\s*([^\n\r]+)',
            # Standard numbered items with letters (2.a., 2.b., etc.)
            r'^\s*(\d+[a-z])\.\s+([^\n\r]+)',
            # Standard numbered items
            r'^\s*(\d+)\.\s+([^\n\r]+)',
            # Letter items alone (a., b., c.) - often sub-items
            r'^\s*([a-z])\.\s+([^\n\r]+)',
            # Checkbox patterns with numbers
            r'^\s*□\s*(\d+[a-z]?)\.\s*([^\n\r]+)',
            r'^\s*\[\s*\]\s*(\d+[a-z]?)\.\s*([^\n\r]+)',
            # Radio button patterns
            r'^\s*○\s*(\d+[a-z]?)\.\s*([^\n\r]+)',
            r'^\s*\(\s*\)\s*(\d+[a-z]?)\.\s*([^\n\r]+)',
            # Items without period
            r'^\s*(\d+[a-z]?)\s+([A-Z][^\n\r]+)',
            # For special cases like "A-Number"
            r'►\s*A-(\d+)',
            # Inline items (like "3. USCIS Online Account Number")
            r'(\d+)\.\s+([A-Z][A-Za-z\s\(\)]+?)(?:\s*\(|$|\n)',
        ]
        
        seen_items = set()
        lines = page_text.split('\n')
        
        # Process line by line for better context
        for line_idx, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
                
            for pattern in patterns:
                match = re.match(pattern, line)
                if match:
                    item_num = match.group(1).strip()
                    item_label = match.group(2).strip() if len(match.groups()) > 1 else ""
                    
                    # For A-Number pattern
                    if pattern == r'►\s*A-(\d+)':
                        item_num = "A-Number"
                        item_label = "Alien Registration Number"
                    
                    # Clean up label
                    item_label = re.sub(r'\s+', ' ', item_label)
                    
                    # Remove trailing punctuation and parentheses content
                    item_label = re.sub(r'\s*\([^)]*\)\s*
    
    def _estimate_y_position(self, text: str, char_position: int) -> float:
        """Estimate Y position based on character position in text"""
        # Count newlines before this position
        newlines_before = text[:char_position].count('\n')
        # Rough estimate: each line is about 20 units
        return newlines_before * 20
    
    def _match_widget_to_item_improved(self, widget, y_pos: float, 
                                       items: List[dict], page_text: str) -> dict:
        """Improved widget to item matching with better heuristics for USCIS forms"""
        widget_name = widget.field_name
        widget_name_lower = widget_name.lower()
        
        # Extract meaningful parts from widget name
        # Remove common prefixes and clean up
        cleaned_name = widget_name
        for prefix in ['form1[0].', '#subform[', 'Page', 'Pg', 'Pt', 'Part']:
            if cleaned_name.startswith(prefix):
                cleaned_name = re.sub(rf'^{re.escape(prefix)}[^\]]*\]?\.?', '', cleaned_name)
        
        # Remove array indices
        cleaned_name = re.sub(r'\[\d+\]', '', cleaned_name)
        cleaned_name = cleaned_name.strip('.]')
        
        # Common USCIS form field mappings based on widget patterns
        widget_patterns = {
            # Name fields
            ('line1', 'familyname', 'lastname'): {'number': '1a', 'label': 'Family Name (Last Name)'},
            ('line2', 'givenname', 'firstname'): {'number': '1b', 'label': 'Given Name (First Name)'},
            ('line3', 'middlename'): {'number': '1c', 'label': 'Middle Name'},
            
            # A-Number
            ('line4', 'anumber', 'alienregistration'): {'number': '2', 'label': 'Alien Registration Number (A-Number)'},
            
            # USCIS Account
            ('line5', 'uscisaccount', 'onlineaccount'): {'number': '3', 'label': 'USCIS Online Account Number'},
            
            # Address fields
            ('line6', 'careof', 'incareof'): {'number': '4a', 'label': 'In Care Of Name'},
            ('line7', 'street', 'address'): {'number': '4b', 'label': 'Street Number and Name'},
            ('line8', 'apt', 'apartment', 'suite'): {'number': '4c', 'label': 'Apt. Ste. Flr. Number'},
            ('line9', 'city', 'citytown'): {'number': '4d', 'label': 'City or Town'},
            ('line10', 'state'): {'number': '4e', 'label': 'State'},
            ('line11', 'zip', 'zipcode'): {'number': '4f', 'label': 'ZIP Code'},
            
            # Personal info
            ('line12', 'countryofbirth', 'birthcountry'): {'number': '7', 'label': 'Country of Birth'},
            ('line13', 'citizenship', 'nationality'): {'number': '8', 'label': 'Country of Citizenship or Nationality'},
            ('line14', 'dateofbirth', 'dob'): {'number': '9', 'label': 'Date of Birth'},
            ('line15', 'ssn', 'socialsecurity'): {'number': '10', 'label': 'U.S. Social Security Number'},
            
            # Immigration info
            ('line16', 'dateofarrival', 'lastarrival'): {'number': '11', 'label': 'Date of Last Arrival Into the United States'},
            ('line17', 'i94', 'arrivalrecord'): {'number': '11', 'label': 'Form I-94 Arrival-Departure Record Number'},
            ('line18', 'passport'): {'number': '11', 'label': 'Passport Number'},
            ('line19', 'travel'): {'number': '11', 'label': 'Travel Document Number'},
            ('line20', 'currentstatus', 'nonimmigrant'): {'number': '12', 'label': 'Current Nonimmigrant Status'},
            ('line21', 'expires', 'statusexpires'): {'number': '12', 'label': 'Date Status Expires'},
            
            # Contact info
            ('line22', 'daytime', 'dayphone'): {'number': '1', 'label': 'Daytime Telephone Number'},
            ('line23', 'mobile', 'cellphone'): {'number': '2', 'label': 'Mobile Telephone Number'},
            ('line24', 'email'): {'number': '3', 'label': 'Email Address'},
            
            # Checkboxes
            ('checkbox', 'cb', 'chk'): {'number': '99', 'label': 'Checkbox'},
            ('radio', 'rb', 'opt'): {'number': '99', 'label': 'Radio Button'},
        }
        
        # Try to match based on widget patterns
        for patterns, mapping in widget_patterns.items():
            if any(p in cleaned_name.lower() for p in patterns):
                # If we have items, try to find a better match
                if items:
                    for item in items:
                        if any(keyword in item['label'].lower() for keyword in patterns):
                            return {
                                'number': item['number'],
                                'label': item['label']
                            }
                return mapping
        
        # Try line number extraction from widget name
        line_match = re.search(r'Line(\d+)', widget_name, re.IGNORECASE)
        if line_match:
            line_num = int(line_match.group(1))
            # Map line numbers to common USCIS form structure
            if line_num <= 3:  # Name fields
                return {'number': f'1{chr(96+line_num)}', 'label': f'Name Field {line_num}'}
            elif line_num <= 11:  # Address fields
                return {'number': f'4{chr(96+line_num-3)}', 'label': f'Address Field {line_num-3}'}
        
        # Try to find closest item by Y position
        if items:
            closest_item = None
            min_distance = float('inf')
            
            for item in items:
                # Calculate distance
                distance = abs(item.get('y_position', 0) - y_pos)
                if distance < min_distance and distance < 100:  # Within reasonable distance
                    min_distance = distance
                    closest_item = item
            
            if closest_item:
                return {
                    'number': closest_item['number'],
                    'label': closest_item['label']
                }
        
        # Extract text field information from widget name
        text_match = re.search(r'Text(\d+)', widget_name)
        if text_match:
            field_num = text_match.group(1)
            return {
                'number': field_num,
                'label': self._extract_field_label(widget, page_text)
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
        
        # Remove common prefixes and clean up
        prefixes_to_remove = [
            'form1[0].', '#subform[0].', '#subform[', 'Page1[0].', 'Page2[0].', 'Page3[0].',
            'Page4[0].', 'Page5[0].', 'Page6[0].', 'Page7[0].', 'Page8[0].',
            'Pg1_', 'Pg2_', 'Pg3_', 'Pg4_', 'Pg5_',
            'P1_', 'P2_', 'P3_', 'P4_', 'P5_',
            'Pt1_', 'Pt2_', 'Pt3_', 'Pt4_', 'Pt5_',
            'Part1', 'Part2', 'Part3', 'Part4', 'Part5',
            'TextField[', 'TextField1[', 'TextField2[',
            'CheckBox[', 'CheckBox1[', 'CheckBox2[',
            'RadioButton[', 'Radio[',
            'DateField[', 'Date['
        ]
        
        cleaned_name = field_name
        for prefix in prefixes_to_remove:
            if cleaned_name.startswith(prefix):
                cleaned_name = cleaned_name[len(prefix):]
                break
        
        # Remove array indices and closing brackets
        cleaned_name = re.sub(r'\[\d+\]', '', cleaned_name)
        cleaned_name = cleaned_name.rstrip(']').rstrip('[')
        cleaned_name = cleaned_name.strip('_')
        
        # Extract meaningful part
        parts = cleaned_name.split('.')
        if parts:
            label = parts[-1]
            
            # Convert various naming conventions to readable format
            # Handle camelCase
            label = re.sub(r'([a-z])([A-Z])', r'\1 \2', label)
            # Handle snake_case
            label = label.replace('_', ' ')
            # Handle abbreviations
            label = label.replace('DOB', 'Date of Birth')
            label = label.replace('SSN', 'Social Security Number')
            label = label.replace('Apt', 'Apartment')
            label = label.replace('Ste', 'Suite')
            label = label.replace('Flr', 'Floor')
            
            # Capitalize appropriately
            words = label.split()
            label = ' '.join(word.capitalize() for word in words)
            
            return label.strip()
        
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
            
        # Try to extract any number
        numbers = re.findall(r'\d+', str(item_num))
        if numbers:
            return (int(numbers[0]), str(item_num))
            
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
        
        # Add part information
        ts += "// Form Structure:\n"
        for part_num, part_title in sorted(st.session_state.part_info.items()):
            part_fields = [f for f in fields if f.part_number == part_num]
            ts += f"// Part {part_num}: {part_title} ({len(part_fields)} fields)\n"
        ts += "\n"
        
        ts += f"export const {form_name} = {{\n"
        
        # Add database mappings
        for obj, fields_list in sorted(db_fields.items()):
            ts += f"  {obj}Data: {{\n"
            for field in sorted(fields_list, key=lambda f: (f.part_number, self._parse_item_number_for_sort(f.item_number))):
                path = field.db_mapping.replace(f"{obj}.", "")
                field_suffix = ":TextBox" if field.field_type == "text" else f":{field.field_type.title()}Box"
                comment = f" // Part {field.part_number}, Item {field.item_number}: {field.field_label[:50]}"
                if len(field.field_label) > 50:
                    comment += "..."
                ts += f'    "{field.field_id}{field_suffix}": "{path}",{comment}\n'
            ts = ts.rstrip(',\n') + '\n'
            ts += "  },\n\n"
        
        # Add questionnaire fields grouped by part
        if questionnaire_fields:
            ts += "  questionnaireData: {\n"
            
            # Group by part for better organization
            questionnaire_by_part = defaultdict(list)
            for field in questionnaire_fields:
                questionnaire_by_part[field.part_number].append(field)
            
            for part_num in sorted(questionnaire_by_part.keys()):
                ts += f"    // Part {part_num} - {st.session_state.part_info.get(part_num, 'Unknown')}\n"
                for field in sorted(questionnaire_by_part[part_num], key=lambda f: self._parse_item_number_for_sort(f.item_number)):
                    ts += f'    "{field.field_id}": {{\n'
                    ts += f'      description: "{field.field_label}",\n'
                    ts += f'      fieldType: "{field.field_type}",\n'
                    ts += f'      part: {field.part_number},\n'
                    ts += f'      item: "{field.item_number}",\n'
                    ts += f'      page: {field.page},\n'
                    ts += f'      required: true\n'
                    ts += "    },\n"
                ts += "\n"
            
            ts = ts.rstrip(',\n') + '\n'
            ts += "  }\n"
        
        ts = ts.rstrip(',\n') + '\n'
        ts += "};\n"
        
        return ts
    
    def generate_json(self, fields: List[PDFField]) -> str:
        """Generate JSON for questionnaire fields"""
        questionnaire_fields = [f for f in fields if not f.is_mapped or f.field_type in ['checkbox', 'radio']]
        
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
            "checkboxCount": sum(1 for f in questionnaire_fields if f.field_type in ['checkbox', 'radio']),
            "textFieldCount": sum(1 for f in questionnaire_fields if f.field_type == 'text'),
            "sections": []
        }
        
        for part_num in sorted(by_part.keys()):
            section = {
                "part": part_num,
                "title": st.session_state.part_info.get(part_num, f"Part {part_num}"),
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
                    "widgetName": field.widget_name,  # Include for debugging
                    "required": True  # Default to required
                }
                
                # Add validation rules for specific field types
                if 'date' in field.field_label.lower():
                    field_data["validation"] = {"type": "date", "format": "MM/DD/YYYY"}
                elif 'email' in field.field_label.lower():
                    field_data["validation"] = {"type": "email"}
                elif 'phone' in field.field_label.lower() or 'telephone' in field.field_label.lower():
                    field_data["validation"] = {"type": "phone"}
                elif 'zip' in field.field_label.lower():
                    field_data["validation"] = {"type": "zip"}
                
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
            max-height: 400px;
            overflow-y: auto;
            font-family: monospace;
            font-size: 0.875rem;
        }
        .extraction-log-entry {
            margin: 0.25rem 0;
            padding: 0.25rem 0;
            border-bottom: 1px solid #f3f4f6;
        }
        .metric-card {
            background: white;
            border: 1px solid #e5e7eb;
            padding: 1.5rem;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        .metric-value {
            font-size: 2rem;
            font-weight: bold;
            color: #2563eb;
            margin: 0.5rem 0;
        }
        .metric-label {
            font-size: 0.875rem;
            color: #6b7280;
        }
        .checkbox-indicator {
            background: #fef3c7;
            border: 1px solid #fbbf24;
            padding: 0.5rem 1rem;
            border-radius: 8px;
            margin: 1rem 0;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        .checkbox-indicator svg {
            width: 20px;
            height: 20px;
            color: #f59e0b;
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="main-header">
        <h1>📄 Smart USCIS Form Field Extractor</h1>
        <p>Advanced extraction with automatic checkbox handling</p>
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
                with st.spinner("Analyzing PDF structure and extracting all fields..."):
                    if extractor.extract_fields_from_pdf(uploaded_file):
                        st.success(f"✅ Successfully extracted {len(st.session_state.extracted_fields)} fields from {len(st.session_state.fields_by_part)} parts!")
                        
                        # Show checkbox auto-move notification
                        checkboxes = sum(1 for f in st.session_state.extracted_fields if f.field_type in ['checkbox', 'radio'])
                        if checkboxes > 0:
                            st.markdown(f"""
                            <div class="checkbox-indicator">
                                ☑️ <strong>{checkboxes} checkboxes/radio buttons</strong> were automatically moved to questionnaire
                            </div>
                            """, unsafe_allow_html=True)
                        
                        st.rerun()
    
    # Display extracted fields
    if st.session_state.extracted_fields:
        st.markdown("---")
        st.markdown("## 📊 Extraction Results")
        
        # Summary metrics
        fields = st.session_state.extracted_fields
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        
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
            text_fields = sum(1 for f in fields if f.field_type == 'text')
            st.metric("Text Fields", text_fields)
        with col6:
            st.metric("Pages", st.session_state.form_info.get('total_pages', 0))
        
        # Show extraction log
        with st.expander("📝 View Extraction Log", expanded=False):
            st.markdown('<div class="extraction-log">', unsafe_allow_html=True)
            for log_entry in st.session_state.extraction_log:
                if log_entry.startswith("==="):
                    st.markdown(f'<div class="extraction-log-entry"><strong>{log_entry}</strong></div>', unsafe_allow_html=True)
                elif log_entry.startswith("Part"):
                    st.markdown(f'<div class="extraction-log-entry" style="color: #2563eb;"><strong>{log_entry}</strong></div>', unsafe_allow_html=True)
                elif "Auto-moved" in log_entry:
                    st.markdown(f'<div class="extraction-log-entry" style="color: #f59e0b;">{log_entry}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="extraction-log-entry">{log_entry}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        
        # Display by parts
        st.markdown("### 📑 Fields by Part")
        
        for part, part_fields in st.session_state.fields_by_part.items():
            # Count field types
            text_count = sum(1 for f in part_fields if f.field_type == 'text')
            checkbox_count = sum(1 for f in part_fields if f.field_type in ['checkbox', 'radio'])
            other_count = len(part_fields) - text_count - checkbox_count
            
            # Get part title
            part_num = int(part.split()[1])
            part_title = st.session_state.part_info.get(part_num, "")
            
            with st.expander(
                f"**{part}** - {part_title} ({len(part_fields)} fields: {text_count} text, {checkbox_count} checkbox/radio, {other_count} other)", 
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
    
    # Show checkbox notification
    checkboxes = sum(1 for f in fields if f.field_type in ['checkbox', 'radio'])
    if checkboxes > 0:
        st.info(f"ℹ️ All {checkboxes} checkbox/radio fields have been automatically moved to questionnaire")
    
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
        if st.button("🗺️ Auto-map Common Fields", use_container_width=True):
            count = auto_map_common_fields(extractor)
            if count > 0:
                st.success(f"Auto-mapped {count} fields")
                st.rerun()
    
    with col3:
        # Move all text fields to questionnaire
        if st.button("📝 All Text → Quest", use_container_width=True):
            count = 0
            for field in fields:
                if field.field_type == 'text' and not field.is_mapped and not field.to_questionnaire:
                    field.to_questionnaire = True
                    count += 1
            if count > 0:
                st.success(f"Moved {count} text fields to questionnaire")
                st.rerun()
    
    with col4:
        if st.button("🔄 Reset All Mappings", use_container_width=True):
            for field in fields:
                field.is_mapped = False
                # Keep checkboxes in questionnaire
                if field.field_type in ['checkbox', 'radio']:
                    field.to_questionnaire = True
                else:
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
    
    # Comprehensive field mappings for USCIS forms
    auto_mappings = {
        # Name fields
        r'family\s*name|last\s*name|surname': 'beneficiary.Beneficiary.beneficiaryLastName',
        r'given\s*name|first\s*name': 'beneficiary.Beneficiary.beneficiaryFirstName',
        r'middle\s*name': 'beneficiary.Beneficiary.beneficiaryMiddleName',
        
        # ID numbers
        r'alien\s*(?:registration\s*)?number|a[-\s]*number': 'beneficiary.Beneficiary.alienNumber',
        r'uscis\s*online\s*account': 'beneficiary.Beneficiary.uscisOnlineAccountNumber',
        r'social\s*security|ssn': 'beneficiary.Beneficiary.beneficiarySsn',
        
        # Personal info
        r'date\s*of\s*birth|birth\s*date|dob': 'beneficiary.Beneficiary.beneficiaryDateOfBirth',
        r'country\s*of\s*birth': 'beneficiary.Beneficiary.beneficiaryCountryOfBirth',
        r'country\s*of\s*citizenship|nationality': 'beneficiary.Beneficiary.beneficiaryCitizenOfCountry',
        r'gender|sex': 'beneficiary.Beneficiary.beneficiaryGender',
        r'marital\s*status': 'beneficiary.Beneficiary.maritalStatus',
        
        # Contact info
        r'daytime\s*(?:telephone|phone)|day\s*phone': 'beneficiary.ContactInfo.daytimeTelephoneNumber',
        r'mobile\s*(?:telephone|phone)|cell\s*phone': 'beneficiary.ContactInfo.mobileTelephoneNumber',
        r'email\s*address': 'beneficiary.ContactInfo.emailAddress',
        
        # Mailing Address fields
        r'(?:mailing\s*)?(?:street\s*(?:number\s*and\s*)?name|street\s*address)': 'beneficiary.MailingAddress.addressStreet',
        r'(?:mailing\s*)?(?:apt|apartment|suite|unit)': 'beneficiary.MailingAddress.addressAptSteFlrNumber',
        r'(?:mailing\s*)?(?:city|town)': 'beneficiary.MailingAddress.addressCity',
        r'(?:mailing\s*)?state': 'beneficiary.MailingAddress.addressState',
        r'(?:mailing\s*)?(?:zip\s*code|postal\s*code)': 'beneficiary.MailingAddress.addressZip',
        r'(?:mailing\s*)?country': 'beneficiary.MailingAddress.addressCountry',
        r'in\s*care\s*of|c/o': 'beneficiary.MailingAddress.inCareOfName',
        
        # Physical Address (if different from mailing)
        r'physical\s*(?:street|address)': 'beneficiary.PhysicalAddress.addressStreet',
        r'physical.*(?:city|town)': 'beneficiary.PhysicalAddress.addressCity',
        r'physical.*state': 'beneficiary.PhysicalAddress.addressState',
        r'physical.*(?:zip|postal)': 'beneficiary.PhysicalAddress.addressZip',
        
        # Document fields
        r'passport\s*number': 'beneficiary.PassportDetails.Passport.passportNumber',
        r'passport\s*(?:issue|issuance)\s*country': 'beneficiary.PassportDetails.Passport.passportIssueCountry',
        r'passport\s*(?:issue|issuance)\s*date': 'beneficiary.PassportDetails.Passport.passportIssueDate',
        r'passport\s*expir': 'beneficiary.PassportDetails.Passport.passportExpiryDate',
        r'travel\s*document\s*number': 'beneficiary.TravelDocument.travelDocumentNumber',
        r'travel.*country.*issuance': 'beneficiary.TravelDocument.countryOfIssuance',
        
        # Immigration status
        r'current\s*(?:nonimmigrant\s*)?status': 'beneficiary.VisaDetails.Visa.currentNonimmigrantStatus',
        r'date\s*(?:status\s*)?expires|expiration\s*date': 'beneficiary.VisaDetails.Visa.dateStatusExpires',
        r'visa\s*number': 'beneficiary.VisaDetails.Visa.visaNumber',
        r'i-94\s*number|form\s*i-94|arrival.*departure.*record': 'beneficiary.I94Details.I94.formI94ArrivalDepartureRecordNumber',
        r'date\s*of\s*(?:last\s*)?arrival': 'beneficiary.I94Details.I94.dateOfLastArrival',
        r'sevis\s*number': 'beneficiary.EducationDetails.studentEXTInfoSEVISNumber',
        
        # Biographic info
        r'eye\s*color': 'beneficiary.BiographicInfo.eyeColor',
        r'hair\s*color': 'beneficiary.BiographicInfo.hairColor',
        r'height.*feet': 'beneficiary.BiographicInfo.heightFeet',
        r'height.*inches': 'beneficiary.BiographicInfo.heightInches',
        r'weight.*pounds': 'beneficiary.BiographicInfo.weightPounds',
        r'race': 'beneficiary.BiographicInfo.race',
        r'ethnicity': 'beneficiary.BiographicInfo.ethnicity',
    }
    
    for field in fields:
        # Skip if already mapped, in questionnaire, or is a checkbox
        if field.is_mapped or field.to_questionnaire or field.field_type in ['checkbox', 'radio']:
            continue
            
        label_lower = field.field_label.lower().strip()
        
        # Try each mapping pattern
        for pattern, db_path in auto_mappings.items():
            if re.search(pattern, label_lower, re.IGNORECASE):
                field.db_mapping = db_path
                field.is_mapped = True
                count += 1
                st.session_state.extraction_log.append(f"Auto-mapped: {field.field_id} '{field.field_label}' → {db_path}")
                break
    
    return count

def render_one_by_one_mapping(extractor: SmartUSCISExtractor):
    """Render one-by-one field mapping with better UX"""
    fields = st.session_state.extracted_fields
    current_idx = st.session_state.current_field_index
    
    # Get unmapped text fields only (checkboxes already in questionnaire)
    unmapped_indices = [i for i, f in enumerate(fields) 
                       if not f.is_mapped and not f.to_questionnaire and f.field_type == 'text']
    
    if not unmapped_indices:
        st.success("✅ All text fields have been processed! Checkboxes are automatically in questionnaire.")
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
    
    st.markdown(f"### Processing Text Field {unmapped_indices.index(current_idx) + 1} of {len(unmapped_indices)}")
    
    # Current field
    field = fields[current_idx]
    
    # Field card with better styling
    st.markdown('<div class="field-card">', unsafe_allow_html=True)
    
    # Field information
    col1, col2 = st.columns([3, 1])
    with col1:
        part_title = st.session_state.part_info.get(field.part_number, f"Part {field.part_number}")
        st.markdown(f'<div class="field-id">{part_title}, Item {field.item_number}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="field-label">{field.field_label}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="field-meta">Field ID: {field.field_id} | Type: {field.field_type} | Page: {field.page}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="field-meta">Widget: {field.widget_name}</div>', unsafe_allow_html=True)
    
    with col2:
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
                    next_idx = unmapped_indices.index(current_idx) + 1
                    if next_idx < len(unmapped_indices):
                        st.session_state.current_field_index = unmapped_indices[next_idx]
                    else:
                        st.session_state.current_field_index = len(fields)
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
                next_idx = unmapped_indices.index(current_idx) + 1
                if next_idx < len(unmapped_indices):
                    st.session_state.current_field_index = unmapped_indices[next_idx]
                else:
                    st.session_state.current_field_index = len(fields)
                st.rerun()
    
    # Or send to questionnaire
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📋 Send to Questionnaire", use_container_width=True, type="secondary"):
            field.to_questionnaire = True
            field.is_mapped = False
            field.db_mapping = None
            # Move to next unmapped
            next_idx = unmapped_indices.index(current_idx) + 1
            if next_idx < len(unmapped_indices):
                st.session_state.current_field_index = unmapped_indices[next_idx]
            else:
                st.session_state.current_field_index = len(fields)
            st.rerun()
    
    with col2:
        if st.button("⏭️ Skip for Now", use_container_width=True):
            # Move to next unmapped
            next_idx = unmapped_indices.index(current_idx) + 1
            if next_idx < len(unmapped_indices):
                st.session_state.current_field_index = unmapped_indices[next_idx]
            else:
                st.session_state.current_field_index = 0
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
            unmapped_text = [f for f in display_fields if not f.is_mapped and not f.to_questionnaire and f.field_type == 'text']
            if unmapped_text:
                if st.button(f"📋 Send {len(unmapped_text)} Unmapped Text Fields to Questionnaire"):
                    for field in unmapped_text:
                        field.to_questionnaire = True
                    st.success(f"Sent {len(unmapped_text)} fields to questionnaire")
                    st.rerun()
    
    # Display fields with better layout
    for i, field in enumerate(display_fields):
        with st.container():
            col1, col2, col3, col4 = st.columns([3, 3.5, 1, 0.5])
            
            with col1:
                # Field info with better formatting
                part_title = st.session_state.part_info.get(field.part_number, f"Part {field.part_number}")
                st.markdown(f"**{field.field_id}** - {part_title}")
                st.markdown(f"Item {field.item_number} • {field.field_type} • Page {field.page}")
                st.caption(field.field_label[:80] + "..." if len(field.field_label) > 80 else field.field_label)
            
            with col2:
                if field.is_mapped:
                    st.success(f"✅ Mapped to: {field.db_mapping}")
                elif field.to_questionnaire:
                    st.warning("📋 In Questionnaire")
                else:
                    # Only show mapping for text fields
                    if field.field_type == 'text':
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
                    else:
                        st.info(f"Auto-assigned to questionnaire ({field.field_type})")
            
            with col3:
                # Quick action buttons
                if field.is_mapped or field.to_questionnaire:
                    if field.field_type == 'text':  # Only allow reset for text fields
                        if st.button("↩️ Reset", key=f"reset_{field.field_id}_{i}", help="Reset mapping"):
                            field.is_mapped = False
                            field.to_questionnaire = False
                            field.db_mapping = None
                            st.rerun()
                else:
                    if field.field_type == 'text':
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
    noise_words = ['the', 'of', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'if', 'any', 'your', 'please', 'provide']
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
            # Check if context matches
            context_matches = {
                'address': ['street', 'city', 'state', 'zip', 'apt'],
                'passport': ['passport', 'issue', 'expir'],
                'contact': ['phone', 'telephone', 'email', 'mobile'],
                'visa': ['visa', 'status', 'nonimmigrant'],
                'biographic': ['height', 'weight', 'eye', 'hair', 'race']
            }
            
            for context, keywords in context_matches.items():
                if context in parent:
                    if any(kw in label_lower for kw in keywords):
                        score += 30
        
        # Special patterns with higher scores
        special_patterns = {
            r'family\s*name|last\s*name': ['lastname', 'familyname', 'beneficiarylastname'],
            r'given\s*name|first\s*name': ['firstname', 'givenname', 'beneficiaryfirstname'],
            r'middle\s*name': ['middlename', 'beneficiarymiddlename'],
            r'a[-\s]*number|alien.*number': ['aliennumber', 'anumber'],
            r'date.*birth|birth.*date|dob': ['dateofbirth', 'birthdate', 'beneficiarydateofbirth'],
            r'country.*birth': ['countryofbirth', 'birthcountry'],
            r'country.*citizenship': ['countryofcitizenship', 'citizenshipcountry'],
            r'street.*name|street.*address': ['addressstreet', 'streetaddress'],
            r'city.*town': ['addresscity', 'city'],
            r'state': ['addressstate', 'state'],
            r'zip.*code|postal': ['addresszip', 'zipcode', 'postalcode'],
            r'passport.*number': ['passportnumber'],
            r'email': ['emailaddress', 'email'],
            r'daytime.*phone': ['daytimetelephonenumber', 'daytimephone'],
            r'mobile.*phone|cell': ['mobiletelephonenumber', 'mobilephone', 'cellphone'],
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
    
    # Breakdown by type
    checkboxes_quest = sum(1 for f in fields if f.to_questionnaire and f.field_type in ['checkbox', 'radio'])
    text_quest = sum(1 for f in fields if f.to_questionnaire and f.field_type == 'text')
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Fields", len(fields))
    with col2:
        st.metric("Database Mapped", mapped, f"{mapped/len(fields)*100:.0f}%")
    with col3:
        st.metric("Questionnaire", questionnaire, f"📋 {checkboxes_quest} ☑️ {text_quest}")
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
        
        # Show stats
        st.info(f"📊 {json_data['checkboxCount']} checkboxes/radio, {json_data['textFieldCount']} text fields")
        
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
                    "Part Title": st.session_state.part_info.get(field.part_number, ""),
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
Parts: {len(st.session_state.fields_by_part)}
Mapped to Database: {mapped}
In Questionnaire: {questionnaire + unmapped}
- Checkboxes/Radio: {checkboxes_quest}
- Text Fields: {text_quest + unmapped}
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
  - **Checkboxes/Radio (Auto)**: {sum(1 for f in fields if f.field_type in ['checkbox', 'radio'])}
  - **Text Fields**: {sum(1 for f in fields if f.to_questionnaire and f.field_type == 'text')}
- **Unique Parts**: {len(st.session_state.fields_by_part)}

## Parts Overview
"""
    
    for part_num, part_title in sorted(st.session_state.part_info.items()):
        part_fields = [f for f in fields if f.part_number == part_num]
        report += f"- **Part {part_num}**: {part_title} ({len(part_fields)} fields)\n"
    
    report += "\n## Field Mappings by Part\n\n"
    
    for part, part_fields in st.session_state.fields_by_part.items():
        part_num = int(part.split()[1])
        part_title = st.session_state.part_info.get(part_num, "")
        report += f"### {part} - {part_title}\n\n"
        report += "| Field ID | Item | Label | Type | Status | Mapping |\n"
        report += "|----------|------|-------|------|--------|----------|\n"
        
        for field in sorted(part_fields, key=lambda f: extractor._parse_item_number_for_sort(f.item_number)):
            status = "Mapped" if field.is_mapped else ("Questionnaire" if field.to_questionnaire else "Unmapped")
            mapping = field.db_mapping or "-"
            label = field.field_label[:40] + "..." if len(field.field_label) > 40 else field.field_label
            report += f"| {field.field_id} | {field.item_number} | {label} | {field.field_type} | {status} | {mapping} |\n"
        
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
            
            # Type breakdown
            checkboxes = sum(1 for f in fields if f.field_type in ['checkbox', 'radio'])
            text_fields = sum(1 for f in fields if f.field_type == 'text')
            st.caption(f"☑️ {checkboxes} checkboxes (auto-quest)")
            st.caption(f"📝 {text_fields} text fields")
            
            if unmapped > 0:
                st.warning(f"⚠️ {unmapped} unmapped")
            
            st.markdown("---")
            
            # Part breakdown with progress
            st.markdown("### 📑 Parts Progress")
            for part, part_fields in st.session_state.fields_by_part.items():
                complete = sum(1 for f in part_fields if f.is_mapped or f.to_questionnaire)
                part_progress = complete / len(part_fields) if part_fields else 0
                
                part_num = int(part.split()[1])
                part_title = st.session_state.part_info.get(part_num, "")
                
                st.markdown(f"**{part}**")
                if part_title:
                    st.caption(part_title)
                st.progress(part_progress)
                st.caption(f"{complete}/{len(part_fields)} fields")
        else:
            st.info("Upload a PDF to begin")
        
        st.markdown("---")
        st.markdown("### ✨ Key Features")
        st.markdown("""
        - ✅ **Extracts ALL parts** properly
        - ☑️ **Auto-moves checkboxes** to questionnaire
        - 🤖 **Smart field matching** with AI
        - 📊 **Comprehensive export** options
        """)
        
        st.markdown("---")
        st.markdown("### 🚀 Quick Tips")
        st.markdown("""
        1. All checkboxes → auto questionnaire
        2. Use **Auto-map** for common fields
        3. Review unmapped before export
        4. Check extraction log for details
        """)

if __name__ == "__main__":
    main(), '', item_label)
                    item_label = re.sub(r'[:\.]
    
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
        
        # First, try specific field patterns based on common USCIS form fields
        specific_mappings = {
            # Name fields
            ('familyname', 'lastname', 'surname'): {'number': '1a', 'label': 'Family Name (Last Name)'},
            ('givenname', 'firstname'): {'number': '1b', 'label': 'Given Name (First Name)'},
            ('middlename', 'middle'): {'number': '1c', 'label': 'Middle Name'},
            # Common ID fields
            ('alien', 'anumber', 'a-number', 'alienregistration'): {'number': '2', 'label': 'Alien Registration Number (A-Number)'},
            ('uscis', 'online', 'account'): {'number': '3', 'label': 'USCIS Online Account Number'},
            # Personal info
            ('dateofbirth', 'birthdate', 'dob'): {'number': '4', 'label': 'Date of Birth'},
            ('countryofbirth', 'birthcountry', 'cob'): {'number': '5', 'label': 'Country of Birth'},
            ('countryofcitizenship', 'citizenship', 'nationality'): {'number': '6', 'label': 'Country of Citizenship or Nationality'},
            ('gender', 'sex'): {'number': '7', 'label': 'Gender'},
            ('maritalstatus', 'marital'): {'number': '8', 'label': 'Marital Status'},
            ('ssn', 'socialsecurity', 'social'): {'number': '9', 'label': 'U.S. Social Security Number'},
            # Address fields
            ('streetnumber', 'street', 'address1', 'streetaddress'): {'number': '10a', 'label': 'Street Number and Name'},
            ('apt', 'apartment', 'suite', 'unit'): {'number': '10b', 'label': 'Apt./Ste./Flr. Number'},
            ('city', 'town', 'citytown'): {'number': '10c', 'label': 'City or Town'},
            ('state', 'province'): {'number': '10d', 'label': 'State'},
            ('zipcode', 'zip', 'postalcode'): {'number': '10e', 'label': 'ZIP Code'},
            ('country',): {'number': '10f', 'label': 'Country'},
            # Contact info
            ('daytimephone', 'dayphone', 'phoneday'): {'number': '11', 'label': 'Daytime Telephone Number'},
            ('mobilephone', 'cellphone', 'mobile'): {'number': '12', 'label': 'Mobile Telephone Number'},
            ('email', 'emailaddress'): {'number': '13', 'label': 'Email Address'},
        }
        
        # Check specific mappings
        for keywords, mapping in specific_mappings.items():
            if any(kw in widget_name_lower.replace('_', '').replace('-', '') for kw in keywords):
                return mapping
        
        # Try to find closest item by Y position
        if items:
            closest_item = None
            min_distance = float('inf')
            
            for item in items:
                # Calculate distance
                distance = abs(item.get('y_position', 0) - y_pos)
                if distance < min_distance and distance < 100:  # Within reasonable distance
                    min_distance = distance
                    closest_item = item
            
            if closest_item:
                return {
                    'number': closest_item['number'],
                    'label': closest_item['label']
                }
        
        # Default fallback - generate item number based on widget name
        # Try to extract number from widget name
        number_match = re.search(r'(\d+[a-z]?)', widget_name_lower)
        if number_match:
            return {
                'number': number_match.group(1),
                'label': self._extract_field_label(widget, page_text)
            }
        
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
        
        # Remove common prefixes and clean up
        prefixes_to_remove = [
            'form1[0].', '#subform[0].', '#subform[', 'Page1[0].', 'Page2[0].', 'Page3[0].',
            'Page4[0].', 'Page5[0].', 'Page6[0].', 'Page7[0].', 'Page8[0].',
            'Pg1_', 'Pg2_', 'Pg3_', 'Pg4_', 'Pg5_',
            'P1_', 'P2_', 'P3_', 'P4_', 'P5_',
            'Pt1_', 'Pt2_', 'Pt3_', 'Pt4_', 'Pt5_',
            'Part1', 'Part2', 'Part3', 'Part4', 'Part5',
            'TextField[', 'TextField1[', 'TextField2[',
            'CheckBox[', 'CheckBox1[', 'CheckBox2[',
            'RadioButton[', 'Radio[',
            'DateField[', 'Date['
        ]
        
        cleaned_name = field_name
        for prefix in prefixes_to_remove:
            if cleaned_name.startswith(prefix):
                cleaned_name = cleaned_name[len(prefix):]
                break
        
        # Remove array indices and closing brackets
        cleaned_name = re.sub(r'\[\d+\]', '', cleaned_name)
        cleaned_name = cleaned_name.rstrip(']').rstrip('[')
        cleaned_name = cleaned_name.strip('_')
        
        # Extract meaningful part
        parts = cleaned_name.split('.')
        if parts:
            label = parts[-1]
            
            # Convert various naming conventions to readable format
            # Handle camelCase
            label = re.sub(r'([a-z])([A-Z])', r'\1 \2', label)
            # Handle snake_case
            label = label.replace('_', ' ')
            # Handle abbreviations
            label = label.replace('DOB', 'Date of Birth')
            label = label.replace('SSN', 'Social Security Number')
            label = label.replace('Apt', 'Apartment')
            label = label.replace('Ste', 'Suite')
            label = label.replace('Flr', 'Floor')
            
            # Capitalize appropriately
            words = label.split()
            label = ' '.join(word.capitalize() for word in words)
            
            return label.strip()
        
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
            
        # Try to extract any number
        numbers = re.findall(r'\d+', str(item_num))
        if numbers:
            return (int(numbers[0]), str(item_num))
            
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
        
        # Add part information
        ts += "// Form Structure:\n"
        for part_num, part_title in sorted(st.session_state.part_info.items()):
            part_fields = [f for f in fields if f.part_number == part_num]
            ts += f"// Part {part_num}: {part_title} ({len(part_fields)} fields)\n"
        ts += "\n"
        
        ts += f"export const {form_name} = {{\n"
        
        # Add database mappings
        for obj, fields_list in sorted(db_fields.items()):
            ts += f"  {obj}Data: {{\n"
            for field in sorted(fields_list, key=lambda f: (f.part_number, self._parse_item_number_for_sort(f.item_number))):
                path = field.db_mapping.replace(f"{obj}.", "")
                field_suffix = ":TextBox" if field.field_type == "text" else f":{field.field_type.title()}Box"
                comment = f" // Part {field.part_number}, Item {field.item_number}: {field.field_label[:50]}"
                if len(field.field_label) > 50:
                    comment += "..."
                ts += f'    "{field.field_id}{field_suffix}": "{path}",{comment}\n'
            ts = ts.rstrip(',\n') + '\n'
            ts += "  },\n\n"
        
        # Add questionnaire fields grouped by part
        if questionnaire_fields:
            ts += "  questionnaireData: {\n"
            
            # Group by part for better organization
            questionnaire_by_part = defaultdict(list)
            for field in questionnaire_fields:
                questionnaire_by_part[field.part_number].append(field)
            
            for part_num in sorted(questionnaire_by_part.keys()):
                ts += f"    // Part {part_num} - {st.session_state.part_info.get(part_num, 'Unknown')}\n"
                for field in sorted(questionnaire_by_part[part_num], key=lambda f: self._parse_item_number_for_sort(f.item_number)):
                    ts += f'    "{field.field_id}": {{\n'
                    ts += f'      description: "{field.field_label}",\n'
                    ts += f'      fieldType: "{field.field_type}",\n'
                    ts += f'      part: {field.part_number},\n'
                    ts += f'      item: "{field.item_number}",\n'
                    ts += f'      page: {field.page},\n'
                    ts += f'      required: true\n'
                    ts += "    },\n"
                ts += "\n"
            
            ts = ts.rstrip(',\n') + '\n'
            ts += "  }\n"
        
        ts = ts.rstrip(',\n') + '\n'
        ts += "};\n"
        
        return ts
    
    def generate_json(self, fields: List[PDFField]) -> str:
        """Generate JSON for questionnaire fields"""
        questionnaire_fields = [f for f in fields if not f.is_mapped or f.field_type in ['checkbox', 'radio']]
        
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
            "checkboxCount": sum(1 for f in questionnaire_fields if f.field_type in ['checkbox', 'radio']),
            "textFieldCount": sum(1 for f in questionnaire_fields if f.field_type == 'text'),
            "sections": []
        }
        
        for part_num in sorted(by_part.keys()):
            section = {
                "part": part_num,
                "title": st.session_state.part_info.get(part_num, f"Part {part_num}"),
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
                    "widgetName": field.widget_name,  # Include for debugging
                    "required": True  # Default to required
                }
                
                # Add validation rules for specific field types
                if 'date' in field.field_label.lower():
                    field_data["validation"] = {"type": "date", "format": "MM/DD/YYYY"}
                elif 'email' in field.field_label.lower():
                    field_data["validation"] = {"type": "email"}
                elif 'phone' in field.field_label.lower() or 'telephone' in field.field_label.lower():
                    field_data["validation"] = {"type": "phone"}
                elif 'zip' in field.field_label.lower():
                    field_data["validation"] = {"type": "zip"}
                
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
            max-height: 400px;
            overflow-y: auto;
            font-family: monospace;
            font-size: 0.875rem;
        }
        .extraction-log-entry {
            margin: 0.25rem 0;
            padding: 0.25rem 0;
            border-bottom: 1px solid #f3f4f6;
        }
        .metric-card {
            background: white;
            border: 1px solid #e5e7eb;
            padding: 1.5rem;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        .metric-value {
            font-size: 2rem;
            font-weight: bold;
            color: #2563eb;
            margin: 0.5rem 0;
        }
        .metric-label {
            font-size: 0.875rem;
            color: #6b7280;
        }
        .checkbox-indicator {
            background: #fef3c7;
            border: 1px solid #fbbf24;
            padding: 0.5rem 1rem;
            border-radius: 8px;
            margin: 1rem 0;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        .checkbox-indicator svg {
            width: 20px;
            height: 20px;
            color: #f59e0b;
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="main-header">
        <h1>📄 Smart USCIS Form Field Extractor</h1>
        <p>Advanced extraction with automatic checkbox handling</p>
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
                with st.spinner("Analyzing PDF structure and extracting all fields..."):
                    if extractor.extract_fields_from_pdf(uploaded_file):
                        st.success(f"✅ Successfully extracted {len(st.session_state.extracted_fields)} fields from {len(st.session_state.fields_by_part)} parts!")
                        
                        # Show checkbox auto-move notification
                        checkboxes = sum(1 for f in st.session_state.extracted_fields if f.field_type in ['checkbox', 'radio'])
                        if checkboxes > 0:
                            st.markdown(f"""
                            <div class="checkbox-indicator">
                                ☑️ <strong>{checkboxes} checkboxes/radio buttons</strong> were automatically moved to questionnaire
                            </div>
                            """, unsafe_allow_html=True)
                        
                        st.rerun()
    
    # Display extracted fields
    if st.session_state.extracted_fields:
        st.markdown("---")
        st.markdown("## 📊 Extraction Results")
        
        # Summary metrics
        fields = st.session_state.extracted_fields
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        
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
            text_fields = sum(1 for f in fields if f.field_type == 'text')
            st.metric("Text Fields", text_fields)
        with col6:
            st.metric("Pages", st.session_state.form_info.get('total_pages', 0))
        
        # Show extraction log
        with st.expander("📝 View Extraction Log", expanded=False):
            st.markdown('<div class="extraction-log">', unsafe_allow_html=True)
            for log_entry in st.session_state.extraction_log:
                if log_entry.startswith("==="):
                    st.markdown(f'<div class="extraction-log-entry"><strong>{log_entry}</strong></div>', unsafe_allow_html=True)
                elif log_entry.startswith("Part"):
                    st.markdown(f'<div class="extraction-log-entry" style="color: #2563eb;"><strong>{log_entry}</strong></div>', unsafe_allow_html=True)
                elif "Auto-moved" in log_entry:
                    st.markdown(f'<div class="extraction-log-entry" style="color: #f59e0b;">{log_entry}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="extraction-log-entry">{log_entry}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        
        # Display by parts
        st.markdown("### 📑 Fields by Part")
        
        for part, part_fields in st.session_state.fields_by_part.items():
            # Count field types
            text_count = sum(1 for f in part_fields if f.field_type == 'text')
            checkbox_count = sum(1 for f in part_fields if f.field_type in ['checkbox', 'radio'])
            other_count = len(part_fields) - text_count - checkbox_count
            
            # Get part title
            part_num = int(part.split()[1])
            part_title = st.session_state.part_info.get(part_num, "")
            
            with st.expander(
                f"**{part}** - {part_title} ({len(part_fields)} fields: {text_count} text, {checkbox_count} checkbox/radio, {other_count} other)", 
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
    
    # Show checkbox notification
    checkboxes = sum(1 for f in fields if f.field_type in ['checkbox', 'radio'])
    if checkboxes > 0:
        st.info(f"ℹ️ All {checkboxes} checkbox/radio fields have been automatically moved to questionnaire")
    
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
        if st.button("🗺️ Auto-map Common Fields", use_container_width=True):
            count = auto_map_common_fields(extractor)
            if count > 0:
                st.success(f"Auto-mapped {count} fields")
                st.rerun()
    
    with col3:
        # Move all text fields to questionnaire
        if st.button("📝 All Text → Quest", use_container_width=True):
            count = 0
            for field in fields:
                if field.field_type == 'text' and not field.is_mapped and not field.to_questionnaire:
                    field.to_questionnaire = True
                    count += 1
            if count > 0:
                st.success(f"Moved {count} text fields to questionnaire")
                st.rerun()
    
    with col4:
        if st.button("🔄 Reset All Mappings", use_container_width=True):
            for field in fields:
                field.is_mapped = False
                # Keep checkboxes in questionnaire
                if field.field_type in ['checkbox', 'radio']:
                    field.to_questionnaire = True
                else:
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
    
    # Comprehensive field mappings for USCIS forms
    auto_mappings = {
        # Name fields
        r'family\s*name|last\s*name|surname': 'beneficiary.Beneficiary.beneficiaryLastName',
        r'given\s*name|first\s*name': 'beneficiary.Beneficiary.beneficiaryFirstName',
        r'middle\s*name': 'beneficiary.Beneficiary.beneficiaryMiddleName',
        
        # ID numbers
        r'alien\s*(?:registration\s*)?number|a[-\s]*number': 'beneficiary.Beneficiary.alienNumber',
        r'uscis\s*online\s*account': 'beneficiary.Beneficiary.uscisOnlineAccountNumber',
        r'social\s*security|ssn': 'beneficiary.Beneficiary.beneficiarySsn',
        
        # Personal info
        r'date\s*of\s*birth|birth\s*date|dob': 'beneficiary.Beneficiary.beneficiaryDateOfBirth',
        r'country\s*of\s*birth': 'beneficiary.Beneficiary.beneficiaryCountryOfBirth',
        r'country\s*of\s*citizenship|nationality': 'beneficiary.Beneficiary.beneficiaryCitizenOfCountry',
        r'gender|sex': 'beneficiary.Beneficiary.beneficiaryGender',
        r'marital\s*status': 'beneficiary.Beneficiary.maritalStatus',
        
        # Contact info
        r'daytime\s*(?:telephone|phone)|day\s*phone': 'beneficiary.ContactInfo.daytimeTelephoneNumber',
        r'mobile\s*(?:telephone|phone)|cell\s*phone': 'beneficiary.ContactInfo.mobileTelephoneNumber',
        r'email\s*address': 'beneficiary.ContactInfo.emailAddress',
        
        # Mailing Address fields
        r'(?:mailing\s*)?(?:street\s*(?:number\s*and\s*)?name|street\s*address)': 'beneficiary.MailingAddress.addressStreet',
        r'(?:mailing\s*)?(?:apt|apartment|suite|unit)': 'beneficiary.MailingAddress.addressAptSteFlrNumber',
        r'(?:mailing\s*)?(?:city|town)': 'beneficiary.MailingAddress.addressCity',
        r'(?:mailing\s*)?state': 'beneficiary.MailingAddress.addressState',
        r'(?:mailing\s*)?(?:zip\s*code|postal\s*code)': 'beneficiary.MailingAddress.addressZip',
        r'(?:mailing\s*)?country': 'beneficiary.MailingAddress.addressCountry',
        r'in\s*care\s*of|c/o': 'beneficiary.MailingAddress.inCareOfName',
        
        # Physical Address (if different from mailing)
        r'physical\s*(?:street|address)': 'beneficiary.PhysicalAddress.addressStreet',
        r'physical.*(?:city|town)': 'beneficiary.PhysicalAddress.addressCity',
        r'physical.*state': 'beneficiary.PhysicalAddress.addressState',
        r'physical.*(?:zip|postal)': 'beneficiary.PhysicalAddress.addressZip',
        
        # Document fields
        r'passport\s*number': 'beneficiary.PassportDetails.Passport.passportNumber',
        r'passport\s*(?:issue|issuance)\s*country': 'beneficiary.PassportDetails.Passport.passportIssueCountry',
        r'passport\s*(?:issue|issuance)\s*date': 'beneficiary.PassportDetails.Passport.passportIssueDate',
        r'passport\s*expir': 'beneficiary.PassportDetails.Passport.passportExpiryDate',
        r'travel\s*document\s*number': 'beneficiary.TravelDocument.travelDocumentNumber',
        r'travel.*country.*issuance': 'beneficiary.TravelDocument.countryOfIssuance',
        
        # Immigration status
        r'current\s*(?:nonimmigrant\s*)?status': 'beneficiary.VisaDetails.Visa.currentNonimmigrantStatus',
        r'date\s*(?:status\s*)?expires|expiration\s*date': 'beneficiary.VisaDetails.Visa.dateStatusExpires',
        r'visa\s*number': 'beneficiary.VisaDetails.Visa.visaNumber',
        r'i-94\s*number|form\s*i-94|arrival.*departure.*record': 'beneficiary.I94Details.I94.formI94ArrivalDepartureRecordNumber',
        r'date\s*of\s*(?:last\s*)?arrival': 'beneficiary.I94Details.I94.dateOfLastArrival',
        r'sevis\s*number': 'beneficiary.EducationDetails.studentEXTInfoSEVISNumber',
        
        # Biographic info
        r'eye\s*color': 'beneficiary.BiographicInfo.eyeColor',
        r'hair\s*color': 'beneficiary.BiographicInfo.hairColor',
        r'height.*feet': 'beneficiary.BiographicInfo.heightFeet',
        r'height.*inches': 'beneficiary.BiographicInfo.heightInches',
        r'weight.*pounds': 'beneficiary.BiographicInfo.weightPounds',
        r'race': 'beneficiary.BiographicInfo.race',
        r'ethnicity': 'beneficiary.BiographicInfo.ethnicity',
    }
    
    for field in fields:
        # Skip if already mapped, in questionnaire, or is a checkbox
        if field.is_mapped or field.to_questionnaire or field.field_type in ['checkbox', 'radio']:
            continue
            
        label_lower = field.field_label.lower().strip()
        
        # Try each mapping pattern
        for pattern, db_path in auto_mappings.items():
            if re.search(pattern, label_lower, re.IGNORECASE):
                field.db_mapping = db_path
                field.is_mapped = True
                count += 1
                st.session_state.extraction_log.append(f"Auto-mapped: {field.field_id} '{field.field_label}' → {db_path}")
                break
    
    return count

def render_one_by_one_mapping(extractor: SmartUSCISExtractor):
    """Render one-by-one field mapping with better UX"""
    fields = st.session_state.extracted_fields
    current_idx = st.session_state.current_field_index
    
    # Get unmapped text fields only (checkboxes already in questionnaire)
    unmapped_indices = [i for i, f in enumerate(fields) 
                       if not f.is_mapped and not f.to_questionnaire and f.field_type == 'text']
    
    if not unmapped_indices:
        st.success("✅ All text fields have been processed! Checkboxes are automatically in questionnaire.")
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
    
    st.markdown(f"### Processing Text Field {unmapped_indices.index(current_idx) + 1} of {len(unmapped_indices)}")
    
    # Current field
    field = fields[current_idx]
    
    # Field card with better styling
    st.markdown('<div class="field-card">', unsafe_allow_html=True)
    
    # Field information
    col1, col2 = st.columns([3, 1])
    with col1:
        part_title = st.session_state.part_info.get(field.part_number, f"Part {field.part_number}")
        st.markdown(f'<div class="field-id">{part_title}, Item {field.item_number}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="field-label">{field.field_label}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="field-meta">Field ID: {field.field_id} | Type: {field.field_type} | Page: {field.page}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="field-meta">Widget: {field.widget_name}</div>', unsafe_allow_html=True)
    
    with col2:
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
                    next_idx = unmapped_indices.index(current_idx) + 1
                    if next_idx < len(unmapped_indices):
                        st.session_state.current_field_index = unmapped_indices[next_idx]
                    else:
                        st.session_state.current_field_index = len(fields)
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
                next_idx = unmapped_indices.index(current_idx) + 1
                if next_idx < len(unmapped_indices):
                    st.session_state.current_field_index = unmapped_indices[next_idx]
                else:
                    st.session_state.current_field_index = len(fields)
                st.rerun()
    
    # Or send to questionnaire
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📋 Send to Questionnaire", use_container_width=True, type="secondary"):
            field.to_questionnaire = True
            field.is_mapped = False
            field.db_mapping = None
            # Move to next unmapped
            next_idx = unmapped_indices.index(current_idx) + 1
            if next_idx < len(unmapped_indices):
                st.session_state.current_field_index = unmapped_indices[next_idx]
            else:
                st.session_state.current_field_index = len(fields)
            st.rerun()
    
    with col2:
        if st.button("⏭️ Skip for Now", use_container_width=True):
            # Move to next unmapped
            next_idx = unmapped_indices.index(current_idx) + 1
            if next_idx < len(unmapped_indices):
                st.session_state.current_field_index = unmapped_indices[next_idx]
            else:
                st.session_state.current_field_index = 0
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
            unmapped_text = [f for f in display_fields if not f.is_mapped and not f.to_questionnaire and f.field_type == 'text']
            if unmapped_text:
                if st.button(f"📋 Send {len(unmapped_text)} Unmapped Text Fields to Questionnaire"):
                    for field in unmapped_text:
                        field.to_questionnaire = True
                    st.success(f"Sent {len(unmapped_text)} fields to questionnaire")
                    st.rerun()
    
    # Display fields with better layout
    for i, field in enumerate(display_fields):
        with st.container():
            col1, col2, col3, col4 = st.columns([3, 3.5, 1, 0.5])
            
            with col1:
                # Field info with better formatting
                part_title = st.session_state.part_info.get(field.part_number, f"Part {field.part_number}")
                st.markdown(f"**{field.field_id}** - {part_title}")
                st.markdown(f"Item {field.item_number} • {field.field_type} • Page {field.page}")
                st.caption(field.field_label[:80] + "..." if len(field.field_label) > 80 else field.field_label)
            
            with col2:
                if field.is_mapped:
                    st.success(f"✅ Mapped to: {field.db_mapping}")
                elif field.to_questionnaire:
                    st.warning("📋 In Questionnaire")
                else:
                    # Only show mapping for text fields
                    if field.field_type == 'text':
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
                    else:
                        st.info(f"Auto-assigned to questionnaire ({field.field_type})")
            
            with col3:
                # Quick action buttons
                if field.is_mapped or field.to_questionnaire:
                    if field.field_type == 'text':  # Only allow reset for text fields
                        if st.button("↩️ Reset", key=f"reset_{field.field_id}_{i}", help="Reset mapping"):
                            field.is_mapped = False
                            field.to_questionnaire = False
                            field.db_mapping = None
                            st.rerun()
                else:
                    if field.field_type == 'text':
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
    noise_words = ['the', 'of', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'if', 'any', 'your', 'please', 'provide']
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
            # Check if context matches
            context_matches = {
                'address': ['street', 'city', 'state', 'zip', 'apt'],
                'passport': ['passport', 'issue', 'expir'],
                'contact': ['phone', 'telephone', 'email', 'mobile'],
                'visa': ['visa', 'status', 'nonimmigrant'],
                'biographic': ['height', 'weight', 'eye', 'hair', 'race']
            }
            
            for context, keywords in context_matches.items():
                if context in parent:
                    if any(kw in label_lower for kw in keywords):
                        score += 30
        
        # Special patterns with higher scores
        special_patterns = {
            r'family\s*name|last\s*name': ['lastname', 'familyname', 'beneficiarylastname'],
            r'given\s*name|first\s*name': ['firstname', 'givenname', 'beneficiaryfirstname'],
            r'middle\s*name': ['middlename', 'beneficiarymiddlename'],
            r'a[-\s]*number|alien.*number': ['aliennumber', 'anumber'],
            r'date.*birth|birth.*date|dob': ['dateofbirth', 'birthdate', 'beneficiarydateofbirth'],
            r'country.*birth': ['countryofbirth', 'birthcountry'],
            r'country.*citizenship': ['countryofcitizenship', 'citizenshipcountry'],
            r'street.*name|street.*address': ['addressstreet', 'streetaddress'],
            r'city.*town': ['addresscity', 'city'],
            r'state': ['addressstate', 'state'],
            r'zip.*code|postal': ['addresszip', 'zipcode', 'postalcode'],
            r'passport.*number': ['passportnumber'],
            r'email': ['emailaddress', 'email'],
            r'daytime.*phone': ['daytimetelephonenumber', 'daytimephone'],
            r'mobile.*phone|cell': ['mobiletelephonenumber', 'mobilephone', 'cellphone'],
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
    
    # Breakdown by type
    checkboxes_quest = sum(1 for f in fields if f.to_questionnaire and f.field_type in ['checkbox', 'radio'])
    text_quest = sum(1 for f in fields if f.to_questionnaire and f.field_type == 'text')
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Fields", len(fields))
    with col2:
        st.metric("Database Mapped", mapped, f"{mapped/len(fields)*100:.0f}%")
    with col3:
        st.metric("Questionnaire", questionnaire, f"📋 {checkboxes_quest} ☑️ {text_quest}")
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
        
        # Show stats
        st.info(f"📊 {json_data['checkboxCount']} checkboxes/radio, {json_data['textFieldCount']} text fields")
        
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
                    "Part Title": st.session_state.part_info.get(field.part_number, ""),
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
Parts: {len(st.session_state.fields_by_part)}
Mapped to Database: {mapped}
In Questionnaire: {questionnaire + unmapped}
- Checkboxes/Radio: {checkboxes_quest}
- Text Fields: {text_quest + unmapped}
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
  - **Checkboxes/Radio (Auto)**: {sum(1 for f in fields if f.field_type in ['checkbox', 'radio'])}
  - **Text Fields**: {sum(1 for f in fields if f.to_questionnaire and f.field_type == 'text')}
- **Unique Parts**: {len(st.session_state.fields_by_part)}

## Parts Overview
"""
    
    for part_num, part_title in sorted(st.session_state.part_info.items()):
        part_fields = [f for f in fields if f.part_number == part_num]
        report += f"- **Part {part_num}**: {part_title} ({len(part_fields)} fields)\n"
    
    report += "\n## Field Mappings by Part\n\n"
    
    for part, part_fields in st.session_state.fields_by_part.items():
        part_num = int(part.split()[1])
        part_title = st.session_state.part_info.get(part_num, "")
        report += f"### {part} - {part_title}\n\n"
        report += "| Field ID | Item | Label | Type | Status | Mapping |\n"
        report += "|----------|------|-------|------|--------|----------|\n"
        
        for field in sorted(part_fields, key=lambda f: extractor._parse_item_number_for_sort(f.item_number)):
            status = "Mapped" if field.is_mapped else ("Questionnaire" if field.to_questionnaire else "Unmapped")
            mapping = field.db_mapping or "-"
            label = field.field_label[:40] + "..." if len(field.field_label) > 40 else field.field_label
            report += f"| {field.field_id} | {field.item_number} | {label} | {field.field_type} | {status} | {mapping} |\n"
        
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
            
            # Type breakdown
            checkboxes = sum(1 for f in fields if f.field_type in ['checkbox', 'radio'])
            text_fields = sum(1 for f in fields if f.field_type == 'text')
            st.caption(f"☑️ {checkboxes} checkboxes (auto-quest)")
            st.caption(f"📝 {text_fields} text fields")
            
            if unmapped > 0:
                st.warning(f"⚠️ {unmapped} unmapped")
            
            st.markdown("---")
            
            # Part breakdown with progress
            st.markdown("### 📑 Parts Progress")
            for part, part_fields in st.session_state.fields_by_part.items():
                complete = sum(1 for f in part_fields if f.is_mapped or f.to_questionnaire)
                part_progress = complete / len(part_fields) if part_fields else 0
                
                part_num = int(part.split()[1])
                part_title = st.session_state.part_info.get(part_num, "")
                
                st.markdown(f"**{part}**")
                if part_title:
                    st.caption(part_title)
                st.progress(part_progress)
                st.caption(f"{complete}/{len(part_fields)} fields")
        else:
            st.info("Upload a PDF to begin")
        
        st.markdown("---")
        st.markdown("### ✨ Key Features")
        st.markdown("""
        - ✅ **Extracts ALL parts** properly
        - ☑️ **Auto-moves checkboxes** to questionnaire
        - 🤖 **Smart field matching** with AI
        - 📊 **Comprehensive export** options
        """)
        
        st.markdown("---")
        st.markdown("### 🚀 Quick Tips")
        st.markdown("""
        1. All checkboxes → auto questionnaire
        2. Use **Auto-map** for common fields
        3. Review unmapped before export
        4. Check extraction log for details
        """)

if __name__ == "__main__":
    main(), '', item_label)
                    
                    # Skip if too short or already seen
                    if len(item_label) < 2 or (item_num, item_label) in seen_items:
                        continue
                    
                    # Skip page numbers or form numbers
                    if re.match(r'^(Page|Form|I-\d+|Edition)', item_label):
                        continue
                    
                    # Look ahead for additional context (like field descriptions)
                    full_label = item_label
                    if line_idx + 1 < len(lines):
                        next_line = lines[line_idx + 1].strip()
                        # If next line looks like a continuation (doesn't start with number or special char)
                        if next_line and not re.match(r'^[\d►□\[\]○\(\)]', next_line):
                            # Check if it's likely a field label continuation
                            if len(next_line) > 10 and not any(skip in next_line.lower() for skip in ['select', 'if you', 'provide']):
                                full_label = f"{item_label} {next_line}"
                    
                    seen_items.add((item_num, item_label))
                    
                    items.append({
                        'number': item_num,
                        'label': full_label[:200],  # Limit length
                        'position': line_idx * 20,  # Approximate position
                        'y_position': line_idx * 20,
                        'line': line_idx
                    })
                    break  # Only match first pattern per line
        
        # Post-process to handle sub-items better
        processed_items = []
        current_main_item = None
        
        for item in sorted(items, key=lambda x: x['line']):
            # Check if this is a sub-item (single letter)
            if len(item['number']) == 1 and item['number'].isalpha():
                if current_main_item:
                    # This is a sub-item of the current main item
                    item['number'] = f"{current_main_item}.{item['number']}"
            else:
                # This is a main item
                match = re.match(r'^(\d+)[a-z]?
    
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
        
        # First, try specific field patterns based on common USCIS form fields
        specific_mappings = {
            # Name fields
            ('familyname', 'lastname', 'surname'): {'number': '1a', 'label': 'Family Name (Last Name)'},
            ('givenname', 'firstname'): {'number': '1b', 'label': 'Given Name (First Name)'},
            ('middlename', 'middle'): {'number': '1c', 'label': 'Middle Name'},
            # Common ID fields
            ('alien', 'anumber', 'a-number', 'alienregistration'): {'number': '2', 'label': 'Alien Registration Number (A-Number)'},
            ('uscis', 'online', 'account'): {'number': '3', 'label': 'USCIS Online Account Number'},
            # Personal info
            ('dateofbirth', 'birthdate', 'dob'): {'number': '4', 'label': 'Date of Birth'},
            ('countryofbirth', 'birthcountry', 'cob'): {'number': '5', 'label': 'Country of Birth'},
            ('countryofcitizenship', 'citizenship', 'nationality'): {'number': '6', 'label': 'Country of Citizenship or Nationality'},
            ('gender', 'sex'): {'number': '7', 'label': 'Gender'},
            ('maritalstatus', 'marital'): {'number': '8', 'label': 'Marital Status'},
            ('ssn', 'socialsecurity', 'social'): {'number': '9', 'label': 'U.S. Social Security Number'},
            # Address fields
            ('streetnumber', 'street', 'address1', 'streetaddress'): {'number': '10a', 'label': 'Street Number and Name'},
            ('apt', 'apartment', 'suite', 'unit'): {'number': '10b', 'label': 'Apt./Ste./Flr. Number'},
            ('city', 'town', 'citytown'): {'number': '10c', 'label': 'City or Town'},
            ('state', 'province'): {'number': '10d', 'label': 'State'},
            ('zipcode', 'zip', 'postalcode'): {'number': '10e', 'label': 'ZIP Code'},
            ('country',): {'number': '10f', 'label': 'Country'},
            # Contact info
            ('daytimephone', 'dayphone', 'phoneday'): {'number': '11', 'label': 'Daytime Telephone Number'},
            ('mobilephone', 'cellphone', 'mobile'): {'number': '12', 'label': 'Mobile Telephone Number'},
            ('email', 'emailaddress'): {'number': '13', 'label': 'Email Address'},
        }
        
        # Check specific mappings
        for keywords, mapping in specific_mappings.items():
            if any(kw in widget_name_lower.replace('_', '').replace('-', '') for kw in keywords):
                return mapping
        
        # Try to find closest item by Y position
        if items:
            closest_item = None
            min_distance = float('inf')
            
            for item in items:
                # Calculate distance
                distance = abs(item.get('y_position', 0) - y_pos)
                if distance < min_distance and distance < 100:  # Within reasonable distance
                    min_distance = distance
                    closest_item = item
            
            if closest_item:
                return {
                    'number': closest_item['number'],
                    'label': closest_item['label']
                }
        
        # Default fallback - generate item number based on widget name
        # Try to extract number from widget name
        number_match = re.search(r'(\d+[a-z]?)', widget_name_lower)
        if number_match:
            return {
                'number': number_match.group(1),
                'label': self._extract_field_label(widget, page_text)
            }
        
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
        
        # Remove common prefixes and clean up
        prefixes_to_remove = [
            'form1[0].', '#subform[0].', '#subform[', 'Page1[0].', 'Page2[0].', 'Page3[0].',
            'Page4[0].', 'Page5[0].', 'Page6[0].', 'Page7[0].', 'Page8[0].',
            'Pg1_', 'Pg2_', 'Pg3_', 'Pg4_', 'Pg5_',
            'P1_', 'P2_', 'P3_', 'P4_', 'P5_',
            'Pt1_', 'Pt2_', 'Pt3_', 'Pt4_', 'Pt5_',
            'Part1', 'Part2', 'Part3', 'Part4', 'Part5',
            'TextField[', 'TextField1[', 'TextField2[',
            'CheckBox[', 'CheckBox1[', 'CheckBox2[',
            'RadioButton[', 'Radio[',
            'DateField[', 'Date['
        ]
        
        cleaned_name = field_name
        for prefix in prefixes_to_remove:
            if cleaned_name.startswith(prefix):
                cleaned_name = cleaned_name[len(prefix):]
                break
        
        # Remove array indices and closing brackets
        cleaned_name = re.sub(r'\[\d+\]', '', cleaned_name)
        cleaned_name = cleaned_name.rstrip(']').rstrip('[')
        cleaned_name = cleaned_name.strip('_')
        
        # Extract meaningful part
        parts = cleaned_name.split('.')
        if parts:
            label = parts[-1]
            
            # Convert various naming conventions to readable format
            # Handle camelCase
            label = re.sub(r'([a-z])([A-Z])', r'\1 \2', label)
            # Handle snake_case
            label = label.replace('_', ' ')
            # Handle abbreviations
            label = label.replace('DOB', 'Date of Birth')
            label = label.replace('SSN', 'Social Security Number')
            label = label.replace('Apt', 'Apartment')
            label = label.replace('Ste', 'Suite')
            label = label.replace('Flr', 'Floor')
            
            # Capitalize appropriately
            words = label.split()
            label = ' '.join(word.capitalize() for word in words)
            
            return label.strip()
        
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
            
        # Try to extract any number
        numbers = re.findall(r'\d+', str(item_num))
        if numbers:
            return (int(numbers[0]), str(item_num))
            
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
        
        # Add part information
        ts += "// Form Structure:\n"
        for part_num, part_title in sorted(st.session_state.part_info.items()):
            part_fields = [f for f in fields if f.part_number == part_num]
            ts += f"// Part {part_num}: {part_title} ({len(part_fields)} fields)\n"
        ts += "\n"
        
        ts += f"export const {form_name} = {{\n"
        
        # Add database mappings
        for obj, fields_list in sorted(db_fields.items()):
            ts += f"  {obj}Data: {{\n"
            for field in sorted(fields_list, key=lambda f: (f.part_number, self._parse_item_number_for_sort(f.item_number))):
                path = field.db_mapping.replace(f"{obj}.", "")
                field_suffix = ":TextBox" if field.field_type == "text" else f":{field.field_type.title()}Box"
                comment = f" // Part {field.part_number}, Item {field.item_number}: {field.field_label[:50]}"
                if len(field.field_label) > 50:
                    comment += "..."
                ts += f'    "{field.field_id}{field_suffix}": "{path}",{comment}\n'
            ts = ts.rstrip(',\n') + '\n'
            ts += "  },\n\n"
        
        # Add questionnaire fields grouped by part
        if questionnaire_fields:
            ts += "  questionnaireData: {\n"
            
            # Group by part for better organization
            questionnaire_by_part = defaultdict(list)
            for field in questionnaire_fields:
                questionnaire_by_part[field.part_number].append(field)
            
            for part_num in sorted(questionnaire_by_part.keys()):
                ts += f"    // Part {part_num} - {st.session_state.part_info.get(part_num, 'Unknown')}\n"
                for field in sorted(questionnaire_by_part[part_num], key=lambda f: self._parse_item_number_for_sort(f.item_number)):
                    ts += f'    "{field.field_id}": {{\n'
                    ts += f'      description: "{field.field_label}",\n'
                    ts += f'      fieldType: "{field.field_type}",\n'
                    ts += f'      part: {field.part_number},\n'
                    ts += f'      item: "{field.item_number}",\n'
                    ts += f'      page: {field.page},\n'
                    ts += f'      required: true\n'
                    ts += "    },\n"
                ts += "\n"
            
            ts = ts.rstrip(',\n') + '\n'
            ts += "  }\n"
        
        ts = ts.rstrip(',\n') + '\n'
        ts += "};\n"
        
        return ts
    
    def generate_json(self, fields: List[PDFField]) -> str:
        """Generate JSON for questionnaire fields"""
        questionnaire_fields = [f for f in fields if not f.is_mapped or f.field_type in ['checkbox', 'radio']]
        
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
            "checkboxCount": sum(1 for f in questionnaire_fields if f.field_type in ['checkbox', 'radio']),
            "textFieldCount": sum(1 for f in questionnaire_fields if f.field_type == 'text'),
            "sections": []
        }
        
        for part_num in sorted(by_part.keys()):
            section = {
                "part": part_num,
                "title": st.session_state.part_info.get(part_num, f"Part {part_num}"),
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
                    "widgetName": field.widget_name,  # Include for debugging
                    "required": True  # Default to required
                }
                
                # Add validation rules for specific field types
                if 'date' in field.field_label.lower():
                    field_data["validation"] = {"type": "date", "format": "MM/DD/YYYY"}
                elif 'email' in field.field_label.lower():
                    field_data["validation"] = {"type": "email"}
                elif 'phone' in field.field_label.lower() or 'telephone' in field.field_label.lower():
                    field_data["validation"] = {"type": "phone"}
                elif 'zip' in field.field_label.lower():
                    field_data["validation"] = {"type": "zip"}
                
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
            max-height: 400px;
            overflow-y: auto;
            font-family: monospace;
            font-size: 0.875rem;
        }
        .extraction-log-entry {
            margin: 0.25rem 0;
            padding: 0.25rem 0;
            border-bottom: 1px solid #f3f4f6;
        }
        .metric-card {
            background: white;
            border: 1px solid #e5e7eb;
            padding: 1.5rem;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        .metric-value {
            font-size: 2rem;
            font-weight: bold;
            color: #2563eb;
            margin: 0.5rem 0;
        }
        .metric-label {
            font-size: 0.875rem;
            color: #6b7280;
        }
        .checkbox-indicator {
            background: #fef3c7;
            border: 1px solid #fbbf24;
            padding: 0.5rem 1rem;
            border-radius: 8px;
            margin: 1rem 0;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        .checkbox-indicator svg {
            width: 20px;
            height: 20px;
            color: #f59e0b;
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="main-header">
        <h1>📄 Smart USCIS Form Field Extractor</h1>
        <p>Advanced extraction with automatic checkbox handling</p>
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
                with st.spinner("Analyzing PDF structure and extracting all fields..."):
                    if extractor.extract_fields_from_pdf(uploaded_file):
                        st.success(f"✅ Successfully extracted {len(st.session_state.extracted_fields)} fields from {len(st.session_state.fields_by_part)} parts!")
                        
                        # Show checkbox auto-move notification
                        checkboxes = sum(1 for f in st.session_state.extracted_fields if f.field_type in ['checkbox', 'radio'])
                        if checkboxes > 0:
                            st.markdown(f"""
                            <div class="checkbox-indicator">
                                ☑️ <strong>{checkboxes} checkboxes/radio buttons</strong> were automatically moved to questionnaire
                            </div>
                            """, unsafe_allow_html=True)
                        
                        st.rerun()
    
    # Display extracted fields
    if st.session_state.extracted_fields:
        st.markdown("---")
        st.markdown("## 📊 Extraction Results")
        
        # Summary metrics
        fields = st.session_state.extracted_fields
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        
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
            text_fields = sum(1 for f in fields if f.field_type == 'text')
            st.metric("Text Fields", text_fields)
        with col6:
            st.metric("Pages", st.session_state.form_info.get('total_pages', 0))
        
        # Show extraction log
        with st.expander("📝 View Extraction Log", expanded=False):
            st.markdown('<div class="extraction-log">', unsafe_allow_html=True)
            for log_entry in st.session_state.extraction_log:
                if log_entry.startswith("==="):
                    st.markdown(f'<div class="extraction-log-entry"><strong>{log_entry}</strong></div>', unsafe_allow_html=True)
                elif log_entry.startswith("Part"):
                    st.markdown(f'<div class="extraction-log-entry" style="color: #2563eb;"><strong>{log_entry}</strong></div>', unsafe_allow_html=True)
                elif "Auto-moved" in log_entry:
                    st.markdown(f'<div class="extraction-log-entry" style="color: #f59e0b;">{log_entry}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="extraction-log-entry">{log_entry}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        
        # Display by parts
        st.markdown("### 📑 Fields by Part")
        
        for part, part_fields in st.session_state.fields_by_part.items():
            # Count field types
            text_count = sum(1 for f in part_fields if f.field_type == 'text')
            checkbox_count = sum(1 for f in part_fields if f.field_type in ['checkbox', 'radio'])
            other_count = len(part_fields) - text_count - checkbox_count
            
            # Get part title
            part_num = int(part.split()[1])
            part_title = st.session_state.part_info.get(part_num, "")
            
            with st.expander(
                f"**{part}** - {part_title} ({len(part_fields)} fields: {text_count} text, {checkbox_count} checkbox/radio, {other_count} other)", 
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
    
    # Show checkbox notification
    checkboxes = sum(1 for f in fields if f.field_type in ['checkbox', 'radio'])
    if checkboxes > 0:
        st.info(f"ℹ️ All {checkboxes} checkbox/radio fields have been automatically moved to questionnaire")
    
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
        if st.button("🗺️ Auto-map Common Fields", use_container_width=True):
            count = auto_map_common_fields(extractor)
            if count > 0:
                st.success(f"Auto-mapped {count} fields")
                st.rerun()
    
    with col3:
        # Move all text fields to questionnaire
        if st.button("📝 All Text → Quest", use_container_width=True):
            count = 0
            for field in fields:
                if field.field_type == 'text' and not field.is_mapped and not field.to_questionnaire:
                    field.to_questionnaire = True
                    count += 1
            if count > 0:
                st.success(f"Moved {count} text fields to questionnaire")
                st.rerun()
    
    with col4:
        if st.button("🔄 Reset All Mappings", use_container_width=True):
            for field in fields:
                field.is_mapped = False
                # Keep checkboxes in questionnaire
                if field.field_type in ['checkbox', 'radio']:
                    field.to_questionnaire = True
                else:
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
    
    # Comprehensive field mappings for USCIS forms
    auto_mappings = {
        # Name fields
        r'family\s*name|last\s*name|surname': 'beneficiary.Beneficiary.beneficiaryLastName',
        r'given\s*name|first\s*name': 'beneficiary.Beneficiary.beneficiaryFirstName',
        r'middle\s*name': 'beneficiary.Beneficiary.beneficiaryMiddleName',
        
        # ID numbers
        r'alien\s*(?:registration\s*)?number|a[-\s]*number': 'beneficiary.Beneficiary.alienNumber',
        r'uscis\s*online\s*account': 'beneficiary.Beneficiary.uscisOnlineAccountNumber',
        r'social\s*security|ssn': 'beneficiary.Beneficiary.beneficiarySsn',
        
        # Personal info
        r'date\s*of\s*birth|birth\s*date|dob': 'beneficiary.Beneficiary.beneficiaryDateOfBirth',
        r'country\s*of\s*birth': 'beneficiary.Beneficiary.beneficiaryCountryOfBirth',
        r'country\s*of\s*citizenship|nationality': 'beneficiary.Beneficiary.beneficiaryCitizenOfCountry',
        r'gender|sex': 'beneficiary.Beneficiary.beneficiaryGender',
        r'marital\s*status': 'beneficiary.Beneficiary.maritalStatus',
        
        # Contact info
        r'daytime\s*(?:telephone|phone)|day\s*phone': 'beneficiary.ContactInfo.daytimeTelephoneNumber',
        r'mobile\s*(?:telephone|phone)|cell\s*phone': 'beneficiary.ContactInfo.mobileTelephoneNumber',
        r'email\s*address': 'beneficiary.ContactInfo.emailAddress',
        
        # Mailing Address fields
        r'(?:mailing\s*)?(?:street\s*(?:number\s*and\s*)?name|street\s*address)': 'beneficiary.MailingAddress.addressStreet',
        r'(?:mailing\s*)?(?:apt|apartment|suite|unit)': 'beneficiary.MailingAddress.addressAptSteFlrNumber',
        r'(?:mailing\s*)?(?:city|town)': 'beneficiary.MailingAddress.addressCity',
        r'(?:mailing\s*)?state': 'beneficiary.MailingAddress.addressState',
        r'(?:mailing\s*)?(?:zip\s*code|postal\s*code)': 'beneficiary.MailingAddress.addressZip',
        r'(?:mailing\s*)?country': 'beneficiary.MailingAddress.addressCountry',
        r'in\s*care\s*of|c/o': 'beneficiary.MailingAddress.inCareOfName',
        
        # Physical Address (if different from mailing)
        r'physical\s*(?:street|address)': 'beneficiary.PhysicalAddress.addressStreet',
        r'physical.*(?:city|town)': 'beneficiary.PhysicalAddress.addressCity',
        r'physical.*state': 'beneficiary.PhysicalAddress.addressState',
        r'physical.*(?:zip|postal)': 'beneficiary.PhysicalAddress.addressZip',
        
        # Document fields
        r'passport\s*number': 'beneficiary.PassportDetails.Passport.passportNumber',
        r'passport\s*(?:issue|issuance)\s*country': 'beneficiary.PassportDetails.Passport.passportIssueCountry',
        r'passport\s*(?:issue|issuance)\s*date': 'beneficiary.PassportDetails.Passport.passportIssueDate',
        r'passport\s*expir': 'beneficiary.PassportDetails.Passport.passportExpiryDate',
        r'travel\s*document\s*number': 'beneficiary.TravelDocument.travelDocumentNumber',
        r'travel.*country.*issuance': 'beneficiary.TravelDocument.countryOfIssuance',
        
        # Immigration status
        r'current\s*(?:nonimmigrant\s*)?status': 'beneficiary.VisaDetails.Visa.currentNonimmigrantStatus',
        r'date\s*(?:status\s*)?expires|expiration\s*date': 'beneficiary.VisaDetails.Visa.dateStatusExpires',
        r'visa\s*number': 'beneficiary.VisaDetails.Visa.visaNumber',
        r'i-94\s*number|form\s*i-94|arrival.*departure.*record': 'beneficiary.I94Details.I94.formI94ArrivalDepartureRecordNumber',
        r'date\s*of\s*(?:last\s*)?arrival': 'beneficiary.I94Details.I94.dateOfLastArrival',
        r'sevis\s*number': 'beneficiary.EducationDetails.studentEXTInfoSEVISNumber',
        
        # Biographic info
        r'eye\s*color': 'beneficiary.BiographicInfo.eyeColor',
        r'hair\s*color': 'beneficiary.BiographicInfo.hairColor',
        r'height.*feet': 'beneficiary.BiographicInfo.heightFeet',
        r'height.*inches': 'beneficiary.BiographicInfo.heightInches',
        r'weight.*pounds': 'beneficiary.BiographicInfo.weightPounds',
        r'race': 'beneficiary.BiographicInfo.race',
        r'ethnicity': 'beneficiary.BiographicInfo.ethnicity',
    }
    
    for field in fields:
        # Skip if already mapped, in questionnaire, or is a checkbox
        if field.is_mapped or field.to_questionnaire or field.field_type in ['checkbox', 'radio']:
            continue
            
        label_lower = field.field_label.lower().strip()
        
        # Try each mapping pattern
        for pattern, db_path in auto_mappings.items():
            if re.search(pattern, label_lower, re.IGNORECASE):
                field.db_mapping = db_path
                field.is_mapped = True
                count += 1
                st.session_state.extraction_log.append(f"Auto-mapped: {field.field_id} '{field.field_label}' → {db_path}")
                break
    
    return count

def render_one_by_one_mapping(extractor: SmartUSCISExtractor):
    """Render one-by-one field mapping with better UX"""
    fields = st.session_state.extracted_fields
    current_idx = st.session_state.current_field_index
    
    # Get unmapped text fields only (checkboxes already in questionnaire)
    unmapped_indices = [i for i, f in enumerate(fields) 
                       if not f.is_mapped and not f.to_questionnaire and f.field_type == 'text']
    
    if not unmapped_indices:
        st.success("✅ All text fields have been processed! Checkboxes are automatically in questionnaire.")
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
    
    st.markdown(f"### Processing Text Field {unmapped_indices.index(current_idx) + 1} of {len(unmapped_indices)}")
    
    # Current field
    field = fields[current_idx]
    
    # Field card with better styling
    st.markdown('<div class="field-card">', unsafe_allow_html=True)
    
    # Field information
    col1, col2 = st.columns([3, 1])
    with col1:
        part_title = st.session_state.part_info.get(field.part_number, f"Part {field.part_number}")
        st.markdown(f'<div class="field-id">{part_title}, Item {field.item_number}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="field-label">{field.field_label}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="field-meta">Field ID: {field.field_id} | Type: {field.field_type} | Page: {field.page}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="field-meta">Widget: {field.widget_name}</div>', unsafe_allow_html=True)
    
    with col2:
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
                    next_idx = unmapped_indices.index(current_idx) + 1
                    if next_idx < len(unmapped_indices):
                        st.session_state.current_field_index = unmapped_indices[next_idx]
                    else:
                        st.session_state.current_field_index = len(fields)
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
                next_idx = unmapped_indices.index(current_idx) + 1
                if next_idx < len(unmapped_indices):
                    st.session_state.current_field_index = unmapped_indices[next_idx]
                else:
                    st.session_state.current_field_index = len(fields)
                st.rerun()
    
    # Or send to questionnaire
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📋 Send to Questionnaire", use_container_width=True, type="secondary"):
            field.to_questionnaire = True
            field.is_mapped = False
            field.db_mapping = None
            # Move to next unmapped
            next_idx = unmapped_indices.index(current_idx) + 1
            if next_idx < len(unmapped_indices):
                st.session_state.current_field_index = unmapped_indices[next_idx]
            else:
                st.session_state.current_field_index = len(fields)
            st.rerun()
    
    with col2:
        if st.button("⏭️ Skip for Now", use_container_width=True):
            # Move to next unmapped
            next_idx = unmapped_indices.index(current_idx) + 1
            if next_idx < len(unmapped_indices):
                st.session_state.current_field_index = unmapped_indices[next_idx]
            else:
                st.session_state.current_field_index = 0
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
            unmapped_text = [f for f in display_fields if not f.is_mapped and not f.to_questionnaire and f.field_type == 'text']
            if unmapped_text:
                if st.button(f"📋 Send {len(unmapped_text)} Unmapped Text Fields to Questionnaire"):
                    for field in unmapped_text:
                        field.to_questionnaire = True
                    st.success(f"Sent {len(unmapped_text)} fields to questionnaire")
                    st.rerun()
    
    # Display fields with better layout
    for i, field in enumerate(display_fields):
        with st.container():
            col1, col2, col3, col4 = st.columns([3, 3.5, 1, 0.5])
            
            with col1:
                # Field info with better formatting
                part_title = st.session_state.part_info.get(field.part_number, f"Part {field.part_number}")
                st.markdown(f"**{field.field_id}** - {part_title}")
                st.markdown(f"Item {field.item_number} • {field.field_type} • Page {field.page}")
                st.caption(field.field_label[:80] + "..." if len(field.field_label) > 80 else field.field_label)
            
            with col2:
                if field.is_mapped:
                    st.success(f"✅ Mapped to: {field.db_mapping}")
                elif field.to_questionnaire:
                    st.warning("📋 In Questionnaire")
                else:
                    # Only show mapping for text fields
                    if field.field_type == 'text':
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
                    else:
                        st.info(f"Auto-assigned to questionnaire ({field.field_type})")
            
            with col3:
                # Quick action buttons
                if field.is_mapped or field.to_questionnaire:
                    if field.field_type == 'text':  # Only allow reset for text fields
                        if st.button("↩️ Reset", key=f"reset_{field.field_id}_{i}", help="Reset mapping"):
                            field.is_mapped = False
                            field.to_questionnaire = False
                            field.db_mapping = None
                            st.rerun()
                else:
                    if field.field_type == 'text':
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
    noise_words = ['the', 'of', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'if', 'any', 'your', 'please', 'provide']
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
            # Check if context matches
            context_matches = {
                'address': ['street', 'city', 'state', 'zip', 'apt'],
                'passport': ['passport', 'issue', 'expir'],
                'contact': ['phone', 'telephone', 'email', 'mobile'],
                'visa': ['visa', 'status', 'nonimmigrant'],
                'biographic': ['height', 'weight', 'eye', 'hair', 'race']
            }
            
            for context, keywords in context_matches.items():
                if context in parent:
                    if any(kw in label_lower for kw in keywords):
                        score += 30
        
        # Special patterns with higher scores
        special_patterns = {
            r'family\s*name|last\s*name': ['lastname', 'familyname', 'beneficiarylastname'],
            r'given\s*name|first\s*name': ['firstname', 'givenname', 'beneficiaryfirstname'],
            r'middle\s*name': ['middlename', 'beneficiarymiddlename'],
            r'a[-\s]*number|alien.*number': ['aliennumber', 'anumber'],
            r'date.*birth|birth.*date|dob': ['dateofbirth', 'birthdate', 'beneficiarydateofbirth'],
            r'country.*birth': ['countryofbirth', 'birthcountry'],
            r'country.*citizenship': ['countryofcitizenship', 'citizenshipcountry'],
            r'street.*name|street.*address': ['addressstreet', 'streetaddress'],
            r'city.*town': ['addresscity', 'city'],
            r'state': ['addressstate', 'state'],
            r'zip.*code|postal': ['addresszip', 'zipcode', 'postalcode'],
            r'passport.*number': ['passportnumber'],
            r'email': ['emailaddress', 'email'],
            r'daytime.*phone': ['daytimetelephonenumber', 'daytimephone'],
            r'mobile.*phone|cell': ['mobiletelephonenumber', 'mobilephone', 'cellphone'],
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
    
    # Breakdown by type
    checkboxes_quest = sum(1 for f in fields if f.to_questionnaire and f.field_type in ['checkbox', 'radio'])
    text_quest = sum(1 for f in fields if f.to_questionnaire and f.field_type == 'text')
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Fields", len(fields))
    with col2:
        st.metric("Database Mapped", mapped, f"{mapped/len(fields)*100:.0f}%")
    with col3:
        st.metric("Questionnaire", questionnaire, f"📋 {checkboxes_quest} ☑️ {text_quest}")
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
        
        # Show stats
        st.info(f"📊 {json_data['checkboxCount']} checkboxes/radio, {json_data['textFieldCount']} text fields")
        
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
                    "Part Title": st.session_state.part_info.get(field.part_number, ""),
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
Parts: {len(st.session_state.fields_by_part)}
Mapped to Database: {mapped}
In Questionnaire: {questionnaire + unmapped}
- Checkboxes/Radio: {checkboxes_quest}
- Text Fields: {text_quest + unmapped}
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
  - **Checkboxes/Radio (Auto)**: {sum(1 for f in fields if f.field_type in ['checkbox', 'radio'])}
  - **Text Fields**: {sum(1 for f in fields if f.to_questionnaire and f.field_type == 'text')}
- **Unique Parts**: {len(st.session_state.fields_by_part)}

## Parts Overview
"""
    
    for part_num, part_title in sorted(st.session_state.part_info.items()):
        part_fields = [f for f in fields if f.part_number == part_num]
        report += f"- **Part {part_num}**: {part_title} ({len(part_fields)} fields)\n"
    
    report += "\n## Field Mappings by Part\n\n"
    
    for part, part_fields in st.session_state.fields_by_part.items():
        part_num = int(part.split()[1])
        part_title = st.session_state.part_info.get(part_num, "")
        report += f"### {part} - {part_title}\n\n"
        report += "| Field ID | Item | Label | Type | Status | Mapping |\n"
        report += "|----------|------|-------|------|--------|----------|\n"
        
        for field in sorted(part_fields, key=lambda f: extractor._parse_item_number_for_sort(f.item_number)):
            status = "Mapped" if field.is_mapped else ("Questionnaire" if field.to_questionnaire else "Unmapped")
            mapping = field.db_mapping or "-"
            label = field.field_label[:40] + "..." if len(field.field_label) > 40 else field.field_label
            report += f"| {field.field_id} | {field.item_number} | {label} | {field.field_type} | {status} | {mapping} |\n"
        
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
            
            # Type breakdown
            checkboxes = sum(1 for f in fields if f.field_type in ['checkbox', 'radio'])
            text_fields = sum(1 for f in fields if f.field_type == 'text')
            st.caption(f"☑️ {checkboxes} checkboxes (auto-quest)")
            st.caption(f"📝 {text_fields} text fields")
            
            if unmapped > 0:
                st.warning(f"⚠️ {unmapped} unmapped")
            
            st.markdown("---")
            
            # Part breakdown with progress
            st.markdown("### 📑 Parts Progress")
            for part, part_fields in st.session_state.fields_by_part.items():
                complete = sum(1 for f in part_fields if f.is_mapped or f.to_questionnaire)
                part_progress = complete / len(part_fields) if part_fields else 0
                
                part_num = int(part.split()[1])
                part_title = st.session_state.part_info.get(part_num, "")
                
                st.markdown(f"**{part}**")
                if part_title:
                    st.caption(part_title)
                st.progress(part_progress)
                st.caption(f"{complete}/{len(part_fields)} fields")
        else:
            st.info("Upload a PDF to begin")
        
        st.markdown("---")
        st.markdown("### ✨ Key Features")
        st.markdown("""
        - ✅ **Extracts ALL parts** properly
        - ☑️ **Auto-moves checkboxes** to questionnaire
        - 🤖 **Smart field matching** with AI
        - 📊 **Comprehensive export** options
        """)
        
        st.markdown("---")
        st.markdown("### 🚀 Quick Tips")
        st.markdown("""
        1. All checkboxes → auto questionnaire
        2. Use **Auto-map** for common fields
        3. Review unmapped before export
        4. Check extraction log for details
        """)

if __name__ == "__main__":
    main(), item['number'])
                if match:
                    current_main_item = match.group(1)
            
            processed_items.append(item)
        
        # Sort by position
        processed_items.sort(key=lambda x: x['position'])
        
        return processed_items
    
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
        
        # First, try specific field patterns based on common USCIS form fields
        specific_mappings = {
            # Name fields
            ('familyname', 'lastname', 'surname'): {'number': '1a', 'label': 'Family Name (Last Name)'},
            ('givenname', 'firstname'): {'number': '1b', 'label': 'Given Name (First Name)'},
            ('middlename', 'middle'): {'number': '1c', 'label': 'Middle Name'},
            # Common ID fields
            ('alien', 'anumber', 'a-number', 'alienregistration'): {'number': '2', 'label': 'Alien Registration Number (A-Number)'},
            ('uscis', 'online', 'account'): {'number': '3', 'label': 'USCIS Online Account Number'},
            # Personal info
            ('dateofbirth', 'birthdate', 'dob'): {'number': '4', 'label': 'Date of Birth'},
            ('countryofbirth', 'birthcountry', 'cob'): {'number': '5', 'label': 'Country of Birth'},
            ('countryofcitizenship', 'citizenship', 'nationality'): {'number': '6', 'label': 'Country of Citizenship or Nationality'},
            ('gender', 'sex'): {'number': '7', 'label': 'Gender'},
            ('maritalstatus', 'marital'): {'number': '8', 'label': 'Marital Status'},
            ('ssn', 'socialsecurity', 'social'): {'number': '9', 'label': 'U.S. Social Security Number'},
            # Address fields
            ('streetnumber', 'street', 'address1', 'streetaddress'): {'number': '10a', 'label': 'Street Number and Name'},
            ('apt', 'apartment', 'suite', 'unit'): {'number': '10b', 'label': 'Apt./Ste./Flr. Number'},
            ('city', 'town', 'citytown'): {'number': '10c', 'label': 'City or Town'},
            ('state', 'province'): {'number': '10d', 'label': 'State'},
            ('zipcode', 'zip', 'postalcode'): {'number': '10e', 'label': 'ZIP Code'},
            ('country',): {'number': '10f', 'label': 'Country'},
            # Contact info
            ('daytimephone', 'dayphone', 'phoneday'): {'number': '11', 'label': 'Daytime Telephone Number'},
            ('mobilephone', 'cellphone', 'mobile'): {'number': '12', 'label': 'Mobile Telephone Number'},
            ('email', 'emailaddress'): {'number': '13', 'label': 'Email Address'},
        }
        
        # Check specific mappings
        for keywords, mapping in specific_mappings.items():
            if any(kw in widget_name_lower.replace('_', '').replace('-', '') for kw in keywords):
                return mapping
        
        # Try to find closest item by Y position
        if items:
            closest_item = None
            min_distance = float('inf')
            
            for item in items:
                # Calculate distance
                distance = abs(item.get('y_position', 0) - y_pos)
                if distance < min_distance and distance < 100:  # Within reasonable distance
                    min_distance = distance
                    closest_item = item
            
            if closest_item:
                return {
                    'number': closest_item['number'],
                    'label': closest_item['label']
                }
        
        # Default fallback - generate item number based on widget name
        # Try to extract number from widget name
        number_match = re.search(r'(\d+[a-z]?)', widget_name_lower)
        if number_match:
            return {
                'number': number_match.group(1),
                'label': self._extract_field_label(widget, page_text)
            }
        
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
        
        # Remove common prefixes and clean up
        prefixes_to_remove = [
            'form1[0].', '#subform[0].', '#subform[', 'Page1[0].', 'Page2[0].', 'Page3[0].',
            'Page4[0].', 'Page5[0].', 'Page6[0].', 'Page7[0].', 'Page8[0].',
            'Pg1_', 'Pg2_', 'Pg3_', 'Pg4_', 'Pg5_',
            'P1_', 'P2_', 'P3_', 'P4_', 'P5_',
            'Pt1_', 'Pt2_', 'Pt3_', 'Pt4_', 'Pt5_',
            'Part1', 'Part2', 'Part3', 'Part4', 'Part5',
            'TextField[', 'TextField1[', 'TextField2[',
            'CheckBox[', 'CheckBox1[', 'CheckBox2[',
            'RadioButton[', 'Radio[',
            'DateField[', 'Date['
        ]
        
        cleaned_name = field_name
        for prefix in prefixes_to_remove:
            if cleaned_name.startswith(prefix):
                cleaned_name = cleaned_name[len(prefix):]
                break
        
        # Remove array indices and closing brackets
        cleaned_name = re.sub(r'\[\d+\]', '', cleaned_name)
        cleaned_name = cleaned_name.rstrip(']').rstrip('[')
        cleaned_name = cleaned_name.strip('_')
        
        # Extract meaningful part
        parts = cleaned_name.split('.')
        if parts:
            label = parts[-1]
            
            # Convert various naming conventions to readable format
            # Handle camelCase
            label = re.sub(r'([a-z])([A-Z])', r'\1 \2', label)
            # Handle snake_case
            label = label.replace('_', ' ')
            # Handle abbreviations
            label = label.replace('DOB', 'Date of Birth')
            label = label.replace('SSN', 'Social Security Number')
            label = label.replace('Apt', 'Apartment')
            label = label.replace('Ste', 'Suite')
            label = label.replace('Flr', 'Floor')
            
            # Capitalize appropriately
            words = label.split()
            label = ' '.join(word.capitalize() for word in words)
            
            return label.strip()
        
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
            
        # Try to extract any number
        numbers = re.findall(r'\d+', str(item_num))
        if numbers:
            return (int(numbers[0]), str(item_num))
            
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
        
        # Add part information
        ts += "// Form Structure:\n"
        for part_num, part_title in sorted(st.session_state.part_info.items()):
            part_fields = [f for f in fields if f.part_number == part_num]
            ts += f"// Part {part_num}: {part_title} ({len(part_fields)} fields)\n"
        ts += "\n"
        
        ts += f"export const {form_name} = {{\n"
        
        # Add database mappings
        for obj, fields_list in sorted(db_fields.items()):
            ts += f"  {obj}Data: {{\n"
            for field in sorted(fields_list, key=lambda f: (f.part_number, self._parse_item_number_for_sort(f.item_number))):
                path = field.db_mapping.replace(f"{obj}.", "")
                field_suffix = ":TextBox" if field.field_type == "text" else f":{field.field_type.title()}Box"
                comment = f" // Part {field.part_number}, Item {field.item_number}: {field.field_label[:50]}"
                if len(field.field_label) > 50:
                    comment += "..."
                ts += f'    "{field.field_id}{field_suffix}": "{path}",{comment}\n'
            ts = ts.rstrip(',\n') + '\n'
            ts += "  },\n\n"
        
        # Add questionnaire fields grouped by part
        if questionnaire_fields:
            ts += "  questionnaireData: {\n"
            
            # Group by part for better organization
            questionnaire_by_part = defaultdict(list)
            for field in questionnaire_fields:
                questionnaire_by_part[field.part_number].append(field)
            
            for part_num in sorted(questionnaire_by_part.keys()):
                ts += f"    // Part {part_num} - {st.session_state.part_info.get(part_num, 'Unknown')}\n"
                for field in sorted(questionnaire_by_part[part_num], key=lambda f: self._parse_item_number_for_sort(f.item_number)):
                    ts += f'    "{field.field_id}": {{\n'
                    ts += f'      description: "{field.field_label}",\n'
                    ts += f'      fieldType: "{field.field_type}",\n'
                    ts += f'      part: {field.part_number},\n'
                    ts += f'      item: "{field.item_number}",\n'
                    ts += f'      page: {field.page},\n'
                    ts += f'      required: true\n'
                    ts += "    },\n"
                ts += "\n"
            
            ts = ts.rstrip(',\n') + '\n'
            ts += "  }\n"
        
        ts = ts.rstrip(',\n') + '\n'
        ts += "};\n"
        
        return ts
    
    def generate_json(self, fields: List[PDFField]) -> str:
        """Generate JSON for questionnaire fields"""
        questionnaire_fields = [f for f in fields if not f.is_mapped or f.field_type in ['checkbox', 'radio']]
        
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
            "checkboxCount": sum(1 for f in questionnaire_fields if f.field_type in ['checkbox', 'radio']),
            "textFieldCount": sum(1 for f in questionnaire_fields if f.field_type == 'text'),
            "sections": []
        }
        
        for part_num in sorted(by_part.keys()):
            section = {
                "part": part_num,
                "title": st.session_state.part_info.get(part_num, f"Part {part_num}"),
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
                    "widgetName": field.widget_name,  # Include for debugging
                    "required": True  # Default to required
                }
                
                # Add validation rules for specific field types
                if 'date' in field.field_label.lower():
                    field_data["validation"] = {"type": "date", "format": "MM/DD/YYYY"}
                elif 'email' in field.field_label.lower():
                    field_data["validation"] = {"type": "email"}
                elif 'phone' in field.field_label.lower() or 'telephone' in field.field_label.lower():
                    field_data["validation"] = {"type": "phone"}
                elif 'zip' in field.field_label.lower():
                    field_data["validation"] = {"type": "zip"}
                
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
            max-height: 400px;
            overflow-y: auto;
            font-family: monospace;
            font-size: 0.875rem;
        }
        .extraction-log-entry {
            margin: 0.25rem 0;
            padding: 0.25rem 0;
            border-bottom: 1px solid #f3f4f6;
        }
        .metric-card {
            background: white;
            border: 1px solid #e5e7eb;
            padding: 1.5rem;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        .metric-value {
            font-size: 2rem;
            font-weight: bold;
            color: #2563eb;
            margin: 0.5rem 0;
        }
        .metric-label {
            font-size: 0.875rem;
            color: #6b7280;
        }
        .checkbox-indicator {
            background: #fef3c7;
            border: 1px solid #fbbf24;
            padding: 0.5rem 1rem;
            border-radius: 8px;
            margin: 1rem 0;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        .checkbox-indicator svg {
            width: 20px;
            height: 20px;
            color: #f59e0b;
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="main-header">
        <h1>📄 Smart USCIS Form Field Extractor</h1>
        <p>Advanced extraction with automatic checkbox handling</p>
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
                with st.spinner("Analyzing PDF structure and extracting all fields..."):
                    if extractor.extract_fields_from_pdf(uploaded_file):
                        st.success(f"✅ Successfully extracted {len(st.session_state.extracted_fields)} fields from {len(st.session_state.fields_by_part)} parts!")
                        
                        # Show checkbox auto-move notification
                        checkboxes = sum(1 for f in st.session_state.extracted_fields if f.field_type in ['checkbox', 'radio'])
                        if checkboxes > 0:
                            st.markdown(f"""
                            <div class="checkbox-indicator">
                                ☑️ <strong>{checkboxes} checkboxes/radio buttons</strong> were automatically moved to questionnaire
                            </div>
                            """, unsafe_allow_html=True)
                        
                        st.rerun()
    
    # Display extracted fields
    if st.session_state.extracted_fields:
        st.markdown("---")
        st.markdown("## 📊 Extraction Results")
        
        # Summary metrics
        fields = st.session_state.extracted_fields
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        
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
            text_fields = sum(1 for f in fields if f.field_type == 'text')
            st.metric("Text Fields", text_fields)
        with col6:
            st.metric("Pages", st.session_state.form_info.get('total_pages', 0))
        
        # Show extraction log
        with st.expander("📝 View Extraction Log", expanded=False):
            st.markdown('<div class="extraction-log">', unsafe_allow_html=True)
            for log_entry in st.session_state.extraction_log:
                if log_entry.startswith("==="):
                    st.markdown(f'<div class="extraction-log-entry"><strong>{log_entry}</strong></div>', unsafe_allow_html=True)
                elif log_entry.startswith("Part"):
                    st.markdown(f'<div class="extraction-log-entry" style="color: #2563eb;"><strong>{log_entry}</strong></div>', unsafe_allow_html=True)
                elif "Auto-moved" in log_entry:
                    st.markdown(f'<div class="extraction-log-entry" style="color: #f59e0b;">{log_entry}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="extraction-log-entry">{log_entry}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        
        # Display by parts
        st.markdown("### 📑 Fields by Part")
        
        for part, part_fields in st.session_state.fields_by_part.items():
            # Count field types
            text_count = sum(1 for f in part_fields if f.field_type == 'text')
            checkbox_count = sum(1 for f in part_fields if f.field_type in ['checkbox', 'radio'])
            other_count = len(part_fields) - text_count - checkbox_count
            
            # Get part title
            part_num = int(part.split()[1])
            part_title = st.session_state.part_info.get(part_num, "")
            
            with st.expander(
                f"**{part}** - {part_title} ({len(part_fields)} fields: {text_count} text, {checkbox_count} checkbox/radio, {other_count} other)", 
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
    
    # Show checkbox notification
    checkboxes = sum(1 for f in fields if f.field_type in ['checkbox', 'radio'])
    if checkboxes > 0:
        st.info(f"ℹ️ All {checkboxes} checkbox/radio fields have been automatically moved to questionnaire")
    
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
        if st.button("🗺️ Auto-map Common Fields", use_container_width=True):
            count = auto_map_common_fields(extractor)
            if count > 0:
                st.success(f"Auto-mapped {count} fields")
                st.rerun()
    
    with col3:
        # Move all text fields to questionnaire
        if st.button("📝 All Text → Quest", use_container_width=True):
            count = 0
            for field in fields:
                if field.field_type == 'text' and not field.is_mapped and not field.to_questionnaire:
                    field.to_questionnaire = True
                    count += 1
            if count > 0:
                st.success(f"Moved {count} text fields to questionnaire")
                st.rerun()
    
    with col4:
        if st.button("🔄 Reset All Mappings", use_container_width=True):
            for field in fields:
                field.is_mapped = False
                # Keep checkboxes in questionnaire
                if field.field_type in ['checkbox', 'radio']:
                    field.to_questionnaire = True
                else:
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
    
    # Comprehensive field mappings for USCIS forms
    auto_mappings = {
        # Name fields
        r'family\s*name|last\s*name|surname': 'beneficiary.Beneficiary.beneficiaryLastName',
        r'given\s*name|first\s*name': 'beneficiary.Beneficiary.beneficiaryFirstName',
        r'middle\s*name': 'beneficiary.Beneficiary.beneficiaryMiddleName',
        
        # ID numbers
        r'alien\s*(?:registration\s*)?number|a[-\s]*number': 'beneficiary.Beneficiary.alienNumber',
        r'uscis\s*online\s*account': 'beneficiary.Beneficiary.uscisOnlineAccountNumber',
        r'social\s*security|ssn': 'beneficiary.Beneficiary.beneficiarySsn',
        
        # Personal info
        r'date\s*of\s*birth|birth\s*date|dob': 'beneficiary.Beneficiary.beneficiaryDateOfBirth',
        r'country\s*of\s*birth': 'beneficiary.Beneficiary.beneficiaryCountryOfBirth',
        r'country\s*of\s*citizenship|nationality': 'beneficiary.Beneficiary.beneficiaryCitizenOfCountry',
        r'gender|sex': 'beneficiary.Beneficiary.beneficiaryGender',
        r'marital\s*status': 'beneficiary.Beneficiary.maritalStatus',
        
        # Contact info
        r'daytime\s*(?:telephone|phone)|day\s*phone': 'beneficiary.ContactInfo.daytimeTelephoneNumber',
        r'mobile\s*(?:telephone|phone)|cell\s*phone': 'beneficiary.ContactInfo.mobileTelephoneNumber',
        r'email\s*address': 'beneficiary.ContactInfo.emailAddress',
        
        # Mailing Address fields
        r'(?:mailing\s*)?(?:street\s*(?:number\s*and\s*)?name|street\s*address)': 'beneficiary.MailingAddress.addressStreet',
        r'(?:mailing\s*)?(?:apt|apartment|suite|unit)': 'beneficiary.MailingAddress.addressAptSteFlrNumber',
        r'(?:mailing\s*)?(?:city|town)': 'beneficiary.MailingAddress.addressCity',
        r'(?:mailing\s*)?state': 'beneficiary.MailingAddress.addressState',
        r'(?:mailing\s*)?(?:zip\s*code|postal\s*code)': 'beneficiary.MailingAddress.addressZip',
        r'(?:mailing\s*)?country': 'beneficiary.MailingAddress.addressCountry',
        r'in\s*care\s*of|c/o': 'beneficiary.MailingAddress.inCareOfName',
        
        # Physical Address (if different from mailing)
        r'physical\s*(?:street|address)': 'beneficiary.PhysicalAddress.addressStreet',
        r'physical.*(?:city|town)': 'beneficiary.PhysicalAddress.addressCity',
        r'physical.*state': 'beneficiary.PhysicalAddress.addressState',
        r'physical.*(?:zip|postal)': 'beneficiary.PhysicalAddress.addressZip',
        
        # Document fields
        r'passport\s*number': 'beneficiary.PassportDetails.Passport.passportNumber',
        r'passport\s*(?:issue|issuance)\s*country': 'beneficiary.PassportDetails.Passport.passportIssueCountry',
        r'passport\s*(?:issue|issuance)\s*date': 'beneficiary.PassportDetails.Passport.passportIssueDate',
        r'passport\s*expir': 'beneficiary.PassportDetails.Passport.passportExpiryDate',
        r'travel\s*document\s*number': 'beneficiary.TravelDocument.travelDocumentNumber',
        r'travel.*country.*issuance': 'beneficiary.TravelDocument.countryOfIssuance',
        
        # Immigration status
        r'current\s*(?:nonimmigrant\s*)?status': 'beneficiary.VisaDetails.Visa.currentNonimmigrantStatus',
        r'date\s*(?:status\s*)?expires|expiration\s*date': 'beneficiary.VisaDetails.Visa.dateStatusExpires',
        r'visa\s*number': 'beneficiary.VisaDetails.Visa.visaNumber',
        r'i-94\s*number|form\s*i-94|arrival.*departure.*record': 'beneficiary.I94Details.I94.formI94ArrivalDepartureRecordNumber',
        r'date\s*of\s*(?:last\s*)?arrival': 'beneficiary.I94Details.I94.dateOfLastArrival',
        r'sevis\s*number': 'beneficiary.EducationDetails.studentEXTInfoSEVISNumber',
        
        # Biographic info
        r'eye\s*color': 'beneficiary.BiographicInfo.eyeColor',
        r'hair\s*color': 'beneficiary.BiographicInfo.hairColor',
        r'height.*feet': 'beneficiary.BiographicInfo.heightFeet',
        r'height.*inches': 'beneficiary.BiographicInfo.heightInches',
        r'weight.*pounds': 'beneficiary.BiographicInfo.weightPounds',
        r'race': 'beneficiary.BiographicInfo.race',
        r'ethnicity': 'beneficiary.BiographicInfo.ethnicity',
    }
    
    for field in fields:
        # Skip if already mapped, in questionnaire, or is a checkbox
        if field.is_mapped or field.to_questionnaire or field.field_type in ['checkbox', 'radio']:
            continue
            
        label_lower = field.field_label.lower().strip()
        
        # Try each mapping pattern
        for pattern, db_path in auto_mappings.items():
            if re.search(pattern, label_lower, re.IGNORECASE):
                field.db_mapping = db_path
                field.is_mapped = True
                count += 1
                st.session_state.extraction_log.append(f"Auto-mapped: {field.field_id} '{field.field_label}' → {db_path}")
                break
    
    return count

def render_one_by_one_mapping(extractor: SmartUSCISExtractor):
    """Render one-by-one field mapping with better UX"""
    fields = st.session_state.extracted_fields
    current_idx = st.session_state.current_field_index
    
    # Get unmapped text fields only (checkboxes already in questionnaire)
    unmapped_indices = [i for i, f in enumerate(fields) 
                       if not f.is_mapped and not f.to_questionnaire and f.field_type == 'text']
    
    if not unmapped_indices:
        st.success("✅ All text fields have been processed! Checkboxes are automatically in questionnaire.")
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
    
    st.markdown(f"### Processing Text Field {unmapped_indices.index(current_idx) + 1} of {len(unmapped_indices)}")
    
    # Current field
    field = fields[current_idx]
    
    # Field card with better styling
    st.markdown('<div class="field-card">', unsafe_allow_html=True)
    
    # Field information
    col1, col2 = st.columns([3, 1])
    with col1:
        part_title = st.session_state.part_info.get(field.part_number, f"Part {field.part_number}")
        st.markdown(f'<div class="field-id">{part_title}, Item {field.item_number}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="field-label">{field.field_label}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="field-meta">Field ID: {field.field_id} | Type: {field.field_type} | Page: {field.page}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="field-meta">Widget: {field.widget_name}</div>', unsafe_allow_html=True)
    
    with col2:
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
                    next_idx = unmapped_indices.index(current_idx) + 1
                    if next_idx < len(unmapped_indices):
                        st.session_state.current_field_index = unmapped_indices[next_idx]
                    else:
                        st.session_state.current_field_index = len(fields)
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
                next_idx = unmapped_indices.index(current_idx) + 1
                if next_idx < len(unmapped_indices):
                    st.session_state.current_field_index = unmapped_indices[next_idx]
                else:
                    st.session_state.current_field_index = len(fields)
                st.rerun()
    
    # Or send to questionnaire
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📋 Send to Questionnaire", use_container_width=True, type="secondary"):
            field.to_questionnaire = True
            field.is_mapped = False
            field.db_mapping = None
            # Move to next unmapped
            next_idx = unmapped_indices.index(current_idx) + 1
            if next_idx < len(unmapped_indices):
                st.session_state.current_field_index = unmapped_indices[next_idx]
            else:
                st.session_state.current_field_index = len(fields)
            st.rerun()
    
    with col2:
        if st.button("⏭️ Skip for Now", use_container_width=True):
            # Move to next unmapped
            next_idx = unmapped_indices.index(current_idx) + 1
            if next_idx < len(unmapped_indices):
                st.session_state.current_field_index = unmapped_indices[next_idx]
            else:
                st.session_state.current_field_index = 0
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
            unmapped_text = [f for f in display_fields if not f.is_mapped and not f.to_questionnaire and f.field_type == 'text']
            if unmapped_text:
                if st.button(f"📋 Send {len(unmapped_text)} Unmapped Text Fields to Questionnaire"):
                    for field in unmapped_text:
                        field.to_questionnaire = True
                    st.success(f"Sent {len(unmapped_text)} fields to questionnaire")
                    st.rerun()
    
    # Display fields with better layout
    for i, field in enumerate(display_fields):
        with st.container():
            col1, col2, col3, col4 = st.columns([3, 3.5, 1, 0.5])
            
            with col1:
                # Field info with better formatting
                part_title = st.session_state.part_info.get(field.part_number, f"Part {field.part_number}")
                st.markdown(f"**{field.field_id}** - {part_title}")
                st.markdown(f"Item {field.item_number} • {field.field_type} • Page {field.page}")
                st.caption(field.field_label[:80] + "..." if len(field.field_label) > 80 else field.field_label)
            
            with col2:
                if field.is_mapped:
                    st.success(f"✅ Mapped to: {field.db_mapping}")
                elif field.to_questionnaire:
                    st.warning("📋 In Questionnaire")
                else:
                    # Only show mapping for text fields
                    if field.field_type == 'text':
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
                    else:
                        st.info(f"Auto-assigned to questionnaire ({field.field_type})")
            
            with col3:
                # Quick action buttons
                if field.is_mapped or field.to_questionnaire:
                    if field.field_type == 'text':  # Only allow reset for text fields
                        if st.button("↩️ Reset", key=f"reset_{field.field_id}_{i}", help="Reset mapping"):
                            field.is_mapped = False
                            field.to_questionnaire = False
                            field.db_mapping = None
                            st.rerun()
                else:
                    if field.field_type == 'text':
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
    noise_words = ['the', 'of', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'if', 'any', 'your', 'please', 'provide']
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
            # Check if context matches
            context_matches = {
                'address': ['street', 'city', 'state', 'zip', 'apt'],
                'passport': ['passport', 'issue', 'expir'],
                'contact': ['phone', 'telephone', 'email', 'mobile'],
                'visa': ['visa', 'status', 'nonimmigrant'],
                'biographic': ['height', 'weight', 'eye', 'hair', 'race']
            }
            
            for context, keywords in context_matches.items():
                if context in parent:
                    if any(kw in label_lower for kw in keywords):
                        score += 30
        
        # Special patterns with higher scores
        special_patterns = {
            r'family\s*name|last\s*name': ['lastname', 'familyname', 'beneficiarylastname'],
            r'given\s*name|first\s*name': ['firstname', 'givenname', 'beneficiaryfirstname'],
            r'middle\s*name': ['middlename', 'beneficiarymiddlename'],
            r'a[-\s]*number|alien.*number': ['aliennumber', 'anumber'],
            r'date.*birth|birth.*date|dob': ['dateofbirth', 'birthdate', 'beneficiarydateofbirth'],
            r'country.*birth': ['countryofbirth', 'birthcountry'],
            r'country.*citizenship': ['countryofcitizenship', 'citizenshipcountry'],
            r'street.*name|street.*address': ['addressstreet', 'streetaddress'],
            r'city.*town': ['addresscity', 'city'],
            r'state': ['addressstate', 'state'],
            r'zip.*code|postal': ['addresszip', 'zipcode', 'postalcode'],
            r'passport.*number': ['passportnumber'],
            r'email': ['emailaddress', 'email'],
            r'daytime.*phone': ['daytimetelephonenumber', 'daytimephone'],
            r'mobile.*phone|cell': ['mobiletelephonenumber', 'mobilephone', 'cellphone'],
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
    
    # Breakdown by type
    checkboxes_quest = sum(1 for f in fields if f.to_questionnaire and f.field_type in ['checkbox', 'radio'])
    text_quest = sum(1 for f in fields if f.to_questionnaire and f.field_type == 'text')
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Fields", len(fields))
    with col2:
        st.metric("Database Mapped", mapped, f"{mapped/len(fields)*100:.0f}%")
    with col3:
        st.metric("Questionnaire", questionnaire, f"📋 {checkboxes_quest} ☑️ {text_quest}")
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
        
        # Show stats
        st.info(f"📊 {json_data['checkboxCount']} checkboxes/radio, {json_data['textFieldCount']} text fields")
        
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
                    "Part Title": st.session_state.part_info.get(field.part_number, ""),
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
Parts: {len(st.session_state.fields_by_part)}
Mapped to Database: {mapped}
In Questionnaire: {questionnaire + unmapped}
- Checkboxes/Radio: {checkboxes_quest}
- Text Fields: {text_quest + unmapped}
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
  - **Checkboxes/Radio (Auto)**: {sum(1 for f in fields if f.field_type in ['checkbox', 'radio'])}
  - **Text Fields**: {sum(1 for f in fields if f.to_questionnaire and f.field_type == 'text')}
- **Unique Parts**: {len(st.session_state.fields_by_part)}

## Parts Overview
"""
    
    for part_num, part_title in sorted(st.session_state.part_info.items()):
        part_fields = [f for f in fields if f.part_number == part_num]
        report += f"- **Part {part_num}**: {part_title} ({len(part_fields)} fields)\n"
    
    report += "\n## Field Mappings by Part\n\n"
    
    for part, part_fields in st.session_state.fields_by_part.items():
        part_num = int(part.split()[1])
        part_title = st.session_state.part_info.get(part_num, "")
        report += f"### {part} - {part_title}\n\n"
        report += "| Field ID | Item | Label | Type | Status | Mapping |\n"
        report += "|----------|------|-------|------|--------|----------|\n"
        
        for field in sorted(part_fields, key=lambda f: extractor._parse_item_number_for_sort(f.item_number)):
            status = "Mapped" if field.is_mapped else ("Questionnaire" if field.to_questionnaire else "Unmapped")
            mapping = field.db_mapping or "-"
            label = field.field_label[:40] + "..." if len(field.field_label) > 40 else field.field_label
            report += f"| {field.field_id} | {field.item_number} | {label} | {field.field_type} | {status} | {mapping} |\n"
        
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
            
            # Type breakdown
            checkboxes = sum(1 for f in fields if f.field_type in ['checkbox', 'radio'])
            text_fields = sum(1 for f in fields if f.field_type == 'text')
            st.caption(f"☑️ {checkboxes} checkboxes (auto-quest)")
            st.caption(f"📝 {text_fields} text fields")
            
            if unmapped > 0:
                st.warning(f"⚠️ {unmapped} unmapped")
            
            st.markdown("---")
            
            # Part breakdown with progress
            st.markdown("### 📑 Parts Progress")
            for part, part_fields in st.session_state.fields_by_part.items():
                complete = sum(1 for f in part_fields if f.is_mapped or f.to_questionnaire)
                part_progress = complete / len(part_fields) if part_fields else 0
                
                part_num = int(part.split()[1])
                part_title = st.session_state.part_info.get(part_num, "")
                
                st.markdown(f"**{part}**")
                if part_title:
                    st.caption(part_title)
                st.progress(part_progress)
                st.caption(f"{complete}/{len(part_fields)} fields")
        else:
            st.info("Upload a PDF to begin")
        
        st.markdown("---")
        st.markdown("### ✨ Key Features")
        st.markdown("""
        - ✅ **Extracts ALL parts** properly
        - ☑️ **Auto-moves checkboxes** to questionnaire
        - 🤖 **Smart field matching** with AI
        - 📊 **Comprehensive export** options
        """)
        
        st.markdown("---")
        st.markdown("### 🚀 Quick Tips")
        st.markdown("""
        1. All checkboxes → auto questionnaire
        2. Use **Auto-map** for common fields
        3. Review unmapped before export
        4. Check extraction log for details
        """)

if __name__ == "__main__":
    main()
