#!/usr/bin/env python3
"""
UNIVERSAL USCIS FORM READER - WITH COMPLETE DATABASE SCHEMA
============================================================
Works with ANY USCIS form - Complete database paths included
"""

import streamlit as st
import json
import re
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
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
    .field-manual {
        border-left: 4px solid #9c27b0;
        background: #f3e5f5;
    }
    .stats-box {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# ===== DATA STRUCTURES =====

@dataclass
class FormField:
    """Universal field structure"""
    item_number: str
    label: str
    field_type: str = "text"
    value: str = ""
    part_number: int = 1
    page_number: int = 1
    parent_item: str = ""
    is_subfield: bool = False
    is_mapped: bool = False
    in_questionnaire: bool = False
    is_manual: bool = False
    db_object: str = ""
    db_path: str = ""
    unique_id: str = ""
    
    def __post_init__(self):
        if not self.unique_id:
            self.unique_id = str(uuid.uuid4())[:8]

@dataclass
class FormPart:
    """Generic part structure"""
    number: int
    title: str
    fields: List[FormField] = field(default_factory=list)
    page_start: int = 1
    page_end: int = 1

@dataclass
class USCISForm:
    """Universal form container"""
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
            "businessType",
            "irsNumber",
            "immigrationStatus",
            "certificateNumber"
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
            "dependent[].passportCountry",
            "dependent[].passportExpiration",
            "dependent[].relationship",
            "dependent[].daytimePhone",
            "dependent[].mobilePhone",
            "dependent[].emailAddress",
            "dependent[].address.street",
            "dependent[].address.city",
            "dependent[].address.state",
            "dependent[].address.zip",
            "dependent[].currentStatus",
            "dependent[].statusExpiration",
            "spouseName",
            "spouseDateOfBirth",
            "childrenNames[]",
            "childrenDatesOfBirth[]"
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
            "attorneyAddress.country",
            "lawFirmName",
            "lawFirmFein",
            "preparerLastName",
            "preparerFirstName",
            "preparerOrganization",
            "preparerDaytimePhone",
            "preparerEmailAddress",
            "interpreterLastName",
            "interpreterFirstName",
            "interpreterOrganization",
            "interpreterDaytimePhone",
            "interpreterLanguage"
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
            "requestedDuration",
            "changeEffectiveDate",
            "previousApplicationNumber",
            "previousReceiptNumber",
            "consulateLocation",
            "portOfEntry",
            "reasonForRequest",
            "basisForEligibility",
            "requestedAction",
            "processingLocation",
            "schoolName",
            "programStartDate",
            "programEndDate",
            "degreeType",
            "fieldOfStudy",
            "jobTitle",
            "socCode",
            "wageRate",
            "wagePeriod"
        ]
    },
    "travel": {
        "label": "✈️ Travel Information",
        "paths": [
            "lastEntryDate",
            "lastEntryPlace",
            "lastEntryStatus",
            "i94ArrivalNumber",
            "i94DepartureNumber",
            "travelDocumentNumber",
            "travelDocumentCountry",
            "travelDocumentExpiration",
            "intendedDepartureDate",
            "intendedReturnDate",
            "tripsAbroad[].departureDate",
            "tripsAbroad[].returnDate",
            "tripsAbroad[].destination",
            "tripsAbroad[].purpose",
            "visaNumber",
            "visaIssuanceDate",
            "visaExpirationDate",
            "consulateOfIssuance"
        ]
    },
    "biographic": {
        "label": "📝 Biographic Information",
        "paths": [
            "ethnicity",
            "race",
            "height.feet",
            "height.inches",
            "weight.pounds",
            "eyeColor",
            "hairColor",
            "gender",
            "maritalStatus",
            "previousMarriages",
            "dateOfMarriage",
            "placeOfMarriage",
            "spouseImmigrationStatus",
            "motherName",
            "fatherName",
            "mothersDateOfBirth",
            "fathersDateOfBirth",
            "countryOfNationality",
            "countryOfLastResidence",
            "nationalIdNumber",
            "taxIdNumber"
        ]
    },
    "employment": {
        "label": "💼 Employment Information",
        "paths": [
            "currentEmployer",
            "employerAddress",
            "employerPhone",
            "jobTitle",
            "employmentStartDate",
            "employmentEndDate",
            "previousEmployer[].name",
            "previousEmployer[].address",
            "previousEmployer[].jobTitle",
            "previousEmployer[].startDate",
            "previousEmployer[].endDate",
            "occupation",
            "yearsInOccupation",
            "qualifications",
            "education.degree",
            "education.fieldOfStudy",
            "education.institution",
            "education.dateCompleted",
            "licenseNumber",
            "licenseState",
            "licenseExpiration"
        ]
    },
    "custom": {
        "label": "✏️ Manual/Custom Fields",
        "paths": []
    }
}

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

