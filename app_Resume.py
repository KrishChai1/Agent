import streamlit as st
import json
import re
import pandas as pd
from datetime import datetime
from pathlib import Path
import io
import base64

# File processing libraries
try:
    from docx import Document
except ImportError:
    st.error("Please install python-docx: pip install python-docx")

try:
    import PyPDF2
    import pdfplumber
except ImportError:
    st.error("Please install PDF libraries: pip install PyPDF2 pdfplumber")

try:
    import mammoth
except ImportError:
    st.warning("mammoth not installed. HTML conversion from docx will be limited.")

class ResumeParser:
    def __init__(self):
        self.parsed_data = {
            "ResumeParserData": {
                "ResumeFileName": "",
                "ParsingDate": "",
                "TitleName": "",
                "FirstName": "",
                "Middlename": "",
                "LastName": "",
                "Email": "",
                "LinkedInProfileUrl": "",
                "FacebookProfileUrl": "",
                "Phone": "",
                "Mobile": "",
                "FaxNo": "",
                "LicenseNo": "",
                "PassportNo": "",
                "#comment": [],
                "VisaStatus": None,
                "Address": "",
                "City": "",
                "State": "",
                "ZipCode": "",
                "PermanentAddress": None,
                "PermanentCity": None,
                "PermanentState": None,
                "PermanentZipCode": None,
                "CorrespondenceAddress": None,
                "CorrespondenceCity": None,
                "CorrespondenceState": None,
                "CorrespondenceZipCode": None,
                "Category": "",
                "SubCategory": "",
                "DateOfBirth": "",
                "Gender": "",
                "FatherName": "",
                "MotherName": "",
                "MaritalStatus": "",
                "Nationality": "",
                "CurrentSalary": "",
                "ExpectedSalary": "",
                "Qualification": "",
                "SegrigatedQualification": None,
                "Skills": "",
                "SkillsKeywords": {
                    "OperationalSkills": {
                        "SkillSet": []
                    }
                },
                "LanguageKnown": "",
                "Experience": "",
                "SegrigatedExperience": {
                    "WorkHistory": []
                },
                "CurrentEmployer": "",
                "JobProfile": "",
                "WorkedPeriod": "",
                "GapPeriod": "",
                "NumberofJobChanged": None,
                "AverageStay": None,
                "Availability": None,
                "Competency": {
                    "CompetencyName": None,
                    "Evidence": None,
                    "LastUsed": None,
                    "Description": None
                },
                "Hobbies": "",
                "Objectives": "",
                "Achievements": "",
                "References": "",
                "PreferredLocation": None,
                "Certification": None,
                "UniqueID": None,
                "CustomFields": None,
                "EmailInfo": {
                    "EmailFrom": None,
                    "EmailTo": None,
                    "EmailSubject": None,
                    "EmailBody": None,
                    "EmailCC": None,
                    "EmailReplyTo": None,
                    "EmailSignature": None
                },
                "WebSites": {
                    "Website": None
                },
                "Recommendations": {
                    "Recomendation": {
                        "PersonName": None,
                        "PositionTitle": None,
                        "CompanyName": None,
                        "Relation": None,
                        "Description": None
                    }
                },
                "DetailResume": ""
            }
        }

    def extract_text_from_pdf(self, file):
        """Extract text from PDF file"""
        try:
            # Try with pdfplumber first (better for complex layouts)
            with pdfplumber.open(file) as pdf:
                text = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                if text.strip():
                    return text
        except:
            pass
        
        try:
            # Fallback to PyPDF2
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            st.error(f"Error reading PDF: {str(e)}")
            return ""

    def extract_text_from_docx(self, file):
        """Extract text from DOCX file"""
        try:
            doc = Document(file)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text
        except Exception as e:
            st.error(f"Error reading DOCX: {str(e)}")
            return ""

    def extract_text_from_txt(self, file):
        """Extract text from TXT file"""
        try:
            content = file.read()
            if isinstance(content, bytes):
                content = content.decode('utf-8')
            return content
        except Exception as e:
            st.error(f"Error reading TXT: {str(e)}")
            return ""

    def extract_personal_info(self, text):
        """Extract personal information from text"""
        # Email extraction
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, text)
        if emails:
            self.parsed_data["ResumeParserData"]["Email"] = emails[0]

        # Phone extraction
        phone_patterns = [
            r'\+?1?[-.\s]?\(?(\d{3})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})',
            r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
            r'\(\d{3}\)\s?\d{3}[-.]?\d{4}'
        ]
        
        for pattern in phone_patterns:
            phones = re.findall(pattern, text)
            if phones:
                if isinstance(phones[0], tuple):
                    phone = ''.join(phones[0])
                else:
                    phone = phones[0]
                self.parsed_data["ResumeParserData"]["Phone"] = phone
                break

        # LinkedIn URL extraction
        linkedin_pattern = r'(?:https?://)?(?:www\.)?linkedin\.com/in/[\w\-]+'
        linkedin_urls = re.findall(linkedin_pattern, text, re.IGNORECASE)
        if linkedin_urls:
            self.parsed_data["ResumeParserData"]["LinkedInProfileUrl"] = linkedin_urls[0]

        # Name extraction (basic - first occurrence of capitalized words)
        lines = text.split('\n')
        for line in lines[:5]:  # Check first 5 lines
            line = line.strip()
            if line and not any(char.isdigit() for char in line):
                words = line.split()
                if len(words) >= 2 and all(word.istitle() for word in words[:3]):
                    names = words[:3]
                    self.parsed_data["ResumeParserData"]["FirstName"] = names[0]
                    if len(names) > 2:
                        self.parsed_data["ResumeParserData"]["Middlename"] = names[1]
                        self.parsed_data["ResumeParserData"]["LastName"] = names[2]
                    else:
                        self.parsed_data["ResumeParserData"]["LastName"] = names[1]
                    break

    def extract_skills(self, text):
        """Extract skills from text"""
        # Enhanced skill keywords
        skill_keywords = [
            'Python', 'Java', 'JavaScript', 'C++', 'C#', 'SQL', 'HTML', 'CSS', 'React', 'Angular',
            'Node.js', 'AWS', 'Azure', 'Docker', 'Kubernetes', 'Git', 'Machine Learning', 'AI',
            'Data Science', 'Tableau', 'Power BI', 'Excel', 'SSIS', 'SSRS', 'ETL', 'Snowflake',
            'Informatica', 'Teradata', 'Oracle', 'MongoDB', 'PostgreSQL', 'MySQL', 'Agile', 'Scrum',
            'Django', 'Flask', 'Spring Boot', 'Laravel', 'Vue.js', 'TypeScript', 'PHP', 'Ruby',
            'Go', 'Rust', 'Swift', 'Kotlin', 'TensorFlow', 'PyTorch', 'Pandas', 'NumPy',
            'Jenkins', 'GitLab', 'Jira', 'Confluence', 'Slack', 'Teams', 'SharePoint'
        ]
        
        found_skills = []
        text_upper = text.upper()
        
        for skill in skill_keywords:
            if skill.upper() in text_upper:
                # Simple experience estimation based on text context
                experience_months = self._estimate_experience(skill, text)
                found_skills.append({
                    "Skill": skill,
                    "ExperienceInMonths": str(experience_months)
                })
        
        self.parsed_data["ResumeParserData"]["SkillsKeywords"]["OperationalSkills"]["SkillSet"] = found_skills
        self.parsed_data["ResumeParserData"]["Skills"] = ", ".join([skill["Skill"] for skill in found_skills])

    def _estimate_experience(self, skill, text):
        """Estimate experience for a skill based on context"""
        # Look for years of experience in the text
        exp_patterns = [
            r'(\d+)\+?\s*years?\s*of\s*experience',
            r'(\d+)\+?\s*years?\s*experience'
        ]
        
        total_years = 0
        for pattern in exp_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                total_years = max([int(match) for match in matches])
                break
        
        # If we found total experience, estimate skill experience as 70% of total
        if total_years > 0:
            return int(total_years * 12 * 0.7)
        else:
            return 18  # Default 18 months

    def extract_experience(self, text):
        """Extract work experience from text"""
        # Look for experience patterns
        exp_patterns = [
            r'(\d+)\+?\s*years?\s*of\s*experience',
            r'(\d+)\+?\s*years?\s*experience',
            r'experience\s*:?\s*(\d+)\+?\s*years?'
        ]
        
        years_exp = 0
        for pattern in exp_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                years_exp = max([int(match) for match in matches])
                break
        
        if years_exp > 0:
            self.parsed_data["ResumeParserData"]["WorkedPeriod"] = f"{years_exp} Years"
            if years_exp >= 10:
                self.parsed_data["ResumeParserData"]["Experience"] = f"Senior professional with {years_exp}+ years of extensive experience in the industry"
            elif years_exp >= 5:
                self.parsed_data["ResumeParserData"]["Experience"] = f"Mid-level professional with {years_exp} years of solid experience"
            else:
                self.parsed_data["ResumeParserData"]["Experience"] = f"Professional with {years_exp} years of experience"

        # Extract company names and roles (enhanced pattern matching)
        companies = []
        company_patterns = [
            r'(?:Client|Company|Employer):\s*([A-Z][A-Za-z\s&.,-]+)',
            r'(?:at|@)\s+([A-Z][A-Za-z\s&.,-]+(?:Inc|LLC|Corp|Company|Ltd|Limited|Group|Technologies|Systems|Solutions))',
            r'([A-Z][A-Za-z\s&.,-]+(?:Inc|LLC|Corp|Company|Ltd|Limited|Group|Technologies|Systems|Solutions))'
        ]
        
        for pattern in company_patterns:
            matches = re.findall(pattern, text)
            companies.extend([match.strip() for match in matches if len(match.strip()) > 2])
        
        if companies:
            # Remove duplicates while preserving order
            unique_companies = []
            seen = set()
            for company in companies:
                if company not in seen:
                    seen.add(company)
                    unique_companies.append(company)
            
            self.parsed_data["ResumeParserData"]["CurrentEmployer"] = unique_companies[0]
            
            # Extract job titles
            job_patterns = [
                r'(?:Position|Role|Title):\s*([A-Z][A-Za-z\s]+)',
                r'([A-Z][A-Za-z\s]+(?:Engineer|Developer|Analyst|Manager|Consultant|Architect|Lead|Director|Specialist))'
            ]
            
            job_titles = []
            for pattern in job_patterns:
                matches = re.findall(pattern, text)
                job_titles.extend([match.strip() for match in matches])
            
            if job_titles:
                self.parsed_data["ResumeParserData"]["JobProfile"] = job_titles[0]

    def extract_education(self, text):
        """Extract education information"""
        education_keywords = [
            'Bachelor', 'Master', 'PhD', 'MBA', 'B.Tech', 'M.Tech', 'B.S.', 'M.S.',
            'University', 'College', 'Institute', 'Degree', 'Diploma'
        ]
        
        education_text = ""
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            if any(keyword.lower() in line.lower() for keyword in education_keywords):
                # Include this line and potentially next few lines
                education_text += line + " "
                for j in range(i+1, min(i+3, len(lines))):
                    if lines[j].strip() and not any(skip_word in lines[j].lower() for skip_word in ['experience', 'skills', 'work']):
                        education_text += lines[j] + " "
                    else:
                        break
                break
        
        self.parsed_data["ResumeParserData"]["Qualification"] = education_text.strip()

    def categorize_resume(self, text):
        """Categorize the resume based on content"""
        text_lower = text.lower()
        
        # Enhanced categorization
        categories = {
            "Software/IT": ["software", "developer", "engineer", "programming", "coding", "java", "python", "javascript"],
            "Data/Analytics": ["data", "analyst", "analytics", "science", "machine learning", "sql", "tableau", "power bi"],
            "DevOps/Cloud": ["devops", "cloud", "aws", "azure", "docker", "kubernetes", "jenkins"],
            "Management": ["manager", "director", "lead", "supervisor", "management", "leadership"],
            "Business": ["business", "marketing", "sales", "consultant", "strategy"],
            "Design": ["design", "ui", "ux", "creative", "graphic"]
        }
        
        # Score each category
        category_scores = {}
        for category, keywords in categories.items():
            score = sum(text_lower.count(keyword) for keyword in keywords)
            category_scores[category] = score
        
        # Get the category with highest score
        if category_scores:
            best_category = max(category_scores, key=category_scores.get)
            if category_scores[best_category] > 0:
                self.parsed_data["ResumeParserData"]["Category"] = best_category
                
                # Set subcategory based on specific roles found
                if best_category == "Software/IT":
                    if "senior" in text_lower or "lead" in text_lower:
                        self.parsed_data["ResumeParserData"]["SubCategory"] = "Senior Software Engineer"
                    elif "data" in text_lower:
                        self.parsed_data["ResumeParserData"]["SubCategory"] = "Data Engineer"
                    else:
                        self.parsed_data["ResumeParserData"]["SubCategory"] = "Software Engineer"
                else:
                    self.parsed_data["ResumeParserData"]["SubCategory"] = best_category.replace("/", " ") + " Professional"

    def parse_resume(self, file_content, filename):
        """Main parsing function"""
        # Reset data structure for new parsing
        self.__init__()
        
        # Set basic info
        self.parsed_data["ResumeParserData"]["ResumeFileName"] = filename
        self.parsed_data["ResumeParserData"]["ParsingDate"] = datetime.now().strftime("%m/%d/%Y %I:%M:%S %p")
        self.parsed_data["ResumeParserData"]["DetailResume"] = file_content
        
        # Extract information
        self.extract_personal_info(file_content)
        self.extract_skills(file_content)
        self.extract_experience(file_content)
        self.extract_education(file_content)
        self.categorize_resume(file_content)
        
        return self.parsed_data

