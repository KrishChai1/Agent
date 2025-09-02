#!/usr/bin/env python3
"""
UNIVERSAL USCIS FORM READER - CORRECTED VERSION
================================================
Properly extracts all subfields (1.a, 1.b) and creates subfields for each option
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
    page_title="USCIS Form Reader - Complete",
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
    .field-context {
        background: #f0f0f0;
        padding: 10px;
        margin: 5px 0;
        border-radius: 5px;
        font-size: 0.9em;
        color: #333;
    }
    .option-field {
        background: #e3f2fd;
        border-left: 3px solid #2196f3;
        padding-left: 10px;
    }
</style>
""", unsafe_allow_html=True)

# ===== DATA STRUCTURES =====

@dataclass
class FormField:
    """Field structure"""
    item_number: str
    label: str
    field_type: str = "text"
    value: str = ""
    part_number: int = 1
    page_number: int = 1
    parent_number: str = ""
    is_parent: bool = False
    is_subfield: bool = False
    is_option: bool = False  # True if this is an option subfield (checkbox/radio)
    subfield_labels: List[str] = dataclass_field(default_factory=list)
    is_mapped: bool = False
    in_questionnaire: bool = False
    db_object: str = ""
    db_path: str = ""
    unique_id: str = ""
    field_context: str = ""  # Complete context from PDF
    sort_order: float = 0.0
    
    def __post_init__(self):
        if not self.unique_id:
            self.unique_id = str(uuid.uuid4())[:8]
        self._calculate_sort_order()
    
    def _calculate_sort_order(self):
        """Calculate sort order"""
        try:
            # Handle patterns like 1, 1.a, 1.a.1, etc.
            parts = self.item_number.replace('-', '.').split('.')
            order = 0.0
            
            # Main number
            if parts[0].isdigit():
                order = float(parts[0])
            
            # Subfield letter
            if len(parts) > 1 and parts[1]:
                if parts[1][0].isalpha():
                    order += (ord(parts[1][0].lower()) - ord('a') + 1) * 0.01
                elif parts[1].isdigit():
                    order += float(parts[1]) * 0.01
            
            # Sub-subfield
            if len(parts) > 2 and parts[2]:
                if parts[2].isdigit():
                    order += float(parts[2]) * 0.0001
            
            self.sort_order = order
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

# ===== DATABASE SCHEMA =====

DATABASE_SCHEMA = {
    "beneficiary": {
        "label": "👤 Beneficiary/Applicant",
        "paths": [
            "beneficiaryLastName",
            "beneficiaryFirstName", 
            "beneficiaryMiddleName",
            "beneficiaryOtherNamesUsed",
            "beneficiaryDateOfBirth",
            "beneficiarySsn",
            "alienNumber",
            "uscisOnlineAccount",
            "beneficiaryCountryOfBirth",
            "beneficiaryCityOfBirth",
            "beneficiaryProvinceOfBirth",
            "beneficiaryCitizenOfCountry",
            "beneficiaryGender",
            "beneficiaryMaritalStatus",
            "beneficiaryDaytimePhone",
            "beneficiaryMobilePhone",
            "beneficiaryEveningPhone",
            "beneficiaryEmail",
            "beneficiaryInCareOfName",
            "beneficiaryStreetNumberAndName",
            "beneficiaryAptSteFlrType",
            "beneficiaryAptSteFlrNumber",
            "beneficiaryCityOrTown",
            "beneficiaryState",
            "beneficiaryZipCode",
            "beneficiaryZipCodePlus4",
            "beneficiaryProvince",
            "beneficiaryPostalCode",
            "beneficiaryCountry",
            "currentNonimmigrantStatus",
            "i94ArrivalDepartureNumber",
            "passportNumber",
            "passportCountryOfIssuance",
            "passportDateOfIssuance",
            "passportDateOfExpiration",
            "dateOfLastArrival",
            "placeOfLastArrival"
        ]
    },
    "petitioner": {
        "label": "🏢 Petitioner/Employer",
        "paths": [
            "petitionerLastName",
            "petitionerFirstName",
            "petitionerMiddleName",
            "petitionerCompanyName",
            "petitionerInCareOfName",
            "petitionerStreetNumberAndName",
            "petitionerAptSteFlrType",
            "petitionerAptSteFlrNumber",
            "petitionerCityOrTown",
            "petitionerState",
            "petitionerZipCode",
            "petitionerZipCodePlus4",
            "petitionerProvince",
            "petitionerPostalCode",
            "petitionerCountry",
            "petitionerDaytimePhone",
            "petitionerEveningPhone",
            "petitionerMobilePhone",
            "petitionerEmail",
            "petitionerFein",
            "petitionerSsn",
            "petitionerIRSNumber"
        ]
    },
    "custom": {
        "label": "✏️ Custom Fields",
        "paths": []
    }
}

