import streamlit as st
import pandas as pd
import json
import re
from typing import Dict, List, Any, Optional
from datetime import datetime
import io
from dataclasses import dataclass, asdict

# Try importing PyPDF2, with fallback options
try:
    import PyPDF2
except ImportError:
    try:
        import pypdf as PyPDF2
    except ImportError:
        st.error("PDF processing library not found. Please install PyPDF2 or pypdf: pip install PyPDF2")
        st.stop()

# Configuration classes
@dataclass
class FormField:
    name: str
    field_type: str
    category: str
    mapping_path: str
    required: bool = False
    validation: Optional[str] = None

@dataclass
class FormConfig:
    form_name: str
    form_type: str
    pdf_name: str
    fields: List[FormField]
    sections: List[str]

class USCISFormProcessor:
    def __init__(self):
        self.known_patterns = {
            'name': ['name', 'first', 'last', 'middle', 'family', 'given'],
            'address': ['address', 'street', 'city', 'state', 'zip', 'country'],
            'date': ['date', 'birth', 'expiry', 'arrival', 'departure'],
            'phone': ['phone', 'telephone', 'mobile', 'cell'],
            'email': ['email', 'mail'],
            'number': ['number', 'receipt', 'alien', 'ssn', 'passport'],
            'checkbox': ['yes', 'no', 'check', 'select'],
            'signature': ['signature', 'sign'],
        }
        
        self.category_mappings = {
            'customer': ['petitioner', 'employer', 'company', 'organization'],
            'beneficiary': ['beneficiary', 'applicant', 'worker', 'employee'],
            'attorney': ['attorney', 'lawyer', 'representative', 'preparer'],
            'case': ['case', 'petition', 'application', 'classification'],
            'questionnaire': ['part', 'section', 'question', 'item']
        }

    def extract_pdf_fields(self, pdf_file) -> List[str]:
        """Extract form fields from PDF"""
        try:
            # Reset file pointer
            pdf_file.seek(0)
            
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            fields = []
            
            # Try to get form fields from AcroForm
            if hasattr(pdf_reader, 'trailer') and "/Root" in pdf_reader.trailer:
                root = pdf_reader.trailer["/Root"]
                if "/AcroForm" in root:
                    acro_form = root["/AcroForm"]
                    if "/Fields" in acro_form:
                        for field in acro_form["/Fields"]:
                            field_obj = field.get_object()
                            if "/T" in field_obj:
                                field_name = field_obj["/T"]
                                fields.append(str(field_name))
            
            # Alternative method: check each page for annotations
            if not fields:
                for page in pdf_reader.pages:
                    if "/Annots" in page:
                        for annot in page["/Annots"]:
                            annot_obj = annot.get_object()
                            if "/T" in annot_obj:
                                field_name = annot_obj["/T"]
                                fields.append(str(field_name))
            
            # Remove duplicates and clean up
            fields = list(set(fields))
            fields = [f for f in fields if f and f.strip()]
            
            return fields
            
        except Exception as e:
            st.error(f"Error extracting PDF fields: {str(e)}")
            # Return some sample fields for demonstration
            return [
                "applicant_last_name", "applicant_first_name", "applicant_middle_name",
                "applicant_address", "applicant_city", "applicant_state", "applicant_zip",
                "applicant_phone", "applicant_email", "applicant_date_of_birth",
                "petitioner_name", "petitioner_address", "attorney_name", "attorney_phone",
                "case_type", "receipt_number", "part_1_question_a", "part_2_item_1"
            ]

    def categorize_field(self, field_name: str) -> str:
        """Categorize field based on name patterns"""
        field_lower = field_name.lower()
        
        for category, keywords in self.category_mappings.items():
            if any(keyword in field_lower for keyword in keywords):
                return category
        
        return 'questionnaire'

    def determine_field_type(self, field_name: str) -> str:
        """Determine field type based on name patterns"""
        field_lower = field_name.lower()
        
        if any(pattern in field_lower for pattern in self.known_patterns['date']):
            return 'date'
        elif any(pattern in field_lower for pattern in self.known_patterns['phone']):
            return 'text'
        elif any(pattern in field_lower for pattern in self.known_patterns['email']):
            return 'text'
        elif any(pattern in field_lower for pattern in ['yes', 'no', 'check', 'select', 'box']):
            return 'checkbox'
        elif 'signature' in field_lower:
            return 'signature'
        elif any(pattern in field_lower for pattern in ['dropdown', 'select', 'option']):
            return 'dropdown'
        else:
            return 'text'

    def generate_mapping_path(self, field_name: str, category: str) -> str:
        """Generate mapping path for the field"""
        field_lower = field_name.lower()
        
        if category == 'customer':
            if 'name' in field_lower:
                if 'first' in field_lower:
                    return 'customer.signatory_first_name'
                elif 'last' in field_lower:
                    return 'customer.signatory_last_name'
                else:
                    return 'customer.customer_name'
            elif 'address' in field_lower:
                if 'street' in field_lower:
                    return 'customer.address_street'
                elif 'city' in field_lower:
                    return 'customer.address_city'
                elif 'state' in field_lower:
                    return 'customer.address_state'
                elif 'zip' in field_lower:
                    return 'customer.address_zip'
                else:
                    return 'customer.address_street'
            elif 'phone' in field_lower:
                return 'customer.signatory_work_phone'
            elif 'email' in field_lower:
                return 'customer.signatory_email_id'
            elif 'tax' in field_lower or 'ein' in field_lower:
                return 'customer.customer_tax_id'
            else:
                return f'customer.{field_name.lower()}'
                
        elif category == 'beneficiary':
            if 'name' in field_lower:
                if 'first' in field_lower:
                    return 'beneficary.Beneficiary.beneficiaryFirstName'
                elif 'last' in field_lower:
                    return 'beneficary.Beneficiary.beneficiaryLastName'
                elif 'middle' in field_lower:
                    return 'beneficary.Beneficiary.beneficiaryMiddleName'
                else:
                    return 'beneficary.Beneficiary.beneficiaryFirstName'
            elif 'birth' in field_lower:
                return 'beneficary.Beneficiary.beneficiaryDateOfBirth'
            elif 'alien' in field_lower:
                return 'beneficary.Beneficiary.alienNumber'
            elif 'ssn' in field_lower:
                return 'beneficary.Beneficiary.beneficiarySsn'
            else:
                return f'beneficary.Beneficiary.{field_name.lower()}'
                
        elif category == 'attorney':
            if 'name' in field_lower:
                if 'first' in field_lower:
                    return 'attorney.attorneyInfo.firstName'
                elif 'last' in field_lower:
                    return 'attorney.attorneyInfo.lastName'
                else:
                    return 'attorney.attorneyInfo.lastName'
            elif 'phone' in field_lower:
                return 'attorney.attorneyInfo.workPhone'
            elif 'email' in field_lower:
                return 'attorney.attorneyInfo.emailAddress'
            elif 'bar' in field_lower:
                return 'attorney.attorneyInfo.stateBarNumber'
            else:
                return f'attorney.attorneyInfo.{field_name.lower()}'
                
        else:
            return f'{field_name}:{self.determine_field_type(field_name).title()}Box'

