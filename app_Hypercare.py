import os
import streamlit as st
import pandas as pd
import yaml
from tabulate import tabulate
import openai
from datetime import datetime
import json
from typing import Dict, List, Any

# CrewAI imports (uncomment when you have CrewAI installed)
# from crewai import Crew, Agent, Task, Process

# Page config
st.set_page_config(
    page_title="Hypercare Excel CrewAI Analyzer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize directories
ANALYSIS_DIR = 'analysis'
os.makedirs(ANALYSIS_DIR, exist_ok=True)

# Load YAML configs
@st.cache_resource
def load_yaml(filename):
    """Load YAML configuration files"""
    try:
        with open(filename, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        st.error(f"Configuration file {filename} not found. Please ensure all YAML files are present.")
        return None

# Initialize OpenAI
def init_openai():
    """Initialize OpenAI with API key from Streamlit secrets"""
    if 'OPENAI_API_KEY' in st.secrets:
        openai.api_key = st.secrets['OPENAI_API_KEY']
        return True
    else:
        st.error("Please add your OpenAI API key to Streamlit secrets (.streamlit/secrets.toml)")
        st.info("Add the following to your secrets.toml file:\n```\nOPENAI_API_KEY = 'your-api-key-here'\n```")
        return False

# Excel file processing functions
def read_excel_file(file):
    """Read Excel file and return DataFrame"""
    try:
        df = pd.read_excel(file)
        return df, None
    except Exception as e:
        return None, f"Error reading file: {str(e)}"

def analyze_single_file(filename, df, query):
    """Analyze a single Excel file using OpenAI"""
    # Prepare data preview
    preview = tabulate(df.head(10), headers='keys', tablefmt='github', showindex=False)
    
    prompt = f"""
You are an expert data analyst specializing in IT issue tracking and root cause analysis. 
Here is a preview of an Excel file containing hypercare issues:

File: {filename}
Total rows: {len(df)}
Columns: {', '.join(df.columns.tolist())}

Data preview:
{preview}

User question: {query}

Please provide a detailed analysis answering the user's question. Focus on:
1. Direct answer to the question
2. Key insights from the data
3. Patterns or trends noticed
4. Recommendations if applicable
"""
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful data analyst specializing in IT operations and issue tracking."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,
            temperature=0.2
        )
        return response['choices'][0]['message']['content']
    except Exception as e:
        return f"Error analyzing file: {str(e)}"

def generate_file_analysis_markdown(filename, df):
    """Generate markdown analysis for a single file"""
    analysis = f"# Analysis for {filename}\n\n"
    analysis += f"Rows: {len(df)}, Columns: {len(df.columns)}\n\n"
    analysis += f"Columns: {', '.join(df.columns.tolist())}\n\n"
    
    # Add first few rows as a table
    if len(df) > 0:
        preview_df = df.head(5)
        analysis += tabulate(preview_df, headers='keys', tablefmt='github', showindex=False)
    
    return analysis

def aggregate_analyses(file_analyses):
    """Aggregate all file analyses and find patterns"""
    prompt = f"""
You are an expert in IT operations and root cause analysis. You have analyzed multiple Excel files containing hypercare issues from different clients. 

Here are the individual analyses:

{chr(10).join(file_analyses)}

Please provide:
1. Common patterns across all files
2. Most frequent types of issues
3. Common root causes
4. Recommendations for preventing similar issues
5. Priority areas for improvement

Format your response in markdown with clear sections.
"""
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an expert in IT operations analysis and root cause identification."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1500,
            temperature=0.3
        )
        return response['choices'][0]['message']['content']
    except Exception as e:
        return f"Error generating aggregate analysis: {str(e)}"

# CrewAI Integration Functions (uncomment when CrewAI is available)
"""
def create_file_agent():
    return Agent(
        role='File Analyst',
        goal='Analyze individual Excel files for issues and patterns',
        backstory='You are an expert data analyst specializing in IT operations and issue tracking.',
        verbose=True,
        allow_delegation=False
    )

def create_aggregator_agent():
    return Agent(
        role='Root Cause Analyst',
        goal='Aggregate findings from multiple analyses and identify root causes',
        backstory='You are a senior IT consultant specializing in root cause analysis and process improvement.',
        verbose=True,
        allow_delegation=False
    )

def run_crewai_analysis(file_paths):
    # Create agents
    file_agent = create_file_agent()
    aggregator_agent = create_aggregator_agent()
    
    # Create tasks
    file_tasks = []
    for file_path in file_paths:
        task = Task(
            description=f'Analyze the Excel file {file_path} and create a detailed report',
            agent=file_agent
        )
        file_tasks.append(task)
    
    aggregation_task = Task(
        description='Aggregate all analyses and identify common patterns and root causes',
        agent=aggregator_agent
    )
    
    # Create crew
    crew = Crew(
        agents=[file_agent, aggregator_agent],
        tasks=file_tasks + [aggregation_task],
        verbose=2,
        process=Process.sequential
    )
    
    # Execute crew
    result = crew.kickoff()
    return result
"""