# ===== EXTRACTION FUNCTIONS =====

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

def get_field_context(text: str, field_number: str, start_pos: int = 0) -> str:
    """Extract complete context for a field from PDF"""
    try:
        # Find the field in text
        search_patterns = [
            rf'{re.escape(field_number)}\.?\s',
            rf'Item\s+Number\s+{re.escape(field_number)}',
            rf'Question\s+{re.escape(field_number)}'
        ]
        
        field_pos = -1
        for pattern in search_patterns:
            match = re.search(pattern, text[start_pos:], re.IGNORECASE)
            if match:
                field_pos = start_pos + match.start()
                break
        
        if field_pos == -1:
            return ""
        
        # Extract context (up to next field or 1000 chars)
        end_pos = min(field_pos + 1000, len(text))
        
        # Try to find next field
        next_field_pattern = r'\n\s*\d+\.?\s+[A-Z]'
        next_match = re.search(next_field_pattern, text[field_pos + 10:end_pos])
        if next_match:
            end_pos = field_pos + 10 + next_match.start()
        
        context = text[field_pos:end_pos]
        return context
        
    except:
        return ""

def extract_checkbox_options(context: str) -> List[Tuple[str, str]]:
    """Extract all checkbox/radio options with their complete content"""
    options = []
    
    # Patterns for checkboxes
    patterns = [
        r'[□☐]\s*([^\n□☐]{2,200})',  # Box symbols
        r'\[\s*\]\s*([^\n\[\]]{2,200})',  # Brackets
        r'○\s*([^\n○]{2,200})',  # Circle
        r'[A-Z]\.\s*([^\n]{2,200})',  # Letter options
        r'\d+\.\s*([^\n]{2,200})'  # Number options
    ]
    
    for pattern in patterns:
        matches = re.finditer(pattern, context)
        for match in matches:
            option_text = match.group(1).strip()
            
            # Clean and split option text
            option_text = re.sub(r'\s+', ' ', option_text)
            
            # Extract main option and description
            if '(' in option_text and ')' in option_text:
                main = option_text[:option_text.index('(')].strip()
                desc = option_text[option_text.index('(')+1:option_text.rindex(')')].strip()
                options.append((main, desc))
            elif ':' in option_text:
                parts = option_text.split(':', 1)
                options.append((parts[0].strip(), parts[1].strip()))
            else:
                options.append((option_text, ""))
    
    # Remove duplicates while preserving order
    seen = set()
    unique_options = []
    for opt in options:
        if opt[0] not in seen and len(opt[0]) > 1:
            seen.add(opt[0])
            unique_options.append(opt)
    
    return unique_options

# ===== FORM EXTRACTOR =====

