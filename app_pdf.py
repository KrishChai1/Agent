import streamlit as st
import json
import re
from datetime import datetime
import pandas as pd
from typing import Dict, List, Any, Optional
import io

# Try different PDF libraries
try:
    from PyPDF2 import PdfReader
    pdf_library = "PyPDF2"
except ImportError:
    try:
        import pypdf
        PdfReader = pypdf.PdfReader
        pdf_library = "pypdf"
    except ImportError:
        try:
            import fitz  # PyMuPDF
            pdf_library = "pymupdf"
        except ImportError:
            pdf_library = None

# Page configuration
st.set_page_config(
    page_title="PDF Form Automation System",
    page_icon="📄",
    layout="wide"
)

# Check for PDF library
if pdf_library is None:
    st.error("""
    No PDF processing library found. Please install one of the following:
    - `pip install PyPDF2`
    - `pip install pypdf`
    - `pip install PyMuPDF`
    """)
    st.stop()

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
    'customer_tax_id': {
        'patterns': [r'ein', r'fein', r'tax[_\s]?id', r'employer[_\s]?id'],
        'mapping': 'customer.customer_tax_id'
    },
    'signatory_first_name': {
        'patterns': [r'signatory[_\s]?first[_\s]?name', r'contact[_\s]?first[_\s]?name'],
        'mapping': 'customer.signatory_first_name'
    },
    'signatory_last_name': {
        'patterns': [r'signatory[_\s]?last[_\s]?name', r'contact[_\s]?last[_\s]?name'],
        'mapping': 'customer.signatory_last_name'
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
    'beneficiary_dob': {
        'patterns': [r'date[_\s]?of[_\s]?birth', r'birth[_\s]?date', r'dob'],
        'mapping': 'beneficiary.Beneficiary.beneficiaryDateOfBirth'
    },
    'attorney_last_name': {
        'patterns': [r'attorney[_\s]?last[_\s]?name', r'att[_\s]?lastname'],
        'mapping': 'attorney.attorneyInfo.lastName'
    },
    'attorney_first_name': {
        'patterns': [r'attorney[_\s]?first[_\s]?name', r'att[_\s]?firstname'],
        'mapping': 'attorney.attorneyInfo.firstName'
    },
    'address_street': {
        'patterns': [r'street[_\s]?number[_\s]?and[_\s]?name', r'address[_\s]?street', r'street[_\s]?address'],
        'mapping': 'address.addressStreet'
    },
    'ssn': {
        'patterns': [r'social[_\s]?security[_\s]?number', r'ssn', r'ussocialssn'],
        'mapping': 'beneficiary.Beneficiary.beneficiarySsn'
    },
    'alien_number': {
        'patterns': [r'alien[_\s]?number', r'a[\-\s]?number', r'dbalien'],
        'mapping': 'beneficiary.Beneficiary.alienNumber'
    },
    'i94_number': {
        'patterns': [r'i[\-\s]?94[_\s]?number', r'arrival[_\s]?number'],
        'mapping': 'beneficiary.I94Details.I94.i94Number'
    },
    'passport_number': {
        'patterns': [r'passport[_\s]?number', r'passport[\s]?#'],
        'mapping': 'beneficiary.PassportDetails.Passport.passportNumber'
    }
}

FIELD_TYPES = {
    'TextBox': ['text', 'name', 'address', 'title', 'number', 'email', 'phone'],
    'CheckBox': ['checkbox', 'check', 'yes/no', 'option', 'select'],
    'Date': ['date', 'dob', 'birth', 'expiry', 'issue', 'mm/dd/yyyy'],
    'RadioButton': ['radio', 'select one', 'choice'],
    'DropDown': ['dropdown', 'select', 'list'],
    'Signature': ['signature', 'sign'],
    'MultipleBox': ['multiple', 'list', 'array']
}

def extract_pdf_fields_pypdf(pdf_file) -> List[Dict[str, Any]]:
    """Extract form fields from PDF using PyPDF2/pypdf"""
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

