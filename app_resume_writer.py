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
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

load_dotenv(override=True)

# Configure page
st.set_page_config(
    page_title="AI Career Optimization Platform",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Professional CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    * {
        font-family: 'Inter', sans-serif;
    }
    
    .main-header {
        background: linear-gradient(135deg, #1e3a8a 0%, #3730a3 100%);
        padding: 2.5rem 2rem;
        border-radius: 0;
        margin: -1rem -1rem 2rem -1rem;
        text-align: left;
    }
    
    .main-header h1 {
        color: white;
        font-size: 2.25rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        letter-spacing: -0.02em;
    }
    
    .main-header p {
        color: #e0e7ff;
        font-size: 1.125rem;
        font-weight: 400;
        margin: 0;
    }
    
    .agent-status {
        background: #f0f9ff;
        border: 1px solid #0284c7;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
    }
    
    .agent-thinking {
        background: #fef3c7;
        border: 1px solid #f59e0b;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.8; }
        100% { opacity: 1; }
    }
    
    .iteration-card {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 1.5rem;
        margin: 1rem 0;
        position: relative;
    }
    
    .iteration-number {
        position: absolute;
        top: -12px;
        left: 20px;
        background: #3730a3;
        color: white;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 0.875rem;
        font-weight: 600;
    }
    
    .feedback-item {
        background: #f0f9ff;
        border-left: 3px solid #0284c7;
        padding: 0.75rem;
        margin: 0.5rem 0;
        border-radius: 4px;
    }
    
    .quality-score {
        display: inline-block;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 0.875rem;
        font-weight: 600;
        margin-left: 0.5rem;
    }
    
    .score-high { background: #dcfce7; color: #14532d; }
    .score-medium { background: #fef3c7; color: #78350f; }
    .score-low { background: #fee2e2; color: #7f1d1d; }
    
    .agent-message {
        background: #e0e7ff;
        border: 1px solid #6366f1;
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
    }
    
    .user-response {
        background: #f3f4f6;
        border: 1px solid #d1d5db;
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
    }
    
    .improvement-suggestion {
        background: #ecfdf5;
        border: 1px solid #10b981;
        padding: 0.75rem;
        border-radius: 6px;
        margin: 0.5rem 0;
    }
    
    .stButton > button {
        background: #3730a3;
        color: white;
        border: none;
        padding: 0.625rem 1.25rem;
        font-weight: 500;
        transition: all 0.2s ease;
    }
    
    .stButton > button:hover {
        background: #4c1d95;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(55, 48, 163, 0.3);
    }
    
    .metric-container {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 1.5rem;
        text-align: center;
        transition: all 0.3s ease;
    }
    
    .section-header {
        color: #1e293b;
        font-size: 1.5rem;
        font-weight: 600;
        margin-bottom: 1.5rem;
        padding-bottom: 0.75rem;
        border-bottom: 2px solid #e2e8f0;
    }
    
    .download-section {
        background: #f0f9ff;
        border: 2px solid #0284c7;
        border-radius: 8px;
        padding: 2rem;
        margin: 1rem 0;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# Enums and Data Classes
class AgentState(Enum):
    IDLE = "idle"
    ANALYZING = "analyzing"
    REFINING = "refining"
    AWAITING_FEEDBACK = "awaiting_feedback"
    COMPLETE = "complete"

@dataclass
class ResumeIteration:
    version: int
    content: str
    quality_score: float
    improvements: List[str]
    feedback_incorporated: List[str]
    timestamp: datetime

@dataclass
class InterviewExchange:
    question: str
    user_response: str
    agent_feedback: str
    follow_up_questions: List[str]
    improvements: List[str]
    score: float

# Initialize session state
def init_session_state():
    defaults = {
        'messages': [],
        'resume_text': "",
        'job_description': "",
        'analysis_complete': False,
        'tailored_resume': "",
        'match_score': 0,
        'interview_questions': [],
        'chat_context': [],
        'api_key': os.getenv("OPENAI_API_KEY", ""),
        'resume_iterations': [],
        'current_agent_state': AgentState.IDLE,
        'interview_exchanges': [],
        'agent_memory': {},
        'user_preferences': {},
        'current_iteration': 0,
        'max_iterations': 3,
        'quality_threshold': 0.85,
        'interview_stage': "initial",
        'user_profile': {},
        'agent_feedback': {},
        'final_resume': "",
        'manual_mode': False
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

def check_api_key():
    """Check if OpenAI API key is configured"""
    api_key = st.session_state.api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        return False, "OpenAI API key not found"
    if not api_key.startswith("sk-"):
        return False, "Invalid OpenAI API key format"
    return True, api_key

def extract_text_from_pdf(pdf_file):
    """Extract text from uploaded PDF file"""
    try:
        pdf_reader = PdfReader(pdf_file)
        text = ""
        
        if len(pdf_reader.pages) == 0:
            st.error("The PDF file appears to be empty.")
            return ""
        
        for i, page in enumerate(pdf_reader.pages):
            try:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            except Exception as e:
                st.warning(f"Could not read page {i+1}: {str(e)}")
                continue
        
        if not text.strip():
            st.error("Could not extract any text from the PDF. The file might be scanned or image-based.")
            return ""
        
        return text
    except Exception as e:
        st.error(f"Error reading PDF: {str(e)}")
        return ""

class ResumeWriterAgent:
    """Agent that iteratively improves resumes until they meet quality standards"""
    
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-3.5-turbo"
        self.state = AgentState.IDLE
        
    def _safe_api_call(self, messages, temperature=0.7, max_tokens=None):
        """Make API call with error handling"""
        try:
            kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature
            }
            if max_tokens:
                kwargs["max_tokens"] = max_tokens
            
            response = self.client.chat.completions.create(**kwargs)
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"API call failed: {str(e)}")
    
    def analyze_resume_quality(self, resume: str, job_description: str) -> Tuple[float, List[str], Dict]:
        """Analyze resume quality and identify specific improvements needed"""
        self.state = AgentState.ANALYZING
        
        prompt = f"""
        As a resume quality analyzer, evaluate this resume against the job description.
        
        Return a JSON object with:
        {{
            "quality_score": <float between 0-1>,
            "strengths": [<list of specific strengths>],
            "critical_improvements": [<list of must-fix issues>],
            "suggested_improvements": [<list of nice-to-have improvements>],
            "missing_keywords": [<list of important keywords from JD not in resume>],
            "keyword_coverage": <float between 0-1>,
            "ats_score": <float between 0-1>,
            "overall_assessment": "<brief assessment>"
        }}
        
        Resume:
        {resume[:3000]}
        
        Job Description:
        {job_description[:2000]}
        
        Be extremely thorough and specific in your analysis.
        """
        
        try:
            response = self._safe_api_call([
                {"role": "system", "content": "You are an expert resume analyzer with deep knowledge of ATS systems and hiring practices."},
                {"role": "user", "content": prompt}
            ])
            
            # Parse response
            content = response.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            result = json.loads(content)
            
            quality_score = float(result.get('quality_score', 0.7))
            improvements = (result.get('critical_improvements', []) + 
                          result.get('suggested_improvements', []))
            
            return quality_score, improvements, result
            
        except Exception as e:
            return 0.7, ["Unable to complete full analysis"], {}
    
    def generate_clarifying_questions(self, resume: str, job_description: str, iteration: int) -> List[str]:
        """Generate questions to gather more information for improvement"""
        
        prompt = f"""
        As a resume optimization expert, you're on iteration {iteration} of improving this resume.
        Generate 3 specific questions to gather information that would help create a stronger resume.
        
        Focus on:
        1. Quantifiable achievements not mentioned
        2. Relevant skills or experiences that might be missing
        3. Specific projects or accomplishments related to the job
        
        Current Resume Summary:
        {resume[:1500]}
        
        Target Role Requirements:
        {job_description[:1000]}
        
        Return ONLY a JSON array of 3 specific, actionable questions.
        Example: ["What was the revenue impact of your sales initiative?", "How many team members did you manage?", "What technologies did you use for the data analysis project?"]
        """
        
        try:
            response = self._safe_api_call([
                {"role": "system", "content": "You are an expert career counselor who asks insightful questions."},
                {"role": "user", "content": prompt}
            ])
            
            content = response.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
                
            questions = json.loads(content)
            
            # Ensure we have valid questions
            if isinstance(questions, list) and all(isinstance(q, str) for q in questions):
                return questions[:3]  # Return max 3 questions
            else:
                raise ValueError("Invalid question format")
                
        except Exception:
            # Return default questions if parsing fails
            return [
                "Can you provide specific metrics or percentages for your key achievements?",
                "What technical skills from the job description have you used but not mentioned?",
                "Describe a project where you demonstrated the leadership skills required for this role."
            ]
    
    def refine_resume(self, resume: str, job_description: str, feedback: Dict[str, str], 
                     previous_iterations: List[ResumeIteration]) -> str:
        """Refine resume based on feedback and previous iterations"""
        self.state = AgentState.REFINING
        
        # Build context from previous iterations
        iteration_context = ""
        if previous_iterations:
            iteration_context = "Previous improvements made:\n"
            for iteration in previous_iterations[-2:]:  # Last 2 iterations
                iteration_context += f"- Version {iteration.version}: {', '.join(iteration.improvements[:2])}\n"
        
        prompt = f"""
        You are an expert resume writer performing iteration {len(previous_iterations) + 1} of resume optimization.
        
        {iteration_context}
        
        User feedback to incorporate:
        {json.dumps(feedback, indent=2)}
        
        Requirements:
        1. Incorporate ALL user feedback provided
        2. Maintain all factual information
        3. Add quantifiable metrics based on feedback
        4. Optimize keyword placement for ATS
        5. Ensure professional tone and clear structure
        6. Use strong action verbs
        
        Original Resume:
        {resume}
        
        Target Job Description:
        {job_description[:1500]}
        
        Create an optimized resume that incorporates the feedback. Return ONLY the complete resume text.
        """
        
        try:
            response = self._safe_api_call([
                {"role": "system", "content": "You are a professional resume writer who creates ATS-optimized resumes."},
                {"role": "user", "content": prompt}
            ], max_tokens=3000)
            
            return response.strip()
            
        except Exception as e:
            st.error(f"Refinement error: {str(e)}")
            return resume

class InterviewCoachAgent:
    """Agent that conducts interactive interview preparation"""
    
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-3.5-turbo"
        
    def _safe_api_call(self, messages, temperature=0.7):
        """Make API call with error handling"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"API call failed: {str(e)}")
    
    def analyze_response(self, question: str, response: str, job_context: str) -> Dict:
        """Analyze interview response and provide detailed feedback"""
        
        prompt = f"""
        As an expert interview coach, analyze this interview response.
        
        Question: {question}
        Candidate's Response: {response}
        Job Context: {job_context[:500]}
        
        Provide a JSON analysis with:
        {{
            "score": <float 0-1>,
            "strengths": [<2-3 specific strengths>],
            "weaknesses": [<2-3 areas for improvement>],
            "follow_up_questions": [<2 follow-up questions>],
            "specific_improvements": [<2-3 concrete improvements>]
        }}
        """
        
        try:
            response_text = self._safe_api_call([
                {"role": "system", "content": "You are an expert interview coach."},
                {"role": "user", "content": prompt}
            ])
            
            content = response_text.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
                
            return json.loads(content)
            
        except Exception:
            return {
                "score": 0.7,
                "strengths": ["Good attempt"],
                "weaknesses": ["Could be more specific"],
                "follow_up_questions": ["Can you provide a specific example?"],
                "specific_improvements": ["Add quantifiable results"]
            }
    
    def generate_contextual_question(self, user_profile: Dict, stage: str, job_description: str) -> Dict:
        """Generate contextual interview questions"""
        
        prompt = f"""
        Generate an interview question for stage: {stage}
        User Profile: {json.dumps(user_profile, indent=2)}
        Job Description excerpt: {job_description[:500]}
        
        Return JSON:
        {{
            "question": "<the question>",
            "question_type": "<behavioral|technical|situational>",
            "tips": [<2 tips for answering>]
        }}
        """
        
        try:
            response = self._safe_api_call([
                {"role": "system", "content": "You are an expert interviewer."},
                {"role": "user", "content": prompt}
            ])
            
            content = response.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
                
            return json.loads(content)
            
        except Exception:
            return {
                "question": "Tell me about a challenging project you've worked on.",
                "question_type": "behavioral",
                "tips": ["Use STAR method", "Include specific metrics"]
            }

def display_agent_status(agent_name: str, status: str, message: str):
    """Display agent status in UI"""
    if status == "thinking":
        st.markdown(f"""
        <div class="agent-thinking">
            <strong>🤖 {agent_name} Agent:</strong> {message}
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="agent-status">
            <strong>🤖 {agent_name} Agent:</strong> {message}
        </div>
        """, unsafe_allow_html=True)

def display_iteration_card(iteration: ResumeIteration):
    """Display resume iteration in a card format"""
    quality_class = "score-high" if iteration.quality_score >= 0.85 else "score-medium" if iteration.quality_score >= 0.7 else "score-low"
    
    st.markdown(f"""
    <div class="iteration-card">
        <span class="iteration-number">Version {iteration.version}</span>
        <div style="margin-top: 1rem;">
            <strong>Quality Score:</strong> 
            <span class="quality-score {quality_class}">{iteration.quality_score:.0%}</span>
        </div>
        <div style="margin-top: 0.5rem;">
            <strong>Improvements Made:</strong>
            <ul style="margin: 0.5rem 0;">
                {''.join([f"<li>{imp}</li>" for imp in iteration.improvements[:3]])}
            </ul>
        </div>
    </div>
    """, unsafe_allow_html=True)

# Main Application
def main():
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>AI Career Optimization Platform</h1>
        <p>Agent-powered resume refinement and interview coaching</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Check API Key
    api_configured, api_key = check_api_key()
    
    if not api_configured:
        st.error("⚠️ API Configuration Required")
        
        api_key_input = st.text_input(
            "OpenAI API Key",
            type="password",
            placeholder="sk-...",
            help="Your API key is stored securely for this session only"
        )
        
        if api_key_input:
            st.session_state.api_key = api_key_input
            st.rerun()
        
        st.stop()
    
    # Initialize agents
    resume_agent = ResumeWriterAgent(api_key)
    interview_agent = InterviewCoachAgent(api_key)
    
    # Sidebar
    with st.sidebar:
        st.markdown("### 🎯 Agent Configuration")
        
        # Mode selector
        mode = st.radio(
            "Select Mode",
            ["Agent Mode (Automated)", "Manual Mode (Simple)"],
            index=0 if not st.session_state.manual_mode else 1
        )
        st.session_state.manual_mode = (mode == "Manual Mode (Simple)")
        
        if not st.session_state.manual_mode:
            st.slider(
                "Quality Threshold",
                min_value=0.7,
                max_value=0.95,
                value=st.session_state.quality_threshold,
                step=0.05,
                key="quality_threshold_slider",
                help="Resume quality score target"
            )
            
            st.slider(
                "Max Iterations",
                min_value=1,
                max_value=5,
                value=st.session_state.max_iterations,
                key="max_iterations_slider",
                help="Maximum refinement iterations"
            )
        
        if st.session_state.current_agent_state != AgentState.IDLE:
            st.markdown("---")
            st.markdown("### 📊 Agent Status")
            st.markdown(f"**State:** {st.session_state.current_agent_state.value}")
            st.markdown(f"**Current Iteration:** {st.session_state.current_iteration}")
            
            if st.session_state.resume_iterations:
                latest = st.session_state.resume_iterations[-1]
                st.metric("Latest Quality Score", f"{latest.quality_score:.0%}")
    
    # Main tabs
    tabs = ["Resume Agent", "Interview Coach", "Download Resume", "History"]
    tab1, tab2, tab3, tab4 = st.tabs(tabs)
    
    with tab1:
        st.markdown("## 🤖 Resume Writer Agent")
        
        if st.session_state.manual_mode:
            st.info("Manual mode: Get a one-time optimized resume without iterative refinement.")
        else:
            st.info("Agent mode: The AI will iteratively refine your resume until it meets quality standards.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Upload Resume")
            uploaded_file = st.file_uploader("Select your resume (PDF)", type=['pdf'])
            
            if uploaded_file:
                resume_text = extract_text_from_pdf(uploaded_file)
                if resume_text:
                    st.session_state.resume_text = resume_text
                    st.success("✓ Resume loaded")
                    
                    with st.expander("View extracted text"):
                        st.text(resume_text[:1000] + "...")
        
        with col2:
            st.markdown("### Target Position")
            job_description = st.text_area(
                "Paste job description",
                height=250,
                placeholder="Include the complete job posting...",
                key="job_desc_input"
            )
            st.session_state.job_description = job_description
        
        if st.session_state.resume_text and st.session_state.job_description:
            st.markdown("---")
            
            # Manual mode - simple one-time optimization
            if st.session_state.manual_mode:
                if st.button("🚀 Optimize Resume", type="primary", use_container_width=True):
                    with st.spinner("Analyzing and optimizing your resume..."):
                        # Quick optimization without iterations
                        try:
                            quality_score, improvements, analysis = resume_agent.analyze_resume_quality(
                                st.session_state.resume_text,
                                st.session_state.job_description
                            )
                            
                            # Direct optimization
                            optimized_resume = resume_agent.refine_resume(
                                st.session_state.resume_text,
                                st.session_state.job_description,
                                {"initial_optimization": "Create ATS-optimized version"},
                                []
                            )
                            
                            st.session_state.tailored_resume = optimized_resume
                            st.session_state.final_resume = optimized_resume
                            st.session_state.analysis_complete = True
                            st.session_state.match_score = int(quality_score * 100)
                            
                            st.success("✅ Resume optimized successfully!")
                            
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Match Score", f"{st.session_state.match_score}%")
                            with col2:
                                st.metric("Keywords Added", len(analysis.get('missing_keywords', [])))
                            with col3:
                                st.metric("ATS Score", f"{int(analysis.get('ats_score', 0.8) * 100)}%")
                            
                            st.info("Navigate to the 'Download Resume' tab to get your optimized resume.")
                            
                        except Exception as e:
                            st.error(f"Error during optimization: {str(e)}")
            
            # Agent mode - iterative refinement
            else:
                if st.button("🚀 Start Resume Agent", type="primary", use_container_width=True):
                    st.session_state.current_agent_state = AgentState.ANALYZING
                    st.session_state.current_iteration = 0
                    st.session_state.resume_iterations = []
                    st.session_state.agent_feedback = {}
                    
                    # Initial analysis
                    display_agent_status("Resume Writer", "thinking", "Analyzing your resume against the job requirements...")
                    
                    quality_score, improvements, full_analysis = resume_agent.analyze_resume_quality(
                        st.session_state.resume_text,
                        st.session_state.job_description
                    )
                    
                    st.markdown(f"### Initial Analysis Complete")
                    st.metric("Initial Quality Score", f"{quality_score:.0%}")
                    
                    if quality_score >= st.session_state.quality_threshold:
                        st.success("Your resume already meets the quality threshold!")
                        st.session_state.tailored_resume = st.session_state.resume_text
                        st.session_state.final_resume = st.session_state.resume_text
                        st.session_state.analysis_complete = True
                    else:
                        st.session_state.current_agent_state = AgentState.AWAITING_FEEDBACK
                        st.rerun()
                
                # Handle iterative refinement
                if st.session_state.current_agent_state == AgentState.AWAITING_FEEDBACK:
                    st.markdown("### 🔄 Iterative Refinement Process")
                    st.markdown(f"**Iteration {st.session_state.current_iteration + 1} of {st.session_state.max_iterations}**")
                    
                    # Generate questions for this iteration
                    current_resume = st.session_state.resume_iterations[-1].content if st.session_state.resume_iterations else st.session_state.resume_text
                    
                    display_agent_status(
                        "Resume Writer", 
                        "thinking", 
                        f"Generating clarifying questions for iteration {st.session_state.current_iteration + 1}..."
                    )
                    
                    questions = resume_agent.generate_clarifying_questions(
                        current_resume,
                        st.session_state.job_description,
                        st.session_state.current_iteration + 1
                    )
                    
                    st.markdown("**Please answer these questions to improve your resume:**")
                    
                    # Create form for feedback collection
                    with st.form(f"feedback_form_{st.session_state.current_iteration}"):
                        feedback = {}
                        
                        for i, question in enumerate(questions):
                            if question and isinstance(question, str):  # Ensure question is valid
                                answer = st.text_area(
                                    question,
                                    key=f"q_{st.session_state.current_iteration}_{i}",
                                    height=100,
                                    placeholder="Provide specific details..."
                                )
                                if answer:
                                    feedback[question] = answer
                        
                        submit_button = st.form_submit_button("Submit Feedback", type="primary")
                        
                        if submit_button:
                            if feedback:
                                # Store feedback and trigger refinement
                                st.session_state.agent_feedback = feedback
                                st.session_state.current_agent_state = AgentState.REFINING
                                st.rerun()
                            else:
                                st.warning("Please answer at least one question to continue.")
                
                # Handle refinement
                elif st.session_state.current_agent_state == AgentState.REFINING:
                    display_agent_status(
                        "Resume Writer",
                        "thinking",
                        "Incorporating your feedback and refining the resume..."
                    )
                    
                    current_resume = st.session_state.resume_iterations[-1].content if st.session_state.resume_iterations else st.session_state.resume_text
                    
                    # Refine resume
                    refined_resume = resume_agent.refine_resume(
                        current_resume,
                        st.session_state.job_description,
                        st.session_state.agent_feedback,
                        st.session_state.resume_iterations
                    )
                    
                    # Analyze refined version
                    new_quality_score, new_improvements, _ = resume_agent.analyze_resume_quality(
                        refined_resume,
                        st.session_state.job_description
                    )
                    
                    # Create iteration record
                    iteration = ResumeIteration(
                        version=st.session_state.current_iteration + 1,
                        content=refined_resume,
                        quality_score=new_quality_score,
                        improvements=new_improvements[:3],
                        feedback_incorporated=list(st.session_state.agent_feedback.keys()),
                        timestamp=datetime.now()
                    )
                    
                    st.session_state.resume_iterations.append(iteration)
                    st.session_state.current_iteration += 1
                    
                    # Display iteration result
                    display_iteration_card(iteration)
                    
                    # Check completion conditions
                    if new_quality_score >= st.session_state.quality_threshold:
                        st.success(f"✅ Quality threshold reached! Final score: {new_quality_score:.0%}")
                        st.session_state.tailored_resume = refined_resume
                        st.session_state.final_resume = refined_resume
                        st.session_state.current_agent_state = AgentState.COMPLETE
                        st.session_state.analysis_complete = True
                        
                        st.balloons()
                        st.info("🎉 Your optimized resume is ready! Go to the 'Download Resume' tab.")
                        
                    elif st.session_state.current_iteration >= st.session_state.max_iterations:
                        st.warning(f"Maximum iterations reached. Final score: {new_quality_score:.0%}")
                        st.session_state.tailored_resume = refined_resume
                        st.session_state.final_resume = refined_resume
                        st.session_state.current_agent_state = AgentState.COMPLETE
                        st.session_state.analysis_complete = True
                        
                        st.info("Your resume has been optimized. Go to the 'Download Resume' tab.")
                        
                    else:
                        st.session_state.current_agent_state = AgentState.AWAITING_FEEDBACK
                        st.session_state.agent_feedback = {}
                        time.sleep(1)
                        st.rerun()
    
    with tab2:
        st.markdown("## 🎤 Interview Coach Agent")
        
        if not st.session_state.job_description:
            st.warning("Please upload a resume and job description in the Resume Agent tab first.")
        else:
            # User profiling
            if not st.session_state.user_profile:
                st.markdown("### Let's build your profile")
                
                with st.form("profile_form"):
                    col1, col2 = st.columns(2)
                    with col1:
                        experience_level = st.selectbox(
                            "Experience Level",
                            ["Entry Level", "Mid-Level", "Senior", "Executive"]
                        )
                        
                        interview_experience = st.selectbox(
                            "Interview Comfort",
                            ["Nervous", "Some experience", "Comfortable", "Very confident"]
                        )
                    
                    with col2:
                        target_role = st.text_input("Target Role", placeholder="e.g., Data Scientist")
                        
                        main_concerns = st.multiselect(
                            "Areas to Practice",
                            ["Technical questions", "Behavioral questions", "Salary negotiation", "Company culture"]
                        )
                    
                    submit_profile = st.form_submit_button("Start Interview Practice", type="primary")
                    
                    if submit_profile:
                        st.session_state.user_profile = {
                            "experience_level": experience_level,
                            "interview_experience": interview_experience,
                            "target_role": target_role,
                            "main_concerns": main_concerns
                        }
                        st.session_state.interview_stage = "warmup"
                        st.rerun()
            
            else:
                # Interview practice interface
                st.markdown("### Interview Practice Session")
                
                # Generate question
                if st.button("Get Interview Question"):
                    display_agent_status(
                        "Interview Coach",
                        "thinking",
                        "Preparing a question based on your profile..."
                    )
                    
                    question_data = interview_agent.generate_contextual_question(
                        st.session_state.user_profile,
                        st.session_state.interview_stage,
                        st.session_state.job_description
                    )
                    
                    st.session_state['current_question'] = question_data
                
                # Display current question
                if 'current_question' in st.session_state:
                    st.markdown(f"""
                    <div class="agent-message">
                        <strong>Interview Question:</strong> {st.session_state.current_question['question']}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Tips
                    with st.expander("💡 Tips for this question"):
                        for tip in st.session_state.current_question.get('tips', []):
                            st.markdown(f"• {tip}")
                    
                    # Response input
                    user_response = st.text_area(
                        "Your Answer",
                        height=200,
                        placeholder="Take your time to structure your response..."
                    )
                    
                    if user_response and st.button("Get Feedback", type="primary"):
                        # Analyze response
                        display_agent_status(
                            "Interview Coach",
                            "thinking",
                            "Analyzing your response..."
                        )
                        
                        analysis = interview_agent.analyze_response(
                            st.session_state.current_question['question'],
                            user_response,
                            st.session_state.job_description
                        )
                        
                        # Display feedback
                        st.markdown("### Feedback on Your Response")
                        
                        # Score
                        score = analysis.get('score', 0.7)
                        score_color = "score-high" if score >= 0.8 else "score-medium" if score >= 0.6 else "score-low"
                        st.markdown(f'<span class="quality-score {score_color}">Score: {score:.0%}</span>', unsafe_allow_html=True)
                        
                        # Strengths and improvements
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.markdown("**Strengths:**")
                            for strength in analysis.get('strengths', []):
                                st.success(f"✓ {strength}")
                        
                        with col2:
                            st.markdown("**Areas to Improve:**")
                            for improvement in analysis.get('specific_improvements', []):
                                st.info(f"→ {improvement}")
                        
                        # Follow-up questions
                        if analysis.get('follow_up_questions'):
                            st.markdown("**Follow-up questions to consider:**")
                            for q in analysis['follow_up_questions']:
                                st.markdown(f"• {q}")
                        
                        # Save exchange
                        exchange = InterviewExchange(
                            question=st.session_state.current_question['question'],
                            user_response=user_response,
                            agent_feedback=str(analysis),
                            follow_up_questions=analysis.get('follow_up_questions', []),
                            improvements=analysis.get('specific_improvements', []),
                            score=score
                        )
                        st.session_state.interview_exchanges.append(exchange)
    
    with tab3:
        st.markdown("## 📥 Download Optimized Resume")
        
        if st.session_state.analysis_complete and (st.session_state.final_resume or st.session_state.tailored_resume):
            st.markdown("""
            <div class="download-section">
                <h3>🎉 Your Optimized Resume is Ready!</h3>
                <p>Your resume has been professionally optimized for ATS systems and the target position.</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Display metrics
            col1, col2, col3 = st.columns(3)
            
            with col1:
                final_score = 85 if st.session_state.manual_mode else st.session_state.resume_iterations[-1].quality_score * 100 if st.session_state.resume_iterations else 80
                st.metric("Final Quality Score", f"{int(final_score)}%")
            
            with col2:
                iterations = len(st.session_state.resume_iterations) if not st.session_state.manual_mode else 1
                st.metric("Iterations", iterations)
            
            with col3:
                st.metric("ATS Optimized", "Yes ✓")
            
            # Resume preview
            st.markdown("### Preview")
            
            final_resume_content = st.session_state.final_resume or st.session_state.tailored_resume
            
            # Editable text area
            edited_resume = st.text_area(
                "You can make final edits before downloading:",
                value=final_resume_content,
                height=500,
                key="final_resume_editor"
            )
            
            # Download options
            st.markdown("### Download Options")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.download_button(
                    label="📄 Download as TXT",
                    data=edited_resume,
                    file_name=f"optimized_resume_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    mime="text/plain",
                    use_container_width=True
                )
            
            with col2:
                # Create a formatted version with metadata
                formatted_resume = f"""{edited_resume}

---
Resume Optimization Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}
Target Position: {st.session_state.job_description[:100]}...
Quality Score: {int(final_score)}%
Optimization Mode: {'Manual' if st.session_state.manual_mode else 'Agent-based'}
"""
                st.download_button(
                    label="📋 Download with Report",
                    data=formatted_resume,
                    file_name=f"resume_with_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    mime="text/plain",
                    use_container_width=True
                )
            
            with col3:
                # Create a markdown version
                markdown_resume = f"""# Optimized Resume

{edited_resume}

## Optimization Details
- **Date**: {datetime.now().strftime('%Y-%m-%d')}
- **Quality Score**: {int(final_score)}%
- **ATS Optimized**: Yes
"""
                st.download_button(
                    label="📝 Download as MD",
                    data=markdown_resume,
                    file_name=f"resume_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                    mime="text/markdown",
                    use_container_width=True
                )
            
            # Additional tips
            with st.expander("📌 Next Steps & Tips"):
                st.markdown("""
                **Before Submitting Your Resume:**
                1. **Format Check**: Save as PDF for final submission to preserve formatting
                2. **ATS Test**: Run through an ATS simulator if available
                3. **Proofread**: Do a final review for any typos or formatting issues
                4. **Customize**: Make minor adjustments for each specific application
                
                **File Format Recommendations:**
                - **PDF**: Best for email submissions and online applications
                - **DOCX**: Required by some ATS systems
                - **TXT**: Useful for copy-pasting into web forms
                
                **Interview Preparation:**
                - Use the Interview Coach tab to practice questions
                - Review the key achievements you've highlighted
                - Prepare stories that demonstrate the skills mentioned
                """)
        
        else:
            st.info("👆 Complete the resume optimization process to download your enhanced resume.")
            
            if st.session_state.current_agent_state != AgentState.IDLE:
                st.warning(f"Agent Status: {st.session_state.current_agent_state.value}")
                
                if st.session_state.resume_iterations:
                    st.markdown("### Progress So Far")
                    latest = st.session_state.resume_iterations[-1]
                    st.metric("Current Quality Score", f"{latest.quality_score:.0%}")
                    st.info(f"The agent is working on iteration {st.session_state.current_iteration} of {st.session_state.max_iterations}")
    
    with tab4:
        st.markdown("## 📚 History & Analytics")
        
        if st.session_state.resume_iterations:
            st.markdown("### Resume Refinement History")
            
            # Quality score progression
            if len(st.session_state.resume_iterations) > 1:
                import pandas as pd
                
                scores = [iteration.quality_score for iteration in st.session_state.resume_iterations]
                versions = [f"V{iteration.version}" for iteration in st.session_state.resume_iterations]
                
                df = pd.DataFrame({
                    "Version": versions,
                    "Quality Score": scores
                })
                
                st.line_chart(df.set_index("Version"))
            
            # Iteration details
            st.markdown("### Iteration Details")
            for iteration in reversed(st.session_state.resume_iterations):
                display_iteration_card(iteration)
                
                with st.expander(f"View Resume Version {iteration.version}"):
                    st.text(iteration.content[:1000] + "...")
                    
                    # Download this version
                    st.download_button(
                        f"Download Version {iteration.version}",
                        data=iteration.content,
                        file_name=f"resume_v{iteration.version}_{iteration.timestamp.strftime('%Y%m%d')}.txt",
                        mime="text/plain",
                        key=f"download_v{iteration.version}"
                    )
        
        if st.session_state.interview_exchanges:
            st.markdown("### Interview Practice History")
            
            # Performance metrics
            scores = [exchange.score for exchange in st.session_state.interview_exchanges]
            avg_score = sum(scores) / len(scores) if scores else 0
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Average Score", f"{avg_score:.0%}")
            with col2:
                st.metric("Questions Practiced", len(st.session_state.interview_exchanges))
            
            # Question history
            st.markdown("### Question-by-Question Review")
            for i, exchange in enumerate(st.session_state.interview_exchanges):
                with st.expander(f"Question {i+1}: {exchange.question[:60]}..."):
                    st.markdown(f"**Your Response:** {exchange.user_response}")
                    st.markdown(f"**Score:** {exchange.score:.0%}")
                    
                    if exchange.improvements:
                        st.markdown("**Key Improvements:**")
                        for imp in exchange.improvements:
                            st.markdown(f"• {imp}")
        
        # Export all data
        if st.session_state.resume_iterations or st.session_state.interview_exchanges:
            st.markdown("### Export Session Data")
            
            session_data = {
                "timestamp": datetime.now().isoformat(),
                "resume_iterations": len(st.session_state.resume_iterations),
                "interview_questions": len(st.session_state.interview_exchanges),
                "final_quality_score": st.session_state.resume_iterations[-1].quality_score if st.session_state.resume_iterations else 0,
                "average_interview_score": sum(e.score for e in st.session_state.interview_exchanges) / len(st.session_state.interview_exchanges) if st.session_state.interview_exchanges else 0
            }
            
            st.download_button(
                "📊 Export Analytics Report",
                data=json.dumps(session_data, indent=2),
                file_name=f"career_optimization_report_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json"
            )

if __name__ == "__main__":
    main()
