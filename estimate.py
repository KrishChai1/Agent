import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import uuid

# Page configuration
st.set_page_config(
    page_title="Marken Digital - Complete Sprint Planning & Estimation",
    page_icon="📊",
    layout="wide"
)

# Initialize session state for all data structures
if 'epics' not in st.session_state:
    st.session_state.epics = {
        'Phase 1': {
            'PS-EPIC-01': {
                'name': 'Goods Receipt & Inbound',
                'complexity': 'High',
                'points': 5,
                'capabilities': [
                    {'name': 'Vehicle Check-in', 'stories': 3, 'points': 5},
                    {'name': 'ASN Validation', 'stories': 3, 'points': 5},
                    {'name': 'Hospital Collections', 'stories': 3, 'points': 5},
                    {'name': 'Depot Receipt', 'stories': 3, 'points': 5},
                    {'name': 'Client Receipt', 'stories': 2, 'points': 5}
                ]
            },
            'PS-EPIC-02': {
                'name': 'Internal Transfer Mgmt',
                'complexity': 'Very High',
                'points': 8,
                'capabilities': [
                    {'name': 'Transfer Labels', 'stories': 3, 'points': 8},
                    {'name': 'Hub-to-Hub Transfer', 'stories': 3, 'points': 8},
                    {'name': 'Hub-to-Depot Transfer', 'stories': 3, 'points': 8},
                    {'name': 'Depot-to-Depot', 'stories': 3, 'points': 8},
                    {'name': 'Pallet Building', 'stories': 3, 'points': 8}
                ]
            },
            'PS-EPIC-03': {
                'name': 'Warehouse & Inventory',
                'complexity': 'High',
                'points': 5,
                'capabilities': [
                    {'name': 'Pharmacy Inventory', 'stories': 3, 'points': 5},
                    {'name': 'Bin Management', 'stories': 3, 'points': 5},
                    {'name': 'Cycle Counting', 'stories': 2, 'points': 5},
                    {'name': 'Lot/Batch Tracking', 'stories': 3, 'points': 5},
                    {'name': 'Expiry Management', 'stories': 3, 'points': 5}
                ]
            }
        },
        'Phase 2': {
            'PM-EPIC-01': {
                'name': 'Patient Registration/NHS',
                'complexity': 'High',
                'points': 5,
                'capabilities': [
                    {'name': 'Self Registration', 'stories': 2, 'points': 5},
                    {'name': 'NHS Validation', 'stories': 3, 'points': 5},
                    {'name': 'Summary Care Record', 'stories': 2, 'points': 5},
                    {'name': 'Identity Verification', 'stories': 3, 'points': 5},
                    {'name': 'Consent Management', 'stories': 2, 'points': 5}
                ]
            },
            'PM-EPIC-02': {
                'name': 'Trust & Payer Mgmt',
                'complexity': 'Medium',
                'points': 3,
                'capabilities': [
                    {'name': 'Trust Registration', 'stories': 2, 'points': 3},
                    {'name': 'Coverage Validation', 'stories': 3, 'points': 3},
                    {'name': 'Funding Workflows', 'stories': 2, 'points': 3},
                    {'name': 'Trust Billing', 'stories': 3, 'points': 3},
                    {'name': 'Budget Tracking', 'stories': 2, 'points': 3}
                ]
            }
        }
    }

if 'rate_card' not in st.session_state:
    st.session_state.rate_card = {
        'Onsite': {
            'Senior Technical Architect': 113.26,
            'Technical Architect': 102.56,
            'Project Manager': 102.56,
            'Senior Developer': 87.40,
            'Developer': 82.05,
            'Team Lead': 89.18,
            'DevOps Engineer': 87.40,
            'Business Analyst': 82.05,
            'Scrum Master': 89.18,
        },
        'Nearshore': {
            'Technical Architect': 68.02,
            'Senior Developer': 57.97,
            'Developer': 54.42,
            'Mobile Developer': 57.97,
            'Tester': 51.46,
            'Senior Tester': 55.01,
            'Automation Test Lead': 59.15,
            'DevOps Engineer': 57.97,
        },
        'Offshore': {
            'Senior Developer': 23.19,
            'Developer': 20.51,
            'Junior Developer': 18.73,
            'Tester': 19.62,
            'Automation Tester': 22.30,
            'Performance Tester': 22.30,
            'Technical Writer': 18.73,
        }
    }

