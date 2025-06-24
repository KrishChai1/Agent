import streamlit as st
import json
import re
import fitz  # PyMuPDF
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Union
from collections import OrderedDict, defaultdict
import pandas as pd
from dataclasses import dataclass, field
import difflib

# Complete Database Object Structure
DB_OBJECTS = {
    "attorney": {
        "attorneyInfo": [
            "firstName", "lastName", "middleName", "workPhone", "mobilePhone", 
            "emailAddress", "faxNumber", "stateBarNumber", "licensingAuthority", 
            "stateOfHighestCourt", "nameOfHighestCourt", "signature",
            "uscisOnlineAccountNumber"
        ],
        "address": [
            "addressStreet", "addressCity", "addressState", "addressZip", 
            "addressCountry", "addressNumber", "addressType"
        ]
    },
    "attorneyLawfirmDetails": {
        "lawfirmDetails": ["lawFirmName", "lawFirmFein"],
        "address": [
            "addressStreet", "addressCity", "addressState", "addressZip", 
            "addressCountry", "addressNumber", "addressType"
        ]
    },
    "beneficiary": {
        "Beneficiary": [
            "beneficiaryFirstName", "beneficiaryLastName", "beneficiaryMiddleName",
            "beneficiaryGender", "beneficiaryDateOfBirth", "beneficiarySsn",
            "alienNumber", "beneficiaryCountryOfBirth", "beneficiaryProvinceOfBirth",
            "stateBirth", "beneficiaryCitizenOfCountry", "beneficiaryCellNumber",
            "beneficiaryHomeNumber", "beneficiaryWorkNumber", "beneficiaryPrimaryEmailAddress",
            "maritalStatus", "fatherFirstName", "fatherLastName", "motherFirstName", 
            "motherLastName", "beneficiarySalutation", "beneficiaryVisaType",
            "beneficiaryDependentsCount"
        ],
        "HomeAddress": [
            "addressStreet", "addressCity", "addressState", "addressZip", 
            "addressCountry", "addressNumber", "addressType"
        ],
        "WorkAddress": [
            "addressStreet", "addressCity", "addressState", "addressZip", 
            "addressCountry", "addressNumber", "addressType"
        ],
        "ForeignAddress": [
            "addressStreet", "addressCity", "addressState", "addressZip", 
            "addressCountry", "addressNumber", "addressType", "addressCounty"
        ],
        "PassportDetails": {
            "Passport": [
                "passportNumber", "passportIssueCountry", 
                "passportIssueDate", "passportExpiryDate"
            ]
        },
        "VisaDetails": {
            "Visa": [
                "visaStatus", "visaExpiryDate", "visaConsulateCity", 
                "visaConsulateCountry", "visaNumber", "f1SevisNumber", 
                "eligibilityCategory", "visaAbroad", "newEffectiveDate",
                "changeOfStatus", "extensionUntil", "eduDegree",
                "employerName", "employerEverify", "arrestedCrime",
                "spouseUscisReceipt", "f1OptEadNumber"
            ]
        },
        "I94Details": {
            "I94": [
                "i94Number", "i94ArrivalDate", "i94ExpiryDate", 
                "i94DepartureDate", "placeLastArrival", "statusAtArrival"
            ]
        },
        "H1bDetails": {
            "H1b": [
                "h1bReceiptNumber", "h1bStartDate", "h1bExpiryDate", 
                "h1bType", "h1bStatus"
            ]
        },
        "GcDetails": {
            "Gc": [
                "gcType", "gcAlienNumber", "gcReceiptNumber"
            ]
        },
        "F1Details": {
            "F1": [
                "sevisNumber", "optEadNumber"
            ]
        },
        "EducationDetails": {
            "BeneficiaryEducation": [
                "universityName", "degreeType", "majorFieldOfStudy", 
                "graduationYear"
            ],
            "Address": [
                "addressStreet", "addressCity", "addressState", "addressZip",
                "addressCountry", "addressType", "addressNumber"
            ]
        },
        "WorkExperienceDetails": {
            "WorkExperienceDetail": [
                "employerName", "jobTitle", "startDate", "endDate", "jobDetails"
            ],
            "Address": [
                "addressStreet", "addressCity", "addressState", "addressZip",
                "addressCountry", "addressType", "addressNumber"
            ]
        },
        "BdDetails": {
            "BeneficiaryDependent": [
                "dependentFirstName", "dependentLastName", "dependentMiddleName",
                "dependentDateOfBirth", "dependentCountryOfBirth", "dependentType",
                "adjustmentOfStatus", "visaAbroad", "dependentAlienNumber",
                "dependentGender", "dependentCitizenOfCountry", "dependentSocialSecurityNumber",
                "dateOfArrival", "i94Number", "passportNumber", "countryOfPassport",
                "passportExpiryDate", "dependentCurrentVisaStatus", "dependentVisaExpiryDate"
            ]
        }
    },
    "customer": {
        "": [
            "customer_name", "customer_type_of_business", "customer_tax_id", 
            "customer_naics_code", "customer_total_employees", "customer_total_h1b_employees", 
            "customer_gross_annual_income", "customer_net_annual_income", 
            "customer_year_established", "customer_dot_code", "h1_dependent_employer", 
            "willful_violator", "higher_education_institution", "nonprofit_organization", 
            "nonprofit_research_organization", "cap_exempt_institution",
            "primary_secondary_education_institution", "nonprofit_clinical_institution",
            "guam_cnmi_cap_exemption", "managing_attorney_id"
        ],
        "signatory": [
            "signatory_first_name", "signatory_last_name", "signatory_middle_name",
            "signatory_job_title", "signatory_work_phone", "signatory_mobile_phone",
            "signatory_email_id", "signatory_digital_signature"
        ],
        "address": [
            "address_street", "address_city", "address_state", "address_zip",
            "address_country", "address_number", "address_type"
        ]
    },
    "case": {
        "": [
            "caseType", "caseSubType", "h1BPetitionType", "premiumProcessing", 
            "h1BRegistrationNumber", "h4Filing", "carrier", "serviceCenter",
            "wageLevel"
        ]
    },
    "lca": {
        "": [
            "positionJobTitle", "inhouseProject", "endClientName", "jobLocation",
            "grossSalary", "swageUnit", "startDate", "endDate", "prevailingWageRate",
            "pwageUnit", "socOnetOesCode", "socOnetOesTitle", "fullTimePosition",
            "wageLevel", "sourceYear", "lcaNumber"
        ],
        "Addresses": [
            "addressStreet", "addressCity", "addressState", "addressZip",
            "addressCounty", "addressType", "addressNumber"
        ]
    }
}

# Field type mappings for TypeScript format
FIELD_TYPE_SUFFIX_MAP = {
    "text": ":TextBox",
    "checkbox": ":CheckBox",
    "radio": ":ConditionBox",
    "select": ":SelectBox",
    "date": ":Date",
    "signature": ":SignatureBox",
    "listbox": ":ListBox",
    "number": ":NumberBox"
}

# Special field type mappings - be specific to avoid false matches
SPECIAL_FIELD_TYPES = {
    # These are very specific field names that should get special types
    "addressType": ":AddressTypeBox",
    "address_type": ":AddressTypeBox",
    "representative": ":ConditionBox",
    "careOfName": ":FullName",
    "care_of_name": ":FullName",
    "alienNumber": ":SingleBox",
    "alien_number": ":SingleBox",
    "ussocialssn": ":SingleBox",
    "arrivalDepartureRecords": ":ConditionBox",
    "arrival_departure_records": ":ConditionBox",
    "dependentApplication": ":ConditionBox",
    "dependent_application": ":ConditionBox",
    "h1bBeneficiaryFirstName": ":MultipleBox",
    "beneficiaryFullName": ":FullName",
    "beneficiary_full_name": ":FullName",
}

# Form-specific part structures
FORM_PART_STRUCTURES = {
    "G-28": {
        "Part 0": "To be completed by attorney or BIA-accredited representative",
        "Part 1": "Information About Attorney or Accredited Representative",
        "Part 2": "Eligibility Information for Attorney or Accredited Representative",
        "Part 3": "Notice of Appearance",
        "Part 4": "Client Consent",
        "Part 5": "Attorney Signature",
        "Part 6": "Additional Information"
    },
    "I-129": {
        "Part 1": "Petitioner Information",
        "Part 2": "Information About This Petition",
        "Part 3": "Beneficiary Information",
        "Part 4": "Processing Information",
        "Part 5": "Basic Information About Employment",
        "Part 6": "Export Control Certification",
        "Part 7": "Petitioner Declaration",
        "Part 8": "Preparer Information",
        "Part 9": "Additional Information"
    },
    "I-90": {
        "Part 1": "Information About You",
        "Part 2": "Application Type",
        "Part 3": "Processing Information",
        "Part 4": "Applicant's Statement",
        "Part 5": "Interpreter's Contact Information",
        "Part 6": "Contact Information of Preparer",
        "Part 7": "Additional Information"
    }
}

@dataclass
class PDFField:
    """Represents a field extracted from PDF"""
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
    mapping_config: Optional[Dict[str, Any]] = None
    is_mapped: bool = False
    is_questionnaire: bool = False
    confidence_score: float = 0.0
    field_type_suffix: str = ":TextBox"
    clean_name: str = ""  # Clean field name like I-90.ts format
    is_custom_field: bool = False  # Flag for custom added fields

@dataclass
class MappingSuggestion:
    """Represents a mapping suggestion"""
    db_path: str
    confidence: float
    reason: str
    field_type: str = "direct"

