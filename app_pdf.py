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
                "spouseUscisReceipt"
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

# Enhanced Field Pattern Matching
FIELD_PATTERNS = {
    # Names
    "lastName": {
        "patterns": [r"last\s*name", r"family\s*name", r"surname", r"apellido"],
        "keywords": ["last", "family", "surname"],
        "priority": 10
    },
    "firstName": {
        "patterns": [r"first\s*name", r"given\s*name", r"nombre"],
        "keywords": ["first", "given"],
        "priority": 10
    },
    "middleName": {
        "patterns": [r"middle\s*name", r"middle\s*initial", r"m\.i\."],
        "keywords": ["middle"],
        "priority": 8
    },
    
    # Dates
    "dateOfBirth": {
        "patterns": [r"date.*birth", r"birth.*date", r"dob", r"fecha.*nacimiento"],
        "keywords": ["birth", "dob", "born"],
        "priority": 10
    },
    
    # Numbers
    "alienNumber": {
        "patterns": [r"alien\s*number", r"a[\-\s]*number", r"uscis\s*number", r"alien\s*registration"],
        "keywords": ["alien", "registration"],
        "priority": 9
    },
    "ssn": {
        "patterns": [r"social\s*security", r"ssn", r"ss\s*#"],
        "keywords": ["social", "security", "ssn"],
        "priority": 9
    },
    "receiptNumber": {
        "patterns": [r"receipt\s*number", r"case\s*number", r"receipt\s*#"],
        "keywords": ["receipt", "case"],
        "priority": 8
    },
    
    # Contact
    "phone": {
        "patterns": [r"phone", r"telephone", r"contact\s*number", r"daytime\s*phone", r"mobile"],
        "keywords": ["phone", "telephone", "mobile", "cell"],
        "priority": 7
    },
    "email": {
        "patterns": [r"email", r"e\-mail", r"electronic\s*mail", r"email\s*address"],
        "keywords": ["email", "mail"],
        "priority": 7
    },
    
    # Address
    "street": {
        "patterns": [r"street", r"address\s*1", r"address\s*line\s*1", r"street\s*address", r"mailing\s*address"],
        "keywords": ["street", "address"],
        "priority": 8
    },
    "city": {
        "patterns": [r"city", r"town", r"ciudad"],
        "keywords": ["city", "town"],
        "priority": 8
    },
    "state": {
        "patterns": [r"state", r"province", r"estado"],
        "keywords": ["state", "province"],
        "priority": 8
    },
    "zip": {
        "patterns": [r"zip", r"postal\s*code", r"zip\s*code", r"codigo\s*postal"],
        "keywords": ["zip", "postal"],
        "priority": 8
    },
    "country": {
        "patterns": [r"country", r"nation", r"pais"],
        "keywords": ["country", "nation"],
        "priority": 8
    },
    
    # Organization
    "companyName": {
        "patterns": [r"company\s*name", r"organization", r"employer\s*name", r"business\s*name", r"petitioner\s*name"],
        "keywords": ["company", "organization", "employer", "business", "petitioner"],
        "priority": 9
    },
    "jobTitle": {
        "patterns": [r"job\s*title", r"position", r"occupation", r"title"],
        "keywords": ["job", "title", "position", "occupation"],
        "priority": 7
    },
    
    # Legal
    "barNumber": {
        "patterns": [r"bar\s*number", r"state\s*bar", r"license\s*number", r"bar\s*#"],
        "keywords": ["bar", "license"],
        "priority": 8
    },
    "signature": {
        "patterns": [r"signature", r"sign", r"firma"],
        "keywords": ["signature", "sign"],
        "priority": 6
    },
    
    # Immigration specific
    "visaType": {
        "patterns": [r"visa\s*type", r"classification", r"visa\s*category", r"status"],
        "keywords": ["visa", "classification", "status"],
        "priority": 8
    },
    "passportNumber": {
        "patterns": [r"passport\s*number", r"passport\s*#", r"travel\s*document"],
        "keywords": ["passport"],
        "priority": 8
    },
    "i94Number": {
        "patterns": [r"i\-94", r"i94", r"arrival.*record"],
        "keywords": ["i94", "arrival"],
        "priority": 8
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
    mapping_type: str = "direct"  # direct, concatenated, conditional, default
    mapping_config: Optional[Dict[str, Any]] = None
    is_mapped: bool = False
    is_questionnaire: bool = False
    confidence_score: float = 0.0

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
        self.field_patterns = FIELD_PATTERNS
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
        """Extract all fields from any USCIS PDF form"""
        fields = []
        section_contexts = {}  # Store section descriptions
        
        try:
            pdf_bytes = pdf_file.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            # First pass: extract section headers and descriptions
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                
                # Look for section headers
                section_patterns = [
                    r'To be completed by (?:an )?attorney or BIA[\s-]*accredited representative',
                    r'Information About (?:the )?Petitioner',
                    r'Information About (?:the )?Beneficiary',
                    r'Information About (?:the )?Applicant',
                    r'Information About This Petition',
                    r'Processing Information',
                    r'Additional Information',
                    r'Petitioner[\s\']*s Statement',
                    r'Preparer[\s\']*s Statement',
                    r'Part\s*(\d+)[\s\-\.]*([A-Za-z\s]+)',
                    r'Section\s*([A-Z])[\s\-\.]*([A-Za-z\s]+)'
                ]
                
                for pattern in section_patterns:
                    matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
                    for match in matches:
                        section_desc = match.group(0)
                        # Store context for this page
                        if page_num not in section_contexts:
                            section_contexts[page_num] = []
                        section_contexts[page_num].append(section_desc.lower())
            
            # Second pass: extract fields with context
            field_index = 0
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_context = section_contexts.get(page_num, [])
                
                for widget in page.widgets():
                    if widget.field_name:
                        field_index += 1
                        
                        # Determine field type
                        field_type = self._get_field_type(widget)
                        
                        # Extract metadata with context
                        part = self._extract_part_with_context(widget.field_name, page_num, form_type, page_context)
                        item = self._extract_item(widget.field_name)
                        description = self._generate_description(widget.field_name, widget.field_display)
                        
                        # Create field object
                        pdf_field = PDFField(
                            index=field_index,
                            raw_name=widget.field_name,
                            field_type=field_type,
                            value=widget.field_value or '',
                            page=page_num + 1,
                            part=part,
                            item=item,
                            description=description
                        )
                        
                        # Get mapping suggestions with context
                        suggestions = self._get_mapping_suggestions_with_context(pdf_field, page_context)
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
            
        except Exception as e:
            st.error(f"Error extracting PDF: {str(e)}")
            return []
        
        return fields
    
    def _extract_part_with_context(self, field_name: str, page_num: int, form_type: str, page_context: List[str]) -> str:
        """Extract part/section with context awareness"""
        # Check page context for attorney section
        for context in page_context:
            if any(term in context for term in ['attorney', 'representative', 'bia-accredited', 'g-28']):
                return "Part 0 - Attorney/Representative"
            elif 'petitioner' in context and 'information' in context:
                return "Part 1 - Petitioner Information"
            elif 'beneficiary' in context and 'information' in context:
                return "Part 2 - Beneficiary Information"
            elif 'applicant' in context and 'information' in context:
                return "Part 1 - Applicant Information"
        
        # Fall back to original extraction
        return self._extract_part(field_name, page_num, form_type)
    
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
    
    def _extract_part(self, field_name: str, page_num: int, form_type: str) -> str:
        """Extract part/section from field name"""
        # Check if this is Part 0 or attorney section at the beginning
        if page_num == 0 or 'attorney' in field_name.lower() or 'representative' in field_name.lower():
            # Check for attorney-related patterns
            attorney_patterns = [
                r'attorney',
                r'representative',
                r'g-?28',
                r'appearance',
                r'bar\s*number',
                r'law\s*firm',
                r'bia[\s-]*accredited'
            ]
            
            for pattern in attorney_patterns:
                if re.search(pattern, field_name, re.IGNORECASE):
                    return "Part 0 - Attorney/Representative"
        
        # Common USCIS patterns
        patterns = [
            (r'Part\s*(\d+)', 'Part {}'),
            (r'Pt\s*(\d+)', 'Part {}'),
            (r'P(\d+)[_\.\-]', 'Part {}'),
            (r'part(\d+)', 'Part {}'),
            (r'Section\s*([A-Z])', 'Section {}'),
            (r'Section\s*(\d+)', 'Section {}'),
            (r'Page\s*(\d+)', 'Page {}'),
            (r'Part([IVX]+)', 'Part {}'),  # Roman numerals
        ]
        
        for pattern, format_str in patterns:
            match = re.search(pattern, field_name, re.IGNORECASE)
            if match:
                part_num = match.group(1)
                # If it's Part 0, label it as attorney section
                if part_num == '0':
                    return "Part 0 - Attorney/Representative"
                return format_str.format(part_num)
        
        # Special sections
        special_sections = {
            'signature': 'Signatures',
            'preparer': 'Preparer Information',
            'interpreter': 'Interpreter Information',
            'attorney': 'Part 0 - Attorney/Representative',
            'representative': 'Part 0 - Attorney/Representative',
            'supplement': 'Supplement',
            'additional': 'Additional Information',
            'certification': 'Certification'
        }
        
        field_lower = field_name.lower()
        for key, section in special_sections.items():
            if key in field_lower:
                return section
        
        # Default by page - if page 1, check if it's attorney section
        if page_num == 0:
            return "Part 0 - Attorney/Representative"
        return f"Page {page_num + 1}"
    
    def _extract_item(self, field_name: str) -> str:
        """Extract item number from field name"""
        patterns = [
            r'Item\s*(\d+[a-zA-Z]?)',
            r'Line\s*(\d+[a-zA-Z]?)',
            r'Question\s*(\d+[a-zA-Z]?)',
            r'[_\.\-](\d+[a-zA-Z]?)[_\.\-]',
            r'#(\d+[a-zA-Z]?)',
            r'No\.?\s*(\d+[a-zA-Z]?)',
            r'Number\s*(\d+[a-zA-Z]?)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, field_name, re.IGNORECASE)
            if match:
                return match.group(1)
        
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
    
    def _get_mapping_suggestions(self, field: PDFField) -> List[MappingSuggestion]:
        """Get intelligent mapping suggestions for a field"""
        suggestions = []
        
        # Normalize field info for matching
        field_name_lower = field.raw_name.lower()
        desc_lower = field.description.lower()
        
        # 1. Check for exact pattern matches
        for pattern_key, pattern_info in self.field_patterns.items():
            confidence = 0.0
            matched = False
            
            # Check regex patterns
            for pattern in pattern_info['patterns']:
                if re.search(pattern, field_name_lower) or re.search(pattern, desc_lower):
                    confidence = pattern_info['priority'] / 10.0
                    matched = True
                    break
            
            # Check keywords if no pattern match
            if not matched:
                for keyword in pattern_info['keywords']:
                    if keyword in field_name_lower or keyword in desc_lower:
                        confidence = (pattern_info['priority'] - 2) / 10.0
                        matched = True
                        break
            
            if matched:
                # Find corresponding database fields
                db_paths = self._find_db_paths_for_pattern(pattern_key)
                for db_path in db_paths:
                    suggestions.append(MappingSuggestion(
                        db_path=db_path,
                        confidence=confidence,
                        reason=f"Pattern match: {pattern_key}"
                    ))
        
        # 2. Check for contextual matches
        context_suggestions = self._get_contextual_suggestions(field)
        suggestions.extend(context_suggestions)
        
        # 3. Check for similar field names in DB
        similarity_suggestions = self._get_similarity_suggestions(field)
        suggestions.extend(similarity_suggestions)
        
        # Sort by confidence
        suggestions.sort(key=lambda x: x.confidence, reverse=True)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_suggestions = []
        for sugg in suggestions:
            if sugg.db_path not in seen:
                seen.add(sugg.db_path)
                unique_suggestions.append(sugg)
        
        return unique_suggestions[:5]  # Return top 5 suggestions
    
    def _find_db_paths_for_pattern(self, pattern_key: str) -> List[str]:
        """Find database paths that match a pattern key"""
        paths = []
        
        # Map pattern keys to database field names
        pattern_to_db_mapping = {
            "lastName": ["lastName", "beneficiaryLastName", "signatory_last_name"],
            "firstName": ["firstName", "beneficiaryFirstName", "signatory_first_name"],
            "middleName": ["middleName", "beneficiaryMiddleName", "signatory_middle_name"],
            "dateOfBirth": ["dateOfBirth", "beneficiaryDateOfBirth"],
            "alienNumber": ["alienNumber", "gcAlienNumber"],
            "ssn": ["ssn", "beneficiarySsn"],
            "phone": ["phone", "workPhone", "mobilePhone", "beneficiaryCellNumber", "signatory_work_phone"],
            "email": ["email", "emailAddress", "beneficiaryPrimaryEmailAddress", "signatory_email_id"],
            "street": ["addressStreet", "address_street"],
            "city": ["addressCity", "address_city"],
            "state": ["addressState", "address_state"],
            "zip": ["addressZip", "address_zip"],
            "country": ["addressCountry", "address_country", "beneficiaryCountryOfBirth"],
            "companyName": ["customer_name", "lawFirmName", "employerName"],
            "jobTitle": ["jobTitle", "positionJobTitle", "signatory_job_title"],
            "barNumber": ["stateBarNumber"],
            "signature": ["signature", "signatory_digital_signature"],
            "visaType": ["visaStatus", "caseType"],
            "passportNumber": ["passportNumber"],
            "i94Number": ["i94Number"],
            "receiptNumber": ["h1bReceiptNumber", "gcReceiptNumber"]
        }
        
        target_fields = pattern_to_db_mapping.get(pattern_key, [pattern_key])
        
        # Search through database structure
        for obj_name, obj_structure in self.db_objects.items():
            paths.extend(self._search_in_object(obj_name, obj_structure, target_fields))
        
        return paths
    
    def _search_in_object(self, obj_name: str, obj_structure: Any, target_fields: List[str], prefix: str = "") -> List[str]:
        """Recursively search for fields in database object"""
        paths = []
        current_prefix = f"{obj_name}{prefix}" if prefix else obj_name
        
        if isinstance(obj_structure, dict):
            for key, value in obj_structure.items():
                if isinstance(value, list):
                    # Check fields in list
                    for field in value:
                        if any(target in field.lower() for target in [t.lower() for t in target_fields]):
                            if key:
                                paths.append(f"{current_prefix}.{key}.{field}")
                            else:
                                paths.append(f"{current_prefix}.{field}")
                else:
                    # Recursive search
                    sub_paths = self._search_in_object("", value, target_fields, f"{prefix}.{key}" if prefix else f".{key}")
                    paths.extend([f"{obj_name}{path}" for path in sub_paths])
        
        return paths
    
    def _get_mapping_suggestions_with_context(self, field: PDFField, page_context: List[str]) -> List[MappingSuggestion]:
        """Get mapping suggestions with page context awareness"""
        suggestions = []
        
        # Determine primary object based on context
        primary_object = None
        if any('attorney' in ctx or 'representative' in ctx for ctx in page_context):
            primary_object = 'attorney'
        elif any('petitioner' in ctx for ctx in page_context):
            primary_object = 'customer'
        elif any('beneficiary' in ctx for ctx in page_context):
            primary_object = 'beneficiary'
        elif any('applicant' in ctx for ctx in page_context):
            # Applicant could be beneficiary or customer depending on form
            primary_object = 'beneficiary'
        
        # Get base suggestions
        base_suggestions = self._get_mapping_suggestions(field)
        
        # Boost suggestions that match the primary object
        if primary_object:
            for suggestion in base_suggestions:
                if suggestion.db_path.startswith(primary_object):
                    suggestion.confidence = min(suggestion.confidence * 1.5, 1.0)
                    suggestion.reason += f" (Context: {primary_object})"
        
        # Re-sort by confidence
        base_suggestions.sort(key=lambda x: x.confidence, reverse=True)
        
        return base_suggestions
    
    def _get_contextual_suggestions(self, field: PDFField) -> List[MappingSuggestion]:
        """Get suggestions based on field context (part, item, page)"""
        suggestions = []
        
        # Enhanced context-based rules
        context_rules = {
            "Part 0 - Attorney/Representative": {
                "patterns": ["attorney", "lawyer", "representative", "bar", "firm"],
                "object": "attorney",
                "boost": 0.9
            },
            "Part 1": {
                "patterns": ["petitioner", "company", "organization", "employer"],
                "object": "customer",
                "boost": 0.8
            },
            "Petitioner Information": {
                "patterns": ["petitioner", "company", "employer"],
                "object": "customer",
                "boost": 0.9
            },
            "Part 2": {
                "patterns": ["beneficiary", "worker", "employee", "alien"],
                "object": "beneficiary",
                "boost": 0.8
            },
            "Beneficiary Information": {
                "patterns": ["beneficiary", "worker"],
                "object": "beneficiary",
                "boost": 0.9
            },
            "Part 3": {
                "patterns": ["beneficiary", "information about"],
                "object": "beneficiary",
                "boost": 0.7
            },
            "Attorney": {
                "patterns": ["attorney", "lawyer", "representative"],
                "object": "attorney",
                "boost": 0.95
            },
            "Signature": {
                "patterns": ["signature", "sign", "date"],
                "object": "signatory",
                "boost": 0.7
            }
        }
        
        # Check if field's part matches any context
        for context, rule in context_rules.items():
            if context.lower() in field.part.lower() or field.part.lower() in context.lower():
                # Look for fields in the suggested object
                obj_name = rule['object']
                if obj_name in self.db_objects:
                    # Check if field description matches patterns
                    matches_pattern = any(pattern in field.description.lower() for pattern in rule['patterns'])
                    
                    if matches_pattern or rule['boost'] > 0.8:
                        # Add targeted suggestions
                        paths = self._search_in_object(obj_name, self.db_objects[obj_name], [])
                        for path in paths[:5]:  # Limit suggestions
                            # Match field name patterns
                            field_name = path.split('.')[-1]
                            if self._is_field_match(field.description, field_name):
                                suggestions.append(MappingSuggestion(
                                    db_path=path,
                                    confidence=rule['boost'],
                                    reason=f"Context match: {context}"
                                ))
        
        return suggestions
    
    def _is_field_match(self, field_desc: str, db_field: str) -> bool:
        """Check if field description matches database field"""
        # Normalize for comparison
        field_desc_norm = field_desc.lower().replace(' ', '').replace('_', '')
        db_field_norm = db_field.lower().replace('_', '')
        
        # Direct substring match
        if db_field_norm in field_desc_norm or field_desc_norm in db_field_norm:
            return True
        
        # Check common variations
        variations = {
            'firstname': ['first', 'given'],
            'lastname': ['last', 'family', 'surname'],
            'middlename': ['middle', 'mi'],
            'dob': ['birth', 'dateofbirth'],
            'ssn': ['social', 'security'],
            'phone': ['telephone', 'phone', 'contact'],
            'email': ['email', 'mail'],
            'street': ['address', 'street'],
            'zip': ['zip', 'postal']
        }
        
        for key, values in variations.items():
            if key in db_field_norm:
                if any(v in field_desc_norm for v in values):
                    return True
        
        return False
    
    def _get_similarity_suggestions(self, field: PDFField) -> List[MappingSuggestion]:
        """Get suggestions based on string similarity"""
        suggestions = []
        
        # Collect all database field names with their paths
        all_fields = []
        for obj_name, obj_structure in self.db_objects.items():
            self._collect_fields(obj_name, obj_structure, all_fields)
        
        # Calculate similarity scores
        field_desc_normalized = field.description.lower().replace(' ', '').replace('_', '')
        
        for db_path, db_field in all_fields:
            db_field_normalized = db_field.lower().replace('_', '')
            
            # Use difflib for similarity
            similarity = difflib.SequenceMatcher(None, field_desc_normalized, db_field_normalized).ratio()
            
            if similarity > 0.6:  # Threshold for similarity
                suggestions.append(MappingSuggestion(
                    db_path=db_path,
                    confidence=similarity * 0.8,  # Scale down confidence
                    reason=f"Similar to: {db_field}"
                ))
        
        return suggestions
    
    def _collect_fields(self, obj_name: str, obj_structure: Any, result: List[Tuple[str, str]], prefix: str = ""):
        """Recursively collect all field paths and names"""
        current_prefix = f"{obj_name}{prefix}" if obj_name else prefix
        
        if isinstance(obj_structure, dict):
            for key, value in obj_structure.items():
                if isinstance(value, list):
                    for field in value:
                        if key:
                            result.append((f"{current_prefix}.{key}.{field}", field))
                        else:
                            result.append((f"{current_prefix}.{field}", field))
                else:
                    new_prefix = f"{prefix}.{key}" if prefix else key
                    if obj_name:
                        self._collect_fields("", value, result, new_prefix)
                    else:
                        self._collect_fields("", value, result, f"{current_prefix}.{key}")
    
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
            field.db_mapping = f"Default Value: {mapping_config.get('value')}"
        elif mapping_type == "questionnaire":
            field.is_questionnaire = True
            field.is_mapped = False
    
    def generate_typescript_export(self, form_type: str, fields: List[PDFField]) -> str:
        """Generate TypeScript mapping file"""
        form_name = form_type.replace("-", "").replace(" ", "")
        
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
            if field.is_mapped and field.db_mapping:
                if field.mapping_type == "direct":
                    # Determine category based on path
                    if field.db_mapping.startswith('customer'):
                        categories['customerData'][field.raw_name] = field.db_mapping
                    elif field.db_mapping.startswith('beneficiary'):
                        categories['beneficiaryData'][field.raw_name] = field.db_mapping
                    elif field.db_mapping.startswith('attorney'):
                        categories['attorneyData'][field.raw_name] = field.db_mapping
                    elif field.db_mapping.startswith('case'):
                        categories['caseData'][field.raw_name] = field.db_mapping
                    elif field.db_mapping.startswith('lca'):
                        categories['lcaData'][field.raw_name] = field.db_mapping
                elif field.mapping_type == "default":
                    categories['defaultData'][field.raw_name] = field.db_mapping
                elif field.mapping_type == "conditional":
                    categories['conditionalData'][field.raw_name] = field.mapping_config
                elif field.mapping_type == "concatenated":
                    # Add to appropriate category based on first field
                    if field.mapping_config.get('fields'):
                        first_field = field.mapping_config['fields'][0]
                        if first_field.startswith('customer'):
                            categories['customerData'][field.raw_name] = field.mapping_config
                        elif first_field.startswith('beneficiary'):
                            categories['beneficiaryData'][field.raw_name] = field.mapping_config
                        elif first_field.startswith('attorney'):
                            categories['attorneyData'][field.raw_name] = field.mapping_config
            elif field.is_questionnaire or (not field.is_mapped and not field.db_mapping):
                # Include all questionnaire fields (explicit and auto-assigned)
                categories['questionnaireData'][field.raw_name] = {
                    'name': f"q_{field.index}",
                    'type': field.field_type,
                    'description': field.description,
                    'part': field.part,
                    'item': field.item
                }
        
        # Calculate accurate counts
        questionnaire_count = len(categories['questionnaireData'])
        mapped_count = sum(1 for f in fields if f.is_mapped)
        unmapped_count = sum(1 for f in fields if not f.is_mapped and not f.is_questionnaire and f.db_mapping)
        
        # Generate TypeScript
        ts_content = f"""// Auto-generated mapping for {form_type}
// Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
// Universal USCIS Form Mapper

export const {form_name} = {{
    "formname": "{form_name}",
    "formTitle": "{form_type}",
    "customerData": {json.dumps(categories['customerData'], indent=8) if categories['customerData'] else 'null'},
    "beneficiaryData": {json.dumps(categories['beneficiaryData'], indent=8) if categories['beneficiaryData'] else 'null'},
    "attorneyData": {json.dumps(categories['attorneyData'], indent=8) if categories['attorneyData'] else 'null'},
    "questionnaireData": {json.dumps(categories['questionnaireData'], indent=8) if categories['questionnaireData'] else '{}'},
    "defaultData": {json.dumps(categories['defaultData'], indent=8) if categories['defaultData'] else '{}'},
    "conditionalData": {json.dumps(categories['conditionalData'], indent=8) if categories['conditionalData'] else '{}'},
    "pdfName": "{form_type.lower().replace(' ', '-')}.pdf",
    "caseData": {json.dumps(categories['caseData'], indent=8) if categories['caseData'] else 'null'},
    "lcaData": {json.dumps(categories['lcaData'], indent=8) if categories['lcaData'] else 'null'},
    "mappingMetadata": {{
        "totalFields": {len(fields)},
        "mappedFields": {mapped_count},
        "questionnaireFields": {questionnaire_count},
        "unmappedFields": {unmapped_count},
        "mappingScore": {self._calculate_mapping_score(fields):.1f},
        "generatedBy": "Universal USCIS Form Mapper",
        "formVersion": "Latest",
        "mappingNotes": {{
            "Part 0": "Attorney/Representative Information",
            "unmappedHandling": "All unmapped fields automatically added to questionnaire"
        }}
    }}
}}"""
        
        return ts_content
    
    def generate_questionnaire_json(self, fields: List[PDFField]) -> str:
        """Generate questionnaire JSON"""
        controls = []
        
        for field in fields:
            if field.is_questionnaire or (not field.is_mapped and not field.db_mapping):
                control = {
                    "name": f"q_{field.index}",
                    "label": field.description,
                    "type": self._get_questionnaire_type(field.field_type),
                    "validators": {"required": False},
                    "style": {"col": "12"},
                    "metadata": {
                        "pdfField": field.raw_name,
                        "part": field.part,
                        "item": field.item,
                        "page": field.page,
                        "fieldType": field.field_type
                    }
                }
                
                # Add specific properties based on field type
                if field.field_type == "select" or field.field_type == "radio":
                    control["options"] = []  # To be filled by user
                elif field.field_type == "checkbox":
                    control["type"] = "colorSwitch"
                elif field.field_type == "date":
                    control["type"] = "date"
                    control["format"] = "MM/DD/YYYY"
                
                controls.append(control)
        
        questionnaire = {
            "formId": st.session_state.get('form_type', 'Unknown'),
            "version": "1.0",
            "generatedDate": datetime.now().isoformat(),
            "controls": controls
        }
        
        return json.dumps(questionnaire, indent=2)
    
    def _get_questionnaire_type(self, field_type: str) -> str:
        """Map field type to questionnaire control type"""
        type_mapping = {
            "text": "text",
            "checkbox": "colorSwitch",
            "radio": "radio",
            "select": "select",
            "date": "date",
            "signature": "text",
            "listbox": "select"
        }
        return type_mapping.get(field_type, "text")
    
    def _calculate_mapping_score(self, fields: List[PDFField]) -> float:
        """Calculate overall mapping score"""
        if not fields:
            return 0.0
        
        total = len(fields)
        mapped = sum(1 for f in fields if f.is_mapped)
        questionnaire = sum(1 for f in fields if f.is_questionnaire)
        
        # Mapped fields get 100%, questionnaire fields get 50%
        score = ((mapped * 100) + (questionnaire * 50)) / total
    def _get_object_index(self, db_path: str) -> int:
        """Get index of object from db_path"""
        if db_path:
            obj_name = db_path.split('.')[0]
            objects = list(self.db_objects.keys())
            if obj_name in objects:
                return objects.index(obj_name)
        return 0

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
            form_type = selected_form.split(" - ")[0]
        
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
            with st.spinner("Extracting PDF fields and analyzing patterns..."):
                # Extract fields
                fields = mapper.extract_pdf_fields(uploaded_file, form_type)
                
                if fields:
                    st.session_state.pdf_fields = fields
                    st.session_state.field_mappings = {f.raw_name: f for f in fields}
                    
                    # Show extraction summary
                    st.success(f"✅ Successfully extracted {len(fields)} fields")
                    
                    # Display metrics
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Fields", len(fields))
                    with col2:
                        mapped = sum(1 for f in fields if f.db_mapping)
                        st.metric("Auto-Mapped", mapped)
                    with col3:
                        high_conf = sum(1 for f in fields if f.confidence_score > 0.8)
                        st.metric("High Confidence", high_conf)
                    with col4:
                        score = mapper._calculate_mapping_score(fields)
                        st.metric("Mapping Score", f"{score}%")
                else:
                    st.error("No fields found in the PDF. Please ensure it's a fillable PDF form.")

def render_mapping_section(mapper: UniversalUSCISMapper):
    """Render field mapping section"""
    if 'pdf_fields' not in st.session_state or not st.session_state.pdf_fields:
        st.info("👆 Please upload a PDF form first")
        return
    
    st.header("🗺️ Field Mapping Configuration")
    
    # Info box about automatic questionnaire assignment
    st.info("ℹ️ **Note**: All unmapped fields are automatically added to the questionnaire. You can change this by selecting a different mapping type.")
    
    # Filters
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        parts = list(set(f.part for f in st.session_state.pdf_fields))
        # Sort parts with Part 0 first
        sorted_parts = []
        if "Part 0 - Attorney/Representative" in parts:
            sorted_parts.append("Part 0 - Attorney/Representative")
        sorted_parts.extend([p for p in sorted(parts) if p != "Part 0 - Attorney/Representative"])
        
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
                field.db_mapping = None
            st.rerun()
    
    # Filter fields
    filtered_fields = []
    for field in st.session_state.pdf_fields:
        # Part filter
        if selected_part != "All" and field.part != selected_part:
            continue
        
        # Status filter
        if status_filter == "Mapped" and not field.is_mapped:
            continue
        elif status_filter == "Suggested" and field.db_mapping and not field.is_mapped:
            continue
        elif status_filter == "Questionnaire" and not field.is_questionnaire:
            continue
        elif status_filter == "Unmapped" and (field.is_mapped or field.is_questionnaire or field.db_mapping):
            continue
        
        # Type filter
        if type_filter != "All" and field.field_type != type_filter:
            continue
        
        # Search filter
        if search_term:
            search_lower = search_term.lower()
            if not any(search_lower in str(getattr(field, attr, '')).lower() 
                      for attr in ['raw_name', 'description', 'item', 'db_mapping']):
                continue
        
        filtered_fields.append(field)
    
    # Display fields
    st.write(f"Showing **{len(filtered_fields)}** of **{len(st.session_state.pdf_fields)}** fields")
    
    # Group by parts
    fields_by_part = defaultdict(list)
    for field in filtered_fields:
        fields_by_part[field.part].append(field)
    
    # Sort parts with Part 0 first
    sorted_parts_display = []
    if "Part 0 - Attorney/Representative" in fields_by_part:
        sorted_parts_display.append(("Part 0 - Attorney/Representative", fields_by_part["Part 0 - Attorney/Representative"]))
    
    for part in sorted(fields_by_part.keys()):
        if part != "Part 0 - Attorney/Representative":
            sorted_parts_display.append((part, fields_by_part[part]))
    
    for part, fields in sorted_parts_display:
        # Special styling for Part 0
        if "Part 0" in part:
            with st.expander(f"⚖️ {part} ({len(fields)} fields)", expanded=True):
                st.info("This section contains attorney/representative information fields")
                for field in fields:
                    render_field_mapping_card(field, mapper)
        else:
            with st.expander(f"📑 {part} ({len(fields)} fields)", expanded=True):
                for field in fields:
                    render_field_mapping_card(field, mapper)

def render_field_mapping_card(field: PDFField, mapper: UniversalUSCISMapper):
    """Render individual field mapping card"""
    with st.container():
        st.markdown('<div class="field-card">', unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([5, 4, 1])
        
        with col1:
            # Field info
            st.markdown(f"**{field.item}** {field.description}")
            st.caption(f"Field: `{field.raw_name}` | Type: {field.field_type} | Page: {field.page}")
            
            # Current mapping status
            if field.is_mapped:
                st.markdown(f'<span class="mapping-badge mapped">✅ Mapped to: {field.db_mapping}</span>', unsafe_allow_html=True)
            elif field.db_mapping and field.confidence_score > 0:
                confidence_class = "high" if field.confidence_score > 0.8 else "medium" if field.confidence_score > 0.6 else "low"
                st.markdown(f'<span class="mapping-badge questionnaire">💡 Suggested: {field.db_mapping} <span class="confidence-{confidence_class}">({field.confidence_score:.0%})</span></span>', unsafe_allow_html=True)
            elif field.is_questionnaire:
                st.markdown('<span class="mapping-badge questionnaire">📋 In Questionnaire (auto-assigned)</span>', unsafe_allow_html=True)
            else:
                st.markdown('<span class="mapping-badge unmapped">❌ Not mapped</span>', unsafe_allow_html=True)
        
        with col2:
            # Mapping controls
            mapping_options = ["Keep Current", "Direct", "Concatenated", "Conditional", "Default Value", "Questionnaire", "Skip"]
            
            # Default selection based on current state
            if field.is_mapped:
                default_option = "Keep Current"
            elif field.is_questionnaire:
                default_option = "Questionnaire"
            elif field.db_mapping:
                default_option = "Direct"
            else:
                default_option = "Questionnaire"
            
            mapping_type = st.selectbox(
                "Mapping Type",
                mapping_options,
                index=mapping_options.index(default_option),
                key=f"type_{field.index}"
            )
            
            if mapping_type == "Direct":
                # Show suggested mapping if available
                if field.db_mapping and not field.is_mapped:
                    st.info(f"Suggested: {field.db_mapping}")
                
                # Database path selector
                default_obj_index = 0
                if field.db_mapping and not field.is_mapped:
                    default_obj_index = mapper._get_object_index(field.db_mapping)
                
                obj_name = st.selectbox(
                    "Object",
                    list(mapper.db_objects.keys()),
                    key=f"obj_{field.index}",
                    index=default_obj_index
                )
                
                # Build path selector dynamically
                if obj_name:
                    paths = []
                    mapper._collect_fields(obj_name, mapper.db_objects[obj_name], paths)
                    if paths:
                        # Get current selection or default
                        current_selection = 0
                        if field.db_mapping and field.db_mapping.startswith(obj_name):
                            for i, (path, _) in enumerate(paths):
                                if path == field.db_mapping:
                                    current_selection = i
                                    break
                        
                        selected_path = st.selectbox(
                            "Field",
                            [p[0] for p in paths],
                            index=current_selection,
                            format_func=lambda x: x.split('.')[-1] + " (" + x + ")",
                            key=f"path_{field.index}"
                        )
            
            elif mapping_type == "Default Value":
                default_val = st.text_input(
                    "Default Value",
                    key=f"default_{field.index}"
                )
            
            elif mapping_type == "Concatenated":
                st.write("Select fields to concatenate:")
                num_fields = st.number_input("Number of fields", min_value=2, max_value=5, value=2, key=f"concat_num_{field.index}")
                concat_fields = []
                for i in range(int(num_fields)):
                    obj = st.selectbox(f"Object {i+1}", list(mapper.db_objects.keys()), key=f"concat_obj_{field.index}_{i}")
                    # Add field selector
            
            elif mapping_type == "Conditional":
                st.write("Define condition:")
                condition = st.text_area("Condition", key=f"condition_{field.index}", height=60)
                true_value = st.text_input("If True", key=f"true_{field.index}")
                false_value = st.text_input("If False", key=f"false_{field.index}")
        
        with col3:
            # Action buttons
            if mapping_type != "Keep Current":
                if st.button("💾", key=f"save_{field.index}", help="Save mapping"):
                    if mapping_type == "Direct" and 'selected_path' in locals():
                        mapper.create_mapping(field, "direct", {"path": selected_path})
                    elif mapping_type == "Default Value" and 'default_val' in locals():
                        mapper.create_mapping(field, "default", {"value": default_val})
                    elif mapping_type == "Questionnaire":
                        mapper.create_mapping(field, "questionnaire", {})
                    elif mapping_type == "Skip":
                        field.is_mapped = False
                        field.is_questionnaire = False
                    st.rerun()
            
            if field.db_mapping and not field.is_mapped and st.button("✅", key=f"accept_{field.index}", help="Accept suggestion"):
                field.is_mapped = True
                mapper.create_mapping(field, "direct", {"path": field.db_mapping})
                st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)

def _get_object_index(db_path: str, db_objects: dict) -> int:
    """Get index of object from db_path"""
    if db_path:
        obj_name = db_path.split('.')[0]
        objects = list(db_objects.keys())
        if obj_name in objects:
            return objects.index(obj_name)
    return 0

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
        st.metric("Score", f"{mapper._calculate_mapping_score(fields)}%")
    
    st.markdown("---")
    
    # Export options
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📄 TypeScript Export")
        st.write("Generate TypeScript mapping file for your application")
        
        # Options
        include_metadata = st.checkbox("Include metadata", value=True)
        include_comments = st.checkbox("Include field comments", value=True)
        
        ts_content = mapper.generate_typescript_export(form_type, fields)
        
        st.download_button(
            label="📥 Download TypeScript File",
            data=ts_content,
            file_name=f"{form_type.replace(' ', '').replace('-', '')}_mapping.ts",
            mime="text/plain",
            use_container_width=True
        )
        
        with st.expander("Preview TypeScript"):
            st.code(ts_content[:1000] + "\n...", language="typescript")
    
    with col2:
        st.subheader("📋 Questionnaire JSON")
        st.write("Generate questionnaire configuration for unmapped fields")
        
        # Options
        include_all_unmapped = st.checkbox("Include all unmapped fields", value=True)
        group_by_part = st.checkbox("Group by part", value=False)
        
        json_content = mapper.generate_questionnaire_json(fields)
        
        st.download_button(
            label="📥 Download Questionnaire JSON",
            data=json_content,
            file_name=f"{form_type.lower().replace(' ', '-')}_questionnaire.json",
            mime="application/json",
            use_container_width=True
        )
        
        with st.expander("Preview JSON"):
            st.code(json_content[:1000] + "\n...", language="json")
    
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
                    'Description': field.description,
                    'Type': field.field_type,
                    'Part': field.part,
                    'Item': field.item,
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
        # Export validation report
        if st.button("🔍 Generate Validation Report", use_container_width=True):
            st.info("Validation report generation in progress...")
    
    with col3:
        # Export for review
        if st.button("👥 Export for Review", use_container_width=True):
            st.info("Review export generation in progress...")

def _get_object_index(db_path: str, db_objects: dict) -> int:
    """Get index of object from db_path"""
    if db_path:
        obj_name = db_path.split('.')[0]
        objects = list(db_objects.keys())
        if obj_name in objects:
            return objects.index(obj_name)
    return 0

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
            truly_unmapped = sum(1 for f in fields if not f.is_mapped and not f.is_questionnaire and not f.db_mapping)
            
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
            
            # Distribution
            st.write("**Field Distribution**")
            distribution_df = pd.DataFrame({
                'Status': ['Mapped', 'Suggested', 'Questionnaire', 'Unmapped'],
                'Count': [mapped, suggested, questionnaire, truly_unmapped]
            })
            st.bar_chart(distribution_df.set_index('Status'))
            
            # Part breakdown
            st.write("**Fields by Part**")
            parts_count = defaultdict(int)
            for field in fields:
                parts_count[field.part] += 1
            
            # Sort with Part 0 first
            sorted_parts = []
            if "Part 0 - Attorney/Representative" in parts_count:
                sorted_parts.append(("Part 0 - Attorney/Representative", parts_count["Part 0 - Attorney/Representative"]))
            
            for part, count in sorted(parts_count.items()):
                if part != "Part 0 - Attorney/Representative":
                    sorted_parts.append((part, count))
            
            for part, count in sorted_parts:
                if "Part 0" in part:
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
        
        # Add note about Part 0
        st.markdown("---")
        st.markdown("### ℹ️ Mapping Tips")
        st.markdown("- **Part 0**: Attorney/Representative info")
        st.markdown("- **Part 1**: Usually Petitioner/Applicant")
        st.markdown("- **Part 2+**: Usually Beneficiary info")
        st.markdown("- **Unmapped**: Auto-added to questionnaire")
    
    # Main content tabs
    tabs = st.tabs(["📤 Upload & Extract", "🗺️ Field Mapping", "📥 Export", "⚙️ Settings"])
    
    with tabs[0]:
        render_upload_section(mapper)
    
    with tabs[1]:
        render_mapping_section(mapper)
    
    with tabs[2]:
        render_export_section(mapper)
    
    with tabs[3]:
        st.header("⚙️ Settings")
        st.write("Configure mapping preferences and defaults")
        
        # Mapping preferences
        st.subheader("Mapping Preferences")
        auto_accept_high = st.checkbox("Auto-accept high confidence mappings (>80%)", value=True)
        include_suggestions = st.checkbox("Show mapping suggestions", value=True)
        
        # Export preferences
        st.subheader("Export Preferences")
        default_format = st.selectbox("Default export format", ["TypeScript", "JavaScript", "JSON"])
        include_unmapped = st.checkbox("Include unmapped fields in export", value=True)
        
        # Database settings
        st.subheader("Database Configuration")
        if st.button("View Database Schema"):
            st.json(DB_OBJECTS)

if __name__ == "__main__":
    main()