def generate_typescript_config(form_config: FormConfig) -> str:
    """Generate TypeScript configuration file"""
    customer_data = {}
    beneficiary_data = {}
    attorney_data = {}
    questionnaire_data = {}
    
    for field in form_config.fields:
        mapping = f'"{field.mapping_path}:{field.field_type.title()}Box"'
        
        if field.category == 'customer':
            customer_data[field.name] = mapping
        elif field.category == 'beneficiary':
            beneficiary_data[field.name] = mapping
        elif field.category == 'attorney':
            attorney_data[field.name] = mapping
        else:
            questionnaire_data[field.name] = mapping
    
    ts_config = f'''export const {form_config.form_name.upper()} = {{
    "formname": "{form_config.form_name.lower()}",
    "pdfName": "{form_config.pdf_name}",
    "customerData": {{
        {',\n        '.join([f'"{k}": {v}' for k, v in customer_data.items()])}
    }},
    "beneficiaryData": {{
        {',\n        '.join([f'"{k}": {v}' for k, v in beneficiary_data.items()])}
    }},
    "questionnaireData": {{
        {',\n        '.join([f'"{k}": {v}' for k, v in questionnaire_data.items()])}
    }},
    "defaultData": {{
        // Add default values here
    }},
    "conditionalData": {{
        // Add conditional logic here
    }},
    "attorneyData": {{
        {',\n        '.join([f'"{k}": {v}' for k, v in attorney_data.items()])}
    }},
    "caseData": {{
        // Add case-specific data here
    }}
}}'''
    
    return ts_config