class FormExtractor:
    """Extract form with all subfields and option subfields"""
    
    def __init__(self):
        self.client = None
        self.setup_openai()
    
    def setup_openai(self):
        """Setup OpenAI"""
        if not OPENAI_AVAILABLE:
            return
        
        try:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                api_key = st.secrets.get("OPENAI_API_KEY", None)
            
            if api_key:
                self.client = openai.OpenAI(api_key=api_key)
                st.success("✅ OpenAI connected")
        except Exception as e:
            st.warning(f"OpenAI setup failed: {str(e)[:100]}")
    
    def extract_form(self, full_text: str, page_texts: Dict[int, str], total_pages: int) -> USCISForm:
        """Extract complete form"""
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
            
            # Extract parts
            parts = self._extract_all_parts(full_text)
            
            if not parts:
                parts = [{"number": 1, "title": "Information"}]
            
            # Process each part
            for part_info in parts:
                st.info(f"Extracting Part {part_info['number']}: {part_info['title']}")
                
                part = FormPart(
                    number=part_info["number"],
                    title=part_info["title"]
                )
                
                # Extract ALL fields including subfields
                part_fields = self._extract_complete_fields(full_text, part_info)
                
                # Sort by field number
                part_fields.sort(key=lambda f: f.sort_order)
                
                part.fields = part_fields
                form.parts[part.number] = part
            
            return form
            
        except Exception as e:
            st.error(f"Extraction error: {str(e)}")
            return USCISForm()
    
    def _identify_form(self, text: str) -> Dict:
        """Identify form"""
        result = {"form_number": "Unknown", "form_title": "USCIS Form"}
        
        # Try patterns
        patterns = [
            r'Form\s+([A-Z]-\d+[A-Z]?)',
            r'USCIS\s+Form\s+([A-Z]-?\d+[A-Z]?)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result["form_number"] = match.group(1)
                break
        
        return result
    
    def _extract_all_parts(self, text: str) -> List[Dict]:
        """Extract all parts"""
        parts = []
        
        # Multiple patterns
        patterns = [
            r'Part\s+(\d+)[.\s\-–]+([^\n]{3,150})',
            r'PART\s+(\d+)[.\s\-–]+([^\n]{3,150})',
            r'Section\s+(\d+)[.\s\-–]+([^\n]{3,150})'
        ]
        
        found_parts = {}
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            
            for match in matches:
                try:
                    part_num = int(match.group(1))
                    part_title = match.group(2).strip()
                    
                    # Clean title
                    part_title = re.sub(r'^[.\-–\s]+', '', part_title)
                    part_title = re.sub(r'[.\s]+$', '', part_title)
                    
                    if part_num not in found_parts:
                        found_parts[part_num] = {
                            "number": part_num,
                            "title": part_title
                        }
                except:
                    continue
        
        parts = sorted(found_parts.values(), key=lambda x: x["number"])
        return parts
    
    def _extract_complete_fields(self, text: str, part_info: Dict) -> List[FormField]:
        """Extract ALL fields including 1.a, 1.b, etc. and create subfields for options"""
        part_num = part_info["number"]
        fields = []
        
        # Get part text
        part_text = self._get_part_text(text, part_num)
        
        # Comprehensive patterns to catch ALL field variations
        field_patterns = [
            # Standard patterns
            r'(\d+)\.\s+([^\n]{3,200})',  # 1. Field
            r'(\d+)\s+([A-Z][^\n]{3,200})',  # 1 Field
            r'Item\s+Number\s+(\d+)\.\s*([^\n]{3,200})',  # Item Number 1. Field
            
            # Subfield patterns - CRITICAL
            r'(\d+)\.([a-z])\.\s+([^\n]{3,200})',  # 1.a. Field
            r'(\d+)([a-z])\.\s+([^\n]{3,200})',  # 1a. Field
            r'(\d+)\s+([a-z])\.\s+([^\n]{3,200})',  # 1 a. Field
            r'([a-z])\.\s+([^\n]{3,200})',  # Just a. Field (when under a parent)
        ]
        
        found_fields = {}
        
        # First pass - extract all numbered fields
        for pattern in field_patterns[:3]:
            matches = re.finditer(pattern, part_text[:15000], re.IGNORECASE)
            
            for match in matches:
                try:
                    item_number = match.group(1)
                    label = match.group(2).strip() if len(match.groups()) > 1 else ""
                    
                    if item_number not in found_fields:
                        # Get complete context
                        context = get_field_context(part_text, item_number, match.start())
                        
                        field = FormField(
                            item_number=item_number,
                            label=label,
                            field_type="text",
                            part_number=part_num,
                            field_context=context
                        )
                        
                        # Check if this is a question with options
                        options = extract_checkbox_options(context)
                        if options:
                            field.is_parent = True
                            field.field_type = "question"
                            field.subfield_labels = [opt[0] for opt in options]
                        
                        found_fields[item_number] = field
                        
                        # Create subfields for options
                        if options:
                            for i, (option_label, option_desc) in enumerate(options):
                                letter = chr(ord('a') + i)
                                subfield_num = f"{item_number}.{letter}"
                                
                                subfield = FormField(
                                    item_number=subfield_num,
                                    label=option_label,
                                    field_type="checkbox",
                                    part_number=part_num,
                                    parent_number=item_number,
                                    is_subfield=True,
                                    is_option=True,
                                    field_context=option_desc
                                )
                                
                                found_fields[subfield_num] = subfield
                except:
                    continue
        
        # Second pass - extract lettered subfields (1.a, 1.b, etc.)
        # Look for patterns where we have number.letter
        subfield_patterns = [
            r'(\d+)\.([a-z])\.\s*([^\n]{3,200})',  # 1.a. Label
            r'(\d+)([a-z])\.\s*([^\n]{3,200})',  # 1a. Label
            r'\b([a-z])\.\s+([^\n]{3,200})',  # a. Label (when context shows it's under a number)
        ]
        
        for pattern in subfield_patterns:
            matches = re.finditer(pattern, part_text[:15000], re.IGNORECASE)
            
            for match in matches:
                try:
                    if len(match.groups()) == 3:
                        # Pattern with number and letter
                        parent_num = match.group(1)
                        letter = match.group(2)
                        label = match.group(3).strip()
                        item_number = f"{parent_num}.{letter}"
                    elif len(match.groups()) == 2:
                        # Just letter pattern - need to find parent
                        letter = match.group(1)
                        label = match.group(2).strip()
                        
                        # Look for parent number before this position
                        text_before = part_text[:match.start()]
                        parent_match = re.search(r'(\d+)\.\s+[^\n]+', text_before[::-1])
                        if parent_match:
                            parent_num = parent_match.group(1)[::-1]
                            item_number = f"{parent_num}.{letter}"
                        else:
                            continue
                    else:
                        continue
                    
                    if item_number not in found_fields:
                        # Get context
                        context = get_field_context(part_text, item_number, match.start())
                        
                        # Ensure parent exists
                        parent_num = item_number.split('.')[0]
                        if parent_num not in found_fields:
                            # Create parent
                            found_fields[parent_num] = FormField(
                                item_number=parent_num,
                                label=f"Field {parent_num}",
                                field_type="parent",
                                part_number=part_num,
                                is_parent=True
                            )
                        
                        # Create subfield
                        subfield = FormField(
                            item_number=item_number,
                            label=label,
                            field_type="text",
                            part_number=part_num,
                            parent_number=parent_num,
                            is_subfield=True,
                            field_context=context
                        )
                        
                        # Check for special types
                        label_lower = label.lower()
                        if any(word in label_lower for word in ["family name", "last name"]):
                            subfield.field_type = "text"
                        elif any(word in label_lower for word in ["given name", "first name"]):
                            subfield.field_type = "text"
                        elif any(word in label_lower for word in ["middle name"]):
                            subfield.field_type = "text"
                        elif "street" in label_lower and "number" in label_lower:
                            subfield.field_type = "address"
                        elif "apt" in label_lower or "ste" in label_lower or "flr" in label_lower:
                            subfield.field_type = "text"
                        elif "city" in label_lower:
                            subfield.field_type = "text"
                        elif "state" in label_lower:
                            subfield.field_type = "text"
                        elif "zip" in label_lower:
                            subfield.field_type = "zip"
                        elif "date" in label_lower:
                            subfield.field_type = "date"
                        
                        found_fields[item_number] = subfield
                        
                except Exception as e:
                    continue
        
        # Convert to list
        fields = list(found_fields.values())
        
        # If we have AI, try to get more fields
        if self.client and len(fields) < 10:
            ai_fields = self._extract_with_ai(part_text, part_num)
            
            # Merge AI fields
            for ai_field in ai_fields:
                if ai_field.item_number not in found_fields:
                    fields.append(ai_field)
        
        return fields
    
    def _extract_with_ai(self, text: str, part_num: int) -> List[FormField]:
        """Use AI to extract fields"""
        try:
            prompt = f"""Extract ALL fields from Part {part_num}.
            
            CRITICAL: Include ALL subfields like:
            1. Full Legal Name
            1.a. Family Name (Last Name)
            1.b. Given Name (First Name)
            1.c. Middle Name
            
            For questions with checkboxes, list each option as a subfield.
            
            Return JSON array:
            [{{
                "number": "1",
                "label": "Full Legal Name",
                "is_parent": true
            }},
            {{
                "number": "1.a",
                "label": "Family Name (Last Name)",
                "parent": "1"
            }}]
            """
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Extract form fields. Return JSON array only."},
                    {"role": "user", "content": prompt + "\n\n" + text[:4000]}
                ],
                temperature=0,
                max_tokens=3000
            )
            
            content = response.choices[0].message.content.strip()
            if "[" in content:
                json_str = content[content.find("["):content.rfind("]")+1]
                data = json.loads(json_str)
                
                fields = []
                for item in data:
                    field = FormField(
                        item_number=item.get("number", ""),
                        label=item.get("label", ""),
                        field_type="text",
                        part_number=part_num,
                        is_parent=item.get("is_parent", False),
                        parent_number=item.get("parent", ""),
                        is_subfield=bool(item.get("parent", ""))
                    )
                    fields.append(field)
                
                return fields
        except:
            return []
        
        return []
    
    def _get_part_text(self, text: str, part_num: int) -> str:
        """Get text for specific part"""
        try:
            # Find part
            pattern = f"Part\\s+{part_num}\\b"
            match = re.search(pattern, text, re.IGNORECASE)
            
            if match:
                start = match.start()
                
                # Find next part
                next_pattern = f"Part\\s+{part_num + 1}\\b"
                next_match = re.search(next_pattern, text[start:], re.IGNORECASE)
                
                if next_match:
                    end = start + next_match.start()
                else:
                    end = min(start + 20000, len(text))
                
                return text[start:end]
        except:
            pass
        
        return text[:20000]

