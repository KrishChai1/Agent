import streamlit as st
import json
import re
import fitz  # PyMuPDF
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Union
from collections import OrderedDict, defaultdict
import pandas as pd
from dataclasses import dataclass, field
import difflib

# Comprehensive USCIS Forms Database
USCIS_FORMS_DATABASE = {
    "I-90": {
        "title": "Application to Replace Permanent Resident Card",
        "keywords": ["permanent resident card", "green card", "replace", "renew"],
        "identifier_patterns": ["Form I-90", "I-90", "OMB No. 1615-0052"],
        "has_g28": True
    },
    "I-129": {
        "title": "Petition for a Nonimmigrant Worker",
        "keywords": ["nonimmigrant worker", "h1b", "l1", "petition"],
        "identifier_patterns": ["Form I-129", "I-129", "OMB No. 1615-0009"],
        "has_g28": True
    },
    "I-130": {
        "title": "Petition for Alien Relative",
        "keywords": ["alien relative", "family", "petition"],
        "identifier_patterns": ["Form I-130", "I-130", "OMB No. 1615-0012"],
        "has_g28": True
    },
    "I-131": {
        "title": "Application for Travel Document",
        "keywords": ["travel document", "reentry permit", "refugee travel"],
        "identifier_patterns": ["Form I-131", "I-131", "OMB No. 1615-0013"],
        "has_g28": True
    },
    "I-140": {
        "title": "Immigrant Petition for Alien Workers",
        "keywords": ["immigrant petition", "alien worker", "employment based"],
        "identifier_patterns": ["Form I-140", "I-140", "OMB No. 1615-0015"],
        "has_g28": True
    },
    "I-485": {
        "title": "Application to Register Permanent Residence or Adjust Status",
        "keywords": ["adjust status", "permanent residence", "green card application"],
        "identifier_patterns": ["Form I-485", "I-485", "OMB No. 1615-0023"],
        "has_g28": True
    },
    "I-539": {
        "title": "Application To Extend/Change Nonimmigrant Status",
        "keywords": ["extend status", "change status", "nonimmigrant"],
        "identifier_patterns": ["Form I-539", "I-539", "OMB No. 1615-0003"],
        "has_g28": True
    },
    "I-765": {
        "title": "Application for Employment Authorization",
        "keywords": ["employment authorization", "work permit", "ead"],
        "identifier_patterns": ["Form I-765", "I-765", "OMB No. 1615-0040"],
        "has_g28": True
    },
    "N-400": {
        "title": "Application for Naturalization",
        "keywords": ["naturalization", "citizenship", "citizen"],
        "identifier_patterns": ["Form N-400", "N-400", "OMB No. 1615-0052"],
        "has_g28": True
    },
    "N-600": {
        "title": "Application for Certificate of Citizenship",
        "keywords": ["certificate of citizenship", "citizenship certificate"],
        "identifier_patterns": ["Form N-600", "N-600", "OMB No. 1615-0057"],
        "has_g28": True
    },
    "I-751": {
        "title": "Petition to Remove Conditions on Residence",
        "keywords": ["remove conditions", "conditional residence"],
        "identifier_patterns": ["Form I-751", "I-751", "OMB No. 1615-0038"],
        "has_g28": True
    },
    "I-526": {
        "title": "Immigrant Petition by Alien Investor",
        "keywords": ["investor", "eb-5", "investment"],
        "identifier_patterns": ["Form I-526", "I-526", "OMB No. 1615-0026"],
        "has_g28": True
    },
    "I-601": {
        "title": "Application for Waiver of Grounds of Inadmissibility",
        "keywords": ["waiver", "inadmissibility", "grounds"],
        "identifier_patterns": ["Form I-601", "I-601", "OMB No. 1615-0029"],
        "has_g28": True
    },
    "I-821": {
        "title": "Application for Temporary Protected Status",
        "keywords": ["temporary protected status", "tps"],
        "identifier_patterns": ["Form I-821", "I-821", "OMB No. 1615-0043"],
        "has_g28": True
    },
    "I-914": {
        "title": "Application for T Nonimmigrant Status",
        "keywords": ["t visa", "trafficking victim"],
        "identifier_patterns": ["Form I-914", "I-914", "OMB No. 1615-0099"],
        "has_g28": True
    },
    "I-918": {
        "title": "Petition for U Nonimmigrant Status",
        "keywords": ["u visa", "crime victim"],
        "identifier_patterns": ["Form I-918", "I-918", "OMB No. 1615-0104"],
        "has_g28": True
    },
    "G-28": {
        "title": "Notice of Entry of Appearance as Attorney or Accredited Representative",
        "keywords": ["attorney", "representative", "appearance"],
        "identifier_patterns": ["Form G-28", "G-28", "OMB No. 1615-0105"],
        "has_g28": False
    },
    "G-325A": {
        "title": "Biographic Information",
        "keywords": ["biographic", "information"],
        "identifier_patterns": ["Form G-325A", "G-325A"],
        "has_g28": False
    },
    "AR-11": {
        "title": "Alien's Change of Address",
        "keywords": ["change of address", "address change"],
        "identifier_patterns": ["Form AR-11", "AR-11", "OMB No. 1615-0007"],
        "has_g28": False
    }
}

# Enhanced Database Object Structure
DB_OBJECTS = {
    "attorney": {
        "attorneyInfo": [
            "firstName", "lastName", "middleName", "workPhone", "mobilePhone", 
            "emailAddress", "faxNumber", "stateBarNumber", "licensingAuthority", 
            "stateOfHighestCourt", "nameOfHighestCourt", "signature",
            "uscisOnlineAccountNumber", "inCareOf"
        ],
        "address": [
            "addressStreet", "addressCity", "addressState", "addressZip", 
            "addressCountry", "addressNumber", "addressType"
        ]
    },
    "attorneyLawfirmDetails": {
        "lawfirmDetails": ["lawFirmName", "lawFirmFein"],
        "address": [
            "addressStreet", "addressCity", "addressState", "addressZip", 
            "addressCountry", "addressNumber", "addressType"
        ]
    },
    "beneficiary": {
        "Beneficiary": [
            "beneficiaryFirstName", "beneficiaryLastName", "beneficiaryMiddleName",
            "beneficiaryGender", "beneficiaryDateOfBirth", "beneficiarySsn",
            "alienNumber", "beneficiaryCountryOfBirth", "beneficiaryProvinceOfBirth",
            "stateBirth", "beneficiaryCitizenOfCountry", "beneficiaryCellNumber",
            "beneficiaryHomeNumber", "beneficiaryWorkNumber", "beneficiaryPrimaryEmailAddress",
            "maritalStatus", "fatherFirstName", "fatherLastName", "motherFirstName", 
            "motherLastName", "beneficiarySalutation", "beneficiaryVisaType",
            "beneficiaryDependentsCount", "beneficiaryInCareOf", "beneficiaryUscisAccountNumber"
        ],
        "HomeAddress": [
            "addressStreet", "addressCity", "addressState", "addressZip", 
            "addressCountry", "addressNumber", "addressType"
        ],
        "MailingAddress": [
            "addressStreet", "addressCity", "addressState", "addressZip", 
            "addressCountry", "addressNumber", "addressType"
        ],
        "WorkAddress": [
            "addressStreet", "addressCity", "addressState", "addressZip", 
            "addressCountry", "addressNumber", "addressType"
        ],
        "ForeignAddress": [
            "addressStreet", "addressCity", "addressState", "addressZip", 
            "addressCountry", "addressNumber", "addressType", "addressCounty"
        ],
        "PhysicalAddress": [
            "addressStreet", "addressCity", "addressState", "addressZip", 
            "addressCountry", "addressNumber", "addressType"
        ],
        "PassportDetails": {
            "Passport": [
                "passportNumber", "passportIssueCountry", 
                "passportIssueDate", "passportExpiryDate"
            ]
        },
        "VisaDetails": {
            "Visa": [
                "visaStatus", "visaExpiryDate", "visaConsulateCity", 
                "visaConsulateCountry", "visaNumber", "f1SevisNumber", 
                "eligibilityCategory", "visaAbroad", "newEffectiveDate",
                "changeOfStatus", "extensionUntil", "eduDegree",
                "employerName", "employerEverify", "arrestedCrime",
                "spouseUscisReceipt", "f1OptEadNumber"
            ]
        },
        "I94Details": {
            "I94": [
                "i94Number", "i94ArrivalDate", "i94ExpiryDate", 
                "i94DepartureDate", "placeLastArrival", "statusAtArrival"
            ]
        },
        "H1bDetails": {
            "H1b": [
                "h1bReceiptNumber", "h1bStartDate", "h1bExpiryDate", 
                "h1bType", "h1bStatus"
            ]
        },
        "GcDetails": {
            "Gc": [
                "gcType", "gcAlienNumber", "gcReceiptNumber"
            ]
        },
        "F1Details": {
            "F1": [
                "sevisNumber", "optEadNumber"
            ]
        },
        "EducationDetails": {
            "BeneficiaryEducation": [
                "universityName", "degreeType", "majorFieldOfStudy", 
                "graduationYear"
            ],
            "Address": [
                "addressStreet", "addressCity", "addressState", "addressZip",
                "addressCountry", "addressType", "addressNumber"
            ]
        },
        "WorkExperienceDetails": {
            "WorkExperienceDetail": [
                "employerName", "jobTitle", "startDate", "endDate", "jobDetails"
            ],
            "Address": [
                "addressStreet", "addressCity", "addressState", "addressZip",
                "addressCountry", "addressType", "addressNumber"
            ]
        },
        "BdDetails": {
            "BeneficiaryDependent": [
                "dependentFirstName", "dependentLastName", "dependentMiddleName",
                "dependentDateOfBirth", "dependentCountryOfBirth", "dependentType",
                "adjustmentOfStatus", "visaAbroad", "dependentAlienNumber",
                "dependentGender", "dependentCitizenOfCountry", "dependentSocialSecurityNumber",
                "dateOfArrival", "i94Number", "passportNumber", "countryOfPassport",
                "passportExpiryDate", "dependentCurrentVisaStatus", "dependentVisaExpiryDate"
            ]
        }
    },
    "customer": {
        "": [
            "customer_name", "customer_type_of_business", "customer_tax_id", 
            "customer_naics_code", "customer_total_employees", "customer_total_h1b_employees", 
            "customer_gross_annual_income", "customer_net_annual_income", 
            "customer_year_established", "customer_dot_code", "h1_dependent_employer", 
            "willful_violator", "higher_education_institution", "nonprofit_organization", 
            "nonprofit_research_organization", "cap_exempt_institution",
            "primary_secondary_education_institution", "nonprofit_clinical_institution",
            "guam_cnmi_cap_exemption", "managing_attorney_id"
        ],
        "signatory": [
            "signatory_first_name", "signatory_last_name", "signatory_middle_name",
            "signatory_job_title", "signatory_work_phone", "signatory_mobile_phone",
            "signatory_email_id", "signatory_digital_signature"
        ],
        "address": [
            "address_street", "address_city", "address_state", "address_zip",
            "address_country", "address_number", "address_type"
        ]
    },
    "case": {
        "": [
            "caseType", "caseSubType", "h1BPetitionType", "premiumProcessing", 
            "h1BRegistrationNumber", "h4Filing", "carrier", "serviceCenter",
            "wageLevel", "requestedAction", "basis", "receiptNumber"
        ]
    },
    "lca": {
        "": [
            "positionJobTitle", "inhouseProject", "endClientName", "jobLocation",
            "grossSalary", "swageUnit", "startDate", "endDate", "prevailingWageRate",
            "pwageUnit", "socOnetOesCode", "socOnetOesTitle", "fullTimePosition",
            "wageLevel", "sourceYear", "lcaNumber"
        ],
        "Addresses": [
            "addressStreet", "addressCity", "addressState", "addressZip",
            "addressCounty", "addressType", "addressNumber"
        ]
    }
}

# Form Intelligence Rules
FORM_INTELLIGENCE = {
    "part_detection_rules": {
        # Part 0 is ALWAYS attorney/representative when specific text is found
        "attorney_section_triggers": [
            "to be completed by attorney or accredited representative",
            "to be completed by an attorney or accredited representative",
            "if any form g-28",
            "if form g-28 is attached",
            "g-28 is attached to this petition"
        ],
        "attorney_indicators": [
            "attorney", "representative", "g-28", "g28", "bar number", 
            "licensing authority", "appearance", "accredited", "bia",
            "law firm", "fein", "ein", "notice of entry"
        ],
        # Information About You = Beneficiary
        "beneficiary_indicators": [
            "information about you", "your name", "your information",
            "applicant information", "personal information", "about yourself"
        ],
        # Petitioner/Company indicators
        "petitioner_indicators": [
            "petitioner information", "employer information", "company",
            "organization", "business", "sponsor", "requestor"
        ]
    },
    "field_mapping_patterns": {
        # Enhanced patterns for better detection
        "names": {
            "last": ["lastname", "last_name", "family_name", "apellido", "surname"],
            "first": ["firstname", "first_name", "given_name", "nombre"],
            "middle": ["middlename", "middle_name", "middle_initial", "mi"]
        },
        "identifiers": {
            "alien": ["alien", "a-number", "anumber", "uscis number", "registration number"],
            "ssn": ["ssn", "social security", "social_security", "ss#"],
            "ein": ["ein", "fein", "tax id", "tax_id", "federal ein"],
            "passport": ["passport", "travel document", "pasaporte"],
            "i94": ["i-94", "i94", "arrival record", "departure record"]
        },
        "contact": {
            "phone": ["phone", "telephone", "tel", "mobile", "cell", "daytime"],
            "email": ["email", "e-mail", "electronic mail"],
            "fax": ["fax", "facsimile"]
        },
        "address": {
            "street": ["street", "address", "calle", "line 1"],
            "apt": ["apt", "apartment", "suite", "ste", "floor", "flr", "unit"],
            "city": ["city", "ciudad", "town"],
            "state": ["state", "province", "estado"],
            "zip": ["zip", "postal", "codigo postal", "zip code"],
            "country": ["country", "pais", "nation"]
        }
    }
}

