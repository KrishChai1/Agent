#!/usr/bin/env python3
"""
UNIVERSAL USCIS FORM READER - FINAL VERSION
============================================
Correctly extracts all parts and maintains proper field sequence
"""

import streamlit as st
import json
import re
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field as dataclass_field
import uuid

# Page config
st.set_page_config(
    page_title="USCIS Form Reader - Final",
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
    .validation-error {
        color: #dc3545;
        font-size: 0.9em;
        margin-top: 5px;
    }
</style>
""", unsafe_allow_html=True)

# ===== DATA STRUCTURES =====

@dataclass
class FormField:
    """Field structure with proper ordering"""
    item_number: str
    label: str
    field_type: str = "text"
    value: str = ""
    part_number: int = 1
    page_number: int = 1
    parent_number: str = ""
    is_parent: bool = False
    is_subfield: bool = False
    subfield_labels: List[str] = dataclass_field(default_factory=list)
    is_mapped: bool = False
    in_questionnaire: bool = False
    db_object: str = ""
    db_path: str = ""
    unique_id: str = ""
    options: List[str] = dataclass_field(default_factory=list)
    option_contexts: Dict[str, str] = dataclass_field(default_factory=dict)
    has_options: bool = False
    sort_order: float = 0.0  # For proper field ordering
    
    def __post_init__(self):
        if not self.unique_id:
            self.unique_id = str(uuid.uuid4())[:8]
        if self.options:
            self.has_options = True
        # Calculate sort order for proper sequence
        self._calculate_sort_order()
    
    def _calculate_sort_order(self):
        """Calculate sort order for proper field sequence"""
        try:
            if '.' in self.item_number:
                parts = self.item_number.split('.')
                main = int(parts[0])
                sub = ord(parts[1][0]) - ord('a') + 1
                self.sort_order = main + (sub * 0.01)
            else:
                self.sort_order = float(self.item_number)
        except:
            self.sort_order = 999

@dataclass
class FormPart:
    """Part structure"""
    number: int
    title: str
    fields: List[FormField] = dataclass_field(default_factory=list)
    page_start: int = 1
    page_end: int = 1

@dataclass
class USCISForm:
    """Form container"""
    form_number: str = "Unknown"
    form_title: str = "USCIS Form"
    edition_date: str = ""
    total_pages: int = 0
    parts: Dict[int, FormPart] = dataclass_field(default_factory=dict)
    raw_text: str = ""

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
            "beneficiaryDaytimeNumber",
            "beneficiaryWorkNumber",
            "beneficiaryEmail",
            "homeAddress.inCareOfName",
            "homeAddress.streetNumberAndName",
            "homeAddress.aptSteFlrType",
            "homeAddress.aptSteFlrNumber",
            "homeAddress.cityOrTown",
            "homeAddress.state",
            "homeAddress.zipCode",
            "homeAddress.zipCodePlus4",
            "homeAddress.province",
            "homeAddress.postalCode",
            "homeAddress.country",
            "mailingAddress.inCareOfName",
            "mailingAddress.streetNumberAndName",
            "mailingAddress.aptSteFlrType",
            "mailingAddress.aptSteFlrNumber",
            "mailingAddress.cityOrTown",
            "mailingAddress.state",
            "mailingAddress.zipCode",
            "mailingAddress.zipCodePlus4",
            "physicalAddress.streetNumberAndName",
            "physicalAddress.aptSteFlrType",
            "physicalAddress.aptSteFlrNumber",
            "physicalAddress.cityOrTown",
            "physicalAddress.state",
            "physicalAddress.zipCode",
            "foreignAddress.streetNumberAndName",
            "foreignAddress.aptSteFlrNumber",
            "foreignAddress.cityOrTown",
            "foreignAddress.province",
            "foreignAddress.postalCode",
            "foreignAddress.country",
            "currentNonimmigrantStatus",
            "statusExpirationDate",
            "i94ArrivalDepartureNumber",
            "passportNumber",
            "passportCountryOfIssuance",
            "passportDateOfIssuance",
            "passportDateOfExpiration",
            "dateOfLastArrival",
            "placeOfLastArrival",
            "immigrationStatus",
            "sevisId",
            "eadCardNumber"
        ]
    },
    "petitioner": {
        "label": "🏢 Petitioner/Employer Information",
        "paths": [
            "petitionerLastName",
            "petitionerFirstName",
            "petitionerMiddleName",
            "petitionerCompanyName",
            "petitionerDBA",
            "petitionerTaxId",
            "petitionerFEIN",
            "petitionerSSN",
            "petitionerWebsite",
            "petitionerPhone",
            "petitionerPhoneExt",
            "petitionerMobilePhone",
            "petitionerEmail",
            "petitionerContactLastName",
            "petitionerContactFirstName",
            "petitionerContactMiddleName",
            "petitionerContactTitle",
            "petitionerContactPhone",
            "petitionerContactPhoneExt",
            "petitionerContactMobilePhone",
            "petitionerContactEmail",
            "petitionerAddress.streetNumberAndName",
            "petitionerAddress.aptSteFlrType",
            "petitionerAddress.aptSteFlrNumber",
            "petitionerAddress.cityOrTown",
            "petitionerAddress.state",
            "petitionerAddress.zipCode",
            "petitionerAddress.zipCodePlus4",
            "petitionerAddress.province",
            "petitionerAddress.postalCode",
            "petitionerAddress.country",
            "petitionerMailingAddress.inCareOfName",
            "petitionerMailingAddress.streetNumberAndName",
            "petitionerMailingAddress.aptSteFlrType",
            "petitionerMailingAddress.aptSteFlrNumber",
            "petitionerMailingAddress.cityOrTown",
            "petitionerMailingAddress.state",
            "petitionerMailingAddress.zipCode",
            "petitionerYearEstablished",
            "petitionerNumberOfEmployees",
            "petitionerGrossAnnualIncome",
            "petitionerNetAnnualIncome",
            "petitionerNAICSCode",
            "petitionerTypeOfBusiness"
        ]
    },
    "employment": {
        "label": "💼 Employment Information",
        "paths": [
            "jobTitle",
            "socCode",
            "naicsCode",
            "numberOfOpenings",
            "wageRangeFrom",
            "wageRangeTo",
            "wageUnit",
            "prevailingWage",
            "workAddress.streetNumberAndName",
            "workAddress.aptSteFlrType",
            "workAddress.aptSteFlrNumber",
            "workAddress.cityOrTown",
            "workAddress.state",
            "workAddress.zipCode",
            "employmentStartDate",
            "employmentEndDate",
            "hoursPerWeek"
        ]
    },
    "dependent": {
        "label": "👥 Dependent/Family Member",
        "paths": [
            "dependent[].lastName",
            "dependent[].firstName",
            "dependent[].middleName",
            "dependent[].relationship",
            "dependent[].dateOfBirth",
            "dependent[].sex",
            "dependent[].countryOfBirth",
            "dependent[].cityOfBirth",
            "dependent[].countryOfCitizenship",
            "dependent[].alienNumber",
            "dependent[].i94Number",
            "dependent[].passportNumber",
            "dependent[].passportCountry",
            "dependent[].passportExpiration",
            "dependent[].maritalStatus",
            "dependent[].applyingWithYou"
        ]
    },
    "attorney": {
        "label": "⚖️ Attorney/Representative",
        "paths": [
            "attorneyLastName",
            "attorneyFirstName",
            "attorneyMiddleName",
            "attorneyBusinessName",
            "attorneyAddress.streetNumberAndName",
            "attorneyAddress.aptSteFlrType",
            "attorneyAddress.aptSteFlrNumber",
            "attorneyAddress.cityOrTown",
            "attorneyAddress.state",
            "attorneyAddress.zipCode",
            "attorneyAddress.zipCodePlus4",
            "attorneyContactPhone",
            "attorneyContactPhoneExt",
            "attorneyContactMobilePhone",
            "attorneyContactEmail",
            "attorneyFaxNumber",
            "attorneyUSCISOnlineNumber",
            "attorneyStateBarNumber",
            "attorneyLicensingAuthority"
        ]
    },
    "preparer": {
        "label": "📝 Preparer Information",
        "paths": [
            "preparerLastName",
            "preparerFirstName",
            "preparerBusinessName",
            "preparerAddress.streetNumberAndName",
            "preparerAddress.aptSteFlrType",
            "preparerAddress.aptSteFlrNumber",
            "preparerAddress.cityOrTown",
            "preparerAddress.state",
            "preparerAddress.zipCode",
            "preparerContactPhone",
            "preparerContactPhoneExt",
            "preparerContactEmail"
        ]
    },
    "custom": {
        "label": "✏️ Custom Fields",
        "paths": []
    }
}

# ===== HELPER FUNCTIONS =====

def extract_pdf_text(pdf_file) -> Tuple[str, Dict[int, str], int]:
    """Extract text from PDF with better handling"""
    if not PYMUPDF_AVAILABLE:
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
                full_text += f"\n\n=== PAGE {page_num + 1} ===\n{text}"
        
        total_pages = len(doc)
        doc.close()
        
        return full_text, page_texts, total_pages
        
    except Exception as e:
        st.error(f"PDF extraction error: {str(e)}")
        return "", {}, 0

def extract_field_options(label: str, context: str = "") -> Tuple[List[str], Dict[str, str]]:
    """Extract all options from checkbox/select fields"""
    options = []
    option_contexts = {}
    label_lower = label.lower()
    
    # Check context for checkbox patterns
    if context:
        # Multiple checkbox patterns
        patterns = [
            r'[□☐]\s*([^\n□☐]{2,100})',
            r'\[\s*\]\s*([^\n\[\]]{2,100})',
            r'○\s*([^\n○]{2,100})',
            r'•\s*([^\n•]{2,100})'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, context)
            for match in matches[:20]:  # Allow more options
                option = match.strip()
                if option and len(option) > 1:
                    # Clean option text
                    option = re.sub(r'\s+', ' ', option)
                    option = option.split('(')[0].strip()  # Remove parenthetical info
                    
                    if option not in options:
                        options.append(option)
                        
                        # Try to find additional context
                        context_pattern = re.escape(option) + r'[:\-\s]*\(([^)]+)\)'
                        context_match = re.search(context_pattern, context)
                        if context_match:
                            option_contexts[option] = context_match.group(1).strip()
    
    # Common field types with options
    if not options:
        if any(word in label_lower for word in ["yes/no", "yes or no", "check if"]):
            options = ["Yes", "No"]
        elif "gender" in label_lower or "sex" in label_lower:
            options = ["Male", "Female"]
        elif "marital" in label_lower:
            options = ["Single", "Married", "Divorced", "Widowed", "Separated", "Marriage Annulled"]
        elif "relationship" in label_lower:
            options = ["Spouse", "Child", "Parent", "Sibling", "Other"]
        elif "country" in label_lower and "citizenship" in label_lower:
            options = []  # Too many to list
        elif "state" in label_lower and not "statement" in label_lower:
            options = []  # State dropdown
    
    return options, option_contexts

def detect_field_type(label: str) -> str:
    """Detect field type from label"""
    label_lower = label.lower()
    
    # Specific field types
    if any(word in label_lower for word in ["date", "dob", "birth", "expir", "issued"]):
        return "date"
    elif "email" in label_lower or "e-mail" in label_lower:
        return "email"
    elif any(word in label_lower for word in ["phone", "telephone", "mobile", "daytime", "evening"]):
        return "phone"
    elif "ssn" in label_lower or "social security" in label_lower:
        return "ssn"
    elif ("alien" in label_lower and "number" in label_lower) or "a-number" in label_lower or "uscis number" in label_lower:
        return "alien_number"
    elif "zip" in label_lower or "postal code" in label_lower:
        return "zip"
    elif any(word in label_lower for word in ["check", "select", "mark", "choose", "indicate"]):
        return "checkbox"
    elif any(word in label_lower for word in ["explain", "describe", "list", "additional information"]):
        return "textarea"
    elif any(word in label_lower for word in ["number", "no.", "#", "receipt", "case"]):
        return "number"
    
    return "text"

def detect_address_components(label: str) -> List[str]:
    """Detect proper address components in correct order"""
    label_lower = label.lower()
    
    # Mailing/Physical US Address
    if "address" in label_lower and "foreign" not in label_lower:
        components = []
        
        # Check if "in care of" is likely
        if "mailing" in label_lower:
            components.append("In Care Of Name (if any)")
        
        # Standard US address components in USCIS order
        components.extend([
            "Street Number and Name",
            "Apt./Ste./Flr.",  # Type selection
            "Number",  # Apartment/Suite/Floor number
            "City or Town",
            "State",
            "ZIP Code",
            "ZIP Code + 4 (if available)"
        ])
        
        # Add country for some forms
        if "country" in label_lower or "international" in label_lower:
            components.append("Country")
        
        return components
    
    # Foreign/International Address
    elif "foreign" in label_lower or "abroad" in label_lower or "international" in label_lower:
        return [
            "Street Number and Name",
            "Apartment Number",
            "City or Town",
            "Province or State",
            "Postal Code",
            "Country"
        ]
    
    # Name fields
    elif "name" in label_lower:
        if "full" in label_lower or "legal" in label_lower:
            components = [
                "Family Name (Last Name)",
                "Given Name (First Name)",
                "Middle Name (if any)"
            ]
            
            # Check for other names
            if "other" in label_lower or "alias" in label_lower:
                components.append("Other Names Used (if any)")
            
            return components
        elif "company" in label_lower or "organization" in label_lower or "business" in label_lower:
            return []  # Company names are single field
    
    return []

# ===== FORM EXTRACTOR =====

class FormExtractor:
    """Form extraction with proper part and field ordering"""
    
    def __init__(self):
        self.client = None
        self.setup_openai()
    
    def setup_openai(self):
        """Setup OpenAI client"""
        if not OPENAI_AVAILABLE:
            return
        
        try:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                api_key = st.secrets.get("OPENAI_API_KEY", None)
            
            if api_key:
                self.client = openai.OpenAI(api_key=api_key)
                st.success("✅ OpenAI GPT-4 connected for enhanced extraction")
        except Exception as e:
            st.warning(f"OpenAI setup failed: {str(e)[:100]}")
            self.client = None
    
    def extract_form(self, full_text: str, page_texts: Dict[int, str], total_pages: int) -> USCISForm:
        """Extract complete form with all parts and fields"""
        try:
            # Identify form
            form_info = self._identify_form(full_text[:5000])
            
            form = USCISForm(
                form_number=form_info.get("form_number", "Unknown"),
                form_title=form_info.get("form_title", "USCIS Form"),
                edition_date=form_info.get("edition_date", ""),
                total_pages=total_pages,
                raw_text=full_text
            )
            
            # Extract ALL parts
            parts = self._extract_all_parts(full_text)
            
            if not parts:
                st.warning("No parts found, creating default structure")
                parts = [{"number": 1, "title": "Information", "page_start": 1}]
            
            # Process each part
            for part_info in parts:
                st.info(f"Processing Part {part_info['number']}: {part_info['title']}")
                
                part = FormPart(
                    number=part_info["number"],
                    title=part_info["title"],
                    page_start=part_info.get("page_start", 1),
                    page_end=part_info.get("page_end", total_pages)
                )
                
                # Extract fields for this part with proper ordering
                part_fields = self._extract_part_fields(full_text, part_info)
                
                # Sort fields by item number for proper sequence
                part_fields.sort(key=lambda f: f.sort_order)
                
                part.fields = part_fields
                form.parts[part.number] = part
            
            return form
            
        except Exception as e:
            st.error(f"Form extraction error: {str(e)}")
            return USCISForm(
                form_number="Unknown",
                form_title="USCIS Form",
                total_pages=total_pages,
                parts={1: FormPart(number=1, title="Main Section", fields=[])}
            )
    
    def _identify_form(self, text: str) -> Dict:
        """Identify form number and title"""
        result = {"form_number": "Unknown", "form_title": "USCIS Form", "edition_date": ""}
        
        # Try regex patterns
        patterns = [
            r'Form\s+([A-Z]-\d+[A-Z]?)',
            r'Form\s+([A-Z]+\d+[A-Z]?)',
            r'USCIS\s+Form\s+([A-Z]-?\d+[A-Z]?)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result["form_number"] = match.group(1)
                break
        
        # Try AI extraction if available
        if self.client:
            try:
                response = self.client.chat.completions.create(
                    model="gpt-4o" if "gpt-4o" in str(self.client.models.list()) else "gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "Extract USCIS form information. Return JSON only."},
                        {"role": "user", "content": f"Extract form number, title, and edition date:\n{text[:2000]}"}
                    ],
                    temperature=0,
                    max_tokens=200
                )
                
                content = response.choices[0].message.content.strip()
                if "{" in content:
                    json_str = content[content.find("{"):content.rfind("}")+1]
                    data = json.loads(json_str)
                    result.update(data)
            except:
                pass
        
        return result
    
    def _extract_all_parts(self, text: str) -> List[Dict]:
        """Extract ALL parts from the form"""
        parts = []
        
        # First try with AI for best results
        if self.client:
            try:
                prompt = """Extract ALL parts from this USCIS form.
                Include every part number and exact title.
                Return as JSON array with structure:
                [{"number": 1, "title": "Part Title", "page_start": 1}]
                
                Text:
                """
                
                response = self.client.chat.completions.create(
                    model="gpt-4o" if "gpt-4o" in str(self.client.models.list()) else "gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "Extract all form parts accurately. Return JSON array only."},
                        {"role": "user", "content": prompt + text[:8000]}
                    ],
                    temperature=0,
                    max_tokens=2000
                )
                
                content = response.choices[0].message.content.strip()
                if "[" in content:
                    json_str = content[content.find("["):content.rfind("]")+1]
                    parts = json.loads(json_str)
                    
                    if parts:
                        st.success(f"AI extracted {len(parts)} parts")
                        return parts
            except Exception as e:
                st.warning(f"AI part extraction failed: {str(e)[:100]}")
        
        # Comprehensive regex patterns for parts
        patterns = [
            r'Part\s+(\d+)[.\s\-–—]+([^\n\r]{3,150})',
            r'Part\s+(\d+)\s*\n\s*([^\n\r]{3,150})',
            r'PART\s+(\d+)[.\s\-–—]+([^\n\r]{3,150})',
            r'Section\s+(\d+)[.\s\-–—]+([^\n\r]{3,150})'
        ]
        
        found_parts = {}
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            
            for match in matches:
                try:
                    part_num = int(match.group(1))
                    part_title = match.group(2).strip()
                    
                    # Clean title
                    part_title = re.sub(r'^[.\-–—\s]+', '', part_title)
                    part_title = re.sub(r'[.\s]+$', '', part_title)
                    part_title = re.sub(r'\s+', ' ', part_title)
                    
                    # Skip if title is too short or looks like a page number
                    if len(part_title) < 3 or part_title.isdigit():
                        continue
                    
                    # Store part (use first occurrence)
                    if part_num not in found_parts:
                        found_parts[part_num] = {
                            "number": part_num,
                            "title": part_title,
                            "page_start": 1
                        }
                except:
                    continue
        
        # Convert to sorted list
        parts = sorted(found_parts.values(), key=lambda x: x["number"])
        
        st.info(f"Regex extracted {len(parts)} parts")
        
        return parts
    
    def _extract_part_fields(self, text: str, part_info: Dict) -> List[FormField]:
        """Extract fields for a specific part with proper sequencing"""
        part_num = part_info["number"]
        part_title = part_info["title"]
        
        # Get part-specific text
        part_text = self._get_part_text(text, part_num)
        
        fields = []
        
        # Try AI extraction first
        if self.client:
            try:
                fields = self._extract_fields_with_ai(part_text, part_num)
                if fields:
                    st.success(f"AI extracted {len(fields)} fields for Part {part_num}")
                    return fields
            except Exception as e:
                st.warning(f"AI field extraction failed for Part {part_num}: {str(e)[:100]}")
        
        # Fallback to pattern extraction
        fields = self._extract_fields_with_patterns(part_text, part_num)
        st.info(f"Pattern extracted {len(fields)} fields for Part {part_num}")
        
        return fields
    
    def _get_part_text(self, text: str, part_num: int) -> str:
        """Extract text for a specific part"""
        try:
            # Find part start
            part_patterns = [
                f"Part\\s+{part_num}\\b",
                f"PART\\s+{part_num}\\b",
                f"Section\\s+{part_num}\\b"
            ]
            
            start_pos = -1
            for pattern in part_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    start_pos = match.start()
                    break
            
            if start_pos == -1:
                return ""
            
            # Find next part
            next_part_pattern = f"Part\\s+{part_num + 1}\\b|PART\\s+{part_num + 1}\\b"
            next_match = re.search(next_part_pattern, text[start_pos:], re.IGNORECASE)
            
            if next_match:
                end_pos = start_pos + next_match.start()
                return text[start_pos:end_pos]
            else:
                # Return up to 15000 characters
                return text[start_pos:min(start_pos + 15000, len(text))]
            
        except:
            return text[:15000]
    
    def _extract_fields_with_ai(self, text: str, part_num: int) -> List[FormField]:
        """Use AI to extract fields with proper structure"""
        try:
            prompt = f"""Extract ALL fields from Part {part_num} of this USCIS form.
            
            IMPORTANT:
            1. Include ALL fields with their exact numbers (1, 1.a, 1.b, 2, 2.a, etc.)
            2. For address fields, include ALL subfields:
               - In Care Of Name
               - Street Number and Name
               - Apt./Ste./Flr. (selection)
               - Number (apt/ste/flr number)
               - City or Town
               - State
               - ZIP Code
               - ZIP Code + 4
            3. For name fields, include:
               - Family Name (Last Name)
               - Given Name (First Name)
               - Middle Name
            4. Include all checkbox/radio options
            
            Return JSON array with structure:
            [{{
                "item_number": "1.a",
                "label": "Family Name (Last Name)",
                "type": "text",
                "options": []
            }}]
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4o" if "gpt-4o" in str(self.client.models.list()) else "gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Extract form fields accurately. Return valid JSON array only."},
                    {"role": "user", "content": prompt + "\n\n" + text[:6000]}
                ],
                temperature=0,
                max_tokens=4000
            )
            
            content = response.choices[0].message.content.strip()
            
            # Extract JSON
            if "[" in content:
                json_str = content[content.find("["):content.rfind("]")+1]
                raw_fields = json.loads(json_str)
                
                # Convert to FormField objects
                fields = []
                for field_data in raw_fields:
                    item_number = str(field_data.get("item_number", "")).strip()
                    label = field_data.get("label", "").strip()
                    
                    if not item_number or not label:
                        continue
                    
                    field_type = field_data.get("type", "text")
                    options = field_data.get("options", [])
                    
                    # Check if address field needs subfields
                    components = detect_address_components(label)
                    
                    # Determine parent/subfield
                    is_subfield = '.' in item_number and item_number.split('.')[1].isalpha()
                    is_parent = bool(components) and not is_subfield
                    
                    field = FormField(
                        item_number=item_number,
                        label=label,
                        field_type=field_type if not is_parent else "parent",
                        part_number=part_num,
                        is_parent=is_parent,
                        is_subfield=is_subfield,
                        subfield_labels=components,
                        options=options if isinstance(options, list) else []
                    )
                    
                    if is_subfield:
                        field.parent_number = item_number.split('.')[0]
                    
                    fields.append(field)
                    
                    # Auto-create subfields for address/name components
                    if components and not is_subfield:
                        for i, comp in enumerate(components):
                            letter = chr(ord('a') + i)
                            subfield = FormField(
                                item_number=f"{item_number}.{letter}",
                                label=comp,
                                field_type=detect_field_type(comp),
                                part_number=part_num,
                                parent_number=item_number,
                                is_subfield=True
                            )
                            fields.append(subfield)
                
                return fields
                
        except Exception as e:
            st.error(f"AI field extraction error: {str(e)}")
            return []
        
        return []
    
    def _extract_fields_with_patterns(self, text: str, part_num: int) -> List[FormField]:
        """Extract fields using regex patterns"""
        fields = []
        
        # Comprehensive field patterns
        patterns = [
            r'(\d+)\.\s*([^\n\r]{5,200})',  # 1. Field Label
            r'(\d+)\s+([^\n\r]{5,200})',     # 1 Field Label
            r'(\d+[a-z])\.\s*([^\n\r]{5,200})',  # 1a. Field Label
            r'(\d+\.[a-z])\s*([^\n\r]{5,200})',  # 1.a Field Label
        ]
        
        found_fields = {}
        
        for pattern in patterns:
            matches = re.finditer(pattern, text[:10000])
            
            for match in matches:
                item_number = match.group(1).strip('.').strip()
                label = match.group(2).strip()
                
                # Normalize item number
                if re.match(r'^\d+[a-z]$', item_number):
                    # Convert "1a" to "1.a"
                    item_number = item_number[:-1] + '.' + item_number[-1]
                
                # Skip if already found
                if item_number in found_fields:
                    continue
                
                # Clean label
                label = re.sub(r'\s+', ' ', label)
                label = re.sub(r'^[.\-\s]+', '', label)
                
                # Skip invalid labels
                if len(label) < 3 or label.isdigit():
                    continue
                
                # Get context for options
                start = match.start()
                end = min(start + 800, len(text))
                context = text[start:end]
                
                # Extract options
                options, option_contexts = extract_field_options(label, context)
                
                # Detect field type
                field_type = detect_field_type(label)
                
                # Check for address/name components
                components = detect_address_components(label)
                
                # Create field
                is_subfield = '.' in item_number and len(item_number.split('.')[1]) == 1
                is_parent = bool(components) and not is_subfield
                
                field = FormField(
                    item_number=item_number,
                    label=label,
                    field_type=field_type if not is_parent else "parent",
                    part_number=part_num,
                    is_parent=is_parent,
                    is_subfield=is_subfield,
                    subfield_labels=components,
                    options=options,
                    option_contexts=option_contexts
                )
                
                if is_subfield:
                    field.parent_number = item_number.split('.')[0]
                
                found_fields[item_number] = field
                
                # Create subfields for components
                if components and not is_subfield:
                    for i, comp in enumerate(components):
                        letter = chr(ord('a') + i)
                        subfield_num = f"{item_number}.{letter}"
                        
                        if subfield_num not in found_fields:
                            subfield = FormField(
                                item_number=subfield_num,
                                label=comp,
                                field_type=detect_field_type(comp),
                                part_number=part_num,
                                parent_number=item_number,
                                is_subfield=True
                            )
                            found_fields[subfield_num] = subfield
        
        # Convert to list and sort
        fields = list(found_fields.values())
        fields.sort(key=lambda f: f.sort_order)
        
        return fields[:100]  # Limit to 100 fields per part

