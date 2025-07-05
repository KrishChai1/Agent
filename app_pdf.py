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
        if 'fields_by_part' not in st.session_state:
            st.session_state.fields_by_part = {}
        if 'current_view_part' not in st.session_state:
            st.session_state.current_view_part = "All"
    
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
    
    def generate_questionnaire_json(self, fields: List[PDFField]) -> str:
        """Generate questionnaire JSON for unmapped fields"""
        questionnaire_fields = [f for f in fields if f.is_questionnaire or not f.db_mapping]
        
        # Group by part
        fields_by_part = defaultdict(list)
        for field in questionnaire_fields:
            fields_by_part[field.part].append(field)
        
        # Build JSON structure
        questionnaire = {
            "formType": st.session_state.form_type,
            "generatedAt": datetime.now().isoformat(),
            "totalQuestions": len(questionnaire_fields),
            "sections": []
        }
        
        # Sort parts
        sorted_parts = sorted(fields_by_part.keys(), 
                            key=lambda x: (0, int(re.search(r'\d+', x).group())) if re.search(r'\d+', x) else (1, x))
        
        for part in sorted_parts:
            section = {
                "name": part,
                "questions": []
            }
            
            for field in fields_by_part[part]:
                question = {
                    "id": field.clean_name,
                    "description": field.description,
                    "type": field.field_type,
                    "required": True,
                    "page": field.page
                }
                
                if field.item:
                    question["item"] = field.item
                
                section["questions"].append(question)
            
            questionnaire["sections"].append(section)
        
        return json.dumps(questionnaire, indent=2)

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
            padding: 15px;
            margin: 10px 0;
            border-radius: 8px;
            transition: all 0.2s;
        }
        .field-card:hover {
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        .part-card {
            background: #f9fafb;
            border: 1px solid #e5e7eb;
            padding: 15px;
            margin: 10px 0;
            border-radius: 8px;
        }
        .part-header {
            font-weight: bold;
            font-size: 1.1em;
            margin-bottom: 10px;
            color: #4b5563;
        }
        .status-badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: bold;
            margin-left: 10px;
        }
        .mapped { background: #d1fae5; color: #065f46; }
        .questionnaire { background: #fef3c7; color: #92400e; }
        .unmapped { background: #fee2e2; color: #991b1b; }
        .database { background: #dbeafe; color: #1e3a8a; }
        .json { background: #e0e7ff; color: #4338ca; }
        .field-table {
            font-size: 0.9em;
            margin-top: 10px;
        }
        .mapping-stats {
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            margin: 10px 0;
        }
    </style>
    <div class="main-header">
        <h1 class="header-title">Smart USCIS Form Mapper</h1>
        <p>Extract, Map to Database Objects, Export Unmapped to JSON</p>
    </div>
    """, unsafe_allow_html=True)

def render_upload_section(mapper: SmartUSCISMapper):
    """Render upload section with extracted fields display"""
    st.markdown("## 📤 Upload & Extract USCIS Form")
    
    uploaded_file = st.file_uploader(
        "Upload USCIS PDF form",
        type=['pdf'],
        help="Upload any fillable USCIS form (Part 0 will be skipped)"
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
                    st.success(f"✅ Detected: **{form_type}** - {USCIS_FORMS_DATABASE[form_type]['title']} ({confidence:.0%} confidence)")
                    
                    with st.spinner("Extracting fields (skipping Part 0)..."):
                        fields = mapper.extract_pdf_fields(uploaded_file, form_type)
                        
                        if fields:
                            st.session_state.pdf_fields = fields
                            st.session_state.field_mappings = {f.raw_name: f for f in fields}
                            st.success(f"✅ Extracted {len(fields)} fields from {len(st.session_state.fields_by_part)} parts!")
                            st.balloons()
                        else:
                            st.error("No fields found")
                else:
                    st.error("Could not detect form type. Please try another form.")
    
    # Display extracted fields by part
    if 'pdf_fields' in st.session_state and st.session_state.pdf_fields:
        st.markdown("---")
        st.markdown("## 📊 Extracted Fields by Part")
        
        # Overall stats
        fields = st.session_state.pdf_fields
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Fields", len(fields))
        with col2:
            st.metric("Total Parts", len(st.session_state.fields_by_part))
        with col3:
            st.metric("Pages", max(f.page for f in fields))
        with col4:
            st.metric("Form", st.session_state.form_type)
        
        # Display fields by part
        sorted_parts = sorted(st.session_state.fields_by_part.keys(), 
                            key=lambda x: (0, int(re.search(r'\d+', x).group())) if re.search(r'\d+', x) else (1, x))
        
        for part in sorted_parts:
            part_fields = st.session_state.fields_by_part[part]
            
            with st.expander(f"📑 **{part}** ({len(part_fields)} fields)", expanded=False):
                # Part stats
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.caption(f"**Fields:** {len(part_fields)}")
                with col2:
                    pages = list(set(f.page for f in part_fields))
                    st.caption(f"**Pages:** {min(pages)}-{max(pages)}")
                with col3:
                    types = list(set(f.field_type for f in part_fields))
                    st.caption(f"**Types:** {', '.join(types)}")
                
                # Field table
                field_data = []
                for field in part_fields:
                    field_data.append({
                        "Field": field.clean_name,
                        "Description": field.description[:50] + "..." if len(field.description) > 50 else field.description,
                        "Type": field.field_type,
                        "Page": field.page,
                        "AI Suggestion": field.ai_suggestions[0].split('.')[-1] if field.ai_suggestions else "-"
                    })
                
                df = pd.DataFrame(field_data)
                st.dataframe(df, use_container_width=True, hide_index=True, height=200)

def render_mapping_section(mapper: SmartUSCISMapper):
    """Render smart mapping section with All option"""
    if 'pdf_fields' not in st.session_state or not st.session_state.pdf_fields:
        st.info("Please upload a PDF form first")
        return
    
    st.markdown("## 🎯 Smart Field Mapping")
    
    # Part selector with All option
    parts = ["All"] + sorted(list(st.session_state.fields_by_part.keys()), 
                           key=lambda x: (0, int(re.search(r'\d+', x).group())) if re.search(r'\d+', x) else (1, x))
    
    col1, col2 = st.columns([3, 1])
    with col1:
        view_part = st.selectbox(
            "📑 View Part",
            parts,
            index=parts.index(st.session_state.current_view_part) if st.session_state.current_view_part in parts else 0,
            help="Select 'All' to see all fields or choose a specific part"
        )
        st.session_state.current_view_part = view_part
    
    with col2:
        # Quick actions
        if st.button("📋 All to Questionnaire", help="Add all unmapped fields to questionnaire"):
            count = 0
            if view_part == "All":
                fields_to_process = st.session_state.pdf_fields
            else:
                fields_to_process = st.session_state.fields_by_part.get(view_part, [])
            
            for field in fields_to_process:
                if not field.is_mapped and not field.is_questionnaire:
                    field.is_questionnaire = True
                    count += 1
            
            if count > 0:
                st.success(f"Added {count} fields to questionnaire")
                st.rerun()
    
    # Get fields to display
    if view_part == "All":
        display_fields = st.session_state.pdf_fields
        # Group by part for display
        fields_by_part = st.session_state.fields_by_part
        sorted_parts = sorted(fields_by_part.keys(), 
                            key=lambda x: (0, int(re.search(r'\d+', x).group())) if re.search(r'\d+', x) else (1, x))
    else:
        display_fields = st.session_state.fields_by_part.get(view_part, [])
        sorted_parts = [view_part]
        fields_by_part = {view_part: display_fields}
    
    # Overall mapping statistics
    st.markdown('<div class="mapping-stats">', unsafe_allow_html=True)
    st.markdown("### 📊 Mapping Status")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    total = len(display_fields)
    mapped = sum(1 for f in display_fields if f.is_mapped)
    quest = sum(1 for f in display_fields if f.is_questionnaire)
    unmapped = total - mapped - quest
    
    with col1:
        st.metric("Total", total)
    with col2:
        st.metric("Mapped to DB", mapped)
        st.caption("Database objects")
    with col3:
        st.metric("To JSON", quest)
        st.caption("Questionnaire")
    with col4:
        st.metric("Unmapped", unmapped)
    with col5:
        progress = (mapped + quest) / total if total > 0 else 0
        st.metric("Progress", f"{progress:.0%}")
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Display fields by part
    for part in sorted_parts:
        part_fields = fields_by_part[part]
        
        # Part header with stats
        part_mapped = sum(1 for f in part_fields if f.is_mapped)
        part_quest = sum(1 for f in part_fields if f.is_questionnaire)
        part_unmapped = len(part_fields) - part_mapped - part_quest
        
        st.markdown(f"""
        <div class="part-card">
            <div class="part-header">
                📑 {part} ({len(part_fields)} fields)
                <span class="status-badge database">DB: {part_mapped}</span>
                <span class="status-badge json">JSON: {part_quest}</span>
                <span class="status-badge unmapped">Unmapped: {part_unmapped}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Display fields
        for field in part_fields:
            render_field_mapping_card(field, mapper)

def render_field_mapping_card(field: PDFField, mapper: SmartUSCISMapper):
    """Render individual field mapping card"""
    with st.container():
        st.markdown('<div class="field-card">', unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([3, 2, 1])
        
        with col1:
            # Field info
            st.markdown(f"**{field.clean_name}** - {field.description}")
            st.caption(f"Type: {field.field_type} | Page: {field.page}")
            
            # Current status
            if field.is_mapped:
                st.markdown(f'<span class="status-badge mapped">✅ Mapped to Database</span>', unsafe_allow_html=True)
                st.caption(f"Path: `{field.db_mapping}`")
            elif field.is_questionnaire:
                st.markdown('<span class="status-badge questionnaire">📋 To JSON (Questionnaire)</span>', unsafe_allow_html=True)
            else:
                st.markdown('<span class="status-badge unmapped">❌ Unmapped</span>', unsafe_allow_html=True)
        
        with col2:
            # Mapping selector
            if field.ai_suggestions:
                default_option = field.db_mapping if field.is_mapped else ("To JSON (Questionnaire)" if field.is_questionnaire else field.ai_suggestions[0])
            else:
                default_option = field.db_mapping if field.is_mapped else ("To JSON (Questionnaire)" if field.is_questionnaire else "Select...")
            
            options = ["Select...", "To JSON (Questionnaire)"] + field.ai_suggestions + ["--- All Database Paths ---"] + mapper.db_paths
            
            try:
                default_index = options.index(default_option)
            except ValueError:
                default_index = 0
            
            selected = st.selectbox(
                "Map to",
                options,
                index=default_index,
                key=f"map_{field.index}",
                label_visibility="collapsed"
            )
        
        with col3:
            # Apply button
            if st.button("Apply", key=f"apply_{field.index}"):
                if selected == "To JSON (Questionnaire)":
                    field.is_questionnaire = True
                    field.is_mapped = False
                    field.db_mapping = None
                    st.success("→ JSON")
                    st.rerun()
                elif selected != "Select..." and selected != "--- All Database Paths ---":
                    field.db_mapping = selected
                    field.is_mapped = True
                    field.is_questionnaire = False
                    st.success("→ DB")
                    st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)

def render_export_section(mapper: SmartUSCISMapper):
    """Render export section with database and JSON visualization"""
    if 'pdf_fields' not in st.session_state or not st.session_state.pdf_fields:
        st.info("Please complete field mapping first")
        return
    
    st.markdown("## 📥 Export & Review")
    
    fields = st.session_state.pdf_fields
    form_type = st.session_state.form_type
    
    # Export statistics
    st.markdown("### 📊 Export Summary")
    
    col1, col2, col3 = st.columns(3)
    
    mapped_count = sum(1 for f in fields if f.is_mapped)
    quest_count = sum(1 for f in fields if f.is_questionnaire)
    unmapped_count = sum(1 for f in fields if not f.is_mapped and not f.is_questionnaire)
    
    with col1:
        st.markdown('<div class="mapping-stats">', unsafe_allow_html=True)
        st.metric("✅ Database Mapped", mapped_count)
        st.caption("Ready for database")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="mapping-stats">', unsafe_allow_html=True)
        st.metric("📋 JSON Questionnaire", quest_count)
        st.caption("Manual entry fields")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        st.markdown('<div class="mapping-stats">', unsafe_allow_html=True)
        st.metric("⚠️ Unmapped", unmapped_count)
        st.caption("Need attention")
        st.markdown('</div>', unsafe_allow_html=True)
    
    if unmapped_count > 0:
        st.warning(f"⚠️ {unmapped_count} fields are still unmapped. They will be added to JSON questionnaire on export.")
    
    # Export buttons
    st.markdown("### 🚀 Export Options")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔧 Generate TypeScript", type="primary", use_container_width=True):
            # Auto-add unmapped to questionnaire
            for field in fields:
                if not field.is_mapped and not field.is_questionnaire:
                    field.is_questionnaire = True
            
            ts_content = mapper.generate_typescript_export(form_type, fields)
            
            st.download_button(
                "📥 Download TypeScript",
                ts_content,
                f"{form_type.replace('-', '')}.ts",
                "text/plain",
                use_container_width=True
            )
    
    with col2:
        if st.button("📋 Generate JSON", type="primary", use_container_width=True):
            # Auto-add unmapped to questionnaire
            for field in fields:
                if not field.is_mapped and not field.is_questionnaire:
                    field.is_questionnaire = True
            
            json_content = mapper.generate_questionnaire_json(fields)
            
            st.download_button(
                "📥 Download Questionnaire JSON",
                json_content,
                f"{form_type.lower()}-questionnaire.json",
                "application/json",
                use_container_width=True
            )
    
    with col3:
        if st.button("📊 Export Summary CSV", type="primary", use_container_width=True):
            data = []
            for field in fields:
                data.append({
                    'Field': field.clean_name,
                    'Description': field.description,
                    'Part': field.part,
                    'Type': field.field_type,
                    'Status': 'Database' if field.is_mapped else 'JSON' if field.is_questionnaire else 'Unmapped',
                    'Mapping': field.db_mapping if field.is_mapped else 'Questionnaire' if field.is_questionnaire else '-',
                    'Page': field.page
                })
            
            df = pd.DataFrame(data)
            csv = df.to_csv(index=False)
            
            st.download_button(
                "📥 Download CSV",
                csv,
                f"{form_type}_mapping_summary.csv",
                "text/csv",
                use_container_width=True
            )
    
    # Preview sections
    st.markdown("### 👁️ Preview Exports")
    
    tab1, tab2, tab3 = st.tabs(["📊 Database Mappings", "📋 JSON Questionnaire", "🔧 TypeScript"])
    
    with tab1:
        # Show database mappings by object
        st.markdown("#### Database Object Mappings")
        
        # Group by database object
        db_mappings = defaultdict(list)
        for field in fields:
            if field.is_mapped and field.db_mapping:
                obj = field.db_mapping.split('.')[0]
                db_mappings[obj].append(field)
        
        for obj, obj_fields in db_mappings.items():
            st.markdown(f"**{obj}** ({len(obj_fields)} fields)")
            
            mapping_data = []
            for field in obj_fields:
                mapping_data.append({
                    "PDF Field": field.clean_name,
                    "Database Path": field.db_mapping,
                    "Description": field.description
                })
            
            df = pd.DataFrame(mapping_data)
            st.dataframe(df, use_container_width=True, hide_index=True, height=150)
    
    with tab2:
        # Show JSON questionnaire structure
        st.markdown("#### JSON Questionnaire Structure")
        
        # Auto-add unmapped for preview
        preview_quest_fields = [f for f in fields if f.is_questionnaire or (not f.is_mapped and not f.is_questionnaire)]
        
        if preview_quest_fields:
            # Group by part
            quest_by_part = defaultdict(list)
            for field in preview_quest_fields:
                quest_by_part[field.part].append(field)
            
            json_preview = {
                "formType": form_type,
                "totalQuestions": len(preview_quest_fields),
                "sections": []
            }
            
            for part, part_fields in sorted(quest_by_part.items()):
                section = {
                    "name": part,
                    "questionCount": len(part_fields),
                    "questions": [
                        {
                            "id": f.clean_name,
                            "description": f.description,
                            "type": f.field_type
                        } for f in part_fields[:3]  # Show first 3
                    ]
                }
                if len(part_fields) > 3:
                    section["questions"].append({"...": f"and {len(part_fields) - 3} more"})
                
                json_preview["sections"].append(section)
            
            st.json(json_preview)
        else:
            st.info("No fields in questionnaire")
    
    with tab3:
        # Show TypeScript preview
        st.markdown("#### TypeScript Export Preview")
        
        # Generate preview
        ts_preview = mapper.generate_typescript_export(form_type, fields[:10])  # Show first 10 fields
        if len(fields) > 10:
            ts_preview = ts_preview.rstrip("}\n") + "\n  // ... and more fields\n};\n"
        
        st.code(ts_preview, language="typescript")

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
        "📤 Upload & Extract",
        "🎯 Smart Mapping",
        "📥 Export & Review"
    ])
    
    with tabs[0]:
        render_upload_section(mapper)
    
    with tabs[1]:
        render_mapping_section(mapper)
    
    with tabs[2]:
        render_export_section(mapper)
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 📊 Overall Status")
        
        if 'pdf_fields' in st.session_state and st.session_state.pdf_fields:
            fields = st.session_state.pdf_fields
            
            total = len(fields)
            mapped = sum(1 for f in fields if f.is_mapped)
            quest = sum(1 for f in fields if f.is_questionnaire)
            unmapped = total - mapped - quest
            
            # Progress visualization
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
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Fields", total)
                st.metric("To Database", mapped)
            with col2:
                st.metric("To JSON", quest)
                st.metric("Unmapped", unmapped)
            
            # Form info
            st.markdown("---")
            st.markdown(f"**Form:** {st.session_state.form_type}")
            st.markdown(f"**Parts:** {len(st.session_state.fields_by_part)}")
            
            # Quick stats by part
            st.markdown("### Part Status")
            for part, part_fields in sorted(st.session_state.fields_by_part.items()):
                part_mapped = sum(1 for f in part_fields if f.is_mapped)
                part_quest = sum(1 for f in part_fields if f.is_questionnaire)
                part_total = len(part_fields)
                part_progress = (part_mapped + part_quest) / part_total if part_total > 0 else 0
                
                st.progress(part_progress, text=f"{part}: {part_mapped + part_quest}/{part_total}")
        else:
            st.info("Upload a form to see status")
        
        st.markdown("---")
        st.markdown("### ℹ️ Workflow")
        st.markdown("""
        1. **Upload** - Auto-detects form type
        2. **Extract** - Shows all fields by part
        3. **Map** - Assign to database or JSON
        4. **Export** - TypeScript & JSON files
        
        **Features:**
        - ⏭️ Part 0 automatically skipped
        - 🤖 AI suggestions for mapping
        - 📊 Database object mapping
        - 📋 JSON questionnaire for manual fields
        - 📥 Multiple export formats
        """)

if __name__ == "__main__":
    main()
