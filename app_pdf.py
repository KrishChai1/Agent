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

# Comprehensive USCIS Forms Database
USCIS_FORMS_DATABASE = {
    "I-90": {
        "title": "Application to Replace Permanent Resident Card",
        "keywords": ["permanent resident card", "green card", "replace", "renew"],
        "identifier_patterns": ["Form I-90", "I-90", "OMB No. 1615-0052"]
    },
    "I-129": {
        "title": "Petition for a Nonimmigrant Worker",
        "keywords": ["nonimmigrant worker", "h1b", "l1", "petition"],
        "identifier_patterns": ["Form I-129", "I-129", "OMB No. 1615-0009"]
    },
    "I-130": {
        "title": "Petition for Alien Relative",
        "keywords": ["alien relative", "family", "petition"],
        "identifier_patterns": ["Form I-130", "I-130", "OMB No. 1615-0012"]
    },
    "I-131": {
        "title": "Application for Travel Document",
        "keywords": ["travel document", "reentry permit", "refugee travel"],
        "identifier_patterns": ["Form I-131", "I-131", "OMB No. 1615-0013"]
    },
    "I-140": {
        "title": "Immigrant Petition for Alien Workers",
        "keywords": ["immigrant petition", "alien worker", "employment based"],
        "identifier_patterns": ["Form I-140", "I-140", "OMB No. 1615-0015"]
    },
    "I-485": {
        "title": "Application to Register Permanent Residence or Adjust Status",
        "keywords": ["adjust status", "permanent residence", "green card application"],
        "identifier_patterns": ["Form I-485", "I-485", "OMB No. 1615-0023"]
    },
    "I-539": {
        "title": "Application To Extend/Change Nonimmigrant Status",
        "keywords": ["extend status", "change status", "nonimmigrant"],
        "identifier_patterns": ["Form I-539", "I-539", "OMB No. 1615-0003"]
    },
    "I-765": {
        "title": "Application for Employment Authorization",
        "keywords": ["employment authorization", "work permit", "ead"],
        "identifier_patterns": ["Form I-765", "I-765", "OMB No. 1615-0040"]
    },
    "N-400": {
        "title": "Application for Naturalization",
        "keywords": ["naturalization", "citizenship", "citizen"],
        "identifier_patterns": ["Form N-400", "N-400", "OMB No. 1615-0052"]
    }
}

# Database Object Structure
DB_OBJECTS = {
    "attorney": {
        "attorneyInfo": [
            "firstName", "lastName", "middleName", "workPhone", "mobilePhone", 
            "emailAddress", "faxNumber", "stateBarNumber", "licensingAuthority"
        ],
        "address": [
            "addressStreet", "addressCity", "addressState", "addressZip", 
            "addressCountry"
        ]
    },
    "attorneyLawfirmDetails": {
        "lawfirmDetails": ["lawFirmName", "lawFirmFein"],
        "address": [
            "addressStreet", "addressCity", "addressState", "addressZip", 
            "addressCountry"
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
            "addressStreet", "addressCity", "addressState", "addressZip", 
            "addressCountry"
        ],
        "MailingAddress": [
            "addressStreet", "addressCity", "addressState", "addressZip", 
            "addressCountry"
        ],
        "PassportDetails": {
            "Passport": [
                "passportNumber", "passportIssueCountry", 
                "passportIssueDate", "passportExpiryDate"
            ]
        },
        "VisaDetails": {
            "Visa": [
                "visaStatus", "visaExpiryDate", "visaNumber"
            ]
        },
        "I94Details": {
            "I94": [
                "i94Number", "i94ArrivalDate", "i94ExpiryDate"
            ]
        }
    },
    "customer": {
        "": [
            "customer_name", "customer_type_of_business", "customer_tax_id", 
            "customer_naics_code", "customer_total_employees"
        ],
        "signatory": [
            "signatory_first_name", "signatory_last_name", "signatory_middle_name",
            "signatory_job_title", "signatory_work_phone", "signatory_email_id"
        ],
        "address": [
            "address_street", "address_city", "address_state", "address_zip",
            "address_country"
        ]
    }
}