# ===== UI COMPONENTS =====

def display_field(field: FormField, key_prefix: str):
    """Display field with complete context"""
    unique_key = f"{key_prefix}_{field.unique_id}"
    
    # Determine style
    if field.is_parent:
        card_class = "parent-field"
        status = "📁 Parent"
    elif field.is_option:
        card_class = "option-field"
        status = f"☑️ Option"
    elif field.is_subfield:
        card_class = "field-subfield"
        status = f"↳ Sub"
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
        # Show field number and label
        st.markdown(f'<span class="field-number-badge">{field.item_number}</span>**{field.label}**', unsafe_allow_html=True)
        
        # Show complete context from PDF if available
        if field.field_context and st.checkbox(f"Show context", key=f"{unique_key}_ctx"):
            st.markdown(f'<div class="field-context">{field.field_context[:500]}</div>', unsafe_allow_html=True)
        
        # Show subfield labels if parent
        if field.is_parent and field.subfield_labels:
            st.caption(f"Options/Subfields: {', '.join(field.subfield_labels[:5])}")
    
    with col2:
        if not field.is_parent:
            if field.field_type == "date":
                field.value = st.date_input("", key=f"{unique_key}_date", label_visibility="collapsed")
                field.value = str(field.value) if field.value else ""
            elif field.field_type == "checkbox" or field.is_option:
                field.value = st.checkbox("Select", key=f"{unique_key}_check")
                field.value = "Yes" if field.value else ""
            elif field.field_type == "textarea":
                field.value = st.text_area("", value=field.value, key=f"{unique_key}_area", height=60, label_visibility="collapsed")
            else:
                field.value = st.text_input("", value=field.value, key=f"{unique_key}_val", label_visibility="collapsed")
        else:
            st.info("See subfields")
    
    with col3:
        st.markdown(f"**{status}**")
        if not field.is_parent:
            c1, c2 = st.columns(2)
            with c1:
                if not field.is_mapped:
                    if st.button("Map", key=f"{unique_key}_map"):
                        st.session_state[f"mapping_{field.unique_id}"] = True
                        st.rerun()
                else:
                    if st.button("Unmap", key=f"{unique_key}_unmap"):
                        field.is_mapped = False
                        field.db_object = ""
                        field.db_path = ""
                        st.rerun()
            with c2:
                if not field.in_questionnaire:
                    if st.button("Quest", key=f"{unique_key}_quest"):
                        field.in_questionnaire = True
                        st.rerun()
                else:
                    if st.button("Remove", key=f"{unique_key}_remq"):
                        field.in_questionnaire = False
                        st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Mapping dialog
    if st.session_state.get(f"mapping_{field.unique_id}"):
        show_mapping(field, unique_key)

