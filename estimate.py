import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json

# Page configuration
st.set_page_config(
    page_title="Marken Digital - Complete Project Implementation",
    page_icon="📊",
    layout="wide"
)

# Initialize complete data structure from documentation
if 'project_data' not in st.session_state:
    st.session_state.project_data = {
        'phases': {
            'Phase 0': {
                'name': 'Due Diligence & Architecture',
                'duration_weeks': 8,
                'start_date': datetime(2025, 1, 1),
                'epics': [],  # No development epics, just planning
                'focus': 'Discovery, Architecture Design, POCs, Business Alignment',
                'team_size': 6,
                'deliverables': [
                    'Technical Architecture Blueprint',
                    'Integration Strategy',
                    'Zebra Scanner POC',
                    'IoT Temperature Sensor POC',
                    'Risk Assessment',
                    'Resource Plan'
                ]
            },
            'Phase 1': {
                'name': 'Polar Scan & Track Implementation',
                'duration_weeks': 28,
                'start_date': datetime(2025, 3, 1),
                'epics': ['PS-EPIC-01', 'PS-EPIC-02', 'PS-EPIC-03', 'PS-EPIC-04', 'PS-EPIC-05',
                         'PS-EPIC-06', 'PS-EPIC-07', 'PS-EPIC-08', 'PS-EPIC-09', 'PS-EPIC-10',
                         'PT-EPIC-01', 'PT-EPIC-02', 'PT-EPIC-03', 'PT-EPIC-04', 'PT-EPIC-05',
                         'PT-EPIC-06', 'PT-EPIC-07', 'PT-EPIC-08', 'PT-EPIC-09', 'PT-EPIC-10',
                         'PT-EPIC-11', 'PT-EPIC-12'],
                'focus': 'Mobile Scanner App, Real-time Tracking, IoT Integration',
                'team_size': 73
            },
            'Phase 2': {
                'name': 'Patient Management System',
                'duration_weeks': 16,
                'start_date': datetime(2025, 10, 1),
                'epics': ['PM-EPIC-01', 'PM-EPIC-02', 'PM-EPIC-03', 'PM-EPIC-04', 'PM-EPIC-05',
                         'PM-EPIC-06', 'PM-EPIC-07', 'PM-EPIC-08', 'PM-EPIC-09', 'PM-EPIC-10',
                         'PM-EPIC-11'],
                'focus': 'Patient Portal, NHS Integration, Clinical Services',
                'team_size': 28
            }
        }
    }

# Complete epic definitions with all capabilities and user stories
if 'epics' not in st.session_state:
    st.session_state.epics = {
        # POLAR SCAN EPICS
        'PS-EPIC-01': {
            'name': 'Goods Receipt & Inbound Operations',
            'system': 'Polar Scan',
            'complexity': 'High',
            'capabilities': {
                'PS-CAP-1.1': {
                    'name': 'Vehicle arrival and check-in processing',
                    'stories': ['Check-in vehicles and capture arrival times', 'Gate operator dashboard', 'Vehicle scheduling'],
                    'points': 5
                },
                'PS-CAP-1.2': {
                    'name': 'ASN validation and goods receipt',
                    'stories': ['Scan ASN barcodes to start receipt', 'Scan individual items against ASN', 'Generate receipt confirmations'],
                    'points': 5
                },
                'PS-CAP-1.3': {
                    'name': 'Hospital/clinic collections management',
                    'stories': ['Scan collections from hospitals', 'Capture signatures at collection', 'Record temperature at collection'],
                    'points': 8
                },
                'PS-CAP-1.4': {
                    'name': 'Polar Speed depot receipt',
                    'stories': ['Handle goods from Polar Speed depots', 'Depot transfer validation', 'Chain of custody tracking'],
                    'points': 5
                },
                'PS-CAP-1.5': {
                    'name': 'Client/customer goods receipt',
                    'stories': ['Process client-specific deliveries', 'Customer receipt workflows', 'Custom labeling'],
                    'points': 5
                }
            }
        },
        'PS-EPIC-02': {
            'name': 'Internal Transfer Management',
            'system': 'Polar Scan',
            'complexity': 'Very High',
            'capabilities': {
                'PS-CAP-2.1': {
                    'name': 'Transfer label generation',
                    'stories': ['Create transfer labels for ambient', 'Create transfer labels for chilled', 'Validate label accuracy'],
                    'points': 8
                },
                'PS-CAP-2.2': {
                    'name': 'Hub-to-hub transfer operations',
                    'stories': ['Scan transfer labels against barcodes', 'Build transfer pallets', 'Hub transfer routing'],
                    'points': 8
                },
                'PS-CAP-2.3': {
                    'name': 'Hub-to-depot transfer management',
                    'stories': ['Move pallets to bus stops', 'Check vehicle presence', 'Staging area management'],
                    'points': 8
                },
                'PS-CAP-2.4': {
                    'name': 'Depot-to-depot transfers',
                    'stories': ['Scan transfers into vehicles', 'Confirm vehicle departure', 'Scan incoming transfers'],
                    'points': 5
                },
                'PS-CAP-2.5': {
                    'name': 'Transfer pallet building',
                    'stories': ['Validate transfer arrival', 'Handle misdeliveries', 'Track chain of custody'],
                    'points': 8
                }
            }
        },
        # Add remaining epics here - truncated for brevity
        # You would copy all the epic definitions from your original code
    }

