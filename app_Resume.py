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
            
            # Extract text from tables
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        text += cell.text + " "
                    text += "\n"
            
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

        # Phone extraction with enhanced patterns
        phone_patterns = [
            r'\+?1?[-.\s]?\(?(\d{3})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})',
            r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
            r'\(\d{3}\)\s?\d{3}[-.]?\d{4}',
            r'\+\d{1,3}[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}'
        ]
        
        for pattern in phone_patterns:
            phones = re.findall(pattern, text)
            if phones:
                if isinstance(phones[0], tuple):
                    phone = ''.join(phones[0])
                else:
                    phone = phones[0]
                self.parsed_data["ResumeParserData"]["Phone"] = phone.strip()
                break

        # LinkedIn URL extraction
        linkedin_pattern = r'(?:https?://)?(?:www\.)?linkedin\.com/in/[\w\-]+'
        linkedin_urls = re.findall(linkedin_pattern, text, re.IGNORECASE)
        if linkedin_urls:
            self.parsed_data["ResumeParserData"]["LinkedInProfileUrl"] = linkedin_urls[0]

        # Enhanced name extraction
        self._extract_name(text)
        
        # Address extraction
        self._extract_address(text)

    def _extract_name(self, text):
        """Extract name from resume text"""
        lines = text.split('\n')
        
        # Look for name in first few lines
        for line in lines[:10]:
            line = line.strip()
            if not line or len(line) < 3:
                continue
                
            # Skip lines with numbers, emails, or common resume words
            skip_words = ['resume', 'cv', 'curriculum', 'vitae', 'phone', 'email', 'address', 'contact', 'summary', 'objective']
            if (any(char.isdigit() for char in line) or 
                '@' in line or 
                any(word.lower() in line.lower() for word in skip_words)):
                continue
            
            # Look for capitalized words that could be names
            words = re.findall(r'\b[A-Z][a-z]+\b', line)
            if len(words) >= 2 and len(words) <= 4 and len(' '.join(words)) < 50:
                if len(words) == 2:
                    self.parsed_data["ResumeParserData"]["FirstName"] = words[0]
                    self.parsed_data["ResumeParserData"]["LastName"] = words[1]
                elif len(words) == 3:
                    self.parsed_data["ResumeParserData"]["FirstName"] = words[0]
                    self.parsed_data["ResumeParserData"]["Middlename"] = words[1]
                    self.parsed_data["ResumeParserData"]["LastName"] = words[2]
                elif len(words) == 4:
                    self.parsed_data["ResumeParserData"]["FirstName"] = words[0]
                    self.parsed_data["ResumeParserData"]["Middlename"] = ' '.join(words[1:3])
                    self.parsed_data["ResumeParserData"]["LastName"] = words[3]
                break

    def _extract_address(self, text):
        """Extract address information"""
        # US states
        us_states = [
            'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA', 'HI', 'ID', 'IL', 'IN', 'IA', 'KS',
            'KY', 'LA', 'ME', 'MD', 'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ', 'NM', 'NY',
            'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC', 'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY'
        ]
        
        # Zip code pattern
        zip_pattern = r'\b\d{5}(?:-\d{4})?\b'
        zip_codes = re.findall(zip_pattern, text)
        if zip_codes:
            self.parsed_data["ResumeParserData"]["ZipCode"] = zip_codes[0]
        
        # State extraction
        for state in us_states:
            if f' {state} ' in text or f' {state},' in text or f'{state} ' in text:
                self.parsed_data["ResumeParserData"]["State"] = state
                break

        # City extraction (basic)
        city_pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*[A-Z]{2}'
        cities = re.findall(city_pattern, text)
        if cities:
            self.parsed_data["ResumeParserData"]["City"] = cities[0]

    def extract_skills(self, text):
        """Extract skills from text with comprehensive database"""
        # Enhanced skill keywords matching original examples
        skill_keywords = [
            # Programming Languages
            'Python', 'Java', 'JavaScript', 'TypeScript', 'C++', 'C#', 'C', 'Go', 'Rust', 'Kotlin',
            'Swift', 'PHP', 'Ruby', 'Scala', 'R', 'MATLAB', 'Perl', 'VB.Net', 'ASP.Net', 'T-SQL', 'PL/SQL',
            
            # Databases
            'SQL', 'MySQL', 'PostgreSQL', 'Oracle', 'SQL Server', 'MongoDB', 'SQLite', 'Redis', 'Cassandra',
            'DynamoDB', 'Neo4j', 'Teradata', 'Snowflake', 'BigQuery', 'MS Access', 'DB2', 'Oracle11g', 'Oracle 10g',
            
            # Cloud & DevOps
            'AWS', 'Azure', 'GCP', 'Google Cloud', 'Docker', 'Kubernetes', 'Jenkins', 'Git', 'GitLab', 'GitHub',
            'CI/CD', 'DevOps', 'Terraform', 'Ansible', 'Chef', 'Puppet', 'Vagrant',
            
            # Data & Analytics
            'ETL', 'SSIS', 'SSRS', 'SSAS', 'Data Science', 'Machine Learning', 'AI', 'Tableau', 'Power BI',
            'Excel', 'Informatica', 'Databricks', 'Apache Spark', 'Hadoop', 'Kafka', 'Airflow',
            'Pandas', 'NumPy', 'Matplotlib', 'Seaborn', 'TensorFlow', 'PyTorch', 'Scikit-learn',
            
            # Web Technologies
            'HTML', 'CSS', 'React', 'Angular', 'Vue.js', 'Node.js', 'Express', 'Django', 'Flask',
            'Spring', 'Spring Boot', 'Laravel', 'Bootstrap', 'jQuery', 'REST API', 'GraphQL', 'SOAP',
            
            # Tools & Utilities
            'Visual Studio', 'VS Code', 'Eclipse', 'IntelliJ', 'Postman', 'Jira', 'Confluence', 'Slack',
            'Teams', 'SharePoint', 'Agile', 'Scrum', 'Kanban', 'Waterfall',
            
            # Microsoft Technologies
            'SSMS', 'Analysis Manager', 'Query Analyzer', 'Business Intelligence Development studio',
            'DTS', 'SQL Profiler', 'Visual Studio 2019', 'Visual Studio 2015', 'Visual Studio 2012',
            'Visual Studio 2008', 'Visual Studio 2010', 'Windows Server', 'IIS',
            
            # Reporting & BI
            'Crystal Reports', 'Business Objects', 'OBIEE', 'QlikView', 'Looker', 'Spotfire',
            
            # Project Management
            'Microsoft Project', 'Asana', 'Trello', 'Monday.com', 'Basecamp'
        ]
        
        found_skills = []
        text_upper = text.upper()
        
        # Check for skills with word boundaries to avoid partial matches
        for skill in skill_keywords:
            # Use word boundaries and case insensitive matching
            pattern = r'\b' + re.escape(skill.upper()) + r'\b'
            if re.search(pattern, text_upper):
                # Estimate experience based on context
                experience_months = self._estimate_experience(skill, text)
                found_skills.append({
                    "Skill": skill,
                    "ExperienceInMonths": str(experience_months)
                })
        
        # Remove duplicates while preserving order
        unique_skills = []
        seen_skills = set()
        for skill in found_skills:
            if skill["Skill"] not in seen_skills:
                seen_skills.add(skill["Skill"])
                unique_skills.append(skill)
        
        self.parsed_data["ResumeParserData"]["SkillsKeywords"]["OperationalSkills"]["SkillSet"] = unique_skills
        self.parsed_data["ResumeParserData"]["Skills"] = ", ".join([skill["Skill"] for skill in unique_skills])

    def _estimate_experience(self, skill, text):
        """Estimate experience for a skill based on context"""
        # Look for years of experience in the text
        exp_patterns = [
            r'(\d+)\+?\s*years?\s*of\s*experience',
            r'(\d+)\+?\s*years?\s*experience',
            r'experience\s*:?\s*(\d+)\+?\s*years?'
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
            return 24  # Default 2 years

    def extract_experience(self, text):
        """Extract work experience from text"""
        # Look for experience patterns
        exp_patterns = [
            r'(\d+)\+?\s*years?\s*of\s*experience',
            r'(\d+)\+?\s*years?\s*experience',
            r'experience\s*:?\s*(\d+)\+?\s*years?',
            r'(\d+)\+?\s*years?\s*in'
        ]
        
        years_exp = 0
        for pattern in exp_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                years_exp = max([int(match) for match in matches])
                break
        
        if years_exp > 0:
            months = years_exp * 12
            if years_exp > 1:
                self.parsed_data["ResumeParserData"]["WorkedPeriod"] = f"{years_exp} Years and {months % 12} Months" if months % 12 > 0 else f"{years_exp} Years"
            else:
                self.parsed_data["ResumeParserData"]["WorkedPeriod"] = f"{years_exp} Year"
            
            # Set experience description
            if years_exp >= 10:
                self.parsed_data["ResumeParserData"]["Experience"] = f"Results-driven professional with {years_exp}+ years of extensive experience"
            elif years_exp >= 5:
                self.parsed_data["ResumeParserData"]["Experience"] = f"Experienced professional with {years_exp} years of solid experience"
            else:
                self.parsed_data["ResumeParserData"]["Experience"] = f"Professional with {years_exp} years of experience"

        # Extract work history
        work_history = self._extract_work_history(text)
        self.parsed_data["ResumeParserData"]["SegrigatedExperience"]["WorkHistory"] = work_history
        
        # Set current employer
        if work_history:
            self.parsed_data["ResumeParserData"]["CurrentEmployer"] = work_history[0].get("Employer", "")
            self.parsed_data["ResumeParserData"]["JobProfile"] = work_history[0].get("JobProfile", "")

    def _extract_work_history(self, text):
        """Extract detailed work history"""
        work_history = []
        
        # Company patterns
        company_patterns = [
            r'(?:Client|Company|Employer):\s*([A-Z][A-Za-z\s&.,-]+)',
            r'([A-Z][A-Za-z\s&.,-]+(?:Inc|LLC|Corp|Company|Ltd|Limited|Group|Technologies|Systems|Solutions|Consulting|Services))',
            r'at\s+([A-Z][A-Za-z\s&.,-]+)',
            r'([A-Z][A-Za-z\s&.,-]+)\s*[-,]\s*([A-Z][a-z]+,?\s*[A-Z]{2})'  # Company - Location pattern
        ]
        
        companies = []
        for pattern in company_patterns:
            matches = re.findall(pattern, text)
            if isinstance(matches[0], tuple) if matches else False:
                companies.extend([match[0].strip() for match in matches if len(match[0].strip()) > 2])
            else:
                companies.extend([match.strip() for match in matches if len(match.strip()) > 2])
        
        # Job title patterns
        job_patterns = [
            r'(?:Position|Role|Title|Job Profile):\s*([A-Z][A-Za-z\s]+)',
            r'^([A-Z][A-Za-z\s]+(?:Engineer|Developer|Analyst|Manager|Consultant|Architect|Lead|Director|Specialist))$',
            r'([A-Z][A-Za-z\s]+(?:Engineer|Developer|Analyst|Manager|Consultant|Architect|Lead|Director|Specialist))\s*[-,]'
        ]
        
        job_titles = []
        for pattern in job_patterns:
            matches = re.findall(pattern, text, re.MULTILINE)
            job_titles.extend([match.strip() for match in matches])
        
        # Date patterns for job periods
        date_patterns = [
            r'(\w+\s*\d{2,4})\s*(?:to|[-–])\s*(\w+\s*\d{2,4}|Present|Current)',
            r'(\d{1,2}/\d{2,4})\s*(?:to|[-–])\s*(\d{1,2}/\d{2,4}|Present|Current)',
            r'(\w{3}\d{2})\s*(?:to|[-–])\s*(\w{3}\d{2}|Present|Current)'
        ]
        
        dates = []
        for pattern in date_patterns:
            matches = re.findall(pattern, text)
            dates.extend(matches)
        
        # Remove duplicates while preserving order
        unique_companies = []
        seen = set()
        for company in companies:
            if company not in seen and len(company) > 3:
                seen.add(company)
                unique_companies.append(company)
        
        # Create work history entries matching the original format
        for i, company in enumerate(unique_companies[:5]):
            work_entry = {
                "Employer": company,
                "JobProfile": job_titles[i] if i < len(job_titles) else "Not specified",
                "JobLocation": "Not specified",
                "JobPeriod": f"{dates[i][0]} to {dates[i][1]}" if i < len(dates) else "Not specified",
                "StartDate": self._convert_date_format(dates[i][0]) if i < len(dates) else "Not specified",
                "EndDate": self._convert_date_format(dates[i][1]) if i < len(dates) else "Not specified",
                "JobDescription": "Not specified"
            }
            work_history.append(work_entry)
        
        return work_history

    def _convert_date_format(self, date_str):
        """Convert date string to standard format"""
        if not date_str or date_str.lower() in ['present', 'current']:
            return datetime.now().strftime("%d/%m/%Y")
        
        # Try to parse common date formats and convert to dd/mm/yyyy
        try:
            # Handle various date formats
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 2:
                    month, year = parts
                    return f"1/{month}/{year}"
            elif len(date_str) == 5 and date_str[3:].isdigit():  # Like "Jan24"
                month_map = {
                    'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
                    'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
                    'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
                }
                month_str = date_str[:3]
                year_str = "20" + date_str[3:]
                if month_str in month_map:
                    return f"1/{month_map[month_str]}/{year_str}"
        except:
            pass
        
        return date_str

    def extract_education(self, text):
        """Extract education information"""
        education_patterns = [
            r'(?i)(?:bachelor|b\.?s\.?|b\.?a\.?|b\.?tech|b\.?e\.?)\s*(?:of|in)?\s*([a-zA-Z\s]+)',
            r'(?i)(?:master|m\.?s\.?|m\.?a\.?|m\.?tech|m\.?e\.?|mba)\s*(?:of|in)?\s*([a-zA-Z\s]+)',
            r'(?i)(?:phd|ph\.?d\.?|doctorate)\s*(?:of|in)?\s*([a-zA-Z\s]+)',
            r'(?i)(?:diploma|certificate)\s*(?:of|in)?\s*([a-zA-Z\s]+)'
        ]
        
        education_info = []
        for pattern in education_patterns:
            matches = re.findall(pattern, text)
            education_info.extend([match.strip() for match in matches if len(match.strip()) > 2])
        
        # University patterns
        university_patterns = [
            r'([A-Z][A-Za-z\s]+(?:University|College|Institute|School))',
            r'(?:University|College|Institute|School)\s+of\s+([A-Za-z\s]+)',
            r'([A-Z]{2,4}),\s*([A-Z]{2}),\s*(USA|India|UK|Canada)'  # Location pattern
        ]
        
        universities = []
        for pattern in university_patterns:
            matches = re.findall(pattern, text)
            if matches:
                if isinstance(matches[0], tuple):
                    universities.extend([match[0].strip() for match in matches if len(match[0].strip()) > 3])
                else:
                    universities.extend([match.strip() for match in matches if len(match.strip()) > 3])
        
        # Combine education info
        education_text = ""
        if education_info:
            education_text += ", ".join(education_info[:3])
        if universities:
            if education_text:
                education_text += " from "
            education_text += ", ".join(universities[:2])
        
        self.parsed_data["ResumeParserData"]["Qualification"] = education_text.strip()

    def categorize_resume(self, text):
        """Categorize resume based on content"""
        text_lower = text.lower()
        
        categories = {
            "Software/IT": ["software", "developer", "engineer", "programming", "coding", "java", "python", "javascript", "technical"],
            "Data/Analytics": ["data", "analyst", "analytics", "science", "machine learning", "sql", "tableau", "power bi", "etl"],
            "Management": ["manager", "director", "lead", "supervisor", "management", "leadership"],
            "Consulting": ["consultant", "consulting", "advisory", "strategy"],
            "Finance": ["finance", "accounting", "financial", "banking", "investment"]
        }
        
        # Score each category
        category_scores = {}
        for category, keywords in categories.items():
            score = sum(text_lower.count(keyword) for keyword in keywords)
            category_scores[category] = score
        
        # Get best category
        if category_scores:
            best_category = max(category_scores, key=category_scores.get)
            if category_scores[best_category] > 0:
                self.parsed_data["ResumeParserData"]["Category"] = best_category
                
                # Set subcategory
                if best_category == "Software/IT":
                    if "senior" in text_lower or "lead" in text_lower:
                        self.parsed_data["ResumeParserData"]["SubCategory"] = "Senior Software Engineer"
                    elif "data" in text_lower:
                        self.parsed_data["ResumeParserData"]["SubCategory"] = "Data Engineer"
                    else:
                        self.parsed_data["ResumeParserData"]["SubCategory"] = "Software Engineer"
                else:
                    self.parsed_data["ResumeParserData"]["SubCategory"] = best_category + " Professional"

    def parse_resume(self, file_content, filename):
        """Main parsing function"""
        # Reset data structure for new parsing
        self.__init__()
        
        # Set basic info
        self.parsed_data["ResumeParserData"]["ResumeFileName"] = filename
        self.parsed_data["ResumeParserData"]["ParsingDate"] = datetime.now().strftime("%m/%d/%Y %I:%M:%S %p")
        self.parsed_data["ResumeParserData"]["DetailResume"] = file_content
        
        # Extract all information
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
    }
    
    .track-talents-logo {
        font-size: 3rem;
        font-weight: 700;
        color: white;
        margin-bottom: 0.5rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
    }
    
    .track-talents-tagline {
        font-size: 1.3rem;
        color: rgba(255,255,255,0.95);
        font-weight: 300;
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
    }
    
    .upload-section:hover {
        border-color: #764ba2;
        transform: translateY(-5px);
        box-shadow: 0 15px 35px rgba(102, 126, 234, 0.2);
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
    </style>
    """, unsafe_allow_html=True)

def create_track_talents_header():
    """Create the TrackTalents branded header"""
    st.markdown("""
    <div class="track-talents-header">
        <div class="track-talents-logo">🎯 TrackTalents</div>
        <div class="track-talents-tagline">AI-Powered Resume Parser & Talent Analytics</div>
    </div>
    """, unsafe_allow_html=True)

def main():
    # Page configuration
    st.set_page_config(
        page_title="TrackTalents Resume Parser",
        page_icon="🎯",
        layout="wide"
    )
    
    # Apply custom CSS
    apply_custom_css()
    
    # TrackTalents Header
    create_track_talents_header()
    
    # Sidebar with proper styling
    st.sidebar.header("📋 Instructions")
    st.sidebar.markdown("""
    **How to Use:**
    1. Upload your resume file
    2. Supported formats: PDF, DOCX, TXT
    3. Click 'Parse Resume' to extract information
    4. Download the structured JSON data
    
    **Features:**
    - Advanced AI parsing
    - Skills detection
    - Contact extraction
    - Work history analysis
    - Education parsing
    - JSON export
    """)
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Support:**")
    st.sidebar.markdown("📧 support@tracktalents.com")
    st.sidebar.markdown("🌐 www.tracktalents.com")
    
    # Main content
    st.markdown("## 📁 Upload Resume")
    
    # File upload
    uploaded_file = st.file_uploader(
        "Choose a resume file",
        type=['pdf', 'docx', 'txt'],
        help="Supported formats: PDF, DOCX, TXT"
    )
    
    if uploaded_file is not None:
        # Success message
        st.markdown(f"""
        <div class="success-message">
            ✅ File uploaded successfully: <strong>{uploaded_file.name}</strong>
        </div>
        """, unsafe_allow_html=True)
        
        # File information
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("File Name", uploaded_file.name)
        with col2:
            st.metric("File Size", f"{uploaded_file.size:,} bytes")
        with col3:
            st.metric("File Type", uploaded_file.type or "Unknown")
        
        if st.button("🚀 Parse Resume", type="primary"):
            with st.spinner("Processing resume..."):
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
                    
                    data = parsed_data["ResumeParserData"]
                    
                    with tab1:
                        st.subheader("Resume Summary")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write("**Name:**", f"{data['FirstName']} {data['Middlename']} {data['LastName']}".strip())
                            st.write("**Email:**", data['Email'])
                            st.write("**Phone:**", data['Phone'])
                        with col2:
                            st.write("**Category:**", data['Category'])
                            st.write("**Sub-Category:**", data['SubCategory'])
                            st.write("**Current Employer:**", data['CurrentEmployer'])
                            st.write("**Experience:**", data['WorkedPeriod'])
                    
                    with tab2:
                        st.subheader("Personal Information")
                        
                        personal_data = {
                            "First Name": data['FirstName'],
                            "Middle Name": data['Middlename'],
                            "Last Name": data['LastName'],
                            "Email": data['Email'],
                            "Phone": data['Phone'],
                            "LinkedIn": data['LinkedInProfileUrl'],
                            "City": data['City'],
                            "State": data['State'],
                            "Zip Code": data['ZipCode']
                        }
                        
                        df_personal = pd.DataFrame(list(personal_data.items()), columns=['Field', 'Value'])
                        st.dataframe(df_personal, use_container_width=True)
                        
                        if data['Qualification']:
                            st.subheader("Education")
                            st.write(data['Qualification'])
                    
                    with tab3:
                        st.subheader("Skills & Experience")
                        
                        # Skills section
                        skills = data['SkillsKeywords']['OperationalSkills']['SkillSet']
                        if skills:
                            st.write(f"**Skills Found:** {len(skills)}")
                            df_skills = pd.DataFrame(skills)
                            st.dataframe(df_skills, use_container_width=True)
                            
                            # Skills summary
                            skill_names = [skill['Skill'] for skill in skills]
                            st.write("**Top Skills:**", ", ".join(skill_names[:10]))
                        else:
                            st.write("No skills detected")
                        
                        # Experience section
                        st.subheader("Work Experience")
                        st.write("**Total Experience:**", data['WorkedPeriod'])
                        st.write("**Current Employer:**", data['CurrentEmployer'])
                        st.write("**Job Profile:**", data['JobProfile'])
                        
                        # Work history
                        work_history = data['SegrigatedExperience']['WorkHistory']
                        if work_history:
                            st.subheader("Work History")
                            for i, job in enumerate(work_history[:3]):
                                st.write(f"**{i+1}. {job['Employer']}** - {job['JobProfile']}")
                                st.write(f"   📅 {job['JobPeriod']}")
                    
                    with tab4:
                        st.markdown("""
                        <div class="download-section">
                            <h3 style="color: #667eea; text-align: center; margin-bottom: 2rem;">📥 Download Results</h3>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # JSON download
                        json_string = json.dumps(parsed_data, indent=2)
                        st.download_button(
                            label="📋 Download Complete JSON",
                            data=json_string,
                            file_name=f"tracktalents_parsed_{uploaded_file.name}.json",
                            mime="application/json",
                            use_container_width=True
                        )
                        
                        # Skills only download
                        skills_data = {
                            "candidate_name": f"{data['FirstName']} {data['LastName']}".strip(),
                            "skills": [skill['Skill'] for skill in skills],
                            "skills_count": len(skills),
                            "experience": data['WorkedPeriod'],
                            "category": data['Category']
                        }
                        skills_json = json.dumps(skills_data, indent=2)
                        
                        st.download_button(
                            label="🛠️ Download Skills Only",
                            data=skills_json,
                            file_name=f"skills_{uploaded_file.name}.json",
                            mime="application/json",
                            use_container_width=True
                        )
                        
                        # Display JSON
                        st.subheader("JSON Output Preview")
                        st.json(parsed_data)
                        
                        # Display raw text
                        with st.expander("View Extracted Text"):
                            st.text_area("Raw extracted text:", text_content, height=300)
                
                except Exception as e:
                    st.error(f"Error parsing resume: {str(e)}")
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
        <p style="font-size: 0.85rem; color: #999;">
            © 2025 TrackTalents. All rights reserved.
        </p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
