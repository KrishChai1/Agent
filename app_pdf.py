import streamlit as st
import json
import re
import fitz  # PyMuPDF
from typing import Dict, List, Optional, Any
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
</style>
""", unsafe_allow_html=True)

# Database structure for mapping
DB_STRUCTURE = {
    "beneficiary": {
        "personal": ["firstName", "lastName", "middleName", "dateOfBirth", "gender", "ssn"],
        "identification": ["alienNumber", "uscisAccountNumber", "passportNumber"],
        "address": ["street", "city", "state", "zipCode", "country"],
        "contact": ["email", "phone", "mobile"]
    },
    "petitioner": {
        "personal": ["firstName", "lastName", "middleName", "companyName"],
        "contact": ["email", "phone", "fax"],
        "address": ["street", "city", "state", "zipCode", "country"]
    },
    "attorney": {
        "info": ["firstName", "lastName", "barNumber", "firmName"],
        "contact": ["email", "phone", "fax"],
        "address": ["street", "city", "state", "zipCode"]
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
    part_title: str = ""
    item_number: str = ""  # e.g., "1.a", "2.b"
    
    # Mapping info
    db_path: Optional[str] = None
    is_questionnaire: bool = False
    mapping_confidence: float = 0.0
    ai_suggestion: Optional[str] = None

@dataclass
class FormStructure:
    """Represents the structure of a form"""
    form_number: str
    form_title: str
    parts: Dict[str, List[ExtractedField]] = field(default_factory=dict)
    total_fields: int = 0
    total_pages: int = 0

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
            current_part_title = ""
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Check for part markers
                text = page.get_text()
                part_match = re.search(r'Part\s+(\d+)[:\.]?\s*([^\n]*)', text, re.IGNORECASE)
                if part_match:
                    current_part = f"Part {part_match.group(1)}"
                    current_part_title = part_match.group(2).strip()
                
                # Extract form fields
                widgets = page.widgets()
                if widgets:
                    if current_part not in form_structure.parts:
                        form_structure.parts[current_part] = []
                    
                    for widget in widgets:
                        if widget and hasattr(widget, 'field_name'):
                            field = self._extract_field(widget, page_num + 1, current_part, current_part_title)
                            if field:
                                form_structure.parts[current_part].append(field)
                                form_structure.total_fields += 1
            
            doc.close()
            
            self.update_status("completed", f"Extracted {form_structure.total_fields} fields from {len(form_structure.parts)} parts")
            return form_structure
            
        except Exception as e:
            self.update_status("error", f"Failed to process PDF: {str(e)}")
            st.error(f"Error: {str(e)}")
            return None
    
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
            'G-28': 'Notice of Entry of Appearance'
        }
        
        for form_num, title in forms.items():
            if form_num in first_page:
                return {'number': form_num, 'title': title}
        
        return {'number': 'Unknown', 'title': 'Unknown Form'}
    
    def _extract_field(self, widget, page: int, part: str, part_title: str) -> Optional[ExtractedField]:
        """Extract field information from widget"""
        try:
            if not widget.field_name:
                return None
            
            # Clean field name
            field_name = widget.field_name
            clean_name = re.sub(r'(form\d*\[?\d*\]?\.|#subform\[?\d*\]?\.)', '', field_name, flags=re.IGNORECASE)
            clean_name = re.sub(r'\[\d+\]', '', clean_name)
            
            # Generate label
            parts = clean_name.split('.')
            label = parts[-1] if parts else clean_name
            label = re.sub(r'([a-z])([A-Z])', r'\1 \2', label)
            label = label.replace('_', ' ').title()
            
            # Extract item number
            item_match = re.search(r'(\d+)\.?([a-z]?)', clean_name)
            item_number = ""
            if item_match:
                item_number = f"{item_match.group(1)}"
                if item_match.group(2):
                    item_number += f".{item_match.group(2)}"
            
            # Determine field type
            type_map = {1: "button", 2: "checkbox", 3: "radio", 4: "text", 5: "dropdown"}
            field_type = type_map.get(widget.field_type, "text") if hasattr(widget, 'field_type') else "text"
            
            return ExtractedField(
                name=clean_name,
                label=label,
                type=field_type,
                page=page,
                part=part,
                part_title=part_title,
                item_number=item_number,
                is_questionnaire=field_type in ["checkbox", "radio"]
            )
            
        except Exception:
            return None

# Mapping Agent
class MappingAgent(Agent):
    """Agent responsible for mapping fields to database objects"""
    
    def __init__(self, api_key: str):
        super().__init__("Mapping Agent")
        self.api_key = api_key
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
        
        patterns = {
            'first name': 'beneficiary.personal.firstName',
            'given name': 'beneficiary.personal.firstName',
            'last name': 'beneficiary.personal.lastName',
            'family name': 'beneficiary.personal.lastName',
            'middle name': 'beneficiary.personal.middleName',
            'date of birth': 'beneficiary.personal.dateOfBirth',
            'email': 'beneficiary.contact.email',
            'phone': 'beneficiary.contact.phone',
            'street': 'beneficiary.address.street',
            'city': 'beneficiary.address.city',
            'state': 'beneficiary.address.state',
            'zip': 'beneficiary.address.zipCode',
            'alien number': 'beneficiary.identification.alienNumber',
            'a-number': 'beneficiary.identification.alienNumber',
            'ssn': 'beneficiary.personal.ssn',
            'social security': 'beneficiary.personal.ssn'
        }
        
        for pattern, db_path in patterns.items():
            if pattern in label_lower:
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
                        db_fields.append(f"{obj}.{cat}.{f}")
            
            prompt = f"""
            Map this form field to the most appropriate database field:
            
            Field Label: {field.label}
            Field Name: {field.name}
            Field Type: {field.type}
            Part: {field.part} - {field.part_title}
            
            Available database fields:
            {json.dumps(db_fields, indent=2)}
            
            Return ONLY the database path (e.g., beneficiary.personal.firstName) or 'null' if no match.
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
    
    def _generate_typescript(self, form_structure: FormStructure) -> str:
        """Generate TypeScript export"""
        form_name = form_structure.form_number.replace('-', '')
        
        # Group fields by type
        sections = {
            'beneficiaryData': {},
            'petitionerData': {},
            'attorneyData': {},
            'questionnaireData': {}
        }
        
        for part_name, fields in form_structure.parts.items():
            for field in fields:
                if field.db_path:
                    # Determine section
                    if field.db_path.startswith('beneficiary.'):
                        section = 'beneficiaryData'
                    elif field.db_path.startswith('petitioner.'):
                        section = 'petitionerData'
                    elif field.db_path.startswith('attorney.'):
                        section = 'attorneyData'
                    else:
                        continue
                    
                    sections[section][field.name] = f"{field.db_path}:TextBox"
                
                elif field.is_questionnaire:
                    key = f"pt{part_name.split()[-1]}_{field.item_number.replace('.', '')}" if field.item_number else field.name
                    sections['questionnaireData'][key] = f"{field.name}:ConditionBox"
        
        # Build TypeScript
        ts = f"export const {form_name} = {{\n"
        ts += f'  formname: "{form_name}",\n'
        
        for section_name, fields_map in sections.items():
            if fields_map:
                ts += f'  {section_name}: {{\n'
                for key, value in fields_map.items():
                    ts += f'    "{key}": "{value}",\n'
                ts = ts.rstrip(',\n') + '\n'
                ts += '  },\n'
            else:
                ts += f'  {section_name}: null,\n'
        
        ts += f'  pdfName: "{form_structure.form_number}"\n'
        ts += '};\n\n'
        ts += f'export default {form_name};'
        
        return ts
    
    def _generate_json(self, form_structure: FormStructure) -> str:
        """Generate JSON for questionnaire"""
        controls = []
        
        for part_name, fields in form_structure.parts.items():
            quest_fields = [f for f in fields if f.is_questionnaire]
            
            if quest_fields:
                # Add part title
                controls.append({
                    "name": f"{part_name.lower().replace(' ', '_')}_title",
                    "label": f"{part_name}: {quest_fields[0].part_title}" if quest_fields[0].part_title else part_name,
                    "type": "title",
                    "style": {"col": "12"}
                })
                
                # Add fields
                for field in quest_fields:
                    label = f"{field.item_number}. {field.label}" if field.item_number else field.label
                    
                    controls.append({
                        "name": field.name,
                        "label": label,
                        "type": "colorSwitch",
                        "validators": {},
                        "style": {"col": "12"}
                    })
        
        return json.dumps({"controls": controls}, indent=2)

