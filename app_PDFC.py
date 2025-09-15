#!/usr/bin/env python3
"""
UNIVERSAL USCIS FORM READER - AGENTIC AI APPROACH
==============================================
Uses Claude Sonnet 4 for intelligent field analysis and structure creation
Incorporates all extraction rules from previous conversations
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
    page_title="Universal USCIS Reader - AI Agent",
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
    .verification-score {
        padding: 10px;
        border-radius: 5px;
        margin: 10px 0;
    }
    .score-excellent { background: #c8e6c9; border: 1px solid #4caf50; }
    .score-good { background: #fff9c4; border: 1px solid #fbc02d; }
    .score-poor { background: #ffccbc; border: 1px solid #f44336; }
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
    verification_report: Dict = dataclass_field(default_factory=dict)
    extraction_verified: bool = False

# ===== DATABASE SCHEMAS =====

DATABASE_SCHEMA = {
    "beneficiary": {
        "label": "👤 Beneficiary/Applicant",
        "paths": [
            "beneficiaryLastName", "beneficiaryFirstName", "beneficiaryMiddleName",
            "beneficiaryOtherNames", "beneficiaryAlienNumber", "beneficiaryUSCISNumber",
            "beneficiarySSN", "beneficiaryDateOfBirth", "beneficiaryGender",
            "beneficiaryCountryOfBirth", "beneficiaryCityOfBirth",
            "beneficiaryCurrentCountryOfCitizenship", "beneficiaryNationality",
            "beneficiaryStreetNumberAndName", "beneficiaryAptSteFlr",
            "beneficiaryAptSteFlrNumber", "beneficiaryCityOrTown",
            "beneficiaryState", "beneficiaryZipCode", "beneficiaryProvince",
            "beneficiaryPostalCode", "beneficiaryCountry", "beneficiaryDaytimePhone",
            "beneficiaryMobilePhone", "beneficiaryEmail", "beneficiaryFaxNumber",
            "beneficiaryInCareOf"
        ]
    },
    "petitioner": {
        "label": "🏢 Petitioner/Employer",
        "paths": [
            "petitionerLastName", "petitionerFirstName", "petitionerMiddleName",
            "petitionerCompanyName", "petitionerOrganizationName",
            "petitionerBusinessType", "petitionerYearEstablished",
            "petitionerStreetNumberAndName", "petitionerAptSteFlr",
            "petitionerAptSteFlrNumber", "petitionerCityOrTown",
            "petitionerState", "petitionerZipCode", "petitionerProvince",
            "petitionerPostalCode", "petitionerCountry", "petitionerDaytimePhone",
            "petitionerMobilePhone", "petitionerEmail", "petitionerFaxNumber",
            "petitionerFEIN", "petitionerSSN", "petitionerEmployeeCount",
            "petitionerGrossIncome", "petitionerNetIncome"
        ]
    },
    "attorney": {
        "label": "⚖️ Attorney/Representative",
        "paths": [
            "attorneyLastName", "attorneyFirstName", "attorneyMiddleName",
            "attorneyOrganizationName", "attorneyBarNumber", "attorneyUSCISNumber",
            "attorneyStreetNumberAndName", "attorneyAptSteFlr",
            "attorneyAptSteFlrNumber", "attorneyCityOrTown", "attorneyState",
            "attorneyZipCode", "attorneyCountry", "attorneyDaytimePhone",
            "attorneyMobilePhone", "attorneyEmail", "attorneyFaxNumber",
            "attorneyG28Attached", "attorneyInCareOf"
        ]
    },
    "interpreter": {
        "label": "🗣️ Interpreter",
        "paths": [
            "interpreterLastName", "interpreterFirstName", "interpreterMiddleName",
            "interpreterOrganizationName", "interpreterLanguage",
            "interpreterStreetNumberAndName", "interpreterAptSteFlr",
            "interpreterAptSteFlrNumber", "interpreterCityOrTown",
            "interpreterState", "interpreterZipCode", "interpreterCountry",
            "interpreterDaytimePhone", "interpreterMobilePhone",
            "interpreterEmail", "interpreterFaxNumber"
        ]
    },
    "preparer": {
        "label": "📝 Preparer",
        "paths": [
            "preparerLastName", "preparerFirstName", "preparerMiddleName",
            "preparerOrganizationName", "preparerStreetNumberAndName",
            "preparerAptSteFlr", "preparerAptSteFlrNumber",
            "preparerCityOrTown", "preparerState", "preparerZipCode",
            "preparerCountry", "preparerDaytimePhone", "preparerMobilePhone",
            "preparerEmail", "preparerFaxNumber"
        ]
    },
    "custom": {
        "label": "✏️ Custom Fields",
        "paths": []
    }
}

# ===== VERIFICATION AGENTS =====

class ExtractionVerificationAgent:
    """AI agent to verify extraction completeness and accuracy"""
    
    def __init__(self, client):
        self.client = client
    
    def verify_complete_extraction(self, form: USCISForm, original_text: str) -> Dict:
        """Verify that all parts and fields were extracted correctly"""
        verification_report = {
            "overall_completeness": 0.0,
            "parts_verified": {},
            "missing_fields": [],
            "extraction_gaps": [],
            "recommendations": []
        }
        
        if not self.client:
            verification_report["note"] = "Verification requires Claude API"
            return verification_report
        
        try:
            # Verify each part
            total_completeness = 0
            for part_num, part in form.parts.items():
                part_verification = self._verify_part_extraction(part, original_text)
                verification_report["parts_verified"][part_num] = part_verification
                total_completeness += part_verification.get("completeness_score", 0)
            
            # Calculate overall completeness
            if form.parts:
                verification_report["overall_completeness"] = total_completeness / len(form.parts)
            
            # Generate recommendations
            verification_report["recommendations"] = self._generate_recommendations(verification_report)
            
        except Exception as e:
            verification_report["error"] = str(e)
        
        return verification_report
    
    def _verify_part_extraction(self, part: FormPart, original_text: str) -> Dict:
        """Verify extraction for a specific part"""
        part_text = self._get_part_text_for_verification(original_text, part.number)
        
        # Get extracted field numbers
        extracted_numbers = set(f.number for f in part.fields)
        
        # AI verification
        verification_prompt = f"""Verify the completeness of field extraction for this USCIS form part.

