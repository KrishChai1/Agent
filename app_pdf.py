import streamlit as st
import PyPDF2
from PyPDF2 import PdfReader
import json
import re
from datetime import datetime
import pandas as pd
from typing import Dict, List, Any, Optional
import io

# Page configuration
st.set_page_config(
    page_title="PDF Form Automation System",
    page_icon="📄",
    layout="wide"
)

# Initialize session state
if 'pdf_fields' not in st.session_state:
    st.session_state.pdf_fields = []
if 'mapped_fields' not in st.session_state:
    st.session_state.mapped_fields = {}
if 'questionnaire_fields' not in st.session_state:
    st.session_state.questionnaire_fields = {}
if 'conditional_fields' not in st.session_state:
    st.session_state.conditional_fields = {}

# Predefined mapping patterns based on your documents
MAPPING_PATTERNS = {
    'customer': {
        'patterns': [
            r'customer[_\s]?name', r'company[_\s]?name', r'employer[_\s]?name',
            r'petitioner[_\s]?name', r'organization[_\s]?name'
        ],
        'mapping': 'customer.customer_name'
    },
    'beneficiary_first_name': {
        'patterns': [
            r'beneficiary[_\s]?first[_\s]?name', r'given[_\s]?name',
            r'ben[_\s]?firstname', r'ben[_\s]?givenname'
        ],
        'mapping': 'beneficiary.Beneficiary.beneficiaryFirstName'
    },
    'beneficiary_last_name': {
        'patterns': [
            r'beneficiary[_\s]?last[_\s]?name', r'family[_\s]?name',
            r'ben[_\s]?lastname', r'ben[_\s]?familyname'
        ],
        'mapping': 'beneficiary.Beneficiary.beneficiaryLastName'
    },
    'attorney_last_name': {
        'patterns': [r'attorney[_\s]?last[_\s]?name', r'att[_\s]?lastname'],
        'mapping': 'attorney.attorneyInfo.lastName'
    },
    'address_street': {
        'patterns': [r'street[_\s]?number[_\s]?and[_\s]?name', r'address[_\s]?street'],
        'mapping': 'address.addressStreet'
    },
    'ssn': {
        'patterns': [r'social[_\s]?security[_\s]?number', r'ssn', r'ussocialssn'],
        'mapping': 'beneficiary.Beneficiary.beneficiarySsn'
    },
    'alien_number': {
        'patterns': [r'alien[_\s]?number', r'a[\-\s]?number', r'dbalien'],
        'mapping': 'beneficiary.Beneficiary.alienNumber'
    }
}

FIELD_TYPES = {
    'TextBox': ['text', 'name', 'address', 'title', 'number', 'email', 'phone'],
    'CheckBox': ['checkbox', 'check', 'yes/no', 'option'],
    'Date': ['date', 'dob', 'birth', 'expiry', 'issue'],
    'RadioButton': ['radio', 'select one', 'choice'],
    'DropDown': ['dropdown', 'select', 'list'],
    'Signature': ['signature', 'sign'],
    'MultipleBox': ['multiple', 'list', 'array']
}

def extract_pdf_fields(pdf_file) -> List[Dict[str, Any]]:
    """Extract form fields from PDF"""
    fields = []
    try:
        pdf_reader = PdfReader(pdf_file)
        
        # Try to get form fields
        if '/AcroForm' in pdf_reader.trailer['/Root']:
            acroform = pdf_reader.trailer['/Root']['/AcroForm']
            if '/Fields' in acroform:
                for field_ref in acroform['/Fields']:
                    field = field_ref.get_object()
                    field_info = extract_field_info(field)
                    if field_info:
                        fields.append(field_info)
        
        # If no form fields, extract text and identify potential fields
        if not fields:
            for page_num, page in enumerate(pdf_reader.pages):
                text = page.extract_text()
                potential_fields = extract_potential_fields(text, page_num)
                fields.extend(potential_fields)
                
    except Exception as e:
        st.error(f"Error extracting PDF fields: {str(e)}")
    
    return fields