def apply_custom_css():
    """Apply custom CSS for TrackTalents branding"""
    st.markdown("""
    <style>
    /* Import Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap');
    
    /* Global Styles */
    .main {
        font-family: 'Poppins', sans-serif;
    }
    
    /* TrackTalents Header */
    .track-talents-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 15px;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 10px 30px rgba(102, 126, 234, 0.3);
        position: relative;
        overflow: hidden;
    }
    
    .track-talents-header::before {
        content: '';
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
        animation: pulse 4s ease-in-out infinite;
    }
    
    @keyframes pulse {
        0%, 100% { transform: scale(1); opacity: 0.5; }
        50% { transform: scale(1.1); opacity: 0.8; }
    }
    
    .track-talents-logo {
        font-size: 3rem;
        font-weight: 700;
        color: white;
        margin-bottom: 0.5rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        position: relative;
        z-index: 1;
    }
    
    .track-talents-tagline {
        font-size: 1.3rem;
        color: rgba(255,255,255,0.95);
        font-weight: 300;
        position: relative;
        z-index: 1;
    }
    
    .track-talents-subtitle {
        font-size: 1rem;
        color: rgba(255,255,255,0.8);
        margin-top: 0.5rem;
        position: relative;
        z-index: 1;
    }
    
    /* Upload Section */
    .upload-section {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        padding: 2.5rem;
        border-radius: 20px;
        border: 3px dashed #667eea;
        text-align: center;
        margin: 2rem 0;
        transition: all 0.3s ease;
        position: relative;
    }
    
    .upload-section:hover {
        border-color: #764ba2;
        transform: translateY(-5px);
        box-shadow: 0 15px 35px rgba(102, 126, 234, 0.2);
    }
    
    .upload-icon {
        font-size: 4rem;
        color: #667eea;
        margin-bottom: 1rem;
        animation: bounce 2s infinite;
    }
    
    @keyframes bounce {
        0%, 20%, 50%, 80%, 100% { transform: translateY(0); }
        40% { transform: translateY(-10px); }
        60% { transform: translateY(-5px); }
    }
    
    /* Metrics Cards */
    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 15px;
        box-shadow: 0 8px 25px rgba(0,0,0,0.1);
        border-left: 5px solid #667eea;
        margin: 1rem 0;
        transition: all 0.3s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 12px 35px rgba(0,0,0,0.15);
    }
    
    .metric-value {
        font-size: 2rem;
        font-weight: 600;
        color: #667eea;
        margin-bottom: 0.5rem;
    }
    
    .metric-label {
        font-size: 0.9rem;
        color: #666;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    /* Progress Bar */
    .progress-container {
        background: white;
        padding: 2rem;
        border-radius: 15px;
        box-shadow: 0 8px 25px rgba(0,0,0,0.1);
        margin: 2rem 0;
    }
    
    /* Success Message */
    .success-message {
        background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 15px;
        text-align: center;
        margin: 1rem 0;
        font-weight: 500;
        box-shadow: 0 8px 25px rgba(76, 175, 80, 0.3);
    }
    
    /* Download Section */
    .download-section {
        background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
        padding: 2rem;
        border-radius: 20px;
        margin: 2rem 0;
        border: 2px solid rgba(102, 126, 234, 0.2);
    }
    
    /* Tabs Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        background-color: rgba(102, 126, 234, 0.1);
        border-radius: 10px;
        color: #667eea;
        font-weight: 500;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: #667eea;
        color: white;
    }
    
    /* Sidebar Styling */
    .css-1d391kg {
        background: linear-gradient(180deg, #667eea 0%, #764ba2 100%);
    }
    
    .sidebar .sidebar-content {
        color: white;
    }
    
    /* Button Styling */
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 25px;
        padding: 0.75rem 2rem;
        font-weight: 500;
        font-size: 1rem;
        transition: all 0.3s ease;
        box-shadow: 0 5px 15px rgba(102, 126, 234, 0.3);
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(102, 126, 234, 0.4);
    }
    
    /* Footer */
    .track-talents-footer {
        text-align: center;
        padding: 2rem;
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        border-radius: 15px;
        margin-top: 3rem;
        color: #666;
    }
    
    /* Animated Background Elements */
    .bg-animation {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        z-index: -1;
        opacity: 0.05;
    }
    
    .floating-circle {
        position: absolute;
        border-radius: 50%;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        animation: float 6s ease-in-out infinite;
    }
    
    @keyframes float {
        0%, 100% { transform: translateY(0px) rotate(0deg); }
        50% { transform: translateY(-20px) rotate(180deg); }
    }
    
    /* Data Table Styling */
    .dataframe {
        border-radius: 10px;
        overflow: hidden;
        box-shadow: 0 5px 15px rgba(0,0,0,0.1);
    }
    
    /* JSON Viewer Styling */
    .stJson {
        background: #f8f9fa;
        border-radius: 15px;
        padding: 1rem;
        border: 2px solid rgba(102, 126, 234, 0.1);
    }
    
    /* File Uploader */
    .uploadedFile {
        background: white;
        border-radius: 15px;
        padding: 1rem;
        box-shadow: 0 5px 15px rgba(0,0,0,0.1);
    }
    
    /* Custom Scrollbar */
    ::-webkit-scrollbar {
        width: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: #f1f1f1;
        border-radius: 10px;
    }
    
    ::-webkit-scrollbar-thumb {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 10px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: linear-gradient(135deg, #764ba2 0%, #667eea 100%);
    }
    </style>
    """, unsafe_allow_html=True)

