import re
import nltk
from datetime import datetime, timedelta
import spacy

# Download required NLTK data (run once)
# nltk.download('punkt')
# nltk.download('averaged_perceptron_tagger')
# nltk.download('maxent_ne_chunker')
# nltk.download('words')

class EnhancedResumeParser(ResumeParser):
    def __init__(self):
        super().__init__()
        # Common prefixes and suffixes for names
        self.name_prefixes = ['mr', 'mrs', 'ms', 'dr', 'prof', 'professor', 'sir', 'madam']
        self.name_suffixes = ['jr', 'sr', 'ii', 'iii', 'iv', 'phd', 'md', 'esq', 'cpa', 'pe']
        
        # Common resume headers that might contain names
        self.resume_headers = ['resume', 'cv', 'curriculum vitae', 'profile', 'about']
        
        # Skills experience keywords
        self.experience_keywords = [
            'years of experience', 'years experience', 'year of experience', 'year experience',
            'months of experience', 'months experience', 'month of experience', 'month experience',
            'experience in', 'experienced in', 'proficient in', 'skilled in', 'expert in',
            'working with', 'worked with', 'using', 'utilized', 'developed using',
            'programming in', 'coding in', 'development in'
        ]

    def _extract_name_enhanced(self, text):
        """Enhanced name extraction with multiple strategies"""
        lines = text.split('\n')
        potential_names = []
        
        # Strategy 1: Look for names in the first few lines (original logic enhanced)
        for i, line in enumerate(lines[:15]):
            line = line.strip()
            if not line or len(line) < 3:
                continue
            
            # Clean the line
            cleaned_line = re.sub(r'[^\w\s]', ' ', line)
            cleaned_line = re.sub(r'\s+', ' ', cleaned_line).strip()
            
            # Skip lines with common resume elements
            skip_patterns = [
                r'\b(phone|email|address|contact|summary|objective|experience|education|skills|resume|cv)\b',
                r'\b\d+\b',  # Lines with numbers
                r'@',  # Email addresses
                r'(http|www)',  # URLs
                r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b'  # Dates
            ]
            
            if any(re.search(pattern, cleaned_line, re.IGNORECASE) for pattern in skip_patterns):
                continue
            
            # Look for capitalized words that could be names
            words = re.findall(r'\b[A-Z][a-z]{1,15}\b', cleaned_line)
            
            # Filter out common non-name words
            non_name_words = ['Resume', 'Curriculum', 'Vitae', 'Profile', 'Summary', 'Objective', 
                            'Professional', 'Personal', 'Contact', 'Information', 'Details']
            words = [word for word in words if word not in non_name_words]
            
            if 2 <= len(words) <= 4 and len(' '.join(words)) <= 50:
                confidence = self._calculate_name_confidence(words, i, cleaned_line)
                potential_names.append({
                    'name': words,
                    'confidence': confidence,
                    'line_number': i,
                    'source': 'header_scan'
                })
        
        # Strategy 2: Look for "Name:" patterns
        name_patterns = [
            r'(?:name|full name|candidate name):\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})',
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s*(?:resume|cv)',
            r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})$'  # Names on their own line
        ]
        
        for pattern in name_patterns:
            matches = re.findall(pattern, text, re.MULTILINE | re.IGNORECASE)
            for match in matches:
                words = match.split()
                if 2 <= len(words) <= 4:
                    potential_names.append({
                        'name': words,
                        'confidence': 0.8,
                        'source': 'pattern_match'
                    })
        
        # Strategy 3: Use NLP for named entity recognition (if available)
        try:
            import nltk
            from nltk import ne_chunk, pos_tag, word_tokenize
            
            # Tokenize and tag the first 500 words
            tokens = word_tokenize(text[:2000])
            pos_tags = pos_tag(tokens)
            chunks = ne_chunk(pos_tags)
            
            for chunk in chunks:
                if hasattr(chunk, 'label') and chunk.label() == 'PERSON':
                    name_words = [token for token, pos in chunk]
                    if 2 <= len(name_words) <= 4:
                        potential_names.append({
                            'name': name_words,
                            'confidence': 0.7,
                            'source': 'nlp_ner'
                        })
        except:
            pass  # NLP libraries not available
        
        # Select the best name
        if potential_names:
            best_name = max(potential_names, key=lambda x: x['confidence'])
            return self._assign_name_parts(best_name['name'])
        
        return None

    def _calculate_name_confidence(self, words, line_number, line_text):
        """Calculate confidence score for potential name"""
        confidence = 0.5
        
        # Higher confidence for names in the first few lines
        if line_number <= 3:
            confidence += 0.3
        elif line_number <= 6:
            confidence += 0.2
        
        # Higher confidence for proper name patterns
        if len(words) == 2:  # First Last
            confidence += 0.2
        elif len(words) == 3:  # First Middle Last
            confidence += 0.3
        
        # Check if words look like names (not all caps, reasonable length)
        for word in words:
            if word.isupper() and len(word) > 3:
                confidence -= 0.1  # Penalize all caps
            if len(word) > 15:
                confidence -= 0.2  # Penalize very long words
        
        # Check if line contains only the name (good indicator)
        if len(line_text.split()) == len(words):
            confidence += 0.2
        
        return min(confidence, 1.0)

    def _assign_name_parts(self, name_words):
        """Assign name parts based on number of words"""
        if len(name_words) == 2:
            self.parsed_data["ResumeParserData"]["FirstName"] = name_words[0]
            self.parsed_data["ResumeParserData"]["LastName"] = name_words[1]
        elif len(name_words) == 3:
            self.parsed_data["ResumeParserData"]["FirstName"] = name_words[0]
            self.parsed_data["ResumeParserData"]["Middlename"] = name_words[1]
            self.parsed_data["ResumeParserData"]["LastName"] = name_words[2]
        elif len(name_words) == 4:
            self.parsed_data["ResumeParserData"]["FirstName"] = name_words[0]
            self.parsed_data["ResumeParserData"]["Middlename"] = ' '.join(name_words[1:3])
            self.parsed_data["ResumeParserData"]["LastName"] = name_words[3]
        
        return True

    def _extract_skill_specific_experience(self, skill, text):
        """Extract specific experience for individual skills"""
        skill_lower = skill.lower()
        text_lower = text.lower()
        
        # Patterns to look for skill-specific experience
        patterns = [
            # "5 years of Python experience"
            rf'(\d+(?:\.\d+)?)\s*(?:years?|yrs?)\s*(?:of\s+)?(?:experience\s+)?(?:with\s+|in\s+|using\s+)?{re.escape(skill_lower)}',
            # "Python: 3 years"
            rf'{re.escape(skill_lower)}\s*:?\s*(\d+(?:\.\d+)?)\s*(?:years?|yrs?)',
            # "Experienced in Python (5 years)"
            rf'(?:experienced?|proficient|skilled|expert)\s+(?:in\s+|with\s+)?{re.escape(skill_lower)}\s*\(?(\d+(?:\.\d+)?)\s*(?:years?|yrs?)',
            # "Python (5+ years)"
            rf'{re.escape(skill_lower)}\s*\(?(\d+(?:\.\d+)?)\+?\s*(?:years?|yrs?)',
            # "5+ years Python"
            rf'(\d+(?:\.\d+)?)\+?\s*(?:years?|yrs?)\s*(?:of\s+)?{re.escape(skill_lower)}',
        ]
        
        max_years = 0
        for pattern in patterns:
            matches = re.findall(pattern, text_lower)
            if matches:
                try:
                    years = max([float(match) for match in matches if isinstance(match, str)])
                    max_years = max(max_years, years)
                except:
                    continue
        
        if max_years > 0:
            return int(max_years * 12)  # Convert to months
        
        # If no specific experience found, estimate based on context
        return self._estimate_skill_experience_from_context(skill, text)

    def _estimate_skill_experience_from_context(self, skill, text):
        """Estimate skill experience from job context and timeline"""
        skill_lower = skill.lower()
        text_lower = text.lower()
        
        # Find job periods where this skill might have been used
        job_periods = self._extract_job_periods(text)
        skill_mentions = []
        
        # Find all mentions of the skill in the text
        for match in re.finditer(re.escape(skill_lower), text_lower):
            start = max(0, match.start() - 500)  # 500 chars before
            end = min(len(text), match.end() + 500)  # 500 chars after
            context = text_lower[start:end]
            skill_mentions.append((match.start(), context))
        
        total_experience_months = 0
        
        # For each skill mention, try to associate it with a job period
        for position, context in skill_mentions:
            # Look for date patterns in the context
            date_patterns = [
                r'(\d{4})\s*(?:to|[-–])\s*(\d{4}|present|current)',
                r'(\w{3,9}\s+\d{4})\s*(?:to|[-–])\s*(\w{3,9}\s+\d{4}|present|current)',
                r'(\d{1,2}/\d{4})\s*(?:to|[-–])\s*(\d{1,2}/\d{4}|present|current)'
            ]
            
            for pattern in date_patterns:
                matches = re.findall(pattern, context)
                if matches:
                    start_date, end_date = matches[0]
                    months = self._calculate_months_between_dates(start_date, end_date)
                    total_experience_months = max(total_experience_months, months)
                    break
        
        # If we found context-based experience, use it
        if total_experience_months > 0:
            return min(total_experience_months, 120)  # Cap at 10 years
        
        # Fallback: estimate based on skill category and overall experience
        return self._estimate_by_skill_category(skill, text)

    def _extract_job_periods(self, text):
        """Extract all job periods from the text"""
        periods = []
        date_patterns = [
            r'(\d{4})\s*(?:to|[-–])\s*(\d{4}|present|current)',
            r'(\w{3,9}\s+\d{4})\s*(?:to|[-–])\s*(\w{3,9}\s+\d{4}|present|current)',
            r'(\d{1,2}/\d{4})\s*(?:to|[-–])\s*(\d{1,2}/\d{4}|present|current)'
        ]
        
        for pattern in date_patterns:
            matches = re.findall(pattern, text)
            for start_date, end_date in matches:
                months = self._calculate_months_between_dates(start_date, end_date)
                periods.append({
                    'start': start_date,
                    'end': end_date,
                    'months': months
                })
        
        return periods

    def _calculate_months_between_dates(self, start_date, end_date):
        """Calculate months between two date strings"""
        try:
            # Handle "present" or "current"
            if end_date.lower() in ['present', 'current']:
                end_date = datetime.now().strftime('%Y')
            
            # Try to parse different date formats
            if re.match(r'^\d{4}$', start_date):  # Year only
                start = datetime(int(start_date), 1, 1)
                end = datetime(int(end_date), 12, 31) if re.match(r'^\d{4}$', end_date) else datetime.now()
            else:
                # More complex parsing for month/year formats
                start = self._parse_flexible_date(start_date)
                end = self._parse_flexible_date(end_date) if end_date.lower() not in ['present', 'current'] else datetime.now()
            
            # Calculate months
            months = (end.year - start.year) * 12 + (end.month - start.month)
            return max(0, months)
        
        except:
            return 24  # Default to 2 years if parsing fails

    def _parse_flexible_date(self, date_str):
        """Parse various date formats"""
        date_str = date_str.strip()
        
        # Month year format (e.g., "January 2020", "Jan 2020")
        month_year_pattern = r'(\w{3,9})\s+(\d{4})'
        match = re.match(month_year_pattern, date_str)
        if match:
            month_name, year = match.groups()
            month_map = {
                'jan': 1, 'january': 1, 'feb': 2, 'february': 2, 'mar': 3, 'march': 3,
                'apr': 4, 'april': 4, 'may': 5, 'jun': 6, 'june': 6,
                'jul': 7, 'july': 7, 'aug': 8, 'august': 8, 'sep': 9, 'september': 9,
                'oct': 10, 'october': 10, 'nov': 11, 'november': 11, 'dec': 12, 'december': 12
            }
            month_num = month_map.get(month_name.lower(), 1)
            return datetime(int(year), month_num, 1)
        
        # MM/YYYY format
        if '/' in date_str:
            parts = date_str.split('/')
            if len(parts) == 2:
                return datetime(int(parts[1]), int(parts[0]), 1)
        
        # Year only
        if re.match(r'^\d{4}$', date_str):
            return datetime(int(date_str), 1, 1)
        
        return datetime.now()

    def _estimate_by_skill_category(self, skill, text):
        """Estimate experience based on skill category and career level"""
        skill_lower = skill.lower()
        
        # Categorize skills
        senior_indicators = ['senior', 'lead', 'principal', 'architect', 'manager', 'director']
        junior_indicators = ['junior', 'entry', 'intern', 'trainee', 'associate']
        
        text_lower = text.lower()
        is_senior = any(indicator in text_lower for indicator in senior_indicators)
        is_junior = any(indicator in text_lower for indicator in junior_indicators)
        
        # Programming languages typically have longer learning curves
        programming_languages = ['python', 'java', 'javascript', 'c++', 'c#', 'go', 'rust', 'scala']
        
        # Databases and tools can be learned faster
        tools_and_frameworks = ['excel', 'tableau', 'power bi', 'jira', 'confluence']
        
        if skill_lower in programming_languages:
            if is_senior:
                return 60  # 5 years
            elif is_junior:
                return 18  # 1.5 years
            else:
                return 36  # 3 years
        elif skill_lower in tools_and_frameworks:
            if is_senior:
                return 36  # 3 years
            elif is_junior:
                return 12  # 1 year
            else:
                return 24  # 2 years
        else:
            # General skills
            if is_senior:
                return 48  # 4 years
            elif is_junior:
                return 15  # 1.25 years
            else:
                return 30  # 2.5 years

    def extract_personal_info(self, text):
        """Enhanced personal information extraction"""
        # Call the original method first
        super().extract_personal_info(text)
        
        # Then try enhanced name extraction if name wasn't found
        if not self.parsed_data["ResumeParserData"]["FirstName"]:
            self._extract_name_enhanced(text)

    def extract_skills(self, text):
        """Enhanced skills extraction with better experience estimation"""
        # Use the original skill keywords
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
                # Use enhanced experience estimation
                experience_months = self._extract_skill_specific_experience(skill, text)
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