def extract_field_info(field_obj) -> Optional[Dict[str, Any]]:
    """Extract information from a PDF field object"""
    try:
        field_info = {
            'name': '',
            'type': 'TextBox',
            'value': '',
            'required': False,
            'page': 0
        }
        
        # Get field name
        if '/T' in field_obj:
            field_info['name'] = field_obj['/T']
        
        # Get field type
        if '/FT' in field_obj:
            field_type = field_obj['/FT']
            if field_type == '/Tx':
                field_info['type'] = 'TextBox'
            elif field_type == '/Ch':
                field_info['type'] = 'DropDown'
            elif field_type == '/Btn':
                if '/Ff' in field_obj and field_obj['/Ff'] & 0x10000:
                    field_info['type'] = 'RadioButton'
                else:
                    field_info['type'] = 'CheckBox'
            elif field_type == '/Sig':
                field_info['type'] = 'Signature'
        
        # Get field value
        if '/V' in field_obj:
            field_info['value'] = str(field_obj['/V'])
        
        # Check if required
        if '/Ff' in field_obj and field_obj['/Ff'] & 0x2:
            field_info['required'] = True
            
        return field_info
    except:
        return None

def extract_potential_fields(text: str, page_num: int) -> List[Dict[str, Any]]:
    """Extract potential form fields from text"""
    fields = []
    lines = text.split('\n')
    
    # Patterns to identify form fields
    patterns = [
        (r'(\w+[\s\w]*?):\s*_{3,}', 'TextBox'),  # Field: ____
        (r'(\w+[\s\w]*?):\s*\[\s*\]', 'CheckBox'),  # Field: [ ]
        (r'(\w+[\s\w]*?):\s*\(\s*\)', 'RadioButton'),  # Field: ( )
        (r'Date.*?:\s*(\w+/\w+/\w+)', 'Date'),  # Date fields
        (r'Signature.*?:\s*_{3,}', 'Signature'),  # Signature fields
    ]
    
    for line in lines:
        for pattern, field_type in patterns:
            matches = re.finditer(pattern, line, re.IGNORECASE)
            for match in matches:
                field_name = match.group(1) if match.groups() else match.group(0)
                field_name = re.sub(r'[^\w\s]', '', field_name).strip()
                if field_name:
                    fields.append({
                        'name': field_name,
                        'type': field_type,
                        'value': '',
                        'required': False,
                        'page': page_num
                    })
    
    return fields

def auto_map_field(field_name: str) -> Optional[str]:
    """Automatically map field based on patterns"""
    field_lower = field_name.lower()
    
    for category, info in MAPPING_PATTERNS.items():
        for pattern in info['patterns']:
            if re.search(pattern, field_lower):
                return info['mapping']
    
    return None

def determine_field_type(field_name: str, existing_type: str = 'TextBox') -> str:
    """Determine the most appropriate field type based on field name"""
    field_lower = field_name.lower()
    
    for field_type, keywords in FIELD_TYPES.items():
        for keyword in keywords:
            if keyword in field_lower:
                return field_type
    
    return existing_type

def generate_typescript(form_name: str, mapped_fields: Dict, questionnaire_fields: Dict, 
                       conditional_fields: Dict, default_fields: Dict) -> str:
    """Generate TypeScript file content based on mappings"""
    
    # Organize fields by category
    customer_data = {}
    beneficiary_data = {}
    attorney_data = {}
    case_data = {}
    
    for field_name, mapping in mapped_fields.items():
        field_type = determine_field_type(field_name)
        mapping_str = f"{mapping}:{field_type}"
        
        if mapping.startswith('customer.'):
            customer_data[field_name] = mapping_str
        elif mapping.startswith('beneficiary.') or mapping.startswith('beneficary.'):
            beneficiary_data[field_name] = mapping_str
        elif mapping.startswith('attorney.'):
            attorney_data[field_name] = mapping_str
        elif mapping.startswith('case.'):
            case_data[field_name] = mapping_str
    
    # Build TypeScript content
    ts_content = f"""export const {form_name} = {{
    "formname": "{form_name}",
    "customerData": {json.dumps(customer_data if customer_data else None, indent=8)},
    "beneficiaryData": {json.dumps(beneficiary_data if beneficiary_data else None, indent=8)},
    "attorneyData": {json.dumps(attorney_data if attorney_data else None, indent=8)},
    "caseData": {json.dumps(case_data if case_data else None, indent=8)},
    "questionnaireData": {json.dumps(questionnaire_fields, indent=8)},
    "defaultData": {json.dumps(default_fields, indent=8)},
    "conditionalData": {json.dumps(conditional_fields, indent=8)},
    "pdfName": "{form_name.replace('_', '-')}"
}}"""
    
    return ts_content

