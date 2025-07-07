import streamlit as st
import json
import re
import fitz  # PyMuPDF
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, OrderedDict
import openai
from abc import ABC, abstractmethod
import time

# Configure page
st.set_page_config(
    page_title="USCIS Form Extractor - AI Agents",
    page_icon="🤖",
    layout="wide"
)

# CSS styling
st.markdown("""
<style>
    .agent-status {
        background: #f0f7ff;
        border-left: 4px solid #2196F3;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 4px;
    }
    .field-card {
        background: white;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        transition: all 0.2s;
    }
    .field-card:hover {
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    .mapped { border-left: 4px solid #4CAF50; }
    .questionnaire { border-left: 4px solid #FFC107; }
    .unmapped { border-left: 4px solid #f44336; }
    .part-header {
        background: linear-gradient(135deg, #2196F3, #1976D2);
        color: white;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    .field-info {
        font-size: 0.9rem;
        color: #666;
        margin-top: 0.5rem;
    }
    .item-number {
        font-weight: bold;
        color: #1976D2;
        margin-right: 0.5rem;
    }
    .part-selector {
        background: white;
        padding: 1.5rem;
        border-radius: 8px;
        border: 1px solid #ddd;
        margin-bottom: 1.5rem;
    }
</style>
""", unsafe_allow_html=True)

# Database structure for mapping
DB_STRUCTURE = {
    "beneficiary": {
        "Beneficiary": ["beneficiaryFirstName", "beneficiaryLastName", "beneficiaryMiddleName", 
                       "beneficiaryDateOfBirth", "beneficiaryGender", "beneficiarySsn",
                       "alienNumber", "uscisOnlineAccountNumber"],
        "MailingAddress": ["addressStreet", "addressCity", "addressState", "addressZip", 
                          "addressCountry", "addressAptSteFlrNumber", "addressNumber", "addressType"],
        "ContactInfo": ["daytimeTelephoneNumber", "mobileTelephoneNumber", "emailAddress"]
    },
    "customer": {
        "": ["customer_name", "customer_tax_id"],
        "SignatoryInfo": ["signatory_first_name", "signatory_last_name", "signatory_middle_name",
                         "signatory_job_title", "signatory_work_phone", "signatory_mobile_phone", 
                         "signatory_email_id"],
        "Address": ["address_street", "address_city", "address_state", "address_zip", 
                   "address_country", "address_number", "address_type"]
    },
    "attorney": {
        "attorneyInfo": ["firstName", "lastName", "middleName", "stateBarNumber", "barNumber",
                        "workPhone", "emailAddress", "faxNumber", "licensingAuthority"],
        "address": ["addressStreet", "addressCity", "addressState", "addressZip", 
                   "addressCountry", "addressNumber", "addressType"]
    },
    "attorneyLawfirmDetails": {
        "lawfirmDetails": ["lawFirmName", "lawFirmEIN"],
        "address": ["addressStreet", "addressCity", "addressState", "addressZip", 
                   "addressCountry", "addressNumber", "addressType"]
    },
    "case": {
        "": ["caseType", "caseSubType", "h1bRegistrationNumber"]
    }
}

@dataclass
class ExtractedField:
    """Represents a field extracted from PDF"""
    name: str
    label: str
    type: str  # text, checkbox, radio, dropdown
    value: str = ""
    page: int = 1
    part: str = "Part 1"
    part_number: int = 1
    part_title: str = ""
    item_number: str = ""  # e.g., "1.a", "2.b"
    
    # Mapping info
    db_path: Optional[str] = None
    is_questionnaire: bool = False
    is_conditional: bool = False
    conditional_data: Optional[Dict] = None
    mapping_confidence: float = 0.0
    ai_suggestion: Optional[str] = None
    
    # For questionnaire generation
    questionnaire_name: str = ""  # e.g., "1_ag", "pt3_1a"
    questionnaire_key: str = ""   # e.g., "pt3_1a"

@dataclass
class FormStructure:
    """Represents the structure of a form"""
    form_number: str
    form_title: str
    parts: Dict[str, List[ExtractedField]] = field(default_factory=OrderedDict)
    total_fields: int = 0
    total_pages: int = 0
    
    def get_part_numbers(self) -> List[str]:
        """Get sorted list of part numbers"""
        return sorted(self.parts.keys(), key=lambda x: int(re.search(r'\d+', x).group() if re.search(r'\d+', x) else 0))