# NLP Keywords for intelligent mapping
NLP_KEYWORDS = {
    "beneficiary": {
        "identifiers": ["your", "applicant", "you", "personal", "individual"],
        "fields": {
            "beneficiaryFirstName": ["first name", "given name", "firstname", "nombre"],
            "beneficiaryLastName": ["last name", "family name", "lastname", "surname", "apellido"],
            "beneficiaryMiddleName": ["middle name", "middle initial", "middlename"],
            "beneficiaryGender": ["gender", "sex", "male female"],
            "beneficiaryDateOfBirth": ["date of birth", "birth date", "dob", "born"],
            "beneficiarySsn": ["social security", "ssn", "ss#"],
            "alienNumber": ["alien number", "a-number", "uscis number", "registration number"],
            "beneficiaryCountryOfBirth": ["country of birth", "birth country", "born in"],
            "beneficiaryCitizenOfCountry": ["citizenship", "citizen of", "nationality"],
            "beneficiaryPrimaryEmailAddress": ["email", "e-mail", "electronic mail"],
            "beneficiaryCellNumber": ["cell phone", "mobile", "cell number"],
            "beneficiaryHomeNumber": ["home phone", "home number"],
            "beneficiaryWorkNumber": ["work phone", "daytime phone", "business phone"],
            "maritalStatus": ["marital status", "married", "single", "divorced"]
        }
    },
    "customer": {
        "identifiers": ["company", "employer", "organization", "petitioner", "business"],
        "fields": {
            "customer_name": ["company name", "employer name", "organization name", "business name"],
            "customer_tax_id": ["ein", "fein", "tax id", "federal tax"],
            "customer_naics_code": ["naics", "naics code"],
            "signatory_first_name": ["signatory first", "authorized first"],
            "signatory_last_name": ["signatory last", "authorized last"],
            "signatory_job_title": ["title", "position", "job title"]
        }
    },
    "address": {
        "addressStreet": ["street", "address line", "street address", "mailing address"],
        "addressCity": ["city", "town", "ciudad"],
        "addressState": ["state", "province", "estado"],
        "addressZip": ["zip", "postal code", "zip code"],
        "addressCountry": ["country", "nation", "pais"]
    },
    "passport": {
        "passportNumber": ["passport number", "passport no", "travel document number"],
        "passportIssueCountry": ["passport country", "issued by country", "passport issued"],
        "passportIssueDate": ["passport issue date", "date issued"],
        "passportExpiryDate": ["passport expiry", "passport expires", "expiration date"]
    },
    "visa": {
        "visaNumber": ["visa number", "visa no"],
        "visaStatus": ["current status", "visa status", "immigration status"],
        "visaExpiryDate": ["status expires", "visa expires", "expiration date"]
    },
    "i94": {
        "i94Number": ["i-94 number", "i94 number", "arrival record"],
        "i94ArrivalDate": ["arrival date", "date of arrival", "entered us"],
        "i94ExpiryDate": ["i-94 expires", "authorized until"]
    }
}

# Field type mappings
FIELD_TYPE_SUFFIX_MAP = {
    "text": ":TextBox",
    "checkbox": ":CheckBox",
    "radio": ":ConditionBox",
    "select": ":SelectBox",
    "date": ":Date",
    "signature": ":SignatureBox"
}

@dataclass
class PDFField:
    """Field representation"""
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
    is_mapped: bool = False
    is_questionnaire: bool = False
    field_type_suffix: str = ":TextBox"
    clean_name: str = ""
    ai_suggestions: List[str] = field(default_factory=list)
    confidence_scores: List[float] = field(default_factory=list)

@dataclass
class MappingSuggestion:
    """Mapping suggestion with confidence"""
    db_path: str
    confidence: float
    reason: str

