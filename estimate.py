import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json

# Page configuration
st.set_page_config(
    page_title="Marken Digital Transformation - Estimation Tool",
    page_icon="📊",
    layout="wide"
)

# Initialize session state
if 'phase_data' not in st.session_state:
    st.session_state.phase_data = {}

# Rate card based on ShipNexus document
RATE_CARD = {
    'Onsite': {
        'P1': {'Senior Technical Head': 140, 'Senior Technical Architect': 113.26, 'Technical Architect': 102.56},
        'U1': {'Junior Developer': 77.59},
        'U2': {'Developer': 82.05, 'Tester': 77.59},
        'U3': {'Senior Developer': 87.40, 'Senior Tester': 82.94},
        'U4': {'Automation Test Lead': 89.18, 'Performance Tester': 87.40, 'Project Manager': 102.56, 'Team Lead': 89.18}
    },
    'Nearshore': {
        'P1': {'Senior Project Manager': 75.12, 'Senior Technical Architect': 75.12, 'Technical Architect': 68.02},
        'U1': {'Junior Developer': 51.46},
        'U2': {'Developer': 54.42, 'Tester': 51.46},
        'U3': {'Senior Developer': 57.97, 'Senior Tester': 55.01},
        'U4': {'Automation Test Lead': 59.15, 'Performance Tester': 57.97, 'Project Manager': 68.02, 'Team Lead': 59.15}
    },
    'Offshore': {
        'P1': {'Senior Project Manager': 29.43, 'Senior Technical Architect': 30.32, 'Technical Architect': 26.75},
        'U1': {'Junior Developer': 18.73},
        'U2': {'Developer': 20.51, 'Tester': 19.62},
        'U3': {'Senior Developer': 23.19, 'Senior Tester': 22.30},
        'U4': {'Automation Test Lead': 23.19, 'Performance Tester': 22.30, 'Project Manager': 26.75, 'Team Lead': 23.19}
    }
}

# Epic complexity and effort mapping
EPIC_COMPLEXITY = {
    # Polar Scan Epics
    'PS-EPIC-01': {'complexity': 'High', 'stories': 14, 'effort_multiplier': 1.5},
    'PS-EPIC-02': {'complexity': 'High', 'stories': 15, 'effort_multiplier': 1.4},
    'PS-EPIC-03': {'complexity': 'Medium', 'stories': 14, 'effort_multiplier': 1.2},
    'PS-EPIC-04': {'complexity': 'High', 'stories': 10, 'effort_multiplier': 1.3},
    'PS-EPIC-05': {'complexity': 'Medium', 'stories': 10, 'effort_multiplier': 1.1},
    'PS-EPIC-06': {'complexity': 'Low', 'stories': 8, 'effort_multiplier': 1.0},
    'PS-EPIC-07': {'complexity': 'High', 'stories': 12, 'effort_multiplier': 1.4},
    'PS-EPIC-08': {'complexity': 'High', 'stories': 10, 'effort_multiplier': 1.3},
    'PS-EPIC-09': {'complexity': 'Very High', 'stories': 8, 'effort_multiplier': 2.0},
    'PS-EPIC-10': {'complexity': 'High', 'stories': 10, 'effort_multiplier': 1.5},
    
    # Polar Track Epics
    'PT-EPIC-01': {'complexity': 'Medium', 'stories': 12, 'effort_multiplier': 1.2},
    'PT-EPIC-02': {'complexity': 'High', 'stories': 10, 'effort_multiplier': 1.3},
    'PT-EPIC-03': {'complexity': 'High', 'stories': 12, 'effort_multiplier': 1.4},
    'PT-EPIC-04': {'complexity': 'Medium', 'stories': 12, 'effort_multiplier': 1.2},
    'PT-EPIC-05': {'complexity': 'Medium', 'stories': 10, 'effort_multiplier': 1.2},
    'PT-EPIC-06': {'complexity': 'High', 'stories': 12, 'effort_multiplier': 1.4},
    'PT-EPIC-07': {'complexity': 'Medium', 'stories': 12, 'effort_multiplier': 1.2},
    'PT-EPIC-08': {'complexity': 'Very High', 'stories': 12, 'effort_multiplier': 1.8},
    'PT-EPIC-09': {'complexity': 'Very High', 'stories': 14, 'effort_multiplier': 2.0},
    'PT-EPIC-10': {'complexity': 'High', 'stories': 10, 'effort_multiplier': 1.3},
    'PT-EPIC-11': {'complexity': 'High', 'stories': 12, 'effort_multiplier': 1.4},
    'PT-EPIC-12': {'complexity': 'High', 'stories': 12, 'effort_multiplier': 1.3},
    
    # Patient Management Epics
    'PM-EPIC-01': {'complexity': 'Very High', 'stories': 12, 'effort_multiplier': 1.8},
    'PM-EPIC-02': {'complexity': 'High', 'stories': 12, 'effort_multiplier': 1.3},
    'PM-EPIC-03': {'complexity': 'High', 'stories': 12, 'effort_multiplier': 1.4},
    'PM-EPIC-04': {'complexity': 'Medium', 'stories': 12, 'effort_multiplier': 1.2},
    'PM-EPIC-05': {'complexity': 'High', 'stories': 12, 'effort_multiplier': 1.3},
    'PM-EPIC-06': {'complexity': 'Medium', 'stories': 12, 'effort_multiplier': 1.2},
    'PM-EPIC-07': {'complexity': 'Medium', 'stories': 12, 'effort_multiplier': 1.2},
    'PM-EPIC-08': {'complexity': 'High', 'stories': 13, 'effort_multiplier': 1.4},
    'PM-EPIC-09': {'complexity': 'High', 'stories': 12, 'effort_multiplier': 1.3},
    'PM-EPIC-10': {'complexity': 'Very High', 'stories': 12, 'effort_multiplier': 1.7},
    'PM-EPIC-11': {'complexity': 'Medium', 'stories': 12, 'effort_multiplier': 1.2}
}

