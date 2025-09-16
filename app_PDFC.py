#!/usr/bin/env python3
"""
UNIVERSAL USCIS FORM READER - ENHANCED PART DETECTION
====================================================
Fixed to properly read all 8 parts using enhanced agentic approach
"""

import streamlit as st
import json
import re
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field as dataclass_field, asdict
import uuid

# Page config
st.set_page_config(
    page_title="Universal USCIS Reader - Enhanced",
    page_icon="🤖",
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
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    st.error("Anthropic not installed. Please run: pip install anthropic")

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
    .agent-status {
        background: #e8f5e8;
        border: 1px solid #4caf50;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    .field-card {
        border: 1px solid #e0e0e0;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 8px;
        background: white;
    }
    .field-parent {
        background: #f3e5f5;
        border-left: 4px solid #9c27b0;
        font-weight: bold;
    }
    .field-subfield {
        background: #e8f4fd;
        border-left: 4px solid #2196f3;
        margin-left: 20px;
    }
    .field-question {
        background: #fff3e0;
        border-left: 4px solid #ff9800;
    }
    .field-choice {
        background: #f1f8e9;
        border-left: 4px solid #8bc34a;
        margin-left: 40px;
    }
    .field-mapped {
        border-right: 4px solid #4caf50;
    }
    .field-questionnaire {
        border-right: 4px solid #673ab7;
    }
    .ai-analysis {
        background: #e3f2fd;
        border: 1px solid #2196f3;
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
        font-size: 0.9em;
    }
    .export-section {
        background: #f5f5f5;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    .part-status {
        background: #f8f9fa;
        border: 1px solid #dee2e6;
        padding: 0.5rem;
        margin: 0.25rem 0;
        border-radius: 4px;
        font-size: 0.9em;
    }
</style>
""", unsafe_allow_html=True)

# ===== DATA STRUCTURES =====

@dataclass
class FieldChoice:
    """Individual choice for a question field"""
    letter: str
    label: str
    value: str = ""
    selected: bool = False

@dataclass
class USCISField:
    """Universal field structure for any USCIS form"""
    number: str
    label: str
    field_type: str = "text"
    part_number: int = 1
    
    # Hierarchy
    is_parent: bool = False
    is_subfield: bool = False
    is_choice: bool = False
    parent_number: str = ""
    subfield_letter: str = ""
    
    # Subfields and choices
    subfields: List['USCISField'] = dataclass_field(default_factory=list)
    choices: List[FieldChoice] = dataclass_field(default_factory=list)
    
    # AI Analysis
    ai_reasoning: str = ""
    confidence: float = 1.0
    field_pattern: str = ""
    
    # User Input
    value: str = ""
    
    # Mapping
    is_mapped: bool = False
    db_object: str = ""
    db_field: str = ""
    
    # Questionnaire
    in_questionnaire: bool = False
    
    # System
    unique_id: str = dataclass_field(default_factory=lambda: str(uuid.uuid4())[:8])
    extraction_method: str = "ai_agent"

@dataclass
class FormPart:
    """Universal form part structure"""
    number: int
    title: str
    fields: List[USCISField] = dataclass_field(default_factory=list)
    ai_analysis: str = ""
    field_patterns: Dict[str, int] = dataclass_field(default_factory=dict)
    processed: bool = False
    extraction_confidence: float = 1.0
    text_length: int = 0

@dataclass
class USCISForm:
    """Universal USCIS form container"""
    form_number: str = "Unknown"
    title: str = "USCIS Form"
    edition_date: str = ""
    total_pages: int = 0
    form_category: str = ""
    parts: Dict[int, FormPart] = dataclass_field(default_factory=dict)
    ai_summary: str = ""
    processing_time: float = 0.0
    extraction_summary: str = ""

# ===== DATABASE SCHEMAS =====

DATABASE_SCHEMA = {
    "beneficiary": {
        "label": "👤 Beneficiary/Applicant",
        "paths": [
            "beneficiaryLastName",
            "beneficiaryFirstName", 
            "beneficiaryMiddleName",
            "beneficiaryOtherNames",
            "beneficiaryAlienNumber",
            "beneficiaryUSCISNumber",
            "beneficiarySSN",
            "beneficiaryDateOfBirth",
            "beneficiaryGender",
            "beneficiaryCountryOfBirth",
            "beneficiaryCityOfBirth",
            "beneficiaryCurrentCountryOfCitizenship",
            "beneficiaryNationality",
            "beneficiaryStreetNumberAndName",
            "beneficiaryAptSteFlr",
            "beneficiaryAptSteFlrNumber",
            "beneficiaryCityOrTown",
            "beneficiaryState",
            "beneficiaryZipCode",
            "beneficiaryProvince",
            "beneficiaryPostalCode",
            "beneficiaryCountry",
            "beneficiaryDaytimePhone",
            "beneficiaryMobilePhone",
            "beneficiaryEmail",
            "beneficiaryFaxNumber"
        ]
    },
    "petitioner": {
        "label": "🏢 Petitioner/Employer",
        "paths": [
            "petitionerLastName",
            "petitionerFirstName",
            "petitionerMiddleName",
            "petitionerCompanyName",
            "petitionerOrganizationName",
            "petitionerBusinessType",
            "petitionerYearEstablished",
            "petitionerStreetNumberAndName",
            "petitionerAptSteFlr",
            "petitionerAptSteFlrNumber",
            "petitionerCityOrTown",
            "petitionerState",
            "petitionerZipCode",
            "petitionerProvince",
            "petitionerPostalCode",
            "petitionerCountry",
            "petitionerDaytimePhone",
            "petitionerMobilePhone",
            "petitionerEmail",
            "petitionerFaxNumber",
            "petitionerFEIN",
            "petitionerSSN",
            "petitionerEmployeeCount",
            "petitionerGrossIncome",
            "petitionerNetIncome"
        ]
    },
    "immigration": {
        "label": "📋 Immigration Status & Documents",
        "paths": [
            "immigrationCurrentStatus",
            "immigrationStatusExpiry",
            "immigrationClassOfAdmission",
            "immigrationLastEntryDate",
            "immigrationI94Number",
            "immigrationArrivalDepartureRecord",
            "immigrationAdmissionNumber",
            "immigrationPassportNumber",
            "immigrationPassportExpiry",
            "immigrationPassportCountry",
            "immigrationTravelDocumentNumber",
            "immigrationTravelDocumentExpiry",
            "immigrationSevisId",
            "immigrationEadNumber",
            "immigrationReceiptNumber",
            "immigrationPriorityDate",
            "immigrationRequestedStatus",
            "immigrationRequestedUntil",
            "immigrationRequestedAction",
            "immigrationPreviousStatuses",
            "immigrationExtensionHistory",
            "immigrationStatusViolations"
        ]
    },
    "employment": {
        "label": "💼 Employment Information",
        "paths": [
            "employmentJobTitle",
            "employmentJobDescription",
            "employmentSocCode",
            "employmentNaicsCode",
            "employmentSalary",
            "employmentSalaryFrequency",
            "employmentWorkLocation",
            "employmentStartDate",
            "employmentEndDate",
            "employmentFullTime",
            "employmentPartTime",
            "employmentTemporary",
            "employmentPermanent",
            "employmentSupervisionLevel",
            "employmentEmployeesSupervised",
            "employmentEducationRequired",
            "employmentExperienceRequired",
            "employmentSpecializationKnowledge",
            "employmentLanguageRequirements",
            "employmentAuthorized",
            "employmentEmployerName",
            "employmentWorkAddress"
        ]
    },
    "family": {
        "label": "👨‍👩‍👧‍👦 Family Information",
        "paths": [
            "familyRelationshipType",
            "familyMaritalStatus",
            "familySpouseLastName",
            "familySpouseFirstName",
            "familySpouseMiddleName",
            "familyMarriageDate",
            "familyMarriagePlace",
            "familyDivorceDate",
            "familyChildrenCount",
            "familyChildLastName",
            "familyChildFirstName",
            "familyChildMiddleName",
            "familyChildDateOfBirth",
            "familyChildCountryOfBirth",
            "familyChildStatus",
            "familyParentLastName",
            "familyParentFirstName",
            "familyParentStatus",
            "familySiblingLastName",
            "familySiblingFirstName",
            "familySiblingStatus"
        ]
    },
    "background": {
        "label": "🔍 Background & Security",
        "paths": [
            "backgroundCriminalHistory",
            "backgroundArrestHistory",
            "backgroundConvictionHistory",
            "backgroundMilitaryService",
            "backgroundGovernmentService",
            "backgroundOrganizationMembership",
            "backgroundWeaponsTraining",
            "backgroundSecurityClearance",
            "backgroundDeportationHistory",
            "backgroundImmigrationViolations",
            "backgroundPublicBenefits",
            "backgroundTaxHistory",
            "backgroundArrestDate",
            "backgroundArrestLocation",
            "backgroundConvictionDate",
            "backgroundConvictionLocation",
            "backgroundMilitaryBranch",
            "backgroundMilitaryRank",
            "backgroundMilitaryDates"
        ]
    },
    "attorney": {
        "label": "⚖️ Attorney/Representative",
        "paths": [
            "attorneyLastName",
            "attorneyFirstName",
            "attorneyMiddleName",
            "attorneyOrganizationName",
            "attorneyBarNumber",
            "attorneyUSCISNumber",
            "attorneyStreetNumberAndName",
            "attorneyAptSteFlr",
            "attorneyAptSteFlrNumber",
            "attorneyCityOrTown",
            "attorneyState",
            "attorneyZipCode",
            "attorneyCountry",
            "attorneyDaytimePhone",
            "attorneyMobilePhone",
            "attorneyEmail",
            "attorneyFaxNumber"
        ]
    },
    "interpreter": {
        "label": "🗣️ Interpreter",
        "paths": [
            "interpreterLastName",
            "interpreterFirstName",
            "interpreterMiddleName",
            "interpreterOrganizationName",
            "interpreterLanguage",
            "interpreterStreetNumberAndName",
            "interpreterAptSteFlr",
            "interpreterAptSteFlrNumber",
            "interpreterCityOrTown",
            "interpreterState",
            "interpreterZipCode",
            "interpreterCountry",
            "interpreterDaytimePhone",
            "interpreterMobilePhone",
            "interpreterEmail",
            "interpreterFaxNumber"
        ]
    },
    "preparer": {
        "label": "📝 Preparer",
        "paths": [
            "preparerLastName",
            "preparerFirstName",
            "preparerMiddleName",
            "preparerOrganizationName",
            "preparerStreetNumberAndName",
            "preparerAptSteFlr",
            "preparerAptSteFlrNumber",
            "preparerCityOrTown",
            "preparerState",
            "preparerZipCode",
            "preparerCountry",
            "preparerDaytimePhone",
            "preparerMobilePhone",
            "preparerEmail",
            "preparerFaxNumber"
        ]
    },
    "custom": {
        "label": "✏️ Custom Fields",
        "paths": []
    }
}

# ===== ENHANCED AI AGENT =====

class UniversalUSCISAgent:
    """Enhanced Claude Sonnet 4 agent for any USCIS form analysis"""
    
    def __init__(self):
        self.client = None
        self.setup_client()
    
    def setup_client(self):
        """Setup Anthropic client"""
        if not ANTHROPIC_AVAILABLE:
            return False
        
        try:
            api_key = st.secrets.get("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                self.client = anthropic.Anthropic(api_key=api_key)
                return True
        except Exception as e:
            st.error(f"Claude API setup failed: {e}")
        return False
    
    def identify_form(self, text: str) -> Dict[str, str]:
        """Identify any USCIS form type and metadata"""
        if not self.client:
            return {"form_number": "Unknown", "title": "USCIS Form", "edition_date": "", "form_category": ""}
        
        prompt = f"""Analyze this USCIS form text and extract metadata:

1. Form number (I-129, I-539, I-485, I-130, etc.)
2. Full form title
3. Edition date
4. Form category (petition, application, notice, etc.)

Return JSON:
{{
    "form_number": "I-XXX",
    "title": "Complete Form Title",
    "edition_date": "MM/DD/YY or date found",
    "form_category": "application/petition/notice/request"
}}

Text to analyze:
{text[:2000]}"""

        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = response.content[0].text.strip()
            if "{" in content:
                json_start = content.find("{")
                json_end = content.rfind("}") + 1
                return json.loads(content[json_start:json_end])
                
        except Exception as e:
            st.warning(f"Form identification error: {e}")
        
        return {"form_number": "Unknown", "title": "USCIS Form", "edition_date": "", "form_category": ""}
    
    def extract_parts(self, text: str) -> List[Dict]:
        """Root cause fix: Accurate part boundary detection for clean text extraction"""
        if not self.client:
            return [{"number": 1, "title": "Main Section"}]
        
        st.info("🔍 Starting precise part boundary detection...")
        
        # STEP 1: Find ALL part positions with exact locations
        part_positions = []
        
        # Enhanced regex patterns that capture exact positions
        part_patterns = [
            (r'(?:^|\n)\s*(Part\s+(\d+)\.?\s*([A-Z][^\n]{0,100}))', re.IGNORECASE | re.MULTILINE),
            (r'(?:^|\n)\s*(PART\s+(\d+)\.?\s*([A-Z][^\n]{0,100}))', re.MULTILINE),
        ]
        
        with st.spinner("Finding exact part positions..."):
            for pattern, flags in part_patterns:
                for match in re.finditer(pattern, text, flags):
                    try:
                        part_num = int(match.group(2))
                        title = match.group(3).strip() if len(match.groups()) > 2 else f"Part {part_num}"
                        start_pos = match.start()
                        
                        # Store exact position and context
                        part_positions.append({
                            "number": part_num,
                            "title": title,
                            "start_pos": start_pos,
                            "full_match": match.group(1),
                            "context": text[max(0, start_pos-50):start_pos+200]
                        })
                    except (ValueError, IndexError):
                        continue
        
        # Remove duplicates and sort by position
        seen_positions = set()
        unique_parts = []
        for part in part_positions:
            pos_key = (part["number"], part["start_pos"] // 100)  # Group nearby positions
            if pos_key not in seen_positions:
                seen_positions.add(pos_key)
                unique_parts.append(part)
        
        unique_parts.sort(key=lambda x: x["start_pos"])
        
        # STEP 2: AI validation of found parts
        if self.client and unique_parts:
            with st.spinner("AI validation of part boundaries..."):
                found_parts_summary = "\n".join([
                    f"Part {p['number']}: {p['title']} (pos: {p['start_pos']})" 
                    for p in unique_parts
                ])
                
                validation_prompt = f"""Validate these USCIS form parts found by regex:

{found_parts_summary}

Document samples:
Beginning: {text[:2000]}
End: {text[-2000:]}

Are these parts reasonable for a USCIS form? Are any major parts missing?
Return JSON with validation and any missing parts:
{{
    "valid_parts": [list of valid part numbers],
    "missing_parts": [
        {{"number": X, "title": "Expected title", "likely_location": "beginning/middle/end"}}
    ],
    "form_type": "detected form type"
}}"""

                try:
                    response = self.client.messages.create(
                        model="claude-3-5-sonnet-20241022",
                        max_tokens=800,
                        messages=[{"role": "user", "content": validation_prompt}]
                    )
                    
                    content = response.content[0].text.strip()
                    if "{" in content:
                        json_start = content.find("{")
                        json_end = content.rfind("}") + 1
                        validation = json.loads(content[json_start:json_end])
                        
                        # Add missing parts if identified
                        if validation.get("missing_parts"):
                            for missing in validation["missing_parts"]:
                                # Try to find these parts with more flexible patterns
                                missing_num = missing["number"]
                                flexible_pattern = rf"Part\s*{missing_num}[^\d]"
                                match = re.search(flexible_pattern, text, re.IGNORECASE)
                                if match:
                                    unique_parts.append({
                                        "number": missing_num,
                                        "title": missing["title"],
                                        "start_pos": match.start(),
                                        "full_match": match.group(0),
                                        "context": text[match.start():match.start()+200]
                                    })
                
                except Exception as e:
                    st.warning(f"AI validation error: {e}")
        
        # STEP 3: Final cleanup and boundary calculation
        unique_parts.sort(key=lambda x: (x["number"], x["start_pos"]))
        
        # Remove exact duplicates by part number (keep first occurrence)
        final_parts = []
        seen_numbers = set()
        for part in unique_parts:
            if part["number"] not in seen_numbers:
                seen_numbers.add(part["number"])
                final_parts.append({
                    "number": part["number"],
                    "title": part["title"],
                    "start_pos": part["start_pos"],
                    "end_pos": None  # Will be calculated in text extraction
                })
        
        final_parts.sort(key=lambda x: x["number"])
        
        # Calculate end positions for clean boundaries
        for i, part in enumerate(final_parts):
            if i < len(final_parts) - 1:
                # End position is start of next part
                next_part_start = None
                for next_part in final_parts[i+1:]:
                    if next_part["start_pos"] > part["start_pos"]:
                        next_part_start = next_part["start_pos"]
                        break
                part["end_pos"] = next_part_start
            else:
                # Last part goes to end of document
                part["end_pos"] = len(text)
        
        st.success(f"✅ Found {len(final_parts)} parts with precise boundaries: {[p['number'] for p in final_parts]}")
        
        # Store positions for use in text extraction
        self._part_positions = {p["number"]: (p["start_pos"], p["end_pos"]) for p in final_parts}
        
        return final_parts if final_parts else [{"number": 1, "title": "Main Section"}]

    def analyze_part_fields(self, part_text: str, part_number: int, part_title: str) -> List[USCISField]:
        """Universal field analysis for any USCIS form part"""
        if not self.client:
            return self._fallback_extraction(part_text, part_number)
        
        prompt = f"""Analyze this USCIS form part and extract ALL fields with intelligent structuring.

UNIVERSAL FIELD ANALYSIS RULES - APPLY TO ALL USCIS FORMS:

1. **NAME FIELDS** → ALWAYS create subfields:
   - "Full Legal Name" / "Your Name" / "Beneficiary Name" / "Petitioner Name" → a=Family/Last Name, b=Given/First Name, c=Middle Name
   - "Other Names Used" → a=Family Name, b=Given Name, c=Middle Name

2. **ADDRESS FIELDS** → ALWAYS create subfields:
   - "Mailing Address" / "Physical Address" / "Home Address" / "Current Address" → a=Street Number and Name, b=Apt/Ste/Flr Number, c=City or Town, d=State, e=ZIP Code
   - "Foreign Address" → add f=Province, g=Postal Code, h=Country
   - "Address History" → Each address gets full subfields

3. **CONTACT FIELDS** → Create subfields for multiple components:
   - "Contact Information" → a=Daytime Phone, b=Mobile Phone, c=Email, d=Fax
   - If single contact type mentioned, keep as single field

4. **DATE FIELDS** → Single field (no subfields):
   - "Date of Birth", "Arrival Date", "Expiration Date", "Marriage Date" → Single date field

5. **YES/NO QUESTIONS** → ALWAYS create choices:
   - Any question ending with "?" that expects Yes/No → a=Yes, b=No
   - "Are you...", "Have you...", "Do you...", "Is your..." → a=Yes, b=No

6. **MULTIPLE CHOICE** → Create choices for each visible option:
   - Checkbox lists → a=First Option, b=Second Option, c=Third Option...
   - Radio button groups → a=Choice1, b=Choice2, c=Choice3...

7. **SINGLE VALUE FIELDS** → No subfields:
   - SSN, Alien Number, USCIS Number, Email, Phone (when standalone) → Single text field

8. **EMPLOYMENT/EDUCATION FIELDS** → Create relevant subfields:
   - "Employment Information" → a=Job Title, b=Company Name, c=Start Date, d=End Date, e=Salary
   - "Education" → a=School Name, b=Degree, c=Field of Study, d=Graduation Date

9. **DOCUMENT FIELDS** → Create subfields for document details:
   - "Passport Information" → a=Passport Number, b=Country of Issuance, c=Expiration Date
   - "Travel Document" → a=Document Number, b=Document Type, c=Expiration Date

10. **SIGNATURE/CERTIFICATION SECTIONS** → Create subfields:
    - "Applicant Certification" → a=Signature, b=Date of Signature
    - "Interpreter Information" → a=Name, b=Language, c=Signature, d=Date

CRITICAL: Find EVERY numbered item (1., 2., 3., etc.) and determine if it needs subfields or choices.

MAINTAIN EXACT NUMBERING from the form. If form shows "5." then use "5" as the number.

Return comprehensive JSON array:
[{{
    "number": "1",
    "label": "Your Full Legal Name",
    "type": "parent",
    "pattern": "name_field",
    "subfields": [
        {{"letter": "a", "label": "Family Name (Last Name)", "type": "text"}},
        {{"letter": "b", "label": "Given Name (First Name)", "type": "text"}},
        {{"letter": "c", "label": "Middle Name (if applicable)", "type": "text"}}
    ],
    "reasoning": "Name field requires family, given, and middle components for proper identification"
}},
{{
    "number": "4",
    "label": "Your U.S. Mailing Address",
    "type": "parent",
    "pattern": "address_field",
    "subfields": [
        {{"letter": "a", "label": "Street Number and Name", "type": "text"}},
        {{"letter": "b", "label": "Apt/Ste/Flr Number", "type": "text"}},
        {{"letter": "c", "label": "City or Town", "type": "text"}},
        {{"letter": "d", "label": "State", "type": "text"}},
        {{"letter": "e", "label": "ZIP Code", "type": "text"}}
    ],
    "reasoning": "Address field requires multiple components for complete mailing information"
}},
{{
    "number": "5",
    "label": "Is your mailing address the same as your physical address?",
    "type": "question",
    "pattern": "yes_no_question", 
    "choices": [
        {{"letter": "a", "label": "Yes"}},
        {{"letter": "b", "label": "No"}}
    ],
    "reasoning": "Yes/No question requires radio button choices for user selection"
}},
{{
    "number": "7",
    "label": "Date of Birth",
    "type": "date",
    "pattern": "single_date",
    "reasoning": "Single date field, no subfields needed as it's one piece of information"
}}]

Part {part_number}: {part_title}
Text to analyze:
{part_text[:12000]}"""

        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=8000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = response.content[0].text.strip()
            if "[" in content:
                json_start = content.find("[")
                json_end = content.rfind("]") + 1
                fields_data = json.loads(content[json_start:json_end])
                
                return self._build_universal_fields(fields_data, part_number)
                
        except Exception as e:
            st.warning(f"AI field analysis error for Part {part_number}: {e}")
            st.info("Using fallback extraction method...")
        
        return self._fallback_extraction(part_text, part_number)
    
    def _build_universal_fields(self, fields_data: List[Dict], part_number: int) -> List[USCISField]:
        """Build universal field objects from AI analysis"""
        fields = []
        
        for field_data in fields_data:
            # Main field
            field = USCISField(
                number=field_data.get("number", ""),
                label=field_data.get("label", ""),
                field_type=field_data.get("type", "text"),
                part_number=part_number,
                ai_reasoning=field_data.get("reasoning", ""),
                field_pattern=field_data.get("pattern", ""),
                is_parent=(field_data.get("type") == "parent")
            )
            
            # Add subfields for structured data
            if "subfields" in field_data:
                field.is_parent = True
                field.field_type = "parent"
                
                for sub_data in field_data["subfields"]:
                    subfield = USCISField(
                        number=f"{field.number}.{sub_data['letter']}",
                        label=sub_data["label"],
                        field_type=sub_data.get("type", "text"),
                        part_number=part_number,
                        is_subfield=True,
                        parent_number=field.number,
                        subfield_letter=sub_data["letter"],
                        field_pattern=field.field_pattern
                    )
                    field.subfields.append(subfield)
                    fields.append(subfield)
            
            # Add choices for questions
            if "choices" in field_data:
                field.field_type = "question"
                
                for choice_data in field_data["choices"]:
                    choice_field = USCISField(
                        number=f"{field.number}.{choice_data['letter']}",
                        label=choice_data["label"],
                        field_type="choice",
                        part_number=part_number,
                        is_choice=True,
                        parent_number=field.number,
                        subfield_letter=choice_data["letter"],
                        field_pattern=field.field_pattern
                    )
                    field.choices.append(FieldChoice(
                        letter=choice_data["letter"],
                        label=choice_data["label"]
                    ))
                    fields.append(choice_field)
            
            fields.append(field)
        
        # Sort fields properly
        fields.sort(key=lambda f: self._get_sort_key(f.number))
        return fields
    
    def _fallback_extraction(self, text: str, part_number: int) -> List[USCISField]:
        """Enhanced fallback pattern-based extraction for any USCIS form"""
        fields = []
        seen_numbers = set()
        
        # Define patterns with proper regex strings
        pattern_list = [
            (r'(\d+)\.\s+([^\n]{3,400})', 'main'),
            (r'(\d+)\.([a-z])\.\s+([^\n]{3,300})', 'subfield'),
            (r'(\d+)([a-z])\.\s+([^\n]{3,300})', 'subfield_compact'),
            (r'Item\s+Number\s+(\d+)[.\s]*([^\n]{3,400})', 'item'),
            (r'Question\s+(\d+)[.\s]*([^\n]{3,400})', 'question'),
            (r'^([A-Z])\.\s+([^\n]{3,300})', 'letter'),
            (r'^\s*([a-z])\.\s+([^\n]{3,200})', 'orphan_sub'),
        ]
        
        for pattern_str, pattern_type in pattern_list:
            flags = re.IGNORECASE | re.MULTILINE
            matches = re.finditer(pattern_str, text[:20000], flags)
            
            for match in matches:
                try:
                    if pattern_type == 'subfield':
                        parent_num = match.group(1)
                        letter = match.group(2)
                        label = match.group(3).strip()
                        number = f"{parent_num}.{letter}"
                        is_subfield = True
                        parent_number = parent_num
                    elif pattern_type == 'subfield_compact':
                        parent_num = match.group(1)
                        letter = match.group(2)
                        label = match.group(3).strip()
                        number = f"{parent_num}.{letter}"
                        is_subfield = True
                        parent_number = parent_num
                    elif pattern_type == 'orphan_sub':
                        letter = match.group(1)
                        label = match.group(2).strip()
                        text_before = text[:match.start()]
                        parent_match = re.search(r'(\d+)\.\s+[^\n]+', text_before[::-1])
                        if parent_match:
                            parent_num = parent_match.group(1)[::-1]
                            number = f"{parent_num}.{letter.lower()}"
                            is_subfield = True
                            parent_number = parent_num
                        else:
                            continue
                    else:
                        number = match.group(1)
                        label = match.group(2).strip() if len(match.groups()) > 1 else f"Field {number}"
                        is_subfield = False
                        parent_number = ""
                    
                    if number in seen_numbers:
                        continue
                    seen_numbers.add(number)
                    
                    # Clean the label
                    label = re.sub(r'\s+', ' ', label)
                    label = label.strip()
                    label = re.sub(r'^[.\-–\s]+', '', label)
                    label = re.sub(r'[.\s]+$', '', label)
                    
                    if len(label) < 3:
                        continue
                    
                    field_type = self._detect_field_type(label)
                    should_be_parent = self._should_be_parent_field(label, text, match.start())
                    
                    field = USCISField(
                        number=number,
                        label=label,
                        field_type="parent" if should_be_parent else field_type,
                        part_number=part_number,
                        is_subfield=is_subfield,
                        is_parent=should_be_parent,
                        parent_number=parent_number,
                        subfield_letter=letter if is_subfield else "",
                        extraction_method="fallback_pattern",
                        field_pattern=pattern_type
                    )
                    fields.append(field)
                    
                except Exception as e:
                    continue
        
        self._create_missing_parents(fields, part_number)
        self._apply_basic_subfield_rules(fields, part_number)
        
        return fields
    
    def _should_be_parent_field(self, label: str, text: str, position: int) -> bool:
        """Determine if field should be a parent based on content analysis"""
        label_lower = label.lower()
        
        name_indicators = ["full name", "legal name", "your name", "beneficiary name", "petitioner name"]
        if any(indicator in label_lower for indicator in name_indicators):
            return True
        
        address_indicators = ["address", "mailing address", "physical address", "home address", "current address"]
        if any(indicator in label_lower for indicator in address_indicators):
            return True
        
        contact_indicators = ["contact information", "phone numbers"]
        if any(indicator in label_lower for indicator in contact_indicators):
            return True
        
        text_ahead = text[position:position + 1000]
        subfield_pattern = r'[a-z]\.\s+[A-Z]'
        if re.search(subfield_pattern, text_ahead):
            return True
        
        return False
    
    def _create_missing_parents(self, fields: List[USCISField], part_number: int):
        """Create parent fields for orphan subfields"""
        parent_numbers = set()
        existing_numbers = set()
        
        for field in fields:
            existing_numbers.add(field.number)
            if field.is_subfield and field.parent_number:
                parent_numbers.add(field.parent_number)
        
        for parent_num in parent_numbers:
            if parent_num not in existing_numbers:
                parent_field = USCISField(
                    number=parent_num,
                    label=f"Field {parent_num}",
                    field_type="parent",
                    part_number=part_number,
                    is_parent=True,
                    extraction_method="inferred_parent"
                )
                fields.append(parent_field)
    
    def _apply_basic_subfield_rules(self, fields: List[USCISField], part_number: int):
        """Apply basic subfield creation rules to parent fields"""
        new_fields = []
        
        for field in fields:
            if field.is_parent:
                label_lower = field.label.lower()
                
                if any(indicator in label_lower for indicator in ["name", "full name", "legal name"]):
                    subfields_to_add = [
                        ("a", "Family Name (Last Name)", "text"),
                        ("b", "Given Name (First Name)", "text"),
                        ("c", "Middle Name (if applicable)", "text")
                    ]
                    for letter, sub_label, sub_type in subfields_to_add:
                        sub_number = f"{field.number}.{letter}"
                        if not any(f.number == sub_number for f in fields):
                            subfield = USCISField(
                                number=sub_number,
                                label=sub_label,
                                field_type=sub_type,
                                part_number=part_number,
                                is_subfield=True,
                                parent_number=field.number,
                                subfield_letter=letter,
                                extraction_method="basic_rule_name"
                            )
                            new_fields.append(subfield)
                
                elif any(indicator in label_lower for indicator in ["address", "mailing", "physical"]):
                    subfields_to_add = [
                        ("a", "Street Number and Name", "text"),
                        ("b", "Apt/Ste/Flr Number", "text"),
                        ("c", "City or Town", "text"),
                        ("d", "State", "text"),
                        ("e", "ZIP Code", "text")
                    ]
                    for letter, sub_label, sub_type in subfields_to_add:
                        sub_number = f"{field.number}.{letter}"
                        if not any(f.number == sub_number for f in fields):
                            subfield = USCISField(
                                number=sub_number,
                                label=sub_label,
                                field_type=sub_type,
                                part_number=part_number,
                                is_subfield=True,
                                parent_number=field.number,
                                subfield_letter=letter,
                                extraction_method="basic_rule_address"
                            )
                            new_fields.append(subfield)
        
        fields.extend(new_fields)
    
    def _detect_field_type(self, label: str) -> str:
        """Universal field type detection"""
        label_lower = label.lower()
        
        if any(word in label_lower for word in ["date", "birth", "expir", "arrival", "departure"]):
            return "date"
        elif "email" in label_lower:
            return "email"
        elif any(word in label_lower for word in ["phone", "telephone", "fax"]):
            return "phone"
        elif any(phrase in label_lower for phrase in ["ssn", "social security"]):
            return "ssn"
        elif any(phrase in label_lower for phrase in ["alien number", "a-number", "a number"]):
            return "alien_number"
        elif any(phrase in label_lower for phrase in ["uscis", "receipt number"]):
            return "text"
        elif any(word in label_lower for word in ["yes", "no", "check", "select", "mark"]):
            return "checkbox"
        elif "?" in label:
            return "question"
        
        return "text"
    
    def _get_sort_key(self, number: str) -> Tuple:
        """Universal sort key for any field numbering"""
        try:
            parts = number.replace('-', '.').split('.')
            main = int(parts[0]) if parts[0].isdigit() else 999
            
            sub = 0
            if len(parts) > 1 and parts[1]:
                if parts[1][0].isalpha():
                    sub = ord(parts[1][0].lower()) - ord('a') + 1
                elif parts[1].isdigit():
                    sub = int(parts[1]) + 100
            
            return (main, sub)
        except:
            return (999, 0)

# ===== ENHANCED FORM PROCESSOR =====

class UniversalFormProcessor:
    """Enhanced universal processor for any USCIS form"""
    
    def __init__(self):
        self.agent = UniversalUSCISAgent()
    
    def process_pdf(self, pdf_file) -> Optional[USCISForm]:
        """Process any USCIS PDF with enhanced analysis and progress tracking"""
        if not PYMUPDF_AVAILABLE:
            st.error("PyMuPDF not available")
            return None
        
        start_time = datetime.now()
        
        # Progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            status_text.text("📖 Extracting PDF content...")
            progress_bar.progress(0.1)
            
            pdf_file.seek(0)
            doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
            
            full_text = ""
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                full_text += f"\n\n=== PAGE {page_num + 1} ===\n{text}"
            
            total_pages = len(doc)
            doc.close()
            
        except Exception as e:
            st.error(f"PDF extraction error: {e}")
            return None
        
        status_text.text("🔍 Identifying form type...")
        progress_bar.progress(0.2)
        
        form_info = self.agent.identify_form(full_text[:3000])
        
        form = USCISForm(
            form_number=form_info["form_number"],
            title=form_info["title"],
            edition_date=form_info["edition_date"],
            form_category=form_info.get("form_category", ""),
            total_pages=total_pages
        )
        
        status_text.text("📋 Extracting all form parts...")
        progress_bar.progress(0.3)
        
        parts_data = self.agent.extract_parts(full_text)
        
        if not parts_data:
            st.error("No parts could be extracted")
            return None
        
        # Process each part
        total_parts = len(parts_data)
        extraction_summary = []
        
        for i, part_info in enumerate(parts_data):
            part_num = part_info["number"]
            part_title = part_info["title"]
            
            status_text.text(f"🔄 Processing Part {part_num}: {part_title}")
            progress_bar.progress(0.4 + (0.5 * i / total_parts))
            
            part_text = self._extract_part_text_enhanced(full_text, part_num)
            
            with st.spinner(f"Analyzing fields in Part {part_num}..."):
                fields = self.agent.analyze_part_fields(part_text, part_num, part_title)
            
            patterns = {}
            for field in fields:
                if field.field_pattern:
                    patterns[field.field_pattern] = patterns.get(field.field_pattern, 0) + 1
            
            part = FormPart(
                number=part_num,
                title=part_title,
                fields=fields,
                field_patterns=patterns,
                processed=True,
                text_length=len(part_text),
                extraction_confidence=part_info.get("confidence", 1.0) if isinstance(part_info, dict) and "confidence" in part_info else 1.0
            )
            
            form.parts[part.number] = part
            
            # Collect summary info
            field_count = len([f for f in fields if not f.is_subfield and not f.is_choice])
            extraction_summary.append(f"Part {part_num}: {field_count} fields")
        
        status_text.text("📊 Finalizing analysis...")
        progress_bar.progress(0.95)
        
        form.processing_time = (datetime.now() - start_time).total_seconds()
        form.ai_summary = self._generate_enhanced_summary(form)
        form.extraction_summary = " | ".join(extraction_summary)
        
        status_text.text("✅ Processing complete!")
        progress_bar.progress(1.0)
        
        return form
    
    def _extract_part_text_enhanced(self, full_text: str, part_number: int) -> str:
        """Root cause fix: Use precise part boundaries instead of fuzzy pattern matching"""
        
        # STEP 1: Use precise boundaries if available from extract_parts
        if hasattr(self, '_part_positions') and part_number in self._part_positions:
            start_pos, end_pos = self._part_positions[part_number]
            
            if start_pos is not None and end_pos is not None:
                part_text = full_text[start_pos:end_pos]
                st.info(f"✅ Part {part_number}: Using precise boundaries ({start_pos}-{end_pos}, {len(part_text)} chars)")
                
                # Quick validation that we have the right content
                part_title_patterns = [
                    rf"Part\s+{part_number}\.?\s*[A-Z]",
                    rf"PART\s+{part_number}\.?\s*[A-Z]"
                ]
                
                has_part_header = any(re.search(pattern, part_text[:200], re.IGNORECASE) 
                                    for pattern in part_title_patterns)
                
                if has_part_header:
                    return part_text
                else:
                    st.warning(f"Part {part_number}: Precise boundaries don't contain part header, falling back to pattern search")
        
        # STEP 2: Fallback to pattern-based extraction with enhanced logic
        st.info(f"Part {part_number}: Using fallback pattern-based extraction")
        
        # Find the exact start position of this part
        part_start_patterns = [
            rf"(?:^|\n)\s*(Part\s+{part_number}\.?\s*[A-Z][^\n]*)",
            rf"(?:^|\n)\s*(PART\s+{part_number}\.?\s*[A-Z][^\n]*)"
        ]
        
        start_pos = -1
        part_header = ""
        
        for pattern in part_start_patterns:
            match = re.search(pattern, full_text, re.IGNORECASE | re.MULTILINE)
            if match:
                start_pos = match.start()
                part_header = match.group(1).strip()
                break
        
        if start_pos == -1:
            # Last resort: position-based estimation
            st.warning(f"Part {part_number}: No header found, using position estimation")
            total_parts = max(8, part_number + 1)
            part_size = len(full_text) // total_parts
            start_pos = max(0, (part_number - 1) * part_size)
            end_pos = min(len(full_text), start_pos + part_size * 2)
            return full_text[start_pos:end_pos]
        
        # Find the end position by looking for the next part
        end_pos = len(full_text)
        
        # Look for any subsequent parts to determine end boundary
        for next_part_num in range(part_number + 1, part_number + 10):
            next_patterns = [
                rf"(?:^|\n)\s*Part\s+{next_part_num}\.?\s*[A-Z]",
                rf"(?:^|\n)\s*PART\s+{next_part_num}\.?\s*[A-Z]"
            ]
            
            for pattern in next_patterns:
                # Start search well after current part header to avoid false matches
                search_start = start_pos + max(100, len(part_header))
                match = re.search(pattern, full_text[search_start:], re.IGNORECASE | re.MULTILINE)
                if match:
                    end_pos = search_start + match.start()
                    st.info(f"Part {part_number}: Found end boundary at Part {next_part_num} (pos: {end_pos})")
                    break
            
            if end_pos < len(full_text):
                break
        
        # Extract the part text
        part_text = full_text[start_pos:end_pos]
        
        # STEP 3: Content validation and cleanup
        text_length = len(part_text)
        
        # Remove any trailing content that looks like it belongs to next part
        lines = part_text.split('\n')
        clean_lines = []
        
        for i, line in enumerate(lines):
            # Check if this line starts a new part
            if i > 5:  # Skip first few lines to avoid false positives
                if re.match(r'^\s*Part\s+\d+\.?\s*[A-Z]', line, re.IGNORECASE):
                    st.info(f"Part {part_number}: Truncated at line {i} to prevent content mixing")
                    break
            clean_lines.append(line)
        
        part_text = '\n'.join(clean_lines)
        
        # Final validation
        if len(part_text) < 50:
            st.error(f"Part {part_number}: Extracted text too short ({len(part_text)} chars)")
            # Expand search area as last resort
            expanded_end = min(len(full_text), end_pos + 1000)
            part_text = full_text[start_pos:expanded_end]
            st.info(f"Part {part_number}: Expanded to {len(part_text)} chars")
        
        st.success(f"Part {part_number}: Clean extraction complete ({len(part_text)} chars)")
        return part_text
    
    def _generate_enhanced_summary(self, form: USCISForm) -> str:
        """Generate enhanced processing summary with detailed metrics"""
        insights = []
        
        total_fields = sum(len(p.fields) for p in form.parts.values())
        parent_fields = sum(len([f for f in p.fields if f.is_parent]) for p in form.parts.values())
        subfields = sum(len([f for f in p.fields if f.is_subfield]) for p in form.parts.values())
        questions = sum(len([f for f in p.fields if f.field_type == "question"]) for p in form.parts.values())
        
        insights.append(f"Enhanced extraction: {form.form_number} with {len(form.parts)} parts")
        insights.append(f"Total fields: {total_fields} ({parent_fields} parent, {subfields} subfields, {questions} questions)")
        
        # Analysis by extraction method
        ai_fields = sum(1 for p in form.parts.values() for f in p.fields if f.extraction_method == "ai_agent")
        fallback_fields = total_fields - ai_fields
        
        if ai_fields > 0:
            insights.append(f"AI analysis: {ai_fields} fields")
        if fallback_fields > 0:
            insights.append(f"Pattern fallback: {fallback_fields} fields")
        
        # Pattern analysis
        all_patterns = {}
        for part in form.parts.values():
            for pattern, count in part.field_patterns.items():
                all_patterns[pattern] = all_patterns.get(pattern, 0) + count
        
        if all_patterns:
            top_patterns = sorted(all_patterns.items(), key=lambda x: x[1], reverse=True)[:3]
            insights.append(f"Top patterns: {', '.join([f'{p}({c})' for p, c in top_patterns])}")
        
        return " | ".join(insights)

# ===== UI FUNCTIONS =====

def display_universal_field(field: USCISField, prefix: str):
    """Display field with universal styling and controls"""
    unique_key = f"{prefix}_{field.unique_id}"
    
    if field.is_parent:
        css_class = "field-parent"
        icon = "📁"
        status = "Parent"
    elif field.is_subfield:
        css_class = "field-subfield" 
        icon = "↳"
        status = f"Sub of {field.parent_number}"
    elif field.field_type == "question":
        css_class = "field-question"
        icon = "❓"
        status = "Question"
    elif field.is_choice:
        css_class = "field-choice"
        icon = "☑️"
        status = f"Choice for {field.parent_number}"
    else:
        css_class = "field-card"
        icon = "📝"
        status = field.field_type.title()
    
    if field.is_mapped:
        css_class += " field-mapped"
    if field.in_questionnaire:
        css_class += " field-questionnaire"
    
    st.markdown(f'<div class="{css_class}">', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([4, 3, 2])
    
    with col1:
        confidence_display = f" ({field.confidence:.0%})" if field.confidence < 1.0 else ""
        st.markdown(f"**{icon} {field.number}. {field.label}**{confidence_display}")
        
        if field.field_pattern or field.ai_reasoning:
            with st.expander("🤖 AI Analysis"):
                if field.field_pattern:
                    st.code(f"Pattern: {field.field_pattern}")
                if field.ai_reasoning:
                    st.markdown(f'<div class="ai-analysis">{field.ai_reasoning}</div>', 
                               unsafe_allow_html=True)
                if field.extraction_method:
                    st.caption(f"Method: {field.extraction_method}")
    
    with col2:
        if not field.is_parent and field.field_type != "question":
            if field.field_type == "date":
                field.value = st.date_input("Value", key=f"{unique_key}_val", 
                                          label_visibility="collapsed")
                field.value = str(field.value) if field.value else ""
            elif field.field_type in ["checkbox", "choice"] or field.is_choice:
                field.value = st.checkbox("", key=f"{unique_key}_choice")
            elif field.field_type == "email":
                field.value = st.text_input("Value", value=field.value, 
                                          key=f"{unique_key}_val", 
                                          placeholder="email@example.com",
                                          label_visibility="collapsed")
            elif field.field_type in ["phone", "ssn", "alien_number"]:
                field.value = st.text_input("Value", value=field.value, 
                                          key=f"{unique_key}_val",
                                          label_visibility="collapsed")
            else:
                field.value = st.text_input("Value", value=field.value, 
                                          key=f"{unique_key}_val", 
                                          label_visibility="collapsed")
    
    with col3:
        status_indicators = [status]
        if field.is_mapped:
            status_indicators.append("✅ Mapped")
        if field.in_questionnaire:
            status_indicators.append("📝 Quest")
        
        st.markdown(" | ".join(status_indicators))
        
        if not field.is_parent:
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Map", key=f"{unique_key}_map_btn", use_container_width=True):
                    st.session_state[f"show_mapping_{field.unique_id}"] = True
                    st.rerun()
            with c2:
                quest_label = "Remove" if field.in_questionnaire else "Quest"
                if st.button(quest_label, key=f"{unique_key}_quest_btn", use_container_width=True):
                    field.in_questionnaire = not field.in_questionnaire
                    st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    if st.session_state.get(f"show_mapping_{field.unique_id}"):
        show_universal_mapping_dialog(field, unique_key)

def show_universal_mapping_dialog(field: USCISField, unique_key: str):
    """Show universal field mapping dialog"""
    st.markdown("---")
    st.markdown("### 🎯 Map Field to Database Schema")
    
    col1, col2 = st.columns(2)
    
    with col1:
        schema = st.selectbox(
            "Database Schema",
            list(DATABASE_SCHEMA.keys()),
            key=f"{unique_key}_schema",
            format_func=lambda x: DATABASE_SCHEMA[x]["label"]
        )
    
    with col2:
        if schema == "custom":
            db_field = st.text_input("Custom Field", key=f"{unique_key}_custom")
        else:
            db_field = st.selectbox(
                "Database Field",
                DATABASE_SCHEMA[schema]["paths"],
                key=f"{unique_key}_field"
            )
    
    if field.field_pattern:
        st.info(f"💡 Suggested mapping based on pattern '{field.field_pattern}'")
    
    col3, col4 = st.columns(2)
    with col3:
        if st.button("✅ Apply Mapping", key=f"{unique_key}_apply"):
            field.is_mapped = True
            field.db_object = schema
            field.db_field = db_field
            del st.session_state[f"show_mapping_{field.unique_id}"]
            st.rerun()
    
    with col4:
        if st.button("❌ Cancel", key=f"{unique_key}_cancel"):
            del st.session_state[f"show_mapping_{field.unique_id}"]
            st.rerun()

def export_universal_data(part: FormPart, export_type: str, form_info: Dict) -> str:
    """Export data with universal structure"""
    base_info = {
        "form_number": form_info.get("form_number", "Unknown"),
        "form_title": form_info.get("title", ""),
        "part_number": part.number,
        "part_title": part.title,
        "timestamp": datetime.now().isoformat()
    }
    
    if export_type == "mapped_fields":
        mapped = [f for f in part.fields if f.is_mapped and not f.is_parent]
        data = {
            **base_info,
            "mapped_fields": [
                {
                    "field_number": f.number,
                    "field_label": f.label,
                    "field_type": f.field_type,
                    "field_pattern": f.field_pattern,
                    "field_value": f.value,
                    "db_object": f.db_object,
                    "db_field": f.db_field,
                    "is_subfield": f.is_subfield,
                    "parent_number": f.parent_number
                }
                for f in mapped
            ],
            "mapping_summary": {
                schema: len([f for f in mapped if f.db_object == schema])
                for schema in set(f.db_object for f in mapped)
            }
        }
    
    elif export_type == "questionnaire":
        quest_fields = [f for f in part.fields if f.in_questionnaire and not f.is_parent]
        data = {
            **base_info,
            "questionnaire_fields": [
                {
                    "field_number": f.number,
                    "field_label": f.label,
                    "field_type": f.field_type,
                    "field_pattern": f.field_pattern,
                    "field_value": f.value,
                    "is_subfield": f.is_subfield,
                    "parent_number": f.parent_number
                }
                for f in quest_fields
            ]
        }
    
    elif export_type == "db_objects":
        db_objects = {}
        for field in part.fields:
            if field.is_mapped and not field.is_parent:
                if field.db_object not in db_objects:
                    db_objects[field.db_object] = []
                db_objects[field.db_object].append({
                    "field_number": field.number,
                    "field_label": field.label,
                    "field_type": field.field_type,
                    "field_pattern": field.field_pattern,
                    "field_value": field.value,
                    "db_field": field.db_field
                })
        
        data = {
            **base_info,
            "database_objects": db_objects
        }
    
    return json.dumps(data, indent=2, default=str)

# ===== MAIN APPLICATION =====

def main():
    st.markdown("""
    <div class="main-header">
        <h1>🤖 Universal USCIS Reader - Enhanced Part Detection</h1>
        <p>Works with ANY USCIS form - now properly reads ALL 8 parts</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize
    if 'form' not in st.session_state:
        st.session_state.form = None
    if 'processor' not in st.session_state:
        st.session_state.processor = UniversalFormProcessor()
    
    # Check AI availability
    if st.session_state.processor.agent.client:
        st.markdown("""
        <div class="agent-status">
            <strong>✅ Enhanced Universal Claude Agent Active</strong><br>
            Multi-pass part detection ensures ALL parts are found (0-8).
        </div>
        """, unsafe_allow_html=True)
    else:
        st.error("❌ Claude API not configured. Please add ANTHROPIC_API_KEY to your Streamlit secrets.")
        st.stop()
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 📊 Enhanced Analysis")
        
        if st.session_state.form:
            form = st.session_state.form
            st.success(f"📄 {form.form_number}")
            st.info(f"📖 {form.title}")
            if form.form_category:
                st.info(f"🏷️ {form.form_category.title()}")
            
            # Enhanced metrics
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Parts Found", len(form.parts))
                st.metric("Processing Time", f"{form.processing_time:.1f}s")
            
            with col2:
                total_fields = sum(len(p.fields) for p in form.parts.values())
                mapped_fields = sum(1 for p in form.parts.values() 
                                  for f in p.fields if f.is_mapped)
                st.metric("Total Fields", total_fields)
                st.metric("Mapped Fields", mapped_fields)
            
            # Parts overview
            st.markdown("### 📋 Parts Overview")
            for part_num, part in sorted(form.parts.items()):
                field_count = len([f for f in part.fields if not f.is_subfield and not f.is_choice])
                confidence = part.extraction_confidence
                confidence_color = "🟢" if confidence > 0.8 else "🟡" if confidence > 0.5 else "🔴"
                
                st.markdown(f"""
                <div class="part-status">
                    {confidence_color} <strong>Part {part_num}</strong>: {field_count} fields<br>
                    <small>{part.title[:50]}...</small>
                </div>
                """, unsafe_allow_html=True)
            
            if form.ai_summary:
                st.markdown("### 🧠 AI Insights")
                st.info(form.ai_summary)
                
            if form.extraction_summary:
                st.markdown("### 📈 Extraction Summary")
                st.info(form.extraction_summary)
        
        if st.button("🔄 Reset", use_container_width=True):
            st.session_state.clear()
            st.rerun()
    
    # Main tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📤 Upload & Process", "🗂️ Field Mapping", "📝 Questionnaire", "💾 Export"])
    
    with tab1:
        st.markdown("### 📤 Upload Any USCIS Form for Enhanced AI Analysis")
        
        uploaded_file = st.file_uploader("Choose USCIS PDF file", type=['pdf'])
        
        if uploaded_file:
            if st.button("🚀 Process with Enhanced AI Agent", type="primary", use_container_width=True):
                form = st.session_state.processor.process_pdf(uploaded_file)
                
                if form:
                    st.session_state.form = form
                    st.success(f"✅ Successfully processed {form.form_number}: {form.title}")
                    
                    st.markdown("### 📋 Enhanced AI Analysis Results")
                    
                    # Detailed part analysis
                    for part_num, part in sorted(form.parts.items()):
                        with st.expander(f"📁 Part {part_num}: {part.title}", expanded=True):
                            parent_fields = len([f for f in part.fields if f.is_parent])
                            subfields = len([f for f in part.fields if f.is_subfield])
                            questions = len([f for f in part.fields if f.field_type == "question"])
                            choices = len([f for f in part.fields if f.is_choice])
                            regular_fields = len([f for f in part.fields if not f.is_parent and not f.is_subfield and not f.is_choice])
                            
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Parent Fields", parent_fields)
                                st.metric("Subfields", subfields)
                            with col2:
                                st.metric("Questions", questions)  
                                st.metric("Choices", choices)
                            with col3:
                                st.metric("Regular Fields", regular_fields)
                                st.metric("Total", len(part.fields))
                            
                            if part.field_patterns:
                                patterns = ", ".join(f"{k}({v})" for k, v in part.field_patterns.items())
                                st.caption(f"🔍 Patterns detected: {patterns}")
                                
                            st.caption(f"📝 Text length: {part.text_length:,} characters")
                            st.caption(f"🎯 Extraction confidence: {part.extraction_confidence:.0%}")
                else:
                    st.error("❌ Failed to process form")
    
    with tab2:
        if st.session_state.form:
            st.markdown("### 🗂️ Universal Field Mapping")
            
            form = st.session_state.form
            
            # Enhanced part selection
            part_numbers = sorted(form.parts.keys())
            part_options = []
            for part_num in part_numbers:
                part = form.parts[part_num]
                field_count = len([f for f in part.fields if not f.is_subfield and not f.is_choice])
                confidence = part.extraction_confidence
                status_icon = "🟢" if confidence > 0.8 else "🟡" if confidence > 0.5 else "🔴"
                part_options.append(f"{status_icon} Part {part_num}: {part.title} ({field_count} fields)")
            
            selected_idx = st.selectbox("Select Part to Map", range(len(part_options)), 
                                      format_func=lambda x: part_options[x])
            selected_part = part_numbers[selected_idx]
            
            if selected_part is not None:
                part = form.parts[selected_part]
                
                st.markdown(f"#### Part {part.number}: {part.title}")
                st.info(f"📊 {len(part.fields)} total fields | Confidence: {part.extraction_confidence:.0%}")
                
                # Display fields with enhanced organization
                displayed = set()
                for field in sorted(part.fields, key=lambda f: st.session_state.processor.agent._get_sort_key(f.number)):
                    if field.number not in displayed:
                        if field.is_parent or not field.is_subfield:
                            display_universal_field(field, f"map_p{part.number}")
                            displayed.add(field.number)
                            
                            # Show related subfields
                            for child in part.fields:
                                if child.parent_number == field.number and child.number not in displayed:
                                    display_universal_field(child, f"map_p{part.number}")
                                    displayed.add(child.number)
        else:
            st.info("👆 Upload and process any USCIS form first")
    
    with tab3:
        if st.session_state.form:
            st.markdown("### 📝 Universal Questionnaire")
            
            form = st.session_state.form
            
            for part_num, part in sorted(form.parts.items()):
                quest_fields = [f for f in part.fields if f.in_questionnaire and not f.is_parent]
                
                if quest_fields:
                    st.markdown(f"#### Part {part_num}: {part.title}")
                    
                    for field in sorted(quest_fields, key=lambda f: st.session_state.processor.agent._get_sort_key(f.number)):
                        st.markdown(f"**{field.number}. {field.label}**")
                        
                        if field.field_pattern:
                            st.caption(f"Pattern: {field.field_pattern}")
                        
                        if field.is_choice or field.field_type == "checkbox":
                            field.value = st.checkbox(f"Select {field.label}", key=f"quest_{field.unique_id}_checkbox")
                        elif field.field_type == "date":
                            field.value = st.date_input(f"Enter date", key=f"quest_{field.unique_id}_date")
                            field.value = str(field.value) if field.value else ""
                        elif field.field_type == "email":
                            field.value = st.text_input(f"Enter email", key=f"quest_{field.unique_id}_email", placeholder="email@example.com")
                        else:
                            field.value = st.text_input(f"Enter value", key=f"quest_{field.unique_id}_text")
                        
                        st.markdown("---")
            
            if not any(f.in_questionnaire for p in form.parts.values() for f in p.fields):
                st.info("No fields added to questionnaire yet. Go to Field Mapping tab to add fields.")
        else:
            st.info("👆 Upload and process any USCIS form first")
    
    with tab4:
        if st.session_state.form:
            st.markdown("### 💾 Enhanced Export Options")
            
            form = st.session_state.form
            form_info = {
                "form_number": form.form_number,
                "title": form.title,
                "form_category": form.form_category
            }
            
            for part_num, part in sorted(form.parts.items()):
                st.markdown(f'<div class="export-section">', unsafe_allow_html=True)
                st.markdown(f"#### Part {part_num}: {part.title}")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    mapped_count = len([f for f in part.fields if f.is_mapped and not f.is_parent])
                    if mapped_count > 0:
                        mapped_data = export_universal_data(part, "mapped_fields", form_info)
                        st.download_button(
                            f"📋 Mapped Fields ({mapped_count})",
                            mapped_data,
                            f"{form.form_number}_part_{part_num}_mapped.json",
                            "application/json",
                            key=f"export_mapped_{part_num}",
                            use_container_width=True
                        )
                    else:
                        st.button(f"📋 Mapped Fields (0)", disabled=True, key=f"disabled_mapped_{part_num}", use_container_width=True)
                
                with col2:
                    quest_count = len([f for f in part.fields if f.in_questionnaire and not f.is_parent])
                    if quest_count > 0:
                        quest_data = export_universal_data(part, "questionnaire", form_info)
                        st.download_button(
                            f"📝 Questionnaire ({quest_count})",
                            quest_data,
                            f"{form.form_number}_part_{part_num}_questionnaire.json",
                            "application/json",
                            key=f"export_quest_{part_num}",
                            use_container_width=True
                        )
                    else:
                        st.button(f"📝 Questionnaire (0)", disabled=True, key=f"disabled_quest_{part_num}", use_container_width=True)
                
                with col3:
                    db_objects = set(f.db_object for f in part.fields if f.is_mapped and not f.is_parent)
                    if db_objects:
                        db_data = export_universal_data(part, "db_objects", form_info)
                        st.download_button(
                            f"🗃️ DB Objects ({len(db_objects)})",
                            db_data,
                            f"{form.form_number}_part_{part_num}_db_objects.json",
                            "application/json",
                            key=f"export_db_{part_num}",
                            use_container_width=True
                        )
                    else:
                        st.button(f"🗃️ DB Objects (0)", disabled=True, key=f"disabled_db_{part_num}", use_container_width=True)
                
                st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown("#### 📦 Complete Form Export")
            if st.button("📥 Download Complete Form Analysis", type="primary", use_container_width=True):
                full_export = {
                    "form_info": {
                        "form_number": form.form_number,
                        "title": form.title,
                        "edition_date": form.edition_date,
                        "form_category": form.form_category,
                        "processing_time": form.processing_time,
                        "ai_summary": form.ai_summary,
                        "extraction_summary": form.extraction_summary
                    },
                    "parts": {
                        str(part_num): {
                            "title": part.title,
                            "field_patterns": part.field_patterns,
                            "extraction_confidence": part.extraction_confidence,
                            "text_length": part.text_length,
                            "fields": [asdict(field) for field in part.fields]
                        }
                        for part_num, part in form.parts.items()
                    }
                }
                
                st.download_button(
                    "📥 Download Complete Analysis",
                    json.dumps(full_export, indent=2, default=str),
                    f"{form.form_number}_complete_analysis.json",
                    "application/json",
                    key="export_complete"
                )
        else:
            st.info("👆 Upload and process any USCIS form first")

if __name__ == "__main__":
    main()