class SmartUSCISMapper:
    """Smart USCIS Form Mapping System with NLP"""
    
    def __init__(self):
        self.db_objects = DB_OBJECTS
        self.uscis_forms = USCIS_FORMS_DATABASE
        self.nlp_keywords = NLP_KEYWORDS
        self.init_session_state()
        self._build_database_paths()
        
    def init_session_state(self):
        """Initialize session state"""
        if 'form_type' not in st.session_state:
            st.session_state.form_type = None
        if 'pdf_fields' not in st.session_state:
            st.session_state.pdf_fields = []
        if 'field_mappings' not in st.session_state:
            st.session_state.field_mappings = {}
        if 'current_part' not in st.session_state:
            st.session_state.current_part = None
        if 'current_field_index' not in st.session_state:
            st.session_state.current_field_index = 0
        if 'fields_by_part' not in st.session_state:
            st.session_state.fields_by_part = {}
    
    def _build_database_paths(self):
        """Build flat list of all database paths"""
        self.db_paths = []
        self.path_descriptions = {}
        
        def extract_paths(obj_name, structure, prefix=""):
            if isinstance(structure, dict):
                for key, value in structure.items():
                    if key == "":
                        if isinstance(value, list):
                            for field_name in value:
                                path = f"{obj_name}.{field_name}"
                                self.db_paths.append(path)
                                desc = field_name.replace('_', ' ').replace('beneficiary', '').replace('customer', '')
                                self.path_descriptions[path] = desc
                    else:
                        new_prefix = f"{obj_name}.{key}"
                        if isinstance(value, list):
                            for field_name in value:
                                path = f"{new_prefix}.{field_name}"
                                self.db_paths.append(path)
                                desc = f"{key} - {field_name}".replace('_', ' ')
                                self.path_descriptions[path] = desc
                        elif isinstance(value, dict):
                            for nested_key, nested_value in value.items():
                                if isinstance(nested_value, list):
                                    for field_name in nested_value:
                                        path = f"{new_prefix}.{nested_key}.{field_name}"
                                        self.db_paths.append(path)
                                        desc = f"{key} {nested_key} - {field_name}".replace('_', ' ')
                                        self.path_descriptions[path] = desc
        
        for obj_name, obj_structure in self.db_objects.items():
            extract_paths(obj_name, obj_structure)
        
        self.db_paths = sorted(list(set(self.db_paths)))
    
    def detect_form_type(self, pdf_file) -> Tuple[Optional[str], float]:
        """Detect USCIS form type from PDF"""
        try:
            pdf_bytes = pdf_file.read()
            pdf_file.seek(0)
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            text_content = ""
            for page_num in range(min(3, len(doc))):
                page = doc[page_num]
                text_content += page.get_text() + " "
            
            doc.close()
            
            text_lower = text_content.lower()
            text_upper = text_content.upper()
            
            form_scores = {}
            
            for form_code, form_info in self.uscis_forms.items():
                score = 0.0
                
                for pattern in form_info["identifier_patterns"]:
                    if pattern in text_content or pattern in text_upper:
                        score += 0.5
                
                if form_code in text_upper or f"FORM {form_code}" in text_upper:
                    score += 0.3
                
                keyword_matches = sum(1 for keyword in form_info["keywords"] if keyword in text_lower)
                if keyword_matches > 0:
                    score += 0.2 * (keyword_matches / len(form_info["keywords"]))
                
                form_scores[form_code] = min(score, 1.0)
            
            best_form = max(form_scores, key=form_scores.get) if form_scores else None
            best_score = form_scores.get(best_form, 0.0) if best_form else 0.0
            
            if best_score >= 0.5:
                return best_form, best_score
            else:
                return None, 0.0
                
        except Exception as e:
            st.error(f"Error detecting form type: {str(e)}")
            return None, 0.0
    
    def extract_pdf_fields(self, pdf_file, form_type: str) -> List[PDFField]:
        """Extract fields from PDF, skipping Part 0"""
        fields = []
        
        try:
            pdf_bytes = pdf_file.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            field_index = 0
            seen_fields = set()
            field_counter_by_part = defaultdict(int)
            
            # First pass: collect all fields
            all_widgets = []
            for page_num in range(len(doc)):
                page = doc[page_num]
                for widget in page.widgets():
                    if widget.field_name and widget.field_name not in seen_fields:
                        seen_fields.add(widget.field_name)
                        all_widgets.append((page_num, widget))
            
            # Sort widgets to ensure proper order
            all_widgets.sort(key=lambda x: (x[0], x[1].rect.y0, x[1].rect.x0))
            
            # Process widgets
            for page_num, widget in all_widgets:
                # Extract part information
                part = self._extract_part(widget.field_name)
                
                # Skip Part 0 fields
                if "Part 0" in part or "part 0" in part.lower():
                    continue
                
                # Clean field name and extract details
                clean_name = self._clean_field_name(widget.field_name)
                field_type = self._get_field_type(widget)
                description = self._generate_description(clean_name, widget.field_display)
                field_type_suffix = FIELD_TYPE_SUFFIX_MAP.get(field_type, ":TextBox")
                
                # Generate proper clean name (P1_1, P1_2, etc.)
                part_match = re.search(r'Part\s*(\d+)', part)
                if part_match:
                    part_num = part_match.group(1)
                    field_counter_by_part[part_num] += 1
                    clean_name = f"P{part_num}_{field_counter_by_part[part_num]}"
                else:
                    field_index += 1
                    clean_name = f"Field_{field_index}"
                
                # Get AI suggestions using NLP
                suggestions = self._get_nlp_suggestions(description, part)
                
                pdf_field = PDFField(
                    index=field_index,
                    raw_name=widget.field_name,
                    field_type=field_type,
                    value=widget.field_value or '',
                    page=page_num + 1,
                    part=part,
                    item=clean_name.split('_')[1] if '_' in clean_name else '',
                    description=description,
                    field_type_suffix=field_type_suffix,
                    clean_name=clean_name,
                    ai_suggestions=[s.db_path for s in suggestions[:3]],
                    confidence_scores=[s.confidence for s in suggestions[:3]]
                )
                
                fields.append(pdf_field)
                field_index += 1
            
            doc.close()
            
            # Group fields by part
            fields_by_part = defaultdict(list)
            for field in fields:
                fields_by_part[field.part].append(field)
            
            st.session_state.fields_by_part = dict(fields_by_part)
            
        except Exception as e:
            st.error(f"Error extracting PDF: {str(e)}")
            return []
        
        return fields
    
    def _get_nlp_suggestions(self, description: str, part: str) -> List[MappingSuggestion]:
        """Get NLP-based mapping suggestions"""
        suggestions = []
        desc_lower = description.lower()
        
        # Determine context from part
        context = self._get_part_context(part, desc_lower)
        
        # Check for exact keyword matches
        for category, keywords_dict in self.nlp_keywords.items():
            if category in ['beneficiary', 'customer']:
                # Check if this is the right context
                if category == 'beneficiary' and context != 'beneficiary':
                    continue
                if category == 'customer' and context not in ['customer', 'petitioner']:
                    continue
                
                # Check field-specific keywords
                for field_path, keywords in keywords_dict.get('fields', {}).items():
                    for keyword in keywords:
                        if keyword in desc_lower:
                            # Build full path
                            if category == 'beneficiary':
                                if '.' in field_path:
                                    full_path = f"beneficiary.{field_path}"
                                else:
                                    full_path = f"beneficiary.Beneficiary.{field_path}"
                            elif category == 'customer':
                                full_path = f"customer.{field_path}"
                            else:
                                full_path = field_path
                            
                            confidence = 0.9 if keyword == desc_lower else 0.8
                            suggestions.append(MappingSuggestion(
                                full_path, confidence, f"Keyword match: {keyword}"
                            ))
                            break
            
            # Check address fields
            elif category == 'address':
                for field_name, keywords in keywords_dict.items():
                    for keyword in keywords:
                        if keyword in desc_lower:
                            # Determine address type
                            if 'home' in desc_lower or 'residence' in desc_lower:
                                base = "beneficiary.HomeAddress"
                            elif 'mail' in desc_lower:
                                base = "beneficiary.MailingAddress"
                            elif context == 'customer':
                                base = "customer.address"
                            else:
                                base = "beneficiary.HomeAddress"
                            
                            full_path = f"{base}.{field_name}"
                            suggestions.append(MappingSuggestion(
                                full_path, 0.85, f"Address field: {keyword}"
                            ))
                            break
            
            # Check document fields (passport, visa, i94)
            elif category in ['passport', 'visa', 'i94']:
                for field_name, keywords in keywords_dict.items():
                    for keyword in keywords:
                        if keyword in desc_lower:
                            if category == 'passport':
                                full_path = f"beneficiary.PassportDetails.Passport.{field_name}"
                            elif category == 'visa':
                                full_path = f"beneficiary.VisaDetails.Visa.{field_name}"
                            elif category == 'i94':
                                full_path = f"beneficiary.I94Details.I94.{field_name}"
                            
                            suggestions.append(MappingSuggestion(
                                full_path, 0.85, f"{category.title()} field: {keyword}"
                            ))
                            break
        
        # Fuzzy matching if no exact matches
        if not suggestions:
            suggestions.extend(self._get_fuzzy_matches(desc_lower))
        
        # Sort by confidence
        suggestions.sort(key=lambda x: x.confidence, reverse=True)
        
        return suggestions[:5]
    
    def _get_fuzzy_matches(self, description: str) -> List[MappingSuggestion]:
        """Get fuzzy matches using string similarity"""
        suggestions = []
        
        for db_path in self.db_paths:
            # Get the field name part
            field_name = db_path.split('.')[-1]
            
            # Convert to readable format
            field_readable = field_name.replace('_', ' ').replace('beneficiary', '').lower()
            
            # Calculate similarity
            similarity = difflib.SequenceMatcher(None, description, field_readable).ratio()
            
            if similarity > 0.6:
                suggestions.append(MappingSuggestion(
                    db_path, similarity * 0.7, f"Similar to: {field_readable}"
                ))
        
        return suggestions
    
    def _get_part_context(self, part: str, description: str) -> str:
        """Determine context from part and description"""
        part_lower = part.lower()
        desc_lower = description.lower()
        
        # Check description for context clues
        if any(word in desc_lower for word in ['your', 'applicant', 'you']):
            return 'beneficiary'
        elif any(word in desc_lower for word in ['company', 'employer', 'organization', 'petitioner']):
            return 'customer'
        
        # Check part name
        if 'information about you' in part_lower:
            return 'beneficiary'
        elif 'petitioner' in part_lower or 'employer' in part_lower:
            return 'customer'
        
        # Default to beneficiary for most forms
        return 'beneficiary'
    
    def _extract_part(self, field_name: str) -> str:
        """Extract part number from field name"""
        patterns = [
            r'Part[\s_\-]*(\d+)',
            r'P(\d+)[\._]',
            r'Section[\s_\-]*(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, field_name, re.IGNORECASE)
            if match:
                return f"Part {match.group(1)}"
        
        return "Part 1"  # Default to Part 1 if no part found
    
    def _clean_field_name(self, field_name: str) -> str:
        """Clean field name"""
        patterns_to_remove = [
            r'form\d*\[\d+\]\.',
            r'#subform\[\d+\]\.',
            r'topmostSubform\[\d+\]\.',
            r'\[\d+\]',
            r'^#',
            r'\.pdf$'
        ]
        
        clean_name = field_name
        for pattern in patterns_to_remove:
            clean_name = re.sub(pattern, '', clean_name, flags=re.IGNORECASE)
        
        return clean_name
    
    def _get_field_type(self, widget) -> str:
        """Determine field type"""
        if widget.field_type == 2:
            return "checkbox"
        elif widget.field_type == 3:
            return "radio"
        elif widget.field_type == 5:
            return "select"
        elif widget.field_type == 7:
            return "signature"
        else:
            return "text"
    
    def _generate_description(self, field_name: str, field_display: str) -> str:
        """Generate field description"""
        if field_display and not field_display.startswith('form'):
            desc = field_display
        else:
            # Extract meaningful part from field name
            parts = field_name.split('.')
            meaningful_part = parts[-1] if parts else field_name
            desc = meaningful_part
        
        # Convert camelCase to readable
        desc = re.sub(r'([a-z])([A-Z])', r'\1 \2', desc)
        
        # Expand common abbreviations
        abbreviations = {
            'DOB': 'Date of Birth',
            'SSN': 'Social Security Number',
            'EIN': 'Employer Identification Number'
        }
        
        for abbr, full in abbreviations.items():
            desc = desc.replace(abbr, full)
        
        return desc.strip()
    
    def generate_typescript_export(self, form_type: str, fields: List[PDFField]) -> str:
        """Generate TypeScript export"""
        form_name = form_type.replace('-', '')
        
        # Group fields by object type
        customer_fields = []
        beneficiary_fields = []
        attorney_fields = []
        questionnaire_fields = []
        
        for field in fields:
            if field.is_questionnaire or not field.db_mapping:
                questionnaire_fields.append(field)
            elif field.db_mapping:
                if field.db_mapping.startswith("customer"):
                    customer_fields.append(field)
                elif field.db_mapping.startswith("beneficiary"):
                    beneficiary_fields.append(field)
                elif field.db_mapping.startswith("attorney"):
                    attorney_fields.append(field)
                else:
                    questionnaire_fields.append(field)
        
        # Generate TypeScript
        ts_content = f"export const {form_name} = {{\n"
        
        if customer_fields:
            ts_content += "  customerData: {\n"
            for field in customer_fields:
                db_path = field.db_mapping.replace("customer.", "")
                ts_content += f'    "{field.clean_name}{field.field_type_suffix}": "{db_path}",\n'
            ts_content = ts_content.rstrip(',\n') + '\n'
            ts_content += "  },\n"
        
        if beneficiary_fields:
            ts_content += "  beneficiaryData: {\n"
            for field in beneficiary_fields:
                db_path = field.db_mapping.replace("beneficiary.", "")
                ts_content += f'    "{field.clean_name}{field.field_type_suffix}": "{db_path}",\n'
            ts_content = ts_content.rstrip(',\n') + '\n'
            ts_content += "  },\n"
        
        if attorney_fields:
            ts_content += "  attorneyData: {\n"
            for field in attorney_fields:
                db_path = field.db_mapping.replace("attorney.", "").replace("attorneyLawfirmDetails.", "")
                ts_content += f'    "{field.clean_name}{field.field_type_suffix}": "{db_path}",\n'
            ts_content = ts_content.rstrip(',\n') + '\n'
            ts_content += "  },\n"
        
        if questionnaire_fields:
            ts_content += "  questionnaireData: {\n"
            for field in questionnaire_fields:
                ts_content += f'    "{field.clean_name}": {{\n'
                ts_content += f'      description: "{field.description}",\n'
                ts_content += f'      fieldType: "{field.field_type}",\n'
                ts_content += f'      part: "{field.part}",\n'
                if field.item:
                    ts_content += f'      item: "{field.item}",\n'
                ts_content += f'      required: true\n'
                ts_content += "    },\n"
            ts_content = ts_content.rstrip(',\n') + '\n'
            ts_content += "  }\n"
        
        ts_content = ts_content.rstrip(',\n') + '\n'
        ts_content += "};\n"
        
        return ts_content

def render_header():
    """Render header"""
    st.markdown("""
    <style>
        .main-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            text-align: center;
        }
        .header-title {
            font-size: 2em;
            font-weight: bold;
            margin: 0;
        }
        .field-card {
            background: white;
            border: 1px solid #e5e7eb;
            padding: 20px;
            margin: 10px 0;
            border-radius: 10px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .suggestion-card {
            background: #f3f4f6;
            padding: 10px;
            margin: 5px 0;
            border-radius: 5px;
            cursor: pointer;
            transition: all 0.2s;
        }
        .suggestion-card:hover {
            background: #e5e7eb;
            transform: translateX(5px);
        }
        .confidence-badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: bold;
            margin-left: 10px;
        }
        .high-confidence { background: #d1fae5; color: #065f46; }
        .medium-confidence { background: #fef3c7; color: #92400e; }
        .low-confidence { background: #fee2e2; color: #991b1b; }
        .progress-bar {
            background: #e5e7eb;
            height: 8px;
            border-radius: 4px;
            margin: 20px 0;
        }
        .progress-fill {
            background: #667eea;
            height: 100%;
            border-radius: 4px;
            transition: width 0.3s;
        }
        .part-selector {
            background: #f9fafb;
            padding: 15px;
            border-radius: 8px;
            margin: 10px 0;
            border: 1px solid #e5e7eb;
        }
    </style>
    <div class="main-header">
        <h1 class="header-title">Smart USCIS Form Mapper</h1>
        <p>Part-by-Part Field Mapping with AI Suggestions</p>
    </div>
    """, unsafe_allow_html=True)

def render_upload_section(mapper: SmartUSCISMapper):
    """Render upload section"""
    st.markdown("## 📤 Upload USCIS Form")
    
    uploaded_file = st.file_uploader(
        "Upload USCIS PDF form",
        type=['pdf'],
        help="Upload any fillable USCIS form"
    )
    
    if uploaded_file:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Filename", uploaded_file.name)
        with col2:
            st.metric("Size", f"{uploaded_file.size / 1024:.1f} KB")
        with col3:
            st.metric("Type", "PDF")
        
        if st.button("🚀 Auto-Detect & Extract", type="primary", use_container_width=True):
            with st.spinner("Detecting form type..."):
                form_type, confidence = mapper.detect_form_type(uploaded_file)
                
                if form_type and confidence >= 0.5:
                    st.session_state.form_type = form_type
                    st.success(f"✅ Detected: {form_type} ({confidence:.0%} confidence)")
                    
                    with st.spinner("Extracting fields (Part 1 onwards)..."):
                        fields = mapper.extract_pdf_fields(uploaded_file, form_type)
                        
                        if fields:
                            st.session_state.pdf_fields = fields
                            st.session_state.field_mappings = {f.raw_name: f for f in fields}
                            st.session_state.current_field_index = 0
                            st.success(f"✅ Extracted {len(fields)} fields!")
                            st.balloons()
                            st.rerun()
                        else:
                            st.error("No fields found")
                else:
                    st.error("Could not detect form type")

def render_mapping_section(mapper: SmartUSCISMapper):
    """Render part-by-part mapping section"""
    if 'pdf_fields' not in st.session_state or not st.session_state.pdf_fields:
        st.info("Please upload a PDF form first")
        return
    
    st.markdown("## 🎯 Smart Field Mapping")
    
    # Part selector
    st.markdown('<div class="part-selector">', unsafe_allow_html=True)
    
    # Get all parts
    parts = sorted(list(st.session_state.fields_by_part.keys()), 
                  key=lambda x: (0, int(re.search(r'\d+', x).group())) if re.search(r'\d+', x) else (1, x))
    
    # Part selection
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        selected_part = st.selectbox(
            "📑 Select Part to Map",
            parts,
            index=parts.index(st.session_state.current_part) if st.session_state.current_part in parts else 0,
            help="Choose which part of the form to work on"
        )
        st.session_state.current_part = selected_part
    
    with col2:
        # Part statistics
        part_fields = st.session_state.fields_by_part.get(selected_part, [])
        mapped = sum(1 for f in part_fields if f.is_mapped)
        quest = sum(1 for f in part_fields if f.is_questionnaire)
        unmapped = len(part_fields) - mapped - quest
        
        st.metric(f"{selected_part} Progress", f"{mapped + quest}/{len(part_fields)}")
    
    with col3:
        # Quick actions for this part
        if st.button("Skip All to Questionnaire", help="Add all unmapped fields in this part to questionnaire"):
            count = 0
            for field in part_fields:
                if not field.is_mapped and not field.is_questionnaire:
                    field.is_questionnaire = True
                    count += 1
            if count > 0:
                st.success(f"Added {count} fields to questionnaire")
                st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Overall progress
    all_fields = st.session_state.pdf_fields
    total_mapped = sum(1 for f in all_fields if f.is_mapped)
    total_quest = sum(1 for f in all_fields if f.is_questionnaire)
    overall_progress = (total_mapped + total_quest) / len(all_fields) if all_fields else 0
    
    st.markdown(f"""
    <div class="progress-bar">
        <div class="progress-fill" style="width: {overall_progress * 100}%"></div>
    </div>
    """, unsafe_allow_html=True)
    
    # Overall stats
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Fields", len(all_fields))
    with col2:
        st.metric("Mapped", total_mapped)
    with col3:
        st.metric("Questionnaire", total_quest)
    with col4:
        st.metric("Unmapped", len(all_fields) - total_mapped - total_quest)
    
    # Get fields for selected part
    part_fields = st.session_state.fields_by_part.get(selected_part, [])
    
    if not part_fields:
        st.warning(f"No fields found in {selected_part}")
        return
    
    # Get current field index within this part
    if 'part_field_index' not in st.session_state or st.session_state.get('last_part') != selected_part:
        st.session_state.part_field_index = 0
        st.session_state.last_part = selected_part
    
    current_idx = st.session_state.part_field_index
    
    # Check if all fields in this part are processed
    if current_idx >= len(part_fields):
        st.success(f"✅ All fields in {selected_part} have been processed!")
        
        # Part summary
        st.markdown(f"### 📊 {selected_part} Summary")
        
        mapped = sum(1 for f in part_fields if f.is_mapped)
        quest = sum(1 for f in part_fields if f.is_questionnaire)
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Database Mapped", f"{mapped} fields")
        with col2:
            st.metric("Manual Entry", f"{quest} fields")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Review Fields", use_container_width=True):
                st.session_state.part_field_index = 0
                st.rerun()
        with col2:
            # Check if there are more parts
            current_part_idx = parts.index(selected_part)
            if current_part_idx < len(parts) - 1:
                if st.button("Next Part →", use_container_width=True, type="primary"):
                    st.session_state.current_part = parts[current_part_idx + 1]
                    st.session_state.part_field_index = 0
                    st.rerun()
        
        return
    
    # Current field
    field = part_fields[current_idx]
    
    # Field card
    st.markdown('<div class="field-card">', unsafe_allow_html=True)
    
    # Field header
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"### Field {current_idx + 1} of {len(part_fields)} in {selected_part}")
        st.markdown(f"**{field.clean_name}** - {field.description}")
    with col2:
        if field.is_mapped:
            st.success("✅ Mapped")
        elif field.is_questionnaire:
            st.warning("📋 Questionnaire")
        else:
            st.info("🔍 Unmapped")
    
    # Field details
    col1, col2, col3 = st.columns(3)
    with col1:
        st.caption(f"**Type:** {field.field_type}")
    with col2:
        st.caption(f"**Page:** {field.page}")
    with col3:
        st.caption(f"**Raw Name:** {field.raw_name.split('.')[-1]}")
    
    # Current mapping
    if field.is_mapped and field.db_mapping:
        st.info(f"**Currently mapped to:** `{field.db_mapping}`")
    elif field.is_questionnaire:
        st.warning("**Currently in:** Manual Entry (Questionnaire)")
    
    # AI Suggestions
    st.markdown("### 🤖 AI Suggestions")
    
    if field.ai_suggestions:
        for i, (suggestion, confidence) in enumerate(zip(field.ai_suggestions, field.confidence_scores)):
            # Determine confidence level
            if confidence > 0.8:
                conf_class = "high-confidence"
                conf_text = "High"
            elif confidence > 0.6:
                conf_class = "medium-confidence"
                conf_text = "Medium"
            else:
                conf_class = "low-confidence"
                conf_text = "Low"
            
            # Suggestion card
            col1, col2 = st.columns([4, 1])
            with col1:
                if st.button(
                    f"📍 {suggestion}",
                    key=f"sugg_{selected_part}_{current_idx}_{i}",
                    use_container_width=True,
                    help=f"Click to select this mapping"
                ):
                    field.db_mapping = suggestion
                    field.is_mapped = True
                    field.is_questionnaire = False
                    st.success(f"Mapped to: {suggestion}")
                    st.session_state.part_field_index += 1
                    st.rerun()
            
            with col2:
                st.markdown(f'<span class="confidence-badge {conf_class}">{conf_text} ({confidence:.0%})</span>', unsafe_allow_html=True)
    else:
        st.info("No AI suggestions available")
    
    # Manual selection
    st.markdown("### 🔧 Manual Selection")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        selected = st.selectbox(
            "Select database field or manual entry:",
            ["Choose..."] + ["Manual Entry (Questionnaire)"] + mapper.db_paths,
            key=f"select_{selected_part}_{current_idx}"
        )
    
    with col2:
        if st.button("Apply", key=f"apply_{selected_part}_{current_idx}", use_container_width=True):
            if selected == "Manual Entry (Questionnaire)":
                field.is_questionnaire = True
                field.is_mapped = False
                field.db_mapping = None
                st.success("Added to questionnaire")
                st.session_state.part_field_index += 1
                st.rerun()
            elif selected != "Choose...":
                field.db_mapping = selected
                field.is_mapped = True
                field.is_questionnaire = False
                st.success(f"Mapped to: {selected}")
                st.session_state.part_field_index += 1
                st.rerun()
    
    # Navigation buttons
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if current_idx > 0:
            if st.button("⬅️ Previous", use_container_width=True):
                st.session_state.part_field_index -= 1
                st.rerun()
    
    with col2:
        if st.button("⏭️ Skip Field", use_container_width=True):
            field.is_questionnaire = True
            st.session_state.part_field_index += 1
            st.rerun()
    
    with col3:
        if current_idx < len(part_fields) - 1:
            if st.button("Next ➡️", use_container_width=True):
                if not field.is_mapped and not field.is_questionnaire:
                    st.error("Please map this field or skip it")
                else:
                    st.session_state.part_field_index += 1
                    st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

