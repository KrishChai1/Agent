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
import hashlib
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
</style>
""", unsafe_allow_html=True)

# Enums and Data Classes
class AgentState(Enum):
    IDLE = "idle"
    ANALYZING = "analyzing"
    REFINING = "refining"
    AWAITING_FEEDBACK = "awaiting_feedback"
    COMPLETE = "complete"

class InterviewMode(Enum):
    GUIDED = "guided"
    PRACTICE = "practice"
    MOCK = "mock"
    COACHING = "coaching"

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
    if 'resume_iterations' not in st.session_state:
        st.session_state.resume_iterations = []
    if 'current_agent_state' not in st.session_state:
        st.session_state.current_agent_state = AgentState.IDLE
    if 'interview_exchanges' not in st.session_state:
        st.session_state.interview_exchanges = []
    if 'agent_memory' not in st.session_state:
        st.session_state.agent_memory = {}
    if 'user_preferences' not in st.session_state:
        st.session_state.user_preferences = {}
    if 'current_iteration' not in st.session_state:
        st.session_state.current_iteration = 0
    if 'max_iterations' not in st.session_state:
        st.session_state.max_iterations = 5
    if 'quality_threshold' not in st.session_state:
        st.session_state.quality_threshold = 0.85
    if 'interview_stage' not in st.session_state:
        st.session_state.interview_stage = "initial"
    if 'user_profile' not in st.session_state:
        st.session_state.user_profile = {}

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
    
    def analyze_resume_quality(self, resume: str, job_description: str) -> Tuple[float, List[str]]:
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
            "missing_elements": [<list of missing critical elements>],
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
            result = json.loads(response.strip().replace('```json', '').replace('```', ''))
            
            quality_score = result.get('quality_score', 0.7)
            improvements = (result.get('critical_improvements', []) + 
                          result.get('suggested_improvements', []))
            
            return quality_score, improvements, result
            
        except Exception as e:
            return 0.7, ["Unable to complete analysis"], {}
    
    def generate_clarifying_questions(self, resume: str, job_description: str, iteration: int) -> List[str]:
        """Generate questions to gather more information for improvement"""
        
        prompt = f"""
        As a resume optimization expert, you're on iteration {iteration} of improving this resume.
        Generate 3-5 specific questions to gather information that would help create a stronger resume.
        
        Focus on:
        1. Quantifiable achievements not mentioned
        2. Relevant skills or experiences that might be missing
        3. Specific projects or accomplishments related to the job
        4. Leadership or impact examples
        
        Current Resume Summary:
        {resume[:1500]}
        
        Target Role Requirements:
        {job_description[:1000]}
        
        Return a JSON array of specific, actionable questions.
        """
        
        try:
            response = self._safe_api_call([
                {"role": "system", "content": "You are an expert career counselor who asks insightful questions."},
                {"role": "user", "content": prompt}
            ])
            
            questions = json.loads(response.strip().replace('```json', '').replace('```', ''))
            return questions if isinstance(questions, list) else []
            
        except Exception:
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
            iteration_context = "Previous feedback incorporated:\n"
            for iteration in previous_iterations[-3:]:  # Last 3 iterations
                iteration_context += f"- Version {iteration.version}: {', '.join(iteration.feedback_incorporated)}\n"
        
        prompt = f"""
        You are an expert resume writer performing iteration {len(previous_iterations) + 1} of resume optimization.
        
        {iteration_context}
        
        Current feedback to incorporate:
        {json.dumps(feedback, indent=2)}
        
        Requirements:
        1. Incorporate ALL feedback provided
        2. Maintain all factual information from the original
        3. Enhance with quantifiable metrics where suggested
        4. Optimize keyword placement for ATS
        5. Ensure compelling narrative flow
        6. Use strong action verbs
        7. Mirror the language style of the job description
        
        Original Resume:
        {resume}
        
        Target Job Description:
        {job_description[:2000]}
        
        Create an optimized resume that addresses all feedback. Return ONLY the resume text.
        """
        
        try:
            response = self._safe_api_call([
                {"role": "system", "content": "You are a master resume writer who creates compelling, ATS-optimized resumes."},
                {"role": "user", "content": prompt}
            ], max_tokens=3000)
            
            return response.strip()
            
        except Exception as e:
            st.error(f"Refinement error: {str(e)}")
            return resume
    
    def suggest_improvements(self, current_resume: str, target_score: float, current_score: float) -> List[str]:
        """Suggest specific improvements to reach target score"""
        
        prompt = f"""
        The current resume has a quality score of {current_score:.2f}.
        Target score is {target_score:.2f}.
        
        Analyze the resume and provide 5 specific, actionable improvements that would increase the score.
        Each suggestion should be concrete and implementable.
        
        Resume excerpt:
        {current_resume[:2000]}
        
        Return a JSON array of improvement suggestions.
        """
        
        try:
            response = self._safe_api_call([
                {"role": "system", "content": "You are a resume improvement specialist."},
                {"role": "user", "content": prompt}
            ])
            
            suggestions = json.loads(response.strip().replace('```json', '').replace('```', ''))
            return suggestions if isinstance(suggestions, list) else []
            
        except Exception:
            return ["Add more quantifiable achievements", "Include industry-specific keywords"]

class InterviewCoachAgent:
    """Agent that conducts interactive interview preparation"""
    
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-3.5-turbo"
        self.conversation_state = {}
        
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
        
        Provide a detailed analysis with:
        {{
            "score": <float 0-1>,
            "strengths": [<specific strengths in the response>],
            "weaknesses": [<areas that need improvement>],
            "missing_elements": [<what should have been included>],
            "follow_up_questions": [<2-3 questions to dig deeper>],
            "improved_response_structure": {{
                "situation": "<if STAR method applies>",
                "task": "<if STAR method applies>",
                "action": "<if STAR method applies>",
                "result": "<if STAR method applies>",
                "key_points": [<main points to hit>]
            }},
            "specific_improvements": [<concrete ways to improve>],
            "sample_enhanced_response": "<a brief example of how to improve>"
        }}
        
        Be specific and actionable in your feedback.
        """
        
        try:
            response = self._safe_api_call([
                {"role": "system", "content": "You are an expert interview coach who provides detailed, actionable feedback."},
                {"role": "user", "content": prompt}
            ])
            
            return json.loads(response.strip().replace('```json', '').replace('```', ''))
            
        except Exception:
            return {
                "score": 0.7,
                "strengths": ["Good attempt"],
                "weaknesses": ["Could be more specific"],
                "follow_up_questions": ["Can you provide a specific example?"],
                "specific_improvements": ["Add quantifiable results"]
            }
    
    def generate_contextual_question(self, user_profile: Dict, previous_exchanges: List[InterviewExchange], 
                                   job_description: str, stage: str) -> Dict:
        """Generate contextual questions based on conversation history"""
        
        # Build conversation context
        context = "Previous exchanges:\n"
        for exchange in previous_exchanges[-3:]:
            context += f"Q: {exchange.question}\n"
            context += f"Key points from response: {exchange.user_response[:200]}...\n"
            context += f"Areas identified for exploration: {', '.join(exchange.follow_up_questions[:2])}\n\n"
        
        prompt = f"""
        As an expert interviewer, generate the next interview question based on the conversation flow.
        
        Interview Stage: {stage}
        User Profile: {json.dumps(user_profile, indent=2)}
        {context}
        Job Requirements: {job_description[:1000]}
        
        Generate a question that:
        1. Builds on previous responses
        2. Explores areas not yet covered
        3. Matches the interview stage ({stage})
        4. Tests specific competencies from the job description
        
        Return JSON:
        {{
            "question": "<the question>",
            "question_type": "<behavioral|technical|situational|cultural>",
            "competency_tested": "<specific skill or quality>",
            "follow_up_prompts": [<2-3 prompts if answer is brief>],
            "ideal_response_elements": [<key points to listen for>],
            "red_flags": [<concerning responses>]
        }}
        """
        
        try:
            response = self._safe_api_call([
                {"role": "system", "content": "You are an expert interviewer who asks probing, relevant questions."},
                {"role": "user", "content": prompt}
            ])
            
            return json.loads(response.strip().replace('```json', '').replace('```', ''))
            
        except Exception:
            return {
                "question": "Tell me about a challenging project you've worked on recently.",
                "question_type": "behavioral",
                "competency_tested": "problem-solving",
                "follow_up_prompts": ["What was your specific role?", "What was the outcome?"]
            }
    
    def provide_coaching(self, weakness_areas: List[str], job_requirements: str) -> str:
        """Provide personalized coaching based on identified weaknesses"""
        
        prompt = f"""
        Provide personalized interview coaching for these areas of improvement:
        {json.dumps(weakness_areas, indent=2)}
        
        Job Requirements:
        {job_requirements[:1000]}
        
        Create a coaching response that:
        1. Addresses each weakness with specific strategies
        2. Provides example responses or frameworks
        3. Includes practice exercises
        4. Offers encouragement while being realistic
        5. Gives insider tips for this type of role
        
        Make it conversational and supportive.
        """
        
        try:
            return self._safe_api_call([
                {"role": "system", "content": "You are a supportive interview coach who provides practical, actionable advice."},
                {"role": "user", "content": prompt}
            ])
        except Exception:
            return "Let's work on strengthening your interview responses. Focus on specific examples and quantifiable results."
    
    def adaptive_difficulty(self, current_performance: float, stage: str) -> str:
        """Adjust question difficulty based on performance"""
        if current_performance > 0.8:
            return "advanced"
        elif current_performance > 0.6:
            return "intermediate"
        else:
            return "foundational"

