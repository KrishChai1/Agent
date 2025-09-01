#!/usr/bin/env python3
"""
UNIVERSAL USCIS FORM READER - ENHANCED WITH OPTIONS & TYPESCRIPT EXPORT
========================================================================
Features:
- Extracts field options from checkboxes/selects
- Shows all options in questionnaire view
- Exports mapped fields as TypeScript
- Exports questionnaire as JSON by part
"""

import streamlit as st
import json
import re
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field
import uuid

# Page config
st.set_page_config(
    page_title="Universal USCIS Form Reader",
    page_icon="📄",
    layout="wide"
)

# Check imports
try:
    import fitz
    PYMUPDF_AVAILABLE = True
except:
    PYMUPDF_AVAILABLE = False
    st.error("Install PyMuPDF: pip install pymupdf")

try:
    import openai
    OPENAI_AVAILABLE = True
except:
    OPENAI_AVAILABLE = False
    st.error("Install OpenAI: pip install openai")

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
        transition: all 0.2s ease;
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
    .option-chip {
        display: inline-block;
        padding: 4px 8px;
        margin: 2px;
        background: #e3f2fd;
        border: 1px solid #2196f3;
        border-radius: 16px;
        font-size: 0.9em;
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
</style>
""", unsafe_allow_html=True)

# ===== DATA STRUCTURES =====

@dataclass
class FormField:
    """Universal field structure with subfield and options support"""
    item_number: str
    label: str
    field_type: str = "text"
    value: str = ""
    part_number: int = 1
    page_number: int = 1
    parent_number: str = ""  # Parent field number (e.g., "1" for "1.a")
    is_parent: bool = False  # True if this field has subfields
    is_subfield: bool = False
    subfield_labels: List[str] = field(default_factory=list)  # For parent fields
    is_mapped: bool = False
    in_questionnaire: bool = False
    db_object: str = ""
    db_path: str = ""
    unique_id: str = ""
    options: List[str] = field(default_factory=list)  # For checkbox/select fields
    has_options: bool = False
    
    def __post_init__(self):
        if not self.unique_id:
            self.unique_id = str(uuid.uuid4())[:8]
        # Check if field has options
        if self.options:
            self.has_options = True

@dataclass
class FormPart:
    """Part structure"""
    number: int
    title: str
    fields: List[FormField] = field(default_factory=list)
    page_start: int = 1
    page_end: int = 1

@dataclass
class USCISForm:
    """Form container"""
    form_number: str = "Unknown"
    form_title: str = "USCIS Form"
    edition_date: str = ""
    total_pages: int = 0
    parts: Dict[int, FormPart] = field(default_factory=dict)
    raw_text: str = ""

# ===== COMPLETE DATABASE SCHEMA =====

DATABASE_SCHEMA = {
    "beneficiary": {
        "label": "👤 Beneficiary/Applicant Information",
        "paths": [
            "beneficiaryLastName",
            "beneficiaryFirstName", 
            "beneficiaryMiddleName",
            "beneficiaryDateOfBirth",
            "beneficiarySsn",
            "alienNumber",
            "uscisOnlineAccount",
            "beneficiaryCountryOfBirth",
            "beneficiaryCitizenOfCountry",
            "beneficiaryCellNumber",
            "beneficiaryWorkNumber",
            "beneficiaryPrimaryEmailAddress",
            "homeAddress.addressStreet",
            "homeAddress.addressCity",
            "homeAddress.addressState",
            "homeAddress.addressZip",
            "homeAddress.addressCountry",
            "physicalAddress.addressStreet",
            "physicalAddress.addressCity",
            "physicalAddress.addressState",
            "physicalAddress.addressZip",
            "currentNonimmigrantStatus",
            "statusExpirationDate",
            "lastArrivalDate",
            "passportNumber",
            "passportCountry",
            "passportExpirationDate",
            "i94Number",
            "travelDocumentNumber",
            "sevisId",
            "dsNumber"
        ]
    },
    "petitioner": {
        "label": "🏢 Petitioner/Employer Information",
        "paths": [
            "petitionerName",
            "petitionerLastName",
            "petitionerFirstName",
            "petitionerMiddleName",
            "companyName",
            "companyTaxId",
            "companyWebsite",
            "signatoryFirstName",
            "signatoryLastName",
            "signatoryMiddleName",
            "signatoryWorkPhone",
            "signatoryMobilePhone",
            "signatoryEmailAddress",
            "signatoryJobTitle",
            "companyAddress.street",
            "companyAddress.city",
            "companyAddress.state",
            "companyAddress.zip",
            "companyAddress.country",
            "yearEstablished",
            "numberOfEmployees",
            "grossAnnualIncome",
            "netAnnualIncome",
            "nafcsCode",
            "businessType"
        ]
    },
    "dependent": {
        "label": "👥 Dependent/Family Member Information",
        "paths": [
            "dependent[].lastName",
            "dependent[].firstName",
            "dependent[].middleName",
            "dependent[].dateOfBirth",
            "dependent[].countryOfBirth",
            "dependent[].countryOfCitizenship",
            "dependent[].alienNumber",
            "dependent[].i94Number",
            "dependent[].passportNumber",
            "dependent[].relationship",
            "dependent[].address.street",
            "dependent[].address.city",
            "dependent[].address.state",
            "dependent[].address.zip"
        ]
    },
    "attorney": {
        "label": "⚖️ Attorney/Representative Information",
        "paths": [
            "attorneyLastName",
            "attorneyFirstName",
            "attorneyMiddleName",
            "attorneyWorkPhone",
            "attorneyMobilePhone",
            "attorneyEmailAddress",
            "attorneyStateBarNumber",
            "attorneyUscisOnlineAccount",
            "attorneyAddress.street",
            "attorneyAddress.city",
            "attorneyAddress.state",
            "attorneyAddress.zip",
            "lawFirmName",
            "lawFirmFein"
        ]
    },
    "application": {
        "label": "📋 Application/Case Information",
        "paths": [
            "caseNumber",
            "receiptNumber",
            "priorityDate",
            "filingDate",
            "approvalDate",
            "applicationType",
            "requestedStatus",
            "requestedClassification",
            "changeEffectiveDate",
            "previousReceiptNumber",
            "consulateLocation",
            "portOfEntry",
            "schoolName",
            "sevisId"
        ]
    },
    "custom": {
        "label": "✏️ Manual/Custom Fields",
        "paths": []
    }
}

# ===== FIELD OPTIONS EXTRACTION =====

def extract_field_options(label: str, text_context: str = "") -> List[str]:
    """Extract possible options for checkbox/select fields"""
    options = []
    label_lower = label.lower()
    
    # Common Yes/No fields
    if any(word in label_lower for word in ["yes/no", "yes or no", "check if", "are you", "do you", "have you", "will you"]):
        return ["Yes", "No"]
    
    # Gender fields
    if "gender" in label_lower or "sex" in label_lower:
        return ["Male", "Female", "Other"]
    
    # Marital status
    if "marital" in label_lower or "marriage" in label_lower:
        return ["Single", "Married", "Divorced", "Widowed", "Separated"]
    
    # Title fields
    if "title" in label_lower and ("mr" in label_lower or "ms" in label_lower):
        return ["Mr.", "Ms.", "Mrs.", "Dr.", "Prof."]
    
    # Try to extract options from context (like "Select one: A) Option1 B) Option2")
    if text_context:
        # Look for patterns like "□ Option1 □ Option2"
        checkbox_pattern = r'□\s*([^\□\n]+)'
        matches = re.findall(checkbox_pattern, text_context)
        if matches:
            options.extend([m.strip() for m in matches[:10]])  # Limit to 10 options
        
        # Look for patterns like "A. Option1 B. Option2"
        letter_pattern = r'[A-Z]\.\s*([^A-Z\n]+)'
        matches = re.findall(letter_pattern, text_context)
        if matches:
            options.extend([m.strip() for m in matches[:10]])
    
    return options

# ===== FIELD TYPE DETECTION =====

def detect_field_type(label: str, text_context: str = "") -> Tuple[str, List[str]]:
    """Detect field type and extract options if applicable"""
    label_lower = label.lower()
    options = []
    
    # Check for fields with options first
    if any(word in label_lower for word in ["check", "select", "mark", "yes/no", "indicate", "choose"]):
        options = extract_field_options(label, text_context)
        return ("checkbox" if options else "select"), options
    
    if any(word in label_lower for word in ["date", "dob", "birth", "expir", "issued"]):
        return "date", []
    elif any(word in label_lower for word in ["number", "ssn", "ein", "a-number", "receipt"]):
        return "number", []
    elif any(word in label_lower for word in ["email", "e-mail"]):
        return "email", []
    elif any(word in label_lower for word in ["phone", "telephone", "mobile", "cell"]):
        return "phone", []
    elif any(word in label_lower for word in ["address", "street", "city", "state", "zip"]):
        return "address", []
    
    return "text", []

def detect_subfield_components(label: str) -> List[str]:
    """Detect if a field should have subfields based on its label"""
    label_lower = label.lower()
    
    # Check for name fields
    if "name" in label_lower:
        if "full" in label_lower or "legal" in label_lower:
            return ["Family Name (Last Name)", "Given Name (First Name)", "Middle Name"]
        elif "company" in label_lower or "organization" in label_lower:
            return []  # Company names are single fields
    
    # Check for address fields
    if "address" in label_lower:
        if "mailing" in label_lower or "physical" in label_lower:
            return ["Street Number and Name", "Apt/Ste/Flr", "City or Town", "State", "ZIP Code"]
        elif "foreign" in label_lower:
            return ["Street Number and Name", "City or Town", "Province", "Postal Code", "Country"]
    
    return []

# ===== PDF EXTRACTION =====

def extract_pdf_text(pdf_file) -> Tuple[str, Dict[int, str], int]:
    """Extract text from PDF"""
    if not PYMUPDF_AVAILABLE:
        return "", {}, 0
    
    try:
        pdf_file.seek(0)
        doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
        
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
        st.error(f"PDF error: {e}")
        return "", {}, 0

# ===== UNIVERSAL FORM EXTRACTOR =====

class UniversalFormExtractor:
    """Extracts ANY USCIS form with proper subfield splitting and options"""
    
    def __init__(self):
        self.setup_openai()
    
    def setup_openai(self):
        """Setup OpenAI client"""
        api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        
        if api_key:
            self.client = openai.OpenAI(api_key=api_key)
        else:
            self.client = None
            st.warning("Add OPENAI_API_KEY to secrets")
    
    def extract_form(self, full_text: str, page_texts: Dict[int, str], total_pages: int) -> USCISForm:
        """Extract form with automatic subfield detection and options"""
        
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
        parts_data = self._extract_parts(full_text)
        
        # Extract fields for each part
        for part_data in parts_data:
            part = FormPart(
                number=part_data["number"],
                title=part_data["title"],
                page_start=part_data.get("page_start", 1),
                page_end=part_data.get("page_end", 1)
            )
            
            # Extract fields with subfield detection and options
            fields = self._extract_and_split_fields(full_text, part_data)
            part.fields = fields
            form.parts[part.number] = part
        
        return form
    
    def _identify_form(self, text: str) -> Dict:
        """Identify form type"""
        
        if not self.client:
            # Fallback
            form_match = re.search(r'Form\s+([A-Z]-?\d+[A-Z]?)', text)
            form_number = form_match.group(1) if form_match else "Unknown"
            
            return {
                "form_number": form_number,
                "form_title": "USCIS Form",
                "edition_date": ""
            }
        
        prompt = """
        Identify the form from this text.
        
        Return ONLY JSON:
        {
            "form_number": "form number",
            "form_title": "form title",
            "edition_date": "edition date"
        }
        
        Text: """ + text
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=200
            )
            
            content = response.choices[0].message.content.strip()
            if "```" in content:
                content = content.split("```")[1].replace("json", "").strip()
            
            return json.loads(content)
            
        except Exception as e:
            st.error(f"Identification error: {e}")
            return {"form_number": "Unknown", "form_title": "USCIS Form", "edition_date": ""}
    
    def _extract_parts(self, text: str) -> List[Dict]:
        """Extract parts from form"""
        
        if not self.client:
            parts = []
            part_matches = re.finditer(r'Part\s+(\d+)[.\s]+([^\n]+)', text)
            
            for match in part_matches:
                parts.append({
                    "number": int(match.group(1)),
                    "title": match.group(2).strip(),
                    "page_start": 1,
                    "page_end": 1
                })
            
            return parts if parts else [{"number": 1, "title": "Main Section", "page_start": 1, "page_end": 1}]
        
        prompt = """
        Extract ALL parts from this form.
        
        Return ONLY a JSON array:
        [
            {
                "number": 1,
                "title": "part title",
                "page_start": 1,
                "page_end": 2
            }
        ]
        
        Text: """ + text[:10000]
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=1500
            )
            
            content = response.choices[0].message.content.strip()
            if "```" in content:
                content = content.split("```")[1].replace("json", "").strip()
            
            parts = json.loads(content)
            return parts if parts else [{"number": 1, "title": "Main Section", "page_start": 1, "page_end": 1}]
            
        except Exception as e:
            st.error(f"Parts extraction error: {e}")
            return [{"number": 1, "title": "Main Section", "page_start": 1, "page_end": 1}]
    
    def _extract_and_split_fields(self, text: str, part_data: Dict) -> List[FormField]:
        """Extract fields and automatically split multi-component fields with options"""
        
        part_num = part_data["number"]
        part_title = part_data["title"]
        
        # First, get raw fields from AI or fallback
        raw_fields = self._extract_raw_fields(text, part_data)
        
        # Process and split fields that need subfields
        processed_fields = []
        
        for field_data in raw_fields:
            item_number = field_data.get("item_number", "")
            label = field_data.get("label", "")
            field_options = field_data.get("options", [])
            
            # Get context for option extraction
            context = self._get_field_context(text, item_number, label)
            
            # Detect field type and extract options
            field_type, detected_options = detect_field_type(label, context)
            
            # Merge options from AI and detection
            all_options = list(set(field_options + detected_options))
            
            # Check if this field should be split into subfields
            subfield_components = detect_subfield_components(label)
            
            if subfield_components:
                # This is a parent field with subfields
                parent_field = FormField(
                    item_number=item_number,
                    label=label,
                    field_type="parent",
                    part_number=part_num,
                    is_parent=True,
                    subfield_labels=subfield_components
                )
                processed_fields.append(parent_field)
                
                # Create subfields a, b, c, etc.
                letters = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j']
                for i, component in enumerate(subfield_components):
                    if i < len(letters):
                        subfield_type, sub_options = detect_field_type(component)
                        subfield = FormField(
                            item_number=f"{item_number}.{letters[i]}",
                            label=component,
                            field_type=subfield_type,
                            part_number=part_num,
                            parent_number=item_number,
                            is_subfield=True,
                            options=sub_options
                        )
                        processed_fields.append(subfield)
            
            else:
                # Regular field or already a subfield
                if re.match(r'^\d+\.[a-z]$', item_number):
                    # This is already a subfield (like 2.a)
                    parent_num = item_number.split('.')[0]
                    field = FormField(
                        item_number=item_number,
                        label=label,
                        field_type=field_type,
                        part_number=part_num,
                        parent_number=parent_num,
                        is_subfield=True,
                        options=all_options
                    )
                else:
                    # Regular field
                    field = FormField(
                        item_number=item_number,
                        label=label,
                        field_type=field_type,
                        part_number=part_num,
                        options=all_options
                    )
                processed_fields.append(field)
        
        return processed_fields
    
    def _get_field_context(self, text: str, item_number: str, label: str) -> str:
        """Get context around a field for option extraction"""
        try:
            # Find the field in text
            pattern = re.escape(item_number) + r'.*?' + re.escape(label[:20])
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            
            if match:
                start = max(0, match.start() - 50)
                end = min(len(text), match.end() + 300)
                return text[start:end]
        except:
            pass
        
        return ""
    
    def _extract_raw_fields(self, text: str, part_data: Dict) -> List[Dict]:
        """Extract raw fields from text with options"""
        
        part_num = part_data["number"]
        part_title = part_data["title"]
        
        if not self.client:
            # Fallback to regex
            fields = []
            field_matches = re.finditer(r'(\d+\.?[a-z]?\.?)\s+([^\n]+)', text[:5000])
            
            for match in field_matches:
                label = match.group(2).strip()[:100]
                context = self._get_field_context(text, match.group(1), label)
                _, options = detect_field_type(label, context)
                
                fields.append({
                    "item_number": match.group(1),
                    "label": label,
                    "options": options
                })
            
            return fields[:50]
        
        prompt = f"""
        Extract ALL fields from Part {part_num}: {part_title}.
        
        Important: 
        - Include the main field labels
        - If you see subfields already labeled (1.a, 1.b), include those too
        - For checkbox/select fields, try to identify the options
        
        Return ONLY a JSON array:
        [
            {{
                "item_number": "field number",
                "label": "field label",
                "options": ["option1", "option2"] or []
            }}
        ]
        
        Text: """ + text[:15000]
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=4000
            )
            
            content = response.choices[0].message.content.strip()
            if "```" in content:
                content = content.split("```")[1].replace("json", "").strip()
            
            fields = json.loads(content)
            return fields if fields else []
            
        except Exception as e:
            st.error(f"Field extraction error: {e}")
            return []

# ===== UI COMPONENTS =====

def display_field(field: FormField, key_prefix: str):
    """Display field with proper parent/child visualization and options"""
    
    unique_key = f"{key_prefix}_{field.unique_id}"
    
    # Determine style
    card_class = ""
    if field.is_parent:
        card_class = "parent-field"
        status = "📁 Parent"
    elif field.is_subfield:
        card_class = "field-subfield"
        status = f"↳ Sub of {field.parent_number}"
    elif field.in_questionnaire:
        card_class = "field-questionnaire"
        status = "📝 Quest"
    elif field.is_mapped:
        card_class = "field-mapped"
        status = f"✅ {field.db_object}"
    else:
        card_class = "field-unmapped"
        status = "❓ Unmapped"
    
    st.markdown(f'<div class="field-card {card_class}">', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([3, 2, 2])
    
    with col1:
        # Show field number prominently
        if field.is_parent:
            st.markdown(f'<span class="field-number-badge">{field.item_number}</span>**{field.label}** (Parent Field)', unsafe_allow_html=True)
            if field.subfield_labels:
                st.caption(f"Has subfields: {', '.join(field.subfield_labels)}")
        elif field.is_subfield:
            st.markdown(f'&nbsp;&nbsp;&nbsp;↳ <span class="field-number-badge">{field.item_number}</span>**{field.label}**', unsafe_allow_html=True)
        else:
            st.markdown(f'<span class="field-number-badge">{field.item_number}</span>**{field.label}**', unsafe_allow_html=True)
        
        # Show options if available
        if field.has_options and field.options:
            options_html = ''.join([f'<span class="option-chip">{opt}</span>' for opt in field.options])
            st.markdown(f'<div style="margin-top: 5px;">Options: {options_html}</div>', unsafe_allow_html=True)
    
    with col2:
        # Only show value input for non-parent fields
        if not field.is_parent:
            if field.field_type == "date":
                date_val = st.date_input("", key=f"{unique_key}_date", label_visibility="collapsed")
                field.value = str(date_val) if date_val else ""
            elif field.field_type == "checkbox" and field.options:
                field.value = st.selectbox("", [""] + field.options, key=f"{unique_key}_check", label_visibility="collapsed")
            elif field.field_type == "select" and field.options:
                field.value = st.selectbox("", [""] + field.options, key=f"{unique_key}_select", label_visibility="collapsed")
            else:
                field.value = st.text_input("", value=field.value, key=f"{unique_key}_val", label_visibility="collapsed")
        else:
            st.info("Parent field - enter values in subfields")
    
    with col3:
        st.markdown(f"**{status}**")
        
        # Only show mapping buttons for non-parent fields
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
                elif field.is_mapped or field.in_questionnaire:
                    if st.button("Clear", key=f"{unique_key}_clear"):
                        field.is_mapped = False
                        field.in_questionnaire = False
                        field.db_object = ""
                        field.db_path = ""
                        st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Mapping interface
    if st.session_state.get(f"mapping_{field.unique_id}"):
        show_mapping(field, unique_key)

def show_mapping(field: FormField, unique_key: str):
    """Mapping interface"""
    
    st.markdown("---")
    st.markdown("### 🔗 Map Field to Database")
    
    col1, col2 = st.columns(2)
    
    with col1:
        db_options = list(DATABASE_SCHEMA.keys())
        db_labels = [DATABASE_SCHEMA[k]["label"] for k in db_options]
        
        selected_idx = st.selectbox(
            "Database Object",
            range(len(db_options)),
            format_func=lambda x: db_labels[x],
            key=f"{unique_key}_dbobj",
            index=None,
            placeholder="Select database object..."
        )
        
        selected_obj = db_options[selected_idx] if selected_idx is not None else None
    
    with col2:
        if selected_obj:
            if selected_obj == "custom":
                path = st.text_input("Custom path", key=f"{unique_key}_custom", placeholder="Enter custom path")
            else:
                paths = DATABASE_SCHEMA[selected_obj]["paths"]
                path = st.selectbox(
                    "Field Path",
                    [""] + paths + ["[custom]"],
                    key=f"{unique_key}_path",
                    placeholder="Select field path..."
                )
                
                if path == "[custom]":
                    path = st.text_input("Enter custom path", key=f"{unique_key}_custpath")
    
    if selected_obj and path:
        st.info(f"📍 Mapping: {field.item_number} → {selected_obj}.{path}")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Apply", key=f"{unique_key}_apply", type="primary"):
            if selected_obj and path:
                field.is_mapped = True
                field.db_object = selected_obj
                field.db_path = path
                del st.session_state[f"mapping_{field.unique_id}"]
                st.success("Mapped successfully!")
                st.rerun()
    
    with col2:
        if st.button("Cancel", key=f"{unique_key}_cancel"):
            del st.session_state[f"mapping_{field.unique_id}"]
            st.rerun()
    
    st.markdown("---")

# ===== EXPORT FUNCTIONS =====

def generate_typescript_interface(form: USCISForm) -> str:
    """Generate TypeScript interface for mapped fields"""
    
    ts_code = "// Generated TypeScript Interface from USCIS Form\n\n"
    
    # Group by database object
    mapped_by_object = {}
    
    for part in form.parts.values():
        for field in part.fields:
            if field.is_mapped and not field.is_parent:
                if field.db_object not in mapped_by_object:
                    mapped_by_object[field.db_object] = []
                mapped_by_object[field.db_object].append(field)
    
    # Generate interfaces
    for obj_name, fields in mapped_by_object.items():
        interface_name = obj_name.capitalize() + "Data"
        ts_code += f"interface {interface_name} {{\n"
        
        # Track unique paths
        added_paths = set()
        
        for field in fields:
            path = field.db_path
            
            # Skip if already added
            if path in added_paths:
                continue
            added_paths.add(path)
            
            # Determine TypeScript type
            ts_type = "string"
            if field.field_type == "date":
                ts_type = "Date | string"
            elif field.field_type == "number":
                ts_type = "number | string"
            elif field.field_type == "checkbox" or field.field_type == "select":
                if field.options:
                    ts_type = " | ".join([f'"{opt}"' for opt in field.options]) + " | null"
                else:
                    ts_type = "boolean | string"
            
            # Handle nested paths
            if "." in path:
                # For now, just use the last part
                path_parts = path.split(".")
                field_name = path_parts[-1]
            else:
                field_name = path
            
            # Add comment with original field
            ts_code += f"  // Field {field.item_number}: {field.label}\n"
            ts_code += f"  {field_name}?: {ts_type};\n"
        
        ts_code += "}\n\n"
    
    # Generate main form data interface
    ts_code += "interface FormData {\n"
    for obj_name in mapped_by_object.keys():
        interface_name = obj_name.capitalize() + "Data"
        ts_code += f"  {obj_name}: {interface_name};\n"
    ts_code += "}\n\n"
    
    # Generate populated data
    ts_code += "// Populated form data\n"
    ts_code += "const formData: FormData = {\n"
    
    for obj_name, fields in mapped_by_object.items():
        ts_code += f"  {obj_name}: {{\n"
        
        added_paths = set()
        for field in fields:
            if field.value and field.db_path not in added_paths:
                added_paths.add(field.db_path)
                
                path = field.db_path
                if "." in path:
                    path_parts = path.split(".")
                    field_name = path_parts[-1]
                else:
                    field_name = path
                
                # Format value based on type
                if field.field_type == "number":
                    value_str = field.value
                else:
                    value_str = f'"{field.value}"'
                
                ts_code += f"    {field_name}: {value_str}, // {field.item_number}\n"
        
        ts_code += "  },\n"
    
    ts_code += "};\n"
    
    return ts_code

def generate_questionnaire_json(form: USCISForm) -> Dict:
    """Generate JSON for questionnaire fields by part"""
    
    questionnaire = {
        "form_info": {
            "form_number": form.form_number,
            "form_title": form.form_title,
            "edition_date": form.edition_date
        },
        "parts": {}
    }
    
    for part in form.parts.values():
        quest_fields = [f for f in part.fields if f.in_questionnaire and not f.is_parent]
        
        if quest_fields:
            part_data = {
                "title": part.title,
                "questions": []
            }
            
            for field in quest_fields:
                question = {
                    "field_number": field.item_number,
                    "question": field.label,
                    "type": field.field_type,
                    "answer": field.value,
                    "is_subfield": field.is_subfield
                }
                
                # Add options if available
                if field.options:
                    question["options"] = field.options
                
                # Add parent reference if subfield
                if field.is_subfield:
                    question["parent_field"] = field.parent_number
                
                part_data["questions"].append(question)
            
            questionnaire["parts"][f"Part_{part.number}"] = part_data
    
    return questionnaire

# ===== MAIN APPLICATION =====

def main():
    st.markdown('<div class="main-header">', unsafe_allow_html=True)
    st.title("📄 Universal USCIS Form Reader")
    st.markdown("Extract fields with options • Map to TypeScript • Export questionnaires")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Initialize
    if 'form' not in st.session_state:
        st.session_state.form = None
    if 'extractor' not in st.session_state:
        st.session_state.extractor = UniversalFormExtractor()
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 📊 Database Schema")
        
        for key, info in DATABASE_SCHEMA.items():
            with st.expander(info["label"]):
                if key == "custom":
                    st.info("Enter any custom path")
                else:
                    paths = info["paths"]
                    st.info(f"{len(paths)} paths available")
                    for path in paths[:5]:
                        st.code(path)
                    if len(paths) > 5:
                        st.caption(f"... +{len(paths)-5} more")
        
        st.markdown("---")
        
        if st.button("🔄 Clear All", type="secondary", use_container_width=True):
            st.session_state.form = None
            for key in list(st.session_state.keys()):
                if key.startswith("mapping_"):
                    del st.session_state[key]
            st.rerun()
        
        if st.session_state.form:
            st.markdown("## 📈 Statistics")
            form = st.session_state.form
            
            # Count fields
            total_fields = 0
            parent_fields = 0
            subfields = 0
            mapped = 0
            quest = 0
            with_options = 0
            
            for part in form.parts.values():
                for field in part.fields:
                    total_fields += 1
                    if field.is_parent:
                        parent_fields += 1
                    elif field.is_subfield:
                        subfields += 1
                    if field.is_mapped:
                        mapped += 1
                    if field.in_questionnaire:
                        quest += 1
                    if field.has_options:
                        with_options += 1
            
            st.metric("Total Fields", total_fields)
            st.metric("Parent Fields", parent_fields)
            st.metric("Subfields", subfields)
            st.metric("Mapped", mapped)
            st.metric("Questionnaire", quest)
            st.metric("With Options", with_options)
    
    # Main tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📤 Upload", "🔗 Map Fields", "📝 Questionnaire", "💾 Export"])
    
    with tab1:
        st.markdown("### Upload USCIS Form")
        st.info("Extracts fields with multiple choice options and automatically splits complex fields")
        
        uploaded_file = st.file_uploader("Choose PDF file", type=['pdf'])
        
        if uploaded_file:
            if st.button("🚀 Extract Form", type="primary", use_container_width=True):
                with st.spinner("Extracting fields and options..."):
                    # Extract PDF
                    full_text, page_texts, total_pages = extract_pdf_text(uploaded_file)
                    
                    if full_text:
                        # Extract form with subfield splitting and options
                        form = st.session_state.extractor.extract_form(
                            full_text, page_texts, total_pages
                        )
                        
                        st.session_state.form = form
                        
                        # Show results
                        st.success(f"✅ Extracted: {form.form_number}")
                        
                        # Statistics
                        total_fields = sum(len(p.fields) for p in form.parts.values())
                        parent_count = sum(1 for p in form.parts.values() for f in p.fields if f.is_parent)
                        subfield_count = sum(1 for p in form.parts.values() for f in p.fields if f.is_subfield)
                        options_count = sum(1 for p in form.parts.values() for f in p.fields if f.has_options)
                        
                        col1, col2, col3, col4, col5 = st.columns(5)
                        with col1:
                            st.metric("Parts", len(form.parts))
                        with col2:
                            st.metric("Total Fields", total_fields)
                        with col3:
                            st.metric("Parent Fields", parent_count)
                        with col4:
                            st.metric("Subfields", subfield_count)
                        with col5:
                            st.metric("With Options", options_count)
                        
                        if parent_count > 0:
                            st.info(f"✨ Split {parent_count} fields into {subfield_count} subfields")
                        if options_count > 0:
                            st.info(f"🎯 Found {options_count} fields with multiple choice options")
                    else:
                        st.error("Could not extract text")
    
    with tab2:
        st.markdown("### Map Fields to Database")
        st.info("Map fields to database objects or move to questionnaire. Field numbers and options are shown.")
        
        if st.session_state.form:
            form = st.session_state.form
            
            for part_num, part in form.parts.items():
                with st.expander(f"Part {part_num}: {part.title}", expanded=(part_num == 1)):
                    
                    # Statistics
                    regular = sum(1 for f in part.fields if not f.is_parent and not f.is_subfield)
                    parents = sum(1 for f in part.fields if f.is_parent)
                    subs = sum(1 for f in part.fields if f.is_subfield)
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Regular Fields", regular)
                    with col2:
                        st.metric("Parent Fields", parents)
                    with col3:
                        st.metric("Subfields", subs)
                    
                    st.markdown("---")
                    
                    # Display fields with proper hierarchy
                    displayed_subfields = set()
                    
                    for field in part.fields:
                        # Skip already displayed subfields
                        if field.item_number in displayed_subfields:
                            continue
                        
                        # Display field
                        display_field(field, f"p{part_num}")
                        
                        # If it's a parent, immediately show its subfields
                        if field.is_parent:
                            for subfield in part.fields:
                                if subfield.parent_number == field.item_number:
                                    display_field(subfield, f"p{part_num}")
                                    displayed_subfields.add(subfield.item_number)
        else:
            st.info("Upload a form first")
    
    with tab3:
        st.markdown("### Questionnaire Fields")
        st.info("Answer questions moved to questionnaire. Field numbers and available options are shown.")
        
        if st.session_state.form:
            # Group by part
            parts_with_questions = {}
            
            for part in st.session_state.form.parts.values():
                quest_fields = [f for f in part.fields if f.in_questionnaire and not f.is_parent]
                if quest_fields:
                    parts_with_questions[part.number] = {
                        "title": part.title,
                        "fields": quest_fields
                    }
            
            if parts_with_questions:
                for part_num, part_info in parts_with_questions.items():
                    st.markdown(f"#### Part {part_num}: {part_info['title']}")
                    
                    for field in part_info["fields"]:
                        st.markdown(f'<span class="field-number-badge">{field.item_number}</span>**{field.label}**', unsafe_allow_html=True)
                        
                        if field.is_subfield:
                            st.caption(f"Subfield of {field.parent_number}")
                        
                        # Show options if available
                        if field.has_options and field.options:
                            col1, col2 = st.columns([3, 1])
                            with col1:
                                # If field has options, show as select
                                field.value = st.selectbox(
                                    "Select answer",
                                    [""] + field.options,
                                    index=0 if not field.value else (field.options.index(field.value) + 1 if field.value in field.options else 0),
                                    key=f"q_select_{field.unique_id}"
                                )
                            with col2:
                                st.markdown("Available options:")
                                for opt in field.options:
                                    st.caption(f"• {opt}")
                        else:
                            # Regular text input
                            field.value = st.text_area(
                                "Answer", 
                                value=field.value, 
                                key=f"q_{field.unique_id}", 
                                height=100
                            )
                        
                        if st.button("Remove from questionnaire", key=f"qr_{field.unique_id}"):
                            field.in_questionnaire = False
                            st.rerun()
                        
                        st.markdown("---")
            else:
                st.info("No questionnaire fields. Use the 'Quest' button in Map Fields tab to add fields.")
        else:
            st.info("Upload a form first")
    
    with tab4:
        st.markdown("### Export Data")
        st.info("Mapped fields export as TypeScript interfaces. Questionnaire exports as JSON.")
        
        if st.session_state.form:
            form = st.session_state.form
            
            # Statistics
            mapped_count = sum(1 for p in form.parts.values() for f in p.fields if f.is_mapped and not f.is_parent)
            quest_count = sum(1 for p in form.parts.values() for f in p.fields if f.in_questionnaire and not f.is_parent)
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Mapped Fields (TypeScript)", mapped_count)
            with col2:
                st.metric("Questionnaire Fields (JSON)", quest_count)
            
            st.markdown("---")
            
            # Generate TypeScript for mapped fields
            if mapped_count > 0:
                st.markdown("#### 📘 TypeScript Interface (Mapped Fields)")
                ts_code = generate_typescript_interface(form)
                
                st.download_button(
                    "📥 Download TypeScript",
                    ts_code,
                    f"{form.form_number}_interface.ts",
                    "text/plain",
                    use_container_width=True
                )
                
                with st.expander("Preview TypeScript"):
                    st.code(ts_code, language="typescript")
            
            # Generate JSON for questionnaire
            if quest_count > 0:
                st.markdown("#### 📋 Questionnaire JSON")
                quest_json = generate_questionnaire_json(form)
                
                json_str = json.dumps(quest_json, indent=2)
                
                st.download_button(
                    "📥 Download Questionnaire JSON",
                    json_str,
                    f"{form.form_number}_questionnaire.json",
                    "application/json",
                    use_container_width=True
                )
                
                with st.expander("Preview Questionnaire JSON"):
                    st.json(quest_json)
            
            # Complete export with everything
            st.markdown("#### 📦 Complete Export")
            
            complete_export = {
                "form_info": {
                    "form_number": form.form_number,
                    "form_title": form.form_title,
                    "edition_date": form.edition_date,
                    "total_pages": form.total_pages
                },
                "typescript_interface": generate_typescript_interface(form) if mapped_count > 0 else None,
                "questionnaire": generate_questionnaire_json(form) if quest_count > 0 else None,
                "all_fields": []
            }
            
            # Add all fields data
            for part in form.parts.values():
                for field in part.fields:
                    field_data = {
                        "part": part.number,
                        "item_number": field.item_number,
                        "label": field.label,
                        "value": field.value,
                        "type": field.field_type,
                        "is_parent": field.is_parent,
                        "is_subfield": field.is_subfield,
                        "options": field.options if field.options else None,
                        "status": "mapped" if field.is_mapped else "questionnaire" if field.in_questionnaire else "unmapped"
                    }
                    
                    if field.is_mapped:
                        field_data["mapping"] = f"{field.db_object}.{field.db_path}"
                    
                    complete_export["all_fields"].append(field_data)
            
            complete_json = json.dumps(complete_export, indent=2)
            
            st.download_button(
                "📥 Download Complete Export",
                complete_json,
                f"{form.form_number}_complete.json",
                "application/json",
                use_container_width=True,
                type="primary"
            )
            
            if not mapped_count and not quest_count:
                st.warning("No fields have been mapped or added to questionnaire yet.")
        else:
            st.info("No data to export. Upload a form first.")

if __name__ == "__main__":
    main()
