#!/usr/bin/env python3
"""
UNIVERSAL USCIS FORM READER - FIXED VERSION
===========================================
Fixed: Proper field sorting and DB object display
"""

# Standard library imports
import json
import re
import uuid
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field as dataclass_field

# Third-party imports
import streamlit as st

# Try to import Anthropic
try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

# Page configuration
st.set_page_config(
    page_title="USCIS Form Reader",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
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
    .field-container {
        background: white;
        border-radius: 8px;
        padding: 12px;
        margin: 8px 0;
        border: 1px solid #e0e0e0;
        border-left: 4px solid #e0e0e0;
    }
    .field-parent {
        border-left-color: #667eea;
        background: #f8f9ff;
        font-weight: 600;
    }
    .field-subfield {
        margin-left: 30px;
        border-left-color: #a8b4ff;
        background: #fafbff;
    }
    .field-mapped {
        background: #e8f5e9;
        border-left-color: #4caf50;
    }
    .field-questionnaire {
        background: #fff8e1;
        border-left-color: #ffc107;
    }
    .field-number-badge {
        background: #667eea;
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.85em;
        font-weight: bold;
        margin-right: 8px;
        display: inline-block;
    }
    .mapping-dialog {
        background: #f5f5f5;
        padding: 15px;
        border-radius: 8px;
        margin-top: 10px;
    }
    .subfield-indicator {
        color: #666;
        font-size: 0.9em;
        margin-left: 5px;
    }
    .db-object-card {
        background: white;
        padding: 10px;
        border-radius: 6px;
        margin-bottom: 8px;
        border: 1px solid #e0e0e0;
        cursor: pointer;
    }
    .db-object-card:hover {
        background: #f8f9ff;
        border-color: #667eea;
    }
    .db-object-selected {
        background: #e8f5e9;
        border-color: #4caf50;
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

@dataclass
class FormField:
    """Form field structure with complete hierarchy support"""
    number: str
    label: str
    field_type: str = "text"  # text, date, checkbox, ssn, ein, parent, etc.
    value: Any = ""
    
    # Hierarchy
    part_number: int = 1
    parent_number: Optional[str] = None
    is_parent: bool = False
    is_subfield: bool = False
    subfield_letter: Optional[str] = None  # a, b, c, etc.
    choices: List[FieldChoice] = dataclass_field(default_factory=list)
    
    # Mapping
    is_mapped: bool = False
    db_object: str = ""
    db_path: str = ""
    
    # Questionnaire
    in_questionnaire: bool = False
    
    # Metadata
    extraction_method: str = "pattern"
    position: int = 0
    context: str = ""
    
    def get_unique_key(self) -> str:
        """Generate unique key for this field"""
        unique_str = f"{self.part_number}_{self.number}_{uuid.uuid4().hex[:8]}"
        return hashlib.md5(unique_str.encode()).hexdigest()[:12]
    
    def get_sort_key(self) -> Tuple:
        """Get sort key for proper numerical ordering - handle all formats"""
        try:
            # Remove any non-alphanumeric characters for parsing
            clean_number = self.number.replace('-', '.').replace('(', '').replace(')', '')
            
            # Split into parts
            parts = clean_number.split('.')
            
            # Main number
            main_num = 999999  # Default for non-numeric
            if parts[0]:
                # Extract just the numeric part
                numeric_match = re.match(r'^(\d+)', parts[0])
                if numeric_match:
                    main_num = int(numeric_match.group(1))
            
            # Sub part (letter or number)
            sub_num = 0
            if len(parts) > 1 and parts[1]:
                sub_part = parts[1].strip()
                if sub_part:
                    if sub_part[0].isalpha():
                        # Letter subfield (a, b, c -> 1, 2, 3)
                        sub_num = ord(sub_part[0].lower()) - ord('a') + 1
                    elif sub_part.isdigit():
                        # Numeric subfield
                        sub_num = int(sub_part) + 100  # Offset to come after letters
                    else:
                        # Mixed or other
                        sub_num = 500
            
            # Use position as final tiebreaker
            return (main_num, sub_num, self.position)
            
        except Exception as e:
            # Fallback for any parsing errors
            print(f"Sort key error for {self.number}: {e}")
            return (999999, 0, self.position)
    
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
            data["choices"] = [
                {"letter": c.letter, "text": c.text, "selected": c.selected}
                for c in self.choices
            ]
        
        if self.is_mapped:
            data["mapping"] = {
                "object": self.db_object,
                "path": self.db_path
            }
        
        if self.parent_number:
            data["parent"] = self.parent_number
        
        return data

@dataclass
class FormPart:
    """Form part/section"""
    number: int
    title: str
    fields: List[FormField] = dataclass_field(default_factory=list)
    
    def get_stats(self) -> Dict:
        """Get statistics for this part"""
        return {
            "total_fields": len(self.fields),
            "mapped_fields": sum(1 for f in self.fields if f.is_mapped),
            "questionnaire_fields": sum(1 for f in self.fields if f.in_questionnaire),
            "parent_fields": sum(1 for f in self.fields if f.is_parent),
            "subfields": sum(1 for f in self.fields if f.is_subfield)
        }
    
    def get_field_hierarchy(self) -> Dict:
        """Get fields organized by hierarchy with proper sorting"""
        hierarchy = {}
        
        # Group parent fields
        for field in self.fields:
            if field.is_parent or (not field.parent_number and '.' not in field.number):
                hierarchy[field.number] = {
                    'field': field,
                    'children': []
                }
        
        # Assign children to parents
        for field in self.fields:
            if field.parent_number and field.parent_number in hierarchy:
                hierarchy[field.parent_number]['children'].append(field)
        
        # Sort children within each parent
        for parent_num in hierarchy:
            hierarchy[parent_num]['children'].sort(key=lambda f: f.get_sort_key())
        
        return hierarchy

# ===== DATABASE SCHEMA =====

DB_SCHEMA = {
    "beneficiary": {
        "label": "👤 Beneficiary/Applicant",
        "icon": "👤",
        "description": "Primary applicant information",
        "fields": [
            "lastName",
            "firstName", 
            "middleName",
            "otherNames",
            "alienNumber",
            "uscisNumber",
            "ssn",
            "dateOfBirth",
            "countryOfBirth",
            "cityOfBirth",
            "stateOfBirth",
            "citizenship",
            "address.street",
            "address.streetNumber",
            "address.streetName",
            "address.apartmentNumber",
            "address.apartmentType",  # Separate from apartment number
            "address.apt",
            "address.suite",
            "address.floor",
            "address.city",
            "address.state",
            "address.zip",
            "address.zipPlus4",
            "address.postalCode",
            "address.province",
            "address.country",
            "phone.daytime",
            "phone.mobile",
            "phone.evening",
            "phone.work",
            "email",
            "gender",
            "maritalStatus"
        ]
    },
    "petitioner": {
        "label": "🏢 Petitioner/Employer",
        "icon": "🏢",
        "description": "Petitioner or employer details",
        "fields": [
            "lastName",
            "firstName",
            "middleName",
            "companyName",
            "tradeName",
            "ein",
            "ssn",
            "address.street",
            "address.streetNumber",
            "address.streetName",
            "address.suite",
            "address.floor",
            "address.city",
            "address.state",
            "address.zip",
            "address.zipPlus4",
            "address.postalCode",
            "address.province",
            "address.country",
            "mailingAddress.street",
            "mailingAddress.suite",
            "mailingAddress.city",
            "mailingAddress.state",
            "mailingAddress.zip",
            "phone",
            "fax",
            "email",
            "website",
            "yearEstablished",
            "numberOfEmployees",
            "annualIncome"
        ]
    },
    "employment": {
        "label": "💼 Employment Information",
        "icon": "💼",
        "description": "Job and employment details",
        "fields": [
            "jobTitle",
            "jobCode",
            "socCode",
            "naicsCode",
            "wages.amount",
            "wages.per",
            "wages.currency",
            "hoursPerWeek",
            "startDate",
            "endDate",
            "worksite.address",
            "worksite.street",
            "worksite.suite",
            "worksite.city",
            "worksite.state",
            "worksite.zip",
            "worksite.county",
            "supervisorName",
            "supervisorTitle",
            "department"
        ]
    },
    "attorney": {
        "label": "⚖️ Attorney/Representative",
        "icon": "⚖️",
        "description": "Legal representative information",
        "fields": [
            "lastName",
            "firstName",
            "middleName",
            "firmName",
            "barNumber",
            "uscisNumber",
            "eligibilityCategory",
            "address.street",
            "address.suite",
            "address.floor",
            "address.city",
            "address.state",
            "address.zip",
            "address.country",
            "phone",
            "fax",
            "email",
            "website"
        ]
    },
    "travel": {
        "label": "✈️ Travel Information",
        "icon": "✈️",
        "description": "Travel and entry details",
        "fields": [
            "passportNumber",
            "passportCountry",
            "passportIssuedDate",
            "passportExpiryDate",
            "dateOfLastEntry",
            "placeOfLastEntry",
            "i94Number",
            "currentStatus",
            "statusExpiryDate",
            "visaNumber",
            "visaCategory"
        ]
    },
    "family": {
        "label": "👨‍👩‍👧‍👦 Family Information",
        "icon": "👨‍👩‍👧‍👦",
        "description": "Family member details",
        "fields": [
            "spouse.lastName",
            "spouse.firstName",
            "spouse.middleName",
            "spouse.dateOfBirth",
            "spouse.countryOfBirth",
            "spouse.alienNumber",
            "children[].lastName",
            "children[].firstName",
            "children[].dateOfBirth",
            "children[].countryOfBirth",
            "children[].alienNumber"
        ]
    },
    "custom": {
        "label": "✏️ Custom Fields",
        "icon": "✏️",
        "description": "User-defined custom fields",
        "fields": []
    }
}

# ===== EXTRACTION ENGINE =====

class FormExtractor:
    """Main extraction engine with enhanced subfield handling"""
    
    def __init__(self):
        self.client = None
        self.setup_client()
        
        # Common field patterns
        self.name_subfields = {
            'a': 'Family Name (Last Name)',
            'b': 'Given Name (First Name)',
            'c': 'Middle Name'
        }
        
        self.address_subfields = {
            'a': 'Street Number and Name',
            'b': 'Apt/Ste/Flr',
            'c': 'City or Town',
            'd': 'State',
            'e': 'ZIP Code',
            'f': 'Province',
            'g': 'Postal Code',
            'h': 'Country'
        }
    
    def setup_client(self):
        """Setup Anthropic client if available"""
        if not ANTHROPIC_AVAILABLE:
            st.sidebar.info("ℹ️ Pattern extraction mode (no API)")
            return
        
        try:
            api_key = st.secrets.get("ANTHROPIC_API_KEY", None)
            if api_key:
                self.client = Anthropic(api_key=api_key)
                st.sidebar.success("✅ Claude API Ready")
            else:
                st.sidebar.info("ℹ️ Add API key for enhanced extraction")
        except Exception as e:
            st.sidebar.warning(f"⚠️ API setup issue: {str(e)[:30]}")
    
    def extract_form(self, text: str) -> Dict:
        """Extract complete form data"""
        result = {
            "success": False,
            "form_number": "Unknown",
            "form_title": "USCIS Form",
            "parts": [],
            "stats": {}
        }
        
        try:
            # Extract form info
            form_info = self._extract_form_info(text)
            result.update(form_info)
            
            # Extract parts
            parts_info = self._extract_parts(text)
            
            # Process each part
            for part_info in parts_info:
                part = FormPart(
                    number=part_info["number"],
                    title=part_info["title"]
                )
                
                # Get part text
                part_text = self._get_part_text(text, part.number)
                
                # Extract fields with enhanced subfield detection
                fields = self._extract_fields_enhanced(part_text, part.number)
                
                # CRITICAL FIX: Sort fields properly using the enhanced sort key
                fields.sort(key=lambda f: f.get_sort_key())
                
                # Verify sorting for debugging
                st.sidebar.info(f"Part {part.number}: {len(fields)} fields extracted")
                
                part.fields = fields
                result["parts"].append(part)
            
            # Default part if none found
            if not result["parts"]:
                part = FormPart(number=1, title="Main Section")
                fields = self._extract_fields_enhanced(text[:15000], 1)
                fields.sort(key=lambda f: f.get_sort_key())
                part.fields = fields
                result["parts"].append(part)
            
            # Calculate stats
            result["stats"] = {
                "total_parts": len(result["parts"]),
                "total_fields": sum(len(p.fields) for p in result["parts"]),
                "parent_fields": sum(sum(1 for f in p.fields if f.is_parent) for p in result["parts"]),
                "subfields": sum(sum(1 for f in p.fields if f.is_subfield) for p in result["parts"])
            }
            
            result["success"] = True
            
        except Exception as e:
            st.error(f"Extraction error: {str(e)[:100]}")
        
        return result
    
    def _extract_form_info(self, text: str) -> Dict:
        """Extract form number and title"""
        info = {"form_number": "Unknown", "form_title": "USCIS Form"}
        
        patterns = [
            r'Form\s+([I]-\d+[A-Z]?)',
            r'USCIS\s+Form\s+([I]-\d+[A-Z]?)',
            r'([I]-\d+[A-Z]?)\s+[,\s]*'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text[:3000], re.IGNORECASE)
            if match:
                info["form_number"] = match.group(1).upper()
                info["form_title"] = f"USCIS Form {info['form_number']}"
                break
        
        return info
    
    def _extract_parts(self, text: str) -> List[Dict]:
        """Extract all parts from form"""
        parts = []
        seen = set()
        
        pattern = r'Part\s+(\d+)[.\s\-–]*([^\n]{3,100})'
        matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
        
        for match in matches:
            try:
                num = int(match.group(1))
                if num not in seen:
                    title = match.group(2).strip()
                    title = re.sub(r'^[.\-–\s]+', '', title)
                    title = re.sub(r'[.\s]+$', '', title)[:100]
                    
                    parts.append({
                        "number": num,
                        "title": title,
                        "position": match.start()
                    })
                    seen.add(num)
            except:
                continue
        
        return sorted(parts, key=lambda x: x["number"])
    
    def _get_part_text(self, text: str, part_num: int) -> str:
        """Get text for specific part"""
        pattern = f"Part\\s+{part_num}\\b"
        match = re.search(pattern, text, re.IGNORECASE)
        
        if not match:
            return text[:15000]
        
        start = match.start()
        
        # Find next part
        next_pattern = f"Part\\s+{part_num + 1}\\b"
        next_match = re.search(next_pattern, text[start:], re.IGNORECASE)
        
        if next_match:
            end = start + next_match.start()
        else:
            end = min(start + 20000, len(text))
        
        return text[start:end]
    
    def _extract_fields_enhanced(self, text: str, part_num: int) -> List[FormField]:
        """Extract fields EXACTLY as they appear - no intelligent merging"""
        # Try AI extraction if available
        if self.client:
            ai_fields = self._extract_fields_ai(text, part_num)
            if ai_fields:
                # Return AI fields WITHOUT enhancement - exactly as extracted
                return ai_fields
        
        # Pattern extraction WITHOUT enhancement - exact extraction
        pattern_fields = self._extract_fields_pattern(text, part_num)
        return pattern_fields  # Return exactly what was found, no enhancement
    
    def _extract_fields_pattern(self, text: str, part_num: int) -> List[FormField]:
        """Pattern-based extraction - EXACT extraction without assumptions"""
        fields = []
        seen = set()
        pos = 0
        
        # More comprehensive patterns to catch ALL fields
        patterns = [
            # Subfields with letters: 1.a. or 1a. or 1. a.
            (r'(\d+)\.?\s*([a-z])\.?\s+([^\n]{2,150})', 'subfield'),
            # Main fields: 1. or Item Number 1
            (r'(?:Item\s+Number\s+)?(\d+)\.?\s+([^\n]{2,150})', 'main'),
            # Fields with dashes: 1-A or 1-1
            (r'(\d+)-([A-Za-z0-9])\s+([^\n]{2,150})', 'dash_field'),
            # Standalone letters that might be subfields
            (r'^([a-z])\.?\s+([^\n]{2,150})', 'orphan'),
            # Fields starting with "Number" prefix
            (r'Number\s+(\d+)[.\s]*([^\n]{2,150})', 'number_prefix'),
            # Fields with parentheses numbers: (1) or (1a)
            (r'\((\d+[a-z]?)\)\s*([^\n]{2,150})', 'paren_field')
        ]
        
        # Process text in chunks to avoid missing fields
        text_chunks = text[:20000]  # Increased from 15000 to catch more
        
        for pattern, ftype in patterns:
            flags = re.IGNORECASE | re.MULTILINE
            matches = re.finditer(pattern, text_chunks, flags)
            
            for match in matches:
                try:
                    # Extract based on pattern type
                    if ftype == 'subfield':
                        # Check if this is actually a subfield or a main field
                        main_num = match.group(1)
                        letter = match.group(2)
                        label = match.group(3).strip()
                        
                        # Check spacing to determine if it's really a subfield
                        match_text = match.group(0)
                        if re.match(r'^\d+\.\s*[a-z]\.', match_text) or re.match(r'^\d+[a-z]\.', match_text):
                            # It's a subfield
                            number = f"{main_num}.{letter}"
                            parent = main_num
                            is_sub = True
                        else:
                            # Might be separate - check context
                            number = f"{main_num}.{letter}"
                            parent = main_num
                            is_sub = True
                            
                    elif ftype == 'dash_field':
                        main_num = match.group(1)
                        sub_part = match.group(2)
                        label = match.group(3).strip()
                        number = f"{main_num}.{sub_part}"
                        parent = main_num
                        letter = sub_part if sub_part.isalpha() else None
                        is_sub = True
                        
                    elif ftype == 'orphan':
                        # Standalone letter - find parent
                        letter = match.group(1)
                        label = match.group(2).strip()
                        
                        # Look backwards for the most recent number
                        text_before = text_chunks[:match.start()]
                        parent_matches = list(re.finditer(r'(\d+)\.?\s+[^\n]+', text_before))
                        
                        if parent_matches:
                            parent_match = parent_matches[-1]
                            parent = parent_match.group(1)
                            number = f"{parent}.{letter}"
                            is_sub = True
                        else:
                            # Can't find parent, skip
                            continue
                            
                    elif ftype == 'paren_field':
                        number = match.group(1)
                        label = match.group(2).strip()
                        parent = None
                        letter = None
                        is_sub = False
                        
                    else:  # main, number_prefix
                        number = match.group(1)
                        label = match.group(2).strip() if len(match.groups()) > 1 else f"Field {number}"
                        parent = None
                        letter = None
                        is_sub = False
                    
                    # Skip if already seen
                    if number in seen:
                        continue
                    
                    seen.add(number)
                    
                    # Clean label - minimal cleaning to preserve original
                    label = re.sub(r'\s+', ' ', label).strip()
                    
                    # Remove trailing punctuation but preserve the label
                    label = re.sub(r'[.:]+
    
    def _extract_fields_ai(self, text: str, part_num: int) -> List[FormField]:
        """AI-based extraction"""
        if not self.client:
            return []
        
        try:
            prompt = f"""Extract ALL fields from Part {part_num} of this USCIS form.

CRITICAL: Include EVERY field and subfield with exact numbering.

For fields with subparts (like names with a, b, c), mark the parent as type "parent" and include all subfields.

Return JSON array:
[
  {{"number": "1", "label": "Full Legal Name", "type": "parent", "is_parent": true}},
  {{"number": "1.a", "label": "Family Name (Last Name)", "type": "text", "parent": "1", "letter": "a"}},
  {{"number": "1.b", "label": "Given Name (First Name)", "type": "text", "parent": "1", "letter": "b"}},
  {{"number": "1.c", "label": "Middle Name", "type": "text", "parent": "1", "letter": "c"}}
]

Text:
{text[:7000]}"""
            
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=3000,
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = response.content[0].text
            
            # Extract JSON
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                
                fields = []
                pos = 0
                
                for item in data:
                    if item.get("number"):
                        field = FormField(
                            number=item["number"],
                            label=item.get("label", ""),
                            field_type=item.get("type", "text"),
                            part_number=part_num,
                            parent_number=item.get("parent"),
                            is_parent=item.get("is_parent", False),
                            is_subfield=bool(item.get("parent")),
                            subfield_letter=item.get("letter"),
                            position=pos,
                            extraction_method="AI"
                        )
                        fields.append(field)
                        pos += 1
                
                return fields
                
        except Exception as e:
            st.warning(f"AI extraction issue: {str(e)[:50]}")
        
        return []
    
    def _extract_choices(self, text: str) -> List[FieldChoice]:
        """Extract checkbox/radio options"""
        choices = []
        
        patterns = [
            r'[□☐]\s*([^\n□☐]{2,80})',
            r'\[\s*\]\s*([^\n\[\]]{2,80})',
            r'○\s*([^\n○]{2,80})'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text[:500])
            if matches and len(matches) >= 2:
                for i, txt in enumerate(matches[:6]):
                    choices.append(FieldChoice(
                        letter=chr(ord('a') + i),
                        text=txt.strip(),
                        selected=False
                    ))
                break
        
        return choices
    
    def _detect_field_type(self, label: str) -> str:
        """Detect field type from label - be specific about apartment fields"""
        lower = label.lower()
        
        # Be very specific about apartment-related fields
        if "apartment number" in lower or "apt number" in lower or "apt. number" in lower:
            return "apartment_number"
        elif "apartment type" in lower or "apt type" in lower or "unit type" in lower:
            return "apartment_type"
        elif any(w in lower for w in ["date", "birth", "expire", "issued"]):
            return "date"
        elif "email" in lower or "e-mail" in lower:
            return "email"
        elif any(w in lower for w in ["phone", "telephone", "mobile", "cell"]):
            return "phone"
        elif "ssn" in lower or "social security" in lower:
            return "ssn"
        elif "ein" in lower or "employer identification" in lower:
            return "ein"
        elif "alien number" in lower or "a-number" in lower or "uscis number" in lower:
            return "alien_number"
        elif any(w in lower for w in ["check", "select", "mark all"]):
            return "checkbox"
        elif any(w in lower for w in ["street number", "street name"]):
            return "address"
        elif any(w in lower for w in ["apt", "suite", "ste", "unit"]) and "type" not in lower:
            return "apartment"
        elif any(w in lower for w in ["floor", "flr"]):
            return "floor"
        elif any(w in lower for w in ["city", "town"]):
            return "city"
        elif "state" in lower and "united states" not in lower:
            return "state"
        elif "zip" in lower or "postal code" in lower:
            return "zip"
        elif "country" in lower:
            return "country"
        
        return "text"

# ===== PDF EXTRACTION =====

def extract_pdf_text(pdf_file) -> Tuple[str, int]:
    """Extract text from PDF"""
    try:
        # Try PyMuPDF first (better extraction)
        try:
            import fitz
            pdf_file.seek(0)
            doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
            
            text = ""
            for i in range(len(doc)):
                page = doc[i]
                text += f"\n\n=== PAGE {i+1} ===\n{page.get_text()}"
            
            pages = len(doc)
            doc.close()
            return text, pages
            
        except ImportError:
            # Fallback to PyPDF2
            import PyPDF2
            pdf_file.seek(0)
            reader = PyPDF2.PdfReader(pdf_file)
            
            text = ""
            for i, page in enumerate(reader.pages):
                text += f"\n\n=== PAGE {i+1} ===\n{page.extract_text()}"
            
            return text, len(reader.pages)
            
    except Exception as e:
        st.error(f"PDF reading error: {str(e)}")
        return "", 0

# ===== UI COMPONENTS =====

def render_field(field: FormField, key_prefix: str):
    """Render a single field with all controls"""
    unique_key = f"{key_prefix}_{field.get_unique_key()}"
    
    # Determine CSS class
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
            # Field number and label
            subfield_indicator = ""
            if field.is_subfield and field.subfield_letter:
                subfield_indicator = f'<span class="subfield-indicator">(subfield {field.subfield_letter})</span>'
            
            st.markdown(
                f'<span class="field-number-badge">{field.number}</span>'
                f'<strong>{field.label}</strong>{subfield_indicator}',
                unsafe_allow_html=True
            )
            
            # Show choices for multiple choice fields
            if field.choices:
                for choice in field.choices:
                    choice.selected = st.checkbox(
                        f"{choice.letter}. {choice.text}",
                        value=choice.selected,
                        key=f"{unique_key}_choice_{choice.letter}"
                    )
        
        with col2:
            # Value input (not for parent fields)
            if not field.is_parent and not field.choices:
                if field.field_type == "date":
                    val = st.date_input(
                        "Value",
                        key=f"{unique_key}_value",
                        label_visibility="collapsed"
                    )
                    field.value = str(val) if val else ""
                elif field.field_type == "checkbox":
                    field.value = st.checkbox(
                        "Selected",
                        key=f"{unique_key}_value"
                    )
                elif field.field_type in ["state"]:
                    # State dropdown
                    states = ["", "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", 
                             "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", 
                             "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", 
                             "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", 
                             "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"]
                    field.value = st.selectbox(
                        "State",
                        states,
                        key=f"{unique_key}_value",
                        label_visibility="collapsed"
                    )
                else:
                    field.value = st.text_input(
                        "Value",
                        value=field.value or "",
                        key=f"{unique_key}_value",
                        label_visibility="collapsed",
                        placeholder=f"Enter {field.field_type}"
                    )
        
        with col3:
            # Action buttons
            c1, c2 = st.columns(2)
            
            with c1:
                if field.is_mapped:
                    st.success(f"✓ {field.db_object}")
                else:
                    if st.button("📎 Map", key=f"{unique_key}_map_btn"):
                        st.session_state[f"mapping_{unique_key}"] = True
            
            with c2:
                quest_label = "📝 Q✓" if field.in_questionnaire else "📝 Q+"
                if st.button(quest_label, key=f"{unique_key}_quest_btn"):
                    field.in_questionnaire = not field.in_questionnaire
                    st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Mapping dialog
        if st.session_state.get(f"mapping_{unique_key}"):
            render_mapping_dialog(field, unique_key)

def render_mapping_dialog(field: FormField, unique_key: str):
    """Render mapping configuration dialog with visible DB objects"""
    st.markdown('<div class="mapping-dialog">', unsafe_allow_html=True)
    st.markdown("**🔗 Map Field to Database**")
    
    # Initialize selected object in session state if not exists
    if f"{unique_key}_selected_object" not in st.session_state:
        st.session_state[f"{unique_key}_selected_object"] = ""
    
    # Show available database objects as radio buttons (more reliable than buttons)
    st.markdown("##### Select Database Object:")
    
    db_object = st.radio(
        "Choose database object:",
        options=list(DB_SCHEMA.keys()),
        format_func=lambda x: f"{DB_SCHEMA[x]['icon']} {DB_SCHEMA[x]['label']}",
        key=f"{unique_key}_db_object_radio",
        horizontal=False
    )
    
    # Show description of selected object
    if db_object:
        st.info(f"📝 {DB_SCHEMA[db_object]['description']}")
        
        st.markdown(f"##### Map to field in {DB_SCHEMA[db_object]['label']}:")
        
        if db_object == "custom":
            # Custom field - only manual entry
            db_path = st.text_input(
                "Enter custom field path:",
                key=f"{unique_key}_map_custom",
                placeholder="e.g., customField.subField",
                help="Enter your custom field path"
            )
        else:
            # Existing DB object - show both dropdown and manual entry
            available_fields = DB_SCHEMA[db_object]["fields"]
            
            # Smart suggestion based on field label
            suggested = None
            field_label_lower = field.label.lower()
            
            for db_field in available_fields:
                db_field_lower = db_field.lower()
                # Check for matching words
                if any(word in db_field_lower for word in field_label_lower.split() if len(word) > 2):
                    suggested = db_field
                    break
            
            # Create tabs for selection method
            tab1, tab2 = st.tabs(["📋 Select from List", "✏️ Enter Manually"])
            
            with tab1:
                selected_path = st.selectbox(
                    "Choose from existing fields:",
                    [""] + available_fields,
                    index=available_fields.index(suggested) + 1 if suggested and suggested in available_fields else 0,
                    key=f"{unique_key}_map_path",
                    help="Select a predefined field"
                )
                db_path = selected_path
            
            with tab2:
                manual_path = st.text_input(
                    "Enter custom field path:",
                    key=f"{unique_key}_manual_path",
                    placeholder="e.g., address.apartmentNumber",
                    help="Type any field path you want"
                )
                if manual_path:
                    db_path = manual_path
    else:
        db_path = ""
    
    # Action buttons
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("✅ Apply Mapping", key=f"{unique_key}_apply", type="primary"):
            if db_object and db_path:
                field.is_mapped = True
                field.db_object = db_object
                field.db_path = db_path
                # Clean up session state
                keys_to_delete = [
                    f"mapping_{unique_key}",
                    f"{unique_key}_selected_object"
                ]
                for key in keys_to_delete:
                    if key in st.session_state:
                        del st.session_state[key]
                st.success(f"Mapped to {db_object}.{db_path}")
                st.rerun()
            else:
                st.error("Please select both object and field path")
    
    with col2:
        if st.button("❌ Cancel", key=f"{unique_key}_cancel"):
            keys_to_delete = [
                f"mapping_{unique_key}",
                f"{unique_key}_selected_object"
            ]
            for key in keys_to_delete:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
    
    with col3:
        if field.is_mapped and st.button("🗑️ Remove Mapping", key=f"{unique_key}_remove"):
            field.is_mapped = False
            field.db_object = ""
            field.db_path = ""
            keys_to_delete = [
                f"mapping_{unique_key}",
                f"{unique_key}_selected_object"
            ]
            for key in keys_to_delete:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Action buttons
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("✅ Apply Mapping", key=f"{unique_key}_apply", type="primary"):
            if db_object and db_path:
                field.is_mapped = True
                field.db_object = db_object
                field.db_path = db_path
                # Clean up session state
                if f"mapping_{unique_key}" in st.session_state:
                    del st.session_state[f"mapping_{unique_key}"]
                if f"{unique_key}_selected_object" in st.session_state:
                    del st.session_state[f"{unique_key}_selected_object"]
                st.success(f"Mapped to {db_object}.{db_path}")
                st.rerun()
            else:
                st.error("Please select both object and field")
    
    with col2:
        if st.button("❌ Cancel", key=f"{unique_key}_cancel"):
            if f"mapping_{unique_key}" in st.session_state:
                del st.session_state[f"mapping_{unique_key}"]
            if f"{unique_key}_selected_object" in st.session_state:
                del st.session_state[f"{unique_key}_selected_object"]
            st.rerun()
    
    with col3:
        if field.is_mapped and st.button("🗑️ Remove", key=f"{unique_key}_remove"):
            field.is_mapped = False
            field.db_object = ""
            field.db_path = ""
            if f"mapping_{unique_key}" in st.session_state:
                del st.session_state[f"mapping_{unique_key}"]
            if f"{unique_key}_selected_object" in st.session_state:
                del st.session_state[f"{unique_key}_selected_object"]
            st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

# ===== MAIN APPLICATION =====

def main():
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>📋 USCIS Form Reader</h1>
        <p>Complete Extraction with Subfield Support</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize session state
    if 'form_data' not in st.session_state:
        st.session_state.form_data = None
    if 'extractor' not in st.session_state:
        st.session_state.extractor = FormExtractor()
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 📊 Dashboard")
        
        if st.session_state.form_data and st.session_state.form_data.get("success"):
            data = st.session_state.form_data
            
            st.success(f"**Form:** {data['form_number']}")
            
            # Statistics
            stats = data["stats"]
            st.metric("Total Parts", stats.get("total_parts", 0))
            st.metric("Total Fields", stats.get("total_fields", 0))
            st.metric("Parent Fields", stats.get("parent_fields", 0))
            st.metric("Subfields", stats.get("subfields", 0))
            
            # Part breakdown
            st.markdown("### Parts Breakdown")
            for part in data["parts"]:
                part_stats = part.get_stats()
                with st.expander(f"Part {part.number}: {part.title[:20]}..."):
                    st.write(f"Total: {part_stats['total_fields']}")
                    st.write(f"Mapped: {part_stats['mapped_fields']}")
                    st.write(f"In Quest: {part_stats['questionnaire_fields']}")
            
            # Field order verification
            st.markdown("### Field Order Check")
            if st.checkbox("Show Field Order"):
                for part in data["parts"]:
                    st.write(f"**Part {part.number}:**")
                    for i, field in enumerate(part.fields[:15]):  # Show first 15
                        st.text(f"  {i+1}. Field {field.number}: {field.label[:30]}...")
        
        st.markdown("---")
        if st.button("🔄 Reset All", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    
    # Main tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📤 Upload & Extract",
        "🔗 Map Fields",
        "📝 Questionnaire",
        "💾 Export Data"
    ])
    
    with tab1:
        render_upload_tab()
    
    with tab2:
        render_mapping_tab()
    
    with tab3:
        render_questionnaire_tab()
    
    with tab4:
        render_export_tab()

def render_upload_tab():
    """Upload and extraction tab"""
    st.markdown("### Upload USCIS Form PDF")
    
    uploaded_file = st.file_uploader(
        "Choose a PDF file",
        type=['pdf'],
        help="Upload any USCIS form (I-129, I-140, I-485, etc.)"
    )
    
    if uploaded_file:
        st.info(f"📄 **File:** {uploaded_file.name} ({uploaded_file.size:,} bytes)")
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            extraction_mode = st.radio(
                "Extraction Mode",
                ["Quick (Pattern-based)", "Enhanced (AI-assisted)"],
                horizontal=True,
                help="AI mode requires API key but provides better subfield detection"
            )
        
        with col2:
            if st.button("🚀 Extract Form", type="primary", use_container_width=True):
                with st.spinner("Extracting form data..."):
                    # Extract PDF text
                    text, page_count = extract_pdf_text(uploaded_file)
                    
                    if text:
                        # Extract form data
                        form_data = st.session_state.extractor.extract_form(text)
                        
                        if form_data["success"]:
                            st.session_state.form_data = form_data
                            
                            # Success message
                            st.success(
                                f"✅ Successfully extracted:"
                                f"\n- {form_data['stats']['total_fields']} total fields"
                                f"\n- {form_data['stats']['parent_fields']} parent fields"
                                f"\n- {form_data['stats']['subfields']} subfields"
                                f"\n- {len(form_data['parts'])} parts"
                            )
                            
                            # Show extraction details
                            with st.expander("📊 Extraction Details"):
                                for part in form_data["parts"]:
                                    st.write(f"**Part {part.number}: {part.title}**")
                                    
                                    # Show hierarchy
                                    hierarchy = part.get_field_hierarchy()
                                    
                                    # Sort parent numbers properly
                                    sorted_parents = sorted(hierarchy.keys(), 
                                                          key=lambda x: int(x) if x.isdigit() else 999)
                                    
                                    for parent_num in sorted_parents:
                                        parent_data = hierarchy[parent_num]
                                        parent_field = parent_data['field']
                                        children = parent_data['children']
                                        
                                        st.write(f"  📁 {parent_field.number}. {parent_field.label}")
                                        
                                        for child in children:
                                            st.write(f"    └─ {child.number}. {child.label}")
                        else:
                            st.error("Extraction failed. Please try again.")
                    else:
                        st.error("Could not read PDF text. Please ensure the PDF is not scanned/image-based.")

def render_mapping_tab():
    """Field mapping tab"""
    if not st.session_state.form_data or not st.session_state.form_data.get("success"):
        st.info("👆 Please upload and extract a form first")
        return
    
    st.markdown("### Map Form Fields to Database")
    
    data = st.session_state.form_data
    
    # Part selector
    part_numbers = [p.number for p in data["parts"]]
    selected_part = st.selectbox(
        "Select Part to Map",
        part_numbers,
        format_func=lambda x: f"Part {x}: {next(p.title for p in data['parts'] if p.number == x)}",
        key="mapping_part_selector"
    )
    
    if selected_part:
        part = next(p for p in data["parts"] if p.number == selected_part)
        
        # Statistics
        stats = part.get_stats()
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Fields", stats["total_fields"])
        with col2:
            st.metric("Mapped", stats["mapped_fields"])
        with col3:
            st.metric("Parent Fields", stats["parent_fields"])
        with col4:
            st.metric("Subfields", stats["subfields"])
        
        # Quick actions
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🎯 Auto-Map Common Fields", use_container_width=True):
                auto_map_fields(part)
                st.rerun()
        
        with col2:
            show_mapped_only = st.checkbox("Show Mapped Only", value=False)
        
        with col3:
            show_unmapped_only = st.checkbox("Show Unmapped Only", value=False)
        
        st.markdown("---")
        
        # Display fields with hierarchy
        hierarchy = part.get_field_hierarchy()
        
        # Sort parent numbers properly for display
        sorted_parents = sorted(hierarchy.keys(), 
                              key=lambda x: int(x) if x.isdigit() else 999)
        
        # Display parent fields and their children
        for parent_num in sorted_parents:
            parent_data = hierarchy[parent_num]
            parent_field = parent_data['field']
            children = parent_data['children']
            
            # Filter logic
            if show_mapped_only and not parent_field.is_mapped and not any(c.is_mapped for c in children):
                continue
            if show_unmapped_only and (parent_field.is_mapped or all(c.is_mapped for c in children)):
                continue
            
            # Render parent field
            render_field(parent_field, f"map_p{part.number}")
            
            # Render children
            for child in children:
                if show_mapped_only and not child.is_mapped:
                    continue
                if show_unmapped_only and child.is_mapped:
                    continue
                
                render_field(child, f"map_p{part.number}")
        
        # Display orphan fields (fields without parents in hierarchy)
        orphan_fields = [f for f in part.fields if f.number not in hierarchy and not f.parent_number]
        
        if orphan_fields:
            st.markdown("#### Other Fields")
            for field in sorted(orphan_fields, key=lambda f: f.get_sort_key()):
                if show_mapped_only and not field.is_mapped:
                    continue
                if show_unmapped_only and field.is_mapped:
                    continue
                
                render_field(field, f"map_p{part.number}")

def render_questionnaire_tab():
    """Questionnaire tab"""
    if not st.session_state.form_data or not st.session_state.form_data.get("success"):
        st.info("👆 Please upload and extract a form first")
        return
    
    st.markdown("### Form Questionnaire")
    
    data = st.session_state.form_data
    
    # Collect all questionnaire fields
    quest_fields = []
    for part in data["parts"]:
        for field in part.fields:
            if field.in_questionnaire:
                quest_fields.append((part, field))
    
    if not quest_fields:
        st.info("No fields in questionnaire. Use the Map Fields tab to add fields to the questionnaire.")
        return
    
    # Sort questionnaire fields properly
    quest_fields.sort(key=lambda x: (x[0].number, x[1].get_sort_key()))
    
    # Group by part
    st.write(f"**Total Questions:** {len(quest_fields)}")
    st.markdown("---")
    
    current_part = None
    for part, field in quest_fields:
        if part.number != current_part:
            st.markdown(f"#### Part {part.number}: {part.title}")
            current_part = part.number
        
        with st.container():
            st.markdown(f"**{field.number}. {field.label}**")
            
            if field.is_subfield and field.subfield_letter:
                st.caption(f"Subfield {field.subfield_letter} of item {field.parent_number}")
            
            quest_key = f"quest_{field.get_unique_key()}"
            
            if field.choices:
                # Multiple choice question
                for choice in field.choices:
                    choice.selected = st.checkbox(
                        f"{choice.letter}. {choice.text}",
                        value=choice.selected,
                        key=f"{quest_key}_choice_{choice.letter}"
                    )
            elif field.field_type == "date":
                field.value = st.date_input(
                    "Answer",
                    key=quest_key
                )
            elif field.field_type == "checkbox":
                field.value = st.checkbox(
                    "Yes",
                    key=quest_key
                )
            else:
                field.value = st.text_area(
                    "Answer",
                    value=field.value or "",
                    key=quest_key,
                    height=70,
                    placeholder=f"Enter {field.field_type}"
                )
            
            st.markdown("---")

def render_export_tab():
    """Export tab"""
    if not st.session_state.form_data or not st.session_state.form_data.get("success"):
        st.info("👆 Please upload and extract a form first")
        return
    
    st.markdown("### Export Form Data")
    
    data = st.session_state.form_data
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📁 Export by Part")
        
        for i, part in enumerate(data["parts"]):
            export_key = f"export_part_{i}_{uuid.uuid4().hex[:8]}"
            if st.button(
                f"📥 Part {part.number}: {part.title[:30]}...",
                key=export_key,
                use_container_width=True
            ):
                export_part_data(part, export_key)
    
    with col2:
        st.markdown("#### 📊 Export Categories")
        
        # Mapped fields export
        mapped_key = f"export_mapped_{uuid.uuid4().hex[:8]}"
        if st.button("📥 Export Mapped Fields", key=mapped_key, use_container_width=True):
            export_mapped_fields(data)
        
        # Questionnaire export
        quest_key = f"export_quest_{uuid.uuid4().hex[:8]}"
        if st.button("📥 Export Questionnaire", key=quest_key, use_container_width=True):
            export_questionnaire(data)
        
        # Complete export
        all_key = f"export_all_{uuid.uuid4().hex[:8]}"
        if st.button("📥 Export Complete Form", key=all_key, use_container_width=True):
            export_all_data(data)

# ===== EXPORT FUNCTIONS =====

def auto_map_fields(part: FormPart):
    """Auto-map common fields to database"""
    
    mapping_rules = {
        # Name fields
        "family name": ("beneficiary", "lastName"),
        "last name": ("beneficiary", "lastName"),
        "given name": ("beneficiary", "firstName"),
        "first name": ("beneficiary", "firstName"),
        "middle name": ("beneficiary", "middleName"),
        
        # Identification
        "alien number": ("beneficiary", "alienNumber"),
        "a-number": ("beneficiary", "alienNumber"),
        "uscis number": ("beneficiary", "uscisNumber"),
        "social security": ("beneficiary", "ssn"),
        
        # Birth information
        "date of birth": ("beneficiary", "dateOfBirth"),
        "country of birth": ("beneficiary", "countryOfBirth"),
        "city of birth": ("beneficiary", "cityOfBirth"),
        
        # Address fields
        "street number and name": ("beneficiary", "address.street"),
        "apt": ("beneficiary", "address.apt"),
        "city or town": ("beneficiary", "address.city"),
        "state": ("beneficiary", "address.state"),
        "zip code": ("beneficiary", "address.zip"),
        "postal code": ("beneficiary", "address.zip"),
        "country": ("beneficiary", "address.country"),
        
        # Contact
        "daytime phone": ("beneficiary", "phone.daytime"),
        "mobile phone": ("beneficiary", "phone.mobile"),
        "email address": ("beneficiary", "email"),
        
        # Employment
        "job title": ("employment", "jobTitle"),
        "soc code": ("employment", "socCode"),
        "naics code": ("employment", "naicsCode"),
        "wages": ("employment", "wages.amount"),
        "start date": ("employment", "startDate"),
        "end date": ("employment", "endDate"),
    }
    
    for field in part.fields:
        if not field.is_mapped:
            field_label_lower = field.label.lower()
            
            for pattern, (obj, path) in mapping_rules.items():
                if pattern in field_label_lower:
                    field.is_mapped = True
                    field.db_object = obj
                    field.db_path = path
                    break

def export_part_data(part: FormPart, key: str):
    """Export single part data"""
    data = {
        "part": part.number,
        "title": part.title,
        "stats": part.get_stats(),
        "fields": []
    }
    
    # Organize fields by hierarchy
    hierarchy = part.get_field_hierarchy()
    
    # Sort parent numbers properly
    sorted_parents = sorted(hierarchy.keys(), 
                          key=lambda x: int(x) if x.isdigit() else 999)
    
    for parent_num in sorted_parents:
        parent_data = hierarchy[parent_num]
        parent_field = parent_data['field']
        children = parent_data['children']
        
        # Add parent field
        data["fields"].append(parent_field.to_dict())
        
        # Add children
        for child in children:
            data["fields"].append(child.to_dict())
    
    # Add orphan fields
    orphan_fields = [f for f in part.fields if f.number not in hierarchy and not f.parent_number]
    for field in sorted(orphan_fields, key=lambda f: f.get_sort_key()):
        data["fields"].append(field.to_dict())
    
    json_str = json.dumps(data, indent=2, default=str)
    
    st.download_button(
        "💾 Download Part Data",
        json_str,
        f"part_{part.number}_data.json",
        "application/json",
        key=f"download_{key}"
    )

def export_mapped_fields(data: Dict):
    """Export all mapped fields organized by database object"""
    mapped = {}
    
    for part in data["parts"]:
        for field in part.fields:
            if field.is_mapped:
                if field.db_object not in mapped:
                    mapped[field.db_object] = {}
                
                # Create nested structure for paths with dots
                path_parts = field.db_path.split('.')
                current = mapped[field.db_object]
                
                for i, part_name in enumerate(path_parts[:-1]):
                    if part_name not in current:
                        current[part_name] = {}
                    current = current[part_name]
                
                # Set the value at the final path
                current[path_parts[-1]] = {
                    "field_number": field.number,
                    "label": field.label,
                    "value": str(field.value) if field.value else "",
                    "part": field.part_number,
                    "type": field.field_type
                }
    
    json_str = json.dumps(mapped, indent=2, default=str)
    
    st.download_button(
        "💾 Download Mapped Fields",
        json_str,
        "mapped_fields.json",
        "application/json",
        key=f"download_mapped_{uuid.uuid4().hex[:8]}"
    )

def export_questionnaire(data: Dict):
    """Export questionnaire responses"""
    quest_data = {
        "form": data["form_number"],
        "responses": {}
    }
    
    for part in data["parts"]:
        quest_fields = [f for f in part.fields if f.in_questionnaire]
        
        if quest_fields:
            part_key = f"Part_{part.number}"
            quest_data["responses"][part_key] = {
                "title": part.title,
                "questions": []
            }
            
            # Sort fields properly before export
            quest_fields.sort(key=lambda f: f.get_sort_key())
            
            for field in quest_fields:
                question_data = field.to_dict()
                
                # Add parent info if subfield
                if field.parent_number:
                    question_data["parent_field"] = field.parent_number
                
                quest_data["responses"][part_key]["questions"].append(question_data)
    
    json_str = json.dumps(quest_data, indent=2, default=str)
    
    st.download_button(
        "💾 Download Questionnaire",
        json_str,
        "questionnaire.json",
        "application/json",
        key=f"download_quest_{uuid.uuid4().hex[:8]}"
    )

def export_all_data(data: Dict):
    """Export complete form data"""
    export = {
        "form": {
            "number": data["form_number"],
            "title": data["form_title"]
        },
        "statistics": data["stats"],
        "parts": []
    }
    
    for part in data["parts"]:
        part_data = {
            "number": part.number,
            "title": part.title,
            "stats": part.get_stats(),
            "fields": []
        }
        
        # Export with hierarchy
        hierarchy = part.get_field_hierarchy()
        
        # Sort parent numbers properly
        sorted_parents = sorted(hierarchy.keys(), 
                              key=lambda x: int(x) if x.isdigit() else 999)
        
        for parent_num in sorted_parents:
            parent_data = hierarchy[parent_num]
            parent_field = parent_data['field']
            children = parent_data['children']
            
            # Add parent with children
            parent_export = parent_field.to_dict()
            parent_export["children"] = [child.to_dict() for child in children]
            part_data["fields"].append(parent_export)
        
        # Add orphan fields
        orphan_fields = [f for f in part.fields if f.number not in hierarchy and not f.parent_number]
        for field in sorted(orphan_fields, key=lambda f: f.get_sort_key()):
            part_data["fields"].append(field.to_dict())
        
        export["parts"].append(part_data)
    
    json_str = json.dumps(export, indent=2, default=str)
    
    st.download_button(
        "💾 Download Complete Form",
        json_str,
        f"{data['form_number']}_complete.json",
        "application/json",
        key=f"download_all_{uuid.uuid4().hex[:8]}"
    )

if __name__ == "__main__":
    main(), '', label)
                    
                    # Limit length but preserve content
                    if len(label) > 150:
                        label = label[:147] + "..."
                    
                    # Detect field type from label
                    field_type = self._detect_field_type(label)
                    
                    # Get context
                    ctx_start = max(0, match.start() - 100)
                    ctx_end = min(len(text_chunks), match.end() + 500)
                    context = text_chunks[ctx_start:ctx_end]
                    
                    # Check for choices
                    choices = self._extract_choices(context)
                    
                    # Check if this is a parent field
                    is_parent = self._check_if_parent_simple(number, text_chunks)
                    
                    field = FormField(
                        number=number,
                        label=label,
                        field_type=field_type if not is_parent else "parent",
                        part_number=part_num,
                        parent_number=parent,
                        is_parent=is_parent,
                        is_subfield=is_sub,
                        subfield_letter=letter if is_sub else None,
                        choices=choices,
                        position=pos,
                        context=context[:200],
                        extraction_method="pattern"
                    )
                    
                    fields.append(field)
                    pos += 1
                    
                except Exception as e:
                    # Log but continue
                    continue
        
        # Create missing parent fields only if they don't exist
        self._create_missing_parents_only(fields, part_num)
        
        return fields
    
    def _check_if_parent_simple(self, number: str, text: str) -> bool:
        """Simple check if field has subfields - no assumptions"""
        # Only mark as parent if we actually find subfields in the text
        subfield_pattern = f"{re.escape(number)}\\.[a-z]"
        return bool(re.search(subfield_pattern, text, re.IGNORECASE))
    
    def _create_missing_parents_only(self, fields: List[FormField], part_num: int):
        """Create parent fields ONLY for actual orphan subfields"""
        parent_nums = {f.parent_number for f in fields if f.parent_number}
        existing = {f.number for f in fields}
        
        for pnum in parent_nums:
            if pnum and pnum not in existing:
                # Only create if we have actual subfields referencing this parent
                children = [f for f in fields if f.parent_number == pnum]
                if children:
                    # Use first child's label to infer parent type, but keep it generic
                    fields.append(FormField(
                        number=pnum,
                        label=f"Item {pnum}",  # Generic label
                        field_type="parent",
                        part_number=part_num,
                        is_parent=True,
                        extraction_method="inferred_parent"
                    ))
    
    def _extract_fields_ai(self, text: str, part_num: int) -> List[FormField]:
        """AI-based extraction"""
        if not self.client:
            return []
        
        try:
            prompt = f"""Extract ALL fields from Part {part_num} of this USCIS form.

CRITICAL: Include EVERY field and subfield with exact numbering.

For fields with subparts (like names with a, b, c), mark the parent as type "parent" and include all subfields.

Return JSON array:
[
  {{"number": "1", "label": "Full Legal Name", "type": "parent", "is_parent": true}},
  {{"number": "1.a", "label": "Family Name (Last Name)", "type": "text", "parent": "1", "letter": "a"}},
  {{"number": "1.b", "label": "Given Name (First Name)", "type": "text", "parent": "1", "letter": "b"}},
  {{"number": "1.c", "label": "Middle Name", "type": "text", "parent": "1", "letter": "c"}}
]

Text:
{text[:7000]}"""
            
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=3000,
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = response.content[0].text
            
            # Extract JSON
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                
                fields = []
                pos = 0
                
                for item in data:
                    if item.get("number"):
                        field = FormField(
                            number=item["number"],
                            label=item.get("label", ""),
                            field_type=item.get("type", "text"),
                            part_number=part_num,
                            parent_number=item.get("parent"),
                            is_parent=item.get("is_parent", False),
                            is_subfield=bool(item.get("parent")),
                            subfield_letter=item.get("letter"),
                            position=pos,
                            extraction_method="AI"
                        )
                        fields.append(field)
                        pos += 1
                
                return fields
                
        except Exception as e:
            st.warning(f"AI extraction issue: {str(e)[:50]}")
        
        return []
    
    def _enhance_fields(self, fields: List[FormField], text: str) -> List[FormField]:
        """Enhance fields with better subfield detection"""
        enhanced = []
        
        for field in fields:
            # Check if this field should have standard subfields
            if field.is_parent or self._should_have_subfields(field.label):
                # Check for name fields
                if any(word in field.label.lower() for word in ['name', 'nombre']):
                    if not any(f.parent_number == field.number for f in fields):
                        # Create standard name subfields
                        enhanced.append(field)
                        for letter, label in self.name_subfields.items():
                            subfield = FormField(
                                number=f"{field.number}.{letter}",
                                label=label,
                                field_type="text",
                                part_number=field.part_number,
                                parent_number=field.number,
                                is_subfield=True,
                                subfield_letter=letter,
                                extraction_method="inferred"
                            )
                            enhanced.append(subfield)
                    else:
                        enhanced.append(field)
                
                # Check for address fields
                elif any(word in field.label.lower() for word in ['address', 'mailing', 'residence']):
                    if not any(f.parent_number == field.number for f in fields):
                        # Create standard address subfields
                        enhanced.append(field)
                        for letter, label in list(self.address_subfields.items())[:5]:  # Common address fields
                            subfield = FormField(
                                number=f"{field.number}.{letter}",
                                label=label,
                                field_type="text",
                                part_number=field.part_number,
                                parent_number=field.number,
                                is_subfield=True,
                                subfield_letter=letter,
                                extraction_method="inferred"
                            )
                            enhanced.append(subfield)
                    else:
                        enhanced.append(field)
                else:
                    enhanced.append(field)
            else:
                enhanced.append(field)
        
        return enhanced
    
    def _should_have_subfields(self, label: str) -> bool:
        """Check if a field typically has subfields"""
        keywords = ['name', 'address', 'mailing', 'residence', 'location', 'contact']
        return any(keyword in label.lower() for keyword in keywords)
    
    def _is_parent_field(self, label: str, context: str, number: str, full_text: str) -> bool:
        """Determine if this is a parent field"""
        # Check if there are subfields in the text
        subfield_pattern = f"{number}\\.[a-z]"
        if re.search(subfield_pattern, full_text[:20000], re.IGNORECASE):
            return True
        
        # Check for typical parent field indicators
        if any(word in label.lower() for word in ['name', 'address', 'information about']):
            return True
        
        # Check context for subfield indicators
        if re.search(r'\n\s*[a-z]\.\s+', context):
            return True
        
        return False
    
    def _extract_choices(self, text: str) -> List[FieldChoice]:
        """Extract checkbox/radio options"""
        choices = []
        
        patterns = [
            r'[□☐]\s*([^\n□☐]{2,80})',
            r'\[\s*\]\s*([^\n\[\]]{2,80})',
            r'○\s*([^\n○]{2,80})'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text[:500])
            if matches and len(matches) >= 2:
                for i, txt in enumerate(matches[:6]):
                    choices.append(FieldChoice(
                        letter=chr(ord('a') + i),
                        text=txt.strip(),
                        selected=False
                    ))
                break
        
        return choices
    
    def _create_parent_fields(self, fields: List[FormField], part_num: int):
        """Create parent fields for orphan subfields"""
        parent_nums = {f.parent_number for f in fields if f.parent_number}
        existing = {f.number for f in fields}
        
        for pnum in parent_nums:
            if pnum and pnum not in existing:
                # Determine label based on children
                child_labels = [f.label for f in fields if f.parent_number == pnum]
                
                if any('name' in label.lower() for label in child_labels):
                    parent_label = "Full Legal Name"
                elif any('address' in label.lower() or 'street' in label.lower() for label in child_labels):
                    parent_label = "Mailing Address"
                else:
                    parent_label = f"Information for Item {pnum}"
                
                fields.append(FormField(
                    number=pnum,
                    label=parent_label,
                    field_type="parent",
                    part_number=part_num,
                    is_parent=True,
                    extraction_method="inferred"
                ))
    
    def _detect_field_type(self, label: str) -> str:
        """Detect field type from label"""
        lower = label.lower()
        
        if any(w in lower for w in ["date", "birth", "expire", "issued"]):
            return "date"
        elif "email" in lower or "e-mail" in lower:
            return "email"
        elif any(w in lower for w in ["phone", "telephone", "mobile", "cell"]):
            return "phone"
        elif "ssn" in lower or "social security" in lower:
            return "ssn"
        elif "ein" in lower or "employer identification" in lower:
            return "ein"
        elif "alien number" in lower or "a-number" in lower or "uscis number" in lower:
            return "alien_number"
        elif any(w in lower for w in ["check", "select", "mark all"]):
            return "checkbox"
        elif any(w in lower for w in ["street", "apt", "suite"]):
            return "address"
        elif any(w in lower for w in ["city", "town"]):
            return "city"
        elif "state" in lower and "united states" not in lower:
            return "state"
        elif "zip" in lower or "postal code" in lower:
            return "zip"
        
        return "text"

# ===== PDF EXTRACTION =====

def extract_pdf_text(pdf_file) -> Tuple[str, int]:
    """Extract text from PDF"""
    try:
        # Try PyMuPDF first (better extraction)
        try:
            import fitz
            pdf_file.seek(0)
            doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
            
            text = ""
            for i in range(len(doc)):
                page = doc[i]
                text += f"\n\n=== PAGE {i+1} ===\n{page.get_text()}"
            
            pages = len(doc)
            doc.close()
            return text, pages
            
        except ImportError:
            # Fallback to PyPDF2
            import PyPDF2
            pdf_file.seek(0)
            reader = PyPDF2.PdfReader(pdf_file)
            
            text = ""
            for i, page in enumerate(reader.pages):
                text += f"\n\n=== PAGE {i+1} ===\n{page.extract_text()}"
            
            return text, len(reader.pages)
            
    except Exception as e:
        st.error(f"PDF reading error: {str(e)}")
        return "", 0

# ===== UI COMPONENTS =====

def render_field(field: FormField, key_prefix: str):
    """Render a single field with all controls"""
    unique_key = f"{key_prefix}_{field.get_unique_key()}"
    
    # Determine CSS class
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
            # Field number and label
            subfield_indicator = ""
            if field.is_subfield and field.subfield_letter:
                subfield_indicator = f'<span class="subfield-indicator">(subfield {field.subfield_letter})</span>'
            
            st.markdown(
                f'<span class="field-number-badge">{field.number}</span>'
                f'<strong>{field.label}</strong>{subfield_indicator}',
                unsafe_allow_html=True
            )
            
            # Show choices for multiple choice fields
            if field.choices:
                for choice in field.choices:
                    choice.selected = st.checkbox(
                        f"{choice.letter}. {choice.text}",
                        value=choice.selected,
                        key=f"{unique_key}_choice_{choice.letter}"
                    )
        
        with col2:
            # Value input (not for parent fields)
            if not field.is_parent and not field.choices:
                if field.field_type == "date":
                    val = st.date_input(
                        "Value",
                        key=f"{unique_key}_value",
                        label_visibility="collapsed"
                    )
                    field.value = str(val) if val else ""
                elif field.field_type == "checkbox":
                    field.value = st.checkbox(
                        "Selected",
                        key=f"{unique_key}_value"
                    )
                elif field.field_type in ["state"]:
                    # State dropdown
                    states = ["", "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", 
                             "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", 
                             "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", 
                             "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", 
                             "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"]
                    field.value = st.selectbox(
                        "State",
                        states,
                        key=f"{unique_key}_value",
                        label_visibility="collapsed"
                    )
                else:
                    field.value = st.text_input(
                        "Value",
                        value=field.value or "",
                        key=f"{unique_key}_value",
                        label_visibility="collapsed",
                        placeholder=f"Enter {field.field_type}"
                    )
        
        with col3:
            # Action buttons
            c1, c2 = st.columns(2)
            
            with c1:
                if field.is_mapped:
                    st.success(f"✓ {field.db_object}")
                else:
                    if st.button("📎 Map", key=f"{unique_key}_map_btn"):
                        st.session_state[f"mapping_{unique_key}"] = True
            
            with c2:
                quest_label = "📝 Q✓" if field.in_questionnaire else "📝 Q+"
                if st.button(quest_label, key=f"{unique_key}_quest_btn"):
                    field.in_questionnaire = not field.in_questionnaire
                    st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Mapping dialog
        if st.session_state.get(f"mapping_{unique_key}"):
            render_mapping_dialog(field, unique_key)

def render_mapping_dialog(field: FormField, unique_key: str):
    """Render mapping configuration dialog with improved DB object display"""
    st.markdown('<div class="mapping-dialog">', unsafe_allow_html=True)
    st.markdown("**🔗 Map Field to Database**")
    
    # Show available database objects clearly
    st.markdown("##### Select Database Object:")
    
    # Display DB objects as cards
    selected_object = st.session_state.get(f"{unique_key}_selected_object", "")
    
    # Create columns for DB objects
    cols = st.columns(3)
    
    for idx, (key, schema) in enumerate(DB_SCHEMA.items()):
        col_idx = idx % 3
        with cols[col_idx]:
            # Create clickable card for each DB object
            if st.button(
                f"{schema['icon']} {schema['label']}",
                key=f"{unique_key}_obj_{key}",
                use_container_width=True,
                type="primary" if selected_object == key else "secondary"
            ):
                st.session_state[f"{unique_key}_selected_object"] = key
                st.rerun()
    
    # Field path selection
    if st.session_state.get(f"{unique_key}_selected_object"):
        db_object = st.session_state[f"{unique_key}_selected_object"]
        
        st.markdown(f"##### Select or Enter Field Path in {DB_SCHEMA[db_object]['label']}:")
        
        if db_object == "custom":
            db_path = st.text_input(
                "Custom Field Path",
                key=f"{unique_key}_map_custom",
                placeholder="e.g., customField.subField"
            )
        else:
            available_fields = DB_SCHEMA[db_object]["fields"]
            
            # Option to select from dropdown OR enter manually
            col1, col2 = st.columns([1, 1])
            
            with col1:
                # Smart suggestions based on field label
                suggested = None
                field_label_lower = field.label.lower()
                
                for db_field in available_fields:
                    if any(word in db_field.lower() for word in field_label_lower.split()):
                        suggested = db_field
                        break
                
                selected_path = st.selectbox(
                    "Select from existing fields",
                    [""] + available_fields,
                    index=available_fields.index(suggested) + 1 if suggested and suggested in available_fields else 0,
                    key=f"{unique_key}_map_path",
                    help="Choose from predefined fields"
                )
            
            with col2:
                manual_path = st.text_input(
                    "OR enter custom path",
                    key=f"{unique_key}_manual_path",
                    placeholder="e.g., address.apartmentNumber",
                    help="Enter a custom field path if not in the list"
                )
            
            # Use manual path if provided, otherwise use selected
            db_path = manual_path if manual_path else selected_path
    else:
        db_path = ""
        db_object = ""
    
    # Action buttons
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("✅ Apply Mapping", key=f"{unique_key}_apply", type="primary"):
            if db_object and db_path:
                field.is_mapped = True
                field.db_object = db_object
                field.db_path = db_path
                # Clean up session state
                if f"mapping_{unique_key}" in st.session_state:
                    del st.session_state[f"mapping_{unique_key}"]
                if f"{unique_key}_selected_object" in st.session_state:
                    del st.session_state[f"{unique_key}_selected_object"]
                st.success(f"Mapped to {db_object}.{db_path}")
                st.rerun()
            else:
                st.error("Please select both object and field")
    
    with col2:
        if st.button("❌ Cancel", key=f"{unique_key}_cancel"):
            if f"mapping_{unique_key}" in st.session_state:
                del st.session_state[f"mapping_{unique_key}"]
            if f"{unique_key}_selected_object" in st.session_state:
                del st.session_state[f"{unique_key}_selected_object"]
            st.rerun()
    
    with col3:
        if field.is_mapped and st.button("🗑️ Remove", key=f"{unique_key}_remove"):
            field.is_mapped = False
            field.db_object = ""
            field.db_path = ""
            if f"mapping_{unique_key}" in st.session_state:
                del st.session_state[f"mapping_{unique_key}"]
            if f"{unique_key}_selected_object" in st.session_state:
                del st.session_state[f"{unique_key}_selected_object"]
            st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

# ===== MAIN APPLICATION =====

def main():
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>📋 USCIS Form Reader</h1>
        <p>Complete Extraction with Subfield Support</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize session state
    if 'form_data' not in st.session_state:
        st.session_state.form_data = None
    if 'extractor' not in st.session_state:
        st.session_state.extractor = FormExtractor()
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 📊 Dashboard")
        
        if st.session_state.form_data and st.session_state.form_data.get("success"):
            data = st.session_state.form_data
            
            st.success(f"**Form:** {data['form_number']}")
            
            # Statistics
            stats = data["stats"]
            st.metric("Total Parts", stats.get("total_parts", 0))
            st.metric("Total Fields", stats.get("total_fields", 0))
            st.metric("Parent Fields", stats.get("parent_fields", 0))
            st.metric("Subfields", stats.get("subfields", 0))
            
            # Part breakdown
            st.markdown("### Parts Breakdown")
            for part in data["parts"]:
                part_stats = part.get_stats()
                with st.expander(f"Part {part.number}: {part.title[:20]}..."):
                    st.write(f"Total: {part_stats['total_fields']}")
                    st.write(f"Mapped: {part_stats['mapped_fields']}")
                    st.write(f"In Quest: {part_stats['questionnaire_fields']}")
            
            # Field order verification
            st.markdown("### Field Order Check")
            if st.checkbox("Show Field Order"):
                for part in data["parts"]:
                    st.write(f"**Part {part.number}:**")
                    for i, field in enumerate(part.fields[:15]):  # Show first 15
                        st.text(f"  {i+1}. Field {field.number}: {field.label[:30]}...")
        
        st.markdown("---")
        if st.button("🔄 Reset All", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    
    # Main tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📤 Upload & Extract",
        "🔗 Map Fields",
        "📝 Questionnaire",
        "💾 Export Data"
    ])
    
    with tab1:
        render_upload_tab()
    
    with tab2:
        render_mapping_tab()
    
    with tab3:
        render_questionnaire_tab()
    
    with tab4:
        render_export_tab()