# Base Agent Class
class Agent(ABC):
    """Base class for all agents"""
    
    def __init__(self, name: str):
        self.name = name
        self.status = "idle"
        self.last_action = ""
    
    @abstractmethod
    def execute(self, *args, **kwargs) -> Any:
        """Execute the agent's main task"""
        pass
    
    def update_status(self, status: str, action: str = ""):
        """Update agent status"""
        self.status = status
        self.last_action = action
        if status != "idle":
            st.markdown(f'<div class="agent-status">🤖 **{self.name}**: {status} {action}</div>', 
                       unsafe_allow_html=True)

# PDF Reader Agent
class PDFReaderAgent(Agent):
    """Agent responsible for reading and extracting fields from PDF"""
    
    def __init__(self):
        super().__init__("PDF Reader Agent")
    
    def execute(self, pdf_file) -> Optional[FormStructure]:
        """Extract fields from PDF"""
        self.update_status("active", "Starting PDF analysis...")
        
        try:
            pdf_bytes = pdf_file.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            # Detect form type
            form_info = self._detect_form_type(doc)
            form_structure = FormStructure(
                form_number=form_info['number'],
                form_title=form_info['title'],
                total_pages=len(doc)
            )
            
            self.update_status("active", f"Detected form: {form_info['number']}")
            
            # Extract fields by parts
            current_part = "Part 1"
            current_part_number = 1
            current_part_title = ""
            seen_fields = set()
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Check for part markers
                text = page.get_text()
                part_matches = re.finditer(r'Part\s+(\d+)[:\.]?\s*([^\n]*)', text, re.IGNORECASE)
                
                for match in part_matches:
                    part_num = int(match.group(1))
                    if part_num != current_part_number:
                        current_part_number = part_num
                        current_part = f"Part {part_num}"
                        current_part_title = match.group(2).strip()
                        break
                
                # Extract form fields
                widgets = page.widgets()
                if widgets:
                    if current_part not in form_structure.parts:
                        form_structure.parts[current_part] = []
                    
                    for widget in widgets:
                        if widget and hasattr(widget, 'field_name'):
                            field = self._extract_field(
                                widget, 
                                page_num + 1, 
                                current_part, 
                                current_part_number,
                                current_part_title
                            )
                            if field:
                                # Check for duplicates
                                field_key = f"{field.part}_{field.name}_{field.item_number}"
                                if field_key not in seen_fields:
                                    seen_fields.add(field_key)
                                    form_structure.parts[current_part].append(field)
                                    form_structure.total_fields += 1
            
            doc.close()
            
            # Sort fields within each part by item number
            for part_name in form_structure.parts:
                form_structure.parts[part_name].sort(
                    key=lambda f: (self._parse_item_number(f.item_number), f.label)
                )
            
            self.update_status("completed", f"Extracted {form_structure.total_fields} fields from {len(form_structure.parts)} parts")
            return form_structure
            
        except Exception as e:
            self.update_status("error", f"Failed to process PDF: {str(e)}")
            st.error(f"Error: {str(e)}")
            return None
    
    def _parse_item_number(self, item_num: str) -> Tuple[int, str]:
        """Parse item number for sorting (e.g., "1.a" -> (1, 'a'))"""
        if not item_num:
            return (999, '')
        
        match = re.match(r'(\d+)\.?([a-z]?)', item_num)
        if match:
            return (int(match.group(1)), match.group(2) or '')
        return (999, item_num)
    
    def _detect_form_type(self, doc) -> dict:
        """Detect USCIS form type"""
        first_page = doc[0].get_text().upper()
        
        forms = {
            'I-129': 'Petition for a Nonimmigrant Worker',
            'I-130': 'Petition for Alien Relative',
            'I-140': 'Immigrant Petition for Alien Worker',
            'I-485': 'Application to Register Permanent Residence',
            'I-765': 'Application for Employment Authorization',
            'N-400': 'Application for Naturalization',
            'G-28': 'Notice of Entry of Appearance as Attorney or Accredited Representative'
        }
        
        for form_num, title in forms.items():
            if form_num in first_page:
                return {'number': form_num, 'title': title}
        
        if 'H CLASSIFICATION SUPPLEMENT' in first_page:
            return {'number': 'I-129H', 'title': 'H Classification Supplement to Form I-129'}
        
        return {'number': 'Unknown', 'title': 'Unknown Form'}
    
    def _extract_field(self, widget, page: int, part: str, part_number: int, part_title: str) -> Optional[ExtractedField]:
        """Extract field information from widget"""
        try:
            if not widget.field_name:
                return None
            
            # Clean field name
            field_name = widget.field_name
            clean_name = re.sub(r'(form\d*\[?\d*\]?\.|#subform\[?\d*\]?\.)', '', field_name, flags=re.IGNORECASE)
            clean_name = re.sub(r'\[\d+\]', '', clean_name)
            clean_name = re.sub(r'^(Part\d+\.|Page\d+\.)', '', clean_name, flags=re.IGNORECASE)
            
            # Generate label
            parts = clean_name.split('.')
            label = parts[-1] if parts else clean_name
            label = re.sub(r'([a-z])([A-Z])', r'\1 \2', label)
            label = label.replace('_', ' ').title()
            
            # Extract item number from various patterns
            item_number = ""
            questionnaire_name = ""
            
            # Try different patterns
            patterns = [
                r'(\d+)\.([a-z])',  # 1.a, 2.b
                r'(\d+)([a-z])',    # 1a, 2b
                r'^(\d+)$',         # Just numbers
            ]
            
            for pattern in patterns:
                match = re.search(pattern, clean_name, re.IGNORECASE)
                if match:
                    if len(match.groups()) == 2:
                        item_number = f"{match.group(1)}.{match.group(2)}"
                        questionnaire_name = f"{match.group(1)}_{match.group(2)}"
                    else:
                        item_number = match.group(1)
                        questionnaire_name = match.group(1)
                    break
            
            # Determine field type
            type_map = {1: "button", 2: "checkbox", 3: "radio", 4: "text", 5: "dropdown"}
            field_type = type_map.get(widget.field_type, "text") if hasattr(widget, 'field_type') else "text"
            
            # Generate questionnaire key
            if item_number:
                quest_key = f"pt{part_number}_{item_number.replace('.', '')}"
            else:
                quest_key = f"pt{part_number}_{clean_name[:10]}"
            
            # Create field
            extracted_field = ExtractedField(
                name=clean_name,
                label=label,
                type=field_type,
                page=page,
                part=part,
                part_number=part_number,
                part_title=part_title,
                item_number=item_number,
                is_questionnaire=field_type in ["checkbox", "radio"],
                questionnaire_name=questionnaire_name or clean_name,
                questionnaire_key=quest_key
            )
            
            # Check if it's conditional (has associated text field)
            if field_type in ["checkbox", "radio"] and item_number:
                extracted_field.is_conditional = True
            
            return extracted_field
            
        except Exception:
            return None