# Main UI
st.title("📄 PDF Form Automation System")
st.markdown("---")

# Sidebar for navigation
with st.sidebar:
    st.header("Navigation")
    step = st.radio(
        "Select Step:",
        ["1. Upload PDF", "2. Field Mapping", "3. Questionnaire Setup", "4. Generate TypeScript"]
    )

# Step 1: Upload PDF
if step == "1. Upload PDF":
    st.header("Step 1: Upload PDF Form")
    
    uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")
    
    if uploaded_file is not None:
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.subheader("PDF Information")
            st.write(f"**Filename:** {uploaded_file.name}")
            st.write(f"**Size:** {uploaded_file.size / 1024:.2f} KB")
            
            form_name = st.text_input(
                "Form Name (e.g., I129, G28):",
                value=uploaded_file.name.replace('.pdf', '').upper()
            )
        
        with col2:
            if st.button("Extract Fields", type="primary"):
                with st.spinner("Extracting fields from PDF..."):
                    fields = extract_pdf_fields(uploaded_file)
                    st.session_state.pdf_fields = fields
                    st.session_state.form_name = form_name
                    
                    if fields:
                        st.success(f"✅ Extracted {len(fields)} fields from the PDF!")
                        
                        # Display extracted fields
                        df = pd.DataFrame(fields)
                        st.dataframe(df)
                    else:
                        st.warning("No form fields found in the PDF. Manual field definition may be required.")

# Step 2: Field Mapping
elif step == "2. Field Mapping":
    st.header("Step 2: Field Mapping")
    
    if not st.session_state.pdf_fields:
        st.warning("Please upload a PDF first!")
    else:
        st.subheader(f"Mapping fields for: {st.session_state.get('form_name', 'Unknown Form')}")
        
        # Auto-mapping option
        if st.button("Auto-map Fields"):
            auto_mapped = 0
            for field in st.session_state.pdf_fields:
                field_name = field['name']
                mapping = auto_map_field(field_name)
                if mapping:
                    st.session_state.mapped_fields[field_name] = mapping
                    auto_mapped += 1
            st.success(f"Auto-mapped {auto_mapped} fields!")
        
        # Manual mapping interface
        st.subheader("Manual Field Mapping")
        
        col1, col2, col3 = st.columns([2, 2, 1])
        col1.write("**PDF Field**")
        col2.write("**Database Mapping**")
        col3.write("**Action**")
        
        for field in st.session_state.pdf_fields:
            field_name = field['name']
            col1, col2, col3 = st.columns([2, 2, 1])
            
            with col1:
                st.text(field_name)
            
            with col2:
                current_mapping = st.session_state.mapped_fields.get(field_name, '')
                mapping = st.text_input(
                    "Mapping",
                    value=current_mapping,
                    key=f"map_{field_name}",
                    label_visibility="collapsed"
                )
                if mapping:
                    st.session_state.mapped_fields[field_name] = mapping
            
            with col3:
                if st.button("❓", key=f"quest_{field_name}", help="Add to questionnaire"):
                    st.session_state.questionnaire_fields[field_name] = {
                        'type': field['type'],
                        'required': field.get('required', False)
                    }
                    if field_name in st.session_state.mapped_fields:
                        del st.session_state.mapped_fields[field_name]

