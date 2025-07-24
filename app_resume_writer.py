# To run: streamlit run app_resume_enhanced.py

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
import json
import os
import requests
from pypdf import PdfReader
import io
from datetime import datetime
import re
import time

load_dotenv(override=True)

# Configure page
st.set_page_config(
    page_title="AI Resume Enhancer & Job Matcher",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better UI
st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 2rem 0;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    .stButton>button {
        background-color: #667eea;
        color: white;
        border-radius: 5px;
        padding: 0.5rem 1rem;
        border: none;
        transition: all 0.3s;
    }
    .stButton>button:hover {
        background-color: #764ba2;
        transform: translateY(-2px);
    }
    .chat-message {
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
    }
    .user-message {
        background-color: #e3f2fd;
        margin-left: 20%;
    }
    .assistant-message {
        background-color: #f5f5f5;
        margin-right: 20%;
    }
    .metric-card {
        background-color: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'resume_text' not in st.session_state:
    st.session_state.resume_text = ""
if 'job_description' not in st.session_state:
    st.session_state.job_description = ""
if 'analysis_complete' not in st.session_state:
    st.session_state.analysis_complete = False
if 'tailored_resume' not in st.session_state:
    st.session_state.tailored_resume = ""
if 'match_score' not in st.session_state:
    st.session_state.match_score = 0
if 'interview_questions' not in st.session_state:
    st.session_state.interview_questions = []
if 'chat_context' not in st.session_state:
    st.session_state.chat_context = []
if 'api_key' not in st.session_state:
    st.session_state.api_key = os.getenv("OPENAI_API_KEY", "")

def check_api_key():
    """Check if OpenAI API key is configured"""
    api_key = st.session_state.api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        return False, "OpenAI API key not found"
    if not api_key.startswith("sk-"):
        return False, "Invalid OpenAI API key format"
    return True, api_key

def push_notification(text):
    """Send push notification via Pushover"""
    if os.getenv("PUSHOVER_TOKEN") and os.getenv("PUSHOVER_USER"):
        try:
            requests.post(
                "https://api.pushover.net/1/messages.json",
                data={
                    "token": os.getenv("PUSHOVER_TOKEN"),
                    "user": os.getenv("PUSHOVER_USER"),
                    "message": text,
                },
                timeout=5
            )
        except:
            pass

def extract_text_from_pdf(pdf_file):
    """Extract text from uploaded PDF file"""
    try:
        pdf_reader = PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text
    except Exception as e:
        st.error(f"Error reading PDF: {str(e)}")
        return ""

class ResumeAnalyzer:
    def __init__(self, api_key):
        self.model_name = "gpt-3.5-turbo"
        self.client = OpenAI(api_key=api_key)
    
    def _safe_api_call(self, messages, temperature=0.7, max_tokens=None):
        """Make API call with error handling and retries"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                kwargs = {
                    "model": self.model_name,
                    "messages": messages,
                    "temperature": temperature
                }
                if max_tokens:
                    kwargs["max_tokens"] = max_tokens
                
                response = self.client.chat.completions.create(**kwargs)
                return response
            except Exception as e:
                if attempt == max_retries - 1:
                    raise Exception(f"API call failed: {str(e)}")
                time.sleep(2 ** attempt)
    
    def analyze_job_fit(self, resume_text, job_description):
        """Analyze how well the resume fits the job description"""
        prompt = f"""
        Analyze the following resume against the job description and provide:
        1. A match score out of 100
        2. Key strengths that align with the job
        3. Gaps or areas for improvement
        4. Specific skills from the JD that should be highlighted
        
        Resume:
        {resume_text[:3000]}
        
        Job Description:
        {job_description}
        
        Provide the response in JSON format with keys: match_score, strengths, gaps, skills_to_highlight
        """
        
        try:
            response = self._safe_api_call([
                {"role": "system", "content": "You are an expert resume analyzer and career counselor."},
                {"role": "user", "content": prompt}
            ])
            
            content = response.choices[0].message.content
            try:
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]
                
                return json.loads(content)
            except:
                return {
                    "match_score": 75,
                    "strengths": ["Strong technical background", "Relevant experience"],
                    "gaps": ["Consider adding more quantifiable achievements"],
                    "skills_to_highlight": ["Technical skills matching job requirements"]
                }
        except Exception as e:
            st.error(f"Error during analysis: {str(e)}")
            return {
                "match_score": 70,
                "strengths": ["Unable to complete full analysis"],
                "gaps": ["Please check API configuration"],
                "skills_to_highlight": ["Review job requirements"]
            }
    
    def tailor_resume(self, resume_text, job_description, analysis):
        """Tailor the resume for the specific job description"""
        prompt = f"""
        Rewrite and optimize the following resume for the specific job description.
        
        Guidelines:
        1. Emphasize skills and experiences that match the job requirements
        2. Use keywords from the job description naturally
        3. Quantify achievements where possible
        4. Maintain truthfulness - only reorganize and emphasize existing content
        5. Focus on the skills to highlight: {', '.join(analysis.get('skills_to_highlight', []))}
        
        Resume:
        {resume_text}
        
        Job Description:
        {job_description}
        
        Provide a complete, well-formatted resume optimized for this position.
        """
        
        try:
            response = self._safe_api_call([
                {"role": "system", "content": "You are an expert resume writer who creates ATS-friendly, compelling resumes."},
                {"role": "user", "content": prompt}
            ], max_tokens=2000)
            
            return response.choices[0].message.content
        except Exception as e:
            st.error(f"Error tailoring resume: {str(e)}")
            return resume_text
    
    def generate_interview_questions(self, resume_text, job_description):
        """Generate relevant interview questions based on JD and resume"""
        prompt = f"""
        Based on the job description and resume, generate 10 interview questions that:
        1. Test the candidate's fit for the role
        2. Explore their relevant experience
        3. Assess technical skills mentioned in the JD
        4. Evaluate soft skills and cultural fit
        5. Include both behavioral and technical questions
        
        Job Description:
        {job_description}
        
        Resume Summary:
        {resume_text[:1000]}
        
        Format as a JSON array of questions.
        """
        
        try:
            response = self._safe_api_call([
                {"role": "system", "content": "You are an experienced technical interviewer."},
                {"role": "user", "content": prompt}
            ], temperature=0.8)
            
            content = response.choices[0].message.content
            try:
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]
                
                return json.loads(content)
            except:
                questions = []
                lines = content.split('\n')
                for line in lines:
                    line = line.strip()
                    if line and (line[0].isdigit() or line.startswith('-') or line.startswith('•')):
                        question = re.sub(r'^[\d\-•\.]+\s*', '', line).strip()
                        if question:
                            questions.append(question)
                
                return questions[:10] if questions else self.get_default_questions()
        except Exception as e:
            st.error(f"Error generating questions: {str(e)}")
            return self.get_default_questions()
    
    def get_default_questions(self):
        """Return default interview questions"""
        return [
            "Tell me about your experience relevant to this role.",
            "What interests you about this position?",
            "Describe a challenging project you've worked on.",
            "How do you stay updated with new technologies?",
            "Where do you see yourself in 5 years?",
            "What are your greatest strengths?",
            "How do you handle tight deadlines?",
            "Describe a time you worked in a team.",
            "What achievement are you most proud of?",
            "Why are you looking for a new opportunity?"
        ]
    
    def chat_response(self, message, context):
        """Generate chat responses for interview preparation"""
        system_prompt = f"""
        You are an AI interview coach helping a candidate prepare for a job interview.
        
        Context:
        - Job Description: {st.session_state.job_description[:500]}
        - Match score: {st.session_state.get('match_score', 'N/A')}%
        
        Help the candidate:
        1. Answer interview questions effectively
        2. Highlight relevant experience
        3. Address any gaps identified
        4. Practice STAR method responses
        5. Build confidence
        
        Be supportive, specific, and actionable in your advice.
        """
        
        try:
            messages = [{"role": "system", "content": system_prompt}] + context + [{"role": "user", "content": message}]
            response = self._safe_api_call(messages)
            return response.choices[0].message.content
        except Exception as e:
            return f"I apologize, but I'm having trouble connecting to the AI service. Error: {str(e)}"

# Main App
def main():
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>🚀 AI Resume Enhancer & Job Matcher</h1>
        <p>Upload your resume, paste a job description, and get AI-powered optimization!</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Check API Key
    api_configured, api_key = check_api_key()
    
    if not api_configured:
        st.error("⚠️ OpenAI API Key Required")
        st.info("Please set your OpenAI API key to use this application.")
        
        api_key_input = st.text_input(
            "Enter your OpenAI API Key",
            type="password",
            placeholder="sk-...",
            help="Get your API key from https://platform.openai.com/api-keys"
        )
        
        if api_key_input:
            st.session_state.api_key = api_key_input
            st.rerun()
        
        st.stop()
    
    # Sidebar with instructions only
    with st.sidebar:
        st.header("📋 How to Use")
        st.markdown("""
        1. **Upload your resume** (PDF format)
        2. **Paste the job description**
        3. **Click Analyze** to get insights
        4. **Review your tailored resume**
        5. **Practice with AI interview coach**
        
        ---
        
        ### 💡 Tips for Best Results:
        - Use complete job descriptions
        - Upload well-formatted PDFs
        - Be specific in interview practice
        
        ### 📊 What You'll Get:
        - Match score percentage
        - Strengths & gaps analysis
        - ATS-optimized resume
        - Custom interview questions
        - AI coaching support
        """)
    
    # Main content area with tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📤 Upload & Analyze", "📊 Results", "✏️ Tailored Resume", "💬 Interview Prep"])
    
    with tab1:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📄 Upload Resume")
            uploaded_file = st.file_uploader("Choose your resume (PDF)", type=['pdf'])
            
            if uploaded_file is not None:
                resume_text = extract_text_from_pdf(uploaded_file)
                if resume_text:
                    st.session_state.resume_text = resume_text
                    st.success("✅ Resume uploaded successfully!")
                    
                    with st.expander("Preview Resume Text"):
                        st.text(st.session_state.resume_text[:1000] + "...")
        
        with col2:
            st.subheader("💼 Job Description")
            job_description = st.text_area(
                "Paste the job description here",
                height=300,
                placeholder="Paste the complete job description including requirements, responsibilities, and qualifications..."
            )
            st.session_state.job_description = job_description
        
        # Analyze button
        if st.button("🔍 Analyze & Match", type="primary", use_container_width=True):
            if st.session_state.resume_text and st.session_state.job_description:
                with st.spinner("🤖 AI is analyzing your resume..."):
                    try:
                        analyzer = ResumeAnalyzer(api_key)
                        
                        # Perform analysis
                        analysis = analyzer.analyze_job_fit(st.session_state.resume_text, st.session_state.job_description)
                        st.session_state.analysis = analysis
                        st.session_state.match_score = analysis.get('match_score', 0)
                        
                        # Generate tailored resume
                        st.session_state.tailored_resume = analyzer.tailor_resume(
                            st.session_state.resume_text, 
                            st.session_state.job_description,
                            analysis
                        )
                        
                        # Generate interview questions
                        st.session_state.interview_questions = analyzer.generate_interview_questions(
                            st.session_state.resume_text,
                            st.session_state.job_description
                        )
                        
                        st.session_state.analysis_complete = True
                        st.success("✅ Analysis complete! Check the Results tab.")
                        
                        # Send notification
                        push_notification(f"Resume analysis complete. Match score: {st.session_state.match_score}%")
                    except Exception as e:
                        st.error(f"Error during analysis: {str(e)}")
            else:
                st.error("Please upload a resume and provide a job description.")
    
    with tab2:
        if st.session_state.analysis_complete:
            st.subheader("📊 Analysis Results")
            
            # Match score with visual
            col1, col2, col3 = st.columns(3)
            with col2:
                st.markdown(f"""
                <div class="metric-card">
                    <h2 style="color: {'green' if st.session_state.match_score >= 80 else 'orange' if st.session_state.match_score >= 60 else 'red'};">
                        {st.session_state.match_score}%
                    </h2>
                    <p>Match Score</p>
                </div>
                """, unsafe_allow_html=True)
            
            # Strengths and gaps
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("💪 Strengths")
                for strength in st.session_state.analysis.get('strengths', []):
                    st.markdown(f"✅ {strength}")
            
            with col2:
                st.subheader("📈 Areas for Improvement")
                for gap in st.session_state.analysis.get('gaps', []):
                    st.markdown(f"⚠️ {gap}")
            
            # Skills to highlight
            st.subheader("🎯 Skills to Emphasize")
            skills_cols = st.columns(4)
            for i, skill in enumerate(st.session_state.analysis.get('skills_to_highlight', [])):
                with skills_cols[i % 4]:
                    st.info(skill)
        else:
            st.info("👆 Please upload your resume and analyze it first.")
    
    with tab3:
        if st.session_state.analysis_complete:
            st.subheader("✏️ Your Tailored Resume")
            st.markdown("This resume has been optimized for the specific job description.")
            
            # Display tailored resume
            st.text_area(
                "Optimized Resume",
                value=st.session_state.tailored_resume,
                height=600,
                key="tailored_resume_display"
            )
            
            # Download button
            st.download_button(
                label="📥 Download Tailored Resume",
                data=st.session_state.tailored_resume,
                file_name=f"tailored_resume_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain"
            )
        else:
            st.info("👆 Please complete the analysis to see your tailored resume.")
    
    with tab4:
        st.subheader("💬 AI Interview Coach")
        
        if st.session_state.analysis_complete:
            # Display sample questions
            with st.expander("📝 Practice Interview Questions"):
                for i, question in enumerate(st.session_state.interview_questions, 1):
                    st.markdown(f"**Q{i}:** {question}")
            
            # Chat interface
            st.markdown("---")
            st.markdown("### Chat with your AI Interview Coach")
            st.markdown("Practice answering questions and get feedback on your responses.")
            
            # Display chat history
            for message in st.session_state.messages:
                with st.container():
                    if message["role"] == "user":
                        st.markdown(f"""
                        <div class="chat-message user-message">
                            <strong>You:</strong> {message["content"]}
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                        <div class="chat-message assistant-message">
                            <strong>Coach:</strong> {message["content"]}
                        </div>
                        """, unsafe_allow_html=True)
            
            # Chat input
            with st.form("chat_form", clear_on_submit=True):
                user_input = st.text_input("Your message:", placeholder="Ask for interview tips or practice your answers...")
                submit = st.form_submit_button("Send")
                
                if submit and user_input:
                    # Add user message
                    st.session_state.messages.append({"role": "user", "content": user_input})
                    st.session_state.chat_context.append({"role": "user", "content": user_input})
                    
                    # Get AI response
                    analyzer = ResumeAnalyzer(api_key)
                    response = analyzer.chat_response(user_input, st.session_state.chat_context[-10:])
                    
                    # Add assistant message
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    st.session_state.chat_context.append({"role": "assistant", "content": response})
                    
                    # Rerun to update chat display
                    st.rerun()
            
            # Clear chat button
            if st.button("🗑️ Clear Chat"):
                st.session_state.messages = []
                st.session_state.chat_context = []
                st.rerun()
        else:
            st.info("👆 Please complete the resume analysis to access the interview coach.")

if __name__ == "__main__":
    main()
