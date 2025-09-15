#!/usr/bin/env python3
"""
UNIVERSAL USCIS FORM READER - FINAL DEBUGGED VERSION
=====================================================
Enhanced with debugging, improved part detection, and proper subfield creation
"""

import streamlit as st
import json
import re
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field as dataclass_field, asdict
import uuid
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Page config
st.set_page_config(
    page_title="Universal USCIS Reader - Debugged",
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
    .debug-panel {
        background: #fffde7;
        border: 2px solid #ffc107;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
        font-family: monospace;
        font-size: 0.9em;
    }
    .part-header {
        background: #e3f2fd;
        border: 2px solid #2196f3;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
        font-weight: bold;
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
    .field-mapped {
        border-right: 4px solid #4caf50;
    }
    .extraction-stats {
        background: #e8f5e9;
        border: 1px solid #4caf50;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# ===== DATA STRUCTURES =====

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
    parent_number: str = ""
    subfield_letter: str = ""
    
    # Subfields
    subfields: List['USCISField'] = dataclass_field(default_factory=list)
    
    # Mapping
    is_mapped: bool = False
    db_object: str = ""
    db_field: str = ""
    
    # Value
    value: str = ""
    
    # Debug info
    extraction_method: str = ""
    match_position: int = 0
    raw_text: str = ""
    
    # System
    unique_id: str = dataclass_field(default_factory=lambda: str(uuid.uuid4())[:8])

@dataclass
class FormPart:
    """Form part structure"""
    number: int
    title: str
    fields: List[USCISField] = dataclass_field(default_factory=list)
    raw_text: str = ""
    extraction_stats: Dict[str, Any] = dataclass_field(default_factory=dict)

@dataclass
class USCISForm:
    """USCIS form container"""
    form_number: str = "Unknown"
    title: str = "USCIS Form"
    total_pages: int = 0
    parts: Dict[int, FormPart] = dataclass_field(default_factory=dict)
    debug_log: List[str] = dataclass_field(default_factory=list)

# ===== DATABASE SCHEMA =====

DATABASE_SCHEMA = {
    "beneficiary": {
        "label": "👤 Beneficiary/Applicant",
        "fields": [
            "beneficiaryLastName",
            "beneficiaryFirstName", 
            "beneficiaryMiddleName",
            "beneficiaryDateOfBirth",
            "beneficiaryCountryOfBirth",
            "beneficiaryAlienNumber",
            "beneficiaryUSCISNumber",
            "beneficiarySSN",
            "beneficiaryStreetNumberAndName",
            "beneficiaryAptSteFlr",
            "beneficiaryCityOrTown",
            "beneficiaryState",
            "beneficiaryZipCode",
            "beneficiaryCountry",
            "beneficiaryDaytimePhone",
            "beneficiaryMobilePhone",
            "beneficiaryEmail"
        ]
    },
    "petitioner": {
        "label": "🏢 Petitioner/Employer",
        "fields": [
            "petitionerLastName",
            "petitionerFirstName",
            "petitionerMiddleName",
            "petitionerCompanyName",
            "petitionerStreetNumberAndName",
            "petitionerAptSteFlr",
            "petitionerCityOrTown",
            "petitionerState",
            "petitionerZipCode",
            "petitionerCountry",
            "petitionerDaytimePhone",
            "petitionerEmail",
            "petitionerFEIN",
            "petitionerSSN"
        ]
    },
    "attorney": {
        "label": "⚖️ Attorney/Representative",
        "fields": [
            "attorneyLastName",
            "attorneyFirstName",
            "attorneyMiddleName",
            "attorneyOrganizationName",
            "attorneyBarNumber",
            "attorneyUSCISNumber",
            "attorneyStreetNumberAndName",
            "attorneyCityOrTown",
            "attorneyState",
            "attorneyZipCode",
            "attorneyCountry",
            "attorneyDaytimePhone",
            "attorneyEmail"
        ]
    },
    "preparer": {
        "label": "📝 Preparer",
        "fields": [
            "preparerLastName",
            "preparerFirstName",
            "preparerOrganizationName",
            "preparerStreetNumberAndName",
            "preparerCityOrTown",
            "preparerState",
            "preparerZipCode",
            "preparerDaytimePhone",
            "preparerEmail"
        ]
    },
    "custom": {
        "label": "✏️ Custom Fields",
        "fields": []
    }
}

# ===== ENHANCED DEBUGGING AGENT =====

class DebugAgent:
    """Debugging agent for troubleshooting extraction issues"""
    
    def __init__(self):
        self.logs = []
        self.stats = {
            "parts_found": 0,
            "fields_extracted": 0,
            "subfields_created": 0,
            "patterns_matched": {}
        }
    
    def log(self, message: str, level: str = "INFO"):
        """Add debug log entry"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        log_entry = f"[{timestamp}] [{level}] {message}"
        self.logs.append(log_entry)
        logger.log(getattr(logging, level), message)
    
    def log_pattern_match(self, pattern_name: str, text_snippet: str, position: int):
        """Log successful pattern match"""
        self.log(f"Pattern '{pattern_name}' matched at position {position}: {text_snippet[:100]}", "DEBUG")
        if pattern_name not in self.stats["patterns_matched"]:
            self.stats["patterns_matched"][pattern_name] = 0
        self.stats["patterns_matched"][pattern_name] += 1
    
    def get_summary(self) -> str:
        """Get debugging summary"""
        summary = [
            f"Parts Found: {self.stats['parts_found']}",
            f"Fields Extracted: {self.stats['fields_extracted']}",
            f"Subfields Created: {self.stats['subfields_created']}",
            "Pattern Matches:"
        ]
        for pattern, count in self.stats["patterns_matched"].items():
            summary.append(f"  - {pattern}: {count}")
        return "\n".join(summary)

# ===== UNIVERSAL AI AGENT =====

class UniversalUSCISAgent:
    """Enhanced AI agent with debugging"""
    
    def __init__(self, debug_agent: DebugAgent):
        self.client = None
        self.debug = debug_agent
        self.setup_client()
    
    def setup_client(self):
        """Setup Anthropic client"""
        if not ANTHROPIC_AVAILABLE:
            self.debug.log("Anthropic not available", "WARNING")
            return False
        
        try:
            api_key = st.secrets.get("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                self.client = anthropic.Anthropic(api_key=api_key)
                self.debug.log("Anthropic client initialized", "INFO")
                return True
        except Exception as e:
            self.debug.log(f"Claude API setup failed: {e}", "ERROR")
        return False
    
    def extract_all_parts(self, text: str) -> List[Dict]:
        """Enhanced part extraction with multiple pattern strategies"""
        self.debug.log("Starting comprehensive part extraction", "INFO")
        parts = []
        seen_parts = set()
        
        # Strategy 1: Standard Part patterns
        patterns = [
            (r'Part\s+(\d+)[\s\.\-–]*([^\n]{0,200})', 'standard_part'),
            (r'PART\s+(\d+)[\s\.\-–]*([^\n]{0,200})', 'uppercase_part'),
            (r'Part\s+([IVX]+)[\s\.\-–]*([^\n]{0,200})', 'roman_part'),
            (r'Section\s+(\d+)[\s\.\-–]*([^\n]{0,200})', 'section'),
            (r'Chapter\s+(\d+)[\s\.\-–]*([^\n]{0,200})', 'chapter'),
            (r'^(\d+)\.\s+([A-Z][^\n]{10,100})', 'numbered_section'),
        ]
        
        for pattern_str, pattern_name in patterns:
            matches = re.finditer(pattern_str, text, re.MULTILINE | re.IGNORECASE)
            for match in matches:
                try:
                    part_num_str = match.group(1)
                    
                    # Convert roman numerals if needed
                    if pattern_name == 'roman_part':
                        part_num = self._roman_to_int(part_num_str)
                    else:
                        part_num = int(part_num_str) if part_num_str.isdigit() else 0
                    
                    if part_num > 0 and part_num not in seen_parts and part_num <= 20:
                        title = match.group(2).strip() if len(match.groups()) > 1 else f"Section {part_num}"
                        title = re.sub(r'[\s\.\-–]+$', '', title)
                        
                        parts.append({
                            "number": part_num,
                            "title": title,
                            "pattern": pattern_name,
                            "position": match.start()
                        })
                        seen_parts.add(part_num)
                        self.debug.log_pattern_match(pattern_name, match.group(0), match.start())
                        
                except Exception as e:
                    self.debug.log(f"Error processing match: {e}", "WARNING")
                    continue
        
        # Strategy 2: Use AI if we have the client
        if self.client and len(parts) < 3:
            self.debug.log("Using AI for enhanced part detection", "INFO")
            ai_parts = self._ai_extract_parts(text[:5000])
            for ai_part in ai_parts:
                if ai_part["number"] not in seen_parts:
                    parts.append(ai_part)
                    seen_parts.add(ai_part["number"])
        
        # Strategy 3: Fallback - create parts based on content indicators
        if len(parts) == 0:
            self.debug.log("Using fallback part creation", "WARNING")
            parts = self._create_fallback_parts(text)
        
        # Sort parts by position or number
        parts.sort(key=lambda x: (x.get("position", 0), x["number"]))
        
        self.debug.stats["parts_found"] = len(parts)
        self.debug.log(f"Total parts extracted: {len(parts)}", "INFO")
        
        return parts
    
    def _roman_to_int(self, roman: str) -> int:
        """Convert roman numerals to integer"""
        values = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
        total = 0
        prev_value = 0
        for char in reversed(roman.upper()):
            value = values.get(char, 0)
            if value < prev_value:
                total -= value
            else:
                total += value
            prev_value = value
        return total
    
    def _ai_extract_parts(self, text: str) -> List[Dict]:
        """Use AI to extract parts"""
        if not self.client:
            return []
        
        prompt = f"""Analyze this USCIS form and identify ALL parts/sections.
Return a JSON array with all parts found:
[{{"number": 1, "title": "Part title", "pattern": "ai_extracted"}}]

Text: {text}"""
        
        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = response.content[0].text
            if "[" in content:
                json_start = content.find("[")
                json_end = content.rfind("]") + 1
                return json.loads(content[json_start:json_end])
        except Exception as e:
            self.debug.log(f"AI extraction error: {e}", "ERROR")
        
        return []
    
    def _create_fallback_parts(self, text: str) -> List[Dict]:
        """Create parts based on content indicators"""
        parts = []
        
        # Look for common section indicators
        indicators = [
            ("information about you", "Information About You"),
            ("petitioner information", "Petitioner Information"),
            ("beneficiary information", "Beneficiary Information"),
            ("employment information", "Employment Information"),
            ("additional information", "Additional Information"),
            ("preparer", "Preparer Information"),
            ("attorney", "Attorney Information"),
            ("signature", "Signatures"),
            ("certification", "Certification")
        ]
        
        part_num = 1
        for indicator, title in indicators:
            if re.search(indicator, text, re.IGNORECASE):
                parts.append({
                    "number": part_num,
                    "title": title,
                    "pattern": "content_based",
                    "position": 0
                })
                part_num += 1
        
        # If still no parts, create a default
        if not parts:
            parts.append({
                "number": 1,
                "title": "Main Section",
                "pattern": "default",
                "position": 0
            })
        
        return parts
    
    def extract_part_fields(self, part_text: str, part_number: int) -> List[USCISField]:
        """Enhanced field extraction with proper subfield creation"""
        self.debug.log(f"Extracting fields for Part {part_number}", "INFO")
        fields = []
        seen_numbers = set()
        
        # Pattern list with priorities
        patterns = [
            # Main numbered fields
            (r'^(\d+)\.\s+([^\n]{3,200})', 'main_field', 1),
            (r'^\s*(\d+)\.\s+([^\n]{3,200})', 'indented_main', 1),
            
            # Subfields with letters
            (r'^(\d+)\.([a-z])\.\s+([^\n]{3,200})', 'standard_subfield', 2),
            (r'^\s*([a-z])\.\s+([^\n]{3,200})', 'letter_only', 3),
            (r'^(\d+)([a-z])\.\s+([^\n]{3,200})', 'compact_subfield', 2),
            
            # Special patterns
            (r'Item\s+Number\s+(\d+)\.?\s*([^\n]{3,200})', 'item_number', 1),
            (r'Question\s+(\d+)\.?\s*([^\n]{3,200})', 'question', 1),
        ]
        
        # Extract all fields
        for pattern_str, pattern_name, priority in patterns:
            matches = re.finditer(pattern_str, part_text, re.MULTILINE | re.IGNORECASE)
            
            for match in matches:
                field_data = self._process_field_match(match, pattern_name, part_number, seen_numbers)
                if field_data:
                    fields.append(field_data)
                    self.debug.stats["fields_extracted"] += 1
        
        # Apply intelligent subfield creation rules
        fields = self._apply_subfield_rules(fields, part_number)
        
        # Sort fields
        fields.sort(key=lambda f: self._get_sort_key(f.number))
        
        self.debug.log(f"Extracted {len(fields)} fields from Part {part_number}", "INFO")
        return fields
    
    def _process_field_match(self, match, pattern_name: str, part_number: int, seen_numbers: set) -> Optional[USCISField]:
        """Process a regex match into a field"""
        try:
            if pattern_name in ['standard_subfield', 'compact_subfield']:
                parent_num = match.group(1)
                letter = match.group(2)
                label = match.group(3).strip()
                number = f"{parent_num}.{letter}"
                is_subfield = True
                parent_number = parent_num
                subfield_letter = letter
            elif pattern_name == 'letter_only':
                # Find parent from context
                letter = match.group(1)
                label = match.group(2).strip()
                # This needs context - skip for now
                return None
            else:
                number = match.group(1)
                label = match.group(2).strip() if len(match.groups()) > 1 else f"Field {number}"
                is_subfield = False
                parent_number = ""
                subfield_letter = ""
            
            if number in seen_numbers:
                return None
            seen_numbers.add(number)
            
            # Clean label
            label = re.sub(r'\s+', ' ', label)
            label = re.sub(r'^[.\-–\s]+', '', label)
            label = re.sub(r'[.\s]+$', '', label)
            
            if len(label) < 3:
                return None
            
            field = USCISField(
                number=number,
                label=label,
                part_number=part_number,
                is_subfield=is_subfield,
                parent_number=parent_number,
                subfield_letter=subfield_letter,
                extraction_method=pattern_name,
                match_position=match.start(),
                raw_text=match.group(0)
            )
            
            # Determine if this should be a parent field
            if self._should_be_parent(label):
                field.is_parent = True
                field.field_type = "parent"
            
            return field
            
        except Exception as e:
            self.debug.log(f"Error processing field match: {e}", "WARNING")
            return None
    
    def _should_be_parent(self, label: str) -> bool:
        """Determine if a field should be a parent with subfields"""
        label_lower = label.lower()
        
        parent_indicators = [
            "name", "full name", "legal name", "your name",
            "address", "mailing address", "physical address", "current address",
            "contact information", "phone", "telephone",
            "employment information", "employer information",
            "beneficiary information", "petitioner information"
        ]
        
        return any(indicator in label_lower for indicator in parent_indicators)
    
    def _apply_subfield_rules(self, fields: List[USCISField], part_number: int) -> List[USCISField]:
        """Apply intelligent subfield creation rules"""
        self.debug.log("Applying subfield creation rules", "DEBUG")
        new_fields = []
        
        for field in fields:
            if field.is_parent:
                label_lower = field.label.lower()
                created_subfields = []
                
                # Name fields
                if any(word in label_lower for word in ["name", "full name", "legal name"]):
                    subfield_specs = [
                        ("a", "Family Name (Last Name)"),
                        ("b", "Given Name (First Name)"),
                        ("c", "Middle Name (if applicable)")
                    ]
                    created_subfields = self._create_subfields(field, subfield_specs, part_number)
                
                # Address fields
                elif any(word in label_lower for word in ["address", "mailing", "physical"]):
                    subfield_specs = [
                        ("a", "Street Number and Name"),
                        ("b", "Apt/Ste/Flr Number (if applicable)"),
                        ("c", "City or Town"),
                        ("d", "State"),
                        ("e", "ZIP Code")
                    ]
                    if "foreign" in label_lower or "country" in label_lower:
                        subfield_specs.extend([
                            ("f", "Province (if applicable)"),
                            ("g", "Postal Code"),
                            ("h", "Country")
                        ])
                    created_subfields = self._create_subfields(field, subfield_specs, part_number)
                
                # Contact information
                elif "contact" in label_lower or "phone" in label_lower:
                    subfield_specs = [
                        ("a", "Daytime Phone Number"),
                        ("b", "Mobile Phone Number (if applicable)"),
                        ("c", "Email Address (if applicable)")
                    ]
                    created_subfields = self._create_subfields(field, subfield_specs, part_number)
                
                # Add created subfields
                new_fields.extend(created_subfields)
                self.debug.stats["subfields_created"] += len(created_subfields)
                
                # Update field's subfields list
                field.subfields = created_subfields
        
        # Combine original fields with new subfields
        all_fields = fields + new_fields
        
        # Remove duplicates based on number
        seen = set()
        unique_fields = []
        for field in all_fields:
            if field.number not in seen:
                seen.add(field.number)
                unique_fields.append(field)
        
        return unique_fields
    
    def _create_subfields(self, parent_field: USCISField, specs: List[Tuple[str, str]], part_number: int) -> List[USCISField]:
        """Create subfields for a parent field"""
        subfields = []
        
        for letter, label in specs:
            subfield = USCISField(
                number=f"{parent_field.number}.{letter}",
                label=label,
                part_number=part_number,
                is_subfield=True,
                parent_number=parent_field.number,
                subfield_letter=letter,
                extraction_method="rule_based"
            )
            subfields.append(subfield)
        
        return subfields
    
    def _get_sort_key(self, number: str) -> Tuple:
        """Get sort key for field number"""
        try:
            parts = number.replace('-', '.').split('.')
            main = int(parts[0]) if parts[0].isdigit() else 999
            
            sub = 0
            if len(parts) > 1 and parts[1]:
                if parts[1][0].isalpha():
                    sub = ord(parts[1][0].lower()) - ord('a') + 1
                elif parts[1].isdigit():
                    sub = int(parts[1])
            
            return (main, sub)
        except:
            return (999, 0)

# ===== FORM PROCESSOR =====

class UniversalFormProcessor:
    """Form processor with debugging"""
    
    def __init__(self):
        self.debug_agent = DebugAgent()
        self.agent = UniversalUSCISAgent(self.debug_agent)
    
    def process_pdf(self, pdf_file) -> Optional[USCISForm]:
        """Process PDF with comprehensive debugging"""
        if not PYMUPDF_AVAILABLE:
            st.error("PyMuPDF not available")
            return None
        
        self.debug_agent.log("Starting PDF processing", "INFO")
        
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
            
            self.debug_agent.log(f"Extracted {len(full_text)} characters from {total_pages} pages", "INFO")
            
        except Exception as e:
            self.debug_agent.log(f"PDF extraction error: {e}", "ERROR")
            return None
        
        # Create form object
        form = USCISForm(
            form_number="Unknown",
            title="USCIS Form",
            total_pages=total_pages,
            debug_log=self.debug_agent.logs
        )
        
        # Extract all parts
        with st.spinner("🔍 Detecting all form parts..."):
            parts_data = self.agent.extract_all_parts(full_text)
            
            if not parts_data:
                self.debug_agent.log("No parts detected, creating default", "WARNING")
                parts_data = [{"number": 1, "title": "Main Section", "pattern": "default"}]
        
        # Process each part
        for part_info in parts_data:
            part_text = self._extract_part_text(full_text, part_info["number"], len(parts_data))
            
            with st.spinner(f"📋 Processing Part {part_info['number']}: {part_info['title']}"):
                fields = self.agent.extract_part_fields(part_text, part_info["number"])
            
            part = FormPart(
                number=part_info["number"],
                title=part_info["title"],
                fields=fields,
                raw_text=part_text[:1000],  # Store first 1000 chars for debugging
                extraction_stats={
                    "pattern": part_info.get("pattern", "unknown"),
                    "field_count": len(fields),
                    "parent_fields": len([f for f in fields if f.is_parent]),
                    "subfields": len([f for f in fields if f.is_subfield])
                }
            )
            
            form.parts[part.number] = part
        
        self.debug_agent.log(f"Processing complete: {len(form.parts)} parts, {sum(len(p.fields) for p in form.parts.values())} total fields", "INFO")
        
        return form
    
    def _extract_part_text(self, full_text: str, part_number: int, total_parts: int) -> str:
        """Extract text for a specific part"""
        self.debug_agent.log(f"Extracting text for Part {part_number}", "DEBUG")
        
        # Find start position
        patterns = [
            rf"Part\s+{part_number}\b",
            rf"PART\s+{part_number}\b",
            rf"Section\s+{part_number}\b"
        ]
        
        start_pos = -1
        for pattern in patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                start_pos = match.start()
                self.debug_agent.log(f"Found Part {part_number} at position {start_pos}", "DEBUG")
                break
        
        if start_pos == -1:
            # Estimate position based on part number
            chunk_size = len(full_text) // max(total_parts, 1)
            start_pos = (part_number - 1) * chunk_size
            self.debug_agent.log(f"Estimated Part {part_number} position at {start_pos}", "WARNING")
        
        # Find end position (start of next part)
        end_pos = len(full_text)
        for next_part in range(part_number + 1, part_number + 5):
            for pattern in patterns:
                next_pattern = pattern.replace(str(part_number), str(next_part))
                match = re.search(next_pattern, full_text[start_pos:], re.IGNORECASE)
                if match:
                    end_pos = start_pos + match.start()
                    self.debug_agent.log(f"Found Part {next_part} at position {end_pos}", "DEBUG")
                    break
            if end_pos < len(full_text):
                break
        
        return full_text[start_pos:end_pos]

# ===== UI FUNCTIONS =====

def display_field_with_mapping(field: USCISField, prefix: str):
    """Display field with database mapping dropdown"""
    unique_key = f"{prefix}_{field.unique_id}"
    
    # Style based on field type
    if field.is_parent:
        css_class = "field-parent"
        icon = "📁"
    elif field.is_subfield:
        css_class = "field-subfield"
        icon = "↳"
    else:
        css_class = "field-card"
        icon = "📝"
    
    if field.is_mapped:
        css_class += " field-mapped"
    
    st.markdown(f'<div class="{css_class}">', unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
    
    with col1:
        st.markdown(f"**{icon} {field.number}. {field.label}**")
        if field.extraction_method:
            st.caption(f"Method: {field.extraction_method}")
    
    with col2:
        if not field.is_parent:
            field.value = st.text_input("Value", value=field.value, 
                                       key=f"{unique_key}_val", 
                                       label_visibility="collapsed")
    
    with col3:
        if not field.is_parent:
            # Database object dropdown
            db_objects = list(DATABASE_SCHEMA.keys())
            selected_obj = st.selectbox(
                "DB Object",
                ["None"] + db_objects,
                index=0 if not field.db_object else db_objects.index(field.db_object) + 1,
                key=f"{unique_key}_obj",
                label_visibility="collapsed",
                format_func=lambda x: DATABASE_SCHEMA[x]["label"] if x != "None" else "Select Object"
            )
            
            if selected_obj != "None":
                field.db_object = selected_obj
                field.is_mapped = True
    
    with col4:
        if field.db_object and field.db_object != "None":
            # Database field dropdown
            db_fields = DATABASE_SCHEMA[field.db_object]["fields"]
            
            if field.db_object == "custom":
                field.db_field = st.text_input("Custom Field", 
                                              value=field.db_field,
                                              key=f"{unique_key}_field",
                                              label_visibility="collapsed")
            else:
                selected_field = st.selectbox(
                    "DB Field",
                    [""] + db_fields,
                    index=0 if not field.db_field else db_fields.index(field.db_field) + 1 if field.db_field in db_fields else 0,
                    key=f"{unique_key}_field",
                    label_visibility="collapsed"
                )
                field.db_field = selected_field
    
    st.markdown('</div>', unsafe_allow_html=True)

def display_debug_panel(debug_agent: DebugAgent):
    """Display debugging information"""
    with st.expander("🔍 Debug Information", expanded=False):
        st.markdown('<div class="debug-panel">', unsafe_allow_html=True)
        
        # Summary stats
        st.markdown("### Extraction Summary")
        st.text(debug_agent.get_summary())
        
        # Recent logs
        st.markdown("### Recent Logs")
        for log in debug_agent.logs[-20:]:  # Show last 20 logs
            st.text(log)
        
        st.markdown('</div>', unsafe_allow_html=True)

# ===== MAIN APPLICATION =====

def main():
    st.markdown("""
    <div class="main-header">
        <h1>🔍 Universal USCIS Reader - Debugged Version</h1>
        <p>Enhanced with debugging and improved part/field extraction</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize
    if 'processor' not in st.session_state:
        st.session_state.processor = UniversalFormProcessor()
    if 'form' not in st.session_state:
        st.session_state.form = None
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 📊 Processing Stats")
        
        if st.session_state.form:
            form = st.session_state.form
            
            st.metric("Total Parts", len(form.parts))
            
            total_fields = sum(len(p.fields) for p in form.parts.values())
            parent_fields = sum(len([f for f in p.fields if f.is_parent]) for p in form.parts.values())
            subfields = sum(len([f for f in p.fields if f.is_subfield]) for p in form.parts.values())
            mapped_fields = sum(len([f for f in p.fields if f.is_mapped]) for p in form.parts.values())
            
            st.metric("Total Fields", total_fields)
            st.metric("Parent Fields", parent_fields)
            st.metric("Subfields", subfields)
            st.metric("Mapped Fields", mapped_fields)
            
            # Part breakdown
            st.markdown("### Parts Found:")
            for part_num, part in sorted(form.parts.items()):
                st.info(f"**Part {part_num}**: {part.title}\n- Fields: {len(part.fields)}")
        
        if st.button("🔄 Reset", use_container_width=True):
            st.session_state.clear()
            st.rerun()
    
    # Main tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📤 Upload", "🗂️ Field Mapping", "🔍 Debug", "💾 Export"])
    
    with tab1:
        st.markdown("### Upload USCIS Form PDF")
        
        uploaded_file = st.file_uploader("Choose PDF file", type=['pdf'])
        
        if uploaded_file:
            if st.button("🚀 Process with Debugging", type="primary", use_container_width=True):
                form = st.session_state.processor.process_pdf(uploaded_file)
                
                if form:
                    st.session_state.form = form
                    st.success(f"✅ Successfully processed form with {len(form.parts)} parts")
                    
                    # Show extraction stats
                    st.markdown('<div class="extraction-stats">', unsafe_allow_html=True)
                    st.markdown("### Extraction Results")
                    
                    for part_num, part in sorted(form.parts.items()):
                        st.markdown(f'<div class="part-header">', unsafe_allow_html=True)
                        st.markdown(f"**Part {part_num}: {part.title}**")
                        
                        stats = part.extraction_stats
                        st.markdown(f"""
                        - Pattern: {stats.get('pattern', 'unknown')}
                        - Total Fields: {stats.get('field_count', 0)}
                        - Parent Fields: {stats.get('parent_fields', 0)}
                        - Subfields: {stats.get('subfields', 0)}
                        """)
                        st.markdown('</div>', unsafe_allow_html=True)
                    
                    st.markdown('</div>', unsafe_allow_html=True)
                else:
                    st.error("Failed to process form")
    
    with tab2:
        if st.session_state.form:
            st.markdown("### Map Fields to Database")
            
            form = st.session_state.form
            
            # Part selector
            part_numbers = sorted(form.parts.keys())
            selected_part = st.selectbox(
                "Select Part",
                part_numbers,
                format_func=lambda x: f"Part {x}: {form.parts[x].title}"
            )
            
            if selected_part:
                part = form.parts[selected_part]
                
                st.markdown(f"#### Part {part.number}: {part.title}")
                st.info(f"Total fields in this part: {len(part.fields)}")
                
                # Display fields hierarchically
                displayed = set()
                for field in sorted(part.fields, key=lambda f: st.session_state.processor.agent._get_sort_key(f.number)):
                    if field.number not in displayed:
                        # Display parent or standalone field
                        if field.is_parent or not field.is_subfield:
                            display_field_with_mapping(field, f"map_p{part.number}")
                            displayed.add(field.number)
                            
                            # Display its subfields
                            for child in part.fields:
                                if child.parent_number == field.number and child.number not in displayed:
                                    display_field_with_mapping(child, f"map_p{part.number}")
                                    displayed.add(child.number)
        else:
            st.info("Upload and process a form first")
    
    with tab3:
        st.markdown("### Debug Information")
        
        if st.session_state.processor:
            display_debug_panel(st.session_state.processor.debug_agent)
        
        if st.session_state.form and st.session_state.form.debug_log:
            st.markdown("### Form Processing Log")
            st.text_area("Processing Log", "\n".join(st.session_state.form.debug_log[-50:]), height=300)
    
    with tab4:
        if st.session_state.form:
            st.markdown("### Export Data")
            
            form = st.session_state.form
            
            # Create export data
            export_data = {
                "form_info": {
                    "total_pages": form.total_pages,
                    "total_parts": len(form.parts)
                },
                "parts": {}
            }
            
            for part_num, part in form.parts.items():
                export_data["parts"][part_num] = {
                    "title": part.title,
                    "extraction_stats": part.extraction_stats,
                    "fields": [
                        {
                            "number": f.number,
                            "label": f.label,
                            "type": f.field_type,
                            "value": f.value,
                            "is_parent": f.is_parent,
                            "is_subfield": f.is_subfield,
                            "parent_number": f.parent_number,
                            "db_object": f.db_object,
                            "db_field": f.db_field,
                            "extraction_method": f.extraction_method
                        }
                        for f in part.fields
                    ]
                }
            
            # Export button
            json_str = json.dumps(export_data, indent=2)
            st.download_button(
                "📥 Download Complete Analysis",
                json_str,
                "uscis_form_analysis.json",
                "application/json"
            )
            
            # Show mapped fields summary
            st.markdown("### Mapped Fields Summary")
            for part_num, part in form.parts.items():
                mapped = [f for f in part.fields if f.is_mapped and not f.is_parent]
                if mapped:
                    st.markdown(f"**Part {part_num}:**")
                    for field in mapped:
                        st.write(f"- {field.number}. {field.label} → {field.db_object}.{field.db_field}")
        else:
            st.info("Process a form to export data")

if __name__ == "__main__":
    main()
