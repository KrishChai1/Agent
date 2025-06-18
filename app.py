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
        "Other": {
            "K-1": "Fiancé(e) of US Citizen",
            "K-2": "Children of K-1",
            "T-1": "Victims of Human Trafficking",
            "U-1": "Victims of Criminal Activity"
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
            "VAWA": "Violence Against Women Act"
        },
        "Green Card Processes": {
            "I-485": "Adjustment of Status",
            "Consular Processing": "Immigrant Visa Processing Abroad",
            "I-601": "Inadmissibility Waiver",
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
            "N-600": "Certificate of Citizenship"
        },
        "Protection": {
            "Asylum": "Asylum Applications",
            "Withholding": "Withholding of Removal",
            "TPS": "Temporary Protected Status"
        },
        "Removal Defense": {
            "Cancellation": "Cancellation of Removal",
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

# SOC Code Database (Job Zone 3 codes to avoid)
JOB_ZONE_3_CODES = {
    "11-1011": "Chief Executives",
    "11-1021": "General and Operations Managers", 
    "11-2011": "Advertising and Promotions Managers",
    "11-2021": "Marketing Managers",
    "11-2022": "Sales Managers",
    "11-3011": "Administrative Services Managers",
    "11-3021": "Computer and Information Systems Managers",
    "11-3031": "Financial Managers"
}

def load_logo():
    """Load Lawtrax logo from file or create professional text logo"""
    try:
        if os.path.exists("assets/lawtrax_logo.png"):
            return Image.open("assets/lawtrax_logo.png")
        return None
    except Exception:
        return None

def call_openai_api(prompt, max_tokens=2000, temperature=0.3):
    """Call OpenAI API for immigration law assistance"""
    try:
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

def generate_immigration_response(case_type, visa_category, case_details):
    """Generate comprehensive immigration responses for any US visa type or immigration matter"""
    
    if case_type == "RFE Response":
        prompt = f"""
        As an expert immigration attorney, draft a comprehensive RFE response for a {visa_category} case.

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

        Format as a professional legal brief suitable for USCIS submission with proper citations.
        """
        
    elif case_type == "Expert Opinion":
        prompt = f"""
        Draft a professional expert opinion letter for an immigration case.

        Expert Details:
        - Position: {case_details.get('position', 'Not specified')}
        - Company: {case_details.get('company', 'Not specified')}
        - Industry: {case_details.get('industry', 'Not specified')}

        The expert opinion should:
        1. Establish expert's credentials and industry experience
        2. Analyze the position's complexity and specialized knowledge requirements
        3. Confirm minimum education requirements for the role
        4. Compare to industry standards and practices
        5. Provide professional opinion on necessity of degree requirement

        Format as a formal expert declaration suitable for immigration submission.
        """

    else:  # General Immigration Guidance
        prompt = f"""
        As an expert immigration attorney, provide comprehensive guidance on:

        Question: {case_details.get('question', 'Not specified')}
        Visa Category: {visa_category}
        
        Provide:
        1. Direct answer to the question
        2. Relevant legal citations (CFR, INA, etc.)
        3. Current policy guidance
        4. Practical considerations and best practices
        5. Recent case law if applicable
        6. Risk analysis and recommendations

        Format as professional legal guidance with proper citations.
        """

    return call_openai_api(prompt, max_tokens=3000, temperature=0.2)

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
        All AI-generated content must be reviewed, verified, and approved by supervising counsel before use.
    </div>
    """, unsafe_allow_html=True)

    # Check API Configuration
    if hasattr(st, 'secrets') and "OPENAI_API_KEY" in st.secrets:
        st.markdown("""
        <div class="success-box">
            <strong>✅ System Status:</strong> Immigration Assistant is ready for professional use.
        </div>
        """, unsafe_allow_html=True)

    # Main content tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "💬 Legal Research", 
        "📄 RFE Responses", 
        "📝 Expert Opinions",
        "📊 Templates",
        "📚 Resources"
    ])

    with tab1:
        st.subheader("💬 Immigration Law Research Assistant")
        
        st.markdown("""
        <div class="info-box">
            <strong>Professional Research Tool:</strong> Ask complex immigration law questions and receive comprehensive, 
            citation-backed analysis suitable for attorney use.
        </div>
        """, unsafe_allow_html=True)
        
        question = st.text_area(
            "Enter your immigration law research question:",
            placeholder="Example: What are the latest USCIS policy updates for H-1B specialty occupation?",
            height=120
        )
        
        if st.button("🔍 Research Question", type="primary"):
            if question:
                with st.spinner("Conducting legal research..."):
                    response = generate_immigration_response("General", "General Immigration", {"question": question})
                    if response:
                        st.session_state.chat_history.append({
                            "question": question,
                            "answer": response,
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        })
                        
                        st.markdown("### 📝 Research Results")
                        st.markdown(f"""
                        <div class="professional-card">
                            <strong>Question:</strong> {question}<br><br>
                            {response}
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Download option
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"Legal_Research_{timestamp}.txt"
                        download_content = f"LAWTRAX IMMIGRATION RESEARCH\n{'='*50}\n\nQuestion: {question}\n\nResults: {response}\n\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        st.download_button(
                            "📥 Download Research",
                            data=download_content,
                            file_name=filename,
                            mime="text/plain"
                        )
            else:
                st.warning("Please enter a research question.")

        # Display recent research
        if st.session_state.chat_history:
            st.markdown("### 📚 Recent Research History")
            for i, chat in enumerate(reversed(st.session_state.chat_history[-3:])):
                with st.expander(f"📋 {chat['question'][:80]}... ({chat['timestamp']})"):
                    st.markdown(chat['answer'])

    with tab2:
        st.subheader("📄 RFE Response Generator")
        
        st.markdown("""
        <div class="rfe-box">
            <strong>🎯 Professional RFE Response Strategy:</strong><br>
            • Address all specific issues raised in the RFE<br>
            • Provide comprehensive legal analysis and supporting evidence<br>
            • Include relevant case law and regulatory citations<br>
            • Recommend expert opinions and additional documentation
        </div>
        """, unsafe_allow_html=True)
        
        # RFE Type Selection
        rfe_type = st.selectbox(
            "Select RFE Type:",
            ["Specialty Occupation", "Beneficiary Qualifications", "Employer-Employee Relationship", "Wage Level"]
        )
        
        # Visa category selection
        visa_categories = []
        for main_cat, subcats in US_VISA_CATEGORIES.items():
            for subcat, visas in subcats.items():
                for visa_code, visa_name in visas.items():
                    visa_categories.append(f"{visa_code} - {visa_name}")
        
        visa_category = st.selectbox(
            "Select Visa Type:",
            ["H-1B - Specialty Occupation Workers"] + sorted(visa_categories)
        )
        
        if rfe_type == "Specialty Occupation":
            col1, col2 = st.columns(2)
            with col1:
                position = st.text_input("Position Title")
                company = st.text_input("Company Name")
                industry = st.text_input("Industry")
                
            with col2:
                soc_code = st.text_input("SOC Code")
                education_req = st.selectbox("Education Requirement", [
                    "Bachelor's Degree", "Master's Degree", "Bachelor's + Experience"
                ])
            
            job_duties = st.text_area("Detailed Job Duties", height=100)
            rfe_issues = st.text_area("RFE Issues Raised", height=100)
            
            if st.button("🚀 Generate RFE Response", type="primary"):
                if position and rfe_issues:
                    # Check SOC code if provided
                    if soc_code:
                        soc_result = check_soc_code(soc_code)
                        if soc_result["status"] == "WARNING":
                            st.markdown(f"""
                            <div class="warning-box">
                                {soc_result["message"]}<br>
                                <strong>Recommendation:</strong> {soc_result["recommendation"]}
                            </div>
                            """, unsafe_allow_html=True)
                    
                    case_details = {
                        "position": position,
                        "company": company,
                        "industry": industry,
                        "soc_code": soc_code,
                        "education_req": education_req,
                        "job_duties": job_duties,
                        "rfe_issues": rfe_issues
                    }
                    
                    with st.spinner("Generating comprehensive RFE response..."):
                        response = generate_immigration_response("RFE Response", visa_category, case_details)
                        if response:
                            st.subheader("📄 Specialty Occupation RFE Response")
                            st.markdown(f"""
                            <div class="professional-card">
                                {response}
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Download option
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            filename = f"RFE_Response_{timestamp}.txt"
                            download_content = f"LAWTRAX IMMIGRATION SERVICES\nRFE RESPONSE\n{'='*60}\n\n{response}\n\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                            st.download_button(
                                "📥 Download Response",
                                data=download_content,
                                file_name=filename,
                                mime="text/plain"
                            )
                else:
                    st.warning("Please provide position title and RFE issues.")

    with tab3:
        st.subheader("📝 Expert Opinion Letter Generator")
        
        st.markdown("""
        <div class="info-box">
            <strong>💡 Expert Opinion Services:</strong> Generate professional expert opinion letters 
            for any type of US immigration case.
        </div>
        """, unsafe_allow_html=True)
        
        expert_type = st.selectbox(
            "Select Expert Opinion Type:",
            ["Position Expert Opinion", "Beneficiary Qualifications", "Industry Standards", "Extraordinary Ability"]
        )
        
        col1, col2 = st.columns(2)
        with col1:
            expert_position = st.text_input("Position Title", key="expert_pos")
            expert_company = st.text_input("Company Name", key="expert_company")
            expert_industry = st.text_input("Industry", key="expert_industry")
            
        with col2:
            expert_education = st.text_input("Education Requirement", key="expert_edu")
            expert_duties = st.text_area("Job Duties", height=100, key="expert_duties")
        
        if st.button("📝 Generate Expert Opinion", type="primary"):
            if expert_position:
                case_details = {
                    "position": expert_position,
                    "company": expert_company,
                    "industry": expert_industry,
                    "education_req": expert_education,
                    "job_duties": expert_duties
                }
                
                with st.spinner("Generating expert opinion letter..."):
                    letter = generate_immigration_response("Expert Opinion", expert_type, case_details)
                    if letter:
                        st.subheader("📝 Expert Opinion Letter")
                        st.markdown(f"""
                        <div class="professional-card">
                            {letter}
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Download option
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"Expert_Opinion_{timestamp}.txt"
                        download_content = f"LAWTRAX IMMIGRATION SERVICES\nEXPERT OPINION LETTER\n{'='*60}\n\n{letter}\n\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        st.download_button(
                            "📥 Download Letter",
                            data=download_content,
                            file_name=filename,
                            mime="text/plain"
                        )
            else:
                st.warning("Please provide position details.")

    with tab4:
        st.subheader("📊 Professional Templates & Checklists")
        
        template_type = st.selectbox(
            "Select Template:",
            ["H-1B Filing Checklist", "Green Card Process", "RFE Response Framework", "Expert Opinion Guide"]
        )
        
        if template_type == "H-1B Filing Checklist":
            st.markdown("""
            <div class="professional-card">
                <h4>✅ H-1B Initial Filing Checklist</h4>
                
                <strong>📋 Required Forms:</strong>
                <ul>
                    <li>Form I-129 (signed by authorized representative)</li>
                    <li>H Classification Supplement</li>
                    <li>LCA (certified by DOL)</li>
                    <li>Filing fees ($460 + additional fees)</li>
                </ul>
                
                <strong>🏢 Employer Documentation:</strong>
                <ul>
                    <li>Detailed support letter</li>
                    <li>Company organizational chart</li>
                    <li>Job description with requirements</li>
                    <li>Evidence of business operations</li>
                </ul>
                
                <strong>👤 Beneficiary Documentation:</strong>
                <ul>
                    <li>Educational credentials and evaluation</li>
                    <li>Resume/CV</li>
                    <li>Experience letters (if applicable)</li>
                    <li>Copy of passport</li>
                </ul>
                
                <strong>🎯 Specialty Occupation Evidence:</strong>
                <ul>
                    <li>Industry standards documentation</li>
                    <li>Job postings requiring degree</li>
                    <li>Expert opinion letter (recommended)</li>
                    <li>Professional association requirements</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
            
        elif template_type == "Green Card Process":
            st.markdown("""
            <div class="professional-card">
                <h4>🟢 Green Card Process Overview</h4>
                
                <strong>Employment-Based Green Cards:</strong>
                <ul>
                    <li><strong>EB-1:</strong> Priority Workers (Extraordinary Ability, Outstanding Researchers, Multinational Executives)</li>
                    <li><strong>EB-2:</strong> Advanced Degree Professionals, National Interest Waiver</li>
                    <li><strong>EB-3:</strong> Skilled Workers and Professionals</li>
                    <li><strong>EB-5:</strong> Immigrant Investors</li>
                </ul>
                
                <strong>Family-Based Green Cards:</strong>
                <ul>
                    <li><strong>Immediate Relatives:</strong> Spouses, unmarried children under 21, parents of US citizens</li>
                    <li><strong>Preference Categories:</strong> F1, F2A, F2B, F3, F4</li>
                </ul>
                
                <strong>Process Steps:</strong>
                <ul>
                    <li>1. Immigrant Petition (I-130/I-140)</li>
                    <li>2. Priority Date and Visa Bulletin</li>
                    <li>3. Adjustment of Status (I-485) or Consular Processing</li>
                    <li>4. Green Card Issuance</li>
                </ul>
                
                <strong>Key Considerations:</strong>
                <ul>
                    <li>Priority date retrogression</li>
                    <li>Per-country limits</li>
                    <li>Concurrent filing eligibility</li>
                    <li>Maintaining status during process</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)

    with tab5:
        st.subheader("📚 Legal Resources & Updates")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            <div class="professional-card">
                <h4>📖 Key Immigration Regulations</h4>
                <ul>
                    <li><strong>8 CFR 214.2(h)</strong> - H Classification Requirements</li>
                    <li><strong>INA 214(i)(1)</strong> - H-1B Statutory Requirements</li>
                    <li><strong>8 CFR 204</strong> - Immigrant Petitions</li>
                    <li><strong>8 CFR 245</strong> - Adjustment of Status</li>
                </ul>
                
                <h4>🏛️ Important Cases</h4>
                <ul>
                    <li><em>Defensor v. Meissner</em> (1999) - Specialty Occupation</li>
                    <li><em>Royal Siam Corp. v. Chertoff</em> (2007) - H-1B Standards</li>
                    <li><em>Kazarian v. USCIS</em> (2010) - EB-1A Analysis</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
            
        with col2:
            st.markdown("""
            <div class="professional-card">
                <h4>📋 USCIS Resources</h4>
                <ul>
                    <li><strong>USCIS Policy Manual</strong> - Current guidance</li>
                    <li><strong>Processing Times</strong> - Updated monthly</li>
                    <li><strong>Fee Schedule</strong> - Current filing fees</li>
                    <li><strong>Forms and Instructions</strong> - Latest versions</li>
                </ul>
                
                <h4>🔧 Professional Tools</h4>
                <ul>
                    <li><strong>SOC Code Database</strong> - Job classifications</li>
                    <li><strong>Visa Bulletin</strong> - Priority dates</li>
                    <li><strong>Case Status</strong> - Application tracking</li>
                    <li><strong>Premium Processing</strong> - Expedited service</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
        
        # SOC Code Checker
        st.markdown("### 🔧 SOC Code Checker")
        soc_input = st.text_input("Enter SOC Code (e.g., 15-1132)")
        if st.button("🔍 Check SOC Code"):
            if soc_input:
                result = check_soc_code(soc_input.strip())
                if result["status"] == "WARNING":
                    st.markdown(f"""
                    <div class="warning-box">
                        {result["message"]}<br>
                        <strong>Recommendation:</strong> {result["recommendation"]}
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div class="success-box">
                        {result["message"]}<br>
                        <strong>Recommendation:</strong> {result["recommendation"]}
                    </div>
                    """, unsafe_allow_html=True)

    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666; padding: 2rem;'>
        <div style='display: flex; justify-content: center; align-items: center; gap: 10px; margin-bottom: 1rem;'>
            <div style='background: #1e3a8a; color: white; padding: 8px 16px; border-radius: 8px; font-weight: bold;'>LAWTRAX</div>
            <span>Immigration Law Assistant</span>
        </div>
        <p><strong>Professional AI-Powered Legal Technology</strong> | For Licensed Immigration Attorneys Only</p>
        <small>All AI-generated content requires review by qualified legal counsel.</small>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
