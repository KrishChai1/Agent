import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json

# Page configuration
st.set_page_config(
    page_title="WMS Microservices Project Dashboard",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better UI
st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
        font-size: 18px;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
    }
    .epic-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 10px;
        border-radius: 5px;
        margin: 10px 0;
    }
    .user-story-card {
        background-color: #ffffff;
        padding: 15px;
        border-left: 4px solid #667eea;
        margin: 10px 0;
        border-radius: 5px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state for project data
if 'project_data' not in st.session_state:
    st.session_state.project_data = {
        'epics': [
            {
                'id': 'EPIC-001',
                'n': 'Core Platform Setup & Infrastructure',
                'priority': 'P0',
                'phase': 0,
                'capabilities': [
                    {
                        'n': 'Azure Cloud Infrastructure Setup',
                        'stories': [
                            {'id': 'US-1.1.1', 'title': 'Set up Azure resource groups', 'points': 8, 'status': 'Not Started'},
                            {'id': 'US-1.1.2', 'title': 'Configure Azure Virtual Networks', 'points': 5, 'status': 'Not Started'},
                            {'id': 'US-1.1.3', 'title': 'Implement Azure Firewall rules', 'points': 8, 'status': 'Not Started'},
                            {'id': 'US-1.1.4', 'title': 'Set up Container Apps Environment', 'points': 13, 'status': 'Not Started'},
                            {'id': 'US-1.1.5', 'title': 'Configure API Management', 'points': 8, 'status': 'Not Started'},
                        ]
                    },
                    {
                        'n': 'Database Migration & Setup',
                        'stories': [
                            {'id': 'US-1.2.1', 'title': 'Setup Azure Database for Oracle', 'points': 13, 'status': 'Not Started'},
                            {'id': 'US-1.2.2', 'title': 'Migrate PL/SQL packages', 'points': 21, 'status': 'Not Started'},
                            {'id': 'US-1.2.3', 'title': 'Setup PostgreSQL database', 'points': 5, 'status': 'Not Started'},
                            {'id': 'US-1.2.4', 'title': 'Implement backup strategies', 'points': 8, 'status': 'Not Started'},
                        ]
                    }
                ]
            },
            {
                'id': 'EPIC-002',
                'n': 'Authentication & User Management',
                'priority': 'P0',
                'phase': 1,
                'capabilities': [
                    {
                        'n': 'Authentication Service',
                        'stories': [
                            {'id': 'US-2.1.1', 'title': 'User login functionality', 'points': 5, 'status': 'Not Started'},
                            {'id': 'US-2.1.2', 'title': 'User logout functionality', 'points': 3, 'status': 'Not Started'},
                            {'id': 'US-2.1.3', 'title': 'Token refresh mechanism', 'points': 5, 'status': 'Not Started'},
                            {'id': 'US-2.1.4', 'title': 'Single Sign-On implementation', 'points': 8, 'status': 'Not Started'},
                            {'id': 'US-2.1.5', 'title': 'Multi-factor authentication', 'points': 8, 'status': 'Not Started'},
                        ]
                    }
                ]
            },
            {
                'id': 'EPIC-003',
                'n': 'Core WMS Operations',
                'priority': 'P0',
                'phase': 1,
                'capabilities': [
                    {
                        'n': 'Inventory Management',
                        'stories': [
                            {'id': 'US-3.1.1', 'title': 'Real-time inventory view', 'points': 8, 'status': 'Not Started'},
                            {'id': 'US-3.1.2', 'title': 'Update inventory quantities', 'points': 5, 'status': 'Not Started'},
                            {'id': 'US-3.1.3', 'title': 'Track inventory movements', 'points': 8, 'status': 'Not Started'},
                            {'id': 'US-3.1.4', 'title': 'Set reorder points', 'points': 5, 'status': 'Not Started'},
                            {'id': 'US-3.1.5', 'title': 'Inventory adjustments', 'points': 5, 'status': 'Not Started'},
                            {'id': 'US-3.1.6', 'title': 'RTM integration', 'points': 13, 'status': 'Not Started'},
                        ]
                    },
                    {
                        'n': 'Receiving Service',
                        'stories': [
                            {'id': 'US-3.2.1', 'title': 'Create receiving documents', 'points': 5, 'status': 'Not Started'},
                            {'id': 'US-3.2.2', 'title': 'Barcode/RFID scanning', 'points': 8, 'status': 'Not Started'},
                            {'id': 'US-3.2.3', 'title': 'Verify shipment contents', 'points': 5, 'status': 'Not Started'},
                            {'id': 'US-3.2.4', 'title': 'Generate putaway tasks', 'points': 8, 'status': 'Not Started'},
                        ]
                    }
                ]
            },
            {
                'id': 'EPIC-004',
                'n': 'Wave Management',
                'priority': 'P1',
                'phase': 2,
                'capabilities': [
                    {
                        'n': 'Wave Planning',
                        'stories': [
                            {'id': 'US-4.1.1', 'title': 'Create picking waves', 'points': 8, 'status': 'Not Started'},
                            {'id': 'US-4.1.2', 'title': 'Set wave criteria', 'points': 5, 'status': 'Not Started'},
                            {'id': 'US-4.1.3', 'title': 'Auto-generate waves', 'points': 13, 'status': 'Not Started'},
                            {'id': 'US-4.1.4', 'title': 'Prioritize waves', 'points': 5, 'status': 'Not Started'},
                        ]
                    }
                ]
            },
            {
                'id': 'EPIC-005',
                'n': 'RF Mobile Operations',
                'priority': 'P0',
                'phase': 2,
                'capabilities': [
                    {
                        'n': 'RF Device Interface',
                        'stories': [
                            {'id': 'US-5.1.1', 'title': 'Responsive mobile interface', 'points': 13, 'status': 'Not Started'},
                            {'id': 'US-5.1.2', 'title': 'Offline capability', 'points': 21, 'status': 'Not Started'},
                            {'id': 'US-5.1.3', 'title': 'Barcode/RFID scanning', 'points': 8, 'status': 'Not Started'},
                            {'id': 'US-5.1.4', 'title': 'Voice-guided operations', 'points': 13, 'status': 'Not Started'},
                        ]
                    }
                ]
            }
        ],
        'team': {
            'size': 8,
            'velocity': 70,
            'sprint_duration': 14
        },
        'costs': {
            'hourly_rates': {
                'Head of Technology': 140,
                'Senior Technical Architect': 113,
                'Technical Architect': 103,
                'Project Manager': 103,
                'Senior Developer': 87,
                'Team Lead': 89,
                'DevOps Engineer': 87,
                'Business Analyst': 82,
                'Integration Specialist': 89
            }
        }
    }

def main():
    st.title("🚀 WMS Microservices Modernization Dashboard")
    st.markdown("### Comprehensive Project Management System")
    
    # Sidebar navigation
    with st.sidebar:
        st.markdown("## Navigation")
        page = st.radio(
            "Select Page",
            ["📊 Overview", "📋 Epics Management", "💰 Cost Analysis", 
             "📈 Progress Tracking", "👥 Team Management", "📅 Sprint Planning"]
        )
    
    if page == "📊 Overview":
        show_overview()
    elif page == "📋 Epics Management":
        show_epics_management()
    elif page == "💰 Cost Analysis":
        show_cost_analysis()
    elif page == "📈 Progress Tracking":
        show_progress_tracking()
    elif page == "👥 Team Management":
        show_team_management()
    elif page == "📅 Sprint Planning":
        show_sprint_planning()

def show_overview():
    st.header("Project Overview Dashboard")
    
    # Calculate metrics
    total_points = sum(
        story['points'] 
        for epic in st.session_state.project_data['epics'] 
        for cap in epic['capabilities'] 
        for story in cap['stories']
    )
    
    total_epics = len(st.session_state.project_data['epics'])
    
    # Display metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Story Points", total_points)
    
    with col2:
        st.metric("Total Epics", total_epics)
    
    with col3:
        velocity = st.session_state.project_data['team']['velocity']
        sprints = total_points / velocity
        st.metric("Estimated Sprints", f"{sprints:.1f}")
    
    with col4:
        duration_weeks = sprints * 2
        st.metric("Est. Duration", f"{duration_weeks:.1f} weeks")
    
    # Phase distribution chart
    st.subheader("📊 Story Points by Phase")
    
    phase_data = {}
    for epic in st.session_state.project_data['epics']:
        phase = f"Phase {epic['phase']}"
        if phase not in phase_data:
            phase_data[phase] = 0
        phase_data[phase] += sum(
            story['points'] 
            for cap in epic['capabilities'] 
            for story in cap['stories']
        )
    
    fig = px.pie(
        values=list(phase_data.values()), 
        names=list(phase_data.keys()),
        title="Story Points Distribution by Phase",
        color_discrete_sequence=px.colors.sequential.Viridis
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Priority distribution
    st.subheader("🎯 Epic Priority Distribution")
    
    priority_data = {}
    for epic in st.session_state.project_data['epics']:
        priority = epic['priority']
        if priority not in priority_data:
            priority_data[priority] = 0
        priority_data[priority] += 1
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig2 = px.bar(
            x=list(priority_data.keys()),
            y=list(priority_data.values()),
            title="Epics by Priority",
            labels={'x': 'Priority', 'y': 'Count'},
            color=list(priority_data.values()),
            color_continuous_scale='Reds'
        )
        st.plotly_chart(fig2, use_container_width=True)
    
    with col2:
        # Technology stack
        st.markdown("### 🛠 Technology Stack")
        st.markdown("""
        - **Backend:** Spring Boot 3.2, Java 17
        - **Frontend:** Angular 17, Angular Material
        - **Database:** Oracle 19c, PostgreSQL 14
        - **Cloud:** Azure (Container Apps, API Management)
        - **DevOps:** Azure DevOps, Docker
        - **Security:** Azure AD B2C, OAuth 2.0
        """)

def show_epics_management():
    st.header("📋 Epics and User Stories Management")
    
    # Create tabs for each epic
    epic_tabs = st.tabs([epic['n'] for epic in st.session_state.project_data['epics']])
    
    for idx, tab in enumerate(epic_tabs):
        with tab:
            epic = st.session_state.project_data['epics'][idx]
            
            # Epic header
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.markdown(f"### {epic['id']}: {epic['n']}")
            with col2:
                st.markdown(f"**Priority:** {epic['priority']}")
            with col3:
                st.markdown(f"**Phase:** {epic['phase']}")
            
            # Capabilities and User Stories
            for cap_idx, capability in enumerate(epic['capabilities']):
                st.markdown(f"#### 🎯 {capability['n']}")
                
                # Create a dataframe for stories
                stories_data = []
                for story in capability['stories']:
                    stories_data.append({
                        'ID': story['id'],
                        'Title': story['title'],
                        'Points': story['points'],
                        'Status': story['status']
                    })
                
                df = pd.DataFrame(stories_data)
                
                # Make it editable
                edited_df = st.data_editor(
                    df,
                    column_config={
                        "Points": st.column_config.NumberColumn(
                            "Story Points",
                            min_value=1,
                            max_value=34,
                            step=1,
                        ),
                        "Status": st.column_config.SelectboxColumn(
                            "Status",
                            options=["Not Started", "In Progress", "Completed", "Blocked"],
                        )
                    },
                    disabled=['ID', 'Title'],
                    hide_index=True,
                    key=f"stories_{epic['id']}_{cap_idx}"
                )
                
                # Update button
                if st.button(f"Save Changes", key=f"save_{epic['id']}_{cap_idx}"):
                    # Update the session state with edited values
                    for i, story in enumerate(capability['stories']):
                        story['points'] = edited_df.iloc[i]['Points']
                        story['status'] = edited_df.iloc[i]['Status']
                    st.success("✅ Changes saved successfully!")
                
                # Show capability total
                cap_total = sum(story['points'] for story in capability['stories'])
                st.markdown(f"**Capability Total: {cap_total} points**")
                
            # Epic summary
            epic_total = sum(
                story['points'] 
                for cap in epic['capabilities'] 
                for story in cap['stories']
            )
            st.info(f"📊 **Epic Total: {epic_total} story points**")

def show_cost_analysis():
    st.header("💰 Cost Analysis & Resource Planning")
    
    # Phase selection
    phase = st.selectbox("Select Phase", ["Phase 0 (Foundation)", "Phase 1 (Core)", "Phase 2 (Advanced)", "Phase 3 (Analytics)"])
    
    # Team composition for selected phase
    st.subheader("Team Composition")
    
    if "Phase 0" in phase:
        st.markdown("### Phase 0 - Onsite Team (Strategic Planning)")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Onsite Resources")
            onsite_weeks = st.number_input("Duration (weeks)", value=4, min_value=1, max_value=12)
            hod_hours = st.number_input("Head of Technology (hours/week)", value=20, min_value=0)
            po_hours = st.number_input("Product Owner (hours/week)", value=40, min_value=0)
            
            # Calculate onsite cost
            rates = st.session_state.project_data['costs']['hourly_rates']
            onsite_cost = (
                hod_hours * onsite_weeks * rates['Head of Technology'] +
                po_hours * onsite_weeks * 120  # Assuming PO rate
            )
            
            st.metric("Onsite Cost", f"${onsite_cost:,.2f}")
        
        with col2:
            st.markdown("#### Offshore Resources")
            arch_hours = st.number_input("Sr. Technical Architect (hours/week)", value=40, min_value=0)
            ba_hours = st.number_input("Business Analyst (hours/week)", value=40, min_value=0)
            
            offshore_cost = (
                arch_hours * onsite_weeks * rates['Senior Technical Architect'] +
                ba_hours * onsite_weeks * rates['Business Analyst']
            )
            
            st.metric("Offshore Cost", f"${offshore_cost:,.2f}")
        
        st.metric("**Total Phase 0 Cost**", f"${onsite_cost + offshore_cost:,.2f}")
    
    else:
        # Other phases - mostly offshore
        st.markdown("### Development Team (Offshore)")
        
        weeks = st.number_input("Phase Duration (weeks)", value=12, min_value=1, max_value=52)
        
        col1, col2 = st.columns(2)
        
        with col1:
            tech_arch = st.number_input("Technical Architects", value=1, min_value=0, max_value=5)
            sr_dev = st.number_input("Senior Developers", value=3, min_value=0, max_value=10)
            team_lead = st.number_input("Team Leads", value=1, min_value=0, max_value=5)
        
        with col2:
            devops = st.number_input("DevOps Engineers", value=1, min_value=0, max_value=5)
            ba = st.number_input("Business Analysts", value=1, min_value=0, max_value=5)
            integration = st.number_input("Integration Specialists", value=1, min_value=0, max_value=5)
        
        # Calculate costs
        rates = st.session_state.project_data['costs']['hourly_rates']
        weekly_cost = (
            tech_arch * 40 * rates['Technical Architect'] +
            sr_dev * 40 * rates['Senior Developer'] +
            team_lead * 40 * rates['Team Lead'] +
            devops * 40 * rates['DevOps Engineer'] +
            ba * 40 * rates['Business Analyst'] +
            integration * 40 * rates['Integration Specialist']
        )
        
        total_phase_cost = weekly_cost * weeks
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Weekly Cost", f"${weekly_cost:,.2f}")
        with col2:
            st.metric("Total Phase Cost", f"${total_phase_cost:,.2f}")
        with col3:
            st.metric("Monthly Burn Rate", f"${weekly_cost * 4.33:,.2f}")
    
    # Cost breakdown visualization
    st.subheader("📊 Cost Breakdown by Role")
    
    roles = []
    costs = []
    
    for role, rate in st.session_state.project_data['costs']['hourly_rates'].items():
        roles.append(role)
        costs.append(rate * 40)  # Weekly cost assuming 40 hours
    
    fig = px.bar(
        x=roles, 
        y=costs,
        title="Weekly Cost by Role (40 hours/week)",
        labels={'x': 'Role', 'y': 'Cost ($)'},
        color=costs,
        color_continuous_scale='Blues'
    )
    fig.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)
    
    # Total project estimation
    st.subheader("💵 Total Project Cost Estimation")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        phase0_cost = 65000  # Estimated
        st.metric("Phase 0", f"${phase0_cost:,.0f}")
    
    with col2:
        phase1_cost = 320000  # Estimated
        st.metric("Phase 1", f"${phase1_cost:,.0f}")
    
    with col3:
        phase2_cost = 240000  # Estimated
        st.metric("Phase 2", f"${phase2_cost:,.0f}")
    
    total_project = phase0_cost + phase1_cost + phase2_cost
    st.success(f"### 💰 Total Project Estimate: ${total_project:,.0f}")

def show_progress_tracking():
    st.header("📈 Progress Tracking")
    
    # Calculate progress metrics
    completed_points = 0
    in_progress_points = 0
    not_started_points = 0
    blocked_points = 0
    
    for epic in st.session_state.project_data['epics']:
        for cap in epic['capabilities']:
            for story in cap['stories']:
                if story['status'] == 'Completed':
                    completed_points += story['points']
                elif story['status'] == 'In Progress':
                    in_progress_points += story['points']
                elif story['status'] == 'Blocked':
                    blocked_points += story['points']
                else:
                    not_started_points += story['points']
    
    total_points = completed_points + in_progress_points + not_started_points + blocked_points
    
    # Progress metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        progress_pct = (completed_points / total_points * 100) if total_points > 0 else 0
        st.metric("Overall Progress", f"{progress_pct:.1f}%")
    
    with col2:
        st.metric("Completed", completed_points)
    
    with col3:
        st.metric("In Progress", in_progress_points)
    
    with col4:
        st.metric("Remaining", not_started_points)
    
    # Burndown chart
    st.subheader("📉 Sprint Burndown")
    
    # Simulated burndown data
    sprints = list(range(1, 11))
    ideal_burndown = [total_points - (total_points/10 * i) for i in range(10)]
    actual_burndown = [total_points - completed_points * (i/3) for i in range(10)]  # Simulated
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=sprints, y=ideal_burndown,
        mode='lines+markers',
        n='Ideal Burndown',
        line=dict(color='green', dash='dash')
    ))
    fig.add_trace(go.Scatter(
        x=sprints, y=actual_burndown,
        mode='lines+markers',
        n='Actual Burndown',
        line=dict(color='blue')
    ))
    
    fig.update_layout(
        title="Sprint Burndown Chart",
        xaxis_title="Sprint",
        yaxis_title="Story Points Remaining",
        hovermode='x unified'
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Epic progress breakdown
    st.subheader("📊 Epic Progress Breakdown")
    
    epic_progress = []
    for epic in st.session_state.project_data['epics']:
        epic_completed = 0
        epic_total = 0
        for cap in epic['capabilities']:
            for story in cap['stories']:
                epic_total += story['points']
                if story['status'] == 'Completed':
                    epic_completed += story['points']
        
        epic_progress.append({
            'Epic': epic['n'],
            'Completed': epic_completed,
            'Remaining': epic_total - epic_completed,
            'Progress': f"{(epic_completed/epic_total*100) if epic_total > 0 else 0:.1f}%"
        })
    
    df_progress = pd.DataFrame(epic_progress)
    st.dataframe(df_progress, use_container_width=True, hide_index=True)

def show_team_management():
    st.header("👥 Team Management")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Team Settings")
        
        team_size = st.number_input(
            "Team Size", 
            value=st.session_state.project_data['team']['size'],
            min_value=1, 
            max_value=20
        )
        
        velocity = st.number_input(
            "Team Velocity (points/sprint)",
            value=st.session_state.project_data['team']['velocity'],
            min_value=10,
            max_value=200
        )
        
        sprint_duration = st.number_input(
            "Sprint Duration (days)",
            value=st.session_state.project_data['team']['sprint_duration'],
            min_value=7,
            max_value=30
        )
        
        if st.button("Update Team Settings"):
            st.session_state.project_data['team']['size'] = team_size
            st.session_state.project_data['team']['velocity'] = velocity
            st.session_state.project_data['team']['sprint_duration'] = sprint_duration
            st.success("Team settings updated!")
    
    with col2:
        st.subheader("Team Composition")
        
        # Pie chart for team composition
        team_roles = {
            'Senior Developers': 3,
            'Junior Developers': 2,
            'DevOps Engineers': 1,
            'Business Analyst': 1,
            'Technical Lead': 1,
            'QA Engineers': 2
        }
        
        fig = px.pie(
            values=list(team_roles.values()),
            names=list(team_roles.keys()),
            title="Team Composition by Role",
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Velocity tracking
    st.subheader("📈 Velocity Tracking")
    
    # Simulated velocity data
    sprint_numbers = list(range(1, 9))
    velocities = [65, 68, 70, 72, 75, 70, 73, 71]
    
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        x=sprint_numbers,
        y=velocities,
        marker_color='lightblue',
        text=velocities,
        textposition='auto',
    ))
    fig2.add_trace(go.Scatter(
        x=sprint_numbers,
        y=[velocity] * len(sprint_numbers),
        mode='lines',
        n='Target Velocity',
        line=dict(color='red', dash='dash')
    ))
    
    fig2.update_layout(
        title="Team Velocity by Sprint",
        xaxis_title="Sprint Number",
        yaxis_title="Story Points Completed",
        showlegend=True
    )
    st.plotly_chart(fig2, use_container_width=True)
    
    # Team capacity planning
    st.subheader("📅 Capacity Planning")
    
    total_points = sum(
        story['points'] 
        for epic in st.session_state.project_data['epics'] 
        for cap in epic['capabilities'] 
        for story in cap['stories']
    )
    
    sprints_needed = total_points / velocity
    weeks_needed = sprints_needed * (sprint_duration / 7)
    months_needed = weeks_needed / 4.33
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Sprints Required", f"{sprints_needed:.1f}")
    with col2:
        st.metric("Weeks Required", f"{weeks_needed:.1f}")
    with col3:
        st.metric("Months Required", f"{months_needed:.1f}")