def calculate_story_points(epic_id, base_points=3):
    """Calculate story points based on complexity"""
    complexity = EPIC_COMPLEXITY[epic_id]['complexity']
    multiplier = EPIC_COMPLEXITY[epic_id]['effort_multiplier']
    stories = EPIC_COMPLEXITY[epic_id]['stories']
    
    complexity_points = {
        'Low': 2,
        'Medium': 3,
        'High': 5,
        'Very High': 8
    }
    
    return stories * complexity_points[complexity] * multiplier

def generate_phase_timeline():
    """Generate project phase timeline"""
    phases = {
        'Phase 0 - Due Diligence': {
            'start': datetime(2025, 1, 1),
            'duration_weeks': 8,
            'epics': [],
            'focus': 'Discovery, Architecture, Business Alignment'
        },
        'Phase 1 - Scan & Track Beta': {
            'start': datetime(2025, 3, 1),
            'duration_weeks': 24,
            'epics': list(EPIC_COMPLEXITY.keys())[:22],  # All PS and PT epics
            'focus': 'Polar Scan + Track Implementation'
        },
        'Phase 2 - Patient Management': {
            'start': datetime(2025, 9, 1),
            'duration_weeks': 20,
            'epics': list(EPIC_COMPLEXITY.keys())[22:],  # All PM epics
            'focus': 'Patient Management System'
        }
    }
    
    return phases

def calculate_resources(phase_name, epics, duration_weeks):
    """Calculate resources needed for each phase"""
    
    # Base resource allocation
    if phase_name == 'Phase 0 - Due Diligence':
        return {
            'Onsite': {
                'Head of Technology': 1,
                'Senior Technical Architect': 2,
                'Business Product Owner': 2
            },
            'Nearshore': {},
            'Offshore': {}
        }
    
    # Calculate story points for the phase
    total_points = sum(calculate_story_points(epic) for epic in epics if epic in EPIC_COMPLEXITY)
    
    # Resource calculation based on velocity (points per person per sprint)
    velocity_per_person_sprint = 10  # Adjustable
    sprints = duration_weeks / 2
    required_capacity = total_points / (velocity_per_person_sprint * sprints)
    
    # Distribute resources (1 onsite : 2 nearshore : 4 offshore)
    resources = {
        'Onsite': {
            'Technical Architect': 2,
            'Project Manager': 1,
            'Team Lead': 2,
            'Senior Developer': 2,
            'DevOps Engineer': 1
        },
        'Nearshore': {
            'Senior Developer': 3,
            'Developer': 4,
            'Senior Tester': 2,
            'Automation Test Lead': 1,
            'UI/UX Developer': 2
        },
        'Offshore': {
            'Developer': 6,
            'Tester': 4,
            'Junior Developer': 3,
            'Performance Tester': 1,
            'Technical Writer': 1
        }
    }
    
    return resources

