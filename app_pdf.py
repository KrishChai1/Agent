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

# Field type mappings for TypeScript format - based on examples
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

# Special field type mappings from the examples
SPECIAL_FIELD_TYPES = {
    # From G28.ts example
    "addressType": ":AddressTypeBox",
    "representative": ":ConditionBox",
    "careOfName": ":FullName",
    
    # From I129.ts example
    "alienNumber": ":SingleBox",
    "ussocialssn": ":SingleBox",
    "arrivalDepartureRecords": ":ConditionBox",
    "dependentApplication": ":ConditionBox",
    
    # From H2B.ts example
    "h1bBeneficiaryFirstName": ":MultipleBox",
    "beneficiaryFullName": ":FullName",
}

# Form-specific part structures
FORM_PART_STRUCTURES = {
    "G-28": {
        "Part 1": "Attorney or Accredited Representative Information",
        "Part 2": "Eligibility Information",
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
        "Part 4": "Additional Information"
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
    field_type_suffix: str = ":TextBox"  # Default suffix

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
    
    def extract_pdf_fields(self, pdf_file, form_type: str) -> List[PDFField]:
        """Extract all fields from any USCIS PDF form with accurate part detection"""
        fields = []
        
        try:
            pdf_bytes = pdf_file.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            # Clean form type to get base form name
            base_form_type = form_type.split(' - ')[0].strip()
            
            # First pass: collect all field names to understand structure
            all_field_data = []
            field_index = 0
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                for widget in page.widgets():
                    if widget.field_name:
                        all_field_data.append({
                            'name': widget.field_name,
                            'page': page_num + 1,
                            'widget': widget,
                            'index': field_index
                        })
                        field_index += 1
            
            # Analyze field names to understand part structure
            part_mapping = self._analyze_form_structure_by_type(all_field_data, base_form_type)
            
            # Second pass: create field objects with correct parts
            for field_data in all_field_data:
                widget = field_data['widget']
                
                # Extract field information
                field_type = self._get_field_type(widget)
                
                # Get part from our analysis
                part = part_mapping.get(field_data['index'], f"Page {field_data['page']}")
                
                # Extract other metadata
                item = self._extract_item(widget.field_name)
                description = self._generate_description(widget.field_name, widget.field_display)
                
                # Determine field type suffix
                field_type_suffix = self._get_field_type_suffix(widget.field_name, field_type)
                
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
                    field_type_suffix=field_type_suffix
                )
                
                # Get mapping suggestions
                suggestions = self._get_mapping_suggestions(pdf_field, base_form_type)
                if suggestions:
                    best_suggestion = suggestions[0]
                    pdf_field.db_mapping = best_suggestion.db_path
                    pdf_field.confidence_score = best_suggestion.confidence
                    pdf_field.mapping_type = best_suggestion.field_type
                else:
                    # Automatically mark unmapped fields as questionnaire
                    pdf_field.is_questionnaire = True
                
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
    
    def _analyze_form_structure_by_type(self, all_field_data: List[Dict], form_type: str) -> Dict[int, str]:
        """Analyze form structure based on specific form type"""
        part_mapping = {}
        
        # Get known structure for this form type
        known_structure = self.form_part_structures.get(form_type, {})
        
        # Common patterns for field names
        part_patterns = [
            # Part patterns
            (r'[Pp]art\s*(\d+)', lambda m: f"Part {m.group(1)}"),
            (r'P(\d+)[_\.\-]', lambda m: f"Part {m.group(1)}"),
            (r'pt(\d+)[_\.\-]', lambda m: f"Part {m.group(1)}"),
            (r'Part(\d+)', lambda m: f"Part {m.group(1)}"),
            
            # Page patterns (fallback)
            (r'Page(\d+)', lambda m: f"Page {m.group(1)}"),
            (r'p(\d+)[_\.\-]', lambda m: f"Page {m.group(1)}"),
        ]
        
        # First pass: Find explicit part numbers
        explicit_parts = {}
        for i, field_data in enumerate(all_field_data):
            field_name = field_data['name']
            
            for pattern, formatter in part_patterns:
                match = re.search(pattern, field_name, re.IGNORECASE)
                if match:
                    part = formatter(match)
                    # Check if this is a known part for this form
                    if known_structure and part in known_structure:
                        part = f"{part} - {known_structure[part]}"
                    explicit_parts[i] = part
                    break
        
        # Apply explicit parts
        for i, part in explicit_parts.items():
            part_mapping[i] = part
        
        # Fill in gaps using proximity and page numbers
        current_part = None
        current_page = 1
        
        for i in range(len(all_field_data)):
            field_data = all_field_data[i]
            page = field_data['page']
            
            if i in part_mapping:
                current_part = part_mapping[i]
                current_page = page
            elif current_part:
                # Check if we're still on the same page or close
                if page == current_page or (i > 0 and i-1 in part_mapping):
                    part_mapping[i] = current_part
                else:
                    # Try to determine from known structure
                    part_mapping[i] = self._guess_part_from_page(page, form_type)
            else:
                # No current part - guess from page
                part_mapping[i] = self._guess_part_from_page(page, form_type)
                current_part = part_mapping[i]
        
        return part_mapping
    
    def _guess_part_from_page(self, page: int, form_type: str) -> str:
        """Guess part based on page number and form type"""
        known_structure = self.form_part_structures.get(form_type, {})
        
        # Simple heuristic: parts often correspond to pages
        estimated_part = f"Part {page}"
        
        # Check if this estimated part exists in known structure
        if estimated_part in known_structure:
            return f"{estimated_part} - {known_structure[estimated_part]}"
        
        # Otherwise return page number
        return f"Page {page}"
    
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
        
        # Check special field types first
        for key, suffix in SPECIAL_FIELD_TYPES.items():
            if key.lower() in field_name_lower:
                return suffix
        
        # Check for specific patterns
        if 'addresstype' in field_name_lower or 'address_type' in field_name_lower:
            return ":AddressTypeBox"
        elif 'fullname' in field_name_lower or 'full_name' in field_name_lower:
            return ":FullName"
        elif field_type == "radio":
            return ":ConditionBox"
        elif field_type == "checkbox":
            return ":CheckBox"
        elif field_type == "date":
            return ":Date"
        elif field_type == "signature":
            return ":SignatureBox"
        
        # Default mapping
        return FIELD_TYPE_SUFFIX_MAP.get(field_type, ":TextBox")
    
    def _extract_item(self, field_name: str) -> str:
        """Extract item number from field name"""
        # Clean the field name first
        clean_name = re.sub(r'\[\d+\]', '', field_name)
        
        patterns = [
            r'Item\s*(\d+[a-zA-Z]?\.?)',
            r'Line\s*(\d+[a-zA-Z]?\.?)',
            r'Question\s*(\d+[a-zA-Z]?\.?)',
            r'_(\d+[a-zA-Z]?)_',
            r'_(\d+[a-zA-Z]?)$',
            r'\.(\d+[a-zA-Z]?)\.',
            r'\.(\d+[a-zA-Z]?)$',
            r'#(\d+[a-zA-Z]?)',
            r'No\.?\s*(\d+[a-zA-Z]?)',
            r'Number\s*(\d+[a-zA-Z]?)',
            r'pt(\d+)_(\d+[a-zA-Z]?)',  # For patterns like pt3_1a
        ]
        
        for pattern in patterns:
            match = re.search(pattern, clean_name, re.IGNORECASE)
            if match:
                if 'pt' in pattern:  # Special handling for pt patterns
                    return match.group(2)
                item = match.group(1)
                return item.rstrip('.')
        
        return ""
    
    def _generate_description(self, field_name: str, field_display: str = "") -> str:
        """Generate human-readable description"""
        # Use display name if available
        if field_display and field_display != field_name:
            desc = field_display
        else:
            desc = field_name
        
        # Clean up common patterns
        desc = re.sub(r'^form\[\d+\]\.', '', desc, flags=re.IGNORECASE)
        desc = re.sub(r'^#subform\[\d+\]\.', '', desc)
        desc = re.sub(r'\[\d+\]', '', desc)
        desc = re.sub(r'\.pdf$', '', desc, flags=re.IGNORECASE)
        
        # Remove technical prefixes
        prefixes_to_remove = [
            'topmostSubform.', 'Page', 'Part', 'Section', '#', 'field'
        ]
        for prefix in prefixes_to_remove:
            if desc.startswith(prefix):
                desc = desc[len(prefix):].lstrip('._-')
        
        # Split by delimiters
        if '_' in desc:
            parts = desc.split('_')
            desc = ' '.join([p for p in parts if p and not p.isdigit()])
        elif '.' in desc:
            parts = desc.split('.')
            desc = ' '.join([p for p in parts if p and not p.isdigit()])
        
        # Convert camelCase
        desc = re.sub(r'([a-z])([A-Z])', r'\1 \2', desc)
        
        # Expand abbreviations
        abbreviations = {
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
            'LLC': 'Limited Liability Company'
        }
        
        for abbr, full in abbreviations.items():
            desc = re.sub(rf'\b{abbr}\b', full, desc, flags=re.IGNORECASE)
        
        # Clean up and title case
        desc = ' '.join(desc.split())
        desc = desc.strip('._- ')
        
        # Smart title case (preserve acronyms)
        words = desc.split()
        result = []
        for word in words:
            if word.isupper() and len(word) > 1:
                result.append(word)  # Keep acronyms
            else:
                result.append(word.capitalize())
        
        return ' '.join(result) if result else "Field"
    
    def _get_mapping_suggestions(self, field: PDFField, form_type: str) -> List[MappingSuggestion]:
        """Get intelligent mapping suggestions for a field"""
        suggestions = []
        
        # Form-specific mapping rules
        if form_type == "G-28":
            suggestions.extend(self._get_g28_suggestions(field))
        elif form_type == "I-129":
            suggestions.extend(self._get_i129_suggestions(field))
        
        # Generic pattern matching
        field_name_lower = field.raw_name.lower()
        desc_lower = field.description.lower()
        
        # Common patterns
        if any(p in field_name_lower for p in ['lastname', 'last_name', 'familyname']):
            if 'attorney' in field.part.lower() or 'part 1' in field.part.lower():
                suggestions.append(MappingSuggestion("attorney.attorneyInfo.lastName", 0.9, "Attorney last name"))
            elif 'beneficiary' in field.part.lower():
                suggestions.append(MappingSuggestion("beneficiary.Beneficiary.beneficiaryLastName", 0.9, "Beneficiary last name"))
            else:
                suggestions.append(MappingSuggestion("customer.signatory_last_name", 0.8, "Signatory last name"))
        
        if any(p in field_name_lower for p in ['firstname', 'first_name', 'givenname']):
            if 'attorney' in field.part.lower() or 'part 1' in field.part.lower():
                suggestions.append(MappingSuggestion("attorney.attorneyInfo.firstName", 0.9, "Attorney first name"))
            elif 'beneficiary' in field.part.lower():
                suggestions.append(MappingSuggestion("beneficiary.Beneficiary.beneficiaryFirstName", 0.9, "Beneficiary first name"))
            else:
                suggestions.append(MappingSuggestion("customer.signatory_first_name", 0.8, "Signatory first name"))
        
        # Sort by confidence and return top suggestions
        suggestions.sort(key=lambda x: x.confidence, reverse=True)
        return suggestions[:1]  # Return only top suggestion
    
    def _get_g28_suggestions(self, field: PDFField) -> List[MappingSuggestion]:
        """Get suggestions specific to G-28 form"""
        suggestions = []
        field_name = field.raw_name.lower()
        
        # Part 1 - Attorney Information
        if "part 1" in field.part.lower():
            if "bar" in field_name:
                suggestions.append(MappingSuggestion("attorney.attorneyInfo.stateBarNumber", 0.95, "G-28 attorney bar number"))
            elif "licensing" in field_name:
                suggestions.append(MappingSuggestion("attorney.attorneyInfo.licensingAuthority", 0.9, "G-28 licensing authority"))
        
        # Part 3 - Client Information
        elif "part 3" in field.part.lower():
            if "petitioner" in field_name:
                suggestions.append(MappingSuggestion("customer.customer_name", 0.85, "G-28 client name"))
        
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
            if "attorney" in part.lower() or "representative" in part.lower():
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
        field.is_mapped = True
        
        if mapping_type == "direct":
            field.db_mapping = mapping_config.get("path")
        elif mapping_type == "concatenated":
            field.db_mapping = json.dumps(mapping_config)
        elif mapping_type == "conditional":
            field.db_mapping = json.dumps(mapping_config)
        elif mapping_type == "default":
            field.db_mapping = f"Default: {mapping_config.get('value')}"
        elif mapping_type == "questionnaire":
            field.is_questionnaire = True
            field.is_mapped = False
    
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
            if field.is_mapped and field.db_mapping and not field.db_mapping.startswith("Default:"):
                # Add type suffix
                mapping_value = f"{field.db_mapping}{field.field_type_suffix}"
                
                if field.mapping_type == "direct":
                    # Determine category based on path
                    if field.db_mapping.startswith('customer'):
                        categories['customerData'][field.raw_name] = mapping_value
                    elif field.db_mapping.startswith('beneficiary'):
                        categories['beneficiaryData'][field.raw_name] = mapping_value  
                    elif field.db_mapping.startswith('attorney'):
                        categories['attorneyData'][field.raw_name] = mapping_value
                    elif field.db_mapping.startswith('case'):
                        categories['caseData'][field.raw_name] = mapping_value
                    elif field.db_mapping.startswith('lca'):
                        categories['lcaData'][field.raw_name] = mapping_value
                elif field.mapping_type == "conditional":
                    categories['conditionalData'][field.raw_name] = field.mapping_config
            elif field.db_mapping and field.db_mapping.startswith("Default:"):
                # Extract default value
                default_value = field.db_mapping.replace("Default: ", "")
                if default_value.lower() in ['true', 'false']:
                    categories['defaultData'][field.raw_name] = field.field_type_suffix
                else:
                    categories['defaultData'][field.raw_name] = f"{default_value}{field.field_type_suffix}"
            elif field.is_questionnaire or (not field.is_mapped and not field.db_mapping):
                # Use simpler format for questionnaire like in examples
                clean_name = field.raw_name.replace('form[0].', '').replace('#subform[0].', '')
                clean_name = re.sub(r'\[\d+\]', '', clean_name)
                categories['questionnaireData'][clean_name] = f"{field.item or clean_name}{field.field_type_suffix}"
        
        # Generate TypeScript content
        ts_content = f"""export const {form_name} = {{
    "formname": "{form_name}",
    "customerData": {self._format_data_section(categories['customerData'])},
    "beneficiaryData": {self._format_data_section(categories['beneficiaryData'])},
    "attorneyData": {self._format_data_section(categories['attorneyData'])},
    "questionnaireData": {self._format_data_section(categories['questionnaireData'])},
    "defaultData": {self._format_data_section(categories['defaultData'])},
    "conditionalData": {self._format_conditional_section(categories['conditionalData'])},
    "pdfName": "{form_type.lower().replace(' ', '-').split(' - ')[0]}",
    "caseData": {self._format_data_section(categories['caseData'])},
    "lcaData": {self._format_data_section(categories['lcaData'])}
}}"""
        
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
                # Generate control name like in the example
                if field.item:
                    control_name = f"p{part_number}_{field.item}"
                else:
                    control_name = f"q_{field.index}"
                
                # Generate label
                if field.item and part_number:
                    label = f"P{part_number}_{field.item}. {field.description}"
                else:
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
                
                # Add line break if needed (like in the example)
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

# Main Streamlit UI functions remain the same...
# [Include all the render_* functions from the original code]

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
    
    # Render UI sections
    st.title("🏛️ Universal USCIS Form Mapper")
    st.write("Extract and map fields from any USCIS form with intelligent part detection")
    
    # Upload section
    with st.container():
        st.header("📤 Upload USCIS Form")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Form type selection
            common_forms = [
                "Custom/Other",
                "G-28 - Notice of Entry of Appearance",
                "I-129 - Petition for Nonimmigrant Worker",
                "I-90 - Application to Replace Green Card",
                "I-140 - Immigrant Petition for Alien Worker",
                "I-485 - Application to Adjust Status",
                "I-539 - Application to Extend/Change Status",
                "I-765 - Application for Employment Authorization",
                "N-400 - Application for Naturalization"
            ]
            
            selected_form = st.selectbox("Select form type:", common_forms)
            
            if selected_form != "Custom/Other":
                form_type = selected_form
            else:
                form_type = st.text_input("Enter custom form type:", placeholder="e.g., I-129")
            
            if form_type:
                st.session_state.form_type = form_type
        
        with col2:
            uploaded_file = st.file_uploader(
                "Upload PDF Form",
                type=['pdf'],
                help="Upload the USCIS PDF form you want to map"
            )
            
            if uploaded_file and form_type:
                if st.button("🔍 Extract Fields", type="primary", use_container_width=True):
                    with st.spinner("Extracting PDF fields..."):
                        fields = mapper.extract_pdf_fields(uploaded_file, form_type)
                        if fields:
                            st.session_state.pdf_fields = fields
                            st.success(f"Extracted {len(fields)} fields!")
    
    # Display results
    if 'pdf_fields' in st.session_state and st.session_state.pdf_fields:
        st.header("📊 Extraction Results")
        
        fields = st.session_state.pdf_fields
        
        # Export section
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📄 TypeScript Export")
            ts_content = mapper.generate_typescript_export(st.session_state.form_type, fields)
            st.download_button(
                label="📥 Download TypeScript",
                data=ts_content,
                file_name=f"{st.session_state.form_type.split(' - ')[0].replace(' ', '')}.ts",
                mime="text/plain"
            )
            with st.expander("Preview TypeScript"):
                st.code(ts_content[:500] + "\n...", language="typescript")
        
        with col2:
            st.subheader("📋 Questionnaire JSON")
            json_content = mapper.generate_questionnaire_json(fields)
            st.download_button(
                label="📥 Download JSON",
                data=json_content,
                file_name=f"{st.session_state.form_type.split(' - ')[0].lower()}-questionnaire.json",
                mime="application/json"
            )
            with st.expander("Preview JSON"):
                st.code(json_content[:500] + "\n...", language="json")

if __name__ == "__main__":
    main()
