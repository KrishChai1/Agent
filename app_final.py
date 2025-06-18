import streamlit as st
import pandas as pd
import datetime
from io import BytesIO
import json
from typing import Dict, List, Optional
import base64

# Page configuration
st.set_page_config(
    page_title="LawTrax - RFE Response Management",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #1f4e79 0%, #2d5aa0 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .case-card {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #007bff;
        margin: 1rem 0;
    }
    .status-active {
        background-color: #d4edda;
        color: #155724;
        padding: 0.25rem 0.5rem;
        border-radius: 4px;
        font-size: 0.875rem;
    }
    .status-pending {
        background-color: #fff3cd;
        color: #856404;
        padding: 0.25rem 0.5rem;
        border-radius: 4px;
        font-size: 0.875rem;
    }
    .status-urgent {
        background-color: #f8d7da;
        color: #721c24;
        padding: 0.25rem 0.5rem;
        border-radius: 4px;
        font-size: 0.875rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'cases' not in st.session_state:
    st.session_state.cases = []
if 'current_case' not in st.session_state:
    st.session_state.current_case = None
if 'documents' not in st.session_state:
    st.session_state.documents = {}

# Visa types and categories
VISA_TYPES = {
    "H-1B": "Specialty Occupation Workers",
    "H-1B1": "Free Trade Agreement Professionals",
    "L-1A": "Intracompany Transferee Executive/Manager",
    "L-1B": "Intracompany Transferee Specialized Knowledge",
    "O-1A": "Extraordinary Ability in Sciences/Arts/Education/Business",
    "O-1B": "Extraordinary Ability in Arts/Motion Pictures",
    "EB-1A": "Extraordinary Ability (Employment-Based)",
    "EB-1B": "Outstanding Professor/Researcher",
    "EB-1C": "Multinational Executive/Manager",
    "EB-2": "Advanced Degree/Exceptional Ability",
    "EB-3": "Skilled Worker/Professional",
    "EB-5": "Immigrant Investor",
    "F-1": "Student Visa",
    "J-1": "Exchange Visitor",
    "B-1/B-2": "Business/Tourism",
    "K-1": "Fiancé(e) Visa",
    "CR-1/IR-1": "Spouse of US Citizen"
}

# Common RFE categories by visa type
RFE_CATEGORIES = {
    "H-1B": [
        "Specialty Occupation Requirements",
        "Employer-Employee Relationship",
        "Beneficiary Qualifications",
        "Wage Requirements",
        "Itinerary/Work Location",
        "Supporting Documentation"
    ],
    "L-1A": [
        "Managerial/Executive Capacity",
        "Qualifying Relationship",
        "New Office Requirements",
        "Employment Duration",
        "Financial Capacity"
    ],
    "L-1B": [
        "Specialized Knowledge",
        "Qualifying Relationship",
        "Position Requirements",
        "Training/Experience",
        "Knowledge Transfer"
    ],
    "O-1A": [
        "Extraordinary Ability Evidence",
        "Sustained Recognition",
        "Critical Role Evidence",
        "Consultation Requirements",
        "Itinerary"
    ],
    "EB-1A": [
        "Extraordinary Ability Criteria",
        "Sustained National/International Acclaim",
        "Original Contributions",
        "Leadership Role",
        "Published Material"
    ],
    "EB-2": [
        "Advanced Degree Evidence",
        "Exceptional Ability",
        "Job Offer Requirements",
        "Labor Certification",
        "National Interest Waiver"
    ]
}

def main():
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>⚖️ LawTrax - RFE Response Management System</h1>
        <p>Comprehensive Immigration Case Management Platform</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.selectbox(
        "Select Page",
        ["Dashboard", "New RFE Case", "Case Management", "Document Library", "Response Generator", "Analytics"]
    )
    
    if page == "Dashboard":
        show_dashboard()
    elif page == "New RFE Case":
        create_new_case()
    elif page == "Case Management":
        manage_cases()
    elif page == "Document Library":
        document_library()
    elif page == "Response Generator":
        response_generator()
    elif page == "Analytics":
        show_analytics()

def show_dashboard():
    st.header("📊 Dashboard")
    
    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Cases", len(st.session_state.cases))
    
    with col2:
        active_cases = len([c for c in st.session_state.cases if c.get('status') == 'Active'])
        st.metric("Active Cases", active_cases)
    
    with col3:
        pending_cases = len([c for c in st.session_state.cases if c.get('status') == 'Pending Review'])
        st.metric("Pending Review", pending_cases)
    
    with col4:
        urgent_cases = len([c for c in st.session_state.cases if c.get('priority') == 'High'])
        st.metric("High Priority", urgent_cases)
    
    # Recent cases
    st.subheader("Recent Cases")
    if st.session_state.cases:
        recent_cases = sorted(st.session_state.cases, key=lambda x: x['created_date'], reverse=True)[:5]
        for case in recent_cases:
            display_case_card(case)
    else:
        st.info("No cases found. Create your first RFE case to get started!")

def create_new_case():
    st.header("📝 Create New RFE Case")
    
    with st.form("new_case_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            case_number = st.text_input("Case Number", placeholder="e.g., MSC2190123456")
            client_name = st.text_input("Client Name", placeholder="Full Name")
            visa_type = st.selectbox("Visa Type", list(VISA_TYPES.keys()))
            priority = st.selectbox("Priority Level", ["Low", "Medium", "High"])
        
        with col2:
            rfe_received_date = st.date_input("RFE Received Date", datetime.date.today())
            response_due_date = st.date_input("Response Due Date")
            uscis_office = st.text_input("USCIS Office", placeholder="e.g., California Service Center")
            attorney = st.text_input("Assigned Attorney")
        
        st.subheader("RFE Details")
        
        if visa_type and visa_type in RFE_CATEGORIES:
            rfe_categories = st.multiselect(
                "RFE Categories",
                RFE_CATEGORIES[visa_type],
                help="Select all applicable RFE categories"
            )
        else:
            rfe_categories = st.text_area("RFE Categories", placeholder="Enter RFE categories...")
        
        rfe_summary = st.text_area(
            "RFE Summary",
            placeholder="Provide a detailed summary of the RFE request...",
            height=150
        )
        
        uploaded_rfe = st.file_uploader(
            "Upload RFE Document",
            type=['pdf', 'doc', 'docx'],
            help="Upload the original RFE document"
        )
        
        submitted = st.form_submit_button("Create Case", type="primary")
        
        if submitted:
            if case_number and client_name and visa_type:
                new_case = {
                    'id': len(st.session_state.cases) + 1,
                    'case_number': case_number,
                    'client_name': client_name,
                    'visa_type': visa_type,
                    'visa_description': VISA_TYPES[visa_type],
                    'priority': priority,
                    'rfe_received_date': rfe_received_date.isoformat(),
                    'response_due_date': response_due_date.isoformat(),
                    'uscis_office': uscis_office,
                    'attorney': attorney,
                    'rfe_categories': rfe_categories,
                    'rfe_summary': rfe_summary,
                    'status': 'Active',
                    'created_date': datetime.datetime.now().isoformat(),
                    'documents': [],
                    'notes': []
                }
                
                if uploaded_rfe:
                    # Store uploaded file
                    file_data = {
                        'name': uploaded_rfe.name,
                        'type': uploaded_rfe.type,
                        'size': uploaded_rfe.size,
                        'data': base64.b64encode(uploaded_rfe.read()).decode()
                    }
                    new_case['rfe_document'] = file_data
                
                st.session_state.cases.append(new_case)
                st.success(f"Case {case_number} created successfully!")
                st.rerun()
            else:
                st.error("Please fill in all required fields.")

def manage_cases():
    st.header("📋 Case Management")
    
    if not st.session_state.cases:
        st.info("No cases found. Create your first case to get started!")
        return
    
    # Filters
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        status_filter = st.selectbox("Filter by Status", ["All", "Active", "Pending Review", "Completed", "On Hold"])
    with col2:
        visa_filter = st.selectbox("Filter by Visa Type", ["All"] + list(VISA_TYPES.keys()))
    with col3:
        priority_filter = st.selectbox("Filter by Priority", ["All", "High", "Medium", "Low"])
    with col4:
        attorney_filter = st.selectbox("Filter by Attorney", ["All"] + list(set([c.get('attorney', '') for c in st.session_state.cases if c.get('attorney')])))
    
    # Apply filters
    filtered_cases = st.session_state.cases.copy()
    
    if status_filter != "All":
        filtered_cases = [c for c in filtered_cases if c.get('status') == status_filter]
    if visa_filter != "All":
        filtered_cases = [c for c in filtered_cases if c.get('visa_type') == visa_filter]
    if priority_filter != "All":
        filtered_cases = [c for c in filtered_cases if c.get('priority') == priority_filter]
    if attorney_filter != "All":
        filtered_cases = [c for c in filtered_cases if c.get('attorney') == attorney_filter]
    
    st.write(f"Found {len(filtered_cases)} case(s)")
    
    # Display cases
    for case in filtered_cases:
        with st.expander(f"📁 {case['case_number']} - {case['client_name']} ({case['visa_type']})"):
            display_case_details(case)

def display_case_card(case):
    status_class = f"status-{case.get('status', 'pending').lower().replace(' ', '-')}"
    
    st.markdown(f"""
    <div class="case-card">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <h4>{case['case_number']} - {case['client_name']}</h4>
                <p><strong>Visa Type:</strong> {case['visa_type']} | <strong>Priority:</strong> {case['priority']}</p>
                <p><strong>Due Date:</strong> {case['response_due_date']}</p>
            </div>
            <div>
                <span class="{status_class}">{case.get('status', 'Pending')}</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def display_case_details(case):
    col1, col2 = st.columns(2)
    
    with col1:
        st.write(f"**Case Number:** {case['case_number']}")
        st.write(f"**Client:** {case['client_name']}")
        st.write(f"**Visa Type:** {case['visa_type']} - {case['visa_description']}")
        st.write(f"**Priority:** {case['priority']}")
        st.write(f"**USCIS Office:** {case.get('uscis_office', 'N/A')}")
    
    with col2:
        st.write(f"**RFE Received:** {case['rfe_received_date']}")
        st.write(f"**Response Due:** {case['response_due_date']}")
        st.write(f"**Status:** {case.get('status', 'Active')}")
        st.write(f"**Attorney:** {case.get('attorney', 'N/A')}")
    
    if case.get('rfe_categories'):
        st.write("**RFE Categories:**")
        for category in case['rfe_categories']:
            st.write(f"• {category}")
    
    if case.get('rfe_summary'):
        st.write("**RFE Summary:**")
        st.write(case['rfe_summary'])
    
    # Action buttons
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button(f"Edit Case {case['id']}", key=f"edit_{case['id']}"):
            st.session_state.current_case = case
    with col2:
        if st.button(f"Add Documents {case['id']}", key=f"docs_{case['id']}"):
            st.session_state.current_case = case
    with col3:
        new_status = st.selectbox(
            "Update Status",
            ["Active", "Pending Review", "Completed", "On Hold"],
            index=["Active", "Pending Review", "Completed", "On Hold"].index(case.get('status', 'Active')),
            key=f"status_{case['id']}"
        )
        if new_status != case.get('status'):
            case['status'] = new_status
            st.success("Status updated!")
    with col4:
        if st.button(f"Delete {case['id']}", key=f"delete_{case['id']}", type="secondary"):
            st.session_state.cases = [c for c in st.session_state.cases if c['id'] != case['id']]
            st.success("Case deleted!")
            st.rerun()

def document_library():
    st.header("📚 Document Library")
    
    if st.session_state.current_case:
        st.subheader(f"Documents for Case: {st.session_state.current_case['case_number']}")
    
    # Document upload
    st.subheader("Upload New Document")
    uploaded_file = st.file_uploader(
        "Choose file",
        type=['pdf', 'doc', 'docx', 'jpg', 'png', 'txt'],
        key="doc_upload"
    )
    
    if uploaded_file:
        col1, col2 = st.columns(2)
        with col1:
            doc_category = st.selectbox(
                "Document Category",
                ["RFE Response", "Supporting Evidence", "Legal Memo", "Client Communication", "USCIS Correspondence", "Other"]
            )
        with col2:
            doc_description = st.text_input("Document Description")
        
        if st.button("Upload Document"):
            if st.session_state.current_case:
                file_data = {
                    'name': uploaded_file.name,
                    'type': uploaded_file.type,
                    'size': uploaded_file.size,
                    'category': doc_category,
                    'description': doc_description,
                    'upload_date': datetime.datetime.now().isoformat(),
                    'data': base64.b64encode(uploaded_file.read()).decode()
                }
                
                if 'documents' not in st.session_state.current_case:
                    st.session_state.current_case['documents'] = []
                
                st.session_state.current_case['documents'].append(file_data)
                st.success("Document uploaded successfully!")
            else:
                st.error("Please select a case first from Case Management.")
    
    # Display documents
    if st.session_state.current_case and st.session_state.current_case.get('documents'):
        st.subheader("Uploaded Documents")
        for i, doc in enumerate(st.session_state.current_case['documents']):
            with st.expander(f"📄 {doc['name']} ({doc['category']})"):
                st.write(f"**Description:** {doc.get('description', 'N/A')}")
                st.write(f"**Size:** {doc['size']} bytes")
                st.write(f"**Upload Date:** {doc['upload_date']}")
                
                if st.button(f"Download {doc['name']}", key=f"download_{i}"):
                    file_data = base64.b64decode(doc['data'])
                    st.download_button(
                        label="Click to Download",
                        data=file_data,
                        file_name=doc['name'],
                        mime=doc['type']
                    )

def response_generator():
    st.header("✍️ RFE Response Generator")
    
    if not st.session_state.current_case:
        st.warning("Please select a case from Case Management first.")
        return
    
    case = st.session_state.current_case
    st.subheader(f"Generating Response for: {case['case_number']}")
    
    # Response template selection
    template_type = st.selectbox(
        "Select Response Template",
        ["Standard RFE Response", "Specialty Occupation (H-1B)", "Extraordinary Ability (O-1A)", "Managerial Capacity (L-1A)", "Custom Template"]
    )
    
    # Response sections
    st.subheader("Response Sections")
    
    # Introduction
    with st.expander("📝 Introduction", expanded=True):
        intro_text = st.text_area(
            "Introduction",
            value=f"""Dear USCIS Officer,

This letter responds to the Request for Further Evidence (RFE) dated {case['rfe_received_date']} regarding the {case['visa_type']} petition for {case['client_name']} (Receipt Number: {case['case_number']}).

We respectfully submit the following documentation and arguments to address the concerns raised in the RFE.""",
            height=150
        )
    
    # Address each RFE category
    if case.get('rfe_categories'):
        for category in case['rfe_categories']:
            with st.expander(f"📋 Response to: {category}"):
                response_text = st.text_area(
                    f"Response for {category}",
                    placeholder=f"Provide detailed response addressing {category}...",
                    height=200,
                    key=f"response_{category}"
                )
                
                # Evidence checklist
                st.write("**Evidence Submitted:**")
                evidence_items = st.text_area(
                    "Evidence List",
                    placeholder="List evidence documents for this section...",
                    key=f"evidence_{category}"
                )
    
    # Conclusion
    with st.expander("🎯 Conclusion"):
        conclusion_text = st.text_area(
            "Conclusion",
            value="""Based on the comprehensive evidence submitted, we respectfully request that USCIS approve the petition. The documentation clearly establishes that all regulatory requirements have been met.

We thank you for your consideration and look forward to a favorable decision.

Respectfully submitted,""",
            height=150
        )
    
    # Generate response
    if st.button("Generate Complete Response", type="primary"):
        complete_response = generate_complete_response(case, intro_text, conclusion_text)
        
        st.subheader("📄 Generated Response")
        st.text_area("Complete RFE Response", complete_response, height=400)
        
        # Download option
        st.download_button(
            label="Download Response as Text",
            data=complete_response,
            file_name=f"RFE_Response_{case['case_number']}.txt",
            mime="text/plain"
        )

def generate_complete_response(case, intro, conclusion):
    response = f"{intro}\n\n"
    
    if case.get('rfe_categories'):
        for i, category in enumerate(case['rfe_categories'], 1):
            response += f"{i}. RESPONSE TO: {category.upper()}\n\n"
            response += f"[Detailed response for {category} would be inserted here]\n\n"
    
    response += f"{conclusion}\n\n"
    response += f"Attorney Name\nBar Number\nFirm Name\nContact Information"
    
    return response

def show_analytics():
    st.header("📈 Analytics & Reports")
    
    if not st.session_state.cases:
        st.info("No data available for analytics. Create some cases first!")
        return
    
    # Case statistics
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Cases by Visa Type")
        visa_counts = {}
        for case in st.session_state.cases:
            visa_type = case['visa_type']
            visa_counts[visa_type] = visa_counts.get(visa_type, 0) + 1
        
        if visa_counts:
            df_visa = pd.DataFrame(list(visa_counts.items()), columns=['Visa Type', 'Count'])
            st.bar_chart(df_visa.set_index('Visa Type'))
    
    with col2:
        st.subheader("Cases by Status")
        status_counts = {}
        for case in st.session_state.cases:
            status = case.get('status', 'Unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
        
        if status_counts:
            df_status = pd.DataFrame(list(status_counts.items()), columns=['Status', 'Count'])
            st.bar_chart(df_status.set_index('Status'))
    
    # Priority distribution
    st.subheader("Priority Distribution")
    priority_counts = {}
    for case in st.session_state.cases:
        priority = case.get('priority', 'Unknown')
        priority_counts[priority] = priority_counts.get(priority, 0) + 1
    
    if priority_counts:
        df_priority = pd.DataFrame(list(priority_counts.items()), columns=['Priority', 'Count'])
        st.bar_chart(df_priority.set_index('Priority'))
    
    # Upcoming deadlines
    st.subheader("Upcoming Deadlines")
    today = datetime.date.today()
    upcoming_cases = []
    
    for case in st.session_state.cases:
        due_date = datetime.datetime.fromisoformat(case['response_due_date']).date()
        days_left = (due_date - today).days
        if days_left >= 0 and days_left <= 30:
            upcoming_cases.append({
                'Case Number': case['case_number'],
                'Client': case['client_name'],
                'Due Date': due_date,
                'Days Left': days_left,
                'Priority': case.get('priority', 'Medium')
            })
    
    if upcoming_cases:
        df_upcoming = pd.DataFrame(upcoming_cases)
        df_upcoming = df_upcoming.sort_values('Days Left')
        st.dataframe(df_upcoming, use_container_width=True)
    else:
        st.info("No upcoming deadlines in the next 30 days.")

if __name__ == "__main__":
    main()