# ===== UI COMPONENTS =====

def display_field(field: FormField, key_prefix: str):
    """Display field with all options"""
    unique_key = f"{key_prefix}_{field.unique_id}"
    
    # Determine style
    if field.is_parent:
        card_class = "parent-field"
        status = "📁 Parent"
    elif field.is_subfield:
        card_class = "field-subfield"
        status = f"↳ {field.parent_number}"
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
        
        # Show all options
        if field.options:
            st.caption("Available options:")
            for opt in field.options:
                context = field.option_contexts.get(opt, "")
                if context:
                    st.markdown(f'<span class="option-chip">{opt}</span> <small>({context})</small>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<span class="option-chip">{opt}</span>', unsafe_allow_html=True)
    
    with col2:
        if not field.is_parent:
            if field.field_type == "date":
                field.value = st.date_input("", key=f"{unique_key}_date", label_visibility="collapsed")
                field.value = str(field.value) if field.value else ""
            elif field.field_type == "textarea":
                field.value = st.text_area("", value=field.value, key=f"{unique_key}_area", height=80, label_visibility="collapsed")
            elif field.options:
                field.value = st.selectbox("", [""] + field.options, key=f"{unique_key}_sel", label_visibility="collapsed")
            else:
                field.value = st.text_input("", value=field.value, key=f"{unique_key}_val", label_visibility="collapsed")
        else:
            st.info("Enter in subfields")
    
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
                else:
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
    """Show mapping interface"""
    st.markdown("---")
    st.markdown("### Map Field to Database")
    
    col1, col2 = st.columns(2)
    
    with col1:
        db_options = list(DATABASE_SCHEMA.keys())
        db_labels = [DATABASE_SCHEMA[k]["label"] for k in db_options]
        
        selected_idx = st.selectbox(
            "Database Object",
            range(len(db_options)),
            format_func=lambda x: db_labels[x],
            key=f"{unique_key}_dbobj"
        )
        
        selected_obj = db_options[selected_idx] if selected_idx is not None else None
    
    with col2:
        if selected_obj:
            if selected_obj == "custom":
                path = st.text_input("Custom path", key=f"{unique_key}_path")
            else:
                paths = DATABASE_SCHEMA[selected_obj]["paths"]
                path = st.selectbox("Field Path", [""] + paths, key=f"{unique_key}_path")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Apply", key=f"{unique_key}_apply"):
            if selected_obj and path:
                field.is_mapped = True
                field.db_object = selected_obj
                field.db_path = path
                del st.session_state[f"mapping_{field.unique_id}"]
                st.rerun()
    with col2:
        if st.button("Cancel", key=f"{unique_key}_cancel"):
            del st.session_state[f"mapping_{field.unique_id}"]
            st.rerun()

