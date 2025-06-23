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
        # Common skill keywords
        skill_keywords = [
            'Python', 'Java', 'JavaScript', 'C++', 'C#', 'SQL', 'HTML', 'CSS', 'React', 'Angular',
            'Node.js', 'AWS', 'Azure', 'Docker', 'Kubernetes', 'Git', 'Machine Learning', 'AI',
            'Data Science', 'Tableau', 'Power BI', 'Excel', 'SSIS', 'SSRS', 'ETL', 'Snowflake',
            'Informatica', 'Teradata', 'Oracle', 'MongoDB', 'PostgreSQL', 'MySQL', 'Agile', 'Scrum'
        ]
        
        found_skills = []
        text_upper = text.upper()
        
        for skill in skill_keywords:
            if skill.upper() in text_upper:
                found_skills.append({
                    "Skill": skill,
                    "ExperienceInMonths": "12"  # Default value
                })
        
        self.parsed_data["ResumeParserData"]["SkillsKeywords"]["OperationalSkills"]["SkillSet"] = found_skills
        self.parsed_data["ResumeParserData"]["Skills"] = ", ".join([skill["Skill"] for skill in found_skills])

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
            months = years_exp * 12
            self.parsed_data["ResumeParserData"]["WorkedPeriod"] = f"{years_exp} Years"

        # Extract company names and roles (basic pattern matching)
        companies = []
        # Look for common company patterns
        company_patterns = [
            r'(?:at|@)\s+([A-Z][A-Za-z\s&.,-]+(?:Inc|LLC|Corp|Company|Ltd|Limited|Group|Technologies|Systems|Solutions))',
            r'([A-Z][A-Za-z\s&.,-]+(?:Inc|LLC|Corp|Company|Ltd|Limited|Group|Technologies|Systems|Solutions))'
        ]
        
        for pattern in company_patterns:
            matches = re.findall(pattern, text)
            companies.extend(matches)
        
        if companies:
            self.parsed_data["ResumeParserData"]["CurrentEmployer"] = companies[0].strip()

    def extract_education(self, text):
        """Extract education information"""
        education_keywords = [
            'Bachelor', 'Master', 'PhD', 'MBA', 'B.Tech', 'M.Tech', 'B.S.', 'M.S.',
            'University', 'College', 'Institute', 'Degree'
        ]
        
        education_text = ""
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            if any(keyword.lower() in line.lower() for keyword in education_keywords):
                # Include this line and potentially next few lines
                education_text += line + " "
                for j in range(i+1, min(i+3, len(lines))):
                    if lines[j].strip():
                        education_text += lines[j] + " "
                    else:
                        break
                break
        
        self.parsed_data["ResumeParserData"]["Qualification"] = education_text.strip()

    def categorize_resume(self, text):
        """Categorize the resume based on content"""
        text_lower = text.lower()
        
        if any(keyword in text_lower for keyword in ['software', 'developer', 'engineer', 'programming']):
            self.parsed_data["ResumeParserData"]["Category"] = "Software/IT"
            self.parsed_data["ResumeParserData"]["SubCategory"] = "Software Engineer"
        elif any(keyword in text_lower for keyword in ['data', 'analyst', 'analytics', 'science']):
            self.parsed_data["ResumeParserData"]["Category"] = "Data/Analytics"
            self.parsed_data["ResumeParserData"]["SubCategory"] = "Data Analyst"
        elif any(keyword in text_lower for keyword in ['marketing', 'sales', 'business']):
            self.parsed_data["ResumeParserData"]["Category"] = "Business"
            self.parsed_data["ResumeParserData"]["SubCategory"] = "Business Analyst"
        else:
            self.parsed_data["ResumeParserData"]["Category"] = "General"
            self.parsed_data["ResumeParserData"]["SubCategory"] = "General"

    def parse_resume(self, file_content, filename):
        """Main parsing function"""
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

