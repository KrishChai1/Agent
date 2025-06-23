import re
from datetime import datetime
import json

class EnhancedResumeParser:
    def __init__(self):
        # Initialize the same structure as the original parser
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
        """Extract text from PDF file - keeping original method"""
        try:
            import pdfplumber
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
            import PyPDF2
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            return ""

    def extract_text_from_docx(self, file):
        """Extract text from DOCX file - keeping original method"""
        try:
            from docx import Document
            doc = Document(file)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        text += cell.text + " "
                    text += "\n"
            
            return text
        except Exception as e:
            return ""

    def extract_text_from_txt(self, file):
        """Extract text from TXT file - keeping original method"""
        try:
            content = file.read()
            if isinstance(content, bytes):
                content = content.decode('utf-8')
            return content
        except Exception as e:
            return ""

    def extract_name_enhanced(self, text):
        """Enhanced name extraction with multiple strategies - NO external dependencies"""
        lines = text.split('\n')
        potential_names = []
        
        # Strategy 1: Look for names in the first few lines with better filtering
        for i, line in enumerate(lines[:20]):
            line = line.strip()
            if not line or len(line) < 3 or len(line) > 100:
                continue
            
            # Clean the line but preserve structure
            cleaned_line = re.sub(r'[^\w\s\-\.]', ' ', line)
            cleaned_line = re.sub(r'\s+', ' ', cleaned_line).strip()
            
            # Skip lines with obvious non-name content
            skip_patterns = [
                r'\b(phone|email|address|contact|summary|objective|experience|education|skills|resume|cv|curriculum|vitae)\b',
                r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',  # Phone numbers
                r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b',  # Emails
                r'\b(http|www|linkedin|github)\b',  # URLs
                r'\b(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b',  # Dates
                r'\b(street|st|avenue|ave|road|rd|drive|dr|lane|ln|boulevard|blvd)\b',  # Address
                r'\b(manager|engineer|developer|analyst|consultant|director|specialist|senior|junior|lead|architect)\b'  # Job titles
            ]
            
            if any(re.search(pattern, cleaned_line, re.IGNORECASE) for pattern in skip_patterns):
                continue
            
            # Look for capitalized words that could be names
            words = re.findall(r'\b[A-Z][a-z]{1,20}\b', cleaned_line)
            
            # Filter out common non-name words
            non_name_words = {
                'Resume', 'Curriculum', 'Vitae', 'Profile', 'Summary', 'Objective', 
                'Professional', 'Personal', 'Contact', 'Information', 'Details',
                'Microsoft', 'Windows', 'Office', 'Word', 'Excel', 'Adobe',
                'University', 'College', 'School', 'Institute', 'Company',
                'January', 'February', 'March', 'April', 'May', 'June',
                'July', 'August', 'September', 'October', 'November', 'December'
            }
            
            words = [word for word in words if word not in non_name_words]
            
            if 2 <= len(words) <= 4 and len(' '.join(words)) <= 60:
                confidence = self.calculate_name_confidence(words, i, cleaned_line, lines)
                potential_names.append({
                    'name': words,
                    'confidence': confidence,
                    'line_number': i,
                    'source': 'header_scan'
                })
        
        # Strategy 2: Look for explicit name patterns
        name_patterns = [
            r'(?:name|full\s*name|candidate\s*name)\s*[:\-]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})',
            r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s*(?:resume|cv|curriculum)',
            r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})$',  # Names on their own line
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s*\n\s*(?:phone|email|contact|address)',  # Name before contact
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
        
        # Strategy 3: Look for names in common resume structures
        # Names often appear before contact information
        contact_pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s*\n.*?(?:phone|email|@|\d{3}[-.]?\d{3}[-.]?\d{4})'
        contact_matches = re.findall(contact_pattern, text, re.DOTALL | re.IGNORECASE)
        for match in contact_matches:
            words = match.split()
            if 2 <= len(words) <= 4:
                potential_names.append({
                    'name': words,
                    'confidence': 0.75,
                    'source': 'contact_context'
                })
        
        # Select the best name
        if potential_names:
            # Remove duplicates
            unique_names = {}
            for name_entry in potential_names:
                name_key = ' '.join(name_entry['name']).lower()
                if name_key not in unique_names or unique_names[name_key]['confidence'] < name_entry['confidence']:
                    unique_names[name_key] = name_entry
            
            # Get the highest confidence name
            best_name = max(unique_names.values(), key=lambda x: x['confidence'])
            self.assign_name_parts(best_name['name'])
            return True
        
        return False

    def calculate_name_confidence(self, words, line_number, line_text, all_lines):
        """Calculate confidence score for potential name"""
        confidence = 0.4
        
        # Higher confidence for names in the very first lines
        if line_number == 0:
            confidence += 0.4
        elif line_number <= 2:
            confidence += 0.3
        elif line_number <= 5:
            confidence += 0.2
        elif line_number <= 10:
            confidence += 0.1
        
        # Higher confidence for proper name patterns
        if len(words) == 2:  # First Last
            confidence += 0.2
        elif len(words) == 3:  # First Middle Last or First Last Suffix
            confidence += 0.3
        
        # Check if words look like real names
        for word in words:
            # Penalize all caps (unless it's very short)
            if word.isupper() and len(word) > 3:
                confidence -= 0.15
            # Penalize very long words
            if len(word) > 20:
                confidence -= 0.2
            # Bonus for common name patterns
            if len(word) >= 3 and len(word) <= 12:
                confidence += 0.05
        
        # Check if line contains only the name (good indicator)
        if len(line_text.split()) == len(words):
            confidence += 0.25
        
        # Check if followed by contact information (strong indicator)
        if line_number < len(all_lines) - 1:
            next_lines = ' '.join(all_lines[line_number+1:line_number+3])
            if re.search(r'(phone|email|@|\d{3}[-.]?\d{3}[-.]?\d{4})', next_lines, re.IGNORECASE):
                confidence += 0.2
        
        # Check if it's at the beginning of the document
        if line_number <= 1:
            confidence += 0.15
        
        return min(confidence, 1.0)

    def assign_name_parts(self, name_words):
        """Assign name parts based on number of words"""
        if len(name_words) == 2:
            self.parsed_data["ResumeParserData"]["FirstName"] = name_words[0]
            self.parsed_data["ResumeParserData"]["LastName"] = name_words[1]
        elif len(name_words) == 3:
            # Could be First Middle Last or First Last Suffix
            potential_suffixes = ['jr', 'sr', 'ii', 'iii', 'iv', 'phd', 'md', 'esq']
            if name_words[2].lower().replace('.', '') in potential_suffixes:
                self.parsed_data["ResumeParserData"]["FirstName"] = name_words[0]
                self.parsed_data["ResumeParserData"]["LastName"] = name_words[1]
                # Could store suffix in a custom field if needed
            else:
                self.parsed_data["ResumeParserData"]["FirstName"] = name_words[0]
                self.parsed_data["ResumeParserData"]["Middlename"] = name_words[1]
                self.parsed_data["ResumeParserData"]["LastName"] = name_words[2]
        elif len(name_words) == 4:
            self.parsed_data["ResumeParserData"]["FirstName"] = name_words[0]
            self.parsed_data["ResumeParserData"]["Middlename"] = ' '.join(name_words[1:3])
            self.parsed_data["ResumeParserData"]["LastName"] = name_words[3]
        
        return True

    def extract_skill_specific_experience(self, skill, text):
        """Extract specific experience for individual skills using only regex"""
        skill_lower = skill.lower()
        text_lower = text.lower()
        
        # Patterns to look for skill-specific experience
        patterns = [
            # Direct patterns: "5 years of Python experience"
            rf'(\d+(?:\.\d+)?)\s*(?:\+\s*)?(?:years?|yrs?)\s*(?:of\s+)?(?:experience\s+)?(?:with\s+|in\s+|using\s+|of\s+)?{re.escape(skill_lower)}',
            
            # Reverse patterns: "Python: 3 years", "Python (5 years)"
            rf'{re.escape(skill_lower)}\s*[:\(]\s*(\d+(?:\.\d+)?)\s*(?:\+\s*)?(?:years?|yrs?)',
            
            # Experience descriptors: "Experienced in Python (5 years)"
            rf'(?:experienced?|proficient|skilled|expert|working)\s+(?:in\s+|with\s+)?{re.escape(skill_lower)}\s*[:\(]?\s*(\d+(?:\.\d+)?)\s*(?:\+\s*)?(?:years?|yrs?)',
            
            # Range patterns: "Python (3-5 years)", "5+ years Python"
            rf'(\d+(?:\.\d+)?)\s*(?:\+|[-–]\s*\d+)?\s*(?:years?|yrs?)\s*(?:of\s+)?(?:experience\s+)?(?:with\s+|in\s+|using\s+)?{re.escape(skill_lower)}',
            
            # Skill lists with experience: "Skills: Python (5 years)"
            rf'(?:skills?|technologies?|tools?).*?{re.escape(skill_lower)}.*?(\d+(?:\.\d+)?)\s*(?:\+\s*)?(?:years?|yrs?)',
            
            # Project duration: "Used Python for 3 years"
            rf'(?:used|using|worked with|utilizing)\s+{re.escape(skill_lower)}\s+(?:for\s+)?(\d+(?:\.\d+)?)\s*(?:\+\s*)?(?:years?|yrs?)',
        ]
        
        max_years = 0
        for pattern in patterns:
            matches = re.findall(pattern, text_lower)
            if matches:
                try:
                    # Handle both string and tuple matches
                    for match in matches:
                        if isinstance(match, tuple):
                            years_str = match[0] if match[0] else match[1] if len(match) > 1 else '0'
                        else:
                            years_str = match
                        
                        years = float(years_str)
                        max_years = max(max_years, years)
                except (ValueError, IndexError):
                    continue
        
        if max_years > 0:
            return int(max_years * 12)  # Convert to months
        
        # If no specific experience found, estimate from job timeline context
        return self.estimate_skill_experience_from_context(skill, text)

    def estimate_skill_experience_from_context(self, skill, text):
        """Estimate skill experience from job context and timeline"""
        skill_lower = skill.lower()
        text_lower = text.lower()
        
        # Find all job periods in the resume
        job_periods = self.extract_all_job_periods(text)
        
        # Look for the skill in different job contexts
        skill_contexts = []
        
        # Find skill mentions and their surrounding context
        for match in re.finditer(re.escape(skill_lower), text_lower):
            start = max(0, match.start() - 1000)  # 1000 chars before
            end = min(len(text), match.end() + 1000)  # 1000 chars after
            context = text[start:end]
            
            # Look for date ranges in this context
            context_periods = self.extract_all_job_periods(context)
            if context_periods:
                skill_contexts.extend(context_periods)
        
        # Calculate total experience from contexts where skill was mentioned
        total_months = 0
        if skill_contexts:
            total_months = max([period['months'] for period in skill_contexts])
        
        # If we found context-based experience, use it (but cap it reasonably)
        if total_months > 0:
            return min(total_months, 120)  # Cap at 10 years
        
        # Fallback: estimate based on overall experience and skill category
        return self.estimate_by_skill_category_and_seniority(skill, text)

    def extract_all_job_periods(self, text):
        """Extract all job periods from text"""
        periods = []
        
        # Multiple date patterns
        date_patterns = [
            # Year ranges: 2020-2023, 2020 to 2023
            r'(\d{4})\s*(?:[-–]|to)\s*(\d{4}|present|current)',
            
            # Month Year ranges: Jan 2020 - Dec 2023
            r'(\w{3,9}\s+\d{4})\s*(?:[-–]|to)\s*(\w{3,9}\s+\d{4}|present|current)',
            
            # MM/YYYY ranges: 01/2020 - 12/2023
            r'(\d{1,2}/\d{4})\s*(?:[-–]|to)\s*(\d{1,2}/\d{4}|present|current)',
            
            # MM-YYYY ranges: 01-2020 to 12-2023
            r'(\d{1,2}-\d{4})\s*(?:[-–]|to)\s*(\d{1,2}-\d{4}|present|current)',
        ]
        
        for pattern in date_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for start_date, end_date in matches:
                months = self.calculate_months_between_dates(start_date, end_date)
                if months > 0:  # Only include valid periods
                    periods.append({
                        'start': start_date,
                        'end': end_date,
                        'months': months
                    })
        
        return periods

    def calculate_months_between_dates(self, start_date, end_date):
        """Calculate months between two date strings"""
        try:
            # Handle "present" or "current"
            if end_date.lower() in ['present', 'current']:
                end_date = str(datetime.now().year)
            
            # Parse start date
            start = self.parse_flexible_date(start_date)
            
            # Parse end date
            if end_date.lower() in ['present', 'current']:
                end = datetime.now()
            else:
                end = self.parse_flexible_date(end_date)
            
            # Calculate months
            months = (end.year - start.year) * 12 + (end.month - start.month)
            return max(0, months)
        
        except:
            return 0  # Return 0 if parsing fails

    def parse_flexible_date(self, date_str):
        """Parse various date formats"""
        date_str = date_str.strip()
        
        # Year only (e.g., "2020")
        if re.match(r'^\d{4}$', date_str):
            return datetime(int(date_str), 1, 1)
        
        # Month year format (e.g., "January 2020", "Jan 2020")
        month_year_pattern = r'(\w{3,9})\s+(\d{4})'
        match = re.match(month_year_pattern, date_str, re.IGNORECASE)
        if match:
            month_name, year = match.groups()
            month_map = {
                'jan': 1, 'january': 1, 'feb': 2, 'february': 2, 'mar': 3, 'march': 3,
                'apr': 4, 'april': 4, 'may': 5, 'jun': 6, 'june': 6,
                'jul': 7, 'july': 7, 'aug': 8, 'august': 8, 'sep': 9, 'september': 9,
                'oct': 10, 'october': 10, 'nov': 11, 'november': 11, 'dec': 12, 'december': 12
            }
            month_num = month_map.get(month_name.lower()[:3], 1)
            return datetime(int(year), month_num, 1)
        
        # MM/YYYY format
        if '/' in date_str:
            parts = date_str.split('/')
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                month, year = int(parts[0]), int(parts[1])
                return datetime(year, month, 1)
        
        # MM-YYYY format
        if '-' in date_str and len(date_str.split('-')) == 2:
            parts = date_str.split('-')
            if parts[0].isdigit() and parts[1].isdigit():
                month, year = int(parts[0]), int(parts[1])
                return datetime(year, month, 1)
        
        # Default fallback
        return datetime.now()

    def estimate_by_skill_category_and_seniority(self, skill, text):
        """Estimate experience based on skill category and detected seniority level"""
        skill_lower = skill.lower()
        text_lower = text.lower()
        
        # Detect seniority level from resume
        senior_indicators = ['senior', 'lead', 'principal', 'architect', 'manager', 'director', 'head of', 'chief', 'vp', 'vice president']
        mid_indicators = ['mid-level', 'intermediate', 'analyst', 'developer', 'engineer']
        junior_indicators = ['junior', 'entry', 'intern', 'trainee', 'associate', 'assistant', 'graduate']
        
        is_senior = any(indicator in text_lower for indicator in senior_indicators)
        is_junior = any(indicator in text_lower for indicator in junior_indicators)
        is_mid = any(indicator in text_lower for indicator in mid_indicators)
        
        # Extract overall experience if mentioned
        overall_exp_patterns = [
            r'(\d+)\+?\s*years?\s*of\s*(?:total\s*)?(?:professional\s*)?experience',
            r'(\d+)\+?\s*years?\s*(?:professional\s*)?experience',
            r'experience\s*:?\s*(\d+)\+?\s*years?'
        ]
        
        overall_years = 0
        for pattern in overall_exp_patterns:
            matches = re.findall(pattern, text_lower)
            if matches:
                overall_years = max([int(match) for match in matches])
                break
        
        # Categorize skills for different default experiences
        programming_languages = ['python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'c', 'go', 'rust', 'kotlin', 'swift', 'php', 'ruby', 'scala', 'r']
        databases = ['sql', 'mysql', 'postgresql', 'oracle', 'mongodb', 'sqlite', 'redis', 'cassandra']
        cloud_platforms = ['aws', 'azure', 'gcp', 'google cloud']
        tools_frameworks = ['excel', 'tableau', 'power bi', 'jira', 'confluence', 'git', 'docker', 'kubernetes']
        
        # Determine base experience based on skill category and seniority
        if skill_lower in programming_languages:
            if is_senior or overall_years >= 8:
                base_months = 72  # 6 years
            elif is_junior or overall_years <= 2:
                base_months = 18  # 1.5 years
            else:
                base_months = 42  # 3.5 years
                
        elif skill_lower in databases:
            if is_senior or overall_years >= 8:
                base_months = 60  # 5 years
            elif is_junior or overall_years <= 2:
                base_months = 12  # 1 year
            else:
                base_months = 36  # 3 years
                
        elif skill_lower in cloud_platforms:
            if is_senior or overall_years >= 8:
                base_months = 48  # 4 years
            elif is_junior or overall_years <= 2:
                base_months = 6   # 6 months
            else:
                base_months = 24  # 2 years
                
        elif skill_lower in tools_frameworks:
            if is_senior or overall_years >= 8:
                base_months = 36  # 3 years
            elif is_junior or overall_years <= 2:
                base_months = 6   # 6 months
            else:
                base_months = 18  # 1.5 years
        else:
            # General skills
            if is_senior or overall_years >= 8:
                base_months = 48  # 4 years
            elif is_junior or overall_years <= 2:
                base_months = 12  # 1 year
            else:
                base_months = 30  # 2.5 years
        
        # If we have overall experience, cap skill experience appropriately
        if overall_years > 0:
            max_skill_months = int(overall_years * 12 * 0.8)  # Skills typically 80% of total experience
            base_months = min(base_months, max_skill_months)
        
        return base_months

    def extract_personal_info(self, text):
        """Enhanced personal information extraction"""
        # Extract email
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, text)
        if emails:
            self.parsed_data["ResumeParserData"]["Email"] = emails[0]

        # Extract phone with enhanced patterns
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

        # Extract LinkedIn URL
        linkedin_pattern = r'(?:https?://)?(?:www\.)?linkedin\.com/in/[\w\-]+'
        linkedin_urls = re.findall(linkedin_pattern, text, re.IGNORECASE)
        if linkedin_urls:
            self.parsed_data["ResumeParserData"]["LinkedInProfileUrl"] = linkedin_urls[0]

        # Enhanced name extraction
        self.extract_name_enhanced(text)
        
        # Extract address information
        self.extract_address(text)

    def extract_address(self, text):
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

        # City extraction
        city_pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*[A-Z]{2}'
        cities = re.findall(city_pattern, text)
        if cities:
            self.parsed_data["ResumeParserData"]["City"] = cities[0]

    def extract_skills(self, text):
        """Enhanced skills extraction with better experience estimation"""
        # Comprehensive skill keywords
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
        
        # Check for skills with word boundaries
        for skill in skill_keywords:
            pattern = r'\b' + re.escape(skill.upper()) + r'\b'
            if re.search(pattern, text_upper):
                # Use enhanced experience estimation
                experience_months = self.extract_skill_specific_experience(skill, text)
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
            
            if years_exp >= 10:
                self.parsed_data["ResumeParserData"]["Experience"] = f"Results-driven professional with {years_exp}+ years of extensive experience"
            elif years_exp >= 5:
                self.parsed_data["ResumeParserData"]["Experience"] = f"Experienced professional with {years_exp} years of solid experience"
            else:
                self.parsed_data["ResumeParserData"]["Experience"] = f"Professional with {years_exp} years of experience"

        # Extract work history
        work_history = self.extract_work_history(text)
        self.parsed_data["ResumeParserData"]["SegrigatedExperience"]["WorkHistory"] = work_history
        
        if work_history:
            self.parsed_data["ResumeParserData"]["CurrentEmployer"] = work_history[0].get("Employer", "")
            self.parsed_data["ResumeParserData"]["JobProfile"] = work_history[0].get("JobProfile", "")

    def extract_work_history(self, text):
        """Extract detailed work history"""
        work_history = []
        
        # Company patterns
        company_patterns = [
            r'(?:Client|Company|Employer):\s*([A-Z][A-Za-z\s&.,-]+)',
            r'([A-Z][A-Za-z\s&.,-]+(?:Inc|LLC|Corp|Company|Ltd|Limited|Group|Technologies|Systems|Solutions|Consulting|Services))',
            r'at\s+([A-Z][A-Za-z\s&.,-]+)',
            r'([A-Z][A-Za-z\s&.,-]+)\s*[-,]\s*([A-Z][a-z]+,?\s*[A-Z]{2})'
        ]
        
        companies = []
        for pattern in company_patterns:
            matches = re.findall(pattern, text)
            if matches and isinstance(matches[0], tuple):
                companies.extend([match[0].strip() for match in matches if len(match[0].strip()) > 2])
            elif matches:
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
        
        # Extract job periods using the enhanced method
        job_periods = self.extract_all_job_periods(text)
        
        # Remove duplicates
        unique_companies = []
        seen = set()
        for company in companies:
            if company not in seen and len(company) > 3:
                seen.add(company)
                unique_companies.append(company)
        
        # Create work history entries
        for i, company in enumerate(unique_companies[:5]):
            period_info = job_periods[i] if i < len(job_periods) else {}
            
            work_entry = {
                "Employer": company,
                "JobProfile": job_titles[i] if i < len(job_titles) else "Not specified",
                "JobLocation": "Not specified",
                "JobPeriod": f"{period_info.get('start', 'Not specified')} to {period_info.get('end', 'Not specified')}",
                "StartDate": self.convert_date_format(period_info.get('start', 'Not specified')),
                "EndDate": self.convert_date_format(period_info.get('end', 'Not specified')),
                "JobDescription": "Not specified"
            }
            work_history.append(work_entry)
        
        return work_history

    def convert_date_format(self, date_str):
        """Convert date string to standard format"""
        if not date_str or date_str == 'Not specified' or date_str.lower() in ['present', 'current']:
            return datetime.now().strftime("%d/%m/%Y")
        
        try:
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 2:
                    month, year = parts
                    return f"1/{month}/{year}"
            elif len(date_str) == 5 and date_str[3:].isdigit():
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
        
        university_patterns = [
            r'([A-Z][A-Za-z\s]+(?:University|College|Institute|School))',
            r'(?:University|College|Institute|School)\s+of\s+([A-Za-z\s]+)',
        ]
        
        universities = []
        for pattern in university_patterns:
            matches = re.findall(pattern, text)
            if matches:
                if isinstance(matches[0], tuple):
                    universities.extend([match[0].strip() for match in matches if len(match[0].strip()) > 3])
                else:
                    universities.extend([match.strip() for match in matches if len(match.strip()) > 3])
        
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
        
        category_scores = {}
        for category, keywords in categories.items():
            score = sum(text_lower.count(keyword) for keyword in keywords)
            category_scores[category] = score
        
        if category_scores:
            best_category = max(category_scores, key=category_scores.get)
            if category_scores[best_category] > 0:
                self.parsed_data["ResumeParserData"]["Category"] = best_category
                
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
        # Set basic info
        self.parsed_data["ResumeParserData"]["ResumeFileName"] = filename
        self.parsed_data["ResumeParserData"]["ParsingDate"] = datetime.now().strftime("%m/%d/%Y %I:%M:%S %p")
        self.parsed_data["ResumeParserData"]["DetailResume"] = file_content
        
        # Extract all information with enhanced methods
        self.extract_personal_info(file_content)
        self.extract_skills(file_content)
        self.extract_experience(file_content)
        self.extract_education(file_content)
        self.categorize_resume(file_content)
        
        return self.parsed_data

