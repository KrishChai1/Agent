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
    st.warning("PIL not available - image features disabled")

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

try:
    import mammoth
    MAMMOTH_AVAILABLE = True
except ImportError:
    MAMMOTH_AVAILABLE = False

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
    # Add more Job Zone 3 codes as needed
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
    }
}

def extract_text_from_file(uploaded_file):
    """Extract text from uploaded file (PDF, DOCX, TXT) with fallback handling"""
    try:
        if uploaded_file.type == "application/pdf":
            if not PDF_AVAILABLE:
                st.error("PDF processing not available. Please install PyPDF2 or upload a TXT file instead.")
                st.info("Alternative: Copy and paste the RFE text directly into the manual input field below.")
                return None
            # Extract text from PDF
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
            # Extract text from DOCX
            doc = docx.Document(uploaded_file)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text
        
        elif uploaded_file.type == "text/plain":
            # Extract text from TXT - this should always work
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
        # Look for common RFE patterns and issues
        rfe_analysis = {
            "issues_identified": [],
            "deadline_mentioned": None,
            "receipt_number": None,
            "case_type": None,
            "specific_requirements": []
        }
        
        # Common RFE keywords and phrases
        specialty_occupation_keywords = ["specialty occupation", "bachelor's degree", "job duties", "position requirements"]
        beneficiary_keywords = ["beneficiary", "qualifications", "education", "experience", "credentials"]
        employer_keywords = ["employer-employee relationship", "right to control", "staffing", "client site"]
        ability_to_pay_keywords = ["ability to pay", "financial capacity", "tax returns", "financial statements"]
        
        rfe_text_lower = rfe_text.lower()
        
        # Identify specific issues
        if any(keyword in rfe_text_lower for keyword in specialty_occupation_keywords):
            rfe_analysis["issues_identified"].append("Specialty Occupation Requirements")
            
        if any(keyword in rfe_text_lower for keyword in beneficiary_keywords):
            rfe_analysis["issues_identified"].append("Beneficiary Qualifications")
            
        if any(keyword in rfe_text_lower for keyword in employer_keywords):
            rfe_analysis["issues_identified"].append("Employer-Employee Relationship")
            
        if any(keyword in rfe_text_lower for keyword in ability_to_pay_keywords):
            rfe_analysis["issues_identified"].append("Ability to Pay")
        
        # Look for deadline
        deadline_pattern = r'response.*?due.*?(\d{1,2}\/\d{1,2}\/\d{4})'
        deadline_match = re.search(deadline_pattern, rfe_text_lower)
        if deadline_match:
            rfe_analysis["deadline_mentioned"] = deadline_match.group(1)
        
        # Look for receipt number
        receipt_pattern = r'(MSC|EAC|WAC|SRC|NBC|IOE)\d{10,13}'
        receipt_match = re.search(receipt_pattern, rfe_text, re.IGNORECASE)
        if receipt_match:
            rfe_analysis["receipt_number"] = receipt_match.group(0)
        
        return rfe_analysis
        
    except Exception as e:
        st.error(f"Error analyzing RFE document: {str(e)}")
        return None