# Mapping Agent
class MappingAgent(Agent):
    """Agent responsible for mapping fields to database objects"""
    
    def __init__(self, api_key: str):
        super().__init__("Mapping Agent")
        self.api_key = api_key
        if api_key:
            openai.api_key = api_key
    
    def execute(self, form_structure: FormStructure, auto_map: bool = True) -> None:
        """Map fields to database objects"""
        if not auto_map:
            return
        
        self.update_status("active", "Starting intelligent field mapping...")
        
        total_mapped = 0
        
        for part_name, fields in form_structure.parts.items():
            for field in fields:
                if field.type == "text" and not field.db_path:
                    # Try pattern matching first
                    suggestion = self._pattern_match(field)
                    
                    # If no pattern match, use AI
                    if not suggestion and self.api_key:
                        suggestion = self._ai_suggest(field)
                    
                    if suggestion:
                        field.db_path = suggestion
                        field.mapping_confidence = 0.9 if self._pattern_match(field) else 0.7
                        total_mapped += 1
        
        self.update_status("completed", f"Mapped {total_mapped} fields automatically")
    
    def _pattern_match(self, field: ExtractedField) -> Optional[str]:
        """Pattern-based field matching"""
        label_lower = field.label.lower()
        name_lower = field.name.lower()
        
        patterns = {
            # Customer/Signatory patterns
            'signatory.*first.*name|signatory.*given': 'customer.SignatoryInfo.signatory_first_name',
            'signatory.*last.*name|signatory.*family': 'customer.SignatoryInfo.signatory_last_name',
            'signatory.*middle': 'customer.SignatoryInfo.signatory_middle_name',
            'signatory.*email': 'customer.SignatoryInfo.signatory_email_id',
            'signatory.*phone|signatory.*work.*phone': 'customer.SignatoryInfo.signatory_work_phone',
            'signatory.*mobile|signatory.*cell': 'customer.SignatoryInfo.signatory_mobile_phone',
            'signatory.*title|signatory.*job': 'customer.SignatoryInfo.signatory_job_title',
            'customer.*name|organization.*name': 'customer.customer_name',
            
            # Attorney patterns
            'attorney.*first.*name|attorney.*given': 'attorney.attorneyInfo.firstName',
            'attorney.*last.*name|attorney.*family': 'attorney.attorneyInfo.lastName',
            'attorney.*middle': 'attorney.attorneyInfo.middleName',
            'state.*bar.*number': 'attorney.attorneyInfo.stateBarNumber',
            'bar.*number': 'attorney.attorneyInfo.barNumber',
            'law.*firm.*name': 'attorneyLawfirmDetails.lawfirmDetails.lawFirmName',
            'licensing.*authority': 'attorney.attorneyInfo.licensingAuthority',
            
            # Beneficiary patterns
            'beneficiary.*first|given.*name': 'beneficiary.Beneficiary.beneficiaryFirstName',
            'beneficiary.*last|family.*name': 'beneficiary.Beneficiary.beneficiaryLastName',
            'beneficiary.*middle': 'beneficiary.Beneficiary.beneficiaryMiddleName',
            'alien.*number|a.*number': 'beneficiary.Beneficiary.alienNumber',
            'uscis.*account': 'beneficiary.Beneficiary.uscisOnlineAccountNumber',
            'date.*birth': 'beneficiary.Beneficiary.beneficiaryDateOfBirth',
            
            # Address patterns (context-sensitive)
            'street|address.*street': 'customer.Address.address_street',
            'city': 'customer.Address.address_city',
            'state': 'customer.Address.address_state',
            'zip': 'customer.Address.address_zip',
            'country': 'customer.Address.address_country',
            
            # Contact patterns
            'email': 'beneficiary.ContactInfo.emailAddress',
            'daytime.*phone': 'beneficiary.ContactInfo.daytimeTelephoneNumber',
            'mobile': 'beneficiary.ContactInfo.mobileTelephoneNumber',
        }
        
        # Check both label and name
        for pattern, db_path in patterns.items():
            if re.search(pattern, label_lower) or re.search(pattern, name_lower):
                return db_path
        
        return None
    
    def _ai_suggest(self, field: ExtractedField) -> Optional[str]:
        """Use AI to suggest field mapping"""
        try:
            # Build context
            db_fields = []
            for obj, categories in DB_STRUCTURE.items():
                for cat, fields in categories.items():
                    for f in fields:
                        if cat:
                            db_fields.append(f"{obj}.{cat}.{f}")
                        else:
                            db_fields.append(f"{obj}.{f}")
            
            prompt = f"""
            Map this form field to the most appropriate database field:
            
            Field Label: {field.label}
            Field Name: {field.name}
            Field Type: {field.type}
            Part: {field.part} - {field.part_title}
            Item Number: {field.item_number}
            
            Available database fields:
            {json.dumps(db_fields, indent=2)}
            
            Return ONLY the database path (e.g., beneficiary.Beneficiary.firstName) or 'null' if no match.
            """
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=50
            )
            
            suggestion = response.choices[0].message.content.strip()
            if suggestion != 'null' and suggestion in db_fields:
                field.ai_suggestion = suggestion
                return suggestion
                
        except Exception:
            pass
        
        return None

