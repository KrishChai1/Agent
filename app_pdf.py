import streamlit as st
import PyPDF2
import pdfplumber
import json
import re
from typing import Dict, List, Any, Tuple
import pandas as pd
from datetime import datetime
import io
import base64
import os
from pathlib import Path

# Import database utilities
from db_utils import USCISDatabase, get_db_mapping_for_field, FIELD_MAPPING_CONFIG

# Initialize session state
if 'form_mappings' not in st.session_state:
    st.session_state.form_mappings = {}
if 'questionnaire_data' not in st.session_state:
    st.session_state.questionnaire_data = {}
if 'db' not in st.session_state:
    st.session_state.db = USCISDatabase()

# Create directories for generated files
Path("generated/questionnaires").mkdir(parents=True, exist_ok=True)
Path("generated/typescript").mkdir(parents=True, exist_ok=True)

# Known form mappings structure based on provided examples
KNOWN_FORM_STRUCTURES = {
    "I-90": {
        "beneficiaryData": ["beneficiaryLastName", "beneficiaryFirstName", "beneficiaryMiddleName", 
                           "beneficiaryDateOfBirth", "alienNumber", "beneficiaryGender", "beneficiarySsn",
                           "beneficiaryCountryOfBirth", "beneficiaryProvinceOfBirth", "beneficiaryCitizenOfCountry",
                           "fatherLastName", "fatherFirstName", "motherLastName", "motherFirstName"],
        "customerData": [],
        "attorneyData": ["lastName", "firstName", "lawFirmName", "workPhone", "emailAddress", 
                        "stateBarNumber", "addressStreet", "addressCity", "addressState", "addressZip"],
        "questionnaireData": ["p1_4", "p1_5a", "p1_5b", "p1_5c", "p1_7", "p1_8a", "p1_8b", "p1_8c"],
        "defaultData": ["selectG28", "P4_1a", "P4_2a", "P6_7b", "P6_7c"],
        "conditionalData": ["P1_6a", "P4_2b", "P1_9a", "P1_9b", "P1_14", "P1_15"]
    },
    "I-129": {
        "customerData": ["customer_name", "signatory_first_name", "signatory_last_name", 
                        "address_street", "address_city", "address_state", "address_zip", 
                        "customer_tax_id", "customer_type_of_business", "customer_year_established",
                        "customer_total_employees", "customer_gross_annual_income", "customer_net_annual_income"],
        "beneficiaryData": ["beneficiaryLastName", "beneficiaryFirstName", "beneficiaryMiddleName",
                           "beneficiaryDateOfBirth", "beneficiaryGender", "alienNumber", "beneficiarySsn",
                           "beneficiaryCountryOfBirth", "beneficiaryProvinceOfBirth", "beneficiaryCitizenOfCountry",
                           "passportNumber", "passportIssueDate", "passportExpiryDate", "passportIssueCountry"],
        "attorneyData": ["lastName", "firstName", "lawFirmName", "workPhone", "emailAddress", "faxNumber",
                        "addressStreet", "addressCity", "addressState", "addressZip"],
        "questionnaireData": ["pt4q3", "petition", "pt4q4", "replacement", "dependents", "dependentscount"],
        "caseData": ["caseType", "caseSubType", "h1BPetitionType"],
        "defaultData": ["totalnoofworkers", "entertainmentgroup", "typeofofficeConsulate", "validpassportYes"],
        "conditionalData": ["careOfName", "t25", "applicationreceipt", "i94number", "visaStatus"]
    },
    "G-28": {
        "attorneyData": ["lastName", "firstName", "middleName", "lawFirmName", "addressStreet",
                        "addressCity", "addressState", "addressZip", "addressCountry", "workPhone", 
                        "emailAddress", "faxNumber", "stateBarNumber", "licensingAuthority"],
        "clientData": ["familyName", "givenName", "middleName", "alienNumber", "uscisAccountNumber",
                      "title", "entityName"],
        "customerData": ["customer_name", "signatory_last_name", "signatory_first_name", "signatory_middle_name",
                        "signatory_job_title", "signatory_work_phone", "signatory_email_id"],
        "defaultData": ["G_28"],
        "conditionalData": []
    },
    "I-140": {
        "customerData": ["customer_name", "signatory_first_name", "signatory_last_name", "signatory_job_title",
                        "address_street", "address_city", "address_state", "address_zip", "customer_tax_id",
                        "customer_type_of_business", "customer_year_established", "customer_total_employees",
                        "customer_gross_annual_income", "customer_net_annual_income", "customer_naics_code"],
        "beneficiaryData": ["beneficiaryLastName", "beneficiaryFirstName", "beneficiaryMiddleName",
                           "beneficiaryDateOfBirth", "beneficiaryCountryOfBirth", "beneficiaryCitizenOfCountry",
                           "alienNumber", "beneficiarySsn", "passportNumber", "passportIssueCountry",
                           "passportExpiryDate"],
        "attorneyData": ["lastName", "firstName", "lawFirmName", "workPhone", "emailAddress"],
        "questionnaireData": [],
        "defaultData": [],
        "conditionalData": []
    }
}