# Enhanced field type mappings
FIELD_TYPE_SUFFIX_MAP = {
    "text": ":TextBox",
    "checkbox": ":CheckBox",
    "radio": ":ConditionBox",
    "select": ":SelectBox",
    "date": ":Date",
    "signature": ":SignatureBox",
    "listbox": ":ListBox",
    "number": ":NumberBox"
}

# Enhanced form structures
ENHANCED_FORM_STRUCTURES = {
    "G-28": {
        "Part 1": "Information About Attorney or Accredited Representative",
        "Part 2": "Eligibility Information for Attorney or Accredited Representative",
        "Part 3": "Notice of Appearance",
        "Part 4": "Client Consent",
        "Part 5": "Attorney Signature",
        "Part 6": "Additional Information"
    },
    "I-90": {
        "Part 0": "To be completed by attorney or BIA-accredited representative (if Form G-28 is attached)",
        "Part 1": "Information About You",
        "Part 2": "Application Type",
        "Part 3": "Processing Information",
        "Part 4": "Applicant's Statement",
        "Part 5": "Interpreter's Contact Information",
        "Part 6": "Contact Information of Preparer",
        "Part 7": "Additional Information"
    },
    "I-539": {
        "Part 0": "To be completed by attorney or BIA-accredited representative (if Form G-28 is attached)",
        "Part 1": "Information About You",
        "Part 2": "Application Type",
        "Part 3": "Processing Information",
        "Part 4": "Additional Information About You",
        "Part 5": "Applicant's Statement and Signature",
        "Part 6": "Interpreter's Information",
        "Part 7": "Contact Information, Statement, and Signature of Preparer",
        "Part 8": "Additional Information"
    },
    "I-129": {
        "Part 0": "To be completed by attorney or BIA-accredited representative (if Form G-28 is attached)",
        "Part 1": "Petitioner Information",
        "Part 2": "Information About This Petition",
        "Part 3": "Beneficiary Information",
        "Part 4": "Processing Information",
        "Part 5": "Basic Information About Employment",
        "Part 6": "Export Control Certification",
        "Part 7": "Petitioner Declaration",
        "Part 8": "Preparer Information",
        "Part 9": "Additional Information"
    },
    "I-485": {
        "Part 0": "To be completed by attorney or BIA-accredited representative (if Form G-28 is attached)",
        "Part 1": "Information About You",
        "Part 2": "Application Type",
        "Part 3": "Additional Information About You",
        "Part 4": "Address History",
        "Part 5": "Marital History",
        "Part 6": "Information About Your Children",
        "Part 7": "Biographic Information",
        "Part 8": "General Eligibility and Inadmissibility Grounds",
        "Part 9": "Accommodations for Individuals With Disabilities",
        "Part 10": "Applicant's Statement and Signature",
        "Part 11": "Interpreter's Information",
        "Part 12": "Contact Information of Preparer",
        "Part 13": "Additional Information"
    },
    "I-765": {
        "Part 0": "To be completed by attorney or BIA-accredited representative (if Form G-28 is attached)",
        "Part 1": "Information About You",
        "Part 2": "Information About Your Eligibility",
        "Part 3": "Applicant's Statement and Signature",
        "Part 4": "Interpreter's Information",
        "Part 5": "Contact Information of Preparer",
        "Part 6": "Additional Information"
    },
    "N-400": {
        "Part 0": "To be completed by attorney or BIA-accredited representative (if Form G-28 is attached)",
        "Part 1": "Information About Your Eligibility",
        "Part 2": "Information About You",
        "Part 3": "Accommodations for Individuals With Disabilities",
        "Part 4": "Information to Contact You",
        "Part 5": "Information About Your Residence",
        "Part 6": "Information About Your Parents",
        "Part 7": "Biographic Information",
        "Part 8": "Information About Your Employment and Schools",
        "Part 9": "Time Outside the United States",
        "Part 10": "Information About Your Marital History",
        "Part 11": "Information About Your Children",
        "Part 12": "Additional Information About You",
        "Part 13": "Applicant's Statement and Signature",
        "Part 14": "Interpreter's Information",
        "Part 15": "Contact Information of Preparer",
        "Part 16": "Additional Information"
    },
    "I-130": {
        "Part 0": "To be completed by attorney or BIA-accredited representative (if Form G-28 is attached)",
        "Part 1": "Relationship",
        "Part 2": "Information About You (Petitioner)",
        "Part 3": "Biographic Information (Petitioner)",
        "Part 4": "Information About Your Relative",
        "Part 5": "Other Information",
        "Part 6": "Petitioner's Statement and Signature",
        "Part 7": "Interpreter's Information",
        "Part 8": "Contact Information of Preparer",
        "Part 9": "Additional Information"
    },
    "I-140": {
        "Part 0": "To be completed by attorney or BIA-accredited representative (if Form G-28 is attached)",
        "Part 1": "Information About You (Petitioner)",
        "Part 2": "Petition Type",
        "Part 3": "Information About the Person for Whom You Are Filing",
        "Part 4": "Processing Information",
        "Part 5": "Additional Information About Petitioner",
        "Part 6": "Petitioner's Statement and Signature",
        "Part 7": "Interpreter's Information",
        "Part 8": "Contact Information of Preparer",
        "Part 9": "Additional Information"
    }
}

@dataclass
class PDFField:
    """Enhanced field representation with better intelligence"""
    index: int
    raw_name: str
    field_type: str
    value: str = ""
    page: int = 1
    part: str = ""
    item: str = ""
    description: str = ""
    db_mapping: Optional[str] = None
    mapping_type: str = "direct"
    mapping_config: Optional[Dict[str, Any]] = None
    is_mapped: bool = False
    is_questionnaire: bool = False
    confidence_score: float = 0.0
    field_type_suffix: str = ":TextBox"
    clean_name: str = ""
    is_custom_field: bool = False
    form_context: Dict[str, Any] = field(default_factory=dict)
    ai_suggestions: List[str] = field(default_factory=list)
    # New field to track page position within part
    position_in_part: int = 0

@dataclass
class MappingSuggestion:
    """Enhanced mapping suggestion with reasoning"""
    db_path: str
    confidence: float
    reason: str
    field_type: str = "direct"
    context_based: bool = False

