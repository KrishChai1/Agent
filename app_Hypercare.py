import os
import streamlit as st
import pandas as pd
import yaml
from openai import OpenAI
from datetime import datetime
from typing import Dict, List, Any
import plotly.express as px
from collections import Counter
import re

# Page config
st.set_page_config(
    page_title="Hypercare Excel Analyzer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize directories
ANALYSIS_DIR = 'analysis'
os.makedirs(ANALYSIS_DIR, exist_ok=True)

# Initialize OpenAI client
@st.cache_resource
def get_openai_client():
    """Initialize OpenAI client with API key from Streamlit secrets"""
    if 'OPENAI_API_KEY' in st.secrets:
        return OpenAI(api_key=st.secrets['OPENAI_API_KEY'])
    else:
        st.error("Please add your OpenAI API key to Streamlit secrets")
        st.info("Add OPENAI_API_KEY = 'your-key' to .streamlit/secrets.toml")
        return None

# Load YAML configs
@st.cache_resource
def load_yaml(filename):
    """Load YAML configuration files"""
    try:
        with open(filename, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return None

# Excel processing functions
def read_excel_file(file):
    """Read Excel file and return DataFrame"""
    try:
        df = pd.read_excel(file)
        df.columns = df.columns.str.strip()
        return df, None
    except Exception as e:
        return None, str(e)

def extract_metrics(df):
    """Extract basic metrics from dataframe"""
    metrics = {
        'total_rows': len(df),
        'total_columns': len(df.columns),
        'columns': list(df.columns)
    }
    
    # Find common columns
    col_mappings = {
        'client': ['Client', 'client', 'Customer', 'Company'],
        'issue': ['Issue Description', 'Issue', 'Description'],
        'status': ['Status', 'State', 'Resolution'],
        'root_cause': ['Root Cause', 'Cause']
    }
    
    found_cols = {}
    for key, possible_names in col_mappings.items():
        for col in df.columns:
            if col in possible_names:
                found_cols[key] = col
                break
    
    # Get client counts if available
    if 'client' in found_cols:
        metrics['unique_clients'] = df[found_cols['client']].nunique()
        metrics['top_clients'] = df[found_cols['client']].value_counts().head(5).to_dict()
    
    return metrics, found_cols

def analyze_with_ai(client, filename, df, query):
    """Analyze file with OpenAI using new API"""
    if not client:
        return "OpenAI client not initialized"
    
    # Get basic info
    metrics, _ = extract_metrics(df)
    
    # Create context
    context = f"""
File: {filename}
Rows: {metrics['total_rows']}
Columns: {', '.join(metrics['columns'])}
"""
    
    # Sample data
    sample = df.head(10).to_string()
    
    prompt = f"""
Analyze this Excel file data and answer the user's question.

Context:
{context}

Data sample:
{sample}

User question: {query}

Provide a clear, detailed answer focusing on:
1. Direct answer to the question
2. Key patterns or insights
3. Specific recommendations
"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a data analyst expert."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=800,
            temperature=0.2
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error: {str(e)}"

def create_comprehensive_report(client, file_data):
    """Generate comprehensive analysis report"""
    if not client:
        return "OpenAI client not initialized"
    
    # Collect metrics from all files
    all_metrics = []
    for filename, df in file_data.items():
        metrics, _ = extract_metrics(df)
        metrics['filename'] = filename
        all_metrics.append(metrics)
    
    # Create summary
    total_issues = sum(m['total_rows'] for m in all_metrics)
    total_files = len(file_data)
    
    context = f"""
Analyzing {total_files} Excel files with {total_issues} total issues.

Files analyzed:
"""
    for m in all_metrics:
        context += f"\n- {m['filename']}: {m['total_rows']} rows, {m['total_columns']} columns"
    
    prompt = f"""
Based on the analysis of multiple Excel files containing IT hypercare issues, provide a comprehensive report.

{context}

Please provide:
1. Executive Summary (2-3 sentences)
2. Key Findings across all files
3. Common patterns and trends
4. Root cause analysis
5. Risk assessment
6. Prioritized recommendations
7. Next steps

Format the response in clear markdown with headers.
"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an IT operations expert providing executive-level analysis."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1500,
            temperature=0.3
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error generating report: {str(e)}"

def create_visualizations(df, found_cols):
    """Create simple visualizations"""
    charts = []
    
    if 'client' in found_cols:
        client_counts = df[found_cols['client']].value_counts().head(10)
        fig = px.bar(
            x=client_counts.values,
            y=client_counts.index,
            orientation='h',
            title="Top 10 Clients by Issue Count",
            labels={'x': 'Number of Issues', 'y': 'Client'}
        )
        charts.append(fig)
    
    if 'status' in found_cols:
        status_counts = df[found_cols['status']].value_counts()
        fig = px.pie(
            values=status_counts.values,
            names=status_counts.index,
            title="Issue Status Distribution"
        )
        charts.append(fig)
    
    return charts

# Main app
def main():
    st.title("📊 Hypercare Excel Analyzer")
    st.markdown("AI-powered analysis for Excel files")
    
    # Get OpenAI client
    client = get_openai_client()
    if not client:
        st.stop()
    
    # Initialize session state
    if 'files' not in st.session_state:
        st.session_state.files = {}
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    if 'analyses' not in st.session_state:
        st.session_state.analyses = {}
    
    # Sidebar
    with st.sidebar:
        st.header("📁 File Upload")
        
        uploaded_files = st.file_uploader(
            "Upload Excel Files",
            type=['xlsx', 'xls'],
            accept_multiple_files=True
        )
        
        if uploaded_files:
            if st.button("Process Files", type="primary"):
                progress = st.progress(0)
                for i, file in enumerate(uploaded_files):
                    progress.progress((i + 1) / len(uploaded_files))
                    df, error = read_excel_file(file)
                    if df is not None:
                        st.session_state.files[file.name] = df
                        st.success(f"✓ {file.name}")
                    else:
                        st.error(f"✗ {file.name}: {error}")
                progress.empty()
        
        if st.session_state.files:
            st.divider()
            st.header("Loaded Files")
            for name in st.session_state.files:
                st.text(f"• {name}")
            
            if st.button("Clear All"):
                st.session_state.files = {}
                st.session_state.chat_history = []
                st.session_state.analyses = {}
                st.rerun()
        
        # Load YAML configs
        st.divider()
        st.header("Configuration")
        configs = {
            "agents.yaml": load_yaml('agents.yaml'),
            "tasks.yaml": load_yaml('tasks.yaml'),
            "crew.yaml": load_yaml('crew.yaml')
        }
        for name, config in configs.items():
            if config:
                st.success(f"✓ {name}")
            else:
                st.warning(f"✗ {name} (optional)")
    
    # Main content
    if st.session_state.files:
        tab1, tab2, tab3, tab4 = st.tabs(["📈 Dashboard", "💬 Chat", "📊 Visualizations", "🤖 Advanced"])
        
        with tab1:
            st.header("Overview")
            
            # Metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Files", len(st.session_state.files))
            with col2:
                total_rows = sum(len(df) for df in st.session_state.files.values())
                st.metric("Total Issues", total_rows)
            with col3:
                avg_rows = total_rows // len(st.session_state.files) if st.session_state.files else 0
                st.metric("Avg Issues/File", avg_rows)
            with col4:
                st.metric("Status", "✅ Ready")
            
            # File details
            st.subheader("File Details")
            details = []
            for name, df in st.session_state.files.items():
                metrics, _ = extract_metrics(df)
                details.append({
                    "File": name,
                    "Rows": metrics['total_rows'],
                    "Columns": metrics['total_columns'],
                    "Clients": metrics.get('unique_clients', 'N/A')
                })
            
            df_details = pd.DataFrame(details)
            st.dataframe(df_details, use_container_width=True)
            
            # Quick insights
            if st.button("🔍 Generate Quick Insights"):
                with st.spinner("Analyzing..."):
                    insights = []
                    for name, df in st.session_state.files.items():
                        metrics, found_cols = extract_metrics(df)
                        if 'unique_clients' in metrics:
                            insights.append(f"**{name}**: {metrics['unique_clients']} unique clients")
                        if 'top_clients' in metrics and metrics['top_clients']:
                            top_client = list(metrics['top_clients'].keys())[0]
                            count = metrics['top_clients'][top_client]
                            insights.append(f"**{name}**: Top client is {top_client} with {count} issues")
                    
                    if insights:
                        st.subheader("Quick Insights")
                        for insight in insights[:5]:
                            st.info(insight)
        
        with tab2:
            st.header("Chat Analysis")
            st.markdown("Ask questions about your data and get AI-powered insights")
            
            # Query input
            query = st.text_input(
                "Ask a question:",
                placeholder="What are the most common issues across all files?",
                key="chat_query"
            )
            
            col1, col2 = st.columns([6, 1])
            with col1:
                analyze_btn = st.button("🚀 Analyze", type="primary")
            with col2:
                if st.button("🗑️ Clear"):
                    st.session_state.chat_history = []
                    st.rerun()
            
            if analyze_btn and query:
                st.session_state.chat_history.append({"role": "user", "content": query})
                
                with st.spinner("Analyzing your data..."):
                    responses = []
                    for name, df in st.session_state.files.items():
                        response = analyze_with_ai(client, name, df, query)
                        responses.append(f"### 📄 {name}\n{response}")
                    
                    full_response = "\n\n---\n\n".join(responses)
                    st.session_state.chat_history.append({"role": "assistant", "content": full_response})
            
            # Display chat history
            for msg in st.session_state.chat_history:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
            
            # Download chat
            if st.session_state.chat_history:
                chat_text = "\n\n".join([
                    f"{'User' if msg['role'] == 'user' else 'Assistant'}: {msg['content']}"
                    for msg in st.session_state.chat_history
                ])
                st.download_button(
                    "📥 Download Chat",
                    data=chat_text,
                    file_name=f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    mime="text/plain"
                )
        
        with tab3:
            st.header("Data Visualizations")
            
            file_choice = st.selectbox(
                "Select file to visualize:",
                list(st.session_state.files.keys())
            )
            
            if file_choice:
                df = st.session_state.files[file_choice]
                _, found_cols = extract_metrics(df)
                charts = create_visualizations(df, found_cols)
                
                if charts:
                    for chart in charts:
                        st.plotly_chart(chart, use_container_width=True)
                else:
                    st.info("No suitable columns found for visualization")
                
                with st.expander("📋 View Raw Data"):
                    st.dataframe(df, use_container_width=True)
        
        with tab4:
            st.header("Advanced Analysis")
            
            if st.button("🔬 Generate Comprehensive Report", type="primary"):
                with st.spinner("Generating comprehensive analysis..."):
                    report = create_comprehensive_report(client, st.session_state.files)
                    
                    st.markdown(report)
                    
                    # Save and download
                    report_with_header = f"# Comprehensive Analysis Report\n\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n{report}"
                    
                    st.download_button(
                        "📥 Download Report",
                        data=report_with_header,
                        file_name=f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                        mime="text/markdown"
                    )
            
            st.divider()
            
            # CrewAI placeholder
            st.subheader("🤖 CrewAI Multi-Agent Analysis")
            st.info("CrewAI integration allows multiple AI agents to collaborate on analyzing your data.")
            
            with st.expander("Setup Instructions"):
                st.markdown("""
                To enable CrewAI:
                1. Install: `pip install crewai`
                2. Import the crewai_integration module
                3. Configure agents in agents.yaml
                4. Run multi-agent analysis
                """)
    
    else:
        # Welcome screen
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.info("👈 Upload Excel files to get started")
            
            with st.expander("📖 Instructions"):
                st.markdown("""
                ### How to use:
                1. **Upload Files**: Use the sidebar to upload Excel files
                2. **Process**: Click 'Process Files' to load your data
                3. **Analyze**: Ask questions in the Chat tab
                4. **Visualize**: View automatic charts
                5. **Report**: Generate comprehensive reports
                
                ### Expected columns:
                - Client/Customer
                - Issue Description
                - Status
                - Root Cause
                - Date/Timestamp
                """)
        
        with col2:
            st.markdown("### Features")
            st.markdown("""
            - ✅ Multi-file analysis
            - ✅ AI-powered insights
            - ✅ Auto visualizations
            - ✅ Export reports
            - ✅ Chat interface
            """)

if __name__ == "__main__":
    main()