# ===== FIELD TYPE DETECTOR =====

def detect_field_type(label: str) -> str:
    """Detect field type from label"""
    label_lower = label.lower()
    
    if any(word in label_lower for word in ["date", "dob", "birth", "expir", "issued"]):
        return "date"
    elif any(word in label_lower for word in ["check", "select", "mark", "yes/no", "indicate"]):
        return "checkbox"
    elif any(word in label_lower for word in ["number", "ssn", "ein", "a-number", "receipt"]):
        return "number"
    elif any(word in label_lower for word in ["email", "e-mail"]):
        return "email"
    elif any(word in label_lower for word in ["phone", "telephone", "mobile", "cell"]):
        return "phone"
    elif any(word in label_lower for word in ["address", "street", "city", "state", "zip"]):
        return "address"
    
    return "text"

# ===== UNIVERSAL FORM EXTRACTOR =====

class UniversalFormExtractor:
    """Extracts ANY USCIS form"""
    
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
        """Extract any form structure"""
        
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
            
            # Extract fields
            fields_data = self._extract_fields(full_text, part_data)
            
            # Convert to FormField objects
            fields = []
            for field_data in fields_data:
                # Detect parent-child relationships
                item_num = field_data.get("item_number", "")
                parent_item = ""
                is_subfield = False
                
                # Check if it's a subfield (e.g., 1.a, 1.b)
                if re.match(r'^\d+\.[a-z]$', item_num):
                    parent_item = item_num.split('.')[0]
                    is_subfield = True
                
                field = FormField(
                    item_number=item_num,
                    label=field_data.get("label", ""),
                    field_type=detect_field_type(field_data.get("label", "")),
                    part_number=part.number,
                    parent_item=parent_item,
                    is_subfield=is_subfield
                )
                fields.append(field)
            
            part.fields = fields
            form.parts[part.number] = part
        
        return form
    
    def _identify_form(self, text: str) -> Dict:
        """Identify form type"""
        
        if not self.client:
            # Fallback pattern matching
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
            # Fallback
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
    
    def _extract_fields(self, text: str, part_data: Dict) -> List[Dict]:
        """Extract fields from part"""
        
        part_num = part_data["number"]
        part_title = part_data["title"]
        
        if not self.client:
            # Fallback
            fields = []
            field_matches = re.finditer(r'(\d+\.?[a-z]?\.?)\s+([^\n]+)', text[:5000])
            
            for match in field_matches:
                fields.append({
                    "item_number": match.group(1),
                    "label": match.group(2).strip()[:100]
                })
            
            return fields[:50]
        
        prompt = f"""
        Extract ALL fields from Part {part_num}: {part_title}.
        
        Return ONLY a JSON array:
        [
            {{
                "item_number": "field number",
                "label": "field label"
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
    """Display field with mapping interface"""
    
    unique_key = f"{key_prefix}_{field.unique_id}"
    
    # Determine style
    if field.is_manual:
        card_class = "field-manual"
        status = "✏️ Manual"
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
        if field.is_subfield:
            st.markdown(f"↳ **{field.item_number}. {field.label}**")
            st.caption(f"Subfield of {field.parent_item}")
        else:
            st.markdown(f"**{field.item_number}. {field.label}**")
    
    with col2:
        # Value input based on type
        if field.field_type == "date":
            date_val = st.date_input("", key=f"{unique_key}_date", label_visibility="collapsed")
            field.value = str(date_val) if date_val else ""
        elif field.field_type == "checkbox":
            field.value = st.selectbox("", ["", "Yes", "No"], key=f"{unique_key}_check", label_visibility="collapsed")
        else:
            field.value = st.text_input("", value=field.value, key=f"{unique_key}_val", label_visibility="collapsed")
    
    with col3:
        st.markdown(f"**{status}**")
        
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
                    field.is_manual = False
                    field.db_object = ""
                    field.db_path = ""
                    st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Mapping interface
    if st.session_state.get(f"mapping_{field.unique_id}"):
        show_mapping(field, unique_key)

def show_mapping(field: FormField, unique_key: str):
    """Mapping interface with full database schema"""
    
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
                field.is_manual = (selected_obj == "custom")
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

# ===== MAIN APPLICATION =====

def main():
    st.markdown('<div class="main-header">', unsafe_allow_html=True)
    st.title("📄 Universal USCIS Form Reader")
    st.markdown("Works with ANY USCIS form - Complete database schema included")
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
                    st.info("Enter any custom path for fields not covered by other objects")
                else:
                    paths = info["paths"]
                    st.info(f"{len(paths)} predefined paths available")
                    for path in paths[:8]:
                        st.code(path)
                    if len(paths) > 8:
                        st.caption(f"... and {len(paths)-8} more paths")
        
        st.markdown("---")
        
        if st.button("🔄 Clear All", type="secondary", use_container_width=True):
            st.session_state.form = None
            for key in list(st.session_state.keys()):
                if key.startswith("mapping_"):
                    del st.session_state[key]
            st.rerun()
        
        if st.session_state.form:
            st.markdown("## 📈 Form Statistics")
            form = st.session_state.form
            
            st.markdown('<div class="stats-box">', unsafe_allow_html=True)
            st.metric("Form", form.form_number)
            st.metric("Pages", form.total_pages)
            st.metric("Parts", len(form.parts))
            
            total_fields = sum(len(p.fields) for p in form.parts.values())
            mapped = sum(1 for p in form.parts.values() for f in p.fields if f.is_mapped)
            quest = sum(1 for p in form.parts.values() for f in p.fields if f.in_questionnaire)
            
            st.metric("Total Fields", total_fields)
            st.metric("Mapped", mapped)
            st.metric("Questionnaire", quest)
            st.metric("Unmapped", total_fields - mapped - quest)
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    # Main tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📤 Upload", "🔗 Map Fields", "📝 Questionnaire", "💾 Export"])
    
    with tab1:
        st.markdown("### Upload ANY USCIS Form")
        st.info("This reader works with all USCIS forms without any hardcoding")
        
        uploaded_file = st.file_uploader("Choose PDF file", type=['pdf'])
        
        if uploaded_file:
            if st.button("🚀 Extract Form", type="primary", use_container_width=True):
                with st.spinner("Extracting form structure..."):
                    # Extract PDF
                    full_text, page_texts, total_pages = extract_pdf_text(uploaded_file)
                    
                    if full_text:
                        # Extract form
                        form = st.session_state.extractor.extract_form(
                            full_text, page_texts, total_pages
                        )
                        
                        st.session_state.form = form
                        
                        # Show results
                        st.success(f"✅ Successfully extracted: {form.form_number}")
                        
                        # Statistics
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Parts Found", len(form.parts))
                        with col2:
                            total_fields = sum(len(p.fields) for p in form.parts.values())
                            st.metric("Fields Found", total_fields)
                        with col3:
                            st.metric("Pages", total_pages)
                    else:
                        st.error("Could not extract text from PDF")
    
    with tab2:
        st.markdown("### Map Fields to Database")
        st.info("Select the appropriate database object and path for each field")
        
        if st.session_state.form:
            form = st.session_state.form
            
            for part_num, part in form.parts.items():
                with st.expander(f"Part {part_num}: {part.title}", expanded=(part_num == 1)):
                    
                    # Part statistics
                    part_fields = len(part.fields)
                    part_mapped = sum(1 for f in part.fields if f.is_mapped)
                    part_quest = sum(1 for f in part.fields if f.in_questionnaire)
                    
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Fields", part_fields)
                    with col2:
                        st.metric("Mapped", part_mapped)
                    with col3:
                        st.metric("Quest", part_quest)
                    with col4:
                        st.metric("Unmapped", part_fields - part_mapped - part_quest)
                    
                    st.markdown("---")
                    
                    # Display fields
                    for field in part.fields:
                        display_field(field, f"p{part_num}")
        else:
            st.info("Upload a form first to begin mapping")
    
    with tab3:
        st.markdown("### Questionnaire Fields")
        st.info("Fields that need manual completion")
        
        if st.session_state.form:
            quest_fields = []
            for part in st.session_state.form.parts.values():
                quest_fields.extend([f for f in part.fields if f.in_questionnaire])
            
            if quest_fields:
                for field in quest_fields:
                    st.markdown(f"**{field.item_number}. {field.label}**")
                    st.caption(f"From Part {field.part_number}")
                    
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
                st.info("No questionnaire fields. Use 'Quest' button to add fields here.")
        else:
            st.info("Upload a form first")
    
    with tab4:
        st.markdown("### Export Data")
        
        if st.session_state.form:
            form = st.session_state.form
            
            # Build export
            export_data = {
                "form_info": {
                    "form_number": form.form_number,
                    "form_title": form.form_title,
                    "edition_date": form.edition_date,
                    "total_pages": form.total_pages,
                    "export_date": datetime.now().isoformat()
                },
                "database_objects": list(DATABASE_SCHEMA.keys()),
                "parts": [],
                "mapped_fields": [],
                "questionnaire_fields": [],
                "all_fields": []
            }
            
            for part in form.parts.values():
                part_data = {
                    "number": part.number,
                    "title": part.title,
                    "fields": []
                }
                
                for field in part.fields:
                    field_data = {
                        "item_number": field.item_number,
                        "label": field.label,
                        "value": field.value,
                        "type": field.field_type,
                        "part": part.number,
                        "is_subfield": field.is_subfield,
                        "parent_item": field.parent_item
                    }
                    
                    if field.is_mapped:
                        field_data["database_object"] = field.db_object
                        field_data["database_path"] = field.db_path
                        field_data["is_manual"] = field.is_manual
                        export_data["mapped_fields"].append(field_data)
                    elif field.in_questionnaire:
                        export_data["questionnaire_fields"].append(field_data)
                    
                    part_data["fields"].append(field_data)
                    export_data["all_fields"].append(field_data)
                
                export_data["parts"].append(part_data)
            
            # Summary
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Fields", len(export_data["all_fields"]))
            with col2:
                st.metric("Mapped", len(export_data["mapped_fields"]))
            with col3:
                st.metric("Questionnaire", len(export_data["questionnaire_fields"]))
            
            # Download
            json_str = json.dumps(export_data, indent=2)
            
            st.download_button(
                "📥 Download Complete JSON",
                json_str,
                f"{form.form_number}_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                "application/json",
                use_container_width=True
            )
            
            # Preview
            with st.expander("Preview Export"):
                st.json(export_data)
        else:
            st.info("No data to export")

if __name__ == "__main__":
    main()