def render_upload_tab():
    """Upload and extraction tab"""
    st.markdown("### Upload USCIS Form PDF")
    
    uploaded_file = st.file_uploader(
        "Choose a PDF file",
        type=['pdf'],
        help="Upload any USCIS form (I-129, I-140, I-485, etc.)"
    )
    
    if uploaded_file:
        st.info(f"📄 **File:** {uploaded_file.name} ({uploaded_file.size:,} bytes)")
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            extraction_mode = st.radio(
                "Extraction Mode",
                ["Quick (Pattern-based)", "Enhanced (AI-assisted)"],
                horizontal=True,
                help="AI mode requires API key but provides better subfield detection"
            )
        
        with col2:
            if st.button("🚀 Extract Form", type="primary", use_container_width=True):
                with st.spinner("Extracting form data..."):
                    # Extract PDF text
                    text, page_count = extract_pdf_text(uploaded_file)
                    
                    if text:
                        # Extract form data
                        form_data = st.session_state.extractor.extract_form(text)
                        
                        if form_data["success"]:
                            st.session_state.form_data = form_data
                            
                            # Success message
                            st.success(
                                f"✅ Successfully extracted:"
                                f"\n- {form_data['stats']['total_fields']} total fields"
                                f"\n- {form_data['stats']['parent_fields']} parent fields"
                                f"\n- {form_data['stats']['subfields']} subfields"
                                f"\n- {len(form_data['parts'])} parts"
                            )
                            
                            # Show extraction details
                            with st.expander("📊 Extraction Details"):
                                for part in form_data["parts"]:
                                    st.write(f"**Part {part.number}: {part.title}**")
                                    
                                    # Show hierarchy
                                    hierarchy = part.get_field_hierarchy()
                                    
                                    # Sort parent numbers properly
                                    sorted_parents = sorted(hierarchy.keys(), 
                                                          key=lambda x: int(x) if x.isdigit() else 999)
                                    
                                    for parent_num in sorted_parents:
                                        parent_data = hierarchy[parent_num]
                                        parent_field = parent_data['field']
                                        children = parent_data['children']
                                        
                                        st.write(f"  📁 {parent_field.number}. {parent_field.label}")
                                        
                                        for child in children:
                                            st.write(f"    └─ {child.number}. {child.label}")
                        else:
                            st.error("Extraction failed. Please try again.")
                    else:
                        st.error("Could not read PDF text. Please ensure the PDF is not scanned/image-based.")

