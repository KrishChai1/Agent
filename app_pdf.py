import streamlit as st
import json
import pandas as pd
from typing import Dict, List, Tuple, Any
import re
from dataclasses import dataclass
from enum import Enum

class FormType(Enum):
    I539 = "I-539"
    I129 = "I-129"
    I140 = "I-140"
    I485 = "I-485"
    G28 = "G-28"
    I907 = "I-907"
    UNKNOWN = "Unknown"

@dataclass
class FormField:
    form_type: str
    part: str
    item: str
    field_name: str
    label: str
    field_type: str = "text"
    is_mapped: bool = False
    database_mapping: str = ""
    default_value: str = ""
    is_conditional: bool = False
    condition: str = ""

class FormMapper:
    def __init__(self):
        self.form_mappings = self._load_form_mappings()
        self.database_fields = self._load_database_fields()
    
    def _load_database_fields(self) -> List[str]:
        """Load all available database fields from the mapping document"""
        return [
            # Customer fields
            "customer.customer_name",
            "customer.customer_address_id.address_street",
            "customer.customer_signatory_id.signatory_last_name",
            "customer.customer_signatory_id.signatory_first_name",
            "customer.customer_tax_id",
            "customer.customer_naics_code",
            
            # Beneficiary fields
            "beneficiary.Beneficiary.beneficiaryLastName",
            "beneficiary.Beneficiary.beneficiaryFirstName",
            "beneficiary.Beneficiary.beneficiaryMiddleName",
            "beneficiary.Beneficiary.beneficiaryDateOfBirth",
            "beneficiary.Beneficiary.beneficiaryCountryOfBirth",
            "beneficiary.Beneficiary.beneficiaryCitizenOfCountry",
            "beneficiary.Beneficiary.beneficiaryGender",
            "beneficiary.Beneficiary.beneficiarySsn",
            "beneficiary.Beneficiary.alien_number",
            
            # Address fields
            "address.address_street",
            "address.address_city",
            "address.address_state",
            "address.address_zip",
            "address.address_country",
            
            # Attorney fields
            "attorney.attorneyInfo.lastName",
            "attorney.attorneyInfo.firstName",
            "attorney.attorneyInfo.stateBarNumber",
            "attorney.attorneyInfo.workPhone",
            "attorney.attorneyInfo.emailAddress",
            
            # Visa/Immigration fields
            "beneficiary.VisaDetails.Visa.visaStatus",
            "beneficiary.VisaDetails.Visa.visaExpiryDate",
            "beneficiary.I94Details.I94.i94Number",
            "beneficiary.I94Details.I94.i94ArrivalDate",
            "beneficiary.PassportDetails.Passport.passportNumber",
            "beneficiary.PassportDetails.Passport.passportExpiryDate",
            "beneficiary.PassportDetails.Passport.passportIssueCountry",
        ]
    
    def _load_form_mappings(self) -> Dict[str, Dict[str, FormField]]:
        """Load predefined form mappings from the mapping document"""
        
        i539_mappings = {
            # Attorney Information
            "attorney_g28_attached": FormField(
                form_type="I-539",
                part="Header",
                item="G-28",
                field_name="attorney_g28_attached",
                label="Form G-28 is attached",
                field_type="checkbox",
                is_mapped=True,
                database_mapping="Default: Yes",
                default_value="Yes"
            ),
            "attorney_state_bar": FormField(
                form_type="I-539",
                part="Header",
                item="State Bar",
                field_name="attorney_state_bar",
                label="Attorney State Bar Number",
                field_type="text",
                is_mapped=True,
                database_mapping="attorney.attorneyInfo.stateBarNumber"
            ),
            
            # Part 1 - Information About You
            "part1_family_name": FormField(
                form_type="I-539",
                part="1",
                item="1a",
                field_name="part1_family_name",
                label="Family Name (Last Name)",
                field_type="text",
                is_mapped=True,
                database_mapping="beneficiary.Beneficiary.beneficiaryLastName"
            ),
            "part1_given_name": FormField(
                form_type="I-539",
                part="1",
                item="1b",
                field_name="part1_given_name",
                label="Given Name (First Name)",
                field_type="text",
                is_mapped=True,
                database_mapping="beneficiary.Beneficiary.beneficiaryFirstName"
            ),
            "part1_middle_name": FormField(
                form_type="I-539",
                part="1",
                item="1c",
                field_name="part1_middle_name",
                label="Middle Name (if applicable)",
                field_type="text",
                is_mapped=True,
                database_mapping="beneficiary.Beneficiary.beneficiaryMiddleName"
            ),
            "part1_alien_number": FormField(
                form_type="I-539",
                part="1",
                item="2",
                field_name="part1_alien_number",
                label="Alien Registration Number (A-Number)",
                field_type="text",
                is_mapped=True,
                database_mapping="beneficiary.Beneficiary.alien_number"
            ),
            "part1_uscis_account": FormField(
                form_type="I-539",
                part="1",
                item="3",
                field_name="part1_uscis_account",
                label="USCIS Online Account Number",
                field_type="text",
                is_mapped=False,
                database_mapping="",
                default_value=""
            ),
            
            # Mailing Address
            "part1_mailing_care_of": FormField(
                form_type="I-539",
                part="1",
                item="4a",
                field_name="part1_mailing_care_of",
                label="In Care Of Name (if any)",
                field_type="text",
                is_mapped=True,
                database_mapping="beneficiary.Beneficiary.beneficiaryLastName and beneficiary.Beneficiary.beneficiaryFirstName"
            ),
            "part1_mailing_street": FormField(
                form_type="I-539",
                part="1",
                item="4b",
                field_name="part1_mailing_street",
                label="Street Number and Name",
                field_type="text",
                is_mapped=True,
                database_mapping="beneficiary.WorkAddress.addressStreet"
            ),
            "part1_mailing_apt": FormField(
                form_type="I-539",
                part="1",
                item="4c",
                field_name="part1_mailing_apt",
                label="Apt. Ste. Flr. Number",
                field_type="text",
                is_mapped=True,
                database_mapping="beneficiary.WorkAddress.addressType, beneficiary.WorkAddress.addressNumber"
            ),
            "part1_mailing_city": FormField(
                form_type="I-539",
                part="1",
                item="4d",
                field_name="part1_mailing_city",
                label="City or Town",
                field_type="text",
                is_mapped=True,
                database_mapping="beneficiary.WorkAddress.addressCity"
            ),
            "part1_mailing_state": FormField(
                form_type="I-539",
                part="1",
                item="4e",
                field_name="part1_mailing_state",
                label="State",
                field_type="text",
                is_mapped=True,
                database_mapping="beneficiary.WorkAddress.addressState"
            ),
            "part1_mailing_zip": FormField(
                form_type="I-539",
                part="1",
                item="4f",
                field_name="part1_mailing_zip",
                label="ZIP Code",
                field_type="text",
                is_mapped=True,
                database_mapping="beneficiary.WorkAddress.addressZip"
            ),
            
            # Physical Address Same as Mailing
            "part1_same_address": FormField(
                form_type="I-539",
                part="1",
                item="5",
                field_name="part1_same_address",
                label="Is your mailing address the same as your physical address?",
                field_type="radio",
                is_mapped=False,
                database_mapping="",
                default_value=""
            ),
            
            # Personal Information
            "part1_country_birth": FormField(
                form_type="I-539",
                part="1",
                item="6",
                field_name="part1_country_birth",
                label="Country of Birth",
                field_type="text",
                is_mapped=True,
                database_mapping="beneficiary.Beneficiary.beneficiaryCountryOfBirth"
            ),
            "part1_country_citizenship": FormField(
                form_type="I-539",
                part="1",
                item="7",
                field_name="part1_country_citizenship",
                label="Country of Citizenship or Nationality",
                field_type="text",
                is_mapped=True,
                database_mapping="beneficiary.Beneficiary.beneficiaryCitizenOfCountry"
            ),
            "part1_date_birth": FormField(
                form_type="I-539",
                part="1",
                item="8",
                field_name="part1_date_birth",
                label="Date of Birth (mm/dd/yyyy)",
                field_type="date",
                is_mapped=True,
                database_mapping="beneficiary.Beneficiary.beneficiaryDateOfBirth"
            ),
            "part1_ssn": FormField(
                form_type="I-539",
                part="1",
                item="9",
                field_name="part1_ssn",
                label="U.S. Social Security Number (if any)",
                field_type="text",
                is_mapped=True,
                database_mapping="beneficiary.Beneficiary.beneficiarySsn"
            ),
            
            # Entry Information
            "part1_last_arrival": FormField(
                form_type="I-539",
                part="1",
                item="10",
                field_name="part1_last_arrival",
                label="Date of Last Arrival Into the United States",
                field_type="date",
                is_mapped=True,
                database_mapping="beneficiary.I94Details.I94.i94ArrivalDate"
            ),
            "part1_i94_number": FormField(
                form_type="I-539",
                part="1",
                item="11",
                field_name="part1_i94_number",
                label="Form I-94 Arrival-Departure Record Number",
                field_type="text",
                is_mapped=True,
                database_mapping="beneficiary.I94Details.I94.i94Number"
            ),
            "part1_passport_number": FormField(
                form_type="I-539",
                part="1",
                item="12",
                field_name="part1_passport_number",
                label="Passport Number (if any)",
                field_type="text",
                is_mapped=True,
                database_mapping="beneficiary.PassportDetails.Passport.passportNumber"
            ),
            "part1_travel_doc_number": FormField(
                form_type="I-539",
                part="1",
                item="13",
                field_name="part1_travel_doc_number",
                label="Travel Document Number (if any)",
                field_type="text",
                is_mapped=False,
                database_mapping=""
            ),
            "part1_passport_country": FormField(
                form_type="I-539",
                part="1",
                item="14a",
                field_name="part1_passport_country",
                label="Country of Passport or Travel Document Issuance",
                field_type="text",
                is_mapped=True,
                database_mapping="beneficiary.PassportDetails.Passport.passportIssueCountry"
            ),
            "part1_passport_expiry": FormField(
                form_type="I-539",
                part="1",
                item="14b",
                field_name="part1_passport_expiry",
                label="Passport or Travel Document Expiration Date",
                field_type="date",
                is_mapped=True,
                database_mapping="beneficiary.PassportDetails.Passport.passportExpiryDate"
            ),
            "part1_current_status": FormField(
                form_type="I-539",
                part="1",
                item="15a",
                field_name="part1_current_status",
                label="Current Nonimmigrant Status",
                field_type="text",
                is_mapped=True,
                database_mapping="beneficiary.VisaDetails.Visa.visaStatus"
            ),
            "part1_status_expiry": FormField(
                form_type="I-539",
                part="1",
                item="15b",
                field_name="part1_status_expiry",
                label="Date Status Expires",
                field_type="date",
                is_mapped=True,
                database_mapping="beneficiary.VisaDetails.Visa.visaExpiryDate"
            ),
            "part1_duration_status": FormField(
                form_type="I-539",
                part="1",
                item="16",
                field_name="part1_duration_status",
                label="Duration of Status (D/S)",
                field_type="checkbox",
                is_mapped=True,
                database_mapping="If value of beneficiary.VisaDetails.Visa.visaExpiryDate is D/S, then choose yes"
            ),
            
            # Part 2 - Application Type
            "part2_application_type": FormField(
                form_type="I-539",
                part="2",
                item="1",
                field_name="part2_application_type",
                label="I am applying for",
                field_type="radio",
                is_mapped=True,
                database_mapping="based on the value of case.caseSubType -- select the appropriate box"
            ),
            "part2_change_effective_date": FormField(
                form_type="I-539",
                part="2",
                item="3b",
                field_name="part2_change_effective_date",
                label="I am requesting the change to be effective",
                field_type="date",
                is_mapped=True,
                database_mapping="beneficiary.VisaDetails.Visa.new_effective_date",
                is_conditional=True,
                condition="If change of status selected"
            ),
            "part2_change_to_status": FormField(
                form_type="I-539",
                part="2",
                item="3c",
                field_name="part2_change_to_status",
                label="Change to status",
                field_type="text",
                is_mapped=True,
                database_mapping="beneficiary.VisaDetails.Visa.change_of_status",
                is_conditional=True,
                condition="If change of status selected"
            ),
            "part2_number_applicants": FormField(
                form_type="I-539",
                part="2",
                item="4",
                field_name="part2_number_applicants",
                label="Number of people included in this application",
                field_type="radio",
                is_mapped=True,
                database_mapping="If beneficiary.Beneficiary.beneficiary_dependent_count = 0, select only option. If > 0, select family option and enter count +1"
            ),
            "part2_school_name": FormField(
                form_type="I-539",
                part="2",
                item="5",
                field_name="part2_school_name",
                label="The name of the school you will attend",
                field_type="text",
                is_mapped=False,
                database_mapping="",
                is_conditional=True,
                condition="If applicable for Academic/Vocational/Exchange Visitor"
            ),
            "part2_sevis_id": FormField(
                form_type="I-539",
                part="2",
                item="6",
                field_name="part2_sevis_id",
                label="Your Student and Exchange Visitor Information System (SEVIS) ID Number",
                field_type="text",
                is_mapped=False,
                database_mapping="",
                is_conditional=True,
                condition="If applicable"
            ),
            
            # Part 3 - Processing Information
            "part3_extend_until": FormField(
                form_type="I-539",
                part="3",
                item="1",
                field_name="part3_extend_until",
                label="I/We request that my/our current or requested status be extended until",
                field_type="date",
                is_mapped=True,
                database_mapping="beneficiary.VisaDetails.Visa.extension_until"
            ),
            "part3_based_on_family": FormField(
                form_type="I-539",
                part="3",
                item="2",
                field_name="part3_based_on_family",
                label="Is this application based on an extension or change of status already granted to your spouse, child, or parent?",
                field_type="radio",
                is_mapped=False,
                database_mapping="get data from H4 Questionnaire -- Item 1"
            ),
            "part3_separate_petition": FormField(
                form_type="I-539",
                part="3",
                item="3",
                field_name="part3_separate_petition",
                label="Is this application based on a separate petition or application?",
                field_type="radio",
                is_mapped=False,
                database_mapping="get data from H4 Questionnaire -- Item 2a"
            ),
        }
        
        return {"I-539": i539_mappings}
    
    def detect_form_type(self, content: str) -> FormType:
        """Detect the type of form based on content"""
        content_lower = content.lower()
        
        if "i-539" in content_lower or "extend/change nonimmigrant status" in content_lower:
            return FormType.I539
        elif "i-129" in content_lower or "petition for a nonimmigrant worker" in content_lower:
            return FormType.I129
        elif "i-140" in content_lower:
            return FormType.I140
        elif "i-485" in content_lower:
            return FormType.I485
        elif "g-28" in content_lower:
            return FormType.G28
        elif "i-907" in content_lower:
            return FormType.I907
        else:
            return FormType.UNKNOWN
    
    def extract_form_fields(self, content: str, form_type: FormType) -> List[FormField]:
        """Extract fields from form content"""
        if form_type.value in self.form_mappings:
            return list(self.form_mappings[form_type.value].values())
        else:
            # For unknown forms, try to extract fields from content
            return self._extract_generic_fields(content, form_type.value)
    
    def _extract_generic_fields(self, content: str, form_type: str) -> List[FormField]:
        """Extract fields from unknown form types"""
        fields = []
        
        # Look for common patterns like "Item 1:", "Part 1", etc.
        patterns = [
            r'Item\s+(\d+[a-z]?)\.?\s*([^\n\r]+)',
            r'Part\s+(\d+)\.?\s*([^\n\r]+)',
            r'(\d+[a-z]?)\.?\s+([A-Z][^\n\r]+)',
        ]
        
        for i, pattern in enumerate(patterns):
            matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                item_num = match.group(1)
                label = match.group(2).strip()
                
                field = FormField(
                    form_type=form_type,
                    part="Unknown",
                    item=item_num,
                    field_name=f"item_{item_num}",
                    label=label,
                    field_type="text",
                    is_mapped=False,
                    database_mapping=""
                )
                fields.append(field)
        
        return fields[:50]  # Limit to first 50 fields
    
    def create_questionnaire_json(self, fields: List[FormField]) -> Dict[str, Any]:
        """Create questionnaire JSON for unmapped fields"""
        controls = []
        
        for field in fields:
            if not field.is_mapped:
                control = {
                    "name": field.field_name,
                    "label": f"{field.part}_{field.item}. {field.label}",
                    "type": self._map_field_type(field.field_type),
                    "validators": self._get_validators(field.field_type),
                    "style": {"col": "12"}
                }
                
                if field.is_conditional:
                    control["className"] = "hide-dummy-class"
                
                controls.append(control)
                
                # Add notes field for certain types
                if field.field_type in ["colorSwitch", "radio"]:
                    notes_control = {
                        "name": f"{field.field_name}_notes",
                        "label": "Notes",
                        "type": "textarea",
                        "validators": {"required": False},
                        "style": {"col": "12"},
                        "className": "hide-dummy-class"
                    }
                    controls.append(notes_control)
        
        return {"controls": controls}
    
    def _map_field_type(self, field_type: str) -> str:
        """Map field type to questionnaire control type"""
        mapping = {
            "text": "text",
            "date": "date",
            "checkbox": "colorSwitch",
            "radio": "radio",
            "textarea": "textarea",
            "number": "number"
        }
        return mapping.get(field_type, "text")
    
    def _get_validators(self, field_type: str) -> Dict[str, Any]:
        """Get validators based on field type"""
        if field_type == "date":
            return {"required": False}
        elif field_type == "text":
            return {"maxLength": "255"}
        else:
            return {"required": False}