def generate_questionnaire_json(form_config: FormConfig) -> Dict[str, Any]:
    """Generate questionnaire JSON configuration"""
    controls = []
    current_section = None
    section_controls = []
    
    for field in form_config.fields:
        if field.category == 'questionnaire':
            control = {
                "name": field.name,
                "label": field.name.replace('_', ' ').title(),
                "type": field.field_type,
                "validators": {
                    "required": field.required
                },
                "style": {
                    "col": "6" if field.field_type != "textarea" else "12"
                }
            }
            
            if field.field_type == "dropdown":
                control["options"] = []
                control["lookup"] = "Custom"
            elif field.field_type == "date":
                control["validators"]["pattern"] = "date"
            elif field.field_type == "checkbox":
                control["defaultValue"] = False
            
            section_controls.append(control)
    
    if section_controls:
        controls.append({
            "group_name": f"{form_config.form_name.upper()} Details",
            "group_key": f"{form_config.form_name.lower()}_details",
            "group_definition": section_controls
        })
    
    return {"controls": controls}

def update_pdf_mapper(form_name: str, fields: List[FormField]) -> str:
    """Generate PDF mapper configuration"""
    mapper_fields = []
    
    for field in fields:
        mapper_field = {
            "Name": field.name,
            "Value": field.mapping_path,
            "Type": field.field_type.title() + "Box"
        }
        mapper_fields.append(mapper_field)
    
    mapper_config = f'''public static {form_name.upper()}: any = [
    {',\n    '.join([f'{{\n        Name: "{field["Name"]}",\n        Value: "{field["Value"]}",\n        Type: "{field["Type"]}"\n    }}' for field in mapper_fields])}
];'''
    
    return mapper_config

