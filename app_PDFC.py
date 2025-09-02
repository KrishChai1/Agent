#!/usr/bin/env python3
"""
UNIVERSAL USCIS FORM READER - MULTI-AGENT SYSTEM
================================================
Advanced extraction with verification agents and proper field hierarchy
"""

import streamlit as st
import json
import re
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field as dataclass_field
import uuid
import hashlib
from anthropic import Anthropic

# Page configuration
st.set_page_config(
    page_title="USCIS Form Reader - Multi-Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        padding: 2rem;
        border-radius: 15px;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .agent-status {
        background: #f8f9fa;
        border-left: 4px solid #007bff;
        padding: 10px;
        margin: 10px 0;
        border-radius: 5px;
    }
    .field-container {
        background: white;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        transition: all 0.3s ease;
    }
    .field-container:hover {
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    .field-parent {
        border-left: 5px solid #1e3c72;
        font-weight: 600;
        background: #f0f4f8;
    }
    .field-subfield {
        border-left: 4px solid #5dade2;
        margin-left: 30px;
        background: #f8f9fa;
    }
    .field-choice {
        border-left: 3px solid #85c1e2;
        margin-left: 60px;
        background: #f0f8ff;
        padding: 8px;
    }
    .field-mapped {
        background: #d4edda !important;
        border-left-color: #28a745 !important;
    }
    .field-questionnaire {
        background: #fff3cd !important;
        border-left-color: #ffc107 !important;
    }
    .field-number {
        display: inline-block;
        background: #1e3c72;
        color: white;
        padding: 3px 10px;
        border-radius: 5px;
        margin-right: 10px;
        font-weight: bold;
        font-size: 0.9em;
    }
    .verification-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.8em;
        margin-left: 5px;
    }
    .verified { background: #d4edda; color: #155724; }
    .unverified { background: #f8d7da; color: #721c24; }
    .extraction-stats {
        background: #e7f3ff;
        padding: 15px;
        border-radius: 10px;
        margin: 15px 0;
        border: 1px solid #b8daff;
    }
</style>
""", unsafe_allow_html=True)

# ===== DATA MODELS =====

@dataclass
class FieldChoice:
    """Choice option for multiple choice fields"""
    letter: str
    text: str
    selected: bool = False
    
    def to_dict(self):
        return {
            "letter": self.letter,
            "text": self.text,
            "selected": self.selected
        }

@dataclass
class FormField:
    """Enhanced field structure with complete metadata"""
    number: str
    label: str
    field_type: str = "text"
    value: Any = ""
    
    # Hierarchy
    part_number: int = 1
    parent_number: Optional[str] = None
    is_parent: bool = False
    is_subfield: bool = False
    choices: List[FieldChoice] = dataclass_field(default_factory=list)
    
    # Mapping
    is_mapped: bool = False
    db_object: str = ""
    db_path: str = ""
    
    # Questionnaire
    in_questionnaire: bool = False
    
    # Metadata
    page_number: int = 1
    context: str = ""
    extraction_method: str = ""
    confidence: float = 1.0
    verified: bool = False
    unique_id: str = ""
    position: int = 0
    
    def __post_init__(self):
        if not self.unique_id:
            # Create unique ID based on part and number
            self.unique_id = hashlib.md5(f"{self.part_number}_{self.number}_{uuid.uuid4()}".encode()).hexdigest()[:12]
    
    def get_sort_key(self) -> Tuple:
        """Get sort key for proper ordering"""
        try:
            parts = self.number.replace('-', '.').split('.')
            main = int(parts[0]) if parts[0].isdigit() else 999
            
            sub = 0
            if len(parts) > 1 and parts[1]:
                if parts[1][0].isalpha():
                    sub = ord(parts[1][0].lower()) - ord('a') + 1
                elif parts[1].isdigit():
                    sub = int(parts[1]) + 100
            
            subsub = 0
            if len(parts) > 2 and parts[2]:
                if parts[2].isdigit():
                    subsub = int(parts[2])
                elif parts[2][0].isalpha():
                    subsub = ord(parts[2][0].lower()) - ord('a') + 1
            
            return (main, sub, subsub, self.position)
        except:
            return (999, 0, 0, self.position)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for export"""
        data = {
            "number": self.number,
            "label": self.label,
            "type": self.field_type,
            "value": str(self.value) if self.value else "",
            "part": self.part_number
        }
        
        if self.choices:
            data["choices"] = [c.to_dict() for c in self.choices]
        
        if self.is_mapped:
            data["mapping"] = {
                "object": self.db_object,
                "path": self.db_path
            }
        
        if self.parent_number:
            data["parent"] = self.parent_number
        
        data["metadata"] = {
            "extraction_method": self.extraction_method,
            "confidence": self.confidence,
            "verified": self.verified
        }
        
        return data

@dataclass
class FormPart:
    """Part/section container"""
    number: int
    title: str
    fields: List[FormField] = dataclass_field(default_factory=list)
    page_start: int = 1
    page_end: int = 1
    verified: bool = False
    extraction_stats: Dict = dataclass_field(default_factory=dict)

@dataclass
class ExtractionResult:
    """Result from extraction agents"""
    success: bool
    form_number: str = ""
    form_title: str = ""
    parts: List[FormPart] = dataclass_field(default_factory=list)
    stats: Dict = dataclass_field(default_factory=dict)
    errors: List[str] = dataclass_field(default_factory=list)

# ===== DATABASE SCHEMA =====

DB_SCHEMA = {
    "beneficiary": {
        "label": "👤 Beneficiary/Applicant",
        "fields": [
            "lastName", "firstName", "middleName", "otherNames",
            "alienNumber", "uscisNumber", "ssn", "dateOfBirth",
            "countryOfBirth", "cityOfBirth", "currentCitizenship",
            "address.street", "address.apt", "address.city",
            "address.state", "address.zip", "address.country",
            "phone.daytime", "phone.mobile", "email"
        ]
    },
    "petitioner": {
        "label": "🏢 Petitioner/Employer",
        "fields": [
            "lastName", "firstName", "middleName", "companyName",
            "fein", "ssn", "address.street", "address.suite",
            "address.city", "address.state", "address.zip",
            "phone", "email", "website"
        ]
    },
    "employment": {
        "label": "💼 Employment",
        "fields": [
            "jobTitle", "socCode", "naicsCode", "wages.from",
            "wages.to", "wages.per", "startDate", "endDate",
            "worksite.address", "worksite.city", "worksite.state"
        ]
    },
    "custom": {
        "label": "✏️ Custom Fields",
        "fields": []
    }
}

# ===== EXTRACTION AGENTS =====

class StructureExtractionAgent:
    """Agent for extracting form structure"""
    
    def __init__(self, client: Optional[Anthropic] = None):
        self.client = client
        self.name = "Structure Agent"
    
    def extract(self, text: str) -> Dict:
        """Extract form structure"""
        st.info(f"🔍 {self.name}: Analyzing form structure...")
        
        if self.client:
            return self._extract_with_ai(text)
        return self._extract_with_patterns(text)
    
    def _extract_with_ai(self, text: str) -> Dict:
        """AI-based structure extraction"""
        prompt = """Analyze this USCIS form and extract its complete structure.

REQUIREMENTS:
1. Identify the form number (e.g., I-129, I-140)
2. Extract all parts with their titles
3. For each part, identify ALL fields including:
   - Main fields (1, 2, 3...)
   - Subfields (1.a, 1.b, 1.c...)
   - Question choices/options

Return JSON:
{
  "form_number": "I-XXX",
  "form_title": "Full Title",
  "edition_date": "MM/DD/YY",
  "parts": [
    {
      "number": 1,
      "title": "Part Title",
      "page_start": 1,
      "page_end": 3
    }
  ]
}

Text:
""" + text[:8000]
        
        try:
            response = self.client.messages.create(
                model="claude-3-opus-20240229",
                max_tokens=2000,
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = response.content[0].text
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            st.warning(f"AI extraction failed: {str(e)[:100]}")
        
        return self._extract_with_patterns(text)
    
    def _extract_with_patterns(self, text: str) -> Dict:
        """Pattern-based structure extraction"""
        result = {
            "form_number": "Unknown",
            "form_title": "USCIS Form",
            "parts": []
        }
        
        # Extract form number
        form_patterns = [
            r'Form\s+([I]-\d+[A-Z]?)',
            r'USCIS\s+Form\s+([I]-\d+[A-Z]?)'
        ]
        
        for pattern in form_patterns:
            match = re.search(pattern, text[:2000], re.IGNORECASE)
            if match:
                result["form_number"] = match.group(1)
                break
        
        # Extract parts
        part_pattern = r'Part\s+(\d+)[.\s\-–]*([^\n]{3,100})'
        matches = re.finditer(part_pattern, text, re.IGNORECASE | re.MULTILINE)
        
        for match in matches:
            try:
                part_num = int(match.group(1))
                title = match.group(2).strip()
                title = re.sub(r'^[.\-–\s]+', '', title)
                
                result["parts"].append({
                    "number": part_num,
                    "title": title,
                    "position": match.start()
                })
            except:
                continue
        
        # Sort by position to maintain order
        result["parts"].sort(key=lambda x: x.get("position", 0))
        
        return result

class FieldExtractionAgent:
    """Agent for extracting fields from parts"""
    
    def __init__(self, client: Optional[Anthropic] = None):
        self.client = client
        self.name = "Field Agent"
    
    def extract_fields(self, text: str, part_number: int) -> List[FormField]:
        """Extract all fields from part text"""
        st.info(f"📝 {self.name}: Extracting fields from Part {part_number}...")
        
        fields = []
        
        # Try AI extraction first
        if self.client:
            ai_fields = self._extract_with_ai(text, part_number)
            fields.extend(ai_fields)
        
        # Pattern extraction as backup/supplement
        pattern_fields = self._extract_with_patterns(text, part_number)
        
        # Merge fields (avoid duplicates)
        existing_numbers = {f.number for f in fields}
        for pf in pattern_fields:
            if pf.number not in existing_numbers:
                fields.append(pf)
        
        # Post-process fields
        fields = self._enhance_fields(fields, text)
        
        return sorted(fields, key=lambda f: f.get_sort_key())
    
    def _extract_with_ai(self, text: str, part_number: int) -> List[FormField]:
        """AI-based field extraction"""
        prompt = f"""Extract ALL fields from Part {part_number} of this USCIS form.

CRITICAL: Include EVERY field with its exact number and label.

For each field, identify:
1. Number (e.g., "1", "1.a", "2")
2. Label (complete text)
3. Type (text, date, checkbox, ssn, etc.)
4. Parent number if it's a subfield
5. Any checkbox/radio options

Return JSON array:
[
  {{
    "number": "1",
    "label": "Full Legal Name",
    "type": "parent",
    "is_parent": true
  }},
  {{
    "number": "1.a",
    "label": "Family Name (Last Name)",
    "type": "text",
    "parent": "1"
  }},
  {{
    "number": "2",
    "label": "Have you ever been arrested?",
    "type": "question",
    "choices": ["Yes", "No"]
  }}
]

Text:
{text[:10000]}"""
        
        try:
            response = self.client.messages.create(
                model="claude-3-opus-20240229",
                max_tokens=4000,
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = response.content[0].text
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            
            if json_match:
                data = json.loads(json_match.group())
                fields = []
                
                for item in data:
                    field = FormField(
                        number=item.get("number", ""),
                        label=item.get("label", ""),
                        field_type=item.get("type", "text"),
                        part_number=part_number,
                        parent_number=item.get("parent"),
                        is_parent=item.get("is_parent", False),
                        extraction_method="AI",
                        confidence=0.9
                    )
                    
                    # Add choices if present
                    if item.get("choices"):
                        for i, choice_text in enumerate(item["choices"]):
                            field.choices.append(FieldChoice(
                                letter=chr(ord('a') + i),
                                text=choice_text
                            ))
                    
                    if field.number:
                        fields.append(field)
                
                return fields
                
        except Exception as e:
            st.warning(f"AI field extraction error: {str(e)[:100]}")
        
        return []
    
    def _extract_with_patterns(self, text: str, part_number: int) -> List[FormField]:
        """Pattern-based field extraction"""
        fields = []
        seen = set()
        
        # Comprehensive patterns
        patterns = [
            # Subfields with letters
            (r'(\d+)\.([a-z])\.?\s+([^\n]{3,200})', 'subfield'),
            # Main numbered fields
            (r'(\d+)\.\s+([^\n]{3,200})', 'main'),
            # Item Number format
            (r'Item\s+Number\s+(\d+)[.\s]*([^\n]{3,200})', 'item'),
            # Orphan subfields
            (r'^([a-z])\.\s+([^\n]{3,200})', 'orphan', re.MULTILINE)
        ]
        
        for pattern, field_type, *flags in patterns:
            regex_flags = re.IGNORECASE | (flags[0] if flags else 0)
            matches = re.finditer(pattern, text[:15000], regex_flags)
            
            for match in matches:
                try:
                    if field_type == 'subfield':
                        number = f"{match.group(1)}.{match.group(2)}"
                        label = match.group(3).strip()
                        parent = match.group(1)
                        is_sub = True
                    elif field_type == 'orphan':
                        # Try to find parent
                        letter = match.group(1)
                        label = match.group(2).strip()
                        
                        # Look for nearest number before this
                        text_before = text[:match.start()]
                        num_match = re.search(r'(\d+)\.\s+[^\n]+', text_before)
                        if num_match:
                            parent = num_match.group(1)
                            number = f"{parent}.{letter}"
                            is_sub = True
                        else:
                            continue
                    else:
                        number = match.group(1)
                        label = match.group(2).strip() if len(match.groups()) > 1 else f"Field {number}"
                        parent = None
                        is_sub = False
                    
                    if number not in seen and len(label) > 2:
                        seen.add(number)
                        
                        # Get context for choice detection
                        context_start = max(0, match.start() - 50)
                        context_end = min(len(text), match.end() + 500)
                        context = text[context_start:context_end]
                        
                        field = FormField(
                            number=number,
                            label=label[:200],
                            field_type=self._detect_field_type(label),
                            part_number=part_number,
                            parent_number=parent,
                            is_subfield=is_sub,
                            context=context,
                            extraction_method="Pattern",
                            position=match.start()
                        )
                        
                        # Extract choices if it's a question
                        choices = self._extract_choices(context)
                        if choices:
                            field.choices = choices
                            field.is_parent = True
                            field.field_type = "question"
                        
                        fields.append(field)
                        
                except Exception as e:
                    continue
        
        return fields
    
    def _extract_choices(self, context: str) -> List[FieldChoice]:
        """Extract checkbox/radio choices from context"""
        choices = []
        
        # Patterns for checkboxes
        patterns = [
            r'[□☐]\s*([^\n□☐]{2,100})',
            r'\[\s*\]\s*([^\n\[\]]{2,100})',
            r'○\s*([^\n○]{2,100})'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, context)
            if matches and len(matches) >= 2:
                for i, text in enumerate(matches[:6]):  # Max 6 choices
                    choices.append(FieldChoice(
                        letter=chr(ord('a') + i),
                        text=text.strip()
                    ))
                break
        
        return choices
    
    def _enhance_fields(self, fields: List[FormField], text: str) -> List[FormField]:
        """Enhance fields with additional metadata"""
        
        # Create parent fields for orphan subfields
        parent_nums = {f.parent_number for f in fields if f.parent_number}
        existing_nums = {f.number for f in fields}
        
        for parent_num in parent_nums:
            if parent_num and parent_num not in existing_nums:
                # Create parent field
                parent_field = FormField(
                    number=parent_num,
                    label=f"Field {parent_num}",
                    field_type="parent",
                    part_number=fields[0].part_number if fields else 1,
                    is_parent=True,
                    extraction_method="Inferred"
                )
                fields.append(parent_field)
        
        # Mark parent fields
        for field in fields:
            # Check if this field has children
            has_children = any(f.parent_number == field.number for f in fields)
            if has_children:
                field.is_parent = True
        
        return fields
    
    def _detect_field_type(self, label: str) -> str:
        """Detect field type from label text"""
        label_lower = label.lower()
        
        type_patterns = {
            "date": ["date", "born", "birth", "expire", "issued"],
            "email": ["email", "e-mail"],
            "phone": ["phone", "telephone", "mobile", "cell"],
            "ssn": ["social security", "ssn"],
            "ein": ["ein", "employer identification", "fein"],
            "alien_number": ["alien number", "a-number", "uscis number"],
            "checkbox": ["select", "check", "mark", "indicate"],
            "address": ["address", "street", "city", "state", "zip"],
            "name": ["name", "given name", "family name", "surname"]
        }
        
        for field_type, keywords in type_patterns.items():
            if any(keyword in label_lower for keyword in keywords):
                return field_type
        
        return "text"

class VerificationAgent:
    """Agent for verifying extraction completeness"""
    
    def __init__(self, client: Optional[Anthropic] = None):
        self.client = client
        self.name = "Verification Agent"
    
    def verify_extraction(self, text: str, fields: List[FormField], part_number: int) -> Dict:
        """Verify if extraction is complete"""
        st.info(f"✅ {self.name}: Verifying Part {part_number} extraction...")
        
        extracted_numbers = {f.number for f in fields}
        
        # Find potentially missing fields
        missing = self._find_missing_by_pattern(text, extracted_numbers)
        
        # AI verification if available
        if self.client:
            ai_result = self._verify_with_ai(text, extracted_numbers)
            missing.extend(ai_result.get("missing", []))
        
        # Remove duplicates
        missing = list(set(missing))
        
        return {
            "total_extracted": len(fields),
            "extracted_numbers": sorted(extracted_numbers),
            "missing_fields": missing,
            "is_complete": len(missing) == 0,
            "confidence": 1.0 if len(missing) == 0 else 0.7
        }
    
    def _find_missing_by_pattern(self, text: str, extracted: Set[str]) -> List[str]:
        """Find potentially missing fields"""
        missing = []
        
        # Look for all numbered patterns
        patterns = [
            r'\b(\d+)\.\s+[A-Z]',
            r'\b(\d+)\.([a-z])\.',
            r'Item\s+Number\s+(\d+)',
        ]
        
        found_in_text = set()
        
        for pattern in patterns:
            matches = re.finditer(pattern, text[:10000], re.IGNORECASE)
            for match in matches:
                if len(match.groups()) == 2:
                    num = f"{match.group(1)}.{match.group(2)}"
                else:
                    num = match.group(1)
                found_in_text.add(num)
        
        # Check what's missing
        for num in found_in_text:
            if num not in extracted:
                missing.append(num)
        
        return missing
    
    def _verify_with_ai(self, text: str, extracted: Set[str]) -> Dict:
        """AI-based verification"""
        if not self.client:
            return {}
        
        prompt = f"""Verify field extraction completeness.

Extracted fields: {sorted(extracted)}

Check the text for any missing numbered fields (1, 2, 3...) or subfields (1.a, 1.b...).

Return JSON:
{{
  "missing": ["list of missing field numbers"],
  "confidence": 0.0-1.0
}}

Text to verify:
{text[:5000]}"""
        
        try:
            response = self.client.messages.create(
                model="claude-3-opus-20240229",
                max_tokens=500,
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = response.content[0].text
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
                
        except:
            pass
        
        return {}

# ===== MASTER ORCHESTRATOR =====

class FormExtractionOrchestrator:
    """Orchestrates all agents for complete extraction"""
    
    def __init__(self):
        self.client = None
        self.initialize_client()
        
        # Initialize agents
        self.structure_agent = StructureExtractionAgent(self.client)
        self.field_agent = FieldExtractionAgent(self.client)
        self.verification_agent = VerificationAgent(self.client)
    
    def initialize_client(self):
        """Initialize Anthropic client"""
        try:
            api_key = st.secrets.get("ANTHROPIC_API_KEY", None)
            if api_key:
                self.client = Anthropic(api_key=api_key)
                st.success("✅ Claude Opus initialized")
        except Exception as e:
            st.warning(f"⚠️ Claude unavailable: {str(e)[:50]}")
    
    def extract_form(self, text: str, page_count: int) -> ExtractionResult:
        """Complete form extraction pipeline"""
        
        result = ExtractionResult(success=False)
        
        try:
            # Step 1: Extract structure
            structure = self.structure_agent.extract(text)
            result.form_number = structure.get("form_number", "Unknown")
            result.form_title = structure.get("form_title", "USCIS Form")
            
            # Step 2: Process each part
            for part_info in structure.get("parts", []):
                part_text = self._get_part_text(text, part_info["number"])
                
                # Extract fields
                fields = self.field_agent.extract_fields(part_text, part_info["number"])
                
                # Verify extraction
                verification = self.verification_agent.verify_extraction(
                    part_text, fields, part_info["number"]
                )
                
                # Create part object
                part = FormPart(
                    number=part_info["number"],
                    title=part_info["title"],
                    fields=fields,
                    verified=verification["is_complete"],
                    extraction_stats=verification
                )
                
                result.parts.append(part)
            
            # If no parts found, treat as single section
            if not result.parts:
                fields = self.field_agent.extract_fields(text, 1)
                part = FormPart(
                    number=1,
                    title="Main Section",
                    fields=fields
                )
                result.parts.append(part)
            
            # Calculate stats
            result.stats = {
                "total_parts": len(result.parts),
                "total_fields": sum(len(p.fields) for p in result.parts),
                "verified_parts": sum(1 for p in result.parts if p.verified),
                "extraction_methods": self._count_methods(result.parts)
            }
            
            result.success = True
            
        except Exception as e:
            result.errors.append(str(e))
            st.error(f"Extraction error: {str(e)[:100]}")
        
        return result
    
    def _get_part_text(self, text: str, part_number: int) -> str:
        """Extract text for specific part"""
        patterns = [
            f"Part\\s+{part_number}\\b",
            f"PART\\s+{part_number}\\b"
        ]
        
        start_pos = -1
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                start_pos = match.start()
                break
        
        if start_pos == -1:
            return text[:15000]  # Return beginning if part not found
        
        # Find next part
        next_pattern = f"Part\\s+{part_number + 1}\\b"
        next_match = re.search(next_pattern, text[start_pos:], re.IGNORECASE)
        
        if next_match:
            end_pos = start_pos + next_match.start()
        else:
            end_pos = min(start_pos + 20000, len(text))
        
        return text[start_pos:end_pos]
    
    def _count_methods(self, parts: List[FormPart]) -> Dict:
        """Count extraction methods used"""
        methods = {}
        for part in parts:
            for field in part.fields:
                method = field.extraction_method or "Unknown"
                methods[method] = methods.get(method, 0) + 1
        return methods

# ===== PDF PROCESSING =====

def extract_pdf_text(pdf_file) -> Tuple[str, int]:
    """Extract text from PDF with fallback methods"""
    try:
        # Try PyMuPDF first
        try:
            import fitz
            pdf_file.seek(0)
            pdf_bytes = pdf_file.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            full_text = ""
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                full_text += f"\n\n=== PAGE {page_num + 1} ===\n{text}"
            
            page_count = len(doc)
            doc.close()
            return full_text, page_count
            
        except ImportError:
            # Fallback to PyPDF2
            import PyPDF2
            pdf_file.seek(0)
            reader = PyPDF2.PdfReader(pdf_file)
            
            full_text = ""
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                full_text += f"\n\n=== PAGE {i + 1} ===\n{text}"
            
            return full_text, len(reader.pages)
            
    except Exception as e:
        st.error(f"PDF extraction failed: {str(e)}")
        return "", 0

# ===== UI COMPONENTS =====

def render_field(field: FormField):
    """Render single field with controls"""
    
    # Generate unique key using field's unique_id
    base_key = field.unique_id
    
    # Determine CSS classes
    css_class = "field-container"
    if field.is_parent:
        css_class += " field-parent"
    elif field.is_subfield:
        css_class += " field-subfield"
    
    if field.is_mapped:
        css_class += " field-mapped"
    elif field.in_questionnaire:
        css_class += " field-questionnaire"
    
    with st.container():
        st.markdown(f'<div class="{css_class}">', unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([4, 2, 2])
        
        with col1:
            # Field info
            verification_badge = ""
            if field.verified:
                verification_badge = '<span class="verification-badge verified">✓ Verified</span>'
            
            st.markdown(
                f'<span class="field-number">{field.number}</span>'
                f'<strong>{field.label}</strong>'
                f'{verification_badge}',
                unsafe_allow_html=True
            )
            
            # Show choices for questions
            if field.choices:
                for choice in field.choices:
                    choice.selected = st.checkbox(
                        f"{choice.letter}. {choice.text}",
                        value=choice.selected,
                        key=f"{base_key}_choice_{choice.letter}"
                    )
        
        with col2:
            # Value input
            if not field.is_parent and not field.choices:
                if field.field_type == "date":
                    value = st.date_input(
                        "Value",
                        key=f"{base_key}_value",
                        label_visibility="collapsed"
                    )
                    field.value = str(value) if value else ""
                elif field.field_type == "checkbox":
                    field.value = st.checkbox(
                        "Selected",
                        key=f"{base_key}_value"
                    )
                else:
                    field.value = st.text_input(
                        "Value",
                        value=field.value or "",
                        key=f"{base_key}_value",
                        label_visibility="collapsed"
                    )
        
        with col3:
            # Actions
            col3a, col3b = st.columns(2)
            
            with col3a:
                if not field.is_mapped:
                    if st.button("Map", key=f"{base_key}_map_btn"):
                        st.session_state[f"map_{base_key}"] = True
                else:
                    st.success(f"→ {field.db_object}")
            
            with col3b:
                btn_label = "Quest +" if not field.in_questionnaire else "Quest ✓"
                if st.button(btn_label, key=f"{base_key}_quest_btn"):
                    field.in_questionnaire = not field.in_questionnaire
                    st.rerun()
        
        # Mapping dialog
        if st.session_state.get(f"map_{base_key}"):
            render_mapping_dialog(field)
        
        st.markdown('</div>', unsafe_allow_html=True)

def render_mapping_dialog(field: FormField):
    """Render mapping configuration"""
    base_key = field.unique_id
    
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        obj = st.selectbox(
            "Database Object",
            [""] + list(DB_SCHEMA.keys()),
            key=f"{base_key}_map_obj"
        )
    
    with col2:
        if obj and obj != "custom":
            path = st.selectbox(
                "Field Path",
                [""] + DB_SCHEMA[obj]["fields"],
                key=f"{base_key}_map_path"
            )
        else:
            path = st.text_input(
                "Custom Path",
                key=f"{base_key}_map_custom"
            )
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Apply", key=f"{base_key}_map_apply"):
            if obj and path:
                field.is_mapped = True
                field.db_object = obj
                field.db_path = path
                del st.session_state[f"map_{base_key}"]
                st.rerun()
    
    with col2:
        if st.button("Cancel", key=f"{base_key}_map_cancel"):
            del st.session_state[f"map_{base_key}"]
            st.rerun()

# ===== MAIN APPLICATION =====

def main():
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>🤖 USCIS Form Reader - Multi-Agent System</h1>
        <p>Intelligent extraction with verification agents</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize session state
    if 'extraction_result' not in st.session_state:
        st.session_state.extraction_result = None
    if 'orchestrator' not in st.session_state:
        st.session_state.orchestrator = FormExtractionOrchestrator()
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 📊 Extraction Dashboard")
        
        if st.session_state.extraction_result:
            result = st.session_state.extraction_result
            
            if result.success:
                st.success(f"Form: {result.form_number}")
                st.metric("Parts", len(result.parts))
                st.metric("Fields", result.stats['total_fields'])
                st.metric("Verified", f"{result.stats['verified_parts']}/{len(result.parts)}")
                
                # Extraction methods
                st.markdown("### Extraction Methods")
                for method, count in result.stats.get('extraction_methods', {}).items():
                    st.write(f"• {method}: {count}")
        
        st.markdown("---")
        if st.button("🔄 Reset", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    
    # Main tabs
    tabs = st.tabs([
        "📤 Upload",
        "🔗 Map Fields",
        "📝 Questionnaire",
        "💾 Export"
    ])
    
    # Upload tab
    with tabs[0]:
        render_upload_tab()
    
    # Map Fields tab
    with tabs[1]:
        render_mapping_tab()
    
    # Questionnaire tab
    with tabs[2]:
        render_questionnaire_tab()
    
    # Export tab
    with tabs[3]:
        render_export_tab()

def render_upload_tab():
    """Upload and extraction tab"""
    st.markdown("### Upload USCIS Form")
    
    uploaded_file = st.file_uploader(
        "Choose PDF file",
        type=['pdf'],
        help="Upload any USCIS form"
    )
    
    if uploaded_file:
        st.info(f"📄 {uploaded_file.name}")
        
        if st.button("🚀 Extract with Multi-Agent System", type="primary"):
            with st.spinner("Extracting..."):
                # Extract PDF text
                text, page_count = extract_pdf_text(uploaded_file)
                
                if text:
                    # Run extraction pipeline
                    result = st.session_state.orchestrator.extract_form(text, page_count)
                    
                    if result.success:
                        st.session_state.extraction_result = result
                        st.success(f"✅ Extracted {result.stats['total_fields']} fields from {len(result.parts)} parts")
                        
                        # Show summary
                        with st.expander("Extraction Summary"):
                            for part in result.parts:
                                status = "✅" if part.verified else "⚠️"
                                st.write(f"{status} **Part {part.number}: {part.title}**")
                                st.write(f"  • Fields: {len(part.fields)}")
                                if part.extraction_stats:
                                    missing = part.extraction_stats.get('missing_fields', [])
                                    if missing:
                                        st.warning(f"  • Potentially missing: {missing[:3]}")
                    else:
                        st.error("Extraction failed")
                else:
                    st.error("Could not read PDF")

def render_mapping_tab():
    """Field mapping tab"""
    if not st.session_state.extraction_result:
        st.info("👆 Upload and extract a form first")
        return
    
    result = st.session_state.extraction_result
    
    st.markdown("### Map Form Fields")
    
    # Part selector
    part_options = {
        p.number: f"Part {p.number}: {p.title}"
        for p in result.parts
    }
    
    selected_part_num = st.selectbox(
        "Select Part",
        options=list(part_options.keys()),
        format_func=lambda x: part_options[x],
        key="mapping_part_selector"
    )
    
    if selected_part_num is not None:
        part = next(p for p in result.parts if p.number == selected_part_num)
        
        # Stats
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Fields", len(part.fields))
        with col2:
            mapped = sum(1 for f in part.fields if f.is_mapped)
            st.metric("Mapped", mapped)
        with col3:
            in_quest = sum(1 for f in part.fields if f.in_questionnaire)
            st.metric("In Questionnaire", in_quest)
        
        # Display fields hierarchically
        st.markdown("---")
        
        # Group fields by parent
        parent_fields = {}
        orphan_fields = []
        
        for field in sorted(part.fields, key=lambda f: f.get_sort_key()):
            if field.is_parent or not field.parent_number:
                parent_fields[field.number] = {
                    'field': field,
                    'children': []
                }
            
        for field in part.fields:
            if field.parent_number and field.parent_number in parent_fields:
                parent_fields[field.parent_number]['children'].append(field)
            elif field.parent_number:
                orphan_fields.append(field)
        
        # Render hierarchically
        for parent_num in sorted(parent_fields.keys()):
            data = parent_fields[parent_num]
            render_field(data['field'])
            
            for child in sorted(data['children'], key=lambda f: f.number):
                render_field(child)
        
        # Render orphans
        for field in orphan_fields:
            render_field(field)

def render_questionnaire_tab():
    """Questionnaire tab"""
    if not st.session_state.extraction_result:
        st.info("👆 Upload and extract a form first")
        return
    
    result = st.session_state.extraction_result
    
    st.markdown("### Form Questionnaire")
    
    # Collect questionnaire fields by part
    quest_fields = {}
    for part in result.parts:
        part_quest = [f for f in part.fields if f.in_questionnaire]
        if part_quest:
            quest_fields[part.number] = {
                'title': part.title,
                'fields': sorted(part_quest, key=lambda f: f.get_sort_key())
            }
    
    if not quest_fields:
        st.info("No fields in questionnaire. Use Map Fields tab to add.")
        return
    
    # Display questionnaire
    for part_num in sorted(quest_fields.keys()):
        st.markdown(f"#### Part {part_num}: {quest_fields[part_num]['title']}")
        
        for field in quest_fields[part_num]['fields']:
            with st.container():
                st.markdown(f"**{field.number}. {field.label}**")
                
                quest_key = f"quest_{field.unique_id}"
                
                if field.choices:
                    for choice in field.choices:
                        choice.selected = st.checkbox(
                            f"{choice.letter}. {choice.text}",
                            value=choice.selected,
                            key=f"{quest_key}_{choice.letter}"
                        )
                elif field.field_type == "date":
                    field.value = st.date_input(
                        "Answer",
                        key=quest_key
                    )
                else:
                    field.value = st.text_area(
                        "Answer",
                        value=field.value or "",
                        key=quest_key,
                        height=70
                    )
                
                st.markdown("---")

def render_export_tab():
    """Export tab"""
    if not st.session_state.extraction_result:
        st.info("👆 Upload and extract a form first")
        return
    
    result = st.session_state.extraction_result
    
    st.markdown("### Export Form Data")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Export by Part")
        
        for i, part in enumerate(result.parts):
            # Use index in key to avoid duplicates
            if st.button(
                f"📥 Part {part.number}: {part.title}",
                key=f"export_part_btn_{i}_{part.number}",
                use_container_width=True
            ):
                export_part(part, i)
    
    with col2:
        st.markdown("#### Export Categories")
        
        if st.button("📥 All Mapped Fields", key="export_mapped", use_container_width=True):
            export_mapped_fields(result)
        
        if st.button("📥 Questionnaire", key="export_quest", use_container_width=True):
            export_questionnaire(result)
        
        if st.button("📥 Complete Form", key="export_all", use_container_width=True):
            export_complete(result)

def export_part(part: FormPart, index: int):
    """Export single part"""
    data = {
        "part": part.number,
        "title": part.title,
        "verified": part.verified,
        "fields": [f.to_dict() for f in part.fields],
        "stats": part.extraction_stats
    }
    
    json_str = json.dumps(data, indent=2, default=str)
    
    st.download_button(
        "Download Part Data",
        json_str,
        f"part_{part.number}.json",
        "application/json",
        key=f"download_part_{index}_{part.number}"
    )

def export_mapped_fields(result: ExtractionResult):
    """Export mapped fields"""
    mapped = {}
    
    for part in result.parts:
        for field in part.fields:
            if field.is_mapped:
                if field.db_object not in mapped:
                    mapped[field.db_object] = {}
                
                key = f"{field.db_path or field.number}"
                mapped[field.db_object][key] = {
                    "field": field.number,
                    "label": field.label,
                    "value": str(field.value) if field.value else "",
                    "part": part.number
                }
    
    json_str = json.dumps(mapped, indent=2, default=str)
    
    st.download_button(
        "Download Mapped Fields",
        json_str,
        "mapped_fields.json",
        "application/json",
        key="download_mapped"
    )

def export_questionnaire(result: ExtractionResult):
    """Export questionnaire"""
    quest_data = {}
    
    for part in result.parts:
        quest_fields = [f for f in part.fields if f.in_questionnaire]
        
        if quest_fields:
            quest_data[f"Part_{part.number}"] = {
                "title": part.title,
                "responses": [f.to_dict() for f in quest_fields]
            }
    
    json_str = json.dumps(quest_data, indent=2, default=str)
    
    st.download_button(
        "Download Questionnaire",
        json_str,
        "questionnaire.json",
        "application/json",
        key="download_quest"
    )

def export_complete(result: ExtractionResult):
    """Export complete form data"""
    data = {
        "form": {
            "number": result.form_number,
            "title": result.form_title
        },
        "stats": result.stats,
        "parts": []
    }
    
    for part in result.parts:
        part_data = {
            "number": part.number,
            "title": part.title,
            "verified": part.verified,
            "fields": [f.to_dict() for f in part.fields],
            "stats": part.extraction_stats
        }
        data["parts"].append(part_data)
    
    json_str = json.dumps(data, indent=2, default=str)
    
    st.download_button(
        "Download Complete Form",
        json_str,
        f"{result.form_number}_complete.json",
        "application/json",
        key="download_complete"
    )

if __name__ == "__main__":
    main()