if 'sprint_config' not in st.session_state:
    st.session_state.sprint_config = {
        'sprint_duration': 2,  # weeks
        'team_velocity': 5,  # points per person per sprint
        'working_days': 10  # per sprint
    }

# Helper functions
def calculate_epic_total_points(epic_data):
    """Calculate total points for an epic from its capabilities"""
    total_points = 0
    for cap in epic_data.get('capabilities', []):
        total_points += cap['stories'] * cap['points']
    return total_points

def calculate_phase_complexity(phase):
    """Calculate total complexity points for a phase"""
    if phase not in st.session_state.epics:
        return 0
    total_points = 0
    for epic_id, epic_data in st.session_state.epics[phase].items():
        total_points += calculate_epic_total_points(epic_data)
    return total_points

def calculate_sprints_needed(total_points, team_size, velocity_per_person):
    """Calculate number of sprints needed"""
    if team_size == 0 or velocity_per_person == 0:
        return 0
    points_per_sprint = team_size * velocity_per_person
    sprints_needed = total_points / points_per_sprint
    return int(sprints_needed + 0.5)  # Round up

def estimate_team_size_from_complexity(total_points, target_sprints):
    """Estimate team size needed to complete work in target sprints"""
    if target_sprints == 0:
        return 0
    velocity_per_person = st.session_state.sprint_config['team_velocity']
    team_size = total_points / (target_sprints * velocity_per_person)
    return int(team_size + 0.5)  # Round up

def estimate_resources_distribution(team_size, phase):
    """Distribute team across locations based on phase complexity"""
    if phase == 'Phase 1':
        # Complex phase - more senior resources
        onsite_ratio = 0.22
        nearshore_ratio = 0.37
        offshore_ratio = 0.41
    else:
        # Less complex - standard distribution
        onsite_ratio = 0.20
        nearshore_ratio = 0.35
        offshore_ratio = 0.45
    
    resources = {
        'Onsite': max(2, int(team_size * onsite_ratio)),
        'Nearshore': max(3, int(team_size * nearshore_ratio)),
        'Offshore': max(3, int(team_size * offshore_ratio))
    }
    
    return resources

def calculate_cost_from_distribution(resources, duration_weeks):
    """Calculate cost based on resource distribution"""
    total_cost = 0
    hours_per_week = 40
    
    # Average rates per location
    avg_rates = {
        'Onsite': 95.0,
        'Nearshore': 58.0,
        'Offshore': 22.0
    }
    
    for location, count in resources.items():
        total_cost += count * avg_rates[location] * hours_per_week * duration_weeks
    
    return total_cost

# Main App
st.title("🚀 Marken Digital - Sprint Planning & Estimation Tool")
st.markdown("### Complete Epic, Capability, and Sprint Management")

# Sidebar configuration
with st.sidebar:
    st.header("⚙️ Sprint Configuration")
    
    st.session_state.sprint_config['sprint_duration'] = st.number_input(
        "Sprint Duration (weeks)",
        min_value=1,
        max_value=4,
        value=st.session_state.sprint_config['sprint_duration']
    )
    
    st.session_state.sprint_config['team_velocity'] = st.number_input(
        "Velocity (points/person/sprint)",
        min_value=1,
        max_value=20,
        value=st.session_state.sprint_config['team_velocity']
    )
    
    contingency = st.slider("Contingency %", 0, 30, 20)
    
    st.markdown("---")
    
    # Quick stats
    st.subheader("📊 Quick Metrics")
    
    phase1_points = calculate_phase_complexity('Phase 1')
    phase2_points = calculate_phase_complexity('Phase 2')
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Phase 1", f"{phase1_points:,} pts")
    with col2:
        st.metric("Phase 2", f"{phase2_points:,} pts")
    
    st.metric("Total Points", f"{phase1_points + phase2_points:,}")