def render_mapping_tab():
    """Field mapping tab"""
    if not st.session_state.form_data or not st.session_state.form_data.get("success"):
        st.info("👆 Please upload and extract a form first")
        return
    
    st.markdown("### Map Form Fields to Database")
    
    data = st.session_state.form_data
    
    # Part selector
    part_numbers = [p.number for p in data["parts"]]
    selected_part = st.selectbox(
        "Select Part to Map",
        part_numbers,
        format_func=lambda x: f"Part {x}: {next(p.title for p in data['parts'] if p.number == x)}",
        key="mapping_part_selector"
    )
    
    if selected_part:
        part = next(p for p in data["parts"] if p.number == selected_part)
        
        # Statistics
        stats = part.get_stats()
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Fields", stats["total_fields"])
        with col2:
            st.metric("Mapped", stats["mapped_fields"])
        with col3:
            st.metric("Parent Fields", stats["parent_fields"])
        with col4:
            st.metric("Subfields", stats["subfields"])
        
        # Quick actions
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🎯 Auto-Map Common Fields", use_container_width=True):
                auto_map_fields(part)
                st.rerun()
        
        with col2:
            show_mapped_only = st.checkbox("Show Mapped Only", value=False)
        
        with col3:
            show_unmapped_only = st.checkbox("Show Unmapped Only", value=False)
        
        st.markdown("---")
        
        # Display fields with hierarchy
        hierarchy = part.get_field_hierarchy()
        
        # Sort parent numbers properly for display
        sorted_parents = sorted(hierarchy.keys(), 
                              key=lambda x: int(x) if x.isdigit() else 999)
        
        # Display parent fields and their children
        for parent_num in sorted_parents:
            parent_data = hierarchy[parent_num]
            parent_field = parent_data['field']
            children = parent_data['children']
            
            # Filter logic
            if show_mapped_only and not parent_field.is_mapped and not any(c.is_mapped for c in children):
                continue
            if show_unmapped_only and (parent_field.is_mapped or all(c.is_mapped for c in children)):
                continue
            
            # Render parent field
            render_field(parent_field, f"map_p{part.number}")
            
            # Render children
            for child in children:
                if show_mapped_only and not child.is_mapped:
                    continue
                if show_unmapped_only and child.is_mapped:
                    continue
                
                render_field(child, f"map_p{part.number}")
        
        # Display orphan fields (fields without parents in hierarchy)
        orphan_fields = [f for f in part.fields if f.number not in hierarchy and not f.parent_number]
        
        if orphan_fields:
            st.markdown("#### Other Fields")
            for field in sorted(orphan_fields, key=lambda f: f.get_sort_key()):
                if show_mapped_only and not field.is_mapped:
                    continue
                if show_unmapped_only and field.is_mapped:
                    continue
                
                render_field(field, f"map_p{part.number}")

