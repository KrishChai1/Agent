import os
import streamlit as st
import pandas as pd
import yaml
from openai import OpenAI
from datetime import datetime
from typing import Dict, List, Any
import plotly.express as px
import plotly.graph_objects as go
from collections import Counter
import re
import json

# Page config
st.set_page_config(
    page_title="Hypercare Excel Analyzer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .priority-high {
        background-color: #ffcccc;
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
    }
    .priority-medium {
        background-color: #fff3cd;
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
    }
    .priority-low {
        background-color: #d4edda;
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
    }
</style>
""", unsafe_allow_html=True)

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
        'root_cause': ['Root Cause', 'root cause', 'Cause', 'Root cause'],
        'priority': ['Priority', 'Severity', 'priority'],
        'date': ['Date', 'Created', 'Updated', 'Timestamp']
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
    
    # Get root causes if available
    if 'root_cause' in found_cols:
        root_causes = df[found_cols['root_cause']].dropna().astype(str)
        # Extract patterns
        patterns = {}
        keywords = ['configuration', 'network', 'database', 'permission', 'timeout', 
                   'memory', 'integration', 'api', 'authentication', 'sync']
        
        for keyword in keywords:
            count = sum(1 for cause in root_causes if keyword.lower() in cause.lower())
            if count > 0:
                patterns[keyword] = count
        
        metrics['root_cause_patterns'] = patterns
        metrics['total_root_causes'] = len(root_causes)
    
    return metrics, found_cols

def analyze_root_causes(client, filename, df, query):
    """Analyze file with focus on root causes"""
    if not client:
        return "OpenAI client not initialized"
    
    # Get metrics
    metrics, found_cols = extract_metrics(df)
    
    # Focus on root causes
    root_cause_info = ""
    if 'root_cause' in found_cols:
        root_causes = df[found_cols['root_cause']].dropna().value_counts().head(10)
        root_cause_info = f"\nTop Root Causes:\n{root_causes.to_string()}\n"
    
    # Create context
    context = f"""
File: {filename}
Total Issues: {metrics['total_rows']}
Columns: {', '.join(metrics['columns'])}
{root_cause_info}
"""
    
    # Sample data
    sample = df.head(10).to_string()
    
    prompt = f"""
Analyze this hypercare issue data with FOCUS ON ROOT CAUSES.

Context:
{context}

Data sample:
{sample}

User question: {query}

Provide analysis that MUST include:
1. Direct answer focusing on ROOT CAUSES
2. Pattern analysis of root causes
3. Most critical root causes that need immediate attention
4. Specific recommendations to prevent these root causes
5. Correlation between issues and their root causes

If the data contains root cause information, prioritize explaining:
- What are the main root causes
- Which root causes are most frequent
- Which root causes have the highest impact
- How to prevent these root causes
"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a root cause analysis expert specializing in IT operations. Focus heavily on identifying and explaining root causes."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,
            temperature=0.2
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error: {str(e)}"