# Export Agent
class ExportAgent(Agent):
    """Agent responsible for exporting data in various formats"""
    
    def __init__(self):
        super().__init__("Export Agent")
    
    def execute(self, form_structure: FormStructure, format: str) -> str:
        """Export form data in specified format"""
        self.update_status("active", f"Generating {format} export...")
        
        if format == "typescript":
            result = self._generate_typescript(form_structure)
        elif format == "json":
            result = self._generate_json(form_structure)
        else:
            result = ""
        
        self.update_status("completed", f"{format} export ready")
        return result
    
    def _get_field_suffix(self, field_type: str) -> str:
        """Get the appropriate suffix for field type"""
        suffix_map = {
            'text': ':TextBox',
            'checkbox': ':CheckBox',
            'radio': ':RadioBox',
            'dropdown': ':DropdownBox',
            'button': ':ButtonBox'
        }
        return suffix_map.get(field_type, ':TextBox')
    
    def _generate_typescript(self, form_structure: FormStructure) -> str:
        """Generate TypeScript export"""
        form_name = form_structure.form_number.replace('-', '')
        
        # Initialize sections
        sections = {
            'customerData': {},
            'beneficiaryData': {},
            'attorneyData': {},
            'questionnaireData': {},
            'defaultData': {},
            'conditionalData': {},
            'caseData': {}
        }
        
        # Track conditional fields
        conditional_fields = []
        
        for part_name, fields in form_structure.parts.items():
            for field in fields:
                if field.db_path:
                    # Determine section based on database path
                    if field.db_path.startswith('customer.'):
                        section = 'customerData'
                    elif field.db_path.startswith('beneficiary.'):
                        section = 'beneficiaryData'
                    elif field.db_path.startswith('attorney.') or field.db_path.startswith('attorneyLawfirmDetails.'):
                        section = 'attorneyData'
                    elif field.db_path.startswith('case.'):
                        section = 'caseData'
                    else:
                        continue
                    
                    # Create field key
                    field_key = field.name
                    if field.db_path.startswith('customer.'):
                        field_key = 'customer' + field.name
                    elif field.db_path.startswith('attorney.'):
                        field_key = 'attorney' + field.name
                    
                    suffix = self._get_field_suffix(field.type)
                    sections[section][field_key] = f"{field.db_path}{suffix}"
                
                elif field.is_questionnaire:
                    # Add to questionnaire data
                    quest_key = field.questionnaire_key
                    sections['questionnaireData'][quest_key] = f"{field.questionnaire_name}:ConditionBox"
                    
                    # Track conditional fields
                    if field.is_conditional:
                        conditional_fields.append(field)
        
        # Generate conditional data
        for field in conditional_fields:
            if field.type == "checkbox":
                sections['conditionalData'][field.questionnaire_key] = {
                    'condition': f"{field.questionnaire_name}==true",
                    'conditionTrue': 'true',
                    'conditionFalse': '',
                    'conditionType': 'CheckBox',
                    'conditionParam': '',
                    'conditionData': ''
                }
            elif field.type == "radio":
                sections['conditionalData'][field.questionnaire_key] = {
                    'condition': f"representative=={field.item_number.split('.')[0] if field.item_number else '1'}",
                    'conditionTrue': field.item_number.split('.')[0] if field.item_number else '1',
                    'conditionFalse': '',
                    'conditionType': 'CheckBox',
                    'conditionParam': '',
                    'conditionData': ''
                }
        
        # Build TypeScript output
        ts = f'export const {form_name} = {{\n'
        ts += f'    "formname": "{form_name}",\n'
        
        # Add each section
        for section_name in ['customerData', 'beneficiaryData', 'attorneyData', 'questionnaireData', 
                           'defaultData', 'conditionalData', 'caseData']:
            if section_name == 'conditionalData' and sections[section_name]:
                ts += f'    "{section_name}": {{\n'
                for key, value in sections[section_name].items():
                    ts += f'        "{key}": {{\n'
                    for k, v in value.items():
                        ts += f'            "{k}": "{v}",\n'
                    ts = ts.rstrip(',\n') + '\n'
                    ts += '        },\n'
                ts = ts.rstrip(',\n') + '\n'
                ts += '    },\n'
            elif sections[section_name]:
                ts += f'    "{section_name}": {{\n'
                for key, value in sections[section_name].items():
                    ts += f'        "{key}": "{value}",\n'
                ts = ts.rstrip(',\n') + '\n'
                ts += '    },\n'
            else:
                ts += f'    "{section_name}": null,\n'
        
        ts += f'    "pdfName": "{form_structure.form_number}"\n'
        ts += '};\n\n'
        ts += f'export default {form_name};'
        
        return ts
    
    def _generate_json(self, form_structure: FormStructure) -> str:
        """Generate JSON for questionnaire"""
        controls = []
        
        for part_name, fields in form_structure.parts.items():
            quest_fields = [f for f in fields if f.is_questionnaire or (f.type == "text" and not f.db_path)]
            
            if quest_fields:
                # Add part title
                part_num = quest_fields[0].part_number
                title_text = f"{part_name}: {quest_fields[0].part_title}" if quest_fields[0].part_title else part_name
                
                controls.append({
                    "name": f"{part_num}_title",
                    "label": title_text,
                    "type": "title",
                    "validators": {},
                    "style": {"col": "12"}
                })
                
                # Add fields
                for field in quest_fields:
                    label = field.label
                    if field.item_number:
                        label = f"{field.item_number}. {label}"
                    
                    control = {
                        "name": field.questionnaire_name,
                        "label": label,
                        "type": "colorSwitch" if field.type in ["checkbox", "radio"] else field.type,
                        "validators": {"required": False}
                    }
                    
                    # Style based on type
                    if field.type == "text":
                        control["style"] = {"col": "7"}
                    else:
                        control["style"] = {"col": "12"}
                    
                    # Radio button specifics
                    if field.type == "radio":
                        control["id"] = field.questionnaire_name
                        control["value"] = field.item_number.split('.')[0] if field.item_number else "1"
                        control["name"] = "representative"  # Group radios together
                    
                    controls.append(control)
        
        return json.dumps({"controls": controls}, indent=2)

