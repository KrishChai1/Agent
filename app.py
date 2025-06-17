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
    initial_sidebar_state="expanded"
)

# Custom CSS for legal theme
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #1e3a8a 0%, #3b82f6 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .rfe-box {
        background: #fef3c7;
        border-left: 5px solid #f59e0b;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 5px;
    }
    .warning-box {
        background: #fee2e2;
        border-left: 5px solid #ef4444;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 5px;
    }
    .success-box {
        background: #d1fae5;
        border-left: 5px solid #10b981;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'case_details' not in st.session_state:
    st.session_state.case_details = {}
if 'github_data' not in st.session_state:
    st.session_state.github_data = {}

def load_logo():
    """Load Lawtrax logo from file or URL"""
    try:
        # Try to load logo from local file first
        if os.path.exists("assets/lawtrax_logo.png"):
            return Image.open("assets/lawtrax_logo.png")
        
        # Try to load from GitHub repository
        if hasattr(st, 'secrets') and "GITHUB_TOKEN" in st.secrets:
            github_token = st.secrets["GITHUB_TOKEN"]
            repo_url = st.secrets.get("LOGO_REPO_URL", "")
            
            if repo_url:
                headers = {"Authorization": f"token {github_token}"}
                response = requests.get(repo_url, headers=headers)
                if response.status_code == 200:
                    content = base64.b64decode(response.json()["content"])
                    return Image.open(BytesIO(content))
        
        # Fallback: Create a simple text logo
        return None
        
    except Exception as e:
        st.error(f"Error loading logo: {str(e)}")
        return None

def get_github_data(repo_owner, repo_name, file_path, github_token=None):
    """Fetch data from GitHub repository"""
    try:
        if not github_token:
            if hasattr(st, 'secrets') and "GITHUB_TOKEN" in st.secrets:
                github_token = st.secrets["GITHUB_TOKEN"]
            else:
                return None
        
        url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{file_path}"
        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            content = response.json()
            if content["encoding"] == "base64":
                decoded_content = base64.b64decode(content["content"]).decode('utf-8')
                return json.loads(decoded_content) if file_path.endswith('.json') else decoded_content
        return None
        
    except Exception as e:
        st.error(f"Error fetching GitHub data: {str(e)}")
        return None

def update_legal_database():
    """Update legal database from GitHub repository"""
    try:
        # Fetch latest SOC codes
        soc_data = get_github_data("lawtrax", "legal-database", "soc_codes/job_zones.json")
        if soc_data:
            st.session_state.github_data['soc_codes'] = soc_data
        
        # Fetch latest immigration updates
        updates_data = get_github_data("lawtrax", "legal-database", "updates/immigration_updates.json")
        if updates_data:
            st.session_state.github_data['legal_updates'] = updates_data
        
        # Fetch case templates
        templates_data = get_github_data("lawtrax", "legal-database", "templates/rfe_templates.json")
        if templates_data:
            st.session_state.github_data['templates'] = templates_data
            
        return True
    except Exception as e:
        st.error(f"Error updating legal database: {str(e)}")
        return False

def trigger_github_action(repo_owner, repo_name, workflow_id, inputs=None):
    """Trigger GitHub Action workflow"""
    try:
        github_token = st.secrets.get("GITHUB_TOKEN")
        if not github_token:
            return None
            
        url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/actions/workflows/{workflow_id}/dispatches"
        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        data = {
            "ref": "main",
            "inputs": inputs or {}
        }
        
        response = requests.post(url, headers=headers, json=data)
        return response.status_code == 204
        
    except Exception as e:
        st.error(f"Error triggering GitHub Action: {str(e)}")
        return False

# SOC Code Database (Job Zone 3 codes to avoid)
JOB_ZONE_3_CODES = {
    "11-1011": "Chief Executives",
    "11-1021": "General and Operations Managers", 
    "11-2011": "Advertising and Promotions Managers",
    "11-2021": "Marketing Managers",
    "11-2022": "Sales Managers",
    "11-3011": "Administrative Services Managers",
    "11-3021": "Computer and Information Systems Managers",
    "11-3031": "Financial Managers",
    "11-3041": "Compensation and Benefits Managers",
    "11-3042": "Training and Development Managers",
    "11-3049": "Human Resources Managers, All Other",
    "11-3051": "Industrial Production Managers",
    "11-3061": "Purchasing Managers",
    "11-3071": "Transportation, Storage, and Distribution Managers",
    "11-9013": "Farmers, Ranchers, and Other Agricultural Managers",
    "11-9021": "Construction Managers",
    "11-9039": "Education Administrators, All Other",
    "11-9041": "Architectural and Engineering Managers",
    "11-9051": "Food Service Managers",
    "11-9081": "Lodging Managers",
    "11-9111": "Medical and Health Services Managers",
    "11-9121": "Natural Sciences Managers",
    "11-9131": "Postmasters and Mail Superintendents",
    "11-9141": "Property, Real Estate, and Community Association Managers",
    "11-9151": "Social and Community Service Managers"
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
            st.error("❌ OpenAI API key not found. Please add it to your Streamlit secrets.")
            return None
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "gpt-4",  # Using GPT-4 for legal accuracy
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

def generate_rfe_response(rfe_type, case_details):
    """Generate RFE response based on type and case details"""
    
    if rfe_type == "Specialty Occupation":
        prompt = f"""
        As an expert immigration attorney, draft a comprehensive response to a Specialty Occupation RFE for an H-1B petition.

        Case Details:
        - Position: {case_details.get('position', 'Not specified')}
        - Company: {case_details.get('company', 'Not specified')} 
        - Industry: {case_details.get('industry', 'Not specified')}
        - Job Duties: {case_details.get('job_duties', 'Not specified')}
        - Education Requirement: {case_details.get('education_req', 'Not specified')}
        - SOC Code: {case_details.get('soc_code', 'Not specified')}

        Requirements for response:
        1. Establish the position qualifies as a specialty occupation under 8 CFR 214.2(h)(4)(iii)(A)
        2. Address all four prongs of specialty occupation criteria
        3. Provide industry evidence and expert opinion
        4. Avoid SOC codes in Job Zone 3
        5. Include relevant case law and precedents
        6. Draft professional, persuasive legal arguments

        Format the response as a formal legal brief with proper citations and structure.
        """
        
    elif rfe_type == "Beneficiary Qualifications":
        prompt = f"""
        As an expert immigration attorney, draft a comprehensive response to a Beneficiary Qualifications RFE for an H-1B petition.

        Beneficiary Details:
        - Name: {case_details.get('beneficiary_name', 'Not specified')}
        - Education: {case_details.get('education', 'Not specified')}
        - Degree Field: {case_details.get('degree_field', 'Not specified')}
        - Work Experience: {case_details.get('experience', 'Not specified')}
        - Position: {case_details.get('position', 'Not specified')}

        Requirements for response:
        1. Demonstrate beneficiary meets minimum education requirements
        2. Address any degree-to-position relationship concerns
        3. Utilize experience letters if degree is unrelated
        4. Apply three-for-one rule if applicable (3 years experience = 1 year education)
        5. Include expert evaluation of credentials
        6. Provide credential evaluation if foreign degree
        7. Draft expert opinion letter on beneficiary qualifications

        Format as a formal legal response with supporting documentation recommendations.
        """

    else:  # General Immigration Question
        prompt = f"""
        As an expert immigration attorney and researcher, provide a comprehensive answer to this immigration law question:

        Question: {case_details.get('question', 'Not specified')}

        Provide:
        1. Direct answer to the question
        2. Relevant legal citations (CFR, INA, etc.)
        3. Current policy guidance or memos
        4. Practical considerations and best practices
        5. Recent case law or precedents if applicable
        6. Risk analysis and recommendations
        7. Alternative approaches if relevant

        Format as professional legal guidance with proper citations.
        """

    return call_openai_api(prompt, max_tokens=3000, temperature=0.2)

def generate_expert_opinion_letter(letter_type, case_details):
    """Generate expert opinion letter for immigration cases"""
    
    if letter_type == "Position Expert Opinion":
        prompt = f"""
        Draft an expert opinion letter for an H-1B specialty occupation case from an industry expert's perspective.

        Position Details:
        - Position Title: {case_details.get('position', 'Not specified')}
        - Company: {case_details.get('company', 'Not specified')}
        - Industry: {case_details.get('industry', 'Not specified')}
        - Job Duties: {case_details.get('job_duties', 'Not specified')}
        - Education Requirement: {case_details.get('education_req', 'Not specified')}

        The expert opinion should:
        1. Establish expert's credentials and industry experience
        2. Analyze the position's complexity and specialized knowledge requirements
        3. Confirm minimum education requirements for the role
        4. Compare to industry standards and practices
        5. Address specialty occupation criteria under INA 214(i)(1)
        6. Provide professional opinion on necessity of degree requirement

        Format as a formal expert declaration with professional letterhead structure.
        """
        
    elif letter_type == "Beneficiary Qualifications Expert Opinion":
        prompt = f"""
        Draft an expert opinion letter evaluating a beneficiary's qualifications for an H-1B position.

        Beneficiary & Position Details:
        - Beneficiary: {case_details.get('beneficiary_name', 'Not specified')}
        - Education: {case_details.get('education', 'Not specified')}
        - Experience: {case_details.get('experience', 'Not specified')}
        - Position: {case_details.get('position', 'Not specified')}
        - Job Duties: {case_details.get('job_duties', 'Not specified')}

        The expert opinion should:
        1. Evaluate beneficiary's educational background
        2. Assess work experience and its relevance
        3. Apply equivalency standards if needed
        4. Address any education-position relationship concerns
        5. Confirm beneficiary meets minimum requirements
        6. Provide professional opinion on qualification sufficiency

        Format as a formal expert evaluation with credentials and detailed analysis.
        """

    return call_openai_api(prompt, max_tokens=2500, temperature=0.2)

def main():
    # Load and display logo
    logo = load_logo()
    
    # Header with logo
    col1, col2 = st.columns([1, 4])
    with col1:
        if logo:
            st.image(logo, width=150)
        else:
            st.markdown("""
            <div style='background: #1e3a8a; color: white; padding: 20px; border-radius: 10px; text-align: center; font-weight: bold; font-size: 24px;'>
                LAWTRAX
            </div>
            """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div style='padding: 20px 0;'>
            <h1 style='color: #1e3a8a; margin: 0;'>⚖️ Immigration Law Assistant</h1>
            <p style='color: #666; font-size: 18px; margin: 5px 0;'>Expert AI assistance for immigration attorneys • RFE Responses • Visa Filings • Legal Research</p>
        </div>
        """, unsafe_allow_html=True)

    # GitHub Data Status Bar
    if hasattr(st, 'secrets') and "GITHUB_TOKEN" in st.secrets:
        with st.expander("🔄 Data Sources & Updates"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("🔄 Update Legal Database"):
                    with st.spinner("Updating from GitHub..."):
                        success = update_legal_database()
                        if success:
                            st.success("✅ Database updated!")
                        else:
                            st.error("❌ Update failed")
            
            with col2:
                last_update = st.session_state.github_data.get('last_update', 'Never')
                st.info(f"📅 Last Update: {last_update}")
            
            with col3:
                data_status = "🟢 Connected" if st.session_state.github_data else "🔴 Disconnected"
                st.info(f"📡 GitHub Status: {data_status}")

    # Disclaimer
    st.markdown("""
    <div class="warning-box">
        <strong>⚠️ LEGAL DISCLAIMER:</strong> This tool is designed for licensed immigration attorneys and legal professionals. 
        All outputs should be reviewed by qualified counsel. This does not constitute legal advice for end clients.
    </div>
    """, unsafe_allow_html=True)

    # Sidebar for case management
    with st.sidebar:
        st.header("📋 Case Information")
        
        # Case tracking
        case_number = st.text_input("Case Number/Reference", help="Internal case tracking")
        client_name = st.text_input("Client Name")
        petition_type = st.selectbox("Petition Type", [
            "H-1B", "H-1B1", "E-3", "TN", "O-1", "L-1", "Other"
        ])
        
        st.markdown("---")
        st.header("🔧 Quick Tools")
        
        # SOC Code Checker
        st.subheader("SOC Code Checker")
        soc_input = st.text_input("Enter SOC Code (e.g., 15-1132)")
        if st.button("Check SOC Code"):
            if soc_input:
                result = check_soc_code(soc_input)
                if result["status"] == "WARNING":
                    st.markdown(f"""
                    <div class="warning-box">
                        {result["message"]}<br>
                        <strong>Position:</strong> {result["title"]}<br>
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

    # Main content tabs
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "💬 Immigration Chat", 
        "📄 RFE Response Generator", 
        "📝 Expert Opinion Letters",
        "📊 Case Templates",
        "📚 Legal Resources",
        "🔧 GitHub Services"
    ])

    with tab1:
        st.subheader("💬 Immigration Law Research Assistant")
        
        # Chat interface
        question = st.text_area(
            "Ask any immigration law question:",
            placeholder="e.g., What are the current processing times for H-1B cap cases? How do I respond to an RFE questioning specialty occupation?",
            height=100
        )
        
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("🔍 Research", type="primary"):
                if question:
                    with st.spinner("Researching immigration law..."):
                        response = generate_rfe_response("General", {"question": question})
                        if response:
                            st.session_state.chat_history.append({
                                "question": question,
                                "answer": response,
                                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            })
        
        # Display chat history
        if st.session_state.chat_history:
            st.markdown("### 📝 Research History")
            for i, chat in enumerate(reversed(st.session_state.chat_history[-5:])):  # Show last 5
                with st.expander(f"Q: {chat['question'][:100]}... ({chat['timestamp']})"):
                    st.markdown(chat['answer'])

    with tab2:
        st.subheader("📄 RFE Response Generator")
        
        rfe_type = st.selectbox(
            "Select RFE Type:",
            ["Specialty Occupation", "Beneficiary Qualifications", "Employer-Employee Relationship", "Wage Level"]
        )
        
        if rfe_type == "Specialty Occupation":
            st.markdown("""
            <div class="rfe-box">
                <strong>🎯 Specialty Occupation RFE Strategy:</strong><br>
                • Avoid SOC codes in Job Zone 3<br>
                • Focus on degree requirement necessity<br>
                • Provide industry evidence and expert opinions<br>
                • Address all four prongs of specialty occupation criteria
            </div>
            """, unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            with col1:
                position = st.text_input("Position Title")
                company = st.text_input("Company Name")
                industry = st.text_input("Industry")
                soc_code = st.text_input("SOC Code")
                
            with col2:
                education_req = st.selectbox("Education Requirement", [
                    "Bachelor's Degree", "Master's Degree", "Bachelor's + Experience", "Equivalent Experience"
                ])
                job_duties = st.text_area("Key Job Duties", height=100)
            
            case_details = {
                "position": position,
                "company": company,
                "industry": industry,
                "soc_code": soc_code,
                "education_req": education_req,
                "job_duties": job_duties
            }
        
        elif rfe_type == "Beneficiary Qualifications":
            st.markdown("""
            <div class="rfe-box">
                <strong>🎯 Beneficiary Qualifications RFE Strategy:</strong><br>
                • Address degree-to-position relationship<br>
                • Utilize experience letters for unrelated degrees<br>
                • Apply three-for-one rule when applicable<br>
                • Provide expert credential evaluation
            </div>
            """, unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            with col1:
                beneficiary_name = st.text_input("Beneficiary Name")
                education = st.text_input("Education (Degree, University)")
                degree_field = st.text_input("Degree Field/Major")
                
            with col2:
                experience = st.text_area("Work Experience Summary", height=80)
                position = st.text_input("H-1B Position")
            
            case_details = {
                "beneficiary_name": beneficiary_name,
                "education": education,
                "degree_field": degree_field,
                "experience": experience,
                "position": position
            }
        
        if st.button("🚀 Generate RFE Response", type="primary"):
            if any(case_details.values()):
                with st.spinner("Generating comprehensive RFE response..."):
                    response = generate_rfe_response(rfe_type, case_details)
                    if response:
                        st.subheader(f"📄 {rfe_type} RFE Response")
                        st.markdown(response)
                        
                        # Download option
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"RFE_Response_{rfe_type.replace(' ', '_')}_{timestamp}.txt"
                        st.download_button(
                            "📥 Download Response",
                            data=response,
                            file_name=filename,
                            mime="text/plain"
                        )
            else:
                st.warning("Please fill in the case details before generating a response.")

    with tab3:
        st.subheader("📝 Expert Opinion Letter Generator")
        
        letter_type = st.selectbox(
            "Select Expert Opinion Type:",
            ["Position Expert Opinion", "Beneficiary Qualifications Expert Opinion"]
        )
        
        if letter_type == "Position Expert Opinion":
            st.info("💡 Generate expert opinion letters from industry professionals about position requirements")
            
            col1, col2 = st.columns(2)
            with col1:
                position = st.text_input("Position Title", key="expert_pos")
                company = st.text_input("Company Name", key="expert_company") 
                industry = st.text_input("Industry/Field", key="expert_industry")
                
            with col2:
                education_req = st.text_input("Education Requirement", key="expert_edu")
                job_duties = st.text_area("Detailed Job Duties", height=100, key="expert_duties")
            
            expert_case_details = {
                "position": position,
                "company": company,
                "industry": industry,
                "education_req": education_req,
                "job_duties": job_duties
            }
            
        elif letter_type == "Beneficiary Qualifications Expert Opinion":
            st.info("💡 Generate expert evaluations of beneficiary education and experience qualifications")
            
            col1, col2 = st.columns(2)
            with col1:
                beneficiary_name = st.text_input("Beneficiary Name", key="qual_name")
                education = st.text_area("Education Background", height=80, key="qual_edu")
                experience = st.text_area("Work Experience", height=80, key="qual_exp")
                
            with col2:
                position = st.text_input("H-1B Position", key="qual_pos")
                job_duties = st.text_area("Position Duties", height=100, key="qual_duties")
            
            expert_case_details = {
                "beneficiary_name": beneficiary_name,
                "education": education,
                "experience": experience,
                "position": position,
                "job_duties": job_duties
            }
        
        if st.button("📝 Generate Expert Opinion Letter", type="primary"):
            if any(expert_case_details.values()):
                with st.spinner("Generating expert opinion letter..."):
                    letter = generate_expert_opinion_letter(letter_type, expert_case_details)
                    if letter:
                        st.subheader(f"📝 {letter_type}")
                        st.markdown(letter)
                        
                        # Download option
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"Expert_Opinion_{letter_type.replace(' ', '_')}_{timestamp}.txt"
                        st.download_button(
                            "📥 Download Letter",
                            data=letter,
                            file_name=filename,
                            mime="text/plain"
                        )
            else:
                st.warning("Please provide case details before generating the expert opinion letter.")

    with tab4:
        st.subheader("📊 Case Templates & Checklists")
        
        template_type = st.selectbox(
            "Select Template:",
            ["H-1B Initial Filing Checklist", "RFE Response Checklist", "Specialty Occupation Arguments", "Common RFE Issues"]
        )
        
        if template_type == "H-1B Initial Filing Checklist":
            st.markdown("""
            ### ✅ H-1B Initial Filing Checklist
            
            **Employer Documents:**
            - [ ] Form I-129 (signed)
            - [ ] LCA (certified)
            - [ ] Support letter detailing position
            - [ ] Company organizational chart
            - [ ] Job description with duties and requirements
            - [ ] Evidence of employer's business
            
            **Beneficiary Documents:**
            - [ ] Copy of passport and current status
            - [ ] Education credentials and evaluation
            - [ ] Resume/CV
            - [ ] Experience letters (if applicable)
            
            **Specialty Occupation Evidence:**
            - [ ] Industry publications/standards
            - [ ] Job postings for similar positions
            - [ ] Expert opinion letter (recommended)
            - [ ] Organizational chart showing position
            """)
            
        elif template_type == "Specialty Occupation Arguments":
            st.markdown("""
            ### 🎯 Specialty Occupation Arguments Framework
            
            **Prong 1: Degree normally required**
            - Industry standards and practices
            - Job postings requiring degree
            - Professional publications
            
            **Prong 2: Degree requirement is common**
            - Similar employers in industry
            - Industry surveys and data
            - Professional association standards
            
            **Prong 3: Employer normally requires degree**
            - Company hiring practices
            - Similar positions at employer
            - Organizational requirements
            
            **Prong 4: Specialized and complex**
            - Technical complexity of duties
            - Specialized knowledge required
            - Professional judgment needed
            """)

    with tab5:
        st.subheader("📚 Legal Resources & Updates")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            ### 📖 Key Regulations
            - **8 CFR 214.2(h)** - H Classification
            - **8 CFR 214.2(h)(4)(iii)(A)** - Specialty Occupation Definition
            - **INA 214(i)(1)** - H-1B Requirements
            - **AFM Chapter 31.3** - Specialty Occupations
            
            ### 🏛️ Important Cases
            - *Defensor v. Meissner* (1999)
            - *Royal Siam Corp. v. Chertoff* (2007)
            - *Residential Fin. Corp. v. USCIS* (2017)
            """)
            
        with col2:
            st.markdown("""
            ### 📋 SOC Code Resources
            - **Job Zone 4-5**: Generally acceptable for H-1B
            - **Job Zone 3**: Avoid for specialty occupation
            - **O*NET Database**: Detailed job analysis
            - **Bureau of Labor Statistics**: Official SOC definitions
            
            ### 🔄 Recent Updates
            - H-1B Electronic Registration
            - Wage Level Determinations
            - RFE Trends and Patterns
            """)

    with tab6:
        st.subheader("🔧 GitHub Services & Data Management")
        
        # GitHub Configuration
        st.markdown("### ⚙️ GitHub Integration Setup")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
            **Required GitHub Secrets:**
            ```toml
            GITHUB_TOKEN = "ghp_your_token_here"
            LOGO_REPO_URL = "https://api.github.com/repos/lawtrax/assets/contents/logo.png"
            ```
            """)
            
        with col2:
            github_status = "🟢 Connected" if hasattr(st, 'secrets') and "GITHUB_TOKEN" in st.secrets else "🔴 Not Connected"
            st.markdown(f"**GitHub Status:** {github_status}")
            
            if st.button("🔧 Test GitHub Connection"):
                if hasattr(st, 'secrets') and "GITHUB_TOKEN" in st.secrets:
                    test_data = get_github_data("lawtrax", "legal-database", "README.md")
                    if test_data:
                        st.success("✅ GitHub connection successful!")
                    else:
                        st.error("❌ GitHub connection failed")
                else:
                    st.error("❌ GitHub token not configured")
        
        st.markdown("---")
        
        # Data Sources Management
        st.markdown("### 📊 Data Sources")
        
        data_sources = [
            {
                "name": "SOC Codes Database",
                "repo": "lawtrax/legal-database",
                "path": "soc_codes/job_zones.json",
                "description": "Updated SOC codes with Job Zone classifications"
            },
            {
                "name": "Immigration Updates",
                "repo": "lawtrax/legal-database", 
                "path": "updates/immigration_updates.json",
                "description": "Latest immigration law changes and policy updates"
            },
            {
                "name": "RFE Templates",
                "repo": "lawtrax/legal-database",
                "path": "templates/rfe_templates.json", 
                "description": "Template responses for common RFE types"
            },
            {
                "name": "Case Law Database",
                "repo": "lawtrax/legal-database",
                "path": "case_law/immigration_cases.json",
                "description": "Recent immigration case law and precedents"
            }
        ]
        
        for source in data_sources:
            with st.expander(f"📁 {source['name']}"):
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    st.write(f"**Repository:** {source['repo']}")
                    st.write(f"**Path:** {source['path']}")
                    st.write(f"**Description:** {source['description']}")
                
                with col2:
                    if source['name'] in st.session_state.github_data:
                        st.success("✅ Data loaded")
                        last_update = st.session_state.github_data.get(f"{source['name']}_last_update", "Unknown")
                        st.write(f"Last update: {last_update}")
                    else:
                        st.warning("⚠️ Data not loaded")
                
                with col3:
                    if st.button(f"🔄 Update", key=f"update_{source['name']}"):
                        with st.spinner(f"Updating {source['name']}..."):
                            repo_parts = source['repo'].split('/')
                            data = get_github_data(repo_parts[0], repo_parts[1], source['path'])
                            if data:
                                st.session_state.github_data[source['name']] = data
                                st.session_state.github_data[f"{source['name']}_last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                st.success("✅ Updated!")
                            else:
                                st.error("❌ Failed to update")
        
        st.markdown("---")
        
        # GitHub Actions Integration
        st.markdown("### 🚀 GitHub Actions")
        
        action_col1, action_col2 = st.columns(2)
        
        with action_col1:
            st.markdown("**Available Workflows:**")
            workflows = [
                {"name": "Update Legal Database", "id": "update-legal-db.yml"},
                {"name": "Generate Case Reports", "id": "generate-reports.yml"},
                {"name": "Backup Client Data", "id": "backup-data.yml"}
            ]
            
            selected_workflow = st.selectbox("Select Workflow:", [w["name"] for w in workflows])
            workflow_inputs = st.text_area("Workflow Inputs (JSON):", value="{}")
            
            if st.button("🚀 Trigger Workflow"):
                workflow_id = next(w["id"] for w in workflows if w["name"] == selected_workflow)
                try:
                    inputs = json.loads(workflow_inputs) if workflow_inputs.strip() else {}
                    success = trigger_github_action("lawtrax", "legal-database", workflow_id, inputs)
                    if success:
                        st.success("✅ Workflow triggered successfully!")
                    else:
                        st.error("❌ Failed to trigger workflow")
                except json.JSONDecodeError:
                    st.error("❌ Invalid JSON in workflow inputs")
        
        with action_col2:
            st.markdown("**Workflow Status:**")
            # You could add workflow status checking here
            st.info("🔄 Check GitHub Actions tab in your repository for workflow status")
            
            st.markdown("**Quick Actions:**")
            if st.button("📊 Generate Daily Report"):
                success = trigger_github_action("lawtrax", "legal-database", "daily-report.yml", 
                                               {"date": datetime.now().strftime("%Y-%m-%d")})
                if success:
                    st.success("✅ Daily report generation started!")
                    
            if st.button("🔄 Sync All Data"):
                success = trigger_github_action("lawtrax", "legal-database", "sync-all.yml")
                if success:
                    st.success("✅ Data sync started!")
        
        st.markdown("---")
        
        # Real-time Data Display
        st.markdown("### 📊 Real-time Data Preview")
        
        if st.session_state.github_data:
            data_type = st.selectbox("Select Data to Preview:", list(st.session_state.github_data.keys()))
            
            if data_type and data_type in st.session_state.github_data:
                data = st.session_state.github_data[data_type]
                
                if isinstance(data, dict):
                    st.json(data)
                elif isinstance(data, str):
                    st.text_area("Data Content:", data, height=200)
                else:
                    st.write(data)
        else:
            st.info("🔄 No data loaded. Update data sources to preview content.")

    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666;'>
        <strong>Lawtrax Immigration Assistant</strong> | Powered by AI | For Licensed Attorneys Only<br>
        <small>Always consult current regulations and seek supervisory review of AI-generated content</small>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