EXTRACTED FIELDS: {sorted(extracted_numbers)}

ORIGINAL PART TEXT:
{part_text[:8000]}

Analyze and return JSON:
{{
    "completeness_score": 0.0-1.0,
    "missing_field_numbers": ["list of any missing numbered fields"],
    "extraction_quality": "excellent/good/fair/poor",
    "field_count_analysis": {{
        "expected_approximate_count": 15,
        "actual_extracted_count": {len(part.fields)},
        "coverage_assessment": "complete/mostly_complete/incomplete"
    }},
    "specific_issues": ["any specific problems found"],
    "verification_notes": "detailed analysis of extraction quality"
}}

Focus on:
1. Are all numbered items (1., 2., 3., etc.) captured?
2. Are subfields properly created for name/address fields?
3. Are Yes/No questions converted to choices?
4. Is the field hierarchy logical and complete?
"""

        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2000,
                messages=[{"role": "user", "content": verification_prompt}]
            )
            
            content = response.content[0].text.strip()
            if "{" in content:
                json_start = content.find("{")
                json_end = content.rfind("}") + 1
                return json.loads(content[json_start:json_end])
        
        except Exception as e:
            return {
                "completeness_score": 0.5,
                "error": str(e),
                "extraction_quality": "unknown"
            }
        
        return {"completeness_score": 0.5, "extraction_quality": "unknown"}
    
    def _get_part_text_for_verification(self, full_text: str, part_number: int) -> str:
        """Extract part text for verification"""
        # Handle Part 0 (Attorney section) specially
        if part_number == 0:
            # Look for attorney section indicators
            attorney_patterns = [
                r"To be completed by an?\s+Attorney",
                r"Attorney or Accredited Representative",
                r"Form G-?28"
            ]
            
            for pattern in attorney_patterns:
                match = re.search(pattern, full_text, re.IGNORECASE)
                if match:
                    start_pos = match.start()
                    # Find end (usually Part 1 or next major section)
                    end_match = re.search(r"Part\s+1\b", full_text[start_pos:], re.IGNORECASE)
                    if end_match:
                        end_pos = start_pos + end_match.start()
                    else:
                        end_pos = min(start_pos + 5000, len(full_text))
                    return full_text[start_pos:end_pos]
        
        # Standard part extraction
        patterns = [
            rf"Part\s+{part_number}\b",
            rf"PART\s+{part_number}\b",
            rf"Part\s+{part_number}\.",
            rf"Part\s+{part_number}\s*:",
        ]
        
        start_pos = -1
        for pattern in patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                start_pos = match.start()
                break
        
        if start_pos == -1:
            # If part not found, return a reasonable section
            section_size = len(full_text) // 8
            start_estimate = part_number * section_size
            return full_text[start_estimate:start_estimate + section_size + 5000]
        
        # Find next part boundary
        end_pos = len(full_text)
        for next_num in range(part_number + 1, part_number + 6):
            next_patterns = [
                rf"Part\s+{next_num}\b",
                rf"PART\s+{next_num}\b"
            ]
            
            for pattern in next_patterns:
                match = re.search(pattern, full_text[start_pos:], re.IGNORECASE)
                if match:
                    end_pos = start_pos + match.start()
                    break
            
            if end_pos < len(full_text):
                break
        
        return full_text[start_pos:end_pos]
    
    def _generate_recommendations(self, verification_report: Dict) -> List[str]:
        """Generate recommendations based on verification results"""
        recommendations = []
        
        overall_score = verification_report.get("overall_completeness", 0)
        
        if overall_score >= 0.9:
            recommendations.append("✅ Excellent extraction - all fields appear to be captured correctly")
        elif overall_score >= 0.75:
            recommendations.append("⚠️ Good extraction with minor gaps - review missing fields")
        elif overall_score >= 0.5:
            recommendations.append("🔍 Moderate extraction - significant fields may be missing")
        else:
            recommendations.append("❌ Poor extraction - manual review recommended")
        
        # Check for missing fields across parts
        missing_count = sum(
            len(part_data.get("missing_field_numbers", []))
            for part_data in verification_report.get("parts_verified", {}).values()
        )
        
        if missing_count > 0:
            recommendations.append(f"🔧 {missing_count} missing fields detected - consider re-extraction")
        
        return recommendations

class UniversalUSCISAgent:
    """Claude Sonnet 4 agent for any USCIS form analysis"""
    
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
        """Extract all parts/sections from any USCIS form - enhanced with Part 0 detection"""
        if not self.client:
            return self._comprehensive_part_extraction(text)
        
        prompt = f"""Analyze this COMPLETE USCIS form and identify ALL parts, sections, or major divisions.

CRITICAL RULES:
1. Part 0 exists if there's text "To be completed by an Attorney or Accredited Representative"
2. Part 0 includes fields like: Form G-28 attached, Attorney State Bar Number, USCIS Online Account Number
3. "Information About You" sections typically refer to the BENEFICIARY (not petitioner)
4. Look for ALL parts from 0 to 10+

Common USCIS form patterns:
- Part 0: Attorney/Representative Information (if present)
- Part 1: Information About You (Beneficiary) OR Petitioner Information
- Part 2: Application Type / Petition Type / Basis
- Part 3: Processing Information / Additional Information About Beneficiary
- Part 4-7: Various sections depending on form
- Part 8+: Contact Information, Certification, Signature sections

Look for ALL variations:
- "Part X." followed by title
- "Part X:" followed by title  
- Attorney sections even if not numbered
- Signature/certification sections
- Contact information sections

