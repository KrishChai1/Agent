#!/usr/bin/env python3
"""
UNIVERSAL USCIS FORM READER - ADVANCED VERSION WITH VALIDATION
==============================================================
Features: Option extraction with context, validation agent, improved field detection
"""

import streamlit as st
import json
import re
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field
import uuid
import traceback

# Page config
st.set_page_config(
    page_title="Advanced USCIS Form Reader",
    page_icon="📄",
    layout="wide"
)

# Check imports
try:
    import fitz
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    st.error("PyMuPDF not installed. Please run: pip install pymupdf")

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    st.warning("OpenAI not installed. Install with: pip install openai")

# Styles
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 10px;
        color: white;
        margin-bottom: 2rem;
        text-align: center;
    }
    .field-card {
        border: 1px solid #e0e0e0;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 8px;
        background: white;
    }
    .field-mapped {
        border-left: 4px solid #4caf50;
        background: #f1f8f4;
    }
    .field-questionnaire {
        border-left: 4px solid #2196f3;
        background: #e8f4fd;
    }
    .field-unmapped {
        border-left: 4px solid #ff9800;
        background: #fff8e1;
    }
    .field-subfield {
        margin-left: 30px;
        border-left: 3px dashed #9e9e9e;
        padding-left: 15px;
    }
    .parent-field {
        background: #f5f5f5;
        font-weight: bold;
    }
    .field-number-badge {
        background: #673ab7;
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: bold;
        display: inline-block;
        margin-right: 8px;
    }
    .option-chip {
        display: inline-block;
        padding: 4px 8px;
        margin: 2px;
        background: #e3f2fd;
        border: 1px solid #2196f3;
        border-radius: 16px;
        font-size: 0.9em;
    }
    .option-context {
        font-size: 0.85em;
        color: #666;
        margin-left: 20px;
        font-style: italic;
    }
    .validation-warning {
        background: #fff3cd;
        border-left: 4px solid #ffc107;
        padding: 10px;
        margin: 10px 0;
        border-radius: 4px;
    }
    .validation-error {
        background: #f8d7da;
        border-left: 4px solid #dc3545;
        padding: 10px;
        margin: 10px 0;
        border-radius: 4px;
    }
