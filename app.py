import streamlit as st
import os
import requests
import json
import pandas as pd
from datetime import datetime
import re
import base64
from io import BytesIO

# Optional imports with fallback handling
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    import docx
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

# Set page config
st.set_page_config(
    page_title="Lawtrax Immigration Assistant",
    page_icon="[LEGAL]",
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
    .upload-box {
        background: linear-gradient(135deg, #f3e8ff 0%, #e9d5ff 100%);
        border-left: 5px solid #8b5cf6;
        padding: 1.5rem;
        margin: 1rem 0;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .tab-content {
        padding: 2rem 1rem;
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
if 'uploaded_rfe_content' not in st.session_state:
    st.session_state.uploaded_rfe_content = None

# Job Zone 3 SOC Codes (to avoid for H-1B)
JOB_ZONE_3_CODES = {
    "15-1199": "Computer Occupations, All Other",
    "15-1134": "Web Developers",
    "15-1152": "Computer Network Support Specialists",
    "15-1153": "Computer Network Architects",
    "15-1154": "Computer Network and Computer Systems Administrators",
    "15-1142": "Network and Computer Systems Administrators",
    "15-1143": "Computer Network Architects",
}

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

def extract_text_from_file(uploaded_file):
    """Extract text from uploaded file with fallback handling"""
    try:
        if uploaded_file.type == "application/pdf":
            if not PDF_AVAILABLE:
                st.error("PDF processing not available. Please install PyPDF2 or upload a TXT file instead.")
                st.info("Alternative: Copy and paste the RFE text directly into the manual input field below.")
                return None
            pdf_reader = PyPDF2.PdfReader(uploaded_file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text
        
        elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            if not DOCX_AVAILABLE:
                st.error("DOCX processing not available. Please install python-docx or upload a TXT file instead.")
                st.info("Alternative: Copy and paste the RFE text directly into the manual input field below.")
                return None
            doc = docx.Document(uploaded_file)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text
        
        elif uploaded_file.type == "text/plain":
            return str(uploaded_file.read(), "utf-8")
        
        else:
            st.error("Unsupported file format. Please upload TXT files or copy/paste content manually.")
            return None
            
    except Exception as e:
        st.error(f"Error extracting text from file: {str(e)}")
        st.info("Please try uploading a TXT file or copy/paste the content manually.")
        return None

def analyze_rfe_document(rfe_text):
    """Analyze RFE document and extract key issues"""
    try:
        rfe_analysis = {
            "issues_identified": [],
            "deadline_mentioned": None,
            "receipt_number": None,
            "case_type": None,
            "specific_requirements": []
        }
        
        specialty_occupation_keywords = ["specialty occupation", "bachelor's degree", "job duties", "position requirements"]
        beneficiary_keywords = ["beneficiary", "qualifications", "education", "experience", "credentials"]
        employer_keywords = ["employer-employee relationship", "right to control", "staffing", "client site"]
        ability_to_pay_keywords = ["ability to pay", "financial capacity", "tax returns", "financial statements"]
        
        rfe_text_lower = rfe_text.lower()
        
        if any(keyword in rfe_text_lower for keyword in specialty_occupation_keywords):
            rfe_analysis["issues_identified"].append("Specialty Occupation Requirements")
            
        if any(keyword in rfe_text_lower for keyword in beneficiary_keywords):
            rfe_analysis["issues_identified"].append("Beneficiary Qualifications")
            
        if any(keyword in rfe_text_lower for keyword in employer_keywords):
            rfe_analysis["issues_identified"].append("Employer-Employee Relationship")
            
        if any(keyword in rfe_text_lower for keyword in ability_to_pay_keywords):
            rfe_analysis["issues_identified"].append("Ability to Pay")
        
        deadline_pattern = r'response.*?due.*?(\d{1,2}\/\d{1,2}\/\d{4})'
        deadline_match = re.search(deadline_pattern, rfe_text_lower)
        if deadline_match:
            rfe_analysis["deadline_mentioned"] = deadline_match.group(1)
        
        receipt_pattern = r'(MSC|EAC|WAC|SRC|NBC|IOE)\d{10,13}'
        receipt_match = re.search(receipt_pattern, rfe_text, re.IGNORECASE)
        if receipt_match:
            rfe_analysis["receipt_number"] = receipt_match.group(0)
        
        return rfe_analysis
        
    except Exception as e:
        st.error(f"Error analyzing RFE document: {str(e)}")
        return None

def call_openai_api(prompt, max_tokens=3000, temperature=0.2):
    """Enhanced OpenAI API call with better error handling"""
    try:
        api_key = None
        if hasattr(st, 'secrets') and "OPENAI_API_KEY" in st.secrets:
            api_key = st.secrets["OPENAI_API_KEY"]
        elif os.getenv("OPENAI_API_KEY"):
            api_key = os.getenv("OPENAI_API_KEY")
        else:
            st.error("[ERROR] OpenAI API key not found. Please configure your API key in Streamlit secrets.")
            return None
        
        if not api_key or not api_key.startswith('sk-'):
            st.error("[ERROR] Invalid API key format. Please check your configuration.")
            return None
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        system_message = """You are an expert immigration attorney with extensive knowledge of US immigration law, USCIS policies, and legal precedents. Provide comprehensive, well-researched, and professionally formatted responses suitable for legal practice. Include relevant citations to statutes, regulations, case law, and USCIS guidance where appropriate. Structure your responses clearly and provide actionable legal advice."""
        
        data = {
            "model": "gpt-4",
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=120
        )
        
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            st.error(f"API Error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        st.error(f"Error calling OpenAI API: {str(e)}")
        return None

def generate_rfe_response_from_document(rfe_text, visa_category, case_details):
    """Generate comprehensive RFE response based on uploaded document"""
    rfe_analysis = analyze_rfe_document(rfe_text)
    
    if not rfe_analysis:
        return "Error analyzing RFE document. Please check the file and try again."
    
    prompt = f"""
    As an expert immigration attorney, provide a comprehensive RFE response based on the following uploaded RFE document and case details.

    VISA CATEGORY: {visa_category}

    RFE DOCUMENT ANALYSIS:
    - Issues Identified: {', '.join(rfe_analysis['issues_identified'])}
    - Receipt Number: {rfe_analysis.get('receipt_number', 'Not found')}
    - Deadline: {rfe_analysis.get('deadline_mentioned', 'Not found')}

    CASE DETAILS:
    - Petitioner: {case_details.get('petitioner', 'Not specified')}
    - Beneficiary: {case_details.get('beneficiary', 'Not specified')}
    - Position: {case_details.get('position', 'Not specified')}

    RFE DOCUMENT CONTENT:
    {rfe_text[:4000]}

    Please provide a comprehensive legal response that:

    1. ADDRESSES EACH SPECIFIC ISSUE raised in the RFE document with detailed legal analysis
    2. PROVIDES REGULATORY FRAMEWORK with citations to relevant statutes, regulations, and case law
    3. RECOMMENDS SPECIFIC EVIDENCE needed to overcome each issue
    4. INCLUDES LEGAL ARGUMENTS with proper citations and precedents
    5. SUGGESTS EXPERT OPINIONS where beneficial
    6. OUTLINES RESPONSE STRATEGY with timeline and priority actions
    7. IDENTIFIES POTENTIAL CHALLENGES and mitigation strategies

    Format the response as a professional legal brief suitable for USCIS submission with:
    - Executive summary
    - Issue-by-issue analysis
    - Legal framework and citations
    - Evidence recommendations
    - Conclusion and next steps

    Ensure the response is comprehensive, well-cited, and addresses all concerns raised in the RFE.
    """
    
    return call_openai_api(prompt, max_tokens=4000, temperature=0.2)

def generate_legal_research_response(question):
    """Enhanced legal research with better prompting"""
    prompt = f"""
    As an expert immigration attorney with comprehensive knowledge of US immigration law, provide detailed research and analysis on the following question:

    RESEARCH QUESTION: {question}

    Please provide a comprehensive response that includes:

    1. DIRECT ANSWER - Clear, actionable response to the specific question
    2. LEGAL FRAMEWORK - Relevant statutes, regulations, and legal standards
    3. CURRENT USCIS POLICY - Latest guidance, policy memoranda, and procedural updates
    4. CASE LAW ANALYSIS - Relevant court decisions and BIA precedents
    5. PRACTICAL GUIDANCE - Strategic considerations and best practices
    6. RISK ASSESSMENT - Potential challenges and mitigation strategies
    7. RECENT DEVELOPMENTS - Any recent changes in law, policy, or practice
    8. CITATIONS - Specific references to legal authorities

    Structure your response clearly with headers and provide specific, actionable guidance suitable for immigration law practice. Include relevant form numbers, filing procedures, and timeline considerations where applicable.

    Focus on providing current, accurate information that would be valuable for immigration attorneys in their practice.
    """
    
    return call_openai_api(prompt, max_tokens=3500, temperature=0.2)

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

def check_soc_code(soc_code):
    """Check if SOC code is in Job Zone 3"""
    if soc_code in JOB_ZONE_3_CODES:
        return {
            "status": "WARNING",
            "message": f"[WARNING] This SOC code ({soc_code}) is Job Zone 3 and should be avoided for H-1B specialty occupation.",
            "title": JOB_ZONE_3_CODES[soc_code],
            "recommendation": "Consider finding a more specific SOC code that falls in Job Zone 4 or 5."
        }
    else:
        return {
            "status": "OK", 
            "message": f"[OK] SOC code {soc_code} appears to be acceptable (not in Job Zone 3).",
            "recommendation": "Verify this SOC code aligns with the actual job duties and requirements."
        }

def load_logo():
    """Load Lawtrax logo with fallback handling"""
    if not PIL_AVAILABLE:
        return None
    try:
        if os.path.exists("assets/lawtrax_logo.png"):
            return Image.open("assets/lawtrax_logo.png")
        return None
    except Exception:
        return None

def main():
    # Professional Header
    if PIL_AVAILABLE:
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
        <strong>[LEGAL] ATTORNEY USE ONLY:</strong> This tool is exclusively designed for licensed immigration attorneys and qualified legal professionals. 
        All AI-generated content must be reviewed, verified, and approved by supervising counsel before use. This system does not provide legal advice to end clients.
    </div>
    """, unsafe_allow_html=True)

    # Check API Configuration and Dependencies
    col1, col2 = st.columns(2)
    
    with col1:
        if hasattr(st, 'secrets') and "OPENAI_API_KEY" in st.secrets:
            st.markdown("""
            <div class="success-box">
                <strong>[OK] API Status:</strong>  connectivity confirmed.
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="warning-box">
                <strong>[WARNING] Configuration Required:</strong> Please configure your OpenAI API key in Streamlit secrets.
            </div>
            """, unsafe_allow_html=True)
    
    with col2:
        dependencies_status = []
        if PDF_AVAILABLE:
            dependencies_status.append("[OK] PDF Support")
        else:
            dependencies_status.append("[X] PDF Support")
            
        if DOCX_AVAILABLE:
            dependencies_status.append("[OK] DOCX Support")
        else:
            dependencies_status.append("[X] DOCX Support")
        
        dependencies_status.append("[OK] TXT Support")
        
        st.markdown(f"""
        <div class="info-box">
            <strong>[INFO] System Dependencies:</strong><br>
            {' | '.join(dependencies_status)}
        </div>
        """, unsafe_allow_html=True)

    # Show installation instructions if dependencies are missing
    missing_deps = []
    if not PDF_AVAILABLE:
        missing_deps.append("PyPDF2")
    if not DOCX_AVAILABLE:
        missing_deps.append("python-docx")
        
    if missing_deps:
        with st.expander("[DEPS] Install Missing Dependencies (Optional)"):
            st.markdown(f"""
            **To enable full file support, install these packages:**
            
            ```bash
            pip install {' '.join(missing_deps)}
            ```
            
            **Or add to requirements.txt:**
            ```
            {chr(10).join(missing_deps)}
            ```
            
            **Note:** The system works perfectly with manual text input. File upload is just a convenience feature.
            """)

    st.markdown("---")

    # Main content tabs - RESTORED ALL ORIGINAL TABS
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "[CHAT] Legal Research Chat", 
        "[RFE] RFE Response Generator", 
        "[EXPERT] Expert Opinion Letters",
        "[TEMPLATES] Professional Templates",
        "[RESOURCES] Legal Resources"
    ])

    with tab1:
        st.markdown("<div class='tab-content'>", unsafe_allow_html=True)
        st.subheader("[CHAT] Immigration Law Research Assistant")
        
        st.markdown("""
        <div class="info-box">
            <strong>Professional Research Tool:</strong> Ask complex immigration law questions and receive comprehensive, 
            citation-backed analysis suitable for attorney use. This tool provides current legal guidance, case law analysis, 
            and practical recommendations for immigration practice.
        </div>
        """, unsafe_allow_html=True)
        
        question = st.text_area(
            "Enter your immigration law research question:",
            placeholder="Example: What are the latest USCIS policy updates for H-1B specialty occupation determinations? How should I address a complex beneficiary qualifications RFE?",
            height=120,
            help="Ask detailed questions about immigration law, policy updates, case strategies, or legal precedents."
        )
        
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("[SEARCH] Research Question", type="primary", use_container_width=True):
                if question:
                    with st.spinner("Conducting comprehensive legal research..."):
                        response = generate_legal_research_response(question)
                        if response:
                            st.session_state.chat_history.append({
                                "question": question,
                                "answer": response,
                                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            })
                            
                            st.markdown("### [RESULTS] Research Results")
                            st.markdown(f"""
                            <div class="professional-card">
                                <strong>Question:</strong> {question}<br><br>
                                {response}
                            </div>
                            """, unsafe_allow_html=True)
                            
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            filename = f"Legal_Research_{timestamp}.txt"
                            download_content = f"LAWTRAX IMMIGRATION RESEARCH\n{'='*50}\n\nQuestion: {question}\n\nResearch Results:\n{response}\n\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                            st.download_button(
                                "[DOWNLOAD] Download Research",
                                data=download_content,
                                file_name=filename,
                                mime="text/plain",
                                use_container_width=True
                            )
                else:
                    st.warning("Please enter a research question.")
        
        if st.session_state.chat_history:
            st.markdown("### [HISTORY] Recent Research History")
            for i, chat in enumerate(reversed(st.session_state.chat_history[-3:])):
                with st.expander(f"[ITEM] {chat['question'][:80]}... ({chat['timestamp']})"):
                    st.markdown(chat['answer'])
        
        st.markdown("</div>", unsafe_allow_html=True)

    with tab2:
        st.markdown("<div class='tab-content'>", unsafe_allow_html=True)
        st.subheader("[RFE] Enhanced RFE Response Generator with Document Upload")
        
        st.markdown("""
        <div class="info-box">
            <strong>[TARGET] Enhanced RFE Response System:</strong> Upload your RFE document for automatic analysis and response generation, 
            or manually enter case details. Supports PDF, DOCX, and TXT files for comprehensive RFE processing.
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="upload-box">
            <strong>[UPLOAD] Upload RFE Document:</strong> Upload the actual RFE document from USCIS for automatic analysis 
            and targeted response generation. The system will extract key issues and generate appropriate responses.
        </div>
        """, unsafe_allow_html=True)

        available_types = ['txt']
        type_description = "TXT"
        
        if PDF_AVAILABLE:
            available_types.append('pdf')
            type_description += ", PDF"
            
        if DOCX_AVAILABLE:
            available_types.append('docx')
            type_description += ", DOCX"

        uploaded_file = st.file_uploader(
            "Upload RFE Document",
            type=available_types,
            help=f"Upload the RFE document received from USCIS ({type_description} format)"
        )

        if not PDF_AVAILABLE or not DOCX_AVAILABLE:
            st.markdown(f"""
            <div class="info-box">
                <strong>[INFO] File Support Status:</strong><br>
                - TXT files: [OK] Supported<br>
                - PDF files: {'[OK] Supported' if PDF_AVAILABLE else '[X] Not available (install PyPDF2)'}<br>
                - DOCX files: {'[OK] Supported' if DOCX_AVAILABLE else '[X] Not available (install python-docx)'}<br><br>
                <strong>[TIP] Tip:</strong> You can always copy and paste RFE content manually below if file upload isn't working.
            </div>
            """, unsafe_allow_html=True)

        if uploaded_file is not None:
            with st.spinner("Analyzing uploaded RFE document..."):
                extracted_text = extract_text_from_file(uploaded_file)
                if extracted_text:
                    st.session_state.uploaded_rfe_content = extracted_text
                    rfe_analysis = analyze_rfe_document(extracted_text)
                    
                    st.markdown("""
                    <div class="success-box">
                        <strong>[OK] RFE Document Successfully Processed</strong>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**[ISSUES] Issues Identified:**")
                        if rfe_analysis and rfe_analysis['issues_identified']:
                            for issue in rfe_analysis['issues_identified']:
                                st.markdown(f"• {issue}")
                        else:
                            st.markdown("• General RFE requirements")
                    
                    with col2:
                        st.markdown("**[DETAILS] Document Details:**")
                        if rfe_analysis:
                            if rfe_analysis.get('receipt_number'):
                                st.markdown(f"• Receipt Number: {rfe_analysis['receipt_number']}")
                            if rfe_analysis.get('deadline_mentioned'):
                                st.markdown(f"• Deadline: {rfe_analysis['deadline_mentioned']}")
                            st.markdown(f"• Document Length: {len(extracted_text)} characters")

        st.markdown("### [FORM] Case Information")
        
        with st.form("enhanced_rfe_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                visa_categories = []
                for main_cat, subcats in US_VISA_CATEGORIES.items():
                    for subcat, visas in subcats.items():
                        for visa_code, visa_name in visas.items():
                            visa_categories.append(f"{visa_code} - {visa_name}")
                
                visa_category = st.selectbox(
                    "Visa Category:",
                    ["H-1B - Specialty Occupation Workers"] + sorted(visa_categories),
                    help="Select the visa category for this RFE"
                )
                
                petitioner = st.text_input("Petitioner/Employer Name")
                beneficiary = st.text_input("Beneficiary Name")
                
            with col2:
                position = st.text_input("Position Title")
                receipt_number = st.text_input("USCIS Receipt Number")
                response_deadline = st.date_input("RFE Response Deadline")
            
            if not st.session_state.uploaded_rfe_content:
                st.markdown("### [INPUT] Manual RFE Content Input")
                st.markdown("""
                <div class="info-box">
                    <strong>[TIP] Manual Input Option:</strong> If you cannot upload a file or prefer to copy/paste, 
                    enter the RFE content directly below. This works just as well as file upload.
                </div>
                """, unsafe_allow_html=True)
                
                manual_rfe_issues = st.text_area(
                    "RFE Content (copy and paste from USCIS document):",
                    height=150,
                    help="Copy and paste the full RFE text or describe the specific issues raised",
                    placeholder="Paste the complete RFE text here, or describe the specific issues such as:\n\n• Specialty occupation requirements not established\n• Beneficiary qualifications insufficient\n• Employer-employee relationship unclear\n• Additional evidence needed for [specific requirement]"
                )
            else:
                manual_rfe_issues = ""
                st.markdown("### [OK] Using Uploaded RFE Document")
                st.info("RFE issues will be extracted from uploaded document")
            
            additional_details = st.text_area(
                "Additional Case Details:",
                height=80,
                help="Any additional relevant information about the case"
            )
            
            submit_rfe = st.form_submit_button("[GENERATE] Generate Comprehensive RFE Response", type="primary")
            
            if submit_rfe:
                if st.session_state.uploaded_rfe_content or manual_rfe_issues:
                    case_details = {
                        "petitioner": petitioner,
                        "beneficiary": beneficiary,
                        "position": position,
                        "receipt_number": receipt_number,
                        "rfe_issues": manual_rfe_issues,
                        "additional_details": additional_details
                    }
                    
                    with st.spinner("Generating comprehensive RFE response..."):
                        if st.session_state.uploaded_rfe_content:
                            response = generate_rfe_response_from_document(
                                st.session_state.uploaded_rfe_content, 
                                visa_category.split(" - ")[0] if " - " in visa_category else visa_category,
                                case_details
                            )
                        else:
                            visa_code = visa_category.split(" - ")[0] if " - " in visa_category else visa_category
                            
                            prompt = f"""
                            As an expert immigration attorney, draft a comprehensive RFE response for a {visa_code} petition.

                            Case Details:
                            - Visa Category: {visa_code}
                            - Position: {case_details.get('position', 'Not specified')}
                            - Petitioner: {case_details.get('petitioner', 'Not specified')}
                            - Beneficiary: {case_details.get('beneficiary', 'Not specified')}
                            - RFE Issues: {case_details.get('rfe_issues', 'Not specified')}
                            - Additional Details: {case_details.get('additional_details', 'Not specified')}

                            Provide a comprehensive legal response addressing:
                            1. Specific requirements for {visa_code} classification
                            2. Regulatory framework and legal standards with citations
                            3. Evidence and documentation requirements
                            4. Case law and precedents supporting the petition
                            5. Industry standards and best practices
                            6. Expert opinion recommendations
                            7. Risk mitigation strategies

                            Format as a professional legal brief suitable for USCIS submission with proper citations and legal reasoning.
                            """
                            
                            response = call_openai_api(prompt, max_tokens=4000, temperature=0.2)
                        
                        if response:
                            st.subheader(f"[RESPONSE] Comprehensive RFE Response - {visa_category}")
                            st.markdown(f"""
                            <div class="professional-card">
                                {response}
                            </div>
                            """, unsafe_allow_html=True)
                            
                            st.session_state['latest_rfe_response'] = {
                                'content': response,
                                'visa_category': visa_category,
                                'petitioner': petitioner,
                                'beneficiary': beneficiary
                            }
                            
                            st.session_state.uploaded_rfe_content = None
                else:
                    st.warning("Please upload an RFE document or manually describe the RFE issues.")
        
        if 'latest_rfe_response' in st.session_state:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"RFE_Response_{st.session_state['latest_rfe_response']['visa_category'].split(' - ')[0]}_{timestamp}.txt"
            download_content = f"""LAWTRAX IMMIGRATION SERVICES
RFE RESPONSE - {st.session_state['latest_rfe_response']['visa_category']}
{'='*80}

Petitioner: {st.session_state['latest_rfe_response']['petitioner']}
Beneficiary: {st.session_state['latest_rfe_response']['beneficiary']}

{st.session_state['latest_rfe_response']['content']}

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
            
            st.download_button(
                "[DOWNLOAD] Download RFE Response",
                data=download_content,
                file_name=filename,
                mime="text/plain",
                key="download_rfe_response"
            )
        
        st.markdown("</div>", unsafe_allow_html=True)

    with tab3:
        st.markdown("<div class='tab-content'>", unsafe_allow_html=True)
        st.subheader("[EXPERT] Expert Opinion & Support Letter Generator")
        
        st.markdown("""
        <div class="info-box">
            <strong>[SERVICES] Expert Opinion Services:</strong> Generate professional expert opinion letters, support letters, 
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
                <strong>[POSITION] Position/Industry Expert Opinion:</strong> Generate expert opinions from qualified 
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
                
                submit_position_expert = st.form_submit_button("[GENERATE] Generate Position Expert Opinion", type="primary")
                
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
                            st.subheader("[LETTER] Position Expert Opinion Letter")
                            st.markdown(f"""
                            <div class="professional-card">
                                {letter}
                            </div>
                            """, unsafe_allow_html=True)
                            
                            st.session_state['latest_expert_opinion'] = {
                                'content': letter,
                                'type': 'Position_Expert_Opinion',
                                'expert': expert_name
                            }
            
            if 'latest_expert_opinion' in st.session_state:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{st.session_state['latest_expert_opinion']['type']}_{timestamp}.txt"
                download_content = f"LAWTRAX IMMIGRATION SERVICES\n{st.session_state['latest_expert_opinion']['type'].replace('_', ' ').upper()}\n{'='*60}\n\n{st.session_state['latest_expert_opinion']['content']}\n\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                st.download_button(
                    "[DOWNLOAD] Download Expert Opinion",
                    data=download_content,
                    file_name=filename,
                    mime="text/plain",
                    key="download_expert_opinion"
                )
        
        st.markdown("</div>", unsafe_allow_html=True)

    with tab4:
        st.markdown("<div class='tab-content'>", unsafe_allow_html=True)
        st.subheader("[TEMPLATES] Comprehensive Immigration Templates & Legal Frameworks")
        
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
                    <h4>[OK] H-1B Specialty Occupation Filing Checklist</h4>
                    
                    <strong>[FORMS] USCIS Forms & Fees:</strong>
                    <ul>
                        <li>Form I-129 (signed by authorized company representative)</li>
                        <li>H Classification Supplement to Form I-129</li>
                        <li>USCIS filing fee ($460) + Fraud Prevention fee ($500)</li>
                        <li>American Competitiveness fee ($750/$1,500 based on company size)</li>
                        <li>Premium Processing fee ($2,805) if requested</li>
                    </ul>
                    
                    <strong>[EMPLOYER] Employer Documentation:</strong>
                    <ul>
                        <li>Certified Labor Condition Application (LCA) from DOL</li>
                        <li>Detailed support letter explaining position and requirements</li>
                        <li>Company organizational chart showing position placement</li>
                        <li>Evidence of employer's business operations and legitimacy</li>
                        <li>Job description with specific duties and education requirements</li>
                        <li>Corporate documents (incorporation, business license)</li>
                    </ul>
                    
                    <strong>[BENEFICIARY] Beneficiary Documentation:</strong>
                    <ul>
                        <li>Copy of passport biographical page</li>
                        <li>Current immigration status documentation</li>
                        <li>Educational credentials and evaluation</li>
                        <li>Resume/CV with detailed work history</li>
                        <li>Experience letters from previous employers</li>
                        <li>Professional licenses/certifications if applicable</li>
                    </ul>
                    
                    <strong>[SPECIALTY] Specialty Occupation Evidence:</strong>
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
                    <h4>[OK] O-1 Extraordinary Ability Filing Checklist</h4>
                    
                    <strong>[FORMS] USCIS Forms & Documentation:</strong>
                    <ul>
                        <li>Form I-129 with O Classification Supplement</li>
                        <li>Consultation from appropriate peer group or labor organization</li>
                        <li>Copy of contract or summary of oral agreement</li>
                        <li>Detailed itinerary of events/activities</li>
                    </ul>
                    
                    <strong>[CRITERIA] Evidence of Extraordinary Ability (O-1A - Sciences/Education/Business/Athletics):</strong>
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
                    
                    <strong>[ARTS] Evidence for O-1B (Arts/Motion Pictures/TV):</strong>
                    <ul>
                        <li>Leading/starring roles in distinguished productions</li>
                        <li>Critical reviews and recognition in major newspapers</li>
                        <li>Commercial or critically acclaimed successes</li>
                        <li>Recognition from industry organizations</li>
                        <li>High salary compared to others in field</li>
                    </ul>
                    
                    <strong>[SUPPORT] Supporting Documentation:</strong>
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
                    <h4>[OK] EB-1 Priority Worker Green Card Checklist</h4>
                    
                    <strong>[FORMS] Form I-140 Package:</strong>
                    <ul>
                        <li>Form I-140 (signed by petitioner)</li>
                        <li>USCIS filing fee ($2,805)</li>
                        <li>Premium Processing fee ($2,805) if requested</li>
                        <li>Supporting evidence based on subcategory</li>
                    </ul>
                    
                    <strong>[EB-1A] EB-1A Extraordinary Ability Requirements:</strong>
                    <ul>
                        <li>Evidence of sustained national/international acclaim</li>
                        <li>One-time major international award OR</li>
                        <li>At least 3 of the 10 regulatory criteria:</li>
                        <li>  - Major awards/prizes for excellence</li>
                        <li>  - Membership in exclusive associations</li>
                        <li>  - Published material about beneficiary</li>
                        <li>  - Judging work of others in field</li>
                        <li>  - Original contributions of major significance</li>
                        <li>  - Scholarly articles by beneficiary</li>
                        <li>  - Critical employment in distinguished organizations</li>
                        <li>  - High salary/remuneration</li>
                        <li>  - Commercial successes in performing arts</li>
                        <li>  - Display of work at artistic exhibitions</li>
                    </ul>
                    
                    <strong>[EB-1B] EB-1B Outstanding Professor/Researcher:</strong>
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
                    
                    <strong>[EB-1C] EB-1C Multinational Manager/Executive:</strong>
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
            
            elif immigrant_type == "Adjustment of Status (I-485)":
                st.markdown("""
                <div class="professional-card">
                    <h4>[OK] Adjustment of Status (I-485) Checklist</h4>
                    
                    <strong>[FORMS] Required Forms and Fees:</strong>
                    <ul>
                        <li>Form I-485 (Application to Adjust Status)</li>
                        <li>Filing fee: $1,440 (includes biometrics)</li>
                        <li>Medical examination (Form I-693)</li>
                        <li>Form I-864 Affidavit of Support (if required)</li>
                    </ul>
                    
                    <strong>[DOCS] Supporting Documentation:</strong>
                    <ul>
                        <li>Copy of birth certificate</li>
                        <li>Copy of passport biographical pages</li>
                        <li>Copy of current immigration status documents</li>
                        <li>Two passport-style photographs</li>
                        <li>Form I-94 arrival/departure record</li>
                        <li>Copy of approved immigrant petition (I-130, I-140, etc.)</li>
                    </ul>
                    
                    <strong>[MEDICAL] Medical Examination Requirements:</strong>
                    <ul>
                        <li>Completed by USCIS-designated civil surgeon</li>
                        <li>Vaccination records and requirements</li>
                        <li>Physical examination and medical history</li>
                        <li>Tuberculosis screening and blood tests</li>
                        <li>Mental health evaluation if indicated</li>
                    </ul>
                    
                    <strong>[SUPPORT] Affidavit of Support (I-864) Requirements:</strong>
                    <ul>
                        <li>Required for family-based and some employment cases</li>
                        <li>Sponsor must meet income requirements (125% of poverty guidelines)</li>
                        <li>Tax returns for most recent 3 years</li>
                        <li>Employment verification letter</li>
                        <li>Bank statements and asset documentation</li>
                    </ul>
                    
                    <strong>[ISSUES] Inadmissibility Issues:</strong>
                    <ul>
                        <li>Criminal history disclosure and documentation</li>
                        <li>Immigration violations and unlawful presence</li>
                        <li>Public charge considerations</li>
                        <li>Waiver applications if needed (I-601, I-601A)</li>
                    </ul>
                    
                    <strong>[WORK] Work Authorization:</strong>
                    <ul>
                        <li>Form I-765 can be filed concurrently</li>
                        <li>No additional fee when filed with I-485</li>
                        <li>Employment authorization typically granted while I-485 pending</li>
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
                    <h4>[TARGET] Specialty Occupation RFE Response Framework</h4>
                    
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
        
        st.markdown("</div>", unsafe_allow_html=True)

    with tab5:
        st.markdown("<div class='tab-content'>", unsafe_allow_html=True)
        st.subheader("[RESOURCES] Comprehensive US Immigration Law Resources")
        
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
                    <h4>[LAW] Immigration and Nationality Act (INA)</h4>
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
                    
                    <h4>[CONSTITUTION] Key Constitutional Provisions</h4>
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
                    <h4>[REGS] Code of Federal Regulations (CFR)</h4>
                    
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
        
        elif resource_category == "USCIS Policy & Guidance":
            st.markdown("""
            <div class="professional-card">
                <h4>[POLICY] USCIS Policy Manual & Comprehensive Guidance</h4>
                
                <strong>[VOLUMES] USCIS Policy Manual Volumes (Complete Coverage):</strong>
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
                
                <strong>[MEMOS] Critical USCIS Policy Memoranda:</strong>
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
                
                <strong>[PROCESSING] Current USCIS Processing Information:</strong>
                <ul>
                    <li><strong>Processing Times</strong> - Updated monthly for all offices and forms</li>
                    <li><strong>Premium Processing</strong> - Available forms and current fees</li>
                    <li><strong>Fee Schedule</strong> - Current USCIS filing fees (updated periodically)</li>
                    <li><strong>Forms and Instructions</strong> - Latest versions with completion guides</li>
                    <li><strong>Field Office Directories</strong> - Locations and contact information</li>
                    <li><strong>Service Center Operations</strong> - Jurisdiction and specializations</li>
                </ul>
                
                <strong>[STATS] USCIS Data and Statistics:</strong>
                <ul>
                    <li><strong>Annual Reports</strong> - Comprehensive immigration statistics</li>
                    <li><strong>Quarterly Reports</strong> - Current processing data</li>
                    <li><strong>H-1B Cap Data</strong> - Annual registration and selection statistics</li>
                    <li><strong>Green Card Statistics</strong> - Issuance data by category</li>
                    <li><strong>Naturalization Data</strong> - Citizenship processing statistics</li>
                    <li><strong>Refugee and Asylum Statistics</strong> - Protection case data</li>
                </ul>
                
                <strong>[OFFICES] USCIS Office Structure and Operations:</strong>
                <ul>
                    <li><strong>National Benefits Center (NBC)</strong> - Centralized processing</li>
                    <li><strong>Service Centers:</strong></li>
                    <li>  - California Service Center (CSC)</li>
                    <li>  - Nebraska Service Center (NSC)</li>
                    <li>  - Texas Service Center (TSC)</li>
                    <li>  - Vermont Service Center (VSC)</li>
                    <li>  - Potomac Service Center (PSC)</li>
                    <li><strong>Field Offices</strong> - Interview and application support offices nationwide</li>
                    <li><strong>Application Support Centers (ASCs)</strong> - Biometrics collection</li>
                </ul>
                
                <strong>[FORMS] USCIS Forms Library (Key Forms):</strong>
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
                
                <strong>[FEES] Current USCIS Fee Structure (2024):</strong>
                <ul>
                    <li><strong>I-129</strong> - $460 (base fee) + additional fees</li>
                    <li><strong>I-140</strong> - $2,805</li>
                    <li><strong>I-485</strong> - $1,440 (includes biometrics)</li>
                    <li><strong>Premium Processing</strong> - $2,805 (15 calendar days)</li>
                    <li><strong>Biometrics</strong> - $85 (when separate)</li>
                    <li><strong>N-400</strong> - $760</li>
                    <li><strong>Fee Waivers</strong> - Available for qualified applicants</li>
                </ul>
                
                <strong>[SYSTEMS] USCIS Electronic Systems:</strong>
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
        
        elif resource_category == "Case Law & Precedents":
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("""
                <div class="professional-card">
                    <h4>[SUPREME] Supreme Court Immigration Cases</h4>
                    
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
                    <h4>[CIRCUIT] Key Circuit Court Decisions</h4>
                    
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
        
        elif resource_category == "Professional Development":
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("""
                <div class="professional-card">
                    <h4>[EDUCATION] Immigration Law Education & Training</h4>
                    
                    <strong>Professional Organizations:</strong>
                    <ul>
                        <li><strong>American Immigration Lawyers Association (AILA)</strong></li>
                        <li>  - National conferences and workshops</li>
                        <li>  - Practice advisories and liaison meetings</li>
                        <li>  - Member forums and networking</li>
                        <li>  - Ethics and professional responsibility</li>
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
                        <li>  - State bar certification programs</li>
                        <li>  - Continuing education requirements</li>
                        <li>  - Peer review and examination</li>
                        <li><strong>AILA Basic Immigration Law Course</strong></li>
                        <li><strong>Advanced Practice Specializations</strong></li>
                        <li><strong>Asylum and Refugee Law Certification</strong></li>
                    </ul>
                </div>
                """, unsafe_allow_html=True)
                
            with col2:
                st.markdown("""
                <div class="professional-card">
                    <h4>[PUBLICATIONS] Essential Immigration Law Publications</h4>
                    
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
        
        # Enhanced SOC Code Checker Tool
        st.markdown("---")
        st.markdown("""
        <div class="info-box">
            <h4>[TOOLS] Professional Immigration Analysis Tools</h4>
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
                    check_soc = st.form_submit_button("[ANALYZE] Analyze SOC Code", type="primary")
                
                if check_soc and soc_input:
                    result = check_soc_code(soc_input.strip())
                    if result["status"] == "WARNING":
                        st.markdown(f"""
                        <div class="warning-box">
                            <strong>[WARNING] SOC Code Analysis Result:</strong><br>
                            {result["message"]}<br>
                            <strong>Position Title:</strong> {result["title"]}<br>
                            <strong>Professional Recommendation:</strong> {result["recommendation"]}<br>
                            <strong>Alternative Strategy:</strong> Consider finding a more specific SOC code in Job Zone 4 or 5, or strengthen the specialty occupation argument with additional evidence.
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                        <div class="success-box">
                            <strong>[OK] SOC Code Analysis Result:</strong><br>
                            {result["message"]}<br>
                            <strong>Professional Recommendation:</strong> {result["recommendation"]}<br>
                            <strong>Next Steps:</strong> Verify job duties align with SOC code description and gather supporting industry evidence.
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