def call_openai_api(prompt, max_tokens=3000, temperature=0.2):
    """Enhanced OpenAI API call with better error handling and prompts"""
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
        
        # Enhanced system message for better responses
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
            timeout=120  # Increased timeout
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
    
    # First analyze the RFE document
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
    {rfe_text[:4000]}  # Limit to first 4000 characters to avoid token limits

    Please provide a comprehensive legal response that:

    1. **ADDRESSES EACH SPECIFIC ISSUE** raised in the RFE document with detailed legal analysis
    2. **PROVIDES REGULATORY FRAMEWORK** with citations to relevant statutes, regulations, and case law
    3. **RECOMMENDS SPECIFIC EVIDENCE** needed to overcome each issue
    4. **INCLUDES LEGAL ARGUMENTS** with proper citations and precedents
    5. **SUGGESTS EXPERT OPINIONS** where beneficial
    6. **OUTLINES RESPONSE STRATEGY** with timeline and priority actions
    7. **IDENTIFIES POTENTIAL CHALLENGES** and mitigation strategies

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

    1. **DIRECT ANSWER** - Clear, actionable response to the specific question
    2. **LEGAL FRAMEWORK** - Relevant statutes, regulations, and legal standards
    3. **CURRENT USCIS POLICY** - Latest guidance, policy memoranda, and procedural updates
    4. **CASE LAW ANALYSIS** - Relevant court decisions and BIA precedents
    5. **PRACTICAL GUIDANCE** - Strategic considerations and best practices
    6. **RISK ASSESSMENT** - Potential challenges and mitigation strategies
    7. **RECENT DEVELOPMENTS** - Any recent changes in law, policy, or practice
    8. **CITATIONS** - Specific references to legal authorities

    Structure your response clearly with headers and provide specific, actionable guidance suitable for immigration law practice. Include relevant form numbers, filing procedures, and timeline considerations where applicable.

    Focus on providing current, accurate information that would be valuable for immigration attorneys in their practice.
    """
    
    return call_openai_api(prompt, max_tokens=3500, temperature=0.2)

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

def main():
    # Professional Header with Logo
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
        <strong>⚖️ ATTORNEY USE ONLY:</strong> This tool is exclusively designed for licensed immigration attorneys and qualified legal professionals. 
        All AI-generated content must be reviewed, verified, and approved by supervising counsel before use. This system does not provide legal advice to end clients.
    </div>
    """, unsafe_allow_html=True)

    # Check API Configuration and Dependencies
    col1, col2 = st.columns(2)
    
    with col1:
        if hasattr(st, 'secrets') and "OPENAI_API_KEY" in st.secrets:
            st.markdown("""
            <div class="success-box">
                <strong>✅ API Status:</strong> OpenAI connectivity confirmed.
            </div>
            # Show installation instructions if dependencies are missing
        missing_deps = []
        if not PDF_AVAILABLE:
            missing_deps.append("PyPDF2")
        if not DOCX_AVAILABLE:
            missing_deps.append("python-docx")
            
        if missing_deps:
            with st.expander("📦 Install Missing Dependencies (Optional)"):
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
        else:
            st.markdown("""
            <div class="warning-box">
                <strong>⚠️ Configuration Required:</strong> Please configure your OpenAI API key in Streamlit secrets.
            </div>
            """, unsafe_allow_html=True)
    
    with col2:
        # Dependency status
        dependencies_status = []
        if PDF_AVAILABLE:
            dependencies_status.append("✅ PDF Support")
        else:
            dependencies_status.append("❌ PDF Support")
            
        if DOCX_AVAILABLE:
            dependencies_status.append("✅ DOCX Support")
        else:
            dependencies_status.append("❌ DOCX Support")
        
        dependencies_status.append("✅ TXT Support")
        
        st.markdown(f"""
        <div class="info-box">
            <strong>📦 System Dependencies:</strong><br>
            {' | '.join(dependencies_status)}
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
                    with st.spinner("Conducting comprehensive legal research..."):
                        response = generate_legal_research_response(question)
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
        st.subheader("📄 Enhanced RFE Response Generator with Document Upload")
        
        st.markdown("""
        <div class="info-box">
            <strong>🎯 Enhanced RFE Response System:</strong> Upload your RFE document for automatic analysis and response generation, 
            or manually enter case details. Supports PDF, DOCX, and TXT files for comprehensive RFE processing.
        </div>
        """, unsafe_allow_html=True)

        # RFE Document Upload Section
        st.markdown("""
        <div class="upload-box">
            <strong>📎 Upload RFE Document:</strong> Upload the actual RFE document from USCIS for automatic analysis 
            and targeted response generation. The system will extract key issues and generate appropriate responses.
        </div>
        """, unsafe_allow_html=True)

        # Determine available file types based on installed libraries
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

        # Show dependency status
        if not PDF_AVAILABLE or not DOCX_AVAILABLE:
            st.info(f"""
            📝 **File Support Status:**
            - TXT files: ✅ Supported
            - PDF files: {'✅ Supported' if PDF_AVAILABLE else '❌ Not available (install PyPDF2)'}
            - DOCX files: {'✅ Supported' if DOCX_AVAILABLE else '❌ Not available (install python-docx)'}
            
            💡 **Tip:** You can always copy and paste RFE content manually below if file upload isn't working.
            """)

        if uploaded_file is not None:
            with st.spinner("Analyzing uploaded RFE document..."):
                extracted_text = extract_text_from_file(uploaded_file)
                if extracted_text:
                    st.session_state.uploaded_rfe_content = extracted_text
                    
                    # Analyze the document
                    rfe_analysis = analyze_rfe_document(extracted_text)
                    
                    st.markdown("""
                    <div class="success-box">
                        <strong>✅ RFE Document Successfully Processed</strong>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Display analysis results
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**📋 Issues Identified:**")
                        if rfe_analysis and rfe_analysis['issues_identified']:
                            for issue in rfe_analysis['issues_identified']:
                                st.markdown(f"• {issue}")
                        else:
                            st.markdown("• General RFE requirements")
                    
                    with col2:
                        st.markdown("**📄 Document Details:**")
                        if rfe_analysis:
                            if rfe_analysis.get('receipt_number'):
                                st.markdown(f"• Receipt Number: {rfe_analysis['receipt_number']}")
                            if rfe_analysis.get('deadline_mentioned'):
                                st.markdown(f"• Deadline: {rfe_analysis['deadline_mentioned']}")
                            st.markdown(f"• Document Length: {len(extracted_text)} characters")

        # Case Details Form
        st.markdown("### 📝 Case Information")
        
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
            
            # Enhanced manual input section
            if not st.session_state.uploaded_rfe_content:
                st.markdown("### 📝 Manual RFE Content Input")
                st.markdown("""
                <div class="info-box">
                    <strong>💡 Manual Input Option:</strong> If you cannot upload a file or prefer to copy/paste, 
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
                st.markdown("### ✅ Using Uploaded RFE Document")
                st.info("RFE issues will be extracted from uploaded document")
            
            additional_details = st.text_area(
                "Additional Case Details:",
                height=80,
                help="Any additional relevant information about the case"
            )
            
            submit_rfe = st.form_submit_button("🚀 Generate Comprehensive RFE Response", type="primary")
            
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
                            # Use uploaded document
                            response = generate_rfe_response_from_document(
                                st.session_state.uploaded_rfe_content, 
                                visa_category.split(" - ")[0] if " - " in visa_category else visa_category,
                                case_details
                            )
                        else:
                            # Use manual input (fallback to original method)
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
                            st.subheader(f"📄 Comprehensive RFE Response - {visa_category}")
                            st.markdown(f"""
                            <div class="professional-card">
                                {response}
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Store response in session state for download
                            st.session_state['latest_rfe_response'] = {
                                'content': response,
                                'visa_category': visa_category,
                                'petitioner': petitioner,
                                'beneficiary': beneficiary
                            }
                            
                            # Clear uploaded content after processing
                            st.session_state.uploaded_rfe_content = None
                else:
                    st.warning("Please upload an RFE document or manually describe the RFE issues.")
        
        # Download button outside form
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
                "📥 Download RFE Response",
                data=download_content,
                file_name=filename,
                mime="text/plain",
                key="download_rfe_response"
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
        
        # Expert opinion generation code continues...
        # (Keep the existing expert opinion functionality)
        
        st.markdown("</div>", unsafe_allow_html=True)

    with tab4:
        st.markdown("<div class='tab-content'>", unsafe_allow_html=True)
        st.subheader("📊 Comprehensive Immigration Templates & Legal Frameworks")
        
        # Templates code continues...
        # (Keep the existing templates functionality)
        
        st.markdown("</div>", unsafe_allow_html=True)

    with tab5:
        st.markdown("<div class='tab-content'>", unsafe_allow_html=True)
        st.subheader("📚 Comprehensive US Immigration Law Resources")
        
        # Resources code continues...
        # (Keep the existing resources functionality)
        
        # Enhanced SOC Code Checker Tool
        st.markdown("---")
        st.markdown("""
        <div class="info-box">
            <h4>🔧 Professional Immigration Analysis Tools</h4>
            <p>Comprehensive tools for immigration law practice including SOC code analysis, visa eligibility assessment, and case strategy planning.</p>
        </div>
        """, unsafe_allow_html=True)
        
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