# ===== MAIN APPLICATION =====

def main():
    st.markdown('<div class="main-header"><h1>📄 USCIS Form Reader - Final Version</h1><p>Complete extraction with proper field sequencing</p></div>', unsafe_allow_html=True)
    
    # Initialize
    if 'form' not in st.session_state:
        st.session_state.form = None
    if 'extractor' not in st.session_state:
        st.session_state.extractor = FormExtractor()
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 📊 Database Schema")
        
        for key, info in DATABASE_SCHEMA.items():
            with st.expander(info["label"]):
                if key == "custom":
                    st.info("Enter any custom path")
                else:
                    paths = info["paths"]
                    st.info(f"{len(paths)} fields available")
                    for path in paths[:8]:
                        st.code(path, language="")
                    if len(paths) > 8:
                        st.caption(f"... and {len(paths)-8} more fields")
        
        st.markdown("---")
        
        if st.button("🔄 Clear All", type="secondary", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
        
        if st.session_state.form:
            st.markdown("## 📈 Form Statistics")
            form = st.session_state.form
            
            total_parts = len(form.parts)
            total_fields = sum(len(p.fields) for p in form.parts.values())
            mapped = sum(1 for p in form.parts.values() for f in p.fields if f.is_mapped)
            quest = sum(1 for p in form.parts.values() for f in p.fields if f.in_questionnaire)
            
            st.metric("Total Parts", total_parts)
            st.metric("Total Fields", total_fields)
            st.metric("Mapped Fields", mapped)
            st.metric("Questionnaire", quest)
    
    # Main tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📤 Upload & Extract",
        "🔗 Map Fields",
        "📝 Questionnaire",
        "💾 Export Data"
    ])
    
    with tab1:
        st.markdown("### Upload USCIS Form PDF")
        st.info("Extracts all parts and fields with proper sequencing (1, 1.a, 1.b, 2, 2.a, etc.)")
        
        uploaded_file = st.file_uploader("Choose PDF file", type=['pdf'])
        
        if uploaded_file:
            col1, col2 = st.columns(2)
            with col1:
                extract_btn = st.button("🚀 Extract Complete Form", type="primary", use_container_width=True)
            with col2:
                if st.button("🔄 Reset", use_container_width=True):
                    st.session_state.form = None
                    st.rerun()
            
            if extract_btn:
                with st.spinner("Extracting form structure..."):
                    try:
                        # Extract PDF text
                        full_text, page_texts, total_pages = extract_pdf_text(uploaded_file)
                        
                        if full_text:
                            # Extract form with all parts and fields
                            form = st.session_state.extractor.extract_form(
                                full_text, page_texts, total_pages
                            )
                            st.session_state.form = form
                            
                            # Show success
                            st.success(f"✅ Successfully extracted: **{form.form_number}**")
                            
                            # Show extracted parts
                            st.markdown("### 📋 Extracted Parts:")
                            
                            for part_num in sorted(form.parts.keys()):
                                part = form.parts[part_num]
                                field_count = len(part.fields)
                                
                                # Count field types
                                regular = sum(1 for f in part.fields if not f.is_parent and not f.is_subfield)
                                parents = sum(1 for f in part.fields if f.is_parent)
                                subfields = sum(1 for f in part.fields if f.is_subfield)
                                
                                st.success(
                                    f"**Part {part_num}: {part.title}**\n"
                                    f"Total: {field_count} fields "
                                    f"(Regular: {regular}, Parents: {parents}, Subfields: {subfields})"
                                )
                            
                            # Overall statistics
                            st.markdown("### 📊 Overall Statistics:")
                            total_parts = len(form.parts)
                            total_fields = sum(len(p.fields) for p in form.parts.values())
                            
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric("Form Number", form.form_number)
                            with col2:
                                st.metric("Total Parts", total_parts)
                            with col3:
                                st.metric("Total Fields", total_fields)
                            with col4:
                                st.metric("Total Pages", total_pages)
                        else:
                            st.error("Could not extract text from PDF")
                    
                    except Exception as e:
                        st.error(f"Extraction error: {str(e)}")
                        st.info("Please try uploading a different PDF")
    
    with tab2:
        st.markdown("### Map Fields to Database")
        
        if st.session_state.form:
            form = st.session_state.form
            
            # Part selector
            part_options = [f"Part {num}: {part.title}" for num, part in sorted(form.parts.items())]
            if part_options:
                selected_part_idx = st.selectbox(
                    "Select Part to Map",
                    range(len(part_options)),
                    format_func=lambda x: part_options[x]
                )
                
                part_num = sorted(form.parts.keys())[selected_part_idx]
                part = form.parts[part_num]
                
                st.info(f"Mapping fields from **{part_options[selected_part_idx]}** ({len(part.fields)} fields)")
                
                # Display fields in proper sequence
                if part.fields:
                    # Sort fields by their sort order
                    sorted_fields = sorted(part.fields, key=lambda f: f.sort_order)
                    
                    # Track displayed subfields
                    displayed = set()
                    
                    for field in sorted_fields:
                        if field.item_number in displayed:
                            continue
                        
                        # Skip subfields (they'll be shown with parent)
                        if field.is_subfield:
                            continue
                        
                        # Display field
                        display_field(field, f"p{part_num}")
                        displayed.add(field.item_number)
                        
                        # If parent, display its subfields
                        if field.is_parent:
                            for subfield in sorted_fields:
                                if subfield.parent_number == field.item_number:
                                    display_field(subfield, f"p{part_num}")
                                    displayed.add(subfield.item_number)
                else:
                    st.warning("No fields found in this part")
            else:
                st.warning("No parts found in form")
        else:
            st.info("Please upload and extract a form first")
    
    with tab3:
        st.markdown("### Questionnaire Fields")
        st.info("Fields moved to questionnaire with all available options")
        
        if st.session_state.form:
            has_questions = False
            
            for part_num in sorted(st.session_state.form.parts.keys()):
                part = st.session_state.form.parts[part_num]
                quest_fields = [f for f in part.fields if f.in_questionnaire and not f.is_parent]
                
                if quest_fields:
                    has_questions = True
                    st.markdown(f"#### Part {part.number}: {part.title}")
                    
                    # Sort questionnaire fields
                    quest_fields.sort(key=lambda f: f.sort_order)
                    
                    for field in quest_fields:
                        st.markdown(f'<span class="field-number-badge">{field.item_number}</span>**{field.label}**', unsafe_allow_html=True)
                        
                        if field.is_subfield:
                            st.caption(f"Subfield of {field.parent_number}")
                        
                        # Show ALL options with context
                        if field.options:
                            st.markdown("**Available Options:**")
                            for opt in field.options:
                                context = field.option_contexts.get(opt, "")
                                if context:
                                    st.write(f"• **{opt}** - _{context}_")
                                else:
                                    st.write(f"• **{opt}**")
                            
                            # Select answer
                            field.value = st.selectbox(
                                "Select your answer:",
                                [""] + field.options,
                                key=f"q_{field.unique_id}"
                            )
                        else:
                            field.value = st.text_area(
                                "Your answer:",
                                value=field.value,
                                key=f"q_{field.unique_id}",
                                height=100
                            )
                        
                        if st.button("Remove from questionnaire", key=f"qr_{field.unique_id}"):
                            field.in_questionnaire = False
                            st.rerun()
                        
                        st.markdown("---")
            
            if not has_questions:
                st.info("No questionnaire fields yet. Use the 'Quest' button in Map Fields tab to add fields.")
        else:
            st.info("Please upload and extract a form first")
    
    with tab4:
        st.markdown("### Export Form Data")
        
        if st.session_state.form:
            form = st.session_state.form
            
            # Build complete export
            export_data = {
                "form_info": {
                    "form_number": form.form_number,
                    "form_title": form.form_title,
                    "edition_date": form.edition_date,
                    "total_pages": form.total_pages,
                    "total_parts": len(form.parts)
                },
                "parts": {},
                "mapped_fields": [],
                "questionnaire_fields": []
            }
            
            # Process each part
            for part_num in sorted(form.parts.keys()):
                part = form.parts[part_num]
                
                part_data = {
                    "title": part.title,
                    "field_count": len(part.fields),
                    "fields": []
                }
                
                # Sort fields
                sorted_fields = sorted(part.fields, key=lambda f: f.sort_order)
                
                for field in sorted_fields:
                    if not field.is_parent:
                        field_data = {
                            "part": part_num,
                            "number": field.item_number,
                            "label": field.label,
                            "type": field.field_type,
                            "value": field.value,
                            "is_subfield": field.is_subfield,
                            "parent": field.parent_number if field.is_subfield else None
                        }
                        
                        # Add options if available
                        if field.options:
                            field_data["options"] = field.options
                            if field.option_contexts:
                                field_data["option_contexts"] = field.option_contexts
                        
                        # Track mapped and questionnaire fields
                        if field.is_mapped:
                            field_data["mapping"] = {
                                "object": field.db_object,
                                "path": field.db_path
                            }
                            export_data["mapped_fields"].append(field_data)
                        
                        if field.in_questionnaire:
                            export_data["questionnaire_fields"].append(field_data)
                        
                        part_data["fields"].append(field_data)
                
                export_data["parts"][f"Part_{part_num}"] = part_data
            
            # Summary statistics
            st.markdown("### 📊 Export Summary")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Parts", len(export_data["parts"]))
            with col2:
                total_fields = sum(p["field_count"] for p in export_data["parts"].values())
                st.metric("Total Fields", total_fields)
            with col3:
                st.metric("Mapped Fields", len(export_data["mapped_fields"]))
            with col4:
                st.metric("Questionnaire", len(export_data["questionnaire_fields"]))
            
            # Export buttons
            st.markdown("### 💾 Download Options")
            
            json_str = json.dumps(export_data, indent=2)
            
            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    "📥 Download Complete JSON",
                    json_str,
                    f"{form.form_number}_complete.json",
                    "application/json",
                    use_container_width=True,
                    type="primary"
                )
            
            with col2:
                # Create TypeScript export for mapped fields
                if export_data["mapped_fields"]:
                    ts_code = generate_typescript(export_data["mapped_fields"])
                    st.download_button(
                        "📥 Download TypeScript",
                        ts_code,
                        f"{form.form_number}_interface.ts",
                        "text/plain",
                        use_container_width=True
                    )
                else:
                    st.info("Map fields first to export TypeScript")
            
            # Preview
            with st.expander("📋 Preview Export Data"):
                st.json(export_data)
        else:
            st.info("Please upload and extract a form first")

def generate_typescript(mapped_fields: List[Dict]) -> str:
    """Generate TypeScript interfaces from mapped fields"""
    ts = "// Generated TypeScript Interface from USCIS Form\n\n"
    
    # Group by object
    by_object = {}
    for field in mapped_fields:
        obj = field["mapping"]["object"]
        if obj not in by_object:
            by_object[obj] = []
        by_object[obj].append(field)
    
    # Generate interfaces
    for obj_name, fields in by_object.items():
        ts += f"interface {obj_name.capitalize()}Data {{\n"
        
        for field in fields:
            path = field["mapping"]["path"]
            field_type = "string"
            
            if field["type"] == "date":
                field_type = "Date | string"
            elif field["type"] == "number":
                field_type = "number"
            elif field.get("options"):
                field_type = " | ".join([f'"{opt}"' for opt in field["options"]])
            
            ts += f"  {path}: {field_type}; // Field {field['number']}\n"
        
        ts += "}\n\n"
    
    return ts

if __name__ == "__main__":
    main()