# Streamlit UI
def main():
    st.title("🏥 Hypercare Excel CrewAI Analyzer")
    st.markdown("Upload Excel files containing hypercare issues and ask questions about the data.")
    
    # Initialize OpenAI
    if not init_openai():
        st.stop()
    
    # Load configurations
    agents_config = load_yaml('agents.yaml')
    tasks_config = load_yaml('tasks.yaml')
    crew_config = load_yaml('crew.yaml')
    
    # Sidebar for configuration and file upload
    with st.sidebar:
        st.header("📁 File Upload")
        uploaded_files = st.file_uploader(
            "Upload Excel Files",
            type=['xlsx', 'xls'],
            accept_multiple_files=True,
            help="Upload one or more Excel files containing hypercare issues"
        )
        
        st.divider()
        
        st.header("⚙️ Configuration")
        st.info("Configuration files loaded:")
        if agents_config:
            st.success("✅ agents.yaml")
        if tasks_config:
            st.success("✅ tasks.yaml")
        if crew_config:
            st.success("✅ crew.yaml")
        
        st.divider()
        
        # Analysis mode
        analysis_mode = st.radio(
            "Analysis Mode",
            ["Individual File Analysis", "Aggregate Analysis", "CrewAI Analysis (Beta)"],
            help="Choose how to analyze your files"
        )
    
    # Initialize session state
    if 'file_data' not in st.session_state:
        st.session_state.file_data = {}
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    if 'analyses' not in st.session_state:
        st.session_state.analyses = {}
    
    # Process uploaded files
    if uploaded_files:
        with st.spinner("Processing uploaded files..."):
            for file in uploaded_files:
                if file.name not in st.session_state.file_data:
                    df, error = read_excel_file(file)
                    if df is not None:
                        st.session_state.file_data[file.name] = df
                        # Generate initial analysis
                        analysis_md = generate_file_analysis_markdown(file.name, df)
                        st.session_state.analyses[file.name] = analysis_md
                        # Save to file
                        with open(os.path.join(ANALYSIS_DIR, f"{file.name}.md"), 'w') as f:
                            f.write(analysis_md)
                    else:
                        st.error(f"Failed to read {file.name}: {error}")
        
        st.success(f"✅ Loaded {len(st.session_state.file_data)} files successfully!")
    
    # Main content area
    if st.session_state.file_data:
        # Display file information
        with st.expander("📊 Uploaded Files Overview", expanded=True):
            file_info = []
            for filename, df in st.session_state.file_data.items():
                file_info.append({
                    "File": filename,
                    "Rows": len(df),
                    "Columns": len(df.columns),
                    "Columns List": ", ".join(df.columns.tolist()[:5]) + ("..." if len(df.columns) > 5 else "")
                })
            st.dataframe(pd.DataFrame(file_info), use_container_width=True)
        
        # Analysis section based on mode
        if analysis_mode == "Individual File Analysis":
            st.header("💬 Ask Questions About Your Data")
            
            # Chat interface
            query = st.text_input("Ask a question about your Excel data:", key="chat_input")
            
            if st.button("Send", type="primary") or query:
                if query:
                    # Add to chat history
                    st.session_state.chat_history.append({"role": "user", "content": query})
                    
                    # Analyze each file
                    with st.spinner("Analyzing files..."):
                        responses = []
                        for filename, df in st.session_state.file_data.items():
                            response = analyze_single_file(filename, df, query)
                            responses.append(f"### {filename}\n{response}")
                        
                        full_response = "\n\n---\n\n".join(responses)
                        st.session_state.chat_history.append({"role": "assistant", "content": full_response})
            
            # Display chat history
            if st.session_state.chat_history:
                st.header("📝 Chat History")
                for message in st.session_state.chat_history:
                    if message["role"] == "user":
                        st.chat_message("user").markdown(message["content"])
                    else:
                        st.chat_message("assistant").markdown(message["content"])
        
        elif analysis_mode == "Aggregate Analysis":
            st.header("🔍 Aggregate Analysis")
            
            if st.button("Generate Aggregate Analysis", type="primary"):
                with st.spinner("Generating comprehensive analysis..."):
                    # Collect all analyses
                    file_analyses = []
                    for filename, analysis in st.session_state.analyses.items():
                        file_analyses.append(f"## {filename}\n{analysis}")
                    
                    # Generate aggregate analysis
                    aggregate_report = aggregate_analyses(file_analyses)
                    
                    # Save aggregate report
                    report_path = os.path.join(ANALYSIS_DIR, "aggregated_report.md")
                    with open(report_path, 'w') as f:
                        f.write(f"# Aggregated Report\n\n{aggregate_report}")
                    
                    st.markdown(aggregate_report)
                    st.success(f"✅ Aggregate report saved to {report_path}")
        
        elif analysis_mode == "CrewAI Analysis (Beta)":
            st.header("🤖 CrewAI Analysis")
            st.info("CrewAI integration is currently in beta. Uncomment the CrewAI code to enable this feature.")
            
            if st.button("Run CrewAI Analysis", type="primary"):
                st.warning("Please install CrewAI and uncomment the integration code to use this feature.")
                # Uncomment below when CrewAI is available
                # with st.spinner("Running CrewAI analysis..."):
                #     file_paths = list(st.session_state.file_data.keys())
                #     result = run_crewai_analysis(file_paths)
                #     st.markdown(result)
        
        # Download section
        st.divider()
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("💾 Download Chat History"):
                if st.session_state.chat_history:
                    chat_md = "# Chat History\n\n"
                    for message in st.session_state.chat_history:
                        role = "User" if message["role"] == "user" else "Assistant"
                        chat_md += f"**{role}:** {message['content']}\n\n"
                    
                    st.download_button(
                        label="Download Chat History (Markdown)",
                        data=chat_md,
                        file_name=f"chat_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                        mime="text/markdown"
                    )
        
        with col2:
            if st.button("🗑️ Clear All Data"):
                st.session_state.file_data = {}
                st.session_state.chat_history = []
                st.session_state.analyses = {}
                st.rerun()
    
    else:
        st.info("👈 Please upload Excel files using the sidebar to begin analysis.")

if __name__ == "__main__":
    main()