def render_questionnaire_tab():
    """Questionnaire tab"""
    if not st.session_state.form_data or not st.session_state.form_data.get("success"):
        st.info("👆 Please upload and extract a form first")
        return
    
    st.markdown("### Form Questionnaire")
    
    data = st.session_state.form_data
    
    # Collect all questionnaire fields
    quest_fields = []
    for part in data["parts"]:
        for field in part.fields:
            if field.in_questionnaire:
                quest_fields.append((part, field))
    
    if not quest_fields:
        st.info("No fields in questionnaire. Use the Map Fields tab to add fields to the questionnaire.")
        return
    
    # Sort questionnaire fields properly
    quest_fields.sort(key=lambda x: (x[0].number, x[1].get_sort_key()))
    
    # Group by part
    st.write(f"**Total Questions:** {len(quest_fields)}")
    st.markdown("---")
    
    current_part = None
    for part, field in quest_fields:
        if part.number != current_part:
            st.markdown(f"#### Part {part.number}: {part.title}")
            current_part = part.number
        
        with st.container():
            st.markdown(f"**{field.number}. {field.label}**")
            
            if field.is_subfield and field.subfield_letter:
                st.caption(f"Subfield {field.subfield_letter} of item {field.parent_number}")
            
            quest_key = f"quest_{field.get_unique_key()}"
            
            if field.choices:
                # Multiple choice question
                for choice in field.choices:
                    choice.selected = st.checkbox(
                        f"{choice.letter}. {choice.text}",
                        value=choice.selected,
                        key=f"{quest_key}_choice_{choice.letter}"
                    )
            elif field.field_type == "date":
                field.value = st.date_input(
                    "Answer",
                    key=quest_key
                )
            elif field.field_type == "checkbox":
                field.value = st.checkbox(
                    "Yes",
                    key=quest_key
                )
            else:
                field.value = st.text_area(
                    "Answer",
                    value=field.value or "",
                    key=quest_key,
                    height=70,
                    placeholder=f"Enter {field.field_type}"
                )
            
            st.markdown("---")