def main():
    st.set_page_config(
        page_title="Resume Parser",
        page_icon="📄",
        layout="wide"
    )
    
    st.title("📄 Resume Parser")
    st.markdown("Upload your resume in various formats (PDF, DOCX, TXT) and get structured JSON output")
    
    # Sidebar
    st.sidebar.header("📋 Instructions")
    st.sidebar.markdown("""
    1. Upload your resume file
    2. Supported formats: PDF, DOCX, TXT
    3. Click 'Parse Resume' to extract information
    4. Download the parsed JSON data
    """)
    
    # File upload
    uploaded_file = st.file_uploader(
        "Choose a resume file",
        type=['pdf', 'docx', 'txt'],
        help="Supported formats: PDF, DOCX, TXT"
    )
    
    if uploaded_file is not None:
        st.success(f"✅ File uploaded: {uploaded_file.name}")
        
        # Display file info
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("File Name", uploaded_file.name)
        with col2:
            st.metric("File Size", f"{uploaded_file.size} bytes")
        with col3:
            st.metric("File Type", uploaded_file.type)
        
        if st.button("🔍 Parse Resume", type="primary"):
            with st.spinner("Parsing resume..."):
                parser = ResumeParser()
                
                # Extract text based on file type
                file_extension = uploaded_file.name.split('.')[-1].lower()
                
                try:
                    if file_extension == 'pdf':
                        text_content = parser.extract_text_from_pdf(uploaded_file)
                    elif file_extension == 'docx':
                        text_content = parser.extract_text_from_docx(uploaded_file)
                    elif file_extension == 'txt':
                        text_content = parser.extract_text_from_txt(uploaded_file)
                    else:
                        st.error("Unsupported file format")
                        return
                    
                    if not text_content.strip():
                        st.error("Could not extract text from the file")
                        return
                    
                    # Parse the resume
                    parsed_data = parser.parse_resume(text_content, uploaded_file.name)
                    
                    st.success("✅ Resume parsed successfully!")
                    
                    # Display results in tabs
                    tab1, tab2, tab3, tab4 = st.tabs(["📊 Summary", "👤 Personal Info", "💼 Experience & Skills", "📥 Download JSON"])
                    
                    with tab1:
                        st.subheader("Resume Summary")
                        data = parsed_data["ResumeParserData"]
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write("**Name:**", f"{data['FirstName']} {data['Middlename']} {data['LastName']}".strip())
                            st.write("**Email:**", data['Email'])
                            st.write("**Phone:**", data['Phone'])
                        with col2:
                            st.write("**Category:**", data['Category'])
                            st.write("**Sub-Category:**", data['SubCategory'])
                            st.write("**Current Employer:**", data['CurrentEmployer'])
                    
                    with tab2:
                        st.subheader("Personal Information")
                        personal_data = {
                            "First Name": data['FirstName'],
                            "Middle Name": data['Middlename'],
                            "Last Name": data['LastName'],
                            "Email": data['Email'],
                            "Phone": data['Phone'],
                            "LinkedIn": data['LinkedInProfileUrl'],
                            "Address": data['Address'],
                            "City": data['City'],
                            "State": data['State'],
                            "Zip Code": data['ZipCode']
                        }
                        
                        df_personal = pd.DataFrame(list(personal_data.items()), columns=['Field', 'Value'])
                        st.dataframe(df_personal, use_container_width=True)
                    
                    with tab3:
                        st.subheader("Skills & Experience")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write("**Skills:**")
                            skills = data['SkillsKeywords']['OperationalSkills']['SkillSet']
                            if skills:
                                df_skills = pd.DataFrame(skills)
                                st.dataframe(df_skills, use_container_width=True)
                            else:
                                st.write("No skills detected")
                        
                        with col2:
                            st.write("**Experience:**")
                            st.write("- **Worked Period:**", data['WorkedPeriod'])
                            st.write("- **Current Employer:**", data['CurrentEmployer'])
                            st.write("- **Job Profile:**", data['JobProfile'])
                        
                        st.write("**Education:**")
                        st.write(data['Qualification'])
                    
                    with tab4:
                        st.subheader("Download Parsed Data")
                        
                        # JSON download
                        json_string = json.dumps(parsed_data, indent=2)
                        st.download_button(
                            label="📥 Download JSON",
                            data=json_string,
                            file_name=f"parsed_{uploaded_file.name}.json",
                            mime="application/json"
                        )
                        
                        # Display JSON
                        st.subheader("JSON Output")
                        st.json(parsed_data)
                        
                        # Display raw text
                        with st.expander("View Extracted Text"):
                            st.text_area("Raw extracted text:", text_content, height=300)
                
                except Exception as e:
                    st.error(f"Error parsing resume: {str(e)}")
                    st.exception(e)

if __name__ == "__main__":
    main()