class USCISFormProcessor:
    def __init__(self, db: USCISDatabase):
        self.db = db
        self.extracted_fields = {}
        self.form_type = None
        self.missing_fields = []
        
    def detect_form_type(self, text: str) -> str:
        """Detect the type of USCIS form from extracted text"""
        form_patterns = {
            "I-90": r"Form I-90.*Application to Replace",
            "I-129": r"Form I-129.*Petition for.*Nonimmigrant Worker",
            "I-140": r"Form I-140.*Immigrant Petition",
            "I-485": r"Form I-485.*Application to Register",
            "I-539": r"Form I-539.*Application to Extend",
            "I-765": r"Form I-765.*Application for Employment",
            "G-28": r"Form G-28.*Notice of Entry.*Appearance",
            "I-130": r"Form I-130.*Petition for Alien Relative",
            "I-131": r"Form I-131.*Application for Travel Document",
            "I-864": r"Form I-864.*Affidavit of Support",
            "I-129H": r"H Classification Supplement",
            "I-129DC": r"H-1B.*Data Collection",
            "I-907": r"Form I-907.*Request for Premium",
            "I-539A": r"Form I-539A.*Supplemental"
        }
        
        for form_type, pattern in form_patterns.items():
            if re.search(pattern, text, re.IGNORECASE | re.DOTALL):
                return form_type
                
        # Try to detect from common keywords
        upper_text = text.upper()
        if "H CLASSIFICATION" in upper_text and "I-129" in upper_text:
            return "I-129H"
        elif "DATA COLLECTION" in upper_text and "H-1B" in upper_text:
            return "I-129DC"
        elif "ADVANCE PAROLE" in upper_text:
            return "I-131"
            
        return "Unknown"
    
    def extract_form_fields(self, pdf_file) -> Dict[str, Any]:
        """Extract form fields from PDF using multiple methods"""
        fields = {}
        text_content = ""
        
        # Method 1: Try to extract form fields using PyPDF2
        try:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            # Extract text content
            for page in pdf_reader.pages:
                text_content += page.extract_text() + "\n"
            
            # Extract form fields if available
            if '/AcroForm' in pdf_reader.trailer['/Root']:
                form_fields = pdf_reader.get_fields()
                if form_fields:
                    for field_name, field_data in form_fields.items():
                        field_value = field_data.get('/V', '')
                        field_type = field_data.get('/FT', '')
                        if field_value:
                            fields[field_name] = {
                                'value': field_value,
                                'type': field_type,
                                'source': 'form_field'
                            }
        except Exception as e:
            st.warning(f"PyPDF2 extraction warning: {str(e)}")
        
        # Method 2: Use pdfplumber for better text extraction
        try:
            pdf_file.seek(0)  # Reset file pointer
            with pdfplumber.open(pdf_file) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    # Extract tables if present
                    tables = page.extract_tables()
                    for table in tables:
                        for row in table:
                            if row and len(row) >= 2:
                                # Simple heuristic: first column might be field name
                                if row[0] and row[1] and not str(row[0]).strip().startswith("Form"):
                                    field_name = self.clean_field_name(str(row[0]))
                                    if field_name:
                                        fields[field_name] = {
                                            'value': str(row[1]).strip(),
                                            'type': 'text',
                                            'source': 'table'
                                        }
                    
                    # Extract text for form type detection
                    page_text = page.extract_text()
                    if page_text:
                        text_content += page_text + "\n"
        except Exception as e:
            st.warning(f"pdfplumber extraction warning: {str(e)}")
        
        # Detect form type
        self.form_type = self.detect_form_type(text_content)
        
        # Extract common fields using regex patterns
        self.extract_fields_from_text(text_content, fields)
        
        self.extracted_fields = fields
        return {
            "form_type": self.form_type,
            "fields": fields,
            "text_content": text_content[:2000],  # First 2000 chars for preview
            "total_pages": len(pdf_reader.pages) if 'pdf_reader' in locals() else 0
        }
    
    def extract_fields_from_text(self, text_content: str, fields: Dict[str, Any]):
        """Extract fields from text using regex patterns"""
        common_patterns = {
            # Name fields
            "lastName": r"(?:Family Name|Last Name)[:\s]*([A-Za-z\s\-']+?)(?:\n|$|First)",
            "firstName": r"(?:Given Name|First Name)[:\s]*([A-Za-z\s\-']+?)(?:\n|$|Middle)",
            "middleName": r"(?:Middle Name)[:\s]*([A-Za-z\s\-']+?)(?:\n|$)",
            
            # Date fields
            "dateOfBirth": r"(?:Date of Birth|DOB)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            
            # Number fields
            "alienNumber": r"(?:A-Number|Alien Number|Alien Registration Number)[:\s]*(?:A[-\s]?)?(\d{8,9})",
            "ssn": r"(?:Social Security Number|SSN)[:\s]*(\d{3}[-\s]?\d{2}[-\s]?\d{4})",
            "phoneNumber": r"(?:Phone Number|Telephone|Daytime Phone)[:\s]*\(?(\d{3})\)?[-\s]?(\d{3})[-\s]?(\d{4})",
            "ein": r"(?:EIN|Employer Identification Number)[:\s]*(\d{2}[-\s]?\d{7})",
            
            # Contact fields
            "email": r"(?:Email Address|E-mail)[:\s]*([\w\.-]+@[\w\.-]+\.\w+)",
            
            # Address fields
            "addressStreet": r"(?:Street Address|Street Number and Name|Address)[:\s]*([^\n]+?)(?:\n|Apt|Suite|$)",
            "city": r"(?:City|City or Town)[:\s]*([A-Za-z\s\-]+?)(?:\n|State|$)",
            "state": r"(?:State|Province)[:\s]*([A-Z]{2})(?:\n|ZIP|$)",
            "zipCode": r"(?:ZIP Code|Postal Code)[:\s]*(\d{5}(?:[-\s]?\d{4})?)",
            "country": r"(?:Country)[:\s]*([A-Za-z\s\-]+?)(?:\n|$)",
            
            # Other common fields
            "gender": r"(?:Gender|Sex)[:\s]*(Male|Female|M|F)",
            "maritalStatus": r"(?:Marital Status)[:\s]*(Single|Married|Divorced|Widowed)",
            "citizenshipCountry": r"(?:Country of Citizenship|Citizenship)[:\s]*([A-Za-z\s\-]+?)(?:\n|$)",
            "birthCountry": r"(?:Country of Birth|Birth Country)[:\s]*([A-Za-z\s\-]+?)(?:\n|$)"
        }
        
        for field_name, pattern in common_patterns.items():
            if field_name not in fields:  # Don't override form fields
                matches = re.findall(pattern, text_content, re.IGNORECASE | re.MULTILINE)
                if matches:
                    # For phone numbers, combine the parts
                    if field_name == "phoneNumber" and isinstance(matches[0], tuple):
                        value = "-".join(matches[0])
                    else:
                        value = matches[0] if isinstance(matches[0], str) else matches[0][0]
                    
                    fields[field_name] = {
                        'value': value.strip(),
                        'type': self.determine_field_type(field_name),
                        'source': 'regex'
                    }
    
    def clean_field_name(self, field_name: str) -> str:
        """Clean and standardize field names"""
        # Remove special characters and normalize
        cleaned = re.sub(r'[^\w\s]', '', field_name)
        cleaned = re.sub(r'\s+', '_', cleaned.strip())
        # Convert to camelCase
        parts = cleaned.lower().split('_')
        if len(parts) > 1:
            return parts[0] + ''.join(p.capitalize() for p in parts[1:])
        return parts[0] if parts else ''
    
    def map_to_database_structure(self, extracted_fields: Dict[str, Any]) -> Dict[str, Any]:
        """Map extracted fields to database structure"""
        form_structure = KNOWN_FORM_STRUCTURES.get(self.form_type, {})
        mapped_data = {
            "formname": self.form_type.lower().replace("-", ""),
            "pdfName": self.form_type,
            "customerData": {},
            "beneficiaryData": {},
            "attorneyData": {},
            "questionnaireData": {},
            "caseData": {},
            "defaultData": {},
            "conditionalData": {}
        }
        
        # Create field mappings for database
        field_mappings = []
        
        # Map fields based on known structure and patterns
        for field_name, field_info in extracted_fields.items():
            mapped = False
            field_value = field_info['value'] if isinstance(field_info, dict) else field_info
            
            # Check if field belongs to known structure
            for category, expected_fields in form_structure.items():
                if any(exp_field.lower() in field_name.lower() for exp_field in expected_fields):
                    mapped_data[category][field_name] = field_value
                    db_mapping = get_db_mapping_for_field(self.form_type, category, field_name)
                    field_mappings.append({
                        'field_name': field_name,
                        'field_value': field_value,
                        'field_type': field_info.get('type', 'text') if isinstance(field_info, dict) else 'text',
                        'data_category': category,
                        'db_mapping': db_mapping,
                        'is_required': True
                    })
                    mapped = True
                    break
            
            # If not mapped, use pattern matching
            if not mapped:
                category = self.determine_category(field_name)
                mapped_data[category][field_name] = field_value
                db_mapping = get_db_mapping_for_field(self.form_type, category, field_name)
                field_mappings.append({
                    'field_name': field_name,
                    'field_value': field_value,
                    'field_type': field_info.get('type', 'text') if isinstance(field_info, dict) else 'text',
                    'data_category': category,
                    'db_mapping': db_mapping,
                    'is_required': False
                })
        
        # Save to database
        form_mapping_id = self.db.save_form_mapping(
            self.form_type,
            mapped_data['formname'],
            mapped_data['pdfName']
        )
        self.db.save_field_mappings(form_mapping_id, field_mappings)
        self.db.save_extracted_data(self.form_type, mapped_data)
        
        return mapped_data
    
    def determine_category(self, field_name: str) -> str:
        """Determine which category a field belongs to"""
        lower_field = field_name.lower()
        
        # Pattern-based categorization
        if any(pattern in lower_field for pattern in ['customer', 'petitioner', 'employer', 'company', 'ein']):
            return 'customerData'
        elif any(pattern in lower_field for pattern in ['beneficiary', 'applicant', 'alien', 'worker', 'ssn']):
            return 'beneficiaryData'
        elif any(pattern in lower_field for pattern in ['attorney', 'representative', 'lawyer', 'bar']):
            return 'attorneyData'
        elif any(pattern in lower_field for pattern in ['case', 'petition', 'application', 'receipt']):
            return 'caseData'
        else:
            return 'questionnaireData'
    
    def identify_missing_fields(self, mapped_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify fields that need to be collected via questionnaire"""
        missing_fields = []
        
        # Get expected structure for this form type
        expected_structure = KNOWN_FORM_STRUCTURES.get(self.form_type, {})
        
        # Check each data category
        for category, expected_fields in expected_structure.items():
            if category in mapped_data:
                extracted_field_names = set(key.lower() for key in mapped_data[category].keys())
                
                for expected_field in expected_fields:
                    # Check if field or similar field exists
                    if not any(expected_field.lower() in field for field in extracted_field_names):
                        missing_fields.append({
                            "category": category,
                            "fieldName": expected_field,
                            "fieldType": self.determine_field_type(expected_field),
                            "required": True,
                            "label": self.generate_field_label(expected_field),
                            "validation": self.get_field_validation(expected_field, self.determine_field_type(expected_field))
                        })
        
        self.missing_fields = missing_fields
        return missing_fields
    
    def determine_field_type(self, field_name: str) -> str:
        """Determine the appropriate field type based on field name"""
        lower_field = field_name.lower()
        
        if any(date_word in lower_field for date_word in ["date", "dob", "birth"]):
            return "date"
        elif any(num_word in lower_field for num_word in ["phone", "telephone", "fax"]):
            return "phone"
        elif "ssn" in lower_field or "social" in lower_field:
            return "ssn"
        elif "email" in lower_field or "e-mail" in lower_field:
            return "email"
        elif any(check_word in lower_field for check_word in ["is", "has", "yes", "no", "check"]):
            return "checkbox"
        elif any(select_word in lower_field for select_word in ["type", "status", "state", "gender"]):
            return "select"
        elif any(area_word in lower_field for area_word in ["description", "explain", "details"]):
            return "textarea"
        else:
            return "text"
    
    def generate_field_label(self, field_name: str) -> str:
        """Generate human-readable label from field name"""
        # Convert camelCase to Title Case
        label = re.sub(r'([A-Z])', r' \1', field_name)
        label = label.strip().title()
        
        # Replace common abbreviations
        replacements = {
            "Ssn": "Social Security Number",
            "Ein": "Employer Identification Number",
            "Dob": "Date of Birth",
            "Id": "ID",
            "Uscis": "USCIS"
        }
        
        for old, new in replacements.items():
            label = label.replace(old, new)
            
        return label
    
    def generate_questionnaire_json(self, missing_fields: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate questionnaire JSON for missing fields"""
        questionnaire = {
            "formType": self.form_type,
            "version": "1.0",
            "createdAt": datetime.now().isoformat(),
            "totalFields": len(missing_fields),
            "sections": {}
        }
        
        # Group fields by category
        for field in missing_fields:
            category = field["category"]
            if category not in questionnaire["sections"]:
                questionnaire["sections"][category] = {
                    "title": category.replace("Data", " Information").title(),
                    "description": f"Please provide the following {category.replace('Data', '').lower()} information",
                    "fields": []
                }
            
            field_def = {
                "id": field["fieldName"],
                "label": field["label"],
                "type": field["fieldType"],
                "required": field["required"],
                "validation": field.get("validation", {}),
                "placeholder": self.get_field_placeholder(field["fieldName"], field["fieldType"])
            }
            
            # Add options for select fields
            if field["fieldType"] == "select":
                field_def["options"] = self.get_field_options(field["fieldName"])
            
            questionnaire["sections"][category]["fields"].append(field_def)
        
        # Save to database
        self.db.save_questionnaire_template(self.form_type, questionnaire)
        
        # Save to file
        questionnaire_path = f"generated/questionnaires/{self.form_type}_questionnaire.json"
        with open(questionnaire_path, 'w') as f:
            json.dump(questionnaire, f, indent=2)
        
        return questionnaire
    
    def get_field_validation(self, field_name: str, field_type: str) -> Dict[str, Any]:
        """Get validation rules for specific fields"""
        validations = {
            "ssn": {
                "pattern": r"^\d{3}-\d{2}-\d{4}$",
                "message": "Format: XXX-XX-XXXX",
                "maxLength": 11
            },
            "phone": {
                "pattern": r"^\(?(\d{3})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})$",
                "message": "Format: (XXX) XXX-XXXX or XXX-XXX-XXXX",
                "maxLength": 14
            },
            "zip": {
                "pattern": r"^\d{5}(-\d{4})?$",
                "message": "Format: XXXXX or XXXXX-XXXX",
                "maxLength": 10
            },
            "alienNumber": {
                "pattern": r"^A?\d{8,9}$",
                "message": "Format: A followed by 8-9 digits",
                "maxLength": 10
            },
            "email": {
                "pattern": r"^[\w\.-]+@[\w\.-]+\.\w+$",
                "message": "Valid email required",
                "maxLength": 100
            },
            "ein": {
                "pattern": r"^\d{2}-\d{7}$",
                "message": "Format: XX-XXXXXXX",
                "maxLength": 10
            },
            "date": {
                "pattern": r"^\d{2}/\d{2}/\d{4}$",
                "message": "Format: MM/DD/YYYY",
                "maxLength": 10
            }
        }
        
        # Check field type first
        if field_type in validations:
            return validations[field_type]
        
        # Then check field name patterns
        for key, validation in validations.items():
            if key in field_name.lower():
                return validation
                
        # Default validation based on type
        if field_type == "text":
            return {"maxLength": 255}
        elif field_type == "textarea":
            return {"maxLength": 1000}
            
        return {}
    
    def get_field_placeholder(self, field_name: str, field_type: str) -> str:
        """Get placeholder text for fields"""
        placeholders = {
            "ssn": "123-45-6789",
            "phone": "(123) 456-7890",
            "email": "example@email.com",
            "date": "MM/DD/YYYY",
            "zip": "12345",
            "alienNumber": "A12345678",
            "ein": "12-3456789"
        }
        
        # Check field type
        if field_type in placeholders:
            return placeholders[field_type]
        
        # Check field name
        for key, placeholder in placeholders.items():
            if key in field_name.lower():
                return placeholder
        
        return f"Enter {self.generate_field_label(field_name).lower()}"
    
    def get_field_options(self, field_name: str) -> List[Dict[str, str]]:
        """Get options for select fields"""
        options_map = {
            "state": [
                {"value": "", "label": "Select State"},
                {"value": "AL", "label": "Alabama"},
                {"value": "AK", "label": "Alaska"},
                {"value": "AZ", "label": "Arizona"},
                {"value": "AR", "label": "Arkansas"},
                {"value": "CA", "label": "California"},
                {"value": "CO", "label": "Colorado"},
                {"value": "CT", "label": "Connecticut"},
                {"value": "DE", "label": "Delaware"},
                {"value": "FL", "label": "Florida"},
                {"value": "GA", "label": "Georgia"},
                {"value": "HI", "label": "Hawaii"},
                {"value": "ID", "label": "Idaho"},
                {"value": "IL", "label": "Illinois"},
                {"value": "IN", "label": "Indiana"},
                {"value": "IA", "label": "Iowa"},
                {"value": "KS", "label": "Kansas"},
                {"value": "KY", "label": "Kentucky"},
                {"value": "LA", "label": "Louisiana"},
                {"value": "ME", "label": "Maine"},
                {"value": "MD", "label": "Maryland"},
                {"value": "MA", "label": "Massachusetts"},
                {"value": "MI", "label": "Michigan"},
                {"value": "MN", "label": "Minnesota"},
                {"value": "MS", "label": "Mississippi"},
                {"value": "MO", "label": "Missouri"},
                {"value": "MT", "label": "Montana"},
                {"value": "NE", "label": "Nebraska"},
                {"value": "NV", "label": "Nevada"},
                {"value": "NH", "label": "New Hampshire"},
                {"value": "NJ", "label": "New Jersey"},
                {"value": "NM", "label": "New Mexico"},
                {"value": "NY", "label": "New York"},
                {"value": "NC", "label": "North Carolina"},
                {"value": "ND", "label": "North Dakota"},
                {"value": "OH", "label": "Ohio"},
                {"value": "OK", "label": "Oklahoma"},
                {"value": "OR", "label": "Oregon"},
                {"value": "PA", "label": "Pennsylvania"},
                {"value": "RI", "label": "Rhode Island"},
                {"value": "SC", "label": "South Carolina"},
                {"value": "SD", "label": "South Dakota"},
                {"value": "TN", "label": "Tennessee"},
                {"value": "TX", "label": "Texas"},
                {"value": "UT", "label": "Utah"},
                {"value": "VT", "label": "Vermont"},
                {"value": "VA", "label": "Virginia"},
                {"value": "WA", "label": "Washington"},
                {"value": "WV", "label": "West Virginia"},
                {"value": "WI", "label": "Wisconsin"},
                {"value": "WY", "label": "Wyoming"}
            ],
            "gender": [
                {"value": "", "label": "Select Gender"},
                {"value": "M", "label": "Male"},
                {"value": "F", "label": "Female"},
                {"value": "O", "label": "Other"}
            ],
            "maritalStatus": [
                {"value": "", "label": "Select Status"},
                {"value": "single", "label": "Single"},
                {"value": "married", "label": "Married"},
                {"value": "divorced", "label": "Divorced"},
                {"value": "widowed", "label": "Widowed"},
                {"value": "separated", "label": "Separated"}
            ],
            "addressType": [
                {"value": "", "label": "Select Type"},
                {"value": "apt", "label": "Apartment"},
                {"value": "ste", "label": "Suite"},
                {"value": "flr", "label": "Floor"}
            ],
            "caseType": [
                {"value": "", "label": "Select Case Type"},
                {"value": "H-1B", "label": "H-1B"},
                {"value": "H-2A", "label": "H-2A"},
                {"value": "H-2B", "label": "H-2B"},
                {"value": "L-1", "label": "L-1"},
                {"value": "O-1", "label": "O-1"},
                {"value": "TN", "label": "TN"}
            ],
            "caseSubType": [
                {"value": "", "label": "Select Sub Type"},
                {"value": "new_employment", "label": "New Employment"},
                {"value": "change_of_status", "label": "Change of Status"},
                {"value": "extension", "label": "Extension"},
                {"value": "amendment", "label": "Amendment"},
                {"value": "change_of_employer", "label": "Change of Employer"}
            ]
        }
        
        # Check exact match first
        if field_name in options_map:
            return options_map[field_name]
        
        # Then check if field name contains key
        for key, options in options_map.items():
            if key.lower() in field_name.lower():
                return options
                
        return [{"value": "", "label": "Select Option"}]
    
    def generate_typescript_file(self, mapped_data: Dict[str, Any], 
                               questionnaire: Dict[str, Any]) -> str:
        """Generate TypeScript file for the form"""
        ts_content = f"""export const {self.form_type.replace('-', '')} = {{
    "formname": "{mapped_data['formname']}",
    "pdfName": "{mapped_data['pdfName']}",
"""
        
        # Add data sections
        for section in ["customerData", "beneficiaryData", "attorneyData", 
                       "questionnaireData", "caseData", "defaultData", "conditionalData"]:
            if section in mapped_data and mapped_data[section]:
                ts_content += f'    "{section}": {{\n'
                
                # Sort fields alphabetically for consistency
                sorted_fields = sorted(mapped_data[section].items())
                
                for field_name, field_value in sorted_fields:
                    # Generate mapping string with proper formatting
                    mapping = self.generate_field_mapping(section, field_name)
                    field_type = self.determine_field_type(field_name)
                    
                    # Determine the UI element type
                    if field_type == "checkbox":
                        ui_type = "CheckBox"
                    elif field_type == "select":
                        ui_type = "SelectBox"
                    elif field_type == "date":
                        ui_type = "DatePicker"
                    elif field_type in ["ssn", "alienNumber"]:
                        ui_type = "SingleBox"
                    else:
                        ui_type = "TextBox"
                    
                    ts_content += f'        "{field_name}": "{mapping}:{ui_type}",\n'
                
                ts_content = ts_content.rstrip(',\n') + '\n'
                ts_content += '    },\n'
            else:
                ts_content += f'    "{section}": {{}},\n'
        
        ts_content = ts_content.rstrip(',\n') + '\n}'
        
        # Add questionnaire fields as comments
        if questionnaire and questionnaire.get("sections"):
            ts_content += "\n\n// Questionnaire fields for missing data:\n"
            ts_content += f"// Total missing fields: {questionnaire.get('totalFields', 0)}\n"
            ts_content += f"// Generated on: {questionnaire.get('createdAt', '')}\n\n"
            
            for section, section_data in questionnaire["sections"].items():
                ts_content += f"// {section_data['title']}:\n"
                for field in section_data["fields"]:
                    required = "Required" if field['required'] else "Optional"
                    ts_content += f"//   - {field['id']}: {field['type']} ({field['label']}) [{required}]\n"
                    if field.get('validation'):
                        ts_content += f"//     Validation: {field['validation'].get('message', '')}\n"
        
        # Save to database
        self.db.save_typescript_mapping(self.form_type, ts_content)
        
        # Save to file
        ts_path = f"generated/typescript/{self.form_type.replace('-', '')}.ts"
        with open(ts_path, 'w') as f:
            f.write(ts_content)
        
        return ts_content
    
    def generate_field_mapping(self, section: str, field_name: str) -> str:
        """Generate field mapping string based on section and field name"""
        # Use the mapping configuration if available
        db_mapping = get_db_mapping_for_field(self.form_type, section, field_name)
        
        if db_mapping and db_mapping != field_name:
            return db_mapping
        
        # Default mapping patterns
        if section == "customerData":
            return f"customer.{field_name}"
        elif section == "beneficiaryData":
            if "address" in field_name.lower():
                return f"beneficiary.HomeAddress.{field_name}"
            else:
                return f"beneficiary.Beneficiary.{field_name}"
        elif section == "attorneyData":
            if "address" in field_name.lower():
                return f"attorney.address.{field_name}"
            else:
                return f"attorney.attorneyInfo.{field_name}"
        elif section == "caseData":
            return f"case.{field_name}"
        elif section == "lcaData":
            return f"lca.Lca.{field_name}"
        else:
            return field_name

# Streamlit UI
def main():
    st.set_page_config(
        page_title="USCIS Form Processor",
        page_icon="📋",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Custom CSS
    st.markdown("""
    <style>
    .main {
        padding: 1rem;
    }
    .stButton > button {
        width: 100%;
    }
    .success-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
        margin: 1rem 0;
    }
    .warning-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #fff3cd;
        border: 1px solid #ffeeba;
        color: #856404;
        margin: 1rem 0;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.title("📋 USCIS Form Processor")
    st.markdown("Extract data from USCIS forms, map to database, and generate questionnaires")
    
    # Sidebar
    with st.sidebar:
        st.header("🛠️ Tools & Statistics")
        
        # Database statistics
        if st.button("📊 Show Statistics"):
            stats = st.session_state.db.get_mapping_statistics()
            st.metric("Total Forms", stats['total_forms'])
            st.metric("Total Fields", stats['total_fields'])
            
            if stats['fields_by_category']:
                st.subheader("Fields by Category")
                for category, count in stats['fields_by_category']:
                    st.write(f"- {category}: {count}")
        
        # Search functionality
        st.subheader("🔍 Search Fields")
        search_term = st.text_input("Search for field mappings")
        if search_term:
            results = st.session_state.db.search_field_mappings(search_term)
            if not results.empty:
                st.dataframe(results[['form_type', 'field_name', 'db_mapping']])
            else:
                st.info("No results found")
        
        # Export functionality
        if st.button("💾 Export All Mappings"):
            export_data = st.session_state.db.export_mappings_to_json()
            st.download_button(
                label="Download JSON Export",
                data=json.dumps(export_data, indent=2),
                file_name=f"uscis_mappings_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
    
    # Main content area
    tab1, tab2, tab3 = st.tabs(["📤 Upload & Process", "📋 Questionnaires", "💻 TypeScript Files"])
    
    with tab1:
        # File upload
        uploaded_file = st.file_uploader(
            "Choose a USCIS PDF form",
            type="pdf",
            help="Upload any USCIS form (I-90, I-129, G-28, etc.)"
        )
        
        if uploaded_file is not None:
            processor = USCISFormProcessor(st.session_state.db)
            
            # Create columns for layout
            col1, col2 = st.columns([1, 1])
            
            with col1:
                st.subheader("📄 Form Analysis")
                
                # Extract form fields
                with st.spinner("Extracting form fields..."):
                    extraction_result = processor.extract_form_fields(uploaded_file)
                
                # Form type detection
                if extraction_result['form_type'] != "Unknown":
                    st.success(f"✅ Form Type Detected: **{extraction_result['form_type']}**")
                else:
                    st.warning("⚠️ Could not detect form type automatically")
                
                # Display extracted fields
                st.write("### 📊 Extracted Fields")
                if extraction_result['fields']:
                    # Group fields by source
                    form_fields = {k: v for k, v in extraction_result['fields'].items() 
                                 if isinstance(v, dict) and v.get('source') == 'form_field'}
                    table_fields = {k: v for k, v in extraction_result['fields'].items() 
                                  if isinstance(v, dict) and v.get('source') == 'table'}
                    regex_fields = {k: v for k, v in extraction_result['fields'].items() 
                                  if isinstance(v, dict) and v.get('source') == 'regex'}
                    
                    if form_fields:
                        st.write("**Form Fields:**")
                        df_form = pd.DataFrame(
                            [(k, v['value'], v.get('type', 'text')) for k, v in form_fields.items()],
                            columns=['Field Name', 'Value', 'Type']
                        )
                        st.dataframe(df_form, use_container_width=True)
                    
                    if table_fields:
                        st.write("**Table Fields:**")
                        df_table = pd.DataFrame(
                            [(k, v['value'], v.get('type', 'text')) for k, v in table_fields.items()],
                            columns=['Field Name', 'Value', 'Type']
                        )
                        st.dataframe(df_table, use_container_width=True)
                    
                    if regex_fields:
                        st.write("**Extracted Fields:**")
                        df_regex = pd.DataFrame(
                            [(k, v['value'], v.get('type', 'text')) for k, v in regex_fields.items()],
                            columns=['Field Name', 'Value', 'Type']
                        )
                        st.dataframe(df_regex, use_container_width=True)
                    
                    st.info(f"Total fields extracted: {len(extraction_result['fields'])}")
                else:
                    st.warning("No fields could be extracted. The PDF might not contain fillable fields.")
                
                # Map to database structure
                st.write("### 🗄️ Database Mapping")
                mapped_data = processor.map_to_database_structure(extraction_result['fields'])
                
                # Display mapping summary
                mapping_summary = {}
                for category, data in mapped_data.items():
                    if isinstance(data, dict) and data:
                        mapping_summary[category] = len(data)
                
                if mapping_summary:
                    df_summary = pd.DataFrame(
                        [(k, v) for k, v in mapping_summary.items()],
                        columns=['Category', 'Field Count']
                    )
                    st.dataframe(df_summary, use_container_width=True)
            
            with col2:
                st.subheader("❓ Missing Fields & Questionnaire")
                
                # Identify missing fields
                missing_fields = processor.identify_missing_fields(mapped_data)
                
                if missing_fields:
                    st.warning(f"### ⚠️ {len(missing_fields)} Missing Fields Identified")
                    
                    # Display missing fields by category
                    missing_by_category = {}
                    for field in missing_fields:
                        category = field['category']
                        if category not in missing_by_category:
                            missing_by_category[category] = []
                        missing_by_category[category].append(field)
                    
                    for category, fields in missing_by_category.items():
                        with st.expander(f"{category} ({len(fields)} fields)", expanded=True):
                            for field in fields:
                                col_label, col_type = st.columns([3, 1])
                                with col_label:
                                    req_symbol = "🔴" if field['required'] else "🟡"
                                    st.write(f"{req_symbol} **{field['label']}**")
                                with col_type:
                                    st.write(f"*{field['fieldType']}*")
                                
                                if field.get('validation', {}).get('message'):
                                    st.caption(f"↳ {field['validation']['message']}")
                    
                    # Generate questionnaire
                    questionnaire = processor.generate_questionnaire_json(missing_fields)
                    
                    st.write("### 📝 Generated Questionnaire")
                    
                    # Display questionnaire preview
                    with st.expander("View Questionnaire Structure"):
                        st.json(questionnaire)
                    
                    # Download buttons
                    col_dl1, col_dl2 = st.columns(2)
                    with col_dl1:
                        json_str = json.dumps(questionnaire, indent=2)
                        st.download_button(
                            label="📥 Download Questionnaire JSON",
                            data=json_str,
                            file_name=f"{processor.form_type}_questionnaire.json",
                            mime="application/json"
                        )
                    
                    with col_dl2:
                        st.info(f"Saved to: generated/questionnaires/{processor.form_type}_questionnaire.json")
                else:
                    st.success("✅ All expected fields were found in the form!")
            
            # Generate TypeScript file
            st.subheader("💻 TypeScript File Generation")
            ts_content = processor.generate_typescript_file(mapped_data, 
                                                           questionnaire if missing_fields else {})
            
            # Display TypeScript content
            col_ts1, col_ts2 = st.columns([3, 1])
            with col_ts1:
                with st.expander("View Generated TypeScript File"):
                    st.code(ts_content, language="typescript")
            
            with col_ts2:
                # Download TypeScript file
                st.download_button(
                    label="📥 Download TypeScript",
                    data=ts_content,
                    file_name=f"{processor.form_type.replace('-', '')}.ts",
                    mime="text/typescript"
                )
                st.info(f"Saved to: generated/typescript/{processor.form_type.replace('-', '')}.ts")
            
            # Save to session state
            st.session_state.form_mappings[processor.form_type] = mapped_data
            if missing_fields:
                st.session_state.questionnaire_data[processor.form_type] = questionnaire
            
            # Display processing summary
            st.markdown("---")
            st.subheader("📊 Processing Summary")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Form Type", processor.form_type)
            with col2:
                st.metric("Fields Extracted", len(extraction_result['fields']))
            with col3:
                st.metric("Missing Fields", len(missing_fields))
            with col4:
                st.metric("Total Pages", extraction_result.get('total_pages', 0))
    
    with tab2:
        st.subheader("📋 Questionnaire Management")
        
        # Get all questionnaires from database
        form_types = st.session_state.db.get_form_mappings()['form_type'].unique().tolist()
        
        if form_types:
            selected_form = st.selectbox("Select a form type", form_types)
            
            if selected_form:
                questionnaire = st.session_state.db.get_latest_questionnaire(selected_form)
                
                if questionnaire:
                    st.success(f"Found questionnaire for {selected_form}")
                    
                    # Display questionnaire details
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Fields", questionnaire.get('totalFields', 0))
                    with col2:
                        st.metric("Sections", len(questionnaire.get('sections', {})))
                    with col3:
                        st.metric("Version", questionnaire.get('version', '1.0'))
                    
                    # Display sections
                    for section_name, section_data in questionnaire.get('sections', {}).items():
                        with st.expander(f"{section_data['title']} ({len(section_data['fields'])} fields)"):
                            st.write(section_data.get('description', ''))
                            
                            for field in section_data['fields']:
                                st.write(f"- **{field['label']}** ({field['id']})")
                                st.caption(f"  Type: {field['type']}, Required: {field['required']}")
                                if field.get('validation', {}).get('message'):
                                    st.caption(f"  Validation: {field['validation']['message']}")
                    
                    # Download button
                    st.download_button(
                        label=f"📥 Download {selected_form} Questionnaire",
                        data=json.dumps(questionnaire, indent=2),
                        file_name=f"{selected_form}_questionnaire.json",
                        mime="application/json"
                    )
                else:
                    st.info(f"No questionnaire found for {selected_form}")
        else:
            st.info("No forms have been processed yet.")
    
    with tab3:
        st.subheader("💻 TypeScript Files")
        
        # Get all TypeScript mappings from database
        form_types = st.session_state.db.get_form_mappings()['form_type'].unique().tolist()
        
        if form_types:
            selected_form = st.selectbox("Select a form type", form_types, key="ts_select")
            
            if selected_form:
                ts_content = st.session_state.db.get_typescript_mapping(selected_form)
                
                if ts_content:
                    st.success(f"Found TypeScript mapping for {selected_form}")
                    
                    # Display TypeScript content
                    st.code(ts_content, language="typescript")
                    
                    # Download button
                    st.download_button(
                        label=f"📥 Download {selected_form} TypeScript",
                        data=ts_content,
                        file_name=f"{selected_form.replace('-', '')}.ts",
                        mime="text/typescript"
                    )
                else:
                    st.info(f"No TypeScript mapping found for {selected_form}")
        else:
            st.info("No forms have been processed yet.")
    
    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #666;'>
            <p>USCIS Form Processor v1.0 | Built with Streamlit</p>
            <p>Supports all major USCIS forms including I-90, I-129, I-140, G-28, and more</p>
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