def render_export_tab():
    """Export tab"""
    if not st.session_state.form_data or not st.session_state.form_data.get("success"):
        st.info("👆 Please upload and extract a form first")
        return
    
    st.markdown("### Export Form Data")
    
    data = st.session_state.form_data
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📁 Export by Part")
        
        for i, part in enumerate(data["parts"]):
            export_key = f"export_part_{i}_{uuid.uuid4().hex[:8]}"
            if st.button(
                f"📥 Part {part.number}: {part.title[:30]}...",
                key=export_key,
                use_container_width=True
            ):
                export_part_data(part, export_key)
    
    with col2:
        st.markdown("#### 📊 Export Categories")
        
        # Mapped fields export
        mapped_key = f"export_mapped_{uuid.uuid4().hex[:8]}"
        if st.button("📥 Export Mapped Fields", key=mapped_key, use_container_width=True):
            export_mapped_fields(data)
        
        # Questionnaire export
        quest_key = f"export_quest_{uuid.uuid4().hex[:8]}"
        if st.button("📥 Export Questionnaire", key=quest_key, use_container_width=True):
            export_questionnaire(data)
        
        # Complete export
        all_key = f"export_all_{uuid.uuid4().hex[:8]}"
        if st.button("📥 Export Complete Form", key=all_key, use_container_width=True):
            export_all_data(data)