# Streamlit UI
def main():
    st.set_page_config(
        page_title="USCIS Form Configuration Generator",
        page_icon="📄",
        layout="wide"
    )
    
    st.title("🏛️ USCIS Form Configuration Generator")
    st.markdown("Upload a USCIS form and automatically generate configuration files")
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Form type selection
        form_type = st.selectbox(
            "Form Type",
            ["I-129", "I-140", "I-485", "G-28", "I-765", "I-539", "Custom"],
            help="Select the type of USCIS form"
        )
        
        # Processing options
        st.subheader("Processing Options")
        auto_categorize = st.checkbox("Auto-categorize fields", value=True)
        generate_questionnaire = st.checkbox("Generate questionnaire JSON", value=True)
        generate_typescript = st.checkbox("Generate TypeScript config", value=True)
        update_mappers = st.checkbox("Update PDF mappers", value=True)
    
    # Main content area
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("📤 Upload Form")
        
        # File upload
        uploaded_file = st.file_uploader(
            "Choose a PDF file",
            type=['pdf'],
            help="Upload the USCIS form PDF file"
        )
        
        if uploaded_file:
            # Form name input
            form_name = st.text_input(
                "Form Name",
                value=uploaded_file.name.split('.')[0],
                help="Enter the form name (e.g., I129, G28, etc.)"
            )
            
            # PDF name input
            pdf_name = st.text_input(
                "PDF Display Name",
                value=form_name.upper(),
                help="Enter the display name for the PDF"
            )
            
            if st.button("🔍 Process Form", type="primary"):
                with st.spinner("Processing form..."):
                    processor = USCISFormProcessor()
                    
                    # Extract fields from PDF
                    fields = processor.extract_pdf_fields(uploaded_file)
                    
                    if fields:
                        st.success(f"Extracted {len(fields)} fields from the form")
                        
                        # Process fields
                        form_fields = []
                        for field_name in fields:
                            category = processor.categorize_field(field_name) if auto_categorize else 'questionnaire'
                            field_type = processor.determine_field_type(field_name)
                            mapping_path = processor.generate_mapping_path(field_name, category)
                            
                            form_field = FormField(
                                name=field_name,
                                field_type=field_type,
                                category=category,
                                mapping_path=mapping_path,
                                required=False
                            )
                            form_fields.append(form_field)
                        
                        # Create form config
                        form_config = FormConfig(
                            form_name=form_name,
                            form_type=form_type,
                            pdf_name=pdf_name,
                            fields=form_fields,
                            sections=list(set([field.category for field in form_fields]))
                        )
                        
                        # Store in session state
                        st.session_state.form_config = form_config
                        st.session_state.processing_options = {
                            'generate_questionnaire': generate_questionnaire,
                            'generate_typescript': generate_typescript,
                            'update_mappers': update_mappers
                        }
                    else:
                        st.error("No form fields found in the PDF. Please check if the file is a fillable PDF form.")
    
    with col2:
        st.header("📊 Field Analysis")
        
        if 'form_config' in st.session_state:
            form_config = st.session_state.form_config
            
            # Display field statistics
            col2a, col2b = st.columns(2)
            with col2a:
                st.metric("Total Fields", len(form_config.fields))
            with col2b:
                st.metric("Categories", len(form_config.sections))
            
            # Category breakdown
            category_counts = {}
            for field in form_config.fields:
                category_counts[field.category] = category_counts.get(field.category, 0) + 1
            
            st.subheader("Field Categories")
            for category, count in category_counts.items():
                st.write(f"**{category.title()}**: {count} fields")
            
            # Field editor
            st.subheader("✏️ Edit Fields")
            
            # Create a DataFrame for editing
            field_data = []
            for i, field in enumerate(form_config.fields):
                field_data.append({
                    'Index': i,
                    'Name': field.name,
                    'Type': field.field_type,
                    'Category': field.category,
                    'Mapping Path': field.mapping_path,
                    'Required': field.required
                })
            
            df = pd.DataFrame(field_data)
            
            # Display editable dataframe
            edited_df = st.data_editor(
                df,
                column_config={
                    "Type": st.column_config.SelectboxColumn(
                        "Field Type",
                        options=["text", "textarea", "dropdown", "checkbox", "date", "radio", "number"],
                        required=True,
                    ),
                    "Category": st.column_config.SelectboxColumn(
                        "Category",
                        options=["customer", "beneficiary", "attorney", "case", "questionnaire"],
                        required=True,
                    ),
                    "Required": st.column_config.CheckboxColumn("Required"),
                },
                disabled=["Index", "Name"],
                hide_index=True,
                use_container_width=True
            )
            
            # Update form config with edited data
            if not edited_df.equals(df):
                for index, row in edited_df.iterrows():
                    field_idx = row['Index']
                    form_config.fields[field_idx].field_type = row['Type']
                    form_config.fields[field_idx].category = row['Category']
                    form_config.fields[field_idx].mapping_path = row['Mapping Path']
                    form_config.fields[field_idx].required = row['Required']
                
                st.session_state.form_config = form_config
    
    # Generate outputs
    if 'form_config' in st.session_state:
        st.header("📋 Generated Configurations")
        
        form_config = st.session_state.form_config
        options = st.session_state.processing_options
        
        tabs = st.tabs(["TypeScript Config", "Questionnaire JSON", "PDF Mapper", "Summary"])
        
        with tabs[0]:
            if options['generate_typescript']:
                st.subheader("📝 TypeScript Configuration")
                ts_config = generate_typescript_config(form_config)
                st.code(ts_config, language='typescript')
                
                st.download_button(
                    label="📥 Download TypeScript Config",
                    data=ts_config,
                    file_name=f"{form_config.form_name}.ts",
                    mime="text/typescript"
                )
        
        with tabs[1]:
            if options['generate_questionnaire']:
                st.subheader("📋 Questionnaire JSON")
                questionnaire_json = generate_questionnaire_json(form_config)
                st.json(questionnaire_json)
                
                st.download_button(
                    label="📥 Download Questionnaire JSON",
                    data=json.dumps(questionnaire_json, indent=2),
                    file_name=f"{form_config.form_name}-form.json",
                    mime="application/json"
                )
        
        with tabs[2]:
            if options['update_mappers']:
                st.subheader("🗺️ PDF Mapper Configuration")
                mapper_config = update_pdf_mapper(form_config.form_name, form_config.fields)
                st.code(mapper_config, language='typescript')
                
                st.download_button(
                    label="📥 Download PDF Mapper",
                    data=mapper_config,
                    file_name=f"{form_config.form_name}-mapper.ts",
                    mime="text/typescript"
                )
        
        with tabs[3]:
            st.subheader("📊 Configuration Summary")
            
            summary_data = {
                "Form Name": form_config.form_name,
                "Form Type": form_config.form_type,
                "PDF Name": form_config.pdf_name,
                "Total Fields": len(form_config.fields),
                "Categories": ", ".join(form_config.sections),
                "Generated At": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            for key, value in summary_data.items():
                st.write(f"**{key}**: {value}")
            
            # Field breakdown by category
            st.subheader("Field Breakdown")
            category_breakdown = {}
            for field in form_config.fields:
                if field.category not in category_breakdown:
                    category_breakdown[field.category] = []
                category_breakdown[field.category].append(field.name)
            
            for category, fields in category_breakdown.items():
                with st.expander(f"{category.title()} Fields ({len(fields)})"):
                    for field in fields:
                        st.write(f"• {field}")

if __name__ == "__main__":
    main()