# Cost calculation functions
def calculate_phase_cost(phase_name):
    """Calculate cost for a phase based on team size and duration"""
    phase = st.session_state.project_data['phases'][phase_name]
    
    if phase_name == 'Phase 0':
        # Fixed cost for Phase 0 - Due Diligence
        hourly_rates = {
            'Head of Technology': 140,
            'Senior Architect': 113,
            'Business Analyst': 82
        }
        # 1 Head of Tech, 2 Architects, 2 BAs, 1 UI/UX
        weekly_cost = (140 + 113*2 + 82*3) * 40
        return weekly_cost * phase['duration_weeks']
    
    else:
        # Calculate based on team size and average rates
        avg_rate_per_person = 45 if phase_name == 'Phase 1' else 40  # Blended rate
        team_size = phase['team_size']
        duration_weeks = phase['duration_weeks']
        hours_per_week = 40
        
        return team_size * avg_rate_per_person * hours_per_week * duration_weeks

def calculate_epic_points(epic_id):
    """Calculate total story points for an epic"""
    if epic_id not in st.session_state.epics:
        return 0
    
    epic = st.session_state.epics[epic_id]
    total_points = 0
    
    for cap_id, cap_data in epic['capabilities'].items():
        num_stories = len(cap_data['stories'])
        points_per_story = cap_data['points']
        total_points += num_stories * points_per_story
    
    return total_points

def get_phase_metrics(phase_name):
    """Get comprehensive metrics for a phase"""
    phase = st.session_state.project_data['phases'][phase_name]
    
    if phase_name == 'Phase 0':
        return {
            'epics': 0,
            'capabilities': 0,
            'stories': 0,
            'points': 0,
            'cost': calculate_phase_cost(phase_name)
        }
    
    # Calculate metrics for Phase 1 and Phase 2
    total_epics = len(phase['epics'])
    total_capabilities = 0
    total_stories = 0
    total_points = 0
    
    for epic_id in phase['epics']:
        if epic_id in st.session_state.epics:
            epic = st.session_state.epics[epic_id]
            total_capabilities += len(epic['capabilities'])
            
            for cap_data in epic['capabilities'].values():
                total_stories += len(cap_data['stories'])
                total_points += len(cap_data['stories']) * cap_data['points']
    
    return {
        'epics': total_epics,
        'capabilities': total_capabilities,
        'stories': total_stories,
        'points': total_points,
        'cost': calculate_phase_cost(phase_name)
    }