def main():
    st.set_page_config(
        page_title="USCIS Form Mapper & Questionnaire Generator",
        page_icon="📄",
        layout="wide"
    )
    
    st.title("📄 USCIS Form Mapper & Questionnaire Generator")
    st.markdown("Upload USCIS forms to generate field mappings and questionnaires")
    
    # Initialize the form mapper
    mapper = FormMapper()
    
    # File upload
    uploaded_file = st.file_uploader(
        "Upload USCIS Form (PDF or Text)",
        type=['pdf', 'txt', 'docx'],
        help="Upload a USCIS form to analyze its fields and generate mappings"
    )
    
    if uploaded_file is not None:
        # Read file content
        if uploaded_file.type == "text/plain":
            content = str(uploaded_file.read(), "utf-8")
        else:
            content = "Form I-539 Application to Extend/Change Nonimmigrant Status"  # Placeholder
        
        # Detect form type
        form_type = mapper.detect_form_type(content)
        
        st.success(f"✅ Detected Form Type: **{form_type.value}**")
        
        # Extract fields
        fields = mapper.extract_form_fields(content, form_type)
        
        # Create tabs
        tab1, tab2, tab3, tab4 = st.tabs([
            "📋 Field Mappings", 
            "❓ Questionnaire JSON", 
            "📊 Summary Statistics",
            "🔄 Consolidated JSON"
        ])
        
        with tab1:
            st.header("Field Mappings")
            
            # Separate mapped and unmapped fields
            mapped_fields = [f for f in fields if f.is_mapped]
            unmapped_fields = [f for f in fields if not f.is_mapped]
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("🟢 Mapped Fields")
                if mapped_fields:
                    mapped_data = []
                    for field in mapped_fields:
                        mapped_data.append({
                            "Part": field.part,
                            "Item": field.item,
                            "Label": field.label[:50] + "..." if len(field.label) > 50 else field.label,
                            "Database Mapping": field.database_mapping,
                            "Default": field.default_value
                        })
                    
                    df_mapped = pd.DataFrame(mapped_data)
                    st.dataframe(df_mapped, use_container_width=True)
                else:
                    st.info("No mapped fields found")
            
            with col2:
                st.subheader("🔴 Unmapped Fields (Need Questionnaire)")
                if unmapped_fields:
                    unmapped_data = []
                    for field in unmapped_fields:
                        unmapped_data.append({
                            "Part": field.part,
                            "Item": field.item,
                            "Label": field.label[:50] + "..." if len(field.label) > 50 else field.label,
                            "Type": field.field_type,
                            "Conditional": "Yes" if field.is_conditional else "No"
                        })
                    
                    df_unmapped = pd.DataFrame(unmapped_data)
                    st.dataframe(df_unmapped, use_container_width=True)
                else:
                    st.info("All fields are mapped!")
        
        with tab2:
            st.header("Questionnaire JSON for Unmapped Fields")
            
            questionnaire = mapper.create_questionnaire_json(fields)
            
            if questionnaire["controls"]:
                st.json(questionnaire)
                
                # Download button
                json_str = json.dumps(questionnaire, indent=2)
                st.download_button(
                    label="📥 Download Questionnaire JSON",
                    data=json_str,
                    file_name=f"{form_type.value.lower()}_questionnaire.json",
                    mime="application/json"
                )
            else:
                st.success("🎉 All fields are mapped! No questionnaire needed.")
        
        with tab3:
            st.header("Summary Statistics")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Fields", len(fields))
            
            with col2:
                mapped_count = len([f for f in fields if f.is_mapped])
                st.metric("Mapped Fields", mapped_count)
            
            with col3:
                unmapped_count = len([f for f in fields if not f.is_mapped])
                st.metric("Unmapped Fields", unmapped_count)
            
            with col4:
                if len(fields) > 0:
                    coverage = (mapped_count / len(fields)) * 100
                    st.metric("Coverage %", f"{coverage:.1f}%")
                else:
                    st.metric("Coverage %", "0%")
            
            # Coverage chart
            if len(fields) > 0:
                import plotly.express as px
                
                data = {
                    "Status": ["Mapped", "Unmapped"],
                    "Count": [mapped_count, unmapped_count]
                }
                
                fig = px.pie(
                    data, 
                    values="Count", 
                    names="Status",
                    title="Field Mapping Coverage",
                    color_discrete_map={
                        "Mapped": "#28a745",
                        "Unmapped": "#dc3545"
                    }
                )
                
                st.plotly_chart(fig, use_container_width=True)
        
        with tab4:
            st.header("Consolidated JSON Mapping")
            
            consolidated = {
                "form_type": form_type.value,
                "total_fields": len(fields),
                "mapped_fields": len([f for f in fields if f.is_mapped]),
                "unmapped_fields": len([f for f in fields if not f.is_mapped]),
                "field_mappings": {},
                "questionnaire_controls": questionnaire["controls"]
            }
            
            # Add all field mappings
            for field in fields:
                field_data = {
                    "part": field.part,
                    "item": field.item,
                    "label": field.label,
                    "type": field.field_type,
                    "is_mapped": field.is_mapped,
                    "database_mapping": field.database_mapping,
                    "default_value": field.default_value,
                    "is_conditional": field.is_conditional,
                    "condition": field.condition
                }
                consolidated["field_mappings"][field.field_name] = field_data
            
            st.json(consolidated)
            
            # Download button
            consolidated_str = json.dumps(consolidated, indent=2)
            st.download_button(
                label="📥 Download Consolidated JSON",
                data=consolidated_str,
                file_name=f"{form_type.value.lower()}_consolidated_mapping.json",
                mime="application/json"
            )
    
    else:
        st.info("👆 Please upload a USCIS form to begin analysis")
        
        # Show example of supported forms
        st.subheader("Supported Forms")
        supported_forms = [
            "I-539: Application to Extend/Change Nonimmigrant Status",
            "I-129: Petition for a Nonimmigrant Worker", 
            "I-140: Immigrant Petition for Alien Worker",
            "I-485: Application to Register Permanent Residence or Adjust Status",
            "G-28: Notice of Entry of Appearance as Attorney or Accredited Representative",
            "I-907: Request for Premium Processing Service"
        ]
        
        for form in supported_forms:
            st.write(f"• {form}")

if __name__ == "__main__":
    main()