# Replace the main function to use the enhanced parser
def main():
    import streamlit as st
    import pandas as pd
    
    # Page configuration
    st.set_page_config(
        page_title="TrackTalents Resume Parser - Enhanced",
        page_icon="🎯",
        layout="wide"
    )
    
    # Apply custom CSS (keeping the original CSS function)
    # apply_custom_css()  # You'll need to copy this from the original
    
    st.markdown("# 🎯 TrackTalents - Enhanced Resume Parser")
    st.markdown("**New Features:** Better name detection & accurate skills experience estimation")
    
    # File upload
    uploaded_file = st.file_uploader(
        "Choose a resume file",
        type=['pdf', 'docx', 'txt'],
        help="Supported formats: PDF, DOCX, TXT"
    )
    
    if uploaded_file is not None:
        st.success(f"✅ File uploaded: **{uploaded_file.name}**")
        
        if st.button("🚀 Parse with Enhanced AI", type="primary"):
            with st.spinner("Processing with enhanced algorithms..."):
                # Use the enhanced parser
                parser = EnhancedResumeParser()
                
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
                    
                    # Parse with enhanced methods
                    parsed_data = parser.parse_resume(text_content, uploaded_file.name)
                    
                    st.success("✅ Resume parsed successfully!")
                    
                    # Display results
                    data = parsed_data["ResumeParserData"]
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.subheader("👤 Name Detection")
                        full_name = f"{data['FirstName']} {data['Middlename']} {data['LastName']}".strip()
                        if full_name.strip():
                            st.success(f"**Name:** {full_name}")
                        else:
                            st.warning("Name not detected")
                        
                        st.write(f"**Email:** {data['Email']}")
                        st.write(f"**Phone:** {data['Phone']}")
                    
                    with col2:
                        st.subheader("🛠️ Skills Analysis")
                        skills = data['SkillsKeywords']['OperationalSkills']['SkillSet']
                        st.write(f"**Skills Found:** {len(skills)}")
                        
                        if skills:
                            for skill in skills[:5]:
                                months = int(skill['ExperienceInMonths'])
                                years = months // 12
                                remaining_months = months % 12
                                
                                if years > 0:
                                    exp_str = f"{years}y {remaining_months}m" if remaining_months > 0 else f"{years}y"
                                else:
                                    exp_str = f"{remaining_months}m"
                                
                                st.write(f"• **{skill['Skill']}:** {exp_str}")
                    
                    # Skills table
                    if skills:
                        st.subheader("📊 Complete Skills Breakdown")
                        skills_df = pd.DataFrame(skills)
                        skills_df['Years'] = (skills_df['ExperienceInMonths'].astype(int) / 12).round(1)
                        display_df = skills_df[['Skill', 'Years']].sort_values('Years', ascending=False)
                        st.dataframe(display_df, use_container_width=True)
                    
                    # Download
                    json_string = json.dumps(parsed_data, indent=2)
                    st.download_button(
                        label="📥 Download Enhanced JSON",
                        data=json_string,
                        file_name=f"enhanced_{uploaded_file.name}.json",
                        mime="application/json"
                    )
                
                except Exception as e:
                    st.error(f"Error: {str(e)}")

if __name__ == "__main__":
    main()
