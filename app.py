import streamlit as st
import os
import requests
import json
import pandas as pd
from datetime import datetime
import re
import base64
from io import BytesIO
from PIL import Image

# Set page config
st.set_page_config(
    page_title="Lawtrax Immigration Assistant",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for professional legal theme
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 50%, #1e40af 100%);
        padding: 2rem;
        border-radius: 15px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .logo-container {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 20px;
        margin-bottom: 1rem;
    }
    .lawtrax-logo {
        background: white;
        padding: 15px 30px;
        border-radius: 10px;
        font-size: 28px;
        font-weight: bold;
        color: #1e3a8a;
        letter-spacing: 2px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .professional-card {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .rfe-box {
        background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
        border-left: 5px solid #f59e0b;
        padding: 1.5rem;
        margin: 1rem 0;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .warning-box {
        background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
        border-left: 5px solid #ef4444;
        padding: 1.5rem;
        margin: 1rem 0;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .success-box {
        background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
        border-left: 5px solid #10b981;
        padding: 1.5rem;
        margin: 1rem 0;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .info-box {
        background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
        border-left: 5px solid #3b82f6;
        padding: 1.5rem;
        margin: 1rem 0;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .tab-content {
        padding: 2rem 1rem;
    }
    .professional-button {
        background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
        color: white;
        border: none;
        padding: 12px 24px;
        border-radius: 8px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.3s ease;
    }
    .professional-button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.15);
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        padding: 0px 20px;
        background-color: #f8fafc;
        border-radius: 8px 8px 0px 0px;
        color: #64748b;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #1e3a8a;
        color: white;
    }
    .footer {
        text-align: center;
        padding: 2rem;
        background: #f8fafc;
        border-radius: 10px;
        margin-top: 3rem;
        border-top: 3px solid #1e3a8a;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'case_details' not in st.session_state:
    st.session_state.case_details = {}

# Comprehensive US Visa Categories and Immigration Types
US_VISA_CATEGORIES = {
    "Non-Immigrant Visas": {
        "Business/Work": {
            "H-1B": "Specialty Occupation Workers",
            "H-1B1": "Free Trade Agreement Professionals (Chile/Singapore)",
            "H-2A": "Temporary Agricultural Workers",
            "H-2B": "Temporary Non-Agricultural Workers",
            "H-3": "Trainees and Special Education Exchange Visitors",
            "H-4": "Dependents of H Visa Holders",
            "L-1A": "Intracompany Transferee Executives/Managers",
            "L-1B": "Intracompany Transferee Specialized Knowledge",
            "L-2": "Dependents of L-1 Visa Holders",
            "O-1A": "Extraordinary Ability in Sciences/Education/Business/Athletics",
            "O-1B": "Extraordinary Ability in Arts/Motion Pictures/TV",
            "O-2": "Support Personnel for O-1",
            "O-3": "Dependents of O-1/O-2 Visa Holders",
            "P-1A": "Internationally Recognized Athletes",
            "P-1B": "Members of Internationally Recognized Entertainment Groups",
            "P-2": "Artists/Entertainers in Reciprocal Exchange Programs",
            "P-3": "Artists/Entertainers in Culturally Unique Programs",
            "P-4": "Dependents of P Visa Holders",
            "E-1": "Treaty Traders",
            "E-2": "Treaty Investors",
            "E-3": "Australian Professionals",
            "TN": "NAFTA/USMCA Professionals",
            "R-1": "Religious Workers",
            "R-2": "Dependents of R-1 Visa Holders"
        },
        "Students/Exchange": {
            "F-1": "Academic Students",
            "F-2": "Dependents of F-1 Students",
            "M-1": "Vocational Students",
            "M-2": "Dependents of M-1 Students",
            "J-1": "Exchange Visitors",
            "J-2": "Dependents of J-1 Exchange Visitors"
        },
        "Visitors": {
            "B-1": "Business Visitors",
            "B-2": "Tourism/Pleasure Visitors",
            "B-1/B-2": "Combined Business/Tourism"
        },
        "Transit/Crew": {
            "C-1": "Transit Aliens",
            "C-2": "Transit to UN Headquarters",
            "C-3": "Government Officials in Transit",
            "D-1": "Crew Members (Sea/Air)",
            "D-2": "Crew Members (Continuing Service)"
        },
        "Media": {
            "I": "Representatives of Foreign Media"
        },
        "Diplomatic": {
            "A-1": "Ambassadors/Government Officials",
            "A-2": "Government Officials/Employees",
            "A-3": "Personal Employees of A-1/A-2",
            "G-1": "Representatives to International Organizations",
            "G-2": "Representatives to International Organizations",
            "G-3": "Representatives to International Organizations",
            "G-4": "International Organization Officers/Employees",
            "G-5": "Personal Employees of G-1 through G-4"
        },
        "Other": {
            "K-1": "Fiancé(e) of US Citizen",
            "K-2": "Children of K-1",
            "K-3": "Spouse of US Citizen",
            "K-4": "Children of K-3",
            "Q-1": "International Cultural Exchange",
            "Q-2": "Irish Peace Process Cultural/Training Program",
            "Q-3": "Dependents of Q-2",
            "S-5": "Informants on Criminal Organizations",
            "S-6": "Informants on Terrorism",
            "S-7": "Dependents of S-5/S-6",
            "T-1": "Victims of Human Trafficking",
            "T-2": "Spouse of T-1",
            "T-3": "Child of T-1",
            "T-4": "Parent of T-1",
            "U-1": "Victims of Criminal Activity",
            "U-2": "Spouse of U-1",
            "U-3": "Child of U-1",
            "U-4": "Parent of U-1",
            "V-1": "Spouse of LPR",
            "V-2": "Child of LPR",
            "V-3": "Derivative Child of V-1/V-2"
        }
    },
        "Green Card/Permanent Residence": {
            "Employment-Based Green Cards": {
                "EB-1A": "Extraordinary Ability",
                "EB-1B": "Outstanding Professors and Researchers", 
                "EB-1C": "Multinational Managers and Executives",
                "EB-2": "Advanced Degree Professionals",
                "EB-2 NIW": "National Interest Waiver",
                "EB-3": "Skilled Workers and Professionals",
                "EB-3 Other": "Other Workers (Unskilled)",
                "EB-4": "Special Immigrants (Religious Workers, etc.)",
                "EB-5": "Immigrant Investors"
            },
            "Family-Based Green Cards": {
                "IR-1": "Spouse of US Citizen",
                "IR-2": "Unmarried Child (Under 21) of US Citizen",
                "IR-3": "Orphan Adopted Abroad by US Citizen",
                "IR-4": "Orphan to be Adopted by US Citizen", 
                "IR-5": "Parent of US Citizen (21 or older)",
                "F1": "Unmarried Sons/Daughters of US Citizens",
                "F2A": "Spouses/Unmarried Children (Under 21) of LPRs",
                "F2B": "Unmarried Sons/Daughters (21+) of LPRs",
                "F3": "Married Sons/Daughters of US Citizens",
                "F4": "Siblings of US Citizens"
            },
            "Other Green Card Categories": {
                "Diversity Visa": "DV Lottery Winners",
                "Asylum-Based": "Asylum Adjustment of Status",
                "Refugee-Based": "Refugee Adjustment of Status",
                "VAWA": "Violence Against Women Act",
                "Registry": "Registry (Pre-1972 Entry)",
                "Cuban Adjustment": "Cuban Adjustment Act",
                "Nicaraguan/Central American": "NACARA",
                "Special Immigrant Juvenile": "SIJ Status"
            },
            "Green Card Processes": {
                "I-485": "Adjustment of Status",
                "Consular Processing": "Immigrant Visa Processing Abroad",
                "I-601": "Inadmissibility Waiver",
                "I-601A": "Provisional Unlawful Presence Waiver",
                "I-751": "Removal of Conditions on Residence",
                "I-90": "Green Card Renewal/Replacement"
            }
        },
        "Family-Based": {
            "IR-1": "Spouse of US Citizen",
            "IR-2": "Unmarried Child (Under 21) of US Citizen",
            "IR-3": "Orphan Adopted Abroad by US Citizen",
            "IR-4": "Orphan to be Adopted by US Citizen",
            "IR-5": "Parent of US Citizen (21 or older)",
            "F1": "Unmarried Sons/Daughters of US Citizens",
            "F2A": "Spouses/Unmarried Children (Under 21) of LPRs",
            "F2B": "Unmarried Sons/Daughters (21+) of LPRs",
            "F3": "Married Sons/Daughters of US Citizens",
            "F4": "Siblings of US Citizens"
        },
        "Employment-Based": {
            "EB-1A": "Extraordinary Ability",
            "EB-1B": "Outstanding Professors/Researchers",
            "EB-1C": "Multinational Managers/Executives",
            "EB-2": "Advanced Degree Professionals",
            "EB-2 NIW": "National Interest Waiver",
            "EB-3": "Skilled Workers/Professionals",
            "EB-3 Other": "Other Workers",
            "EB-4": "Special Immigrants",
            "EB-5": "Immigrant Investors"
        },
        "Diversity": {
            "DV": "Diversity Visa Lottery"
        },
        "Special Categories": {
            "Asylum": "Asylum-Based Adjustment",
            "Refugee": "Refugee-Based Adjustment",
            "VAWA": "Violence Against Women Act",
            "Registry": "Registry (Pre-1972 Entry)"
        }
            },
        "Other Immigration Matters": {
            "Status Changes": {
                "AOS": "Adjustment of Status",
                "COS": "Change of Status",
                "Extension": "Extension of Stay"
            },
            "Naturalization": {
                "N-400": "Application for Naturalization",
                "N-600": "Certificate of Citizenship",
                "N-565": "Replacement of Citizenship Document"
            },
            "Protection": {
                "Asylum": "Asylum Applications",
                "Withholding": "Withholding of Removal",
                "CAT": "Convention Against Torture",
                "TPS": "Temporary Protected Status",
                "DED": "Deferred Enforced Departure"
            },
            "Removal Defense": {
                "Cancellation": "Cancellation of Removal",
                "Relief": "Other Forms of Relief",
                "Appeals": "BIA Appeals",
                "Motions": "Motions to Reopen/Reconsider"
            },
            "Special Programs": {
                "DACA": "Deferred Action for Childhood Arrivals",
                "Parole": "Humanitarian Parole",
                "Waiver": "Inadmissibility Waivers"
            }
        }
}

def load_logo():
    """Load Lawtrax logo from file or create professional text logo"""
    try:
        # Try to load logo from local file first
        if os.path.exists("assets/lawtrax_logo.png"):
            return Image.open("assets/lawtrax_logo.png")
        return None
    except Exception:
        return None

def call_openai_api(prompt, max_tokens=2000, temperature=0.3):
    """Call OpenAI API for immigration law assistance"""
    try:
        # Get API key
        api_key = None
        if hasattr(st, 'secrets') and "OPENAI_API_KEY" in st.secrets:
            api_key = st.secrets["OPENAI_API_KEY"]
        elif os.getenv("OPENAI_API_KEY"):
            api_key = os.getenv("OPENAI_API_KEY")
        else:
            st.error("❌ OpenAI API key not found. Please configure your API key in Streamlit secrets.")
            return None
        
        if not api_key or not api_key.startswith('sk-'):
            st.error("❌ Invalid API key format. Please check your configuration.")
            return None
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=60
        )
        
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            st.error(f"API Error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        st.error(f"Error calling OpenAI API: {str(e)}")
        return None

def check_soc_code(soc_code):
    """Check if SOC code is in Job Zone 3 (to avoid)"""
    if soc_code in JOB_ZONE_3_CODES:
        return {
            "status": "WARNING",
            "message": f"⚠️ This SOC code ({soc_code}) is Job Zone 3 and should be avoided for H-1B specialty occupation.",
            "title": JOB_ZONE_3_CODES[soc_code],
            "recommendation": "Consider finding a more specific SOC code that falls in Job Zone 4 or 5."
        }
    else:
        return {
            "status": "OK", 
            "message": f"✅ SOC code {soc_code} appears to be acceptable (not in Job Zone 3).",
            "recommendation": "Verify this SOC code aligns with the actual job duties and requirements."
        }

def generate_comprehensive_immigration_response(case_type, visa_category, case_details):
    """Generate comprehensive immigration responses for any US visa type or immigration matter"""
    
    if case_type == "RFE Response":
        if visa_category in ["H-1B", "H-1B1", "E-3", "TN"]:
            return generate_work_visa_rfe_response(visa_category, case_details)
        elif visa_category in ["L-1A", "L-1B"]:
            return generate_l_visa_rfe_response(visa_category, case_details)
        elif visa_category in ["O-1A", "O-1B"]:
            return generate_o_visa_rfe_response(visa_category, case_details)
        elif visa_category in ["EB-1A", "EB-1B", "EB-1C", "EB-2", "EB-3"]:
            return generate_immigrant_visa_rfe_response(visa_category, case_details)
        elif visa_category in ["F-1", "M-1", "J-1"]:
            return generate_student_visa_rfe_response(visa_category, case_details)
        elif visa_category in ["Family-Based"]:
            return generate_family_visa_rfe_response(case_details)
        else:
            return generate_general_rfe_response(visa_category, case_details)
    
    elif case_type == "Initial Petition":
        return generate_initial_petition_guidance(visa_category, case_details)
    
    elif case_type == "Motion":
        return generate_motion_response(visa_category, case_details)
    
    elif case_type == "Appeal":
        return generate_appeal_brief(visa_category, case_details)
    
    else:
        return generate_general_immigration_guidance(case_type, visa_category, case_details)

def generate_work_visa_rfe_response(visa_category, case_details):
    """Generate RFE responses for work-based visas"""
    prompt = f"""
    As an expert immigration attorney, draft a comprehensive RFE response for a {visa_category} petition.

    Case Details:
    - Visa Category: {visa_category}
    - Position: {case_details.get('position', 'Not specified')}
    - Company: {case_details.get('company', 'Not specified')}
    - Beneficiary: {case_details.get('beneficiary', 'Not specified')}
    - RFE Issues: {case_details.get('rfe_issues', 'Not specified')}
    - Additional Details: {case_details.get('additional_details', 'Not specified')}

    Provide a comprehensive legal response addressing:
    1. Specific requirements for {visa_category} classification
    2. Regulatory framework and legal standards
    3. Evidence and documentation requirements
    4. Case law and precedents supporting the petition
    5. Industry standards and best practices
    6. Expert opinion recommendations
    7. Risk mitigation strategies

    Format as a professional legal brief suitable for USCIS submission with proper citations and legal reasoning.
    """
    return call_openai_api(prompt, max_tokens=3000, temperature=0.2)

def generate_l_visa_rfe_response(visa_category, case_details):
    """Generate RFE responses for L-1 intracompany transferee visas"""
    prompt = f"""
    As an expert immigration attorney specializing in intracompany transferees, draft a comprehensive RFE response for an {visa_category} petition.

    Case Details:
    - Visa Category: {visa_category}
    - Position: {case_details.get('position', 'Not specified')}
    - US Company: {case_details.get('us_company', 'Not specified')}
    - Foreign Company: {case_details.get('foreign_company', 'Not specified')}
    - Relationship: {case_details.get('company_relationship', 'Not specified')}
    - Beneficiary Experience: {case_details.get('experience', 'Not specified')}
    - RFE Issues: {case_details.get('rfe_issues', 'Not specified')}

    Address the following {visa_category} requirements:
    1. Qualifying relationship between US and foreign entities
    2. Beneficiary's qualifying employment abroad (1 year in 3 years)
    3. Managerial/Executive capacity (L-1A) or Specialized Knowledge (L-1B)
    4. Position offered in the US
    5. Corporate documentation and business operations
    6. Detailed organizational structure and reporting relationships

    Provide legal analysis with citations to 8 CFR 214.2(l) and relevant case law.
    """
    return call_openai_api(prompt, max_tokens=3000, temperature=0.2)

def generate_o_visa_rfe_response(visa_category, case_details):
    """Generate RFE responses for O-1 extraordinary ability visas"""
    prompt = f"""
    As an expert immigration attorney specializing in extraordinary ability cases, draft a comprehensive RFE response for an {visa_category} petition.

    Case Details:
    - Visa Category: {visa_category}
    - Field of Expertise: {case_details.get('field', 'Not specified')}
    - Beneficiary: {case_details.get('beneficiary', 'Not specified')}
    - Achievements: {case_details.get('achievements', 'Not specified')}
    - Evidence Submitted: {case_details.get('evidence', 'Not specified')}
    - RFE Issues: {case_details.get('rfe_issues', 'Not specified')}

    Address {visa_category} extraordinary ability criteria:
    1. Evidence of extraordinary ability through sustained national/international acclaim
    2. Recognition for achievements and significant contributions
    3. Consultation requirements and peer recognition
    4. Specific events/activities in the US
    5. Itinerary and supporting documentation

    For O-1A (Sciences/Education/Business/Athletics):
    - Major awards or recognition
    - Membership in exclusive associations
    - Published material about the beneficiary
    - Original contributions of major significance
    - Scholarly articles
    - High salary or remuneration
    - Critical role in distinguished organizations

    For O-1B (Arts/Motion Pictures/TV):
    - Leading/starring roles in distinguished productions
    - Critical reviews and recognition
    - Commercial or critically acclaimed successes
    - High salary or remuneration

    Provide detailed legal analysis with regulatory citations and supporting evidence strategy.
    """
    return call_openai_api(prompt, max_tokens=3000, temperature=0.2)

def generate_immigrant_visa_rfe_response(visa_category, case_details):
    """Generate RFE responses for employment-based immigrant visas"""
    prompt = f"""
    As an expert immigration attorney specializing in employment-based immigrant petitions, draft a comprehensive RFE response for an {visa_category} case.

    Case Details:
    - Visa Category: {visa_category}
    - Beneficiary: {case_details.get('beneficiary', 'Not specified')}
    - Employer: {case_details.get('employer', 'Not specified')}
    - Position: {case_details.get('position', 'Not specified')}
    - Priority Date: {case_details.get('priority_date', 'Not specified')}
    - Labor Certification: {case_details.get('labor_cert', 'Not specified')}
    - RFE Issues: {case_details.get('rfe_issues', 'Not specified')}

    Address specific {visa_category} requirements:

    For EB-1A (Extraordinary Ability):
    - Sustained national/international acclaim
    - Evidence of extraordinary ability in field
    - Continued work in area of expertise
    - Substantial benefit to the US

    For EB-1B (Outstanding Professor/Researcher):
    - International recognition for outstanding achievements
    - At least 3 years experience in teaching/research
    - Tenure track or permanent research position offer

    For EB-1C (Multinational Manager/Executive):
    - Qualifying managerial/executive position abroad
    - Same employer or qualifying relationship
    - Managerial/executive position in US

    For EB-2 (Advanced Degree/Exceptional Ability):
    - Advanced degree or exceptional ability
    - Labor certification (unless NIW)
    - Job offer requiring advanced degree

    For EB-3 (Skilled Worker/Professional):
    - Bachelor's degree or 2+ years experience
    - Labor certification
    - Permanent, full-time job offer

    Provide comprehensive legal analysis with INA and regulatory citations.
    """
    return call_openai_api(prompt, max_tokens=3000, temperature=0.2)

def generate_family_visa_rfe_response(case_details):
    """Generate RFE responses for family-based immigration cases"""
    prompt = f"""
    As an expert immigration attorney specializing in family-based immigration, draft a comprehensive RFE response.

    Case Details:
    - Petition Type: {case_details.get('petition_type', 'Not specified')}
    - Petitioner: {case_details.get('petitioner', 'Not specified')}
    - Beneficiary: {case_details.get('beneficiary', 'Not specified')}
    - Relationship: {case_details.get('relationship', 'Not specified')}
    - Marriage Date: {case_details.get('marriage_date', 'Not specified')}
    - RFE Issues: {case_details.get('rfe_issues', 'Not specified')}

    Address family-based petition requirements:
    1. Qualifying relationship establishment
    2. Petitioner's US citizenship or LPR status
    3. Bona fide marriage evidence (if applicable)
    4. Financial support requirements (I-864)
    5. Admissibility issues and waivers
    6. Documentary evidence of relationship

    For Marriage Cases:
    - Evidence of bona fide marriage
    - Joint financial documents
    - Cohabitation evidence
    - Social evidence of relationship
    - Termination of previous marriages

    For Parent/Child Cases:
    - Birth certificates and relationship proof
    - Age requirements and legitimation
    - Adoption documentation if applicable

    Provide legal analysis with INA citations and evidentiary recommendations.
    """
    return call_openai_api(prompt, max_tokens=3000, temperature=0.2)

def generate_general_immigration_guidance(case_type, visa_category, case_details):
    """Generate general immigration guidance for any type of case"""
    prompt = f"""
    As an expert immigration attorney with comprehensive knowledge of US immigration law, provide detailed guidance on:

    Case Type: {case_type}
    Visa Category: {visa_category}
    Question/Issue: {case_details.get('question', case_details.get('issue', 'Not specified'))}
    
    Additional Details:
    {case_details.get('details', 'Not specified')}

    Provide comprehensive legal guidance including:
    1. Applicable legal framework and regulatory requirements
    2. Current USCIS policies and procedures
    3. Required documentation and evidence
    4. Strategic considerations and best practices
    5. Potential challenges and risk mitigation
    6. Timeline and procedural requirements
    7. Recent updates or changes in law/policy
    8. Alternative options or strategies if applicable

    Include relevant citations to INA, CFR, USCIS Policy Manual, and case law as appropriate.
    Format as professional legal guidance suitable for attorney use.
    """
    return call_openai_api(prompt, max_tokens=3000, temperature=0.2)

def generate_expert_opinion_letter(letter_type, case_details):
    """Generate expert opinion letter for immigration cases"""
    
    if letter_type == "Position Expert Opinion":
        prompt = f"""
        Draft a professional expert opinion letter for an H-1B specialty occupation case from a qualified industry expert's perspective.

        Position Details:
        - Position Title: {case_details.get('position', 'Not specified')}
        - Company: {case_details.get('company', 'Not specified')}
        - Industry: {case_details.get('industry', 'Not specified')}
        - Job Duties: {case_details.get('job_duties', 'Not specified')}
        - Education Requirement: {case_details.get('education_req', 'Not specified')}

        The expert opinion letter should:
        1. Establish the expert's credentials, education, and extensive industry experience
        2. Analyze the position's complexity and specialized knowledge requirements
        3. Confirm minimum education requirements for similar roles in the industry
        4. Compare position requirements to industry standards and best practices
        5. Address specialty occupation criteria under INA 214(i)(1) and 8 CFR 214.2(h)(4)(iii)(A)
        6. Provide professional opinion on the necessity of the degree requirement
        7. Include industry data, standards, and comparable positions

        Format as a formal expert declaration with professional letterhead structure, suitable for USCIS submission.
        """
        
    elif letter_type == "Beneficiary Qualifications Expert Opinion":
        prompt = f"""
        Draft a professional expert opinion letter evaluating a beneficiary's qualifications for an H-1B position.

        Beneficiary & Position Details:
        - Beneficiary: {case_details.get('beneficiary_name', 'Not specified')}
        - Education: {case_details.get('education', 'Not specified')}
        - Experience: {case_details.get('experience', 'Not specified')}
        - Position: {case_details.get('position', 'Not specified')}
        - Job Duties: {case_details.get('job_duties', 'Not specified')}

        The expert evaluation should:
        1. Assess and evaluate the beneficiary's educational background and credentials
        2. Analyze work experience and its direct relevance to the position
        3. Apply appropriate equivalency standards and three-for-one rule if needed
        4. Address any education-position relationship concerns comprehensively
        5. Confirm beneficiary meets or exceeds minimum requirements for the role
        6. Provide detailed professional opinion on qualification sufficiency
        7. Include credential analysis and industry comparison

        Format as a formal expert evaluation with expert credentials, detailed analysis, and professional conclusions suitable for legal submission.
        """

    return call_openai_api(prompt, max_tokens=2500, temperature=0.2)

def main():
    # Professional Header with Logo
    logo = load_logo()
    
    st.markdown("""
    <div class="main-header">
        <div class="logo-container">
            <div class="lawtrax-logo">LAWTRAX</div>
        </div>
        <h1 style='margin: 0; font-size: 2.5rem; font-weight: 300;'>Immigration Law Assistant</h1>
        <p style='margin: 0.5rem 0 0 0; font-size: 1.1rem; opacity: 0.9;'>
            Professional AI-Powered Legal Research & RFE Response Generation
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Professional Disclaimer
    st.markdown("""
    <div class="warning-box">
        <strong>⚖️ ATTORNEY USE ONLY:</strong> This tool is exclusively designed for licensed immigration attorneys and qualified legal professionals. 
        All AI-generated content must be reviewed, verified, and approved by supervising counsel before use. This system does not provide legal advice to end clients.
    </div>
    """, unsafe_allow_html=True)

    # Check API Configuration
    if hasattr(st, 'secrets') and "OPENAI_API_KEY" in st.secrets:
        st.markdown("""
        <div class="success-box">
            <strong>✅ System Status:</strong> Immigration Assistant is ready for professional use. API connectivity confirmed.
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="warning-box">
            <strong>⚠️ Configuration Required:</strong> Please configure your OpenAI API key in Streamlit secrets to enable AI-powered legal research.
        </div>
        """, unsafe_allow_html=True)

    # Main content tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "💬 Legal Research Chat", 
        "📄 RFE Response Generator", 
        "📝 Expert Opinion Letters",
        "📊 Professional Templates",
        "📚 Legal Resources"
    ])

    with tab1:
        st.markdown("<div class='tab-content'>", unsafe_allow_html=True)
        st.subheader("💬 Immigration Law Research Assistant")
        
        st.markdown("""
        <div class="info-box">
            <strong>Professional Research Tool:</strong> Ask complex immigration law questions and receive comprehensive, 
            citation-backed analysis suitable for attorney use. This tool provides current legal guidance, case law analysis, 
            and practical recommendations for immigration practice.
        </div>
        """, unsafe_allow_html=True)
        
        # Research interface
        question = st.text_area(
            "Enter your immigration law research question:",
            placeholder="Example: What are the latest USCIS policy updates for H-1B specialty occupation determinations? How should I address a complex beneficiary qualifications RFE?",
            height=120,
            help="Ask detailed questions about immigration law, policy updates, case strategies, or legal precedents."
        )
        
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("🔍 Research Question", type="primary", use_container_width=True):
                if question:
                    with st.spinner("Conducting legal research..."):
                        response = generate_rfe_response("General", {"question": question})
                        if response:
                            st.session_state.chat_history.append({
                                "question": question,
                                "answer": response,
                                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            })
                            
                            st.markdown("### 📋 Research Results")
                            st.markdown(f"""
                            <div class="professional-card">
                                <strong>Question:</strong> {question}<br><br>
                                {response}
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Download option
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            filename = f"Legal_Research_{timestamp}.txt"
                            download_content = f"LAWTRAX IMMIGRATION RESEARCH\n{'='*50}\n\nQuestion: {question}\n\nResearch Results:\n{response}\n\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                            st.download_button(
                                "📥 Download Research",
                                data=download_content,
                                file_name=filename,
                                mime="text/plain",
                                use_container_width=True
                            )
                else:
                    st.warning("Please enter a research question.")
        
        # Display recent research history
        if st.session_state.chat_history:
            st.markdown("### 📚 Recent Research History")
            for i, chat in enumerate(reversed(st.session_state.chat_history[-3:])):  # Show last 3
                with st.expander(f"📋 {chat['question'][:80]}... ({chat['timestamp']})"):
                    st.markdown(chat['answer'])
        
        st.markdown("</div>", unsafe_allow_html=True)

    with tab2:
        st.markdown("<div class='tab-content'>", unsafe_allow_html=True)
        st.subheader("📄 Comprehensive Immigration Response Generator")
        
        st.markdown("""
        <div class="info-box">
            <strong>🎯 Complete US Immigration Coverage:</strong> Generate professional responses for any US visa type, 
            immigration petition, RFE, motion, or appeal. Covers all non-immigrant visas, immigrant visas, 
            adjustment of status, naturalization, and removal defense matters.
        </div>
        """, unsafe_allow_html=True)
        
        # Case Type and Visa Category Selection
        col1, col2 = st.columns(2)
        
        with col1:
            case_type = st.selectbox(
                "Select Case Type:",
                ["RFE Response", "Initial Petition Strategy", "Motion to Reopen/Reconsider", 
                 "BIA Appeal Brief", "Adjustment of Status", "Naturalization", 
                 "Removal Defense", "Waiver Application", "General Immigration Guidance"],
                help="Choose the type of immigration matter you need assistance with"
            )
        
        with col2:
            # Visa category selection based on comprehensive list
            visa_categories = []
            for main_cat, subcats in US_VISA_CATEGORIES.items():
                for subcat, visas in subcats.items():
                    for visa_code, visa_name in visas.items():
                        visa_categories.append(f"{visa_code} - {visa_name}")
            
            visa_category = st.selectbox(
                "Select Visa Type/Immigration Category:",
                ["General Immigration Matter"] + sorted(visa_categories),
                help="Choose the specific visa type or immigration category"
            )
        
        # Dynamic form based on case type and visa category
        if case_type == "RFE Response":
            st.markdown("""
            <div class="rfe-box">
                <strong>🎯 RFE Response Strategy:</strong><br>
                • Address all specific issues raised in the RFE<br>
                • Provide comprehensive legal analysis and supporting evidence<br>
                • Include relevant case law and regulatory citations<br>
                • Recommend expert opinions and additional documentation
            </div>
            """, unsafe_allow_html=True)
            
            with st.form("comprehensive_rfe_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    petitioner = st.text_input("Petitioner/Employer", help="Name of petitioning individual or company")
                    beneficiary = st.text_input("Beneficiary", help="Name of beneficiary (if different from petitioner)")
                    position = st.text_input("Position/Role", help="Job title or role (if applicable)")
                    
                with col2:
                    receipt_number = st.text_input("Receipt Number", help="USCIS receipt number")
                    rfe_date = st.date_input("RFE Date", help="Date RFE was issued")
                    response_deadline = st.date_input("Response Deadline", help="Deadline to respond to RFE")
                
                rfe_issues = st.text_area(
                    "RFE Issues Raised", 
                    height=120,
                    help="Detailed description of all issues raised in the RFE"
                )
                
                additional_details = st.text_area(
                    "Additional Case Details",
                    height=100, 
                    help="Any additional relevant information about the case"
                )
                
                submit_rfe = st.form_submit_button("🚀 Generate Comprehensive RFE Response", type="primary")
                
                if submit_rfe:
                    if rfe_issues:
                        case_details = {
                            "petitioner": petitioner,
                            "beneficiary": beneficiary,
                            "position": position,
                            "receipt_number": receipt_number,
                            "rfe_issues": rfe_issues,
                            "additional_details": additional_details
                        }
                        
                        with st.spinner("Generating comprehensive immigration response..."):
                            visa_code = visa_category.split(" - ")[0] if " - " in visa_category else visa_category
                            response = generate_comprehensive_immigration_response("RFE Response", visa_code, case_details)
                            
                            if response:
                                st.subheader(f"📄 {case_type} - {visa_category}")
                                st.markdown(f"""
                                <div class="professional-card">
                                    {response}
                                </div>
                                """, unsafe_allow_html=True)
                                
                                # Store response in session state for download
                                st.session_state['latest_response'] = {
                                    'content': response,
                                    'type': case_type,
                                    'category': visa_category
                                }
                    else:
                        st.warning("Please describe the RFE issues before generating a response.")
            
            # Download button outside form
            if 'latest_response' in st.session_state:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"Immigration_Response_{st.session_state['latest_response']['type'].replace(' ', '_')}_{timestamp}.txt"
                download_content = f"LAWTRAX IMMIGRATION SERVICES\n{st.session_state['latest_response']['type'].upper()} - {st.session_state['latest_response']['category']}\n{'='*80}\n\n{st.session_state['latest_response']['content']}\n\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                st.download_button(
                    "📥 Download Response",
                    data=download_content,
                    file_name=filename,
                    mime="text/plain",
                    key="download_rfe_response"
                )
        
        elif case_type in ["Initial Petition Strategy", "General Immigration Guidance"]:
            st.markdown("""
            <div class="info-box">
                <strong>💡 Strategic Immigration Guidance:</strong> Get comprehensive legal strategy and guidance 
                for initial petitions, case planning, and general immigration matters.
            </div>
            """, unsafe_allow_html=True)
            
            with st.form("immigration_guidance_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    client_name = st.text_input("Client Name")
                    case_priority = st.selectbox("Case Priority", ["Standard", "Premium Processing", "Urgent"])
                    
                with col2:
                    filing_deadline = st.date_input("Target Filing Date", help="Desired filing date")
                    budget_range = st.selectbox("Budget Range", ["Under $5K", "$5K-$10K", "$10K-$25K", "$25K+", "No Limit"])
                
                immigration_question = st.text_area(
                    "Immigration Question or Case Details",
                    height=150,
                    placeholder="Describe your immigration question, case scenario, or strategic planning needs...",
                    help="Provide detailed information about the immigration matter"
                )
                
                specific_concerns = st.text_area(
                    "Specific Legal Concerns or Challenges",
                    height=100,
                    help="Any specific legal issues, potential problems, or areas of concern"
                )
                
                submit_guidance = st.form_submit_button("🔍 Get Immigration Guidance", type="primary")
                
                if submit_guidance:
                    if immigration_question:
                        case_details = {
                            "client": client_name,
                            "priority": case_priority,
                            "question": immigration_question,
                            "concerns": specific_concerns,
                            "details": f"Priority: {case_priority}, Budget: {budget_range}, Deadline: {filing_deadline}"
                        }
                        
                        with st.spinner("Analyzing immigration matter and generating guidance..."):
                            visa_code = visa_category.split(" - ")[0] if " - " in visa_category else visa_category
                            response = generate_comprehensive_immigration_response(case_type, visa_code, case_details)
                            
                            if response:
                                st.subheader(f"📋 {case_type} - {visa_category}")
                                st.markdown(f"""
                                <div class="professional-card">
                                    {response}
                                </div>
                                """, unsafe_allow_html=True)
                                
                                # Store response for download
                                st.session_state['latest_guidance'] = {
                                    'content': response,
                                    'client': client_name,
                                    'category': visa_category,
                                    'type': case_type
                                }
                    else:
                        st.warning("Please provide your immigration question or case details.")
            
            # Download button outside form
            if 'latest_guidance' in st.session_state:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"Immigration_Guidance_{timestamp}.txt"
                download_content = f"LAWTRAX IMMIGRATION SERVICES\n{st.session_state['latest_guidance']['type'].upper()}\n{'='*60}\n\nCase: {st.session_state['latest_guidance']['category']}\nClient: {st.session_state['latest_guidance']['client']}\n\n{st.session_state['latest_guidance']['content']}\n\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                st.download_button(
                    "📥 Download Guidance",
                    data=download_content,
                    file_name=filename,
                    mime="text/plain",
                    key="download_guidance"
                )
        
        else:  # Other case types (Motions, Appeals, etc.)
            st.markdown("""
            <div class="rfe-box">
                <strong>⚖️ Advanced Immigration Matters:</strong> Professional assistance with complex immigration 
                cases including motions, appeals, removal defense, and specialized applications.
            </div>
            """, unsafe_allow_html=True)
            
            with st.form("advanced_immigration_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    case_number = st.text_input("Case/Receipt Number")
                    court_venue = st.text_input("Immigration Court/USCIS Office", help="Venue handling the case")
                    opposing_counsel = st.text_input("Government Attorney/USCIS Officer", help="If known")
                    
                with col2:
                    case_status = st.selectbox("Current Case Status", 
                                             ["Pending", "Denied", "Approved with Conditions", "In Removal Proceedings", "Other"])
                    deadline = st.date_input("Filing Deadline")
                    priority_level = st.selectbox("Priority Level", ["Standard", "Expedite Requested", "Emergency"])
                
                case_background = st.text_area(
                    "Case Background and Current Situation",
                    height=120,
                    help="Detailed background of the immigration case and current status"
                )
                
                legal_issues = st.text_area(
                    "Legal Issues and Arguments",
                    height=120,
                    help="Specific legal issues, arguments to be made, or grounds for relief"
                )
                
                submit_advanced = st.form_submit_button(f"🚀 Generate {case_type}", type="primary")
                
                if submit_advanced:
                    if case_background and legal_issues:
                        case_details = {
                            "case_number": case_number,
                            "court_venue": court_venue,
                            "case_status": case_status,
                            "background": case_background,
                            "legal_issues": legal_issues,
                            "details": f"Priority: {priority_level}, Deadline: {deadline}"
                        }
                        
                        with st.spinner(f"Generating {case_type.lower()}..."):
                            visa_code = visa_category.split(" - ")[0] if " - " in visa_category else visa_category
                            response = generate_comprehensive_immigration_response(case_type, visa_code, case_details)
                            
                            if response:
                                st.subheader(f"⚖️ {case_type} - {visa_category}")
                                st.markdown(f"""
                                <div class="professional-card">
                                    {response}
                                </div>
                                """, unsafe_allow_html=True)
                                
                                # Store response for download
                                st.session_state['latest_advanced_document'] = {
                                    'content': response,
                                    'type': case_type,
                                    'category': visa_category,
                                    'case_number': case_number
                                }
                    else:
                        st.warning("Please provide case background and legal issues.")
            
            # Download button outside form
            if 'latest_advanced_document' in st.session_state:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{st.session_state['latest_advanced_document']['type'].replace(' ', '_')}_{timestamp}.txt"
                download_content = f"LAWTRAX IMMIGRATION SERVICES\n{st.session_state['latest_advanced_document']['type'].upper()}\n{'='*60}\n\nCase: {st.session_state['latest_advanced_document']['category']}\nCase Number: {st.session_state['latest_advanced_document']['case_number']}\n\n{st.session_state['latest_advanced_document']['content']}\n\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                st.download_button(
                    "📥 Download Document",
                    data=download_content,
                    file_name=filename,
                    mime="text/plain",
                    key="download_advanced_document"
                )
        
        st.markdown("</div>", unsafe_allow_html=True)

    with tab3:
        st.markdown("<div class='tab-content'>", unsafe_allow_html=True)
        st.subheader("📝 Expert Opinion & Support Letter Generator")
        
        st.markdown("""
        <div class="info-box">
            <strong>💡 Expert Opinion Services:</strong> Generate professional expert opinion letters, support letters, 
            and evaluations for any type of US immigration case. Covers all visa categories from employment-based 
            to family-based to special immigrant categories.
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            letter_type = st.selectbox(
                "Select Expert Opinion Type:",
                [
                    "Position/Job Expert Opinion",
                    "Beneficiary Qualifications Expert Opinion", 
                    "Industry Expert Opinion",
                    "Extraordinary Ability Expert Opinion",
                    "Academic Credential Evaluation",
                    "Country Conditions Expert Opinion",
                    "Medical Expert Opinion",
                    "Business Valuation Expert Opinion",
                    "Cultural/Religious Expert Opinion",
                    "General Support Letter"
                ],
                help="Choose the type of expert opinion or support letter needed"
            )
        
        with col2:
            # Expert visa category selection
            expert_visa_categories = []
            for main_cat, subcats in US_VISA_CATEGORIES.items():
                for subcat, visas in subcats.items():
                    for visa_code, visa_name in visas.items():
                        expert_visa_categories.append(f"{visa_code} - {visa_name}")
            
            expert_visa_category = st.selectbox(
                "Related Visa Type:",
                ["General Immigration Matter"] + sorted(expert_visa_categories),
                help="Select the visa type this expert opinion relates to"
            )
        
        if letter_type in ["Position/Job Expert Opinion", "Industry Expert Opinion"]:
            st.markdown("""
            <div class="info-box">
                <strong>💼 Position/Industry Expert Opinion:</strong> Generate expert opinions from qualified 
                industry professionals regarding job requirements, industry standards, and position complexity.
            </div>
            """, unsafe_allow_html=True)
            
            with st.form("position_expert_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    expert_name = st.text_input("Expert Name")
                    expert_title = st.text_input("Expert Title/Position")
                    expert_company = st.text_input("Expert Company/Organization")
                    expert_credentials = st.text_area("Expert Credentials & Experience", height=80)
                    
                with col2:
                    position_title = st.text_input("Position Being Evaluated")
                    company_name = st.text_input("Company/Employer")
                    industry_field = st.text_input("Industry/Field")
                    job_duties = st.text_area("Position Duties & Requirements", height=80)
                
                opinion_focus = st.text_area(
                    "Specific Issues for Expert to Address",
                    height=100,
                    help="What specific aspects should the expert opinion focus on?"
                )
                
                submit_position_expert = st.form_submit_button("📝 Generate Position Expert Opinion", type="primary")
                
                if submit_position_expert and all([expert_name, position_title, opinion_focus]):
                    expert_case_details = {
                        "expert_name": expert_name,
                        "expert_title": expert_title,
                        "expert_company": expert_company,
                        "expert_credentials": expert_credentials,
                        "position": position_title,
                        "company": company_name,
                        "industry": industry_field,
                        "job_duties": job_duties,
                        "opinion_focus": opinion_focus
                    }
                    
                    with st.spinner("Generating expert opinion letter..."):
                        letter = generate_expert_opinion_letter("Position Expert Opinion", expert_case_details)
                        if letter:
                            st.subheader("📝 Position Expert Opinion Letter")
                            st.markdown(f"""
                            <div class="professional-card">
                                {letter}
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Store for download
                            st.session_state['latest_expert_opinion'] = {
                                'content': letter,
                                'type': 'Position_Expert_Opinion',
                                'expert': expert_name
                            }
            
            # Download button outside form
            if 'latest_expert_opinion' in st.session_state:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{st.session_state['latest_expert_opinion']['type']}_{timestamp}.txt"
                download_content = f"LAWTRAX IMMIGRATION SERVICES\n{st.session_state['latest_expert_opinion']['type'].replace('_', ' ').upper()}\n{'='*60}\n\n{st.session_state['latest_expert_opinion']['content']}\n\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                st.download_button(
                    "📥 Download Expert Opinion",
                    data=download_content,
                    file_name=filename,
                    mime="text/plain",
                    key="download_expert_opinion"
                )
        
        elif letter_type == "Extraordinary Ability Expert Opinion":
            st.markdown("""
            <div class="info-box">
                <strong>🌟 Extraordinary Ability Expert Opinion:</strong> Generate expert opinions for O-1, EB-1A, 
                and other extraordinary ability cases from recognized peers in the field.
            </div>
            """, unsafe_allow_html=True)
            
            with st.form("extraordinary_expert_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    expert_name = st.text_input("Expert Name")
                    expert_credentials = st.text_area("Expert Qualifications & Recognition", height=100)
                    field_of_expertise = st.text_input("Field of Expertise")
                    
                with col2:
                    beneficiary_name = st.text_input("Beneficiary Name")
                    beneficiary_field = st.text_input("Beneficiary's Field")
                    achievements = st.text_area("Beneficiary's Key Achievements", height=100)
                
                extraordinary_evidence = st.text_area(
                    "Evidence of Extraordinary Ability",
                    height=120,
                    help="Describe the evidence demonstrating extraordinary ability"
                )
                
                peer_recognition = st.text_area(
                    "Peer Recognition & Industry Impact",
                    height=100,
                    help="How is the beneficiary recognized by peers and what is their industry impact?"
                )
                
                submit_extraordinary = st.form_submit_button("📝 Generate Extraordinary Ability Expert Opinion", type="primary")
                
                if submit_extraordinary and all([expert_name, beneficiary_name, extraordinary_evidence]):
                    expert_case_details = {
                        "expert_name": expert_name,
                        "expert_credentials": expert_credentials,
                        "field": field_of_expertise,
                        "beneficiary_name": beneficiary_name,
                        "beneficiary_field": beneficiary_field,
                        "achievements": achievements,
                        "evidence": extraordinary_evidence,
                        "recognition": peer_recognition
                    }
                    
                    with st.spinner("Generating extraordinary ability expert opinion..."):
                        letter = generate_expert_opinion_letter("Extraordinary Ability Expert Opinion", expert_case_details)
                        if letter:
                            st.subheader("📝 Extraordinary Ability Expert Opinion Letter")
                            st.markdown(f"""
                            <div class="professional-card">
                                {letter}
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Store for download
                            st.session_state['latest_expert_opinion'] = {
                                'content': letter,
                                'type': 'Extraordinary_Ability_Expert_Opinion',
                                'expert': expert_name
                            }
            
            # Download button for extraordinary ability opinion
            if 'latest_expert_opinion' in st.session_state and st.session_state['latest_expert_opinion']['type'] == 'Extraordinary_Ability_Expert_Opinion':
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"Extraordinary_Ability_Expert_Opinion_{timestamp}.txt"
                download_content = f"LAWTRAX IMMIGRATION SERVICES\nEXTRAORDINARY ABILITY EXPERT OPINION\n{'='*60}\n\n{st.session_state['latest_expert_opinion']['content']}\n\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                st.download_button(
                    "📥 Download Expert Opinion",
                    data=download_content,
                    file_name=filename,
                    mime="text/plain",
                    key="download_extraordinary_opinion"
                )
        
        elif letter_type == "Country Conditions Expert Opinion":
            st.markdown("""
            <div class="info-box">
                <strong>🌍 Country Conditions Expert Opinion:</strong> Generate expert opinions on country conditions 
                for asylum, withholding of removal, CAT, and other protection-based cases.
            </div>
            """, unsafe_allow_html=True)
            
            with st.form("country_conditions_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    expert_name = st.text_input("Expert Name")
                    expert_qualifications = st.text_area("Expert Qualifications & Experience", height=80)
                    country_of_concern = st.text_input("Country of Concern")
                    
                with col2:
                    beneficiary_profile = st.text_area("Beneficiary Profile", height=80, 
                                                     help="Demographics, background, political/social profile")
                    time_period = st.text_input("Relevant Time Period", help="Time period for country conditions")
                
                conditions_issues = st.text_area(
                    "Specific Country Conditions Issues",
                    height=120,
                    help="Political, social, economic, or security conditions to address"
                )
                
                persecution_risk = st.text_area(
                    "Risk Assessment",
                    height=100,
                    help="Assessment of risk to beneficiary based on profile and country conditions"
                )
                
                submit_country = st.form_submit_button("📝 Generate Country Conditions Expert Opinion", type="primary")
                
                if submit_country and all([expert_name, country_of_concern, conditions_issues]):
                    expert_case_details = {
                        "expert_name": expert_name,
                        "expert_qualifications": expert_qualifications,
                        "country": country_of_concern,
                        "beneficiary_profile": beneficiary_profile,
                        "time_period": time_period,
                        "conditions": conditions_issues,
                        "risk_assessment": persecution_risk
                    }
                    
                    with st.spinner("Generating country conditions expert opinion..."):
                        letter = generate_expert_opinion_letter("Country Conditions Expert Opinion", expert_case_details)
                        if letter:
                            st.subheader("📝 Country Conditions Expert Opinion Letter")
                            st.markdown(f"""
                            <div class="professional-card">
                                {letter}
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Store for download
                            st.session_state['latest_expert_opinion'] = {
                                'content': letter,
                                'type': 'Country_Conditions_Expert_Opinion',
                                'expert': expert_name
                            }
            
            # Download button for country conditions opinion
            if 'latest_expert_opinion' in st.session_state and st.session_state['latest_expert_opinion']['type'] == 'Country_Conditions_Expert_Opinion':
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"Country_Conditions_Expert_Opinion_{timestamp}.txt"
                download_content = f"LAWTRAX IMMIGRATION SERVICES\nCOUNTRY CONDITIONS EXPERT OPINION\n{'='*60}\n\n{st.session_state['latest_expert_opinion']['content']}\n\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                st.download_button(
                    "📥 Download Expert Opinion",
                    data=download_content,
                    file_name=filename,
                    mime="text/plain",
                    key="download_country_opinion"
                )
        
        else:  # General expert opinion types
            st.markdown("""
            <div class="info-box">
                <strong>📋 General Expert Opinion:</strong> Generate customized expert opinions and support letters 
                for any immigration matter requiring professional evaluation or endorsement.
            </div>
            """, unsafe_allow_html=True)
            
            with st.form("general_expert_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    expert_name = st.text_input("Expert Name")
                    expert_title = st.text_input("Expert Title/Position")
                    expert_organization = st.text_input("Expert Organization")
                    
                with col2:
                    subject_matter = st.text_input("Subject Matter/Focus")
                    case_context = st.text_input("Case Context", help="Brief description of the immigration case")
                
                expert_qualifications = st.text_area(
                    "Expert Qualifications & Credentials",
                    height=100,
                    help="Detailed qualifications that establish expert's credibility"
                )
                
                opinion_scope = st.text_area(
                    "Scope of Expert Opinion",
                    height=120,
                    help="What specific issues should the expert address in their opinion?"
                )
                
                supporting_facts = st.text_area(
                    "Supporting Facts & Evidence",
                    height=100,
                    help="Key facts and evidence the expert should reference"
                )
                
                submit_general_expert = st.form_submit_button("📝 Generate Expert Opinion", type="primary")
                
                if submit_general_expert and all([expert_name, subject_matter, opinion_scope]):
                    expert_case_details = {
                        "expert_name": expert_name,
                        "expert_title": expert_title,
                        "expert_organization": expert_organization,
                        "expert_qualifications": expert_qualifications,
                        "subject_matter": subject_matter,
                        "case_context": case_context,
                        "opinion_scope": opinion_scope,
                        "supporting_facts": supporting_facts
                    }
                    
                    with st.spinner("Generating expert opinion letter..."):
                        letter = generate_expert_opinion_letter("General Expert Opinion", expert_case_details)
                        if letter:
                            st.subheader(f"📝 {letter_type}")
                            st.markdown(f"""
                            <div class="professional-card">
                                {letter}
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Store for download
                            st.session_state['latest_expert_opinion'] = {
                                'content': letter,
                                'type': letter_type.replace(' ', '_'),
                                'expert': expert_name
                            }
            
            # Download button for general expert opinion
            if 'latest_expert_opinion' in st.session_state and 'General' in st.session_state['latest_expert_opinion']['type']:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{st.session_state['latest_expert_opinion']['type']}_{timestamp}.txt"
                download_content = f"LAWTRAX IMMIGRATION SERVICES\n{st.session_state['latest_expert_opinion']['type'].replace('_', ' ').upper()}\n{'='*60}\n\n{st.session_state['latest_expert_opinion']['content']}\n\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                st.download_button(
                    "📥 Download Expert Opinion",
                    data=download_content,
                    file_name=filename,
                    mime="text/plain",
                    key="download_general_expert_opinion"
                )
        
        st.markdown("</div>", unsafe_allow_html=True)

    with tab4:
        st.markdown("<div class='tab-content'>", unsafe_allow_html=True)
        st.subheader("📊 Comprehensive Immigration Templates & Legal Frameworks")
        
        template_category = st.selectbox(
            "Select Template Category:",
            [
                "Non-Immigrant Visa Checklists", 
                "Immigrant Visa Checklists",
                "RFE Response Frameworks", 
                "Legal Argument Templates",
                "Motion & Appeal Templates",
                "Evidence Collection Guides",
                "Interview Preparation Guides",
                "Compliance & Documentation"
            ]
        )
        
        if template_category == "Non-Immigrant Visa Checklists":
            visa_type = st.selectbox(
                "Select Non-Immigrant Visa Type:",
                ["H-1B Specialty Occupation", "L-1 Intracompany Transferee", "O-1 Extraordinary Ability", 
                 "E-1/E-2 Treaty Investor/Trader", "TN NAFTA Professional", "F-1 Student", 
                 "B-1/B-2 Visitor", "R-1 Religious Worker", "P-1 Athlete/Entertainer"]
            )
            
            if visa_type == "H-1B Specialty Occupation":
                st.markdown("""
                <div class="professional-card">
                    <h4>✅ H-1B Specialty Occupation Filing Checklist</h4>
                    
                    <strong>📋 USCIS Forms & Fees:</strong>
                    <ul>
                        <li>Form I-129 (signed by authorized company representative)</li>
                        <li>H Classification Supplement to Form I-129</li>
                        <li>USCIS filing fee ($460) + Fraud Prevention fee ($500)</li>
                        <li>American Competitiveness fee ($750/$1,500 based on company size)</li>
                        <li>Premium Processing fee ($2,805) if requested</li>
                    </ul>
                    
                    <strong>🏢 Employer Documentation:</strong>
                    <ul>
                        <li>Certified Labor Condition Application (LCA) from DOL</li>
                        <li>Detailed support letter explaining position and requirements</li>
                        <li>Company organizational chart showing position placement</li>
                        <li>Evidence of employer's business operations and legitimacy</li>
                        <li>Job description with specific duties and education requirements</li>
                        <li>Corporate documents (incorporation, business license)</li>
                    </ul>
                    
                    <strong>👤 Beneficiary Documentation:</strong>
                    <ul>
                        <li>Copy of passport biographical page</li>
                        <li>Current immigration status documentation</li>
                        <li>Educational credentials and evaluation</li>
                        <li>Resume/CV with detailed work history</li>
                        <li>Experience letters from previous employers</li>
                        <li>Professional licenses/certifications if applicable</li>
                    </ul>
                    
                    <strong>🎯 Specialty Occupation Evidence:</strong>
                    <ul>
                        <li>Industry standards documentation</li>
                        <li>Comparable job postings requiring degree</li>
                        <li>Expert opinion letter (recommended)</li>
                        <li>Professional association requirements</li>
                        <li>Industry salary surveys</li>
                        <li>Academic research on position requirements</li>
                    </ul>
                </div>
                """, unsafe_allow_html=True)
                
            elif visa_type == "O-1 Extraordinary Ability":
                st.markdown("""
                <div class="professional-card">
                    <h4>✅ O-1 Extraordinary Ability Filing Checklist</h4>
                    
                    <strong>📋 USCIS Forms & Documentation:</strong>
                    <ul>
                        <li>Form I-129 with O Classification Supplement</li>
                        <li>Consultation from appropriate peer group or labor organization</li>
                        <li>Copy of contract or summary of oral agreement</li>
                        <li>Detailed itinerary of events/activities</li>
                    </ul>
                    
                    <strong>🌟 Evidence of Extraordinary Ability (O-1A - Sciences/Education/Business/Athletics):</strong>
                    <ul>
                        <li>Major awards or prizes for excellence</li>
                        <li>Membership in exclusive associations requiring outstanding achievements</li>
                        <li>Published material about beneficiary in professional publications</li>
                        <li>Evidence of original contributions of major significance</li>
                        <li>Authorship of scholarly articles in professional journals</li>
                        <li>High salary or remuneration compared to others in field</li>
                        <li>Critical employment in distinguished organizations</li>
                        <li>Commercial successes in performing arts</li>
                    </ul>
                    
                    <strong>🎭 Evidence for O-1B (Arts/Motion Pictures/TV):</strong>
                    <ul>
                        <li>Leading/starring roles in distinguished productions</li>
                        <li>Critical reviews and recognition in major newspapers</li>
                        <li>Commercial or critically acclaimed successes</li>
                        <li>Recognition from industry organizations</li>
                        <li>High salary compared to others in field</li>
                    </ul>
                    
                    <strong>📄 Supporting Documentation:</strong>
                    <ul>
                        <li>Detailed consultation letter from peer group</li>
                        <li>Expert opinion letters from industry professionals</li>
                        <li>Media coverage and press articles</li>
                        <li>Awards, certificates, and recognition letters</li>
                        <li>Employment verification and salary documentation</li>
                    </ul>
                </div>
                """, unsafe_allow_html=True)
        
        elif template_category == "Immigrant Visa Checklists":
            immigrant_type = st.selectbox(
                "Select Green Card/Immigrant Visa Category:",
                ["EB-1 Priority Workers", "EB-2 Advanced Degree/NIW", "EB-3 Skilled Workers", 
                 "EB-5 Investor Green Card", "Family-Based (Immediate Relatives)", "Family-Based (Preference Categories)", 
                 "Adjustment of Status (I-485)", "Consular Processing", "Green Card Renewal (I-90)",
                 "Removal of Conditions (I-751)", "Asylum-Based Adjustment", "Diversity Visa"]
            )
            
            if immigrant_type == "EB-1 Priority Workers":
                st.markdown("""
                <div class="professional-card">
                    <h4>✅ EB-1 Priority Worker Green Card Checklist</h4>
                    
                    <strong>📋 Form I-140 Package:</strong>
                    <ul>
                        <li>Form I-140 (signed by petitioner)</li>
                        <li>USCIS filing fee ($2,805)</li>
                        <li>Premium Processing fee ($2,805) if requested</li>
                        <li>Supporting evidence based on subcategory</li>
                    </ul>
                    
                    <strong>🌟 EB-1A Extraordinary Ability Requirements:</strong>
                    <ul>
                        <li>Evidence of sustained national/international acclaim</li>
                        <li>One-time major international award OR</li>
                        <li>At least 3 of the 10 regulatory criteria:</li>
                        <li>&nbsp;&nbsp;• Major awards/prizes for excellence</li>
                        <li>&nbsp;&nbsp;• Membership in exclusive associations</li>
                        <li>&nbsp;&nbsp;• Published material about beneficiary</li>
                        <li>&nbsp;&nbsp;• Judging work of others in field</li>
                        <li>&nbsp;&nbsp;• Original contributions of major significance</li>
                        <li>&nbsp;&nbsp;• Scholarly articles by beneficiary</li>
                        <li>&nbsp;&nbsp;• Critical employment in distinguished organizations</li>
                        <li>&nbsp;&nbsp;• High salary/remuneration</li>
                        <li>&nbsp;&nbsp;• Commercial successes in performing arts</li>
                        <li>&nbsp;&nbsp;• Display of work at artistic exhibitions</li>
                    </ul>
                    
                    <strong>👨‍🏫 EB-1B Outstanding Professor/Researcher:</strong>
                    <ul>
                        <li>Evidence of international recognition</li>
                        <li>At least 3 years experience in teaching/research</li>
                        <li>Job offer for tenure track or permanent research position</li>
                        <li>At least 2 of 6 regulatory criteria</li>
                        <li>Major awards for outstanding achievements</li>
                        <li>Membership in associations requiring outstanding achievements</li>
                        <li>Published material written by others about beneficiary's work</li>
                        <li>Participation as judge of others' work</li>
                        <li>Original scientific or scholarly research contributions</li>
                        <li>Authorship of scholarly books or articles</li>
                    </ul>
                    
                    <strong>🏢 EB-1C Multinational Manager/Executive:</strong>
                    <ul>
                        <li>Evidence of qualifying employment abroad (1 year in past 3)</li>
                        <li>Proof of qualifying relationship between entities</li>
                        <li>Evidence of managerial/executive capacity abroad and in US</li>
                        <li>Job offer for managerial/executive position in US</li>
                        <li>Corporate documents showing relationship</li>
                        <li>Organizational charts and business operations evidence</li>
                    </ul>
                </div>
                """, unsafe_allow_html=True)
            
            elif immigrant_type == "EB-5 Investor Green Card":
                st.markdown("""
                <div class="professional-card">
                    <h4>✅ EB-5 Investor Green Card Checklist</h4>
                    
                    <strong>📋 Form I-526E Package (Regional Center):</strong>
                    <ul>
                        <li>Form I-526E (EB-5 Immigrant Petition by Regional Center Investor)</li>
                        <li>USCIS filing fee ($11,160)</li>
                        <li>Evidence of qualifying investment ($800,000 or $1,050,000)</li>
                        <li>Source of funds documentation</li>
                    </ul>
                    
                    <strong>💰 Investment Requirements:</strong>
                    <ul>
                        <li>Minimum investment: $1,050,000 (general) or $800,000 (TEA)</li>
                        <li>Investment in new commercial enterprise</li>
                        <li>Investment at risk and subject to loss</li>
                        <li>Investment must create at least 10 full-time jobs for US workers</li>
                    </ul>
                    
                    <strong>📄 Source of Funds Documentation:</strong>
                    <ul>
                        <li>Tax returns for past 5 years</li>
                        <li>Bank statements and financial records</li>
                        <li>Business ownership documentation</li>
                        <li>Property sale agreements and appraisals</li>
                        <li>Gift documentation (if applicable)</li>
                        <li>Loan agreements and collateral documentation</li>
                    </ul>
                    
                    <strong>🏢 Business Plan Requirements:</strong>
                    <ul>
                        <li>Comprehensive business plan with job creation projections</li>
                        <li>Market analysis and financial projections</li>
                        <li>Economic impact study</li>
                        <li>Management structure and operational plan</li>
                    </ul>
                    
                    <strong>⏰ Process Timeline:</strong>
                    <ul>
                        <li>I-526E approval: 12-18 months</li>
                        <li>Conditional Green Card (I-485 or Consular Processing)</li>
                        <li>I-829 removal of conditions: Filed 90 days before 2-year anniversary</li>
                        <li>Permanent Green Card upon I-829 approval</li>
                    </ul>
                </div>
                """, unsafe_allow_html=True)
            
            elif immigrant_type == "Adjustment of Status (I-485)":
                st.markdown("""
                <div class="professional-card">
                    <h4>✅ Adjustment of Status (I-485) Checklist</h4>
                    
                    <strong>📋 Required Forms and Fees:</strong>
                    <ul>
                        <li>Form I-485 (Application to Adjust Status)</li>
                        <li>Filing fee: $1,440 (includes biometrics)</li>
                        <li>Medical examination (Form I-693)</li>
                        <li>Form I-864 Affidavit of Support (if required)</li>
                    </ul>
                    
                    <strong>👤 Supporting Documentation:</strong>
                    <ul>
                        <li>Copy of birth certificate</li>
                        <li>Copy of passport biographical pages</li>
                        <li>Copy of current immigration status documents</li>
                        <li>Two passport-style photographs</li>
                        <li>Form I-94 arrival/departure record</li>
                        <li>Copy of approved immigrant petition (I-130, I-140, etc.)</li>
                    </ul>
                    
                    <strong>🏥 Medical Examination Requirements:</strong>
                    <ul>
                        <li>Completed by USCIS-designated civil surgeon</li>
                        <li>Vaccination records and requirements</li>
                        <li>Physical examination and medical history</li>
                        <li>Tuberculosis screening and blood tests</li>
                        <li>Mental health evaluation if indicated</li>
                    </ul>
                    
                    <strong>💰 Affidavit of Support (I-864) Requirements:</strong>
                    <ul>
                        <li>Required for family-based and some employment cases</li>
                        <li>Sponsor must meet income requirements (125% of poverty guidelines)</li>
                        <li>Tax returns for most recent 3 years</li>
                        <li>Employment verification letter</li>
                        <li>Bank statements and asset documentation</li>
                    </ul>
                    
                    <strong>⚠️ Inadmissibility Issues:</strong>
                    <ul>
                        <li>Criminal history disclosure and documentation</li>
                        <li>Immigration violations and unlawful presence</li>
                        <li>Public charge considerations</li>
                        <li>Waiver applications if needed (I-601, I-601A)</li>
                    </ul>
                    
                    <strong>🔄 Work Authorization:</strong>
                    <ul>
                        <li>Form I-765 can be filed concurrently</li>
                        <li>No additional fee when filed with I-485</li>
                        <li>Employment authorization typically granted while I-485 pending</li>
                    </ul>
                </div>
                """, unsafe_allow_html=True)
            
            elif immigrant_type == "Green Card Renewal (I-90)":
                st.markdown("""
                <div class="professional-card">
                    <h4>✅ Green Card Renewal (I-90) Checklist</h4>
                    
                    <strong>📋 When to File I-90:</strong>
                    <ul>
                        <li>Green card expired or will expire within 6 months</li>
                        <li>Green card lost, stolen, or damaged</li>
                        <li>Card contains incorrect information</li>
                        <li>Name change since card was issued</li>
                        <li>Received card but never received it</li>
                    </ul>
                    
                    <strong>💳 Form I-90 Requirements:</strong>
                    <ul>
                        <li>Form I-90 (Application to Replace Permanent Resident Card)</li>
                        <li>Filing fee: $540</li>
                        <li>Biometrics fee: $85</li>
                        <li>Copy of current or expired green card (if available)</li>
                    </ul>
                    
                    <strong>📄 Supporting Documentation:</strong>
                    <ul>
                        <li>Copy of green card (front and back)</li>
                        <li>Government-issued photo identification</li>
                        <li>Legal name change documents (if applicable)</li>
                        <li>Police report (if card was stolen)</li>
                        <li>Two passport-style photographs</li>
                    </ul>
                    
                    <strong>⏰ Processing Information:</strong>
                    <ul>
                        <li>Processing time: 8-13 months</li>
                        <li>Receipt notice serves as temporary evidence</li>
                        <li>ADIT stamp available if immediate travel needed</li>
                        <li>Biometrics appointment required</li>
                    </ul>
                    
                    <strong>🚨 Special Situations:</strong>
                    <ul>
                        <li>Conditional residents must file I-751, not I-90</li>
                        <li>Commuter green card holders have special requirements</li>
                        <li>Cards damaged by USCIS error may be replaced for free</li>
                    </ul>
                </div>
                """, unsafe_allow_html=True)
            
            elif immigrant_type == "Removal of Conditions (I-751)":
                st.markdown("""
                <div class="professional-card">
                    <h4>✅ Removal of Conditions (I-751) Checklist</h4>
                    
                    <strong>📋 When to File I-751:</strong>
                    <ul>
                        <li>Must file within 90 days before conditional green card expires</li>
                        <li>Applies to spouses of US citizens/LPRs who received 2-year conditional cards</li>
                        <li>Conditional residents based on marriage</li>
                        <li>Child derivatives of conditional residents</li>
                    </ul>
                    
                    <strong>💑 Joint Filing with Spouse:</strong>
                    <ul>
                        <li>Form I-751 (both spouses sign)</li>
                        <li>Filing fee: $760</li>
                        <li>Biometrics fee: $85</li>
                        <li>Evidence of bona fide marriage</li>
                    </ul>
                    
                    <strong>📄 Evidence of Bona Fide Marriage:</strong>
                    <ul>
                        <li>Joint bank account statements</li>
                        <li>Joint lease agreements or mortgage documents</li>
                        <li>Joint utility bills and insurance policies</li>
                        <li>Joint tax returns</li>
                        <li>Birth certificates of children born to marriage</li>
                        <li>Photos together with family and friends</li>
                        <li>Affidavits from friends and family</li>
                        <li>Travel documents showing joint trips</li>
                    </ul>
                    
                    <strong>⚠️ Waiver Situations (Filing Alone):</strong>
                    <ul>
                        <li>Divorce or annulment (good faith marriage)</li>
                        <li>Domestic violence or extreme cruelty</li>
                        <li>Extreme hardship if removed from US</li>
                        <li>Death of US citizen spouse</li>
                    </ul>
                    
                    <strong>🔄 Process Timeline:</strong>
                    <ul>
                        <li>File within 90 days of card expiration</li>
                        <li>Receipt notice extends status for 24 months</li>
                        <li>Processing time: 12-18 months</li>
                        <li>Interview may be required</li>
                        <li>Approval results in 10-year green card</li>
                    </ul>
                </div>
                """, unsafe_allow_html=True)
            
        elif template_category == "RFE Response Frameworks":
            rfe_framework = st.selectbox(
                "Select RFE Response Framework:",
                ["Specialty Occupation Framework", "Extraordinary Ability Framework", 
                 "Beneficiary Qualifications Framework", "Employer-Employee Relationship", 
                 "Ability to Pay Framework", "Bona Fide Marriage Framework"]
            )
            
            if rfe_framework == "Specialty Occupation Framework":
                st.markdown("""
                <div class="professional-card">
                    <h4>🎯 Specialty Occupation RFE Response Framework</h4>
                    
                    <strong>I. Legal Framework Analysis</strong>
                    <ul>
                        <li>8 CFR 214.2(h)(4)(iii)(A) - Specialty occupation definition</li>
                        <li>INA Section 214(i)(1) - H-1B requirements</li>
                        <li>USCIS Policy Manual guidance</li>
                        <li>Relevant case law and precedents</li>
                    </ul>
                    
                    <strong>II. Four-Prong Analysis Structure</strong>
                    
                    <strong>Prong 1: Degree Normally Required by Industry</strong>
                    <ul>
                        <li>Industry surveys and employment data</li>
                        <li>Professional association standards</li>
                        <li>Academic research on industry requirements</li>
                        <li>Government labor statistics and reports</li>
                    </ul>
                    
                    <strong>Prong 2: Degree Requirement Common Among Similar Employers</strong>
                    <ul>
                        <li>Comparative job postings from similar companies</li>
                        <li>Industry hiring practices documentation</li>
                        <li>Professional networking site analysis</li>
                        <li>Competitor analysis and benchmarking</li>
                    </ul>
                    
                    <strong>Prong 3: Employer Normally Requires Degree</strong>
                    <ul>
                        <li>Company hiring policies and procedures</li>
                        <li>Historical hiring data for similar positions</li>
                        <li>Job descriptions and qualification requirements</li>
                        <li>Organizational structure and reporting relationships</li>
                    </ul>
                    
                    <strong>Prong 4: Position Nature is Specialized and Complex</strong>
                    <ul>
                        <li>Detailed analysis of job duties and responsibilities</li>
                        <li>Technical complexity and specialization requirements</li>
                        <li>Independent judgment and decision-making authority</li>
                        <li>Advanced knowledge and skills application</li>
                    </ul>
                    
                    <strong>III. Supporting Evidence Strategy</strong>
                    <ul>
                        <li>Expert opinion letters from industry professionals</li>
                        <li>Academic and professional literature citations</li>
                        <li>Industry standards and best practices documentation</li>
                        <li>Professional certification and licensing requirements</li>
                    </ul>
                </div>
                """, unsafe_allow_html=True)
        
        elif template_category == "Legal Argument Templates":
            st.markdown("""
            <div class="professional-card">
                <h4>⚖️ Legal Argument Templates & Strategies</h4>
                
                <strong>🎯 Burden of Proof Arguments</strong>
                <ul>
                    <li>Preponderance of evidence standard in immigration cases</li>
                    <li>Petitioner's burden to establish eligibility</li>
                    <li>USCIS burden to articulate specific deficiencies</li>
                    <li>Due process considerations in adjudication</li>
                </ul>
                
                <strong>📚 Statutory Interpretation Arguments</strong>
                <ul>
                    <li>Plain meaning rule application</li>
                    <li>Legislative intent and Congressional purpose</li>
                    <li>Agency deference limitations (Chevron doctrine)</li>
                    <li>Constitutional interpretation principles</li>
                </ul>
                
                <strong>🏛️ Administrative Law Arguments</strong>
                <ul>
                    <li>Arbitrary and capricious standard review</li>
                    <li>Agency policy consistency requirements</li>
                    <li>Procedural due process protections</li>
                    <li>Equal protection and discrimination claims</li>
                </ul>
                
                <strong>📖 Case Law Citation Framework</strong>
                <ul>
                    <li>Supreme Court immigration precedents</li>
                    <li>Circuit court decisions and splits</li>
                    <li>BIA precedent decisions</li>
                    <li>District court persuasive authority</li>
                </ul>
                
                <strong>🔄 Factual Distinction Arguments</strong>
                <ul>
                    <li>Case-specific fact pattern analysis</li>
                    <li>Distinguishing adverse precedents</li>
                    <li>Analogizing favorable decisions</li>
                    <li>Highlighting unique circumstances</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
        
        elif template_category == "Motion & Appeal Templates":
            motion_type = st.selectbox(
                "Select Motion/Appeal Type:",
                ["Motion to Reopen", "Motion to Reconsider", "BIA Appeal Brief", 
                 "Federal Court Petition", "Emergency Motion", "Joint Motion"]
            )
            
            st.markdown(f"""
            <div class="professional-card">
                <h4>⚖️ {motion_type} Template Framework</h4>
                
                <strong>I. Jurisdictional Requirements</strong>
                <ul>
                    <li>Timeliness of filing (90-day deadline for most motions)</li>
                    <li>Proper party standing and representation</li>
                    <li>Final order requirement for appeals</li>
                    <li>Fee payment and filing procedures</li>
                </ul>
                
                <strong>II. Legal Standards</strong>
                <ul>
                    <li>{"New facts or changed country conditions (Motion to Reopen)" if "Reopen" in motion_type else ""}</li>
                    <li>{"Legal or factual error in prior decision (Motion to Reconsider)" if "Reconsider" in motion_type else ""}</li>
                    <li>{"Clear error of law or abuse of discretion (BIA Appeal)" if "BIA" in motion_type else ""}</li>
                    <li>{"Constitutional or statutory interpretation (Federal Court)" if "Federal" in motion_type else ""}</li>
                </ul>
                
                <strong>III. Argument Structure</strong>
                <ul>
                    <li>Statement of facts and procedural history</li>
                    <li>Legal standard and burden of proof</li>
                    <li>Substantive legal arguments with citations</li>
                    <li>Request for specific relief</li>
                </ul>
                
                <strong>IV. Supporting Evidence</strong>
                <ul>
                    <li>Documentary evidence and exhibits</li>
                    <li>Expert affidavits and opinions</li>
                    <li>Country condition reports and studies</li>
                    <li>Legal memoranda and precedent analysis</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("</div>", unsafe_allow_html=True)

    with tab5:
        st.markdown("<div class='tab-content'>", unsafe_allow_html=True)
        st.subheader("📚 Comprehensive US Immigration Law Resources")
        
        resource_category = st.selectbox(
            "Select Resource Category:",
            ["Statutes & Regulations", "Case Law & Precedents", "USCIS Policy & Guidance", 
             "BIA Decisions", "Federal Court Decisions", "Country Conditions Resources", 
             "Professional Development", "Research Tools & Databases"]
        )
        
        if resource_category == "Statutes & Regulations":
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("""
                <div class="professional-card">
                    <h4>📖 Immigration and Nationality Act (INA)</h4>
                    <ul>
                        <li><strong>INA § 101</strong> - Definitions</li>
                        <li><strong>INA § 201</strong> - Numerical Limitations on Individual Foreign States</li>
                        <li><strong>INA § 203</strong> - Allocation of Immigrant Visas</li>
                        <li><strong>INA § 212</strong> - Excludable Aliens (Inadmissibility)</li>
                        <li><strong>INA § 214</strong> - Admission of Nonimmigrants</li>
                        <li><strong>INA § 216</strong> - Conditional Permanent Resident Status</li>
                        <li><strong>INA § 237</strong> - Deportable Aliens (Removal)</li>
                        <li><strong>INA § 240</strong> - Removal Proceedings</li>
                        <li><strong>INA § 240A</strong> - Cancellation of Removal</li>
                        <li><strong>INA § 245</strong> - Adjustment of Status</li>
                        <li><strong>INA § 316</strong> - Requirements for Naturalization</li>
                    </ul>
                    
                    <h4>⚖️ Key Constitutional Provisions</h4>
                    <ul>
                        <li><strong>5th Amendment</strong> - Due Process (applies to all persons)</li>
                        <li><strong>14th Amendment</strong> - Equal Protection and Due Process</li>
                        <li><strong>Article I, § 8</strong> - Congressional Power over Immigration</li>
                        <li><strong>Supremacy Clause</strong> - Federal vs. State Authority</li>
                    </ul>
                </div>
                """, unsafe_allow_html=True)
                
            with col2:
                st.markdown("""
                <div class="professional-card">
                    <h4>📋 Code of Federal Regulations (CFR)</h4>
                    
                    <strong>8 CFR - Key Immigration Regulations:</strong>
                    <ul>
                        <li><strong>8 CFR 103</strong> - Immigration Benefit Procedures</li>
                        <li><strong>8 CFR 214.1</strong> - General Nonimmigrant Classifications</li>
                        <li><strong>8 CFR 214.2(b)</strong> - B-1/B-2 Visitors</li>
                        <li><strong>8 CFR 214.2(f)</strong> - F-1/F-2 Students</li>
                        <li><strong>8 CFR 214.2(h)</strong> - H Classifications</li>
                        <li><strong>8 CFR 214.2(l)</strong> - L Classifications</li>
                        <li><strong>8 CFR 214.2(o)</strong> - O Classifications</li>
                        <li><strong>8 CFR 204</strong> - Immigrant Petitions</li>
                        <li><strong>8 CFR 245</strong> - Adjustment of Status</li>
                        <li><strong>8 CFR 1003</strong> - Immigration Court Procedures</li>
                        <li><strong>8 CFR 1208</strong> - Asylum Procedures</li>
                        <li><strong>8 CFR 1240</strong> - Removal Proceedings</li>
                    </ul>
                    
                    <strong>Other Relevant CFR Sections:</strong>
                    <ul>
                        <li><strong>20 CFR 655</strong> - Labor Certification (DOL)</li>
                        <li><strong>22 CFR 40-42</strong> - Consular Processing (State Dept)</li>
                        <li><strong>28 CFR</strong> - DOJ Immigration Procedures</li>
                    </ul>
                </div>
                """, unsafe_allow_html=True)
        
        elif resource_category == "Case Law & Precedents":
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("""
                <div class="professional-card">
                    <h4>🏛️ Supreme Court Immigration Cases</h4>
                    
                    <strong>Foundational Cases:</strong>
                    <ul>
                        <li><em>Chae Chan Ping v. United States</em> (1889) - Plenary Power Doctrine</li>
                        <li><em>Yick Wo v. Hopkins</em> (1886) - Equal Protection for Non-Citizens</li>
                        <li><em>Mathews v. Diaz</em> (1976) - Federal Immigration Power</li>
                        <li><em>Landon v. Plasencia</em> (1982) - Due Process Rights</li>
                        <li><em>INS v. Chadha</em> (1983) - Legislative Veto Invalidation</li>
                    </ul>
                    
                    <strong>Modern Supreme Court Decisions:</strong>
                    <ul>
                        <li><em>Zadvydas v. Davis</em> (2001) - Indefinite Detention</li>
                        <li><em>INS v. St. Cyr</em> (2001) - Retroactivity and Habeas</li>
                        <li><em>Demore v. Kim</em> (2003) - Mandatory Detention</li>
                        <li><em>Clark v. Martinez</em> (2005) - Constitutional Avoidance</li>
                        <li><em>Kucana v. Holder</em> (2010) - Judicial Review</li>
                        <li><em>Arizona v. United States</em> (2012) - State Immigration Laws</li>
                        <li><em>Kerry v. Din</em> (2015) - Consular Processing Due Process</li>
                        <li><em>Sessions v. Morales-Santana</em> (2017) - Citizenship Gender Equality</li>
                        <li><em>Pereira v. Sessions</em> (2018) - Notice to Appear Requirements</li>
                        <li><em>Barton v. Barr</em> (2020) - Categorical Approach</li>
                    </ul>
                </div>
                """, unsafe_allow_html=True)
                
            with col2:
                st.markdown("""
                <div class="professional-card">
                    <h4>📖 Key Circuit Court Decisions</h4>
                    
                    <strong>Employment-Based Immigration:</strong>
                    <ul>
                        <li><em>Defensor v. Meissner</em> (D.C. Cir. 1999) - Specialty Occupation</li>
                        <li><em>Royal Siam Corp. v. Chertoff</em> (D.C. Cir. 2007) - H-1B Standards</li>
                        <li><em>Innova Solutions v. Baran</em> (D.C. Cir. 2018) - SOC Code Analysis</li>
                        <li><em>Kazarian v. USCIS</em> (9th Cir. 2010) - EB-1A Two-Step Analysis</li>
                    </ul>
                    
                    <strong>Removal Defense & Protection:</strong>
                    <ul>
                        <li><em>Matter of Mogharrabi</em> (9th Cir. 1987) - Persecution Definition</li>
                        <li><em>INS v. Elias-Zacarias</em> (1992) - Political Opinion</li>
                        <li><em>Cece v. Holder</em> (7th Cir. 2013) - Social Group</li>
                        <li><em>Restrepo v. McAleenan</em> (9th Cir. 2019) - Domestic Violence</li>
                    </ul>
                    
                    <strong>Family-Based Immigration:</strong>
                    <ul>
                        <li><em>Matter of Brantigan</em> (BIA 1977) - Bona Fide Marriage</li>
                        <li><em>Bark v. INS</em> (9th Cir. 1975) - Marriage Fraud</li>
                        <li><em>Adams v. Howerton</em> (9th Cir. 1980) - Same-Sex Marriage</li>
                    </ul>
                    
                    <strong>Naturalization & Citizenship:</strong>
                    <ul>
                        <li><em>Fedorenko v. United States</em> (1981) - Good Moral Character</li>
                        <li><em>Kungys v. United States</em> (1988) - Materiality Standard</li>
                        <li><em>Maslenjak v. United States</em> (2017) - Denaturalization</li>
                    </ul>
                </div>
                """, unsafe_allow_html=True)
        
        elif resource_category == "USCIS Policy & Guidance":
            st.markdown("""
            <div class="professional-card">
                <h4>📋 USCIS Policy Manual & Comprehensive Guidance</h4>
                
                <strong>🔗 USCIS Policy Manual Volumes (Complete Coverage):</strong>
                <ul>
                    <li><strong>Volume 1</strong> - General Policies and Procedures</li>
                    <li><strong>Volume 2</strong> - Nonimmigrants (H, L, O, P, E, TN, F, B, etc.)</li>
                    <li><strong>Volume 3</strong> - Humanitarian Programs (Asylum, Refugee, TPS, VAWA)</li>
                    <li><strong>Volume 4</strong> - Travel and Identity Documents</li>
                    <li><strong>Volume 5</strong> - Adoptions</li>
                    <li><strong>Volume 6</strong> - Immigrants (EB-1, EB-2, EB-3, EB-4, EB-5)</li>
                    <li><strong>Volume 7</strong> - Adjustment of Status (I-485)</li>
                    <li><strong>Volume 8</strong> - Admissibility (Grounds of Inadmissibility)</li>
                    <li><strong>Volume 9</strong> - Waivers and Other Forms of Relief</li>
                    <li><strong>Volume 10</strong> - Employment Authorization</li>
                    <li><strong>Volume 11</strong> - Travel Documents</li>
                    <li><strong>Volume 12</strong> - Citizenship and Naturalization</li>
                    <li><strong>Volume 13</strong> - Executive Orders and Delegation</li>
                    <li><strong>Volume 14</strong> - USCIS Officer Safety</li>
                </ul>
                
                <strong>📄 Critical USCIS Policy Memoranda:</strong>
                <ul>
                    <li><strong>Brand Memo (1999)</strong> - H-1B Specialty Occupation Standards</li>
                    <li><strong>Cronin Memo (2000)</strong> - H-1B Itinerary Requirements</li>
                    <li><strong>Yates Memo (2005)</strong> - H-1B Beneficiary's Education</li>
                    <li><strong>Neufeld Memo (2010)</strong> - H-1B Employer-Employee Relationship</li>
                    <li><strong>Kazarian Decision (2010)</strong> - EB-1A Two-Step Analysis</li>
                    <li><strong>Dhanasar Decision (2016)</strong> - EB-2 National Interest Waiver</li>
                    <li><strong>Matter of W-Y-U (2018)</strong> - L-1B Specialized Knowledge</li>
                    <li><strong>Public Charge Rule (2019-2021)</strong> - Inadmissibility Determinations</li>
                    <li><strong>COVID-19 Flexibility (2020-2023)</strong> - Pandemic Accommodations</li>
                </ul>
                
                <strong>🔄 Current USCIS Processing Information:</strong>
                <ul>
                    <li><strong>Processing Times</strong> - Updated monthly for all offices and forms</li>
                    <li><strong>Premium Processing</strong> - Available forms and current fees</li>
                    <li><strong>Fee Schedule</strong> - Current USCIS filing fees (updated periodically)</li>
                    <li><strong>Forms and Instructions</strong> - Latest versions with completion guides</li>
                    <li><strong>Field Office Directories</strong> - Locations and contact information</li>
                    <li><strong>Service Center Operations</strong> - Jurisdiction and specializations</li>
                </ul>
                
                <strong>📊 USCIS Data and Statistics:</strong>
                <ul>
                    <li><strong>Annual Reports</strong> - Comprehensive immigration statistics</li>
                    <li><strong>Quarterly Reports</strong> - Current processing data</li>
                    <li><strong>H-1B Cap Data</strong> - Annual registration and selection statistics</li>
                    <li><strong>Green Card Statistics</strong> - Issuance data by category</li>
                    <li><strong>Naturalization Data</strong> - Citizenship processing statistics</li>
                    <li><strong>Refugee and Asylum Statistics</strong> - Protection case data</li>
                </ul>
                
                <strong>🏢 USCIS Office Structure and Operations:</strong>
                <ul>
                    <li><strong>National Benefits Center (NBC)</strong> - Centralized processing</li>
                    <li><strong>Service Centers:</strong></li>
                    <li>&nbsp;&nbsp;• California Service Center (CSC)</li>
                    <li>&nbsp;&nbsp;• Nebraska Service Center (NSC)</li>
                    <li>&nbsp;&nbsp;• Texas Service Center (TSC)</li>
                    <li>&nbsp;&nbsp;• Vermont Service Center (VSC)</li>
                    <li>&nbsp;&nbsp;• Potomac Service Center (PSC)</li>
                    <li><strong>Field Offices</strong> - Interview and application support offices nationwide</li>
                    <li><strong>Application Support Centers (ASCs)</strong> - Biometrics collection</li>
                </ul>
                
                <strong>📋 USCIS Forms Library (Key Forms):</strong>
                <ul>
                    <li><strong>I-129</strong> - Nonimmigrant Worker Petition</li>
                    <li><strong>I-130</strong> - Family-Based Immigrant Petition</li>
                    <li><strong>I-140</strong> - Employment-Based Immigrant Petition</li>
                    <li><strong>I-485</strong> - Adjustment of Status Application</li>
                    <li><strong>I-539</strong> - Change/Extension of Nonimmigrant Status</li>
                    <li><strong>I-765</strong> - Employment Authorization Application</li>
                    <li><strong>I-131</strong> - Travel Document Application</li>
                    <li><strong>I-751</strong> - Removal of Conditions on Residence</li>
                    <li><strong>I-90</strong> - Green Card Renewal/Replacement</li>
                    <li><strong>N-400</strong> - Naturalization Application</li>
                    <li><strong>I-589</strong> - Asylum Application</li>
                    <li><strong>I-601</strong> - Inadmissibility Waiver</li>
                    <li><strong>I-601A</strong> - Provisional Unlawful Presence Waiver</li>
                    <li><strong>I-864</strong> - Affidavit of Support</li>
                    <li><strong>I-693</strong> - Medical Examination Report</li>
                </ul>
                
                <strong>💰 Current USCIS Fee Structure (2024):</strong>
                <ul>
                    <li><strong>I-129</strong> - $460 (base fee) + additional fees</li>
                    <li><strong>I-140</strong> - $2,805</li>
                    <li><strong>I-485</strong> - $1,440 (includes biometrics)</li>
                    <li><strong>Premium Processing</strong> - $2,805 (15 calendar days)</li>
                    <li><strong>Biometrics</strong> - $85 (when separate)</li>
                    <li><strong>N-400</strong> - $760</li>
                    <li><strong>Fee Waivers</strong> - Available for qualified applicants</li>
                </ul>
                
                <strong>🔍 USCIS Electronic Systems:</strong>
                <ul>
                    <li><strong>myUSCIS Account</strong> - Online case management</li>
                    <li><strong>H-1B Electronic Registration</strong> - Cap season registration</li>
                    <li><strong>USCIS Contact Center</strong> - 1-800-375-5283</li>
                    <li><strong>Case Status Online</strong> - Real-time case tracking</li>
                    <li><strong>InfoPass Appointments</strong> - Field office scheduling</li>
                    <li><strong>E-Filing System</strong> - Online form submission</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
        
        elif resource_category == "Professional Development":
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("""
                <div class="professional-card">
                    <h4>📚 Immigration Law Education & Training</h4>
                    
                    <strong>Professional Organizations:</strong>
                    <ul>
                        <li><strong>American Immigration Lawyers Association (AILA)</strong></li>
                        <li>&nbsp;&nbsp;• National conferences and workshops</li>
                        <li>&nbsp;&nbsp;• Practice advisories and liaison meetings</li>
                        <li>&nbsp;&nbsp;• Member forums and networking</li>
                        <li>&nbsp;&nbsp;• Ethics and professional responsibility</li>
                        <li><strong>American Bar Association Immigration Section</strong></li>
                        <li><strong>Federal Bar Association Immigration Law Section</strong></li>
                        <li><strong>National Immigration Forum</strong></li>
                        <li><strong>State and Local Bar Immigration Committees</strong></li>
                    </ul>
                    
                    <strong>Continuing Legal Education Providers:</strong>
                    <ul>
                        <li><strong>AILA University</strong> - Comprehensive training programs</li>
                        <li><strong>CLE International</strong> - Immigration law specialization</li>
                        <li><strong>American University</strong> - Immigration CLE courses</li>
                        <li><strong>Georgetown Law</strong> - Immigration law programs</li>
                        <li><strong>Practicing Law Institute (PLI)</strong> - Immigration track</li>
                        <li><strong>National Institute for Trial Advocacy</strong> - Immigration trial skills</li>
                    </ul>
                    
                    <strong>Certification and Specialization:</strong>
                    <ul>
                        <li><strong>Board Certification in Immigration Law</strong></li>
                        <li>&nbsp;&nbsp;• State bar certification programs</li>
                        <li>&nbsp;&nbsp;• Continuing education requirements</li>
                        <li>&nbsp;&nbsp;• Peer review and examination</li>
                        <li><strong>AILA Basic Immigration Law Course</strong></li>
                        <li><strong>Advanced Practice Specializations</strong></li>
                        <li><strong>Asylum and Refugee Law Certification</strong></li>
                    </ul>
                </div>
                """, unsafe_allow_html=True)
                
            with col2:
                st.markdown("""
                <div class="professional-card">
                    <h4>📖 Essential Immigration Law Publications</h4>
                    
                    <strong>Primary Treatises and References:</strong>
                    <ul>
                        <li><strong>Kurzban's Immigration Law Sourcebook</strong> - Annual updates</li>
                        <li><strong>Steel on Immigration Law</strong> - Comprehensive treatise</li>
                        <li><strong>Fragomen Immigration Law Handbook</strong></li>
                        <li><strong>Austin T. Fragomen Immigration Procedures Handbook</strong></li>
                        <li><strong>AILA's Immigration Law Today</strong> - Current developments</li>
                    </ul>
                    
                    <strong>Specialized Practice Guides:</strong>
                    <ul>
                        <li><strong>Business Immigration Law</strong> - Employment-based practice</li>
                        <li><strong>Family-Based Immigration Practice</strong></li>
                        <li><strong>Asylum and Refugee Law Practice Guide</strong></li>
                        <li><strong>Removal Defense and Litigation</strong></li>
                        <li><strong>Naturalization and Citizenship Law</strong></li>
                        <li><strong>Immigration Consequences of Criminal Convictions</strong></li>
                    </ul>
                    
                    <strong>Journals and Periodicals:</strong>
                    <ul>
                        <li><strong>Immigration Law Today</strong> - AILA publication</li>
                        <li><strong>Interpreter Releases</strong> - Weekly updates</li>
                        <li><strong>Immigration Daily</strong> - News and analysis</li>
                        <li><strong>Bender's Immigration Bulletin</strong></li>
                        <li><strong>Georgetown Immigration Law Journal</strong></li>
                        <li><strong>Stanford Law Review Immigration Symposium</strong></li>
                    </ul>
                    
                    <strong>Electronic Resources:</strong>
                    <ul>
                        <li><strong>AILA InfoNet</strong> - Member research database</li>
                        <li><strong>ILW.com</strong> - Immigration news portal</li>
                        <li><strong>Immigration Library</strong> - Case law database</li>
                        <li><strong>Immlaw.com</strong> - Practice resources</li>
                        <li><strong>CLINIC Network</strong> - Pro bono resources</li>
                    </ul>
                </div>
                """, unsafe_allow_html=True)
        
        elif resource_category == "Research Tools & Databases":
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("""
                <div class="professional-card">
                    <h4>🔍 Legal Research Platforms</h4>
                    
                    <strong>Comprehensive Legal Databases:</strong>
                    <ul>
                        <li><strong>Westlaw Edge</strong></li>
                        <li>&nbsp;&nbsp;• Immigration Law Library</li>
                        <li>&nbsp;&nbsp;• KeyCite citation analysis</li>
                        <li>&nbsp;&nbsp;• ALR Immigration articles</li>
                        <li>&nbsp;&nbsp;• BNA Immigration Library</li>
                        <li><strong>Lexis+ (LexisNexis)</strong></li>
                        <li>&nbsp;&nbsp;• Immigration law materials</li>
                        <li>&nbsp;&nbsp;• Shepard's Citations</li>
                        <li>&nbsp;&nbsp;• Matthew Bender Immigration treatises</li>
                        <li><strong>Bloomberg Law</strong></li>
                        <li>&nbsp;&nbsp;• Immigration practice center</li>
                        <li>&nbsp;&nbsp;• Daily immigration news</li>
                        <li>&nbsp;&nbsp;• Regulatory tracking</li>
                    </ul>
                    
                    <strong>Free and Government Resources:</strong>
                    <ul>
                        <li><strong>Google Scholar</strong> - Free case law access</li>
                        <li><strong>Justia.com</strong> - Free legal resources</li>
                        <li><strong>FindLaw.com</strong> - Legal research tools</li>
                        <li><strong>USCIS.gov</strong> - Official policy and forms</li>
                        <li><strong>DOJ EOIR</strong> - Immigration court decisions</li>
                        <li><strong>State Department</strong> - Consular processing info</li>
                        <li><strong>Federal Register</strong> - Regulatory updates</li>
                    </ul>
                    
                    <strong>Immigration-Specific Databases:</strong>
                    <ul>
                        <li><strong>AILA InfoNet</strong> - Members-only research</li>
                        <li><strong>BIA Database</strong> - Board decisions</li>
                        <li><strong>Immigration Library</strong> - Specialized research</li>
                        <li><strong>Interpreter Releases Archives</strong></li>
                        <li><strong>INSight (archived)</strong> - Historical INS guidance</li>
                    </ul>
                </div>
                """, unsafe_allow_html=True)
                
            with col2:
                st.markdown("""
                <div class="professional-card">
                    <h4>🏛️ Government Resources & Databases</h4>
                    
                    <strong>USCIS Resources:</strong>
                    <ul>
                        <li><strong>USCIS Policy Manual</strong> - Complete guidance</li>
                        <li><strong>Administrative Appeals Office (AAO)</strong> - Decision database</li>
                        <li><strong>USCIS Forms and Fee Calculator</strong></li>
                        <li><strong>Processing Time Information</strong></li>
                        <li><strong>Field Office and Service Center Directories</strong></li>
                        <li><strong>myUSCIS Account Portal</strong></li>
                    </ul>
                    
                    <strong>DOJ Executive Office for Immigration Review (EOIR):</strong>
                    <ul>
                        <li><strong>Immigration Court Practice Manual</strong></li>
                        <li><strong>Board of Immigration Appeals (BIA) Decisions</strong></li>
                        <li><strong>Immigration Judge Benchbook</strong></li>
                        <li><strong>Court Locations and Contact Information</strong></li>
                        <li><strong>Electronic Filing System (ECAS)</strong></li>
                    </ul>
                    
                    <strong>Department of State:</strong>
                    <ul>
                        <li><strong>Foreign Affairs Manual (FAM)</strong></li>
                        <li><strong>Visa Bulletin</strong> - Monthly priority date updates</li>
                        <li><strong>Country-Specific Information</strong></li>
                        <li><strong>Consular Processing Procedures</strong></li>
                        <li><strong>Travel.State.Gov</strong> - Visa information</li>
                    </ul>
                    
                    <strong>Department of Labor:</strong>
                    <ul>
                        <li><strong>PERM Labor Certification</strong></li>
                        <li><strong>Prevailing Wage Determinations</strong></li>
                        <li><strong>O*NET Occupational Database</strong></li>
                        <li><strong>Bureau of Labor Statistics</strong></li>
                        <li><strong>Foreign Labor Certification</strong></li>
                    </ul>
                    
                    <strong>Other Federal Agencies:</strong>
                    <ul>
                        <li><strong>CBP.gov</strong> - Entry and inspection procedures</li>
                        <li><strong>ICE.gov</strong> - Enforcement policies</li>
                        <li><strong>Federal Register</strong> - Regulatory changes</li>
                        <li><strong>Congressional Research Service</strong> - Policy reports</li>
                    </ul>
                </div>
                """, unsafe_allow_html=True)
        
        # Enhanced SOC Code Checker Tool
        st.markdown("---")
        st.markdown("""
        <div class="info-box">
            <h4>🔧 Professional Immigration Analysis Tools</h4>
            <p>Comprehensive tools for immigration law practice including SOC code analysis, visa eligibility assessment, and case strategy planning.</p>
        </div>
        """, unsafe_allow_html=True)
        
        tool_type = st.selectbox(
            "Select Analysis Tool:",
            ["SOC Code Checker", "Visa Eligibility Assessment", "Filing Deadline Calculator", "Case Strategy Planner"]
        )
        
        if tool_type == "SOC Code Checker":
            with st.form("comprehensive_soc_checker"):
                col1, col2 = st.columns([2, 1])
                with col1:
                    soc_input = st.text_input("Enter SOC Code", placeholder="Example: 15-1132", 
                                             help="Enter the Standard Occupational Classification code")
                    position_title = st.text_input("Position Title (Optional)", help="Job title for additional context")
                
                with col2:
                    check_soc = st.form_submit_button("🔍 Analyze SOC Code", type="primary")
                
                if check_soc and soc_input:
                    result = check_soc_code(soc_input.strip())
                    if result["status"] == "WARNING":
                        st.markdown(f"""
                        <div class="warning-box">
                            <strong>⚠️ SOC Code Analysis Result:</strong><br>
                            {result["message"]}<br>
                            <strong>Position Title:</strong> {result["title"]}<br>
                            <strong>Professional Recommendation:</strong> {result["recommendation"]}<br>
                            <strong>Alternative Strategy:</strong> Consider finding a more specific SOC code in Job Zone 4 or 5, or strengthen the specialty occupation argument with additional evidence.
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                        <div class="success-box">
                            <strong>✅ SOC Code Analysis Result:</strong><br>
                            {result["message"]}<br>
                            <strong>Professional Recommendation:</strong> {result["recommendation"]}<br>
                            <strong>Next Steps:</strong> Verify job duties align with SOC code description and gather supporting industry evidence.
                        </div>
                        """, unsafe_allow_html=True)
        
        elif tool_type == "Visa Eligibility Assessment":
            st.markdown("""
            <div class="info-box">
                <strong>📋 Comprehensive Visa Eligibility Assessment:</strong> Analyze client eligibility for multiple visa categories 
                and identify the best immigration strategy based on their profile and goals.
            </div>
            """, unsafe_allow_html=True)
            
            with st.form("visa_eligibility_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    current_status = st.selectbox("Current Immigration Status", 
                                                ["F-1 Student", "H-1B", "L-1", "O-1", "B-1/B-2", "Out of Status", "Outside US", "Other"])
                    education_level = st.selectbox("Highest Education Level", 
                                                 ["High School", "Associate Degree", "Bachelor's Degree", "Master's Degree", "PhD/Doctorate", "Professional Degree"])
                    work_experience = st.selectbox("Years of Work Experience", 
                                                 ["Less than 1 year", "1-3 years", "3-5 years", "5-10 years", "10+ years"])
                
                with col2:
                    field_of_expertise = st.text_input("Field of Expertise/Industry")
                    employer_sponsorship = st.selectbox("Employer Sponsorship Available", ["Yes", "No", "Uncertain"])
                    family_ties = st.selectbox("US Family Ties", ["US Citizen Spouse", "LPR Spouse", "US Citizen Parent", "US Citizen Child", "Other Family", "None"])
                
                special_circumstances = st.text_area("Special Circumstances or Goals", 
                                                   help="Any special qualifications, achievements, or immigration goals")
                
                assess_eligibility = st.form_submit_button("📊 Assess Visa Eligibility", type="primary")
                
                if assess_eligibility:
                    # This would generate a comprehensive eligibility assessment
                    st.markdown("""
                    <div class="success-box">
                        <strong>✅ Eligibility Assessment Generated:</strong> Based on the provided information, 
                        a comprehensive analysis of potential visa options would be generated here, including recommended 
                        strategies and timeline considerations.
                    </div>
                    """, unsafe_allow_html=True)
        
        st.markdown("</div>", unsafe_allow_html=True)

    # Professional Footer
    st.markdown("""
    <div class="footer">
        <div style='display: flex; justify-content: center; align-items: center; gap: 20px; margin-bottom: 1rem;'>
            <div class="lawtrax-logo" style='font-size: 18px; padding: 8px 16px;'>LAWTRAX</div>
            <span style='color: #64748b; font-size: 14px;'>Immigration Law Assistant</span>
        </div>
        <p style='color: #64748b; margin: 0; font-size: 14px;'>
            <strong>Professional AI-Powered Legal Technology</strong> | For Licensed Immigration Attorneys Only<br>
            <small>All AI-generated content requires review by qualified legal counsel. System compliance with professional responsibility standards.</small>
        </p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
