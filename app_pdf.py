import streamlit as st
import json
import re
from datetime import datetime
import pandas as pd
from typing import Dict, List, Any, Optional
import io

# Try to import PDF library
try:
    import PyPDF2
    from PyPDF2 import PdfReader
    PDF_AVAILABLE = True
except ImportError:
    try:
        import pypdf as PyPDF2
        from pypdf import PdfReader
        PDF_AVAILABLE = True
    except ImportError:
        PDF_AVAILABLE = False

# Page configuration
st.set_page_config(
    page_title="PDF Form Automation System",
    page_icon="📄",
    layout="wide"
)

# Check if PDF library is available
if not PDF_AVAILABLE:
    st.error("PDF processing library not found. Please install PyPDF2 or pypdf:")
    st.code("pip install PyPDF2")
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
if 'default_fields' not in st.session_state:
    st.session_state.default_fields = {}

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
    'customer_signatory_first': {
        'patterns': [r'signatory[_\s]?first[_\s]?name', r'authorized[_\s]?official'],
        'mapping': 'customer.signatory_first_name'
    },
    'customer_signatory_last': {
        'patterns': [r'signatory[_\s]?last[_\s]?name'],
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
    'beneficiary_middle_name': {
        'patterns': [r'beneficiary[_\s]?middle[_\s]?name', r'ben[_\s]?middlename'],
        'mapping': 'beneficiary.Beneficiary.beneficiaryMiddleName'
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
    'address_city': {
        'patterns': [r'city', r'address[_\s]?city'],
        'mapping': 'address.addressCity'
    },
    'address_state': {
        'patterns': [r'state', r'address[_\s]?state'],
        'mapping': 'address.addressState'
    },
    'address_zip': {
        'patterns': [r'zip[_\s]?code', r'postal[_\s]?code', r'address[_\s]?zip'],
        'mapping': 'address.addressZip'
    },
    'ssn': {
        'patterns': [r'social[_\s]?security[_\s]?number', r'ssn', r'ussocialssn'],
        'mapping': 'beneficiary.Beneficiary.beneficiarySsn'
    },
    'alien_number': {
        'patterns': [r'alien[_\s]?number', r'a[\-\s]?number', r'dbalien'],
        'mapping': 'beneficiary.Beneficiary.alienNumber'
    },
    'date_of_birth': {
        'patterns': [r'date[_\s]?of[_\s]?birth', r'dob', r'birth[_\s]?date'],
        'mapping': 'beneficiary.Beneficiary.beneficiaryDateOfBirth'
    },
    'i94_number': {
        'patterns': [r'i[\-\s]?94[_\s]?number', r'arrival[_\s]?number'],
        'mapping': 'beneficiary.I94Details.I94.i94Number'
    },
    'passport_number': {
        'patterns': [r'passport[_\s]?number', r'travel[_\s]?document'],
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

def extract_pdf_fields(pdf_file) -> List[Dict[str, Any]]:
    """Extract form fields from PDF"""
    fields = []
    try:
        pdf_reader = PdfReader(pdf_file)
        
        # Try to get form fields
        if hasattr(pdf_reader, 'get_form_text_fields'):
            form_fields = pdf_reader.get_form_text_fields()
            if form_fields:
                for field_name, field_value in form_fields.items():
                    fields.append({
                        'name': field_name,
                        'type': 'TextBox',
                        'value': field_value or '',
                        'required': False,
                        'page': 0
                    })
        
        # Try another method to get fields
        if not fields and hasattr(pdf_reader, 'get_fields'):
            pdf_fields = pdf_reader.get_fields()
            if pdf_fields:
                for field_name, field_obj in pdf_fields.items():
                    field_type = 'TextBox'
                    if isinstance(field_obj, dict):
                        if field_obj.get('/FT') == '/Btn':
                            field_type = 'CheckBox'
                        elif field_obj.get('/FT') == '/Ch':
                            field_type = 'DropDown'
                    
                    fields.append({
                        'name': field_name,
                        'type': field_type,
                        'value': '',
                        'required': False,
                        'page': 0
                    })
        
        # If still no fields, extract text and identify potential fields
        if not fields:
            for page_num, page in enumerate(pdf_reader.pages):
                text = page.extract_text()
                potential_fields = extract_potential_fields(text, page_num)
                fields.extend(potential_fields)
                
    except Exception as e:
        st.error(f"Error extracting PDF fields: {str(e)}")
        # Fallback: manual field entry
        st.info("Unable to extract fields automatically. You can manually add fields.")
    
    return fields

def extract_potential_fields(text: str, page_num: int) -> List[Dict[str, Any]]:
    """Extract potential form fields from text"""
    fields = []
    seen_fields = set()
    
    # Clean text
    text = re.sub(r'\s+', ' ', text)
    
    # Patterns to identify form fields
    patterns = [
        # Field Name followed by underscores or boxes
        (r'([A-Za-z][A-Za-z\s]{2,30})(?:\s*:?\s*)(?:_{3,}|\[[\s\x00]*\]|\([\s\x00]*\))', 'TextBox'),
        # Item Number patterns (like "1a.", "2.b.")
        (r'(\d+\.?[a-z]?\.?\s+[A-Za-z][A-Za-z\s]{2,30})(?:\s*:?\s*)(?:_{3,}|\[[\s\x00]*\])', 'TextBox'),
        # Checkbox patterns
        (r'([A-Za-z][A-Za-z\s]{2,30})\s*\[[\s\x00]*\]', 'CheckBox'),
        # Radio button patterns
        (r'([A-Za-z][A-Za-z\s]{2,30})\s*\([\s\x00]*\)', 'RadioButton'),
        # Date patterns
        (r'(Date[A-Za-z\s]*|DOB|Birth\s*Date)(?:\s*:?\s*)(?:_{3,}|[\s\x00]*)', 'Date'),
        # Signature patterns
        (r'(Signature[A-Za-z\s]*)(?:\s*:?\s*)_{3,}', 'Signature'),
    ]
    
    for pattern, field_type in patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            field_name = match.group(1).strip()
            # Clean field name
            field_name = re.sub(r'\s+', ' ', field_name)
            field_name = re.sub(r'[^\w\s\-.]', '', field_name).strip()
            
            if field_name and len(field_name) > 2 and field_name not in seen_fields:
                seen_fields.add(field_name)
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
    field_lower = re.sub(r'[^\w\s]', ' ', field_lower)
    field_lower = re.sub(r'\s+', ' ', field_lower).strip()
    
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
    
    # Clean form name
    form_name_clean = re.sub(r'[^\w]', '', form_name)
    
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
        field_key = re.sub(r'[^\w]', '_', field_name)
        formatted_questionnaire[field_key] = f"{field_key}:{field_info.get('type', 'TextBox')}"
    
    # Build TypeScript content
    ts_content = f"""export const {form_name_clean} = {{
    "formname": "{form_name_clean}",
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
                value=uploaded_file.name.replace('.pdf', '').replace('-', '').replace(' ', '_').upper()
            )
        
        with col2:
            if st.button("Extract Fields", type="primary"):
                with st.spinner("Extracting fields from PDF..."):
                    fields = extract_pdf_fields(uploaded_file)
                    
                    # If no fields extracted, allow manual entry
                    if not fields:
                        st.warning("No fields could be extracted automatically.")
                        if st.checkbox("Add fields manually"):
                            num_fields = st.number_input("Number of fields to add:", min_value=1, max_value=50, value=5)
                            for i in range(num_fields):
                                col_name, col_type = st.columns(2)
                                with col_name:
                                    field_name = st.text_input(f"Field {i+1} name:", key=f"manual_field_{i}")
                                with col_type:
                                    field_type = st.selectbox(
                                        f"Field {i+1} type:",
                                        ["TextBox", "CheckBox", "Date", "RadioButton", "DropDown", "Signature"],
                                        key=f"manual_type_{i}"
                                    )
                                if field_name:
                                    fields.append({
                                        'name': field_name,
                                        'type': field_type,
                                        'value': '',
                                        'required': False,
                                        'page': 0
                                    })
                    
                    st.session_state.pdf_fields = fields
                    st.session_state.form_name = form_name
                    
                    if fields:
                        st.success(f"✅ Found {len(fields)} fields!")
                        
                        # Display extracted fields
                        df = pd.DataFrame(fields)
                        st.dataframe(df, use_container_width=True)

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
            if st.button("🔄 Auto-map Fields", type="primary", use_container_width=True):
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
            if st.button("🗑️ Clear All Mappings", use_container_width=True):
                st.session_state.mapped_fields = {}
                st.success("All mappings cleared!")
        
        # Manual mapping interface
        st.subheader("Field Mappings")
        
        for field in st.session_state.pdf_fields:
            field_name = field['name']
            
            col1, col2, col3, col4 = st.columns([3, 3, 1, 1])
            
            with col1:
                st.text_input(
                    "PDF Field",
                    value=field_name,
                    disabled=True,
                    key=f"display_{field_name}"
                )
            
            with col2:
                current_mapping = st.session_state.mapped_fields.get(field_name, '')
                mapping = st.text_input(
                    "Database Mapping",
                    value=current_mapping,
                    key=f"map_{field_name}",
                    placeholder="e.g., customer.customer_name"
                )
                if mapping:
                    st.session_state.mapped_fields[field_name] = mapping
                elif field_name in st.session_state.mapped_fields:
                    del st.session_state.mapped_fields[field_name]
            
            with col3:
                if st.button("❓", key=f"quest_{field_name}", help="Add to questionnaire", use_container_width=True):
                    st.session_state.questionnaire_fields[field_name] = {
                        'type': field['type'],
                        'required': field.get('required', False)
                    }
                    if field_name in st.session_state.mapped_fields:
                        del st.session_state.mapped_fields[field_name]
                    st.success(f"Added {field_name} to questionnaire!")
            
            with col4:
                if field_name in st.session_state.mapped_fields:
                    st.success("✅")
                elif field_name in st.session_state.questionnaire_fields:
                    st.info("❓")
                else:
                    st.error("❌")

# Step 3: Questionnaire Setup
elif step == "3. Questionnaire Setup":
    st.header("Step 3: Questionnaire Setup")
    
    if not st.session_state.questionnaire_fields:
        st.info("No fields added to questionnaire yet. Go back to Field Mapping to add fields.")
    else:
        st.subheader("Questionnaire Fields")
        
        # Add new questionnaire field manually
        with st.expander("➕ Add New Questionnaire Field"):
            col1, col2 = st.columns(2)
            with col1:
                new_field_name = st.text_input("Field Name")
            with col2:
                new_field_type = st.selectbox(
                    "Field Type",
                    ["TextBox", "CheckBox", "RadioButton", "DropDown", "Date", "MultipleBox"]
                )
            
            if st.button("Add Field") and new_field_name:
                st.session_state.questionnaire_fields[new_field_name] = {
                    'type': new_field_type,
                    'required': False
                }
                st.success(f"Added {new_field_name} to questionnaire!")
        
        # Edit existing questionnaire fields
        for field_name, field_info in list(st.session_state.questionnaire_fields.items()):
            with st.expander(f"📝 {field_name}"):
                col1, col2, col3 = st.columns([2, 2, 1])
                
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
                            key=f"opt_{field_name}",
                            height=100
                        )
                        field_info['options'] = options
                    
                    if field_type == "MultipleBox":
                        sub_fields = st.text_area(
                            "Sub-fields (one per line)",
                            value=field_info.get('sub_fields', ''),
                            key=f"sub_{field_name}",
                            height=100
                        )
                        field_info['sub_fields'] = sub_fields
                
                with col3:
                    if st.button("🗑️ Remove", key=f"remove_{field_name}"):
                        del st.session_state.questionnaire_fields[field_name]
                        st.rerun()
                
                # Update field info
                field_info['type'] = field_type
                field_info['required'] = required
                st.session_state.questionnaire_fields[field_name] = field_info
        
        # Conditional Fields Section
        st.subheader("Conditional Fields")
        
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("➕ Add Conditional Field", use_container_width=True):
                cond_name = f"condition_{len(st.session_state.conditional_fields) + 1}"
                st.session_state.conditional_fields[cond_name] = {
                    "condition": "",
                    "conditionTrue": "",
                    "conditionFalse": "",
                    "conditionType": "TextBox"
                }
        
        for cond_name, cond_info in list(st.session_state.conditional_fields.items()):
            with st.expander(f"⚡ {cond_name}"):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    cond_info['condition'] = st.text_input(
                        "Condition (e.g., case.caseType==H1B)",
                        value=cond_info.get('condition', ''),
                        key=f"cond_{cond_name}"
                    )
                    
                    col_true, col_false = st.columns(2)
                    with col_true:
                        cond_info['conditionTrue'] = st.text_input(
                            "If True",
                            value=cond_info.get('conditionTrue', ''),
                            key=f"true_{cond_name}"
                        )
                    with col_false:
                        cond_info['conditionFalse'] = st.text_input(
                            "If False",
                            value=cond_info.get('conditionFalse', ''),
                            key=f"false_{cond_name}"
                        )
                    
                    cond_info['conditionType'] = st.selectbox(
                        "Result Type",
                        ["TextBox", "CheckBox", "Value", "ConditionBox"],
                        index=["TextBox", "CheckBox", "Value", "ConditionBox"].index(
                            cond_info.get('conditionType', 'TextBox')
                        ),
                        key=f"type_cond_{cond_name}"
                    )
                
                with col2:
                    if st.button("🗑️ Remove", key=f"remove_cond_{cond_name}"):
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
        
        col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
        with col1:
            default_key = st.text_input("Field Name", key="default_field_name")
        with col2:
            default_value = st.text_input("Default Value", key="default_field_value")
        with col3:
            default_type = st.selectbox("Type", ["TextBox", "CheckBox"], key="default_field_type")
        with col4:
            if st.button("Add Default", use_container_width=True):
                if default_key and default_value:
                    st.session_state.default_fields[default_key] = f"{default_value}:{default_type}"
                    st.success(f"Added default: {default_key}")
        
        # Display current defaults
        if st.session_state.default_fields:
            st.write("Current default values:")
            for key, value in st.session_state.default_fields.items():
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.text(f"{key} = {value}")
                with col2:
                    if st.button("🗑️", key=f"del_default_{key}"):
                        del st.session_state.default_fields[key]
                        st.rerun()
        
        # Generate TypeScript
        st.markdown("---")
        if st.button("🚀 Generate TypeScript", type="primary", use_container_width=True):
            ts_content = generate_typescript(
                form_name,
                st.session_state.mapped_fields,
                st.session_state.questionnaire_fields,
                st.session_state.conditional_fields,
                st.session_state.default_fields
            )
            
            st.subheader("Generated TypeScript")
            st.code(ts_content, language="typescript")
            
            # Download button
            st.download_button(
                label="📥 Download TypeScript File",
                data=ts_content,
                file_name=f"{form_name}.ts",
                mime="text/plain",
                use_container_width=True
            )
        
        # Summary
        with st.expander("📊 Mapping Summary", expanded=True):
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Mapped Fields", len(st.session_state.mapped_fields))
            with col2:
                st.metric("Questionnaire Fields", len(st.session_state.questionnaire_fields))
            with col3:
                st.metric("Conditional Fields", len(st.session_state.conditional_fields))
            with col4:
                st.metric("Default Values", len(st.session_state.default_fields))
            
            # Show all mappings
            if st.session_state.mapped_fields:
                st.subheader("Field Mappings")
                mapping_df = pd.DataFrame(
                    [(field, mapping) for field, mapping in st.session_state.mapped_fields.items()],
                    columns=["PDF Field", "Database Mapping"]
                )
                st.dataframe(mapping_df, use_container_width=True)

# Footer
st.markdown("---")
with st.expander("💡 Tips & Help"):
    st.markdown("""
    ### How to Use This Tool:
    
    1. **Upload PDF**: Upload your form PDF file
    2. **Extract Fields**: The system will try to extract form fields automatically
    3. **Map Fields**: 
       - Use Auto-map for common fields
       - Manually map fields to database paths (e.g., `customer.customer_name`)
       - Click ❓ to add unmapped fields to questionnaire
    4. **Configure Questionnaire**: Set up field types and options for questionnaire fields
    5. **Generate TypeScript**: Create the final TypeScript file with all mappings
    
    ### Common Mapping Patterns:
    - Customer: `customer.customer_name`, `customer.customer_tax_id`
    - Beneficiary: `beneficiary.Beneficiary.beneficiaryFirstName`
    - Attorney: `attorney.attorneyInfo.lastName`
    - Address: `address.addressStreet`, `address.addressCity`
    
    ### Field Types:
    - **TextBox**: Regular text input
    - **CheckBox**: Yes/No options
    - **Date**: Date fields (mm/dd/yyyy)
    - **RadioButton**: Single selection from options
    - **DropDown**: Dropdown selection
    - **MultipleBox**: Multiple related fields
    """)