# Main App
st.title("🚀 Marken Digital Transformation - Complete Implementation Plan")
st.markdown("### 33 Epics | 165 Capabilities | 750+ User Stories")

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuration")
    
    contingency = st.slider("Contingency %", 0, 30, 20)
    
    st.markdown("---")
    st.header("📊 Project Summary")
    
    total_epics = 33
    total_capabilities = 165
    total_stories = 750
    
    st.metric("Total Epics", total_epics)
    st.metric("Total Capabilities", total_capabilities)
    st.metric("Total User Stories", f"{total_stories}+")

# Main tabs
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Executive Dashboard",
    "📅 Timeline & Phases",
    "💰 Cost Analysis",
    "📝 Epics & Stories",
    "👥 Resources",
    "📈 Reports"
])

with tab1:
    st.header("Executive Dashboard")
    
    # Calculate totals
    total_cost = 0
    phase_summary = []
    
    for phase_name in ['Phase 0', 'Phase 1', 'Phase 2']:
        metrics = get_phase_metrics(phase_name)
        phase = st.session_state.project_data['phases'][phase_name]
        
        phase_summary.append({
            'Phase': phase_name,
            'Name': phase['name'],
            'Duration': f"{phase['duration_weeks']} weeks",
            'Team Size': phase['team_size'],
            'Epics': metrics['epics'],
            'Capabilities': metrics['capabilities'],
            'User Stories': metrics['stories'],
            'Story Points': metrics['points'],
            'Base Cost': metrics['cost'],
            'Total Cost': metrics['cost'] * (1 + contingency/100)
        })
        total_cost += metrics['cost'] * (1 + contingency/100)
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Duration", "52 weeks")
        st.caption("~12 months")
    
    with col2:
        st.metric("Total Investment", f"${total_cost/1000000:.1f}M")
        st.caption(f"Includes {contingency}% contingency")
    
    with col3:
        st.metric("Peak Team Size", "73 people")
        st.caption("During Phase 1")
    
    with col4:
        total_points = sum(ps['Story Points'] for ps in phase_summary)
        st.metric("Total Story Points", f"{total_points:,}")
    
    # Phase comparison table
    st.subheader("Phase-by-Phase Summary")
    
    # Create display dataframe with formatted currency columns
    df_phases = pd.DataFrame(phase_summary)
    df_phases_display = df_phases.copy()
    
    # Format currency columns for display only
    df_phases_display['Base Cost'] = df_phases_display['Base Cost'].apply(lambda x: f"${x:,.0f}")
    df_phases_display['Total Cost'] = df_phases_display['Total Cost'].apply(lambda x: f"${x:,.0f}")
    
    st.dataframe(df_phases_display, use_container_width=True)
    
    # Visualizations
    col1, col2 = st.columns(2)
    
    with col1:
        # Cost distribution - use numeric values from original df_phases
        fig = px.pie(
            df_phases,
            values='Total Cost',  # Use column name directly
            names='Name',
            title='Cost Distribution by Phase'
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Complexity distribution
        complexity_data = []
        for ps in phase_summary:
            if ps['Story Points'] > 0:
                complexity_data.append({
                    'Phase': ps['Phase'],
                    'Points': ps['Story Points']
                })
        
        if complexity_data:
            fig = px.bar(
                complexity_data,
                x='Phase',
                y='Points',
                title='Story Points by Phase',
                color='Points',
                color_continuous_scale='Blues'
            )
            st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.header("Project Timeline & Phases")
    
    # Create timeline data
    timeline_data = []
    
    for phase_name in ['Phase 0', 'Phase 1', 'Phase 2']:
        phase = st.session_state.project_data['phases'][phase_name]
        end_date = phase['start_date'] + timedelta(weeks=phase['duration_weeks'])
        
        timeline_data.append({
            'Phase': phase_name,
            'Name': phase['name'],
            'Start': phase['start_date'],
            'End': end_date,
            'Duration': f"{phase['duration_weeks']} weeks"
        })
    
    # Gantt chart
    df_timeline = pd.DataFrame(timeline_data)
    
    fig = px.timeline(
        df_timeline,
        x_start='Start',
        x_end='End',
        y='Name',
        title='Project Implementation Timeline',
        color='Phase'
    )
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(fig, use_container_width=True)
    
    # Phase details
    for phase_name in ['Phase 0', 'Phase 1', 'Phase 2']:
        phase = st.session_state.project_data['phases'][phase_name]
        metrics = get_phase_metrics(phase_name)
        
        with st.expander(f"📋 {phase_name}: {phase['name']}"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Phase Details:**")
                st.write(f"- Start Date: {phase['start_date'].strftime('%B %d, %Y')}")
                st.write(f"- Duration: {phase['duration_weeks']} weeks")
                st.write(f"- Team Size: {phase['team_size']} people")
                st.write(f"- Focus: {phase['focus']}")
            
            with col2:
                st.markdown("**Metrics:**")
                st.write(f"- Epics: {metrics['epics']}")
                st.write(f"- Capabilities: {metrics['capabilities']}")
                st.write(f"- User Stories: {metrics['stories']}")
                st.write(f"- Story Points: {metrics['points']}")
                st.write(f"- Cost: ${metrics['cost']:,.0f}")
            
            if phase_name == 'Phase 0' and 'deliverables' in phase:
                st.markdown("**Key Deliverables:**")
                for deliverable in phase['deliverables']:
                    st.write(f"- {deliverable}")

with tab3:
    st.header("Cost Analysis by Phase")
    
    # Detailed cost breakdown
    cost_details = []
    
    for phase_name in ['Phase 0', 'Phase 1', 'Phase 2']:
        phase = st.session_state.project_data['phases'][phase_name]
        base_cost = calculate_phase_cost(phase_name)
        
        cost_details.append({
            'Phase': phase_name,
            'Name': phase['name'],
            'Team Size': phase['team_size'],
            'Duration (weeks)': phase['duration_weeks'],
            'Base Cost': base_cost,
            'Contingency': base_cost * (contingency/100),
            'Total Cost': base_cost * (1 + contingency/100),
            'Weekly Burn': base_cost / phase['duration_weeks'],
            'Cost per Person': base_cost / (phase['team_size'] * phase['duration_weeks']) if phase['team_size'] > 0 else 0
        })
    
    df_cost = pd.DataFrame(cost_details)
    
    # Summary metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        total_base = df_cost['Base Cost'].sum()
        st.metric("Total Base Cost", f"${total_base:,.0f}")
    
    with col2:
        total_contingency = df_cost['Contingency'].sum()
        st.metric("Total Contingency", f"${total_contingency:,.0f}")
    
    with col3:
        total_project = df_cost['Total Cost'].sum()
        st.metric("Total Project Cost", f"${total_project:,.0f}")
    
    # Cost breakdown table
    st.subheader("Phase-wise Cost Breakdown")
    
    # Create a copy for display with formatted currency columns
    df_cost_display = df_cost.copy()
    for col in ['Base Cost', 'Contingency', 'Total Cost', 'Weekly Burn', 'Cost per Person']:
        df_cost_display[col] = df_cost_display[col].apply(lambda x: f"${x:,.0f}")
    
    st.dataframe(df_cost_display, use_container_width=True)
    
    # Cost visualization
    st.subheader("Cost Distribution Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Cost by phase bar chart - use numeric values from original df_cost
        fig = px.bar(
            df_cost,
            x='Phase',
            y='Total Cost',
            title='Total Cost by Phase',
            color='Total Cost',
            color_continuous_scale='Reds'
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Weekly burn rate comparison - use numeric values from original df_cost
        fig = px.bar(
            df_cost,
            x='Phase',
            y='Weekly Burn',
            title='Weekly Burn Rate by Phase',
            color='Weekly Burn',
            color_continuous_scale='Blues'
        )
        st.plotly_chart(fig, use_container_width=True)

with tab4:
    st.header("Epics, Capabilities & User Stories")
    
    # System filter
    system_filter = st.selectbox(
        "Filter by System",
        ["All", "Polar Scan", "Polar Track", "Patient Management"]
    )
    
    # Phase filter
    phase_filter = st.selectbox(
        "Filter by Phase",
        ["All", "Phase 1", "Phase 2"]
    )
    
    # Display epics
    for epic_id, epic_data in st.session_state.epics.items():
        # Apply filters
        if system_filter != "All" and epic_data['system'] != system_filter:
            continue
        
        # Check phase assignment
        in_phase1 = epic_id in st.session_state.project_data['phases']['Phase 1']['epics']
        in_phase2 = epic_id in st.session_state.project_data['phases']['Phase 2']['epics']
        
        if phase_filter == "Phase 1" and not in_phase1:
            continue
        if phase_filter == "Phase 2" and not in_phase2:
            continue
        
        # Display epic
        with st.expander(f"📋 {epic_id}: {epic_data['name']} ({epic_data['system']})"):
            # Epic summary
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Complexity", epic_data['complexity'])
            
            with col2:
                num_capabilities = len(epic_data['capabilities'])
                st.metric("Capabilities", num_capabilities)
            
            with col3:
                total_points = calculate_epic_points(epic_id)
                st.metric("Story Points", total_points)
            
            # Capabilities table
            st.subheader("Capabilities & User Stories")
            
            for cap_id, cap_data in epic_data['capabilities'].items():
                st.markdown(f"**{cap_id}: {cap_data['name']}**")
                st.write(f"Points per story: {cap_data['points']}")
                st.write("User Stories:")
                for story in cap_data['stories']:
                    st.write(f"  • {story}")
                st.markdown("---")

with tab5:
    st.header("Resource Planning")
    
    # Phase-wise resource breakdown
    st.subheader("Resource Distribution by Phase")
    
    phase_select = st.selectbox("Select Phase", ["Phase 0", "Phase 1", "Phase 2"])
    
    if phase_select == "Phase 0":
        resource_data = []
        resource_data.append({'Role': 'Head of Technology', 'Location': 'Onsite', 'Count': 1, 'Rate': '$140/hr'})
        resource_data.append({'Role': 'Senior Technical Architect', 'Location': 'Onsite', 'Count': 2, 'Rate': '$113/hr'})
        resource_data.append({'Role': 'Business Analyst', 'Location': 'Onsite', 'Count': 2, 'Rate': '$82/hr'})
        resource_data.append({'Role': 'UI/UX Designer', 'Location': 'Onsite', 'Count': 1, 'Rate': '$82/hr'})
        
        df_resources = pd.DataFrame(resource_data)
        st.dataframe(df_resources, use_container_width=True)
        
    elif phase_select == "Phase 1":
        st.write("**Total Team: 73 people**")
        
        st.markdown("**Onsite (16)**")
        st.write("• Senior Technical Architect: 2 @ $113/hr")
        st.write("• Technical Architect: 2 @ $103/hr")
        st.write("• Project Manager: 2 @ $103/hr")
        st.write("• Senior Developer: 3 @ $87/hr")
        st.write("• Team Lead: 2 @ $89/hr")
        st.write("• DevOps Engineer: 2 @ $87/hr")
        st.write("• Business Analyst: 2 @ $82/hr")
        st.write("• Integration Specialist: 1 @ $89/hr")
        
        st.markdown("**Nearshore (27)**")
        st.write("• Technical Architect: 2 @ $68/hr")
        st.write("• Senior Developer: 4 @ $58/hr")
        st.write("• Mobile Developer: 3 @ $58/hr")
        st.write("• Developer: 6 @ $54/hr")
        st.write("• Senior Tester: 3 @ $55/hr")
        st.write("• Automation Test Lead: 2 @ $59/hr")
        st.write("• UI/UX Developer: 3 @ $54/hr")
        st.write("• DevOps Engineer: 1 @ $58/hr")
        st.write("• Integration Developer: 2 @ $58/hr")
        st.write("• Performance Engineer: 1 @ $58/hr")
        
        st.markdown("**Offshore (30)**")
        st.write("• Senior Developer: 4 @ $23/hr")
        st.write("• Developer: 8 @ $21/hr")
        st.write("• Junior Developer: 4 @ $19/hr")
        st.write("• Integration Developer: 3 @ $23/hr")
        st.write("• Tester: 6 @ $20/hr")
        st.write("• Automation Tester: 3 @ $22/hr")
        st.write("• Performance Tester: 2 @ $22/hr")
        
    else:  # Phase 2
        st.write("**Total Team: 28 people**")
        
        st.markdown("**Onsite (7)**")
        st.write("• Technical Architect: 1 @ $103/hr")
        st.write("• Project Manager: 1 @ $103/hr")
        st.write("• Senior Developer: 2 @ $87/hr")
        st.write("• Team Lead: 1 @ $89/hr")
        st.write("• Business Analyst: 1 @ $82/hr")
        st.write("• Data Architect: 1 @ $103/hr")
        
        st.markdown("**Nearshore (10)**")
        st.write("• Senior Developer: 2 @ $58/hr")
        st.write("• Developer: 3 @ $54/hr")
        st.write("• Senior Tester: 1 @ $55/hr")
        st.write("• Automation Test Lead: 1 @ $59/hr")
        st.write("• UI/UX Developer: 2 @ $54/hr")
        st.write("• QA Lead: 1 @ $55/hr")
        
        st.markdown("**Offshore (11)**")
        st.write("• Developer: 4 @ $21/hr")
        st.write("• Junior Developer: 2 @ $19/hr")
        st.write("• Tester: 3 @ $20/hr")
        st.write("• Automation Tester: 1 @ $22/hr")
        st.write("• Technical Writer: 1 @ $19/hr")

with tab6:
    st.header("Project Reports")
    
    st.subheader("Complete Project Summary")
    
    # Executive summary
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Project Scope:**")
        st.write("• 3 Systems: Polar Scan, Polar Track, Patient Management")
        st.write("• 33 Epics across all systems")
        st.write("• 165 Capabilities")
        st.write("• 750+ User Stories")
        st.write("• 52 weeks total duration")
        
    with col2:
        st.markdown("**Investment Summary:**")
        total_project_cost = sum(calculate_phase_cost(f"Phase {i}") * (1 + contingency/100) for i in range(3))
        st.write(f"• Total Investment: ${total_project_cost:,.0f}")
        st.write(f"• Contingency: {contingency}%")
        st.write("• Peak Team Size: 73 people")
        st.write("• Phases: 3 (including Due Diligence)")
    
    # Generate downloadable report
    if st.button("📥 Generate Complete Report"):
        report_data = {
            'project_summary': {
                'total_epics': 33,
                'total_capabilities': 165,
                'total_stories': '750+',
                'total_duration_weeks': 52,
                'total_investment': f"${total_project_cost:,.0f}",
                'contingency_percent': contingency
            },
            'phases': {},
            'epics': st.session_state.epics,
            'timestamp': datetime.now().isoformat()
        }
        
        # Add phase details
        for phase_name in ['Phase 0', 'Phase 1', 'Phase 2']:
            phase = st.session_state.project_data['phases'][phase_name]
            metrics = get_phase_metrics(phase_name)
            
            report_data['phases'][phase_name] = {
                'name': phase['name'],
                'duration_weeks': phase['duration_weeks'],
                'team_size': phase['team_size'],
                'epics': metrics['epics'],
                'capabilities': metrics['capabilities'],
                'stories': metrics['stories'],
                'points': metrics['points'],
                'cost': f"${metrics['cost'] * (1 + contingency/100):,.0f}"
            }
        
        st.download_button(
            label="Download JSON Report",
            data=json.dumps(report_data, indent=2, default=str),
            file_name=f"marken_complete_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )

# Footer
st.markdown("---")
st.info("""
**Implementation Highlights:**
- **Phase 0 (8 weeks):** Due diligence, architecture design, POCs
- **Phase 1 (28 weeks):** 22 epics - Polar Scan + Track systems, Mobile app, IoT
- **Phase 2 (16 weeks):** 11 epics - Patient Management System, NHS Integration

**Critical Success Factors:**
- Early architecture validation in Phase 0
- Mobile app development expertise for Zebra scanners
- Strong integration capabilities for real-time systems
- Healthcare compliance knowledge for Phase 2
""")