# ===== EXPORT FUNCTIONS =====

def auto_map_fields(part: FormPart):
    """Auto-map common fields to database"""
    
    mapping_rules = {
        # Name fields
        "family name": ("beneficiary", "lastName"),
        "last name": ("beneficiary", "lastName"),
        "given name": ("beneficiary", "firstName"),
        "first name": ("beneficiary", "firstName"),
        "middle name": ("beneficiary", "middleName"),
        
        # Identification
        "alien number": ("beneficiary", "alienNumber"),
        "a-number": ("beneficiary", "alienNumber"),
        "uscis number": ("beneficiary", "uscisNumber"),
        "social security": ("beneficiary", "ssn"),
        
        # Birth information
        "date of birth": ("beneficiary", "dateOfBirth"),
        "country of birth": ("beneficiary", "countryOfBirth"),
        "city of birth": ("beneficiary", "cityOfBirth"),
        
        # Address fields
        "street number and name": ("beneficiary", "address.street"),
        "apt": ("beneficiary", "address.apt"),
        "city or town": ("beneficiary", "address.city"),
        "state": ("beneficiary", "address.state"),
        "zip code": ("beneficiary", "address.zip"),
        "postal code": ("beneficiary", "address.zip"),
        "country": ("beneficiary", "address.country"),
        
        # Contact
        "daytime phone": ("beneficiary", "phone.daytime"),
        "mobile phone": ("beneficiary", "phone.mobile"),
        "email address": ("beneficiary", "email"),
        
        # Employment
        "job title": ("employment", "jobTitle"),
        "soc code": ("employment", "socCode"),
        "naics code": ("employment", "naicsCode"),
        "wages": ("employment", "wages.amount"),
        "start date": ("employment", "startDate"),
        "end date": ("employment", "endDate"),
    }
    
    for field in part.fields:
        if not field.is_mapped:
            field_label_lower = field.label.lower()
            
            for pattern, (obj, path) in mapping_rules.items():
                if pattern in field_label_lower:
                    field.is_mapped = True
                    field.db_object = obj
                    field.db_path = path
                    break

