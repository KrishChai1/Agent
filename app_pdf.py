#!/usr/bin/env python3
"""
Complete Integrated USCIS Form Reader System
Combines your multi-agent extractor with database mapping
"""

# First, include ALL your existing imports and classes
# [Copy all imports from your original paste.txt here]

# Then add these additional imports for mapping functionality:
from typing import Dict, List, Optional, Any, Tuple, Set, Union
from collections import defaultdict

# Additional Enums for mapping
class MappingStatus(Enum):
    MAPPED = "mapped"
    UNMAPPED = "unmapped"
    MANUAL = "manual"
    QUESTIONNAIRE = "questionnaire"

# Additional Data Classes for mapping
@dataclass
class ExtractedField:
    """Represents an extracted field from PDF"""
    key: str
    label: str
    value: str
    field_type: FieldType
    page: int
    confidence: float
    mapping_status: MappingStatus = MappingStatus.UNMAPPED
    mapped_to: Optional[str] = None
    
@dataclass
class FieldMapping:
    """Represents a mapping between PDF field and database field"""
    pdf_field_key: str
    pdf_field_label: str
    database_table: str
    database_field: str
    transformation: Optional[str] = None

# [Include ALL your existing classes here: PatternLibrary, BaseAgent, etc.]

# Then add this enhanced main function that combines both systems:
def main():
    st.markdown(
        '<div class="main-header">'
        '<h1>🤖 USCIS Form Reader & Database Mapper</h1>'
        '<p>Multi-Agent Extraction → Database Mapping → Export</p>'
        '</div>', 
        unsafe_allow_html=True
    )
    
    # Initialize session states
    if 'extraction_output' not in st.session_state:
        st.session_state.extraction_output = None
    if 'extraction_result' not in st.session_state:
        st.session_state.extraction_result = None
    if 'mapped_fields' not in st.session_state:
        st.session_state.mapped_fields = {}
    if 'unmapped_fields' not in st.session_state:
        st.session_state.unmapped_fields = {}
    if 'database_schema' not in st.session_state:
        st.session_state.database_schema = {
            "beneficiary": {
                "firstName": "string",
                "lastName": "string",
                "middleName": "string",
                "dateOfBirth": "date",
                "alienNumber": "string",
                "socialSecurityNumber": "string",
                "countryOfBirth": "string",
                "countryOfCitizenship": "string"
            },
            "address": {
                "streetNumber": "string",
                "streetName": "string",
                "aptNumber": "string",
                "city": "string",
                "state": "string",
                "zipCode": "string"
            },
            "contact": {
                "daytimePhone": "string",
                "mobilePhone": "string",
                "emailAddress": "string"
            }
        }
    
    # Create tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📄 Extract",
        "🔗 Map Fields",
        "✏️ Manual Entry",
        "❓ Questionnaire",
        "💾 Export"
    ])
    
    # Tab 1: Extraction (Your existing code)
    with tab1:
        st.markdown("## 📄 Upload USCIS Form")
        
        uploaded_file = st.file_uploader(
            "Choose a PDF form",
            type=['pdf'],
            help="Supported forms: I-539, I-129, G-28, I-90, I-485, I-765, N-400"
        )
        
        if uploaded_file:
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                st.success(f"✅ Uploaded: {uploaded_file.name}")
            
            with col2:
                process_btn = st.button(
                    "🚀 Extract & Map",
                    type="primary",
                    use_container_width=True
                )
            
            if process_btn:
                # Create containers
                st.session_state.agent_container = st.container()
                
                with st.spinner("Processing with multi-agent system..."):
                    # Run your existing extraction
                    coordinator = MasterCoordinator(max_iterations=3)
                    output = coordinator.execute(uploaded_file)
                    
                    if output:
                        st.session_state.extraction_output = output
                        
                        # Convert to mapping format
                        extracted_fields = {}
                        for key, value in output.items():
                            if not key.startswith('_') and not key.endswith('_title'):
                                label = output.get(f"{key}_title", key)
                                
                                # Create ExtractedField
                                field = ExtractedField(
                                    key=key,
                                    label=label,
                                    value=str(value) if value else "",
                                    field_type=determine_field_type(label),
                                    page=1,
                                    confidence=0.95
                                )
                                extracted_fields[key] = field
                        
                        # Auto-map fields
                        mapped, unmapped = auto_map_fields(
                            extracted_fields,
                            st.session_state.database_schema
                        )
                        
                        st.session_state.mapped_fields = mapped
                        st.session_state.unmapped_fields = unmapped
                        st.session_state.extracted_fields = extracted_fields
                        
                        st.success(f"✅ Extraction Complete!")
                        st.info(f"📊 Extracted: {len(extracted_fields)} | "
                               f"✅ Mapped: {len(mapped)} | "
                               f"❓ Unmapped: {len(unmapped)}")
                    else:
                        st.error("❌ Extraction Failed")
            
            # Show results
            if st.session_state.extraction_output:
                metadata = st.session_state.extraction_output.get('_metadata', {})
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Form", metadata.get('form_number', 'Unknown'))
                with col2:
                    st.metric("Total Fields", metadata.get('total_fields', 0))
                with col3:
                    st.metric("Score", f"{metadata.get('validation_score', 0):.0%}")
                with col4:
                    st.metric("Mapped", len(st.session_state.mapped_fields))
    
    # Tab 2: Mapping Interface
    with tab2:
        st.markdown("### 🔗 Field Mapping")
        
        if st.session_state.extraction_output:
            # Show mapping interface
            for field_key, field in st.session_state.unmapped_fields.items():
                col1, col2, col3 = st.columns([3, 1, 3])
                
                with col1:
                    st.info(f"**{field.label}**\n\nValue: {field.value}")
                
                with col2:
                    st.markdown("→")
                
                with col3:
                    # Database field selector
                    options = ["-- Select --"]
                    for table, fields in st.session_state.database_schema.items():
                        for fname in fields:
                            options.append(f"{table}.{fname}")
                    
                    selected = st.selectbox(
                        "Database field",
                        options,
                        key=f"map_{field_key}"
                    )
                    
                    if selected != options[0]:
                        if st.button("Map", key=f"btn_{field_key}"):
                            # Create mapping
                            table, fname = selected.split('.')
                            mapping = FieldMapping(
                                pdf_field_key=field_key,
                                pdf_field_label=field.label,
                                database_table=table,
                                database_field=fname
                            )
                            st.session_state.mapped_fields[field_key] = mapping
                            del st.session_state.unmapped_fields[field_key]
                            st.rerun()
        else:
            st.info("Please extract fields first")
    
    # Tab 3: Manual Entry (from mapping system)
    with tab3:
        st.markdown("### ✏️ Add Fields Manually")
        # [Include manual entry code from mapping system]
    
    # Tab 4: Questionnaire (from mapping system)
    with tab4:
        st.markdown("### ❓ Complete Unmapped Fields")
        # [Include questionnaire code from mapping system]
    
    # Tab 5: Export
    with tab5:
        st.markdown("### 💾 Export Options")
        
        if st.session_state.mapped_fields:
            # Generate exports
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # JSON export
                export_data = generate_json_mapping(
                    st.session_state.mapped_fields,
                    st.session_state.extracted_fields
                )
                
                json_str = json.dumps(export_data, indent=2)
                st.download_button(
                    "📥 Download Mapped JSON",
                    json_str,
                    "mapped_data.json",
                    mime="application/json"
                )
            
            with col2:
                # TypeScript export
                ts_code = generate_typescript_interface(
                    st.session_state.mapped_fields,
                    "USCISForm"
                )
                
                st.download_button(
                    "📥 Download TypeScript",
                    ts_code,
                    "form_interface.ts",
                    mime="text/plain"
                )
            
            with col3:
                # Unmapped fields
                if st.session_state.unmapped_fields:
                    unmapped_data = {
                        k: {"label": v.label, "value": v.value}
                        for k, v in st.session_state.unmapped_fields.items()
                    }
                    
                    json_str = json.dumps(unmapped_data, indent=2)
                    st.download_button(
                        "📥 Download Unmapped",
                        json_str,
                        "unmapped_fields.json",
                        mime="application/json"
                    )
        else:
            st.info("No data to export yet")