def show_mapping(field: FormField, unique_key: str):
    """Mapping interface with manual option"""
    st.markdown("---")
    st.markdown("### Map Field to Database")
    
    col1, col2 = st.columns(2)
    
    with col1:
        map_type = st.radio(
            "Mapping Type",
            ["Database Schema", "Manual Entry"],
            key=f"{unique_key}_maptype"
        )
    
    with col2:
        if map_type == "Database Schema":
            db_options = list(DATABASE_SCHEMA.keys())
            db_labels = [DATABASE_SCHEMA[k]["label"] for k in db_options]
            
            selected_idx = st.selectbox(
                "Database Object",
                range(len(db_options)),
                format_func=lambda x: db_labels[x],
                key=f"{unique_key}_dbobj"
            )
            
            selected_obj = db_options[selected_idx]
            
            if selected_obj == "custom":
                path = st.text_input("Custom path", key=f"{unique_key}_custompath")
            else:
                paths = DATABASE_SCHEMA[selected_obj]["paths"]
                path = st.selectbox("Field Path", [""] + paths, key=f"{unique_key}_path")
        else:
            selected_obj = st.text_input("Object Name", key=f"{unique_key}_manobj")
            path = st.text_input("Field Path", key=f"{unique_key}_manpath")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Apply Mapping", key=f"{unique_key}_apply"):
            if selected_obj and path:
                field.is_mapped = True
                field.db_object = selected_obj
                field.db_path = path
                del st.session_state[f"mapping_{field.unique_id}"]
                st.success(f"Mapped to {selected_obj}.{path}")
                st.rerun()
    with col2:
        if st.button("Cancel", key=f"{unique_key}_cancel"):
            del st.session_state[f"mapping_{field.unique_id}"]
            st.rerun()