def prioritize_new_ticket(client, ticket_description, historical_data):
    """Prioritize a new ticket based on historical data"""
    if not client:
        return None
    
    # Analyze historical patterns
    all_issues = []
    all_root_causes = []
    
    for df in historical_data.values():
        metrics, found_cols = extract_metrics(df)
        if 'issue' in found_cols:
            all_issues.extend(df[found_cols['issue']].dropna().tolist())
        if 'root_cause' in found_cols:
            all_root_causes.extend(df[found_cols['root_cause']].dropna().tolist())
    
    context = f"""
Historical data summary:
- Total historical issues: {len(all_issues)}
- Total root causes identified: {len(all_root_causes)}
- Common patterns: configuration issues, network problems, permission errors, timeout issues
"""
    
    prompt = f"""
Analyze this new IT support ticket and provide prioritization based on historical data.

New Ticket: {ticket_description}

{context}

Provide a structured analysis with:
1. **Priority Level**: HIGH/MEDIUM/LOW with justification
2. **Likely Root Cause**: Based on similar historical issues
3. **Immediate Actions**: Step-by-step actions to take right now
4. **Investigation Steps**: Ordered list of things to check
5. **Preventive Measures**: How to prevent this in the future
6. **Estimated Resolution Time**: Based on similar past issues
7. **Resources Needed**: Teams or people to involve

Format as a clear, actionable plan.
"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an IT operations expert who prioritizes and resolves issues efficiently."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,
            temperature=0.2
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error: {str(e)}"

def generate_insights_report(file_data):
    """Generate downloadable insights report"""
    report = f"# Hypercare Insights Report\n\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    total_issues = 0
    all_clients = set()
    all_root_causes = []
    
    for filename, df in file_data.items():
        metrics, found_cols = extract_metrics(df)
        total_issues += metrics['total_rows']
        
        report += f"\n## File: {filename}\n"
        report += f"- Total Issues: {metrics['total_rows']}\n"
        
        if 'unique_clients' in metrics:
            report += f"- Unique Clients: {metrics['unique_clients']}\n"
            all_clients.update(metrics.get('top_clients', {}).keys())
        
        if 'root_cause_patterns' in metrics:
            report += f"- Root Cause Patterns:\n"
            for pattern, count in metrics['root_cause_patterns'].items():
                report += f"  - {pattern}: {count} occurrences\n"
        
        if 'root_cause' in found_cols:
            root_causes = df[found_cols['root_cause']].dropna()
            all_root_causes.extend(root_causes.tolist())
    
    # Summary section
    report += f"\n## Overall Summary\n"
    report += f"- Total Files Analyzed: {len(file_data)}\n"
    report += f"- Total Issues: {total_issues}\n"
    report += f"- Total Unique Clients: {len(all_clients)}\n"
    
    # Top root causes
    if all_root_causes:
        root_cause_counts = Counter(all_root_causes)
        report += f"\n## Top 10 Root Causes\n"
        for cause, count in root_cause_counts.most_common(10):
            report += f"- {cause}: {count} occurrences\n"
    
    return report

def create_visualizations(df, found_cols):
    """Create enhanced visualizations"""
    charts = []
    
    if 'client' in found_cols:
        client_counts = df[found_cols['client']].value_counts().head(10)
        fig = px.bar(
            x=client_counts.values,
            y=client_counts.index,
            orientation='h',
            title="Top 10 Clients by Issue Count",
            labels={'x': 'Number of Issues', 'y': 'Client'},
            color=client_counts.values,
            color_continuous_scale='Reds'
        )
        charts.append(fig)
    
    if 'status' in found_cols:
        status_counts = df[found_cols['status']].value_counts()
        fig = px.pie(
            values=status_counts.values,
            names=status_counts.index,
            title="Issue Status Distribution",
            hole=0.4
        )
        charts.append(fig)
    
    if 'root_cause' in found_cols:
        # Word frequency in root causes
        root_causes = df[found_cols['root_cause']].dropna().astype(str)
        words = []
        for cause in root_causes:
            words.extend(re.findall(r'\b\w+\b', cause.lower()))
        
        word_freq = Counter([w for w in words if len(w) > 4])
        top_words = word_freq.most_common(15)
        
        if top_words:
            fig = px.bar(
                x=[w[1] for w in top_words],
                y=[w[0] for w in top_words],
                orientation='h',
                title="Most Common Words in Root Causes",
                labels={'x': 'Frequency', 'y': 'Word'}
            )
            charts.append(fig)
    
    return charts

# Main app
def main():
    st.title("📊 Hypercare Excel Analyzer")
    st.markdown("AI-powered analysis for Excel files with root cause focus and ticket prioritization")
    
    # Get OpenAI client
    client = get_openai_client()
    if not client:
        st.stop()
    
    # Initialize session state
    if 'files' not in st.session_state:
        st.session_state.files = {}
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    if 'insights' not in st.session_state:
        st.session_state.insights = []
    if 'ticket_analyses' not in st.session_state:
        st.session_state.ticket_analyses = []
    
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
                st.session_state.insights = []
                st.session_state.ticket_analyses = []
                st.rerun()
    
    # Main content
    if st.session_state.files:
        tabs = st.tabs(["📈 Dashboard", "💬 Root Cause Chat", "📊 Visualizations", "🎫 New Ticket Priority", "🤖 Advanced"])
        
        with tabs[0]:  # Dashboard
            st.header("Overview Dashboard")
            
            # Metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Files", len(st.session_state.files))
            with col2:
                total_rows = sum(len(df) for df in st.session_state.files.values())
                st.metric("Total Issues", total_rows)
            with col3:
                # Count root causes
                root_cause_count = 0
                for df in st.session_state.files.values():
                    _, found_cols = extract_metrics(df)
                    if 'root_cause' in found_cols:
                        root_cause_count += df[found_cols['root_cause']].notna().sum()
                st.metric("Root Causes Found", root_cause_count)
            with col4:
                st.metric("Status", "✅ Ready")
            
            # File details with insights
            st.subheader("File Analysis & Insights")
            
            insights_data = []
            for name, df in st.session_state.files.items():
                metrics, found_cols = extract_metrics(df)
                
                insight = {
                    "File": name,
                    "Issues": metrics['total_rows'],
                    "Clients": metrics.get('unique_clients', 'N/A'),
                }
                
                # Add top root cause if available
                if 'root_cause_patterns' in metrics and metrics['root_cause_patterns']:
                    top_pattern = max(metrics['root_cause_patterns'].items(), key=lambda x: x[1])
                    insight["Top Root Cause Pattern"] = f"{top_pattern[0]} ({top_pattern[1]})"
                else:
                    insight["Top Root Cause Pattern"] = "N/A"
                
                insights_data.append(insight)
            
            df_insights = pd.DataFrame(insights_data)
            st.dataframe(df_insights, use_container_width=True)
            
            # Generate and download insights
            col1, col2 = st.columns([3, 1])
            with col1:
                if st.button("🔍 Generate Detailed Insights"):
                    with st.spinner("Analyzing all files..."):
                        # Generate insights
                        st.session_state.insights = []
                        for name, df in st.session_state.files.items():
                            metrics, found_cols = extract_metrics(df)
                            
                            if 'root_cause_patterns' in metrics:
                                for pattern, count in sorted(metrics['root_cause_patterns'].items(), 
                                                           key=lambda x: x[1], reverse=True)[:3]:
                                    st.session_state.insights.append(
                                        f"**{name}**: {pattern} issues found {count} times"
                                    )
                            
                            if 'top_clients' in metrics and metrics['top_clients']:
                                top_client = list(metrics['top_clients'].items())[0]
                                st.session_state.insights.append(
                                    f"**{name}**: {top_client[0]} has {top_client[1]} issues"
                                )
                        
                        if st.session_state.insights:
                            st.subheader("Key Insights")
                            for insight in st.session_state.insights[:10]:
                                st.info(insight)
            
            with col2:
                # Download insights button
                if st.session_state.files:
                    report = generate_insights_report(st.session_state.files)
                    st.download_button(
                        "📥 Download Report",
                        data=report,
                        file_name=f"insights_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                        mime="text/markdown",
                        use_container_width=True
                    )
        
        with tabs[1]:  # Root Cause Chat
            st.header("Root Cause Analysis Chat")
            st.markdown("Ask questions to understand root causes and patterns in your data")
            
            # Predefined questions
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("🔍 What are the top root causes?"):
                    query = "What are the most common root causes across all files?"
                    st.session_state.chat_query = query
            with col2:
                if st.button("⚡ Which issues are critical?"):
                    query = "Which root causes are most critical and need immediate attention?"
                    st.session_state.chat_query = query
            with col3:
                if st.button("🛡️ How to prevent issues?"):
                    query = "What are the best practices to prevent these root causes?"
                    st.session_state.chat_query = query
            
            # Query input
            query = st.text_input(
                "Ask about root causes:",
                placeholder="What are the root causes for configuration issues?",
                key="root_cause_query",
                value=st.session_state.get('chat_query', '')
            )
            
            col1, col2 = st.columns([6, 1])
            with col1:
                analyze_btn = st.button("🚀 Analyze Root Causes", type="primary")
            with col2:
                if st.button("🗑️ Clear"):
                    st.session_state.chat_history = []
                    st.rerun()
            
            if analyze_btn and query:
                st.session_state.chat_history.append({"role": "user", "content": query})
                
                with st.spinner("Analyzing root causes..."):
                    responses = []
                    for name, df in st.session_state.files.items():
                        response = analyze_root_causes(client, name, df, query)
                        responses.append(f"### 📄 {name}\n{response}")
                    
                    full_response = "\n\n---\n\n".join(responses)
                    st.session_state.chat_history.append({"role": "assistant", "content": full_response})
            
            # Display chat history
            for msg in st.session_state.chat_history:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
            
            # Download chat
            if st.session_state.chat_history:
                chat_text = "# Root Cause Analysis Chat\n\n"
                for msg in st.session_state.chat_history:
                    role = "User" if msg["role"] == "user" else "Assistant"
                    chat_text += f"## {role}:\n{msg['content']}\n\n"
                
                st.download_button(
                    "📥 Download Chat Analysis",
                    data=chat_text,
                    file_name=f"root_cause_chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                    mime="text/markdown"
                )
        
        with tabs[2]:  # Visualizations
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
        
        with tabs[3]:  # New Ticket Priority
            st.header("🎫 New Ticket Prioritization")
            st.markdown("Enter a new ticket description to get priority and next steps based on historical data")
            
            # Ticket input
            ticket_description = st.text_area(
                "New Ticket Description:",
                placeholder="User cannot access the system. Getting 'permission denied' error when trying to log in to the dashboard.",
                height=100
            )
            
            if st.button("🎯 Analyze & Prioritize Ticket", type="primary"):
                if ticket_description:
                    with st.spinner("Analyzing ticket based on historical patterns..."):
                        analysis = prioritize_new_ticket(client, ticket_description, st.session_state.files)
                        
                        if analysis:
                            # Store analysis
                            ticket_entry = {
                                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                "description": ticket_description,
                                "analysis": analysis
                            }
                            st.session_state.ticket_analyses.append(ticket_entry)
                            
                            # Display analysis
                            st.markdown("### 📋 Ticket Analysis & Next Steps")
                            st.markdown(analysis)
                            
                            # Download ticket analysis
                            ticket_report = f"# Ticket Analysis Report\n\nGenerated: {ticket_entry['timestamp']}\n\n"
                            ticket_report += f"## Ticket Description\n{ticket_description}\n\n"
                            ticket_report += f"## Analysis & Recommendations\n{analysis}"
                            
                            st.download_button(
                                "📥 Download Ticket Analysis",
                                data=ticket_report,
                                file_name=f"ticket_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                                mime="text/markdown"
                            )
                else:
                    st.warning("Please enter a ticket description")
            
            # Show recent ticket analyses
            if st.session_state.ticket_analyses:
                st.divider()
                st.subheader("Recent Ticket Analyses")
                
                for i, ticket in enumerate(reversed(st.session_state.ticket_analyses[-5:])):
                    with st.expander(f"Ticket from {ticket['timestamp']}"):
                        st.text(f"Description: {ticket['description'][:100]}...")
                        st.markdown(ticket['analysis'])
        
        with tabs[4]:  # Advanced
            st.header("Advanced Analysis")
            
            if st.button("🔬 Generate Comprehensive Report", type="primary"):
                with st.spinner("Generating comprehensive analysis..."):
                    # Create comprehensive report focusing on root causes
                    report = "# Comprehensive Hypercare Analysis Report\n\n"
                    report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    
                    # Executive Summary
                    total_issues = sum(len(df) for df in st.session_state.files.values())
                    report += f"## Executive Summary\n"
                    report += f"- Analyzed {len(st.session_state.files)} files with {total_issues} total issues\n"
                    
                    # Root Cause Analysis
                    all_root_causes = []
                    for df in st.session_state.files.values():
                        _, found_cols = extract_metrics(df)
                        if 'root_cause' in found_cols:
                            all_root_causes.extend(df[found_cols['root_cause']].dropna().tolist())
                    
                    if all_root_causes:
                        root_cause_freq = Counter(all_root_causes)
                        report += f"\n## Top Root Causes\n"
                        for cause, count in root_cause_freq.most_common(10):
                            percentage = (count / len(all_root_causes)) * 100
                            report += f"- {cause}: {count} occurrences ({percentage:.1f}%)\n"
                    
                    # Pattern Analysis
                    report += f"\n## Pattern Analysis\n"
                    patterns = ['configuration', 'network', 'permission', 'database', 'timeout']
                    for pattern in patterns:
                        count = sum(1 for cause in all_root_causes if pattern in str(cause).lower())
                        if count > 0:
                            report += f"- {pattern.capitalize()} related issues: {count}\n"
                    
                    # Recommendations
                    report += f"\n## Recommendations\n"
                    report += "1. **Immediate Actions**: Address top 3 root causes first\n"
                    report += "2. **Process Improvements**: Implement automated checks for common issues\n"
                    report += "3. **Training**: Focus team training on preventing top root causes\n"
                    report += "4. **Monitoring**: Set up alerts for patterns identified\n"
                    
                    st.markdown(report)
                    
                    # Download button
                    st.download_button(
                        "📥 Download Comprehensive Report",
                        data=report,
                        file_name=f"comprehensive_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                        mime="text/markdown"
                    )
    
    else:
        # Welcome screen
        st.info("👈 Upload Excel files to get started")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            with st.expander("📖 How to Use This App"):
                st.markdown("""
                ### Getting Started:
                1. **Upload Files**: Use sidebar to upload Excel files with hypercare issues
                2. **Dashboard**: View insights and download reports
                3. **Root Cause Chat**: Ask questions about root causes
                4. **Ticket Priority**: Get instant analysis for new tickets
                5. **Visualizations**: See patterns in your data
                
                ### Expected Columns:
                - Client/Customer
                - Issue Description
                - Status
                - **Root Cause** (important!)
                - Priority/Severity
                - Date/Timestamp
                """)
        
        with col2:
            st.markdown("### ✨ Key Features")
            st.markdown("""
            - 🔍 Root cause analysis
            - 🎫 Ticket prioritization
            - 📊 Auto visualizations
            - 💬 AI-powered chat
            - 📥 Downloadable reports
            - 🎯 Actionable insights
            """)

if __name__ == "__main__":
    main()