# Helper functions
def determine_field_type(label: str) -> FieldType:
    """Determine field type from label"""
    label_lower = label.lower()
    
    if 'date' in label_lower or 'birth' in label_lower:
        return FieldType.DATE
    elif 'number' in label_lower or 'phone' in label_lower:
        return FieldType.NUMBER
    elif 'email' in label_lower:
        return FieldType.EMAIL
    elif 'name' in label_lower:
        return FieldType.NAME
    elif 'address' in label_lower or 'street' in label_lower:
        return FieldType.ADDRESS
    else:
        return FieldType.TEXT

def auto_map_fields(extracted_fields: Dict[str, ExtractedField], 
                   database_schema: Dict) -> Tuple[Dict, Dict]:
    """Auto-map fields based on patterns"""
    # [Include the auto_map_fields function from mapping system]
    pass

def generate_typescript_interface(mapped_fields: Dict[str, FieldMapping], 
                                form_name: str) -> str:
    """Generate TypeScript interface"""
    # [Include the TypeScript generation function]
    pass

def generate_json_mapping(mapped_fields: Dict[str, FieldMapping], 
                         extracted_fields: Dict[str, ExtractedField]) -> Dict:
    """Generate JSON with mapped data"""
    # [Include the JSON generation function]
    pass

# [Include all other helper functions]

if __name__ == "__main__":
    main()