Return JSON array with ALL parts found:
[{{
    "number": 0,
    "title": "To be completed by an Attorney or Accredited Representative"
}},
{{
    "number": 1,
    "title": "Information About You"
}},
... continue for ALL parts found ...]

COMPLETE FORM TEXT:
{text}"""

        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = response.content[0].text.strip()
            if "[" in content:
                json_start = content.find("[")
                json_end = content.rfind("]") + 1
                parts = json.loads(content[json_start:json_end])
                
                # Verify we got Part 0 if attorney section exists
                if self._has_attorney_section(text) and not any(p["number"] == 0 for p in parts):
                    parts.insert(0, {
                        "number": 0,
                        "title": "To be completed by an Attorney or Accredited Representative"
                    })
                
                if parts and len(parts) >= 3:
                    return parts
                
        except Exception as e:
            st.warning(f"AI parts extraction error: {e}")
        
        # Enhanced fallback extraction
        return self._comprehensive_part_extraction(text)
    
    def _has_attorney_section(self, text: str) -> bool:
        """Check if form has attorney/representative section"""
        attorney_indicators = [
            "to be completed by an attorney",
            "attorney or accredited representative",
            "form g-28",
            "attorney state bar number"
        ]
        
        text_lower = text.lower()
        return any(indicator in text_lower for indicator in attorney_indicators)
    
    def _comprehensive_part_extraction(self, text: str) -> List[Dict]:
        """Comprehensive fallback part extraction with Part 0 support"""
        parts = {}
        
        # Check for Part 0 (Attorney section) first
        if self._has_attorney_section(text):
            parts[0] = {
                "number": 0,
                "title": "To be completed by an Attorney or Accredited Representative",
                "position": 0
            }
        
        # Multiple comprehensive patterns for part detection
        patterns = [
            # Standard formats
            r'Part\s+(\d+)\.\s*([^\n]{3,200})',
            r'PART\s+(\d+)\.\s*([^\n]{3,200})',
            r'Part\s+(\d+)\s*[:\-–]?\s*([^\n]{3,200})',
            
            # Header formats
            r'Part\s+(\d+)[.\s]*([A-Z][^\n]{3,200})',
            r'PART\s+(\d+)[.\s]*([A-Z][^\n]{3,200})',
            
            # Section formats  
            r'Section\s+([A-Z]|\d+)\.\s*([^\n]{3,200})',
            r'SECTION\s+([A-Z]|\d+)\.\s*([^\n]{3,200})',
            
            # Boxed/formatted parts
            r'►\s*Part\s+(\d+)[.\s]*([^\n]{3,200})',
            
            # Variations with contact/signature
            r'Part\s+(\d+)\.\s*(Contact\s+Information[^\n]{0,100})',
            r'Part\s+(\d+)\.\s*(Certification[^\n]{0,100})',
            r'Part\s+(\d+)\.\s*(Additional\s+Information[^\n]{0,100})',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            
            for match in matches:
                try:
                    part_num_str = match.group(1)
                    part_title = match.group(2).strip()
                    
                    # Convert part number
                    if part_num_str.isdigit():
                        part_num = int(part_num_str)
                    elif len(part_num_str) == 1 and part_num_str.isalpha():
                        # Convert A=1, B=2, etc.
                        part_num = ord(part_num_str.upper()) - ord('A') + 1
                    else:
                        continue
                    
                    # Clean title
                    part_title = re.sub(r'^[.\-–\s]+', '', part_title)
                    part_title = re.sub(r'[.\s]+$', '', part_title)  # FIXED: Complete regex
                    part_title = re.sub(r'\s+', ' ', part_title)
                    
                    # Skip very short or generic titles
                    if len(part_title) < 3:
                        continue
                    
                    # Special handling for "Information About You"
                    if "information about you" in part_title.lower():
                        # This is typically the beneficiary section
                        part_title = "Information About You (Beneficiary)"
                    
                    # Only keep if not already found or this one is better
                    if part_num not in parts or len(part_title) > len(parts[part_num]["title"]):
                        parts[part_num] = {
                            "number": part_num,
                            "title": part_title,
                            "position": match.start()
                        }
                        
                except (ValueError, IndexError):
                    continue
        
        # Convert to sorted list
        sorted_parts = sorted(parts.values(), key=lambda x: x["number"])
        
        # If we found parts, return them
        if sorted_parts:
            return sorted_parts
        
        # Ultimate fallback
        return [{"number": 1, "title": "Main Section"}]
    
    def analyze_part_fields(self, part_text: str, part_number: int, part_title: str) -> List[USCISField]:
        """Universal field analysis for any USCIS form part"""
        if not self.client:
            return self._fallback_extraction(part_text, part_number)
        
        # Special instructions for Part 0 (Attorney section)
        part_0_instructions = ""
        if part_number == 0:
            part_0_instructions = """
SPECIAL ATTENTION: This is Part 0 - Attorney/Representative section.
Common fields include:
- Form G-28 attached (checkbox)
- Attorney State Bar Number
- Attorney or Accredited Representative USCIS Online Account Number
- Attorney Name fields
- Attorney Contact Information
"""
        
        # Special instructions for "Information About You"
        beneficiary_instructions = ""
        if "information about you" in part_title.lower():
            beneficiary_instructions = """
IMPORTANT: "Information About You" typically refers to the BENEFICIARY in USCIS forms.
Map these fields with beneficiary context in mind.
"""
        
        prompt = f"""Analyze this USCIS form part and extract ALL fields with intelligent structuring.
{part_0_instructions}
{beneficiary_instructions}

UNIVERSAL FIELD ANALYSIS RULES - APPLY TO ALL USCIS FORMS:

1. **NAME FIELDS** → ALWAYS create subfields:
   - "Full Legal Name" / "Your Name" / "Beneficiary Name" / "Petitioner Name" → a=Family/Last Name, b=Given/First Name, c=Middle Name
   - "Other Names Used" → a=Family Name, b=Given Name, c=Middle Name
   - For Part 0: "Attorney Name" → a=Family Name, b=Given Name, c=Middle Name

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

