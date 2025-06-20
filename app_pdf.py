import streamlit as st
import json
import pandas as pd
from typing import Dict, List, Tuple, Any, Optional
import re
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime
import base64
from io import BytesIO
import PyPDF2

class FormType(Enum):
    LCA = "LCA"
    I129 = "I-129"
    G28 = "G-28"
    I539 = "I-539"
    I765 = "I-765"
    I140 = "I-140"
    I485 = "I-485"
    I907 = "I-907"
    I131 = "I-131"
    I864 = "I-864"
    UNKNOWN = "Unknown"

@dataclass
class FormField:
    pdf_field_name: str
    field_type: str
    label: str = ""
    database_mapping: str = ""
    is_mapped: bool = False
    default_value: str = ""
    value: str = ""

class SimplifiedFormMapper:
    def __init__(self):
        # Sample database fields for mapping suggestions
        self.database_fields = [
            "customer.customer_name",
            "customer.address_street",
            "customer.address_city",
            "customer.address_state",
            "customer.address_zip",
            "customer.signatory_first_name",
            "customer.signatory_last_name",
            "beneficiary.Beneficiary.beneficiaryFirstName",
            "beneficiary.Beneficiary.beneficiaryLastName",
            "beneficiary.Beneficiary.beneficiaryDateOfBirth",
            "beneficiary.Beneficiary.beneficiaryCountryOfBirth",
            "beneficiary.Beneficiary.beneficiarySsn",
            "attorney.attorneyInfo.lastName",
            "attorney.attorneyInfo.firstName",
            "attorney.attorneyInfo.stateBarNumber",
            "attorney.attorneyInfo.emailAddress",
        ]
    
    def detect_form_type(self, content: str) -> FormType:
        """Detect the type of form based on content"""
        content_lower = content.lower()
        
        form_patterns = {
            "LCA": ["labor condition application", "lca"],
            "I-129": ["i-129", "petition for a nonimmigrant worker"],
            "G-28": ["g-28", "g28", "notice of entry of appearance"],
            "I-539": ["i-539", "i539", "extend/change nonimmigrant status"],
            "I-765": ["i-765", "i765", "employment authorization"],
            "I-140": ["i-140", "i140", "immigrant petition"],
            "I-485": ["i-485", "i485", "adjust status"],
            "I-907": ["i-907", "i907", "premium processing"],
            "I-131": ["i-131", "i131", "travel document"],
            "I-864": ["i-864", "i864", "affidavit of support"],
        }
        
        for form_type, patterns in form_patterns.items():
            for pattern in patterns:
                if pattern in content_lower:
                    return FormType(form_type)
        
        return FormType.UNKNOWN
    
    def extract_pdf_fields(self, pdf_content: bytes) -> List[FormField]:
        """Extract actual form fields from the PDF"""
        fields = []
        try:
            pdf_reader = PyPDF2.PdfReader(BytesIO(pdf_content))
            
            # Try to extract form fields
            if '/AcroForm' in pdf_reader.trailer['/Root']:
                form = pdf_reader.trailer['/Root']['/AcroForm']
                if '/Fields' in form:
                    for field_ref in form['/Fields']:
                        field = field_ref.get_object()
                        field_dict = self._extract_field_info(field)
                        if field_dict:
                            fields.append(field_dict)
            
            # If no form fields, extract text and parse it
            if not fields:
                text_content = ""
                for page in pdf_reader.pages:
                    text_content += page.extract_text() + "\n"
                fields = self._parse_text_for_fields(text_content)
            
        except Exception as e:
            st.error(f"Error extracting PDF fields: {str(e)}")
        
        return fields
    
    def _extract_field_info(self, field) -> Optional[FormField]:
        """Extract field information from PDF field object"""
        try:
            field_name = str(field.get('/T', 'Unknown'))
            field_type = str(field.get('/FT', '/Tx'))
            field_value = str(field.get('/V', ''))
            
            # Map PDF field types
            type_mapping = {
                '/Tx': 'TextBox',
                '/Btn': 'CheckBox',
                '/Ch': 'DropDown',
                '/Sig': 'Signature'
            }
            
            # Generate a readable label
            label = self._generate_label(field_name)
            
            # Try to suggest database mapping
            suggested_mapping = self._suggest_database_mapping(field_name, label)
            
            return FormField(
                pdf_field_name=field_name,
                field_type=type_mapping.get(field_type, 'TextBox'),
                label=label,
                database_mapping=suggested_mapping,
                is_mapped=bool(suggested_mapping),
                value=field_value
            )
        except:
            return None
    
    def _parse_text_for_fields(self, text: str) -> List[FormField]:
        """Parse text content to identify potential form fields"""
        fields = []
        
        # Common patterns for form fields
        patterns = [
            r'(?:Part|Section)\s+(\d+)[:\s]+([^\n]+)',
            r'(\d+[a-z]?)\.?\s+([A-Z][^:\n]+):?',
            r'([A-Z][^:]+):\s*_{3,}',
            r'([A-Z][^:]+):\s*\[?\s*\]?',
        ]
        
        seen_fields = set()
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.MULTILINE)
            for match in matches:
                if len(match.groups()) >= 2:
                    field_id = match.group(1)
                    field_label = match.group(2).strip()
                else:
                    field_label = match.group(1).strip()
                    field_id = field_label
                
                field_name = f"field_{field_id}".replace(' ', '_').lower()
                
                if field_name not in seen_fields and len(field_label) > 3:
                    seen_fields.add(field_name)
                    
                    suggested_mapping = self._suggest_database_mapping(field_name, field_label)
                    
                    fields.append(FormField(
                        pdf_field_name=field_name,
                        field_type="TextBox",
                        label=field_label,
                        database_mapping=suggested_mapping,
                        is_mapped=bool(suggested_mapping)
                    ))
        
        return fields[:100]  # Limit to first 100 fields
    
    def _generate_label(self, field_name: str) -> str:
        """Generate a readable label from field name"""
        # Remove common prefixes
        label = re.sub(r'^(txt|chk|cbo|rad|btn)', '', field_name)
        # Replace underscores and camelCase
        label = re.sub(r'([A-Z])', r' \1', label)
        label = label.replace('_', ' ').replace('-', ' ')
        # Title case
        return ' '.join(word.capitalize() for word in label.split())
    
    def _suggest_database_mapping(self, field_name: str, label: str) -> str:
        """Suggest database mapping based on field name and label"""
        field_lower = field_name.lower()
        label_lower = label.lower()
        
        # Simple mapping rules
        if any(term in field_lower or term in label_lower for term in ['first', 'given']):
            if 'attorney' in field_lower or 'attorney' in label_lower:
                return "attorney.attorneyInfo.firstName"
            elif 'beneficiary' in field_lower or 'beneficiary' in label_lower:
                return "beneficiary.Beneficiary.beneficiaryFirstName"
            elif 'customer' in field_lower or 'signatory' in label_lower:
                return "customer.signatory_first_name"
        
        if any(term in field_lower or term in label_lower for term in ['last', 'family', 'surname']):
            if 'attorney' in field_lower or 'attorney' in label_lower:
                return "attorney.attorneyInfo.lastName"
            elif 'beneficiary' in field_lower or 'beneficiary' in label_lower:
                return "beneficiary.Beneficiary.beneficiaryLastName"
            elif 'customer' in field_lower or 'signatory' in label_lower:
                return "customer.signatory_last_name"
        
        if any(term in field_lower or term in label_lower for term in ['email', 'e-mail']):
            if 'attorney' in field_lower or 'attorney' in label_lower:
                return "attorney.attorneyInfo.emailAddress"
            else:
                return "customer.signatory_email_id"
        
        if 'ssn' in field_lower or 'social security' in label_lower:
            return "beneficiary.Beneficiary.beneficiarySsn"
        
        if 'date' in field_lower and 'birth' in field_lower:
            return "beneficiary.Beneficiary.beneficiaryDateOfBirth"
        
        if 'country' in field_lower and 'birth' in field_lower:
            return "beneficiary.Beneficiary.beneficiaryCountryOfBirth"
        
        if 'bar' in field_lower and 'number' in field_lower:
            return "attorney.attorneyInfo.stateBarNumber"
        
        return ""  # No mapping suggested
    
    def generate_typescript(self, form_name: str, fields: List[FormField]) -> str:
        """Generate TypeScript interface for the form"""
        # Clean form name for interface
        interface_name = re.sub(r'[^a-zA-Z0-9]', '', form_name.replace('.pdf', ''))
        
        ts_content = f"""// TypeScript interface for {form_name}
// Auto-generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

export interface {interface_name}Form {{
"""
        
        for field in fields:
            # Clean field name for TypeScript
            ts_field_name = re.sub(r'[^a-zA-Z0-9_]', '_', field.pdf_field_name)
            if ts_field_name[0].isdigit():
                ts_field_name = f"field_{ts_field_name}"
            
            # Map field types to TypeScript types
            ts_type = 'string'
            if field.field_type == 'CheckBox':
                ts_type = 'boolean'
            elif field.field_type == 'Number':
                ts_type = 'number'
            elif 'date' in field.pdf_field_name.lower() or 'date' in field.label.lower():
                ts_type = 'Date | string'
            
            # Add comment with label and mapping
            comment = f"  // {field.label}"
            if field.database_mapping:
                comment += f" -> {field.database_mapping}"
            
            ts_content += f"{comment}\n"
            ts_content += f"  {ts_field_name}: {ts_type};\n"
        
        ts_content += "}\n"
        return ts_content
    
    def generate_questionnaire(self, fields: List[FormField]) -> Dict[str, Any]:
        """Generate questionnaire JSON for unmapped fields"""
        controls = []
        
        for field in fields:
            if not field.is_mapped:
                control = {
                    "name": re.sub(r'[^a-zA-Z0-9_]', '_', field.pdf_field_name),
                    "label": field.label or field.pdf_field_name,
                    "type": self._map_field_type_to_control(field.field_type),
                    "validators": {"required": False},
                    "style": {"col": "6"}
                }
                
                if field.field_type == "CheckBox":
                    control["type"] = "colorSwitch"
                elif field.field_type == "DropDown":
                    control["options"] = []
                    control["lookup"] = "TBD"
                
                controls.append(control)
        
        return {
            "title": "Additional Information Required",
            "description": "Please provide the following information",
            "controls": controls
        }
    
    def _map_field_type_to_control(self, field_type: str) -> str:
        """Map PDF field type to questionnaire control type"""
        mapping = {
            "TextBox": "text",
            "CheckBox": "colorSwitch",
            "DropDown": "dropdown",
            "Signature": "text",
            "RadioButton": "radio"
        }
        return mapping.get(field_type, "text")
    
    def generate_consolidated_mapping(self, form_type: str, form_name: str, fields: List[FormField]) -> Dict[str, Any]:
        """Generate consolidated mapping with all information"""
        mapped_fields = [f for f in fields if f.is_mapped]
        unmapped_fields = [f for f in fields if not f.is_mapped]
        
        # Create object to attribute mappings
        object_mappings = {}
        for field in mapped_fields:
            if field.database_mapping:
                parts = field.database_mapping.split('.')
                if len(parts) >= 2:
                    obj_path = '.'.join(parts[:-1])
                    attribute = parts[-1]
                    
                    if obj_path not in object_mappings:
                        object_mappings[obj_path] = []
                    
                    object_mappings[obj_path].append({
                        "pdf_field": field.pdf_field_name,
                        "attribute": attribute,
                        "field_type": field.field_type,
                        "label": field.label
                    })
        
        return {
            "form_info": {
                "form_type": form_type,
                "form_name": form_name,
                "extraction_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "total_fields": len(fields),
                "mapped_fields": len(mapped_fields),
                "unmapped_fields": len(unmapped_fields),
                "coverage_percentage": round((len(mapped_fields) / len(fields) * 100), 2) if fields else 0
            },
            "object_to_attribute_mappings": object_mappings,
            "mapped_fields_detail": [
                {
                    "pdf_field": f.pdf_field_name,
                    "label": f.label,
                    "field_type": f.field_type,
                    "database_mapping": f.database_mapping,
                    "value": f.value
                } for f in mapped_fields
            ],
            "unmapped_fields_detail": [
                {
                    "pdf_field": f.pdf_field_name,
                    "label": f.label,
                    "field_type": f.field_type,
                    "suggested_control": self._map_field_type_to_control(f.field_type)
                } for f in unmapped_fields
            ]
        }

