#!/usr/bin/env python3
"""
ENHANCED UNIVERSAL USCIS FORM READER - WITH VALIDATION AGENT
============================================================
Includes comprehensive part detection and validation systems
"""

import streamlit as st
import json
import re
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field as dataclass_field, asdict
import uuid

# Page config
st.set_page_config(
    page_title="Enhanced USCIS Reader - AI + Validation",
    page_icon="🔍",
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

# Enhanced styles with validation indicators
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
    .validation-success {
        background: #e8f5e8;
        border: 2px solid #4caf50;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    .validation-warning {
        background: #fff3e0;
        border: 2px solid #ff9800;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    .validation-error {
        background: #ffebee;
        border: 2px solid #f44336;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    .part-validation {
        background: #f5f5f5;
        border-left: 4px solid #2196f3;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 4px;
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
    .field-validated {
        border-right: 4px solid #4caf50;
    }
    .field-flagged {
        border-right: 4px solid #ff9800;
    }
</style>
""", unsafe_allow_html=True)

# ===== DATA STRUCTURES =====

@dataclass 
class ValidationResult:
    """Validation result for form parts and fields"""
    is_valid: bool
    confidence: float
    issues: List[str] = dataclass_field(default_factory=list)
    suggestions: List[str] = dataclass_field(default_factory=list)
    validation_method: str = "unknown"
    timestamp: datetime = dataclass_field(default_factory=datetime.now)

@dataclass
class PartValidation:
    """Validation data for a form part"""
    part_number: int
    expected_fields_range: Tuple[int, int]  # (min, max) expected fields
    actual_fields_count: int
    missing_patterns: List[str] = dataclass_field(default_factory=list)
    suspicious_patterns: List[str] = dataclass_field(default_factory=list)
    validation_score: float = 0.0
    is_complete: bool = False

@dataclass
class FieldChoice:
    """Individual choice for a question field"""
    letter: str
    label: str
    value: str = ""
    selected: bool = False

@dataclass
class USCISField:
    """Universal field structure with validation"""
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
    
    # Validation
    validation_result: Optional[ValidationResult] = None
    is_validated: bool = False
    
    # System
    unique_id: str = dataclass_field(default_factory=lambda: str(uuid.uuid4())[:8])
    extraction_method: str = "ai_agent"

@dataclass
class FormPart:
    """Enhanced form part with validation"""
    number: int
    title: str
    fields: List[USCISField] = dataclass_field(default_factory=list)
    ai_analysis: str = ""
    field_patterns: Dict[str, int] = dataclass_field(default_factory=dict)
    processed: bool = False
    
    # Validation
    validation: Optional[PartValidation] = None
    raw_text: str = ""
    text_length: int = 0
    extraction_confidence: float = 0.0

@dataclass
class USCISForm:
    """Enhanced USCIS form with comprehensive validation"""
    form_number: str = "Unknown"
    title: str = "USCIS Form"
    edition_date: str = ""
    total_pages: int = 0
    form_category: str = ""
    parts: Dict[int, FormPart] = dataclass_field(default_factory=dict)
    ai_summary: str = ""
    processing_time: float = 0.0
    
    # Enhanced validation
    expected_parts: List[int] = dataclass_field(default_factory=list)
    validation_results: Dict[str, ValidationResult] = dataclass_field(default_factory=dict)
    overall_validation_score: float = 0.0
    validation_summary: str = ""

# ===== KNOWN FORM STRUCTURES =====

KNOWN_FORM_STRUCTURES = {
    "I-129": {
        "expected_parts": list(range(0, 9)),  # Parts 0-8
        "part_titles": {
            0: "Attorney or Representative",
            1: "Information About the Employer",
            2: "Information About the Beneficiary", 
            3: "Processing Information",
            4: "Additional Information",
            5: "Employer Attestation",
            6: "Employer Certification and Signature",
            7: "Signature of Person Preparing Form",
            8: "Additional Information"
        },
        "critical_patterns": [
            r"Part\s*(\d+)\.",
            r"PART\s*(\d+)\.",
            r"Section\s*(\d+)\."
        ]
    },
    "I-485": {
        "expected_parts": list(range(0, 14)),  # Parts 0-13
        "part_titles": {
            0: "Attorney or Representative",
            1: "Information About You",
            2: "Application Type",
            3: "Additional Information About You",
            4: "Address History",
            5: "Marital History", 
            6: "Information About Your Children",
            7: "Biographic Information",
            8: "General Eligibility and Inadmissibility Grounds",
            9: "Accommodations for Individuals With Disabilities",
            10: "Applicant's Statement and Signature",
            11: "Interpreter's Information",
            12: "Contact Information of Preparer",
            13: "Additional Information"
        }
    },
    "I-130": {
        "expected_parts": list(range(0, 9)),  # Parts 0-8
        "part_titles": {
            0: "Attorney or Representative",
            1: "Relationship",
            2: "Information About You (Petitioner)",
            3: "Information About the Person You Are Filing For",
            4: "Information About Your Relative's Entry Into the United States",
            5: "Information About Your Employment",
            6: "Additional Information",
            7: "Petitioner's Statement and Signature", 
            8: "Additional Information"
        }
    }
}

# ===== VALIDATION AGENT =====

class FormValidationAgent:
    """Comprehensive validation agent for USCIS forms"""
    
    def __init__(self, client=None):
        self.client = client
        
    def validate_form_structure(self, form: USCISForm, full_text: str) -> ValidationResult:
        """Validate overall form structure and completeness"""
        issues = []
        suggestions = []
        confidence = 1.0
        
        # Check if form type is known
        form_structure = KNOWN_FORM_STRUCTURES.get(form.form_number)
        if form_structure:
            expected_parts = form_structure["expected_parts"]
            found_parts = list(form.parts.keys())
            
            # Check for missing parts
            missing_parts = set(expected_parts) - set(found_parts)
            if missing_parts:
                issues.append(f"Missing parts: {sorted(missing_parts)}")
                confidence -= 0.1 * len(missing_parts)
                suggestions.append("Re-scan document for missing part headers")
            
            # Check for unexpected parts
            extra_parts = set(found_parts) - set(expected_parts)
            if extra_parts:
                issues.append(f"Unexpected parts found: {sorted(extra_parts)}")
                suggestions.append("Verify these are legitimate form parts")
            
            # Validate part titles if available
            expected_titles = form_structure.get("part_titles", {})
            for part_num, part in form.parts.items():
                if part_num in expected_titles:
                    expected_title = expected_titles[part_num].lower()
                    actual_title = part.title.lower()
                    if not any(word in actual_title for word in expected_title.split()[:3]):
                        issues.append(f"Part {part_num} title mismatch: expected '{expected_titles[part_num]}', got '{part.title}'")
                        confidence -= 0.05
        else:
            suggestions.append(f"Form {form.form_number} structure not in knowledge base - using generic validation")
        
        # Validate part sequence
        sorted_parts = sorted(form.parts.keys())
        if sorted_parts != list(range(min(sorted_parts), max(sorted_parts) + 1)):
            issues.append("Non-sequential part numbering detected")
            suggestions.append("Check for missing or misnumbered parts")
        
        return ValidationResult(
            is_valid=len(issues) == 0,
            confidence=max(0.0, confidence),
            issues=issues,
            suggestions=suggestions,
            validation_method="structure_validation"
        )
    
    def validate_part_extraction(self, part: FormPart, full_text: str, form_number: str) -> PartValidation:
        """Validate individual part extraction completeness"""
        
        # Get expected field count ranges based on form type and part
        expected_range = self._get_expected_field_range(form_number, part.number)
        actual_count = len([f for f in part.fields if not f.is_subfield and not f.is_choice])
        
        # Check for missing common patterns
        missing_patterns = []
        suspicious_patterns = []
        
        # Common field patterns to look for
        common_patterns = [
            (r'\b\d+\.?\s*[a-z]\.?\s+', 'subfield_pattern'),
            (r'\b\d+\.\s+.*name', 'name_field'),
            (r'\b\d+\.\s+.*address', 'address_field'),
            (r'\b\d+\.\s+.*date', 'date_field'),
            (r'yes\s*\[\s*\]\s*no\s*\[\s*\]', 'checkbox_pair'),
            (r'\[\s*\]\s*[A-Z]', 'checkbox_option')
        ]
        
        part_text_sample = part.raw_text[:5000] if part.raw_text else ""
        
        for pattern, pattern_name in common_patterns:
            matches = len(re.findall(pattern, part_text_sample, re.IGNORECASE))
            extracted_count = sum(1 for f in part.fields if pattern_name in f.field_pattern)
            
            if matches > extracted_count * 1.5:  # 50% tolerance
                missing_patterns.append(f"Potentially missed {pattern_name} fields: found {matches} patterns, extracted {extracted_count}")
        
        # Calculate validation score
        score = 1.0
        if actual_count < expected_range[0]:
            score -= 0.3
        elif actual_count > expected_range[1] * 1.5:
            score -= 0.2
        
        if missing_patterns:
            score -= 0.2
        
        if part.text_length < 500:  # Very short part text might indicate incomplete extraction
            score -= 0.3
            suspicious_patterns.append("Part text seems unusually short")
        
        return PartValidation(
            part_number=part.number,
            expected_fields_range=expected_range,
            actual_fields_count=actual_count,
            missing_patterns=missing_patterns,
            suspicious_patterns=suspicious_patterns,
            validation_score=max(0.0, score),
            is_complete=(score > 0.7 and len(missing_patterns) == 0)
        )
    
    def _get_expected_field_range(self, form_number: str, part_number: int) -> Tuple[int, int]:
        """Get expected field count range for a specific form part"""
        
        # Known ranges for common form parts
        common_ranges = {
            0: (2, 8),    # Attorney section - usually few fields
            1: (5, 20),   # Basic info sections
            2: (5, 25),   # Beneficiary/applicant info
            3: (3, 15),   # Additional info
            4: (2, 12),   # Addresses/history
            5: (2, 10),   # Marital/family
            6: (1, 8),    # Signatures
            7: (1, 8),    # Preparer info
            8: (1, 5)     # Additional info
        }
        
        # Form-specific adjustments
        if form_number == "I-129":
            if part_number == 2:  # Beneficiary section is usually larger
                return (8, 30)
            elif part_number == 5:  # Employer attestation has many checkboxes
                return (10, 40)
        elif form_number == "I-485":
            if part_number == 8:  # Eligibility section has many questions
                return (15, 60)
        
        return common_ranges.get(part_number, (3, 20))
    
    def run_comprehensive_validation(self, form: USCISForm, full_text: str) -> Dict[str, ValidationResult]:
        """Run all validation checks on the form"""
        results = {}
        
        # 1. Structure validation
        results["structure"] = self.validate_form_structure(form, full_text)
        
        # 2. Part-by-part validation
        for part_num, part in form.parts.items():
            part.validation = self.validate_part_extraction(part, full_text, form.form_number)
        
        # 3. AI-powered validation if available
        if self.client:
            results["ai_validation"] = self._ai_validation_check(form, full_text)
        
        # 4. Cross-validation checks
        results["cross_validation"] = self._cross_validation_checks(form)
        
        # Calculate overall score
        total_issues = sum(len(r.issues) for r in results.values())
        avg_confidence = sum(r.confidence for r in results.values()) / len(results)
        
        form.overall_validation_score = max(0.0, avg_confidence - (total_issues * 0.1))
        form.validation_results = results
        
        return results
    
    def _ai_validation_check(self, form: USCISForm, full_text: str) -> ValidationResult:
        """AI-powered validation check"""
        if not self.client:
            return ValidationResult(is_valid=True, confidence=0.5, validation_method="ai_unavailable")
        
        prompt = f"""Analyze this USCIS form extraction and identify potential issues:

Form: {form.form_number} - {form.title}
Parts extracted: {list(form.parts.keys())}
Total fields: {sum(len(p.fields) for p in form.parts.values())}

For each part, check if the field count and types seem reasonable:
{chr(10).join([f"Part {p.number}: {p.title} ({len(p.fields)} fields)" for p in form.parts.values()])}

Look for:
1. Missing parts that should exist
2. Parts with suspiciously few or many fields  
3. Common fields that might be missing
4. Structural inconsistencies

Return JSON:
{{
    "issues": ["specific issue 1", "specific issue 2"],
    "suggestions": ["suggestion 1", "suggestion 2"],
    "confidence": 0.85,
    "missing_parts": [1, 3],
    "suspicious_parts": [2, 5]
}}

Form text sample: {full_text[:3000]}"""
        
        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = response.content[0].text.strip()
            if "{" in content:
                json_start = content.find("{")
                json_end = content.rfind("}") + 1
                data = json.loads(content[json_start:json_end])
                
                return ValidationResult(
                    is_valid=len(data.get("issues", [])) == 0,
                    confidence=data.get("confidence", 0.5),
                    issues=data.get("issues", []),
                    suggestions=data.get("suggestions", []),
                    validation_method="ai_analysis"
                )
        except Exception as e:
            return ValidationResult(
                is_valid=False, 
                confidence=0.3,
                issues=[f"AI validation failed: {e}"],
                validation_method="ai_error"
            )
    
    def _cross_validation_checks(self, form: USCISForm) -> ValidationResult:
        """Cross-validation between parts and fields"""
        issues = []
        suggestions = []
        
        # Check for orphaned subfields
        all_parent_numbers = {f.number for p in form.parts.values() for f in p.fields if f.is_parent}
        orphaned_subfields = []
        
        for part in form.parts.values():
            for field in part.fields:
                if field.is_subfield and field.parent_number not in all_parent_numbers:
                    orphaned_subfields.append(f"{field.number} (parent: {field.parent_number})")
        
        if orphaned_subfields:
            issues.append(f"Orphaned subfields found: {orphaned_subfields[:5]}")
            suggestions.append("Check parent field extraction")
        
        # Check for duplicate field numbers within parts
        for part_num, part in form.parts.items():
            field_numbers = [f.number for f in part.fields]
            duplicates = set([x for x in field_numbers if field_numbers.count(x) > 1])
            if duplicates:
                issues.append(f"Part {part_num} has duplicate field numbers: {duplicates}")
        
        return ValidationResult(
            is_valid=len(issues) == 0,
            confidence=0.9 if len(issues) == 0 else 0.6,
            issues=issues,
            suggestions=suggestions,
            validation_method="cross_validation"
        )

# ===== ENHANCED AI AGENT =====

class EnhancedUSCISAgent:
    """Enhanced Claude agent with comprehensive part detection"""
    
    def __init__(self):
        self.client = None
        self.validator = None
        self.setup_client()
    
    def setup_client(self):
        """Setup Anthropic client and validator"""
        if not ANTHROPIC_AVAILABLE:
            return False
        
        try:
            api_key = st.secrets.get("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                self.client = anthropic.Anthropic(api_key=api_key)
                self.validator = FormValidationAgent(self.client)
                return True
        except Exception as e:
            st.error(f"Claude API setup failed: {e}")
        return False
    
    def comprehensive_part_extraction(self, text: str, form_number: str = "Unknown") -> List[Dict]:
        """Multi-strategy part extraction with validation"""
        
        # Strategy 1: AI-based extraction
        ai_parts = self._ai_extract_parts(text, form_number)
        
        # Strategy 2: Pattern-based extraction  
        pattern_parts = self._pattern_extract_parts(text)
        
        # Strategy 3: Known structure matching
        structure_parts = self._structure_extract_parts(text, form_number)
        
        # Combine and validate results
        combined_parts = self._combine_part_results(ai_parts, pattern_parts, structure_parts)
        
        # Final validation
        validated_parts = self._validate_part_completeness(combined_parts, text, form_number)
        
        return validated_parts
    
    def _ai_extract_parts(self, text: str, form_number: str) -> List[Dict]:
        """Enhanced AI part extraction with multiple passes"""
        if not self.client:
            return []
        
        # First pass - scan entire document
        prompt1 = f"""Analyze this complete USCIS form {form_number} and identify ALL parts/sections.

CRITICAL REQUIREMENTS:
1. Find EVERY part number (0, 1, 2, 3, 4, 5, 6, 7, 8, etc.)
2. Look through the ENTIRE document, not just the beginning
3. Include Part 0 (attorney section) if it exists
4. Don't miss any parts in the middle or end

Common patterns to look for:
- "Part 0." or "Part 0:" (Attorney/Representative section)
- "Part 1." through "Part 8+" 
- "PART X." or "PART X:" (uppercase)
- "Section X." or "Chapter X."

For each part found, extract:
- Exact part number
- Complete title as written
- Approximate location in document

Return comprehensive JSON array:
[{{
    "number": 0,
    "title": "To be completed by an Attorney or Accredited Representative",
    "location": "beginning"
}}, ...]

Text to analyze (showing first 8000 chars, but analyze conceptually for all parts):
{text[:8000]}

CONTINUE SCANNING for parts that appear later in the document...
Additional text sample from middle:
{text[len(text)//2:len(text)//2+2000] if len(text) > 10000 else ""}

Text sample from end:
{text[-2000:] if len(text) > 4000 else ""}"""

        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt1}]
            )
            
            content = response.content[0].text.strip()
            if "[" in content:
                json_start = content.find("[")
                json_end = content.rfind("]") + 1
                parts = json.loads(content[json_start:json_end])
                
                # Second pass - verify completeness
                if len(parts) < 5:  # Suspiciously few parts, try again with different approach
                    return self._ai_extract_parts_detailed(text, form_number, parts)
                
                return parts
                
        except Exception as e:
            st.warning(f"AI part extraction error: {e}")
        
        return []
    
    def _ai_extract_parts_detailed(self, text: str, form_number: str, initial_parts: List[Dict]) -> List[Dict]:
        """Detailed AI extraction when initial scan finds too few parts"""
        if not self.client:
            return initial_parts
        
        found_numbers = {p["number"] for p in initial_parts}
        expected_max = KNOWN_FORM_STRUCTURES.get(form_number, {}).get("expected_parts", [])
        
        if expected_max:
            max_expected = max(expected_max)
            missing_parts = set(range(0, max_expected + 1)) - found_numbers
            
            if missing_parts:
                prompt = f"""The initial scan found parts {sorted(found_numbers)} but we expect parts up to {max_expected} for form {form_number}.

Search specifically for these missing parts: {sorted(missing_parts)}

Look for alternative patterns:
- "Part X" without periods
- Parts embedded in headers or footers
- Parts with slightly different formatting
- Parts that might be labeled as "Section" instead

For each missing part found, return:
{{
    "number": X,
    "title": "exact title found",
    "pattern": "how it was labeled"
}}

Scan this text more carefully:
{text[:12000]}"""
                
                try:
                    response = self.client.messages.create(
                        model="claude-3-5-sonnet-20241022",
                        max_tokens=800,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    
                    content = response.content[0].text.strip()
                    if "[" in content or "{" in content:
                        try:
                            if "[" in content:
                                json_start = content.find("[")
                                json_end = content.rfind("]") + 1
                                additional_parts = json.loads(content[json_start:json_end])
                            else:
                                json_start = content.find("{")
                                json_end = content.rfind("}") + 1
                                part_data = json.loads(content[json_start:json_end])
                                additional_parts = [part_data] if isinstance(part_data, dict) else []
                            
                            # Merge with initial parts
                            all_parts = initial_parts.copy()
                            for new_part in additional_parts:
                                if new_part["number"] not in found_numbers:
                                    all_parts.append(new_part)
                            
                            return sorted(all_parts, key=lambda x: x["number"])
                            
                        except json.JSONDecodeError:
                            pass
                        
                except Exception as e:
                    st.warning(f"Detailed AI extraction error: {e}")
        
        return initial_parts
    
    def _pattern_extract_parts(self, text: str) -> List[Dict]:
        """Pattern-based part extraction as fallback"""
        parts = []
        
        # Multiple pattern attempts
        patterns = [
            (r'(?:^|\n)\s*Part\s+(\d+)\.?\s*([^\n]{0,100})', re.IGNORECASE | re.MULTILINE),
            (r'(?:^|\n)\s*PART\s+(\d+)\.?\s*([^\n]{0,100})', re.MULTILINE),
            (r'(?:^|\n)\s*Section\s+(\d+)\.?\s*([^\n]{0,100})', re.IGNORECASE | re.MULTILINE),
            (r'Part\s*(\d+)\s*[:\-\.]\s*([^\n]{3,100})', re.IGNORECASE),
            (r'(?:^|\n)(\d+)\.\s*[A-Z][^0-9\n]{10,80}', re.MULTILINE),  # Numbered sections
        ]
        
        found_numbers = set()
        
        for pattern, flags in patterns:
            matches = re.finditer(pattern, text, flags)
            
            for match in matches:
                try:
                    if len(match.groups()) >= 2:
                        number = int(match.group(1))
                        title = match.group(2).strip()
                    else:
                        # Handle single group patterns
                        number = len(parts)
                        title = match.group(1).strip() if match.groups() else f"Section {number}"
                    
                    if number not in found_numbers and 0 <= number <= 20:
                        found_numbers.add(number)
                        parts.append({
                            "number": number,
                            "title": title[:100],  # Limit title length
                            "extraction_method": "pattern"
                        })
                        
                except (ValueError, IndexError):
                    continue
        
        return sorted(parts, key=lambda x: x["number"])
    
    def _structure_extract_parts(self, text: str, form_number: str) -> List[Dict]:
        """Extract parts based on known form structures"""
        parts = []
        
        structure = KNOWN_FORM_STRUCTURES.get(form_number)
        if not structure:
            return parts
        
        expected_parts = structure["expected_parts"]
        part_titles = structure.get("part_titles", {})
        
        for part_num in expected_parts:
            # Look for this specific part in the text
            part_patterns = [
                rf'Part\s+{part_num}\.?\s*([^\n]{{0,100}})',
                rf'PART\s+{part_num}\.?\s*([^\n]{{0,100}})',
                rf'Section\s+{part_num}\.?\s*([^\n]{{0,100}})'
            ]
            
            found = False
            for pattern in part_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    title = match.group(1).strip() if match.groups() else part_titles.get(part_num, f"Part {part_num}")
                    parts.append({
                        "number": part_num,
                        "title": title,
                        "extraction_method": "structure_based"
                    })
                    found = True
                    break
            
            # If not found but expected, add with default title
            if not found and part_num in part_titles:
                parts.append({
                    "number": part_num,
                    "title": part_titles[part_num],
                    "extraction_method": "structure_inferred"
                })
        
        return parts
    
    def _combine_part_results(self, ai_parts: List[Dict], pattern_parts: List[Dict], structure_parts: List[Dict]) -> List[Dict]:
        """Intelligently combine results from different extraction methods"""
        combined = {}
        
        # Add all parts from different sources
        all_sources = [
            (ai_parts, "ai", 1.0),
            (pattern_parts, "pattern", 0.8), 
            (structure_parts, "structure", 0.6)
        ]
        
        for parts_list, source, confidence in all_sources:
            for part in parts_list:
                part_num = part["number"]
                if part_num not in combined:
                    combined[part_num] = {
                        "number": part_num,
                        "title": part["title"],
                        "confidence": confidence,
                        "sources": [source],
                        "extraction_method": part.get("extraction_method", source)
                    }
                else:
                    # Update with higher confidence source
                    if confidence > combined[part_num]["confidence"]:
                        combined[part_num]["title"] = part["title"]
                        combined[part_num]["confidence"] = confidence
                    combined[part_num]["sources"].append(source)
        
        # Sort by part number
        return sorted(combined.values(), key=lambda x: x["number"])
    
    def _validate_part_completeness(self, parts: List[Dict], text: str, form_number: str) -> List[Dict]:
        """Final validation of part completeness"""
        
        # Check against known structures
        structure = KNOWN_FORM_STRUCTURES.get(form_number)
        if structure:
            expected_parts = set(structure["expected_parts"])
            found_parts = set(p["number"] for p in parts)
            
            missing_parts = expected_parts - found_parts
            if missing_parts:
                st.warning(f"⚠️ Missing expected parts for {form_number}: {sorted(missing_parts)}")
                
                # Try to add missing parts with generic titles
                for missing_num in missing_parts:
                    default_title = structure.get("part_titles", {}).get(
                        missing_num, f"Part {missing_num}"
                    )
                    parts.append({
                        "number": missing_num,
                        "title": default_title,
                        "confidence": 0.3,
                        "sources": ["validation_inferred"],
                        "extraction_method": "validation_recovery"
                    })
        
        # Ensure we have at least a reasonable number of parts
        if len(parts) < 3:
            st.warning("⚠️ Very few parts detected - this may indicate extraction issues")
        
        return sorted(parts, key=lambda x: x["number"])

# ===== ENHANCED FORM PROCESSOR =====

class EnhancedFormProcessor:
    """Enhanced processor with comprehensive validation"""
    
    def __init__(self):
        self.agent = EnhancedUSCISAgent()
    
    def process_pdf_with_validation(self, pdf_file) -> Optional[USCISForm]:
        """Process PDF with comprehensive validation"""
        if not PYMUPDF_AVAILABLE:
            st.error("PyMuPDF not available")
            return None
        
        start_time = datetime.now()
        
        # Extract PDF content
        try:
            pdf_file.seek(0)
            doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
            
            full_text = ""
            page_texts = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                page_texts.append(text)
                full_text += f"\n\n=== PAGE {page_num + 1} ===\n{text}"
            
            total_pages = len(doc)
            doc.close()
            
        except Exception as e:
            st.error(f"PDF extraction error: {e}")
            return None
        
        # Progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Step 1: Form identification
        status_text.text("🔍 Identifying form type...")
        progress_bar.progress(0.1)
        
        form_info = self.agent.identify_form(full_text[:3000])
        form = USCISForm(
            form_number=form_info["form_number"],
            title=form_info["title"],
            edition_date=form_info["edition_date"],
            form_category=form_info.get("form_category", ""),
            total_pages=total_pages
        )
        
        # Step 2: Enhanced part extraction
        status_text.text("📋 Extracting form parts with validation...")
        progress_bar.progress(0.2)
        
        parts_data = self.agent.comprehensive_part_extraction(full_text, form.form_number)
        
        if not parts_data:
            st.error("❌ No parts could be extracted from the form")
            return None
        
        st.success(f"✅ Extracted {len(parts_data)} parts")
        
        # Display extraction summary
        with st.expander("📊 Part Extraction Summary", expanded=True):
            for part in parts_data:
                confidence_color = "🟢" if part.get("confidence", 1.0) > 0.8 else "🟡" if part.get("confidence", 1.0) > 0.5 else "🔴"
                sources = part.get("sources", ["unknown"])
                st.write(f"{confidence_color} **Part {part['number']}**: {part['title']} (Sources: {', '.join(sources)})")
        
        # Step 3: Process each part with validation
        total_parts = len(parts_data)
        
        for i, part_info in enumerate(parts_data):
            part_num = part_info["number"]
            part_title = part_info["title"]
            
            status_text.text(f"🔄 Processing Part {part_num}: {part_title}")
            progress_bar.progress(0.3 + (0.5 * i / total_parts))
            
            # Extract part text
            part_text = self._extract_part_text_enhanced(full_text, part_num, page_texts)
            
            # Analyze fields
            fields = self.agent.analyze_part_fields(part_text, part_num, part_title)
            
            # Create part with validation data
            part = FormPart(
                number=part_num,
                title=part_title,
                fields=fields,
                raw_text=part_text,
                text_length=len(part_text),
                extraction_confidence=part_info.get("confidence", 1.0),
                processed=True
            )
            
            # Collect field patterns
            patterns = {}
            for field in fields:
                if field.field_pattern:
                    patterns[field.field_pattern] = patterns.get(field.field_pattern, 0) + 1
            part.field_patterns = patterns
            
            form.parts[part_num] = part
        
        # Step 4: Comprehensive validation
        status_text.text("🔍 Running validation checks...")
        progress_bar.progress(0.9)
        
        if self.agent.validator:
            validation_results = self.agent.validator.run_comprehensive_validation(form, full_text)
            
            # Display validation summary
            self._display_validation_results(validation_results, form)
        
        # Step 5: Finalize
        form.processing_time = (datetime.now() - start_time).total_seconds()
        form.ai_summary = self._generate_enhanced_summary(form)
        
        status_text.text("✅ Processing complete!")
        progress_bar.progress(1.0)
        
        return form
    
    def _extract_part_text_enhanced(self, full_text: str, part_number: int, page_texts: List[str]) -> str:
        """Enhanced part text extraction with multiple strategies"""
        
        # Strategy 1: Look for exact part boundaries
        part_patterns = [
            rf"Part\s+{part_number}\.?\s*([^\n]*)",
            rf"PART\s+{part_number}\.?\s*([^\n]*)", 
            rf"Section\s+{part_number}\.?\s*([^\n]*)"
        ]
        
        start_pos = -1
        for pattern in part_patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                start_pos = match.start()
                break
        
        if start_pos == -1:
            # Strategy 2: Look for part in specific pages
            for page_idx, page_text in enumerate(page_texts):
                for pattern in part_patterns:
                    if re.search(pattern, page_text, re.IGNORECASE):
                        # Return text from this page and next few pages
                        combined_text = ""
                        for i in range(page_idx, min(page_idx + 3, len(page_texts))):
                            combined_text += page_texts[i] + "\n"
                        return combined_text
        
        if start_pos == -1:
            # Strategy 3: Return proportional text based on part number
            text_per_part = len(full_text) // max(8, part_number + 1)
            start_pos = part_number * text_per_part
            return full_text[start_pos:start_pos + text_per_part * 2]
        
        # Find end of this part
        next_part_patterns = [
            rf"Part\s+{part_number + 1}\b",
            rf"PART\s+{part_number + 1}\b",
            rf"Section\s+{part_number + 1}\b"
        ]
        
        end_pos = len(full_text)
        for pattern in next_part_patterns:
            match = re.search(pattern, full_text[start_pos:], re.IGNORECASE)
            if match:
                end_pos = start_pos + match.start()
                break
        
        return full_text[start_pos:end_pos]
    
    def _display_validation_results(self, validation_results: Dict[str, ValidationResult], form: USCISForm):
        """Display comprehensive validation results"""
        
        st.markdown("### 🔍 Validation Results")
        
        overall_issues = sum(len(r.issues) for r in validation_results.values())
        overall_confidence = sum(r.confidence for r in validation_results.values()) / len(validation_results)
        
        if overall_issues == 0 and overall_confidence > 0.8:
            st.markdown(f"""
            <div class="validation-success">
                <strong>✅ Validation Passed</strong><br>
                Overall Confidence: {overall_confidence:.1%}<br>
                All parts and fields appear to be extracted correctly.
            </div>
            """, unsafe_allow_html=True)
        elif overall_issues < 3 and overall_confidence > 0.6:
            st.markdown(f"""
            <div class="validation-warning">
                <strong>⚠️ Validation Warnings</strong><br>
                Overall Confidence: {overall_confidence:.1%}<br>
                {overall_issues} potential issues detected. Review recommended.
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="validation-error">
                <strong>❌ Validation Issues</strong><br>
                Overall Confidence: {overall_confidence:.1%}<br>
                {overall_issues} issues detected. Manual review required.
            </div>
            """, unsafe_allow_html=True)
        
        # Detailed results
        for check_type, result in validation_results.items():
            with st.expander(f"📋 {check_type.replace('_', ' ').title()} ({result.confidence:.1%} confidence)"):
                if result.issues:
                    st.markdown("**Issues Found:**")
                    for issue in result.issues:
                        st.markdown(f"• {issue}")
                
                if result.suggestions:
                    st.markdown("**Suggestions:**")
                    for suggestion in result.suggestions:
                        st.markdown(f"• {suggestion}")
                
                if not result.issues and not result.suggestions:
                    st.success("No issues detected in this area.")
        
        # Part-level validation
        if any(p.validation for p in form.parts.values()):
            st.markdown("#### 📊 Part-Level Validation")
            
            for part_num, part in sorted(form.parts.items()):
                if part.validation:
                    val = part.validation
                    status_icon = "✅" if val.is_complete else "⚠️" if val.validation_score > 0.5 else "❌"
                    
                    st.markdown(f"""
                    <div class="part-validation">
                        <strong>{status_icon} Part {part_num}: {part.title}</strong><br>
                        Fields: {val.actual_fields_count} (expected: {val.expected_fields_range[0]}-{val.expected_fields_range[1]})<br>
                        Validation Score: {val.validation_score:.1%}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if val.missing_patterns:
                        with st.expander(f"Missing Patterns - Part {part_num}"):
                            for pattern in val.missing_patterns:
                                st.warning(pattern)
    
    def _generate_enhanced_summary(self, form: USCISForm) -> str:
        """Generate enhanced processing summary"""
        insights = []
        
        total_fields = sum(len(p.fields) for p in form.parts.values())
        parent_fields = sum(len([f for f in p.fields if f.is_parent]) for p in form.parts.values())
        subfields = sum(len([f for f in p.fields if f.is_subfield]) for p in form.parts.values())
        
        insights.append(f"Processed {form.form_number} with {len(form.parts)} parts")
        insights.append(f"Extracted {total_fields} total fields ({parent_fields} parent, {subfields} subfields)")
        insights.append(f"Overall validation score: {form.overall_validation_score:.1%}")
        
        if form.validation_results:
            total_issues = sum(len(r.issues) for r in form.validation_results.values())
            if total_issues == 0:
                insights.append("All validation checks passed")
            else:
                insights.append(f"{total_issues} validation issues detected")
        
        return " | ".join(insights)

# ===== ENHANCED UI =====

def display_enhanced_field(field: USCISField, prefix: str):
    """Display field with enhanced validation indicators"""
    unique_key = f"{prefix}_{field.unique_id}"
    
    # Determine styling based on validation
    css_classes = ["field-card"]
    status_indicators = []
    
    if field.is_parent:
        css_classes.append("field-parent")
        status_indicators.append("📁 Parent")
    elif field.is_subfield:
        css_classes.append("field-subfield") 
        status_indicators.append(f"↳ Sub of {field.parent_number}")
    
    if field.is_validated:
        css_classes.append("field-validated")
        status_indicators.append("✅ Validated")
    elif field.validation_result and not field.validation_result.is_valid:
        css_classes.append("field-flagged")
        status_indicators.append("⚠️ Flagged")
    
    if field.is_mapped:
        status_indicators.append("🎯 Mapped")
    if field.in_questionnaire:
        status_indicators.append("📝 Quest")
    
    st.markdown(f'<div class="{" ".join(css_classes)}">', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([4, 3, 2])
    
    with col1:
        confidence_indicator = ""
        if field.confidence < 1.0:
            confidence_indicator = f" ({field.confidence:.1%})"
        
        st.markdown(f"**{field.number}. {field.label}**{confidence_indicator}")
        
        # Enhanced analysis display
        if field.field_pattern or field.ai_reasoning or field.validation_result:
            with st.expander("🔍 Analysis & Validation"):
                if field.field_pattern:
                    st.code(f"Pattern: {field.field_pattern}")
                if field.ai_reasoning:
                    st.info(f"AI: {field.ai_reasoning}")
                if field.validation_result:
                    if field.validation_result.issues:
                        st.warning("Issues: " + ", ".join(field.validation_result.issues))
                    if field.validation_result.suggestions:
                        st.info("Suggestions: " + ", ".join(field.validation_result.suggestions))
    
    with col2:
        if not field.is_parent:
            # Field value input (same as before)
            if field.field_type == "date":
                field.value = st.date_input("Value", key=f"{unique_key}_val", 
                                          label_visibility="collapsed")
                field.value = str(field.value) if field.value else ""
            elif field.field_type in ["checkbox", "choice"] or field.is_choice:
                field.value = st.checkbox("", key=f"{unique_key}_choice")
            else:
                field.value = st.text_input("Value", value=field.value, 
                                          key=f"{unique_key}_val", 
                                          label_visibility="collapsed")
    
    with col3:
        st.markdown(" | ".join(status_indicators))
        
        if not field.is_parent:
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("Map", key=f"{unique_key}_map", use_container_width=True):
                    st.session_state[f"show_mapping_{field.unique_id}"] = True
                    st.rerun()
            with c2:
                quest_label = "✓" if field.in_questionnaire else "Quest"
                if st.button(quest_label, key=f"{unique_key}_quest", use_container_width=True):
                    field.in_questionnaire = not field.in_questionnaire
                    st.rerun()
            with c3:
                val_label = "✓" if field.is_validated else "Val"
                if st.button(val_label, key=f"{unique_key}_val_btn", use_container_width=True):
                    field.is_validated = not field.is_validated
                    st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

# ===== MAIN APPLICATION =====

def main():
    st.markdown("""
    <div class="main-header">
        <h1>🔍 Enhanced USCIS Reader - AI + Validation</h1>
        <p>Comprehensive part detection with validation agent</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize
    if 'form' not in st.session_state:
        st.session_state.form = None
    if 'processor' not in st.session_state:
        st.session_state.processor = EnhancedFormProcessor()
    
    # Check system status
    if st.session_state.processor.agent.client:
        st.markdown("""
        <div class="validation-success">
            <strong>✅ Enhanced AI Agent Active</strong><br>
            Multi-strategy part detection with comprehensive validation enabled.
        </div>
        """, unsafe_allow_html=True)
    else:
        st.error("❌ Claude API not configured. Please add ANTHROPIC_API_KEY to your Streamlit secrets.")
        st.stop()
    
    # Sidebar with enhanced metrics
    with st.sidebar:
        st.markdown("## 📊 Enhanced Analysis")
        
        if st.session_state.form:
            form = st.session_state.form
            st.success(f"📄 {form.form_number}")
            st.info(f"📖 {form.title}")
            
            # Enhanced metrics
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Parts", len(form.parts))
                total_fields = sum(len(p.fields) for p in form.parts.values())
                st.metric("Fields", total_fields)
            
            with col2:
                validated_fields = sum(1 for p in form.parts.values() for f in p.fields if f.is_validated)
                st.metric("Validated", f"{validated_fields}/{total_fields}")
                
                if form.overall_validation_score > 0:
                    score_color = "green" if form.overall_validation_score > 0.8 else "orange" if form.overall_validation_score > 0.5 else "red"
                    st.markdown(f"**Validation:** <span style='color: {score_color}'>{form.overall_validation_score:.1%}</span>", 
                               unsafe_allow_html=True)
            
            # Part status overview
            st.markdown("### 📋 Part Status")
            for part_num, part in sorted(form.parts.items()):
                validation_icon = "✅" if part.validation and part.validation.is_complete else "⚠️" if part.validation and part.validation.validation_score > 0.5 else "❌"
                field_count = len([f for f in part.fields if not f.is_subfield])
                st.markdown(f"{validation_icon} Part {part_num}: {field_count} fields")
        
        if st.button("🔄 Reset Application", use_container_width=True):
            st.session_state.clear()
            st.rerun()
    
    # Main interface
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📤 Upload & Process", "🔍 Validation Report", "🗂️ Field Mapping", "📝 Questionnaire", "💾 Export"])
    
    with tab1:
        st.markdown("### 📤 Upload USCIS Form for Enhanced Processing")
        
        uploaded_file = st.file_uploader("Choose USCIS PDF file", type=['pdf'])
        
        if uploaded_file:
            if st.button("🚀 Process with Enhanced AI + Validation", type="primary", use_container_width=True):
                form = st.session_state.processor.process_pdf_with_validation(uploaded_file)
                
                if form:
                    st.session_state.form = form
                    st.balloons()
                else:
                    st.error("❌ Failed to process form")
    
    with tab2:
        if st.session_state.form:
            st.markdown("### 🔍 Comprehensive Validation Report")
            
            form = st.session_state.form
            
            if form.validation_results:
                # Summary metrics
                col1, col2, col3, col4 = st.columns(4)
                
                total_issues = sum(len(r.issues) for r in form.validation_results.values())
                total_suggestions = sum(len(r.suggestions) for r in form.validation_results.values())
                avg_confidence = sum(r.confidence for r in form.validation_results.values()) / len(form.validation_results)
                
                with col1:
                    st.metric("Overall Score", f"{form.overall_validation_score:.1%}")
                with col2:
                    st.metric("Issues Found", total_issues)
                with col3:
                    st.metric("Suggestions", total_suggestions)
                with col4:
                    st.metric("Avg Confidence", f"{avg_confidence:.1%}")
                
                # Re-run validation
                if st.button("🔄 Re-run Validation", type="secondary"):
                    with st.spinner("Running validation..."):
                        if st.session_state.processor.agent.validator:
                            new_results = st.session_state.processor.agent.validator.run_comprehensive_validation(
                                form, "")  # Would need full text stored
                            form.validation_results = new_results
                            st.rerun()
                
                # Validation details already displayed by processor
            else:
                st.info("No validation results available. Process a form first.")
        else:
            st.info("👆 Upload and process a USCIS form first")
    
    with tab3:
        if st.session_state.form:
            st.markdown("### 🗂️ Enhanced Field Mapping")
            
            form = st.session_state.form
            
            # Part selection with validation status
            part_options = []
            for part_num in sorted(form.parts.keys()):
                part = form.parts[part_num]
                status = "✅" if part.validation and part.validation.is_complete else "⚠️"
                part_options.append((part_num, f"{status} Part {part_num}: {part.title}"))
            
            if part_options:
                selected_idx = st.selectbox(
                    "Select Part to Map",
                    range(len(part_options)),
                    format_func=lambda x: part_options[x][1]
                )
                
                selected_part_num = part_options[selected_idx][0]
                part = form.parts[selected_part_num]
                
                st.markdown(f"#### Part {part.number}: {part.title}")
                
                if part.validation:
                    val = part.validation
                    st.info(f"📊 Validation: {val.validation_score:.1%} score, {val.actual_fields_count} fields extracted")
                
                # Display fields with enhanced validation
                displayed = set()
                for field in sorted(part.fields, key=lambda f: st.session_state.processor.agent._get_sort_key(f.number)):
                    if field.number not in displayed:
                        display_enhanced_field(field, f"map_p{part.number}")
                        displayed.add(field.number)
                        
                        # Show related subfields
                        for child in part.fields:
                            if child.parent_number == field.number and child.number not in displayed:
                                display_enhanced_field(child, f"map_p{part.number}")
                                displayed.add(child.number)
        else:
            st.info("👆 Upload and process a USCIS form first")
    
    with tab4:
        # Questionnaire tab (same as before, but with validation indicators)
        if st.session_state.form:
            st.markdown("### 📝 Interactive Questionnaire")
            
            form = st.session_state.form
            
            for part_num, part in sorted(form.parts.items()):
                quest_fields = [f for f in part.fields if f.in_questionnaire and not f.is_parent]
                
                if quest_fields:
                    validation_status = ""
                    if part.validation:
                        validation_status = f" ({part.validation.validation_score:.1%} validated)"
                    
                    st.markdown(f"#### Part {part_num}: {part.title}{validation_status}")
                    
                    for field in sorted(quest_fields, key=lambda f: st.session_state.processor.agent._get_sort_key(f.number)):
                        validation_indicator = "✅" if field.is_validated else "⚠️" if field.validation_result and not field.validation_result.is_valid else ""
                        
                        st.markdown(f"**{validation_indicator} {field.number}. {field.label}**")
                        
                        # Field input (same logic as before)
                        if field.field_type in ["checkbox", "choice"] or field.is_choice:
                            field.value = st.checkbox(f"Select", key=f"quest_{field.unique_id}")
                        elif field.field_type == "date":
                            field.value = st.date_input(f"Enter date", key=f"quest_{field.unique_id}")
                            field.value = str(field.value) if field.value else ""
                        else:
                            field.value = st.text_input(f"Enter value", key=f"quest_{field.unique_id}")
                        
                        st.markdown("---")
            
            if not any(f.in_questionnaire for p in form.parts.values() for f in p.fields):
                st.info("No fields added to questionnaire. Use the Field Mapping tab to add fields.")
        else:
            st.info("👆 Upload and process a USCIS form first")
    
    with tab5:
        # Export tab with validation data
        if st.session_state.form:
            st.markdown("### 💾 Enhanced Export Options")
            
            form = st.session_state.form
            
            # Export validation report
            if form.validation_results:
                validation_export = {
                    "form_info": {
                        "form_number": form.form_number,
                        "title": form.title,
                        "overall_validation_score": form.overall_validation_score
                    },
                    "validation_summary": {
                        check: {
                            "is_valid": result.is_valid,
                            "confidence": result.confidence,
                            "issues": result.issues,
                            "suggestions": result.suggestions
                        }
                        for check, result in form.validation_results.items()
                    },
                    "part_validations": {
                        str(part.number): {
                            "title": part.title,
                            "validation_score": part.validation.validation_score if part.validation else 0,
                            "is_complete": part.validation.is_complete if part.validation else False,
                            "field_count": len([f for f in part.fields if not f.is_subfield]),
                            "missing_patterns": part.validation.missing_patterns if part.validation else []
                        }
                        for part in form.parts.values()
                    }
                }
                
                st.download_button(
                    "📋 Download Validation Report",
                    json.dumps(validation_export, indent=2, default=str),
                    f"{form.form_number}_validation_report.json",
                    "application/json",
                    type="secondary",
                    use_container_width=True
                )
            
            st.markdown("#### Standard Export Options")
            # ... rest of export logic same as before
            
        else:
            st.info("👆 Upload and process a USCIS form first")

if __name__ == "__main__":
    main()
