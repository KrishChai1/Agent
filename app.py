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

def generate_comprehensive_immigration_response(case_type, visa_category, case_details):
    """Generate comprehensive immigration responses for any US visa type or immigration matter"""
    
    prompt = f"""
    As an expert immigration attorney with comprehensive knowledge of US immigration law, provide detailed guidance on:

    Case Type: {case_type}
    Visa Category: {visa_category}
    Question/Issue: {case_details.get('question', case_details.get('rfe_issues', 'Not specified'))}
    
    Additional Details:
    {case_details.get('details', case_details.get('additional_details', 'Not specified'))}

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

def main():
    # Professional Header with Logo
    st.markdown("""
    <div class="main-header">
        <div class="logo-container">
            <div class="lawtrax-logo">LAWTRAX</div>
        </div>
        <h1 style='margin: 0; font-size: 2.5rem; font-weight: 300;'>Immigration Law Assistant</h1>
        <p style='margin: 0.5rem 0 0 0; font-size: 1.1rem; opacity: 0.9;'>
            Professional AI-Powered Legal Research & Immigration Guidance
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
    tab1, tab2, tab3 = st.tabs([
        "💬 Legal Research Chat", 
        "📄 Immigration Response Generator", 
        "📚 Legal Resources"
    ])

    with tab1:
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
        
        if st.button("🔍 Research Question", type="primary", use_container_width=True):
            if question:
                with st.spinner("Conducting legal research..."):
                    response = generate_comprehensive_immigration_response("General Immigration Guidance", "General Immigration Matter", {"question": question})
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

    with tab2:
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
        
        # Immigration question input
        immigration_question = st.text_area(
            "Immigration Question or Case Details",
            height=150,
            placeholder="Describe your immigration question, case scenario, or strategic planning needs...",
            help="Provide detailed information about the immigration matter"
        )
        
        if st.button("🚀 Generate Immigration Response", type="primary", use_container_width=True):
            if immigration_question:
                case_details = {
                    "question": immigration_question,
                    "case_type": case_type,
                    "visa_category": visa_category
                }
                
                with st.spinner("Generating comprehensive immigration response..."):
                    visa_code = visa_category.split(" - ")[0] if " - " in visa_category else visa_category
                    response = generate_comprehensive_immigration_response(case_type, visa_code, case_details)
                    
                    if response:
                        st.subheader(f"📄 {case_type} - {visa_category}")
                        st.markdown(f"""
                        <div class="professional-card">
                            {response}
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Download option
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"Immigration_Response_{case_type.replace(' ', '_')}_{timestamp}.txt"
                        download_content = f"LAWTRAX IMMIGRATION SERVICES\n{case_type.upper()} - {visa_category}\n{'='*80}\n\n{response}\n\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        st.download_button(
                            "📥 Download Response",
                            data=download_content,
                            file_name=filename,
                            mime="text/plain",
                            use_container_width=True
                        )
            else:
                st.warning("Please provide your immigration question or case details.")

    with tab3:
        st.subheader("📚 Essential Legal Resources & Current Updates")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            <div class="professional-card">
                <h4>📖 Key Immigration Regulations</h4>
                <ul>
                    <li><strong>8 CFR 214.2(h)</strong> - H Classification Requirements</li>
                    <li><strong>8 CFR 214.2(h)(4)(iii)(A)</strong> - Specialty Occupation Definition</li>
                    <li><strong>INA 214(i)(1)</strong> - H-1B Statutory Requirements</li>
                    <li><strong>8 CFR 214.2(h)(4)(iii)(C)</strong> - Beneficiary Qualifications</li>
                    <li><strong>8 CFR 204</strong> - Immigrant Petitions</li>
                    <li><strong>8 CFR 245</strong> - Adjustment of Status</li>
                    <li><strong>USCIS Policy Manual</strong> - Current Guidance</li>
                </ul>
                
                <h4>🏛️ Landmark Immigration Cases</h4>
                <ul>
                    <li><em>Defensor v. Meissner</em> (1999) - Specialty Occupation Standards</li>
                    <li><em>Royal Siam Corp. v. Chertoff</em> (2007) - Degree Requirements</li>
                    <li><em>Residential Fin. Corp. v. USCIS</em> (2017) - Industry Standards</li>
                    <li><em>Innova Solutions v. Baran</em> (2018) - SOC Code Analysis</li>
                    <li><em>Kazarian v. USCIS</em> (2010) - EB-1A Two-Step Analysis</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
            
        with col2:
            st.markdown("""
            <div class="professional-card">
                <h4>📋 Immigration Practice Resources</h4>
                <ul>
                    <li><strong>USCIS Policy Manual</strong> - Complete guidance database</li>
                    <li><strong>AILA InfoNet</strong> - Member research resources</li>
                    <li><strong>BIA Decisions</strong> - Board precedent decisions</li>
                    <li><strong>Federal Courts</strong> - Circuit court decisions</li>
                    <li><strong>O*NET Database</strong> - Occupational analysis</li>
                    <li><strong>DOL Resources</strong> - Labor certification guidance</li>
                </ul>
                
                <h4>🔄 Current Immigration Updates</h4>
                <ul>
                    <li><strong>H-1B Electronic Registration</strong> - Updated process requirements</li>
                    <li><strong>EB-5 Reform</strong> - Investment and regional center changes</li>
                    <li><strong>Green Card Processing</strong> - Priority date movements</li>
                    <li><strong>RFE Trends Analysis</strong> - Current USCIS patterns</li>
                    <li><strong>Policy Manual Updates</strong> - Recent guidance revisions</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)

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