def extract_pdf_fields_pymupdf(pdf_file) -> List[Dict[str, Any]]:
    """Extract form fields from PDF using PyMuPDF"""
    fields = []
    try:
        import fitz
        
        # Save uploaded file to bytes
        pdf_bytes = pdf_file.read()
        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        for page_num in range(len(pdf_document)):
            page = pdf_document[page_num]
            text = page.get_text()
            potential_fields = extract_potential_fields(text, page_num)
            fields.extend(potential_fields)
            
        pdf_document.close()
        
    except Exception as e:
        st.error(f"Error extracting PDF fields with PyMuPDF: {str(e)}")
    
    return fields

def extract_pdf_fields(pdf_file) -> List[Dict[str, Any]]:
    """Extract form fields from PDF using available library"""
    if pdf_library in ["PyPDF2", "pypdf"]:
        return extract_pdf_fields_pypdf(pdf_file)
    elif pdf_library == "pymupdf":
        return extract_pdf_fields_pymupdf(pdf_file)
    else:
        return []

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
            field_info['name'] = str(field_obj['/T'])
        
        # Get field type
        if '/FT' in field_obj:
            field_type = field_obj['/FT']
            if str(field_type) == '/Tx':
                field_info['type'] = 'TextBox'
            elif str(field_type) == '/Ch':
                field_info['type'] = 'DropDown'
            elif str(field_type) == '/Btn':
                if '/Ff' in field_obj and field_obj['/Ff'] & 0x10000:
                    field_info['type'] = 'RadioButton'
                else:
                    field_info['type'] = 'CheckBox'
            elif str(field_type) == '/Sig':
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
        (r'Date.*?:\s*\(mm/dd/yyyy\)', 'Date'),  # Date fields
        (r'Signature.*?:\s*_{3,}', 'Signature'),  # Signature fields
        (r'(\w+[\s\w]*?)\s+Number', 'TextBox'),  # Number fields
    ]
    
    # Look for common form field indicators
    for i, line in enumerate(lines):
        # Skip empty lines
        if not line.strip():
            continue
            
        # Check each pattern
        for pattern, field_type in patterns:
            matches = re.finditer(pattern, line, re.IGNORECASE)
            for match in matches:
                field_name = match.group(1) if match.groups() else match.group(0)
                field_name = re.sub(r'[^\w\s]', '', field_name).strip()
                if field_name and len(field_name) > 2:  # Skip very short matches
                    fields.append({
                        'name': field_name,
                        'type': field_type,
                        'value': '',
                        'required': False,
                        'page': page_num + 1  # 1-based page numbering
                    })
        
        # Look for checkbox patterns
        if '☐' in line or '□' in line or '[ ]' in line:
            # Extract the label before the checkbox
            parts = re.split(r'[☐□\[\]]', line)
            if parts and parts[0].strip():
                field_name = parts[0].strip()
                if len(field_name) > 2:
                    fields.append({
                        'name': field_name,
                        'type': 'CheckBox',
                        'value': '',
                        'required': False,
                        'page': page_num + 1
                    })
    
    # Remove duplicates
    unique_fields = []
    seen = set()
    for field in fields:
        field_key = f"{field['name']}_{field['page']}"
        if field_key not in seen:
            seen.add(field_key)
            unique_fields.append(field)
    
    return unique_fields