def render_all_fields_view(mapper: SmartUSCISMapper):
    """Render all fields view"""
    if 'pdf_fields' not in st.session_state or not st.session_state.pdf_fields:
        st.info("Please upload a PDF form first")
        return
    
    st.markdown("## 📊 All Fields Overview")
    
    fields = st.session_state.pdf_fields
    
    # Filter by part
    parts = ["All Parts"] + sorted(list(st.session_state.fields_by_part.keys()), 
                                  key=lambda x: (0, int(re.search(r'\d+', x).group())) if re.search(r'\d+', x) else (1, x))
    
    selected_part_filter = st.selectbox("Filter by Part", parts)
    
    # Filter fields
    if selected_part_filter == "All Parts":
        display_fields = fields
    else:
        display_fields = [f for f in fields if f.part == selected_part_filter]
    
    # Create DataFrame
    data = []
    for field in display_fields:
        data.append({
            'Field': field.clean_name,
            'Description': field.description,
            'Part': field.part,
            'Type': field.field_type,
            'Status': 'Mapped' if field.is_mapped else 'Questionnaire' if field.is_questionnaire else 'Unmapped',
            'Mapping': field.db_mapping if field.db_mapping else '-',
            'Page': field.page
        })
    
    df = pd.DataFrame(data)
    
    # Display stats
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Fields", len(display_fields))
    with col2:
        mapped = len([f for f in display_fields if f.is_mapped])
        st.metric("Mapped", mapped)
    with col3:
        quest = len([f for f in display_fields if f.is_questionnaire])
        st.metric("Questionnaire", quest)
    
    # Display table
    st.dataframe(df, use_container_width=True, hide_index=True)