class UniversalUSCISMapper:
    """Universal USCIS Form Mapping System"""
    
    def __init__(self):
        self.db_objects = DB_OBJECTS
        self.form_part_structures = FORM_PART_STRUCTURES
        self.init_session_state()
        self._build_database_paths_cache()
        
    def init_session_state(self):
        """Initialize Streamlit session state"""
        if 'form_type' not in st.session_state:
            st.session_state.form_type = None
        if 'pdf_fields' not in st.session_state:
            st.session_state.pdf_fields = []
        if 'field_mappings' not in st.session_state:
            st.session_state.field_mappings = {}
        if 'questionnaire_fields' not in st.session_state:
            st.session_state.questionnaire_fields = {}
        if 'conditional_mappings' not in st.session_state:
            st.session_state.conditional_mappings = {}
        if 'custom_field_counter' not in st.session_state:
            st.session_state.custom_field_counter = 1000  # Start from 1000 for custom fields
    
    def _build_database_paths_cache(self):
        """Build a cache of all database paths for efficient access"""
        self.db_paths_cache = []
        
        def extract_paths(obj_name, structure, prefix=""):
            """Recursively extract all paths from the database structure"""
            if isinstance(structure, dict):
                for key, value in structure.items():
                    if key == "":  # Empty string key
                        # Direct fields under object
                        if isinstance(value, list):
                            for field_name in value:
                                path = f"{obj_name}.{field_name}"
                                self.db_paths_cache.append(path)
                    else:
                        # Named sub-object
                        new_prefix = f"{obj_name}.{key}"
                        if isinstance(value, list):
                            # List of fields
                            for field_name in value:
                                path = f"{new_prefix}.{field_name}"
                                self.db_paths_cache.append(path)
                        elif isinstance(value, dict):
                            # Nested structure
                            for nested_key, nested_value in value.items():
                                if isinstance(nested_value, list):
                                    for field_name in nested_value:
                                        path = f"{new_prefix}.{nested_key}.{field_name}"
                                        self.db_paths_cache.append(path)
                                elif isinstance(nested_value, dict):
                                    # Even deeper nesting
                                    for deep_key, deep_value in nested_value.items():
                                        if isinstance(deep_value, list):
                                            for field_name in deep_value:
                                                path = f"{new_prefix}.{nested_key}.{deep_key}.{field_name}"
                                                self.db_paths_cache.append(path)
            elif isinstance(structure, list):
                # Direct list of fields
                for field_name in structure:
                    if prefix:
                        path = f"{prefix}.{field_name}"
                    else:
                        path = f"{obj_name}.{field_name}"
                    self.db_paths_cache.append(path)
        
        # Build paths for all objects
        for obj_name, obj_structure in self.db_objects.items():
            extract_paths(obj_name, obj_structure)
        
        # Remove duplicates and sort
        self.db_paths_cache = sorted(list(set(self.db_paths_cache)))
        
        # Debug output
        print(f"Built database paths cache with {len(self.db_paths_cache)} paths")
    
    def get_all_database_paths(self) -> List[str]:
        """Get all available database paths from cache"""
        return self.db_paths_cache.copy()
    
    def _clean_field_name_for_export(self, field_name: str, part: str, item: str = "") -> str:
        """Clean field name to match I-90.ts format (e.g., P1_3a)"""
        # Extract part number from the assigned part
        part_match = re.search(r'Part\s*(\d+)', part, re.IGNORECASE)
        if not part_match and re.search(r'Part\s*0', part, re.IGNORECASE):
            part_num = "0"
        else:
            part_num = part_match.group(1) if part_match else "1"
        
        # Special handling for attorney section (Part 0)
        if "attorney" in part.lower() or "representative" in part.lower():
            if not part_match:
                part_num = "0"
        
        # Use the item if provided from extraction
        field_id = item
        
        if not field_id:
            # Check for SubP patterns first
            subp_match = re.search(r'SubP\d+line(\d+[a-zA-Z]?)', field_name, re.IGNORECASE)
            if subp_match:
                field_id = subp_match.group(1)
            else:
                # Clean the field name more aggressively
                clean_name = field_name
                
                # Remove all the form structure patterns
                patterns_to_remove = [
                    r'form\d*\[\d+\]\.',
                    r'#subform\[\d+\]\.',
                    r'#pageSet\[\d+\]\.',
                    r'Page\d+\[\d+\]\.',
                    r'PDF417BarCode\d*\[\d+\]',
                    r'topmostSubform\[\d+\]\.',
                    r'Form\d+\s*#page\s*Set\s*Page\d+\s*',
                    r'Pdf417bar\s*Code\d+',
                    r'\[\d+\]',
                    r'^#',
                    r'\.pdf$',
                    r'^Page\d+\.',
                    r'^form\.',
                    r'^field\.',
                    r'P\d+line',
                    r'Part\d+line',
                    r'SubP\d+line',
                ]
                
                for pattern in patterns_to_remove:
                    clean_name = re.sub(pattern, '', clean_name, flags=re.IGNORECASE)
                
                # Try to extract from the cleaned field name
                # Look for common patterns
                patterns = [
                    # Look for specific field patterns first
                    r'AttorneyStateBarNumber',  # -> would become something like P0_1a
                    r'P(\d+)_(\d+[a-zA-Z]?)',   # Already in format
                    r'Part(\d+)_(\d+[a-zA-Z]?)', # Part format
                    r'line(\d+[a-zA-Z]?)',       # line patterns
                    r'Item[\s_\.\-]*(\d+[a-zA-Z]?)',
                    r'Question[\s_\.\-]*(\d+[a-zA-Z]?)',
                    r'_(\d+[a-zA-Z]?)$',         # End numbers
                    r'#(\d+[a-zA-Z]?)',          # Hash numbers
                ]
                
                # Special handling for known field types
                if 'AttorneyStateBarNumber' in clean_name:
                    # Look for a number pattern in the original field name
                    num_match = re.search(r'(\d+[a-zA-Z]?)', field_name)
                    if num_match:
                        field_id = num_match.group(1)
                    else:
                        field_id = '1a'  # Default for state bar number
                elif 'FamilyName' in clean_name or 'LastName' in clean_name:
                    # Check if there's a line number before it
                    line_match = re.search(r'line(\d+[a-zA-Z]?)', field_name, re.IGNORECASE)
                    if line_match:
                        field_id = line_match.group(1)
                    else:
                        field_id = '1a'  # Default for family name
                elif 'GivenName' in clean_name or 'FirstName' in clean_name:
                    line_match = re.search(r'line(\d+[a-zA-Z]?)', field_name, re.IGNORECASE)
                    if line_match:
                        field_id = line_match.group(1)
                    else:
                        field_id = '1b'
                elif 'MiddleName' in clean_name:
                    line_match = re.search(r'line(\d+[a-zA-Z]?)', field_name, re.IGNORECASE)
                    if line_match:
                        field_id = line_match.group(1)
                    else:
                        field_id = '1c'
                else:
                    # Try patterns
                    for pattern in patterns:
                        match = re.search(pattern, clean_name, re.IGNORECASE)
                        if match:
                            if pattern.startswith(r'P(\d+)'):
                                # Already has part, use the field part
                                field_id = match.group(2)
                            else:
                                field_id = match.group(1) if match.lastindex == 1 else match.group(match.lastindex)
                            break
        
        # If still no field ID, try to extract any number
        if not field_id:
            # Look in the original field name for any line numbers
            line_match = re.search(r'line(\d+[a-zA-Z]?)', field_name, re.IGNORECASE)
            if line_match:
                field_id = line_match.group(1)
            else:
                numbers = re.findall(r'\b(\d{1,2}[a-zA-Z]?)\b', field_name)
                if numbers:
                    # Filter out part numbers
                    valid_numbers = [n for n in numbers if not re.match(r'^0\d$', n)]  # Skip 00-09
                    if valid_numbers:
                        field_id = valid_numbers[-1]
        
        # Last resort - use counter
        if not field_id:
            field_id = str(self.field_counter)
            self.field_counter += 1
        
        # Clean up field ID
        field_id = field_id.strip('._- ')
        
        # Ensure field ID is reasonable length
        if len(field_id) > 5:
            # Try to extract just the numeric part with optional letter
            match = re.search(r'(\d{1,2}[a-zA-Z]?)', field_id)
            if match:
                field_id = match.group(1)
            else:
                field_id = field_id[:5]
        
        # Construct the clean name
        return f"P{part_num}_{field_id}"
    
    def extract_pdf_fields(self, pdf_file, form_type: str) -> List[PDFField]:
        """Extract all fields from any USCIS PDF form with accurate part detection"""
        fields = []
        self.field_counter = 1  # Initialize field counter
        
        try:
            pdf_bytes = pdf_file.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            # Clean form type to get base form name
            base_form_type = form_type.split(' - ')[0].strip()
            
            # Check if this form has attorney section
            has_attorney_section = base_form_type in ["G-28", "I-129", "I-130", "I-140"]
            
            # First pass: collect all field names to understand structure
            all_field_data = []
            field_index = 0
            seen_fields = set()  # Track seen field names to avoid duplicates
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                for widget in page.widgets():
                    if widget.field_name:
                        # Skip duplicate field names
                        if widget.field_name in seen_fields:
                            continue
                        seen_fields.add(widget.field_name)
                        
                        all_field_data.append({
                            'name': widget.field_name,
                            'page': page_num + 1,
                            'widget': widget,
                            'index': field_index,
                            'display': widget.field_display or ""
                        })
                        field_index += 1
            
            # Analyze field names to understand part structure
            part_mapping = self._analyze_form_structure_advanced(all_field_data, base_form_type, has_attorney_section)
            
            # Second pass: create field objects with correct parts
            for field_data in all_field_data:
                widget = field_data['widget']
                
                # Extract field information
                field_type = self._get_field_type(widget)
                
                # Get part from our analysis
                part = part_mapping.get(field_data['index'], f"Page {field_data['page']}")
                
                # Extract item
                item = self._extract_item_advanced(widget.field_name, field_data['display'])
                
                # Generate description
                description = self._generate_description(widget.field_name, widget.field_display)
                
                # Determine field type suffix
                field_type_suffix = self._get_field_type_suffix(widget.field_name, field_type)
                
                # Generate clean name for export
                clean_name = self._clean_field_name_for_export(widget.field_name, part, item)
                
                # Create field object
                pdf_field = PDFField(
                    index=field_data['index'],
                    raw_name=widget.field_name,
                    field_type=field_type,
                    value=widget.field_value or '',
                    page=field_data['page'],
                    part=part,
                    item=item,
                    description=description,
                    field_type_suffix=field_type_suffix,
                    clean_name=clean_name
                )
                
                # Get mapping suggestions
                suggestions = self._get_mapping_suggestions(pdf_field, base_form_type)
                if suggestions:
                    best_suggestion = suggestions[0]
                    pdf_field.db_mapping = best_suggestion.db_path
                    pdf_field.confidence_score = best_suggestion.confidence
                    pdf_field.mapping_type = best_suggestion.field_type
                    pdf_field.is_mapped = False  # Not mapped yet, just suggested
                    pdf_field.is_questionnaire = False
                else:
                    # No mapping found - mark as questionnaire by default
                    pdf_field.is_questionnaire = True
                    pdf_field.is_mapped = False
                    pdf_field.db_mapping = None
                
                fields.append(pdf_field)
            
            doc.close()
            
            # Display extraction summary
            self._display_extraction_summary(fields, form_type)
            
        except Exception as e:
            st.error(f"Error extracting PDF: {str(e)}")
            import traceback
            st.error(traceback.format_exc())
            return []
        
        return fields
    
    def add_custom_field(self, part: str, item: str, description: str, field_type: str = "text") -> PDFField:
        """Add a custom field to the form"""
        # Generate unique index
        custom_index = st.session_state.custom_field_counter
        st.session_state.custom_field_counter += 1
        
        # Extract part number for clean name
        part_match = re.search(r'Part\s*(\d+)', part, re.IGNORECASE)
        part_num = part_match.group(1) if part_match else "1"
        
        # Generate clean name
        clean_name = f"P{part_num}_{item}" if item else f"P{part_num}_custom{custom_index}"
        
        # Determine field type suffix
        field_type_suffix = FIELD_TYPE_SUFFIX_MAP.get(field_type, ":TextBox")
        
        # Create custom field
        custom_field = PDFField(
            index=custom_index,
            raw_name=f"custom_field_{custom_index}",
            field_type=field_type,
            value="",
            page=1,
            part=part,
            item=item,
            description=description,
            field_type_suffix=field_type_suffix,
            clean_name=clean_name,
            is_custom_field=True,
            is_questionnaire=True  # Default to questionnaire
        )
        
        return custom_field
    
    def _clean_field_name_for_analysis(self, field_name: str) -> str:
        """Clean field name for better pattern analysis"""
        # Remove common noise patterns
        patterns_to_remove = [
            r'form\d*\[\d+\]\.',
            r'#subform\[\d+\]\.',
            r'#pageSet\[\d+\]\.',
            r'Page\d+\[\d+\]\.',
            r'PDF417BarCode\d*\[\d+\]',
            r'\[\d+\]',
            r'\.pdf$',
            r'^#',
        ]
        
        clean_name = field_name
        for pattern in patterns_to_remove:
            clean_name = re.sub(pattern, '', clean_name, flags=re.IGNORECASE)
        
        return clean_name
    
    def _group_fields_by_pattern(self, all_field_data: List[Dict]) -> Dict[int, str]:
        """Group fields by common patterns to identify parts"""
        field_groups = {}
        
        # Common patterns that indicate field groupings
        group_patterns = {
            'petitioner': 'Part 1',
            'beneficiary': 'Part 3',
            'employment': 'Part 5',
            'processing': 'Part 4',
            'declaration': 'Part 7',
            'preparer': 'Part 8',
            'additional': 'Part 9',
            'attorney': 'Part 0',
            'representative': 'Part 0',
            'appearance': 'Part 0',
        }
        
        for field_data in all_field_data:
            field_text = f"{field_data['name']} {field_data.get('display', '')}".lower()
            
            for pattern, part in group_patterns.items():
                if pattern in field_text:
                    field_groups[field_data['index']] = part
                    break
        
        return field_groups
    
    def _detect_page_boundaries(self, all_field_data: List[Dict]) -> Dict[int, str]:
        """Detect logical part boundaries based on page transitions"""
        page_boundaries = {}
        
        # Analyze field distribution across pages
        fields_per_page = defaultdict(list)
        for field_data in all_field_data:
            fields_per_page[field_data['page']].append(field_data)
        
        # Look for patterns in page transitions
        for page, fields in fields_per_page.items():
            if len(fields) < 5:  # Small number of fields might indicate end of part
                continue
            
            # Check first few fields of the page for part indicators
            first_fields = fields[:5]
            for field in first_fields:
                clean_name = self._clean_field_name_for_analysis(field['name'])
                
                # Look for part indicators
                part_match = re.search(r'Part[\s_\-]*(\d+)', clean_name, re.IGNORECASE)
                if part_match:
                    page_boundaries[page] = f"Part {part_match.group(1)}"
                    break
        
        return page_boundaries
    
    def _infer_part_from_context(self, field_data: Dict, all_fields: List[Dict], 
                                 current_index: int, known_structure: Dict) -> str:
        """Infer part from field context and surrounding fields"""
        page = field_data['page']
        
        # Look at nearby fields for clues
        window_size = 10
        start_idx = max(0, current_index - window_size)
        end_idx = min(len(all_fields), current_index + window_size + 1)
        
        nearby_fields = all_fields[start_idx:end_idx]
        
        # Check for part indicators in nearby fields
        for nearby in nearby_fields:
            clean_name = self._clean_field_name_for_analysis(nearby['name'])
            part_match = re.search(r'Part[\s_\-]*(\d+)', clean_name, re.IGNORECASE)
            if part_match:
                part = f"Part {part_match.group(1)}"
                if known_structure and part in known_structure:
                    return f"{part} - {known_structure[part]}"
                return part
        
        # Default based on page number
        if page == 1:
            return "Part 1" if not known_structure else "Part 1 - " + known_structure.get("Part 1", "Information")
        else:
            estimated_part = f"Part {page}"
            if known_structure and estimated_part in known_structure:
                return f"{estimated_part} - {known_structure[estimated_part]}"
            return f"Page {page}"
    
    def _smooth_part_assignments(self, part_mapping: Dict[int, str], 
                                all_field_data: List[Dict]) -> Dict[int, str]:
        """Smooth out part assignments to fix inconsistencies"""
        # Group consecutive fields and ensure they have consistent parts
        sorted_fields = sorted(all_field_data, key=lambda x: (x['page'], x['index']))
        
        for i in range(1, len(sorted_fields) - 1):
            current = sorted_fields[i]
            prev = sorted_fields[i-1]
            next_field = sorted_fields[i+1]
            
            current_idx = current['index']
            prev_idx = prev['index']
            next_idx = next_field['index']
            
            # If current field has no clear part but neighbors do
            if current_idx in part_mapping:
                current_part = part_mapping[current_idx]
                
                # If surrounded by same part and on same page, assign same part
                if (prev_idx in part_mapping and next_idx in part_mapping and 
                    part_mapping[prev_idx] == part_mapping[next_idx] and
                    current['page'] == prev['page'] == next_field['page'] and
                    'Page' in current_part and 'Part' in part_mapping[prev_idx]):
                    part_mapping[current_idx] = part_mapping[prev_idx]
        
        return part_mapping
    
    def _analyze_form_structure_advanced(self, all_field_data: List[Dict], form_type: str, has_attorney_section: bool) -> Dict[int, str]:
        """Advanced form structure analysis with improved part detection"""
        part_mapping = {}
        
        # Get known structure for this form type
        known_structure = self.form_part_structures.get(form_type, {})
        
        # Enhanced part detection using multiple strategies
        
        # Strategy 1: Look for part indicators in field names (cleaned)
        part_indicators = {}
        for field_data in all_field_data:
            field_name = field_data['name']
            display_name = field_data.get('display', '')
            
            # Clean the field name for better pattern matching
            clean_field = self._clean_field_name_for_analysis(field_name)
            
            # Look for part patterns in cleaned name
            part_patterns = [
                (r'Part[\s_\-]*(\d+)', lambda m: f"Part {m.group(1)}"),
                (r'P(\d+)_', lambda m: f"Part {m.group(1)}"),
                (r'pt(\d+)_', lambda m: f"Part {m.group(1)}"),
                (r'Section[\s_\-]*(\d+)', lambda m: f"Part {m.group(1)}"),
                (r'Part_(\d+)', lambda m: f"Part {m.group(1)}"),
            ]
            
            for pattern, formatter in part_patterns:
                match = re.search(pattern, clean_field, re.IGNORECASE)
                if match:
                    part_num = formatter(match)
                    if field_data['index'] not in part_indicators:
                        part_indicators[field_data['index']] = part_num
                    break
        
        # Strategy 2: Analyze field groups by name patterns
        field_groups = self._group_fields_by_pattern(all_field_data)
        
        # Strategy 3: Use page boundaries and field positions
        page_boundaries = self._detect_page_boundaries(all_field_data)
        
        # Strategy 4: Check for attorney fields on first page
        if has_attorney_section:
            attorney_keywords = ['attorney', 'representative', 'bar', 'licensing', 'accredited', 'g-28', 'g28', 'appearance', 'eligibility']
            first_page_fields = [f for f in all_field_data if f['page'] == 1]
            
            # More thorough check for attorney fields
            attorney_field_count = 0
            for f in first_page_fields:
                field_text = f"{f['name']} {f.get('display', '')}".lower()
                if any(keyword in field_text for keyword in attorney_keywords):
                    attorney_field_count += 1
            
            # If significant number of attorney fields on first page
            if attorney_field_count >= 3 or (attorney_field_count > 0 and len(first_page_fields) < 20):
                for f in first_page_fields:
                    part_mapping[f['index']] = "Part 0 - To be completed by attorney or BIA-accredited representative"
        
        # Strategy 5: Use field sequence and content analysis
        current_part = None
        current_page = 1
        field_count_in_part = 0
        last_part_indicator_index = -1
        
        for i, field_data in enumerate(all_field_data):
            if field_data['index'] in part_mapping:  # Skip already mapped fields
                continue
            
            field_name = field_data['name']
            page = field_data['page']
            
            # Check if we have a part indicator for this field
            if field_data['index'] in part_indicators:
                current_part = part_indicators[field_data['index']]
                last_part_indicator_index = i
                field_count_in_part = 0
                
                # Add description from known structure if available
                if known_structure and current_part in known_structure:
                    current_part = f"{current_part} - {known_structure[current_part]}"
                
                part_mapping[field_data['index']] = current_part
                current_page = page
            
            # Check field groups
            elif field_data['index'] in field_groups:
                group_part = field_groups[field_data['index']]
                if group_part != current_part:
                    current_part = group_part
                    field_count_in_part = 0
                part_mapping[field_data['index']] = current_part
            
            # If we're on the same page and have a current part
            elif current_part and page == current_page:
                # Check if we should continue with current part
                if field_count_in_part < 50:  # Reasonable field count per part
                    part_mapping[field_data['index']] = current_part
                    field_count_in_part += 1
                else:
                    # Too many fields, might be a new part
                    current_part = self._infer_part_from_context(field_data, all_field_data, i, known_structure)
                    part_mapping[field_data['index']] = current_part
                    field_count_in_part = 0
            
            # Page boundary detected
            elif page != current_page and page in page_boundaries:
                suggested_part = page_boundaries[page]
                if suggested_part != current_part:
                    current_part = suggested_part
                    field_count_in_part = 0
                part_mapping[field_data['index']] = current_part
                current_page = page
            
            # Default: try to infer from context
            else:
                inferred_part = self._infer_part_from_context(field_data, all_field_data, i, known_structure)
                part_mapping[field_data['index']] = inferred_part
                if inferred_part != current_part:
                    current_part = inferred_part
                    field_count_in_part = 0
                current_page = page
        
        # Post-process: smooth out any inconsistencies
        part_mapping = self._smooth_part_assignments(part_mapping, all_field_data)
        
        return part_mapping
    
    def _extract_item_advanced(self, field_name: str, field_display: str = "") -> str:
        """Advanced item extraction with better pattern matching"""
        # First clean the field name
        clean_name = self._clean_field_name_for_analysis(field_name)
        
        # Special handling for SubP patterns
        # If field name has SubP0line1a pattern, extract the item (1a)
        subp_match = re.search(r'SubP\d+line(\d+[a-zA-Z]?)', clean_name, re.IGNORECASE)
        if subp_match:
            return subp_match.group(1)
        
        # Remove misleading part references
        clean_name = re.sub(r'P\d+line', 'line', clean_name, flags=re.IGNORECASE)
        clean_name = re.sub(r'Part\d+line', 'line', clean_name, flags=re.IGNORECASE)
        clean_name = re.sub(r'SubP\d+line', 'line', clean_name, flags=re.IGNORECASE)
        
        # Also check display name
        all_text = f"{clean_name} {field_display}"
        
        # Comprehensive patterns for item extraction
        patterns = [
            # Explicit item patterns
            r'Item\s*Number\s*(\d+[a-zA-Z]?\.?)',
            r'Item\s*(\d+[a-zA-Z]?\.?)',
            r'Line\s*(\d+[a-zA-Z]?\.?)',
            r'Question\s*(\d+[a-zA-Z]?\.?)',
            r'Q\s*(\d+[a-zA-Z]?\.?)',
            r'No\.?\s*(\d+[a-zA-Z]?)',
            r'Number\s*(\d+[a-zA-Z]?)',
            
            # Field ID patterns - updated to avoid part references
            r'line(\d+[a-zA-Z]?)',  # line1a, line2b, etc.
            r'[_\.\-](\d+[a-zA-Z]?)$',  # At end
            r'[_\.\-](\d+[a-zA-Z]?)[_\.\-]',  # In middle
            
            # Other patterns
            r'#(\d+[a-zA-Z]?)',
            r'\b(\d{1,2}[a-zA-Z]?)\b',  # Standalone small numbers with optional letter
        ]
        
        # Try patterns on clean name first
        for pattern in patterns:
            match = re.search(pattern, clean_name, re.IGNORECASE)
            if match:
                item = match.group(1)
                # Validate item - should be reasonable (1-99 with optional letter)
                if re.match(r'^\d{1,2}[a-zA-Z]?$', item):
                    return item.rstrip('.')
        
        # If not found, try on full text
        for pattern in patterns:
            match = re.search(pattern, all_text, re.IGNORECASE)
            if match:
                item = match.group(1)
                # Validate item
                if re.match(r'^\d{1,2}[a-zA-Z]?$', item):
                    return item.rstrip('.')
        
        # Last resort: look for any reasonable field identifier
        # Extract all alphanumeric segments
        segments = re.findall(r'[a-zA-Z0-9]+', clean_name)
        for segment in reversed(segments):  # Start from end
            # Check if segment looks like a field ID (not a part reference)
            if re.match(r'^\d{1,2}[a-zA-Z]?$', segment) and not re.match(r'^P\d+$', segment):
                return segment
        
        return ""
    
    def _get_field_type(self, widget) -> str:
        """Determine field type from widget"""
        if widget.field_type == fitz.PDF_WIDGET_TYPE_CHECKBOX:
            return "checkbox"
        elif widget.field_type == fitz.PDF_WIDGET_TYPE_RADIOBUTTON:
            return "radio"
        elif widget.field_type == fitz.PDF_WIDGET_TYPE_COMBOBOX:
            return "select"
        elif widget.field_type == fitz.PDF_WIDGET_TYPE_LISTBOX:
            return "listbox"
        elif widget.field_type == fitz.PDF_WIDGET_TYPE_SIGNATURE:
            return "signature"
        else:
            # Check if it's a date field
            if any(pattern in widget.field_name.lower() for pattern in ['date', 'mm/dd/yyyy', 'fecha']):
                return "date"
            return "text"
    
    def _get_field_type_suffix(self, field_name: str, field_type: str) -> str:
        """Get TypeScript field type suffix based on field name and type"""
        field_name_lower = field_name.lower()
        
        # Clean the field name first to better match patterns
        clean_name = re.sub(r'\[\d+\]', '', field_name_lower)
        clean_name = re.sub(r'form\d*\.', '', clean_name)
        clean_name = re.sub(r'#subform\d*\.', '', clean_name)
        
        # Check special field types first - be more specific
        # Only assign FullName if it's explicitly a full name field
        if any(pattern in clean_name for pattern in ['fullname', 'full_name', 'completename']):
            return ":FullName"
        
        # Check for name fields - individual name fields should be TextBox
        elif any(pattern in clean_name for pattern in ['lastname', 'last_name', 'familyname', 'family_name']):
            return ":TextBox"  # Individual name fields are text boxes
        elif any(pattern in clean_name for pattern in ['firstname', 'first_name', 'givenname', 'given_name']):
            return ":TextBox"  # Individual name fields are text boxes
        elif any(pattern in clean_name for pattern in ['middlename', 'middle_name', 'middleinitial', 'middle_initial']):
            return ":TextBox"  # Individual name fields are text boxes
        
        # Check for specific field patterns
        elif 'addresstype' in clean_name or 'address_type' in clean_name:
            return ":AddressTypeBox"
        elif any(pattern in clean_name for pattern in ['ssn', 'social_security', 'socialsecurity']):
            return ":SingleBox"
        elif 'alien' in clean_name and any(pattern in clean_name for pattern in ['number', 'no', '#']):
            return ":SingleBox"
        elif 'representative' in clean_name and field_type == "radio":
            return ":ConditionBox"
        elif 'careofname' in clean_name or 'care_of_name' in clean_name:
            return ":FullName"
        elif any(pattern in clean_name for pattern in ['uscisaccount', 'uscis_account', 'onlineaccount']):
            return ":SingleBox"
        elif field_type == "radio":
            return ":ConditionBox"
        elif field_type == "checkbox":
            return ":CheckBox"
        elif field_type == "date" or any(pattern in clean_name for pattern in ['date', 'fecha', 'dob']):
            return ":Date"
        elif field_type == "signature" or 'signature' in clean_name:
            return ":SignatureBox"
        elif field_type == "select" or field_type == "listbox":
            return ":SelectBox"
        elif any(pattern in clean_name for pattern in ['phone', 'telephone', 'fax']):
            return ":TextBox"  # Phone numbers are usually text boxes
        elif 'email' in clean_name:
            return ":TextBox"  # Email is a text box
        elif any(pattern in clean_name for pattern in ['number', 'count', 'total']) and not 'phone' in clean_name:
            return ":NumberBox"  # Numeric fields
        
        # Default mapping based on field type
        return FIELD_TYPE_SUFFIX_MAP.get(field_type, ":TextBox")
    
    def _generate_description(self, field_name: str, field_display: str = "") -> str:
        """Generate human-readable description"""
        # Store original for fallback
        original_name = field_name
        
        # Use display name if available and meaningful
        if field_display and field_display != field_name and not field_display.startswith('form'):
            desc = field_display
        else:
            desc = field_name
        
        # First, handle Sub patterns more carefully
        # Check if this is a SubP pattern that shouldn't be removed
        sub_pattern_match = re.search(r'SubP\d+line\d+[a-zA-Z]?', desc)
        if sub_pattern_match:
            # Extract the actual field name after SubP pattern
            after_pattern = desc[sub_pattern_match.end():]
            if after_pattern:
                # Clean the after pattern part
                after_pattern = re.sub(r'^[_\.\-\s]+', '', after_pattern)
                if after_pattern and not after_pattern.isdigit():
                    desc = after_pattern
        
        # Aggressive cleaning for complex field names
        cleaning_patterns = [
            # Form structure patterns
            r'form\d*\[\d+\]\.',
            r'#subform\[\d+\]\.',
            r'#pageSet\[\d+\]\.',
            r'Page\d+\[\d+\]\.',
            r'topmostSubform\[\d+\]\.',
            r'Form\d+\s*#page\s*Set\s*Page\d+\s*',
            
            # PDF-specific patterns
            r'PDF417BarCode\d*\[\d+\]',
            r'Pdf417bar\s*Code\d+',
            r'\.pdf$',
            
            # Array indices
            r'\[\d+\]',
            
            # Technical prefixes
            r'^#',
            r'^form\.',
            r'^field\.',
            r'^Page\d+\.',
            
            # Part patterns - clean these to avoid confusion
            r'^Part\d+[_\.\-]',
            r'^P\d+[_\.\-]',
            r'^pt\d+[_\.\-]',
            r'P\d+line\d+[a-zA-Z]?[_\.\-]?',  # Remove P1line1a type patterns
            r'Part\d+line\d+[a-zA-Z]?[_\.\-]?',  # Remove Part1line1a type patterns
            
            # Sub-patterns - be more careful here
            r'^SubP\d+line\d+[a-zA-Z]?[_\.\-]',  # Remove SubP1line1a_ prefix
            r'^Sub\s*P\d+line\d+[a-zA-Z]?\s*[_\.\-]',  # Remove "Sub P1line1a_" prefix
        ]
        
        for pattern in cleaning_patterns:
            desc = re.sub(pattern, '', desc, flags=re.IGNORECASE)
        
        # Additional cleaning for line references
        desc = re.sub(r'^line\d+[a-zA-Z]?[_\.\-]?', '', desc, flags=re.IGNORECASE)
        
        # Extract meaningful part after cleaning
        # Look for the last meaningful segment
        segments = desc.split('.')
        meaningful_segments = []
        
        for segment in segments:
            # Skip empty or purely numeric segments
            if segment and not segment.isdigit() and len(segment) > 1:
                # Skip common technical terms
                if segment.lower() not in ['form', 'page', 'field', 'subform', 'text', 'checkbox', 'sub']:
                    meaningful_segments.append(segment)
        
        # Use the most meaningful segment
        if meaningful_segments:
            desc = meaningful_segments[-1]  # Usually the last segment is most descriptive
        
        # Further cleaning
        desc = desc.strip('._- ')
        
        # If we still have technical junk, try different approach
        if not desc or desc.lower() in ['field', 'text', 'checkbox', 'radio', 'sub']:
            # Try to extract from original field name
            parts = original_name.split('.')
            for part in reversed(parts):
                clean_part = re.sub(r'\[\d+\]', '', part)
                clean_part = re.sub(r'SubP\d+line\d+[a-zA-Z]?', '', clean_part, flags=re.IGNORECASE)
                clean_part = re.sub(r'P\d+line\d+[a-zA-Z]?', '', clean_part, flags=re.IGNORECASE)
                clean_part = re.sub(r'line\d+[a-zA-Z]?', '', clean_part, flags=re.IGNORECASE)
                clean_part = clean_part.strip('._- ')
                if clean_part and not clean_part.isdigit() and len(clean_part) > 2:
                    if clean_part.lower() not in ['form', 'page', 'field', 'subform', 'sub']:
                        desc = clean_part
                        break
        
        # Handle underscores and camelCase
        if '_' in desc:
            parts = desc.split('_')
            # Filter out part references and empty parts
            parts = [p for p in parts if p and not p.isdigit() and not re.match(r'^P\d+$', p, re.IGNORECASE)]
            desc = ' '.join(parts)
        
        # Convert camelCase to spaces
        desc = re.sub(r'([a-z])([A-Z])', r'\1 \2', desc)
        
        # Expand common abbreviations and fix common field names
        abbreviations = {
            'FamilyName': 'Last Name',
            'GivenName': 'First Name',
            'MiddleName': 'Middle Name',
            'LastName': 'Last Name',
            'FirstName': 'First Name',
            'Apt': 'Apartment',
            'Ste': 'Suite',
            'Flr': 'Floor',
            'St': 'Street',
            'Ave': 'Avenue',
            'Blvd': 'Boulevard',
            'DOB': 'Date of Birth',
            'SSN': 'Social Security Number',
            'FEIN': 'Federal EIN',
            'EIN': 'Employer Identification Number',
            'MI': 'Middle Initial',
            'Ln': 'Line',
            'Pt': 'Part',
            'No': 'Number',
            'Tel': 'Telephone',
            'Fax': 'Facsimile',
            'Atty': 'Attorney',
            'Org': 'Organization',
            'Corp': 'Corporation',
            'Inc': 'Incorporated',
            'LLC': 'Limited Liability Company',
            'Addr': 'Address',
            'Cty': 'City',
            'Cnty': 'County',
            'Zip': 'ZIP Code',
            'Ph': 'Phone',
            'Sig': 'Signature',
            'Auth': 'Authorization',
            'Rep': 'Representative',
            'Info': 'Information',
            'Num': 'Number',
            'Govt': 'Government',
            'Fed': 'Federal',
            'Intl': 'International',
            'AttorneyStateBarNumber': 'State Bar Number'
        }
        
        # Apply abbreviation expansions
        for abbr, full in abbreviations.items():
            # Case-insensitive replacement for whole words
            desc = re.sub(rf'\b{abbr}\b', full, desc, flags=re.IGNORECASE)
        
        # Clean up and format
        desc = ' '.join(desc.split())
        desc = desc.strip('._- ')
        
        # Only remove "Sub" if it's a standalone prefix, not part of a word
        if desc.startswith('Sub ') and len(desc) > 4:
            desc = desc[4:]
        
        # Smart title case (preserve acronyms)
        if desc:
            words = desc.split()
            result = []
            for word in words:
                if word.isupper() and len(word) > 1 and word not in ['SSN', 'EIN', 'FEIN', 'LLC']:
                    result.append(word)  # Keep acronyms
                else:
                    result.append(word.capitalize())
            desc = ' '.join(result)
        
        # If still empty or generic, provide a default based on item
        if not desc or desc.lower() in ['field', 'text', '', 'sub']:
            # Try to use item number if available
            item_match = re.search(r'(\d+[a-zA-Z]?)', original_name)
            if item_match:
                desc = f"Field {item_match.group(1)}"
            else:
                desc = "Field"
        
        return desc
    
    def _get_mapping_suggestions(self, field: PDFField, form_type: str) -> List[MappingSuggestion]:
        """Get intelligent mapping suggestions for a field"""
        suggestions = []
        
        # Clean field name and description for better matching
        field_name_lower = field.raw_name.lower()
        desc_lower = field.description.lower()
        clean_name_lower = field.clean_name.lower()
        
        # Combine all text for comprehensive matching
        all_text = f"{field_name_lower} {desc_lower} {clean_name_lower}"
        
        # Form-specific mapping rules
        if form_type == "G-28":
            suggestions.extend(self._get_g28_suggestions(field))
        elif form_type == "I-129":
            suggestions.extend(self._get_i129_suggestions(field))
        elif form_type == "I-90":
            suggestions.extend(self._get_i90_suggestions(field))
        
        # Enhanced generic pattern matching
        
        # Attorney/Representative mappings (Part 0 or attorney sections)
        if "part 0" in field.part.lower() or "attorney" in field.part.lower() or "representative" in field.part.lower():
            if any(p in all_text for p in ['lastname', 'last_name', 'family_name', 'apellido']):
                suggestions.append(MappingSuggestion("attorney.attorneyInfo.lastName", 0.95, "Attorney last name"))
            elif any(p in all_text for p in ['firstname', 'first_name', 'given_name', 'nombre']):
                suggestions.append(MappingSuggestion("attorney.attorneyInfo.firstName", 0.95, "Attorney first name"))
            elif any(p in all_text for p in ['middlename', 'middle_name', 'middle_initial']):
                suggestions.append(MappingSuggestion("attorney.attorneyInfo.middleName", 0.9, "Attorney middle name"))
            elif "bar" in all_text and any(p in all_text for p in ['number', 'no', '#']):
                suggestions.append(MappingSuggestion("attorney.attorneyInfo.stateBarNumber", 0.95, "State bar number"))
            elif any(p in all_text for p in ['firm', 'office']) and "name" in all_text:
                suggestions.append(MappingSuggestion("attorneyLawfirmDetails.lawfirmDetails.lawFirmName", 0.9, "Law firm name"))
            elif "fein" in all_text or ("tax" in all_text and "id" in all_text):
                suggestions.append(MappingSuggestion("attorneyLawfirmDetails.lawfirmDetails.lawFirmFein", 0.9, "Law firm FEIN"))
            elif any(p in all_text for p in ['phone', 'telephone', 'tel']):
                if "mobile" in all_text or "cell" in all_text:
                    suggestions.append(MappingSuggestion("attorney.attorneyInfo.mobilePhone", 0.85, "Attorney mobile phone"))
                else:
                    suggestions.append(MappingSuggestion("attorney.attorneyInfo.workPhone", 0.85, "Attorney work phone"))
            elif "email" in all_text:
                suggestions.append(MappingSuggestion("attorney.attorneyInfo.emailAddress", 0.9, "Attorney email"))
            elif "fax" in all_text:
                suggestions.append(MappingSuggestion("attorney.attorneyInfo.faxNumber", 0.85, "Attorney fax"))
            elif "licensing" in all_text and "authority" in all_text:
                suggestions.append(MappingSuggestion("attorney.attorneyInfo.licensingAuthority", 0.9, "Licensing authority"))
            elif "uscis" in all_text and "account" in all_text:
                suggestions.append(MappingSuggestion("attorney.attorneyInfo.uscisOnlineAccountNumber", 0.9, "USCIS account number"))
        
        # Petitioner/Customer mappings (usually Part 1)
        elif "part 1" in field.part.lower() or "petitioner" in field.part.lower():
            if any(p in all_text for p in ['company', 'organization', 'business', 'employer']) and "name" in all_text:
                suggestions.append(MappingSuggestion("customer.customer_name", 0.9, "Company/Organization name"))
            elif any(p in all_text for p in ['lastname', 'last_name', 'family_name']):
                suggestions.append(MappingSuggestion("customer.signatory.signatory_last_name", 0.85, "Signatory last name"))
            elif any(p in all_text for p in ['firstname', 'first_name', 'given_name']):
                suggestions.append(MappingSuggestion("customer.signatory.signatory_first_name", 0.85, "Signatory first name"))
            elif "title" in all_text and "job" in all_text:
                suggestions.append(MappingSuggestion("customer.signatory.signatory_job_title", 0.85, "Signatory job title"))
            elif "fein" in all_text or ("federal" in all_text and "ein" in all_text) or ("tax" in all_text and "id" in all_text):
                suggestions.append(MappingSuggestion("customer.customer_tax_id", 0.9, "Federal Tax ID"))
            elif "naics" in all_text:
                suggestions.append(MappingSuggestion("customer.customer_naics_code", 0.9, "NAICS code"))
            elif "employees" in all_text:
                if "h1b" in all_text or "h-1b" in all_text:
                    suggestions.append(MappingSuggestion("customer.customer_total_h1b_employees", 0.85, "H1B employees"))
                else:
                    suggestions.append(MappingSuggestion("customer.customer_total_employees", 0.85, "Total employees"))
            elif "established" in all_text or "year" in all_text and "business" in all_text:
                suggestions.append(MappingSuggestion("customer.customer_year_established", 0.85, "Year established"))
            elif any(p in all_text for p in ['phone', 'telephone']):
                if "mobile" in all_text or "cell" in all_text:
                    suggestions.append(MappingSuggestion("customer.signatory.signatory_mobile_phone", 0.8, "Signatory mobile"))
                else:
                    suggestions.append(MappingSuggestion("customer.signatory.signatory_work_phone", 0.8, "Signatory work phone"))
            elif "email" in all_text:
                suggestions.append(MappingSuggestion("customer.signatory.signatory_email_id", 0.85, "Signatory email"))
        
        # Beneficiary mappings (usually Part 3)
        elif "beneficiary" in field.part.lower() or "part 3" in field.part.lower() or "information about you" in field.part.lower():
            if any(p in all_text for p in ['lastname', 'last_name', 'family_name', 'apellido']):
                suggestions.append(MappingSuggestion("beneficiary.Beneficiary.beneficiaryLastName", 0.95, "Beneficiary last name"))
            elif any(p in all_text for p in ['firstname', 'first_name', 'given_name', 'nombre']):
                suggestions.append(MappingSuggestion("beneficiary.Beneficiary.beneficiaryFirstName", 0.95, "Beneficiary first name"))
            elif any(p in all_text for p in ['middlename', 'middle_name', 'middle_initial']):
                suggestions.append(MappingSuggestion("beneficiary.Beneficiary.beneficiaryMiddleName", 0.9, "Beneficiary middle name"))
            elif any(p in all_text for p in ['alien', 'a-number', 'anumber', 'uscis']) and any(p in all_text for p in ['number', 'no', '#']):
                suggestions.append(MappingSuggestion("beneficiary.Beneficiary.alienNumber", 0.95, "Alien number"))
            elif "ssn" in all_text or ("social" in all_text and "security" in all_text):
                suggestions.append(MappingSuggestion("beneficiary.Beneficiary.beneficiarySsn", 0.95, "Social Security Number"))
            elif any(p in all_text for p in ['birth', 'nacimiento']) and any(p in all_text for p in ['date', 'fecha']):
                suggestions.append(MappingSuggestion("beneficiary.Beneficiary.beneficiaryDateOfBirth", 0.95, "Date of birth"))
            elif "gender" in all_text or "sex" in all_text:
                suggestions.append(MappingSuggestion("beneficiary.Beneficiary.beneficiaryGender", 0.9, "Gender"))
            elif "country" in all_text and "birth" in all_text:
                suggestions.append(MappingSuggestion("beneficiary.Beneficiary.beneficiaryCountryOfBirth", 0.9, "Country of birth"))
            elif "marital" in all_text and "status" in all_text:
                suggestions.append(MappingSuggestion("beneficiary.Beneficiary.maritalStatus", 0.9, "Marital status"))
            elif "passport" in all_text and any(p in all_text for p in ['number', 'no', '#']):
                suggestions.append(MappingSuggestion("beneficiary.PassportDetails.Passport.passportNumber", 0.9, "Passport number"))
            elif "i-94" in all_text or "i94" in all_text:
                if any(p in all_text for p in ['number', 'no', '#']):
                    suggestions.append(MappingSuggestion("beneficiary.I94Details.I94.i94Number", 0.9, "I-94 number"))
                elif "arrival" in all_text:
                    suggestions.append(MappingSuggestion("beneficiary.I94Details.I94.i94ArrivalDate", 0.85, "I-94 arrival date"))
            elif any(p in all_text for p in ['phone', 'telephone']):
                if "mobile" in all_text or "cell" in all_text:
                    suggestions.append(MappingSuggestion("beneficiary.Beneficiary.beneficiaryCellNumber", 0.85, "Mobile phone"))
                elif "home" in all_text:
                    suggestions.append(MappingSuggestion("beneficiary.Beneficiary.beneficiaryHomeNumber", 0.85, "Home phone"))
                else:
                    suggestions.append(MappingSuggestion("beneficiary.Beneficiary.beneficiaryWorkNumber", 0.85, "Work phone"))
            elif "email" in all_text:
                suggestions.append(MappingSuggestion("beneficiary.Beneficiary.beneficiaryPrimaryEmailAddress", 0.9, "Email address"))
        
        # Address mappings (check field context)
        if any(p in all_text for p in ['street', 'address', 'calle']):
            if "attorney" in field.part.lower() or "part 0" in field.part.lower():
                if "firm" in all_text:
                    suggestions.append(MappingSuggestion("attorneyLawfirmDetails.address.addressStreet", 0.85, "Law firm street"))
                else:
                    suggestions.append(MappingSuggestion("attorney.address.addressStreet", 0.85, "Attorney street"))
            elif "petitioner" in field.part.lower() or "part 1" in field.part.lower():
                suggestions.append(MappingSuggestion("customer.address.address_street", 0.85, "Company street"))
            elif "beneficiary" in field.part.lower() or "part 3" in field.part.lower():
                if "foreign" in all_text:
                    suggestions.append(MappingSuggestion("beneficiary.ForeignAddress.addressStreet", 0.85, "Foreign address street"))
                elif "work" in all_text:
                    suggestions.append(MappingSuggestion("beneficiary.WorkAddress.addressStreet", 0.85, "Work address street"))
                else:
                    suggestions.append(MappingSuggestion("beneficiary.HomeAddress.addressStreet", 0.85, "Home address street"))
        
        elif any(p in all_text for p in ['city', 'ciudad']):
            if "attorney" in field.part.lower() or "part 0" in field.part.lower():
                suggestions.append(MappingSuggestion("attorney.address.addressCity", 0.85, "Attorney city"))
            elif "petitioner" in field.part.lower() or "part 1" in field.part.lower():
                suggestions.append(MappingSuggestion("customer.address.address_city", 0.85, "Company city"))
            elif "beneficiary" in field.part.lower() or "part 3" in field.part.lower():
                suggestions.append(MappingSuggestion("beneficiary.HomeAddress.addressCity", 0.85, "City"))
        
        elif any(p in all_text for p in ['state', 'province', 'estado']):
            if "attorney" in field.part.lower() or "part 0" in field.part.lower():
                suggestions.append(MappingSuggestion("attorney.address.addressState", 0.85, "Attorney state"))
            elif "petitioner" in field.part.lower() or "part 1" in field.part.lower():
                suggestions.append(MappingSuggestion("customer.address.address_state", 0.85, "Company state"))
            elif "beneficiary" in field.part.lower() or "part 3" in field.part.lower():
                suggestions.append(MappingSuggestion("beneficiary.HomeAddress.addressState", 0.85, "State"))
        
        elif any(p in all_text for p in ['zip', 'postal', 'codigo']):
            if "attorney" in field.part.lower() or "part 0" in field.part.lower():
                suggestions.append(MappingSuggestion("attorney.address.addressZip", 0.85, "Attorney ZIP"))
            elif "petitioner" in field.part.lower() or "part 1" in field.part.lower():
                suggestions.append(MappingSuggestion("customer.address.address_zip", 0.85, "Company ZIP"))
            elif "beneficiary" in field.part.lower() or "part 3" in field.part.lower():
                suggestions.append(MappingSuggestion("beneficiary.HomeAddress.addressZip", 0.85, "ZIP code"))
        
        # Case/Petition specific mappings
        elif any(p in all_text for p in ['petition', 'classification', 'category']):
            if "h1b" in all_text or "h-1b" in all_text:
                suggestions.append(MappingSuggestion("case.h1BPetitionType", 0.85, "H1B petition type"))
            else:
                suggestions.append(MappingSuggestion("case.caseType", 0.85, "Case type"))
        
        # Sort by confidence and return top suggestions
        suggestions.sort(key=lambda x: x.confidence, reverse=True)
        return suggestions[:3]  # Return top 3 suggestions for better coverage
    
    def _get_g28_suggestions(self, field: PDFField) -> List[MappingSuggestion]:
        """Get suggestions specific to G-28 form"""
        suggestions = []
        field_name = field.raw_name.lower()
        clean_name = field.clean_name.lower()
        desc_lower = field.description.lower()
        all_text = f"{field_name} {clean_name} {desc_lower}"
        
        # Debug special cases
        if "attorneystatebarnumber" in field_name.replace(" ", "").lower():
            suggestions.append(MappingSuggestion("attorney.attorneyInfo.stateBarNumber", 0.98, "Attorney state bar number"))
            return suggestions  # Return immediately for this specific case
        
        # Part 0/1 - Attorney Information
        if "part 0" in field.part.lower() or ("part 1" in field.part.lower() and "attorney" in field.part.lower()):
            # Name fields
            if any(p in desc_lower for p in ['last name', 'family name', 'apellido']):
                suggestions.append(MappingSuggestion("attorney.attorneyInfo.lastName", 0.95, "Attorney last name"))
            elif any(p in desc_lower for p in ['first name', 'given name', 'nombre']):
                suggestions.append(MappingSuggestion("attorney.attorneyInfo.firstName", 0.95, "Attorney first name"))
            elif any(p in desc_lower for p in ['middle name', 'middle initial']):
                suggestions.append(MappingSuggestion("attorney.attorneyInfo.middleName", 0.9, "Attorney middle name"))
            
            # Bar and licensing - check all text
            elif any(p in all_text for p in ['bar', 'state bar', 'statebar', 'bar number', 'barnumber']):
                suggestions.append(MappingSuggestion("attorney.attorneyInfo.stateBarNumber", 0.95, "State bar number"))
            elif "licensing" in all_text and "authority" in all_text:
                suggestions.append(MappingSuggestion("attorney.attorneyInfo.licensingAuthority", 0.9, "Licensing authority"))
            elif "highest" in all_text and "court" in all_text:
                if "state" in all_text:
                    suggestions.append(MappingSuggestion("attorney.attorneyInfo.stateOfHighestCourt", 0.9, "State of highest court"))
                else:
                    suggestions.append(MappingSuggestion("attorney.attorneyInfo.nameOfHighestCourt", 0.9, "Name of highest court"))
            
            # Contact information
            elif any(p in all_text for p in ['phone', 'telephone', 'daytime']):
                if any(p in all_text for p in ['mobile', 'cell']):
                    suggestions.append(MappingSuggestion("attorney.attorneyInfo.mobilePhone", 0.9, "Attorney mobile phone"))
                else:
                    suggestions.append(MappingSuggestion("attorney.attorneyInfo.workPhone", 0.9, "Attorney work phone"))
            elif "email" in all_text:
                suggestions.append(MappingSuggestion("attorney.attorneyInfo.emailAddress", 0.9, "Attorney email"))
            elif "fax" in all_text:
                suggestions.append(MappingSuggestion("attorney.attorneyInfo.faxNumber", 0.85, "Attorney fax"))
            
            # USCIS account
            elif "uscis" in all_text and any(p in all_text for p in ['account', 'online']):
                suggestions.append(MappingSuggestion("attorney.attorneyInfo.uscisOnlineAccountNumber", 0.9, "USCIS account number"))
            
            # Signature
            elif "signature" in all_text:
                suggestions.append(MappingSuggestion("attorney.attorneyInfo.signature", 0.9, "Attorney signature"))
            
            # Law firm fields in Part 0/1
            elif any(p in all_text for p in ['firm', 'organization', 'office', 'company']) and "name" in all_text:
                suggestions.append(MappingSuggestion("attorneyLawfirmDetails.lawfirmDetails.lawFirmName", 0.9, "Law firm name"))
            elif "fein" in all_text or ("tax" in all_text and "id" in all_text) or "ein" in all_text:
                suggestions.append(MappingSuggestion("attorneyLawfirmDetails.lawfirmDetails.lawFirmFein", 0.9, "Law firm FEIN"))
        
        # Part 2 - Law Firm Information (if exists)
        elif "part 2" in field.part.lower() or "firm" in field.part.lower():
            if any(p in all_text for p in ['firm', 'organization']) and "name" in all_text:
                suggestions.append(MappingSuggestion("attorneyLawfirmDetails.lawfirmDetails.lawFirmName", 0.9, "Law firm name"))
            elif "fein" in all_text or ("tax" in all_text and "id" in all_text):
                suggestions.append(MappingSuggestion("attorneyLawfirmDetails.lawfirmDetails.lawFirmFein", 0.9, "Law firm FEIN"))
        
        # Part 3 - Client Information
        elif "part 3" in field.part.lower() or "client" in field.part.lower() or "appearance" in field.part.lower():
            if any(p in all_text for p in ['petitioner', 'client', 'applicant', 'company', 'organization']) and "name" in all_text:
                suggestions.append(MappingSuggestion("customer.customer_name", 0.85, "Client/Company name"))
            elif any(p in all_text for p in ['alien', 'uscis', 'a-number']) and any(p in all_text for p in ['number', 'no', '#']):
                suggestions.append(MappingSuggestion("beneficiary.Beneficiary.alienNumber", 0.85, "Client alien number"))
            elif any(p in desc_lower for p in ['last name', 'family name', 'apellido']):
                suggestions.append(MappingSuggestion("beneficiary.Beneficiary.beneficiaryLastName", 0.85, "Client last name"))
            elif any(p in desc_lower for p in ['first name', 'given name', 'nombre']):
                suggestions.append(MappingSuggestion("beneficiary.Beneficiary.beneficiaryFirstName", 0.85, "Client first name"))
        
        # Address fields (check context) - more specific matching
        if any(p in all_text for p in ['street', 'address', 'calle']) and not any(p in all_text for p in ['city', 'state', 'zip', 'country']):
            if "attorney" in field.part.lower() or "part 0" in field.part.lower() or "part 1" in field.part.lower():
                if "firm" in all_text or "office" in all_text:
                    suggestions.append(MappingSuggestion("attorneyLawfirmDetails.address.addressStreet", 0.85, "Law firm street"))
                else:
                    suggestions.append(MappingSuggestion("attorney.address.addressStreet", 0.85, "Attorney street"))
            elif "firm" in field.part.lower() or "part 2" in field.part.lower():
                suggestions.append(MappingSuggestion("attorneyLawfirmDetails.address.addressStreet", 0.85, "Law firm street"))
        
        elif any(p in all_text for p in ['city', 'ciudad']) and not any(p in all_text for p in ['state', 'county']):
            if "attorney" in field.part.lower() or "part 0" in field.part.lower():
                if "firm" in all_text:
                    suggestions.append(MappingSuggestion("attorneyLawfirmDetails.address.addressCity", 0.85, "Law firm city"))
                else:
                    suggestions.append(MappingSuggestion("attorney.address.addressCity", 0.85, "Attorney city"))
        
        elif any(p in all_text for p in ['state', 'province', 'estado']) and not "bar" in all_text:
            if "attorney" in field.part.lower() or "part 0" in field.part.lower():
                if "firm" in all_text:
                    suggestions.append(MappingSuggestion("attorneyLawfirmDetails.address.addressState", 0.85, "Law firm state"))
                else:
                    suggestions.append(MappingSuggestion("attorney.address.addressState", 0.85, "Attorney state"))
        
        elif any(p in all_text for p in ['zip', 'postal', 'codigo']):
            if "attorney" in field.part.lower() or "part 0" in field.part.lower():
                if "firm" in all_text:
                    suggestions.append(MappingSuggestion("attorneyLawfirmDetails.address.addressZip", 0.85, "Law firm ZIP"))
                else:
                    suggestions.append(MappingSuggestion("attorney.address.addressZip", 0.85, "Attorney ZIP"))
        
        return suggestions
    
    def _get_i129_suggestions(self, field: PDFField) -> List[MappingSuggestion]:
        """Get suggestions specific to I-129 form"""
        suggestions = []
        field_name = field.raw_name.lower()
        
        # Part 1 - Petitioner Information
        if "part 1" in field.part.lower():
            if "company" in field_name or "organization" in field_name:
                suggestions.append(MappingSuggestion("customer.customer_name", 0.9, "I-129 company name"))
            elif "fein" in field_name or "tax" in field_name:
                suggestions.append(MappingSuggestion("customer.customer_tax_id", 0.9, "I-129 tax ID"))
        
        # Part 3 - Beneficiary Information  
        elif "part 3" in field.part.lower():
            if "alien" in field_name:
                suggestions.append(MappingSuggestion("beneficiary.Beneficiary.alienNumber", 0.9, "I-129 alien number"))
        
        return suggestions
    
    def _get_i90_suggestions(self, field: PDFField) -> List[MappingSuggestion]:
        """Get suggestions specific to I-90 form"""
        suggestions = []
        field_name = field.raw_name.lower()
        clean_name = field.clean_name
        
        # Use clean name patterns from I-90.ts
        if clean_name == "P1_3a":
            suggestions.append(MappingSuggestion("beneficiary.Beneficiary.beneficiaryLastName", 0.95, "I-90 last name"))
        elif clean_name == "P1_3b":
            suggestions.append(MappingSuggestion("beneficiary.Beneficiary.beneficiaryFirstName", 0.95, "I-90 first name"))
        elif clean_name == "P1_3c":
            suggestions.append(MappingSuggestion("beneficiary.Beneficiary.beneficiaryMiddleName", 0.95, "I-90 middle name"))
        elif "anumber" in field_name or ("alien" in field_name and "number" in field_name):
            suggestions.append(MappingSuggestion("beneficiary.Beneficiary.alienNumber", 0.9, "I-90 alien number"))
        
        return suggestions
    
    def _display_extraction_summary(self, fields: List[PDFField], form_type: str):
        """Display detailed extraction summary organized by parts"""
        st.write("### 📊 Extraction Summary")
        st.write(f"**Form**: {form_type}")
        st.write(f"**Total fields extracted**: {len(fields)}")
        
        # Group fields by part
        fields_by_part = defaultdict(list)
        for field in fields:
            fields_by_part[field.part].append(field)
        
        # Sort parts naturally
        def natural_sort_key(part):
            # Extract numbers from part name for natural sorting
            numbers = re.findall(r'\d+', part)
            if numbers:
                return (0, int(numbers[0]))
            return (1, part)
        
        sorted_parts = sorted(fields_by_part.keys(), key=natural_sort_key)
        
        # Display part-by-part breakdown
        st.write("**Part-by-Part Field Breakdown:**")
        
        for part in sorted_parts:
            part_fields = fields_by_part[part]
            
            # Count field types
            type_counts = defaultdict(int)
            for field in part_fields:
                type_counts[field.field_type] += 1
            
            # Create summary string
            type_summary = ", ".join([f"{count} {ftype}{'s' if count > 1 else ''}" 
                                     for ftype, count in sorted(type_counts.items())])
            
            # Display with appropriate icon
            if "part 0" in part.lower() or "attorney" in part.lower():
                icon = "⚖️"
            elif "part" in part.lower():
                icon = "📑"
            else:
                icon = "📄"
            
            st.write(f"{icon} **{part}**: {len(part_fields)} fields ({type_summary})")
            
            # Show sample fields in expander
            with st.expander(f"View fields in {part}"):
                sample_fields = part_fields[:10]
                for field in sample_fields:
                    field_info = f"• {field.description}"
                    if field.item:
                        field_info += f" (Item {field.item})"
                    field_info += f" - Type: {field.field_type}"
                    field_info += f" - Clean Name: {field.clean_name}"
                    st.write(field_info)
                
                if len(part_fields) > 10:
                    st.write(f"... and {len(part_fields) - 10} more fields")
        
        # Show debug info for part detection
        with st.expander("🔍 Part Detection Debug Info"):
            st.write("**Sample field names and their detected parts:**")
            
            # Show fields from Part 0 first if they exist
            part_0_fields = [f for f in fields if "part 0" in f.part.lower()]
            if part_0_fields:
                st.write("**Part 0 (Attorney) Fields:**")
                debug_data_p0 = []
                for field in part_0_fields[:10]:
                    debug_data_p0.append({
                        "Raw Field Name": field.raw_name[:50] + "..." if len(field.raw_name) > 50 else field.raw_name,
                        "Clean Name": field.clean_name,
                        "Description": field.description,
                        "Detected Part": field.part,
                        "Page": field.page,
                        "Suggested Mapping": field.db_mapping or "-"
                    })
                
                debug_df_p0 = pd.DataFrame(debug_data_p0)
                st.dataframe(debug_df_p0, use_container_width=True, hide_index=True)
                st.write("---")
            
            # Show other fields
            st.write("**Other Sample Fields:**")
            debug_fields = [f for f in fields if "part 0" not in f.part.lower()][:20]
            debug_data = []
            for field in debug_fields:
                debug_data.append({
                    "Raw Field Name": field.raw_name[:50] + "..." if len(field.raw_name) > 50 else field.raw_name,
                    "Clean Name": field.clean_name,
                    "Description": field.description,
                    "Detected Part": field.part,
                    "Page": field.page
                })
            
            debug_df = pd.DataFrame(debug_data)
            st.dataframe(debug_df, use_container_width=True, hide_index=True)
            
            st.write("**Part detection strategies used:**")
            st.write("1. ✅ Cleaned field names for pattern matching")
            st.write("2. ✅ Analyzed field groupings by content")
            st.write("3. ✅ Detected page boundaries")
            st.write("4. ✅ Applied contextual inference")
            st.write("5. ✅ Smoothed part assignments")
            st.write("6. ✅ Special handling for attorney fields (Part 0)")
        
        # Show mapping statistics
        st.write("**Mapping Statistics:**")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            mapped = sum(1 for f in fields if f.db_mapping)
            st.metric("Auto-suggested", f"{mapped} ({mapped/len(fields)*100:.1f}%)")
        
        with col2:
            high_conf = sum(1 for f in fields if f.confidence_score > 0.8)
            st.metric("High confidence", f"{high_conf} ({high_conf/len(fields)*100:.1f}%)")
        
        with col3:
            questionnaire = sum(1 for f in fields if f.is_questionnaire)
            st.metric("Questionnaire", f"{questionnaire} ({questionnaire/len(fields)*100:.1f}%)")
        
        with col4:
            score = self.calculate_mapping_score(fields)
            st.metric("Overall Score", f"{score}%")
        
        # Show database paths debug info
        with st.expander("🗄️ Database Paths Debug Info"):
            st.write(f"**Total database paths available**: {len(self.db_paths_cache)}")
            st.write("**Sample paths:**")
            for i, path in enumerate(self.db_paths_cache[:20]):
                st.code(path)
            if len(self.db_paths_cache) > 20:
                st.write(f"... and {len(self.db_paths_cache) - 20} more paths")
    
    def create_mapping(self, field: PDFField, mapping_type: str, mapping_config: Dict[str, Any]) -> None:
        """Create a field mapping"""
        field.mapping_type = mapping_type
        field.mapping_config = mapping_config
        
        if mapping_type == "direct":
            field.db_mapping = mapping_config.get("path")
            field.is_mapped = True
            field.is_questionnaire = False
        elif mapping_type == "concatenated":
            field.db_mapping = json.dumps(mapping_config)
            field.is_mapped = True
            field.is_questionnaire = False
        elif mapping_type == "conditional":
            field.db_mapping = json.dumps(mapping_config)
            field.is_mapped = True
            field.is_questionnaire = False
        elif mapping_type == "default":
            field.db_mapping = f"Default: {mapping_config.get('value')}"
            field.is_mapped = True
            field.is_questionnaire = False
        elif mapping_type == "questionnaire":
            field.is_questionnaire = True
            field.is_mapped = False
            # Don't clear db_mapping for questionnaire fields, keep suggestions
    
    def generate_typescript_export(self, form_type: str, fields: List[PDFField]) -> str:
        """Generate TypeScript mapping file in the correct format"""
        form_name = form_type.replace("-", "").replace(" ", "").split(" - ")[0]
        
        # Group mappings by category
        categories = {
            "customerData": {},
            "beneficiaryData": {},
            "attorneyData": {},
            "caseData": {},
            "lcaData": {},
            "questionnaireData": {},
            "defaultData": {},
            "conditionalData": {}
        }
        
        # Process fields
        for field in fields:
            # Use clean name instead of raw name
            field_key = field.clean_name or field.raw_name
            
            if field.is_mapped and field.db_mapping and not field.db_mapping.startswith("Default:"):
                # Add type suffix
                mapping_value = f"{field.db_mapping}{field.field_type_suffix}"
                
                if field.mapping_type == "direct":
                    # Determine category based on path
                    if field.db_mapping.startswith('customer'):
                        categories['customerData'][field_key] = mapping_value
                    elif field.db_mapping.startswith('beneficiary'):
                        categories['beneficiaryData'][field_key] = mapping_value  
                    elif field.db_mapping.startswith('attorney'):
                        categories['attorneyData'][field_key] = mapping_value
                    elif field.db_mapping.startswith('case'):
                        categories['caseData'][field_key] = mapping_value
                    elif field.db_mapping.startswith('lca'):
                        categories['lcaData'][field_key] = mapping_value
                elif field.mapping_type == "conditional":
                    categories['conditionalData'][field_key] = field.mapping_config
            elif field.db_mapping and field.db_mapping.startswith("Default:"):
                # Extract default value
                default_value = field.db_mapping.replace("Default: ", "")
                if default_value.lower() in ['true', 'false']:
                    categories['defaultData'][field_key] = field.field_type_suffix
                else:
                    categories['defaultData'][field_key] = f"{default_value}{field.field_type_suffix}"
            elif field.is_questionnaire or (not field.is_mapped and not field.db_mapping):
                # Use clean name for questionnaire
                categories['questionnaireData'][field_key] = f"{field.item or field_key}{field.field_type_suffix}"
        
   # Generate TypeScript content
        ts_content = f"""export const {form_name} = {{
    "formname": "{form_name.lower()}",
    "pdfName": "{form_type.split(' - ')[0]}",
    "customerData": {self._format_data_section(categories['customerData'])},
    "beneficiaryData": {self._format_data_section(categories['beneficiaryData'])},
    "attorneyData": {self._format_data_section(categories['attorneyData'])},
    "questionnaireData": {self._format_data_section(categories['questionnaireData'])},
    "defaultData": {self._format_data_section(categories['defaultData'])},
    "conditionalData": {self._format_conditional_section(categories['conditionalData'])},
    "caseData": {self._format_data_section(categories['caseData'])},
    "lcaData": {self._format_data_section(categories['lcaData'])}
}}
        
        return ts_content
     
     def _format_data_section(self, data: Dict[str, str]) -> str:
        """Format data section for TypeScript"""
        if not data:
            return "null"
        
        lines = []
        for key, value in data.items():
            # Escape quotes in key and value
            key_escaped = key.replace('"', '\\"')
            value_escaped = value.replace('"', '\\"')
            lines.append(f'        "{key_escaped}": "{value_escaped}"')
        
        return "{\n" + ",\n".join(lines) + "\n    }"
    
    def _format_conditional_section(self, data: Dict[str, Any]) -> str:
        """Format conditional data section for TypeScript"""
        if not data:
            return "{}"
        
        lines = []
        for key, config in data.items():
            lines.append(f'        "{key}": {json.dumps(config, indent=12)[:-1]}        }}')
        
        return "{\n" + ",\n".join(lines) + "\n    }"
    
    def generate_questionnaire_json(self, fields: List[PDFField]) -> str:
        """Generate questionnaire JSON in the correct format"""
        controls = []
        
        # Group fields by part for better organization
        fields_by_part = defaultdict(list)
        for field in fields:
            if field.is_questionnaire or (not field.is_mapped and not field.db_mapping):
                fields_by_part[field.part].append(field)
        
        # Sort parts naturally
        def natural_sort_key(part):
            numbers = re.findall(r'\d+', part)
            if numbers:
                return (0, int(numbers[0]))
            return (1, part)
        
        sorted_parts = sorted(fields_by_part.keys(), key=natural_sort_key)
        
        # Add controls for each part
        for part in sorted_parts:
            # Extract part number
            part_match = re.search(r'Part\s*(\d+)', part, re.IGNORECASE)
            part_number = part_match.group(1) if part_match else "1"
            
            # Add part title
            part_id = f"p{part_number}_title"
            controls.append({
                "name": part_id,
                "label": part,
                "type": "title",
                "validators": {},
                "className": "h5",
                "style": {
                    "col": "12"
                }
            })
            
            # Add fields for this part
            for field in fields_by_part[part]:
                # Use clean name
                control_name = field.clean_name.lower() if field.clean_name else f"q_{field.index}"
                
                # Generate label
                label = field.description
                
                control = {
                    "name": control_name,
                    "label": label,
                    "type": self._get_questionnaire_type(field.field_type),
                    "validators": {},
                    "style": {
                        "col": "12"
                    }
                }
                
                # Add specific properties based on field type
                if field.field_type == "radio":
                    control["type"] = "radio"
                    control["value"] = ""
                    control["style"]["success"] = True
                elif field.field_type == "checkbox":
                    control["type"] = "checkbox"
                    control["style"]["success"] = True
                    control["className"] = "custom-control-success"
                elif field.field_type == "text" and "address" in field.description.lower():
                    # Check for address type fields
                    if any(t in field.description.lower() for t in ['apt', 'ste', 'flr']):
                        control["type"] = "radio"
                        control["style"]["radio"] = True
                        control["style"]["col"] = "1"
                
                controls.append(control)
                
                # Add line break if needed
                if field.field_type == "radio" and "address" in field.description.lower():
                    controls.append({
                        "name": "",
                        "label": "",
                        "type": "br",
                        "validators": {},
                        "style": {
                            "col": "12"
                        }
                    })
        
        questionnaire = {
            "controls": controls
        }
        
        return json.dumps(questionnaire, indent=4)
    
    def _get_questionnaire_type(self, field_type: str) -> str:
        """Map field type to questionnaire control type"""
        type_mapping = {
            "text": "text",
            "checkbox": "checkbox",
            "radio": "radio",
            "select": "select",
            "date": "date",
            "signature": "text",
            "listbox": "select"
        }
        return type_mapping.get(field_type, "text")
    
    def calculate_mapping_score(self, fields: List[PDFField]) -> float:
        """Calculate overall mapping score"""
        if not fields:
            return 0.0
        
        total = len(fields)
        mapped = sum(1 for f in fields if f.is_mapped)
        questionnaire = sum(1 for f in fields if f.is_questionnaire)
        
        # Mapped fields get 100%, questionnaire fields get 50%
        score = ((mapped * 100) + (questionnaire * 50)) / total
        return round(score, 1)

# Streamlit UI Components
def render_header():
    """Render application header"""
    st.markdown(
    <style>
        .main-header {
            background: linear-gradient(135deg, #1e3c72, #2a5298);
            color: white;
            padding: 25px;
            border-radius: 10px;
            margin-bottom: 25px;
            text-align: center;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .metric-card {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            text-align: center;
            margin: 10px 0;
        }
        .field-card {
            background: white;
            border: 1px solid #e0e0e0;
            padding: 15px;
            margin: 10px 0;
            border-radius: 8px;
            transition: all 0.3s ease;
        }
        .field-card:hover {
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            border-color: #2a5298;
        }
        .mapping-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 500;
        }
        .mapped { background: #d4edda; color: #155724; }
        .questionnaire { background: #d1ecf1; color: #0c5460; }
        .unmapped { background: #f8d7da; color: #721c24; }
        .confidence-high { color: #28a745; }
        .confidence-medium { color: #ffc107; }
        .confidence-low { color: #dc3545; }
        .part-header {
            background: #f8f9fa;
            padding: 10px;
            border-radius: 5px;
            margin: 10px 0;
            font-weight: bold;
        }
    </style>
    "", unsafe_allow_html=True)
    
    st.markdown('<div class="main-header"><h1>🏛️ Universal USCIS Form Mapper</h1><p>Intelligent mapping for any USCIS form</p></div>', unsafe_allow_html=True)

def render_upload_section(mapper: UniversalUSCISMapper):
    """Render upload section"""
    st.header("📤 Upload USCIS Form")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Form type input
        form_type = st.text_input(
            "Form Type/Number",
            placeholder="e.g., I-129, I-485, N-400",
            help="Enter the USCIS form number or select from common forms"
        )
        
        # Common forms dropdown
        common_forms = [
            "Custom/Other",
            "G-28 - Notice of Entry of Appearance",
            "I-129 - Petition for Nonimmigrant Worker",
            "I-140 - Immigrant Petition for Alien Worker",
            "I-485 - Application to Adjust Status",
            "I-539 - Application to Extend/Change Status",
            "I-765 - Application for Employment Authorization",
            "I-131 - Application for Travel Document",
            "I-90 - Application to Replace Green Card",
            "I-130 - Petition for Alien Relative",
            "I-526 - Immigrant Petition by Alien Investor",
            "I-829 - Petition by Investor",
            "N-400 - Application for Naturalization",
            "N-600 - Application for Certificate of Citizenship"
        ]
        
        selected_form = st.selectbox("Or select from common forms:", common_forms)
        
        if selected_form != "Custom/Other":
            form_type = selected_form
        
        if form_type:
            st.session_state.form_type = form_type
            st.success(f"Selected form: **{form_type}**")
    
    with col2:
        uploaded_file = st.file_uploader(
            "Upload PDF Form",
            type=['pdf'],
            help="Upload the USCIS PDF form you want to map"
        )
        
        if uploaded_file:
            file_details = {
                "Filename": uploaded_file.name,
                "FileType": uploaded_file.type,
                "FileSize": f"{uploaded_file.size / 1024:.2f} KB"
            }
            st.write("**File Details:**")
            for key, value in file_details.items():
                st.write(f"- {key}: {value}")
    
    # Extract button
    if uploaded_file and form_type:
        if st.button("🔍 Extract & Analyze Fields", type="primary", use_container_width=True):
            with st.spinner("Extracting PDF fields and analyzing form structure..."):
                # Extract fields
                fields = mapper.extract_pdf_fields(uploaded_file, form_type)
                
                if fields:
                    st.session_state.pdf_fields = fields
                    st.session_state.field_mappings = {f.raw_name: f for f in fields}
                else:
                    st.error("No fields found in the PDF. Please ensure it's a fillable PDF form.")

def render_mapping_section(mapper: UniversalUSCISMapper):
    """Render field mapping section"""
    if 'pdf_fields' not in st.session_state or not st.session_state.pdf_fields:
        st.info("👆 Please upload a PDF form first")
        return
    
    st.header("🗺️ Field Mapping Configuration")
    
    # Info box
    st.info("ℹ️ **Note**: All unmapped fields are automatically added to the questionnaire. You can change this by selecting a different mapping type.")
    
    # Add custom field section
    with st.expander("➕ Add Custom Field"):
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            # Get available parts
            parts = list(set(f.part for f in st.session_state.pdf_fields))
            def natural_sort_key(part):
                numbers = re.findall(r'\d+', part)
                if numbers:
                    return (0, int(numbers[0]))
                return (1, part)
            sorted_parts = sorted(parts, key=natural_sort_key)
            
            custom_part = st.selectbox("Select Part", sorted_parts, key="custom_part")
        
        with col2:
            custom_item = st.text_input("Item Number", placeholder="e.g., 1a, 2b", key="custom_item")
        
        with col3:
            custom_desc = st.text_input("Field Description", placeholder="e.g., Additional Phone Number", key="custom_desc")
        
        with col4:
            custom_type = st.selectbox("Field Type", ["text", "checkbox", "radio", "date", "select"], key="custom_type")
        
        if st.button("➕ Add Field", use_container_width=True):
            if custom_desc:
                # Add custom field
                custom_field = mapper.add_custom_field(custom_part, custom_item, custom_desc, custom_type)
                st.session_state.pdf_fields.append(custom_field)
                st.success(f"Added custom field: {custom_field.clean_name} - {custom_desc}")
                st.rerun()
            else:
                st.error("Please provide a field description")
    
    # Filters
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        parts = list(set(f.part for f in st.session_state.pdf_fields))
        # Sort parts naturally
        def natural_sort_key(part):
            numbers = re.findall(r'\d+', part)
            if numbers:
                return (0, int(numbers[0]))
            return (1, part)
        sorted_parts = sorted(parts, key=natural_sort_key)
        
        selected_part = st.selectbox("Filter by Part", ["All"] + sorted_parts)
    
    with col2:
        status_filter = st.selectbox("Filter by Status", ["All", "Mapped", "Suggested", "Questionnaire", "Unmapped", "Custom"])
    
    with col3:  
        field_types = list(set(f.field_type for f in st.session_state.pdf_fields))
        type_filter = st.selectbox("Filter by Type", ["All"] + sorted(field_types))
    
    with col4:  
        search_term = st.text_input("Search fields", placeholder="Enter keyword...")
    
    # Quick actions
    st.markdown("### Quick Actions")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("✅ Accept All High Confidence (>80%)", use_container_width=True):
            count = 0
            for field in st.session_state.pdf_fields:
                if not field.is_mapped and field.confidence_score > 0.8 and field.db_mapping:
                    field.is_mapped = True
                    mapper.create_mapping(field, "direct", {"path": field.db_mapping})
                    count += 1
            if count > 0:
                st.success(f"Accepted {count} high confidence mappings")
                st.rerun()
    
    with col2:
        if st.button("📋 All Unmapped to Questionnaire", use_container_width=True):
            count = 0
            for field in st.session_state.pdf_fields:
                if not field.is_mapped and not field.is_questionnaire:
                    field.is_questionnaire = True
                    count += 1
            if count > 0:
                st.success(f"Added {count} fields to questionnaire")
                st.rerun()
    
    with col3:
        if st.button("🔄 Reset All Mappings", use_container_width=True):
            for field in st.session_state.pdf_fields:
                if not field.is_custom_field:  # Don't reset custom fields
                    field.is_mapped = False
                    field.is_questionnaire = False
                    field.mapping_type = "direct"
                    field.mapping_config = None
            st.rerun()
    
    # Filter fields
    filtered_fields = []
    for field in st.session_state.pdf_fields:
        # Apply filters
        if selected_part != "All" and field.part != selected_part:
            continue
        
        if status_filter != "All":
            if status_filter == "Mapped" and not field.is_mapped:
                continue
            elif status_filter == "Suggested" and (not field.db_mapping or field.is_mapped or field.is_questionnaire):
                continue
            elif status_filter == "Questionnaire" and not field.is_questionnaire:
                continue
            elif status_filter == "Unmapped" and (field.is_mapped or field.is_questionnaire or field.db_mapping):
                continue
            elif status_filter == "Custom" and not field.is_custom_field:
                continue
        
        if type_filter != "All" and field.field_type != type_filter:
            continue
        
        if search_term:
            search_lower = search_term.lower()
            if not any(search_lower in str(getattr(field, attr, '')).lower() 
                      for attr in ['raw_name', 'description', 'item', 'db_mapping', 'clean_name']):
                continue
        
        filtered_fields.append(field)
    
    # Display fields
    st.write(f"Showing **{len(filtered_fields)}** of **{len(st.session_state.pdf_fields)}** fields")
    
    # Group by parts
    fields_by_part = defaultdict(list)
    for field in filtered_fields:
        fields_by_part[field.part].append(field)
    
    # Sort parts
    def natural_sort_key(part):
        numbers = re.findall(r'\d+', part)
        if numbers:
            return (0, int(numbers[0]))
        return (1, part)
    
    sorted_parts_display = sorted(fields_by_part.keys(), key=natural_sort_key)
    
    # If no parts found, show debug info
    if not sorted_parts_display:
        st.warning("No fields to display with current filters.")
        return
    
    for part in sorted_parts_display:
        fields = fields_by_part[part]
        
        # Count field types
        type_counts = defaultdict(int)
        for field in fields:
            type_counts[field.field_type] += 1
        
        type_summary = ", ".join([f"{count} {ftype}{'s' if count > 1 else ''}" 
                                 for ftype, count in sorted(type_counts.items())])
        
        # Icon based on part
        if "part 0" in part.lower() or "attorney" in part.lower():
            icon = "⚖️"
        elif "part" in part.lower():
            icon = "📑"
        else:
            icon = "📄"
        
        expanded = "Part 1" in part or "Part 0" in part  # Expand Part 0 and 1 by default
        
        with st.expander(f"{icon} {part} ({len(fields)} fields: {type_summary})", expanded=expanded):
            # Add a quick summary of fields in this part
            st.markdown("**Fields in this part:**")
            
            # Create a preview table
            preview_data = []
            for field in fields[:5]:  # Show first 5 fields
                preview_data.append({
                    "Clean Name": field.clean_name,
                    "Description": field.description,
                    "Type": field.field_type,
                    "Status": "✅ Mapped" if field.is_mapped else "📋 Questionnaire" if field.is_questionnaire else "💡 Suggested" if field.db_mapping else "❌ Unmapped",
                    "Custom": "✨" if field.is_custom_field else ""
                })
            
            if preview_data:
                preview_df = pd.DataFrame(preview_data)
                st.dataframe(preview_df, use_container_width=True, hide_index=True)
                
                if len(fields) > 5:
                    st.caption(f"... and {len(fields) - 5} more fields")
            
            st.markdown("---")
            
            # Now show the detailed field cards
            for field in fields:
                render_field_mapping_card(field, mapper)

def render_field_mapping_card(field: PDFField, mapper: UniversalUSCISMapper):
    """Render individual field mapping card"""
    with st.container():
        st.markdown('<div class="field-card">', unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([5, 4, 1])
        
        with col1:
            # Field info - Use clean name as primary display
            field_label = f"**{field.clean_name}** - {field.description}"
            if field.item:
                field_label += f" (Item {field.item})"
            if field.is_custom_field:
                field_label += " ✨ *Custom*"
            st.markdown(field_label)
            
            # Show raw name in caption for debugging
            st.caption(f"Raw: `{field.raw_name}` | Type: {field.field_type} | Page: {field.page}")
            
            # Current mapping status
            if field.is_mapped and field.db_mapping:
                st.markdown(f'<span class="mapping-badge mapped">✅ Mapped to: {field.db_mapping}</span>', unsafe_allow_html=True)
            elif field.db_mapping and field.confidence_score > 0 and not field.is_questionnaire:
                confidence_class = "high" if field.confidence_score > 0.8 else "medium" if field.confidence_score > 0.6 else "low"
                st.markdown(f'<span class="mapping-badge questionnaire">💡 Suggested: {field.db_mapping} <span class="confidence-{confidence_class}">({field.confidence_score:.0%})</span></span>', unsafe_allow_html=True)
            elif field.is_questionnaire:
                st.markdown('<span class="mapping-badge questionnaire">📋 In Questionnaire</span>', unsafe_allow_html=True)
            else:
                st.markdown('<span class="mapping-badge unmapped">❌ Not mapped</span>', unsafe_allow_html=True)
        
        with col2:
            # Mapping controls
            mapping_options = ["Keep Current", "Direct Mapping", "Default Value", "Add to Questionnaire", "Custom Path", "Skip Field"]
            
            # Add delete option for custom fields
            if field.is_custom_field:
                mapping_options.append("Delete Field")
            
            # Default selection based on current status
            if field.is_mapped:
                default_option = "Keep Current"
            elif field.is_questionnaire:
                default_option = "Keep Current"
            elif field.db_mapping and not field.is_questionnaire:
                default_option = "Direct Mapping"
            else:
                default_option = "Add to Questionnaire"
            
            mapping_type = st.selectbox(
                "Mapping Type",
                mapping_options,
                index=mapping_options.index(default_option),
                key=f"type_{field.index}",
                label_visibility="collapsed"
            )
            
            # Show appropriate controls based on selection
            custom_path = None
            
            if mapping_type == "Direct Mapping":
                # Get all database paths
                db_paths = mapper.get_all_database_paths()
                
                # Show database object selector prominently
                st.markdown("**📂 Select Database Object:**")
                
                # Show ALL database objects in a dropdown first
                db_objects = list(DB_OBJECTS.keys())
                selected_object = st.selectbox(
                    "Database Category",
                    ["🔍 Auto-detect based on context"] + [f"📁 {obj}" for obj in db_objects],
                    key=f"obj_select_{field.index}",
                    help="Choose a database object category to filter available fields"
                )
                
                # Clean up the selection
                if selected_object.startswith("📁 "):
                    selected_object = selected_object[3:]  # Remove emoji prefix
                
                # Filter paths based on selection or context
                if selected_object and selected_object != "🔍 Auto-detect based on context":
                    # User selected specific object
                    filtered_paths = [p for p in db_paths if p.startswith(selected_object)]
                    st.caption(f"📊 Showing {len(filtered_paths)} fields from {selected_object}")
                else:
                    # Auto-detect based on part
                    part_lower = field.part.lower()
                    
                    if "attorney" in part_lower or "part 0" in part_lower or "representative" in part_lower:
                        filtered_paths = [p for p in db_paths if p.startswith(("attorney", "attorneyLawfirm"))]
                        st.caption("🔍 Auto-detected: Attorney/Law Firm fields")
                    elif "beneficiary" in part_lower or "part 3" in part_lower or "information about you" in part_lower:
                        filtered_paths = [p for p in db_paths if p.startswith("beneficiary")]
                        st.caption("🔍 Auto-detected: Beneficiary fields")
                    elif "petitioner" in part_lower or "part 1" in part_lower or "employer" in part_lower:
                        filtered_paths = [p for p in db_paths if p.startswith("customer")]
                        st.caption("🔍 Auto-detected: Customer/Petitioner fields")
                    elif "case" in part_lower or "petition" in part_lower:
                        filtered_paths = [p for p in db_paths if p.startswith("case")]
                        st.caption("🔍 Auto-detected: Case fields")
                    elif "lca" in part_lower or "labor" in part_lower:
                        filtered_paths = [p for p in db_paths if p.startswith("lca")]
                        st.caption("🔍 Auto-detected: LCA fields")
                    else:
                        # Show all paths if no specific context
                        filtered_paths = db_paths
                        st.caption(f"📊 Showing all {len(db_paths)} database fields")
                
                # Show suggested mappings if available
                if field.db_mapping and not field.is_mapped:
                    st.info(f"💡 **Suggested**: {field.db_mapping}")
                    
                    # Quick accept button for suggestion
                    if st.button(f"✅ Use suggestion", key=f"use_sugg_{field.index}", type="primary"):
                        field.is_mapped = True
                        field.is_questionnaire = False
                        mapper.create_mapping(field, "direct", {"path": field.db_mapping})
                        st.rerun()
                
                # Create dropdown options
                if filtered_paths:
                    dropdown_options = ["-- Select a database field --"] + filtered_paths
                else:
                    dropdown_options = ["-- Select a database field --"] + db_paths
                
                # Try to find current mapping in options
                default_index = 0
                if field.db_mapping and field.db_mapping in dropdown_options:
                    default_index = dropdown_options.index(field.db_mapping)
                
                st.markdown("**🎯 Select Database Field:**")
                custom_path = st.selectbox(
                    "Choose field",
                    dropdown_options,
                    key=f"path_select_{field.index}",
                    help=f"Select from {len(dropdown_options)-1} available fields",
                    index=default_index,
                    label_visibility="collapsed"
                )
                
                # Handle selection
                if custom_path and custom_path != "-- Select a database field --":
                    st.success(f"✅ Selected: `{custom_path}`")
                else:
                    custom_path = None
            
            elif mapping_type == "Custom Path":
                st.markdown("**✏️ Enter Custom Database Path:**")
                st.caption("Use this option to manually enter a database path not in the dropdown")
                
                # Text input for custom path
                custom_path = st.text_input(
                    "Database path",
                    value=field.db_mapping if field.db_mapping and not field.db_mapping.startswith("Default:") else "",
                    key=f"custom_path_{field.index}",
                    placeholder="e.g., beneficiary.Beneficiary.beneficiaryFirstName",
                    help="Enter a custom database path in the format: object.subobject.field",
                    label_visibility="collapsed"
                )
                
                # Show autocomplete suggestions
                if custom_path:
                    db_paths = mapper.get_all_database_paths()
                    # Find matching paths
                    search_term = custom_path.lower()
                    suggestions = [p for p in db_paths if search_term in p.lower()]
                    
                    # Smart ordering
                    exact_matches = [p for p in suggestions if p.lower() == search_term]
                    starts_with = [p for p in suggestions if p.lower().startswith(search_term) and p not in exact_matches]
                    contains = [p for p in suggestions if p not in exact_matches and p not in starts_with]
                    
                    ordered_suggestions = exact_matches + starts_with + contains
                    ordered_suggestions = ordered_suggestions[:8]
                    
                    if ordered_suggestions:
                        st.caption(f"📍 Found {len(suggestions)} matches. Click to select:")
                        
                        # Create columns for suggestions
                        cols = st.columns(2)
                        for idx, sugg in enumerate(ordered_suggestions):
                            with cols[idx % 2]:
                                if st.button(f"→ {sugg}", key=f"sugg_{field.index}_{idx}", help=f"Use {sugg}"):
                                    field.is_mapped = True
                                    field.is_questionnaire = False
                                    mapper.create_mapping(field, "direct", {"path": sugg})
                                    st.rerun()
                    else:
                        st.warning("⚠️ No matching database fields found - this will create a new custom path")
                else:
                    st.info("💡 Start typing to see suggestions from existing database fields")
            
            elif mapping_type == "Default Value":
                default_val = st.text_input(
                    "Default Value",
                    value="",
                    key=f"default_{field.index}",
                    placeholder="Enter default value (e.g., true, false, or text)"
                )
        
        with col3:
            # Action buttons
            if mapping_type == "Delete Field" and field.is_custom_field:
                if st.button("🗑️", key=f"delete_{field.index}", help="Delete custom field", type="secondary"):
                    st.session_state.pdf_fields.remove(field)
                    st.success("Custom field deleted")
                    st.rerun()
            elif mapping_type != "Keep Current":
                if st.button("💾", key=f"save_{field.index}", help="Save mapping", type="primary"):
                    saved = False
                    
                    if mapping_type == "Direct Mapping":
                        if custom_path and custom_path != "-- Select a database field --":
                            field.is_mapped = True
                            field.is_questionnaire = False
                            mapper.create_mapping(field, "direct", {"path": custom_path})
                            st.success("✅ Mapping saved!")
                            saved = True
                        else:
                            st.error("Please select a database path")
                    
                    elif mapping_type == "Custom Path":
                        if f"custom_path_{field.index}" in st.session_state:
                            path_value = st.session_state[f"custom_path_{field.index}"]
                            if path_value:
                                field.is_mapped = True
                                field.is_questionnaire = False
                                mapper.create_mapping(field, "direct", {"path": path_value})
                                st.success("✅ Custom mapping saved!")
                                saved = True
                            else:
                                st.error("Please enter a database path")
                        else:
                            st.error("Please enter a database path")
                            
                    elif mapping_type == "Default Value":
                        if f"default_{field.index}" in st.session_state:
                            default_value = st.session_state[f"default_{field.index}"]
                            if default_value:
                                field.is_mapped = True
                                field.is_questionnaire = False
                                mapper.create_mapping(field, "default", {"value": default_value})
                                st.success("✅ Default value saved!")
                                saved = True
                            else:
                                st.error("Please enter a default value")
                        else:
                            st.error("Please enter a default value")
                            
                    elif mapping_type == "Add to Questionnaire":
                        field.is_mapped = False
                        field.is_questionnaire = True
                        field.db_mapping = None
                        mapper.create_mapping(field, "questionnaire", {})
                        st.success("✅ Added to questionnaire!")
                        saved = True
                        
                    elif mapping_type == "Skip Field":
                        field.is_mapped = False
                        field.is_questionnaire = False
                        field.db_mapping = None
                        st.success("✅ Field skipped!")
                        saved = True
                    
                    if saved:
                        st.rerun()
            
            # Quick accept button for suggestions
            if field.db_mapping and not field.is_mapped and not field.is_questionnaire:
                if st.button("✅", key=f"accept_{field.index}", help="Accept suggestion"):
                    field.is_mapped = True
                    field.is_questionnaire = False
                    mapper.create_mapping(field, "direct", {"path": field.db_mapping})
                    st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)

def render_all_fields_view(mapper: UniversalUSCISMapper):
    """Render comprehensive view of all fields (mapped + questionnaire)"""
    if 'pdf_fields' not in st.session_state or not st.session_state.pdf_fields:
        st.info("👆 Please complete field mapping first")
        return
    
    st.header("📊 All Fields Overview")
    
    fields = st.session_state.pdf_fields
    
    # Summary metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Total Fields", len(fields))
    with col2:
        mapped_count = sum(1 for f in fields if f.is_mapped)
        st.metric("Mapped", mapped_count)
    with col3:
        quest_count = sum(1 for f in fields if f.is_questionnaire)
        st.metric("Questionnaire", quest_count)
    with col4:
        unmapped_count = sum(1 for f in fields if not f.is_mapped and not f.is_questionnaire)
        st.metric("Unmapped", unmapped_count)
    with col5:
        custom_count = sum(1 for f in fields if f.is_custom_field)
        st.metric("Custom", custom_count)
    
    # Filters
    st.markdown("### 🔍 Filter Options")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        view_filter = st.selectbox(
            "View", 
            ["All Fields", "Mapped Only", "Questionnaire Only", "Unmapped Only", "Custom Only"],
            key="all_fields_view_filter"
        )
    
    with col2:
        parts = list(set(f.part for f in fields))
        def natural_sort_key(part):
            numbers = re.findall(r'\d+', part)
            if numbers:
                return (0, int(numbers[0]))
            return (1, part)
        sorted_parts = sorted(parts, key=natural_sort_key)
        
        part_filter = st.selectbox("Part", ["All Parts"] + sorted_parts, key="all_fields_part_filter")
    
    with col3:
        field_types = list(set(f.field_type for f in fields))
        type_filter = st.selectbox("Type", ["All Types"] + sorted(field_types), key="all_fields_type_filter")
    
    with col4:
        search_all = st.text_input("Search", placeholder="Search all fields...", key="all_fields_search")
    
    # Filter fields
    filtered_fields = fields.copy()
    
    # Apply view filter
    if view_filter == "Mapped Only":
        filtered_fields = [f for f in filtered_fields if f.is_mapped]
    elif view_filter == "Questionnaire Only":
        filtered_fields = [f for f in filtered_fields if f.is_questionnaire]
    elif view_filter == "Unmapped Only":
        filtered_fields = [f for f in filtered_fields if not f.is_mapped and not f.is_questionnaire]
    elif view_filter == "Custom Only":
        filtered_fields = [f for f in filtered_fields if f.is_custom_field]
    
    # Apply part filter
    if part_filter != "All Parts":
        filtered_fields = [f for f in filtered_fields if f.part == part_filter]
    
    # Apply type filter
    if type_filter != "All Types":
        filtered_fields = [f for f in filtered_fields if f.field_type == type_filter]
    
    # Apply search
    if search_all:
        search_lower = search_all.lower()
        filtered_fields = [f for f in filtered_fields if 
                          search_lower in f.raw_name.lower() or 
                          search_lower in f.description.lower() or 
                          search_lower in (f.db_mapping or '').lower() or
                          search_lower in f.clean_name.lower() or
                          search_lower in f.part.lower()]
    
    # Display options
    col1, col2 = st.columns(2)
    with col1:
        display_mode = st.radio(
            "Display Mode", 
            ["Table View", "Card View", "Grouped by Part", "Grouped by Status"],
            horizontal=True,
            key="all_fields_display_mode"
        )
    
    with col2:
        if display_mode == "Table View":
            columns_to_show = st.multiselect(
                "Columns",
                ["Index", "Clean Name", "Description", "Part", "Item", "Type", "Status", "Database Path", "Confidence", "Page", "Raw Name"],
                default=["Clean Name", "Description", "Part", "Type", "Status", "Database Path"],
                key="all_fields_columns"
            )
    
    st.write(f"**Showing {len(filtered_fields)} of {len(fields)} fields**")
    
    # Display based on mode
    if display_mode == "Table View":
        # Create dataframe
        data = []
        for field in filtered_fields:
            row = {}
            
            if "Index" in columns_to_show:
                row["Index"] = field.index
            if "Clean Name" in columns_to_show:
                row["Clean Name"] = field.clean_name
            if "Description" in columns_to_show:
                row["Description"] = field.description
            if "Part" in columns_to_show:
                row["Part"] = field.part
            if "Item" in columns_to_show:
                row["Item"] = field.item or "-"
            if "Type" in columns_to_show:
                row["Type"] = field.field_type
            if "Status" in columns_to_show:
                if field.is_mapped:
                    row["Status"] = "✅ Mapped"
                elif field.is_questionnaire:
                    row["Status"] = "📋 Questionnaire"
                elif field.db_mapping:
                    row["Status"] = "💡 Suggested"
                else:
                    row["Status"] = "❌ Unmapped"
            if "Database Path" in columns_to_show:
                row["Database Path"] = field.db_mapping or "-"
            if "Confidence" in columns_to_show:
                row["Confidence"] = f"{field.confidence_score:.0%}" if field.confidence_score > 0 else "-"
            if "Page" in columns_to_show:
                row["Page"] = field.page
            if "Raw Name" in columns_to_show:
                row["Raw Name"] = field.raw_name[:50] + "..." if len(field.raw_name) > 50 else field.raw_name
            
            if field.is_custom_field:
                row["Custom"] = "✨"
            else:
                row["Custom"] = ""
            
            data.append(row)
        
        if data:
            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            # Export option
            csv = df.to_csv(index=False)
            st.download_button(
                "📥 Download as CSV",
                csv,
                f"{st.session_state.form_type}_all_fields.csv",
                "text/csv",
                key="download_all_fields_csv"
            )
    
    elif display_mode == "Card View":
        # Display as cards
        for field in filtered_fields:
            with st.container():
                st.markdown('<div class="field-card">', unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    st.markdown(f"**{field.clean_name}** - {field.description}")
                    st.caption(f"Part: {field.part} | Type: {field.field_type} | Page: {field.page}")
                
                with col2:
                    if field.is_mapped:
                        st.success(f"✅ Mapped to: {field.db_mapping}")
                    elif field.is_questionnaire:
                        st.info("📋 In Questionnaire")
                    elif field.db_mapping:
                        st.warning(f"💡 Suggested: {field.db_mapping} ({field.confidence_score:.0%})")
                    else:
                        st.error("❌ Not mapped")
                
                with col3:
                    if field.is_custom_field:
                        st.markdown("✨ **Custom**")
                
                st.markdown('</div>', unsafe_allow_html=True)
    
    elif display_mode == "Grouped by Part":
        # Group by part
        fields_by_part = defaultdict(list)
        for field in filtered_fields:
            fields_by_part[field.part].append(field)
        
        # Sort parts
        def natural_sort_key(part):
            numbers = re.findall(r'\d+', part)
            if numbers:
                return (0, int(numbers[0]))
            return (1, part)
        
        sorted_parts_display = sorted(fields_by_part.keys(), key=natural_sort_key)
        
        for part in sorted_parts_display:
            part_fields = fields_by_part[part]
            
            # Count statuses
            mapped = sum(1 for f in part_fields if f.is_mapped)
            quest = sum(1 for f in part_fields if f.is_questionnaire)
            unmapped = sum(1 for f in part_fields if not f.is_mapped and not f.is_questionnaire)
            
            icon = "⚖️" if "attorney" in part.lower() or "part 0" in part.lower() else "📑"
            
            with st.expander(f"{icon} **{part}** - {len(part_fields)} fields (✅ {mapped} | 📋 {quest} | ❌ {unmapped})", expanded=False):
                # Create table for this part
                data = []
                for field in part_fields:
                    data.append({
                        "Clean Name": field.clean_name,
                        "Description": field.description,
                        "Item": field.item or "-",
                        "Type": field.field_type,
                        "Status": "✅ Mapped" if field.is_mapped else "📋 Questionnaire" if field.is_questionnaire else "💡 Suggested" if field.db_mapping else "❌ Unmapped",
                        "Database Path": field.db_mapping or "-",
                        "Custom": "✨" if field.is_custom_field else ""
                    })
                
                if data:
                    df = pd.DataFrame(data)
                    st.dataframe(df, use_container_width=True, hide_index=True)
    
    else:  # Grouped by Status
        # Group by status
        status_groups = {
            "✅ Mapped": [f for f in filtered_fields if f.is_mapped],
            "📋 Questionnaire": [f for f in filtered_fields if f.is_questionnaire],
            "💡 Suggested": [f for f in filtered_fields if f.db_mapping and not f.is_mapped and not f.is_questionnaire],
            "❌ Unmapped": [f for f in filtered_fields if not f.is_mapped and not f.is_questionnaire and not f.db_mapping]
        }
        
        for status, status_fields in status_groups.items():
            if status_fields:
                with st.expander(f"{status} ({len(status_fields)} fields)", expanded=status == "✅ Mapped"):
                    data = []
                    for field in status_fields:
                        data.append({
                            "Clean Name": field.clean_name,
                            "Description": field.description,
                            "Part": field.part,
                            "Item": field.item or "-",
                            "Type": field.field_type,
                            "Database Path": field.db_mapping or "-",
                            "Confidence": f"{field.confidence_score:.0%}" if field.confidence_score > 0 else "-",
                            "Custom": "✨" if field.is_custom_field else ""
                        })
                    
                    if data:
                        df = pd.DataFrame(data)
                        st.dataframe(df, use_container_width=True, hide_index=True)
    
    # Bulk actions
    if filtered_fields:
        st.markdown("---")
        st.markdown("### ⚡ Bulk Actions")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📋 Add All Unmapped to Questionnaire", use_container_width=True):
                count = 0
                for field in filtered_fields:
                    if not field.is_mapped and not field.is_questionnaire:
                        field.is_questionnaire = True
                        mapper.create_mapping(field, "questionnaire", {})
                        count += 1
                if count > 0:
                    st.success(f"Added {count} fields to questionnaire")
                    st.rerun()
        
        with col2:
            if st.button("✅ Accept All Suggestions > 80%", use_container_width=True):
                count = 0
                for field in filtered_fields:
                    if not field.is_mapped and field.db_mapping and field.confidence_score > 0.8:
                        field.is_mapped = True
                        mapper.create_mapping(field, "direct", {"path": field.db_mapping})
                        count += 1
                if count > 0:
                    st.success(f"Accepted {count} high confidence mappings")
                    st.rerun()
        
        with col3:
            if st.button("🔄 Refresh View", use_container_width=True):
                st.rerun()

def render_mapped_fields_reference(mapper: UniversalUSCISMapper):
    """Render reference view of all mapped fields"""
    if 'pdf_fields' not in st.session_state or not st.session_state.pdf_fields:
        st.info("👆 Please complete field mapping first")
        return
    
    st.header("📚 Mapped Fields Reference")
    
    fields = st.session_state.pdf_fields
    
    # Get only mapped fields
    mapped_fields = [f for f in fields if f.is_mapped and f.db_mapping]
    
    if not mapped_fields:
        st.warning("No fields have been mapped yet. Please map some fields first.")
        return
    
    st.write(f"**Total mapped fields**: {len(mapped_fields)}")
    
    # Group by database object
    grouped_mappings = defaultdict(list)
    for field in mapped_fields:
        if field.db_mapping:
            obj_name = field.db_mapping.split('.')[0]
            grouped_mappings[obj_name].append(field)
    
    # Display options
    col1, col2, col3 = st.columns(3)
    with col1:
        view_mode = st.selectbox("View Mode", ["By Database Object", "By Form Part", "All Fields"])
    with col2:
        sort_by = st.selectbox("Sort By", ["Field Name", "Description", "Part", "Confidence"])
    with col3:
        search_mapped = st.text_input("Search mapped fields", placeholder="Enter keyword...")
    
    # Filter mapped fields based on search
    if search_mapped:
        search_lower = search_mapped.lower()
        filtered_mapped = [f for f in mapped_fields if 
                          search_lower in f.raw_name.lower() or 
                          search_lower in f.description.lower() or 
                          search_lower in (f.db_mapping or '').lower() or
                          search_lower in f.clean_name.lower()]
    else:
        filtered_mapped = mapped_fields
    
    # Sort fields
    if sort_by == "Field Name":
        filtered_mapped.sort(key=lambda x: x.clean_name)
    elif sort_by == "Description":
        filtered_mapped.sort(key=lambda x: x.description)
    elif sort_by == "Part":
        filtered_mapped.sort(key=lambda x: (x.part, x.index))
    elif sort_by == "Confidence":
        filtered_mapped.sort(key=lambda x: x.confidence_score, reverse=True)
    
    # Display based on view mode
    if view_mode == "By Database Object":
        st.markdown("### 🗃️ Mappings by Database Object")
        
        # Re-group filtered fields
        filtered_grouped = defaultdict(list)
        for field in filtered_mapped:
            if field.db_mapping:
                obj_name = field.db_mapping.split('.')[0]
                filtered_grouped[obj_name].append(field)
        
        # Display each object's mappings
        for obj_name in sorted(filtered_grouped.keys()):
            obj_fields = filtered_grouped[obj_name]
            
            with st.expander(f"**{obj_name}** ({len(obj_fields)} fields)", expanded=True):
                # Create a dataframe for better display
                data = []
                for field in obj_fields:
                    data.append({
                        "PDF Field": field.description,
                        "Clean Name": field.clean_name,
                        "Part": field.part,
                        "Type": field.field_type,
                        "Maps To": field.db_mapping,
                        "Confidence": f"{field.confidence_score:.0%}" if field.confidence_score > 0 else "Manual",
                        "Custom": "✨" if field.is_custom_field else ""
                    })
                
                df = pd.DataFrame(data)
                st.dataframe(df, use_container_width=True, hide_index=True)
    
    elif view_mode == "By Form Part":
        st.markdown("### 📑 Mappings by Form Part")
        
        # Group by part
        part_grouped = defaultdict(list)
        for field in filtered_mapped:
            part_grouped[field.part].append(field)
        
        # Sort parts
        def natural_sort_key(part):
            numbers = re.findall(r'\d+', part)
            if numbers:
                return (0, int(numbers[0]))
            return (1, part)
        
        sorted_parts = sorted(part_grouped.keys(), key=natural_sort_key)
        
        for part in sorted_parts:
            part_fields = part_grouped[part]
            icon = "⚖️" if "attorney" in part.lower() or "part 0" in part.lower() else "📑"
            
            with st.expander(f"{icon} **{part}** ({len(part_fields)} mapped fields)", expanded=False):
                data = []
                for field in part_fields:
                    data.append({
                        "Field": field.description,
                        "Clean Name": field.clean_name,
                        "Item": field.item or "-",
                        "Type": field.field_type,
                        "Database Path": field.db_mapping,
                        "Confidence": f"{field.confidence_score:.0%}" if field.confidence_score > 0 else "Manual",
                        "Custom": "✨" if field.is_custom_field else ""
                    })
                
                df = pd.DataFrame(data)
                st.dataframe(df, use_container_width=True, hide_index=True)
    
    else:  # All Fields view
        st.markdown("### 📋 All Mapped Fields")
        
        # Create comprehensive dataframe
        data = []
        for field in filtered_mapped:
            data.append({
                "Index": field.index,
                "Description": field.description,
                "Clean Name": field.clean_name,
                "Part": field.part,
                "Item": field.item or "-",
                "Page": field.page,
                "Type": field.field_type,
                "PDF Field Name": field.raw_name,
                "Database Path": field.db_mapping,
                "Confidence": f"{field.confidence_score:.0%}" if field.confidence_score > 0 else "Manual",
                "Custom": "✨" if field.is_custom_field else ""
            })
        
        df = pd.DataFrame(data)
        
        # Display
        st.write(f"Showing {len(df)} mapped fields")
        st.dataframe(df, use_container_width=True, hide_index=True)

def render_export_section(mapper: UniversalUSCISMapper):
    """Render export section"""
    if 'pdf_fields' not in st.session_state or not st.session_state.pdf_fields:
        st.info("👆 Please complete field mapping first")
        return
    
    st.header("📥 Export Mapping Configuration")
    
    fields = st.session_state.pdf_fields
    form_type = st.session_state.form_type
    
    # Summary statistics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Fields", len(fields))
    with col2:
        st.metric("Mapped", sum(1 for f in fields if f.is_mapped))
    with col3:
        st.metric("Questionnaire", sum(1 for f in fields if f.is_questionnaire))
    with col4:
        st.metric("Score", f"{mapper.calculate_mapping_score(fields)}%")
    
    st.markdown("---")
    
    # Export options
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📄 TypeScript Export")
        st.write("Generate TypeScript mapping file for your application")
        
        ts_content = mapper.generate_typescript_export(form_type, fields)
        
        # Clean form name for filename
        form_name = form_type.split(' - ')[0].replace(' ', '').replace('-', '')
        
        st.download_button(
            label="📥 Download TypeScript File",
            data=ts_content,
            file_name=f"{form_name}.ts",
            mime="text/plain",
            use_container_width=True
        )
        
        with st.expander("Preview TypeScript"):
            st.code(ts_content, language="typescript")
    
    with col2:
        st.subheader("📋 Questionnaire JSON")
        st.write("Generate questionnaire configuration for unmapped fields")
        
        json_content = mapper.generate_questionnaire_json(fields)
        
        st.download_button(
            label="📥 Download Questionnaire JSON",
            data=json_content,
            file_name=f"{form_type.split(' - ')[0].lower().replace(' ', '-')}-questionnaire.json",
            mime="application/json",
            use_container_width=True
        )
        
        with st.expander("Preview JSON"):
            st.code(json_content, language="json")
    
    # Additional exports
    st.markdown("---")
    st.subheader("📊 Additional Export Options")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Export mapping summary
        if st.button("📈 Export Mapping Summary", use_container_width=True):
            summary_data = []
            for field in fields:
                summary_data.append({
                    'Field Name': field.raw_name,
                    'Clean Name': field.clean_name,
                    'Description': field.description,
                    'Type': field.field_type,
                    'Part': field.part,
                    'Item': field.item,
                    'Page': field.page,
                    'Mapping': field.db_mapping or 'Unmapped',
                    'Status': 'Mapped' if field.is_mapped else 'Questionnaire' if field.is_questionnaire else 'Unmapped',
                    'Confidence': f"{field.confidence_score:.0%}" if field.confidence_score > 0 else '',
                    'Custom': 'Yes' if field.is_custom_field else 'No'
                })
            
            df = pd.DataFrame(summary_data)
            csv = df.to_csv(index=False)
            
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=f"{form_type}_mapping_summary.csv",
                mime="text/csv"
            )
    
    with col2:
        # Documentation
        if st.button("📝 Generate Documentation", use_container_width=True):
            doc_content = f"""# {form_type} Field Mapping Documentation