class EnhancedUSCISMapper:
    """Enhanced Universal USCIS Form Mapping System with AI-like intelligence"""
    
    def __init__(self):
        self.db_objects = DB_OBJECTS
        self.form_intelligence = FORM_INTELLIGENCE
        self.enhanced_structures = ENHANCED_FORM_STRUCTURES
        self.uscis_forms = USCIS_FORMS_DATABASE
        self.init_session_state()
        self._build_database_paths_cache()
        self._initialize_intelligence_engine()
        
    def init_session_state(self):
        """Initialize enhanced session state"""
        if 'form_type' not in st.session_state:
            st.session_state.form_type = None
        if 'pdf_fields' not in st.session_state:
            st.session_state.pdf_fields = []
        if 'field_mappings' not in st.session_state:
            st.session_state.field_mappings = {}
        if 'has_attorney_section' not in st.session_state:
            st.session_state.has_attorney_section = False
        if 'form_context' not in st.session_state:
            st.session_state.form_context = {}
        if 'mapping_history' not in st.session_state:
            st.session_state.mapping_history = []
        if 'ai_confidence_threshold' not in st.session_state:
            st.session_state.ai_confidence_threshold = 0.8
        if 'detected_form_type' not in st.session_state:
            st.session_state.detected_form_type = None
        if 'detection_confidence' not in st.session_state:
            st.session_state.detection_confidence = 0.0
        if 'part0_fields' not in st.session_state:
            st.session_state.part0_fields = []
    
    def _initialize_intelligence_engine(self):
        """Initialize the AI-like intelligence for better mapping"""
        self.context_patterns = {
            "form_has_attorney": False,
            "beneficiary_parts": [],
            "petitioner_parts": [],
            "current_form_type": None,
            "detected_patterns": {},
            "field_relationships": {}
        }
        
        # Learning patterns from successful mappings
        self.learning_patterns = defaultdict(lambda: defaultdict(float))
    
    def _build_database_paths_cache(self):
        """Build enhanced cache with categorization"""
        self.db_paths_cache = []
        self.categorized_paths = defaultdict(list)
        
        def extract_paths(obj_name, structure, prefix=""):
            """Recursively extract and categorize paths"""
            if isinstance(structure, dict):
                for key, value in structure.items():
                    if key == "":
                        if isinstance(value, list):
                            for field_name in value:
                                path = f"{obj_name}.{field_name}"
                                self.db_paths_cache.append(path)
                                self.categorized_paths[obj_name].append(path)
                    else:
                        new_prefix = f"{obj_name}.{key}"
                        if isinstance(value, list):
                            for field_name in value:
                                path = f"{new_prefix}.{field_name}"
                                self.db_paths_cache.append(path)
                                self.categorized_paths[obj_name].append(path)
                        elif isinstance(value, dict):
                            for nested_key, nested_value in value.items():
                                if isinstance(nested_value, list):
                                    for field_name in nested_value:
                                        path = f"{new_prefix}.{nested_key}.{field_name}"
                                        self.db_paths_cache.append(path)
                                        self.categorized_paths[obj_name].append(path)
        
        for obj_name, obj_structure in self.db_objects.items():
            extract_paths(obj_name, obj_structure)
        
        self.db_paths_cache = sorted(list(set(self.db_paths_cache)))
    
    def detect_form_type(self, pdf_file) -> Tuple[Optional[str], float]:
        """Automatically detect USCIS form type from PDF content"""
        try:
            pdf_bytes = pdf_file.read()
            pdf_file.seek(0)  # Reset file pointer
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            # Extract text from first few pages
            text_content = ""
            for page_num in range(min(3, len(doc))):
                page = doc[page_num]
                text_content += page.get_text() + " "
            
            doc.close()
            
            # Clean text
            text_lower = text_content.lower()
            text_upper = text_content.upper()
            
            # Detection scores for each form
            form_scores = {}
            
            for form_code, form_info in self.uscis_forms.items():
                score = 0.0
                matches = []
                
                # Check identifier patterns (highest weight)
                for pattern in form_info["identifier_patterns"]:
                    if pattern in text_content or pattern in text_upper:
                        score += 0.5
                        matches.append(f"Found identifier: {pattern}")
                
                # Check form code specifically
                if form_code in text_upper or f"FORM {form_code}" in text_upper:
                    score += 0.3
                    matches.append(f"Found form code: {form_code}")
                
                # Check keywords
                keyword_matches = sum(1 for keyword in form_info["keywords"] if keyword in text_lower)
                if keyword_matches > 0:
                    score += 0.2 * (keyword_matches / len(form_info["keywords"]))
                    matches.append(f"Matched {keyword_matches} keywords")
                
                # Check title
                if form_info["title"].lower() in text_lower:
                    score += 0.3
                    matches.append("Title match")
                
                form_scores[form_code] = {
                    "score": min(score, 1.0),
                    "matches": matches
                }
            
            # Find best match
            best_form = None
            best_score = 0.0
            
            for form_code, data in form_scores.items():
                if data["score"] > best_score:
                    best_score = data["score"]
                    best_form = form_code
            
            # Set threshold for confident detection
            if best_score >= 0.5:
                return best_form, best_score
            else:
                return None, 0.0
                
        except Exception as e:
            st.error(f"Error detecting form type: {str(e)}")
            return None, 0.0
    
    def extract_pdf_fields(self, pdf_file, form_type: str) -> List[PDFField]:
        """Enhanced extraction with intelligent part detection"""
        fields = []
        self.field_counter = 1
        
        try:
            pdf_bytes = pdf_file.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            # Clean form type
            base_form_type = form_type
            
            # First pass: collect text from first page to detect attorney section
            first_page_text = ""
            if len(doc) > 0:
                first_page_text = doc[0].get_text().lower()
            
            # Enhanced attorney section detection - look for the specific trigger text
            has_attorney_text = False
            for trigger in self.form_intelligence["part_detection_rules"]["attorney_section_triggers"]:
                if trigger in first_page_text:
                    has_attorney_text = True
                    st.session_state.has_attorney_section = True
                    break
            
            # Get form-specific structure
            form_structure = self.enhanced_structures.get(base_form_type, {})
            
            # If attorney section detected but form doesn't have Part 0, add it
            if st.session_state.has_attorney_section and "Part 0" not in form_structure:
                form_structure = {
                    "Part 0": "To be completed by attorney or BIA-accredited representative (if Form G-28 is attached)",
                    **form_structure
                }
            
            # Collect all field data with position tracking
            all_field_data = []
            field_index = 0
            seen_fields = set()
            
            # Track attorney fields found in the initial section
            attorney_section_fields = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_text = page.get_text().lower()
                
                # Check if this page has attorney section trigger
                has_attorney_trigger = any(trigger in page_text for trigger in 
                                         self.form_intelligence["part_detection_rules"]["attorney_section_triggers"])
                
                for widget in page.widgets():
                    if widget.field_name and widget.field_name not in seen_fields:
                        seen_fields.add(widget.field_name)
                        
                        field_data = {
                            'name': widget.field_name,
                            'page': page_num + 1,
                            'widget': widget,
                            'index': field_index,
                            'display': widget.field_display or "",
                            'page_has_attorney_trigger': has_attorney_trigger
                        }
                        
                        # If we're on page 1 and attorney trigger was found
                        if page_num == 0 and has_attorney_trigger:
                            # Check if this field appears after the attorney trigger text
                            # This is a simplified check - in reality you'd want more sophisticated position checking
                            field_text = f"{widget.field_name} {widget.field_display or ''}".lower()
                            
                            # Count as potential attorney field if it's on the same page as the trigger
                            if len(attorney_section_fields) < 5:  # Assuming max 5 fields in attorney section
                                attorney_section_fields.append(field_index)
                        
                        all_field_data.append(field_data)
                        field_index += 1
            
            # Store detected attorney fields
            st.session_state.part0_fields = attorney_section_fields
            
            # Intelligent part mapping with enhanced attorney detection
            part_mapping = self._intelligent_part_detection_fixed(
                all_field_data, base_form_type, form_structure, attorney_section_fields
            )
            
            # Second pass: create field objects with intelligence
            for field_data in all_field_data:
                widget = field_data['widget']
                
                # Extract field information
                field_type = self._get_field_type(widget)
                part = part_mapping.get(field_data['index'], f"Page {field_data['page']}")
                item = self._extract_item_intelligent(widget.field_name, field_data['display'])
                description = self._generate_intelligent_description(widget.field_name, widget.field_display, part)
                field_type_suffix = self._get_intelligent_field_suffix(widget.field_name, field_type, description)
                clean_name = self._generate_clean_name_enhanced(widget.field_name, part, item, field_data['index'])
                
                # Store form context
                form_context = {
                    "form_type": base_form_type,
                    "has_attorney": st.session_state.has_attorney_section,
                    "part_context": self._get_part_context(part),
                    "page": field_data['page'],
                    "is_attorney_field": field_data['index'] in attorney_section_fields
                }
                
                # Create field object
                pdf_field = PDFField(
                    index=field_data['index'],
                    raw_name=widget.field_name,
                    field_type=field_type,
                    value=widget.field_value or '',
                    page=field_data['page'],
                    part=part,
                    item=item,
                    description=description,
                    field_type_suffix=field_type_suffix,
                    clean_name=clean_name,
                    form_context=form_context
                )
                
                # Get intelligent mapping suggestions
                suggestions = self._get_intelligent_suggestions(pdf_field, base_form_type)
                if suggestions:
                    best_suggestion = suggestions[0]
                    pdf_field.db_mapping = best_suggestion.db_path
                    pdf_field.confidence_score = best_suggestion.confidence
                    pdf_field.mapping_type = best_suggestion.field_type
                    pdf_field.ai_suggestions = [s.db_path for s in suggestions[:3]]
                else:
                    # Default to questionnaire for unmapped fields
                    pdf_field.is_questionnaire = True
                
                fields.append(pdf_field)
            
            doc.close()
            
            # Display intelligent extraction summary
            self._display_intelligent_summary(fields, form_type)
            
        except Exception as e:
            st.error(f"Error extracting PDF: {str(e)}")
            import traceback
            st.error(traceback.format_exc())
            return []
        
        return fields
    
    def _intelligent_part_detection_fixed(self, all_field_data: List[Dict], form_type: str, 
                                        form_structure: Dict[str, str], attorney_fields: List[int]) -> Dict[int, str]:
        """Fixed intelligent part detection with proper Part 0 handling"""
        part_mapping = {}
        
        # Phase 1: Map attorney fields to Part 0 if detected
        if st.session_state.has_attorney_section and attorney_fields:
            part_0_desc = form_structure.get("Part 0", "Part 0 - Attorney/Representative Information")
            for field_idx in attorney_fields:
                part_mapping[field_idx] = part_0_desc
        
        # Phase 2: Look for explicit part indicators in field names
        for field_data in all_field_data:
            if field_data['index'] in part_mapping:
                continue
            
            # Clean field name
            clean_name = self._clean_field_name(field_data['name'])
            
            # Look for explicit part indicators
            part_match = re.search(r'Part[\s_\-]*(\d+)', clean_name, re.IGNORECASE)
            if part_match:
                part_num = part_match.group(1)
                part_key = f"Part {part_num}"
                if part_key in form_structure:
                    part_mapping[field_data['index']] = f"{part_key} - {form_structure[part_key]}"
        
        # Phase 3: Context-based detection for remaining fields
        for field_data in all_field_data:
            if field_data['index'] in part_mapping:
                continue
            
            field_text = f"{field_data['name']} {field_data.get('display', '')}".lower()
            
            # Check for specific part indicators
            for part_key, part_desc in form_structure.items():
                part_desc_lower = part_desc.lower()
                
                # Check for beneficiary indicators
                if any(indicator in field_text for indicator in self.form_intelligence["part_detection_rules"]["beneficiary_indicators"]):
                    if "information about you" in part_desc_lower:
                        part_mapping[field_data['index']] = f"{part_key} - {part_desc}"
                        break
                
                # Check for petitioner indicators
                elif any(indicator in field_text for indicator in self.form_intelligence["part_detection_rules"]["petitioner_indicators"]):
                    if any(term in part_desc_lower for term in ["petitioner", "employer", "company"]):
                        part_mapping[field_data['index']] = f"{part_key} - {part_desc}"
                        break
        
        # Phase 4: Smart inference for unmapped fields
        sorted_fields = sorted(all_field_data, key=lambda x: (x['page'], x['index']))
        
        # Track current part based on page transitions
        current_part = None
        page_to_part = {}
        
        # Build page-to-part mapping from already mapped fields
        for field_data in sorted_fields:
            if field_data['index'] in part_mapping:
                page = field_data['page']
                part = part_mapping[field_data['index']]
                if page not in page_to_part:
                    page_to_part[page] = part
        
        # Map remaining fields based on page and proximity
        for field_data in sorted_fields:
            if field_data['index'] not in part_mapping:
                page = field_data['page']
                
                # If we have a part for this page, use it
                if page in page_to_part:
                    part_mapping[field_data['index']] = page_to_part[page]
                else:
                    # Look at nearby mapped fields
                    nearby_parts = []
                    window = 5
                    
                    for i, other_field in enumerate(sorted_fields):
                        if abs(i - sorted_fields.index(field_data)) <= window:
                            if other_field['index'] in part_mapping:
                                nearby_parts.append(part_mapping[other_field['index']])
                    
                    if nearby_parts:
                        # Use most common nearby part
                        most_common = max(set(nearby_parts), key=nearby_parts.count)
                        part_mapping[field_data['index']] = most_common
                    else:
                        # Default based on page and form structure
                        if page == 1 and st.session_state.has_attorney_section:
                            part_mapping[field_data['index']] = form_structure.get("Part 0", "Part 0 - Attorney/Representative Information")
                        else:
                            # Try to estimate part based on page number
                            estimated_part_num = page - (1 if st.session_state.has_attorney_section else 0)
                            estimated_part = f"Part {estimated_part_num}"
                            if estimated_part in form_structure:
                                part_mapping[field_data['index']] = f"{estimated_part} - {form_structure[estimated_part]}"
                            else:
                                # Find the closest valid part
                                for part_key in form_structure:
                                    if part_key.startswith("Part"):
                                        part_mapping[field_data['index']] = f"{part_key} - {form_structure[part_key]}"
                                        break
        
        return part_mapping
    
    def _generate_clean_name_enhanced(self, field_name: str, part: str, item: str, field_index: int) -> str:
        """Generate clean field name with proper G-28 style formatting"""
        # Extract part number
        part_match = re.search(r'Part\s*(\d+)', part, re.IGNORECASE)
        part_num = part_match.group(1) if part_match else "1"
        
        # Handle Part 0 specially
        if "part 0" in part.lower():
            part_num = "0"
            # For attorney fields, use special formatting
            if field_index in st.session_state.get('part0_fields', []):
                position = st.session_state.part0_fields.index(field_index)
                # Format as G28 P1_3a style
                return f"G28 P1_{position + 1}"
        
        # Use item if available
        if item:
            return f"P{part_num}_{item}"
        
        # Generate from field name
        clean = self._clean_field_name(field_name)
        
        # Extract number from end
        num_match = re.search(r'(\d+[a-zA-Z]?)$', clean)
        if num_match:
            return f"P{part_num}_{num_match.group(1)}"
        
        # Use position within part
        if not hasattr(self, '_part_counters'):
            self._part_counters = defaultdict(int)
        
        self._part_counters[part_num] += 1
        
        return f"P{part_num}_{self._part_counters[part_num]}"
    
    def _get_field_type(self, widget) -> str:
        """Determine field type from widget"""
        if widget.field_type == 2:  # Button/checkbox
            return "checkbox"
        elif widget.field_type == 3:  # Radio
            return "radio"
        elif widget.field_type == 4:  # Text
            return "text"
        elif widget.field_type == 5:  # Choice/dropdown
            return "select"
        elif widget.field_type == 7:  # Signature
            return "signature"
        else:
            return "text"
    
    def _get_part_context(self, part: str) -> str:
        """Get context for a part (attorney, beneficiary, petitioner, etc.)"""
        part_lower = part.lower()
        
        if "part 0" in part_lower or any(term in part_lower for term in ["attorney", "representative", "accredited"]):
            return "attorney"
        elif any(term in part_lower for term in ["information about you", "your information", "applicant"]):
            return "beneficiary"
        elif any(term in part_lower for term in ["petitioner", "employer", "company", "organization"]):
            return "petitioner"
        elif "beneficiary" in part_lower:
            return "beneficiary"
        else:
            return "general"
    
    def _get_intelligent_suggestions(self, field: PDFField, form_type: str) -> List[MappingSuggestion]:
        """AI-powered intelligent mapping suggestions"""
        suggestions = []
        
        # Get part context
        part_context = field.form_context.get("part_context", "general")
        
        # Clean field data for matching
        field_text = f"{field.raw_name} {field.description} {field.clean_name}".lower()
        
        # Phase 1: Context-based mapping
        if part_context == "attorney" or field.form_context.get("is_attorney_field", False):
            suggestions.extend(self._get_attorney_suggestions(field, field_text))
        elif part_context == "beneficiary":
            suggestions.extend(self._get_beneficiary_suggestions(field, field_text))
        elif part_context == "petitioner":
            suggestions.extend(self._get_petitioner_suggestions(field, field_text))
        
        # Phase 2: Pattern-based mapping
        suggestions.extend(self._get_pattern_based_suggestions(field, field_text))
        
        # Phase 3: AI-like fuzzy matching
        if len(suggestions) < 3:
            suggestions.extend(self._get_fuzzy_suggestions(field, field_text))
        
        # Remove duplicates and sort by confidence
        unique_suggestions = {}
        for sugg in suggestions:
            if sugg.db_path not in unique_suggestions or sugg.confidence > unique_suggestions[sugg.db_path].confidence:
                unique_suggestions[sugg.db_path] = sugg
        
        final_suggestions = sorted(unique_suggestions.values(), key=lambda x: x.confidence, reverse=True)
        
        return final_suggestions[:5]  # Return top 5 suggestions
    
    def _get_attorney_suggestions(self, field: PDFField, field_text: str) -> List[MappingSuggestion]:
        """Get attorney-specific suggestions"""
        suggestions = []
        
        # Attorney name fields
        if any(term in field_text for term in ["last", "family", "apellido"]):
            suggestions.append(MappingSuggestion("attorney.attorneyInfo.lastName", 0.95, "Attorney last name", context_based=True))
        elif any(term in field_text for term in ["first", "given", "nombre"]):
            suggestions.append(MappingSuggestion("attorney.attorneyInfo.firstName", 0.95, "Attorney first name", context_based=True))
        elif any(term in field_text for term in ["middle", "initial"]):
            suggestions.append(MappingSuggestion("attorney.attorneyInfo.middleName", 0.9, "Attorney middle name", context_based=True))
        
        # Attorney credentials
        elif any(term in field_text for term in ["bar", "state bar"]) and any(term in field_text for term in ["number", "no", "#"]):
            suggestions.append(MappingSuggestion("attorney.attorneyInfo.stateBarNumber", 0.98, "State bar number", context_based=True))
        elif "licensing" in field_text and "authority" in field_text:
            suggestions.append(MappingSuggestion("attorney.attorneyInfo.licensingAuthority", 0.95, "Licensing authority", context_based=True))
        elif "uscis" in field_text and "account" in field_text:
            suggestions.append(MappingSuggestion("attorney.attorneyInfo.uscisOnlineAccountNumber", 0.9, "USCIS account", context_based=True))
        
        # Law firm
        elif any(term in field_text for term in ["firm", "organization"]) and "name" in field_text:
            suggestions.append(MappingSuggestion("attorneyLawfirmDetails.lawfirmDetails.lawFirmName", 0.9, "Law firm name", context_based=True))
        elif any(term in field_text for term in ["fein", "ein", "tax"]):
            suggestions.append(MappingSuggestion("attorneyLawfirmDetails.lawfirmDetails.lawFirmFein", 0.9, "Law firm FEIN", context_based=True))
        
        # Contact info
        elif "phone" in field_text:
            if "mobile" in field_text or "cell" in field_text:
                suggestions.append(MappingSuggestion("attorney.attorneyInfo.mobilePhone", 0.85, "Attorney mobile", context_based=True))
            else:
                suggestions.append(MappingSuggestion("attorney.attorneyInfo.workPhone", 0.85, "Attorney phone", context_based=True))
        elif "email" in field_text:
            suggestions.append(MappingSuggestion("attorney.attorneyInfo.emailAddress", 0.9, "Attorney email", context_based=True))
        elif "fax" in field_text:
            suggestions.append(MappingSuggestion("attorney.attorneyInfo.faxNumber", 0.85, "Attorney fax", context_based=True))
        
        # Address
        elif "street" in field_text or ("address" in field_text and "email" not in field_text):
            suggestions.append(MappingSuggestion("attorney.address.addressStreet", 0.85, "Attorney street", context_based=True))
        elif "city" in field_text:
            suggestions.append(MappingSuggestion("attorney.address.addressCity", 0.85, "Attorney city", context_based=True))
        elif "state" in field_text and "bar" not in field_text:
            suggestions.append(MappingSuggestion("attorney.address.addressState", 0.85, "Attorney state", context_based=True))
        elif "zip" in field_text or "postal" in field_text:
            suggestions.append(MappingSuggestion("attorney.address.addressZip", 0.85, "Attorney ZIP", context_based=True))
        
        return suggestions
    
    def _get_beneficiary_suggestions(self, field: PDFField, field_text: str) -> List[MappingSuggestion]:
        """Get beneficiary-specific suggestions"""
        suggestions = []
        
        # Names
        if any(term in field_text for term in ["last", "family", "apellido"]):
            suggestions.append(MappingSuggestion("beneficiary.Beneficiary.beneficiaryLastName", 0.95, "Your last name", context_based=True))
        elif any(term in field_text for term in ["first", "given", "nombre"]):
            suggestions.append(MappingSuggestion("beneficiary.Beneficiary.beneficiaryFirstName", 0.95, "Your first name", context_based=True))
        elif any(term in field_text for term in ["middle", "initial"]):
            suggestions.append(MappingSuggestion("beneficiary.Beneficiary.beneficiaryMiddleName", 0.9, "Your middle name", context_based=True))
        
        # Identifiers
        elif any(term in field_text for term in ["alien", "a-number", "uscis"]) and any(term in field_text for term in ["number", "no"]):
            suggestions.append(MappingSuggestion("beneficiary.Beneficiary.alienNumber", 0.95, "Alien number", context_based=True))
        elif "ssn" in field_text or ("social" in field_text and "security" in field_text):
            suggestions.append(MappingSuggestion("beneficiary.Beneficiary.beneficiarySsn", 0.95, "SSN", context_based=True))
        elif "uscis" in field_text and "account" in field_text and "online" in field_text:
            suggestions.append(MappingSuggestion("beneficiary.Beneficiary.beneficiaryUscisAccountNumber", 0.9, "USCIS account", context_based=True))
        
        # Personal info
        elif any(term in field_text for term in ["birth", "dob"]) and "date" in field_text:
            suggestions.append(MappingSuggestion("beneficiary.Beneficiary.beneficiaryDateOfBirth", 0.95, "Date of birth", context_based=True))
        elif "gender" in field_text or "sex" in field_text:
            suggestions.append(MappingSuggestion("beneficiary.Beneficiary.beneficiaryGender", 0.9, "Gender", context_based=True))
        elif "marital" in field_text:
            suggestions.append(MappingSuggestion("beneficiary.Beneficiary.maritalStatus", 0.9, "Marital status", context_based=True))
        
        # Country/Location
        elif "country" in field_text and "birth" in field_text:
            suggestions.append(MappingSuggestion("beneficiary.Beneficiary.beneficiaryCountryOfBirth", 0.9, "Country of birth", context_based=True))
        elif "country" in field_text and ("citizen" in field_text or "nationality" in field_text):
            suggestions.append(MappingSuggestion("beneficiary.Beneficiary.beneficiaryCitizenOfCountry", 0.9, "Citizenship", context_based=True))
        
        # Contact
        elif "phone" in field_text:
            if "mobile" in field_text or "cell" in field_text:
                suggestions.append(MappingSuggestion("beneficiary.Beneficiary.beneficiaryCellNumber", 0.85, "Mobile phone", context_based=True))
            elif "home" in field_text:
                suggestions.append(MappingSuggestion("beneficiary.Beneficiary.beneficiaryHomeNumber", 0.85, "Home phone", context_based=True))
            elif "work" in field_text or "daytime" in field_text:
                suggestions.append(MappingSuggestion("beneficiary.Beneficiary.beneficiaryWorkNumber", 0.85, "Work phone", context_based=True))
        elif "email" in field_text:
            suggestions.append(MappingSuggestion("beneficiary.Beneficiary.beneficiaryPrimaryEmailAddress", 0.9, "Email", context_based=True))
        
        # Documents
        elif "passport" in field_text and any(term in field_text for term in ["number", "no"]):
            suggestions.append(MappingSuggestion("beneficiary.PassportDetails.Passport.passportNumber", 0.9, "Passport number", context_based=True))
        elif ("i-94" in field_text or "i94" in field_text) and any(term in field_text for term in ["number", "no"]):
            suggestions.append(MappingSuggestion("beneficiary.I94Details.I94.i94Number", 0.9, "I-94 number", context_based=True))
        
        # Addresses - determine type
        elif "street" in field_text or ("address" in field_text and "email" not in field_text):
            if "mailing" in field_text:
                suggestions.append(MappingSuggestion("beneficiary.MailingAddress.addressStreet", 0.85, "Mailing street", context_based=True))
            elif "physical" in field_text:
                suggestions.append(MappingSuggestion("beneficiary.PhysicalAddress.addressStreet", 0.85, "Physical street", context_based=True))
            elif "foreign" in field_text or "abroad" in field_text:
                suggestions.append(MappingSuggestion("beneficiary.ForeignAddress.addressStreet", 0.85, "Foreign street", context_based=True))
            elif "work" in field_text:
                suggestions.append(MappingSuggestion("beneficiary.WorkAddress.addressStreet", 0.85, "Work street", context_based=True))
            else:
                suggestions.append(MappingSuggestion("beneficiary.HomeAddress.addressStreet", 0.85, "Home street", context_based=True))
        
        return suggestions
    
    def _get_petitioner_suggestions(self, field: PDFField, field_text: str) -> List[MappingSuggestion]:
        """Get petitioner/company suggestions"""
        suggestions = []
        
        # Company info
        if any(term in field_text for term in ["company", "organization", "business", "employer"]) and "name" in field_text:
            suggestions.append(MappingSuggestion("customer.customer_name", 0.9, "Company name", context_based=True))
        elif any(term in field_text for term in ["fein", "ein", "tax id"]):
            suggestions.append(MappingSuggestion("customer.customer_tax_id", 0.9, "Tax ID", context_based=True))
        elif "naics" in field_text:
            suggestions.append(MappingSuggestion("customer.customer_naics_code", 0.9, "NAICS code", context_based=True))
        
        # Signatory
        elif any(term in field_text for term in ["last", "family"]) and "signatory" not in field.part.lower():
            suggestions.append(MappingSuggestion("customer.signatory.signatory_last_name", 0.85, "Signatory last name", context_based=True))
        elif any(term in field_text for term in ["first", "given"]) and "signatory" not in field.part.lower():
            suggestions.append(MappingSuggestion("customer.signatory.signatory_first_name", 0.85, "Signatory first name", context_based=True))
        
        return suggestions
    
    def _get_pattern_based_suggestions(self, field: PDFField, field_text: str) -> List[MappingSuggestion]:
        """Get pattern-based suggestions using intelligent patterns"""
        suggestions = []
        
        # Go through each pattern category
        for category, patterns in self.form_intelligence["field_mapping_patterns"].items():
            for pattern_type, pattern_list in patterns.items():
                for pattern in pattern_list:
                    if pattern in field_text:
                        # Generate appropriate suggestion based on context
                        if category == "names":
                            context = field.form_context.get("part_context", "general")
                            if context == "attorney":
                                base_path = "attorney.attorneyInfo"
                            elif context == "beneficiary":
                                base_path = "beneficiary.Beneficiary"
                            elif context == "petitioner":
                                base_path = "customer.signatory"
                            else:
                                base_path = "beneficiary.Beneficiary"  # Default
                            
                            if pattern_type == "last":
                                suggestions.append(MappingSuggestion(f"{base_path}.{'lastName' if 'attorney' in base_path else 'beneficiaryLastName' if 'beneficiary' in base_path else 'signatory_last_name'}", 
                                                                   0.85, f"Pattern match: {pattern}"))
                            elif pattern_type == "first":
                                suggestions.append(MappingSuggestion(f"{base_path}.{'firstName' if 'attorney' in base_path else 'beneficiaryFirstName' if 'beneficiary' in base_path else 'signatory_first_name'}", 
                                                                   0.85, f"Pattern match: {pattern}"))
        
        return suggestions
    
    def _get_fuzzy_suggestions(self, field: PDFField, field_text: str) -> List[MappingSuggestion]:
        """Get fuzzy matching suggestions using AI-like matching"""
        suggestions = []
        
        # Get relevant database paths based on context
        context = field.form_context.get("part_context", "general")
        if context == "attorney":
            relevant_paths = self.categorized_paths["attorney"] + self.categorized_paths["attorneyLawfirmDetails"]
        elif context == "beneficiary":
            relevant_paths = self.categorized_paths["beneficiary"]
        elif context == "petitioner":
            relevant_paths = self.categorized_paths["customer"]
        else:
            relevant_paths = self.db_paths_cache
        
        # Calculate similarity scores
        field_words = set(re.findall(r'\w+', field_text.lower()))
        
        for path in relevant_paths[:50]:  # Limit to top 50 for performance
            path_words = set(re.findall(r'\w+', path.lower()))
            
            # Calculate Jaccard similarity
            intersection = field_words.intersection(path_words)
            union = field_words.union(path_words)
            
            if union:
                similarity = len(intersection) / len(union)
                
                if similarity > 0.3:  # Threshold for fuzzy match
                    suggestions.append(MappingSuggestion(path, similarity * 0.7, f"Fuzzy match: {similarity:.0%}"))
        
        return suggestions
    
    def _clean_field_name(self, field_name: str) -> str:
        """Clean field name for analysis"""
        patterns_to_remove = [
            r'form\d*\[\d+\]\.',
            r'#subform\[\d+\]\.',
            r'topmostSubform\[\d+\]\.',
            r'\[\d+\]',
            r'^#',
            r'\.pdf$'
        ]
        
        clean_name = field_name
        for pattern in patterns_to_remove:
            clean_name = re.sub(pattern, '', clean_name, flags=re.IGNORECASE)
        
        return clean_name
    
    def _extract_item_intelligent(self, field_name: str, field_display: str = "") -> str:
        """Intelligently extract item number"""
        clean_name = self._clean_field_name(field_name)
        
        # Patterns for item extraction
        patterns = [
            r'Item\s*(\d+[a-zA-Z]?)',
            r'Line\s*(\d+[a-zA-Z]?)',
            r'Question\s*(\d+[a-zA-Z]?)',
            r'_(\d+[a-zA-Z]?)$',
            r'\.(\d+[a-zA-Z]?)$',
            r'\b(\d{1,2}[a-zA-Z]?)\b'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, clean_name, re.IGNORECASE)
            if match:
                item = match.group(1)
                if re.match(r'^\d{1,2}[a-zA-Z]?$', item):
                    return item.rstrip('.')
        
        return ""
    
    def _generate_intelligent_description(self, field_name: str, field_display: str, part: str) -> str:
        """Generate intelligent human-readable descriptions"""
        # Use display name if meaningful
        if field_display and not field_display.startswith('form'):
            desc = field_display
        else:
            desc = self._clean_field_name(field_name)
        
        # Extract meaningful part
        parts = desc.split('.')
        meaningful_part = ""
        
        for part_str in reversed(parts):
            if part_str and not part_str.isdigit() and len(part_str) > 2:
                if part_str.lower() not in ['form', 'field', 'text', 'checkbox']:
                    meaningful_part = part_str
                    break
        
        if meaningful_part:
            desc = meaningful_part
        
        # Convert camelCase
        desc = re.sub(r'([a-z])([A-Z])', r'\1 \2', desc)
        
        # Expand abbreviations
        abbreviations = {
            'FamilyName': 'Family Name (Last Name)',
            'GivenName': 'Given Name (First Name)',
            'MiddleName': 'Middle Name',
            'DOB': 'Date of Birth',
            'SSN': 'Social Security Number',
            'EIN': 'Employer Identification Number',
            'USCIS': 'USCIS',
            'Apt': 'Apartment',
            'Ste': 'Suite'
        }
        
        for abbr, full in abbreviations.items():
            desc = re.sub(rf'\b{abbr}\b', full, desc, flags=re.IGNORECASE)
        
        # Add context based on part
        context = self._get_part_context(part)
        if context == "attorney" and "name" in desc.lower() and "firm" not in desc.lower():
            desc = f"Attorney {desc}"
        elif context == "beneficiary" and "name" in desc.lower():
            desc = f"Your {desc}"
        
        return desc.strip()
    
    def _get_intelligent_field_suffix(self, field_name: str, field_type: str, description: str) -> str:
        """Get intelligent TypeScript field suffix"""
        combined_text = f"{field_name} {description}".lower()
        
        # Special field types
        if "full name" in combined_text and "name" in combined_text:
            return ":FullName"
        elif "address type" in combined_text:
            return ":AddressTypeBox"
        elif any(term in combined_text for term in ["ssn", "alien number", "a-number"]):
            return ":SingleBox"
        elif field_type == "date" or "date" in combined_text:
            return ":Date"
        elif field_type == "signature" or "signature" in combined_text:
            return ":SignatureBox"
        elif field_type == "checkbox":
            return ":CheckBox"
        elif field_type == "radio":
            return ":ConditionBox"
        elif "number" in combined_text and "phone" not in combined_text:
            return ":NumberBox"
        else:
            return FIELD_TYPE_SUFFIX_MAP.get(field_type, ":TextBox")
    
    def _display_intelligent_summary(self, fields: List[PDFField], form_type: str):
        """Display enhanced extraction summary with intelligence insights"""
        st.markdown("### 🧠 Intelligent Extraction Summary")
        
        # Key insights
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📄 Form Type", form_type)
            if st.session_state.has_attorney_section:
                st.caption("✅ G-28 Attached")
        
        with col2:
            st.metric("🔢 Total Fields", len(fields))
            high_conf = sum(1 for f in fields if f.confidence_score > 0.8)
            st.caption(f"🎯 {high_conf} high confidence")
        
        with col3:
            parts = list(set(f.part for f in fields))
            st.metric("📑 Parts Detected", len(parts))
            st.caption(f"📄 Across {max(f.page for f in fields)} pages")
        
        with col4:
            auto_mapped = sum(1 for f in fields if f.db_mapping)
            st.metric("🤖 Auto-Mapped", f"{auto_mapped} ({auto_mapped/len(fields)*100:.0f}%)")
            st.caption("AI suggestions ready")
        
        # Part breakdown with context
        st.markdown("### 📊 Intelligent Part Analysis")
        
        # Group by part
        fields_by_part = defaultdict(list)
        for field in fields:
            fields_by_part[field.part].append(field)
        
        # Sort parts
        def natural_sort_key(part):
            match = re.search(r'Part\s*(\d+)', part)
            if match:
                return (0, int(match.group(1)))
            return (1, part)
        
        sorted_parts = sorted(fields_by_part.keys(), key=natural_sort_key)
        
        # Create visual part analysis
        for part in sorted_parts:
            part_fields = fields_by_part[part]
            context = self._get_part_context(part)
            
            # Determine icon and color
            if context == "attorney":
                icon = "⚖️"
                color = "blue"
            elif context == "beneficiary":
                icon = "👤"
                color = "green"
            elif context == "petitioner":
                icon = "🏢"
                color = "orange"
            else:
                icon = "📄"
                color = "gray"
            
            # Part summary
            with st.expander(f"{icon} **{part}** ({len(part_fields)} fields)", expanded="Part 0" in part or "Part 1" in part):
                # Context explanation
                if context == "attorney":
                    st.info("🔍 **Attorney Section**: These fields are for the legal representative (G-28 attachment)")
                elif context == "beneficiary":
                    st.info("🔍 **Beneficiary Section**: These fields are about the applicant/beneficiary")
                elif context == "petitioner":
                    st.info("🔍 **Petitioner Section**: These fields are about the sponsoring company/employer")
                
                # Field type breakdown
                type_counts = defaultdict(int)
                for field in part_fields:
                    type_counts[field.field_type] += 1
                
                # Quick stats
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Fields", len(part_fields))
                with col2:
                    mapped = sum(1 for f in part_fields if f.db_mapping)
                    st.metric("Suggested", mapped)
                with col3:
                    avg_conf = sum(f.confidence_score for f in part_fields if f.confidence_score > 0) / len([f for f in part_fields if f.confidence_score > 0]) if any(f.confidence_score > 0 for f in part_fields) else 0
                    st.metric("Avg Confidence", f"{avg_conf:.0%}")
                
                # Sample fields with AI insights
                st.markdown("**🔍 AI-Detected Fields:**")
                
                sample_data = []
                for field in part_fields[:8]:
                    sample_data.append({
                        "Field": field.description,
                        "Type": field.field_type,
                        "AI Suggestion": field.db_mapping if field.db_mapping else "To Questionnaire",
                        "Confidence": f"{field.confidence_score:.0%}" if field.confidence_score > 0 else "-",
                        "Context": "✓" if field.confidence_score > 0 and any(s for s in field.ai_suggestions) else ""
                    })
                
                if sample_data:
                    df = pd.DataFrame(sample_data)
                    st.dataframe(df, use_container_width=True, hide_index=True)
                
                if len(part_fields) > 8:
                    st.caption(f"... and {len(part_fields) - 8} more fields")
        
        # AI Insights - Special attention to Part 0
        with st.expander(" AI Intelligence Report", expanded=False):
            st.markdown("### Form Understanding")
            
            # Form structure understanding
            st.write("**✅ Detected Form Structure:**")
            if st.session_state.has_attorney_section:
                st.write("- ⚖️ Attorney representation detected (G-28 attached)")
                st.write(f"- 📝 Part 0 identified with {len(st.session_state.get('part0_fields', []))} attorney fields")
            
            # Beneficiary detection
            beneficiary_parts = [p for p in sorted_parts if "information about you" in p.lower()]
            if beneficiary_parts:
                st.write(f"- 👤 Beneficiary information detected in: {', '.join(beneficiary_parts)}")
            
            # Mapping confidence
            st.write("\n**📊 Mapping Confidence Analysis:**")
            
            confidence_ranges = {
                "High (>80%)": sum(1 for f in fields if f.confidence_score > 0.8),
                "Medium (60-80%)": sum(1 for f in fields if 0.6 <= f.confidence_score <= 0.8),
                "Low (<60%)": sum(1 for f in fields if 0 < f.confidence_score < 0.6),
                "No suggestion": sum(1 for f in fields if f.confidence_score == 0)
            }
            
            conf_df = pd.DataFrame(confidence_ranges.items(), columns=["Confidence Level", "Field Count"])
            st.dataframe(conf_df, use_container_width=True, hide_index=True)
            
            # Pattern detection
            st.write("\n**🔍 Detected Patterns:**")
            pattern_counts = defaultdict(int)
            for field in fields:
                if field.db_mapping:
                    obj = field.db_mapping.split('.')[0]
                    pattern_counts[obj] += 1
            
            if pattern_counts:
                st.write("Primary data objects detected:")
                for obj, count in sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True):
                    st.write(f"- {obj}: {count} fields")
            
            # Recommendations
            st.write("\n**💡 AI Recommendations:**")
            if st.session_state.has_attorney_section:
                st.write("- ✅ Review Part 0 mappings for attorney information")
            st.write("- 🎯 Accept high-confidence suggestions (>80%) for faster mapping")
            st.write("- 📋 Unmapped fields will automatically go to questionnaire")
            st.write("- 🔄 You can always adjust mappings manually")
    
    def calculate_mapping_score(self, fields: List[PDFField]) -> float:
        """Calculate overall mapping quality score"""
        if not fields:
            return 0.0
        
        mapped = sum(1 for f in fields if f.is_mapped)
        high_conf = sum(1 for f in fields if f.confidence_score > 0.8)
        suggested = sum(1 for f in fields if f.db_mapping)
        
        score = (
            (mapped / len(fields)) * 40 +  # 40% weight for mapped fields
            (high_conf / len(fields)) * 30 +  # 30% weight for high confidence
            (suggested / len(fields)) * 30  # 30% weight for AI suggestions
        )
        
        return min(score * 100, 100)
    
    def generate_typescript_export(self, form_type: str, fields: List[PDFField]) -> str:
        """Generate TypeScript export file in the required format"""
        # Clean form name
        form_name = form_type.replace('-', '')
        
        # Group fields by object type
        customer_fields = []
        beneficiary_fields = []
        attorney_fields = []
        questionnaire_fields = []
        
        for field in fields:
            if field.is_questionnaire or not field.db_mapping:
                questionnaire_fields.append(field)
            elif field.db_mapping:
                if field.db_mapping.startswith("customer"):
                    customer_fields.append(field)
                elif field.db_mapping.startswith("beneficiary"):
                    beneficiary_fields.append(field)
                elif field.db_mapping.startswith("attorney"):
                    attorney_fields.append(field)
                else:
                    questionnaire_fields.append(field)
        
        # Generate TypeScript content in the specific format
        ts_content = f"export const {form_name} = {{\n"
        
        # Add customer data if present
        if customer_fields:
            ts_content += "  customerData: {\n"
            for field in customer_fields:
                db_path = field.db_mapping.replace("customer.", "")
                ts_content += f'    "{field.clean_name}{field.field_type_suffix}": "{db_path}",\n'
            ts_content = ts_content.rstrip(',\n') + '\n'
            ts_content += "  },\n"
        
        # Add beneficiary data if present
        if beneficiary_fields:
            ts_content += "  beneficiaryData: {\n"
            for field in beneficiary_fields:
                db_path = field.db_mapping.replace("beneficiary.", "")
                ts_content += f'    "{field.clean_name}{field.field_type_suffix}": "{db_path}",\n'
            ts_content = ts_content.rstrip(',\n') + '\n'
            ts_content += "  },\n"
        
        # Add attorney data if present  
        if attorney_fields:
            ts_content += "  attorneyData: {\n"
            for field in attorney_fields:
                db_path = field.db_mapping.replace("attorney.", "").replace("attorneyLawfirmDetails.", "")
                ts_content += f'    "{field.clean_name}{field.field_type_suffix}": "{db_path}",\n'
            ts_content = ts_content.rstrip(',\n') + '\n'
            ts_content += "  },\n"
        
        # Add questionnaire data
        if questionnaire_fields:
            ts_content += "  questionnaireData: {\n"
            for field in questionnaire_fields:
                ts_content += f'    "{field.clean_name}": {{\n'
                ts_content += f'      description: "{field.description}",\n'
                ts_content += f'      fieldType: "{field.field_type}",\n'
                ts_content += f'      part: "{field.part}",\n'
                if field.item:
                    ts_content += f'      item: "{field.item}",\n'
                ts_content += f'      required: true\n'
                ts_content += "    },\n"
            ts_content = ts_content.rstrip(',\n') + '\n'
            ts_content += "  }\n"
        
        # Remove trailing comma if no questionnaire data
        ts_content = ts_content.rstrip(',\n') + '\n'
        ts_content += "};\n"
        
        return ts_content
    
    def generate_questionnaire_json(self, fields: List[PDFField]) -> str:
        """Generate questionnaire JSON for manual entry fields"""
        questionnaire_fields = [f for f in fields if f.is_questionnaire or not f.db_mapping]
        
        # Group by part
        fields_by_part = defaultdict(list)
        for field in questionnaire_fields:
            fields_by_part[field.part].append(field)
        
        # Build JSON structure
        questionnaire = {
            "formType": st.session_state.form_type,
            "generatedAt": datetime.now().isoformat(),
            "totalQuestions": len(questionnaire_fields),
            "sections": []
        }
        
        # Sort parts naturally
        def natural_sort_key(part):
            match = re.search(r'Part\s*(\d+)', part)
            if match:
                return (0, int(match.group(1)))
            return (1, part)
        
        sorted_parts = sorted(fields_by_part.keys(), key=natural_sort_key)
        
        for part in sorted_parts:
            section = {
                "name": part,
                "questions": []
            }
            
            for field in fields_by_part[part]:
                question = {
                    "id": field.clean_name,
                    "description": field.description,
                    "type": field.field_type,
                    "required": True,
                    "page": field.page
                }
                
                if field.item:
                    question["item"] = field.item
                
                section["questions"].append(question)
            
            questionnaire["sections"].append(section)
        
        return json.dumps(questionnaire, indent=2)
    
    def get_all_database_paths(self) -> List[str]:
        """Get all available database paths"""
        return self.db_paths_cache