def render_export_section(mapper: SmartUSCISMapper):
    """Render export section"""
    if 'pdf_fields' not in st.session_state or not st.session_state.pdf_fields:
        st.info("Please complete field mapping first")
        return
    
    st.markdown("## 📥 Export")
    
    fields = st.session_state.pdf_fields
    form_type = st.session_state.form_type
    
    # Export stats
    col1, col2, col3 = st.columns(3)
    
    mapped_count = sum(1 for f in fields if f.is_mapped)
    quest_count = sum(1 for f in fields if f.is_questionnaire)
    unmapped_count = sum(1 for f in fields if not f.is_mapped and not f.is_questionnaire)
    
    with col1:
        st.metric("✅ Ready", mapped_count + quest_count)
    with col2:
        st.metric("⚠️ Unmapped", unmapped_count)
    with col3:
        readiness = ((mapped_count + quest_count) / len(fields)) * 100 if fields else 0
        st.metric("📊 Readiness", f"{readiness:.0f}%")
    
    # Export buttons
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔧 Generate TypeScript", type="primary", use_container_width=True):
            ts_content = mapper.generate_typescript_export(form_type, fields)
            
            st.download_button(
                "📥 Download TypeScript",
                ts_content,
                f"{form_type.replace('-', '')}.ts",
                "text/plain",
                use_container_width=True
            )
            
            with st.expander("Preview TypeScript"):
                st.code(ts_content, language="typescript")
    
    with col2:
        if st.button("📊 Export Summary", type="primary", use_container_width=True):
            data = []
            for field in fields:
                data.append({
                    'Field': field.clean_name,
                    'Description': field.description,
                    'Part': field.part,
                    'Type': field.field_type,
                    'Mapping': field.db_mapping if field.db_mapping else 'Questionnaire' if field.is_questionnaire else 'Unmapped',
                    'Page': field.page
                })
            
            df = pd.DataFrame(data)
            csv = df.to_csv(index=False)
            
            st.download_button(
                "📥 Download CSV",
                csv,
                f"{form_type}_mappings.csv",
                "text/csv",
                use_container_width=True
            )