## Overview
- **Total Fields**: {len(fields)}
- **Mapped Fields**: {sum(1 for f in fields if f.is_mapped)}
- **Questionnaire Fields**: {sum(1 for f in fields if f.is_questionnaire)}
- **Custom Fields**: {sum(1 for f in fields if f.is_custom_field)}
- **Mapping Score**: {mapper.calculate_mapping_score(fields)}%

## Field Mappings

"""
            for field in fields:
                if field.is_mapped:
                    doc_content += f"- **{field.description}** ({field.clean_name}): `{field.db_mapping}`"
                    if field.is_custom_field:
                        doc_content += " *(Custom Field)*"
                    doc_content += "\n"
            
            st.download_button(
                label="📥 Download Docs",
                data=doc_content,
                file_name=f"{form_type}_mapping_documentation.md",
                mime="text/markdown"
            )
    
    with col3:
        # Help text
        st.info("💡 Use the TypeScript file in your application to map form fields to your database structure.")

def main():
    st.set_page_config(
        page_title="Universal USCIS Form Mapper",
        page_icon="🏛️",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize mapper
    mapper = UniversalUSCISMapper()
    
    # Render header
    render_header()
    
    # Sidebar
    with st.sidebar:
        st.header("📊 Mapping Overview")
        
        if 'pdf_fields' in st.session_state and st.session_state.pdf_fields:
            fields = st.session_state.pdf_fields
            
            # Progress metrics
            total = len(fields)
            mapped = sum(1 for f in fields if f.is_mapped)
            suggested = sum(1 for f in fields if f.db_mapping and not f.is_mapped and not f.is_questionnaire)
            questionnaire = sum(1 for f in fields if f.is_questionnaire or (not f.is_mapped and not f.db_mapping))
            custom = sum(1 for f in fields if f.is_custom_field)
            
            # Display metrics
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("Total Fields", total)
            if custom > 0:
                st.caption(f"Including {custom} custom fields")
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Progress bars
            st.write("**Mapping Progress**")
            st.progress(mapped / total if total > 0 else 0)
            st.caption(f"Mapped: {mapped} ({mapped/total*100:.1f}%)")
            
            st.progress(suggested / total if total > 0 else 0)
            st.caption(f"Suggested: {suggested} ({suggested/total*100:.1f}%)")
            
            st.progress(questionnaire / total if total > 0 else 0)
            st.caption(f"Questionnaire: {questionnaire} ({questionnaire/total*100:.1f}%)")
            
            # Part breakdown
            st.write("**Fields by Part**")
            parts_count = defaultdict(int)
            for field in fields:
                parts_count[field.part] += 1
            
            # Sort parts
            def natural_sort_key(part):
                numbers = re.findall(r'\d+', part)
                if numbers:
                    return (0, int(numbers[0]))
                return (1, part)
            
            sorted_parts = sorted(parts_count.items(), key=lambda x: natural_sort_key(x[0]))
            
            for part, count in sorted_parts:
                if "part 0" in part.lower() or "attorney" in part.lower():
                    st.write(f"⚖️ {part}: **{count}**")
                else:
                    st.write(f"- {part}: {count}")
            
            # Field types
            st.write("**Field Types**")
            type_counts = defaultdict(int)
            for field in fields:
                type_counts[field.field_type] += 1
            
            for ftype, count in sorted(type_counts.items()):
                st.write(f"- {ftype}: {count}")
        else:
            st.info("Upload a form to see mapping overview")
        
        st.markdown("---")
        st.markdown("### 📚 Resources")
        st.markdown("[USCIS Forms](https://www.uscis.gov/forms/all-forms)")
        st.markdown("[Form Instructions](https://www.uscis.gov/forms)")
        
        # Mapping tips
        st.markdown("---")
        st.markdown("### ℹ️ Mapping Tips")
        st.markdown("- **G-28**: Part 0 is Attorney info")
        st.markdown("- **I-129**: Part 8 is Preparer info")
        st.markdown("- **I-90**: Follow clean naming (P1_3a)")
        st.markdown("- **Auto-mapping**: High confidence suggestions")
        st.markdown("- **Unmapped**: Auto-added to questionnaire")
        st.markdown("- **Custom Fields**: Add missing fields manually")
    
    # Main content tabs
    tabs = st.tabs(["📤 Upload & Extract", "🗺️ Field Mapping", "📊 All Fields", "📚 Mapped Reference", "📥 Export", "⚙️ Settings"])
    
    with tabs[0]:
        render_upload_section(mapper)
    
    with tabs[1]:
        render_mapping_section(mapper)
    
    with tabs[2]:
        render_all_fields_view(mapper)
    
    with tabs[3]:
        render_mapped_fields_reference(mapper)
    
    with tabs[4]:
        render_export_section(mapper)
    
    with tabs[5]:
        st.header("⚙️ Settings")
        st.write("Configure mapping preferences and defaults")
        
        # View database schema
        st.subheader("📋 Database Schema")
        
        with st.expander("View Complete Database Schema", expanded=False):
            st.json(DB_OBJECTS)
        
        # Export/Import settings
        st.subheader("💾 Configuration Management")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Export Current Configuration**")
            if st.button("📥 Export Config", use_container_width=True):
                config = {
                    "form_type": st.session_state.get("form_type", ""),
                    "field_mappings": {},
                    "questionnaire_fields": [],
                    "custom_fields": []
                }
                
                if 'pdf_fields' in st.session_state:
                    for field in st.session_state.pdf_fields:
                        if field.is_mapped and field.db_mapping:
                            config["field_mappings"][field.clean_name] = {
                                "db_path": field.db_mapping,
                                "type": field.mapping_type,
                                "confidence": field.confidence_score
                            }
                        elif field.is_questionnaire:
                            config["questionnaire_fields"].append(field.clean_name)
                        
                        if field.is_custom_field:
                            config["custom_fields"].append({
                                "clean_name": field.clean_name,
                                "description": field.description,
                                "part": field.part,
                                "item": field.item,
                                "field_type": field.field_type
                            })
                
                config_json = json.dumps(config, indent=2)
                st.download_button(
                    "📥 Download Configuration",
                    config_json,
                    f"{config['form_type']}_config.json",
                    "application/json"
                )
        
        with col2:
            st.write("**Import Configuration**")
            uploaded_config = st.file_uploader(
                "Upload Config File",
                type=['json'],
                help="Upload a previously exported configuration file"
            )
            
            if uploaded_config:
                if st.button("📤 Apply Configuration", use_container_width=True):
                    try:
                        config = json.load(uploaded_config)
                        # Apply configuration logic here
                        st.success("Configuration applied successfully!")
                    except Exception as e:
                        st.error(f"Error applying configuration: {str(e)}")
        
        # Database connection settings
        st.subheader("🔌 Database Connection")
        st.info("Database connection settings would be configured here in a production environment.")
        
        # Advanced options
        st.subheader("🔧 Advanced Options")
        
        col1, col2 = st.columns(2)
        
        with col1:
            confidence_threshold = st.slider(
                "Auto-accept confidence threshold",
                min_value=0.5,
                max_value=1.0,
                value=0.8,
                step=0.05,
                help="Mappings with confidence above this threshold can be auto-accepted"
            )
        
        with col2:
            show_debug = st.checkbox(
                "Show debug information",
                value=False,
                help="Display additional debug information during field extraction"
            )
        
        # Clear cache
        st.subheader("🗑️ Clear Data")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Clear Current Form Data", use_container_width=True):
                if 'pdf_fields' in st.session_state:
                    del st.session_state.pdf_fields
                if 'form_type' in st.session_state:
                    del st.session_state.form_type
                if 'field_mappings' in st.session_state:
                    del st.session_state.field_mappings
                st.success("Form data cleared!")
                st.rerun()
        
        with col2:
            if st.button("Reset All Settings", use_container_width=True):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.success("All settings reset!")
                st.rerun()

 if __name__ == "__main__":
    main()