def calculate_cost(resources, duration_weeks):
    """Calculate cost based on resources and duration"""
    total_cost = 0
    hours_per_week = 40
    
    for location, roles in resources.items():
        for role, count in roles.items():
            # Map role to rate card
            if location == 'Onsite':
                if 'Architect' in role:
                    rate = RATE_CARD[location]['P1'].get('Technical Architect', 100)
                elif 'Manager' in role:
                    rate = RATE_CARD[location]['U4'].get('Project Manager', 100)
                elif 'Senior' in role:
                    rate = RATE_CARD[location]['U3'].get('Senior Developer', 85)
                elif 'Lead' in role:
                    rate = RATE_CARD[location]['U4'].get('Team Lead', 90)
                else:
                    rate = RATE_CARD[location]['U2'].get('Developer', 80)
            elif location == 'Nearshore':
                if 'Architect' in role:
                    rate = RATE_CARD[location]['P1'].get('Technical Architect', 68)
                elif 'Manager' in role:
                    rate = RATE_CARD[location]['U4'].get('Project Manager', 68)
                elif 'Senior' in role:
                    rate = RATE_CARD[location]['U3'].get('Senior Developer', 57)
                elif 'Lead' in role:
                    rate = RATE_CARD[location]['U4'].get('Team Lead', 59)
                else:
                    rate = RATE_CARD[location]['U2'].get('Developer', 54)
            else:  # Offshore
                if 'Architect' in role:
                    rate = RATE_CARD[location]['P1'].get('Technical Architect', 26)
                elif 'Manager' in role:
                    rate = RATE_CARD[location]['U4'].get('Project Manager', 26)
                elif 'Senior' in role:
                    rate = RATE_CARD[location]['U3'].get('Senior Developer', 23)
                elif 'Junior' in role:
                    rate = RATE_CARD[location]['U1'].get('Junior Developer', 18)
                else:
                    rate = RATE_CARD[location]['U2'].get('Developer', 20)
            
            total_cost += count * rate * hours_per_week * duration_weeks
    
    return total_cost

# Main Streamlit App
st.title("🚀 Marken Digital Transformation - Project Estimation Tool")
st.markdown("---")

# Sidebar for configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    
    velocity = st.slider("Team Velocity (points/person/sprint)", 5, 20, 10)
    contingency = st.slider("Contingency %", 0, 30, 15)
    
    st.header("📊 Summary Statistics")
    st.metric("Total Epics", 33)
    st.metric("Total Capabilities", 165)
    st.metric("Total User Stories", "750+")

# Main content tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📅 Timeline", "👥 Resources", "💰 Costs", "📊 Complexity Analysis", "📈 Dashboard"])

# Generate phase data
phases = generate_phase_timeline()

with tab1:
    st.header("Project Timeline")
    
    # Create Gantt chart
    gantt_data = []
    for phase_name, phase_info in phases.items():
        end_date = phase_info['start'] + timedelta(weeks=phase_info['duration_weeks'])
        gantt_data.append({
            'Task': phase_name,
            'Start': phase_info['start'],
            'Finish': end_date,
            'Duration': f"{phase_info['duration_weeks']} weeks"
        })
    
    df_gantt = pd.DataFrame(gantt_data)
    
    fig = px.timeline(
        df_gantt, 
        x_start="Start", 
        x_end="Finish", 
        y="Task",
        title="Project Phase Timeline",
        height=400
    )
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(fig, use_container_width=True)
    
    # Phase details
    for phase_name, phase_info in phases.items():
        with st.expander(f"📌 {phase_name}"):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Start Date:** {phase_info['start'].strftime('%Y-%m-%d')}")
                st.write(f"**Duration:** {phase_info['duration_weeks']} weeks")
                st.write(f"**Focus:** {phase_info['focus']}")
            with col2:
                st.write(f"**Epics Count:** {len(phase_info['epics'])}")
                if phase_info['epics']:
                    total_stories = sum(EPIC_COMPLEXITY[epic]['stories'] for epic in phase_info['epics'] if epic in EPIC_COMPLEXITY)
                    st.write(f"**Total Stories:** {total_stories}")