def export_part_data(part: FormPart, key: str):
    """Export single part data"""
    data = {
        "part": part.number,
        "title": part.title,
        "stats": part.get_stats(),
        "fields": []
    }
    
    # Organize fields by hierarchy
    hierarchy = part.get_field_hierarchy()
    
    # Sort parent numbers properly
    sorted_parents = sorted(hierarchy.keys(), 
                          key=lambda x: int(x) if x.isdigit() else 999)
    
    for parent_num in sorted_parents:
        parent_data = hierarchy[parent_num]
        parent_field = parent_data['field']
        children = parent_data['children']
        
        # Add parent field
        data["fields"].append(parent_field.to_dict())
        
        # Add children
        for child in children:
            data["fields"].append(child.to_dict())
    
    # Add orphan fields
    orphan_fields = [f for f in part.fields if f.number not in hierarchy and not f.parent_number]
    for field in sorted(orphan_fields, key=lambda f: f.get_sort_key()):
        data["fields"].append(field.to_dict())
    
    json_str = json.dumps(data, indent=2, default=str)
    
    st.download_button(
        "💾 Download Part Data",
        json_str,
        f"part_{part.number}_data.json",
        "application/json",
        key=f"download_{key}"
    )

def export_mapped_fields(data: Dict):
    """Export all mapped fields organized by database object"""
    mapped = {}
    
    for part in data["parts"]:
        for field in part.fields:
            if field.is_mapped:
                if field.db_object not in mapped:
                    mapped[field.db_object] = {}
                
                # Create nested structure for paths with dots
                path_parts = field.db_path.split('.')
                current = mapped[field.db_object]
                
                for i, part_name in enumerate(path_parts[:-1]):
                    if part_name not in current:
                        current[part_name] = {}
                    current = current[part_name]
                
                # Set the value at the final path
                current[path_parts[-1]] = {
                    "field_number": field.number,
                    "label": field.label,
                    "value": str(field.value) if field.value else "",
                    "part": field.part_number,
                    "type": field.field_type
                }
    
    json_str = json.dumps(mapped, indent=2, default=str)
    
    st.download_button(
        "💾 Download Mapped Fields",
        json_str,
        "mapped_fields.json",
        "application/json",
        key=f"download_mapped_{uuid.uuid4().hex[:8]}"
    )