</style>
""", unsafe_allow_html=True)

# ===== DATA STRUCTURES =====

@dataclass
class FieldOption:
    """Option with associated context"""
    value: str
    context: str = ""  # Additional text/instructions for this option
    sub_options: List[str] = field(default_factory=list)

@dataclass
class FormField:
    """Enhanced field structure with validation"""
    item_number: str
    label: str
    field_type: str = "text"
    value: str = ""
    part_number: int = 1
    page_number: int = 1
    parent_number: str = ""
    is_parent: bool = False
    is_subfield: bool = False
    subfield_labels: List[str] = field(default_factory=list)
    is_mapped: bool = False
    in_questionnaire: bool = False
    db_object: str = ""
    db_path: str = ""
    unique_id: str = ""
    options: List[FieldOption] = field(default_factory=list)
    has_options: bool = False
    validation_rules: List[str] = field(default_factory=list)
    validation_errors: List[str] = field(default_factory=list)
    field_context: str = ""  # Additional context from form
    
    def __post_init__(self):
        if not self.unique_id:
            self.unique_id = str(uuid.uuid4())[:8]
        if self.options:
            self.has_options = True

@dataclass
class FormPart:
    """Part structure"""
    number: int
    title: str
    fields: List[FormField] = field(default_factory=list)
    page_start: int = 1
    page_end: int = 1
    instructions: str = ""  # Part-specific instructions

@dataclass
class USCISForm:
    """Form container"""
    form_number: str = "Unknown"
    form_title: str = "USCIS Form"
    edition_date: str = ""
    total_pages: int = 0
    parts: Dict[int, FormPart] = field(default_factory=dict)
    raw_text: str = ""
    validation_summary: Dict = field(default_factory=dict)

# ===== COMPLETE DATABASE SCHEMA =====

DATABASE_SCHEMA = {
    "beneficiary": {
        "label": "👤 Beneficiary/Applicant Information",
        "paths": [
            "beneficiaryLastName",
            "beneficiaryFirstName", 
            "beneficiaryMiddleName",
            "beneficiaryOtherNames",
            "beneficiaryDateOfBirth",
            "beneficiarySsn",
            "alienNumber",
            "uscisOnlineAccount",
            "beneficiaryCountryOfBirth",
            "beneficiaryCityOfBirth",
            "beneficiaryProvinceOfBirth",
            "beneficiaryCitizenOfCountry",
            "beneficiaryCellNumber",
            "beneficiaryWorkNumber",
            "beneficiaryPrimaryEmailAddress",
            "homeAddress.inCareOf",
            "homeAddress.streetNumber",
            "homeAddress.streetName",
            "homeAddress.apartmentType",
            "homeAddress.apartmentNumber",
            "homeAddress.city",
            "homeAddress.state",
            "homeAddress.zipCode",
            "homeAddress.zipCodePlus4",
            "homeAddress.province",
            "homeAddress.postalCode",
            "homeAddress.country",
            "physicalAddress.streetNumber",
            "physicalAddress.streetName",
            "physicalAddress.city",
            "physicalAddress.state",
            "physicalAddress.zipCode",
            "currentNonimmigrantStatus",
            "statusExpirationDate",
            "lastArrivalDate",
            "passportNumber",
            "passportCountry",
            "passportIssuedDate",
            "passportExpirationDate",
            "i94Number",
            "travelDocumentNumber",
            "sevisId",
            "dsNumber",
            "maritalStatus",
            "numberOfMarriages",
            "dateOfCurrentMarriage",
            "placeOfCurrentMarriage"
        ]
    },
    "petitioner": {
        "label": "🏢 Petitioner/Employer Information",
        "paths": [
            "petitionerName",
            "petitionerLastName",
            "petitionerFirstName",
            "petitionerMiddleName",
            "companyName",
            "companyTradeName",
            "companyTaxId",
            "companyFein",
            "companyWebsite",
            "signatoryFirstName",
            "signatoryLastName",
            "signatoryMiddleName",
            "signatoryJobTitle",
            "signatoryWorkPhone",
            "signatoryWorkPhoneExt",
            "signatoryMobilePhone",
            "signatoryEmailAddress",
            "companyAddress.streetNumber",
            "companyAddress.streetName",
            "companyAddress.suite",
            "companyAddress.city",
            "companyAddress.state",
            "companyAddress.zipCode",
            "companyAddress.province",
            "companyAddress.postalCode",
            "companyAddress.country",
            "yearEstablished",
            "numberOfEmployees",
            "numberOfUSEmployees",
            "grossAnnualIncome",
            "netAnnualIncome",
            "naicsCode",
            "businessType",
            "ownershipType"
        ]
    },
    "dependent": {
        "label": "👥 Dependent/Family Member Information",
        "paths": [
            "dependent[].lastName",
            "dependent[].firstName",
            "dependent[].middleName",
            "dependent[].dateOfBirth",
            "dependent[].countryOfBirth",
            "dependent[].countryOfCitizenship",
            "dependent[].alienNumber",
            "dependent[].i94Number",
            "dependent[].passportNumber",
            "dependent[].passportCountry",
            "dependent[].relationship",
            "dependent[].maritalStatus",
            "dependent[].address.streetNumber",
            "dependent[].address.streetName",
            "dependent[].address.apartment",
            "dependent[].address.city",
            "dependent[].address.state",
            "dependent[].address.zipCode",
            "dependent[].applyingWithYou"
        ]
    },
    "attorney": {
        "label": "⚖️ Attorney/Representative Information",
        "paths": [
            "attorneyLastName",
            "attorneyFirstName",
            "attorneyMiddleName",
            "attorneyWorkPhone",
            "attorneyWorkPhoneExt",
            "attorneyMobilePhone",
            "attorneyEmailAddress",
            "attorneyStateBarNumber",
            "attorneyUscisOnlineAccount",
            "attorneyAddress.streetNumber",
            "attorneyAddress.streetName",
            "attorneyAddress.suite",
            "attorneyAddress.city",
            "attorneyAddress.state",
            "attorneyAddress.zipCode",
            "lawFirmName",
            "lawFirmFein",
            "attorneyEligibilityCategory"
        ]
    },
    "application": {
        "label": "📋 Application/Case Information",
        "paths": [
            "caseNumber",
            "receiptNumber",
            "priorityDate",
            "filingDate",
            "approvalDate",
            "applicationType",
            "requestedStatus",
            "requestedClassification",
            "changeOfStatusFrom",
            "changeOfStatusTo",
            "extensionFrom",
            "extensionTo",
            "processingLocation",
            "consulateLocation",
            "portOfEntry",
            "dateOfEntry",
            "mannerOfEntry",
            "previousPetitionReceipt",
            "basisForClassification",
            "requestedValidityPeriod"
        ]
    },
    "employment": {
        "label": "💼 Employment Information",
        "paths": [
            "jobTitle",
            "jobCode",
            "socCode",
            "workLocation.streetNumber",
            "workLocation.streetName",
            "workLocation.city",
            "workLocation.state",
            "workLocation.zipCode",
            "annualSalary",
            "wagePerHour",
            "hoursPerWeek",
            "employmentStartDate",
            "employmentEndDate",
            "previousEmployer",
            "previousJobTitle",
            "previousEmploymentDates"
        ]
    },
    "custom": {
        "label": "✏️ Manual/Custom Fields",
        "paths": []
    }
}

# ===== VALIDATION RULES =====

VALIDATION_RULES = {
    "ssn": {
        "pattern": r'^\d{3}-?\d{2}-?\d{4}$',
        "message": "SSN must be in format XXX-XX-XXXX"
    },
    "ein": {
        "pattern": r'^\d{2}-?\d{7}$',
        "message": "EIN must be in format XX-XXXXXXX"
    },
    "alien_number": {
        "pattern": r'^[A]\d{8,9}$|^\d{8,9}$',
        "message": "Alien Number must be 8-9 digits, optionally starting with 'A'"
    },
    "email": {
        "pattern": r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
        "message": "Invalid email format"
    },
    "phone": {
        "pattern": r'^(\+1)?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}$',
        "message": "Phone must be in format (XXX) XXX-XXXX"
    },
    "date": {
        "pattern": r'^\d{2}/\d{2}/\d{4}$|^\d{4}-\d{2}-\d{2}$',
        "message": "Date must be in format MM/DD/YYYY or YYYY-MM-DD"
    },
    "zip": {
        "pattern": r'^\d{5}(-\d{4})?$',
        "message": "ZIP code must be in format XXXXX or XXXXX-XXXX"
    }
}

# ===== ENHANCED EXTRACTION FUNCTIONS =====

def extract_field_options_with_context(label: str, form_text: str, field_number: str) -> List[FieldOption]:
    """Extract options with their associated context/instructions"""
    options = []
    label_lower = label.lower()
    
    # Try to find the field in the form text for context
    field_context = ""
    try:
        # Look for the field number in the text
        pattern = re.escape(field_number) + r'[.\s]+' + re.escape(label[:30])
        match = re.search(pattern, form_text, re.IGNORECASE)
        if match:
            start = match.start()
            end = min(start + 1000, len(form_text))
            field_context = form_text[start:end]
    except:
        pass
    
    # Extract checkbox/radio options from context
    if field_context:
        # Look for checkbox patterns: □ Option or ☐ Option
        checkbox_pattern = r'[□☐]\s*([^\n□☐]{3,100})'
        matches = re.findall(checkbox_pattern, field_context)
        for match in matches:
            option_text = match.strip()
            if option_text:
                # Check if there's additional context after the option
                context = ""
                context_pattern = re.escape(option_text) + r'\s*[:\-]?\s*([^\n□☐]{5,200})'
                context_match = re.search(context_pattern, field_context)
                if context_match:
                    context = context_match.group(1).strip()
                
                options.append(FieldOption(
                    value=option_text.split('.')[0].strip(),
                    context=context
                ))
    
    # Common field types with predefined options
    if not options:
        if any(word in label_lower for word in ["yes/no", "yes or no", "check if", "are you", "do you", "have you"]):
            options = [
                FieldOption(value="Yes", context="Select if applicable"),
                FieldOption(value="No", context="Select if not applicable")
            ]
        elif "gender" in label_lower or "sex" in label_lower:
            options = [
                FieldOption(value="Male"),
                FieldOption(value="Female"),
                FieldOption(value="Other", context="Specify if selected")
            ]
        elif "marital" in label_lower:
            options = [
                FieldOption(value="Single", context="Never married"),
                FieldOption(value="Married", context="Currently married"),
                FieldOption(value="Divorced", context="Marriage legally ended"),
                FieldOption(value="Widowed", context="Spouse deceased"),
                FieldOption(value="Separated", context="Legally separated")
            ]
        elif "employment" in label_lower and "status" in label_lower:
            options = [
                FieldOption(value="Employed", context="Currently working"),
                FieldOption(value="Unemployed", context="Not currently working"),
                FieldOption(value="Self-employed", context="Own business"),
                FieldOption(value="Student", context="Full-time student"),
                FieldOption(value="Retired", context="No longer working")
            ]
        elif "relationship" in label_lower:
            options = [
                FieldOption(value="Spouse", context="Husband or wife"),
                FieldOption(value="Child", context="Son or daughter"),
                FieldOption(value="Parent", context="Mother or father"),
                FieldOption(value="Sibling", context="Brother or sister"),
                FieldOption(value="Other", context="Specify relationship")
            ]
        elif "status" in label_lower and any(word in label_lower for word in ["immigration", "visa", "nonimmigrant"]):
            options = [
                FieldOption(value="H-1B", context="Specialty occupation"),
                FieldOption(value="L-1", context="Intracompany transferee"),
                FieldOption(value="F-1", context="Student"),
                FieldOption(value="B-1/B-2", context="Business/Tourist"),
                FieldOption(value="O-1", context="Extraordinary ability"),
                FieldOption(value="Other", context="Specify status")
            ]
    
    return options

def detect_field_type_enhanced(label: str, context: str = "") -> Tuple[str, List[FieldOption]]:
    """Enhanced field type detection with better categorization"""
    label_lower = label.lower()
    
    # Check for specific field types
    if any(word in label_lower for word in ["check", "select", "mark", "choose", "indicate"]):
        options = extract_field_options_with_context(label, context, "")
        return ("checkbox" if len(options) <= 2 else "select"), options
    
    # Date fields
    if any(word in label_lower for word in ["date", "dob", "birth", "expir", "issued", "validity"]):
        return "date", []
    
    # Number fields with specific types
    if "ssn" in label_lower or "social security" in label_lower:
        return "ssn", []
    elif "ein" in label_lower or "tax id" in label_lower:
        return "ein", []
    elif "alien" in label_lower and "number" in label_lower:
        return "alien_number", []
    elif any(word in label_lower for word in ["number", "receipt", "case"]):
        return "number", []
    
    # Contact fields
    if any(word in label_lower for word in ["email", "e-mail"]):
        return "email", []
    elif any(word in label_lower for word in ["phone", "telephone", "mobile", "cell", "fax"]):
        return "phone", []
    
    # Address components
    if "zip" in label_lower or "postal code" in label_lower:
        return "zip", []
    elif any(word in label_lower for word in ["address", "street", "city", "state"]):
        return "address", []
    
    # Text area for longer responses
    if any(word in label_lower for word in ["explain", "describe", "list", "additional"]):
        return "textarea", []
    
    return "text", []

def detect_address_components(label: str) -> List[str]:
    """Enhanced address component detection"""
    label_lower = label.lower()
    
    # US Address
    if "address" in label_lower and "foreign" not in label_lower:
        if "mailing" in label_lower:
            return [
                "In Care Of Name (if any)",
                "Street Number",
                "Street Name",
                "Apt./Ste./Flr. Type",
                "Apt./Ste./Flr. Number",
                "City or Town",
                "State",
                "ZIP Code",
                "ZIP Code Plus 4"
            ]
        else:
            return [
                "Street Number",
                "Street Name",
                "Apt./Ste./Flr. Number",
                "City or Town",
                "State",
                "ZIP Code"
            ]
    
    # Foreign Address
    elif "foreign" in label_lower or "abroad" in label_lower:
        return [
            "Street Number",
            "Street Name",
            "Apartment Number",
            "City or Town",
            "Province or State",
            "Postal Code",
            "Country"
        ]
    
    # Name fields
    elif "name" in label_lower:
        if "full" in label_lower or "legal" in label_lower:
            return [
                "Family Name (Last Name)",
                "Given Name (First Name)",
                "Middle Name (if any)",
                "Other Names Used (if any)"
            ]
        elif "maiden" in label_lower or "other" in label_lower:
            return ["Family Name", "Given Name", "Middle Name"]
    
    return []

# ===== VALIDATION AGENT =====

class ValidationAgent:
    """AI-powered validation agent for form fields"""
    
    def __init__(self, openai_client=None):
        self.client = openai_client
        
    def validate_field(self, field: FormField) -> List[str]:
        """Validate a single field and return errors/warnings"""
        errors = []
        
        if not field.value:
            if field.field_type not in ["checkbox", "select"]:
                return []  # Empty fields are okay unless required
        
        # Type-specific validation
        if field.field_type == "ssn":
            if not re.match(VALIDATION_RULES["ssn"]["pattern"], field.value):
                errors.append(VALIDATION_RULES["ssn"]["message"])
                
        elif field.field_type == "ein":
            if not re.match(VALIDATION_RULES["ein"]["pattern"], field.value):
                errors.append(VALIDATION_RULES["ein"]["message"])
                
        elif field.field_type == "alien_number":
            if not re.match(VALIDATION_RULES["alien_number"]["pattern"], field.value):
                errors.append(VALIDATION_RULES["alien_number"]["message"])
                
        elif field.field_type == "email":
            if not re.match(VALIDATION_RULES["email"]["pattern"], field.value):
                errors.append(VALIDATION_RULES["email"]["message"])
                
        elif field.field_type == "phone":
            if not re.match(VALIDATION_RULES["phone"]["pattern"], field.value):
                errors.append(VALIDATION_RULES["phone"]["message"])
                
        elif field.field_type == "date":
            if not re.match(VALIDATION_RULES["date"]["pattern"], field.value):
                errors.append(VALIDATION_RULES["date"]["message"])
                
        elif field.field_type == "zip":
            if not re.match(VALIDATION_RULES["zip"]["pattern"], field.value):
                errors.append(VALIDATION_RULES["zip"]["message"])
        
        return errors
    
    def validate_form_with_ai(self, form: USCISForm) -> Dict:
        """Use AI to validate entire form and provide feedback"""
        if not self.client:
            return {"status": "AI validation not available", "issues": []}
        
        # Collect all field data
        form_data = []
        for part in form.parts.values():
            for field in part.fields:
                if not field.is_parent and field.value:
                    form_data.append({
                        "field": field.item_number,
                        "label": field.label,
                        "value": field.value,
                        "type": field.field_type
                    })
        
        if not form_data:
            return {"status": "No data to validate", "issues": []}
        
        try:
            prompt = f"""
            Review this USCIS form data for completeness and accuracy.
            Identify any issues, inconsistencies, or missing critical information.
            
            Form: {form.form_number}
            Data: {json.dumps(form_data[:50], indent=2)}  
            
            Return JSON with structure:
            {{
                "overall_status": "complete/incomplete/needs_review",
                "completeness_score": 0-100,
                "critical_missing": ["list of critical missing fields"],
                "warnings": ["list of warnings"],
                "suggestions": ["list of suggestions"]
            }}
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=1000
            )
            
            content = response.choices[0].message.content.strip()
            if "```" in content:
                content = content.split("```")[1].replace("json", "").strip()
            
            return json.loads(content)
            
        except Exception as e:
            return {"status": "Validation error", "error": str(e)[:100]}
    
    def suggest_improvements(self, field: FormField) -> List[str]:
        """Suggest improvements for field values"""
        suggestions = []
        
        if field.field_type == "phone" and field.value:
            # Suggest formatting
            digits = re.sub(r'\D', '', field.value)
            if len(digits) == 10:
                formatted = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
                if formatted != field.value:
                    suggestions.append(f"Consider formatting as: {formatted}")
        
        elif field.field_type == "date" and field.value:
            # Suggest consistent date format
            if "-" in field.value:
                suggestions.append("Consider using MM/DD/YYYY format for consistency")
        
        return suggestions