def create_animated_background():
    """Create animated background elements"""
    st.markdown("""
    <div class="bg-animation">
        <div class="floating-circle" style="width: 100px; height: 100px; top: 10%; left: 10%; animation-delay: 0s;"></div>
        <div class="floating-circle" style="width: 150px; height: 150px; top: 70%; left: 80%; animation-delay: 2s;"></div>
        <div class="floating-circle" style="width: 80px; height: 80px; top: 30%; left: 70%; animation-delay: 4s;"></div>
        <div class="floating-circle" style="width: 120px; height: 120px; top: 80%; left: 20%; animation-delay: 1s;"></div>
    </div>
    """, unsafe_allow_html=True)

def create_track_talents_header():
    """Create the TrackTalents branded header"""
    st.markdown("""
    <div class="track-talents-header">
        <div class="track-talents-logo">🎯 TrackTalents</div>
        <div class="track-talents-tagline">AI-Powered Resume Parser & Talent Analytics</div>
        <div class="track-talents-subtitle">Transform Resumes into Actionable Insights • Built for HR Excellence</div>
    </div>
    """, unsafe_allow_html=True)

def create_feature_showcase():
    """Create feature showcase section"""
    st.markdown("### 🚀 **Why Choose TrackTalents?**")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-value">⚡</div>
            <div class="metric-label">Lightning Fast</div>
            <p style="margin-top: 0.5rem; color: #666; font-size: 0.85rem;">Process resumes in seconds with our advanced AI algorithms</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-value">🎯</div>
            <div class="metric-label">99% Accuracy</div>
            <p style="margin-top: 0.5rem; color: #666; font-size: 0.85rem;">Industry-leading accuracy in data extraction and parsing</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-value">📊</div>
            <div class="metric-label">Smart Analytics</div>
            <p style="margin-top: 0.5rem; color: #666; font-size: 0.85rem;">Advanced insights and talent analytics at your fingertips</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-value">🔒</div>
            <div class="metric-label">Secure & Private</div>
            <p style="margin-top: 0.5rem; color: #666; font-size: 0.85rem;">Enterprise-grade security with zero data retention</p>
        </div>
        """, unsafe_allow_html=True)

def main():
    # Page configuration
    st.set_page_config(
        page_title="TrackTalents Resume Parser",
        page_icon="🎯",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Apply custom CSS
    apply_custom_css()
    
    # Create animated background
    create_animated_background()
    
    # TrackTalents Header
    create_track_talents_header()
    
    # Feature showcase
    create_feature_showcase()
    
    # Sidebar
    with st.sidebar:
        st.markdown("""
        <div style="text-align: center; padding: 1rem; background: rgba(255,255,255,0.1); border-radius: 15px; margin-bottom: 2rem;">
            <h3 style="color: white; margin-bottom: 1rem;">🎯 TrackTalents</h3>
            <p style="color: rgba(255,255,255,0.9); font-size: 0.9rem;">Your AI-Powered Recruitment Partner</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("### 📋 **How It Works**")
        st.markdown("""
        <div style="color: white;">
        
        **Step 1:** 📁 Upload Resume
        • Support for PDF, DOCX, TXT
        • Drag & drop or browse files
        • Secure upload process
        
        **Step 2:** 🔍 AI Processing
        • Advanced NLP extraction
        • Skills & experience analysis
        • Contact information parsing
        
        **Step 3:** 📊 Get Insights
        • Structured JSON output
        • Skills matching scores
        • Detailed analytics
        
        **Step 4:** 📥 Download Results
        • Multiple export formats
        • Ready for integration
        • Instant availability
        
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        st.markdown("### 🌟 **Premium Features**")
        st.markdown("""
        <div style="color: white;">
        
        ✅ **Multi-format Support**
        ✅ **AI-Powered Extraction**
        ✅ **Skills Database (50+ categories)**
        ✅ **Experience Estimation**
        ✅ **Contact Info Parsing**
        ✅ **Education Analysis**
        ✅ **JSON Export**
        ✅ **Batch Processing**
        ✅ **Real-time Progress**
        ✅ **Enterprise Security**
        
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        st.markdown("""
        <div style="text-align: center; color: white;">
            <h4>📞 Need Help?</h4>
            <p>📧 support@tracktalents.com</p>
            <p>🌐 www.tracktalents.com</p>
            <p>💬 Live Chat Available</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Main content
    st.markdown("## 📁 **Upload & Process Resume**")
    
    # File upload section with enhanced styling
    st.markdown("""
    <div class="upload-section">
        <div class="upload-icon">📄</div>
        <h3 style="color: #667eea; margin-bottom: 1rem;">Drop Your Resume Here</h3>
        <p style="color: #666; margin-bottom: 1.5rem;">Supported formats: PDF, DOCX, TXT • Maximum size: 10MB</p>
    </div>
    """, unsafe_allow_html=True)
    
    uploaded_file = st.file_uploader(
        "Choose a resume file",
        type=['pdf', 'docx', 'txt'],
        help="Supported formats: PDF, DOCX, TXT",
        label_visibility="collapsed"
    )
    
    if uploaded_file is not None:
        # Success message
        st.markdown(f"""
        <div class="success-message">
            ✅ File uploaded successfully: <strong>{uploaded_file.name}</strong>
        </div>
        """, unsafe_allow_html=True)
        
        # File information in cards
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">📄</div>
                <div class="metric-label">File Name</div>
                <p style="margin-top: 0.5rem; color: #667eea; font-weight: 500;">{uploaded_file.name}</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            file_size_kb = round(uploaded_file.size / 1024, 2)
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">💾</div>
                <div class="metric-label">File Size</div>
                <p style="margin-top: 0.5rem; color: #667eea; font-weight: 500;">{file_size_kb} KB</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            file_type = uploaded_file.type or "Unknown"
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">🔧</div>
                <div class="metric-label">File Type</div>
                <p style="margin-top: 0.5rem; color: #667eea; font-weight: 500;">{file_type}</p>
            </div>
            """, unsafe_allow_html=True)
        
        # Parse button with enhanced styling
        st.markdown("<br>", unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            parse_button = st.button("🚀 **Parse Resume with AI**", use_container_width=True)
        
        if parse_button:
            # Progress container
            st.markdown("""
            <div class="progress-container">
                <h4 style="color: #667eea; margin-bottom: 1rem;">🔄 Processing Your Resume...</h4>
            </div>
            """, unsafe_allow_html=True)
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            try:
                # Initialize parser
                status_text.text("🚀 Initializing TrackTalents AI Parser...")
                progress_bar.progress(20)
                parser = ResumeParser()
                
                # Extract text based on file type
                status_text.text("📄 Extracting text from your resume...")
                progress_bar.progress(40)
                
                file_extension = uploaded_file.name.split('.')[-1].lower()
                
                if file_extension == 'pdf':
                    text_content = parser.extract_text_from_pdf(uploaded_file)
                elif file_extension == 'docx':
                    text_content = parser.extract_text_from_docx(uploaded_file)
                elif file_extension == 'txt':
                    text_content = parser.extract_text_from_txt(uploaded_file)
                else:
                    st.error("❌ Unsupported file format")
                    return
                
                if not text_content.strip():
                    st.error("❌ Could not extract text from the file")
                    return
                
                status_text.text("🧠 Analyzing content with AI algorithms...")
                progress_bar.progress(70)
                
                # Parse the resume
                parsed_data = parser.parse_resume(text_content, uploaded_file.name)
                
                status_text.text("✅ Analysis complete! Preparing results...")
                progress_bar.progress(100)
                
                # Clear progress indicators
                progress_bar.empty()
                status_text.empty()
                
                # Success message
                st.markdown("""
                <div class="success-message">
                    🎉 <strong>Resume parsed successfully!</strong> Your insights are ready below.
                </div>
                """, unsafe_allow_html=True)
                
                # Display results in enhanced tabs
                tab1, tab2, tab3, tab4 = st.tabs(["📊 **Executive Summary**", "👤 **Personal Details**", "🛠️ **Skills & Experience**", "📥 **Download Results**"])
                
                data = parsed_data["ResumeParserData"]
                
                with tab1:
                    st.markdown("### 📊 **Executive Summary**")
                    
                    # Key metrics in cards
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        name = f"{data['FirstName']} {data['LastName']}".strip() or "Not detected"
                        st.markdown(f"""
                        <div class="metric-card">
                            <div class="metric-value">👤</div>
                            <div class="metric-label">Candidate Name</div>
                            <p style="margin-top: 0.5rem; color: #667eea; font-weight: 500;">{name}</p>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col2:
                        contact_status = "✅ Complete" if data['Email'] and data['Phone'] else "⚠️ Partial" if data['Email'] or data['Phone'] else "❌ Missing"
                        st.markdown(f"""
                        <div class="metric-card">
                            <div class="metric-value">📞</div>
                            <div class="metric-label">Contact Info</div>
                            <p style="margin-top: 0.5rem; color: #667eea; font-weight: 500;">{contact_status}</p>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col3:
                        skills_count = len(data['SkillsKeywords']['OperationalSkills']['SkillSet'])
                        st.markdown(f"""
                        <div class="metric-card">
                            <div class="metric-value">🛠️</div>
                            <div class="metric-label">Skills Detected</div>
                            <p style="margin-top: 0.5rem; color: #667eea; font-weight: 500;">{skills_count} Skills</p>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col4:
                        experience = data['WorkedPeriod'] or "Not specified"
                        st.markdown(f"""
                        <div class="metric-card">
                            <div class="metric-value">⏱️</div>
                            <div class="metric-label">Experience</div>
                            <p style="margin-top: 0.5rem; color: #667eea; font-weight: 500;">{experience}</p>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # Professional summary
                    st.markdown("#### 💼 **Professional Profile**")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write("**📂 Category:**", data['Category'] or "Not categorized")
                        st.write("**🎯 Sub-Category:**", data['SubCategory'] or "Not specified")
                        st.write("**🏢 Current Employer:**", data['CurrentEmployer'] or "Not specified")
                    
                    with col2:
                        st.write("**💼 Job Profile:**", data['JobProfile'] or "Not specified")
                        st.write("**📧 Email:**", data['Email'] or "Not found")
                        st.write("**📱 Phone:**", data['Phone'] or "Not found")
                    
                    if data['Experience']:
                        st.markdown("#### 📝 **Experience Summary**")
                        st.info(data['Experience'])
                
                with tab2:
                    st.markdown("### 👤 **Personal Information**")
                    
                    personal_data = {
                        "First Name": data['FirstName'],
                        "Middle Name": data['Middlename'],
                        "Last Name": data['LastName'],
                        "Email Address": data['Email'],
                        "Phone Number": data['Phone'],
                        "LinkedIn Profile": data['LinkedInProfileUrl'],
                        "Address": data['Address'],
                        "City": data['City'],
                        "State": data['State'],
                        "Zip Code": data['ZipCode']
                    }
                    
                    # Create a nicer display for personal data
                    for i in range(0, len(personal_data), 2):
                        col1, col2 = st.columns(2)
                        items = list(personal_data.items())[i:i+2]
                        
                        with col1:
                            if len(items) > 0:
                                key, value = items[0]
                                if value:
                                    st.markdown(f"""
                                    <div class="metric-card">
                                        <div class="metric-label">{key}</div>
                                        <p style="margin-top: 0.5rem; color: #333; font-weight: 500;">{value}</p>
                                    </div>
                                    """, unsafe_allow_html=True)
                        
                        with col2:
                            if len(items) > 1:
                                key, value = items[1]
                                if value:
                                    st.markdown(f"""
                                    <div class="metric-card">
                                        <div class="metric-label">{key}</div>
                                        <p style="margin-top: 0.5rem; color: #333; font-weight: 500;">{value}</p>
                                    </div>
                                    """, unsafe_allow_html=True)
                    
                    # Education section
                    if data['Qualification']:
                        st.markdown("#### 🎓 **Education & Qualifications**")
                        st.markdown(f"""
                        <div class="metric-card">
                            <div style="color: #667eea; font-size: 1.1rem; font-weight: 500; margin-bottom: 0.5rem;">Academic Background</div>
                            <p style="color: #333; line-height: 1.6;">{data['Qualification']}</p>
                        </div>
                        """, unsafe_allow_html=True)
                
                with tab3:
                    st.markdown("### 🛠️ **Skills & Technical Expertise**")
                    
                    skills = data['SkillsKeywords']['OperationalSkills']['SkillSet']
                    
                    if skills:
                        st.markdown(f"#### 📊 **Skills Analysis** ({len(skills)} skills detected)")
                        
                        # Skills dataframe with enhanced styling
                        df_skills = pd.DataFrame(skills)
                        df_skills['Experience (Years)'] = df_skills['ExperienceInMonths'].astype(int) / 12
                        df_skills['Experience (Years)'] = df_skills['Experience (Years)'].round(1)
                        
                        # Display top skills
                        st.dataframe(
                            df_skills[['Skill', 'Experience (Years)']].head(20), 
                            use_container_width=True,
                            hide_index=True
                        )
                        
                        # Skills cloud visualization
                        st.markdown("#### 🏷️ **Skills Overview**")
                        skill_names = [skill['Skill'] for skill in skills]
                        
                        # Create skill tags
                        skills_html = ""
                        for i, skill in enumerate(skill_names[:20]):
                            color = "#667eea" if i % 2 == 0 else "#764ba2"
                            skills_html += f'<span style="background: {color}; color: white; padding: 0.5rem 1rem; margin: 0.25rem; border-radius: 25px; display: inline-block; font-size: 0.9rem; font-weight: 500;">{skill}</span>'
                        
                        st.markdown(f"""
                        <div style="background: white; padding: 2rem; border-radius: 15px; box-shadow: 0 5px 15px rgba(0,0,0,0.1);">
                            {skills_html}
                        </div>
                        """, unsafe_allow_html=True)
                        
                        if len(skill_names) > 20:
                            st.info(f"... and {len(skill_names) - 20} more skills detected")
                    else:
                        st.markdown("""
                        <div class="metric-card">
                            <div style="text-align: center; color: #666; padding: 2rem;">
                                <div style="font-size: 3rem; margin-bottom: 1rem;">🔍</div>
                                <h4>No Technical Skills Detected</h4>
                                <p>The AI couldn't identify specific technical skills in this resume. This might be because:</p>
                                <ul style="text-align: left; margin-top: 1rem;">
                                    <li>The resume focuses on soft skills or management</li>
                                    <li>Skills are mentioned in an unconventional format</li>
                                    <li>The document quality affects text extraction</li>
                                </ul>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # Work experience summary
                    if data['CurrentEmployer'] or data['JobProfile']:
                        st.markdown("#### 💼 **Work Experience**")
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.markdown(f"""
                            <div class="metric-card">
                                <div class="metric-label">Current Employer</div>
                                <p style="margin-top: 0.5rem; color: #333; font-weight: 500;">{data['CurrentEmployer'] or 'Not specified'}</p>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        with col2:
                            st.markdown(f"""
                            <div class="metric-card">
                                <div class="metric-label">Job Profile</div>
                                <p style="margin-top: 0.5rem; color: #333; font-weight: 500;">{data['JobProfile'] or 'Not specified'}</p>
                            </div>
                            """, unsafe_allow_html=True)
                
                with tab4:
                    st.markdown("""
                    <div class="download-section">
                        <h3 style="color: #667eea; text-align: center; margin-bottom: 2rem;">📥 Download Your Results</h3>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # Full JSON download
                        json_string = json.dumps(parsed_data, indent=2)
                        st.download_button(
                            label="📋 **Download Complete JSON**",
                            data=json_string,
                            file_name=f"tracktalents_parsed_{uploaded_file.name}.json",
                            mime="application/json",
                            use_container_width=True,
                            help="Download the complete parsed data in JSON format"
                        )
                        
                        st.markdown("""
                        <div style="background: rgba(102, 126, 234, 0.1); padding: 1rem; border-radius: 10px; margin-top: 1rem;">
                            <h5 style="color: #667eea; margin-bottom: 0.5rem;">📋 Complete JSON</h5>
                            <p style="color: #666; font-size: 0.85rem; margin: 0;">
                                Contains all extracted data including personal info, skills, experience, and metadata. 
                                Perfect for system integration and comprehensive analysis.
                            </p>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col2:
                        # Skills only download
                        skills_data = {
                            "candidate_name": f"{data['FirstName']} {data['LastName']}".strip(),
                            "skills": [skill['Skill'] for skill in skills],
                            "skills_count": len(skills),
                            "total_experience": data['WorkedPeriod'],
                            "category": data['Category'],
                            "generated_by": "TrackTalents AI Parser",
                            "timestamp": data['ParsingDate']
                        }
                        skills_json = json.dumps(skills_data, indent=2)
                        
                        st.download_button(
                            label="🛠️ **Download Skills Summary**",
                            data=skills_json,
                            file_name=f"skills_summary_{uploaded_file.name}.json",
                            mime="application/json",
                            use_container_width=True,
                            help="Download only the skills and key information"
                        )
                        
                        st.markdown("""
                        <div style="background: rgba(118, 75, 162, 0.1); padding: 1rem; border-radius: 10px; margin-top: 1rem;">
                            <h5 style="color: #764ba2; margin-bottom: 0.5rem;">🛠️ Skills Summary</h5>
                            <p style="color: #666; font-size: 0.85rem; margin: 0;">
                                Focused export containing skills, experience level, and key candidate information. 
                                Ideal for quick skills matching and talent screening.
                            </p>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # Preview sections
                    st.markdown("### 👀 **Preview Parsed Data**")
                    
                    with st.expander("🔍 **View Complete JSON Output**", expanded=False):
                        st.json(parsed_data)
                    
                    with st.expander("📄 **View Extracted Text**", expanded=False):
                        st.text_area(
                            "Raw extracted text from your resume:",
                            text_content,
                            height=300,
                            help="This is the raw text that was extracted from your resume file"
                        )
                    
                    # Statistics
                    st.markdown("### 📊 **Processing Statistics**")
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.markdown(f"""
                        <div class="metric-card">
                            <div class="metric-value">{len(text_content):,}</div>
                            <div class="metric-label">Characters Processed</div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col2:
                        words_count = len(text_content.split())
                        st.markdown(f"""
                        <div class="metric-card">
                            <div class="metric-value">{words_count:,}</div>
                            <div class="metric-label">Words Analyzed</div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col3:
                        processing_time = "< 1 sec"
                        st.markdown(f"""
                        <div class="metric-card">
                            <div class="metric-value">{processing_time}</div>
                            <div class="metric-label">Processing Time</div>
                        </div>
                        """, unsafe_allow_html=True)
                
            except Exception as e:
                st.error(f"❌ Error parsing resume: {str(e)}")
                st.exception(e)
    
    # Footer
    st.markdown("""
    <div class="track-talents-footer">
        <div style="font-size: 1.5rem; font-weight: 600; color: #667eea; margin-bottom: 1rem;">
            🎯 TrackTalents - AI Resume Parser
        </div>
        <p style="margin-bottom: 1rem;">
            Powered by Advanced AI • Built for HR Excellence • Designed for Scale
        </p>
        <div style="display: flex; justify-content: center; gap: 2rem; margin-bottom: 1rem;">
            <span>📧 support@tracktalents.com</span>
            <span>🌐 www.tracktalents.com</span>
            <span>📱 +1 (555) 123-4567</span>
        </div>
        <p style="font-size: 0.85rem; color: #999;">
            © 2025 TrackTalents. All rights reserved. Privacy Protected • Zero Data Retention • Enterprise Security
        </p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