# Main UI Functions
def render_field_mapping(form_structure: FormStructure):
    """Render field mapping interface"""
    st.markdown("## 🎯 Field Mapping")
    
    # Quick stats
    col1, col2, col3 = st.columns(3)
    total_fields = form_structure.total_fields
    mapped_fields = sum(1 for fields in form_structure.parts.values() for f in fields if f.db_path)
    quest_fields = sum(1 for fields in form_structure.parts.values() for f in fields if f.is_questionnaire)
    
    col1.metric("Total Fields", total_fields)
    col2.metric("Mapped to DB", mapped_fields)
    col3.metric("Questionnaire", quest_fields)
    
    # Display fields by part
    for part_name, fields in form_structure.parts.items():
        with st.expander(f"**{part_name}** ({len(fields)} fields)", expanded=True):
            st.markdown(f'<div class="part-header">{part_name}: {fields[0].part_title if fields and fields[0].part_title else ""}</div>', 
                       unsafe_allow_html=True)
            
            for idx, field in enumerate(fields):
                # Determine status
                if field.db_path:
                    status_class = "mapped"
                    status_text = "✅ Mapped"
                elif field.is_questionnaire:
                    status_class = "questionnaire"
                    status_text = "📋 Questionnaire"
                else:
                    status_class = "unmapped"
                    status_text = "❌ Unmapped"
                
                # Field card
                st.markdown(f'<div class="field-card {status_class}">', unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns([3, 3, 1])
                
                with col1:
                    label = f"{field.item_number}. {field.label}" if field.item_number else field.label
                    st.markdown(f"**{label}**")
                    st.caption(f"Type: {field.type} | Page: {field.page}")
                
                with col2:
                    if field.type == "text":
                        # Database mapping
                        db_options = ["-- Select Database Field --"]
                        for obj, categories in DB_STRUCTURE.items():
                            for cat, db_fields in categories.items():
                                for f in db_fields:
                                    db_options.append(f"{obj}.{cat}.{f}")
                        
                        current = field.db_path if field.db_path else "-- Select Database Field --"
                        selected = st.selectbox(
                            "Map to",
                            db_options,
                            index=db_options.index(current) if current in db_options else 0,
                            key=f"map_{part_name}_{idx}",
                            label_visibility="collapsed"
                        )
                        
                        if selected != current and selected != "-- Select Database Field --":
                            field.db_path = selected
                            st.rerun()
                    else:
                        # Questionnaire toggle
                        field.is_questionnaire = st.checkbox(
                            "Include in Questionnaire",
                            value=field.is_questionnaire,
                            key=f"quest_{part_name}_{idx}"
                        )
                
                with col3:
                    st.markdown(f"**{status_text}**")
                
                st.markdown('</div>', unsafe_allow_html=True)

def main():
    st.title("🤖 USCIS Form Extractor - AI Agents")
    st.markdown("Intelligent form field extraction and mapping using specialized agents")
    
    # Initialize session state
    if 'form_structure' not in st.session_state:
        st.session_state.form_structure = None
    if 'agents' not in st.session_state:
        st.session_state.agents = {}
    
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
    
    # Main tabs
    tab1, tab2, tab3 = st.tabs(["📤 Upload & Extract", "🎯 Map Fields", "📥 Export"])
    
    with tab1:
        st.markdown("## Upload PDF Form")
        
        uploaded_file = st.file_uploader(
            "Choose a USCIS PDF form",
            type=['pdf'],
            help="Upload any fillable USCIS form"
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
                    with st.spinner("Processing..."):
                        form_structure = st.session_state.agents['pdf_reader'].execute(uploaded_file)
                        
                        if form_structure:
                            st.session_state.form_structure = form_structure
                            
                            # Execute mapping if enabled
                            if auto_map and api_key:
                                st.session_state.agents['mapper'].execute(form_structure)
                            
                            st.success(f"✅ Successfully processed {form_structure.form_number}")
                            st.balloons()
    
    with tab2:
        if st.session_state.form_structure:
            # Quick actions
            col1, col2, col3 = st.columns(3)
            
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
                if st.button("📋 All to Questionnaire", use_container_width=True):
                    count = 0
                    for fields in st.session_state.form_structure.parts.values():
                        for field in fields:
                            if field.type in ["checkbox", "radio"] and not field.is_questionnaire:
                                field.is_questionnaire = True
                                count += 1
                    st.success(f"Moved {count} fields to questionnaire")
                    st.rerun()
            
            with col3:
                if st.button("🔄 Reset All", use_container_width=True):
                    for fields in st.session_state.form_structure.parts.values():
                        for field in fields:
                            field.db_path = None
                            field.is_questionnaire = field.type in ["checkbox", "radio"]
                    st.rerun()
            
            # Render mapping interface
            render_field_mapping(st.session_state.form_structure)
        else:
            st.info("👆 Please upload and process a PDF form first")
    
    with tab3:
        if st.session_state.form_structure:
            st.markdown("## 📥 Export Options")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### TypeScript Export")
                st.markdown("For database field mappings")
                
                if st.button("Generate TypeScript", use_container_width=True):
                    exporter = ExportAgent()
                    ts_code = exporter.execute(st.session_state.form_structure, "typescript")
                    
                    st.download_button(
                        "⬇️ Download TypeScript",
                        ts_code,
                        f"{st.session_state.form_structure.form_number}.ts",
                        mime="text/typescript"
                    )
                    
                    with st.expander("Preview"):
                        st.code(ts_code, language="typescript")
            
            with col2:
                st.markdown("### JSON Export")
                st.markdown("For questionnaire configuration")
                
                if st.button("Generate JSON", use_container_width=True):
                    exporter = ExportAgent()
                    json_code = exporter.execute(st.session_state.form_structure, "json")
                    
                    st.download_button(
                        "⬇️ Download JSON",
                        json_code,
                        f"{st.session_state.form_structure.form_number}-questionnaire.json",
                        mime="application/json"
                    )
                    
                    with st.expander("Preview"):
                        st.code(json_code, language="json")
        else:
            st.info("👆 Please process a form first")

if __name__ == "__main__":
    main()