# Main UI Functions
def render_field_mapping(form_structure: FormStructure, selected_part: str):
    """Render field mapping interface for selected part"""
    st.markdown("## 🎯 Field Mapping")
    
    # Part selector
    st.markdown('<div class="part-selector">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([3, 2, 2])
    
    with col1:
        part_options = form_structure.get_part_numbers()
        selected_part = st.selectbox(
            "📑 Select Part to View",
            part_options,
            index=part_options.index(selected_part) if selected_part in part_options else 0,
            key="part_selector"
        )
    
    with col2:
        # Stats for selected part
        if selected_part in form_structure.parts:
            part_fields = form_structure.parts[selected_part]
            mapped = sum(1 for f in part_fields if f.db_path)
            quest = sum(1 for f in part_fields if f.is_questionnaire)
            st.metric("Part Progress", f"{mapped + quest}/{len(part_fields)}")
    
    with col3:
        # Overall stats
        total_fields = form_structure.total_fields
        total_mapped = sum(1 for fields in form_structure.parts.values() for f in fields if f.db_path)
        total_quest = sum(1 for fields in form_structure.parts.values() for f in fields if f.is_questionnaire)
        st.metric("Overall Progress", f"{total_mapped + total_quest}/{total_fields}")
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Display fields for selected part
    if selected_part in form_structure.parts:
        fields = form_structure.parts[selected_part]
        
        # Part header
        st.markdown(f'''
        <div class="part-header">
            <h3>{selected_part}</h3>
            {f'<p>{fields[0].part_title}</p>' if fields and fields[0].part_title else ''}
            <small>{len(fields)} fields extracted</small>
        </div>
        ''', unsafe_allow_html=True)
        
        # Display each field
        for idx, field in enumerate(fields):
            # Determine status
            if field.db_path:
                status_class = "mapped"
                status_text = "✅ Mapped to Database"
            elif field.is_questionnaire:
                status_class = "questionnaire"
                status_text = "📋 Questionnaire Field"
            else:
                status_class = "unmapped"
                status_text = "❌ Not Mapped"
            
            # Field card
            st.markdown(f'<div class="field-card {status_class}">', unsafe_allow_html=True)
            
            col1, col2, col3 = st.columns([3, 3, 1])
            
            with col1:
                # Field label with item number
                if field.item_number:
                    st.markdown(f'<span class="item-number">{field.item_number}</span>{field.label}', 
                              unsafe_allow_html=True)
                else:
                    st.markdown(f'**{field.label}**')
                
                # Field info
                st.markdown(f'''
                <div class="field-info">
                    Field type: {field.type} • Page: {field.page}<br>
                    Internal name: {field.name}
                </div>
                ''', unsafe_allow_html=True)
            
            with col2:
                if field.type == "text":
                    # Database mapping dropdown
                    db_options = ["-- Select Database Field --", "📋 Move to Questionnaire"]
                    
                    # Build grouped options
                    for obj, categories in DB_STRUCTURE.items():
                        for cat, db_fields in categories.items():
                            for f in db_fields:
                                if cat:
                                    db_options.append(f"{obj}.{cat}.{f}")
                                else:
                                    db_options.append(f"{obj}.{f}")
                    
                    current = field.db_path if field.db_path else "-- Select Database Field --"
                    if field.is_questionnaire:
                        current = "📋 Move to Questionnaire"
                    
                    selected = st.selectbox(
                        "Map to",
                        db_options,
                        index=db_options.index(current) if current in db_options else 0,
                        key=f"map_{selected_part}_{idx}",
                        label_visibility="collapsed"
                    )
                    
                    if selected != current:
                        if selected == "📋 Move to Questionnaire":
                            field.is_questionnaire = True
                            field.db_path = None
                        elif selected != "-- Select Database Field --":
                            field.db_path = selected
                            field.is_questionnaire = False
                        st.rerun()
                else:
                    # Checkbox/Radio options
                    include = st.checkbox(
                        "Include in Questionnaire",
                        value=field.is_questionnaire,
                        key=f"quest_{selected_part}_{idx}"
                    )
                    if include != field.is_questionnaire:
                        field.is_questionnaire = include
                        st.rerun()
                    
                    if field.is_conditional:
                        st.caption("This field has conditional logic")
            
            with col3:
                st.markdown(f"**{status_text}**")
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    return selected_part

def main():
    st.title("🤖 USCIS Form Extractor - AI Agents")
    st.markdown("Intelligent form field extraction and mapping using specialized agents")
    
    # Initialize session state
    if 'form_structure' not in st.session_state:
        st.session_state.form_structure = None
    if 'agents' not in st.session_state:
        st.session_state.agents = {}
    if 'selected_part' not in st.session_state:
        st.session_state.selected_part = "Part 1"
    
    # Sidebar for configuration
    with st.sidebar:
        st.markdown("## ⚙️ Configuration")
        
        # OpenAI API Key
        api_key = st.text_input(
            "OpenAI API Key",
            type="password",
            value=st.secrets.get("OPENAI_API_KEY", ""),
            help="Required for intelligent field mapping"
        )
        
        st.markdown("## 🤖 Agent Status")
        for agent_name, agent in st.session_state.agents.items():
            st.markdown(f"**{agent_name}**: {agent.status}")
        
        if st.session_state.form_structure:
            st.markdown("## 📊 Form Statistics")
            st.metric("Total Parts", len(st.session_state.form_structure.parts))
            st.metric("Total Fields", st.session_state.form_structure.total_fields)
            
            # Part breakdown
            st.markdown("### Fields by Part")
            for part in st.session_state.form_structure.get_part_numbers():
                fields = st.session_state.form_structure.parts[part]
                st.caption(f"{part}: {len(fields)} fields")
    
    # Main tabs
    tab1, tab2, tab3 = st.tabs(["📤 Upload & Extract", "🎯 Map Fields", "📥 Export"])
    
    with tab1:
        st.markdown("## Upload PDF Form")
        
        uploaded_file = st.file_uploader(
            "Choose a USCIS PDF form",
            type=['pdf'],
            help="Upload any fillable USCIS form (G-28, I-129, I-130, etc.)"
        )
        
        if uploaded_file:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                auto_map = st.checkbox("Enable AI Auto-Mapping", value=True, help="Use AI to suggest field mappings")
            
            with col2:
                if st.button("🚀 Process PDF", type="primary", use_container_width=True):
                    # Initialize agents
                    st.session_state.agents['pdf_reader'] = PDFReaderAgent()
                    st.session_state.agents['mapper'] = MappingAgent(api_key)
                    st.session_state.agents['exporter'] = ExportAgent()
                    
                    # Execute PDF reading
                    with st.spinner("Processing PDF..."):
                        form_structure = st.session_state.agents['pdf_reader'].execute(uploaded_file)
                        
                        if form_structure:
                            st.session_state.form_structure = form_structure
                            st.session_state.selected_part = form_structure.get_part_numbers()[0] if form_structure.parts else "Part 1"
                            
                            # Execute mapping if enabled
                            if auto_map and api_key:
                                st.session_state.agents['mapper'].execute(form_structure)
                            
                            st.success(f"✅ Successfully processed {form_structure.form_number}")
                            
                            # Show summary
                            with st.expander("📊 Extraction Summary", expanded=True):
                                for part in form_structure.get_part_numbers():
                                    fields = form_structure.parts[part]
                                    st.write(f"**{part}**: {len(fields)} fields")
                                    
                                    # Field type breakdown
                                    types = defaultdict(int)
                                    for field in fields:
                                        types[field.type] += 1
                                    
                                    type_info = ", ".join([f"{count} {t}" for t, count in types.items()])
                                    st.caption(f"Types: {type_info}")
    
    with tab2:
        if st.session_state.form_structure:
            # Quick actions
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                if st.button("🤖 Auto-Map All", use_container_width=True):
                    if api_key:
                        mapper = MappingAgent(api_key)
                        mapper.execute(st.session_state.form_structure)
                        st.success("Auto-mapping complete!")
                        st.rerun()
                    else:
                        st.error("Please provide OpenAI API key")
            
            with col2:
                if st.button("📋 Checkboxes to Quest", use_container_width=True):
                    count = 0
                    for fields in st.session_state.form_structure.parts.values():
                        for field in fields:
                            if field.type in ["checkbox", "radio"] and not field.is_questionnaire:
                                field.is_questionnaire = True
                                count += 1
                    st.success(f"Moved {count} fields")
                    st.rerun()
            
            with col3:
                if st.button("📝 Unmapped to Quest", use_container_width=True):
                    count = 0
                    for fields in st.session_state.form_structure.parts.values():
                        for field in fields:
                            if not field.db_path and not field.is_questionnaire:
                                field.is_questionnaire = True
                                count += 1
                    st.success(f"Moved {count} fields")
                    st.rerun()
            
            with col4:
                if st.button("🔄 Reset All", use_container_width=True):
                    for fields in st.session_state.form_structure.parts.values():
                        for field in fields:
                            field.db_path = None
                            field.is_questionnaire = field.type in ["checkbox", "radio"]
                    st.rerun()
            
            # Render mapping interface
            st.session_state.selected_part = render_field_mapping(
                st.session_state.form_structure, 
                st.session_state.selected_part
            )
        else:
            st.info("👆 Please upload and process a PDF form first")
    
    with tab3:
        if st.session_state.form_structure:
            st.markdown("## 📥 Export Options")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### TypeScript Export")
                st.markdown("Database field mappings in TypeScript format")
                
                if st.button("Generate TypeScript", use_container_width=True):
                    exporter = ExportAgent()
                    ts_code = exporter.execute(st.session_state.form_structure, "typescript")
                    
                    st.download_button(
                        "⬇️ Download TypeScript",
                        ts_code,
                        f"{st.session_state.form_structure.form_number}.ts",
                        mime="text/typescript"
                    )
                    
                    with st.expander("Preview TypeScript"):
                        st.code(ts_code, language="typescript")
            
            with col2:
                st.markdown("### JSON Export")
                st.markdown("Questionnaire configuration in JSON format")
                
                if st.button("Generate JSON", use_container_width=True):
                    exporter = ExportAgent()
                    json_code = exporter.execute(st.session_state.form_structure, "json")
                    
                    st.download_button(
                        "⬇️ Download JSON",
                        json_code,
                        f"{st.session_state.form_structure.form_number}-questionnaire.json",
                        mime="application/json"
                    )
                    
                    with st.expander("Preview JSON"):
                        st.code(json_code, language="json")
        else:
            st.info("👆 Please process a form first")

if __name__ == "__main__":
    main()