# Step 3: Questionnaire Setup
elif step == "3. Questionnaire Setup":
    st.header("Step 3: Questionnaire Setup")
    
    if not st.session_state.questionnaire_fields:
        st.info("No fields added to questionnaire yet. Go back to Field Mapping to add fields.")
    else:
        st.subheader("Questionnaire Fields")
        
        for field_name, field_info in st.session_state.questionnaire_fields.items():
            with st.expander(f"📝 {field_name}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    field_type = st.selectbox(
                        "Field Type",
                        ["TextBox", "CheckBox", "RadioButton", "DropDown", "Date", "MultipleBox"],
                        index=["TextBox", "CheckBox", "RadioButton", "DropDown", "Date", "MultipleBox"].index(
                            field_info.get('type', 'TextBox')
                        ),
                        key=f"type_{field_name}"
                    )
                    
                    required = st.checkbox(
                        "Required",
                        value=field_info.get('required', False),
                        key=f"req_{field_name}"
                    )
                
                with col2:
                    if field_type in ["RadioButton", "DropDown", "CheckBox"]:
                        options = st.text_area(
                            "Options (one per line)",
                            value=field_info.get('options', ''),
                            key=f"opt_{field_name}"
                        )
                        field_info['options'] = options
                    
                    if field_type == "MultipleBox":
                        sub_fields = st.text_area(
                            "Sub-fields (JSON format)",
                            value=field_info.get('sub_fields', '{}'),
                            key=f"sub_{field_name}"
                        )
                        field_info['sub_fields'] = sub_fields
                
                # Update field info
                field_info['type'] = field_type
                field_info['required'] = required
                st.session_state.questionnaire_fields[field_name] = field_info
        
        # Conditional Fields Section
        st.subheader("Conditional Fields")
        
        if st.button("Add Conditional Field"):
            st.session_state.conditional_fields[f"condition_{len(st.session_state.conditional_fields)}"] = {
                "condition": "",
                "conditionTrue": "",
                "conditionFalse": "",
                "conditionType": "TextBox"
            }
        
        for cond_name, cond_info in st.session_state.conditional_fields.items():
            with st.expander(f"⚡ {cond_name}"):
                cond_info['condition'] = st.text_input("Condition", value=cond_info.get('condition', ''))
                cond_info['conditionTrue'] = st.text_input("If True", value=cond_info.get('conditionTrue', ''))
                cond_info['conditionFalse'] = st.text_input("If False", value=cond_info.get('conditionFalse', ''))
                cond_info['conditionType'] = st.selectbox(
                    "Result Type",
                    ["TextBox", "CheckBox", "Value"],
                    index=["TextBox", "CheckBox", "Value"].index(cond_info.get('conditionType', 'TextBox'))
                )

# Step 4: Generate TypeScript
elif step == "4. Generate TypeScript":
    st.header("Step 4: Generate TypeScript File")
    
    if not st.session_state.get('form_name'):
        st.warning("Please complete previous steps first!")
    else:
        form_name = st.session_state.get('form_name', 'Form')
        
        # Default values section
        st.subheader("Default Values")
        default_fields = {}
        
        col1, col2 = st.columns(2)
        with col1:
            default_key = st.text_input("Field Name")
        with col2:
            default_value = st.text_input("Default Value")
        
        if st.button("Add Default"):
            if default_key and default_value:
                default_fields[default_key] = f"{default_value}:CheckBox"
        
        # Generate TypeScript
        if st.button("Generate TypeScript", type="primary"):
            ts_content = generate_typescript(
                form_name,
                st.session_state.mapped_fields,
                st.session_state.questionnaire_fields,
                st.session_state.conditional_fields,
                default_fields
            )
            
            st.subheader("Generated TypeScript")
            st.code(ts_content, language="typescript")
            
            # Download button
            st.download_button(
                label="Download TypeScript File",
                data=ts_content,
                file_name=f"{form_name}.ts",
                mime="text/plain"
            )
        
        # Summary
        with st.expander("📊 Mapping Summary"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Mapped Fields", len(st.session_state.mapped_fields))
            with col2:
                st.metric("Questionnaire Fields", len(st.session_state.questionnaire_fields))
            with col3:
                st.metric("Conditional Fields", len(st.session_state.conditional_fields))
            
            # Show all mappings
            if st.session_state.mapped_fields:
                st.subheader("Field Mappings")
                for field, mapping in st.session_state.mapped_fields.items():
                    st.text(f"{field} → {mapping}")

# Footer
st.markdown("---")
st.markdown("### 💡 Tips")
st.markdown("""
- **Auto-mapping** uses pattern matching to identify common fields
- **Questionnaire fields** are for data not stored in the database
- **Conditional fields** allow dynamic form behavior
- **Generated TypeScript** follows your existing format structure
""")