def main():
    st.set_page_config(
        page_title="USCIS Form Mapper & TypeScript Generator",
        page_icon="📄",
        layout="wide"
    )
    
    st.title("📄 USCIS Form Mapper & TypeScript Generator")
    st.markdown("Upload a USCIS form to generate TypeScript interfaces, questionnaires, and field mappings")
    
    # Initialize mapper
    mapper = SimplifiedFormMapper()
    
    # File upload
    uploaded_file = st.file_uploader(
        "Upload USCIS Form (PDF)",
        type=['pdf'],
        help="Upload a USCIS form PDF to analyze its fields"
    )
    
    if uploaded_file is not None:
        # Read PDF content
        pdf_content = uploaded_file.read()
        
        # Extract text for form type detection
        try:
            pdf_reader = PyPDF2.PdfReader(BytesIO(pdf_content))
            text_content = ""
            for page in pdf_reader.pages:
                text_content += page.extract_text() + "\n"
            
            # Detect form type
            form_type = mapper.detect_form_type(text_content)
            
            # Extract fields
            fields = mapper.extract_pdf_fields(pdf_content)
            
            if not fields:
                st.warning("No form fields could be extracted from this PDF.")
            else:
                st.success(f"✅ Detected Form Type: **{form_type.value}**")
                st.info(f"📊 Extracted **{len(fields)}** fields from the PDF")
                
                # Create tabs
                tab1, tab2, tab3, tab4 = st.tabs([
                    "💻 TypeScript Interface",
                    "❓ Questionnaire JSON",
                    "🔄 Consolidated Mapping",
                    "📋 Field Details"
                ])
                
                with tab1:
                    st.header("TypeScript Interface")
                    
                    ts_content = mapper.generate_typescript(uploaded_file.name, fields)
                    st.code(ts_content, language="typescript")
                    
                    st.download_button(
                        label=f"📥 Download {uploaded_file.name.replace('.pdf', '')}.ts",
                        data=ts_content,
                        file_name=f"{uploaded_file.name.replace('.pdf', '')}.ts",
                        mime="text/typescript"
                    )
                
                with tab2:
                    st.header("Questionnaire JSON")
                    
                    unmapped_count = len([f for f in fields if not f.is_mapped])
                    if unmapped_count > 0:
                        st.info(f"Found {unmapped_count} unmapped fields that need questionnaire entries")
                        
                        questionnaire = mapper.generate_questionnaire(fields)
                        st.json(questionnaire)
                        
                        st.download_button(
                            label="📥 Download Questionnaire JSON",
                            data=json.dumps(questionnaire, indent=2),
                            file_name=f"{form_type.value.lower()}_questionnaire.json",
                            mime="application/json"
                        )
                    else:
                        st.success("🎉 All fields are mapped! No questionnaire needed.")
                
                with tab3:
                    st.header("Consolidated Mapping")
                    
                    consolidated = mapper.generate_consolidated_mapping(
                        form_type.value,
                        uploaded_file.name,
                        fields
                    )
                    
                    # Display summary metrics
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Fields", consolidated["form_info"]["total_fields"])
                    with col2:
                        st.metric("Mapped Fields", consolidated["form_info"]["mapped_fields"])
                    with col3:
                        st.metric("Unmapped Fields", consolidated["form_info"]["unmapped_fields"])
                    with col4:
                        st.metric("Coverage %", f"{consolidated['form_info']['coverage_percentage']}%")
                    
                    # Show object mappings
                    if consolidated["object_to_attribute_mappings"]:
                        st.subheader("Object to Attribute Mappings")
                        for obj_path, mappings in consolidated["object_to_attribute_mappings"].items():
                            with st.expander(f"📁 {obj_path}"):
                                df = pd.DataFrame(mappings)
                                st.dataframe(df, use_container_width=True)
                    
                    # Download consolidated JSON
                    st.download_button(
                        label="📥 Download Consolidated Mapping JSON",
                        data=json.dumps(consolidated, indent=2),
                        file_name=f"{form_type.value.lower()}_consolidated_mapping.json",
                        mime="application/json"
                    )
                
                with tab4:
                    st.header("Field Details")
                    
                    # Separate mapped and unmapped
                    mapped_fields = [f for f in fields if f.is_mapped]
                    unmapped_fields = [f for f in fields if not f.is_mapped]
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.subheader(f"🟢 Mapped Fields ({len(mapped_fields)})")
                        if mapped_fields:
                            mapped_data = []
                            for field in mapped_fields:
                                mapped_data.append({
                                    "PDF Field": field.pdf_field_name,
                                    "Label": field.label,
                                    "Type": field.field_type,
                                    "Mapping": field.database_mapping
                                })
                            df_mapped = pd.DataFrame(mapped_data)
                            st.dataframe(df_mapped, use_container_width=True, height=400)
                    
                    with col2:
                        st.subheader(f"🔴 Unmapped Fields ({len(unmapped_fields)})")
                        if unmapped_fields:
                            unmapped_data = []
                            for field in unmapped_fields:
                                unmapped_data.append({
                                    "PDF Field": field.pdf_field_name,
                                    "Label": field.label,
                                    "Type": field.field_type
                                })
                            df_unmapped = pd.DataFrame(unmapped_data)
                            st.dataframe(df_unmapped, use_container_width=True, height=400)
                
        except Exception as e:
            st.error(f"Error processing PDF: {str(e)}")
    
    else:
        st.info("👆 Please upload a USCIS form PDF to begin analysis")
        
        with st.expander("ℹ️ What this tool does"):
            st.markdown("""
            This tool analyzes USCIS PDF forms and generates:
            
            1. **TypeScript Interface** - Type-safe interface for form fields
            2. **Questionnaire JSON** - Dynamic form configuration for unmapped fields
            3. **Consolidated Mapping** - Complete field analysis with object-to-attribute mappings
            4. **Field Details** - Comprehensive view of all extracted fields
            
            The tool automatically:
            - Detects the form type
            - Extracts all form fields
            - Suggests database mappings based on field names
            - Generates proper TypeScript types
            - Creates questionnaire controls for unmapped fields
            """)

if __name__ == "__main__":
    main()