# ===== MAIN APPLICATION =====

def main():
    st.markdown('<div class="main-header"><h1>📄 USCIS Form Reader</h1><p>Complete extraction with all subfields and options</p></div>', unsafe_allow_html=True)
    
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
                    st.info("Enter custom paths manually")
                else:
                    paths = info["paths"]
                    st.info(f"{len(paths)} fields")
                    for path in paths[:10]:
                        st.code(path, language="")
        
        if st.button("🔄 Clear All", use_container_width=True):
            st.session_state.clear()
            st.rerun()
    
    # Main tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📤 Upload",
        "🔗 Map Fields",
        "📝 Questionnaire",
        "💾 Export"
    ])
    
    with tab1:
        st.markdown("### Upload USCIS Form PDF")
        st.info("Extracts ALL fields including 1.a, 1.b, etc. and creates subfields for each checkbox option")
        
        uploaded_file = st.file_uploader("Choose PDF", type=['pdf'])
        
        if uploaded_file:
            if st.button("🚀 Extract Complete Form", type="primary", use_container_width=True):
                with st.spinner("Extracting all fields and subfields..."):
                    try:
                        # Extract PDF
                        full_text, page_texts, total_pages = extract_pdf_text(uploaded_file)
                        
                        if full_text:
                            # Extract form
                            form = st.session_state.extractor.extract_form(
                                full_text, page_texts, total_pages
                            )
                            st.session_state.form = form
                            
                            # Show results
                            st.success(f"✅ Extracted: {form.form_number}")
                            
                            # Show parts and fields
                            for part_num, part in form.parts.items():
                                total = len(part.fields)
                                parents = sum(1 for f in part.fields if f.is_parent)
                                subfields = sum(1 for f in part.fields if f.is_subfield)
                                options = sum(1 for f in part.fields if f.is_option)
                                
                                st.success(
                                    f"**Part {part_num}: {part.title}**\n"
                                    f"• Total: {total} fields\n"
                                    f"• Parents: {parents}\n"
                                    f"• Subfields: {subfields}\n"
                                    f"• Option fields: {options}"
                                )
                                
                                # Show sample fields
                                if st.checkbox(f"Show fields from Part {part_num}", key=f"show_p{part_num}"):
                                    for field in part.fields[:20]:
                                        st.text(f"  {field.item_number}: {field.label[:60]}")
                        else:
                            st.error("Could not extract text")
                    
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
    
    with tab2:
        st.markdown("### Map Fields to Database")
        
        if st.session_state.form:
            form = st.session_state.form
            
            # Part selector
            part_nums = sorted(form.parts.keys())
            selected_part = st.selectbox(
                "Select Part",
                part_nums,
                format_func=lambda x: f"Part {x}: {form.parts[x].title}"
            )
            
            if selected_part:
                part = form.parts[selected_part]
                st.info(f"Showing {len(part.fields)} fields from Part {selected_part}")
                
                # Sort and display fields
                sorted_fields = sorted(part.fields, key=lambda f: f.sort_order)
                
                # Track displayed
                displayed = set()
                
                for field in sorted_fields:
                    if field.item_number in displayed:
                        continue
                    
                    # Skip subfields of non-parent fields
                    if field.is_subfield and field.parent_number in displayed:
                        continue
                    
                    # Display field
                    display_field(field, f"p{selected_part}")
                    displayed.add(field.item_number)
                    
                    # Display subfields if parent
                    if field.is_parent:
                        for sub in sorted_fields:
                            if sub.parent_number == field.item_number:
                                display_field(sub, f"p{selected_part}")
                                displayed.add(sub.item_number)
        else:
            st.info("Upload a form first")
    
    with tab3:
        st.markdown("### Questionnaire Fields")
        
        if st.session_state.form:
            has_questions = False
            
            for part_num in sorted(st.session_state.form.parts.keys()):
                part = st.session_state.form.parts[part_num]
                quest_fields = [f for f in part.fields if f.in_questionnaire]
                
                if quest_fields:
                    has_questions = True
                    st.markdown(f"#### Part {part_num}: {part.title}")
                    
                    for field in sorted(quest_fields, key=lambda f: f.sort_order):
                        st.markdown(f"**{field.item_number}. {field.label}**")
                        
                        # Show context
                        if field.field_context:
                            with st.expander("Show full context from PDF"):
                                st.text(field.field_context[:1000])
                        
                        # Input based on type
                        if field.is_option or field.field_type == "checkbox":
                            field.value = st.checkbox(
                                "Check if applicable",
                                key=f"q_{field.unique_id}"
                            )
                            field.value = "Yes" if field.value else "No"
                        else:
                            field.value = st.text_area(
                                "Answer:",
                                value=field.value,
                                key=f"q_{field.unique_id}"
                            )
                        
                        st.markdown("---")
            
            if not has_questions:
                st.info("No questionnaire fields. Use 'Quest' button to add.")
        else:
            st.info("Upload a form first")
    
    with tab4:
        st.markdown("### Export Data")
        
        if st.session_state.form:
            form = st.session_state.form
            
            # Build export
            export_data = {
                "form": form.form_number,
                "parts": {}
            }
            
            for part_num, part in form.parts.items():
                part_data = {
                    "title": part.title,
                    "fields": []
                }
                
                for field in sorted(part.fields, key=lambda f: f.sort_order):
                    field_data = {
                        "number": field.item_number,
                        "label": field.label,
                        "type": field.field_type,
                        "value": field.value,
                        "is_subfield": field.is_subfield,
                        "is_option": field.is_option,
                        "parent": field.parent_number if field.is_subfield else None
                    }
                    
                    if field.is_mapped:
                        field_data["mapping"] = f"{field.db_object}.{field.db_path}"
                    
                    if field.field_context:
                        field_data["context"] = field.field_context[:200]
                    
                    part_data["fields"].append(field_data)
                
                export_data["parts"][f"Part_{part_num}"] = part_data
            
            # Export button
            json_str = json.dumps(export_data, indent=2)
            
            st.download_button(
                "📥 Download Complete Export",
                json_str,
                f"{form.form_number}_complete.json",
                "application/json",
                use_container_width=True
            )
            
            # Show preview
            with st.expander("Preview"):
                st.json(export_data)
        else:
            st.info("Upload a form first")

if __name__ == "__main__":
    main()