6. **CHECKBOXES** → Create as single checkbox field:
   - "Select this box if Form G-28 is attached" → checkbox field
   - "Check if..." → checkbox field

7. **MULTIPLE CHOICE** → Create choices for each visible option:
   - Checkbox lists → a=First Option, b=Second Option, c=Third Option...
   - Radio button groups → a=Choice1, b=Choice2, c=Choice3...

8. **SINGLE VALUE FIELDS** → No subfields:
   - SSN, Alien Number, USCIS Number, Email, Phone (when standalone) → Single text field
   - State Bar Number, Account Numbers → Single text field

9. **EMPLOYMENT/EDUCATION FIELDS** → Create relevant subfields:
   - "Employment Information" → a=Job Title, b=Company Name, c=Start Date, d=End Date, e=Salary
   - "Education" → a=School Name, b=Degree, c=Field of Study, d=Graduation Date

10. **SIGNATURE/CERTIFICATION SECTIONS** → Create subfields:
    - "Applicant Certification" → a=Signature, b=Date of Signature
    - "Interpreter Information" → a=Name, b=Language, c=Signature, d=Date

CRITICAL: Find EVERY numbered item (1., 2., 3., etc.) and determine if it needs subfields or choices.

MAINTAIN EXACT NUMBERING from the form. If form shows "5." then use "5" as the number.

