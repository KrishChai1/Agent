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
    I129DC = "I-129DC"
    I129H = "I-129H"
    I907 = "I-907"
    I539 = "I-539"
    I539A = "I-539A"
    I_G28 = "I-G28"
    I_I907 = "I-I907"
    I765 = "I-765"
    I140 = "I-140"
    I129L = "I-129L"
    I918 = "I-918"
    I_765G28 = "I-765G28"
    I_I140 = "I-I140"
    H_2B = "H-2B"
    ETA_9089 = "ETA-9089"
    I129_TN = "I-129TN"
    I129_T = "I-129T"
    I_131 = "I-131"
    I485 = "I-485"
    I485J = "I-485J"
    I485A = "I-485A"
    I864 = "I-864"
    I864A = "I-864A"
    I129R = "I-129R"
    I829 = "I-829"
    UNKNOWN = "Unknown"

@dataclass
class FormField:
    form_type: str
    pdf_field_name: str
    database_mapping: str
    field_type: str
    label: str = ""
    is_mapped: bool = True
    default_value: str = ""
    is_conditional: bool = False
    condition: str = ""
    group: str = ""
    validators: Dict[str, Any] = None

    def __post_init__(self):
        if self.validators is None:
            self.validators = {}

class USCISFormMapper:
    def __init__(self):
        self.form_mappings = self._load_all_form_mappings()
        self.json_configs = self._load_json_configs()
        
    def _load_all_form_mappings(self) -> Dict[str, List[FormField]]:
        """Load all form mappings from the TypeScript file structure"""
        mappings = {
            "LCA": self._load_lca_mappings(),
            "I-129": self._load_i129_mappings(),
            "G-28": self._load_g28_mappings(),
            "I-129DC": self._load_i129dc_mappings(),
            "I-129H": self._load_i129h_mappings(),
            "I-907": self._load_i907_mappings(),
            "I-539": self._load_i539_mappings(),
            "I-539A": self._load_i539a_mappings(),
            "I-G28": self._load_i_g28_mappings(),
            "I-I907": self._load_i_i907_mappings(),
            "I-765": self._load_i765_mappings(),
            "I-140": self._load_i140_mappings(),
            "I-129L": self._load_i129l_mappings(),
            "I-918": self._load_i918_mappings(),
            "I-765G28": self._load_i_765g28_mappings(),
            "I-I140": self._load_i_i140_mappings(),
            "H-2B": self._load_h2b_mappings(),
            "ETA-9089": self._load_eta9089_mappings(),
            "I-129TN": self._load_i129tn_mappings(),
            "I-129T": self._load_i129t_mappings(),
            "I-131": self._load_i131_mappings(),
            "I-485": self._load_i485_mappings(),
            "I-485J": self._load_i485j_mappings(),
            "I-485A": self._load_i485a_mappings(),
            "I-864": self._load_i864_mappings(),
            "I-864A": self._load_i864a_mappings(),
            "I-129R": self._load_i129r_mappings(),
            "I-829": self._load_i829_mappings()
        }
        return mappings
    
    def _load_lca_mappings(self) -> List[FormField]:
        """Load LCA form mappings"""
        return [
            FormField("LCA", "CaseCase_type", "case.caseType", "TextBox", "Case Type"),
            FormField("LCA", "LcaPosition_job_title", "lca.Lca.positionJobTitle", "TextBox", "Position Job Title"),
            FormField("LCA", "LcaSoc_onet_oes_code", "lca.Lca.socOnetOesCode", "TextBox", "SOC/O*NET/OES Code"),
            FormField("LCA", "LcaSoc_onet_oes_title", "lca.Lca.socOnetOesTitle", "TextBox", "SOC/O*NET/OES Title"),
            FormField("LCA", "LcaFull_time_position", "lca.Lca.fullTimePosition", "CheckBox", "Full Time Position"),
            FormField("LCA", "LcaStart_date", "lca.Lca.startDate", "TextBox", "Start Date"),
            FormField("LCA", "LcaEnd_date", "lca.Lca.endDate", "TextBox", "End Date"),
            FormField("LCA", "CaseCase_sub_type", "case.caseSubType", "TextBox", "Case Sub Type"),
            FormField("LCA", "CustomerCustomer_name", "customer.customer_name", "TextBox", "Customer Name"),
            FormField("LCA", "CustomerCustomer_doing_business", "customer.customer_doing_business", "TextBox", "Customer Doing Business As"),
            FormField("LCA", "EmployerCustomerCustomer_address_idAddress_street", "customer.address_street", "TextBox", "Employer Street Address"),
            FormField("LCA", "EmployerAddressAddress_2", "customer.address_type", "TextBox", "Address Type"),
            FormField("LCA", "EmployerAddressAddress_city", "customer.address_city", "TextBox", "City"),
            FormField("LCA", "EmployerAddressAddress_state", "customer.address_state", "TextBox", "State"),
            FormField("LCA", "EmployerAddressAddress_zip", "customer.address_zip", "TextBox", "ZIP Code"),
            FormField("LCA", "EmployerAddressAddress_country", "customer.address_country", "TextBox", "Country"),
            FormField("LCA", "EmployerCustomerCustomer_signatory_phone", "customer.signatory_work_phone", "TextBox", "Signatory Phone"),
            FormField("LCA", "CustomerCustomer_tax_id", "customer.customer_tax_id", "TextBox", "Tax ID"),
            FormField("LCA", "CustomerCustomer_naics_code", "customer.customer_naics_code", "TextBox", "NAICS Code"),
            FormField("LCA", "EmployerPocSignatorySignatory_last_name", "customer.signatory_last_name", "TextBox", "Signatory Last Name"),
            FormField("LCA", "EmployerPocSignatorySignatory_first_name", "customer.signatory_first_name", "TextBox", "Signatory First Name"),
            FormField("LCA", "EmployerPocSignatorySignatory_job_title", "customer.signatory_job_title", "TextBox", "Signatory Job Title"),
            FormField("LCA", "AttorneyUserLast_name", "attorney.attorneyInfo.lastName", "TextBox", "Attorney Last Name"),
            FormField("LCA", "AttorneyUserFirst_name", "attorney.attorneyInfo.firstName", "TextBox", "Attorney First Name"),
            FormField("LCA", "AttorneyUserEmail_address", "attorney.attorneyInfo.emailAddress", "TextBox", "Attorney Email"),
            FormField("LCA", "Attorney_lawfirm_detailsLaw_firm_name", "attorneyLawfirmDetails.lawfirmDetails.lawFirmName", "TextBox", "Law Firm Name"),
            FormField("LCA", "WageLcaGrossSalary", "lca.Lca.grossSalary", "TextBox", "Gross Salary"),
            FormField("LCA", "LcaSwage_unit", "lca.Lca.swageUnit", "CheckBox", "Wage Unit"),
            FormField("LCA", "WageLcaPrevailing_wage_rate", "lca.Lca.prevailingWateRate", "TextBox", "Prevailing Wage Rate"),
            FormField("LCA", "LcaPwage_unit", "lca.Lca.pwageUnit", "CheckBox", "Prevailing Wage Unit"),
            FormField("LCA", "LcaWage_level", "lca.Lca.wageLevel", "CheckBox", "Wage Level"),
            FormField("LCA", "LcaSource_year", "lca.Lca.sourceYear", "TextBox", "Source Year"),
            FormField("LCA", "CustomerH1_dependent_employer", "customer.h1_dependent_employer", "CheckBox", "H1 Dependent Employer"),
            FormField("LCA", "CustomerWillful_violator", "customer.willful_violator", "CheckBox", "Willful Violator")
        ]
    
    def _load_i129_mappings(self) -> List[FormField]:
        """Load I-129 form mappings"""
        return [
            FormField("I-129", "customercustomer_name_i129", "customer.customer_name", "TextBox", "Customer Name"),
            FormField("I-129", "PET_Postal", "customer.customer_name", "TextBox", "Petitioner Postal"),
            FormField("I-129", "PET_FamilyName", "customer.customer_name", "TextBox", "Petitioner Family Name"),
            FormField("I-129", "PET_GivenName", "customer.customer_name", "TextBox", "Petitioner Given Name"),
            FormField("I-129", "BEN_FamilyName1", "customer.customer_name", "TextBox", "Beneficiary Family Name 1"),
            FormField("I-129", "BEN_GivenName1", "customer.customer_name", "TextBox", "Beneficiary Given Name 1"),
            FormField("I-129", "customersignatory_first", "customer.signatory_first_name", "TextBox", "Signatory First Name"),
            FormField("I-129", "customeraddress_street_i129", "customer.address_street", "TextBox", "Customer Street Address"),
            FormField("I-129", "customeraddress_type_i129", "customer.address_type", "CheckBox", "Address Type"),
            FormField("I-129", "customeraddress_city_i129", "customer.address_city", "TextBox", "City"),
            FormField("I-129", "customeraddress_state_i129", "customer.address_state", "TextBox", "State"),
            FormField("I-129", "customeraddress_zip_i129", "customer.address_zip", "TextBox", "ZIP Code"),
            FormField("I-129", "customeraddress_country_i129", "customer.address_country", "TextBox", "Country"),
            FormField("I-129", "customersignatory_work_phone", "customer.signatory_work_phone", "TextBox", "Work Phone"),
            FormField("I-129", "customersignatory_email_id", "customer.signatory_email_id", "TextBox", "Email"),
            FormField("I-129", "customercustomer_tax_id", "customer.customer_tax_id", "TextBox", "Tax ID"),
            FormField("I-129", "casecaseType", "case.caseType", "TextBox", "Case Type"),
            FormField("I-129", "ApplicationReceipt_1", "beneficary.H1bDetails.H1b.h1bReceiptNumber", "TextBox", "Application Receipt Number"),
            FormField("I-129", "casecaseSubType", "case.caseSubType", "CheckBox", "Case Sub Type"),
            FormField("I-129", "RequestedAction", "case.caseSubType", "CheckBox", "Requested Action"),
            FormField("I-129", "beneficiaryBeneficiarybeneficiaryLastName", "beneficary.Beneficiary.beneficiaryLastName", "TextBox", "Beneficiary Last Name"),
            FormField("I-129", "beneficiaryBeneficiarybeneficiaryFirstName_i129", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary First Name"),
            FormField("I-129", "beneficiaryBeneficiarybeneficiaryDateOfBirth", "beneficary.Beneficiary.beneficiaryDateOfBirth", "TextBox", "Date of Birth"),
            FormField("I-129", "beneficiaryBeneficiarybeneficiaryGender", "beneficary.Beneficiary.beneficiaryGender", "CheckBox", "Gender"),
            FormField("I-129", "ussocialssn_1", "beneficary.Beneficiary.beneficiarySsn", "TextBox", "SSN"),
            FormField("I-129", "Alien#1", "beneficary.Beneficiary.alienNumber", "TextBox", "Alien Number"),
            FormField("I-129", "i94number_1", "beneficary.I94Details.I94.i94Number", "TextBox", "I-94 Number"),
            FormField("I-129", "beneficiaryBeneficiarybeneficiaryCountryOfBirth", "beneficary.Beneficiary.beneficiaryCountryOfBirth", "TextBox", "Country of Birth"),
            FormField("I-129", "beneficiaryBeneficiarybeneficiaryProvinceOfBirth", "beneficary.Beneficiary.stateBirth", "TextBox", "Province of Birth"),
            FormField("I-129", "beneficiaryBeneficiarybeneficiaryCitizenOfCountry", "beneficary.Beneficiary.beneficiaryCitizenOfCountry", "TextBox", "Country of Citizenship"),
            FormField("I-129", "beneficiaryI94DetailsI94i94ArrivalDate", "beneficary.I94Details.I94.i94ArrivalDate", "TextBox", "I-94 Arrival Date"),
            FormField("I-129", "beneficiaryPassportDetailsPassportpassportNumber", "beneficary.PassportDetails.Passport.passportNumber", "TextBox", "Passport Number"),
            FormField("I-129", "beneficiaryPassportDetailsPassportpassportIssueDate", "beneficary.PassportDetails.Passport.passportIssueDate", "TextBox", "Passport Issue Date"),
            FormField("I-129", "beneficiaryPassportDetailsPassportpassportExpiryDate", "beneficary.PassportDetails.Passport.passportExpiryDate", "TextBox", "Passport Expiry Date"),
            FormField("I-129", "beneficiaryPassportDetailsPassportpassportIssueCountry", "beneficary.PassportDetails.Passport.passportIssueCountry", "TextBox", "Passport Issue Country"),
            FormField("I-129", "beneficiaryVisaDetailsVisavisaStatus", "beneficary.VisaDetails.Visa.visaStatus", "TextBox", "Visa Status"),
            FormField("I-129", "beneficiaryVisaDetailsVisavisaExpiryDate", "beneficary.VisaDetails.Visa.visaExpiryDate", "TextBox", "Visa Expiry Date"),
            FormField("I-129", "lcaLcapositionJobTitle", "lca.Lca.positionJobTitle", "TextBox", "Position Job Title"),
            FormField("I-129", "lcaLcalcaNumbe", "lca.Lca.lcaNumber", "TextBox", "LCA Number"),
            FormField("I-129", "lcaLcagrossSalary", "lca.Lca.grossSalary", "TextBox", "Gross Salary"),
            FormField("I-129", "lcaLcaswageUni", "lca.Lca.swageUnit", "TextBox", "Wage Unit"),
            FormField("I-129", "lcaLcastartDate", "lca.Lca.startDate", "TextBox", "Start Date"),
            FormField("I-129", "lcaLcaendDate", "lca.Lca.endDate", "TextBox", "End Date"),
            FormField("I-129", "customercustomer_type_of_business", "customer.customer_type_of_business", "TextBox", "Type of Business"),
            FormField("I-129", "customercustomer_year_established", "customer.customer_year_established", "TextBox", "Year Established"),
            FormField("I-129", "customercustomer_total_employees", "customer.customer_total_employees", "TextBox", "Total Employees"),
            FormField("I-129", "customercustomer_gross_annual_income", "customer.customer_gross_annual_income", "TextBox", "Gross Annual Income"),
            FormField("I-129", "customercustomer_net_annual_income", "customer.customer_net_annual_income", "TextBox", "Net Annual Income")
        ]
    
    def _load_g28_mappings(self) -> List[FormField]:
        """Load G-28 form mappings"""
        return [
            FormField("G-28", "attorneyattorneyInfolastName_g28", "attorney.attorneyInfo.lastName", "TextBox", "Attorney Last Name"),
            FormField("G-28", "ATT_MiddleName", "customer.customer_name", "TextBox", "Attorney Middle Name"),
            FormField("G-28", "attorneyattorneyInfofirstName_g28", "attorney.attorneyInfo.firstName", "TextBox", "Attorney First Name"),
            FormField("G-28", "attorneyaddressaddressStreet_g28", "attorney.address.addressStreet", "TextBox", "Street Address"),
            FormField("G-28", "attorneyaddressaddressType_g28", "attorney.address.addressType", "CheckBox", "Address Type"),
            FormField("G-28", "attorneyaddressaddressNumber_g28", "attorney.address.addressNumber", "TextBox", "Address Number"),
            FormField("G-28", "attorneyaddressaddressCity_g28", "attorney.address.addressCity", "TextBox", "City"),
            FormField("G-28", "attorneyaddressaddressState_g28", "attorney.address.addressState", "TextBox", "State"),
            FormField("G-28", "attorneyaddressaddressZip_g28", "attorney.address.addressZip", "TextBox", "ZIP Code"),
            FormField("G-28", "addressaddress_country_g28", "attorney.address.addressCountry", "TextBox", "Country"),
            FormField("G-28", "attorneyattorneyInfoworkPhone_g28", "attorney.attorneyInfo.workPhone", "TextBox", "Work Phone"),
            FormField("G-28", "ATT_FAX_g28", "attorney.attorneyInfo.faxNumber", "TextBox", "Fax Number"),
            FormField("G-28", "attorneyattorneyInfoemailAddress_g28", "attorney.attorneyInfo.emailAddress", "TextBox", "Email Address"),
            FormField("G-28", "attorneyattorneyInfolicensingAuthority", "attorney.attorneyInfo.licensingAuthority", "TextBox", "Licensing Authority"),
            FormField("G-28", "attorneyattorneyInfostateBarNumber_g28", "attorney.attorneyInfo.stateBarNumber", "TextBox", "State Bar Number"),
            FormField("G-28", "attorneyLawfirmDetailslawfirmDetailslawFirmName_g28", "attorneyLawfirmDetails.lawfirmDetails.lawFirmName", "TextBox", "Law Firm Name"),
            FormField("G-28", "customersignatory_last_name_g28", "customer.signatory_last_name", "TextBox", "Signatory Last Name"),
            FormField("G-28", "customersignatory_first_name_g28", "customer.signatory_first_name", "TextBox", "Signatory First Name"),
            FormField("G-28", "MiddleName", "customer.signatory_middle_name", "TextBox", "Signatory Middle Name"),
            FormField("G-28", "customercustomer_name_g28", "customer.customer_name", "TextBox", "Customer Name"),
            FormField("G-28", "G_28", "customer.customer_name", "CheckBox", "G-28 Checkbox"),
            FormField("G-28", "customersignatory_job_title_g28", "customer.signatory_job_title", "TextBox", "Signatory Job Title"),
            FormField("G-28", "customersignatory_work_phone_g28", "customer.signatory_work_phone", "TextBox", "Signatory Work Phone"),
            FormField("G-28", "customersignatory_email_id_g28", "customer.signatory_email_id", "TextBox", "Signatory Email"),
            FormField("G-28", "customeraddress_street_g28", "customer.address_street", "TextBox", "Customer Street Address"),
            FormField("G-28", "customeraddress_type_g28", "customer.address_type", "CheckBox", "Customer Address Type"),
            FormField("G-28", "customeraddress_number_g28", "customer.address_number", "TextBox", "Customer Address Number"),
            FormField("G-28", "customeraddress_city_g28", "customer.address_city", "TextBox", "Customer City"),
            FormField("G-28", "customeraddress_state_g28", "customer.address_state", "TextBox", "Customer State"),
            FormField("G-28", "customeraddress_zip_g28", "customer.address_zip", "TextBox", "Customer ZIP"),
            FormField("G-28", "customeraddress_country_g28", "customer.address_country", "TextBox", "Customer Country")
        ]
    
    def _load_i539_mappings(self) -> List[FormField]:
        """Load I-539 form mappings"""
        return [
            FormField("I-539", "attorneyStateBarNumber", "attorney.attorneyInfo.stateBarNumber", "TextBox", "Attorney State Bar Number"),
            FormField("I-539", "beneficiaryLastName", "beneficary.Beneficiary.beneficiaryLastName", "TextBox", "Beneficiary Last Name"),
            FormField("I-539", "beneficiaryFirstName", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary First Name"),
            FormField("I-539", "beneficiaryMiddleName", "beneficary.Beneficiary.beneficiaryMiddleName", "TextBox", "Beneficiary Middle Name"),
            FormField("I-539", "beneficiaryName", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary Name"),
            FormField("I-539", "workAddressStreet", "beneficary.WorkAddress.addressStreet", "TextBox", "Work Address Street"),
            FormField("I-539", "workAddressNumber", "beneficary.WorkAddress.addressNumber", "TextBox", "Work Address Number"),
            FormField("I-539", "workAddressCity", "beneficary.WorkAddress.addressCity", "TextBox", "Work Address City"),
            FormField("I-539", "workAddressState", "beneficary.WorkAddress.addressState", "TextBox", "Work Address State"),
            FormField("I-539", "workAddressZip", "beneficary.WorkAddress.addressZip", "TextBox", "Work Address ZIP"),
            FormField("I-539", "homeAddressStreet", "beneficary.HomeAddress.addressStreet", "TextBox", "Home Address Street"),
            FormField("I-539", "homeAddressNumber", "beneficary.HomeAddress.addressNumber", "TextBox", "Home Address Number"),
            FormField("I-539", "homeAddressCity", "beneficary.HomeAddress.addressCity", "TextBox", "Home Address City"),
            FormField("I-539", "homeAddressState", "beneficary.HomeAddress.addressState", "TextBox", "Home Address State"),
            FormField("I-539", "homeAddressZip", "beneficary.HomeAddress.addressZip", "TextBox", "Home Address ZIP"),
            FormField("I-539", "beneficiaryCountryOfBirth", "beneficary.Beneficiary.beneficiaryCountryOfBirth", "TextBox", "Country of Birth"),
            FormField("I-539", "beneficiaryCitizenOfCountry", "beneficary.Beneficiary.beneficiaryCitizenOfCountry", "TextBox", "Country of Citizenship"),
            FormField("I-539", "beneficiaryDateOfBirth", "beneficary.Beneficiary.beneficiaryDateOfBirth", "TextBox", "Date of Birth"),
            FormField("I-539", "i94ArrivalDate", "beneficary.I94Details.I94.i94ArrivalDate", "TextBox", "I-94 Arrival Date"),
            FormField("I-539", "foreignAddressStreet", "beneficary.ForeignAddress.addressStreet", "TextBox", "Foreign Address Street"),
            FormField("I-539", "foreignAddressNumber", "beneficary.ForeignAddress.addressNumber", "TextBox", "Foreign Address Number"),
            FormField("I-539", "foreignAddressCity", "beneficary.ForeignAddress.addressCity", "TextBox", "Foreign Address City"),
            FormField("I-539", "foreignAddressState", "beneficary.ForeignAddress.addressState", "TextBox", "Foreign Address State"),
            FormField("I-539", "foreignAddressZip", "beneficary.ForeignAddress.addressZip", "TextBox", "Foreign Address ZIP"),
            FormField("I-539", "foreignAddressCountry", "beneficary.ForeignAddress.addressCountry", "TextBox", "Foreign Address Country"),
            FormField("I-539", "beneficiaryHomeNumber", "beneficary.Beneficiary.beneficiaryHomeNumber", "TextBox", "Home Phone Number"),
            FormField("I-539", "beneficiaryCellNumber", "beneficary.Beneficiary.beneficiaryCellNumber", "TextBox", "Cell Phone Number"),
            FormField("I-539", "beneficiaryPrimaryEmailAddress", "beneficary.Beneficiary.beneficiaryPrimaryEmailAddress", "TextBox", "Primary Email Address"),
            FormField("I-539", "attorneyLastName", "attorney.attorneyInfo.lastName", "TextBox", "Attorney Last Name"),
            FormField("I-539", "attorneyFirstName", "attorney.attorneyInfo.firstName", "TextBox", "Attorney First Name"),
            FormField("I-539", "attorneyOrgName", "attorneyLawfirmDetails.lawfirmDetails.lawFirmName", "TextBox", "Attorney Organization Name"),
            FormField("I-539", "attorneyHomePhoneNumber", "attorney.attorneyInfo.workPhone", "TextBox", "Attorney Phone Number"),
            FormField("I-539", "attorneyCellNumber", "attorney.attorneyInfo.workPhone", "TextBox", "Attorney Cell Number"),
            FormField("I-539", "attorneyEmail", "attorney.attorneyInfo.emailAddress", "TextBox", "Attorney Email"),
            FormField("I-539", "default", "beneficary.Beneficiary.beneficiaryFirstName", "CheckBox", "Default"),
            FormField("I-539", "workAddressType", "beneficary.WorkAddress.addressType", "CheckBox", "Work Address Type"),
            FormField("I-539", "homeAddressType", "beneficary.HomeAddress.addressType", "CheckBox", "Home Address Type"),
            FormField("I-539", "foreignAddressType", "beneficary.ForeignAddress.addressType", "CheckBox", "Foreign Address Type"),
            FormField("I-539", "reinstatement", "case.caseSubType", "CheckBox", "Reinstatement"),
            FormField("I-539", "ussocialssn_1", "beneficary.Beneficiary.beneficiarySsn", "TextBox", "Social Security Number"),
            FormField("I-539", "Alien#1", "beneficary.Beneficiary.alienNumber", "TextBox", "Alien Number"),
            FormField("I-539", "Anumber1", "beneficary.Beneficiary.alienNumber", "TextBox", "A-Number"),
            FormField("I-539", "i94number_1", "beneficary.I94Details.I94.i94Number", "TextBox", "I-94 Number"),
            FormField("I-539", "additionalLastName", "beneficary.Beneficiary.beneficiaryLastName", "TextBox", "Additional Last Name"),
            FormField("I-539", "additionalFirstName", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Additional First Name"),
            FormField("I-539", "additionalMiddleName", "beneficary.Beneficiary.beneficiaryMiddleName", "TextBox", "Additional Middle Name"),
            FormField("I-539", "schoolName_I539", "beneficary.Beneficiary.h4Info.h4Info.P2_5txt", "TextBox", "School Name"),
            FormField("I-539", "sevisNumber_I539", "beneficary.Beneficiary.h4Info.h4Info.P2_6txt", "TextBox", "SEVIS Number")
        ]
    
    def _load_i129dc_mappings(self) -> List[FormField]:
        """Load I-129DC form mappings"""
        return [
            FormField("I-129DC", "customercustomer_name_i129dc", "customer.customer_name", "TextBox", "Customer Name"),
            FormField("I-129DC", "beneficiaryBeneficiarybeneficiaryFirstName_i129dc", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary First Name"),
            FormField("I-129DC", "customerh1_dependent_employer", "customer.h1_dependent_employer", "CheckBox", "H1 Dependent Employer"),
            FormField("I-129DC", "PartAItem3", "customer.willful_violator", "CheckBox", "Part A Item 3"),
            FormField("I-129DC", "customerwillful_violator", "customer.willful_violator", "CheckBox", "Willful Violator"),
            FormField("I-129DC", "petitioner50", "customer.willful_violator", "CheckBox", "Petitioner 50"),
            FormField("I-129DC", "lcaLcagrossSalary_i129dc", "lca.Lca.grossSalary", "TextBox", "LCA Gross Salary"),
            FormField("I-129DC", "customerhigher_education_institution", "customer.higher_education_institution", "CheckBox", "Higher Education Institution"),
            FormField("I-129DC", "customernonprofit_organization", "customer.nonprofit_organization", "CheckBox", "Nonprofit Organization"),
            FormField("I-129DC", "customernonprofit_research_organization", "customer.nonprofit_research_organization", "CheckBox", "Nonprofit Research Organization"),
            FormField("I-129DC", "PartBItem4", "customer.nonprofit_research_organization", "CheckBox", "Part B Item 4"),
            FormField("I-129DC", "PartBItem5", "customer.nonprofit_clinical_institution", "CheckBox", "Part B Item 5"),
            FormField("I-129DC", "customerprimary_secondary_education_institution", "customer.primary_secondary_education_institution", "CheckBox", "Primary/Secondary Education Institution"),
            FormField("I-129DC", "customernonprofit_clinical_institution", "customer.nonprofit_clinical_institution", "CheckBox", "Nonprofit Clinical Institution"),
            FormField("I-129DC", "PartBItem9Yes", "customer.nonprofit_clinical_institution", "CheckBox", "Part B Item 9 Yes"),
            FormField("I-129DC", "caseh1BPetitionType", "case.h1BPetitionType", "CheckBox", "H1B Petition Type"),
            FormField("I-129DC", "beneficiaryEducationDetailsBeneficiaryEducationdegreeType1", "beneficary.EducationDetails.BeneficiaryEducation.degreeType", "TextBox", "Degree Type"),
            FormField("I-129DC", "DotCode1", "customer.customer_dot_code", "TextBox", "DOT Code"),
            FormField("I-129DC", "NaicsCode1", "customer.customer_naics_code", "TextBox", "NAICS Code")
        ]
    
    def _load_i129h_mappings(self) -> List[FormField]:
        """Load I-129H form mappings"""
        return [
            FormField("I-129H", "customercustomer_name", "customer.customer_name", "TextBox", "Customer Name"),
            FormField("I-129H", "totalbeneficiaries", "customer.customer_name", "TextBox", "Total Beneficiaries"),
            FormField("I-129H", "beneficiaryBeneficiarybeneficiaryFirstName", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary First Name"),
            FormField("I-129H", "beneficiaryBeneficiarybeneficiaryFirstName1", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary First Name 1"),
            FormField("I-129H", "classificationsought", "case.h1BPetitionType", "CheckBox", "Classification Sought"),
            FormField("I-129H", "beneficiaryConfirmationNumber", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary Confirmation Number"),
            FormField("I-129H", "customerguam_cnmi_cap_exemption", "customer.guam_cnmi_cap_exemption", "CheckBox", "Guam CNMI Cap Exemption"),
            FormField("I-129H", "customerguam_cnmi_cap_exemption1", "customer.guam_cnmi_cap_exemption", "CheckBox", "Guam CNMI Cap Exemption 1"),
            FormField("I-129H", "ownershipInterest", "customer.customer_name", "CheckBox", "Ownership Interest"),
            FormField("I-129H", "proposedDuties", "customer.customer_name", "TextBox", "Proposed Duties"),
            FormField("I-129H", "workExp", "customer.customer_name", "TextBox", "Work Experience"),
            FormField("I-129H", "customersignatorysignatory_first_name", "customer.signatory_first_name", "TextBox", "Signatory First Name"),
            FormField("I-129H", "customersignatorysignatory_first_name1", "customer.signatory_first_name", "TextBox", "Signatory First Name 1"),
            FormField("I-129H", "beneficiaryConfirmationNumber", "case.beneficiaryConfirmationNumber", "TextBox", "Beneficiary Confirmation Number")
        ]
    
    def _load_i907_mappings(self) -> List[FormField]:
        """Load I-907 form mappings"""
        return [
            FormField("I-907", "customercustomer_name_i907", "customer.customer_name", "TextBox", "Customer Name"),
            FormField("I-907", "NAME3", "customer.customer_name", "TextBox", "Name 3"),
            FormField("I-907", "G_28", "customer.customer_name", "CheckBox", "G-28"),
            FormField("I-907", "attorneyattorneyInfofirstName1", "attorney.attorneyInfo.firstName", "TextBox", "Attorney First Name"),
            FormField("I-907", "attorneyaddressaddressStreet", "attorney.address.addressStreet", "TextBox", "Attorney Street Address"),
            FormField("I-907", "attorneyaddressaddressType", "attorney.address.addressType", "CheckBox", "Attorney Address Type"),
            FormField("I-907", "attorneyaddressaddressNumber", "attorney.address.addressNumber", "TextBox", "Attorney Address Number"),
            FormField("I-907", "attorneyaddressaddressCity", "attorney.address.addressCity", "TextBox", "Attorney City"),
            FormField("I-907", "attorneyaddressaddressState", "attorney.address.addressState", "TextBox", "Attorney State"),
            FormField("I-907", "attorneyaddressaddressZip", "attorney.address.addressZip", "TextBox", "Attorney ZIP"),
            FormField("I-907", "attorneyaddressaddress_country", "attorney.address.addressCountry", "TextBox", "Attorney Country"),
            FormField("I-907", "customercustomer_name1", "customer.customer_name", "TextBox", "Customer Name 1"),
            FormField("I-907", "customersignatory_last_name", "customer.signatory_last_name", "TextBox", "Signatory Last Name"),
            FormField("I-907", "beneficiaryBeneficiarybeneficiaryFirstName_i907", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary First Name"),
            FormField("I-907", "beneficiaryBeneficiarybeneficiaryLastName_i907", "beneficary.Beneficiary.beneficiaryLastName", "TextBox", "Beneficiary Last Name"),
            FormField("I-907", "BEN_MiddleName", "beneficary.Beneficiary.beneficiaryMiddleName", "TextBox", "Beneficiary Middle Name"),
            FormField("I-907", "customersignatory_first_name", "customer.signatory_first_name", "TextBox", "Signatory First Name"),
            FormField("I-907", "SIG_MiddleName", "customer.signatory_middle_name", "TextBox", "Signatory Middle Name"),
            FormField("I-907", "customersignatory_job_title", "customer.signatory_job_title", "TextBox", "Signatory Job Title"),
            FormField("I-907", "customercustomer_tax_id", "customer.customer_tax_id", "TextBox", "Customer Tax ID"),
            FormField("I-907", "customeraddress_street", "customer.address_street", "TextBox", "Customer Street Address"),
            FormField("I-907", "customeraddress_type", "customer.address_type", "CheckBox", "Customer Address Type"),
            FormField("I-907", "customeraddress_number", "customer.address_number", "TextBox", "Customer Address Number"),
            FormField("I-907", "customeraddress_city", "customer.address_city", "TextBox", "Customer City"),
            FormField("I-907", "customeraddress_state", "customer.address_state", "TextBox", "Customer State"),
            FormField("I-907", "customeraddress_zip", "customer.address_zip", "TextBox", "Customer ZIP"),
            FormField("I-907", "customeraddress_country", "customer.address_country", "TextBox", "Customer Country"),
            FormField("I-907", "attorneyattorneyInfofirstName3", "attorney.attorneyInfo.firstName", "TextBox", "Attorney First Name 3"),
            FormField("I-907", "attorneyattorneyInfoworkPhone", "attorney.attorneyInfo.workPhone", "TextBox", "Attorney Work Phone"),
            FormField("I-907", "BEN_Email", "attorney.attorneyInfo.faxNumber", "TextBox", "Beneficiary Email"),
            FormField("I-907", "attorneyattorneyInfoemailAddress", "attorney.attorneyInfo.emailAddress", "TextBox", "Attorney Email Address"),
            FormField("I-907", "attorneyattorneyInfolastName1", "attorney.attorneyInfo.lastName", "TextBox", "Attorney Last Name 1"),
            FormField("I-907", "attorneyattorneyInfofirstName11", "attorney.attorneyInfo.firstName", "TextBox", "Attorney First Name 11"),
            FormField("I-907", "attorneyLawfirmDetailslawfirmDetailslawFirmName", "attorneyLawfirmDetails.lawfirmDetails.lawFirmName", "TextBox", "Law Firm Name"),
            FormField("I-907", "attorneyaddressaddressStreet1", "attorney.address.addressStreet", "TextBox", "Attorney Street Address 1"),
            FormField("I-907", "attorneyaddressaddressType1", "attorney.address.addressType", "CheckBox", "Attorney Address Type 1"),
            FormField("I-907", "attorneyaddressaddressNumber1", "attorney.address.addressNumber", "TextBox", "Attorney Address Number 1"),
            FormField("I-907", "attorneyaddressaddressCity1", "attorney.address.addressCity", "TextBox", "Attorney City 1"),
            FormField("I-907", "attorneyaddressaddressState1", "attorney.address.addressState", "TextBox", "Attorney State 1"),
            FormField("I-907", "attorneyaddressaddressZip1", "attorney.address.addressZip", "TextBox", "Attorney ZIP 1"),
            FormField("I-907", "attorneyaddressaddress_country1", "attorney.address.addressCountry", "TextBox", "Attorney Country 1"),
            FormField("I-907", "attorneyattorneyInfoworkPhone1", "attorney.attorneyInfo.workPhone", "TextBox", "Attorney Work Phone 1"),
            FormField("I-907", "attorneyattorneyInfoemailAddress1", "attorney.attorneyInfo.emailAddress", "TextBox", "Attorney Email Address 1")
        ]
    
    def _load_i539a_mappings(self) -> List[FormField]:
        """Load I-539A form mappings"""
        return [
            FormField("I-539A", "attorneyStateBarNumber", "attorney.attorneyInfo.stateBarNumber", "TextBox", "Attorney State Bar Number"),
            FormField("I-539A", "beneficiaryLastName", "beneficary.Beneficiary.beneficiaryLastName", "TextBox", "Beneficiary Last Name"),
            FormField("I-539A", "beneficiaryFirstName", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary First Name"),
            FormField("I-539A", "beneficiaryMiddleName", "beneficary.Beneficiary.beneficiaryMiddleName", "TextBox", "Beneficiary Middle Name"),
            FormField("I-539A", "dependentLastName", "beneficary.Beneficiary.beneficiaryLastName", "TextBox", "Dependent Last Name"),
            FormField("I-539A", "dependentFirstName", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Dependent First Name"),
            FormField("I-539A", "dependentMiddleName", "beneficary.Beneficiary.beneficiaryMiddleName", "TextBox", "Dependent Middle Name"),
            FormField("I-539A", "dependentCountryOfBirth", "beneficary.Beneficiary.beneficiaryCountryOfBirth", "TextBox", "Dependent Country of Birth"),
            FormField("I-539A", "dependentCitizenOfCountry", "beneficary.Beneficiary.beneficiaryCitizenOfCountry", "TextBox", "Dependent Country of Citizenship"),
            FormField("I-539A", "dependentDateOfBirth", "beneficary.Beneficiary.beneficiaryDateOfBirth", "TextBox", "Dependent Date of Birth"),
            FormField("I-539A", "i94ArrivalDate", "beneficary.I94Details.I94.i94ArrivalDate", "TextBox", "I-94 Arrival Date"),
            FormField("I-539A", "beneficiaryHomeNumber", "beneficary.Beneficiary.beneficiaryHomeNumber", "TextBox", "Home Phone Number"),
            FormField("I-539A", "beneficiaryCellNumber", "beneficary.Beneficiary.beneficiaryCellNumber", "TextBox", "Cell Phone Number"),
            FormField("I-539A", "beneficiaryPrimaryEmailAddress", "beneficary.Beneficiary.beneficiaryPrimaryEmailAddress", "TextBox", "Primary Email Address"),
            FormField("I-539A", "attorneyLastName", "attorney.attorneyInfo.lastName", "TextBox", "Attorney Last Name"),
            FormField("I-539A", "attorneyFirstName", "attorney.attorneyInfo.firstName", "TextBox", "Attorney First Name"),
            FormField("I-539A", "attorneyOrgName", "attorneyLawfirmDetails.lawfirmDetails.lawFirmName", "TextBox", "Attorney Organization Name"),
            FormField("I-539A", "attorneyHomePhoneNumber", "attorney.attorneyInfo.workPhone", "TextBox", "Attorney Phone Number"),
            FormField("I-539A", "attorneyCellNumber", "attorney.attorneyInfo.mobilePhone", "TextBox", "Attorney Cell Number"),
            FormField("I-539A", "attorneyEmail", "attorney.attorneyInfo.emailAddress", "TextBox", "Attorney Email"),
            FormField("I-539A", "default", "beneficary.Beneficiary.beneficiaryFirstName", "CheckBox", "Default"),
            FormField("I-539A", "dbussocialssn1", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Social Security Number"),
            FormField("I-539A", "dbalien1", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Alien Number"),
            FormField("I-539A", "dbanumber1", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "A-Number"),
            FormField("I-539A", "dbi94number1", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "I-94 Number")
        ]
    
    def _load_i_g28_mappings(self) -> List[FormField]:
        """Load I-G28 form mappings"""
        return [
            FormField("I-G28", "attorneyattorneyInfolastName", "attorney.attorneyInfo.lastName", "TextBox", "Attorney Last Name"),
            FormField("I-G28", "ATT_MiddleName", "beneficary.Beneficiary.beneficiaryLastName", "TextBox", "Attorney Middle Name"),
            FormField("I-G28", "attorneyattorneyInfofirstName", "attorney.attorneyInfo.firstName", "TextBox", "Attorney First Name"),
            FormField("I-G28", "attorneyaddressaddressStreet", "attorney.address.addressStreet", "TextBox", "Attorney Street Address"),
            FormField("I-G28", "attorneyaddressaddressType_ig28", "attorney.address.addressType", "CheckBox", "Attorney Address Type"),
            FormField("I-G28", "attorneyaddressaddressNumber", "attorney.address.addressNumber", "TextBox", "Attorney Address Number"),
            FormField("I-G28", "attorneyaddressaddressCity", "attorney.address.addressCity", "TextBox", "Attorney City"),
            FormField("I-G28", "attorneyaddressaddressState", "attorney.address.addressState", "TextBox", "Attorney State"),
            FormField("I-G28", "attorneyaddressaddressZip", "attorney.address.addressZip", "TextBox", "Attorney ZIP"),
            FormField("I-G28", "addressaddress_country", "attorney.address.addressCountry", "TextBox", "Attorney Country"),
            FormField("I-G28", "attorneyattorneyInfoworkPhone", "attorney.attorneyInfo.workPhone", "TextBox", "Attorney Work Phone"),
            FormField("I-G28", "ATT_FAX", "attorney.attorneyInfo.faxNumber", "TextBox", "Attorney Fax"),
            FormField("I-G28", "attorneyattorneyInfoemailAddress", "attorney.attorneyInfo.emailAddress", "TextBox", "Attorney Email"),
            FormField("I-G28", "attorneyattorneyInfolicensingAuthority", "attorney.attorneyInfo.licensingAuthority", "TextBox", "Licensing Authority"),
            FormField("I-G28", "attorneyattorneyInfostateBarNumber", "attorney.attorneyInfo.stateBarNumber", "TextBox", "State Bar Number"),
            FormField("I-G28", "attorneyLawfirmDetailslawfirmDetailslawFirmName", "attorneyLawfirmDetails.lawfirmDetails.lawFirmName", "TextBox", "Law Firm Name"),
            FormField("I-G28", "customersignatory_last_name", "beneficary.Beneficiary.beneficiaryLastName", "TextBox", "Signatory Last Name"),
            FormField("I-G28", "customersignatory_first_name", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Signatory First Name"),
            FormField("I-G28", "MiddleName", "beneficary.Beneficiary.beneficiaryMiddleName", "TextBox", "Signatory Middle Name"),
            FormField("I-G28", "IG_28", "beneficary.Beneficiary.beneficiaryFirstName", "CheckBox", "IG-28 Checkbox"),
            FormField("I-G28", "customersignatory_work_phone", "beneficary.Beneficiary.beneficiaryWorkNumber", "TextBox", "Signatory Work Phone"),
            FormField("I-G28", "Part2_Cell", "beneficary.Beneficiary.beneficiaryCellNumber", "TextBox", "Cell Phone"),
            FormField("I-G28", "customersignatory_email_id", "beneficary.Beneficiary.beneficiaryPrimaryEmailAddress", "TextBox", "Signatory Email"),
            FormField("I-G28", "customeraddress_street", "beneficary.WorkAddress.addressStreet", "TextBox", "Customer Street Address"),
            FormField("I-G28", "customeraddress_type_ig28", "beneficary.WorkAddress.addressType", "CheckBox", "Customer Address Type"),
            FormField("I-G28", "customeraddress_number", "beneficary.WorkAddress.addressNumber", "TextBox", "Customer Address Number"),
            FormField("I-G28", "customeraddress_city", "beneficary.WorkAddress.addressCity", "TextBox", "Customer City"),
            FormField("I-G28", "customeraddress_state", "beneficary.WorkAddress.addressState", "TextBox", "Customer State"),
            FormField("I-G28", "customeraddress_zip", "beneficary.WorkAddress.addressZip", "TextBox", "Customer ZIP"),
            FormField("I-G28", "customeraddress_country", "beneficary.WorkAddress.addressCountry", "TextBox", "Customer Country"),
            FormField("I-G28", "BEN_FamilyName2", "beneficary.Beneficiary.beneficiaryLastName", "TextBox", "Beneficiary Family Name 2"),
            FormField("I-G28", "BEN_GivenName2", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary Given Name 2"),
            FormField("I-G28", "BEN_MiddleName2", "beneficary.Beneficiary.beneficiaryMiddleName", "TextBox", "Beneficiary Middle Name 2"),
            FormField("I-G28", "BEN_ANumber_1", "beneficary.Beneficiary.alienNumber", "TextBox", "Beneficiary A-Number")
        ]
    
    def _load_i_i907_mappings(self) -> List[FormField]:
        """Load I-I907 form mappings"""
        return [
            FormField("I-I907", "attorneyattorneyInfostateBarNumber", "attorney.attorneyInfo.stateBarNumber", "TextBox", "Attorney State Bar Number"),
            FormField("I-I907", "attorneyattorneyInfolastName", "attorney.attorneyInfo.lastName", "TextBox", "Attorney Last Name"),
            FormField("I-I907", "attorneyattorneyInfofirstName", "attorney.attorneyInfo.firstName", "TextBox", "Attorney First Name"),
            FormField("I-I907", "I_I907", "beneficary.Beneficiary.beneficiaryLastName", "CheckBox", "I-I907 Checkbox"),
            FormField("I-I907", "attorneyattorneyInfofirstName1", "attorney.attorneyInfo.firstName", "TextBox", "Attorney First Name 1"),
            FormField("I-I907", "attorneyaddressaddressStreet", "attorney.address.addressStreet", "TextBox", "Attorney Street Address"),
            FormField("I-I907", "attorneyaddressaddressType", "attorney.address.addressType", "CheckBox", "Attorney Address Type"),
            FormField("I-I907", "attorneyaddressaddressNumber", "attorney.address.addressNumber", "TextBox", "Attorney Address Number"),
            FormField("I-I907", "attorneyaddressaddressCity", "attorney.address.addressCity", "TextBox", "Attorney City"),
            FormField("I-I907", "attorneyaddressaddressState", "attorney.address.addressState", "TextBox", "Attorney State"),
            FormField("I-I907", "attorneyaddressaddressZip", "attorney.address.addressZip", "TextBox", "Attorney ZIP"),
            FormField("I-I907", "attorneyaddressaddress_country", "attorney.address.addressCountry", "TextBox", "Attorney Country"),
            FormField("I-I907", "customercustomer_name1", "beneficary.Beneficiary.beneficiaryLastName", "TextBox", "Customer Name 1"),
            FormField("I-I907", "PETITIONER_FirstName", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Petitioner First Name"),
            FormField("I-I907", "PETITIONER_MiddleName", "beneficary.Beneficiary.beneficiaryMiddleName", "TextBox", "Petitioner Middle Name"),
            FormField("I-I907", "BEN_MiddleName", "beneficary.Beneficiary.beneficiaryMiddleName", "TextBox", "Beneficiary Middle Name"),
            FormField("I-I907", "beneficiaryBeneficiarybeneficiaryFirstName", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary First Name"),
            FormField("I-I907", "beneficiaryBeneficiarybeneficiaryLastName", "beneficary.Beneficiary.beneficiaryLastName", "TextBox", "Beneficiary Last Name"),
            FormField("I-I907", "BEN_FamilyName2", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary Family Name 2"),
            FormField("I-I907", "BEN_GivenName2", "beneficary.Beneficiary.beneficiaryLastName", "TextBox", "Beneficiary Given Name 2"),
            FormField("I-I907", "BEN_MiddleName2", "beneficary.Beneficiary.beneficiaryMiddleName", "TextBox", "Beneficiary Middle Name 2"),
            FormField("I-I907", "customeraddress_street", "beneficary.HomeAddress.addressStreet", "TextBox", "Customer Street Address"),
            FormField("I-I907", "customeraddress_type", "beneficary.HomeAddress.addressType", "CheckBox", "Customer Address Type"),
            FormField("I-I907", "customeraddress_number", "beneficary.HomeAddress.addressNumber", "TextBox", "Customer Address Number"),
            FormField("I-I907", "customeraddress_city", "beneficary.HomeAddress.addressCity", "TextBox", "Customer City"),
            FormField("I-I907", "customeraddress_state", "beneficary.HomeAddress.addressState", "TextBox", "Customer State"),
            FormField("I-I907", "customeraddress_zip", "beneficary.HomeAddress.addressZip", "TextBox", "Customer ZIP"),
            FormField("I-I907", "customeraddress_country", "beneficary.HomeAddress.addressCountry", "TextBox", "Customer Country"),
            FormField("I-I907", "attorneyattorneyInfofirstName3", "attorney.attorneyInfo.firstName", "TextBox", "Attorney First Name 3"),
            FormField("I-I907", "attorneyattorneyInfoworkPhone", "attorney.attorneyInfo.workPhone", "TextBox", "Attorney Work Phone"),
            FormField("I-I907", "BEN_Email", "attorney.attorneyInfo.faxNumber", "TextBox", "Beneficiary Email"),
            FormField("I-I907", "attorneyattorneyInfoemailAddress", "attorney.attorneyInfo.emailAddress", "TextBox", "Attorney Email Address"),
            FormField("I-I907", "attorneyattorneyInfolastName1", "attorney.attorneyInfo.lastName", "TextBox", "Attorney Last Name 1"),
            FormField("I-I907", "attorneyattorneyInfofirstName11", "attorney.attorneyInfo.firstName", "TextBox", "Attorney First Name 11"),
            FormField("I-I907", "attorneyLawfirmDetailslawfirmDetailslawFirmName", "attorneyLawfirmDetails.lawfirmDetails.lawFirmName", "TextBox", "Law Firm Name"),
            FormField("I-I907", "attorneyaddressaddressStreet1", "attorney.address.addressStreet", "TextBox", "Attorney Street Address 1"),
            FormField("I-I907", "attorneyaddressaddressType1", "attorney.address.addressType", "CheckBox", "Attorney Address Type 1"),
            FormField("I-I907", "attorneyaddressaddressNumber1", "attorney.address.addressNumber", "TextBox", "Attorney Address Number 1"),
            FormField("I-I907", "attorneyaddressaddressCity1", "attorney.address.addressCity", "TextBox", "Attorney City 1"),
            FormField("I-I907", "attorneyaddressaddressState1", "attorney.attorneyaddressaddressState", "TextBox", "Attorney State 1"),
            FormField("I-I907", "attorneyaddressaddressZip1", "attorney.address.addressZip", "TextBox", "Attorney ZIP 1"),
            FormField("I-I907", "attorneyaddressaddress_country1", "attorney.address.addressCountry", "TextBox", "Attorney Country 1"),
            FormField("I-I907", "attorneyattorneyInfoworkPhone1", "attorney.attorneyInfo.workPhone", "TextBox", "Attorney Work Phone 1"),
            FormField("I-I907", "attorneyattorneyInfoemailAddress1", "attorney.attorneyInfo.emailAddress", "TextBox", "Attorney Email Address 1"),
            FormField("I-I907", "BEN_ANumber_1", "beneficary.Beneficiary.alienNumber", "TextBox", "Beneficiary A-Number 1"),
            FormField("I-I907", "P3ANumber1", "beneficary.Beneficiary.alienNumber", "TextBox", "P3 A-Number 1")
        ]
    
    def _load_i765_mappings(self) -> List[FormField]:
        """Load I-765 form mappings"""
        return [
            FormField("I-765", "caseType", "case.caseSubType", "CheckBox", "Case Type"),
            FormField("I-765", "beneficiaryLastName", "beneficary.Beneficiary.beneficiaryLastName", "TextBox", "Beneficiary Last Name"),
            FormField("I-765", "beneficiaryFirstName", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary First Name"),
            FormField("I-765", "beneficiaryMiddleName", "beneficary.Beneficiary.beneficiaryMiddleName", "TextBox", "Beneficiary Middle Name"),
            FormField("I-765", "beneficiaryName", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary Name"),
            FormField("I-765", "workAddressStreet", "beneficary.WorkAddress.addressStreet", "TextBox", "Work Address Street"),
            FormField("I-765", "workAddressType", "beneficary.WorkAddress.addressType", "CheckBox", "Work Address Type"),
            FormField("I-765", "workAddressNumber", "beneficary.WorkAddress.addressNumber", "TextBox", "Work Address Number"),
            FormField("I-765", "workAddressCity", "beneficary.WorkAddress.addressCity", "TextBox", "Work Address City"),
            FormField("I-765", "workAddressState", "beneficary.WorkAddress.addressState", "TextBox", "Work Address State"),
            FormField("I-765", "workAddressZip", "beneficary.WorkAddress.addressZip", "TextBox", "Work Address ZIP"),
            FormField("I-765", "homeAddressStreet", "beneficary.HomeAddress.addressStreet", "TextBox", "Home Address Street"),
            FormField("I-765", "homeAddressType", "beneficary.HomeAddress.addressType", "CheckBox", "Home Address Type"),
            FormField("I-765", "homeAddressNumber", "beneficary.HomeAddress.addressNumber", "TextBox", "Home Address Number"),
            FormField("I-765", "homeAddressCity", "beneficary.HomeAddress.addressCity", "TextBox", "Home Address City"),
            FormField("I-765", "homeAddressState", "beneficary.HomeAddress.addressState", "TextBox", "Home Address State"),
            FormField("I-765", "homeAddressZip", "beneficary.HomeAddress.addressZip", "TextBox", "Home Address ZIP"),
            FormField("I-765", "fatherLastName", "beneficary.Beneficiary.fatherLastName", "TextBox", "Father's Last Name"),
            FormField("I-765", "fatherFirstName", "beneficary.Beneficiary.fatherFirstName", "TextBox", "Father's First Name"),
            FormField("I-765", "motherLastName", "beneficary.Beneficiary.motherLastName", "TextBox", "Mother's Last Name"),
            FormField("I-765", "motherFirstName", "beneficary.Beneficiary.motherFirstName", "TextBox", "Mother's First Name"),
            FormField("I-765", "beneficiaryCountryOfBirth", "beneficary.Beneficiary.beneficiaryCountryOfBirth", "TextBox", "Country of Birth"),
            FormField("I-765", "beneficiaryProvinceOfBirth", "beneficary.Beneficiary.beneficiaryProvinceOfBirth", "TextBox", "Province of Birth"),
            FormField("I-765", "stateBirth", "beneficary.Beneficiary.stateBirth", "TextBox", "State of Birth"),
            FormField("I-765", "beneficiaryDateOfBirth", "beneficary.Beneficiary.beneficiaryDateOfBirth", "TextBox", "Date of Birth"),
            FormField("I-765", "i94ArrivalDate", "beneficary.I94Details.I94.i94ArrivalDate", "TextBox", "I-94 Arrival Date"),
            FormField("I-765", "passportNumber", "beneficary.PassportDetails.Passport.passportNumber", "TextBox", "Passport Number"),
            FormField("I-765", "passportIssueCountry", "beneficary.PassportDetails.Passport.passportIssueCountry", "TextBox", "Passport Issue Country"),
            FormField("I-765", "passportExpiryDate", "beneficary.PassportDetails.Passport.passportExpiryDate", "TextBox", "Passport Expiry Date"),
            FormField("I-765", "placeOfLastArrival", "beneficary.I94Details.I94.placeLastArrival", "TextBox", "Place of Last Arrival"),
            FormField("I-765", "statusOfLastArrival", "beneficary.I94Details.I94.statusAtArrival", "TextBox", "Status at Last Arrival"),
            FormField("I-765", "visaStatus", "beneficary.VisaDetails.Visa.visaStatus", "TextBox", "Visa Status"),
            FormField("I-765", "sevis", "beneficary.VisaDetails.Visa.f1SevisNumber", "TextBox", "SEVIS Number"),
            FormField("I-765", "eligibility1", "beneficary.VisaDetails.Visa.eligibilityCategory", "TextBox", "Eligibility Category"),
            FormField("I-765", "beneficiaryHomeNumber", "beneficary.Beneficiary.beneficiaryHomeNumber", "TextBox", "Home Phone Number"),
            FormField("I-765", "beneficiaryCellNumber", "beneficary.Beneficiary.beneficiaryCellNumber", "TextBox", "Cell Phone Number"),
            FormField("I-765", "beneficiaryPrimaryEmailAddress", "beneficary.Beneficiary.beneficiaryPrimaryEmailAddress", "TextBox", "Primary Email Address"),
            FormField("I-765", "attorneyLastName", "attorney.attorneyInfo.lastName", "TextBox", "Attorney Last Name"),
            FormField("I-765", "attorneyFirstName", "attorney.attorneyInfo.firstName", "TextBox", "Attorney First Name"),
            FormField("I-765", "attorneyOrgName", "attorneyLawfirmDetails.lawfirmDetails.lawFirmName", "TextBox", "Attorney Organization Name"),
            FormField("I-765", "attorneyAddressStreet", "attorney.address.addressStreet", "TextBox", "Attorney Street Address"),
            FormField("I-765", "attorneyAddressType", "attorney.address.addressType", "CheckBox", "Attorney Address Type"),
            FormField("I-765", "attorneyAddressNumber", "attorney.address.addressNumber", "TextBox", "Attorney Address Number"),
            FormField("I-765", "attorneyAddressCity", "attorney.address.addressCity", "TextBox", "Attorney City"),
            FormField("I-765", "attorneyAddressState", "attorney.address.addressState", "TextBox", "Attorney State"),
            FormField("I-765", "attorneyAddressZip", "attorney.address.addressZip", "TextBox", "Attorney ZIP"),
            FormField("I-765", "attorneyAddressCountry", "attorney.address.addressCountry", "TextBox", "Attorney Country"),
            FormField("I-765", "attorneyHomePhoneNumber", "attorney.attorneyInfo.workPhone", "TextBox", "Attorney Phone Number"),
            FormField("I-765", "attorneyCellNumber", "attorney.attorneyInfo.workPhone", "TextBox", "Attorney Cell Number"),
            FormField("I-765", "attorneyEmail", "attorney.attorneyInfo.emailAddress", "TextBox", "Attorney Email"),
            FormField("I-765", "default", "beneficary.Beneficiary.beneficiaryFirstName", "CheckBox", "Default"),
            FormField("I-765", "additionalLastName", "beneficary.Beneficiary.beneficiaryLastName", "TextBox", "Additional Last Name"),
            FormField("I-765", "additionalFirstName", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Additional First Name"),
            FormField("I-765", "additionalMiddleName", "beneficary.Beneficiary.beneficiaryMiddleName", "TextBox", "Additional Middle Name"),
            FormField("I-765", "ssn_1", "beneficary.Beneficiary.beneficiarySsn", "TextBox", "Social Security Number"),
            FormField("I-765", "dbalien1_1", "beneficary.Beneficiary.alienNumber", "TextBox", "Alien Number 1"),
            FormField("I-765", "dbi94number1_1", "beneficary.I94Details.I94.i94Number", "TextBox", "I-94 Number 1"),
            FormField("I-765", "uscis2b_1_2", "beneficary.VisaDetails.Visa.spouseUscisReceipt", "TextBox", "USCIS Receipt Number 2"),
            FormField("I-765", "uscis2b_1_3", "beneficary.VisaDetails.Visa.spouseUscisReceipt", "TextBox", "USCIS Receipt Number 3"),
            FormField("I-765", "dbalien1_2", "beneficary.Beneficiary.alienNumber", "TextBox", "Alien Number 2")
        ]
    
    def _load_i140_mappings(self) -> List[FormField]:
        """Load I-140 form mappings"""
        return [
            FormField("I-140", "attorneyStateBarNumber", "attorney.attorneyInfo.stateBarNumber", "TextBox", "Attorney State Bar Number"),
            FormField("I-140", "companyName", "customer.customer_name", "TextBox", "Company Name"),
            FormField("I-140", "careOfName", "customer.signatory_first_name", "TextBox", "Care Of Name"),
            FormField("I-140", "customerAddressStreetNumber", "customer.address_street", "TextBox", "Customer Street Number"),
            FormField("I-140", "customerAddressStreetName", "customer.address_number", "TextBox", "Customer Street Name"),
            FormField("I-140", "customeraddress_type", "customer.address_type", "CheckBox", "Customer Address Type"),
            FormField("I-140", "customerAddressStreetCity", "customer.address_city", "TextBox", "Customer City"),
            FormField("I-140", "customerAddressStreetState", "customer.address_state", "TextBox", "Customer State"),
            FormField("I-140", "customerAddressStreetZip", "customer.address_zip", "TextBox", "Customer ZIP"),
            FormField("I-140", "customerAddressStreetCountry", "customer.address_country", "TextBox", "Customer Country"),
            FormField("I-140", "ein_1", "customer.customer_tax_id", "TextBox", "EIN 1"),
            FormField("I-140", "ein_1_1", "customer.customer_tax_id", "TextBox", "EIN 1-1"),
            FormField("I-140", "beneficiaryLastName", "beneficary.Beneficiary.beneficiaryLastName", "TextBox", "Beneficiary Last Name"),
            FormField("I-140", "beneficiaryFirstName", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary First Name"),
            FormField("I-140", "beneficiaryMiddleName", "beneficary.Beneficiary.beneficiaryMiddleName", "TextBox", "Beneficiary Middle Name"),
            FormField("I-140", "beneficiaryName", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary Name"),
            FormField("I-140", "workAddressStreet", "beneficary.WorkAddress.addressStreet", "TextBox", "Work Address Street"),
            FormField("I-140", "workAddressType", "beneficary.WorkAddress.addressType", "CheckBox", "Work Address Type"),
            FormField("I-140", "workAddressNumber", "beneficary.WorkAddress.addressNumber", "TextBox", "Work Address Number"),
            FormField("I-140", "workAddressCity", "beneficary.WorkAddress.addressCity", "TextBox", "Work Address City"),
            FormField("I-140", "workAddressState", "beneficary.WorkAddress.addressState", "TextBox", "Work Address State"),
            FormField("I-140", "workAddressZip", "beneficary.WorkAddress.addressZip", "TextBox", "Work Address ZIP"),
            FormField("I-140", "workAddressCountry", "beneficary.WorkAddress.addressCountry", "TextBox", "Work Address Country"),
            FormField("I-140", "beneficiaryDateOfBirth", "beneficary.Beneficiary.beneficiaryDateOfBirth", "TextBox", "Date of Birth"),
            FormField("I-140", "beneficiaryCityOfBirth", "beneficary.Beneficiary.beneficiaryProvinceOfBirth", "TextBox", "City of Birth"),
            FormField("I-140", "beneficiaryStateOfBirth", "beneficary.Beneficiary.stateBirth", "TextBox", "State of Birth"),
            FormField("I-140", "beneficiaryCitizenOfCountry", "beneficary.Beneficiary.beneficiaryCitizenOfCountry", "TextBox", "Country of Citizenship"),
            FormField("I-140", "beneficiaryCountryOfBirth", "beneficary.Beneficiary.beneficiaryCountryOfBirth", "TextBox", "Country of Birth"),
            FormField("I-140", "dbalien1", "beneficary.Beneficiary.alienNumber", "TextBox", "Alien Number"),
            FormField("I-140", "ussocialssn_1", "beneficary.Beneficiary.beneficiarySsn", "TextBox", "Social Security Number 1"),
            FormField("I-140", "ssn", "beneficary.Beneficiary.beneficiarySsn", "TextBox", "SSN"),
            FormField("I-140", "i94ArrivalDate", "beneficary.I94Details.I94.i94ArrivalDate", "TextBox", "I-94 Arrival Date"),
            FormField("I-140", "dbi94number1", "beneficary.I94Details.I94.i94Number", "TextBox", "I-94 Number"),
            FormField("I-140", "i94ExpiryDate", "beneficary.I94Details.I94.i94ExpiryDate", "TextBox", "I-94 Expiry Date"),
            FormField("I-140", "statusAtArrival", "beneficary.I94Details.I94.statusAtArrival", "TextBox", "Status at Arrival"),
            FormField("I-140", "passportNumber", "beneficary.PassportDetails.Passport.passportNumber", "TextBox", "Passport Number"),
            FormField("I-140", "passportIssueCountry", "beneficary.PassportDetails.Passport.passportIssueCountry", "TextBox", "Passport Issue Country"),
            FormField("I-140", "passportExpiryDate", "beneficary.PassportDetails.Passport.passportExpiryDate", "TextBox", "Passport Expiry Date"),
            FormField("I-140", "foreignAddressStreet", "beneficary.ForeignAddress.addressNumber", "TextBox", "Foreign Address Street"),
            FormField("I-140", "foreignAddressNumber", "beneficary.ForeignAddress.addressStreet", "TextBox", "Foreign Address Number"),
            FormField("I-140", "foreignAddressCity", "beneficary.ForeignAddress.addressCity", "TextBox", "Foreign Address City"),
            FormField("I-140", "foreignAddressZip", "beneficary.ForeignAddress.addressZip", "TextBox", "Foreign Address ZIP"),
            FormField("I-140", "foreignAddressCountry", "beneficary.ForeignAddress.addressCountry", "TextBox", "Foreign Address Country"),
            FormField("I-140", "foreignAddressProvince", "beneficary.ForeignAddress.addressState", "TextBox", "Foreign Address Province"),
            FormField("I-140", "foreignAddressType", "beneficary.ForeignAddress.addressType", "CheckBox", "Foreign Address Type"),
            FormField("I-140", "typeOfBusiness", "customer.customer_type_of_business", "TextBox", "Type of Business"),
            FormField("I-140", "dateEstablished", "customer.customer_year_established", "TextBox", "Date Established"),
            FormField("I-140", "totalEmployees", "customer.customer_total_employees", "TextBox", "Total Employees"),
            FormField("I-140", "grossAnnualIncome", "customer.customer_gross_annual_income", "TextBox", "Gross Annual Income"),
            FormField("I-140", "netAnnualIncome", "customer.customer_net_annual_income", "TextBox", "Net Annual Income"),
            FormField("I-140", "NaicsCode1", "customer.customer_naics_code", "TextBox", "NAICS Code"),
            FormField("I-140", "signatoryLastName", "customer.signatory_last_name", "TextBox", "Signatory Last Name"),
            FormField("I-140", "signatoryFirstName", "customer.signatory_first_name", "TextBox", "Signatory First Name"),
            FormField("I-140", "signatoryTitle", "customer.signatory_job_title", "TextBox", "Signatory Title"),
            FormField("I-140", "signatoryWorkPhone", "customer.signatory_work_phone", "TextBox", "Signatory Work Phone"),
            FormField("I-140", "signatoryEmail", "customer.signatory_email_id", "TextBox", "Signatory Email"),
            FormField("I-140", "default", "beneficary.Beneficiary.beneficiaryFirstName", "CheckBox", "Default"),
            FormField("I-140", "additionalLastName", "beneficary.Beneficiary.beneficiaryLastName", "TextBox", "Additional Last Name"),
            FormField("I-140", "additionalFirstName", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Additional First Name"),
            FormField("I-140", "additionalMiddleName", "beneficary.Beneficiary.beneficiaryMiddleName", "TextBox", "Additional Middle Name"),
            FormField("I-140", "attorneyattorneyInfolastName1", "attorney.attorneyInfo.lastName", "TextBox", "Attorney Last Name 1"),
            FormField("I-140", "attorneyattorneyInfofirstName11", "attorney.attorneyInfo.firstName", "TextBox", "Attorney First Name 11"),
            FormField("I-140", "attorneyLawfirmDetailslawfirmDetailslawFirmName", "attorneyLawfirmDetails.lawfirmDetails.lawFirmName", "TextBox", "Law Firm Name"),
            FormField("I-140", "attorneyattorneyInfoworkPhone1", "attorney.attorneyInfo.workPhone", "TextBox", "Attorney Work Phone 1"),
            FormField("I-140", "ATT_MobileNumber", "attorney.attorneyInfo.workPhone", "TextBox", "Attorney Mobile Number"),
            FormField("I-140", "attorneyattorneyInfoemailAddress1", "attorney.attorneyInfo.emailAddress", "TextBox", "Attorney Email Address 1")
        ]
    
    def _load_i129l_mappings(self) -> List[FormField]:
        """Load I-129L form mappings"""
        return [
            FormField("I-129L", "customercustomer_name", "customer.customer_name", "TextBox", "Customer Name"),
            FormField("I-129L", "beneficiaryBeneficiarybeneficiaryFirstName", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary First Name"),
            FormField("I-129L", "default", "case.h1BPetitionType", "CheckBox", "Default")
        ]
    
    def _load_i918_mappings(self) -> List[FormField]:
        """Load I-918 form mappings"""
        return [
            FormField("I-918", "stateBarNumber", "attorney.attorneyInfo.stateBarNumber", "TextBox", "State Bar Number"),
            FormField("I-918", "beneficiaryLastName", "beneficary.Beneficiary.beneficiaryLastName", "TextBox", "Beneficiary Last Name"),
            FormField("I-918", "beneficiaryFirstName", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary First Name"),
            FormField("I-918", "beneficiaryMiddleName", "beneficary.Beneficiary.beneficiaryMiddleName", "TextBox", "Beneficiary Middle Name"),
            FormField("I-918", "homeAddressAddressStreet", "beneficary.HomeAddress.addressStreet", "TextBox", "Home Address Street"),
            FormField("I-918", "homeAddressType", "beneficary.HomeAddress.addressType", "CheckBox", "Home Address Type"),
            FormField("I-918", "homeAddressAddressNumber", "beneficary.HomeAddress.addressNumber", "TextBox", "Home Address Number"),
            FormField("I-918", "homeAddressAddressCity", "beneficary.HomeAddress.addressCity", "TextBox", "Home Address City"),
            FormField("I-918", "homeAddressAddressState", "beneficary.HomeAddress.addressState", "TextBox", "Home Address State"),
            FormField("I-918", "homeAddressAddressZip", "beneficary.HomeAddress.addressZip", "TextBox", "Home Address ZIP"),
            FormField("I-918", "homeAddressAddressCountry", "beneficary.HomeAddress.country", "TextBox", "Home Address Country"),
            FormField("I-918", "beneficiaryName", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary Name"),
            FormField("I-918", "workAddressAddressStreet", "beneficary.WorkAddress.addressStreet", "TextBox", "Work Address Street"),
            FormField("I-918", "workAddressType", "beneficary.WorkAddress.addressType", "CheckBox", "Work Address Type"),
            FormField("I-918", "workAddressAddressNumber", "beneficary.WorkAddress.addressNumber", "TextBox", "Work Address Number"),
            FormField("I-918", "workAddressAddressCity", "beneficary.WorkAddress.addressCity", "TextBox", "Work Address City"),
            FormField("I-918", "workAddressAddressState", "beneficary.WorkAddress.addressState", "TextBox", "Work Address State"),
            FormField("I-918", "workAddressAddressZip", "beneficary.WorkAddress.addressZip", "TextBox", "Work Address ZIP"),
            FormField("I-918", "workAddressAddressCountry", "beneficary.WorkAddress.addressCountry", "TextBox", "Work Address Country"),
            FormField("I-918", "dbalien1", "beneficary.Beneficiary.alienNumber", "TextBox", "Alien Number"),
            FormField("I-918", "ssn", "beneficary.Beneficiary.beneficiarySsn", "TextBox", "Social Security Number"),
            FormField("I-918", "beneficiaryDateOfBirth", "beneficary.Beneficiary.beneficiaryDateOfBirth", "TextBox", "Date of Birth"),
            FormField("I-918", "beneficiaryCountryOfBirth", "beneficary.Beneficiary.beneficiaryCountryOfBirth", "TextBox", "Country of Birth"),
            FormField("I-918", "beneficiaryCitizenOfCountry", "beneficary.Beneficiary.beneficiaryCitizenOfCountry", "TextBox", "Country of Citizenship"),
            FormField("I-918", "dbi94number1", "beneficary.I94Details.I94.i94Number", "TextBox", "I-94 Number"),
            FormField("I-918", "passportNumber", "beneficary.PassportDetails.Passport.passportNumber", "TextBox", "Passport Number"),
            FormField("I-918", "passportIssueCountry", "beneficary.PassportDetails.Passport.passportIssueCountry", "TextBox", "Passport Issue Country"),
            FormField("I-918", "passportIssueDate", "beneficary.PassportDetails.Passport.passportIssueDate", "TextBox", "Passport Issue Date"),
            FormField("I-918", "passportExpiryDate", "beneficary.PassportDetails.Passport.passportExpiryDate", "TextBox", "Passport Expiry Date"),
            FormField("I-918", "i94ArrivalDate", "beneficary.I94Details.I94.i94ArrivalDate", "TextBox", "I-94 Arrival Date"),
            FormField("I-918", "i94ExpiryDate", "beneficary.I94Details.I94.i94ExpiryDate", "TextBox", "I-94 Expiry Date"),
            FormField("I-918", "foreignAddressAddressStreet", "beneficary.ForeignAddress.addressNumber", "TextBox", "Foreign Address Street"),
            FormField("I-918", "foreignAddressAddressNumber", "beneficary.ForeignAddress.addressStreet", "TextBox", "Foreign Address Number"),
            FormField("I-918", "foreignAddressAddressCity", "beneficary.ForeignAddress.addressCity", "TextBox", "Foreign Address City"),
            FormField("I-918", "foreignAddressAddressZip", "beneficary.ForeignAddress.addressZip", "TextBox", "Foreign Address ZIP"),
            FormField("I-918", "foreignAddressAddressCountry", "beneficary.ForeignAddress.addressCountry", "TextBox", "Foreign Address Country"),
            FormField("I-918", "foreignAddressAddressState", "beneficary.ForeignAddress.addressState", "TextBox", "Foreign Address State"),
            FormField("I-918", "foreignAddressType", "beneficary.ForeignAddress.addressType", "CheckBox", "Foreign Address Type"),
            FormField("I-918", "beneficiaryHomeNumber", "beneficary.Beneficiary.beneficiaryHomeNumber", "TextBox", "Home Phone Number"),
            FormField("I-918", "beneficiaryCellNumber", "beneficary.Beneficiary.beneficiaryCellNumber", "TextBox", "Cell Phone Number"),
            FormField("I-918", "beneficiaryPrimaryEmailAddress", "beneficary.Beneficiary.beneficiaryPrimaryEmailAddress", "TextBox", "Primary Email Address"),
            FormField("I-918", "attorneyLastName", "attorney.attorneyInfo.lastName", "TextBox", "Attorney Last Name"),
            FormField("I-918", "attorneyFirstName", "attorney.attorneyInfo.firstName", "TextBox", "Attorney First Name"),
            FormField("I-918", "attorneyLawFirmName", "attorneyLawfirmDetails.lawfirmDetails.lawFirmName", "TextBox", "Law Firm Name"),
            FormField("I-918", "attorneyAddressStreet", "attorney.address.addressStreet", "TextBox", "Attorney Street Address"),
            FormField("I-918", "attorneyAddressNumber", "attorney.address.addressNumber", "TextBox", "Attorney Address Number"),
            FormField("I-918", "attorneyAddressCity", "attorney.address.addressCity", "TextBox", "Attorney City"),
            FormField("I-918", "attorneyAddressState", "attorney.address.addressState", "TextBox", "Attorney State"),
            FormField("I-918", "attorneyAddressZip", "attorney.address.addressZip", "TextBox", "Attorney ZIP"),
            FormField("I-918", "attorneyAddressType", "attorney.address.addressType", "CheckBox", "Attorney Address Type"),
            FormField("I-918", "attorneyAddress_country", "attorney.address.addressCountry", "TextBox", "Attorney Country"),
            FormField("I-918", "default", "beneficary.Beneficiary.beneficiaryFirstName", "CheckBox", "Default"),
            FormField("I-918", "beneficiaryLastName1", "beneficary.Beneficiary.beneficiaryLastName", "TextBox", "Beneficiary Last Name 1"),
            FormField("I-918", "beneficiaryFirstName1", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary First Name 1"),
            FormField("I-918", "beneficiaryMiddleName1", "beneficary.Beneficiary.beneficiaryMiddleName", "TextBox", "Beneficiary Middle Name 1"),
            FormField("I-918", "dbanumber1", "beneficary.Beneficiary.alienNumber", "TextBox", "A-Number 1")
        ]
    
    def _load_i_765g28_mappings(self) -> List[FormField]:
        """Load I-765G28 form mappings"""
        return [
            FormField("I-765G28", "attorneyattorneyInfolastName", "attorney.attorneyInfo.lastName", "TextBox", "Attorney Last Name"),
            FormField("I-765G28", "ATT_MiddleName", "beneficary.Beneficiary.beneficiaryLastName", "TextBox", "Attorney Middle Name"),
            FormField("I-765G28", "attorneyattorneyInfofirstName", "attorney.attorneyInfo.firstName", "TextBox", "Attorney First Name"),
            FormField("I-765G28", "attorneyaddressaddressStreet", "attorney.address.addressStreet", "TextBox", "Attorney Street Address"),
            FormField("I-765G28", "attorneyaddressaddressType_i765g28", "attorney.address.addressType", "CheckBox", "Attorney Address Type"),
            FormField("I-765G28", "attorneyaddressaddressNumber", "attorney.address.addressNumber", "TextBox", "Attorney Address Number"),
            FormField("I-765G28", "attorneyaddressaddressCity", "attorney.address.addressCity", "TextBox", "Attorney City"),
            FormField("I-765G28", "attorneyaddressaddressState", "attorney.address.addressState", "TextBox", "Attorney State"),
            FormField("I-765G28", "attorneyaddressaddressZip", "attorney.address.addressZip", "TextBox", "Attorney ZIP"),
            FormField("I-765G28", "addressaddress_country", "attorney.address.addressCountry", "TextBox", "Attorney Country"),
            FormField("I-765G28", "attorneyattorneyInfoworkPhone", "attorney.attorneyInfo.workPhone", "TextBox", "Attorney Work Phone"),
            FormField("I-765G28", "ATT_FAX", "attorney.attorneyInfo.faxNumber", "TextBox", "Attorney Fax"),
            FormField("I-765G28", "attorneyattorneyInfoemailAddress", "attorney.attorneyInfo.emailAddress", "TextBox", "Attorney Email"),
            FormField("I-765G28", "attorneyattorneyInfolicensingAuthority", "attorney.attorneyInfo.licensingAuthority", "TextBox", "Licensing Authority"),
            FormField("I-765G28", "attorneyattorneyInfostateBarNumber", "attorney.attorneyInfo.stateBarNumber", "TextBox", "State Bar Number"),
            FormField("I-765G28", "attorneyLawfirmDetailslawfirmDetailslawFirmName", "attorneyLawfirmDetails.lawfirmDetails.lawFirmName", "TextBox", "Law Firm Name"),
            FormField("I-765G28", "customersignatory_last_name", "beneficary.Beneficiary.beneficiaryLastName", "TextBox", "Signatory Last Name"),
            FormField("I-765G28", "customersignatory_first_name", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Signatory First Name"),
            FormField("I-765G28", "MiddleName", "beneficary.Beneficiary.beneficiaryMiddleName", "TextBox", "Signatory Middle Name"),
            FormField("I-765G28", "IG_28", "beneficary.Beneficiary.beneficiaryFirstName", "CheckBox", "IG-28 Checkbox"),
            FormField("I-765G28", "customersignatory_work_phone", "beneficary.Beneficiary.beneficiaryWorkNumber", "TextBox", "Signatory Work Phone"),
            FormField("I-765G28", "Part2_Cell", "beneficary.Beneficiary.beneficiaryCellNumber", "TextBox", "Cell Phone"),
            FormField("I-765G28", "customersignatory_email_id", "beneficary.Beneficiary.beneficiaryPrimaryEmailAddress", "TextBox", "Signatory Email"),
            FormField("I-765G28", "customeraddress_street", "beneficary.WorkAddress.addressStreet", "TextBox", "Customer Street Address"),
            FormField("I-765G28", "customeraddress_type_i765g28", "beneficary.WorkAddress.addressType", "CheckBox", "Customer Address Type"),
            FormField("I-765G28", "customeraddress_number", "beneficary.WorkAddress.addressNumber", "TextBox", "Customer Address Number"),
            FormField("I-765G28", "customeraddress_city", "beneficary.WorkAddress.addressCity", "TextBox", "Customer City"),
            FormField("I-765G28", "customeraddress_state", "beneficary.WorkAddress.addressState", "TextBox", "Customer State"),
            FormField("I-765G28", "customeraddress_zip", "beneficary.WorkAddress.addressZip", "TextBox", "Customer ZIP"),
            FormField("I-765G28", "customeraddress_country", "beneficary.WorkAddress.addressCountry", "TextBox", "Customer Country"),
            FormField("I-765G28", "BEN_FamilyName2", "beneficary.Beneficiary.beneficiaryLastName", "TextBox", "Beneficiary Family Name 2"),
            FormField("I-765G28", "BEN_GivenName2", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary Given Name 2"),
            FormField("I-765G28", "BEN_MiddleName2", "beneficary.Beneficiary.beneficiaryMiddleName", "TextBox", "Beneficiary Middle Name 2"),
            FormField("I-765G28", "BEN_ANumber_1", "beneficary.Beneficiary.alienNumber", "TextBox", "Beneficiary A-Number")
        ]
    
    def _load_i_i140_mappings(self) -> List[FormField]:
        """Load I-I140 form mappings"""
        return [
            FormField("I-I140", "attorneyStateBarNumber", "attorney.attorneyInfo.stateBarNumber", "TextBox", "Attorney State Bar Number"),
            FormField("I-I140", "beneficiaryLastName1", "beneficary.Beneficiary.beneficiaryLastName", "TextBox", "Beneficiary Last Name 1"),
            FormField("I-I140", "beneficiaryFirstName1", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary First Name 1"),
            FormField("I-I140", "beneficiaryMiddleName1", "beneficary.Beneficiary.beneficiaryMiddleName", "TextBox", "Beneficiary Middle Name 1"),
            FormField("I-I140", "careOfName", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Care Of Name"),
            FormField("I-I140", "customerAddressStreetNumber", "beneficary.WorkAddress.addressStreet", "TextBox", "Customer Street Number"),
            FormField("I-I140", "customerAddressStreetName", "beneficary.WorkAddress.addressNumber", "TextBox", "Customer Street Name"),
            FormField("I-I140", "customeraddress_type", "beneficary.WorkAddress.addressType", "CheckBox", "Customer Address Type"),
            FormField("I-I140", "customerAddressStreetCity", "beneficary.WorkAddress.addressCity", "TextBox", "Customer City"),
            FormField("I-I140", "customerAddressStreetState", "beneficary.WorkAddress.addressState", "TextBox", "Customer State"),
            FormField("I-I140", "customerAddressStreetZip", "beneficary.WorkAddress.addressZip", "TextBox", "Customer ZIP"),
            FormField("I-I140", "customerAddressStreetCountry", "beneficary.WorkAddress.addressCountry", "TextBox", "Customer Country"),
            FormField("I-I140", "ssn", "beneficary.Beneficiary.beneficiarySsn", "TextBox", "Social Security Number"),
            FormField("I-I140", "beneficiaryLastName", "beneficary.Beneficiary.beneficiaryLastName", "TextBox", "Beneficiary Last Name"),
            FormField("I-I140", "beneficiaryFirstName", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary First Name"),
            FormField("I-I140", "beneficiaryMiddleName", "beneficary.Beneficiary.beneficiaryMiddleName", "TextBox", "Beneficiary Middle Name"),
            FormField("I-I140", "beneficiaryName", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary Name"),
            FormField("I-I140", "workAddressStreet", "beneficary.WorkAddress.addressStreet", "TextBox", "Work Address Street"),
            FormField("I-I140", "workAddressType", "beneficary.WorkAddress.addressType", "CheckBox", "Work Address Type"),
            FormField("I-I140", "workAddressNumber", "beneficary.WorkAddress.addressNumber", "TextBox", "Work Address Number"),
            FormField("I-I140", "workAddressCity", "beneficary.WorkAddress.addressCity", "TextBox", "Work Address City"),
            FormField("I-I140", "workAddressState", "beneficary.WorkAddress.addressState", "TextBox", "Work Address State"),
            FormField("I-I140", "workAddressZip", "beneficary.WorkAddress.addressZip", "TextBox", "Work Address ZIP"),
            FormField("I-I140", "workAddressCountry", "beneficary.WorkAddress.addressCountry", "TextBox", "Work Address Country"),
            FormField("I-I140", "beneficiaryDateOfBirth", "beneficary.Beneficiary.beneficiaryDateOfBirth", "TextBox", "Date of Birth"),
            FormField("I-I140", "beneficiaryCityOfBirth", "beneficary.Beneficiary.beneficiaryProvinceOfBirth", "TextBox", "City of Birth"),
            FormField("I-I140", "beneficiaryStateOfBirth", "beneficary.Beneficiary.stateBirth", "TextBox", "State of Birth"),
            FormField("I-I140", "beneficiaryCitizenOfCountry", "beneficary.Beneficiary.beneficiaryCitizenOfCountry", "TextBox", "Country of Citizenship"),
            FormField("I-I140", "beneficiaryCountryOfBirth", "beneficary.Beneficiary.beneficiaryCountryOfBirth", "TextBox", "Country of Birth"),
            FormField("I-I140", "dbalien1", "beneficary.Beneficiary.alienNumber", "TextBox", "Alien Number"),
            FormField("I-I140", "ussocialssn_1", "beneficary.Beneficiary.beneficiarySsn", "TextBox", "Social Security Number 1"),
            FormField("I-I140", "i94ArrivalDate", "beneficary.I94Details.I94.i94ArrivalDate", "TextBox", "I-94 Arrival Date"),
            FormField("I-I140", "dbi94number1", "beneficary.I94Details.I94.i94Number", "TextBox", "I-94 Number"),
            FormField("I-I140", "i94ExpiryDate", "beneficary.I94Details.I94.i94ExpiryDate", "TextBox", "I-94 Expiry Date"),
            FormField("I-I140", "statusAtArrival", "beneficary.I94Details.I94.statusAtArrival", "TextBox", "Status at Arrival"),
            FormField("I-I140", "passportNumber", "beneficary.PassportDetails.Passport.passportNumber", "TextBox", "Passport Number"),
            FormField("I-I140", "passportIssueCountry", "beneficary.PassportDetails.Passport.passportIssueCountry", "TextBox", "Passport Issue Country"),
            FormField("I-I140", "passportExpiryDate", "beneficary.PassportDetails.Passport.passportExpiryDate", "TextBox", "Passport Expiry Date"),
            FormField("I-I140", "foreignAddressStreet", "beneficary.ForeignAddress.addressNumber", "TextBox", "Foreign Address Street"),
            FormField("I-I140", "foreignAddressNumber", "beneficary.ForeignAddress.addressStreet", "TextBox", "Foreign Address Number"),
            FormField("I-I140", "foreignAddressCity", "beneficary.ForeignAddress.addressCity", "TextBox", "Foreign Address City"),
            FormField("I-I140", "foreignAddressZip", "beneficary.ForeignAddress.addressZip", "TextBox", "Foreign Address ZIP"),
            FormField("I-I140", "foreignAddressCountry", "beneficary.ForeignAddress.addressCountry", "TextBox", "Foreign Address Country"),
            FormField("I-I140", "foreignAddressProvince", "beneficary.ForeignAddress.addressState", "TextBox", "Foreign Address Province"),
            FormField("I-I140", "foreignAddressType", "beneficary.ForeignAddress.addressType", "CheckBox", "Foreign Address Type"),
            FormField("I-I140", "signatoryLastName", "beneficary.Beneficiary.beneficiaryLastName", "TextBox", "Signatory Last Name"),
            FormField("I-I140", "signatoryFirstName", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Signatory First Name"),
            FormField("I-I140", "signatoryWorkPhone", "beneficary.Beneficiary.beneficiaryCellNumber", "TextBox", "Signatory Work Phone"),
            FormField("I-I140", "signatoryEmail", "beneficary.Beneficiary.beneficiaryPrimaryEmailAddress", "TextBox", "Signatory Email"),
            FormField("I-I140", "default", "beneficary.Beneficiary.beneficiaryFirstName", "CheckBox", "Default"),
            FormField("I-I140", "additionalLastName", "beneficary.Beneficiary.beneficiaryLastName", "TextBox", "Additional Last Name"),
            FormField("I-I140", "additionalFirstName", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Additional First Name"),
            FormField("I-I140", "additionalMiddleName", "beneficary.Beneficiary.beneficiaryMiddleName", "TextBox", "Additional Middle Name"),
            FormField("I-I140", "attorneyattorneyInfolastName1", "attorney.attorneyInfo.lastName", "TextBox", "Attorney Last Name 1"),
            FormField("I-I140", "attorneyattorneyInfofirstName11", "attorney.attorneyInfo.firstName", "TextBox", "Attorney First Name 11"),
            FormField("I-I140", "attorneyLawfirmDetailslawfirmDetailslawFirmName", "attorneyLawfirmDetails.lawfirmDetails.lawFirmName", "TextBox", "Law Firm Name"),
            FormField("I-I140", "attorneyattorneyInfoworkPhone1", "attorney.attorneyInfo.workPhone", "TextBox", "Attorney Work Phone 1"),
            FormField("I-I140", "ATT_MobileNumber", "attorney.attorneyInfo.workPhone", "TextBox", "Attorney Mobile Number"),
            FormField("I-I140", "attorneyattorneyInfoemailAddress1", "attorney.attorneyInfo.emailAddress", "TextBox", "Attorney Email Address 1")
        ]
    
    def _load_h2b_mappings(self) -> List[FormField]:
        """Load H-2B form mappings"""
        return [
            FormField("H-2B", "customer_name", "customer.customer_name", "TextBox", "Customer Name"),
            FormField("H-2B", "beneficiaryFirstName", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary First Name"),
            FormField("H-2B", "beneficiaryFirstName1", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary First Name 1"),
            FormField("H-2B", "customerguam_cnmi_cap_exemption", "customer.guam_cnmi_cap_exemption", "CheckBox", "Guam CNMI Cap Exemption"),
            FormField("H-2B", "customerguam_cnmi_cap_exemption1", "customer.guam_cnmi_cap_exemption", "CheckBox", "Guam CNMI Cap Exemption 1"),
            FormField("H-2B", "petitionerName1", "customer.signatory_first_name", "TextBox", "Petitioner Name 1"),
            FormField("H-2B", "employerName1", "customer.signatory_job_title", "TextBox", "Employer Name 1"),
            FormField("H-2B", "default", "beneficary.Beneficiary.beneficiaryFirstName", "CheckBox", "Default")
        ]
    
    def _load_eta9089_mappings(self) -> List[FormField]:
        """Load ETA-9089 form mappings"""
        return [
            FormField("ETA-9089", "page2_c1", "attorney.attorneyInfo.lastName", "TextBox", "Attorney Last Name"),
            FormField("ETA-9089", "page2_c2", "attorney.attorneyInfo.firstName", "TextBox", "Attorney First Name"),
            FormField("ETA-9089", "page2_c3", "attorney.attorneyInfo.middleName", "TextBox", "Attorney Middle Name"),
            FormField("ETA-9089", "page2_c4", "attorneyLawfirmDetails.lawfirmDetails.lawFirmName", "TextBox", "Law Firm Name"),
            FormField("ETA-9089", "page2_d1", "customer.signatory_last_name", "TextBox", "Signatory Last Name"),
            FormField("ETA-9089", "page2_d2", "customer.signatory_first_name", "TextBox", "Signatory First Name"),
            FormField("ETA-9089", "page2_d3", "customer.signatory_middle_name", "TextBox", "Signatory Middle Name"),
            FormField("ETA-9089", "page2_d4", "customer.signatory_job_title", "TextBox", "Signatory Job Title"),
            FormField("ETA-9089", "page3_a1", "beneficary.Beneficiary.beneficiaryLastName", "TextBox", "Beneficiary Last Name"),
            FormField("ETA-9089", "page3_a2", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary First Name"),
            FormField("ETA-9089", "page3_a3", "beneficary.Beneficiary.beneficiaryMiddleName", "TextBox", "Beneficiary Middle Name"),
            FormField("ETA-9089", "page3_a4", "beneficary.HomeAddress.addressStreet", "TextBox", "Home Address Street"),
            FormField("ETA-9089", "page3_a5", "beneficary.HomeAddress.addressType", "TextBox", "Home Address Type"),
            FormField("ETA-9089", "page3_a6", "beneficary.HomeAddress.addressCity", "TextBox", "Home Address City"),
            FormField("ETA-9089", "page3_a7", "beneficary.HomeAddress.addressState", "TextBox", "Home Address State"),
            FormField("ETA-9089", "page3_a8", "beneficary.HomeAddress.addressZip", "TextBox", "Home Address ZIP"),
            FormField("ETA-9089", "page3_a9", "beneficary.HomeAddress.addressCountry", "TextBox", "Home Address Country"),
            FormField("ETA-9089", "page3_a10", "beneficary.HomeAddress.addressCounty", "TextBox", "Home Address County"),
            FormField("ETA-9089", "page3_a11", "beneficary.Beneficiary.beneficiaryDateOfBirth", "TextBox", "Date of Birth"),
            FormField("ETA-9089", "page3_a12", "beneficary.Beneficiary.beneficiaryVisaType", "TextBox", "Visa Type"),
            FormField("ETA-9089", "page3_a13", "beneficary.Beneficiary.alienNumber", "TextBox", "Alien Number"),
            FormField("ETA-9089", "page3_a14", "beneficary.Beneficiary.beneficiaryCountryOfBirth", "TextBox", "Country of Birth"),
            FormField("ETA-9089", "page3_a15", "beneficary.Beneficiary.beneficiaryCitizenOfCountry", "TextBox", "Country of Citizenship"),
            FormField("ETA-9089", "default", "beneficary.Beneficiary.beneficiaryLastName", "CheckBox", "Default")
        ]
    
    def _load_i129tn_mappings(self) -> List[FormField]:
        """Load I-129TN form mappings"""
        return [
            FormField("I-129TN", "customer_name", "customer.customer_name", "TextBox", "Customer Name"),
            FormField("I-129TN", "beneficiaryName", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary Name"),
            FormField("I-129TN", "customerSignatory_last_name", "customer.signatory_last_name", "TextBox", "Signatory Last Name"),
            FormField("I-129TN", "customerSignatory_first_name", "customer.signatory_first_name", "TextBox", "Signatory First Name"),
            FormField("I-129TN", "customerSignatory_dayTimeNumber", "customer.signatory_work_phone", "TextBox", "Signatory Daytime Number"),
            FormField("I-129TN", "customerSignatory_email", "customer.signatory_email_id", "TextBox", "Signatory Email"),
            FormField("I-129TN", "attorneyInfoLastName", "attorney.attorneyInfo.lastName", "TextBox", "Attorney Last Name"),
            FormField("I-129TN", "attorneyInfoFirstName", "attorney.attorneyInfo.firstName", "TextBox", "Attorney First Name"),
            FormField("I-129TN", "attorneyInfoOrgName", "attorneyLawfirmDetails.lawfirmDetails.lawFirmName", "TextBox", "Attorney Organization Name"),
            FormField("I-129TN", "attorneyAddressStreet", "attorney.address.addressStreet", "TextBox", "Attorney Street Address"),
            FormField("I-129TN", "attorneyAddressType", "attorney.address.addressType", "CheckBox", "Attorney Address Type"),
            FormField("I-129TN", "attorneyAddressNumber", "attorney.address.addressNumber", "TextBox", "Attorney Address Number"),
            FormField("I-129TN", "attorneyAddressCity", "attorney.address.addressCity", "TextBox", "Attorney City"),
            FormField("I-129TN", "attorneyAddressState", "attorney.address.addressState", "TextBox", "Attorney State"),
            FormField("I-129TN", "attorneyAddressZip", "attorney.address.addressZip", "TextBox", "Attorney ZIP"),
            FormField("I-129TN", "attorneyAddressCountry", "attorney.address.addressCountry", "TextBox", "Attorney Country"),
            FormField("I-129TN", "attorneyAddressWorkPhone", "attorney.attorneyInfo.workPhone", "TextBox", "Attorney Work Phone"),
            FormField("I-129TN", "attorneyAddressFaxNumber", "attorney.attorneyInfo.faxNumber", "TextBox", "Attorney Fax Number"),
            FormField("I-129TN", "attorneyAddressEmail", "attorney.attorneyInfo.emailAddress", "TextBox", "Attorney Email"),
            FormField("I-129TN", "default", "beneficary.Beneficiary.beneficiaryFirstName", "CheckBox", "Default")
        ]
    
    def _load_i129t_mappings(self) -> List[FormField]:
        """Load I-129T form mappings"""
        return [
            FormField("I-129T", "customer_name", "customer.customer_name", "TextBox", "Customer Name"),
            FormField("I-129T", "beneficiaryName", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary Name"),
            FormField("I-129T", "customerSignatory_last_name", "customer.signatory_last_name", "TextBox", "Signatory Last Name"),
            FormField("I-129T", "customerSignatory_first_name", "customer.signatory_first_name", "TextBox", "Signatory First Name"),
            FormField("I-129T", "customerSignatory_dayTimeNumber", "customer.signatory_work_phone", "TextBox", "Signatory Daytime Number"),
            FormField("I-129T", "customerSignatory_email", "customer.signatory_email_id", "TextBox", "Signatory Email"),
            FormField("I-129T", "attorneyInfoLastName", "attorney.attorneyInfo.lastName", "TextBox", "Attorney Last Name"),
            FormField("I-129T", "attorneyInfoFirstName", "attorney.attorneyInfo.firstName", "TextBox", "Attorney First Name"),
            FormField("I-129T", "attorneyInfoOrgName", "attorneyLawfirmDetails.lawfirmDetails.lawFirmName", "TextBox", "Attorney Organization Name"),
            FormField("I-129T", "attorneyAddressStreet", "attorney.address.addressStreet", "TextBox", "Attorney Street Address"),
            FormField("I-129T", "attorneyAddressType", "attorney.address.addressType", "CheckBox", "Attorney Address Type"),
            FormField("I-129T", "attorneyAddressNumber", "attorney.address.addressNumber", "TextBox", "Attorney Address Number"),
            FormField("I-129T", "attorneyAddressCity", "attorney.address.addressCity", "TextBox", "Attorney City"),
            FormField("I-129T", "attorneyAddressState", "attorney.address.addressState", "TextBox", "Attorney State"),
            FormField("I-129T", "attorneyAddressZip", "attorney.address.addressZip", "TextBox", "Attorney ZIP"),
            FormField("I-129T", "attorneyAddressCountry", "attorney.address.addressCountry", "TextBox", "Attorney Country"),
            FormField("I-129T", "attorneyAddressWorkPhone", "attorney.attorneyInfo.workPhone", "TextBox", "Attorney Work Phone"),
            FormField("I-129T", "attorneyAddressFaxNumber", "attorney.attorneyInfo.faxNumber", "TextBox", "Attorney Fax Number"),
            FormField("I-129T", "attorneyAddressEmail", "attorney.attorneyInfo.emailAddress", "TextBox", "Attorney Email"),
            FormField("I-129T", "default", "beneficary.Beneficiary.beneficiaryFirstName", "CheckBox", "Default")
        ]
    
    def _load_i131_mappings(self) -> List[FormField]:
        """Load I-131 form mappings"""
        return [
            FormField("I-131", "attorneyStateBarNumber", "attorney.attorneyInfo.stateBarNumber", "TextBox", "Attorney State Bar Number"),
            FormField("I-131", "beneficiaryLastName", "beneficary.Beneficiary.beneficiaryLastName", "TextBox", "Beneficiary Last Name"),
            FormField("I-131", "beneficiaryFirstName", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary First Name"),
            FormField("I-131", "beneficiaryMiddleName", "beneficary.Beneficiary.beneficiaryMiddleName", "TextBox", "Beneficiary Middle Name"),
            FormField("I-131", "careOfName", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Care Of Name"),
            FormField("I-131", "homeAddressStreetName", "beneficary.HomeAddress.addressStreet", "TextBox", "Home Street Name"),
            FormField("I-131", "homeAddressStreetNumber", "beneficary.HomeAddress.addressNumber", "TextBox", "Home Street Number"),
            FormField("I-131", "homeAddressType", "beneficary.HomeAddress.addressType", "CheckBox", "Home Address Type"),
            FormField("I-131", "homeAddressCity", "beneficary.HomeAddress.addressCity", "TextBox", "Home City"),
            FormField("I-131", "homeAddressState", "beneficary.HomeAddress.addressState", "TextBox", "Home State"),
            FormField("I-131", "homeAddressZip", "beneficary.HomeAddress.addressZip", "TextBox", "Home ZIP"),
            FormField("I-131", "homeAddressCountry", "beneficary.HomeAddress.addressCountry", "TextBox", "Home Country"),
            FormField("I-131", "dbalien1", "beneficary.Beneficiary.alienNumber", "TextBox", "Alien Number"),
            FormField("I-131", "beneficiaryCountryOfBirth", "beneficary.Beneficiary.beneficiaryCountryOfBirth", "TextBox", "Country of Birth"),
            FormField("I-131", "beneficiaryCitizenOfCountry", "beneficary.Beneficiary.beneficiaryCitizenOfCountry", "TextBox", "Country of Citizenship"),
            FormField("I-131", "beneficiaryVisaType", "beneficary.Beneficiary.beneficiaryVisaType", "TextBox", "Visa Type"),
            FormField("I-131", "beneficiaryDateOfBirth", "beneficary.Beneficiary.beneficiaryDateOfBirth", "TextBox", "Date of Birth"),
            FormField("I-131", "ssn", "beneficary.Beneficiary.beneficiarySsn", "TextBox", "Social Security Number"),
            FormField("I-131", "attorneyLastName", "attorney.attorneyInfo.lastName", "TextBox", "Attorney Last Name"),
            FormField("I-131", "attorneyFirstName", "attorney.attorneyInfo.firstName", "TextBox", "Attorney First Name"),
            FormField("I-131", "attorneyOrgName", "attorneyLawfirmDetails.lawfirmDetails.lawFirmName", "TextBox", "Attorney Organization Name"),
            FormField("I-131", "attorneyAddressStreet", "attorney.address.addressStreet", "TextBox", "Attorney Street Address"),
            FormField("I-131", "attorneyAddressNumber", "attorney.address.addressNumber", "TextBox", "Attorney Address Number"),
            FormField("I-131", "attorneyAddressCity", "attorney.address.addressCity", "TextBox", "Attorney City"),
            FormField("I-131", "attorneyAddressState", "attorney.address.addressState", "TextBox", "Attorney State"),
            FormField("I-131", "attorneyAddressZip", "attorney.address.addressZip", "TextBox", "Attorney ZIP"),
            FormField("I-131", "attorneyAddressType", "attorney.address.addressType", "CheckBox", "Attorney Address Type"),
            FormField("I-131", "attorneyAddressCountry", "attorney.address.addressCountry", "TextBox", "Attorney Country"),
            FormField("I-131", "attorneyEmail", "attorney.attorneyInfo.emailAddress", "TextBox", "Attorney Email"),
            FormField("I-131", "default", "beneficary.Beneficiary.beneficiaryFirstName", "CheckBox", "Default")
        ]
    
    def _load_i485_mappings(self) -> List[FormField]:
        """Load I-485 form mappings"""
        return [
            FormField("I-485", "attorneyStateBarNo", "attorney.attorneyInfo.stateBarNumber", "TextBox", "Attorney State Bar Number"),
            FormField("I-485", "beneficiaryLastName", "beneficary.Beneficiary.beneficiaryLastName", "TextBox", "Beneficiary Last Name"),
            FormField("I-485", "beneficiaryFirstName", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary First Name"),
            FormField("I-485", "beneficiaryMiddleName", "beneficary.Beneficiary.beneficiaryMiddleName", "TextBox", "Beneficiary Middle Name"),
            FormField("I-485", "beneficiaryCareOfName", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Care Of Name"),
            FormField("I-485", "beneficiaryProvinceOfBirth", "beneficary.Beneficiary.beneficiaryProvinceOfBirth", "TextBox", "Province of Birth"),
            FormField("I-485", "beneficiaryCountryOfBirth", "beneficary.Beneficiary.beneficiaryCountryOfBirth", "TextBox", "Country of Birth"),
            FormField("I-485", "beneficiaryCitizenOfCountry", "beneficary.Beneficiary.beneficiaryCitizenOfCountry", "TextBox", "Country of Citizenship"),
            FormField("I-485", "beneficiaryDateOfBirth", "beneficary.Beneficiary.beneficiaryDateOfBirth", "TextBox", "Date of Birth"),
            FormField("I-485", "workAddressStreet", "beneficary.WorkAddress.addressStreet", "TextBox", "Work Address Street"),
            FormField("I-485", "workAddressNumber", "beneficary.WorkAddress.addressNumber", "TextBox", "Work Address Number"),
            FormField("I-485", "workAddressType", "beneficary.WorkAddress.addressType", "CheckBox", "Work Address Type"),
            FormField("I-485", "workAddressCity", "beneficary.WorkAddress.addressCity", "TextBox", "Work Address City"),
            FormField("I-485", "workAddressState", "beneficary.WorkAddress.addressState", "TextBox", "Work Address State"),
            FormField("I-485", "workAddressZip", "beneficary.WorkAddress.addressZip", "TextBox", "Work Address ZIP"),
            FormField("I-485", "p1_28a_beneficiaryLastName", "beneficary.Beneficiary.beneficiaryLastName", "TextBox", "Part 1 Last Name"),
            FormField("I-485", "p1_28b_beneficiaryFirstName", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Part 1 First Name"),
            FormField("I-485", "p1_28c_beneficiaryMiddleName", "beneficary.Beneficiary.beneficiaryMiddleName", "TextBox", "Part 1 Middle Name"),
            FormField("I-485", "p14_1a", "beneficary.Beneficiary.beneficiaryLastName", "TextBox", "Part 14 Last Name"),
            FormField("I-485", "p14_1b", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Part 14 First Name"),
            FormField("I-485", "p14", "beneficary.Beneficiary.beneficiaryMiddleName", "TextBox", "Part 14 Middle Name"),
            FormField("I-485", "ussocialssn_1", "beneficary.Beneficiary.beneficiarySsn", "TextBox", "Social Security Number"),
            FormField("I-485", "dbi94number1", "beneficary.I94Details.I94.i94Number", "TextBox", "I-94 Number"),
            FormField("I-485", "p12_1a", "attorney.attorneyInfo.lastName", "TextBox", "Attorney Last Name"),
            FormField("I-485", "p12_1b", "attorney.attorneyInfo.firstName", "TextBox", "Attorney First Name"),
            FormField("I-485", "p12_2", "attorneyLawfirmDetails.lawfirmDetails.lawFirmName", "TextBox", "Law Firm Name"),
            FormField("I-485", "p12_3a_Street", "attorney.address.addressStreet", "TextBox", "Attorney Street"),
            FormField("I-485", "p12_3b_Number", "attorney.address.addressNumber", "TextBox", "Attorney Number"),
            FormField("I-485", "p12_3c_City", "attorney.address.addressCity", "TextBox", "Attorney City"),
            FormField("I-485", "p12_3d_State", "attorney.address.addressState", "TextBox", "Attorney State"),
            FormField("I-485", "p12_3e_Zip", "attorney.address.addressZip", "TextBox", "Attorney ZIP"),
            FormField("I-485", "p12_3b_", "attorney.address.addressType", "CheckBox", "Attorney Address Type"),
            FormField("I-485", "p12_3h_Country", "attorney.address.addressCountry", "TextBox", "Attorney Country"),
            FormField("I-485", "p12_5_Number", "attorney.attorneyInfo.workPhone", "TextBox", "Attorney Phone"),
            FormField("I-485", "p12_6_Email", "attorney.attorneyInfo.emailAddress", "TextBox", "Attorney Email"),
            FormField("I-485", "dbalien1_1", "beneficary.Beneficiary.alienNumber", "TextBox", "Alien Number"),
            FormField("I-485", "p10_4", "beneficary.Beneficiary.beneficiaryCellNumber", "TextBox", "Cell Number"),
            FormField("I-485", "p10_5", "beneficary.Beneficiary.beneficiaryPrimaryEmailAddress", "TextBox", "Email Address"),
            FormField("I-485", "default", "beneficary.Beneficiary.beneficiaryFirstName", "CheckBox", "Default")
        ]
    
    def _load_i485j_mappings(self) -> List[FormField]:
        """Load I-485J form mappings"""
        return [
            FormField("I-485J", "beneficiaryLastName", "beneficary.Beneficiary.beneficiaryLastName", "TextBox", "Beneficiary Last Name"),
            FormField("I-485J", "beneficiaryFirstName", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary First Name"),
            FormField("I-485J", "beneficiaryMiddleName", "beneficary.Beneficiary.beneficiaryMiddleName", "TextBox", "Beneficiary Middle Name"),
            FormField("I-485J", "beneficiaryCareOfName", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Care Of Name"),
            FormField("I-485J", "beneficiaryCountryOfBirth", "beneficary.Beneficiary.beneficiaryCountryOfBirth", "TextBox", "Country of Birth"),
            FormField("I-485J", "beneficiaryDateOfBirth", "beneficary.Beneficiary.beneficiaryDateOfBirth", "TextBox", "Date of Birth"),
            FormField("I-485J", "workAddressStreet", "beneficary.WorkAddress.addressStreet", "TextBox", "Work Address Street"),
            FormField("I-485J", "workAddressNumber", "beneficary.WorkAddress.addressNumber", "TextBox", "Work Address Number"),
            FormField("I-485J", "workAddressType", "beneficary.WorkAddress.addressType", "CheckBox", "Work Address Type"),
            FormField("I-485J", "workAddressCity", "beneficary.WorkAddress.addressCity", "TextBox", "Work Address City"),
            FormField("I-485J", "workAddressState", "beneficary.WorkAddress.addressState", "TextBox", "Work Address State"),
            FormField("I-485J", "workAddressZip", "beneficary.WorkAddress.addressZip", "TextBox", "Work Address ZIP"),
            FormField("I-485J", "p3_4", "beneficary.Beneficiary.beneficiaryCellNumber", "TextBox", "Cell Number"),
            FormField("I-485J", "p3_5", "beneficary.Beneficiary.beneficiaryPrimaryEmailAddress", "TextBox", "Email Address"),
            FormField("I-485J", "p4_1a", "attorney.attorneyInfo.lastName", "TextBox", "Attorney Last Name"),
            FormField("I-485J", "p4_1b", "attorney.attorneyInfo.firstName", "TextBox", "Attorney First Name"),
            FormField("I-485J", "p4_2", "attorneyLawfirmDetails.lawfirmDetails.lawFirmName", "TextBox", "Law Firm Name"),
            FormField("I-485J", "attorneyStreet", "attorney.address.addressStreet", "TextBox", "Attorney Street"),
            FormField("I-485J", "attorneyaddressNumber", "attorney.address.addressNumber", "TextBox", "Attorney Number"),
            FormField("I-485J", "attorneyaddressCity", "attorney.address.addressCity", "TextBox", "Attorney City"),
            FormField("I-485J", "attorneyaddressState", "attorney.address.addressState", "TextBox", "Attorney State"),
            FormField("I-485J", "attorneyaddressZip", "attorney.address.addressZip", "TextBox", "Attorney ZIP"),
            FormField("I-485J", "attorneyAddressType", "attorney.address.addressType", "CheckBox", "Attorney Address Type"),
            FormField("I-485J", "attorneyaddresscountry", "attorney.address.addressCountry", "TextBox", "Attorney Country"),
            FormField("I-485J", "attorneyworkPhone", "attorney.attorneyInfo.workPhone", "TextBox", "Attorney Phone"),
            FormField("I-485J", "attorneyemailAddress", "attorney.attorneyInfo.emailAddress", "TextBox", "Attorney Email"),
            FormField("I-485J", "dbalien1", "beneficary.Beneficiary.alienNumber", "TextBox", "Alien Number"),
            FormField("I-485J", "dbanumber1", "beneficary.Beneficiary.alienNumber", "TextBox", "A-Number"),
            FormField("I-485J", "customercustomer_name", "customer.customer_name", "TextBox", "Customer Name"),
            FormField("I-485J", "customercustomer_type_of_business", "customer.customer_type_of_business", "TextBox", "Type of Business"),
            FormField("I-485J", "customercustomer_year_established", "customer.customer_year_established", "TextBox", "Year Established"),
            FormField("I-485J", "customercustomer_total_employees", "customer.customer_total_employees", "TextBox", "Total Employees"),
            FormField("I-485J", "customercustomer_gross_annual_income", "customer.customer_gross_annual_income", "TextBox", "Gross Annual Income"),
            FormField("I-485J", "customercustomer_net_annual_income", "customer.customer_net_annual_income", "TextBox", "Net Annual Income"),
            FormField("I-485J", "customeraddress_street", "customer.address_street", "TextBox", "Customer Street"),
            FormField("I-485J", "customeraddress_number", "customer.address_nmber", "TextBox", "Customer Number"),
            FormField("I-485J", "customeraddress_type", "customer.address_type", "CheckBox", "Customer Address Type"),
            FormField("I-485J", "customeraddress_city", "customer.address_city", "TextBox", "Customer City"),
            FormField("I-485J", "customeraddress_state", "customer.address_state", "TextBox", "Customer State"),
            FormField("I-485J", "customeraddress_zip", "customer.address_zip", "TextBox", "Customer ZIP"),
            FormField("I-485J", "ein_1", "customer.customer_tax_id", "TextBox", "EIN"),
            FormField("I-485J", "NaicsCode1", "customer.customer_naics_code", "TextBox", "NAICS Code"),
            FormField("I-485J", "signatorysignatory_last_name", "customer.signatory_last_name", "TextBox", "Signatory Last Name"),
            FormField("I-485J", "signatorysignatory_first_name", "customer.signatory_first_name", "TextBox", "Signatory First Name"),
            FormField("I-485J", "signatorysignatory_job_title", "customer.signatory_job_title", "TextBox", "Signatory Job Title"),
            FormField("I-485J", "customersignatory_work_phone", "customer.signatory_work_phone", "TextBox", "Signatory Work Phone"),
            FormField("I-485J", "customersignatory_email_id", "customer.signatory_email_id", "TextBox", "Signatory Email"),
            FormField("I-485J", "attorneylastName", "attorney.attorneyInfo.lastName", "TextBox", "Attorney Last Name 2"),
            FormField("I-485J", "attorneyfirstName", "attorney.attorneyInfo.firstName", "TextBox", "Attorney First Name 2"),
            FormField("I-485J", "attorneyOrgName", "attorneyLawfirmDetails.lawfirmDetails.lawFirmName", "TextBox", "Attorney Org Name"),
            FormField("I-485J", "attorneyaddressStreet2", "attorney.address.addressStreet", "TextBox", "Attorney Street 2"),
            FormField("I-485J", "attorneyaddressaddressNumber", "attorney.address.addressNumber", "TextBox", "Attorney Number 2"),
            FormField("I-485J", "attorneyaddressaddressCity2", "attorney.address.addressCity", "TextBox", "Attorney City 2"),
            FormField("I-485J", "attorneyaddressaddressState2", "attorney.address.addressState", "TextBox", "Attorney State 2"),
            FormField("I-485J", "attorneyaddressaddressZip2", "attorney.address.addressZip", "TextBox", "Attorney ZIP 2"),
            FormField("I-485J", "attorneyaddressaddressType", "attorney.address.addressType", "CheckBox", "Attorney Address Type 2"),
            FormField("I-485J", "attorneyaddressaddress_country2", "attorney.address.addressCountry", "TextBox", "Attorney Country 2"),
            FormField("I-485J", "attorneyworkPhone2", "attorney.attorneyInfo.workPhone", "TextBox", "Attorney Phone 2"),
            FormField("I-485J", "attorneyemailAddress2", "attorney.attorneyInfo.emailAddress", "TextBox", "Attorney Email 2"),
            FormField("I-485J", "beneficiaryLastName2", "beneficary.Beneficiary.beneficiaryLastName", "TextBox", "Beneficiary Last Name 2"),
            FormField("I-485J", "beneficiaryFirstName2", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary First Name 2"),
            FormField("I-485J", "beneficiaryMiddleName2", "beneficary.Beneficiary.beneficiaryMiddleName", "TextBox", "Beneficiary Middle Name 2"),
            FormField("I-485J", "default", "beneficary.Beneficiary.beneficiaryFirstName", "CheckBox", "Default")
        ]
    
    def _load_i485a_mappings(self) -> List[FormField]:
        """Load I-485A form mappings"""
        return [
            FormField("I-485A", "beneficiaryLastName", "beneficary.Beneficiary.beneficiaryLastName", "TextBox", "Beneficiary Last Name"),
            FormField("I-485A", "beneficiaryFirstName", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary First Name"),
            FormField("I-485A", "beneficiaryMiddleName", "beneficary.Beneficiary.beneficiaryMiddleName", "TextBox", "Beneficiary Middle Name"),
            FormField("I-485A", "beneficiaryCareOfName", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Care Of Name"),
            FormField("I-485A", "beneficiaryCountryOfBirth", "beneficary.Beneficiary.beneficiaryCountryOfBirth", "TextBox", "Country of Birth"),
            FormField("I-485A", "beneficiaryDateOfBirth", "beneficary.Beneficiary.beneficiaryDateOfBirth", "TextBox", "Date of Birth"),
            FormField("I-485A", "beneficiaryCitizenOfCountry", "beneficary.Beneficiary.beneficiaryCitizenOfCountry", "TextBox", "Country of Citizenship"),
            FormField("I-485A", "workAddressStreet", "beneficary.WorkAddress.addressStreet", "TextBox", "Work Address Street"),
            FormField("I-485A", "workAddressNumber", "beneficary.WorkAddress.addressNumber", "TextBox", "Work Address Number"),
            FormField("I-485A", "workAddressType", "beneficary.WorkAddress.addressType", "CheckBox", "Work Address Type"),
            FormField("I-485A", "workAddressCity", "beneficary.WorkAddress.addressCity", "TextBox", "Work Address City"),
            FormField("I-485A", "workAddressState", "beneficary.WorkAddress.addressState", "TextBox", "Work Address State"),
            FormField("I-485A", "workAddressZip", "beneficary.WorkAddress.addressZip", "TextBox", "Work Address ZIP"),
            FormField("I-485A", "beneficiaryLastName1", "beneficary.Beneficiary.beneficiaryLastName", "TextBox", "Beneficiary Last Name 1"),
            FormField("I-485A", "beneficiaryFirstName1", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary First Name 1"),
            FormField("I-485A", "beneficiaryMiddleName1", "beneficary.Beneficiary.beneficiaryMiddleName", "TextBox", "Beneficiary Middle Name 1"),
            FormField("I-485A", "p4_4", "beneficary.Beneficiary.beneficiaryCellNumber", "TextBox", "Cell Number"),
            FormField("I-485A", "p4_5", "beneficary.Beneficiary.beneficiaryPrimaryEmailAddress", "TextBox", "Email Address"),
            FormField("I-485A", "p6_1a", "attorney.attorneyInfo.lastName", "TextBox", "Attorney Last Name"),
            FormField("I-485A", "p6_1a", "attorney.attorneyInfo.firstName", "TextBox", "Attorney First Name"),
            FormField("I-485A", "p6_2", "attorneyLawfirmDetails.lawfirmDetails.lawFirmName", "TextBox", "Law Firm Name"),
            FormField("I-485A", "attorneyaddressStreet", "attorney.address.addressStreet", "TextBox", "Attorney Street"),
            FormField("I-485A", "attorneyaddressNumber", "attorney.address.addressNumber", "TextBox", "Attorney Number"),
            FormField("I-485A", "attorneyaddressCity", "attorney.address.addressCity", "TextBox", "Attorney City"),
            FormField("I-485A", "attorneyaddressState", "attorney.address.addressState", "TextBox", "Attorney State"),
            FormField("I-485A", "attorneyaddressZip", "attorney.address.addressZip", "TextBox", "Attorney ZIP"),
            FormField("I-485A", "attorneyaddressaddressType", "attorney.address.addressType", "CheckBox", "Attorney Address Type"),
            FormField("I-485A", "attorneyaddressCountry", "attorney.address.addressCountry", "TextBox", "Attorney Country"),
            FormField("I-485A", "P6_5", "attorney.attorneyInfo.workPhone", "TextBox", "Attorney Phone"),
            FormField("I-485A", "P6_6", "attorney.attorneyInfo.emailAddress", "TextBox", "Attorney Email"),
            FormField("I-485A", "dbalien1", "beneficary.Beneficiary.alienNumber", "TextBox", "Alien Number"),
            FormField("I-485A", "ein_1", "beneficary.Beneficiary.alienNumber", "TextBox", "EIN"),
            FormField("I-485A", "default", "beneficary.Beneficiary.beneficiaryFirstName", "CheckBox", "Default")
        ]
    
    def _load_i864_mappings(self) -> List[FormField]:
        """Load I-864 form mappings"""
        return [
            FormField("I-864", "stateBarNumber", "attorney.attorneyInfo.stateBarNumber", "TextBox", "State Bar Number"),
            FormField("I-864", "beneficiaryLastName", "beneficary.Beneficiary.beneficiaryLastName", "TextBox", "Beneficiary Last Name"),
            FormField("I-864", "beneficiaryFirstName", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary First Name"),
            FormField("I-864", "beneficiaryMiddleName", "beneficary.Beneficiary.beneficiaryMiddleName", "TextBox", "Beneficiary Middle Name"),
            FormField("I-864", "beneficiaryName", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary Name"),
            FormField("I-864", "workAddressStreet", "beneficary.WorkAddress.addressStreet", "TextBox", "Work Address Street"),
            FormField("I-864", "workAddressNumber", "beneficary.WorkAddress.addressNumber", "TextBox", "Work Address Number"),
            FormField("I-864", "workAddressType", "beneficary.WorkAddress.addressType", "CheckBox", "Work Address Type"),
            FormField("I-864", "workAddressCity", "beneficary.WorkAddress.addressCity", "TextBox", "Work Address City"),
            FormField("I-864", "workAddressState", "beneficary.WorkAddress.addressState", "TextBox", "Work Address State"),
            FormField("I-864", "workAddressZip", "beneficary.WorkAddress.addressZip", "TextBox", "Work Address ZIP"),
            FormField("I-864", "workAddresscounty", "beneficary.WorkAddress.addressCounty", "TextBox", "Work Address County"),
            FormField("I-864", "workAddresscountry", "beneficary.WorkAddress.addressCountry", "TextBox", "Work Address Country"),
            FormField("I-864", "beneficiaryDateOfBirth", "beneficary.Beneficiary.beneficiaryDateOfBirth", "TextBox", "Date of Birth"),
            FormField("I-864", "beneficiaryCitizenOfCountry", "beneficary.Beneficiary.beneficiaryCitizenOfCountry", "TextBox", "Country of Citizenship"),
            FormField("I-864", "beneficiaryCellNumber", "beneficary.Beneficiary.beneficiaryCellNumber", "TextBox", "Cell Number"),
            FormField("I-864", "beneficiaryLastName1", "beneficary.Beneficiary.beneficiaryLastName", "TextBox", "Beneficiary Last Name 1"),
            FormField("I-864", "beneficiaryFirstName1", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary First Name 1"),
            FormField("I-864", "beneficiaryMiddleName1", "beneficary.Beneficiary.beneficiaryMiddleName", "TextBox", "Beneficiary Middle Name 1"),
            FormField("I-864", "attorneyInfoFirstName", "attorney.attorneyInfo.firstName", "TextBox", "Attorney First Name"),
            FormField("I-864", "attorneyInfoLastName", "attorney.attorneyInfo.lastName", "TextBox", "Attorney Last Name"),
            FormField("I-864", "lawFirmName", "attorneyLawfirmDetails.lawfirmDetails.lawFirmName", "TextBox", "Law Firm Name"),
            FormField("I-864", "attorneyaddressStreet", "attorney.address.addressStreet", "TextBox", "Attorney Street"),
            FormField("I-864", "attorneyaddressNumber", "attorney.address.addressNumber", "TextBox", "Attorney Number"),
            FormField("I-864", "attorneyaddressCity", "attorney.address.addressCity", "TextBox", "Attorney City"),
            FormField("I-864", "attorneyaddressState", "attorney.address.addressState", "TextBox", "Attorney State"),
            FormField("I-864", "attorneyaddressZip", "attorney.address.addressZip", "TextBox", "Attorney ZIP"),
            FormField("I-864", "attorneyaddressaddressType", "attorney.address.addressType", "CheckBox", "Attorney Address Type"),
            FormField("I-864", "attorneyaddressCountry", "attorney.address.addressCountry", "TextBox", "Attorney Country"),
            FormField("I-864", "workPhone", "attorney.attorneyInfo.workPhone", "TextBox", "Attorney Phone"),
            FormField("I-864", "emailAddress", "attorney.attorneyInfo.emailAddress", "TextBox", "Attorney Email"),
            FormField("I-864", "default", "beneficary.Beneficiary.beneficiaryFirstName", "CheckBox", "Default")
        ]
    
    def _load_i864a_mappings(self) -> List[FormField]:
        """Load I-864A form mappings"""
        return [
            FormField("I-864A", "stateBarNumber", "attorney.attorneyInfo.stateBarNumber", "TextBox", "State Bar Number"),
            FormField("I-864A", "beneficiaryLastName", "beneficary.Beneficiary.beneficiaryLastName", "TextBox", "Beneficiary Last Name"),
            FormField("I-864A", "beneficiaryFirstName", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary First Name"),
            FormField("I-864A", "beneficiaryMiddleName", "beneficary.Beneficiary.beneficiaryMiddleName", "TextBox", "Beneficiary Middle Name"),
            FormField("I-864A", "beneficiaryName", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary Name"),
            FormField("I-864A", "workAddressStreet", "beneficary.WorkAddress.addressStreet", "TextBox", "Work Address Street"),
            FormField("I-864A", "workAddressNumber", "beneficary.WorkAddress.addressNumber", "TextBox", "Work Address Number"),
            FormField("I-864A", "workAddressType", "beneficary.WorkAddress.addressType", "CheckBox", "Work Address Type"),
            FormField("I-864A", "workAddressCity", "beneficary.WorkAddress.addressCity", "TextBox", "Work Address City"),
            FormField("I-864A", "workAddressState", "beneficary.WorkAddress.addressState", "TextBox", "Work Address State"),
            FormField("I-864A", "workAddressZip", "beneficary.WorkAddress.addressZip", "TextBox", "Work Address ZIP"),
            FormField("I-864A", "workAddresscounty", "beneficary.WorkAddress.addressCounty", "TextBox", "Work Address County"),
            FormField("I-864A", "workAddresscountry", "beneficary.WorkAddress.addressCountry", "TextBox", "Work Address Country"),
            FormField("I-864A", "beneficiaryDateOfBirth", "beneficary.Beneficiary.beneficiaryDateOfBirth", "TextBox", "Date of Birth"),
            FormField("I-864A", "beneficiaryCountryOfBirth", "beneficary.Beneficiary.beneficiaryCountryOfBirth", "TextBox", "Country of Birth"),
            FormField("I-864A", "beneficiaryProvinceOfBirth", "beneficary.Beneficiary.beneficiaryProvinceOfBirth", "TextBox", "Province of Birth"),
            FormField("I-864A", "beneficiaryStateOfBirth", "beneficary.Beneficiary.stateBirth", "TextBox", "State of Birth"),
            FormField("I-864A", "ssn", "beneficary.Beneficiary.beneficiarySsn", "TextBox", "Social Security Number"),
            FormField("I-864A", "beneficiaryLastName1", "beneficary.Beneficiary.beneficiaryLastName", "TextBox", "Beneficiary Last Name 1"),
            FormField("I-864A", "beneficiaryFirstName1", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary First Name 1"),
            FormField("I-864A", "beneficiaryMiddleName1", "beneficary.Beneficiary.beneficiaryMiddleName", "TextBox", "Beneficiary Middle Name 1"),
            FormField("I-864A", "attorneyInfoFirstName", "attorney.attorneyInfo.firstName", "TextBox", "Attorney First Name"),
            FormField("I-864A", "attorneyInfoLastName", "attorney.attorneyInfo.lastName", "TextBox", "Attorney Last Name"),
            FormField("I-864A", "lawFirmName", "attorneyLawfirmDetails.lawfirmDetails.lawFirmName", "TextBox", "Law Firm Name"),
            FormField("I-864A", "attorneyaddressStreet", "attorney.address.addressStreet", "TextBox", "Attorney Street"),
            FormField("I-864A", "attorneyaddressNumber", "attorney.address.addressNumber", "TextBox", "Attorney Number"),
            FormField("I-864A", "attorneyaddressCity", "attorney.address.addressCity", "TextBox", "Attorney City"),
            FormField("I-864A", "attorneyaddressState", "attorney.address.addressState", "TextBox", "Attorney State"),
            FormField("I-864A", "attorneyaddressZip", "attorney.address.addressZip", "TextBox", "Attorney ZIP"),
            FormField("I-864A", "attorneyaddressaddressType", "attorney.address.addressType", "CheckBox", "Attorney Address Type"),
            FormField("I-864A", "attorneyaddressCountry", "attorney.address.addressCountry", "TextBox", "Attorney Country"),
            FormField("I-864A", "workPhone", "attorney.attorneyInfo.workPhone", "TextBox", "Attorney Phone"),
            FormField("I-864A", "emailAddress", "attorney.attorneyInfo.emailAddress", "TextBox", "Attorney Email"),
            FormField("I-864A", "ein_1", "beneficary.Beneficiary.alienNumber", "TextBox", "EIN"),
            FormField("I-864A", "default", "beneficary.Beneficiary.beneficiaryFirstName", "CheckBox", "Default")
        ]
    
    def _load_i129r_mappings(self) -> List[FormField]:
        """Load I-129R form mappings"""
        return [
            FormField("I-129R", "petitionName", "customer.customer_name", "TextBox", "Petition Name"),
            FormField("I-129R", "beneficiaryName", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary Name"),
            FormField("I-129R", "petitionName1", "customer.signatory_first_name", "TextBox", "Petition Name 1"),
            FormField("I-129R", "petitionTitle1", "customer.signatory_job_title", "TextBox", "Petition Title 1"),
            FormField("I-129R", "streetName1", "customer.address_street", "TextBox", "Street Name 1"),
            FormField("I-129R", "addressNumber1", "customer.address_number", "TextBox", "Address Number 1"),
            FormField("I-129R", "apt1", "customer.address_type", "CheckBox", "Apt 1"),
            FormField("I-129R", "empName1", "customer.customer_name", "TextBox", "Employer Name 1"),
            FormField("I-129R", "city1", "customer.address_city", "TextBox", "City 1"),
            FormField("I-129R", "state1", "customer.address_state", "TextBox", "State 1"),
            FormField("I-129R", "zipCode1", "customer.address_zip", "TextBox", "ZIP Code 1"),
            FormField("I-129R", "phoneNumber1", "customer.signatory_work_phone", "TextBox", "Phone Number 1"),
            FormField("I-129R", "emailAddress1", "customer.signatory_email_id", "TextBox", "Email Address 1"),
            FormField("I-129R", "default", "customer.customer_name", "CheckBox", "Default")
        ]
    
    def _load_i829_mappings(self) -> List[FormField]:
        """Load I-829 form mappings"""
        return [
            FormField("I-829", "stateBarNumber", "attorney.attorneyInfo.stateBarNumber", "TextBox", "State Bar Number"),
            FormField("I-829", "beneficiaryLastName_P2_1a", "beneficary.Beneficiary.beneficiaryLastName", "TextBox", "Beneficiary Last Name P2 1a"),
            FormField("I-829", "beneficiaryFirstName_P2_1b", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary First Name P2 1b"),
            FormField("I-829", "beneficiaryMiddleName_P2_1c", "beneficary.Beneficiary.beneficiaryMiddleName", "TextBox", "Beneficiary Middle Name P2 1c"),
            FormField("I-829", "dbalien1", "beneficary.Beneficiary.alienNumber", "TextBox", "Alien Number"),
            FormField("I-829", "ussocialssn_1", "beneficary.Beneficiary.beneficiarySsn", "TextBox", "Social Security Number"),
            FormField("I-829", "beneficiaryDateOfBirth", "beneficary.Beneficiary.beneficiaryDateOfBirth", "TextBox", "Date of Birth"),
            FormField("I-829", "beneficiaryCountryOfBirth", "beneficary.Beneficiary.beneficiaryCountryOfBirth", "TextBox", "Country of Birth"),
            FormField("I-829", "beneficiaryCitizenOfCountry", "beneficary.Beneficiary.beneficiaryCitizenOfCountry", "TextBox", "Country of Citizenship"),
            FormField("I-829", "beneficiaryFirstName_P2_14a", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary First Name P2 14a"),
            FormField("I-829", "addressStreet_P2_14b", "beneficary.WorkAddress.addressStreet", "TextBox", "Address Street P2 14b"),
            FormField("I-829", "addressNumber_P2_14c", "beneficary.WorkAddress.addressNumber", "TextBox", "Address Number P2 14c"),
            FormField("I-829", "P2_14c", "beneficary.WorkAddress.addressType", "CheckBox", "P2 14c"),
            FormField("I-829", "addressCity_P2_14d", "beneficary.WorkAddress.addressCity", "TextBox", "Address City P2 14d"),
            FormField("I-829", "addressState_P2_14e", "beneficary.WorkAddress.addressState", "TextBox", "Address State P2 14e"),
            FormField("I-829", "addressZip_P2_14f", "beneficary.WorkAddress.addressZip", "TextBox", "Address ZIP P2 14f"),
            FormField("I-829", "addressStreet_P2_16a", "beneficary.WorkAddress.addressStreet", "TextBox", "Address Street P2 16a"),
            FormField("I-829", "addressNumber_P2_16b", "beneficary.WorkAddress.addressNumber", "TextBox", "Address Number P2 16b"),
            FormField("I-829", "P2_16b", "beneficary.WorkAddress.addressType", "CheckBox", "P2 16b"),
            FormField("I-829", "addressCity_P2_16c", "beneficary.WorkAddress.addressCity", "TextBox", "Address City P2 16c"),
            FormField("I-829", "addressState_P2_16d", "beneficary.WorkAddress.addressState", "TextBox", "Address State P2 16d"),
            FormField("I-829", "addressZip_P2_16e", "beneficary.WorkAddress.addressZip", "TextBox", "Address ZIP P2 16e"),
            FormField("I-829", "ussocialssn_1", "beneficary.Beneficiary.beneficiarySsn", "TextBox", "Social Security Number"),
            FormField("I-829", "dbi94number1", "beneficary.I94Details.I94.i94Number", "TextBox", "I-94 Number"),
            FormField("I-829", "beneficiaryHomeNumber_P9_1", "beneficary.Beneficiary.beneficiaryHomeNumber", "TextBox", "Home Number P9 1"),
            FormField("I-829", "beneficiaryCellNumber_P9_2", "beneficary.Beneficiary.beneficiaryCellNumber", "TextBox", "Cell Number P9 2"),
            FormField("I-829", "beneficiaryPrimaryEmailAddress_P9_1", "beneficary.Beneficiary.beneficiaryPrimaryEmailAddress", "TextBox", "Email Address P9 1"),
            FormField("I-829", "preparerLastName_P11_1a", "attorney.attorneyInfo.lastName", "TextBox", "Preparer Last Name P11 1a"),
            FormField("I-829", "preparerFirstName_P11_1b", "attorney.attorneyInfo.firstName", "TextBox", "Preparer First Name P11 1b"),
            FormField("I-829", "businessName_P11_2", "attorneyLawfirmDetails.lawfirmDetails.lawFirmName", "TextBox", "Business Name P11 2"),
            FormField("I-829", "preparerHomeNumber_P11_3", "attorney.attorneyInfo.workPhone", "TextBox", "Preparer Home Number P11 3"),
            FormField("I-829", "preparerEmailAddress_P11_5", "attorney.attorneyInfo.emailAddress", "TextBox", "Preparer Email Address P11 5"),
            FormField("I-829", "beneficiaryLastName_P12_1a", "beneficary.Beneficiary.beneficiaryLastName", "TextBox", "Beneficiary Last Name P12 1a"),
            FormField("I-829", "beneficiaryFirstName_P12_1b", "beneficary.Beneficiary.beneficiaryFirstName", "TextBox", "Beneficiary First Name P12 1b"),
            FormField("I-829", "beneficiaryMiddleName_P12_1c", "beneficary.Beneficiary.beneficiaryMiddleName", "TextBox", "Beneficiary Middle Name P12 1c"),
            FormField("I-829", "dbanumber1", "beneficary.Beneficiary.alienNumber", "TextBox", "A-Number 1"),
            FormField("I-829", "default", "beneficary.Beneficiary.beneficiaryFirstName", "CheckBox", "Default")
        ]
    
    def _load_json_configs(self) -> Dict[str, Dict]:
        """Load JSON configuration files"""
        configs = {
            "case-config": {
                "controls": [
                    {
                        "name": "customerType",
                        "label": "Customer Type",
                        "type": "dropdown",
                        "validators": {"required": True},
                        "options": [],
                        "lookup": "customerType",
                        "style": {"col": "6"}
                    },
                    {
                        "name": "caseType",
                        "label": "Case Type",
                        "type": "dropdown",
                        "validators": {"required": True},
                        "options": [],
                        "lookup": "customerCaseType",
                        "style": {"col": "6"}
                    },
                    {
                        "name": "pdfMapper",
                        "label": "Pdf Mapper",
                        "type": "dropdown",
                        "validators": {"required": False},
                        "options": [],
                        "lookup": "customerPdfMapper",
                        "style": {"col": "6"},
                        "multiSelectFlag": "true"
                    },
                    {
                        "name": "questionnaireMapper",
                        "label": "Questionare Mapper",
                        "type": "dropdown",
                        "validators": {"required": False},
                        "options": [],
                        "lookup": "customerQuestionareMapper",
                        "style": {"col": "6"},
                        "multiSelectFlag": "true"
                    }
                ]
            },
            "beneficiary-details": {
                "controls": [
                    {
                        "name": "existingBeneficiary",
                        "label": "Existing Beneficiary",
                        "type": "switch",
                        "validators": {},
                        "defaultValue": True,
                        "style": {"col": "6"}
                    },
                    {
                        "name": "beneficiaryId",
                        "label": "Beneficiary Name",
                        "type": "dropdown",
                        "validators": {"required": True},
                        "options": [],
                        "lookup": "CustomerList",
                        "style": {"col": "6"}
                    },
                    {
                        "name": "beneficiarySalutation",
                        "label": "Salutation",
                        "type": "dropdown",
                        "validators": {"required": True},
                        "options": [],
                        "lookup": "Salutation",
                        "disabled": True,
                        "style": {"col": "6"}
                    },
                    {
                        "name": "beneficiaryFirstName",
                        "label": "Beneficiary FirstName",
                        "type": "text",
                        "validators": {"required": True},
                        "disabled": True,
                        "style": {"col": "6"}
                    },
                    {
                        "name": "beneficiaryMiddleName",
                        "label": "Middle Name",
                        "type": "text",
                        "validators": {"required": False},
                        "disabled": True,
                        "style": {"col": "6"}
                    },
                    {
                        "name": "beneficiaryLastName",
                        "label": "Beneficiary Last Name",
                        "type": "text",
                        "validators": {"required": True},
                        "disabled": True,
                        "style": {"col": "6"},
                        "upercase": True
                    },
                    {
                        "name": "beneficiaryVisaType",
                        "label": "Current Beneficiary Visa Type",
                        "type": "dropdown",
                        "validators": {"required": True},
                        "options": [],
                        "disabled": True,
                        "lookup": "BeneficiaryVisaType",
                        "defaultValue": "H1B",
                        "style": {"col": "6"}
                    },
                    {
                        "name": "beneficiaryCellNumber",
                        "label": "Mobile/Cell Phone",
                        "type": "text",
                        "validators": {"required": False},
                        "disabled": True,
                        "mask": "(000) 000 0000",
                        "style": {"col": "6"}
                    },
                    {
                        "name": "beneficiaryRestrictedAccess",
                        "label": "Restrict Beneficiary Portal Access",
                        "type": "checkbox",
                        "defaultValue": False,
                        "validators": {},
                        "disabled": False,
                        "style": {"col": "6"}
                    },
                    {
                        "name": "beneficiaryEmail",
                        "label": "Beneficiary Email",
                        "type": "text",
                        "validators": {"required": True, "pattern": True},
                        "patternType": "email",
                        "disabled": True,
                        "style": {"col": "6"}
                    }
                ]
            }
        }
        return configs
    
    def detect_form_type(self, content: str) -> FormType:
        """Detect the type of form based on content or filename"""
        content_lower = content.lower()
        
        # Check for specific form types
        form_patterns = {
            "lca": ["labor condition application", "lca", "eca-"],
            "i-129": ["i-129", "petition for a nonimmigrant worker", "form i-129"],
            "g-28": ["g-28", "g28", "notice of entry of appearance"],
            "i-129dc": ["i-129dc", "i129dc", "data collection"],
            "i-129h": ["i-129h", "i129h", "h classification supplement"],
            "i-907": ["i-907", "i907", "premium processing"],
            "i-539": ["i-539", "i539", "extend/change nonimmigrant status"],
            "i-539a": ["i-539a", "i539a", "supplemental information"],
            "i-g28": ["i-g28", "ig28"],
            "i-i907": ["i-i907", "ii907"],
            "i-765": ["i-765", "i765", "employment authorization"],
            "i-140": ["i-140", "i140", "immigrant petition for alien worker"],
            "i-129l": ["i-129l", "i129l", "l classification supplement"],
            "i-918": ["i-918", "i918", "u nonimmigrant status"],
            "i-765g28": ["i-765g28", "i765g28"],
            "i-i140": ["i-i140", "ii140"],
            "h-2b": ["h-2b", "h2b"],
            "eta-9089": ["eta-9089", "eta 9089", "eta9089", "perm"],
            "i-129tn": ["i-129tn", "i129tn", "tn classification"],
            "i-129t": ["i-129t", "i129t", "t classification"],
            "i-131": ["i-131", "i131", "travel document"],
            "i-485": ["i-485", "i485", "adjust status", "green card"],
            "i-485j": ["i-485j", "i485j", "job offer"],
            "i-485a": ["i-485a", "i485a", "adjustment of status"],
            "i-864": ["i-864", "i864", "affidavit of support"],
            "i-864a": ["i-864a", "i864a", "contract between sponsor"],
            "i-129r": ["i-129r", "i129r", "religious worker"],
            "i-829": ["i-829", "i829", "remove conditions"]
        }
        
        for form_type, patterns in form_patterns.items():
            for pattern in patterns:
                if pattern in content_lower:
                    return FormType(form_type.upper().replace("_", "-"))
        
        return FormType.UNKNOWN
    
    def extract_fields_from_pdf(self, pdf_content: bytes) -> Tuple[FormType, List[FormField]]:
        """Extract form type and fields from PDF content"""
        try:
            pdf_reader = PyPDF2.PdfReader(BytesIO(pdf_content))
            text_content = ""
            
            # Extract text from all pages
            for page in pdf_reader.pages:
                text_content += page.extract_text() + "\n"
            
            # Detect form type
            form_type = self.detect_form_type(text_content)
            
            # Get mapped fields
            if form_type.value in self.form_mappings:
                fields = self.form_mappings[form_type.value]
            else:
                fields = []
            
            return form_type, fields
            
        except Exception as e:
            st.error(f"Error processing PDF: {str(e)}")
            return FormType.UNKNOWN, []
    
    def generate_questionnaire(self, fields: List[FormField], form_type: str) -> Dict[str, Any]:
        """Generate questionnaire JSON for unmapped fields"""
        controls = []
        unmapped_fields = [f for f in fields if not f.is_mapped]
        
        for field in unmapped_fields:
            control = {
                "name": field.pdf_field_name.lower().replace(" ", "_"),
                "label": field.label or field.pdf_field_name,
                "type": self._map_field_type_to_control(field.field_type),
                "validators": {"required": False},
                "style": {"col": "6"}
            }
            
            if field.is_conditional:
                control["className"] = "hide-dummy-class"
                control["condition"] = field.condition
            
            controls.append(control)
        
        return {
            "form_type": form_type,
            "controls": controls
        }
    
    def _map_field_type_to_control(self, field_type: str) -> str:
        """Map PDF field type to control type"""
        mapping = {
            "TextBox": "text",
            "CheckBox": "checkbox",
            "RadioButton": "radio",
            "DropDown": "dropdown",
            "DateField": "date"
        }
        return mapping.get(field_type, "text")
    
    def generate_typescript_mapping(self, form_type: str, fields: List[FormField]) -> str:
        """Generate TypeScript mapping code"""
        ts_code = f"""export const {form_type.replace("-", "_")}_MAPPING = [
"""
        
        for field in fields:
            ts_code += f"""    {{
        Name: "{field.pdf_field_name}",
        Value: "{field.database_mapping}",
        Type: "{field.field_type}",
        Label: "{field.label}"
    }},
"""
        
        ts_code += "];\n"
        return ts_code
    
    def generate_consolidated_json(self, form_type: str, fields: List[FormField], questionnaire: Dict) -> Dict:
        """Generate consolidated JSON with all mappings and questionnaire"""
        mapped_fields = [f for f in fields if f.is_mapped]
        unmapped_fields = [f for f in fields if not f.is_mapped]
        
        return {
            "form_type": form_type,
            "total_fields": len(fields),
            "mapped_fields_count": len(mapped_fields),
            "unmapped_fields_count": len(unmapped_fields),
            "coverage_percentage": (len(mapped_fields) / len(fields) * 100) if fields else 0,
            "mapped_fields": [
                {
                    "pdf_field_name": f.pdf_field_name,
                    "database_mapping": f.database_mapping,
                    "field_type": f.field_type,
                    "label": f.label,
                    "default_value": f.default_value,
                    "is_conditional": f.is_conditional,
                    "condition": f.condition
                } for f in mapped_fields
            ],
            "unmapped_fields": [
                {
                    "pdf_field_name": f.pdf_field_name,
                    "field_type": f.field_type,
                    "label": f.label,
                    "suggested_control": self._map_field_type_to_control(f.field_type)
                } for f in unmapped_fields
            ],
            "questionnaire": questionnaire
        }

def main():
    st.set_page_config(
        page_title="USCIS Form Mapper & Questionnaire Generator",
        page_icon="📄",
        layout="wide"
    )
    
    st.title("📄 USCIS Form Mapper & Questionnaire Generator")
    st.markdown("Upload USCIS forms to generate field mappings and questionnaires")
    
    # Initialize the mapper
    mapper = USCISFormMapper()
    
    # File upload
    uploaded_file = st.file_uploader(
        "Upload USCIS Form (PDF)",
        type=['pdf'],
        help="Upload a USCIS form PDF to analyze its fields and generate mappings"
    )
    
    if uploaded_file is not None:
        # Process the PDF
        pdf_content = uploaded_file.read()
        form_type, fields = mapper.extract_fields_from_pdf(pdf_content)
        
        if form_type == FormType.UNKNOWN:
            st.warning("⚠️ Unknown form type. Please ensure you've uploaded a valid USCIS form.")
        else:
            st.success(f"✅ Detected Form Type: **{form_type.value}**")
            
            # Create tabs
            tab1, tab2, tab3, tab4, tab5 = st.tabs([
                "📋 Field Mappings", 
                "❓ Questionnaire JSON", 
                "📊 Summary Statistics",
                "💻 TypeScript Code",
                "🔄 Consolidated JSON"
            ])
            
            with tab1:
                st.header("Field Mappings")
                
                # Separate mapped and unmapped fields
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
                                "Database Mapping": field.database_mapping,
                                "Type": field.field_type,
                                "Label": field.label
                            })
                        
                        df_mapped = pd.DataFrame(mapped_data)
                        st.dataframe(df_mapped, use_container_width=True, height=400)
                    else:
                        st.info("No mapped fields found")
                
                with col2:
                    st.subheader(f"🔴 Unmapped Fields ({len(unmapped_fields)})")
                    if unmapped_fields:
                        unmapped_data = []
                        for field in unmapped_fields:
                            unmapped_data.append({
                                "PDF Field": field.pdf_field_name,
                                "Type": field.field_type,
                                "Label": field.label,
                                "Conditional": "Yes" if field.is_conditional else "No"
                            })
                        
                        df_unmapped = pd.DataFrame(unmapped_data)
                        st.dataframe(df_unmapped, use_container_width=True, height=400)
                    else:
                        st.success("All fields are mapped!")
            
            with tab2:
                st.header("Questionnaire JSON")
                
                questionnaire = mapper.generate_questionnaire(fields, form_type.value)
                
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
                
                # Visual representation
                if len(fields) > 0:
                    st.subheader("Field Mapping Coverage")
                    progress_bar = st.progress(0)
                    progress_bar.progress(mapped_count / len(fields))
                    
                    # Field type distribution
                    st.subheader("Field Type Distribution")
                    field_types = {}
                    for field in fields:
                        field_types[field.field_type] = field_types.get(field.field_type, 0) + 1
                    
                    df_types = pd.DataFrame(
                        list(field_types.items()),
                        columns=["Field Type", "Count"]
                    )
                    st.bar_chart(df_types.set_index("Field Type"))
            
            with tab4:
                st.header("TypeScript Mapping Code")
                
                ts_code = mapper.generate_typescript_mapping(form_type.value, fields)
                st.code(ts_code, language="typescript")
                
                # Download button
                st.download_button(
                    label="📥 Download TypeScript Code",
                    data=ts_code,
                    file_name=f"{form_type.value.lower()}_mapping.ts",
                    mime="text/plain"
                )
            
            with tab5:
                st.header("Consolidated JSON")
                
                questionnaire = mapper.generate_questionnaire(fields, form_type.value)
                consolidated = mapper.generate_consolidated_json(form_type.value, fields, questionnaire)
                
                st.json(consolidated)
                
                # Download button
                consolidated_str = json.dumps(consolidated, indent=2)
                st.download_button(
                    label="📥 Download Consolidated JSON",
                    data=consolidated_str,
                    file_name=f"{form_type.value.lower()}_consolidated.json",
                    mime="application/json"
                )
    
    else:
        st.info("👆 Please upload a USCIS form PDF to begin analysis")
        
        # Show supported forms
        with st.expander("📋 Supported Forms", expanded=True):
            forms = [
                "LCA - Labor Condition Application",
                "I-129 - Petition for a Nonimmigrant Worker",
                "I-140 - Immigrant Petition for Alien Worker",
                "I-485 - Application to Adjust Status",
                "I-539 - Application to Extend/Change Nonimmigrant Status",
                "I-765 - Application for Employment Authorization",
                "I-907 - Request for Premium Processing",
                "G-28 - Notice of Entry of Appearance",
                "I-131 - Application for Travel Document",
                "I-864 - Affidavit of Support",
                "I-918 - Petition for U Nonimmigrant Status",
                "I-829 - Petition to Remove Conditions",
                "ETA-9089 - Application for Permanent Employment Certification",
                "And many more..."
            ]
            
            for i in range(0, len(forms), 2):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"• {forms[i]}")
                with col2:
                    if i + 1 < len(forms):
                        st.write(f"• {forms[i + 1]}")

if __name__ == "__main__":
    main()