def render_enhanced_header():
    """Render enhanced header with modern design"""
    st.markdown("""
    <style>
        .main-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 15px;
            margin-bottom: 30px;
            text-align: center;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            position: relative;
            overflow: hidden;
        }
        .main-header::before {
            content: '';
            position: absolute;
            top: -50%;
            right: -50%;
            bottom: -50%;
            left: -50%;
            background: linear-gradient(45deg, transparent 30%, rgba(255,255,255,0.1) 50%, transparent 70%);
            animation: shimmer 3s infinite;
        }
        @keyframes shimmer {
            0% { transform: translateX(-100%) translateY(-100%) rotate(45deg); }
            100% { transform: translateX(100%) translateY(100%) rotate(45deg); }
        }
        .header-title {
            font-size: 2.5em;
            font-weight: bold;
            margin: 0;
            position: relative;
            z-index: 1;
        }
        .header-subtitle {
            font-size: 1.2em;
            opacity: 0.9;
            margin-top: 10px;
            position: relative;
            z-index: 1;
        }
        .feature-badge {
            display: inline-block;
            background: rgba(255,255,255,0.2);
            padding: 5px 15px;
            border-radius: 20px;
            margin: 5px;
            font-size: 0.9em;
        }
        .metric-card-enhanced {
            background: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.08);
            text-align: center;
            transition: all 0.3s ease;
            border: 1px solid transparent;
            position: relative;
            overflow: hidden;
        }
        .metric-card-enhanced:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 25px rgba(0,0,0,0.15);
            border-color: #667eea;
        }
        .metric-card-enhanced::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, #667eea, #764ba2);
        }
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
            animation: pulse 2s infinite;
        }
        .status-active { background: #10b981; }
        .status-pending { background: #f59e0b; }
        @keyframes pulse {
            0% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.8; transform: scale(1.1); }
            100% { opacity: 1; transform: scale(1); }
        }
        .ai-badge {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 500;
            display: inline-block;
            margin-left: 10px;
        }
        .field-card-enhanced {
            background: white;
            border: 1px solid #e5e7eb;
            padding: 20px;
            margin: 15px 0;
            border-radius: 12px;
            transition: all 0.3s ease;
            position: relative;
        }
        .field-card-enhanced:hover {
            box-shadow: 0 10px 25px rgba(0,0,0,0.1);
            border-color: #667eea;
            transform: translateY(-2px);
        }
        .confidence-bar {
            height: 4px;
            background: #e5e7eb;
            border-radius: 2px;
            overflow: hidden;
            margin-top: 8px;
        }
        .confidence-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea, #764ba2);
            transition: width 0.3s ease;
        }
        .part-section {
            background: linear-gradient(135deg, #f3f4f6, #ffffff);
            padding: 20px;
            border-radius: 12px;
            margin: 20px 0;
            border: 1px solid #e5e7eb;
        }
        .ai-insight {
            background: linear-gradient(135deg, #f0f9ff, #e0f2fe);
            border-left: 4px solid #3b82f6;
            padding: 15px;
            border-radius: 8px;
            margin: 10px 0;
        }
        .form-detection-card {
            background: white;
            border: 2px solid #e5e7eb;
            border-radius: 12px;
            padding: 20px;
            margin: 20px 0;
            position: relative;
        }
        .form-detection-card.detected {
            border-color: #10b981;
            background: #f0fdf4;
        }
        .detection-confidence {
            position: absolute;
            top: 10px;
            right: 10px;
            background: #667eea;
            color: white;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85em;
        }
        .attorney-highlight {
            background: #e0f2fe;
            border: 2px solid #3b82f6;
            padding: 15px;
            border-radius: 8px;
            margin: 10px 0;
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="main-header">
        <h1 class="header-title">🧠 Intelligent USCIS Form Mapper</h1>
        <p class="header-subtitle">AI-Powered Form Detection & Database Mapping</p>
        <div style="margin-top: 20px;">
            <span class="feature-badge">🔍 Auto-Detection</span>
            <span class="feature-badge">🎯 Smart Mapping</span>
            <span class="feature-badge">📊 Part Analysis</span>
            <span class="feature-badge">🤖 AI Suggestions</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_enhanced_upload_section(mapper: EnhancedUSCISMapper):
    """Render enhanced upload section with auto-detection"""
    st.markdown("## 📤 Smart Form Upload & Auto-Detection")
    
    # Instructions
    st.markdown("""
    <div class="ai-insight">
        <strong>🤖 How it works:</strong> Simply upload any USCIS form PDF and our AI will automatically detect the form type. 
        No need to select the form manually - we support all major USCIS forms from <a href="https://www.uscis.gov/forms/all-forms" target="_blank">uscis.gov</a>.
    </div>
    """, unsafe_allow_html=True)
    
    # File upload section
    col1, col2 = st.columns([2, 1])
    
    with col1:
        uploaded_file = st.file_uploader(
            "Drop your USCIS PDF form here or browse",
            type=['pdf'],
            help="Upload any fillable USCIS form - we'll automatically detect which form it is",
            key="pdf_uploader"
        )
        
        if uploaded_file:
            # File info
            st.markdown("### 📎 Uploaded File")
            file_info = {
                "📄 Filename": uploaded_file.name,
                "📦 Size": f"{uploaded_file.size / 1024:.1f} KB",
                "🏷️ Type": uploaded_file.type
            }
            
            col_info1, col_info2, col_info3 = st.columns(3)
            with col_info1:
                st.metric("Filename", uploaded_file.name)
            with col_info2:
                st.metric("Size", f"{uploaded_file.size / 1024:.1f} KB")
            with col_info3:
                st.metric("Type", "PDF")
    
    with col2:
        if uploaded_file:
            # G-28 attachment check
            st.markdown("### ⚖️ Attorney Representation")
            has_g28 = st.checkbox(
                "Is Form G-28 or G-28I attached?",
                help="Check this if you have attorney representation",
                value=False
            )
            
            if has_g28:
                st.success("✅ Part 0 will be detected for attorney")
                st.session_state.has_attorney_section = True
        else:
            # Show supported forms
            with st.expander("📋 View Supported Forms"):
                forms_list = list(USCIS_FORMS_DATABASE.keys())
                # Display in columns
                cols = st.columns(3)
                for i, form in enumerate(forms_list):
                    with cols[i % 3]:
                        st.write(f"• {form}")
    
    # Auto-detect and extract button
    if uploaded_file:
        st.markdown("---")
        
        if st.button(
            "🚀 Auto-Detect Form & Extract Fields",
            type="primary",
            use_container_width=True,
            help="AI will automatically detect the form type and extract all fields"
        ):
            with st.spinner("🔍 Detecting form type..."):
                # Progress display
                progress_text = st.empty()
                progress_bar = st.progress(0)
                
                # Step 1: Detect form type
                progress_text.text("📄 Reading PDF content...")
                progress_bar.progress(0.2)
                
                form_type, confidence = mapper.detect_form_type(uploaded_file)
                
                progress_text.text("🧠 Analyzing form structure...")
                progress_bar.progress(0.4)
                
                if form_type and confidence >= 0.5:
                    st.session_state.detected_form_type = form_type
                    st.session_state.detection_confidence = confidence
                    st.session_state.form_type = form_type
                    
                    # Show detection result
                    progress_text.empty()
                    progress_bar.empty()
                    
                    # Detection result card
                    st.markdown(f"""
                    <div class="form-detection-card detected">
                        <div class="detection-confidence">{confidence:.0%} Confidence</div>
                        <h3>✅ Form Detected: {form_type}</h3>
                        <p>{USCIS_FORMS_DATABASE[form_type]['title']}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Extract fields
                    with st.spinner(f"🧠 Extracting fields from {form_type}..."):
                        progress_text = st.empty()
                        progress_bar = st.progress(0)
                        
                        steps = [
                            "📄 Reading form structure...",
                            "🔍 Detecting form parts...",
                            "⚖️ Checking for attorney section...",
                            "🎯 Analyzing field patterns...",
                            "🤖 Generating AI mappings...",
                            "✅ Analysis complete!"
                        ]
                        
                        for i, step in enumerate(steps[:-1]):
                            progress_text.text(step)
                            progress_bar.progress((i + 1) / len(steps))
                            import time
                            time.sleep(0.3)
                        
                        # Extract fields
                        fields = mapper.extract_pdf_fields(uploaded_file, form_type)
                        
                        if fields:
                            st.session_state.pdf_fields = fields
                            st.session_state.field_mappings = {f.raw_name: f for f in fields}
                            progress_text.text(steps[-1])
                            progress_bar.progress(1.0)
                            
                            # Show success
                            st.balloons()
                            st.success(f" Successfully analyzed {len(fields)} fields from {form_type}!")
                            
                            # Show special note if attorney section found
                            if st.session_state.has_attorney_section:
                                st.markdown("""
                                <div class="attorney-highlight">
                                    <strong>⚖️ Attorney Section Detected!</strong> Part 0 has been identified for attorney/representative information.
                                    The AI found the text "to be completed by attorney or accredited representative" and mapped the corresponding fields.
                                </div>
                                """, unsafe_allow_html=True)
                        else:
                            st.error("❌ No fields found. Please ensure it's a fillable PDF form.")
                
                else:
                    # Could not detect form
                    progress_text.empty()
                    progress_bar.empty()
                    
                    st.markdown("""
                    <div class="form-detection-card">
                        <h3>❓ Unable to Auto-Detect Form Type</h3>
                        <p>The AI couldn't confidently identify this form. This might happen if:</p>
                        <ul>
                            <li>The PDF is scanned or not fillable</li>
                            <li>It's not a standard USCIS form</li>
                            <li>The form is damaged or incomplete</li>
                        </ul>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Manual selection fallback
                    st.markdown("### 📋 Manual Form Selection")
                    
                    form_type = st.selectbox(
                        "Please select the form type manually:",
                        [""] + list(USCIS_FORMS_DATABASE.keys()),
                        help="Select the USCIS form type"
                    )
                    
                    if form_type:
                        if st.button("Extract with Manual Selection", type="secondary"):
                            st.session_state.form_type = form_type
                            fields = mapper.extract_pdf_fields(uploaded_file, form_type)
                            
                            if fields:
                                st.session_state.pdf_fields = fields
                                st.session_state.field_mappings = {f.raw_name: f for f in fields}
                                st.success(f"✅ Extracted {len(fields)} fields!")
                                st.rerun()

def render_intelligent_mapping_section(mapper: EnhancedUSCISMapper):
    """Render intelligent mapping section with AI features"""
    if 'pdf_fields' not in st.session_state or not st.session_state.pdf_fields:
        st.info("👆 Please upload a PDF form first")
        return
    
    st.markdown("## 🎯 Intelligent Field Mapping")
    
    # AI Assistant Message
    st.markdown("""
    <div class="ai-insight">
        <strong>🤖 AI Assistant:</strong> I've analyzed your form and provided intelligent suggestions. 
        High-confidence mappings can be auto-accepted. All unmapped fields will automatically go to the questionnaire.
    </div>
    """, unsafe_allow_html=True)
    
    # Quick Stats
    fields = st.session_state.pdf_fields
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        total = len(fields)
        st.markdown('<div class="metric-card-enhanced">', unsafe_allow_html=True)
        st.metric("Total Fields", total)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        high_conf = sum(1 for f in fields if f.confidence_score > 0.8)
        st.markdown('<div class="metric-card-enhanced">', unsafe_allow_html=True)
        st.metric("High Confidence", high_conf)
        st.caption(f"{high_conf/total*100:.0f}% ready")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        mapped = sum(1 for f in fields if f.is_mapped)
        st.markdown('<div class="metric-card-enhanced">', unsafe_allow_html=True)
        st.metric("Mapped", mapped)
        st.caption(f"{mapped/total*100:.0f}% complete")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col4:
        quest = sum(1 for f in fields if f.is_questionnaire)
        st.markdown('<div class="metric-card-enhanced">', unsafe_allow_html=True)
        st.metric("Questionnaire", quest)
        st.caption("Manual entry")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col5:
        score = mapper.calculate_mapping_score(fields)
        st.markdown('<div class="metric-card-enhanced">', unsafe_allow_html=True)
        st.metric("AI Score", f"{score}%")
        st.caption("Overall quality")
        st.markdown('</div>', unsafe_allow_html=True)
    
    # AI Actions
    st.markdown("### ⚡ AI Quick Actions")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button(
            "🎯 Auto-Accept High Confidence",
            use_container_width=True,
            help="Accept all mappings with >80% confidence"
        ):
            count = 0
            for field in fields:
                if not field.is_mapped and field.confidence_score > 0.8 and field.db_mapping:
                    field.is_mapped = True
                    field.is_questionnaire = False
                    count += 1
            if count > 0:
                st.success(f"✅ Accepted {count} high-confidence mappings!")
                st.rerun()
    
    with col2:
        if st.button(
            "📋 Unmapped → Questionnaire",
            use_container_width=True,
            help="Move all unmapped fields to questionnaire"
        ):
            count = 0
            for field in fields:
                if not field.is_mapped and not field.is_questionnaire:
                    field.is_questionnaire = True
                    count += 1
            if count > 0:
                st.success(f"📋 Added {count} fields to questionnaire!")
                st.rerun()
    
    with col3:
        threshold = st.slider(
            "Confidence Threshold",
            0.5, 1.0, st.session_state.ai_confidence_threshold, 0.05,
            help="Set minimum confidence for auto-accept"
        )
        st.session_state.ai_confidence_threshold = threshold
    
    with col4:
        if st.button(
            "🔄 Reset All",
            use_container_width=True,
            help="Reset all mappings"
        ):
            for field in fields:
                field.is_mapped = False
                field.is_questionnaire = False
            st.rerun()
    
    # Filter and Search
    st.markdown("### 🔍 Filter & Search")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        parts = list(set(f.part for f in fields))
        parts.sort(key=lambda x: (0, int(re.search(r'\d+', x).group())) if re.search(r'\d+', x) else (1, x))
        
        selected_part = st.selectbox(
            "Filter by Part",
            ["All Parts"] + parts,
            help="Focus on specific form sections"
        )
    
    with col2:
        status_filter = st.selectbox(
            "Filter by Status",
            ["All", "AI Suggested", "Mapped", "Questionnaire", "Unmapped"],
            help="Filter by mapping status"
        )
    
    with col3:
        search_term = st.text_input(
            "Search fields",
            placeholder="Type to search...",
            help="Search field names or descriptions"
        )
    
    # Apply filters
    filtered_fields = []
    for field in fields:
        if selected_part != "All Parts" and field.part != selected_part:
            continue
        
        if status_filter == "AI Suggested" and (not field.db_mapping or field.is_mapped):
            continue
        elif status_filter == "Mapped" and not field.is_mapped:
            continue
        elif status_filter == "Questionnaire" and not field.is_questionnaire:
            continue
        elif status_filter == "Unmapped" and (field.is_mapped or field.is_questionnaire or field.db_mapping):
            continue
        
        if search_term and search_term.lower() not in f"{field.raw_name} {field.description} {field.db_mapping or ''}".lower():
            continue
        
        filtered_fields.append(field)
    
    # Display fields by part
    st.markdown(f"### 📊 Showing {len(filtered_fields)} of {len(fields)} fields")
    
    # Group by part
    fields_by_part = defaultdict(list)
    for field in filtered_fields:
        fields_by_part[field.part].append(field)
    
    # Sort parts
    sorted_parts = sorted(fields_by_part.keys(), 
                         key=lambda x: (0, int(re.search(r'\d+', x).group())) if re.search(r'\d+', x) else (1, x))
    
    for part in sorted_parts:
        part_fields = fields_by_part[part]
        context = mapper._get_part_context(part)
        
        # Part header with context
        if context == "attorney":
            icon = "⚖️"
            color = "#3b82f6"
            info = "Attorney/Representative Information (G-28 Attached)"
        elif context == "beneficiary":
            icon = "👤"
            color = "#10b981"
            info = "Beneficiary/Applicant Information"
        elif context == "petitioner":
            icon = "🏢"
            color = "#f59e0b"
            info = "Petitioner/Company Information"
        else:
            icon = "📄"
            color = "#6b7280"
            info = "General Information"
        
        # Part statistics
        mapped_count = sum(1 for f in part_fields if f.is_mapped)
        suggested_count = sum(1 for f in part_fields if f.db_mapping and not f.is_mapped)
        quest_count = sum(1 for f in part_fields if f.is_questionnaire)
        
        with st.expander(
            f"{icon} **{part}** ({len(part_fields)} fields | ✅ {mapped_count} | 💡 {suggested_count} | 📋 {quest_count})",
            expanded="Part 0" in part or "Part 1" in part
        ):
            # Context info
            st.info(f"🔍 **Context**: {info}")
            
            # Special note for Part 0
            if "Part 0" in part:
                st.markdown("""
                <div class="attorney-highlight">
                    <strong>⚖️ Attorney Section</strong> - These fields appear after "to be completed by attorney or accredited representative" text.
                </div>
                """, unsafe_allow_html=True)
            
            # Quick actions for this part
            col1, col2 = st.columns(2)
            with col1:
                if st.button(f"Accept all suggestions in {part}", key=f"accept_part_{part}"):
                    count = 0
                    for field in part_fields:
                        if not field.is_mapped and field.db_mapping:
                            field.is_mapped = True
                            field.is_questionnaire = False
                            count += 1
                    if count > 0:
                        st.success(f"✅ Accepted {count} mappings!")
                        st.rerun()
            
            with col2:
                if st.button(f"All unmapped to questionnaire", key=f"quest_part_{part}"):
                    count = 0
                    for field in part_fields:
                        if not field.is_mapped and not field.is_questionnaire:
                            field.is_questionnaire = True
                            count += 1
                    if count > 0:
                        st.success(f"📋 Added {count} to questionnaire!")
                        st.rerun()
            
            # Display fields
            for field in part_fields:
                render_intelligent_field_card(field, mapper)

def render_intelligent_field_card(field: PDFField, mapper: EnhancedUSCISMapper):
    """Render intelligent field mapping card"""
    with st.container():
        st.markdown('<div class="field-card-enhanced">', unsafe_allow_html=True)
        
        # Main content
        col1, col2, col3 = st.columns([5, 4, 1])
        
        with col1:
            # Field information
            st.markdown(f"### {field.clean_name} - {field.description}")
            
            # Metadata
            metadata = []
            if field.item:
                metadata.append(f"Item {field.item}")
            metadata.append(f"Type: {field.field_type}")
            metadata.append(f"Page {field.page}")
            
            st.caption(" | ".join(metadata))
            
            # Current status with AI insight
            if field.is_mapped and field.db_mapping:
                st.success(f"✅ **Mapped to:** `{field.db_mapping}`")
            elif field.db_mapping and not field.is_questionnaire:
                # Show AI suggestion with confidence
                st.info(f"🤖 **AI Suggests:** `{field.db_mapping}`")
                
                # Confidence bar
                st.markdown(f"""
                <div class="confidence-bar">
                    <div class="confidence-fill" style="width: {field.confidence_score * 100}%"></div>
                </div>
                """, unsafe_allow_html=True)
                
                st.caption(f"Confidence: {field.confidence_score:.0%}")
                
                # Show alternative suggestions if available
                if len(field.ai_suggestions) > 1:
                    with st.expander("View alternative suggestions"):
                        for i, alt in enumerate(field.ai_suggestions[1:3], 1):
                            st.write(f"{i}. `{alt}`")
            elif field.is_questionnaire:
                st.warning("📋 **In Questionnaire** - Manual entry required")
            else:
                st.error("❌ **Unmapped** - Will go to questionnaire")
        
        with col2:
            # Mapping controls
            if not field.is_mapped:
                mapping_action = st.selectbox(
                    "Action",
                    ["Choose Action", "Accept AI Suggestion", "Select Different Mapping", 
                     "Add to Questionnaire", "Set Default Value"],
                    key=f"action_{field.index}",
                    label_visibility="collapsed"
                )
                
                if mapping_action == "Accept AI Suggestion" and field.db_mapping:
                    st.info(f"Will map to: `{field.db_mapping}`")
                
                elif mapping_action == "Select Different Mapping":
                    # Smart search for database fields
                    search_query = st.text_input(
                        "Search database fields",
                        placeholder="Type to search...",
                        key=f"search_{field.index}"
                    )
                    
                    if search_query:
                        # Get relevant suggestions
                        all_paths = mapper.get_all_database_paths()
                        matches = [p for p in all_paths if search_query.lower() in p.lower()][:10]
                        
                        if matches:
                            selected_path = st.selectbox(
                                "Select mapping",
                                [""] + matches,
                                key=f"select_{field.index}"
                            )
                        else:
                            st.warning("No matches found")
                
                elif mapping_action == "Set Default Value":
                    default_value = st.text_input(
                        "Default value",
                        key=f"default_{field.index}",
                        placeholder="Enter default value"
                    )
            else:
                st.success("✅ Mapped")
                if st.button("Edit", key=f"edit_{field.index}"):
                    field.is_mapped = False
                    st.rerun()
        
        with col3:
            # Save button
            if not field.is_mapped and mapping_action != "Choose Action":
                if st.button("💾", key=f"save_{field.index}", help="Save mapping"):
                    if mapping_action == "Accept AI Suggestion" and field.db_mapping:
                        field.is_mapped = True
                        field.is_questionnaire = False
                        st.success("✅ Saved!")
                        st.rerun()
                    elif mapping_action == "Add to Questionnaire":
                        field.is_questionnaire = True
                        field.is_mapped = False
                        field.db_mapping = None
                        st.success("📋 Added!")
                        st.rerun()
                    elif mapping_action == "Select Different Mapping":
                        if f"select_{field.index}" in st.session_state:
                            selected = st.session_state[f"select_{field.index}"]
                            if selected:
                                field.db_mapping = selected
                                field.is_mapped = True
                                field.is_questionnaire = False
                                st.success("✅ Mapped!")
                                st.rerun()
                    elif mapping_action == "Set Default Value":
                        if f"default_{field.index}" in st.session_state:
                            value = st.session_state[f"default_{field.index}"]
                            if value:
                                field.db_mapping = f"Default: {value}"
                                field.is_mapped = True
                                field.is_questionnaire = False
                                st.success("✅ Set!")
                                st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)

def render_all_fields_view(mapper: EnhancedUSCISMapper):
    """Render all fields view with bulk actions"""
    if 'pdf_fields' not in st.session_state or not st.session_state.pdf_fields:
        st.info("👆 Please upload a PDF form first")
        return
    
    st.markdown("## 📊 All Fields Overview")
    
    fields = st.session_state.pdf_fields
    
    # Create DataFrame
    data = []
    for field in fields:
        status = "Mapped" if field.is_mapped else "Questionnaire" if field.is_questionnaire else "AI Suggested" if field.db_mapping else "Unmapped"
        
        data.append({
            "Index": field.index,
            "Field": field.description,
            "Clean Name": field.clean_name,
            "Part": field.part.split(' - ')[0] if ' - ' in field.part else field.part,
            "Type": field.field_type,
            "Status": status,
            "AI Confidence": f"{field.confidence_score:.0%}" if field.confidence_score > 0 else "-",
            "Database Path": field.db_mapping if field.db_mapping else "-",
            "Page": field.page
        })
    
    df = pd.DataFrame(data)
    
    # Display with color coding
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Status": st.column_config.TextColumn(
                "Status",
                help="Current mapping status"
            ),
            "AI Confidence": st.column_config.TextColumn(
                "AI Confidence",
                help="AI confidence score"
            ),
            "Field": st.column_config.TextColumn(
                "Field",
                help="Field description",
                width="large"
            ),
            "Database Path": st.column_config.TextColumn(
                "Database Path",
                help="Mapped database path",
                width="large"
            )
        }
    )

def render_export_dashboard(mapper: EnhancedUSCISMapper):
    """Render enhanced export dashboard"""
    if 'pdf_fields' not in st.session_state or not st.session_state.pdf_fields:
        st.info("👆 Please complete field mapping first")
        return
    
    st.markdown("## 📥 Export & Integration")
    
    fields = st.session_state.pdf_fields
    form_type = st.session_state.form_type
    
    # Export readiness check
    col1, col2, col3, col4 = st.columns(4)
    
    mapped_count = sum(1 for f in fields if f.is_mapped)
    quest_count = sum(1 for f in fields if f.is_questionnaire)
    unmapped_count = sum(1 for f in fields if not f.is_mapped and not f.is_questionnaire)
    
    with col1:
        st.markdown('<div class="metric-card-enhanced">', unsafe_allow_html=True)
        st.metric("✅ Ready", f"{mapped_count + quest_count}")
        st.caption("Fields configured")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="metric-card-enhanced">', unsafe_allow_html=True)
        st.metric("⚠️ Pending", unmapped_count)
        st.caption("Need attention")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        readiness = ((mapped_count + quest_count) / len(fields)) * 100 if fields else 0
        st.markdown('<div class="metric-card-enhanced">', unsafe_allow_html=True)
        st.metric("📊 Readiness", f"{readiness:.0f}%")
        st.caption("Export ready")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col4:
        quality = mapper.calculate_mapping_score(fields)
        st.markdown('<div class="metric-card-enhanced">', unsafe_allow_html=True)
        st.metric("⭐ Quality", f"{quality:.0f}%")
        st.caption("Mapping score")
        st.markdown('</div>', unsafe_allow_html=True)
    
    if unmapped_count > 0:
        st.warning(f"⚠️ {unmapped_count} fields are still unmapped. They will be added to the questionnaire on export.")
    
    # Export options
    st.markdown("### 🚀 Export Options")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📄 TypeScript Mapping")
        st.write("Generate TypeScript file for your application integration")
        
        # Export settings
        include_unmapped = st.checkbox("Auto-include unmapped as questionnaire", value=True)
        
        if st.button("🔧 Generate TypeScript", type="primary", use_container_width=True):
            # Auto-convert unmapped if selected
            if include_unmapped:
                for field in fields:
                    if not field.is_mapped and not field.is_questionnaire:
                        field.is_questionnaire = True
            
            ts_content = mapper.generate_typescript_export(form_type, fields)
            
            # Clean form name
            form_name = form_type.replace('-', '')
            
            st.download_button(
                "📥 Download TypeScript File",
                ts_content,
                f"{form_name}.ts",
                "text/plain",
                use_container_width=True
            )
            
            with st.expander("Preview TypeScript"):
                st.code(ts_content, language="typescript")
    
    with col2:
        st.markdown("#### 📋 Questionnaire JSON")
        st.write("Generate dynamic questionnaire for manual entry fields")
        
        # Questionnaire options
        group_by_part = st.checkbox("Group questions by part", value=True)
        
        if st.button("📝 Generate Questionnaire", type="primary", use_container_width=True):
            json_content = mapper.generate_questionnaire_json(fields)
            
            st.download_button(
                "📥 Download Questionnaire JSON",
                json_content,
                f"{form_type.lower()}-questionnaire.json",
                "application/json",
                use_container_width=True
            )
            
            with st.expander("Preview JSON"):
                st.code(json_content, language="json")
    
    # Additional exports
    st.markdown("### 📊 Additional Exports")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📈 Mapping Report", use_container_width=True):
            # Generate detailed report
            report = f"""# {form_type} Mapping Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}

## Summary
- Total Fields: {len(fields)}
- Mapped: {mapped_count} ({mapped_count/len(fields)*100:.1f}%)
- Questionnaire: {quest_count} ({quest_count/len(fields)*100:.1f}%)
- Unmapped: {unmapped_count} ({unmapped_count/len(fields)*100:.1f}%)

## AI Performance
- High Confidence (>80%): {sum(1 for f in fields if f.confidence_score > 0.8)}
- Medium Confidence (60-80%): {sum(1 for f in fields if 0.6 <= f.confidence_score <= 0.8)}
- Low Confidence (<60%): {sum(1 for f in fields if 0 < f.confidence_score < 0.6)}

## Form Detection
- Form Type: {form_type}
- Detection Confidence: {st.session_state.get('detection_confidence', 0):.0%}
- Has Attorney Section: {'Yes' if st.session_state.has_attorney_section else 'No'}
- Part 0 Fields Detected: {len(st.session_state.get('part0_fields', []))}

## Detailed Mappings
"""
            for field in fields:
                if field.is_mapped:
                    report += f"\n- **{field.clean_name}** ({field.description}) → `{field.db_mapping}`"
                    if field.confidence_score > 0:
                        report += f" (AI: {field.confidence_score:.0%})"
            
            st.download_button(
                "📥 Download Report",
                report,
                f"{form_type}_mapping_report.md",
                "text/markdown"
            )
    
    with col2:
        if st.button("📊 Export to Excel", use_container_width=True):
            # Create Excel export
            data = []
            for field in fields:
                data.append({
                    'Clean Name': field.clean_name,
                    'Description': field.description,
                    'Part': field.part,
                    'Type': field.field_type,
                    'Status': 'Mapped' if field.is_mapped else 'Questionnaire' if field.is_questionnaire else 'Unmapped',
                    'Database Path': field.db_mapping or '',
                    'AI Confidence': f"{field.confidence_score:.0%}" if field.confidence_score > 0 else '',
                    'Page': field.page
                })
            
            df = pd.DataFrame(data)
            csv = df.to_csv(index=False)
            
            st.download_button(
                "📥 Download CSV",
                csv,
                f"{form_type}_mappings.csv",
                "text/csv"
            )
    
    with col3:
        if st.button("🔗 API Integration", use_container_width=True):
            # Show API integration code
            api_code = f"""
// Integration example for {form_type}
import {{ {form_type.replace('-', '')} }} from './{form_type.replace('-', '')}.ts';

// Initialize form mapping
const formMapping = {form_type.replace('-', '')};

// Map PDF fields to database
async function mapFormData(pdfData) {{
    const mappedData = {{}};
    
    // Process customer data
    if (formMapping.customerData) {{
        mappedData.customer = mapFieldsToObject(pdfData, formMapping.customerData);
    }}
    
    // Process beneficiary data
    if (formMapping.beneficiaryData) {{
        mappedData.beneficiary = mapFieldsToObject(pdfData, formMapping.beneficiaryData);
    }}
    
    // Process attorney data (if G-28 attached)
    if (formMapping.attorneyData) {{
        mappedData.attorney = mapFieldsToObject(pdfData, formMapping.attorneyData);
    }}
    
    // Handle questionnaire fields
    const questionnaireData = await promptForQuestionnaireData(formMapping.questionnaireData);
    
    return {{ ...mappedData, ...questionnaireData }};
}}

// Helper function to map fields
function mapFieldsToObject(pdfData, fieldMapping) {{
    const result = {{}};
    
    for (const [pdfField, dbPath] of Object.entries(fieldMapping)) {{
        const value = pdfData[pdfField];
        setNestedProperty(result, dbPath, value);
    }}
    
    return result;
}}
"""
            st.code(api_code, language="javascript")

def render_ai_insights_dashboard(mapper: EnhancedUSCISMapper):
    """Render AI insights and analytics dashboard"""
    if 'pdf_fields' not in st.session_state or not st.session_state.pdf_fields:
        st.info("👆 Please complete field mapping first")
        return
    
    st.markdown("## 🧠 AI Insights & Analytics")
    
    fields = st.session_state.pdf_fields
    
    # Form Detection Insights
    if st.session_state.get('detected_form_type'):
        st.markdown("### 🔍 Form Detection Results")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Detected Form", st.session_state.detected_form_type)
        with col2:
            st.metric("Detection Confidence", f"{st.session_state.get('detection_confidence', 0):.0%}")
        with col3:
            st.metric("Form Title", USCIS_FORMS_DATABASE[st.session_state.detected_form_type]['title'])
    
    # AI Performance Metrics
    st.markdown("### 📊 AI Performance Metrics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        ai_suggested = sum(1 for f in fields if f.db_mapping)
        st.metric("🤖 AI Suggestions", ai_suggested)
        st.caption(f"{ai_suggested/len(fields)*100:.0f}% coverage")
    
    with col2:
        high_conf = sum(1 for f in fields if f.confidence_score > 0.8)
        st.metric("🎯 High Confidence", high_conf)
        st.caption(f"{high_conf/len(fields)*100:.0f}% of fields")
    
    with col3:
        accepted = sum(1 for f in fields if f.is_mapped and f.confidence_score > 0)
        if ai_suggested > 0:
            acceptance_rate = accepted / ai_suggested * 100
        else:
            acceptance_rate = 0
        st.metric("✅ Acceptance Rate", f"{acceptance_rate:.0f}%")
        st.caption("AI suggestions accepted")
    
    with col4:
        avg_conf = sum(f.confidence_score for f in fields if f.confidence_score > 0) / len([f for f in fields if f.confidence_score > 0]) if any(f.confidence_score > 0 for f in fields) else 0
        st.metric("📈 Avg Confidence", f"{avg_conf:.0%}")
        st.caption("Overall AI confidence")
    
    # Special Focus: Part 0 Detection
    if st.session_state.has_attorney_section:
        st.markdown("### ⚖️ Attorney Section (Part 0) Detection")
        
        part0_fields_count = len(st.session_state.get('part0_fields', []))
        part0_fields_in_data = [f for f in fields if "Part 0" in f.part]
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Detected Fields", part0_fields_count)
            st.caption("In attorney section")
        with col2:
            st.metric("Mapped to Part 0", len(part0_fields_in_data))
            st.caption("Successfully assigned")
        with col3:
            # Show first few Part 0 field names
            if part0_fields_in_data:
                st.metric("Sample Field", part0_fields_in_data[0].clean_name)
                st.caption("G-28 format")
    
    # Confidence Distribution
    st.markdown("### 📊 Confidence Distribution")
    
    # Create confidence bins
    conf_data = []
    for field in fields:
        if field.confidence_score > 0:
            if field.confidence_score > 0.9:
                bin_label = "90-100%"
            elif field.confidence_score > 0.8:
                bin_label = "80-90%"
            elif field.confidence_score > 0.7:
                bin_label = "70-80%"
            elif field.confidence_score > 0.6:
                bin_label = "60-70%"
            else:
                bin_label = "Below 60%"
            
            conf_data.append({
                "Confidence Range": bin_label,
                "Count": 1,
                "Status": "Accepted" if field.is_mapped else "Pending"
            })
    
    if conf_data:
        conf_df = pd.DataFrame(conf_data)
        conf_summary = conf_df.groupby(["Confidence Range", "Status"]).count().reset_index()
        
        # Display as a pivot table
        pivot_df = conf_summary.pivot(index="Confidence Range", columns="Status", values="Count").fillna(0)
        st.dataframe(pivot_df, use_container_width=True)
    
    # Pattern Analysis
    st.markdown("### 🔍 Pattern Analysis")
    
    # Analyze mapping patterns
    pattern_data = defaultdict(lambda: {"count": 0, "accepted": 0})
    
    for field in fields:
        if field.db_mapping:
            obj = field.db_mapping.split('.')[0]
            pattern_data[obj]["count"] += 1
            if field.is_mapped:
                pattern_data[obj]["accepted"] += 1
    
    if pattern_data:
        pattern_df = pd.DataFrame([
            {
                "Database Object": obj,
                "Suggestions": data["count"],
                "Accepted": data["accepted"],
                "Acceptance Rate": f"{data['accepted']/data['count']*100:.0f}%" if data['count'] > 0 else "0%"
            }
            for obj, data in pattern_data.items()
        ])
        
        st.dataframe(pattern_df, use_container_width=True, hide_index=True)
    
    # Learning Insights
    st.markdown("### 💡 AI Learning Insights")
    
    insights = []
    
    # Analyze form structure
    if st.session_state.has_attorney_section:
        insights.append("✅ Successfully detected attorney section (G-28 attached)")
        insights.append(f"⚖️ Found trigger text: 'to be completed by attorney or accredited representative'")
        if st.session_state.get('part0_fields'):
            insights.append(f"📝 Identified {len(st.session_state.part0_fields)} fields in Part 0 with G-28 naming format")
    
    # Analyze part detection
    parts_with_context = defaultdict(list)
    for field in fields:
        context = mapper._get_part_context(field.part)
        parts_with_context[context].append(field.part)
    
    for context, parts in parts_with_context.items():
        unique_parts = list(set(parts))
        if context == "beneficiary":
            insights.append(f"👤 Identified beneficiary sections: {', '.join(unique_parts)}")
        elif context == "attorney":
            insights.append(f"⚖️ Identified attorney sections: {', '.join(unique_parts)}")
        elif context == "petitioner":
            insights.append(f"🏢 Identified petitioner sections: {', '.join(unique_parts)}")
    
    # High confidence patterns
    high_conf_fields = [f for f in fields if f.confidence_score > 0.9]
    if high_conf_fields:
        insights.append(f"🎯 {len(high_conf_fields)} fields matched with >90% confidence")
    
    # Display insights
    for insight in insights:
        st.info(insight)
    
    # Recommendations
    st.markdown("### 🎯 AI Recommendations")
    
    recommendations = []
    
    # Check unmapped fields
    unmapped = [f for f in fields if not f.is_mapped and not f.is_questionnaire]
    if unmapped:
        recommendations.append(f"📋 {len(unmapped)} fields need attention - consider adding to questionnaire")
    
    # Check low confidence accepted
    low_conf_accepted = [f for f in fields if f.is_mapped and 0 < f.confidence_score < 0.6]
    if low_conf_accepted:
        recommendations.append(f"⚠️ {len(low_conf_accepted)} low-confidence mappings accepted - review for accuracy")
    
    # Check rejection rate
    rejected = [f for f in fields if f.db_mapping and not f.is_mapped and not f.is_questionnaire]
    if rejected and ai_suggested > 0:
        rejection_rate = len(rejected) / ai_suggested * 100
        if rejection_rate > 30:
            recommendations.append(f"🔍 High rejection rate ({rejection_rate:.0f}%) - AI may need adjustment")
    
    # Part 0 specific recommendations
    if st.session_state.has_attorney_section:
        part0_unmapped = [f for f in fields if "Part 0" in f.part and not f.is_mapped]
        if part0_unmapped:
            recommendations.append(f"⚖️ {len(part0_unmapped)} Part 0 (attorney) fields still unmapped")
    
    if not recommendations:
        recommendations.append("✅ All systems optimal - great mapping quality!")
    
    for rec in recommendations:
        st.warning(rec)

def main():
    """Enhanced main application"""
    st.set_page_config(
        page_title="Intelligent USCIS Form Mapper",
        page_icon="🧠",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Custom CSS
    st.markdown("""
    <style>
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }
        .stTabs [data-baseweb="tab"] {
            padding: 10px 20px;
            background-color: #f3f4f6;
            border-radius: 8px;
        }
        .stTabs [data-baseweb="tab"]:hover {
            background-color: #e5e7eb;
        }
        .stTabs [aria-selected="true"] {
            background-color: #667eea !important;
            color: white !important;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Initialize mapper
    mapper = EnhancedUSCISMapper()
    
    # Render header
    render_enhanced_header()
    
    # Sidebar with AI Assistant
    with st.sidebar:
        st.markdown("## 🤖 AI Assistant")
        
        if 'pdf_fields' in st.session_state and st.session_state.pdf_fields:
            fields = st.session_state.pdf_fields
            
            # AI Status
            st.markdown("### 📊 Current Status")
            
            total = len(fields)
            mapped = sum(1 for f in fields if f.is_mapped)
            progress = mapped / total if total > 0 else 0
            
            # Progress circle
            st.markdown(f"""
            <div style="text-align: center; padding: 20px;">
                <div style="position: relative; width: 120px; height: 120px; margin: 0 auto;">
                    <svg width="120" height="120" style="transform: rotate(-90deg);">
                        <circle cx="60" cy="60" r="50" fill="none" stroke="#e5e7eb" stroke-width="10"/>
                        <circle cx="60" cy="60" r="50" fill="none" stroke="#667eea" stroke-width="10"
                                stroke-dasharray="{progress * 314} 314" stroke-linecap="round"/>
                    </svg>
                    <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%) rotate(90deg); font-size: 24px; font-weight: bold;">
                        {progress * 100:.0f}%
                    </div>
                </div>
                <p style="margin-top: 10px; font-size: 14px; color: #6b7280;">Mapping Progress</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Quick stats
            st.markdown("### 📈 Quick Stats")
            
            stats = {
                "🤖 AI Suggested": sum(1 for f in fields if f.db_mapping),
                "✅ Mapped": mapped,
                "📋 Questionnaire": sum(1 for f in fields if f.is_questionnaire),
                "❌ Unmapped": sum(1 for f in fields if not f.is_mapped and not f.is_questionnaire)
            }
            
            for label, count in stats.items():
                st.write(f"{label}: **{count}**")
            
            # AI Insights
            st.markdown("### 💡 AI Insights")
            
            if st.session_state.has_attorney_section:
                st.success("✅ G-28 detected")
                if st.session_state.get('part0_fields'):
                    st.info(f"⚖️ {len(st.session_state.part0_fields)} Part 0 fields")
            
            high_conf = sum(1 for f in fields if f.confidence_score > 0.8)
            if high_conf > 0:
                st.info(f"🎯 {high_conf} high-confidence matches ready")
            
            # Form context
            st.markdown("### 📄 Form Context")
            st.write(f"**Form:** {st.session_state.form_type}")
            
            if st.session_state.get('detected_form_type'):
                st.write(f"**Auto-detected:** Yes ({st.session_state.get('detection_confidence', 0):.0%})")
            
            # Part breakdown
            parts = list(set(f.part for f in fields))
            st.write(f"**Parts:** {len(parts)}")
            
            # Context detection
            contexts = defaultdict(int)
            for field in fields:
                context = mapper._get_part_context(field.part)
                contexts[context] += 1
            
            for context, count in contexts.items():
                icon = {"attorney": "⚖️", "beneficiary": "👤", "petitioner": "🏢"}.get(context, "📄")
                st.write(f"{icon} {context.title()}: {count} fields")
        
        else:
            st.info("Upload a form to activate AI Assistant")
        
        # Help section
        st.markdown("---")
        st.markdown("### ❓ Need Help?")
        with st.expander("Quick Guide"):
            st.markdown("""
            1. **Upload Form**: Upload any USCIS PDF - auto-detection!
            2. **AI Analysis**: AI detects form type & suggests mappings
            3. **Review & Map**: Accept AI suggestions or customize
            4. **Export**: Generate TypeScript and JSON files
            
            **Tips:**
            - 🔍 No need to select form type
            - 🎯 High confidence = >80% accuracy
            - 📋 Unmapped fields → questionnaire
            - ⚖️ Part 0 = Attorney (if G-28 attached)
            - 👤 "Information About You" = Beneficiary
            
            **G-28 Format:**
            - Part 0 fields use "G28 P1_" format
            - Auto-detected from trigger text
            """)
    
    # Main content tabs
    tabs = st.tabs([
        "📤 Upload Form",
        "🎯 Smart Mapping",
        "📊 All Fields",
        "📥 Export",
        "🧠 AI Insights",
        "⚙️ Settings"
    ])
    
    with tabs[0]:
        render_enhanced_upload_section(mapper)
    
    with tabs[1]:
        render_intelligent_mapping_section(mapper)
    
    with tabs[2]:
        render_all_fields_view(mapper)
    
    with tabs[3]:
        render_export_dashboard(mapper)
    
    with tabs[4]:
        render_ai_insights_dashboard(mapper)
    
    with tabs[5]:
        st.markdown("## ⚙️ Settings & Configuration")
        
        # AI Settings
        st.markdown("### 🤖 AI Configuration")
        
        col1, col2 = st.columns(2)
        
        with col1:
            confidence_threshold = st.slider(
                "Auto-accept confidence threshold",
                0.5, 1.0, st.session_state.ai_confidence_threshold, 0.05,
                help="Minimum confidence for auto-accepting AI suggestions"
            )
            st.session_state.ai_confidence_threshold = confidence_threshold
            
            enable_learning = st.checkbox(
                "Enable AI learning from corrections",
                value=True,
                help="Allow AI to learn from your mapping corrections"
            )
        
        with col2:
            fuzzy_match = st.checkbox(
                "Enable fuzzy matching",
                value=True,
                help="Use fuzzy string matching for better suggestions"
            )
            
            context_aware = st.checkbox(
                "Context-aware mapping",
                value=True,
                help="Consider form context when suggesting mappings"
            )
        
        # Database Configuration
        st.markdown("### 🗄️ Database Configuration")
        
        with st.expander("View Database Schema"):
            st.json(DB_OBJECTS)
        
        # Form Intelligence
        st.markdown("### 🧠 Form Intelligence")
        
        with st.expander("View Form Understanding Rules"):
            st.json(FORM_INTELLIGENCE)
        
        with st.expander("View Supported Forms"):
            forms_df = pd.DataFrame([
                {"Form": code, "Title": info["title"]}
                for code, info in USCIS_FORMS_DATABASE.items()
            ])
            st.dataframe(forms_df, use_container_width=True, hide_index=True)
        
        # Clear data
        st.markdown("### 🗑️ Clear Data")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Clear Current Form", type="secondary", use_container_width=True):
                for key in ['pdf_fields', 'form_type', 'field_mappings', 'has_attorney_section', 
                           'detected_form_type', 'detection_confidence', 'part0_fields']:
                    if key in st.session_state:
                        del st.session_state[key]
                st.success("Form data cleared!")
                st.rerun()
        
        with col2:
            if st.button("Reset All Settings", type="secondary", use_container_width=True):
                st.session_state.clear()
                st.success("All settings reset!")
                st.rerun()

if __name__ == "__main__":
    main()