with tab2:
    st.header("Resource Allocation")
    
    for phase_name, phase_info in phases.items():
        st.subheader(phase_name)
        
        resources = calculate_resources(phase_name, phase_info['epics'], phase_info['duration_weeks'])
        
        # Display resources in columns
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**🏢 Onsite**")
            for role, count in resources['Onsite'].items():
                st.write(f"• {role}: {count}")
        
        with col2:
            st.markdown("**🌍 Nearshore**")
            for role, count in resources['Nearshore'].items():
                st.write(f"• {role}: {count}")
        
        with col3:
            st.markdown("**🌏 Offshore**")
            for role, count in resources['Offshore'].items():
                st.write(f"• {role}: {count}")
        
        # Calculate total headcount
        total_onsite = sum(resources['Onsite'].values())
        total_nearshore = sum(resources['Nearshore'].values())
        total_offshore = sum(resources['Offshore'].values())
        
        st.markdown(f"**Total Team Size:** {total_onsite + total_nearshore + total_offshore} "
                   f"(Ratio - {total_onsite}:{total_nearshore}:{total_offshore})")

with tab3:
    st.header("Cost Analysis")
    
    total_project_cost = 0
    cost_breakdown = []
    
    for phase_name, phase_info in phases.items():
        resources = calculate_resources(phase_name, phase_info['epics'], phase_info['duration_weeks'])
        phase_cost = calculate_cost(resources, phase_info['duration_weeks'])
        total_project_cost += phase_cost
        
        cost_breakdown.append({
            'Phase': phase_name,
            'Base Cost': phase_cost,
            'Contingency': phase_cost * (contingency/100),
            'Total Cost': phase_cost * (1 + contingency/100)
        })
    
    df_cost = pd.DataFrame(cost_breakdown)
    
    # Display cost summary
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Base Cost", f"${total_project_cost:,.0f}")
    with col2:
        st.metric("Contingency", f"${total_project_cost * (contingency/100):,.0f}")
    with col3:
        st.metric("Total Project Cost", f"${total_project_cost * (1 + contingency/100):,.0f}")
    
    # Cost breakdown table
    st.subheader("Phase-wise Cost Breakdown")
    st.dataframe(
        df_cost.style.format({
            'Base Cost': '${:,.0f}',
            'Contingency': '${:,.0f}',
            'Total Cost': '${:,.0f}'
        }),
        use_container_width=True
    )
    
    # Cost distribution pie chart
    fig = px.pie(
        df_cost,
        values='Total Cost',
        names='Phase',
        title='Cost Distribution by Phase'
    )
    st.plotly_chart(fig)

with tab4:
    st.header("Epic Complexity Analysis")
    
    # Prepare complexity data
    complexity_data = []
    for epic_id, epic_info in EPIC_COMPLEXITY.items():
        complexity_data.append({
            'Epic': epic_id,
            'System': epic_id.split('-')[0],
            'Complexity': epic_info['complexity'],
            'Stories': epic_info['stories'],
            'Effort Multiplier': epic_info['effort_multiplier'],
            'Story Points': calculate_story_points(epic_id)
        })
    
    df_complexity = pd.DataFrame(complexity_data)
    
    # Complexity distribution
    col1, col2 = st.columns(2)
    
    with col1:
        fig = px.pie(
            df_complexity.groupby('Complexity').size().reset_index(name='Count'),
            values='Count',
            names='Complexity',
            title='Epic Complexity Distribution'
        )
        st.plotly_chart(fig)
    
    with col2:
        fig = px.bar(
            df_complexity.groupby('System')['Story Points'].sum().reset_index(),
            x='System',
            y='Story Points',
            title='Story Points by System',
            color='System'
        )
        st.plotly_chart(fig)
    
    # Detailed complexity table
    st.subheader("Epic Complexity Details")
    st.dataframe(
        df_complexity.style.format({
            'Effort Multiplier': '{:.1f}',
            'Story Points': '{:.0f}'
        }),
        use_container_width=True
    )