def main():
    """Main application"""
    st.set_page_config(
        page_title="Smart USCIS Form Mapper",
        page_icon="🧠",
        layout="wide"
    )
    
    # Initialize mapper
    mapper = SmartUSCISMapper()
    
    # Render header
    render_header()
    
    # Create tabs
    tabs = st.tabs([
        "📤 Upload Form",
        "🎯 Smart Mapping",
        "📊 All Fields",
        "📥 Export"
    ])
    
    with tabs[0]:
        render_upload_section(mapper)
    
    with tabs[1]:
        render_mapping_section(mapper)
    
    with tabs[2]:
        render_all_fields_view(mapper)
    
    with tabs[3]:
        render_export_section(mapper)
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 📊 Mapping Status")
        
        if 'pdf_fields' in st.session_state and st.session_state.pdf_fields:
            fields = st.session_state.pdf_fields
            
            total = len(fields)
            mapped = sum(1 for f in fields if f.is_mapped)
            quest = sum(1 for f in fields if f.is_questionnaire)
            unmapped = total - mapped - quest
            
            # Progress circle
            progress = (mapped + quest) / total if total > 0 else 0
            
            st.markdown(f"""
            <div style="text-align: center; padding: 20px;">
                <div style="position: relative; width: 100px; height: 100px; margin: 0 auto;">
                    <svg width="100" height="100" style="transform: rotate(-90deg);">
                        <circle cx="50" cy="50" r="40" fill="none" stroke="#e5e7eb" stroke-width="8"/>
                        <circle cx="50" cy="50" r="40" fill="none" stroke="#667eea" stroke-width="8"
                                stroke-dasharray="{progress * 251} 251" stroke-linecap="round"/>
                    </svg>
                    <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%) rotate(90deg); font-size: 20px; font-weight: bold;">
                        {progress * 100:.0f}%
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            st.metric("Total Fields", total)
            st.metric("Mapped", mapped)
            st.metric("Questionnaire", quest)
            st.metric("Unmapped", unmapped)
            
            if st.session_state.form_type:
                st.markdown("---")
                st.markdown(f"**Form:** {st.session_state.form_type}")
                
                # Part progress
                st.markdown("### Part Progress")
                for part, part_fields in st.session_state.fields_by_part.items():
                    part_mapped = sum(1 for f in part_fields if f.is_mapped or f.is_questionnaire)
                    part_total = len(part_fields)
                    part_progress = part_mapped / part_total if part_total > 0 else 0
                    st.progress(part_progress, text=f"{part}: {part_mapped}/{part_total}")
        else:
            st.info("Upload a form to see status")
        
        st.markdown("---")
        st.markdown("### ℹ️ How it Works")
        st.markdown("""
        1. **Upload** - Auto-detects form type
        2. **Select Part** - Choose which part to work on
        3. **Map Fields** - Review each field one by one
        4. **AI Suggests** - Click to accept suggestions
        5. **Export** - Generate TypeScript/CSV
        
        **Tips:**
        - Part 0 is automatically skipped
        - Work on one part at a time
        - Fields numbered as P1_1, P1_2, etc.
        - Skip unmapped fields to questionnaire
        """)

if __name__ == "__main__":
    main()