def auto_map_field(field_name: str) -> Optional[str]:
    """Automatically map field based on patterns"""
    field_lower = field_name.lower().replace(' ', '_')
    
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
    
    # Format questionnaire data
    formatted_questionnaire = {}
    for field_name, field_info in questionnaire_fields.items():
        field_key = field_name.replace(' ', '_').lower()
        formatted_questionnaire[field_key] = f"{field_key}:{field_info.get('type', 'TextBox')}"
    
    # Build TypeScript content
    ts_content = f"""export const {form_name} = {{
    "formname": "{form_name}",
    "customerData": {json.dumps(customer_data if customer_data else None, indent=8)},
    "beneficiaryData": {json.dumps(beneficiary_data if beneficiary_data else None, indent=8)},
    "attorneyData": {json.dumps(attorney_data if attorney_data else None, indent=8)},
    "caseData": {json.dumps(case_data if case_data else None, indent=8)},
    "questionnaireData": {json.dumps(formatted_questionnaire, indent=8)},
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
    
    st.markdown("---")
    st.markdown("### Current Session")
    st.info(f"Form: {st.session_state.get('form_name', 'Not set')}")
    st.info(f"Total Fields: {len(st.session_state.pdf_fields)}")
    st.info(f"Mapped: {len(st.session_state.mapped_fields)}")
    st.info(f"Questionnaire: {len(st.session_state.questionnaire_fields)}")

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
            st.write(f"**PDF Library:** {pdf_library}")
            
            form_name = st.text_input(
                "Form Name (e.g., I129, G28):",
                value=uploaded_file.name.replace('.pdf', '').replace('-', '_').upper()
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
                        st.dataframe(df, height=400)
                        
                        # Show field summary
                        st.subheader("Field Summary")
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            field_types = df['type'].value_counts()
                            st.write("**Field Types:**")
                            for ft, count in field_types.items():
                                st.write(f"- {ft}: {count}")
                        with col2:
                            st.write("**Pages:**")
                            pages = df['page'].value_counts().sort_index()
                            for page, count in pages.items():
                                st.write(f"- Page {page}: {count} fields")
                        with col3:
                            required_count = df['required'].sum()
                            st.write("**Required Fields:**")
                            st.write(f"- Required: {required_count}")
                            st.write(f"- Optional: {len(fields) - required_count}")
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
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Auto-map Common Fields", type="primary"):
                auto_mapped = 0
                for field in st.session_state.pdf_fields:
                    field_name = field['name']
                    if field_name not in st.session_state.mapped_fields:
                        mapping = auto_map_field(field_name)
                        if mapping:
                            st.session_state.mapped_fields[field_name] = mapping
                            auto_mapped += 1
                st.success(f"Auto-mapped {auto_mapped} fields!")
        
        with col2:
            if st.button("📋 Clear All Mappings"):
                st.session_state.mapped_fields = {}
                st.session_state.questionnaire_fields = {}
                st.rerun()
        
        # Manual mapping interface
        st.subheader("Manual Field Mapping")
        
        # Filter options
        filter_col1, filter_col2 = st.columns(2)
        with filter_col1:
            filter_unmapped = st.checkbox("Show only unmapped fields", value=False)
        with filter_col2:
            filter_type = st.selectbox("Filter by type", ["All"] + list(set(f['type'] for f in st.session_state.pdf_fields)))
        
        # Headers
        col1, col2, col3, col4 = st.columns([3, 3, 1, 1])
        col1.write("**PDF Field**")
        col2.write("**Database Mapping**")
        col3.write("**Type**")
        col4.write("**Actions**")
        
        for field in st.session_state.pdf_fields:
            field_name = field['name']
            
            # Apply filters
            if filter_unmapped and (field_name in st.session_state.mapped_fields or field_name in st.session_state.questionnaire_fields):
                continue
            if filter_type != "All" and field['type'] != filter_type:
                continue
            
            col1, col2, col3, col4 = st.columns([3, 3, 1, 1])
            
            with col1:
                st.text(f"{field_name}")
                if field.get('required'):
                    st.caption("*Required")
            
            with col2:
                current_mapping = st.session_state.mapped_fields.get(field_name, '')
                
                # Provide dropdown with common mappings
                common_mappings = [
                    "",
                    "customer.customer_name",
                    "customer.customer_tax_id",
                    "customer.signatory_first_name",
                    "customer.signatory_last_name",
                    "beneficiary.Beneficiary.beneficiaryFirstName",
                    "beneficiary.Beneficiary.beneficiaryLastName",
                    "beneficiary.Beneficiary.beneficiaryDateOfBirth",
                    "attorney.attorneyInfo.firstName",
                    "attorney.attorneyInfo.lastName",
                    "Custom..."
                ]
                
                selected = st.selectbox(
                    "Select mapping",
                    common_mappings,
                    index=common_mappings.index(current_mapping) if current_mapping in common_mappings else 0,
                    key=f"select_{field_name}",
                    label_visibility="collapsed"
                )
                
                if selected == "Custom...":
                    mapping = st.text_input(
                        "Custom mapping",
                        value=current_mapping if current_mapping not in common_mappings else "",
                        key=f"custom_{field_name}",
                        label_visibility="collapsed"
                    )
                else:
                    mapping = selected
                
                if mapping:
                    st.session_state.mapped_fields[field_name] = mapping
                    if field_name in st.session_state.questionnaire_fields:
                        del st.session_state.questionnaire_fields[field_name]
                elif field_name in st.session_state.mapped_fields:
                    del st.session_state.mapped_fields[field_name]
            
            with col3:
                st.caption(field['type'])
            
            with col4:
                if st.button("📝", key=f"quest_{field_name}", help="Add to questionnaire"):
                    st.session_state.questionnaire_fields[field_name] = {
                        'type': field['type'],
                        'required': field.get('required', False)
                    }
                    if field_name in st.session_state.mapped_fields:
                        del st.session_state.mapped_fields[field_name]
                    st.rerun()

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
                    
                    # Update field info
                    field_info['type'] = field_type
                    field_info['required'] = required
                
                with col2:
                    if field_type in ["RadioButton", "DropDown"]:
                        options = st.text_area(
                            "Options (one per line)",
                            value=field_info.get('options', ''),
                            key=f"opt_{field_name}",
                            height=100
                        )
                        field_info['options'] = options
                    
                    if field_type == "CheckBox":
                        default_checked = st.checkbox(
                            "Default Checked",
                            value=field_info.get('default_checked', False),
                            key=f"def_{field_name}"
                        )
                        field_info['default_checked'] = default_checked
                    
                    if field_type == "MultipleBox":
                        sub_fields = st.text_area(
                            "Sub-fields (JSON format)",
                            value=field_info.get('sub_fields', '{\n  "field1": "TextBox",\n  "field2": "Date"\n}'),
                            key=f"sub_{field_name}",
                            height=150
                        )
                        try:
                            json.loads(sub_fields)
                            field_info['sub_fields'] = sub_fields
                        except:
                            st.error("Invalid JSON format")
                
                st.session_state.questionnaire_fields[field_name] = field_info
                
                # Remove button
                if st.button(f"Remove {field_name}", key=f"remove_{field_name}"):
                    del st.session_state.questionnaire_fields[field_name]
                    st.rerun()
        
        # Conditional Fields Section
        st.subheader("Conditional Fields")
        st.caption("Define fields that appear/change based on conditions")
        
        # Add new conditional field
        with st.expander("➕ Add New Conditional Field"):
            col1, col2 = st.columns(2)
            with col1:
                cond_name = st.text_input("Conditional Field Name", key="new_cond_name")
                condition = st.text_input("Condition (e.g., case.caseType==H1B)", key="new_condition")
                condition_type = st.selectbox("Result Type", ["TextBox", "CheckBox", "Value"], key="new_cond_type")
            with col2:
                condition_true = st.text_input("Value if True", key="new_cond_true")
                condition_false = st.text_input("Value if False", key="new_cond_false")
                
            if st.button("Add Conditional Field"):
                if cond_name and condition:
                    st.session_state.conditional_fields[cond_name] = {
                        "condition": condition,
                        "conditionTrue": condition_true,
                        "conditionFalse": condition_false,
                        "conditionType": condition_type
                    }
                    st.rerun()
        
        # Display existing conditional fields
        for cond_name, cond_info in st.session_state.conditional_fields.items():
            with st.expander(f"⚡ {cond_name}"):
                col1, col2 = st.columns(2)
                with col1:
                    cond_info['condition'] = st.text_input(
                        "Condition", 
                        value=cond_info.get('condition', ''),
                        key=f"cond_{cond_name}"
                    )
                    cond_info['conditionType'] = st.selectbox(
                        "Result Type",
                        ["TextBox", "CheckBox", "Value"],
                        index=["TextBox", "CheckBox", "Value"].index(cond_info.get('conditionType', 'TextBox')),
                        key=f"cond_type_{cond_name}"
                    )
                with col2:
                    cond_info['conditionTrue'] = st.text_input(
                        "If True", 
                        value=cond_info.get('conditionTrue', ''),
                        key=f"true_{cond_name}"
                    )
                    cond_info['conditionFalse'] = st.text_input(
                        "If False", 
                        value=cond_info.get('conditionFalse', ''),
                        key=f"false_{cond_name}"
                    )
                
                if st.button(f"Remove {cond_name}", key=f"remove_cond_{cond_name}"):
                    del st.session_state.conditional_fields[cond_name]
                    st.rerun()

# Step 4: Generate TypeScript
elif step == "4. Generate TypeScript":
    st.header("Step 4: Generate TypeScript File")
    
    if not st.session_state.get('form_name'):
        st.warning("Please complete previous steps first!")
    else:
        form_name = st.session_state.get('form_name', 'Form')
        
        # Default values section
        st.subheader("Default Values")
        st.caption("Define default values for form fields")
        
        # Add existing default values if any
        if 'default_fields' not in st.session_state:
            st.session_state.default_fields = {}
        
        with st.expander("➕ Add Default Value"):
            col1, col2, col3 = st.columns([3, 3, 1])
            with col1:
                default_key = st.text_input("Field Name", key="new_default_key")
            with col2:
                default_value = st.text_input("Default Value", key="new_default_value")
            with col3:
                default_type = st.selectbox("Type", ["TextBox", "CheckBox"], key="new_default_type")
            
            if st.button("Add Default"):
                if default_key and default_value:
                    st.session_state.default_fields[default_key] = f"{default_value}:{default_type}"
                    st.rerun()
        
        # Display existing defaults
        if st.session_state.default_fields:
            st.write("**Current Default Values:**")
            for key, value in st.session_state.default_fields.items():
                col1, col2, col3 = st.columns([3, 3, 1])
                with col1:
                    st.text(key)
                with col2:
                    st.text(value)
                with col3:
                    if st.button("❌", key=f"del_def_{key}"):
                        del st.session_state.default_fields[key]
                        st.rerun()
        
        # Summary before generation
        st.subheader("📊 Form Summary")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Fields", len(st.session_state.pdf_fields))
        with col2:
            st.metric("Mapped Fields", len(st.session_state.mapped_fields))
        with col3:
            st.metric("Questionnaire Fields", len(st.session_state.questionnaire_fields))
        with col4:
            st.metric("Conditional Fields", len(st.session_state.conditional_fields))
        
        # Generate TypeScript
        if st.button("🚀 Generate TypeScript", type="primary"):
            ts_content = generate_typescript(
                form_name,
                st.session_state.mapped_fields,
                st.session_state.questionnaire_fields,
                st.session_state.conditional_fields,
                st.session_state.get('default_fields', {})
            )
            
            st.subheader("Generated TypeScript")
            st.code(ts_content, language="typescript")
            
            # Download button
            st.download_button(
                label="📥 Download TypeScript File",
                data=ts_content,
                file_name=f"{form_name}.ts",
                mime="text/plain"
            )
        
        # Show detailed mappings
        with st.expander("📋 View All Mappings"):
            if st.session_state.mapped_fields:
                st.subheader("Field Mappings")
                mapping_df = pd.DataFrame([
                    {"PDF Field": field, "Database Mapping": mapping}
                    for field, mapping in st.session_state.mapped_fields.items()
                ])
                st.dataframe(mapping_df)
            
            if st.session_state.questionnaire_fields:
                st.subheader("Questionnaire Fields")
                quest_df = pd.DataFrame([
                    {"Field": field, "Type": info.get('type', 'TextBox'), "Required": info.get('required', False)}
                    for field, info in st.session_state.questionnaire_fields.items()
                ])
                st.dataframe(quest_df)

# Footer
st.markdown("---")
st.markdown("### 💡 Tips")
st.markdown("""
- **Auto-mapping** uses pattern matching to identify common fields (customer names, beneficiary info, etc.)
- **Questionnaire fields** are for data not stored in the database
- **Conditional fields** allow dynamic form behavior based on other field values
- **Generated TypeScript** follows your existing format structure
- Use the sidebar to track your progress through the workflow
""")