# ===== FORM EXTRACTOR =====

class UniversalFormExtractor:
    """Advanced form extractor with AI validation"""
    
    def __init__(self):
        self.setup_openai()
        self.validator = ValidationAgent(self.client)
    
    def setup_openai(self):
        """Setup OpenAI client"""
        if not OPENAI_AVAILABLE:
            self.client = None
            return
            
        api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        
        if api_key:
            try:
                self.client = openai.OpenAI(api_key=api_key)
                st.success("✅ OpenAI connected - using GPT-4o for enhanced extraction")
            except Exception as e:
                st.warning(f"Could not initialize OpenAI: {str(e)[:100]}")
                self.client = None
        else:
            self.client = None
            st.info("Add OPENAI_API_KEY for AI-powered extraction and validation")
    
    def extract_form(self, full_text: str, page_texts: Dict[int, str], total_pages: int) -> USCISForm:
        """Extract form with enhanced field detection"""
        try:
            form_info = self._identify_form(full_text[:3000])
            
            form = USCISForm(
                form_number=form_info.get("form_number", "Unknown"),
                form_title=form_info.get("form_title", "USCIS Form"),
                edition_date=form_info.get("edition_date", ""),
                total_pages=total_pages,
                raw_text=full_text
            )
            
            parts_data = self._extract_parts_enhanced(full_text)
            
            for part_data in parts_data:
                part = FormPart(
                    number=part_data["number"],
                    title=part_data["title"],
                    page_start=part_data.get("page_start", 1),
                    page_end=part_data.get("page_end", 1),
                    instructions=part_data.get("instructions", "")
                )
                
                try:
                    part.fields = self._extract_fields_with_options(full_text, part_data)
                except Exception as e:
                    st.warning(f"Error extracting Part {part_data['number']}: {str(e)[:100]}")
                    part.fields = []
                
                form.parts[part.number] = part
            
            return form
            
        except Exception as e:
            st.error(f"Form extraction error: {str(e)}")
            return USCISForm(
                form_number="Unknown",
                form_title="USCIS Form",
                parts={1: FormPart(number=1, title="Main Section", fields=[])}
            )
    
    def _identify_form(self, text: str) -> Dict:
        """Identify form using AI"""
        form_match = re.search(r'Form\s+([A-Z]-?\d+[A-Z]?)', text)
        form_number = form_match.group(1) if form_match else "Unknown"
        
        if not self.client:
            return {"form_number": form_number, "form_title": "USCIS Form", "edition_date": ""}
        
        try:
            prompt = """Extract form number, title, and edition date. Return JSON only."""
            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt + "\n\n" + text}],
                temperature=0,
                max_tokens=200
            )
            
            content = response.choices[0].message.content.strip()
            if "```" in content:
                content = content.split("```")[1].replace("json", "").strip()
            return json.loads(content)
        except:
            return {"form_number": form_number, "form_title": "USCIS Form", "edition_date": ""}
    
    def _extract_parts_enhanced(self, text: str) -> List[Dict]:
        """Extract parts with instructions"""
        if self.client:
            try:
                prompt = """
                Extract ALL parts from this USCIS form.
                Include any instructions or notes for each part.
                
                Return JSON array:
                [{
                    "number": 1,
                    "title": "Part Title",
                    "instructions": "Any specific instructions for this part",
                    "page_start": 1,
                    "page_end": 2
                }]
                """
                
                response = self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt + "\n\n" + text[:12000]}],
                    temperature=0,
                    max_tokens=2000
                )
                
                content = response.choices[0].message.content.strip()
                if "```" in content:
                    content = content.split("```")[1].replace("json", "").strip()
                
                parts = json.loads(content)
                if parts:
                    return parts
            except:
                pass
        
        # Fallback
        parts = []
        part_matches = re.finditer(r'Part\s+(\d+)[.\s]+([^\n]+)', text)
        for match in part_matches:
            parts.append({
                "number": int(match.group(1)),
                "title": match.group(2).strip(),
                "instructions": "",
                "page_start": 1,
                "page_end": 1
            })
        
        return parts if parts else [{"number": 1, "title": "Main Section"}]
    
    def _extract_fields_with_options(self, text: str, part_data: Dict) -> List[FormField]:
        """Extract fields with complete options and context"""
        part_num = part_data["number"]
        
        # Use AI if available
        if self.client:
            try:
                fields = self._extract_with_ai(text, part_data)
                if fields:
                    return fields
            except:
                pass
        
        # Fallback to pattern matching
        return self._extract_with_patterns(text, part_data)
    
    def _extract_with_ai(self, text: str, part_data: Dict) -> List[FormField]:
        """Use GPT-4o for accurate field extraction"""
        try:
            # Find part-specific text
            part_text = self._get_part_text(text, part_data["number"])
            
            prompt = f"""
            Extract ALL form fields from Part {part_data['number']}: {part_data['title']}.
            
            For EACH field provide:
            1. Field number (e.g., "1", "1.a", "2.b")
            2. Complete field label
            3. Field type (text, date, checkbox, select, address, name, etc.)
            4. All available options with their context/instructions
            5. Whether it has subfields
            
            For address fields, include ALL components:
            - Street Number (separate from Street Name)
            - Street Name
            - Apartment/Suite/Floor Type
            - Apartment/Suite/Floor Number
            - City, State, ZIP, ZIP+4
            
            Return JSON array with complete field information.
            Include parent fields AND their subfields.
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt + "\n\n" + part_text[:10000]}],
                temperature=0,
                max_tokens=4000
            )
            
            content = response.choices[0].message.content.strip()
            if "```" in content:
                content = content.split("```")[1].replace("json", "").strip()
            
            raw_fields = json.loads(content)
            return self._process_ai_fields(raw_fields, part_data["number"], text)
            
        except Exception as e:
            st.warning(f"AI extraction failed: {str(e)[:100]}")
            return []
    
    def _process_ai_fields(self, raw_fields: List[Dict], part_num: int, full_text: str) -> List[FormField]:
        """Process AI-extracted fields into FormField objects"""
        processed_fields = []
        
        for field_data in raw_fields:
            item_number = str(field_data.get("item_number", "")).strip()
            label = field_data.get("label", "").strip()
            field_type = field_data.get("type", "text")
            
            # Extract options with context
            options = []
            if "options" in field_data:
                for opt in field_data["options"]:
                    if isinstance(opt, dict):
                        options.append(FieldOption(
                            value=opt.get("value", ""),
                            context=opt.get("context", "")
                        ))
                    else:
                        options.append(FieldOption(value=str(opt)))
            
            # Determine if parent/subfield
            is_subfield = '.' in item_number and len(item_number.split('.')[1]) == 1
            is_parent = field_data.get("has_subfields", False)
            
            field = FormField(
                item_number=item_number,
                label=label,
                field_type=field_type,
                part_number=part_num,
                is_parent=is_parent,
                is_subfield=is_subfield,
                options=options,
                field_context=field_data.get("context", "")
            )
            
            if is_subfield:
                field.parent_number = item_number.split('.')[0]
            
            # Auto-detect address components if needed
            if is_parent and "address" in label.lower():
                field.subfield_labels = detect_address_components(label)
            
            processed_fields.append(field)
        
        return processed_fields
    
    def _extract_with_patterns(self, text: str, part_data: Dict) -> List[FormField]:
        """Fallback pattern-based extraction"""
        fields = []
        part_text = self._get_part_text(text, part_data["number"])
        
        # Pattern for fields
        pattern = r'(\d+\.?[a-z]?)\s+([^\n]{5,150})'
        matches = re.finditer(pattern, part_text[:8000])
        
        for match in matches:
            item_number = match.group(1).rstrip('.')
            label = match.group(2).strip()
            
            # Get field context
            start = match.start()
            end = min(start + 500, len(part_text))
            context = part_text[start:end]
            
            # Detect type and options
            field_type, options = detect_field_type_enhanced(label, context)
            
            # Check if address field needs components
            components = detect_address_components(label)
            
            is_subfield = '.' in item_number and len(item_number.split('.')[1]) == 1
            is_parent = bool(components)
            
            field = FormField(
                item_number=item_number,
                label=label,
                field_type=field_type if not is_parent else "parent",
                part_number=part_data["number"],
                is_parent=is_parent,
                is_subfield=is_subfield,
                options=options,
                subfield_labels=components
            )
            
            if is_subfield:
                field.parent_number = item_number.split('.')[0]
            
            fields.append(field)
            
            # Create subfields for components
            if components and not is_subfield:
                for i, comp in enumerate(components):
                    letter = chr(ord('a') + i)
                    sub_type, _ = detect_field_type_enhanced(comp)
                    
                    subfield = FormField(
                        item_number=f"{item_number}.{letter}",
                        label=comp,
                        field_type=sub_type,
                        part_number=part_data["number"],
                        parent_number=item_number,
                        is_subfield=True
                    )
                    fields.append(subfield)
        
        return fields[:100]  # Limit fields
    
    def _get_part_text(self, text: str, part_num: int) -> str:
        """Extract text for specific part"""
        try:
            pattern = f"Part\\s+{part_num}"
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                start = match.start()
                next_pattern = f"Part\\s+{part_num + 1}"
                next_match = re.search(next_pattern, text[start:], re.IGNORECASE)
                if next_match:
                    return text[start:start + next_match.start()]
                return text[start:start + 15000]
        except:
            pass
        return text[:15000]

# ===== UI COMPONENTS =====

def display_field_enhanced(field: FormField, key_prefix: str, validator: ValidationAgent):
    """Enhanced field display with validation feedback"""
    unique_key = f"{key_prefix}_{field.unique_id}"
    
    # Validate field
    if field.value:
        field.validation_errors = validator.validate_field(field)
    
    # Determine style
    card_class = ""
    if field.is_parent:
        card_class = "parent-field"
        status = "📁 Parent"
    elif field.validation_errors:
        card_class = "field-card validation-error"
        status = "⚠️ Invalid"
    elif field.in_questionnaire:
        card_class = "field-questionnaire"
        status = "📝 Quest"
    elif field.is_mapped:
        card_class = "field-mapped"
        status = "✅ Mapped"
    else:
        card_class = "field-unmapped"
        status = "❓ Unmapped"
    
    st.markdown(f'<div class="field-card {card_class}">', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([3, 2, 2])
    
    with col1:
        st.markdown(f'<span class="field-number-badge">{field.item_number}</span>**{field.label}**', unsafe_allow_html=True)
        
        # Show options with context
        if field.has_options and field.options:
            for opt in field.options:
                opt_html = f'<span class="option-chip">{opt.value}</span>'
                if opt.context:
                    opt_html += f'<span class="option-context"> - {opt.context}</span>'
                st.markdown(opt_html, unsafe_allow_html=True)
        
        # Show validation errors
        if field.validation_errors:
            for error in field.validation_errors:
                st.markdown(f'<div class="validation-error">⚠️ {error}</div>', unsafe_allow_html=True)
        
        # Show suggestions
        suggestions = validator.suggest_improvements(field)
        if suggestions:
            for suggestion in suggestions:
                st.info(f"💡 {suggestion}")
    
    with col2:
        if not field.is_parent:
            if field.field_type == "date":
                date_val = st.date_input("", key=f"{unique_key}_date", label_visibility="collapsed")
                field.value = str(date_val) if date_val else ""
            elif field.field_type == "textarea":
                field.value = st.text_area("", value=field.value, key=f"{unique_key}_area", height=100, label_visibility="collapsed")
            elif field.options:
                # Show select with option context as help
                option_values = [opt.value for opt in field.options]
                selected_idx = 0
                if field.value in option_values:
                    selected_idx = option_values.index(field.value) + 1
                
                field.value = st.selectbox(
                    "",
                    [""] + option_values,
                    index=selected_idx,
                    key=f"{unique_key}_sel",
                    label_visibility="collapsed"
                )
                
                # Show context for selected option
                if field.value:
                    for opt in field.options:
                        if opt.value == field.value and opt.context:
                            st.caption(opt.context)
            else:
                field.value = st.text_input("", value=field.value, key=f"{unique_key}_val", label_visibility="collapsed")
    
    with col3:
        st.markdown(f"**{status}**")
        if not field.is_parent:
            c1, c2 = st.columns(2)
            with c1:
                if not field.is_mapped and not field.in_questionnaire:
                    if st.button("Map", key=f"{unique_key}_map"):
                        st.session_state[f"mapping_{field.unique_id}"] = True
                        st.rerun()
            with c2:
                if not field.is_mapped and not field.in_questionnaire:
                    if st.button("Quest", key=f"{unique_key}_quest"):
                        field.in_questionnaire = True
                        st.rerun()
                elif field.is_mapped or field.in_questionnaire:
                    if st.button("Clear", key=f"{unique_key}_clear"):
                        field.is_mapped = False
                        field.in_questionnaire = False
                        field.db_object = ""
                        field.db_path = ""
                        st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Mapping dialog
    if st.session_state.get(f"mapping_{field.unique_id}"):
        show_mapping(field, unique_key)

def show_mapping(field: FormField, unique_key: str):
    """Mapping interface"""
    st.markdown("---")
    st.markdown("### 🔗 Map Field to Database")
    
    col1, col2 = st.columns(2)
    
    with col1:
        db_options = list(DATABASE_SCHEMA.keys())
        db_labels = [DATABASE_SCHEMA[k]["label"] for k in db_options]
        
        selected_idx = st.selectbox(
            "Database Object",
            range(len(db_options)),
            format_func=lambda x: db_labels[x],
            key=f"{unique_key}_dbobj",
            index=None,
            placeholder="Select database object..."
        )
        selected_obj = db_options[selected_idx] if selected_idx is not None else None
    
    with col2:
        if selected_obj:
            if selected_obj == "custom":
                path = st.text_input("Custom path", key=f"{unique_key}_custom", placeholder="Enter custom path")
            else:
                paths = DATABASE_SCHEMA[selected_obj]["paths"]
                path = st.selectbox(
                    "Field Path",
                    [""] + paths + ["[custom]"],
                    key=f"{unique_key}_path",
                    placeholder="Select field path..."
                )
                
                if path == "[custom]":
                    path = st.text_input("Enter custom path", key=f"{unique_key}_custpath")
    
    if selected_obj and path:
        st.info(f"📍 Mapping: {field.item_number} → {selected_obj}.{path}")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Apply", key=f"{unique_key}_apply", type="primary"):
            if selected_obj and path:
                field.is_mapped = True
                field.db_object = selected_obj
                field.db_path = path
                del st.session_state[f"mapping_{field.unique_id}"]
                st.success("Mapped successfully!")
                st.rerun()
    with col2:
        if st.button("Cancel", key=f"{unique_key}_cancel"):
            del st.session_state[f"mapping_{field.unique_id}"]
            st.rerun()

def extract_pdf_text(pdf_file) -> Tuple[str, Dict[int, str], int]:
    """Extract text from PDF"""
    if not PYMUPDF_AVAILABLE:
        st.error("PyMuPDF is not available")
        return "", {}, 0
    
    try:
        pdf_file.seek(0)
        pdf_bytes = pdf_file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        full_text = ""
        page_texts = {}
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            if text.strip():
                page_texts[page_num + 1] = text
                full_text += f"\n=== PAGE {page_num + 1} ===\n{text}"
        
        total_pages = len(doc)
        doc.close()
        
        return full_text, page_texts, total_pages
        
    except Exception as e:
        st.error(f"PDF extraction error: {str(e)}")
        return "", {}, 0

# ===== MAIN APPLICATION =====

def main():
    st.markdown('<div class="main-header"><h1>📄 Advanced USCIS Form Reader</h1><p>AI-Powered Extraction with Validation</p></div>', unsafe_allow_html=True)
    
    # Initialize
    if 'form' not in st.session_state:
        st.session_state.form = None
    if 'extractor' not in st.session_state:
        st.session_state.extractor = UniversalFormExtractor()
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 📊 Database Schema")
        
        for key, info in DATABASE_SCHEMA.items():
            with st.expander(info["label"]):
                if key == "custom":
                    st.info("Enter any custom path")
                else:
                    paths = info["paths"]
                    st.info(f"{len(paths)} paths available")
                    for path in paths[:5]:
                        st.code(path)
                    if len(paths) > 5:
                        st.caption(f"... +{len(paths)-5} more")
        
        st.markdown("---")
        
        if st.button("🔄 Clear All", type="secondary", use_container_width=True):
            st.session_state.clear()
            st.rerun()
        
        if st.session_state.form:
            st.markdown("## 📈 Statistics")
            form = st.session_state.form
            
            total_fields = sum(len(p.fields) for p in form.parts.values())
            mapped = sum(1 for p in form.parts.values() for f in p.fields if f.is_mapped)
            quest = sum(1 for p in form.parts.values() for f in p.fields if f.in_questionnaire)
            with_options = sum(1 for p in form.parts.values() for f in p.fields if f.has_options)
            
            st.metric("Total Fields", total_fields)
            st.metric("Mapped", mapped)
            st.metric("Questionnaire", quest)
            st.metric("With Options", with_options)
    
    # Main tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📤 Upload", "🔗 Map", "📝 Questionnaire", "✅ Validate", "💾 Export"])
    
    with tab1:
        st.markdown("### Upload USCIS Form")
        
        uploaded_file = st.file_uploader("Choose PDF file", type=['pdf'])
        
        if uploaded_file:
            if st.button("🚀 Extract Form with AI", type="primary", use_container_width=True):
                with st.spinner("Extracting with GPT-4o..."):
                    try:
                        full_text, page_texts, total_pages = extract_pdf_text(uploaded_file)
                        
                        if full_text:
                            form = st.session_state.extractor.extract_form(full_text, page_texts, total_pages)
                            st.session_state.form = form
                            st.success(f"✅ Extracted: {form.form_number}")
                            
                            # Show statistics
                            total_fields = sum(len(p.fields) for p in form.parts.values())
                            with_options = sum(1 for p in form.parts.values() for f in p.fields if f.has_options)
                            
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Parts", len(form.parts))
                            with col2:
                                st.metric("Fields", total_fields)
                            with col3:
                                st.metric("With Options", with_options)
                            
                            if with_options > 0:
                                st.info(f"🎯 Extracted {with_options} fields with complete options and context")
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
    
    with tab2:
        if st.session_state.form:
            st.markdown("### Map Fields to Database")
            
            form = st.session_state.form
            validator = st.session_state.extractor.validator
            
            for part_num, part in form.parts.items():
                with st.expander(f"Part {part_num}: {part.title}", expanded=(part_num == 1)):
                    if part.instructions:
                        st.info(f"📋 {part.instructions}")
                    
                    displayed = set()
                    for field in part.fields:
                        if field.item_number not in displayed:
                            if not field.is_subfield:
                                display_field_enhanced(field, f"p{part_num}", validator)
                                displayed.add(field.item_number)
                                
                                if field.is_parent:
                                    for sub in part.fields:
                                        if sub.parent_number == field.item_number:
                                            display_field_enhanced(sub, f"p{part_num}", validator)
                                            displayed.add(sub.item_number)
        else:
            st.info("Upload a form first")
    
    with tab3:
        if st.session_state.form:
            st.markdown("### Questionnaire Fields")
            
            for part in st.session_state.form.parts.values():
                quest_fields = [f for f in part.fields if f.in_questionnaire and not f.is_parent]
                
                if quest_fields:
                    st.markdown(f"#### Part {part.number}: {part.title}")
                    
                    for field in quest_fields:
                        st.markdown(f'<span class="field-number-badge">{field.item_number}</span>**{field.label}**', unsafe_allow_html=True)
                        
                        if field.options:
                            # Show all options with context
                            st.markdown("**Available Options:**")
                            for opt in field.options:
                                if opt.context:
                                    st.markdown(f"• **{opt.value}** - {opt.context}")
                                else:
                                    st.markdown(f"• {opt.value}")
                            
                            # Select answer
                            option_values = [opt.value for opt in field.options]
                            field.value = st.selectbox(
                                "Select answer",
                                [""] + option_values,
                                key=f"q_{field.unique_id}"
                            )
                        else:
                            field.value = st.text_area("Answer", value=field.value, key=f"q_{field.unique_id}")
                        
                        if st.button("Remove", key=f"qr_{field.unique_id}"):
                            field.in_questionnaire = False
                            st.rerun()
                        
                        st.markdown("---")
        else:
            st.info("No questionnaire fields")
    
    with tab4:
        st.markdown("### AI Validation Agent")
        
        if st.session_state.form and st.session_state.extractor.client:
            if st.button("🤖 Run AI Validation", type="primary"):
                with st.spinner("Validating form with AI..."):
                    validator = st.session_state.extractor.validator
                    validation_result = validator.validate_form_with_ai(st.session_state.form)
                    
                    # Display results
                    if "completeness_score" in validation_result:
                        score = validation_result["completeness_score"]
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Completeness Score", f"{score}%")
                        with col2:
                            status = validation_result.get("overall_status", "unknown")
                            if status == "complete":
                                st.success(f"Status: {status.upper()}")
                            elif status == "incomplete":
                                st.warning(f"Status: {status.upper()}")
                            else:
                                st.info(f"Status: {status.upper()}")
                        
                        # Critical missing fields
                        if validation_result.get("critical_missing"):
                            st.markdown("### ⚠️ Critical Missing Fields")
                            for item in validation_result["critical_missing"]:
                                st.error(f"• {item}")
                        
                        # Warnings
                        if validation_result.get("warnings"):
                            st.markdown("### ⚡ Warnings")
                            for warning in validation_result["warnings"]:
                                st.warning(f"• {warning}")
                        
                        # Suggestions
                        if validation_result.get("suggestions"):
                            st.markdown("### 💡 Suggestions")
                            for suggestion in validation_result["suggestions"]:
                                st.info(f"• {suggestion}")
                    else:
                        st.error("Validation failed")
        else:
            st.info("AI validation requires OpenAI API key and form data")
    
    with tab5:
        st.markdown("### Export Data")
        
        if st.session_state.form:
            form = st.session_state.form
            
            # Export options
            export_data = {
                "form_info": {
                    "form_number": form.form_number,
                    "form_title": form.form_title,
                    "edition_date": form.edition_date
                },
                "fields": []
            }
            
            for part in form.parts.values():
                for field in part.fields:
                    if not field.is_parent:
                        field_data = {
                            "part": part.number,
                            "number": field.item_number,
                            "label": field.label,
                            "value": field.value,
                            "type": field.field_type,
                            "options": [{"value": opt.value, "context": opt.context} for opt in field.options] if field.options else None
                        }
                        
                        if field.is_mapped:
                            field_data["mapping"] = f"{field.db_object}.{field.db_path}"
                        
                        export_data["fields"].append(field_data)
            
            json_str = json.dumps(export_data, indent=2)
            
            st.download_button(
                "📥 Download Complete Export",
                json_str,
                f"{form.form_number}_complete.json",
                "application/json",
                use_container_width=True,
                type="primary"
            )

if __name__ == "__main__":
    main()