def parse_resume_sections(resume_text: str) -> Dict:
    """Parse resume into structured sections"""
    sections = {
        "contact": "",
        "summary": "",
        "experience": [],
        "education": [],
        "skills": [],
        "certifications": [],
        "projects": [],
        "achievements": []
    }
    
    # Enhanced section patterns
    section_patterns = {
        "contact": r"^(.*?)(?=\n(?:Summary|Objective|Profile|Experience|Education))",
        "summary": r"(?:Summary|Objective|Profile|About Me|Professional Summary)\s*:?\s*\n(.*?)(?=\n(?:Experience|Work|Education|Skills))",
        "experience": r"(?:Experience|Work Experience|Professional Experience|Employment)\s*:?\s*\n(.*?)(?=\n(?:Education|Skills|Projects|Certifications|$))",
        "education": r"(?:Education|Academic Background|Qualifications)\s*:?\s*\n(.*?)(?=\n(?:Skills|Projects|Certifications|Experience|$))",
        "skills": r"(?:Skills|Technical Skills|Core Competencies|Expertise)\s*:?\s*\n(.*?)(?=\n(?:Projects|Certifications|Experience|Education|$))",
        "certifications": r"(?:Certifications?|Licenses?|Credentials?)\s*:?\s*\n(.*?)(?=\n(?:Projects|Experience|Education|Skills|$))",
        "projects": r"(?:Projects?|Portfolio|Work Samples)\s*:?\s*\n(.*?)(?=\n(?:Experience|Education|Skills|Certifications|$))",
        "achievements": r"(?:Achievements?|Awards?|Honors?|Recognition)\s*:?\s*\n(.*?)(?=\n(?:Experience|Education|Skills|Projects|$))"
    }
    
    for section, pattern in section_patterns.items():
        match = re.search(pattern, resume_text, re.IGNORECASE | re.DOTALL | re.MULTILINE)
        if match:
            content = match.group(1) if section != "contact" else match.group(0)
            sections[section] = content.strip()
    
    return sections

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
            max_value=10,
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
        
        st.markdown("---")
        st.markdown("### 💡 Agent Capabilities")
        st.markdown("""
        **Resume Writer Agent:**
        - Iterative refinement
        - Quality assessment
        - Feedback incorporation
        - ATS optimization
        
        **Interview Coach Agent:**
        - Adaptive questioning
        - Response analysis
        - Personalized coaching
        - Progress tracking
        """)
    
    # Main tabs
    tab1, tab2, tab3 = st.tabs(["Resume Agent", "Interview Coach Agent", "Agent History"])
    
    with tab1:
        st.markdown("## 🤖 Resume Writer Agent")
        st.markdown("This agent will iteratively refine your resume until it meets quality standards.")
        
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
                key="job_desc_input"
            )
            st.session_state.job_description = job_description
        
        if st.session_state.resume_text and st.session_state.job_description:
            st.markdown("---")
            
            if st.button("Start Resume Agent", type="primary", use_container_width=True):
                st.session_state.current_agent_state = AgentState.ANALYZING
                st.session_state.current_iteration = 0
                st.session_state.resume_iterations = []
                
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
                else:
                    # Start iterative refinement
                    st.markdown("### 🔄 Starting Iterative Refinement Process")
                    
                    current_resume = st.session_state.resume_text
                    iteration_container = st.container()
                    
                    while (st.session_state.current_iteration < st.session_state.max_iterations and 
                           quality_score < st.session_state.quality_threshold):
                        
                        st.session_state.current_iteration += 1
                        
                        with iteration_container:
                            st.markdown(f"#### Iteration {st.session_state.current_iteration}")
                            
                            # Generate clarifying questions
                            display_agent_status(
                                "Resume Writer", 
                                "thinking", 
                                f"Generating clarifying questions for iteration {st.session_state.current_iteration}..."
                            )
                            
                            questions = resume_agent.generate_clarifying_questions(
                                current_resume,
                                st.session_state.job_description,
                                st.session_state.current_iteration
                            )
                            
                            # Display questions and collect feedback
                            st.markdown("**Please answer these questions to improve your resume:**")
                            
                            feedback = {}
                            for i, question in enumerate(questions[:3]):
                                response = st.text_area(
                                    question,
                                    key=f"q_{st.session_state.current_iteration}_{i}",
                                    height=100
                                )
                                if response:
                                    feedback[question] = response
                            
                            if st.button(f"Submit Feedback for Iteration {st.session_state.current_iteration}", 
                                       key=f"submit_{st.session_state.current_iteration}"):
                                
                                # Refine resume based on feedback
                                display_agent_status(
                                    "Resume Writer",
                                    "thinking",
                                    "Incorporating your feedback and refining the resume..."
                                )
                                
                                refined_resume = resume_agent.refine_resume(
                                    current_resume,
                                    st.session_state.job_description,
                                    feedback,
                                    st.session_state.resume_iterations
                                )
                                
                                # Analyze refined version
                                new_quality_score, new_improvements, _ = resume_agent.analyze_resume_quality(
                                    refined_resume,
                                    st.session_state.job_description
                                )
                                
                                # Create iteration record
                                iteration = ResumeIteration(
                                    version=st.session_state.current_iteration,
                                    content=refined_resume,
                                    quality_score=new_quality_score,
                                    improvements=new_improvements[:3],
                                    feedback_incorporated=list(feedback.keys()),
                                    timestamp=datetime.now()
                                )
                                
                                st.session_state.resume_iterations.append(iteration)
                                display_iteration_card(iteration)
                                
                                # Check if we've reached the threshold
                                if new_quality_score >= st.session_state.quality_threshold:
                                    st.success(f"✅ Quality threshold reached! Score: {new_quality_score:.0%}")
                                    st.session_state.tailored_resume = refined_resume
                                    st.session_state.current_agent_state = AgentState.COMPLETE
                                    break
                                else:
                                    current_resume = refined_resume
                                    quality_score = new_quality_score
                                    st.info(f"Quality improved to {new_quality_score:.0%}. Continuing refinement...")
                            else:
                                break
                    
                    if st.session_state.current_agent_state == AgentState.COMPLETE:
                        st.markdown("### 🎉 Resume Optimization Complete!")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.download_button(
                                "📥 Download Optimized Resume",
                                data=st.session_state.tailored_resume,
                                file_name=f"optimized_resume_{datetime.now().strftime('%Y%m%d')}.txt",
                                mime="text/plain"
                            )
                        with col2:
                            if st.button("View Full Resume"):
                                st.text_area("Final Resume", st.session_state.tailored_resume, height=500)
    
    with tab2:
        st.markdown("## 🎤 Interview Coach Agent")
        st.markdown("This agent adapts to your responses and provides personalized coaching.")
        
        if not st.session_state.job_description:
            st.warning("Please upload a resume and job description in the Resume Agent tab first.")
        else:
            # User profiling
            if not st.session_state.user_profile:
                st.markdown("### Let's build your profile")
                
                col1, col2 = st.columns(2)
                with col1:
                    experience_level = st.selectbox(
                        "Experience Level",
                        ["Entry Level (0-2 years)", "Mid-Level (3-5 years)", 
                         "Senior (6-10 years)", "Executive (10+ years)"]
                    )
                    
                    interview_experience = st.selectbox(
                        "Interview Experience",
                        ["Limited", "Some experience", "Comfortable", "Very experienced"]
                    )
                
                with col2:
                    target_role_level = st.selectbox(
                        "Target Role Level",
                        ["Individual Contributor", "Team Lead", "Manager", "Director+"]
                    )
                    
                    main_concerns = st.multiselect(
                        "Main Interview Concerns",
                        ["Technical questions", "Behavioral questions", "Salary negotiation",
                         "Company culture fit", "Leadership scenarios", "Case studies"]
                    )
                
                if st.button("Start Interview Coaching", type="primary"):
                    st.session_state.user_profile = {
                        "experience_level": experience_level,
                        "interview_experience": interview_experience,
                        "target_role_level": target_role_level,
                        "main_concerns": main_concerns
                    }
                    st.session_state.interview_stage = "warmup"
                    st.rerun()
            
            else:
                # Interview coaching interface
                st.markdown("### Interview Practice Session")
                
                # Progress indicator
                stages = ["warmup", "technical", "behavioral", "advanced", "wrap-up"]
                current_stage_index = stages.index(st.session_state.interview_stage)
                
                progress_cols = st.columns(len(stages))
                for i, (col, stage) in enumerate(zip(progress_cols, stages)):
                    with col:
                        if i < current_stage_index:
                            st.success(f"✓ {stage.title()}")
                        elif i == current_stage_index:
                            st.info(f"▶ {stage.title()}")
                        else:
                            st.text(f"○ {stage.title()}")
                
                st.markdown("---")
                
                # Chat interface
                chat_container = st.container()
                
                # Display conversation history
                with chat_container:
                    for exchange in st.session_state.interview_exchanges:
                        st.markdown(f"""
                        <div class="agent-message">
                            <strong>Coach:</strong> {exchange.question}
                        </div>
                        """, unsafe_allow_html=True)
                        
                        st.markdown(f"""
                        <div class="user-response">
                            <strong>You:</strong> {exchange.user_response}
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Show feedback
                        with st.expander("View Feedback & Analysis"):
                            st.markdown(f"**Score:** {exchange.score:.0%}")
                            st.markdown("**Strengths:**")
                            for strength in exchange.improvements[:2]:
                                st.markdown(f"• {strength}")
                            st.markdown(exchange.agent_feedback)
                
                # Generate next question
                if len(st.session_state.interview_exchanges) == 0 or st.button("Next Question"):
                    display_agent_status(
                        "Interview Coach",
                        "thinking",
                        "Preparing your next question based on our conversation..."
                    )
                    
                    question_data = interview_agent.generate_contextual_question(
                        st.session_state.user_profile,
                        st.session_state.interview_exchanges,
                        st.session_state.job_description,
                        st.session_state.interview_stage
                    )
                    
                    st.markdown(f"""
                    <div class="agent-message">
                        <strong>Coach:</strong> {question_data['question']}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Response input
                    user_response = st.text_area(
                        "Your Response",
                        height=200,
                        placeholder="Take your time to structure your response...",
                        key=f"response_{len(st.session_state.interview_exchanges)}"
                    )
                    
                    if user_response and st.button("Submit Response", type="primary"):
                        # Analyze response
                        display_agent_status(
                            "Interview Coach",
                            "thinking",
                            "Analyzing your response and preparing feedback..."
                        )
                        
                        analysis = interview_agent.analyze_response(
                            question_data['question'],
                            user_response,
                            st.session_state.job_description
                        )
                        
                        # Generate coaching feedback
                        coaching_feedback = interview_agent.provide_coaching(
                            analysis.get('weaknesses', []),
                            st.session_state.job_description
                        )
                        
                        # Create exchange record
                        exchange = InterviewExchange(
                            question=question_data['question'],
                            user_response=user_response,
                            agent_feedback=coaching_feedback,
                            follow_up_questions=analysis.get('follow_up_questions', []),
                            improvements=analysis.get('strengths', []) + analysis.get('specific_improvements', []),
                            score=analysis.get('score', 0.7)
                        )
                        
                        st.session_state.interview_exchanges.append(exchange)
                        
                        # Update stage if needed
                        if len(st.session_state.interview_exchanges) % 3 == 0 and current_stage_index < len(stages) - 1:
                            st.session_state.interview_stage = stages[current_stage_index + 1]
                        
                        st.rerun()
                
                # Session summary
                if len(st.session_state.interview_exchanges) >= 5:
                    st.markdown("---")
                    st.markdown("### Session Summary")
                    
                    avg_score = sum(e.score for e in st.session_state.interview_exchanges) / len(st.session_state.interview_exchanges)
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Average Score", f"{avg_score:.0%}")
                    with col2:
                        st.metric("Questions Practiced", len(st.session_state.interview_exchanges))
                    with col3:
                        st.metric("Stage", st.session_state.interview_stage.title())
                    
                    if st.button("Get Personalized Action Plan"):
                        display_agent_status(
                            "Interview Coach",
                            "thinking",
                            "Creating your personalized improvement plan..."
                        )
                        
                        # Generate action plan based on all exchanges
                        weak_areas = []
                        for exchange in st.session_state.interview_exchanges:
                            if exchange.score < 0.8:
                                weak_areas.extend(exchange.improvements)
                        
                        action_plan = interview_agent.provide_coaching(
                            list(set(weak_areas))[:5],
                            st.session_state.job_description
                        )
                        
                        st.markdown("### Your Personalized Action Plan")
                        st.markdown(action_plan)
                        
                        # Download option
                        st.download_button(
                            "📥 Download Action Plan",
                            data=action_plan,
                            file_name=f"interview_action_plan_{datetime.now().strftime('%Y%m%d')}.txt",
                            mime="text/plain"
                        )
    
    with tab3:
        st.markdown("## 📚 Agent History & Analytics")
        
        if st.session_state.resume_iterations:
            st.markdown("### Resume Refinement History")
            
            # Quality score chart
            quality_scores = [iteration.quality_score for iteration in st.session_state.resume_iterations]
            versions = [f"V{iteration.version}" for iteration in st.session_state.resume_iterations]
            
            import pandas as pd
            df = pd.DataFrame({
                "Version": versions,
                "Quality Score": quality_scores
            })
            
            st.line_chart(df.set_index("Version"))
            
            # Iteration details
            st.markdown("### Iteration Details")
            for iteration in reversed(st.session_state.resume_iterations):
                display_iteration_card(iteration)
                
                with st.expander(f"View Resume Version {iteration.version}"):
                    st.text(iteration.content[:1000] + "...")
        
        if st.session_state.interview_exchanges:
            st.markdown("### Interview Practice Analytics")
            
            # Performance chart
            scores = [exchange.score for exchange in st.session_state.interview_exchanges]
            questions = [f"Q{i+1}" for i in range(len(scores))]
            
            df = pd.DataFrame({
                "Question": questions,
                "Score": scores
            })
            
            st.line_chart(df.set_index("Question"))
            
            # Detailed feedback
            st.markdown("### Question-by-Question Review")
            for i, exchange in enumerate(st.session_state.interview_exchanges):
                with st.expander(f"Question {i+1}: {exchange.question[:50]}..."):
                    st.markdown(f"**Your Response:** {exchange.user_response}")
                    st.markdown(f"**Score:** {exchange.score:.0%}")
                    st.markdown(f"**Coach Feedback:** {exchange.agent_feedback}")

if __name__ == "__main__":
    main()
