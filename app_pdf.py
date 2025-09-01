#!/usr/bin/env python3
"""
UNIVERSAL USCIS FORM READER - FIXED VERSION
============================================
Stable version with proper error handling and part extraction
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
    page_title="USCIS Form Reader",
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
    subfield_labels: List[str] = dataclass_field(default_factory=list)
    is_mapped: bool = False
    in_questionnaire: bool = False
    db_object: str = ""
    db_path: str = ""
    unique_id: str = ""
    options: List[str] = dataclass_field(default_factory=list)
    option_contexts: Dict[str, str] = dataclass_field(default_factory=dict)
    has_options: bool = False
    validation_errors: List[str] = dataclass_field(default_factory=list)
    
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
            "beneficiaryDateOfBirth",
            "beneficiarySsn",
            "alienNumber",
            "uscisOnlineAccount",
            "beneficiaryCountryOfBirth",
            "beneficiaryCityOfBirth",
            "beneficiaryCitizenOfCountry",
            "beneficiaryPhone",
            "beneficiaryEmail",
            "homeAddress.inCareOf",
            "homeAddress.streetNumber",
            "homeAddress.streetName",
            "homeAddress.aptType",
            "homeAddress.aptNumber",
            "homeAddress.city",
            "homeAddress.state",
            "homeAddress.zipCode",
            "homeAddress.country",
            "currentStatus",
            "statusExpirationDate",
            "passportNumber",
            "passportCountry",
            "i94Number",
            "maritalStatus"
        ]
    },
    "petitioner": {
        "label": "🏢 Petitioner/Employer",
        "paths": [
            "companyName",
            "companyTaxId",
            "signatoryFirstName",
            "signatoryLastName",
            "signatoryTitle",
            "signatoryPhone",
            "signatoryEmail",
            "companyAddress.streetNumber",
            "companyAddress.streetName",
            "companyAddress.suite",
            "companyAddress.city",
            "companyAddress.state",
            "companyAddress.zipCode",
            "yearEstablished",
            "numberOfEmployees",
            "grossAnnualIncome",
            "businessType"
        ]
    },
    "attorney": {
        "label": "⚖️ Attorney",
        "paths": [
            "attorneyLastName",
            "attorneyFirstName",
            "attorneyPhone",
            "attorneyEmail",
            "attorneyBarNumber",
            "lawFirmName"
        ]
    },
    "custom": {
        "label": "✏️ Custom",
        "paths": []
    }
}

# ===== HELPER FUNCTIONS =====

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
                full_text += f"\n=== PAGE {page_num + 1} ===\n{text}"
        
        total_pages = len(doc)
        doc.close()
        
        return full_text, page_texts, total_pages
        
    except Exception as e:
        st.error(f"PDF error: {str(e)[:200]}")
        return "", {}, 0

def extract_field_options(label: str, context: str = "") -> Tuple[List[str], Dict[str, str]]:
    """Extract options from field label and context"""
    options = []
    option_contexts = {}
    label_lower = label.lower()
    
    # Look for checkbox patterns in context
    if context:
        # Pattern: □ Option or ☐ Option
        checkbox_patterns = [
            r'[□☐]\s*([^\n□☐]{2,50})',
            r'\[\s*\]\s*([^\n\[\]]{2,50})',
            r'○\s*([^\n○]{2,50})'
        ]
        
        for pattern in checkbox_patterns:
            matches = re.findall(pattern, context[:500])
            for match in matches[:10]:  # Limit to 10 options
                option = match.strip()
                if option and len(option) > 1:
                    options.append(option)
                    # Try to find context after the option
                    context_pattern = re.escape(option) + r'[:\-\s]*([^\n□☐\[\]○]{5,100})'
                    context_match = re.search(context_pattern, context)
                    if context_match:
                        option_contexts[option] = context_match.group(1).strip()
    
    # Predefined options for common fields
    if not options:
        if any(word in label_lower for word in ["yes/no", "yes or no", "are you", "do you"]):
            options = ["Yes", "No"]
        elif "gender" in label_lower:
            options = ["Male", "Female", "Other"]
        elif "marital" in label_lower:
            options = ["Single", "Married", "Divorced", "Widowed", "Separated"]
        elif "relationship" in label_lower:
            options = ["Spouse", "Child", "Parent", "Sibling", "Other"]
    
    return options, option_contexts

def detect_field_type(label: str, context: str = "") -> str:
    """Detect field type from label"""
    label_lower = label.lower()
    
    if any(word in label_lower for word in ["date", "birth", "expir"]):
        return "date"
    elif any(word in label_lower for word in ["email"]):
        return "email"
    elif any(word in label_lower for word in ["phone", "telephone"]):
        return "phone"
    elif "ssn" in label_lower or "social security" in label_lower:
        return "ssn"
    elif "alien number" in label_lower or "a-number" in label_lower:
        return "alien_number"
    elif any(word in label_lower for word in ["check", "select", "choose"]):
        return "checkbox"
    elif any(word in label_lower for word in ["explain", "describe"]):
        return "textarea"
    elif "zip" in label_lower:
        return "zip"
    
    return "text"

def detect_address_components(label: str) -> List[str]:
    """Detect address components"""
    label_lower = label.lower()
    
    if "address" in label_lower:
        if "foreign" in label_lower:
            return [
                "Street Number and Name",
                "City or Town",
                "Province",
                "Postal Code",
                "Country"
            ]
        else:
            return [
                "In Care Of Name",
                "Street Number",
                "Street Name",
                "Apt./Ste./Flr. Type",
                "Apt./Ste./Flr. Number",
                "City or Town",
                "State",
                "ZIP Code",
                "ZIP Code Plus 4"
            ]
    elif "name" in label_lower and ("full" in label_lower or "legal" in label_lower):
        return [
            "Family Name (Last Name)",
            "Given Name (First Name)",
            "Middle Name"
        ]
    
    return []

# ===== FORM EXTRACTOR =====

class FormExtractor:
    """Form extraction with AI support"""
    
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
                st.success("✅ OpenAI connected")
        except Exception as e:
            st.warning(f"OpenAI setup failed: {str(e)[:100]}")
            self.client = None
    
    def extract_form(self, full_text: str, page_texts: Dict[int, str], total_pages: int) -> USCISForm:
        """Extract form structure and fields"""
        try:
            # Identify form
            form_info = self._identify_form(full_text[:3000])
            
            form = USCISForm(
                form_number=form_info.get("form_number", "Unknown"),
                form_title=form_info.get("form_title", "USCIS Form"),
                edition_date=form_info.get("edition_date", ""),
                total_pages=total_pages,
                raw_text=full_text
            )
            
            # Extract parts
            parts = self._extract_parts(full_text)
            
            # Process each part
            for part_info in parts:
                part = FormPart(
                    number=part_info["number"],
                    title=part_info["title"],
                    page_start=part_info.get("page_start", 1),
                    page_end=part_info.get("page_end", 1)
                )
                
                # Extract fields for this part
                part_fields = self._extract_fields(full_text, part_info)
                part.fields = part_fields
                
                form.parts[part.number] = part
            
            # If no parts found, create default
            if not form.parts:
                form.parts[1] = FormPart(
                    number=1,
                    title="Main Section",
                    fields=self._extract_fields(full_text, {"number": 1, "title": "Main"})
                )
            
            return form
            
        except Exception as e:
            st.error(f"Extraction error: {str(e)[:200]}")
            # Return minimal form
            return USCISForm(
                form_number="Unknown",
                form_title="USCIS Form",
                total_pages=total_pages,
                parts={1: FormPart(number=1, title="Main Section", fields=[])}
            )
    
    def _identify_form(self, text: str) -> Dict:
        """Identify form type"""
        result = {"form_number": "Unknown", "form_title": "USCIS Form", "edition_date": ""}
        
        # Try regex first
        form_match = re.search(r'Form\s+([A-Z]-?\d+[A-Z]?)', text)
        if form_match:
            result["form_number"] = form_match.group(1)
        
        # Try AI if available
        if self.client:
            try:
                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "Extract form information. Return JSON only."},
                        {"role": "user", "content": f"Extract form number, title, edition date from:\n{text[:1000]}"}
                    ],
                    temperature=0,
                    max_tokens=200
                )
                
                content = response.choices[0].message.content.strip()
                if content.startswith("{"):
                    result.update(json.loads(content))
            except:
                pass
        
        return result
    
    def _extract_parts(self, text: str) -> List[Dict]:
        """Extract parts from form"""
        parts = []
        
        # Try AI extraction
        if self.client:
            try:
                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "Extract form parts. Return JSON array only."},
                        {"role": "user", "content": f"Extract all parts (number and title) from:\n{text[:5000]}"}
                    ],
                    temperature=0,
                    max_tokens=1000
                )
                
                content = response.choices[0].message.content.strip()
                if content.startswith("["):
                    parts = json.loads(content)
                    if parts:
                        return parts
            except:
                pass
        
        # Fallback to regex
        part_pattern = r'Part\s+(\d+)[.\s\-]+([^\n]{3,100})'
        matches = re.finditer(part_pattern, text, re.IGNORECASE)
        
        for match in matches:
            try:
                part_num = int(match.group(1))
                part_title = match.group(2).strip()
                # Clean title
                part_title = re.sub(r'[.\s]+$', '', part_title)
                
                parts.append({
                    "number": part_num,
                    "title": part_title,
                    "page_start": 1,
                    "page_end": 1
                })
            except:
                continue
        
        # If no parts found, create default
        if not parts:
            parts = [{"number": 1, "title": "Information", "page_start": 1, "page_end": 1}]
        
        return parts
    
    def _extract_fields(self, text: str, part_info: Dict) -> List[FormField]:
        """Extract fields for a part"""
        fields = []
        part_num = part_info["number"]
        
        # Try to get part-specific text
        part_text = self._get_part_text(text, part_num)
        
        # Try AI extraction
        if self.client and len(part_text) > 100:
            try:
                ai_fields = self._extract_fields_with_ai(part_text, part_num)
                if ai_fields:
                    return ai_fields
            except:
                pass
        
        # Fallback to pattern extraction
        return self._extract_fields_with_patterns(part_text, part_num)
    
    def _get_part_text(self, text: str, part_num: int) -> str:
        """Get text for specific part"""
        try:
            # Find start of part
            part_pattern = f"Part\\s+{part_num}\\b"
            match = re.search(part_pattern, text, re.IGNORECASE)
            
            if match:
                start = match.start()
                # Find next part
                next_pattern = f"Part\\s+{part_num + 1}\\b"
                next_match = re.search(next_pattern, text[start:], re.IGNORECASE)
                
                if next_match:
                    end = start + next_match.start()
                    return text[start:end]
                else:
                    # Take up to 10000 chars
                    return text[start:min(start + 10000, len(text))]
        except:
            pass
        
        # Return first portion if part not found
        return text[:10000]
    
    def _extract_fields_with_ai(self, text: str, part_num: int) -> List[FormField]:
        """Extract fields using AI"""
        try:
            prompt = f"""Extract all form fields from Part {part_num}.
            For each field include:
            - item_number (like "1", "1.a", "2.b")
            - label (complete field label)
            - type (text, date, checkbox, select, address, name)
            - options (if checkbox/select)
            
            Return JSON array only."""
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Extract form fields. Return valid JSON array only."},
                    {"role": "user", "content": prompt + "\n\n" + text[:4000]}
                ],
                temperature=0,
                max_tokens=3000
            )
            
            content = response.choices[0].message.content.strip()
            
            # Clean response
            if "```" in content:
                content = content.split("```")[1].replace("json", "").strip()
            
            if not content.startswith("["):
                # Try to find JSON array in response
                match = re.search(r'\[.*\]', content, re.DOTALL)
                if match:
                    content = match.group(0)
            
            raw_fields = json.loads(content)
            
            # Convert to FormField objects
            fields = []
            for field_data in raw_fields:
                item_number = str(field_data.get("item_number", "")).strip()
                label = field_data.get("label", "").strip()
                
                if not item_number or not label:
                    continue
                
                # Get field type and options
                field_type = field_data.get("type", "text")
                options = field_data.get("options", [])
                
                # Check if address field needs components
                components = detect_address_components(label)
                
                # Determine if parent/subfield
                is_subfield = '.' in item_number and len(item_number.split('.')) == 2
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
                
                # Add subfields for components
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
            st.warning(f"AI extraction failed: {str(e)[:100]}")
            return []
    
    def _extract_fields_with_patterns(self, text: str, part_num: int) -> List[FormField]:
        """Extract fields using regex patterns"""
        fields = []
        
        # Field pattern
        field_pattern = r'(\d+\.?[a-z]?)\s*[.\-\s]*([^\n]{5,150})'
        matches = re.finditer(field_pattern, text[:8000])
        
        count = 0
        for match in matches:
            if count >= 50:  # Limit fields
                break
            
            item_number = match.group(1).strip('.').strip()
            label = match.group(2).strip()
            
            # Skip if too short or invalid
            if len(label) < 3 or not item_number[0].isdigit():
                continue
            
            # Get context for options
            start = match.start()
            end = min(start + 500, len(text))
            context = text[start:end]
            
            # Extract options
            options, option_contexts = extract_field_options(label, context)
            
            # Detect type
            field_type = detect_field_type(label, context)
            
            # Check for address components
            components = detect_address_components(label)
            
            # Determine if parent/subfield
            is_subfield = '.' in item_number and len(item_number.split('.')) == 2
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
            
            fields.append(field)
            count += 1
            
            # Add subfields for components
            if components and not is_subfield:
                for i, comp in enumerate(components):
                    if i >= 10:  # Limit subfields
                        break
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
                    count += 1
        
        return fields

# ===== VALIDATION =====

def validate_field(field: FormField) -> List[str]:
    """Validate field value"""
    errors = []
    
    if not field.value:
        return []
    
    if field.field_type == "ssn":
        if not re.match(r'^\d{3}-?\d{2}-?\d{4}$', field.value):
            errors.append("SSN format: XXX-XX-XXXX")
    elif field.field_type == "email":
        if "@" not in field.value or "." not in field.value:
            errors.append("Invalid email format")
    elif field.field_type == "phone":
        digits = re.sub(r'\D', '', field.value)
        if len(digits) != 10:
            errors.append("Phone must have 10 digits")
    elif field.field_type == "zip":
        if not re.match(r'^\d{5}(-\d{4})?$', field.value):
            errors.append("ZIP format: XXXXX or XXXXX-XXXX")
    
    return errors

# ===== UI COMPONENTS =====

def display_field(field: FormField, key_prefix: str):
    """Display a field"""
    unique_key = f"{key_prefix}_{field.unique_id}"
    
    # Validate
    field.validation_errors = validate_field(field)
    
    # Determine style
    if field.is_parent:
        card_class = "parent-field"
        status = "📁 Parent"
    elif field.validation_errors:
        card_class = "field-card validation-error"
        status = "⚠️ Error"
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
        
        # Show options
        if field.options:
            st.caption("Options:")
            for opt in field.options:
                context = field.option_contexts.get(opt, "")
                if context:
                    st.markdown(f'<span class="option-chip">{opt}</span> - {context}', unsafe_allow_html=True)
                else:
                    st.markdown(f'<span class="option-chip">{opt}</span>', unsafe_allow_html=True)
        
        # Show validation errors
        for error in field.validation_errors:
            st.error(error)
    
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
    st.markdown("### Map Field")
    
    col1, col2 = st.columns(2)
    
    with col1:
        db_options = list(DATABASE_SCHEMA.keys())
        selected = st.selectbox(
            "Database Object",
            db_options,
            key=f"{unique_key}_dbobj"
        )
    
    with col2:
        if selected:
            paths = DATABASE_SCHEMA[selected]["paths"]
            if selected == "custom":
                path = st.text_input("Custom path", key=f"{unique_key}_path")
            else:
                path = st.selectbox("Field Path", [""] + paths, key=f"{unique_key}_path")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Apply", key=f"{unique_key}_apply"):
            if selected and path:
                field.is_mapped = True
                field.db_object = selected
                field.db_path = path
                del st.session_state[f"mapping_{field.unique_id}"]
                st.rerun()
    with col2:
        if st.button("Cancel", key=f"{unique_key}_cancel"):
            del st.session_state[f"mapping_{field.unique_id}"]
            st.rerun()

# ===== MAIN APP =====

def main():
    st.markdown('<div class="main-header"><h1>📄 USCIS Form Reader</h1></div>', unsafe_allow_html=True)
    
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
                paths = info["paths"]
                for path in paths[:5]:
                    st.code(path)
                if len(paths) > 5:
                    st.caption(f"+{len(paths)-5} more")
        
        if st.button("🔄 Clear All", use_container_width=True):
            st.session_state.clear()
            st.rerun()
    
    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📤 Upload", "🔗 Map Fields", "📝 Questionnaire", "💾 Export"])
    
    with tab1:
        st.markdown("### Upload USCIS Form PDF")
        
        uploaded_file = st.file_uploader("Choose PDF", type=['pdf'])
        
        if uploaded_file:
            if st.button("🚀 Extract Form", type="primary", use_container_width=True):
                with st.spinner("Extracting..."):
                    try:
                        # Extract PDF text
                        full_text, page_texts, total_pages = extract_pdf_text(uploaded_file)
                        
                        if full_text:
                            # Extract form
                            form = st.session_state.extractor.extract_form(
                                full_text, page_texts, total_pages
                            )
                            st.session_state.form = form
                            
                            # Show results
                            st.success(f"✅ Extracted: {form.form_number}")
                            
                            # Statistics
                            total_parts = len(form.parts)
                            total_fields = sum(len(p.fields) for p in form.parts.values())
                            
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Parts", total_parts)
                            with col2:
                                st.metric("Fields", total_fields)
                            with col3:
                                st.metric("Pages", total_pages)
                            
                            # Show parts
                            st.markdown("### Extracted Parts:")
                            for part_num, part in form.parts.items():
                                st.info(f"**Part {part_num}**: {part.title} ({len(part.fields)} fields)")
                        else:
                            st.error("Could not extract text from PDF")
                    
                    except Exception as e:
                        st.error(f"Error: {str(e)[:200]}")
    
    with tab2:
        st.markdown("### Map Fields to Database")
        
        if st.session_state.form:
            form = st.session_state.form
            
            # Show each part
            for part_num, part in form.parts.items():
                with st.expander(f"Part {part_num}: {part.title} ({len(part.fields)} fields)", expanded=(part_num == 1)):
                    
                    if not part.fields:
                        st.warning("No fields found in this part")
                        continue
                    
                    # Display fields
                    displayed = set()
                    
                    for field in part.fields:
                        if field.item_number in displayed:
                            continue
                        
                        # Skip subfields (shown with parent)
                        if field.is_subfield:
                            continue
                        
                        # Display field
                        display_field(field, f"p{part_num}")
                        displayed.add(field.item_number)
                        
                        # Display subfields
                        if field.is_parent:
                            for subfield in part.fields:
                                if subfield.parent_number == field.item_number:
                                    display_field(subfield, f"p{part_num}")
                                    displayed.add(subfield.item_number)
        else:
            st.info("Please upload a form first")
    
    with tab3:
        st.markdown("### Questionnaire Fields")
        
        if st.session_state.form:
            has_questions = False
            
            for part in st.session_state.form.parts.values():
                quest_fields = [f for f in part.fields if f.in_questionnaire and not f.is_parent]
                
                if quest_fields:
                    has_questions = True
                    st.markdown(f"#### Part {part.number}: {part.title}")
                    
                    for field in quest_fields:
                        st.markdown(f"**{field.item_number}. {field.label}**")
                        
                        # Show all options with contexts
                        if field.options:
                            st.caption("Available options:")
                            for opt in field.options:
                                context = field.option_contexts.get(opt, "")
                                if context:
                                    st.write(f"• **{opt}** - {context}")
                                else:
                                    st.write(f"• {opt}")
                            
                            field.value = st.selectbox(
                                "Select answer",
                                [""] + field.options,
                                key=f"q_{field.unique_id}"
                            )
                        else:
                            field.value = st.text_area(
                                "Answer",
                                value=field.value,
                                key=f"q_{field.unique_id}"
                            )
                        
                        if st.button("Remove", key=f"qr_{field.unique_id}"):
                            field.in_questionnaire = False
                            st.rerun()
                        
                        st.markdown("---")
            
            if not has_questions:
                st.info("No questionnaire fields. Use 'Quest' button in Map Fields tab.")
        else:
            st.info("Please upload a form first")
    
    with tab4:
        st.markdown("### Export Data")
        
        if st.session_state.form:
            form = st.session_state.form
            
            # Build export data
            export_data = {
                "form_info": {
                    "form_number": form.form_number,
                    "form_title": form.form_title,
                    "edition_date": form.edition_date,
                    "total_pages": form.total_pages
                },
                "parts": [],
                "mapped_fields": [],
                "questionnaire_fields": []
            }
            
            for part in form.parts.values():
                part_data = {
                    "number": part.number,
                    "title": part.title,
                    "fields": []
                }
                
                for field in part.fields:
                    if not field.is_parent:
                        field_data = {
                            "part": part.number,
                            "number": field.item_number,
                            "label": field.label,
                            "type": field.field_type,
                            "value": field.value
                        }
                        
                        if field.options:
                            field_data["options"] = field.options
                            field_data["option_contexts"] = field.option_contexts
                        
                        if field.is_mapped:
                            field_data["mapping"] = f"{field.db_object}.{field.db_path}"
                            export_data["mapped_fields"].append(field_data)
                        
                        if field.in_questionnaire:
                            export_data["questionnaire_fields"].append(field_data)
                        
                        part_data["fields"].append(field_data)
                
                export_data["parts"].append(part_data)
            
            # Export button
            json_str = json.dumps(export_data, indent=2)
            
            st.download_button(
                "📥 Download Complete Export (JSON)",
                json_str,
                f"{form.form_number}_export.json",
                "application/json",
                use_container_width=True
            )
            
            # Show summary
            st.markdown("### Export Summary")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Fields", sum(len(p["fields"]) for p in export_data["parts"]))
            with col2:
                st.metric("Mapped Fields", len(export_data["mapped_fields"]))
            with col3:
                st.metric("Questionnaire", len(export_data["questionnaire_fields"]))
        else:
            st.info("Please upload a form first")

if __name__ == "__main__":
    main()
