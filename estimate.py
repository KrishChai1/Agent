import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import uuid

# Page configuration
st.set_page_config(
    page_title="Marken Digital - Complete Project Estimation Tool",
    page_icon="📊",
    layout="wide"
)

# Initialize session state for all data structures
if 'epics' not in st.session_state:
    # Initialize with default epics
    st.session_state.epics = {
        'Phase 1': {
            'PS-EPIC-01': {'name': 'Goods Receipt & Inbound', 'complexity': 'High', 'points': 5, 'capabilities': 5, 'stories': 14},
            'PS-EPIC-02': {'name': 'Internal Transfer Mgmt', 'complexity': 'Very High', 'points': 8, 'capabilities': 5, 'stories': 15},
            'PS-EPIC-03': {'name': 'Warehouse & Inventory', 'complexity': 'High', 'points': 5, 'capabilities': 5, 'stories': 14},
            'PS-EPIC-04': {'name': 'Temperature Zone Ops', 'complexity': 'Very High', 'points': 8, 'capabilities': 5, 'stories': 10},
            'PS-EPIC-05': {'name': 'Staging & Bus Stop', 'complexity': 'Medium', 'points': 3, 'capabilities': 5, 'stories': 10},
            'PS-EPIC-06': {'name': 'Cross-docking', 'complexity': 'Medium', 'points': 3, 'capabilities': 5, 'stories': 8},
            'PS-EPIC-07': {'name': 'Outbound & Final Mile', 'complexity': 'High', 'points': 5, 'capabilities': 5, 'stories': 12},
            'PS-EPIC-08': {'name': 'Exception Management', 'complexity': 'High', 'points': 5, 'capabilities': 5, 'stories': 10},
            'PS-EPIC-09': {'name': 'System Integration', 'complexity': 'Very High', 'points': 13, 'capabilities': 5, 'stories': 8},
            'PS-EPIC-10': {'name': 'Mobile Scanner App', 'complexity': 'Very High', 'points': 8, 'capabilities': 5, 'stories': 10},
            'PT-EPIC-01': {'name': 'Customer Onboarding', 'complexity': 'Medium', 'points': 3, 'capabilities': 5, 'stories': 12},
            'PT-EPIC-02': {'name': 'Master Data Mgmt', 'complexity': 'High', 'points': 5, 'capabilities': 5, 'stories': 10},
            'PT-EPIC-03': {'name': 'Order Management', 'complexity': 'High', 'points': 5, 'capabilities': 5, 'stories': 12},
            'PT-EPIC-04': {'name': 'Middle Mile Delivery', 'complexity': 'High', 'points': 5, 'capabilities': 5, 'stories': 12},
            'PT-EPIC-05': {'name': 'Hub & Depot Network', 'complexity': 'High', 'points': 5, 'capabilities': 5, 'stories': 10},
            'PT-EPIC-06': {'name': 'Final Mile Operations', 'complexity': 'Very High', 'points': 8, 'capabilities': 5, 'stories': 12},
            'PT-EPIC-07': {'name': 'Fleet & Driver Mgmt', 'complexity': 'High', 'points': 5, 'capabilities': 5, 'stories': 12},
            'PT-EPIC-08': {'name': 'Real-time Tracking', 'complexity': 'Very High', 'points': 8, 'capabilities': 5, 'stories': 12},
            'PT-EPIC-09': {'name': 'IoT Temperature Platform', 'complexity': 'Very High', 'points': 8, 'capabilities': 5, 'stories': 14},
            'PT-EPIC-10': {'name': 'Inventory Visibility', 'complexity': 'High', 'points': 5, 'capabilities': 5, 'stories': 10},
            'PT-EPIC-11': {'name': 'Exception & Incident', 'complexity': 'High', 'points': 5, 'capabilities': 5, 'stories': 12},
            'PT-EPIC-12': {'name': 'Analytics Platform', 'complexity': 'High', 'points': 5, 'capabilities': 5, 'stories': 12}
        },
        'Phase 2': {
            'PM-EPIC-01': {'name': 'Patient Registration/NHS', 'complexity': 'High', 'points': 5, 'capabilities': 5, 'stories': 12},
            'PM-EPIC-02': {'name': 'Trust & Payer Mgmt', 'complexity': 'Medium', 'points': 3, 'capabilities': 5, 'stories': 12},
            'PM-EPIC-03': {'name': 'Prescription Processing', 'complexity': 'High', 'points': 5, 'capabilities': 5, 'stories': 12},
            'PM-EPIC-04': {'name': 'Treatment Planning', 'complexity': 'Medium', 'points': 3, 'capabilities': 5, 'stories': 12},
            'PM-EPIC-05': {'name': 'Pharmacy Network', 'complexity': 'Medium', 'points': 3, 'capabilities': 5, 'stories': 12},
            'PM-EPIC-06': {'name': 'Scheduling & Care', 'complexity': 'Medium', 'points': 3, 'capabilities': 5, 'stories': 12},
            'PM-EPIC-07': {'name': 'Phlebotomy Services', 'complexity': 'Medium', 'points': 3, 'capabilities': 5, 'stories': 12},
            'PM-EPIC-08': {'name': 'Clinical Documentation', 'complexity': 'High', 'points': 5, 'capabilities': 5, 'stories': 13},
            'PM-EPIC-09': {'name': 'Delivery to Patients', 'complexity': 'Medium', 'points': 3, 'capabilities': 5, 'stories': 12},
            'PM-EPIC-10': {'name': 'Compliance & Quality', 'complexity': 'High', 'points': 5, 'capabilities': 5, 'stories': 12},
            'PM-EPIC-11': {'name': 'Patient Portal', 'complexity': 'Medium', 'points': 3, 'capabilities': 5, 'stories': 12}
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
            'Mobile Developer': 87.40,
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

if 'custom_resources' not in st.session_state:
    st.session_state.custom_resources = {}

# Helper functions
def calculate_phase_complexity(phase):
    """Calculate total complexity points for a phase"""
    if phase not in st.session_state.epics:
        return 0
    total_points = sum(epic['points'] * epic['stories'] for epic in st.session_state.epics[phase].values())
    return total_points

def estimate_resources_from_complexity(phase, duration_weeks):
    """Automatically estimate resources based on complexity"""
    complexity_points = calculate_phase_complexity(phase)
    
    # Base calculation: points per person per week
    velocity_per_person_week = 5  # Adjustable base velocity
    total_person_weeks = complexity_points / velocity_per_person_week
    avg_team_size = total_person_weeks / duration_weeks if duration_weeks > 0 else 1
    
    # Distribution ratios based on phase
    if phase == 'Phase 1':
        # More complex, needs more senior resources
        onsite_ratio = 0.22
        nearshore_ratio = 0.37
        offshore_ratio = 0.41
        
        resources = {
            'Onsite': {
                'Senior Technical Architect': max(1, int(avg_team_size * 0.03)),
                'Technical Architect': max(1, int(avg_team_size * 0.03)),
                'Project Manager': max(1, int(avg_team_size * 0.02)),
                'Senior Developer': max(2, int(avg_team_size * 0.05)),
                'Team Lead': max(1, int(avg_team_size * 0.03)),
                'DevOps Engineer': max(1, int(avg_team_size * 0.03)),
                'Business Analyst': max(1, int(avg_team_size * 0.03)),
            },
            'Nearshore': {
                'Technical Architect': max(1, int(avg_team_size * 0.03)),
                'Senior Developer': max(2, int(avg_team_size * 0.06)),
                'Developer': max(3, int(avg_team_size * 0.10)),
                'Mobile Developer': max(2, int(avg_team_size * 0.04)),
                'Senior Tester': max(2, int(avg_team_size * 0.04)),
                'Automation Test Lead': max(1, int(avg_team_size * 0.03)),
                'DevOps Engineer': max(1, int(avg_team_size * 0.02)),
            },
            'Offshore': {
                'Senior Developer': max(2, int(avg_team_size * 0.05)),
                'Developer': max(4, int(avg_team_size * 0.12)),
                'Junior Developer': max(2, int(avg_team_size * 0.06)),
                'Tester': max(3, int(avg_team_size * 0.08)),
                'Automation Tester': max(2, int(avg_team_size * 0.04)),
                'Performance Tester': max(1, int(avg_team_size * 0.03)),
                'Technical Writer': max(1, int(avg_team_size * 0.02)),
            }
        }
    else:  # Phase 2 - less complex
        resources = {
            'Onsite': {
                'Technical Architect': 1,
                'Project Manager': 1,
                'Senior Developer': max(1, int(avg_team_size * 0.10)),
                'Team Lead': 1,
                'Business Analyst': 1,
            },
            'Nearshore': {
                'Senior Developer': max(1, int(avg_team_size * 0.10)),
                'Developer': max(2, int(avg_team_size * 0.15)),
                'Senior Tester': 1,
                'Automation Test Lead': 1,
            },
            'Offshore': {
                'Developer': max(2, int(avg_team_size * 0.20)),
                'Junior Developer': max(1, int(avg_team_size * 0.10)),
                'Tester': max(2, int(avg_team_size * 0.15)),
                'Automation Tester': 1,
                'Technical Writer': 1,
            }
        }
    
    return resources

def calculate_cost_from_resources(resources, duration_weeks):
    """Calculate cost from resource allocation"""
    total_cost = 0
    hours_per_week = 40
    
    for location, roles in resources.items():
        for role, count in roles.items():
            if role in st.session_state.rate_card.get(location, {}):
                rate = st.session_state.rate_card[location][role]
            else:
                # Default rates
                rate = 50 if location == 'Offshore' else 75 if location == 'Nearshore' else 100
            total_cost += count * rate * hours_per_week * duration_weeks
    
    return total_cost

def get_team_size_from_resources(resources):
    """Get total team size from resources dict"""
    total = 0
    for location in resources.values():
        total += sum(location.values())
    return total

# Main App
st.title("🚀 Marken Digital Transformation - Complete Estimation Tool")
st.markdown("### Dynamic Epic Management & Resource Estimation")

# Sidebar configuration
with st.sidebar:
    st.header("⚙️ Global Settings")
    
    contingency = st.slider("Contingency %", 0, 30, 20)
    velocity_per_week = st.slider("Team Velocity (points/person/week)", 3, 10, 5)
    
    st.markdown("---")
    
    # Quick stats
    st.subheader("📊 Quick Stats")
    
    phase1_points = calculate_phase_complexity('Phase 1')
    phase2_points = calculate_phase_complexity('Phase 2')
    
    st.metric("Phase 1 Points", f"{phase1_points:,}")
    st.metric("Phase 2 Points", f"{phase2_points:,}")
    st.metric("Total Points", f"{phase1_points + phase2_points:,}")
    
    st.markdown("---")
    
    # Export/Import configuration
    if st.button("💾 Export Full Configuration"):
        config = {
            'epics': st.session_state.epics,
            'rate_card': st.session_state.rate_card,
            'custom_resources': st.session_state.custom_resources
        }
        st.download_button(
            label="Download JSON",
            data=json.dumps(config, indent=2),
            file_name=f"marken_config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )

# Main tabs
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Dashboard",
    "📝 Epic Management",
    "👥 Resource Planning",
    "💵 Rate Cards",
    "📈 Analysis",
    "🎯 Estimation"
])

with tab1:
    st.header("Executive Dashboard")
    
    # Phase selector for detailed view
    phase_options = ['Overview', 'Phase 1', 'Phase 2']
    selected_phase = st.selectbox("Select View", phase_options)
    
    if selected_phase == 'Overview':
        # Overview metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_epics = sum(len(epics) for epics in st.session_state.epics.values())
            st.metric("Total Epics", total_epics)
        
        with col2:
            total_stories = sum(
                sum(epic['stories'] for epic in phase_epics.values())
                for phase_epics in st.session_state.epics.values()
            )
            st.metric("Total User Stories", total_stories)
        
        with col3:
            total_capabilities = sum(
                sum(epic['capabilities'] for epic in phase_epics.values())
                for phase_epics in st.session_state.epics.values()
            )
            st.metric("Total Capabilities", total_capabilities)
        
        with col4:
            total_points = phase1_points + phase2_points
            st.metric("Total Story Points", f"{total_points:,}")
        
        # Phase comparison
        st.subheader("Phase Comparison")
        
        comparison_data = []
        for phase in ['Phase 1', 'Phase 2']:
            if phase in st.session_state.epics:
                phase_epics = st.session_state.epics[phase]
                points = calculate_phase_complexity(phase)
                stories = sum(epic['stories'] for epic in phase_epics.values())
                
                # Estimate duration based on complexity
                estimated_weeks = max(8, int(points / (velocity_per_week * 20)))  # Assume 20 person team average
                
                comparison_data.append({
                    'Phase': phase,
                    'Epics': len(phase_epics),
                    'User Stories': stories,
                    'Story Points': points,
                    'Estimated Weeks': estimated_weeks,
                    'Complexity': 'High' if points > 1000 else 'Medium' if points > 500 else 'Low'
                })
        
        df_comparison = pd.DataFrame(comparison_data)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.dataframe(df_comparison, use_container_width=True)
        
        with col2:
            fig = px.bar(
                df_comparison,
                x='Phase',
                y='Story Points',
                title='Complexity by Phase',
                color='Story Points',
                color_continuous_scale='RdYlBu_r'
            )
            st.plotly_chart(fig, use_container_width=True)
    
    else:
        # Detailed phase view
        if selected_phase in st.session_state.epics:
            phase_epics = st.session_state.epics[selected_phase]
            
            # Phase metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Epics", len(phase_epics))
            
            with col2:
                total_stories = sum(epic['stories'] for epic in phase_epics.values())
                st.metric("User Stories", total_stories)
            
            with col3:
                total_points = calculate_phase_complexity(selected_phase)
                st.metric("Story Points", f"{total_points:,}")
            
            with col4:
                avg_complexity = total_points / len(phase_epics) if phase_epics else 0
                st.metric("Avg Epic Complexity", f"{avg_complexity:.1f}")
            
            # Epic details table
            st.subheader(f"{selected_phase} Epics")
            
            epic_data = []
            for epic_id, epic_info in phase_epics.items():
                epic_data.append({
                    'Epic ID': epic_id,
                    'Name': epic_info['name'],
                    'Complexity': epic_info['complexity'],
                    'Points/Story': epic_info['points'],
                    'Capabilities': epic_info['capabilities'],
                    'User Stories': epic_info['stories'],
                    'Total Points': epic_info['points'] * epic_info['stories']
                })
            
            df_epics = pd.DataFrame(epic_data)
            
            st.dataframe(
                df_epics.style.background_gradient(subset=['Total Points']),
                use_container_width=True
            )
            
            # Complexity distribution
            complexity_dist = df_epics.groupby('Complexity')['Epic ID'].count()
            
            fig = px.pie(
                values=complexity_dist.values,
                names=complexity_dist.index,
                title=f'{selected_phase} Complexity Distribution'
            )
            st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.header("Epic Management")
    
    # Phase selector
    epic_phase = st.selectbox("Select Phase", ['Phase 1', 'Phase 2'], key='epic_mgmt_phase')
    
    # Add new epic
    with st.expander("➕ Add New Epic"):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            new_epic_id = st.text_input("Epic ID", value=f"CUSTOM-{str(uuid.uuid4())[:8].upper()}")
            new_epic_name = st.text_input("Epic Name")
        
        with col2:
            new_epic_complexity = st.selectbox("Complexity", ['Low', 'Medium', 'High', 'Very High'])
            complexity_points = {'Low': 2, 'Medium': 3, 'High': 5, 'Very High': 8}
            new_epic_points = st.number_input("Points per Story", min_value=1, value=complexity_points[new_epic_complexity])
        
        with col3:
            new_epic_capabilities = st.number_input("Capabilities", min_value=1, value=5)
            new_epic_stories = st.number_input("User Stories", min_value=1, value=10)
        
        if st.button("Add Epic") and new_epic_name:
            if epic_phase not in st.session_state.epics:
                st.session_state.epics[epic_phase] = {}
            
            st.session_state.epics[epic_phase][new_epic_id] = {
                'name': new_epic_name,
                'complexity': new_epic_complexity,
                'points': new_epic_points,
                'capabilities': new_epic_capabilities,
                'stories': new_epic_stories
            }
            st.success(f"Added epic: {new_epic_id}")
            st.rerun()
    
    # Edit existing epics
    st.subheader(f"Edit {epic_phase} Epics")
    
    if epic_phase in st.session_state.epics:
        epics = st.session_state.epics[epic_phase]
        
        # Create editable dataframe
        epic_list = []
        for epic_id, epic_info in epics.items():
            epic_list.append({
                'Epic ID': epic_id,
                'Name': epic_info['name'],
                'Complexity': epic_info['complexity'],
                'Points': epic_info['points'],
                'Capabilities': epic_info['capabilities'],
                'Stories': epic_info['stories'],
                'Total Points': epic_info['points'] * epic_info['stories'],
                'Delete': False
            })
        
        if epic_list:
            df_edit = pd.DataFrame(epic_list)
            
            # Edit interface
            edited_df = st.data_editor(
                df_edit,
                column_config={
                    'Epic ID': st.column_config.TextColumn('Epic ID', disabled=True),
                    'Name': st.column_config.TextColumn('Name'),
                    'Complexity': st.column_config.SelectboxColumn(
                        'Complexity',
                        options=['Low', 'Medium', 'High', 'Very High']
                    ),
                    'Points': st.column_config.NumberColumn('Points/Story', min_value=1, max_value=20),
                    'Capabilities': st.column_config.NumberColumn('Capabilities', min_value=1),
                    'Stories': st.column_config.NumberColumn('User Stories', min_value=1),
                    'Total Points': st.column_config.NumberColumn('Total Points', disabled=True),
                    'Delete': st.column_config.CheckboxColumn('Delete')
                },
                use_container_width=True,
                key=f'epic_editor_{epic_phase}'
            )
            
            # Apply changes button
            if st.button("Apply Changes", key=f'apply_{epic_phase}'):
                # Update epics
                new_epics = {}
                for _, row in edited_df.iterrows():
                    if not row['Delete']:
                        new_epics[row['Epic ID']] = {
                            'name': row['Name'],
                            'complexity': row['Complexity'],
                            'points': row['Points'],
                            'capabilities': row['Capabilities'],
                            'stories': row['Stories']
                        }
                
                st.session_state.epics[epic_phase] = new_epics
                st.success("Changes applied successfully!")
                st.rerun()
            
            # Summary metrics
            st.markdown("---")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                total_stories = edited_df['Stories'].sum()
                st.metric("Total Stories", total_stories)
            
            with col2:
                total_points = (edited_df['Points'] * edited_df['Stories']).sum()
                st.metric("Total Points", f"{total_points:,}")
            
            with col3:
                avg_complexity = total_points / len(edited_df) if len(edited_df) > 0 else 0
                st.metric("Avg Epic Size", f"{avg_complexity:.0f} points")

with tab3:
    st.header("Resource Planning")
    
    resource_phase = st.selectbox("Select Phase", ['Phase 1', 'Phase 2'], key='resource_phase')
    
    # Duration input
    duration_weeks = st.number_input(
        f"{resource_phase} Duration (weeks)",
        min_value=4,
        max_value=52,
        value=28 if resource_phase == 'Phase 1' else 16,
        key=f'duration_{resource_phase}'
    )
    
    # Resource estimation method
    estimation_method = st.radio(
        "Resource Estimation Method",
        ['Automatic (Based on Complexity)', 'Manual Override'],
        key=f'method_{resource_phase}'
    )
    
    if estimation_method == 'Automatic (Based on Complexity)':
        # Calculate recommended resources
        st.subheader("Recommended Resources Based on Complexity")
        
        complexity = calculate_phase_complexity(resource_phase)
        st.info(f"Phase Complexity: {complexity:,} story points")
        
        recommended_resources = estimate_resources_from_complexity(resource_phase, duration_weeks)
        
        # Display recommendations
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**🏢 Onsite**")
            for role, count in recommended_resources['Onsite'].items():
                st.write(f"• {role}: {count}")
        
        with col2:
            st.markdown("**🌍 Nearshore**")
            for role, count in recommended_resources['Nearshore'].items():
                st.write(f"• {role}: {count}")
        
        with col3:
            st.markdown("**🌏 Offshore**")
            for role, count in recommended_resources['Offshore'].items():
                st.write(f"• {role}: {count}")
        
        # Calculate metrics
        team_size = get_team_size_from_resources(recommended_resources)
        cost = calculate_cost_from_resources(recommended_resources, duration_weeks)
        
        st.markdown("---")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Team Size", team_size)
        with col2:
            st.metric("Weekly Velocity", f"{complexity/duration_weeks:.0f} points")
        with col3:
            st.metric("Base Cost", f"${cost:,.0f}")
        with col4:
            st.metric("With Contingency", f"${cost * (1 + contingency/100):,.0f}")
        
        # Apply recommendations button
        if st.button(f"Apply Recommendations to {resource_phase}"):
            if resource_phase not in st.session_state.custom_resources:
                st.session_state.custom_resources[resource_phase] = {}
            st.session_state.custom_resources[resource_phase] = recommended_resources
            st.success("Resources applied!")
    
    else:
        # Manual resource override
        st.subheader("Manual Resource Configuration")
        
        if resource_phase not in st.session_state.custom_resources:
            st.session_state.custom_resources[resource_phase] = {
                'Onsite': {},
                'Nearshore': {},
                'Offshore': {}
            }
        
        col1, col2, col3 = st.columns(3)
        
        # Manual resource editors
        with col1:
            st.markdown("**🏢 Onsite**")
            onsite_roles = list(st.session_state.rate_card['Onsite'].keys())
            
            for role in onsite_roles:
                current_val = st.session_state.custom_resources[resource_phase]['Onsite'].get(role, 0)
                new_val = st.number_input(
                    role,
                    min_value=0,
                    value=current_val,
                    key=f'onsite_{resource_phase}_{role}_manual'
                )
                if new_val > 0:
                    st.session_state.custom_resources[resource_phase]['Onsite'][role] = new_val
                elif role in st.session_state.custom_resources[resource_phase]['Onsite']:
                    del st.session_state.custom_resources[resource_phase]['Onsite'][role]
        
        with col2:
            st.markdown("**🌍 Nearshore**")
            nearshore_roles = list(st.session_state.rate_card['Nearshore'].keys())
            
            for role in nearshore_roles:
                current_val = st.session_state.custom_resources[resource_phase]['Nearshore'].get(role, 0)
                new_val = st.number_input(
                    role,
                    min_value=0,
                    value=current_val,
                    key=f'nearshore_{resource_phase}_{role}_manual'
                )
                if new_val > 0:
                    st.session_state.custom_resources[resource_phase]['Nearshore'][role] = new_val
                elif role in st.session_state.custom_resources[resource_phase]['Nearshore']:
                    del st.session_state.custom_resources[resource_phase]['Nearshore'][role]
        
        with col3:
            st.markdown("**🌏 Offshore**")
            offshore_roles = list(st.session_state.rate_card['Offshore'].keys())
            
            for role in offshore_roles:
                current_val = st.session_state.custom_resources[resource_phase]['Offshore'].get(role, 0)
                new_val = st.number_input(
                    role,
                    min_value=0,
                    value=current_val,
                    key=f'offshore_{resource_phase}_{role}_manual'
                )
                if new_val > 0:
                    st.session_state.custom_resources[resource_phase]['Offshore'][role] = new_val
                elif role in st.session_state.custom_resources[resource_phase]['Offshore']:
                    del st.session_state.custom_resources[resource_phase]['Offshore'][role]

with tab4:
    st.header("Rate Card Management")
    
    location = st.selectbox("Select Location", ['Onsite', 'Nearshore', 'Offshore'])
    
    # Add new role
    with st.expander("Add New Role"):
        new_role = st.text_input("Role Name")
        new_rate = st.number_input("Hourly Rate (USD)", min_value=10.0, value=50.0, step=0.5)
        
        if st.button("Add Role") and new_role:
            st.session_state.rate_card[location][new_role] = new_rate
            st.success(f"Added {new_role} at ${new_rate}/hr")
            st.rerun()
    
    # Edit existing rates
    st.subheader(f"{location} Rates")
    
    rates_data = []
    for role, rate in st.session_state.rate_card[location].items():
        rates_data.append({'Role': role, 'Rate ($/hr)': rate})
    
    if rates_data:
        df_rates = pd.DataFrame(rates_data)
        
        edited_rates = st.data_editor(
            df_rates,
            column_config={
                'Role': st.column_config.TextColumn('Role', disabled=True),
                'Rate ($/hr)': st.column_config.NumberColumn('Rate ($/hr)', min_value=10.0, step=0.5)
            },
            use_container_width=True,
            key=f'rate_editor_{location}'
        )
        
        if st.button(f"Update {location} Rates"):
            # Update rates
            for _, row in edited_rates.iterrows():
                st.session_state.rate_card[location][row['Role']] = row['Rate ($/hr)']
            st.success("Rates updated!")
            st.rerun()

with tab5:
    st.header("Project Analysis")
    
    # Complexity analysis
    st.subheader("Complexity Analysis")
    
    complexity_data = []
    for phase, epics in st.session_state.epics.items():
        for epic_id, epic_info in epics.items():
            complexity_data.append({
                'Phase': phase,
                'Epic': epic_id,
                'Name': epic_info['name'],
                'Complexity': epic_info['complexity'],
                'Points': epic_info['points'] * epic_info['stories']
            })
    
    if complexity_data:
        df_complexity = pd.DataFrame(complexity_data)
        
        # Complexity heatmap
        pivot_table = df_complexity.pivot_table(
            values='Points',
            index='Complexity',
            columns='Phase',
            aggfunc='sum',
            fill_value=0
        )
        
        fig = px.imshow(
            pivot_table,
            labels=dict(x="Phase", y="Complexity", color="Story Points"),
            title="Complexity Heatmap",
            color_continuous_scale="RdYlBu_r"
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Top complex epics
        st.subheader("Top 10 Most Complex Epics")
        top_epics = df_complexity.nlargest(10, 'Points')
        
        fig = px.bar(
            top_epics,
            x='Points',
            y='Name',
            color='Phase',
            orientation='h',
            title='Most Complex Epics by Points'
        )
        st.plotly_chart(fig, use_container_width=True)

with tab6:
    st.header("🎯 Dynamic Project Estimation")
    
    st.markdown("### Complete Project Estimation Based on Current Configuration")
    
    # Calculate estimations for both phases
    estimations = []
    
    for phase in ['Phase 1', 'Phase 2']:
        if phase in st.session_state.epics:
            # Get complexity
            complexity = calculate_phase_complexity(phase)
            
            # Estimate duration if not set
            estimated_weeks = max(8, int(complexity / (velocity_per_week * 25)))
            
            # Get or estimate resources
            if phase in st.session_state.custom_resources:
                resources = st.session_state.custom_resources[phase]
            else:
                resources = estimate_resources_from_complexity(phase, estimated_weeks)
            
            # Calculate cost
            cost = calculate_cost_from_resources(resources, estimated_weeks)
            team_size = get_team_size_from_resources(resources)
            
            estimations.append({
                'Phase': phase,
                'Epics': len(st.session_state.epics[phase]),
                'User Stories': sum(e['stories'] for e in st.session_state.epics[phase].values()),
                'Story Points': complexity,
                'Duration (weeks)': estimated_weeks,
                'Team Size': team_size,
                'Base Cost': cost,
                'Contingency': cost * (contingency/100),
                'Total Cost': cost * (1 + contingency/100),
                'Weekly Burn': cost / estimated_weeks if estimated_weeks > 0 else 0
            })
    
    # Display estimation summary
    df_estimation = pd.DataFrame(estimations)
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_duration = df_estimation['Duration (weeks)'].sum()
        st.metric("Total Duration", f"{total_duration} weeks")
        st.caption(f"~{total_duration/4.33:.1f} months")
    
    with col2:
        total_cost = df_estimation['Total Cost'].sum()
        st.metric("Total Investment", f"${total_cost/1000000:.2f}M")
        st.caption(f"Includes {contingency}% contingency")
    
    with col3:
        peak_team = df_estimation['Team Size'].max()
        st.metric("Peak Team Size", peak_team)
    
    with col4:
        total_points = df_estimation['Story Points'].sum()
        st.metric("Total Story Points", f"{total_points:,}")
    
    # Detailed estimation table
    st.subheader("Detailed Estimation by Phase")
    
    st.dataframe(
        df_estimation.style.format({
            'Base Cost': '${:,.0f}',
            'Contingency': '${:,.0f}',
            'Total Cost': '${:,.0f}',
            'Weekly Burn': '${:,.0f}',
            'Story Points': '{:,.0f}'
        }).background_gradient(subset=['Total Cost', 'Team Size', 'Story Points']),
        use_container_width=True
    )
    
    # Velocity analysis
    st.subheader("Velocity Analysis")
    
    velocity_data = []
    for est in estimations:
        if est['Duration (weeks)'] > 0 and est['Team Size'] > 0:
            velocity_data.append({
                'Phase': est['Phase'],
                'Points per Week': est['Story Points'] / est['Duration (weeks)'],
                'Points per Person': est['Story Points'] / (est['Team Size'] * est['Duration (weeks)']),
                'Cost per Point': est['Base Cost'] / est['Story Points'] if est['Story Points'] > 0 else 0
            })
    
    if velocity_data:
        df_velocity = pd.DataFrame(velocity_data)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            fig = px.bar(
                df_velocity,
                x='Phase',
                y='Points per Week',
                title='Weekly Velocity'
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            fig = px.bar(
                df_velocity,
                x='Phase',
                y='Points per Person',
                title='Individual Velocity'
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col3:
            fig = px.bar(
                df_velocity,
                x='Phase',
                y='Cost per Point',
                title='Cost Efficiency'
            )
            st.plotly_chart(fig, use_container_width=True)
    
    # Timeline visualization
    st.subheader("Project Timeline")
    
    timeline_data = []
    start_date = datetime(2025, 1, 1)
    
    for est in estimations:
        end_date = start_date + timedelta(weeks=est['Duration (weeks)'])
        timeline_data.append({
            'Phase': est['Phase'],
            'Start': start_date,
            'End': end_date,
            'Duration': f"{est['Duration (weeks)']} weeks"
        })
        start_date = end_date
    
    df_timeline = pd.DataFrame(timeline_data)
    
    fig = px.timeline(
        df_timeline,
        x_start='Start',
        x_end='End',
        y='Phase',
        title='Estimated Project Timeline'
    )
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(fig, use_container_width=True)
    
    # Export final estimation
    if st.button("📥 Export Complete Estimation"):
        export_data = {
            'estimation_summary': df_estimation.to_dict(),
            'epics': st.session_state.epics,
            'rate_card': st.session_state.rate_card,
            'resources': st.session_state.custom_resources,
            'velocity_analysis': df_velocity.to_dict() if velocity_data else {},
            'timeline': df_timeline.to_dict(),
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'contingency_percent': contingency,
                'velocity_per_week': velocity_per_week
            }
        }
        
        st.download_button(
            label="Download Complete Estimation",
            data=json.dumps(export_data, indent=2, default=str),
            file_name=f"marken_complete_estimation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )

# Footer
st.markdown("---")
st.info("""
**Features of this tool:**
- ✏️ Add, edit, or delete epics with custom complexity points
- 📊 Automatic resource estimation based on complexity
- 👥 Manual resource override capability
- 💰 Dynamic cost calculation
- 📈 Real-time project metrics
- 💾 Export/import complete configurations
- 🎯 Velocity-based duration estimation
""")

st.warning("""
**Quick Guide:**
1. **Epic Management**: Add/edit epics and their complexity in the "Epic Management" tab
2. **Resource Planning**: Choose automatic (complexity-based) or manual resource allocation
3. **Rate Cards**: Adjust hourly rates per location and role
4. **Analysis**: View complexity heatmaps and identify high-risk epics
5. **Estimation**: Get complete project estimation with timeline and costs
""")