# Example usage of the enhanced parser
def main_enhanced():
    # Page configuration
    st.set_page_config(
        page_title="TrackTalents Resume Parser - Enhanced",
        page_icon="🎯",
        layout="wide"
    )
    
    # Apply custom CSS (same as before)
    apply_custom_css()
    
    # TrackTalents Header
    create_track_talents_header()
    
    st.markdown("## 🚀 Enhanced Resume Parser")
    st.markdown("**New Features:** Improved name detection & accurate skills experience estimation")
    
    # File upload
    uploaded_file = st.file_uploader(
        "Choose a resume file",
        type=['pdf', 'docx', 'txt'],
        help="Supported formats: PDF, DOCX, TXT"
    )
    
    if uploaded_file is not None:
        if st.button("🔍 Parse with Enhanced AI", type="primary"):
            with st.spinner("Processing with enhanced algorithms..."):
                # Use the enhanced parser
                parser = EnhancedResumeParser()
                
                # Extract text based on file type
                file_extension = uploaded_file.name.split('.')[-1].lower()
                
                try:
                    if file_extension == 'pdf':
                        text_content = parser.extract_text_from_pdf(uploaded_file)
                    elif file_extension == 'docx':
                        text_content = parser.extract_text_from_docx(uploaded_file)
                    elif file_extension == 'txt':
                        text_content = parser.extract_text_from_txt(uploaded_file)
                    
                    if not text_content.strip():
                        st.error("Could not extract text from the file")
                        return
                    
                    # Parse the resume with enhanced methods
                    parsed_data = parser.parse_resume(text_content, uploaded_file.name)
                    
                    st.success("✅ Resume parsed with enhanced AI!")
                    
                    # Display enhanced results
                    data = parsed_data["ResumeParserData"]
                    
                    # Show improvements
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.subheader("📋 Enhanced Name Detection")
                        full_name = f"{data['FirstName']} {data['Middlename']} {data['LastName']}".strip()
                        if full_name.strip():
                            st.success(f"✅ **Name Found:** {full_name}")
                        else:
                            st.warning("⚠️ Name not detected")
                    
                    with col2:
                        st.subheader("🛠️ Enhanced Skills Analysis")
                        skills = data['SkillsKeywords']['OperationalSkills']['SkillSet']
                        if skills:
                            st.success(f"✅ **Skills Found:** {len(skills)} with experience estimates")
                            
                            # Show top skills with experience
                            for skill in skills[:5]:
                                months = int(skill['ExperienceInMonths'])
                                years = months // 12
                                remaining_months = months % 12
                                
                                if years > 0:
                                    exp_str = f"{years}y {remaining_months}m" if remaining_months > 0 else f"{years}y"
                                else:
                                    exp_str = f"{remaining_months}m"
                                
                                st.write(f"• **{skill['Skill']}**: {exp_str}")
                        else:
                            st.warning("⚠️ No skills detected")
                    
                    # Skills experience breakdown
                    if skills:
                        st.subheader("📊 Skills Experience Breakdown")
                        
                        # Create DataFrame for better visualization
                        skills_df = pd.DataFrame(skills)
                        skills_df['ExperienceYears'] = skills_df['ExperienceInMonths'].astype(int) / 12
                        skills_df['ExperienceYears'] = skills_df['ExperienceYears'].round(1)
                        
                        # Sort by experience
                        skills_df = skills_df.sort_values('ExperienceYears', ascending=False)
                        
                        # Display as a nice table
                        display_df = skills_df[['Skill', 'ExperienceYears']].copy()
                        display_df.columns = ['Skill', 'Years of Experience']
                        
                        st.dataframe(display_df, use_container_width=True)
                        
                        # Download enhanced JSON
                        json_string = json.dumps(parsed_data, indent=2)
                        st.download_button(
                            label="📥 Download Enhanced JSON",
                            data=json_string,
                            file_name=f"enhanced_parsed_{uploaded_file.name}.json",
                            mime="application/json",
                            use_container_width=True
                        )
                
                except Exception as e:
                    st.error(f"Error parsing resume: {str(e)}")
                    st.exception(e)

if __name__ == "__main__":
    main_enhanced()