Return comprehensive JSON array:
[{{
    "number": "1",
    "label": "Select this box if Form G-28 is attached",
    "type": "checkbox",
    "pattern": "checkbox_field",
    "reasoning": "Checkbox for G-28 attachment indication"
}},
{{
    "number": "2",
    "label": "Attorney State Bar Number (if applicable)",
    "type": "text",
    "pattern": "bar_number",
    "reasoning": "Single text field for attorney bar number"
}},
{{
    "number": "3",
    "label": "Attorney or Accredited Representative USCIS Online Account Number",
    "type": "text",
    "pattern": "account_number",
    "reasoning": "Single text field for USCIS account number"
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
        
        # Special patterns for Part 0 (Attorney section)
        if part_number == 0:
            # Look for attorney-specific fields
            attorney_patterns = [
                (r'form\s+g-?28\s+is\s+attached', 'G-28 Attached', 'checkbox'),
                (r'attorney\s+state\s+bar\s+number', 'Attorney State Bar Number', 'text'),
                (r'uscis\s+online\s+account\s+number', 'USCIS Online Account Number', 'text'),
                (r'attorney\s+or\s+accredited\s+representative', 'Attorney or Accredited Representative', 'parent'),
            ]
            
            field_num = 1
            for pattern, label, field_type in attorney_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    field = USCISField(
                        number=str(field_num),
                        label=label,
                        field_type=field_type,
                        part_number=0,
                        extraction_method="fallback_attorney_pattern"
                    )
                    
                    # Add name subfields for attorney name
                    if field_type == 'parent' and 'representative' in label.lower():
                        self._add_name_subfields(field, fields, part_number)
                    
                    fields.append(field)
                    field_num += 1
        
        # Standard field extraction patterns
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
                    field_data = self._process_field_match(match, pattern_type, text)
                    if field_data and field_data['number'] not in seen_numbers:
                        seen_numbers.add(field_data['number'])
                        
                        field = USCISField(
                            number=field_data['number'],
                            label=field_data['label'],
                            field_type=field_data['field_type'],
                            part_number=part_number,
                            is_subfield=field_data.get('is_subfield', False),
                            is_parent=field_data.get('is_parent', False),
                            parent_number=field_data.get('parent_number', ''),
                            subfield_letter=field_data.get('subfield_letter', ''),
                            extraction_method="fallback_pattern",
                            field_pattern=pattern_type
                        )
                        
                        # Apply intelligent field rules
                        self._apply_field_intelligence(field, fields, part_number)
                        fields.append(field)
                        
                except Exception:
                    continue
        
        # Create missing parents and apply rules
        self._create_missing_parents(fields, part_number)
        self._apply_basic_subfield_rules(fields, part_number)
        
        return fields
    
    def _process_field_match(self, match, pattern_type: str, text: str) -> Optional[Dict]:
        """Process a regex match into field data"""
        if pattern_type == 'subfield':
            parent_num = match.group(1)
            letter = match.group(2)
            label = match.group(3).strip()
            return {
                'number': f"{parent_num}.{letter}",
                'label': label,
                'field_type': 'text',
                'is_subfield': True,
                'parent_number': parent_num,
                'subfield_letter': letter
            }
        elif pattern_type == 'subfield_compact':
            parent_num = match.group(1)
            letter = match.group(2)
            label = match.group(3).strip()
            return {
                'number': f"{parent_num}.{letter}",
                'label': label,
                'field_type': 'text',
                'is_subfield': True,
                'parent_number': parent_num,
                'subfield_letter': letter
            }
        else:
            number = match.group(1)
            label = match.group(2).strip() if len(match.groups()) > 1 else f"Field {number}"
            
            # Clean the label
            label = re.sub(r'\s+', ' ', label)
            label = re.sub(r'^[.\-–\s]+', '', label)
            label = re.sub(r'[.\s]+$', '', label)
            
            if len(label) < 3:
                return None
            
            field_type = self._detect_field_type(label)
            is_parent = self._should_be_parent_field(label, text, match.start())
            
            return {
                'number': number,
                'label': label,
                'field_type': 'parent' if is_parent else field_type,
                'is_parent': is_parent
            }
    
    def _apply_field_intelligence(self, field: USCISField, existing_fields: List[USCISField], part_number: int):
        """Apply intelligent rules to fields based on content"""
        label_lower = field.label.lower()
        
        # Name field intelligence
        if any(indicator in label_lower for indicator in ["name", "full name", "legal name"]):
            if not field.is_subfield:
                field.is_parent = True
                field.field_type = "parent"
                # Subfields will be added by _apply_basic_subfield_rules
        
        # Address field intelligence
        elif any(indicator in label_lower for indicator in ["address", "mailing", "physical"]):
            if not field.is_subfield:
                field.is_parent = True
                field.field_type = "parent"
        
        # Yes/No question intelligence
        elif "?" in field.label:
            field.field_type = "question"
            # Choices will be added by _apply_basic_subfield_rules
        
        # Checkbox intelligence
        elif any(phrase in label_lower for phrase in ["select this box", "check if", "check this box"]):
            field.field_type = "checkbox"
        
        # Date field intelligence
        elif any(word in label_lower for word in ["date", "birth", "expir", "arrival", "departure"]):
            field.field_type = "date"
    
    def _add_name_subfields(self, parent_field: USCISField, fields: List[USCISField], part_number: int):
        """Add standard name subfields"""
        subfields_to_add = [
            ("a", "Family Name (Last Name)", "text"),
            ("b", "Given Name (First Name)", "text"),
            ("c", "Middle Name (if applicable)", "text")
        ]
        
        for letter, sub_label, sub_type in subfields_to_add:
            subfield = USCISField(
                number=f"{parent_field.number}.{letter}",
                label=sub_label,
                field_type=sub_type,
                part_number=part_number,
                is_subfield=True,
                parent_number=parent_field.number,
                subfield_letter=letter,
                extraction_method="auto_generated_name"
            )
            parent_field.subfields.append(subfield)
            fields.append(subfield)
    
    def _should_be_parent_field(self, label: str, text: str, position: int) -> bool:
        """Determine if field should be a parent based on content analysis"""
        label_lower = label.lower()
        
        # Name indicators
        name_indicators = ["full name", "legal name", "your name", "beneficiary name", 
                          "petitioner name", "attorney name", "representative name"]
        if any(indicator in label_lower for indicator in name_indicators):
            return True
        
        # Address indicators
        address_indicators = ["address", "mailing address", "physical address", 
                             "home address", "current address", "foreign address"]
        if any(indicator in label_lower for indicator in address_indicators):
            return True
        
        # Contact indicators
        contact_indicators = ["contact information", "phone numbers"]
        if any(indicator in label_lower for indicator in contact_indicators):
            return True
        
        # Check for subfields ahead
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
                
                # Name fields
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
                            field.subfields.append(subfield)
                
                # Address fields
                elif any(indicator in label_lower for indicator in ["address", "mailing", "physical"]):
                    subfields_to_add = [
                        ("a", "Street Number and Name", "text"),
                        ("b", "Apt/Ste/Flr Number", "text"),
                        ("c", "City or Town", "text"),
                        ("d", "State", "text"),
                        ("e", "ZIP Code", "text")
                    ]
                    
                    # Add foreign address fields if needed
                    if "foreign" in label_lower or "abroad" in label_lower:
                        subfields_to_add.extend([
                            ("f", "Province", "text"),
                            ("g", "Postal Code", "text"),
                            ("h", "Country", "text")
                        ])
                    
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
                            field.subfields.append(subfield)
            
            # Yes/No questions
            elif field.field_type == "question" and "?" in field.label:
                if not field.choices:
                    for letter, choice_label in [("a", "Yes"), ("b", "No")]:
                        choice = FieldChoice(letter=letter, label=choice_label)
                        field.choices.append(choice)
                        
                        choice_field = USCISField(
                            number=f"{field.number}.{letter}",
                            label=choice_label,
                            field_type="choice",
                            part_number=part_number,
                            is_choice=True,
                            parent_number=field.number,
                            subfield_letter=letter,
                            extraction_method="basic_rule_yesno"
                        )
                        new_fields.append(choice_field)
        
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
        elif any(phrase in label_lower for phrase in ["uscis", "receipt number", "account number"]):
            return "text"
        elif any(phrase in label_lower for phrase in ["state bar number", "bar number"]):
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

# ===== FORM PROCESSOR =====

class UniversalFormProcessor:
    """Universal processor for any USCIS form with verification"""
    
    def __init__(self):
        self.agent = UniversalUSCISAgent()
        self.verification_agent = None
        if self.agent.client:
            self.verification_agent = ExtractionVerificationAgent(self.agent.client)
    
    def process_pdf(self, pdf_file) -> Optional[USCISForm]:
        """Process any USCIS PDF with universal AI analysis and verification"""
        if not PYMUPDF_AVAILABLE:
            st.error("PyMuPDF not available")
            return None
        
        start_time = datetime.now()
        
        try:
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
        
        with st.spinner("🤖 Universal AI Agent analyzing form..."):
            form_info = self.agent.identify_form(full_text[:3000])
            
            form = USCISForm(
                form_number=form_info["form_number"],
                title=form_info["title"],
                edition_date=form_info["edition_date"],
                form_category=form_info.get("form_category", ""),
                total_pages=total_pages
            )
            
            parts_data = self.agent.extract_parts(full_text)
            
            # Process each part with field extraction
            for part_info in parts_data:
                part_text = self._extract_part_text(full_text, part_info["number"])
                
                with st.spinner(f"🔍 Analyzing Part {part_info['number']}: {part_info['title']}"):
                    fields = self.agent.analyze_part_fields(
                        part_text, 
                        part_info["number"], 
                        part_info["title"]
                    )
                
                patterns = {}
                for field in fields:
                    if field.field_pattern:
                        patterns[field.field_pattern] = patterns.get(field.field_pattern, 0) + 1
                
                part = FormPart(
                    number=part_info["number"],
                    title=part_info["title"],
                    fields=fields,
                    field_patterns=patterns,
                    processed=True
                )
                
                form.parts[part.number] = part
        
        # VERIFICATION PHASE
        if self.verification_agent:
            with st.spinner("🔍 Verifying extraction completeness..."):
                verification_report = self.verification_agent.verify_complete_extraction(form, full_text)
                form.verification_report = verification_report
                
                # Mark as verified if verification was completed
                if verification_report:
                    form.extraction_verified = True
                
                # Display verification results
                self._display_verification_results(verification_report)
                
                # Attempt to fix gaps if found
                missing_fields_found = any(
                    part_data.get("missing_field_numbers", [])
                    for part_data in verification_report.get("parts_verified", {}).values()
                )
                
                if missing_fields_found:
                    with st.spinner("🔧 Attempting to recover missing fields..."):
                        self._attempt_field_recovery(form, full_text, verification_report)
        else:
            st.warning("Verification agent not available - Claude API required for verification")
        
        form.processing_time = (datetime.now() - start_time).total_seconds()
        form.ai_summary = self._generate_form_insights(form)
        
        return form
    
    def _display_verification_results(self, verification_report: Dict):
        """Display verification results to user"""
        overall_score = verification_report.get("overall_completeness", 0)
        
        score_class = "score-excellent" if overall_score >= 0.9 else "score-good" if overall_score >= 0.75 else "score-poor"
        
        st.markdown(f"""
        <div class="verification-score {score_class}">
            <h4>📊 Extraction Verification: {overall_score:.1%}</h4>
        </div>
        """, unsafe_allow_html=True)
        
        # Show recommendations
        recommendations = verification_report.get("recommendations", [])
        if recommendations:
            for rec in recommendations:
                if "✅" in rec:
                    st.success(rec)
                elif "⚠️" in rec:
                    st.warning(rec)
                elif "🔍" in rec:
                    st.info(rec)
                elif "❌" in rec:
                    st.error(rec)
                else:
                    st.info(rec)
    
    def _attempt_field_recovery(self, form: USCISForm, full_text: str, verification_report: Dict):
        """Attempt to recover missing fields identified during verification"""
        recovery_count = 0
        
        for part_num, part_data in verification_report.get("parts_verified", {}).values():
            missing_numbers = part_data.get("missing_field_numbers", [])
            if missing_numbers and part_num in form.parts:
                part = form.parts[part_num]
                part_text = self._extract_part_text(full_text, part_num)
                
                # Try to extract missing fields
                recovered_fields = self._extract_specific_fields(part_text, missing_numbers, part_num)
                
                if recovered_fields:
                    part.fields.extend(recovered_fields)
                    # Re-sort fields
                    part.fields.sort(key=lambda f: self.agent._get_sort_key(f.number))
                    recovery_count += len(recovered_fields)
        
        if recovery_count > 0:
            st.success(f"🔧 Recovered {recovery_count} missing fields")
        else:
            st.info("🔍 No additional fields could be recovered")
    
    def _extract_specific_fields(self, part_text: str, missing_numbers: List[str], part_num: int) -> List[USCISField]:
        """Try to extract specific missing field numbers"""
        recovered_fields = []
        
        for number in missing_numbers:
            # Try different patterns for this specific number
            patterns = [
                rf'{re.escape(number)}\.\s+([^\n]{{3,300}})',
                rf'Item\s+Number\s+{re.escape(number)}\s+([^\n]{{3,300}})',
                rf'Question\s+{re.escape(number)}\s+([^\n]{{3,300}})'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, part_text, re.IGNORECASE)
                if match:
                    label = match.group(1).strip()
                    if len(label) > 3:
                        field = USCISField(
                            number=number,
                            label=label,
                            field_type=self.agent._detect_field_type(label),
                            part_number=part_num,
                            extraction_method="recovery_verification"
                        )
                        recovered_fields.append(field)
                        break
        
        return recovered_fields
    
    def _extract_part_text(self, full_text: str, part_number: int) -> str:
        """Enhanced universal part text extraction"""
        # Special handling for Part 0 (Attorney section)
        if part_number == 0:
            attorney_patterns = [
                r"To be completed by an?\s+Attorney",
                r"Attorney or Accredited Representative",
                r"Form G-?28"
            ]
            
            for pattern in attorney_patterns:
                match = re.search(pattern, full_text, re.IGNORECASE)
                if match:
                    start_pos = match.start()
                    # Find end (usually Part 1 or next major section)
                    end_match = re.search(r"Part\s+1\b", full_text[start_pos:], re.IGNORECASE)
                    if end_match:
                        end_pos = start_pos + end_match.start()
                    else:
                        end_pos = min(start_pos + 10000, len(full_text))
                    return full_text[start_pos:end_pos]
        
        # Standard part extraction
        patterns = [
            rf"Part\s+{part_number}\b",
            rf"PART\s+{part_number}\b", 
            rf"Part\s+{part_number}\.",
            rf"Part\s+{part_number}\s*:",
            rf"Part\s+{part_number}\s*[:\-–]",
        ]
        
        start_pos = -1
        for pattern in patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                start_pos = match.start()
                break
        
        if start_pos == -1:
            # If specific part not found, try to estimate position
            estimated_pos = (part_number - 1) * (len(full_text) // 8)
            return full_text[estimated_pos:estimated_pos + 25000]
        
        # Find end position (next part or end of document)
        end_pos = len(full_text)
        
        # Look for next several parts to find the actual next one
        for next_part_num in range(part_number + 1, part_number + 5):
            next_patterns = [
                rf"Part\s+{next_part_num}\b",
                rf"PART\s+{next_part_num}\b",
                rf"Part\s+{next_part_num}\.",
            ]
            
            for pattern in next_patterns:
                match = re.search(pattern, full_text[start_pos:], re.IGNORECASE)
                if match:
                    end_pos = start_pos + match.start()
                    break
            
            if end_pos < len(full_text):
                break
        
        # Extract the part text
        part_text = full_text[start_pos:end_pos]
        
        # Ensure we have enough content
        if len(part_text) < 500 and end_pos < len(full_text):
            # Extend to ensure we capture the full part
            end_pos = min(start_pos + 30000, len(full_text))
            part_text = full_text[start_pos:end_pos]
        
        return part_text
    
    def _generate_form_insights(self, form: USCISForm) -> str:
        """Generate insights about the processed form"""
        insights = []
        
        total_fields = sum(len(p.fields) for p in form.parts.values())
        parent_fields = sum(len([f for f in p.fields if f.is_parent]) for p in form.parts.values())
        subfields = sum(len([f for f in p.fields if f.is_subfield]) for p in form.parts.values())
        questions = sum(len([f for f in p.fields if f.field_type == "question"]) for p in form.parts.values())
        
        insights.append(f"Processed {form.form_number} with {len(form.parts)} parts")
        insights.append(f"Extracted {total_fields} total fields")
        insights.append(f"Created {parent_fields} parent fields with {subfields} subfields")
        insights.append(f"Identified {questions} question fields")
        
        # Check for Part 0
        if 0 in form.parts:
            insights.append("✅ Attorney/Representative section detected")
        
        all_patterns = {}
        for part in form.parts.values():
            for pattern, count in part.field_patterns.items():
                all_patterns[pattern] = all_patterns.get(pattern, 0) + count
        
        if all_patterns:
            insights.append(f"Field patterns: {', '.join(all_patterns.keys())}")
        
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
        st.markdown(f"**{icon} {field.number}. {field.label}**")
        
        if field.field_pattern or field.ai_reasoning:
            with st.expander("🤖 AI Analysis"):
                if field.field_pattern:
                    st.code(f"Pattern: {field.field_pattern}")
                if field.ai_reasoning:
                    st.markdown(f'<div class="ai-analysis">{field.ai_reasoning}</div>', 
                               unsafe_allow_html=True)
    
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
    """Show universal field mapping dialog with smart suggestions"""
    st.markdown("---")
    st.markdown("### 🎯 Map Field to Database Schema")
    
    # Smart mapping suggestions based on field context
    suggestions = get_smart_mapping_suggestions(field)
    
    if suggestions:
        st.info(f"💡 Suggested mappings based on field analysis:")
        for suggestion in suggestions[:3]:
            st.caption(f"• {suggestion}")
    
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
        st.info(f"💡 Pattern detected: '{field.field_pattern}'")
    
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

def get_smart_mapping_suggestions(field: USCISField) -> List[str]:
    """Get smart mapping suggestions based on field context"""
    suggestions = []
    label_lower = field.label.lower()
    
    # Part 0 = Attorney mapping
    if field.part_number == 0:
        if "bar number" in label_lower:
            suggestions.append("attorney.attorneyBarNumber")
        elif "g-28" in label_lower or "g28" in label_lower:
            suggestions.append("attorney.attorneyG28Attached")
        elif "account number" in label_lower:
            suggestions.append("attorney.attorneyUSCISNumber")
        elif "name" in label_lower:
            if field.subfield_letter == "a":
                suggestions.append("attorney.attorneyLastName")
            elif field.subfield_letter == "b":
                suggestions.append("attorney.attorneyFirstName")
            elif field.subfield_letter == "c":
                suggestions.append("attorney.attorneyMiddleName")
    
    # Part with "Information About You" = Beneficiary mapping
    elif field.part_number == 1:  # Often Part 1
        form_part = st.session_state.get('form', USCISForm()).parts.get(field.part_number)
        if form_part and "information about you" in form_part.title.lower():
            # This is beneficiary section
            if "last name" in label_lower or field.subfield_letter == "a":
                suggestions.append("beneficiary.beneficiaryLastName")
            elif "first name" in label_lower or field.subfield_letter == "b":
                suggestions.append("beneficiary.beneficiaryFirstName")
            elif "middle name" in label_lower or field.subfield_letter == "c":
                suggestions.append("beneficiary.beneficiaryMiddleName")
            elif "alien number" in label_lower or "a-number" in label_lower:
                suggestions.append("beneficiary.beneficiaryAlienNumber")
            elif "date of birth" in label_lower:
                suggestions.append("beneficiary.beneficiaryDateOfBirth")
            elif "country of birth" in label_lower:
                suggestions.append("beneficiary.beneficiaryCountryOfBirth")
    
    # Generic field mappings
    if "ssn" in label_lower or "social security" in label_lower:
        suggestions.append("beneficiary.beneficiarySSN")
    elif "email" in label_lower:
        suggestions.append("beneficiary.beneficiaryEmail")
    elif "phone" in label_lower:
        if "mobile" in label_lower:
            suggestions.append("beneficiary.beneficiaryMobilePhone")
        else:
            suggestions.append("beneficiary.beneficiaryDaytimePhone")
    
    return suggestions

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
        <h1>🤖 Universal USCIS Reader - AI Agent</h1>
        <p>Intelligent extraction with Part 0 detection and beneficiary mapping</p>
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
            <strong>✅ Universal Claude Agent Active</strong><br>
            Ready to process any USCIS form with intelligent field analysis.
        </div>
        """, unsafe_allow_html=True)
    else:
        st.error("❌ Claude API not configured. Please add ANTHROPIC_API_KEY to your Streamlit secrets.")
        st.stop()
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 📊 Form Analysis")
        
        if st.session_state.form:
            form = st.session_state.form
            st.success(f"📄 {form.form_number}")
            st.info(f"📖 {form.title}")
            if form.form_category:
                st.info(f"🏷️ {form.form_category.title()}")
            
            st.metric("Parts", len(form.parts))
            
            # Check for Part 0
            if 0 in form.parts:
                st.success("✅ Attorney Section Detected (Part 0)")
            
            total_fields = sum(len(p.fields) for p in form.parts.values())
            mapped_fields = sum(1 for p in form.parts.values() 
                              for f in p.fields if f.is_mapped)
            quest_fields = sum(1 for p in form.parts.values() 
                             for f in p.fields if f.in_questionnaire)
            
            st.metric("Total Fields", total_fields)
            st.metric("Mapped Fields", mapped_fields)
            st.metric("Questionnaire Fields", quest_fields)
            
            if form.processing_time:
                st.metric("Processing Time", f"{form.processing_time:.1f}s")
            
            # Verification Status
            if form.extraction_verified:
                verification_score = form.verification_report.get("overall_completeness", 0)
                if verification_score >= 0.9:
                    st.success(f"✅ Verified: {verification_score:.1%}")
                elif verification_score >= 0.75:
                    st.warning(f"⚠️ Verified: {verification_score:.1%}")
                else:
                    st.error(f"🔍 Verified: {verification_score:.1%}")
                
                # Show verification details
                with st.expander("🔍 Verification Details"):
                    parts_verified = form.verification_report.get("parts_verified", {})
                    for part_num, part_data in parts_verified.items():
                        score = part_data.get("completeness_score", 0)
                        quality = part_data.get("extraction_quality", "unknown")
                        st.write(f"Part {part_num}: {score:.1%} ({quality})")
                    
                    recommendations = form.verification_report.get("recommendations", [])
                    if recommendations:
                        st.markdown("**Recommendations:**")
                        for rec in recommendations:
                            st.caption(rec)
            else:
                st.info("🔄 Not verified")
            
            if form.ai_summary:
                st.markdown("### 🧠 AI Insights")
                st.info(form.ai_summary)
        
        if st.button("🔄 Reset", use_container_width=True):
            st.session_state.clear()
            st.rerun()
    
    # Main tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📤 Upload & Process", "🗂️ Field Mapping", "📝 Questionnaire", "💾 Export"])
    
    with tab1:
        st.markdown("### 📤 Upload Any USCIS Form for Universal AI Analysis")
        
        uploaded_file = st.file_uploader("Choose USCIS PDF file", type=['pdf'])
        
        if uploaded_file:
            if st.button("🚀 Process with Universal AI Agent", type="primary", use_container_width=True):
                form = st.session_state.processor.process_pdf(uploaded_file)
                
                if form:
                    st.session_state.form = form
                    st.success(f"✅ Successfully processed {form.form_number}: {form.title}")
                    
                    st.markdown("### 📋 Universal AI Analysis Results")
                    
                    for part_num, part in sorted(form.parts.items()):
                        parent_fields = len([f for f in part.fields if f.is_parent])
                        subfields = len([f for f in part.fields if f.is_subfield])
                        questions = len([f for f in part.fields if f.field_type == "question"])
                        choices = len([f for f in part.fields if f.is_choice])
                        regular_fields = len([f for f in part.fields if not f.is_parent and not f.is_subfield and not f.is_choice])
                        
                        # Special highlighting for Part 0
                        if part_num == 0:
                            st.warning(f"""
                            **Part {part_num}: {part.title}** ⚖️ ATTORNEY SECTION
                            📁 Parent fields: {parent_fields} | 
                            ↳ Subfields: {subfields} | 
                            ❓ Questions: {questions} | 
                            ☑️ Choices: {choices} | 
                            📝 Regular fields: {regular_fields}
                            **Total: {len(part.fields)} fields**
                            """)
                        else:
                            st.info(f"""
                            **Part {part_num}: {part.title}**
                            📁 Parent fields: {parent_fields} | 
                            ↳ Subfields: {subfields} | 
                            ❓ Questions: {questions} | 
                            ☑️ Choices: {choices} | 
                            📝 Regular fields: {regular_fields}
                            **Total: {len(part.fields)} fields**
                            """)
                        
                        if part.field_patterns:
                            patterns = ", ".join(f"{k}({v})" for k, v in part.field_patterns.items())
                            st.caption(f"🔍 Patterns detected: {patterns}")
                else:
                    st.error("❌ Failed to process form")
    
    with tab2:
        if st.session_state.form:
            st.markdown("### 🗂️ Universal Field Mapping")
            
            form = st.session_state.form
            
            part_numbers = sorted(form.parts.keys())
            selected_part = st.selectbox(
                "Select Part to Map",
                part_numbers,
                format_func=lambda x: f"Part {x}: {form.parts[x].title}"
            )
            
            if selected_part:
                part = form.parts[selected_part]
                
                # Special note for Part 0
                if selected_part == 0:
                    st.warning("⚖️ **Attorney/Representative Section** - Fields will auto-map to attorney schema")
                
                # Special note for "Information About You"
                if "information about you" in part.title.lower():
                    st.info("👤 **Information About You** - Fields will auto-map to beneficiary schema")
                
                st.markdown(f"#### Part {part.number}: {part.title}")
                
                displayed = set()
                for field in sorted(part.fields, key=lambda f: st.session_state.processor.agent._get_sort_key(f.number)):
                    if field.number not in displayed:
                        if field.is_parent or not field.is_subfield:
                            display_universal_field(field, f"map_p{part.number}")
                            displayed.add(field.number)
                            
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
            st.markdown("### 💾 Universal Export Options")
            
            form = st.session_state.form
            form_info = {
                "form_number": form.form_number,
                "title": form.title,
                "form_category": form.form_category
            }
            
            for part_num, part in sorted(form.parts.items()):
                st.markdown(f'<div class="export-section">', unsafe_allow_html=True)
                
                # Special highlighting for Part 0
                if part_num == 0:
                    st.markdown(f"#### Part {part_num}: {part.title} ⚖️")
                else:
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
            if st.button("📥 Download Complete Form Data", type="primary", use_container_width=True):
                full_export = {
                    "form_info": {
                        "form_number": form.form_number,
                        "title": form.title,
                        "edition_date": form.edition_date,
                        "form_category": form.form_category,
                        "processing_time": form.processing_time,
                        "ai_summary": form.ai_summary,
                        "extraction_verified": form.extraction_verified,
                        "verification_score": form.verification_report.get("overall_completeness", 0) if form.verification_report else 0
                    },
                    "parts": {
                        str(part_num): {
                            "title": part.title,
                            "field_patterns": part.field_patterns,
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
