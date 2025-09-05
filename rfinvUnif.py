import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import json
from io import BytesIO
import xlsxwriter

# Page configuration
st.set_page_config(
    page_title="SPLUS RTM Project Management",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'epics' not in st.session_state:
    st.session_state.epics = {
        'EPIC-001': {
            'name': 'Customer Account Management Platform',
            'priority': 'P0',
            'duration_months': 4,
            'total_points': 144,
            'capabilities': {
                'C1.1': {
                    'name': 'Customer Profile Management',
                    'user_stories': [
                        {'id': 'US-001.1', 'name': 'Create and manage customer profiles', 'points': 13, 'complexity': 'High'},
                        {'id': 'US-001.2', 'name': 'Self-register and manage preferences', 'points': 8, 'complexity': 'Medium'},
                        {'id': 'US-001.3', 'name': 'Configure credit limits and payment terms', 'points': 5, 'complexity': 'Medium'}
                    ]
                },
                'C1.2': {
                    'name': 'Contract & SLA Management',
                    'user_stories': [
                        {'id': 'US-001.4', 'name': 'Define customer-specific contracts', 'points': 21, 'complexity': 'High'},
                        {'id': 'US-001.5', 'name': 'Automatically enforce SLA terms', 'points': 13, 'complexity': 'High'}
                    ]
                },
                'C1.3': {
                    'name': 'Customer Portal (CFW)',
                    'user_stories': [
                        {'id': 'US-001.6', 'name': 'Responsive web portal for tracking', 'points': 21, 'complexity': 'High'}
                    ]
                }
            }
        },
        'EPIC-002': {
            'name': 'Order Management System (OMS)',
            'priority': 'P0',
            'duration_months': 5,
            'total_points': 178,
            'capabilities': {
                'C2.1': {
                    'name': 'Order Creation & Processing',
                    'user_stories': [
                        {'id': 'US-002.1', 'name': 'Create orders with inventory validation', 'points': 13, 'complexity': 'High'},
                        {'id': 'US-002.2', 'name': 'Place orders through multiple channels', 'points': 21, 'complexity': 'High'},
                        {'id': 'US-002.3', 'name': 'Auto-allocate inventory', 'points': 13, 'complexity': 'High'}
                    ]
                },
                'C2.2': {
                    'name': 'Activity Board & Monitoring',
                    'user_stories': [
                        {'id': 'US-002.4', 'name': 'Real-time order status dashboard', 'points': 8, 'complexity': 'Medium'},
                        {'id': 'US-002.5', 'name': 'Manage order exceptions', 'points': 13, 'complexity': 'High'}
                    ]
                }
            }
        },
        'EPIC-003': {
            'name': 'Inventory Management Platform',
            'priority': 'P0',
            'duration_months': 6,
            'total_points': 233,
            'capabilities': {
                'C3.1': {
                    'name': 'Real-time Inventory Tracking',
                    'user_stories': [
                        {'id': 'US-003.1', 'name': 'Real-time inventory visibility', 'points': 13, 'complexity': 'High'},
                        {'id': 'US-003.2', 'name': 'Track serialized inventory', 'points': 21, 'complexity': 'High'},
                        {'id': 'US-003.3', 'name': 'Automated replenishment', 'points': 13, 'complexity': 'High'}
                    ]
                }
            }
        },
        'EPIC-004': {
            'name': 'WMS & RF Scanner Integration',
            'priority': 'P0',
            'duration_months': 5,
            'total_points': 199,
            'capabilities': {}
        },
        'EPIC-005': {
            'name': 'Routing & Transportation Management',
            'priority': 'P1',
            'duration_months': 4,
            'total_points': 178,
            'capabilities': {}
        }
    }

if 'resource_rates' not in st.session_state:
    st.session_state.resource_rates = {
        'onsite': {
            'Head of Technology': 140,
            'Senior Technical Architect': 113,
            'Technical Architect': 103,
            'Project Manager': 103,
            'Senior Developer': 87,
            'Team Lead': 89,
            'DevOps Engineer': 87,
            'Business Analyst': 82
        },
        'offshore': {
            'Senior Developer': 23,
            'Developer': 21,
            'Junior Developer': 19,
            'Integration Developer': 23,
            'Tester': 20,
            'Automation Tester': 22,
            'Performance Tester': 22
        }
    }

if 'phases' not in st.session_state:
    st.session_state.phases = {
        'Phase 0': {
            'name': 'Foundation',
            'duration': 2,
            'start_month': 1,
            'team': {
                'onsite': {'Head of Technology': 1, 'Senior Technical Architect': 2},
                'offshore': {'Senior Developer': 2, 'DevOps Engineer': 1}
            },
            'epics': []
        },
        'Phase 1': {
            'name': 'Core Platform',
            'duration': 4,
            'start_month': 3,
            'team': {
                'onsite': {'Head of Technology': 1, 'Senior Technical Architect': 2, 'Team Lead': 1},
                'offshore': {'Senior Developer': 2, 'Developer': 2, 'Automation Tester': 1}
            },
            'epics': ['EPIC-001', 'EPIC-010']
        },
        'Phase 2': {
            'name': 'Order Management',
            'duration': 4,
            'start_month': 7,
            'team': {
                'onsite': {'Head of Technology': 1, 'Senior Technical Architect': 2, 'Team Lead': 2},
                'offshore': {'Senior Developer': 2, 'Developer': 4, 'Automation Tester': 2}
            },
            'epics': ['EPIC-002']
        },
        'Phase 3': {
            'name': 'Inventory & WMS',
            'duration': 5,
            'start_month': 11,
            'team': {
                'onsite': {'Head of Technology': 1, 'Senior Technical Architect': 2, 'Team Lead': 3},
                'offshore': {'Senior Developer': 3, 'Developer': 6, 'Automation Tester': 3}
            },
            'epics': ['EPIC-003', 'EPIC-004']
        },
        'Phase 4': {
            'name': 'Transportation',
            'duration': 4,
            'start_month': 16,
            'team': {
                'onsite': {'Head of Technology': 1, 'Senior Technical Architect': 2, 'Team Lead': 3},
                'offshore': {'Senior Developer': 3, 'Developer': 6, 'Automation Tester': 3}
            },
            'epics': ['EPIC-005', 'EPIC-006']
        },
        'Phase 5': {
            'name': 'Integration & Analytics',
            'duration': 3,
            'start_month': 20,
            'team': {
                'onsite': {'Head of Technology': 1, 'Senior Technical Architect': 2, 'Team Lead': 2},
                'offshore': {'Senior Developer': 2, 'Developer': 4, 'Automation Tester': 2}
            },
            'epics': ['EPIC-007', 'EPIC-008', 'EPIC-009']
        },
        'Phase 6': {
            'name': 'Optimization',
            'duration': 2,
            'start_month': 23,
            'team': {
                'onsite': {'Head of Technology': 1, 'Senior Technical Architect': 2, 'Team Lead': 1},
                'offshore': {'Senior Developer': 2, 'Developer': 2, 'Performance Tester': 2}
            },
            'epics': []
        }
    }

if 'contingency' not in st.session_state:
    st.session_state.contingency = 15

def calculate_phase_cost(phase_data):
    monthly_cost = 0
    hours_per_month = 160
    
    # Calculate onsite costs
    for role, count in phase_data['team']['onsite'].items():
        if role in st.session_state.resource_rates['onsite']:
            rate = st.session_state.resource_rates['onsite'][role]
            monthly_cost += rate * hours_per_month * count
    
    # Calculate offshore costs
    for role, count in phase_data['team']['offshore'].items():
        role_key = role
        # Map role to rate key
        if role == 'DevOps Engineer':
            role_key = 'Developer'
        if role_key in st.session_state.resource_rates['offshore']:
            rate = st.session_state.resource_rates['offshore'][role_key]
            monthly_cost += rate * hours_per_month * count
    
    total_phase_cost = monthly_cost * phase_data['duration']
    return monthly_cost, total_phase_cost

def calculate_total_project_cost():
    total_cost = 0
    for phase_name, phase_data in st.session_state.phases.items():
        _, phase_cost = calculate_phase_cost(phase_data)
        total_cost += phase_cost
    
    contingency_amount = total_cost * (st.session_state.contingency / 100)
    total_with_contingency = total_cost + contingency_amount
    
    return total_cost, contingency_amount, total_with_contingency

def calculate_epic_points(epic_data):
    total_points = 0
    for cap_id, cap_data in epic_data.get('capabilities', {}).items():
        for story in cap_data.get('user_stories', []):
            total_points += story['points']
    return total_points

# Custom CSS
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1e3d59;
        text-align: center;
        margin-bottom: 2rem;
        padding: 1rem;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .metric-card {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
        font-size: 1rem;
    }
    </style>
""", unsafe_allow_html=True)

# Header
st.markdown('<h1 class="main-header">🚀 SPLUS RTM Project Management Dashboard</h1>', unsafe_allow_html=True)

# Sidebar for navigation
with st.sidebar:
    st.markdown("## 🎯 Navigation")
    page = st.selectbox(
        "Select Page",
        ["Executive Dashboard", "Timelines & Phases", "EPICs Management", 
         "Capabilities", "User Stories", "Cost Analysis", "Reports"]
    )
    
    st.markdown("---")
    st.markdown("## ⚙️ Settings")
    
    # Contingency slider that properly updates
    new_contingency = st.slider(
        "Contingency %",
        min_value=0,
        max_value=50,
        value=st.session_state.contingency,
        step=5,
        key="contingency_slider",
        help="Adjust project contingency percentage"
    )
    
    # Update contingency in session state if changed
    if new_contingency != st.session_state.contingency:
        st.session_state.contingency = new_contingency
        st.rerun()
    
    # Display current contingency
    st.info(f"Current Contingency: {st.session_state.contingency}%")

# Main content based on selected page
if page == "Executive Dashboard":
    st.markdown("## 📊 Executive Summary")
    
    # Calculate metrics
    total_cost, contingency_amount, total_with_contingency = calculate_total_project_cost()
    total_epics = len(st.session_state.epics)
    total_points = sum(epic['total_points'] for epic in st.session_state.epics.values())
    
    # Display key metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Investment", f"${total_with_contingency:,.0f}", f"Includes {st.session_state.contingency}% contingency")
    with col2:
        st.metric("Project Duration", "24 months", "6 phases")
    with col3:
        st.metric("Total EPICs", total_epics, f"{total_points} story points")
    with col4:
        st.metric("Contingency Amount", f"${contingency_amount:,.0f}", f"{st.session_state.contingency}%")
    
    # Phase distribution chart
    st.markdown("### 📈 Phase-wise Cost Distribution")
    phase_costs = []
    phase_names = []
    for phase_name, phase_data in st.session_state.phases.items():
        _, phase_cost = calculate_phase_cost(phase_data)
        phase_costs.append(phase_cost)
        phase_names.append(f"{phase_name}: {phase_data['name']}")
    
    fig = px.bar(
        x=phase_names, 
        y=phase_costs,
        title="Cost Distribution Across Phases",
        labels={'x': 'Phase', 'y': 'Cost ($)'},
        color=phase_costs,
        color_continuous_scale='Viridis'
    )
    fig.update_layout(height=400, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)
    
    # EPICs Priority Distribution
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 🎯 EPICs Priority Distribution")
        priority_count = {}
        for epic in st.session_state.epics.values():
            priority = epic.get('priority', 'P2')
            priority_count[priority] = priority_count.get(priority, 0) + 1
        
        fig = px.pie(
            values=list(priority_count.values()),
            names=list(priority_count.keys()),
            title="EPICs by Priority",
            color_discrete_map={'P0': '#FF4B4B', 'P1': '#FFA500', 'P2': '#4CAF50'}
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("### 📊 Story Points Distribution")
        epic_points = {epic_id: epic['total_points'] 
                      for epic_id, epic in st.session_state.epics.items()}
        fig = px.bar(
            x=list(epic_points.keys()),
            y=list(epic_points.values()),
            title="Story Points by EPIC",
            labels={'x': 'EPIC', 'y': 'Story Points'},
            color=list(epic_points.values()),
            color_continuous_scale='Blues'
        )
        st.plotly_chart(fig, use_container_width=True)

elif page == "Timelines & Phases":
    st.markdown("## 📅 Project Timeline & Phases")
    
    # Create Gantt chart
    gantt_data = []
    for phase_name, phase_data in st.session_state.phases.items():
        start_date = datetime(2025, 1, 1) + timedelta(days=(phase_data['start_month']-1)*30)
        end_date = start_date + timedelta(days=phase_data['duration']*30)
        gantt_data.append({
            'Task': f"{phase_name}: {phase_data['name']}",
            'Start': start_date,
            'Finish': end_date,
            'Resource': phase_name
        })
    
    df_gantt = pd.DataFrame(gantt_data)
    fig = px.timeline(
        df_gantt, 
        x_start="Start", 
        x_end="Finish", 
        y="Task",
        title="Project Timeline (24 Months)",
        color="Resource"
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(height=500)
    st.plotly_chart(fig, use_container_width=True)
    
    # Phase details
    st.markdown("### 📋 Phase Details")
    for phase_name, phase_data in st.session_state.phases.items():
        with st.expander(f"{phase_name}: {phase_data['name']}"):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Duration", f"{phase_data['duration']} months")
                st.metric("Start Month", phase_data['start_month'])
            with col2:
                monthly_cost, phase_cost = calculate_phase_cost(phase_data)
                st.metric("Monthly Cost", f"${monthly_cost:,.0f}")
                st.metric("Total Phase Cost", f"${phase_cost:,.0f}")
            with col3:
                st.markdown("**Team Composition:**")
                st.markdown("*Onsite:*")
                for role, count in phase_data['team']['onsite'].items():
                    st.write(f"• {role}: {count}")
                st.markdown("*Offshore:*")
                for role, count in phase_data['team']['offshore'].items():
                    st.write(f"• {role}: {count}")
            
            if phase_data['epics']:
                st.markdown("**Assigned EPICs:**")
                for epic_id in phase_data['epics']:
                    if epic_id in st.session_state.epics:
                        st.write(f"• {epic_id}: {st.session_state.epics[epic_id]['name']}")

elif page == "EPICs Management":
    st.markdown("## 🎯 EPICs Management")
    
    # Add new EPIC
    with st.expander("➕ Add New EPIC"):
        col1, col2, col3 = st.columns(3)
        with col1:
            new_epic_id = st.text_input("EPIC ID", placeholder="EPIC-XXX")
            new_epic_name = st.text_input("EPIC Name", placeholder="Enter EPIC name")
        with col2:
            new_epic_priority = st.selectbox("Priority", ["P0", "P1", "P2"])
            new_epic_duration = st.number_input("Duration (months)", min_value=1, max_value=12, value=3)
        with col3:
            new_epic_points = st.number_input("Initial Story Points", min_value=0, value=89)
            if st.button("Add EPIC", type="primary"):
                if new_epic_id and new_epic_name:
                    st.session_state.epics[new_epic_id] = {
                        'name': new_epic_name,
                        'priority': new_epic_priority,
                        'duration_months': new_epic_duration,
                        'total_points': new_epic_points,
                        'capabilities': {}
                    }
                    st.success(f"✅ EPIC {new_epic_id} added successfully!")
                    st.rerun()
    
    # Display and edit existing EPICs
    st.markdown("### 📊 Existing EPICs")
    
    # Create tabs for each EPIC
    if st.session_state.epics:
        epic_tabs = st.tabs(list(st.session_state.epics.keys()))
        
        for idx, (epic_id, epic_data) in enumerate(st.session_state.epics.items()):
            with epic_tabs[idx]:
                col1, col2, col3, col4, col5 = st.columns(5)
                
                with col1:
                    updated_name = st.text_input(
                        "Name", 
                        value=epic_data['name'],
                        key=f"epic_name_{epic_id}"
                    )
                    if updated_name != epic_data['name']:
                        st.session_state.epics[epic_id]['name'] = updated_name
                
                with col2:
                    updated_priority = st.selectbox(
                        "Priority",
                        ["P0", "P1", "P2"],
                        index=["P0", "P1", "P2"].index(epic_data['priority']),
                        key=f"epic_priority_{epic_id}"
                    )
                    if updated_priority != epic_data['priority']:
                        st.session_state.epics[epic_id]['priority'] = updated_priority
                
                with col3:
                    updated_duration = st.number_input(
                        "Duration (months)",
                        min_value=1,
                        max_value=12,
                        value=epic_data['duration_months'],
                        key=f"epic_duration_{epic_id}"
                    )
                    if updated_duration != epic_data['duration_months']:
                        st.session_state.epics[epic_id]['duration_months'] = updated_duration
                
                with col4:
                    # Recalculate points based on capabilities
                    calculated_points = calculate_epic_points(epic_data)
                    st.metric("Total Story Points", calculated_points)
                    st.session_state.epics[epic_id]['total_points'] = calculated_points
                
                with col5:
                    if st.button(f"🗑️ Delete", key=f"delete_{epic_id}"):
                        del st.session_state.epics[epic_id]
                        st.rerun()
                
                # Display capabilities for this EPIC
                st.markdown(f"#### Capabilities for {epic_id}")
                
                # Add new capability
                with st.expander("➕ Add Capability"):
                    cap_col1, cap_col2, cap_col3 = st.columns(3)
                    with cap_col1:
                        new_cap_id = st.text_input("Capability ID", placeholder="C1.X", key=f"new_cap_id_{epic_id}")
                    with cap_col2:
                        new_cap_name = st.text_input("Capability Name", key=f"new_cap_name_{epic_id}")
                    with cap_col3:
                        if st.button("Add Capability", key=f"add_cap_{epic_id}"):
                            if new_cap_id and new_cap_name:
                                if 'capabilities' not in st.session_state.epics[epic_id]:
                                    st.session_state.epics[epic_id]['capabilities'] = {}
                                st.session_state.epics[epic_id]['capabilities'][new_cap_id] = {
                                    'name': new_cap_name,
                                    'user_stories': []
                                }
                                st.success(f"✅ Capability {new_cap_id} added!")
                                st.rerun()
                
                # Display existing capabilities
                if epic_data.get('capabilities'):
                    for cap_id, cap_data in epic_data['capabilities'].items():
                        st.write(f"**{cap_id}: {cap_data['name']}**")
                        st.write(f"User Stories: {len(cap_data.get('user_stories', []))}")

elif page == "Capabilities":
    st.markdown("## 🔧 Capabilities Management")
    
    # Select EPIC to manage capabilities
    selected_epic = st.selectbox(
        "Select EPIC",
        options=list(st.session_state.epics.keys()),
        format_func=lambda x: f"{x}: {st.session_state.epics[x]['name']}"
    )
    
    if selected_epic:
        epic_data = st.session_state.epics[selected_epic]
        st.markdown(f"### Managing Capabilities for {selected_epic}")
        
        # Display capabilities
        if epic_data.get('capabilities'):
            for cap_id, cap_data in epic_data['capabilities'].items():
                with st.expander(f"{cap_id}: {cap_data['name']}"):
                    # Edit capability name
                    updated_cap_name = st.text_input(
                        "Capability Name",
                        value=cap_data['name'],
                        key=f"cap_name_{selected_epic}_{cap_id}"
                    )
                    if updated_cap_name != cap_data['name']:
                        st.session_state.epics[selected_epic]['capabilities'][cap_id]['name'] = updated_cap_name
                    
                    # Display user stories count
                    st.metric("User Stories", len(cap_data.get('user_stories', [])))
                    
                    # Delete capability button
                    if st.button(f"🗑️ Delete Capability", key=f"del_cap_{selected_epic}_{cap_id}"):
                        del st.session_state.epics[selected_epic]['capabilities'][cap_id]
                        st.rerun()
        else:
            st.info("No capabilities defined for this EPIC yet.")

elif page == "User Stories":
    st.markdown("## 📝 User Stories Management")
    
    # Select EPIC and Capability
    col1, col2 = st.columns(2)
    with col1:
        selected_epic = st.selectbox(
            "Select EPIC",
            options=list(st.session_state.epics.keys()),
            format_func=lambda x: f"{x}: {st.session_state.epics[x]['name']}"
        )
    
    with col2:
        if selected_epic and st.session_state.epics[selected_epic].get('capabilities'):
            capability_options = list(st.session_state.epics[selected_epic]['capabilities'].keys())
            selected_capability = st.selectbox(
                "Select Capability",
                options=capability_options,
                format_func=lambda x: f"{x}: {st.session_state.epics[selected_epic]['capabilities'][x]['name']}"
            )
        else:
            selected_capability = None
            st.info("No capabilities available for selected EPIC")
    
    if selected_epic and selected_capability:
        cap_data = st.session_state.epics[selected_epic]['capabilities'][selected_capability]
        
        # Add new user story
        st.markdown("### ➕ Add User Story")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            new_story_id = st.text_input("Story ID", placeholder="US-XXX.X")
        with col2:
            new_story_name = st.text_input("Story Description")
        with col3:
            new_story_points = st.number_input("Story Points", min_value=1, max_value=34, value=8)
        with col4:
            new_story_complexity = st.selectbox("Complexity", ["Low", "Medium", "High", "Very High"])
            
        if st.button("Add User Story", type="primary"):
            if new_story_id and new_story_name:
                if 'user_stories' not in cap_data:
                    cap_data['user_stories'] = []
                cap_data['user_stories'].append({
                    'id': new_story_id,
                    'name': new_story_name,
                    'points': new_story_points,
                    'complexity': new_story_complexity
                })
                st.success(f"✅ User Story {new_story_id} added!")
                st.rerun()
        
        # Display existing user stories
        st.markdown("### 📋 Existing User Stories")
        if cap_data.get('user_stories'):
            for idx, story in enumerate(cap_data['user_stories']):
                with st.expander(f"{story['id']}: {story['name']}"):
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        updated_name = st.text_input(
                            "Description",
                            value=story['name'],
                            key=f"story_name_{selected_epic}_{selected_capability}_{idx}"
                        )
                        if updated_name != story['name']:
                            cap_data['user_stories'][idx]['name'] = updated_name
                    
                    with col2:
                        updated_points = st.number_input(
                            "Points",
                            min_value=1,
                            max_value=34,
                            value=story['points'],
                            key=f"story_points_{selected_epic}_{selected_capability}_{idx}"
                        )
                        if updated_points != story['points']:
                            cap_data['user_stories'][idx]['points'] = updated_points
                            st.rerun()
                    
                    with col3:
                        complexity_options = ["Low", "Medium", "High", "Very High"]
                        current_idx = complexity_options.index(story['complexity']) if story['complexity'] in complexity_options else 1
                        updated_complexity = st.selectbox(
                            "Complexity",
                            complexity_options,
                            index=current_idx,
                            key=f"story_complexity_{selected_epic}_{selected_capability}_{idx}"
                        )
                        if updated_complexity != story['complexity']:
                            cap_data['user_stories'][idx]['complexity'] = updated_complexity
                    
                    with col4:
                        if st.button(f"🗑️ Delete", key=f"del_story_{selected_epic}_{selected_capability}_{idx}"):
                            cap_data['user_stories'].pop(idx)
                            st.rerun()
        else:
            st.info("No user stories defined yet.")

elif page == "Cost Analysis":
    st.markdown("## 💰 Cost Analysis")
    
    # Overall cost summary
    total_cost, contingency_amount, total_with_contingency = calculate_total_project_cost()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Base Cost", f"${total_cost:,.0f}")
    with col2:
        st.metric(f"Contingency ({st.session_state.contingency}%)", f"${contingency_amount:,.0f}")
    with col3:
        st.metric("Total Investment", f"${total_with_contingency:,.0f}")
    
    # Phase-wise cost breakdown
    st.markdown("### 📊 Phase-wise Cost Breakdown")
    
    phase_data = []
    for phase_name, phase_info in st.session_state.phases.items():
        monthly_cost, phase_cost = calculate_phase_cost(phase_info)
        phase_data.append({
            'Phase': phase_name,
            'Name': phase_info['name'],
            'Duration (months)': phase_info['duration'],
            'Monthly Cost': f"${monthly_cost:,.0f}",
            'Total Cost': f"${phase_cost:,.0f}",
            'With Contingency': f"${phase_cost * (1 + st.session_state.contingency/100):,.0f}"
        })
    
    df_phases = pd.DataFrame(phase_data)
    st.dataframe(df_phases, use_container_width=True, hide_index=True)
    
    # Resource utilization
    st.markdown("### 👥 Resource Utilization")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Onsite Resources")
        onsite_df = pd.DataFrame([
            {'Role': role, 'Hourly Rate': f"${rate}", 'Annual Cost': f"${rate * 2080:,.0f}"}
            for role, rate in st.session_state.resource_rates['onsite'].items()
        ])
        st.dataframe(onsite_df, use_container_width=True, hide_index=True)
    
    with col2:
        st.markdown("#### Offshore Resources")
        offshore_df = pd.DataFrame([
            {'Role': role, 'Hourly Rate': f"${rate}", 'Annual Cost': f"${rate * 2080:,.0f}"}
            for role, rate in st.session_state.resource_rates['offshore'].items()
        ])
        st.dataframe(offshore_df, use_container_width=True, hide_index=True)
    
    # Cost projection chart
    st.markdown("### 📈 Cost Projection Over Time")
    
    months = []
    cumulative_costs = []
    cumulative_cost = 0
    
    for phase_name, phase_info in st.session_state.phases.items():
        monthly_cost, _ = calculate_phase_cost(phase_info)
        for month in range(phase_info['start_month'], phase_info['start_month'] + phase_info['duration']):
            months.append(f"Month {month}")
            cumulative_cost += monthly_cost * (1 + st.session_state.contingency/100)
            cumulative_costs.append(cumulative_cost)
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=months,
        y=cumulative_costs,
        mode='lines+markers',
        name='Cumulative Cost',
        line=dict(color='#1e3d59', width=3),
        fill='tonexty',
        fillcolor='rgba(30, 61, 89, 0.1)'
    ))
    
    fig.update_layout(
        title="Cumulative Cost Projection",
        xaxis_title="Timeline",
        yaxis_title="Cost ($)",
        hovermode='x unified',
        height=400
    )
    st.plotly_chart(fig, use_container_width=True)

elif page == "Reports":
    st.markdown("## 📄 Reports & Downloads")
    
    # Generate comprehensive report
    st.markdown("### 📊 Generate Reports")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📥 Download EPICs Report", type="primary", use_container_width=True):
            # Create Excel file with EPICs data
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                # EPICs summary
                epics_data = []
                for epic_id, epic_info in st.session_state.epics.items():
                    epics_data.append({
                        'EPIC ID': epic_id,
                        'Name': epic_info['name'],
                        'Priority': epic_info['priority'],
                        'Duration': epic_info['duration_months'],
                        'Story Points': epic_info['total_points']
                    })
                df_epics = pd.DataFrame(epics_data)
                df_epics.to_excel(writer, sheet_name='EPICs', index=False)
                
                # Capabilities
                cap_data = []
                for epic_id, epic_info in st.session_state.epics.items():
                    for cap_id, cap_info in epic_info.get('capabilities', {}).items():
                        cap_data.append({
                            'EPIC': epic_id,
                            'Capability ID': cap_id,
                            'Capability Name': cap_info['name'],
                            'User Stories Count': len(cap_info.get('user_stories', []))
                        })
                df_caps = pd.DataFrame(cap_data)
                df_caps.to_excel(writer, sheet_name='Capabilities', index=False)
                
                # User Stories
                stories_data = []
                for epic_id, epic_info in st.session_state.epics.items():
                    for cap_id, cap_info in epic_info.get('capabilities', {}).items():
                        for story in cap_info.get('user_stories', []):
                            stories_data.append({
                                'EPIC': epic_id,
                                'Capability': cap_id,
                                'Story ID': story['id'],
                                'Description': story['name'],
                                'Points': story['points'],
                                'Complexity': story['complexity']
                            })
                df_stories = pd.DataFrame(stories_data)
                df_stories.to_excel(writer, sheet_name='User Stories', index=False)
            
            st.download_button(
                label="📥 Download EPICs Excel Report",
                data=output.getvalue(),
                file_name=f"SPLUS_RTM_EPICs_Report_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    
    with col2:
        if st.button("💰 Download Cost Analysis", type="primary", use_container_width=True):
            # Create cost analysis report
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                # Phase costs
                phase_costs = []
                for phase_name, phase_info in st.session_state.phases.items():
                    monthly_cost, phase_cost = calculate_phase_cost(phase_info)
                    phase_costs.append({
                        'Phase': phase_name,
                        'Name': phase_info['name'],
                        'Duration': phase_info['duration'],
                        'Monthly Cost': monthly_cost,
                        'Total Cost': phase_cost,
                        'With Contingency': phase_cost * (1 + st.session_state.contingency/100)
                    })
                df_phase_costs = pd.DataFrame(phase_costs)
                df_phase_costs.to_excel(writer, sheet_name='Phase Costs', index=False)
                
                # Resource rates
                df_onsite = pd.DataFrame(list(st.session_state.resource_rates['onsite'].items()), 
                                        columns=['Role', 'Hourly Rate'])
                df_onsite.to_excel(writer, sheet_name='Onsite Rates', index=False)
                
                df_offshore = pd.DataFrame(list(st.session_state.resource_rates['offshore'].items()), 
                                          columns=['Role', 'Hourly Rate'])
                df_offshore.to_excel(writer, sheet_name='Offshore Rates', index=False)
            
            st.download_button(
                label="📥 Download Cost Analysis Excel",
                data=output.getvalue(),
                file_name=f"SPLUS_RTM_Cost_Analysis_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    
    with col3:
        if st.button("📋 Download Full Project Report", type="primary", use_container_width=True):
            # Generate comprehensive JSON report
            project_data = {
                'project_name': 'SPLUS RTM Modernization',
                'generated_date': datetime.now().isoformat(),
                'total_investment': total_with_contingency,
                'contingency_percentage': st.session_state.contingency,
                'duration_months': 24,
                'epics': st.session_state.epics,
                'phases': st.session_state.phases,
                'resource_rates': st.session_state.resource_rates
            }
            
            json_str = json.dumps(project_data, indent=2, default=str)
            st.download_button(
                label="📥 Download Full Project JSON",
                data=json_str,
                file_name=f"SPLUS_RTM_Project_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json"
            )
    
    # Display summary statistics
    st.markdown("### 📊 Project Statistics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_epics = len(st.session_state.epics)
        st.metric("Total EPICs", total_epics)
    
    with col2:
        total_capabilities = sum(len(epic.get('capabilities', {})) for epic in st.session_state.epics.values())
        st.metric("Total Capabilities", total_capabilities)
    
    with col3:
        total_stories = sum(
            len(cap.get('user_stories', []))
            for epic in st.session_state.epics.values()
            for cap in epic.get('capabilities', {}).values()
        )
        st.metric("Total User Stories", total_stories)
    
    with col4:
        total_points = sum(epic['total_points'] for epic in st.session_state.epics.values())
        st.metric("Total Story Points", total_points)
    
    # Project timeline summary
    st.markdown("### 📅 Timeline Summary")
    timeline_df = pd.DataFrame([
        {
            'Phase': phase_name,
            'Name': phase_info['name'],
            'Start Month': phase_info['start_month'],
            'End Month': phase_info['start_month'] + phase_info['duration'] - 1,
            'Duration': f"{phase_info['duration']} months",
            'EPICs': ', '.join(phase_info['epics']) if phase_info['epics'] else 'Foundation/Support'
        }
        for phase_name, phase_info in st.session_state.phases.items()
    ])
    st.dataframe(timeline_df, use_container_width=True, hide_index=True)

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666;'>
        <p>SPLUS RTM Project Management Dashboard | Generated on {}</p>
        <p>Total Investment: ${:,.0f} (Including {}% Contingency)</p>
    </div>
    """.format(
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        calculate_total_project_cost()[2],
        st.session_state.contingency
    ),
    unsafe_allow_html=True
)