# Main tabs
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Dashboard",
    "📝 Epic & Capabilities",
    "🎯 Sprint Planning",
    "👥 Team Estimation",
    "💰 Cost Analysis",
    "📈 Reports"
])

with tab1:
    st.header("Project Dashboard")
    
    # Calculate summary metrics
    total_epics = sum(len(phase_epics) for phase_epics in st.session_state.epics.values())
    total_capabilities = sum(
        len(epic.get('capabilities', [])) 
        for phase_epics in st.session_state.epics.values()
        for epic in phase_epics.values()
    )
    total_stories = sum(
        sum(cap['stories'] for cap in epic.get('capabilities', []))
        for phase_epics in st.session_state.epics.values()
        for epic in phase_epics.values()
    )
    total_points = calculate_phase_complexity('Phase 1') + calculate_phase_complexity('Phase 2')
    
    # Display metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Epics", total_epics)
    with col2:
        st.metric("Total Capabilities", total_capabilities)
    with col3:
        st.metric("Total User Stories", total_stories)
    with col4:
        st.metric("Total Story Points", f"{total_points:,}")
    
    # Phase breakdown
    st.subheader("Phase Breakdown")
    
    phase_data = []
    for phase in ['Phase 1', 'Phase 2']:
        if phase in st.session_state.epics:
            epics = st.session_state.epics[phase]
            capabilities = sum(len(epic.get('capabilities', [])) for epic in epics.values())
            stories = sum(
                sum(cap['stories'] for cap in epic.get('capabilities', []))
                for epic in epics.values()
            )
            points = calculate_phase_complexity(phase)
            
            phase_data.append({
                'Phase': phase,
                'Epics': len(epics),
                'Capabilities': capabilities,
                'User Stories': stories,
                'Story Points': points,
                'Avg Points/Story': points / stories if stories > 0 else 0
            })
    
    df_phases = pd.DataFrame(phase_data)
    st.dataframe(df_phases, use_container_width=True)
    
    # Visualization
    col1, col2 = st.columns(2)
    
    with col1:
        fig = px.bar(
            df_phases,
            x='Phase',
            y='Story Points',
            title='Story Points by Phase',
            color='Story Points',
            color_continuous_scale='Blues'
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        fig = px.pie(
            df_phases,
            values='User Stories',
            names='Phase',
            title='User Stories Distribution'
        )
        st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.header("Epic & Capability Management")
    
    phase_select = st.selectbox("Select Phase", ['Phase 1', 'Phase 2'])
    
    # Add new epic
    with st.expander("➕ Add New Epic"):
        col1, col2 = st.columns(2)
        
        with col1:
            new_epic_id = st.text_input("Epic ID", value=f"EPIC-{str(uuid.uuid4())[:8].upper()}")
            new_epic_name = st.text_input("Epic Name")
        
        with col2:
            new_epic_complexity = st.selectbox(
                "Complexity",
                ['Low', 'Medium', 'High', 'Very High']
            )
            complexity_map = {'Low': 2, 'Medium': 3, 'High': 5, 'Very High': 8}
            new_epic_points = complexity_map[new_epic_complexity]
        
        st.subheader("Add Capabilities")
        num_capabilities = st.number_input("Number of Capabilities", min_value=1, max_value=10, value=3)
        
        capabilities_list = []
        for i in range(num_capabilities):
            col1, col2, col3 = st.columns(3)
            with col1:
                cap_name = st.text_input(f"Capability {i+1} Name", key=f"cap_name_{i}")
            with col2:
                cap_stories = st.number_input(f"Stories", min_value=1, value=3, key=f"cap_stories_{i}")
            with col3:
                cap_points = st.number_input(f"Points/Story", min_value=1, value=new_epic_points, key=f"cap_points_{i}")
            
            if cap_name:
                capabilities_list.append({
                    'name': cap_name,
                    'stories': cap_stories,
                    'points': cap_points
                })
        
        if st.button("Add Epic") and new_epic_name and capabilities_list:
            if phase_select not in st.session_state.epics:
                st.session_state.epics[phase_select] = {}
            
            st.session_state.epics[phase_select][new_epic_id] = {
                'name': new_epic_name,
                'complexity': new_epic_complexity,
                'points': new_epic_points,
                'capabilities': capabilities_list
            }
            st.success(f"Added epic: {new_epic_id}")
            st.rerun()
    
    # Display and edit existing epics
    st.subheader(f"{phase_select} Epics")
    
    if phase_select in st.session_state.epics:
        for epic_id, epic_data in st.session_state.epics[phase_select].items():
            with st.expander(f"📋 {epic_id}: {epic_data['name']}"):
                # Epic summary
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Complexity", epic_data['complexity'])
                with col2:
                    total_stories = sum(cap['stories'] for cap in epic_data.get('capabilities', []))
                    st.metric("Total Stories", total_stories)
                with col3:
                    total_points = calculate_epic_total_points(epic_data)
                    st.metric("Total Points", total_points)
                
                # Capabilities table
                st.subheader("Capabilities")
                if 'capabilities' in epic_data:
                    cap_data = []
                    for cap in epic_data['capabilities']:
                        cap_data.append({
                            'Capability': cap['name'],
                            'User Stories': cap['stories'],
                            'Points/Story': cap['points'],
                            'Total Points': cap['stories'] * cap['points']
                        })
                    
                    df_cap = pd.DataFrame(cap_data)
                    st.dataframe(df_cap, use_container_width=True)
                
                # Delete epic button
                if st.button(f"Delete Epic {epic_id}", key=f"del_{epic_id}"):
                    del st.session_state.epics[phase_select][epic_id]
                    st.success(f"Deleted epic: {epic_id}")
                    st.rerun()

with tab3:
    st.header("Sprint Planning")
    
    sprint_phase = st.selectbox("Select Phase for Sprint Planning", ['Phase 1', 'Phase 2'])
    
    if sprint_phase in st.session_state.epics:
        # Calculate phase metrics
        total_points = calculate_phase_complexity(sprint_phase)
        
        # Sprint planning inputs
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Sprint Configuration")
            target_sprints = st.number_input(
                "Target Number of Sprints",
                min_value=1,
                max_value=30,
                value=14 if sprint_phase == 'Phase 1' else 8
            )
            
            sprint_duration = st.session_state.sprint_config['sprint_duration']
            st.info(f"Sprint Duration: {sprint_duration} weeks")
        
        with col2:
            st.subheader("Calculated Requirements")
            
            # Calculate team size needed
            team_size_needed = estimate_team_size_from_complexity(total_points, target_sprints)
            
            st.metric("Team Size Required", team_size_needed)
            st.metric("Total Duration", f"{target_sprints * sprint_duration} weeks")
            st.metric("Points per Sprint", f"{total_points / target_sprints:.0f}")
        
        # Sprint breakdown
        st.subheader("Sprint-by-Sprint Breakdown")
        
        # Distribute epics across sprints
        epics = st.session_state.epics[sprint_phase]
        epic_list = []
        for epic_id, epic_data in epics.items():
            epic_points = calculate_epic_total_points(epic_data)
            epic_list.append({
                'Epic ID': epic_id,
                'Name': epic_data['name'],
                'Points': epic_points,
                'Sprints Needed': epic_points / (team_size_needed * st.session_state.sprint_config['team_velocity'])
            })
        
        df_epics = pd.DataFrame(epic_list)
        
        # Create sprint allocation
        sprint_allocation = []
        points_per_sprint = team_size_needed * st.session_state.sprint_config['team_velocity']
        
        current_sprint = 1
        current_points = 0
        epics_in_sprint = []
        
        for _, epic in df_epics.iterrows():
            if current_points + epic['Points'] > points_per_sprint * 1.2:  # Allow 20% overflow
                sprint_allocation.append({
                    'Sprint': f"Sprint {current_sprint}",
                    'Epics': ', '.join(epics_in_sprint),
                    'Points': current_points,
                    'Team Size': team_size_needed,
                    'Capacity': points_per_sprint,
                    'Utilization %': (current_points / points_per_sprint * 100)
                })
                current_sprint += 1
                current_points = epic['Points']
                epics_in_sprint = [epic['Epic ID']]
            else:
                current_points += epic['Points']
                epics_in_sprint.append(epic['Epic ID'])
        
        # Add last sprint
        if epics_in_sprint:
            sprint_allocation.append({
                'Sprint': f"Sprint {current_sprint}",
                'Epics': ', '.join(epics_in_sprint),
                'Points': current_points,
                'Team Size': team_size_needed,
                'Capacity': points_per_sprint,
                'Utilization %': (current_points / points_per_sprint * 100)
            })
        
        df_sprints = pd.DataFrame(sprint_allocation)
        st.dataframe(df_sprints, use_container_width=True)
        
        # Sprint velocity chart
        fig = px.bar(
            df_sprints,
            x='Sprint',
            y='Points',
            title='Sprint Load Distribution',
            color='Utilization %',
            color_continuous_scale='RdYlGn_r'
        )
        fig.add_hline(y=points_per_sprint, line_dash="dash", line_color="red", 
                     annotation_text="Sprint Capacity")
        st.plotly_chart(fig, use_container_width=True)

with tab4:
    st.header("Team Estimation")
    
    team_phase = st.selectbox("Select Phase for Team Planning", ['Phase 1', 'Phase 2'])
    
    if team_phase in st.session_state.epics:
        total_points = calculate_phase_complexity(team_phase)
        
        # Team sizing options
        sizing_method = st.radio(
            "Team Sizing Method",
            ["Fixed Duration", "Fixed Team Size", "Balanced Approach"]
        )
        
        if sizing_method == "Fixed Duration":
            target_weeks = st.number_input(
                "Target Duration (weeks)",
                min_value=4,
                max_value=52,
                value=28 if team_phase == 'Phase 1' else 16
            )
            
            sprints = target_weeks / st.session_state.sprint_config['sprint_duration']
            team_size = estimate_team_size_from_complexity(total_points, sprints)
            
        elif sizing_method == "Fixed Team Size":
            team_size = st.number_input(
                "Fixed Team Size",
                min_value=5,
                max_value=100,
                value=50
            )
            
            velocity = st.session_state.sprint_config['team_velocity']
            sprints = calculate_sprints_needed(total_points, team_size, velocity)
            target_weeks = sprints * st.session_state.sprint_config['sprint_duration']
            
        else:  # Balanced
            team_size = 40 if team_phase == 'Phase 1' else 20
            velocity = st.session_state.sprint_config['team_velocity']
            sprints = calculate_sprints_needed(total_points, team_size, velocity)
            target_weeks = sprints * st.session_state.sprint_config['sprint_duration']
        
        # Display team composition
        st.subheader("Recommended Team Composition")
        
        resources = estimate_resources_distribution(team_size, team_phase)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("🏢 Onsite", resources['Onsite'])
            st.caption("Leadership & Architecture")
        
        with col2:
            st.metric("🌍 Nearshore", resources['Nearshore'])
            st.caption("Senior Development")
        
        with col3:
            st.metric("🌏 Offshore", resources['Offshore'])
            st.caption("Development & Testing")
        
        # Team metrics
        st.subheader("Team Performance Metrics")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Team Size", team_size)
        
        with col2:
            st.metric("Duration", f"{target_weeks:.0f} weeks")
        
        with col3:
            velocity_total = team_size * st.session_state.sprint_config['team_velocity']
            st.metric("Team Velocity", f"{velocity_total} pts/sprint")
        
        with col4:
            st.metric("Total Sprints", f"{sprints:.0f}")
        
        # Skills distribution
        st.subheader("Recommended Skills Distribution")
        
        skills_data = {
            'Skill Area': ['Development', 'Testing', 'Architecture', 'DevOps', 'Business Analysis', 'Management'],
            'Percentage': [40, 25, 10, 10, 10, 5],
            'People': [
                int(team_size * 0.40),
                int(team_size * 0.25),
                int(team_size * 0.10),
                int(team_size * 0.10),
                int(team_size * 0.10),
                int(team_size * 0.05)
            ]
        }
        
        df_skills = pd.DataFrame(skills_data)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.dataframe(df_skills, use_container_width=True)
        
        with col2:
            fig = px.pie(
                df_skills,
                values='People',
                names='Skill Area',
                title='Team Skills Distribution'
            )
            st.plotly_chart(fig, use_container_width=True)

with tab5:
    st.header("Cost Analysis")
    
    cost_phase = st.selectbox("Select Phase for Cost Analysis", ['Phase 1', 'Phase 2', 'Combined'])
    
    if cost_phase == 'Combined':
        phases_to_analyze = ['Phase 1', 'Phase 2']
    else:
        phases_to_analyze = [cost_phase]
    
    cost_summary = []
    
    for phase in phases_to_analyze:
        if phase in st.session_state.epics:
            total_points = calculate_phase_complexity(phase)
            
            # Estimate team and duration
            if phase == 'Phase 1':
                team_size = 50
                duration_weeks = 28
            else:
                team_size = 25
                duration_weeks = 16
            
            # Calculate cost
            resources = estimate_resources_distribution(team_size, phase)
            base_cost = calculate_cost_from_distribution(resources, duration_weeks)
            
            cost_summary.append({
                'Phase': phase,
                'Team Size': team_size,
                'Duration (weeks)': duration_weeks,
                'Story Points': total_points,
                'Base Cost': base_cost,
                'Contingency': base_cost * (contingency/100),
                'Total Cost': base_cost * (1 + contingency/100),
                'Cost per Point': base_cost / total_points if total_points > 0 else 0,
                'Weekly Burn': base_cost / duration_weeks if duration_weeks > 0 else 0
            })
    
    df_cost = pd.DataFrame(cost_summary)
    
    # Display cost summary
    st.subheader("Cost Summary")
    
    for col in ['Base Cost', 'Contingency', 'Total Cost', 'Cost per Point', 'Weekly Burn']:
        df_cost[col] = df_cost[col].apply(lambda x: f"${x:,.0f}")
    
    st.dataframe(df_cost, use_container_width=True)
    
    # Total project cost
    if len(cost_summary) > 1:
        total_cost = sum(row['Total Cost'] for row in cost_summary if isinstance(row.get('Total Cost', 0), (int, float)))
        st.metric("Total Project Cost", f"${total_cost:,.0f}")
    
    # Cost breakdown visualization
    st.subheader("Cost Distribution")
    
    cost_breakdown = []
    for phase_data in cost_summary:
        phase = phase_data['Phase']
        resources = estimate_resources_distribution(phase_data['Team Size'], phase)
        
        # Calculate cost per location
        avg_rates = {'Onsite': 95.0, 'Nearshore': 58.0, 'Offshore': 22.0}
        duration = phase_data['Duration (weeks)']
        
        for location, count in resources.items():
            cost = count * avg_rates[location] * 40 * duration
            cost_breakdown.append({
                'Phase': phase,
                'Location': location,
                'Cost': cost
            })
    
    df_breakdown = pd.DataFrame(cost_breakdown)
    
    fig = px.sunburst(
        df_breakdown,
        path=['Phase', 'Location'],
        values='Cost',
        title='Cost Distribution by Phase and Location'
    )
    st.plotly_chart(fig, use_container_width=True)

with tab6:
    st.header("Project Reports")
    
    st.subheader("Executive Summary")
    
    # Calculate overall metrics
    total_epics = sum(len(phase_epics) for phase_epics in st.session_state.epics.values())
    total_capabilities = sum(
        len(epic.get('capabilities', [])) 
        for phase_epics in st.session_state.epics.values()
        for epic in phase_epics.values()
    )
    total_stories = sum(
        sum(cap['stories'] for cap in epic.get('capabilities', []))
        for phase_epics in st.session_state.epics.values()
        for epic in phase_epics.values()
    )
    phase1_points = calculate_phase_complexity('Phase 1')
    phase2_points = calculate_phase_complexity('Phase 2')
    total_points = phase1_points + phase2_points
    
    # Executive metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Epics", total_epics)
        st.metric("Phase 1", len(st.session_state.epics.get('Phase 1', {})))
        st.metric("Phase 2", len(st.session_state.epics.get('Phase 2', {})))
    
    with col2:
        st.metric("Total Capabilities", total_capabilities)
        st.metric("Total User Stories", total_stories)
        st.metric("Avg Stories/Epic", f"{total_stories/total_epics:.1f}" if total_epics > 0 else "0")
    
    with col3:
        st.metric("Total Story Points", f"{total_points:,}")
        st.metric("Phase 1 Points", f"{phase1_points:,}")
        st.metric("Phase 2 Points", f"{phase2_points:,}")
    
    with col4:
        # Estimate total cost
        p1_cost = calculate_cost_from_distribution(
            estimate_resources_distribution(50, 'Phase 1'), 28
        ) * (1 + contingency/100)
        p2_cost = calculate_cost_from_distribution(
            estimate_resources_distribution(25, 'Phase 2'), 16
        ) * (1 + contingency/100)
        
        st.metric("Estimated Total Cost", f"${(p1_cost + p2_cost)/1000000:.1f}M")
        st.metric("Phase 1 Cost", f"${p1_cost/1000000:.1f}M")
        st.metric("Phase 2 Cost", f"${p2_cost/1000000:.1f}M")
    
    # Detailed breakdown
    st.subheader("Detailed Epic Breakdown")
    
    epic_details = []
    for phase, epics in st.session_state.epics.items():
        for epic_id, epic_data in epics.items():
            total_stories = sum(cap['stories'] for cap in epic_data.get('capabilities', []))
            total_points = calculate_epic_total_points(epic_data)
            
            epic_details.append({
                'Phase': phase,
                'Epic ID': epic_id,
                'Epic Name': epic_data['name'],
                'Complexity': epic_data['complexity'],
                'Capabilities': len(epic_data.get('capabilities', [])),
                'User Stories': total_stories,
                'Total Points': total_points
            })
    
    df_epic_details = pd.DataFrame(epic_details)
    st.dataframe(df_epic_details, use_container_width=True)
    
    # Export functionality
    st.subheader("Export Report")
    
    if st.button("📥 Generate Full Report"):
        report_data = {
            'summary': {
                'total_epics': total_epics,
                'total_capabilities': total_capabilities,
                'total_stories': total_stories,
                'total_points': total_points,
                'estimated_cost': f"${(p1_cost + p2_cost):,.0f}",
                'contingency_percent': contingency
            },
            'phases': {
                'Phase 1': {
                    'epics': len(st.session_state.epics.get('Phase 1', {})),
                    'points': phase1_points,
                    'estimated_team': 50,
                    'duration_weeks': 28,
                    'cost': f"${p1_cost:,.0f}"
                },
                'Phase 2': {
                    'epics': len(st.session_state.epics.get('Phase 2', {})),
                    'points': phase2_points,
                    'estimated_team': 25,
                    'duration_weeks': 16,
                    'cost': f"${p2_cost:,.0f}"
                }
            },
            'sprint_config': st.session_state.sprint_config,
            'epics': st.session_state.epics,
            'timestamp': datetime.now().isoformat()
        }
        
        st.download_button(
            label="Download JSON Report",
            data=json.dumps(report_data, indent=2),
            file_name=f"marken_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )
        
        # Also offer CSV export of epic details
        csv_data = df_epic_details.to_csv(index=False)
        st.download_button(
            label="Download Epic Details (CSV)",
            data=csv_data,
            file_name=f"marken_epics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )

# Footer
st.markdown("---")
st.info("""
**📌 Tool Features:**
- Epic management with capabilities and user stories
- Story point calculation per capability
- Sprint planning with velocity calculations
- Team size estimation based on complexity
- Cost analysis with location distribution
- Complete project reporting

**🚀 Quick Tips:**
- Each capability can have different story points based on complexity
- Sprint velocity is configurable (default: 5 points/person/sprint)
- Team distribution adjusts automatically based on phase complexity
- Use 20-30% contingency for complex phases
""")