def show_sprint_planning():
    st.header("📅 Sprint Planning")
    
    # Sprint selector
    sprint_num = st.selectbox("Select Sprint", [f"Sprint {i}" for i in range(1, 21)])
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader(f"{sprint_num} Planning")
        
        # Available stories for sprint
        st.markdown("### Available User Stories")
        
        available_stories = []
        for epic in st.session_state.project_data['epics']:
            for cap in epic['capabilities']:
                for story in cap['stories']:
                    if story['status'] == 'Not Started':
                        available_stories.append({
                            'Select': False,
                            'ID': story['id'],
                            'Epic': epic['n'][:30] + '...',
                            'Story': story['title'],
                            'Points': story['points']
                        })
        
        if available_stories:
            df_stories = pd.DataFrame(available_stories)
            
            edited_df = st.data_editor(
                df_stories,
                column_config={
                    "Select": st.column_config.CheckboxColumn(
                        "Select",
                        default=False,
                    )
                },
                disabled=['ID', 'Epic', 'Story', 'Points'],
                hide_index=True,
                key=f"sprint_planning_{sprint_num}"
            )
            
            # Calculate selected points
            selected_points = edited_df[edited_df['Select']]['Points'].sum()
            
            velocity = st.session_state.project_data['team']['velocity']
            
            if selected_points > velocity:
                st.warning(f"⚠️ Selected points ({selected_points}) exceed team velocity ({velocity})")
            else:
                st.success(f"✅ Selected points: {selected_points} / {velocity}")
            
            if st.button("Commit to Sprint"):
                if selected_points > 0:
                    st.success(f"Sprint {sprint_num} committed with {selected_points} points!")
                else:
                    st.error("Please select at least one story")
        else:
            st.info("No available stories for planning")
    
    with col2:
        st.subheader("Sprint Metrics")
        
        velocity = st.session_state.project_data['team']['velocity']
        
        st.metric("Team Velocity", velocity)
        st.metric("Sprint Duration", f"{st.session_state.project_data['team']['sprint_duration']} days")
        st.metric("Team Size", st.session_state.project_data['team']['size'])
        
        # Sprint calendar
        st.markdown("### Sprint Calendar")
        start_date = datetime.now()
        end_date = start_date + timedelta(days=st.session_state.project_data['team']['sprint_duration'])
        
        st.markdown(f"**Start:** {start_date.strftime('%Y-%m-%d')}")
        st.markdown(f"**End:** {end_date.strftime('%Y-%m-%d')}")
        
        # Sprint goals
        st.markdown("### Sprint Goals")
        goals = st.text_area(
            "Define sprint goals:",
            placeholder="1. Complete authentication service\n2. Setup CI/CD pipeline\n3. ...",
            height=150
        )

if __n__ == "__main__":
    main()