with tab5:
    st.header("Executive Dashboard")
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_duration = sum(phase['duration_weeks'] for phase in phases.values())
        st.metric("Total Duration", f"{total_duration} weeks")
    
    with col2:
        st.metric("Total Cost", f"${total_project_cost * (1 + contingency/100):,.0f}")
    
    with col3:
        total_resources = 0
        for phase_name, phase_info in phases.items():
            resources = calculate_resources(phase_name, phase_info['epics'], phase_info['duration_weeks'])
            phase_resources = sum(sum(loc.values()) for loc in resources.values())
            total_resources = max(total_resources, phase_resources)
        st.metric("Peak Team Size", total_resources)
    
    with col4:
        total_points = sum(calculate_story_points(epic) for epic in EPIC_COMPLEXITY.keys())
        st.metric("Total Story Points", f"{total_points:.0f}")
    
    # Resource distribution over time
    st.subheader("Resource Distribution Over Project Lifecycle")
    
    resource_timeline = []
    for phase_name, phase_info in phases.items():
        resources = calculate_resources(phase_name, phase_info['epics'], phase_info['duration_weeks'])
        resource_timeline.append({
            'Phase': phase_name,
            'Onsite': sum(resources['Onsite'].values()),
            'Nearshore': sum(resources['Nearshore'].values()),
            'Offshore': sum(resources['Offshore'].values())
        })
    
    df_resource_timeline = pd.DataFrame(resource_timeline)
    
    fig = go.Figure()
    fig.add_trace(go.Bar(name='Onsite', x=df_resource_timeline['Phase'], y=df_resource_timeline['Onsite']))
    fig.add_trace(go.Bar(name='Nearshore', x=df_resource_timeline['Phase'], y=df_resource_timeline['Nearshore']))
    fig.add_trace(go.Bar(name='Offshore', x=df_resource_timeline['Phase'], y=df_resource_timeline['Offshore']))
    fig.update_layout(barmode='stack', title='Resource Stack by Phase')
    st.plotly_chart(fig, use_container_width=True)
    
    # Risk assessment
    st.subheader("Risk Assessment")
    risks = [
        {"Risk": "Integration Complexity", "Impact": "High", "Probability": "Medium", "Mitigation": "Early POCs, dedicated integration team"},
        {"Risk": "Mobile App Performance", "Impact": "Medium", "Probability": "Low", "Mitigation": "Performance testing from Phase 1"},
        {"Risk": "Data Migration", "Impact": "High", "Probability": "Medium", "Mitigation": "Phased migration approach"},
        {"Risk": "Regulatory Compliance", "Impact": "Very High", "Probability": "Low", "Mitigation": "Continuous compliance checks"},
        {"Risk": "User Adoption", "Impact": "Medium", "Probability": "Medium", "Mitigation": "Change management program"}
    ]
    
    df_risks = pd.DataFrame(risks)
    st.dataframe(df_risks, use_container_width=True)

# Footer
st.markdown("---")
st.markdown("### 📝 Notes")
st.info("""
**Key Assumptions:**
- Microservices architecture with React/Angular frontend
- Android-based Zebra scanner application for Polar Scan
- RESTful APIs with event-driven architecture
- Cloud-native deployment (AWS/Azure)
- CI/CD pipeline from Phase 1
- Agile methodology with 2-week sprints
""")

st.warning("""
**Critical Success Factors:**
- Early stakeholder alignment in Phase 0
- Strong integration between Scan and Track systems
- Robust testing strategy for mobile applications
- Performance optimization for real-time tracking
- Compliance with healthcare regulations (GDPR, GDP)
""")

# Download functionality
if st.button("📥 Export Estimation Report"):
    report = {
        "phases": phases,
        "total_cost": total_project_cost * (1 + contingency/100),
        "complexity_analysis": complexity_data,
        "resource_summary": resource_timeline
    }
    
    st.download_button(
        label="Download JSON Report",
        data=json.dumps(report, default=str, indent=2),
        file_name=f"marken_estimation_{datetime.now().strftime('%Y%m%d')}.json",
        mime="application/json"
    )