def export_questionnaire(data: Dict):
    """Export questionnaire responses"""
    quest_data = {
        "form": data["form_number"],
        "responses": {}
    }
    
    for part in data["parts"]:
        quest_fields = [f for f in part.fields if f.in_questionnaire]
        
        if quest_fields:
            part_key = f"Part_{part.number}"
            quest_data["responses"][part_key] = {
                "title": part.title,
                "questions": []
            }
            
            # Sort fields properly before export
            quest_fields.sort(key=lambda f: f.get_sort_key())
            
            for field in quest_fields:
                question_data = field.to_dict()
                
                # Add parent info if subfield
                if field.parent_number:
                    question_data["parent_field"] = field.parent_number
                
                quest_data["responses"][part_key]["questions"].append(question_data)
    
    json_str = json.dumps(quest_data, indent=2, default=str)
    
    st.download_button(
        "💾 Download Questionnaire",
        json_str,
        "questionnaire.json",
        "application/json",
        key=f"download_quest_{uuid.uuid4().hex[:8]}"
    )

def export_all_data(data: Dict):
    """Export complete form data"""
    export = {
        "form": {
            "number": data["form_number"],
            "title": data["form_title"]
        },
        "statistics": data["stats"],
        "parts": []
    }
    
    for part in data["parts"]:
        part_data = {
            "number": part.number,
            "title": part.title,
            "stats": part.get_stats(),
            "fields": []
        }
        
        # Export with hierarchy
        hierarchy = part.get_field_hierarchy()
        
        # Sort parent numbers properly
        sorted_parents = sorted(hierarchy.keys(), 
                              key=lambda x: int(x) if x.isdigit() else 999)
        
        for parent_num in sorted_parents:
            parent_data = hierarchy[parent_num]
            parent_field = parent_data['field']
            children = parent_data['children']
            
            # Add parent with children
            parent_export = parent_field.to_dict()
            parent_export["children"] = [child.to_dict() for child in children]
            part_data["fields"].append(parent_export)
        
        # Add orphan fields
        orphan_fields = [f for f in part.fields if f.number not in hierarchy and not f.parent_number]
        for field in sorted(orphan_fields, key=lambda f: f.get_sort_key()):
            part_data["fields"].append(field.to_dict())
        
        export["parts"].append(part_data)
    
    json_str = json.dumps(export, indent=2, default=str)
    
    st.download_button(
        "💾 Download Complete Form",
        json_str,
        f"{data['form_number']}_complete.json",
        "application/json",
        key=f"download_all_{uuid.uuid4().hex[:8]}"
    )

if __name__ == "__main__":
    main()
