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

# Special field type mappings
SPECIAL_FIELD_TYPES = {
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
    clean_name: str = ""

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
        self.field_counter = 1
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
        if self.db_paths_cache:
            print(f"Sample paths: {self.db_paths_cache[:5]}")
    
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
        
        # Use the item if available
        field_id = item
        
        if not field_id:
            # Try to extract from the field name
            # First, clean the field name aggressively
            clean_name = field_name
            
            # Remove all PDF structure noise
            noise_patterns = [
                r'topmostSubform\[\d+\]\.',
                r'form\d*\[\d+\]\.',
                r'#subform\[\d+\]\.',
                r'#pageSet\[\d+\]\.',
                r'Page\d+\[\d+\]\.',
                r'PDF417BarCode\d*\[\d+\]',
                r'Form\d+\s*#page\s*Set\s*Page\d+\s*',
                r'Pdf417bar\s*Code\d+',
                r'\.pdf$',
                r'\[\d+\]',
                r'^#',
                r'^form\.',
                r'^field\.',
                r'^Page\d+\.',
            ]
            
            for pattern in noise_patterns:
                clean_name = re.sub(pattern, '', clean_name, flags=re.IGNORECASE)
            
            # Look for field identifiers
            # Try to find numbers that look like field IDs
            matches = re.findall(r'[_\.\-](\d{1,2}[a-zA-Z]?)', clean_name)
            if matches:
                field_id = matches[-1]  # Take the last match
            else:
                # Look for line patterns
                line_match = re.search(r'line(\d{1,2}[a-zA-Z]?)', clean_name, re.IGNORECASE)
                if line_match:
                    field_id = line_match.group(1)
                else:
                    # Look for item patterns
                    item_match = re.search(r'Item[\s_\.\-]*(\d{1,2}[a-zA-Z]?)', clean_name, re.IGNORECASE)
                    if item_match:
                        field_id = item_match.group(1)
        
        # If still no field ID, use counter
        if not field_id:
            field_id = str(self.field_counter)
            self.field_counter += 1
        
        # Clean up field ID
        field_id = field_id.strip('._- ')
        
        # Ensure field ID is reasonable
        if len(field_id) > 3:
            # Try to extract just the numeric part with optional letter
            match = re.search(r'(\d{1,2}[a-zA-Z]?)', field_id)
            if match:
                field_id = match.group(1)
            else:
                field_id = field_id[:3]
        
        # Construct the clean name
        return f"P{part_num}_{field_id}"
    
    def extract_pdf_fields(self, pdf_file, form_type: str) -> List[PDFField]:
        """Extract all fields from any USCIS PDF form with accurate part detection"""
        fields = []
        self.field_counter = 1  # Reset field counter
        
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
            part_mapping = self._analyze_form_structure_smart(all_field_data, base_form_type, has_attorney_section)
            
            # Second pass: create field objects with correct parts
            for field_data in all_field_data:
                widget = field_data['widget']
                
                # Extract field information
                field_type = self._get_field_type(widget)
                
                # Get part from our analysis
                part = part_mapping.get(field_data['index'], f"Page {field_data['page']}")
                
                # Extract item
                item = self._extract_item_smart(widget.field_name, field_data['display'])
                
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
    
    def _analyze_form_structure_smart(self, all_field_data: List[Dict], form_type: str, has_attorney_section: bool) -> Dict[int, str]:
        """Smart form structure analysis with improved part detection"""
        part_mapping = {}
        
        # Get known structure for this form type
        known_structure = self.form_part_structures.get(form_type, {})
        
        # Strategy 1: Use known form structure as primary guide
        if known_structure:
            # For forms with known structure, use page-based heuristics
            if form_type == "G-28":
                # G-28 specific logic
                for field_data in all_field_data:
                    page = field_data['page']
                    field_name = field_data['name'].lower()
                    
                    if page == 1:
                        # Page 1 usually has Part 0 (attorney info) and Part 1
                        if any(keyword in field_name for keyword in ['attorney', 'bar', 'licensing', 'representative']):
                            part_mapping[field_data['index']] = "Part 0 - To be completed by attorney or BIA-accredited representative"
                        else:
                            part_mapping[field_data['index']] = "Part 1 - Information About Attorney or Accredited Representative"
                    elif page == 2:
                        # Page 2 typically has Parts 2-4
                        if any(keyword in field_name for keyword in ['eligibility', 'accredited']):
                            part_mapping[field_data['index']] = "Part 2 - Eligibility Information for Attorney or Accredited Representative"
                        elif any(keyword in field_name for keyword in ['appearance', 'agency']):
                            part_mapping[field_data['index']] = "Part 3 - Notice of Appearance"
                        else:
                            part_mapping[field_data['index']] = "Part 4 - Client Consent"
                    else:
                        # Later pages
                        part_mapping[field_data['index']] = f"Part {page + 2} - Additional Information"
            
            elif form_type == "I-129":
                # I-129 specific logic
                for field_data in all_field_data:
                    page = field_data['page']
                    field_name = field_data['name'].lower()
                    
                    if page == 1:
                        part_mapping[field_data['index']] = "Part 1 - Petitioner Information"
                    elif page == 2:
                        part_mapping[field_data['index']] = "Part 2 - Information About This Petition"
                    elif page == 3:
                        part_mapping[field_data['index']] = "Part 3 - Beneficiary Information"
                    # Continue for other pages...
            
            else:
                # Generic form with known structure
                self._apply_generic_smart_mapping(all_field_data, part_mapping, known_structure)
        
        else:
            # For unknown forms, use smart heuristics
            self._apply_generic_smart_mapping(all_field_data, part_mapping, {})
        
        # Strategy 2: Override with explicit part indicators in field names
        for field_data in all_field_data:
            clean_name = self._clean_field_name_for_analysis(field_data['name'])
            
            # Look for explicit part indicators
            part_match = re.search(r'Part[\s_\-]*(\d+)', clean_name, re.IGNORECASE)
            if part_match:
                part_num = part_match.group(1)
                if known_structure and f"Part {part_num}" in known_structure:
                    part_mapping[field_data['index']] = f"Part {part_num} - {known_structure[f'Part {part_num}']}"
                else:
                    part_mapping[field_data['index']] = f"Part {part_num}"
        
        # Strategy 3: Fill in gaps with contextual analysis
        for field_data in all_field_data:
            if field_data['index'] not in part_mapping:
                # Use context from nearby fields
                part = self._infer_part_from_neighbors(field_data, all_field_data, part_mapping, known_structure)
                part_mapping[field_data['index']] = part
        
        return part_mapping
    
    def _apply_generic_smart_mapping(self, all_field_data: List[Dict], part_mapping: Dict[int, str], known_structure: Dict):
        """Apply smart generic mapping based on field patterns and positions"""
        # Group fields by page
        fields_by_page = defaultdict(list)
        for field in all_field_data:
            fields_by_page[field['page']].append(field)
        
        # Analyze each page
        for page, fields in fields_by_page.items():
            # Look for part indicators on this page
            page_part = None
            
            # Check first few fields for part clues
            for field in fields[:10]:
                field_name = field['name'].lower()
                
                # Attorney/representative fields typically in Part 0 or 1
                if any(keyword in field_name for keyword in ['attorney', 'representative', 'bar', 'licensing']):
                    page_part = "Part 0 - To be completed by attorney or BIA-accredited representative"
                    break
                
                # Petitioner fields typically in Part 1
                elif any(keyword in field_name for keyword in ['petitioner', 'employer', 'company', 'organization']):
                    page_part = "Part 1 - Petitioner Information"
                    break
                
                # Beneficiary fields typically in Part 3
                elif any(keyword in field_name for keyword in ['beneficiary', 'alien', 'your name']):
                    page_part = "Part 3 - Beneficiary Information"
                    break
            
            # If no specific part found, estimate based on page number
            if not page_part:
                if page == 1:
                    page_part = "Part 1"
                else:
                    page_part = f"Part {page}"
                
                # Add description if known
                if known_structure and page_part in known_structure:
                    page_part = f"{page_part} - {known_structure[page_part]}"
            
            # Assign to all fields on this page
            for field in fields:
                if field['index'] not in part_mapping:
                    part_mapping[field['index']] = page_part
    
    def _infer_part_from_neighbors(self, field_data: Dict, all_fields: List[Dict], 
                                   part_mapping: Dict[int, str], known_structure: Dict) -> str:
        """Infer part from neighboring fields"""
        # Look at fields before and after
        field_index = field_data['index']
        
        # Check previous fields
        for i in range(field_index - 1, max(0, field_index - 5), -1):
            if i in part_mapping:
                return part_mapping[i]
        
        # Check next fields
        for i in range(field_index + 1, min(len(all_fields), field_index + 5)):
            if i in part_mapping:
                return part_mapping[i]
        
        # Default based on page
        page = field_data['page']
        return f"Part {page}"
    
    def _clean_field_name_for_analysis(self, field_name: str) -> str:
        """Clean field name for better pattern analysis"""
        # Remove common noise patterns
        patterns_to_remove = [
            r'topmostSubform\[\d+\]\.',
            r'form\d*\[\d+\]\.',
            r'#subform\[\d+\]\.',
            r'#pageSet\[\d+\]\.',
            r'Page\d+\[\d+\]\.',
            r'PDF417BarCode\d*\[\d+\]',
            r'Pdf417bar\s*Code\d+',
            r'\[\d+\]',
            r'\.pdf$',
            r'^#',
            r'^form\.',
        ]
        
        clean_name = field_name
        for pattern in patterns_to_remove:
            clean_name = re.sub(pattern, '', clean_name, flags=re.IGNORECASE)
        
        return clean_name
    
    def _extract_item_smart(self, field_name: str, field_display: str = "") -> str:
        """Smart item extraction with better pattern matching"""
        # First clean the field name
        clean_name = self._clean_field_name_for_analysis(field_name)
        
        # Remove misleading patterns
        clean_name = re.sub(r'P\d+line', 'line', clean_name, flags=re.IGNORECASE)
        clean_name = re.sub(r'Part\d+line', 'line', clean_name, flags=re.IGNORECASE)
        
        # Look for item patterns
        patterns = [
            r'line(\d{1,2}[a-zA-Z]?)',
            r'Item[\s_\.\-]*(\d{1,2}[a-zA-Z]?)',
            r'Question[\s_\.\-]*(\d{1,2}[a-zA-Z]?)',
            r'[_\.\-](\d{1,2}[a-zA-Z]?)$',
            r'#(\d{1,2}[a-zA-Z]?)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, clean_name, re.IGNORECASE)
            if match:
                item = match.group(1)
                # Validate item
                if re.match(r'^\d{1,2}[a-zA-Z]?$', item):
                    return item.rstrip('.')
        
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
        
        # Clean the field name first
        clean_name = re.sub(r'\[\d+\]', '', field_name_lower)
        clean_name = re.sub(r'form\d*\.', '', clean_name)
        clean_name = re.sub(r'#subform\d*\.', '', clean_name)
        
        # Check special field types first
        if any(pattern in clean_name for pattern in ['fullname', 'full_name', 'completename']):
            return ":FullName"
        elif 'addresstype' in clean_name or 'address_type' in clean_name:
            return ":AddressTypeBox"
        elif any(pattern in clean_name for pattern in ['ssn', 'social_security', 'socialsecurity']):
            return ":SingleBox"
        elif 'alien' in clean_name and any(pattern in clean_name for pattern in ['number', 'no', '#']):
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
        elif any(pattern in clean_name for pattern in ['number', 'count', 'total']) and not 'phone' in clean_name:
            return ":NumberBox"
        
        # Default
        return ":TextBox"
    
    def _generate_description(self, field_name: str, field_display: str = "") -> str:
        """Generate human-readable description"""
        # Use display name if available
        if field_display and field_display != field_name and not field_display.startswith('form'):
            desc = field_display
        else:
            desc = field_name
        
        # Clean aggressively
        cleaning_patterns = [
            r'topmostSubform\[\d+\]\.',
            r'form\d*\[\d+\]\.',
            r'#subform\[\d+\]\.',
            r'#pageSet\[\d+\]\.',
            r'Page\d+\[\d+\]\.',
            r'PDF417BarCode\d*\[\d+\]',
            r'Pdf417bar\s*Code\d+',
            r'\.pdf$',
            r'\[\d+\]',
            r'^#',
            r'^form\.',
            r'^field\.',
            r'^Page\d+\.',
        ]
        
        for pattern in cleaning_patterns:
            desc = re.sub(pattern, '', desc, flags=re.IGNORECASE)
        
        # Extract meaningful part
        segments = desc.split('.')
        meaningful = None
        
        for segment in reversed(segments):
            segment = segment.strip()
            if segment and not segment.isdigit() and len(segment) > 2:
                if segment.lower() not in ['form', 'page', 'field', 'subform', 'text', 'checkbox']:
                    meaningful = segment
                    break
        
        if meaningful:
            desc = meaningful
        
        # Convert camelCase to spaces
        desc = re.sub(r'([a-z])([A-Z])', r'\1 \2', desc)
        
        # Common replacements
        replacements = {
            'FamilyName': 'Last Name',
            'GivenName': 'First Name',
            'MiddleName': 'Middle Name',
            'LastName': 'Last Name',
            'FirstName': 'First Name',
        }
        
        for old, new in replacements.items():
            desc = desc.replace(old, new)
        
        # Clean up
        desc = ' '.join(desc.split())
        desc = desc.strip('._- ')
        
        # Smart title case
        if desc:
            words = desc.split()
            result = []
            for word in words:
                if word.isupper() and len(word) > 1:
                    result.append(word)  # Keep acronyms
                else:
                    result.append(word.capitalize())
            desc = ' '.join(result)
        
        return desc or "Field"
    
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
        
        # Enhanced generic pattern matching based on part and field content
        
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
        
        # Petitioner/Customer mappings (usually Part 1)
        elif "part 1" in field.part.lower() or "petitioner" in field.part.lower():
            if any(p in all_text for p in ['company', 'organization', 'business', 'employer']) and "name" in all_text:
                suggestions.append(MappingSuggestion("customer.customer_name", 0.9, "Company/Organization name"))
            elif "fein" in all_text or ("federal" in all_text and "ein" in all_text):
                suggestions.append(MappingSuggestion("customer.customer_tax_id", 0.9, "Federal Tax ID"))
        
        # Beneficiary mappings (usually Part 3 or "Information About You")
        elif "beneficiary" in field.part.lower() or "part 3" in field.part.lower() or "information about you" in field.part.lower():
            if any(p in all_text for p in ['lastname', 'last_name', 'family_name']):
                suggestions.append(MappingSuggestion("beneficiary.Beneficiary.beneficiaryLastName", 0.95, "Beneficiary last name"))
            elif any(p in all_text for p in ['firstname', 'first_name', 'given_name']):
                suggestions.append(MappingSuggestion("beneficiary.Beneficiary.beneficiaryFirstName", 0.95, "Beneficiary first name"))
            elif any(p in all_text for p in ['alien', 'a-number', 'anumber']) and any(p in all_text for p in ['number', 'no']):
                suggestions.append(MappingSuggestion("beneficiary.Beneficiary.alienNumber", 0.95, "Alien number"))
        
        # Sort by confidence and return top suggestions
        suggestions.sort(key=lambda x: x.confidence, reverse=True)
        return suggestions[:3]
    
    def _get_g28_suggestions(self, field: PDFField) -> List[MappingSuggestion]:
        """Get suggestions specific to G-28 form"""
        suggestions = []
        field_name = field.raw_name.lower()
        clean_name = field.clean_name.lower()
        desc_lower = field.description.lower()
        
        # Part 0/1 - Attorney Information
        if "part 0" in field.part.lower() or ("part 1" in field.part.lower() and "attorney" in field.part.lower()):
            if any(p in desc_lower for p in ['last name', 'family name']):
                suggestions.append(MappingSuggestion("attorney.attorneyInfo.lastName", 0.95, "Attorney last name"))
            elif any(p in desc_lower for p in ['first name', 'given name']):
                suggestions.append(MappingSuggestion("attorney.attorneyInfo.firstName", 0.95, "Attorney first name"))
        
        return suggestions
    
    def _get_i129_suggestions(self, field: PDFField) -> List[MappingSuggestion]:
        """Get suggestions specific to I-129 form"""
        suggestions = []
        field_name = field.raw_name.lower()
        
        # Part 1 - Petitioner Information
        if "part 1" in field.part.lower():
            if "company" in field_name or "organization" in field_name:
                suggestions.append(MappingSuggestion("customer.customer_name", 0.9, "Company name"))
        
        return suggestions
    
    def _get_i90_suggestions(self, field: PDFField) -> List[MappingSuggestion]:
        """Get suggestions specific to I-90 form"""
        suggestions = []
        clean_name = field.clean_name
        
        # Use clean name patterns
        if clean_name == "P1_3a":
            suggestions.append(MappingSuggestion("beneficiary.Beneficiary.beneficiaryLastName", 0.95, "Last name"))
        elif clean_name == "P1_3b":
            suggestions.append(MappingSuggestion("beneficiary.Beneficiary.beneficiaryFirstName", 0.95, "First name"))
        
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
                for field in part_fields[:10]:
                    field_info = f"• {field.description}"
                    if field.item:
                        field_info += f" (Item {field.item})"
                    field_info += f" - Type: {field.field_type}"
                    field_info += f" - Clean Name: {field.clean_name}"
                    st.write(field_info)
                
                if len(part_fields) > 10:
                    st.write(f"... and {len(part_fields) - 10} more fields")
        
        # Show mapping statistics
        st.write("**Mapping Statistics:**")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            mapped = sum(1 for f in fields if f.db_mapping)
            st.metric("Auto-mapped", f"{mapped} ({mapped/len(fields)*100:.1f}%)")
        
        with col2:
            high_conf = sum(1 for f in fields if f.confidence_score > 0.8)
            st.metric("High confidence", f"{high_conf} ({high_conf/len(fields)*100:.1f}%)")
        
        with col3:
            questionnaire = sum(1 for f in fields if f.is_questionnaire)
            st.metric("Questionnaire", f"{questionnaire} ({questionnaire/len(fields)*100:.1f}%)")
        
        with col4:
            score = self.calculate_mapping_score(fields)
            st.metric("Overall Score", f"{score}%")
    
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
    st.markdown("""
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
    """, unsafe_allow_html=True)
    
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
        status_filter = st.selectbox("Filter by Status", ["All", "Mapped", "Suggested", "Questionnaire", "Unmapped"])
    
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
                    "Status": "✅ Mapped" if field.is_mapped else "📋 Questionnaire" if field.is_questionnaire else "💡 Suggested" if field.db_mapping else "❌ Unmapped"
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
                
                # Debug: Show total paths
                if db_paths:
                    st.caption(f"📊 {len(db_paths)} database fields available")
                else:
                    st.error("⚠️ No database paths available. Check configuration.")
                    # Force rebuild cache
                    mapper._build_database_paths_cache()
                    db_paths = mapper.get_all_database_paths()
                
                # Show suggested mappings if available
                if field.db_mapping and not field.is_mapped:
                    st.info(f"💡 Suggested: {field.db_mapping}")
                    
                    # Quick accept button for suggestion
                    if st.button(f"Use suggestion", key=f"use_sugg_{field.index}"):
                        field.is_mapped = True
                        field.is_questionnaire = False
                        mapper.create_mapping(field, "direct", {"path": field.db_mapping})
                        st.rerun()
                
                # Filter paths based on field context
                part_lower = field.part.lower()
                
                # Primary filter by object type based on part
                filtered_paths = []
                
                # Smart filtering based on part
                if "attorney" in part_lower or "part 0" in part_lower or "representative" in part_lower:
                    filtered_paths = [p for p in db_paths if p.startswith(("attorney", "attorneyLawfirm"))]
                elif "beneficiary" in part_lower or "part 3" in part_lower or "information about you" in part_lower:
                    filtered_paths = [p for p in db_paths if p.startswith("beneficiary")]
                elif "petitioner" in part_lower or "part 1" in part_lower or "employer" in part_lower:
                    filtered_paths = [p for p in db_paths if p.startswith("customer")]
                elif "case" in part_lower or "petition" in part_lower or "part 2" in part_lower:
                    filtered_paths = [p for p in db_paths if p.startswith("case")]
                elif "lca" in part_lower or "labor" in part_lower:
                    filtered_paths = [p for p in db_paths if p.startswith("lca")]
                
                # If no filtered paths or very few, show all paths
                if len(filtered_paths) < 5:
                    filtered_paths = db_paths
                
                # Create dropdown options
                dropdown_options = ["-- Select a database field --"] + filtered_paths
                
                # Try to find current mapping in options
                default_index = 0
                if field.db_mapping and field.db_mapping in dropdown_options:
                    default_index = dropdown_options.index(field.db_mapping)
                
                # Show the selectbox
                custom_path = st.selectbox(
                    "Select database field",
                    dropdown_options,
                    key=f"path_select_{field.index}",
                    help=f"Select from {len(dropdown_options)-1} available fields",
                    index=default_index
                )
                
                # Handle selection
                if custom_path and custom_path != "-- Select a database field --":
                    st.success(f"Selected: {custom_path}")
                else:
                    custom_path = None
            
            elif mapping_type == "Custom Path":
                # Text input for custom path
                custom_path = st.text_input(
                    "Enter database path",
                    value=field.db_mapping if field.db_mapping and not field.db_mapping.startswith("Default:") else "",
                    key=f"custom_path_{field.index}",
                    placeholder="e.g., beneficiary.Beneficiary.beneficiaryFirstName",
                    help="Enter a custom database path"
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
                                if st.button(f"→ {sugg}", key=f"sugg_{field.index}_{idx}"):
                                    field.is_mapped = True
                                    field.is_questionnaire = False
                                    mapper.create_mapping(field, "direct", {"path": sugg})
                                    st.rerun()
                    else:
                        st.warning("No matching database fields found")
            
            elif mapping_type == "Default Value":
                default_val = st.text_input(
                    "Default Value",
                    value="",
                    key=f"default_{field.index}",
                    placeholder="Enter default value (e.g., true, false, or text)"
                )
        
        with col3:
            # Action buttons
            if mapping_type != "Keep Current":
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
                    'Confidence': f"{field.confidence_score:.0%}" if field.confidence_score > 0 else ''
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
- **Mapping Score**: {mapper.calculate_mapping_score(fields)}%

## Field Mappings

"""
            for field in fields:
                if field.is_mapped:
                    doc_content += f"- **{field.description}** ({field.clean_name}): `{field.db_mapping}`\n"
            
            st.download_button(
                label="📥 Download Docs",
                data=doc_content,
                file_name=f"{form_type}_mapping_documentation.md",
                mime="text/markdown"
            )
    
    with col3:
        # Help text
        st.info("💡 Use the TypeScript file in your application to map form fields to your database structure.")

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
                        "Confidence": f"{field.confidence_score:.0%}" if field.confidence_score > 0 else "Manual"
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
                        "Confidence": f"{field.confidence_score:.0%}" if field.confidence_score > 0 else "Manual"
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
                "Confidence": f"{field.confidence_score:.0%}" if field.confidence_score > 0 else "Manual"
            })
        
        df = pd.DataFrame(data)
        
        # Display
        st.write(f"Showing {len(df)} mapped fields")
        st.dataframe(df, use_container_width=True, hide_index=True)

def main():
    """Main application entry point"""
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
            
            # Display metrics
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("Total Fields", total)
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
    
    # Main content tabs
    tabs = st.tabs(["📤 Upload & Extract", "🗺️ Field Mapping", "📚 Mapped Reference", "📥 Export", "⚙️ Settings"])
    
    with tabs[0]:
        render_upload_section(mapper)
    
    with tabs[1]:
        render_mapping_section(mapper)
    
    with tabs[2]:
        render_mapped_fields_reference(mapper)
    
    with tabs[3]:
        render_export_section(mapper)
    
    with tabs[4]:
        st.header("⚙️ Settings")
        st.write("Configure mapping preferences and defaults")
        
        # Mapping preferences
        st.subheader("Mapping Preferences")
        auto_accept_high = st.checkbox("Auto-accept high confidence mappings (>80%)", value=True)
        include_suggestions = st.checkbox("Show mapping suggestions", value=True)
        auto_questionnaire = st.checkbox("Automatically add unmapped fields to questionnaire", value=True)
        
        # Export preferences
        st.subheader("Export Preferences")
        default_format = st.selectbox("Default export format", ["TypeScript", "JavaScript", "JSON"])
        include_comments = st.checkbox("Include comments in export", value=True)
        
        # Database settings
        st.subheader("📊 Database Schema Browser")
        st.write("Explore the available database fields for mapping")
        
        # Database browser
        selected_object = st.selectbox(
            "Select database object",
            list(DB_OBJECTS.keys()),
            help="Choose a database object to view its structure"
        )
        
        if selected_object:
            obj_structure = DB_OBJECTS[selected_object]
            
            # Display structure in a user-friendly way
            for sub_obj, fields in obj_structure.items():
                if sub_obj:
                    st.write(f"**{sub_obj}:**")
                else:
                    st.write("**Fields:**")
                
                if isinstance(fields, list):
                    # Create columns for better display
                    cols = st.columns(3)
                    for i, field in enumerate(fields):
                        with cols[i % 3]:
                            full_path = f"{selected_object}.{sub_obj}.{field}" if sub_obj else f"{selected_object}.{field}"
                            st.code(full_path, language=None)
                elif isinstance(fields, dict):
                    # Handle nested structures
                    for nested_key, nested_fields in fields.items():
                        st.write(f"  *{nested_key}:*")
                        if isinstance(nested_fields, list):
                            cols = st.columns(3)
                            for i, field in enumerate(nested_fields):
                                with cols[i % 3]:
                                    full_path = f"{selected_object}.{sub_obj}.{nested_key}.{field}"
                                    st.code(full_path, language=None)
        
        # Quick reference
        st.markdown("---")
        st.subheader("📚 Quick Reference")
        
        with st.expander("Common Field Mappings"):
            st.markdown("""
            **Attorney Fields:**
            - `attorney.attorneyInfo.lastName` - Attorney's last name
            - `attorney.attorneyInfo.stateBarNumber` - Bar number
            - `attorneyLawfirmDetails.lawfirmDetails.lawFirmName` - Law firm name
            
            **Beneficiary Fields:**
            - `beneficiary.Beneficiary.beneficiaryFirstName` - First name
            - `beneficiary.Beneficiary.alienNumber` - Alien/USCIS number
            - `beneficiary.Beneficiary.beneficiarySsn` - Social Security Number
            
            **Customer/Petitioner Fields:**
            - `customer.customer_name` - Company/Organization name
            - `customer.customer_tax_id` - Federal Tax ID/EIN
            - `customer.signatory.signatory_first_name` - Signatory's name
            
            **Address Fields:**
            - `beneficiary.HomeAddress.addressStreet` - Street address
            - `beneficiary.HomeAddress.addressCity` - City
            - `beneficiary.HomeAddress.addressState` - State
            - `beneficiary.HomeAddress.addressZip` - ZIP code
            """)
        
        with st.expander("Field Type Suffixes"):
            st.markdown("""
            **TypeScript Field Type Suffixes:**
            - `:TextBox` - Regular text input
            - `:CheckBox` - Checkbox field
            - `:ConditionBox` - Radio button/conditional
            - `:SelectBox` - Dropdown selection
            - `:Date` - Date field
            - `:SignatureBox` - Signature field
            - `:FullName` - Full name field
            - `:SingleBox` - Single character boxes (SSN, A#)
            - `:AddressTypeBox` - Address type selection
            """)
        
        # View full schema button
        if st.button("View Complete Database Schema"):
            st.json(DB_OBJECTS)

if __name__ == "__main__":
    main()
