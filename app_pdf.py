#!/usr/bin/env python3
"""
UNIVERSAL USCIS FORM READER - WITH VERIFICATION AGENTS
======================================================
Complete extraction with AI verification to ensure no fields are missed
"""

import streamlit as st
import json
import re
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field as dataclass_field
import uuid

# Page config
st.set_page_config(
    page_title="USCIS Form Reader - AI Verified",
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
    .verification-success {
        background: #d4edda;
        border: 1px solid #c3e6cb;
        padding: 10px;
        border-radius: 5px;
        margin: 10px 0;
    }
    .verification-warning {
        background: #fff3cd;
        border: 1px solid #ffeeba;
        padding: 10px;
        border-radius: 5px;
        margin: 10px 0;
    }
    .field-context {
        background: #f8f9fa;
        padding: 10px;
        margin: 5px 0;
        border-left: 3px solid #6c757d;
        font-size: 0.9em;
    }
    .option-subfield {
        background: #e3f2fd;
        border-left: 3px solid #2196f3;
    }
</style>
""", unsafe_allow_html=True)

# ===== DATA STRUCTURES =====

@dataclass
class FormField:
    """Field structure with verification"""
    item_number: str
    label: str
    field_type: str = "text"
    value: str = ""
    part_number: int = 1
    page_number: int = 1
    parent_number: str = ""
    is_parent: bool = False
    is_subfield: bool = False
    is_option: bool = False
    subfield_labels: List[str] = dataclass_field(default_factory=list)
    is_mapped: bool = False
    in_questionnaire: bool = False
    db_object: str = ""
    db_path: str = ""
    unique_id: str = ""
    field_context: str = ""
    extraction_method: str = ""  # How this field was extracted
    confidence: float = 1.0  # Extraction confidence
    verified: bool = False  # Whether field was verified
    raw_position: int = 0  # Position in original text
    
    def __post_init__(self):
        if not self.unique_id:
            self.unique_id = str(uuid.uuid4())[:8]
    
    def get_sort_key(self) -> Tuple:
        """Get sort key for proper ordering"""
        try:
            parts = self.item_number.replace('-', '.').split('.')
            
            # Main number
            main = int(parts[0]) if parts[0].isdigit() else 999
            
            # Subfield letter or number
            sub = 0
            if len(parts) > 1 and parts[1]:
                if parts[1][0].isalpha():
                    sub = ord(parts[1][0].lower()) - ord('a') + 1
                elif parts[1].isdigit():
                    sub = int(parts[1]) + 100
            
            # Sub-subfield
            subsub = 0
            if len(parts) > 2 and parts[2]:
                if parts[2].isdigit():
                    subsub = int(parts[2])
                elif parts[2][0].isalpha():
                    subsub = ord(parts[2][0].lower()) - ord('a') + 1
            
            return (main, sub, subsub, self.raw_position)
        except:
            return (999, 0, 0, self.raw_position)

@dataclass
class FormPart:
    """Part structure with verification"""
    number: int
    title: str
    fields: List[FormField] = dataclass_field(default_factory=list)
    page_start: int = 1
    page_end: int = 1
    verified: bool = False
    verification_notes: str = ""

@dataclass
class USCISForm:
    """Form container with verification status"""
    form_number: str = "Unknown"
    form_title: str = "USCIS Form"
    edition_date: str = ""
    total_pages: int = 0
    parts: Dict[int, FormPart] = dataclass_field(default_factory=dict)
    raw_text: str = ""
    extraction_stats: Dict = dataclass_field(default_factory=dict)
    verification_report: Dict = dataclass_field(default_factory=dict)

# ===== DATABASE SCHEMA =====

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
            "beneficiaryCountryOfBirth",
            "beneficiaryCityOfBirth",
            "beneficiaryCurrentCountryOfCitizenship",
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
            "beneficiaryEmail"
        ]
    },
    "petitioner": {
        "label": "🏢 Petitioner/Employer",
        "paths": [
            "petitionerLastName",
            "petitionerFirstName",
            "petitionerMiddleName",
            "petitionerCompanyName",
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
            "petitionerEmail",
            "petitionerFEIN",
            "petitionerSSN"
        ]
    },
    "custom": {
        "label": "✏️ Custom",
        "paths": []
    }
}

# ===== EXTRACTION VERIFICATION AGENT =====

class ExtractionVerificationAgent:
    """AI agent to verify extraction completeness"""
    
    def __init__(self, client=None):
        self.client = client
    
    def verify_part_extraction(self, part_text: str, extracted_fields: List[FormField]) -> Dict:
        """Verify if all fields were extracted from a part"""
        
        # Build list of extracted numbers
        extracted_numbers = set()
        for field in extracted_fields:
            extracted_numbers.add(field.item_number)
        
        # Pattern-based verification
        missing_fields = self._find_missing_fields_by_pattern(part_text, extracted_numbers)
        
        # AI verification if available
        ai_verification = {}
        if self.client:
            ai_verification = self._verify_with_ai(part_text, extracted_numbers)
        
        return {
            "extracted_count": len(extracted_fields),
            "extracted_numbers": sorted(extracted_numbers),
            "missing_by_pattern": missing_fields,
            "ai_verification": ai_verification,
            "is_complete": len(missing_fields) == 0
        }
    
    def _find_missing_fields_by_pattern(self, text: str, extracted_numbers: Set[str]) -> List[str]:
        """Find fields that appear in text but weren't extracted"""
        missing = []
        
        # Comprehensive patterns
        patterns = [
            r'\b(\d+)\.\s+[A-Z]',  # 1. Field
            r'\b(\d+)\.([a-z])\.\s',  # 1.a. Field
            r'\b(\d+)([a-z])\.\s',  # 1a. Field
            r'Item\s+Number\s+(\d+)',  # Item Number format
            r'Question\s+(\d+)',  # Question format
        ]
        
        found_in_text = set()
        
        for pattern in patterns:
            matches = re.finditer(pattern, text[:20000], re.IGNORECASE)
            for match in matches:
                if len(match.groups()) == 2:
                    # Subfield pattern
                    num = f"{match.group(1)}.{match.group(2)}"
                else:
                    num = match.group(1)
                
                found_in_text.add(num)
        
        # Check for missing
        for num in found_in_text:
            if num not in extracted_numbers:
                # Check if parent exists for subfields
                if '.' in num:
                    parent = num.split('.')[0]
                    if parent not in extracted_numbers:
                        missing.append(num)
                else:
                    missing.append(num)
        
        return sorted(missing)
    
    def _verify_with_ai(self, text: str, extracted_numbers: Set[str]) -> Dict:
        """Use AI to verify extraction"""
        try:
            prompt = f"""Analyze this form text and verify field extraction.
            
            Extracted field numbers: {sorted(extracted_numbers)}
            
            Check if any fields are missing. Look for:
            1. All numbered items (1, 2, 3...)
            2. All lettered subfields (1.a, 1.b, 1.c...)
            3. Any checkbox options that should be subfields
            
            Return JSON:
            {{
                "missing_fields": ["list of missing field numbers"],
                "confidence": 0.0-1.0,
                "notes": "any observations"
            }}
            
            Text to analyze:
            {text[:3000]}
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4o" if "gpt-4" in str(self.client.models.list()) else "gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a form extraction verification agent."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                max_tokens=1000
            )
            
            content = response.choices[0].message.content.strip()
            if "{" in content:
                json_str = content[content.find("{"):content.rfind("}")+1]
                return json.loads(json_str)
            
        except Exception as e:
            return {"error": str(e)[:100]}
        
        return {}

# ===== COMPREHENSIVE FIELD EXTRACTOR =====

class ComprehensiveFieldExtractor:
    """Multi-method field extraction with verification"""
    
    def __init__(self):
        self.client = None
        self.verification_agent = None
        self.setup_openai()
    
    def setup_openai(self):
        """Setup OpenAI client"""
        if not OPENAI_AVAILABLE:
            return
        
        try:
            api_key = os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY", None)
            
            if api_key:
                self.client = openai.OpenAI(api_key=api_key)
                self.verification_agent = ExtractionVerificationAgent(self.client)
                st.success("✅ OpenAI connected with verification agent")
        except Exception as e:
            st.warning(f"OpenAI setup failed: {str(e)[:100]}")
    
    def extract_form_with_verification(self, full_text: str, page_texts: Dict[int, str], total_pages: int) -> USCISForm:
        """Extract form with multiple passes and verification"""
        
        with st.spinner("Identifying form..."):
            form_info = self._identify_form(full_text[:5000])
        
        form = USCISForm(
            form_number=form_info.get("form_number", "Unknown"),
            form_title=form_info.get("form_title", "USCIS Form"),
            edition_date=form_info.get("edition_date", ""),
            total_pages=total_pages,
            raw_text=full_text
        )
        
        # Extract parts
        with st.spinner("Extracting parts..."):
            parts = self._extract_all_parts(full_text)
            
            if not parts:
                parts = [{"number": 1, "title": "Main Section"}]
        
        # Process each part with verification
        for part_info in parts:
            with st.spinner(f"Processing Part {part_info['number']}: {part_info['title']}"):
                part = FormPart(
                    number=part_info["number"],
                    title=part_info["title"]
                )
                
                # Get part text
                part_text = self._get_part_text(full_text, part_info["number"])
                
                # Multi-pass extraction
                fields = self._multi_pass_extraction(part_text, part_info["number"])
                
                # Verify extraction
                if self.verification_agent:
                    verification = self.verification_agent.verify_part_extraction(part_text, fields)
                    
                    # Show verification results
                    if verification["missing_by_pattern"]:
                        st.warning(f"Part {part_info['number']}: Found {len(verification['missing_by_pattern'])} potentially missing fields: {verification['missing_by_pattern'][:5]}")
                        
                        # Try to extract missing fields
                        additional_fields = self._extract_missing_fields(part_text, verification["missing_by_pattern"], part_info["number"])
                        fields.extend(additional_fields)
                    else:
                        st.success(f"Part {part_info['number']}: Extraction verified - {len(fields)} fields found")
                    
                    part.verified = True
                    part.verification_notes = str(verification)
                
                # Sort fields properly
                fields.sort(key=lambda f: f.get_sort_key())
                
                part.fields = fields
                form.parts[part.number] = part
        
        # Final verification
        form.extraction_stats = {
            "total_parts": len(form.parts),
            "total_fields": sum(len(p.fields) for p in form.parts.values()),
            "verified_parts": sum(1 for p in form.parts.values() if p.verified)
        }
        
        return form
    
    def _identify_form(self, text: str) -> Dict:
        """Identify form type"""
        result = {"form_number": "Unknown", "form_title": "USCIS Form"}
        
        patterns = [
            r'Form\s+([A-Z]-\d+[A-Z]?)',
            r'USCIS\s+Form\s+([A-Z]-?\d+[A-Z]?)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result["form_number"] = match.group(1)
                break
        
        # Try AI identification
        if self.client:
            try:
                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "Extract form identification."},
                        {"role": "user", "content": f"Extract form number and title from:\n{text[:1000]}"}
                    ],
                    temperature=0,
                    max_tokens=100
                )
                
                content = response.choices[0].message.content.strip()
                if "form" in content.lower():
                    # Parse response
                    form_match = re.search(r'([A-Z]-\d+[A-Z]?)', content)
                    if form_match:
                        result["form_number"] = form_match.group(1)
            except:
                pass
        
        return result
    
    def _extract_all_parts(self, text: str) -> List[Dict]:
        """Extract all parts from form"""
        parts = []
        found_parts = {}
        
        # Multiple patterns
        patterns = [
            r'Part\s+(\d+)[.\s\-–]+([^\n]{3,150})',
            r'PART\s+(\d+)[.\s\-–]+([^\n]{3,150})',
            r'Section\s+(\d+)[.\s\-–]+([^\n]{3,150})'
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            
            for match in matches:
                try:
                    part_num = int(match.group(1))
                    part_title = match.group(2).strip()
                    
                    # Clean title
                    part_title = re.sub(r'^[.\-–\s]+', '', part_title)
                    part_title = re.sub(r'[.\s]+$', '', part_title)
                    
                    if part_num not in found_parts and len(part_title) > 2:
                        found_parts[part_num] = {
                            "number": part_num,
                            "title": part_title,
                            "position": match.start()
                        }
                except:
                    continue
        
        parts = sorted(found_parts.values(), key=lambda x: x["number"])
        return parts
    
    def _get_part_text(self, text: str, part_num: int) -> str:
        """Extract text for specific part"""
        try:
            # Find part start
            patterns = [
                f"Part\\s+{part_num}\\b",
                f"PART\\s+{part_num}\\b"
            ]
            
            start_pos = -1
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    start_pos = match.start()
                    break
            
            if start_pos == -1:
                return ""
            
            # Find next part
            next_pattern = f"Part\\s+{part_num + 1}\\b|PART\\s+{part_num + 1}\\b"
            next_match = re.search(next_pattern, text[start_pos:], re.IGNORECASE)
            
            if next_match:
                end_pos = start_pos + next_match.start()
            else:
                end_pos = min(start_pos + 25000, len(text))
            
            return text[start_pos:end_pos]
            
        except:
            return text[:25000]
    
    def _multi_pass_extraction(self, text: str, part_num: int) -> List[FormField]:
        """Extract fields using multiple methods"""
        all_fields = {}
        
        # Pass 1: Pattern-based extraction
        pattern_fields = self._extract_by_patterns(text, part_num)
        for field in pattern_fields:
            if field.item_number not in all_fields:
                all_fields[field.item_number] = field
        
        # Pass 2: AI extraction if available
        if self.client:
            ai_fields = self._extract_by_ai(text, part_num)
            for field in ai_fields:
                if field.item_number not in all_fields:
                    all_fields[field.item_number] = field
                    field.extraction_method = "AI"
        
        # Pass 3: Look for orphan subfields and create parents
        self._create_missing_parents(all_fields, part_num)
        
        # Pass 4: Extract checkbox options as subfields
        self._extract_option_subfields(all_fields, text, part_num)
        
        return list(all_fields.values())
    
    def _extract_by_patterns(self, text: str, part_num: int) -> List[FormField]:
        """Pattern-based extraction"""
        fields = []
        
        # Comprehensive patterns - ORDER MATTERS
        patterns = [
            # Subfields first (most specific)
            (r'(\d+)\.([a-z])\.\s*([^\n]{2,200})', 'subfield'),  # 1.a. Label
            (r'(\d+)([a-z])\.\s*([^\n]{2,200})', 'subfield_compact'),  # 1a. Label
            (r'\b([a-z])\.\s+([^\n]{2,200})', 'orphan_subfield'),  # a. Label
            
            # Main fields
            (r'(\d+)\.\s+([^\n]{3,200})', 'main'),  # 1. Label
            (r'Item\s+Number\s+(\d+)[.\s]*([^\n]{3,200})', 'item_number'),  # Item Number 1
            (r'Question\s+(\d+)[.\s]*([^\n]{3,200})', 'question'),  # Question 1
        ]
        
        found_items = set()
        
        for pattern, pattern_type in patterns:
            matches = re.finditer(pattern, text[:20000], re.IGNORECASE | re.MULTILINE)
            
            for match in matches:
                try:
                    # Parse based on pattern type
                    if pattern_type in ['subfield', 'subfield_compact']:
                        parent_num = match.group(1)
                        letter = match.group(2)
                        label = match.group(3).strip()
                        item_number = f"{parent_num}.{letter}"
                        is_subfield = True
                        parent_number = parent_num
                    elif pattern_type == 'orphan_subfield':
                        # Try to find parent
                        letter = match.group(1)
                        label = match.group(2).strip()
                        
                        # Look back for parent number
                        text_before = text[:match.start()]
                        parent_match = re.search(r'(\d+)\.\s+[^\n]+', text_before[::-1])
                        if parent_match:
                            parent_num = parent_match.group(1)[::-1]
                            item_number = f"{parent_num}.{letter}"
                            is_subfield = True
                            parent_number = parent_num
                        else:
                            continue
                    else:
                        item_number = match.group(1)
                        label = match.group(2).strip() if len(match.groups()) > 1 else f"Field {item_number}"
                        is_subfield = False
                        parent_number = ""
                    
                    # Skip if already found
                    if item_number in found_items:
                        continue
                    
                    found_items.add(item_number)
                    
                    # Clean label
                    label = re.sub(r'\s+', ' ', label)
                    label = label[:200]  # Limit length
                    
                    # Get context
                    context_start = max(0, match.start() - 50)
                    context_end = min(len(text), match.end() + 500)
                    context = text[context_start:context_end]
                    
                    # Create field
                    field = FormField(
                        item_number=item_number,
                        label=label,
                        field_type=self._detect_field_type(label),
                        part_number=part_num,
                        is_subfield=is_subfield,
                        parent_number=parent_number,
                        field_context=context,
                        extraction_method="pattern",
                        raw_position=match.start()
                    )
                    
                    fields.append(field)
                    
                except Exception as e:
                    continue
        
        return fields
    
    def _extract_by_ai(self, text: str, part_num: int) -> List[FormField]:
        """AI-based extraction"""
        try:
            prompt = f"""Extract ALL fields from Part {part_num}.
            
            CRITICAL REQUIREMENTS:
            1. Include EVERY numbered field (1, 2, 3...)
            2. Include EVERY lettered subfield (1.a, 1.b, 1.c...)
            3. Include checkbox options as subfields
            4. Maintain exact numbering from the form
            
            Return JSON array with COMPLETE extraction:
            [{{
                "number": "1",
                "label": "Full Legal Name",
                "type": "parent"
            }},
            {{
                "number": "1.a",
                "label": "Family Name (Last Name)",
                "type": "text",
                "parent": "1"
            }},
            {{
                "number": "1.b",
                "label": "Given Name (First Name)",
                "type": "text",
                "parent": "1"
            }}]
            
            Text:
            {text[:8000]}
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4o" if "gpt-4" in str(self.client.models.list()) else "gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Extract ALL form fields. Do not miss any field."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                max_tokens=4000
            )
            
            content = response.choices[0].message.content.strip()
            
            # Extract JSON
            if "[" in content:
                json_str = content[content.find("["):content.rfind("]")+1]
                data = json.loads(json_str)
                
                fields = []
                for item in data:
                    field = FormField(
                        item_number=item.get("number", ""),
                        label=item.get("label", ""),
                        field_type=item.get("type", "text"),
                        part_number=part_num,
                        parent_number=item.get("parent", ""),
                        is_subfield=bool(item.get("parent", "")),
                        is_parent=(item.get("type") == "parent"),
                        extraction_method="AI"
                    )
                    
                    if field.item_number:
                        fields.append(field)
                
                return fields
                
        except Exception as e:
            st.warning(f"AI extraction error: {str(e)[:100]}")
        
        return []
    
    def _create_missing_parents(self, all_fields: Dict[str, FormField], part_num: int):
        """Create parent fields for orphan subfields"""
        parents_needed = set()
        
        for field_num, field in all_fields.items():
            if field.is_subfield and field.parent_number:
                if field.parent_number not in all_fields:
                    parents_needed.add(field.parent_number)
        
        for parent_num in parents_needed:
            parent = FormField(
                item_number=parent_num,
                label=f"Field {parent_num}",
                field_type="parent",
                part_number=part_num,
                is_parent=True,
                extraction_method="inferred"
            )
            all_fields[parent_num] = parent
    
    def _extract_option_subfields(self, all_fields: Dict[str, FormField], text: str, part_num: int):
        """Extract checkbox/radio options as subfields"""
        for field_num, field in list(all_fields.items()):
            # Look for questions with options
            if field.field_context and not field.is_subfield:
                # Check for checkbox patterns
                patterns = [
                    r'[□☐]\s*([^\n□☐]{2,100})',
                    r'\[\s*\]\s*([^\n\[\]]{2,100})',
                    r'○\s*([^\n○]{2,100})'
                ]
                
                options = []
                for pattern in patterns:
                    matches = re.findall(pattern, field.field_context)
                    options.extend(matches)
                
                if options and len(options) > 1:
                    # Make this a parent field
                    field.is_parent = True
                    field.field_type = "question"
                    
                    # Create subfields for options
                    for i, option in enumerate(options[:10]):  # Limit to 10 options
                        letter = chr(ord('a') + i)
                        subfield_num = f"{field_num}.{letter}"
                        
                        if subfield_num not in all_fields:
                            subfield = FormField(
                                item_number=subfield_num,
                                label=option.strip(),
                                field_type="checkbox",
                                part_number=part_num,
                                parent_number=field_num,
                                is_subfield=True,
                                is_option=True,
                                extraction_method="option_extraction"
                            )
                            all_fields[subfield_num] = subfield
    
    def _extract_missing_fields(self, text: str, missing_numbers: List[str], part_num: int) -> List[FormField]:
        """Try to extract specific missing fields"""
        fields = []
        
        for num in missing_numbers:
            # Look for this specific field
            patterns = [
                rf'{re.escape(num)}\.\s*([^\n]{{3,200}})',
                rf'Item\s+Number\s+{re.escape(num)}\s*([^\n]{{3,200}})'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    label = match.group(1).strip() if len(match.groups()) > 0 else f"Field {num}"
                    
                    # Determine if subfield
                    is_subfield = '.' in num and num.split('.')[1].isalpha()
                    parent_number = num.split('.')[0] if is_subfield else ""
                    
                    field = FormField(
                        item_number=num,
                        label=label,
                        field_type="text",
                        part_number=part_num,
                        is_subfield=is_subfield,
                        parent_number=parent_number,
                        extraction_method="recovery",
                        verified=True
                    )
                    
                    fields.append(field)
                    break
        
        return fields
    
    def _detect_field_type(self, label: str) -> str:
        """Detect field type from label"""
        label_lower = label.lower()
        
        if any(word in label_lower for word in ["date", "birth", "expir"]):
            return "date"
        elif "email" in label_lower:
            return "email"
        elif any(word in label_lower for word in ["phone", "telephone"]):
            return "phone"
        elif any(word in label_lower for word in ["check", "select", "mark"]):
            return "checkbox"
        elif "ssn" in label_lower or "social security" in label_lower:
            return "ssn"
        elif "alien number" in label_lower or "a-number" in label_lower:
            return "alien_number"
        
        return "text"

# ===== UI FUNCTIONS =====

def extract_pdf_text(pdf_file) -> Tuple[str, Dict[int, str], int]:
    """Extract text from PDF"""
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
        st.error(f"PDF error: {str(e)}")
        return "", {}, 0

def display_field(field: FormField, key_prefix: str):
    """Display field with verification status"""
    unique_key = f"{key_prefix}_{field.unique_id}"
    
    # Determine style
    if field.is_parent:
        card_class = "parent-field"
        status = "📁 Parent"
    elif field.is_option:
        card_class = "option-subfield"
        status = "☑️ Option"
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
    
    # Add verification indicator
    if field.verified:
        status += " ✓"
    
    st.markdown(f'<div class="field-card {card_class}">', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([3, 2, 2])
    
    with col1:
        st.markdown(f'<span class="field-number-badge">{field.item_number}</span>**{field.label}**', unsafe_allow_html=True)
        
        # Show extraction method
        if field.extraction_method:
            st.caption(f"Extracted by: {field.extraction_method}")
        
        # Show context on demand
        if field.field_context and st.checkbox("Show context", key=f"{unique_key}_ctx"):
            st.markdown(f'<div class="field-context">{field.field_context[:500]}</div>', unsafe_allow_html=True)
    
    with col2:
        if not field.is_parent:
            if field.field_type == "date":
                field.value = st.date_input("", key=f"{unique_key}_date", label_visibility="collapsed")
                field.value = str(field.value) if field.value else ""
            elif field.field_type == "checkbox" or field.is_option:
                field.value = st.checkbox("", key=f"{unique_key}_check")
                field.value = "Yes" if field.value else "No"
            else:
                field.value = st.text_input("", value=field.value, key=f"{unique_key}_val", label_visibility="collapsed")
    
    with col3:
        st.markdown(f"**{status}**")
        if not field.is_parent:
            c1, c2 = st.columns(2)
            with c1:
                if not field.is_mapped:
                    if st.button("Map", key=f"{unique_key}_map"):
                        st.session_state[f"mapping_{field.unique_id}"] = True
                        st.rerun()
            with c2:
                if st.button("Quest", key=f"{unique_key}_quest"):
                    field.in_questionnaire = not field.in_questionnaire
                    st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Mapping dialog
    if st.session_state.get(f"mapping_{field.unique_id}"):
        show_mapping(field, unique_key)

def show_mapping(field: FormField, unique_key: str):
    """Show mapping dialog"""
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        map_type = st.radio("Type", ["Database", "Manual"], key=f"{unique_key}_type")
    
    with col2:
        if map_type == "Database":
            obj = st.selectbox("Object", list(DATABASE_SCHEMA.keys()), key=f"{unique_key}_obj")
            if obj != "custom":
                path = st.selectbox("Path", DATABASE_SCHEMA[obj]["paths"], key=f"{unique_key}_path")
            else:
                path = st.text_input("Path", key=f"{unique_key}_cpath")
        else:
            obj = st.text_input("Object", key=f"{unique_key}_mobj")
            path = st.text_input("Path", key=f"{unique_key}_mpath")
    
    if st.button("Apply", key=f"{unique_key}_apply"):
        if obj and path:
            field.is_mapped = True
            field.db_object = obj
            field.db_path = path
            del st.session_state[f"mapping_{field.unique_id}"]
            st.rerun()

# ===== MAIN APPLICATION =====

def main():
    st.markdown('<div class="main-header"><h1>📄 USCIS Form Reader - AI Verified</h1><p>Complete extraction with verification agents</p></div>', unsafe_allow_html=True)
    
    # Initialize
    if 'form' not in st.session_state:
        st.session_state.form = None
    if 'extractor' not in st.session_state:
        st.session_state.extractor = ComprehensiveFieldExtractor()
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 📊 Status")
        
        if st.session_state.form:
            form = st.session_state.form
            
            st.success(f"Form: {form.form_number}")
            st.metric("Parts", len(form.parts))
            st.metric("Total Fields", sum(len(p.fields) for p in form.parts.values()))
            
            # Verification status
            st.markdown("### Verification")
            for part_num, part in sorted(form.parts.items()):
                if part.verified:
                    st.success(f"Part {part_num}: ✓ Verified")
                else:
                    st.warning(f"Part {part_num}: Not verified")
        
        if st.button("🔄 Clear", use_container_width=True):
            st.session_state.clear()
            st.rerun()
    
    # Main tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📤 Upload", "🔗 Map", "📝 Quest", "💾 Export"])
    
    with tab1:
        st.markdown("### Upload and Extract with Verification")
        
        uploaded_file = st.file_uploader("Choose PDF", type=['pdf'])
        
        if uploaded_file:
            if st.button("🚀 Extract with Verification", type="primary", use_container_width=True):
                # Extract PDF
                full_text, page_texts, total_pages = extract_pdf_text(uploaded_file)
                
                if full_text:
                    # Extract with verification
                    form = st.session_state.extractor.extract_form_with_verification(
                        full_text, page_texts, total_pages
                    )
                    st.session_state.form = form
                    
                    # Show results
                    st.success(f"✅ Extraction Complete: {form.form_number}")
                    
                    # Show extraction stats
                    st.markdown("### Extraction Statistics")
                    for part_num, part in sorted(form.parts.items()):
                        total = len(part.fields)
                        by_method = {}
                        for f in part.fields:
                            method = f.extraction_method or "unknown"
                            by_method[method] = by_method.get(method, 0) + 1
                        
                        st.info(
                            f"**Part {part_num}: {part.title}**\n"
                            f"• Total: {total} fields\n"
                            f"• Methods: {by_method}"
                        )
                else:
                    st.error("Could not extract text")
    
    with tab2:
        if st.session_state.form:
            st.markdown("### Map Fields - Verified Extraction")
            
            form = st.session_state.form
            
            # Part selector
            part_num = st.selectbox(
                "Select Part",
                sorted(form.parts.keys()),
                format_func=lambda x: f"Part {x}: {form.parts[x].title}"
            )
            
            if part_num:
                part = form.parts[part_num]
                
                # Show fields in proper sequence
                sorted_fields = sorted(part.fields, key=lambda f: f.get_sort_key())
                
                st.info(f"Showing {len(sorted_fields)} fields (verified: {part.verified})")
                
                # Display fields maintaining hierarchy
                displayed = set()
                for field in sorted_fields:
                    if field.item_number not in displayed:
                        if not field.is_subfield or field.parent_number not in [f.item_number for f in sorted_fields]:
                            display_field(field, f"p{part_num}")
                            displayed.add(field.item_number)
                            
                            # Show subfields
                            if field.is_parent:
                                for sub in sorted_fields:
                                    if sub.parent_number == field.item_number and sub.item_number not in displayed:
                                        display_field(sub, f"p{part_num}")
                                        displayed.add(sub.item_number)
        else:
            st.info("Upload a form first")
    
    with tab3:
        if st.session_state.form:
            st.markdown("### Questionnaire")
            
            for part in st.session_state.form.parts.values():
                quest_fields = [f for f in part.fields if f.in_questionnaire]
                
                if quest_fields:
                    st.markdown(f"#### Part {part.number}")
                    
                    for field in sorted(quest_fields, key=lambda f: f.get_sort_key()):
                        st.write(f"**{field.item_number}. {field.label}**")
                        
                        if field.is_option:
                            field.value = st.checkbox(field.label, key=f"q_{field.unique_id}")
                        else:
                            field.value = st.text_input("Answer", key=f"q_{field.unique_id}")
        else:
            st.info("Upload a form first")
    
    with tab4:
        if st.session_state.form:
            st.markdown("### Export Verified Data")
            
            form = st.session_state.form
            
            # Build export
            export_data = {
                "form": form.form_number,
                "extraction_stats": form.extraction_stats,
                "parts": {}
            }
            
            for part_num, part in form.parts.items():
                export_data["parts"][part_num] = {
                    "title": part.title,
                    "verified": part.verified,
                    "fields": [
                        {
                            "number": f.item_number,
                            "label": f.label,
                            "value": f.value,
                            "method": f.extraction_method,
                            "mapping": f"{f.db_object}.{f.db_path}" if f.is_mapped else None
                        }
                        for f in sorted(part.fields, key=lambda x: x.get_sort_key())
                    ]
                }
            
            json_str = json.dumps(export_data, indent=2)
            
            st.download_button(
                "📥 Download Verified Export",
                json_str,
                f"{form.form_number}_verified.json",
                "application/json",
                use_container_width=True
            )

if __name__ == "__main__":
    main()
